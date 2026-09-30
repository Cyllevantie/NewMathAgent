# -*- coding: utf-8 -*-
"""⓪ 读题：上传原件 → AI 读 → 人确认 → 才往下跑。

这一族的判据都围绕两条地基（见 `lib/web/server.py` 的「⓪ 读题」那一段）：
  · **发现 A**：agent 绝不能在阶段内改 `request/`/`data/` ⇒ 搬文件只能由服务端在链外做。
  · **发现 B**：确认时的搬运会让下一次点「开始全链」触发换题轮转，把 `reports/` 整份扫走 ⇒
    读题产物必须另存一份在 `runtime/quality/intake/`（轮转搬不走）并幂等恢复。

写法照 `test_stale_noise.py`：**每条正题配一个对照组**，否则断言可能只是恒真。
"""
import asyncio
import json
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))
sys.path.insert(0, str(PROJECT / "regression"))
from test_workflow import load_server  # noqa: E402

INBOX = "request/_inbox"


class IntakeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for rel in ("CLAUDE.md", "AGENTS.md"):
            shutil.copy2(PROJECT / rel, self.root / rel)
        for rel in ("skills", "docs"):
            shutil.copytree(PROJECT / rel, self.root / rel)
        self.s = load_server(self.root)

    # ---- 夹具（`install_successful_runner` 是 `test_workflow` 里测试类的方法，
    #      这里照它的口径重写一份最小的：桩掉 `_call`、写报告、记下阶段调用顺序）----

    def stage(self, sid):
        return next(x for x in self.s.STAGES if x["id"] == sid)

    def install_successful_runner(self, after=None):
        calls = []

        async def runner(prompt, sid, cap=None):
            calls.append(sid)
            st = self.stage(sid)
            if sid == "write":
                (self.root / "paper").mkdir(exist_ok=True)
                # 必须 >80 字节：`_artifact_ok('write')` 卡的就是大小。低于这个数时 write 会被
                #   判失败、整链挂起，而报错只说"阶段未成功完成：failed"。
                (self.root / "paper/main.pdf").write_bytes(b"%PDF-1.4\n" + b"x" * 200)
            else:
                # 报告必须**真写出来**：`_artifact_ok()` 看的就是它，缺了会被判"阶段失败"。
                #   （注意别写成 `self.s.report(...)` —— 那个方法在测试类上、不在模块上，
                #    会抛 AttributeError，阶段按失败收场，黄灯的 kind 变成 failure。）
                rp = self.s.REPORTS / st["report"]
                rp.parent.mkdir(parents=True, exist_ok=True)
                rp.write_text("最终结论：PASS\n" + "evidence " * 30, encoding="utf-8")
            if sid == "code":
                (self.root / "code").mkdir(exist_ok=True)
                (self.root / "code/example.txt").write_text("fixture", encoding="utf-8")
            if st.get("gate"):
                side = (self.s.REPORTS / st["report"]).with_suffix(".verdict.json")
                side.write_text(json.dumps({"schema_version": 1, "stage": sid,
                                            "input_digest": self.s._input_digest(st),
                                            "status": "PASS", "issues": []}), encoding="utf-8")
            if after:
                after(sid)
            return 0, "", False

        self.s._call = runner
        return calls

    # ---- 夹具 ----

    def inbox(self, *rels, body=b"x"):
        for rel in rels:
            p = self.root / INBOX / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(body)

    def proposal(self, rows, text="AI 读到的题面", extra=None):
        """造一份 AI 的机读提案（`reports/INTAKE.json`）。"""
        d = {"schema_version": 1,
             "problem": {"file": INBOX + "/题目.pdf", "text": text, "chars": len(text),
                         "pages": 2, "subquestions": ["问题一"], "uncertain": []},
             "files": rows, "notes": []}
        if extra:
            d.update(extra)
        (self.root / "reports").mkdir(parents=True, exist_ok=True)
        (self.root / "reports/INTAKE.json").write_text(
            json.dumps(d, ensure_ascii=False), encoding="utf-8")
        # **只写机读的提案**：人读的那份报告是 agent 写的（夹具 runner 已经写过）。
        #   这里若再补一个报告存根，会把 runner 那份**覆盖**掉 ⇒ `_artifact_ok`（卡 80 字节）
        #   判假 ⇒ 读题阶段被当成"执行失败" ⇒ 整链挂起，而日志只说"阶段未成功完成：failed"。
        return d

    def rows_for(self, *rels):
        return [{"path": f"{INBOX}/{r}", "role": "attachment",
                 "target": f"request/attachments/{r}", "why": "夹具"} for r in rels]

    def confirm(self, rows, problem_text="人确认过的题面", corrections="", note="", ai_rows=None,
                ai_text=None):
        """真流程是「链停下来亮灯 → 人在灯上点确认」—— 所以这里先把那盏灯点起来。

        AI 的提案必须在**链跑起来之后**才写进 `reports/`：第一轮 `_prepare_workspace`
          会把 `reports/` 整份轮转进 cache（发现②）—— 先写后跑的话，提案会被搬走，
          确认时看到的是「缺 reports/INTAKE.json」。所以这里用 runner 的 `after` 钩子写它，
          与真实 agent 的行为一致（agent 是在阶段里写报告的）。
        `ai_text`：AI 在 `problem.text` 里给的题面正文。**必须从这里传**，不能先自己
          `self.proposal(...)` 再调 `confirm` —— 下面这个 `after` 钩子会把 `INTAKE.json`
          **整份重写**，先前写的那份连同它的 text 一起被顶掉，测出来的"回退"结果会是钩子
          写的默认文本：看着像产品有 bug，其实是夹具。
        """
        if not self.s.state.get("pending"):
            def after(sid):
                if sid == "intake":
                    self.proposal(ai_rows if ai_rows is not None else rows,
                                  text=("AI 读到的题面" if ai_text is None else ai_text))
            self.install_successful_runner(after=after)
            asyncio.run(self.s.run_all())
            assert (self.s.state.get("pending") or {}).get("kind") == "intake", \
                f"没亮读题灯，不能确认：{self.s.state.get('halt_reason')}"
        req = self.s.DecisionReq(action="confirm", roles=rows, problem_text=problem_text,
                                 corrections=corrections, note=note)
        return asyncio.run(self.s._apply_decision(req))

    # ---- 1. 没确认就把链停在 ⓪ ----

    def test_an_unconfirmed_upload_stops_the_chain_at_intake(self):
        """有未确认的原件 ⇒ 跑完 ⓪ 必须停下等人核对；没有确认就不许往下跑。"""
        self.inbox("题目.pdf", "附件1.xlsx")
        calls = self.install_successful_runner()
        asyncio.run(self.s.run_all())
        self.assertEqual(calls, ["intake"], f"应当只跑 ⓪ 就停：{calls}")
        self.assertEqual(self.s.state["stages"]["intake"], "awaiting_user")
        self.assertTrue(self.s.state["halt_gate"])
        self.assertEqual((self.s.state.get("pending") or {}).get("kind"), "intake")

    def test_without_an_inbox_the_chain_does_not_stop_for_confirmation(self):
        """对照组：没有 inbox ⇒ **不亮读题灯**、链一路跑完。

        ⓪ 本身还是会跑一次（它就是链上的一个阶段）—— 这条钉的是"不会停下来等人"，
        以及"跑完不会留下任何待确认状态"。既有的全链回归靠的就是这条。
        """
        calls = self.install_successful_runner()
        asyncio.run(self.s.run_all())
        self.assertTrue(self.s.state["run_completed"], self.s.state["halt_reason"])
        self.assertFalse(self.s.state["halt_gate"], "没有待确认原件却亮灯了")
        self.assertIsNone(self.s.state.get("pending"))
        self.assertTrue(str(self.s.state["stages"].get("intake", "")).startswith("done"),
                        f"⓪ 应当照常跑完并标 done：{self.s.state['stages'].get('intake')}")
        self.assertIn("intake", calls)

    # ---- 2. 这盏灯的出路只有「确认 / 重读」 ----

    def test_the_intake_light_only_offers_confirm_and_retry(self):
        """不给 rollback（链首、点了必然 400）、不给 disclose（会写"已知残余"污染审计）、
        不给 attest（会绕过"还没确认"这件事）。"""
        self.inbox("题目.pdf")
        self.install_successful_runner()
        asyncio.run(self.s.run_all())
        acts = (self.s.state.get("pending") or {}).get("actions") or []
        self.assertIn("confirm", acts)
        self.assertIn("retry", acts)
        for bad in ("rollback", "disclose", "attest"):
            self.assertNotIn(bad, acts, f"读题这盏灯不该给 {bad}")
        # 对照组：**别的阶段**的普通失败黄灯仍然给 rollback —— 证明上面那条不是恒真
        p = self.s._build_pending(self.stage("literature"), "failure", "failed", "随便失败一下")
        self.assertIn("rollback", p["actions"])

    # ---- 3. 确认按"人改过的表"落盘 ----

    def test_confirm_materializes_where_the_table_says(self):
        """落点必须照**确认页那张表**，不是 AI 的原提案。"""
        self.inbox("题目.pdf", "附件3/result1.xlsx", "垃圾.zip")
        # AI 的提案与人的改法**必须分开传**：`ai_rows` 是提案（写进 INTAKE.json），
        #   `rows` 是人在确认页上改过的那张表。若把提案先写进 `reports/`，第一轮轮转会把它
        #   搬走 ⇒ 确认时读到的是"人自己那张表"，于是人工改动一条都记不出来。
        ai_rows = self.rows_for("题目.pdf") + [
            {"path": INBOX + "/附件3/result1.xlsx", "role": "data",
             "target": "data/附件3/result1.xlsx", "why": "AI 说是数据集"},
            {"path": INBOX + "/垃圾.zip", "role": "needs_manual", "target": "", "why": "压缩包"},
        ]
        rows = [
            {"path": INBOX + "/题目.pdf", "role": "problem", "target": "request/attachments/题目.pdf"},
            # 故意把 AI 判的 data 改回 attachment —— 落点必须跟着**人**的改法走
            {"path": INBOX + "/附件3/result1.xlsx", "role": "attachment",
             "target": "request/attachments/附件3/result1.xlsx"},
            {"path": INBOX + "/垃圾.zip", "role": "ignore", "target": ""},
        ]
        out = self.confirm(rows, problem_text="人确认过的题面\n第二行", ai_rows=ai_rows)
        self.assertEqual(out["resume_index"], self.s.STAGE_IDX["literature"])
        self.assertTrue(out["resumed"])
        self.assertTrue((self.root / "request/attachments/附件3/result1.xlsx").is_file(),
                        "没有按人改后的目标落盘（子目录结构也没保住）")
        self.assertFalse((self.root / "data/附件3/result1.xlsx").exists(),
                         "照 AI 的原提案落了盘 —— 应当以人的改法为准")
        self.assertEqual((self.root / "request/problem.md").read_text(encoding="utf-8"),
                         "人确认过的题面\n第二行")
        self.assertFalse((self.root / INBOX).exists(), "确认之后 _inbox 应当被清掉")
        conf = json.loads((self.root / "runtime/quality/intake/confirmed.json").read_text(encoding="utf-8"))
        self.assertTrue(any("result1" in h for h in conf["human_edits"]),
                        f"人工改动没进审计痕：{conf['human_edits']}")

    def test_confirm_writes_the_problem_even_when_the_panel_sends_nothing(self):
        """哨兵：机械读题拆掉之后，`request/problem.md` 只剩**确认这一步**一个写点。

        只靠 `_materialize_inbox` 里那句 `if problem_text is not None:` 会漏：面板没回传
        （人没动过那个框、或走的是 CLI/接口）时就一个字都不写，
        而 `content_quality._evidence()` 硬判 `source.file` 必须在 `request/` 下并
        **逐字读它** ⇒ ①–⑯ 全部失去题意锚点，而且此处不报错 —— 要等门禁以
        "找不到题面原文"的形式炸，那时已经烧掉几十分钟。
        """
        self.inbox("题目.pdf")
        out = self.confirm(self.rows_for("题目.pdf"), problem_text=None,
                           ai_text="AI 读到的题面正文\n第二行")
        self.assertEqual(out["resume_index"], self.s.STAGE_IDX["literature"])
        self.assertEqual((self.root / "request/problem.md").read_text(encoding="utf-8"),
                         "AI 读到的题面正文\n第二行",
                         "面板没回传题面时没有回退到 AI 的那份 ⇒ request/problem.md 会缺席")

    def test_confirm_refuses_when_neither_side_has_a_problem_text(self):
        """对照组：**人没给、AI 也没给** ⇒ 必须 400，且**一件原件都不许动**。

        没有它，上面那条可能只是"反正总会写点什么"。而空题面比没题面更坏：它会一路带到
        ①–⑯，`content_quality` 的"题面里有原文"核查看上去**跑过了**。
        "一件都不许动"是 `_materialize_inbox` 自己的承诺（全成或全不动）——
        所以题面的空判必须在**搬运之前**做。
        """
        self.inbox("题目.pdf")
        with self.assertRaises(self.s.HTTPException):
            self.confirm(self.rows_for("题目.pdf"), problem_text=None, ai_text="")
        self.assertFalse((self.root / "request/problem.md").exists(), "拒了确认却还是落了题面")
        self.assertTrue((self.root / INBOX / "题目.pdf").is_file(),
                        "拒了确认却把原件搬走了 —— 违反了「全成或全不动」")

    def test_a_target_outside_the_workspace_is_rejected_and_nothing_moves(self):
        """目标是 `../x` 这种 ⇒ 400，且**一件都不许动**。"""
        self.inbox("题目.pdf", "附件1.xlsx")
        self.proposal(self.rows_for("题目.pdf", "附件1.xlsx"))
        before = sorted(p.relative_to(self.root).as_posix()
                        for p in (self.root / INBOX).rglob("*") if p.is_file())
        with self.assertRaises(self.s.HTTPException):
            self.confirm([{"path": INBOX + "/题目.pdf", "role": "attachment",
                           "target": "request/../../evil.txt"},
                          {"path": INBOX + "/附件1.xlsx", "role": "attachment",
                           "target": "request/attachments/附件1.xlsx"}])
        self.assertFalse((self.root / "evil.txt").exists())
        after = sorted(p.relative_to(self.root).as_posix()
                       for p in (self.root / INBOX).rglob("*") if p.is_file())
        self.assertEqual(after, before, "校验失败时不该动任何一件")
        self.assertFalse((self.root / "request/attachments/附件1.xlsx").exists(),
                         "半路落盘了 —— 必须「全成或全不动」")

    # ---- 4. 确认过就不重跑（省钱的那条） ----

    def test_a_confirmed_intake_is_not_re_run(self):
        """已确认且输入没变 ⇒ 不重跑 AI；产物还能从快照恢复回来（发现②）。"""
        self.inbox("题目.pdf")
        self.proposal(self.rows_for("题目.pdf"))
        self.confirm([{"path": INBOX + "/题目.pdf", "role": "problem",
                       "target": "request/attachments/题目.pdf"}])
        # 模拟"轮转把 reports/ 扫走了"
        (self.root / "reports/INTAKE.json").unlink()
        (self.root / "reports/INTAKE_REPORT.md").unlink()
        calls = self.install_successful_runner()
        asyncio.run(self.s.run_all())
        self.assertNotIn("intake", calls, f"确认过了还重跑 AI：{calls}")
        self.assertTrue((self.root / "reports/INTAKE_REPORT.md").is_file(),
                        "读题产物没从 runtime/quality/intake/ 恢复回来")

    def test_reuploading_invalidates_the_earlier_confirmation(self):
        """换一批原件 ⇒ 旧的确认自动失效、必须重新确认（与 `_waived` 同一套语义）。"""
        self.inbox("题目.pdf")
        self.proposal(self.rows_for("题目.pdf"))
        self.confirm([{"path": INBOX + "/题目.pdf", "role": "problem",
                       "target": "request/attachments/题目.pdf"}])
        self.assertFalse(self.s._intake_unconfirmed(), "刚确认完就不该再要求确认")
        self.inbox("题目.pdf", "新的附件.xlsx", body="不一样的内容".encode("utf-8"))
        self.assertTrue(self.s._intake_unconfirmed(), "换了输入还认为已确认 —— 会拿旧读法开跑")

    # ---- 4b. 确认之后不许整链重跑 ----

    def test_confirming_does_not_make_the_next_run_redo_everything(self):
        """确认之后**再点一次「开始全链」不许整链重跑**。

        病因链：确认那一步把 `reports/` 整份轮转进 cache ⇒ `reports/INTAKE_REPORT.md` 在
        「从 ① 起跑」的那一轮里是**缺席**的，而它在 ①–⑯ 每个阶段的输入清单里（前序报告全收）
        ⇒ 回执记的是"这个文件不存在"；下一轮 intake 短路把它恢复回来 ⇒ 文件**从无到有**
        ⇒ ①–⑯ 的输入指纹全变 ⇒ 整链真重跑（15 个阶段，含小时级的 ④⑥）。
        所以 `run_all` 要"每轮都恢复"（在轮转之后、任何阶段之前），让它**恒在盘上**、指纹恒定。
        """
        self.inbox("题目.pdf")
        self.confirm([{"path": INBOX + "/题目.pdf", "role": "problem",
                       "target": "request/attachments/题目.pdf"}])
        first = self.install_successful_runner()
        asyncio.run(self.s.run_all())
        self.assertTrue(self.s.state["run_completed"], self.s.state["halt_reason"])
        self.assertIn("literature", first)
        second = self.install_successful_runner()
        asyncio.run(self.s.run_all())
        self.assertEqual(second, [],
                         f"确认之后又整链重跑了一遍（前几个：{second[:5]}）—— "
                         f"读题报告在盘上时有时无，把 ①–⑯ 的输入指纹全抖了一遍")

    def test_the_reading_report_is_on_disk_in_every_run_after_confirmation(self):
        """上一条的**直接判据**：确认之后，每一轮开跑时那份报告都得在盘上（否则指纹抖）。

        只看一条：轮转之后的恢复有没有跑。少了它，①–⑯ 会记下"文件不存在"。
        """
        self.inbox("题目.pdf")
        self.confirm([{"path": INBOX + "/题目.pdf", "role": "problem",
                       "target": "request/attachments/题目.pdf"}])
        # （注意：确认那一刻 `reports/` 还在 —— 轮转发生在**下一次开跑**的开头。）
        first = self.install_successful_runner()
        asyncio.run(self.s.run_all())
        self.assertIn("literature", first)
        self.assertTrue((self.root / "reports/INTAKE_REPORT.md").is_file(),
                        "开跑后报告没被恢复到 reports/ —— 各阶段会把它记成「不存在」")

    def test_the_reading_report_is_part_of_the_downstream_input_digest(self):
        """机制判据：读题报告**确实在** ①–⑯ 的输入指纹里 —— 这才是上面那条的"为什么"。

        没有这条，上面两条只是"断言某函数被调过"，看不出真正在防什么：把恢复整个关掉，
        第二轮仍然空 —— 因为两轮都缺席、指纹恒定，压根不抖。
        真正会抖的情形是"一轮缺席、下一轮被恢复回来"，而这条钉住了"缺席与在场就是两个指纹"。
        """
        st = self.stage("literature")
        before = self.s._input_digest(st)
        (self.root / "reports").mkdir(parents=True, exist_ok=True)
        (self.root / "reports/INTAKE_REPORT.md").write_text("读题报告", encoding="utf-8")
        self.assertNotEqual(self.s._input_digest(st), before,
                            "读题报告不在后续阶段的输入指纹里 —— 那这条链路的前提就变了")

    # ---- 5. 发现 A 的哨兵 ----

    def test_writing_into_request_during_a_stage_is_unverified(self):
        """**发现 A 的哨兵**：阶段执行期间改 `request/` 会被判 unverified（硬挂）。

        这条钉的是"将来有人顺手让 agent 去搬文件"这种改法 —— 它当场变红，
        而不是等到线上出现一次"查不出原因的挂起"。
        """
        st = self.stage("literature")
        (self.root / "reports").mkdir(parents=True, exist_ok=True)

        async def runner(prompt, sid, cap=None):
            (self.root / "request").mkdir(parents=True, exist_ok=True)
            (self.root / "request/偷改的.txt").write_text("x", encoding="utf-8")  # ← 违规动作
            rp = self.s.REPORTS / st["report"]
            rp.parent.mkdir(parents=True, exist_ok=True)
            rp.write_text("最终结论：PASS\n" + "evidence " * 30, encoding="utf-8")
            return 0, "", False

        self.s._call = runner
        out = asyncio.run(self.s.run_stage(st))
        self.assertEqual(out, "unverified",
                         "阶段执行期间改 request/ 竟然没被判 unverified —— 发现 A 的防线没了")

    # ---- 端点级：`kind=folder` ----

    def test_the_upload_endpoint_keeps_the_folder_structure(self):
        """端点级：`files` + `paths` 成对提交时必须**保住子目录**，并自动起链读题。

        浏览器只把基名放进 `File.name`，相对路径在 `webkitRelativePath` 里且**不会自动进
        multipart** ⇒ 后端能不能保住结构，全看这条契约对不对得上。
        """
        from fastapi.testclient import TestClient
        started = []
        self.s._start_chain = lambda: started.append(1)      # 别真起线程（那是后台跑链）
        self.install_successful_runner()
        client = TestClient(self.s.app)
        files = [("files", ("题目.pdf", b"%PDF-1.4 x", "application/pdf")),
                 ("files", ("result1.xlsx", b"xlsx", "application/octet-stream"))]
        # data 用 dict + **list 值**表示重复字段（httpx 的写法；传元组列表会被当普通字段 ⇒ 422）
        r = client.post("/api/upload", files=files,
                        data={"kind": "folder", "paths": ["题目.pdf", "附件3/result1.xlsx"]})
        self.assertEqual(r.status_code, 200, r.text)
        got = sorted(p.relative_to(self.root).as_posix()
                     for p in (self.root / INBOX).rglob("*") if p.is_file())
        self.assertEqual(got, sorted([INBOX + "/题目.pdf", INBOX + "/附件3/result1.xlsx"]),
                         f"目录结构没保住：{got}")
        self.assertTrue(started, "上传完没有自动起链读题")

    def test_the_upload_endpoint_rejects_mismatched_paths(self):
        """`paths` 与 `files` 条数对不上 ⇒ 400 且说清怎么办（不许猜着配对）。"""
        from fastapi.testclient import TestClient
        client = TestClient(self.s.app)
        r = client.post("/api/upload",
                        files=[("files", ("a.txt", b"x", "text/plain"))],
                        data={"kind": "folder", "paths": ["a.txt", "b.txt"]})
        self.assertEqual(r.status_code, 400)
        self.assertIn("对不上", r.json()["detail"])

    # ---- 确认表的校验 ----

    def test_a_target_inside_the_inbox_is_rejected(self):
        """目标不能还在 `_inbox` 里：确认的最后一步会把 `_inbox` 整个删掉 ⇒ 原件静默消失。

        （AI 的提案里 `problem.file` 正是 `request/_inbox/…` 这个形状，写串了会被原样预填。）
        """
        self.inbox("题目.pdf")
        with self.assertRaises(self.s.HTTPException) as cm:
            self.confirm([{"path": INBOX + "/题目.pdf", "role": "attachment",
                           "target": INBOX + "/题目.pdf"}])
        self.assertIn("_inbox", str(cm.exception.detail))

    def test_two_rows_pointing_at_one_target_are_rejected(self):
        """两行指向同一个落点 ⇒ 会互相覆盖（后写的盖前写的），必须拦在落盘之前。"""
        self.inbox("附件3/result1.xlsx", "附件4/result1.xlsx")
        with self.assertRaises(self.s.HTTPException) as cm:
            self.confirm([
                {"path": INBOX + "/附件3/result1.xlsx", "role": "attachment",
                 "target": "request/attachments/result1.xlsx"},
                {"path": INBOX + "/附件4/result1.xlsx", "role": "attachment",
                 "target": "request/attachments/result1.xlsx"}])
        self.assertIn("同一个落点", str(cm.exception.detail))

    def test_two_same_named_attachments_get_distinct_targets_by_default(self):
        """两处同名附件**默认不该被串成同一个目标**。

        若配对只看基名（后写顶前写），两行会渲染成同一个 target —— 照默认直接确认就丢文件。
        """
        self.inbox("附件3/result1.xlsx", "附件4/result1.xlsx")
        # 提案必须在**链跑起来之后**写（第一轮轮转会搬走 reports/）：用 runner 的 after
        #   钩子，跟真 agent 一样。
        rows = [
            {"path": INBOX + "/附件3/result1.xlsx", "role": "attachment",
             "target": "request/attachments/附件3/result1.xlsx", "why": "附件3 的模板"},
            {"path": INBOX + "/附件4/result1.xlsx", "role": "attachment",
             "target": "request/attachments/附件4/result1.xlsx", "why": "附件4 的模板"}]
        self.install_successful_runner(
            after=lambda sid: sid == "intake" and self.proposal(rows))
        asyncio.run(self.s.run_all())                      # 亮灯
        rows = self.s._intake_panel_fields()["files"]
        targets = [r["target"] for r in rows]
        self.assertEqual(len(set(targets)), len(targets), f"两行目标撞了：{targets}")
        whys = [r["why"] for r in rows]
        self.assertTrue(all("附件3" in w or "附件4" in w for w in whys),
                        f"理由串味了（基名配对顶掉了）：{whys}")

    def test_the_corrections_note_reaches_the_literature_hint(self):
        """确认页填的「更正说明」必须真的传给 ① —— 键名写错就等于这个功能是死的。

        （若 `_record_confirmation` 写的是 `note`、而 `_intake_hint` 读的是 `corrections`，
        人填的更正就进不了 ①。）
        """
        self.inbox("题目.pdf")
        self.confirm([{"path": INBOX + "/题目.pdf", "role": "problem",
                       "target": "request/attachments/题目.pdf"}],
                     corrections="第 3 问的单位是万元，不是元")
        hint = self.s.state.get("seed_hints", {}).get("literature", "")
        self.assertIn("第 3 问的单位是万元", hint, f"更正说明没进 ① 的提示：{hint[:200]}")

    # ---- 前端一致性哨兵 ----

    def test_every_action_the_driver_can_emit_has_a_button(self):
        """哨兵：服务端 `_action_set` 能给出的每个动作，前端都得有对应按钮。

        为什么值得单开一条：整套后端都写好了、测试也全绿，前端只要少加一个 `#dc_confirm`
        按钮，读题的黄灯上就只剩「再试一次」，这个功能在真机上根本走不到"确认"那一步
        （点「开始全链」还会被 409 拦回来，提示让人去点一个不存在的按钮）。纯前端缺失，
        服务端测试**看不见**。
        """
        html = (PROJECT / "lib/web/static/index.html").read_text(encoding="utf-8")
        buttons = set(re.findall(r'id="dc_([a-z_]+)"', html))
        # `_action_set` 可能吐出的动作名（按它自己的分支列出来）
        for action in ("retry", "extend", "rollback", "disclose", "attest", "confirm"):
            self.assertIn(action, buttons,
                          f"服务端会给「{action}」，而 index.html 里没有 id=\"dc_{action}\" 的按钮")
        # 反向：每个按钮都得有 onclick 绑上（别加了按钮忘了接线）
        for b in ("confirm", "retry", "disclose", "attest"):
            self.assertIn(f"$('dc_{b}').onclick", html, f"dc_{b} 按钮没接 onclick")

    def test_the_upload_entry_keeps_its_one_required_attribute(self):
        """上传入口是"一个拖放区 + 一个确认"，其中唯一**不能**丢的是 `webkitdirectory`。

        为什么单钉它：没有这个属性，`<input multiple>` 照样能选、照样能传，只是
        每份文件的 `webkitRelativePath` 变成空 ⇒ 后端把子目录**拍平**，而本题的
        `附件3/` 就是子目录。整条链不会报任何错，只是附件从此找不到 —— 静默、且事后无法追。
        """
        html = (PROJECT / "lib/web/static/index.html").read_text(encoding="utf-8")
        m = re.search(r'<input[^>]*id="up_folder"[^>]*>', html)
        self.assertIsNotNone(m, "找不到 #up_folder（选文件夹的入口没了？）")
        self.assertIn("webkitdirectory", m.group(0),
                      "#up_folder 丢了 webkitdirectory ⇒ 子目录会被静默拍平")

    def test_no_dangling_up_ui_reference(self):
        """哨兵：JS 里 `$('up_…')` 引用的每个 id，markup 里都得有。

        删 markup 却漏删 JS 只是 `null.onclick = …` 当场抛错；反过来（改了 id 忘了改引用）
        会静默变成"按钮点了没反应"。这两种手滑在删元素时最容易发生（零散文件那一行、
        `up_go_files`、`up_go_folder` 都撤过）。纯前端，服务端测试看不见。
        """
        html = (PROJECT / "lib/web/static/index.html").read_text(encoding="utf-8")
        ids = set(re.findall(r'id="([^"]+)"', html))
        used = set(re.findall(r"\$\('(up_[a-z_]+)'\)", html))
        self.assertTrue(used, "一个 up_* 引用都没找到 —— 正则或界面结构变了，这条就白钉了")
        self.assertEqual(sorted(used - ids), [], "JS 引用了 markup 里不存在的 id")

    def test_upload_is_staged_then_confirmed(self):
        """拖放与选文件夹都只**暂存**，真正发出去只在 `#up_go` 那一下。

        为什么钉这个：暂存 + 确认是为了两条入口行为一致，同时让人在**发出去之前能看见到底
        选到了什么**（选错文件夹要等传完才知道就晚了）。真正的判据是"`doUpload(` 只有一个
        调用点" —— 多一个就说明某条路又变成了立即上传。
        """
        html = (PROJECT / "lib/web/static/index.html").read_text(encoding="utf-8")
        self.assertIn('<button id="up_go" disabled', html, "确认按钮该是禁用的初始态")
        self.assertIn("$('up_go').disabled=false", html, "暂存之后要把确认按钮放开")
        self.assertIn("$('up_go').onclick", html, "确认按钮没接 onclick")
        self.assertIn("_stagePairs(await dropPairs(dt), name)", html, "拖放没有走暂存那条路")
        self.assertIn("doUpload(p.pairs, true, p.name)", html, "确认按钮没有真的发出上传")
        self.assertNotIn("await doUpload", html,
                         "还有入口在**立即上传**（拖放/选完就传）—— 应当只暂存，等确认")

    def test_the_problem_is_rendered_and_compared_against_the_original_pdf(self):
        """确认页的形状：读完生成**渲染后**的 md 让人检查，看看和原 pdf 是不是对的上；
        AI 读错了能自己改。

        钉四件事：
          · 题面走 `mdToHtml` **渲染**（不是把 markdown 原文摊在 textarea 里）；
          · 渲染的是 `#ik_text` 的**当前值**（所以改完切回来立刻能看到新渲染）；
          · 有「改文字」的开关；
          · 内嵌**原 PDF**，且走**复用**现成的 `/api/read`（不要为这个新开端点）。
        外加一条反向守卫：机械读题已拆掉，`ik_mech` 不许再出现。
        """
        html = (PROJECT / "lib/web/static/index.html").read_text(encoding="utf-8")
        self.assertIn('id="ik_view"', html, "没有渲染容器")
        self.assertIn('id="ik_edit"', html, "没有「✎ 改文字」开关")
        self.assertIn("mdToHtml(ta.value)", html, "题面没有走 mdToHtml 渲染")
        self.assertNotIn('id="ik_mech"', html, "机械对照栏应当已经拆掉")
        self.assertIn("/api/read?path=", html, "没有内嵌原 PDF（应当是复用 /api/read）")

    def test_the_confirm_button_is_shown_by_the_rendered_actions(self):
        """光有按钮不够：`renderDecision` 必须按 `acts.includes('confirm')` 显隐它。"""
        html = (PROJECT / "lib/web/static/index.html").read_text(encoding="utf-8")
        self.assertIn("acts.includes('confirm')", html,
                      "确认按钮没有跟着动作集显隐 ⇒ 别的黄灯上也会挂着一个点了必然 400 的按钮")

    # ---- 7. ⓪ 的绿 / 灰：它的「通过」不写回执 ----

    def confirmed_intake(self):
        """造一个「⓪ 已人工确认过」的盘面：读题报告在盘、题面已落盘、inbox 空。"""
        rep = self.root / "reports" / "INTAKE_REPORT.md"
        rep.parent.mkdir(parents=True, exist_ok=True)
        rep.write_text("# 读题报告\n" + "内容" * 60 + "\n", encoding="utf-8")
        prob = self.root / "request" / "problem.md"
        prob.parent.mkdir(parents=True, exist_ok=True)
        prob.write_text("题面正文\n", encoding="utf-8")
        shutil.rmtree(self.root / INBOX, ignore_errors=True)
        return rep, prob

    def test_a_confirmed_intake_turns_green_after_a_resume(self):
        """⓪ 过了之后面板上该是绿的，不该还停在灰色。

        ⓪ 的「通过」走的是**人工确认**那条路，而 `_do_intake_confirm`（`/api/decision` 的
        confirm 分支）只把题面/附件落盘、然后从 ① 起跑，**从来不写 ⓪ 的回执** ——
        `runtime/quality/stages.json` 里有 literature/analysis/review/code/audit/
        robustness/drawio/figreview 的条目，**唯独没有 `intake`**。
        ⇒ `_backfill_before` 那套"产物在盘 + 回执对得上"的判据对它**永远不成立**，
          于是确认完从 ① 起跑之后 ⓪ 就被画成灰色（见 `_intake_passed_without_receipt`）。

        判据 + 三条对照组（三条判据各缺一条都必须留灰）—— 对照组不是装饰：
        少了它们，一条恒真的 `return True` 也能让正题绿。
        """
        self.confirmed_intake()
        self.s.state["stages"]["intake"] = "idle"
        self.s._backfill_before(1)
        self.assertEqual(self.s.state["stages"]["intake"], "done(skip)",
                         "确认过的 ⓪ 被回填成灰的")

        # 对照①：读题报告不在盘上（`_artifact_ok` 那把尺）
        (self.root / "reports" / "INTAKE_REPORT.md").unlink()
        self.s.state["stages"]["intake"] = "idle"
        self.s._backfill_before(1)
        self.assertEqual(self.s.state["stages"]["intake"], "idle", "没有读题报告也画绿了")

        # 对照②：确认没落地（`_materialize_inbox` 无条件写的那份题面不在）
        _, prob = self.confirmed_intake()
        prob.unlink()
        self.s.state["stages"]["intake"] = "idle"
        self.s._backfill_before(1)
        self.assertEqual(self.s.state["stages"]["intake"], "idle", "确认没落地也画绿了")

        # 对照③：inbox 里还有等着人确认的原件
        self.confirmed_intake()
        self.inbox("题目.pdf")
        self.s.state["stages"]["intake"] = "idle"
        self.s._backfill_before(1)
        self.assertEqual(self.s.state["stages"]["intake"], "idle", "还有未确认原件也画绿了")

    # ---- 6. 顺序与编号 ----

    def test_adding_intake_renumbered_nothing(self):
        """⓪ 只许插在链首：①…⑯ 的 id **逐项不变**（重排编号会牵连全仓上千处引用）。"""
        ids = [s["id"] for s in self.s.STAGES]
        self.assertEqual(ids[0], "intake")
        self.assertEqual(ids[1:], [
            "literature", "analysis", "review", "code", "audit", "robustness", "drawio",
            "figreview", "write", "mathproof", "cross", "rubric", "fix", "format",
            "verify", "demo"])
        self.assertEqual(self.s.STAGE_IDX["literature"], 1)


if __name__ == "__main__":
    unittest.main()
