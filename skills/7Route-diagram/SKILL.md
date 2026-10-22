---
name: 7Route-diagram
description: "数学建模图示与渲染阶段。读取 4Coding-and-computation 交付的 figures/data + figures/spec + figure lock，渲染所有数据图；同时生成技术路线图、子问题求解流程图、模型结构图、数据处理流程图等非数据图示，并导出论文可引用 PDF。"
allowed-tools: PowerShell, Read, Write, Edit, Grep, Glob, Agent, WebSearch, WebFetch
---

# 数据图渲染与非数据图示

> 通用执行纪律（增量返修 / 缩比预估 / 分段落盘 / 方法标记 / 返修只动清单内）见 `../_references/stage_discipline.md`。
> 本阶段适用：一（增量返修，含 1.1 探针复用）、五（返修只动清单内）。
> **探针/量测脚本要复用（通用纪律 一·1.1）**：本轮写的取证/量测脚本一律留在 `_tmp/`
> （另有散落的在 `tmp/`，两个都要看）；下一轮开工第一步 = `ls _tmp/ tmp/` → 把上一轮
> 为同一批对象写过的脚本先原样重跑（秒级，确认数在当前版本里还成立）→ 只对本轮新出现或改过
> 的对象写新脚本。别每轮从零重写 —— 全链 776 个自写脚本里 **683 个（88%）只被用过一次**
> 就再也没人碰。复用探针 ≠ 跳过复核：探针只是取证手段，判定仍逐条对着当前版本做。

本 skill 承接 `4Coding-and-computation`。④/⑦ 已解耦：④ 只交数据层
（`figures/data/<id>.npz` + `figures/spec/<id>.json` + `figures/<id>.lock.json`），
**本阶段是数据图的唯一渲染者**，同时负责论文中的非数据型图示（技术路线图、求解流程图、
模型结构图、数据处理流程图、变量关系图、指标体系图等）。

## 数据图渲染（第一优先，先做这一块）

开工先盘点三件套，再动 draw.io：

```powershell
python skills/figure-studio/scripts/figure_lock.py verify --root .
```

- PASS（或只有 `[lock:advisory]`）⇒ 读 `figures/spec/*.json` 与 `figures/data/*.npz`。
- `[lock:data]` ⇒ 数据层在锁之后变了，**不要画**。写 `reports/HANDBACK_REQUEST.md`
  交回 ④（见下面「动态交回规则」），本阶段结束。
- `[lock:contract]` ⇒ spec 的字段/claim/统计口径被改过。先看是哪一条：若是
  `meta.claim` 与锁不一致，**直接重渲**（`render_specs.py` 渲染前用 `check_meta=False`，
  本来就允许用重渲修 meta）；若是 spec 语义被改，先确认是不是自己上一轮改的，是就改回
  锁定值，不是就交回 ④。

渲染规则：

1. `figures/make_figures.py` 是**本阶段的产物**。从
   `skills/figure-studio/scripts/render_specs.py` 复制一份作为起点，或在它的
   `custom` 分支里写特殊拼版；不要把它写进 `code/`。
2. 只读 `figures/data` / `spec` 的语义部分 / `lock`；**不许改**。要换字段、换统计口径、
   换 claim ⇒ 交回 ④。可以改：recipe、layout、配色、标题、caption 文字、图例位置、
   坐标范围、面板顺序、`options`。
3. 每个面板用 `studio` 的 recipe；渲染后调 `studio.save_figure(...)`，sources 传
   `studio.lock_sources(root, id)`（它会带上 bundle/spec/lock 和原始 source）。
   `save_figure` 会先验锁，锁不过直接拒绝渲染。
4. 声明式 spec 可直接跑 `python skills/figure-studio/scripts/render_specs.py --root .`；
   它**逐图验锁**：某张失败只跳过该图并列出原因，其余照渲（一张坏图不拖住整批）。
   `render.mode="custom"` 的图（SHAP 组合、和弦、环形热图、分布总装、CV ROC 等）
   由 `figures/make_figures.py` 里的自定义代码用 `studio` 对应 recipe 排。
5. 渲完按原判据：`python -m lib.visualization audit` PASS +
   `python skills/figure-studio/scripts/audit_studio.py --root .` PASS + 打开 PNG 目检 +
   `python -m lib.visualization review <id> ...` 签名。`audit_studio` 已内置 `figure_lock`，
   所以锁、语言、来源数据、meta 一次查完。

**不要在数据层之外重算数值**：`figures/make_figures.py` 只能读 bundle；
发现 bundle 里没有需要的量 ⇒ 交回 ④，不要在 ⑦ 里重新求解或从 `code/outputs` 另取一份。

## 出图工作流：先选图，再自评，再优化

不要拿到 spec 就一张张硬画。按下面五步走，把“丑图/废图”挡在登记之前。

### 1. 数据驱动选图（triage）

先读 `figures/spec/*.json`、`figures/data/*.npz`、`reports/FIGURE_BRIEF.json` 与
`reports/FIGURE_PLAN.md`，对每张图回答：

- 它支持哪句 claim？claim 是不是数据真能支持的？
- 数据形态适合当前 recipe 吗？（场是否近乎平坦、类别是否过多、是否有配对 ID、
  有没有真实区间/标签/贡献值 —— 见 `figure-studio/assets/recipes.json` 的 `required_fields`）
- 如果不适合，按 `recipes.json` 的 `fallback` 换图型；换图型不改 fields/claim，属于 ⑦ 的权限。
- 如果**数据本身不足以支持 claim**（不是图型问题），不要硬画 —— 写
  `reports/HANDBACK_REQUEST.md` 交回 ④，说明缺哪个量/哪个字段。

把结论写进 `reports/DRAWIO_REPORT.md` 的「选图决策」表：`figure_id | claim | 数据形态 |
候选 recipe | 淘汰理由`。不要只写“已生成”。

### 2. 候选生成（落 `tmp/`，不登记）

每个主图至少比较 **2 个不同视觉编码的候选**（不是 2 个配色）。候选图一律渲染到
`tmp/figures/<figure_id>/cand_<n>.png`，**不要**写 `figures/`、不要 `save_figure`；
看完再选一个定稿。候选可以换 recipe / 拆面板 / 改 layout / 改坐标范围。
`fig_roadmap` 不适用「2 个配色」——按 §5A 生成 3–4 个**不同结构**的候选（路由树 / 泳道 / 变体）。

### 3. 自评（打开实际 PNG，在最终物理尺寸看）

逐张按下面六条打分（1–5），写进 `reports/DRAWIO_REPORT.md` 的「自评」表：

| 维度 | 判据 | 典型失败 |
|---|---|---|
| claim 支持 | 图一眼能看出 claim；没有多余信息 | 图画得很漂亮，但和 claim 无关 |
| 信息密度 | 有效绘图区占画布的大部分；没有“一大片空白只用上很小一块” | 右侧 55% 空白、9 宫格只用了 1 格 |
| 可读性 | 图例不压线、文字不压文字、字号 ≥ 最小字号 | 图例盖住曲线、标签跑出画布 |
| 灰度 | 黑白打印仍能区分 ≥5 条序列 | 只靠红/绿区分 |
| 语言/统计 | 图内语言=模板语言；n/区间/排除规则写清 | 中文图里整句英文；假 p 值 |
| 冗余 | 没有和另一张图重复讲同一件事 | 同一数据画了折线又画柱状 |

任一项 ≤2 分就回第 2 步换候选；不要“先登记再说”。

### 4. 优化与定稿（串行登记）

选定候选后，用 `studio.save_figure(...)` 写成品、source data、meta 并登记 manifest。
**登记必须串行**：`figures/manifest.json` 是整份读—改—写，多个进程同时登记会丢条目
（`lib/visualization/evidence.py` 的进程内锁挡不住跨进程写）。定稿后再打开一次 PNG，
确认优化没有引入新的遮挡/裁切。

### 5. 多 agent 并行（默认：`fig_roadmap` 3–4 个结构候选）

**A. `fig_roadmap` 的候选面板（默认，不再可选）**

1. 主 agent 先按 `references/route-diagram.md` 定结构（问题路由树 / X 问泳道）和内容清单；
   按 `../_references/stage_discipline.md` 八建 `.fma_panel_lock`。
2. 并行启动 3 个（最多 4 个）子 agent（优先 `config/agents.json` 的 `fig-candidate`；
   不可用时 general-purpose），每个画一个**不同结构/阅读方向**的候选：
   - C1 问题路由树（自上而下）；
   - C2 X 问泳道（共享上/下母线）；
   - C3 路由树的另一分组（按问分组 / 按方法分组 / 左→右）或泳道的变体；
   - 第 4 个只在 C1–C3 有明显缺口时加。
   **不允许只换配色/字号**；候选必须是不同结构或不同阅读方向。
3. 子 agent 只写 `tmp/figures/fig_roadmap/cand_<n>.{drawio,png}`（或 `.svg/.png`），
   自己跑 `check_layout.py` + `references/route-diagram.md` 的 8 条自检，返回：
   候选路径、结构、自检结果、已知缺陷。
4. 主 agent 收齐后**先删 `.fma_panel_lock`**，再在最终物理尺寸看 3–4 张 PNG，按 claim 支持 / 信息密度 / 可读性 /
   灰度 / 语言 / 冗余打分，选 1 个（可嫁接其他候选的局部），由主 agent 自己重画/合并定稿；
   **登记、导出、5.1 自检只由主 agent 做**。
5. 子 agent 不可用 → 主 agent 串行画 3 个结构候选，不许只画一个就交。
6. 成本：3 个候选约 1–2 分钟、约 3 倍绘图 token；比 ⑧ 打回一次便宜。

**B. 数据图 / 其他非数据图（按 `figure_id` 并行）**

图多（>4 张）或候选多时，按 `figure_id` 分组并行。硬规则同上：

- 每个子 agent 只碰自己那组 `figure_id`，只读 spec/bundle；
- 候选图只写 `tmp/figures/<figure_id>/`，不得调用 `save_figure`、不得写 `figures/`、
  `figures/manifest.json`、`source_data`、`meta`；
- 子 agent 返回：候选路径、推荐 recipe/layout、自评表、需要主 agent 执行的最终参数；
- 主 agent 收齐后**串行**跑 `save_figure` 登记，避免 manifest 丢更新。
  并行省的是“看图和试错”，不是“写登记”。

### 6. ⑧ 回执：按 figure_id 返修，不全量重渲

⑧ 判 FAIL 回来时，先读 `reports/FIGURE_REVIEW_REPORT.verdict.json` 的 `issues`：

- 按 `figure_id` 分组；**只重渲被点名的图**，其余图的 PDF/SVG/PNG、source data、
  meta 保持逐字节不变（自检：改前/改后对未点名图算 sha256，应完全相同）。
- 每条 issue 按 `fix` 执行（换图型/改 loc/裁 xlim/拆面板/改 caption），不要顺手改别的图。
- 数据层 `[lock:data]` 不是 ⑦ 能修的：写 `HANDBACK_REQUEST.md` 交回 ④，不要重画。
- `reports/FIGURE_POLISH_QUEUE.json` 里**没打回但可优化**的项：本轮只改点名的图，
  改完在 `DRAWIO_REPORT.md` 写“按 polish queue 改了哪些图”；没点名的图不动。
- 在 `DRAWIO_REPORT.md` 写一张「本轮改动面」表：`figure_id | 原问题 | 改法 | 复验`。
  ⑧ 下一轮只看这张表和它点过的图，不从头怀疑全部。

### 7. 返修编排：按 figure_id 只读诊断，主 agent 串行写

⑧ 回执按 `figure_id` 分组后，若 **≥2 张图互不依赖**，可以让子 agent 并行做**只读诊断**：

- 每个子 agent 只负责一个/一组 `figure_id`，读该图的 issue、PNG、spec 与
  `figures/make_figures.py` 的对应段，可在 `tmp/figures/<figure_id>/diag/` 写探针或局部截图；
- 返回：问题证据、拟改的 recipe/options/layout/caption、精确 patch（文件+位置+旧→新）、
  重渲命令、风险；
- 子 agent **不得**调用 `save_figure`，不得写 `figures/`、`source_data`、`meta`、
  `figures/manifest.json`，也不得改 spec/bundle；
- 主 agent 串行应用改动并 `save_figure` 登记；`manifest.json` 永远只有一个写者；
- 涉及数据层 `[lock:data]`、claim/统计口径或**多张图共用的布局/图注**时，不并行：
  按本 SKILL 的边界交回 ④，或由主 agent 单改；
- 复验命令由主 agent 跑；未被点名的图的 PDF/SVG/PNG、source data、meta 保持逐字节不变
  （改前/改后算 sha256 对照）。

`fig_roadmap` 的 3–4 个结构候选仍按 §5A 并行生成，但**选型、合并、登记、导出**只由主 agent 做。

## 非数据图示：几何表达与篇幅排版

对于数学物理或空间关系问题，先阅读 docs/GEOMETRY.md（相对项目根），判断是否需要整体几何图与截面/投影配图。

**题意示意图：从题面出发，不要从"库里有哪个函数"出发。**
数理类题（运动/几何/受力/光学/空间结构/流程演化）几乎都能靠一张示意图把题意讲清楚，
它往往比多画两张流程图有用得多。做法是：

1. 先读题面，把题里真实存在的对象与关系列出来：有哪些实体、什么形状/位置、哪些量标在哪、
   什么在动/受力/受约束、哪些关系是题面给定的（只画已确认的关系，不画猜想）。
2. 为这些对象选图元——`visualization.schematic` 提供通用图元，只负责画你给的东西：
   - `scene2d(xlim=..., ylim=...)` / `scene3d(azimuth=..., elevation=..., limits=...)` 建场景
   - `point` 标点、`segment` 连线（`arrow=True` 表走向）、`arrow` 画矢量（力/速度/方向）
   - `region` 画多边形区域/截面/可行域、`dimension` 标尺寸、`path` 画轨迹、`axes` 画坐标轴
   - `Scene.project()` 可把三维坐标投到视平面（正交投影，不计算遮挡）
   - 画完用 `visualization.export.export(...)` 导出并登记来源
   - **`scene3d` 只适合点/线/箭头级的简单三维示意**；实体剖切、隐藏面、内部结构
     改用第五类 `fig_geometry_3d`（见下文与 `references/physical-3d.md`）
3. 每张示意图只讲一件事，标签用题面/论文里的符号（与符号表一致），
   不要在一张图里叠三层含义；辅助线细而弱、主对象粗而深。

**数量按需分配，但先判重**：不是"全题只准画一张"，也不是"每问各画一张"。
先问这一问的几何是否真的与前面不同：只差时间窗/参数/输出、几何同构 ⇒ **合并**成
一张（同相机、同比例的双面板，或共用模型 + 参数标注）；所有问共用的方法细节
（如控制体）只画一张；没有几何/物理对象的子问题不配图。
判据是"这张图能不能让读者少读一段文字就懂"，而不是"总共几张"。

**演化与对比类必须用多面板，不要硬塞进一张**：
- 有"动起来"的过程（运动/传播/演化/收敛），用同一场景的两个（或多个）时刻并排表达：
  t₁ 与 t₂、初始态与终止态、迭代前与迭代后——各面板共享同一坐标范围与视角，否则读者无法比较。
- 对比类（不同参数/不同方案/优化前后）同理并排；面板标题写清各自状态（如"(a) $t=0$"、"(b) $t=T$"）。
- 用 `schematic.scene2d_panels` / `scene3d_panels` 建共享画布，各面板按同一套坐标画；
  3D 多面板**必须共用同一 `camera` 与 `limits`**，否则形变会让对比失效。

**不要套现成形状**：`geometry.py` 里的 `sphere_section` 等是布局示例，不是"每道题都画球"的模板。
先前的问题正是"库里只有球截面，于是什么题都画个球"。现在有了通用图元，图应当长得像这道题。
若题面是纯数据/统计/优化问题（没有几何或物理对象），就不画示意图，别硬凑。

**物理立体 / 3D 剖切图不要用 `schematic.scene3d` 硬画**：它只做正交投影、
不计算遮挡，也不支持实心剖切。按第五类 `fig_geometry_3d` 的 Route A/B 走
（见 `references/physical-3d.md`）：透明线框用 `style3d`，实心剖切用 `solid3d`，
计算结果场用 Route C（读 `figures/data`）。

## 通用绘图协议

读取项目根目录 `docs/VISUALIZATION.md` 的自定义图登记与视觉复核协议。根据本题实际方法选择图示，并登记来源、可编辑源和导出资产；目检后单独记录复核。

图中文字写成面向论文读者的方法、输入与输出；绘图报告不能用流程完成状态代替正文采用状态。

### 所有图共用 `figure-studio` 的画风与语言

数据图先读 `../figure-studio/SKILL.md`；非数据图（**`fig_roadmap` 除外**，它按
`references/route-diagram.md` 生成）仍以 `paper-diagram` 为主，只借用
`figure-studio` 的语言/画风 tokens。共同规则：

- 语言/宽度/字体由模板决定（CUMCM → 中文、160 mm、微软雅黑；英文/Nature → 英文、183 mm、Arial）；
  用 `python skills/figure-studio/scripts/resolve_context.py --write` 解析，不要凭习惯写英文标题。
- 数据图的图型、构图、配色、面板、图注文字，按 `figure-studio/references/catalog.md` 与
  `composition.md` 选；`studio.py` 里已有的 recipe 直接用，不要从零手写。
- 允许把 2×2 折线改成场图/云雨/点区间/3D 曲面+投影；允许拆面板、重排、换色、改图注文字。
- **仍然不许**改 `figures/data/*`、spec 的 `fields`/`field_mapping`/`claim`/`statistics`、
  `figures/*.lock.json`、`code/`、`results/`、`*.npz`、`figures/manifest.json` 的 `sources`、
  claim 的语义。必须动数值或口径来源时，按本 SKILL 的「阶段边界」交回 ④。
- 非数据图继续走 `paper-diagram`（`fig_roadmap` 除外，见 `references/route-diagram.md`）；
  `figure-studio` 只管数据图/拼版图/机制示意，不替代 draw.io 路线图。

改完仍按原判据：重跑 `figures/make_figures.py` 重渲 + 重新登记 + 重新目检 +
`python -m lib.visualization audit` PASS；再跑
`python skills/figure-studio/scripts/figure_lock.py verify --root .` 与
`python skills/figure-studio/scripts/audit_studio.py --root .` 查锁、语言、来源数据、脚本静态项。

## 数学建模规范参考

如需领域判断，读取 `../_references/math_modeling_norms.md` 中的“图表与可视化”和“非数据图工具选择”小节。该文件只作为规范知识库，不要求为了凑数量生成额外图示。

## 阶段边界

- 本阶段负责：**所有数据图的渲染**（`figures/make_figures.py`、PDF/SVG/PNG、
  `figures/source_data/*`、`figures/<id>.meta.json`），以及 DrawIO 源文件、非数据图 PDF、
  图示生成记录。
- ④ 只交 `figures/data` + `figures/spec` + `figures/*.lock.json`；本阶段**不重算、不改**它们。
  允许改的只有"落在图片面、不碰语义"的东西：recipe / `options` / `layout` / 面板顺序 /
  `legend(loc=)` / `bbox=` / `xlim`·`ylim` / `clip_on` / 色标档界 `levels` / `gamma` / 字号 /
  线宽 / `edgecolor` / 抽稀 `ccount`·`rcount` / caption 与标题文字。
- 本阶段**仍然不许**：改 `figures/data`、spec 的 `fields`/`field_mapping`/`claim`/`statistics`、
  `figures/*.lock.json`、`code/`、`results/`、任何 `*.npz`、`figures/manifest.json` 的
  `sources` 字段、claim 的语义（那是 `4Coding-and-computation` 的事）、
  `reports/RESULTS_REPORT.md` 的数值结论、重跑模型。
- 改完的硬判据（逐条都要满足，缺一条就说明这次要动的是"数值或口径来源"⇒ 那才走交回）：
  ① `figures/data`、`figures/spec`、`figures/*.lock.json`、`code/`、`results/`、所有 `*.npz`、
  `figures/manifest.json` 的 `sources` 与改动逐字节相同（`figure_lock verify` 会替你核前两项）；
  ② 重跑 `figures/make_figures.py` 重渲 + 重新登记 + 重新目检（自述要写实际看到的，别照抄旧 note）；
  ③ `python -m lib.visualization audit` PASS + `figure_lock.py verify` PASS。
- ⑧ 判 FAIL 的 4 条全是"画法/图注"，若按"只准交回 ④"的旧边界，一次交回的代价是
  ④ 41 min + ⑤⑥ 58 min + ⑦⑧ 72 min ≈ 2h51m，换来的 4 处改动一行数值都不动。

## 必须产出

在当前工作目录创建或更新：

```text
figures/
  make_figures.py                    # 数据图渲染器（本阶段拥有）
  <id>.pdf / <id>.svg / <id>.png     # 数据图成品
  source_data/<id>__<panel>.csv      # 逐面板来源数据
  <id>.meta.json                     # language/width/counts/intervals/exclusions
  fig_roadmap.drawio
  fig_roadmap.pdf
  fig_flow_q1.drawio
  fig_flow_q1.pdf
  fig_geometry_3d.pdf / .png         # 第五类，按需；Route A/B 成品
  fig_geometry_3d.scene.json         # Route B 的投影/相机/标签记录（Route A 可无）
  make_geometry_3d.py                # 第五类可复现源脚本（本阶段拥有）
  ...
reports/DRAWIO_REPORT.md
```

数据图的清单以 `figures/spec/*.json` 为准：每个 spec 都要有对应的成品与 meta；
`[lock:advisory]` 的旧图可以暂缺，但本轮新交的图不能缺。

**数量纪律（图 1 必出，其余少而精）**：

- `fig_roadmap`（论文里的图 1「分析流程图」）是硬性要求，不是可选 ——
  「（可选）流程图/架构图」那种说法不适用。`python lib/web/check_skeleton.py` 会核它
  有没有出现在 `paper/sections/1_restatement.tex`、栏宽是否 ≥0.85。本阶段必出这一张。
- 除此之外，竞赛论文**只需要 2–4 张**非数据图，流程图最多再 1 张。这些是按需：
  要画才说明它解释了哪个别处讲不清的东西。
- `fig_pipeline`/`fig_model`/`fig_index_system`/`fig_decision_tree` 等只在本题真有对应结构时才画，
  没有就在 `reports/DRAWIO_REPORT.md` 写一句"本题无独立数据处理链路/无分层指标体系，故不画"即可——
  不需要为没画的图编理由。宁可少而精，也不要凑数量。

**什么才算流程图**：有判断/分支/循环/迭代的求解过程（如"是否收敛→否→回到第 3 步"）。
"输入 → 模型 → 输出"三格直串不是流程图，那是把正文一句话画成了图，不要画。

**单图规模上限（防"把整题塞成一张巨长的图"）**：
- 单张图**节点 ≤ 12 个**、层级 ≤ 4 层；横向展开宽度不超过版面宽（≈160mm）。
- 超了就拆成两张（按子问题或按阶段），或把可枚举的细节改成论文里的表格——
  表格读起来比一张塞满字的巨图快得多，也更专业。
- 图里不塞长句：节点文字 ≤10 字/行、最多 2 行；解释、公式、判据一律留在正文。

## 一张大图，其余一律小图（配色同源）

全文只留一张"大图"：`fig_roadmap`（论文里的图 1「分析流程图」）。它仍然破例：
可以宽、可以信息密度高；**配色不再是它独有的** —— 其余非数据图也可以沿用同一套
语义色，但尺寸仍守小图。它的位置是「问题重述」之后、「问题分析」之前
（参考件就是排在 图 1，然后才进第二节）—— 由 `9Paper-writing` 放进 `1_restatement.tex` 末尾。

### 别在登记路径之外渲染交付图（诊断用的渲染一律落 `tmp/`）

⑧ 绘图门禁会在本阶段启动时直接判 `figure_evidence_failed` ——
`env_drive: 数据、脚本、配置或图片已改变`，而逐条比对下来变的只有 `.pdf`/`.svg` 两个文件
（PNG、配置、脚本都没变）。原因：这两种格式内嵌渲染元数据（时间戳等），任何重跑都换字节 ——
只要渲染没走 `export()`/`register()`，manifest 的快照就对不上，审计必然判过期。
（⑧ 自己的探针把 `export` 换成真实现、写进交付目录，也会撞同一类。）

**规矩**：要重渲交付图就走脚本（`figures/make_figures.py` / `figures/make_flow_figures.py` ——
它们渲染完会自己登记）；只为看一眼/做对比而渲染的，输出落 `tmp/`，别碰 `figures/`。
判据：渲完之后 `python -m lib.visualization audit` 仍应为 PASS。

### `fig_roadmap` 的配色取 config 的语义键，而且换配色时它是必改的一处

换过配色后本阶段必须重跑：**示意图（`fig_geometry`/`fig_flow_solve`/`fig_q4_material`）会跟着
`config/visualization.json` 的语义键重渲**，而 **`fig_roadmap` 的配色是"烤"在
`.drawio` 文件里的** —— 配置怎么改都碰不到它。它的 `fillColor`/`strokeColor`
若全是 `#333333 / #222222 / #f2f2f2 / #d9d9d9` 这类中性灰，就是一点语义键都没取到，
与本文档「它可以有配色」那条对不上。

**小图同源**：`fig_flow_*` / `fig_pipeline` / `fig_model` / `fig_geometry_3d` 等
非数据图也从同一 `config/visualization.json` 取语义键（主流程 `palette[0]`、
判断 `warn`、分组 `box`/`grid`），不再强制灰阶；同类节点同色、同语义同色，
只做语义区分，不做装饰色。

**消费者一侧的兜底**：如果 `reports/FIGURE_PLAN.md` 没点名这件事，
而 `config/visualization.json` 的 `palette`/语义键变了（判据：把 `.drawio` 里实际用的色值
与新语义键逐个比对，一个都对不上），也要主动重画 —— 别等计划写全。

**规矩**：
1. `fig_roadmap` 的节点/连线颜色**从 `config/visualization.json` 的语义键取**：
   `ink`(#1F2937) 主文字 · `line`(#475569) 主结构线 · `box`(#CBD5E1) 分组框 ·
   主流程用 `palette[0]`(#1D4ED8) · `warn`(#EF4444) 只用于阈值/异常/警示；
   浅底用 `grid`(#E2E8F0)。
2. **换配色时它必须重画**（改 `.drawio` 的 XML 或重画），然后重出 PDF/PNG、
   `python -m lib.visualization register` 重登记、重新目检 —— 光重跑导出命令是没用的
   （导出只是把同一批旧颜色再转一遍）。
3. 判据：打开 `figures/fig_roadmap.png`，若整张图仍是中性灰（没有任何一处取到
   `palette[0]` 或 `warn`），说明这道没做。

栏宽照参考件写 `0.85\textwidth`，别缩到 0.7 栏（缩到七成栏宽会让节点字直接糊掉：
一张 954×1297 的竖版大图就是这么放错的）。下限由
`python lib/web/check_skeleton.py` 机械核。

**除它之外的非数据图（流程图、示意图）仍守：**

- 配色同源 —— 流程图、结构图、数据流图**可以沿用 `fig_roadmap` 的同一套语义色**
  （主流程 `palette[0]`、判断 `warn`、分组 `box`/`grid`），不再强制黑白；
  但只做语义区分，不做装饰，且必须经得起灰度打印（明度/线型可区分，不能只靠红绿）。
  同类节点同色，跨图同一语义同色；`fig_geometry_3d` 物理立体图也沿用这套低饱和色
  （热/湿/固体/剖面/箭头），不做高饱和装饰色。
- 几何/物理示意可以画三维（轴测） —— 圆柱、球、多层介质、
  空间坐标与方位这类本身就有三维结构的对象，用轴测图比硬压成二维剖切清楚得多。
  透视/正交要注明，遮挡要交代，投影有歧义时配一张二维剖切或投影。
  三维图的具体后端与自检见下面的「第五类非数据图」和
  `references/physical-3d.md`。
- 小 —— 单张 3D 图半栏以内（≈80mm）；两个相近问合并的双面板 ≤120mm。
  小图的作用是"把一句话讲清楚"，不是第二个展台。两张同构的小图并排放
  （`9Paper-writing` 用 `\paperfigurepair`），别各占一个整栏位置。
- **节点更少**：小图节点 ≤ 8 个、层级 ≤ 3 层。现有 11 个节点的 `fig_flow_solve`
  应按此精简（Picard 回路与终点判断是它的核心，保留；其余细节进正文）。

### 第五类非数据图：物理立体 / 3D 剖切示意图（`fig_geometry_3d`）

本阶段的非数据图按用途分五类（前四类沿用原规范）：

| # | 类型 | 典型文件 | 回答的问题 |
|---|---|---|---|
| 1 | 技术路线图 | `fig_roadmap` | 整题怎么走、各问怎么分流 |
| 2 | 子问题求解流程图 | `fig_flow_q*` | 这一问的算法/判断/循环 |
| 3 | 数据处理/模型结构/指标体系/决策树 | `fig_pipeline` / `fig_model` / `fig_index_system` / `fig_decision_tree` | 数据怎么流、模块怎么连、指标怎么分层 |
| 4 | 二维几何/物理示意 | `fig_geometry` / `fig_q4_material` / `fig_flow_solve` | 截面、角度、投影、二维关系 |
| 5 | **物理立体 / 3D 剖切** | `fig_geometry_3d` | 对象长什么样、内部怎么分层、边界加在哪、哪一问的几何变了 |

第五类不是给现有流程图换皮，也不是“每问一张”的装饰图。完整规范见
`references/physical-3d.md`。

**先决定这一问要不要画（按问判重）**：

1. 这一问有独立的几何对象吗？没有（纯判定/查表/统计）⇒ 不画。
2. 和前面某一问的几何差得多吗？只差时间窗/参数/输出、几何同构 ⇒ **合并**：
   同一相机、同一比例的双面板，或“共用模型 + 参数标注”；不要重复画。
3. 是所有问共用的方法细节吗（如有限体积控制体）⇒ 只画一张小图，不放进每一问。
4. 画出来能讲清一个别处讲不清的关系吗？不能 ⇒ 不画，在
   `reports/DRAWIO_REPORT.md` 写一句“本题无独立几何对象/与 Qx 同构，故不画”。

**四条渲染路线，由 agent 按内容选，不是固定模板**：

| 路线 | 适用 | 入口 |
|---|---|---|
| A 透明线框 + 2D 剖切 | 讲内部径向分层、坐标映射、边界；实体不透明会挡住内部 | `assets/physical3d/style3d.py` |
| B 实心剖切 | 实体圆柱/球/多层介质的楔形/半剖；隐藏面与剖面填充重要 | `assets/physical3d/solid3d.py` |
| C 数据场曲面/切片 | 计算结果场 $T(r,t)$ / $C(r,t)$；必须读 `figures/data`，不重算 | `figure-studio` + `solid3d.surface()` |
| D 交互 3D | 网页 demo / 答辩演示，不是论文静态图；交 ⑯ | ⑯ 用 `skills/16Web-demo/assets/scene3d.js` 整段内联实现（见 `skills/16Web-demo/SKILL.md`「动态三维模型」） |

同一内容可以 A/B 各做一个候选，主 agent 选一张，**不要两张都进论文**。
重要 3D 图默认 2–3 个结构候选（A 透明线框 / B 实心剖切 / 合并版）；
优先 `config/agents.json` 的 `fig-3d-candidate`，不可用时用 general-purpose。
子 agent 只写 `tmp/figures/<id>/`，主 agent 选一张定稿并串行导出/登记。

**字体 / 语言 / 宽度**：先跑
`python skills/figure-studio/scripts/resolve_context.py --write`；
中文 → 微软雅黑、正文 ≥8 pt；英文 → Arial。3D 图**不得另起一套 rcParams**，
与数据图、路线图放在一起时字体字号必须看不出差别。

**强制自检 10 条**（打开实际 PNG 在最终印刷尺寸看，逐条复验）：

1. 投影/遮挡写清楚；多面板共用同一相机与比例。
2. 剖面有填充/剖面线/边线，不是空壳。
3. 内部线不穿出实体；被挡住的部分不画；透明面不混成脏灰。
4. 标签不压文字/不压实体/不穿几何；引线从锚点到文字；白描边不是白底框。
5. 箭头物理方向正确（热流入、水分流出、收缩向内、通量正方向）。
6. 字体/语言/字号与其他图一致。
7. 文字完整落在画布内，最小字号 ≥8 pt。
8. 半径/长度/角度按比例；截取段注明；单位齐全。
9. 半栏 ≈80 mm 或合并双面板 ≈120 mm；没有大片空白。
10. 同一几何不在两问各画一张；一张图只讲一件事；图内没有解释性长句。

生成后跑 QA 并把结果写进 `reports/DRAWIO_REPORT.md`：

```bash
python skills/7Route-diagram/assets/physical3d/qa_physical3d.py \
    --pdf figures/fig_geometry_3d.pdf \
    --png figures/fig_geometry_3d.png \
    --scene figures/fig_geometry_3d.scene.json \
    --width-mm 90 --font "Microsoft YaHei" \
    --report reports/FIG_GEOMETRY_3D_QA.json
```

Route A（mplot3d）没有 `.scene.json` 时只查 PDF/PNG；标签仍按上面 10 条目检。

读取这些文件的目的不是提取数据作图，而是理解论文方法、章节结构、子问题关系和已有图表，避免重复。

## 工作流程

### Step 0: 先渲染数据图（本阶段是唯一渲染者）

按上面「数据图渲染」与「出图工作流」两节：验锁 → triage → 候选（落 `tmp/`）→ 自评 →
定稿串行 `save_figure`。**数据图没渲完，不要开始画 draw.io** —— ⑧ 的一等公民是数据图，
非数据图是配角。

### Step 1: 盘点已有图表和需求

先读取以下文件（存在则读取）：`reports/ANALYSIS_MODELING_REPORT.md`、`reports/RESULTS_REPORT.md`、
**`reports/FIGURE_PLAN.md`**、`figures/` 目录列表。

> `FIGURE_PLAN.md` 是本阶段的任务清单来源之一：`4Coding-and-computation` 会在里面
> 点名「本轮哪些非数据图资产需要重画、画成什么样」（尤其**换配色时受影响的 `.drawio`** ——
> 那些图的颜色烤在文件里，`config/visualization.json` 碰不到它们）。不读它就会漏活：
> 全局换现代配色时，三张示意图会自动跟上，而 `fig_roadmap` 一个色都不会换 ——
> 不是不想做，是任务清单里没有这一项。

然后从前序文档提取非数据图需求，输出一个清单：

```text
DRAWIO PLAN CHECKLIST:
[ ] fig_roadmap      技术路线图，放在问题重述/绪论
[ ] fig_flow_q1      问题一求解流程图
[ ] fig_flow_q2      问题二求解流程图
[ ] fig_flow_q3      问题三求解流程图
[ ] fig_pipeline     数据处理流程图
[ ] fig_model        模型结构/变量关系图
```

清单不是固定模板，要根据题目实际删减或增补。不要为了凑图生成无意义图示。

### Step 2: 判定图类型

常见图示选择：

| 图类型 | 文件名建议 | 适用场景 |
| --- | --- | --- |
| 技术路线图 | `fig_roadmap` | 展示整体解题路线、章节逻辑、方法串联 |
| 子问题求解流程图 | `fig_flow_q1`, `fig_flow_q2` | 展示单个子问题的输入、判断、算法、输出 |
| 数据处理流程图 | `fig_pipeline` | 展示数据清洗、特征构造、建模输入 |
| 模型结构图 | `fig_model` | 展示模块关系、变量关系、模型层次 |
| 指标体系图 | `fig_index_system` | 展示目标层、准则层、指标层 |
| 决策树/规则图 | `fig_decision_tree` | 展示分类规则、设备选择、策略分支 |
| 物理立体/3D 剖切示意图 | `fig_geometry_3d` | 对象本身有三维结构（圆柱/球/多层/空间机构），需要表达内部结构、剖面、层位或三维场 |

技术路线图 / 全文概览 / 研究框架图**不再使用 paper-diagram 的五个线性模板**
（`roadmap-5band` / `roadmap-3phase` / `framework-3col` / `stageflow-3col` / `taskflow-land` 已停用：
五带、三阶段、三栏研究框架、三栏阶段、横版任务流水线都不再进入 `fig_roadmap`）。

`fig_roadmap` 按 `references/route-diagram.md` 的结构规范生成，**首选「问题路由树」**：
共用输入/模型 → 真实条件（菱形，出口标「是 / 否」或真实工况）→ 各问分支 → 每支方法小框与结果文档。
若题目各问是并列关系、没有真实路由条件，改用 **「X 问泳道」**：顶部共享输入/模型母线，
每问一条纵向泳道（窗口 → 方法小框 → 真实判据 → 输出），底部检验母线汇合。
**禁止时间轴版式**（2026A 已否决）；图内不出现解释性旁白、图例、注、脚注、总结条。
**字体 / 语言 / 宽度跟数据图走**：先跑 `python skills/figure-studio/scripts/resolve_context.py --write`，
按 `language` / `font` / `width_mm` 画（中文 → 微软雅黑、160 mm；英文 → Arial、183 mm），
不沿用旧模板的字体字号，也不因换结构就单独换字体。

**旧产物一律重画**：`figures/fig_roadmap.drawio` 若来自五个线性模板（旁边有
`fig_roadmap.content.json`，或 XML 里能看出五带/三阶段/三栏/横版结构），视为过期模板，
改名留档后按 `references/route-diagram.md` 重画；不许在旧 XML 上改两笔交差。
重画后重新导出 PDF/PNG、`python -m lib.visualization register` 重登记、重新目检 ——
只换 `.drawio` 不重导出不算。

不要用 DrawIO 画这些图：

- 结果对比柱状图
- 预测误差曲线
- 灵敏度曲线
- 相关性热力图
- 分布图和箱线图

### Step 3: 生成 DrawIO 源文件

每张图一个 `.drawio` 文件，放在 `figures/`。

DrawIO 内容要求：

- 文字语言与论文语言一致。
- 节点文字短，必要时双行，不堆长句。
- 同类节点样式统一。
- 箭头方向清晰，避免交叉。
- 图中不写大段解释，解释留给论文正文。
- 不使用装饰性阴影和过度渐变。

生成大 XML 时，分段写入，避免截断。示例：

```bash
mkdir -p figures
cat << 'XMLEOF' > figures/fig_roadmap.drawio
<mxfile>
  <diagram name="Page-1">
    <mxGraphModel>
      <root>
        <mxCell id="0"/>
        <mxCell id="1" parent="0"/>
        <!-- nodes and edges -->
      </root>
    </mxGraphModel>
  </diagram>
</mxfile>
XMLEOF
```

### Step 4: 导出 PDF（本机无 DrawIO CLI 时，用 matplotlib 兜底画图，见 Step 4b）

优先用可用的 DrawIO 命令导出 PDF：

```bash
DRAWIO_BIN="$(command -v drawio 2>/dev/null || command -v draw.io 2>/dev/null || command -v draw.io.exe 2>/dev/null || true)"
if [ -n "$DRAWIO_BIN" ]; then
  "$DRAWIO_BIN" --export --format pdf --crop --output figures/fig_roadmap.pdf figures/fig_roadmap.drawio
else
  echo "DrawIO command not found; use matplotlib fallback (Step 4b)."
fi
```

如果无法导出 PDF，且没有 DrawIO，**必须走 Step 4b 的 matplotlib 兜底**，不得只留 `.drawio` 源文件就收尾。

### Step 4b: matplotlib 兜底绘制（本机默认路径，DrawIO 不可用时必走）

DrawIO 导出不可用时，用 Matplotlib 生成矢量 PDF。解释器从 config/runtime.local.json 读取。

根据 Step 1 已确认的清单生成，子问题数量和节点内容均取自本题报告。没有独立解释价值的流程不单独画图。

节点形状与配色按"节点类型"定，而不是随手挑（这样读者不看文字也能认出这是输入还是判断）：

本表只是语义映射，色值一律从 `config/visualization.json` 现取，与「小图同源」同一套，不是 Step 4b 专属配色。

| 节点类型 | 形状 | 填充/边框（语义键） |
| --- | --- | --- |
| 输入数据 / 已知条件 | 平行四边形 | `grid` 浅底 / `line` 边 |
| 过程 / 处理步骤 | 圆角矩形 | `grid` 浅底 / `palette[0]` 边 |
| 判断 / 条件分支 | 菱形 | `grid` 浅底 / `warn` 边（仅判断/阈值/异常） |
| 模型 / 算法模块 | 矩形 | `box` / `line` |
| 输出 / 结论 | 圆角矩形（加粗边框） | `grid` / `ink` |
| 反馈 / 迭代回路 | 虚线箭头 | `line` / `aux` |

其余纪律：
- **分区**：用虚线圆角矩形把图分 2–3 个区（如"数据输入 / 模型构建 / 结果输出"），每区一个淡色底 —— 别把所有节点摊成一个平面。
- **主色 ≤ 5 种**；同类节点必须同色同框。
- 箭头要带语义（输入/输出/反馈/迭代），不做纯连线。
- 方向全图统一（自上而下 或 自左向右），不要一半横一半竖。
- 判断分支的"是/否"标注在箭头旁。

matplotlib 画流程图要点：

- 用 `matplotlib.patches.FancyBboxPatch` 或 `Rectangle` 画节点框，`annotate` 画箭头；`fig.add_artist` 布局。
- 中文：`import matplotlib; matplotlib.rcParams['font.sans-serif']=['SimHei','Microsoft YaHei','Noto Sans CJK SC']`，`rcParams['axes.unicode_minus']=False`。
- 矢量输出：`plt.savefig('figures/fig_roadmap.pdf', bbox_inches='tight')`，不写图内大标题（标题交论文 caption）。
- 节点文字短（≤10 字/行，必要时双行），同类节点同色同框，箭头单向清晰、避免交叉。
- 颜色按 `config/visualization.json` 的语义键取（低饱和、灰度可读），不用装饰性阴影/渐变；风格与 5coding 数据图一致（引用 `../_references/math_modeling_norms.md` 图表规范）。

写一个 `figures/make_flow_figures.py` 统一生成已选图（分段写，别一个超长脚本），执行后自检每个 PDF 非空且 `pdfinfo`/文件大小 > 1KB。生成失败就修脚本重跑，不要在报告里空口说明。

### Step 5: 自检和修复

每张图必须检查：

- DrawIO 路径保留非空 `.drawio`；Matplotlib 兜底保留可复现源脚本。
- 若导出成功，`.pdf` 文件非空。
- 节点没有明显重叠。
- 箭头不穿过核心节点。
- 字号、颜色、边框风格一致。
- **文本不许溢出它所在的框、也不许压到框线**。在脚本里量、不靠目测：文本的 `get_window_extent()`（matplotlib）
  或 drawio 里的文本几何，与所在框的矩形比一遍；越界就缩字号 / 改短文案 / 加宽框，别把字塞出去。
  位图层没有这条判据（`quality.texts_overlap` 只查字压字，见 `docs/KNOWN_GAPS.md` 附录里的「待办 8」）⇒ 生成期自检是唯一防线。
- 文件名和图意一致。
- 没有与 `4Coding-and-computation` 的数据图重复。

发现问题要修 `.drawio` 并重新导出，不要只在报告里解释。

### 5.1 大流程图（fig_roadmap）的强制自检回路

`fig_roadmap` 生成/导出后，必须打开实际 PNG 逐框检查，发现问题就改脚本/XML 再渲染，
直到下面 8 条全过；每轮把「第几轮、改了哪些框、复验结果」写进 `reports/DRAWIO_REPORT.md`。
**不许只跑 `check_layout.py` 就收尾** —— 它不查文字是否居中，也不查框是否比文字大太多。

1. **文字居中**：每个框内文字块的水平中心与框中心偏差 ≤ 4 px（或 ≤5% 框宽），
   垂直中心偏差 ≤ 4 px（或 ≤5% 框高）。不居中就改 anchor/坐标，或把框缩到文字大小。
   按框坐标与文字包围盒量，不要靠目测「差不多」。
2. **文字不溢出**：每行都落在框线内，左右留白 ≥ 4 px；长句换行，字号不低于 9 pt。
3. **起止居中**：开始对准第一个框的中心，结束对准最后一个框的中心；箭头垂直进入/离开。
4. **菱形真分支**：每个菱形都有真实出口标签（是/否或真实工况）；没有「按题切片」这类伪判断。
5. **箭头连接**：从框边到框边，不悬空、不穿框、不绕圈、不在框内拐弯。
6. **无解释性文字**：图内没有整句解释、图例、注、脚注、总结条；只有节点事实和分支标签。
7. **并列拆框**：一个框里不塞并列项；大框只做容器，容器内每项有自己的小框。
8. **空白与对齐**：同列同宽、同行同高、间距统一；没有大片空白或明显偏心。

### Step 6: 写生成记录

创建 `reports/DRAWIO_REPORT.md`，至少包含：

```markdown
# 数据图与非数据图示生成报告

## 数据图清单
| figure_id | claim | recipe | 宽度 | 锁定状态 | 状态 |
| --- | --- | --- | --- | --- | --- |

## 选图决策
| figure_id | claim | 数据形态 | 候选 recipe | 淘汰理由 |
| --- | --- | --- | --- | --- |

## 自评（1–5 分）
| figure_id | claim 支持 | 信息密度 | 可读性 | 灰度 | 语言/统计 | 冗余 | 结论 |
| --- | --- | --- | --- | --- | --- | --- | --- |

## 本轮改动面（返修时）
| figure_id | 原问题 | 改法 | 复验 |
| --- | --- | --- | --- |

## 非数据图示清单
| 文件 | 类型 | 来源依据 | 用途 | 状态 |
| --- | --- | --- | --- | --- |

## 3D 物理立体图自检（有 fig_geometry_3d 时）
| figure_id | 路线 | 投影 | 标签越界/压实体 | 剖面/隐藏面 | 与同构问是否合并 | QA 报告 |
| --- | --- | --- | --- | --- | --- | --- |

## 未生成图示及原因

## 导出与自检记录

## 给论文阶段的嵌入建议
```

嵌入建议只说明每张图适合放入哪个章节和建议 caption。最终的图表插入代码（LaTeX 的 `\begin{figure}...\end{figure}`）由 `9Paper-writing` 根据论文结构决定。

## 质量要求

- 图示服务论文论证，不为装饰而画。
- 每张图必须能对应到`reports/ANALYSIS_MODELING_REPORT.md` 中的真实方法。
- 数据图由本阶段按 `figures/spec/*.json` 渲染，不得另起一套数据、另算一份结果。
- 论文阶段引用的非数据图都应有 `.drawio` 源文件和 PDF，或者在 `reports/DRAWIO_REPORT.md` 说明导出失败。

## 动态交回规则（发现前序阶段错了）

> **先看这一条：画法与图注文字类的缺陷，一律就地修，不许往上交**。
> 色标档界读不出、标注被轴裁掉、图例压线、caption 数字写错 —— 这些都在你的授权里
> （见「阶段边界」的四类白名单与三条硬判据）。**交回只留给"必须动数值或口径来源"那一类。**
> 一次这样的交回 = ④ 41 min + ⑤⑥ 58 min + ⑦⑧ 72 min ≈ 2h51m，换四行不碰数值的改动。

若出现以下任一情况 —— **画图所需的关键数据缺失、`figure_lock verify` 报 `[lock:data]`/`[lock:contract]`
且不是本阶段改的、或图与 `reports/RESULTS_REPORT.md` 对不上到"必须动数值/口径"的程度** ——
不要画一张「大概是这样」的示意图充数，那会变成论文里的假证据；也不要自己改 bundle/spec/claim。

创建 `reports/HANDBACK_REQUEST.md`：

```
target: <code | robustness | analysis>
reason: <一句话说清：哪里不对、期望改什么>
```

然后停止本阶段并结束本轮（不要继续往下做，更不要编造数值把坑填上）。
编排器会把它作为回退建议交给用户决策（黄灯面板），确认后才补跑；补跑完自动回到本阶段续跑（届时 `HANDBACK_REQUEST.md` 已被清除）。**不再自动回退** —— 失败/超时一律转黄灯等人。

> 机制事实：驱动对每一个阶段都调 `check_handback()`，并为「阶段写了 HANDBACK」专门开了
> 非失败通道 —— 所以交回不等于本阶段失败，不会污染回执。已用上它的 7 个阶段：
> 5coding / 6Robustness / 7Route-diagram / 14Layout-and-format / 9Paper-writing / 11Cross-question-check / 15Verification。
