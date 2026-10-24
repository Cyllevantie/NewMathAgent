#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Check the ④→⑦ figure-selection record.

Each main figure has a per-figure FigureBrief (candidates) and a ⑦ choice sidecar
(figures/choice/<id>.json).  This checker catches the old failure mode where the
agent rendered one default recipe and called it "selected":

  * fewer than the configured number of candidates (default 2);
  * all candidates use the same recipe family (a colour/layout change is not a
    different visual encoding);
  * the selected recipe is not one of the candidates;
  * a strict run also requires the candidate PNGs to exist under tmp/figures/.

Usage:
    python skills/figure-studio/scripts/check_selection.py --root .
    python skills/figure-studio/scripts/check_selection.py --root . --strict
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

FAMILY = {
    "field_heatmap": "field", "field_contour": "field", "field_moving": "field",
    "profiles": "profiles", "small_multiples": "profiles",
    "convergence": "convergence",
    "sensitivity_dot": "interval", "dot_interval": "interval",
    "grouped_bars": "bars", "ablation_bars": "bars", "sampled_bars": "bars",
    "surface3d": "surface", "surface3d-response": "surface",
    "trajectory": "trajectory",
    "raincloud": "distribution", "group_raincloud": "distribution",
    "field_raincloud": "distribution",
    "split_raincloud": "distribution", "field_split_raincloud": "distribution",
    "stacked_composition": "composition",
    "field_waterfall": "profiles",
}


def _read(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None


def _family(recipe: str) -> str:
    return FAMILY.get(str(recipe or "").strip().lower(), str(recipe or ""))


def _min_candidates(root: Path) -> int:
    cfg = _read(root / "config" / "visualization.json") or {}
    selection = ((cfg.get("chart_mix") or {}).get("selection") or {})
    try:
        return max(2, int(selection.get("min_candidates_per_figure") or 2))
    except (TypeError, ValueError):
        return 2


def check(root: Path, strict: bool = False) -> list[str]:
    problems: list[str] = []
    briefs = root / "reports" / "figure_briefs"
    specs = root / "figures" / "spec"
    choices = root / "figures" / "choice"
    minimum = _min_candidates(root)
    ids = sorted(p.stem for p in specs.glob("*.json"))
    for fid in ids:
        brief = _read(briefs / f"{fid}.json") or {}
        spec = _read(specs / f"{fid}.json") or {}
        choice = _read(choices / f"{fid}.json") or {}
        candidates = [c for c in (brief.get("candidates") or []) if isinstance(c, dict)]
        recipes = [str(c.get("recipe") or "") for c in candidates]
        recipes = [r for r in recipes if r]
        # ⑦ may add a recipe that ④'s brief did not foresee (the data contract
        # allows it; only fields/claim/statistics are locked).  Those rendered
        # candidates live in the choice sidecar, so the record has to accept
        # them instead of judging the selection only against the brief.
        choice_candidates = [c for c in (choice.get("candidates") or [])
                             if isinstance(c, dict)]
        choice_recipes = [str(c.get("recipe") or "") for c in choice_candidates]
        choice_recipes = [r for r in choice_recipes if r]
        all_recipes = list(dict.fromkeys(recipes + choice_recipes))
        if len(recipes) < minimum:
            if len(recipes) == 0:
                problems.append(f"{fid}: brief 没有候选 recipe")
            else:
                problems.append(
                    f"{fid}: 只有 {len(recipes)} 个候选 recipe；至少给 "
                    f"{minimum} 个不同视觉编码")
        fams = {_family(r) for r in all_recipes}
        if len(fams) < 2 and len(all_recipes) >= 2:
            problems.append(f"{fid}: 候选 recipe 全在同一视觉编码家族 {sorted(fams)}；换配色/排版不算候选")
        selected = str(choice.get("selected") or "")
        # A line-family winner must have at least one non-line alternative in
        # the record.  Otherwise "candidate" was only a second line chart, and
        # a whole run drifts into line charts without anyone choosing them.
        if _family(selected) in ("profiles", "convergence", "trajectory"):
            non_line = fams - {"profiles", "convergence", "trajectory"}
            if not non_line:
                problems.append(
                    f"{fid}: 选中的是折线族，但候选里没有非折线编码；"
                    f"至少补一个 raincloud/field_raincloud/grouped_bars/dot_interval 候选并实际渲染")
        if not selected:
            problems.append(f"{fid}: 缺 figures/choice/{fid}.json 或 selected 字段")
        elif all_recipes and selected not in all_recipes:
            problems.append(f"{fid}: selected={selected!r} 不在候选 {all_recipes}")
        if strict:
            for i, cand in enumerate(candidates, 1):
                p = root / "tmp" / "figures" / fid / f"cand_{i}.png"
                if not p.is_file():
                    problems.append(f"{fid}: strict 模式缺候选渲染图 {p.relative_to(root)}")
    return problems


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", type=Path, default=Path.cwd())
    ap.add_argument("--strict", action="store_true")
    args = ap.parse_args(argv)
    problems = check(args.root.resolve(), strict=args.strict)
    print(json.dumps({"status": "FAIL" if problems else "PASS",
                      "issues": problems}, ensure_ascii=False, indent=2))
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
