# -*- coding: utf-8 -*-
"""Reports / 图 侧栏：按 mtime 倒序 + 报告标生成阶段。

用户 2026-10-20：最新报告放最上；报告后面标阶段（如 WRITING_PLAN.md ⑨ 论文撰写）；
图不用标阶段（图都由 ⑦ 生成）。这里钉住服务端排序/映射与前端渲染钩子。
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "regression"))

from test_workflow import load_server  # noqa: E402


class FileListTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "reports").mkdir()
        (self.root / "figures").mkdir()
        self.s = load_server(self.root)

    def touch(self, rel, mtime):
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("# x\n", encoding="utf-8")
        os.utime(p, (mtime, mtime))
        return p

    def test_reports_are_stage_order_desc_and_carry_stage(self):
        # mtime 故意与阶段顺序相反：排序必须按阶段号，而不是文件时间。
        self.touch("reports/ANALYSIS_MODELING_REPORT.md", 9000)
        self.touch("reports/FIGURE_PLAN.md", 8000)
        self.touch("reports/WRITING_PLAN.md", 7000)
        self.touch("reports/VERIFY_REPORT.md", 2000)
        self.touch("reports/DEMO_REPORT.md", 1000)
        self.touch("reports/HIL_DECISION.md", 9500)
        files = self.s._files_payload("reports")["files"]
        names = [f["name"] for f in files]
        self.assertEqual(names, [
            "reports/VERIFY_REPORT.md",               # 验收置顶
            "reports/DEMO_REPORT.md",                 # ⑯
            "reports/WRITING_PLAN.md",                # ⑨
            "reports/FIGURE_PLAN.md",                 # ④
            "reports/ANALYSIS_MODELING_REPORT.md",    # ②
            "reports/HIL_DECISION.md",                # 无阶段，排最后
        ])
        by = {f["name"]: f.get("stage") for f in files}
        self.assertEqual(by["reports/DEMO_REPORT.md"], "demo")
        self.assertEqual(by["reports/VERIFY_REPORT.md"], "verify")
        self.assertEqual(by["reports/WRITING_PLAN.md"], "write")
        self.assertEqual(by["reports/FIGURE_PLAN.md"], "code")
        self.assertEqual(by["reports/ANALYSIS_MODELING_REPORT.md"], "analysis")
        self.assertIsNone(by["reports/HIL_DECISION.md"])
        hil = next(f for f in files if f["name"] == "reports/HIL_DECISION.md")
        self.assertEqual(hil.get("stage_label"), "人工决策")

    def test_figures_are_newest_first_without_stage(self):
        self.touch("figures/fig2_old.png", 1000)
        self.touch("figures/fig10_new.png", 9000)
        files = self.s._files_payload("fig")["files"]
        self.assertEqual([f["name"] for f in files],
                         ["figures/fig10_new.png", "figures/fig2_old.png"])
        self.assertTrue(all("stage" not in f for f in files))

    def test_report_paragraphs_are_compact(self):
        html = (PROJECT / "lib/web/static/index.html").read_text(encoding="utf-8")
        self.assertIn(".markdown p{margin:0 0 3px}", html)
        self.assertIn(".markdown{white-space:normal;font-family:inherit;font-size:14px;line-height:1.55",
                      html)
        self.assertIn("#view.markdown{white-space:normal;line-height:1.55", html,
                      "ID 选择器会压过 .markdown，必须显式复位 white-space")
        self.assertIn("font-size:14px", html, "报告页不能被 #view 的 13px 压住")
        self.assertNotIn("line-height:1.95", html,
                         "编辑主题的报告行高应已收紧，避免每两句话之间空太大")

    def test_nested_inline_tokens_are_resolved_and_sidebar_clears(self):
        html = (PROJECT / "lib/web/static/index.html").read_text(encoding="utf-8")
        self.assertIn("mdInline(txt,tok)", html,
                      "链接文字必须走行内渲染，并共享外层 token")
        self.assertIn("while(str!==prev)", html,
                      "外层 token 替换后必须继续解析内层 token")
        self.assertIn("renderSidebar();   // 侧栏的「图」组与计数也要同步", html)
        self.assertIn("(?![A-Za-z0-9_])", html, "百分数单位不能用 \\b 收尾")

    def test_stage_row_keeps_status_on_one_line(self):
        """返修行同时有 📝 徽章 + 状态 + 计时章，右栏不许被挤到第二行。

        蓝图/像素主题的徽章带框，比深色主题更宽；旧 290px 左栏在
        「建模评审门禁」+ 徽章 + 计时章这类组合下会把右栏挤换行。
        """
        html = (PROJECT / "lib/web/static/index.html").read_text(encoding="utf-8")
        self.assertIn("grid-template-columns:300px 1fr", html,
                      "阶段进度左栏要比旧 290px 宽一点")
        self.assertIn(".stage .sname{flex:1 1 auto;min-width:0;overflow:hidden;"
                      "text-overflow:ellipsis;white-space:nowrap}", html)
        self.assertIn(".stage .dotline > span:last-child{flex:0 0 auto;white-space:nowrap}",
                      html)
        self.assertIn('<span class="sname" title=', html, "阶段名必须包在可收缩的 .sname 里")

    def test_report_and_figure_tabs_scroll_inside_view(self):
        """报告/图片页签必须像运行日志一样在 #view 内滚动，不能把整页撑长。

        实测根因：section 作为 grid/flex 容器默认 min-height:auto，报告的长内容
        会把 section 撑出 main 的固定高度，body 变成 28000px 的可滚长页。
        """
        html = (PROJECT / "lib/web/static/index.html").read_text(encoding="utf-8")
        self.assertIn("section{display:flex;flex-direction:column;min-width:0;min-height:0}",
                      html, "section 少了 min-height:0，报告/图片会把网页撑长")
        self.assertIn("#view{flex:1;overflow:auto;", html)

    def test_frontend_renders_stage_badge_and_time_sort(self):
        html = (PROJECT / "lib/web/static/index.html").read_text(encoding="utf-8")
        for token in ("sortByMtime", "filestage", "--stage:", "var(--stage",
                      "f.stage", "STAGE_NAME[f.stage]", "file withstage"):
            self.assertIn(token, html, token)
        self.assertNotIn("fileidx", html, "报告行不再显示时间序序号")
        self.assertNotIn("circledNo", html, "报告行不再显示时间序序号")
        self.assertIn("filesList=reps", html, "报告顺序必须用服务端的阶段倒序")
        self.assertNotIn("filesList=sortByMtime(reps)", html,
                         "前端不能把报告按 mtime 重排，否则阶段顺序失效")
        self.assertNotIn("function figNo", html,
                         "图已改为按 mtime 倒序，旧的 figN 排序函数不该再留着")


if __name__ == "__main__":
    unittest.main()
