# -*- coding: utf-8 -*-
"""Role-based paper structure: load roles/profile, assemble paper-structure.tex.

P1 的目标是“角色化但行为不变”：
  - 模板 `roles.json` 说明每个角色怎么实现；
  - 赛题 profile（或模板默认 profile）说明要哪些角色、什么顺序；
  - 本模块把两者合成为 `paper/paper-structure.tex` 与 `paper/structure.json`。

这里刻意**不 import** `lib.web.check_skeleton`，也不 import 驱动；
它是 P1 的独立装配器，可以被 ⑨、测试和将来的 CLI 共用。
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

TEMPLATES_REL = Path("skills/9Paper-writing/templates")
PROFILE_REL = Path("runtime/effective_profile.json")
INTAKE_REL = Path("reports/INTAKE.json")
ANALYSIS_REL = Path("reports/ANALYSIS_MODELING_REPORT.md")

PAGE_KINDS = {"cover", "abstract", "contents", "body", "references", "ai_statement", "appendix"}
CN_DIGITS = "零一二三四五六七八九"
COUNTING_UNCERTAIN_RE = re.compile(r"小问|子问题|分几问|拆成|分问|几问|分几")


class StructureError(RuntimeError):
    """A fatal structure problem; `.code` is the CLI exit code."""

    def __init__(self, message: str, code: int = 2):
        super().__init__(message)
        self.code = int(code)


def canonical_json(value) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def cn_num(n: int) -> str:
    """1..99 的中文数字；超过 99 直接写阿拉伯数字（不静默写错）。"""
    if not isinstance(n, int) or n < 1:
        raise ValueError("cn_num expects a positive integer")
    if n < 10:
        return CN_DIGITS[n]
    if n < 20:
        return "十" + (CN_DIGITS[n % 10] if n % 10 else "")
    if n < 100:
        tens, ones = divmod(n, 10)
        return CN_DIGITS[tens] + "十" + (CN_DIGITS[ones] if ones else "")
    return str(n)


def _load_json(path: Path, what: str, code: int = 2) -> dict:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except OSError as exc:
        raise StructureError(f"{what} 读不到：{path}（{exc}）", code) from exc
    except json.JSONDecodeError as exc:
        raise StructureError(f"{what} 不是合法 JSON：{path}（{exc}）", code) from exc
    if not isinstance(data, dict):
        raise StructureError(f"{what} 顶层必须是对象：{path}", code)
    return data


def resolve_template(root: Path, template: str | None, profile_path: Path | None) -> str:
    if template:
        return template
    if profile_path and Path(profile_path).is_file():
        data = _load_json(Path(profile_path), "profile")
        if isinstance(data.get("template"), str) and data["template"]:
            return data["template"]
    found = sorted((Path(root) / TEMPLATES_REL).glob("*/*/roles.json"))
    if len(found) == 1:
        return found[0].parent.relative_to(Path(root) / TEMPLATES_REL).as_posix()
    if not found:
        raise StructureError(f"{TEMPLATES_REL} 下没有任何 roles.json", 2)
    raise StructureError("有多个模板族，必须显式指定 --template", 2)


def load_roles(root: Path, template: str):
    path = Path(root) / TEMPLATES_REL / template / "roles.json"
    data = _load_json(path, "模板 roles.json", 2)
    if data.get("schema_version") != 1:
        raise StructureError("roles.json 的 schema_version 必须是 1", 2)
    if data.get("template") != template:
        raise StructureError(f"roles.json.template={data.get('template')!r} 与 {template!r} 不一致", 2)
    roles = data.get("roles")
    if not isinstance(roles, dict) or not roles:
        raise StructureError("roles.json.roles 必须是非空对象", 2)
    for rid, role in roles.items():
        if not isinstance(role, dict):
            raise StructureError(f"role {rid!r} 不是对象", 2)
        placement = role.get("placement")
        if placement not in {"block", "file", "external"}:
            raise StructureError(f"role {rid!r} 的 placement 非法：{placement!r}", 3)
        if placement == "block" and not role.get("block"):
            raise StructureError(f"role {rid!r} 缺 block", 3)
        if placement == "file" and not (role.get("file") or role.get("file_pattern")):
            raise StructureError(f"role {rid!r} 缺 file/file_pattern", 3)
        if placement == "external" and not role.get("project"):
            raise StructureError(f"role {rid!r} 缺 project", 3)
        if role.get("page_kind") is not None and role["page_kind"] not in PAGE_KINDS:
            raise StructureError(f"role {rid!r} 的 page_kind 未知：{role['page_kind']!r}", 3)
        if role.get("mode") not in (None, "section", "inline", "merged", "none"):
            raise StructureError(f"role {rid!r} 的 mode 非法：{role['mode']!r}", 3)
    return data, path


def load_profile(root: Path, template: str, profile_path: Path | None):
    if profile_path is not None:
        path = Path(profile_path)
        if not path.is_absolute():
            path = Path(root) / path
        if path.is_file():
            data = _load_json(path, "effective_profile", 2)
            source = "effective_profile"
        else:
            # 显式给了 profile 却不存在：不静默回退（否则调用方以为读到了）
            raise StructureError(f"profile 不存在：{path}", 2)
    else:
        path = Path(root) / TEMPLATES_REL / template / "structure.default.json"
        data = _load_json(path, "模板 structure.default.json", 2)
        source = "template-default"
    if data.get("schema_version") != 1:
        raise StructureError("profile 的 schema_version 必须是 1", 2)
    if data.get("template") != template:
        raise StructureError(f"profile.template={data.get('template')!r} 与 {template!r} 不一致", 2)
    if not isinstance(data.get("structure"), dict):
        raise StructureError("profile.structure 必须是对象", 2)
    return data, source


def _counting_uncertain(intake: dict) -> bool:
    problem = intake.get("problem") if isinstance(intake.get("problem"), dict) else {}
    confidence = str(problem.get("confidence", "")).lower()
    if confidence in {"low", "uncertain"}:
        return True
    for item in problem.get("uncertain") or []:
        if COUNTING_UNCERTAIN_RE.search(str(item)):
            return True
    return False


def _analysis_subquestion_count(text: str) -> int | None:
    """在 ANALYSIS_MODELING_REPORT 里找“子问题”小节后的第一张表，数数据行。"""
    lines = text.splitlines()
    start = None
    for i, line in enumerate(lines):
        if re.match(r"^#{1,6}\s+.*子问题", line):
            start = i + 1
            break
    if start is None:
        return None
    table = []
    for line in lines[start:]:
        stripped = line.strip()
        if stripped.startswith("|"):
            table.append(stripped)
        elif table:
            break
    if len(table) < 2:
        return None
    # 第一行是表头，第二行通常是 |---| 分隔行；之后才是数据行。
    data_rows = []
    for row in table[1:]:
        cells = [c.strip() for c in row.strip("|").split("|")]
        if all(re.fullmatch(r":?-{2,}:?", c) for c in cells if c):
            continue
        data_rows.append(row)
    return len(data_rows) or None


def resolve_problem_count(root: Path, profile: dict) -> dict:
    structure = profile.get("structure") or {}
    explicit = structure.get("problem_count")
    if isinstance(explicit, int) and not isinstance(explicit, bool) and explicit > 0:
        return {"problem_count": explicit, "problem_count_source": "effective_profile",
                "intake_subquestion_count": None, "warnings": []}

    intake_count = None
    intake_path = Path(root) / INTAKE_REL
    if intake_path.is_file():
        try:
            intake = _load_json(intake_path, "INTAKE.json")
            problem = intake.get("problem") if isinstance(intake.get("problem"), dict) else {}
            sub = problem.get("subquestions")
            if isinstance(sub, list) and sub:
                intake_count = len(sub)
                if not _counting_uncertain(intake):
                    return {"problem_count": intake_count,
                            "problem_count_source": "intake:problem.subquestions",
                            "intake_subquestion_count": intake_count, "warnings": []}
        except StructureError:
            # 读题结果坏了不应阻断建模报告回退；check 会在需要时单独报
            pass

    analysis_path = Path(root) / ANALYSIS_REL
    if analysis_path.is_file():
        try:
            count = _analysis_subquestion_count(analysis_path.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            count = None
        if count:
            warnings = []
            if intake_count is not None and intake_count != count:
                warnings.append(
                    f"INTAKE 读数 {intake_count} 与论文问数 {count} 不一致；"
                    "题面未分问时以建模设计（ANALYSIS_MODELING_REPORT §子问题）为准")
            return {"problem_count": count, "problem_count_source": "analysis_report",
                    "intake_subquestion_count": intake_count, "warnings": warnings}

    raise StructureError(
        "无法确定 problem_count：effective_profile 没有显式值；"
        "INTAKE.json#problem.subquestions 缺失/uncertain；"
        "ANALYSIS_MODELING_REPORT.md 也找不到“子问题”表", 5)


def _validate_structure(roles: dict, structure: dict) -> None:
    order = structure.get("order")
    disabled = structure.get("disabled") or []
    supplement = structure.get("supplement") or []
    if not isinstance(order, list) or not order:
        raise StructureError("structure.order 必须是非空列表", 3)
    if len(set(order)) != len(order):
        raise StructureError("structure.order 有重复角色", 3)
    unknown = [r for r in order if r not in roles]
    if unknown:
        raise StructureError(f"structure.order 引用了未知角色：{unknown}", 3)
    unknown = [r for r in disabled if r not in roles]
    if unknown:
        raise StructureError(f"structure.disabled 引用了未知角色：{unknown}", 3)
    unknown = [r for r in supplement if r not in roles]
    if unknown:
        raise StructureError(f"structure.supplement 引用了未知角色：{unknown}", 3)
    for rid in disabled:
        role = roles[rid]
        if not role.get("disablable"):
            raise StructureError(f"角色 {rid!r} 不可禁用（disablable=false）", 3)
    for rid in order:
        if rid in disabled:
            continue
        role = roles[rid]
        mode = role.get("mode", "section")
        if mode in {"inline", "merged"}:
            host = role.get("host")
            if not host or host not in order or host in disabled:
                raise StructureError(f"角色 {rid!r} 的 mode={mode} 需要启用的 host", 3)
        if mode == "none" and not str(role.get("waiver") or "").strip():
            raise StructureError(f"角色 {rid!r} 的 mode=none 需要非空 waiver", 3)
    enabled = [r for r in order if r not in disabled]
    for rid in enabled:
        pinned = roles[rid].get("pinned")
        if pinned == "first" and enabled[0] != rid:
            raise StructureError(f"角色 {rid!r} 必须排第一", 3)
        if pinned == "last" and enabled[-1] != rid:
            raise StructureError(f"角色 {rid!r} 必须排最后", 3)


def _role_files(role: dict, problem_count: int, template_dir: Path) -> tuple[list[str], list[str]]:
    """Return (files, warnings). Paths are relative to the paper workspace."""
    files, warnings = [], []
    placement = role.get("placement")
    if placement == "block":
        files.append(role["block"])
        if not (template_dir / role["block"]).is_file():
            raise StructureError(f"角色 block 缺失：{role['block']}", 3)
        # references / materials_list 的 block 是包装，辅助 file 也要进 files 供孤儿检查
        if role.get("file"):
            files.append(role["file"])
    elif placement == "file":
        if role.get("file_pattern"):
            for i in range(1, problem_count + 1):
                rel = role["file_pattern"].replace("{N}", str(i))
                files.append(rel)
                if not (template_dir / rel).is_file():
                    warnings.append(f"问题文件暂缺（写手稍后创建）：{rel}")
        else:
            files.append(role["file"])
            if not (template_dir / role["file"]).is_file():
                raise StructureError(f"角色 file 缺失：{role['file']}", 3)
        if role.get("wrapper_block"):
            files.insert(0, role["wrapper_block"])
            if not (template_dir / role["wrapper_block"]).is_file():
                raise StructureError(f"角色 wrapper block 缺失：{role['wrapper_block']}", 3)
        if role.get("file") and role.get("block"):
            # references / materials_list: block 是包装，file 是辅助产物
            files.append(role["file"])
    return files, warnings


def build_plan(root: Path, template: str, roles_doc: dict, profile: dict, profile_source: str) -> dict:
    roles = roles_doc["roles"]
    structure = profile.get("structure") or {}
    _validate_structure(roles, structure)
    order = list(structure["order"])
    disabled = list(structure.get("disabled") or [])
    supplement = list(structure.get("supplement") or [])
    template_dir = Path(root) / TEMPLATES_REL / template

    resolved = resolve_problem_count(root, profile)
    problem_count = resolved["problem_count"]
    warnings = list(resolved.get("warnings") or [])

    enabled = [r for r in order if r not in disabled]
    files, page_kinds, modes, deliverables = [], {}, {}, set()
    section_numbers = {}
    section_no = 0
    alias = {}
    for rid in enabled:
        role = roles[rid]
        placement = role.get("placement")
        if placement == "external":
            supplement.append(rid) if rid not in supplement else None
        mode = role.get("mode", "section")
        modes[rid] = mode
        if placement != "external" and mode not in {"inline", "merged", "none"}:
            role_files, role_warn = _role_files(role, problem_count, template_dir)
            files.extend(role_files)
            warnings.extend(role_warn)
        if placement != "external" and mode not in {"inline", "merged", "none"}:
            numbering = role.get("numbering")
            if numbering == "section":
                section_no += 1
                section_numbers[rid] = cn_num(section_no)
        kind = role.get("page_kind")
        if kind is not None and placement != "external" and mode not in {"inline", "merged", "none"}:
            if rid == "references" and role.get("shares_page_with") == "ai_statement" \
                    and "ai_statement" in enabled:
                kind = "ai_statement"
                alias["references"] = "ai_statement"
            page_kinds.setdefault(kind, []).append(rid)
        for item in role.get("deliverables") or []:
            deliverables.add(item)

    # supplement（如 appendix_pdf）不进正文 order，但它的交付物要算进来
    for rid in supplement:
        for item in (roles.get(rid) or {}).get("deliverables") or []:
            deliverables.add(item)

    # title 与 abstract 同页：title 自己 page_kind=null，但要进 abstract 页面组
    for rid in enabled:
        role = roles[rid]
        if role.get("page_kind") is None and role.get("shares_page_with"):
            host_kind = roles.get(role["shares_page_with"], {}).get("page_kind")
            if host_kind in page_kinds and rid not in page_kinds[host_kind]:
                page_kinds[host_kind].insert(0, rid)

    page_markers = {"abstract": ["摘要"]}
    body_roles = page_kinds.get("body") or []
    if body_roles and body_roles[0] in section_numbers:
        page_markers["body"] = [f"{section_numbers[body_roles[0]]}、"]
    for kind in ("ai_statement", "references"):
        if kind in page_kinds:
            first = page_kinds[kind][0]
            if first in section_numbers:
                page_markers[kind] = [f"{section_numbers[first]}、"]
    if "appendix" in page_kinds:
        page_markers["appendix"] = ["附录"]

    # 健全性：5_problemN 只做 warning，不作为 problem_count 来源
    paper_dir = Path(root) / "paper" / "sections"
    if paper_dir.is_dir():
        found = sorted(int(m.group(1)) for p in paper_dir.glob("5_problem*.tex")
                       if (m := re.fullmatch(r"5_problem(\d+)\.tex", p.name)))
        if found and found != list(range(1, problem_count + 1)):
            warnings.append(f"5_problemN 文件编号 {found} 与 problem_count={problem_count} 不一致")

    plan = {
        "schema_version": 1,
        "profile": profile.get("profile") or "unknown",
        "profile_source": profile_source,
        "template": template,
        "template_roles_sha256": sha256_file(template_dir / "roles.json"),
        "title": None,
        "title_source": "unset",
        "keywords": None,
        "problem_count": problem_count,
        "problem_count_source": resolved["problem_count_source"],
        "intake_subquestion_count": resolved.get("intake_subquestion_count"),
        "enabled": enabled,
        "disabled": disabled,
        "supplement": supplement,
        "order": order,
        "modes": modes,
        "page_kinds": page_kinds,
        "page_kind_aliases": alias,
        "section_numbers": section_numbers,
        "page_markers": page_markers,
        "files": files,
        "roles": {rid: roles[rid] for rid in enabled},
        "deliverables": sorted(deliverables),
        "warnings": warnings,
    }
    return plan


def render_tex(plan: dict) -> str:
    roles = plan.get("roles") or {}
    out = [
        "% generated by lib.paper_structure from <profile>; don't hand-edit",
        f"% template={plan['template']} profile={plan.get('profile', 'unknown')} "
        f"problem_count={plan.get('problem_count', 0)}",
    ]
    for rid in plan.get("enabled") or []:
        role = roles.get(rid, {})
        if role.get("placement") == "external":
            continue
        if role.get("mode") in {"inline", "merged", "none"}:
            continue
        if role.get("barrier_before"):
            out.append("\\FloatBarrier")
        if role.get("placement") == "block":
            out.append(f"\\input{{{role['block'][:-4]}}}")
            continue
        if role.get("file_pattern"):
            if role.get("wrapper_block"):
                out.append(f"\\input{{{role['wrapper_block'][:-4]}}}")
            for i in range(1, int(plan["problem_count"]) + 1):
                rel = role["file_pattern"].replace("{N}", str(i))
                out.append(f"\\input{{{rel[:-4]}}}")
            continue
        if role.get("file"):
            out.append(f"\\input{{{role['file'][:-4]}}}")
    return "\n".join(out) + "\n"


def _semantic_digest(plan: dict) -> str:
    keys = ("profile", "template", "problem_count", "enabled", "disabled", "supplement",
            "page_kinds", "page_kind_aliases", "section_numbers", "page_markers", "title")
    return sha256_text(canonical_json({k: plan.get(k) for k in keys}))


def assemble(root, profile_path=None, template=None, out_dir=None) -> dict:
    root = Path(root).resolve()
    profile_path = Path(profile_path) if profile_path else None
    template = resolve_template(root, template, profile_path)
    roles_doc, roles_path = load_roles(root, template)
    profile, profile_source = load_profile(root, template, profile_path)
    plan = build_plan(root, template, roles_doc, profile, profile_source)
    tex = render_tex(plan)
    plan["inputs"] = re.findall(r"\\input\{([^{}]+)\}", tex)
    plan["paper_structure_sha256"] = sha256_text(tex)
    plan["structure_sha256"] = _semantic_digest(plan)

    out = Path(out_dir) if out_dir else (root / "paper")
    out.mkdir(parents=True, exist_ok=True)
    for name, text in (("paper-structure.tex", tex), ("structure.json", canonical_json(plan))):
        tmp = out / (name + ".tmp")
        tmp.write_text(text, encoding="utf-8")
        tmp.replace(out / name)
    return plan


def check(root, out_dir=None) -> dict:
    root = Path(root).resolve()
    out = Path(out_dir) if out_dir else (root / "paper")
    issues = []
    structure_path = out / "structure.json"
    tex_path = out / "paper-structure.tex"
    if not structure_path.is_file():
        return {"status": "FAIL", "issues": ["缺 paper/structure.json"]}
    if not tex_path.is_file():
        return {"status": "FAIL", "issues": ["缺 paper/paper-structure.tex"]}
    try:
        plan = json.loads(structure_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"status": "FAIL", "issues": [f"structure.json 不可读：{exc}"]}
    tex = tex_path.read_text(encoding="utf-8")
    if plan.get("paper_structure_sha256") != sha256_text(tex):
        issues.append("paper-structure.tex 与 structure.json.paper_structure_sha256 不一致")
    if "inputs" in plan:
        actual_inputs = re.findall(r"\\input\{([^{}]+)\}", tex)
        if actual_inputs != plan["inputs"]:
            issues.append("paper-structure.tex 的 \\input 序列与 structure.json.inputs 不一致")
    if plan.get("structure_sha256") != _semantic_digest(plan):
        issues.append("structure.json 的语义摘要不一致（手改过？）")
    for rel in plan.get("files") or []:
        if not (out / rel).is_file():
            issues.append(f"缺文件：{rel}")
    problem_count = plan.get("problem_count")
    if not isinstance(problem_count, int) or problem_count < 1:
        issues.append("problem_count 不是正整数")
    else:
        found = sorted(int(m.group(1)) for p in (out / "sections").glob("5_problem*.tex")
                       if (m := re.fullmatch(r"5_problem(\d+)\.tex", p.name)))
        if found and found != list(range(1, problem_count + 1)):
            issues.append(f"5_problemN 编号 {found} 与 problem_count={problem_count} 不一致")
    return {"status": "PASS" if not issues else "FAIL", "issues": issues}


def sync_title(root, out_dir=None) -> dict:
    root = Path(root).resolve()
    out = Path(out_dir) if out_dir else (root / "paper")
    structure_path = out / "structure.json"
    title_path = out / "blocks" / "title.tex"
    if not structure_path.is_file():
        raise StructureError("sync-title：缺 paper/structure.json", 6)
    if not title_path.is_file():
        raise StructureError("sync-title：缺 paper/blocks/title.tex", 6)
    text = title_path.read_text(encoding="utf-8", errors="replace")
    m = re.search(r"\\papertitle\s*\{([^{}]*)\}", text)
    if not m:
        raise StructureError("sync-title：title.tex 里没有 \\papertitle{...}", 6)
    title = re.sub(r"\s+", " ", m.group(1)).strip()
    if not title or title.startswith("<") or "论文标题" in title:
        plan = json.loads(structure_path.read_text(encoding="utf-8"))
        plan.setdefault("warnings", []).append("title 仍是占位符，未回填")
        structure_path.write_text(canonical_json(plan), encoding="utf-8")
        return plan
    plan = json.loads(structure_path.read_text(encoding="utf-8"))
    plan["title"] = title
    plan["title_source"] = "blocks/title.tex"
    plan["structure_sha256"] = _semantic_digest(plan)
    structure_path.write_text(canonical_json(plan), encoding="utf-8")
    return plan
