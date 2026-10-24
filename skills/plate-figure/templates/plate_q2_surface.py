# -*- coding: utf-8 -*-
"""问题 2 主图：D(C,T) 响应面。

上半版是 sci-box 07 风格的平滑三维曲面（coolwarm + 色条），下半版是三条
温度切片、归一化物性和量级 KPI；不再用俯视等高线热力图。

运行：
    E:/miniconda3/envs/NewMathAgent/python.exe -X utf8 figures/plate_q2.py
"""


from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills" / "plate-figure" / "assets"))
import plate_common as P  # noqa: E402

from matplotlib.patches import FancyBboxPatch  # noqa: E402

P.setup()

# ---------------------------------------------------------------------------
# data
# ---------------------------------------------------------------------------
d = np.load(ROOT / "figures" / "data" / "q2_props.npz")
C = np.asarray(d["C_grid"], float)
T = np.asarray(d["T_grid"], float)
L = np.asarray(d["log10D"], float)
D30 = np.asarray(d["D_30"], float)
D40 = np.asarray(d["D_40"], float)
D50 = np.asarray(d["D_50"], float)
rho_cp = np.asarray(d["rho_cp"], float)
k = np.asarray(d["k"], float)

FULL_DEC = float(np.nanmax(L) - np.nanmin(L))
WET = C >= 0.15
WET_DEC = float(np.nanmax(L[:, WET]) - np.nanmin(L[:, WET]))
i15 = int(np.argmin(np.abs(C - 0.15)))
C_LOG = np.log10(C)
TICKS = [0.05, 0.15, 0.5, 1.25, 2.5]
TICK_POS = np.log10(TICKS)

# ---------------------------------------------------------------------------
# figure
# ---------------------------------------------------------------------------
W, H = 210.0, 150.0
fig = P.canvas(W, H)
P.header(fig, "", f"扩散系数跨 {FULL_DEC:.1f} 个数量级", "")

# ---------------------------------------------------------------------------
# a  smooth 3D response surface (sci-box 07 style)
# ---------------------------------------------------------------------------
axa = P.axes_mm(fig, 4, 68, 148, 60, projection="3d")
XX, YY = np.meshgrid(C_LOG, T)
surf = axa.plot_surface(XX, YY, L, cmap="coolwarm", vmin=-12.2, vmax=-7.8,
                        rcount=80, ccount=110, linewidth=0, antialiased=True,
                        shade=True, alpha=0.98)
axa.plot(np.full_like(T, np.log10(0.15)), T, L[:, i15], color=P.RED, lw=1.8,
         zorder=12)
axa.text(np.log10(0.15), 31.0, float(L[0, i15]) + 0.55, "C=0.15", color=P.RED,
         fontsize=5.2, fontweight="bold", zorder=13,
         bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none", alpha=0.88))
axa.set_xticks(TICK_POS)
axa.set_xticklabels([f"{v:g}" for v in TICKS])
axa.set_yticks([30, 40, 50])
axa.set_zticks([-12, -10, -8])
axa.set_xlabel("C / (kg/kg)", labelpad=3)
axa.set_ylabel("T / °C", labelpad=4)
# z 轴标题会压到右侧 KPI 文本（实测与「干判据」重叠 19.7 pt²）；
# 量纲已由竖色条承担，这里不再重复标注。
axa.set_zlabel("")
axa.view_init(elev=30, azim=-58)
axa.tick_params(labelsize=5.2, pad=0)
axa.set_box_aspect((1.55, 1.05, 0.72), zoom=1.32)
for pane in (axa.xaxis.pane, axa.yaxis.pane, axa.zaxis.pane):
    pane.set_facecolor("white")
    pane.set_edgecolor("#DDDDDD")
axa.xaxis._axinfo["grid"]["color"] = (0.85, 0.85, 0.85, 0.7)
axa.yaxis._axinfo["grid"]["color"] = (0.85, 0.85, 0.85, 0.7)
axa.zaxis._axinfo["grid"]["color"] = (0.85, 0.85, 0.85, 0.7)
axa.xaxis._axinfo["grid"]["linewidth"] = 0.4
axa.yaxis._axinfo["grid"]["linewidth"] = 0.4
axa.zaxis._axinfo["grid"]["linewidth"] = 0.4

cax = fig.add_axes([149.0 / W, 78.0 / H, 2.8 / W, 38.0 / H])
cb = fig.colorbar(surf, cax=cax)
# 竖排标签在色条右侧，实测压住 KPI 的「干判据」（19.7 pt²）；改成色条上方的
# 横排标题，右侧只留刻度数字。
cb.ax.set_title("log$_{10}$D", fontsize=5.8, pad=2)
cb.set_ticks([-12, -10, -8])
cb.ax.tick_params(labelsize=5.0, length=1.4, width=0.4)
cb.outline.set_linewidth(0.35)

# ---------------------------------------------------------------------------
# b  D at four moisture levels x three temperatures (grouped bars)
# ---------------------------------------------------------------------------
axb = P.axes_mm(fig, 8, 14, 93, 36)
C_BARS = [0.15, 0.5, 1.25, 2.5]
def _at(arr):
    return [float(np.interp(c, C, arr)) for c in C_BARS]
D_BARS = [(30, _at(D30), P.BLUE3), (40, _at(D40), P.BLUE),
          (50, _at(D50), P.RED)]
xx = np.arange(len(C_BARS))
bw = 0.24
for j, (temp, vals, col) in enumerate(D_BARS):
    axb.bar(xx + (j - 1) * bw, vals, width=bw, color=col, edgecolor="white",
            lw=0.3, label=f"{temp} °C", zorder=3)
axb.set_yscale("log")
axb.set_ylim(1.0e-12, 3.0e-8)
axb.set_xticks(xx)
axb.set_xticklabels([f"{c:g}" for c in C_BARS], fontsize=5.3)
axb.set_ylabel("D / (m$^2$/s)", labelpad=2.5)
axb.legend(loc="lower left", frameon=False, fontsize=5.0, ncol=3,
           handlelength=1.0, columnspacing=0.7)
P.clean(axb, grid=True)

# ---------------------------------------------------------------------------
# c  normalized properties at the same moisture levels (grouped bars)
# ---------------------------------------------------------------------------
axc = P.axes_mm(fig, 109, 14, 97, 36)
rho_b = _at(rho_cp / np.nanmax(rho_cp))
k_b = _at(k / np.nanmax(k))
bw2 = 0.32
axc.bar(xx - bw2 / 2, rho_b, width=bw2, color=P.BLUE, edgecolor="white",
        lw=0.3, label="ρc$_p$", zorder=3)
axc.bar(xx + bw2 / 2, k_b, width=bw2, color=P.GREEN2, edgecolor="white",
        lw=0.3, label="k", zorder=3)
axc.set_xticks(xx)
axc.set_xticklabels([f"{c:g}" for c in C_BARS], fontsize=5.3)
axc.set_ylim(0.0, 1.12)
axc.set_ylabel("归一化物性", labelpad=2.5)
axc.legend(loc="upper left", frameon=False, fontsize=5.0, ncol=2,
           handlelength=1.0, columnspacing=0.7)
P.clean(axc)

# ---------------------------------------------------------------------------
# d  magnitude KPI (compact, no cards)
# ---------------------------------------------------------------------------
P.kpi_block(fig, 157, 78, 48, 50,
            [(f"{FULL_DEC:.1f} 个数量级", "全范围"),
             (f"{WET_DEC:.1f} 个数量级", "C ≥ 0.15"),
             ("C = 0.15", "干判据"),
             ("28–50 °C", "温度范围")],
            cols=1, accent=P.BLUE)

# ---------------------------------------------------------------------------
# panel letters
# ---------------------------------------------------------------------------
P.caption_below(fig, 5, 58, "a", "D(C,T) 曲面")
P.caption_below(fig, 8, 8, "b", "四个含水率水平，C / (kg/kg)")
P.caption_below(fig, 109, 8, "c", "归一化物性，C / (kg/kg)")
P.caption_below(fig, 157, 74, "d", "量级")

P.save(fig, "fig_q2_plate")
