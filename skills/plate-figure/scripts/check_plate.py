#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Require every ``figures/plate_*.py`` to have a registered, reviewed plate.

The ⑦ stage may not silently skip the Nature-style main figures just because
the small ``figure-studio`` charts still render.  Each plate generator is
``figures/plate_<id>.py`` and its registered figure id is
``fig_<id>_plate`` (e.g. ``plate_q3.py`` -> ``fig_q3_plate``).

Usage:
    python skills/plate-figure/scripts/check_plate.py --root .
    python skills/plate-figure/scripts/check_plate.py --root . --json
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def _load(path: Path, default=None):
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return default


BANNED_TEXT = ("Panel a", "Panels a", "Panel b", "Panel c",
               "(a)", "(b)", "(c)", "(d)",
               "Note:", "Appendix-", "RESULTS ·")


def _pdf_text(path: Path) -> str:
    try:
        import pymupdf as fitz  # PyMuPDF >= 1.24
    except Exception:
        try:
            import fitz  # older PyMuPDF
        except Exception:
            return ""
    try:
        with fitz.open(str(path)) as doc:
            return "".join(page.get_text() for page in doc)
    except Exception:
        return ""


KPI_MIN_TILE_MM = 17.0
KPI_MAX_TILE_MM = 40.0


def _kpi_layout_issues(source: str, name: str) -> list[str]:
    """Catch a multi-row KPI block that would fit on one row.

    The helper itself expands blocks that fit (``plate_common.kpi_block``),
    but a copied script can still pass a narrow ``cols`` and then hand-place
    tiles around it.  The check is deliberately geometric, not stylistic:
    a block at least ``n × 17 mm`` wide must put all n tiles in one row.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    problems: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        fname = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", "")
        if fname != "kpi_block" or len(node.args) < 6:
            continue
        try:
            width = float(ast.literal_eval(node.args[3]))
            tiles = node.args[5]
            n = len(tiles.elts) if isinstance(tiles, ast.List) else 0
        except (ValueError, TypeError, SyntaxError):
            continue
        cols_node = None
        for kw in node.keywords:
            if kw.arg == "cols":
                cols_node = kw.value
                break
        try:
            cols = int(ast.literal_eval(cols_node)) if cols_node is not None else None
        except (ValueError, TypeError, SyntaxError):
            cols = None
        if n and cols is not None and cols < n and width / n >= KPI_MIN_TILE_MM:
            problems.append(
                f"{name}: KPI {n} 项在 {width:g} mm 宽块里仍用 cols={cols}；"
                f"横向放得下就必须排成一行（≥{KPI_MIN_TILE_MM:g} mm/项），"
                f"不要 2×2 宫格")
        if n and cols == n and width / n > KPI_MAX_TILE_MM:
            problems.append(
                f"{name}: KPI 一行跨度过大（{width / n:.0f} mm/项 > "
                f"{KPI_MAX_TILE_MM:g} mm/项）—— 保持 Q1 那种紧凑间距，"
                f"值排在一起，不要把四个数拉到整张图宽")
    return problems


def _figure_context(root: Path) -> dict:
    # The resolved context is authoritative; config is only a fallback for a
    # workspace where ④/⑦ has not written reports/FIGURE_CONTEXT.json yet.
    data = _load(root / "reports" / "FIGURE_CONTEXT.json", {}) or {}
    if data:
        return data
    return _load(root / "config" / "visualization.json", {}) or {}


def _language(root: Path) -> str:
    return str(_figure_context(root).get("language") or "zh").strip().lower()


def _kpi_placement_issues(source: str, name: str) -> list[str]:
    """Require a wide KPI block to sit just under a panel caption.

    The stage kept rewriting ``figures/plate_q4.py`` back to a bottom KPI block;
    the width check alone cannot see that.  ``caption_below`` and ``kpi_block``
    coordinates are literal in these scripts, so a small AST pass is enough.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    captions: list[tuple[float, float]] = []
    kpis: list[tuple[float, float, float, float]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        fname = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", "")
        try:
            if fname == "caption_below" and len(node.args) >= 3:
                captions.append((float(ast.literal_eval(node.args[1])),
                                 float(ast.literal_eval(node.args[2]))))
            elif fname == "kpi_block" and len(node.args) >= 5:
                kpis.append((float(ast.literal_eval(node.args[1])),
                             float(ast.literal_eval(node.args[2])),
                             float(ast.literal_eval(node.args[3])),
                             float(ast.literal_eval(node.args[4]))))
        except (ValueError, TypeError, SyntaxError):
            continue
    problems: list[str] = []
    for kx, ky, kw, kh in kpis:
        if kw < 60:                      # narrow sidebar KPI is allowed
            continue
        candidates = [(cx, cy) for cx, cy in captions if abs(cx - kx) <= 12]
        if not candidates:
            problems.append(
                f"{name}: KPI 块 (x={kx:g}, y={ky:g}) 附近没有面板 caption；"
                f"KPI 要贴在它所总结的面板描述下面，不要甩到整图底部")
            continue
        gap = min(abs(cy - (ky + kh)) for _cx, cy in candidates)
        if gap > 8:
            problems.append(
                f"{name}: KPI 顶边离最近 caption 有 {gap:.0f} mm（>8 mm）——"
                f"把 KPI 移到 caption 正下方，值/标签成组贴近")
    return problems


def check(root: Path) -> list[str]:
    problems: list[str] = []
    context = _figure_context(root)
    language = str(context.get("language") or "zh").strip().lower()
    expected_font = str(context.get("font") or
                        ("Microsoft YaHei" if language.startswith("zh") else "Arial"))
    scripts = sorted(
        p for p in (root / "figures").glob("plate_*.py")
        if p.name not in {"make_plates.py"}
    )
    if not scripts:
        return ["figures/plate_*.py 不存在：主图 plate 生成器缺失（⑦ 没有按 plate-figure 出图）"]
    manifest = _load(root / "figures" / "manifest.json", {}) or {}
    figures = manifest.get("figures", {}) if isinstance(manifest, dict) else {}
    signatures: dict[tuple, list[str]] = {}
    for script in scripts:
        stem = script.stem.removeprefix("plate_")
        fid = f"fig_{stem}_plate"
        src = script.read_text(encoding="utf-8", errors="replace")
        if "plate_common" not in src and expected_font not in src:
            problems.append(
                f"{fid}: 未使用模板语言版式（plate_common / {expected_font}）；"
                f"当前模板语言是 {language!r}，不要硬套另一种字体")
        problems.extend(_kpi_layout_issues(src, fid))
        problems.extend(_kpi_placement_issues(src, fid))
        # 不要求套模板：只把脚本里真实写出的 axes_mm 矩形收集成“构图签名”，
        # 用来抓“四张图其实是同一个骨架换数据”。作者仍然自己设计构图。
        rects = re.findall(
            r"(?:P\.)?axes_mm\(\s*fig\s*,\s*([-\d.]+)\s*,\s*([-\d.]+)\s*,"
            r"\s*([-\d.]+)\s*,\s*([-\d.]+)", src)
        if rects:
            sig = tuple(sorted(tuple(round(float(v), 1) for v in r) for r in rects))
            signatures.setdefault(sig, []).append(script.name)
        entry = figures.get(fid)
        if not isinstance(entry, dict):
            problems.append(f"{fid}: manifest 未登记（{script.name} 没有产出/登记）")
            continue
        artifacts = entry.get("artifacts") or []
        if not artifacts:
            problems.append(f"{fid}: manifest 没有 artifacts")
        for rel in artifacts:
            if not (root / str(rel)).is_file():
                problems.append(f"{fid}: 产物不存在 {rel}")
        review = entry.get("review") or {}
        if review.get("status") != "passed":
            problems.append(f"{fid}: 尚未通过当前版本的视觉复核")

        pdf = root / "figures" / f"{fid}.pdf"
        text = _pdf_text(pdf) if pdf.is_file() else ""
        if text:
            for banned in BANNED_TEXT:
                if banned in text:
                    problems.append(
                        f"{fid}: 图内仍有说明句/英文脚注「{banned}」；"
                        f"口径写进 manifest caption，不进图")
            cjk = sum(1 for ch in text if "一" <= ch <= "鿿")
            latin = sum(1 for ch in text if ("A" <= ch <= "Z") or ("a" <= ch <= "z"))
            if language.startswith("zh") and cjk < 20:
                problems.append(
                    f"{fid}: 图内中文字符仅 {cjk} 个（<20）；中文模板的主图应使用中文标题/标注")
            elif language.startswith("en") and latin < 40:
                problems.append(
                    f"{fid}: 图内英文字母仅 {latin} 个（<40）；英文模板的主图应使用英文标题/标注"
                    f"（不要沿用中文模板的文案）")
    for _sig, names in signatures.items():
        if len(names) > 1:
            problems.append(
                f"构图重复：{', '.join(names)} 的 axes_mm 矩形完全相同；"
                f"每张主图要按自己的证据链重新设计构图，不要复制同一骨架")
    return problems


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", type=Path, default=Path.cwd())
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    try:
        problems = check(args.root.resolve())
    except Exception as exc:                 # 崩溃也要吐出合法 JSON，别让驱动只看到空 stdout
        problems = [f"check_plate 运行失败：{type(exc).__name__}: {exc}"]
    if args.json:
        print(json.dumps({"status": "FAIL" if problems else "PASS",
                          "issues": problems}, ensure_ascii=False, indent=2))
    else:
        print("PASS" if not problems else "FAIL")
        for p in problems:
            print(" -", p)
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
