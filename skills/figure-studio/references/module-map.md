# 模块映射：数据图型库 / 比较与拼版 / 投稿契约 / 场图与 3D 内核

> 这个 skill 不把任何外部仓库整包复制进 NewMathAgent。外部模板带各自的路径、模拟数据和
> 许可证，整包复制会变成第二个绘图入口。这里的做法是**翻译成 recipe + 数据契约 + 本项目的
> 渲染函数**；`assets/recipes.json` 用 `category` 表示四个功能模块，不再保留来源字段。

## 1. 数据图型库（data-recipe-library）

| 模板 | recipe | 实现状态 | 说明 |
|---|---|---|---|
| 多分类 SHAP 柱状+蜂群 | `shap-combo` | `studio.shap_combo` | 需要真实加性贡献；没有真 SHAP 就改 `ablation-bars`，不要把回归系数冒充 SHAP |
| 配对云雨 | `paired-raincloud` | `studio.paired_raincloud` | 有 subject ID 才能配对；没有就 `paired-dumbbell` |
| 交叉验证 ROC+CI | `roc-curve-ci` | `studio.roc_curve_ci` | 需要 fpr/tpr × model × fold；单模型 ROC 用 `roc_curve` |
| Taylor | `taylor-diagram` | `studio.taylor_panel` | 用笛卡尔四分之一圆，避免极坐标刻度打架 |
| 相关矩阵组合 | `correlation-pairgrid` | `studio.scatter_matrix` | 3–8 个连续变量 |
| 预测—真实边缘分布 | `marginal-joint-scatter` | `studio.prediction_marginal` | 大样本用 hexbin，不抽稀 |
| RF/TPE 调参 3D 曲面 | `tuning-surface-3d` / `surface3d-response` | `studio.surface3d_panel` | 平滑曲面 + 二维投影；不画瀑布 |
| 下三角相关+半边小提琴 | `split-violin-corr-matrix` | `studio.split_violin_corr_matrix` | 需要 feature × group × value；组别 ≤3 |
| 确定性场的拆半小提琴 | `field-split-raincloud` | `studio.field_split_raincloud` | 只借 sci-box 05 的 split-violin；相关矩阵/分组树不适用（空间自相关是构造出来的） |
| 分组环形热图 | `circular-heatmap` | `studio.circular_heatmap` | 类别要有周期/分组含义；否则用矩形热图 |
| 城市公园降温组合 | `distribution-composite` | `studio.distribution_composite` | 堆叠 + 云雨 + 箱线的总装；组件总和无意义时不要堆叠 |
| Nature 和弦 | `chord-diagram` | `studio.chord_diagram` | 需要 source × target × weight；稀疏连接用邻接矩阵 |

**结论：11 个模板全部有本项目的通用 Python 实现**（`studio.py`）。其中 6 个需要对应的数据契约：
fold 级 ROC、真 SHAP 贡献、feature × group 分布、分组环形数据、来源-去向流量。数据不适配时
按 `recipes.json` 的 `fallback` 降级即可；数据适配时直接调用。

## 2. 比较与拼版（comparison-and-composition）

| 图型 | recipe | 实现状态 |
|---|---|---|
| 分组柱 / 多指标柱 | `grouped-bars` / `multi-metric-bar-panel` | `studio.grouped_bars` |
| 消融条 | `ablation-bars` | `studio.grouped_bars(horizontal=True)` |
| 组成分解 / 堆叠 | `stacked-composition` | `studio.stacked_composition` |
| 正确率/分类分解 | `grouped-bars` + `matrix-heatmap` | 已有底层 |
| 趋势 / 事件时间线 | `trend-line` / `timeline` | `studio.profile_panel` / `timeline_panel` |
| 优化热图 / 双热图 | `signed-error-heatmap` / `matrix-heatmap` | `studio.heatmap_panel` |
| 速度/扫描 | `log-scale-bars` / `parameter-sweep` | `studio.grouped_bars` / `profile_panel` |
| 雷达 | `radar` | `studio.radar_panel` |
| 3D 流形 / 带灰块曲面 | `surface3d-response` | `studio.surface3d_panel`（数据没有多井结构就如实说） |
| 轨迹 / 相图 | `trajectory-2d` | `studio.trajectory_panel` |
| 预测诊断 | `prediction-diagnostics` | `studio.prediction_marginal` |
| 综合拼版 | `plate` / `hero-evidence` | `studio.plate_layout` / `hero_layout` |

## 3. 投稿契约与质控（publication-contract）

| 模板/原型 | recipe | 状态 |
|---|---|---|
| paired | `paired-raincloud` / `paired-dumbbell` | 已实现 |
| marginal | `marginal-joint-scatter` | 已实现 |
| dotplot | `horizontal-dot-interval` | 已实现 |
| ROC | `roc-curve-ci` | `studio.roc_curve_ci` |
| volcano | `volcano-plot` | external |
| quantitative grid | `quantitative-grid` | `grid_layout` |
| schematic-led composite | `schematic-generic` / `cylinder-schematic` | `cylinder_schematic` 已实现 |
| image plate + quant | — | 本 skill 不处理显微/图像板 |
| asymmetric mixed-modality | `hero-evidence` / `plate` | 已实现布局 |
| 数据层契约 | `figures/data` + `figures/spec` + `figures/*.lock.json` | `figure_lock.py`（build/verify） |

## 4. 场图与 3D 内核（field-and-3d-core）

| 能力 | 落点 |
|---|---|
| 场图/等高线/热图 | `studio.field_panel`、`studio.heatmap_panel`、`lib.visualization.charts` |
| 3D 曲面 | `studio.surface3d_panel`、`charts.surface3d` |
| 语义色阶/PowerNorm | `assets/style.tokens.json` + `config/visualization.json` 的 `quantity_cmap` |
| 导出/登记/目检 | `lib.visualization.export/evidence/quality` |

## 5. 为什么不把外部仓库放进项目

- 外部脚本带 Linux 路径和模拟数据，直接 import 会污染项目；
- 许可证各不相同，整包复制会让再分发变复杂；
- 一个入口比四个入口更容易维护。需要参考实现时，在本项目之外保留 clone，不要复制进 skill。
