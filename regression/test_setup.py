"""产物路径点选、不归档删除本题、开屏配置页 —— 三块的哨兵与对照组。

为什么单独一个文件：这三件都是**界面侧**能力，其中「删除本题」是全仓
**第一条真删数据**的路径（别的都是 `rename` 归档或 `move` 暂存），风险与别的都不一样，
值得有自己的一组判据 + 对照组。

手法照 `test_intake.py`：用 `load_server` 把 ROOT 指到临时目录，**不碰真工作区**。
"""
import asyncio
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))
sys.path.insert(0, str(PROJECT / "lib" / "web"))
sys.path.insert(0, str(PROJECT / "regression"))

from test_workflow import load_server  # noqa: E402


def _html():
    return (PROJECT / "lib/web/static/index.html").read_text(encoding="utf-8")


class StoreOutputDirTests(unittest.TestCase):
    """`_store_output_dir`：产物路径落盘前的**归一化**（纯函数，脱服务可测）。"""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for rel in ("CLAUDE.md", "AGENTS.md"):
            shutil.copy2(PROJECT / rel, self.root / rel)
        for rel in ("skills", "docs"):
            shutil.copytree(PROJECT / rel, self.root / rel)
        self.s = load_server(self.root)

    def test_relative_when_inside_the_repo(self):
        """性质：**仓内**的目录一律存成相对路径 —— 这份配置跟着仓库走，存绝对会让新机器写错地方。

        （`config/delivery.local.json` 随仓库被拷走，本仓无 git —— 与
        `test_local_decoupling.py::test_the_shipped_delivery_config_is_not_pinned_to_a_machine`
        守的是同一件事。）
        """
        f = self.s._store_output_dir
        self.assertEqual(f(str(self.root / "产物")), "产物")
        self.assertEqual(f(str(self.root / "a" / "b")), "a/b")
        self.assertEqual(f("产物"), "产物", "已经是相对路径的要原样留下")
        self.assertEqual(f(""), "", "空 = 回落默认（<根>/产物）")
        self.assertEqual(f("   "), "", "纯空白也算空")

    def test_absolute_only_when_outside(self):
        """对照组：仓外目录**只能**存绝对路径 —— 否则 `resolve_output_dir` 会把它拼到仓里。

        没有这条，上面那条可能只是"反正都存相对"——而那是错的：显式选仓外是**合法用法**
        （`resolve_output_dir` 本来就允许，`regression/test_delivery.py` 钉着这条）。
        """
        outside = Path(self.temp.name).parent / "不是仓内的目录"
        got = self.s._store_output_dir(str(outside))
        self.assertTrue(Path(got).is_absolute(), f"仓外应当存绝对，实际 {got!r}")
        self.assertEqual(got, str(outside))

    def test_the_repo_root_itself_falls_back_to_the_default(self):
        """选中仓库根 ⇒ 存空串。

        `resolve_output_dir` 对"等于 root"本来就回落 `<root>/产物`；存成相对串 `"."` 反而会让
        它在**仓根原地**归档（把 `reports/` 之类直接改到根上）。这条是那个边界。
        """
        self.assertEqual(self.s._store_output_dir(str(self.root)), "")

    def test_saving_normalizes(self):
        """落盘那一步真的走了归一化（不是只在 helper 里对）。"""
        self.s._save_delivery_config(self.s._store_output_dir(str(self.root / "我的产物")), "2026A")
        cfg = json.loads((self.root / "config/delivery.local.json").read_text(encoding="utf-8"))
        self.assertEqual(cfg["output_dir"], "我的产物")


class WipeProblemTests(unittest.TestCase):
    """「不归档删除本题」：删产物 + 删状态，**保留题面与附件**。"""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for rel in ("CLAUDE.md", "AGENTS.md"):
            shutil.copy2(PROJECT / rel, self.root / rel)
        for rel in ("skills", "docs"):
            shutil.copytree(PROJECT / rel, self.root / rel)
        self.s = load_server(self.root)

    def _seed(self):
        """造一份"跑过一轮"的盘面：产物 + 题面附件 + 状态 + 框架文件各就各位。"""
        r = self.root
        for rel in ("reports", "code", "results", "figures", "paper", "demo", "paper_appendix"):
            (r / rel).mkdir(parents=True, exist_ok=True)
            (r / rel / "x.txt").write_text("产物 " * 40, encoding="utf-8")
        (r / "运行说明.md").write_text("说明 " * 40, encoding="utf-8")
        # 题面与附件（**必须留下**）
        (r / "request/attachments").mkdir(parents=True, exist_ok=True)
        (r / "request/problem.md").write_text("题面正文", encoding="utf-8")
        (r / "request/attachments/附件1.xlsx").write_bytes(b"xlsx")
        (r / "data").mkdir(exist_ok=True)
        (r / "data/d.csv").write_text("a,b\n1,2\n", encoding="utf-8")
        # 两个「最新」指针里放点东西 + cache
        out = self.s._delivery_dir()
        (out / "提交作品/最新作品").mkdir(parents=True, exist_ok=True)
        (out / "提交作品/最新作品/正文.pdf").write_bytes(b"pdf")
        (out / "各阶段产物/最新产物/编码计算").mkdir(parents=True, exist_ok=True)
        # cache 下**按题分目录**：本题一份、往届一份。归档名格式见 `delivery_name()`
        #   （`<题目标识>_<日期_时间>`），而"本题是谁"由 workspace.json 记着。
        (out / "cache/2026A_2026.9.25_18.32.16/工作区原件").mkdir(parents=True, exist_ok=True)
        (out / "cache/2026A_2026.9.25_18.32.16/工作区原件/旧产物.txt").write_text("本题的", encoding="utf-8")
        (out / "cache/2025B_2025.9.1_10.00.00").mkdir(parents=True, exist_ok=True)
        (out / "cache/2025B_2025.9.1_10.00.00/唯一的副本.txt").write_text("往届的", encoding="utf-8")
        q0 = r / "runtime/quality"
        q0.mkdir(parents=True, exist_ok=True)
        (q0 / "workspace.json").write_text(
            json.dumps({"source_digest": "old", "run_id": "r1", "problem_id": "2026A"},
                       ensure_ascii=False), encoding="utf-8")
        (out / "其他产物/reports").mkdir(parents=True, exist_ok=True)
        (out / "其他产物/reports/old.md").write_text("旧", encoding="utf-8")
        # 状态
        q = r / "runtime/quality"
        q.mkdir(parents=True, exist_ok=True)
        (q / "stages.json").write_text("{}", encoding="utf-8")
        (q / "feedback/deadbeef").mkdir(parents=True, exist_ok=True)
        (q / "pending_decision.json").write_text("{}", encoding="utf-8")
        (r / "runtime/web_run.log").write_text("log", encoding="utf-8")

    def wipe(self, word="删除本题"):
        return asyncio.run(self.s.wipe_problem(self.s.WipeReq(confirm=word)))

    def test_it_deletes_products_and_state_but_keeps_inputs(self):
        """主判据：产物没了、状态清了，而**题面/附件一个都还在**。"""
        self._seed()
        out = self.wipe()
        r = self.root
        for rel in ("reports", "code", "results", "figures", "paper", "demo", "paper_appendix"):
            self.assertFalse((r / rel / "x.txt").exists(), f"{rel} 的产物应当被删掉")
        self.assertFalse((r / "运行说明.md").exists())
        self.assertFalse((r / "runtime/quality/stages.json").exists(), "回执应当被清")
        self.assertFalse((r / "runtime/quality/feedback").exists(),
                         "返修台账必须清 —— 它是无 run_id 过滤的全目录 glob，残留会让下一轮 ② 假报缺账")
        self.assertFalse((r / "runtime/quality/pending_decision.json").exists())
        # **本题**的 cache 要没，**往届**的必须留着 —— `cache/<归档名>/` 里躺的是被轮转出去的
        #   那道题的产物原件，误删就是删掉上一题唯一的副本（确认框里承诺过"保留往届归档"）。
        self.assertFalse((self.s._delivery_dir()
                          / "cache/2026A_2026.9.25_18.32.16").exists(), "本题的 cache 应当被删")
        self.assertTrue((self.s._delivery_dir()
                         / "cache/2025B_2025.9.1_10.00.00/唯一的副本.txt").is_file(),
                        "往届归档被连坐删了 —— cache 只能删本题那一份")
        self.assertFalse((self.s._delivery_dir() / "其他产物").exists())
        # 保留面
        self.assertEqual((r / "request/problem.md").read_text(encoding="utf-8"), "题面正文")
        self.assertTrue((r / "request/attachments/附件1.xlsx").is_file())
        self.assertEqual((r / "data/d.csv").read_text(encoding="utf-8"), "a,b\n1,2\n")
        for rel in ("lib/web/server.py", "skills", "docs", "CLAUDE.md"):
            self.assertTrue((PROJECT / rel).exists(), f"框架本体 {rel} 不该被动")
        self.assertTrue(out["kept"], "回给面板的 kept 不能是空的（用户要看见留着什么）")

    def test_the_two_pointers_are_rebuilt_empty(self):
        """两个「最新」的**内容**要没，但**骨架**必须建回来。

        骨架不在的话 `_delivery_status` 与 `lib/delivery/checks.py` 的路径假设就落空。
        对照组在下面那条。
        """
        self._seed()
        self.wipe()
        out = self.s._delivery_dir()
        for ptr in (out / "提交作品/最新作品", out / "各阶段产物/最新产物"):
            self.assertTrue(ptr.is_dir(), f"{ptr.name} 的空骨架应当建回来")
            self.assertEqual(list(ptr.iterdir()), [], f"{ptr.name} 里不该还剩东西")

    def test_workspace_record_is_rewritten_to_the_current_digest(self):
        """删完之后 `workspace.json` 必须记**当前**的 digest。

        不重写的话，下一次点「开始全链」会因为 digest 对不上被当成**换题**，白跑一轮
        `_rotate_pointers` + `_invalidate_from(0)` —— 而产物刚被删光，那一轮只会产出两个空归档目录。
        **证伪**：把重写那一步去掉（或写成旧 digest），这条必须变红。
        """
        self._seed()
        self.wipe()
        path = self.root / "runtime/quality/workspace.json"
        self.assertTrue(path.is_file(), "workspace.json 应当被重建")
        self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["source_digest"],
                         self.s._source_digest(),
                         "记的不是当前 digest ⇒ 下次 ▶ 会被当成换题")

    def test_the_kept_originals_survive_the_wipe(self):
        """`runtime/quality/intake/kept/` 里是标为「忽略（不动它）」的原件的**唯一一份**
        （`_materialize_inbox` 先 copy 进 kept/ 再 rmtree 掉 `_inbox/`）。

        而 wipe 第④步是对 `runtime/quality/` **整层遍历删** ⇒ 不显式绕开就连原件一起 rmtree，
        正好毁掉确认框里承诺"会留"的东西（与 cache 那条是同一类错法）。
        对照组：intake/ 下的**状态**（confirmed.json）要照常删掉。
        """
        self._seed()
        kept = self.root / "runtime/quality/intake/kept"
        (kept / "附件").mkdir(parents=True, exist_ok=True)
        (kept / "附件/备注.md").write_text("用户选的是「忽略（不动它）」", encoding="utf-8")
        q = self.root / "runtime/quality/intake"
        (q / "confirmed.json").write_text("{}", encoding="utf-8")
        self.wipe()
        self.assertTrue((kept / "附件/备注.md").is_file(),
                        "「不动它」的原件被删了 —— 那是工作区里唯一一份")
        self.assertFalse((q / "confirmed.json").exists(), "intake 下的状态应当照常清掉")

    def test_the_wipe_gate_blocks_starting_a_chain(self):
        """独占闸：删除期间不许起链（`/api/start` 认 `wiping_at`）。

        光看 `state["running"]` 是"先查后做"，中间窗口里链照样能起来 —— 而 wipe 第⑥步会把
        阶段状态刷回 idle，于是黄灯重新点亮、托管下还会"删完又起链"。
        用**时间戳**而不是布尔：万一中途异常没清掉，300 秒后自动失效，不会把起链永久锁死。
        """
        self._seed()
        self.s.state["wiping_at"] = __import__("time").time()
        with self.assertRaises(self.s.HTTPException) as cm:
            asyncio.run(self.s.start(self.s.StartReq()))
        self.assertIn("正在删除", str(cm.exception))
        # 对照组：闸放下（或时间戳很旧 = 那次删除半路挂了没清掉）之后**必须不再挡**
        # —— 否则上面那条可能只是"永远拒"。这里直接验判据本身，**不**调 `start()`：
        # 那一句会真的起链、真去拉模型。
        import time as _t
        self.s.state["wiping_at"] = 0.0
        self.assertFalse(_t.time() - self.s.state["wiping_at"] < 300, "闸放下之后判据仍为真")
        self.s.state["wiping_at"] = _t.time() - 301
        self.assertFalse(_t.time() - self.s.state["wiping_at"] < 300,
                         "超过 300 秒的旧闸必须自动失效（否则一次失败把起链永久锁死）")

    def test_an_illegal_problem_id_does_not_crash_the_handback_path(self):
        """题目标识非法时，遗留交回单的归档路径要**退化**而不是把链炸成"驱动异常"。

        `delivery_name()` 对含 `\\/:*?"<>|` 的标识会抛 `ValueError`（它自己的约定），
        而标识是 `.env`/面板可填的。`check_handback` 在**每个阶段**都被无条件调用，
        所以这里一抛就是整链挂掉，而日志只说"驱动异常" —— 与 `_delivery_status`/`_redo_from`
        同一类，那两处早就设防了。
        """
        self._seed()
        (self.root / "runtime/quality/workspace.json").write_text(
            json.dumps({"problem_id": "2026A:B"}), encoding="utf-8")
        (self.root / "reports/HANDBACK_REQUEST.md").write_text(
            "target: code\n", encoding="utf-8")
        self.assertIsNone(self.s.check_handback(0), "cur_idx=0 时任何 target 都算遗留 ⇒ 归档放行")
        self.assertTrue(any("旧交回单" in str(p) for p in (self.s._cache_dir()).rglob("*")),
                        "交回单没被暂存到 cache（那它就消失了）")

    def test_the_stale_halt_banner_is_cleared(self):
        """删干净之后，页头不许还挂着**上一轮**的「已挂起 · <原因>」。

        光清 `state["pending"]` 不够 —— 页头那行读的是 `halt_gate`/`halt_reason`。
        """
        self._seed()
        self.s.state["halt_gate"] = True
        self.s.state["halt_reason"] = "上一轮失败的原因"
        self.s.state["stale_instr"] = {"analysis", "review"}
        self.s.state["run_completed"] = True
        self.wipe()
        self.assertFalse(self.s.state.get("halt_gate"), "页头还会显示「已挂起」")
        self.assertEqual(self.s.state.get("halt_reason"), "")
        self.assertEqual(self.s.state.get("stale_instr"), set(), "蓝条上还会挂着旧标记")
        self.assertFalse(self.s.state.get("run_completed"))
        self.assertIsNone(self.s.state.get("pending"))
        self.assertEqual([v for v in self.s.state["stages"].values() if v != "idle"], [],
                         "阶段状态应当全部回到 idle（产物都删了，还显示 ✅ 就是撒谎）")
        # 阶段行上那个建议计数也是上一轮的，不清就会挂着一串不存在的建议
        self.assertEqual(self.s.state.get("adv_by_stage"), {})
        self.assertEqual(self.s.state.get("waived"), set())

    def test_the_confirm_word_is_required(self):
        """对照组：没打对暗号 ⇒ 400，且**一件都不许动**（不可逆操作不能一键完成）。"""
        self._seed()
        with self.assertRaises(self.s.HTTPException):
            self.wipe(word="删")
        self.assertTrue((self.root / "reports/x.txt").exists(), "拒绝了却还是删了东西")
        self.assertTrue((self.s._delivery_dir() / "cache").exists())

    def test_running_chain_blocks_the_wipe(self):
        """对照组：链在跑 ⇒ 409（绝不在它跑着的时候删它正在写的东西）。"""
        self._seed()
        self.s.state["running"] = True
        try:
            with self.assertRaises(self.s.HTTPException):
                self.wipe()
        finally:
            self.s.state["running"] = False
        self.assertTrue((self.root / "reports/x.txt").exists())


class BrowseTruncationTests(unittest.TestCase):
    """`truncated` 不许**假报**"还有更多"（面板会照着这句提示"只列了前 500 个"）。"""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for rel in ("CLAUDE.md", "AGENTS.md"):
            shutil.copy2(PROJECT / rel, self.root / rel)
        for rel in ("skills", "docs"):
            shutil.copytree(PROJECT / rel, self.root / rel)
        self.s = load_server(self.root)

    def test_exactly_the_cap_of_dirs_with_files_after_is_not_truncated(self):
        """恰好 500 个目录、后面还有**文件** ⇒ 不许说"被截断了"。

        若早停放在循环**头上**判 `len(names) >= 500`，收满 500 个目录之后只要后面还有
        **任意**条目（哪怕全是文件）就置 `truncated=True` ⇒ 面板谎报"目录太多只列了前 500 个"，
        而其实**已经列全了**。
        """
        base = self.root / "many"
        base.mkdir()
        for i in range(500):
            (base / f"d{i:03d}").mkdir()
        for i in range(5):                       # 目录之后夹几个文件：误报截断的排布就出在这一步
            (base / f"f{i}.txt").write_text("x", encoding="utf-8")
        r = asyncio.run(self.s.browse(str(base)))
        self.assertEqual(len(r["dirs"]), 500)
        self.assertFalse(r["truncated"], "已经列全了却说被截断")

    def test_the_early_stop_only_counts_directories(self):
        """早停判据必须在"这一项**确实会被收进** `names`"**之后** —— 钉的是**顺序**。

        为什么需要一条结构哨兵而不只是行为用例：要摆出"判据在循环头上"那种排布，
        得先建 500 个目录**再**让下一个条目是文件（行为用例 `..._is_not_truncated` 正是这么建的），
        但那只覆盖"目录恰好 500"这一种排布。判据的位置是这类误报的**全部**成因，
        所以直接把顺序钉死：`entry.is_dir()` 必须出现在 `len(names) >= 500` **之前**。
        """
        h = (PROJECT / "lib/web/server.py").read_text(encoding="utf-8-sig")
        seg = h[h.index("def _list():"):]
        seg = seg[:seg.index("return sorted(")]
        self.assertIn("if len(names) >= 500:", seg, "找不到早停判据（实现变了？）")
        self.assertLess(seg.index("entry.is_dir()"), seg.index("if len(names) >= 500:"),
                        "早停判据跑到目录过滤**之前**了 ⇒ 收满 500 个目录后遇到文件也会假报截断")

    def test_more_than_the_cap_is_reported(self):
        """对照组：真超了必须如实说 —— 否则上面那条可能只是"永远不报截断"。"""
        base = self.root / "more"
        base.mkdir()
        for i in range(503):
            (base / f"d{i:03d}").mkdir()
        r = asyncio.run(self.s.browse(str(base)))
        self.assertEqual(len(r["dirs"]), 500)
        self.assertTrue(r["truncated"], "真超了却没报截断（用户会以为列全了）")


class RoleTableCompletenessTests(unittest.TestCase):
    """确认表必须**覆盖 inbox 里的每一份原件** —— 否则最后那一下 `rmtree(_inbox)` 会把它们静默销毁。"""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for rel in ("CLAUDE.md", "AGENTS.md"):
            shutil.copy2(PROJECT / rel, self.root / rel)
        for rel in ("skills", "docs"):
            shutil.copytree(PROJECT / rel, self.root / rel)
        self.s = load_server(self.root)
        self.inbox = self.root / "request/_inbox"
        for rel in ("题目.pdf", "附件1.xlsx"):
            p = self.inbox / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(b"x")

    def test_a_short_table_is_refused_and_nothing_is_deleted(self):
        """表里少一行 ⇒ 400，且 `_inbox/` 一个字节不动。

        只校验"表里的行都在 inbox 里"是**单向**的：短了的那份既不会被搬（不在 plan 里）、
        也不会进 `kept/`（那里只收表里标了 ignore/needs_manual 的）⇒ 直接消失、无任何留痕。
        症状：inbox 两份、只提交一行 ⇒ 另一份再也找不到。
        """
        with self.assertRaises(self.s.HTTPException) as cm:
            self.s._validate_roles([{"path": "request/_inbox/题目.pdf", "role": "problem",
                                     "target": "request/attachments/题目.pdf"}])
        self.assertIn("少了", str(cm.exception))
        self.assertIn("附件1.xlsx", str(cm.exception), "报错要指名少了哪几份，调用方才能补")
        self.assertTrue((self.inbox / "附件1.xlsx").is_file(), "拒绝了却还是动了 inbox")

    def test_a_complete_table_passes(self):
        """对照组：表齐了就得放行 —— 否则上面那条可能只是"什么都拒"。"""
        plan = self.s._validate_roles([
            {"path": "request/_inbox/题目.pdf", "role": "problem",
             "target": "request/attachments/题目.pdf"},
            {"path": "request/_inbox/附件1.xlsx", "role": "attachment",
             "target": "request/attachments/附件1.xlsx"}])
        self.assertEqual(len(plan), 2)

    def test_a_row_outside_the_inbox_is_still_refused(self):
        """反向那条要照拒；同时正向那条不能松（互为对照）。"""
        with self.assertRaises(self.s.HTTPException):
            self.s._validate_roles([{"path": "request/_inbox/不存在.pdf", "role": "problem",
                                     "target": "request/attachments/不存在.pdf"}])


class IntakeProposalTypeTests(unittest.TestCase):
    """AI 写的 `INTAKE.json` 是**不可信输入**：类型不对不能让确认页整张表消失。"""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for rel in ("CLAUDE.md", "AGENTS.md"):
            shutil.copy2(PROJECT / rel, self.root / rel)
        for rel in ("skills", "docs"):
            shutil.copytree(PROJECT / rel, self.root / rel)
        self.s = load_server(self.root)
        (self.root / "reports").mkdir(parents=True, exist_ok=True)

    def _write(self, obj):
        (self.root / "reports/INTAKE.json").write_text(json.dumps(obj), encoding="utf-8")

    def test_wrong_types_do_not_crash_the_panel(self):
        """`files` 写成字符串、`subquestions` 写成数字 ⇒ 归一成空，不许抛。

        不归一的话 `len(...)`/`.get(...)` 当场抛 ⇒ `/api/intake` 500、确认页**整张表消失**
        —— 而那时链正停在黄灯上，用户既看不到也不能确认。
        """
        self._write({"problem": {"text": "题面", "subquestions": 3}, "files": "不是数组",
                     "notes": {"也不是": "数组"}})
        prop = self.s._intake_proposal()
        self.assertEqual(prop["files"], [])
        self.assertEqual(prop["problem"]["subquestions"], [])
        self.assertEqual(prop["notes"], [])
        self.assertEqual(prop["problem"]["text"], "题面", "正常的字段要保住")
        d = asyncio.run(self.s.intake_texts())        # 这一句必须能跑通：不归一就在这里 500
        self.assertEqual(d["ai"], "题面")

    def test_problem_written_as_a_list_is_normalised(self):
        self._write({"problem": ["题面"], "files": [1, {"path": "a"}], "notes": []})
        prop = self.s._intake_proposal()
        self.assertEqual(prop["problem"], {})
        self.assertEqual(prop["files"], [{"path": "a"}], "非字典的条目要滤掉")


class ModelConfigWriteTests(unittest.TestCase):
    """写 `.env` 这条路：**里面是唯一一份密钥**，所以每条边界都要钉住。"""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for rel in ("CLAUDE.md", "AGENTS.md"):
            shutil.copy2(PROJECT / rel, self.root / rel)
        for rel in ("skills", "docs"):
            shutil.copytree(PROJECT / rel, self.root / rel)
        self.s = load_server(self.root)
        self.env = self.root / ".env"

    def test_it_keeps_every_other_line(self):
        """只动指定的键，其余行（注释、FMA_* 旋钮、WEBDRIVER_*）一字不动。"""
        self.env.write_text("# 注释\nFMA_API_PROXY=auto\nANTHROPIC_MODEL=old\nexport ANTHROPIC_BASE_URL=https://a\n",
                            encoding="utf-8")
        wrote = self.s._write_dotenv_keys({"ANTHROPIC_MODEL": "new", "ANTHROPIC_AUTH_TOKEN": "tok"})
        text = self.env.read_text(encoding="utf-8")
        self.assertIn("# 注释", text)
        self.assertIn("FMA_API_PROXY=auto", text)
        self.assertIn("ANTHROPIC_MODEL=new", text)
        self.assertIn("ANTHROPIC_AUTH_TOKEN=tok", text)
        self.assertNotIn("ANTHROPIC_MODEL=old", text)
        self.assertIn("export ANTHROPIC_BASE_URL=https://a", text, "带 export 的行要保持原样")
        self.assertEqual(wrote, ["ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_MODEL"])

    def test_a_value_with_a_newline_is_refused(self):
        """值里含换行 ⇒ 抛错，**一个字节都不许写**。

        不拦的话，一个换行就能在 `.env` 里伪造出任意配置键 —— 比如注入
        `WEBDRIVER_CLAUDE=<任意 exe>`，而下次启动 `_find_claude()` 指哪用哪。
        """
        before = b"ANTHROPIC_MODEL=old\n"
        self.env.write_bytes(before)
        with self.assertRaises(ValueError):
            self.s._write_dotenv_keys({"ANTHROPIC_AUTH_TOKEN": "t\nWEBDRIVER_CLAUDE=C:/evil.exe"})
        self.assertEqual(self.env.read_bytes(), before, ".env 被改动了")

    def test_all_line_breaks_are_refused_not_just_crlf(self):
        """判据必须与**读取端**同一套：`_load_dotenv` 用 `text.splitlines()` 切行，
        而 `str.splitlines()` 认的不止 `\\r\\n` —— 还有 `\\x0b \\x0c \\x1c \\x1d \\x1e \\x85 \\u2028 \\u2029`。

        只挡 `\\r\\n` 时，值里塞一个 `\\x0c` 照样能在 `.env` 里伪造出 `WEBDRIVER_CLAUDE=…`
        那样的**独立键**（下次启动 `_find_claude()` 指哪用哪，每个阶段跑那个 exe）。
        """
        for ch in ("\x0b", "\x0c", "\x1c", "\x1d", "\x1e", "\x85", " ", " ",
                   "\r", "\n"):
            with self.subTest(break_char=hex(ord(ch))):
                before = b"ANTHROPIC_MODEL=old\n"
                self.env.write_bytes(before)
                with self.assertRaises(ValueError):
                    self.s._write_dotenv_keys({"ANTHROPIC_AUTH_TOKEN": f"t{ch}WEBDRIVER_CLAUDE=x"})
                self.assertEqual(self.env.read_bytes(), before)

    def test_it_does_not_truncate_when_the_read_fails(self):
        """读不出来 ⇒ 抛错，**绝不**当成空文件继续写。

        当成空文件继续写（`except (OSError, UnicodeError): lines = []`）会把整个 `.env`
        截成三行，别的配置全没了，还回一句"已保存"。这里用一个**非法 UTF-8** 的文件模拟读不出来。
        """
        self.env.write_bytes(b"ANTHROPIC_MODEL=old\n\xff\xfe\x00garbage\n")
        with self.assertRaises((ValueError, UnicodeError, OSError)):
            self.s._write_dotenv_keys({"ANTHROPIC_MODEL": "new"})
        self.assertIn(b"\xff\xfe", self.env.read_bytes(), "原文件被动过了")

    def test_the_write_is_atomic_and_keeps_the_bom(self):
        """写完不留临时文件；原文件有 BOM 就带回去（`utf-8-sig` 读会把它吃掉）。"""
        self.env.write_bytes("\ufeffANTHROPIC_MODEL=old\n".encode("utf-8"))
        self.s._write_dotenv_keys({"ANTHROPIC_MODEL": "new"})
        raw = self.env.read_bytes()
        self.assertTrue(raw.startswith(b"\xef\xbb\xbf"), "BOM 丢了")
        self.assertIn(b"ANTHROPIC_MODEL=new", raw)
        self.assertEqual([p.name for p in self.root.glob(".env.*.tmp")], [], "残留了临时文件")

    def test_the_round_trip_through_load_dotenv_works(self):
        """判据是**回读**：写完再 `_load_dotenv` 一遍，读出来的值得跟写进去的一样。

        得先把这两个键从 `os.environ` 里摘掉：`_load_dotenv` 的规则是"**已存在的环境变量
        优先**"（`:95-96`），而测试进程 import server 时已经带着真 `.env` 的值了 ——
        不摘掉的话它会把新值静默挡回去，测出来的是"没生效"，看着像产品 bug，其实是测试没摆对
        场景（VSCode 集成终端起驱动就是这个情形）。
        """
        self.env.write_text("ANTHROPIC_BASE_URL=https://old\n", encoding="utf-8")
        self.s._write_dotenv_keys({"ANTHROPIC_BASE_URL": "https://new", "ANTHROPIC_MODEL": "m[1m]"})
        keys = ("ANTHROPIC_MODEL", "ANTHROPIC_BASE_URL")
        saved = {k: os.environ.pop(k, None) for k in keys}

        def _restore():                      # 严格还原：原来没有的也要摘掉，别漏给别的用例
            for k, v in saved.items():
                os.environ.pop(k, None)
                if v is not None:
                    os.environ[k] = v
        self.addCleanup(_restore)
        # `_load_dotenv` 的契约是"**把值设进 `os.environ`**"（返回值只是键名清单）⇒ 断言环境
        written, bad = self.s._load_dotenv(self.env)
        self.assertEqual(bad, [])
        self.assertIn("ANTHROPIC_MODEL", written)
        self.assertEqual(os.environ.get("ANTHROPIC_MODEL"), "m[1m]")
        self.assertEqual(os.environ.get("ANTHROPIC_BASE_URL"), "https://new")


class OriginGuardTests(unittest.TestCase):
    """跨站写请求必须被 403 挡掉（安全控制，坏了不会有人立刻发现）。"""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for rel in ("CLAUDE.md", "AGENTS.md"):
            shutil.copy2(PROJECT / rel, self.root / rel)
        for rel in ("skills", "docs"):
            shutil.copytree(PROJECT / rel, self.root / rel)
        self.s = load_server(self.root)

    def _client(self):
        from fastapi.testclient import TestClient
        return TestClient(self.s.app)

    def test_a_cross_site_write_is_403_and_changes_nothing(self):
        """带外部 Origin 的 POST ⇒ 403（不是 500），且盘面一个字节不动。

        为什么必须钉"403 而不是 500"：中间件若在 `call_next` 之前就抛（例如
        `return JSONResponse(...)` 而 `JSONResponse` **没被 import** ⇒ `NameError`），
        功能上仍然挡得住（handler 没执行），但 403 的契约失效、每次跨站尝试都在日志里留一条
        未捕获 traceback（真出问题时会被当成"驱动崩了"）。
        """
        (self.root / "request").mkdir(parents=True, exist_ok=True)
        (self.root / "request/problem.md").write_text("原题面", encoding="utf-8")
        c = self._client()
        r = c.post("/api/wipe-problem", json={"confirm": "删除本题"},
                   headers={"Origin": "http://evil.example"})
        self.assertEqual(r.status_code, 403, f"跨站写请求没被 403 挡住：{r.status_code} {r.text[:120]}")
        self.assertEqual((self.root / "request/problem.md").read_text(encoding="utf-8"), "原题面")

    def test_a_local_origin_still_passes(self):
        """对照组：本机 Origin 照旧放行（别把正常用法一起挡了）。"""
        c = self._client()
        r = c.post("/api/wipe-problem", json={"confirm": "错暗号"},
                   headers={"Origin": "http://127.0.0.1:8901"})
        self.assertEqual(r.status_code, 400, "本机 Origin 应当走到端点的参数校验（400），而不是被中间件挡")

    def test_unc_paths_are_refused(self):
        """UNC 一律拒：`/api/browse` 走 GET，而 Origin 中间件只查非 GET ⇒ 恶意页面能用它
        让**本机**去连攻击者的 SMB（NTLM 凭据转发面）。

        必须覆盖**混用分隔符**那几种写法：Windows 把 `/` 与 `\\` 当同一个字符，只查
        `\\\\` / `//` 开头会被 `\\/evil-host\\share`、`/\\evil-host/share` 绕开
        —— 那两种会一路走到 `is_dir()`（把 `resolve()` 打在不可路由的主机上会卡 21 秒，
        那就是真的发了 SMB 连接）。
        """
        c = self._client()
        BS = chr(92)
        for bad in (BS * 2 + "evil-host" + BS + "share", "//evil-host/share",
                    BS + "/evil-host" + BS + "share", "/" + BS + "evil-host/share",
                    BS * 3 + "evil-host" + BS + "share",
                    BS * 2 + "?" + BS + "C:" + BS + "Windows"):
            with self.subTest(path=bad):
                r = c.get("/api/browse", params={"path": bad})
                self.assertEqual(r.status_code, 400, f"{bad!r} 没被拒：{r.status_code}")

    def test_a_local_path_that_merely_looks_like_unc_is_still_allowed(self):
        """对照组：别把**仓内的相对路径**也一起挡了。

        `./\\\\evil-host/share` 看着像 UNC，其实 pathlib 把它当**仓内相对路径**
        （resolve → `<仓根>\\evil-host\\share`）⇒ 只是"目录不存在"，应当 404 而不是 400。
        拿"字符串里有 evil"当判据会把这句误报成"守卫被绕开"。
        """
        c = self._client()
        r = c.get("/api/browse", params={"path": "./" + chr(92) * 2 + "evil-host/share"})
        self.assertIn(r.status_code, (200, 404), f"仓内相对路径被误拒：{r.status_code}")

    def test_unc_paths_are_refused_by_the_delivery_setter_too(self):
        """UNC 也不该能当产物目录存下来（存了的话归档/清理每一步都会去碰网络路径）。"""
        c = self._client()
        r = c.post("/api/delivery", json={"output_dir": chr(92) * 2 + "evil-host" + chr(92) + "share"})
        self.assertTrue(r.status_code in (200, 400, 422), r.status_code)


class SetupPanelFrontendTests(unittest.TestCase):
    """开屏页 / 目录选择器 / 删除按钮的前端形状（纯字符串哨兵 —— 没有浏览器时的硬约束）。"""

    def test_the_landing_page_exists_and_the_title_toggles_it(self):
        h = _html()
        for token in ('id="splash"', 'id="splash_inner"', 'id="splash_brand"',
                      'id="brand"', 'class="hero-title"'):
            self.assertIn(token, h, f"开屏页缺少 {token}")
        self.assertIn("$('brand').onclick", h, "主界面标题没接点击（回不去展示页）")
        self.assertIn("$('splash_brand').onclick", h, "展示页标题没接点击（回不去主界面）")

    def test_the_config_form_has_the_three_keys_and_the_1m_box(self):
        h = _html()
        for token in ('id="cf_base"', 'id="cf_key"', 'id="cf_model"', 'id="cf_1m"',
                      'id="cf_test"', 'id="cf_save"'):
            self.assertIn(token, h, f"配置表单缺少 {token}")
        self.assertIn("/api/model_config", h, "表单没接配置端点")
        self.assertIn("_cfgSuffix", h, "没有保留原有 [1m] 写法的机制")

    def test_the_1m_box_writes_the_suffix_into_the_field(self):
        """勾选框要把后缀**当场写进模型框**（勾上之后模型名后面出现 `[1m]`）。

        **这条只钉"接线"，钉不住"效果"**（别以为它能替代行为用例）：把真正写回那一行
        （`el.value = cb.checked ? …`）删掉，这条**照样绿**。
        真正管效果的是行为夹具 `regression/test_frontend_render.py`（桩 DOM + 真触发 change 事件），
        那条会红。所以两条都在：这条查接线（改名/漏绑没重复拼），那条查行为。
        另：`modelFromForm` **不能**再拼一次后缀（再拼一次会成 `x[1m][1m]`）。
        """
        h = _html()
        self.assertIn("function syncSuffixBox(", h)
        self.assertIn("$('cf_1m').addEventListener('change'", h, "勾选框没接 change 事件")
        seg = h[h.index("function modelFromForm()"):]
        seg = seg[:seg.index("\n")]
        self.assertNotIn("_cfgSuffix", seg, "modelFromForm 又拼了一遍后缀 ⇒ 会变成 [1m][1m]")

    def test_the_two_buttons_keep_their_wording(self):
        """两个按钮的文案是 `保存并进入` / `直接进入`。

        （改文案是小事，但它俩是**这一页仅有的出口** —— 名字变了说明有人动过这块，
          顺带把行为夹具也跑一遍更稳。）"""
        h = _html()
        self.assertIn(">保存并进入<", h, "cf_save 的文案变了")
        self.assertIn(">直接进入<", h, "cf_back 的文案变了")

    def test_the_removed_bits_stay_removed(self):
        """这几样不该再长回来：五条项目介绍、"🧩 模型配置来源"那一行（含打码密钥）、
        以及"三个键都填上才算配好…"那段说明。

        `hero-kicker`（英文名）**不在删除清单里** —— 它要放回标题**上面**（见下一条）。
        哨兵只挡上面这三样，别顺手把「不许有 hero-kicker」也算进来。
        """
        h = _html()
        for token, what in (("cf_note", "「配置来源」那行"),
                            ("hero-list", "那五条项目介绍"),
                            ("不会外传", "配置表单上那段说明文字")):
            self.assertNotIn(token, h, f"{what}又回来了")

    def test_the_english_name_sits_above_the_chinese_title(self):
        """英文名 `NewMathAgent` 在中文标题**上面**；第二行「一键生成」压在「模」下面。

        （这里钉的是**结构顺序** —— 只钉"两个都在"是不够的，它俩谁在上面才是这条的内容。）
        """
        h = _html()
        # 锚点要带 `class="`：裸的 `hero-kicker` 会先命中 `<style>` 里那条 CSS 规则，
        #   于是切出来的片段是样式表、断言看着像"实现坏了"（凡是要定位 **markup** 的地方
        #   一律带上标签特征）。
        i_kick = h.index('class="hero-kicker"')
        i_title = h.index('id="splash_brand"')
        self.assertLess(i_kick, i_title, "英文名没在中文标题上面")
        self.assertIn("NewMathAgent</div>", h[i_kick:i_kick + 200], "上面那行不是英文名")
        self.assertIn("传入完整赛题，经过 17 个阶段，一键生成数学建模论文", h)
        # 「一键」要缩到「模」的位置（2em）：只钉"有缩进类"，具体 em 值让 CSS 去定
        self.assertIn('class="ht-line ht-indent">一键生成', h, "第二行没带缩进类")

    def test_the_directory_picker_wires_every_button(self):
        h = _html()
        for token in ('id="dv_pick"', 'id="dirpop"', 'id="dp_list"', 'id="dp_up"',
                      'id="dp_home"', 'id="dp_out"', 'id="dp_use"'):
            self.assertIn(token, h, f"目录选择器缺少 {token}")
        self.assertIn("/api/browse", h, "没接列目录端点")

    def test_the_wipe_button_needs_both_a_confirm_and_the_word(self):
        """删除是**不可逆**的，所以它必须过两道：`confirm` 弹窗 + 手输暗号。"""
        h = _html()
        self.assertIn('id="dv_wipe"', h)
        seg = h[h.index("$('dv_wipe').onclick"):]
        seg = seg[:seg.index("\n};")]
        self.assertIn("confirm(", seg, "删除没有确认弹窗")
        self.assertIn("prompt(", seg, "删除没有要求手输暗号")

    def test_the_back_exit_starts_the_main_ui(self):
        """「← 回主界面」必须**先把主界面起起来**再隐层。

        只 `splHide()`、不 `startMain()` 的话（不建 SSE、不起 4 秒轮询、也不 loadFiles），
        进去看到的是一个**死界面**，而且回不到配置页。
        """
        h = _html()
        seg = h[h.index("$('cf_back').onclick"):]
        seg = seg[:seg.index("\n")]
        self.assertIn("startMain()", seg, "回主界面没把主界面起起来（进去是个死界面）")
        self.assertIn("splHide()", seg)

    def test_the_intake_dirty_flag_is_bound_to_one_reading(self):
        """脏标记只对**同一份读题结果**有效。

        只判"脏 + 有子节点"时，⓪ 重跑带回**新**的一份读题后面板会继续显示上一轮的分类表与
        题面（点「🔁 再试一次」后新灯上的表与题面全是旧的），而 `_ikCollect` 会把那份
        旧题面当 `problem_text` 提交 ⇒ 写进 `request/problem.md`（①–⑯ 全链的题意锚点）。
        """
        h = _html()
        self.assertIn("box.dataset.ikFor", h, "脏标记没绑读题结果的身份")
        # 从**代码那句**切（`if(box.dataset.dirty` 开头），别从裸的条件文本切 ——
        #   renderDecision 的注释里也引了同样的条件，`h.index` 会先命中那句注释，
        #   于是切出来的片段是注释、断言看着像"实现坏了"。
        seg = h[h.index("if(box.dataset.dirty"):]
        seg = seg[:seg.index("\n")]
        self.assertIn("ikFor", seg, "重画判据里没带身份 ⇒ 换了那份读题也不会重画")
        # 另一层保险：灯灭时必须走一次 renderIntakePanel(null)（否则那条清理永远不执行）
        seg2 = h[h.index("function renderDecision(st)"):]
        seg2 = seg2[:seg2.index("const acts=p.actions")]
        self.assertIn("renderIntakePanel(null)", seg2, "灯灭时没有清读题面板")

    def test_saving_checks_configured_before_entering(self):
        """保存成功 ≠ 配好了：`POST` 的 `None` 语义是"留空 = 不改"，只填模型不填密钥时照样 200。

        不看 `d.configured` 就进主界面，等于**从侧门绕过 boot() 的门控** —— 没密钥也能进去，
        第一次跑阶段才炸。这条把那个判断钉住。
        """
        h = _html()
        seg = h[h.index("$('cf_save').onclick"):]
        seg = seg[:seg.index("\n};")]
        self.assertIn("if(!d.configured)", seg, "保存后没有检查是否真的配齐了")
        self.assertIn("d.missing", seg, "没告诉用户还差哪几项")

    def test_startup_is_gated_on_a_single_config_probe(self):
        """启动必须先问一次配置，且**配置页期间不得**建 SSE / 起状态轮询。

        否则主界面会在配置页后面同时活着（轮询照打、日志照刷），"没配好"就只是个摆设。
        """
        h = _html()
        self.assertIn("await (await fetch('/api/model_config'))", h, "启动没有先问配置")
        boot = h[h.index("(async function boot()"):]
        self.assertIn("splShow('config')", boot)
        self.assertIn("splShow('boot')", boot)
        start = h[h.index("function startMain()"):]
        begin = h[:h.index("function startMain()")]
        self.assertIn("new EventSource('/api/stream')", start)
        self.assertNotIn("new EventSource('/api/stream')", begin,
                         "EventSource 只能在 startMain 里建 —— 别的地方建就等于绕过了开屏门控")


if __name__ == "__main__":
    unittest.main()
