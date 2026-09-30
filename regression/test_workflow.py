"""Offline fault injection: never launch the model runner or competition code."""
import ast
import asyncio
import copy
import io
import json
import os
import sys
import tempfile
import time
import types
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, Mock

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "lib" / "web"))
from workflow_quality import read_verdict, fingerprint, StageReceipts


def load_server(root):
    # Run the real driver in an isolated workspace, replacing only bootstrap paths.
    # exist_ok：同一 root 上重复调用是**重启存活**类测试的必需手段（重新 exec
    # server.py 模拟进程重启）。没有它会 FileExistsError。
    (root / "lib/web/static").mkdir(parents=True, exist_ok=True)
    tree = ast.parse((PROJECT / "lib/web/server.py").read_text(encoding="utf-8-sig"))
    for node in tree.body:
        if isinstance(node, ast.Assign):
            names = [t.id for t in node.targets if isinstance(t, ast.Name)]
            if "ROOT" in names:
                node.value = ast.parse(f"Path({str(root)!r})", mode="eval").body
            if "CLAUDE" in names:
                node.value = ast.parse("Path('fake-runner')", mode="eval").body
    module = types.ModuleType("isolated_server")
    module.__file__ = str(PROJECT / "lib/web/server.py")
    exec(compile(ast.fix_missing_locations(tree), module.__file__, "exec"), module.__dict__)
    module._real_log = module.log      # 留着真身：测「写文件失败要留痕」得跑真的
    module.log = Mock()
    module.emit = Mock()
    module._real_collect_outputs = module._collect_outputs
    module._collect_outputs = Mock(return_value=True)
    return module


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.s = load_server(self.root)

    def report(self, stage, text):
        path = self.s.REPORTS / stage["report"]
        path.write_text(text + "\n" + "evidence " * 30, encoding="utf-8")

    def stage(self, sid):
        return next(x for x in self.s.STAGES if x["id"] == sid)

    def expected_full_chain(self):
        """干净通过一轮里**实际会被调用**的阶段顺序。

        少了 `fix` 不是漏跑，是设计行为：`12Rubric-final` 明确 PASS 且没有 must/fatal
        判词时，没有东西要它处置，驱动跳过它省一次 agent 调用。要它跑，得先让 rubric
        判出东西来 —— 见 `test_rubric_paper_side_verdict_runs_fix_then_rechecks`。
        """
        return [s["id"] for s in self.s.STAGES if s["id"] != "fix"]

    def test_unknown_verdict_is_not_pass(self):
        st = self.stage("review")
        self.report(st, "尚未完成审核，不能下结论。")
        self.assertNotEqual(self.s.gate_result(st), "ok")

    def test_old_analysis_approval_cannot_override_new_review(self):
        (self.s.REPORTS / "ANALYSIS_MODELING_REPORT.md").write_text("评审结论：APPROVED", encoding="utf-8")
        st = self.stage("review")
        self.report(st, "整题门禁裁决：REVISE")
        self.assertNotEqual(self.s.gate_result(st), "ok")

    def test_nonzero_exit_with_report_is_execution_failure(self):
        st = self.stage("literature")
        async def failed(*args, **kwargs):
            self.report(st, "partial result")
            return 1, "runner failed", False
        self.s._call = failed
        self.assertNotEqual(asyncio.run(self.s.run_stage(st)), "ok")

    def test_stage_agent_is_allowed_to_wait_for_its_subagents(self):
        """门禁阶段必须能等自己的子 agent —— 不能被 CLI 的 600s 上限掐死。

        3Modeling-review-gate / 10Math-proof-gate / 11Cross-question-check / 12Rubric-final 的 SKILL 都要求「并行 spawn N 个
        独立子 agent」；Agent 工具默认后台运行，主 agent 的回合就结束在"等子 agent"处。
        `claude -p` 默认只等 600s，到点打印「Background tasks still running after 600s;
        terminating.」并**结束整个会话** —— 子 agent 被杀、报告从未写出，而进程 rc=0，
        于是只留下 `执行第 1 次失败 rc=0 stalled=False artifact=False` 这个查不出原因的哑谜：
        报告缺失被记成"阶段失败"，真因却在 CLI 的等待上限上。
        """
        captured = {}
        class FakePopen:
            def __init__(self, cmd, **kw):
                captured.update(kw.get("env") or {})
                self.pid, self.returncode = 424242, 0
                self.stdout = io.BytesIO(b"")
            def wait(self):
                return self.returncode
        real = self.s.subprocess.Popen
        self.s.subprocess.Popen = FakePopen
        self.addCleanup(setattr, self.s.subprocess, "Popen", real)
        sh = {"pid": None, "lines": [], "sid": "review", "last_out": 0.0, "tail": ""}
        # 出站代理那条既有行为不能被这条改动顶掉：**API 主机**要被摘出代理（Clash 开/关都能连上）。
        # 主机是**从 `ANTHROPIC_BASE_URL` 推**出来的，不是写死的厂商域名 —— 所以这里显式设一个
        #   测试端点（见 test_proxy.py：换端点必须跟着换，硬编码 deepseek 会在换端点时静默失效）。
        old = os.environ.get("ANTHROPIC_BASE_URL")
        os.environ["ANTHROPIC_BASE_URL"] = "https://api.example-endpoint.test/anthropic"
        self.addCleanup(lambda: os.environ.__setitem__("ANTHROPIC_BASE_URL", old) if old is not None
                        else os.environ.pop("ANTHROPIC_BASE_URL", None))
        self.s._claude_worker(["claude", "-p", "x"], sh)
        self.assertEqual(captured.get("CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS"), "0",
                         "未关掉 CLI 的后台等待上限：等子 agent 的阶段会被 600s 静默掐死")
        self.assertIn("api.example-endpoint.test", captured.get("NO_PROXY", ""))

    def assert_gate_rejected_without_delivering(self, sid, expect_in_reason):
        """门禁判否 ⇒ **不打包**，而且必须是**门禁**拦下的（不是驱动自己崩了）。

        这一条要**显式钉住"是门禁否的"**：驱动异常 / 没挂起 / 没转黄灯，都算红。
        为什么不能只断言"没打包"：那是个**恒真**的弱判据 —— 链若在门禁评估之前就崩掉
        （例如 `_input_paths` 里那句 `next(... for s if s["id"] == "code")` 抛
        `StopIteration`），`_collect_outputs` 同样没被调过，用例照样绿，而挂起文案
        只剩下「驱动异常：」四个字，看不出所以然。对应的两处支撑是 `_stage_index`
        不抛异常、`_driver_exc_text` 带类型名。
        """
        self.assertEqual(self.s.state["stages"].get(sid), "awaiting_user",
                         f"{sid} 该停在黄灯等人工决策")
        self.assertTrue(self.s.state["halt_gate"], "门禁判否必须转黄灯")
        why = str(self.s.state.get("halt_reason") or "")
        self.assertNotIn("驱动异常", why, f"这是**驱动崩了**，不是门禁判否：{why}")
        self.assertIn(expect_in_reason, why, f"挂起原因不对：{why}")
        self.s._collect_outputs.assert_not_called()
        self.assertFalse(self.s.state["run_completed"], "门禁没过不许报本轮完成")

    def test_cross_failure_never_collects(self):
        self.s.STAGES = [copy.deepcopy(self.stage("cross"))]
        async def failed(stage, **kwargs):
            self.report(stage, "整题 FAIL")
            return "ok"
        self.s.run_stage = failed
        asyncio.run(self.s.run_all())
        self.assert_gate_rejected_without_delivering("cross", "门禁未通过")

    def test_final_verify_failure_never_collects(self):
        self.s.STAGES = [copy.deepcopy(self.stage("verify"))]
        async def failed(stage, **kwargs):
            self.report(stage, "最终结论：FAIL")
            return "ok"
        self.s.run_stage = failed
        asyncio.run(self.s.run_all())
        self.assert_gate_rejected_without_delivering("verify", "门禁未通过")

    def test_missing_gate_report_never_collects(self):
        self.s.STAGES = [copy.deepcopy(self.stage("review"))]
        self.s.run_stage = AsyncMock(return_value="ok")
        asyncio.run(self.s.run_all())
        self.assert_gate_rejected_without_delivering("review", "未获得当前版本的明确有效裁决")

    def test_a_passing_gate_still_mirrors_and_packages(self):
        """对照组：上面三条钉的是"判否不打包"，别顺手把**通过**的门禁也掐掉。

        阶段性打包（⑨ 之后每完成一个阶段就移一次）正是靠这一段：镜像 + 打包发生在
        「裁决已处置完、链继续往前走」之后，收益是判否那一版不再进展示区 / 提交包，
        **风险**是通过的门禁也一起漏掉 —— 这条钉住它。
        """
        self.s.STAGES = [copy.deepcopy(self.stage("cross"))]
        async def passed(stage, **kwargs):
            self.report(stage, "整题 PASS：三问口径一致，通过。")
            return "ok"
        self.s.run_stage = passed
        snaps = []
        self.s._snapshot_stage = lambda st, fig_before=None: snaps.append(st["id"])
        asyncio.run(self.s.run_all())
        self.assertEqual(snaps, ["cross"], "通过的门禁必须照旧镜像进「各阶段产物」")
        self.assertTrue(self.s._collect_outputs.called, "通过的门禁必须照旧阶段性打包")
        self.assertTrue(self.s.state["run_completed"], self.s.state.get("halt_reason"))

    def install_successful_runner(self, failures=None, after=None):
        calls = []
        failures = failures or {}
        async def runner(prompt, sid, cap=None):
            calls.append(sid)
            st = self.stage(sid)
            status = "PASS"
            if failures.get(sid, 0):
                failures[sid] -= 1
                status = "FAIL"
            if sid == "write":
                (self.root / "paper").mkdir(exist_ok=True)
                (self.root / "paper/main.pdf").write_bytes(b"%PDF-1.4\n" + b"test fixture " * 20)
            else:
                self.report(st, "最终结论：" + status)
            if sid == "code":
                (self.root / "code").mkdir(exist_ok=True)
                (self.root / "code/example.txt").write_text("generic fixture")
            if st.get("gate"):
                sidecar = (self.s.REPORTS / st["report"]).with_suffix(".verdict.json")
                sidecar.write_text(json.dumps({"schema_version": 1, "stage": sid,
                    "input_digest": self.s._input_digest(st), "status": status, "issues": []}), encoding="utf-8")
            if after:
                after(sid)
            return 0, "", False
        self.s._call = runner
        return calls

    def test_full_pipeline_success_then_resume_without_model_calls(self):
        calls = self.install_successful_runner()
        asyncio.run(self.s.run_all())
        self.assertTrue(self.s.state["run_completed"], self.s.state["halt_reason"])
        self.assertEqual(calls, self.expected_full_chain())
        # 口径是**⑨ 及之后每完成一个阶段就同步一次**，不是"只在链尾收一次"：⑨ 结束后先把
        #   **目前能移入的**移入，其余的**等它们各自的阶段完成再移入**；若后续阶段又改动了
        #   产物，就移入后**把之前的产物替代**。
        #   干净跑通一轮 = ⑨→⑯ 里**真跑过的**每个阶段各一次（⑬ 走的是“无事可做就跳过”那条 `continue` 路，不经过钩子）
        #   加链尾那次：write, mathproof, cross, rubric, format, verify, demo = 7，再加链尾 = **8**
        self.assertEqual(self.s._collect_outputs.call_count, 8,
                         "⑨ 起每个完成阶段各收一次 + 链尾一次；改挂钩点必须同步这条")
        calls.clear()
        asyncio.run(self.s.run_all())
        self.assertEqual(calls, [])
        self.assertTrue(self.s.state["run_completed"])

    # ---------------- 「从所选阶段重跑」= 真的从那里起跑 ----------------
    # 起点必须真的落在所选阶段：若 `run_all` 起点恒为 0，
    # "从 ⑨ 重跑"就变成"从 ① 走一遍、靠回执跳过" —— 而上游**门禁**若是裁决过期，
    # `run_all` 会当场把它真跑一遍（`if verdict == "UNVERIFIED"` 那段），于是链卡在 ⑤。
    def test_start_from_stage_skips_an_upstream_gate_with_a_stale_verdict(self):
        calls = self.install_successful_runner()
        asyncio.run(self.s.run_all())                    # 第一轮跑通 ⇒ ①–⑧ 都有回执
        self.assertTrue(self.s.state["run_completed"], self.s.state["halt_reason"])
        calls.clear()
        # 把 ⑤ 结果可信度审计 的裁决改"过期"：起点若从 ① 走，这一发就会把链拦下来
        aud = self.stage("audit")
        (self.s.REPORTS / aud["report"]).with_suffix(".verdict.json").write_text(
            json.dumps({"schema_version": 1, "stage": "audit", "input_digest": "deadbeef",
                        "status": "PASS", "issues": []}), encoding="utf-8")
        self.s._redo_from("write")      # 与「↺ 从所选阶段重跑」同一条路：⑨ 及之后清空
        self.s._set_start_from("write")
        asyncio.run(self.s.run_all())
        self.assertNotIn("audit", calls, "从 ⑨ 起跑 => 上游 ⑤ 一次都不许被调起来")
        self.assertNotIn("review", calls)
        self.assertEqual(calls[0], "write")
        self.assertTrue(self.s.state["run_completed"], self.s.state["halt_reason"])
        # 上游被**如实回填**（不是画成"这一轮跑过"）：③ 没被动过 ⇒ 回填成复用。
        # ⑤ 在这里**如实留 idle** —— 因为本用例把它的裁决侧车改过了，而侧车属于 ⑤ 的
        #   **产物半份**（`_output_digest` 里含它）⇒ 它确实不再满足复用条件。这正是要的：
        #   回填不替它撒谎。（真实盘面上那盏"裁决过期"比这更隐蔽：回执对得上、侧车却过期，
        #   于是链每一轮都"复用 → 又真跑一遍"，表现成"卡住"。）
        self.assertEqual(self.s.state["stages"]["review"], "done(skip)")
        self.assertEqual(self.s.state["stages"]["audit"], "idle")

    def test_start_index_is_one_shot(self):
        """起点只对**这一次**起链生效 —— 否则一次「从 ⑨ 重跑」会把之后每一轮点「开始全链」都带偏。"""
        calls = self.install_successful_runner()
        asyncio.run(self.s.run_all())
        calls.clear()
        self.s._redo_from("write")
        self.s._set_start_from("write")
        asyncio.run(self.s.run_all())
        self.assertEqual(self.s.state["start_index"], 0)
        self.assertEqual(calls[0], "write")
        calls.clear()
        asyncio.run(self.s.run_all())                    # 第二次：从 ① 走，全复用 ⇒ 无调用
        self.assertEqual(calls, [])

    def test_backfill_leaves_an_unreusable_prior_stage_idle(self):
        """回填**不许**把"其实没跑、也复用不了"的阶段画成绿的。"""
        self.install_successful_runner()
        asyncio.run(self.s.run_all())
        (self.s.REPORTS / self.stage("review")["report"]).unlink()   # ③ 产物没了
        self.s._set_start_from("write")
        asyncio.run(self.s.run_all())
        self.assertEqual(self.s.state["stages"]["review"], "idle")
        self.assertEqual(self.s.state["stages"]["literature"], "done(skip)")
        # ④ 也被如实留灰：③ 的报告是它输入指纹的一半（上游报告变了 ⇒ 它的产物可能过期）
        self.assertEqual(self.s.state["stages"]["code"], "idle")

    def test_start_from_stage_drops_only_the_earlier_yellow_lights(self):
        """起点**之前**的黄灯作废（链不会走到它）；起点及之后的照留（链真会走到）。"""
        self.s.state["pending"] = {"stage": "audit", "kind": "paused", "actions": ["retry"]}
        self.s.state["halt_gate"] = True
        self.s._set_start_from("write")
        self.assertIsNone(self.s.state["pending"])
        self.assertFalse(self.s.state["halt_gate"])
        self.assertEqual(self.s.state["stages"]["audit"], "idle")
        # 起点之后的黄灯不许被顺手清掉
        self.s.state["pending"] = {"stage": "rubric", "kind": "failure", "actions": ["retry"]}
        self.s.state["halt_gate"] = True
        self.s._set_start_from("write")
        self.assertIsNotNone(self.s.state["pending"])
        self.assertTrue(self.s.state["halt_gate"])

    def test_redo_from_a_judge_must_not_stash_the_paper(self):
        """从 ⑫ 评分标终审 重跑时，`paper/` **不许**被整目录搬进 cache。

        `ARTIFACTS` 里 `paper` 被 ⑨（**第一声明者**）、⑬、⑭ 三处声明 —— 后两者是
        "读着现有论文再就地改"的阶段；而 `_redo_from` 会把重跑区间里**所有**声明都暂存，
        于是整个 `paper/` 连附录一起被搬走，面板上就是"论文没了"。
        判据：只有**第一声明者**的产物才该被搬（`_stage_rels(own_only=True)`）。
        """
        self.install_successful_runner()
        asyncio.run(self.s.run_all())
        paper = self.root / "paper"
        appendix = self.root / "paper_appendix"
        self.assertTrue((paper / "main.pdf").is_file())
        appendix.mkdir(exist_ok=True)
        (appendix / "main.pdf").write_bytes(b"%PDF-1.4\n" + b"appendix fixture " * 20)
        # 这三个阶段都不是 paper 的第一声明者 ⇒ 从它们重跑，论文必须原地不动
        for sid in ("rubric", "fix", "format"):
            self.s._redo_from(sid)
            self.assertTrue((paper / "main.pdf").is_file(),
                            f"从 {sid} 重跑把论文搬走了 —— 那个阶段正要读它")
            self.assertTrue(appendix.is_dir(), f"从 {sid} 重跑把附录搬走了")
        # ⑨ 论文撰写 是第一声明者 ⇒ 从它重跑照旧把论文搬走（那才是"重写一遍"）
        self.s._redo_from("write")
        self.assertFalse(paper.exists(), "从 ⑨ 重跑必须把论文搬走（重写时不许留着旧的冒充产物）")

    def _poison_audit_verdict(self):
        """把 ⑤ 的裁决改成"过期" —— 起点若从 ① 走，这一发就会把链拽回 ⑤。"""
        aud = self.stage("audit")
        (self.s.REPORTS / aud["report"]).with_suffix(".verdict.json").write_text(
            json.dumps({"schema_version": 1, "stage": "audit", "input_digest": "deadbeef",
                        "status": "PASS", "issues": []}), encoding="utf-8")

    def _pending(self, sid, action):
        self.s.state["pending"] = {"stage": sid, "kind": "failure", "actions": [action],
                                   "reason": "fixture", "verdict": "FAIL", "issues": []}

    def test_disclose_resumes_at_the_next_stage_not_from_the_top(self):
        """点「接受并披露」⑪ 应当去 ⑫，**不许**绕回 ⑤。

        判据：`/api/decision` 见到 `resumed` 必须按 `_apply_decision` 返回的 `resume_from`
        起链，而不是无条件 `_start_chain()`（后者会让 `run_all` 从 ① 走一遍）。否则 ⑤ 那份
        "过期"的裁决会在复用之后被 `run_all` 当场真跑一遍（`if verdict == "UNVERIFIED"`
        那段），阶段号看着就是"回到了 ⑤"。
        """
        self.install_successful_runner()
        asyncio.run(self.s.run_all())
        self._poison_audit_verdict()
        self._pending("cross", "disclose")
        seen = {}
        self.s._start_chain = Mock(side_effect=lambda: seen.__setitem__("i", self.s.state["start_index"]))
        r = asyncio.run(self.s.decision(self.s.DecisionReq(action="disclose")))
        self.assertTrue(r["resumed"])
        self.assertEqual(r["resume_index"], self.s.STAGE_IDX["cross"] + 1)
        self.assertEqual(seen["i"], self.s.STAGE_IDX["rubric"],
                         "披露之后必须接着 ⑫ 跑，不是从 ① 重走（那样会被 ⑤ 拦住）")

    def test_retry_and_rollback_resume_at_their_own_stage(self):
        """retry 回到**本阶段**、rollback 回到**目标阶段** —— 同样不许从 ① 重走。"""
        self.install_successful_runner()
        self.s.state["stages"]["cross"] = "failed"
        self._pending("cross", "retry")
        seen = {}
        self.s._start_chain = Mock(side_effect=lambda: seen.__setitem__("i", self.s.state["start_index"]))
        r = asyncio.run(self.s.decision(self.s.DecisionReq(action="retry")))
        self.assertEqual(seen["i"], self.s.STAGE_IDX["cross"])

        self._pending("cross", "rollback")
        r = asyncio.run(self.s.decision(self.s.DecisionReq(action="rollback", stage="code")))
        self.assertEqual(seen["i"], self.s.STAGE_IDX["code"])
        self.assertEqual(r["resume_index"], self.s.STAGE_IDX["code"])

    def test_disclose_on_the_last_stage_starts_past_the_end(self):
        """最后一个阶段被披露 ⇒ 起点落在**链尾**（直接去收交付），不是回头重走一遍。"""
        self._pending("demo", "disclose")
        r = asyncio.run(self.s._apply_decision(self.s.DecisionReq(action="disclose")))
        self.assertEqual(r["resume_index"], len(self.s.STAGES))
        self.assertEqual(self.s._set_start_index(r["resume_index"]), len(self.s.STAGES))

    def test_a_hard_kill_leaves_the_previous_report_recoverable_at_startup(self):
        """断电 / 硬杀之后重启续跑：不许丢开跑前被搬进暂存的那份报告。

        `_stash_markers_for_restore` 开跑前把报告搬进 `_pending_markers/`，而搬回去的
        `_restore` 只活在**那个进程的内存里**；进程被硬杀之后没人搬 ⇒ 上一份完好的报告
        永远扣在暂存里、`reports/` 只剩骨架或空白，而且它的**下游**因为"被搬走的文件不在
        盘上"成片失配 ⇒ 整段重跑（小时级）。
        判据：启动时的 `_recover_pending_markers()` 把它搬回来（**只在盘上那份不在时才搬**）。
        被打断的阶段因为没有回执、本来就要重跑，所以"能不能续上"由这一条决定。
        """
        st = self.stage("review")
        dest = self.s._PENDING_MARKERS / "review"
        dest.mkdir(parents=True, exist_ok=True)
        (dest / "reports_MODELING_REVIEW_REPORT.md").write_text("上一份完好的评审报告",
                                                                encoding="utf-8")
        self.assertFalse((self.s.REPORTS / st["report"]).exists(), "前提：盘上那份确实没了")
        self.s._recover_pending_markers()
        self.assertTrue((self.s.REPORTS / st["report"]).is_file(),
                        "断电后必须能把它找回来，否则下游整段重跑")
        self.assertEqual((self.s.REPORTS / st["report"]).read_text(encoding="utf-8"),
                         "上一份完好的评审报告")

    def test_recovery_does_not_overwrite_a_real_new_product(self):
        """反面：盘上已有一份像样的新产物 ⇒ **不许**拿旧版盖掉（那就是"旧产物冒充新一轮"）。

        判据必须**只在确证是骨架时**才搬回（侧车在、且 status=UNVERIFIED）。若写成
        "门禁的裁决侧车不是 UNVERIFIED 就搬回"，那侧车**不在**盘上时这句取反恰恰成了
        "搬回" ⇒ 会把 agent 刚写完的报告换回旧的。
        """
        st = self.stage("review")
        self.report(st, "这一轮刚写好的新评审报告\n" * 20)
        dest = self.s._PENDING_MARKERS / "review"
        dest.mkdir(parents=True, exist_ok=True)
        (dest / "reports_MODELING_REVIEW_REPORT.md").write_text("上一版旧的", encoding="utf-8")
        self.s._recover_pending_markers()
        self.assertIn("这一轮刚写好的",
                      (self.s.REPORTS / st["report"]).read_text(encoding="utf-8"),
                      "盘上是新产物时不许拿旧版盖掉")
        # 而且那份已失效的旧副本要**清掉** —— 留着它会让该阶段的防半成品机制永久失效
        # （`_stash_markers_for_restore` 见 tgt 存在就跳过 ⇒ mapping 永远为空）。
        self.assertFalse((dest / "reports_MODELING_REVIEW_REPORT.md").exists(),
                         "盘上已是新产物 ⇒ 暂存里那份旧副本要作废（否则 mapping 永远为空）")

    def test_a_pending_on_the_last_stage_does_not_brick_the_driver(self):
        """在 ⑯（链尾）上点「接受并披露」⇒ `_set_start_index(16)`，run_all 顶部那行
        `STAGES[index]['name']` 会越界 ⇒ IndexError；**那一行在 `try:` 之外** ⇒ `finally`
        （唯一把 `running` 置回 False 的地方）不执行 ⇒ 链已死，面板却还报"在运行"：
        回「已在运行」、任何决策 409、只能重启驱动（黄灯还已被清掉，看着像"点了没反应"）。

        判据：这条路上 run_all 必须**正常跑完**，而不是崩在起跑线上。
        """
        self.install_successful_runner()
        asyncio.run(self.s.run_all())
        self._pending("demo", "disclose")
        r = asyncio.run(self.s._apply_decision(self.s.DecisionReq(action="disclose")))
        self.s._set_start_index(r["resume_index"])          # = len(STAGES) = 链尾
        asyncio.run(self.s.run_all())
        self.assertFalse(self.s.state["running"], "起跑期异常会让 running 永远卡在 True")
        self.assertTrue(self.s.state["run_completed"], self.s.state["halt_reason"])

    def test_backfill_keeps_stale_marks_for_stages_before_the_start(self):
        """起点之前的阶段这一轮**走不到**、不会重新推导 ⇒ 它们「按旧要求交付」的标记
        必须留着。整份清掉会让 `_backfill_before` 读到空集合、把那些阶段画成干净的 ✅
        （阶段由 done(stale-instr) 变 done(skip)、面板蓝条随之整批消失）
        —— 那正是「静默放行」，而蓝条是「按旧要求交付」唯一的可见痕迹。
        """
        self.install_successful_runner()
        asyncio.run(self.s.run_all())
        self.s.state["stale_instr"] = {"analysis"}
        self.s.state["stages"]["analysis"] = "done(stale-instr)"
        self.s._set_start_from("write")
        asyncio.run(self.s.run_all())
        self.assertIn("analysis", self.s.state["stale_instr"], "起点之前的标记被清掉了")
        self.assertEqual(self.s.state["stages"]["analysis"], "done(stale-instr)")

    def test_the_stage_hook_asks_for_a_partial_package(self):
        """阶段性同步**必须** `final=False`：缺省是严格分支，
        而 ⑭ 写的清单声明了要等 ⑯ 才产出的 `demo.html` ⇒ `package()` 抛「找不到」
        ⇒ 从 ⑭ 起**每一次同步都失败**，"每阶段把已做好的移入"等于没生效。
        """
        src = (PROJECT / "lib/web/server.py").read_text(encoding="utf-8")
        i = src.index("def _maybe_collect_outputs")
        self.assertIn("_collect_outputs(final=False)", src[i:i + 2600],
                      "阶段性同步必须显式 final=False；缺省 True 会因 demo.html 还没产出而每次都失败")

    def test_handback_puts_the_previous_report_back(self):
        """交回上游那条路有意不产出报告，但**必须把上一份搬回**：
        否则 `reports/` 空着、`gate_result()` 只能给 UNVERIFIED，run_all 在裁决检查那儿
        就 halt，**永远走不到 `check_handback`** ⇒ 交回单推荐的回退阶段根本看不到。
        """
        st = self.stage("review")
        self.report(st, "上一轮的评审报告\n" * 40)
        before = (self.s.REPORTS / st["report"]).read_text(encoding="utf-8")

        async def hb(prompt, sid, cap=None):
            self.s.HANDBACK.write_text("target: analysis\nreason: 补算", encoding="utf-8")
            return 0, "", False          # rc=0 且不产出报告 = 按 SKILL 交回上游

        self.s._call = hb
        self.assertEqual(asyncio.run(self.s.run_stage(st)), "ok")
        self.assertTrue((self.s.REPORTS / st["report"]).is_file(),
                        "交回上游时上一份报告必须原路搬回，否则驱动读不到裁决、也走不到交回单")
        self.assertEqual((self.s.REPORTS / st["report"]).read_text(encoding="utf-8"), before)

    def test_a_skeleton_written_before_a_pause_does_not_evict_the_previous_version(self):
        """暂停时**不许**把开跑前那份**完好的报告与裁决**丢掉。

        根因：搬回的判据是 `_artifact_ok()`（只看"文件在不在、>80 字节"），门禁按 SKILL
        「先落骨架」（§6.1）写的那一小份骨架（562 字节）照样通过 ⇒ 被当成"产出了有效产物"。
        判据换成「**这次有没有真的写出回执**」—— 回执在跑之前刚被作废（`_invalidate_stage`），
        只有真正成功才会被重新写上，所以它精确等价于"真的产出了可接受的东西"。
        """
        st = self.stage("verify")
        self.report(st, "上一轮的完整裁决\n" * 200)
        before = (self.s.REPORTS / st["report"]).read_text(encoding="utf-8")
        self.assertGreater(len(before), 80)

        async def interrupted(prompt, sid, cap=None):
            # 骨架 > 80 字节 ⇒ 旧判据会放过它
            (self.s.REPORTS / st["report"]).write_text("骨架占位\n" * 40, encoding="utf-8")
            self.s.state["stopping"] = True
            return -1, "", False

        self.s._call = interrupted
        asyncio.run(self.s.run_stage(st))
        self.assertEqual((self.s.REPORTS / st["report"]).read_text(encoding="utf-8"), before,
                         "写了骨架 ≠ 产出了有效产物 —— 旧那份必须原路搬回")

    def test_review_repair_halts_into_pending_then_rollback_replays(self):
        """门禁不过 → 不再自动回退，而是转黄灯等用户；用户选回退后才重跑。"""
        calls = self.install_successful_runner({"review": 1})
        asyncio.run(self.s.run_all())
        # 第一次：停在 review，转黄灯，不收集交付
        self.assertFalse(self.s.state["run_completed"])
        self.assertEqual(self.s.state["stages"]["review"], "awaiting_user")
        p = self.s.state["pending"]
        self.assertEqual(p["stage"], "review")
        self.assertEqual(p["kind"], "failure")
        self.assertEqual(p["recommended"], "analysis")        # 默认映射 review→analysis
        self.assertEqual(p["recommended_source"], "default")
        self.assertIn("rollback", p["actions"])
        self.assertIn("disclose", p["actions"])               # 有产物 → 可披露
        self.assertTrue(self.s.state["halt_gate"])
        self.s._collect_outputs.assert_not_called()
        # 用户选「回退到 analysis」
        asyncio.run(self.s._apply_decision(self.s.DecisionReq(action="rollback", stage="analysis")))
        calls.clear()
        asyncio.run(self.s.run_all())
        self.assertTrue(self.s.state["run_completed"], self.s.state["halt_reason"])
        self.assertEqual(calls[:2], ["analysis", "review"])   # literature 回执未作废 → done(skip)

    def test_cross_repair_halts_then_rollback_rechecks_mathproof(self):
        calls = self.install_successful_runner({"cross": 1})
        asyncio.run(self.s.run_all())
        p = self.s.state["pending"]
        self.assertEqual(p["stage"], "cross")
        self.assertEqual(p["recommended"], "write")           # 默认映射 cross→write
        asyncio.run(self.s._apply_decision(self.s.DecisionReq(action="rollback", stage="write")))
        calls.clear()
        asyncio.run(self.s.run_all())
        self.assertTrue(self.s.state["run_completed"], self.s.state["halt_reason"])
        # 阶段顺序：write 之后是 mathproof（数学论证门禁）再 cross，
        # 排版与版式（14Layout-and-format）在内容阶段**之后**，不出现在这条回退链的前段。
        # 本用例钉的是：回退之后 mathproof 要在 cross 之前重判一次。
        self.assertEqual(calls[:3], ["write", "mathproof", "cross"])

    def test_persistent_failure_halts_after_single_attempt(self):
        """每阶段只跑 1 次：失败即转黄灯，既不自动重试 3 次、也不自动回退。"""
        calls = self.install_successful_runner({"verify": 100})
        asyncio.run(self.s.run_all())
        self.assertEqual(calls.count("verify"), 1)
        self.assertNotIn("demo", calls)
        # 同上：中途的阶段性打包是**预期行为**（⑨/⑭ 各一次），这条守的是“链没收口”。
        self.assertFalse(self.s.state["run_completed"])
        self.assertTrue(self.s.state["halt_gate"])
        self.assertEqual(self.s.state["stages"]["verify"], "awaiting_user")
        self.assertEqual(self.s.state["pending"]["stage"], "verify")

    def test_changed_problem_invalidates_existing_success(self):
        calls = self.install_successful_runner()
        asyncio.run(self.s.run_all())
        calls.clear()
        (self.root / "request").mkdir()
        (self.root / "request/problem.md").write_text("new generic problem")
        asyncio.run(self.s.run_all())
        self.assertEqual(calls, self.expected_full_chain())
        self.assertTrue(self.s.state["run_completed"], self.s.state["halt_reason"])

    def test_changed_report_invalidates_downstream(self):
        """外部改动某阶段产物 → 该阶段必重跑；**下游按输入指纹决定**。

        语义：runner 重跑时若产出一致内容 ⇒ 下游输入未变 ⇒ 复用。
        也就是"重绘几张图不该拖垮整条下游"。
        """
        calls = self.install_successful_runner()
        asyncio.run(self.s.run_all())
        self.report(self.stage("analysis"), "external modification")
        calls.clear()
        asyncio.run(self.s.run_all())
        self.assertEqual(calls, ["analysis"])          # 只重跑被改动的那一阶段
        self.assertTrue(self.s.state["run_completed"], self.s.state["halt_reason"])

    def test_changed_report_content_propagates_downstream(self):
        """若重跑后产物**内容确实变了**，下游输入指纹随之变化 → 必须级联重跑。"""
        self.install_successful_runner()
        asyncio.run(self.s.run_all())
        # 外部扰动 analysis 产物 → 它必须重跑
        self.report(self.stage("analysis"), "external modification")

        def after(sid):
            if sid == "analysis":      # 重跑时产出**不同**内容
                (self.s.REPORTS / "ANALYSIS_MODELING_REPORT.md").write_text(
                    "重跑后的建模报告：" + "y" * 300, encoding="utf-8")
        calls = self.install_successful_runner(after=after)
        asyncio.run(self.s.run_all())
        # 从 analysis 起（它之前的阶段回执仍新鲜 ⇒ `ok(skip)`，不进 calls）。
        #   别用 `[1:]` 表达这件事：链首是 ⓪ 读题而不是 literature，砍掉的是读题 ⇒ 假红。
        chain = self.expected_full_chain()
        self.assertEqual(calls, chain[chain.index("analysis"):])

    def test_stale_files_without_receipt_are_not_skipped(self):
        st = self.stage("literature")
        self.report(st, "old result")
        calls = self.install_successful_runner()
        self.assertEqual(asyncio.run(self.s.run_stage(st)), "ok")
        self.assertEqual(calls, ["literature"])

    def test_noop_cannot_reuse_old_completion_marker(self):
        st = self.stage("literature")
        self.report(st, "old result")
        self.s._call = AsyncMock(return_value=(0, "", False))
        self.assertEqual(asyncio.run(self.s.run_stage(st)), "failed")

    def test_an_interrupted_stage_gets_its_previous_report_back(self):
        """阶段**被打断**（暂停 / 强杀）⇒ 开跑前搬走的那一份必须原路搬回。

        不搬的后果是连锁的：③ 建模评审门禁 每被打断一次都会把 `MODELING_REVIEW_REPORT.md`
        （连同裁决侧车）留在 `cache/<时间戳>_...` 里，而它们的缺失让 7 条下游回执的
        **artifacts 半份**同时失配 ⇒ ④–⑯ 全被判「要重跑」，表现成"只是暂停一下，
        却又要重新跑一遍"。

        与上一条的分界：**失败不回填**（不产出就不许拿旧产物冒充完成），
        只有**被打断**才回填。
        """
        st = self.stage("review")
        self.report(st, "上一份完好的报告")

        def interrupted(*_a, **_kw):
            self.s.state["stopping"] = True      # 模拟：刚开跑就被暂停杀掉
            return (-1, "", False)

        self.s._call = AsyncMock(side_effect=interrupted)
        self.assertEqual(asyncio.run(self.s.run_stage(st)), "stopped")
        self.assertTrue((self.root / "reports/MODELING_REVIEW_REPORT.md").is_file(),
                        "被打断后上一份报告没搬回来 —— 下游回执会因此整片失配、全链重跑")

    def test_nothing_is_rejudged_after_the_chain_finishes(self):
        """收尾**不再重判任何判官**。

        口径：⑪ 过后已表示正文没问题，⑫ 和 ⑬ 只是打磨语句 —— 打磨必然让新稿与之前判过的
        对不上，不能因此把 ⑩数学论证门禁 / ⑪跨问一致性 / ⑫评分标终审 拉回来重判。
        链跑完就是跑完：demo 改了 `paper/main.tex` 之后，收尾不得再按名单复验一遍。
        """
        def after(sid):
            if sid == "demo":
                with (self.root / "paper/main.tex").open("a", encoding="utf-8") as f:
                    f.write("% updated by demo")

        calls = self.install_successful_runner(after=after)
        asyncio.run(self.s.run_all())
        tail = calls[calls.index("demo") + 1:]
        self.assertEqual(tail, [], f"收尾不该再重跑任何阶段，实际 {tail}")
        self.assertTrue(self.s.state["run_completed"], self.s.state["halt_reason"])

    def test_a_polish_pass_does_not_make_the_content_judges_run_again(self):
        """⑬/⑭ 打磨措辞与版式之后，⑩⑪⑫ **下次也不该被拉回来重判**。

        ⑭ 只动 `paper/sections/*.tex` 里的排版（例如式(14) 后的定点位移），下一轮却让
        ⑩⑪⑫ 各重跑一遍（每次十几分钟），而它们判的内容一个字没变。
        判据见 `_later_paper_owner`：「此后只有打磨者（⑬按判词返修 / ⑭排版）动过论文」
        ⇒ 内容判决仍然有效。⑬ 真改了正文的情形**不**走这条（它之后没有"更后的打磨者回执有效"，
        该重判的照旧重判）。
        """
        def after(sid):
            if sid == "format":
                p = self.root / "paper/sections/5_problem4.tex"
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text("\\par\\vspace{9pt}\n", encoding="utf-8")

        calls = self.install_successful_runner(after=after)
        asyncio.run(self.s.run_all())
        self.assertTrue(self.s.state["run_completed"], self.s.state["halt_reason"])
        calls.clear()
        asyncio.run(self.s.run_all())
        judges = [c for c in calls if c in ("mathproof", "cross", "rubric")]
        self.assertEqual(judges, [], f"内容判官不该因打磨被重判，实际 {calls}")
        self.assertEqual(sorted(self.s.state.get("layout_superseded") or []),
                         ["cross", "mathproof", "rubric"],
                         "被打磨过的内容判官要留在痕迹里（面板可见、可手动重跑）")
        self.assertTrue(self.s.state["run_completed"])

    def test_a_cross_verdict_comes_back_to_cross_after_the_repair(self):
        """⑪ 把 claim 判词交给 ⑬ 之后，只要 ⑬ 动了 `paper/`，⑪ **必须复评**。

        口径：「当时说 13、14 只打磨，但是 **11 这里还没结束**」。代价很具体：⑬ 可以把附录表里的
        `\\mp0.013` 改成 `-0.013/+0.020` —— 那**动了数值**，而那条判词正是 ⑪ 为这张表提的。
        若 `_layout_superseded` 把 `fix` 也算作 ⑪ 的"打磨者" ⇒ 判"审查对象没变" ⇒ 不回评，
        **改了数值也没人复查**。
        （⑫ 不一样：它判完就结束了，⑬ 只是它的工具步骤 ⇒ 那半边口径照旧，见 `_layout_superseded`
          的注释与 `test_the_repair_goes_back_to_rubric_instead_of_straight_forward`。）
        """
        calls = []

        def after(sid):
            calls.append(sid)
            if sid == "fix":           # ⑬ 真动了稿子
                p = self.root / "paper/sections/5_problem4.tex"
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text("\\par% 13 定点改写\n", encoding="utf-8")

        self.install_successful_runner(after=after)
        # ⑪ 恒判 REVISE_CLAIM（纯论文侧）⇒ 每次都会把活交给 ⑬；桩必须幂等（见下条用例的坑③）
        self.s._gate_decision = lambda st: (
            {"status": "REVISE_CLAIM", "reason": "paper_repair_required", "target": "fix",
             "issues": [{"id": "c1", "category": "claim", "tier": "must"}], "advisories": []}
            if st["id"] == "cross"
            else {"status": "PASS", "reason": "", "issues": [], "advisories": []})
        asyncio.run(self.s.run_all())
        i = calls.index("fix")
        self.assertIn("cross", calls[i + 1:],
                      f"⑬ 改了稿之后 ⑪ 没被拉回来复评，实际 {calls}")

    def test_a_rejudge_with_no_advisories_clears_the_old_badge(self):
        """`adv_by_stage`（阶段行上那个建议角标）必须随每次复评更新，直到 ok 时清掉。

        判据：**非 ok** 的分支里也要覆盖"复评后一条建议都没有"这一格 —— 缺了它，上一轮
        那批会原封不动留着，面板显示的建议属于一个**早就不存在**的裁决（谎报）。
        第二轮复评（0 条建议）之后，那个阶段在 `adv_by_stage` 里必须已经没有条目。
        """
        # ⑪ 恒判 REVISE_CLAIM（交 ⑬ 定点改写，不挂黄灯）；建议只在**第 1 轮**给
        # （用 `fix_rounds` 区分轮次：它在交接后由 `_back_to_judge` 置位）。
        def verdict(st):
            if st["id"] != "cross":
                return {"status": "PASS", "reason": "", "issues": [], "advisories": []}
            first = not (self.s.state.get("fix_rounds") or {}).get("cross")
            return {"status": "REVISE_CLAIM", "reason": "paper_repair_required", "target": "fix",
                    "issues": [{"id": "c1", "category": "claim", "tier": "must"}],
                    "advisories": ([{"id": "adv-only-in-round-1", "severity": "info"}]
                                   if first else [])}

        def after(sid):
            if sid == "fix":
                p = self.root / "paper/sections/5_problem4.tex"
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text("\\par% 13 定点改写\n", encoding="utf-8")

        self.install_successful_runner(after=after)
        self.s._gate_decision = verdict
        asyncio.run(self.s.run_all())
        self.assertEqual((self.s.state.get("fix_rounds") or {}).get("cross", 0) >= 2, True,
                         f"⑪ 应当复评过至少两轮，实际 {self.s.state.get('fix_rounds')}")
        self.assertNotIn("cross", self.s.state.get("adv_by_stage") or {},
                         "复评后 0 条建议，上一轮那批还挂在 📝 上（显示的是一个不存在的裁决）")

    def _resume_with_rubric_verdict(self, verdict, strict=False, spy=None):
        """让链**停在 rubric**（前面每一关都留下回执），再换掉 rubric 的裁决续跑。

        三处约束：
          ① 不能把 `self.s.STAGES` 截短成 [rubric, fix] —— `_input_split` 要去 STAGES 里
             找 `code`/`write` 算输入指纹，截短后抛 StopIteration，被 run_all 兜成"驱动异常"，
             测试就会**因为错的理由**红或绿。
          ② 不能替换 `self.s.run_stage` —— `run_all` 正是靠它决定"这关已经做过了、跳过"，
             换掉之后每个阶段都会被真的执行一遍。
          ③ 桩必须**幂等** —— `gate_result` 与门禁尾部各调一次 `_gate_decision`，
             同一阶段一次执行会被问两遍；用 pop 队列会一次消费两条裁决。
        该用例的搭法：第一轮让 rubric"失败"停机（fix/demo 因此没跑过），第二轮只换裁决。
        """
        calls = []
        fixed = {"done": False}

        def after(sid):
            calls.append(sid)
            if sid == "fix":
                fixed["done"] = True
                # 只能改 `.tex`：`paper/` 下的 pdf 属于构建产物，刻意不进指纹。
                path = self.root / "paper/main.tex"
                path.parent.mkdir(parents=True, exist_ok=True)
                prior = path.read_text(encoding="utf-8") if path.exists() else ""
                path.write_text(prior + "\n% 13Repair-by-rubric-verdict\n", encoding="utf-8")

        self.install_successful_runner(failures={"rubric": 1}, after=after)
        if spy is not None:
            _inner = self.s._call

            async def _spy(prompt, sid, cap=None):
                spy(prompt, sid)
                return await _inner(prompt, sid, cap)

            self.s._call = _spy
        asyncio.run(self.s.run_all())
        self.assertFalse(self.s.state["run_completed"], "第一轮应停在 rubric 上")
        calls.clear()

        if strict:
            # 第一轮之后才开严格模式：开了之后 `_gate_decision` 会去校验题意契约与 v2 裁决，
            #   而 fixture 造的是 v1 侧车、也没有 TASK_CONTRACT.json —— 那样第一轮根本跑不到 rubric。
            (self.root / "config").mkdir(exist_ok=True)
            (self.root / "config/content_quality.json").write_text(
                '{"schema_version": 1, "verdict_schema_version": 2}', encoding="utf-8")
        self.s._gate_decision = lambda st: (
            (verdict["after"] if fixed["done"] else verdict["before"])
            if st["id"] == "rubric"
            else {"status": "PASS", "reason": "", "issues": [], "advisories": []})
        asyncio.run(self.s.run_all())
        return calls

    def test_rubric_paper_side_verdict_runs_fix_then_rechecks(self):
        """rubric 的正向出路：论文侧判词**不停机**，跑完 13Repair-by-rubric-verdict 再对新版本复评一次。

        这是全链唯一一条"门禁不通过却继续往下走"的路径。复评靠 `_review_object_stale`
        判 —— 13Repair-by-rubric-verdict 写了 `paper/`，所有在成稿上做判断的阶段就都失效了。
        """
        calls = self._resume_with_rubric_verdict({
            "before": {"status": "NEEDS_FIX", "reason": "paper_repair_required", "target": "fix",
                       "issues": [{"id": "r1", "category": "claim", "tier": "must"}],
                       "advisories": []},
            "after": {"status": "PASS", "reason": "", "issues": [], "advisories": []}})
        self.assertEqual(calls[:2], ["rubric", "fix"],
                         f"判词后应紧接着跑 13Repair-by-rubric-verdict，实际 {calls}")
        self.assertEqual(calls.count("rubric"), 2,
                         f"fix 之后必须复评一次 rubric，实际 {calls}")
        # 复评不是"排在最后（收尾复验）"，而是**fix 之后立刻回 12**
        # （⑬ 是 ⑫ 的工具步骤：处理完就要返回 12）⇒ ⑫ 复评完才继续 14/15，
        # 于是收尾复验只需补那些被 ⑬ 改动带失效的上游判官（mathproof/cross）。
        self.assertEqual(calls[:3], ["rubric", "fix", "rubric"],
                         f"顺序应是 ⑫→⑬→⑫ 复评，实际 {calls}")
        self.assertLess(calls.index("rubric", 2), 0 if "format" not in calls else calls.index("format"),
                        f"复评必须发生在 14Layout-and-format 之前，实际 {calls}")
        self.assertTrue(self.s.state["run_completed"], self.s.state["halt_reason"])

    def test_verify_hands_paper_side_findings_to_the_repair_stage(self):
        """“15 判完给 13 改，正如 12 判完给 13 改一样，13 改完后直接跳回 15”。

        ⑮ 验收 后面**没有写作阶段** —— 所以 `claim_revision` 若走 `_halt("缺少后续写作阶段")`，
        它的判词（例如表 1 漏登记一个量 /「已证明」缺推导指针）就只能回退 ⑨ 重写整篇。
        可那两条全是**文字级**，而 ⑬ 就是为「论文侧定点改写」造的 ⇒ 交给它、改完跳回 ⑮ 复评，
        与 ⑫↔⑬ 同一套。⑮ 自己会重新编译（SKILL 的 Step 7/8），所以跳过 ⑭ 不会留下旧 PDF。
        """
        calls = []

        async def runner(prompt, sid, cap=None):
            calls.append(sid)
            st = next(x for x in self.s.STAGES if x["id"] == sid)
            if sid == "write":
                (self.root / "paper").mkdir(exist_ok=True)
                (self.root / "paper/main.pdf").write_bytes(b"%PDF-1.4\n" + b"x" * 100)
            else:
                self.report(st, "最终结论：PASS")
            if sid == "code":
                (self.root / "code").mkdir(exist_ok=True)
                (self.root / "code/example.txt").write_text("fixture", encoding="utf-8")
            if sid == "fix":
                # ⑬ 改稿 ⇒ ⑮ 的审查对象真变了。不变的话 `_back_to_judge` 会判"没动稿、回去空转"
                # 而**刻意不回评** —— 那是另一半设计，本用例要先有"真改了"才测得到回评。
                (self.root / "paper").mkdir(exist_ok=True)
                p = self.root / "paper/main.tex"
                p.write_text((p.read_text(encoding="utf-8") if p.exists() else "") + "\n% 13 fix\n",
                             encoding="utf-8")
            if st.get("gate"):
                (self.s.REPORTS / st["report"]).with_suffix(".verdict.json").write_text(
                    json.dumps({"schema_version": 1, "stage": sid,
                                "input_digest": self.s._input_digest(st),
                                "status": "PASS", "issues": []}, ensure_ascii=False),
                    encoding="utf-8")
            return 0, "", False

        self.s._call = runner
        claim = {"id": "V1", "severity": "soft", "category": "claim",
                 "check_ids": ["content_coverage"], "evidence": "e", "fix": "f", "recheck": "r"}

        def dec(st):
            # 桩必须幂等：同一阶段一次执行会被问好几遍（见 `_resume_with_rubric_verdict`）
            if st["id"] == "verify" and calls.count("verify") <= 1:
                return {"status": "REVISE_CLAIM", "reason": "content_repair_required",
                        "issues": [claim], "checks": []}
            return {"status": "PASS", "reason": "", "issues": [], "advisories": []}

        self.s._gate_decision = dec
        asyncio.run(self.s.run_all())
        self.assertIn("verify", calls, f"⑮ 应当跑过，实际 {calls}")
        i1 = calls.index("verify")
        self.assertIn("fix", calls[i1:], f"⑮ 的论文侧判词应当交给 ⑬，实际 {calls}")
        i_fix = calls.index("fix", i1)
        self.assertIn("verify", calls[i_fix + 1:], f"⑬ 改完必须回 ⑮ 复评，实际 {calls}")
        self.assertLess(calls.index("verify", i_fix), len(calls),
                        "复评要真的发生")
        self.assertNotIn("write", calls[i_fix + 1:],
                         "这条路的重点是**不必**回退 ⑨ 重写整篇")
        self.assertTrue(self.s.state["run_completed"], self.s.state["halt_reason"])
        self.assertEqual((self.s.state.get("fix_rounds") or {}).get("verify"), 1,
                         "来回一轮就该记一轮（按门禁分别计数）")

    def _verify_handoff_runner(self, mutate_paper):
        """⑮ 恒判 REVISE_CLAIM、⑬ 按 `mutate_paper` 决定改不改稿的夹具。"""
        calls = []

        async def runner(prompt, sid, cap=None):
            calls.append(sid)
            st = next(x for x in self.s.STAGES if x["id"] == sid)
            if sid == "write":
                (self.root / "paper").mkdir(exist_ok=True)
                (self.root / "paper/main.pdf").write_bytes(b"%PDF-1.4\n" + b"x" * 100)
            else:
                self.report(st, "最终结论：PASS")
            if sid == "code":
                (self.root / "code").mkdir(exist_ok=True)
                (self.root / "code/example.txt").write_text("fixture", encoding="utf-8")
            if sid == "fix" and mutate_paper:
                (self.root / "paper").mkdir(exist_ok=True)
                p = self.root / "paper/main.tex"
                p.write_text((p.read_text(encoding="utf-8") if p.exists() else "")
                             + f"\n% 13 round {calls.count('fix')}\n", encoding="utf-8")
            if st.get("gate"):
                (self.s.REPORTS / st["report"]).with_suffix(".verdict.json").write_text(
                    json.dumps({"schema_version": 1, "stage": sid,
                                "input_digest": self.s._input_digest(st),
                                "status": "PASS", "issues": []}, ensure_ascii=False),
                    encoding="utf-8")
            return 0, "", False

        self.s._call = runner
        claim = {"id": "V1", "severity": "soft", "category": "claim",
                 "check_ids": ["content_coverage"], "evidence": "e", "fix": "f", "recheck": "r"}
        self.s._gate_decision = lambda st: (
            {"status": "REVISE_CLAIM", "reason": "content_repair_required",
             "issues": [claim], "checks": []} if st["id"] == "verify"
            else {"status": "PASS", "reason": "", "issues": [], "advisories": []})
        return calls

    def test_the_repair_loop_terminates_when_the_repair_changes_nothing(self):
        """⑮→⑬→⑮ 在「⑬ 不动稿」时必须**有界**，不能空转。

        ⑬ 按 SKILL「判词不属实的记 not_reproduced、不动稿」⇒ 若 `_back_to_judge` 在
        `fix_rounds += 1` **之前**就 return，轮数永不增长 ⇒ 上限永不命中 ⇒ 控制流从 ⑬ 往前走、
        经 ⑭ **又撞回 ⑮** ⇒ 再交接 ⑬ …… run_stage 会被反复调用仍在 fix→format→verify
        打转、`run_completed` 永远 False；⑬ 回执仍新鲜时更省 —— **agent 调用 0 次**，
        链既不前进也不亮黄灯，只能手点 ⏹。
        判据：**有界**（不空转），且「没动稿」这一轮要**越过**那一关继续往下。
        """
        calls = self._verify_handoff_runner(mutate_paper=False)
        asyncio.run(self.s.run_all())
        # 判据是**有界**：不动稿也占额度 ⇒ 最多 MAX+1 轮就结束；否则会一直转到天荒地老
        # （61 次调用仍不退出、run_completed 永远 False）。
        self.assertLessEqual(calls.count("fix"), self.s.RUBRIC_FIX_MAX_ROUNDS + 1,
                             f"不动稿也要占额度，不许无限来回：{calls}")
        self.assertLess(len(calls), 40, f"不许空转（原缺陷是 61 次仍不退出）：{calls}")
        self.assertTrue(self.s.state["run_completed"] or self.s.state["halt_gate"],
                        f"必须有终点，不能既不前进也不亮黄灯：{calls}")

    def test_a_repair_round_that_only_rewrites_its_report_does_not_send_us_back(self):
        """⑬ 只重写**自己的记录**不算"改过稿" —— 不该回 ⑮ 复评一轮。

        病灶在 `_input_split` 的默认（"所有前序报告全收"）：⑬ 的 `FIX_REPORT.md` 卡在 ⑮ 的
        输入里，而 ⑬ **每跑一次就重写一份**（哪怕它判"判词不属实、不动稿"，SKILL 允许）⇒
        `_review_object_stale(verify)` 恒真 ⇒ `_back_to_judge` 以为"稿子动了"，白回 ⑮ 复评；
        回评又是一模一样的 claim 判词 ⇒ 再交 ⑬ …… 一路烧到 3 轮上限转黄灯为止
        （本用例的桩就是这条轨迹：`calls.count("fix")` 会是 3、链以黄灯收场）。
        处置见 `lib/web/server.py::_REPORT_INPUT_EXCLUDE`；逐阶段的指纹性质由
        `test_stale_noise.py::NarrativeReportNoiseTests` 钉住。
        """
        calls = self._verify_handoff_runner(mutate_paper=False)   # ⑬ 只写 FIX_REPORT.md
        asyncio.run(self.s.run_all())
        self.assertEqual(calls.count("verify"), 1,
                         f"⑬ 没动稿（只重写了返修记录）⇒ ⑮ 不该被拉回来复评：{calls}")
        self.assertEqual(calls.count("fix"), 1, f"只该交接一轮：{calls}")
        self.assertTrue(self.s.state["run_completed"],
                        f"应当越过 ⑮ 继续往下并跑完，实际停在 {self.s.state.get('halt_reason')}")
        self.assertFalse(self.s.state["halt_gate"], "没动稿不是失败，不该亮黄灯")

    def test_the_repair_loop_halts_at_the_cap_instead_of_silently_moving_on(self):
        """每轮都真改稿 ⇒ 上限（3 轮）到顶要**转黄灯**，不是静默往前走。

        口径：「先最多 3 轮…还不过就转黄灯问人」。上限那条路若只 `return False` ⇒
        调用方 `index += 1` 一路往下、链报成功，而那一关的判词**一次都没被处置**
        （也就是"报成功，而 NEEDS_FIX 从未被重新看过"）。
        """
        calls = self._verify_handoff_runner(mutate_paper=True)
        asyncio.run(self.s.run_all())
        self.assertEqual(calls.count("fix"), self.s.RUBRIC_FIX_MAX_ROUNDS,
                         f"每轮都改了稿 ⇒ 应当正好来回 {self.s.RUBRIC_FIX_MAX_ROUNDS} 轮：{calls}")
        self.assertTrue(self.s.state["halt_gate"], "到顶必须转黄灯交人")
        self.assertEqual(self.s.state["pending"]["stage"], "verify")
        self.assertFalse(self.s.state["run_completed"])

    def test_autopilot_keeps_going_and_only_stops_a_spin(self):
        """托管该不该自动关：判据是**速率**，不是总次数。

          · 慢循环（窗内回退不密，例如一轮一小时）⇒ 一直托管，**不**自动关；
          · 自旋（窗内回退过密，例如门禁秒判失败、一轮几秒）⇒ 自动关掉托管 + 留人工黄灯。

        为什么不能按键分桶计数来判：真实的 `_apply_decision` 会把 `state["pending"]` 清成
        None（`_redo_from` → `_set_pending(None)`）⇒ 写计数那侧求键时 pending 已经没了，键从
        `"audit->code"` 变成 `"None->code"`，与判据读的键永不相等、`n >= 3` 恒假 —— 闸根本
        没接上。凡是拿假实现冒充 `_apply_decision` 的桩，都必须照真实行为把 pending 清掉，
        否则正是这个错会被掩住（日志里 `None->code` 一路数到 3 也不会有任何提示）。
        """
        pend = {"stage": "verify", "kind": "failure",
                "actions": ["retry", "rollback", "disclose"], "recommended": "format"}
        started = []
        self.s._start_chain = Mock(side_effect=lambda: started.append(1))
        self.s._set_start_index = Mock()

        async def fake_apply(req):
            # 照**真实** `_apply_decision` 的行为：回退一旦落实，pending 就没了。缺这一行的假实现
            #   会把键名不一致这类缺陷藏起来。新闸不按键分桶，
            #   但这一行留着，防的是"日后又有人把闸改回按键分桶"这一类回潮。
            self.s.state["pending"] = None
            return {"ok": True, "resumed": True, "resume_index": 14,
                    "action": req.action, "target": req.stage}
        self.s._apply_decision = fake_apply

        # ① 慢循环：窗内只有 3 条**老**时刻 ⇒ 再来一次照样回退，托管**不**关
        old = time.time() - (self.s.AUTOPILOT_SPIN_WINDOW + 60)
        self.s.state["auto_rollback_times"] = [old, old, old]
        self.s.state["autopilot"] = True
        self.s.state["pending"] = dict(pend)
        asyncio.run(self.s._autopilot_fire())
        self.assertTrue(self.s.state["autopilot"], "窗外的老回退不算数 ⇒ 托管必须继续开着")
        self.assertEqual(len(started), 1, "慢循环必须照常回退")
        self.assertEqual(len(self.s.state["auto_rollback_times"]), 1,
                         "窗口外的老时刻要剪掉、刚落的那一笔要记上 —— 这是记帐那半的判据")

        # ② 自旋：窗内已经 4 条 ⇒ 关掉托管、不再回退、不起新链、黄灯留给用户
        now = time.time()
        self.s.state["auto_rollback_times"] = [now, now, now, now]
        self.s.state["autopilot"] = True
        self.s.state["autopilot_armed"] = True
        self.s.state["pending"] = dict(pend)
        before = len(started)
        asyncio.run(self.s._autopilot_fire())
        self.assertFalse(self.s.state["autopilot"], "自旋必须自动关掉托管")
        self.assertFalse(self.s.state["autopilot_armed"], "armed 也要一起收掉")
        self.assertEqual(len(started), before, "判自旋时不许再起链")
        self.assertIsNotNone(self.s.state["pending"], "黄灯要留给用户，不能替他把待决策项收走")

    def test_the_spin_guard_survives_a_new_run(self):
        """闸的**跨 run** 记忆：`run_all` 每次开头都会把一堆内存态清掉，`auto_rollback_times`
        绝不能在里面 —— 清掉就等于没闸（每次回退都起一条新链，新链一清，回退→挂起→回退
        就成了无限循环：最坏的形态是 30 秒内起 22 条链、194 次 agent 调用）。

        判据用 AST 取 `run_all` 函数体里所有 `state[...] = ...` 的赋值**目标键**：
          · 正对照：它**必须**清 `fix_rounds`（找不到就说明这个探针压根没定位到清理段，
            那种情况下"没找到 auto_rollback_times"是假绿 —— 先让正对照红）；
          · 待验项：它**不许**清 `auto_rollback_times`。
        把清理行搬进 `run_all` 即变红。
        """
        tree = ast.parse((PROJECT / "lib/web/server.py").read_text(encoding="utf-8-sig"))
        fn = next((n for n in ast.walk(tree)
                   if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                   and n.name == "run_all"), None)
        self.assertIsNotNone(fn, "找不到 run_all ⇒ 探针失效")
        keys = set()
        for node in ast.walk(fn):
            if isinstance(node, ast.Assign):
                for t in node.targets:
                    if (isinstance(t, ast.Subscript) and isinstance(t.value, ast.Name)
                            and t.value.id == "state" and isinstance(t.slice, ast.Constant)):
                        keys.add(t.slice.value)
        self.assertIn("fix_rounds", keys,
                      "正对照失败：run_all 里没找到清理段 ⇒ 这个探针是瞎的，别信它的绿")
        self.assertNotIn("auto_rollback_times", keys,
                         "run_all 不许清 auto_rollback_times —— 清了自旋闸就等于没有")

    def test_advisory_badge_is_dropped_once_the_gate_passes(self):
        """门禁 **PASS 之后**不该再挂「还有 N 条建议」的角标。

        判据：那一行已经是 ✅，旁边还写"还有 13 件要不要做"是自相矛盾的；而该做的机器侧在
        **决策那一刻**就折进下游阶段的提示里了，原文仍在 RUBRIC_REVIEW.md 与 HIL 面板上。
        反面也要钉住：门禁**没过**时角标必须留着（那是唯一的"要不要花成本做"入口）。
        """
        adv = [{"id": "RB-7", "category": "presentation", "fix": "把页边距那句对齐",
                "cost": "小"}]
        self._resume_with_rubric_verdict({
            "before": {"status": "NEEDS_FIX", "reason": "paper_repair_required", "target": "fix",
                       "issues": [{"id": "R-1", "category": "claim", "tier": "must"}],
                       "advisories": adv},
            "after": {"status": "PASS", "reason": "", "issues": [], "advisories": adv}})
        self.assertTrue(self.s.state["run_completed"], self.s.state["halt_reason"])
        self.assertNotIn("rubric", self.s.state["adv_by_stage"],
                         "门禁已经 PASS 且只剩可选建议 ⇒ 不该再挂角标")

    def test_hard_deferred_advisories_keep_the_badge_and_are_not_called_optional(self):
        """`advisories` 里**混着两种东西**，投递时必须分开说。

        `_rubric_route` 会把「目标阶段排在门禁之后」的**硬项**降级进 `advisories`（它们此刻
        确实修不了，放行并留痕是对的）。所以一批建议里可能同时有 `severity=hard, tier=must`
        的项 —— 例如「figures/fig_roadmap.content.json 里那 10 处含内部词的图内文字」
        （内部词泄漏进图，评委直接看得见）与「交付 PDF 在标题层认不出稳健性检验模块」。
        若把整批都写成「可选建议、按成本决定是否落实」，红线项就被说成可以不做；
        若角标在 PASS 时整批撤掉，这些条目再没有任何人看得到。

        判据：① 必做项在门禁 PASS 之后**仍留角标**（可选项才撤）；
              ② 折进下游阶段的提示里**分段**写，必做段点明"必须落实"、且在可选段之前。
        """
        hard = {"id": "RB-6", "severity": "hard", "tier": "must", "category": "presentation",
                "fix": "图里那 10 处含内部词的图内文字要改"}
        opt = {"id": "RB-7", "severity": "soft", "tier": "optional", "category": "presentation",
               "fix": "页边距那句对齐"}
        prompts = {}

        def spy(prompt, sid):
            prompts.setdefault(sid, []).append(prompt)

        self._resume_with_rubric_verdict(
            {"before": {"status": "NEEDS_FIX", "reason": "paper_repair_required", "target": "fix",
                        "issues": [{"id": "R-1", "category": "claim", "tier": "must"}],
                        "advisories": [hard, opt]},
             "after": {"status": "PASS", "reason": "", "issues": [], "advisories": [hard, opt]}},
            spy=spy)
        self.assertTrue(self.s.state["run_completed"], self.s.state["halt_reason"])
        kept = self.s.state["adv_by_stage"].get("rubric") or []
        self.assertEqual([a["id"] for a in kept], ["RB-6"],
                         "PASS 之后角标只该留必做项（RB-6），可选项（RB-7）撤掉")
        # 折进 ⑭ 的提示：两段分开，必做段在前，且不许把必做项说成"可选"
        txt = "\n".join(prompts.get("format") or [])
        self.assertIn("RB-6", txt, "必做延后项必须投递给 ⑭")
        self.assertIn("RB-7", txt, "可选项也要照旧投递（只是措辞不同）")
        i_must, i_opt = txt.find("必做"), txt.find("可选建议")
        self.assertNotEqual(i_must, -1, "必做段没写出来")
        self.assertNotEqual(i_opt, -1, "可选段没写出来")
        self.assertLess(i_must, i_opt, "必做段必须排在可选段之前（先看到要紧的）")
        must_seg = txt[i_must:i_opt] if i_must < i_opt else txt[i_must:]
        self.assertNotIn("可选", must_seg, "必做段里不许出现「可选」——这正是原缺陷")
        self.assertIn("必须落实", must_seg)

    def test_advisory_badge_survives_while_the_gate_still_fails(self):
        """门禁没过 ⇒ 角标必须留着（要靠它按成本决定做不做）。"""
        adv = [{"id": "RB-8", "category": "presentation", "fix": "补一次符号表引用", "cost": "中"}]
        self.install_successful_runner(failures={"rubric": 1})
        self.s._gate_decision = lambda st: (
            {"status": "NEEDS_FIX", "reason": "boom", "target": "write",
             "issues": [{"id": "R-9", "category": "claim", "tier": "must"}], "advisories": adv}
            if st["id"] == "rubric"
            else {"status": "PASS", "reason": "", "issues": [], "advisories": []})
        asyncio.run(self.s.run_all())
        self.assertFalse(self.s.state["run_completed"], "这一轮应当停在 rubric")
        self.assertEqual(self.s.state["adv_by_stage"].get("rubric"), adv,
                         "门禁没过时角标不该被撤掉")

    def test_rubric_recheck_tells_the_judge_to_go_incremental(self):
        """⑬ 修完再回 ⑫ 重判，必须是**增量**复评，而不是从零重打整份评分标。

        素材本来就都在：回执、裁决、`state["fix_required"]`（上一轮点名要 ⑬ 处置的判词 id）
        全在盘上 / 内存里，什么都没删。但只有素材不够 —— `_back_to_judge` 把 index 指回 ⑫ 后，
        ⑫ 的输入指纹因 `paper/` 被 ⑬ 改过而失配 ⇒ 仍会从零重打一遍。
        判据：复评轮必须带上增量提示 —— 点名要复核的判词 id + 指向 `reports/_REVISION_DIFF.md`，
        外加两条护栏（仍须给完整 status/逐项打分；新问题照旧报、该 FAIL 就 FAIL）。
        """
        prompts = []

        def spy(prompt, sid):
            if sid == "rubric":
                prompts.append(prompt)

        self._resume_with_rubric_verdict(
            {"before": {"status": "NEEDS_FIX", "reason": "paper_repair_required", "target": "fix",
                        "issues": [{"id": "R-7", "category": "claim", "tier": "must"}],
                        "advisories": []},
             "after": {"status": "PASS", "reason": "", "issues": [], "advisories": []}},
            spy=spy)
        # 首轮里 rubric 故意失败一次 ⇒ run_stage 会重试，所以首评可能占 2 条提示。
        # 判据放在**最后一条**上：带复评提示的必须只有它。多留这种余量是故意的 ——
        # 钉的是"复评轮带提示"，不是"第一轮恰好调了几次"。
        self.assertGreaterEqual(len(prompts), 2, f"应有首评 + 一次复评，实际 {len(prompts)}")
        for i, p in enumerate(prompts[:-1]):
            self.assertNotIn("复评", p, f"第 {i + 1} 条不是复评轮，不该带复评提示")
        again = prompts[-1]
        for needle in ("复评", "走增量", "R-7", "_REVISION_DIFF.md", "完整", "照旧报"):
            self.assertIn(needle, again, f"复评提示里缺 {needle!r}")

    def test_fix_must_hand_back_a_disposition_for_every_verdict(self):
        """13Repair-by-rubric-verdict 交不出逐条处置表 → 打回。

        没有这道对账，一份「什么都没做、也没说为什么」的报告，与一份「逐条核过、
        两条判词被证伪所以没改」的报告，在驱动眼里**完全一样**；而这两者对下一步的
        意义正好相反（后者该收手，前者该重试）。
        """
        calls = self._resume_with_rubric_verdict(
            {"before": {"status": "NEEDS_FIX", "reason": "paper_repair_required", "target": "fix",
                        "issues": [{"id": "R-3", "category": "claim", "tier": "must"}],
                        "advisories": []},
             "after": {"status": "PASS", "reason": "", "issues": [], "advisories": []}},
            strict=True)
        self.assertIn("fix", calls, f"fix 应已执行，实际 {calls}")
        self.assertFalse(self.s.state["run_completed"], "缺处置表不该收口")
        self.assertIn("逐条处置", self.s.state["halt_reason"])

    def test_fix_is_skipped_when_rubric_has_no_verdicts(self):
        """rubric 明确通过（只剩轻微项）→ 13Repair-by-rubric-verdict 无事可做，跳过，省一次 agent 调用。

        反向对照在 `test_rubric_paper_side_verdict_runs_fix_then_rechecks`：
        有 must 判词时 fix 必须跑。
        """
        calls = self._resume_with_rubric_verdict(
            {"before": {"status": "PASS", "reason": "only_optional_remain", "issues": [],
                        "advisories": [{"id": "R-9", "category": "claim", "cost": "约 1 小时"}]},
             "after": {"status": "PASS", "reason": "", "issues": [], "advisories": []}})
        self.assertNotIn("fix", calls, f"rubric 没有 must/fatal 判词时不该跑 fix，实际 {calls}")
        self.assertEqual(self.s.state["stages"]["fix"], "done(skip)")
        self.assertTrue(self.s.state["run_completed"], self.s.state["halt_reason"])

    def test_rubric_model_defect_halts_instead_of_running_fix(self):
        """反向对照：判词里混有模型类时**整单回退**，不许走 fix 那条正向路。

        否则一份「模型不适配本题」会被 13Repair-by-rubric-verdict 改成一段漂亮话交上去。
        """
        model_verdict = {"status": "NEEDS_FIX", "reason": "content_repair_required",
                         "target": "analysis",
                         "issues": [{"id": "r1", "category": "constraint_model", "tier": "must"}],
                         "advisories": []}
        calls = self._resume_with_rubric_verdict(
            {"before": model_verdict, "after": model_verdict})
        self.assertEqual(calls, ["rubric"], f"模型类判词应就地停机，实际 {calls}")
        self.assertFalse(self.s.state["run_completed"])
        self.assertEqual(self.s.state["stages"]["rubric"], "awaiting_user")

    def test_pause_halts_into_pending_with_an_exit(self):
        """「暂停」从当前阶段停下并**转黄灯** —— 把出口留好。

        只有「停止」一种的话，一停到底、不给决策面板：链停在半路、产物停在半路，
        人只能干看着，想接着做只能重新点「开始全链」再自己猜从哪续。
        暂停与「接下来怎么办」是同一处入口；要硬停用「停止」。
        """
        def after(sid):
            if sid == "code":
                self.s.state["stopping"] = True
                self.s.state["pause_to_halt"] = True
        self.install_successful_runner(after=after)
        asyncio.run(self.s.run_all())

        self.assertFalse(self.s.state["run_completed"])
        self.assertTrue(self.s.state["halt_gate"], "暂停应转黄灯，而不是硬停")
        p = self.s.state["pending"]
        self.assertEqual(p["kind"], "paused")
        self.assertIn("rollback", p["actions"])            # 黄灯上要有出口
        self.assertIn("awaiting_user", self.s.state["stages"].values())

    def test_stop_is_a_hard_stop_that_clears_the_panel(self):
        """「停止」是硬停：黄灯若亮着就一并收起，状态落成 stopped。

        与暂停的分工 —— 暂停把出口留好（停在这儿还能接着做），停止不留。
        """
        self.s.state["halt_gate"] = True
        self.s.state["pending"] = {"stage": "code", "kind": "paused"}
        self.s.state["stages"]["code"] = "awaiting_user"
        asyncio.run(self.s.stop())
        self.assertFalse(self.s.state["halt_gate"])
        self.assertIsNone(self.s.state["pending"])
        self.assertEqual(self.s.state["stages"]["code"], "stopped")
        self.assertFalse(self.s.state["pause_to_halt"], "硬停不该留下暂停信号")

    def test_pause_on_a_live_chain_asks_for_a_halt(self):
        """链在跑、没有黄灯时按暂停 → 只**请求**转黄灯（下个检查点才落），不立刻硬停。"""
        self.s.state["running"] = True
        self.s.state["halt_gate"] = False
        self.s.state["pending"] = None
        asyncio.run(self.s.pause())
        self.assertTrue(self.s.state["stopping"])
        self.assertTrue(self.s.state["pause_to_halt"])

    def test_pause_refuses_when_nothing_is_running(self):
        self.s.state["running"] = False
        with self.assertRaises(Exception):
            asyncio.run(self.s.pause())

    def _pretend_same_problem(self):
        """把 `workspace.json` 写成与当前输入摘要一致 ⇒ `_prepare_workspace` 判「不是换题」。

        真实的「同一题续跑」就是这个状态（`_source_digest` 没变 ⇒ 既不轮转、也不搬工作区）。
        凡是**预置**了一批文件（例如上一轮的返修回执 `runtime/quality/feedback/`）再跑整链的
        用例，都必须先把自己摆到这个状态 —— 否则那些文件会被当成「上一题的东西」搬走
        （换题时搬走返修回执是**刻意**的，见 `_prepare_workspace`）。
        """
        p = self.s.LOG_DIR / "quality" / "workspace.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({"source_digest": self.s._source_digest(),
                                 "run_id": "test", "problem_id": "2026A"},
                                ensure_ascii=False), encoding="utf-8")

    def _touch(self, *rels):
        for rel in rels:
            p = self.root / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("x", encoding="utf-8")

    def test_redo_stash_lands_in_one_time_named_folder(self):
        """回退暂存落 `<选定目录>/cache/<题目标识_日期_时间>/` —— **一个**时间文件夹装全部残留。

        每个 rel 各占一个 `cache/<ts>_<名>/` 会散成一堆；从 cache 里读回时得先猜
        哪几个属于同一轮、哪几个是同一阶段。
        """
        self._touch("paper/main.tex", "reports/VERIFY_REPORT.md")
        self.s._redo_from("write")
        cache = self.root / "产物" / "cache"
        names = [p.name for p in cache.iterdir()]
        self.assertEqual(len(names), 1, f"应只有一个时间文件夹，实际 {names}")
        self.assertTrue(names[0].startswith("2026."), names[0])
        self.assertNotIn(":", names[0], "Windows 保留字符不能出现在目录名里")
        stamp = cache / names[0]
        # **按阶段分文件夹**：从 cache 里一眼看出退到了哪几步、每步留下什么。
        #   拍平成 reports_xxx.md / paper/ 就看不出谁是谁了。
        self.assertTrue((stamp / "论文撰写/paper/main.tex").is_file())
        self.assertTrue((stamp / "验收/VERIFY_REPORT.md").is_file())
        self.assertFalse((self.root / "paper").exists(), "是移动不是复制")

    def test_stash_does_not_create_empty_stage_folders(self):
        """回退会把「该阶段起」的**每一段**都试搬一次，而大多数阶段这次没产物。

        预建目录的话 cache 里会多出一堆空文件夹（一次回退能建十几个空目录，
        只有一两个真装了东西）—— 从 cache 里读回时反而看不出哪几步真有内容。
        """
        self._touch("paper/main.tex")
        self.s._redo_from("write")
        cache = self.root / "产物" / "cache"
        stamp = next(iter(cache.iterdir()))
        self.assertTrue((stamp / "论文撰写/paper/main.tex").is_file())
        empty = [p.name for p in stamp.iterdir() if p.is_dir() and not any(p.iterdir())]
        self.assertEqual(empty, [], f"不该有空目录：{empty}")

    # ---- 换题轮转：两个「最新」指针 ----

    def _pointers(self):
        root = self.root / "产物"
        return (root / "提交作品" / "最新作品", root / "各阶段产物" / "最新产物")

    def _seed_pointers(self):
        sub, stg = self._pointers()
        (sub).mkdir(parents=True, exist_ok=True)
        (sub / "正文.pdf").write_text("final", encoding="utf-8")
        (stg / "建模设计").mkdir(parents=True, exist_ok=True)
        (stg / "建模设计/A.md").write_text("x", encoding="utf-8")
        return sub, stg

    def test_rotation_skips_empty_pointers_and_builds_the_skeleton(self):
        """首次运行 / 手工建的空样板 → **不轮转**，只把骨架建出来。

        空目录被归档会产出一堆空档案；而「最新」这两个名字本来就是骨架，
        首次跑时它们还不存在，谈不上"归档上一题"。
        """
        info = self.s._rotate_pointers("首次", "2026A")
        self.assertEqual(info["rotated"], [], "两个指针都还不存在，不该有东西被归档")
        sub, stg = self._pointers()
        self.assertTrue(sub.is_dir() and stg.is_dir(), "骨架要建出来")
        self.assertEqual(list(sub.iterdir()), [])
        # 手工建的那种「已存在的空目录」：同样不轮转、不留空归档
        info2 = self.s._rotate_pointers("空样板", "2026A")
        self.assertEqual(info2["rotated"], [])
        self.assertEqual(list(stg.iterdir()), [])

    def test_rotation_uses_one_and_the_same_name_on_both_pointers(self):
        """换题归档：两个「最新」改成**同一个** `<题目标识_日期_时间>/`，再建两个空的。

        同名是有意义的 —— 从产物目录里一眼就能把「这一题的提交件」与
        「这一题的阶段产物」对起来（`unique_boundary_name` 必须同时查两个 parent，
        各查各的会让两边算出不同的名字）。
        """
        sub, stg = self._seed_pointers()
        info = self.s._rotate_pointers("换题", "2026A")
        name = info["name"]
        self.assertTrue(name.startswith("2026A_"), name)
        # `rotated` 报的是**归档落点**（前端要显示「归档到哪」），两处同一个名字
        self.assertEqual({Path(p).name for p in info["rotated"]}, {name})
        self.assertEqual(len(info["rotated"]), 2)
        self.assertEqual((sub.parent / name / "正文.pdf").read_text(encoding="utf-8"), "final")
        self.assertTrue((stg.parent / name / "建模设计/A.md").is_file())
        self.assertTrue(sub.is_dir() and list(sub.iterdir()) == [], "指针要建回且是空的")
        self.assertTrue(stg.is_dir() and list(stg.iterdir()) == [])

    def test_rotation_rolls_back_when_the_second_pointer_cannot_be_moved(self):
        """任一改名失败 ⇒ 已改的**改回来** + 抛 RotationBlocked，不留半截状态。

        不能靠"让 `Path.rename` 抛 OSError"来造失败：`rotate_pointer` 把 OSError
        当跨盘信号、会退到 `copytree` 兜底（那是它的正常功能）。所以这里直接在
        `rotate_pointer` 这一层让第二次调用失败 —— 钉的正是 `_rotate_pointers` 的回滚。
        """
        import lib.delivery.core as core
        sub, stg = self._seed_pointers()
        real = core.rotate_pointer
        seen = []

        def flaky(pointer, dest_root, name):
            seen.append(Path(pointer).name)
            if len(seen) == 2:                     # 第二个指针那次失败
                raise ValueError("归档目标已存在：<模拟被占用>")
            return real(pointer, dest_root, name)

        with unittest.mock.patch.object(core, "rotate_pointer", flaky):
            with self.assertRaises(self.s.RotationBlocked):
                self.s._rotate_pointers("换题", "2026A")
        self.assertTrue((sub / "正文.pdf").is_file(), "第一处改名必须被回滚回原地")
        self.assertTrue((stg / "建模设计/A.md").is_file(), "第二处原地未动")
        self.assertEqual(sorted(p.name for p in (sub.parent).iterdir()
                                if not p.name.startswith(".")),
                         ["最新作品"], "第一处不该留下半份归档")

    def test_rotation_uses_the_first_free_name_when_it_is_taken(self):
        """撞名（例如用户样板里那个同名空目录）→ 退到 `-2`，且**不覆盖**已有的。"""
        sub, _ = self._seed_pointers()
        taken = sub.parent / "2026A_2026.9.24_10.25.03"
        taken.mkdir(parents=True, exist_ok=True)
        (taken / "别动我.txt").write_text("keep", encoding="utf-8")
        info = self.s._rotate_pointers("换题", "2026A")
        self.assertNotEqual(info["name"], taken.name)
        self.assertEqual((taken / "别动我.txt").read_text(encoding="utf-8"), "keep")

    def test_rotation_adopts_a_leftover_from_an_interrupted_package(self):
        """`package()` 崩在两次 rename 之间会留下 `.<指针名>.old-<uuid8>` —— 收编它。

        那份残留内容是完整的（是上一份打包好的提交件）；不认它就会永久留在盘上。
        """
        sub, _ = self._pointers()
        sub.parent.mkdir(parents=True, exist_ok=True)
        leftover = sub.parent / ".最新作品.old-deadbeef"
        leftover.mkdir()
        (leftover / "正文.pdf").write_text("orphan", encoding="utf-8")
        info = self.s._rotate_pointers("换题", "2026A")
        self.assertTrue((sub.parent / info["name"] / "正文.pdf").is_file(),
                        "残留应该被收编并一起归档")

    def test_rotation_adopts_the_newest_leftover_and_clears_building_junk(self):
        """打包崩溃留下的中间件：收编**最新**那份、清掉半成品、别把文件当目录用。

        三种错法：
        ① 取 `sorted()[0]` = 最旧的一份 ⇒ 把很旧的包当成本轮的归档边界，
           而更新的那份永远躺在隐藏目录里没人看得见；
        ② `.<指针名>.building-*`（还在建的半成品）永远没人收；
        ③ 残留若是**文件**，`rename` 上去会把指针路径变成文件 ⇒ 之后 `mkdir` 抛
           `FileExistsError`，绕过 `RotationBlocked` 的语义。
        """
        import os
        sub, _ = self._pointers()
        parent = sub.parent
        parent.mkdir(parents=True, exist_ok=True)
        old = parent / ".最新作品.old-aaaa"
        old.mkdir()
        (old / "正文.pdf").write_text("旧", encoding="utf-8")
        new = parent / ".最新作品.old-zzzz"
        new.mkdir()
        (new / "正文.pdf").write_text("新", encoding="utf-8")
        os.utime(old, (1000, 1000))
        os.utime(new, (2000, 2000))
        junk = parent / ".最新作品.building-dead"
        junk.mkdir()
        (junk / "半成品").write_text("x", encoding="utf-8")
        (parent / ".最新作品.old-afile").write_text("我是文件", encoding="utf-8")

        info = self.s._rotate_pointers("换题", "2026A")
        self.assertFalse(junk.exists(), "打包半成品没被清掉")
        self.assertTrue(sub.is_dir(), "指针必须还是个**目录**")
        self.assertEqual((parent / info["name"] / "正文.pdf").read_text(encoding="utf-8"), "新",
                         "收编的该是**最新**那份残留")

    def test_a_leftover_is_archived_even_when_the_pointer_exists(self):
        """指针还在时，崩溃残留也必须被收走。

        若 `if pointer.exists(): continue` 直接跳过 ⇒ 一份**完整的旧提交包**永久留在
        `.最新作品.old-<uuid8>/` 里：连一行日志都没有，而 dot 目录面板看不见。
        """
        sub, _ = self._pointers()
        parent = sub.parent
        sub.mkdir(parents=True, exist_ok=True)
        (sub / "正文.pdf").write_text("这一轮的", encoding="utf-8")
        leftover = parent / ".最新作品.old-deadbeef"
        leftover.mkdir()
        (leftover / "正文.pdf").write_text("上一轮的残留", encoding="utf-8")

        info = self.s._rotate_pointers("换题", "2026A")
        self.assertFalse(leftover.exists(), "残留还留在隐藏目录里 —— 面板看不见")
        archived = {p.read_text(encoding="utf-8")
                    for p in (parent / info["name"]).rglob("正文.pdf")}
        self.assertEqual(archived, {"这一轮的", "上一轮的残留"},
                         "残留该和本轮内容一起进归档")

    def test_switching_problem_uses_the_old_id_and_files_the_originals(self):
        """换题归档的两条口径：

        ① 归档名用**上一轮记下的**题目标识 —— `/api/start` 是**先落盘新 problem_id
           再起链**的，用当前配置会把旧题的产物装进新题的名字里；
        ② 工作区原件落进 `cache/<同一个名字>/工作区原件/`，与两个「最新」的归档同名 ——
           从 cache 里一眼能看出「这份原件属于哪一题的哪一轮」。
        """
        (self.root / "request").mkdir(parents=True, exist_ok=True)
        (self.root / "config").mkdir(parents=True, exist_ok=True)
        (self.root / "request/problem.md").write_text("A 题", encoding="utf-8")
        self.s._save_delivery_config("", "2026A")
        self.s._prepare_workspace()                    # 首次：记下 digest 与 2026A（此时无指针可归档）

        sub, _ = self._seed_pointers()                 # 题 A 跑出了东西
        (self.root / "request/problem.md").write_text("B 题", encoding="utf-8")
        self.s._save_delivery_config("", "2026B")      # 模拟 /api/start 先存新 pid
        (self.root / "reports").mkdir(exist_ok=True)
        (self.root / "reports/RESULTS_REPORT.md").write_text("x", encoding="utf-8")

        self.s._prepare_workspace()                    # 换题

        archived = [p.name for p in sub.parent.iterdir()
                    if p.is_dir() and not p.name.startswith(".")]
        self.assertIn("最新作品", archived, "指针要建回来")
        stamp = [x for x in archived if x != "最新作品"]
        self.assertEqual(len(stamp), 1, f"该恰好有一份归档，实际 {archived}")
        self.assertTrue(stamp[0].startswith("2026A_"),
                        f"归档名用了新题的标识：{stamp[0]}")
        # 工作区原件落进同名的 cache 子目录
        self.assertTrue(
            (self.root / "产物/cache" / stamp[0] / "工作区原件/reports/RESULTS_REPORT.md").is_file(),
            "工作区原件没进 cache/<同名>/工作区原件/")
        self.assertFalse((self.root / "reports/RESULTS_REPORT.md").exists(),
                         "原件是移动不是复制")
        self.assertTrue((self.root / "reports").is_dir(),
                        "reports/ 本身要重建 —— 后续阶段得往这里写")

    # ---- 各阶段产物：每阶段跑完镜像一份 ----

    def test_stage_snapshot_mirrors_overwrites_and_deletes(self):
        """幂等 = **对齐**，不是累加：源改了就更新、源删了就跟着删、`__pycache__` 不进来。

        累加会让上轮画过、这轮不画的图继续挂着 —— 看起来像现在的产物，正撞
        「不冒充本轮成功」那条纪律。
        """
        dest = self.s._stage_dir() / "编码计算"
        (self.root / "code/outputs").mkdir(parents=True, exist_ok=True)
        (self.root / "code/__pycache__").mkdir(parents=True, exist_ok=True)
        (self.root / "code/__pycache__/x.pyc").write_bytes(b"x")
        (self.root / "code/outputs/a.json").write_text("a", encoding="utf-8")

        self.s._mirror_paths(["code"], dest)
        self.assertTrue((dest / "code/outputs/a.json").is_file())
        self.assertTrue((dest / "code/__pycache__").exists() is False,
                        "__pycache__ 是解释器实现物，不该被镜像")

        (self.root / "code/outputs/b.json").write_text("b", encoding="utf-8")
        (self.root / "code/outputs/a.json").unlink()
        self.s._mirror_paths(["code"], dest)
        self.assertTrue((dest / "code/outputs/b.json").is_file(), "新增的没镜像过去")
        self.assertFalse((dest / "code/outputs/a.json").exists(), "源删了，目标该跟着删")
        # 源整条没了 → 目标那条也删掉
        import shutil as _sh
        _sh.rmtree(self.root / "code")
        self.s._mirror_paths(["code"], dest)
        self.assertFalse((dest / "code").exists(), "源没了，目标该跟着删")

    def test_stage_snapshot_writes_a_marker_and_skips_when_nothing_is_on_disk(self):
        """一份产都没有 → **不建目录**（同 `_stash_paths` 的纪律）；有则落可机读的标记。"""
        st = next(s for s in self.s.STAGES if s["id"] == "analysis")
        self.assertIsNone(self.s._snapshot_stage(st, None))
        self.assertFalse(self.s._stage_dir().exists(), "一条产物都不在盘上，不该建空目录")

        (self.root / "reports").mkdir(parents=True, exist_ok=True)
        (self.root / "reports/ANALYSIS_MODELING_REPORT.md").write_text("v1", encoding="utf-8")
        self.s._snapshot_stage(st, None)
        marker = self.s._stage_dir() / "建模设计" / ".snapshot.json"
        self.assertTrue(marker.is_file())
        data = json.loads(marker.read_text(encoding="utf-8"))
        self.assertEqual(data["stage"], "analysis")
        self.assertTrue(data["complete"])
        self.assertEqual(data["failed"], [])

    def test_stage_snapshot_picks_figures_up_from_the_manifest_diff(self):
        """`figures/` 不在 `ARTIFACTS` 里（那张表自述"不是穷举清单"）——
        图的归属靠**登记表自己的差分**认领，不靠一张手维护的「阶段 → 图」映射。
        """
        from lib.visualization.evidence import write_json
        (self.root / "figures").mkdir(parents=True, exist_ok=True)
        (self.root / "figures/make_demo.py").write_text("# script\n", encoding="utf-8")
        for name in ("fig_a.png", "fig_a.svg", "fig_b.png"):
            (self.root / "figures" / name).write_bytes(name.encode())
        write_json(self.root / "figures/manifest.json", {
            "schema_version": 1, "figures": {
                "fig_a": {"script": "figures/make_demo.py"},
                "fig_b": {"script": "figures/make_demo.py"}}})
        before = self.s._figure_index()
        self.assertIsNotNone(before)

        manifest = json.loads((self.root / "figures/manifest.json").read_text(encoding="utf-8"))
        manifest["figures"]["fig_a"]["claim"] = "这一轮重渲过它"   # 条目变了 = 重渲了
        write_json(self.root / "figures/manifest.json", manifest)

        changed, keys = self.s._figure_paths_changed(before)
        self.assertEqual(keys, ["fig_a"], "只有条目变了的那个 key")
        self.assertIn("figures/fig_a.png", changed)
        self.assertIn("figures/fig_a.svg", changed, "同一个 key 的其它扩展名要一起收")
        self.assertIn("figures/make_demo.py", changed, "它的脚本也要一起收")
        self.assertNotIn("figures/fig_b.png", changed, "没变的图不该跟着搬")

        (self.root / "figures/manifest.json").unlink()
        self.assertEqual(self.s._figure_paths_changed(before), ([], []),
                         "登记表读不到时，宁可少镜像也不瞎猜")

    def test_a_locked_file_does_not_abort_the_alignment_pass(self):
        """对齐删除碰到被占用的文件 ⇒ 记下来继续，**不许**让整次镜像半途作废。

        若 `p.unlink()` 不兜异常：一个被占文件就把异常抛出 `_mirror_paths`、
        被 `_snapshot_stage` 外层 try 吞掉 —— 结果是「镜像只做了一半，而盘上留着
        上一轮的 `.snapshot.json` 继续自称 complete: true」，比明说没做全更糟。
        """
        dest = self.s._stage_dir() / "编码计算"
        (dest / "code/outputs").mkdir(parents=True, exist_ok=True)
        (dest / "code/outputs/stale.json").write_text("上轮留下的", encoding="utf-8")
        (self.root / "code/outputs").mkdir(parents=True, exist_ok=True)
        (self.root / "code/outputs/keep.json").write_text("新", encoding="utf-8")

        with open(dest / "code/outputs/stale.json", "rb") as held:
            held.read(1)
            failed = self.s._mirror_paths(["code"], dest)
        self.assertTrue((dest / "code/outputs/keep.json").is_file(),
                        "新文件该镜像过去 —— 删旧失败不该拖停整批")
        self.assertTrue(any("stale.json" in f for f in failed),
                        f"删不掉的旧文件该被如实记下来：{failed}")

    def test_the_marker_stays_incomplete_if_the_mirror_blows_up(self):
        """镜像中途崩掉 ⇒ 标记必须停在 `complete: false`。

        否则盘上留的是**上一轮**那份 `complete: true`，读起来像这一轮做全了。
        """
        st = next(s for s in self.s.STAGES if s["id"] == "analysis")
        (self.root / "reports").mkdir(parents=True, exist_ok=True)
        (self.root / "reports/ANALYSIS_MODELING_REPORT.md").write_text("v", encoding="utf-8")
        marker = self.s._stage_dir() / "建模设计" / ".snapshot.json"
        self.s._snapshot_stage(st, None)
        self.assertTrue(json.loads(marker.read_text(encoding="utf-8"))["complete"])

        with unittest.mock.patch.object(self.s, "_mirror_paths",
                                        side_effect=RuntimeError("模拟镜像炸了")):
            self.s._snapshot_stage(st, None)
        data = json.loads(marker.read_text(encoding="utf-8"))
        self.assertFalse(data["complete"], "崩了还留着 complete: true —— 读起来像这轮做全了")

    def test_retired_figures_are_dropped_from_the_mirror(self):
        """图从登记表退役/改名 ⇒ 展示区那份必须跟着删。

        「幂等 = 对齐，不是累加」对 `figures/` 得单独实现：逐 rel 对齐盖不到图
        （图不在 `ARTIFACTS` 里），于是一张退役的图会永远挂在展示区。
        """
        from lib.visualization.evidence import write_json
        (self.root / "figures").mkdir(parents=True, exist_ok=True)
        (self.root / "figures/fig_a.png").write_bytes(b"a")
        (self.root / "figures/fig_b.png").write_bytes(b"b")
        manifest = self.root / "figures/manifest.json"
        before = self.s._figure_index()                     # 空登记表 → 两条都算「新增」
        write_json(manifest, {"schema_version": 1, "figures": {"fig_a": {}, "fig_b": {}}})
        st = next(s for s in self.s.STAGES if s["id"] == "drawio")
        self.s._snapshot_stage(st, before)
        dest = self.s._stage_dir() / "技术路线图"
        self.assertTrue((dest / "figures/fig_a.png").is_file())

        write_json(manifest, {"schema_version": 1, "figures": {"fig_b": {}}})   # fig_a 退役
        self.s._snapshot_stage(st, before)
        self.assertFalse((dest / "figures/fig_a.png").exists(), "退役的图还挂在展示区里")
        self.assertTrue((dest / "figures/fig_b.png").is_file(), "没退役的不许被误删")

    def test_figure_files_are_found_via_the_registrys_artifacts_field(self):
        """文件名与图键不同名时，靠登记表自己的 `artifacts` 收进来。

        只按 `glob(f"{key}.*")` 收会**静默漏掉**这类图 —— 登记表才是权威。
        """
        from lib.visualization.evidence import write_json
        (self.root / "figures").mkdir(parents=True, exist_ok=True)
        (self.root / "figures/图一.png").write_bytes(b"x")
        write_json(self.root / "figures/manifest.json", {"schema_version": 1, "figures": {
            "fig_one": {"artifacts": ["figures/图一.png"]}}})
        self.assertIn("figures/图一.png", self.s._figure_rels_for(["fig_one"]))

    def test_figure_attribution_reads_the_durable_file(self):
        """阶段↔图 的**归属权威**在 `runtime/` 下、不随快照被搬走。

        归属若只存在 `.snapshot.json` 里，而**换题归档**与**回退**都会把那个目录
        整份搬走 ⇒ 纯复用的一轮里该阶段的图整批不进展示区，**且盘上没有任何标记说明漏了**
        （`missing: []` + `complete: true` 读起来像"本来就没有图"）。

        直接钉机制，**不绕道「搬走目录再看展示区」** —— 那种写法是**恒真的**
        （差分为空时只要 `fig_before` 传得不对就会重新镜像，与有没有持久归属无关）。
        这里反过来：**只**通过归属表告诉它该阶段有哪些图，再看它认不认。
        """
        from lib.visualization.evidence import write_json
        (self.root / "figures").mkdir(parents=True, exist_ok=True)
        (self.root / "figures/fig_a.png").write_bytes(b"a")
        write_json(self.root / "figures/manifest.json",
                   {"schema_version": 1, "figures": {"fig_a": {}}})
        st = next(s for s in self.s.STAGES if s["id"] == "drawio")
        shot = self.s._stage_dir() / "技术路线图" / "figures/fig_a.png"

        # ① 归属表里记着 ⇒ 差分为空的一轮也要把图镜像过来
        self.s._save_figure_attr({"drawio": ["fig_a"]})
        self.s._snapshot_stage(st, self.s._figure_index())      # 差分为空
        self.assertTrue(shot.is_file(),
                        "归属表里记着的图没被镜像 —— 持久归属没生效（复用了旧实现？）")

        # ② 反向守卫：归属表空着、差分也为空 ⇒ 就不该凭空多出图来
        #    （没有这条，上面那句「镜像了」可能只是差分碰巧非空造成的）
        import shutil as _sh
        _sh.rmtree(self.s._stage_dir())
        self.s._save_figure_attr({})
        self.s._snapshot_stage(st, self.s._figure_index())
        self.assertFalse(shot.exists(), "归属表空着却把图镜像过去了")

    def test_the_snapshot_hook_covers_the_reuse_paths_too(self):
        """源码级钉子：镜像挂在 `run_all` 里、且必须在「成功/复用」那道 guard **之后**。

        挂在 `run_stage` 内部的话：① 它在门禁裁决之前，会把被否的产物先摆进展示区；
        ② 它有 6 条早返回，都不是「阶段完成」；③ **16 个阶段全 `ok(skip)` 秒过时
        「最新产物」永远回填不上** —— 那条最要命（功能上线后第一次按「开始全链」就是这情形）。
        """
        src = (PROJECT / "lib/web/server.py").read_text(encoding="utf-8")
        run_all = src.split("async def run_all", 1)[1]
        # 别把动作元组写死在这里（"confirmed" 一进那个元组，这条用例就会
        #   `substring not found` 变成**假红**）—— 只锚 `if outcome not in (`。
        guard = run_all.index("if outcome not in (")
        snap = run_all.index("_snapshot_stage(stage, fig_before)")
        self.assertGreater(snap, guard, "镜像调用跑到成功 guard 前面了")
        run_stage = src.split("async def run_stage", 1)[1].split("async def run_all", 1)[0]
        self.assertNotIn("_snapshot_stage", run_stage,
                         "镜像挂进 run_stage 内部了 —— 复用路径会漏，且会把被否产物摆上展台")

    def test_the_gate_snapshot_lands_after_its_verdict(self):
        """门禁的镜像必须在**裁决之后**。

        门禁的裁决要等 `gate_result()` 才算，协议返修还会**重写裁决侧车** ——
        镜像若落在前面，展示区里留下的是「被门禁否掉的那一版产物」与
        「被取代的 UNVERIFIED 裁决」。

        光"在 `gate_result` 之后"**不够** —— 算出 `decision` 不等于裁决已处置，
        `交回上游`（`check_handback`）与 `门禁未通过` 两条出路都排在它后面好几十行。
        若在那里镜像 + 阶段性打包：`cross` 判 FAIL 的那一轮照样被摆进「各阶段产物」、
        照样收进 `提交作品/最新作品/`，而紧接着的挂起文案写着「保留草稿，**不收集为正式交付**」。
        判据因此是：门禁这一处必须落在**所有"否掉"的出路之后**（用 `rindex` 取门禁那一次，
        非门禁那次在前）。
        """
        src = (PROJECT / "lib/web/server.py").read_text(encoding="utf-8")
        run_all = src.split("async def run_all", 1)[1]
        verdict = run_all.index("verdict = gate_result(stage)")
        snap = run_all.rindex("_snapshot_stage(stage, fig_before)")
        self.assertGreater(snap, verdict, "门禁的镜像跑到裁决前面了")
        self.assertLess(run_all.index("check_handback(index)"), snap,
                        "门禁的镜像/打包跑到「交回上游」那条出路前面了 —— 被否的那版会先进展台")
        self.assertLess(run_all.index("门禁未通过（{verdict}）"), snap,
                        "门禁的镜像/打包跑到「判否」那条出路前面了 —— 被否的那版会被打包进提交件")

    def test_the_coding_stage_gets_a_longer_wall_clock_budget(self):
        """④ 的固有耗时（约 51.9 min）比全局默认上限（30 min）长，所以它要有自己的默认值。

        否则每轮 ④ **必然**弹一次超时黄灯要人点「延长」（一轮里可能点四次），
        而「🛑 停止」就在同一面板上 —— 离丢掉整段只差一次点错。
        钉住三件：④ 有自己的默认值、别的阶段不被一起抬高（那会钝掉这盏灯）、
        人的延长与协议级短上限仍然优先。
        """
        self.assertEqual(self.s._effective_limits("code")[0], self.s.STAGE_CAP_DEFAULT["code"])
        self.assertGreater(self.s.STAGE_CAP_DEFAULT["code"], self.s.RETRY_CAP_DEFAULT,
                           "④ 的默认上限不比全局大 ⇒ 这条修法没有意义")
        self.assertEqual(self.s._effective_limits("write")[0], self.s.RETRY_CAP_DEFAULT,
                         "别的阶段被一起抬高了 —— 那会把超时这盏灯钝掉")
        self.s.state["retry_cap"] = {"code": 7200}
        self.assertEqual(self.s._effective_limits("code")[0], 7200, "用户延长过就该用他的值")
        self.assertEqual(self.s._effective_limits("code", cap=900)[0], 900,
                         "协议级修复的短上限优先于一切")

    def test_stage_names_are_unique_and_filesystem_safe(self):
        """阶段中文名会被当目录名用（`各阶段产物/<名字>/`、cache 的 `<阶段>/`）——
        重名会让两个阶段的产物悄悄叠进同一个目录，找不回来。"""
        names = [s["name"] for s in self.s.STAGES]
        self.assertEqual(len(set(names)), len(names), f"阶段中文名有重复：{names}")
        for name in names:
            self.assertFalse({c for c in name if c in '\\/:*?"<>|'},
                             f"{name!r} 含 Windows 保留字符，不能当目录名")

    def test_a_partial_rebuild_does_not_delete_already_delivered_files(self):
        """整体替换 + 只收"盘上现在有的" ⇒ 一次回退之后的同步会把**已经交付的**件
        从 `最新作品/` 里删掉。

        路径：包里有完整的 `demo.html` 与运行说明.md → 回退到 ≤⑬ ⇒ `_redo_from`
        按 `ARTIFACTS[format]`/`[demo]` 把 `demo/`、`运行说明.md` 搬进 cache ⇒ 工作区一时
        没有它们 ⇒ 若照旧整体替换，交付目录里那两件**直接消失**（链若停在 ⑯ 之前就一直缺着，
        与论文末页的清单表对不上）。
        判据：允许缺项时，被跳过的项要**从旧包搬过来**（保留上一版），而不是被抹掉。
        """
        from lib.delivery.core import package

        (self.root / "paper").mkdir(parents=True, exist_ok=True)
        (self.root / "paper/main.pdf").write_bytes(b"%PDF-1.4\n" + b"x" * 50)
        (self.root / "demo").mkdir(exist_ok=True)
        (self.root / "demo/demo.html").write_text("<html>demo</html>", encoding="utf-8")
        (self.root / "运行说明.md").write_text("# 说明", encoding="utf-8")
        items = [{"path": "正文.pdf", "desc": "", "source": "paper/main.pdf"},
                 {"path": "demo.html", "desc": "", "source": "demo/demo.html"},
                 {"path": "运行说明.md", "desc": "", "source": "运行说明.md"}]
        out = self.root / "产物" / "提交作品" / "最新作品"
        package(self.root, out, items)
        self.assertTrue((out / "demo.html").is_file())

        # 回退把 demo/ 与 运行说明.md 搬走了（工作区一时没有它们）
        (self.root / "demo/demo.html").unlink()
        (self.root / "运行说明.md").unlink()
        package(self.root, out, items, allow_missing=True)
        self.assertTrue((out / "demo.html").is_file(),
                        "工作区暂时没有 ≠ 已经交付的那份要跟着消失")
        self.assertTrue((out / "运行说明.md").is_file())
        self.assertTrue((out / "正文.pdf").is_file())

    def test_the_carry_also_works_when_the_manifest_itself_was_moved_away(self):
        """回退会把 `reports/SUBMISSION_MANIFEST.json` 与 `运行说明.md` **一起**搬进 cache
        （`ARTIFACTS["format"]` 的第一声明者就是 format）⇒ 中途收走的是"临时清单 =
        盘上现在有的东西"，而 `demo.html` / 运行说明.md **连名字都没进清单** ⇒
        整体替换直接把它们从 `最新作品/` 抹掉。
        这条与"清单在、只是源缺失"那一条走的是**两扇不同的门**，所以要各钉一条。
        """
        from lib.delivery.core import package, provisional_items

        (self.root / "paper").mkdir(parents=True, exist_ok=True)
        (self.root / "paper/main.pdf").write_bytes(b"%PDF-1.4\n" + b"x" * 50)
        (self.root / "demo").mkdir(exist_ok=True)
        (self.root / "demo/demo.html").write_text("<html>d</html>", encoding="utf-8")
        (self.root / "运行说明.md").write_text("# 说明", encoding="utf-8")
        out = self.root / "产物" / "提交作品" / "最新作品"
        package(self.root, out, [{"path": "正文.pdf", "desc": "", "source": "paper/main.pdf"},
                                 {"path": "demo.html", "desc": "", "source": "demo/demo.html"},
                                 {"path": "运行说明.md", "desc": "", "source": "运行说明.md"}])
        # 回退：demo/ 与 运行说明.md 被搬走（清单也是），只剩 paper/
        (self.root / "demo").rename(self.root / "demo_moved")
        (self.root / "运行说明.md").unlink()
        package(self.root, out, provisional_items(self.root), allow_missing=True)
        self.assertTrue((out / "demo.html").is_file(),
                        "临时清单看不见它 ⇒ 必须从旧包保留（只增不减）")
        self.assertTrue((out / "运行说明.md").is_file())
        self.assertTrue((out / "正文.pdf").is_file())

    def test_the_carry_protects_the_archive_subtrees_too(self):
        """`_carry` 若只要**顶层的文件**（`p.is_file()`），`其余文件/` 这个**目录**
        就永远进不了搬运名单。可它装着 `内部报告/`、`辅助脚本/`、`正文/`、`附录/` 四棵子树，
        而 `build_plan` **只在对应源目录还在盘上时**才重建它们 —— 于是「回退把
        `paper_appendix/` 搬进 cache」这种事一发生，旧包里的 `其余文件/附录/` 就会静静消失
        （提交件那一层有 `_carry` 兜着，归档这一层没有）。

        判据两条：① 顶层**目录**也要搬；② 是**合并**不是替换 —— 这轮重建过的以新版为准，
        这轮没重建的（源目录被搬走了）从旧包补回来。
        """
        from lib.delivery.core import package

        for d in ("paper", "paper_appendix"):
            (self.root / d).mkdir(parents=True, exist_ok=True)
            (self.root / d / "main.pdf").write_bytes(b"%PDF-1.4\n" + b"x" * 50)
        out = self.root / "产物" / "提交作品" / "最新作品"
        items = [{"path": "正文.pdf", "desc": "", "source": "paper/main.pdf"}]
        arch = out / "其余文件"
        package(self.root, out, items)
        self.assertTrue((arch / "附录/main.pdf").is_file(), "首次打包就该有这两棵子树")
        self.assertTrue((arch / "正文/main.pdf").is_file())

        # ① 这轮重建的以新版为准
        (self.root / "paper/main.pdf").write_bytes(b"%PDF-1.4\n" + b"NEW" * 40)
        # ② 这轮回退把 paper_appendix/ 搬走了（源目录不在盘上 ⇒ build_plan 不再生成那棵子树）
        (self.root / "paper_appendix").rename(self.root / "appendix_moved")
        package(self.root, out, items, allow_missing=True)
        self.assertTrue((arch / "附录/main.pdf").is_file(),
                        "工作区暂时没有 paper_appendix/ ⇒ 旧包里的 `其余文件/附录/` 不该消失")
        self.assertIn(b"NEW", (arch / "正文/main.pdf").read_bytes(),
                      "重建过的子树要以这一版为准（合并 ≠ 一律留着旧版）")

    def test_a_package_half_swapped_by_a_crash_is_recovered(self):
        """换包是**两次独立 rename**，崩在中间会让 `最新作品`
        整个不见、完好的旧包躺在隐藏的 `.最新作品.old-*` 里 —— 而收编它的代码只在换题时跑，
        同一题点「开始全链」续跑**永远不会自愈**（面板一直显示"没有提交件"，包其实好好的）。
        判据：`package()` 一进来就把残局收回来。
        """
        from lib.delivery.core import package

        (self.root / "paper").mkdir(parents=True, exist_ok=True)
        (self.root / "paper/main.pdf").write_bytes(b"%PDF-1.4\n" + b"x" * 50)
        out = self.root / "产物" / "提交作品" / "最新作品"
        items = [{"path": "正文.pdf", "desc": "", "source": "paper/main.pdf"}]
        package(self.root, out, items)
        # 模拟崩在两次 rename 之间：指针没了，旧包落在 .old-* 里，另有半个 staging
        out.rename(out.parent / ".最新作品.old-deadbeef")
        (out.parent / ".最新作品.building-cafe").mkdir()
        package(self.root, out, items)
        self.assertTrue((out / "正文.pdf").is_file(), "残局必须被收回来，否则续跑永远看不到包")
        self.assertFalse((out.parent / ".最新作品.building-cafe").exists(), "半个 staging 要清掉")

    def test_provisional_items_uses_the_same_names_as_the_manifest(self):
        """⑨ 结束时就先把已经做好的移入 `提交作品/最新作品`。

        动机：提交清单由 **⑭** 写，而 ⑭ 排在 ⑨ 之后 ⇒ 链一旦在 ⑨~⑬ 停下（黄灯），
        那个文件夹会一片空白 —— 尽管正文 PDF / 附录 / `result*.xlsx` 早就做好了。
        判据：临时清单的**名字**必须与 ⑭ 那份同源（正文用 `body_pdf_name()`、其余用
        `FIXED_SOURCES` 的键），否则会出现「先叫 result1.xlsx、后改叫 结果1.xlsx」这种漂移。
        """
        from lib.delivery.core import FIXED_SOURCES, body_pdf_name, provisional_items

        (self.root / "paper").mkdir(parents=True, exist_ok=True)
        (self.root / "paper/main.tex").write_text(r"\papertitle{测试标题}", encoding="utf-8")
        (self.root / "paper/main.pdf").write_bytes(b"%PDF-1.4\n" + b"x" * 50)
        (self.root / "paper_appendix").mkdir(exist_ok=True)
        (self.root / "paper_appendix/main.pdf").write_bytes(b"%PDF-1.4\n" + b"x" * 50)
        (self.root / "results").mkdir(exist_ok=True)
        (self.root / "results/result1.xlsx").write_bytes(b"x" * 10)
        (self.root / "code").mkdir(exist_ok=True)
        (self.root / "code/core.py").write_text("print(1)", encoding="utf-8")

        got = {i["path"]: i["source"] for i in provisional_items(self.root)}
        self.assertEqual(got.get(body_pdf_name(self.root)), "paper/main.pdf",
                         "正文名必须来自 body_pdf_name()，不许另起一套")
        self.assertEqual(got.get("附录A.pdf"), FIXED_SOURCES["附录A.pdf"])
        self.assertEqual(got.get("result1.xlsx"), "results/result1.xlsx")
        self.assertEqual(got.get("core.py"), "code/core.py")
        # 盘上没有的**不许编** —— 编一个不存在的名字，`check()` 会判「清单声明了它但产物里没有」
        self.assertNotIn("demo.html", got)
        self.assertNotIn("运行说明.md", got)

    def test_collect_outputs_falls_back_to_the_provisional_list(self):
        """⑭ 还没跑（没有提交清单）时也要能收一批 —— 而不是只报一句"打包失败"什么都不做。"""
        (self.root / "paper").mkdir(parents=True, exist_ok=True)
        (self.root / "paper/main.tex").write_text(r"\papertitle{测试标题}", encoding="utf-8")
        (self.root / "paper/main.pdf").write_bytes(b"%PDF-1.4\n" + b"x" * 50)
        self.assertTrue(self.s._real_collect_outputs(), "没有清单也该能先收一批")
        out = self.s._submission_dir()
        names = sorted(p.name for p in out.iterdir()) if out.is_dir() else []
        self.assertIn("测试标题.pdf", names, f"临时包该有正文 PDF，实际 {names}")

    def test_rotation_then_a_failed_package_leaves_the_archive_intact(self):
        """端到端：打包成功 → 换题轮转 → 再打包失败 ⇒ 归档里那份**逐字节不变**。

        钉的是「轮转管指针目录这个名字、`package()` 管目录里面的内容」这条分工 ——
        `package()` 只在 `out.parent` 里造 `.{name}.building-*` / `.{name}.old-*`，
        碰不到已经改名归档的那份。
        """
        self._make_submission_workspace()
        self.assertTrue(self.s._real_collect_outputs())
        sub = self.s._submission_dir()
        before = {p.relative_to(sub).as_posix(): p.read_bytes()
                  for p in sub.rglob("*") if p.is_file()}
        self.assertIn("正文.pdf", before, "先得真打包出一份提交件")

        self.s._rotate_pointers("换题", "2026A")       # 换题
        archived = [p for p in sub.parent.iterdir()
                    if p.is_dir() and not p.name.startswith(".") and p.name != "最新作品"]
        self.assertEqual(len(archived), 1, [p.name for p in sub.parent.iterdir()])
        self.assertEqual({p.relative_to(archived[0]).as_posix(): p.read_bytes()
                          for p in archived[0].rglob("*") if p.is_file()}, before,
                         "归档那份该与打包完时逐字节相同")

        (self.root / "paper/main.pdf").unlink()        # 清单声明了它 → 打包必失败
        self.assertFalse(self.s._real_collect_outputs())
        self.assertEqual({p.relative_to(archived[0]).as_posix(): p.read_bytes()
                          for p in archived[0].rglob("*") if p.is_file()}, before,
                         "打包失败动了已归档的那份")
        leftovers = [p.name for p in sub.parent.iterdir() if p.name.startswith(".")]
        self.assertEqual(leftovers, [], f"打包失败留了中间件：{leftovers}")

    # ---- 跨盘 / 被占用：暂存工作区原件 ----

    def test_a_full_wipe_also_clears_the_showcase_and_the_two_pointers(self):
        """整链清空（从 ① 重跑）必须把**展示区**与**两个「最新」指针**一并收走。

        否则：工作区产物搬进 cache 了，而面板仍显示「提交件 → …（已生成）」，
        对那份**上一轮的**包跑 `delivery check` 还会判 PASS —— 与「当前和历史永远
        分得清」这条设计直接相冲。
        """
        (self.root / "reports").mkdir(parents=True, exist_ok=True)
        (self.root / "reports/RESULTS_REPORT.md").write_text("x", encoding="utf-8")
        sub, stg = self._pointers()
        sub.mkdir(parents=True, exist_ok=True)
        (sub / "正文.pdf").write_text("上一轮的", encoding="utf-8")
        (stg / "编码计算").mkdir(parents=True, exist_ok=True)
        (stg / "编码计算/RESULTS_REPORT.md").write_text("x", encoding="utf-8")

        self.s._redo_from("literature")

        self.assertEqual(list(sub.iterdir()), [], "提交件指针没清干净")
        self.assertEqual(list(stg.iterdir()), [], "阶段产物指针没清干净")
        stamps = list((self.root / "产物" / "cache").iterdir())
        self.assertEqual(len(stamps), 1, stamps)
        self.assertTrue((stamps[0] / "最新/提交作品/正文.pdf").is_file(),
                        "被清掉的旧包该在 cache 里可恢复")

    def test_a_local_rollback_clears_that_stages_showcase_only(self):
        """局部回退只管被回退的阶段，且**不动**两个指针（提交件不是这次要重做的东西）。"""
        (self.root / "paper").mkdir(parents=True, exist_ok=True)
        (self.root / "paper/main.tex").write_text("x", encoding="utf-8")
        sub, stg = self._pointers()
        for name in ("论文撰写", "编码计算"):
            (stg / name).mkdir(parents=True, exist_ok=True)
            (stg / name / "x.md").write_text("x", encoding="utf-8")
        sub.mkdir(parents=True, exist_ok=True)
        (sub / "正文.pdf").write_text("提交件", encoding="utf-8")

        self.s._redo_from("write")

        self.assertFalse((stg / "论文撰写").exists(), "被回退阶段的展示区快照该收走")
        self.assertTrue((stg / "编码计算/x.md").is_file(), "别的阶段的快照不许动")
        self.assertTrue((sub / "正文.pdf").is_file(), "局部回退不该动提交件指针")

    def test_a_cross_device_stash_still_moves_the_files(self):
        """对照组：**真**跨盘（errno 18）时 `_stash_paths` 仍必须把东西搬过去。

        产物目录可以设到别的盘（面板那个框直接能填），而 `_stash_paths` 若只有
        `p.rename(dest)` ⇒ 跨盘时**整批静默失败**：一件都没搬走，调用方却照旧往下跑。
        """
        (self.root / "reports").mkdir(parents=True, exist_ok=True)
        (self.root / "reports/RESULTS_REPORT.md").write_text("x", encoding="utf-8")
        dest = self.root / "产物" / "cache" / "某个名字" / "工作区原件"
        real = Path.rename
        calls = []

        def flaky(self_, target):
            calls.append(self_.name)
            if len(calls) == 1:                        # 只让第一次 rename 报「跨盘」
                raise OSError(18, "Invalid cross-device link")
            return real(self_, target)

        with unittest.mock.patch.object(Path, "rename", flaky):
            moved = self.s._stash_paths(["reports"], dest_root=dest)
        self.assertEqual(moved, ["reports"], "跨盘该复制过去，不该整批失败")
        self.assertTrue((dest / "reports/RESULTS_REPORT.md").is_file())
        self.assertFalse((self.root / "reports").exists(), "复制成功后源该删掉")
        self.assertEqual([p.name for p in dest.parent.iterdir() if p.name.startswith(".")],
                         [], "不该留下 .copying- 临时目录")

    def test_a_locked_workspace_file_stops_the_problem_switch(self):
        """换题时工作区原件搬不走 ⇒ **中止本轮**，不许让新题继承旧题的产物。

        跨盘搬不走时若照常往下跑、还 log「已归档」：8/8 一件都没搬走，
        于是新题在上一题的 `reports/paper/code` 上面跑，而回执紧接着被作废 ⇒ 没人会发现。
        """
        (self.root / "request").mkdir(parents=True, exist_ok=True)
        (self.root / "config").mkdir(parents=True, exist_ok=True)
        (self.root / "request/problem.md").write_text("A 题", encoding="utf-8")
        self.s._prepare_workspace()                    # 首次：记下 digest
        (self.root / "reports").mkdir(exist_ok=True)
        (self.root / "reports/RESULTS_REPORT.md").write_text("x", encoding="utf-8")
        digest_before = json.loads(
            (self.root / "runtime/quality/workspace.json").read_text(encoding="utf-8"))
        (self.root / "request/problem.md").write_text("B 题", encoding="utf-8")

        with open(self.root / "reports/RESULTS_REPORT.md", "rb") as held:
            held.read(1)
            with self.assertRaises(self.s.RotationBlocked):
                self.s._prepare_workspace()

        self.assertTrue((self.root / "reports/RESULTS_REPORT.md").is_file(), "原件该还在")
        self.assertEqual(
            json.loads((self.root / "runtime/quality/workspace.json").read_text(encoding="utf-8")),
            digest_before,
            "workspace.json 被改写了 —— 下一轮就不会再判成「换题」了，新题静默继承旧题产物")

    def test_the_source_digest_ignores_plan_md(self):
        """`plan.md` 是 ① 自己写的**产出**，不许当「题目输入」。

        若把它算作输入：`plan.md` 出现或变化 ⇒ 下一次点「开始全链」被判成「换题」⇒ ① 刚打包好的
        `提交作品/最新作品` 被**整目录改名归档**、指针清空，`各阶段产物/最新产物` 同样，
        工作区原件全搬进 cache，`_invalidate_from(0)` 把全部回执照废 ⇒ 整链从 ① 重跑
        （④ 是小时级）—— 明明没换题，表现成「再点一次怎么又整链重跑」。
        """
        (self.root / "request").mkdir(parents=True, exist_ok=True)
        (self.root / "request/problem.md").write_text("题面", encoding="utf-8")
        before = self.s._source_digest()
        (self.root / "plan.md").write_text("# 计划 v1", encoding="utf-8")
        self.assertEqual(self.s._source_digest(), before,
                         "写 plan.md 动了「题目摘要」⇒ 下次点 ▶ 会被当成换题、清空提交件")
        (self.root / "plan.md").write_text("# 计划 v2", encoding="utf-8")
        self.assertEqual(self.s._source_digest(), before)

        # 但它仍是**事实**：改了它，读它的阶段必须失效（走 artifacts 半份，作用域精确）
        stage = next(s for s in self.s.STAGES if s["id"] == "analysis")
        art_before = self.s._input_split(stage)[0]
        (self.root / "plan.md").write_text("# 计划 v3", encoding="utf-8")
        self.assertNotEqual(self.s._input_split(stage)[0], art_before,
                            "改了 plan.md 却没有任何阶段失效 —— 那是漏失效")

    def test_problem_switch_also_stashes_the_repair_feedback(self):
        """换题必须把 `runtime/quality/feedback/` 一起搬走。

        `receipt_ledger_issues()` 读它是**无 run_id 过滤的全目录 glob**：残留一条上一题的
        `gate_decision.json`，新一轮 ② 建模设计就**必然**挂在「缺返修台账」自检上 ——
        而那条提示是**假事实**（本轮根本没收到回执），「再试一次」也出不来。
        （`_redo_from` 的 start_i==0 分支已经这么做了，`_prepare_workspace` 这条路不能漏。）
        """
        (self.root / "request").mkdir(parents=True, exist_ok=True)
        (self.root / "config").mkdir(parents=True, exist_ok=True)
        (self.root / "request/problem.md").write_text("A 题", encoding="utf-8")
        self.s._prepare_workspace()
        fb = self.root / "runtime/quality/feedback/00621cfb/00d2b0df"
        fb.mkdir(parents=True, exist_ok=True)
        (fb / "gate_decision.json").write_text("{}", encoding="utf-8")
        (self.root / "request/problem.md").write_text("B 题", encoding="utf-8")

        self.s._prepare_workspace()
        self.assertFalse((self.root / "runtime/quality/feedback").exists(),
                         "换题后上一题的返修回执还在 ⇒ 新一轮 ② 会挂在「缺返修台账」上")

    # ---- 归档命名口径：用「已经跑完的那道题」的标识 ----

    def test_archive_names_with_the_recorded_id_not_the_panel_one(self):
        """手动归档必须用**记录值**，不是面板当前配置。

        用当前配置就会贴错标签：面板把 2026A 改成 2026B 再点「📦 归档本题并换新」⇒
        **2026A 的提交件被盖上 2026B 的名字**；反过来，换到 B 题后自动轮转若拿记录值，
        又会把 **B 题的提交件**归成 2026A。同一件事两个入口两套口径 —— 而「题目标识
        进归档目录名」正是要的东西。
        """
        (self.root / "config").mkdir(parents=True, exist_ok=True)
        (self.root / "request").mkdir(parents=True, exist_ok=True)
        (self.root / "request/problem.md").write_text("A 题", encoding="utf-8")
        self.s._save_delivery_config("", "2026A")
        self.s._prepare_workspace()                  # 记下：这道题 = 2026A
        self._seed_pointers()                        # A 题跑出了提交件
        self.s._save_delivery_config("", "2026B")    # 面板改成 B 题

        resp = asyncio.run(self.s.archive_delivery(self.s.ArchiveReq()))
        self.assertTrue(resp["name"].startswith("2026A_"),
                        f"用面板的新标识给旧题的成果命名了：{resp['name']}")

    def test_archive_on_empty_pointers_does_not_claim_success(self):
        """两个「最新」都空 ⇒ 只建骨架、**没有**归档目录，不许回一个假的 `archived_to`。

        否则前端会打出「已归档 → X/（0 项改名为该时间戳）」，而那个 X/ 从未被创建。
        """
        (self.root / "config").mkdir(parents=True, exist_ok=True)
        resp = asyncio.run(self.s.archive_delivery(self.s.ArchiveReq(problem_id="2026A")))
        self.assertFalse(resp["created"])
        self.assertEqual(resp["rotated"], [])
        self.assertNotIn("archived_to", resp,
                         "回了指向不存在目录的 archived_to —— 那是冒充成功")
        self.assertIn("note", resp)

    # ---- 题目标识非法时不许把出口炸掉 ----

    def test_start_rejects_an_illegal_problem_id(self):
        """落盘前必须校验题目标识。

        含 Windows 保留字符的标识（例如 `2026A:2026.9.18`）一旦进配置，
        之后**每一次**回退 / 清空都会 500 —— 而黄灯那条路是在清掉面板之后才炸的。
        唯一会校验的 `POST /api/delivery` 前端从来不调，所以必须在 `/api/start` 挡。
        """
        (self.root / "config").mkdir(parents=True, exist_ok=True)
        with self.assertRaises(Exception) as cm:
            asyncio.run(self.s.start(self.s.StartReq(problem_id="2026A:2026.9.18")))
        self.assertIn("题目标识", str(cm.exception))
        self.assertFalse(self.s.state["running"], "被拒时不该把链起起来")

    def test_redo_falls_back_to_a_timestamp_when_the_id_is_illegal(self):
        """题目标识非法不许把**回退**整条路炸掉 —— 回退是黄灯唯一的出口。"""
        (self.root / "config").mkdir(parents=True, exist_ok=True)
        (self.root / "paper").mkdir(parents=True, exist_ok=True)
        (self.root / "paper/main.tex").write_text("x", encoding="utf-8")
        self.s._save_delivery_config("", "2026A:2026.9.18")

        cleared = self.s._redo_from("write")          # 关键：不许抛
        self.assertIn("paper", cleared)
        stamps = [p.name for p in (self.root / "产物" / "cache").iterdir()]
        self.assertEqual(len(stamps), 1, stamps)
        self.assertNotIn(":", stamps[0], "Windows 保留字符不能出现在目录名里")

    def test_a_failed_rollback_leaves_the_decision_panel_intact(self):
        """回退失败时决策面板必须**还在**（否则连重试的入口都没有）。

        若 `_apply_decision` 在调 `_redo_from` **之前**就 `_set_pending(None)`：
        `_redo_from` 中途一抛（例如题目标识非法），就变成「面板已消失、产物没搬、链也没起」，
        只看到一个 500。清 pending 必须晚于回退成功。
        """
        (self.root / "config").mkdir(parents=True, exist_ok=True)
        self.s._set_pending({"stage": "verify", "kind": "failure", "status": "failed",
                             "actions": ["retry", "rollback"], "recommended": "write"})
        self.s.state["stages"]["verify"] = "awaiting_user"
        with unittest.mock.patch.object(self.s, "_redo_from",
                                        side_effect=RuntimeError("模拟回退中途炸")):
            with self.assertRaises(Exception):
                asyncio.run(self.s._apply_decision(
                    self.s.DecisionReq(action="rollback", stage="write")))
        self.assertIsNotNone(self.s.state["pending"],
                             "回退失败后决策面板消失了 —— 用户没有重试入口")

    def test_the_first_rotation_after_upgrade_keeps_the_problem_id(self):
        """旧版写的 `workspace.json` 没有 `problem_id` ⇒ 第一次轮转也不能丢题目标识。

        否则归档目录名退化成只有时间戳，与旁边已有的 `2026A_…` 以及「提交件归档 /
        阶段产物归档 / 工作区原件 三处同名」那条对账约定都不符。
        """
        (self.root / "config").mkdir(parents=True, exist_ok=True)
        (self.root / "request").mkdir(parents=True, exist_ok=True)
        (self.root / "request/problem.md").write_text("题面", encoding="utf-8")
        ws = self.s.LOG_DIR / "quality" / "workspace.json"
        ws.parent.mkdir(parents=True, exist_ok=True)
        ws.write_text(json.dumps({"source_digest": "STALE", "run_id": "old"}), encoding="utf-8")
        self.s._save_delivery_config("", "2026A")
        self._seed_pointers()

        self.s._prepare_workspace()
        stamp = [p.name for p in (self.root / "产物" / "提交作品").iterdir()
                 if p.is_dir() and p.name != "最新作品"]
        self.assertEqual(len(stamp), 1, stamp)
        self.assertTrue(stamp[0].startswith("2026A_"), f"第一次轮转把题目标识丢了：{stamp[0]}")

    def test_cleanup_refuses_before_the_run_completes(self):
        """中途搬走 reports/ code/，回退与重跑就没东西可读了 —— 所以必须拦住。"""
        self._touch("reports/VERIFY_REPORT.md")
        self.s.state["run_completed"] = False
        with self.assertRaises(Exception):
            asyncio.run(self.s.cleanup())
        self.assertTrue((self.root / "reports").exists(), "被拒时不该动任何东西")

    def test_cleanup_moves_leftovers_into_other_products(self):
        self._touch("reports/VERIFY_REPORT.md", "code/run_all.py", "paper/main.tex")
        self.s.state["run_completed"] = True
        result = asyncio.run(self.s.cleanup())
        self.assertIn("reports", result["moved"])
        dest = self.root / "产物" / "其他产物"
        self.assertTrue((dest / "reports/VERIFY_REPORT.md").is_file())
        self.assertTrue((dest / "code/run_all.py").is_file())
        self.assertFalse((self.root / "reports").exists())
        # 框架本体不许被搬走 —— 它是代码，不是本轮的产物；产物目录与 cache 是**落点**，
        #   更不能搬（搬了就是把自己移进自己）。临时工作区里没有 lib/web/ skills/，
        #   所以直接查清单本身 —— 那才是判据。
        for keep in ("lib", "skills", "docs", "regression", "config",
                     "产物", "cache", "request", "data"):
            self.assertNotIn(keep, self.s.CLEANUP_RELS, f"{keep} 不该出现在清理清单里")

    def test_cleanup_button_hidden_until_complete_and_nothing_left(self):
        self._touch("reports/VERIFY_REPORT.md")
        self.s.state["run_completed"] = False
        self.assertFalse(self.s._can_cleanup(), "没跑完不该出现清理按钮")
        self.s.state["run_completed"] = True
        self.assertTrue(self.s._can_cleanup())
        asyncio.run(self.s.cleanup())
        self.assertFalse(self.s._can_cleanup(), "清完就不该再显示按钮")

    def test_analysis_contract_selfcheck_halts_early(self):
        """题意契约的锚点对不上时，**在 analysis 收尾当场挂起**，不留给下游门禁。

        契约先写、报告后定稿，报告一改引用就失效。等 `4review` 拦下时已经过了
        40 分钟、agent 上下文早没了、人也被卡在下一个阶段。
        """
        (self.root / "config").mkdir(exist_ok=True)
        (self.root / "config/content_quality.json").write_text("{}", encoding="utf-8")
        (self.root / "request").mkdir(exist_ok=True)
        (self.root / "request/problem.md").write_text("题面原文里有这句话", encoding="utf-8")
        rep = self.root / "reports"
        rep.mkdir(exist_ok=True)

        def after(sid):
            # 契约必须**在 analysis 跑的当口**写出来，不能提前放 —— `_prepare_workspace`
            #   在开跑时会把整个 `reports/` 暂存走（输入版本变更），预放的会被搬走。
            #   这也正是真实情形：契约是 3analysis 自己产出的。
            if sid == "analysis":
                (rep / "TASK_CONTRACT.json").write_text(json.dumps({
                    "schema_version": 1, "requirements": [{
                        "id": "r1",
                        "source": {"file": "request/problem.md", "quote": "题面原文里有这句话"},
                        "source_semantics": {"quantifier": "each", "scope": "s", "unit": "u",
                                             "time_reference": "t"},
                        "model_semantics": {"quantifier": "each", "scope": "s", "unit": "u",
                                            "time_reference": "t"},
                        "model_anchor": {"file": "reports/ANALYSIS_MODELING_REPORT.md",
                                         "quote": "这句在报告里根本不存在"},
                        "status": "mapped"}]}, ensure_ascii=False), encoding="utf-8")

        calls = self.install_successful_runner(after=after)
        asyncio.run(self.s.run_all())
        self.assertIn("analysis", calls)
        self.assertTrue(self.s.state["halt_gate"], "自检不过应当场挂起")
        self.assertEqual(self.s.state["stages"]["analysis"], "awaiting_user")
        self.assertIn("题意契约自检不过", self.s.state["halt_reason"])
        self.assertNotIn("review", calls, "自检不过就不该再往下白跑一轮 review")

    def test_analysis_receipt_ledger_selfcheck_halts_early(self):
        """返修记录「自证」当场挂起，不留给下游门禁白跑一轮。

        报告 §15.1 的返修记录写「该句改『≤0.98%』」，而 `≤0.98%`
        这时**只出现在那张表里**（正文仍是旧的 ≤0.4%）—— 拿全文检索当自检，
        **记录自己把自己证明了**。代价是 review 每轮重查、每轮打回，白烧几十分钟。
        """
        (self.root / "config").mkdir(exist_ok=True)
        (self.root / "config/content_quality.json").write_text("{}", encoding="utf-8")
        self._pretend_same_problem()      # 上一轮的返修回执要活到 ② 跑的那一刻
        fb = self.s.LOG_DIR / "quality/feedback/run1/abc123"
        fb.mkdir(parents=True, exist_ok=True)
        (fb / "gate_decision.json").write_text(
            json.dumps({"issues": [{"id": "rv2_x"}]}, ensure_ascii=False), encoding="utf-8")
        rep = self.root / "reports"
        rep.mkdir(exist_ok=True)

        def after(sid):
            # 与题意契约同理：这些文件必须**在 analysis 跑的当口**写出来 ——
            # `_prepare_workspace` 开跑时会把 `reports/` 整个暂存走。
            if sid != "analysis":
                return
            (rep / "ANALYSIS_MODELING_REPORT.md").write_text(
                "# 报告\n\n## 2. 模型\n正文一句，没提那个串。\n\n"
                "## 15. 版本与修订历史\n\n### 15.1 本轮返修复验记录\n\n"
                "| 项 | 处置 |\n|---|---|\n| rv2_x | 该句改「≤0.98%」 |\n", encoding="utf-8")
            (rep / "RECEIPT_LEDGER.json").write_text(json.dumps({
                "schema_version": 1,
                "receipt": "runtime/quality/feedback/run1/abc123/gate_decision.json",
                "report": "reports/ANALYSIS_MODELING_REPORT.md",
                "items": [{"id": "rv2_x", "disposition": "applied", "probe": "≤0.98%"}]},
                ensure_ascii=False), encoding="utf-8")

        calls = self.install_successful_runner(after=after)
        asyncio.run(self.s.run_all())
        self.assertIn("analysis", calls)
        self.assertTrue(self.s.state["halt_gate"], "台账不过应当场挂起")
        self.assertEqual(self.s.state["stages"]["analysis"], "awaiting_user")
        self.assertIn("返修台账自检不过", self.s.state["halt_reason"])
        self.assertNotIn("review", calls, "台账不过就不该再往下白跑一轮 review")

    def test_analysis_receipt_ledger_honest_declaration_passes(self):
        """反向对照：诚实登记（没做就说没做）不该被拦 —— 否则等于逼人撒谎。"""
        (self.root / "config").mkdir(exist_ok=True)
        (self.root / "config/content_quality.json").write_text("{}", encoding="utf-8")
        self._pretend_same_problem()      # 上一轮的返修回执要活到 ② 跑的那一刻
        fb = self.s.LOG_DIR / "quality/feedback/run1/abc123"
        fb.mkdir(parents=True, exist_ok=True)
        (fb / "gate_decision.json").write_text(
            json.dumps({"issues": [{"id": "rv2_x"}]}, ensure_ascii=False), encoding="utf-8")
        rep = self.root / "reports"
        rep.mkdir(exist_ok=True)

        def after(sid):
            if sid != "analysis":
                return
            (rep / "RECEIPT_LEDGER.json").write_text(json.dumps({
                "schema_version": 1,
                "receipt": "runtime/quality/feedback/run1/abc123/gate_decision.json",
                "report": "reports/ANALYSIS_MODELING_REPORT.md",
                "items": [{"id": "rv2_x", "disposition": "not_applied",
                           "reason": "本轮时间不够，下一轮做"}]}, ensure_ascii=False),
                encoding="utf-8")

        calls = self.install_successful_runner(after=after)
        asyncio.run(self.s.run_all())
        self.assertIn("review", calls, "诚实登记应当放行到下一阶段")

    def test_a_gate_that_really_ran_ends_as_done_not_awaiting_review(self):
        """门禁真跑完、裁决读出来之后必须写成 `done`；停在 `awaiting_review` 面板会显成"没通过"。

        症状：⑧ 的裁决早就 PASS、⑨ 都在写论文了，可面板把 ⑧ 画成 ⏸/黑 —— 因为状态回写被
        `_ran_now` 判成"没跑过"给跳过了（门禁跑完时状态是 `awaiting_review`，
        而 `_ran_now` 的判据正是 `== "done"`）。
        这条同时钉住另一半：**复用留下的 `done(skip)` 不许被覆盖**。
        """
        self.install_successful_runner()
        asyncio.run(self.s.run_all())
        st = self.s.state["stages"]
        self.assertEqual(st["review"], "done",
                         "③ 门禁真跑完却停在 awaiting_review —— 面板会显成『没通过』")
        self.assertEqual(st["figreview"], "done", "⑧ 同上")
        calls = self.install_successful_runner()      # 第二轮：全部复用
        asyncio.run(self.s.run_all())
        self.assertEqual(st["review"], "done(skip)", "复用标记被覆盖了 —— 收尾自检会跟着误判")
        self.assertEqual(st["figreview"], "done(skip)")

    def test_self_checks_run_only_when_the_stage_really_ran(self):
        """收尾自检的护栏：**只有 `done`（真跑过）才做；`done(skip)`（复用）不做**。

        回退到 ⑧ write 后链条走到 ②，analysis 靠回执被复用 ——
        可盘上的返修台账是**上一轮留下的**、答的是旧回执，自检于是报「receipt 指错了」当场挂起。
        重试仍然复用（输入没变）⇒ **死循环，出不来**。

        （这条护栏不写成「跑一整轮链」的集成测试：严格模式（建了 `config/content_quality.json`）
        下六个门禁各需一份合规 v2 侧车，夹具成本远超它要验的那一行判断；
        端到端由「回退后那条链能走通」在实机上验。）
        """
        st = self.stage("analysis")
        for value, expected in (("done", True),          # 真跑过 → 要自检
                                ("done(skip)", False),   # 复用 → 不检（上一轮的残留不归它管）
                                ("done(stale-instr)", False),
                                ("done(manual)", False),
                                ("awaiting_user", False),
                                ("idle", False)):
            self.s.state["stages"]["analysis"] = value
            self.assertEqual(self.s._stage_ran_this_round(st), expected, f"状态 {value!r}")

    def test_a_reused_stage_is_not_held_to_the_previous_rounds_ledger(self):
        """复用**不是**「这一轮真跑过」—— 收尾自检必须据此跳过。

        顺序是关键：`run_all` 若先无条件写 `state["stages"][sid] = "done"`、**之后**才取
        `_stage_ran_this_round()`，而那个函数读的正是这个字段 ⇒ 复用留下的 `done(skip)`
        被覆盖掉、复用被当成「真跑了」。

        后果：⑪ 结果可信度审计 判 NEEDS_FIX → 回退到 ⑤ 编码计算 → ② 建模设计 被复用，
        可它的返修台账答的是 ③ 建模评审 那份回执，而 `runtime/quality/feedback/` 里最新的
        一份已经是回退时写下的审计回执 ⇒ 自检报「receipt 指错了」当场挂起；
        重试仍是复用 ⇒ **出不来**。

        上面那条 `test_self_checks_run_only_when_the_stage_really_ran` 只对手工摆好的
        `state["stages"]` 断言真值表 —— 它**到不了**这个顺序问题。
        这条补的正是那条集成路径：回退之后的第二轮里 ② 被复用、且链子继续往下走。
        """
        (self.root / "config").mkdir(exist_ok=True)
        (self.root / "config/content_quality.json").write_text("{}", encoding="utf-8")
        self._pretend_same_problem()
        audit_stage = self.stage("audit")            # 截短 STAGES 之前先抓住它
        # 链子截短到「①文献 ②建模 ④编码 ⑨写作」：截短**不是**为了省时间，是因为严格模式下
        #   `review/audit/cross/verify` 四个门禁各要一份合规的 TASK_CONTRACT.json 才过得了
        #   机械地板，而 mock runner 写不出它 —— 留着它们用例会死在不相干的地方。
        #   `code`/`write` 两个 id **必须留**：`_input_split` 拿它们当分档基准
        #   （`index >= at("code")` / `at("write")`），少了就是 StopIteration。
        #   两个 pass 用**同一份** STAGES：改它会让部分阶段的输入摘要跟着变，
        #   于是第二轮该"复用"的反而会真跑，用例就测不到东西了。
        self.s.STAGES = [self.stage(x) for x in ("literature", "analysis", "code", "write")]
        # 上一轮：③ 建模评审 判 REVISE → 回执投给了 ②。② 是**带着这份回执**跑完的。
        old = self.s.LOG_DIR / "quality/feedback/run0/review01"
        old.mkdir(parents=True, exist_ok=True)
        (old / "gate_decision.json").write_text(json.dumps({
            "schema_version": 2, "stage": "review", "status": "NEEDS_FIX",
            "target": "analysis", "reason": "content_repair_required",
            "issues": [{"id": "rv2_x"}]}, ensure_ascii=False), encoding="utf-8")
        rep = self.root / "reports"
        rep.mkdir(exist_ok=True)

        def after(sid):
            if sid != "analysis":
                return
            (rep / "RECEIPT_LEDGER.json").write_text(json.dumps({
                "schema_version": 1,
                "receipt": "runtime/quality/feedback/run0/review01/gate_decision.json",
                "report": "reports/ANALYSIS_MODELING_REPORT.md",
                "items": [{"id": "rv2_x", "disposition": "not_applied",
                           "reason": "本轮时间不够，下一轮做"}]}, ensure_ascii=False),
                encoding="utf-8")

        calls = self.install_successful_runner(after=after)
        asyncio.run(self.s.run_all())
        self.assertIn("analysis", calls, "第一轮 ② 应当**真跑**")
        self.assertTrue(self.s.state["run_completed"], self.s.state["halt_reason"])

        # 下一轮：feedback/ 里多出一份**更新**的回执。回退时驱动干的就是这件事 ——
        # `_apply_decision` 的 rollback 分支第一句就是 `_save_feedback(失败的门禁)`，
        # 把那份裁决另存一份进 feedback/。于是「② 的台账答的是 ③ 的回执」与
        # 「feedback/ 里最新的是别家门的」同时成立。
        self.assertIsInstance(self.s._save_feedback(audit_stage), str)
        calls.clear()
        asyncio.run(self.s.run_all())

        self.assertEqual(calls, [], "产物都在、输入没变 —— 这一轮应当**全部复用**")
        self.assertNotIn("analysis", calls, "② 的输入没变，应当复用而不是重跑")
        self.assertEqual(self.s.state["stages"]["analysis"], "done(skip)")
        # 走到 `run_completed` 本身就是「主循环把每一步都走完了」的正信号：
        #   链若在 ② 就挂起，根本到不了终点。
        self.assertTrue(self.s.state["run_completed"],
                        f"复用的一轮不该拿上一轮的台账去自检：{self.s.state.get('halt_reason')}")

    def test_orphan_agent_reaper_only_kills_our_own_stale_agents(self):
        """收容孤儿：只杀「登记过」**且**「命令行指向本工作区」的。

        为什么需要：`taskkill /F` 杀**服务**时子进程不会被一起带走，孤儿会继续往 reports/
        写 —— 孤儿 analysis 会与新起一轮的 analysis 并发改写同一份报告与题意契约。
        为什么不能全杀：可能还开着**别的** claude 会话（比如 VSCode 扩展）——
        它们的命令行里没有本工作区路径，必须放过。
        """
        q = self.root / "runtime/quality"
        q.mkdir(parents=True, exist_ok=True)
        (q / "stage_pids.json").write_text(json.dumps([111, 222, 333]), encoding="utf-8")
        mine = str(self.root)
        self.s._claude_processes = lambda: [
            (111, f"claude.exe -p 你在工作区 {mine} 执行 literature"),   # 本工作区的孤儿 → 杀
            (222, "claude.exe --input-format stream-json"),              # 别的会话 → 放过
            (444, f"claude.exe -p {mine}"),                              # 没登记 → 放过
        ]
        killed = []
        n = self.s._reap_orphan_agents(kill=killed.append)
        self.assertEqual(n, 1)
        self.assertEqual(killed, [111])
        self.assertFalse((q / "stage_pids.json").exists(), "收完要清登记表")

    def test_orphan_reaper_is_a_noop_without_a_registry(self):
        self.assertEqual(self.s._reap_orphan_agents(kill=lambda p: None), 0)

    def test_orphan_reaper_never_kills_the_process_that_calls_it(self):
        """回收器**绝不能杀自己** —— 否则阶段 agent 一 import 本文件就把自己干掉。

        `_register_stage_pid()` 把**正在跑的那个阶段 agent 自己**也登记在表里，
        而回收器的匹配条件只有「pid 在表里」+「命令行含项目根」——两条它自己都满足。
        现场表现：`rc=1`，无任何诊断（Windows 上被 taskkill /F 掉的进程退出码就是 1）。
        此时 runtime/web_run.log 里 🧹 行号与 rc=1 行号相邻，可据此认定。
        """
        q = self.root / "runtime/quality"
        q.mkdir(parents=True, exist_ok=True)
        me = os.getpid()
        (q / "stage_pids.json").write_text(json.dumps([me, 111]), encoding="utf-8")
        mine = str(self.root)
        self.s._claude_processes = lambda: [
            (me,  f"claude.exe -p 你在 {mine} 执行 review"),   # 就是调用方自己 → 必须放过
            (111, f"claude.exe -p 你在 {mine} 执行 review"),   # 真孤儿 → 杀
        ]
        killed = []
        self.assertEqual(self.s._reap_orphan_agents(kill=killed.append), 1)
        self.assertEqual(killed, [111])
        self.assertNotIn(me, killed)

    def test_importing_server_never_reaps_orphans(self):
        """孤儿回收必须在「作为服务器启动」时跑，不能在模块级。

        模块级的话，**任何** import 本文件的进程都会执行它，而门禁 SKILL 恰恰鼓励 agent
        用「项目自带的门禁函数」自检（`from server import STAGES`）—— 于是 agent 自杀。
        这里用「登记表有没有被消费掉」当探针：回收器第一件事就是 unlink 它。
        """
        q = self.root / "runtime/quality"
        q.mkdir(parents=True, exist_ok=True)
        reg = q / "stage_pids.json"
        reg.write_text(json.dumps([999999]), encoding="utf-8")
        load_server(self.root)          # 等价于 agent 的 `from server import STAGES`
        self.assertTrue(reg.exists(),
                        "import 触发了孤儿回收（登记表被消费）—— 调用它的 agent 会把自己杀掉")

    def test_stage_pid_registration_is_bounded_and_deduped(self):
        """登记表只留最近 50 个、且不重复 —— 它不该随运行次数无限增长。"""
        for pid in list(range(60)) + [59]:
            self.s._register_stage_pid(pid)
        data = json.loads((self.root / "runtime/quality/stage_pids.json").read_text(encoding="utf-8"))
        self.assertLessEqual(len(data), 50)
        self.assertEqual(len(data), len(set(data)), "不该有重复 pid")

    def test_rollback_hint_is_honest_when_the_gate_never_finished(self):
        """门禁**没跑完**时，回退目标拿到的提示不能说成「它判你不合格」。

        `review` 因为没写出报告而失败时，它的裁决是 UNVERIFIED、issues 只有一条
        「去补 `.verdict.json`」—— **那是 review 自己的产物**。这条若被当返修回执投给
        `analysis`，analysis 会跑去追 `MODELING_REVIEW_REPORT.verdict.json`，
        拿着一份与本阶段无关、也执行不了的指令干活，最后整段失败。
        """
        hint = self.s._save_feedback(self.stage("review"))     # 没有报告 → no_report
        self.assertIn("没有跑完", hint)
        self.assertNotIn("按具体问题修复", hint)

    def test_rollback_hint_stays_a_repair_receipt_for_real_defects(self):
        """有具体缺陷时仍是正常返修回执 —— 别把这条一起改掉。"""
        self.s._gate_decision = lambda s: {
            "status": "NEEDS_FIX", "reason": "task_contract_failed",
            "issues": [{"id": "task_contract", "severity": "hard", "category": "task_interpretation"}]}
        hint = self.s._save_feedback(self.stage("review"))
        self.assertIn("按具体问题修复", hint)

    def test_verify_gate_catches_missing_submission_manifest_early(self):
        """提交清单缺失必须在 verify 就拦下，而不是等到收口打包 —— 中间隔着 demo 与一轮复验。

        包装发生在整链最后，那时才发现"清单没写"，已经白跑好几个小时。
        """
        # 反向对照：没有 config/delivery.local.json 时这条审计**不跑**（与其它四个客观审计
        # 同一开关约定）—— 少了这个 gate 会把 22 个不碰交付层的全链用例一次打红。
        self.report(self.stage("verify"), "最终结论：PASS")
        self.assertNotEqual(self.s._gate_decision(self.stage("verify"))["reason"],
                            "delivery_manifest_incomplete")
        (self.root / "config").mkdir(exist_ok=True)
        (self.root / "config/delivery.local.json").write_text("{}", encoding="utf-8")
        d = self.s._gate_decision(self.stage("verify"))
        self.assertEqual(d["reason"], "delivery_manifest_incomplete")
        self.assertEqual(d["target"], "format")            # 清单是 format 的产物
        self.assertIn("SUBMISSION_MANIFEST", d["issues"][0]["evidence"])

    def test_gate_cannot_mutate_reviewed_input(self):
        (self.root / "paper").mkdir()
        (self.root / "paper/main.pdf").write_bytes(b"old document")
        tex = self.root / "paper/main.tex"
        tex.write_text("\\documentclass{article}", encoding="utf-8")
        def after(sid):
            if sid == "verify":
                tex.write_text("\\documentclass{article}\\usepackage{evil}", encoding="utf-8")
        self.install_successful_runner(after=after)
        self.assertEqual(asyncio.run(self.s.run_stage(self.stage("verify"))), "unverified")

    def test_recompiling_paper_does_not_fail_verify(self):
        """15Verification 的 SKILL **要求**跑 xelatex 编译论文（Step 7）。

        编译会重写 main.pdf / main.log（后者首行带编译时刻，必然变字节）。这些是构建产物，
        不是"输入被改"。旧实现把它们算进指纹 → verify 跑完必判 unverified → run_all 立即
        _halt 且**不给重试** → 整链死在最后一关、交付产物永不打包。
        """
        (self.root / "paper").mkdir()
        (self.root / "paper/main.tex").write_text("\\documentclass{article}", encoding="utf-8")
        def after(sid):
            if sid == "verify":                      # 模拟 xelatex 就地编译
                (self.root / "paper/main.pdf").write_bytes(b"%PDF-1.4 rebuilt")
                (self.root / "paper/main.log").write_text("This is XeTeX ... 10 SEP 2026 16:30\n")
                (self.root / "paper/main.out").write_text("bookmarks")
        self.install_successful_runner(after=after)
        self.assertEqual(asyncio.run(self.s.run_stage(self.stage("verify"))), "ok")

    def test_full_chain_survives_paper_recompiles(self):
        """写后每个阶段都就地重编译论文，整链仍须正常收口（比赛日最致命的场景）。

        write→mathproof→cross→verify 的输入指纹都含 paper/。15Verification 的 SKILL 明确要求跑
        xelatex 两遍，重编译会重写 main.pdf/main.log（后者首行带编译时刻）。旧实现把这些构建
        产物算进指纹 → verify 跑完判 unverified → run_all 立即 _halt 且不给重试 → 交付产物
        永不打包，十几小时的链死在最后一关。
        """
        def after(sid):
            # format 也重编译论文（它独占排版层），必须在这个集合里 ——
            # 否则「阶段就地改了 paper/ 之后整链仍能跑完」这条鲁棒性覆盖会漏掉它。
            # 13Repair-by-rubric-verdict 同理：它按判词改 `paper/sections/*.tex` 后必须重编译，是写后唯一
            # 会主动改正文的阶段（12Rubric-final 只读，不进这个集合）。
            if sid in {"write", "format", "mathproof", "cross", "verify", "fix"}:
                (self.root / "paper").mkdir(exist_ok=True)
                # 注意 >80B：_artifact_ok 对 paper/main.pdf 有 80 字节下限
                (self.root / "paper/main.pdf").write_bytes(
                    b"%PDF-1.4 rebuilt " + sid.encode() + b" x" * 200)
                (self.root / "paper/main.log").write_text(f"XeTeX run {sid} 10 SEP 2026 16:40\n")
        calls = self.install_successful_runner(after=after)
        asyncio.run(self.s.run_all())
        self.assertTrue(self.s.state["run_completed"], self.s.state["halt_reason"])
        self.assertIn("verify", calls)
        # 口径是**⑨ 及之后每完成一个阶段就同步一次**，不是"只在链尾收一次"：⑨ 结束后先把
        #   **目前能移入的**移入，其余的**等它们各自的阶段完成再移入**；若后续阶段又改动了
        #   产物，就移入后**把之前的产物替代**。
        #   干净跑通一轮 = ⑨→⑯ 里**真跑过的**每个阶段各一次（⑬ 走的是“无事可做就跳过”那条 `continue` 路，不经过钩子）
        #   加链尾那次：write, mathproof, cross, rubric, format, verify, demo = 7，再加链尾 = **8**
        self.assertEqual(self.s._collect_outputs.call_count, 8,
                         "⑨ 起每个完成阶段各收一次 + 链尾一次；改挂钩点必须同步这条")

    def test_drawio_figures_do_not_stale_code_receipt(self):
        """drawio 往 figures/ 写自己的路线图/流程图，不是 code 的产物。

        旧实现把整个 figures/ 算进 code 的输出指纹 → 跑完 drawio 后，续跑时 code 的回执必然
        失配 → 最重的阶段从零重跑，并因 figures/ 变化级联拖垮整条下游。
        """
        st = self.stage("code")
        (self.root / "code").mkdir(exist_ok=True)
        (self.root / "code/example.txt").write_text("fixture")
        (self.root / "results").mkdir(exist_ok=True)
        (self.root / "results/r.json").write_text("{}")
        (self.root / "figures").mkdir(exist_ok=True)
        (self.root / "figures/fig_q1.pdf").write_bytes(b"code's own figure")
        self.report(st, "结果：PASS")
        before = self.s._output_digest(st)
        (self.root / "figures/fig_roadmap.pdf").write_bytes(b"drawio's roadmap")
        (self.root / "figures/fig_flow_q1.pdf").write_bytes(b"drawio's flow")
        self.assertEqual(before, self.s._output_digest(st))

    def test_stop_does_not_collect_and_resets_running(self):
        async def stopped(*args):
            self.s.state["stopping"] = True
            return 0, "", False
        self.s._call = stopped
        asyncio.run(self.s.run_all())
        self.s._collect_outputs.assert_not_called()
        self.assertFalse(self.s.state["running"])

    def test_exception_resets_running_and_records_reason(self):
        self.s._call = AsyncMock(side_effect=RuntimeError("fixture failure"))
        asyncio.run(self.s.run_all())
        self.assertFalse(self.s.state["running"])
        self.assertIn("fixture failure", self.s.state["halt_reason"])
        self.s._collect_outputs.assert_not_called()

    def test_redo_while_running_rejected(self):
        self.s.state["running"] = True
        with self.assertRaises(self.s.HTTPException) as cm:
            asyncio.run(self.s.redo(self.s.StageReq(stage="analysis")))
        self.assertEqual(cm.exception.status_code, 409)

    def test_stash_rejects_parent_and_preserves_two_versions(self):
        with self.assertRaises(ValueError):
            self.s._stash_paths(["../outside"])
        for value in ["first", "second"]:
            (self.root / "sample.txt").write_text(value)
            self.s._stash_paths(["sample.txt"])
        self.assertEqual({p.read_text() for p in self.s.CACHE.glob("*sample.txt")}, {"first", "second"})

    def test_verdict_formats_and_conflicts(self):
        st = self.stage("verify")
        for text, passes in [("**PASS（附披露）**", True), ("最终结论：PASS", True),
                             ("未判 PASS", False), ("最终结论：PASS\n最终结论：FAIL", False),
                             ("```\nPASS\n```", False)]:
            with self.subTest(text=text):
                self.report(st, text)
                self.assertEqual(self.s.gate_result(st) == "ok", passes)

    def test_structured_verdict_rejects_wrong_version_and_unresolved_issue(self):
        st = self.stage("verify")
        self.report(st, "最终结论：PASS")
        path = (self.s.REPORTS / st["report"]).with_suffix(".verdict.json")
        data = {"schema_version": 1, "stage": "verify", "input_digest": "old", "status": "PASS", "issues": []}
        path.write_text(json.dumps(data))
        self.assertEqual(self.s.gate_result(st), "UNVERIFIED")
        data["input_digest"] = self.s._input_digest(st)
        data["issues"] = [{"id": "I1", "severity": "hard", "evidence": "file:1", "fix": "fix it", "recheck": "test"}]
        path.write_text(json.dumps(data))
        self.assertEqual(self.s.gate_result(st), "UNVERIFIED")

    def test_packaging_failure_is_not_completion(self):
        self.install_successful_runner()
        self.s._collect_outputs.return_value = False
        asyncio.run(self.s.run_all())
        self.assertFalse(self.s.state["run_completed"])
        self.assertTrue(self.s.state["halt_gate"])

    def _make_submission_workspace(self):
        """造一份最小可打包的工作区（含 14Layout-and-format 该写的提交清单）。"""
        # 构建产物仍叫 main.pdf（打包时才改名成 正文.pdf / 附录A.pdf）—— 见
        # delivery.core.FIXED_SOURCES 的注释。
        for rel, body in [("paper/main.pdf", "pdf"), ("paper/main.tex", "tex"),
                          ("paper_appendix/main.pdf", "pdf"), ("paper_appendix/main.tex", "tex"),
                          ("demo/demo.html", "<html></html>"), ("results/result1.xlsx", "x"),
                          ("code/run_all.py", "# entry"), ("request/attachments/附件1.xlsx", "a"),
                          ("运行说明.md", "# 运行说明"), ("reports/RESULTS_REPORT.md", "# r")]:
            p = self.root / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(body, encoding="utf-8")
        (self.root / "reports/SUBMISSION_MANIFEST.json").write_text(json.dumps({
            "schema_version": 1, "stage": "format",
            "items": [{"path": n, "desc": "d"} for n in
                      ["正文.pdf", "附录A.pdf", "demo.html", "运行说明.md", "result1.xlsx",
                       "附件1.xlsx", "run_all.py"]]}, ensure_ascii=False), encoding="utf-8")

    def test_real_packaging_builds_submission_shaped_delivery(self):
        """收口打包出来的是**提交形状**的提交件：那一层只有提交项 + 其余文件/。

        落点是 `提交作品/最新作品/`（比产物根再下沉一层），
        于是产物根上只剩骨架目录、不再摊着提交件。
        """
        self._make_submission_workspace()
        self.assertTrue(self.s._real_collect_outputs())
        out = self.s._submission_dir()
        self.assertEqual(out, self.root / "产物" / "提交作品" / "最新作品")
        names = sorted(p.name for p in out.iterdir())
        self.assertEqual(names, sorted(["正文.pdf", "附录A.pdf", "demo.html", "运行说明.md",
                                        "result1.xlsx", "附件1.xlsx", "run_all.py", "其余文件"]))
        self.assertTrue((out / "其余文件/正文/main.tex").is_file())
        self.assertTrue((out / "其余文件/内部报告/RESULTS_REPORT.md").is_file())
        # 提交件**不许**摊在产物根上（`checks.py` 的白名单只认提交件根那一层）
        top = {p.name for p in (self.root / "产物").iterdir()}
        self.assertNotIn("正文.pdf", top, "提交件漏到产物根上了")
        self.assertLessEqual(top, {"提交作品", "各阶段产物", "cache", "其他产物"}, top)

    def test_real_packaging_failure_preserves_previous_delivery(self):
        """打包失败不该动上一份提交件 —— 不冒充本轮成功。"""
        out = self.s._submission_dir()
        out.mkdir(parents=True)
        (out / "old.txt").write_text("previous delivery", encoding="utf-8")
        self._make_submission_workspace()
        (self.root / "paper/main.pdf").unlink()      # 清单声明了它，盘上却没有
        self.assertFalse(self.s._real_collect_outputs())
        self.assertEqual((out / "old.txt").read_text(encoding="utf-8"), "previous delivery")

    def test_compressed_inputs_are_not_ignored(self):
        (self.root / "data").mkdir()
        p = self.root / "data/sample.csv.gz"
        p.write_bytes(b"first")
        before = fingerprint(self.root, ["data"])
        p.write_bytes(b"second")
        self.assertNotEqual(before, fingerprint(self.root, ["data"]))

    def test_per_question_verdict_lines_do_not_conflict_with_overall(self):
        """逐问「结论：PASS」+ 整题「整题结论：NEEDS_FIX」不是矛盾，显式整题行优先。

        旧实现只用一条"前缀可选"的正则：逐问行也被当成整题裁决 → found={PASS,NEEDS_FIX} →
        判 conflicting_verdict → **合法 v2 侧车被整份丢弃**，而驱动的修复提示只让
        "补写 .verdict.json、不要改动报告本体"（问题恰在报告本体），两轮后必然挂起。
        """
        report = self.root / "reports/AUDIT.md"
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text("- 结论：PASS（Q1 数值正确）\n- 结论：PASS（Q2 口径一致）\n"
                          "整题结论：NEEDS_FIX\n", encoding="utf-8")
        out = read_verdict(report, "audit", "d", allow_v2=False)
        self.assertEqual(out["status"], "NEEDS_FIX")

    def test_conflicting_overall_verdicts_still_block(self):
        """反向护栏：两个互相矛盾的**整题**判词仍必须判 UNVERIFIED。"""
        report = self.root / "reports/AUDIT2.md"
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text("整题结论：PASS\n整题门禁裁决：REVISE\n", encoding="utf-8")
        out = read_verdict(report, "audit", "d", allow_v2=False)
        self.assertEqual(out["status"], "UNVERIFIED")
        self.assertEqual(out["reason"], "conflicting_verdict")

    # ---- 裁决过期 ≠ 裁决写坏 ----

    def _gate_sidecar(self, digest, status="NEEDS_FIX", issues=None, advisories=None):
        """写一份 v2 门禁产物（报告 + 侧车），侧车声明 digest。"""
        rep = self.root / "reports/MODELING_REVIEW_REPORT.md"
        rep.parent.mkdir(parents=True, exist_ok=True)
        rep.write_text("# 评审\n\n## 整题门禁裁决：NEEDS_FIX\n", encoding="utf-8")
        rep.with_suffix(".verdict.json").write_text(json.dumps({
            "schema_version": 2, "stage": "review", "input_digest": digest, "status": status,
            "target": "analysis",
            "advisories": advisories if advisories is not None else [
                {"id": "ad_x", "category": "presentation", "evidence": "e", "fix": "f"}],
            "issues": issues if issues is not None else [
                {"id": "rv_x", "severity": "hard", "evidence": "e", "fix": "f", "recheck": "r"}]},
            ensure_ascii=False), encoding="utf-8")
        return rep

    def test_stale_digest_is_not_reported_as_malformed_json(self):
        """指纹失配是「裁决过期」，不是「JSON 写坏了」—— 两者处置完全相反。

        场景：门禁判出一批 hard 之后，有人改了
        `skills/_references/stage_discipline.md`（它在门禁 instructions 指纹里）→ 侧车
        指纹对不上 → 被当成格式错 → 驱动交给**改不了它的上游生产阶段**一句
        「去补 .verdict.json」，**那批真发现整份丢弃**，上游还白重写了一遍报告。
        """
        rep = self._gate_sidecar("OLD_DIGEST")
        out = read_verdict(rep, "review", "NEW_DIGEST", allow_v2=True)
        self.assertEqual(out["status"], "UNVERIFIED")
        self.assertEqual(out["reason"], "verdict_stale",
                         "指纹失配必须报 verdict_stale，不能混进 verdict_malformed")
        # findings 不能丢 —— 人对下一轮该怎么办，靠的就是这批
        self.assertEqual([i["id"] for i in out["stale_issues"]], ["rv_x"])
        self.assertEqual(out["issues"], [], "过期裁决不得参与返修路由")
        self.assertEqual(out["stale_digest"]["recorded"], "OLD_DIGEST")
        # advisories 也要跟着活下来：正文没动时它们指的文字同样真实存在 ——
        # 漏了，「延后建议随回退投递」在过期裁决上就成空转（而正文没动正是这里最常见的情形）。
        self.assertEqual([a["id"] for a in out.get("advisories") or []], ["ad_x"])

    def test_malformed_sidecar_still_reports_malformed(self):
        """反向对照：侧车真写坏了仍是 verdict_malformed（那条提示"去补 JSON"是对的）。"""
        rep = self._gate_sidecar("D")
        data = json.loads(rep.with_suffix(".verdict.json").read_text(encoding="utf-8"))
        data["stage"] = "audit"                       # 身份对不上
        rep.with_suffix(".verdict.json").write_text(json.dumps(data, ensure_ascii=False),
                                                    encoding="utf-8")
        out = read_verdict(rep, "review", "D", allow_v2=True)
        self.assertEqual(out["status"], "UNVERIFIED")
        self.assertNotEqual(out["reason"], "verdict_stale")

    def test_enforce_passes_a_stale_verdict_through_untouched(self):
        """enforce 绝不能把「过期」改写成「去补 .verdict.json」—— 改 JSON 修不动
        「这份裁决是在另一套要求下算出来的」这件事。"""
        import content_quality
        stale = {"status": "UNVERIFIED", "reason": "verdict_stale", "issues": [],
                 "stale_issues": [{"id": "rv_x"}]}
        out = content_quality.enforce(self.root, "review", dict(stale),
                                      [s["id"] for s in self.s.STAGES])
        self.assertEqual(out["reason"], "verdict_stale")
        self.assertEqual([i["id"] for i in out["stale_issues"]], ["rv_x"])

    def test_stale_with_changed_report_offers_only_rerun(self):
        """被审报告**变了** → findings 指的文字已不在 → 只有重跑本门禁一条路。

        拿旧地图找新路没有意义：退了上游，它按 findings 去改，而 findings 说的那段
        文字在现在这份报告里根本不存在。
        """
        stage = self.stage("review")
        p = self.s._build_pending(
            stage, "failure", "stale", "门禁裁决过期",
            decision={"status": "UNVERIFIED", "reason": "verdict_stale", "issues": [],
                      "stale_issues": [{"id": "rv_x", "severity": "hard", "evidence": "e"}],
                      "stale_digest": {"recorded": "a:i", "current": "b:i",
                                       "artifacts_changed": True}})
        self.assertEqual(p["actions"], ["retry"], "正文变了就只能重判")
        self.assertIsNone(p["recommended"], "不该推荐任何上游阶段")
        self.assertEqual([i["id"] for i in p["issues"]], ["rv_x"],
                         "过期裁决查出来的东西必须在面板上看得见，不能丢")

    def test_stale_with_unchanged_report_still_allows_rollback(self):
        """只有做法要求/判据变了、**正文一个字没动** → findings 仍指着真实文字 → 退上游有意义。

        改一次 `skills/_references/` 就让在飞裁决作废、而上游报告没变 ——
        那种情况逼人重判 20+ 分钟纯属浪费，该把回退那条路留着。
        """
        stage = self.stage("review")
        p = self.s._build_pending(
            stage, "failure", "stale", "门禁裁决过期",
            decision={"status": "UNVERIFIED", "reason": "verdict_stale", "issues": [],
                      "stale_issues": [{"id": "rv_x", "severity": "hard", "evidence": "e"}],
                      "stale_digest": {"recorded": "a:i", "current": "a:j",
                                       "artifacts_changed": False}})
        self.assertIn("rollback", p["actions"], "正文没动，回退是有意义的一条路")
        self.assertEqual(p["recommended"], "analysis", "退回默认映射给的返修目标")
        self.assertEqual([i["id"] for i in p["issues"]], ["rv_x"])

    def _write_gate_sidecar(self, sid, check_ids, advisories=(), issues=(), failed=()):
        st = self.stage(sid)
        self.report(st, "整题门禁裁决：NEEDS_FIX")
        (self.root / "request").mkdir(exist_ok=True)
        (self.root / "request/problem.md").write_text("题面原文里有这句话", encoding="utf-8")
        # 每个 check 都要带 evidence 且**必须真的能核到**（`_evidence` 会去文件里找引文）——
        # 漏了会被 enforce 判 verdict_malformed，测试就测不到想测的那条规则。
        ev = [{"file": "request/problem.md", "quote": "题面原文里有这句话"}]
        (self.s.REPORTS / st["report"]).with_suffix(".verdict.json").write_text(json.dumps({
            "schema_version": 2, "stage": sid, "input_digest": self.s._input_digest(st),
            "status": "NEEDS_FIX", "issues": list(issues),
            "checks": [{"id": cid, "status": "failed" if cid in failed else "passed",
                        "reason": "checked", "evidence": ev} for cid in check_ids],
            "advisories": list(advisories)}, ensure_ascii=False), encoding="utf-8")
        return st

    def test_deferred_advisories_reach_an_upstream_stage_on_rollback(self):
        """指向上游的延后建议必须真能送到 —— 缺口在 `12Rubric-final` 上。

        `run_all` 的投递条件是 `any(s["id"] == dest for s in STAGES[index+1:])`（只发下游），
        而 rubric 允许 `optional` 的三类**全部指向上游**：`claim`→write(7)、
        `presentation`→format(8)、`diagram`→drawio(6)，而 rubric 是第 13 个（下标 12），
        `STAGES[13:]` 只剩 fix/demo —— 按这个条件一条都投不出去，这个机制就等于只有面板可见、从不落地。
        回退到被指的那个阶段，正是它唯一会再跑一次的时机。
        """
        (self.root / "config").mkdir(exist_ok=True)
        (self.root / "config/content_quality.json").write_text("{}", encoding="utf-8")
        self._write_gate_sidecar(
            "rubric",
            check_ids=["rubric_adaptation", "rubric_originality", "rubric_evidence",
                       "rubric_trace", "rubric_redline"],
            advisories=[{"id": "AD-1", "category": "presentation",
                         "evidence": "§11.7 仍写 R1–R13", "fix": "三处统一改 R1–R14",
                         "cost": "10 分钟"}])
        st = self.stage("rubric")
        hints = {"format": "基础回执", "write": "基础回执"}
        n = self.s._fold_in_deferred_advisories(hints, st, "format", "rubric")
        self.assertEqual(n, 1, "延后建议应当被投递出去")
        self.assertIn("改 R1–R14", hints["format"], "presentation→format，该落在 format 的 hint 里")
        self.assertIn("基础回执", hints["format"], "原有的返修回执不能被顶掉")
        self.assertEqual(hints["write"], "基础回执", "不该顺手塞给无关阶段")

    def test_advisory_for_a_stage_outside_the_rollback_path_is_not_misfiled(self):
        """反向对照：往 `write` 去的建议，在「回退到 format」这条路上不该塞给任何人。"""
        (self.root / "config").mkdir(exist_ok=True)
        (self.root / "config/content_quality.json").write_text("{}", encoding="utf-8")
        self._write_gate_sidecar(
            "rubric",
            check_ids=["rubric_adaptation", "rubric_originality", "rubric_evidence",
                       "rubric_trace", "rubric_redline"],
            advisories=[{"id": "AD-9", "category": "claim",
                         "evidence": "措辞过强", "fix": "加披露"}])
        st = self.stage("rubric")
        hints = {"format": "基础回执"}
        n = self.s._fold_in_deferred_advisories(hints, st, "format", "rubric")
        self.assertEqual(n, 0, "write 不在回退路径上，不该被硬塞")
        self.assertEqual(hints, {"format": "基础回执"}, "没人该被改到")

    def test_stale_findings_reach_the_producer_as_a_normal_receipt(self):
        """正文没动的过期裁决，投给回退目标时要**当普通回执**写下去。

        上游读的是 `issues`，而过期裁决的 issues 是空的（findings 在 `stale_issues` 里、
        不参与路由）—— 不转过去，上游就只拿到一份空壳回执，白跑。
        """
        stale = {"status": "UNVERIFIED", "reason": "verdict_stale", "issues": [],
                 "stale_issues": [{"id": "rv_x", "severity": "hard", "evidence": "e",
                                   "fix": "f", "recheck": "r"}],
                 "stale_digest": {"artifacts_changed": False}}
        self.assertTrue(self.s._has_actionable_feedback(stale), "正文没动 → 对上游就是真回执")
        stale_true = dict(stale, stale_digest={"artifacts_changed": True})
        self.assertFalse(self.s._has_actionable_feedback(stale_true),
                         "正文动了 → findings 可能已失效，不能包装成真回执")

    def test_full_wipe_archives_artifacts_and_receipts(self):
        """整链清空要把**产物和回执一起**收进 cache，否则新的一轮当场卡死。

        回执留在 `runtime/quality/feedback/` 里，而新的一轮 ② 建模设计 是**没有回执**的一轮 ——
        收尾自检 `check_receipts` 看到「有回执、没台账」，要它凭空交一份答旧回执的台账，
        全链在第 2 步挂起、白跑一遍。只清产物不清回执 = 把上一轮的语义泄漏进新一轮。
        """
        (self.root / "config").mkdir(exist_ok=True)
        (self.root / "config/content_quality.json").write_text("{}", encoding="utf-8")
        (self.root / "config/delivery.local.json").write_text(
            json.dumps({"output_dir": str(self.root / "产物"), "problem_id": "T"}),
            encoding="utf-8")
        R = self.s.REPORTS
        R.mkdir(parents=True, exist_ok=True)
        for name in ("LITERATURE_DIRECTION.md", "ANALYSIS_MODELING_REPORT.md",
                     "MODELING_REVIEW_REPORT.md"):
            (R / name).write_text("x" * 200, encoding="utf-8")
        for name in ("TASK_CONTRACT.json", "RECEIPT_LEDGER.json",
                     "MODELING_REVIEW_REPORT.verdict.json", "HIL_DECISION.md"):
            (R / name).write_text("{}", encoding="utf-8")
        fb = self.s.LOG_DIR / "quality/feedback/run1/abc"
        fb.mkdir(parents=True, exist_ok=True)
        (fb / "gate_decision.json").write_text(json.dumps({"issues": [{"id": "x"}]}),
                                               encoding="utf-8")

        # 先**挂上**一盏黄灯再清空，否则下面的断言是空的 ——
        #   fixture 里若没有 pending，`is None` 恒真，
        #   负对照跑出来居然是绿的（测试因为错误的理由通过）。
        self.s._set_pending({"stage": "review", "kind": "failure", "status": "stale",
                             "reason": "旧黄灯", "issues": []})
        self.s.state["halt_gate"] = True
        self.assertIsNotNone(self.s.state["pending"], "夹具应当先有黄灯")

        cleared = self.s._redo_from("literature")
        for must in ("reports/TASK_CONTRACT.json", "reports/RECEIPT_LEDGER.json",
                     "reports/MODELING_REVIEW_REPORT.verdict.json",
                     "runtime/quality/feedback", "reports/HIL_DECISION.md"):
            self.assertIn(must, cleared, f"{must} 没被收走")
        self.assertEqual(sorted(p.name for p in R.iterdir()), [], "reports/ 应当清空")
        self.assertIsNone(self.s.state.get("pending"), "清空后黄灯必须灭")
        self.assertFalse(self.s.state.get("halt_gate"), "清空后不该还挂着 halt")
        self.assertFalse((self.s.LOG_DIR / "quality/feedback").exists(), "回执该收进 cache")

        import receipt_ledger
        self.assertEqual(receipt_ledger.receipt_ledger_issues(self.root), [],
                         "全新一轮不该被上一轮的回执要求交台账")
        # 落点形状：cache/<题目标识_日期_时间>/<阶段中文名>/ + 回执/
        cache = self.root / "产物/cache"
        self.assertTrue(any(p.name == "建模设计" for p in cache.rglob("*")))
        self.assertTrue(any(p.name == "回执" for p in cache.rglob("*")))

    def test_partial_rollback_keeps_the_receipt(self):
        """反向对照：**局部回退**时那份回执正是 analysis 要答的 —— 收走了等于把回执弄丢。"""
        (self.root / "config").mkdir(exist_ok=True)
        (self.root / "config/delivery.local.json").write_text(
            json.dumps({"output_dir": str(self.root / "产物"), "problem_id": "T"}),
            encoding="utf-8")
        R = self.s.REPORTS
        R.mkdir(parents=True, exist_ok=True)
        (R / "ANALYSIS_MODELING_REPORT.md").write_text("x" * 200, encoding="utf-8")
        fb = self.s.LOG_DIR / "quality/feedback/run1/abc"
        fb.mkdir(parents=True, exist_ok=True)
        (fb / "gate_decision.json").write_text(json.dumps({"issues": [{"id": "x"}]}),
                                               encoding="utf-8")

        cleared = self.s._redo_from("analysis")          # 不是从第 0 步
        self.assertNotIn("runtime/quality/feedback", cleared)
        self.assertTrue((fb / "gate_decision.json").exists(), "局部回退必须留住回执")

    def clean_contract(self):
        """铺一份**过得了预检**的题意契约。

        必需：`_gate_decision` 对 review 先跑题意契约预检，不过就**短路返回
        `task_contract_failed`**，根本走不到 `read_verdict` —— 那样这两个用例测的
        就不是「裁决过期」了。契约是 review 的正常前置，铺上才是真实情形。
        """
        (self.root / "config").mkdir(exist_ok=True)
        (self.root / "config/content_quality.json").write_text("{}", encoding="utf-8")
        (self.root / "request").mkdir(exist_ok=True)
        (self.root / "request/problem.md").write_text("题面原文里有这句话", encoding="utf-8")
        self.s.REPORTS.mkdir(parents=True, exist_ok=True)
        (self.s.REPORTS / "ANALYSIS_MODELING_REPORT.md").write_text(
            "模型锚点句在此。\n", encoding="utf-8")
        (self.s.REPORTS / "TASK_CONTRACT.json").write_text(json.dumps({
            "schema_version": 1, "requirements": [{
                "id": "r1",
                "source": {"file": "request/problem.md", "quote": "题面原文里有这句话"},
                "source_semantics": {"quantifier": "each", "scope": "s", "unit": "u",
                                     "time_reference": "t"},
                "model_semantics": {"quantifier": "each", "scope": "s", "unit": "u",
                                    "time_reference": "t"},
                "model_anchor": {"file": "reports/ANALYSIS_MODELING_REPORT.md",
                                 "quote": "模型锚点句在此。"},
                "status": "mapped"}]}, ensure_ascii=False), encoding="utf-8")

    def test_revived_pending_is_recomputed_when_the_verdict_went_stale(self):
        """重启后复活的黄灯存着**旧裁决结论**（issues/target/actions 都是上次算的）。

        判据或驱动代码一变，那份裁决就作废了。按旧结论渲染会给出一个**做不成事的按钮**：
        推荐回退上游，而回退时交出去的回执其实是「裁决过期」，上游拿一句
        「去补 .verdict.json」白忙一场，那批真发现也随之丢弃。
        """
        self.clean_contract()
        st = self.stage("review")
        self.report(st, "整题门禁裁决：NEEDS_FIX")
        (self.s.REPORTS / "MODELING_REVIEW_REPORT.verdict.json").write_text(json.dumps({
            "schema_version": 2, "stage": "review", "input_digest": "旧指纹",
            "status": "NEEDS_FIX", "target": "analysis",
            "issues": [{"id": "rv_x", "severity": "hard", "evidence": "上游没改那个串",
                        "fix": "f", "recheck": "r"}]}, ensure_ascii=False), encoding="utf-8")
        self.s.PENDING_FILE.parent.mkdir(parents=True, exist_ok=True)
        self.s.PENDING_FILE.write_text(json.dumps({
            "stage": "review", "kind": "failure", "status": "blocked", "reason": "旧结论",
            "actions": ["retry", "rollback", "disclose"], "recommended": "analysis",
            "issues": []}, ensure_ascii=False), encoding="utf-8")

        self.s._load_pending()
        got = self.s.state["pending"]
        self.assertEqual(got["actions"], ["retry"], "过期裁决只能重跑本门禁，不该还推荐回退上游")
        self.assertIsNone(got["recommended"])
        self.assertEqual([i["id"] for i in got["issues"]], ["rv_x"],
                         "上一轮查出来的条目必须还在面板上")

    def test_a_healthy_pending_survives_a_restart_untouched(self):
        """反向对照：裁决没过期的黄灯必须**原样复活**，别把好黄灯也重算了。"""
        self.clean_contract()
        st = self.stage("review")
        self.report(st, "整题门禁裁决：NEEDS_FIX")
        (self.s.REPORTS / "MODELING_REVIEW_REPORT.verdict.json").write_text(json.dumps({
            "schema_version": 2, "stage": "review",
            "input_digest": self.s._input_digest(st),           # ← 指纹是新鲜的
            "status": "NEEDS_FIX", "target": "analysis",
            "issues": [{"id": "rv_x", "severity": "hard", "evidence": "e", "fix": "f",
                        "recheck": "r"}]}, ensure_ascii=False), encoding="utf-8")
        self.s.PENDING_FILE.parent.mkdir(parents=True, exist_ok=True)
        self.s.PENDING_FILE.write_text(json.dumps({
            "stage": "review", "kind": "failure", "status": "blocked", "reason": "原样",
            "actions": ["retry", "rollback", "disclose"], "recommended": "analysis",
            "issues": [{"id": "rv_x"}]}, ensure_ascii=False), encoding="utf-8")

        self.s._load_pending()
        got = self.s.state["pending"]
        self.assertEqual(got["reason"], "原样")
        self.assertIn("rollback", got["actions"])
        self.assertEqual(got["recommended"], "analysis")

    def test_gbk_evidence_file_is_readable(self):
        """GBK 写的中文产物不能再把门禁洗成 UNVERIFIED。

        Windows 中文环境下 agent 自写的 json/csv 常是 GBK；旧实现严格 utf-8-sig 解码抛
        UnicodeDecodeError → 被宽 except 吞成 verdict_malformed → 两轮后整链挂起，
        而 reason/evidence 里只留一句 codec 报错，人工看不出是编码问题。
        """
        from content_quality import _read_text
        p = self.root / "results" / "gbk.csv"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes("作物,面积\n豆类,0.3\n".encode("gbk"))
        self.assertIn("豆类", _read_text(p))

    def test_stale_handback_does_not_brick_chain_head(self):
        """上一轮遗留的 HANDBACK 不能把本轮全链顶死在第一个阶段。

        旧实现：check_handback 在每个阶段被无条件调用，而 _target_index 对 index >= cur_idx
        一律抛 ValueError —— 链首 cur_idx=0 时**任何** target 都满足，于是上一轮 write 按 SKILL
        交回 code 后残留的 HANDBACK 会让下一次「开始全链」在 ① 文献阶段就"驱动异常"挂起，
        每次重启 100% 复现，且 HIL_DECISION 给的三条建议都治不好（真·砖）。
        """
        self.s.HANDBACK.parent.mkdir(parents=True, exist_ok=True)
        self.s.HANDBACK.write_text("target: code", encoding="utf-8")
        calls = self.install_successful_runner()
        asyncio.run(self.s.run_all())
        self.assertTrue(self.s.state["run_completed"], self.s.state["halt_reason"])
        # 链从第一阶段正常起跑（⓪ 读题 现在排在它前面，它没有 inbox 时照跑、不拦链）
        self.assertEqual([c for c in calls if c != "intake"][0], "literature")
        self.assertFalse(self.s.HANDBACK.exists())            # 已归档，不再残留

    def test_write_handback_is_not_treated_as_failure(self):
        """9Paper-writing 按 SKILL 交回上游时本就不产 PDF，产物门禁不能把它判成失败。

        旧实现：_artifact_ok('write') 要求 paper/main.pdf，交回时必然没有 → 三次重试全失败 →
        挂起；而 HANDBACK 的唯一消费点在 run_stage **之后**，永远来不及被消费，正确动作
        （退回 code 补算）执行不到，还留下 HANDBACK 砖住下一轮。
        """
        st = self.stage("write")
        (self.root / "paper").mkdir(exist_ok=True)
        self.s.HANDBACK.parent.mkdir(parents=True, exist_ok=True)
        async def runner(prompt, sid, cap=None):
            self.s.HANDBACK.write_text("target: code\n理由：RESULTS_REPORT 数值不一致\n", encoding="utf-8")
            return 0, "", False                      # 按 SKILL 停写：没有产 PDF
        self.s._call = runner
        self.assertEqual(asyncio.run(self.s.run_stage(st)), "ok")

    def test_write_without_pdf_and_without_handback_still_fails(self):
        """反向护栏：既没产物也没交回，仍必须判失败（别把门禁放水）。"""
        st = self.stage("write")
        (self.root / "paper").mkdir(exist_ok=True)
        self.s._call = AsyncMock(return_value=(0, "", False))
        self.assertEqual(asyncio.run(self.s.run_stage(st)), "failed")

    def test_malformed_handback_blocks(self):
        def after(sid):
            if sid == "cross":
                self.s.HANDBACK.write_text("target: imaginary-stage")
        self.install_successful_runner(after=after)
        asyncio.run(self.s.run_all())
        # 这条不该断言 `_collect_outputs` 一次都没调 —— ⑨/⑭ 跑完会**阶段性**收一批
        #   （"已做好的先移入"），而这条用例里它们都成功跑过。
        #   这条用例要守的是：**没跑完的链不会收口**。
        self.assertFalse(self.s.state["run_completed"])
        self.assertTrue(self.s.state["halt_gate"])

    def test_actual_api_state_and_redo_conflict(self):
        from fastapi.testclient import TestClient
        client = TestClient(self.s.app)
        self.s.state.update(halt_gate=True, halt_reason="fixture", run_completed=False)
        response = client.get("/api/state")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["halt_reason"], "fixture")
        self.s.state["running"] = True
        self.assertEqual(client.post("/api/redo", json={"stage": "write"}).status_code, 409)

    def test_json_approval_cannot_override_markdown_failure(self):
        st = self.stage("verify")
        self.report(st, "最终结论：FAIL")
        data = {"schema_version": 1, "stage": "verify", "input_digest": self.s._input_digest(st),
                "status": "PASS", "issues": []}
        (self.s.REPORTS / st["report"]).with_suffix(".verdict.json").write_text(json.dumps(data))
        decision = self.s._gate_decision(st)
        self.assertNotEqual(self.s.gate_result(st), "ok")
        # 冲突取更保守的非 PASS 并记冲突项（而非整条 UNVERIFIED，避免丢掉诊断+整段重跑）
        self.assertEqual(decision["reason"], "verdict_conflict")
        self.assertEqual(decision["status"], "FAIL")

    def enable_strict(self):
        (self.root / "config").mkdir(exist_ok=True)
        (self.root / "config/content_quality.json").write_text("{}", encoding="utf-8")
        (self.root / "docs").mkdir(exist_ok=True)
        (self.root / "docs/CONTENT_QUALITY.md").write_text("# fixture", encoding="utf-8")
        (self.root / "request").mkdir(exist_ok=True)
        (self.root / "request/problem.md").write_text(
            "题面：其他作物每年相对2023约±5%变化。", encoding="utf-8")

    def write_contract(self, stage):
        quote = "每年相对2023约±5%变化"
        contract = {"schema_version": 1, "requirements": [{
            "id": "demand",
            "source": {"file": "request/problem.md", "quote": quote},
            "source_semantics": {"quantifier": "each", "scope": "each crop", "unit": "kg",
                                 "time_reference": "fixed_base"},
            "model_semantics": {"quantifier": "each", "scope": "each crop", "unit": "kg",
                                "time_reference": "fixed_base"},
            "model_anchor": {"file": "reports/" + stage["report"], "quote": "整题门禁裁决"},
            "status": "mapped"}]}
        (self.s.REPORTS / "TASK_CONTRACT.json").write_text(
            json.dumps(contract, ensure_ascii=False), encoding="utf-8")
        return quote

    def test_strict_content_quality_path_end_to_end(self):
        """补上此前零覆盖：strict 开关 + 题意契约前置 + v2 侧车，全程走 _gate_decision。"""
        self.enable_strict()
        st = self.stage("review")
        self.report(st, "整题门禁裁决：APPROVED")
        # 无题意契约 → 必须先回 analysis 补契约（裁决还没被读）
        self.assertEqual(self.s.gate_result(st), "NEEDS_FIX")
        self.assertEqual(self.s._gate_decision(st)["target"], "analysis")
        # 写契约 + v2 侧车 → 放行
        quote = self.write_contract(st)
        checks = [{"id": cid, "status": "passed", "reason": "checked",
                   "evidence": [{"file": "request/problem.md", "quote": quote}]}
                  for cid in self.s.CONTENT_CHECKS["review"]]
        sidecar = (self.s.REPORTS / st["report"]).with_suffix(".verdict.json")
        sidecar.write_text(json.dumps({"schema_version": 2, "stage": "review",
                                       "input_digest": self.s._input_digest(st),
                                       "status": "APPROVED", "issues": [], "checks": checks},
                                      ensure_ascii=False), encoding="utf-8")
        self.assertEqual(self.s.gate_result(st), "ok")

    def test_markdown_json_conflict_is_reported_not_silently_passed(self):
        """正文裁决与侧车冲突：判 UNVERIFIED 并要求重产一致裁决，不得原样放行侧车 status/target。"""
        self.enable_strict()
        st = self.stage("review")
        self.report(st, "整题门禁裁决：REVISE")
        self.write_contract(st)
        checks = [{"id": cid, "status": "passed", "reason": "checked",
                   "evidence": [{"file": "request/problem.md", "quote": "每年相对2023约±5%变化"}]}
                  for cid in self.s.CONTENT_CHECKS["review"]]
        sidecar = (self.s.REPORTS / st["report"]).with_suffix(".verdict.json")
        sidecar.write_text(json.dumps({"schema_version": 2, "stage": "review",
                                       "input_digest": self.s._input_digest(st),
                                       "status": "APPROVED", "issues": [], "checks": checks,
                                       "target": "code"}, ensure_ascii=False), encoding="utf-8")
        decision = self.s._gate_decision(st)
        self.assertEqual(decision["reason"], "verdict_conflict")
        self.assertEqual(decision["status"], "UNVERIFIED")
        self.assertNotIn("target", decision)                    # 不采用 agent 侧车的 target
        self.assertIn("REVISE", str(decision["issues"]))        # 诊断写明两侧状态
        self.assertEqual(self.s.gate_result(st), "UNVERIFIED")

    def test_conflict_cannot_be_waved_as_claim_revision(self):
        """冲突且侧车写 REVISE_CLAIM（audit）→ 不得当成有条件放行。"""
        self.enable_strict()
        st = self.stage("audit")
        self.report(st, "整题门禁裁决：PASS")
        self.write_contract(st)
        sidecar = (self.s.REPORTS / st["report"]).with_suffix(".verdict.json")
        sidecar.write_text(json.dumps({"schema_version": 2, "stage": "audit",
                                       "input_digest": self.s._input_digest(st),
                                       "status": "REVISE_CLAIM",
                                       "issues": [{"id": "x", "severity": "hard", "evidence": "e",
                                                   "fix": "f", "recheck": "r"}]},
                                      ensure_ascii=False), encoding="utf-8")
        self.assertNotEqual(self.s.gate_result(st), "claim_revision")
        self.assertEqual(self.s.gate_result(st), "UNVERIFIED")

    def test_code_fingerprint_is_deterministic_across_processes(self):
        """指纹必须跨进程稳定，否则每次启动都判门禁失效、白重跑。"""
        import subprocess
        code_type = type((lambda: None).__code__)
        self.assertEqual(self.s._canon({3, 1, 2}, code_type), self.s._canon({2, 3, 1}, code_type))
        script = ("import sys; sys.path.insert(0, 'lib/web'); sys.argv=['x']; import server; "
                  "print(server._prompt_fingerprint(), server._gate_logic_fingerprint())")
        # 这是全仓**唯一**一处跑真 server.py 的子进程（其余都走 `load_server` 的 AST 改写，
        #   那会把 ROOT 与 CLAUDE 换掉）。而真 server.py 在 import 期就会 `_find_claude()`
        #   —— 一台没装 VSCode Claude 扩展、PATH 里也没有 claude 的机器上它会 `SystemExit`
        #   ⇒ 子进程 rc≠0、stdout 为空 ⇒ 最后那句 `assertTrue("")` 红。显式喂一个存在的路径
        #   即可（`_find_claude` 只要求 `p.exists()`，不校验它是不是真 claude），
        #   断言的内容（两个指纹跨进程一致）不受影响。
        #   注意别去掉 `cwd=str(PROJECT)`：脚本里 `sys.path.insert(0,'lib/web')` 是相对路径。
        env = {**os.environ, "WEBDRIVER_CLAUDE": sys.executable}
        outs = {subprocess.run([sys.executable, "-c", script], cwd=str(PROJECT), env=env,
                               capture_output=True, text=True,
                               encoding="utf-8", errors="replace").stdout.strip()
                for _ in range(2)}
        self.assertEqual(len(outs), 1, outs)
        self.assertTrue(outs.pop().strip())

    def test_input_digest_is_stage_scoped(self):
        lit, wr = self.stage("literature"), self.stage("write")
        before_lit, before_wr = self.s._input_digest(lit), self.s._input_digest(wr)
        (self.root / "config").mkdir(exist_ok=True)
        (self.root / "config/publication.json").write_text("{}", encoding="utf-8")
        self.assertEqual(self.s._input_digest(lit), before_lit)      # 与 literature 无关
        self.assertNotEqual(self.s._input_digest(wr), before_wr)     # write 受影响

    def test_prompt_and_gate_logic_fingerprints_invalidate_right_stages(self):
        gate, nongate = self.stage("review"), self.stage("analysis")
        base_gate, base_nongate = self.s._input_digest(gate), self.s._input_digest(nongate)
        # 注入指令变化 → 所有阶段失效（新指令必须送达 agent）
        self.s._prompt_fingerprint = lambda: "changed"
        self.assertNotEqual(self.s._input_digest(gate), base_gate)
        self.assertNotEqual(self.s._input_digest(nongate), base_nongate)
        # 门禁裁决逻辑变化 → 只让门禁阶段失效
        self.s._prompt_fingerprint = lambda: ""
        g0, n0 = self.s._input_digest(gate), self.s._input_digest(nongate)
        self.s._gate_logic_fingerprint = lambda: "changed"
        self.assertNotEqual(self.s._input_digest(gate), g0)
        self.assertEqual(self.s._input_digest(nongate), n0)

    def test_protocol_repair_keeps_report_and_uses_short_cap(self):
        st = self.stage("review")
        self.report(st, "整题门禁裁决：APPROVED")
        (self.s.REPORTS / st["report"]).with_suffix(".verdict.json").write_text("{}", encoding="utf-8")
        report = self.s.REPORTS / st["report"]
        # 仅"报告已写好、只缺合法 v2 侧车"才走轻量补写
        self.assertTrue(self.s._protocol_repair(
            {"reason": "verdict_malformed",
             "issues": [{"evidence": "内容审查需要 version 2 结构化裁决（含 checks 与 typed issues）"}]}, report))
        # 引文不实 / md-json 冲突 → 必须整段重审，不得只补侧车
        self.assertFalse(self.s._protocol_repair(
            {"reason": "verdict_malformed",
             "issues": [{"evidence": "Evidence quote does not match source: x.md"}]}, report))
        self.assertFalse(self.s._protocol_repair({"reason": "verdict_conflict"}, report))
        self.assertFalse(self.s._protocol_repair({"reason": "structured"}, report))
        caps = []

        async def runner(prompt, sid, cap=None):
            caps.append(cap)
            return 0, "", False          # 不重写报告：验证报告本体未被暂存
        self.s._call = runner
        asyncio.run(self.s.run_stage(st, round_hint="只补侧车", repair_only=True))
        self.assertEqual((self.s.REPORTS / st["report"]).read_text(encoding="utf-8"),
                         "整题门禁裁决：APPROVED\n" + "evidence " * 30)
        self.assertEqual(caps, [self.s.CALL_PROTOCOL_CAP])


    # ---------------- 人工决策（黄灯）----------------

    def test_effective_limits_pure(self):
        """超时上限纯函数：默认 / 用户覆盖 / 协议修复优先级。"""
        s = self.s
        s.state["retry_cap"] = {}
        # 不延长时的默认上限是 RETRY_CAP_DEFAULT（30 分钟）—— 不是那个总天花板。
        #   两者若共用一个常量（都是 1800），「延长」就永远延不出去。
        # 默认上限**按阶段取**（`_default_cap`）：④ 有自己的值（固有耗时约 52 min），
        #   其余阶段仍是全局默认 —— 这里跟着那个单一出处走，别再写死 RETRY_CAP_DEFAULT。
        self.assertEqual(s._effective_limits("code"), (s._default_cap("code"), s.STALL_SILENT))
        self.assertEqual(s._effective_limits("code", has_conn=True),
                         (s._default_cap("code"), s.STALL_CONN))
        s.state["retry_cap"]["code"] = 1500
        # 延长只抬**墙钟上限**，假死容忍**不跟着走**（两者解耦）。
        #   绑在一起时，一个真·死进程要等满上限才被发现；而上限现在能追加到 3 小时。
        #   解耦的代价如实认：慢但在等 API 的阶段会每 STALL_CONN 亮一次黄灯问一次。
        self.assertEqual(s._effective_limits("code"), (1500, s.STALL_SILENT))
        self.assertEqual(s._effective_limits("code", has_conn=True), (1500, s.STALL_CONN))
        # 天花板现在**高于**默认值：延长累积到 2400 秒应当照数生效（旧实现会被夹回 1800）
        s.state["retry_cap"]["code"] = 2400
        self.assertEqual(s._effective_limits("code"), (2400, s.STALL_SILENT))
        self.assertGreater(s.RETRY_CAP_MAX, s.RETRY_CAP_DEFAULT,
                           "总天花板必须高于默认上限，否则「延长」根本延不出去")
        # 超过天花板的覆盖值仍然被夹住（接口层本来就该拒，这里是兜底）
        s.state["retry_cap"]["code"] = s.RETRY_CAP_MAX + 9999
        self.assertEqual(s._effective_limits("code"), (s.RETRY_CAP_MAX, s.STALL_SILENT))
        # 协议级修复的短上限优先于用户覆盖（格式修复不该被延长到几小时）
        self.assertEqual(s._effective_limits("code", cap=s.CALL_PROTOCOL_CAP)[0], s.CALL_PROTOCOL_CAP)

    def test_gate_strings_agree_with_default_repair_map(self):
        """STAGES[].gate 的 `X->y` 与默认回退映射必须一一吻合。

        gate 字符串本身从不被解析（装饰性），但两处说法不一致会误导读代码的人 ——
        用测试把「单一事实来源」钉住，而不是在中断路径上引入解析器。
        """
        for st in self.s.STAGES:
            g = st.get("gate")
            if not g or "->" not in g:
                continue
            self.assertEqual(self.s._default_repair_target(st["id"]), g.split("->", 1)[1].strip(),
                             f"{st['id']} 的 gate={g!r} 与默认回退映射不一致")

    def test_disclose_waives_stage_and_expires_on_input_change(self):
        """披露必须落成机器可读的豁免；输入一变豁免自动失效、门禁重新生效。"""
        calls = self.install_successful_runner({"audit": 1})
        s = self.s
        asyncio.run(s.run_all())
        self.assertEqual(s.state["pending"]["stage"], "audit")
        asyncio.run(s._apply_decision(s.DecisionReq(action="disclose", note="残余增益极小")))
        self.assertIn("audit", s._load_waivers())
        res = (s.REPORTS / "_KNOWN_WRITING_RESIDUALS.md").read_text(encoding="utf-8")
        self.assertIn("[HIL-DISCLOSE", res)          # 必须可与人写的章节区分
        calls.clear()
        asyncio.run(s.run_all())
        self.assertEqual(calls.count("audit"), 0)    # 豁免放行 → 零模型调用
        self.assertTrue(s.state["run_completed"])
        self.assertEqual(s.state["stages"]["audit"], "done(disclosed)")
        # 改动上游输入 → 豁免立即失效
        (self.root / "request").mkdir(exist_ok=True)
        (self.root / "request/problem.md").write_text("changed problem")
        calls.clear()
        asyncio.run(s.run_all())
        self.assertGreater(calls.count("audit"), 0, "输入变了之后豁免必须失效、该阶段必须重跑")

    def test_attest_recertifies_edited_artifact_without_rerunning_producer(self):
        """人工改好产物后 attest：**生产阶段不重跑**，链从其后继续，且留下可追的审计痕。

        这是「回执答『盘面变了没有』，而人工修正恰恰让答案是『变了』」那个反直觉缺陷的解法：
        重跑会推翻人工修正，所以必须有一个显式的「以当前盘面重新认证」的动作。
        """
        calls = self.install_successful_runner({"audit": 1})
        s = self.s
        asyncio.run(s.run_all())
        self.assertEqual(s.state["pending"]["stage"], "audit")

        # 模拟人手工修正建模产物（audit 的上游）
        self.report(self.stage("analysis"), "最终结论：人工修正后的建模报告")

        # 驱动应能识别出「analysis 的产物被改过」，并把它作为 attest 的默认目标
        p = s._build_pending(self.stage("audit"), "failure", "blocked", "复核")
        self.assertIn("attest", p["actions"])
        self.assertEqual(p["attest_default"], "analysis")
        self.assertTrue(next(c for c in p["candidates"]
                             if c["id"] == "analysis")["out_changed"])

        r = asyncio.run(s._apply_decision(
            s.DecisionReq(action="attest", stage="analysis", note="人工定点修正")))
        self.assertTrue(r["ok"])
        self.assertEqual(r["attested"], "analysis")
        self.assertEqual(s.state["stages"]["analysis"], "done(manual)")   # 不是干净的 done
        self.assertTrue((self.root / r["trail"]).is_file())               # 留痕
        import json as _json
        trail = _json.loads((self.root / r["trail"]).read_text(encoding="utf-8"))
        self.assertEqual(trail["note"], "人工定点修正")
        self.assertIn("reports/ANALYSIS_MODELING_REPORT.md", trail["artifacts"])

        calls.clear()
        asyncio.run(s.run_all())
        self.assertNotIn("analysis", calls)          # 生产阶段零重跑 —— 人工修正没被推翻
        self.assertIn("review", calls)               # 上游变了 → 门禁重判（便宜，且应该重判）
        self.assertGreater(calls.count("audit"), 0)

    def test_instruction_change_marks_stale_instead_of_rerunning_expensive_stages(self):
        """改「做法要求」（SKILL/规范/CLAUDE.md/注入指令）**不该**让贵的生产阶段从零重跑。

        若把产物类输入与指令类输入混在同一个 digest 里：改一个错别字 = 全链重跑
        （code 一步就是小时级），而且**人手工认证过的产物也会被一句话推翻** ——
        那正好把 attest（治"agent 幻觉改不过"的那味药）自己的出口堵死。

        判据：只有「产物所依据的事实」变了才自动重做；做法要求变了只标 `done(stale-instr)`
        + 记进 `state["stale_instr"]`，由人决定要不要按新要求重来。**门禁也走这条路**
        —— 把门禁排除在外是自相矛盾的：既然承认「字节层面
        分不清错别字与判据变更」，就不该对门禁假定分得清。否则代价很具体：加一条**只管
        论文措辞**的规矩，会把 ③ 建模评审门禁整段拉起来真重判。
        """
        calls = self.install_successful_runner()
        s = self.s
        asyncio.run(s.run_all())
        self.assertTrue(s.state["run_completed"], s.state["halt_reason"])

        # 改一处**做法要求**：工作区说明（CLAUDE.md 在各阶段的 instructions 里）
        (self.root / "CLAUDE.md").write_text("# 改了说明\n")
        calls.clear()
        asyncio.run(s.run_all())
        self.assertTrue(s.state["run_completed"], s.state["halt_reason"])
        # 贵的生产阶段与**门禁**一个都没重跑。
        # 这条要按新的**因果链**读（不是把守卫放松）：
        #   新顺序里 14Layout-and-format 排在 13Repair-by-rubric-verdict **之后**，而它会改 `paper/`
        #   ⇒ 13Repair 消费过的事实变了 ⇒ 它必然被判失效 ⇒ 连带 re-run fix→format→verify→demo
        #   这一条**产物因果链**。
        #   这不是"改说明害的"，而是"编辑者排在消费者之后"的固有代价 —— 所以这条守卫
        #   只对**不在该链上**的阶段断言"一个都不许重跑"，并另加一条钉住链上的稳态。
        for sid in ("analysis", "code", "robustness", "write",
                    "review", "audit", "figreview", "mathproof", "cross", "rubric"):
            self.assertNotIn(sid, calls, f"{sid} 不该因为改了说明就重跑/重判")
        # **产物因果链不存在** —— 门禁的裁决侧车若记的是「这条裁决是在哪版输入上算的」，
        #   改一处说明就会让它的 instructions 半份变 ⇒ 判"过期"
        #   ⇒ 重判 ⇒ 连带把 `fix→format→verify→demo` 那一串带起来。现在门禁裁决也享受
        #   「只有做法要求变了 ⇒ 不重判」（与回执同口径，见 `lib/web/server.py::_gate_decision`
        #   的 `_read_sidecar_digest`）⇒ 改一处说明**一个阶段都不重跑**；它们被如实标成
        #   `done(stale-instr)`（面板蓝条看得见）。
        self.assertEqual(calls, [], f"改说明不该让任何阶段重跑（含判官），实际 {calls}")
        self.assertIn("verify", s.state["stale_instr"], "被标记出来、人看得见")
        # 但它们被标记出来了，人看得见（面板那条蓝条列的就是 stale_instr）
        for sid in ("code", "review"):
            self.assertIn(sid, s.state["stale_instr"])
            self.assertEqual(s.state["stages"][sid], "done(stale-instr)",
                             f"{sid} 该被标成「按旧要求交付」等人决定")

    def test_artifact_change_still_reruns_downstream(self):
        """反向对照：改**产物所依据的事实**仍然照旧自动重做 —— 宽待不能越界。"""
        calls = self.install_successful_runner()
        s = self.s
        asyncio.run(s.run_all())
        self.assertTrue(s.state["run_completed"], s.state["halt_reason"])

        calls.clear()
        (s.REPORTS / "RESULTS_REPORT.md").write_text(
            "最终结论：PASS\n换了结果\n" + "evidence " * 30, encoding="utf-8")
        asyncio.run(s.run_all())
        self.assertIn("code", calls, "产物本身被改了，code 必须重跑")
        self.assertNotIn("code", s.state["stale_instr"], "这是产物变更，不是指令变更，不该进 stale_instr")

    def test_a_gate_still_reruns_when_its_facts_change(self):
        """反向守卫：**事实**（被审对象）变了，门禁仍必须自动重判。

        与上一条一起把口径夹住：**做法要求**变了只标记、
        **事实**变了照旧自动重跑 —— 后者是「论文里的数与你交出去的代码不是一回事」
        的唯一防线，不许被「只标记」顺手吞掉。
        """
        calls = self.install_successful_runner()
        s = self.s
        asyncio.run(s.run_all())
        self.assertTrue(s.state["run_completed"], s.state["halt_reason"])

        calls.clear()
        # 改一件**在每个阶段的事实半份里、且没有任何阶段会重写**的东西（`plan.md`）。
        # 别拿 `reports/ANALYSIS_MODELING_REPORT.md` 试：那是 ② 的产物，而 mock runner
        #    会确定性地把它重写成同一份内容 ⇒ 门禁的输入又对上了，测试会假绿。
        (self.root / "plan.md").write_text("# 计划改了\n" + "x " * 50, encoding="utf-8")
        asyncio.run(s.run_all())
        self.assertIn("review", calls, "事实变了，门禁必须重判")
        self.assertNotIn("review", s.state["stale_instr"],
                         "这是事实变更、不是指令变更，不该进 stale_instr")

    def test_a_stale_gate_still_runs_the_mechanical_floor(self):
        """门禁被标 `stale` 之后，驱动自己的**机械地板**不许跟着停摆。

        那批审计是程序说了算的客观检查（题意契约 / 结构化结果 / 版式 / 图表 / 提交清单），
        便宜且不需要人。门禁若一走 `stale` 就早返回，它们会**整批停摆**；又因为那条路刻意
        不重存回执 ⇒ 之后每一轮都还是 stale ⇒ **永远不跑**。
        """
        calls = self.install_successful_runner()
        s = self.s
        asyncio.run(s.run_all())
        self.assertTrue(s.state["run_completed"], s.state["halt_reason"])

        # 同时做两件事：① 改一处「做法要求」（门禁本会只标记不重跑）；
        # ② 启用交付清单预检却不放清单（mock runner 不写它 ⇒ precheck 必然失败）
        (self.root / "CLAUDE.md").write_text("# 改了说明\n")
        (self.root / "config").mkdir(exist_ok=True)
        (self.root / "config/delivery.local.json").write_text(
            json.dumps({"output_dir": "", "problem_id": "2026A"}), encoding="utf-8")

        calls.clear()
        asyncio.run(s.run_all())
        self.assertIn("verify", calls,
                      "地板不过却走了 stale 近路 —— ⑬ 的提交清单预检就永远不会跑")
        self.assertTrue(s.state["halt_gate"], "地板不过应当亮黄灯，而不是静默放行")

    def test_the_stale_mark_survives_a_restart(self):
        """「按旧要求交付」的标记必须熬过重启。

        `state["stale_instr"]` 是**内存态**，而 `done(stale-instr)` 在回执里是**持久态** ——
        重启后若不从回执反推回来，面板会写成「已完成交付」、那条蓝条消失，
        于是「这是按旧要求做的、要不要按新要求重来」这个**唯一的可见痕迹**没了。
        """
        self.install_successful_runner()
        s = self.s
        asyncio.run(s.run_all())
        (self.root / "CLAUDE.md").write_text("# 改了说明\n")
        asyncio.run(s.run_all())
        self.assertIn("analysis", s.state["stale_instr"])

        s2 = load_server(self.root)          # 同一 root 重新 exec = 模拟重启
        self.assertIn("analysis", s2.state["stale_instr"],
                      "重启后标记丢了 —— 蓝条消失，而阶段还挂着「按旧要求交付」")
        self.assertEqual(s2.state["stages"]["analysis"], "done(stale-instr)")
        # 真正的不变量：反推出来的集合必须与链上当时算的**完全一致**。
        #   （别拿「某个阶段不在里面」当守卫 —— `CLAUDE.md` 在每个阶段的 instructions 里，
        #   改它之后**所有有回执的阶段**都该被标记，挑一个出来断言「不在」是错的。）
        self.assertEqual(set(s2.state["stale_instr"]), set(s.state["stale_instr"]),
                         "重启后反推的标记集合与链上算的不一致")

    def test_an_instruction_change_does_not_rewrite_the_paper(self):
        """改「做法要求」不许让 ⑨ 整篇重写。

        ⑨ 的产物（`paper/` + `paper_appendix/`）会被**下游合法改写**（⑩ 排版、⑮ 按评分判词返修），
        所以它的 `outputs` 半份**必然**对自己的回执失配 —— 走不到 `stale` 那条近路。
        只认 ⑩ `format` 一家接管的话，链在 ⑩ 的收尾复验之前断掉、或 ⑮ 改过 `paper/` 时，
        这条失效 ⇒ **⑨ 真的整篇重写**（小时级，而且推翻下游的版式/返修成果）。
        """
        calls = self.install_successful_runner()
        s = self.s
        asyncio.run(s.run_all())
        self.assertTrue(s.state["run_completed"], s.state["halt_reason"])

        (self.root / "CLAUDE.md").write_text("# 改了说明\n")
        calls.clear()
        asyncio.run(s.run_all())
        self.assertNotIn("write", calls,
                         "改了做法要求却把 ⑨ 整篇重写了 —— 它会推翻下游的版式/返修成果")
        self.assertIn("write", s.state["stale_instr"], "该如实标出「按旧要求交付」")

    def test_the_paper_is_not_rewritten_when_the_owner_is_only_instruction_stale(self):
        """改一条**共享的**做法要求之后，⑨ 不许整篇重写。

        接管分支若用**整份** digest 判「拥有者（⑩/⑮）的回执有效」—— `CLAUDE.md`
        一变，拥有者自己的回执**也失配** ⇒ 接管必然落空 ⇒ ⑨ 整篇重写（小时级，且推翻
        下游的版式/返修成果）。判据改成「它的**产物**还没被动过」（只比事实半份）才堵得住。

        夹具注意：**必须让 ⑩ 真的写 `paper/`**。默认的 mock runner 只给 ⑨ 写 `paper/`，
        于是 ⑨ 的 `outputs` 从不变 ⇒ 走的是 `stale` 近路、**根本到不了接管分支** ⇒
        这条测试会恒真（两版都绿也说明不了问题）。真实现里 ⑩ 排版精修**就是**会改
        `paper/` 的。
        """
        def after(sid):
            if sid == "format":              # ⑩ 版式精修：真实现会改 paper/ 下的源文件
                (self.root / "paper/main.tex").write_text("% 版式精修\n", encoding="utf-8")

        calls = self.install_successful_runner(after=after)
        s = self.s
        asyncio.run(s.run_all())
        self.assertTrue(s.state["run_completed"], s.state["halt_reason"])

        (self.root / "CLAUDE.md").write_text("# 改了说明\n")     # 共享的做法要求变了
        calls.clear()
        asyncio.run(s.run_all())
        self.assertNotIn("write", calls,
                         "⑩ 只是改了版式、而做法要求变了 ⇒ ⑨ 不该整篇重写把它推翻")
        self.assertIn("write", s.state["stale_instr"], "该如实标出「按旧要求交付」")

    def test_stale_instr_cleared_once_stage_really_reruns(self):
        """按新要求重跑之后，`stale-instr` 标记必须消失（否则面板永远挂着旧提示）。"""
        self.install_successful_runner()
        s = self.s
        asyncio.run(s.run_all())
        (self.root / "CLAUDE.md").write_text("# 改了说明\n")
        asyncio.run(s.run_all())
        self.assertIn("analysis", s.state["stale_instr"])
        # 真的重跑 analysis（清掉它的回执 → 下一轮没有回执可复用 → 走正常执行路径）
        s._receipt_store().invalidate(["analysis"])
        asyncio.run(s.run_all())
        self.assertNotIn("analysis", s.state["stale_instr"])

    def test_attest_refused_while_chain_is_running(self):
        """attest 不能在链正在跑时执行 —— 它会起**第二条链**，两条共享同一份 state。

        `_do_attest` 一律返回 resumed=True，端点据此再起一条 run_all；而 run_all 既不看
        `state["running"]`、一进来又把所有阶段重置为 idle。两条路都会中招：
        无黄灯时（CLI/API）与**超时黄灯**时（那时链确实还在跑，正是超时黄灯的定义）。
        """
        self.install_successful_runner()
        s = self.s
        asyncio.run(s.run_all())
        s.state["pending"] = None
        s.state["running"] = True
        with self.assertRaises(Exception) as cm:
            asyncio.run(s._apply_decision(s.DecisionReq(action="attest", stage="analysis")))
        self.assertIn("正在运行", str(cm.exception))
        # 超时黄灯同样拦住
        s.state["pending"] = {"stage": "code", "kind": "overtime", "status": "overtime",
                              "reason": "x", "actions": ["retry", "extend", "attest"],
                              "recommended": None, "candidates": [], "issues": [],
                              "retry_cap_default": 10800, "attest_default": "analysis"}
        with self.assertRaises(Exception) as cm:
            asyncio.run(s._apply_decision(s.DecisionReq(action="attest", stage="analysis")))
        self.assertIn("正在运行", str(cm.exception))

    def test_format_takeover_keeps_manual_marker(self):
        """被 14Layout-and-format 接管时，write 的「人工认证」标记必须活下来。

        那条分支若返回 "ok"，会落进 run_all 的公共尾巴、被 `_save_receipt()`（默认
        manual=False）抹掉 —— 回执就退化成 `done`，面板从此把「人放行的」画成
        「干净通过」，正是前端明确禁止的撒谎。
        """
        root = self.root
        n = {"i": 0}

        def after(sid):                      # format 每次真跑都改一次 paper/
            if sid == "format":
                n["i"] += 1
                (root / "paper").mkdir(exist_ok=True)
                (root / "paper/body.tex").write_text(f"% 版式精修 {n['i']}\n")

        self.install_successful_runner(after=after)
        s = self.s
        asyncio.run(s.run_all())
        (root / "paper/body.tex").write_text("% 人手修正的正文\n")
        r = asyncio.run(s._apply_decision(s.DecisionReq(action="attest", stage="write",
                                                        note="手工定稿")))
        self.assertTrue(r["ok"])
        for i in (2, 3, 4):                  # 第 3 轮正是「被 format 接管」生效的那一轮
            asyncio.run(s.run_all())
            self.assertEqual(s.state["stages"]["write"], "done(manual)", f"第 {i} 轮退化了")
            self.assertTrue(s._receipt_store().is_manual("write"), f"第 {i} 轮回执标记丢了")

    def test_attest_marker_survives_resume_and_rechain(self):
        """`done(manual)` 必须活过 `run_all` —— 否则前端那个「人工认证」标记永远画不出来。

        两个覆盖点都要防：
          ① `run_all` 开头把所有阶段重置成 idle；
          ② 成功路径会 `_receipt_store().save(...)`（默认 manual=False），把回执里的认证标记抹掉。
        这里把「认证 → 再跑一次链」整条走一遍，断言状态与回执标记都还在。
        """
        calls = self.install_successful_runner()
        s = self.s
        asyncio.run(s.run_all())
        self.assertTrue(s.state["run_completed"])

        r = asyncio.run(s._apply_decision(
            s.DecisionReq(action="attest", stage="analysis", note="手工核对")))
        self.assertTrue(r["ok"])
        self.assertEqual(s.state["stages"]["analysis"], "done(manual)")

        # 再跑一条链：analysis 应被复用，且标记不能退化
        calls.clear()
        asyncio.run(s.run_all())
        self.assertEqual(s.state["stages"]["analysis"], "done(manual)")
        self.assertNotIn("analysis", calls)
        self.assertTrue(s._receipt_store().is_manual("analysis"),
                        "回执里的 manual 标记被成功路径的 save 抹掉了")

    def test_attest_works_without_pending(self):
        """没有黄灯也能认证（CLI 路径）—— 但必须显式给 --stage。"""
        self.install_successful_runner()
        s = self.s
        asyncio.run(s.run_all())
        # ① 不给 stage → 400
        with self.assertRaises(Exception) as cm:
            asyncio.run(s._apply_decision(s.DecisionReq(action="attest", note="x")))
        self.assertIn("--stage", str(cm.exception))
        # ② 给了 stage 就照办（此时 state["pending"] 是 None）
        self.assertIsNone(s.state["pending"])
        r = asyncio.run(s._apply_decision(
            s.DecisionReq(action="attest", stage="code", note="手工跑完脚本")))
        self.assertTrue(r["ok"])
        self.assertEqual(r["attested"], "code")
        # ③ 其余动作在没有 pending 时仍然 409
        with self.assertRaises(Exception) as cm:
            asyncio.run(s._apply_decision(s.DecisionReq(action="retry")))
        self.assertIn("没有待决策项", str(cm.exception))

    def test_attest_rejects_gate_and_missing_artifact(self):
        """attest 的两道硬门：不许认证门禁阶段，不许对不存在的产物认证。

        第 ③ 步是**反向对照** —— 没有它，前两条可能只是「永远拒绝」的假绿。
        """
        self.install_successful_runner({"audit": 1})
        s = self.s
        asyncio.run(s.run_all())
        self.assertEqual(s.state["pending"]["stage"], "audit")
        # 人先改了产物，attest 才有默认目标可算
        self.report(self.stage("analysis"), "最终结论：人工修正后的建模报告")

        # ① 门禁阶段：review 已跑过且带 gate
        with self.assertRaises(Exception) as cm:
            asyncio.run(s._apply_decision(s.DecisionReq(action="attest", stage="review")))
        self.assertIn("门禁", str(cm.exception))

        # ② 产物不在盘上的阶段
        (s.REPORTS / "ANALYSIS_MODELING_REPORT.md").unlink()
        with self.assertRaises(Exception) as cm:
            asyncio.run(s._apply_decision(s.DecisionReq(action="attest", stage="analysis")))
        self.assertIn("不在盘上", str(cm.exception))

        # ③ 反向对照：产物在盘上就真能认证
        self.report(self.stage("analysis"), "最终结论：人工修正后的建模报告")
        r = asyncio.run(s._apply_decision(
            s.DecisionReq(action="attest", stage="analysis", note="ok")))
        self.assertTrue(r["ok"])

    def test_retry_decision_resumes_without_reexecuting_done_stages(self):
        calls = self.install_successful_runner({"audit": 1})
        s = self.s
        asyncio.run(s.run_all())
        self.assertEqual(s.state["pending"]["stage"], "audit")
        # 单次**重试**给的限时被夹在 [RETRY_CAP_EXTRA_MIN, RETRY_CAP_EXTRA_MAX]：
        #   请求 7200 秒会被夹到 RETRY_CAP_EXTRA_MAX。长计算靠**迭代**续 —— 到点再亮黄灯，
        #   人看着实际进展决定「再延长」多少（那是**追加**，见 ExtendIsAdditiveTests）。
        #   假死容忍与此无关：它不跟限时走，封在 STALL_SILENT / STALL_CONN。
        #   断言直接对着**常量**，不写死具体数值 —— 否则一个数两处写，改一处必炸另一处。
        asyncio.run(s._apply_decision(s.DecisionReq(action="retry", extra_seconds=7200)))
        self.assertGreater(7200, s.RETRY_CAP_EXTRA_MAX, "夹具要点：请求值要**大于**上限才谈得上夹")
        self.assertEqual(s.state["retry_cap"].get("audit"), s.RETRY_CAP_EXTRA_MAX)
        self.assertIsNone(s.state["pending"])
        calls.clear()
        asyncio.run(s.run_all())
        self.assertTrue(s.state["run_completed"], s.state["halt_reason"])
        self.assertEqual(calls.count("audit"), 1)     # 恰好重跑 1 次
        self.assertNotIn("literature", calls)         # 前序回执未作废 → done(skip)，零重复

    def test_retry_hint_carries_previous_failure_output(self):
        """重试的 prompt 必须带上上次失败的原始输出，否则等于把同一个 prompt 再发一遍。"""
        s = self.s
        prompts, n_code = [], 0
        async def runner(prompt, sid, cap=None):
            nonlocal n_code
            prompts.append((sid, prompt))
            st = self.stage(sid)
            if sid == "audit":
                n_code += 1
                if n_code == 1:
                    return 1, "BOOM singular matrix at step 42", False
            if sid == "write":
                (self.root / "paper").mkdir(exist_ok=True)
                (self.root / "paper/main.pdf").write_bytes(b"%PDF-1.4\n" + b"fixture " * 20)
            else:
                self.report(st, "最终结论：PASS")
            if sid == "code":
                (self.root / "code").mkdir(exist_ok=True)
                (self.root / "code/x.txt").write_text("fixture")
            if st.get("gate"):
                (s.REPORTS / st["report"]).with_suffix(".verdict.json").write_text(json.dumps(
                    {"schema_version": 1, "stage": sid, "input_digest": s._input_digest(st),
                     "status": "PASS", "issues": []}))
            return 0, "", False
        s._call = runner
        asyncio.run(s.run_all())
        asyncio.run(s._apply_decision(s.DecisionReq(action="retry", note="换个求解器试试")))
        prompts.clear()
        asyncio.run(s.run_all())
        code_prompts = [p for sid, p in prompts if sid == "audit"]
        self.assertEqual(len(code_prompts), 1)
        self.assertIn("BOOM singular matrix at step 42", code_prompts[0])
        self.assertIn("换个求解器试试", code_prompts[0])

    def test_state_exposes_pending_and_decision_api_rejects(self):
        from fastapi.testclient import TestClient
        client = TestClient(self.s.app)
        s = self.s
        calls = self.install_successful_runner({"audit": 1})
        asyncio.run(s.run_all())
        body = client.get("/api/state").json()
        self.assertIn("pending", body)
        self.assertEqual(body["pending"]["stage"], "audit")
        self.assertIn("attempts", body)
        # 无 pending 时 409
        s._set_pending(None)
        self.assertEqual(client.post("/api/decision", json={"action": "retry"}).status_code, 409)
        # 恢复 pending 后：非法动作 400 / 非法目标 400
        s._set_pending(body["pending"])
        self.assertEqual(client.post("/api/decision", json={"action": "nonsense"}).status_code, 400)
        self.assertEqual(client.post("/api/decision",
                                     json={"action": "rollback", "stage": "verify"}).status_code, 400)
        self.assertGreater(len(calls), 0)

    def test_all_workflow_skills_reference_discipline(self):
        """每个阶段 SKILL 必须对通用纪律「明确表态」（引用或写豁免理由）。

        与 lib/web/healthcheck.py 的同名检查是同一事实的两道锁：单测防改坏、体检防漏加。
        """
        sk = PROJECT / "skills"
        # 必须从 STAGES 派生，不能写死一份清单：写死的话**新加的阶段永远不会被检查**
        #   （往 STAGES 加一个 skill 存在但不引用纪律的阶段，本用例照样绿）。
        #   `0Start-mathmodel` 不在 STAGES 里（它是入口），单独补上。
        for d in sorted({s["skill"] for s in self.s.STAGES} | {"0Start-mathmodel"}):
            p = sk / d / "SKILL.md"
            self.assertTrue(p.exists(), f"缺 {d}")
            self.assertIn("_references/stage_discipline.md", p.read_text(encoding="utf-8"),
                          f"{d} 未引用通用纪律")
        self.assertTrue((sk / "_references" / "stage_discipline.md").exists())


    def test_a_clean_rubric_makes_fix_green_without_running_it(self):
        """⑫ 通过 ⇒ ⑬ 自动为绿（跳过，不调 agent）。

        ⑬ 只是执行 ⑫ 判词的工具步骤：⑫ 变绿则 ⑬ 自动也为绿。
        """
        calls = self.install_successful_runner()
        asyncio.run(self.s.run_all())
        self.assertNotIn("fix", calls, "⑫ 干净时不该调 ⑬")
        self.assertEqual(self.s.state["stages"]["fix"], "done(skip)")

    def test_the_repair_goes_back_to_rubric_instead_of_straight_forward(self):
        """⑫ 没过 ⇒ 交 ⑬ 就地改 ⇒ **改完回 ⑫ 复评**（不是"修完直接往下走、只在收尾复评"）。

        ⑫ 没过时它亮黄灯，等 ⑬ 处理完再回到 ⑫。
        夹具用 `_resume_with_rubric_verdict`：它造的判词是**合规的**（claim + tier=must），
        这样才走得通"正向交给 ⑬"那条路 —— 只写 status=FAIL、没有判词的桩会被门禁判
        malformed 直接停机（那种桩会让 calls 停在 rubric，走不到 ⑬）。
        轮数上限见 `lib/web/server.py::RUBRIC_FIX_MAX_ROUNDS`（=3，到顶转黄灯）。
        """
        calls = self._resume_with_rubric_verdict({
            "before": {"status": "NEEDS_FIX", "reason": "paper_repair_required", "target": "fix",
                       "issues": [{"id": "r1", "category": "claim", "tier": "must"}],
                       "advisories": []},
            "after": {"status": "PASS", "reason": "", "issues": [], "advisories": []}})
        self.assertEqual(calls[:3], ["rubric", "fix", "rubric"],
                         f"顺序应是 ⑫ 判不过 → ⑬ 修 → 回 ⑫ 复评，实际 {calls}")
        self.assertEqual(self.s.state["fix_rounds"]["rubric"], 1,
                         "来回一轮就该记一轮（上限 RUBRIC_FIX_MAX_ROUNDS=3）")

    def test_every_skill_name_resolves_to_its_stage(self):
        """阶段别名解析必须**大小写不敏感**，且 16 个 skill 目录名一定解析得中。

        要防的坏法：查表用 `.lower()` 而键是**原样大小写**的 skill 目录名 ⇒
        目录按「序号+英文」命名时 16 个名字**一个都查不中**：
          · `HANDBACK_REQUEST.md` 写 `target: 9Paper-writing` → `check_handback` 抛
            「target 不是已知阶段」→ 整链按"驱动异常"停机；
          · 裁决里的 target 写 skill 名 → `_target_index` **静默**退回默认映射 ⇒
            黄灯推荐的回退阶段是错的（不报错，最坏的一种）。
        """
        for st in self.s.STAGES:
            self.assertEqual(self.s._resolve_stage_id(st["skill"]), st["id"],
                             f"skill 目录名解析不出来：{st['skill']}")
            self.assertEqual(self.s._resolve_stage_id(st["skill"].lower()), st["id"],
                             f"小写写法解析不出来：{st['skill'].lower()}")
            self.assertEqual(self.s._resolve_stage_id(f"  {st['id']}  "), st["id"],
                             "阶段 id 本身（含空白）必须照旧可用")
        # 改名前的旧目录名照旧认：老工作区里遗留的交回单不该把链顶死
        for old, sid in (("9writing", "write"), ("9format", "format"), ("13fix", "fix"),
                         ("11verity", "verify"), ("5coding", "code"), ("web-demo", "demo")):
            self.assertEqual(self.s._resolve_stage_id(old), sid, old)
        self.assertIsNone(self.s._resolve_stage_id("nonsense"), "不认识的写法不许猜出东西来")

    def test_handback_target_written_as_a_skill_dir_name_is_accepted(self):
        """交回单里把 target 写成 skill 目录名（文档/面板都这么显示）必须被认，而不是把链顶死。

        否则 `target: 9Paper-writing` → ValueError → run_all 兜成"驱动异常"停机。
        """
        (self.s.REPORTS / "HANDBACK_REQUEST.md").write_text(
            "target: 9Paper-writing\n理由：附录还没做完\n", encoding="utf-8")
        # 用 `STAGE_IDX[...]` 而不是裸下标：插入 ⓪ 读题之后，裸下标 `12` 已经从
        #   "⑬ 按评分判词返修"漂成"⑫ 评分标终审" —— 断言侥幸仍绿，但语义已经不是它在测的那件事）。
        self.assertEqual(self.s.check_handback(self.s.STAGE_IDX["fix"]),
                         self.s.STAGE_IDX["write"])

    def test_a_layout_pass_does_not_drag_the_repair_stage_back(self):
        """⑭ 只做版式手术（改 `paper/_base/` + 重编 PDF）⇒ 下一轮 ⑬ **不该**被拉回来重跑。

        ⑫ 判过之后 ⑬ 就该解耦：⑭/⑮ 跟 ⑫、⑬ 无关，不该把 ⑬ 带回来。
        否则（只改 `paper/_base/preamble.tex` 并重写 `main.pdf` 时）下一轮 `calls == ['fix']`
        —— ⑬ 的产物含**整份 `paper/`**，⑭ 一动手就作废它的回执
        （`_LAYOUT_OWNED_PATHS` 那条解耦只覆盖输入侧、且够不着 `paper/sections/`）。
        判定：把 ⑨ 的「被下游接管」判据（`_taken_over_by`）同样用到 ⑬ 上。
        """
        def layout_pass(sid):
            if sid != "format":
                return
            p = self.root / "paper/_base/preamble.tex"
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("\\documentclass{article}\n" * 20, encoding="utf-8")
            (self.root / "paper/main.pdf").write_bytes(b"%PDF-1.4\n" + b"z" * 140)

        calls = self.install_successful_runner(after=layout_pass)
        # ⑫ 判「PASS 但带 issue」——`_rubric_hands_off()` 只看 issues，这类必须真跑一次 ⑬
        self.s._gate_decision = lambda st: (
            {"status": "PASS", "reason": "", "advisories": [],
             "issues": [{"id": "r1", "category": "claim", "tier": "optional"}]}
            if st["id"] == "rubric"
            else {"status": "PASS", "reason": "", "issues": [], "advisories": []})
        asyncio.run(self.s.run_all())
        self.assertIn("fix", calls, f"⑫ 带 issue 时 ⑬ 必须真跑，实际 {calls}")
        calls.clear()
        asyncio.run(self.s.run_all())
        self.assertNotIn("fix", calls,
                         f"只改版式不该把 ⑬ 拉回来（⑭ 已接管 paper/），实际 {calls}")
        self.assertEqual(calls, [], f"整链应全部复用、零 agent 调用，实际 {calls}")

    def test_a_fresh_verdict_still_runs_the_repair_even_after_a_layout_pass(self):
        """闸门：⑫ **刚判出**判词把活交下来时，⑬ 必须真跑 —— 接管判定不许吞掉它。

        没有这道闸，「12 没过 → 等 13 处理 → 回 12」会被静默跳过（接管判据只看回执）。
        判据是 `state["fix_loop_return"]`（⑫ 交接时置成本关 id）。
        """
        calls = self._resume_with_rubric_verdict({
            "before": {"status": "NEEDS_FIX", "reason": "paper_repair_required", "target": "fix",
                       "issues": [{"id": "r1", "category": "claim", "tier": "must"}],
                       "advisories": []},
            "after": {"status": "PASS", "reason": "", "issues": [], "advisories": []}})
        self.assertEqual(calls[:3], ["rubric", "fix", "rubric"],
                         f"⑫→⑬→⑫ 这条设计路径必须走得通，实际 {calls}")

    def test_a_forward_handoff_does_not_skip_a_gate_that_never_ran(self):
        """`forward`（⑬ 没动稿 ⇒ 不回评）不许把**还没跑过**的判官跳过去。

        写法若为 `index = max(index + 1, STAGE_IDX[交接方] + 1)`：交接方是 ⑪（`cross`，
        index 11）时 `max(13 + 1, 11 + 1) = 14` ⇒ **直接落到 ⑭，
        ⑫ 评分标终审一次都不评**；而尾段写着「收尾不再重判任何判官」⇒ 此后永远不会跑。

        `forward` 的理由是"那一关的审查对象一个字没动 ⇒ **已经跑过**的阶段没有需要重跑的新输入"
        —— 那句对"**没跑过**"的阶段不成立：它不是"不需要重跑"，是"还没轮到"。
        判据：走完 forward 之后 ⑫ 必须被跑到。
        """
        calls = []
        self.install_successful_runner(after=lambda sid: calls.append(sid))
        # ⑪ 判 REVISE_CLAIM（纯论文侧）⇒ 交接 ⑬；⑬ 只写报告、不动 paper/ ⇒ 触发 forward。
        # 桩必须幂等：同一阶段一次执行会被问两遍（见 `_resume_with_rubric_verdict` 的坑③）。
        self.s._gate_decision = lambda st: (
            {"status": "REVISE_CLAIM", "reason": "paper_repair_required", "target": "fix",
             "issues": [{"id": "c1", "category": "claim", "tier": "must"}], "advisories": []}
            if st["id"] == "cross"
            else {"status": "PASS", "reason": "", "issues": [], "advisories": []})
        asyncio.run(self.s.run_all())
        self.assertIn("fix", calls, f"⑪ 交接后 ⑬ 必须真跑，实际 {calls}")
        self.assertIn("rubric", calls,
                      f"forward 把没跑过的 ⑫ 跨过去了（落到 ⑭ 去了）：{calls}")

    def test_the_handoff_marker_is_consumed_even_when_the_repair_fails(self):
        """⑫→⑬ 的「回来复评」标志必须在 ⑬ 的**每一种出路**上被消费掉。

        若 ⑬ 执行失败（rc≠0）→ 黄灯 → 标志还挂着 True，而唯一的消费点
        （⑬ 跑完那段跳回 ⑫）永远走不到 ⇒ 人工修好、认证续跑时 ⑫ 一次都不复评，
        链却照常跑完 ⑭⑮⑯ 并报成功，而 ⑫ 的 NEEDS_FIX 裁决从未被重新看过。
        判定：标志在**进入 ⑬ 那一轮的开头**就取走（`run_all` 的 `_rubric_handoff`），
        无论 ⑬ 走真跑 / 被接管 / 豁免 / stale / manual / 失败哪条路。
        """
        self.install_successful_runner()
        asyncio.run(self.s.run_all())
        self.assertTrue(self.s.state["run_completed"], self.s.state["halt_reason"])
        # 第二轮：⑫ 判 NEEDS_FIX 交回 ⑬，而 ⑬ 执行失败
        self.s._gate_decision = lambda st: (
            {"status": "NEEDS_FIX", "reason": "paper_repair_required", "target": "fix",
             "issues": [{"id": "r1", "category": "claim", "tier": "must"}], "advisories": []}
            if st["id"] == "rubric"
            else {"status": "PASS", "reason": "", "issues": [], "advisories": []})
        real = self.s._call

        async def failing_fix(prompt, sid, cap=None):
            if sid == "fix":
                return 1, "boom", False
            return await real(prompt, sid, cap)

        self.s._call = failing_fix
        asyncio.run(self.s.run_all())
        p = self.s.state.get("pending") or {}
        self.assertEqual(p.get("stage"), "fix", f"应停在 ⑬ 的黄灯上：{p.get('stage')}")
        self.assertFalse(self.s.state["fix_loop_return"],
                         "⑫ 的交接标志不许悬空 —— 它就是「还要回 ⑫ 复评一次」这个承诺")

    def test_an_overtime_light_always_offers_extend(self):
        """超时黄灯**必须**带「延长」—— 哪怕那份裁决同时是"过期"的。

        根因：`_action_set` 里 `kind == "overtime"` 那条若排在两条 `stale` 分支**之后**，
        复活旧黄灯时按当前盘面重算（`_load_pending` → `_build_pending(kind="overtime",
        status="stale")`）就会撞上 stale 分支，actions 被压成 `['retry']` ⇒
        面板上「再延长 N 分钟 + 延长」整组控件不显示。
        延长的语义是"别杀它、再给点时间"，跟裁决新鲜度毫不相干 ⇒ 这条必须排最前。
        """
        acts = self.s._action_set("cross", "overtime", "stale", True, None,
                                  stale=True, stale_findings_ok=False)
        self.assertIn("extend", acts,
                      f"超时灯必须给「延长」（哪怕裁决过期），实际 {acts}")
        # 反向对照：普通失败灯在同样"裁决过期"下仍**不该**给延长（那是超时专有的出路）。
        acts2 = self.s._action_set("cross", "failure", "blocked", True, None,
                                   stale=True, stale_findings_ok=False)
        self.assertNotIn("extend", acts2, f"失败灯不该给「延长」，实际 {acts2}")

    def test_a_human_waiver_outranks_a_matching_receipt(self):
        """人工「接受并披露」**优先于**回执复用。

        要防的坏法：`12Rubric-final → 13Repair` 交接时会重存一份"与当前输入
        相符"的回执（`_save_receipt`），而豁免检查若排在三条复用近路**之后** ⇒ 对着 ⑫
        点「接受并披露」后，下一次跑 ⑫ 命中复用直接返回 `ok`、裁决里那条 FAIL 被重新读出来
        ⇒ **黄灯原地再现、出不去**。豁免是人的显式决定，优先级必须高于"回执说没人动过"。
        （输入一变豁免自动失效 —— `_waived` 比的是输入 digest。）
        """
        st = self.stage("rubric")
        self.report(st, "评分标终审报告：FAIL")
        self.s._save_receipt(st)
        self.assertEqual(asyncio.run(self.s.run_stage(st)), "ok", "没有豁免时应照旧复用")
        self.s._save_waivers({"rubric": {"digest": self.s._input_digest(st),
                                         "at": "2026-09-27T05:00:00", "note": "人工接受"}})
        self.assertEqual(asyncio.run(self.s.run_stage(st)), "waived",
                         "披露必须优先于回执复用，否则黄灯出不去")

    def test_each_stage_is_mirrored_exactly_once_per_run(self):
        """每个阶段每轮**只镜像一次**产物。

        否则非门禁阶段会被镜像两遍（`if not stage.get("gate")` 那里一次、门禁那条
        通用调用又一次）⇒ 白走一遍整棵产物树（`code/` 上百 MB）、`.snapshot.json` 重写两次、
        日志里「阶段快照不完整」成对出现。
        """
        counted = {}
        real = self.s._snapshot_stage

        def spy(stage, fig_before=None):
            counted[stage["id"]] = counted.get(stage["id"], 0) + 1
            return real(stage, fig_before)

        self.s._snapshot_stage = spy
        self.install_successful_runner()
        asyncio.run(self.s.run_all())
        dup = sorted(k for k, v in counted.items() if v > 1)
        self.assertEqual(dup, [], f"这些阶段被镜像了多遍：{dup}")
        self.assertEqual(set(counted), {s["id"] for s in self.s.STAGES},
                         "每个阶段都该镜像一次")


class OvertimeLampTests(unittest.TestCase):
    """超时黄灯的去重键必须是「**在哪个限值下**报过」，不是「报过没有」。

    否则：`code` 亮了一次超时黄灯，点「延长本次限时至 10 分钟」之后，
    它**再也不会亮** —— 面板一直显示耗时 57m14s，实际已跑 58 分钟没人管。
    根因：`/api/decision(action=extend)` 自己就 `_set_pending(None)` 了，而复位
    `overtime_notified` 那段挂在 `if pending 是 overtime` 判断**里面**，于是永不执行。
    """

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.s = load_server(self.root)

    def _patched(self, cap_seconds):
        """把 `_call` 外部依赖全换成可控的：假 worker 不产出、不退，靠事件放行。"""
        import threading
        s = self.s
        s.STALL_SAMPLE = 0.05         # 看门狗 5 秒一轮 → 压到 50ms
        s.WAIT_AFTER_KILL = 0.2
        s.STALL_SILENT = 1e9          # 只测**墙钟上限**那条路，别让假死抢戏
        s.STALL_CONN = 1e9
        s.state["retry_cap"]["code"] = cap_seconds
        s._find_claude = lambda: Path("fake-runner")
        s._tree_cpu_seconds = lambda pid: None
        s._refresh_tcp = lambda: set()
        s._kill_tree = lambda pid: None
        stop = threading.Event()

        def fake_worker(cmd, sh):
            sh["pid"] = 424242
            stop.wait(30)
            sh["rc"] = 0
            sh["done"] = True

        s._claude_worker = fake_worker
        return stop

    def _await_overtime(self, limit, timeout=8.0):
        async def wait():
            t0 = time.time()
            while time.time() - t0 < timeout:
                await asyncio.sleep(0.05)
                p = self.s.state.get("pending")
                if p and p.get("kind") == "overtime":
                    return p
            return None
        return asyncio.run(wait())

    def test_overtime_lamp_relights_after_the_limit_is_extended(self):
        """病灶本体：延长之后再超限，必须**再亮一次**。"""
        stop = self._patched(cap_seconds=1)
        s = self.s

        async def scenario():
            task = asyncio.create_task(s._call("prompt", "code"))
            t0 = time.time()
            first = None
            while time.time() - t0 < 6:
                await asyncio.sleep(0.05)
                p = s.state.get("pending")
                if p and p.get("kind") == "overtime":
                    first = p
                    break
            self.assertIsNotNone(first, "首次超限就该亮黄灯")
            # 用户点「延长」：`/api/decision(action=extend)` 做的正是这两件事 ——
            # 清黄灯 + 改限值。复位逻辑若挂在 pending 判断里就再也醒不过来。
            s._set_pending(None)
            s.state["stages"]["code"] = "running"
            s.state["retry_cap"]["code"] = 2
            second = None
            t1 = time.time()
            while time.time() - t1 < 6:
                await asyncio.sleep(0.05)
                p = s.state.get("pending")
                if p and p.get("kind") == "overtime":
                    second = p
                    break
            self.assertIsNotNone(second, "延长后的新限值到点必须**再亮一次**，不能从此哑掉")
            s.state["stopping"] = True
            await asyncio.wait_for(task, timeout=5)
            # 放行必须在 `asyncio.run` **里面**：`asyncio.run` 收尾会
            #   `shutdown_default_executor()` 等那个 worker 线程，留在外面等 = 白等 30 秒。
            stop.set()

        asyncio.run(scenario())

    def test_the_same_limit_does_not_relight_every_tick(self):
        """反向对照：同一个限值下不能每 50ms 刷一次面板（去重还得管用）。"""
        stop = self._patched(cap_seconds=1)
        s = self.s
        seen = []

        async def scenario():
            task = asyncio.create_task(s._call("prompt", "code"))
            t0 = time.time()
            while time.time() - t0 < 3:
                await asyncio.sleep(0.05)
                p = s.state.get("pending")
                if p and p.get("kind") == "overtime":
                    seen.append(p.get("created_at"))
                    # 不模拟延长：就把黄灯**原样留着**，看它会不会被反复重建
                    s._set_pending(p)
            s.state["stopping"] = True
            await asyncio.wait_for(task, timeout=5)
            stop.set()

        asyncio.run(scenario())
        self.assertTrue(seen, "至少该亮一次")
        self.assertEqual(len(set(seen)), 1, "同一限值下只该构造一次黄灯，不许每轮重建")

    def test_a_flipping_connection_state_does_not_relight_the_lamp(self):
        """去重键里**不能带 `limit`**。

        `limit`（假死容忍）由"这一刻有没有 ESTABLISHED 连接"决定（闲着 300 秒、握着连接 1200 秒），
        而那是每 STALL_SAMPLE=5 秒**现查一次**的 ⇒ 同一盏灯在两次采样之间键就变、**反复重发**。
        症状是同一阶段、同一上限在相隔十秒内各重亮一次，且时间越往后这一串越密。
        上面那条用例把 `_refresh_tcp` 固定成常数 ⇒ **结构上看不见这个翻转**，所以单开这条。
        """
        stop = self._patched(cap_seconds=1)
        s = self.s
        s.STALL_SILENT, s.STALL_CONN = 1e6, 2e6       # 都远大于墙钟上限：只测超限那条路
        tick = [0]

        def flipping_tcp():
            tick[0] += 1
            return {424242} if tick[0] % 2 else set()  # 每次采样都翻转连接状态

        s._refresh_tcp = flipping_tcp
        seen = []

        async def scenario():
            task = asyncio.create_task(s._call("prompt", "code"))
            t0 = time.time()
            while time.time() - t0 < 3:
                await asyncio.sleep(0.05)
                p = s.state.get("pending")
                if p and p.get("kind") == "overtime":
                    seen.append(p.get("created_at"))
                    s._set_pending(p)              # 不模拟延长：让黄灯原样留着
            s.state["stopping"] = True
            await asyncio.wait_for(task, timeout=5)
            stop.set()

        asyncio.run(scenario())
        self.assertTrue(seen, "至少该亮一次")
        self.assertEqual(len(set(seen)), 1,
                         "连接状态一翻转就重亮 —— 去重键里还带着 limit（应该只留 cap_s 与 kind）")

    def test_a_stall_or_protocol_capped_light_does_not_offer_extend(self):
        """「延长」对这两类灯没用 ⇒ 不给按钮。

        · 假死/静默灯：延长的是**墙钟上限**，而它管的是"没输出" ⇒ 点了没用，还会因为 cap_s
          变了让去重键变化 ⇒ **下一轮 5 秒后又原样亮一遍**；
        · 协议级修复的短上限（`CALL_PROTOCOL_CAP=900`）：`_effective_limits` 里 `cap` 永远压过
          用户覆盖 ⇒ 点了只写进 state、对它毫无作用，日志却写「追加 10 分钟」骗人。
        """
        s = self.s
        self.assertNotIn("extend", s._action_set("code", "overtime", "overtime", True, None,
                                                 limit_kind="stall"),
                         "假死灯不该给「延长」")
        self.assertNotIn("extend", s._action_set("code", "overtime", "overtime", True, None,
                                                 capped=True),
                         "协议级短上限下的灯不该给「延长」（它压不过 cap）")
        self.assertIn("extend", s._action_set("code", "overtime", "overtime", True, None),
                      "墙钟上限那类灯必须照旧给「延长」—— 那是它的唯一出路")


class ExtendIsAdditiveTests(unittest.TestCase):
    """「延长本次限时」是**追加**，不是替换：

        默认 30 分钟 → 到点亮黄灯问 → 你加 10 ⇒ 本次临时上限 40
        → 40 到点**再问一次** → 再加 ⟶ …（总天花板 = RETRY_CAP_MAX）
        而这一轮的临时上限**只属于这一次执行**，下次重跑退回 30。

    两条容易写反的地方：`RETRY_CAP_MAX` 既是默认值又是天花板（就延不动了）；extend 若写成替换，
    填 10 会把 30 缩短成 10（而阶段可能已跑 30 分钟 ⇒ 超限恒成立）。
    """

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.s = load_server(self.root)

    def _overtime_pending(self):
        return {"stage": "code", "kind": "overtime", "status": "overtime", "reason": "x",
                "actions": ["retry", "extend"], "recommended": None, "candidates": [],
                "issues": [], "retry_cap_default": self.s.RETRY_CAP_DEFAULT,
                "attest_default": None}

    def _extend(self, seconds=600):
        s = self.s
        s.state["stages"]["code"] = "awaiting_user"
        s.state["pending"] = self._overtime_pending()
        return asyncio.run(s._apply_decision(
            s.DecisionReq(action="extend", stage="code", extra_seconds=seconds)))

    def test_extend_adds_to_the_current_limit(self):
        s = self.s
        s.state["retry_cap"] = {}
        r = self._extend(600)
        self.assertEqual(r["effective_seconds"], s._default_cap("code") + 600,
                         "30 分钟 + 追加 10 = 40 分钟（不是把它替换成 10）")

    def test_extending_twice_keeps_accumulating(self):
        """40 到点再问 → 再加 10 ⇒ 50。第二次延长若把上限**压回**你填的那个数就错了。"""
        s = self.s
        s.state["retry_cap"] = {}
        self._extend(600)
        r2 = self._extend(600)
        self.assertEqual(r2["effective_seconds"], s._default_cap("code") + 1200)

    def test_extension_stops_at_the_ceiling(self):
        """到顶就**明确拒绝**：若它照样清黄灯、置 running，并声称
        「下一次超限会立刻再问你」—— 而去重键 `(cap_s, kind)` 一个分量都没变 ⇒ 那盏灯
        再也不会亮（那次调用从此没有墙钟兜底，只剩静默检测）。
        判据：到顶直接 400，**不动任何状态、也不清黄灯**，文案说清还能怎么办。"""
        s = self.s
        s.state["retry_cap"] = {}
        r = None
        while s._effective_limits("code")[0] < s.RETRY_CAP_MAX:   # 追加到顶就停（到顶后再加会被拒）
            r = self._extend(s.RETRY_CAP_EXTRA_MAX)
        self.assertEqual(r["effective_seconds"], s.RETRY_CAP_MAX)
        self.assertEqual(s._effective_limits("code")[0], s.RETRY_CAP_MAX)
        with self.assertRaises(s.HTTPException) as cm:
            self._extend(s.RETRY_CAP_EXTRA_MAX)
        self.assertIn("不能再延长", str(cm.exception.detail))

    def test_a_tiny_extension_is_raised_to_the_floor(self):
        """填 1 分钟不该把上限压到 1 分钟 —— 至少追加 RETRY_CAP_EXTRA_MIN。"""
        s = self.s
        s.state["retry_cap"] = {}
        r = self._extend(60)
        self.assertEqual(r["effective_seconds"], s._default_cap("code") + s.RETRY_CAP_EXTRA_MIN)

    def test_the_stall_tolerance_does_not_grow_with_the_cap(self):
        """解耦：墙钟上限能追加到 3 小时，但「多久没动静才怀疑它死了」**封住不动**。

        绑在一起时，一个真·死进程（无输出 + 无 CPU + 无连接）要等满上限才被发现 ——
        上限追加到 3 小时就是瞎等 3 小时。解耦的代价如实认：慢但在等 API 的阶段
        会每 STALL_CONN 亮一次黄灯问一次，答一句「再延长」继续。
        """
        s = self.s
        s.state["retry_cap"] = {}
        self.assertEqual(s._effective_limits("code")[1], s.STALL_SILENT)
        self.assertEqual(s._effective_limits("code", has_conn=True)[1], s.STALL_CONN)
        while s._effective_limits("code")[0] < s.RETRY_CAP_MAX:   # 追加到顶就停（到顶后再加会被拒）
            self._extend(s.RETRY_CAP_EXTRA_MAX)
        cap_s, limit = s._effective_limits("code")
        self.assertEqual(cap_s, s.RETRY_CAP_MAX, "上限该一路追加到天花板")
        self.assertEqual(limit, s.STALL_SILENT, "假死容忍不该跟着上限涨")
        self.assertLess(limit, cap_s, "两者已解耦：容忍应当显著小于上限")

    def test_the_temp_limit_dies_with_the_execution(self):
        """用户第 5 点：这一轮的临时上限只属于这一次执行，下次重跑退回 30。"""
        s = self.s
        s.state["retry_cap"] = {}
        self._extend(600)
        self.assertIn("code", s.state["retry_cap"])
        st = next(x for x in s.STAGES if x["id"] == "code")
        (s.REPORTS / st["report"]).write_text("最终结论：PASS\n" + "evidence " * 30,
                                              encoding="utf-8")
        (self.root / "code").mkdir(exist_ok=True)
        (self.root / "code/example.txt").write_text("fixture", encoding="utf-8")

        async def ok(prompt, sid, cap=None):
            return 0, "", False
        s._call = ok
        asyncio.run(s.run_stage(st))
        self.assertNotIn("code", s.state["retry_cap"], "执行结束后临时上限必须被清掉")
        # 「退回默认」= 退回**该阶段自己的**默认（④ 有自己单独标定的值，见 STAGE_CAP_DEFAULT）
        self.assertEqual(s._effective_limits("code")[0], s._default_cap("code"))


class LogFileShadowTests(unittest.TestCase):
    """`runtime/web_run.log` 上**只能有一个写者**（就是 `log()`）。

    若 `nohup … >> runtime/web_run.log 2>&1` 起服务，进程 stdout 也在写
    同一个文件。stdout 是块缓冲的，冲下来时按它自己的 fd 位置落盘 → **把 `log()` 刚追加的行
    整段覆盖掉**。文件结构正好是证据：前一段全是 `log()` 的行，之后全是 `INFO:` 行
    —— 分界点就是第一次重定向启动服务的时刻。
    后果：`web 就绪`、超时黄灯那整晚的行全没了，而那是排查 bug 的唯一依据。
    """

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.s = load_server(self.root)

    def test_detects_stdout_pointing_at_the_log_file(self):
        s = self.s
        s.LOG_DIR.mkdir(parents=True, exist_ok=True)
        logf = s.LOG_DIR / "web_run.log"
        logf.write_text("x\n", encoding="utf-8")
        self.assertFalse(s._stdout_shadows_the_log(), "stdout 不是那个文件时不该误报")

        saved = os.dup(1)
        fh = os.open(str(logf), os.O_WRONLY | os.O_APPEND)
        try:
            os.dup2(fh, 1)
            os.close(fh)
            self.assertTrue(s._stdout_shadows_the_log(),
                            "stdout 指向日志文件时必须报出来 —— 否则 log() 会静默丢行")
        finally:
            os.dup2(saved, 1)          # 立刻恢复，别让断言输出跑进日志文件
            os.close(saved)

    def test_missing_log_file_is_not_a_collision(self):
        s = self.s
        s.LOG_DIR.mkdir(parents=True, exist_ok=True)
        (s.LOG_DIR / "web_run.log").unlink(missing_ok=True)
        self.assertFalse(s._stdout_shadows_the_log())

    def test_log_write_failure_is_recorded_not_swallowed(self):
        """日志写不进去必须留痕 —— 静默丢证据正是这个 bug 的教训。"""
        s = self.s
        s.LOG_DIR.mkdir(parents=True, exist_ok=True)
        s.LOG_DIR.joinpath("web_run.log").mkdir(exist_ok=True)   # 同名目录 → open 必失败
        s._real_log("探针：这条写不进去")
        errs = s.state.get("log_write_errors") or []
        self.assertTrue(errs, "写文件失败必须记进 state，不能吞掉")
        self.assertIn("log_write_errors", s.state2dict())


class AdvisoryPanelTests(unittest.TestCase):
    """轻微建议在面板上**默认折叠**，但必须如实报总数与类别分布。

    一轮定点返修可能留下**二十几条**轻微项（`why_not_blocking` 逐条看全是
    「只改一句 / 不改任何数值 / 订正引用」级），面板铺开后"看着问题很多" —— 而拦链的只有个位数。
    折叠行只报「共 N 条 + 按类别分布」，点开才看明细；**总数必须如实**，不能只报"显示几条"。
    """

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.s = load_server(self.root)

    def stage(self, sid):
        return next(x for x in self.s.STAGES if x["id"] == sid)

    def test_pending_reports_the_true_advisory_total_and_caps_the_payload(self):
        st = self.stage("review")
        advs = [{"id": f"a{i}", "category": "claim", "evidence": "e", "fix": "f",
                 "why_not_blocking": "w"} for i in range(23)]
        p = self.s._build_pending(st, "failure", "blocked", "x",
                                  decision={"status": "NEEDS_FIX", "reason": "content_repair_required",
                                            "issues": [], "advisories": advs})
        self.assertEqual(p["advisories_total"], 23, "总数必须如实报 —— 不能让人以为只显示的就是全部")
        self.assertEqual(len(p["advisories"]), 23, "23 条在 40 的上限内，应当全带")
        self.assertNotIn("仅 12 条", str(p))   # 旧实现截到 12，面板会少报

    def test_an_oversized_advisory_list_is_capped_but_still_counted(self):
        st = self.stage("review")
        advs = [{"id": f"a{i}", "category": "claim", "evidence": "e", "fix": "f",
                 "why_not_blocking": "w"} for i in range(60)]
        p = self.s._build_pending(st, "failure", "blocked", "x",
                                  decision={"status": "NEEDS_FIX", "reason": "content_repair_required",
                                            "issues": [], "advisories": advs})
        self.assertEqual(len(p["advisories"]), 40, "载荷上限 40")
        self.assertEqual(p["advisories_total"], 60, "超上限时总数更要如实")
        self.assertGreater(p["advisories_total"], len(p["advisories"]),
                           "前端靠这个差值说出「面板只带前 40 条」")


class StalePendingSchemaTests(unittest.TestCase):
    """重启时复活的 pending 若来自**更早的驱动**，必须按当前盘面重算。

    否则都是同一个毛病：旧序列化的字段被当现状显示：
      · `retry_cap_max=1800`，而实际已是 10800；
      · 缺 `retry_extra_default` → 面板算不出「追加 N 分钟后上限 = …」；
      · 缺 `advisories_total` → 面板把"带下来的 12 条"说成全部（侧车里其实 23 条）。
    """

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.s = load_server(self.root)

    def _revive(self, pending):
        self.s.PENDING_FILE.parent.mkdir(parents=True, exist_ok=True)
        self.s.PENDING_FILE.write_text(json.dumps(pending, ensure_ascii=False), encoding="utf-8")
        self.s._load_pending()
        return self.s.state.get("pending")

    _OLD = {"stage": "review", "kind": "failure", "status": "blocked", "reason": "旧结论",
            "actions": ["retry", "rollback", "disclose"], "recommended": "analysis",
            "issues": [{"id": "R-1"}], "advisories": [{"id": "a1"}] * 12,
            "retry_cap_max": 1800}

    def test_a_pending_from_an_older_driver_is_rebuilt(self):
        got = self._revive(dict(self._OLD))
        self.assertIn("advisories_total", got, "旧版写的不该原样复活")
        self.assertIn("retry_extra_default", got)
        self.assertNotEqual(got.get("retry_cap_max"), 1800, "该用当前的上限口径重算")

    def test_a_current_pending_survives_untouched(self):
        """反向护栏：本版写的 pending 必须**原样复活** —— 别把好黄灯也重算了。"""
        fresh = dict(self._OLD)
        fresh.update({"advisories_total": 12, "retry_extra_default": 600,
                      "retry_extra_max": 1800})
        self.s._build_pending = lambda *a, **k: (_ for _ in ()).throw(
            AssertionError("本版写的 pending 不该触发重算"))
        got = self._revive(fresh)
        self.assertEqual(got["reason"], "旧结论")
        self.assertEqual(got["advisories_total"], 12)


class FailureTailTests(unittest.TestCase):
    """进程非零退出时，`pending.tail` 是**唯一**的线索 —— 面板必须拿得到它。

    例：review 因 `API Error: 402 Insufficient Balance` 退出，`rc=1`。
    没有裁决 → `issues` 只剩一条派生的 `verdict_schema`（"缺少必查项…"），
    真正死因只在 tail 里。而**前端若不渲染 tail**，答案就一直在那个字段里、
    只是没人显示它 —— 于是只剩"为什么又不行"这类只能靠猜的问题。
    """

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.s = load_server(self.root)

    def stage(self, sid):
        return next(x for x in self.s.STAGES if x["id"] == sid)

    def test_execution_failure_carries_the_tail(self):
        st = self.stage("review")
        p = self.s._build_pending(st, "failure", "failed", "阶段未成功完成：failed",
                                  decision={"status": "UNVERIFIED", "reason": "verdict_malformed",
                                            "issues": [{"id": "verdict_schema"}],
                                            "advisories": []},
                                  tail="…前面一堆输出…\nAPI Error: 402 Insufficient Balance")
        self.assertIn("402 Insufficient Balance", p["tail"],
                      "面板靠这个字段显示死因，不能丢")
        self.assertFalse(p["issues"] and len(p["issues"]) > 1,
                         "这种失败本来就只有一条派生 issue —— 所以 tail 必须顶上")

    def test_tail_is_capped_so_the_payload_stays_bounded(self):
        st = self.stage("review")
        p = self.s._build_pending(st, "failure", "failed", "x",
                                  decision={"status": "UNVERIFIED", "reason": "verdict_malformed",
                                            "issues": [], "advisories": []},
                                  tail="X" * 5000)
        self.assertEqual(len(p["tail"]), 1500, "末 1500 字 —— 与 _retry_hint 的口径一致")


class RollbackNoteTests(unittest.TestCase):
    """回退时人工补的要求必须跟着回执一起交给目标阶段。

    否则（例如口径改成「摘要计入正文额度」后想让 ⑨ 顺手压掉超出的那一页）：
    `req.note` 只有 `retry` 那条路用（`_retry_hint`），**回退会把它丢掉** ——
    人写了要求、回退过去的生产阶段却看不到。
    """

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.s = load_server(self.root)

    def _stage(self, sid):
        return next(x for x in self.s.STAGES if x["id"] == sid)

    def test_rollback_carries_the_user_note(self):
        s = self.s
        st = self._stage("mathproof")
        (s.REPORTS / st["report"]).write_text("整题门禁裁决：REVISE_HARD\n" + "e " * 60,
                                              encoding="utf-8")
        s.state["stages"]["mathproof"] = "awaiting_user"
        s.state["pending"] = {"stage": "mathproof", "kind": "failure", "status": "blocked",
                              "reason": "x", "actions": ["retry", "rollback"],
                              "candidates": [{"id": "write"}], "issues": []}
        real_redo = s._redo_from
        s._redo_from = lambda *a, **k: []          # 别真去搬产物

        asyncio.run(s._apply_decision(s.DecisionReq(
            action="rollback", stage="write", note="摘要现在计入正文额度，PDF 超 1 页，压掉一页")))
        s._redo_from = real_redo

        hints = s.state.get("seed_hints") or {}
        self.assertTrue(hints, "回退该设 seed_hints")
        self.assertIn("摘要现在计入正文额度", hints.get("write", ""),
                      "人工补的要求必须到目标阶段手里")
        self.assertIn("摘要现在计入正文额度", hints.get("format", ""),
                      "回退路径上每个要重跑的阶段都该看到它")


class ReceiptStoreConcurrencyTests(unittest.TestCase):
    """回执文件是**整份读—改—写**的，写者不止一个（run_all 线程 / uvicorn 事件循环 /
    看门狗）。`save`/`invalidate` 若写成「构造时读一份快照、保存时整份写回」，那么
    **把旧快照写回去的那个，会连中间新增的回执一起盖掉** —— 丢得没有任何日志。

    典型时序：旧链跑到 ④ 编码计算并超限转黄灯但**任务继续运行**；随后在面板上回退到
    ② 建模设计 → `_start_chain()` 又起了一条链（它不看有没有链在跑），两条链同时写；
    旧链的 ④ 成功写下回执后，新链的写者拿着更早的快照一 flush ⇒ `code` 的回执消失、
    **且无任何日志**；重启时 `code` 被判「没跑过」⇒ 整链从 ④ 重来约 35 分钟，
    而它明明已经成功过。

    判定：`_mutate` 在**同一把锁里重新读盘**再改再写（见 workflow_quality.StageReceipts）。
    这几个用例都是**确定性**的 —— 不需要线程，只要两个持有不同快照的对象交叠操作。
    """

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "stages.json"

    def _save(self, store, stage, run="r1"):
        store.save(stage, f"in-{stage}", f"out-{stage}", run)

    def test_a_stale_snapshot_cannot_drop_a_receipt_written_in_between(self):
        """A 先读 → B 写 code → A 再写 audit：code 不许丢。"""
        a = StageReceipts(self.path)          # A 读（此时盘上还没有 code）
        b = StageReceipts(self.path)
        self._save(b, "code", "run-old")      # 旧链的 ④ 成功写回执
        self._save(a, "audit", "run-new")     # 新链的写者把旧快照写回去
        rec = StageReceipts(self.path).records
        self.assertIn("code", rec, "旧链的成功回执被新链的旧快照盖掉了 —— 就是那个 bug")
        self.assertIn("audit", rec)

    def test_a_stale_invalidate_cannot_drop_a_receipt_written_in_between(self):
        """作废是**点名**的：A 作废 analysis 时不该顺手把 code 也抹掉。"""
        a = StageReceipts(self.path)
        b = StageReceipts(self.path)
        self._save(b, "code", "run-old")
        a.invalidate(["analysis"])
        rec = StageReceipts(self.path).records
        self.assertIn("code", rec)
        self.assertNotIn("analysis", rec, "点名的那个还是要作废")

    def test_invalidate_still_accepts_a_generator(self):
        """调用方传的是生成器（`(s["id"] for s in STAGES[index:])`）—— 只能迭代一次。"""
        store = StageReceipts(self.path)
        for sid in ("analysis", "review", "code"):
            self._save(store, sid)
        store.invalidate(sid for sid in ("analysis", "review"))
        rec = StageReceipts(self.path).records
        self.assertEqual(sorted(rec), ["code"])

    def test_matches_reads_what_this_object_loaded(self):
        """`matches` 的读语义没变 —— 它比的是本对象载入的那份（调用方本就各自新建）。"""
        store = StageReceipts(self.path)
        self._save(store, "code")
        self.assertTrue(store.matches("code", "in-code", "out-code"))
        self.assertFalse(store.matches("code", "in-code", "别的"))
        self.assertFalse(store.matches("audit", "in-code", "out-code"))

    def test_many_threads_writing_at_once_lose_nothing(self):
        """真并发下也不许丢。20 个线程各自持**不同快照**同时写 —— 旧实现基本全丢。

        这条测的是锁本身：前两条是确定性的「快照交叠」，这条是「同时刻并发」。
        用 Barrier 把 20 个线程卡在同一瞬间，再一起写。
        """
        import threading
        n = 20
        stores = [StageReceipts(self.path) for _ in range(n)]   # 20 份快照，全是空的
        barrier = threading.Barrier(n)
        errors = []

        def worker(i):
            try:
                barrier.wait(timeout=10)
                self._save(stores[i], f"stage{i:02d}")
            except Exception as exc:                            # noqa: BLE001
                errors.append(exc)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(n)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=15)

        self.assertEqual(errors, [])
        rec = StageReceipts(self.path).records
        missing = [f"stage{i:02d}" for i in range(n) if f"stage{i:02d}" not in rec]
        self.assertEqual(missing, [], f"并发写丢了 {len(missing)} 条：{missing}")

    def test_a_save_racing_an_invalidate_keeps_what_it_should(self):
        """作废与保存并发：点名的作废掉，没点名的保住。"""
        import threading
        keeper, victim = StageReceipts(self.path), StageReceipts(self.path)
        self._save(StageReceipts(self.path), "analysis")
        barrier = threading.Barrier(2)

        def do_save():
            barrier.wait(timeout=10)
            self._save(keeper, "code")

        def do_invalidate():
            barrier.wait(timeout=10)
            victim.invalidate(["analysis"])

        ts = [threading.Thread(target=do_save), threading.Thread(target=do_invalidate)]
        for t in ts:
            t.start()
        for t in ts:
            t.join(timeout=15)

        rec = StageReceipts(self.path).records
        self.assertIn("code", rec)
        self.assertNotIn("analysis", rec)


class RevivedPendingActionsTests(unittest.TestCase):
    """复活的黄灯里 `actions` 必须按**当前驱动**现算。

    面板上的按钮**只由盘上那份 `pending_decision.json` 决定**。驱动新增一个动作之后
    旧快照的 actions 里没有它 —— 重启后那个新按钮
    **根本不会出现**，看到的是"功能没生效"。收窄时更糟：旧快照给出后端已不认的动作。

    `_load_pending` 原有三条分支各管一种"旧"：超时语义已失效 / 裁决过期 / 缺新字段 ——
    这一条是第四种：**字段齐全、语义没过期，但动作集变了**，前三条都放它过。
    """

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.s = load_server(self.root)

    def _write_pending(self, actions, **extra):
        self.s.PENDING_FILE.parent.mkdir(parents=True, exist_ok=True)
        p = {"stage": "drawio", "kind": "failure", "status": "blocked",
             "reason": "drawio 按 SKILL 交回上游：建议退到 code", "actions": actions,
             "recommended": "code", "recommended_source": "handback",
             "attest_default": None, "candidates": [], "issues": [],
             "advisories": [], "advisories_total": 0,
             "retry_extra_default": 600, "retry_extra_max": 1800}
        p.update(extra)
        self.s.PENDING_FILE.write_text(json.dumps(p, ensure_ascii=False), encoding="utf-8")
        return p

    def test_a_new_action_in_the_driver_appears_after_restart(self):
        """旧快照缺 attest；复活后必须补上 —— 否则那个按钮永远不出现。"""
        self._write_pending(["retry", "rollback", "disclose"],
                            attest_default="analysis")   # 有可认证目标 → 该给 attest
        self.s._load_pending()
        acts = (self.s.state.get("pending") or {}).get("actions") or []
        self.assertIn("attest", acts, f"新动作没补上：{acts}")

    def test_an_action_the_driver_no_longer_offers_is_dropped(self):
        """反向也要管：旧快照给了后端已不认的动作 → 点下去只会 400。"""
        self._write_pending(["retry", "rollback", "disclose", "extend"])
        self.s._load_pending()
        acts = (self.s.state.get("pending") or {}).get("actions") or []
        self.assertNotIn("extend", acts, f"失败黄灯不该有 extend：{acts}")

    def test_the_recommendation_is_not_clobbered(self):
        """只换 actions，不许动 recommended —— 整体重建会丢掉 agent 主动交回给的建议。"""
        self._write_pending(["retry", "rollback"])
        self.s._load_pending()
        p = self.s.state.get("pending") or {}
        self.assertEqual(p.get("recommended"), "code")
        self.assertEqual(p.get("recommended_source"), "handback")


class FigureOnlyRollbackTests(unittest.TestCase):
    """回退到 ④ 时，**纯图缺陷不搬数值产物** —— 自动判，不给人多一个按钮。

    背景：⑦ 的图问题按 `category=diagram` 路由回 ④（它是唯一拥有 `figures/make_figures.py` 的
    **前序**阶段；⑨ 排版与版式虽然才是"重画图"的官方接手人，却在 ⑦ 的**下游**，指不到）。
    而 `ARTIFACTS["code"] = ["reports/RESULTS_REPORT.md","code","results"]` —— 照搬的话，
    为了修一个色标与两处图例位置，`code/outputs/*.npz` 与 `results/*.xlsx` 被整包搬进 cache，
    ④ 只能**从零重算**。而交回单 §4 自己写着「这一单**一条都不许触发重算**」。

    判据收紧到"**每一条**未解决项都是 diagram"：混进任何别的类别（implementation /
    data_integrity / validation…）就说明数值本身也可能有问题 → 照旧整包搬走、让它重算。
    宁可多算一次，不可拿旧数当新数。
    """

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.s = load_server(self.root)
        (self.root / "code/outputs").mkdir(parents=True)
        (self.root / "code/outputs/solution.npz").write_bytes(b"NPZ" * 40)
        (self.root / "results").mkdir()
        (self.root / "results/result1.xlsx").write_bytes(b"xlsx" * 40)
        (self.root / "reports").mkdir(exist_ok=True)
        (self.root / "reports/RESULTS_REPORT.md").write_text("结果" * 80, encoding="utf-8")
        self.s.state["run_id"] = "r1"

    def _rollback(self, issues):
        self.s.state["stages"]["drawio"] = "awaiting_user"
        self.s.state["pending"] = {
            "stage": "drawio", "kind": "failure", "status": "blocked", "reason": "x",
            "actions": ["retry", "rollback", "disclose"], "recommended": "code",
            "recommended_source": "handback", "attest_default": None,
            "candidates": [], "issues": issues}
        return asyncio.run(self.s._apply_decision(
            self.s.DecisionReq(action="rollback", stage="code")))

    def _present(self):
        return ((self.root / "code/outputs/solution.npz").is_file(),
                (self.root / "results/result1.xlsx").is_file(),
                (self.root / "reports/RESULTS_REPORT.md").is_file())

    def test_all_diagram_issues_leave_the_numeric_artifacts_alone(self):
        """正题：缺陷全是"图本身的产出" → 数值产物一件不搬。"""
        self._rollback([{"id": "FIG-1", "severity": "hard", "category": "diagram"},
                        {"id": "FIG-2", "severity": "soft", "category": "diagram"}])
        self.assertEqual(self._present(), (True, True, True),
                         "纯图缺陷却把数值产物搬走了 —— 那就是逼 ④ 从零重算")

    def test_a_mixed_issue_set_still_stashes_everything(self):
        """对照组：混进一条非 diagram → 数值可能有问题 → 照旧整包搬走。"""
        self._rollback([{"id": "FIG-1", "severity": "hard", "category": "diagram"},
                        {"id": "X-1", "severity": "hard",
                         "category": "implementation"}])
        self.assertEqual(self._present(), (False, False, False),
                         "非纯图缺陷却没搬数值产物 —— 拿旧数当新数，比多算一次危险得多")

    def test_an_empty_issue_set_is_not_treated_as_figure_only(self):
        """没有未解决项 ≠ 纯图缺陷 —— 判据要求"至少有一条且全是 diagram"。"""
        self.assertFalse(self.s._figure_only_defects([]))
        self.assertFalse(self.s._figure_only_defects(None))

    def test_other_stages_are_unaffected(self):
        """只在 ④ 上生效：回退到别的阶段时该搬的照搬（这条防着 `_rels` 被改宽）。"""
        (self.root / "reports/ANALYSIS_MODELING_REPORT.md").write_text("x" * 200, encoding="utf-8")
        self.s.state["stages"]["drawio"] = "awaiting_user"
        self.s.state["pending"] = {
            "stage": "drawio", "kind": "failure", "status": "blocked", "reason": "x",
            "actions": ["retry", "rollback", "disclose"], "recommended": "analysis",
            "recommended_source": "verdict", "attest_default": None, "candidates": [],
            "issues": [{"id": "FIG-1", "severity": "hard", "category": "diagram"}]}
        asyncio.run(self.s._apply_decision(
            self.s.DecisionReq(action="rollback", stage="analysis")))
        self.assertFalse((self.root / "reports/ANALYSIS_MODELING_REPORT.md").is_file(),
                         "回退到 ② 却没搬它的产物 —— `_rels` 被改宽了")

    # ---- 交回那一盏灯：pending 是空壳 ⇒ 回查它上一轮拿到的上游门禁回执 ----
    #  ⑦技术路线图 交回 ④ 时它**不是门禁** ⇒ pending 的 issues 天然为空
    #  ⇒ ① `_figure_only_defects([])` = False ⇒ 明明全是 diagram，也把整包
    #     数值产物搬走（④ 回来得自己 robocopy 搬回；想不起来就是从零重算）；
    #     ② `_has_actionable_feedback({})` = False ⇒ 给 ④ 的提示词写成"没有跑完…仅供排查…
    #     与本阶段无关"，而那张交回单**正是**它的返修单（反的）。

    def _receipt(self, stage_id, issues, sub="r0/aaaa1111", **extra):
        folder = self.root / "runtime/quality/feedback" / sub
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "gate_decision.json").write_text(json.dumps(
            dict({"schema_version": 2, "stage": stage_id, "issues": issues}, **extra),
            ensure_ascii=False), encoding="utf-8")
        return "runtime/quality/feedback/" + sub

    def _handback_pending(self):
        """⑦ 交回 ④ 的真实形状：pending 走 `_build_pending`（借回执那一步在它里面）。"""
        st = next(x for x in self.s.STAGES if x["id"] == "drawio")
        return self.s._build_pending(st, "failure", "blocked", "drawio 按 SKILL 交回上游",
                                     handback=self.s.STAGE_IDX["code"])

    def _two_diagrams(self):
        return [{"id": "F-2", "severity": "hard", "category": "diagram"},
                {"id": "F-5", "severity": "soft", "category": "diagram"}]

    def test_a_handback_lamp_borrows_the_upstream_gate_issues(self):
        """正题：交回那条路上，把上游门禁那批未解决项借过来 —— 面板显示它、判据也依据它。"""
        self.s.state["hint_src"]["drawio"] = self._receipt("figreview", self._two_diagrams())
        p = self._handback_pending()
        self.assertEqual([i["id"] for i in p["issues"]], ["F-2", "F-5"],
                         "交回那盏灯没借到上游门禁的缺陷清单 —— 面板空着，判据也瞎了")
        self.assertEqual(p.get("recommended_source"), "handback", "交回的落点不能被我改掉")

    def test_the_borrowed_issues_make_the_rollback_figure_only(self):
        """端到端：借到"全是 diagram"⇒ 回退到 ④ 一件数值产物都不搬。"""
        self.s.state["hint_src"]["drawio"] = self._receipt("figreview", self._two_diagrams())
        self.s._set_pending(self._handback_pending())
        self.s.state["stages"]["drawio"] = "awaiting_user"
        asyncio.run(self.s._apply_decision(
            self.s.DecisionReq(action="rollback", stage="code")))
        self.assertEqual(self._present(), (True, True, True),
                         "交回那盏灯借到了纯图缺陷，却还是把数值产物搬走了")
        _got = self.s.state["hint_src"].get("code")
        self.assertIsNotNone(_got, "回退区间内每个阶段都要记下『这一轮拿到哪份回执』（交回时要回查）")
        self.assertTrue((self.root / _got / "gate_decision.json").is_file(),
                        "记下的那份回执必须真的在盘上 —— 交回时要按它回查缺陷清单")

    def test_a_mixed_upstream_receipt_still_stashes(self):
        """对照组：借来的那批混了非 diagram ⇒ 照旧整包搬（数值可能真有问题）。"""
        self.s.state["hint_src"]["drawio"] = self._receipt("figreview", [
            {"id": "F-2", "severity": "hard", "category": "diagram"},
            {"id": "AU-1", "severity": "hard", "category": "validation"}])
        self.s._set_pending(self._handback_pending())
        self.s.state["stages"]["drawio"] = "awaiting_user"
        asyncio.run(self.s._apply_decision(
            self.s.DecisionReq(action="rollback", stage="code")))
        self.assertEqual(self._present(), (False, False, False))

    def test_the_borrow_refuses_a_non_gate_source(self):
        """硬边界：非门禁的"裁决"是空壳，没有判据可言 ⇒ 不借（保守照搬）。"""
        self.s.state["hint_src"]["drawio"] = self._receipt("drawio", self._two_diagrams(),
                                                          sub="r0/bbbb2222")
        self.assertIsNone(self.s._borrowed_upstream_issues(
            next(x for x in self.s.STAGES if x["id"] == "drawio")))

    def test_the_borrow_refuses_a_downstream_source(self):
        """硬边界：下游阶段的回执与本次返修无关 ⇒ 不借。"""
        self.s.state["hint_src"]["drawio"] = self._receipt("write", self._two_diagrams(),
                                                          sub="r0/cccc3333")
        self.assertIsNone(self.s._borrowed_upstream_issues(
            next(x for x in self.s.STAGES if x["id"] == "drawio")))

    def test_no_recorded_receipt_means_conservative(self):
        """没记录到回执（旧 pending / 重启后复活）⇒ 不借 ⇒ 与今天一样保守。"""
        self.assertIsNone(self.s._borrowed_upstream_issues(
            next(x for x in self.s.STAGES if x["id"] == "drawio")))
        self.s._set_pending(self._handback_pending())
        self.assertEqual(self.s.state["pending"]["issues"], [])

    def test_the_handback_hint_is_not_worded_as_did_not_finish(self):
        """提示词不许再是反的：交回单**就是**本轮要执行的返修单，不是"仅供排查"的原始输出。"""
        (self.root / "reports/HANDBACK_REQUEST.md").write_text(
            "target: code\n\nreason: 数据图的画法问题交回上游\n", encoding="utf-8")
        hint = self.s._save_feedback(next(x for x in self.s.STAGES if x["id"] == "drawio"))
        self.assertIn("HANDBACK_REQUEST.md", hint, "没把交回单指给下游/上游看")
        self.assertNotIn("仅供排查", hint,
                         "交回那条路又把交回单说成『仅供参考的原始输出』—— 提示词是反的")
        self.assertFalse((self.root / "reports/HANDBACK_REQUEST.md").is_file(),
                         "投递即出队：交回单拷进 feedback 后就该从 reports/ 移走")


class HandbackIsOneShotTests(unittest.TestCase):
    """交回单是**一次性消息**：投递（拷进 feedback 目录）之后就从 `reports/` 移除。

    坏法：⑦ 写完交回单就停下等决策；回退后链条**从 ① 重走**，走到 ③ 时
    `check_handback` 看到这份交回单 —— 它的 `target: code`（下标 3）在 ③（下标 2）看来是
    **下游**，不构成「前序返修」→ 判无效 → **搬进 cache**。于是 ④ 真正开跑时
    清单已经不在 `reports/` 了，而提示还让它去那儿读 —— **清单投递失败**。

    为什么不能改成「`check_handback` 别搬走它」：留着它会造**死循环** —— 走到 ⑤ 那一轮时
    `target: code`（3）< 4 反而构成合法前序 → ⑤ 又停下要求回退到 ④ → ④ 跑完 → ⑤ 再看到
    它 → 无限循环。`check_handback` 搬走它正是在**防这个环**。

    **这条用例是"性质测试"，不是"负对照"**：清理由**两处**共同保证 ——
    `_redo_from`（它的理由是"黄灯要跟着灭"）与 `_save_feedback`（投递即出队）。
    负对照：把 `_save_feedback` 里那句 unlink 拿掉，本条**照样绿** ——
    因为走标准回退路径时 `_redo_from` 已经清过。真正会泄漏的是**有一条回退路径
    绕过 `_redo_from`** 的情形 —— 所以这里钉的是**性质**：
    无论走哪条路，"投递之后 `reports/` 里不该再有它"必须成立。
    """

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.s = load_server(self.root)
        (self.root / "reports").mkdir(exist_ok=True)
        (self.root / "reports/ANALYSIS_MODELING_REPORT.md").write_text("x" * 200, encoding="utf-8")
        self.s.state["run_id"] = "r1"

    def _write_handback(self):
        self.s.HANDBACK.write_text("target: code\n\nreason: 数据图的根子在 ④\n",
                                   encoding="utf-8")

    def test_the_handback_moves_into_the_feedback_folder_and_leaves_reports(self):
        self._write_handback()
        self.s.state["stages"]["drawio"] = "awaiting_user"
        self.s.state["pending"] = {
            "stage": "drawio", "kind": "failure", "status": "blocked", "reason": "交回",
            "actions": ["retry", "rollback", "disclose"], "recommended": "analysis",
            "recommended_source": "handback", "attest_default": None, "candidates": [],
            "issues": [{"id": "FIG-1", "severity": "hard", "category": "diagram"}]}
        self.s.state["seed_hints"] = {}
        import asyncio as _a
        _a.run(self.s._apply_decision(
            self.s.DecisionReq(action="rollback", stage="analysis")))

        self.assertFalse(self.s.HANDBACK.is_file(),
                         "交回单还留在 reports/ —— 从 ① 重走时会被 ③ 当成下游交回单搬走")
        fb = self.s.LOG_DIR / "quality" / "feedback"
        copies = list(fb.rglob("HANDBACK_REQUEST.md"))
        self.assertTrue(copies, "交回单没投递进 feedback 目录 —— 那就是真丢了")
        self.assertIn("数据图的根子在", copies[0].read_text(encoding="utf-8"))

    def test_a_run_without_a_handback_is_unaffected(self):
        self.s.state["stages"]["drawio"] = "awaiting_user"
        self.s.state["pending"] = {
            "stage": "drawio", "kind": "failure", "status": "blocked", "reason": "x",
            "actions": ["retry", "rollback", "disclose"], "recommended": "analysis",
            "recommended_source": "verdict", "attest_default": None, "candidates": [],
            "issues": []}
        import asyncio as _a
        _a.run(self.s._apply_decision(
            self.s.DecisionReq(action="rollback", stage="analysis")))
        self.assertFalse(self.s.HANDBACK.exists())      # 本来就没有，不该报错


class RevisionDiffTests(unittest.TestCase):
    """返修跑要留一页「改前/改后」对照（`lib/web/server.py:_write_revision_diff`）。

    要防的坏法**不是**"没改对"，而是**修 A 时顺手弄坏了本来正确的 B**：
    已被独立验证正确的一个数值可能在返修里被改错。评审回执虽然写了
    「可放行部分／保留，勿重写」，但那是散文；下一轮评审得重读整份报告才可能发现越界改动。
    落成一页 diff 之后，**清单外的改动**一眼可见。

    （这个函数一度写好了却没有调用者 —— 属于"存了工具、没接线"那一类。）
    """

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.s = load_server(self.root)
        (self.root / "reports").mkdir(exist_ok=True)

    def _stage_report(self, text):
        p = self.root / "reports/ANALYSIS_MODELING_REPORT.md"
        p.write_text(text, encoding="utf-8")
        return p

    def test_an_in_scope_edit_and_an_out_of_scope_edit_are_both_shown(self):
        """改对了清单内一条、又顺手改坏了清单外一条 —— 两处都必须出现在对照里。"""
        before = self.root / "reports/_before.md"
        before.write_text("第 1 行：**目标值 = 4.14e-3**（已独立验证，勿重写）\n"
                          "第 2 行：口径 = 体积平均\n", encoding="utf-8")
        self._stage_report("第 1 行：**目标值 = 4.14e-3**（已独立验证，勿重写）\n"
                           "第 2 行：口径 = 全域最大 ← 清单内要求改的\n"
                           "第 3 行：新增一句 ← 清单外的越界改动\n")
        self.s._write_revision_diff("analysis", before)
        out = (self.root / "reports/_REVISION_DIFF.md").read_text(encoding="utf-8")
        self.assertIn("返修改动对照", out)
        self.assertIn("清单内要求改的", out)          # 清单内的改动在
        self.assertIn("清单外的越界改动", out)        # 越界的那处也在 —— 这是这个功能的意义
        self.assertIn("+", out) and self.assertIn("-", out)

    def test_it_reports_the_change_size(self):
        before = self.root / "reports/_before.md"
        before.write_text("a\nb\nc\n", encoding="utf-8")
        self._stage_report("a\nB\nc\nd\n")
        self.s._write_revision_diff("analysis", before)
        out = (self.root / "reports/_REVISION_DIFF.md").read_text(encoding="utf-8")
        self.assertIn("改动：**+2 / -1 行**", out)

    def test_a_missing_snapshot_is_a_no_op(self):
        """没有"改前"快照时不许报错、也不许编出一份空的对照。"""
        self._stage_report("x\n")
        self.s._write_revision_diff("analysis", self.root / "reports/_nope.md")
        self.assertFalse((self.root / "reports/_REVISION_DIFF.md").exists())

    def test_paper_stages_are_skipped(self):
        """论文侧（report 以 paper 开头）不做这种报告级对照 —— 那是 format 的活。"""
        st = next(x for x in self.s.STAGES if x["id"] == "format")
        self.assertTrue(str(st["report"]).startswith("paper")
                        or str(st["report"]).endswith(".md"))

    def test_the_hooks_are_wired_into_run_stage(self):
        """源码级钉子：跑前留快照（判据 `round_hint`）、成功分支调 diff。"""
        src = (PROJECT / "lib/web/server.py").read_text(encoding="utf-8")
        i = src.index("async def run_stage")
        j = src.index("def _write_revision_diff")
        seg = src[i:j]
        self.assertIn("_rev_before", seg, "run_stage 里没有留快照")
        self.assertIn("if round_hint:", seg, "快照该只在返修跑时留（判据 round_hint）")
        self.assertIn("_write_revision_diff(sid, _rev_before)", seg, "成功分支没调 diff")
        self.assertIn("try:", seg.split("_write_revision_diff(sid, _rev_before)")[0][-200:],
                      "调用没做异常保护 —— 辅助留证不该能把阶段带崩")


class LocateTargetsTests(unittest.TestCase):
    """「手工修复」面板的定位核心：从判词里算出**改哪儿**（`lib/web/server.py:_locate_targets`）。

    黄灯上的判词说的是「§8 第 5 条」「§5.6 的 (v) 行」这类**章节坐标**，
    而报告 1700+ 行 —— 只给一个「已手工修好」按钮，等于让人拿判词去整篇里翻。

    判词通常**同时含**文件路径（`reports/RESULTS_REPORT.md`）与被改文字的**引用**
    （「Δr 口径（网格，V10）」）。拿后者在前者里搜即得行号 —— 纯文本检索，不猜语义。
    """

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "reports").mkdir()
        self.s = load_server(self.root)

    def _report(self, body):
        (self.root / "reports/RESULTS_REPORT.md").write_text(body, encoding="utf-8")

    def test_it_picks_the_specific_quote_not_the_generic_one(self):
        """判词里既有长引文（真正要改的）也有短通用短语，
        取第一个会把位置指到文件前部的通用短语上。判据是**引文更长者胜**。"""
        self._report("第一行：这里写着**不动任何数值**，是句通用话\n" * 3 +
                     "\n" * 40 +
                     "第 44 行：**Δr 口径**（网格，V10）单侧 ≤0.04 h\n")
        got = self.s._locate_targets(
            "判词：「**Δr 口径**（网格，V10）单侧 ≤0.04 h」写错了；注意**不动任何数值**。"
            "改法：在 reports/RESULTS_REPORT.md 里定点改。")
        self.assertTrue(got, "没定位到")
        self.assertEqual(got[0]["file"], "reports/RESULTS_REPORT.md")
        self.assertIn("Δr 口径", got[0]["matched"], f"指到了通用短语：{got[0]}")
        self.assertGreater(got[0]["line"], 3, "指到了文件前部的通用短语")

    def test_it_returns_the_context_around_the_line(self):
        # 引文要 ≥12 字才进候选（短的通用短语会命中文件随便一处）—— 夹具也得守这条，
        # 不然测的是"夹具太短"，不是定位器。
        target = "这一行是判词点名要改的那句话"
        self._report("\n".join(f"第 {i} 行" + (target if i == 10 else " 其他内容")
                              for i in range(1, 21)))
        got = self.s._locate_targets(f"改 reports/RESULTS_REPORT.md 里「{target}」那处")
        self.assertTrue(got, "没定位到")
        self.assertEqual(got[0]["line"], 10)
        ctx = got[0]["context"]
        self.assertEqual([c["n"] for c in ctx], list(range(7, 14)), "上下文应是目标行 ±3 行")
        self.assertEqual(sum(1 for c in ctx if c["hit"]), 1, "只该有一行被标为目标")

    def test_no_file_path_means_no_guess(self):
        """判词里没有文件路径时**老实返回空** —— 前端会显示"未定位到，请手工检索"。"""
        self._report("随便什么内容\n")
        self.assertEqual(self.s._locate_targets("§8 第 5 条的那个分句写错了"), [])

    def test_it_does_not_point_at_a_file_that_does_not_exist(self):
        self._report("内容\n")
        self.assertEqual(self.s._locate_targets("改 reports/NO_SUCH.md 里的「某个句子」"), [])



if __name__ == "__main__":
    unittest.main()
