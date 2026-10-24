#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Figure-level duplication and line-family budget checks.

Two failures kept slipping past the per-figure checks:

* the same 3D surface was rendered twice — once as the plate hero and again as
  a standalone support chart (``q2_props`` vs ``fig_q2_plate``);
* almost every support figure was a family of line profiles, even when the
  claim was about how a distribution shifts.

This checker is deliberately mechanical: it reads the spec recipes, the
manifest and the plate scripts, not the pixels.  A figure is "line-heavy" when
the majority of its panels use a line-family recipe.  The budget comes from
``config/visualization.json`` -> ``chart_mix.line_budget`` so a problem can
tighten it without editing code.  It also rejects a paper figure whose panels
are *all* field maps — that is the "two contour plots and no distribution"
shape the 2026-10 run kept producing.

Usage:
    python skills/figure-studio/scripts/check_figure_mix.py --root .
    python skills/figure-studio/scripts/check_figure_mix.py --root . --json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

DEFAULT_LINE_RECIPES = {
    "profiles", "profile", "field_waterfall", "field-waterfall",
    "small_multiples", "small-multiples",
    "paired_dumbbell", "paired-dumbbell",
    "roc_curve", "roc-curve", "roc",
}
SURFACE_RECIPES = {
    "surface3d", "surface3d-response", "surface3d_response",
    "trajectory3d", "trajectory-3d", "trajectory_3d",
}
FIELD_RECIPES = {"field_contour", "field-contour", "field_heatmap",
                 "field-heatmap", "field_moving", "field-moving"}
HEATMAP_RECIPES = {"heatmap", "matrix-heatmap", "matrix_heatmap",
                   "composition-heatmap", "composition_heatmap",
                   "annotated-heatmap", "annotated_heatmap",
                   "table-heatmap", "table_heatmap"}
THREE_D_TOKENS = (
    "plot_surface", "surface3d", "Axes3D", "Poly3DCollection",
    'projection="3d"', "projection='3d'", "projection=\"3d\"",
)


def _load(path: Path, default=None):
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return default


def _recipe(panel) -> str:
    return str((panel or {}).get("recipe") or "").strip().lower()


def _plate_bundles(root: Path) -> dict[str, dict]:
    """bundle basename -> {plate, is_3d} for every ``figures/plate_*.py``."""
    found: dict[str, dict] = {}
    for script in sorted((root / "figures").glob("plate_*.py")):
        if script.name == "make_plates.py":
            continue
        text = script.read_text(encoding="utf-8", errors="replace")
        is_3d = any(tok in text for tok in THREE_D_TOKENS)
        for match in re.findall(r'["\']([^"\']+\.npz)["\']', text):
            name = Path(match).name
            found.setdefault(name, {"plate": script.name, "is_3d": is_3d})
            found[name]["is_3d"] = found[name]["is_3d"] or is_3d
    return found


def _matrix_available(root: Path) -> bool:
    """True when at least one bundle has a compact 2D matrix suitable for a heatmap.

    Uses a size guard so a normal space-time field (thousands of time rows)
    does not masquerade as a parameter matrix.  This keeps the annotated-heatmap
    requirement data-driven instead of forcing every problem to invent one.
    """
    try:
        import numpy as np
    except Exception:
        return True
    for path in sorted((root / "figures" / "data").glob("*.npz")):
        try:
            with np.load(path, allow_pickle=True) as data:
                for key in data.files:
                    arr = data[key]
                    if (getattr(arr, "ndim", 0) == 2
                            and 2 <= arr.shape[0] <= 512
                            and 2 <= arr.shape[1] <= 512):
                        return True
        except Exception:
            continue
    return False


def _surface_duplicates(root: Path) -> dict[str, dict]:
    """spec figure id -> plate owner, for surface panels backed by a plate bundle."""
    plates = _plate_bundles(root)
    out: dict[str, dict] = {}
    for spec_path in sorted((root / "figures" / "spec").glob("*.json")):
        spec = _load(spec_path, {}) or {}
        fid = str(spec.get("figure_id") or spec_path.stem)
        panels = [p for p in (spec.get("panels") or []) if isinstance(p, dict)]
        if not any(_recipe(p) in SURFACE_RECIPES for p in panels):
            continue
        bundle = Path(str(((spec.get("data") or {}).get("path")) or "")).name
        owner = plates.get(bundle)
        if owner and owner.get("is_3d"):
            out[fid] = owner
    return out


def duplicate_ids(root: Path) -> list[str]:
    """Figure ids the ⑦ renderer should skip as plate-owned 3D duplicates."""
    return sorted(_surface_duplicates(Path(root).resolve()))


def check(root: Path) -> dict:
    root = root.resolve()
    issues: list[str] = []
    advisories: list[str] = []
    cfg = _load(root / "config" / "visualization.json", {}) or {}
    mix = ((cfg.get("chart_mix") or {}).get("line_budget") or {})
    def _int(key, default):
        try:
            return int(mix.get(key, default))
        except (TypeError, ValueError):
            return default
    max_line = _int("max_line_panels", 6)
    min_line = _int("min_line_panels", 4)
    max_field = _int("max_field_panels", 2)
    max_field_maps = _int("max_field_maps", 1)
    max_heatmaps = _int("max_heatmaps", 1)
    min_annotated_cfg = _int("min_annotated_heatmaps", 1)
    matrix_available = _matrix_available(root)
    min_annotated = min_annotated_cfg if matrix_available else 0
    max_dist = _int("max_distribution_panels", 1)
    max_bar = _int("max_bar_panels", 3)
    try:
        balance_share = float(mix.get("subfamily_balance_share", 0.7))
    except (TypeError, ValueError):
        balance_share = 0.7
    line_recipes = {str(x).strip().lower() for x in
                    (mix.get("line_recipes") or [])} or DEFAULT_LINE_RECIPES

    manifest = _load(root / "figures" / "manifest.json", {}) or {}
    figures = manifest.get("figures", {}) if isinstance(manifest, dict) else {}
    dupes = _surface_duplicates(root)

    # Geometry figures are grouped by model.  If the workspace has included
    # geometry figures, any *other* geometry figure still on disk / in the
    # manifest is a superseded duplicate — no matter what it is called.
    geom_ids = {fid for fid in figures if str(fid).startswith("fig_geometry")}
    included_geom = {fid for fid in geom_ids
                     if bool((figures.get(fid) or {}).get("included", True))}
    disk_geom = {p.stem for p in (root / "figures").glob("fig_geometry*.png")}
    stale_geom = sorted((geom_ids | disk_geom) - included_geom)
    if included_geom and stale_geom:
        issues.append(
            "旧几何图仍在（" + "、".join(stale_geom) + "）：当前已包含 "
            + "、".join(sorted(included_geom))
            + "；删掉旧 PDF/SVG/PNG/scene.json 并从 manifest 移除，"
              "否则同一几何会出现两次")

    total_line = 0
    total_field = 0
    total_field_maps = 0
    total_heatmaps = 0
    total_annotated = 0
    total_dist = 0
    total_bar = 0
    recipe_counts: dict[str, int] = {}
    line_rows: list[tuple[str, int, int]] = []
    field_rows: list[tuple[str, int, int]] = []
    heatmap_rows: list[tuple[str, int, int]] = []
    dist_rows: list[tuple[str, int, int]] = []
    bar_rows: list[tuple[str, int, int]] = []
    for spec_path in sorted((root / "figures" / "spec").glob("*.json")):
        spec = _load(spec_path, {}) or {}
        fid = str(spec.get("figure_id") or spec_path.stem)
        panels = [p for p in (spec.get("panels") or []) if isinstance(p, dict)]
        if not panels:
            continue
        # A plate-owned duplicate is not rendered, so its line panels do not
        # count against the budget; only flag it if it is still registered.
        owner = dupes.get(fid)
        if owner:
            entry = figures.get(fid) if isinstance(figures, dict) else None
            on_disk = any((root / "figures" / f"{fid}{ext}").is_file()
                          for ext in (".png", ".pdf", ".svg"))
            if (entry and (entry.get("artifacts") or [])) or on_disk:
                bundle = Path(str(((spec.get("data") or {}).get("path")) or "")).name
                where = "仍登记在 manifest" if entry else "仍有旧产物"
                issues.append(
                    f"{fid}: 3D 面板与 {owner['plate']} 同源同图型"
                    f"（都读 {bundle}，plate 已画 3D）—— 只保留 plate 的曲面；"
                    f"这张支撑图不要生成/登记，删掉旧 PDF/SVG/PNG（当前{where}）")
            continue
        entry = figures.get(fid) if isinstance(figures, dict) else None
        included = True if entry is None else bool(entry.get("included", True))
        if not included:
            # Excluded support figures still appear on disk, so they count in
            # the visual mix; note it so ⑦ can remove them if not needed.
            if entry and (entry.get("artifacts") or []):
                advisories.append(
                    f"{fid}: manifest 标了 included=false 但仍有产物；"
                    f"它会计入视觉混排预算，不需要就移除，不要只改 included")
        if len(panels) >= 2 and all(_recipe(p) in FIELD_RECIPES for p in panels):
            issues.append(
                f"{fid}: {len(panels)} 个面板全是场图（{', '.join(_recipe(p) for p in panels)}）——"
                f"论文主图至少要有一个分布/比较面板；若 claim 讲前沿推进或分布移动，"
                f"把其中一面改成 field_raincloud（sci-box 半小提琴 + 箱线 + 散点）")
        for p in panels:
            if _recipe(p) not in SURFACE_RECIPES:
                continue
            fields = [str(x) for x in (p.get("fields") or [])]
            if any(("field" in f.lower() or f.lower() in ("t", "r", "time", "radius"))
                   for f in fields):
                issues.append(
                    f"{fid}: surface3d 画的是时空场（fields={fields}），不是两参数响应面——"
                    f"温度/浓度分布改用 field_split_raincloud（sci-box 05 拆半小提琴）"
                    f"或 field_raincloud；surface3d 只留给 C×T→D 这类响应面")
        for p in panels:
            key = _recipe(p)
            recipe_counts[key] = recipe_counts.get(key, 0) + 1
        line_panels = sum(1 for p in panels if _recipe(p) in line_recipes)
        field_panels = sum(1 for p in panels if _recipe(p) in FIELD_RECIPES)
        heatmap_panels = sum(1 for p in panels if _recipe(p) in HEATMAP_RECIPES)
        annotated_panels = sum(
            1 for p in panels
            if _recipe(p) in {"annotated-heatmap", "annotated_heatmap"}
            or (_recipe(p) in HEATMAP_RECIPES
                and bool((p.get("options") or {}).get("annotate"))))
        dist_panels = sum(1 for p in panels
                         if _recipe(p) in {"raincloud", "group_raincloud",
                                           "field_raincloud", "split_raincloud",
                                           "field_split_raincloud",
                                           "distribution_box"})
        bar_panels = sum(1 for p in panels
                         if _recipe(p) in {"sampled_bars", "sampled-bars",
                                           "grouped_bars", "grouped-bars",
                                           "stacked_composition", "stacked-composition",
                                           "ablation_bars", "ablation-bars"})
        for p in panels:
            if _recipe(p) not in {"annotated-heatmap", "annotated_heatmap"}:
                continue
            opts = p.get("options") or {}
            try:
                cells = int(opts.get("max_rows") or 10) * int(opts.get("max_cols") or 8)
            except (TypeError, ValueError):
                cells = 80
            if cells < 40:
                advisories.append(
                    f"{fid}: annotated_heatmap 只有约 {cells} 格（<40）——"
                    f"格子多一点通常更好读，但不是硬要求；在不挤字的前提下可以增加抽样数")
        total_line += line_panels
        total_field += field_panels + heatmap_panels
        total_field_maps += field_panels
        total_heatmaps += heatmap_panels
        total_annotated += annotated_panels
        total_dist += dist_panels
        total_bar += bar_panels
        if line_panels:
            line_rows.append((fid, line_panels, len(panels)))
        if field_panels:
            field_rows.append((fid, field_panels, len(panels)))
        if heatmap_panels:
            heatmap_rows.append((fid, heatmap_panels, len(panels)))
        if dist_panels:
            dist_rows.append((fid, dist_panels, len(panels)))
        if bar_panels:
            bar_rows.append((fid, bar_panels, len(panels)))

    if total_line > max_line:
        detail = "; ".join(f"{fid} {n}/{total} 个面板" for fid, n, total in line_rows)
        issues.append(
            f"折线面板共 {total_line} 个，超过预算 {max_line} 个（{detail}）——"
            f"把纯时间序列改成 sampled_bars/grouped_bars/dot_interval，把场分布改成 "
            f"field_raincloud/raincloud；折线只留真正需要连续轨迹的一两张")
    elif total_line == max_line and total_line:
        advisories.append(
            f"折线面板已到预算上限 {max_line} 个；新增图不要再选 profiles/field_waterfall")
    if total_line < min_line:
        detail = "; ".join(f"{fid} {n}/{total}" for fid, n, total in line_rows) or "0 个"
        issues.append(
            f"折线面板只有 {total_line} 个（{detail}），低于下限 {min_line} 个——"
            f"不是“全都不要折线”：连续剖面、历史序列、需要读斜率/交点/谷值的"
            f"应保留 profiles / field_waterfall；收敛/离散网格用点图，不要硬折线。"
            f"把被压成柱/雨云/热力图的其中几张改回折线剖面")
    if total_field_maps > max_field_maps:
        detail = "; ".join(f"{fid} {n}/{total}" for fid, n, total in field_rows)
        issues.append(
            f"场图面板 {total_field_maps} 个，超过 {max_field_maps} 个（{detail}）——"
            f"场图/热力图总预算 {max_field} 要平均分配：留 1 张场图，"
            f"另一张改成带数字的矩阵热力图")
    if total_heatmaps > max_heatmaps:
        detail = "; ".join(f"{fid} {n}/{total}" for fid, n, total in heatmap_rows)
        issues.append(
            f"矩阵热力图 {total_heatmaps} 个，超过 {max_heatmaps} 个（{detail}）——"
            f"场图/热力图总预算 {max_field}：1 张场图 + 1 张带数字的热力图，"
            f"不要两张都做成场图或都做成热力图")
    if total_annotated < min_annotated:
        issues.append(
            f"带数字标注的矩阵热力图只有 {total_annotated} 张，少于要求的 "
            f"{min_annotated} 张——加一张 `heatmap` 且 options.annotate=true 的图，"
            f"格子里写数值（如参数×情景、C×T 的粗网格），不要只画色块")
    if total_field > max_field:
        detail = "; ".join(f"{fid} {n}/{total}" for fid, n, total in field_rows + heatmap_rows)
        issues.append(
            f"场图+热力图共 {total_field} 个，超过预算 {max_field} 个（{detail}）——"
            f"两张要平均分配：1 张场图 + 1 张带数字的热力图；其余改折线/点/柱")
    if total_dist > max_dist:
        detail = "; ".join(f"{fid} {n}/{total}" for fid, n, total in dist_rows)
        issues.append(
            f"雨云/分布面板 {total_dist} 个，超过预算 {max_dist} 个（{detail}）——"
            f"雨云只用在“分布形状是 claim”的图；其余改回折线剖面或场图/点图，"
            f"不要把每张都做成温度分布")
    if total_bar > max_bar:
        detail = "; ".join(f"{fid} {n}/{total}" for fid, n, total in bar_rows)
        issues.append(
            f"柱/抽样柱面板 {total_bar} 个，超过预算 {max_bar} 个（{detail}）——"
            f"连续时间序列优先折线（能读斜率/谷值/交点）；柱状只用于离散类别，"
            f"不要把连续量按几个时刻切成柱子")

    # Soft sub-family balance: don't let one subtype eat the whole family
    # budget when the data could support another; if it cannot, this is only
    # an advisory, not a reason to invent a chart.
    families = {
        "折线": ("profiles", "field_waterfall", "small_multiples"),
        "柱": ("sampled_bars", "grouped_bars", "stacked_composition"),
        "分布": ("raincloud", "field_raincloud", "split_raincloud",
                 "field_split_raincloud", "distribution_box"),
    }
    for fam, subtypes in families.items():
        counts = {k: recipe_counts.get(k, 0) for k in subtypes}
        total = sum(counts.values())
        if total < 2:
            continue
        top, n = max(counts.items(), key=lambda kv: kv[1])
        if n / total > balance_share:
            advisories.append(
                f"{fam}类里 `{top}` 占 {n}/{total} 个面板（>{balance_share:.0%}）——"
                f"如果数据支持别的子类，换一张均分一下；数据不支持这种图就不用硬换")

    return {"status": "FAIL" if issues else "PASS", "issues": issues,
            "advisories": advisories,
            "line_panels": total_line, "max_line_panels": max_line,
            "min_line_panels": min_line,
            "field_panels": total_field, "max_field_panels": max_field,
            "field_map_panels": total_field_maps,
            "max_field_maps": max_field_maps,
            "heatmap_panels": total_heatmaps,
            "max_heatmaps": max_heatmaps,
            "annotated_heatmaps": total_annotated,
            "min_annotated_heatmaps": min_annotated,
            "matrix_available": matrix_available,
            "distribution_panels": total_dist,
            "max_distribution_panels": max_dist,
            "bar_panels": total_bar, "max_bar_panels": max_bar,
            "line_figures": line_rows, "field_figures": field_rows,
            "heatmap_figures": heatmap_rows,
            "distribution_figures": dist_rows, "bar_figures": bar_rows}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", type=Path, default=Path.cwd())
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    try:
        result = check(args.root)
    except Exception as exc:                 # keep --json parseable
        result = {"status": "FAIL", "issues": [f"check_figure_mix 运行失败：{exc}"],
                  "advisories": []}
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
