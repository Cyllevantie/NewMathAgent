---
name: mathmodel-figure-templates
description: Use this skill in the MathModel LaTeX sandbox when the user asks to reproduce built-in scientific visualization templates, especially prompts from the Improve tab mentioning $mathmodel-figure-templates, 科研绘图模板, SHAP蜂群柱状图, 配对云雨图, 交叉验证ROC, 泰勒图, 相关矩阵组合图, 预测真实值边缘分布图, TPE调参3D曲面, 下三角相关矩阵半边小提琴图, 分组环形热图, 城市公园降温组合图, or Nature和弦图. It provides ready-to-run Python scripts bundled inside the skill.
allowed-tools: Bash(*), Read, Write, Edit, Grep, Glob
---

# MathModel Figure Templates

This skill is bundled into the LaTeX sandbox at `skills/mathmodel-figure-templates`. It contains ready-to-run Python/matplotlib scripts for the figure templates exposed in the MathModel Improve tab.

Preview images for all 11 templates are in `assets/previews/` (e.g.
`rf_tpe_surface_replica.png`, `paired_raincloud_replica.png`).  These templates are
**single-chart style sources**, not a mandatory figure set: pick one only when the
data shape matches (see `../plate-figure/SKILL.md` for the applicability table).
Do not force SHAP/ROC/Taylor/correlation/chord templates onto a deterministic PDE
model just to “use a template”. **But templates are grammars, not all-or-nothing:
if one panel is applicable, splice it into the figure.** For template 05
(`grouped-corr-split-violin`), take the split half-violin panel (centre vs
surface / early vs late) and pair it with a field or line panel; do not take the
correlation matrix or group tree (spatial autocorrelation is built in, not an
independent sample). Project recipe: `studio.field_split_raincloud`; other
applicable parts are listed in `../plate-figure/SKILL.md` §「部件拼接」.

## Fast Path

1. Match the requested chart in `references/figure-catalog.md`.
2. From the project root, run the renderer with the template id:

```bash
python3 skills/mathmodel-figure-templates/scripts/render_template.py paired-raincloud
```

3. The renderer copies the bundled template script into `绘图复刻/scripts/`, runs it there, and writes outputs to `绘图复刻/outputs/`.
4. Return the generated PNG/PDF/SVG paths and the copied script path to the user.

Use `--list` to show supported ids:

```bash
python3 skills/mathmodel-figure-templates/scripts/render_template.py --list
```

## Output Contract

- Work under the current workspace unless the user gives another path.
- Default project folder: `绘图复刻`.
- Script path: `绘图复刻/scripts/make_<template>.py`.
- Outputs: `绘图复刻/outputs/<template>_replica.png`, `.pdf`, `.svg`.
- Use the bundled scripts as the first choice; edit the copied workspace script only when the user requests customization.
- The bundled scripts use deterministic simulated data. Do not claim simulated values reproduce a source study exactly.

## Template Ids

- `multiclass-shap-combo`
- `paired-raincloud`
- `cv-roc-ci`
- `taylor-diagram`
- `correlation-pairgrid`
- `prediction-marginal-grid`
- `rf-tpe-surface`
- `grouped-corr-split-violin`
- `grouped-circular-heatmap`
- `urban-park-cooling-combo`
- `nature-chord-diagram`

## When Customizing

If the user asks for changes, copy/run the nearest template first, then edit the copied file in `绘图复刻/scripts/`. Preserve:

- `MPLCONFIGDIR` before importing matplotlib.
- deterministic seeds for simulated data.
- PNG/PDF/SVG export.
- readable labels, legends, and high-DPI output.

Use `references/plot-recipes.md` for implementation patterns.
