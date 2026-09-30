# -*- coding: utf-8 -*-
"""改「阶段链账本」不该把每个阶段标成 `done(stale-instr)`。

阶段链的编号一变，面板上 ① 文献定向、② 建模设计、④ 编码计算… 全会被标成「按旧要求交付」，
而它们跟"阶段数变了"毫无关系。两个来源：

1. **`prompt_for` 里写死了阶段数** —— 而那正是 `_prompt_fingerprint()` 哈希的东西：
   `_code_fingerprint(prompt_for.__code__)`。改一个数字 = 每个阶段的注入指令都变。
2. **`CLAUDE.md` / `AGENTS.md` 被整文件哈希**（`_input_split` 的 `ins` 列表），
   而阶段链的编号表就写在这两个文件里 —— 加一行表 = 每个阶段都变。

所以账本住在 `docs/STAGE_CHAIN.md`（**不在** `ins` 里），注入 prompt 里不带数字：
**改链不再产生任何 stale 标记**，而真改 SKILL/规范照旧触发（下面对照组钉住这一点）。
"""
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))
sys.path.insert(0, str(PROJECT / "regression"))
from test_workflow import load_server  # noqa: E402

LEDGER = "docs/STAGE_CHAIN.md"


class StaleNoiseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for rel in ("CLAUDE.md", "AGENTS.md"):
            shutil.copy2(PROJECT / rel, self.root / rel)
        for rel in ("skills", "docs"):
            shutil.copytree(PROJECT / rel, self.root / rel)
        self.s = load_server(self.root)

    def _ins(self, sid):
        """该阶段的「做法要求」指纹。"""
        stage = next(x for x in self.s.STAGES if x["id"] == sid)
        return self.s._input_split(stage)[1]

    # ---- 三条性质 ----

    def test_the_injected_prompt_carries_no_stage_count(self):
        """prompt 里不许出现「N 阶段」—— 它是 `prompt_for.__code__` 的一部分。"""
        import re
        src = (PROJECT / "lib/web/server.py").read_text(encoding="utf-8")
        base = src.split("def prompt_for(stage, first):", 1)[1].split('if sid == "write"', 1)[0]
        self.assertIsNone(re.search(r"\d+\s*阶段", base),
                          "注入 prompt 里又写死阶段数了 —— 加/删一个阶段会把每个阶段标成 stale")

    def test_the_workspace_docs_hold_no_stage_table(self):
        """CLAUDE.md / AGENTS.md 被整文件哈希，编号表不许住在这里。"""
        for rel in ("CLAUDE.md", "AGENTS.md"):
            t = (PROJECT / rel).read_text(encoding="utf-8")
            self.assertNotIn("| # | Skill | 作用 | 产出 |", t,
                             f"{rel} 里又出现了阶段链编号表 —— 它会进每个阶段的指纹")
            self.assertIsNone(__import__("re").search(r"\d+\s*个阶段", t),
                              f"{rel} 里又写死了阶段数")
            self.assertIn(LEDGER, t, f"{rel} 该指向账本 {LEDGER}")

    def test_the_ledger_exists_and_is_not_fingerprinted(self):
        p = PROJECT / LEDGER
        self.assertTrue(p.is_file(), f"缺账本 {LEDGER}")
        t = p.read_text(encoding="utf-8")
        self.assertIn("| # | Skill | 作用 | 产出 |", t, "账本里该有编号表")
        # 账本改了 → 指纹不动
        before = self._ins("analysis")
        p2 = self.root / LEDGER
        p2.write_text(t + "\n<!-- 记账而已 -->\n", encoding="utf-8")
        self.assertEqual(self._ins("analysis"), before, "改了账本，指纹不该动")

    # ---- 正题 + 对照组（防这条测试变成恒真） ----

    def test_adding_a_stage_changes_no_instruction_digest(self):
        """加一个阶段（含插在中间）→ 任何阶段的「做法要求」指纹都不许变。"""
        import copy
        targets = ["literature", "review", "code", "drawio", "figreview", "write", "demo"]
        before = {t: self._ins(t) for t in targets}
        for where in ("end", "middle"):
            with self.subTest(insert_at=where):
                stages = copy.deepcopy(self.s.STAGES)
                dummy = {"id": "_probe", "name": "探针", "skill": "8Figure-gate",
                         "report": "PROBE.md", "gate": None}
                if where == "end":
                    stages.append(dummy)
                else:
                    i = next(k for k, x in enumerate(stages) if x["id"] == "drawio")
                    stages.insert(i + 1, dummy)
                self.s.STAGES = stages
                for t in targets:
                    self.assertEqual(self._ins(t), before[t],
                                     f"插到 {where} 之后，{t} 的指令指纹变了 —— 又回到"
                                     f"「加阶段=全阶段 stale」了")

    def test_changing_the_skill_still_changes_the_digest(self):
        """对照组：真改「做法要求」必须照旧触发 —— 否则上面的断言可能只是恒真。"""
        before = self._ins("analysis")
        p = self.root / "skills/2Modeling-design/SKILL.md"
        p.write_text(p.read_text(encoding="utf-8") + "\n<!-- 真的改了规范 -->\n",
                     encoding="utf-8")
        self.assertNotEqual(self._ins("analysis"), before,
                            "改了阶段的 SKILL 却不触发失效 —— 那 stale 机制就废了")

    def test_changing_claude_md_still_changes_the_digest(self):
        """CLAUDE.md 里**操作性**的内容仍必须进指纹（只有账本被挪走，不是整份排除）。"""
        before = self._ins("analysis")
        p = self.root / "CLAUDE.md"
        p.write_text(p.read_text(encoding="utf-8") + "\n- 新规矩：论文数值必须来自 reports。\n",
                     encoding="utf-8")
        self.assertNotEqual(self._ins("analysis"), before)


class GateMidRunInstructionEditTests(unittest.TestCase):
    """门禁执行期间改「做法要求」不许判死。

    `run_stage` 收尾那道"输入在执行期间被改动"的闸门，门禁那一路若比的是
    `_input_digest(stage)` —— **整份**（事实 + 做法要求），那么改一句 `CLAUDE.md`
    或改一个 SKILL，就会把一个六分钟前开始的评审当场打成 `unverified` 硬挂，
    而它审的报告一个字都没动。这与 `_input_split` 的整套设计自相矛盾
    （那里明写"改了做法要求 → 只标 stale，不硬挂"）。

    症状：改 `CLAUDE.md`/`AGENTS.md` 时，正在跑的 ③ 建模评审门禁跟着挂了，
    提示还写着"常因：往 request//data 放文件、或门禁改了被审论文"—— 两件都没发生。
    """

    def test_the_gate_tamper_check_compares_only_the_artifacts_half(self):
        """源码级钉子：门禁那一路必须比 `_input_split(...)[0]`，不许比整份 digest。"""
        src = (PROJECT / "lib/web/server.py").read_text(encoding="utf-8")
        i = src.index("审核/执行期间输入发生变更")
        block = src[max(0, i - 700):i]
        self.assertIn("_input_split(stage)[0]", block,
                      "门禁的执行期输入校验又比回整份 digest 了 —— 改文档会硬挂正在跑的门禁")
        self.assertNotIn("_input_digest(stage) != inputs", block,
                         "又拿整份 digest 判门禁了")

    def test_editing_instructions_mid_stage_would_not_trip_the_gate_check(self):
        """行为级：改做法要求后，artifacts 半份不变 → 不该触发那道闸门。"""
        import shutil as _sh
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            for rel in ("CLAUDE.md", "AGENTS.md"):
                _sh.copy2(PROJECT / rel, root / rel)
            for rel in ("skills", "docs"):
                _sh.copytree(PROJECT / rel, root / rel)
            s = load_server(root)
            stage = next(x for x in s.STAGES if x["id"] == "review")
            art_before = s._input_split(stage)[0]
            full_before = s._input_split(stage)[1]
            p = root / "CLAUDE.md"
            p.write_text(p.read_text(encoding="utf-8") + "\n- 一句新要求\n", encoding="utf-8")
            self.assertEqual(s._input_split(stage)[0], art_before,
                             "改做法要求不该动 artifacts 半份")
            self.assertNotEqual(s._input_split(stage)[1], full_before,
                                "做法要求那半份本来就该变（只是不该判死门禁）")


class FigureScriptIsNotFingerprintedTests(unittest.TestCase):
    """画图脚本必须住在 `figures/` —— 改它**不许**触发 ⑤ 审计 / ⑥ 稳健性 重跑。

    症状：`code/make_figures.py` 改一行画图代码，⑤ 结果可信度审计与 ⑥ 稳健性
    （约 23 分钟）就各重跑一遍，而**数值一个字都没变**。

    根因：`lib/web/server.py:_input_split` 把「上游有 code 阶段」的阶段的输入算作
    `art += ["code", "results"]` —— **整个 `code/` 目录**都在指纹里。而 `figures/`
    是**故意不进任何指纹**的（见 ARTIFACTS 的注释：「含了它会让 drawio 重画就判定
    robustness 的输出变了，害得小时级的稳健性白跑一遍」）。
    画图脚本住在 `code/` 里，就把那道保护绕过去了。

    正确做法不是"在指纹里按文件名排除"（脆弱、换个名字就失效），而是**让文件住在该住的目录**：
    数据图脚本 → `figures/make_figures.py`，与非数据图脚本 `figures/make_flow_figures.py` 一致。
    """

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for rel in ("CLAUDE.md", "AGENTS.md"):
            shutil.copy2(PROJECT / rel, self.root / rel)
        for rel in ("skills", "docs", "figures", "code"):
            if (PROJECT / rel).is_dir():
                shutil.copytree(PROJECT / rel, self.root / rel)
        self.s = load_server(self.root)

    def _art(self, sid):
        """该阶段「产物所依据的事实」那半份指纹。"""
        stage = next(x for x in self.s.STAGES if x["id"] == sid)
        return self.s._input_split(stage)[0]

    def test_the_data_figure_script_lives_under_figures(self):
        # 这条钉的不变量是「它**不许**住在 code/ 下」；而 `figures/make_figures.py` 本身是
        #   **④ 的产物**（SKILL 规定数据图脚本写进 figures/）。所以在**已清空的工作区**里
        #   它本来就不存在 —— 那时只钉前一条，别把「还没跑到 ④」误判成缺陷。
        self.assertFalse((PROJECT / "code/make_figures.py").exists(),
                         "code/ 下还有一份 —— 住在那里就会连锁触发 ⑤⑥ 重跑")
        if not (PROJECT / "figures").is_dir():
            self.skipTest("工作区已清空（还没有 figures/）：④ 跑完才会产出它")
        self.assertTrue((PROJECT / "figures/make_figures.py").is_file(),
                        "数据图脚本不在 figures/ 下 —— 那它就会进 ⑤⑥ 的输入指纹")

    def test_editing_the_figure_script_changes_no_stage_input(self):
        """正题：改一行画图代码，⑤⑥ 的输入指纹必须纹丝不动。"""
        p = self.root / "figures/make_figures.py"
        p.parent.mkdir(parents=True, exist_ok=True)     # 干净工作区里它还不存在
        p.write_text("# 画图脚本\n", encoding="utf-8")
        before = {sid: self._art(sid) for sid in ("audit", "robustness", "drawio")}
        p.write_text(p.read_text(encoding="utf-8") + "\n# 改一行画图代码\n", encoding="utf-8")
        for sid, v in before.items():
            self.assertEqual(self._art(sid), v,
                             f"改了 figures/make_figures.py，{sid} 的输入却变了 —— "
                             f"那 ⑤⑥ 又会白跑一遍（数值根本没变）")

    def test_editing_the_solver_still_changes_it(self):
        """对照组：改**数值**代码必须照旧触发 —— 否则上面的断言可能只是恒真。"""
        p = self.root / "code/core.py"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("# 数值核心\n", encoding="utf-8")
        before = self._art("audit")
        p.write_text(p.read_text(encoding="utf-8") + "\n# 改一处数值\n", encoding="utf-8")
        self.assertNotEqual(self._art("audit"), before,
                            "改了 code/core.py 却不触发失效 —— 那数值过期就没人管了")


class LibraryDependencyTests(unittest.TestCase):
    """库/规范只给**真正依赖它的**阶段 —— 不再是"≥④ 一律打包"。

    症状：改一行画图库 `lib/visualization/*` ⇒ **每个下游阶段一起失效**（含只审数值/口径/
    泄漏的 ⑤）。拆成按阶段的表是对的，代价落在最不该的地方：④⑥ 这类小时级生产阶段有
    stale-instr 宽待保着，被误伤的是**重判要真花时间的门禁**。

    表的**依据必须是会话原始记录**（含 PowerShell 的调用），不能是 `runtime/web_run.log` ——
    那个渲染器**只记七个工具名**（`PowerShell` 一条都不进）⇒ 拿它算"命中 0 次"会**系统性
    漏掉经 PowerShell 的使用**：据此算出的"⑤ 188 次访问 0 命中 `lib/visualization/`"、
    "⑥ 76 次 0 命中"都不成立 —— 按会话原始记录，⑤ 真跑了 5 次
    `& $py -m lib.visualization audit`、⑥ 真跑了 `-m lib.result_contract audit/validate`。
    对账单：`tmp/deps_classify.py`。

    下面五条：三条正向（该响的必须响）、一条**真反向**（不该响的响就是错）、一条防手滑。
    """

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for rel in ("CLAUDE.md", "AGENTS.md"):
            shutil.copy2(PROJECT / rel, self.root / rel)
        for rel in ("skills", "docs"):
            shutil.copytree(PROJECT / rel, self.root / rel)
        for rel in ("lib/visualization", "lib/result_contract", "config"):
            (self.root / rel).mkdir(parents=True, exist_ok=True)
        self.s = load_server(self.root)

    def _ins(self, sid):
        stage = next(x for x in self.s.STAGES if x["id"] == sid)
        return self.s._input_split(stage)[1]

    def _flip(self, rel, body_before, body_after, ids):
        f = self.root / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(body_before, encoding="utf-8")
        before = {i: self._ins(i) for i in ids}
        f.write_text(body_after, encoding="utf-8")
        return before, {i: self._ins(i) for i in ids}

    def test_changing_the_plotting_library_wakes_its_real_users(self):
        """④ 读它 24 次、⑧ 的地板就是图表审计 —— 改了必须响。"""
        before, after = self._flip("lib/visualization/charts.py", "x = 1\n", "x = 2\n",
                                   ("code", "figreview"))
        self.assertNotEqual(before["code"], after["code"], "④ 依赖画图库，改它必须重判")
        self.assertNotEqual(before["figreview"], after["figreview"],
                            "⑧ 的机械地板就是 visualization 的审计，改它必须重判")

    def test_the_audit_and_robustness_gates_do_wake_on_plotting_changes(self):
        """⑤ 与 ⑥ **都会**跑 `python -m lib.visualization audit` —— 改了画图库必须响。

        （别拿 `runtime/web_run.log` 里"0 次命中"当依据：那几次调用全走的 PowerShell，
        日志不记。按会话原始记录：⑤ 5 次、⑥ 1 次。）
        """
        before, after = self._flip("lib/visualization/charts.py", "x = 1\n", "x = 2\n",
                                   ("audit", "robustness"))
        self.assertNotEqual(before["audit"], after["audit"],
                            "⑤ 的复核里就在跑 visualization 的审计（`-m lib.visualization audit`）"
                            "—— 图库变了它的复核结论就可能变，不能装作没看见")
        self.assertNotEqual(before["robustness"], after["robustness"],
                            "⑥ 同样跑 `-m lib.visualization audit`")

    def test_the_gates_do_not_wake_on_a_doc_they_never_read(self):
        """真反向守卫：**别改过头**。`docs/GEOMETRY.md` 是 ⑦/⑧ 的画图几何协议，
        ⑤⑥ 从不读它（完整记录里 ⑤ 那次是"探时间戳"，没有读内容）—— 它变了不该唤醒这两家。
        """
        before, after = self._flip("docs/GEOMETRY.md", "z = 1\n", "z = 2\n",
                                   ("audit", "robustness"))
        self.assertEqual(before["audit"], after["audit"],
                         "⑤ 不读几何图协议，却因为它变了被唤醒 —— 表给宽了")
        self.assertEqual(before["robustness"], after["robustness"],
                         "⑥ 不读几何图协议，却因为它变了被唤醒 —— 表给宽了")

    def test_the_audit_gate_still_follows_the_result_contract(self):
        """反向守卫：**别改过头**。⑤ 真读 `result_contract`（`-m lib.result_contract audit`）——
        摘掉它等于让审计漏掉"结构化结果变了"，比多跑一轮危险得多。

        ⑥ 同理：它跑 `-m lib.result_contract audit` / `validate` 共 4 次，也必须跟着这条走。
        """
        before, after = self._flip("lib/result_contract/core.py", "y = 1\n", "y = 2\n",
                                   ("audit", "robustness"))
        self.assertNotEqual(before["audit"], after["audit"],
                            "⑤ 依赖 result_contract —— 这条不许跟着 blanket 一起被摘掉")
        self.assertNotEqual(before["robustness"], after["robustness"],
                            "⑥ 也在跑 result_contract 的审计/校验，不能漏")

    def test_every_stage_named_in_the_table_exists(self):
        """手滑守卫：表里写错阶段 id（如 `figreviews`）会让那条依赖**静默失效**。"""
        ids = {s["id"] for s in self.s.STAGES}
        for path, users in self.s._LIB_INSTRUCTION_USERS.items():
            unknown = users - ids
            self.assertFalse(unknown, f"{path} 指向了不存在的阶段: {sorted(unknown)}")

    def test_the_conservative_default_covers_stages_without_evidence(self):
        """没有运行证据的阶段（⑬验收/⑭评分标/⑮返修/⑯Demo）保守给全 ——
        给多了只是多跑一轮，给少了会让阶段漏掉真变化。"""
        for sid in ("verify", "rubric", "fix", "demo"):
            self.assertIn(sid, self.s._LIB_INSTRUCTION_USERS["lib/visualization"], sid)


class DerivedResultFingerprintTests(unittest.TestCase):
    """`results/` 下的**派生根验件**两侧都不进指纹。

    症状：在 ⑤ 点"再试一次"会莫名其妙回到 ④ —— ⑤ 的判词**明确要求** "重新 build"结构化
    结果，而它同时写着"**先复用已保存结果，不默认重跑优化器**"；可 `results/registry.json`
    住在 ④ 的输入与产物指纹里 ⇒ 执行那句判词就必然把小时级的 ④ 打回重算，判词自相矛盾。
    更糟：④ 一起跑，它的回执当场失效（不可逆）。

    与 `figures/` 完全同构：负责这些文件的机制是 `python -m lib.result_contract audit`
    （驱动对 ⑤/⑬ 直接跑），不是指纹。**真交付物 `result1–4.xlsx` 照旧进指纹**（下面的对照组）。
    """

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for rel in ("CLAUDE.md", "AGENTS.md"):
            shutil.copy2(PROJECT / rel, self.root / rel)
        for rel in ("skills", "docs"):
            shutil.copytree(PROJECT / rel, self.root / rel)
        for rel in ("results", "code", "reports", "config"):
            (self.root / rel).mkdir(parents=True, exist_ok=True)
        (self.root / "results/registry.json").write_text('{"metrics": {}}\n', encoding="utf-8")
        (self.root / "results/result1.xlsx").write_text("fake-xlsx\n", encoding="utf-8")
        self.s = load_server(self.root)

    def _code(self):
        return next(x for x in self.s.STAGES if x["id"] == "code")

    def _both(self):
        stage = self._code()
        return self.s._input_split(stage)[0], self.s._output_digest(stage)

    def test_rebuilding_the_registry_does_not_wake_the_solver(self):
        """⑤ 判词要求的那句 `result_contract build` 不许把 ④ 打回重算。"""
        art_before, out_before = self._both()
        (self.root / "results/registry.json").write_text('{"metrics": {"q3": 1}}\n',
                                                        encoding="utf-8")
        art_after, out_after = self._both()
        self.assertEqual(art_before, art_after, "重建登记表又把 ④ 的输入指纹改了")
        self.assertEqual(out_before, out_after, "重建登记表又把 ④ 的产物指纹改了")

    def test_a_real_deliverable_still_invalidates_downstream(self):
        """对照组：真交付物变了必须照旧失效 —— 否则上面的断言可能只是把整个 results/ 摘掉了。

        两侧的取法不同：`results/` 是 ④ 的**产物**，所以验它看 `_output_digest` 变；
        而它的**输入**要拿下游（⑬ 验收，输入里才含 `code`+`results`）来验。
        """
        out_before = self.s._output_digest(self._code())
        verify = next(x for x in self.s.STAGES if x["id"] == "verify")
        in_before = self.s._input_split(verify)[0]
        (self.root / "results/result1.xlsx").write_text("changed\n", encoding="utf-8")
        self.assertNotEqual(out_before, self.s._output_digest(self._code()),
                            "交付物变了却没让 ④ 的产物指纹变")
        self.assertNotEqual(in_before, self.s._input_split(verify)[0],
                            "交付物变了却没让下游（⑬）的输入指纹变")

    def test_the_audit_gate_still_sees_a_rebuilt_registry(self):
        """摘的是**指纹**，不是审计：⑤ 的地板在运行期直接读登记表，照旧会看见它变了。"""
        src = (PROJECT / "lib/web/server.py").read_text(encoding="utf-8")
        self.assertIn("audit_results(ROOT", src,
                      "⑤/⑬ 的地板必须仍然直接跑 result_contract 审计（而不是靠指纹）")


class ReferenceDependencyTests(unittest.TestCase):
    """`skills/_references/**` 也按**真实依赖**给 —— 不再是整目录。

    症状：往 `math_modeling_norms.md` 加一节「行文用词：不要用故」（**只管论文措辞**）
    ⇒ 该目录哈希变 ⇒ **全部 16 个阶段**的「做法要求」指纹一起变。生产阶段有 stale 宽待保着，
    被误伤的是**门禁**（`_input_split` 明写"判据一变必须重判"）⇒ ③⑤ 真的从头重判一遍。

    与 `_LIB_INSTRUCTION_USERS` 同一套纪律：依据 = 运行日志的真实文件访问；
    **没证据的阶段保守给全**；**只在访问量 ≥50 且零命中时才敢摘**。
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

    def _ins(self, sid):
        stage = next(x for x in self.s.STAGES if x["id"] == sid)
        return self.s._input_split(stage)[1]

    def _edit(self, rel, ids):
        f = self.root / rel
        before = {i: self._ins(i) for i in ids}
        f.write_text(f.read_text(encoding="utf-8") + "\n<!-- 改一笔 -->\n", encoding="utf-8")
        return before, {i: self._ins(i) for i in ids}

    # ---- 正题：改了跟它无关的规范，不许把它吵醒 ----

    def test_editing_the_modeling_norms_does_not_wake_the_audit_gate(self):
        """⑤ 结果可信度审计：608 次文件访问、`_references/` **0 命中** ⇒ 摘掉。"""
        before, after = self._edit("skills/_references/math_modeling_norms.md",
                                   ("audit", "literature"))
        self.assertEqual(before["audit"], after["audit"],
                         "⑤ 又被 `math_modeling_norms.md` 唤醒了 —— 它审的是数值/口径/泄漏，"
                         "运行日志 608 次访问里 0 次落在 _references/ 下")

    def test_editing_stage_discipline_does_not_wake_its_non_readers(self):
        """⑪ 数学论证门禁 105 次访问、`stage_discipline.md` 0 命中 ⇒ 摘掉。"""
        before, after = self._edit("skills/_references/stage_discipline.md",
                                   ("mathproof",))
        self.assertEqual(before["mathproof"], after["mathproof"],
                         "⑪ 又被 `stage_discipline.md` 唤醒了 —— 它读的是 norms，不是纪律")

    # ---- 反向守卫：别改过头（真读它的必须照旧响） ----

    def test_the_review_gate_still_follows_the_modeling_norms(self):
        """③ 是 `math_modeling_norms.md` 的**第一消费者**（33 次命中）——
        摘掉它等于让建模评审漏掉规范变化，比多跑一轮危险得多。"""
        before, after = self._edit("skills/_references/math_modeling_norms.md", ("review",))
        self.assertNotEqual(before["review"], after["review"],
                            "③ 不跟 `math_modeling_norms.md` 了 —— 那建模评审就会照着旧规范放行")

    def test_the_coding_stage_still_follows_stage_discipline(self):
        """反向守卫：④ 读 `stage_discipline.md` 11 次（返修纪律就在那里）。"""
        before, after = self._edit("skills/_references/stage_discipline.md", ("code",))
        self.assertNotEqual(before["code"], after["code"], "④ 不跟 stage_discipline 了")

    def test_internal_leak_words_follows_its_skill_citations(self):
        """`internal_leak_words.md` 全阶段 0 命中，**但** SKILL 文本点名了它的消费者：
        `skills/15Verification/SKILL.md`（两处）与 `skills/9Paper-writing/SKILL.md`（一处）。
        摘"零命中"要靠这条交叉证据，不能只看访问日志。"""
        users = self.s._REFERENCE_USERS["internal_leak_words.md"]
        self.assertIn("write", users, "⑨ 的 SKILL 点名了它（写作定稿自检第⑤条）")
        self.assertIn("verify", users, "⑬ 的 SKILL 点名了它（复扫最终 pdf）")
        self.assertNotIn("code", users,
                         "④ 不产 pdf、也不做终稿复扫 —— 它读它 0 次（1042 次访问里）")

    # ---- 纪律守卫 ----

    def test_every_stage_named_in_the_table_exists(self):
        """手滑守卫：表里写错阶段 id 会让那条依赖**静默失效**。"""
        ids = {s["id"] for s in self.s.STAGES}
        for ref, users in self.s._REFERENCE_USERS.items():
            unknown = users - ids
            self.assertFalse(unknown, f"{ref} 指向了不存在的阶段: {sorted(unknown)}")

    def test_every_reference_file_is_covered(self):
        """漏一个文件 = 它整份掉出所有阶段的指纹（改了没人知道）。"""
        on_disk = {p.name for p in (PROJECT / "skills/_references").iterdir() if p.is_file()}
        self.assertEqual(on_disk, set(self.s._REFERENCE_USERS),
                         "`skills/_references/` 的实盘文件与 _REFERENCE_USERS 的键不一致")

    def test_the_conservative_default_covers_stages_without_evidence(self):
        """没有运行证据的阶段（⑫⑬⑭⑮⑯ 从未跑过）保守给全 ——
        给多了只是多跑一轮，给少了会让阶段漏掉真变化。"""
        for ref, users in self.s._REFERENCE_USERS.items():
            for sid in ("cross", "verify", "rubric", "fix", "demo"):
                self.assertIn(sid, users, f"{sid} 从未运行过，{ref} 该保守给它")

    def test_the_references_directory_is_not_fingerprinted_wholesale(self):
        """源码级钉子：`ins` 里不许再出现整目录。"""
        src = (PROJECT / "lib/web/server.py").read_text(encoding="utf-8")
        block = src.split("    ins = [", 1)[1].split("]", 1)[0]
        self.assertNotIn("skills/_references", block,
                         "`ins` 又整目录打包 `skills/_references` 了 —— "
                         "改一条只管论文措辞的规矩会命中全部 16 个阶段")


class FigurePolishAuthorityTests(unittest.TestCase):
    """⑦ 有权**就地**优化数据图的画法与图注 —— 契约必须留在 SKILL 文本里。

    为什么要有这条守卫：这项授权**只写在 SKILL 文本里**（驱动侧不改 —— ⑧ 的 `FAIL->drawio`
    本来就把回执交给 ⑦）。文本被改回去 = 结构被改回去，而它的代价是
    **2h51m / 次**（④ 41 min + ⑤⑥ 58 min + ⑦⑧ 72 min，换四行不碰数值的改动）。
    """

    def _skill(self, rel):
        return (PROJECT / rel).read_text(encoding="utf-8", errors="replace")

    def test_drawio_may_polish_but_must_not_touch_numbers(self):
        t = self._skill("skills/7Route-diagram/SKILL.md")
        for kw in ("legend(loc=)", "bbox=", "ylim", "clip_on", "levels", "gamma", "caption"):
            self.assertIn(kw, t, f"⑦ 的白名单少了 {kw} —— ⑧ 那类判词又只能交回 ④")
        for guard in ("code/", "results/", "*.npz", "sources", "逐字节"):
            self.assertIn(guard, t, f"⑦ 的硬判据少了 {guard} —— 授权会变成改数值的口子")

    def test_drawio_must_not_hand_back_a_pure_polish_defect(self):
        t = self._skill("skills/7Route-diagram/SKILL.md")
        self.assertIn("不许往上交", t,
                      "交回规则没写『画法类就地修』—— 一层打磨又得绕 ④ 一圈")

    def test_figreview_routes_polish_to_drawio_and_numbers_to_code(self):
        t = self._skill("skills/8Figure-gate/SKILL.md")
        self.assertIn("就地改", t, "⑧ 的去向没写清『画法类由 ⑦ 就地改』")
        self.assertIn("数值或口径", t, "⑧ 没写明『只有数值/口径才交回 ④』")

    def test_coding_stage_knows_it_no_longer_owns_the_polish(self):
        t = self._skill("skills/4Coding-and-computation/SKILL.md")
        self.assertIn("首次生成", t, "④ 的分工没写『首次生成』")
        self.assertIn("不再回退本阶段", t, "④ 不知道『画得好不好』已经不归它了")


class TestEntrypointHygieneTests(unittest.TestCase):
    """每个测试文件的 `unittest.main()` 必须在**文件末尾**。

    `if __name__ == "__main__":` 块被夹在**文件中间**时，**直接跑该文件**
    （`python regression/test_x.py`）会静默少跑后面全部测试类 —— 例如
    `test_workflow.py` 少跑 42 条、`test_viz_quality.py` 少跑 36 条，
    而输出仍旧是「OK」，看不出少了东西。

    `unittest discover` **不受影响**（它按模块收集、不执行 `__main__` 块），所以这个坑
    **只在有人直接跑单个文件时**发作 —— 而那正是排查问题时最常用的姿势。
    """

    def test_no_test_file_has_a_mid_file_main_block(self):
        for p in sorted((PROJECT / "regression").glob("test_*.py")):
            lines = p.read_text(encoding="utf-8").split("\n")
            idx = next((i for i, l in enumerate(lines)
                        if l.startswith('if __name__ == "__main__":')), None)
            if idx is None:
                continue
            self.assertGreaterEqual(
                idx, len(lines) - 4,
                f"{p.name}: `unittest.main()` 在第 {idx + 1} 行、文件共 {len(lines)} 行 —— "
                f"它**后面**的测试类在直接跑该文件时根本不会执行（而输出仍写着 OK）。"
                f"把它挪到文件末尾。")


class ContentLayoutDecouplingTests(unittest.TestCase):
    """内容侧阶段**不看版式侧**。

    背景：`14Layout-and-format` 排在 `13Repair-by-rubric-verdict` **之后**，而它独占
    `paper/_base/`（导言区）并重编 PDF。若内容判官（10/11/12/13）仍按整份 `paper/` 判失效，
    排版每动一次就把它们判失效一次 ⇒ 下一轮重修 `13→14→15`（14 一次 ~2h）。
    所以版式侧文件不进内容侧的输入指纹，但**内容**（`paper/sections/` 等）照旧要算。
    """

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        from test_workflow import load_server
        self.s = load_server(self.root)
        for rel in ("paper/_base/preamble.tex", "paper/sections/5_problem4.tex",
                    "paper/main.pdf", "paper/main.tex"):
            p = self.root / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("x", encoding="utf-8")

    def _art(self, sid):
        stage = next(st for st in self.s.STAGES if st["id"] == sid)
        return self.s._input_split(stage)[0]

    def test_layout_only_edits_do_not_invalidate_the_content_stages(self):
        for sid in ("mathproof", "cross", "rubric", "fix"):
            before = self._art(sid)
            (self.root / "paper/_base/preamble.tex").write_text("y", encoding="utf-8")
            (self.root / "paper/main.pdf").write_bytes(b"%PDF-1.4 new")
            self.assertEqual(self._art(sid), before,
                             f"{sid} 不该因为 14Layout-and-format 改了版式/重编了 PDF 就失效")

    def test_content_edits_still_invalidate_them(self):
        """反向守卫：真改了正文 ⇒ 必须失效（否则会拿旧判词去改新文字）。

        注意每轮要写**不同**内容：若每轮写同一串，第二轮起字节没变、指纹自然也不变，
        断言必红。
        """
        for n, sid in enumerate(("mathproof", "cross", "rubric")):
            before = self._art(sid)
            (self.root / "paper/sections/5_problem4.tex").write_text(f"改了正文 {n}", encoding="utf-8")
            self.assertNotEqual(self._art(sid), before,
                                f"{sid} 必须看到正文被改")

    def test_verification_still_sees_layout(self):
        """`15Verification` **不在**解耦名单里 —— 它要审的正是最终成品（含版式）。

        注意**不要**拿 `paper/main.pdf` 当探针：编译产物本来就被 `_is_paper_build_output`
        排除在所有阶段的指纹之外（既有设计），改它谁都不动。
        """
        before = self._art("verify")
        (self.root / "paper/_base/preamble.tex").write_text("改了版式 2", encoding="utf-8")
        self.assertNotEqual(self._art("verify"), before, "验收必须看到版式变了")

    def test_verification_ignores_the_registration_sidecars(self):
        """登记件不许进指纹：`paper/page-map.json` / `formula-review.json` 是
        **构建派生的登记件**（⑭/⑮ 重编译后按物理页**重绑**映射、**重测**公式页）。
        它们若留在指纹里，⑮ 按 SKILL 重编译、重绑映射之后就会**自己把自己判成"输入发生
        变更"** ⇒ `unverified` 硬挂、**交付包永不收集**（挂起时 reason 给的那两条提示是
        "往 request/data 放文件"与"改了被审论文"，而 `request/`+`data/` 的 mtime 根本没动，
        两条都不是真因）。

        判据与 `main.tex` 同一条（改 `.tex` 才算真的改论文）：
          · 两个登记件变了 ⇒ ⑮ 的输入指纹**不许动**；
          · 正对照 `.tex` 变了 ⇒ 必须动（没有它，一条恒等的实现也能让上面那条绿）。
        """
        before = self._art("verify")
        (self.root / "paper/page-map.json").write_text('{"schema_version": 1}', encoding="utf-8")
        (self.root / "paper/formula-review.json").write_text('{"schema_version": 1}', encoding="utf-8")
        self.assertEqual(self._art("verify"), before,
                         "登记件是构建副产品，不该让 ⑮ 的输入指纹变")
        (self.root / "paper/sections/5_problem4.tex").write_text("改了正文", encoding="utf-8")
        self.assertNotEqual(self._art("verify"), before,
                            "正对照失败：改 .tex 必须动指纹（否则上面那条是假的）")


class NarrativeReportNoiseTests(unittest.TestCase):
    """⑬/⑭ 写**自己的报告**不该把 ⑮ 判失效。

    根因：`_input_split` 默认"所有前序报告全收"，而 ⑬ 的 `FIX_REPORT.md` / ⑭ 的
    `FORMAT_REPORT.md` 正卡在 ⑮ 前面。⑬ 哪怕判「判词不属实、不动稿」（它的 SKILL 允许，
    报告照样重写一份）也会让 ⑮ 失配 —— 而 `_back_to_judge` 判"⑬ 有没有动稿"读的正是这份
    指纹，于是 **⑬ 自己的记录成了"改过稿"的自证**，白回 ⑮ 复评一轮；⑭ 的输入里也有
    ⑬ 的返修记录 ⇒ 一次 ~2h 的空跑。摘除表见 `lib/web/server.py::_REPORT_INPUT_EXCLUDE`。

    这里必须同时钉住**两件相反的事**：叙述重写**不许**触发（下面第一组），
    真改成品**必须**触发（第二组对照）。只钉前者的话，把 ⑮ 的输入整个清空也能过。
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

    def _art(self, sid):
        stage = next(x for x in self.s.STAGES if x["id"] == sid)
        return self.s._input_split(stage)[0]

    def _touch(self, rel, text="x"):
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")

    # ---- 第一组：叙述重写不该触发（先建好文件，再改内容 —— 缺→有 本身也是变化） ----

    def test_repair_record_does_not_invalidate_the_later_stages(self):
        for rel in ("reports/FIX_REPORT.md", "reports/FORMAT_REPORT.md"):
            self._touch(rel, "第一版")
        for sid in ("format", "verify"):
            with self.subTest(stage=sid):
                before = self._art(sid)
                # 内容每次都不同 —— 否则第二个 subTest 写的是同一串字节，断言就成了恒真
                self._touch("reports/FIX_REPORT.md", f"⑬ 这一轮说：判词不属实，不动稿（{sid}）")
                self.assertEqual(self._art(sid), before,
                                 f"⑬ 只重写了自己的返修记录，{sid} 不该失配")

    def test_format_record_does_not_invalidate_verification(self):
        self._touch("reports/FORMAT_REPORT.md", "第一版")
        before = self._art("verify")
        self._touch("reports/FORMAT_REPORT.md", "⑭ 这一轮压了两页")
        self.assertEqual(self._art("verify"), before, "⑭ 只重写了自己的排版记录，⑮ 不该失配")

    def test_other_stages_still_take_every_upstream_report(self):
        """默认**没变**：表里没写的阶段照旧全收（摘除必须是逐阶段、有证据的）。

        探针用 ④ 的结果报告（排在所有目标**之前**，谁都收得到）—— 拿 ⑫ 的去探 ⑪ 是探不到的，
        ⑫ 排在 ⑪ 后面，它本来就不在 ⑪ 的输入里。
        """
        self._touch("reports/RESULTS_REPORT.md", "第一版")
        for n, sid in enumerate(("demo", "cross", "verify")):
            with self.subTest(stage=sid):
                before = self._art(sid)
                self._touch("reports/RESULTS_REPORT.md", f"④ 第 {n + 2} 次跑的结果")   # 每次内容都要不同
                self.assertNotEqual(self._art(sid), before,
                                    f"{sid} 该看到 ④ 的结果报告变了")

    # ---- 第二组：真改成品必须触发（否则上面那组可能只是恒真） ----

    def test_a_real_paper_edit_still_invalidates_verification(self):
        for rel in ("reports/FIX_REPORT.md", "reports/FORMAT_REPORT.md"):
            self._touch(rel)
        before = self._art("verify")
        self._touch("paper/sections/5_problem4.tex", "改了正文 —— 必须重验")
        self.assertNotEqual(self._art("verify"), before, "正文改了，⑮ 必须重验")

    def test_verification_now_sees_the_appendix_and_the_submission_pack(self):
        """这是"漏"的那一侧：⑮ 逐项对账的提交件必须都进指纹。"""
        for rel in ("paper_appendix", "reports/SUBMISSION_MANIFEST.json", "运行说明.md"):
            with self.subTest(path=rel):
                self._touch(rel, "第一版")
                before = self._art("verify")
                self._touch(rel, "第二版")
                self.assertNotEqual(self._art("verify"), before,
                                    f"{rel} 改了，⑮ 却不重验 —— 改动漏网")

    # ---- 不变量：摘掉的只是叙述，它说的东西必须仍在指纹里 ----

    def test_dropping_a_record_loses_no_deliverable(self):
        """摘除的**正确性条件**（不是"零命中就摘"）：那份报告的写者除了报告之外能碰的
        东西，必须已经在本阶段的输入里 —— 否则摘掉就真漏了。

        这条会随 `ARTIFACTS`/摘除表变化自动复查：谁把 `paper` 从 ⑮ 的输入里去掉、
        或者新加一个「只存在于报告里」的产物，它当场就红。
        """
        writer = {s["report"]: s["id"] for s in self.s.STAGES}
        for sid, dropped in self.s._REPORT_INPUT_EXCLUDE.items():
            stage = next(x for x in self.s.STAGES if x["id"] == sid)
            art = self.s._input_paths(stage)
            for rep in dropped:
                wid = writer[rep]
                # 写者除 `reports/**` 之外的产物（= 真东西；报告本身只是叙述）
                deliverables = [p for p in self.s.ARTIFACTS[wid]
                                if not p.replace("\\", "/").startswith("reports/")]
                for path in deliverables:
                    p = path.replace("\\", "/")
                    covered = any(p == d or p.startswith(d.rstrip("/") + "/")
                                  for d in art)
                    self.assertTrue(
                        covered, f"{sid} 摘掉了 reports/{rep}，但它的写者 {wid} 的产物 "
                                 f"{p} 不在 {sid} 的输入里 —— 摘掉就漏真变化了")


if __name__ == "__main__":
    unittest.main()
