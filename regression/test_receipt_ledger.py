# -*- coding: utf-8 -*-
"""返修台账自检：探针不许落在「版本/返修记录」里，也不许被更长的串前缀撞上。

这些用例的形状都出自真实报告里的边角（已用独立字符串计数复核过），不是编出来的：
  · §15.1 正文仍写「偏差 ≤0.4%」，而「≤0.98%」只在版本表/返修记录里出现；
  · 「66600 s」三处命中全在版本表/返修记录，§15.2 正文 0 命中；
  · 「M3」「热供给」只在返修记录里出现，回执要求的 §2 A3/§9.9 T4 正文 0 命中；
  · 回执要求增 `q4.moist_max_at_tend`，实际只加了 `q4.moist_max_at_tend_minus_60s`。
"""
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "lib" / "web"))
import receipt_ledger  # noqa: E402

# 与真报告同构：正文（§2）与版本表/返修记录（§15.x 及其子节）分开。
REPORT = """# 建模报告

## 2. 模型
A3 保留解释①为对照模型 M2，在 6Robustness 中给出 ΔT、Δt_end。
§12.1 登记 q4.moist_max_at_tend_minus_60s 一条。

## 15. 版本与修订历史

| 版本 | 说明 |
|---|---|
| v1.4 | 按 17 条清单定点返修：偏差改「≤0.98%」；改「自 66600 s 起」；补 M3 与热供给 |

### 15.1 本轮返修复验记录

| 回执项 | 处置 |
|---|---|
| `rv2_provenance_numbers` | ① §15.2 该句改「自 **66600 s** 起」；③ §15.1「偏差 ≤0.4%」改为 **≤0.98%** |
| `rv2_mechanism_scope_minors` | 补「Δt_end 方向 M1 ≤ **M3** ≤ M2」与「**热供给**限速」 |
| `rv2_registry_contract_gaps` | ① §12.1 增 `q4.moist_max_at_tend` |
"""

RECEIPT_IDS = ["rv2_provenance_numbers", "rv2_mechanism_scope_minors", "rv2_registry_contract_gaps"]
RECEIPT_REL = "runtime/quality/feedback/run1/abc123/gate_decision.json"


class ReceiptLedgerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        (self.tmp / "reports").mkdir()
        (self.tmp / "runtime/quality/feedback/run1/abc123").mkdir(parents=True)
        (self.tmp / "reports/ANALYSIS_MODELING_REPORT.md").write_text(REPORT, encoding="utf-8")
        self.receipt(RECEIPT_REL, {"issues": [{"id": i} for i in RECEIPT_IDS]})

    def receipt(self, rel, obj):
        p = self.tmp / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")

    def ledger(self, items, **kw):
        obj = {"schema_version": 1, "receipt": kw.pop("receipt", RECEIPT_REL),
               "report": kw.pop("report", "reports/ANALYSIS_MODELING_REPORT.md"), "items": items}
        obj.update(kw)
        self.receipt("reports/RECEIPT_LEDGER.json", obj)

    def check(self, **kw):
        return receipt_ledger.receipt_ledger_issues(self.tmp, **kw)

    # ---- 核心：记录不许自证 ----

    def test_probe_only_in_the_record_section_is_rejected(self):
        """核心判据：探针只出现在版本表/返修记录里 → 记录自己把自己证明了，必须判失败。

        三例（≤0.98% / 66600 s / M3+热供给）都落在这里。
        """
        for probe, iid in (("≤0.98%", "rv2_provenance_numbers"),
                           ("66600", "rv2_mechanism_scope_minors"),
                           ("M3", "rv2_registry_contract_gaps")):
            self.ledger([{"id": i, "disposition": "not_applied", "reason": "占位"} for i in RECEIPT_IDS])
            self.ledger([{"id": iid, "disposition": "applied", "probe": probe}]
                        + [{"id": i, "disposition": "not_applied", "reason": "占位"}
                           for i in RECEIPT_IDS if i != iid])
            probs = self.check()
            self.assertEqual(len(probs), 1, probs)
            self.assertIn("版本/返修记录区", probs[0])
            self.assertIn(probe, probs[0])

    def test_probe_present_in_body_passes(self):
        """真改到正文 → 通过（防过度拦截：`Δt_end`/`6Robustness` 在 §2 正文里）。"""
        self.ledger([
            {"id": "rv2_provenance_numbers", "disposition": "applied", "probe": "Δt_end"},
            {"id": "rv2_mechanism_scope_minors", "disposition": "applied", "probe": "6Robustness"},
            {"id": "rv2_registry_contract_gaps", "disposition": "applied",
             "probe": "q4.moist_max_at_tend_minus_60s"},
        ])
        self.assertEqual(self.check(), [])

    # ---- 前缀碰撞 ----

    def test_ascii_probe_is_not_fooled_by_a_longer_identifier(self):
        """回执要的是 `q4.moist_max_at_tend`，只加了 `..._minus_60s` —— 不许算命中。

        正文里**只有** `q4.moist_max_at_tend_minus_60s`；探针以 `d` 结尾，后邻是 `_`，
        按标识符边界匹配应当拒掉这个命中。
        """
        lines = REPORT.splitlines()
        ev, rec = receipt_ledger._probe_hits(lines, receipt_ledger._record_zone(lines),
                                             "q4.moist_max_at_tend")
        self.assertEqual(ev, [], "被 _minus_60s 前缀撞上了 —— 前缀防护失效")
        self.assertTrue(rec, "记录区那一行应当命中（记录里确实写了这个串）")

    def test_prefix_hits_are_still_found_when_they_are_real(self):
        """反过来也要成立：真写了 `..._minus_60s` 就该命中，别把边界防护做成了全拒。"""
        lines = REPORT.splitlines()
        ev, _ = receipt_ledger._probe_hits(lines, receipt_ledger._record_zone(lines),
                                           "q4.moist_max_at_tend_minus_60s")
        self.assertEqual(ev, [5])

    def test_chinese_probe_still_matches_inside_chinese_text(self):
        """中文探针不能套 ASCII 边界规则 —— 否则两侧都是汉字，永远匹配不到。"""
        lines = REPORT.splitlines()
        ev, _ = receipt_ledger._probe_hits(lines, receipt_ledger._record_zone(lines), "对照模型")
        self.assertEqual(ev, [4])

    # ---- 诚实登记的口子必须留着 ----

    def test_honest_not_applied_passes_without_a_probe(self):
        """没做就写没做 —— 不逼人撒谎。review 下一轮照样会查，但那是它的活。"""
        self.ledger([
            {"id": "rv2_provenance_numbers", "disposition": "not_applied", "reason": "本轮时间不够"},
            {"id": "rv2_mechanism_scope_minors", "disposition": "deferred", "reason": "留给 6Robustness 实跑"},
            {"id": "rv2_registry_contract_gaps", "disposition": "not_applied", "reason": "登记表待重排"},
        ])
        self.assertEqual(self.check(), [])

    def test_not_applied_may_not_carry_a_probe(self):
        """没做的事不能有证据 —— 否则又变成"记录自证"。"""
        self.ledger([
            {"id": "rv2_provenance_numbers", "disposition": "not_applied", "reason": "x",
             "probe": "≤0.98%"},
            {"id": "rv2_mechanism_scope_minors", "disposition": "not_applied", "reason": "x"},
            {"id": "rv2_registry_contract_gaps", "disposition": "not_applied", "reason": "x"},
        ])
        self.assertEqual(len(self.check()), 1)

    def test_partial_must_say_what_is_left(self):
        """只做一半必须标 partial 并写 remaining，不许标 applied。"""
        self.ledger([
            {"id": "rv2_provenance_numbers", "disposition": "partial", "probe": "≤0.98%"},
            {"id": "rv2_mechanism_scope_minors", "disposition": "not_applied", "reason": "x"},
            {"id": "rv2_registry_contract_gaps", "disposition": "not_applied", "reason": "x"},
        ])
        probs = self.check()
        self.assertTrue(any("remaining" in p for p in probs), probs)

    # ---- 回执对账 ----

    def test_every_receipt_item_must_be_answered(self):
        """不许挑着答：回执 3 条只交代 1 条 → 报出漏的那两条。"""
        self.ledger([{"id": "rv2_provenance_numbers", "disposition": "not_applied", "reason": "x"}])
        probs = self.check()
        self.assertTrue(any("漏了回执里的 2 条" in p for p in probs), probs)

    def test_ids_not_in_the_receipt_are_rejected(self):
        self.ledger([{"id": i, "disposition": "not_applied", "reason": "x"} for i in RECEIPT_IDS]
                    + [{"id": "rv9_invented", "disposition": "not_applied", "reason": "x"}])
        self.assertTrue(any("不存在的 id" in p for p in self.check()))

    def test_ledger_pointing_at_the_wrong_receipt_is_rejected(self):
        """答错回执 = 答非所问：给了更新的回执却还在答旧的。"""
        self.receipt("runtime/quality/feedback/run2/def456/gate_decision.json",
                     {"issues": [{"id": "rv3_new"}]})
        self.ledger([{"id": i, "disposition": "not_applied", "reason": "x"} for i in RECEIPT_IDS])
        self.assertTrue(any("指错了" in p for p in self.check()))

    def test_missing_ledger_is_a_problem_when_a_receipt_exists(self):
        """带着回执跑却不交台账 → 必须报（否则等于没交代）。"""
        probs = self.check()
        self.assertEqual(len(probs), 1, probs)
        self.assertIn("缺返修台账", probs[0])
        self.assertIn(RECEIPT_REL, probs[0])

    def test_empty_receipt_directory_does_not_demand_a_ledger(self):
        """没有回执（干净工作区 / 首轮）→ 不要求台账，别把首轮卡死。"""
        shutil.rmtree(self.tmp / "runtime/quality/feedback")
        self.assertEqual(self.check(), [])
        self.assertTrue(any("缺返修台账" in p for p in self.check(require=True)))

    def test_malformed_ledger_is_reported_not_crashed(self):
        for bad in ("{not json", "[]", '{"schema_version": 2, "items": []}',
                    '{"schema_version": 1}'):
            (self.tmp / "reports/RECEIPT_LEDGER.json").write_text(bad, encoding="utf-8")
            self.assertTrue(self.check(), f"{bad!r} 应当报问题而不是崩")


# ---------------- 复合判词：一个探针不能签整条 ----------------
#
# 回执的 `fix` 里是 ①②③④ 四小项（补假设 / 改写理由 / 换论证方式 / 补披露清单）时，
# 只给一个探针（对应其中一个小项）就签 `applied`，会让「改了一半、记 applied」照样过关，
# 下一轮门禁再把剩下几项原样提出来。
COMPOUND_FIX = "① §5.2(b)/S18 补 S 级假设「ρ_d 沿 a 均匀」；② §6 P3 注与 S16 改写理由；" \
               "③ §6 P2 换逐点极值论证；④ §13.4 增补环境外推与 S16/S17 披露项。"
# recheck 把「复跑脚本」「复算常数」也编号进去了（6 项）—— 它**不**当分母，
# 否则会逼人给验证步骤编一个假探针。
COMPOUND_RECHECK = "① 逐行可复核；② 出含/不含压缩项数据；③ 检索「假设 S5」无误引；" \
                   "④ §13.4 项数=6；⑤ 重跑 check_contract.py 通过；⑥ 复算 μ₁=1.4185。"

BODY = {
    "a": "容量因子按 χ_i = ρ_d(C_i) + C_i·ρ_d'(C_i) 计，附录2 常数 ρ 时才退化为 ρ/(1+C)²。",
    "b": "压缩项量级：2|Ṙ|/R 均值/峰值 3.6×10⁻⁵–7.1×10⁻⁵ s⁻¹，与 1.97×10⁻⁴ s⁻¹ 之比 2.8–5.5。",
    "c": "P2 换逐点极值论证：min_t[C_s − C_air] > 0（末态余量约 5%）。",
    "d": "必修披露清单（6 项）已含 S8 环境外推与 S16/S17。",
}
COMPOUND_REPORT = ("# 报告\n\n## 5. 物性\n" + BODY["a"] + "\n\n## 6. 命题\n" + BODY["b"]
                   + "\n" + BODY["c"] + "\n\n## 13. 披露\n" + BODY["d"]
                   + "\n\n## 15. 版本与修订历史\n\n### 15.1 本轮返修复验记录\n\n"
                   "| 项 | 处置 |\n|---|---|\n| MA-1 | ① 已补假设 ② 已改写理由 ③ 已换论证 ④ 已补披露 |\n")
PROBES = [BODY["a"][:24], BODY["b"][:24], BODY["c"][:24], BODY["d"][:24]]


class CompoundReceiptTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        (self.tmp / "reports").mkdir()
        (self.tmp / "reports/ANALYSIS_MODELING_REPORT.md").write_text(
            COMPOUND_REPORT, encoding="utf-8")
        self.receipt_rel = "runtime/quality/feedback/r/1/gate_decision.json"
        p = self.tmp / self.receipt_rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({"issues": [
            {"id": "MA-1", "fix": COMPOUND_FIX, "recheck": COMPOUND_RECHECK}]},
            ensure_ascii=False), encoding="utf-8")

    def ledger(self, items):
        (self.tmp / "reports/RECEIPT_LEDGER.json").write_text(json.dumps({
            "schema_version": 1, "receipt": self.receipt_rel,
            "report": "reports/ANALYSIS_MODELING_REPORT.md", "items": items},
            ensure_ascii=False), encoding="utf-8")

    def check(self):
        return receipt_ledger.receipt_ledger_issues(self.tmp)

    def test_subitem_count_comes_from_fix_not_recheck(self):
        """分母取 `fix` 的小项数；`recheck` 里的验证步骤不算 —— 否则会逼人给验证步骤编探针。"""
        self.assertEqual(receipt_ledger._count_subitems(COMPOUND_FIX), 4)
        self.assertEqual(receipt_ledger._count_subitems(COMPOUND_RECHECK), 6)
        self.assertEqual(receipt_ledger._count_subitems("没有编号，一整条"), 1)
        self.assertEqual(receipt_ledger._count_subitems("① 只一项"), 1)
        self.assertEqual(receipt_ledger._count_subitems(None), 1)

    def test_applied_with_one_probe_on_a_compound_item_is_rejected(self):
        """4 小项只给 1 个探针就签 applied —— 必须判失败。"""
        self.ledger([{"id": "MA-1", "disposition": "applied", "probes": [PROBES[0]]}])
        probs = self.check()
        self.assertEqual(len(probs), 1, probs)
        self.assertIn("4 个", probs[0])
        self.assertIn("只给了 1 个探针", probs[0])

    def test_four_distinct_probes_pass(self):
        self.ledger([{"id": "MA-1", "disposition": "applied", "probes": PROBES}])
        self.assertEqual(self.check(), [])

    def test_partial_with_fewer_probes_still_allowed(self):
        """只做了一部分 → 标 partial + remaining，不逼它把没做的也编号。"""
        self.ledger([{"id": "MA-1", "disposition": "partial", "probes": [PROBES[0]],
                      "remaining": "②③④ 未做"}])
        self.assertEqual(self.check(), [])

    def test_partial_without_remaining_is_rejected(self):
        self.ledger([{"id": "MA-1", "disposition": "partial", "probes": [PROBES[0]]}])
        self.assertTrue(any("remaining" in p for p in self.check()))

    def test_sliced_probes_of_the_same_sentence_do_not_count(self):
        """拿同一句话的两截凑数不算逐小项给证据。"""
        a = BODY["a"]
        self.ledger([{"id": "MA-1", "disposition": "applied",
                      "probes": [a[:30], a[:16], a[:26], a[:22]]}])
        probs = self.check()
        self.assertTrue(any("一截" in p for p in probs), probs)

    def test_singular_probe_field_still_works_for_simple_items(self):
        """向后兼容：单小项的回执项，旧写法 `probe: "..."` 仍然有效。"""
        p = self.tmp / self.receipt_rel
        p.write_text(json.dumps({"issues": [{"id": "MA-1", "fix": "改成 χ_i 这个记号"}]},
                                ensure_ascii=False), encoding="utf-8")
        self.ledger([{"id": "MA-1", "disposition": "applied", "probe": PROBES[0]}])
        self.assertEqual(self.check(), [])


if __name__ == "__main__":
    unittest.main()
