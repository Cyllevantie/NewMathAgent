"""Content-quality contract: task-fidelity mapping and typed repair routing.

Offline only: fabricate a request + modeling report + review verdict and call the
real content_quality module (no model runner, no competition code).
Locks the intent behind docs/CONTENT_QUALITY.md:
  * model/semantic mismatch with the problem statement is a defect even when the
    reviewer tries to tag it soft;
  * constraint/stochastic/task errors route back to analysis, not writing.
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "lib" / "web"))
import content_quality as cq
from content_quality import REQUIRED, task_contract_issues, enforce

STAGES = ["intake", "literature", "analysis", "review", "code", "audit", "robustness", "drawio", "figreview", "write",
          "mathproof", "cross", "rubric", "fix", "format", "verify", "demo"]
          # ↑ 必须与 lib/web/server.py 的 STAGES 顺序一致：它决定 category→返修阶段的
          #   先后比较（backward/forward 判定），顺序漂了会让路由语义静默失真。


def make_root():
    root = Path(tempfile.mkdtemp())
    (root / "request").mkdir()
    (root / "reports").mkdir()
    (root / "request/problem.md").write_text(
        "每种作物预期销售量每年相对2023年约±5%变化。三年内所有土地至少种一次豆类。",
        encoding="utf-8")
    (root / "reports/ANALYSIS_MODELING_REPORT.md").write_text(
        "模型将销量写为逐年连乘 d_t = d_2023 * prod(1+u_k)。豆类只要求地块种过即可。",
        encoding="utf-8")
    return root


def write_contract(root, source_ref, model_ref):
    spec = {"schema_version": 1, "requirements": [{
        "id": "demand_ref",
        "source": {"file": "request/problem.md", "quote": "每年相对2023年约±5%变化"},
        "source_semantics": {"quantifier": "each", "scope": "each crop", "unit": "kg",
                             "time_reference": source_ref},
        "model_semantics": {"quantifier": "each", "scope": "each crop", "unit": "kg",
                            "time_reference": model_ref},
        "model_anchor": {"file": "reports/ANALYSIS_MODELING_REPORT.md",
                         "quote": "模型将销量写为逐年连乘"},
        "status": "mapped"}]}
    (root / "reports/TASK_CONTRACT.json").write_text(
        json.dumps(spec, ensure_ascii=False), encoding="utf-8")


def checks_for(root, state_by_id):
    ev_q1 = {"file": "request/problem.md", "quote": "相对2023年约±5%变化"}
    ev_q2 = {"file": "reports/ANALYSIS_MODELING_REPORT.md", "quote": "逐年连乘"}
    return [{"id": cid, "status": state_by_id.get(cid, "passed"),
             "reason": "checked", "evidence": [ev_q1, ev_q2]}
            for cid in REQUIRED["review"]]


class ContentQualityTest(unittest.TestCase):
    def test_mapped_contract_passes_and_mismatch_flags(self):
        root = make_root()
        write_contract(root, "fixed_base", "fixed_base")
        self.assertEqual(task_contract_issues(root), [])
        write_contract(root, "fixed_base", "growth_chain")   # 题面固定基期 vs 模型连乘
        issues = task_contract_issues(root)
        self.assertEqual(len(issues), 1)
        self.assertIn("demand_ref", issues[0])

    def test_soft_tagged_stochastic_error_still_routes_to_analysis(self):
        root = make_root()
        write_contract(root, "fixed_base", "fixed_base")
        decision = {"schema_version": 2, "stage": "review", "input_digest": "d",
                    "status": "REVISE", "reason": "structured",
                    "checks": checks_for(root, {"stochastic_semantics": "failed"}),
                    "issues": [{"id": "s1", "category": "stochastic_model",
                                "check_ids": ["stochastic_semantics"], "severity": "soft",
                                "evidence": "模型把固定基期波动写成逐年连乘",
                                "fix": "d_t = d_2023*(1+u_t)",
                                "recheck": "re-run"}]}
        out = enforce(root, "review", decision, STAGES)
        self.assertEqual(out["status"], "NEEDS_FIX")
        self.assertEqual(out["target"], "analysis")
        self.assertEqual([i["severity"] for i in out["issues"]], ["hard"])

    def test_passed_review_is_unchanged(self):
        root = make_root()
        decision = {"schema_version": 2, "stage": "review", "input_digest": "d",
                    "status": "APPROVED", "reason": "structured",
                    "checks": checks_for(root, {}), "issues": []}
        out = enforce(root, "review", decision, STAGES)
        self.assertEqual(out["status"], "APPROVED")

    def test_multi_check_issue_routes_to_earliest_producer_regardless_of_order(self):
        """一条 issue 挂多个 failed 检查时，按最早的生产阶段路由，与书写顺序无关。"""
        root = make_root()
        for order in (["implementation_fidelity", "task_fidelity"],
                      ["task_fidelity", "implementation_fidelity"]):
            checks = [{"id": c, "status": "failed" if c in order else "passed", "reason": "ok",
                       "evidence": [{"file": "request/problem.md", "quote": "相对2023年约±5%变化"}]}
                      for c in REQUIRED["audit"]]
            out = enforce(root, "audit", {"schema_version": 2, "stage": "audit", "input_digest": "d",
                                          "reason": "structured", "status": "REVISE", "checks": checks,
                                          "issues": [{"id": "i1", "category": "implementation",
                                                      "check_ids": order, "severity": "hard",
                                                      "evidence": "e", "fix": "f", "recheck": "r"}]}, STAGES)
            self.assertEqual(out["target"], "analysis")   # 题意级缺陷优先回 analysis

    def test_audit_claim_tag_on_result_check_cannot_handoff_to_writing(self):
        """optimality 属结果可信度检查：即使标 claim 也必须回生产阶段。"""
        root = make_root()
        checks = [{"id": c, "status": "failed" if c == "optimality" else "passed",
                   "reason": "ok", "evidence": [{"file": "request/problem.md",
                                                 "quote": "相对2023年约±5%变化"}]}
                  for c in REQUIRED["audit"]]
        out = enforce(root, "audit", {"schema_version": 2, "stage": "audit", "input_digest": "d",
                                      "reason": "structured", "status": "REVISE_CLAIM",
                                      "checks": checks,
                                      "issues": [{"id": "c1", "category": "claim",
                                                  "check_ids": ["optimality"], "severity": "soft",
                                                  "evidence": "数值对但措辞过强",
                                                  "fix": "降级措辞", "recheck": "seen"}]}, STAGES)
        self.assertEqual(out["status"], "NEEDS_FIX")
        self.assertEqual(out["target"], "code")

    def test_failed_check_with_empty_issues_cannot_pass(self):
        """侧车自相矛盾（某必查项 failed 却 status=PASS 且 issues:[]）必须拦下。

        覆盖率校验若挂在 `if typed:` 里面 —— issues 为空时 typed 也为空 ⇒ 整段被跳过 ⇒
        这份侧车被原样放行为 PASS。加上 v2 没有 v1 那条「批准不能与未解决项矛盾」的兜底
        （`workflow_quality.read_verdict` 只对 `schema_version==1` 生效），
        结果就是"自认未证明最优性/比较有效性"的审计静默过关、直达写作与终验。
        """
        root = make_root()
        checks = [{"id": c, "status": "failed" if c in {"optimality", "comparison_validity"} else "passed",
                   "reason": "ok", "evidence": [{"file": "request/problem.md",
                                                 "quote": "相对2023年约±5%变化"}]}
                  for c in REQUIRED["audit"]]
        out = enforce(root, "audit", {"schema_version": 2, "stage": "audit", "input_digest": "d",
                                      "reason": "structured", "status": "PASS",
                                      "checks": checks, "issues": []}, STAGES)
        self.assertEqual(out["status"], "UNVERIFIED")
        self.assertEqual(out["reason"], "verdict_malformed")

    def test_all_checks_passed_with_no_issues_still_passes(self):
        """反向护栏：全部检查 passed 且无 issue 时仍正常放行，别把合法空集也拦死。"""
        root = make_root()
        checks = [{"id": c, "status": "passed", "reason": "ok",
                   "evidence": [{"file": "request/problem.md", "quote": "相对2023年约±5%变化"}]}
                  for c in REQUIRED["audit"]]
        out = enforce(root, "audit", {"schema_version": 2, "stage": "audit", "input_digest": "d",
                                      "reason": "structured", "status": "PASS",
                                      "checks": checks, "issues": []}, STAGES)
        self.assertEqual(out["status"], "PASS")

    def test_audit_claim_only_handoff_still_works_for_textual_checks(self):
        """门禁必查项若含文稿类检查（如 narrative_consistency），纯 claim 仍可交接写作。"""
        import content_quality as cq
        original = cq.REQUIRED["audit"]
        cq.REQUIRED["audit"] = ["narrative_consistency"]
        try:
            root = make_root()
            out = enforce(root, "audit", {"schema_version": 2, "stage": "audit", "input_digest": "d",
                                          "reason": "structured", "status": "REVISE_CLAIM",
                                          "checks": [{"id": "narrative_consistency", "status": "failed",
                                                      "reason": "ok",
                                                      "evidence": [{"file": "request/problem.md",
                                                                    "quote": "相对2023年约±5%变化"}]}],
                                          "issues": [{"id": "c1", "category": "claim",
                                                      "check_ids": ["narrative_consistency"],
                                                      "severity": "soft", "evidence": "措辞过强",
                                                      "fix": "降级措辞", "recheck": "seen"}]}, STAGES)
            self.assertEqual(out["status"], "REVISE_CLAIM")
            self.assertNotIn("target", out)
        finally:
            cq.REQUIRED["audit"] = original

    def test_audit_model_issue_cannot_be_waved_as_claim(self):
        root = make_root()
        checks = [{"id": c, "status": "failed" if c == "stochastic_semantics" else "passed",
                   "reason": "ok", "evidence": [{"file": "request/problem.md",
                                                 "quote": "相对2023年约±5%变化"}]}
                  for c in REQUIRED["audit"]]
        out = enforce(root, "audit", {"schema_version": 2, "stage": "audit", "input_digest": "d",
                                      "reason": "structured", "status": "REVISE_CLAIM",
                                      "checks": checks,
                                      "issues": [{"id": "m1", "category": "stochastic_model",
                                                  "check_ids": ["stochastic_semantics"], "severity": "hard",
                                                  "evidence": "随机过程不符题意", "fix": "改模型",
                                                  "recheck": "re-run"}]}, STAGES)
        self.assertEqual(out["status"], "NEEDS_FIX")
        self.assertEqual(out["target"], "analysis")


class CrossNarrativeHandoffTest(unittest.TestCase):
    """11Cross-question-check：**纯措辞类判词不该把整链停下**。

    判词全是 `narrative_consistency` + `category=claim`（文稿表述不自洽）时，若每轮都判 FAIL
    ⇒ 整链停在 ⑪（`severity` 若不被消费，soft 与 hard 一样拦链）。
    处置与 `audit` 同一条路 —— 纯 claim 交写作（REVISE_CLAIM ⇒ 清单进 ⑨ 的 hint + 终验核查），
    不拦链；而挂在 `comparison_validity` 上的实质项（反推成 validation）照旧 NEEDS_FIX。
    """

    def _verdict(self, failed, issues):
        return {"schema_version": 2, "stage": "cross", "input_digest": "d",
                "reason": "structured", "status": "FAIL",
                "checks": [{"id": c, "status": "failed" if c in failed else "passed",
                            "reason": "ok",
                            "evidence": [{"file": "request/problem.md",
                                          "quote": "相对2023年约±5%变化"}]}
                           for c in REQUIRED["cross"]],
                "issues": issues}

    def test_narrative_only_verdict_hands_off_to_writing(self):
        root = make_root()
        out = enforce(root, "cross", self._verdict(
            ["narrative_consistency"],
            [{"id": "Y-1", "category": "claim", "check_ids": ["narrative_consistency"],
              "severity": "soft", "evidence": "图 1 的「主档」标注与正文定义相反",
              "fix": "改图注", "recheck": "重看图"}]), STAGES)
        self.assertEqual(out["status"], "REVISE_CLAIM",
                         "纯措辞类判词应当交接写作，而不是把链停在 ⑪")
        self.assertNotIn("target", out)

    def test_a_substantive_issue_on_comparison_validity_still_blocks(self):
        """反向守卫：判词挂在 comparison_validity 上（反推成 validation）⇒ 照旧 NEEDS_FIX。

        就算审查者把 category 填成 claim 也拦得住 —— 那是 `_effective_category` 的
        错分类防护，不是审查者自觉。
        """
        root = make_root()
        out = enforce(root, "cross", self._verdict(
            ["comparison_validity"],
            [{"id": "Y-9", "category": "claim", "check_ids": ["comparison_validity"],
              "severity": "soft", "evidence": "两问的对比基准不同却并列",
              "fix": "统一基准", "recheck": "重算"}]), STAGES)
        self.assertEqual(out["status"], "NEEDS_FIX")
        self.assertEqual(out["target"], "code")     # validation → code


def rubric_decision(root, failed, issues, status="FAIL"):
    """rubric 的 v2 侧车：**必须逐项声明全部 5 个必查项**，通过项也要写。"""
    anchor = {"file": "request/problem.md", "quote": "相对2023年约±5%变化"}
    return {"schema_version": 2, "stage": "rubric", "input_digest": "d", "reason": "structured",
            "status": status,
            "checks": [{"id": cid, "status": "failed" if cid in failed else "passed",
                        "reason": "checked", "evidence": [anchor]}
                       for cid in REQUIRED["rubric"]],
            "issues": issues}


def rubric_issue(iid, category, check_ids, tier=None):
    d = {"id": iid, "category": category, "check_ids": check_ids, "severity": "hard",
         "evidence": "判词原文", "fix": "改法", "recheck": "复验"}
    if tier:
        d["tier"] = tier
    return d


class RubricRoutingTest(unittest.TestCase):
    """12Rubric-final 是唯一有**正向**出路的门禁，路由规则与其余五道都不同。

    这里守的三条不变量（每条都有反向对照）：
      ① 论文侧判词 → 正向交 13Repair-by-rubric-verdict，不回退 write（写是小时级）；
      ② 只要混有模型/数值/实现类判词，就整单回退到生产阶段，fix 这轮不跑；
      ③ 只有「严重/中等」清零才算过 —— 只剩 optional 时放行，不卡链。
    """

    def test_paper_side_claim_goes_forward_to_fix(self):
        root = make_root()
        out = enforce(root, "rubric", rubric_decision(
            root, ["rubric_trace"],
            [rubric_issue("r1", "claim", ["rubric_trace"], "must")]), STAGES)
        self.assertEqual(out["status"], "NEEDS_FIX")
        self.assertEqual(out["target"], "fix")

    def test_a_layout_only_redline_is_deferred_not_routed_downstream(self):
        """⑫ 的硬项全是版式类时：**不许**路由到排在 ⑫ 之后的 14Layout-and-format。

        ⑭ 排在 ⑫ 之后，而只排掉 claim 的 `backward` 会把 presentation 也算成"可回退"，
        `min(..., key=stage_order.index)` 于是吐出一个**后序** target ⇒ 驱动 `_target_index`
        拒绝（只认前序）、黄灯上连推荐目标都没有，链就卡在 ⑫ 上。
        正确处置与通用分支的 `advisories_deferred` 同款：**放行 + 留痕**，由驱动投递给 ⑭。
        （`rubric_redline` 被反推表钉成 presentation —— 见 RESULT_CHECK_CATEGORY。）
        """
        root = make_root()
        out = enforce(root, "rubric", rubric_decision(
            root, ["rubric_redline"],
            [rubric_issue("r1", "presentation", ["rubric_redline"], "must")]), STAGES)
        self.assertNotEqual(out.get("target"), "format",
                            "target 落到了后序阶段 —— 驱动会拒绝，黄灯无法执行")
        self.assertEqual(out["status"], "PASS")
        self.assertEqual(out["reason"], "advisories_deferred")
        self.assertEqual([a["id"] for a in out.get("advisories") or []], ["r1"],
                         "延后项必须留在 advisories 里（驱动据此投递给 ⑭）")

    def test_a_claim_plus_a_layout_item_hands_only_the_claim_to_fix(self):
        """claim + 版式混在一起：只把 claim 交给 ⑬，版式项进 advisories（⑬ 无权改版式）。"""
        root = make_root()
        out = enforce(root, "rubric", rubric_decision(
            root, ["rubric_trace", "rubric_redline"],
            [rubric_issue("r1", "claim", ["rubric_trace"], "must"),
             rubric_issue("r2", "presentation", ["rubric_redline"], "must")]), STAGES)
        self.assertEqual(out["target"], "fix")
        self.assertEqual([i["id"] for i in out["issues"]], ["r1"],
                         "⑬ 只该拿到论文侧（claim）那一项")
        self.assertEqual([a["id"] for a in out.get("advisories") or []], ["r2"])

    def test_model_defect_blocks_the_forward_path(self):
        """有模型类判词时整单回退，**不许**把措辞项单独交给 fix 了事。"""
        root = make_root()
        out = enforce(root, "rubric", rubric_decision(
            root, ["rubric_trace", "rubric_adaptation"],
            [rubric_issue("r1", "claim", ["rubric_trace"], "must"),
             rubric_issue("r2", "constraint_model", ["rubric_adaptation"], "must")]), STAGES)
        self.assertEqual(out["status"], "NEEDS_FIX")
        self.assertEqual(out["target"], "analysis")

    def test_optional_only_remains_pass(self):
        """没必要评分满分：严重的和中等的处理完就行。"""
        root = make_root()
        out = enforce(root, "rubric", rubric_decision(
            root, ["rubric_trace"],
            [rubric_issue("r1", "claim", ["rubric_trace"], "optional")]), STAGES)
        self.assertEqual(out["status"], "PASS")
        self.assertEqual(out["reason"], "only_optional_remain")
        self.assertEqual(len(out["advisories"]), 1)

    def test_optional_cannot_downgrade_a_model_defect(self):
        """反洗白：模型类判词标了 optional 也强制升回 must。"""
        root = make_root()
        out = enforce(root, "rubric", rubric_decision(
            root, ["rubric_evidence"],
            [rubric_issue("r1", "implementation", ["rubric_evidence"], "optional")]), STAGES)
        self.assertEqual(out["status"], "NEEDS_FIX")
        self.assertEqual(out["target"], "code")
        self.assertEqual(out["issues"][0]["tier"], "must")

    def test_adaptation_miscategorised_as_claim_is_reversed(self):
        """错分类防护：rubric_adaptation 是模型层判断，填成 claim 会被掰回 constraint_model。"""
        root = make_root()
        out = enforce(root, "rubric", rubric_decision(
            root, ["rubric_adaptation"],
            [rubric_issue("r1", "claim", ["rubric_adaptation"])]), STAGES)
        self.assertEqual(out["target"], "analysis")
        self.assertNotEqual(out["target"], "fix")

    def test_tier_is_rejected_outside_rubric(self):
        """别的门禁写 tier 没有意义，且会让人误以为"标了 optional 就不拦"——直接拒。"""
        root = make_root()
        anchor = {"file": "request/problem.md", "quote": "相对2023年约±5%变化"}
        checks = [{"id": c, "status": "failed" if c == "task_fidelity" else "passed",
                   "reason": "ok", "evidence": [anchor]} for c in REQUIRED["verify"]]
        out = enforce(root, "verify", {
            "schema_version": 2, "stage": "verify", "input_digest": "d", "reason": "structured",
            "status": "FAIL", "checks": checks,
            "issues": [dict(rubric_issue("v1", "claim", ["task_fidelity"]), tier="optional")]}, STAGES)
        self.assertEqual(out["status"], "UNVERIFIED")
        self.assertEqual(out["reason"], "verdict_malformed")

    def test_fatal_cannot_be_washed_into_fix(self):
        """fatal 不吃「两侧都可能」。

        `rubric_originality` / `rubric_evidence` 刻意**不在**反推表里（因为对 must 而言
        确实两侧都可能：创新点没写清楚 vs 模型确实没改进）。但 fatal 的定义是一票否决，
        不存在「只是没讲清楚」—— 不钉死的话，「完全无创新」「全文无检验」填成 claim
        就能路由到 13Repair-by-rubric-verdict，改一段措辞把一票否决洗掉。
        """
        root = make_root()
        for chk, want in (("rubric_originality", "analysis"), ("rubric_evidence", "robustness")):
            out = enforce(root, "rubric", rubric_decision(
                root, [chk], [rubric_issue("r1", "claim", [chk], "fatal")]), STAGES)
            self.assertEqual(out["target"], want,
                             f"{chk} 的 fatal 判词填成 claim 后应回退到 {want}，不能走 fix")
        # 反向对照：同一条检查项标成 must 时，仍允许审查者判成措辞问题（走 fix）。
        out = enforce(root, "rubric", rubric_decision(
            root, ["rubric_originality"],
            [rubric_issue("r1", "claim", ["rubric_originality"], "must")]), STAGES)
        self.assertEqual(out["target"], "fix")

    def test_stage_order_missing_fix_is_reported_as_driver_side(self):
        """阶段表漏了 fix → 报 stage_order_mismatch（驱动侧问题），不是裁决 JSON 的错。"""
        root = make_root()
        without_fix = [s for s in STAGES if s != "fix"]
        out = enforce(root, "rubric", rubric_decision(
            root, ["rubric_trace"],
            [rubric_issue("r1", "claim", ["rubric_trace"])]), without_fix)
        self.assertEqual(out["status"], "UNVERIFIED")
        self.assertEqual(out["reason"], "stage_order_mismatch")


class FixDispositionTest(unittest.TestCase):
    """13Repair-by-rubric-verdict 的逐条处置表。

    没有这道校验，一份「什么都没做、也没说为什么」的报告，与一份「逐条核过、两条判词
    被证伪所以没改」的报告，在驱动眼里**完全一样** —— 而这两者对下一步的意义正好相反。
    """

    def setUp(self):
        self.root = make_root()
        (self.root / "reports").mkdir(exist_ok=True)

    def write(self, spec):
        (self.root / "reports/FIX_REPORT.json").write_text(
            json.dumps(spec, ensure_ascii=False), encoding="utf-8")

    def item(self, key, **kw):
        return dict({"id": key, "disposition": "fixed", "evidence": "paper/sections/1.tex:9 已改写",
                     "recheck": "grep -c X -> 0"}, **kw)

    def test_missing_table_is_reported_only_when_there_are_verdicts(self):
        issues = cq.fix_disposition_issues(self.root, ["r1"])
        self.assertEqual(len(issues), 1)
        self.assertIn("FIX_REPORT.json", issues[0])
        # 反向对照：本轮没有任何 must/fatal 判词 → 13Repair-by-rubric-verdict 无事可做，不该强收一张空表。
        self.assertEqual(cq.fix_disposition_issues(self.root, []), [])

    def test_every_required_id_must_have_a_disposition(self):
        self.write({"schema_version": 1, "stage": "fix", "items": [self.item("r1")]})
        self.assertEqual(cq.fix_disposition_issues(self.root, ["r1"]), [])
        issues = cq.fix_disposition_issues(self.root, ["r1", "r2"])
        self.assertEqual(len(issues), 1)
        self.assertIn("r2", issues[0])

    def test_fixed_requires_recheck_not_just_evidence(self):
        self.write({"schema_version": 1, "stage": "fix",
                    "items": [self.item("r1", recheck="   ")]})
        issues = cq.fix_disposition_issues(self.root, ["r1"])
        self.assertTrue(any("recheck" in i for i in issues), issues)

    def test_evidence_is_mandatory_for_every_disposition(self):
        """这一条是「复核了没有」的唯一机器凭据：说 which 是假的，就要指出论文里本来有它。"""
        for disp in ("not_reproduced", "deferred", "out_of_scope"):
            self.write({"schema_version": 1, "stage": "fix",
                        "items": [self.item("r1", disposition=disp, evidence="")]})
            issues = cq.fix_disposition_issues(self.root, ["r1"])
            self.assertTrue(any("evidence" in i for i in issues), f"{disp}: {issues}")
            # 带证据就通过 —— not_reproduced 与 fixed 一样是合格产出
            self.write({"schema_version": 1, "stage": "fix",
                        "items": [self.item("r1", disposition=disp, evidence="论文里本来就有")]})
            self.assertEqual(cq.fix_disposition_issues(self.root, ["r1"]), [])

    def test_illegal_disposition_and_duplicate_id_rejected(self):
        self.write({"schema_version": 1, "stage": "fix", "items": [self.item("r1", disposition="大概改了吧")]})
        self.assertTrue(any("disposition 非法" in i
                            for i in cq.fix_disposition_issues(self.root, ["r1"])))
        self.write({"schema_version": 1, "stage": "fix", "items": [self.item("r1"), self.item("r1")]})
        self.assertTrue(any("重复" in i for i in cq.fix_disposition_issues(self.root, ["r1"])))

    def test_wrong_stage_or_schema_rejected(self):
        self.write({"schema_version": 1, "stage": "rubric", "items": []})
        self.assertTrue(any("stage" in i for i in cq.fix_disposition_issues(self.root, [])))
        self.write({"schema_version": 2, "stage": "fix", "items": []})
        self.assertTrue(any("schema_version" in i
                            for i in cq.fix_disposition_issues(self.root, [])))


class AdvisoriesIsNotASideDoorTests(unittest.TestCase):
    """`advisories` 是**轻微/可选**那条通道，能不能算轻微由 category 定，不由审查者说了算。

    **constraint_model** 这类实质项塞进 `advisories`（哪怕明写「会改变论文报出的不确定性」）
    本该是拦链的 must 项。校验若只作用在 `issues` 上、`advisories` 一个字都不查，等于开了
    一扇绕开拦截的侧门。
    """

    def _verdict(self, root, advisories):
        return {"schema_version": 2, "stage": "review", "input_digest": "d",
                "status": "APPROVED", "reason": "structured",
                "checks": checks_for(root, {}), "issues": [], "advisories": advisories}

    def test_substantive_advisory_is_rejected(self):
        root = make_root()
        out = enforce(root, "review", self._verdict(root, [
            {"id": "A-1", "category": "constraint_model",
             "evidence": "口径不确定性里混进了一个报告自己判定「违反 P4」的变体",
             "fix": "剔除该变体后重报不确定性"}]), STAGES)
        self.assertEqual(out["status"], "UNVERIFIED")
        self.assertEqual(out["reason"], "verdict_malformed")
        self.assertIn("A-1", out["issues"][0]["evidence"])

    def test_light_advisory_still_passes(self):
        """反向对照：真正的轻微项（措辞/版式/引用编号）必须留着 —— 别把口子焊死。"""
        root = make_root()
        out = enforce(root, "review", self._verdict(root, [
            {"id": "A-2", "category": "presentation",
             "evidence": "§11.7 仍写 R1–R13，而 §12 已新增 R14",
             "fix": "三处统一改 R1–R14",
             "why_not_blocking": "只改交叉引用编号，不改任何数值、方程或判据"},
            {"id": "A-3", "category": "claim",
             "evidence": "「严格相同」措辞过强，建议加一句披露",
             "fix": "改为「数值上与…一致」",
             "why_not_blocking": "只动一句归因措辞，结论与数值不变"}]), STAGES)
        self.assertEqual(out["status"], "APPROVED")

    def test_rubric_advisories_are_unaffected(self):
        """rubric 是这条通道的正当主人：它的 advisories 本来就该是 optional 那三类。"""
        root = make_root()
        ev = {"file": "request/problem.md", "quote": "相对2023年约±5%变化"}
        decision = {"schema_version": 2, "stage": "rubric", "input_digest": "d",
                    "status": "APPROVED", "reason": "structured",
                    "checks": [{"id": cid, "status": "passed", "reason": "checked",
                                "evidence": [ev]} for cid in REQUIRED["rubric"]],
                    "issues": [],
                    "advisories": [{"id": "R-1", "category": "presentation",
                                    "evidence": "图注编号可读性", "fix": "统一格式",
                                    "cost": "10 分钟"}]}
        out = enforce(root, "rubric", decision, STAGES)
        self.assertEqual(out["status"], "APPROVED")


class AdvisoryChannelTests(unittest.TestCase):
    """`issues` 是**拦链**通道，`advisories` 是**不拦链**通道。选错通道 = 白写。

      · **登记/自述类**塞进 `issues`（哪怕自己写着「本身不构成回退理由」）会被反洗白规则
        升成 must 拦链 —— 真正该拦的只有一条时，也白拖一轮；
      · 本门禁四个必查项**全部**在 `RESULT_CHECK_CATEGORY` 里 ⇒ `issues` 的 category 一律被
        反推成实质类 ⇒ `severity` 一律 hard ⇒ **写 soft/info 完全不起作用**。
    """

    def setUp(self):
        self.root = make_root()

    def _verdict(self, issues=(), advisories=()):
        return {"schema_version": 2, "stage": "review", "input_digest": "d",
                "status": "NEEDS_FIX", "reason": "structured",
                "checks": checks_for(self.root, {"model_assumptions": "failed"}),
                "issues": list(issues), "advisories": list(advisories)}

    _HARD = {"id": "R-1", "category": "constraint_model", "check_ids": ["model_assumptions"],
             "severity": "hard", "evidence": "e", "fix": "f", "recheck": "r"}

    def test_info_inside_issues_is_ignored_not_rejected(self):
        """`severity: info` 塞在 `issues` 里：**不判不符、也不起作用** —— 仍按 hard 拦链。

        刻意不在这里判 `verdict_malformed` 逼它挪去 `advisories`：那等于给 agent 一个
        「这条不影响交付」的自述式合法表达，而它可能判错，判错就少一道兜底。宁可白拖一轮，
        也不放过一条。（省这一轮靠 SKILL 里「登记/自述类走 advisories」的自觉。）
        """
        out = enforce(self.root, "review",
                      self._verdict(issues=[dict(self._HARD, severity="info")]), STAGES)
        self.assertEqual(out["status"], "NEEDS_FIX", "info 不该被当成放行信号")
        self.assertEqual([i["severity"] for i in out["issues"]], ["hard"], "info 仍按 hard 拦链")

    def test_soft_inside_issues_is_still_allowed_but_becomes_hard(self):
        """反向护栏：`soft` 不判不符（它只在别的门禁可能作数），但本门禁仍算 hard —— 会拦链。"""
        out = enforce(self.root, "review",
                      self._verdict(issues=[dict(self._HARD, severity="soft")]), STAGES)
        self.assertEqual(out["status"], "NEEDS_FIX")
        self.assertEqual([i["severity"] for i in out["issues"]], ["hard"])

    def test_advisory_without_why_not_blocking_is_rejected(self):
        """逼审查者为「不拦链」给出理由：说不出哪个数值/方程/判据不会变，它就是实质缺陷。"""
        out = enforce(self.root, "review", self._verdict(advisories=[
            {"id": "adv-1", "category": "presentation", "evidence": "e", "fix": "f"}]), STAGES)
        self.assertEqual(out["status"], "UNVERIFIED")
        self.assertIn("why_not_blocking", out["issues"][0]["evidence"])

    def test_advisory_with_a_blank_why_is_rejected(self):
        out = enforce(self.root, "review", self._verdict(advisories=[
            {"id": "adv-1", "category": "presentation", "evidence": "e", "fix": "f",
             "why_not_blocking": "   "}]), STAGES)
        self.assertEqual(out["status"], "UNVERIFIED")

    def test_a_complete_advisory_passes_and_does_not_block(self):
        """带齐 category + why_not_blocking 的文稿项：放行，且不出现在 issues 里。"""
        out = enforce(self.root, "review", self._verdict(
            issues=[self._HARD],
            advisories=[{"id": "adv-1", "category": "claim", "evidence": "§17 自述措辞",
                         "fix": "改述",
                         "why_not_blocking": "只动一句自述，不改任何数值、方程、判据或交付件"}]), STAGES)
        self.assertEqual(out["status"], "NEEDS_FIX")
        self.assertEqual([i["id"] for i in out["issues"]], ["R-1"])
        self.assertEqual([a["id"] for a in out.get("advisories") or []], ["adv-1"])


class ReportWordingRouteTests(unittest.TestCase):
    """`report_wording`：**报告层**措辞建议的专用通道，路由回 `analysis`。

    为什么单开一个：`claim`→write、`presentation`→format、`diagram`→drawio 三条**都回不到
    analysis**，于是"建模报告某句措辞不成立"这类建议只能去 ⑧ 论文撰写绕一圈 —— 而 write
    不改编报告，那句错话就一直在报告里，下一轮门禁重新记一遍（同一句错话会被反复提）。
    """

    def setUp(self):
        self.root = make_root()

    def _verdict(self, advisories):
        return {"schema_version": 2, "stage": "review", "input_digest": "d",
                "status": "NEEDS_FIX", "reason": "structured",
                "checks": checks_for(self.root, {"model_assumptions": "failed"}),
                "issues": [{"id": "R-1", "category": "constraint_model",
                            "check_ids": ["model_assumptions"], "severity": "hard",
                            "evidence": "e", "fix": "f", "recheck": "r"}],
                "advisories": advisories}

    def test_report_wording_advisory_routes_to_analysis(self):
        out = enforce(self.root, "review", self._verdict([
            {"id": "adv-1", "category": "report_wording",
             "evidence": "§6 P2 那句等价性断言措辞不成立",
             "fix": "改为…", "why_not_blocking": "只改报告里一句话，不动数值与判据"}]), STAGES)
        self.assertEqual(out["status"], "NEEDS_FIX")
        self.assertEqual([a["id"] for a in out.get("advisories") or []], ["adv-1"])
        self.assertEqual(cq.TARGETS["report_wording"], "analysis",
                         "必须回写那份报告的阶段 —— 否则 write 改不了报告，错话一直留着")

    def test_report_wording_does_not_open_a_whitewash_hole(self):
        """作为 **issue** 时它一样会被反推成实质类 —— 不会因为名字里有 wording 就放行。

        反推看的是 `check_ids`（哪些必查项 failed），跟 category 叫什么无关。
        review 四个必查项全在反推表里 ⇒ 任何 issue 都躲不过。
        """
        out = enforce(self.root, "review", {
            "schema_version": 2, "stage": "review", "input_digest": "d",
            "status": "NEEDS_FIX", "reason": "structured",
            "checks": checks_for(self.root, {"model_assumptions": "failed"}),
            "issues": [{"id": "R-1", "category": "report_wording",
                        "check_ids": ["model_assumptions"], "severity": "soft",
                        "evidence": "模型假设不成立", "fix": "f", "recheck": "r"}]}, STAGES)
        self.assertEqual(out["status"], "NEEDS_FIX")
        self.assertEqual([i["severity"] for i in out["issues"]], ["hard"],
                         "填成 report_wording 也照样按实质类拦链")
        self.assertEqual(out["target"], "analysis")

    def test_a_substantive_category_cannot_ride_in_advisories(self):
        """反向护栏：实质类仍然进不了 advisories —— 这条守卫没被新类别撑开。"""
        out = enforce(self.root, "review", self._verdict([
            {"id": "adv-9", "category": "constraint_model",
             "evidence": "模型约束写错", "fix": "f", "why_not_blocking": "影响不大"}]), STAGES)
        self.assertEqual(out["status"], "UNVERIFIED")
        self.assertIn("adv-9", out["issues"][0]["evidence"])


if __name__ == "__main__":
    unittest.main()
