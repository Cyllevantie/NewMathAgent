# -*- coding: utf-8 -*-
"""Route A 示例：最坏点 + 事件求根（Q3 型几何）。

左边 3D 透明圆柱回答“最坏点在哪里”，右边 2D 曲线回答“达标时刻怎么定位”。
两张图共用同一套字体/语义色；公式放在曲线之外，白描边而不是白底框。

运行::

    python skills/7Route-diagram/assets/physical3d/templates/route_a_event.py \
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

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import style3d as S  # noqa: E402


def _halo_text(ax, x, y, text, color, size=8.2, ha="left", va="center",
               bold=False, zorder=20):
    ax.text(x, y, text, color="white", fontsize=size + 0.8, ha=ha, va=va,
            fontweight=("bold" if bold else "normal"), zorder=zorder - 0.1)
    ax.text(x, y, text, color=color, fontsize=size, ha=ha, va=va,
            fontweight=("bold" if bold else "normal"), zorder=zorder)


def build(font: str, width_mm: float, out_dir: Path, stem: str):
    S.configure_style(font, 8.5)
    fig = plt.figure(figsize=(width_mm / 25.4, width_mm / 25.4 * 0.50))

    # ---------------- (a) 3D 最坏点 ----------------
    ax3 = fig.add_axes([0.00, 0.06, 0.47, 0.90], projection="3d")
    S.setup_ax(ax3, elev=18, azim=-62,
               xlim=(-3.0, 3.0), ylim=(-3.0, 3.0), zlim=(-0.2, 6.4))
    S.half_cyl(ax3, 2.0, 0, 6, 0, 2 * np.pi, color=S.FILL_BLUE, alpha=0.15)
    for z in (0, 2, 4, 6):
        S.ring(ax3, 2.0, z, 0, 2 * np.pi, color=S.BLUE, lw=1.2)
    for th in np.linspace(0, 2 * np.pi, 8, endpoint=False):
        S.vertical_line(ax3, 2.0, th, 0, 6, color=S.BLUE, lw=0.8,
                        alpha=0.55)
    ax3.plot([0, 0], [0, 0], [0, 6], color=S.AMBER, lw=2.0,
             ls=(0, (3, 2)))
    ax3.plot([0], [0], [3], marker="o", ms=7, color=S.RED, zorder=10)
    S.annotate3d(ax3, (0.0, 0.0, 3.0), "最坏点 $r=0$", xytext=(20, 14),
                 color=S.RED, bold=True, size=8.6)
    S.annotate3d(ax3, (0.0, 0.0, 6.0), "$\\max_r C(r,t)$", xytext=(18, 8),
                 color=S.AMBER, size=8.2)
    fig.text(0.01, 0.02, "全场最坏点在轴心", fontsize=8.2,
             color=S.MUTED, ha="left", va="bottom")

    # ---------------- (b) 事件求根 ----------------
    ax = fig.add_axes([0.55, 0.16, 0.43, 0.72])
    ax.set_xlim(0, 1)
    ax.set_ylim(-0.28, 0.30)
    ax.axis("off")

    x = np.linspace(0, 1, 400)
    y = 0.18 * np.tanh((0.62 - x) * 4.0)
    ax.plot([0, 1], [0, 0], color=S.MUTED, lw=0.9, ls=(0, (4, 3)))
    ax.plot(x, y, color=S.AMBER, lw=2.0)

    xstar = 0.62
    ax.plot([xstar, xstar], [-0.26, 0.0], color=S.RED, lw=0.9,
            ls=(0, (3, 2)))
    ax.plot([xstar], [0], marker="o", ms=6, color=S.RED, zorder=5)
    _halo_text(ax, xstar + 0.02, 0.055, "$t^*=57.1383$ h", S.RED,
               size=8.4, va="bottom")
    _halo_text(ax, 0.50, 0.285, "$g(t)=\\max_r C-0.15$", S.SUB,
               size=8.2, va="top")
    _halo_text(ax, 0.01, -0.02, "$0$", S.MUTED, size=8.0, va="top")

    # 扫描 / Brent
    ax.annotate("", xy=(0.48, 0.225), xytext=(0.05, 0.225),
                arrowprops=dict(arrowstyle="-|>", color=S.TEAL, lw=1.1))
    _halo_text(ax, 0.26, 0.245, "扫描", S.TEAL, size=8.0, ha="center",
               va="bottom")
    ax.annotate("", xy=(0.55, -0.165), xytext=(0.63, -0.165),
                arrowprops=dict(arrowstyle="<|-|>", color=S.PURPLE, lw=1.1,
                                shrinkA=0, shrinkB=0))
    _halo_text(ax, 0.59, -0.185, "$[t_k,t_{k+1}]$：Brent", S.PURPLE,
               size=8.2, ha="center", va="top")
    ax.annotate("", xy=(1.0, -0.245), xytext=(0.05, -0.245),
                arrowprops=dict(arrowstyle="-|>", color=S.MUTED, lw=0.9))
    _halo_text(ax, 0.99, -0.265, "$t$", S.MUTED, size=8.4, ha="right",
               va="top")
    fig.text(0.56, 0.02, "事件求根（示意）", fontsize=8.2,
             color=S.MUTED, ha="left", va="bottom")

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
