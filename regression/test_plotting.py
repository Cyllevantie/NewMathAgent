"""Rendering and numeric guards; requires the project's scientific Python stack."""
import tempfile
import unittest
from pathlib import Path

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from lib.visualization.charts import canvas, heatmap, style, trend
    from lib.visualization.export import export
except ImportError:
    plt = None


@unittest.skipIf(plt is None, "Run with NumPy/Matplotlib installed")
class PlottingTests(unittest.TestCase):
    def tearDown(self):
        plt.close("all")

    def test_geometry_preserves_projection_scale_and_rejects_degeneracy(self):
        import numpy as np
        from lib.visualization.geometry import orthographic, sphere_section, angle_marker
        np.testing.assert_allclose(orthographic([[0, 2, 0], [0, 0, 3]], azimuth=0, elevation=0), [[2, 0], [0, 3]])
        fig, ax = plt.subplots()
        self.assertAlmostEqual(angle_marker(ax, [0, 0], [1, 0], [0, 1], radius=.2, label="angle"), 90)
        with self.assertRaises(ValueError):
            angle_marker(ax, [0, 0], [0, 0], [0, 1], radius=.2, label="invalid")
        with self.assertRaises(ValueError): sphere_section(fig, radius=1, height=2)

    def test_reject_missing_and_unsorted_data(self):
        _, ax = plt.subplots()
        for x, y in (([1, 2], [2, float("nan")]), ([2, 1], [1, 2])):
            with self.assertRaises(ValueError): trend(ax, x, y, label="test")

    def test_interval_requires_definition_and_valid_bounds(self):
        _, ax = plt.subplots()
        with self.assertRaises(ValueError):
            trend(ax, [1, 2], [2, 3], label="test", low=[1, 2], high=[3, 4])
        with self.assertRaises(ValueError):
            trend(ax, [1, 2], [2, 3], label="test", low=[3, 4], high=[4, 5], interval_label="range")

    def test_heatmap_rejects_invalid_correlation(self):
        _, ax = plt.subplots()
        with self.assertRaises(ValueError):
            heatmap(ax, [[1, 2], [2, 1]], ["a", "b"], ["a", "b"], colorbar_label="r", correlation=True)

    def test_export_detects_real_clipping_and_not_unused_ticks(self):
        import shutil
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "config").mkdir()
            shutil.copy2(Path(__file__).resolve().parents[1] / "config/visualization.json", root / "config/visualization.json")
            (root / "data.csv").write_text("x,y\n1,2\n2,3")
            (root / "plot.py").write_text("# fixture")
            with style() as settings:
                fig = canvas(settings)
                ax = fig.add_subplot()
                trend(ax, [1, 2], [2, 3], label="test")
                ax.set(xlabel="x", ylabel="y")
                kwargs = dict(sources=["data.csv"], script="plot.py", claim="test claim", caption="test caption", settings=settings)
                entry = export(fig, root, "valid", **kwargs)
                self.assertEqual(entry["auto_issues"], [])
                self.assertEqual(entry["review"]["status"], "pending")
                self.assertEqual(len(entry["artifacts"]), 3)
                fig.text(1.2, .5, "clipped", fontsize=9)
                entry = export(fig, root, "clipped", **kwargs)
                self.assertTrue(entry["auto_issues"])
