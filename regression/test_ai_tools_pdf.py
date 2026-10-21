# -*- coding: utf-8 -*-
"""AI 工具使用详情 PDF 生成器：模板口径与端到端编译。

用户 2026-10-20 确认：以后统一按该模板生成，不手写 PDF。
"""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
SCRIPT = PROJECT / "skills/9Paper-writing/scripts/make_ai_tools_pdf.py"
REF = PROJECT / "skills/9Paper-writing/references/ai-tools-pdf.md"
EXAMPLE = PROJECT / "skills/9Paper-writing/assets/ai_tools/AI工具使用详情_示例.pdf"


def payload():
    return {
        "competition": "全国大学生数学建模竞赛（2026 年）",
        "problem": "A 题：药材的烘干问题",
        "tools": [
            {"name": "ChatGPT-6 Astra", "access": "桌面应用 / 网页端",
             "purpose": "LaTeX 公式排版、语言润色"},
            {"name": "DeepSeek-Flash", "access": "Visual Studio Code 插件",
             "purpose": "PSO 算法代码框架与调试辅助"},
        ],
        "records": [
            {"title": "LaTeX 公式排版",
             "prompt": "请把推导出的方程转成 LaTeX 代码，保持符号和上下标不变。",
             "equation": r"\rho c_p\frac{\partial T}{\partial t}=1",
             "ai": "给出了对应的 LaTeX 代码。",
             "member": "核对偏导符号、括号和量纲后放入论文公式环境。",
             "adoption": "约 80%", "check": "偏导、下标、括号与队员推导一致"},
            {"title": "PSO 算法代码",
             "prompt": "请给出一个 PSO 的 Python 代码框架，目标函数和约束由外部传入。",
             "ai": "给出了代码骨架。",
             "member": "按本题目标函数、约束重写，并做基准测试。",
             "adoption": "约 50%", "check": "目标函数、约束、随机种子、基准测试"},
        ],
        "code_rows": [
            {"part": "核心求解器", "ai": "由队员完成；AI 未参与核心推导"},
            {"part": "论文文字", "ai": "队员撰写；AI 仅做 LaTeX 排版和润色"},
        ],
        "manual_note": "核心建模、推导和结论均由队员完成。",
    }


class AiToolsPdfTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "reports").mkdir()
        (self.root / "reports" / "AI_TOOL_USAGE.json").write_text(
            json.dumps(payload(), ensure_ascii=False), encoding="utf-8")

    def run_script(self, *args):
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--root", str(self.root), *args],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=120,
        )

    def write_data(self, data):
        (self.root / "reports" / "AI_TOOL_USAGE.json").write_text(
            json.dumps(data, ensure_ascii=False), encoding="utf-8")

    def tex_path(self):
        return self.root / "paper/ai_tools/AI工具使用详情.tex"

    def test_no_compile_writes_template_tex(self):
        p = self.run_script("--no-compile")
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        tex = (self.root / "paper/ai_tools/AI工具使用详情.tex").read_text(encoding="utf-8")
        self.assertIn(r"\documentclass[12pt,a4paper]{ctexart}", tex)
        self.assertIn("top=2.42cm,bottom=2.27cm,left=2.50cm,right=2.18cm", tex)
        self.assertIn(r"\linespread{1.375}", tex)
        self.assertIn(r"\setCJKmainfont[BoldFont=SimHei]{SimSun}", tex)
        self.assertIn(r"\newunicodechar{α}{$\alpha$}", tex)
        self.assertIn(r"\begin{longtable}", tex)
        self.assertIn("提示词：", tex)
        self.assertIn("AI：", tex)
        self.assertIn("队员：", tex)
        # 不能只验证标签：payload 的真实内容必须进 .tex
        self.assertIn("请把推导出的方程转成 LaTeX 代码", tex)
        self.assertIn("给出了对应的 LaTeX 代码", tex)
        self.assertIn("核对偏导符号、括号和量纲", tex)
        self.assertIn("ChatGPT-6 Astra", tex)
        self.assertIn("DeepSeek-Flash", tex)
        self.assertNotIn("我：", tex)
        self.assertNotIn("队伍信息", tex)
        self.assertNotIn("使用起止时间", tex)
        self.assertNotIn("未保留完整聊天截图", tex)
        self.assertNotIn("问题重述由 AI 改写", tex)
        self.assertNotIn("本参赛队在竞赛过程中使用了 AI 工具", tex)

    def test_full_compile_if_xelatex_available(self):
        if not shutil.which("xelatex"):
            self.skipTest("xelatex 不可用")
        p = self.run_script()
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        pdf = self.root / "paper/ai_tools/AI工具使用详情.pdf"
        self.assertTrue(pdf.is_file())
        self.assertGreater(pdf.stat().st_size, 1000)

    def test_failed_compile_does_not_leave_a_stale_pdf(self):
        if not shutil.which("xelatex"):
            self.skipTest("xelatex 不可用")
        p = self.run_script()
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        pdf = self.root / "paper/ai_tools/AI工具使用详情.pdf"
        self.assertTrue(pdf.is_file())
        data = payload()
        data["records"][0]["equation"] = r"\frac{a}{b"
        (self.root / "reports" / "AI_TOOL_USAGE.json").write_text(
            json.dumps(data, ensure_ascii=False), encoding="utf-8")
        p = self.run_script()
        self.assertEqual(p.returncode, 1)
        self.assertFalse(pdf.exists(), "编译失败后不能把截断 PDF 留在交付路径")

    def test_no_code_rows_closes_at_section_five(self):
        data = payload()
        data["code_rows"] = []
        (self.root / "reports" / "AI_TOOL_USAGE.json").write_text(
            json.dumps(data, ensure_ascii=False), encoding="utf-8")
        p = self.run_script("--no-compile")
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        tex = (self.root / "paper/ai_tools/AI工具使用详情.tex").read_text(encoding="utf-8")
        self.assertIn(r"\section*{五、人工主导说明}", tex)
        self.assertNotIn(r"\section*{六、人工主导说明}", tex)

    def test_no_compile_removes_stale_pdf(self):
        out = self.root / "paper" / "ai_tools"
        out.mkdir(parents=True)
        pdf = out / "AI工具使用详情.pdf"
        pdf.write_bytes(b"%PDF-1.4 OLD VERSION\n" + b"x" * 2000)
        data = payload()
        data["problem"] = "B 题：换了一道题"
        self.write_data(data)

        p = self.run_script("--no-compile")

        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertFalse(pdf.exists(), "只写 .tex 时旧 PDF 不能留在交付路径")
        tex = self.tex_path().read_text(encoding="utf-8")
        self.assertIn("B 题：换了一道题", tex)

    def test_text_fields_reject_first_person(self):
        data = payload()
        data["records"][0]["member"] = "我把偏导符号逐个核对过了。"
        self.write_data(data)

        p = self.run_script("--no-compile")

        self.assertEqual(p.returncode, 2, p.stdout + p.stderr)
        self.assertIn("records[1].member", p.stderr)
        self.assertIn("禁用表述", p.stderr)
        self.assertFalse(self.tex_path().exists(), "校验失败不能留下半成品 .tex")

    def test_text_fields_reject_forbidden_phrases(self):
        for phrase in ("本参赛队", "使用起止时间", "未保留完整聊天截图", "问题重述"):
            with self.subTest(phrase=phrase):
                data = payload()
                data["records"][0]["prompt"] = "请按" + phrase + "的要求写。"
                self.write_data(data)

                p = self.run_script("--no-compile")

                self.assertEqual(p.returncode, 2, p.stdout + p.stderr)
                self.assertIn(f"禁用表述“{phrase}”", p.stderr)

    def test_tools_fields_must_be_non_empty(self):
        for key in ("name", "access", "purpose"):
            with self.subTest(key=key):
                data = payload()
                data["tools"][0][key] = "  "
                self.write_data(data)

                p = self.run_script("--no-compile")

                self.assertEqual(p.returncode, 2, p.stdout + p.stderr)
                self.assertIn(f"tools[1] 缺少 {key}", p.stderr)

    def test_code_rows_fields_must_be_non_empty(self):
        for key in ("part", "ai"):
            with self.subTest(key=key):
                data = payload()
                data["code_rows"][0][key] = ""
                self.write_data(data)

                p = self.run_script("--no-compile")

                self.assertEqual(p.returncode, 2, p.stdout + p.stderr)
                self.assertIn(f"code_rows[1] 缺少 {key}", p.stderr)

    def test_empty_adoption_and_check_omits_section_four(self):
        data = payload()
        for rec in data["records"]:
            rec["adoption"] = ""
            rec["check"] = ""
        self.write_data(data)

        p = self.run_script("--no-compile")

        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        tex = self.tex_path().read_text(encoding="utf-8")
        self.assertNotIn("采纳与人工核验", tex)
        self.assertNotIn("人工核验重点", tex)
        self.assertIn(r"\section*{四、代码与数据说明}", tex)
        self.assertIn(r"\section*{五、人工主导说明}", tex)

    def test_section_numbers_shift_when_both_later_sections_absent(self):
        data = payload()
        data["code_rows"] = []
        for rec in data["records"]:
            rec["adoption"] = ""
            rec["check"] = ""
        self.write_data(data)

        p = self.run_script("--no-compile")

        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        tex = self.tex_path().read_text(encoding="utf-8")
        self.assertNotIn("采纳与人工核验", tex)
        self.assertIn(r"\section*{四、人工主导说明}", tex)
        self.assertNotIn(r"\section*{五、", tex)

    def test_adoption_table_is_kept_when_data_present(self):
        # 反向对照：不能为了省空表把有内容的第四节也删掉。
        p = self.run_script("--no-compile")

        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        tex = self.tex_path().read_text(encoding="utf-8")
        self.assertIn(r"\section*{四、采纳与人工核验}", tex)
        self.assertIn("约 80", tex)
        self.assertIn(r"\section*{五、代码与数据说明}", tex)
        self.assertIn(r"\section*{六、人工主导说明}", tex)

    def test_text_check_is_not_over_broad(self):
        # 反向对照：只拦完整禁用短语与“我”，不能连“参赛队员”“问题理解”也拦掉。
        data = payload()
        data["records"][0]["member"] = "参赛队员核对符号；问题理解由队员完成。"
        self.write_data(data)

        p = self.run_script("--no-compile")

        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        tex = self.tex_path().read_text(encoding="utf-8")
        self.assertIn("参赛队员核对符号", tex)

    def test_missing_data_is_an_error(self):
        (self.root / "reports" / "AI_TOOL_USAGE.json").unlink()
        p = self.run_script("--no-compile")
        self.assertEqual(p.returncode, 2)
        self.assertIn("AI_TOOL_USAGE.json", p.stderr)

    def test_docs_and_example_are_wired(self):
        skill = (PROJECT / "skills/9Paper-writing/SKILL.md").read_text(encoding="utf-8")
        self.assertIn("make_ai_tools_pdf.py", skill)
        self.assertIn("references/ai-tools-pdf.md", skill)
        self.assertIn("AI_TOOL_USAGE.json", skill)
        self.assertTrue(REF.is_file())
        self.assertTrue(EXAMPLE.is_file())


if __name__ == "__main__":
    unittest.main()
