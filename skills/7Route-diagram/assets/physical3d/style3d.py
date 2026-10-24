# -*- coding: utf-8 -*-
"""物理立体示意图 · Route A：Matplotlib 3D 透明线框 / 剖切图元。

这套图元的定位（与 ``solid3d.py`` 分工）：

- Route A（本文件）：**透明线框 + 2D 剖切**。适合解释内部结构、径向分层、
  坐标映射、场量位置。mplot3d 画透明面，标签用 ``annotate3d`` 放到 2D 层，
  白描边而不是白底框，避免白框切断几何。
- Route B（``solid3d.py``）：**实心剖切**。自写矢量投影 + 深度排序，
  适合实体圆柱/球/多层的楔形剖切、隐藏面、剖面填充。

字体/语言不在这里硬编码：``configure_style(font=None)`` 读
``reports/FIGURE_CONTEXT.json``（CUMCM 当前为 Microsoft YaHei，英文模板为
Arial 等）；调用方也可以显式传入 ``font`` / ``width_mm``。
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np
import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.patches import Circle
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
from mpl_toolkits.mplot3d import proj3d

# ---------------------------------------------------------------------------
# 语义色（与 figure-studio / 论文其他图同一套低饱和色）
# ---------------------------------------------------------------------------
INK = "#1F2937"
SUB = "#475569"
MUTED = "#64748B"
LINE = "#CBD5E1"
BLUE = "#1D4ED8"
TEAL = "#0F766E"
AMBER = "#B45309"
PURPLE = "#6D28D9"
GREEN = "#15803D"
RED = "#B91C1C"

FILL_BLUE = "#E8F0FE"
FILL_TEAL = "#E6F4F1"
FILL_AMBER = "#FEF3C7"
FILL_PURPLE = "#EDE9FE"
FILL_GRAY = "#F1F5F9"
FILL_GREEN = "#F0FDF4"


def _context_font() -> str | None:
    for rel in ("reports/FIGURE_CONTEXT.json", "config/visualization.json"):
        try:
            data = json.loads((Path(__file__).resolve().parents[4] / rel)
                              .read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        font = str(data.get("font") or "").strip()
        if font:
            return font
    return None


def configure_style(font: str | None = None, base_size: float = 8.5,
                    pdf_fonttype: int = 42) -> None:
    """统一字体、数学字体、矢量字体嵌入方式；``font=None`` 读模板 context。"""
    font = font or _context_font() or "Microsoft YaHei"
    mpl.rcParams.update({
        "font.size": base_size,
        "font.family": "sans-serif",
        "font.sans-serif": [font, "Microsoft YaHei", "SimHei",
                            "Noto Sans CJK SC", "Arial", "DejaVu Sans"],
        "mathtext.fontset": "cm",
        "axes.unicode_minus": False,
        "pdf.fonttype": pdf_fonttype,
        "ps.fonttype": pdf_fonttype,
        "figure.dpi": 120,
        # 不要用 tight bbox：它会改变最终印刷宽度（120 mm 变 116/125 mm）。
        # 图内留白在构图时用 axes 位置控制。
        "savefig.bbox": None,
        "savefig.pad_inches": 0.0,
    })


def setup_ax(ax, elev=18, azim=-62, box=None,
             xlim=(-3.0, 3.0), ylim=(-3.0, 3.0), zlim=(0.0, 6.2),
             dist=10.0, ortho=True):
    """建一个无坐标轴的 3D 场景；正交为默认（论文示意图不制造透视歧义）。

    ``box=None`` 时按坐标范围自动取 ``set_box_aspect``，保证 x/y/z 等比例；
    显式传 box 时必须与坐标范围成比例，否则圆柱会被拉长/压扁。
    """
    if ortho:
        ax.set_proj_type("ortho")
    ax.view_init(elev=elev, azim=azim)
    if box is None:
        box = (xlim[1] - xlim[0], ylim[1] - ylim[0], zlim[1] - zlim[0])
    ax.set_box_aspect(box)
    ax.set_xlim(*xlim)
    ax.set_ylim(*ylim)
    ax.set_zlim(*zlim)
    ax.set_axis_off()
    # matplotlib >=3.8 删除了 Axes3D.dist 的 setter：`ax.dist = 9`
    # 只会在实例上挂一个普通属性，get_proj() 仍读 _dist=10。
    # 直接写 _dist（老版本也有这个字段）；失败再退回 dist。
    try:
        ax._dist = float(dist)
    except Exception:
        try:
            ax.dist = dist
        except Exception:
            pass
    return ax


# ---------------------------------------------------------------------------
# 3D 图元
# ---------------------------------------------------------------------------
def half_cyl(ax, r, z0, z1, t0=0.0, t1=np.pi, color=FILL_BLUE,
             alpha=0.32, edge=None, lw=0.0, n=72):
    """圆柱侧面（可只画一段角度）。透明填充；不要用它画实心体。"""
    t = np.linspace(t0, t1, n)
    z = np.linspace(z0, z1, 2)
    T, Z = np.meshgrid(t, z)
    X, Y = r * np.cos(T), r * np.sin(T)
    ax.plot_surface(X, Y, Z, color=color, alpha=alpha, linewidth=lw,
                    edgecolor=edge, shade=False, antialiased=True)


def cut_face(ax, r, z0, z1, theta, color=FILL_GRAY, alpha=0.55,
             edge=LINE, lw=0.6):
    """r-z 平面上的单个径向剖面（矩形）。"""
    c, s = np.cos(theta), np.sin(theta)
    pts = [(0, 0, z0), (r * c, r * s, z0), (r * c, r * s, z1), (0, 0, z1)]
    poly = Poly3DCollection([pts], facecolor=color, edgecolor="none",
                            alpha=alpha)
    ax.add_collection3d(poly)
    ax.plot([0, r * c], [0, r * s], [z0, z0], color=edge, lw=lw)
    ax.plot([0, r * c], [0, r * s], [z1, z1], color=edge, lw=lw)


def diameter_face(ax, r, z0, z1, color=FILL_GRAY, alpha=0.9,
                  edge=LINE, lw=0.6):
    """半圆柱的直径剖面（y=0 的整块矩形）。"""
    pts = [(-r, 0, z0), (r, 0, z0), (r, 0, z1), (-r, 0, z1)]
    poly = Poly3DCollection([pts], facecolor=color, edgecolor="none",
                            alpha=alpha)
    ax.add_collection3d(poly)
    ax.plot([-r, r], [0, 0], [z0, z0], color=edge, lw=lw)
    ax.plot([-r, r], [0, 0], [z1, z1], color=edge, lw=lw)


def annular_cap(ax, r_in, r_out, z, theta0=0.0, theta1=np.pi,
                color=FILL_GRAY, alpha=0.55, edge=LINE, lw=0.6,
                nr=24, nt=48):
    """环形扇面（端面）；单个多边形，不产生内部网格线。"""
    t = np.linspace(theta0, theta1, nt)
    outer = [(r_out * np.cos(a), r_out * np.sin(a), z) for a in t]
    if r_in <= 1e-9:
        pts = outer + [(0.0, 0.0, z)]
    else:
        inner = [(r_in * np.cos(a), r_in * np.sin(a), z) for a in t[::-1]]
        pts = outer + inner
    poly = Poly3DCollection([pts], facecolor=color, edgecolor="none",
                            alpha=alpha)
    ax.add_collection3d(poly)
    ring(ax, r_out, z, theta0, theta1, color=edge, lw=lw)
    if r_in > 1e-9:
        ring(ax, r_in, z, theta0, theta1, color=edge, lw=lw)


def ring(ax, r, z, theta0=0.0, theta1=np.pi, color=LINE, lw=0.8,
         ls="-", n=120):
    t = np.linspace(theta0, theta1, n)
    ax.plot(r * np.cos(t), r * np.sin(t), np.full_like(t, z),
            color=color, lw=lw, ls=ls)


def radial_line(ax, r0, r1, z, theta, color=LINE, lw=0.8, ls="-"):
    ax.plot([r0 * np.cos(theta), r1 * np.cos(theta)],
            [r0 * np.sin(theta), r1 * np.sin(theta)],
            [z, z], color=color, lw=lw, ls=ls)


def vertical_line(ax, r, theta, z0, z1, color=LINE, lw=0.8, ls="-",
                  alpha=1.0):
    ax.plot([r * np.cos(theta), r * np.cos(theta)],
            [r * np.sin(theta), r * np.sin(theta)],
            [z0, z1], color=color, lw=lw, ls=ls, alpha=alpha)


def arrow3d(ax, p0, p1, color=SUB, lw=1.4, ratio=0.18):
    p0 = np.asarray(p0, float)
    p1 = np.asarray(p1, float)
    d = p1 - p0
    ax.quiver(p0[0], p0[1], p0[2], d[0], d[1], d[2],
              color=color, linewidth=lw, arrow_length_ratio=ratio,
              normalize=False)


def label3d(ax, p, text, color=INK, size=8.5, ha="left", va="center",
            bold=False, halo=True, halo_width=2.6, zorder=20):
    """3D 标签：用白色底层文字做描边，避免白框切断几何。

    不要用 ``path_effects`` 给文字描边：它会把文字转成轮廓，PDF 里丢字体、
    也不可检索。这里画两遍文字（白色大一号 + 彩色），字体仍正常嵌入。
    """
    if halo:
        ax.text(p[0], p[1], p[2], text, color="white",
                fontsize=size + halo_width * 0.28, ha=ha, va=va,
                fontweight=("bold" if bold else "normal"),
                zorder=zorder - 0.1, clip_on=False)
    ax.text(p[0], p[1], p[2], text, color=color, fontsize=size,
            ha=ha, va=va, fontweight=("bold" if bold else "normal"),
            zorder=zorder, clip_on=False)


def annotate3d(ax, p, text, xytext=(18, 10), color=INK, size=8.5,
               ha="left", va="center", bold=False, halo=True,
               leader=True, leader_color=None, leader_lw=0.8,
               arrow=False, zorder=25):
    """把 3D 点投到 2D，再用 ``annotate`` 放标签（可带引线）。

    ``xytext`` 是屏幕偏移（points）。这是 Route A 解决“3D 标签乱跑”的关键：
    锚点跟着 3D 走，文字位置由屏幕偏移决定，引线不会穿过实体。
    """
    x3, y3, z3 = p
    x2, y2, _ = proj3d.proj_transform(x3, y3, z3, ax.get_proj())
    lc = leader_color or color
    arrowstyle = "-|>" if arrow else "-"
    if leader or arrow:
        if halo:
            ax.annotate("", xy=(x2, y2), xytext=xytext,
                        textcoords="offset points", annotation_clip=False,
                        arrowprops=dict(arrowstyle=arrowstyle, color="white",
                                        lw=leader_lw + 2.2, shrinkA=2,
                                        shrinkB=2))
        ax.annotate("", xy=(x2, y2), xytext=xytext,
                    textcoords="offset points", annotation_clip=False,
                    arrowprops=dict(arrowstyle=arrowstyle, color=lc,
                                    lw=leader_lw, shrinkA=2, shrinkB=2))
    if halo:
        ax.annotate(text, xy=(x2, y2), xytext=xytext,
                    textcoords="offset points", ha=ha, va=va,
                    color="white", fontsize=size + 0.8,
                    fontweight=("bold" if bold else "normal"),
                    zorder=zorder - 0.1, annotation_clip=False)
    ann = ax.annotate(text, xy=(x2, y2), xytext=xytext,
                      textcoords="offset points", ha=ha, va=va,
                      color=color, fontsize=size,
                      fontweight=("bold" if bold else "normal"),
                      zorder=zorder, annotation_clip=False)
    return ann


def dimension3d(ax, p0, p1, text, color=SUB, size=8.0, offset=(0, 0),
                lw=0.9, double=True):
    """3D 两点间尺寸标注：投影后画双箭头 + 偏移文字。"""
    x0, y0, _ = proj3d.proj_transform(*p0, ax.get_proj())
    x1, y1, _ = proj3d.proj_transform(*p1, ax.get_proj())
    style = "<|-|>" if double else "-|>"
    ax.annotate("", xy=(x1, y1), xytext=(x0, y0),
                arrowprops=dict(arrowstyle=style, color=color, lw=lw,
                                shrinkA=0, shrinkB=0),
                annotation_clip=False)
    ax.annotate(text, xy=((x0 + x1) / 2, (y0 + y1) / 2),
                xytext=offset, textcoords="offset points",
                ha="center", va="center", color="white",
                fontsize=size + 0.8, annotation_clip=False, zorder=24)
    ax.annotate(text, xy=((x0 + x1) / 2, (y0 + y1) / 2),
                xytext=offset, textcoords="offset points",
                ha="center", va="center", color=color, fontsize=size,
                annotation_clip=False, zorder=25)


# ---------------------------------------------------------------------------
# 2D 面板（横截面、事件示意）——Route A/B 共用
# ---------------------------------------------------------------------------
def panel_2d(ax, xlim, ylim, equal=True):
    ax.set_aspect("equal" if equal else "auto")
    ax.set_xlim(*xlim)
    ax.set_ylim(*ylim)
    ax.axis("off")
    return ax


def cross_section(ax, R, rings=(), theta_arrows=(), color=FILL_BLUE,
                  edge=BLUE, lw=1.5, center_color=AMBER):
    """圆截面 + 内部等 r 虚线 + 轴心点。"""
    ax.add_patch(Circle((0, 0), R, facecolor=color, edgecolor=edge,
                        lw=lw, zorder=1))
    for rr in rings:
        ax.add_patch(Circle((0, 0), rr, fill=False, edgecolor="#93C5FD",
                            lw=0.8, ls=(0, (4, 3)), zorder=2))
    ax.plot([0], [0], marker="o", ms=4.0, color=center_color, zorder=5)
    for ang in theta_arrows:
        a = np.deg2rad(ang)
        ax.annotate("", xy=(R * np.cos(a), R * np.sin(a)),
                    xytext=(0.0, 0.0),
                    arrowprops=dict(arrowstyle="-|>", color=edge, lw=1.2,
                                    shrinkA=0, shrinkB=0), zorder=4)


def boundary_arrow(ax, angle_deg, R, text, color, inward=True,
                   text_offset=(0.06, 0.0), text_size=8.4):
    """表面边界箭头。``inward=True`` 表示热/质流向表面内部（对流加热）。

    2026A 的 F1 曾把热流画成向外——这是物理方向错误。对流边界的热量
    从环境进入药材，箭头应指向表面内部；水分从表面向外蒸发，箭头向外。
    """
    a = np.deg2rad(angle_deg)
    c, s = np.cos(a), np.sin(a)
    if inward:
        p0 = (R * 1.28 * c, R * 1.28 * s)
        p1 = (R * 0.98 * c, R * 0.98 * s)
    else:
        p0 = (R * 0.98 * c, R * 0.98 * s)
        p1 = (R * 1.28 * c, R * 1.28 * s)
    ax.annotate("", xy=p1, xytext=p0,
                arrowprops=dict(arrowstyle="-|>", color=color, lw=1.4,
                                shrinkA=0, shrinkB=0), zorder=6)
    tx = R * 1.30 * c + text_offset[0] * (1 if c >= 0 else -1)
    ty = R * 1.30 * s + text_offset[1]
    ha = "left" if c >= 0 else "right"
    ax.text(tx, ty, text, color="white", fontsize=text_size + 0.8,
            ha=ha, va="center", zorder=5.9)
    ax.text(tx, ty, text, color=color, fontsize=text_size,
            ha=ha, va="center", zorder=6.0)


# ---------------------------------------------------------------------------
# 导出
# ---------------------------------------------------------------------------
def save(fig, stem, out_dir, dpi=600):
    """固定画布导出 PDF + PNG；不要用 bbox_inches='tight' 改最终尺寸。"""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    pdf = out_dir / (stem + ".pdf")
    png = out_dir / (stem + ".png")
    fig.savefig(pdf, format="pdf", bbox_inches=None)
    fig.savefig(png, dpi=dpi, bbox_inches=None)
    return pdf, png


def save_fixed(fig, stem, out_dir, width_mm, dpi=600):
    """按最终印刷宽度导出：先按 width_mm 设定 figsize，再保存。"""
    w = width_mm / 25.4
    h = fig.get_figheight() * (w / fig.get_figwidth())
    fig.set_size_inches(w, h)
    return save(fig, stem, out_dir, dpi=dpi)
