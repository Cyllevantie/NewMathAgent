# -*- coding: utf-8 -*-
"""Render every generic recipe once on small synthetic arrays.

This is a shape/API smoke test, not a paper figure.  It catches the failure
mode where a recipe is accepted by ``check_brief`` but cannot actually render.

Run from the project root:
    python skills/figure-studio/scripts/smoke_recipes.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import studio  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
OUT = Path("tmp/figure-studio-smoke")
OUT.mkdir(parents=True, exist_ok=True)
ctx = studio.context(ROOT)
rng = np.random.default_rng(7)

# Every non-external `implemented` string must resolve to a real function.
import json
recipes = json.loads((Path(__file__).resolve().parents[1] / "assets" / "recipes.json").read_text(encoding="utf-8"))
for rec in recipes["recipes"]:
    impl = rec.get("implemented", "")
    if impl.startswith("studio."):
        name = impl.split("(", 1)[0].split(".", 1)[1]
        if not hasattr(studio, name):
            raise SystemExit(f"{rec['id']}: missing studio.{name}")


def save(fig, name):
    fig.savefig(OUT / f"{name}.png", dpi=220, facecolor="white")
    print("rendered", OUT / f"{name}.png")


with studio.style(ctx) as settings:
    # shap combo
    n, k = 180, 7
    X = rng.normal(size=(n, k))
    contrib = X * rng.uniform(0.2, 1.2, size=k)
    fig = studio.canvas(ctx, width_mm=160, height_mm=90, constrained=False)
    studio.shap_combo(fig, [f"特征 {i+1}" for i in range(k)], contrib, X, ctx,
                      top_n=6, title="SHAP 组合（合成数据冒烟）")
    save(fig, "01_shap_combo")

    # ROC with folds
    curves = {}
    for m in range(2):
        folds = []
        for _ in range(5):
            y = rng.integers(0, 2, 140)
            score = 1.0 / (1.0 + np.exp(-(y * (1.2 + 0.5 * m) + rng.normal(0, 1.0, 140))))
            folds.append((y, score))
        curves[f"模型 {m+1}"] = folds
    fig = studio.canvas(ctx, width_mm=100, height_mm=90, constrained=True)
    ax = fig.add_subplot(111)
    studio.roc_curve_ci(ax, curves, ctx, title="CV ROC + 波动带（合成数据冒烟）")
    save(fig, "02_roc_ci")

    # split violin + corr matrix
    feats = ["C", "dC/dr", "d2C/dr2", "maxC", "meanC"]
    g1 = rng.normal(size=(60, len(feats)))
    g2 = g1 * 0.8 + rng.normal(0, 0.5, g1.shape)
    fig = studio.canvas(ctx, width_mm=120, height_mm=120, constrained=False)
    studio.split_violin_corr_matrix(fig, feats, {"前期": g1, "后期": g2}, ctx,
                                    title="相关矩阵 + 半边小提琴（合成数据冒烟）")
    save(fig, "03_split_violin_corr")

    # circular heatmap
    cats = [f"组 {i+1}" for i in range(8)]
    mets = ["指标 A", "指标 B", "指标 C", "指标 D"]
    vals = rng.uniform(0, 1, size=(len(cats), len(mets)))
    fig = studio.canvas(ctx, width_mm=120, height_mm=120, constrained=False)
    ax = fig.add_axes([0.12, 0.12, 0.66, 0.70], projection="polar")
    studio.circular_heatmap(ax, cats, mets, vals, ctx, title="分组环形热图（合成数据冒烟）")
    save(fig, "04_circular_heatmap")

    # distribution composite
    comps = {"A": rng.uniform(1, 3, 4), "B": rng.uniform(1, 3, 4), "C": rng.uniform(1, 3, 4)}
    obs = {f"组 {i+1}": rng.normal(i * 0.3, 1, 80) for i in range(4)}
    fig = studio.canvas(ctx, width_mm=160, height_mm=80, constrained=False)
    studio.distribution_composite(fig, [f"阶段 {i+1}" for i in range(4)], comps, obs, ctx,
                                  title="组成 + 云雨 + 箱线（合成数据冒烟）")
    save(fig, "05_distribution_composite")

    # chord
    links = [("C", "T", 8), ("C", "r", 5), ("T", "r", 4), ("r", "边界", 3), ("T", "边界", 2)]
    fig = studio.canvas(ctx, width_mm=90, height_mm=90, constrained=False)
    ax = fig.add_subplot(111)
    studio.chord_diagram(ax, links, ctx, title="和弦图（合成数据冒烟）")
    save(fig, "06_chord")

print("OK", OUT)
