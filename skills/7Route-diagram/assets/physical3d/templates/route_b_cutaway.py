# -*- coding: utf-8 -*-
"""Route B 示例：实心圆柱的楔形剖切（自写矢量渲染器）。

适合：对象是实体（圆柱/球/多层介质），需要真的“剖开”看内部，
且不透明面会挡住内部结构。相比 Route A 的透明线框，这张更像论文里的
“立体剖切图”，剖面有填充/剖面线，隐藏面由逐面深度排序处理。

运行（项目根目录）::

    python skills/7Route-diagram/assets/physical3d/templates/route_b_cutaway.py \
        --out-dir figures --stem fig_geometry_3d --width-mm 90
"""
from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import solid3d as S  # noqa: E402


def build(font: str, width_mm: float, out_dir: Path, stem: str) -> tuple[Path, Path]:
    S.configure_style(font, 8.5)
    R = 2.0
    Z = 12.5
    cut_deg, cut_start = 70.0, -35.0
    th_cut = math.radians(cut_start + cut_deg)   # 右侧剖面所在角

    cam = S.Camera(azim=-58, elev=20, zoom=1.10)
    sc = S.Scene(cam)
    sc.cylinder(r=R, z0=0, z1=Z, cut=(cut_deg, cut_start),
                segments=112, color="#DBEAFE", cut_hatch="///",
                cut_color="#F8FAFC", cut_edge="#94A3B8")

    # 剖面上的径向分层（r=0.5/1.0/1.5），画在切面平面内
    c, s = math.cos(th_cut), math.sin(th_cut)
    for rr in (0.5, 1.0, 1.5):
        sc.line([(rr * c, rr * s, 0.02), (rr * c, rr * s, Z - 0.02)],
                color="#93C5FD", lw=0.7, ls=(0, (4, 3)), layer=8)
    # 剖面上的 z 向分层
    for z in (3.0, 6.0, 9.0):
        sc.line([(0.02 * c, 0.02 * s, z), ((R - 0.02) * c, (R - 0.02) * s, z)],
                color="#93C5FD", lw=0.7, ls=(0, (4, 3)), layer=8)

    # 轴心
    sc.line([(0, 0, 0), (0, 0, Z)], color=S.AMBER, lw=1.6,
            ls=(0, (3, 2)), layer=8)

    # 边界箭头：热流入（向内），水分流出（向外）
    a_heat = math.radians(215.0)
    sc.arrow((2.62 * math.cos(a_heat), 2.62 * math.sin(a_heat), 8.2),
             (2.04 * math.cos(a_heat), 2.04 * math.sin(a_heat), 8.2),
             color=S.RED, lw=1.5)
    sc.label((2.62 * math.cos(a_heat), 2.62 * math.sin(a_heat), 8.2),
             "热 $h,\\ T_\\infty$", offset=(-8, 16), color=S.RED,
             ha="right", auto=False)
    a_moist = math.radians(180.0)
    sc.arrow((2.04 * math.cos(a_moist), 2.04 * math.sin(a_moist), 3.0),
             (3.00 * math.cos(a_moist), 3.00 * math.sin(a_moist), 3.0),
             color=S.TEAL, lw=1.5)
    sc.label((3.00 * math.cos(a_moist), 3.00 * math.sin(a_moist), 3.0),
             "湿 $h_m,\\ C_\\infty$", offset=(-8, 0), color=S.TEAL,
             ha="right", auto=False)

    # 半径尺寸：沿剖面从轴心到外缘
    z_arrow = 10.6
    sc.arrow((0.02 * c, 0.02 * s, z_arrow),
             ((R - 0.02) * c, (R - 0.02) * s, z_arrow),
             color=S.BLUE, lw=1.0, style="<|-|>", head=7.0)
    sc.label(((R * 0.55) * c, (R * 0.55) * s, z_arrow),
             "$R_0=2$ cm", offset=(30, -2), color=S.BLUE, ha="left",
             auto=False)

    # 轴心 / 剖面标签
    sc.label((0, 0, Z + 0.08), "轴心 $r=0$", offset=(-12, 18),
             color=S.AMBER, bold=True, ha="right", auto=False)
    sc.label((0.90 * c, 0.90 * s, 2.2), "剖面", offset=(24, 0),
             color=S.SUB, auto=False)

    fig, ax = plt.subplots(figsize=(width_mm / 25.4, width_mm / 25.4 * 1.05))
    sc.fit(ax, margin=0.15)
    sc.draw(ax, fig)
    # 图内不写标题；截取说明放左下角，避免和几何抢位置
    fig.text(0.02, 0.02, "$L=25$ cm，图中截取 12.5 cm", fontsize=7.6,
             color=S.MUTED, ha="left", va="bottom")

    out_dir.mkdir(parents=True, exist_ok=True)
    pdf, png = sc.save(fig, stem, out_dir, width_mm=width_mm, dpi=600)
    plt.close(fig)
    return pdf, png


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out-dir", type=Path, default=Path("figures"))
    ap.add_argument("--stem", default="fig_geometry_3d")
    ap.add_argument("--font", default="Microsoft YaHei")
    ap.add_argument("--width-mm", type=float, default=90.0)
    args = ap.parse_args()
    pdf, png = build(args.font, args.width_mm, args.out_dir, args.stem)
    print(pdf)
    print(png)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
