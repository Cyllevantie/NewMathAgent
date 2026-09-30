# DrawIO 图示生成报告（`7Route-diagram` / 8drawio · 2026-09-29 第 3 轮）

> 本阶段只产/维护**图件**：非数据图（技术路线图、几何示意、耦合结构、动边界示意）由本阶段生成；
> **数据图的"画得好不好"**（图例落点、坐标区宽窄、刻度标签、等值线层、标注落点、caption 数字现算改正）
> 自 2026-09-26 起也由本阶段**就地改**（`skills/7Route-diagram/SKILL.md`「阶段边界」）。
> 本阶段**不重跑模型、不改 `code/`、不改 `results/` 的数值件、不改公共库 `lib/visualization/*.py`、
> 不改 `config/visualization.json`、不改前序报告的数值结论**。
>
> **本轮是 ⑦ 在本赛题上的第 3 轮**。本轮开工时的盘面 = 上一轮结束时被判 FAIL 的盘面，
> 由驱动存档在 `产物/cache/2026A_2026.9.29_21.31.50/技术路线图/快照/`（`.snapshot.json` 记 `at=21:10:22`）；
> 上一轮的 `DRAWIO_REPORT.md` 也已由驱动移入
> `产物/cache/2026A_2026.9.29_21.31.50/技术路线图/DRAWIO_REPORT.md`。本报告是它的**续版**：
> §2/§3/§7 中与本轮改动无关的内容照旧保留（图示清单、未生成原因、嵌入建议）。
>
> 用户随本轮送来的返修回执是 `runtime/quality/feedback/a705ae79/f8efc38e/`
> （`stage=figreview`、`status=FAIL`、**`target=drawio`**、**1 条 soft issue** + 2 条 info advisory）
> —— 这是**点名本阶段**的回执，逐条复验见 §1。

## 1. 回执 `a705ae79/f8efc38e` 的逐条复验

回执只有 **1 条 issue**（soft / `diagram` / 判据 `readability`），落在本阶段的**就地白名单**内
（改调用方的标注落点 = 画法，不碰任何数值/坐标范围/色阶），故**就地改**，未写 `HANDBACK_REQUEST.md`。

### 1.1 `fig-5-caliber-baseline-through-label`（soft · `readability`）—— 已落地 ✅

**问题**（回执原文的口径，本阶段独立复量后一致）：`figures/caliber_sensitivity.png` 的
**主档基准红虚线**（`figures/make_figures.py` 的 `ax.axvline(vals[0]=57.15, color=WARN, lw=1.2,
linestyle="--")`，**整高**）在交付 dpi 下落在显示列 `x=1086.3`，而数值标注「**56.85**」
（`env_plateau` 档，与基准线只差 0.30 h）的字框是 `x[1078.7, 1140.7]` ⇒ **竖线从首位数字的字身中间纵贯**
（线在框内 7.7 px）。相邻的「56.97」（`env_peak` 档）字框左缘 `1088.8` 只在基准线右侧 **2.4 px 擦过**、
字身未压。

**处置**：把**这一行**的标注翻到点的**左侧**（`xytext=(-6, 0)` + `ha="right"`）。判据按**实测字框**定，
不写死档名与下标（档值一变就漏）：画完一版、量每段标注的显示字框，凡「点在基准线左侧、且字框含
基准线列」的才翻；只往一个方向翻 ⇒ 一趟即收敛，且「只擦框不压字」的 56.97 **不会被误翻**
（这正是回执"不许让它变坏"的要求）。**数值、坐标范围、色阶、参考线本身一律未动**；
**没有**改用 `xmax=`/`ymax=` 截线（那会改掉 `axvline` 的 `get_xydata()`，`[0,1]` → `[0,截点]`，
按 `transAxes` 判别 `axvline` 的复量探针随即失效、退到 `transData` 分支把轴分数当数据坐标读 ⇒ 读出伪影 ——
同 `q3_criteria` 处的注释）。

| 行 | 档 | 取值 /h | 改前字框 | 改后字框 | 改前净空 | 改后净空 |
|---|---|---|---|---|---|---|
| y=4 | `env_plateau` | 56.85 | `x[1078.7, 1140.7]`（含基准线 ✗） | `x[980.0, 1042.0]` | **−7.67 px** | **+44.34 px** |
| y=3 | `env_peak` | 56.97 | `x[1088.8, 1150.8]` | **一字未动** | +2.44 px | +2.44 px（未变坏） |

**复验（逐条按回执的 `recheck` 做，全部达标）**：

| recheck 要求 | 实测 | 结论 |
|---|---|---|
| 重跑 `_tmp/fig8b_line_text_cross.py` `ref` 模式 ⇒ `caliber_sensitivity` 命中数 **0** | 13 张全报「线穿字：无」，`caliber_sensitivity` 也**整节为空**（`_tmp/dr7c_cross_ref_after.txt`） | ✅ 0 |
| 同上 `all` 模式 | 唯一残留是 `数据线 _nolegend_ 穿过 '53.05'` —— 回执自己判过的**探针假阳**，三路取证见下 | ✅ |
| 放大交付像素目检 `56.85` 与 `56.97` 两处无压字 | `_tmp/fig8_crops/dr7c_deliv_5685_r3.png`（×6）、`dr7c_deliv_5697_r3b.png`（×8）、`dr7c_deliv_two_r3b.png`（×4）逐张打开：56.85 在其蓝点左侧、红线不经过其任何字形；56.97 在右侧，红线只从首字「5」**左侧的留白**穿过、笔画未触及 | ✅ |
| `figures/caliber_sensitivity.png` 的 sha256 列出 | `95be558ab65f5bd0…` → **`39a7dea5766cb249cc3f64ce8f562526244f73f7274c775b5a155dd1084ab801`** | ✅ |
| `_tmp/fig8_repro_check.py` 仍 13/13 | **13/13 逐字节相同**（收口复跑） | ✅ |
| `python -m lib.visualization audit` 仍 PASS | `{"status": "PASS", "issues": []}`、退出码 0 | ✅ |

**独立复量探针（本轮新写，`_tmp/dr7c_annotation_geom.py`）**：走生产入口渲到 `_tmp/dr7_render/`
（sha256 自证 == 交付 PNG），逐行列出 7 档的取值、字的显示框、基准线列、横向净空：

```
基准竖线：数据 x=57.1500 h  显示列 x=1086.3（lw=1.2 pt ⇒ 半宽 1.83 px）；坐标区 80.1 mm；标尺 86.69 px/h
 档   取值/h    x点     字框 x0   字框 x1   净空(线↔框)  线在框内?
  1  57.1833  1089.2   1107.6   1169.6      21.22       否
  2  56.8500  1060.3    980.0   1042.0      44.34       否     ← 本轮翻面（ha=right, xytxt=(-6,0)）
  3  56.9667  1070.4   1088.8   1150.8       2.44       否     ← 一字未动
  …（其余 4 档净空 18.3–275.1 px）
⇒ 字框含竖线的标注数 = 0（判据 0）；⑧ 口径命中数 = 0（判据 0）
```

**`all` 模式那一条残留命中的判假取证（`_tmp/dr7c_cross_filter_false_positive.py`）** —— 回执给的判别式是
"线是否真画出来"，本阶段三路取证：

```
① 逐条 Line2D 的绘制属性：
   #0 label='_nolegend_'  linestyle='None' lw=1.3 visible=True marker='o' ⇒ 真画出墨迹？**否**
   #1 label='_child1'     linestyle='--'   lw=1.2 visible=True marker='None' ⇒ 真画出墨迹？是
② 只对「真画的线」重跑 ⑧ 同一套相交判据 ⇒ 命中数 = **0**
③ 交付像素：该连线本该经过的空走廊 x[816,1046] × PIL 行[600,607] 内 palette[0] 蓝像素 = **0**
   （对照：同一行上 '53.05' 自己的标记内该色像素 = 120 ⇒ 色判有效、行号没取错）
```

⇒ 那 29 个"入框采样点"来自 `comparison()` 里 `errorbar(fmt="o")` 的**连线**，其 `linestyle=None`
**根本不绘制**，属探针假阳（**未改 ⑧ 的探针**，这一条按回执给的过滤规则另行取证）。

**改动面的独立性**：本轮对 `figures/make_figures.py` 的逐行 diff 只有两处（标注的收集方式 + 上述自适应
判据，见 §5），**其余一字未动**；`figures/*.png` 相对驱动快照**只有 `caliber_sensitivity.png` 一张**画面变化
（§6）。

### 1.2 两条 info advisory（不拦链，本阶段照登记）

| id | 内容 | 本阶段处置 |
|---|---|---|
| `adv-roadmap-print-font` | `fig_roadmap` 按登记宽 138.7 mm 排印折算字号 ≈ 6.6 pt < `min_font_size=8` | **不在 ⑦ 的处置面**（实测提字号会被 `check_layout.py` 判 14/24/38/49 条版式失败 ⇒ 等于重排整张图）。按 `docs/VISUALIZATION.md` 第 6 条归 **⑭format** 定夺；本轮该 PNG 逐字节未变。见 §7 待办。 |
| `adv-analysis-d-drop-3mm` | `reports/ANALYSIS_MODELING_REPORT.md:358` 的「$D$ 的下降只发生在最外层 3 mm」是无口径量级句 | **不是 ⑦ 的产物**（③ analysis 的报告），本阶段**未改**；已在 §8 登记。 |

## 2. 图示清单

| 文件（`figures/`） | 类型 | 来源依据 | 论文用途（采用状态） | 状态 |
|---|---|---|---|---|
| `fig_roadmap.drawio` · `.pdf` · `.png` | **五带技术路线图**（彩色，全文唯一的大图） | `figures/fig_roadmap.content.json`、`request/problem.md`、`ANALYSIS_MODELING_REPORT.md`、`RESULTS_REPORT.md`、`results/q3.json`、`results/q4.json`、`results/sensitivity.json` | **正文图 1「分析流程图」**，排在问题重述之后、问题分析之前（`1_restatement.tex` 末尾） | 上一轮产出；**本轮未动**（PNG 与快照逐字节相同）；已登记 / 已复核 |
| `fig_geometry` · `.pdf` · `.svg` · `.png` | 几何示意（轴测圆柱 + 径向截面与网格，灰阶半栏 80 mm） | `request/problem.md`（L、R₀）、`ANALYSIS_MODELING_REPORT.md` §4.1/§4.3 | **正文**：问题重述 / 模型建立 | 上一轮产出；**本轮未动**（PNG 逐字节相同）；复核签名仍有效 |
| `fig_coupling` · `.pdf` · `.svg` · `.png` | 传热传质耦合结构图（灰阶半栏 80 mm） | `request/problem.md`（h、h_m）、`ANALYSIS_MODELING_REPORT.md` §4.1/§4.3 | **正文**：写出控制方程与定解条件之后 | 同上 |
| `fig_q4_material` · `.pdf` · `.svg` · `.png` | Q4 动边界与材料坐标 ξ 示意（双面板演化，灰阶半栏 80 mm） | `results/q4.json`、`request/attachments/附件2.xlsx`（现算 R(t_dry)）、`ANALYSIS_MODELING_REPORT.md` §9.3 | **正文**：问题四的动边界 / 坐标变换小节 | 同上 |
| 13 张数据图（`q1_field` … `convergence`） | 填充等高线 / 折线族 / 响应面 / 柱状 / 横排点图 | 各自 `code/outputs/figdata_*.npz` 与 `results/*.json` | 正文与附录（见 `reports/FIGURE_PLAN.md` 的逐张清单） | **本轮 1 张改像素**（`caliber_sensitivity`，§5）；其余 12 张 PNG 逐字节相同；13 张全部重渲 + 重登记 + 重签复核 |
| 2 张稳健性图（`rb_tornado`、`rb_uncertainty`） | 龙卷风图 / 直方图 + 代价曲线 | `code/outputs/figdata_sens.npz`、`results/sensitivity.json`、`tmp/rob/out/*.json` | 由 `6Robustness` 生成，附录（检验节） | **本轮未动**（PNG 逐字节相同），复核签名仍有效 |

生成脚本三支，都住 `figures/`：`figures/make_figures.py`（13 张数据图）、
`figures/make_robustness_figures.py`（2 张稳健性图，**属 `6Robustness`**）、
`figures/make_flow_figures.py`（3 张灰阶示意图）；
技术路线图的**可复现内容源**是 `figures/fig_roadmap.content.json`，渲染器是
`skills/paper-diagram/scripts/roadmap_5band.py`。

### 尺寸口径（不是把 160 mm 缩小）

📌 模板 preamble 的 `geometry` 是 `left=2.50cm, right=2.18cm` ⇒ **`\textwidth` = 163.2 mm**。

| 图 | 设计/登记宽 | 依据 | PNG 实测 | PDF MediaBox |
|---|---|---|---|---|
| `fig_roadmap` | 954 px 画布；登记 **138.7 mm** | 论文按 `0.85\textwidth` = **138.72 mm** 排（`lib/web/check_skeleton.py` 机械核 ≥0.85 栏） | 954 × 1297 | 242.4 × 329.1 mm |
| 三张示意图 | **80.0 mm** | `0.49\textwidth` = **79.97 mm**，给 `\paperfigurepair`（并排）或半栏 `\paperfigure` 用 | 944 × 755 / 944 × 755 / 944 × 685 | 80.0 × 64.0 / 80.0 × 64.0 / 80.0 × 58.0 mm（**1:1**） |

> 80 mm 在 config 的 `dpi=220` 下只有 693 px、过不了 `quality.minimum_width_px=800`，
> 故这三张**逐图 `settings["dpi"] = 300`**（只作用于本脚本），80 mm → 944 px。

### 配色口径（`fig_roadmap` 是唯一彩图）

- **`fig_roadmap`** 由 `roadmap_5band.py --theme semantic` 渲染，**从 `config/visualization.json`
  的语义键现取**：节点框 `fillColor=#E2E8F0`（`grid`）、`strokeColor=#475569`（`line`）、
  字色 `#1F2937`（`ink`）；标题条与旗标走 `palette[0]` `#1D4ED8` 一族；
  **全图唯一一处 `warn` `#EF4444`** 落在写着判据阈值 `0.15` 的那一格 —— 与
  `config` 的 `_palette_note`（「`warn` 只用于阈值/异常/警示」）逐字一致。本轮**未改**
  `config/visualization.json` 的 `palette` 或任何语义键（§6 的哈希可核）。
- **三张示意图**色值同样取自语义键（浅底 `grid` + 深灰边 `line` + 黑字 `ink` + 辅助线 `aux`），
  **刻意不引用** `visualization.schematic.MAIN/ACCENT`（那套蓝橙按 SKILL 只给 `fig_roadmap`）。
- **`q2_diffusivity` 的表面状态轨迹**自上一轮起由 `warn` 红改为 `palette[0]` 蓝 ——
  全项目「红色 = 阈值/基准/警示」这条语义无例外（本轮该图未动）。
- 本轮改的 `caliber_sensitivity` **只挪了一处数值标注的落点**，未动任何颜色：图上唯一的红仍是
  主档基准虚线（阈值/基准语义），与上一条一致。

## 3. 未生成图示及原因

| 图型 | 是否生成 | 说明 |
|---|---|---|
| `fig_flow_q1`…`fig_flow_q4`（各问求解流程图） | **不生成** | 四问是**同一套确定性骨架**、差别只在物性与时间窗（`ANALYSIS_MODELING_REPORT.md` §4.1），逐问画会得到四张几乎相同的图；求解路线由 `fig_roadmap` ③ 带承载。 |
| 求解流程图（含 Picard 迭代回路） | **不生成** | 交付档是**半隐式欧拉（系数滞后一步、不迭代）**（§13 统一代码契约）⇒ 画一圈"迭代收敛"回路会是**假证据**。 |
| `fig_pipeline`（数据处理流程图） | **不生成** | 本题无独立数据处理链路：输入就是附件 1（环境，241 点 · 60 s）、附件 2（半径，145 点 · 1800 s）与附录 2~4 的经验式，无清洗/特征构造环节。 |
| `fig_index_system`（分层指标体系） | **不生成** | 不是评价类问题，没有目标层/准则层/指标层结构。 |
| `fig_decision_tree` | **不生成** | 不存在分支决策规则；Q3/Q4 的"事件定位"是一条单调求根。 |
| `fig_model`（模型结构总览） | 由 **`fig_coupling`** 承担 | 本题的模块关系就是物理耦合关系（环境 → Robin 边界 → 体内两场），单独再画一张总览图只会重复。 |

对照 `ANALYSIS_MODELING_REPORT.md` §12 给 `drawio` 的四项交付：① 技术路线图 → `fig_roadmap`；
② 耦合结构图 → `fig_coupling`；③ 一维径向几何与网格 → `fig_geometry`；
④ Q4 动边界与 ξ 坐标变换 → `fig_q4_material`。**四项齐备，无缺项。**

## 4. 导出与自检记录

### 4.1 生成命令（可复现）

```powershell
# 13 张数据图（export() 自己登记；本轮在其中改了 caliber_sensitivity 的一处标注落点）
python figures/make_figures.py
# 2 张稳健性图（⑥ 的脚本；本轮未动）
python figures/make_robustness_figures.py
# 三张灰阶示意图（本轮未动）
python figures/make_flow_figures.py

# 全量自检
python -m lib.visualization audit                 # 期望 PASS / issues []
python -m lib.result_contract build               # 见 §6 的 registry 重盖戳说明
python -m lib.result_contract audit / validate    # 期望 [] / PASS
```

技术路线图的命令（本轮未重跑，记录以供复现）：

```powershell
python skills/paper-diagram/scripts/roadmap_5band.py figures/fig_roadmap.content.json `
       --theme semantic -o figures/fig_roadmap.drawio
python skills/paper-diagram/scripts/check_layout.py figures/fig_roadmap.drawio
$env:PATH = "C:\Users\Cyl\Downloads\new math agent\tmp\drawio_bin;$env:PATH"
python skills/paper-diagram/scripts/export_figure.py figures/fig_roadmap.drawio
```

> ⚠️ **交付图只走生产入口重渲**（SKILL 硬规矩）：本轮所有"为了量一量/比一比"的渲染
> **一律落 `_tmp/dr7_render/`**，没有一次写进 `figures/`。判据：收口时 `audit` 仍 **PASS**。
> ⚠️ **量交付像素必须走生产入口复刻**：`_tmp/dr7_probe_lib.py` 把 `export()` 打桩成
> 「同一构图序（`fig.set_dpi` → `canvas.draw()` → `savefig(dpi, facecolor="white")`）渲到 `_tmp/`」，
> 并对**每一张**都比 sha256 与 `figures/` 的交付件 ⇒ 收口时复跑仍 **13/13 逐字节相同**
> （`_tmp/fig8_repro_check.py`），所以按它的坐标系量的数字就是交付像素的数字。

### 4.2 机器自检结果（本轮收口实跑）

| 检查 | 命令 / 探针 | 结果 |
|---|---|---|
| 登记表完整性 / 未登记资产 / 复核签名 / 位图质量 / 图例压数据 | `python -m lib.visualization audit` | **PASS，`issues = []`**（19 项全部有当前版本的 sources/script/config/图片哈希快照与复核签名） |
| 结构化结果 | `python -m lib.result_contract audit` / `validate` | **`[]` / PASS**（`build` 重盖戳后，见 §6） |
| `fig_roadmap` 版式体检 | `python lib/web/check_skeleton.py` 的同一支 `check_layout.py`（`audit()` 内部会调） | **FAIL 0 / WARN 0**（本轮未动该图） |
| 越界 / 小字号 / 图例压数据 / 注记互压 | `export()` 内建（13 张本轮全部重渲） | **`auto_issues` 全为空**（唯一提醒是 `q4_effects` 的"近单色 91%"，柱状图正常形态，不进 `auto_issues`） |
| **图例框 vs 参考线**（三道机器闸的盲区） | `_tmp/fig8_delivery_probe.py`（⑧ 的探针，**原样重跑**） | **查 1 整节为空**（13 张一张不漏） |
| 图例几何（含**图级**图例）vs 参考线 | `_tmp/fig8b_legend_geom.py`（复用 ⑧ 第 2 轮的探针） | 15 张图（13 数据 + 2 稳健性）的**全部**图例 × 参考线命中 **0**；两条 `✗ 文字入框` 是已知假阳（轴视图区间**外**的隐藏刻度标签 `−0.5`/`−5`，matplotlib 建对象但不绘制） |
| **参考线穿文字**（本轮回执点名的那一类） | `_tmp/fig8b_line_text_cross.py ref`（**原样重跑**） | **13 张全「无」**；`all` 模式仅剩一条已判假的 `_nolegend_`（`linestyle=None` 不绘制，三路取证见 §1.1） |
| 标注 vs 基准线的逐行净空 | `_tmp/dr7c_annotation_geom.py`（本轮新写） | `caliber_sensitivity` 7 档：字框含竖线者 **0**；被翻面那一档净空 +44.3 px |
| **刻度标签之间的净空** | `_tmp/dr7_tickcheck.py`（交付像素坐标） | 13 张数据图的全部坐标轴：`< 2 px` 的相邻标签对 **0 对** |
| 坐标区宽度 | `_tmp/dr7_axes_all.py` | 所有坐标区 **≥ 40.7 mm**；`caliber_sensitivity` **80.1 × 71.9 mm**（与改前**同尺寸**，只挪了标注） |
| 白等值线标注 vs 红阈值线 | `_tmp/dr7_whitelabel.py` | 三张场图：框内含红像素的字形 **0 个**，最小净空 37.2–85.0 px |
| caption/claim ↔ 现算值 | `_tmp/dr7b_caption_recheck.py`（复用） | **23 项全 ✅**（三处字符串本轮一字未动，仍逐位相符） |
| **manifest 除 `review` 外的字段未变** | `_tmp/dr7c_manifest_fields_proof.py`（本轮新写） | 脚本里 `sources/claim/caption` 的源码片段 **39/39 逐字节相同**（对快照版脚本）；manifest 与脚本字面量 **33/33 相同** |
| 控制字符（交付面两侧） | `_tmp/au41_ctrl_scan.py` + `_tmp/dr7b_caption_recheck.py` 末段 | 交付面 **0 命中** |

### 4.3 目检与复核（`review` 记录）

**13 张本轮重渲的图逐张打开交付 PNG 目检并重签**（`export()`/`register()` 每次重渲都把 `review`
打回 `pending`）。审阅者统一记为 `7Route-diagram 主 agent（逐张打开交付 PNG 目检）`。

- 12 张**画面零变化**（与驱动快照逐字节相同），自述写的是"本轮实际看到的画面 + 该背景事实"，
  未照抄上一轮整段 note；
- `caliber_sensitivity` 写本轮改动后的新画面（7 档点与数值、红线只从两串数字之间的空白穿过、
  「56.85」在其点左侧、「56.97」在右侧、图例在坐标区下方）。

4 张非数据图与 2 张 `rb_*`（⑥ 的脚本产出）本轮**未重渲**，复核签名仍有效，未重签。

**如实登记的观感限制（未改，均有既定口径）**：

| 图 | 限制 | 为什么不动 |
|---|---|---|
| `q1_field` 右栏 | 水分场大片同色（导出的「近单色」提醒 34%） | 平区正是物理上未受扰动的区域、也就是该图要讲的结论本身；⑧ 已登记 advisory `adv-field-flat-share` 并**建议不改**，本阶段照此办理。 |
| `q4_effects` 第 4 档 | 柱高 72.00 h 是**输出窗上界**，不是估计值 | 图内注记已写明「按窗上界绘制、**是下界不是估计值**」，不会被误读成点值。 |
| `fig_roadmap` 排印字号 | 954 px 画布、FS = 16 px，压到 `0.85\textwidth`（138.7 mm）后正文侧约 **6.6 pt** < `min_font_size` 8 | 见 §7 的待办 ①：实测把 `FS` 提到 17/18/19/20 会被 `check_layout.py` 判出 14/24/38/49 条版式失败 ⇒ **文案已贴预算，提字号等于重排整张图**；且"版式/嵌入尺寸"按 `docs/VISUALIZATION.md` 第 6 条归 ⑭format。本阶段刻意未动这张图的几何。 |
| `fig_coupling` | 半栏 80 mm 内符号较多、细笔画在缩图下略糊 | 交付件 @300 dpi 可读；并排双图是既定版面。 |
| `q3_criteria` / `caliber_sensitivity` / `rb_uncertainty` | 图例移到坐标区外后，坐标区**高度**略减（81.2 → 72.7、79.2 → 71.9、71.4 → 63.5 mm，上一轮的改动） | 这是"图例不再压参考线"的代价；**宽度一律未变**（63.1 / 80.1 / 65.0 mm），刻度净空与曲线可读性均无回退（§4.2 三行机器判据可核）。 |

## 5. 本轮的数据图改动（**1 处**，落在「落在图片面、不碰数值」的白名单里）

**一个数都没动**：`code/`、`results/` 数值件、`*.npz`、`config/`、`lib/visualization/*.py`
的 sha256 **逐文件全等**（§6）。

### 5.1 `caliber_sensitivity`：数值标注的落点自适应（回执 issue `fig-5`）

对 `figures/make_figures.py` 的逐行 diff（对快照版）**只有这两处**：

```diff
-    for y, v in enumerate(vals):
-        ax.annotate("%.2f" % v, (v, y), textcoords="offset points", xytext=(6, 0),
-                    va="center", fontsize=8, color=INK)
+    anns = [ax.annotate("%.2f" % v, (v, y), textcoords="offset points", xytext=(6, 0),
+                        va="center", fontsize=8, color=INK)
+            for y, v in enumerate(vals)]
...
     ax.set(xlim=(51.5, 59.5), xlabel="$t_{dry}$ / h")
+    # ★ 数值标注的落点自适应（2026-09-29 本阶段第 3 轮，回执 issue `fig-5`）：…
+    fig.canvas.draw()                     # constrained layout 落位之后，字框才是最终值
+    _r = fig.canvas.get_renderer()
+    _xline = ax.transData.transform((vals[0], 0.0))[0]
+    for _a in anns:
+        _box = _a.get_window_extent(_r)
+        if _box.x0 <= _xline <= _box.x1 and ax.transData.transform(_a.xy)[0] < _xline:
+            _a.set_position((-6, 0))
+            _a.set_ha("right")
```

**没有**动数值、`xlim`、色阶、参考线的绘制参数，**没有**动共享库（`lib/visualization/*.py` 一行未改），
**没有**截短参考线。改完的硬判据（SKILL「阶段边界」的三条）逐条满足：
① `code/`、`results/` 数值件、`*.npz`、`manifest.json` 的 `sources` 与改动**逐字节相同**（§6 + §4.2）；
② 走生产脚本重渲 + 重登记 + 逐张重目检（§4.3）；
③ `python -m lib.visualization audit` **PASS**。

## 6. 改动面与阶段边界

### 6.1 对**驱动快照**（= 本轮开工时的盘面原件，`产物/cache/2026A_2026.9.29_21.31.50/技术路线图/快照/`）

| 组 | 逐字节相同 | 变化 | 说明 |
|---|---|---|---|
| `code/`（4 个 `figdata_*.npz`） | **全部** | **0** | 未重跑求解器、未改一行代码 |
| `results/`（`q3/q4/sensitivity/convergence.json`） | **全部** | **0** | 数值面零变化 |
| `reports/`（`ANALYSIS_MODELING_REPORT.md`、`RESULTS_REPORT.md`）、`request/`、`tmp/rob/` | **全部** | **0** | 前序报告与输入一字未动 |
| `figures/*.png` | **18 / 19** | **1** | 唯一变的是 `caliber_sensitivity.png`：`95be558ab65f5bd0…` → `39a7dea5766cb249…` |
| `figures/*.pdf` · `*.svg` | 0 | 28 | .pdf/.svg **内嵌创建时戳与每进程随机图元 id** ⇒ 重渲必换（本项目既定口径，非缺陷） |
| `figures/make_figures.py` | —— | 1 | 本轮**唯一有意改动的脚本**，diff 见 §5.1 |

### 6.2 对**自己取的开工基线**（131 项，`_tmp/dr7c_baseline.json`）

`config/` 变化 **0**、`lib/` 与 `lib/visualization/` 变化 **0**、`code/` 变化 **0**、
`reports/*.md`（前序报告）变化 **0**；`results/` 唯一变化是 `results/registry.json`（见 6.3）；
`figures/` 的变化 = 上述 .pdf/.svg 批次 + `make_figures.py` + `manifest.json`（因 `review` 重签而变）。

### ★ 6.3 `results/registry.json` 这一处变动的说明（必须读）

`figures/make_figures.py` 被列在 `results/metric-spec.json` 的 `scripts` 里 ⇒ 只要动它，
`python -m lib.result_contract audit` 就会报「结构化结果已过期或被修改，重新build」。
本阶段据实处理并**留下可核证据**（`_tmp/dr7c_registry_restamp.txt`，对照份 = 本轮开工时复制的
`_tmp/dr7c_registry_before.json`）：

- 两份 JSON 展开成 **362 个键路径逐键比**：只在一边出现的键 **0 / 0**，值不同的键 **1 个** ——
  `/snapshot/figures/make_figures.py`（`fe2008a1bd7db735…` → `3dc3b3c0956bf48d…`）；
- **落在 `/metrics` 下的差异键数 = 0** ⇒ 指标值逐字段未变；
- 重跑 `python -m lib.result_contract build` 后 `audit` 输出 **`[]`**，`validate` 仍 **PASS**。

⇒ 这是**登记件的重盖戳**，不是数值面变化。**未**改任何数值、未改 `code/outputs/*.npz`、
未改 `figures/manifest.json` 的 `sources` 字段（§4.2 的 AST 探针可核）。

### 6.4 阶段边界声明

- 本阶段**未**重跑模型、**未**修改 `code/`、**未**改 `results/` 的数值件、`config/`、
  `lib/visualization/*.py` 与任何前序报告 —— §6.1/6.2 的逐文件哈希可核。
- 被改的画图脚本只有 `figures/make_figures.py` 一个，且只有 §5.1 那一处；
  **无一处触碰数据、坐标范围或色阶**。
- **没有写 `reports/HANDBACK_REQUEST.md`**：唯一那条 issue 落在「落在图片面、不碰数值」的白名单里
  （SKILL「阶段边界」的标注落点类），**就地改**即可 —— 一次交回的代价是 ④ 41 min + ⑤⑥ 58 min +
  ⑦⑧ 72 min ≈ **2h51m**，换来的是**一行数值都没动**的改动。
- 所有探针都在 `_tmp/`（新）与 `tmp/`（历史遗留）下运行；需要"重渲"的一律重定向到
  `_tmp/dr7_render/`，没有一次写进 `figures/`（收口时 `audit` PASS 可核）。
- **未改动 `reports/FIGURE_PLAN.md`**（它在 `ARTIFACTS["code"]` 里，改它会作废 ④ 的回执）：
  本轮的改动与它的自述不冲突，故**无需改动**。

### 6.5 本轮复用的探针（都在 `_tmp/`，下一轮**先原样重跑**）

`_tmp/dr7_probe_lib.py`（生产入口复刻 + sha 自证）、`_tmp/fig8_repro_check.py`（13/13 沙箱自证）、
`_tmp/fig8b_line_text_cross.py`（线穿字，`ref`/`all` 两模式；`all` 要按"线是否真画出来"过滤）、
`_tmp/fig8b_legend_geom.py` + `_tmp/fig8b_legend_zero.py`（图例几何，含**图级**图例）、
`_tmp/fig8b_delivery_probe.py`（⑧ 的越界/字号/序列数三查）、`_tmp/fig8b_issue_recheck.py`（现读交付串 + 现算）、
`_tmp/fig8b_change_face_snapshot.py` / `_tmp/dr7c_change_face.py`（对**驱动快照**的改动面）、
`_tmp/fig8b_registry_restamp.py` / `_tmp/dr7c_registry_restamp.txt`（registry 重盖戳判别）、
`_tmp/dr7_tickcheck.py`、`_tmp/dr7_axes_all.py`、`_tmp/dr7_whitelabel.py`、`_tmp/dr7b_caption_recheck.py`。
**本轮新写 5 支**：`dr7c_annotation_geom.py`（标注 vs 基准线逐行净空）、
`dr7c_cross_filter_false_positive.py`（`linestyle=None` 假阳三路取证）、
`dr7c_manifest_fields_proof.py`（manifest 除 `review` 外字段未变的等价证明）、
`dr7c_change_face.py`、`dr7c_baseline.py` / `dr7c_resign.py`。

## 7. 给论文阶段的嵌入建议

> 只给"放哪一节 + 建议 caption"。LaTeX 的 `\begin{figure}` / `\paperfigure` 由 `9Paper-writing`
> 按论文结构决定。**每张图的 caption 已在 `figures/manifest.json` 里写好**，可直接取用。

| 图 | 建议位置 | 宽度 | 建议 caption |
|---|---|---|---|
| `fig_roadmap` | `paper/sections/1_restatement.tex` **末尾**（问题重述之后、问题分析之前） | `\paperfigure[0.85\textwidth]{fig_roadmap}{分析流程图}{fig_roadmap}` | 本题的技术路线（① 破题 … ⑤ 评价）—— 登记宽 138.7 mm 就是这一档排印宽 |
| `fig_geometry` | 「问题重述」或「模型建立」开头的几何与边界说明处 | 半栏；**建议与 `fig_coupling` 用 `\paperfigurepair` 并排**（两者都是 80 × 64 mm） | 药材的几何与计算网格示意：(a) 轴测圆柱（断口示意）；(b) 径向截面与有限体积网格、中心对称与 Robin 边界 |
| `fig_coupling` | 「模型建立」中写出控制方程与定解条件之后 | 同上，与 `fig_geometry` 并排 | 传热传质耦合结构：环境 → 表面 Robin 边界 → 体内两场，以及 $T\Rightarrow D\Rightarrow C$ 与 $C\Rightarrow\rho,c_p,k\Rightarrow\alpha$ 两条耦合链 |
| `fig_q4_material` | 「问题四」的动边界 / 材料坐标变换小节 | 半栏 `\paperfigure[0.49\textwidth]{fig_q4_material}{…}{fig_q4_material}`（80 × 58 mm，**不要**与上面两张并排） | 问题 4 的动边界与材料坐标 $\xi=r/R(t)$：两栏共用同一坐标范围，同一物质点被压缩到外圆半径的 0.8 处而 $\xi$ 不变 |

**三条硬约束交 `9Paper-writing` / `14Layout-and-format`**：

1. `fig_roadmap` 必须**正好出现一次**且**不小于 0.85 栏**（`python lib/web/check_skeleton.py` 机械核）。
2. 三张示意图是**半栏设计宽**（80 mm），**不要**放进整栏 `\paperfigure`（默认 `\textwidth`
   会把它们放大到 2 倍、字号随之变大、与正文失衡）。
3. 图里的符号与论文符号表一致（$r$、$R(t)$、$\xi$、$C$、$T$、$h$、$h_m$、$D$、$\rho_d$ 等）。

**一条提示交 `⑨Paper-writing`**：

- 三处 caption 里写死的口径句，正文若要复述请**照抄同句口径**：
  ① `q1_field`（问题 1）：**按 $|\Delta C|>0.1$ kg/kg 的口径，变化区只到最外 6.19 mm**；
  ② `q2_drydown` / `q2_moist_field`（问题 2）：**到 $t=24$ h 时表面与环境之差已小于
  0.02 kg/kg（该口径自约 22.2 h 起一直满足）**；
  ③ `q2_diffusivity`：轨迹为**蓝色**（不再是红线），阈值红仍是唯一的红。
- `q3_criteria` / `caliber_sensitivity` / `rb_uncertainty` 三张图的**图例在坐标区外**
  （前两张在栏下方、`rb_uncertainty` 左栏在轴下方）；caption 未提图例位置，**不需要改正文措辞**。
- `caliber_sensitivity` 本轮把「56.85」（环境延拓取饱和拟合档）的数值标注挪到了该点的**左侧**
  （避开主档基准虚线），其余 6 档仍在点右侧。**caption 与正文都没有描述标注左右**，
  故**无需任何改动**；若正文要写"标注一律在点右侧"，按现状改写为"在点的相邻一侧"。
- `q3_dryfront` / `q2_moist_field` / `q4_field` 三张场图的白色等值线**不含阈值那一层**
  （阈值只由红线 + 图例承担，避免与红线重合）；`q2_temp_field` 右栏是**线性**纵轴。两句已写进 caption。

**两条待办交 `⑭Layout-and-format`（本阶段刻意未动）**：

- ① `fig_roadmap` 的画布是 954 px、全图 16 px 字号；按登记宽 **138.7 mm**（= `0.85\textwidth`）排印时
  正文字号折算约 **6.6 pt**，低于 `config/visualization.json` 的 `min_font_size = 8`。实测把渲染字号
  提到 17/18/19/20 会被 `check_layout.py` 判出 **14/24/38/49** 条版式失败 ⇒ **文案已贴预算，
  提字号等于重排整张图**；按 `docs/VISUALIZATION.md` 第 6 条（版式/嵌入尺寸 → ⑭format），
  由该阶段在"整页横排（`sidewaysfigure`）/ 精简重排 / 接受 6.6 pt 并在图注注明"之间定夺。
  **不是图的内容缺陷。**（本阶段独立复算：PDF MediaBox 687.12×932.88 pt、源 FS=16 px ⇒
  PDF 内 11.52 pt，按 138.7 mm 折算 ≈ 6.6 pt，与 ⑧ 的 advisory 相符。）
- ② 三张把图例移到**坐标区外**的图（`q3_criteria`、`caliber_sensitivity`、`rb_uncertainty`）
  坐标区**高度**各减 7–13 mm。若排版时发现某一页版面紧张，可优先把这三张与会重跑的图分开排，
  或按 ⑭ 的口径重新分配图幅；**宽度与刻度净空不受影响**（§4.2）。

## 8. 本轮新发现（未改，登记备查）

按通用纪律五·4，返修途中发现、但不属回执清单的，**不顺手改**，在此登记：

1. **`q1_field` 的 `claim` 字段**：「1800 s 内温度场整体升温而水分只在最外层**数毫米**内下降，
   中心点几乎不动」——与上一轮 issue fig-1 同一族（未印数、无口径），但**不是回执点名的四处**，
   且按 caption 同句的 $|\Delta C|>0.1$ kg/kg 口径（6.19 mm）与图面可见结构（0.31–7.55 mm）都站得住，
   故**未改**（上一轮已登记，本轮结论不变）。若下一轮门禁按"无口径"判它，改法是把口径并进这一句。
2. **`reports/ANALYSIS_MODELING_REPORT.md:358`**（③ 的产物，**本阶段不改**）：「本段含水率变化极小，
   $D$ 的下降只发生在最外层 3 mm」——无口径的量级句，且量不同（$D$ 而非 $C$）。
   ⑧ 本轮把它登记为 advisory `adv-analysis-d-drop-3mm` 并投给 **analysis**；本阶段**未改**（不属它的处置面）。
3. **⑧ 的复量探针有一处判别式裂缝**（给下一轮的提示，不是交付缺陷）：
   `_tmp/fig8_delivery_probe.py` 用 `ydata == [0,1]` 判别 `axvline`（`transAxes` 分支）。
   若某轮改用"给参考线加 `ymax=`/`xmax=`"的修法，该判别式随即失效、探针退到 `transData`
   分支把轴分数当数据坐标读 ⇒ 会读出"仍在框内"的**伪影**。本阶段两轮都因此改走"图例外移 / 标注换侧"，
   使探针在任何变换下都读 0。若将来必须截线，探针的判别式建议改成 `ln.get_transform()`。
4. **`fig8b_line_text_cross.py` 的 `all` 模式会对"不绘制的线"报假阳**（`errorbar(fmt="o")` 的连线，
   `linestyle=None`）。本阶段**未改 ⑧ 的探针**（那是它的取证工具），而是按回执给的判据另行取证
   （`_tmp/dr7c_cross_filter_false_positive.py`，§1.1）。下一轮若要复跑 `all` 模式，
   记得按"线是否真画出来"过滤，否则会看到这条已知假阳。
5. **⑧ 的 advisory `adv-field-flat-share`**（`q1_field` 右栏 80.8% / `q2_temp_field` 左栏 66.6% 同色）：
   ⑧ 已判"不建议按死色药方改"、本阶段**照此不改**（平区即结论本身；`contourf` 的档界不吃
   `PowerNorm` 的 gamma）。**延后建议，未落实。**
