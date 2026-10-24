# -*- coding: utf-8 -*-
"""Route A 示例：透明线框 + 2D 剖切（圆柱热质耦合模型）。

这不是固定模板，而是一份**可改的设计样例**：
- 左边 2D 横截面负责讲清边界条件与半径；
- 右边 3D 透明圆柱负责讲清“径向一维 + 轴向长度”；
- 标签用 ``annotate3d`` 固定在屏幕偏移上，引线不穿实体。

运行（项目根目录）::

    python skills/7Route-diagram/assets/physical3d/templates/route_a_wireframe.py \
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


def build(font: str, width_mm: float, out_dir: Path, stem: str) -> tuple[Path, Path]:
    S.configure_style(font, 8.5)
    fig = plt.figure(figsize=(width_mm / 25.4, width_mm / 25.4 * 0.56))

    # ---------------- (a) 2D 横截面 ----------------
    ax2 = fig.add_axes([0.015, 0.10, 0.34, 0.82])
    S.panel_2d(ax2, (-1.65, 1.65), (-1.55, 1.55))
    S.cross_section(ax2, 1.0, rings=(0.25, 0.5, 0.75), theta_arrows=(0,))
    ax2.annotate("", xy=(1.0, 0.0), xytext=(0.0, 0.0),
                 arrowprops=dict(arrowstyle="-|>", color=S.BLUE, lw=1.3,
                                 shrinkA=0, shrinkB=0), zorder=6)
    ax2.text(0.55, -0.13, "$r$", color=S.BLUE, fontsize=9.5,
             fontweight="bold")
    # 对流加热：箭头指向表面内部；水分蒸发：箭头向外
    S.boundary_arrow(ax2, 112, 1.0, "热：$h,\\ T_\\infty$", S.RED,
                     inward=True, text_offset=(0.06, 0.14))
    S.boundary_arrow(ax2, 62, 1.0, "湿：$h_m,\\ C_\\infty$", S.TEAL,
                     inward=False, text_offset=(0.06, -0.16))
    ax2.text(0.0, -0.16, "$r=0$", color="white", fontsize=9.0, ha="center",
             va="top", zorder=6.9)
    ax2.text(0.0, -0.16, "$r=0$", color=S.AMBER, fontsize=8.2, ha="center",
             va="top", zorder=7.0)
    ax2.text(-1.52, -1.42, "横截面", fontsize=8.2, color=S.MUTED)

    # ---------------- (b) 3D 透明圆柱 ----------------
    ax3 = fig.add_axes([0.34, 0.03, 0.64, 0.94], projection="3d")
    S.setup_ax(ax3, elev=18, azim=-62,
               xlim=(-3.0, 3.0), ylim=(-3.0, 3.0), zlim=(-0.2, 6.4))
    S.half_cyl(ax3, 2.0, 0, 6, 0, 2 * np.pi, color=S.FILL_BLUE, alpha=0.15)
    # 外轮廓
    for z in (0.0, 3.0, 6.0):
        S.ring(ax3, 2.0, z, 0, 2 * np.pi, color=S.BLUE, lw=1.2)
    for th in np.linspace(0, 2 * np.pi, 8, endpoint=False):
        S.vertical_line(ax3, 2.0, th, 0, 6, color=S.BLUE, lw=0.8,
                        ls=(0, (4, 3)))
    # 内部径向分层
    for rr in (0.5, 1.0, 1.5):
        S.ring(ax3, rr, 0.03, 0, 2 * np.pi, color="#93C5FD", lw=0.7,
               ls=(0, (4, 3)))
        for z in (0.0, 6.0):
            S.ring(ax3, rr, z + (0.03 if z == 0 else -0.03), 0, 2 * np.pi,
                   color="#93C5FD", lw=0.7, ls=(0, (4, 3)))
    # 轴心
    ax3.plot([0, 0], [0, 0], [0, 6], color=S.AMBER, lw=1.5,
             ls=(0, (3, 2)))
    S.annotate3d(ax3, (0, 0, 6.05), "轴心 $r=0$", xytext=(18, 12),
                 color=S.AMBER, bold=True)
    S.annotate3d(ax3, (2.0, 0.0, 3.0), "$R_0=2$ cm", xytext=(24, 0),
                 color=S.BLUE)
    S.annotate3d(ax3, (0.0, -2.0, 0.0), "$L=25$ cm（示意截取）",
                 xytext=(-8, -22), color=S.MUTED, ha="right", size=8.0)
    ax3.text2D(0.78, 0.04, "三维透视", transform=ax3.transAxes,
               fontsize=8.2, color=S.MUTED)

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
