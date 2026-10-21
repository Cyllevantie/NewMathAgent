# -*- coding: utf-8 -*-
"""④ 计算后端探测哨兵：1D 串行、2D 限并发、GPU 只在批量大时建议。"""
import json
import subprocess
import sys
import unittest
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
SCRIPT = PROJECT / "skills" / "4Coding-and-computation" / "scripts" / "detect_compute.py"
REF = PROJECT / "skills" / "4Coding-and-computation" / "references" / "compute-backends.md"
SKILL = PROJECT / "skills" / "4Coding-and-computation" / "SKILL.md"


def run(problem: str, batch: int = 0) -> dict:
    p = subprocess.run(
        [sys.executable, str(SCRIPT), "--problem", problem, "--batch", str(batch)],
        cwd=str(PROJECT), capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=30)
    assert p.returncode == 0, p.stderr
    return json.loads(p.stdout)


class ComputeBackendTests(unittest.TestCase):
    def test_1d_pde_is_cpu_serial(self):
        d = run("1d-pde")
        self.assertEqual(d["recommended_backend"], "cpu-serial")
        self.assertEqual(d["workers"], 1)

    def test_2d_pde_caps_parallel_workers(self):
        d = run("2d-pde")
        self.assertEqual(d["recommended_backend"], "cpu-parallel")
        self.assertLessEqual(d["workers"], 3)
        self.assertGreaterEqual(d["workers"], 1)

    def test_monte_carlo_backend_is_cpu_or_gpu(self):
        d = run("monte-carlo", 200000)
        self.assertIn(d["recommended_backend"], ("cpu-parallel", "gpu-batched"))
        if d["recommended_backend"] == "gpu-batched":
            self.assertEqual(d["workers"], 1)

    def test_skill_points_to_policy_and_detector(self):
        text = SKILL.read_text(encoding="utf-8")
        self.assertIn("compute-backends.md", text)
        self.assertIn("detect_compute.py", text)
        self.assertIn("GPU", text)
        self.assertTrue(REF.is_file())


if __name__ == "__main__":
    unittest.main()
