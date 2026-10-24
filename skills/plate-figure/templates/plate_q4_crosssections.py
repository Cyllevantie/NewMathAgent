# -*- coding: utf-8 -*-
"""问题 4 主图：收缩动域把烘干时间压到 51.2 h。

左侧是数据驱动的截面示意（湿芯 / 干壳 / 半径收缩），右侧是 R(t) 与
固定半径对照；底部 KPI 条。图内不放 "Panel a: ..." 说明文字。

运行：
    E:/miniconda3/envs/NewMathAgent/python.exe -X utf8 figures/plate_q4.py
"""


from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills" / "plate-figure" / "assets"))
import plate_common as P  # noqa: E402

from matplotlib.patches import Circle, FancyArrowPatch  # noqa: E402

P.setup()

# ---------------------------------------------------------------------------
# data
# ---------------------------------------------------------------------------
d = np.load(ROOT / "figures" / "data" / "q4_shrink.npz")
XI = np.asarray(d["xi"], float)
T4 = np.asarray(d["t_h"], float)
C4 = np.asarray(d["C"], float)
R4 = np.asarray(d["R_cm"], float)
LEVEL = float(np.asarray(d["level"]).ravel()[0])

s4 = json.loads((ROOT / "results" / "q4_summary.json").read_text(encoding="utf-8-sig"))
T_DRY = float(s4["t_dry_h"])
R_TD = float(s4["R_tdry_cm"])
chk = json.loads((ROOT / "results" / "q4_checks.json").read_text(encoding="utf-8-sig"))
FIX2 = float(chk["fixed_R_negative"]["R2cm"]["t_dry_h"])
FIX12 = float(chk["fixed_R_negative"]["R1198"]["t_dry_h"])
dm = np.load(ROOT / "figures" / "data" / "q4_drymass.npz")
DRIFT = np.asarray(dm["drift_pct"], float)
TDM = np.asarray(dm["t_h"], float)
i_td = int(np.argmin(np.abs(TDM - T_DRY)))
DRIFT_TD = float(DRIFT[i_td])

SCALE = 6.0  # mm per cm in the cross-section strip


def front_xi(row: np.ndarray) -> float:
    """Smallest xi where C <= 0.15; 1.0 if the whole section is still wet."""
    idx = np.where(row <= LEVEL)[0]
    if not len(idx):
        return 1.0
    j = int(idx[0])
    if j == 0:
        return 0.0
    x0, x1 = XI[j - 1], XI[j]
    c0, c1 = row[j - 1], row[j]
    return float(x0 + (LEVEL - c0) * (x1 - x0) / (c1 - c0))


TIMES = [0.5, 36.0, T_DRY]
ROWS = []
for tt in TIMES:
    j = int(np.argmin(np.abs(T4 - tt)))
    R = float(R4[j])
    xf = front_xi(C4[j])
    ROWS.append((tt, R, xf * R, R - xf * R))

# ---------------------------------------------------------------------------
# figure
# ---------------------------------------------------------------------------
W, H = 210.0, 150.0
fig = P.canvas(W, H)
P.header(fig, "", f"收缩把烘干压到 {T_DRY:.1f} h", "")

# ---------------------------------------------------------------------------
# a  data-driven cross-sections
# ---------------------------------------------------------------------------
axa = P.axes_mm(fig, 5, 46, 94, 82)
axa.set_xlim(0, 105)
axa.set_ylim(0, 84)
axa.set_aspect("equal")
axa.axis("off")

centres = [18.0, 52.0, 86.0]
y0 = 46.0
for xc, (tt, R, r_wet, shell) in zip(centres, ROWS):
    ro = R * SCALE
    ri = r_wet * SCALE
    axa.add_patch(Circle((xc, y0), ro, fc=P.DRY, ec=P.AMBER, lw=0.9, zorder=1))
    if ri > 0.15:
        axa.add_patch(Circle((xc, y0), ri, fc="#DCEAF7", ec=P.BLUE, lw=0.8,
                             zorder=2))
    axa.text(xc, y0 - ro - 5.0, f"{tt:.1f} h", fontsize=6.0, fontweight="bold",
             color=P.INK, ha="center", va="top")
    axa.text(xc, y0 - ro - 10.2, f"R={R:.3f} cm", fontsize=5.2, color=P.MUTED,
             ha="center", va="top")
    if r_wet <= 0.03:
        axa.text(xc, y0, "干透", fontsize=5.6, color=P.AMBER, ha="center",
                 va="center", zorder=5, bbox=P.wbox(0.16, 0.9))
    elif shell * 10 > 0.5:
        axa.text(xc, y0, f"干壳\n{shell * 10:.1f} mm", fontsize=5.0,
                 color=P.AMBER, ha="center", va="center", zorder=5,
                 linespacing=1.35, bbox=P.wbox(0.16, 0.85))
    else:
        axa.text(xc, y0, "全湿", fontsize=5.4, color=P.BLUE, ha="center",
                 va="center", zorder=5, bbox=P.wbox(0.16, 0.85))

for xa, xb in [(18 + 11.3, 52 - 8.4), (52 + 7.5, 86 - 7.3)]:
    axa.add_patch(FancyArrowPatch((xa, y0), (xb, y0), arrowstyle="-|>",
                                  mutation_scale=7, lw=0.8, color=P.LINE))

# legend inside the panel
axa.add_patch(Circle((8.0, 79.0), 2.2, fc="#DCEAF7", ec=P.BLUE, lw=0.7))
axa.text(11.5, 79.0, "湿芯 C > 0.15", fontsize=5.3, color=P.INK,
         ha="left", va="center")
axa.add_patch(Circle((40.0, 79.0), 2.2, fc=P.DRY, ec=P.AMBER, lw=0.7))
axa.text(43.5, 79.0, "干壳 C ≤ 0.15", fontsize=5.3, color=P.INK,
         ha="left", va="center")
axa.text(86.0, 79.0, "6 mm/cm", fontsize=5.1, color=P.MUTED,
         ha="center", va="center")

# ---------------------------------------------------------------------------
# b  R(t)
# ---------------------------------------------------------------------------
axb = P.axes_mm(fig, 104, 100, 101, 28)
sample_t = [0.0, 6.0, 24.0, T_DRY]
sample_r = [float(np.interp(t, T4, R4)) for t in sample_t]
bar_cols = [P.BLUE3, P.BLUE2, P.BLUE, P.RED]
xx = np.arange(len(sample_t))
axb.scatter(xx, sample_r, s=34, color=bar_cols, edgecolor="white",
            linewidth=0.6, zorder=4)
for i, (t, r) in enumerate(zip(sample_t, sample_r)):
    axb.text(i, r + 0.045, f"{r:.3f}", fontsize=5.5, color=P.INK,
             ha="center", va="bottom", zorder=5)
axb.set_xticks(xx)
axb.set_xticklabels(["0 h", "6 h", "24 h", f"{T_DRY:.1f} h"], fontsize=5.4)
axb.set_ylim(1.1, 2.14)
axb.set_yticks([1.2, 1.6, 2.0])
axb.set_ylabel("R / cm", labelpad=2.5)
P.clean(axb)
axb.tick_params(axis="x", length=0)

# ---------------------------------------------------------------------------
# c  fixed-radius controls
# ---------------------------------------------------------------------------
axc = P.axes_mm(fig, 104, 50, 101, 36)
labels = ["固定 R=2 cm", "收缩 R(t)", "固定 R=1.198 cm"]
vals = [FIX2, T_DRY, FIX12]
cols = [P.MUTED, P.BLUE, P.BLUE3]
yy = np.arange(3)
axc.barh(yy, vals, height=0.52, color=cols, edgecolor="white", lw=0.5,
         zorder=3)
for y, v in zip(yy, vals):
    axc.text(v + 2.0, y, f"{v:.1f} h", fontsize=5.6, color=P.INK,
             ha="left", va="center", zorder=4)
axc.set_yticks(yy)
axc.set_yticklabels(labels, fontsize=5.4)
axc.invert_yaxis()
axc.set_xlim(0, 155)
axc.set_xticks([0, 50, 100, 150])
P.clean(axc)
axc.tick_params(axis="y", length=0, pad=2)

# ---------------------------------------------------------------------------
# panel letters + KPI band
# ---------------------------------------------------------------------------
P.caption_below(fig, 5, 44, "a", "三时刻截面（湿芯 / 干壳）")
P.caption_below(fig, 104, 96, "b", "R(t) 采样，时间 / h")
P.caption_below(fig, 104, 46, "c", "固定 R 对照，$t_{dry}$ / h")

# KPI belongs directly under the (a) caption, not at the plate bottom.
P.kpi_block(fig, 5, 28, 100, 14,
            [(f"{T_DRY:.2f} h", "烘干时间"),
             (f"{R_TD:.3f} cm", "$t_{dry}$ 时半径"),
             (f"{FIX2:.1f} h", "固定 R=2 cm 对照"),
             (f"{DRIFT_TD:.1f}%", "干物质漂移（审计）")],
            cols=4, accent=P.BLUE)

P.save(fig, "fig_q4_plate")
