---
name: figure-studio
description: "统一科研绘图入口：把数据图型库（data-recipe-library）、比较与拼版（comparison-and-composition）、投稿契约与质控（publication-contract）、场图与3D内核（field-and-3d-core）合成一个 skill。用于数据图选型、多面板与拼版、3D 响应面、机制示意、中文/英文图内文字、配色与字体统一、来源数据与目检门禁。"
allowed-tools: PowerShell, Read, Write, Edit, Grep, Glob, Agent
---

# Figure Studio：一个入口，四种图法

> 这不是“再加一个模板库”。它解决的是四件反复发生的事：
> ① 库里没有的图型，agent 只会退回折线/柱状/表格；
> ② 数据图型库 / 比较与拼版 / 投稿契约与质控 / 场图与3D内核各自成包，没有接进流水线；
> ③ ⑦ 的权限只够挪图例，换不了图型和构图；
> ④ 渲完 PNG 就登记，没有“打开看、说看到什么、再改”的回路。
>
> 做法是：**一个共享 skill + 四个内部分工 + 现有阶段边界不变**。
> ④ 仍负责数据与 claim，⑦ 仍负责图面与构图，⑧ 仍只判不改。
> skill 是方法库，不是新阶段；权限仍在阶段那边。

## 0. 什么时候用它

- 要画数据图、多面板图、拼版大图、3D 响应面、机制/几何示意；
- 要统一全文图的配色、字体、字号、面板短描述、图注语言；
- 要从数据图型库 / 比较与拼版 / 投稿契约与质控 / 场图与3D内核里选一个，而不是默认折线；
- 要在投稿前检查“图是否支持 claim、是否有来源数据、是否读得清”。

不适用：纯 draw.io 技术路线图/流程图（走 `../paper-diagram/SKILL.md`）；
纯文献阅读、论文润色、引用、PPT（走项目外的写作/阅读工具，不要塞进这里）。

## 0.1 四个功能模块

| 功能模块 | 负责什么 | 主要文件 |
|---|---|---|
| **数据图型库** | 分布、关系、归因、模型诊断等通用 recipe；50+ 条目录项，含 6 个新补齐的通用模板 | `assets/recipes.json`、`references/catalog.md`、`scripts/studio.py` |
| **比较与拼版** | 分组比较、消融、组成分解、hero+evidence、plate 总装 | `references/composition.md`、`studio.grouped_bars/stacked_composition/plate_layout` |
| **投稿契约与质控** | FigureBrief、bundle/spec/lock、统计口径、source data、导出与目检门禁 | `assets/figure-brief.schema.json`、`scripts/figure_lock.py`、`references/qa.md`、`statistics.md`、`source-data.md` |
| **场图与 3D 内核** | 场图/等高线/3D 曲面、语义色阶、导出台账、目检签名 | `assets/style.tokens.json`、`lib/visualization` |

日常路由、文件说明和 recipe `category` 都使用上表的功能名；第三方来源只在
`references/ecosystem.md` 的授权原则里抽象说明，不进入 recipe 字段。

## 1. 先解析模板语言，再动笔

图内文字的语言由**论文模板**决定，不由聊天语言决定。先跑：

```powershell
python skills/figure-studio/scripts/resolve_context.py --write
```

它读取 `config/delivery.local.json` 的 `template`（其次 `paper/structure.json`），输出
`reports/FIGURE_CONTEXT.json`：`language / width_mm / font / labels_path / rule`。

| 模板 | 语言 | 全宽 | 半栏 | 字体 |
|---|---|---:|---:|---|
| `zh/cumcm-latex` | 中文 | 160 mm | 80 mm | Microsoft YaHei |
| `en/**`、Nature 系 | English | 183 mm | 88 mm | Arial |
| 未声明 | 看正文 CJK 比例；CUMCM 默认中文；英文正文则 183/88 | 160 mm（zh）/183 mm（en） | 80 mm（zh）/88 mm（en） | 对应字体 |

硬规则：

- 一张图只使用一种解释性语言。方法名/模型名/指标名（TPE、SHAP、AUC、RMSE、R²）可保留拉丁写法，但坐标轴、面板标题、注释必须是模板语言。
- 中文图不要用 `$...$` 写单位、上下标或简单希腊字母；优先 Unicode（`R²`、`℃`、`μ`、`σ`），避免字体缺字。若发现方框，改成 ASCII（如 `kg/kg`、`m2/s`）。
- 标签从 `assets/labels.zh.json` / `labels.en.json` 取；新词同时加到两份字典，不要在图脚本里临时翻译。
- 图注写在 LaTeX 里；**图内不写整图标题**，只放面板短描述和必要注释，不放大段解释。

## 2. 路由：先看数据形状，再看图型

| 你手上的数据 | 默认 recipe | 不要做什么 |
|---|---|---|
| `(r,t)` 二维场，且**空间结构本身是 claim** | `field_contour` / `field_heatmap` | 不要只切几条折线就说完场结构；场不是默认图型 |
| `(r,t)` 二维场，但 claim 是**分布怎么移动/变窄** | `field_raincloud`（按时间或半径带分组，sci-box 半小提琴 + 箱线 + 散点） | 不要再交一整墙 `profiles` / `field_waterfall` 折线 |
| 场里两组空间带在每个时间窗的分布差 | `field_split_raincloud`（sci-box 05 背靠背半小提琴：中心区 vs 表面区；`anomaly=true` 先减径向均值成 ΔT） | 不要硬做相关矩阵；确定性场的空间自相关不是独立样本 |
| 空间/时间剖面族 | `profiles` / `small_multiples` | 连续变化/斜率是 claim 时用折线；只有少数检查点比较才用 `sampled_bars`/`grouped_bars` |
| 时间序列只看几个检查点 | `sampled_bars`（按 x 抽样成柱） | 不要为了“连续感”画整条折线；抽样点要在图注写清 |
| 多组分布（每组多个观测） | `raincloud` / `distribution_box` | 每组 <3 个观测不要硬画小提琴 |
| 同一对象前后测 | `paired_raincloud` / `paired_dumbbell` | 不要画成两组独立柱 |
| 多口径/多方法 + 区间 | `dot_interval` / `forest_plot` | 不要只有均值、没有真实区间 |
| 类别 × 序列 | `grouped_bars` / `stacked_composition` | 组成总和没有意义时不要堆叠 |
| 矩阵数值/敏感性表 | `annotated_heatmap`（默认 10×8 抽样，格子里写数字；格数由 agent 按可读性决定，多一点更好） | 矩阵 >12×10 且不需逐格读数；只画色块不写数 |
| 多变量关系 | `correlation_matrix` / `scatter_matrix` | 变量 >12 不要硬塞相关矩阵 |
| 预测 vs 观测 | `prediction_marginal` / `residual_panel` | 不要只画拟合线不画误差 |
| 真实二分类 | `roc_curve` | AUC≈1 时不要拿 ROC 当卖点 |
| 多模型形状+幅度 | `taylor_diagram` | 不要只比相关系数 |
| 两参数 → 指标 | `surface3d` + 2D 投影 | 不要画 3D 柱/3D 饼；不要用瀑布替代曲面 |
| 3–8 维指纹 | `radar` | 维度 >8、量纲不可比时不要用 |
| 机理/几何 | `cylinder_schematic` / `paper-diagram` | 纯数据题不要硬画示意图 |

完整目录、数据契约、适用/禁用/退路见 [`references/catalog.md`](references/catalog.md)；
机器可读的 recipe 列表见 [`assets/recipes.json`](assets/recipes.json)。

**每张主图至少写 2 个不同视觉编码的候选**，不是同图型换配色。至少一个候选来自不同 recipe 家族（如 `profiles` vs `field_contour`、`dot_interval` vs `grouped_bars`）。写清：映射哪些字段、回答什么问题、保留/隐藏什么、淘汰理由、退路。用户点名图型只是 preference；先检查数据契约，不适合就降级并说明。

候选不是 ④ 的“最终选择”：④ 只保证每个候选需要的字段都在 bundle 里并写进 brief；⑦ 渲染候选到 `tmp/figures/<id>/cand_*.png`，按 claim 支持 / 信息密度 / 可读性 / 灰度 / 语言统计 / 冗余评分后，把选择写进 `figures/choice/<id>.json`。选择不能改 fields、claim、statistics 或 bundle。

**sci-box 部件拼接**：模板是语法，不是整张用或整张不用；只适配一个面板时，
把那个面板（05 拆半小提琴 / 08 半小提琴 / 10 云雨+箱线 / 07 3D 面）与本题的
场图/折线拼成一张，不适配的部件（相关矩阵/分组树/ROC/Taylor）不画。见
`../plate-figure/SKILL.md` §「部件拼接」。

**混排预算与判重**：支撑图折线 4–6、场图/热力图共 2（1 张场图 + 1 张带数字的矩阵热力图）、雨云/分布 ≤1、柱/抽样柱 ≤3
（`config/visualization.json` 的 `chart_mix.line_budget`）；连续轨迹/相轨迹保留
折线，只在少数检查点比较时才用柱/点，场分布才用雨云，不要把一整批图压成同一种。
同一 bundle + 同一视觉编码只出现一次，plate hero 已画的 3D 曲面不再出同源支撑图。
**同类子型也尽量均分**（柱里的 sampled/grouped、折线里的 profiles/field_waterfall）；
数据不支持另一种子型时不要硬换，保留并在报告里说明。
机械检查：`python skills/figure-studio/scripts/check_figure_mix.py --root .`。

## 3. FigureBrief：画之前先写清楚

每张图先写 `reports/FIGURE_BRIEF.json`（或每题一个 `reports/figure_briefs/<id>.json`），至少包含：

```json
{
  "figure_id": "q3_dryfront",
  "question": "干前沿如何推进？",
  "claim": "干前沿由表面推进到中心，表面与中心达标相差约 46 h。",
  "language": "zh",
  "template": "zh/cumcm-latex",
  "width_mm": 160,
  "archetype": "hero_evidence",
  "data": [
    {"path": "figures/data/q3_field.npz", "fields": ["r", "t", "C"],
     "unit": "cm, h, kg/kg", "n": 77427, "role": "simulated", "exclusions": "无"}
  ],
  "panels": [
    {"id": "a", "role": "hero", "recipe": "field_contour",
     "fields": ["r", "t", "C"],
     "field_mapping": {"x": "r", "y": "t", "z": "C", "level": 0.15},
     "options": {"quantity": "moisture", "level": 0.15},
     "claim": "干前沿随时间向内推进。"},
    {"id": "b", "role": "comparison", "recipe": "profiles",
     "fields": ["r", "C_center", "C_surface"],
     "field_mapping": {"x": "r", "series": ["C_center", "C_surface"],
                       "series_labels": ["中心", "表面"]},
     "options": {"series_labels": ["中心", "表面"]},
     "claim": "中心与表面在末段收敛。"}
  ],
  "statistics": {
    "interval": {"kind": "none", "method": "不适用"},
    "test": {"kind": "none", "p_values": false},
    "unit": "每条曲线是一个确定性模拟时刻",
    "paired": false,
    "n_independent": 1
  },
  "candidates": [
    {"encoding": "颜色 + 位置", "recipe": "field_contour",
     "mapped_fields": ["r", "t", "C"], "keeps": "场的整体推进", "hides": "单点精度",
     "rejected_reason": "备用，若场太平坦则改剖面"},
    {"encoding": "多条剖面折线", "recipe": "profiles",
     "mapped_fields": ["r", "C_center", "C_surface"], "keeps": "末段收敛",
     "hides": "空间结构", "rejected_reason": "作为 b 面板，不单独成图"},
    {"encoding": "等值线 + 判据线", "recipe": "field_contour",
     "mapped_fields": ["r", "t", "C"], "keeps": "干前沿位置", "hides": "低值细节",
     "rejected_reason": "与 a 重复，只保留一个"}
  ],
  "fallbacks": [
    {"condition": "场过于平坦", "action": "改 profiles，保留判据线"}
  ]
}
```

校验：

```powershell
python skills/figure-studio/scripts/check_brief.py reports/FIGURE_BRIEF.json --context reports/FIGURE_CONTEXT.json
```

它会拒绝：未知 recipe、重复面板 id、hero 不在首位、语言/宽度与模板不一致、有区间却没写区间定义、写了 p 值却 `test.kind=none`。

### 3.1 数据图交付契约（④ → ⑦）：bundle / spec / lock

FigureBrief 是“图要证明什么”，下面这三件是“数从哪来、谁有权改”。**④ 只写这三件，
⑦ 只读这三件并渲染**：

```text
figures/data/<id>.npz       # ④：只读数据包（字段名就是 spec/锁里的字段名）
figures/spec/<id>.json      # ④：recipe + fields/field_mapping + claim/stats + layout
figures/<id>.lock.json      # ④：bundle/spec 语义部分/source/claim 的哈希
```

④ 用 `studio.save_bundle(...)` 一次写齐三件：

```python
studio.save_bundle(
    ".", "q3_dryfront", {"r": r, "t": t, "C": C}, ctx,
    claim="干前沿由表面推进到中心，表面与中心达标相差约 46 h。",
    sources=["results/q3.json", "code/q3.py"],
    panels=[
        {"id": "a", "role": "hero", "recipe": "field_contour",
         "fields": ["r", "t", "C"], "field_mapping": {"x": "r", "y": "t", "z": "C"},
         "claim": "干前沿随时间向内推进。", "options": {"quantity": "moisture", "level": 0.15}},
    ],
    statistics={"interval": {"kind": "none", "method": "不适用"},
                "test": {"kind": "none", "p_values": False},
                "unit": "每条曲线是一个确定性模拟时刻", "paired": False},
)
```

校验：

```powershell
python skills/figure-studio/scripts/figure_lock.py verify --root .
```

锁校验分三类，报告里带前缀：

| 前缀 | 含义 | 谁修 |
|---|---|---|
| `[lock:data]` | bundle / source 在锁之后变了（数据层被改） | **回 ④** 重建 bundle + lock，⑦ 不许改数据 |
| `[lock:contract]` | spec 的 fields / field_mapping / claim / statistics 被改 | **回 ④** 改语义；⑦ 只能改 recipe/layout/options |
| `[lock:advisory]` | 旧图还没接 bundle/spec/lock，或 caption 数字不在 claim 里 | 迁移提示；下次 ④ 重跑补上 |

⑦ 渲染前 `save_figure` 会再验一次锁；锁不过直接拒绝渲染。它允许 ⑦ 改
**recipe / layout / 配色 / 标题 / caption 文字**，但不允许改数据、字段映射、统计口径、claim。

## 4. 统一画风

**分类色、字体、字号、画布、3D 边线**的唯一来源是 [`assets/style.tokens.json`](assets/style.tokens.json)；
**连续量的色阶**仍由 `config/visualization.json` 的 `quantity_cmap` 提供（`studio.field_panel` 用
`quantity=` 取它）。两者分工写死：tokens 管“画风与版式”，config 管“物理量 → 色阶”。
不要在每个脚本里另写一套 rcParams；也不要在脚本里就地编色阶。

要点：

- **分类色**：8 色固定顺序（主蓝 `#1D4ED8` 起）。≥5 条序列必须同时用颜色 + 线型 + 标记；灰度打印下不能只靠色相。
- **语义色**：`warn` 只用于阈值/异常；`positive` 只用于增益；`highlight` 只给每图一个 callout；`muted` 只给背景对象，不当文字色。
- **连续量**：按物理量取 `quantity_cmap`（温度 inferno；水分/浓度/扩散 viridis；残差 Reds；参与 Blues；轴比 YlOrRd）。同一量跨图同色；同图多栏共用 `vmin/vmax`。
- **字体与字号**：中文 Microsoft YaHei（全宽 9 pt 正文 / 8 pt 刻度；半栏 8/7）；英文 Arial（全宽 7–8/6.5–7；半栏 7/6）。半栏图用 `studio.style(ctx, width_mm=80)` + `studio.canvas(ctx, width_mm=80)`，两者宽度要一致；任何渲染后小于 7 pt（英文 6 pt）的字都必须改布局，不许整体缩小。
- **面板短描述**：**全图不写 a/b/c 字母**（`studio.panel_label` 已是 no-op）。需要时在面板下方
  写一行短描述（物理偏移 mm，不是 axes 比例），解释留图注；没有合适描述就留空。
- **轴线**：只留左/下；网格 y 向、浅灰、在数据下方；图例白底半透明（中文模板必须，防止压曲线）。
- **3D**：只在第三维真有变量时用；`plot_surface` 平滑曲面 + 细网格边 + 合适视角；必须配二维投影/切片/等高线；禁止 3D 柱/3D 饼/瀑布替代曲面。
- **导出**：PDF/SVG 可编辑文字（`pdf.fonttype=42`、`svg.fonttype=none`），PNG 300 dpi；物理宽度是契约，**不要用 `bbox_inches='tight'` 改交付图的宽度**（预览图可以）。

完整理由、半栏字号、3D 默认视角见 [`references/style.md`](references/style.md)。

## 5. 构图：一张图只回答一个问题

常用 archetype：

| archetype | 结构 | 适合 |
|---|---|---|
| `hero_evidence` | 1 个主面板 42%–60% + 2–4 个证据面板 | 主结果 + 支撑证据；竞赛/期刊主图 |
| `asymmetric_composite` | 主面板 + 不等宽辅助面板 | 主结果明显、辅助证据异质 |
| `quantitative_grid` | 等权网格 | 多个同等重要的指标/条件 |
| `schematic_led` | 机理示意主面板 + 定量证据 | 有几何/物理对象、需要先讲机制 |
| `plate` | 机理 + 结果 + 背景的总览大图 | “一张大图讲完整故事” |
| `diagnostic_strip` | 主图 + 残差/误差条带 | 预测/拟合图要交代误差 |

规则：

- 每个面板承担**不同的推断角色**（hero / effect / distribution / uncertainty / diagnostic / comparison / composition / mechanism / sensitivity / convergence / context），不是把同一证据换一种图再画一遍。
- 面板顺序就是论证顺序：a 主结果 → b 效应/分布 → c 诊断/稳健性；不要按数据表顺序排。
- 共享轴、共享色标、共享图例；面板短描述和标题对齐；不要把图例放到数据上。
- 拼版大图要有“叙事条”或一句结论，不要只是 9 个小图拼贴。
- 参考投稿契约示例：一主多辅、manifest 记录 counts/intervals/exclusions、四格式导出、
  QA 记录。它的价值是**构图与交付契约**，不是另一套配色。

更多版式与面板角色见 [`references/composition.md`](references/composition.md)。

## 6. 渲染：④ 写 bundle，⑦ 用 `studio.py` 画

**④ 不碰画布。** 它只调 `studio.save_bundle(...)`（见 3.1），把数据/claim/字段/统计口径
锁进 `figures/data`、`figures/spec`、`figures/<id>.lock.json`。

**⑦ 是唯一渲染者。** 它读 bundle + spec，写 `figures/make_figures.py`，然后：

```python
import sys
sys.path.insert(0, "skills/figure-studio/scripts")
import studio

root = "."
ctx = studio.context(root)                 # 读模板语言/宽度/字体/labels
bundle = studio.load_bundle(root, "q3_field")   # 只读；不要改
spec = studio.load_spec(root, "q3_field")
with studio.style(ctx, width_mm=160) as settings:
    fig = studio.canvas(ctx, width_mm=160, height_mm=110, constrained=False)
    ax = studio.axes_mm(fig, 12, 20, 90, 70, width_mm=160, height_mm=110)
    studio.field_panel(ax, bundle["r"], bundle["t"], bundle["C"], ctx, kind="contour",
                       quantity="moisture", level=0.15, level_label="C = 0.15")
    studio.panel_label(fig, ax, "a", ctx, "含水率场与干前沿")
    studio.save_figure(
        fig, root, "q3_field", ctx, settings,
        sources=studio.lock_sources(root, "q3_field"),   # bundle + spec + lock + 原始来源
        script="figures/make_figures.py",
        claim=spec["claim"],                             # 必须与锁一致
        caption="问题三含水率场；红虚线为 C=0.15。",
        source_data={"a": (("t_h", "r_cm", "C"), rows)},
        meta={"intervals": "无", "exclusions": "无"},
    )
```

声明式 spec（`render.mode = "declarative"`）可以直接用现成渲染器：

```powershell
python skills/figure-studio/scripts/render_specs.py --root .
# 或把 render_specs.py 复制成 figures/make_figures.py，再在自定义分支里扩展
```

它逐图验锁：某张失败只跳过该图并报错，其余照渲 —— 一张坏图不会拖住整批。
它支持场图、剖面、配对云雨/哑铃、分布箱线、点区间、分组柱、堆叠组成、相关矩阵、
矩阵热图、ROC、Taylor、雷达、3D 曲面、轨迹、收敛、时间线、圆柱示意。需要特殊拼版的图
（SHAP 组合、和弦、环形热图、分布总装、CV ROC 等）在 spec 里写 `render.mode="custom"`，
由 ⑦ 在 `figures/make_figures.py` 里用 `studio` 的对应 recipe 自己排。

`save_figure` 会：

1. 先跑 `figure_lock.verify_one`；数据层/契约不一致就**拒绝渲染**（不会用旧数据画新图）；
2. 写出每个面板的 tidy CSV 到 `figures/source_data/<id>__<panel>.csv`；
3. 调 `lib.visualization.export` 导出 PDF/SVG/PNG 并登记 `figures/manifest.json`；
4. 写 `figures/<id>.meta.json`（language/template/width/font/claim/caption/source_data/counts/intervals/exclusions/spec/lock）；
5. 在项目树内时，把 `studio.py`、`resolve_context.py`、`style.tokens.json`、当前语言的
   `labels.*.json` 自动加进 `sources` —— 改画风/词表会让相关图被判过期，避免交付旧像素。

已实现 recipe 见 `studio.py` 的 `field_panel / profile_panel / paired_raincloud / paired_dumbbell /
dot_interval / grouped_bars / stacked_composition / correlation_matrix / scatter_matrix /
prediction_marginal / roc_panel / taylor_panel / radar_panel / surface3d_panel /
trajectory_panel / convergence_panel / timeline_panel / cylinder_schematic /
shap_combo / roc_curve_ci / split_violin_corr_matrix / circular_heatmap /
distribution_composite / chord_diagram`。
未实现的 recipe 在 `recipes.json` 里标 `external`，按 `references/catalog.md` 适配，不要假装已内置。

## 7. 门禁：机器能查的 + 必须眼睛看的

机器：

```powershell
python -m lib.visualization audit
python skills/figure-studio/scripts/figure_lock.py verify --root .
python skills/figure-studio/scripts/audit_studio.py --root .
```

`audit` 查：登记/过期/自动检查/目检签名；`figure_lock.py` 查：bundle/source 哈希、
spec 语义部分、claim 与统计口径、渲染后 meta 的 claim 是否仍与锁一致；`audit_studio.py`
查：语言/宽度与模板一致、逐面板来源数据与 counts、`meta` 是否齐全、脚本里有没有
`cmap=jet/rainbow`、是否使用 `studio.style`/`charts.style`、图内文字行有没有内部文件名。
`audit_studio.py` 已内置锁检查；单独跑 `figure_lock.py` 是为了看 `[lock:data]` /
`[lock:contract]` 的分类。字号/字体的最终判据是 `export` 的最小字号 + 目检。

眼睛（必须打开实际 PNG/PDF，在最终物理尺寸看）：

- [ ] 图例不压曲线、文字不压文字、轴标签没有被裁；
- [ ] **信息密度**：没有“一大片空白只用上很小一块”（右侧 55% 空白、九宫格只用 1 格、
      色标只用 2–3 档都算失败）；
- [ ] 灰度下仍能区分 ≥5 条序列；
- [ ] 场图不是一片死色；低值平台有 gamma 或改剖面；
- [ ] 3D 视角可读、遮挡交代、配了二维投影；
- [ ] 图里说的和 claim/正文一致；数值与 results 对得上；
- [ ] 中文图没有英文解释句；英文图没有中文解释句；
- [ ] 统计：n、区间定义、配对单位、排除规则都写清；没有假 p 值/假 CI。

逐项清单、统计与 source data 合同见 [`references/qa.md`](references/qa.md)。
统计口径见 [`references/statistics.md`](references/statistics.md)；来源数据/FAIR 见 [`references/source-data.md`](references/source-data.md)。

## 8. 与 17 阶段的关系（④/⑦ 已解耦）

| 阶段 | 它负责 | 它不负责 |
|---|---|---|
| ④ 编程实现 | 数据、claim、FigureBrief、`figures/data` + `spec` + `lock` | **不画布、不写 `figures/make_figures.py`、不导出 PDF/PNG** |
| ⑦ 技术路线图/绘图 | **所有数据图渲染** + 图型/构图/配色/面板/图注文字 + 非数据图 | 不改 `figures/data`/`spec` 语义/`*.lock.json`、`code/`、`results/`、claim 语义 |
| ⑧ 绘图门禁 | 只判不改；按本 skill 的 QA 清单复核；先跑 `figure_lock.py verify` | 不自己改图；`[lock:data]` 交回 ④，其余 FAIL 回 ⑦ |

- ⑦ 的权限：**换图型/拆面板/重排构图/改配色/改图注文字**，以及写 `figures/make_figures.py`。
  它不能动数据层：bundle/spec 语义/锁由 ④ 写，`save_figure` 渲染前会验锁。
- ⑧ 必须读实际 PNG，并在报告里写“我看到了什么”；只跑 audit 不算完成。
- 项目仍是 17 个阶段，`7Route-diagram` 的 id 不变；本 skill 是 ④/⑦/⑧ 共享的方法库，不新增阶段。

迁移已经落地（第二阶段）。完整契约、权限、回退路由与向后兼容见
[`references/decoupling.md`](references/decoupling.md)：

1. **④**：`save_bundle` → `figures/data/<id>.npz` + `figures/spec/<id>.json` + `figures/<id>.lock.json`。
2. **⑦**：读三件 → `figures/make_figures.py` 渲染 → `save_figure` 写 PDF/SVG/PNG、source data、meta。
3. **⑧**：`figure_lock.py verify` 分 `[lock:data]`（回 ④）与 `[lock:contract]`（回 ⑦）。

## 9. 四个功能模块的边界

| 模块 | 负责 | 不负责 |
|---|---|---|
| **数据图型库**（`data-recipe-library`） | 分布、关系、归因、模型诊断；11 个通用模板全部有实现 | 不处理 draw.io 流程图；不把不适配的数据硬套模板 |
| **比较与拼版**（`comparison-and-composition`） | 分组比较、消融、组成、hero+evidence、plate 总装 | 不做数值变换；不把无叙事关系的图拼在一起 |
| **投稿契约与质控**（`publication-contract`） | FigureBrief、统计口径、source data、导出与目检门禁 | 不替 ④ 决定 claim；不替 ⑧ 改图 |
| **场图与 3D 内核**（`field-and-3d-core`） | 场图/等高线/3D 曲面、语义色阶、导出台账、目检签名 | 不单独成入口；不绕过 `lib.visualization` 另写一套 |

外部参考只提供设计原则与数据契约，不复制代码，也不把外部仓库放进项目。第三方来源、版本与
许可证在项目外的参考目录维护，不进入本仓库。

## 10. 禁止清单

- 不要把外部模板的模拟数据直接当结果；替换数据、样本量、模型名和统计标注。
- 不要为了“图好看”改数值、删点、平滑、截断而不在图注说明。
- 不要在没有真实标签时画 ROC/PR/校准；不要把 AUC≈1 当模型强的证据。
- 不要在没有真实区间时画误差棒/CI；不要把标准差叫 95% CI。
- 不要用 3D 柱、3D 饼、瀑布替代 3D 曲面；不要只有 3D 没有二维投影。
- 不要在 CUMCM 图里写英文解释句；不要把内部文件名（result3.xlsx、2026A、figdata_sens.npz）写进图内文字。
- 不要在 ⑦ 改 `figures/data`、spec 的 fields/field_mapping/claim/statistics、`*.lock.json`；要改就交回 ④。
- 不要在登记路径之外渲染交付图；诊断图落 `tmp/`。
- 不要把“跑完 audit”当成“看过图”；没有 Read PNG 记录的复核不算。

## 11. 文件地图

```text
skills/figure-studio/
  SKILL.md
  assets/
    style.tokens.json        # 分类色/字体/字号/画布/3D 边线来源
    labels.zh.json           # 中文图内词表
    labels.en.json           # 英文图内词表
    figure-brief.schema.json # 图意契约
    recipes.json             # recipe 目录（机器可读）
  references/
    catalog.md               # 42+ 图型的数据契约、适用/禁用/退路
    composition.md           # hero+evidence / plate / 面板角色
    style.md                 # 配色、字体、字号、3D、导出理由
    language.md              # 模板语言解析与中英规则
    qa.md                    # 机器/眼睛/统计/source data 清单
    statistics.md            # n、区间、p 值、多重比较
    source-data.md           # 逐面板 CSV、counts/intervals/exclusions
    ecosystem.md             # 外部参考与授权原则（不记录第三方名称）
    module-map.md            # 数据图型库/比较与拼版/投稿契约的逐项落点与实现状态
    decoupling.md            # ④/⑦ 解耦契约、figure_lock、权限与回退路由
  scripts/
    resolve_context.py       # 模板 -> language/width/font/labels
    check_brief.py           # FigureBrief 校验
    studio.py                # 统一 style + recipe + save_bundle/save_figure + render_spec
    figure_lock.py           # 数据包/spec 语义/source/claim 的锁：build/verify
    render_specs.py          # ⑦ 的默认声明式渲染器（可复制成 figures/make_figures.py）
    audit_studio.py          # 语言/来源数据/figure lock/脚本静态检查
    check_selection.py       # 候选/选中记录与“折线赢家必须有过非折线候选”
    check_figure_mix.py      # 图级判重（plate 已画的 3D）+ 折线预算
    smoke_recipes.py         # 六个通用模板的合成数据冒烟渲染
```

## 12. 一句话验收

> 把图给一个没读过论文的人看 10 秒，他能说出这张图在证明什么；把图缩到最终纸面尺寸，图例不压线、字不糊、灰度能分清；把图注遮住，图里的数和正文对得上；`figure_lock.py verify` 没有 `[lock:data]`/`[lock:contract]`。四条都过，才算画完。
