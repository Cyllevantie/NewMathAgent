#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Static checks that the project's ``visualization audit`` cannot see.

It checks the *method* layer: template language, FigureBrief, per-panel source
data, meta sidecars, and a few script-level anti-patterns (rainbow colormaps,
hard-coded rcParams, tight bbox on registered figures).  It never redraws and
never signs a visual review.

Usage:
    python skills/figure-studio/scripts/audit_studio.py --root .
    python skills/figure-studio/scripts/audit_studio.py --root . --json
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SKILL_ROOT = Path(__file__).resolve().parents[1]
if str(SKILL_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(SKILL_ROOT / "scripts"))

import resolve_context  # noqa: E402
try:
    import figure_lock  # noqa: E402
except Exception as _lock_exc:           # pragma: no cover - NumPy missing
    figure_lock = None
    _LOCK_IMPORT_ERROR = str(_lock_exc)
else:
    _LOCK_IMPORT_ERROR = ""

BAD_CMAPS = re.compile(
    r"(cmap\s*=\s*['\"](jet|rainbow|hsv|gist_rainbow)|plt\.cm\.(jet|rainbow|hsv|gist_rainbow))",
    re.I,
)
INTERNAL_NAMES = re.compile(r"(result[1-4]\.xlsx|2026A|figdata_sens|result3\b|result4\b)")
CJK = re.compile(r"[一-鿿]")
LATIN_WORD = re.compile(r"[A-Za-z]{3,}")


def _load(path: Path, default=None):
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return default


def _row_count(path: Path) -> int:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return max(0, sum(1 for _ in csv.reader(fh)) - 1)


def _long_latin(text: str) -> bool:
    # Three or more Latin words in a row, ignoring canonical tokens.
    words = LATIN_WORD.findall(text or "")
    canonical = {"RMSE", "MAPE", "AUC", "ROC", "SHAP", "TPE", "LSTM", "CNN", "PDF", "SVG", "PNG"}
    words = [w for w in words if w.upper() not in canonical]
    return len(words) >= 3


def check(root: Path) -> dict:
    root = root.resolve()
    issues: list[str] = []
    advisories: list[str] = []

    ctx_path = root / "reports" / "FIGURE_CONTEXT.json"
    ctx = _load(ctx_path)
    if not ctx:
        ctx = resolve_context.resolve(root)
        advisories.append("reports/FIGURE_CONTEXT.json 不存在；使用即时解析结果（建议先 --write）")

    manifest_path = root / "figures" / "manifest.json"
    manifest = _load(manifest_path)
    if manifest is None:
        if manifest_path.exists():
            issues.append("figures/manifest.json 存在但不可读；不要静默当成零图")
        manifest = {"figures": {}}
    figures = manifest.get("figures", {}) if isinstance(manifest, dict) else {}
    if not figures:
        advisories.append("figures/manifest.json 没有登记图；如果是零图场景，在报告里写不适用依据")

    for fid, entry in sorted(figures.items()):
        if not entry.get("included", True):
            continue
        meta_path = root / "figures" / f"{fid}.meta.json"
        meta = _load(meta_path)
        script0 = str(entry.get("script") or "")
        uses_studio = ("studio" in script0.lower()
                       or any("figure-studio" in str(s) for s in (entry.get("sources") or [])))
        if not meta:
            if uses_studio:
                issues.append(f"{fid}: 缺 figures/{fid}.meta.json（language/width/counts/intervals/exclusions）")
            else:
                advisories.append(f"{fid}: 旧图未接 figure-studio；下次重渲时补 meta 侧车（迁移期只提示）")
        else:
            if meta.get("language") != ctx.get("language"):
                issues.append(f"{fid}: meta.language={meta.get('language')!r} 与模板 {ctx.get('language')!r} 不一致")
            allowed_widths = [float(ctx.get("width_mm", 0))]
            if ctx.get("half_width_mm"):
                allowed_widths.append(float(ctx["half_width_mm"]))
            if not any(abs(float(meta.get("width_mm", 0)) - w) <= 0.5 for w in allowed_widths):
                issues.append(
                    f"{fid}: meta.width_mm={meta.get('width_mm')} 不是模板允许的宽度 {allowed_widths}"
                )
            actual = entry.get("width_mm")
            if actual is not None and abs(float(meta.get("width_mm", 0)) - float(actual)) > 0.5:
                issues.append(f"{fid}: meta.width_mm={meta.get('width_mm')} 与 manifest {actual} 不一致")
            if meta.get("font") and ctx.get("font") and meta["font"] != ctx["font"]:
                advisories.append(f"{fid}: meta.font={meta['font']!r}，模板字体={ctx['font']!r}")
            for key in ("counts", "intervals", "exclusions"):
                if key not in meta:
                    issues.append(f"{fid}: meta 缺 {key}（写清观测数/区间定义/排除规则）")
            text = " ".join(str(meta.get(k, "")) for k in ("claim", "caption"))
            if INTERNAL_NAMES.search(text):
                issues.append(f"{fid}: claim/caption 里出现内部文件名或试算代号：{INTERNAL_NAMES.search(text).group(0)}")
            if ctx.get("language") == "zh" and not CJK.search(text):
                advisories.append(f"{fid}: 中文模板但 claim/caption 没有中文")
            if ctx.get("language") == "zh" and _long_latin(text):
                advisories.append(f"{fid}: 中文模板的 claim/caption 含较长英文短语，确认是否为方法名")
            if ctx.get("language") == "en" and CJK.search(text):
                issues.append(f"{fid}: 英文模板的 claim/caption 出现中文")

            source_data = meta.get("source_data") or {}
            if not source_data:
                (issues if uses_studio else advisories).append(
                    f"{fid}: meta.source_data 为空；studio 图必须有逐面板 CSV"
                )
            for panel, rel in source_data.items():
                p = root / rel
                if not p.is_file():
                    issues.append(f"{fid}/{panel}: source_data 不存在：{rel}")
                    continue
                try:
                    n = _row_count(p)
                except Exception as exc:
                    issues.append(f"{fid}/{panel}: source_data 读不了：{exc}")
                    continue
                if n < 1:
                    issues.append(f"{fid}/{panel}: source_data 没有数据行")
                declared = None
                if isinstance(meta.get("counts"), dict):
                    declared = meta["counts"].get(panel) or meta["counts"].get(f"{panel}_rows")
                if declared is None:
                    if uses_studio:
                        advisories.append(f"{fid}/{panel}: counts 未按 panel id 记录（建议 counts.{{'{panel}': n}}）")
                elif isinstance(declared, int) and declared != n:
                    (issues if uses_studio else advisories).append(
                        f"{fid}/{panel}: CSV {n} 行，meta 声明 {declared} 行"
                    )

        script = entry.get("script")
        if script:
            sp = root / script
            if not sp.is_file():
                issues.append(f"{fid}: script 不存在：{script}")
            elif sp.suffix.lower() in {".py", ".m"}:
                text = sp.read_text(encoding="utf-8", errors="replace")
                if BAD_CMAPS.search(text):
                    issues.append(f"{fid}: 脚本出现 jet/rainbow/hsv；连续量请按 quantity 取色阶")
                if "studio.style" not in text and "charts.style" not in text:
                    advisories.append(f"{fid}: 脚本未使用 studio.style/charts.style，确认字体/字号/配色是否统一")
                if "bbox_inches" in text and "tight" in text:
                    advisories.append(f"{fid}: 脚本用了 tight bbox；交付图宽度应以物理尺寸为准（预览图可例外）")
                # Only flag names that sit on a text-rendering line.  A path in
                # ``sources=[...]`` is provenance, not reader-facing text.
                text_calls = re.compile(r"(fig\.text|ax\.text|ax\.annotate|set_title|set_xlabel|set_ylabel|label\s*=)")
                for line in text.splitlines():
                    if INTERNAL_NAMES.search(line) and text_calls.search(line):
                        advisories.append(f"{fid}: 脚本的图内文字行出现内部文件名/试算代号：{line.strip()[:80]}")
                        break

        for src in entry.get("sources") or []:
            p = root / src
            if not p.exists():
                issues.append(f"{fid}: source 不存在：{src}")

    # Data-layer lock (④ -> ⑦ contract).  Only figures that have a bundle
    # and/or a spec are mandatory; legacy figures get an advisory so a
    # half-migrated workspace does not turn every gate red.
    if figure_lock is None:
        advisories.append(f"figure_lock 不可用（{_LOCK_IMPORT_ERROR}）；跳过数据层锁检查")
    elif (root / "figures").is_dir():
        try:
            for item in figure_lock.verify(root):
                text = figure_lock.format_issue(item)
                if item.get("kind") == "advisory":
                    advisories.append(text)
                else:
                    issues.append(text)
        except Exception as exc:         # noqa: BLE001 - audit must not crash
            issues.append(f"figure lock 检查失败：{exc}")

    # FigureBrief validation, when present
    briefs = []
    one = root / "reports" / "FIGURE_BRIEF.json"
    if one.is_file():
        briefs.append(one)
    briefs += sorted((root / "reports" / "figure_briefs").glob("*.json")) if (root / "reports" / "figure_briefs").is_dir() else []
    if figures and not briefs:
        advisories.append(
            "有已登记图但没有 FigureBrief；主图应先写 reports/FIGURE_BRIEF.json 或 reports/figure_briefs/<id>.json"
        )
    if briefs:
        import check_brief
        schema = _load(SKILL_ROOT / "assets" / "figure-brief.schema.json")
        recipes = _load(SKILL_ROOT / "assets" / "recipes.json")
        for bp in briefs:
            brief = _load(bp)
            if not brief:
                issues.append(f"{bp}: 不可读")
                continue
            errs = check_brief.validate(brief, schema)
            errs += check_brief.semantic_checks(brief, recipes, ctx)
            for e in errs:
                issues.append(f"{bp.name}: {e}")

    return {"status": "FAIL" if issues else "PASS", "issues": issues, "advisories": advisories,
            "context": {"template": ctx.get("template"), "language": ctx.get("language"),
                        "width_mm": ctx.get("width_mm"), "font": ctx.get("font")}}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", type=Path, default=Path.cwd())
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    result = check(args.root)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(result["status"])
        for x in result["issues"]:
            print(" -", x)
        for x in result["advisories"]:
            print(" ~", x)
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
