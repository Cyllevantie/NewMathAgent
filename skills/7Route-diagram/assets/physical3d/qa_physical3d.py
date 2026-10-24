#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""物理立体图 QA：矢量、字体、标签越界/压实体/互相重叠。

用法（项目根目录）::

    python skills/7Route-diagram/assets/physical3d/qa_physical3d.py \
        --pdf figures/fig_geometry_shared.pdf \
        --png figures/fig_geometry_shared.png \
        --scene figures/fig_geometry_shared.scene.json \
        --width-mm 80 --font "Microsoft YaHei"

退出码：0 = 全部通过；1 = 有硬缺陷；2 = 文件缺失/无法读取。
Route A（mplot3d）没有 ``.scene.json`` 时只查 PDF/PNG；标签由 5.1 目检兜底。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

try:
    import fitz  # PyMuPDF
except Exception:  # pragma: no cover
    fitz = None
from PIL import Image


def _norm_font(s: str) -> str:
    return "".join(ch for ch in s.lower() if ch.isalnum())


def check_pdf(path: Path, font: str | None, width_mm: float | None,
              allow_raster: bool = False) -> dict:
    out = {"ok": True, "errors": [], "warnings": [], "info": {}}
    if fitz is None:
        out["ok"] = False
        out["errors"].append(
            "PyMuPDF 不可用，无法检查 PDF；请 pip install PyMuPDF")
        return out
    doc = fitz.open(str(path))
    if doc.page_count != 1:
        out["ok"] = False
        out["errors"].append(f"PDF 页数应为 1，实际 {doc.page_count}")
    page = doc[0]
    images = page.get_images(full=True)
    out["info"]["raster_images"] = len(images)
    if images and not allow_raster:
        out["ok"] = False
        out["errors"].append(
            f"PDF 含 {len(images)} 个位图；物理立体图应为纯矢量（文字+面片）")
    fonts = page.get_fonts(full=True)
    names = [f[3] for f in fonts]
    out["info"]["fonts"] = names
    if font:
        want = _norm_font(font)
        if not any(want in _norm_font(n) for n in names):
            out["warnings"].append(
                f"PDF 字体列表里没找到 {font!r}；实际：{names}")
    if width_mm:
        got_mm = page.rect.width * 25.4 / 72.0
        out["info"]["width_mm"] = round(got_mm, 2)
        if abs(got_mm - width_mm) > max(1.5, width_mm * 0.04):
            out["warnings"].append(
                f"PDF 宽度 {got_mm:.1f} mm 与目标 {width_mm:.1f} mm 偏差较大")
    text = page.get_text()
    out["info"]["text_chars"] = len(text.strip())
    if not text.strip():
        out["warnings"].append("PDF 里没有可提取文字；检查文字是否被转曲")
    # 文字块是否被画布裁掉（Route A 没有 scene.json 时的兜底）
    clipped = []
    tol = 3.0  # pt；字形侧边/下伸部会略超出，真正裁切通常远超 3 pt
    # 默认页面 clip 会丢掉完全在画布外的文字块；扩到无穷远再按 bbox 判。
    clip = fitz.Rect(-1e5, -1e5, page.rect.x1 + 1e5, page.rect.y1 + 1e5)
    for b in page.get_text("blocks", clip=clip):
        x0, y0, x1, y1 = b[:4]
        if (x0 < -tol or y0 < -tol or
                x1 > page.rect.width + tol or y1 > page.rect.height + tol):
            clipped.append(str(b[4])[:40].replace("\n", " "))
    out["info"]["clipped_text_blocks"] = len(clipped)
    if clipped:
        out["ok"] = False
        out["errors"].append("有文字被画布裁掉：" + " | ".join(clipped[:3]))
    doc.close()
    return out


def check_png(path: Path) -> dict:
    out = {"ok": True, "errors": [], "warnings": [], "info": {}}
    im = Image.open(path).convert("RGB")
    w, h = im.size
    out["info"]["size"] = [w, h]
    if w < 300 or h < 300:
        out["ok"] = False
        out["errors"].append(f"PNG 只有 {w}×{h}，分辨率过低")
    # 非白像素占比
    px = im.resize((min(w, 400), min(h, 400)))
    try:
        data = list(px.get_flattened_data())
    except AttributeError:  # Pillow < 11
        data = list(px.getdata())
    nonwhite = sum(1 for r, g, b in data if min(r, g, b) < 245)
    ratio = nonwhite / max(1, len(data))
    out["info"]["ink_ratio"] = round(ratio, 4)
    if ratio < 0.004:
        out["errors"].append("PNG 几乎全白，可能没画上")
        out["ok"] = False
    return out


def check_scene(path: Path, width_mm: float | None,
                allow_geometry_hits: bool = False) -> dict:
    out = {"ok": True, "errors": [], "warnings": [], "info": {}}
    data = json.loads(path.read_text(encoding="utf-8"))
    out["info"]["projection"] = data.get("projection")
    out["info"]["faces"] = data.get("faces")
    out["info"]["labels"] = len(data.get("labels") or [])
    if data.get("projection") not in ("orthographic", "perspective"):
        out["errors"].append("scene.json 缺少 projection（正交/透视）")
        out["ok"] = False
    if not data.get("faces"):
        out["errors"].append("scene.json 里没有面片")
        out["ok"] = False
    labels = data.get("labels") or []
    if not labels:
        out["warnings"].append("scene.json 没有标签记录；确认图内是否真的无需标签")
    boxes = []
    for lb in labels:
        text = lb.get("text", "")
        if lb.get("out_of_bounds"):
            out["errors"].append(f"标签越出画布：{text!r}")
            out["ok"] = False
        if lb.get("geometry_hits", 0) and not allow_geometry_hits:
            out["warnings"].append(
                f"标签压在实体上（{lb['geometry_hits']} 个采样点）：{text!r}")
        bb = lb.get("bbox")
        if bb:
            boxes.append((text, bb))
    # 标签互相重叠
    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            t1, a = boxes[i]
            t2, b = boxes[j]
            ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
            iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
            if ix > 1e-12 and iy > 1e-12:
                out["errors"].append(f"标签互相重叠：{t1!r} <-> {t2!r}")
                out["ok"] = False
    if width_mm and data.get("width_mm"):
        if abs(float(data["width_mm"]) - width_mm) > 1.0:
            out["warnings"].append(
                f"scene.json 宽度 {data['width_mm']} 与目标 {width_mm} 不一致")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--pdf", required=True, type=Path)
    ap.add_argument("--png", type=Path)
    ap.add_argument("--scene", type=Path)
    ap.add_argument("--width-mm", type=float, default=None)
    ap.add_argument("--font", default=None)
    ap.add_argument("--allow-raster", action="store_true")
    ap.add_argument("--allow-geometry-hits", action="store_true")
    ap.add_argument("--report", type=Path, default=None)
    args = ap.parse_args()

    reports = {}
    rc = 0
    if fitz is None:
        print("PyMuPDF unavailable: cannot check PDF (pip install PyMuPDF)",
              file=sys.stderr)
        return 2
    if not args.pdf.exists():
        print(f"missing PDF: {args.pdf}", file=sys.stderr)
        return 2
    try:
        reports["pdf"] = check_pdf(args.pdf, args.font, args.width_mm,
                                   allow_raster=args.allow_raster)
    except Exception as exc:
        print(f"unreadable PDF: {args.pdf}: {exc}", file=sys.stderr)
        return 2
    if args.png:
        if not args.png.exists():
            print(f"missing PNG: {args.png}", file=sys.stderr)
            return 2
        try:
            reports["png"] = check_png(args.png)
        except Exception as exc:
            print(f"unreadable PNG: {args.png}: {exc}", file=sys.stderr)
            return 2
    if args.scene:
        if not args.scene.exists():
            print(f"missing scene json: {args.scene}", file=sys.stderr)
            return 2
        try:
            reports["scene"] = check_scene(
                args.scene, args.width_mm,
                allow_geometry_hits=args.allow_geometry_hits)
        except Exception as exc:
            print(f"unreadable scene json: {args.scene}: {exc}",
                  file=sys.stderr)
            return 2

    for part, rep in reports.items():
        if not rep["ok"]:
            rc = 1
    payload = {"ok": rc == 0, "parts": reports}
    txt = json.dumps(payload, ensure_ascii=False, indent=2)
    print(txt)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(txt, encoding="utf-8")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
