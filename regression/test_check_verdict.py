# -*- coding: utf-8 -*-
"""`lib/web/check_verdict.py`（裁决侧车自检）。

为什么值得钉住：这个工具存在的唯一理由是**它必须与驱动同判**。它一旦与驱动漂移，
agent 就会照着一个错的结论去改 JSON —— 比没有这个工具更糟。所以这里钉三件事：
  ① 兜底阶段顺序与 `server.STAGES` **逐项同序**（顺序错会让 backward/forward 判定漂移，
     而 `enforce()` 只比集合、抓不到顺序错）；
  ② 合格的侧车 → 退出码 0；
  ③ 缺必查项 / 找不到侧车 → 退出码 1 / 2，且**话说得出来**（不是一句"失败"）。
"""
import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "lib" / "web"))
sys.path.insert(0, str(PROJECT / "regression"))

import check_verdict as CV                      # noqa: E402
from content_quality import REQUIRED            # noqa: E402


def _run(argv):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = CV.main(argv)
    return rc, buf.getvalue()


class CheckVerdictTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_fallback_order_matches_the_driver(self):
        """兜底表必须与 `server.STAGES` 同序 —— 漏改会在**别的机器/驱动没跑时**悄悄错。"""
        from test_workflow import load_server

        s = load_server(self.root / "iso")
        self.assertEqual(CV.FALLBACK_ORDER, [x["id"] for x in s.STAGES],
                         "lib/web/check_verdict.py 的 FALLBACK_ORDER 与 server.STAGES 不一致"
                         "（顺序也要一致：enforce 只比集合，顺序错它抓不到）")

    def _mk(self, stage, checks, status="PASS", write_sidecar=True):
        (self.root / "reports").mkdir(parents=True, exist_ok=True)
        (self.root / "config").mkdir(parents=True, exist_ok=True)
        (self.root / "config/content_quality.json").write_text(
            '{"schema_version": 1, "verdict_schema_version": 2}', encoding="utf-8")
        # 报告正文里必须**真的有**下面 _passing_checks 引用的那句话：`_evidence()` 要求
        # quote 与源文件逐字相符（NFC/空白/全角折叠后）。锚点不成立时 enforce 会先报
        # 「Check needs source anchors」，用例就测不到它本来要测的那条规则了。
        (self.root / "reports/X_REPORT.md").write_text(
            "最终结论：" + status + "\n" + "evidence " * 40 + "\n核过\n", encoding="utf-8")
        if write_sidecar:
            (self.root / "reports/X_REPORT.verdict.json").write_text(json.dumps(
                {"schema_version": 2, "stage": stage, "input_digest": "aa:bb",
                 "status": status, "issues": [], "checks": checks}, ensure_ascii=False),
                encoding="utf-8")

    def _passing_checks(self, stage):
        return [{"id": cid, "status": "passed", "reason": "核过",
                 "evidence": [{"file": "reports/X_REPORT.md", "quote": "核过"}]}
                for cid in REQUIRED[stage]]

    def test_a_wellformed_sidecar_exits_zero(self):
        self._mk("cross", self._passing_checks("cross"))
        rc, out = _run(["--stage", "cross", "--root", str(self.root)])
        self.assertEqual(rc, 0, f"合格侧车应当 0，实际 {rc}\n{out}")
        self.assertIn("✓", out)
        self.assertIn("PASS", out)

    def test_missing_required_check_exits_one_and_says_which(self):
        checks = [c for c in self._passing_checks("cross") if c["id"] != "narrative_consistency"]
        self._mk("cross", checks)
        rc, out = _run(["--stage", "cross", "--root", str(self.root)])
        self.assertEqual(rc, 1, f"缺必查项应当 1，实际 {rc}\n{out}")
        self.assertIn("narrative_consistency", out,
                      "必须**指名**缺了哪一项，不能只说一句'格式错'")

    def test_no_sidecar_exits_two(self):
        (self.root / "reports").mkdir(parents=True, exist_ok=True)
        rc, out = _run(["--stage", "cross", "--root", str(self.root)])
        self.assertEqual(rc, 2, f"找不到侧车是环境问题，应当 2，实际 {rc}\n{out}")
        self.assertIn("verdict.json", out)

    def test_stage_field_is_used_to_find_the_sidecar(self):
        """按侧车里的 `stage` 找，不维护"阶段→报告名"第二张表（少一处会漂的知识）。"""
        self._mk("cross", self._passing_checks("cross"))
        hits, unreadable = CV.find_sidecar(self.root / "reports", "cross")
        self.assertEqual([p.name for p in hits], ["X_REPORT.verdict.json"])
        self.assertEqual(unreadable, [])
        # 侧车缺 `stage` ⇒ 匹配不上，而且**要报出来**（那正是最需要知道的一种坏法）
        (self.root / "reports/Y.verdict.json").write_text('{"schema_version": 2}', encoding="utf-8")
        hits2, unread2 = CV.find_sidecar(self.root / "reports", "cross")
        self.assertEqual([p.name for p in hits2], ["X_REPORT.verdict.json"])
        self.assertEqual([p.name for p, _ in unread2], ["Y.verdict.json"])

    def test_it_refuses_to_invent_its_own_stage_report_table(self):
        """源码级钉子：它必须调驱动的两个函数，不许自己重写判据。"""
        src = (PROJECT / "lib/web/check_verdict.py").read_text(encoding="utf-8")
        self.assertIn("from content_quality import enforce", src)
        self.assertIn("from workflow_quality import read_verdict", src)
        self.assertNotIn("import server", src,
                         "不要 import server.py —— 仓库里所有 CLI 都走 HTTP 拿驱动信息")


if __name__ == "__main__":
    unittest.main()
