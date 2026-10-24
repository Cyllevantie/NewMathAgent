# -*- coding: utf-8 -*-
"""Figure-level policy tests: KPI row, duplicate 3D, line budget, flow wiring.

These are the failure modes that per-figure checks missed in the 2026-10 run:

* a 4-item KPI block laid out as 2x2 even though the block was wide enough
  for one row (``fig_q4_plate``);
* the same D(C,T) surface rendered twice — as plate hero and as ``q2_props``;
* a support set where almost every figure was a family of line profiles;
* a route tree whose Q3 branch had a "是" label but no incoming arrow.

The tests build tiny temporary workspaces; they do not read or rewrite the
current run's figures.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))
sys.path.insert(0, str(PROJECT / "skills" / "plate-figure" / "scripts"))
sys.path.insert(0, str(PROJECT / "skills" / "plate-figure" / "assets"))
sys.path.insert(0, str(PROJECT / "skills" / "figure-studio" / "scripts"))
sys.path.insert(0, str(PROJECT / "skills" / "7Route-diagram" / "scripts"))

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

import check_figure_mix  # noqa: E402
import check_roadmap_design  # noqa: E402
import check_plate  # noqa: E402
import check_selection  # noqa: E402
import plate_common as P  # noqa: E402
import studio  # noqa: E402


class KpiOneRowTests(unittest.TestCase):
    def test_a_wide_block_expands_four_tiles_to_one_row(self):
        fig = P.canvas(210, 150)
        P.kpi_block(fig, 5, 8, 94, 30,
                    [("51.2 h", "烘干时间"), ("1.200 cm", "半径"),
                     ("130.5 h", "固定 R 对照"), ("-11.0%", "干物质漂移")],
                    cols=2)
        values = [t for t in fig.axes[0].texts[0::2]]
        ys = {round(t.get_position()[1], 4) for t in values}
        self.assertEqual(len(ys), 1, f"KPI 应排成一行，实际 y={ys}")
        plt.close(fig)

    def test_a_full_width_block_keeps_a_compact_pitch(self):
        fig = P.canvas(210, 150)
        P.kpi_block(fig, 5, 12, 200, 22,
                    [("51.2 h", "烘干时间"), ("1.200 cm", "半径"),
                     ("130.5 h", "固定 R 对照"), ("-11.0%", "漂移")],
                    cols=4)
        xs = [t.get_position()[0] for t in fig.axes[0].texts[0::2]]
        self.assertLessEqual(max(xs) - min(xs), 3 * P.KPI_MAX_TILE_MM + 1e-6,
                             "KPI 不应横跨整张图；保持 Q1 那种紧凑间距")
        plt.close(fig)

    def test_check_plate_rejects_rows_that_would_fit_one_line(self):
        src = ('P.kpi_block(fig, 5, 8, 94, 30,\n'
               '  [("a", "A"), ("b", "B"), ("c", "C"), ("d", "D")],\n'
               '  cols=2)\n')
        issues = check_plate._kpi_layout_issues(src, "fig_q4_plate")
        self.assertTrue(issues, "宽块里的 2×2 KPI 没有被判失败")
        self.assertIn("一行", issues[0])

    def test_check_plate_rejects_a_kpi_row_stretched_across_the_plate(self):
        src = ('P.kpi_block(fig, 5, 12, 200, 22,\n'
               '  [("a", "A"), ("b", "B"), ("c", "C"), ("d", "D")],\n'
               '  cols=4)\n')
        issues = check_plate._kpi_layout_issues(src, "fig_q4_plate")
        self.assertTrue(any("跨度过大" in x for x in issues), issues)

    def test_check_plate_accepts_a_narrow_sidebar(self):
        src = ('P.kpi_block(fig, 157, 78, 48, 50,\n'
               '  [("a", "A"), ("b", "B"), ("c", "C"), ("d", "D")],\n'
               '  cols=1)\n')
        self.assertEqual(check_plate._kpi_layout_issues(src, "fig_q2_plate"), [])


class LanguageDecouplingTests(unittest.TestCase):
    def test_check_plate_reads_the_template_language(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "reports").mkdir()
            (root / "reports" / "FIGURE_CONTEXT.json").write_text(
                json.dumps({"language": "en", "font": "Arial"}), encoding="utf-8")
            self.assertEqual(check_plate._language(root), "en")

    def test_plate_setup_uses_the_context_font_instead_of_a_hard_coded_one(self):
        old_root = P.ROOT
        old_rc = matplotlib.rcParams["font.sans-serif"]
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "reports").mkdir()
            (root / "reports" / "FIGURE_CONTEXT.json").write_text(
                json.dumps({"language": "en", "font": "Arial"}), encoding="utf-8")
            P.ROOT = root
            try:
                P.setup()
                self.assertEqual(matplotlib.rcParams["font.sans-serif"][0], "Arial")
            finally:
                P.ROOT = old_root
                matplotlib.rcParams["font.sans-serif"] = old_rc


class _Workspace(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "config").mkdir()
        (self.root / "figures" / "spec").mkdir(parents=True)
        (self.root / "figures" / "data").mkdir(parents=True)
        (self.root / "figures" / "choice").mkdir()
        (self.root / "reports" / "figure_briefs").mkdir(parents=True)
        self._config(max_line=2)

    def _config(self, max_line=6, min_line=0, max_field=99, max_dist=99, max_bar=99,
                max_field_maps=99, max_heatmaps=99, min_annotated=0):
        # Focused tests disable the other budgets unless they are the subject.
        (self.root / "config" / "visualization.json").write_text(json.dumps({
            "chart_mix": {
                "selection": {"min_candidates_per_figure": 2},
                "line_budget": {"max_line_panels": max_line,
                                "min_line_panels": min_line,
                                "max_field_panels": max_field,
                                "max_distribution_panels": max_dist,
                                "max_bar_panels": max_bar,
                                "max_field_maps": max_field_maps,
                                "max_heatmaps": max_heatmaps,
                                "min_annotated_heatmaps": min_annotated},
            }
        }, ensure_ascii=False), encoding="utf-8")

    def _spec(self, fid, recipe, data="figures/data/x.npz"):
        (self.root / "figures" / "spec" / f"{fid}.json").write_text(json.dumps({
            "figure_id": fid,
            "data": {"path": data},
            "panels": [{"id": "a", "recipe": recipe,
                        "fields": ["x", "y", "z"]}],
        }, ensure_ascii=False), encoding="utf-8")

    def _manifest(self, ids, artifacts=True):
        figures = {fid: {"artifacts": [f"figures/{fid}.png"] if artifacts else []}
                   for fid in ids}
        (self.root / "figures" / "manifest.json").write_text(
            json.dumps({"figures": figures}, ensure_ascii=False), encoding="utf-8")


class FigureMixTests(_Workspace):
    def _plate(self, bundle="q2_props.npz", three_d=True):
        body = f'import numpy as np\nnp.load("figures/data/{bundle}")\n'
        if three_d:
            body += 'ax.plot_surface(x, y, z)\n'
        (self.root / "figures" / "plate_q2.py").write_text(body, encoding="utf-8")

    def test_a_surface_owned_by_a_plate_is_reported_when_still_registered(self):
        self._plate()
        self._spec("q2_props", "surface3d", "figures/data/q2_props.npz")
        self._manifest(["q2_props"])
        result = check_figure_mix.check(self.root)
        self.assertEqual(result["status"], "FAIL")
        self.assertTrue(any("同源同图型" in x for x in result["issues"]))

    def test_an_unregistered_duplicate_is_only_skipped(self):
        self._plate()
        self._spec("q2_props", "surface3d", "figures/data/q2_props.npz")
        self._manifest([])
        result = check_figure_mix.check(self.root)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(check_figure_mix.duplicate_ids(self.root), ["q2_props"])

    def test_an_old_duplicate_png_must_be_deleted_too(self):
        self._plate()
        self._spec("q2_props", "surface3d", "figures/data/q2_props.npz")
        self._manifest([])
        (self.root / "figures" / "q2_props.png").write_bytes(b"old")
        result = check_figure_mix.check(self.root)
        self.assertEqual(result["status"], "FAIL")
        self.assertIn("仍有旧产物", result["issues"][0])

    def test_excluded_support_figures_still_count_in_the_visual_mix(self):
        self._config(min_line=0, max_field=0, max_dist=0, max_bar=0)
        self._spec("support", "field_contour")
        (self.root / "figures" / "manifest.json").write_text(json.dumps({
            "figures": {"support": {"included": False,
                                    "artifacts": ["figures/support.png"]}}
        }, ensure_ascii=False), encoding="utf-8")
        result = check_figure_mix.check(self.root)
        self.assertEqual(result["status"], "FAIL")
        self.assertIn("场图+热力图", " ".join(result["issues"]))

    def test_balanced_budget_flags_too_few_lines_and_too_many_fields(self):
        self._config(max_line=6, min_line=2, max_field=1, max_dist=1)
        for fid in ("f1", "f2"):
            self._spec(fid, "field_contour")
        for fid in ("d1", "d2"):
            self._spec(fid, "field_raincloud")
        self._manifest(["f1", "f2", "d1", "d2"])
        result = check_figure_mix.check(self.root)
        text = " ".join(result["issues"])
        self.assertIn("低于下限", text)
        self.assertIn("场图+热力图", text)
        self.assertIn("雨云/分布面板", text)

    def test_a_lingering_combined_geometry_figure_is_reported(self):
        for name in ("fig_geometry_shared.png", "fig_geometry_q4.png",
                     "fig_geometry_3d.png"):
            (self.root / "figures" / name).write_bytes(b"x")
        self._manifest(["fig_geometry_3d"])
        result = check_figure_mix.check(self.root)
        self.assertEqual(result["status"], "FAIL")
        self.assertIn("旧几何图仍在", result["issues"][0])
        (self.root / "figures" / "fig_geometry_3d.png").unlink()
        self._manifest([])
        self.assertEqual(check_figure_mix.check(self.root)["status"], "PASS")

    def test_line_budget_counts_panels_not_figures(self):
        for fid in ("a", "b", "c"):
            self._spec(fid, "profiles")
        self._manifest(["a", "b", "c"])
        result = check_figure_mix.check(self.root)
        self.assertEqual(result["status"], "FAIL")
        self.assertIn("折线面板共 3 个", result["issues"][0])
        self._config(max_line=3)
        self.assertEqual(check_figure_mix.check(self.root)["status"], "PASS")

    def test_field_raincloud_is_not_a_line_panel(self):
        self._spec("q3_dryfront", "field_raincloud")
        self._manifest(["q3_dryfront"])
        result = check_figure_mix.check(self.root)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["line_panels"], 0)

    def test_an_all_field_paper_figure_needs_a_distribution_or_comparison_panel(self):
        (self.root / "figures" / "spec" / "q3.json").write_text(json.dumps({
            "figure_id": "q3", "data": {"path": "figures/data/q3.npz"},
            "panels": [{"id": "a", "recipe": "field_contour", "fields": ["x", "y", "z"]},
                       {"id": "b", "recipe": "field_contour", "fields": ["x", "y", "z"]}],
        }, ensure_ascii=False), encoding="utf-8")
        self._manifest(["q3"])
        result = check_figure_mix.check(self.root)
        self.assertEqual(result["status"], "FAIL")
        self.assertIn("全是场图", result["issues"][0])


class SelectionTests(_Workspace):
    def _brief(self, fid, recipes):
        (self.root / "reports" / "figure_briefs" / f"{fid}.json").write_text(
            json.dumps({"figure_id": fid,
                        "candidates": [{"recipe": r} for r in recipes]},
                       ensure_ascii=False), encoding="utf-8")

    def _choice(self, fid, selected, candidates=()):
        payload = {"figure_id": fid, "selected": selected}
        if candidates:
            payload["candidates"] = [{"recipe": r} for r in candidates]
        (self.root / "figures" / "choice" / f"{fid}.json").write_text(
            json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    def test_a_line_winner_needs_a_non_line_candidate(self):
        self._spec("h", "profiles")
        self._brief("h", ["profiles", "field_waterfall"])
        self._choice("h", "profiles")
        problems = check_selection.check(self.root)
        self.assertTrue(any("没有非折线编码" in p for p in problems), problems)

    def test_adding_a_raincloud_candidate_clears_it(self):
        self._spec("h", "profiles")
        self._brief("h", ["profiles", "raincloud"])
        self._choice("h", "profiles")
        self.assertEqual(check_selection.check(self.root), [])

    def test_the_renderer_may_add_a_candidate_the_brief_did_not_foresee(self):
        self._spec("h", "field_raincloud")
        self._brief("h", ["profiles", "field_waterfall"])
        self._choice("h", "field_raincloud", ["profiles", "field_raincloud"])
        self.assertEqual(check_selection.check(self.root), [])


class RoadmapDesignTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "figures").mkdir()
        (self.root / "reports").mkdir()
        (self.root / "skills" / "7Route-diagram" / "scripts").mkdir(parents=True)

    def _script(self):
        names = ["q1h", "q1b2", "q1b3", "q2h", "q3h", "q4h", "d1", "d2", "d3", "c1"]
        body = chr(10).join(f'V("{n}", 0, 0, 1, 1, "", "")' for n in names)
        (self.root / "skills" / "7Route-diagram" / "scripts" / "flow1_roadmap.py").write_text(
            body, encoding="utf-8")

    def _drawio(self, ids):
        cells = "".join(
            f'<mxCell id="{i}" value="{i}" vertex="1"><mxGeometry x="0" y="0" width="1" height="1"/></mxCell>'
            for i in ids)
        (self.root / "figures" / "fig_roadmap.drawio").write_text(
            f'<mxfile><diagram><mxGraphModel><root><mxCell id="0"/>{cells}</root>'
            f'</mxGraphModel></diagram></mxfile>', encoding="utf-8")

    def test_reusing_the_reference_skeleton_is_rejected(self):
        self._script()
        self._drawio(["q1h", "q1b2", "q1b3", "q2h", "q3h", "q4h", "d1", "d2", "d3", "c1"])
        (self.root / "reports" / "ROADMAP_DESIGN.md").write_text("design", encoding="utf-8")
        issues = check_roadmap_design.check(self.root)
        self.assertTrue(any("参考实现的节点骨架" in x for x in issues), issues)

    def test_a_different_layout_passes_when_the_design_note_exists(self):
        self._script()
        self._drawio(["b1", "q1_head", "q2_head", "q3_head", "q4_head", "x1", "x2"])
        (self.root / "reports" / "ROADMAP_DESIGN.md").write_text("design", encoding="utf-8")
        self.assertEqual(check_roadmap_design.check(self.root), [])

    def test_a_missing_design_note_is_reported(self):
        self._script()
        self._drawio(["b1", "q1_head"])
        issues = check_roadmap_design.check(self.root)
        self.assertTrue(any("ROADMAP_DESIGN.md" in x for x in issues), issues)


class FlowWiringTests(unittest.TestCase):
    SCRIPT = PROJECT / "skills" / "paper-diagram" / "scripts" / "check_layout.py"

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def _xml(self, *, start_edge=True, branch_edge=True, diamond_exits=2):
        cells = [
            '<mxCell id="a" value="开始" style="rounded=1;fillColor=#eee;" vertex="1">'
            '<mxGeometry x="120" y="20" width="80" height="24" as="geometry"/></mxCell>',
            '<mxCell id="b" value="处理" style="rounded=1;fillColor=#eee;" vertex="1">'
            '<mxGeometry x="120" y="100" width="100" height="32" as="geometry"/></mxCell>',
            '<mxCell id="c" value="校核" style="rounded=1;fillColor=#eee;" vertex="1">'
            '<mxGeometry x="120" y="180" width="100" height="24" as="geometry"/></mxCell>',
            '<mxCell id="d" value="判断？" style="rhombus;fillColor=#fff;" vertex="1">'
            '<mxGeometry x="120" y="240" width="100" height="44" as="geometry"/></mxCell>',
            '<mxCell id="r1" value="结果1" style="rounded=1;fillColor=#eee;" vertex="1">'
            '<mxGeometry x="80" y="320" width="80" height="24" as="geometry"/></mxCell>',
            '<mxCell id="r2" value="结果2" style="rounded=1;fillColor=#eee;" vertex="1">'
            '<mxGeometry x="180" y="320" width="80" height="24" as="geometry"/></mxCell>',
        ]
        edges = []
        if start_edge:
            edges.append('<mxCell id="e1" style="edgeStyle=orthogonalEdgeStyle;" edge="1">'
                         '<mxGeometry><mxPoint x="160" y="45" as="sourcePoint"/>'
                         '<mxPoint x="170" y="99" as="targetPoint"/></mxGeometry></mxCell>')
        edges.append('<mxCell id="e2" style="edgeStyle=orthogonalEdgeStyle;" edge="1">'
                     '<mxGeometry><mxPoint x="170" y="133" as="sourcePoint"/>'
                     '<mxPoint x="170" y="179" as="targetPoint"/></mxGeometry></mxCell>')
        if branch_edge:
            edges.append('<mxCell id="e3" style="edgeStyle=orthogonalEdgeStyle;" edge="1">'
                         '<mxGeometry><mxPoint x="170" y="205" as="sourcePoint"/>'
                         '<mxPoint x="170" y="239" as="targetPoint"/></mxGeometry></mxCell>')
        for k in range(diamond_exits):
            edges.append(f'<mxCell id="d{k}" style="edgeStyle=orthogonalEdgeStyle;" edge="1">'
                         f'<mxGeometry><mxPoint x="{120 + k * 100}" y="285" as="sourcePoint"/>'
                         f'<mxPoint x="{120 + k * 100}" y="319" as="targetPoint"/></mxGeometry></mxCell>')
        return ('<mxfile><diagram><mxGraphModel pageWidth="400" pageHeight="360"><root>'
                '<mxCell id="0"/><mxCell id="1" parent="0"/>' + "".join(cells + edges) +
                '</root></mxGraphModel></diagram></mxfile>')

    def _run(self, xml):
        p = self.root / "flow.drawio"
        p.write_text(xml, encoding="utf-8")
        proc = subprocess.run([sys.executable, "-X", "utf8", str(self.SCRIPT), str(p), "--flow"],
                              capture_output=True, text=True, encoding="utf-8", errors="replace")
        return proc.returncode, proc.stdout + proc.stderr

    def test_a_complete_chain_passes(self):
        code, out = self._run(self._xml())
        self.assertEqual(code, 0, out)

    def test_english_start_and_result_labels_are_recognized(self):
        xml = (self._xml().replace('value="开始"', 'value="Start"')
               .replace('value="结果1"', 'value="Result 1"')
               .replace('value="结果2"', 'value="Result 2"'))
        code, out = self._run(xml)
        self.assertEqual(code, 0, out)

    def test_a_missing_start_arrow_is_reported(self):
        code, out = self._run(self._xml(start_edge=False))
        self.assertNotEqual(code, 0, out)
        self.assertIn("没有出口箭头", out)
        self.assertIn("没有入口箭头", out)

    def test_a_branch_without_an_incoming_arrow_is_reported(self):
        code, out = self._run(self._xml(branch_edge=False))
        self.assertNotEqual(code, 0, out)
        self.assertIn("d: 支链/节点没有入口箭头", out)

    def test_a_diamond_with_one_exit_is_reported(self):
        code, out = self._run(self._xml(diamond_exits=1))
        self.assertNotEqual(code, 0, out)
        self.assertIn("判断菱形只有 1 个出口", out)

    def _bus_xml(self, bus_y=112):
        """Four input cards inside a dashed band, joined by one horizontal bus."""
        cells = [
            '<mxCell id="fr" value="" style="rounded=1;dashed=1;fillColor=none;" vertex="1">'
            '<mxGeometry x="10" y="55" width="380" height="95" as="geometry"/></mxCell>',
        ]
        for k, x in enumerate((30, 120, 210, 300)):
            cells.append(f'<mxCell id="c{k}" value="卡{k}" style="rounded=0;fillColor=#eef;" vertex="1">'
                         f'<mxGeometry x="{x}" y="70" width="70" height="30" as="geometry"/></mxCell>')
        edges = ['<mxCell id="bus" style="edgeStyle=orthogonalEdgeStyle;endArrow=none;" edge="1">'
                 f'<mxGeometry><mxPoint x="65" y="{bus_y}" as="sourcePoint"/>'
                 f'<mxPoint x="335" y="{bus_y}" as="targetPoint"/></mxGeometry></mxCell>']
        for k, xc in enumerate((65, 155, 245, 335)):
            edges.append(f'<mxCell id="t{k}" style="edgeStyle=orthogonalEdgeStyle;endArrow=none;" edge="1">'
                         f'<mxGeometry><mxPoint x="{xc}" y="101" as="sourcePoint"/>'
                         f'<mxPoint x="{xc}" y="{bus_y - 1}" as="targetPoint"/></mxGeometry></mxCell>')
        return ('<mxfile><diagram><mxGraphModel pageWidth="400" pageHeight="360"><root>'
                '<mxCell id="0"/><mxCell id="1" parent="0"/>' + "".join(cells + edges) +
                '</root></mxGraphModel></diagram></mxfile>')

    def test_an_input_bus_flush_with_the_cards_is_reported(self):
        code, out = self._run(self._bus_xml(bus_y=102))
        self.assertNotEqual(code, 0, out)
        self.assertIn("输入母线离卡片底边", out)

    def test_a_brace_with_visible_taps_passes(self):
        code, out = self._run(self._bus_xml(bus_y=112))
        self.assertEqual(code, 0, out)

    def test_crossing_a_dashed_container_is_not_a_failure(self):
        """The dashed frame is a grouping edge, not a wall (⑦ used to split
        arrows at it and open white gaps in the border — both looked broken)."""
        xml = ('<mxfile><diagram><mxGraphModel pageWidth="400" pageHeight="360"><root>'
               '<mxCell id="0"/><mxCell id="1" parent="0"/>'
               '<mxCell id="fr" value="" style="rounded=1;dashed=1;fillColor=none;" vertex="1">'
               '<mxGeometry x="60" y="100" width="200" height="100" as="geometry"/></mxCell>'
               '<mxCell id="start" value="开始" style="rounded=1;fillColor=#eee;" vertex="1">'
               '<mxGeometry x="120" y="20" width="80" height="24" as="geometry"/></mxCell>'
               '<mxCell id="inner" value="模型" style="rounded=1;fillColor=#eee;" vertex="1">'
               '<mxGeometry x="110" y="140" width="100" height="30" as="geometry"/></mxCell>'
               '<mxCell id="res" value="结果" style="rounded=1;fillColor=#eee;" vertex="1">'
               '<mxGeometry x="120" y="260" width="80" height="24" as="geometry"/></mxCell>'
               '<mxCell id="e1" style="edgeStyle=orthogonalEdgeStyle;" edge="1">'
               '<mxGeometry><mxPoint x="160" y="44" as="sourcePoint"/>'
               '<mxPoint x="160" y="139" as="targetPoint"/></mxGeometry></mxCell>'
               '<mxCell id="e2" style="edgeStyle=orthogonalEdgeStyle;" edge="1">'
               '<mxGeometry><mxPoint x="160" y="170" as="sourcePoint"/>'
               '<mxPoint x="160" y="259" as="targetPoint"/></mxGeometry></mxCell>'
               '</root></mxGraphModel></diagram></mxfile>')
        code, out = self._run(xml)
        self.assertEqual(code, 0, out)


class FieldRaincloudSmokeTests(unittest.TestCase):
    def test_field_raincloud_renders_time_groups(self):
        ctx = studio.context(PROJECT)
        x = np.linspace(0, 2, 21)
        t = np.linspace(0, 60, 61)
        z = 2.5 * np.exp(-t[:, None] / 20) + 0.02 * x[None, :]
        fig, ax = plt.subplots(figsize=(5, 3))
        with studio.style(ctx):
            studio.field_raincloud(ax, x, t, z, ctx, group_by="time",
                                   groups=[0, 20, 40, 60],
                                   xlabel="C / (kg/kg)", reference=0.15)
        out = Path(tempfile.mkdtemp()) / "raincloud.png"
        fig.savefig(out, dpi=100)
        plt.close(fig)
        self.assertTrue(out.is_file() and out.stat().st_size > 1000)

    def test_constant_groups_do_not_crash_the_kde(self):
        ctx = studio.context(PROJECT)
        fig, ax = plt.subplots(figsize=(4, 2.5))
        with studio.style(ctx):
            studio.raincloud_groups(ax, {"a": np.full(10, 2.5), "b": np.arange(10)},
                                    ctx, xlabel="C")
        plt.close(fig)

    def test_the_declarative_dispatch_routes_sampled_bars(self):
        ctx = studio.context(PROJECT)
        x = np.linspace(0, 50, 51)
        y = np.exp(-x / 20)
        panel = {
            "id": "a", "recipe": "sampled_bars",
            "fields": ["t", "M"],
            "field_mapping": {"x": "t", "series": ["M"],
                              "series_labels": ["M_s"]},
            "options": {"times": [0, 10, 50], "xlabel": "时间 / h"},
        }
        fig, ax = plt.subplots(figsize=(4, 3))
        with studio.style(ctx):
            studio._render_panel(ax, panel, {"t": x, "M": y}, ctx)
        self.assertEqual(len([p for p in ax.patches if p.get_height() > 0]), 3)
        plt.close(fig)

    def test_sampled_bars_forwards_the_gradient_switch(self):
        """`sampled_bars` 收了 gradient 参数就必须传给 grouped_bars。"""
        ctx = studio.context(PROJECT)
        calls = {}
        original = studio.grouped_bars

        def probe(ax, cats, series, ctx_, **kw):
            calls.update(kw)
            return original(ax, cats, series, ctx_, **kw)

        studio.grouped_bars = probe
        self.addCleanup(lambda: setattr(studio, "grouped_bars", original))
        x = np.linspace(0, 50, 51)
        fig, ax = plt.subplots(figsize=(4, 3))
        with studio.style(ctx):
            studio.sampled_bars(ax, x, {"M": np.exp(-x / 20)}, ctx,
                                times=[0, 25, 50], gradient=False)
        self.assertIs(calls.get("gradient"), False)
        plt.close(fig)

    def test_split_raincloud_draws_the_two_halves_on_opposite_sides(self):
        ctx = studio.context(PROJECT)
        fig, ax = plt.subplots(figsize=(5, 3))
        calls = []
        original = ax.fill_between

        def probe(x, y1, y2, **kw):
            calls.append((float(np.min(y1)), float(np.max(y2))))
            return original(x, y1, y2, **kw)

        ax.fill_between = probe
        with studio.style(ctx):
            studio.split_raincloud(
                ax, {"w": (np.linspace(1, 2, 50), np.linspace(3, 4, 50))},
                ctx, labels=("A", "B"), legend=False)
        self.assertEqual(len(calls), 2, calls)
        # one half must sit above the category line (0), the other below it
        self.assertTrue(any(lo == 0.0 and hi > 0 for lo, hi in calls), calls)
        self.assertTrue(any(lo < 0 and hi == 0.0 for lo, hi in calls), calls)
        plt.close(fig)

    def test_annotated_heatmap_downsamples_and_writes_numbers(self):
        ctx = studio.context(PROJECT)
        rows = np.linspace(0, 2, 40)
        cols = np.linspace(28, 50, 30)
        mat = np.add.outer(rows, cols * 0.01)
        panel = {
            "id": "a", "recipe": "annotated_heatmap",
            "fields": ["C", "T", "D"],
            "field_mapping": {"rows": "C", "columns": "T", "values": "D"},
            "options": {"max_rows": 6, "max_cols": 5},
        }
        fig, ax = plt.subplots(figsize=(5, 4))
        with studio.style(ctx):
            studio._render_panel(ax, panel, {"C": rows, "T": cols, "D": mat}, ctx)
        # 6x5 cells each get a numeric annotation
        self.assertGreaterEqual(len(ax.texts), 30)
        plt.close(fig)

    def test_field_split_raincloud_renders_time_windows(self):
        ctx = studio.context(PROJECT)
        x = np.linspace(0, 2, 21)
        t = np.linspace(0, 3, 61)
        z = 28 + 8 * (t[:, None] / 3) ** 1.5 + 2 * (x[None, :] / 2) ** 2
        panel = {
            "id": "a", "recipe": "field_split_raincloud",
            "fields": ["r", "t", "T"],
            "field_mapping": {"x": "r", "y": "t", "z": "T"},
            "options": {"n_windows": 4, "xlabel": "T / °C",
                        "band_labels": ["中心区", "表面区"]},
        }
        fig, ax = plt.subplots(figsize=(5, 3))
        with studio.style(ctx):
            studio._render_panel(ax, panel, {"r": x, "t": t, "T": z}, ctx)
        self.assertEqual(len(ax.get_yticks()), 4)
        plt.close(fig)

    def test_the_declarative_dispatch_routes_field_raincloud(self):
        ctx = studio.context(PROJECT)
        x = np.linspace(0, 2, 21)
        t = np.linspace(0, 60, 61)
        z = 2.5 * np.exp(-t[:, None] / 20) + 0.02 * x[None, :]
        panel = {
            "id": "a", "recipe": "field_raincloud",
            "fields": ["x", "t", "z"],
            "field_mapping": {"x": "x", "y": "t", "z": "z"},
            "options": {"group_by": "time", "times": [0, 20, 40, 60],
                        "xlabel": "C", "level": 0.15},
        }
        fig, ax = plt.subplots(figsize=(5, 3))
        with studio.style(ctx):
            studio._render_panel(ax, panel, {"x": x, "t": t, "z": z}, ctx)
        self.assertEqual(len(ax.get_yticks()), 4)
        plt.close(fig)


class PanelRuleConsistencyTests(unittest.TestCase):
    """图内字母/虚线穿框这两条规则，提示词、SKILL 与检查器必须同一口径。

    2026-10-23 冲突实例：`check_plate` 把 `(a)` 判 FAIL，而 ⑦ 的提示词还在教
    “面板标识写在每个面板下方 `(a) 短描述`”；`check_layout` 已允许穿容器虚线，
    而 7Route 的复查单还写着“不穿框”。
    """

    def test_server_prompt_does_not_teach_panel_letters(self):
        text = (PROJECT / "lib/web/server.py").read_text(encoding="utf-8")
        self.assertNotIn("(a) 短描述", text)
        self.assertIn("图内不写 a/b/c", text)

    def test_plate_skill_bans_letters(self):
        text = (PROJECT / "skills/plate-figure/SKILL.md").read_text(encoding="utf-8")
        self.assertNotIn("写 `(a) 短描述`", text)
        self.assertIn("不写 a/b/c", text)

    def test_roadmap_checks_allow_crossing_the_dashed_container(self):
        layout = (PROJECT / "skills/paper-diagram/scripts/check_layout.py").read_text(encoding="utf-8")
        self.assertNotIn("连线穿过容器虚线框", layout)
        ref = (PROJECT / "skills/7Route-diagram/references/route-diagram.md").read_text(encoding="utf-8")
        self.assertIn("容器虚线边允许", ref)
        self.assertIn("大括号", ref)


if __name__ == "__main__":
    unittest.main()
