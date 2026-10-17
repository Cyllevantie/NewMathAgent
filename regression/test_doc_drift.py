# -*- coding: utf-8 -*-
"""跨文件的「散文漂移」哨兵（2026-10-17 单一源收敛轮）。

这一组守的是**同一事实被手写多份**造成的那类漂移 —— 它们全是这轮审计里实际抓到的
（旧阶段编号、过期阈值、模板归属句、正典与注入副本）。与行为用例不同，这里扫的是
live 文档/源码文本：

- 每条断言都配「至少扫到一处」的正对照，防止 glob/正则写错后静默变绿；
- 历史目录（产物/、2026A试跑示例/、reports/、_tmp/、tmp/、paper/、paper_appendix/、
  demo/、figures/、code/、results/、cache/、runtime/）不扫；
- `docs/KNOWN_GAPS.md` 是历史台账，文件头已声明「旧编号只作历史记录」，单独豁免。
"""
import ast
import json
import re
import sys
import unittest
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
# 单跑本模块时 `regression/` 不在 sys.path（discover 才会加）——
# 下面两个用例要借 `test_workflow.load_server` 复用隔离工作区加载器。
sys.path.insert(0, str(Path(__file__).resolve().parent))

LIVE_GLOBS = ("lib/**/*.py", "lib/web/static/index.html", "skills/**/*.md",
              "skills/**/*.tex", "skills/skills.sh.json", "docs/**/*.md",
              "README.md", "CLAUDE.md", "AGENTS.md")
EXEMPT = {(PROJECT / "docs/KNOWN_GAPS.md").resolve()}


def live_files():
    seen = {}
    for pat in LIVE_GLOBS:
        for p in sorted(PROJECT.glob(pat)):
            if p.is_file():
                seen[p.resolve()] = p
    return [p for r, p in sorted(seen.items()) if r not in EXEMPT]


class StageNumberingDriftTest(unittest.TestCase):
    """旧阶段编号 / 旧门禁数不许再出现在 live 文本里。

    当前编号：⑩=数学论证门禁、⑬=按评分判词返修、⑭=排版与版式、⑮=验收。
    旧稿里 ⑩ 曾是排版、⑮ 曾是返修 —— 这类串会让读它的 agent 按错阶段行事。
    字符串在断言里拼接构造，避免本文件自己命中自己的扫描。
    """

    # 只钉**语义上必然错误**的组合（「排版」只能指 ⑭、「验收」只能指 ⑮…）。
    #   2026-10-17 审计：原先把 `⑩ 无权/既不能/会打转` 也钉进来，会误伤事实正确的
    #   「⑩（数学论证）只审不改，既不能改论文」这类句子 —— 泛用动词不能绑阶段号。
    STALE = [
        re.compile(r"⑩\s*排版"), re.compile(r"⑩\s*独占"),
        re.compile(r"⑬\s*验收"), re.compile(r"⑭\s*评分标"),
        re.compile(r"⑮\s*按评分判词返修"), re.compile(r"共\s*6\s*道门禁"),
    ]

    def test_no_stale_stage_numbering_in_live_files(self):
        hits = []
        files = live_files()
        self.assertGreater(len(files), 50, "没扫到 live 文件 —— glob 写错了？")   # 正对照
        for p in files:
            text = p.read_text(encoding="utf-8", errors="replace")
            for rx in self.STALE:
                for m in rx.finditer(text):
                    hits.append(f"{p.relative_to(PROJECT).as_posix()}: {m.group(0)}")
        self.assertEqual(hits, [], "旧编号/旧口径残留（按当前 STAGES 改成新编号）：\n" + "\n".join(hits))


class TemplateOwnershipDriftTest(unittest.TestCase):
    """模板层的「清单表归属」句必须指向 ⑨ —— 模板会被 ⑨ 原样复制进两个工程。

    只禁**归属类**旧句；`由 14Layout-and-format 填公式数 / 独占导言区` 是对的（仍归 ⑭），
    别把它们误伤进黑名单。
    """

    STALE = ["由 format 阶段生成", "由 14Layout-and-format 逐行生成",
             "由 `14Layout-and-format` 逐行生成", "由 14Layout-and-format 生成该节"]

    def test_templates_do_not_carry_old_ownership_phrases(self):
        hits, scanned = [], 0
        for p in sorted((PROJECT / "skills").glob("**/templates/**/*")):
            if not p.is_file() or p.suffix not in (".tex", ".md"):
                continue
            scanned += 1
            text = p.read_text(encoding="utf-8", errors="replace")
            for s in self.STALE:
                if s in text:
                    hits.append(f"{p.relative_to(PROJECT).as_posix()}: {s}")
        self.assertGreater(scanned, 5, "没扫到模板文件 —— glob 写错了？")      # 正对照
        self.assertEqual(hits, [], "模板里还有旧归属句：\n" + "\n".join(hits))


class FillThresholdDriftTest(unittest.TestCase):
    """摘要填充率的散文阈值必须等于 `config/publication.json`（机器单源）。

    统一写法 `target X / hard Y`，本用例才扫得到；每份点名文件必须**至少出现一处**
    （正对照），且所有出现都必须等于配置值。改写法 = 改哨兵覆盖面，别只改一处。
    """

    CANON = re.compile(r"target\s*([0-9]+(?:\.[0-9]+)?)\s*/\s*hard\s*([0-9]+(?:\.[0-9]+)?)")
    # 文件 → 至少应出现的 canonical 次数。9 SKILL 有三处（摘要完成度/步骤6/纪律），
    #   把其中一处改写成 `target=`/百分号/逆序会让计数掉下来 —— 单靠"至少一处"会漏。
    FILES = {"config/publication.json": 1, "skills/9Paper-writing/SKILL.md": 3,
             "skills/_references/math_modeling_norms.md": 1,
             "skills/15Verification/SKILL.md": 1, "docs/PUBLICATION.md": 1,
             "skills/12Rubric-final/references/precedence.md": 1}

    def test_prose_thresholds_match_config(self):
        cfg = json.loads((PROJECT / "config/publication.json").read_text(encoding="utf-8-sig"))
        target = float(cfg["min_kind_fill"]["abstract"]["target"])
        hard = float(cfg["min_kind_fill"]["abstract"]["hard"])
        for rel, min_hits in self.FILES.items():
            text = (PROJECT / rel).read_text(encoding="utf-8")
            found = self.CANON.findall(text)
            self.assertGreaterEqual(len(found), min_hits,
                                    f"{rel} 的 `target X / hard Y` 只有 {len(found)} 处"
                                    f"（应≥{min_hits}）—— 写法被改掉或哨兵覆盖不到")
            for t, h in found:
                self.assertEqual((float(t), float(h)), (target, hard),
                                 f"{rel} 的 target/hard 与 config 不一致："
                                 f"{(t, h)} vs {(target, hard)}")


class GateCountDriftTest(unittest.TestCase):
    """叙述里的「共 N 道门禁」必须等于 STAGES 里带 gate 的阶段数（数字从代码派生）。"""

    def test_narrative_gate_count_matches_stages(self):
        import tempfile
        from test_workflow import load_server
        with tempfile.TemporaryDirectory() as tmp:
            gates = sum(1 for s in load_server(Path(tmp)).STAGES if s.get("gate"))
        text = (PROJECT / "skills/0Start-mathmodel/SKILL.md").read_text(encoding="utf-8")
        found = re.findall(r"共\s*(\d+)\s*道门禁", text)
        self.assertTrue(found, "0Start 里没写「共 N 道门禁」—— 哨兵覆盖不到")
        for n in found:
            self.assertEqual(int(n), gates, f"叙述写 {n} 道、实际 {gates} 道")


class MethodMarkCopyDriftTest(unittest.TestCase):
    """`stage_discipline §4` 与 `server.py` 的注入副本必须同含同一组关键句（逐字哨兵）。"""

    TOKENS = ("必须同时写一个同名 `.meta.json`", "`_method` 与 `_params`",
              "作废旧产物（方法变更：A → B）")

    def test_canon_and_prompt_copy_agree(self):
        canon = (PROJECT / "skills/_references/stage_discipline.md").read_text(encoding="utf-8")
        src = (PROJECT / "lib/web/server.py").read_text(encoding="utf-8")
        # 只扫**注入块本身**：扫整份文件时，把关键句挪进注释也能骗过哨兵（2026-10-17 审计）。
        start = src.index('if sid in ("code", "robustness"):')
        end = src.index('if stage.get("gate"):', start)
        prompt = src[start:end]
        self.assertGreater(len(prompt), 300, "注入块没截出来 —— 锚点变了？")   # 正对照
        for tok in self.TOKENS:
            self.assertIn(tok, canon, f"§4 正典缺关键句：{tok}")
            self.assertIn(tok, prompt, f"prompt 注入副本缺关键句：{tok}")


class CodeFpScopeTest(unittest.TestCase):
    """`_code_fp()` 只哈希 code/ **源码**：写 code/outputs 不许改它（2026-10-17 修）。

    对照组两条：写产物 ⇒ 指纹不变；改源码 ⇒ 指纹必须变（否则方法变更抓不到）。
    """

    def test_code_fp_ignores_generated_outputs(self):
        import shutil
        import tempfile
        from test_workflow import load_server
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, True)
        (tmp / "code/outputs").mkdir(parents=True)
        (tmp / "code/core.py").write_text("x = 1\n", encoding="utf-8")
        srv = load_server(tmp)          # 隔离工作区：别拿真仓库当 ROOT（模块级自检会读盘）
        fp1 = srv._code_fp()
        self.assertTrue(fp1, "指纹为空 —— _code_fp 失败被吞成了空串")
        (tmp / "code/outputs/a.npz").write_bytes(b"data")
        self.assertEqual(srv._code_fp(), fp1,
                         "写了产物不该改源码指纹（否则每轮把旧产物全判 stale）")
        (tmp / "code/core.py").write_text("x = 2\n", encoding="utf-8")
        self.assertNotEqual(srv._code_fp(), fp1, "改了源码必须改指纹（方法变更要抓得到）")


class CheckerInstructionDependencyTest(unittest.TestCase):
    """`check_skeleton.py` 是 ⑨/⑭/⑦ 的手工判据：它变了必须让这些阶段的 instructions 失配。

    为什么需要这条：`_prompt_fingerprint()` 只哈希 `server.py`，检查器是独立文件；
    不把它放进 `_LIB_INSTRUCTION_USERS`，改完判据后旧回执会被原样复用
    （2026-10-17 用户要求修）。
    """

    def test_the_checker_is_an_instruction_dependency_of_its_users(self):
        tree = ast.parse((PROJECT / "lib/web/server.py").read_text(encoding="utf-8"))
        table = None
        for node in tree.body:
            if (isinstance(node, ast.Assign)
                    and any(isinstance(t, ast.Name) and t.id == "_LIB_INSTRUCTION_USERS"
                            for t in node.targets)):
                table = ast.literal_eval(node.value)
                break
        self.assertIsInstance(table, dict, "没找到 _LIB_INSTRUCTION_USERS —— 锚点变了？")
        self.assertIn("lib/web/check_skeleton.py", table,
                      "改 check_skeleton.py 不会让任何阶段 stale —— 加进 _LIB_INSTRUCTION_USERS")
        self.assertEqual(table["lib/web/check_skeleton.py"], {"write", "format", "drawio"},
                         "check_skeleton.py 的依赖阶段应正好是 ⑨/⑭/⑦（见各自 SKILL 的引用）")


if __name__ == "__main__":
    unittest.main()
