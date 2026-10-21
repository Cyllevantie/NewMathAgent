"""产物路径点选、不归档删除本题、开屏配置页 —— 三块的哨兵与对照组。

为什么单独一个文件：这三件都是**界面侧**能力，其中「删除本题」是全仓
**第一条真删数据**的路径（别的都是 `rename` 归档或 `move` 暂存），风险与别的都不一样，
值得有自己的一组判据 + 对照组。

手法照 `test_intake.py`：用 `load_server` 把 ROOT 指到临时目录，**不碰真工作区**。
"""
import asyncio
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

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

    def test_a_unc_path_is_refused_before_it_is_stored(self):
        """网络路径在**落盘前**就要断掉：存下去之后归档/清理/删除每一步都过网络，
        `POST /api/wipe-all` 的 rmtree 更会直接打到远端共享。

        对照组：只是"看着像 UNC"的本机相对路径（`./\\\\evil-host/share`，`resolve()` 之后
        其实是仓内某个目录名）不能被误拒 —— 判据是 `_is_unc_path`，不是"字符串里有反斜杠"。
        """
        f = self.s._store_output_dir
        for bad in (chr(92) * 2 + "evil-host" + chr(92) + "share",
                    "//evil-host/share"):
            with self.assertRaises(self.s.HTTPException) as cm:
                f(bad)
            self.assertEqual(cm.exception.status_code, 400, bad)
        # 对照组：本机路径照常
        self.assertEqual(f(str(self.root / "产物")), "产物")

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


def _seed_a_run_workspace(s):
    """造一份"跑过一轮"的盘面：产物 + 题面附件 + 状态 + 草稿各就各位。

    两份删除口径（`products` / `everything`）**共用这一份夹具** —— 它们的差别只在
    `wipe()` 打哪个端点，盘面必须一模一样，否则对照组证明不了"差的就是那几样"。
    """
    r = s.ROOT
    for rel in ("reports", "code", "results", "figures", "paper", "demo", "paper_appendix"):
        (r / rel).mkdir(parents=True, exist_ok=True)
        (r / rel / "x.txt").write_text("产物 " * 40, encoding="utf-8")
    (r / "运行说明.md").write_text("说明 " * 40, encoding="utf-8")
    # 题面与附件（`products` 口径下**必须留下**）
    (r / "request/attachments").mkdir(parents=True, exist_ok=True)
    (r / "request/problem.md").write_text("题面正文", encoding="utf-8")
    (r / "request/attachments/附件1.xlsx").write_bytes(b"xlsx")
    (r / "data").mkdir(exist_ok=True)
    (r / "data/d.csv").write_text("a,b\n1,2\n", encoding="utf-8")
    # 阶段草稿与探针：`_tmp/` 与 `tmp/` 是**两个**目录，各阶段两个都用
    #   （`skills/_references/stage_discipline.md` 自己提醒过"另有散落的在 tmp/"）；
    #   `plan.md`/`todo.md` 是每道题的规划件，落在项目根。只有 `everything` 口径会删它们。
    (r / "_tmp").mkdir(exist_ok=True)
    (r / "_tmp/草稿.py").write_text("print(1)\n", encoding="utf-8")
    (r / "tmp/tbltest").mkdir(parents=True, exist_ok=True)
    (r / "tmp/tbltest/x.png").write_bytes(b"png")
    (r / "plan.md").write_text("整体流程方案\n", encoding="utf-8")
    (r / "todo.md").write_text("- [ ] 问题一\n", encoding="utf-8")
    (r / "runtime").mkdir(exist_ok=True)
    (r / "runtime/.watch_input.json").write_text("{}", encoding="utf-8")
    # 两个「最新」指针里放点东西 + cache
    out = s._delivery_dir()
    (out / "提交作品/最新作品").mkdir(parents=True, exist_ok=True)
    (out / "提交作品/最新作品/正文.pdf").write_bytes(b"pdf")
    (out / "各阶段产物/最新产物/编码计算").mkdir(parents=True, exist_ok=True)
    # cache 下**按题分目录**：本题一份、往届一份。归档名格式见 `delivery_name()`
    #   （`<题目标识>_<日期_时间>`），而"本题是谁"由 workspace.json 记着。
    (out / "cache/2026A_2026.9.25_18.32.16/工作区原件").mkdir(parents=True, exist_ok=True)
    (out / "cache/2026A_2026.9.25_18.32.16/工作区原件/旧产物.txt").write_text("本题的", encoding="utf-8")
    (out / "cache/2025B_2025.9.1_10.00.00").mkdir(parents=True, exist_ok=True)
    (out / "cache/2025B_2025.9.1_10.00.00/唯一的副本.txt").write_text("往届的", encoding="utf-8")
    # 轮转/「📦 归档本题并换新」留下的**兄弟目录**（与两个「最新」同级）——
    #   它们不在任何指针里，只有显式遍历父目录才看得见。盘上真实存在
    #   （`产物/各阶段产物/2026A_2026.10.4_18.24.29/`）。
    (out / "各阶段产物/2026A_2026.10.4_18.24.29/题目读取").mkdir(parents=True, exist_ok=True)
    (out / "各阶段产物/2026A_2026.10.4_18.24.29/题目读取/INTAKE.json").write_text("{}", encoding="utf-8")
    (out / "提交作品/2026A_2026.10.4_18.24.29").mkdir(parents=True, exist_ok=True)
    (out / "提交作品/2026A_2026.10.4_18.24.29/正文.pdf").write_bytes(b"pdf")
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
        _seed_a_run_workspace(self.s)

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
        # `waived` 的类型必须与初始化（`{}`）和写点（`state["waived"][sid] = rec`）一致 ——
        #   写成 `set()` 时，删完之后第一次「接受并披露」会在**已落盘之后**抛 TypeError，
        #   盘上多一条 waivers.json、内存与 pending 全没更新。这条断言原先钉的正是 `set()`
        #   （把错误值钉死了），已于 2026-10-04 改正。
        self.assertEqual(self.s.state.get("waived"), {})
        self.assertEqual(self.s.state.get("fix_required"), [])

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


class WipeEverythingTests(unittest.TestCase):
    """「删除全部内容」：连题面与附件一起删，回到**刚 clone 的状态**。

    与 `WipeProblemTests` 的差别就是这一族要钉的东西：那边保留的（题面/附件/数据集/
    `_tmp/`/「不动它」的原件/往届归档），这边**必须全删**；而两条**都不能碰**框架与脚本
    （2026-10-04 用户原话：「改动项目的脚本什么的不要删哈，只删题的产物」）。
    因此夹具与那边**共用同一份** `_seed_a_run_workspace`，最后还有一条把两个口径摆在一起比。
    """

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for rel in ("CLAUDE.md", "AGENTS.md"):
            shutil.copy2(PROJECT / rel, self.root / rel)
        for rel in ("skills", "docs"):
            shutil.copytree(PROJECT / rel, self.root / rel)
        # 框架本体里也摆几样"最容易被误伤"的：脚本、本机配置、展示文件夹、`.env`
        (self.root / "lib/web").mkdir(parents=True, exist_ok=True)
        (self.root / "lib/web/server.py").write_text("# 框架脚本\n", encoding="utf-8")
        (self.root / "config").mkdir(exist_ok=True)
        (self.root / "config/runtime.local.json").write_text('{"python": "", "tool_directories": []}',
                                                             encoding="utf-8")
        (self.root / "2026A试跑示例").mkdir(exist_ok=True)
        (self.root / "2026A试跑示例/q1.py").write_text("print(1)\n", encoding="utf-8")
        (self.root / ".env").write_text("# 本机配置\n", encoding="utf-8")   # 注释行：不往 os.environ 里放东西
        self.s = load_server(self.root)

    def wipe(self, word="删除全部"):
        return asyncio.run(self.s.wipe_everything(self.s.WipeReq(confirm=word)))

    def test_it_takes_the_problem_the_attachments_and_the_drafts_too(self):
        """主判据：题面/附件/数据集/草稿**一并删掉** —— 这正是与「不归档删除本题」的差别。"""
        _seed_a_run_workspace(self.s)
        out = self.wipe()
        self.assertTrue(out["ok"])
        r = self.root
        for rel in ("request", "data", "_tmp", "tmp", "plan.md", "todo.md",
                    "runtime/.watch_input.json"):
            self.assertFalse((r / rel).exists(), f"{rel} 应当被删掉（删完要重新上传赛题）")
        for rel in ("reports", "code", "results", "figures", "paper", "demo",
                    "paper_appendix", "运行说明.md"):
            self.assertFalse((r / rel).exists(), f"{rel} 应当被删掉")
        self.assertFalse((self.s._delivery_dir() / "cache").exists(),
                         "cache 整棵都要没 —— 这条口径不区分本题与往届（确认框里写明了）")
        self.assertFalse((self.s._delivery_dir() / "其他产物").exists())
        # 轮转留下的**兄弟目录**：它们与两个「最新」同级，不在任何指针里 ——
        #   只清指针的实现会把它们留成"用户认不出来的旧归档"（盘上真出现过）。
        out = self.s._delivery_dir()
        self.assertFalse((out / "各阶段产物/2026A_2026.10.4_18.24.29").exists(),
                         "归档出来的兄弟目录没删 —— 面板空了、产物根里还躺着一摞旧归档")
        self.assertFalse((out / "提交作品/2026A_2026.10.4_18.24.29").exists())
        self.assertEqual(sorted(p.name for p in (out / "各阶段产物").iterdir()), ["最新产物"])
        self.assertEqual(sorted(p.name for p in (out / "提交作品").iterdir()), ["最新作品"])
        self.assertFalse((r / "runtime/quality/stages.json").exists())
        self.assertFalse((r / "runtime/quality/pending_decision.json").exists())
        # `web_run.log` **不断言"不存在"**：删除函数末尾自己还要 log 一行摘要，
        #   而 log() 就是往这个文件 append —— 删完必然又建回来（内容只剩那行摘要）。
        #   （这里也断言不了：`load_server` 把模块的 log 换成了 Mock，测不出真写盘行为。）

    def test_the_framework_the_scripts_and_the_local_config_stay(self):
        """反面：**框架与脚本一个都不许动**（用户 2026-10-04 明确要求）。

        这条与主判据必须同时成立 —— 一份"把项目根整个 rmtree"的实现能满足主判据，
        却会把 `lib/`、`skills/`、`.env`、展示文件夹一起带走。
        """
        _seed_a_run_workspace(self.s)
        self.wipe()
        for rel in ("lib/web/server.py", "skills", "docs", "CLAUDE.md", "AGENTS.md",
                    "config/runtime.local.json", ".env", "2026A试跑示例/q1.py"):
            self.assertTrue((self.root / rel).exists(), f"{rel} 是项目自己的东西，不该被删")

    def test_the_kept_originals_go_too_here(self):
        """`intake/kept/` 的"不动它"原件：`products` 口径**留着**，这里**删掉**。

        两个口径在这里刚好相反，所以必须各钉一条 —— 拿掉 `every` 那条分支，这条会红；
        把 `products` 那条也改成删，`WipeProblemTests` 那条会红。
        """
        _seed_a_run_workspace(self.s)
        kept = self.root / "runtime/quality/intake/kept"
        (kept / "附件").mkdir(parents=True, exist_ok=True)
        (kept / "附件/备注.md").write_text("用户选的是「忽略（不动它）」", encoding="utf-8")
        self.wipe()
        self.assertFalse((kept / "附件/备注.md").exists(),
                         "「删除全部内容」要回到刚 clone，留一份用户看不见的原件副本是自相矛盾")

    def test_the_other_words_do_not_unlock_this_one(self):
        """暗号必须**是这个**：拿「删除本题」来删全部 ⇒ 400，且**一个字节都没动**。

        两道闸里最要紧的一道 —— 用户想删产物、手一滑点成"删除全部"，就靠这个字面拦住。
        """
        _seed_a_run_workspace(self.s)
        with self.assertRaises(self.s.HTTPException) as cm:
            self.wipe(word="删除本题")
        self.assertIn("删除全部", str(cm.exception))
        self.assertTrue((self.root / "request/problem.md").is_file(), "暗号打错却把题面删了")
        self.assertTrue((self.root / "reports/x.txt").is_file())

    def test_it_refuses_while_a_chain_is_running(self):
        """运行中 409，且什么都不删（与另一条口径同一把闸）。"""
        _seed_a_run_workspace(self.s)
        self.s.state["running"] = True
        with self.assertRaises(self.s.HTTPException) as cm:
            self.wipe()
        self.assertIn("正在跑", str(cm.exception))
        self.assertTrue((self.root / "request/problem.md").is_file())
        self.assertTrue((self.root / "reports/x.txt").is_file())

    def test_the_two_pointers_come_back_as_empty_skeletons(self):
        """两个「最新」的内容要没，但**骨架建回来** —— 交付与面板的路径假设靠它。"""
        _seed_a_run_workspace(self.s)
        self.wipe()
        out = self.s._delivery_dir()
        for ptr in (out / "提交作品/最新作品", out / "各阶段产物/最新产物"):
            self.assertTrue(ptr.is_dir(), f"{ptr.name} 的空骨架应当建回来")
            self.assertEqual(list(ptr.iterdir()), [], f"{ptr.name} 里不该还剩东西")

    def test_the_workspace_record_is_rewritten_to_the_current_digest(self):
        """`workspace.json` 记**现在**的 digest，否则下一次 ▶ 被当成换题白转一轮。"""
        _seed_a_run_workspace(self.s)
        self.wipe()
        path = self.root / "runtime/quality/workspace.json"
        self.assertTrue(path.is_file(), "workspace.json 应当被重建")
        self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["source_digest"],
                         self.s._source_digest(), "记的不是当前 digest ⇒ 下次 ▶ 会被当成换题")

    def test_the_previous_problem_id_does_not_leak_into_the_next_one(self):
        """「删除全部内容」要清题目标识 —— 它是**每题**的，面板已不再提供编辑入口。

        2026-10-17 实盘残留：`config/delivery.local.json` 与 `runtime/quality/workspace.json`
        里都留着上一题的 `seeing-sound-2026-10-15`，`/api/delivery` 原样回给面板；
        下一题会继承这个名字，而用户没有任何地方能改。模板是本机偏好，必须留下。
        """
        _seed_a_run_workspace(self.s)
        cfg = self.root / "config/delivery.local.json"
        cfg.parent.mkdir(parents=True, exist_ok=True)
        cfg.write_text(json.dumps({"output_dir": "", "problem_id": "上一题",
                                   "template": "zh/cumcm-latex"}, ensure_ascii=False),
                       encoding="utf-8")
        self.wipe()
        self.assertEqual(json.loads(cfg.read_text(encoding="utf-8"))["problem_id"], "",
                         "config/delivery.local.json 还留着上一题的标识")
        ws = json.loads((self.root / "runtime/quality/workspace.json").read_text(encoding="utf-8"))
        self.assertEqual(ws["problem_id"], "", "workspace.json 还留着上一题的标识")
        self.assertEqual(json.loads(cfg.read_text(encoding="utf-8"))["template"],
                         "zh/cumcm-latex", "模板是本机偏好，不该被一起清掉")

    def test_the_memory_state_types_match_their_writers(self):
        """删完之后的内存态必须能被**后续动作**直接用，而不只是"看着像清了"。

        2026-10-04 对抗性核查抓出来的真缺陷：`waived` 初始化是 `{}`、唯一写点是
        `state["waived"][sid] = rec`（披露那条路），而删除函数当时写的是 `set()` ——
        删完之后第一次「接受并披露」会在**已经 `_save_waivers` 落盘之后**抛
        `TypeError: 'set' object does not support item assignment`：盘上多一条
        waivers.json，内存、pending、续跑全没更新。同处的 `fix_required`（初始化 `[]`）
        也一样写成了 `set()`。
        **证伪**：把两处改回 `set()` / `set()`，这条立刻红。
        """
        _seed_a_run_workspace(self.s)
        self.wipe()
        st = self.s.state
        st["waived"]["review"] = {"why": "披露时就是这么写的"}     # 写点：`state["waived"][sid] = rec`
        st["fix_required"].append("RV7-1")                          # 写点：一律赋列表
        self.assertEqual(st["waived"]["review"]["why"], "披露时就是这么写的")
        self.assertEqual(st["fix_required"], ["RV7-1"])

    def test_a_second_wipe_is_harmless(self):
        """幂等：连点两次不该炸（第二次没什么可删，但要照样回 ok）。"""
        _seed_a_run_workspace(self.s)
        self.wipe()
        out = self.wipe()
        self.assertTrue(out["ok"])

    def test_a_locked_path_is_reported_instead_of_silently_left(self):
        """删不掉的项必须回给面板 —— 警告不能只写日志：本函数随后会删掉 `web_run.log`。

        2026-10-17 真事故：服务端 stdout 被重定向到 `_tmp/server_restart.out.log`，
        Windows 下这个打开的文件句柄让 `shutil.rmtree(_tmp)` 整体失败；`_rm` 只 log 了
        一条警告，而第 ④ 步紧接着删掉 `runtime/web_run.log`，面板只报「删了 17 项」，
        `_tmp/` 里 298 个旧文件原封不动。证伪：把 `failed.append` 去掉、只留 `log(...)`，
        本条的 `assertIn` 立刻红。
        """
        _seed_a_run_workspace(self.s)
        real_rmtree = shutil.rmtree

        def fake(path, *a, **kw):
            if Path(path).name == "_tmp":
                raise PermissionError("被别的程序占着")
            return real_rmtree(path, *a, **kw)

        with mock.patch.object(self.s.shutil, "rmtree", side_effect=fake):
            out = self.wipe()
        self.assertIn("_tmp/", out["failed"], "删不掉的项没回给面板")
        self.assertTrue((self.root / "_tmp").exists(), "对照组：失败的项确实还在盘上")

    def test_the_same_disk_under_the_other_scope_keeps_the_problem(self):
        """**对照组**：同一份盘面走「不归档删除本题」⇒ 题面、草稿、往届归档都还在。

        没有它，上面那几条删干净的断言可能只是"夹具本来就没有这些文件"。
        """
        _seed_a_run_workspace(self.s)
        asyncio.run(self.s.wipe_problem(self.s.WipeReq(confirm="删除本题")))
        self.assertTrue((self.root / "request/problem.md").is_file(), "那条口径不该动题面")
        self.assertTrue((self.root / "_tmp/草稿.py").is_file(), "那条口径不该动阶段草稿")
        self.assertTrue((self.root / "plan.md").is_file(), "那条口径不该动规划件")
        self.assertTrue((self.s._delivery_dir() / "cache/2025B_2025.9.1_10.00.00").is_dir(),
                        "那条口径只删本题那一份归档")
        self.assertTrue((self.s._delivery_dir() / "各阶段产物/2026A_2026.10.4_18.24.29").is_dir(),
                        "那条口径不碰兄弟归档 —— 那是用户**特意**归档留下来的（要连它也删，"
                        "就与「不归档删除本题」这个名字和确认框里的承诺都不符）")
        self.assertFalse((self.root / "reports/x.txt").exists(), "产物那边照删")


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


class ModelConfigReachesClaudeTests(unittest.TestCase):
    """模型三键必须**随命令行**递进去 —— 只放子进程 env 是无效的。

    2026-10-04 实测：把 `ANTHROPIC_BASE_URL` 指到一个本地监听再 spawn `claude -p`，
    它**一个请求都不发**、照样把话答完 —— 用的是 `~/.claude/settings.json` 的 `env` 那套。
    后果：开屏页填的钥匙/.env 里那把钥匙从头到尾没被用过，而「测试连接」照样「连通正常」、
    链也照样出结果（走的是别的凭据）。命令行 `--settings` 是压得过它的那条通道：
    同一把令牌从那里递，请求头上才真是它。

    每条正题都配一条对照组 —— 少了它们，一个无条件塞 `--settings` 的实现也能全绿，
    而那种实现会把"订阅/登录态用户"的凭据顶掉。
    """

    MODEL_KEYS = ("ANTHROPIC_BASE_URL", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_MODEL")

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for rel in ("CLAUDE.md", "AGENTS.md"):
            shutil.copy2(PROJECT / rel, self.root / rel)
        for rel in ("skills", "docs"):
            shutil.copytree(PROJECT / rel, self.root / rel)
        self.s = load_server(self.root)
        self.captured = {}

        captured = self.captured

        class FakePopen:
            def __init__(self, cmd, **kw):
                captured["cmd"] = list(cmd)
                self.pid, self.returncode = 424242, 0
                self.stdout = io.BytesIO(b"")

            def wait(self):
                return self.returncode

        real = self.s.subprocess.Popen
        self.s.subprocess.Popen = FakePopen
        self.addCleanup(setattr, self.s.subprocess, "Popen", real)

    def _set_env(self, values):
        """把三个键设成 `values`（没列的一律清掉），跑完还原。"""
        for k in self.MODEL_KEYS:
            old = os.environ.get(k)
            self.addCleanup(lambda k=k, old=old: os.environ.__setitem__(k, old)
                            if old is not None else os.environ.pop(k, None))
            os.environ.pop(k, None)
        os.environ.update(values)

    def _spawn(self):
        sh = {"pid": None, "lines": [], "sid": "review", "last_out": 0.0, "tail": ""}
        self.s._claude_worker(["claude", "-p", "x"], sh)
        return self.captured["cmd"]

    def _settings_env(self, cmd):
        self.assertIn("--settings", cmd,
                      "没把模型配置递给 claude —— 它会用用户级 settings 里那套，"
                      "`.env`/开屏页填的钥匙等于没填")
        return json.loads(cmd[cmd.index("--settings") + 1])["env"]

    def test_the_three_keys_ride_along_in_settings(self):
        cfg = {"ANTHROPIC_BASE_URL": "https://api.probe.test/anthropic",
               "ANTHROPIC_AUTH_TOKEN": "sk-probe-not-a-real-key",
               "ANTHROPIC_MODEL": "probe-model[1M]"}
        self._set_env(cfg)
        self.assertEqual(self._settings_env(self._spawn()), cfg)

    def test_only_the_configured_keys_are_passed(self):
        """有令牌时只带配过的键 —— 不许编出一个空端点/空模型名塞给人家。"""
        self._set_env({"ANTHROPIC_AUTH_TOKEN": "sk-probe-not-a-real-key",
                       "ANTHROPIC_MODEL": "probe-model[1M]"})
        self.assertEqual(self._settings_env(self._spawn()),
                         {"ANTHROPIC_AUTH_TOKEN": "sk-probe-not-a-real-key",
                          "ANTHROPIC_MODEL": "probe-model[1M]"})

    def test_a_logged_in_user_keeps_their_own_credentials(self):
        """对照组①：一个键都没配 ⇒ **不许**塞 `--settings`。

        订阅/登录态用户靠 claude 自己的凭据跑；塞一份空 env 进去等于把人家的登录顶掉
        —— 那是"修好了 A 弄坏了 B"。
        """
        self._set_env({})
        self.assertNotIn("--settings", self._spawn())

    def test_no_token_means_no_interference(self):
        """对照组②：只填了端点和模型名、**没有令牌** ⇒ 同样不插手。

        从仓库克隆下来还没配 `.env` 的人正落在这一档（仓库里那份 `.env` 的令牌就是空的）：
        强指端点而不给令牌只会把本来能跑的他顶成 401。判定"配没配"的那把尺子是**令牌**。
        """
        self._set_env({"ANTHROPIC_BASE_URL": "https://api.probe.test/anthropic",
                       "ANTHROPIC_MODEL": "probe-model[1M]"})
        self.assertNotIn("--settings", self._spawn())

    def test_the_test_button_also_passes_them(self):
        """「测试连接」走的是**另一个 spawn 口**（`subprocess.run`），必须同样带上。

        那个按钮测的就是"我刚填的这组能不能用"；不带 `--settings` 的话，它测的其实是
        claude 自己 settings 里那套 —— 于是**填什么都会「连通正常」**，
        正是用户看到的那一幕。
        """
        ran = {}

        class Done:
            returncode, stdout, stderr = 0, "可以", ""

        def fake_run(cmd, **kw):
            ran["cmd"] = list(cmd)
            return Done()

        real = self.s.subprocess.run
        self.s.subprocess.run = fake_run
        self.addCleanup(setattr, self.s.subprocess, "run", real)

        out = asyncio.run(self.s.test_model_config(self.s.ModelConfigReq(
            base_url="https://api.probe.test/anthropic",
            auth_token="sk-probe-not-a-real-key", model="probe-model[1M]")))
        self.assertTrue(out.get("ok"), out)
        self.assertEqual(self._settings_env(ran["cmd"]),
                         {"ANTHROPIC_BASE_URL": "https://api.probe.test/anthropic",
                          "ANTHROPIC_AUTH_TOKEN": "sk-probe-not-a-real-key",
                          "ANTHROPIC_MODEL": "probe-model[1M]"})


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
        """UNC **不许**当产物目录存下来。

        原先这条写的是 `assertTrue(r.status_code in (200, 400, 422))` —— 允许 200，
        于是它自称守的那条不变量（"不该存下来"）根本没被守住；实测当时确实**存下来了**
        （`config/delivery.local.json` 里躺着一个 `\\\\evil-host\\share\\`）。
        存下去的后果不只是"归档会碰网络路径"：`POST /api/wipe-all` 的 `rmtree` 会直接
        打到远端共享上。现在改成硬断言 400。
        """
        c = self._client()
        r = c.post("/api/delivery", json={"output_dir": chr(92) * 2 + "evil-host" + chr(92) + "share"})
        self.assertEqual(r.status_code, 400, r.text)
        self.assertFalse(self.s.DELIVERY_CFG.exists(), "被拒了却还是把配置写下去了")


class SetupPanelFrontendTests(unittest.TestCase):
    """开屏页 / 目录选择器 / 删除按钮的前端形状（纯字符串哨兵 —— 没有浏览器时的硬约束）。"""

    def test_the_landing_page_exists_and_the_title_toggles_it(self):
        h = _html()
        for token in ('id="splash"', 'id="splash_inner"', 'id="splash_brand"',
                      'id="brand"', 'class="hero-title"'):
            self.assertIn(token, h, f"开屏页缺少 {token}")
        self.assertIn("$('brand').onclick", h, "主界面标题没接点击（回不去展示页）")
        self.assertIn("$('splash_brand').onclick", h, "展示页标题没接点击（回不去主界面）")

    def test_the_delivery_panel_uses_a_template_selector_and_time_only_archive_names(self):
        """产物面板：模板下拉替代题目标识；归档名留空 = 时间。"""
        h = _html()
        self.assertIn('id="dv_template"', h)
        self.assertIn('id="template_btn"', h, "缺少「选择比赛/输出模板」触发按钮")
        self.assertIn('id="template_pop"', h, "缺少模板下拉浮层")
        self.assertNotIn('id="dv_pid"', h, "题目标识框已删，不应再长回来")
        self.assertIn("选择比赛/输出模板", h)
        self.assertIn("_tplBtn.onclick", h, "模板框没接触发浮层")
        self.assertIn("tpl-row", h, "模板浮层没有行样式/结构")
        self.assertIn("归档名（可留空", h)
        self.assertIn("body:JSON.stringify({output_dir:$('dv_dir').value, name})", h)
        self.assertIn("$('delivbtn').title=title", h)
        self.assertIn("下一个归档名", h)

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

    def test_the_upload_panel_folds_away_after_the_intake_confirm(self):
        """⓪ 读完题、人确认过之后，「上传赛题」那块要**自动收起**（用户 2026-10-15 要求）。

        收起走的是与 `#up_close` 同一条路（`display='none'`）—— **只是收起不是清空**，
        点「⬆ 上传赛题」随时能再展开（换题时还要用）。
        对照组：`confirm` 以外的动作**不许**碰它（点「再试一次」时用户很可能要重新选文件夹）。
        """
        h = _html()
        seg = h[h.index("if(r.ok){", h.index("async function decide(")):]
        seg = seg[:seg.index("}catch")]
        self.assertIn("action==='confirm'", seg, "没把'收起面板'限定在 ⓪ 确认那一下")
        self.assertIn("uppanel", seg, "确认之后没把上传面板收起来")
        self.assertIn("dvPanel(false)", seg, "确认之后没把「产物」面板一起收起来（两块是一起展开的）")

    def test_the_two_setup_panels_open_and_close_together(self):
        """「上传赛题」与「产物」是**一对**：点上传时两块一起展开、各自有 ✕、⓪ 确认后一起收。

        （用户 2026-10-15 的要求：换题时这两件事总是连着做，分两次点等于把一件活拆成两步；
        收的时候只收一半也会留一块空占着版面。）
        走的都是同一个出口 `dvPanel()` —— 三处各写一遍 `display=…` 迟早有一处忘了同步刷新。
        """
        h = _html()
        self.assertIn('id="dv_close"', h, "「产物」面板右上角没有 ✕")
        self.assertIn("$('dv_close').onclick", h, "那个 ✕ 没接事件")
        seg = h[h.index("$('upbtn').onclick"):]
        seg = seg[:seg.index("\n", seg.index("$('upbtn').onclick"))]
        self.assertIn("dvPanel(true)", seg, "点「上传赛题」时没把「产物」一起展开")
        # 出口只能有一个：`toggleDelivery` 与 ✕ 都必须走 `dvPanel`
        self.assertIn("function dvPanel(", h, "没有统一出口")
        self.assertIn("dvPanel(p.style.display==='none'", h, "开关没走统一出口")

    def test_the_start_button_warns_when_no_model_config_is_found(self):
        """点 ▶ 之前必须查一次模型配置：三键不齐就弹确认框，而不是闷头起链。

        为什么要它：2026-10-15 的现场是"`.env` 里有端点、没密钥"（跑的其实是环境里那把），
        而点 ▶ 时**一道校验都没有** —— 用户会等半小时才发现某个阶段在报"密钥无效"。
        **只提示、不硬拦**：机器上的 Claude Code 自己已登录是合法路径，那种情况下三键本来就是空的。
        """
        h = _html()
        seg = h[h.index("$('start').onclick"):]
        seg = seg[:seg.index("\n};")]
        self.assertIn("/api/model_config", seg, "起链前没查模型配置")
        self.assertIn("configured", seg, "没判'配没配'")
        self.assertIn("confirm(", seg, "没弹确认框")
        self.assertIn("splShow('config')", seg, "没给'回开屏页去配'的出口")

    def test_the_wipe_button_needs_both_a_confirm_and_the_word(self):
        """删除是**不可逆**的，所以它必须过两道：`confirm` 弹窗 + 手输暗号。"""
        h = _html()
        self.assertIn('id="dv_wipe"', h)
        seg = h[h.index("$('dv_wipe').onclick"):]
        seg = seg[:seg.index("\n};")]
        self.assertIn("confirm(", seg, "删除没有确认弹窗")
        self.assertIn("prompt(", seg, "删除没有要求手输暗号")

    def test_the_wipe_all_button_needs_both_a_confirm_and_its_own_word(self):
        """「删除全部内容」连题面一起删 ⇒ 同样两道闸，且**暗号不是另一个按钮那个**。

        暗号共用一个词的话，"想删产物、手一滑点成删除全部"就没人拦 —— 代价从
        "重跑一遍"变成"题面没了"。所以这里连 `NotIn` 一起钉。
        """
        h = _html()
        self.assertIn('id="dv_wipe_all"', h)
        seg = h[h.index("$('dv_wipe_all').onclick"):]
        seg = seg[:seg.index("\n};")]
        self.assertIn("confirm(", seg, "删除全部没有确认弹窗")
        self.assertIn("prompt(", seg, "删除全部没有要求手输暗号")
        self.assertIn("/api/wipe-all", seg, "面板没打 /api/wipe-all")
        self.assertIn("删除全部", seg, "暗号文案不是「删除全部」")
        self.assertIn("d.failed", seg, "删不掉的项没显示在面板上")
        self.assertNotIn("删除本题", seg, "两个按钮共用了同一个暗号 —— 手滑点错就拦不住了")

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


class RecoveredRepairHintTests(unittest.TestCase):
    """重启后把"这一阶段还欠一次返修"从**盘上**认回来（`_recovered_repair_hint`）。

    事故背景（2026-10-15）：⑤ 判 NEEDS_FIX(6 条) → 托管自动回退 ④编码计算 → ④ 跑到一半
    **驱动被阶段 agent 误杀**。返修提示是内存态 ⇒ 重启后 ④ 会被当成普通重跑：照样跑、
    照样被 ⑤ 重判，但不知道上一轮被点名的 6 条是什么 ⇒ 白烧一轮。

    三条硬边界各配一条对照（只认门禁 / 只在该阶段没交付时生效 / 只取最新），
    外加一条**防泄漏**的硬断言：认回过程一个字节都不许往 `reports/` 写。
    """

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for rel in ("CLAUDE.md", "AGENTS.md"):
            shutil.copy2(PROJECT / rel, self.root / rel)
        for rel in ("skills", "docs"):
            shutil.copytree(PROJECT / rel, self.root / rel)
        self.s = load_server(self.root)

    def _feedback(self, judge, target, uid="aaa111", mtime=None):
        """造一份门禁回执（`gate_decision.json`）**与它的路由档**，照 `_save_feedback` 的落法。

        路由档刻意**不在** `feedback/` 里 —— 那个目录被 `receipt_ledger` 无差别 glob 着，
        多放一个 `.json` 就会让②建模设计的台账自检误判"receipt 指错了"（见 `_save_feedback` 的注释）。
        """
        folder = self.s.LOG_DIR / "quality" / "feedback" / "run1" / uid
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "gate_decision.json").write_text(json.dumps(
            {"schema_version": 2, "stage": judge, "status": "NEEDS_FIX",
             "issues": [{"id": "R1", "fix": "把 §3 的系数重算"}]}, ensure_ascii=False), encoding="utf-8")
        route = self.s.LOG_DIR / "quality" / "routes" / "run1" / (uid + ".json")
        route.parent.mkdir(parents=True, exist_ok=True)
        route.write_text(json.dumps(
            {"judge": judge, "target": target, "run_id": "run1",
             "at": "2026-10-15T19:02:52"}, ensure_ascii=False), encoding="utf-8")
        if mtime:
            os.utime(route, (mtime, mtime))
        return folder, route

    def test_the_route_file_stays_out_of_the_feedback_glob(self):
        """**防误伤**：路由档不许落在 `feedback/` 里 —— 那个目录被返修台账无差别 glob 着，
        多一个 `.json` 就会让②建模设计的台账自检判「receipt 指错了」并当场硬挂。"""
        self._feedback("audit", "code")
        stray = sorted(p.name for p in (self.s.LOG_DIR / "quality" / "feedback").rglob("*.json"))
        self.assertEqual(stray, ["gate_decision.json"],
                         f"feedback/ 里多出了 json（{stray}）—— 台账会把最新的那个当成回执")

    def _stage(self, sid):
        return next(x for x in self.s.STAGES if x["id"] == sid)

    def _deliver(self, sid):
        """让该阶段**真的交付过一次**：造产物 + 走真写点记回执（digest 由驱动自己算，不手搓）。"""
        st = self._stage(sid)
        if sid == "code":
            (self.root / "code").mkdir(exist_ok=True)
            (self.root / "code/q1.py").write_text("print(1)\n", encoding="utf-8")
            (self.root / "reports").mkdir(exist_ok=True)
            (self.root / "reports/RESULTS_REPORT.md").write_text("结论：PASS\n" + "证据 " * 60, encoding="utf-8")
        self.s._save_receipt(st)

    def test_it_recovers_the_unsettled_receipt_from_disk(self):
        folder, _route = self._feedback("audit", "code")
        hint = self.s._recovered_repair_hint("code")
        self.assertTrue(hint, "盘上那份未结清的回执没被认回来")
        self.assertIn(str(folder.relative_to(self.root)).replace("\\", "/"), hint.replace("\\", "/"),
                      "提示里没给出回执目录 —— 阶段 agent 找不到那份清单")
        self.assertIn("返修", hint)

    def test_it_never_writes_into_reports(self):
        """**防泄漏**：认回过程只读 `runtime/quality/feedback/`，一个字节都不许往 `reports/` 写。

        往 `reports/` 放交回单正是"交回单泄漏到下游"那类坑的入口 —— 一个留在盘上的
        `HANDBACK_REQUEST.md` 会被下游阶段读到、误认成"给我的返修单"。
        """
        self._feedback("audit", "code")
        before = sorted(p.relative_to(self.root).as_posix() for p in (self.root / "reports").rglob("*")) \
            if (self.root / "reports").is_dir() else []
        self.s._recovered_repair_hint("code")
        after = sorted(p.relative_to(self.root).as_posix() for p in (self.root / "reports").rglob("*")) \
            if (self.root / "reports").is_dir() else []
        self.assertEqual(after, before, "认回回执时往 reports/ 写了东西 —— 那正是泄漏的入口")

    def test_a_non_gate_judge_is_ignored(self):
        """边界①：**只认门禁的裁决**。非门禁的"裁决"是空壳，不构成返修要求。"""
        self._feedback("drawio", "code")          # ⑦技术路线图：gate=None
        self.assertIsNone(self.s._recovered_repair_hint("code"),
                          "拿非门禁的裁决当返修单了")

    def test_an_already_delivered_stage_is_not_pressed_again(self):
        """边界②之一：这一阶段**已经交付过**（手上有回执）⇒ 不许再拿旧回执压它。

        这条同时就是"消费标记"：交付了就不再提示，不需要额外状态。
        """
        self._feedback("audit", "code")
        self._deliver("code")
        self.assertTrue(self.s._receipt_store().records.get("code"), "夹具没造成'有回执'")
        self.assertIsNone(self.s._recovered_repair_hint("code"),
                          "已经交付过还被旧回执压着 ⇒ 会凭空多烧一轮返修")

    def test_a_stage_whose_downstream_took_over_is_not_pressed_again(self):
        """边界②之二（**这条是复核抓出来的**）：回执与盘面**对不上**、但**回复存在**时，也不认回。

        判据必须是"**根本没有回执**"，不是"回执对不上"—— 因为 `run_stage` 那五条复用近路
        （豁免/回执复用/stale-instr/taken-over/读题）的**共同前置都是 `not round_hint`**：
        我这条兜底一给出非空提示，它们**全部失效**。最要命的是 taken-over ——
        ⑨论文撰写 被 ⑭排版 改过 `paper/` 之后，它的回执 `outputs` 半份**必然**失配
        （这正是 taken-over 存在的理由），按"对不上"判它欠返修就会把整篇论文重新拉起来跑。
        """
        self._feedback("audit", "code")
        self._deliver("code")
        # 让下游改掉产物：回执还在，但与盘面对不上了
        (self.root / "code/q1.py").write_text("print(2)\n", encoding="utf-8")
        self.assertEqual((self.root / "code/q1.py").read_text(encoding="utf-8"), "print(2)\n",
                         "夹具没把盘面改掉（'回执与盘面对不上'是这条的前提）")
        self.assertTrue(self.s._receipt_store().records.get("code"), "夹具把回执弄丢了")
        self.assertIsNone(self.s._recovered_repair_hint("code"),
                          "回执对不上（下游接管/输入变了）也被当成欠返修 ⇒ 会推翻下游的成果")

    def test_the_panel_gets_the_judgements_back_after_a_restart(self):
        """重启后**面板上那个 📝 角标与判词**要从盘上恢复 —— 它原本是内存态，重启即清零。

        与提示词共用 `_unsettled_feedback` 同一份判据：各写一套迟早自相矛盾
        （"提示词说欠返修、面板说干净"），而人**只看得到面板那一半**。
        模拟重启的手法照本仓既有做法：在**同一个 root** 上重新 exec 一遍 server.py。
        """
        self._feedback("audit", "code")
        again = load_server(self.root)              # = 重启（state 全新，模块级反推会跑一遍）
        issues = (again.state.get("issues_by_stage") or {}).get("code") or []
        self.assertTrue(issues, "重启后面板上的判据没了 —— 人看到的是一排干净的阶段")
        self.assertIn("把 §3 的系数重算", json.dumps(issues, ensure_ascii=False))

    def test_the_panel_is_not_scared_by_a_settled_receipt(self):
        """两条对照：非门禁的判官不显示、**已经交付过**的不显示。

        少了它们，一个"只要盘上有回执就往面板上挂 📝"的实现照样能让正题绿 ——
        而那种实现会让人天天看见一排并不存在的待办。
        """
        self._feedback("drawio", "code")            # ⑦ 不是门禁
        again = load_server(self.root)
        self.assertFalse((again.state.get("issues_by_stage") or {}).get("code"),
                         "非门禁的裁决被当成待办了")
        self._deliver("code")                       # 交付过 ⇒ 不该再挂着
        again2 = load_server(self.root)
        self.assertFalse((again2.state.get("issues_by_stage") or {}).get("code"),
                         "已经交付过的阶段还挂着旧判据")

    def test_a_human_decision_beats_a_stale_receipt(self):
        """人工放过它的（「接受并披露」/ attest）⇒ 旧回执**不许**再把它拖去返修。

        这是"边界②"的例外，而且是**必须显式写**的一条：非空的 round_hint 恰好会关掉
        `run_stage` 里的豁免近路（`if _wrec and not round_hint and …`）⇒ 少了这一条，
        人明明点过「接受并披露」，一次重启之后又会被旧回执拉去重跑一整轮。
        两条对照：不豁免 → 借（正题）；豁免输入一变自动失效 → 又该借（`_waived` 自己的判据）。
        """
        self._feedback("audit", "code")
        self.assertIsNotNone(self.s._recovered_repair_hint("code"), "前提：不豁免时应当借")
        # 披露：照 `/api/decision` 那条路**原样**写（`_load_waivers` → 改 → `_save_waivers`）
        w = self.s._load_waivers()
        w["code"] = {"digest": self.s._input_digest(self._stage("code")),
                     "at": "2026-10-15T20:00:00", "note": "接受并披露"}
        self.s._save_waivers(w)
        self.assertIsNone(self.s._recovered_repair_hint("code"),
                          "人已经「接受并披露」过，旧回执又把它拖去返修了")

    def test_an_attested_stage_is_not_pressed_again(self):
        """人工认证（attest）过的阶段也不被旧回执扣住 —— 靠的是**它一定带回执**这条不变量。

        认证把 `manual` 标记写在**回执**里（`StageReceipts.save(..., manual=True)`），
        所以它天然落进"有回执 ⇒ 不认回"那条边界，不需要单独判 `is_manual`
        （那会是一条永远走不到的死代码）。这条用例守的是那个不变量本身：
        哪天 attest 改成不写回执，它会先红。
        """
        self._feedback("audit", "code")
        self.s._receipt_store().save("code", "art", "out", "run1", manual=True)
        self.assertTrue(self.s._receipt_store().is_manual("code"), "attest 没在回执里留 manual 标记")
        self.assertIsNone(self.s._recovered_repair_hint("code"),
                          "attest 过的阶段又被旧回执扣住了")

    def test_a_route_whose_receipt_is_gone_is_not_borrowed(self):
        """路由档与回执分居两处 ⇒ 必须确认**回执还在**。

        换题轮转会把 `feedback/` 整份搬进 cache，而 `routes/` 不跟着走 —— 不查这一条，
        就会拿一份"回执已经不在盘上"的路由，让 agent 去读一个不存在的目录。
        """
        folder, _route = self._feedback("audit", "code")
        self.assertIsNotNone(self.s._recovered_repair_hint("code"), "前提：回执在时应当借")
        shutil.rmtree(folder)                       # 模拟被轮转搬走 / 被清理删掉
        self.assertIsNone(self.s._recovered_repair_hint("code"),
                          "回执已经不在了，还拿这份路由去让 agent 读空气")

    def test_a_receipt_for_another_target_is_not_borrowed(self):
        """边界③'借错人'：这份回执要的是别人返修，别扣到这个阶段头上。"""
        self._feedback("audit", "write")
        self.assertIsNone(self.s._recovered_repair_hint("code"))

    def test_the_newest_receipt_wins(self):
        """同一个目标有多份未结清回执 ⇒ 取**最新**那份（旧的不许反复应用）。"""
        _f1, old = self._feedback("audit", "code", uid="old000")
        _f2, new = self._feedback("audit", "code", uid="new000")
        os.utime(old, (1_700_000_000, 1_700_000_000))
        os.utime(new, (1_800_000_000, 1_800_000_000))
        hint = self.s._recovered_repair_hint("code")
        self.assertIn("new000", hint.replace("\\", "/"), "取的不是最新那份")
        self.assertNotIn("old000", hint.replace("\\", "/"))


class VerdictArchiveTests(unittest.TestCase):
    """门禁判词留档：**过没过都留**，📝 里随时看得到"这一关最终判了什么"。

    用户 2026-10-16 的原话：「把所有的门禁环节，每次过了后，即使过了，前端 📝 也显示最终的判词」
    —— 参考的正是 ⑤⑫ 那种"跑完了还看得到"的形态。
    与 `issues_by_stage` 的口径**故意不同**（那个过了就撤，防"以为还没修"），所以存储、
    落盘、清理三件事都必须分开做对 —— 下面每条各配一个对照组。
    """

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for rel in ("CLAUDE.md", "AGENTS.md"):
            shutil.copy2(PROJECT / rel, self.root / rel)
        for rel in ("skills", "docs"):
            shutil.copytree(PROJECT / rel, self.root / rel)
        self.s = load_server(self.root)

    def test_a_passed_verdict_is_kept_and_persisted(self):
        """通过也留：内存里有、盘上也有（不落盘 ⇒ 重启就没了，那条另行验证）。"""
        self.s._note_verdict("rubric", {"status": "PASS", "reason": "", "issues": [],
                                        "passed": True, "at": "2026-10-16 10:00"})
        entry = self.s.state["verdict_by_stage"]["rubric"]
        self.assertTrue(entry["passed"])
        f = self.root / "runtime/quality/verdict_by_stage.json"
        self.assertTrue(f.is_file(), "判词留档没落盘 —— 重启后面板就没了")
        self.assertEqual(json.loads(f.read_text(encoding="utf-8"))["rubric"]["status"], "PASS")
        # 对照组：**未通过**的也记（"过没过都留"的另一半，别只测通过那条）
        self.s._note_verdict("audit", {"status": "NEEDS_FIX", "reason": "r",
                                       "issues": [{"id": "a1", "severity": "hard"}],
                                       "passed": False, "at": "2026-10-16 10:05"})
        self.assertFalse(self.s.state["verdict_by_stage"]["audit"]["passed"])

    def test_a_restart_reads_the_archive_back(self):
        """重启存活：重新 exec 一遍 server.py（与其它"重启存活"类测试同一手法），
        模块级 `_restore_verdicts_by_stage()` 要把盘上那份读回来。"""
        self.s._note_verdict("verify", {"status": "PASS", "reason": "", "issues": [],
                                        "passed": True, "at": "2026-10-16 11:00"})
        s2 = load_server(self.root)                       # 模拟驱动重启（同一工作区）
        self.assertIn("verify", s2.state["verdict_by_stage"],
                      "重启后判词留档没了 —— 📝 里的最终判词不该因为重启消失")
        self.assertEqual(s2.state["verdict_by_stage"]["verify"]["status"], "PASS")

    def test_non_gate_stages_never_get_a_verdict(self):
        """⑯ 交互Demo 这类非门禁阶段没有裁决；`not_gate` 只是流程占位。

        旧实现把 `_gate_decision` 对非门禁返回的 `PASS / not_gate` 也记进留档，
        于是 📝 里长出一句"最终判词：已通过"——用户看到的正是这个。
        """
        self.s._note_verdict("demo", {"status": "PASS", "reason": "not_gate", "issues": [],
                                      "passed": True, "at": "2026-10-19 00:07"})
        self.assertNotIn("demo", self.s.state["verdict_by_stage"],
                         "非门禁阶段被写入了判词")
        f = self.root / "runtime/quality/verdict_by_stage.json"
        if f.is_file():
            self.assertNotIn("demo", json.loads(f.read_text(encoding="utf-8")))
        # 对照组：真门禁照常留档
        self.s._note_verdict("figreview", {"status": "PASS", "reason": "", "issues": [],
                                           "passed": True, "at": "2026-10-19 00:07"})
        self.assertIn("figreview", self.s.state["verdict_by_stage"])

    def test_restart_drops_legacy_non_gate_verdicts(self):
        """旧版本写进盘的非门禁判词，重启读回时要被过滤掉。"""
        f = self.root / "runtime/quality/verdict_by_stage.json"
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps({
            "demo": {"status": "PASS", "reason": "not_gate", "passed": True},
            "figreview": {"status": "PASS", "reason": "", "passed": True},
        }), encoding="utf-8")
        s2 = load_server(self.root)
        self.assertNotIn("demo", s2.state["verdict_by_stage"],
                         "重启后旧的非门禁判词又回来了")
        self.assertIn("figreview", s2.state["verdict_by_stage"])
        # 过滤后要顺手清盘，否则下一次重启还会看到
        self.assertNotIn("demo", json.loads(f.read_text(encoding="utf-8")))

    def test_redo_clears_the_archive_from_that_stage_onward(self):
        """被作废的阶段即将重判：旧判词不能继续挂在面板上冒充现任。
        对照组：**上游**那一关的留档必须还在（别把整份留档一起掀了）。"""
        self.s._note_verdict("audit", {"status": "NEEDS_FIX", "issues": [], "passed": False, "at": "t"})
        self.s._note_verdict("rubric", {"status": "PASS", "issues": [], "passed": True, "at": "t"})
        self.s._redo_from("rubric")
        self.assertNotIn("rubric", self.s.state["verdict_by_stage"], "被重跑的阶段还挂着旧判词")
        self.assertIn("audit", self.s.state["verdict_by_stage"], "对照组：上游留档被误删了")
        self.s._redo_from("audit")
        self.assertNotIn("audit", self.s.state["verdict_by_stage"])

    def test_the_api_and_the_panel_carry_it(self):
        """接线（纯字符串 —— 行为由上面三条和前端夹具各管一段，这条防改名/漏接）。"""
        srv = (PROJECT / "lib/web/server.py").read_text(encoding="utf-8-sig")
        for token in ('"verdict_by_stage": {}', "def _note_verdict(", "_note_verdict(stage[\"id\"], {",
                      "def _restore_verdicts_by_stage(", "_restore_verdicts_by_stage()  #",
                      '"verdicts": {k: v for k, v in (state.get("verdict_by_stage")',
                      'state["verdict_by_stage"] = {}'):
            self.assertIn(token, srv, f"server.py 缺 {token!r}")
        h = _html()
        for token in ("st.verdicts?st.verdicts[id]", "这一关的最终判词", "已结清，留档",
                      "advvd", "lastSt.verdicts?lastSt.verdicts[sid]"):
            self.assertIn(token, h, f"index.html 缺 {token!r}")


class DriverPidTests(unittest.TestCase):
    """驱动把自己的 pid 写在盘上（`runtime/driver.pid`）—— 2026-10-15 那起事故的产物。

    那天 ④编码计算的 agent 为了清"残留的 stray python"，`tasklist | grep python` 数出两个
    python.exe，`taskkill /F` 两个一起杀 —— 其中一个**就是驱动本体**（也是个 python.exe）。
    现场：控制台窗口当场消失、日志断在半句、那一轮从 ④ 白跑；`taskkill /F` 不给对方
    写日志的机会，事后只能翻会话转录才查得出是谁干的。

    这份档案管两件事：① 阶段纪律点名"这个 pid 永远不许碰"；② 下一任驱动启动时能说出
    "上一任没有正常退出"，而不是只留一句泛泛的"被外部强杀"。下面每条都配了对照组。
    """

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for rel in ("CLAUDE.md", "AGENTS.md"):
            shutil.copy2(PROJECT / rel, self.root / rel)
        for rel in ("skills", "docs"):
            shutil.copytree(PROJECT / rel, self.root / rel)
        self.s = load_server(self.root)

    def test_it_writes_and_reads_its_own_record(self):
        self.s._write_driver_pid(8901)
        rec = self.s._driver_pid_record()
        self.assertEqual(int(rec["pid"]), os.getpid(), "写的不是当前进程的 pid")
        self.assertEqual(rec["port"], 8901)
        self.assertTrue(rec.get("started_at"), "没记启动时刻 ⇒ 启动横幅说不出'起于何时'")

    def test_a_stale_record_is_how_we_learn_the_previous_driver_died(self):
        """判据的分母：档案还在、而那个 pid 已经不在了 ⇒ 上一任**没正常退出**。

        （`_clear_driver_pid` 只在正常退出时删档案，所以"档案还在"本身就是一个信号。）
        """
        alive = self.s._snapshot_pids()
        free = max(alive) + 1 if alive else 999999
        while free in alive:
            free += 1
        self.s.DRIVER_PID.write_text(
            json.dumps({"pid": free, "port": 8901, "started_at": "2026-10-15T19:00:00"}),
            encoding="utf-8")
        rec = self.s._driver_pid_record()
        self.assertTrue(rec, "陈旧档案读不回来 ⇒ 启动横幅报不出'上一任没正常退出'")
        self.assertFalse(self.s._pid_alive(rec["pid"]), "不存在的 pid 被判成活着")
        # 对照组：活着的 pid 必须判活（`_pid_alive` 恒假的实现同样会让上面那条通过）
        self.assertTrue(self.s._pid_alive(os.getpid()))

    def test_only_its_own_record_is_cleared(self):
        """正常退出只撤**自己**那份档案 —— 别人（例如刚重启的下一任）写的那份不许动。

        没有这条对照，一个无脑 `unlink()` 的实现也能让"自己那份被清掉"通过。
        """
        alive = self.s._snapshot_pids()
        other = max(alive) + 1 if alive else 999999
        while other in alive:
            other += 1
        self.s.DRIVER_PID.write_text(json.dumps({"pid": other}), encoding="utf-8")
        self.s._clear_driver_pid()
        self.assertTrue(self.s.DRIVER_PID.is_file(), "把**别人**的 pid 档案删了")
        self.s._write_driver_pid(8901)
        self.s._clear_driver_pid()
        self.assertFalse(self.s.DRIVER_PID.is_file(), "自己正常退出时没撤档")

    def test_a_closed_console_window_counts_as_a_manual_stop(self):
        """**关窗口**与**被强杀**必须区分得开（用户 2026-10-15 要求）。

        机制：Windows 关窗口会给进程发 `CTRL_CLOSE_EVENT`，而 `taskkill /F` **什么都不发** ——
        所以收到事件就说明是人手动关的 ⇒ 撤掉 pid 档案（当作正常退出）⇒ 下一任启动时
        不必再报那句吓人的话；而**没收到事件**的那一档（档案还在、pid 已死）才真的该被人看见。

        对照组：`CTRL_C`（事件 0）**不许**撤档 —— 那条路走的是 Ctrl+C ⇒ KeyboardInterrupt ⇒
        atexit 撤档，处理器不该抢它的活（抢了的话"Ctrl+C 也算关窗"就没人分得清了）。
        """
        self.s._write_driver_pid(8901)
        self.s.log.reset_mock()
        self.s._console_ctrl(0)                                  # CTRL_C
        self.assertTrue(self.s.DRIVER_PID.is_file(), "把 Ctrl+C 也当成关窗口了")
        self.s._console_ctrl(2)                                  # CTRL_CLOSE_EVENT = 关窗口
        self.assertFalse(self.s.DRIVER_PID.is_file(), "关窗口之后 pid 档案没撤掉")
        self.assertTrue(self.s.log.called, "关窗口没留痕 —— 下一任就分不出它和'被强杀'")

    def test_the_startup_warning_only_fires_for_a_real_kill(self):
        """那句话只在**真被强杀**时才该出现，且要把区分方法说清（否则用户没法判断）。

        源级哨兵：`__main__` 里要装处理器、警告文案里要点出"既不是 Ctrl+C、也不是关窗口"。
        """
        src = (PROJECT / "lib/web/server.py").read_text(encoding="utf-8")
        self.assertIn("SetConsoleCtrlHandler(_console_ctrl", src, "没装控制台事件处理器")
        seg = src[src.index("上一任驱动（pid"):]
        seg = seg[:seg.index("紧接着那条「收掉孤儿」")]
        self.assertIn("关窗口", seg, "文案没说清'关窗口'这条已被排除")
        self.assertIn("taskkill", seg, "文案没点出最可能的真凶")

    def test_a_broken_or_missing_record_never_breaks_startup(self):
        """档案只是线索，坏掉/缺失都不许把启动带崩（与 `_restore_stale_instr` 同一条纪律）。"""
        self.assertIsNone(self.s._driver_pid_record(), "文件不存在时应当返回 None")
        for bad in ("{不是 json", "[]", "{}", '{"pid": null}'):
            self.s.DRIVER_PID.write_text(bad, encoding="utf-8")
            self.assertIsNone(self.s._driver_pid_record(), f"坏档案没被挡住：{bad!r}")

    def test_the_next_driver_can_see_the_pid_without_reading_a_file(self):
        """驱动 pid 必须**直接写在阶段提示里**，不能只躺在一个 agent 得自己去翻的文件里。

        2026-10-15 之后补的一条：`driver.pid` 是可写文件，agent 删掉/改掉它就等于把保护关掉；
        而提示是**驱动亲口喂进上下文**的，改不掉。顺带也让"我到底该跳过哪个 pid"从"去读个文件"
        变成"眼前就有"。
        """
        stage = next(s for s in self.s.STAGES if s["id"] == "code")
        text = self.s.prompt_for(stage, first=True)
        self.assertIn(str(os.getpid()), text, "阶段提示里没有驱动 pid")
        self.assertIn("driver.pid", text, "没告诉 agent 那份档案在哪")
        self.assertIn("TaskStop", text, "没给正确做法")
        # 断言**口径**而不是某个固定措辞 —— 写死一句话，改一次措辞它就假红一次
        #   （2026-10-15 就这么红过一次：'任何情况下都不许杀进程' 改成
        #   '永不许按进程名杀进程' 之后，仍断言前者）。
        self.assertIn("按进程名", text, "没写清'永不许按进程名杀'")

    def test_the_reaper_skips_agents_owned_by_a_still_living_driver(self):
        """登记表**跨实例共享** ⇒ 收容前必须先看"spawn 它的那个驱动还在不在"。

        没有这一条时：手动再起一个驱动（`--port 8902`）就会把第一个实例正在跑的阶段 agent
        当成孤儿杀掉 —— 与"自己人杀自己人"是同一族事故。
        对照组：owner 已经死了 ⇒ 照收（不然这条就变成"永远不收"了）。
        """
        # "另一个还活着的驱动"就用本测试进程的父进程 —— 它一定活着、且不是我自己（不另起进程，
        #   免得为一条用例引入 subprocess）。
        owner = os.getppid()
        self.assertTrue(self.s._pid_alive(owner), "前提不成立：父进程应当活着")
        self.s._register_stage_pid(4242)
        path = self.s.STAGE_PIDS
        data = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(data[0].get("driver"), os.getpid(), "登记时没记下是哪个驱动 spawn 的")
        data[0]["driver"] = owner                         # 假装是"另一个还活着的驱动"起的
        path.write_text(json.dumps(data), encoding="utf-8")
        self.s._claude_processes = lambda: [(4242, str(self.root))]
        killed = []
        self.s._reap_orphan_agents(kill=lambda pid: killed.append(pid))
        self.assertEqual(killed, [], "把另一个活着的驱动正在用的阶段 agent 当孤儿杀了")

        # 对照组：owner 不在了 ⇒ 该收就得收
        data[0]["driver"] = 999999
        path.write_text(json.dumps(data), encoding="utf-8")
        killed = []
        self.s._reap_orphan_agents(kill=lambda pid: killed.append(pid))
        self.assertEqual(killed, [4242], "owner 已死却不收 —— 那孤儿就永远没人管了")

    def test_an_old_style_registry_entry_is_still_reaped(self):
        """兼容：老格式（纯 int，不知道谁 spawn 的）按孤儿处理，不许因为读不出字段就放弃收容。"""
        self.s.STAGE_PIDS.parent.mkdir(parents=True, exist_ok=True)
        self.s.STAGE_PIDS.write_text(json.dumps([4243]), encoding="utf-8")
        self.s._claude_processes = lambda: [(4243, str(self.root))]
        killed = []
        self.s._reap_orphan_agents(kill=lambda pid: killed.append(pid))
        self.assertEqual(killed, [4243])

    def test_the_rule_is_written_where_the_agents_will_read_it(self):
        """硬红线必须落在**阶段 agent 真会读到的**那几份文件里，且点名 driver.pid。

        只写一句"不要杀进程"不够 —— 触发那次事故的推断是"python 只可能是我自己的"，
        所以规矩里必须出现「驱动本身就是个 python.exe」与 `runtime/driver.pid`。
        """
        for rel in ("CLAUDE.md", "AGENTS.md", "skills/_references/stage_discipline.md"):
            text = (PROJECT / rel).read_text(encoding="utf-8")
            self.assertIn("绝不许杀进程", text, f"{rel} 里没有这条硬红线")
            self.assertIn("taskkill", text, f"{rel} 没点名具体的命令")
            self.assertIn("driver.pid", text, f"{rel} 没说'驱动的 pid 在哪、不许碰'")
            self.assertIn("TaskStop", text, f"{rel} 没给正确做法（停自己后台任务用 TaskStop）")


if __name__ == "__main__":
    unittest.main()
