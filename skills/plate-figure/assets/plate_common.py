# -*- coding: utf-8 -*-
"""Shared drawing grammar for the Nature-style plates.

Every ``figures/plate_<id>.py`` imports this module so the plates keep one
type scale, one semantic palette and one header/KPI grammar.  The figure
language/font come from ``reports/FIGURE_CONTEXT.json``; the plate text itself
is supplied by each plate, so an English template can use the same atoms.
The module is deliberately small: layout is per-plate (the plates must not
share one skeleton), only the atoms are shared.

    import sys
    from pathlib import Path
    ROOT = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(ROOT / "skills" / "plate-figure" / "assets"))
    import plate_common as P

Run under the project interpreter:
    E:/miniconda3/envs/NewMathAgent/python.exe -X utf8 figures/plate_q3.py
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib as mpl

mpl.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyBboxPatch  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
FIG_DIR = ROOT / "figures"

# --- one type scale ---------------------------------------------------------
# Default for the current CUMCM run; ``setup()`` overrides it from
# ``reports/FIGURE_CONTEXT.json`` so an English template gets its own font
# instead of being forced into a Chinese font.
FONT = "Microsoft YaHei"
FS_TITLE = 11.4
FS_SUB = 6.4
FS_BODY = 6.2
FS_TICK = 5.7
FS_SMALL = 5.2

# --- one semantic palette ---------------------------------------------------
INK = "#1F2937"
MID = "#4B5563"
MUTED = "#6B7280"
LINE = "#475569"
BLUE = "#1D4ED8"
BLUE2 = "#3B82F6"
BLUE3 = "#60A5FA"
PALE = "#EAF2FB"
EDGE = "#C9DDF0"
RED = "#B64342"
GREEN = "#2F7D46"
GREEN2 = "#5E813F"
AMBER = "#B45309"
PURPLE = "#6D28D9"
DRY = "#E6E6E6"
WHITE = "#FFFFFF"


def figure_context() -> dict:
    """Read the resolved paper-template context (language/font/width).

    The plate grammar is language-agnostic; the *caller* supplies the words.
    This helper exists only so ``setup()`` and the checker can agree with the
    template instead of assuming Chinese.
    """
    try:
        return json.loads((ROOT / "reports" / "FIGURE_CONTEXT.json")
                          .read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def setup(font: str | None = None) -> None:
    ctx = figure_context()
    font = font or str(ctx.get("font") or FONT)
    fonts = [font]
    for fallback in (FONT, "SimHei", "Noto Sans CJK SC", "DejaVu Sans"):
        if fallback not in fonts:
            fonts.append(fallback)
    mpl.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": fonts,
        "mathtext.fontset": "dejavusans",
        "font.size": FS_BODY,
        "axes.labelsize": FS_BODY,
        "xtick.labelsize": FS_TICK,
        "ytick.labelsize": FS_TICK,
        "axes.linewidth": 0.7,
        "axes.edgecolor": "#333333",
        "axes.spines.top": False,
        "axes.spines.right": False,
        "xtick.major.size": 2.2,
        "ytick.major.size": 2.2,
        "xtick.major.width": 0.6,
        "ytick.major.width": 0.6,
        "xtick.direction": "out",
        "ytick.direction": "out",
        "legend.frameon": False,
        "pdf.fonttype": 42,
        "svg.fonttype": "none",
        "figure.facecolor": "white",
        "savefig.facecolor": "white",
        "axes.unicode_minus": False,
    })


def canvas(w_mm: float, h_mm: float) -> plt.Figure:
    fig = plt.figure(figsize=(w_mm / 25.4, h_mm / 25.4))
    fig._plate_w = w_mm
    fig._plate_h = h_mm
    return fig


def axes_mm(fig: plt.Figure, x: float, y: float, w: float, h: float, **kw):
    W, H = fig._plate_w, fig._plate_h
    return fig.add_axes([x / W, y / H, w / W, h / H], **kw)


def ftext(fig: plt.Figure, x: float, y: float, s: str, **kw):
    return fig.text(x / fig._plate_w, y / fig._plate_h, s, **kw)


def clean(ax, grid: bool = False) -> None:
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.tick_params(pad=2)
    if grid:
        ax.grid(True, color=EDGE, lw=0.35, alpha=0.75)
        ax.set_axisbelow(True)


def header(fig: plt.Figure, kicker: str, title: str, subtitle: str) -> None:
    """Deprecated no-op: figures do not carry a figure-level title.

    The title/caption belongs to LaTeX (⑨).  If a short claim note helps the
    reader, use :func:`claim_note` at 6–7 pt, regular weight, near the chart
    (middle/bottom of a blank area), never as a top header.
    """
    return None


def claim_note(fig: plt.Figure, x: float, y: float, text: str, *,
               color: str = MUTED, ha: str = "left", va: str = "top") -> None:
    """Small, non-bold claim annotation — a supplement, not a title."""
    ftext(fig, x, y, text, fontsize=FS_BODY, color=color,
          fontweight="normal", ha=ha, va=va)


def letter(fig: plt.Figure, x: float, y: float, s: str) -> None:
    ftext(fig, x, y, s, fontsize=8.8, fontweight="bold", color=INK,
          ha="left", va="bottom")


def wbox(pad: float = 0.22, alpha: float = 1.0) -> dict:
    return dict(boxstyle="round,pad=%s" % pad, fc=WHITE, ec="none", alpha=alpha)


def direct(ax, x: float, y: float, s: str, color: str = INK, dx: float = 4,
           dy: float = 0, ha: str = "left", va: str = "center",
           fontsize: float = FS_SMALL) -> None:
    """Direct label (no legend box) with a white halo so it stays readable."""
    ax.annotate(s, xy=(x, y), xytext=(dx, dy), textcoords="offset points",
                fontsize=fontsize, color=color, ha=ha, va=va,
                bbox=wbox(0.18, 0.92), zorder=12)


def kpi_band(fig: plt.Figure, x: float, y: float, w: float, h: float,
             tiles, note: str | None = None, accent: str = BLUE,
             pale: str = PALE, edge: str = EDGE) -> None:
    """Bottom band: optional one-line claim + N value/label tiles."""
    ax = axes_mm(fig, x, y, w, h)
    ax.set_xlim(0, w)
    ax.set_ylim(0, h)
    ax.axis("off")
    # Text only: no band, no tiles.  The user explicitly rejected the card
    # frames around KPI values.
    top = h - 3.0 if note else h - 1.0
    if note:
        ax.text(0.0, h - 1.0, note, fontsize=6.0, style="italic", color=INK,
                ha="left", va="top")
    n = len(tiles)
    tw = w / n
    for i, (value, label) in enumerate(tiles):
        cx = (i + 0.5) * tw
        ax.text(cx, top * 0.60, value, fontsize=8.0, fontweight="bold",
                color=accent, ha="center", va="center")
        ax.text(cx, top * 0.40, label, fontsize=5.3, color=MUTED,
                ha="center", va="center")


def caption_below(fig: plt.Figure, x: float, y: float, letter: str,
                  text: str) -> None:
    """Short panel description below the panel; the a/b/c letter is omitted.

    ``letter`` is kept in the signature so existing generators can call this
    without a rewrite; it is deliberately not drawn.
    """
    if not str(text).strip():
        return
    ftext(fig, x, y, str(text), fontsize=5.6, color=MUTED,
          ha="left", va="top")


KPI_MIN_TILE_MM = 17.0
KPI_MAX_TILE_MM = 36.0


def kpi_block(fig: plt.Figure, x: float, y: float, w: float, h: float,
              tiles, cols: int | None = None, accent: str = BLUE) -> None:
    """紧凑 KPI 文字块：无边框、无底板。

    2–4 项只要横排放得下，就**必须排成一行**（`fig_q1_plate` 的样式）。
    ``cols`` 只是上限：宽块里传 ``cols=2`` 也会被展开成一行；只有侧栏
    窄到每个条目不足 ``KPI_MIN_TILE_MM`` 时才允许竖排/两行。
    """
    ax = axes_mm(fig, x, y, w, h)
    ax.set_xlim(0, w)
    ax.set_ylim(0, h)
    ax.axis("off")
    n = len(tiles)
    fit = max(1, min(n, int(w // KPI_MIN_TILE_MM)))
    if fit >= n:
        cols = n
    else:
        cols = min(int(cols) if cols else fit, fit)
    # A full-width block must not stretch four values across the whole plate:
    # keep a compact pitch like the Q1 reference and leave the rest blank.
    block_w = min(w, cols * KPI_MAX_TILE_MM)
    rows = (n + cols - 1) // cols
    cw, rh = block_w / cols, h / rows
    for i, (value, label) in enumerate(tiles):
        r, c = divmod(i, cols)
        cx = c * cw
        cy = h - (r + 1) * rh
        ax.text(cx + 0.8, cy + rh * 0.58, value, fontsize=7.6,
                fontweight="bold", color=accent, ha="left", va="center")
        ax.text(cx + 0.8, cy + rh * 0.30, label, fontsize=5.0, color=MUTED,
                ha="left", va="center")


def save(fig: plt.Figure, stem: str) -> None:
    fig.savefig(FIG_DIR / f"{stem}.png", dpi=300, facecolor="white")
    fig.savefig(FIG_DIR / f"{stem}.pdf", facecolor="white")
    plt.close(fig)
    print("wrote", FIG_DIR / f"{stem}.png", "and", FIG_DIR / f"{stem}.pdf")
