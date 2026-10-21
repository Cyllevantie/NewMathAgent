# -*- coding: utf-8 -*-
"""创新台账自检：基线 → 失败模式 → 干预 → 可测增量 → 证伪 → 审计/稳健性。

为什么要有它：建模阶段最常见的“创新”是**方法名清单**（用了 PSO / 机器学习 /
材料坐标 / 灵敏度分析），但评委能感知的创新必须能回答四件事：

1. 基线模型是什么，头条数字/决策是什么；
2. 基线在什么条件下会错（失败模式）；
3. 改了什么，为什么这个改动能修掉它（可证伪命题）；
4. 改完哪个数字变了多少；如果没变，是否诚实降级。

台账拆成四份、各由一个阶段拥有：
`reports/INNOVATION_LEDGER.json`（② design）、
`reports/INNOVATION_MEASUREMENT.json`（④ measurement）、
`reports/INNOVATION_ROBUSTNESS.json`（⑥ robustness）、
`reports/INNOVATION_PAPER.json`（⑨ paper）。
本检查器按 id 把它们合并到**内存视图**里做机械核对：字段是否齐、引用是否存在、
adopted 是否真的测过、测失败是否降级、核心创新是否经过审计与稳健性检验、主答案
是否守住护栏。它**不**判断创新是否“新”（那是 ③ 建模评审门禁的活），只保证
“创新”这句话是**可证伪、可追踪、不会把主答案带偏**的。⑤ 的复核结论写在独立的
`reports/INNOVATION_AUDIT.json`，不写回任何台账。

用法（项目根目录）::

    python lib/web/check_innovation.py --stage design
    python lib/web/check_innovation.py --stage code
    python lib/web/check_innovation.py --stage audit
    python lib/web/check_innovation.py --stage robustness
    python lib/web/check_innovation.py --stage write
    python lib/web/check_innovation.py --stage all

返回码 `0 = 通过`、`1 = 有问题`、`2 = 台账缺失/不可读`。
schema 与示例见 `skills/2Modeling-design/references/innovation-ledger.md`。
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

LEDGER_REL = "reports/INNOVATION_LEDGER.json"
MEASUREMENT_REL = "reports/INNOVATION_MEASUREMENT.json"
ROBUSTNESS_REL = "reports/INNOVATION_ROBUSTNESS.json"
PAPER_REL = "reports/INNOVATION_PAPER.json"
AUDIT_REL = "reports/INNOVATION_AUDIT.json"
# 设计台账只归 ②；下游三份 sidecar 各归 ④/⑥/⑨。把下游字段写回设计台账会让
#   ② 的产物指纹被下游合法写入打断（② 每轮重跑），所以这里显式禁止。
DESIGN_ONLY = ("measurement", "robustness", "paper", "audit", "claim_scope")
SIDE_ALLOWED = {
    MEASUREMENT_REL: {"measurement", "status", "downgrade_reason"},
    ROBUSTNESS_REL: {"robustness", "claim_scope", "core", "status", "downgrade_reason"},
    PAPER_REL: {"paper"},
}
STAGES = ("design", "code", "audit", "robustness", "write", "all")
TYPES = {"mechanism", "structure", "criterion", "evidence"}
LENSES = {"mechanism", "data", "adversarial", "optimization"}
STATUSES = {"adopted", "rejected", "downgraded"}
DESIGN_FIELDS = (
    "id", "question", "lens", "type", "baseline_id", "failure_mode",
    "intervention", "claim", "predicted_delta", "test", "kill_if", "status",
)
MEASUREMENT_FIELDS = ("source", "passed")
PRIMARY_FIELDS = ("metric", "baseline_value", "intervention_value",
                  "relative_change", "guard_passed")
AUDIT_VERDICTS = {"PASS", "FAIL", "REVISE", "UNVERIFIED"}
# ⑤ 的 evidence 是「复核了没有」的唯一机器凭据：只判非空时写 "x" 就能过。
# 要能追到具体产物（路径样 token），且不是「两列一致」这种没有指认对象的短句。
AUDIT_EVIDENCE_MIN_CHARS = 12
AUDIT_EVIDENCE_PATH_TOKENS = ("reports/", "code/", "results/", "figures/", "paper/")
# ⑥ SKILL 要求 core 项至少做 2 类扰动/重抽样/口径对照，并逐项记 what/result。
ROBUSTNESS_MIN_CHECKS = 2


def _text(value) -> bool:
    if not isinstance(value, str):
        return False
    v = value.strip()
    return bool(v) and v.lower() not in {"none", "null", "nan"}


def _num(value) -> bool:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return False
    try:
        return math.isfinite(float(value))
    except (OverflowError, ValueError):
        return False


def _answer_text(value) -> bool:
    """定性主答案的非空判定：拒绝 None、空串、'None'/'null'/'nan' 这类占位。"""
    if isinstance(value, str):
        return bool(value.strip()) and value.strip().lower() not in {"none", "null", "nan"}
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        try:
            return math.isfinite(float(value))
        except (OverflowError, ValueError):
            return False
    return False


def _audit_evidence_ok(value) -> bool:
    """⑤ 复核证据必须可追到具体产物：≥12 字且含路径样 token。

    只判非空挡不住 `"evidence": "x"` —— 一句占位就过，等于没有复核记录；
    长度门槛再挡掉「两列一致」这种没有指认对象的短句。
    """
    if not _text(value):
        return False
    evidence = value.strip().lower()
    return (len(evidence) >= AUDIT_EVIDENCE_MIN_CHARS
            and any(token in evidence for token in AUDIT_EVIDENCE_PATH_TOKENS))


def _load(root: Path):
    path = root / LEDGER_REL
    if not path.is_file():
        return None, [
            f"缺创新台账 `{LEDGER_REL}`：② 建模设计必须先写基线卡与候选台账，"
            "不能只在报告里写一句“创新点”。schema 见 "
            "`skills/2Modeling-design/references/innovation-ledger.md`。"
        ]
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:  # noqa: BLE001 - 报错要给 agent 看
        return None, [f"创新台账不可读（{path}）：{exc}"]
    if not isinstance(data, dict):
        return None, [f"创新台账根节点必须是对象，实际是 {type(data).__name__}"]
    return data, []


def _check_design_ownership(data, issues):
    """设计台账不许夹带下游字段：measurement/robustness/paper/audit/claim_scope。

    这四个字段分别由 ④/⑥/⑨/⑤ 写在自己的文件里。若仍塞在 `INNOVATION_LEDGER.json`，
       下游一改，② 的回执 outputs 就变 ⇒ ② 每轮重跑并级联 ③④。
    """
    items = data.get("items")
    if not isinstance(items, list):
        return
    for idx, item in enumerate(items, 1):
        if not isinstance(item, dict):
            continue
        for field in DESIGN_ONLY:
            if field in item:
                issues.append(
                    f"items[{idx}].{field} 不属于设计台账："
                    "measurement→INNOVATION_MEASUREMENT.json（④）、"
                    "robustness/claim_scope→INNOVATION_ROBUSTNESS.json（⑥）、"
                    "paper→INNOVATION_PAPER.json（⑨）、audit→INNOVATION_AUDIT.json（⑤）；"
                    "写回设计台账会让 ② 的回执每轮自失效"
                )


def _merge_sidecar(root: Path, rel: str, data, issues):
    """把某阶段自己的 sidecar 合并进内存视图；不改盘上的设计台账。"""
    path = root / rel
    if not path.is_file():
        return
    try:
        doc = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:  # noqa: BLE001
        issues.append(f"`{rel}` 不可读：{exc}")
        return
    if not isinstance(doc, dict):
        issues.append(f"`{rel}` 根节点必须是对象")
        return
    if type(doc.get("schema_version")) is not int or doc.get("schema_version") != 1:
        issues.append(f"`{rel}` 的 `schema_version` 必须是整数 1")
    raw = doc.get("items")
    if not isinstance(raw, dict):
        issues.append(f"`{rel}` 必须含 `items`（id → 该阶段字段）")
        return
    items = data.get("items")
    items = items if isinstance(items, list) else []
    by_id = {i.get("id"): i for i in items
             if isinstance(i, dict) and isinstance(i.get("id"), str)}
    allowed = SIDE_ALLOWED[rel]
    for key, val in raw.items():
        if key not in by_id:
            issues.append(f"`{rel}` 的 id={key!r} 不在设计台账里")
            continue
        if not isinstance(val, dict):
            issues.append(f"`{rel}` 的 id={key!r} 必须是对象")
            continue
        for field, value in val.items():
            if field not in allowed:
                issues.append(f"`{rel}` 的 id={key!r} 含不属于本阶段的字段 {field!r}")
                continue
            by_id[key][field] = value


def _check_schema(data, root: Path, issues):
    if type(data.get("schema_version")) is not int or data.get("schema_version") != 1:
        issues.append("`schema_version` 必须是整数 1（true/1.0 不算）")
    report = data.get("report")
    if not _text(report):
        issues.append("`report` 必须指向建模报告（通常 reports/ANALYSIS_MODELING_REPORT.md）")
    elif not (root / report).is_file():
        issues.append(f"`report` 指向的文件不存在：{report}")

    panel = data.get("panel")
    if not isinstance(panel, dict):
        issues.append("缺 `panel`：记录本轮跑了哪些视角、共几个候选")
    else:
        lenses = panel.get("lenses")
        if not isinstance(lenses, list) or len({str(x) for x in lenses}) < 3:
            issues.append("`panel.lenses` 至少要有 3 个不同视角")
        else:
            lens_set = {str(x) for x in lenses}
            if not ({"adversarial", "optimization"} & lens_set):
                issues.append(
                    "`panel.lenses` 至少要有一个对抗/审稿视角或优化视角"
                    "（默认 adversarial；纯优化题可用 optimization 代替）"
                )
        candidates = panel.get("candidates")
        if not isinstance(candidates, int) or isinstance(candidates, bool) or candidates < 3:
            issues.append("`panel.candidates` 必须是 ≥3 的整数（至少 3 个候选）")

    baselines = data.get("baselines")
    if not isinstance(baselines, list) or not baselines:
        issues.append("`baselines` 至少要有 1 条基线卡")
        baselines = []
    seen_base = set()
    for idx, base in enumerate(baselines, 1):
        tag = f"baselines[{idx}]"
        if not isinstance(base, dict):
            issues.append(f"{tag} 必须是对象")
            continue
        for key in ("id", "question", "model", "headline"):
            if not _text(base.get(key)):
                issues.append(f"{tag}.{key} 必须是非空字符串")
        bid = base.get("id")
        if _text(bid):
            if bid in seen_base:
                issues.append(f"{tag}.id 重复：{bid}")
            seen_base.add(bid)

    items = data.get("items")
    if not isinstance(items, list):
        issues.append("`items` 必须是数组（至少 3 个候选，含 rejected）")
        items = []
    elif len(items) < 3:
        issues.append("`items` 至少要有 3 个候选（含 rejected），不能只记采用项")
    return seen_base, items


def _check_design(data, root: Path, issues, stage="design"):
    seen_base, items = _check_schema(data, root, issues)
    baselines = data.get("baselines")
    baselines = baselines if isinstance(baselines, list) else []
    base_q = {
        b.get("id"): b.get("question")
        for b in baselines
        if isinstance(b, dict) and _text(b.get("id"))
    }
    adopted, core = [], []
    seen_item = set()
    for idx, item in enumerate(items, 1):
        tag = f"items[{idx}]"
        if not isinstance(item, dict):
            issues.append(f"{tag} 必须是对象")
            continue
        iid = item.get("id")
        if _text(iid):
            if iid in seen_item:
                issues.append(f"{tag}.id 重复：{iid}（一个 id 只能对应一个候选）")
            seen_item.add(iid)
        for key in DESIGN_FIELDS:
            if not _text(item.get(key)):
                issues.append(f"{tag}.{key} 必须是非空字符串")
        lens = item.get("lens")
        if _text(lens) and lens not in LENSES:
            issues.append(f"{tag}.lens={lens!r} 不在 {sorted(LENSES)}")
        typ = item.get("type")
        if _text(typ) and typ not in TYPES:
            issues.append(f"{tag}.type={typ!r} 不在 {sorted(TYPES)}")
        status = item.get("status")
        if _text(status) and status not in STATUSES:
            issues.append(f"{tag}.status={status!r} 不在 {sorted(STATUSES)}")
        bid = item.get("baseline_id")
        if _text(bid) and seen_base and bid not in seen_base:
            issues.append(f"{tag}.baseline_id 指向不存在的基线：{bid}")
        if _text(bid) and bid in base_q and _text(item.get("question")) \
                and base_q[bid] != item.get("question"):
            issues.append(
                f"{tag}.question={item.get('question')!r} 与基线 {bid} 的 question="
                f"{base_q[bid]!r} 不一致"
            )
        if status == "adopted":
            adopted.append(item)
            if not isinstance(item.get("core"), bool):
                issues.append(f"{tag}.core 必须是 true/false（adopted 项必填）")
            guard = item.get("primary_guard")
            gtag = f"{tag}.primary_guard"
            if not isinstance(guard, dict):
                issues.append(
                    f"{gtag} 缺失：adopted 必须写主答案护栏（metric / allowed_relative_change / why）。"
                    "创新默认只能让主答案在护栏内变化；超出且无独立证据 = 模型被带偏，不是创新"
                )
            else:
                if not _text(guard.get("metric")):
                    issues.append(f"{gtag}.metric 必须写明哪个主答案（如 1800 s 中心温度、t_dry）")
                allowed = guard.get("allowed_relative_change")
                if not _num(allowed) or allowed < 0 or allowed > 1:
                    issues.append(
                        f"{gtag}.allowed_relative_change 必须是 0–1 的相对值（10% 写 0.10，不要写 10）"
                    )
                if not _text(guard.get("why")):
                    issues.append(f"{gtag}.why 必须说明为什么允许这个偏离（题面/文献/多数模型量级）")
            if item.get("core") is True:
                core.append(item)
        elif status == "rejected" and not _text(item.get("reject_reason")):
            issues.append(f"{tag} 是 rejected，必须写 `reject_reason`")
        elif status == "downgraded" and not _text(item.get("downgrade_reason")):
            issues.append(f"{tag} 是 downgraded，必须写 `downgrade_reason`")
    if len(core) > 1:
        issues.append(
            f"core=true 的 adopted 有 {len(core)} 个（{[i.get('id') for i in core]}）："
            "一篇论文最多 1 个核心创新，其余写成 supporting/关键处理"
        )
    if len(adopted) > 2:
        issues.append(
            f"adopted 有 {len(adopted)} 个（{[i.get('id') for i in adopted]}）："
            "最多 1 core + 1 supporting；其余必须 rejected 或写在“关键处理”里"
        )
    if not adopted:
        downgraded = [
            i for i in items
            if isinstance(i, dict) and i.get("status") == "downgraded"
            and _text(i.get("downgrade_reason"))
        ]
        if _text(data.get("no_adoption_reason")):
            # ② 明确声明“本题没有值得做的增量”，后续阶段没有 adopted 可测，合法。
            pass
        elif stage == "design":
            issues.append(
                "没有 adopted 项时必须写 `no_adoption_reason`：说明为什么本题没有值得做的增量，"
                "不能空着让读者以为忘了做"
            )
        elif not downgraded:
            issues.append(
                "没有 adopted，也没有任何 `downgraded + downgrade_reason`："
                "④/⑤ 测失败后必须留下降级记录，不能把候选删掉当没发生"
            )
    return adopted, core


def _source_exists(root: Path, source: str) -> bool:
    if source.startswith(("http://", "https://")):
        return True
    return (root / source).is_file()


def _check_measurement(root: Path, issues, adopted):
    for item in adopted:
        tag = f"{item.get('id', '?')}.measurement"
        m = item.get("measurement")
        if not isinstance(m, dict):
            issues.append(
                f"{tag} 缺失：adopted 必须在 {MEASUREMENT_REL} 写实测值"
                "（基线/干预/差值/来源）")
            continue
        kind = m.get("kind", "quantitative")
        if kind not in ("quantitative", "qualitative"):
            issues.append(f"{tag}.kind={kind!r} 只能是 quantitative 或 qualitative")
        for key in MEASUREMENT_FIELDS:
            if key not in m:
                issues.append(f"{tag}.{key} 缺失")
        if not isinstance(m.get("passed"), bool):
            issues.append(f"{tag}.passed 必须是 true/false")
        source = m.get("source")
        if not _text(source):
            issues.append(f"{tag}.source 必须是非空路径（不能空串/None）")
        elif not _source_exists(root, source):
            issues.append(f"{tag}.source 指向的文件不存在：{source}")
        if kind == "quantitative":
            for key in ("baseline_value", "intervention_value", "delta"):
                if not _num(m.get(key)):
                    issues.append(f"{tag}.{key} 必须是有限数值")
            b, i, d = m.get("baseline_value"), m.get("intervention_value"), m.get("delta")
            if _num(b) and _num(i) and _num(d):
                expect = float(i) - float(b)
                if not math.isfinite(expect):
                    issues.append(f"{tag}.delta 无法核对：baseline/intervention 差值溢出浮点范围")
                elif abs(float(d) - expect) > 5e-3 * max(1.0, abs(expect)):
                    issues.append(
                        f"{tag}.delta={d} 与 intervention_value - baseline_value="
                        f"{expect:.6g} 不一致；不能自报一个与两列对不上的差值"
                    )
            if not _text(m.get("delta_unit")):
                issues.append(f"{tag}.delta_unit 必须写明单位（如 h、%、元）")
        elif kind == "qualitative":
            if not _text(m.get("evidence")):
                issues.append(f"{tag}.evidence 缺失：定性结果也要写证据/反例测试")
        primary = m.get("primary")
        ptag = f"{tag}.primary"
        if not isinstance(primary, dict):
            issues.append(
                f"{ptag} 缺失：adopted 必须同时报主答案在 baseline/intervention 下的值，"
                "不能只报一个对创新有利的次要指标"
            )
        else:
            guard = item.get("primary_guard")
            guard = guard if isinstance(guard, dict) else {}
            pkind = primary.get("kind", "quantitative")
            if pkind not in ("quantitative", "qualitative"):
                issues.append(f"{ptag}.kind={pkind!r} 只能是 quantitative 或 qualitative")
            if not _text(primary.get("metric")):
                issues.append(f"{ptag}.metric 必须非空")
            if (_text(guard.get("metric")) and _text(primary.get("metric"))
                    and guard.get("metric") != primary.get("metric")):
                issues.append(
                    f"{ptag}.metric={primary.get('metric')!r} 与 primary_guard.metric="
                    f"{guard.get('metric')!r} 不一致：④ 不能换一个主答案来避开护栏"
                )
            if not isinstance(primary.get("guard_passed"), bool):
                issues.append(f"{ptag}.guard_passed 必须是 true/false")
            if pkind == "qualitative":
                for key in ("metric", "baseline_value", "intervention_value", "guard_passed"):
                    if key not in primary:
                        issues.append(f"{ptag}.{key} 缺失")
                if not _answer_text(primary.get("baseline_value")):
                    issues.append(f"{ptag}.baseline_value 必须写明基线的主答案（可为文字，不能 None/空）")
                if not _answer_text(primary.get("intervention_value")):
                    issues.append(f"{ptag}.intervention_value 必须写明干预后的主答案（可为文字，不能 None/空）")
            else:
                for key in PRIMARY_FIELDS:
                    if key not in primary:
                        issues.append(f"{ptag}.{key} 缺失")
                for key in ("baseline_value", "intervention_value", "relative_change"):
                    if not _num(primary.get(key)):
                        issues.append(f"{ptag}.{key} 必须是有限数值")
                b, i, rel = (primary.get("baseline_value"),
                             primary.get("intervention_value"),
                             primary.get("relative_change"))
                expected_rel = None
                if _num(b) and _num(i):
                    if float(b) == 0:
                        issues.append(f"{ptag}.baseline_value 不能为 0（无法计算相对变化）")
                    else:
                        diff = float(i) - float(b)
                        expected_rel = diff / abs(float(b)) if math.isfinite(diff) else None
                        if expected_rel is None or not math.isfinite(expected_rel):
                            issues.append(f"{ptag}.relative_change 无法重算：baseline/intervention 差值溢出")
                        elif _num(rel) and abs(float(rel) - expected_rel) > 5e-3 * max(1.0, abs(expected_rel)):
                            issues.append(
                                f"{ptag}.relative_change={rel} 与 "
                                f"(intervention-baseline)/|baseline|={expected_rel:.6g} 不一致；"
                                "不能自报一个与两列对不上的比例"
                            )
                allowed = guard.get("allowed_relative_change")
                checked_rel = expected_rel
                if _num(allowed) and checked_rel is not None:
                    should_pass = abs(checked_rel) <= float(allowed) + 1e-12
                    if primary.get("guard_passed") is not should_pass:
                        issues.append(
                            f"{ptag}.guard_passed={primary.get('guard_passed')} 与 "
                            f"|重算相对变化|={abs(checked_rel):.4g} / allowed={allowed} 不一致"
                        )
            if primary.get("guard_passed") is False and not _text(primary.get("independent_evidence")):
                issues.append(
                    f"{ptag}.guard_passed=false 但没有 `independent_evidence`："
                    "主答案大幅偏离基线时，必须有独立证据（实验/文献/多模型一致/题面给定值）"
                    "证明是基线错了；没有就只能降级，不能把偏离包装成创新"
                )
        if m.get("passed") is False:
            issues.append(
                f"{tag}.passed=false，但 {item.get('id')} 仍是 adopted："
                "必须改成 downgraded 并写 downgrade_reason，不能把失败结果继续叫创新"
            )


def _merge_external_audit(root: Path, data, issues):
    """⑤ 是门禁，不能改自己的输入台账（否则会被判“执行期间输入变更”）。

    所以 ⑤ 把复核结果写到独立的 `reports/INNOVATION_AUDIT.json`，本函数按 id 合并到
    ledger 的内存副本里再校验；台账本身保持 ② 的设计 + ④ 的 measurement。
    """
    path = root / AUDIT_REL
    if not path.is_file():
        return
    try:
        doc = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:  # noqa: BLE001
        issues.append(f"创新复核文件不可读（{path}）：{exc}")
        return
    if not isinstance(doc, dict):
        issues.append(f"`{AUDIT_REL}` 根节点必须是对象")
        return
    if type(doc.get("schema_version")) is not int or doc.get("schema_version") != 1:
        issues.append(f"`{AUDIT_REL}` 的 `schema_version` 必须是整数 1")
    items = doc.get("items")
    if not isinstance(items, dict):
        issues.append(f"`{AUDIT_REL}` 必须含 `items`（id → verdict/evidence）")
        return
    ledger_items = data.get("items")
    ledger_items = ledger_items if isinstance(ledger_items, list) else []
    # 台账里的 audit 块一律不算数：⑤ 的复核只能来自外部文件。先清空，
    # 再按外部文件逐 id 覆盖；缺 id 的 adopted 项会在 _check_audit 里报缺失。
    for item in ledger_items:
        if isinstance(item, dict):
            item.pop("audit", None)
    ledger_ids = {i.get("id") for i in ledger_items
                  if isinstance(i, dict) and isinstance(i.get("id"), str)}
    for key, val in items.items():
        if key not in ledger_ids:
            issues.append(f"`{AUDIT_REL}` 的 id={key!r} 不在台账里")
            continue
        if not isinstance(val, dict):
            issues.append(f"`{AUDIT_REL}` 的 id={key!r} 必须是对象")
            continue
        for item in ledger_items:
            if isinstance(item, dict) and item.get("id") == key:
                item["audit"] = val


def _check_audit(issues, adopted, require_pass=False):
    for item in adopted:
        tag = f"{item.get('id', '?')}.audit"
        audit = item.get("audit")
        if not isinstance(audit, dict):
            issues.append(f"{tag} 缺失：⑤ 必须对 adopted 项做独立复核")
            continue
        verdict = audit.get("verdict")
        if not isinstance(verdict, str) or verdict not in AUDIT_VERDICTS:
            issues.append(f"{tag}.verdict={verdict!r} 不在 {sorted(AUDIT_VERDICTS)}")
        if not _audit_evidence_ok(audit.get("evidence")):
            issues.append(
                f"{tag}.evidence 必须是可核对的复核记录：至少 {AUDIT_EVIDENCE_MIN_CHARS} 字，"
                "并含 reports/、code/、results/、figures/、paper/ 之一的路径"
                "（写 \"x\" 这类占位、或只说\"两列一致\"都没法核对）"
            )
        # ⑤ 本阶段允许 FAIL（发现失败正是门禁的职责）；但 ⑥/⑨ 不能在 FAIL 之后继续用该项。
        if require_pass and verdict != "PASS":
            issues.append(
                f"{tag}.verdict={verdict!r}：⑤ 未 PASS，⑥/⑨ 不能继续把该项当作已复核的创新"
            )


def _check_robustness(issues, adopted, core):
    core_ids = {id(x) for x in core}
    for item in adopted:
        if id(item) not in core_ids:
            continue
        tag = f"{item.get('id', '?')}.robustness"
        rob = item.get("robustness")
        if not isinstance(rob, dict):
            issues.append(
                f"{tag} 缺失：core 项必须在 {ROBUSTNESS_REL} 做稳健性检验（⑥）")
            continue
        if not isinstance(rob.get("survives"), bool):
            issues.append(f"{tag}.survives 必须是 true/false")
        if not _text(rob.get("evidence")):
            issues.append(f"{tag}.evidence 必须非空")
        # SKILL ⑥ 要求「至少做 2 类扰动/重抽样/口径对照」，并逐项记 what/result。
        #   只查 survives/evidence 时，一句「三组扰动方向一致」就能过 —— 读者无法知道
        #   到底扰了什么、每项结果如何，稳健性检验退化成一句自述。
        checks = rob.get("checks")
        if not isinstance(checks, list) or len(checks) < ROBUSTNESS_MIN_CHECKS:
            issues.append(
                f"{tag}.checks 必须是长度 ≥{ROBUSTNESS_MIN_CHECKS} 的列表："
                "逐项写做了什么扰动/重抽样/口径对照，以及该条件下的实际结果"
                "（只有一句 evidence 不算做了稳健性检验）"
            )
        else:
            seen_what = set()
            for idx, check in enumerate(checks, 1):
                ctag = f"{tag}.checks[{idx}]"
                if not isinstance(check, dict):
                    issues.append(f"{ctag} 必须是对象（what/result）")
                    continue
                what = check.get("what")
                if not _text(what):
                    issues.append(f"{ctag}.what 必须非空（写清扰动/对照的条件）")
                else:
                    key = " ".join(what.split()).lower()
                    if key in seen_what:
                        issues.append(
                            f"{ctag}.what={what!r} 重复：同一项检查不要重复记，"
                            f"至少要有 {ROBUSTNESS_MIN_CHECKS} 个不同的检查"
                        )
                    seen_what.add(key)
                if not _text(check.get("result")):
                    issues.append(f"{ctag}.result 必须非空（写该条件跑出来的实际结果）")
        if rob.get("survives") is False:
            if not _text(item.get("claim_scope")):
                issues.append(
                    f"{tag}.survives=false 时必须写 `claim_scope`：把结论限定到实际成立的范围内"
                )
            issues.append(
                f"{tag}.survives=false 的 core 项不能继续保留 core=true："
                "⑥ 必须把它改为 core=false（supporting/关键处理）或 status=downgraded，"
                "否则 ⑨ 无法把它放进 2.5"
            )


def _check_write(issues, adopted, core, all_items=()):
    all_items = all_items if isinstance(all_items, list) else []
    for item in all_items:
        if not isinstance(item, dict) or item.get("status") == "adopted":
            continue
        paper = item.get("paper")
        paper = paper if isinstance(paper, dict) else {}
        if str(paper.get("section", "")).startswith("2.5"):
            issues.append(
                f"{item.get('id', '?')} 的状态是 {item.get('status')!r}，却登记在 2.5："
                "rejected/downgraded 的项不能写进“本文主要创新点”，只能进局限/负结果"
            )
    for item in adopted:
        tag = f"{item.get('id', '?')}.paper"
        paper = item.get("paper")
        if not isinstance(paper, dict):
            issues.append(
                f"{tag} 缺失：⑨ 必须在 {PAPER_REL} 登记它写进哪一节、哪个 claim")
            continue
        if not _text(paper.get("section")):
            issues.append(f"{tag}.section 必须非空（如 2.5）")
        if not _text(paper.get("claim_id")):
            issues.append(f"{tag}.claim_id 必须非空（正文里可核对的 claim 标识）")
        measurement = item.get("measurement")
        measurement = measurement if isinstance(measurement, dict) else {}
        primary = measurement.get("primary")
        primary = primary if isinstance(primary, dict) else {}
        audit = item.get("audit")
        audit = audit if isinstance(audit, dict) else {}
        if audit.get("verdict") != "PASS":
            issues.append(
                f"{tag} 的 ⑤ 复核不是 PASS（{audit.get('verdict')!r}）："
                "adopted 项不能进入论文 2.5；先回 ④/② 修，或降级为 downgraded"
            )
        if (primary.get("guard_passed") is False
                and str(paper.get("section", "")).startswith("2.5")):
            issues.append(
                f"{tag} 的主答案偏离超 guard：即使有独立证据，也不能写进 2.5；"
                "只能作为条件性对照/局限，或先降级为 downgraded/关键处理"
            )
        rob_any = item.get("robustness")
        rob_any = rob_any if isinstance(rob_any, dict) else {}
        if (str(paper.get("section", "")).startswith("2.5")
                and rob_any.get("survives") is not True):
            issues.append(
                f"{tag} 写进 2.5 但 robustness.survives 不是 true："
                "2.5 的每一项都必须有通过的稳健性检验；不稳的只能进关键处理/局限"
            )
        if item.get("core") is True:
            if not str(paper.get("section", "")).startswith("2.5"):
                issues.append(f"{tag}.section 必须是 2.5（核心创新写在“本文主要创新点”）")
            rob = item.get("robustness")
            rob = rob if isinstance(rob, dict) else {}
            if rob.get("survives") is False:
                issues.append(
                    f"{tag} 是 core 但 robustness.survives=false："
                    "不能继续放在 2.5，降级为 supporting/关键处理"
                )


def validate(root, stage="design"):
    """返回问题列表；空列表 = 通过。

    四份文件各归一个阶段：
      design      `INNOVATION_LEDGER.json`（②）
      measurement `INNOVATION_MEASUREMENT.json`（④）
      robustness  `INNOVATION_ROBUSTNESS.json`（⑥）
      paper       `INNOVATION_PAPER.json`（⑨）
    ⑤ 的 `INNOVATION_AUDIT.json` 仍是外部复核文件。本函数按 stage 只合并**已发生**
    的那些 sidecar，再在同一份内存视图上校验；盘上的设计台账始终不被下游改写。
    """
    root = Path(root).resolve()
    data, issues = _load(root)
    if data is None:
        return issues
    _check_design_ownership(data, issues)
    if stage in ("code", "audit", "robustness", "write", "all"):
        _merge_sidecar(root, MEASUREMENT_REL, data, issues)
    if stage in ("robustness", "write", "all"):
        _merge_sidecar(root, ROBUSTNESS_REL, data, issues)
    if stage in ("write", "all"):
        _merge_sidecar(root, PAPER_REL, data, issues)
    adopted, core = _check_design(data, root, issues, stage=stage)
    if stage in ("code", "audit", "robustness", "write", "all"):
        _check_measurement(root, issues, adopted)
    if stage in ("audit", "robustness", "write", "all"):
        if adopted and not (root / AUDIT_REL).is_file():
            issues.append(
                f"缺 `{AUDIT_REL}`：⑤ 的独立复核必须写在外部文件，"
                "不能把 audit 块塞进台账自证"
            )
        _merge_external_audit(root, data, issues)
        _check_audit(issues, adopted,
                     require_pass=stage in ("robustness", "write", "all"))
    if stage in ("robustness", "write", "all"):
        _check_robustness(issues, adopted, core)
    if stage in ("write", "all"):
        _check_write(issues, adopted, core, data.get("items", []))
    return issues


def main() -> int:
    ap = argparse.ArgumentParser(description="创新台账自检（基线→失败模式→增量→审计）")
    ap.add_argument("--root", type=Path, default=Path.cwd())
    ap.add_argument("--stage", choices=STAGES, default="design",
                    help="design=②；code=④；audit=⑤；robustness=⑥；write=⑨；all=全链")
    ap.add_argument("--json", action="store_true", help="以 JSON 输出，便于程序消费")
    args = ap.parse_args()
    root = args.root.resolve()
    issues = validate(root, args.stage)
    if args.json:
        print(json.dumps({"root": str(root), "stage": args.stage,
                          "status": "PASS" if not issues else "FAIL",
                          "issues": issues}, ensure_ascii=False, indent=2))
    elif issues:
        print(f"创新台账自检不过（stage={args.stage}，{len(issues)} 条）：\n")
        for i, problem in enumerate(issues, 1):
            print(f"  {i}. {problem}")
        print("\n修法：按 `skills/2Modeling-design/references/innovation-ledger.md` 补齐；"
              "不要靠改措辞绕过——adopted 必须有基线、失败模式、可证伪 test、实测 delta；"
              "测失败就写 downgraded + downgrade_reason。")
    else:
        print(f"创新台账自检通过（stage={args.stage}）：{root}")
    # 只有“台账本身缺失/不可读”才是 rc=2；INNOVATION_AUDIT.json 解析失败是普通问题（rc=1）。
    missing = any(p.startswith("缺创新台账") or "创新台账不可读" in p for p in issues)
    return 0 if not issues else (2 if missing else 1)


if __name__ == "__main__":
    raise SystemExit(main())
