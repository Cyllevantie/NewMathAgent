"""④/⑦ 解耦契约：bundle + spec + figure lock。

These tests pin the boundary that is easy to erode:

- ④ writes the three files; ⑦ reads them and may change presentation only;
- changing a bundle/source *without* re-cutting the lock is `[lock:data]`;
- changing fields/claim/statistics is `[lock:contract]`;
- changing recipe/options/layout is allowed (presentation);
- `save_figure` refuses to render when the lock fails.
"""
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

PROJECT = Path(__file__).resolve().parents[1]
SCRIPTS = PROJECT / "skills/figure-studio/scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import studio
    import figure_lock
    import audit_studio
except ImportError as exc:                       # pragma: no cover
    studio = None
    figure_lock = None
    audit_studio = None
    IMPORT_ERROR = str(exc)
else:
    IMPORT_ERROR = ""


def _issue_kinds(issues):
    return [i["kind"] for i in issues]


@unittest.skipIf(studio is None, f"scientific stack missing: {IMPORT_ERROR}")
class FigureLockTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "config").mkdir()
        shutil.copy2(PROJECT / "config/visualization.json",
                     self.root / "config/visualization.json")
        (self.root / "results").mkdir()
        (self.root / "results/q3.json").write_text('{"ok": true}', encoding="utf-8")
        (self.root / "figures").mkdir()
        (self.root / "figures/make_figures.py").write_text(
            "# owned by 7Route-diagram\nimport studio\n", encoding="utf-8")
        self.ctx = studio.context(self.root)
        self.r = np.linspace(0, 1, 12)
        self.t = np.linspace(0, 5, 8)
        self.C = np.exp(-np.outer(self.t, self.r))
        self._bundle()

    def _bundle(self):
        studio.save_bundle(
            self.root, "q3_demo",
            {"r": self.r, "t": self.t, "C": self.C},
            self.ctx,
            claim="含水率场在 5 h 内向内推进。",
            sources=["results/q3.json"],
            panels=[{
                "id": "a", "recipe": "field_contour",
                "fields": ["r", "t", "C"],
                "field_mapping": {"x": "r", "y": "t", "z": "C"},
                "claim": "含水率随时间向内推进。",
                "options": {"quantity": "moisture", "level": 0.15},
            }],
            statistics={"interval": {"kind": "none", "method": "不适用"},
                        "test": {"kind": "none", "p_values": False},
                        "unit": "确定性模拟", "paired": False},
            width_mm=160, height_mm=90,
            layout={"kind": "single"},
        )

    def _spec_path(self):
        return self.root / "figures/spec/q3_demo.json"

    def _write_spec(self, spec):
        self._spec_path().write_text(json.dumps(spec, ensure_ascii=False, indent=2),
                                     encoding="utf-8")

    def _read_spec(self):
        return json.loads(self._spec_path().read_text(encoding="utf-8"))

    def test_save_bundle_writes_the_three_files_and_verifies(self):
        for rel in ("figures/data/q3_demo.npz", "figures/spec/q3_demo.json",
                    "figures/q3_demo.lock.json"):
            self.assertTrue((self.root / rel).is_file(), rel)
        self.assertEqual(figure_lock.verify(self.root), [])
        lock = json.loads((self.root / "figures/q3_demo.lock.json").read_text(encoding="utf-8"))
        self.assertEqual(lock["owner"], "4Coding-and-computation")
        self.assertEqual(lock["claim"], "含水率场在 5 h 内向内推进。")
        self.assertIn("C", lock["data"]["fields"])
        self.assertEqual(lock["data"]["fields"]["C"]["shape"], [8, 12])
        self.assertIn("results/q3.json", lock["sources"])

    def test_save_bundle_rejects_the_reserved_field_name_file(self):
        with self.assertRaises(ValueError) as caught:
            studio.save_bundle(
                self.root, "bad", {"file": self.r, "C": self.C}, self.ctx,
                claim="测试 claim 足够长。", sources=["results/q3.json"],
                panels=[{"id": "a", "recipe": "field_heatmap",
                         "fields": ["file", "C"],
                         "field_mapping": {"x": "file", "y": "file", "z": "C"},
                         "claim": "测试面板 claim。"}],
                statistics={"interval": {"kind": "none", "method": "不适用"}},
            )
        self.assertIn("file", str(caught.exception))

    def test_save_bundle_rejects_an_unknown_recipe(self):
        with self.assertRaises(ValueError) as caught:
            studio.save_bundle(
                self.root, "bad", {"r": self.r, "t": self.t, "C": self.C}, self.ctx,
                claim="测试 claim 足够长。", sources=["results/q3.json"],
                panels=[{"id": "a", "recipe": "not_a_recipe",
                         "fields": ["r", "t", "C"],
                         "field_mapping": {"x": "r", "y": "t", "z": "C"},
                         "claim": "测试面板 claim。"}],
                statistics={"interval": {"kind": "none", "method": "不适用"}},
            )
        self.assertIn("未知 recipe", str(caught.exception))

    def test_save_bundle_rejects_a_missing_required_field(self):
        with self.assertRaises(ValueError) as caught:
            studio.save_bundle(
                self.root, "bad", {"r": self.r, "t": self.t, "C": self.C}, self.ctx,
                claim="测试 claim 足够长。", sources=["results/q3.json"],
                panels=[{"id": "a", "recipe": "field_contour",
                         "fields": ["r", "t", "C"],
                         "field_mapping": {"x": "r", "y": "t"},
                         "claim": "测试面板 claim。"}],
                statistics={"interval": {"kind": "none", "method": "不适用"}},
            )
        self.assertIn("level", str(caught.exception))

    def test_brief_is_hashed_and_must_match_the_spec(self):
        brief_dir = self.root / "reports/figure_briefs"
        brief_dir.mkdir(parents=True)
        brief = {
            "figure_id": "q3_demo",
            "claim": "含水率场在 5 h 内向内推进。",
            "panels": [{"id": "a", "fields": ["r", "t", "C"],
                        "claim": "含水率随时间向内推进。"}],
            "data": [{"fields": ["r", "t", "C"]}],
        }
        path = brief_dir / "q3_demo.json"
        path.write_text(json.dumps(brief, ensure_ascii=False, indent=2), encoding="utf-8")
        self._bundle()                       # re-cut with the brief present
        lock = json.loads((self.root / "figures/q3_demo.lock.json").read_text(encoding="utf-8"))
        self.assertEqual(lock["brief"]["path"], "reports/figure_briefs/q3_demo.json")
        self.assertEqual(figure_lock.verify(self.root), [])
        brief["claim"] = "含水率场在 1 h 内向内推进。"
        path.write_text(json.dumps(brief, ensure_ascii=False, indent=2), encoding="utf-8")
        issues = figure_lock.verify(self.root)
        self.assertIn("contract", _issue_kinds(issues))
        self.assertTrue(any("FigureBrief" in i["message"] for i in issues))

    def test_an_explicit_brief_with_the_wrong_id_is_rejected(self):
        path = self.root / "reports/figure_briefs/wrong.json"
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps({
            "figure_id": "another_figure",
            "claim": "含水率场在 5 h 内向内推进。",
        }, ensure_ascii=False), encoding="utf-8")
        with self.assertRaises(ValueError) as caught:
            studio.save_bundle(
                self.root, "q3_demo", {"r": self.r, "t": self.t, "C": self.C},
                self.ctx,
                claim="含水率场在 5 h 内向内推进。", sources=["results/q3.json"],
                panels=[{"id": "a", "recipe": "field_contour",
                         "fields": ["r", "t", "C"],
                         "field_mapping": {"x": "r", "y": "t", "z": "C",
                                           "level": 0.15},
                         "claim": "含水率随时间向内推进。",
                         "options": {"quantity": "moisture", "level": 0.15}}],
                statistics={"interval": {"kind": "none", "method": "不适用"}},
                brief="reports/figure_briefs/wrong.json",
            )
        self.assertIn("figure_id", str(caught.exception))

    def test_bundle_edit_without_relocking_is_a_data_issue(self):
        path = self.root / "figures/data/q3_demo.npz"
        with np.load(path) as z:
            arrays = {k: z[k] for k in z.files}
        arrays["C"] = arrays["C"] * 1.01
        np.savez_compressed(path, **arrays)
        issues = figure_lock.verify(self.root)
        self.assertIn("data", _issue_kinds(issues))
        self.assertTrue(any("sha256" in i["message"] for i in issues))

    def test_malformed_lock_is_a_contract_issue(self):
        (self.root / "figures/q3_demo.lock.json").write_text(
            '{"schema_version": 1, "figure_id": "q3_demo", "data": []}',
            encoding="utf-8")
        issues = figure_lock.verify(self.root)
        self.assertIn("contract", _issue_kinds(issues))

    def test_lock_path_escape_is_a_contract_issue(self):
        path = self.root / "figures/q3_demo.lock.json"
        lock = json.loads(path.read_text(encoding="utf-8"))
        lock["data"]["path"] = "../../outside.npz"
        path.write_text(json.dumps(lock, ensure_ascii=False, indent=2), encoding="utf-8")
        issues = figure_lock.verify(self.root)
        self.assertIn("contract", _issue_kinds(issues))
        self.assertTrue(any("越界" in i["message"] or "路径" in i["message"] for i in issues))

    def test_source_edit_without_relocking_is_a_data_issue(self):
        (self.root / "results/q3.json").write_text('{"ok": false}', encoding="utf-8")
        issues = figure_lock.verify(self.root)
        self.assertIn("data", _issue_kinds(issues))
        self.assertTrue(any("results/q3.json" in i["message"] for i in issues))

    def test_spec_field_edit_is_a_contract_issue(self):
        spec = self._read_spec()
        spec["panels"][0]["fields"] = ["r", "t"]
        self._write_spec(spec)
        issues = figure_lock.verify(self.root)
        self.assertIn("contract", _issue_kinds(issues))
        self.assertTrue(any("fields" in i["message"] for i in issues))

    def test_spec_options_and_layout_are_presentation_only(self):
        spec = self._read_spec()
        spec["panels"][0]["options"] = {"quantity": "moisture", "gamma": 0.8}
        spec["layout"] = {"kind": "grid", "rows": 1, "cols": 1}
        spec["panels"][0]["recipe"] = "field_heatmap"
        self._write_spec(spec)
        self.assertEqual(figure_lock.verify(self.root), [],
                         "换图型/颜色/版式是 ⑦ 的权限，不该判契约失败")

    def test_spec_unit_edit_is_a_contract_issue(self):
        spec = self._read_spec()
        spec["data"]["fields"]["C"]["unit"] = "g/kg"
        self._write_spec(spec)
        issues = figure_lock.verify(self.root)
        self.assertIn("contract", _issue_kinds(issues))

    def test_spec_claim_edit_is_a_contract_issue(self):
        spec = self._read_spec()
        spec["claim"] = "含水率场在 1 h 内推进。"
        self._write_spec(spec)
        issues = figure_lock.verify(self.root)
        self.assertIn("contract", _issue_kinds(issues))
        self.assertTrue(any("claim" in i["message"] for i in issues))

    def test_missing_lock_with_bundle_is_a_contract_issue(self):
        (self.root / "figures/q3_demo.lock.json").unlink()
        issues = figure_lock.verify(self.root)
        self.assertIn("contract", _issue_kinds(issues))
        self.assertTrue(any("lock" in i["message"] for i in issues))

    def test_save_figure_refuses_a_stale_bundle(self):
        path = self.root / "figures/data/q3_demo.npz"
        with np.load(path) as z:
            arrays = {k: z[k] for k in z.files}
        arrays["C"] = arrays["C"] + 1
        np.savez_compressed(path, **arrays)
        with plt.rc_context():
            fig, ax = plt.subplots()
            ax.plot(self.r, self.r)
            with self.assertRaises(ValueError) as caught:
                studio.save_figure(
                    fig, self.root, "q3_demo", self.ctx, {"min_font_size": 1, "dpi": 100},
                    sources=[], script="figures/make_figures.py",
                    claim="含水率场在 5 h 内向内推进。", caption="测试图。")
            plt.close(fig)
        self.assertIn("figure lock", str(caught.exception))

    def test_save_figure_refuses_a_missing_lock(self):
        (self.root / "figures/q3_demo.lock.json").unlink()
        with plt.rc_context():
            fig, ax = plt.subplots()
            ax.plot(self.r, self.r)
            with self.assertRaises(ValueError) as caught:
                studio.save_figure(
                    fig, self.root, "q3_demo", self.ctx, {"min_font_size": 1, "dpi": 100},
                    sources=[], script="figures/make_figures.py",
                    claim="含水率场在 5 h 内向内推进。", caption="测试图。")
            plt.close(fig)
        self.assertIn("lock", str(caught.exception))

    def test_save_figure_refuses_an_unreadable_lock(self):
        (self.root / "figures/q3_demo.lock.json").write_text("{not json", encoding="utf-8")
        with plt.rc_context():
            fig, ax = plt.subplots()
            ax.plot(self.r, self.r)
            with self.assertRaises(ValueError) as caught:
                studio.save_figure(
                    fig, self.root, "q3_demo", self.ctx, {"min_font_size": 1, "dpi": 100},
                    sources=[], script="figures/make_figures.py",
                    claim="含水率场在 5 h 内向内推进。", caption="测试图。")
            plt.close(fig)
        self.assertIn("不可读", str(caught.exception))

    def test_save_figure_succeeds_and_meta_matches_the_lock(self):
        with studio.style(self.ctx, width_mm=160) as settings:
            fig = studio.canvas(self.ctx, width_mm=160, height_mm=90, constrained=False)
            ax = fig.add_subplot(111)
            ax.plot(self.r, self.r)
            studio.save_figure(
                fig, self.root, "q3_demo", self.ctx, settings,
                sources=studio.lock_sources(self.root, "q3_demo"),
                script="figures/make_figures.py",
                claim="含水率场在 5 h 内向内推进。",
                caption="测试图；无统计区间。",
                source_data={"a": (("r",), ((float(x),) for x in self.r))},
                meta={"intervals": "无", "exclusions": "无"},
            )
            plt.close(fig)
        self.assertEqual(figure_lock.verify(self.root), [])
        meta = json.loads((self.root / "figures/q3_demo.meta.json").read_text(encoding="utf-8"))
        self.assertEqual(meta["claim"], "含水率场在 5 h 内向内推进。")
        self.assertEqual(meta["spec"], "figures/spec/q3_demo.json")
        self.assertEqual(meta["figure_lock"], "figures/q3_demo.lock.json")

    def test_manifest_claim_edit_is_a_contract_issue(self):
        self.test_save_figure_succeeds_and_meta_matches_the_lock()
        path = self.root / "figures/manifest.json"
        manifest = json.loads(path.read_text(encoding="utf-8"))
        manifest["figures"]["q3_demo"]["claim"] = "含水率场在 1 h 内推进。"
        path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        issues = figure_lock.verify(self.root)
        self.assertIn("contract", _issue_kinds(issues))
        self.assertTrue(any("manifest.claim" in i["message"] for i in issues))

    def test_meta_claim_edit_is_a_contract_issue(self):
        self.test_save_figure_succeeds_and_meta_matches_the_lock()
        path = self.root / "figures/q3_demo.meta.json"
        meta = json.loads(path.read_text(encoding="utf-8"))
        meta["claim"] = "含水率场在 1 h 内推进。"
        path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        issues = figure_lock.verify(self.root)
        self.assertIn("contract", _issue_kinds(issues))
        self.assertTrue(any("meta.claim" in i["message"] for i in issues))

    def test_audit_studio_surfaces_lock_issues(self):
        spec = self._read_spec()
        spec["panels"][0]["fields"] = ["r", "t"]
        self._write_spec(spec)
        result = audit_studio.check(self.root)
        self.assertEqual(result["status"], "FAIL")
        self.assertTrue(any("[lock:contract]" in i for i in result["issues"]),
                        result["issues"])


@unittest.skipIf(studio is None, f"scientific stack missing: {IMPORT_ERROR}")
class RenderSpecTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "config").mkdir()
        shutil.copy2(PROJECT / "config/visualization.json",
                     self.root / "config/visualization.json")
        (self.root / "results").mkdir()
        (self.root / "results/q3.json").write_text("{}", encoding="utf-8")
        (self.root / "figures").mkdir()
        (self.root / "figures/make_figures.py").write_text(
            "# renderer\nimport studio\n", encoding="utf-8")
        self.ctx = studio.context(self.root)
        self.r = np.linspace(0, 1, 12)
        self.t = np.linspace(0, 5, 8)
        self.C = np.exp(-np.outer(self.t, self.r))
        studio.save_bundle(
            self.root, "q3_demo", {"r": self.r, "t": self.t, "C": self.C}, self.ctx,
            claim="含水率场在 5 h 内向内推进。", sources=["results/q3.json"],
            panels=[{"id": "a", "recipe": "field_contour",
                     "fields": ["r", "t", "C"],
                     "field_mapping": {"x": "r", "y": "t", "z": "C"},
                     "claim": "含水率随时间向内推进。",
                     "options": {"quantity": "moisture", "level": 0.15}}],
            statistics={"interval": {"kind": "none", "method": "不适用"},
                        "test": {"kind": "none", "p_values": False},
                        "unit": "确定性模拟", "paired": False},
            width_mm=160, height_mm=90, layout={"kind": "single"},
        )

    def test_declarative_spec_renders_and_registers(self):
        rendered = studio.render_specs(self.root)
        self.assertEqual(len(rendered), 1)
        for suffix in (".pdf", ".svg", ".png"):
            self.assertTrue((self.root / f"figures/q3_demo{suffix}").is_file(), suffix)
        self.assertTrue((self.root / "figures/q3_demo.meta.json").is_file())
        self.assertEqual(figure_lock.verify(self.root), [])
        meta = json.loads((self.root / "figures/q3_demo.meta.json").read_text(encoding="utf-8"))
        self.assertIn("a", meta["source_data"])
        self.assertGreater(meta["counts"]["a"], 0)

    def test_render_fixes_a_stale_meta_claim_instead_of_refusing(self):
        studio.render_specs(self.root)
        meta_path = self.root / "figures/q3_demo.meta.json"
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        meta["claim"] = "错误的 claim。"
        meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        # A stale meta is a rendering problem, not a data-layer problem.
        self.assertTrue(any(i["message"].find("meta.claim") >= 0
                            for i in figure_lock.verify(self.root)))
        studio.render_specs(self.root)
        self.assertEqual(figure_lock.verify(self.root), [])
        fixed = json.loads(meta_path.read_text(encoding="utf-8"))
        self.assertEqual(fixed["claim"], "含水率场在 5 h 内向内推进。")

    def test_grid_without_rows_cols_does_not_overlap_panels(self):
        studio.save_bundle(
            self.root, "q_grid",
            {"r": self.r, "t": self.t, "C": self.C, "c1": self.r, "c2": self.r ** 2},
            self.ctx, claim="两个面板用于网格测试。", sources=["results/q3.json"],
            panels=[
                {"id": "a", "recipe": "field_contour", "fields": ["r", "t", "C"],
                 "field_mapping": {"x": "r", "y": "t", "z": "C", "level": 0.15},
                 "options": {"quantity": "moisture", "level": 0.15},
                 "claim": "面板 a 的 claim。"},
                {"id": "b", "recipe": "profiles", "fields": ["r", "c1", "c2"],
                 "field_mapping": {"x": "r", "series": ["c1", "c2"]},
                 "options": {"series_labels": ["甲", "乙"]},
                 "claim": "面板 b 的 claim。"},
            ],
            statistics={"interval": {"kind": "none", "method": "不适用"}},
            width_mm=160, height_mm=90, layout={"kind": "grid"},
        )
        spec = studio.load_spec(self.root, "q_grid")
        seen = {}
        original = studio.save_figure

        def fake_save(fig, *args, **kwargs):
            seen["pos"] = [ax.get_position().bounds for ax in fig.axes]
            return {"artifacts": ["figures/q_grid.png"]}

        studio.save_figure = fake_save
        try:
            studio.render_spec(spec, self.root, ctx=self.ctx)
        finally:
            studio.save_figure = original
        positions = seen["pos"]
        self.assertGreaterEqual(len(positions), 2)
        # A field panel adds a colorbar Axes; the two **panel** axes are added first.
        self.assertNotEqual(positions[0], positions[1],
                            "两个面板落在同一格 —— layout 只写了 kind=grid")

    def test_an_explicit_empty_selection_renders_nothing(self):
        self.assertEqual(studio.render_specs(self.root, []), [],
                         "显式空列表被当成 None，会把锁失败的图也重渲一遍")

    def test_custom_spec_is_skipped_not_guessed(self):
        spec = json.loads((self.root / "figures/spec/q3_demo.json").read_text(encoding="utf-8"))
        spec["render"] = {"mode": "custom", "script": "figures/make_figures.py"}
        (self.root / "figures/spec/q3_demo.json").write_text(
            json.dumps(spec, ensure_ascii=False), encoding="utf-8")
        self.assertEqual(studio.render_specs(self.root), [])


@unittest.skipIf(studio is None, f"scientific stack missing: {IMPORT_ERROR}")
class DeclarativeRecipeTests(unittest.TestCase):
    """The default renderer must cover the common recipe shapes, not just fields."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "config").mkdir()
        shutil.copy2(PROJECT / "config/visualization.json",
                     self.root / "config/visualization.json")
        (self.root / "results").mkdir()
        (self.root / "results/q.json").write_text("{}", encoding="utf-8")
        (self.root / "figures").mkdir()
        (self.root / "figures/make_figures.py").write_text("# renderer\nimport studio\n",
                                                          encoding="utf-8")
        self.ctx = studio.context(self.root)
        self.rng = np.random.default_rng(3)

    def _save(self, fid, arrays, panels, *, layout=None, height=90):
        studio.save_bundle(
            self.root, fid, arrays, self.ctx,
            claim=f"{fid} 的 claim 足够长。", sources=["results/q.json"],
            panels=panels,
            statistics={"interval": {"kind": "none", "method": "不适用"},
                        "test": {"kind": "none", "p_values": False},
                        "unit": "确定性模拟", "paired": False},
            width_mm=160, height_mm=height, layout=layout or {"kind": "single"},
        )

    def test_common_recipes_render(self):
        # profiles
        x = np.linspace(0, 1, 20)
        self._save("q_profiles",
                   {"x": x, "c1": np.sin(x), "c2": np.cos(x)},
                   [{"id": "a", "recipe": "profiles", "fields": ["x", "c1", "c2"],
                     "field_mapping": {"x": "x", "series": ["c1", "c2"]},
                     "options": {"series_labels": ["甲", "乙"]},
                     "claim": "两条剖面随半径变化。"}])
        # grouped bars
        self._save("q_bars",
                   {"cat": np.array(["甲", "乙", "丙"]),
                    "s1": [1.0, 2.0, 3.0], "s2": [1.5, 2.5, 3.5]},
                   [{"id": "a", "recipe": "grouped_bars", "fields": ["cat", "s1", "s2"],
                     "field_mapping": {"categories": "cat", "series": ["s1", "s2"]},
                     "claim": "两个方案在三个类别上的差异。"}])
        # distribution boxes
        self._save("q_box",
                   {"a": self.rng.normal(size=40), "b": self.rng.normal(0.5, 1, 40)},
                   [{"id": "a", "recipe": "distribution_box", "fields": ["a", "b"],
                     "field_mapping": {"groups": ["a", "b"]},
                     "options": {"groups": ["a", "b"]},
                     "claim": "两组分布不同。"}])
        # correlation matrix
        mat = np.array([[1.0, .4, -.2], [.4, 1.0, .1], [-.2, .1, 1.0]])
        self._save("q_corr",
                   {"matrix": mat},
                   [{"id": "a", "recipe": "correlation_matrix", "fields": ["matrix"],
                     "field_mapping": {"matrix": "matrix"},
                     "options": {"variables": ["甲", "乙", "丙"]},
                     "claim": "三个变量相关结构。"}])
        # heatmap
        self._save("q_heat",
                   {"values": self.rng.uniform(size=(3, 4))},
                   [{"id": "a", "recipe": "table_heatmap", "fields": ["values"],
                     "field_mapping": {"values": "values"},
                     "options": {"rows": ["甲", "乙", "丙"],
                                 "columns": ["一", "二", "三", "四"]},
                     "claim": "三行四列的矩阵。"}])
        # radar (polar)
        self._save("q_radar",
                   {"s1": [.8, .6, .7], "s2": [.5, .9, .6]},
                   [{"id": "a", "recipe": "radar", "fields": ["s1", "s2"],
                     "field_mapping": {"series": ["s1", "s2"]},
                     "options": {"metrics": ["甲", "乙", "丙"],
                                 "categories": ["甲", "乙", "丙"]},
                     "claim": "两条指纹的形状。"}])
        # surface + projection is custom; just the 3D surface
        xs = np.linspace(0, 1, 8)
        ys = np.linspace(0, 1, 9)
        zz = np.outer(ys, xs)
        self._save("q_surface",
                   {"x": xs, "y": ys, "z": zz},
                   [{"id": "a", "recipe": "surface3d", "fields": ["x", "y", "z"],
                     "field_mapping": {"x": "x", "y": "y", "z": "z"},
                     "claim": "两个参数共同影响响应面。"}])
        rendered = studio.render_specs(self.root)
        self.assertEqual(len(rendered), 7)
        self.assertEqual(figure_lock.verify(self.root), [])
        for fid in ("q_profiles", "q_bars", "q_box", "q_corr", "q_heat", "q_radar", "q_surface"):
            self.assertTrue((self.root / f"figures/{fid}.png").is_file(), fid)
            meta = json.loads((self.root / f"figures/{fid}.meta.json").read_text(encoding="utf-8"))
            self.assertGreaterEqual(sum(meta["counts"].values()), 1, fid)


if __name__ == "__main__":
    unittest.main()
