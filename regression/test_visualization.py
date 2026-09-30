"""Evidence failures must block release even when an overall report says PASS."""
import json
import tempfile
import unittest
from pathlib import Path

from lib.visualization.evidence import audit, load, register, review, write_json


class FigureEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for rel in ("config/visualization.json", "figures/a.pdf", "data/a.csv", "data/b.csv", "plot.py"):
            p = self.root / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("content", encoding="utf-8")
        register(self.root, "a", artifacts=["figures/a.pdf"], sources=["data/a.csv", "data/b.csv"],
                 script="plot.py", claim="A documented claim", caption="A documented caption", width_mm=160)

    def approve(self):
        review(self.root, "a", reviewer="test", note="Fixture review only, no real chart")

    def test_pending_blocks_then_explicit_review_passes(self):
        self.assertTrue(audit(self.root))
        self.approve()
        self.assertEqual(audit(self.root), [])

    def test_secondary_source_invalidates_review(self):
        self.approve()
        (self.root / "data/b.csv").write_text("changed")
        self.assertTrue(audit(self.root))
        with self.assertRaises(ValueError): self.approve()

    def test_caption_edit_invalidates_signature(self):
        self.approve()
        data = load(self.root)
        data["figures"]["a"]["caption"] = "changed"
        write_json(self.root / "figures/manifest.json", data)
        self.assertTrue(audit(self.root))

    def test_asset_and_style_changes_invalidate(self):
        self.approve()
        for rel in ("figures/a.pdf", "config/visualization.json"):
            p = self.root / rel
            old = p.read_bytes()
            p.write_bytes(b"changed")
            self.assertTrue(audit(self.root))
            p.write_bytes(old)
        self.assertEqual(audit(self.root), [])

    def test_unknown_asset_blocks(self):
        self.approve()
        (self.root / "figures/unknown.png").write_bytes(b"image")
        self.assertTrue(audit(self.root))

    def test_malformed_manifest_blocks(self):
        (self.root / "figures/manifest.json").write_text("{")
        self.assertTrue(audit(self.root))

    def test_path_escape_rejected(self):
        with self.assertRaises(ValueError):
            register(self.root, "bad", artifacts=["../outside.pdf"], sources=["data/a.csv"],
                     script="plot.py", claim="claim", caption="caption", width_mm=160)

    def test_overall_pass_cannot_bypass_pending_figures(self):
        from test_workflow import load_server
        server = load_server(self.root)
        stage = next(s for s in server.STAGES if s["id"] == "verify")
        (server.REPORTS / stage["report"]).write_text("PASS\n" + "evidence " * 30)
        self.assertEqual(server._gate_decision(stage)["reason"], "figure_evidence_failed")
        server._save_feedback(stage)
        decisions = list((self.root / "runtime").rglob("gate_decision.json"))
        self.assertEqual(len(decisions), 1)
        self.assertEqual(json.loads(decisions[0].read_text(encoding="utf-8"))["reason"], "figure_evidence_failed")
        self.approve()
        self.assertEqual(server.gate_result(stage), "ok")


class SnapshotScopeTests(unittest.TestCase):
    """图的快照只哈希**产像素**的模块 —— 检查器不算。

    若 `snapshot()` 把 `lib/visualization/*.py` 整目录哈希进去，只改 `quality.py`
    里一条 warning 判据（加"单侧贴边非白带"），**19 张图全部**会被判「数据、脚本、配置或图片
    已改变，需重新生成和复核」⇒ 逼着 ⑦/⑧ 把整套图重画重看，而像素一个都没动。
    属于 `docs/WORKFLOW_RELIABILITY.md` 记的「共享文件被整目录哈希进每个阶段」同一类问题。
    """

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for rel in ("config/visualization.json", "figures/a.png", "figures/a.py", "data/a.csv"):
            p = self.root / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("content", encoding="utf-8")
        for name in ("charts.py", "quality.py", "evidence.py", "__init__.py"):
            (self.root / "lib" / "visualization").mkdir(parents=True, exist_ok=True)
            (self.root / "lib" / "visualization" / name).write_text("x = 1\n", encoding="utf-8")
        self.entry = {"sources": ["data/a.csv"], "artifacts": ["figures/a.png"],
                      "script": "figures/a.py"}

    def _snap(self):
        from lib.visualization.evidence import snapshot
        return snapshot(self.root, self.entry)

    def test_the_checker_is_not_in_the_snapshot(self):
        keys = self._snap()
        self.assertIn("lib/visualization/charts.py", keys, "画图的模块必须在")
        self.assertIn("figures/a.py", keys)
        self.assertIn("data/a.csv", keys)
        self.assertNotIn("lib/visualization/quality.py", keys, "检查器不产像素，不许进快照")
        self.assertNotIn("lib/visualization/evidence.py", keys)

    def test_editing_a_checker_does_not_stale_the_figure(self):
        before = self._snap()
        (self.root / "lib/visualization/quality.py").write_text("x = 2   # 收紧一条判据\n",
                                                            encoding="utf-8")
        self.assertEqual(self._snap(), before, "改检查器不该让图变成'需重新生成'")

    def test_editing_a_producer_does_stale_the_figure(self):
        """反向守卫：真改了画图代码，图**必须**被判过期 —— 不然会悄悄交付旧图。"""
        before = self._snap()
        (self.root / "lib/visualization/charts.py").write_text("x = 3   # 改画法\n", encoding="utf-8")
        self.assertNotEqual(self._snap(), before)

    def test_every_declared_producer_actually_exists(self):
        """`PIXEL_PRODUCERS` 里写错一个名字 = 那个模块**静默地**不再进指纹。

        宁可在这儿红，也别让它悄悄放行一张用旧画法渲染的图。
        """
        from lib.visualization.evidence import PIXEL_PRODUCERS
        project = Path(__file__).resolve().parents[1]
        for name in PIXEL_PRODUCERS:
            self.assertTrue((project / "lib" / "visualization" / name).is_file(),
                            f"PIXEL_PRODUCERS 里的 {name} 不在 lib/visualization/ 下")
        self.assertNotIn("quality.py", PIXEL_PRODUCERS)
        self.assertNotIn("evidence.py", PIXEL_PRODUCERS)


if __name__ == "__main__":
    unittest.main()
