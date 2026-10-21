#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""The data-layer lock between ④ (data/claim) and ⑦ (canvas/composition).

A figure is split into three files:

    figures/data/<id>.npz       numbers only (④ owns, read-only for ⑦)
    figures/spec/<id>.json      recipe + field mapping + layout (④ writes the
                                semantic part; ⑦ may change layout/options only)
    figures/<id>.lock.json      hashes of the bundle, the spec's semantic part,
                                the source files and the claim (④ owns)

`④` calls ``studio.save_bundle(...)`` (or this CLI) to write all three.
`⑦` renders from the bundle and spec; it may change recipe/layout/colour, but
must not change the data, the field mapping, the statistics or the claim.
`⑧` runs ``verify`` before judging the figure.

The lock is a contract, not a signature: it catches accidental/unauthorised
edits (a regenerated bundle without a new lock, a spec edited in place, a
source file changed after the bundle was cut).  It is deliberately
dependency-free (NumPy + stdlib) so ``audit_studio.py`` can import it.

Usage:
    python skills/figure-studio/scripts/figure_lock.py verify --root .
    python skills/figure-studio/scripts/figure_lock.py verify --root . --figure q3_dryfront
    python skills/figure-studio/scripts/figure_lock.py build --root . --figure q3_dryfront
    python skills/figure-studio/scripts/figure_lock.py show --root . --figure q3_dryfront
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import uuid
from pathlib import Path

try:
    import numpy as np
except ImportError:                      # pragma: no cover - audit gives an advisory
    np = None

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SCHEMA_VERSION = 1
FIGURE_ID = re.compile(r"[a-zA-Z0-9_-]+")
NUMBER = re.compile(r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?%?")
KIND_PREFIX = {"data": "[lock:data]", "contract": "[lock:contract]",
               "advisory": "[lock:advisory]"}


# ---------------------------------------------------------------------------
# paths / json
# ---------------------------------------------------------------------------
def data_rel(figure_id: str) -> str:
    return f"figures/data/{figure_id}.npz"


def spec_rel(figure_id: str) -> str:
    return f"figures/spec/{figure_id}.json"


def lock_rel(figure_id: str) -> str:
    return f"figures/{figure_id}.lock.json"


def _load(path: Path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return default


def _write_json(path: Path, data) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def _rooted(root: Path, rel: str) -> Path:
    """Resolve a project-relative path and refuse to escape the workspace."""
    root = Path(root).resolve()
    path = (root / str(rel)).resolve()
    if not path.is_relative_to(root):
        raise ValueError(f"路径越界：{rel}")
    return path


def _sha_file(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _sha_text(text: str) -> str:
    return hashlib.sha256(str(text or "").encode("utf-8")).hexdigest()


def _canonical(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def numbers(text: str) -> list[str]:
    """Numeric tokens in a claim/caption, kept as written (``46``, ``0.15``)."""
    return NUMBER.findall(str(text or ""))


def _as_list(value) -> list:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return list(value)
    return [value]


# ---------------------------------------------------------------------------
# semantic part of the spec (what ⑦ may NOT change)
# ---------------------------------------------------------------------------
def _panel_semantic(panel: dict) -> dict:
    fields = sorted(str(x) for x in _as_list(panel.get("fields")))
    raw_mapping = panel.get("field_mapping") or {}
    mapping = {}
    if isinstance(raw_mapping, dict):
        for key, value in raw_mapping.items():
            mapping[str(key)] = value
    claim = str(panel.get("claim") or "")
    return {
        "id": str(panel.get("id") or ""),
        "fields": fields,
        "field_mapping": mapping,
        "claim": claim,
        "claim_sha256": _sha_text(claim),
    }


def spec_semantic(spec: dict) -> dict:
    """The part of a spec that defines *meaning*, not presentation.

    ``recipe``, ``options``, ``title``, ``axes_mm`` and ``layout`` are
    presentation: ⑦ may change them.  Fields, field mapping, statistics and
    claims are the data contract: ④ owns them.
    """
    claim = str(spec.get("claim") or "")
    return {
        "figure_id": str(spec.get("figure_id") or ""),
        "language": spec.get("language"),
        "template": spec.get("template"),
        "claim": claim,
        "claim_sha256": _sha_text(claim),
        "statistics": spec.get("statistics") or {},
        "data_path": ((spec.get("data") or {}) if isinstance(spec.get("data"), dict) else {}).get("path"),
        "data_fields": ((spec.get("data") or {}) if isinstance(spec.get("data"), dict) else {}).get("fields") or {},
        "panels": [_panel_semantic(p) for p in (spec.get("panels") or [])
                   if isinstance(p, dict)],
    }


def semantic_digest(spec: dict) -> str:
    return _sha_text(_canonical(spec_semantic(spec)))


# ---------------------------------------------------------------------------
# bundle metadata
# ---------------------------------------------------------------------------
def _npz_meta(path: Path) -> dict:
    if np is None:
        raise RuntimeError("figure_lock 需要 numpy")
    out = {}
    with np.load(path, allow_pickle=False) as bundle:
        for key in bundle.files:
            arr = bundle[key]
            out[key] = {"dtype": str(arr.dtype), "shape": list(arr.shape)}
    return out


def _unit_of(declared, name: str) -> str:
    value = (declared or {}).get(name)
    if isinstance(value, dict):
        return str(value.get("unit") or "")
    if value is None:
        return ""
    return str(value)


def _brief_info(root: Path, figure_id: str) -> dict | None:
    """Prefer a per-figure brief; fall back to the aggregate one if it matches."""
    for rel in (f"reports/figure_briefs/{figure_id}.json", "reports/FIGURE_BRIEF.json"):
        path = _rooted(root, rel)
        data = _load(path)
        if isinstance(data, dict) and str(data.get("figure_id") or "") == figure_id:
            return {"path": rel, "sha256": _sha_file(path),
                    "claim": str(data.get("claim") or "")}
    return None


def _brief_mismatches(brief: dict, spec: dict) -> list[str]:
    """Compare the FigureBrief with the bundle spec when they describe the same figure."""
    problems = []
    if not isinstance(brief, dict) or str(brief.get("figure_id") or "") != spec.get("figure_id"):
        return problems
    if brief.get("claim") and str(brief["claim"]).strip() != str(spec.get("claim") or "").strip():
        problems.append("FigureBrief.claim 与 spec.claim 不一致")
    for key in ("language", "template"):
        if brief.get(key) and spec.get(key) and brief[key] != spec[key]:
            problems.append(f"FigureBrief.{key}={brief[key]!r} 与 spec={spec[key]!r} 不一致")
    bstats = brief.get("statistics") or {}
    sstats = spec.get("statistics") or {}
    if isinstance(bstats, dict) and isinstance(sstats, dict):
        # Compare the keys the brief actually declares; the spec fills defaults
        # (e.g. p_values=False) that a minimal brief may omit.
        for key in ("interval", "test"):
            b, s = bstats.get(key), sstats.get(key)
            if isinstance(b, dict) and isinstance(s, dict):
                for sub, value in b.items():
                    if sub in s and s[sub] != value:
                        problems.append(f"FigureBrief.statistics.{key}.{sub} 与 spec 不一致")
        for key in ("unit", "paired"):
            if key in bstats and key in sstats and bstats[key] != sstats[key]:
                problems.append(f"FigureBrief.statistics.{key} 与 spec 不一致")
    brief_panels = {str(p.get("id")): p for p in (brief.get("panels") or []) if isinstance(p, dict)}
    spec_panels = {str(p.get("id")): p for p in (spec.get("panels") or []) if isinstance(p, dict)}
    for pid in sorted(set(brief_panels) - set(spec_panels)):
        problems.append(f"FigureBrief 有面板 {pid!r}，spec 里没有")
    for pid in sorted(set(spec_panels) - set(brief_panels)):
        problems.append(f"spec 有面板 {pid!r}，FigureBrief 里没有")
    for pid in sorted(set(brief_panels) & set(spec_panels)):
        b = brief_panels[pid]
        s = spec_panels[pid]
        bclaim = str(b.get("claim") or "").strip()
        sclaim = str(s.get("claim") or "").strip()
        if bclaim and sclaim and bclaim != sclaim:
            problems.append(f"面板 {pid}: FigureBrief.claim 与 spec.claim 不一致")
        # Brief's panel.fields is the free-form list; spec.fields must cover it.
        bfields = {str(x) for x in _as_list(b.get("fields"))}
        sfields = {str(x) for x in _as_list(s.get("fields"))}
        if bfields and not bfields.issubset(sfields):
            problems.append(f"面板 {pid}: spec.fields 缺少 FigureBrief 里的 {sorted(bfields - sfields)}")
    declared = brief.get("data") or []
    names = set()
    for item in declared:
        if isinstance(item, dict):
            for f in _as_list(item.get("fields")):
                names.add(str(f))
    if names and isinstance(spec.get("data"), dict):
        bundle_fields = set((spec["data"].get("fields") or {}).keys())
        missing = sorted(names - bundle_fields)
        if missing:
            problems.append(f"FigureBrief.data.fields 不在 bundle 里：{missing}")
    return problems


# ---------------------------------------------------------------------------
# build
# ---------------------------------------------------------------------------
def build(root: str | Path, figure_id: str, *, spec_path: str | None = None,
          brief_path: str | None = None) -> dict:
    """Write ``figures/<id>.lock.json`` from the current bundle/spec/sources.

    Called by ``studio.save_bundle``.  Running it again after a deliberate
    data regeneration is how ④ "re-signs" the figure; ⑦ must never call it.
    """
    root = Path(root)
    if not FIGURE_ID.fullmatch(figure_id):
        raise ValueError("figure id 只能是字母/数字/_/-")
    srel = str(spec_path or spec_rel(figure_id)).replace("\\", "/")
    spec_file = _rooted(root, srel)
    spec = _load(spec_file)
    if not isinstance(spec, dict):
        raise ValueError(f"读不到 spec：{srel}")
    if str(spec.get("figure_id") or "") != figure_id:
        raise ValueError(f"spec.figure_id={spec.get('figure_id')!r} 与 {figure_id!r} 不一致")
    if not str(spec.get("claim") or "").strip():
        raise ValueError("spec.claim 为空；④ 必须先写清 claim")
    data = spec.get("data") or {}
    if not isinstance(data, dict):
        raise ValueError("spec.data 必须是对象（path/fields）")
    if not isinstance(spec.get("panels") or [], list):
        raise ValueError("spec.panels 必须是数组")
    if not isinstance(spec.get("sources") or [], list):
        raise ValueError("spec.sources 必须是数组")
    drel = str(data.get("path") or data_rel(figure_id)).replace("\\", "/")
    dpath = _rooted(root, drel)
    if not dpath.is_file():
        raise ValueError(f"数据 bundle 不存在：{drel}")
    if np is None:
        raise RuntimeError("figure_lock 需要 numpy")
    npz_meta = _npz_meta(dpath)
    declared = data.get("fields") or {}
    fields = {}
    for name, meta in npz_meta.items():
        item = {"dtype": meta["dtype"], "shape": meta["shape"],
                "unit": _unit_of(declared, name)}
        fields[name] = item
    sources = {}
    for rel in spec.get("sources") or []:
        rel = str(rel).replace("\\", "/")
        path = _rooted(root, rel)
        if not path.is_file():
            raise ValueError(f"source 不存在：{rel}")
        sources[rel] = _sha_file(path)
    panels = {}
    for panel in spec.get("panels") or []:
        if not isinstance(panel, dict):
            continue
        canonical = _panel_semantic(panel)
        if canonical["id"] in panels:
            raise ValueError(f"spec.panels 有重复 id：{canonical['id']!r}")
        missing = [f for f in canonical["fields"] if f not in npz_meta]
        if missing:
            raise ValueError(f"面板 {canonical['id']}: bundle 缺少字段 {missing}")
        panels[canonical["id"]] = {
            "fields": canonical["fields"],
            "field_mapping": canonical["field_mapping"],
            "claim": canonical["claim"],
            "claim_sha256": canonical["claim_sha256"],
            "n": panel.get("n"),
        }
    if brief_path:
        brel = str(brief_path).replace("\\", "/")
        brief = _load(_rooted(root, brel))
    else:
        info = _brief_info(root, figure_id)
        brel = info["path"] if info else None
        brief = _load(_rooted(root, brel)) if brel else None
    brief_meta = None
    if brel:
        if not isinstance(brief, dict):
            raise ValueError(f"FigureBrief 读不到或不是对象：{brel}")
        if brief.get("figure_id") and str(brief["figure_id"]) != figure_id:
            raise ValueError(
                f"FigureBrief.figure_id={brief['figure_id']!r} 与 {figure_id!r} 不一致")
        problems = _brief_mismatches(brief, spec)
        if problems:
            raise ValueError("FigureBrief 与 spec 不一致：" + "；".join(problems))
        brief_meta = {"path": brel, "sha256": _sha_file(_rooted(root, brel))}
    lock = {
        "schema_version": SCHEMA_VERSION,
        "figure_id": figure_id,
        "owner": "4Coding-and-computation",
        "language": spec.get("language"),
        "template": spec.get("template"),
        "width_mm": spec.get("width_mm"),
        "claim": str(spec.get("claim") or ""),
        "claim_sha256": _sha_text(str(spec.get("claim") or "")),
        "claim_numbers": numbers(str(spec.get("claim") or "") + " " +
                                " ".join(str(p.get("claim") or "") for p in panels.values())),
        "statistics": spec.get("statistics") or {},
        "data": {"path": drel, "sha256": _sha_file(dpath), "fields": fields},
        "sources": sources,
        "panels": panels,
        "spec": {"path": srel, "semantic_sha256": semantic_digest(spec)},
    }
    if brief_meta:
        lock["brief"] = brief_meta
    _write_json(root / lock_rel(figure_id), lock)
    return lock


# ---------------------------------------------------------------------------
# verify
# ---------------------------------------------------------------------------
def _issue(figure_id: str, kind: str, message: str) -> dict:
    return {"figure": figure_id, "kind": kind, "message": message}


def format_issue(issue: dict) -> str:
    prefix = KIND_PREFIX.get(issue.get("kind"), "[lock]")
    return f"{prefix} {issue.get('figure')}: {issue.get('message')}"


def _allowed_numbers(lock: dict) -> set[str]:
    allowed = set(str(x) for x in (lock.get("claim_numbers") or []))
    for panel in (lock.get("panels") or {}).values():
        allowed.update(str(x) for x in numbers(panel.get("claim") or ""))
    return allowed


def verify_one(root: str | Path, figure_id: str, *, check_meta: bool = True) -> list[dict]:
    """Check one lock.  Returns issue dicts; empty means the contract holds."""
    try:
        return _verify_one(root, figure_id, check_meta=check_meta)
    except (ValueError, TypeError, AttributeError, KeyError, OSError) as exc:
        return [_issue(str(figure_id), "contract", f"锁/路径不可用：{exc}")]


def _verify_one(root: str | Path, figure_id: str, *, check_meta: bool = True) -> list[dict]:
    root = Path(root)
    if not FIGURE_ID.fullmatch(str(figure_id)):
        return [_issue(str(figure_id), "contract", "figure id 不合法（只能是字母/数字/_/-）")]
    lp = _rooted(root, lock_rel(figure_id))
    if not lp.is_file():
        return []
    lock = _load(lp)
    if not isinstance(lock, dict):
        return [_issue(figure_id, "contract", "lock 文件不可读")]
    issues: list[dict] = []
    if int(lock.get("schema_version") or 0) != SCHEMA_VERSION:
        issues.append(_issue(figure_id, "contract",
                             f"lock.schema_version={lock.get('schema_version')!r}，期望 {SCHEMA_VERSION}"))
        return issues
    if str(lock.get("figure_id") or "") != figure_id:
        issues.append(_issue(figure_id, "contract",
                             f"lock.figure_id={lock.get('figure_id')!r} 与文件名不一致"))
        return issues

    # 1. bundle
    data = lock.get("data") or {}
    drel = str(data.get("path") or data_rel(figure_id)).replace("\\", "/")
    dpath = _rooted(root, drel)
    bundle_meta = None
    if not dpath.is_file():
        issues.append(_issue(figure_id, "data",
                             f"数据 bundle 不存在：{drel}（④ 未交付或已被移走）"))
    else:
        actual = _sha_file(dpath)
        if actual != data.get("sha256"):
            issues.append(_issue(figure_id, "data",
                                 f"{drel} 的 sha256 与锁不一致（数据层被改动）→ 交回 ④ 重建 bundle 与 lock"))
        else:
            try:
                bundle_meta = _npz_meta(dpath)
            except Exception as exc:       # noqa: BLE001
                issues.append(_issue(figure_id, "data", f"{drel} 不可读：{exc}"))
            if bundle_meta is not None:
                declared = data.get("fields") or {}
                for name, meta in declared.items():
                    if name not in bundle_meta:
                        issues.append(_issue(figure_id, "data",
                                             f"{drel} 缺少锁里登记的字段 {name!r}"))
                        continue
                    if meta.get("shape") is not None and \
                            list(meta["shape"]) != list(bundle_meta[name]["shape"]):
                        issues.append(_issue(
                            figure_id, "data",
                            f"{drel}:{name} 形状 {bundle_meta[name]['shape']} 与锁 {meta['shape']} 不一致"))
                    if meta.get("dtype") and meta["dtype"] != bundle_meta[name]["dtype"]:
                        issues.append(_issue(
                            figure_id, "data",
                            f"{drel}:{name} dtype {bundle_meta[name]['dtype']} 与锁 {meta['dtype']} 不一致"))

    # 2. sources
    for rel, expected in sorted((lock.get("sources") or {}).items()):
        path = _rooted(root, rel)
        if not path.is_file():
            issues.append(_issue(figure_id, "data",
                                 f"source 不存在：{rel}（bundle 所依据的事实已不在盘上）→ 交回 ④"))
        elif _sha_file(path) != expected:
            issues.append(_issue(figure_id, "data",
                                 f"source {rel} 的 sha256 与锁不一致 → 交回 ④ 重建 bundle 与 lock"))

    # 3. spec semantic part
    srel = str((lock.get("spec") or {}).get("path") or spec_rel(figure_id)).replace("\\", "/")
    spath = _rooted(root, srel)
    spec = None
    if not spath.is_file():
        issues.append(_issue(figure_id, "contract",
                             f"spec 不存在：{srel}（④ 未交付或 ⑦ 误删）"))
    else:
        spec = _load(spath)
        if not isinstance(spec, dict):
            issues.append(_issue(figure_id, "contract", f"spec 不可读：{srel}"))
            spec = None
        else:
            digest = semantic_digest(spec)
            if digest != (lock.get("spec") or {}).get("semantic_sha256"):
                issues.append(_issue(
                    figure_id, "contract",
                    "spec 的语义部分（fields/field_mapping/claim/statistics）与锁不一致"
                    " → ⑦ 只能改 recipe/layout/options，要改字段或 claim 请交回 ④"))
            if str(spec.get("claim") or "") != str(lock.get("claim") or ""):
                issues.append(_issue(figure_id, "contract",
                                     "spec.claim 与锁里的 claim 不一致 → 交回 ④ 重建 lock"))
            if str(spec.get("figure_id") or "") != figure_id:
                issues.append(_issue(figure_id, "contract",
                                     f"spec.figure_id={spec.get('figure_id')!r} 与 {figure_id!r} 不一致"))
            for panel in spec.get("panels") or []:
                if not isinstance(panel, dict):
                    continue
                pid = str(panel.get("id") or "")
                locked = (lock.get("panels") or {}).get(pid) or {}
                fields = set(str(x) for x in _as_list(panel.get("fields")))
                locked_fields = set(str(x) for x in (locked.get("fields") or []))
                if locked_fields and fields != locked_fields:
                    issues.append(_issue(
                        figure_id, "contract",
                        f"面板 {pid} 的 fields 与锁不一致：spec={sorted(fields)}，"
                        f"lock={sorted(locked_fields)}"))
                if bundle_meta is not None:
                    missing = sorted(fields - set(bundle_meta))
                    if missing:
                        issues.append(_issue(
                            figure_id, "contract",
                            f"面板 {pid} 引用了 bundle 里不存在的字段 {missing}"))

    # 4. registry + rendered meta, when they exist.  These are **rendering**
    #    products: re-rendering rewrites them, so `check_meta=False` (used by
    #    save_figure/render_specs) deliberately skips this block.
    if check_meta:
        manifest = _load(root / "figures" / "manifest.json", {}) or {}
        entry = ((manifest.get("figures") or {}) if isinstance(manifest, dict) else {}).get(figure_id)
        if isinstance(entry, dict):
            registered_claim = str(entry.get("claim") or "").strip()
            if registered_claim and registered_claim != str(lock.get("claim") or "").strip():
                issues.append(_issue(
                    figure_id, "contract",
                    "manifest.claim 与锁不一致 → ⑦/⑨ 只能改 caption，claim 要回 ④"))
        meta_path = root / "figures" / f"{figure_id}.meta.json"
        if meta_path.is_file():
            meta = _load(meta_path, {})
            if not isinstance(meta, dict):
                issues.append(_issue(figure_id, "contract", "meta 侧车不可读"))
            else:
                if str(meta.get("claim") or "").strip() != str(lock.get("claim") or "").strip():
                    issues.append(_issue(
                        figure_id, "contract",
                        "渲染后的 meta.claim 与锁不一致 → ⑦ 只能改 caption/画法，不能改 claim"))
                for key in ("language", "template"):
                    if meta.get(key) and lock.get(key) and meta[key] != lock[key]:
                        issues.append(_issue(
                            figure_id, "contract",
                            f"meta.{key}={meta.get(key)!r} 与锁 {lock.get(key)!r} 不一致"))
                if str(meta.get("figure_id") or figure_id) != figure_id:
                    issues.append(_issue(figure_id, "contract",
                                         f"meta.figure_id={meta.get('figure_id')!r} 与文件名不一致"))
                for key, expected in (("data", data_rel(figure_id)),
                                      ("spec", spec_rel(figure_id)),
                                      ("figure_lock", lock_rel(figure_id))):
                    if meta.get(key) and str(meta[key]).replace("\\", "/") != expected:
                        issues.append(_issue(
                            figure_id, "contract",
                            f"meta.{key}={meta[key]!r} 与锁登记的 {expected!r} 不一致"))
                allowed = _allowed_numbers(lock)
                caption_numbers = set(numbers(meta.get("caption") or ""))
                extra = sorted(caption_numbers - allowed)
                if extra:
                    issues.append(_issue(
                        figure_id, "advisory",
                        f"caption 里的数字 {extra} 不在 lock 的 claim 数字里；"
                        f"若来自当前结果，请在 claim/图注里写清口径，否则删掉"))

    # 5. brief
    brief = lock.get("brief") or {}
    if brief.get("path"):
        bp = _rooted(root, str(brief["path"]))
        if not bp.is_file():
            issues.append(_issue(figure_id, "contract",
                                 f"FigureBrief 不存在：{brief['path']}"))
        elif _sha_file(bp) != brief.get("sha256"):
            issues.append(_issue(figure_id, "contract",
                                 "FigureBrief 在锁之后被改动 → 交回 ④ 重建 lock"))
    return issues


def _discover(root: Path) -> tuple[list[str], list[str], list[str]]:
    figures = root / "figures"
    if not figures.is_dir():
        return [], [], []
    locks = sorted(p.name[:-len(".lock.json")] for p in figures.glob("*.lock.json")
                   if p.name.endswith(".lock.json"))
    specs = sorted(p.stem for p in (figures / "spec").glob("*.json")) if (figures / "spec").is_dir() else []
    bundles = sorted(p.stem for p in (figures / "data").glob("*.npz")) if (figures / "data").is_dir() else []
    return locks, specs, bundles


def verify(root: str | Path, figure_id: str | None = None, *,
           check_meta: bool = True) -> list[dict]:
    """Verify every lock (or one figure) and flag bundle/spec without a lock.

    Returns a flat list of ``{"figure", "kind", "message"}``.  ``advisory``
    issues are migration notes (legacy figures), not failures.
    """
    root = Path(root)
    issues: list[dict] = []
    if figure_id:
        return verify_one(root, figure_id, check_meta=check_meta)
    locks, specs, bundles = _discover(root)
    for fid in locks:
        issues.extend(verify_one(root, fid, check_meta=check_meta))
    for fid in sorted(set(specs) | set(bundles)):
        if fid not in locks:
            issues.append(_issue(
                fid, "contract",
                f"有 figures/{'spec' if fid in specs else 'data'}/ 产物但没有 figures/{fid}.lock.json"
                "（④ 未交付数据锁；不要手写 lock，运行 studio.save_bundle 或 figure_lock build）"))
    # Legacy figures: rendered/manifested but never cut into a bundle.  Migration
    # note only; the next ④ run must produce the three files.
    meta_ids = sorted(p.name[:-len(".meta.json")] for p in (root / "figures").glob("*.meta.json")
                      if p.name.endswith(".meta.json"))
    for fid in meta_ids:
        if fid not in locks and fid not in specs and fid not in bundles:
            issues.append(_issue(
                fid, "advisory",
                "旧图未接数据契约（没有 figures/data + spec + lock）；下次 ④ 重跑时补 bundle，"
                "迁移期不判失败"))
    return issues


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p_verify = sub.add_parser("verify", help="check locks against bundles/specs/sources")
    p_verify.add_argument("--root", type=Path, default=Path.cwd())
    p_verify.add_argument("--figure", default=None)
    p_verify.add_argument("--json", action="store_true")
    p_build = sub.add_parser("build", help="write a lock from an existing spec/bundle")
    p_build.add_argument("--root", type=Path, default=Path.cwd())
    p_build.add_argument("--figure", required=True)
    p_build.add_argument("--spec", default=None)
    p_build.add_argument("--brief", default=None)
    p_show = sub.add_parser("show", help="print a lock")
    p_show.add_argument("--root", type=Path, default=Path.cwd())
    p_show.add_argument("--figure", required=True)
    args = ap.parse_args()

    if args.cmd == "build":
        lock = build(args.root, args.figure, spec_path=args.spec, brief_path=args.brief)
        print(f"wrote {lock_rel(args.figure)}")
        return 0
    if args.cmd == "show":
        data = _load(args.root / lock_rel(args.figure))
        if data is None:
            print(f"FAIL: 没有 {lock_rel(args.figure)}")
            return 1
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return 0

    issues = verify(args.root, args.figure)
    hard = [i for i in issues if i["kind"] in ("data", "contract")]
    advisories = [i for i in issues if i["kind"] == "advisory"]
    if args.json:
        print(json.dumps({"status": "FAIL" if hard else "PASS",
                          "issues": [format_issue(i) for i in hard],
                          "advisories": [format_issue(i) for i in advisories]},
                         ensure_ascii=False, indent=2))
    else:
        print("FAIL" if hard else "PASS")
        for item in hard:
            print(" -", format_issue(item))
        for item in advisories:
            print(" ~", format_issue(item))
    return 0 if not hard else 1


if __name__ == "__main__":
    raise SystemExit(main())
