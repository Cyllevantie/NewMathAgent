#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Guard against submitting the reference roadmap skeleton as the final figure.

The template is a grammar/style reference, not a fixed layout.  Running
``figures/make_roadmap.py`` produces a valid *reference* composition, but if
that exact node skeleton is submitted unchanged for every problem the stage
stops designing.  This check compares the node ids in the drawio with the ids
declared by the reference implementation; a high overlap means "still the
reference skeleton" and the stage must re-lay it out for this problem.

It also requires ``reports/ROADMAP_DESIGN.md`` (question count, real branches,
steps per branch, result documents) so the layout decision is written down
before drawing.

Usage:
    python skills/7Route-diagram/scripts/check_roadmap_design.py --root .
    python skills/7Route-diagram/scripts/check_roadmap_design.py --root . --json
"""
from __future__ import annotations

import argparse
import contextlib
import io
import json
import re
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def _reference_ids(root: Path) -> set[str]:
    src = root / "skills" / "7Route-diagram" / "scripts" / "flow1_roadmap.py"
    try:
        text = src.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return set()
    ids = set(re.findall(r'(?:V|T)\("([A-Za-z][A-Za-z0-9_]*)"', text))
    return {i for i in ids if not i.startswith(("l_", "e_"))}


def _plain(value: str) -> str:
    text = re.sub(r"<br\s*/?>", " ", value or "", flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _boxes(path: Path):
    tree = ET.parse(path)
    model = next(tree.iter("mxGraphModel"))
    pw = float(model.get("pageWidth", 0) or 0)
    ph = float(model.get("pageHeight", 0) or 0)
    if not pw or not ph:
        return []
    out = []
    for cell in tree.iter("mxCell"):
        if cell.get("vertex") != "1":
            continue
        style = cell.get("style") or ""
        if ("strokeColor=none" in style or "dashed=1;fillColor=none" in style
                or "shape=document" not in style and "rhombus" not in style
                and "rounded=1" not in style and "parallelogram" not in style):
            continue
        g = cell.find("mxGeometry")
        if g is None:
            continue
        try:
            x, y = float(g.get("x", 0)), float(g.get("y", 0))
            w, h = float(g.get("width", 0)), float(g.get("height", 0))
        except (TypeError, ValueError):
            continue
        text = _plain(cell.get("value"))
        if len(text) < 2:
            continue
        out.append((text, (x + w / 2) / pw, (y + h / 2) / ph))
    return out


def _reference_boxes(root: Path):
    src = root / "skills" / "7Route-diagram" / "scripts" / "flow1_roadmap.py"
    if not src.is_file():
        return []
    code = src.read_text(encoding="utf-8", errors="replace")
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "ref.drawio"
        code = re.sub(r'OUT\s*=\s*PROJECT_ROOT\s*/\s*"figures"\s*/\s*"fig_roadmap\.drawio"',
                      f'OUT = Path(r"{out.as_posix()}")', code, count=1)
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                exec(compile(code, str(src), "exec"),
                     {"__name__": "__main__", "__file__": str(src)})
            return _boxes(out)
        except Exception:
            return []


def _layout_copy_hits(root: Path, drawio: Path) -> list[str]:
    ref = _reference_boxes(root)
    cur = _boxes(drawio)
    if len(ref) < 8 or not cur:
        return []
    used = set()
    hits = 0
    for text, nx, ny in ref:
        best = None
        for i, (ctext, cx, cy) in enumerate(cur):
            if i in used or ctext != text:
                continue
            d = abs(cx - nx) + abs(cy - ny)
            if best is None or d < best[0]:
                best = (d, i)
        if best is not None and best[0] <= 0.08:
            used.add(best[1]); hits += 1
    if hits >= max(8, int(len(ref) * 0.6)):
        return [f"{hits}/{len(ref)} 个框的文字+归一化位置与参考实现重合"]
    return []


def check(root: Path) -> list[str]:
    root = root.resolve()
    drawio = root / "figures" / "fig_roadmap.drawio"
    if not drawio.is_file():
        return []
    issues: list[str] = []
    design = root / "reports" / "ROADMAP_DESIGN.md"
    if not design.is_file():
        issues.append(
            "fig_roadmap: 缺 reports/ROADMAP_DESIGN.md（先写本题问数/真实分支/"
            "支链步数/结果文档数，再画；不要直接跑参考生成器）")
    try:
        tree = ET.parse(drawio)
    except Exception as exc:                 # noqa: BLE001
        return [f"fig_roadmap: drawio 无法解析：{exc}"]
    ids = {c.get("id") for c in tree.iter("mxCell") if c.get("id")}
    ref = _reference_ids(root)
    hits = sorted(ids & ref)
    if ref and len(hits) >= max(8, int(len(ref) * 0.6)):
        sample = "、".join(hits[:8])
        issues.append(
            f"fig_roadmap: 仍是参考实现的节点骨架（命中 {len(hits)}/{len(ref)} 个 id："
            f"{sample}…）——模板只给语法/比例，本题的列数、层数、支链和结果文档要重排；"
            f"请按 reports/ROADMAP_DESIGN.md 重新构图或另写生成器，不要只改画布/字号")
    else:
        overlap = _layout_copy_hits(root, drawio)
        if overlap:
            issues.append(
                "fig_roadmap: 换了节点 id 但布局仍是参考实现（" + overlap[0] +
                "）——不要只重命名，按本题结构重新排列；模板只给语法/比例")
    return issues


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", type=Path, default=Path.cwd())
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    try:
        problems = check(args.root)
    except Exception as exc:                 # noqa: BLE001
        problems = [f"check_roadmap_design 运行失败：{type(exc).__name__}: {exc}"]
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
