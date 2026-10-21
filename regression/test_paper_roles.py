# -*- coding: utf-8 -*-
"""P1: role schema, problem_count resolution, assembler and structure check."""
import json
import hashlib
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))

from lib import paper_structure as ps  # noqa: E402

TEMPLATE = "zh/cumcm-latex"
TEMPLATE_DIR = PROJECT / "skills/9Paper-writing/templates" / TEMPLATE


def _has_live_problem_count_source() -> bool:
    """`PROJECT` 是一份“跑过的工作区”时才有问数可解析。

    干净检出（没有 `reports/ANALYSIS_MODELING_REPORT.md`、也没有 `reports/INTAKE.json`）
    上，`resolve_problem_count` 必然抛 StructureError；这两组用例用 live 工作区做
    “resolver 与当前题一致”的交叉核对，没有 live 源时应**跳过**，不能把干净检出打红。
    """
    return ((PROJECT / "reports/ANALYSIS_MODELING_REPORT.md").is_file()
            or (PROJECT / "reports/INTAKE.json").is_file())


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _intake(root: Path, subquestions, confidence="high", uncertain=None) -> None:
    _write(root / "reports/INTAKE.json", json.dumps({
        "schema_version": 1,
        "problem": {
            "subquestions": subquestions,
            "confidence": confidence,
            "uncertain": uncertain or [],
        },
    }, ensure_ascii=False))


def _analysis_report(root: Path, rows: int = 3) -> None:
    body = "\n".join(f"| P{i} | 目标{i} |" for i in range(1, rows + 1))
    _write(root / "reports/ANALYSIS_MODELING_REPORT.md",
           "## 1.2 子问题\n\n| 子问题 | 目标 |\n|---|---|\n" + body + "\n")


class RolesSchemaTests(unittest.TestCase):
    def test_roles_json_is_valid_and_complete(self):
        doc, path = ps.load_roles(PROJECT, TEMPLATE)
        roles = doc["roles"]
        self.assertEqual(len(roles), 13)
        for rid, role in roles.items():
            self.assertIn(role["placement"], {"block", "file", "external"}, rid)
            if role.get("page_kind") is not None:
                self.assertIn(role["page_kind"], ps.PAGE_KINDS, rid)
            if role["placement"] == "block":
                self.assertTrue((TEMPLATE_DIR / role["block"]).is_file(), rid)
            if role["placement"] == "file" and role.get("file"):
                self.assertTrue((TEMPLATE_DIR / role["file"]).is_file(), rid)

    def test_core_roles_cannot_be_disabled(self):
        roles = ps.load_roles(PROJECT, TEMPLATE)[0]["roles"]
        for rid in ("analysis", "assumptions", "symbols"):
            self.assertFalse(roles[rid]["disablable"], rid)
        for rid in ("ai_statement", "appendix_pdf", "materials_list"):
            self.assertTrue(roles[rid]["disablable"], rid)

    def test_default_profile_matches_roles(self):
        roles = ps.load_roles(PROJECT, TEMPLATE)[0]["roles"]
        profile, _ = ps.load_profile(PROJECT, TEMPLATE, None)
        order = profile["structure"]["order"]
        self.assertEqual(len(order), len(set(order)))
        self.assertTrue(set(order) <= set(roles))
        self.assertEqual(order[0], "title")
        self.assertEqual(order[-1], "materials_list")


class ProblemCountTests(unittest.TestCase):
    def setUp(self):
        if not _has_live_problem_count_source():
            self.skipTest("干净检出没有 live 报告/INTAKE，无法与当前题交叉核对问数")
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def test_explicit_profile_count_wins(self):
        out = ps.resolve_problem_count(self.tmp, {"structure": {"problem_count": 5}})
        self.assertEqual(out["problem_count"], 5)
        self.assertEqual(out["problem_count_source"], "effective_profile")

    def test_intake_list_used_when_certain(self):
        _intake(self.tmp, ["a", "b", "c"], confidence="high")
        out = ps.resolve_problem_count(self.tmp, {"structure": {}})
        self.assertEqual(out["problem_count"], 3)
        self.assertEqual(out["problem_count_source"], "intake:problem.subquestions")
        self.assertEqual(out["intake_subquestion_count"], 3)

    def test_intake_string_is_not_len(self):
        _intake(self.tmp, "abc", confidence="high")
        _analysis_report(self.tmp, rows=4)
        out = ps.resolve_problem_count(self.tmp, {"structure": {}})
        self.assertEqual(out["problem_count"], 4)
        self.assertEqual(out["problem_count_source"], "analysis_report")

    def test_count_uncertain_falls_back_to_analysis(self):
        _intake(self.tmp, ["one"], confidence="medium",
                uncertain=["题面没有分问，是否拆成多问需人拍板"])
        _analysis_report(self.tmp, rows=3)
        out = ps.resolve_problem_count(self.tmp, {"structure": {}})
        self.assertEqual(out["problem_count"], 3)
        self.assertEqual(out["problem_count_source"], "analysis_report")
        self.assertEqual(out["intake_subquestion_count"], 1)
        self.assertTrue(out["warnings"])

    def test_no_source_exits_5_without_writing(self):
        with self.assertRaises(ps.StructureError) as ctx:
            ps.resolve_problem_count(self.tmp, {"structure": {}})
        self.assertEqual(ctx.exception.code, 5)
        self.assertFalse((self.tmp / "paper").exists())

    def test_current_workspace_resolves_consistently(self):
        """The live workspace may have 3 or 4 questions; pin the **source/consistency**,
        not a number that belongs to one particular run.

        The old version hard-coded `3` + `analysis_report`; the workspace then moved to a
        4-question run with a certain INTAKE list, so the test started failing even though
        the resolver was correct.  The invariant that matters is: the resolver returns a
        positive count and its source agrees with the count it reports.
        """
        out = ps.resolve_problem_count(PROJECT, {"structure": {}})
        self.assertGreaterEqual(out["problem_count"], 1)
        self.assertIn(out["problem_count_source"],
                      {"effective_profile", "intake:problem.subquestions", "analysis_report"})
        if out["problem_count_source"] == "intake:problem.subquestions":
            self.assertEqual(out["problem_count"], out["intake_subquestion_count"])
            intake = json.loads((PROJECT / "reports/INTAKE.json").read_text(encoding="utf-8"))
            subs = ((intake.get("problem") or {}).get("subquestions"))
            self.assertIsInstance(subs, list)
            self.assertEqual(out["problem_count"], len(subs))
        elif out["problem_count_source"] == "analysis_report":
            self.assertGreaterEqual(out["problem_count"], 1)
            self.assertIsInstance(out["intake_subquestion_count"], (int, type(None)))


class AssemblerTests(unittest.TestCase):
    def setUp(self):
        if not _has_live_problem_count_source():
            self.skipTest("干净检出没有 live 报告/INTAKE，无法解析问数")
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.out = self.tmp / "paper"
        shutil.copytree(TEMPLATE_DIR / "blocks", self.out / "blocks")
        shutil.copytree(TEMPLATE_DIR / "sections", self.out / "sections")
        shutil.copy2(TEMPLATE_DIR / "references.tex", self.out / "references.tex")
        # The template ships 5_problem1..3; a live 4-question workspace resolves to 4.
        # ⑨ creates the extra section at write time; simulate that before assemble/check.
        self.problem_count = ps.resolve_problem_count(
            PROJECT, {"structure": {}})["problem_count"]
        for i in range(1, self.problem_count + 1):
            p = self.out / "sections" / f"5_problem{i}.tex"
            if not p.is_file():
                p.write_text(f"\\section{{问题{i}}}\\label{{sec:problem{i}}}\n",
                             encoding="utf-8")

    def test_assemble_default_and_check(self):
        plan = ps.assemble(PROJECT, template=TEMPLATE, out_dir=self.out)
        self.assertEqual(plan["problem_count"], self.problem_count)
        self.assertEqual(plan["enabled"][0], "title")
        self.assertEqual(plan["enabled"][-1], "materials_list")
        self.assertEqual(set(plan["deliverables"]), {"AI工具使用详情.pdf", "附录A.pdf"})
        cfg = json.loads((PROJECT / "config/publication.json").read_text(encoding="utf-8"))
        self.assertEqual(plan["page_markers"], cfg["kind_start_markers"])
        tex = (self.out / "paper-structure.tex").read_text(encoding="utf-8")
        for token in ("\\input{blocks/title}", "\\input{blocks/abstract}",
                      f"\\input{{sections/5_problem{self.problem_count}}}", "\\FloatBarrier",
                      "\\input{blocks/materials_list}"):
            self.assertIn(token, tex)
        self.assertEqual(ps.check(PROJECT, self.out)["status"], "PASS")

    def test_assemble_is_byte_idempotent(self):
        ps.assemble(PROJECT, template=TEMPLATE, out_dir=self.out)
        first = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                 for p in (self.out / "paper-structure.tex", self.out / "structure.json")}
        ps.assemble(PROJECT, template=TEMPLATE, out_dir=self.out)
        second = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in (self.out / "paper-structure.tex", self.out / "structure.json")}
        self.assertEqual(first, second)

    def test_check_catches_tampered_tex(self):
        ps.assemble(PROJECT, template=TEMPLATE, out_dir=self.out)
        p = self.out / "paper-structure.tex"
        p.write_text(p.read_text(encoding="utf-8") + "% tampered\n", encoding="utf-8")
        result = ps.check(PROJECT, self.out)
        self.assertEqual(result["status"], "FAIL")
        self.assertTrue(any("paper_structure_sha256" in x for x in result["issues"]))

    def test_sync_title_fills_from_block(self):
        ps.assemble(PROJECT, template=TEMPLATE, out_dir=self.out)
        title = self.out / "blocks/title.tex"
        title.write_text("\\papertitle{测试标题}\n", encoding="utf-8")
        plan = ps.sync_title(PROJECT, self.out)
        self.assertEqual(plan["title"], "测试标题")
        self.assertEqual(plan["title_source"], "blocks/title.tex")
        self.assertEqual(ps.check(PROJECT, self.out)["status"], "PASS")

    def test_sync_title_refuses_placeholder(self):
        ps.assemble(PROJECT, template=TEMPLATE, out_dir=self.out)
        plan = ps.sync_title(PROJECT, self.out)
        self.assertIsNone(plan["title"])
        self.assertTrue(any("占位符" in w for w in plan["warnings"]))


if __name__ == "__main__":
    unittest.main()
