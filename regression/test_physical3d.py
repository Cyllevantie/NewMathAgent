# -*- coding: utf-8 -*-
"""第五类非数据图（物理立体 / 3D 剖切）哨兵。

查三类东西：
1. 文档：SKILL / reference 真的声明了第五类、四条路线、按问判重与 QA；
2. 代码：相机投影、剖切面片、标签记录/越界判定；
3. 端到端：小场景能渲染出纯矢量 PDF，字体嵌入、文字可提取。
"""
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

PROJECT = Path(__file__).resolve().parents[1]
ASSETS = PROJECT / "skills" / "7Route-diagram" / "assets" / "physical3d"
SKILL = PROJECT / "skills" / "7Route-diagram" / "SKILL.md"
REF = PROJECT / "skills" / "7Route-diagram" / "references" / "physical-3d.md"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


class Physical3dDocsTests(unittest.TestCase):
    def test_skill_declares_fifth_type(self):
        text = SKILL.read_text(encoding="utf-8")
        self.assertIn("第五类非数据图", text)
        self.assertIn("fig_geometry_3d", text)
        self.assertIn("physical-3d.md", text)
        self.assertIn("按问判重", text)
        self.assertIn("合并", text)
        self.assertIn("qa_physical3d.py", text)

    def test_reference_has_routes_and_self_check(self):
        text = REF.read_text(encoding="utf-8")
        for token in ("Route A", "Route B", "Route C", "Route D",
                      "透明线框", "实心剖切", "按问判重",
                      "强制自检", "qa_physical3d.py"):
            self.assertIn(token, text)
        self.assertGreaterEqual(text.count("\n1. "), 1)

    def test_templates_exist(self):
        for name in ("route_a_wireframe.py", "route_b_cutaway.py",
                     "route_a_shrinkage.py", "route_a_event.py"):
            self.assertTrue((ASSETS / "templates" / name).is_file(), name)

    def test_agents_json_has_3d_candidate(self):
        agents = json.loads((PROJECT / "config" / "agents.json")
                            .read_text(encoding="utf-8"))
        self.assertIn("fig-3d-candidate", agents)
        spec = agents["fig-3d-candidate"]
        self.assertIn("physical-3d.md", spec["prompt"])
        self.assertIn("qa_physical3d.py", spec["prompt"])


class Physical3dCodeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.S = _load("physical3d_solid3d", ASSETS / "solid3d.py")

    def test_camera_projection_axis_aligned(self):
        S = self.S
        cam = S.Camera(azim=0.0, elev=0.0)
        xy, dep = cam.project([[1, 0, 0], [0, 1, 0], [0, 0, 1]])
        # azim=0: f=(1,0,0), right=(0,1,0), up=(0,0,1)
        self.assertAlmostEqual(xy[0, 0], 0.0, places=6)
        self.assertAlmostEqual(xy[0, 1], 0.0, places=6)
        self.assertAlmostEqual(xy[1, 0], 1.0, places=6)
        self.assertAlmostEqual(xy[2, 1], 1.0, places=6)
        self.assertAlmostEqual(dep[0], -1.0, places=6)

    def test_camera_pole_is_not_degenerate(self):
        S = self.S
        for elev in (90.0, -90.0):
            cam = S.Camera(azim=-58.0, elev=elev)
            xy, _ = cam.project([[1, 0, 0], [0, 1, 0], [0, 0, 1]])
            self.assertGreater(float(np.abs(xy).max()), 0.5, elev)

    def test_cap_segments_are_self_colored(self):
        S = self.S
        sc = S.Scene(S.Camera())
        sc.cylinder(r=1.0, z0=0.0, z1=2.0, segments=24)
        caps = [f for f in sc.faces if f.name.endswith(":cap")]
        self.assertTrue(caps)
        for f in caps:
            self.assertEqual(f.edge, f.color)
            self.assertAlmostEqual(f.lw, 0.3, places=6)

    def test_cylinder_cut_has_cut_faces_and_caps(self):
        S = self.S
        sc = S.Scene(S.Camera())
        sc.cylinder(r=2.0, z0=0.0, z1=5.0, cut=(90.0, 0.0), segments=48)
        names = [f.name for f in sc.faces]
        self.assertTrue(any(":outer" in n for n in names))
        self.assertEqual(sum(":cut" in n for n in names), 2)
        self.assertTrue(any(":cap" in n for n in names))
        # 90° 楔形切掉 => 保留 270°，外侧 + 端面面片应明显少于整圆柱
        outer = sum(":outer" in n for n in names)
        self.assertGreater(outer, 20)
        self.assertLess(outer, 48)

    def test_hollow_cylinder_has_inner_wall(self):
        S = self.S
        sc = S.Scene(S.Camera())
        sc.cylinder(r=2.0, inner=1.0, z0=0.0, z1=5.0, segments=32)
        names = [f.name for f in sc.faces]
        self.assertTrue(any(":inner" in n for n in names))

    def test_surface_ignores_inf_and_all_nan(self):
        S = self.S
        sc = S.Scene(S.Camera())
        X, Y = np.meshgrid([0.0, 1.0, 2.0], [0.0, 1.0, 2.0])
        Z = np.array([[np.inf, 1.0, 2.0],
                      [1.0, 2.0, 3.0],
                      [2.0, 3.0, 4.0]])
        sc.surface(X, Y, Z)
        self.assertEqual(len(sc.faces), 3)  # 含 inf 的那个角被跳过
        from matplotlib.colors import to_rgb
        colors = {tuple(np.round(to_rgb(f.color), 4)) for f in sc.faces}
        self.assertGreater(len(colors), 1)  # 不能全落到 cmap(0)
        sc2 = S.Scene(S.Camera())
        sc2.surface(X, Y, np.full_like(Z, np.nan))
        self.assertEqual(sc2.faces, [])

    def test_preferred_label_offset_is_kept(self):
        S = self.S
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        S.configure_style("DejaVu Sans", 8.5)
        sc = S.Scene(S.Camera(azim=-58, elev=20))
        sc.cylinder(r=1.0, z0=0.0, z1=1.0, segments=24)
        sc.label((0, 0, 1.9), "axis", offset=(18, 8), auto=True)
        fig, ax = plt.subplots(figsize=(2.4, 2.4))
        sc.fit(ax, margin=0.25)
        rec = sc.draw(ax, fig)
        plt.close(fig)
        self.assertEqual(rec["labels"][0]["offset_pt"], [18.0, 8.0])

    def test_save_width_mismatch_raises(self):
        S = self.S
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        S.configure_style("DejaVu Sans", 8.5)
        sc = S.Scene(S.Camera())
        sc.box((0, 0, 0), (1, 1, 1))
        fig, ax = plt.subplots(figsize=(2.0, 2.0))
        sc.fit(ax)
        sc.draw(ax, fig)
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(ValueError):
                sc.save(fig, "t", td, width_mm=60.0)
        plt.close(fig)

    def test_label_record_and_out_of_bounds_detection(self):
        S = self.S
        sc = S.Scene(S.Camera(azim=-58, elev=20))
        sc.cylinder(r=1.0, z0=0.0, z1=2.0, segments=24)
        sc.label((0, 0, 1.0), "axis", offset=(20, 0), auto=False)
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        S.configure_style("DejaVu Sans", 8.5)
        fig, ax = plt.subplots(figsize=(2.4, 2.4))
        sc.fit(ax, margin=0.12)
        rec = sc.draw(ax, fig)
        plt.close(fig)
        self.assertEqual(len(rec["labels"]), 1)
        self.assertIn("bbox", rec["labels"][0])
        self.assertIn("out_of_bounds", rec["labels"][0])

    def test_qa_flags_off_page_text(self):
        try:
            import fitz
        except Exception:
            self.skipTest("PyMuPDF unavailable")
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "offpage.pdf"
            doc = fitz.open()
            page = doc.new_page(width=200, height=200)
            page.insert_text((220, 50), "OFFPAGE", fontsize=12)
            doc.save(str(p))
            doc.close()
            qa = _load("physical3d_qa_offpage", ASSETS / "qa_physical3d.py")
            rep = qa.check_pdf(p, "DejaVu Sans", None)
            self.assertFalse(rep["ok"])
            self.assertGreater(rep["info"]["clipped_text_blocks"], 0)

    def test_end_to_end_pdf_is_vector_and_has_fonts(self):
        S = self.S
        try:
            import fitz  # noqa: F401
        except Exception:
            self.skipTest("PyMuPDF unavailable")
        S.configure_style("DejaVu Sans", 8.5)
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        sc = S.Scene(S.Camera(azim=-58, elev=20))
        sc.cylinder(r=1.0, z0=0.0, z1=2.0, segments=24, cut=(60, -30))
        sc.label((0, 0, 2.05), "axis", offset=(-10, 12), ha="right", auto=False)
        fig, ax = plt.subplots(figsize=(60 / 25.4, 60 / 25.4))
        sc.fit(ax, margin=0.12)
        sc.draw(ax, fig)
        with tempfile.TemporaryDirectory() as td:
            pdf, png = sc.save(fig, "t", td, width_mm=60)
            plt.close(fig)
            qa = _load("physical3d_qa", ASSETS / "qa_physical3d.py")
            rep = qa.check_pdf(pdf, "DejaVu Sans", 60)
            self.assertTrue(rep["ok"], rep)
            self.assertEqual(rep["info"]["raster_images"], 0)
            self.assertGreater(rep["info"]["text_chars"], 0)
            self.assertTrue(rep["info"]["fonts"])
            self.assertTrue(png.is_file())


if __name__ == "__main__":
    unittest.main()
