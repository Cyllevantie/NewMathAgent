# -*- coding: utf-8 -*-
"""跨阶段提示词一致性哨兵（2026-10-20 审计后固化）。

这里只钉**已经确认并修过的真矛盾**，防止后续编辑把旧口径又写回来。
不是全文语法检查；每条都对应一次实际冲突。
"""
import unittest
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]


def text(rel):
    return (PROJECT / rel).read_text(encoding="utf-8")


class InstructionConsistencyTests(unittest.TestCase):
    def test_page_quota_is_abstract_plus_body(self):
        t = text("skills/14Layout-and-format/SKILL.md")
        self.assertIn("摘要 + 正文（一～七）合计 ≤30 页", t)
        self.assertIn("正文 ≤29 页", t)
        self.assertNotIn("正文（一～七）≤30 页", t)
        self.assertIn("摘要 + 正文（一～七）合计 ≤30 页",
                      text("skills/12Rubric-final/references/precedence.md"))

    def test_appendix_can_take_tables_and_derivations(self):
        t = text("skills/14Layout-and-format/SKILL.md")
        self.assertIn("能迁的只有补充内容（补充图、补充表、完整推导块、更细的参数表）", t)
        self.assertNotIn("能迁的只有「补充图」", t)

    def test_appendix_does_not_contain_full_source(self):
        for rel in ("skills/15Verification/SKILL.md", "skills/9Paper-writing/SKILL.md"):
            t = text(rel)
            self.assertNotIn("附录完整代码", t, rel)
            self.assertIn("源码不排进论文", t, rel)

    def test_audit_precedes_robustness(self):
        t = text("skills/3Modeling-review-gate/SKILL.md")
        self.assertIn("先由 ⑤ 结果可信度审计", t)
        self.assertNotIn("代码跑完后 6Robustness 再做", t)

    def test_route_diagram_canvas_and_colors_come_from_config(self):
        t = text("skills/7Route-diagram/references/route-diagram.md")
        self.assertIn("图宽按 §0 定", t)
        self.assertNotIn("1200–1500", t)
        self.assertIn("色值一律从 `config/visualization.json`", t)
        self.assertNotIn("#66BB6A", t)
        self.assertNotIn("GeoGebra", text("skills/7Route-diagram/SKILL.md"))

    def test_figure_gate_font_size_comes_from_tokens(self):
        t = text("skills/8Figure-gate/SKILL.md")
        self.assertIn("style.tokens.json", t)
        self.assertIn("typography.<lang>[_half].min_pt", t)

    def test_report_figure_ownership_is_data_layer_only(self):
        t = text("skills/0Start-mathmodel/SKILL.md")
        self.assertIn("只交数据层", t)
        self.assertNotIn("负责生成所有依赖计算结果或实验输出的数据图", t)
        self.assertIn("数据图的唯一渲染者", t)

    def test_figure_gate_data_layer_goes_to_code(self):
        t = text("skills/0Start-mathmodel/SKILL.md")
        self.assertIn("数据层 `[lock:data]` 由驱动直接回 4Coding-and-computation", t)

    def test_gate_list_is_current(self):
        t = text("skills/_references/stage_discipline.md")
        self.assertIn("（③⑤⑧⑩⑪⑫⑮）", t)
        self.assertNotIn("（③⑤⑦⑧⑩⑪⑫⑮）", t)

    def test_verification_is_read_only_and_runs_before_demo_only(self):
        t = text("skills/15Verification/SKILL.md")
        self.assertIn("其后只有一段", t)
        self.assertNotIn("其后还有三段", t)
        self.assertIn("检查（发现问题只记录，不修改论文）", t)
        self.assertNotIn("编译用 xelatex 跑两遍", t)

    def test_demo_3d_screenshot_has_exemption_and_correct_name(self):
        t = text("skills/16Web-demo/SKILL.md")
        self.assertIn("若本页有三维主视图", t)
        self.assertIn("shot_1_default.png", t)
        self.assertNotIn("shot_default.png", t)

    def test_route_d_does_not_use_geogebra(self):
        for rel in ("skills/7Route-diagram/SKILL.md",
                    "skills/7Route-diagram/references/physical-3d.md",
                    "docs/GEOMETRY.md"):
            self.assertNotIn("GeoGebra", text(rel), rel)

    def test_writing_has_no_redundant_symbol_intro_or_arabic_assumption(self):
        self.assertNotIn("全表约定", text("skills/9Paper-writing/SKILL.md"))
        tmpl = text("skills/9Paper-writing/templates/zh/cumcm-latex/sections/3_assumptions.tex")
        self.assertNotIn("假设 N", tmpl)
        self.assertIn("假设\\chinese{enumi}", tmpl)

    def test_ai_usage_pdf_is_not_scored(self):
        # 只删“AI 使用说明/声明真实性”的评分；AI 痕迹、内容人工核验、数据真实性保留。
        official = text("skills/12Rubric-final/references/rubric_official.md")
        self.assertNotIn("AI使用说明", official)
        redline = text("skills/12Rubric-final/references/rubric_redline.md")
        self.assertNotIn("AI声明真实性", redline)
        self.assertIn("6 维 25 条红线", redline)
        skill = text("skills/12Rubric-final/SKILL.md")
        self.assertNotIn("AI 声明真实性", skill)
        self.assertIn("25 条", skill)
        self.assertNotIn("AI声明真实性", text("docs/CONTENT_QUALITY.md"))

    def test_word_version_is_not_promised(self):
        t = text("docs/WORKFLOW_RELIABILITY.md")
        self.assertNotIn("Word 仍为可选导出", t)
        self.assertIn("不产出 Word/docx", t)

    def test_abstract_is_judged_by_fill_not_600_chars(self):
        t = text("skills/12Rubric-final/references/precedence.md")
        self.assertNotIn("<600 字", t)
        self.assertIn("版心填充率 < hard", t)

    def test_parentheses_allow_four_categories(self):
        t = text("skills/9Paper-writing/SKILL.md")
        self.assertIn("数字/误差、附录引用、单位或首次定义", t)

    def test_caption_rule_is_short_noun_phrase(self):
        t = text("skills/12Rubric-final/SKILL.md")
        self.assertNotIn("图表标题是否有洞察", t)
        self.assertIn("图表标题是否点明对象/对比", t)

    def test_source_code_goes_to_manifest_not_paper_appendix(self):
        """R15（2026-10-20）：评分标「核心代码放附录」与 `CUMCM_2026_REQUIREMENTS.md:32` 冲突。

        源码以散装 `.py` 进提交清单，附录只放补充推导/数据/图表/清单；
        「无代码附录→⚠️」必须消失，否则 ⑫ 会把合规稿判成缺陷。
        """
        official = text("skills/12Rubric-final/references/rubric_official.md")
        precedence = text("skills/12Rubric-final/references/precedence.md")
        # 正对照：新口径确实写进了两份文件（路径/编码写错时不会静默变绿）
        self.assertIn("散装 `.py`", official)
        self.assertIn("R15", precedence)
        self.assertIn("散装 `.py`", precedence)
        for stale in ("核心代码是否放在附录中", "无代码附录", "附录放核心代码",
                      "附录是否包含核心代码"):
            self.assertNotIn(stale, official, f"R15 旧口径回流：{stale}")

    def test_body_pdf_composition_matches_page_quota(self):
        """正文 = 一～七（29 页），不是整本 PDF；旧句「31 页正文」与 224–227 自相矛盾。"""
        t = text("skills/14Layout-and-format/SKILL.md")
        # 正对照：同一文件里的计页口径仍在
        self.assertIn("摘要 + 正文（一～七）合计 ≤30 页", t)
        self.assertIn("摘要 1 页 + 正文（一～七）29 页", t)
        self.assertNotIn("31 页正文", t)          # 反向对照：改回旧句即失败

    def test_roadmap_reference_templates_are_packaged(self):
        """flow1/flow2 必须在项目资产里，且 route 文档明确优先级。"""
        base = PROJECT / "skills/7Route-diagram/assets/roadmap_templates"
        for name in ("flow1.png", "flow2.png"):
            self.assertTrue((base / name).is_file(), name)
        self.assertTrue((PROJECT / "skills/7Route-diagram/scripts/flow1_roadmap.py").is_file())
        t = text("skills/7Route-diagram/references/route-diagram.md")
        self.assertIn("flow1.png", t)
        self.assertIn("flow2.png", t)
        self.assertIn("优先按 flow1", t)

    def test_plate_figure_is_wired_into_stage7(self):
        """Main figures must use the Nature-style plate skill, not only charts."""
        t = text("skills/7Route-diagram/SKILL.md")
        self.assertIn("plate-figure", t)
        self.assertIn("figures/plate_q1.py", t)
        self.assertIn("figures/plate_q4.py", t)
        self.assertTrue((PROJECT / "skills/plate-figure/SKILL.md").is_file())
        self.assertTrue((PROJECT / "skills/plate-figure/assets/plate_common.py").is_file())
        for name in ("plate_q1_schematic.py", "plate_q2_surface.py",
                     "plate_q3_results.py", "plate_q4_crosssections.py"):
            self.assertTrue((PROJECT / "skills/plate-figure/templates" / name).is_file(), name)
        self.assertIn("plate", text("skills/4Coding-and-computation/SKILL.md"))

    def test_reference_images_are_vendored_inside_the_project(self):
        """Skills must not depend on reference images outside the repo.

        The user deletes external reference folders between runs.  Style
        references must live under ``skills/*/assets/``; a hard-coded
        ``...Downloads/test/...`` path is a broken skill waiting to happen.
        """
        import re
        offenders = []
        pattern = re.compile(r"[A-Za-z]:[\\/][^\s`\"']*Downloads[\\/]test")
        for path in (PROJECT / "skills").rglob("*.md"):
            body = path.read_text(encoding="utf-8", errors="replace")
            if pattern.search(body):
                offenders.append(str(path.relative_to(PROJECT)))
        self.assertEqual(offenders, [], f"仍引用项目外参考图：{offenders}")
        for name in ("composite_1.png", "composite_2.png", "composite_3.png"):
            self.assertTrue((PROJECT / "skills/plate-figure/assets/references" / name).is_file(),
                            name)
        for name in ("flow1.png", "flow2.png"):
            self.assertTrue((PROJECT / "skills/7Route-diagram/assets/roadmap_templates"
                             / name).is_file(), name)

    def test_figure_selection_is_claim_driven_not_quota_driven(self):
        """旧 quota 不许回流；候选检查器必须存在。"""
        import json
        cfg = json.loads(text("config/visualization.json"))
        cm = cfg["chart_mix"]
        self.assertNotIn("require_one_non_line_per_question", cm)
        self.assertNotIn("min_data_figures_per_question", cm)
        self.assertEqual(cm["selection"]["mode"], "claim_driven")
        self.assertTrue((PROJECT / "skills/figure-studio/scripts/check_selection.py").is_file())
        schema = json.loads(text("skills/figure-studio/assets/figure-brief.schema.json"))
        self.assertEqual(schema["properties"]["candidates"]["minItems"], 2)
        for q in ("Q1", "Q2", "Q3", "Q4"):
            self.assertIn("stroke", cfg["question_palette"][q])


if __name__ == "__main__":
    unittest.main()
