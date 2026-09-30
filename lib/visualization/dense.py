"""Faceted heatmaps retain every row and one common absolute colour scale."""
import math

import matplotlib.pyplot as plt
from matplotlib.colors import Normalize

from .charts import numeric


def faceted_heatmap(values, rows, columns, *, colorbar_label, rows_per_panel=18,
                    width_mm=170):
    values = numeric(values, ndim=2)
    if values.shape != (len(rows), len(columns)):
        raise ValueError("Heatmap labels do not match data")
    if type(rows_per_panel) is not int or not 1 <= rows_per_panel <= 24:
        raise ValueError("Use 1 to 24 rows per panel")
    count = math.ceil(len(rows) / rows_per_panel)
    if count > 3:
        raise ValueError("Split into multiple figures; at most three panels per figure")
    if width_mm / count < 50:
        raise ValueError("Each panel needs at least 50 mm; split the figure")
    height_mm = max(65, min(rows_per_panel, len(rows)) * 4 + 20)
    fig, axes = plt.subplots(1, count, squeeze=False, layout="constrained",
                             figsize=(width_mm / 25.4, height_mm / 25.4))
    # Never normalise each panel separately: colour must remain comparable.
    norm = Normalize(vmin=float(values.min()), vmax=float(values.max()))
    for i, ax in enumerate(axes.flat):
        start = i * rows_per_panel
        end = min(start + rows_per_panel, len(rows))
        im = ax.imshow(values[start:end], aspect="auto", cmap="Blues", norm=norm,
                       interpolation="nearest")
        ax.set_yticks(range(end-start), rows[start:end])
        ax.set_xticks(range(len(columns)), columns, rotation=45, ha="right")
        ax.set_title(f"{rows[start]}–{rows[end-1]}", loc="left", fontsize=9)
        ax.set_ylim(min(rows_per_panel, len(rows))-.5, -.5)
    fig.colorbar(im, ax=list(axes.flat), orientation="horizontal", fraction=.06,
                 pad=.08, label=colorbar_label, aspect=50)
    return fig
