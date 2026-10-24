# -*- coding: utf-8 -*-
"""问题 3 主图：干前沿从表面推进到轴心。

左上是唯一保留的场图（C(r,t)），右侧是六条径向剖面与敏感性分布，
左下收敛小图，底部 KPI 条。图内不放 "Panel a: ..." 说明文字；口径写进
manifest / LaTeX caption。

运行：
    E:/miniconda3/envs/NewMathAgent/python.exe -X utf8 figures/plate_q3.py
"""


from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills" / "plate-figure" / "assets"))
import plate_common as P  # noqa: E402

from matplotlib.colors import BoundaryNorm, ListedColormap  # noqa: E402
from scipy.stats import gaussian_kde  # noqa: E402

P.setup()

# ---------------------------------------------------------------------------
# data
# ---------------------------------------------------------------------------
d3 = np.load(ROOT / "figures" / "data" / "q3_dryfront.npz")
R = np.asarray(d3["r_cm"], float)
T = np.asarray(d3["t_h"], float)
C = np.asarray(d3["C"], float)
RMAX = float(R[-1])
s3 = json.loads((ROOT / "results" / "q3_summary.json").read_text(encoding="utf-8-sig"))
T_DRY = float(s3["t_dry_h"])
i_surf = int(np.where(C[:, -1] <= 0.15)[0][0])
T_SURF = float(T[i_surf])
DT_LAG = T_DRY - T_SURF

sens = np.load(ROOT / "figures" / "data" / "q_sensitivity.npz")
GROUPS = [
    ("$h_m$\n传质系数", sens["labels_hm"], sens["values_hm"], float(sens["ref_hm"][0]),
     P.BLUE2),
    ("$C_e$\n环境含水率", sens["labels_ce"], sens["values_ce"], float(sens["ref_ce"][0]),
     P.RED),
    ("$\\lambda$/$\\rho_{ref}$\n蒸发/密度", sens["labels_ref"], sens["values_ref"],
     float(sens["ref_ref"][0]), "#42949E"),
    ("U5\n4 h 外推", sens["labels_u5"], sens["values_u5"], float(sens["ref_u5"][0]),
     "#9A4D8E"),
]

conv = np.load(ROOT / "figures" / "data" / "q_convergence.npz")
q3c = json.loads((ROOT / "results" / "q3_checks.json").read_text(encoding="utf-8-sig"))
MESH_T = np.asarray(conv["val_q3"], float)
STEP_T = np.array([q3c["convergence"]["N400_dt10p0"]["t_dry_h"],
                   q3c["convergence"]["N400_dt2p0"]["t_dry_h"],
                   q3c["convergence"]["N400_dt1p0"]["t_dry_h"]])

# ---------------------------------------------------------------------------
# figure
# ---------------------------------------------------------------------------
W, H = 210.0, 150.0
fig = P.canvas(W, H)
P.header(fig, "", f"干前沿 {T_DRY:.1f} h 到轴心", "")

LEVELS = [0.0, 0.15, 0.35, 0.60, 0.90, 1.25, 1.60, 1.95, 2.25, 2.80]
WET = ["#E3EEF8", "#C6DEF1", "#A3C9E6", "#7FAFD7",
       "#5A91C4", "#3775BA", "#1F5FA8", "#0F4D92"]
CMAP = ListedColormap([P.DRY] + WET)
NORM = BoundaryNorm(LEVELS, len(WET) + 1)

# ---------------------------------------------------------------------------
# a  hero moisture field
# ---------------------------------------------------------------------------
axa = P.axes_mm(fig, 5, 46, 100, 82)
axa.pcolormesh(T, R, C.T, cmap=CMAP, norm=NORM, shading="auto",
               rasterized=True, zorder=1)
cs = axa.contour(T, R, C.T, levels=[0.15], colors=[P.RED], linewidths=1.25,
                 zorder=4)
lab = axa.clabel(cs, fmt="C = 0.15", inline=True, inline_spacing=6,
                 fontsize=5.3, colors=P.RED)
for lb in lab or []:
    lb.set_bbox({"facecolor": "white", "edgecolor": "none", "alpha": 0.95,
                 "pad": 0.5})
    lb.set_zorder(6)

axa.annotate(f"表面干燥\n{T_SURF:.1f} h", xy=(T_SURF, RMAX),
             xytext=(T_SURF + 3.0, 1.60), fontsize=5.7, color=P.RED,
             ha="left", va="center", linespacing=1.35, bbox=P.wbox(0.24), zorder=9,
             arrowprops=dict(arrowstyle="-|>", color=P.RED, lw=0.75,
                             shrinkA=1, shrinkB=2, mutation_scale=5.5))
axa.annotate(f"轴心干燥\n{T_DRY:.1f} h", xy=(T_DRY, 0.0),
             xytext=(T_DRY - 10.5, 0.42), fontsize=5.7, color=P.RED,
             ha="right", va="center", linespacing=1.35, bbox=P.wbox(0.24), zorder=9,
             arrowprops=dict(arrowstyle="-|>", color=P.RED, lw=0.75,
                             shrinkA=1, shrinkB=2, mutation_scale=5.5))
axa.annotate("", xy=(T_DRY, 0.10), xytext=(T_SURF, 0.10),
             arrowprops=dict(arrowstyle="<|-|>", color=P.RED, lw=0.7,
                             shrinkA=0, shrinkB=0, mutation_scale=5.0),
             zorder=8)
axa.text(0.5 * (T_SURF + T_DRY), 0.17, f"{DT_LAG:.0f} h",
         fontsize=5.6, color=P.RED, ha="center", va="bottom", zorder=9)
axa.text(3.0, 0.62, "湿芯", fontsize=6.4, fontweight="bold", color=P.WHITE,
         ha="left", va="center", zorder=8,
         bbox=dict(boxstyle="round,pad=0.24", fc=P.BLUE, ec="none", alpha=0.9))
axa.set_xlim(0, float(T[-1]))
axa.set_ylim(0, RMAX)
axa.set_xticks([0, 12, 24, 36, 48, 60])
axa.set_yticks([0, 0.5, 1.0, 1.5, 2.0])
axa.set_ylabel("r / R", labelpad=3)
P.clean(axa)

cax = axa.inset_axes([0.60, 0.905, 0.34, 0.026])
from matplotlib.cm import ScalarMappable  # noqa: E402
sm = ScalarMappable(norm=NORM, cmap=CMAP)
cb = fig.colorbar(sm, cax=cax, orientation="horizontal")
cb.set_ticks([0.15, 0.60, 1.25, 2.55])
cb.ax.set_xticklabels(["0.15", "0.6", "1.25", "2.55"])
cb.ax.tick_params(labelsize=5.0, length=1.2, width=0.4, pad=1)
cb.outline.set_linewidth(0.35)
cax.set_title("C / (kg/kg)", fontsize=5.0, color=P.MID, pad=1.0, loc="left")
for sp in cax.spines.values():
    sp.set_visible(False)

# ---------------------------------------------------------------------------
# b  wet-core radius at five times (bars, no line)
# ---------------------------------------------------------------------------
axb = P.axes_mm(fig, 112, 102, 93, 26)
SEL_T = [T_SURF, 24.0, 36.0, 48.0, T_DRY]
def _front_at(tt):
    j = int(np.argmin(np.abs(T - tt)))
    row = C[j]
    wet = np.where(row >= 0.15)[0]
    if not len(wet):
        return 0.0
    k = int(wet[-1])
    if k >= len(R) - 1:
        return RMAX
    c0, c1 = row[k], row[k + 1]
    return float(R[k] + (0.15 - c0) * (R[k + 1] - R[k]) / (c1 - c0))
front = np.asarray([_front_at(t) for t in SEL_T], float)
frac = front / RMAX
cols = ["#9DC3E6", "#6FA3CC", "#3775BA", "#1F5FA8", "#0F4D92"]
xx = np.arange(len(SEL_T))
axb.bar(xx, frac, width=0.55, color=cols, edgecolor="white", lw=0.4,
        zorder=3)
for i, (t, r) in enumerate(zip(SEL_T, front)):
    axb.text(i, frac[i] + 0.035, f"{r:.2f}", fontsize=5.2, color=P.INK,
             ha="center", va="bottom", zorder=4)
axb.set_xticks(xx)
axb.set_xticklabels([f"{t:.1f}" if t in (T_SURF, T_DRY) else f"{t:.0f}"
                     for t in SEL_T], fontsize=5.2)
axb.set_ylim(0, 1.18)
axb.set_ylabel("湿芯半径 $r/R$", labelpad=2.5)
P.clean(axb)
axb.tick_params(axis="x", length=0)

# ---------------------------------------------------------------------------
# c  sensitivity distribution (half-violin + box + points)
# ---------------------------------------------------------------------------
axc = P.axes_mm(fig, 112, 54, 93, 38)
xs = np.arange(len(GROUPS), dtype=float)
rng = np.random.default_rng(7)
for x0, (gname, labels, values, ref, color) in zip(xs, GROUPS):
    vals = np.asarray([(float(v) / ref - 1.0) * 100.0 for v in values], float)
    if len(vals) >= 3 and np.ptp(vals) > 1e-9:
        kde = gaussian_kde(vals, bw_method=0.55)
        yg = np.linspace(vals.min() - 3.0, vals.max() + 3.0, 140)
        dens = kde(yg)
        dens = dens / dens.max() * 0.30
        axc.fill_betweenx(yg, x0 - dens, x0, color=color, alpha=0.30, lw=0)
        axc.plot(x0 - dens, yg, color=color, lw=0.55, alpha=0.85, zorder=2)
    axc.plot([x0 + 0.12, x0 + 0.12], [vals.min(), vals.max()],
             color=color, lw=0.55, alpha=0.55, zorder=3)
    axc.plot([x0 + 0.04, x0 + 0.20], [np.median(vals), np.median(vals)],
             color=color, lw=1.2, zorder=4)
    jitter = rng.uniform(-0.035, 0.035, len(vals))
    axc.scatter(np.full(len(vals), x0 + 0.30) + jitter, vals, s=5.0,
                color=color, edgecolor="white", linewidth=0.3, zorder=5)
axc.axhline(0.0, color=P.BLUE, lw=0.65, ls=(0, (3, 2)), zorder=1)
axc.set_xlim(-0.55, len(GROUPS) - 1 + 0.62)
axc.set_ylim(-10, 55)
axc.set_xticks(xs)
axc.set_xticklabels([g[0] for g in GROUPS], fontsize=5.1, linespacing=1.35)
axc.set_yticks([-10, 0, 10, 20, 30, 40, 50])
axc.set_ylabel("$t_{dry}$ 相对变化 / %", labelpad=2.5)
P.clean(axc)
axc.tick_params(axis="x", length=0, pad=1.5)
axc.annotate("$C_e$ 最敏感 +48.6%", xy=(1.30, 48.6), xytext=(1.45, 52.0),
             fontsize=5.3, color=P.RED, ha="left", va="top",
             bbox=P.wbox(0.18), zorder=8,
             arrowprops=dict(arrowstyle="-|>", color=P.RED, lw=0.65,
                             shrinkA=1, shrinkB=2, mutation_scale=5))


# ---------------------------------------------------------------------------
# d  convergence
# ---------------------------------------------------------------------------
axd = P.axes_mm(fig, 10, 8, 47, 28)
lv = np.arange(1, 4)
axd.axhline(T_DRY, color=P.MUTED, lw=0.55, ls=(0, (4, 2)), zorder=1)
axd.scatter(lv, MESH_T, s=22, color=P.BLUE2, edgecolor="white",
            linewidth=0.4, zorder=4)
axd.scatter(lv, STEP_T, s=18, marker="s", color=P.GREEN2,
            edgecolor="white", linewidth=0.4, zorder=5)
axd.text(0.98, 0.94, "● 网格 200→800", transform=axd.transAxes, fontsize=5.0,
         color=P.BLUE2, va="top", ha="right")
axd.text(0.98, 0.82, "■ Δt 10→1 s", transform=axd.transAxes, fontsize=5.0,
         color=P.GREEN2, va="top", ha="right")
drift = max(MESH_T.max() - MESH_T.min(), STEP_T.max() - STEP_T.min())
axd.text(0.98, 0.67, f"最大差 {drift:.2f} h", transform=axd.transAxes,
         fontsize=5.0, color=P.MID, va="bottom", ha="right")
axd.set_xlim(0.7, 3.3)
axd.set_ylim(min(MESH_T.min(), STEP_T.min()) - 0.08,
             max(MESH_T.max(), STEP_T.max()) + 0.12)
axd.set_xticks([1, 2, 3])
axd.set_xticklabels(["粗", "中", "细"])
axd.set_ylabel("$t_{dry}$ / h", labelpad=2.5)
P.clean(axd)

# ---------------------------------------------------------------------------
# panel letters + KPI band
# ---------------------------------------------------------------------------
P.caption_below(fig, 5, 38.5, "a", "场 C(r,t)，时间 / h")
P.caption_below(fig, 112, 96, "b", "湿芯半径 r/R，时间 / h")
P.caption_below(fig, 112, 48, "c", "敏感性分布")
P.caption_below(fig, 5, 4, "d", "网格 / 时间步收敛（粗/中/细）")

P.kpi_block(fig, 112, 12, 93, 30,
            [("57.57 h", "轴心干燥"),
             ("12.55 h", "表面干燥"),
             (f"{DT_LAG:.1f} h", "前后相差"),
             ("0.40%", "GCI（N=800）")],
            cols=4, accent=P.BLUE)

P.save(fig, "fig_q3_plate")
