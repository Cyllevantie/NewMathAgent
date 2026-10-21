# -*- coding: utf-8 -*-
"""Figure Studio: one style, one contract, many recipes.

This module is deliberately a *thin* layer over the project's existing
``lib/visualization`` primitives.  It adds the parts that used to be copied
from figure to figure: language resolution, the unified palette/typography,
panel geometry in millimetres, source-data sidecars, and a handful of
composite recipes (paired raincloud, dot interval, Taylor, radar, 3D
projection, cylinder schematic).

It does not train models, fit curves, or invent intervals.  Every numeric
argument must come from a saved result.  The caller owns the claim.
"""
from __future__ import annotations

import csv
import json
import sys
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping, Sequence

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

import matplotlib as mpl  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import patches  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap, PowerNorm, TwoSlopeNorm  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Patch, PathPatch, Rectangle  # noqa: E402
from matplotlib.path import Path as MplPath  # noqa: E402

from lib.visualization import charts  # noqa: E402
from lib.visualization.export import export as _export  # noqa: E402

from resolve_context import resolve as _resolve  # noqa: E402


# ---------------------------------------------------------------------------
# context and style
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Context:
    root: Path
    template: str
    language: str
    width_mm: float
    half_width_mm: float
    height_mm: float
    dpi: int
    font: str
    labels: Mapping[str, str]
    tokens: Mapping[str, object]
    font_candidates: Sequence[str] = ()

    def L(self, key: str, default: str | None = None) -> str:
        return str(self.labels.get(key, default if default is not None else key))


def context(root: str | Path | None = None, template: str | None = None,
            width_mm: float | None = None) -> Context:
    data = _resolve(Path(root or PROJECT_ROOT), template=template, width_mm=width_mm)
    return Context(
        root=Path(data["root"]),
        template=data["template"],
        language=data["language"],
        width_mm=float(data["width_mm"]),
        half_width_mm=float(data["half_width_mm"]),
        height_mm=float(data["height_mm"]),
        dpi=int(data["dpi"]),
        font=data["font"],
        labels=data["labels"],
        tokens=data["tokens"],
        font_candidates=tuple(data.get("font_candidates") or ()),
    )


def _typo(ctx: Context, width_mm: float | None = None) -> dict:
    """Pick the full-width or half-width typography profile."""
    typo = ctx.tokens.get("typography") or {}
    width = float(width_mm if width_mm is not None else ctx.width_mm)
    profile = ctx.language
    half = f"{ctx.language}_half"
    if width <= 90 and half in typo:
        profile = half
    return dict(typo.get(profile, typo.get(ctx.language, {})))


def _series(ctx: Context) -> list[str]:
    return list((ctx.tokens.get("palette") or {}).get("series") or
                ["#1D4ED8", "#0F766E", "#6D28D9", "#B45309", "#4D7C0F", "#475569"])


def _semantic(ctx: Context, key: str) -> str:
    return str((ctx.tokens.get("palette") or {}).get("semantic", {}).get(key, "#1F2937"))


@contextmanager
def style(ctx: Context, *, width_mm: float | None = None):
    """Apply the unified rcParams and yield the merged export settings.

    Pass ``width_mm`` when the canvas will be narrower than ``ctx.width_mm``;
    that selects the half-width typography profile and records the effective
    width in the export settings.
    """
    effective_width = float(width_mm if width_mm is not None else ctx.width_mm)
    typo = _typo(ctx, effective_width)
    fonts = [ctx.font] + [f for f in (ctx.font_candidates or ()) if f != ctx.font]
    series = _series(ctx)
    linestyles = list((ctx.tokens.get("lines") or {}).get("linestyles") or ["-", "--", ":", "-."])
    with charts.style() as base:
        settings = dict(base)
        settings.update({
            "font_size": float(typo.get("body_pt", 9.0)),
            "min_font_size": float(typo.get("min_pt", 7.5)),
            "width_mm": effective_width,
            "height_mm": ctx.height_mm,
            "dpi": ctx.dpi,
            "palette": series,
            "fonts": fonts,
        })
        rc = {
            "font.family": "sans-serif",
            "font.sans-serif": fonts,
            "font.size": float(typo.get("body_pt", 9.0)),
            "axes.labelsize": float(typo.get("axis_pt", 9.0)),
            "axes.titlesize": float(typo.get("panel_title_pt", 9.0)),
            "xtick.labelsize": float(typo.get("tick_pt", 8.0)),
            "ytick.labelsize": float(typo.get("tick_pt", 8.0)),
            "legend.fontsize": float(typo.get("legend_pt", 8.0)),
            "axes.linewidth": float(typo.get("spine_width", 0.8)),
            "xtick.major.width": float(typo.get("tick_width", 0.8)),
            "ytick.major.width": float(typo.get("tick_width", 0.8)),
            "lines.linewidth": float(typo.get("line_width", 1.2)),
            "lines.markersize": float(typo.get("marker_size", 4.5)),
            "axes.prop_cycle": mpl.cycler(
                color=series,
                linestyle=(linestyles * ((len(series) // max(1, len(linestyles))) + 1))[:len(series)],
            ),
            "axes.unicode_minus": False,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.axisbelow": True,
            "legend.frameon": True,
            "legend.framealpha": 0.92,
            "legend.edgecolor": _semantic(ctx, "box"),
            "legend.facecolor": "white",
            "legend.fancybox": False,
            "hatch.linewidth": 0.35,
            "pdf.fonttype": 42,
            "svg.fonttype": "none",
            "figure.facecolor": "white",
            "savefig.facecolor": "white",
            "savefig.dpi": ctx.dpi,
        }
        with mpl.rc_context(rc):
            yield settings


def canvas(ctx: Context, *, width_mm: float | None = None, height_mm: float | None = None,
           constrained: bool = True):
    w = float(width_mm or ctx.width_mm)
    h = float(height_mm or ctx.height_mm)
    fig = plt.figure(figsize=(w / 25.4, h / 25.4), facecolor="white")
    if constrained:
        fig.set_layout_engine("constrained")
    return fig


def axes_mm(fig, x: float, y: float, w: float, h: float, *, width_mm: float,
            height_mm: float, **kwargs):
    """Place an Axes using millimetres measured from the lower-left corner."""
    return fig.add_axes([x / width_mm, y / height_mm, w / width_mm, h / height_mm], **kwargs)


def panel_label(fig, ax, letter: str, ctx: Context, title: str | None = None,
                *, dx_mm: float = -7.0, dy_mm: float = 2.2, gap_mm: float = 4.0):
    """Place a bold panel letter and an optional short title above the Axes.

    Offsets are in millimetres, not figure fractions: a fixed fraction moves a
    label twice as far on a 160 mm canvas as on an 80 mm one, which is how
    panel titles ended up off the left edge in earlier drafts.
    """
    typo = _typo(ctx)
    box = ax.get_position()
    w_mm = fig.get_figwidth() * 25.4
    h_mm = fig.get_figheight() * 25.4
    x_mm = max(0.5, box.x0 * w_mm + dx_mm)
    x = x_mm / w_mm
    y = (box.y1 * h_mm + dy_mm) / h_mm
    fig.text(x, y, letter, fontsize=float(typo.get("panel_letter_pt", 9.5)),
             fontweight="bold", color=_semantic(ctx, "ink"), ha="left", va="bottom")
    if title:
        fig.text((box.x0 * w_mm + dx_mm + gap_mm) / w_mm, y, title,
                 fontsize=float(typo.get("panel_title_pt", 9.0)),
                 fontweight="bold", color=_semantic(ctx, "ink"), ha="left", va="bottom")


def fig_title(fig, text: str, ctx: Context, *, x: float = 0.055, y: float = 0.995,
              subtitle: str | None = None):
    """A short figure-level title.  Manuscript captions still belong in LaTeX."""
    typo = _typo(ctx)
    fig.text(x, y, text, fontsize=float(typo.get("panel_title_pt", 9.0)) + 0.6,
             fontweight="bold", color=_semantic(ctx, "ink"), ha="left", va="top")
    if subtitle:
        fig.text(x, y - 0.045, subtitle, fontsize=float(typo.get("small_pt", 7.5)),
                 color=_semantic(ctx, "line"), ha="left", va="top")


def clean(ax, *, grid: str | None = "y"):
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    if grid:
        ax.grid(axis=grid, color=mpl.rcParams.get("grid.color", "#E2E8F0"), linewidth=0.7)
    return ax


# ---------------------------------------------------------------------------
# recipes: fields and profiles
# ---------------------------------------------------------------------------
def field_panel(ax, x, y, z, ctx: Context, *, kind: str = "contour",
                quantity: str = "moisture", colorbar_label: str | None = None,
                level: float | None = None, level_label: str | None = None,
                xlabel: str | None = None, ylabel: str | None = None,
                title: str | None = None, vmin=None, vmax=None, gamma=None,
                levels: int = 14):
    """Space-time field: filled contour (thresholds/fronts) or mesh."""
    x = np.asarray(x, float)
    y = np.asarray(y, float)
    z = np.asarray(z, float)
    if z.shape != (len(y), len(x)):
        raise ValueError(f"field z must be (len(y), len(x)); got {z.shape}")
    colorbar_label = colorbar_label or ctx.L("moisture")
    xlabel = xlabel or ctx.L("time_h")
    ylabel = ylabel or ctx.L("radius_cm")

    if kind == "contour":
        charts.contour(
            ax, x, y, z, colorbar_label=colorbar_label, quantity=quantity,
            levels=levels, lines=([level] if level is not None else None),
            highlight=level, highlight_color=_semantic(ctx, "warn"),
            highlight_label=(level_label or ctx.L("criterion")) if level is not None else None,
            vmin=vmin, vmax=vmax, gamma=gamma,
        )
    elif kind == "heatmap":
        cmap = charts.quantity_cmap(quantity) or "viridis"
        g = charts.quantity_gamma(quantity) if gamma is None else gamma
        norm = PowerNorm(g, vmin=float(np.nanmin(z)) if vmin is None else vmin,
                         vmax=float(np.nanmax(z)) if vmax is None else vmax)
        mesh = ax.pcolormesh(x, y, z, cmap=cmap, norm=norm, shading="auto", rasterized=True)
        cb = ax.figure.colorbar(mesh, ax=ax, label=colorbar_label, shrink=.86)
        cb.ax.yaxis.set_major_locator(mpl.ticker.MaxNLocator(nbins=6))
    else:
        raise ValueError("kind must be 'contour' or 'heatmap'")
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    if title:
        ax.set_title(title, loc="left", fontsize=mpl.rcParams["axes.titlesize"],
                     fontweight="bold", pad=4)
    return ax


def heatmap_panel(ax, values, rows: Sequence[str], columns: Sequence[str],
                  ctx: Context, *, colorbar_label: str | None = None,
                  quantity: str | None = None, correlation: bool = False,
                  annotate: bool | None = None, title: str | None = None):
    """Labeled matrix heatmap (categorical rows/columns), wrapping charts.heatmap."""
    charts.heatmap(
        ax, values, rows, columns, colorbar_label=colorbar_label or ctx.L("value"),
        quantity=quantity, correlation=correlation, annotate=annotate,
    )
    ax.set_xticklabels(columns, rotation=45, ha="right")
    ax.set_yticklabels(rows)
    if title:
        ax.set_title(title, loc="left", fontweight="bold", pad=4)
    return ax


def profile_panel(ax, x, series: Mapping[str, Sequence[float]], ctx: Context, *,
                  xlabel: str | None = None, ylabel: str | None = None,
                  logy: bool = False, direct: bool = True, markers: bool = False,
                  legend: bool = False, title: str | None = None,
                  colors: Sequence[str] | None = None):
    """Several radial/time profiles, with direct end labels by default."""
    x = np.asarray(x, float)
    if np.any(np.diff(x) <= 0):
        raise ValueError("profile x must be strictly increasing")
    cols = list(colors or _series(ctx))
    for i, (label, ys) in enumerate(series.items()):
        ys = np.asarray(ys, float)
        ax.plot(x, ys, color=cols[i % len(cols)],
                linestyle=["-", "--", ":", "-."][i % 4],
                marker=("o", "s", "^", "D")[i % 4] if markers else None,
                markersize=mpl.rcParams["lines.markersize"] * 0.75,
                label=str(label))
        if direct and np.isfinite(ys[-1]):
            ax.annotate(str(label), xy=(x[-1], ys[-1]), xytext=(4, 0),
                        textcoords="offset points", va="center", ha="left",
                        fontsize=mpl.rcParams["legend.fontsize"],
                        color=cols[i % len(cols)], clip_on=False)
    if logy:
        ax.set_yscale("log")
    if direct:
        # Leave room for the end labels instead of letting them run off the
        # canvas; the data still occupy the same physical span.
        ax.set_xlim(float(x[0]), float(x[-1]) * 1.12)
    ax.set_xlabel(xlabel or ctx.L("radius_cm"))
    ax.set_ylabel(ylabel or ctx.L("moisture"))
    if legend and not direct:
        ax.legend(loc="best")
    clean(ax)
    if title:
        ax.set_title(title, loc="left", fontweight="bold", pad=4)
    return ax


def small_multiples(fig, x, series: Mapping[str, Sequence[float]], facets: Mapping[str, Sequence[str]],
                    ctx: Context, *, ncols: int = 3, xlabel: str | None = None,
                    ylabel: str | None = None, sharey: bool = True):
    """Facet a family of profiles into a compact grid."""
    names = list(facets)
    nrows = int(np.ceil(len(names) / ncols))
    axes = fig.subplots(nrows, ncols, sharex=True, sharey=sharey, squeeze=False)
    for k, name in enumerate(names):
        ax = axes[k // ncols][k % ncols]
        sub = {lab: series[lab] for lab in facets[name] if lab in series}
        profile_panel(ax, x, sub, ctx, xlabel=xlabel, ylabel=ylabel, direct=False)
        ax.set_title(str(name), loc="left", fontsize=mpl.rcParams["axes.titlesize"] * 0.9)
    for k in range(len(names), nrows * ncols):
        axes[k // ncols][k % ncols].axis("off")
    return axes


# ---------------------------------------------------------------------------
# recipes: distributions and estimates
# ---------------------------------------------------------------------------
def _kde_half(ax, values, x0: float, side: str, color: str, width: float = 0.28):
    vals = np.asarray(values, float)
    vals = vals[np.isfinite(vals)]
    if len(vals) < 5 or np.std(vals) <= 0:
        return
    try:
        from scipy.stats import gaussian_kde
        kde = gaussian_kde(vals)
        grid = np.linspace(vals.min(), vals.max(), 220)
        d = np.asarray(kde(grid), float)
        d = d / max(d.max(), 1e-12) * width
    except Exception:
        hist, edges = np.histogram(vals, bins=24, density=True)
        grid = 0.5 * (edges[:-1] + edges[1:])
        d = hist / max(hist.max(), 1e-12) * width
    if side == "left":
        ax.fill_betweenx(grid, x0 - d, x0, color=color, alpha=0.30, linewidth=0, zorder=1)
    else:
        ax.fill_betweenx(grid, x0, x0 + d, color=color, alpha=0.30, linewidth=0, zorder=1)


def paired_raincloud(ax, before, after, ctx: Context, *, labels: Sequence[str] | None = None,
                     xlabel: str | None = None, ylabel: str | None = None,
                     title: str | None = None, seed: int = 0):
    """Paired raincloud: half violin + points + box + subject lines."""
    before = np.asarray(before, float)
    after = np.asarray(after, float)
    if before.shape != after.shape:
        raise ValueError("before/after must have the same paired length")
    labels = tuple(labels or (ctx.L("before"), ctx.L("after")))
    cols = _series(ctx)
    ink = _semantic(ctx, "ink")
    rng = np.random.default_rng(seed)
    xs = [0.0, 1.0]
    for j, (vals, x0, side) in enumerate(((before, xs[0], "left"), (after, xs[1], "right"))):
        _kde_half(ax, vals, x0, side, cols[j])
        jitter = rng.uniform(-0.045, 0.045, len(vals))
        ax.scatter(np.full(len(vals), x0) + jitter, vals, s=7, color=cols[j],
                   alpha=0.55, linewidth=0, zorder=3)
        q = np.quantile(vals, [0.25, 0.5, 0.75])
        ax.plot([x0 - 0.055, x0 + 0.055], [q[1], q[1]], color=ink, lw=1.6, zorder=4)
        ax.plot([x0, x0], [q[0], q[2]], color=ink, lw=1.0, zorder=4)
        ax.scatter([x0], [q[1]], s=18, facecolor="white", edgecolor=ink, zorder=5)
    for b, a in zip(before, after):
        ax.plot(xs, [b, a], color=_semantic(ctx, "muted"), alpha=0.18, lw=0.55, zorder=0)
    ax.set_xticks(xs, list(labels))
    ax.set_xlim(-0.65, 1.65)
    ax.set_xlabel(xlabel or "")
    ax.set_ylabel(ylabel or ctx.L("moisture"))
    clean(ax)
    if title:
        ax.set_title(title, loc="left", fontweight="bold", pad=4)
    return ax


def paired_dumbbell(ax, before, after, ctx: Context, *, labels: Sequence[str] | None = None,
                    ylabel: str | None = None, title: str | None = None):
    """Small-n paired change: every subject is a line + two dots."""
    before = np.asarray(before, float)
    after = np.asarray(after, float)
    if before.shape != after.shape:
        raise ValueError("before/after must have the same paired length")
    labels = tuple(labels or (ctx.L("before"), ctx.L("after")))
    cols = _series(ctx)
    y = np.arange(len(before))
    for i, (b, a) in enumerate(zip(before, after)):
        ax.plot([b, a], [i, i], color=_semantic(ctx, "muted"), lw=1.0, zorder=1)
    ax.scatter(before, y, color=cols[0], s=16, zorder=2, label=labels[0])
    ax.scatter(after, y, color=cols[1], s=16, zorder=2, label=labels[1])
    ax.set_yticks(y)
    ax.set_yticklabels([f"{i+1}" for i in y], fontsize=mpl.rcParams["xtick.labelsize"] * 0.9)
    ax.invert_yaxis()
    ax.set_xlabel(ylabel or ctx.L("moisture"))
    ax.legend(loc="best")
    clean(ax, grid="x")
    if title:
        ax.set_title(title, loc="left", fontweight="bold", pad=4)
    return ax


def distribution_box(ax, groups: Mapping[str, Sequence[float]], ctx: Context, *,
                     ylabel: str | None = None, xlabel: str | None = None,
                     logy: bool = False, title: str | None = None, showfliers: bool = False):
    """Box + strip; keeps every observation visible for small samples."""
    names = list(groups)
    vals = [np.asarray(groups[n], float) for n in names]
    bp = ax.boxplot(vals, tick_labels=names, showfliers=showfliers, widths=0.45,
                    patch_artist=True, medianprops={"color": _semantic(ctx, "ink"), "lw": 1.4},
                    whiskerprops={"color": _semantic(ctx, "line"), "lw": 0.8},
                    capprops={"color": _semantic(ctx, "line"), "lw": 0.8},
                    boxprops={"edgecolor": _semantic(ctx, "line"), "lw": 0.8})
    cols = _series(ctx)
    rng = np.random.default_rng(0)
    for i, (patch, v) in enumerate(zip(bp["boxes"], vals), start=1):
        patch.set_facecolor(cols[(i - 1) % len(cols)] + "33")
        jitter = rng.uniform(-0.08, 0.08, len(v))
        ax.scatter(np.full(len(v), i) + jitter, v, s=8, color=cols[(i - 1) % len(cols)],
                   alpha=0.65, linewidth=0, zorder=3)
    if logy:
        ax.set_yscale("log")
    ax.set_ylabel(ylabel or ctx.L("value"))
    if xlabel:
        ax.set_xlabel(xlabel)
    clean(ax)
    if title:
        ax.set_title(title, loc="left", fontweight="bold", pad=4)
    return ax


def dot_interval(ax, labels: Sequence[str], values: Sequence[float],
                 low: Sequence[float] | None, high: Sequence[float] | None,
                 ctx: Context, *, reference: float | None = None,
                 xlabel: str | None = None, title: str | None = None,
                 groups: Sequence[str] | None = None, sort: bool = True,
                 value_fmt: str = "{:.2f}", value_labels: bool = True):
    """Sorted point estimates with real intervals; one row per category."""
    values = np.asarray(values, float)
    labels = list(labels)
    if low is None or high is None:
        low = high = None
    else:
        low = np.asarray(low, float)
        high = np.asarray(high, float)
        if not (np.all(low <= values) and np.all(high >= values)):
            raise ValueError("interval bounds must contain the estimate")
    order = np.argsort(values) if sort else np.arange(len(values))
    values = values[order]
    labels = [labels[i] for i in order]
    if low is not None:
        low, high = low[order], high[order]
    if groups is not None:
        groups = [groups[i] for i in order]
    y = np.arange(len(values))
    cols = _series(ctx)
    if groups is None:
        colors = [cols[0]] * len(values)
    else:
        uniq = list(dict.fromkeys(groups))
        colors = [cols[uniq.index(g) % len(cols)] for g in groups]
    if low is not None:
        xerr = np.vstack([values - low, high - values])
        ax.errorbar(values, y, xerr=xerr, fmt="none", ecolor=_semantic(ctx, "line"),
                    elinewidth=0.8, capsize=2.2, capthick=0.6, zorder=2)
    for i, (v, c) in enumerate(zip(values, colors)):
        ax.scatter(v, y[i], s=22, color=c, edgecolor="white", linewidth=0.4, zorder=3)
        if value_labels:
            ax.text(v, y[i] - 0.28, value_fmt.format(v), ha="center", va="bottom",
                    fontsize=mpl.rcParams["xtick.labelsize"] * 0.95, color=_semantic(ctx, "line"))
    ax.set_yticks(y, labels)
    ax.set_ylim(-0.7, len(values) - 0.3)
    ax.invert_yaxis()
    if reference is not None:
        ax.axvline(reference, color=_semantic(ctx, "warn"), lw=1.0, ls="--", zorder=1)
    ax.set_xlabel(xlabel or ctx.L("value"))
    clean(ax, grid="x")
    if title:
        ax.set_title(title, loc="left", fontweight="bold", pad=4)
    return ax


# ---------------------------------------------------------------------------
# recipes: comparison and composition
# ---------------------------------------------------------------------------
def grouped_bars(ax, categories: Sequence[str], series: Mapping[str, Sequence[float]],
                 ctx: Context, *, ylabel: str | None = None, xlabel: str | None = None,
                 errors: Mapping[str, Sequence[float]] | None = None,
                 horizontal: bool = False, title: str | None = None,
                 value_fmt: str = "{:.2f}", hatches: bool = True,
                 value_labels: bool = True):
    """Grouped bars with black edges, optional hatches and direct values."""
    cats = list(categories)
    names = list(series)
    n = len(names)
    cols = _series(ctx)
    width = 0.78 / max(1, n)
    base = np.arange(len(cats), dtype=float)
    hatch_pool = ["", "///", "...", "\\\\\\", "xx"]
    for i, name in enumerate(names):
        vals = np.asarray(series[name], float)
        if vals.shape != (len(cats),):
            raise ValueError(f"series {name!r} does not match categories")
        offset = (i - (n - 1) / 2) * width
        kwargs = dict(color=cols[i % len(cols)], edgecolor=_semantic(ctx, "ink"),
                      linewidth=0.55, width=width * 0.92,
                      hatch=hatch_pool[i % len(hatch_pool)] if hatches else None,
                      label=str(name), zorder=2)
        if horizontal:
            xpos = base + offset
            ax.barh(xpos, vals, **kwargs)
            if errors and name in errors:
                ax.errorbar(vals, xpos, xerr=errors[name], fmt="none",
                            ecolor=_semantic(ctx, "ink"), elinewidth=0.8, capsize=2)
            if value_labels:
                for xv, yv in zip(vals, xpos):
                    ax.annotate(value_fmt.format(xv), xy=(xv, yv), xytext=(3, 0),
                                textcoords="offset points", va="center", ha="left",
                                fontsize=mpl.rcParams["xtick.labelsize"] * 0.78,
                                color=_semantic(ctx, "line"), clip_on=False)
        else:
            xpos = base + offset
            ax.bar(xpos, vals, **kwargs)
            if errors and name in errors:
                ax.errorbar(xpos, vals, yerr=errors[name], fmt="none",
                            ecolor=_semantic(ctx, "ink"), elinewidth=0.8, capsize=2)
            if value_labels:
                for xv, yv in zip(xpos, vals):
                    ax.annotate(value_fmt.format(yv), xy=(xv, yv), xytext=(0, 2),
                                textcoords="offset points", va="bottom", ha="center",
                                fontsize=mpl.rcParams["xtick.labelsize"] * 0.78,
                                color=_semantic(ctx, "line"), clip_on=False)
    if horizontal:
        ax.set_yticks(base, cats)
        ax.invert_yaxis()
        ax.set_xlabel(ylabel or ctx.L("value"))
    else:
        ax.set_xticks(base, cats)
        ax.set_ylabel(ylabel or ctx.L("value"))
        if xlabel:
            ax.set_xlabel(xlabel)
    clean(ax, grid="x" if horizontal else "y")
    if title:
        ax.set_title(title, loc="left", fontweight="bold", pad=4)
    return ax


def stacked_composition(ax, categories: Sequence[str], components: Mapping[str, Sequence[float]],
                        ctx: Context, *, ylabel: str | None = None, title: str | None = None,
                        normalize: bool = False, legend: bool = True):
    """Stacked composition; only use when the component sum is meaningful."""
    cats = list(categories)
    names = list(components)
    cols = _series(ctx)
    mat = np.vstack([np.asarray(components[n], float) for n in names])
    if mat.shape[1] != len(cats):
        raise ValueError("components must share the category length")
    if normalize:
        total = mat.sum(axis=0)
        mat = 100.0 * mat / np.where(total == 0, 1, total)
    bottom = np.zeros(len(cats))
    hatch_pool = ["", "///", "...", "\\\\\\", "xx", "++"]
    x = np.arange(len(cats))
    for i, name in enumerate(names):
        ax.bar(x, mat[i], bottom=bottom, color=cols[i % len(cols)],
               edgecolor=_semantic(ctx, "ink"), linewidth=0.45,
               hatch=hatch_pool[i % len(hatch_pool)], label=str(name), zorder=2)
        bottom += mat[i]
    ax.set_xticks(x, cats)
    ax.set_ylabel(ylabel or (ctx.L("share") if normalize else ctx.L("value")))
    clean(ax)
    if legend:
        ax.legend(loc="upper left", bbox_to_anchor=(1.01, 1.0), frameon=True,
                  borderaxespad=0, fontsize=mpl.rcParams["legend.fontsize"])
    if title:
        ax.set_title(title, loc="left", fontweight="bold", pad=4)
    return ax


def correlation_matrix(ax, variables: Sequence[str], matrix, ctx: Context, *,
                       lower: bool = True, title: str | None = None,
                       colorbar_label: str | None = None):
    """Correlation matrix, zero-centred, optional lower triangle."""
    a = np.asarray(matrix, float)
    if a.shape != (len(variables), len(variables)):
        raise ValueError("matrix shape must match variables")
    a = a.copy()
    if lower:
        a[np.triu_indices_from(a, k=1)] = np.nan
    cmap = mpl.colormaps["RdBu_r"].copy()
    cmap.set_bad("white")
    im = ax.imshow(np.ma.masked_invalid(a), cmap=cmap, vmin=-1, vmax=1, aspect="auto")
    ax.set_xticks(range(len(variables)), variables, rotation=45, ha="right")
    ax.set_yticks(range(len(variables)), variables)
    ax.tick_params(length=0)
    for i in range(len(variables)):
        for j in range(len(variables)):
            if np.isfinite(a[i, j]) and len(variables) <= 12:
                ax.text(j, i, f"{a[i, j]:.2f}", ha="center", va="center",
                        fontsize=mpl.rcParams["xtick.labelsize"] * 0.82,
                        color="white" if abs(a[i, j]) > 0.6 else _semantic(ctx, "ink"))
    cb = ax.figure.colorbar(im, ax=ax, label=colorbar_label or ctx.L("correlation"), shrink=.85)
    cb.ax.yaxis.set_major_locator(mpl.ticker.MaxNLocator(nbins=5))
    for s in ax.spines.values():
        s.set_visible(False)
    if title:
        ax.set_title(title, loc="left", fontweight="bold", pad=4)
    return ax


def scatter_matrix(fig, data: Mapping[str, Sequence[float]], ctx: Context, *,
                   variables: Sequence[str] | None = None, title: str | None = None):
    """Small correlation pair-grid: lower scatter, diagonal histogram, upper r."""
    names = list(variables or data)
    k = len(names)
    gs = fig.add_gridspec(k, k, hspace=0.08, wspace=0.08)
    axes = np.empty((k, k), dtype=object)
    cols = _series(ctx)
    for i, yi in enumerate(names):
        for j, xj in enumerate(names):
            ax = fig.add_subplot(gs[i, j])
            axes[i, j] = ax
            xv = np.asarray(data[xj], float)
            yv = np.asarray(data[yi], float)
            if i == j:
                ax.hist(xv, bins=24, color=cols[i % len(cols)], alpha=0.75, edgecolor="white")
            elif i > j:
                ax.scatter(xv, yv, s=5, color=cols[0], alpha=0.35, linewidth=0, rasterized=True)
            else:
                r = float(np.corrcoef(xv, yv)[0, 1])
                ax.text(0.5, 0.5, f"{r:.2f}", ha="center", va="center",
                        transform=ax.transAxes, fontsize=mpl.rcParams["xtick.labelsize"])
                ax.set_xlim(0, 1)
                ax.set_ylim(0, 1)
            if i == k - 1:
                ax.set_xlabel(xj, fontsize=mpl.rcParams["xtick.labelsize"] * 0.9)
            if j == 0:
                ax.set_ylabel(yi, fontsize=mpl.rcParams["xtick.labelsize"] * 0.9)
            ax.tick_params(labelsize=mpl.rcParams["xtick.labelsize"] * 0.75)
            clean(ax, grid=None)
    if title:
        fig.text(0.01, 0.995, title, ha="left", va="top", fontweight="bold",
                 fontsize=mpl.rcParams["axes.titlesize"])
    return axes


# ---------------------------------------------------------------------------
# recipes: diagnostics, model evaluation, 3D
# ---------------------------------------------------------------------------
def prediction_marginal(fig, observed, predicted, ctx: Context, *,
                        xlabel: str | None = None, ylabel: str | None = None,
                        title: str | None = None, bins: int = 28):
    """Joint prediction-observation scatter with marginal distributions."""
    obs = np.asarray(observed, float)
    pred = np.asarray(predicted, float)
    if obs.shape != pred.shape:
        raise ValueError("observed and predicted must be paired")
    gs = fig.add_gridspec(2, 2, width_ratios=[4, 1], height_ratios=[1, 4],
                          hspace=0.05, wspace=0.05)
    ax = fig.add_subplot(gs[1, 0])
    top = fig.add_subplot(gs[0, 0], sharex=ax)
    right = fig.add_subplot(gs[1, 1], sharey=ax)
    lo = float(min(obs.min(), pred.min()))
    hi = float(max(obs.max(), pred.max()))
    hb = ax.hexbin(obs, pred, gridsize=34, mincnt=1, cmap="Blues", linewidths=0,
                   rasterized=True)
    ax.plot([lo, hi], [lo, hi], color=_semantic(ctx, "muted"), ls="--", lw=0.8)
    ax.set_xlim(lo, hi)
    ax.set_ylim(lo, hi)
    ax.set_xlabel(xlabel or ctx.L("observed"))
    ax.set_ylabel(ylabel or ctx.L("predicted"))
    top.hist(obs, bins=bins, color=_series(ctx)[0], alpha=0.65, edgecolor="white")
    top.axis("off")
    right.hist(pred, bins=bins, orientation="horizontal", color=_series(ctx)[1],
               alpha=0.65, edgecolor="white")
    right.axis("off")
    rmse = float(np.sqrt(np.mean((pred - obs) ** 2)))
    ss = float(np.sum((obs - obs.mean()) ** 2))
    r2 = 1 - float(np.sum((pred - obs) ** 2)) / ss if ss > 0 else float("nan")
    ax.text(0.03, 0.97, f"n = {len(obs):,}\nRMSE = {rmse:.3g}\n$R^2$ = {r2:.3f}",
            transform=ax.transAxes, ha="left", va="top",
            fontsize=mpl.rcParams["legend.fontsize"] * 0.95,
            bbox={"facecolor": "white", "edgecolor": "none", "alpha": 0.9, "pad": 2})
    cb = fig.colorbar(hb, ax=ax, orientation="horizontal", pad=0.10, shrink=0.55)
    cb.set_label(ctx.L("count"), fontsize=mpl.rcParams["legend.fontsize"])
    clean(ax)
    if title:
        fig.text(0.01, 0.995, title, ha="left", va="top", fontweight="bold",
                 fontsize=mpl.rcParams["axes.titlesize"])
    return ax, top, right


def _roc_points(y_true, y_score):
    """ROC points without scikit-learn (the project does not require it)."""
    y = np.asarray(y_true).astype(float)
    score = np.asarray(y_score, float)
    if y.ndim != 1 or score.ndim != 1 or y.shape != score.shape:
        raise ValueError("ROC needs one-dimensional y_true and y_score of equal length")
    if not np.all(np.isin(y, (0.0, 1.0))):
        raise ValueError("y_true must be binary 0/1")
    order = np.argsort(-score, kind="mergesort")
    y, score = y[order], score[order]
    # One point per distinct score (ties are a single threshold).
    last = np.r_[np.where(np.diff(score))[0], len(score) - 1]
    tps = np.cumsum(y)[last]
    fps = (last + 1) - tps
    positives = float(y.sum())
    negatives = float(len(y) - positives)
    if positives == 0 or negatives == 0:
        raise ValueError("ROC needs both positive and negative examples")
    return (np.r_[0.0, fps / negatives], np.r_[0.0, tps / positives])


def _auc(fpr, tpr) -> float:
    return float(np.sum(np.diff(fpr) * (tpr[1:] + tpr[:-1]) / 2.0))


def roc_panel(ax, curves: Mapping[str, tuple], ctx: Context, *,
              title: str | None = None):
    """ROC curves from real labels.  ``curves`` maps name -> (y_true, y_score)."""
    cols = _series(ctx)
    for i, (name, (y_true, y_score)) in enumerate(curves.items()):
        fpr, tpr = _roc_points(y_true, y_score)
        area = _auc(fpr, tpr)
        ax.plot(fpr, tpr, color=cols[i % len(cols)], lw=1.3,
                label=f"{name} (AUC={area:.2f})")
    ax.plot([0, 1], [0, 1], color=_semantic(ctx, "muted"), ls=":", lw=0.8)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1.02)
    ax.set_xlabel(ctx.L("false_positive_rate"))
    ax.set_ylabel(ctx.L("true_positive_rate"))
    ax.legend(loc="lower right", fontsize=mpl.rcParams["legend.fontsize"])
    clean(ax)
    if title:
        ax.set_title(title, loc="left", fontweight="bold", pad=4)
    return ax


def taylor_panel(ax, models: Sequence[str], correlation: Sequence[float],
                 std_ratio: Sequence[float], ctx: Context, *, title: str | None = None,
                 label_points: bool = True):
    """Taylor diagram drawn in Cartesian coordinates (a clean quarter circle).

    Radial distance is the standard-deviation ratio; the angle is arccos(r).
    Plotting it on a normal Axes avoids the overlapping polar tick labels that
    a raw ``projection='polar'`` produces when the panel is small.
    """
    corr = np.clip(np.asarray(correlation, float), -1, 1)
    ratio = np.asarray(std_ratio, float)
    theta = np.arccos(corr)
    x = ratio * np.cos(theta)
    y = ratio * np.sin(theta)
    rmax = max(1.05, float(np.nanmax(ratio)) * 1.12)
    grid = _semantic(ctx, "grid")
    line = _semantic(ctx, "line")
    ink = _semantic(ctx, "ink")
    cols = _series(ctx)

    ax.set_aspect("equal")
    ax.set_xlim(-0.02, rmax * 1.08)
    ax.set_ylim(-0.02, rmax * 1.08)

    arcs = np.linspace(0, np.pi / 2, 240)
    for r in np.linspace(rmax / 4, rmax, 4):
        ax.plot(r * np.cos(arcs), r * np.sin(arcs), color=grid, lw=0.65, zorder=0)
        ax.text(r * 0.70, r * 0.70, f"{r:.1f}", color=line,
                fontsize=mpl.rcParams["xtick.labelsize"],
                ha="center", va="center", zorder=1)
    for c in (0.90, 0.95, 0.99):
        th = np.arccos(c)
        ax.plot([0, rmax * np.cos(th)], [0, rmax * np.sin(th)],
                color=grid, lw=0.65, zorder=0)
        ax.text(rmax * 1.01 * np.cos(th), rmax * 1.01 * np.sin(th), f"{c:.2f}",
                color=line, fontsize=mpl.rcParams["xtick.labelsize"],
                ha="left", va="bottom", clip_on=False, zorder=1)
    ax.plot([0, rmax], [0, 0], color=line, lw=0.8, zorder=1)
    ax.plot([0, 0], [0, rmax], color=line, lw=0.8, zorder=1)
    ax.scatter([1.0], [0.0], marker="*", s=62, color=ink, zorder=5)
    ax.annotate(ctx.L("reference_point"), xy=(1.0, 0.0), xytext=(4, -12), textcoords="offset points",
                fontsize=mpl.rcParams["legend.fontsize"], color=ink)
    for i, name in enumerate(models):
        ax.scatter(x[i], y[i], s=26, color=cols[i % len(cols)],
                   edgecolor="white", linewidth=0.4, zorder=4)
        if label_points:
            ax.annotate(str(name), xy=(x[i], y[i]), xytext=(4, 4),
                        textcoords="offset points",
                        fontsize=mpl.rcParams["legend.fontsize"] * 0.82,
                        color=cols[i % len(cols)])
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)
    if title:
        ax.set_title(title, loc="left", fontweight="bold", pad=6)
    return ax

def radar_panel(ax, categories: Sequence[str], series: Mapping[str, Sequence[float]],
                ctx: Context, *, normalize: bool = False, title: str | None = None,
                legend: bool = True):
    """Radar fingerprint for 3-8 metrics; values must be comparable.

    A radar needs a polar Axes.  Silently drawing the same data on a
    rectilinear Axes produces a misleading sawtooth, so fail loudly instead.
    """
    if getattr(ax, "name", "") != "polar":
        raise ValueError("radar_panel requires a polar Axes; use fig.add_axes(..., projection='polar')")
    cats = list(categories)
    k = len(cats)
    angles = np.linspace(0, 2 * np.pi, k, endpoint=False).tolist()
    angles += angles[:1]
    cols = _series(ctx)
    mat = np.vstack([np.asarray(series[name], float) for name in series])
    if normalize:
        denom = np.nanmax(np.abs(mat), axis=0)
        mat = mat / np.where(denom == 0, 1, denom)
    for i, name in enumerate(series):
        vals = mat[i].tolist() + [mat[i][0]]
        ax.plot(angles, vals, color=cols[i % len(cols)], lw=1.2, label=str(name))
        ax.fill(angles, vals, color=cols[i % len(cols)], alpha=0.10)
    ax.set_xticks(angles[:-1], cats)
    ax.set_yticks([0.25, 0.5, 0.75, 1.0])
    ax.set_yticklabels([])
    ax.set_ylim(0, max(1.0, float(np.nanmax(mat)) * 1.12))
    ax.tick_params(labelsize=mpl.rcParams["xtick.labelsize"])
    if legend:
        ax.legend(loc="upper right", bbox_to_anchor=(1.28, 1.10),
                  fontsize=mpl.rcParams["legend.fontsize"])
    if title:
        ax.set_title(title, loc="left", fontweight="bold", pad=12)
    return ax


def surface3d_panel(ax, x, y, z, ctx: Context, *, quantity: str = "diffusivity",
                    colorbar_label: str | None = None, projection_ax=None,
                    view: tuple[float, float] | None = None, title: str | None = None,
                    xlabel: str | None = None, ylabel: str | None = None,
                    zlabel: str | None = None):
    """3D data surface, not a waterfall.  Pair it with a 2D projection."""
    x = np.asarray(x, float)
    y = np.asarray(y, float)
    z = np.asarray(z, float)
    charts.surface3d(ax, x, y, z, colorbar_label=colorbar_label or ctx.L("diffusivity"),
                     quantity=quantity, colorbar=projection_ax is None,
                     view=view or (ctx.tokens.get("surface3d") or {}).get("view"))
    ax.set_xlabel(xlabel or ctx.L("moisture_short"))
    ax.set_ylabel(ylabel or ctx.L("temperature"))
    ax.set_zlabel(zlabel or ctx.L("diffusivity_log"))
    if projection_ax is not None:
        charts.response(projection_ax, x, y, z, colorbar_label=colorbar_label or ctx.L("diffusivity"),
                        quantity=quantity)
        projection_ax.set_xlabel(xlabel or ctx.L("moisture_short"))
        projection_ax.set_ylabel(ylabel or ctx.L("temperature"))
    if title:
        ax.set_title(title, loc="left", fontweight="bold", pad=4)
    return ax


def trajectory_panel(ax, x, y, ctx: Context, *, order=None, time=None,
                     xlabel: str | None = None, ylabel: str | None = None,
                     title: str | None = None):
    """Ordered state trajectory, optionally coloured by time."""
    x = np.asarray(x, float)
    y = np.asarray(y, float)
    if order is not None:
        x, y = x[order], y[order]
        if time is not None:
            time = np.asarray(time, float)[order]
    if time is None:
        ax.plot(x, y, color=_series(ctx)[0], lw=1.4)
    else:
        t = np.asarray(time, float)
        sc = ax.scatter(x, y, c=t, cmap="viridis", s=14, zorder=2)
        ax.plot(x, y, color=_semantic(ctx, "muted"), lw=0.6, alpha=0.6, zorder=1)
        cb = ax.figure.colorbar(sc, ax=ax, label=ctx.L("time_h"), shrink=.85)
        cb.ax.yaxis.set_major_locator(mpl.ticker.MaxNLocator(nbins=5))
    ax.scatter([x[0]], [y[0]], s=30, color=_semantic(ctx, "positive"), zorder=3)
    ax.scatter([x[-1]], [y[-1]], s=30, color=_semantic(ctx, "warn"), zorder=3)
    ax.set_xlabel(xlabel or ctx.L("value"))
    ax.set_ylabel(ylabel or ctx.L("value"))
    clean(ax)
    if title:
        ax.set_title(title, loc="left", fontweight="bold", pad=4)
    return ax


def convergence_panel(ax, resolution, values, ctx: Context, *, reference: float | None = None,
                      xlabel: str | None = None, ylabel: str | None = None,
                      logx: bool = False, title: str | None = None):
    """Convergence curve with an optional reference line."""
    x = np.asarray(resolution, float)
    y = np.asarray(values, float)
    ax.plot(x, y, color=_series(ctx)[0], marker="o", ms=4, lw=1.3)
    if reference is not None:
        ax.axhline(reference, color=_semantic(ctx, "warn"), ls="--", lw=0.9)
    if logx:
        ax.set_xscale("log")
    ax.set_xlabel(xlabel or ctx.L("mesh"))
    ax.set_ylabel(ylabel or ctx.L("dry_time"))
    clean(ax)
    if title:
        ax.set_title(title, loc="left", fontweight="bold", pad=4)
    return ax


def timeline_panel(ax, events: Mapping[str, float], ctx: Context, *, title: str | None = None,
                   xlabel: str | None = None):
    """Event timeline; labels alternate above and below the axis."""
    names = list(events)
    times = [float(events[n]) for n in names]
    ax.axhline(0, color=_semantic(ctx, "line"), lw=1.0)
    for i, (name, t) in enumerate(zip(names, times)):
        ax.plot([t, t], [-0.08, 0.08], color=_series(ctx)[i % len(_series(ctx))], lw=1.2)
        ax.scatter([t], [0], s=18, color=_series(ctx)[i % len(_series(ctx))], zorder=3)
        ax.text(t, 0.15 if i % 2 == 0 else -0.22, f"{name}\n{t:g} h",
                ha="center", va="bottom" if i % 2 == 0 else "top",
                fontsize=mpl.rcParams["legend.fontsize"])
    ax.set_ylim(-0.5, 0.5)
    ax.set_yticks([])
    ax.set_xlabel(xlabel or ctx.L("time_h"))
    clean(ax, grid=None)
    for s in ax.spines.values():
        s.set_visible(False)
    if title:
        ax.set_title(title, loc="left", fontweight="bold", pad=4)
    return ax


# ---------------------------------------------------------------------------
# recipes: schematic
# ---------------------------------------------------------------------------
def cylinder_schematic(ax, radius_cm: float, profile, ctx: Context, *,
                       length_cm: float = 8.0, title: str | None = None,
                       cmap_name: str = "Blues", annotate: bool = True):
    """Longitudinal cutaway of a cylinder, mirrored moisture field, flux arrows."""
    r = np.asarray(profile, float)
    nr = len(r)
    nx, ny = 700, 240
    xs = np.linspace(0, length_cm, nx)
    ys = np.linspace(-radius_cm, radius_cm, ny)
    # r=0 at the centreline, r=radius at the wall
    rr = np.abs(ys)[:, None] / radius_cm * np.ones((1, nx))
    field = np.interp(rr.ravel(), np.linspace(0, 1, nr), r).reshape(ny, nx)
    cmap = mpl.colormaps[cmap_name]
    norm = PowerNorm(0.6, vmin=float(np.nanmin(field)), vmax=float(np.nanmax(field)))
    ax.imshow(field, extent=[0, length_cm, -radius_cm, radius_cm], origin="lower",
              aspect="auto", cmap=cmap, norm=norm, interpolation="bilinear", zorder=1)
    ax.add_patch(Rectangle((0, -radius_cm), length_cm, 2 * radius_cm, fill=False,
                           ec=_semantic(ctx, "line"), lw=1.0, zorder=3))
    ax.add_patch(patches.Ellipse((length_cm, 0), 0.45, 2 * radius_cm,
                                 fill=False, ec=_semantic(ctx, "line"), lw=0.9, zorder=3))
    if annotate:
        for x in np.linspace(1.0, length_cm - 0.8, 5):
            ax.add_patch(FancyArrowPatch((x, radius_cm), (x, radius_cm * 1.22),
                                         arrowstyle="-|>", mutation_scale=7,
                                         color=_semantic(ctx, "highlight"), lw=0.9,
                                         zorder=5, clip_on=False))
        ax.text(length_cm / 2, radius_cm * 1.30, ctx.L("evaporation_boundary"),
                ha="center", va="bottom", fontsize=mpl.rcParams["legend.fontsize"],
                color=_semantic(ctx, "highlight"))
        ax.annotate("", xy=(length_cm * 0.12, -radius_cm * 1.18),
                    xytext=(length_cm * 0.88, -radius_cm * 1.18),
                    arrowprops=dict(arrowstyle="<->", color=_semantic(ctx, "line"), lw=0.8))
        ax.text(length_cm / 2, -radius_cm * 1.30, f"{ctx.L('length')} {length_cm:g} cm",
                ha="center", va="top", fontsize=mpl.rcParams["legend.fontsize"])
        ax.annotate("", xy=(length_cm * 0.94, -radius_cm * 0.55),
                    xytext=(length_cm * 0.94, radius_cm * 0.55),
                    arrowprops=dict(arrowstyle="<->", color=_semantic(ctx, "line"), lw=0.8))
        ax.text(length_cm * 0.98, 0, f"{ctx.L('radius')} = {radius_cm:g} cm", rotation=90,
                va="center", ha="left", fontsize=mpl.rcParams["legend.fontsize"])
    ax.set_xlim(-0.6, length_cm + 0.9)
    ax.set_ylim(-radius_cm * 1.55, radius_cm * 1.55)
    ax.set_aspect("equal")
    ax.axis("off")
    if title:
        ax.set_title(title, loc="left", fontweight="bold", pad=4)
    return ax


# ---------------------------------------------------------------------------
# layout and delivery
# ---------------------------------------------------------------------------
def grid_layout(fig, *, rows: int, cols: int, **kwargs):
    """Thin wrapper for an equal-weight panel grid."""
    return fig.add_gridspec(rows, cols, **kwargs)


def hero_layout(fig, ctx: Context, *, width_mm: float | None = None,
                height_mm: float | None = None, hero_fraction: float = 0.58,
                n_evidence: int = 3):
    """Return ``(hero_rect, [evidence_rects])`` in millimetres.

    This is a planning helper, not a renderer.  Callers place their own Axes
    with :func:`axes_mm` so a hero panel can be any recipe.
    """
    w = float(width_mm or ctx.width_mm)
    h = float(height_mm or ctx.height_mm)
    margin = float((ctx.tokens.get("composition") or {}).get("margin_mm", 6.0))
    gutter = float((ctx.tokens.get("composition") or {}).get("gutter_mm", 4.0))
    hero_w = (w - 2 * margin - gutter) * hero_fraction
    side_w = w - 2 * margin - gutter - hero_w
    hero = (margin, margin, hero_w, h - 2 * margin)
    side_h = (h - 2 * margin - gutter * (n_evidence - 1)) / max(1, n_evidence)
    evidence = [(margin + hero_w + gutter, margin + i * (side_h + gutter), side_w, side_h)
                for i in range(n_evidence)]
    return hero, evidence


def plate_layout(fig, ctx: Context, *, width_mm: float | None = None,
                 height_mm: float | None = None, columns: Sequence[float] = (0.58, 0.42),
                 rows: Sequence[float] = (0.58, 0.42)):
    """Return a dict of axes factories for a simple asymmetric plate."""
    w = float(width_mm or ctx.width_mm)
    h = float(height_mm or ctx.height_mm)
    margin = float((ctx.tokens.get("composition") or {}).get("margin_mm", 6.0))
    gutter = float((ctx.tokens.get("composition") or {}).get("gutter_mm", 4.0))
    inner_w = w - 2 * margin
    inner_h = h - 2 * margin
    col_w = [(inner_w - gutter * (len(columns) - 1)) * c / sum(columns) for c in columns]
    row_h = [(inner_h - gutter * (len(rows) - 1)) * r / sum(rows) for r in rows]

    def at(row: int, col: int, **kwargs):
        x = margin + sum(col_w[:col]) + gutter * col
        y = margin + sum(row_h[row + 1:]) + gutter * (len(rows) - 1 - row)
        return axes_mm(fig, x, y, col_w[col], row_h[row],
                       width_mm=w, height_mm=h, **kwargs)

    return at


def write_source_data(root: str | Path, figure_id: str, panel: str,
                      header: Sequence[str], rows: Iterable[Sequence[object]]) -> str:
    """Write one tidy CSV per panel and return its project-relative path."""
    import re
    if not re.fullmatch(r"[a-zA-Z0-9_-]+", str(figure_id)):
        raise ValueError(f"figure id 不合法：{figure_id!r}")
    if not re.fullmatch(r"[a-zA-Z0-9_-]+", str(panel)):
        raise ValueError(f"面板 id 不合法：{panel!r}")
    root = Path(root)
    rel = Path("figures") / "source_data" / f"{figure_id}__{panel}.csv"
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(list(header))
        for row in rows:
            writer.writerow(list(row))
    return rel.as_posix()


def _write_json(path: str | Path, data) -> None:
    """Atomic JSON write (the same pattern as lib.visualization.evidence)."""
    import uuid
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def _normalise_arrays(arrays: Mapping[str, object]) -> dict:
    import re
    import numpy as _np
    clean = {}
    for name, value in arrays.items():
        name = str(name)
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
            raise ValueError(f"bundle 字段名不合法：{name!r}（只能字母/数字/_，且不以数字开头）")
        if name == "file":
            # `numpy.savez_compressed(file, **arrays)` binds `file` to its own
            # output parameter — a bundle field named `file` would raise
            # "multiple values for argument 'file'".  Make it a clear error.
            raise ValueError("bundle 字段名不能是 'file'（与 numpy.savez 的参数冲突），请改名")
        arr = _np.asarray(value)
        if arr.dtype == object:
            try:
                arr = _np.asarray(value, dtype=str)
            except Exception as exc:       # noqa: BLE001
                raise ValueError(f"bundle 字段 {name!r} 不能转成数值或字符串数组：{exc}")
            if arr.dtype == object:
                raise ValueError(f"bundle 字段 {name!r} 是 object 数组；请传数值或字符串")
        if arr.ndim == 0:
            arr = arr.reshape(1)
        clean[name] = arr
    if not clean:
        raise ValueError("bundle 至少需要一个数组")
    return clean


_RECIPES_CACHE: dict | None = None


def _recipes() -> dict:
    global _RECIPES_CACHE
    if _RECIPES_CACHE is None:
        path = _SCRIPT_DIR.parent / "assets" / "recipes.json"
        _RECIPES_CACHE = json.loads(path.read_text(encoding="utf-8"))
    return _RECIPES_CACHE


def _validate_recipe(panel: Mapping, arrays: Mapping[str, object]) -> None:
    """Check the recipe exists and the panel's field_mapping covers its required fields."""
    recipe = str(panel.get("recipe") or "").strip()
    if not recipe:
        return                       # legacy specs may omit it; check_brief still checks the brief
    data = _recipes()
    ids = {r["id"] for r in data.get("recipes", [])}
    aliases = data.get("aliases") or {}
    # Exact id wins over an alias with the same spelling (see check_brief.py).
    target = recipe if recipe in ids else aliases.get(recipe, recipe)
    if target not in ids:
        raise ValueError(
            f"面板 {panel.get('id')}: 未知 recipe {recipe!r}；见 assets/recipes.json")
    spec = next((r for r in data.get("recipes", []) if r["id"] == target), {})
    mapping = panel.get("field_mapping") or {}
    # A required field may be declared in `field_mapping` (data reference) or in
    # `options` (a presentation value such as `level`, `series_labels`).
    declared = set(mapping) | set(panel.get("options") or {})
    missing = [f for f in (spec.get("required_fields") or []) if f not in declared]
    if missing:
        raise ValueError(
            f"面板 {panel.get('id')}: recipe {recipe!r} 的 field_mapping/options 缺 {missing}")
    # `field_mapping` 的值可能是标签/数值（如 series_labels、level），所以这里只校验
    # required key 存在；真正的数组引用由 `panel.fields` 校验（上面已做），渲染器再兜底。


def _normalise_panels(panels, arrays: Mapping[str, object]) -> list[dict]:
    """Validate panel ids/fields/claims and keep presentation fields as given."""
    import re
    if isinstance(panels, Mapping):
        panels = [dict(value, id=key) for key, value in panels.items()]
    out = []
    seen = set()
    for index, raw in enumerate(panels or []):
        if not isinstance(raw, Mapping):
            raise ValueError(f"panels[{index}] 必须是对象")
        panel = dict(raw)
        pid = str(panel.get("id") or chr(ord("a") + index))
        if not re.fullmatch(r"[a-zA-Z0-9_-]+", pid):
            raise ValueError(f"面板 id 不合法：{pid!r}（只能字母/数字/_/-）")
        if pid in seen:
            raise ValueError(f"panels: 重复的面板 id {pid!r}")
        seen.add(pid)
        fields = panel.get("fields")
        if isinstance(fields, str):
            fields = [fields]
        fields = [str(f) for f in (fields or [])]
        if not fields:
            raise ValueError(f"面板 {pid}: fields 不能为空")
        missing = [f for f in fields if f not in arrays]
        if missing:
            raise ValueError(f"面板 {pid}: bundle 缺少字段 {missing}")
        claim = str(panel.get("claim") or "").strip()
        if not claim:
            raise ValueError(f"面板 {pid}: 必须写 claim（这张面板支持哪句话）")
        if "options" in panel and not isinstance(panel["options"], Mapping):
            raise ValueError(f"面板 {pid}: options 必须是对象")
        if "field_mapping" in panel and not isinstance(panel["field_mapping"], Mapping):
            raise ValueError(f"面板 {pid}: field_mapping 必须是对象")
        if panel.get("n") is not None:
            try:
                panel["n"] = int(panel["n"])
            except (TypeError, ValueError):
                raise ValueError(f"面板 {pid}: n 必须是整数或省略")
        panel["id"] = pid
        panel["fields"] = fields
        panel.setdefault("recipe", "")
        panel["claim"] = claim
        _validate_recipe(panel, arrays)
        out.append(panel)
    if not out:
        raise ValueError("至少需要一个面板")
    return out


def _default_layout(panels: Sequence[Mapping]) -> dict:
    if len(panels) == 1:
        return {"kind": "single"}
    cols = 2 if len(panels) > 1 else 1
    rows = (len(panels) + cols - 1) // cols
    return {"kind": "grid", "rows": rows, "cols": cols}


def save_bundle(root: str | Path, figure_id: str, arrays: Mapping[str, object],
                ctx: Context, *, claim: str, sources: Sequence[str],
                panels, statistics: Mapping | None = None,
                caption: str | None = None, width_mm: float | None = None,
                height_mm: float | None = None, layout: Mapping | None = None,
                units: Mapping[str, str] | None = None,
                render: Mapping | None = None,
                brief: str | None = None) -> dict:
    """④'s delivery: write ``figures/data/<id>.npz`` + ``spec/<id>.json`` + ``<id>.lock.json``.

    This is the data-layer half of the ④/⑦ split.  It writes **no canvas**:
    ⑦ owns ``figures/make_figures.py`` and the PDF/SVG/PNG.  Every numeric
    argument is saved verbatim; the lock records its hash, field shapes and
    the claim so ⑦ cannot silently change what the figure means.
    """
    import re
    import uuid
    root = Path(root)
    if not (root / "config" / "visualization.json").is_file():
        raise FileNotFoundError(
            "save_bundle needs the project root (config/visualization.json is missing).")
    if not re.fullmatch(r"[a-zA-Z0-9_-]+", figure_id):
        raise ValueError("figure id 只能是字母/数字/_/-")
    claim = str(claim or "").strip()
    if not claim:
        raise ValueError("claim 不能为空：图必须支持一句可检验的话")
    clean = _normalise_arrays(arrays)
    normalised = _normalise_panels(panels, clean)
    if layout is not None and not isinstance(layout, Mapping):
        raise ValueError("layout 必须是对象（如 {'kind':'grid','rows':1,'cols':2}）")
    if render is not None and not isinstance(render, Mapping):
        raise ValueError("render 必须是对象")
    if statistics is not None and not isinstance(statistics, Mapping):
        raise ValueError("statistics 必须是对象")
    stats = dict(statistics or {})
    stats.setdefault("interval", {"kind": "none", "method": "不适用"})
    stats.setdefault("test", {"kind": "none", "p_values": False})
    stats.setdefault("unit", "")
    stats.setdefault("paired", False)
    width = float(width_mm or ctx.width_mm)
    height = float(height_mm or ctx.height_mm)
    if width <= 0 or height <= 0:
        raise ValueError("width_mm/height_mm 必须是正数")
    if units is not None and not isinstance(units, Mapping):
        raise ValueError("units 必须是对象（字段名 -> 单位）")
    unit_map = {str(k): str(v) for k, v in (units or {}).items()}
    if isinstance(sources, (str, Path)):
        sources = [str(sources)]
    data_path = root / "figures" / "data" / f"{figure_id}.npz"
    data_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = data_path.with_name(data_path.name + "." + uuid.uuid4().hex + ".tmp.npz")
    np.savez_compressed(tmp, **clean)
    tmp.replace(data_path)

    spec = {
        "schema_version": 2,
        "figure_id": figure_id,
        "language": ctx.language,
        "template": ctx.template,
        "width_mm": width,
        "height_mm": height,
        "claim": claim,
        "caption": str(caption or claim),
        "statistics": stats,
        "data": {
            "path": f"figures/data/{figure_id}.npz",
            "fields": {name: {"unit": unit_map.get(name, "")} for name in clean},
        },
        "sources": list(dict.fromkeys(str(s).replace("\\", "/") for s in sources)),
        "layout": dict(layout) if layout else _default_layout(normalised),
        "panels": normalised,
        "render": dict(render) if render else {
            "mode": "declarative", "script": "figures/make_figures.py"},
    }
    spec_path = root / "figures" / "spec" / f"{figure_id}.json"
    _write_json(spec_path, spec)

    # The lock module is deliberately dependency-free (NumPy + stdlib); import
    # it lazily so ``studio.py`` keeps working when only rendering.
    import figure_lock
    lock = figure_lock.build(root, figure_id,
                             spec_path=f"figures/spec/{figure_id}.json",
                             brief_path=brief)
    return {"data": f"figures/data/{figure_id}.npz",
            "spec": f"figures/spec/{figure_id}.json",
            "lock": f"figures/{figure_id}.lock.json",
            "lock_data": lock}


def _check_figure_id(figure_id: str) -> str:
    import re
    figure_id = str(figure_id)
    if not re.fullmatch(r"[a-zA-Z0-9_-]+", figure_id):
        raise ValueError(f"figure id 不合法：{figure_id!r}")
    return figure_id


def load_bundle(root: str | Path, figure_id: str) -> dict:
    """Read the read-only data bundle ④ produced."""
    figure_id = _check_figure_id(figure_id)
    path = Path(root) / "figures" / "data" / f"{figure_id}.npz"
    if not path.is_file():
        raise FileNotFoundError(f"数据 bundle 不存在：{path}")
    with np.load(path, allow_pickle=False) as bundle:
        return {name: bundle[name].copy() for name in bundle.files}


def load_spec(root: str | Path, figure_id: str) -> dict | None:
    figure_id = _check_figure_id(figure_id)
    path = Path(root) / "figures" / "spec" / f"{figure_id}.json"
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None


def load_lock(root: str | Path, figure_id: str) -> dict | None:
    figure_id = _check_figure_id(figure_id)
    path = Path(root) / "figures" / f"{figure_id}.lock.json"
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None


def lock_sources(root: str | Path, figure_id: str) -> list[str]:
    """Manifest sources for a decoupled figure: bundle + spec + lock + original sources."""
    lock = load_lock(root, figure_id)
    if not lock:
        return []
    rels = []
    for rel in ((lock.get("data") or {}).get("path"),
                (lock.get("spec") or {}).get("path"),
                f"figures/{figure_id}.lock.json"):
        if rel and rel not in rels:
            rels.append(str(rel))
    for rel in (lock.get("sources") or {}):
        if rel not in rels:
            rels.append(str(rel))
    return rels


def save_figure(fig, root: str | Path, figure_id: str, ctx: Context, settings: Mapping,
                *, sources: Sequence[str], script: str, claim: str, caption: str,
                source_data: Mapping[str, tuple[Sequence[str], Iterable[Sequence[object]]]] | None = None,
                meta: Mapping | None = None):
    """Export PDF/SVG/PNG, register, and write the source-data/meta sidecars."""
    root = Path(root)
    if not (root / "config" / "visualization.json").is_file():
        raise FileNotFoundError(
            "save_figure needs the project root (config/visualization.json is missing). "
            "Run from the project tree; a standalone demo must copy that config first."
        )
    if isinstance(sources, (str, Path)):
        sources = [str(sources)]
    sources = list(dict.fromkeys(str(s) for s in sources))
    if script:
        script_path = (root / script).resolve()
        if not script_path.is_relative_to(root.resolve()):
            raise ValueError(f"渲染脚本越界：{script}")
        if not script_path.is_file():
            raise FileNotFoundError(
                f"渲染脚本不存在：{script}。⑦ 要先写 figures/make_figures.py，再登记；"
                "否则 manifest 的快照没有可哈希的脚本，登记到一半会失败。")
    # Decoupled figures: refuse to render if the data layer was changed without
    # re-cutting the lock, or if ⑦ tries to replace the claim.  This is the
    # single enforcement point for "⑦ must not touch the data/claim".
    lock_path = root / "figures" / f"{figure_id}.lock.json"
    has_bundle = (root / "figures" / "data" / f"{figure_id}.npz").is_file()
    has_spec = (root / "figures" / "spec" / f"{figure_id}.json").is_file()
    if lock_path.is_file():
        lock = load_lock(root, figure_id)
        if not isinstance(lock, dict) or not lock:
            raise ValueError(f"figure lock 不可读：figures/{figure_id}.lock.json")
        import figure_lock as _lock
        problems = [i for i in _lock.verify_one(root, figure_id, check_meta=False)
                    if i["kind"] in ("data", "contract")]
        if problems:
            raise ValueError(
                "figure lock 不通过，拒绝渲染（先修数据层/契约）：\n" +
                "\n".join(_lock.format_issue(i) for i in problems))
        if str(lock.get("claim") or "").strip() != str(claim or "").strip():
            raise ValueError("claim 与 figure lock 不一致；⑦ 只能改 caption/画法，不能改 claim")
        sources.extend(lock_sources(root, figure_id))
    elif has_bundle or has_spec:
        raise ValueError(
            f"有 figures/data 或 figures/spec，但没有 figures/{figure_id}.lock.json；"
            "④ 未交付数据锁，拒绝渲染。先运行 studio.save_bundle 或 figure_lock build。")
    else:
        lock = None
    # The shared skill is a real dependency of the pixels: record it when the
    # figure lives inside the project.  (The demo gallery is outside the
    # project tree and copies nothing, so it skips these entries.)
    for rel in (
        "skills/figure-studio/scripts/studio.py",
        "skills/figure-studio/scripts/resolve_context.py",
        "skills/figure-studio/assets/style.tokens.json",
        f"skills/figure-studio/assets/labels.{ctx.language}.json",
    ):
        if (root / rel).is_file():
            sources.append(rel)
    source_rows = {}
    if source_data:
        for panel, (header, rows) in source_data.items():
            rel = write_source_data(root, figure_id, panel, header, rows)
            sources.append(rel)
            try:
                with (root / rel).open("r", encoding="utf-8-sig", newline="") as fh:
                    source_rows[panel] = max(0, sum(1 for _ in csv.reader(fh)) - 1)
            except OSError:
                source_rows[panel] = 0
    sources = list(dict.fromkeys(sources))
    entry = _export(
        fig, root, figure_id, sources=sources, script=script,
        claim=claim, caption=caption, settings=dict(settings),
    )
    actual_width = float(fig.get_figwidth() * 25.4)
    actual_height = float(fig.get_figheight() * 25.4)
    sidecar = {
        "schema_version": 1,
        "figure_id": figure_id,
        "language": ctx.language,
        "template": ctx.template,
        "width_mm": actual_width,
        "height_mm": actual_height,
        "font": ctx.font,
        "claim": claim,
        "caption": caption,
        "source_data": {k: f"figures/source_data/{figure_id}__{k}.csv" for k in (source_data or {})},
        "counts": source_rows,
        "intervals": "未声明（请在 meta 中补区间类型/方法/水平）",
        "exclusions": "未声明（请在 meta 中补排除规则）",
    }
    if meta:
        sidecar.update(meta)
    # These are contract fields, not caller-overridable presentation fields.
    sidecar["figure_id"] = figure_id
    sidecar["claim"] = claim
    sidecar["language"] = ctx.language
    sidecar["template"] = ctx.template
    if lock:
        sidecar.setdefault("spec", f"figures/spec/{figure_id}.json")
        sidecar.setdefault("figure_lock", f"figures/{figure_id}.lock.json")
        sidecar.setdefault("data", f"figures/data/{figure_id}.npz")
    # The rendered size is a fact, not a caller-supplied label.
    sidecar["width_mm"] = actual_width
    sidecar["height_mm"] = actual_height
    out = root / "figures" / f"{figure_id}.meta.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(sidecar, ensure_ascii=False, indent=2), encoding="utf-8")
    return entry
# ---------------------------------------------------------------------------
# spec renderer: the default ⑦ implementation for declarative figures
# ---------------------------------------------------------------------------
_AXES_RECIPES = {
    "field-contour": "field_contour", "contour-field": "field_contour",
    "field_contour": "field_contour",
    "field-heatmap": "field_heatmap", "heatmap-field": "field_heatmap",
    "field_heatmap": "field_heatmap",
    "profiles": "profiles", "profile": "profiles",
    "trend-line": "profiles", "trend_line": "profiles",
    "parameter-sweep": "profiles", "parameter_sweep": "profiles",
    "paired-raincloud": "paired_raincloud", "paired_raincloud": "paired_raincloud",
    "paired-dumbbell": "paired_dumbbell", "paired_dumbbell": "paired_dumbbell",
    "distribution-box": "distribution_box", "distribution_box": "distribution_box",
    "horizontal-dot-interval": "dot_interval", "dot-interval": "dot_interval",
    "forest-plot": "dot_interval", "forest_plot": "dot_interval",
    "sensitivity-dot": "dot_interval", "sensitivity_dot": "dot_interval",
    "dot_interval": "dot_interval",
    "grouped-bars": "grouped_bars", "grouped_bars": "grouped_bars",
    "ablation-bars": "grouped_bars", "ablation_bars": "grouped_bars",
    "multi-metric-bar-panel": "grouped_bars", "multi_metric_bar_panel": "grouped_bars",
    "log-scale-bars": "grouped_bars", "log_scale_bars": "grouped_bars",
    "stacked-composition": "stacked_composition", "stacked_composition": "stacked_composition",
    "correlation-matrix": "correlation_matrix", "correlation_matrix": "correlation_matrix",
    "matrix-heatmap": "heatmap", "matrix_heatmap": "heatmap", "heatmap": "heatmap",
    "table-heatmap": "heatmap", "table_heatmap": "heatmap",
    "signed-error-heatmap": "heatmap", "signed_error_heatmap": "heatmap",
    "composition-heatmap": "heatmap", "composition_heatmap": "heatmap",
    "roc-curve": "roc_curve", "roc_curve": "roc_curve", "roc": "roc_curve",
    "taylor-diagram": "taylor", "taylor_diagram": "taylor", "taylor": "taylor",
    "radar": "radar",
    "surface3d-response": "surface3d", "surface3d": "surface3d",
    "trajectory-2d": "trajectory", "trajectory_2d": "trajectory", "trajectory": "trajectory",
    "convergence": "convergence",
    "timeline": "timeline",
    "cylinder-schematic": "cylinder", "cylinder_schematic": "cylinder",
}
_CUSTOM_ONLY = {
    "scatter-matrix", "scatter_matrix", "correlation-pairgrid",
    "marginal-joint-scatter", "prediction-marginal", "prediction_marginal",
    "shap-combo", "shap_combo",
    "split-violin-corr-matrix", "split_violin_corr_matrix", "circular-heatmap",
    "circular_heatmap", "distribution-composite", "distribution_composite",
    "chord-diagram", "chord_diagram", "roc-curve-ci", "roc_curve_ci",
    "hero-evidence", "hero_evidence", "quantitative-grid", "quantitative_grid",
    "plate", "diagnostic-strip", "diagnostic_strip",
    "small-multiples", "small_multiples",
    "distribution-violin", "distribution_violin", "distribution-strip",
    "distribution_strip", "ecdf", "ridgeline", "decomposition-stl",
    "feature-importance", "feature_importance", "streamfield",
    "schematic-generic", "schematic_generic",
}


def _recipe_name(panel: Mapping) -> str:
    return str(panel.get("recipe") or "").strip().lower()


def _panel_value(panel: Mapping, key: str, index: int) -> str:
    mapping = panel.get("field_mapping") or {}
    value = mapping.get(key)
    if value is None:
        fields = list(panel.get("fields") or [])
        value = fields[index] if index < len(fields) else None
    if value is None:
        raise ValueError(f"面板 {panel.get('id')}: 缺少字段映射 {key!r}（fields={panel.get('fields')}）")
    if isinstance(value, (list, tuple)):
        raise ValueError(f"面板 {panel.get('id')}: {key!r} 需要单个字段，得到 {value!r}")
    return str(value)


def _strings(panel: Mapping, bundle: Mapping, key: str, default=None, required=True):
    options = panel.get("options") or {}
    value = options.get(key)
    if value is None:
        mapping = panel.get("field_mapping") or {}
        value = mapping.get(key)
        if isinstance(value, str) and value in bundle:
            value = bundle[value]
    if value is None:
        value = default
    if value is None:
        if required:
            raise ValueError(f"面板 {panel.get('id')}: 缺少 {key!r}（写在 options 或 bundle 字段里）")
        return []
    return [str(x) for x in (value if isinstance(value, (list, tuple, np.ndarray)) else [value])]


def _series_map(panel: Mapping, bundle: Mapping, key: str = "series") -> dict:
    mapping = panel.get("field_mapping") or {}
    names = mapping.get(key)
    if names is None:
        names = list(panel.get("fields") or [])[1:]
    if isinstance(names, str):
        names = [names]
    names = [str(n) for n in names]
    options = panel.get("options") or {}
    labels = options.get("series_labels") or names
    if isinstance(labels, str):
        labels = [labels]
    if len(labels) != len(names):
        raise ValueError(f"面板 {panel.get('id')}: series_labels 与 series 长度不一致")
    missing = [n for n in names if n not in bundle]
    if missing:
        raise ValueError(f"面板 {panel.get('id')}: bundle 缺少 series 字段 {missing}")
    return {str(label): bundle[name] for label, name in zip(labels, names)}


def _render_panel(ax, panel: Mapping, bundle: Mapping, ctx: Context) -> None:
    recipe = _recipe_name(panel)
    alias = _AXES_RECIPES.get(recipe)
    if alias is None:
        if recipe in _CUSTOM_ONLY:
            raise ValueError(
                f"recipe {recipe!r} 需要图级自定义渲染；在 spec 里写 "
                f'"render": {{"mode": "custom"}}，由 figures/make_figures.py 处理')
        raise ValueError(f"未知 recipe {recipe!r}；见 assets/recipes.json")
    options = dict(panel.get("options") or {})
    title = panel.get("title")

    if alias in ("field_contour", "field_heatmap"):
        x = bundle[_panel_value(panel, "x", 0)]
        y = bundle[_panel_value(panel, "y", 1)]
        z = bundle[_panel_value(panel, "z", 2)]
        field_panel(ax, x, y, z, ctx,
                    kind="contour" if alias == "field_contour" else "heatmap",
                    quantity=str(options.get("quantity") or "moisture"),
                    colorbar_label=options.get("colorbar_label"),
                    level=options.get("level"),
                    level_label=options.get("level_label"),
                    gamma=options.get("gamma"),
                    vmin=options.get("vmin"), vmax=options.get("vmax"),
                    title=title)
        return
    if alias == "profiles":
        x = bundle[_panel_value(panel, "x", 0)]
        profile_panel(ax, x, _series_map(panel, bundle), ctx,
                      xlabel=options.get("xlabel"), ylabel=options.get("ylabel"),
                      logy=bool(options.get("logy")), direct=bool(options.get("direct", True)),
                      markers=bool(options.get("markers")), legend=bool(options.get("legend")),
                      title=title)
        return
    if alias in ("paired_raincloud", "paired_dumbbell"):
        before = bundle[_panel_value(panel, "before", 0)]
        after = bundle[_panel_value(panel, "after", 1)]
        labels = options.get("labels") or [ctx.L("before"), ctx.L("after")]
        if alias == "paired_raincloud":
            paired_raincloud(ax, before, after, ctx, labels=labels,
                             xlabel=options.get("xlabel"), ylabel=options.get("ylabel"),
                             title=title, seed=int(options.get("seed", 0)))
        else:
            paired_dumbbell(ax, before, after, ctx, labels=labels,
                            ylabel=options.get("ylabel"), title=title)
        return
    if alias == "distribution_box":
        names = options.get("groups") or list(panel.get("fields") or [])
        if isinstance(names, str):
            names = [names]
        missing = [n for n in names if n not in bundle]
        if missing:
            raise ValueError(f"面板 {panel.get('id')}: 分布组缺少字段 {missing}")
        distribution_box(ax, {str(n): bundle[n] for n in names}, ctx,
                         ylabel=options.get("ylabel"), xlabel=options.get("xlabel"),
                         logy=bool(options.get("logy")), title=title)
        return
    if alias == "dot_interval":
        labels = _strings(panel, bundle, "labels", default=list(panel.get("fields") or []))
        values = bundle[_panel_value(panel, "values", 0)]
        low = high = None
        mapping = panel.get("field_mapping") or {}
        if mapping.get("low") or options.get("low"):
            low = bundle[str(mapping.get("low") or options["low"])]
        if mapping.get("high") or options.get("high"):
            high = bundle[str(mapping.get("high") or options["high"])]
        dot_interval(ax, labels, values, low, high, ctx,
                     reference=options.get("reference"),
                     xlabel=options.get("xlabel"), title=title,
                     groups=options.get("groups"),
                     sort=bool(options.get("sort", True)),
                     value_fmt=str(options.get("value_fmt", "{:.2f}")),
                     value_labels=bool(options.get("value_labels", True)))
        return
    if _recipe_name(panel) in ("ablation-bars", "ablation_bars"):
        labels = _strings(panel, bundle, "labels",
                          default=list(panel.get("fields") or []))
        values = bundle[_panel_value(panel, "values", 0)]
        grouped_bars(ax, labels,
                     {str(options.get("series_label") or ctx.L("value")): values},
                     ctx, horizontal=True, title=title,
                     value_fmt=str(options.get("value_fmt", "{:.2f}")),
                     value_labels=bool(options.get("value_labels", True)))
        return
    if alias == "grouped_bars":
        categories = _strings(panel, bundle, "categories")
        grouped_bars(ax, categories, _series_map(panel, bundle), ctx,
                     ylabel=options.get("ylabel"), xlabel=options.get("xlabel"),
                     horizontal=bool(options.get("horizontal")),
                     title=title, value_fmt=str(options.get("value_fmt", "{:.2f}")),
                     hatches=bool(options.get("hatches", True)),
                     value_labels=bool(options.get("value_labels", True)))
        return
    if alias == "stacked_composition":
        categories = _strings(panel, bundle, "categories")
        stacked_composition(ax, categories, _series_map(panel, bundle, "components"), ctx,
                            ylabel=options.get("ylabel"), title=title,
                            normalize=bool(options.get("normalize")),
                            legend=bool(options.get("legend", True)))
        return
    if alias == "correlation_matrix":
        variables = _strings(panel, bundle, "variables", default=list(panel.get("fields") or []))
        matrix = bundle[_panel_value(panel, "matrix", 0)]
        correlation_matrix(ax, variables, matrix, ctx,
                           lower=bool(options.get("lower", True)), title=title,
                           colorbar_label=options.get("colorbar_label"))
        return
    if alias == "heatmap":
        rows = _strings(panel, bundle, "rows")
        columns = _strings(panel, bundle, "columns")
        values = bundle[_panel_value(panel, "values", 0)]
        heatmap_panel(ax, values, rows, columns, ctx,
                      colorbar_label=options.get("colorbar_label"),
                      quantity=options.get("quantity"),
                      correlation=bool(options.get("correlation")),
                      annotate=options.get("annotate"), title=title)
        return
    if alias == "roc_curve":
        mapping = panel.get("field_mapping") or {}
        specs = options.get("curves") or []
        if not specs:
            raise ValueError(f"面板 {panel.get('id')}: roc_curve 需要 options.curves")
        curves = {}
        for item in specs:
            name = str(item.get("name") or item.get("model") or "曲线")
            y_true = item.get("y_true") or mapping.get("y_true")
            y_score = item.get("y_score") or mapping.get("y_score")
            if not y_true or not y_score:
                raise ValueError(f"面板 {panel.get('id')}: ROC {name} 缺少 y_true/y_score")
            curves[name] = (bundle[str(y_true)], bundle[str(y_score)])
        roc_panel(ax, curves, ctx, title=title)
        return
    if alias == "taylor":
        models = _strings(panel, bundle, "models")
        correlation = bundle[_panel_value(panel, "correlation", 0)]
        std_ratio = bundle[_panel_value(panel, "std_ratio", 1)]
        taylor_panel(ax, models, correlation, std_ratio, ctx,
                     title=title, label_points=bool(options.get("label_points", True)))
        return
    if alias == "radar":
        categories = _strings(panel, bundle, "categories",
                              default=(panel.get("options") or {}).get("metrics"))
        radar_panel(ax, categories, _series_map(panel, bundle), ctx,
                    normalize=bool(options.get("normalize")), title=title,
                    legend=bool(options.get("legend", True)))
        return
    if alias == "surface3d":
        x = bundle[_panel_value(panel, "x", 0)]
        y = bundle[_panel_value(panel, "y", 1)]
        z = bundle[_panel_value(panel, "z", 2)]
        surface3d_panel(ax, x, y, z, ctx,
                        quantity=str(options.get("quantity") or "diffusivity"),
                        colorbar_label=options.get("colorbar_label"),
                        view=tuple(options["view"]) if options.get("view") else None,
                        title=title, xlabel=options.get("xlabel"),
                        ylabel=options.get("ylabel"), zlabel=options.get("zlabel"))
        return
    if alias == "trajectory":
        mapping = panel.get("field_mapping") or {}
        x = bundle[_panel_value(panel, "x", 0)]
        y = bundle[_panel_value(panel, "y", 1)]
        order_field = options.get("order") or mapping.get("path_order")
        time_field = options.get("time") or mapping.get("time")
        order = bundle[str(order_field)] if order_field and str(order_field) in bundle else None
        time = bundle[str(time_field)] if time_field and str(time_field) in bundle else None
        trajectory_panel(ax, x, y, ctx, order=order, time=time,
                         xlabel=options.get("xlabel"), ylabel=options.get("ylabel"),
                         title=title)
        return
    if alias == "convergence":
        resolution = bundle[_panel_value(panel, "resolution", 0)]
        values = bundle[_panel_value(panel, "values", 1)]
        convergence_panel(ax, resolution, values, ctx,
                          reference=options.get("reference"),
                          xlabel=options.get("xlabel"), ylabel=options.get("ylabel"),
                          logx=bool(options.get("logx")), title=title)
        return
    if alias == "timeline":
        mapping = panel.get("field_mapping") or {}
        opts_events = options.get("events")
        if isinstance(opts_events, dict):
            events = {str(k): float(v) for k, v in opts_events.items()}
        else:
            labels_field = (opts_events or mapping.get("events")
                            or mapping.get("labels") or options.get("labels"))
            times_field = options.get("times") or mapping.get("times")
            if not (labels_field and times_field
                    and str(labels_field) in bundle and str(times_field) in bundle):
                raise ValueError(
                    f"面板 {panel.get('id')}: timeline 需要 options.events 字典，"
                    "或 field_mapping 同时给出 labels/events 与 times")
            events = {str(name): float(t)
                      for name, t in zip(bundle[str(labels_field)], bundle[str(times_field)])}
        timeline_panel(ax, events, ctx, title=title, xlabel=options.get("xlabel"))
        return
    if alias == "cylinder":
        radius = float(options.get("radius_cm") or 0.5)
        profile = bundle[_panel_value(panel, "profile", 0)]
        cylinder_schematic(ax, radius, profile, ctx,
                           length_cm=float(options.get("length_cm", 8.0)), title=title)
        return
    raise ValueError(f"未接线的 recipe {recipe!r}")


def _panel_source_data(panel: Mapping, bundle: Mapping):
    """A generic tidy CSV for a declarative panel.

    ⑦ may pass its own ``source_data`` for transformed panels; this covers the
    direct field-to-axes case so every declarative figure has traceable numbers.
    """
    names = [str(f) for f in (panel.get("fields") or []) if str(f) in bundle]
    if not names:
        return None
    arrays = [np.asarray(bundle[name]) for name in names]
    if all(a.ndim == 1 for a in arrays) and len({a.shape[0] for a in arrays}) == 1:
        header = names
        rows = zip(*[a.tolist() for a in arrays])
        return {str(panel.get("id") or "a"): (header, rows)}
    if (len(arrays) == 3 and arrays[0].ndim == 1 and arrays[1].ndim == 1
            and arrays[2].ndim == 2 and arrays[2].shape == (len(arrays[1]), len(arrays[0]))):
        x, y, z = arrays
        header = names
        rows = ((x[j].item() if hasattr(x[j], "item") else x[j],
                 y[i].item() if hasattr(y[i], "item") else y[i],
                 z[i, j].item() if hasattr(z[i, j], "item") else z[i, j])
                for i in range(len(y)) for j in range(len(x)))
        return {str(panel.get("id") or "a"): (header, rows)}
    header = ["index"] + names
    total = max(int(a.size) for a in arrays)
    rows = []
    for k in range(total):
        row = [k]
        for a in arrays:
            flat = a.reshape(-1)
            row.append(flat[k].item() if k < flat.size and hasattr(flat[k], "item") else
                       (flat[k] if k < flat.size else ""))
        rows.append(row)
    return {str(panel.get("id") or "a"): (header, rows)}


def _axes_for(fig, panel: Mapping, layout: Mapping, index: int, ctx: Context,
              width_mm: float, height_mm: float):
    recipe = _AXES_RECIPES.get(_recipe_name(panel))
    projection = panel.get("projection")
    if projection is None:
        projection = "polar" if recipe == "radar" else ("3d" if recipe == "surface3d" else None)
    kind = str(layout.get("kind") or "grid")
    if kind not in {"single", "grid", "mm"}:
        raise ValueError(f"未知 layout.kind={kind!r}；支持 single/grid/mm")
    if kind == "mm":
        box = panel.get("axes_mm")
        if not box or len(box) != 4:
            raise ValueError(f"面板 {panel.get('id')}: layout.kind=mm 需要 axes_mm=[x,y,w,h]")
        kwargs = {"projection": projection} if projection else {}
        return axes_mm(fig, float(box[0]), float(box[1]), float(box[2]), float(box[3]),
                       width_mm=width_mm, height_mm=height_mm, **kwargs)
    if kind == "single":
        if index > 0:
            raise ValueError("layout.kind=single 只能有一个面板")
        kwargs = {"projection": projection} if projection else {}
        return fig.add_subplot(111, **kwargs)
    rows = int(layout.get("rows") or 1)
    cols = int(layout.get("cols") or 1)
    gs = fig.add_gridspec(rows, cols, left=0.09, right=0.95, top=0.90, bottom=0.12,
                          wspace=0.42, hspace=0.52)
    kwargs = {"projection": projection} if projection else {}
    return fig.add_subplot(gs[index // cols, index % cols], **kwargs)


def render_spec(spec: Mapping, root: str | Path, ctx: Context | None = None):
    """Render one declarative figure from its bundle + spec.

    This is the default implementation of ⑦'s renderer.  It never writes
    ``figures/data`` / ``spec`` / ``lock``; it reads the bundle and hands the
    pixels to ``save_figure``.  Specs that need a bespoke composition set
    ``render.mode = "custom"`` and are handled by ``figures/make_figures.py``.
    """
    import re
    root = Path(root)
    spec = dict(spec)
    figure_id = str(spec.get("figure_id") or "")
    if not figure_id:
        raise ValueError("spec.figure_id 为空")
    if not re.fullmatch(r"[a-zA-Z0-9_-]+", figure_id):
        raise ValueError(f"spec.figure_id 不合法：{figure_id!r}")
    render = spec.get("render") or {}
    if not isinstance(render, Mapping):
        raise ValueError(f"{figure_id}: spec.render 必须是对象")
    if str(render.get("mode") or "declarative") != "declarative":
        raise ValueError(f"{figure_id}: render.mode={render.get('mode')!r}，请交给自定义渲染器")
    ctx = ctx or context(root, template=spec.get("template"))
    bundle = load_bundle(root, figure_id)
    width = float(spec.get("width_mm") or ctx.width_mm)
    height = float(spec.get("height_mm") or ctx.height_mm)
    layout = spec.get("layout") or _default_layout(spec.get("panels") or [])
    if not isinstance(layout, Mapping):
        raise ValueError(f"{figure_id}: spec.layout 必须是对象")
    panels = [p for p in (spec.get("panels") or []) if isinstance(p, dict)]
    if not panels:
        raise ValueError(f"{figure_id}: spec.panels 为空")
    if str(layout.get("kind") or "grid") == "grid":
        # `{"kind":"grid"}` without rows/cols used to put every panel in cell
        # (0,0) — they silently overlapped.  Fill the auto grid from panel count.
        layout = dict(layout)
        auto = _default_layout(panels)
        layout.setdefault("rows", auto.get("rows", 1))
        layout.setdefault("cols", auto.get("cols", 1))
        if not layout.get("rows") or not layout.get("cols"):
            layout["rows"], layout["cols"] = auto.get("rows", 1), auto.get("cols", 1)
        try:
            _rows, _cols = int(layout["rows"]), int(layout["cols"])
        except (TypeError, ValueError):
            raise ValueError(f"{figure_id}: layout.rows/cols 必须是整数")
        if _rows * _cols < len(panels):
            raise ValueError(
                f"{figure_id}: layout grid {_rows}×{_cols} 放不下 {len(panels)} 个面板")
    panel_ids = []
    for index, panel in enumerate(panels):
        if isinstance(panel.get("fields"), str):
            panel["fields"] = [panel["fields"]]
        if "field_mapping" in panel and not isinstance(panel["field_mapping"], Mapping):
            raise ValueError(f"{figure_id}: 面板 field_mapping 必须是对象")
        if "options" in panel and not isinstance(panel["options"], Mapping):
            raise ValueError(f"{figure_id}: 面板 options 必须是对象")
        pid = str(panel.get("id") or chr(ord("a") + index))
        panel["id"] = pid
        if not re.fullmatch(r"[a-zA-Z0-9_-]+", pid):
            raise ValueError(f"{figure_id}: 面板 id 不合法：{pid!r}")
        panel_ids.append(pid)
    if len(panel_ids) != len(set(panel_ids)):
        raise ValueError(f"{figure_id}: 面板 id 重复：{panel_ids}")
    with style(ctx, width_mm=width) as settings:
        fig = canvas(ctx, width_mm=width, height_mm=height, constrained=False)
        source_data = {}
        for index, panel in enumerate(panels):
            ax = _axes_for(fig, panel, layout, index, ctx, width, height)
            _render_panel(ax, panel, bundle, ctx)
            if panel.get("title") or panel.get("id"):
                panel_label(fig, ax, str(panel.get("id") or chr(ord("a") + index)),
                            ctx, panel.get("title"))
            data = _panel_source_data(panel, bundle)
            if data:
                source_data.update(data)
        stats = spec.get("statistics") or {}
        if not isinstance(stats, dict):
            stats = {}
        interval = stats.get("interval") or {}
        if not isinstance(interval, dict):
            interval = {}
        if str(interval.get("kind") or "none") == "none":
            interval_text = "无（未显示区间）" if ctx.language == "zh" else "none (no interval shown)"
        else:
            interval_text = (f"{interval.get('kind')}（{interval.get('method') or '未写方法'}）"
                             if ctx.language == "zh"
                             else f"{interval.get('kind')} ({interval.get('method') or 'method not stated'})")
        exclusions = spec.get("exclusions")
        if not exclusions:
            exclusions = "无" if ctx.language == "zh" else "none"
        meta = {
            "intervals": interval_text,
            "exclusions": str(exclusions),
            "spec": f"figures/spec/{figure_id}.json",
            "figure_lock": f"figures/{figure_id}.lock.json",
            "data": f"figures/data/{figure_id}.npz",
        }
        spec_sources = spec.get("sources")
        if isinstance(spec_sources, (str, Path)):
            spec_sources = [str(spec_sources)]
        sources = lock_sources(root, figure_id) or list(spec_sources or [])
        caption = str(spec.get("caption") or spec.get("claim") or "")
        try:
            entry = save_figure(
                fig, root, figure_id, ctx, settings,
                sources=sources,
                script=str(render.get("script") or "figures/make_figures.py"),
                claim=str(spec.get("claim") or ""),
                caption=caption,
                source_data=source_data,
                meta=meta,
            )
        finally:
            plt.close(fig)
        return entry


def render_specs(root: str | Path, figures: Sequence[str] | None = None,
                 ctx: Context | None = None) -> list[dict]:
    """Render every declarative spec (or the selected ids) under ``figures/spec``."""
    root = Path(root)
    spec_dir = root / "figures" / "spec"
    if not spec_dir.is_dir():
        return []
    out = []
    # `None` = render all; an explicit empty list = render none (the caller
    # already determined that every spec failed its lock).
    if isinstance(figures, (str, Path)):
        figures = [str(figures)]
    wanted = None if figures is None else set(figures)
    for path in sorted(spec_dir.glob("*.json")):
        try:
            spec = load_spec(root, path.stem)
        except ValueError as exc:
            print(f"skip {path.stem}: {exc}", flush=True)
            continue
        if not spec:
            continue
        if wanted is not None and path.stem not in wanted:
            continue
        render = spec.get("render") or {}
        mode = render.get("mode") if isinstance(render, Mapping) else "declarative"
        if str(mode or "declarative") != "declarative":
            print(f"skip {path.stem}: render.mode=custom", flush=True)
            continue
        spec_ctx = ctx or context(root, template=spec.get("template"))
        out.append(render_spec(spec, root, spec_ctx))
    return out


# ---------------------------------------------------------------------------
# recipes: six generic templates in the data-recipe-library module
# ---------------------------------------------------------------------------
def shap_combo(fig, features: Sequence[str], contributions, feature_values=None,
               ctx: Context | None = None, *, class_index: int = 0, top_n: int = 10,
               title: str | None = None, seed: int = 0):
    """Two-panel attribution view: mean |contribution| bars + beeswarm.

    ``contributions`` is ``(n_samples, n_features)`` or
    ``(n_samples, n_features, n_classes)``.  ``feature_values`` has the same
    first two dimensions; when omitted, colour encodes the signed contribution.
    """
    if ctx is None:
        raise ValueError("shap_combo needs the context (ctx)")
    c = np.asarray(contributions, float)
    if c.ndim == 3:
        c = c[:, :, int(class_index)]
    if c.ndim != 2 or c.shape[1] != len(features):
        raise ValueError("contributions must be (n_samples, n_features[, n_classes])")
    if feature_values is None:
        fv = None
    else:
        fv = np.asarray(feature_values, float)
        if fv.ndim == 3:
            fv = fv[:, :, int(class_index)]
        if fv.shape != c.shape:
            raise ValueError("feature_values must match contributions")
    importance = np.mean(np.abs(c), axis=0)
    order = np.argsort(importance)[::-1][:max(1, int(top_n))]
    gs = fig.add_gridspec(1, 2, width_ratios=[1.0, 1.65], wspace=0.08)
    ax_bar = fig.add_subplot(gs[0, 0])
    ax_swarm = fig.add_subplot(gs[0, 1])
    cols = _series(ctx)
    y = np.arange(len(order))
    ax_bar.barh(y, importance[order], color=cols[0], edgecolor=_semantic(ctx, "ink"), linewidth=0.5)
    ax_bar.set_yticks(y, [features[i] for i in order])
    ax_bar.invert_yaxis()
    ax_bar.set_xlabel(ctx.L("importance"))
    clean(ax_bar, grid="x")

    rng = np.random.default_rng(seed)
    if fv is None:
        vmax = max(1e-12, float(np.nanmax(np.abs(c[:, order]))))
        cmap = mpl.colormaps["RdBu_r"]
        norm = mpl.colors.Normalize(-vmax, vmax)
        color_label = ctx.L("contribution")
    else:
        cmap = mpl.colormaps["coolwarm"]
        norm = mpl.colors.Normalize(float(np.nanmin(fv[:, order])),
                                    float(np.nanmax(fv[:, order])))
        color_label = ctx.L("value")
    for rank, fi in enumerate(order):
        x = c[:, fi]
        jitter = rng.uniform(-0.28, 0.28, len(x))
        color = (fv[:, fi] if fv is not None else x)
        ax_swarm.scatter(x, np.full(len(x), rank) + jitter, c=color, cmap=cmap, norm=norm,
                         s=7, alpha=0.65, linewidth=0, rasterized=True)
    ax_swarm.axvline(0, color=_semantic(ctx, "line"), lw=0.8)
    ax_swarm.set_yticks(y, [features[i] for i in order])
    ax_swarm.invert_yaxis()
    ax_swarm.set_xlabel(ctx.L("contribution"))
    clean(ax_swarm, grid="x")
    sm = mpl.cm.ScalarMappable(norm=norm, cmap=cmap)
    cb = fig.colorbar(sm, ax=ax_swarm, label=color_label, shrink=.82, pad=0.02)
    cb.ax.yaxis.set_major_locator(mpl.ticker.MaxNLocator(nbins=5))
    if title:
        fig.text(0.01, 0.995, title, ha="left", va="top", fontweight="bold",
                 fontsize=mpl.rcParams["axes.titlesize"])
    return ax_bar, ax_swarm


def roc_curve_ci(ax, curves: Mapping[str, Sequence[tuple]], ctx: Context, *,
                 n_grid: int = 101, band: str = "sd", title: str | None = None):
    """Fold-level ROC curves with a mean line and a variability band.

    ``curves[name]`` is a sequence of ``(fpr, tpr)`` or ``(y_true, y_score)``
    pairs.  The band is ``±1 sample SD`` across folds by default; ``band='ci'``
    uses a normal 95% interval of the mean (also across folds).
    """
    grid = np.linspace(0, 1, int(n_grid))
    cols = _series(ctx)
    for i, (name, folds) in enumerate(curves.items()):
        tprs, areas = [], []
        for fold in folds:
            if len(fold) != 2:
                raise ValueError("each fold must be (fpr, tpr) or (y_true, y_score)")
            a, b = np.asarray(fold[0], float), np.asarray(fold[1], float)
            binary_a = set(np.unique(a).tolist()) <= {0.0, 1.0}
            looks_like_curve = (a.ndim == 1 and b.ndim == 1 and len(a) > 2
                                and a[0] == 0 and a[-1] == 1 and b[0] == 0 and b[-1] == 1
                                and np.all(np.diff(a) >= 0)
                                and np.all((a >= 0) & (a <= 1))
                                and np.all((b >= 0) & (b <= 1)))
            if looks_like_curve and not (binary_a and len(np.unique(b)) > 2):
                fpr, tpr = a, b
            else:
                fpr, tpr = _roc_points(a, b)
            order = np.argsort(fpr)
            fpr, tpr = fpr[order], tpr[order]
            tprs.append(np.interp(grid, fpr, tpr))
            areas.append(_auc(fpr, tpr))
        tprs = np.asarray(tprs)
        mean = tprs.mean(axis=0)
        sd = tprs.std(axis=0, ddof=1) if len(tprs) > 1 else np.zeros_like(mean)
        half = (1.96 * sd / np.sqrt(len(tprs))) if (band == "ci" and len(tprs) > 1) else sd
        color = cols[i % len(cols)]
        auc_sd = np.std(areas, ddof=1) if len(areas) > 1 else 0.0
        ax.plot(grid, mean, color=color, lw=1.4,
                label=f"{name} (AUC={np.mean(areas):.2f}±{auc_sd:.2f})")
        if len(tprs) > 1:
            ax.fill_between(grid, np.clip(mean - half, 0, 1), np.clip(mean + half, 0, 1),
                            color=color, alpha=0.17, linewidth=0)
    ax.plot([0, 1], [0, 1], color=_semantic(ctx, "muted"), ls=":", lw=0.8)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1.02)
    ax.set_xlabel(ctx.L("false_positive_rate"))
    ax.set_ylabel(ctx.L("true_positive_rate"))
    ax.legend(loc="lower right", fontsize=mpl.rcParams["legend.fontsize"] * 0.9)
    clean(ax)
    if title:
        ax.set_title(title, loc="left", fontweight="bold", pad=4)
    return ax


def split_violin_corr_matrix(fig, features: Sequence[str], groups: Mapping[str, np.ndarray],
                             ctx: Context, *, corr_matrix=None, title: str | None = None):
    """Lower-triangle correlation matrix with split violins on the diagonal.

    ``groups`` maps a group name to an array ``(n_group, n_features)``.  The
    diagonal compares the first two groups; extra groups are ignored on the
    diagonal but still enter the correlation matrix.
    """
    names = list(groups)
    if len(names) < 2:
        raise ValueError("need at least two groups for split violins")
    mats = [np.asarray(groups[n], float) for n in names]
    if any(m.ndim != 2 or m.shape[1] != len(features) for m in mats):
        raise ValueError("each group must be (n_group, n_features)")
    allv = np.vstack(mats)
    corr = np.asarray(corr_matrix, float) if corr_matrix is not None else np.corrcoef(allv, rowvar=False)
    k = len(features)
    if corr.shape != (k, k):
        raise ValueError("corr_matrix must be (n_features, n_features)")
    cols = _series(ctx)
    gs = fig.add_gridspec(k, k, hspace=0.06, wspace=0.06)
    cmap = mpl.colormaps["RdBu_r"]
    for i in range(k):
        for j in range(k):
            ax = fig.add_subplot(gs[i, j])
            ax.set_xticks([]); ax.set_yticks([])
            for spine in ax.spines.values():
                spine.set_visible(False)
            if i > j:
                ax.add_patch(Rectangle((0, 0), 1, 1, color=cmap((corr[i, j] + 1) / 2), lw=0))
                ax.text(0.5, 0.5, f"{corr[i, j]:.2f}", ha="center", va="center",
                        fontsize=mpl.rcParams["xtick.labelsize"] * 0.8,
                        color="white" if abs(corr[i, j]) > 0.6 else _semantic(ctx, "ink"))
                ax.set_xlim(0, 1); ax.set_ylim(0, 1)
            elif i == j:
                vals1, vals2 = mats[0][:, i], mats[1][:, i]
                lo, hi = float(np.nanmin(np.r_[vals1, vals2])), float(np.nanmax(np.r_[vals1, vals2]))
                if hi <= lo:
                    hi = lo + 1e-9
                ax.set_xlim(0, 1); ax.set_ylim(lo, hi)
                _kde_half(ax, vals1, 0.5, "left", cols[0], width=0.34)
                _kde_half(ax, vals2, 0.5, "right", cols[1], width=0.34)
                for vals, side in ((vals1, -0.02), (vals2, 0.02)):
                    q = np.quantile(vals, [0.25, 0.5, 0.75])
                    ax.plot([0.5 + side, 0.5 + side], [q[0], q[2]],
                            color=_semantic(ctx, "ink"), lw=1.0)
                ax.text(0.5, 0.97, features[i], ha="center", va="top",
                        transform=ax.transAxes,
                        fontsize=mpl.rcParams["xtick.labelsize"] * 0.8,
                        fontweight="bold")
            else:
                ax.axis("off")
    if title:
        fig.text(0.01, 0.995, title, ha="left", va="top", fontweight="bold",
                 fontsize=mpl.rcParams["axes.titlesize"])
    return gs


def circular_heatmap(ax, categories: Sequence[str], metrics: Sequence[str], values,
                     ctx: Context, *, cmap: str = "viridis", title: str | None = None):
    """Grouped circular heatmap: categories around the circle, metrics as rings."""
    if getattr(ax, "name", "") != "polar":
        raise ValueError("circular_heatmap requires a polar Axes")
    cats, mets = list(categories), list(metrics)
    v = np.asarray(values, float)
    if v.shape != (len(cats), len(mets)):
        raise ValueError("values must be (n_categories, n_metrics)")
    n = len(cats)
    width = 2 * np.pi / max(1, n)
    gap = width * 0.08
    ax.set_theta_offset(np.pi / 2)
    ax.set_theta_direction(-1)
    norm = mpl.colors.Normalize(float(np.nanmin(v)), float(np.nanmax(v)))
    cm = mpl.colormaps[cmap]
    ring = 1.0 / max(1, len(mets))
    for i in range(n):
        theta = i * width + width / 2
        for j in range(len(mets)):
            ax.bar(theta, ring * 0.92, width=width - gap, bottom=j * ring,
                   color=cm(norm(v[i, j])), edgecolor="white", linewidth=0.5, align="center")
    ax.set_xticks([i * width + width / 2 for i in range(n)], cats)
    ax.set_yticks([(j + 0.5) * ring for j in range(len(mets))])
    ax.set_yticklabels([])
    ax.set_ylim(0, len(mets) * ring)
    ax.tick_params(axis="x", labelsize=mpl.rcParams["xtick.labelsize"])
    handles = [Patch(facecolor="white", edgecolor=_semantic(ctx, "line"),
                     label=f"{j+1}. {m}") for j, m in enumerate(mets)]
    ax.legend(handles=handles, loc="upper left", bbox_to_anchor=(-0.18, 1.06),
              frameon=False, fontsize=mpl.rcParams["legend.fontsize"] * 0.9,
              handlelength=1.0, handleheight=0.8)
    ax.spines["polar"].set_visible(False)
    sm = mpl.cm.ScalarMappable(norm=norm, cmap=cm)
    cb = ax.figure.colorbar(sm, ax=ax, label=ctx.L("value"), shrink=.8, pad=0.06)
    cb.ax.yaxis.set_major_locator(mpl.ticker.MaxNLocator(nbins=5))
    if title:
        ax.set_title(title, loc="left", fontweight="bold", pad=12)
    return ax


def distribution_composite(fig, categories: Sequence[str], components: Mapping[str, Sequence[float]],
                           observations: Mapping[str, Sequence[float]], ctx: Context, *,
                           title: str | None = None, normalize: bool = False):
    """Stacked composition + group raincloud + boxplot, one generic plate."""
    cats = list(categories)
    obs = {k: np.asarray(v, float) for k, v in observations.items()}
    if not obs:
        raise ValueError("observations must contain at least one group")
    gs = fig.add_gridspec(1, 3, width_ratios=[1.15, 1.25, 0.9], wspace=0.35)
    ax1 = fig.add_subplot(gs[0, 0])
    stacked_composition(ax1, cats, components, ctx, normalize=normalize, legend=False)
    ax1.set_title(ctx.L("composition"), loc="left", fontweight="bold", pad=4)
    ax2 = fig.add_subplot(gs[0, 1])
    cols = _series(ctx)
    for i, (name, vals) in enumerate(obs.items()):
        _kde_half(ax2, vals, float(i), "right", cols[i % len(cols)], width=0.32)
        rng = np.random.default_rng(i)
        ax2.scatter(np.full(len(vals), i) + rng.uniform(-0.06, 0.06, len(vals)), vals,
                    s=6, color=cols[i % len(cols)], alpha=0.5, linewidth=0)
        q = np.quantile(vals, [0.25, 0.5, 0.75])
        ax2.plot([i - 0.05, i + 0.05], [q[1], q[1]], color=_semantic(ctx, "ink"), lw=1.3)
        ax2.plot([i, i], [q[0], q[2]], color=_semantic(ctx, "ink"), lw=0.9)
    ax2.set_xticks(range(len(obs)), list(obs))
    ax2.set_ylabel(ctx.L("value"))
    ax2.set_title(ctx.L("distribution"), loc="left", fontweight="bold", pad=4)
    clean(ax2)
    ax3 = fig.add_subplot(gs[0, 2])
    ax3.boxplot(list(obs.values()), tick_labels=list(obs), widths=0.45, showfliers=False)
    ax3.set_title(ctx.L("comparison"), loc="left", fontweight="bold", pad=4)
    ax3.tick_params(axis="x", labelrotation=30)
    clean(ax3)
    if title:
        fig.text(0.01, 0.995, title, ha="left", va="top", fontweight="bold",
                 fontsize=mpl.rcParams["axes.titlesize"])
    return ax1, ax2, ax3


def chord_diagram(ax, links: Sequence[tuple[str, str, float]], ctx: Context, *,
                  title: str | None = None, min_weight: float = 0.0):
    """Generic chord diagram for source -> target weights."""
    links = [(str(s), str(t), float(w)) for s, t, w in links if float(w) > min_weight]
    if not links:
        raise ValueError("no links above min_weight")
    nodes = list(dict.fromkeys([s for s, _, _ in links] + [t for _, t, _ in links]))
    total = sum(w for _, _, w in links)
    if total <= 0:
        raise ValueError("weights must sum to a positive value")
    per = 180.0 / total
    colors = _series(ctx)
    node_color = {n: colors[i % len(colors)] for i, n in enumerate(nodes)}
    node_total = {n: 0.0 for n in nodes}
    for s, t, w in links:
        node_total[s] += w
        node_total[t] += w
    start = 90.0
    node_arc = {}
    for n in nodes:
        span = per * node_total[n]
        node_arc[n] = (start, start - span)
        start -= span + 1.2
    for n in nodes:
        a0, a1 = node_arc[n]
        ax.add_patch(patches.Wedge((0, 0), 1.0, a1, a0, width=0.045,
                                   facecolor=node_color[n], edgecolor="none", zorder=5))
        mid = np.radians((a0 + a1) / 2)
        ax.text(1.13 * np.cos(mid), 1.13 * np.sin(mid), n,
                ha="left" if np.cos(mid) >= 0 else "right", va="center",
                fontsize=mpl.rcParams["legend.fontsize"] * 0.95)
    src_cursor = {n: node_arc[n][0] for n in nodes}
    tgt_cursor = {n: node_arc[n][1] for n in nodes}
    for s, t, w in links:
        span = per * w
        s0, s1 = src_cursor[s], src_cursor[s] - span
        t0, t1 = tgt_cursor[t], tgt_cursor[t] + span
        src_cursor[s] = s1
        tgt_cursor[t] = t1
        p0 = (np.cos(np.radians(s0)), np.sin(np.radians(s0)))
        p1 = (np.cos(np.radians(s1)), np.sin(np.radians(s1)))
        p2 = (np.cos(np.radians(t1)), np.sin(np.radians(t1)))
        p3 = (np.cos(np.radians(t0)), np.sin(np.radians(t0)))
        verts = [p0, (0, 0), (0, 0), p2, p3, (0, 0), (0, 0), p1, p0]
        codes = [MplPath.MOVETO, MplPath.CURVE4, MplPath.CURVE4, MplPath.CURVE4,
                 MplPath.LINETO, MplPath.CURVE4, MplPath.CURVE4, MplPath.CURVE4,
                 MplPath.CLOSEPOLY]
        ax.add_patch(PathPatch(MplPath(verts, codes), facecolor=node_color[s],
                               edgecolor="none", alpha=0.30, zorder=1))
    ax.set_aspect("equal")
    ax.set_xlim(-1.28, 1.28)
    ax.set_ylim(-1.28, 1.28)
    ax.axis("off")
    if title:
        ax.set_title(title, loc="left", fontweight="bold", pad=4)
    return ax
