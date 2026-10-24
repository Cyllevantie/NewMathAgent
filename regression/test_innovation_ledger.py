# -*- coding: utf-8 -*-
"""创新台账哨兵：基线/失败模式/test/delta 不能被“方法名”绕过。

这一组守的是 2026-10-20 加的 ②→③→④→⑤→⑥→⑨ 创新闭环：
- 字段与引用完整性（design）；
- adopted 必须真测过（code）；
- 测失败/复核失败必须降级（audit/write）；
- core 必须过稳健性（robustness/write）；
- 文档、agent 角色、指令依赖表不能漏接。
"""
import ast
import copy
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "lib" / "web"))

import check_innovation as ci  # noqa: E402

# ⑤/⑥ 的合格夹具：evidence 必须能被机械核对（≥12 字 + 路径样 token）；
# core 的 robustness 至少 2 项 what/result。各用例复用，避免同一形状散落几十份。
AUDIT_EVIDENCE = "⑤ 复算 results/innovation_checks.json，baseline/intervention 两列与代码输出一致"


def robust_checks():
    return [{"what": "D0 ±10%", "result": "t_dry 变化 4.2%，结论不变"},
            {"what": "h_m ±10%", "result": "t_dry 变化 2.8%，结论不变"}]


def base_ledger():
    return {
        "schema_version": 1,
        "report": "reports/ANALYSIS_MODELING_REPORT.md",
        "panel": {"lenses": ["mechanism", "data", "adversarial", "closure"],
                  "candidates": 9, "adopted": 1},
        "baselines": [
            {"id": "BASE-Q4", "question": "Q4",
             "model": "材料坐标一维径向有限体积，R(t) 取题给实测",
             "headline": "达标时间 t_dry", "unit": "h"},
            {"id": "BASE-Q4-N", "question": "Q4",
             "model": "固定域一维径向有限体积（朴素基线）",
             "headline": "达标时间 t_dry", "unit": "h"},
            {"id": "BASE-Q2", "question": "Q2",
             "model": "一维径向有限体积 + 题给物性",
             "headline": "72 h 末含水率", "unit": "kg/kg"},
            {"id": "BASE-Q1", "question": "Q1",
             "model": "一维径向有限体积 + 题给物性",
             "headline": "1800 s 末含水率", "unit": "kg/kg"},
        ],
        "items": [
            {
                "id": "INN-1", "question": "Q4", "lens": "mechanism",
                "type": "mechanism", "core": True, "baseline_id": "BASE-Q4",
                "failure_mode": "R(t) 只作输入，收缩与失水关系未被检验",
                "intervention": "用干物质守恒和失水量推导 R(t)，与实测对照",
                "claim": "若收缩由失水驱动，则预测 R(t) 与实测相对误差应在 3% 内",
                "predicted_delta": "t_dry 变化 3%–10%",
                "test": "同物性下跑 baseline 与 intervention，比较 t_dry 与 R(t) 误差",
                "kill_if": "R(t) 误差 >10%，或 t_dry 变化 <1%",
                "status": "adopted",
                "primary_guard": {
                    "metric": "t_dry",
                    "allowed_relative_change": 0.10,
                    "why": "题给物性与多数模型给出的量级；超过 10% 必须有独立证据",
                },
            },
            {
                "id": "INN-2", "question": "Q2", "lens": "adversarial",
                "type": "criterion", "core": False, "baseline_id": "BASE-Q2",
                "failure_mode": "平均值判据掩盖局部未达标",
                "intervention": "改用全场最大值判据",
                "claim": "若存在局部未达标，则平均判据会提前报达标",
                "predicted_delta": "达标时间推迟 5% 以上",
                "test": "同一结果分别按平均与最大值判据计算",
                "kill_if": "两种判据给出相同 t_dry",
                "status": "rejected",
                "reject_reason": "题面已要求全场最大值，属于硬约束，不作为创新",
            },
            {
                "id": "INN-3", "question": "Q1", "lens": "data",
                "type": "mechanism", "core": False, "baseline_id": "BASE-Q1",
                "failure_mode": "Ce=Y 可能高估干燥速率",
                "intervention": "引入 GAB 等温线并做可辨识性检验",
                "claim": "若参数可辨识，则 t_dry 增加 10% 以上",
                "predicted_delta": "t_dry 增加 10%–25%",
                "test": "用干燥曲线拟合 GAB，比较 baseline 与 intervention",
                "kill_if": "参数置信区间跨两个数量级",
                "status": "rejected",
                "reject_reason": "当前附件没有平衡含水率数据，参数不可辨识",
            },
        ],
        "no_adoption_reason": None,
    }


class InnovationLedgerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        (self.tmp / "reports").mkdir()
        (self.tmp / "results").mkdir()
        (self.tmp / "reports" / "ANALYSIS_MODELING_REPORT.md").write_text(
            "# 建模报告\n", encoding="utf-8")
        (self.tmp / "results" / "innovation_checks.json").write_text(
            '{"ok": true}\n', encoding="utf-8")
        self.ledger = base_ledger()

    def write(self, data=None):
        data = copy.deepcopy(self.ledger if data is None else data)
        items = data.get("items")
        items = items if isinstance(items, list) else []
        # 生产口径：设计台账只放设计字段；④/⑥/⑨ 各写自己的 sidecar。
        # 测试仍把下游字段挂在 self.ledger 上，这里统一拆到三份文件里。
        meas, rob, paper = {}, {}, {}
        for item in items:
            if not isinstance(item, dict) or not isinstance(item.get("id"), str):
                continue
            iid = item["id"]
            m = {}
            for key in ("measurement",):
                if key in item:
                    m[key] = item[key]
            for key in ("status", "downgrade_reason"):
                if key in item:
                    m[key] = item[key]
            if m:
                meas[iid] = m
            r = {}
            for key in ("robustness", "claim_scope", "core", "status", "downgrade_reason"):
                if key in item:
                    r[key] = item[key]
            if r:
                rob[iid] = r
            if "paper" in item:
                paper[iid] = {"paper": item["paper"]}
            for key in ci.DESIGN_ONLY:
                item.pop(key, None)
        (self.tmp / ci.LEDGER_REL).write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        for rel, payload in ((ci.MEASUREMENT_REL, meas), (ci.ROBUSTNESS_REL, rob),
                             (ci.PAPER_REL, paper)):
            (self.tmp / rel).write_text(
                json.dumps({"schema_version": 1, "items": payload},
                           ensure_ascii=False, indent=2), encoding="utf-8")

    def validate(self, stage):
        self.write()
        if stage in ("audit", "robustness", "write", "all"):
            items = self.ledger.get("items")
            items = items if isinstance(items, list) else []
            audits = {i["id"]: i["audit"] for i in items
                      if isinstance(i, dict) and isinstance(i.get("audit"), dict)}
            if audits:
                (self.tmp / "reports" / "INNOVATION_AUDIT.json").write_text(
                    json.dumps({"schema_version": 1, "items": audits},
                               ensure_ascii=False), encoding="utf-8")
        return ci.validate(self.tmp, stage)

    def assert_has(self, issues, needle):
        self.assertTrue(any(needle in x for x in issues),
                        "期望命中 %r，实际：%s" % (needle, issues))

    def add_measurement(self, passed=True, source="results/innovation_checks.json"):
        self.ledger["items"][0]["measurement"] = {
            "kind": "quantitative",
            "baseline_value": 50.8333,
            "intervention_value": 52.4,
            "delta": 1.5667,
            "delta_unit": "h",
            "relative": 0.0308,
            "source": source,
            "passed": passed,
            "note": "R(t) 最大相对误差 2.1%",
            "primary": {
                "metric": "t_dry",
                "baseline_value": 50.8333,
                "intervention_value": 52.4,
                "relative_change": 0.0308,
                "guard_passed": True,
            },
        }

    def reject_all(self):
        for item in self.ledger["items"]:
            item["status"] = "rejected"
            item["reject_reason"] = "测试用"

    def add_contribution(self, iid="INN-4"):
        item = {
            "id": iid, "question": "Q4", "lens": "closure", "type": "closure",
            "kind": "contribution", "core": False, "baseline_id": "BASE-Q4-N",
            "failure_mode": "R(t) 与 ρ_s(C) 同时当独立输入，干物质漂移 −10.98%",
            "intervention": "ρ_s∝R⁻² + 固体连续性；ρ_b(C) 只进热容",
            "claim": "闭合自洽时 M_s 守恒，t_dry 变化 ≤0.01%",
            "predicted_delta": "t_dry 51.2257→51.2205 h",
            "test": "同 solver 跑 appendix 与 consistent 热密度",
            "kill_if": "M_s 漂移仍 >1%",
            "status": "adopted",
            "contribution": "材料坐标下的自洽收缩闭合",
            "baseline_is_naive": "朴素基线把 R(t) 与 ρ_s(C) 同时当独立物理输入",
            "contribution_evidence": "results/innovation_checks.json",
            "measurement": {
                "kind": "quantitative", "baseline_value": 51.2257,
                "intervention_value": 51.2205, "delta": -0.0052,
                "delta_unit": "h", "source": "results/innovation_checks.json",
                "passed": True, "evidence": "results/q4_checks.json#heat_capacity",
            },
            "audit": {"verdict": "PASS",
                      "evidence": "按 results/q4_checks.json 复算 heat_capacity 变体与干物质漂移"},
            "paper": {"section": "2.5", "claim_id": "C4"},
        }
        self.ledger["items"].append(item)
        return item

    def test_valid_design_passes(self):
        self.assertEqual(self.validate("design"), [])

    def test_a_contribution_can_fill_2_5_without_primary_guard(self):
        """模型贡献（closure）只凭一致性/差值进 2.5，不套主答案护栏。"""
        for item in self.ledger["items"]:
            item["status"] = "rejected"
            item["reject_reason"] = "测试用"
        self.add_contribution()
        self.assertEqual(self.validate("write"), [])

    def test_a_contribution_without_evidence_is_rejected(self):
        self.reject_all()
        self.add_contribution()["contribution_evidence"] = ""
        self.assert_has(self.validate("design"), "contribution_evidence")

    def test_contribution_cap_is_enforced(self):
        """「模型特点与关键处理」最多 3 条；否则 2.5 会被写成方法清单。"""
        self.reject_all()
        for n in range(4):
            self.add_contribution(iid=f"INN-{10 + n}")
        self.assert_has(self.validate("design"), "最多 3 条")

    def test_contribution_delta_must_match_the_two_columns(self):
        """contribution 的差值也是证据，不能自报一个与 baseline/intervention 对不上的数。"""
        self.reject_all()
        item = self.add_contribution()
        item["measurement"]["delta"] = 0.5
        self.assert_has(self.validate("code"), "不一致")

    def test_contribution_must_not_carry_a_primary_guard(self):
        self.reject_all()
        item = self.add_contribution()
        item["primary_guard"] = {"metric": "t_dry",
                                 "allowed_relative_change": 0.1,
                                 "why": "测试用"}
        self.assert_has(self.validate("design"), "primary_guard 不应出现在 contribution")

    def test_contribution_measurement_must_not_carry_primary(self):
        self.reject_all()
        item = self.add_contribution()
        item["measurement"]["primary"] = {"metric": "t_dry", "guard_passed": True}
        self.assert_has(self.validate("code"), "primary 不应出现在 contribution")

    def test_contribution_core_must_be_false(self):
        self.reject_all()
        item = self.add_contribution()
        item["core"] = True
        self.assert_has(self.validate("design"), "core 必须是 false")
        item["core"] = None
        self.assert_has(self.validate("design"), "core 必须是 false")

    def test_contribution_write_requires_audit_pass(self):
        self.reject_all()
        item = self.add_contribution()
        item["audit"]["verdict"] = "FAIL"
        self.assert_has(self.validate("write"), "⑤ 复核不是 PASS")

    def test_panel_must_include_the_closure_lens(self):
        """4 个视角仍可能全是机制/数据/对抗 + 一个自定义补位，必须点名缺 closure。"""
        self.ledger["panel"]["lenses"] = ["mechanism", "data", "adversarial", "literature"]
        self.assert_has(self.validate("design"), "必须含 closure")

    def test_optimization_can_replace_closure_for_an_optimization_problem(self):
        """纯优化/决策题允许 optimization 顶替 closure（但 4 个视角仍需互不相同）。"""
        self.ledger["panel"]["lenses"] = ["mechanism", "data", "adversarial", "optimization"]
        issues = self.validate("design")
        self.assertFalse(any("closure" in x for x in issues), issues)

    def test_a_panel_of_only_mechanism_hypotheses_is_rejected(self):
        for item in self.ledger["items"]:
            item["type"] = "mechanism"
        self.assert_has(self.validate("design"), "模型层")

    def test_design_ledger_must_not_carry_downstream_fields(self):
        """measurement/robustness/paper 写回设计台账 = ② 的回执每轮自失效。"""
        self.ledger["items"][0]["measurement"] = {"passed": True}
        (self.tmp / ci.LEDGER_REL).write_text(
            json.dumps(self.ledger, ensure_ascii=False), encoding="utf-8")
        self.assert_has(ci.validate(self.tmp, "design"), "不属于设计台账")

    def test_sidecars_do_not_modify_the_design_ledger(self):
        """④⑥⑨ 只写自己的 sidecar；设计台账字节必须保持不变。"""
        self.write()
        before = (self.tmp / ci.LEDGER_REL).read_bytes()
        self.add_measurement()
        self.ledger["items"][0]["robustness"] = {
            "survives": True, "evidence": "做了扰动", "checks": robust_checks()}
        self.ledger["items"][0]["paper"] = {"section": "2.5", "claim_id": "C1"}
        self.write()
        self.assertEqual(before, (self.tmp / ci.LEDGER_REL).read_bytes(),
                         "写 sidecar 时顺手改了设计台账 —— ② 的回执会因此失效")

    def test_unknown_sidecar_id_is_rejected(self):
        self.write()
        (self.tmp / ci.MEASUREMENT_REL).write_text(
            json.dumps({"schema_version": 1, "items": {"NOPE": {"measurement": {}}}},
                       ensure_ascii=False), encoding="utf-8")
        self.assert_has(ci.validate(self.tmp, "code"), "不在设计台账")

    def test_missing_ledger_is_an_error(self):
        issues = ci.validate(self.tmp, "design")
        self.assert_has(issues, "缺创新台账")

    def test_panel_needs_four_lenses(self):
        """4 个不同视角 + closure 后，adversarial/optimization 已被集合大小隐含。"""
        self.ledger["panel"]["lenses"] = ["mechanism", "data", "adversarial"]
        self.assert_has(self.validate("design"), "至少要有 4 个不同视角")

    def test_panel_needs_three_candidates(self):
        self.ledger["panel"]["candidates"] = 2
        self.assert_has(self.validate("design"), "panel.candidates")

    def test_fewer_than_three_items_fails(self):
        self.ledger["items"] = self.ledger["items"][:2]
        self.assert_has(self.validate("design"), "至少要有 3 个候选")

    def test_adopted_missing_failure_mode_fails(self):
        self.ledger["items"][0]["failure_mode"] = ""
        self.assert_has(self.validate("design"), "failure_mode")

    def test_item_question_must_match_its_baseline(self):
        self.ledger["items"][0]["question"] = "Q9"
        self.assert_has(self.validate("design"), "不一致")

    def test_adopted_missing_test_or_kill_if_fails(self):
        for key in ("test", "kill_if"):
            data = copy.deepcopy(self.ledger)
            data["items"][0][key] = ""
            self.write(data)
            self.assert_has(ci.validate(self.tmp, "design"), key)

    def test_adopted_missing_primary_guard_fails(self):
        del self.ledger["items"][0]["primary_guard"]
        self.assert_has(self.validate("design"), "主答案护栏")

    def test_primary_guard_threshold_must_be_a_fraction(self):
        self.ledger["items"][0]["primary_guard"]["allowed_relative_change"] = 10
        self.assert_has(self.validate("design"), "10% 写 0.10")

    def test_code_requires_primary_answer(self):
        self.add_measurement()
        del self.ledger["items"][0]["measurement"]["primary"]
        self.assert_has(self.validate("code"), "primary")

    def test_primary_guard_failure_needs_independent_evidence(self):
        self.add_measurement()
        self.ledger["items"][0]["measurement"]["primary"].update({
            "intervention_value": 5.42,
            "relative_change": -0.893,
            "guard_passed": False,
        })
        self.assert_has(self.validate("code"), "independent_evidence")

    def test_primary_guard_flag_must_match_values(self):
        self.add_measurement()
        self.ledger["items"][0]["measurement"]["primary"].update({
            "intervention_value": 5.42,
            "relative_change": -0.893,
            "guard_passed": True,
        })
        self.assert_has(self.validate("code"), "不一致")

    def test_core_count_is_capped(self):
        second = copy.deepcopy(self.ledger["items"][0])
        second.update({"id": "INN-2b", "status": "adopted", "core": True})
        self.ledger["items"].append(second)
        self.assert_has(self.validate("design"), "最多 1 个核心创新")

    def test_no_adoption_needs_reason(self):
        for item in self.ledger["items"]:
            item["status"] = "rejected"
            item["reject_reason"] = "测试用"
        self.assert_has(self.validate("design"), "no_adoption_reason")

    def test_all_adopted_downgraded_is_allowed_after_design(self):
        self.ledger["items"][0].update({
            "status": "downgraded",
            "downgrade_reason": "④ 测出主答案偏离 84%，且无独立证据",
        })
        self.assertEqual(self.validate("code"), [])

    def test_no_adopted_and_no_downgrade_is_rejected_after_design(self):
        for item in self.ledger["items"]:
            item["status"] = "rejected"
            item["reject_reason"] = "测试用"
        self.assert_has(self.validate("code"), "downgraded")

    def test_no_adoption_reason_is_allowed_until_write_but_2_5_cannot_be_empty(self):
        """no_adoption_reason 允许 ②-⑥ 诚实收尾；但 ⑨ 不能把 2.5 写空。

        2026-10-24 用户口径：论文不能“啥都没有”。只写 no_adoption_reason 会让 2.5 空着，
        write 阶段必须打回 ② 补一条 contribution（模型特点与关键处理）。
        """
        for item in self.ledger["items"]:
            item["status"] = "rejected"
            item["reject_reason"] = "本题没有值得做的增量"
        self.ledger["no_adoption_reason"] = "题面只要求复现标准扩散模型，额外闭合无数据支持"
        for stage in ("design", "code", "audit", "robustness"):
            self.assertEqual(self.validate(stage), [], stage)
        for stage in ("write", "all"):
            self.assert_has(self.validate(stage), "2.5 不能为空")

    def test_code_requires_measurement(self):
        self.assert_has(self.validate("code"), "measurement")

    def test_code_source_must_exist(self):
        self.add_measurement(source="results/not_there.json")
        self.assert_has(self.validate("code"), "source 指向的文件不存在")

    def test_code_failed_measurement_must_be_downgraded(self):
        self.add_measurement(passed=False)
        issues = self.validate("code")
        self.assert_has(issues, "passed=false")
        self.assert_has(issues, "downgraded")

    def test_code_valid_passes(self):
        self.add_measurement()
        self.assertEqual(self.validate("code"), [])

    def test_audit_requires_verdict(self):
        self.add_measurement()
        self.assert_has(self.validate("audit"), "audit")

    def test_audit_fail_is_allowed_at_audit_but_blocks_robustness_and_write(self):
        self.add_measurement()
        self.ledger["items"][0]["audit"] = {"verdict": "FAIL", "evidence": AUDIT_EVIDENCE}
        self.assertEqual(self.validate("audit"), [])
        self.assert_has(self.validate("robustness"), "未 PASS")
        self.ledger["items"][0]["robustness"] = {
            "survives": True, "evidence": "三组扰动方向一致", "checks": robust_checks()}
        self.ledger["items"][0]["paper"] = {"section": "2.5", "claim_id": "C-INN-1"}
        self.assert_has(self.validate("write"), "复核不是 PASS")

    def test_embedded_audit_without_external_file_is_rejected(self):
        self.add_measurement()
        self.ledger["items"][0]["audit"] = {"verdict": "PASS", "evidence": AUDIT_EVIDENCE}
        self.write()
        issues = ci.validate(self.tmp, "audit")
        self.assert_has(issues, "INNOVATION_AUDIT")

    def test_embedded_audit_plus_empty_external_is_rejected(self):
        self.add_measurement()
        self.ledger["items"][0]["audit"] = {"verdict": "PASS", "evidence": AUDIT_EVIDENCE}
        self.write()
        (self.tmp / "reports" / "INNOVATION_AUDIT.json").write_text(
            '{"schema_version": 1, "items": {}}', encoding="utf-8")
        issues = ci.validate(self.tmp, "write")
        self.assert_has(issues, "audit")

    def test_external_audit_must_cover_every_adopted_item(self):
        self.add_measurement()
        extra = copy.deepcopy(self.ledger["items"][0])
        extra.update({"id": "INN-2b", "core": False})
        self.ledger["items"].append(extra)
        self.write()
        (self.tmp / "reports" / "INNOVATION_AUDIT.json").write_text(
            json.dumps({"schema_version": 1,
                        "items": {"INN-1": {"verdict": "PASS", "evidence": AUDIT_EVIDENCE}}},
                       ensure_ascii=False), encoding="utf-8")
        issues = ci.validate(self.tmp, "write")
        self.assert_has(issues, "INN-2b.audit")

    def test_audit_valid_passes(self):
        self.add_measurement()
        self.ledger["items"][0]["audit"] = {"verdict": "PASS", "evidence": AUDIT_EVIDENCE}
        self.assertEqual(self.validate("audit"), [])

    def test_external_audit_file_is_merged(self):
        self.add_measurement()
        (self.tmp / "reports" / "INNOVATION_AUDIT.json").write_text(
            json.dumps({"schema_version": 1,
                        "items": {"INN-1": {"verdict": "PASS", "evidence": AUDIT_EVIDENCE}}},
                       ensure_ascii=False), encoding="utf-8")
        self.assertEqual(self.validate("audit"), [])

    def test_external_audit_unknown_id_fails(self):
        self.add_measurement()
        (self.tmp / "reports" / "INNOVATION_AUDIT.json").write_text(
            json.dumps({"schema_version": 1,
                        "items": {"NOPE": {"verdict": "PASS", "evidence": AUDIT_EVIDENCE}}},
                       ensure_ascii=False), encoding="utf-8")
        self.assert_has(self.validate("audit"), "不在台账里")

    def test_primary_metric_must_match_guard(self):
        self.add_measurement()
        self.ledger["items"][0]["measurement"]["primary"]["metric"] = "某个次要指标"
        self.assert_has(self.validate("code"), "不能换一个主答案")

    def test_qualitative_primary_answer_is_allowed(self):
        self.add_measurement()
        self.ledger["items"][0]["primary_guard"]["metric"] = "最大值位置"
        self.ledger["items"][0]["measurement"]["primary"] = {
            "kind": "qualitative", "metric": "最大值位置",
            "baseline_value": "中心", "intervention_value": "中心",
            "guard_passed": True,
        }
        self.assertEqual(self.validate("code"), [])

    def test_primary_guard_failure_with_independent_evidence_passes_code(self):
        self.add_measurement()
        self.ledger["items"][0]["measurement"]["primary"].update({
            "intervention_value": 5.42,
            "relative_change": -0.893,
            "guard_passed": False,
            "independent_evidence": "题面空气温度 41.5 ℃，原模型 33.6 ℃ 与文献量级一致",
        })
        self.assertEqual(self.validate("code"), [])

    def test_robustness_required_for_core(self):
        self.add_measurement()
        self.ledger["items"][0]["audit"] = {"verdict": "PASS", "evidence": AUDIT_EVIDENCE}
        self.assert_has(self.validate("robustness"), "robustness")

    def test_robustness_failure_needs_claim_scope(self):
        self.add_measurement()
        self.ledger["items"][0]["audit"] = {"verdict": "PASS", "evidence": AUDIT_EVIDENCE}
        self.ledger["items"][0]["robustness"] = {
            "survives": False, "evidence": "h_m 扰动下方向反转", "checks": robust_checks()}
        issues = self.validate("robustness")
        self.assert_has(issues, "claim_scope")

    def test_robustness_valid_passes(self):
        self.add_measurement()
        self.ledger["items"][0]["audit"] = {"verdict": "PASS", "evidence": AUDIT_EVIDENCE}
        self.ledger["items"][0]["robustness"] = {
            "survives": True, "evidence": "三组扰动方向一致",
            "checks": [{"what": "D0 ±10%", "result": "方向不变"},
                       {"what": "h_m ±10%", "result": "方向不变"}]}
        self.assertEqual(self.validate("robustness"), [])

    def test_robustness_checks_must_be_two_items(self):
        """只有 survives/evidence 不算稳健性检验：SKILL ⑥ 要求 checks 至少 2 项。"""
        self.add_measurement()
        self.ledger["items"][0]["audit"] = {"verdict": "PASS", "evidence": AUDIT_EVIDENCE}
        for checks in (None, [{"what": "D0 ±10%", "result": "方向不变"}]):
            rob = {"survives": True, "evidence": "三组扰动方向一致"}
            if checks is not None:
                rob["checks"] = checks
            self.ledger["items"][0]["robustness"] = rob
            self.assert_has(self.validate("robustness"), "checks")

    def test_robustness_checks_need_distinct_what_and_result(self):
        self.add_measurement()
        self.ledger["items"][0]["audit"] = {"verdict": "PASS", "evidence": AUDIT_EVIDENCE}
        self.ledger["items"][0]["robustness"] = {
            "survives": True, "evidence": "三组扰动方向一致",
            "checks": [{"what": "D0 ±10%", "result": "方向不变"},
                       {"what": "D0  ±10%", "result": "方向不变"}]}
        self.assert_has(self.validate("robustness"), "重复")
        self.ledger["items"][0]["robustness"]["checks"] = [
            {"what": "D0 ±10%", "result": ""},
            {"what": "h_m ±10%", "result": "方向不变"}]
        self.assert_has(self.validate("robustness"), "result")
        self.ledger["items"][0]["robustness"]["checks"] = [
            {"what": "", "result": "方向不变"},
            {"what": "h_m ±10%", "result": "方向不变"}]
        self.assert_has(self.validate("robustness"), "what")

    def test_write_requires_paper_mapping(self):
        self.add_measurement()
        self.ledger["items"][0]["audit"] = {"verdict": "PASS", "evidence": AUDIT_EVIDENCE}
        self.ledger["items"][0]["robustness"] = {
            "survives": True, "evidence": "三组扰动方向一致", "checks": robust_checks()}
        self.assert_has(self.validate("write"), "paper")

    def test_write_core_must_be_in_2_5(self):
        self.add_measurement()
        self.ledger["items"][0]["audit"] = {"verdict": "PASS", "evidence": AUDIT_EVIDENCE}
        self.ledger["items"][0]["robustness"] = {
            "survives": True, "evidence": "三组扰动方向一致", "checks": robust_checks()}
        self.ledger["items"][0]["paper"] = {"section": "5.4", "claim_id": "C1"}
        self.assert_has(self.validate("write"), "必须是 2.5")

    def test_write_fails_when_primary_guard_fails_without_evidence(self):
        self.add_measurement()
        self.ledger["items"][0]["measurement"]["primary"].update({
            "intervention_value": 5.42,
            "relative_change": -0.893,
            "guard_passed": False,
        })
        self.ledger["items"][0]["audit"] = {"verdict": "PASS", "evidence": AUDIT_EVIDENCE}
        self.ledger["items"][0]["robustness"] = {
            "survives": True, "evidence": "三组扰动方向一致", "checks": robust_checks()}
        self.ledger["items"][0]["paper"] = {"section": "2.5", "claim_id": "C-INN-1"}
        self.assert_has(self.validate("write"), "不能写进 2.5")

    def test_write_guard_failure_with_evidence_still_cannot_be_in_2_5(self):
        self.add_measurement()
        self.ledger["items"][0]["measurement"]["primary"].update({
            "intervention_value": 5.42,
            "relative_change": -0.893,
            "guard_passed": False,
            "independent_evidence": "题面空气温度 41.5 ℃，原模型 33.6 ℃ 与文献量级一致",
        })
        self.ledger["items"][0]["audit"] = {"verdict": "PASS", "evidence": AUDIT_EVIDENCE}
        self.ledger["items"][0]["robustness"] = {
            "survives": True, "evidence": "三组扰动方向一致", "checks": robust_checks()}
        self.ledger["items"][0]["paper"] = {"section": "2.5", "claim_id": "C-INN-1"}
        self.assert_has(self.validate("write"), "不能写进 2.5")

    def test_downgraded_item_cannot_be_written_into_2_5(self):
        self.add_measurement()
        self.ledger["items"][0]["audit"] = {"verdict": "PASS", "evidence": AUDIT_EVIDENCE}
        self.ledger["items"][0]["robustness"] = {
            "survives": True, "evidence": "三组扰动方向一致", "checks": robust_checks()}
        self.ledger["items"][0]["paper"] = {"section": "2.5", "claim_id": "C-INN-1"}
        self.ledger["items"][0]["status"] = "downgraded"
        self.ledger["items"][0]["downgrade_reason"] = "测试失败"
        self.assert_has(self.validate("write"), "rejected/downgraded")

    def test_rejected_item_cannot_be_written_into_2_5(self):
        self.add_measurement()
        self.ledger["items"][0]["audit"] = {"verdict": "PASS", "evidence": AUDIT_EVIDENCE}
        self.ledger["items"][0]["robustness"] = {
            "survives": True, "evidence": "三组扰动方向一致", "checks": robust_checks()}
        self.ledger["items"][0]["paper"] = {"section": "2.5", "claim_id": "C-INN-1"}
        self.ledger["items"][1]["paper"] = {"section": "2.5", "claim_id": "C-INN-2"}
        self.assert_has(self.validate("write"), "rejected/downgraded")

    def test_guard_failed_supporting_can_live_in_model_section(self):
        self.add_measurement()
        self.ledger["items"][0]["core"] = False
        self.ledger["items"][0]["measurement"]["primary"].update({
            "intervention_value": 5.42,
            "relative_change": -0.893,
            "guard_passed": False,
            "independent_evidence": "题面空气温度 41.5 ℃，原模型 33.6 ℃ 与文献量级一致",
        })
        self.ledger["items"][0]["audit"] = {"verdict": "PASS", "evidence": AUDIT_EVIDENCE}
        self.ledger["items"][0]["robustness"] = {
            "survives": True, "evidence": "三组扰动方向一致", "checks": robust_checks()}
        self.ledger["items"][0]["paper"] = {"section": "5.4", "claim_id": "C-INN-1"}
        self.assertEqual(self.validate("write"), [])

    def test_failed_robustness_supporting_cannot_be_in_2_5(self):
        self.add_measurement()
        self.ledger["items"][0]["core"] = False
        self.ledger["items"][0]["audit"] = {"verdict": "PASS", "evidence": AUDIT_EVIDENCE}
        self.ledger["items"][0]["robustness"] = {
            "survives": False, "evidence": "扰动下反转", "checks": robust_checks()}
        self.ledger["items"][0]["claim_scope"] = "仅在低 h_m 时成立"
        self.ledger["items"][0]["paper"] = {"section": "2.5", "claim_id": "C1"}
        self.assert_has(self.validate("write"), "robustness.survives")

    def test_write_valid_passes(self):
        self.add_measurement()
        self.ledger["items"][0]["audit"] = {"verdict": "PASS", "evidence": AUDIT_EVIDENCE}
        self.ledger["items"][0]["robustness"] = {
            "survives": True, "evidence": "三组扰动方向一致", "checks": robust_checks()}
        self.ledger["items"][0]["paper"] = {"section": "2.5", "claim_id": "C-INN-1"}
        self.assertEqual(self.validate("write"), [])

    def test_fake_relative_change_is_recomputed_and_rejected(self):
        self.add_measurement()
        self.ledger["items"][0]["measurement"]["primary"].update({
            "baseline_value": 33.6,
            "intervention_value": 5.4,
            "relative_change": 0.03,
            "guard_passed": True,
        })
        self.assert_has(self.validate("code"), "不一致")

    def test_delta_must_match_baseline_and_intervention(self):
        self.add_measurement()
        self.ledger["items"][0]["measurement"]["delta"] = 99
        self.assert_has(self.validate("code"), "delta")

    def test_core_must_be_boolean_on_adopted(self):
        del self.ledger["items"][0]["core"]
        self.assert_has(self.validate("design"), "core 必须是")

    def test_duplicate_item_ids_are_rejected(self):
        self.ledger["items"][1]["id"] = "INN-1"
        self.assert_has(self.validate("design"), "id 重复")

    def test_empty_source_is_rejected(self):
        self.add_measurement(source="")
        self.assert_has(self.validate("code"), "source 必须")

    def test_non_dict_measurement_does_not_crash_write(self):
        self.ledger["items"][0]["measurement"] = "done"
        self.ledger["items"][0]["audit"] = {"verdict": "PASS", "evidence": AUDIT_EVIDENCE}
        self.ledger["items"][0]["robustness"] = {
            "survives": True, "evidence": "三组扰动方向一致", "checks": robust_checks()}
        self.ledger["items"][0]["paper"] = {"section": "2.5", "claim_id": "C1"}
        issues = self.validate("write")
        self.assert_has(issues, "measurement 缺失")

    def test_items_null_does_not_crash_audit(self):
        self.ledger["items"] = None
        issues = self.validate("audit")
        self.assert_has(issues, "items")

    def test_huge_numbers_cannot_bypass_delta_check(self):
        self.add_measurement()
        self.ledger["items"][0]["measurement"].update({
            "baseline_value": 1e308, "intervention_value": -1e308, "delta": 0})
        self.assert_has(self.validate("code"), "差值溢出")

    def test_placeholder_none_text_is_rejected(self):
        self.add_measurement()
        self.ledger["items"][0]["measurement"]["primary"].update({
            "intervention_value": 5.42, "relative_change": -0.8934,
            "guard_passed": False, "independent_evidence": "None"})
        self.assert_has(self.validate("code"), "independent_evidence")

    def test_nan_relative_change_is_rejected(self):
        self.add_measurement()
        self.ledger["items"][0]["measurement"]["primary"]["relative_change"] = float("nan")
        self.assert_has(self.validate("code"), "有限数值")

    def test_schema_version_bool_is_rejected(self):
        self.ledger["schema_version"] = True
        self.assert_has(self.validate("design"), "schema_version")

    def test_core_with_failed_robustness_must_be_downgraded(self):
        self.add_measurement()
        self.ledger["items"][0]["audit"] = {"verdict": "PASS", "evidence": AUDIT_EVIDENCE}
        self.ledger["items"][0]["robustness"] = {
            "survives": False, "evidence": "扰动下反转", "checks": robust_checks()}
        self.ledger["items"][0]["claim_scope"] = "仅在 h_m 较低时成立"
        self.assert_has(self.validate("robustness"), "不能继续保留 core")

    def test_write_rechecks_robustness(self):
        self.add_measurement()
        self.ledger["items"][0]["audit"] = {"verdict": "PASS", "evidence": AUDIT_EVIDENCE}
        self.ledger["items"][0]["paper"] = {"section": "2.5", "claim_id": "C1"}
        self.assert_has(self.validate("write"), "robustness")

    def test_stage_all_runs_write_checks(self):
        self.add_measurement()
        self.ledger["items"][0]["audit"] = {"verdict": "PASS", "evidence": AUDIT_EVIDENCE}
        self.ledger["items"][0]["robustness"] = {
            "survives": True, "evidence": "三组扰动方向一致", "checks": robust_checks()}
        self.ledger["items"][0]["paper"] = {"section": "2.5", "claim_id": "C1"}
        self.assertEqual(self.validate("all"), [])

    def test_missing_report_is_rejected(self):
        self.ledger["report"] = "reports/NOPE.md"
        self.assert_has(self.validate("design"), "不存在")

    def test_dangling_baseline_id_is_rejected(self):
        self.ledger["items"][0]["baseline_id"] = "NOPE"
        self.assert_has(self.validate("design"), "不存在")

    def test_adopted_cap_is_enforced(self):
        second = copy.deepcopy(self.ledger["items"][0])
        second.update({"id": "INN-9", "core": False})
        third = copy.deepcopy(second)
        third.update({"id": "INN-10"})
        self.ledger["items"].extend([second, third])
        self.assert_has(self.validate("design"), "adopted 有")

    def test_rejected_without_reason_is_rejected(self):
        del self.ledger["items"][1]["reject_reason"]
        self.assert_has(self.validate("design"), "reject_reason")

    def test_empty_audit_evidence_is_rejected(self):
        self.add_measurement()
        self.ledger["items"][0]["audit"] = {"verdict": "PASS", "evidence": ""}
        self.assert_has(self.validate("audit"), "evidence 必须")

    def test_audit_evidence_must_name_a_product_path(self):
        """只判非空时 "x" 就能过；现在要求 ≥12 字且含路径样 token。"""
        self.add_measurement()
        for bad in ("x", "两列一致"):
            self.ledger["items"][0]["audit"] = {"verdict": "PASS", "evidence": bad}
            self.assert_has(self.validate("audit"), "evidence 必须")
        # 反向对照：合格复核记录（指认 results/ 产物）照常通过。
        self.ledger["items"][0]["audit"] = {"verdict": "PASS", "evidence": AUDIT_EVIDENCE}
        self.assertEqual(self.validate("audit"), [])

    def test_quantitative_fields_must_be_numeric(self):
        self.add_measurement()
        self.ledger["items"][0]["measurement"]["delta"] = "n/a"
        self.assert_has(self.validate("code"), "必须是有限数值")

    def test_qualitative_empty_answer_is_rejected(self):
        self.add_measurement()
        self.ledger["items"][0]["primary_guard"]["metric"] = "最大值位置"
        self.ledger["items"][0]["measurement"]["primary"] = {
            "kind": "qualitative", "metric": "最大值位置",
            "baseline_value": None, "intervention_value": "",
            "guard_passed": True,
        }
        self.assert_has(self.validate("code"), "baseline_value")

    def test_cli_exit_codes(self):
        self.write()
        p = subprocess.run(
            [sys.executable, str(PROJECT / "lib" / "web" / "check_innovation.py"),
             "--root", str(self.tmp), "--stage", "design", "--json"],
            capture_output=True, text=True, encoding="utf-8", errors="replace")
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertEqual(json.loads(p.stdout)["status"], "PASS")

        broken = copy.deepcopy(self.ledger)
        broken["items"][0]["failure_mode"] = ""
        self.write(broken)
        p = subprocess.run(
            [sys.executable, str(PROJECT / "lib" / "web" / "check_innovation.py"),
             "--root", str(self.tmp), "--stage", "design", "--json"],
            capture_output=True, text=True, encoding="utf-8", errors="replace")
        self.assertEqual(p.returncode, 1, p.stdout + p.stderr)
        self.assertEqual(json.loads(p.stdout)["status"], "FAIL")

        (self.tmp / ci.LEDGER_REL).unlink()
        p = subprocess.run(
            [sys.executable, str(PROJECT / "lib" / "web" / "check_innovation.py"),
             "--root", str(self.tmp), "--stage", "design"],
            capture_output=True, text=True, encoding="utf-8", errors="replace")
        self.assertEqual(p.returncode, 2, p.stdout + p.stderr)

    def test_ledger_input_tracking_avoids_self_invalidation(self):
        tree = ast.parse((PROJECT / "lib/web/server.py").read_text(encoding="utf-8"))
        table = None
        for node in tree.body:
            if (isinstance(node, ast.Assign)
                    and any(isinstance(t, ast.Name) and t.id == "_EXTRA_INPUT_PATHS"
                            for t in node.targets)):
                table = ast.literal_eval(node.value)
                break
        self.assertIsInstance(table, dict, "没找到 _EXTRA_INPUT_PATHS")
        ledger = "reports/INNOVATION_LEDGER.json"
        meas = "reports/INNOVATION_MEASUREMENT.json"
        rob = "reports/INNOVATION_ROBUSTNESS.json"
        paper = "reports/INNOVATION_PAPER.json"
        audit = "reports/INNOVATION_AUDIT.json"
        # 各阶段只把自己的产物排除在输入之外；别人的 sidecar 可以只读。
        self.assertIn(ledger, table.get("code", []))
        self.assertNotIn(meas, table.get("code", []),
                         "④ 写 measurement，不能把它当自己的输入")
        self.assertIn(ledger, table.get("robustness", []))
        self.assertIn(meas, table.get("robustness", []))
        self.assertNotIn(rob, table.get("robustness", []),
                         "⑥ 写 robustness，不能把它当自己的输入")
        self.assertIn(ledger, table.get("write", []))
        self.assertIn(meas, table.get("write", []))
        self.assertIn(rob, table.get("write", []))
        self.assertNotIn(paper, table.get("write", []),
                         "⑨ 写 paper sidecar，不能把它当自己的输入")
        self.assertIn(ledger, table.get("review", []))
        self.assertIn(ledger, table.get("audit", []))
        self.assertIn(meas, table.get("audit", []))
        self.assertIn(audit, table.get("robustness", []))
        self.assertIn(audit, table.get("write", []))

    def test_new_artifacts_are_declared(self):
        tree = ast.parse((PROJECT / "lib/web/server.py").read_text(encoding="utf-8"))
        table = None
        for node in tree.body:
            if (isinstance(node, ast.Assign)
                    and any(isinstance(t, ast.Name) and t.id == "ARTIFACTS"
                            for t in node.targets)):
                table = ast.literal_eval(node.value)
                break
        self.assertIsInstance(table, dict, "没找到 ARTIFACTS")
        self.assertIn("reports/INNOVATION_LEDGER.json", table.get("analysis", []))
        self.assertIn("reports/INNOVATION_MEASUREMENT.json", table.get("code", []))
        self.assertIn("reports/INNOVATION_ROBUSTNESS.json", table.get("robustness", []))
        self.assertIn("reports/INNOVATION_PAPER.json", table.get("write", []))
        self.assertIn("reports/INNOVATION_AUDIT.json", table.get("audit", []))
        self.assertIn("reports/AI_TOOL_USAGE.json", table.get("write", []))
        # 设计台账不能被下游写成自己的产物：analysis 只列 design。
        for stage in ("code", "robustness", "write", "audit"):
            self.assertNotIn("reports/INNOVATION_LEDGER.json", table.get(stage, []),
                             f"{stage} 不该把设计台账当自己的产物")

    def test_docs_and_roles_are_wired(self):
        stage2 = (PROJECT / "skills/2Modeling-design/SKILL.md").read_text(encoding="utf-8")
        for token in ("INNOVATION_LEDGER.json", "基线卡", "可证伪", "主答案", "护栏",
                      "check_innovation.py", "idea-adversarial"):
            self.assertIn(token, stage2, token)
        gate = (PROJECT / "skills/3Modeling-review-gate/SKILL.md").read_text(encoding="utf-8")
        for token in ("创新审计", "INNOVATION_LEDGER.json", "review-innovation",
                      "check_innovation.py"):
            self.assertIn(token, gate, token)
        for rel in ("skills/4Coding-and-computation/SKILL.md",
                    "skills/5Result-credibility-audit/SKILL.md",
                    "skills/6Robustness/SKILL.md",
                    "skills/9Paper-writing/SKILL.md"):
            text = (PROJECT / rel).read_text(encoding="utf-8")
            self.assertIn("INNOVATION_LEDGER.json", text, rel)
            self.assertIn("check_innovation.py", text, rel)
        for rel in ("skills/5Result-credibility-audit/SKILL.md",
                    "skills/6Robustness/SKILL.md",
                    "skills/9Paper-writing/SKILL.md"):
            self.assertIn("INNOVATION_AUDIT.json",
                          (PROJECT / rel).read_text(encoding="utf-8"), rel)
        for rel, sidecar in (
            ("skills/4Coding-and-computation/SKILL.md", "INNOVATION_MEASUREMENT.json"),
            ("skills/5Result-credibility-audit/SKILL.md", "INNOVATION_MEASUREMENT.json"),
            ("skills/6Robustness/SKILL.md", "INNOVATION_ROBUSTNESS.json"),
            ("skills/9Paper-writing/SKILL.md", "INNOVATION_PAPER.json"),
        ):
            self.assertIn(sidecar, (PROJECT / rel).read_text(encoding="utf-8"), rel)
        ledger_doc = (PROJECT / "skills/2Modeling-design/references/innovation-ledger.md").read_text(
            encoding="utf-8")
        for sidecar in ("INNOVATION_MEASUREMENT.json", "INNOVATION_ROBUSTNESS.json",
                        "INNOVATION_PAPER.json", "INNOVATION_AUDIT.json"):
            self.assertIn(sidecar, ledger_doc, sidecar)

        agents = json.loads((PROJECT / "config/agents.json").read_text(encoding="utf-8"))
        for role in ("idea-adversarial", "review-innovation"):
            self.assertIn(role, agents)

        server = (PROJECT / "lib/web/server.py").read_text(encoding="utf-8")
        tree = ast.parse(server)
        table = None
        for node in tree.body:
            if (isinstance(node, ast.Assign)
                    and any(isinstance(t, ast.Name) and t.id == "_LIB_INSTRUCTION_USERS"
                            for t in node.targets)):
                table = ast.literal_eval(node.value)
                break
        self.assertIsInstance(table, dict, "没找到 _LIB_INSTRUCTION_USERS")
        self.assertEqual(
            table.get("lib/web/check_innovation.py"),
            {"analysis", "review", "code", "audit", "robustness", "write"},
        )


if __name__ == "__main__":
    unittest.main()
