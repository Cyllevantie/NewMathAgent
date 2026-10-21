#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Resolve the figure context: template language, canvas width, font, labels.

The figure text language follows the paper template, not the author's chat
language.  For ``zh/cumcm-latex`` every explanatory label is Chinese; method
names such as TPE, SHAP and AUC may stay in Latin script.

Usage (from the project root):
    python skills/figure-studio/scripts/resolve_context.py --write
    python skills/figure-studio/scripts/resolve_context.py --json
"""
from __future__ import annotations

import argparse
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
TOKENS_PATH = SKILL_ROOT / "assets" / "style.tokens.json"


def _read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None


def _cjk_ratio(text: str) -> float:
    if not text:
        return 0.0
    cjk = len(re.findall(r"[一-鿿]", text))
    return cjk / max(1, len(text))


def _template_from_project(root: Path) -> tuple[str | None, str]:
    """Return (template, reason) from the project's own declarations."""
    for rel, key in (("config/delivery.local.json", "template"),
                     ("paper/structure.json", "template")):
        data = _read_json(root / rel)
        if isinstance(data, dict) and data.get(key):
            return str(data[key]), f"{rel}:{key}"

    tpl_root = root / "skills" / "9Paper-writing" / "templates"
    mains = sorted(tpl_root.glob("*/*/roles.json"))
    if len(mains) == 1:
        return mains[0].parent.relative_to(tpl_root).as_posix(), "single template family"

    # Last resort: inspect the compiled paper source.  This is deliberately
    # conservative: only used when no config/template declaration exists.
    for rel in ("paper/main.tex", "paper/paper-structure.tex"):
        p = root / rel
        if p.is_file():
            text = p.read_text(encoding="utf-8", errors="replace")[:4000]
            if _cjk_ratio(text) >= 0.03:
                return "zh/unknown", f"{rel}: CJK text"
            return "en/unknown", f"{rel}: no CJK text"
    return None, "no template declaration found"


def _font_available(name: str) -> bool:
    try:
        from matplotlib import font_manager
        font_manager.findfont(
            font_manager.FontProperties(family=name), fallback_to_default=False
        )
        return True
    except Exception:
        return False


def _choose_font(candidates: list[str]) -> str:
    for name in candidates:
        if _font_available(name):
            return name
    return "DejaVu Sans"


def resolve(root: Path, template: str | None = None, width_mm: float | None = None) -> dict:
    root = Path(root).resolve()
    tokens = _read_json(TOKENS_PATH) or {}
    reason = "explicit --template" if template else ""
    if not template:
        template, reason = _template_from_project(root)
    if not template:
        # A safe default for this repository: CUMCM Chinese.
        template, reason = "zh/cumcm-latex", "default (no declaration found)"

    first = template.split("/", 1)[0].strip().lower()
    if first in {"zh", "en"}:
        language = first
    else:
        low = template.lower()
        language = "zh" if ("cumcm" in low or "zh" in low or _cjk_ratio(template) > 0) else "en"

    typo = (tokens.get("typography") or {}).get(language, {})
    canvas = (tokens.get("canvas") or {}).get(language, {})
    labels_path = SKILL_ROOT / "assets" / f"labels.{language}.json"
    fonts = [typo.get("font", "Microsoft YaHei" if language == "zh" else "Arial")]
    fonts += list(typo.get("fallback") or [])
    font = _choose_font(fonts)

    resolved_width = float(width_mm or canvas.get("width_mm", 160 if language == "zh" else 183))
    labels = _read_json(labels_path) or {}
    return {
        "schema_version": 1,
        "root": str(root),
        "template": template,
        "template_reason": reason,
        "language": language,
        "language_label": "中文" if language == "zh" else "English",
        "width_mm": resolved_width,
        "half_width_mm": float(canvas.get("half_width_mm", resolved_width / 2)),
        "height_mm": float(canvas.get("height_mm", 100 if language == "zh" else 110)),
        "dpi": int(canvas.get("dpi", 300)),
        "font": font,
        "font_candidates": fonts,
        "labels_path": str(labels_path),
        "labels": labels,
        "tokens_path": str(TOKENS_PATH),
        "tokens": tokens,
        "rule": "图内解释性文字用中文；方法名/模型名/软件名可保留英文；图注在 LaTeX 中写。"
        if language == "zh"
        else "Use English explanatory text; keep method and unit symbols unchanged.",
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", type=Path, default=Path.cwd())
    ap.add_argument("--template", default=None)
    ap.add_argument("--width", type=float, default=None, help="override final width in mm")
    ap.add_argument("--json", action="store_true", help="print the full context (default: summary)")
    ap.add_argument("--write", action="store_true", help="write reports/FIGURE_CONTEXT.json")
    args = ap.parse_args()

    ctx = resolve(args.root, args.template, args.width)
    if args.write:
        out = Path(args.root).resolve() / "reports" / "FIGURE_CONTEXT.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(ctx, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"wrote {out}")
    if args.json:
        print(json.dumps(ctx, ensure_ascii=False, indent=2))
    else:
        print(json.dumps({
            "template": ctx["template"],
            "template_reason": ctx["template_reason"],
            "language": ctx["language"],
            "width_mm": ctx["width_mm"],
            "font": ctx["font"],
            "labels_path": ctx["labels_path"],
            "rule": ctx["rule"],
        }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
