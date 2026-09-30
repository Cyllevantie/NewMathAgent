"""Typed review coverage and repair routing, independent of any competition."""
import json
import re
import unicodedata
from pathlib import Path

# 证据锚点按"可核对"而非"逐字节"比对：折叠空白/全角标点/弯引号/Unicode 组合形式，
# 消除 CRLF、全角逗号、弯引号造成的假 UNVERIFIED；"必须真的出现在项目文件里"不变。
_FOLD = str.maketrans({
    "，": ",", "。": ".", "：": ":", "；": ";", "（": "(", "）": ")",
    "【": "[", "】": "]", "“": '"', "”": '"', "‘": "'", "’": "'",
    "　": " ", "、": ",", "－": "-", "—": "-", "％": "%", "～": "~",
})


def _norm(text):
    text = unicodedata.normalize("NFC", text).translate(_FOLD)
    return re.sub(r"\s+", " ", text).strip()

# Producer stages, not the stage that happened to discover a defect.
TARGETS = {
    "task_interpretation": "analysis", "constraint_model": "analysis",
    "stochastic_model": "analysis", "implementation": "code",
    # report_wording 是给 `advisories` 用的**报告层措辞**通道：登记/自述/引用/命名/计数这类
    # 「只需改报告里的几句话」的建议，归**写那份报告的阶段**（analysis）。
    # 为什么单开一个：`claim`→write、`presentation`→format、`diagram`→drawio，
    # 三条都**回不到 analysis**，于是"建模报告某句措辞不成立"这类建议只能去 ⑧ 论文撰写绕一圈
    # —— 而 write 不改编报告，那句错话就一直在报告里，下一轮门禁重新记一遍（一轮建议里
    # 常有几条自述是在追前几轮的建议）。
    # 它**只对 advisories 有意义**：作为 `issues` 的 category 时，`_effective_category` 照样按
    # `check_ids` 反推成实质类（review 四个必查项全在反推表里），该拦的一条不会漏。
    "report_wording": "analysis",
    "data_integrity": "code", "validation": "code", "experiment": "robustness",
    "proof": "write", "claim": "write",
    # presentation 是**版式/排版/图文编辑**缺陷，归 format 不归 write：
    # 「图注编号对不上」「浮体位置留下大片空白」「表超页边」这类都是定点手术（秒级），
    # 送回 write 要重跑整篇写作。真正属于措辞的仍归 claim/proof（→ write）。
    "presentation": "format",
    # diagram 是**图本身的产出**缺陷：图画错、缺图、图内容与数据不符 → 回 drawio 重画。
    # 与 presentation 的分界：图**画得对不对**归 diagram（drawio），图**排得好不好**归
    # presentation（format）。审查者按此二选一 —— 故意不放进 RESULT_CHECK_CATEGORY
    # 强制反推，因为 figure_coverage 失败两种都可能（见下方该表注释）。
    "diagram": "drawio",
}
# 错分类防护：这些检查项一旦 failed，根源必在模型/结果/实现——不可能靠改措辞解决。
# 无论审查者把它的 category 填成什么（含 claim/presentation），一律按本表反推类别向后返修。
# 刻意**不含** proof_validity / proof_applicability / narrative_consistency / figure_coverage /
# content_coverage：这些失败可能确实只是文稿措辞问题（可回 write，且它们在门禁序列上本就是向后）。
RESULT_CHECK_CATEGORY = {
    "task_fidelity": "task_interpretation", "quantifiers": "constraint_model",
    "stochastic_semantics": "stochastic_model", "model_assumptions": "constraint_model",
    "implementation_fidelity": "implementation", "feasibility": "validation",
    "optimality": "validation", "comparison_validity": "validation",
    # 评分标阶段（rubric）的两条：它们是**模型层判断**，审查者若填成 claim/presentation
    # 就能混进"改措辞即可"的那条路 —— 所以钉死在反推表里。
    "rubric_adaptation": "constraint_model", "rubric_redline": "presentation",
}

# ---------------- 评分标终审（rubric / 13Repair-by-rubric-verdict）专用 ----------------
# rubric 的"论文侧"发现走**正向**到紧随其后的 13Repair-by-rubric-verdict 定点改写，而不是回退 write 重跑整篇
# （write 是小时级，改一句话不值当）。只有 claim 算论文侧：措辞、摘要、结论表述、
# 创新点的**表达**。其余类别一律仍回退各自的生产阶段 —— 措辞改不掉一个错的模型。
RUBRIC_FORWARD_CATEGORY = "claim"
# `fatal` 专用的反推表。与 RESULT_CHECK_CATEGORY 的区别在**适用条件**：上表对
# 「只是话没说准」这类两可情形网开一面，而 fatal 的定义是**一票否决** ——
# 不存在「只是没讲清楚」这回事。
# 不钉死的话，「完全无创新」「全文无检验」这两条 fatal
#   被填成 category=claim 就会路由到 13Repair-by-rubric-verdict —— 改一段措辞把一票否决洗掉，
#   正是这套反洗白机制存在的意义被绕开的地方。
#   只有 rubric_trace（AI 痕迹/措辞）没有 entry：它的 fatal 形态确实是文风问题，
#   重写文稿就能解决，走 fix 是对的。
FATAL_CHECK_CATEGORY = {
    "rubric_evidence": "experiment",              # 全文无检验 → 回 robustness 补做
    "rubric_originality": "task_interpretation",  # 模型确实没有针对性改进 → 回 analysis 重设计
}
# 允许被标成 optional（"轻微/可选，先看成本再定改不改"）的类别。
# 模型/数据/实现类**即使审查者标了 optional 也强制返修**：那正是 RESULT_CHECK_CATEGORY
# 要防的洗白 —— 一份"模型不适配"不该被一句"影响不大"降级成建议。
OPTIONAL_OK = {"claim", "presentation", "diagram", "report_wording"}
TIERS = {"fatal", "must", "optional"}


def _effective_category(issue, stage_order=None, tier=None):
    """错分类防护：结果/模型类检查 failed 时，类别一律以检查项反推为准。

    一条 issue 挂多个 failed 检查时，取 stage_order 上**最早**的生产阶段（与 enforce 的
    target 取"最早的必要返修阶段"一致），否则返修目标会随 check_ids 的书写顺序漂移。

    `tier="fatal"` 时用**并上** `FATAL_CHECK_CATEGORY` 的表：fatal 不接受
    「两侧都可能」那套网开一面，见该表的注释。
    """
    table = RESULT_CHECK_CATEGORY
    if tier == "fatal":
        table = {**RESULT_CHECK_CATEGORY, **FATAL_CHECK_CATEGORY}
    derived = [table[c] for c in issue["check_ids"] if c in table]
    if not derived:
        return issue["category"]
    if stage_order:
        # 顺序表与 TARGETS 同步这件事已由 enforce() 在入口一次性查过（`stage_order_mismatch`），
        # 这里保留一条兜底 raise：本函数也可能被 enforce 以外的调用方直接用。
        missing = [c for c in derived if TARGETS[c] not in stage_order]
        if missing:
            raise _VerdictError(
                f"category {missing} 的返修阶段不在给定的阶段顺序表里（表={list(stage_order)}）——"
                f" 顺序表与 content_quality.TARGETS 不同步，按未定义处理")
        # 取"其 producer 阶段最早"的那个类别（与 enforce 的 target 语义一致）
        return min(derived, key=lambda cat: stage_order.index(TARGETS[cat]))
    return derived[0]


REQUIRED = {
    "review": ["task_fidelity", "quantifiers", "stochastic_semantics", "model_assumptions"],
    "audit": ["task_fidelity", "quantifiers", "stochastic_semantics", "implementation_fidelity",
              "feasibility", "optimality", "comparison_validity",
              # `claim_scope` 是 audit **唯一**能发 REVISE_CLAIM 的通道，也是它唯一
              #   不被反推表改写的检查项 —— 它**刻意不在** RESULT_CHECK_CATEGORY 里。
              #   没有它的时候：audit 的 7 项全在反推表里 → 任何 failed 的 category 都会被
              #   掰回 analysis/code → 「全部未解决项均为 claim」永不成立 → REVISE_CLAIM
              #   不可达；一份合法的"结论需降级表述"审计要么被判 UNVERIFIED 卡住（不填
              #   issue 时），要么被转成回 code 重算（填了 issue 时）—— 而它本意只是改一句话。
              "claim_scope"],
    "mathproof": ["proof_validity", "proof_applicability", "optimality", "narrative_consistency"],
    "cross": ["task_fidelity", "comparison_validity", "narrative_consistency"],
    "verify": ["task_fidelity", "optimality", "proof_applicability", "narrative_consistency",
               "figure_coverage", "content_coverage"],
    # 评分标终审：四份评委视角评分标（适配性 15 维 / AI 痕迹 10 维 / 合规红线 26 条 /
    #   官方四大项 16 维）逐项打分，产出「严重 / 中等 / 轻微」三级判词。
    #   缺了这一项，enforce 会在 `if stage not in REQUIRED` 处**原样放行** —— 门禁静默空转。
    #   前两项在 RESULT_CHECK_CATEGORY 里（模型层不许被填成措辞）；后三项刻意**不在**：
    #   "创新点没写清楚"（便宜，claim→fix）与"模型确实没有针对性改进"（很贵，optional+成本）
    #   都得由审查者按证据选；"论文里没写灵敏度分析"也可能是根本没做（experiment→robustness）。
    "rubric": ["rubric_adaptation", "rubric_originality", "rubric_evidence",
               "rubric_trace", "rubric_redline"],
}
PASS = {"PASS", "APPROVED", "CLEAN"}


def _read_text(path):
    """按 UTF-8 → GBK/cp936 → 替换符 依次尝试解码。

    为什么不能只认 UTF-8：Windows 中文环境下 agent 自己 `open(p,'w')` 写的 json/csv（或
    题面附件）常是 GBK；严格 utf-8-sig 解码遇 GBK 会抛 UnicodeDecodeError → 被 enforce
    的宽 except 吞成 UNVERIFIED/verdict_malformed → 重试一次仍失败 → **整链挂起**，
    而 reason/evidence 里只留一句 codec 报错，人工看不出是编码问题。
    """
    raw = Path(path).read_bytes()
    for encoding in ("utf-8-sig", "gbk", "cp936"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def _evidence(root, anchors):
    if not isinstance(anchors, list) or not anchors:
        raise ValueError("Check needs source anchors")
    root = Path(root).resolve()
    for anchor in anchors:
        name, quote = anchor["file"], anchor["quote"]
        if not isinstance(name, str) or not isinstance(quote, str) or not quote.strip():
            raise ValueError("Invalid evidence anchor")
        path = (root / name).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise ValueError("Evidence file missing/outside project")
        if path.suffix.lower() not in {".md", ".txt", ".tex", ".py", ".json", ".csv"}:
            raise ValueError("Use a text source anchor, not binary evidence")
        if _norm(quote) not in _norm(_read_text(path)):
            raise ValueError(f"Evidence quote does not match source: {name}"
                             "（已按 NFC/空白折叠/全角标点比对，仍不匹配；多为改写而非原文）")


def task_contract_issues(root):
    """Check declared task-to-model semantics; interpretation still needs review.

    Distinguishes "missing/unreadable" from "structurally wrong" from "semantically
    inconsistent with the problem", so the routed analysis stage gets an actionable
    reason instead of one generic string.
    """
    root = Path(root).resolve()
    path = root / "reports/TASK_CONTRACT.json"
    try:
        spec = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, ValueError) as exc:
        return [f"题意契约缺失或不可读: reports/TASK_CONTRACT.json（{exc}）。"
                "content-quality 已启用，3analysis 必须先写该契约并随建模报告更新。"]
    if not isinstance(spec, dict) or spec.get("schema_version") != 1:
        return ["题意契约结构错误: schema_version 必须为 1"]
    if not isinstance(spec.get("requirements"), list) or not spec["requirements"]:
        return ["题意契约结构错误: requirements 必须是非空列表"]
    ids, issues = set(), []
    fields = {"quantifier", "scope", "unit", "time_reference"}
    try:
        for requirement in spec["requirements"]:
            if not isinstance(requirement, dict):
                issues.append("题意契约结构错误: requirement 必须是对象")
                continue
            key = requirement.get("id")
            if not isinstance(key, str) or not key.strip() or key in ids:
                issues.append(f"题意契约结构错误: 无效或重复的 requirement id={key!r}")
                continue
            ids.add(key)
            source = requirement.get("source")
            if not isinstance(source, dict) or not isinstance(source.get("file"), str):
                issues.append(f"{key}: source.file 缺失")
                continue
            try:
                source_path = (root / source["file"]).resolve()
            except (OSError, ValueError):
                issues.append(f"{key}: source.file 路径非法")
                continue
            if not source_path.is_relative_to(root / "request"):
                issues.append(f"{key}: 题面锚点必须位于 request/（不能引用 agent 报告）")
                continue
            try:
                _evidence(root, [source, requirement.get("model_anchor") or {}])
            except (ValueError, KeyError, TypeError, OSError) as exc:
                issues.append(f"{key}: {exc}")
                continue
            given, model = requirement.get("source_semantics"), requirement.get("model_semantics")
            if (not isinstance(given, dict) or not isinstance(model, dict)
                    or set(given) != fields or set(model) != fields):
                issues.append(f"{key}: source_semantics/model_semantics 必须含 "
                              "quantifier/scope/unit/time_reference 四字段")
                continue
            empty = [f"{kind}.{f}" for kind, block in
                     (("source_semantics", given), ("model_semantics", model))
                     for f in sorted(fields) if not isinstance(block[f], str) or not block[f].strip()]
            if empty:
                issues.append(f"{key}: 语义字段为空或非字符串 -> {', '.join(empty)}"
                              "（无对应概念时写 not_applicable）")
                continue
            if given != model:
                issues.append(f"{key}: 题面与模型的量词/范围/单位/时间基准不一致"
                              f"（source={given} model={model}）")
            if requirement.get("status") != "mapped":
                issues.append(f"{key}: 题面要求尚未映射到模型（status={requirement.get('status')!r}）")
    except (KeyError, TypeError, AttributeError, ValueError, OSError) as exc:
        issues.append(f"题意契约结构错误: {exc}")
    return issues


FIX_DISPOSITIONS = {"fixed", "not_reproduced", "deferred", "out_of_scope"}


def fix_disposition_issues(root, required_ids):
    """校验 `13Repair-by-rubric-verdict` 的逐条处置表：**每条 must/fatal 判词都必须有一条处置**。

    为什么值得单设一道机械校验：`13Repair-by-rubric-verdict` 的 SKILL 要求「改之前先复核每条判词是不是真的，
    不属实的记 `not_reproduced` 不动稿」—— 但那是散文。没有这道校验，一份"什么都没做、
    也没说为什么"的报告，和一份"逐条核过、两条判词被证伪所以没改"的报告，在驱动眼里
    **完全一样**；而这两者对下一步的意义正好相反（后者该收手，前者该重试）。

    `required_ids` 是上游 rubric 判词里 must/fatal 的 issue id —— 由驱动在 rubric
    那一关就地取出来存着（不能事后重读：13Repair-by-rubric-verdict 一改 paper/，rubric 的 input_digest 就变了）。
    """
    root = Path(root).resolve()
    try:
        spec = json.loads((root / "reports/FIX_REPORT.json").read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, ValueError) as exc:
        # 没有判词要处置时**不强制**交表：13Repair-by-rubric-verdict 每次全链都会跑，rubric 全过时它无事可做，
        #   为一次"什么都没做"的调用强收一张空表只会凭空多一条挂起路径。
        #   判据与这道校验的目的自洽：要查的是"每条判词都有处置"，没有判词就没什么可查。
        if not required_ids:
            return []
        return [f"逐条处置表缺失或不可读: reports/FIX_REPORT.json（{exc}）。"
                f"本轮有 {len(required_ids)} 条 must/fatal 判词要处置，13Repair-by-rubric-verdict 必须逐条交代。"]
    if not isinstance(spec, dict) or spec.get("schema_version") != 1:
        return ["逐条处置表结构错误: schema_version 必须为 1"]
    if spec.get("stage") != "fix":
        return [f"逐条处置表 stage 必须为 'fix'，收到 {spec.get('stage')!r}"]
    items = spec.get("items")
    if not isinstance(items, list):
        return ["逐条处置表结构错误: items 必须是列表"]
    seen, issues = set(), []
    for item in items:
        if not isinstance(item, dict):
            issues.append("逐条处置表结构错误: item 必须是对象")
            continue
        key = item.get("id")
        if not isinstance(key, str) or not key.strip() or key in seen:
            issues.append(f"逐条处置表结构错误: 无效或重复的判词 id={key!r}")
            continue
        seen.add(key)
        if item.get("disposition") not in FIX_DISPOSITIONS:
            issues.append(f"{key}: disposition 非法 {item.get('disposition')!r}"
                          f"（合法值 {sorted(FIX_DISPOSITIONS)}）")
            continue
        if not str(item.get("evidence") or "").strip():
            issues.append(f"{key}: 缺 evidence —— 处置必须带证据：「改了」要能指认改动位置，"
                          "「没改」要能指认论文里本来就有")
        if item["disposition"] == "fixed" and not str(item.get("recheck") or "").strip():
            issues.append(f"{key}: disposition=fixed 缺 recheck（复验方式与真实输出）")
    missing = sorted(set(required_ids) - seen)
    if missing:
        issues.append(f"这些判词没有处置记录: {missing} —— "
                      "每条 must/fatal 判词都必须在 items 里出现一次")
    return issues


def _rubric_route(decision, typed, stage_order, current):
    """评分标终审的路由。与其余四个门禁都不同：它有一条**正向**出路。

    ① 有模型/数值/实现类缺陷 → 整单回退到最靠前的生产阶段，`fix` 这轮**不跑**。
       否则一份「模型不适配本题」的判词会被改写成一段漂亮话交上去 ——
       那正是 `RESULT_CHECK_CATEGORY` 存在要防的事。
    ② 只有论文侧（`claim`）→ 正向交给紧随其后的 `fix` 定点改写，不回退 `write`。
       `write` 是小时级，为了改几句摘要措辞重跑整篇不值当。
    ③ 只剩 `optional`（轻微/可选）→ 放行并留痕。严重的和中等的处理完即可，
       不必评分满分；一条「加个对比会更好」不该把整链卡住。
    """
    minor = [dict(i, deferred=True) for i in typed if i["tier"] == "optional"]
    hard = [i for i in typed if i["tier"] != "optional"]
    if not hard:
        return dict(decision, issues=[], status="PASS", reason="only_optional_remain",
                    advisories=minor)
    if stage_order.index("fix") <= current:
        # 阶段表把 fix 排到了 rubric 之前 —— 那就不存在「正向交给它」这回事。
        # 退回普通回退语义，不在这里造一个指向后方阶段的正向 target。
        target = min((TARGETS[i["category"]] for i in hard), key=stage_order.index)
        return dict(decision, issues=hard, target=target, status="NEEDS_FIX",
                    reason="content_repair_required", advisories=minor)
    # 「归下游阶段」的硬项：`presentation` → `14Layout-and-format`
    #   排在 ⑫ **之后**。它们此刻**修不了**（那个阶段还没跑）：既不能当回退目标（非法 ——
    #   驱动只认前序，`_target_index` 会拒，整条路断在这里，⑫ 只能带着一个不可执行的
    #   推荐停黄灯），也不该塞给 ⑬（它只改措辞，版式不归它）。
    #   与通用分支的 `advisories_deferred` 同款处置：**放行并留痕** —— 驱动会把它投递给
    #   目标阶段（`_fold_in_deferred_advisories` / `adv_by_stage`）⇒ ⑭ 跑之前就拿到清单。
    downstream = [i for i in hard if i["category"] != RUBRIC_FORWARD_CATEGORY
                  and stage_order.index(TARGETS[i["category"]]) >= current]
    backward = [i for i in hard if i["category"] != RUBRIC_FORWARD_CATEGORY
                and stage_order.index(TARGETS[i["category"]]) < current]
    forward = [i for i in hard if i["category"] == RUBRIC_FORWARD_CATEGORY]
    deferred = minor + [dict(i, deferred=True) for i in downstream]
    if backward:
        target = min((TARGETS[i["category"]] for i in backward), key=stage_order.index)
        return dict(decision, issues=hard, target=target, status="NEEDS_FIX",
                    reason="content_repair_required", advisories=deferred)
    if forward:
        # 只有论文侧（claim）+ 被延后的下游项：**issues 只放 claim**，下游项进 advisories ——
        # 否则 ⑬ 会拿到一条它无权处置的版式判词（它的 SKILL 明写"版式不归本阶段"）。
        return dict(decision, issues=forward, target="fix", status="NEEDS_FIX",
                    reason="paper_repair_required", advisories=deferred)
    # 硬项全是"归下游阶段"的：本关放行、全部留痕（配置里此刻没有这种 category，但
    # 阶段顺序一变就可能出现 —— 不许再退回"猜一个 target"）。
    return dict(decision, issues=[], status="PASS", reason="advisories_deferred",
                advisories=deferred)


class _VerdictError(Exception):
    """Malformed typed verdict: the stage must re-emit the sidecar, not redo the review."""


def enforce(root, stage, decision, stage_order):
    """Validate review coverage; substantive defects cannot be claim-only handoffs.

    Anchors establish traceability, not the truth of the reviewer's interpretation.
    Malformed/missing evidence stays UNVERIFIED, never implies a passed review.
    """
    if stage not in REQUIRED:
        return decision
    # 「裁决过期」**原样放行**，绝不能落进下面那条 `!= "structured"` 的分支。
    #   那条分支会把它改写成 `verdict_malformed` + 「去补 .verdict.json」——
    #   可这份裁决的正文是完整的，只是**按旧要求**写的。改 JSON 修不动这件事，
    #   而且会让驱动把回执发给改不了它的上游阶段、丢掉全部 findings。
    #   正确处置由驱动做：判「重跑本门禁」，findings 放在 `stale_issues` 里仅供人看。
    if decision.get("reason") == "verdict_stale":
        return decision
    # 「报告裁决行与侧车 status 冲突」也要**原样放行 + 给对处方**：
    #   若落到下面那条 `!= "structured"` 分支 ⇒ 会被改写成 `verdict_malformed`
    #   + 「按 docs/CONTENT_QUALITY.md 修正裁决 JSON」—— 而这条路上**改 JSON 永远无效**：
    #   冲突的定义就是"两边不一致"，只改一边仍然是冲突。agent 照着办会白烧一轮门禁重跑
    #   再转黄灯（`workflow_quality.read_verdict` 早就把 reason 定成了 `conflicting_verdict`，
    #   是这里没认它）。
    if decision.get("reason") == "conflicting_verdict":
        return {"status": "UNVERIFIED", "reason": "conflicting_verdict",
                "issues": [{"id": "verdict_conflict", "severity": "hard",
                            "evidence": "报告末尾的裁决行与 `.verdict.json` 的 status 不是同一个结论",
                            "fix": "**这不是「JSON 格式错」，别去重写结构**：两边都读一遍，"
                                   "把**报告末尾那行「整题门禁裁决」**或**侧车的 `status`**"
                                   "改成同一个结论（驱动按侧车路由，报告那行是给人核对的）。",
                            "recheck": "重读报告末尾裁决行与侧车 status，两者必须是同一个裁决词"}]}
    # **先查调用方的阶段顺序表，再查裁决**。
    #   顺序表与 `TARGETS` 不同步时（最典型：调用方拿着的是旧的那张 STAGES），
    #   后面 `stage_order.index(...)` 会抛 `list.index(x): x not in list` —— 被下面的宽
    #   except 吞成 `verdict_malformed`，而那条 fix 文案让 agent「去改裁决 JSON」，
    #   根本不是这里的问题。分开判、报错才指得准。
    # rubric 多一个正向目标 `fix`（不在 TARGETS 里，它是阶段而不是类别），一并纳入对账 ——
    # 否则阶段表漏了 fix 时这里查不出来，后面 `stage_order.index("fix")` 才炸成一团。
    extra = {"fix"} if stage == "rubric" else set()
    missing = sorted((set(TARGETS.values()) | {stage} | extra) - set(stage_order or []))
    if missing:
        return {"status": "UNVERIFIED", "reason": "stage_order_mismatch",
                "issues": [{"id": "stage_order", "severity": "hard",
                            "evidence": f"调用方给的阶段顺序表缺 {missing}（表={list(stage_order or [])}）",
                            "fix": "这是**驱动侧**的问题，不是裁决 JSON 的问题："
                                   "把调用 content_quality.enforce() 时传入的 stage_order "
                                   "更新成与 lib/web/server.py 的 STAGES 同一份（**id 集合与顺序都要一致**）。注意本检查只比集合，顺序错了它**抓不到** —— 顺序错了会让 backward/forward 判定漂移，实测能把本该返修的缺陷降级成 advisory 静默放行。",
                            "recheck": "同步顺序表后重跑门禁复评"}]}
    try:
        if decision.get("reason") != "structured" or decision.get("schema_version") != 2:
            raise _VerdictError("内容审查需要 version 2 结构化裁决（含 checks 与 typed issues）")
        checks, issues = decision["checks"], decision["issues"]
        if not isinstance(checks, list):
            raise _VerdictError("checks 必须是列表")
        # `advisories` 是**轻微/可选**那条通道，而「能不能算轻微」由 category 定，
        #   不由审查者自己说了算 —— 与 `issues` 的 tier 同一套反洗白哲学。
        #   漏掉这一步就等于开了一扇没人校验的侧门：直接往 advisories 里塞东西即可绕开拦截
        #   —— 会出现十几条 category 全是 constraint_model（实质类）的 advisory，
        #   其中有的明写「会改变论文报出的不确定性」—— 那本该是拦链的 must 项。
        #   允许留在 advisories 的只有 OPTIONAL_OK 那几类（claim/presentation/diagram/
        #   report_wording）—— 分别是论文措辞、版式、图、以及**报告层措辞**：
        #   引用编号对不上、措辞过强、图注错位这类确实是"看成本决定加不加"的。
        for adv in decision.get("advisories") or []:
            if not isinstance(adv, dict):
                raise _VerdictError("advisories 的每一项必须是对象")
            cat = adv.get("category")
            if cat not in OPTIONAL_OK:
                raise _VerdictError(
                    f"advisory {adv.get('id')!r} 的 category 是 {cat!r}，"
                    f"不属于可降级的三类 {sorted(OPTIONAL_OK)} —— 实质类缺陷不能塞进 `advisories`"
                    f"绕开拦截。把它挪进 `issues`（那里会按 category 判它拦不拦链，"
                    f"check_ids 指向确已 failed 的必查项），或者它确实只是措辞/版式问题就改 category。")
            # `why_not_blocking` 必填。不是形式主义：这条要求的作用是**逼审查者为「不拦链」
            #   明确给出理由** —— 说得出「哪个数值/方程/判据不会变」，它就真是文稿类；
            #   说不出来，它就该回 `issues` 去拦链。没有这一句，advisories 就退回成一句
            #   无成本的"这条不重"，而这正是反洗白要防的东西。
            #     rubric 不适用这条：它的轻微项由 `tier: optional` 走 `_rubric_route` 生成，
            #     文档对它的等价强制是「必须附成本估计」（见 docs/CONTENT_QUALITY.md）。
            why = adv.get("why_not_blocking") if stage != "rubric" else "n/a(rubric)"
            if not isinstance(why, str) or not why.strip():
                raise _VerdictError(
                    f"advisory {adv.get('id')!r} 缺 `why_not_blocking`：必须一句话说清"
                    f"「为什么不影响交付」（哪个数值/方程/判据**不会**变）。写不出来，"
                    f"说明它其实是实质缺陷 —— 那就该放进 `issues`，让它拦链。")
        seen, failed = set(), set()
        for check in checks:
            key = check["id"]
            if key in seen or key not in REQUIRED[stage]:
                raise _VerdictError(f"检查项 id 重复或未知: {key!r}（本阶段必查 {sorted(REQUIRED[stage])}）")
            seen.add(key)
            if check["status"] not in {"passed", "failed", "not_applicable"}:
                raise _VerdictError(f"检查项 {key} 的 status 非法: {check['status']!r}")
            if not isinstance(check.get("reason"), str) or not check["reason"].strip():
                raise _VerdictError(f"检查项 {key} 缺 reason")
            _evidence(root, check["evidence"])
            if check["status"] == "failed":
                failed.add(key)
        if seen != set(REQUIRED[stage]):
            raise _VerdictError(f"缺少必查项: {sorted(set(REQUIRED[stage]) - seen)}")
        issue_ids, typed = set(), []
        for issue in issues:
            if issue["id"] in issue_ids:
                raise _VerdictError(f"issue id 重复: {issue['id']}")
            issue_ids.add(issue["id"])
            # 注：`severity: "info"` 塞在 `issues` 里**不判不符、也不起作用** —— 本门禁的 severity
            # 由 category 反推，一律 hard。不在这里判 `verdict_malformed` 逼它挪去 advisories，
            # 因为那会**开一个口子**：agent 从此有了一个"这项不影响交付"的合法表达，
            # 而它可能判错，判错就少一道兜底。**不要这个口子**：
            # 宁可白拖一轮，也不放过一条。想省这一轮，靠 SKILL 里那句
            # 「登记/自述类走 advisories」的自觉。
            category = issue["category"]
            ids = issue["check_ids"]
            if category not in TARGETS:
                raise _VerdictError(f"issue {issue['id']} 的 category 非法: {category!r}"
                                    f"（合法值 {sorted(TARGETS)}）")
            if not isinstance(ids, list) or not ids or not set(ids) <= failed:
                raise _VerdictError(f"issue {issue['id']} 的 check_ids 必须非空且指向 failed 检查"
                                    f"（failed={sorted(failed)}）")
            # tier 必须在 category **之前**解析：fatal 会换一张反推表（见
            #    _effective_category），顺序反了 fatal 就享受不到那层加固。
            tier = issue.get("tier", "must")
            if tier not in TIERS:
                raise _VerdictError(f"issue {issue['id']} 的 tier 非法: {tier!r}"
                                    f"（合法值 {sorted(TIERS)}）")
            # `tier` 是 rubric 独有的三级判词（fatal/must/optional）。别的门禁写它没有意义，
            # 而且会让人误以为"标了 optional 就不拦" —— 直接拒掉，不给这个错觉。
            if stage != "rubric" and tier != "must":
                raise _VerdictError(f"issue {issue['id']}: tier 只对 rubric 阶段有效"
                                    f"（本阶段 {stage} 不接受 tier={tier!r}）")
            # The category fixes routing even when the reviewer calls it soft/info；
            # 错分类防护：实质检查失败却被填成 claim/presentation → 取实质类别。
            category = _effective_category(issue, stage_order, tier)
            # 反洗白：模型/数据/实现类**不许**被降级成"建议"。
            if tier == "optional" and category not in OPTIONAL_OK:
                tier = "must"
            severity = ("soft" if tier == "optional" or category in {"claim", "presentation"}
                        else "hard")
            typed.append(dict(issue, category=category, severity=severity, tier=tier))
        # 覆盖率校验必须在 `if typed:` **之外**：issues 为空时 typed 也为空，若整段被跳过，
        # 一份「某必查项 failed + issues: [] + status: PASS」的侧车会被原样放行——failed 与 PASS
        # 自相矛盾却静默过关（v2 没有 v1 那条"批准不能与未解决项矛盾"的兜底）。
        covered = {cid for i in typed for cid in i["check_ids"]}
        if covered != failed:
            raise _VerdictError(f"failed 检查未关联返修 issue: {sorted(failed - covered)}")
        if typed:
            current = stage_order.index(stage)
            if stage == "rubric":
                return _rubric_route(decision, typed, stage_order, current)
            # `claim` 只能从「检查项不在 RESULT_CHECK_CATEGORY 里」产生，
            #   而 audit 的 REQUIRED 里有 `claim_scope`（唯一一项非反推类）——
            #   审查者对它填 category=claim 时会落到这里，交出有条件放行而不是回退重算。
            #   其余门禁的通道是 narrative_consistency / figure_coverage / content_coverage。
            claim_only = all(i["category"] == "claim" for i in typed)
            # cross 也走「纯 claim ⇒ 交写作、不拦链」：两轮判词**全是** `narrative_consistency`
            #   （文稿表述与数字/图表自洽）+ `category=claim` ⇒ 而 `severity` 在驱动里算出来
            #   **没人读**（见上面那行 `severity = ...`）⇒ soft 与 hard 一样拦链
            #   ⇒ 只要还剩一条措辞级不自洽，整链就停在 ⑪。claim 类判词的出路本来就是
            #   **交给写作**（REVISE_CLAIM ⇒ `run_all` 把清单塞进 write 的 hint
            #   「必须逐项落实…后续终验须核查」），不是把链停在这里。
            #   只有**全部**条目都是 claim 才走这条：判词挂在 `task_fidelity` /
            #   `comparison_validity` 上时，反推表会把它拨成 task_interpretation / validation
            #   ⇒ 不是纯 claim ⇒ 照旧 NEEDS_FIX、照旧拦链。
            # `verify` 也走这条：
            #   ⑮ 的 REQUIRED 里 `content_coverage` / `narrative_consistency` 两条**不在**
            #   反推表里 ⇒ 审查者填 claim 就留得住 ⇒ 纯 claim 时可走"交写作"。
            #   这类判词常是**文字级**（例如漏登记一个量 / 「已证明」缺推导指针），
            #   若因为"没有后续写作阶段"被迫回退 ⑨ 重写整篇，代价是 ≈2h。
            #   它的出路与 audit/cross **不同**：那两个后面有 `write`，所以交给 write；
            #   ⑮ 后面没有 ⇒ 由 `run_all` 交给 ⑬ 定点改写、改完回 ⑮ 复评（与 ⑫↔⑬ 同一套）。
            if stage in {"audit", "cross", "verify"} and claim_only:
                # 纯 claim：显式交接给写作（不是向后返修请求）
                result = dict(decision, issues=typed, status="REVISE_CLAIM",
                              reason="content_repair_required")
                result.pop("target", None)
                return result
            # 不变量（**机制已核实，不是"producer 都排在门禁之前"**）：
            # 模型类 category 不会漏放，靠的**不是**「它们的 producer 都排在门禁之前」——
            # review(第 2 位) 与 implementation/data_integrity/validation(→code=第 3 位)
            # 恰好相反。真正起作用的是 `_effective_category` 的错分类防护：五个门禁的
            # REQUIRED 检查项**全部**在 RESULT_CHECK_CATEGORY 里，于是任何 failed 的类别
            # 都会被反推成 analysis/code 这类，必然落在 backward 侧。
            # 穷举 5 门禁 × 全部必查项 × 11 个 category（264 组合）：forward 命中数为 0，
            # 所以下面 `if not backward:` 那条 advisories_deferred 分支**当前不可达**
            # （留着是为将来新增「producer 排在门禁之后」的类别）。
            # 改动 STAGES 顺序、TARGETS 或 REQUIRED 时，这条要**重新穷举核**，不要信注释。
            backward = [i for i in typed if stage_order.index(TARGETS[i["category"]]) < current]
            forward = [i for i in typed if stage_order.index(TARGETS[i["category"]]) >= current]
            if not backward:
                # 本阶段无向后返修项（仅当非 HARD_CHECK_CATEGORY 的检查在早期门禁失败时才可能）：
                # 延后到目标阶段处理，本关放行但留痕（advisories 由驱动投递到 TARGETS[category]）。
                return dict(decision, issues=[], status="PASS", reason="advisories_deferred",
                            advisories=[dict(i, deferred=True) for i in forward])
            # 取「最早的生产阶段」时**先把 claim 排除**：
            #   claim 的正当出路是"交给写作 / 交给 ⑬ 定点改写"（最便宜），不该把**整单**
            #   拽回 ⑨ 重写整篇。混合单如：
            #     「content_coverage→claim」＋「figure_coverage→presentation」
            #   ⇒ claim→write（第 9 位）比 presentation→format（第 14 位）更早
            #   ⇒ 会把"几秒级的版式手术"推荐成"重跑 ⑨ 论文撰写（小时级）"，
            #   与驱动自己的口径直接冲突（`server.py`：「verify 的默认回退目标是
            #   14Layout-and-format 而不是 9Paper-writing……那是 ⑭ 的活（秒级）」）。
            #   `pool` 全取自 `backward` ⇒ target 必然仍是**前序**阶段，不会造出非法目标。
            #   claim 项**仍留在 `issues` 里**（本处不动 `backward`）—— 它只是当轮不再
            #     决定 target，下一轮复评时它会单独成单、走 claim_only ⇒ 交 ⑬
            #     （代价：多一次 ⑮ 复评 ≈ 分钟级，而不是 ⑨ 的 ≈2 小时）。
            pool = [i for i in backward if i["category"] != "claim"] or backward
            target = min((TARGETS[i["category"]] for i in pool), key=stage_order.index)
            result = dict(decision, issues=backward, target=target, status="NEEDS_FIX",
                          reason="content_repair_required")
            if forward:
                result["advisories"] = [dict(i, deferred=True) for i in forward]
            return result
        if decision["status"] == "REVISE_CLAIM":
            raise _VerdictError("claim 交接必须有具体 failed 检查与修复项")
        return decision
    except _VerdictError as exc:
        return {"status": "UNVERIFIED", "reason": "verdict_malformed",
                "issues": [{"id": "verdict_schema", "severity": "hard",
                            "evidence": str(exc),
                            "fix": "按 docs/CONTENT_QUALITY.md 修正裁决 JSON（只补/改 .verdict.json，"
                                   "不要重做审查、不要改动报告本体）",
                            "recheck": "重写 reports/<REPORT>.verdict.json 后由门禁复评"}]}
    except (OSError, UnicodeError, ValueError, KeyError, TypeError, AttributeError) as exc:
        return {"status": "UNVERIFIED", "reason": "verdict_malformed",
                "issues": [{"id": "verdict_schema", "severity": "hard",
                            "evidence": str(exc),
                            "fix": "按 docs/CONTENT_QUALITY.md 修正裁决 JSON",
                            "recheck": "重写 reports/<REPORT>.verdict.json"}]}
