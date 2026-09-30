"""Real-defect fixtures: the gate must keep catching the 2024C failures.

These encode the four defects found on 2024C (plus the 2025A-style
model-vs-writing mis-route). They are the safety net for any slimming/robustness
change: "减负不降拦截力" means A-D must stay green before AND after every change
to content_quality/workflow_quality/skills.

Offline only: fabricate request + modeling report + typed verdicts, call the
real content_quality module. No model runner, no competition code.

ForwardRoutingTest (fixture E) pins the routing of a presentation/claim defect
found at an early gate: it must not brick the verdict, and it must land on a
stage that can actually fix it. A-D must pass on the untouched tree.
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "lib" / "web"))
from content_quality import REQUIRED, enforce, task_contract_issues

STAGES = ["intake", "literature", "analysis", "review", "code", "audit", "robustness", "drawio", "figreview", "write",
          "mathproof", "cross", "rubric", "fix", "format", "verify", "demo"]
          # ↑ 必须与 lib/web/server.py 的 STAGES 顺序一致：它决定 category→返修阶段的
          #   先后比较（backward/forward 判定），顺序漂了会让路由语义静默失真。

# The actual 2024C wording (abridged) and the flawed model text.
PROBLEM = ("根据经验，小麦和玉米未来的预期销售量有增长的趋势，平均年增长率介于5%~10%之间，"
           "其他农作物未来每年的预期销售量相对于2023年大约有±5%的变化。"
           "因含有豆类作物根菌的土壤有利于其他作物生长，从2023年开始要求每个地块（含大棚）"
           "的所有土地三年内至少种植一次豆类作物。")
MODEL = ("模型将其他作物销量设为逐年连乘：d_t = d_2023 * prod_{k<=t}(1+u_k)，u_k~U(-5%,5%)。"
         "豆类约束按‘该地块在窗口内至少种植过一次豆类’实现，不校验豆类覆盖面积占比。"
         "命题3 由各期决策互不牵制推出总期望可加，据此称该解为自适应意义下的最优值。")


def make_root():
    root = Path(tempfile.mkdtemp())
    (root / "request").mkdir()
    (root / "reports").mkdir()
    (root / "request/problem.md").write_text(PROBLEM, encoding="utf-8")
    (root / "reports/ANALYSIS_MODELING_REPORT.md").write_text(MODEL, encoding="utf-8")
    return root


def write_contract(root, *, demand_time, legume_scope):
    spec = {"schema_version": 1, "requirements": [
        {"id": "demand_trajectory",
         "source": {"file": "request/problem.md", "quote": "相对于2023年大约有±5%的变化"},
         "source_semantics": {"quantifier": "each", "scope": "each crop each year",
                              "unit": "kg", "time_reference": demand_time},
         "model_semantics": {"quantifier": "each", "scope": "each crop each year",
                             "unit": "kg", "time_reference": "growth_chain"},
         "model_anchor": {"file": "reports/ANALYSIS_MODELING_REPORT.md",
                          "quote": "模型将其他作物销量设为逐年连乘"},
         "status": "mapped"},
        {"id": "legume_all_land",
         "source": {"file": "request/problem.md", "quote": "的所有土地三年内至少种植一次豆类作物"},
         "source_semantics": {"quantifier": "all", "scope": "all land of each plot",
                              "unit": "area", "time_reference": "rolling_3y"},
         "model_semantics": {"quantifier": "at_least_one", "scope": legume_scope,
                             "unit": "area", "time_reference": "rolling_3y"},
         "model_anchor": {"file": "reports/ANALYSIS_MODELING_REPORT.md",
                          "quote": "至少种植过一次豆类"},
         "status": "mapped"}]}
    (root / "reports/TASK_CONTRACT.json").write_text(
        json.dumps(spec, ensure_ascii=False), encoding="utf-8")


def ev(root):
    return [{"file": "request/problem.md", "quote": "相对于2023年大约有±5%的变化"},
            {"file": "reports/ANALYSIS_MODELING_REPORT.md", "quote": "至少种植过一次豆类"}]


def decision(root, stage, failed_id, category, *, severity="soft", status="REVISE"):
    checks = [{"id": cid, "status": "failed" if cid == failed_id else "passed",
               "reason": "checked", "evidence": ev(root)}
              for cid in REQUIRED[stage]]
    return {"schema_version": 2, "stage": stage, "input_digest": "d", "status": status,
            "reason": "structured", "checks": checks,
            "issues": [{"id": "x1", "category": category, "check_ids": [failed_id],
                        "severity": severity, "evidence": "缺陷证据",
                        "fix": "按题意修复", "recheck": "复算"}]}


class EvidenceAnchorTest(unittest.TestCase):
    """引文核验（`_evidence`）的**负例**。

    为什么必须有：把 `content_quality.py` 里那句 `_evidence(root, check["evidence"])`
    整行删掉，**135 个用例全绿** —— 这条"引文必须真的出现在项目文件里"的反幻觉护栏
    零测试覆盖：删掉它之后，一份 checks 全 passed、引文纯属捏造的裁决会从
    `UNVERIFIED/verdict_malformed` 变成 **`APPROVED/structured`**。
    仓库里唯一提到失败文案的地方是 `test_workflow.py` 里一句手写字符串（喂给纯字符串判断的
    `_protocol_repair`），根本不经过 `_evidence`。
    """

    def _verdict(self, root, quote, fname="request/problem.md"):
        checks = [{"id": cid, "status": "passed", "reason": "checked",
                   "evidence": [{"file": fname, "quote": quote}]}
                  for cid in REQUIRED["review"]]
        return {"schema_version": 2, "stage": "review", "input_digest": "d",
                "status": "APPROVED", "reason": "structured", "checks": checks, "issues": []}

    def test_genuine_quote_passes(self):
        """反向对照：真引文必须能通过 —— 否则下面三条可能只是"永远拒绝"。"""
        root = make_root()
        out = enforce(root, "review", self._verdict(root, PROBLEM[:30]), STAGES)
        self.assertEqual(out["status"], "APPROVED")

    def test_tampered_quote_is_rejected(self):
        root = make_root()
        out = enforce(root, "review", self._verdict(root, "这句话在题面里根本不存在"), STAGES)
        self.assertEqual(out["status"], "UNVERIFIED")
        self.assertEqual(out["reason"], "verdict_malformed")
        self.assertIn("Evidence quote does not match", out["issues"][0]["evidence"])

    def test_binary_evidence_is_rejected(self):
        """二进制文件不能当引文来源（否则可用一张 png 骗过核验）。"""
        root = make_root()
        (root / "request/pic.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"x" * 40)
        out = enforce(root, "review", self._verdict(root, "随便", fname="request/pic.png"), STAGES)
        self.assertEqual(out["status"], "UNVERIFIED")
        self.assertIn("text source anchor", out["issues"][0]["evidence"])

    def test_evidence_outside_project_is_rejected(self):
        """项目外的文件不能当引文来源。"""
        root = make_root()
        out = enforce(root, "review", self._verdict(root, "x", fname="../outside.md"), STAGES)
        self.assertEqual(out["status"], "UNVERIFIED")
        self.assertIn("outside project", out["issues"][0]["evidence"])


class StageTableTest(unittest.TestCase):
    """本文件里的 `STAGES` 是**第三份副本**（另两份在 server.py 与前端），必须与驱动一致。

    把驱动侧 `server.py` 的 `audit` 与 `robustness` 对调，这两份测试副本仍会**全绿**
    —— 没有任何机制把它们对起来，而它们参与 backward/forward 判定的 index 比较，
    顺序漂了会让下面那些 `test_*_routes_to_*` 断言在断言一个不存在的设计。
    """

    def test_local_stages_match_driver(self):
        import ast
        src = (PROJECT / "lib" / "web" / "server.py").read_text(encoding="utf-8-sig")
        driver = []
        for node in ast.parse(src).body:
            if (isinstance(node, ast.Assign) and node.targets
                    and getattr(node.targets[0], "id", "") == "STAGES"):
                driver = [v.value for elt in node.value.elts for k, v in zip(elt.keys, elt.values)
                          if getattr(k, "value", "") == "id"]
        self.assertTrue(driver, "没能从 server.py 解析出 STAGES")
        self.assertEqual(STAGES, driver, "本文件的 STAGES 副本与驱动不一致（含顺序）")


class DefectCatchTest(unittest.TestCase):
    """A-D: must pass before and after the slimming/robustness pass."""

    def test_A_stochastic_trajectory_mismatch_is_caught(self):
        """2024C 缺陷①: '每年相对2023 ±5%' implemented as a year-on-year chain."""
        root = make_root()
        write_contract(root, demand_time="fixed_base", legume_scope="all land of each plot")
        issues = task_contract_issues(root)
        self.assertTrue(any("demand_trajectory" in i for i in issues), issues)

    def test_A_review_soft_tagged_stochastic_defect_still_routes_to_analysis(self):
        root = make_root()
        write_contract(root, demand_time="fixed_base", legume_scope="all land of each plot")
        out = enforce(root, "review",
                      decision(root, "review", "stochastic_semantics", "stochastic_model",
                               severity="soft"), STAGES)
        self.assertEqual(out["status"], "NEEDS_FIX")
        self.assertEqual(out["target"], "analysis")
        self.assertEqual([i["severity"] for i in out["issues"]], ["hard"])

    def test_B_legume_scope_weakening_is_caught(self):
        """2024C 缺陷②: '所有土地' weakened to '发生过一次'."""
        root = make_root()
        write_contract(root, demand_time="fixed_base", legume_scope="any occurrence")
        issues = task_contract_issues(root)
        self.assertTrue(any("legume_all_land" in i for i in issues), issues)

    def test_B_review_quantifier_defect_routes_to_analysis(self):
        root = make_root()
        write_contract(root, demand_time="fixed_base", legume_scope="all land of each plot")
        out = enforce(root, "review",
                      decision(root, "review", "quantifiers", "constraint_model"), STAGES)
        self.assertEqual(out["status"], "NEEDS_FIX")
        self.assertEqual(out["target"], "analysis")

    def test_C_unproven_optimality_routes_to_producer_not_wording(self):
        """2024C 缺陷③: 命题给未收敛数值解背书 → 结果可信度问题，必须回生产阶段，不得只改措辞。"""
        root = make_root()
        write_contract(root, demand_time="fixed_base", legume_scope="all land of each plot")
        out = enforce(root, "mathproof",
                      decision(root, "mathproof", "optimality", "claim"), STAGES)
        self.assertEqual(out["status"], "NEEDS_FIX")
        self.assertEqual(out["target"], "code")

    def test_C_pure_proof_text_error_may_route_to_writing(self):
        """纯文稿推导错误（proof_validity）才允许回写作。"""
        root = make_root()
        write_contract(root, demand_time="fixed_base", legume_scope="all land of each plot")
        out = enforce(root, "mathproof",
                      decision(root, "mathproof", "proof_validity", "claim"), STAGES)
        self.assertEqual(out["status"], "NEEDS_FIX")
        self.assertEqual(out["target"], "write")

    def test_C_optimality_rooted_in_model_cannot_be_waved_as_claim(self):
        root = make_root()
        write_contract(root, demand_time="fixed_base", legume_scope="all land of each plot")
        out = enforce(root, "mathproof",
                      decision(root, "mathproof", "optimality", "validation"), STAGES)
        self.assertEqual(out["status"], "NEEDS_FIX")
        self.assertEqual(out["target"], "code")

    def test_D_solving_shortfall_explained_as_risk_is_not_accepted(self):
        """2024C 缺陷④: dominated candidate explained as '主动让渡期望' -> code."""
        root = make_root()
        write_contract(root, demand_time="fixed_base", legume_scope="all land of each plot")
        out = enforce(root, "audit",
                      decision(root, "audit", "comparison_validity", "validation"), STAGES)
        self.assertEqual(out["status"], "NEEDS_FIX")
        self.assertEqual(out["target"], "code")
        self.assertNotEqual(out["status"], "REVISE_CLAIM")


class ForwardRoutingTest(unittest.TestCase):
    """E: an early-gate finding must route, not brick the verdict."""

    def test_E_early_gate_no_longer_bricks_on_writing_style_finding(self):
        """早期门禁报文稿类缺陷时不得 raise 成 UNVERIFIED 卡死，必须掰回能改的阶段。"""
        root = make_root()
        write_contract(root, demand_time="fixed_base", legume_scope="all land of each plot")
        out = enforce(root, "review",
                      decision(root, "review", "task_fidelity", "presentation"), STAGES)
        self.assertNotEqual(out["status"], "UNVERIFIED")
        self.assertEqual(out["status"], "NEEDS_FIX")       # 错分类防护把它掰回 analysis
        self.assertEqual(out["target"], "analysis")

    def test_E_forward_shape_with_model_category_still_routes_back(self):
        root = make_root()
        write_contract(root, demand_time="fixed_base", legume_scope="all land of each plot")
        out = enforce(root, "review",
                      decision(root, "review", "task_fidelity", "stochastic_model"), STAGES)
        self.assertEqual(out["status"], "NEEDS_FIX")
        self.assertEqual(out["target"], "analysis")

    def test_E_miscategorized_model_defect_cannot_be_deferred_as_writing(self):
        """错分类防护：task_fidelity 失败却填 presentation → 仍强制回 analysis，不得延后放行。"""
        root = make_root()
        write_contract(root, demand_time="fixed_base", legume_scope="all land of each plot")
        out = enforce(root, "review",
                      decision(root, "review", "task_fidelity", "presentation"), STAGES)
        self.assertEqual(out["status"], "NEEDS_FIX")
        self.assertEqual(out["target"], "analysis")
        self.assertEqual([i["severity"] for i in out["issues"]], ["hard"])

    def test_E_miscategorized_implementation_defect_at_review_routes_back(self):
        """错分类防护：review 上把 implementation 类缺陷填成别的类别，也必须回生产阶段。"""
        root = make_root()
        write_contract(root, demand_time="fixed_base", legume_scope="all land of each plot")
        out = enforce(root, "review",
                      decision(root, "review", "task_fidelity", "implementation"), STAGES)
        self.assertEqual(out["status"], "NEEDS_FIX")
        self.assertEqual(out["target"], "analysis")

    def test_E_genuine_presentation_issue_on_late_gate_is_advisory(self):
        """verify 上 narrative 类检查失败且确属版式/图文 → 回 format（不是 write）。

        presentation 的 producer 是 format（专用排版阶段），排在 verify 之前 → 向后返修。
        这正是「版式问题不该拖整篇写作重跑」那条设计的机器判据：目标必须落在 format。
        """
        root = make_root()
        write_contract(root, demand_time="fixed_base", legume_scope="all land of each plot")
        out = enforce(root, "verify",
                      decision(root, "verify", "narrative_consistency", "presentation"), STAGES)
        self.assertNotEqual(out["status"], "UNVERIFIED")
        self.assertEqual(out["status"], "NEEDS_FIX")   # format 在 verify 之前 → 向后返修
        self.assertEqual(out["target"], "format")

    def test_E_diagram_defect_on_late_gate_routes_to_drawio(self):
        """verify 上判「图本身画错了」→ 回 drawio 重画，而不是回 write 重写论文。"""
        root = make_root()
        write_contract(root, demand_time="fixed_base", legume_scope="all land of each plot")
        out = enforce(root, "verify",
                      decision(root, "verify", "narrative_consistency", "diagram"), STAGES)
        self.assertNotEqual(out["status"], "UNVERIFIED")
        self.assertEqual(out["status"], "NEEDS_FIX")
        self.assertEqual(out["target"], "drawio")

    def test_stage_order_out_of_sync_is_reported_as_driver_side(self):
        """调用方的阶段顺序表与 TARGETS 不同步时，必须报成「驱动侧」问题。

        若直接抛 `list.index(x): x not in list`，会被 enforce 的宽 except 吞成
        `verdict_malformed`，而那条 fix 文案让 agent「去改裁决 JSON」—— 根本不是这里的问题，
        纯属误导（真正该改的是调用 enforce() 时传进来的 stage_order）。
        """
        root = make_root()
        write_contract(root, demand_time="fixed_base", legume_scope="all land of each plot")
        old12 = ["literature", "analysis", "review", "code", "drawio", "robustness",
                 "audit", "write", "mathproof", "cross", "verify", "demo"]     # 缺 format
        out = enforce(root, "verify",
                      decision(root, "verify", "narrative_consistency", "presentation"), old12)
        self.assertEqual(out["status"], "UNVERIFIED")
        self.assertEqual(out["reason"], "stage_order_mismatch")
        self.assertIn("format", out["issues"][0]["evidence"])
        self.assertIn("驱动侧", out["issues"][0]["fix"])
        # 反向对照：顺序表补齐后行为不变（不是「永远拒绝」）
        ok = enforce(root, "verify",
                     decision(root, "verify", "narrative_consistency", "presentation"), STAGES)
        self.assertEqual(ok["status"], "NEEDS_FIX")

    def test_audit_can_issue_revise_claim_via_claim_scope(self):
        """audit 必须**能**发 REVISE_CLAIM，且不能因此削弱反洗白。

        若 audit 的必查项全在 `RESULT_CHECK_CATEGORY` 反推表里，任何 failed 的
        category 都会被掰回 analysis/code → 「全部未解决项均为 claim」永不成立 → REVISE_CLAIM
        不可达。于是「算得没错、只是报告里话说满了」这种审计，要么被判 UNVERIFIED 卡住
        （不填 issue 时），要么被转成**回退重算**（填了 issue 时）—— 而它本意只是改一句话。
        所以给 audit 补一个**不在反推表里**的必查项 `claim_scope` 作为唯一通道。
        """
        root = make_root()
        write_contract(root, demand_time="fixed_base", legume_scope="all land of each plot")
        out = enforce(root, "audit",
                      decision(root, "audit", "claim_scope", "claim"), STAGES)
        self.assertEqual(out["status"], "REVISE_CLAIM")
        self.assertEqual(out["reason"], "content_repair_required")
        self.assertNotIn("target", out)          # 有条件交接，不是往后返修
        # 反向对照：同一句 claim 挂在**反推表内**的检查项上，仍必须被掰回生产阶段
        #   —— 否则"claim_scope"就成了给模型缺陷洗白的后门。
        out2 = enforce(root, "audit",
                       decision(root, "audit", "comparison_validity", "claim"), STAGES)
        self.assertEqual(out2["status"], "NEEDS_FIX")
        self.assertEqual(out2["target"], "code")

    def test_E_reviewer_category_is_overridden_by_check_id_at_audit(self):
        """audit 上审查者把 comparison_validity 失败填成 experiment，仍按检查项反推路由到 code。

        audit 的 REQUIRED 检查项**全部**都在 RESULT_CHECK_CATEGORY 反推表里，
        因此 audit 上任何一条 failed 检查的 category 都会被反推覆盖 ——
        `experiment`（→robustness）在 audit 上**根本不可达**。

        推论（写进这里免得后人重蹈）：把 audit 前移到 robustness 之前，**并不会**让
        audit 的实验类缺陷变成 forward/advisory —— 它压根产生不出 experiment 类缺陷。
        前移的收益只有「便宜的先跑，结果不可信时不白跑昂贵的 robustness」这一条成本论，
        与路由无关。
        """
        root = make_root()
        write_contract(root, demand_time="fixed_base", legume_scope="all land of each plot")
        out = enforce(root, "audit",
                      decision(root, "audit", "comparison_validity", "experiment"), STAGES)
        self.assertEqual(out["status"], "NEEDS_FIX")
        self.assertEqual(out["issues"][0]["category"], "validation")   # 被反推覆盖
        self.assertEqual(out["target"], "code")


if __name__ == "__main__":
    unittest.main()
