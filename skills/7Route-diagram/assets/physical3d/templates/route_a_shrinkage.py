# -*- coding: utf-8 -*-
"""Route A 示例：收缩域与材料坐标的双面板（Q4 型几何）。

设计要点：
- 两个面板共用同一视角与轴向比例，读者才能看出“动域 → 固定域”的对应；
- 初始/当前外径用虚线/实线区分，标签用 ``annotate3d`` 固定屏幕偏移；
- 不写长解释，映射关系只留一个箭头 + 符号。

运行::

    python skills/7Route-diagram/assets/physical3d/templates/route_a_shrinkage.py \
        --out-dir figures --stem fig_geometry_3d --width-mm 120
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import style3d as S  # noqa: E402


def build(font: str, width_mm: float, out_dir: Path, stem: str):
    S.configure_style(font, 8.5)
    R0, Rt = 2.000, 1.198
    Z0, Z1 = 0.0, 6.0
    fig = plt.figure(figsize=(width_mm / 25.4, width_mm / 25.4 * 0.46))

    # ---------------- (a) 物理域 ----------------
    axL = fig.add_axes([0.01, 0.12, 0.40, 0.80], projection="3d")
    S.setup_ax(axL, elev=18, azim=-60,
               xlim=(-3.0, 3.0), ylim=(-3.0, 3.0), zlim=(-0.2, 6.4))
    for z in (Z0, 3.0, Z1):
        S.ring(axL, R0, z, 0, 2 * np.pi, color=S.MUTED, lw=0.9,
               ls=(0, (4, 3)))
    for th in np.linspace(0, 2 * np.pi, 8, endpoint=False):
        S.vertical_line(axL, R0, th, Z0, Z1, color=S.MUTED, lw=0.7,
                        ls=(0, (4, 3)))
    for z in (Z0, 3.0, Z1):
        S.ring(axL, Rt, z, 0, 2 * np.pi, color=S.BLUE, lw=1.4)
    for th in np.linspace(0, 2 * np.pi, 8, endpoint=False):
        S.vertical_line(axL, Rt, th, Z0, Z1, color=S.BLUE, lw=0.9)
    axL.plot([0, 0], [0, 0], [Z0 - 0.1, Z1 + 0.1], color=S.AMBER, lw=1.4,
             ls=(0, (3, 2)))
    S.annotate3d(axL, (0, 0, Z1 + 0.12), "$r=0$", xytext=(-8, 14),
                 color=S.AMBER, bold=True, ha="right")
    S.annotate3d(axL, (R0, 0, Z1 * 0.72), "$R_0$",
                 xytext=(18, 6), color=S.MUTED)
    S.annotate3d(axL, (Rt, 0, Z1 * 0.35), "$R(t)$",
                 xytext=(18, -6), color=S.BLUE)
    S.arrow3d(axL, (R0 * 0.98, 0.0, 2.0), (Rt * 1.02, 0.0, 2.0),
              color=S.RED, lw=1.6)
    S.annotate3d(axL, (0.55, 0.05, 2.0), "收缩", xytext=(6, -18),
                 color=S.RED, bold=True, size=8.2)
    fig.text(0.01, 0.035, "(a) 物理域 $r\\in[0,R(t)]$", fontsize=8.2,
             color=S.MUTED, ha="left", va="bottom")

    # ---------------- (b) 材料坐标 ----------------
    axR = fig.add_axes([0.59, 0.12, 0.40, 0.80], projection="3d")
    S.setup_ax(axR, elev=18, azim=-60,
               xlim=(-3.0, 3.0), ylim=(-3.0, 3.0), zlim=(-0.2, 6.4))
    for z in (0.0, 1.5, 3.0, 4.5, 6.0):
        S.ring(axR, 1.0, z, 0, 2 * np.pi, color=S.BLUE, lw=1.2)
        for rr in (0.25, 0.5, 0.75):
            S.ring(axR, rr, z, 0, 2 * np.pi, color="#93C5FD", lw=0.7,
                   ls=(0, (4, 3)))
    for th in np.linspace(0, 2 * np.pi, 8, endpoint=False):
        S.vertical_line(axR, 1.0, th, Z0, Z1, color=S.BLUE, lw=0.9)
    axR.plot([0, 0], [0, 0], [Z0 - 0.1, Z1 + 0.1], color=S.AMBER, lw=1.4,
             ls=(0, (3, 2)))
    S.annotate3d(axR, (0, 0, Z1 + 0.12), "$\\xi=0$", xytext=(-8, 14),
                 color=S.AMBER, bold=True, ha="right")
    S.annotate3d(axR, (1.0, 0, Z1 * 0.55), "$\\xi=1$", xytext=(16, 0),
                 color=S.BLUE)
    fig.text(0.59, 0.035, "(b) 材料坐标 $\\xi\\in[0,1]$", fontsize=8.2,
             color=S.MUTED, ha="left", va="bottom")

    # 面板之间的映射箭头（figure 坐标）
    arr = FancyArrowPatch((0.425, 0.50), (0.575, 0.50),
                          transform=fig.transFigure, arrowstyle="-|>",
                          mutation_scale=12, color=S.PURPLE, lw=1.6)
    fig.add_artist(arr)
    fig.text(0.500, 0.545, "$\\xi=r/R(t)$", color=S.PURPLE, fontsize=8.4,
             ha="center", va="bottom")
    fig.text(0.500, 0.455, "动域 → 固定域", color=S.PURPLE, fontsize=7.8,
             ha="center", va="top")

    out_dir.mkdir(parents=True, exist_ok=True)
    pdf, png = S.save_fixed(fig, stem, out_dir, width_mm)
    plt.close(fig)
    return pdf, png


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out-dir", type=Path, default=Path("figures"))
    ap.add_argument("--stem", default="fig_geometry_3d")
    ap.add_argument("--font", default="Microsoft YaHei")
    ap.add_argument("--width-mm", type=float, default=120.0)
    args = ap.parse_args()
    pdf, png = build(args.font, args.width_mm, args.out_dir, args.stem)
    print(pdf)
    print(png)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
