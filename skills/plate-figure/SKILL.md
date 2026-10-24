---
name: plate-figure
description: "Nature-style composite plates for the main paper figures. Use when a question needs a designed plate (headline + hero + supporting panels + KPI band) rather than a standalone chart. Ships reference layouts (current-problem Q1 schematic, Q2 3D surface, Q3 field, Q4 cross-sections) and a shared style module; the figure language and font follow the paper template (reports/FIGURE_CONTEXT.json), not a hard-coded Chinese default."
allowed-tools: PowerShell, Read, Write, Edit, Grep, Glob, Bash
---

# Nature-style 合成图（plate）

论文主图不是“一张 chart + 图例”，而是一整版 **plate**：一个 hero 面板占 40–55%
面积，其余面板按证据链排成不等宽马赛克，底部一条 KPI 条收束。图内**不写整图标题**；
正式标题/图注交给 ⑨/LaTeX，需要时只用 6–7 pt 常规字写一句 claim 补充。参考图已复制
进项目：`skills/plate-figure/assets/references/composite_1–3.png`（只看版式语法，
不抄内容；见同目录 `README.md`）。不要依赖项目外的参考图路径。

**图内语言 = 论文模板语言**：读 `reports/FIGURE_CONTEXT.json` 的 `language` / `font`
（CUMCM 当前解析为中文、Microsoft YaHei；英文模板则是英文、Arial），不要在图脚本里
硬写中文或中文字体。图内只放：面板短描述（**不写 a/b/c 字母**）、直接标注、KPI，以及可选的
6–7 pt 常规 claim 补充；**不放整图标题/kicker/副标题**。**不放** “Panel a: …” 这类说明句，不放数据来源脚注，不放
“RESULTS · …” 英文 kicker。口径、来源、排除规则写进 `figures/manifest.json` 的 caption
或 LaTeX 图注；图内说明句一律视为不合格。

## 构图自己设计（不要套模板）

`templates/` 里的几张只是**当前题已经生成过的参考实现**，不是菜单，也不是必选项；
**问数由题目决定（可能 3 问、5 问，不要假设正好四问）**，每问一张，问数少就少画、
问数多就按同一语法再设计。不要整份复制；复制会得到同一骨架，`check_plate.py` 会把
两张 `axes_mm` 矩形完全相同的 plate 判为“构图重复”。正确做法：从这一问的 claim 出发，
自己决定

1. hero 放什么（场/3D/示意图/截面条），占多大；
2. 需要哪 2–4 个 supporting panel，每个回答哪半句；
3. 怎么排（左 hero + 右 stack、上宽 3D + 下三栏、三时刻截面条、时间轴 + 局部放大……）；
4. 底部是 KPI 条、短 claim 条，还是不要底条。

参考实现（仅供看语法，不是模板编号）：

| 问 | 当时的设计 | 文件 |
|---|---|---|
| Q1 预热 | 左剖面示意（湿芯/干皮）+ 右 2×2 + KPI 条 | `templates/plate_q1_schematic.py` |
| Q2 物性 | 上宽 3D 曲面（sci-box 07 风格）+ 下排切片/物性/KPI | `templates/plate_q2_surface.py` |
| Q3 干前沿 | 左上场图 + 右上剖面族 + 右下敏感性分布 + 左下收敛 | `templates/plate_q3_results.py` |
| Q4 收缩 | 左侧三时刻截面条 + 右上 R(t) + 右下固定 R 对照 | `templates/plate_q4_crosssections.py` |

新题如果四种都不合适，就设计第五种；不要为了“有模板”把图塞进现有骨架。

## 共享样式

- `skills/plate-figure/assets/plate_common.py` 提供字体（`setup()` 从
  `reports/FIGURE_CONTEXT.json` 读取；CUMCM 当前为 Microsoft YaHei、英文模板为
  Arial 等）、语义色、`claim_note()`（`header()` 已废弃为 no-op）、`caption_below()`、`kpi_block()`、`clean()`、`save()`。
  每个 plate 以
  ```python
  ROOT = Path(__file__).resolve().parents[1]
  sys.path.insert(0, str(ROOT / "skills" / "plate-figure" / "assets"))
  import plate_common as P
  ```
  引入，不要复制第二套字体/配色。
- 参考实现里的 `ROOT = parents[1]` 是按“脚本在 `figures/`”写的；在 templates 目录里
  直接运行会指错根目录，属正常。

## 版式语法（硬要求）

1. **不写整图标题**：标题/图注归 ⑨ 的 LaTeX `\caption`。若图内需要一句 claim 补充，
   用 `plate_common.claim_note()`：6–7 pt、常规字重、灰色/墨色，放在图内空位
   （中间或下边），**不要放顶部、不要加粗**，不要让它看起来像标题。
   例：Q2 的「扩散系数跨 4.2 个数量级」放在 3D 曲面下方的空位，6–7 pt 常规字，
   紧贴图而不是横在画布顶部。
2. **hero 面板**：占 40–55% 面积；场图/3D/示意图优先。其余面板明显更小，按 a→b→c 阅读。
3. **不等宽马赛克**：不要 2×2 等分四宫格；允许上排 35/65、下排 60/40 这类不等宽。
4. **面板描述**：**全图不写 a/b/c 字母**（用户 2026-10-23 明确要求；`check_plate`
   会把 `(a)`–`(d)` 判 FAIL）。需要时只在每个面板**下方**写一行短描述
   （如 `径向剖面`、`湿芯 / 干皮`），描述只写图名/口径，不写整句；没有合适描述就留空，
   不要用字母占位。上下叠放时给下方描述留出上一面板 x 轴刻度的高度。
4b. **KPI 单行**：2–4 个 KPI 只要横向放得下，就排成**一行并排**（参照
   本套 plate 里已经排成一行的那张的底部：值在上、标签在下，无框、无底板、彼此贴紧）。
   不要 2×2 宫格，也不要把 KPI 塞进带边框的卡片。**KPI 放在它所总结的面板
   caption 正下方**（例如「三时刻截面」这行描述下面），不要甩到整张 plate 的底部或
   顶部；值/标签成组贴近，组间距不要拉满画布。只有侧栏窄于
   `4 × 17 mm` 时才允许竖排（`plate_common.kpi_block` 会按宽度自动决定；
   宽块里即使传 `cols=2` 也会展开成一行）。
5. **一套语义色**：蓝=数据/湿区，红=阈值/事件/干前沿，绿=收敛/验证，琥珀=边界/蒸发。
   同一语义跨面板同色；不引入彩虹色。
6. **直接标注**：曲线末端直标、事件点用星/圆 + 短引线；不要给每条线都加图例框。
7. **留白**：plate 近白像素 69–80%；hero 之外不要塞满。不要阴影、发光、3D 装饰。
8. **字体**：模板语言字体（CUMCM→Microsoft YaHei，英文→Arial）；正文 6–7 pt，最小 5 pt；
   PDF 保留可编辑文字（`pdf.fonttype=42`, `svg.fonttype='none'`）。
9. **导出**：`fig.savefig(..., dpi=300)` PNG + PDF；不要 `bbox_inches='tight'`。
10. **数据诚实**：每个数字可回溯到 `figures/data/*.npz` 或 `results/*.json`；不得为好看改
    claim，不得把删失下界画成实测点，不得用合成数据补面板。
11. **图内不放说明句/脚注**：`Panel a: …`、`Panels a–b: …`、`Note:`、`Appendix-…`、
    英文 `RESULTS · …` 都会被 `check_plate.py` 判失败。把 provenance 写进 manifest caption。
12. **构图必须不同**：任意两张 plate 的 `axes_mm` 矩形集合不能雷同；`check_plate.py`
    机械核对。问数不是固定的——每问一张，有几问画几张。
13. **语言/字体跟模板**：`check_plate.py` 读 `reports/FIGURE_CONTEXT.json` 的
    `language`/`font`；中文模板要求中文标题/标注（CJK≥20），英文模板要求英文
    （拉丁字母≥40），不会把中文当成唯一合法语言。

## 与 sci-box 模板的关系

`scientific-figure-making` / `mathmodel-figure-templates` 的 11 个模板是**单图型**模板，
不是 plate。本题可直接用的：

| # | sci-box 模板 | 本题是否适用 | 依据 / 怎么用 |
|---|---|---|---|
| 01 | 多分类 SHAP 组合图 | 否 | 没有分类器/特征归因；这是确定性 PDE，不是 ML 模型 |
| 02 | 配对云雨图 | 部分 | 需要**配对样本**；本题只有单因素扰动 vs 基线，不是配对重复。可借“半小提琴 + 散点”语法，不要伪造配对 |
| 03 | 交叉验证 ROC + CI | 否 | 没有二分类标签/概率输出 |
| 04 | 多模型泰勒图 | 否 | 只有一个模型；没有多模型 vs 观测场，不能硬凑 |
| 05 | 相关矩阵组合图 | **部分（split-violin 已用）** | 相关矩阵部分不适用：确定性场的空间自相关是构造出来的（21 个径向 T 序列的 Spearman 中位数 ≈0.99999），不是独立样本；**背靠背半小提琴**适用，已实现为 `split_raincloud` / `field_split_raincloud`（按时间窗分组、中心区 vs 表面区）。**q2_3h 的温度面板直接用这个 split-violin**（模板 05 右上那种中心区/表面区背靠背分布；原始 T 后段时间差小，优先用 ΔT=T−⟨T⟩_r）；它替代温度热力图，场上限留给 q3_dryfront 的干前沿。含水率面板可保留折线剖面，不要再加第二张雨云 |
| 06 | 预测-真实边缘分布图 | 否 | 没有实测目标场；只有误差上界（Bessel/制造解），没有逐点 prediction–truth 对 |
| 07 | TPE 调参 3D 曲面 | **是（已用）** | **Q2 的 3D hero**：`plot_surface` + `coolwarm` + 色条；见 `plate_q2.py` |
| 08 | 相关矩阵 + 半小提琴 | 部分 | 相关矩阵不适用；**半小提琴**语法用于 Q3 敏感性分布 |
| 09 | 分组环形热图 | 否 | 没有组成/占比数据；环形排布反而降低可读性 |
| 10 | 堆叠 + 云雨 + 箱线 | **部分（已实现）** | 借**半小提琴 + 散点 + 中位线**；`studio.raincloud` / `studio.field_raincloud` 已提供该语法。每组 n=3–5 时不要硬画密度，退化为点 + 中位线 |
| 11 | Nature 风格和弦图 | 否 | 没有类别间流量/组成转移；强行画会把流程图变成装饰 |

结论：**只有 07 是完整套用；08/10 只借分布语法**。其余 8 个不是“画风不适配”，
而是数据形态不对（缺分类标签、多模型/观测、重复样本、相关样本或组成流量）。
不要为了“用上模板”硬画；硬套会变成装饰图或假统计，数据诚实那一条先不过。

### 部件拼接：部分适配就拼，不要整张放弃

sci-box 模板是**单图型语法**，不是“整张图要么全用、要么不用”。一个面板适配，
就把它和本题的场图/折线/柱拼在一张 plate 里；不适配的部件不画。可拼的部件：

| 模板 | 可拼的部件 | 拼接示例 | 不要拼的 |
|---|---|---|---|
| 05 | 背靠背半小提琴（中心 vs 表面、前窗 vs 后窗） | q2_3h：05 split-violin（T 或 ΔT）+ 一条含水率折线 | 相关矩阵、分组树（确定性场没有独立样本） |
| 08 | 半小提琴 + 点 + 中位线 | 敏感性分布 + 场图/折线 | 相关矩阵本身 |
| 10 | 半小提琴 + 箱线 + 堆叠条 | 多时刻分布 + 分组柱 | 没有组成总和的堆叠 |
| 07 | 3D 响应面 | Q2 3D hero + 2D 投影/切片 | 没有第三维含义时硬上 3D |
| 02 | 配对云雨（有配对 ID 时） | 前后测分布 + 折线 | 没有配对 ID 时伪造配对 |
| 06 | 预测-真实边缘分布（有观测/预测对时） | 误差分布 + 残差 | 没有实测目标场时 |

拼接只允许**一个面板一种语法**；不要把两个模板的整套布局硬塞进同一张。每个面板
仍要写清 claim/字段/统计口径；不能因为“模板好看”引入假相关、假 p 值或假配对。

需要单图样式时：

```bash
python skills/mathmodel-figure-templates/scripts/render_template.py --list
python skills/mathmodel-figure-templates/scripts/render_template.py rf-tpe-surface
```

把它们产出的单图并入 plate 时，仍按本 skill 的面板短描述/语义色/模板语言字体统一，
不要让单图自带一套字体和配色。

## 生成流程

1. 先读 `reports/FIGURE_PLAN.md`、`reports/RESULTS_REPORT.md`、对应 `figures/data/<id>.npz`
   和 `results/*.json`，写清：plate 的 hero claim、2–3 个 supporting claim、caption 口径
   （写进 manifest/LaTeX，不要写回图内）。
2. 在 `figures/plate_<id>.py` 里**自己搭构图**（脚本名决定登记 id `fig_<id>_plate`）。
   可以参考 `templates/` 的写法，但不要整份复制；先让脚本跑通，再调版式。
3. 跑 `python figures/plate_<id>.py`，打开 PNG 目检：claim note 不压面板、hero 不空、引线不穿字、
   最小字号 ≥5 pt、面板描述对齐、图内没有说明句。
4. 与另外三张 plate 对照：骨架是否明显不同？如果看起来像同一张图的换数据，重新设计
   本图的 hero/面板/排布，而不是换模板。
5. 跑 `python figures/make_plates.py`，再跑
   `python skills/plate-figure/scripts/check_plate.py --root .`；检查器会同时核对
   模板语言、版式唯一性、manifest 登记与视觉复核。
6. 登记：`figures/fig_<id>_plate.png/.pdf` 写入 `figures/manifest.json`，claim/caption 用
   plate 的 caption（可以写口径，但**不要**写回图内）；再做视觉复核。
7. 数据层的 `figures/data`/`spec`/`lock` 不动；plate 只读 bundle，不重算模型。
