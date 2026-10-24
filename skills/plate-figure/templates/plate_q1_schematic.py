# -*- coding: utf-8 -*-
"""问题 1 主图：预热 30 min，热穿过整根，失水只发生在表层。

只读 ``figures/data/q1_series.npz``。版式与 Q3/Q4 不同：左侧是剖面试意图，
右侧 2×2 是温度、径向含水率、中心/表面含水率和失水层厚度，底部 KPI 条。

运行：
    E:/miniconda3/envs/NewMathAgent/python.exe -X utf8 figures/plate_q1.py
"""


from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from scipy.stats import gaussian_kde

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills" / "plate-figure" / "assets"))
import plate_common as P  # noqa: E402

from matplotlib.patches import Circle, FancyArrowPatch  # noqa: E402

P.setup()

# ---------------------------------------------------------------------------
# data
# ---------------------------------------------------------------------------
d = np.load(ROOT / "figures" / "data" / "q1_series.npz")
T = np.asarray(d["t_h"], float)
TC = np.asarray(d["T_center"], float)
TS = np.asarray(d["T_surface"], float)
CC = np.asarray(d["C_center"], float)
CS = np.asarray(d["C_surface"], float)
R = np.asarray(d["r_field"], float)
TF = np.asarray(d["t_field"], float)
CF = np.asarray(d["C_field"], float)
TF = np.asarray(d["T_field"], float)
TFLD = np.asarray(d["t_field"], float)

R0 = float(R[-1])
C0 = float(CF[0, 0])
T_END = float(T[-1])
I_END = int(np.argmin(np.abs(T - T_END)))
C_END = CF[I_END]

# 10 % 失水层：C 降到 0.9*C0 以下的半径区间
LOSS = 0.9 * C0
r_cross = []
for row in CF:
    idx = np.where(row < LOSS)[0]
    if not len(idx):
        r_cross.append(R0)
        continue
    j = int(idx[0])
    if j == 0:
        r_cross.append(R[0])
    else:
        r0, r1 = R[j - 1], R[j]
        c0, c1 = row[j - 1], row[j]
        r_cross.append(float(r0 + (LOSS - c0) * (r1 - r0) / (c1 - c0)))
r_cross = np.asarray(r_cross, float)
skin_mm = (R0 - r_cross) * 10.0
SKIN_END = float(np.interp(T_END, T, skin_mm))
R_SKIN = R0 - SKIN_END / 10.0

# panel c uses the delivered 30-min radial profile
C_PROF = C_END

# ---------------------------------------------------------------------------
# figure
# ---------------------------------------------------------------------------
W, H = 210.0, 150.0
fig = P.canvas(W, H)
P.header(fig, "", "30 min：热穿整根，水只动 4.1 mm 表层", "")

# ---------------------------------------------------------------------------
# a  cross-section schematic (no heatmap)
# ---------------------------------------------------------------------------
axa = P.axes_mm(fig, 5, 48, 64, 80)
axa.set_xlim(-2.35, 2.35)
axa.set_ylim(-2.85, 2.85)
axa.set_aspect("equal")
axa.axis("off")

axa.add_patch(Circle((0, 0), R0, fc=P.DRY, ec=P.AMBER, lw=1.0, zorder=1))
axa.add_patch(Circle((0, 0), R_SKIN, fc="#DCEAF7", ec=P.BLUE, lw=0.8, zorder=2))
axa.add_patch(Circle((0, 0), R_SKIN * 0.18, fc="none", ec=P.BLUE, lw=0.5,
                     ls=(0, (2, 2)), zorder=3))
axa.plot([0], [0], marker="+", ms=6, color=P.BLUE, mew=0.9, zorder=4)

# radial dimension
axa.annotate("", xy=(R0, -2.42), xytext=(0, -2.42),
             arrowprops=dict(arrowstyle="<->", color=P.LINE, lw=0.65,
                             shrinkA=0, shrinkB=0), zorder=5)
axa.text(R0 / 2, -2.30, "R = 2 cm", fontsize=5.6, color=P.LINE,
         ha="center", va="bottom")

# direct labels
axa.annotate("湿芯\nC = 2.550", xy=(0, 0), xytext=(0, -0.72),
             fontsize=5.8, color=P.BLUE, ha="center", va="center",
             linespacing=1.35, bbox=P.wbox(0.22), zorder=8)
axa.annotate("干皮 4.1 mm\nC = 1.510", xy=(1.80, 0.75), xytext=(0.35, 2.28),
             fontsize=5.8, color=P.AMBER, ha="left", va="center",
             linespacing=1.35, bbox=P.wbox(0.22), zorder=8,
             arrowprops=dict(arrowstyle="-|>", color=P.AMBER, lw=0.7,
                             shrinkA=1, shrinkB=1, mutation_scale=5))
axa.annotate("热流入", xy=(1.55, 1.85), xytext=(0.45, 2.80),
             fontsize=5.6, color=P.RED, ha="left", va="top",
             bbox=P.wbox(0.18), zorder=8,
             arrowprops=dict(arrowstyle="-|>", color=P.RED, lw=0.7,
                             shrinkA=1, shrinkB=2, mutation_scale=5))
axa.annotate("水分流出", xy=(1.94, -1.25), xytext=(0.55, -2.72),
             fontsize=5.6, color=P.AMBER, ha="left", va="top",
             bbox=P.wbox(0.18), zorder=8,
             arrowprops=dict(arrowstyle="-|>", color=P.AMBER, lw=0.7,
                             shrinkA=1, shrinkB=2, mutation_scale=5))
for xy in [(-1.55, 1.45), (-1.35, -1.35)]:
    axa.add_patch(FancyArrowPatch(xy, (xy[0] * 0.55, xy[1] * 0.55),
                                  arrowstyle="-|>", mutation_scale=5.5,
                                  lw=0.7, color=P.RED, zorder=6))

# ---------------------------------------------------------------------------
# b  wet core vs dry skin (stacked bars, no line)
# ---------------------------------------------------------------------------
axb = P.axes_mm(fig, 71, 102, 63, 28)
t_show = [0.0, 0.25, 0.5]
T_c = [float(np.interp(t, T, TC)) for t in t_show]
T_s = [float(np.interp(t, T, TS)) for t in t_show]
skin_show = np.asarray([float(np.interp(t, T, skin_mm)) for t in t_show], float)
wet_r = R0 - skin_show / 10.0
yy = np.arange(3)
axb.barh(yy, wet_r, height=0.55, color="#DCEAF7", edgecolor=P.BLUE,
         lw=0.7, zorder=3)
axb.barh(yy, skin_show / 10.0, left=wet_r, height=0.55, color=P.DRY,
         edgecolor=P.AMBER, lw=0.7, zorder=3)
axb.set_yticks(yy)
axb.set_yticklabels(["0 min", "15 min", "30 min"], fontsize=5.3)
axb.invert_yaxis()
axb.set_xlim(0, 2.1)
P.clean(axb)
axb.tick_params(axis="y", length=0)

# ---------------------------------------------------------------------------
# c  radial temperature distribution (sci-box raincloud grammar)
# ---------------------------------------------------------------------------
axc = P.axes_mm(fig, 140, 102, 65, 28)
groups = [0.0, 0.25, 0.5]
cols = ["#E8A598", "#D96C5F", P.RED]
for i, (tt, col) in enumerate(zip(groups, cols)):
    j = int(np.argmin(np.abs(TFLD - tt)))
    vals = np.asarray(TF[j], float)
    if np.ptp(vals) < 1e-9:
        axc.plot([i - 0.30, i], [vals[0], vals[0]], color=col, lw=1.2,
                 alpha=0.9, zorder=2)
    else:
        kernel = gaussian_kde(vals, bw_method=0.55)
        yg = np.linspace(vals.min() - 0.6, vals.max() + 0.6, 120)
        dens = kernel(yg)
        dens = dens / max(dens.max(), 1e-12) * 0.34
        axc.fill_betweenx(yg, i - dens, i, color=col, alpha=0.32, lw=0)
        axc.plot(i - dens, yg, color=col, lw=0.6, alpha=0.9, zorder=2)
    bp = axc.boxplot([vals], positions=[i + 0.14], widths=0.11,
                     patch_artist=True, showfliers=False, zorder=4,
                     medianprops=dict(color=col, lw=0.9),
                     whiskerprops=dict(color=col, lw=0.6),
                     capprops=dict(color=col, lw=0.6),
                     boxprops=dict(facecolor=col, edgecolor=col, lw=0.5))
    for patch in bp["boxes"]:
        patch.set_alpha(0.25)
    rng = np.random.default_rng(11 + i)
    axc.scatter(np.full(len(vals), i + 0.31) + rng.uniform(-0.03, 0.03, len(vals)),
                vals, s=4.0, color=col, edgecolor="white", linewidth=0.25, zorder=5)
axc.set_xlim(-0.55, 2.55)
axc.set_ylim(27.4, 38.2)
axc.set_xticks([0, 1, 2])
axc.set_xticklabels(["0 min", "15 min", "30 min"], fontsize=5.2)
axc.set_ylabel("温度 / °C", labelpad=2.5)
P.clean(axc)
axc.tick_params(axis="x", length=0)

# ---------------------------------------------------------------------------
# d  relative change after 30 min (diverging bars)
# ---------------------------------------------------------------------------
axd = P.axes_mm(fig, 71, 52, 134, 36)
labels = ["表面 T", "中心 T", "表面 C", "中心 C"]
vals = [(TS[-1] / TS[0] - 1.0) * 100.0,
        (TC[-1] / TC[0] - 1.0) * 100.0,
        (CS[-1] / C0 - 1.0) * 100.0,
        (CC[-1] / C0 - 1.0) * 100.0]
cols = [P.RED, P.RED, P.BLUE, P.BLUE]
yy = np.arange(4)
axd.barh(yy, vals, height=0.52, color=cols, edgecolor="white", lw=0.4,
         zorder=3)
axd.axvline(0, color=P.INK, lw=0.7, zorder=4)
for y, v in zip(yy, vals):
    if abs(v) < 0.15:
        txt, ha, dx = "≈0", "left", 2.0
    else:
        txt, ha, dx = f"{v:+.1f}%", ("left" if v >= 0 else "right"), (2.0 if v >= 0 else -2.0)
    axd.text(v + dx, y, txt, fontsize=5.5, color=P.INK, ha=ha, va="center",
             zorder=5)
axd.set_yticks(yy)
axd.set_yticklabels(labels, fontsize=5.4)
axd.invert_yaxis()
axd.set_xlim(-55, 45)
P.clean(axd)
axd.tick_params(axis="y", length=0)

# ---------------------------------------------------------------------------
# panel letters + KPI band
# ---------------------------------------------------------------------------
P.caption_below(fig, 5, 48, "a", "径向剖面")
P.caption_below(fig, 71, 98, "b", "湿芯（蓝）/ 干皮（灰），半径 / cm")
P.caption_below(fig, 140, 98, "c", "温度分布（0/15/30 min）")
P.caption_below(fig, 71, 46, "d", "30 min 相对变化 / %")

P.kpi_block(fig, 71, 30, 134, 14,
            [("36.79 °C", "表面温度"),
             ("33.58 °C", "中心温度"),
             ("1.510 kg/kg", "表面含水率"),
             (f"{SKIN_END:.1f} mm", "失水层厚度")],
            cols=4, accent=P.BLUE)

P.save(fig, "fig_q1_plate")
