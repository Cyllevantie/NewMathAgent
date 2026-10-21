#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Validate a FigureBrief and its recipe ids before any plotting code is written.

Usage:
    python skills/figure-studio/scripts/check_brief.py reports/FIGURE_BRIEF.json
    python skills/figure-studio/scripts/check_brief.py reports/FIGURE_BRIEF.json --context reports/FIGURE_CONTEXT.json
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
SCHEMA = SKILL_ROOT / "assets" / "figure-brief.schema.json"
RECIPES = SKILL_ROOT / "assets" / "recipes.json"


def _type_ok(value, expected: str) -> bool:
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "boolean":
        return isinstance(value, bool)
    return True


def validate(value, schema, path="$", errors=None):
    errors = errors if errors is not None else []
    if not isinstance(schema, dict):
        return errors
    expected = schema.get("type")
    if expected and not _type_ok(value, expected):
        errors.append(f"{path}: expected {expected}, got {type(value).__name__}")
        return errors
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path}: {value!r} not in {schema['enum']}")
    if isinstance(value, str):
        if "minLength" in schema and len(value.strip()) < schema["minLength"]:
            errors.append(f"{path}: shorter than {schema['minLength']} characters")
        if "pattern" in schema and not re.fullmatch(schema["pattern"], value):
            errors.append(f"{path}: does not match {schema['pattern']}")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            errors.append(f"{path}: below minimum {schema['minimum']}")
        if "maximum" in schema and value > schema["maximum"]:
            errors.append(f"{path}: above maximum {schema['maximum']}")
    if isinstance(value, list):
        if "minItems" in schema and len(value) < schema["minItems"]:
            errors.append(f"{path}: needs at least {schema['minItems']} item(s)")
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for i, item in enumerate(value):
                validate(item, item_schema, f"{path}[{i}]", errors)
    if isinstance(value, dict):
        for key in schema.get("required", []):
            if key not in value:
                errors.append(f"{path}: missing required key {key!r}")
        props = schema.get("properties") or {}
        for key, sub in props.items():
            if key in value:
                validate(value[key], sub, f"{path}.{key}", errors)
        additional = schema.get("additionalProperties")
        if isinstance(additional, dict):
            for key, sub in value.items():
                if key not in props:
                    validate(sub, additional, f"{path}.{key}", errors)
    return errors


def semantic_checks(brief: dict, recipes: dict, context: dict | None = None) -> list[str]:
    errors: list[str] = []
    ids = {r["id"] for r in recipes.get("recipes", [])}
    aliases = recipes.get("aliases") or {}
    by_id = {r["id"]: r for r in recipes.get("recipes", [])}
    panels = [p for p in brief.get("panels", []) if isinstance(p, dict)]
    panel_ids = [p.get("id") for p in panels]
    if len(panel_ids) != len(set(panel_ids)):
        errors.append("panels: duplicate panel ids")
    for i, panel in enumerate(panels):
        rid = panel.get("recipe")
        if rid not in ids and rid not in aliases:
            errors.append(f"panels[{i}].recipe: unknown recipe {rid!r}; see assets/recipes.json")
        elif rid in aliases and aliases[rid] not in ids:
            errors.append(f"panels[{i}].recipe: alias {rid!r} points to missing {aliases[rid]!r}")
        # An exact recipe id wins over an alias with the same spelling.  Some
        # catalog entries (e.g. split-violin-corr-matrix) are both an id and an
        # alias for a simpler recipe; preferring the alias would validate the
        # wrong required_fields.
        target = rid if rid in ids else aliases.get(rid, rid)
        spec = by_id.get(target) or {}
        required = spec.get("required_fields") or []
        mapping = panel.get("field_mapping") or {}
        # `level` / `series_labels` / `reference` can live in options (presentation),
        # while `x`/`y`/`z`/`series` are data references in field_mapping.
        declared = set(mapping) | set(panel.get("options") or {})
        missing = [f for f in required if f not in declared]
        if missing:
            errors.append(
                f"panels[{i}].field_mapping/options: missing required fields {missing} for recipe {rid!r}")
        if panel.get("role") == "hero" and i != 0:
            errors.append(f"panels[{i}]: hero panel must be the first panel")
    if panel_ids and panel_ids[0] not in {"a", "A"}:
        errors.append("panels: first panel id should be 'a'")

    stats = brief.get("statistics") or {}
    interval = stats.get("interval") or {}
    if interval.get("kind") != "none" and not interval.get("method"):
        errors.append("statistics.interval.method: required when an interval is shown")
    if stats.get("test", {}).get("p_values"):
        if stats.get("test", {}).get("kind") == "none":
            errors.append("statistics.test: p_values=true but kind='none'")
    if stats.get("paired") and not any("pair" in str(d.get("role", "")) for d in brief.get("data", [])):
        # Not fatal: the data role vocabulary is small.  Warn only.
        pass

    if context:
        if brief.get("language") != context.get("language"):
            errors.append(
                f"language: brief={brief.get('language')!r} but template context={context.get('language')!r}"
            )
        allowed_widths = [float(context.get("width_mm", 0))]
        if context.get("half_width_mm"):
            allowed_widths.append(float(context["half_width_mm"]))
        try:
            brief_width = float(brief.get("width_mm", 0))
        except (TypeError, ValueError):
            brief_width = None
        if brief_width is None or not any(abs(brief_width - w) <= 0.5 for w in allowed_widths):
            errors.append(
                f"width_mm: brief={brief.get('width_mm')} but template context allows {allowed_widths}"
            )
        if brief.get("template") and brief.get("template") != context.get("template"):
            errors.append(
                f"template: brief={brief.get('template')!r} but context={context.get('template')!r}"
            )
    return errors


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("brief", type=Path)
    ap.add_argument("--context", type=Path, default=None)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    try:
        brief = json.loads(args.brief.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        print(f"FAIL: cannot read brief: {exc}")
        return 2
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    recipes = json.loads(RECIPES.read_text(encoding="utf-8"))
    context = None
    if args.context:
        context = json.loads(args.context.read_text(encoding="utf-8-sig"))

    errors = validate(brief, schema)
    errors += semantic_checks(brief, recipes, context)
    result = {"status": "FAIL" if errors else "PASS", "brief": str(args.brief), "errors": errors}
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(result["status"])
        for error in errors:
            print(" -", error)
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
