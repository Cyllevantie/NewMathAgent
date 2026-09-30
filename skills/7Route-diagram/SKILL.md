---
name: 7Route-diagram
description: "数学建模非数据型图示绘制阶段。根据 ANALYSIS_MODELING_REPORT.md、RESULTS_REPORT.md 和已有 figures/ 生成技术路线图、子问题求解流程图、模型结构图、数据处理流程图等 DrawIO 图，并导出论文可引用 PDF。"
allowed-tools: PowerShell, Read, Write, Edit, Grep, Glob, Agent, WebSearch, WebFetch
---

# DrawIO 非数据图示绘制

> 通用执行纪律（增量返修 / 缩比预估 / 分段落盘 / 方法标记 / 返修只动清单内）见 `../_references/stage_discipline.md`。
> 本阶段适用：一（增量返修，含 1.1 探针复用）、五（返修只动清单内）。
> **探针/量测脚本要复用（通用纪律 一·1.1）**：本轮写的取证/量测脚本一律留在 `_tmp/`
> （另有散落的在 `tmp/`，两个都要看）；下一轮开工第一步 = `ls _tmp/ tmp/` → 把上一轮
> 为同一批对象写过的脚本先原样重跑（秒级，确认数在当前版本里还成立）→ 只对本轮新出现或改过
> 的对象写新脚本。别每轮从零重写 —— 全链 776 个自写脚本里 **683 个（88%）只被用过一次**
> 就再也没人碰。复用探针 ≠ 跳过复核：探针只是取证手段，判定仍逐条对着当前版本做。

本 skill 承接 `4Coding-and-computation`。它只负责论文中的非数据型图示，例如技术路线图、求解流程图、模型结构图、数据处理流程图、变量关系图、指标体系图等。

## 几何表达与篇幅排版

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
3. 每张示意图只讲一件事，标签用题面/论文里的符号（与符号表一致），
   不要在一张图里叠三层含义；辅助线细而弱、主对象粗而深。

**数量按需分配，不要理解成"全题只准画一张"**：每个子问题、每个需要直观理解的对象都可以有自己的示意图。
判据是"这张图能不能让读者少读一段文字就懂"，而不是"总共几张"。没有几何/物理对象的子问题就不配图。

**演化与对比类必须用多面板，不要硬塞进一张**：
- 有"动起来"的过程（运动/传播/演化/收敛），用同一场景的两个（或多个）时刻并排表达：
  t₁ 与 t₂、初始态与终止态、迭代前与迭代后——各面板共享同一坐标范围与视角，否则读者无法比较。
- 对比类（不同参数/不同方案/优化前后）同理并排；面板标题写清各自状态（如"(a) $t=0$"、"(b) $t=T$"）。
- 用 `schematic.scene2d_panels` / `scene3d_panels` 建共享画布，各面板按同一套坐标画；
  3D 多面板**必须共用同一 `camera` 与 `limits`**，否则形变会让对比失效。

**不要套现成形状**：`geometry.py` 里的 `sphere_section` 等是布局示例，不是"每道题都画球"的模板。
先前的问题正是"库里只有球截面，于是什么题都画个球"。现在有了通用图元，图应当长得像这道题。
若题面是纯数据/统计/优化问题（没有几何或物理对象），就不画示意图，别硬凑。

## 通用绘图协议

读取项目根目录 `docs/VISUALIZATION.md` 的自定义图登记与视觉复核协议。根据本题实际方法选择图示，并登记来源、可编辑源和导出资产；目检后单独记录复核。

图中文字写成面向论文读者的方法、输入与输出；绘图报告不能用流程完成状态代替正文采用状态。

## 数学建模规范参考

如需领域判断，读取 `../_references/math_modeling_norms.md` 中的“图表与可视化”和“非数据图工具选择”小节。该文件只作为规范知识库，不要求为了凑数量生成额外图示。

## 阶段边界

- 本阶段负责：DrawIO 源文件、非数据图 PDF、图示生成记录；以及数据图的"画得好不好"（见下）。
- 数据图的首次生成由 `4Coding-and-computation` 负责；画法与图注文字的后续优化，由本阶段就地改。
  允许改的只有"落在图片面、不碰数值"的东西：
  `legend(loc=)` / `bbox=` / `xlim`·`ylim` / `clip_on` / 色标档界 `levels` / `gamma` / 字号 /
  线宽 / `edgecolor` / 抽稀 `ccount`·`rcount` / caption 与 claim 里的数字按现算改正。
- 本阶段**仍然不许**：改 `code/`、改 `results/`、改任何 `*.npz`、改 `figures/manifest.json` 的
  `sources` 字段、改 claim 的语义（说什么、什么条件下成立 —— 那是 `4Coding-and-computation` 的事）、
  改 `reports/RESULTS_REPORT.md` 的数值结论、重跑模型。
- 改完的硬判据（逐条都要满足，缺一条就说明这次要动的是"数值或口径来源"⇒ 那才走交回）：
  ① `code/`、`results/`、所有 `*.npz`、`figures/manifest.json` 的 `sources` 与改动逐字节相同；
  ② 重跑 `figures/make_figures.py` 重渲 + 重新登记 + 重新目检（自述要写实际看到的，别照抄旧 note）；
  ③ `python -m lib.visualization audit` PASS。
- ⑧ 判 FAIL 的 4 条全是"画法/图注"，若按"只准交回 ④"的旧边界，一次交回的代价是
  ④ 41 min + ⑤⑥ 58 min + ⑦⑧ 72 min ≈ 2h51m，换来的 4 处改动一行数值都不动。

## 必须产出

在当前工作目录创建或更新：

```text
figures/
  fig_roadmap.drawio
  fig_roadmap.pdf
  fig_flow_q1.drawio
  fig_flow_q1.pdf
  ...
reports/DRAWIO_REPORT.md
```

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

## 一张大图，其余一律小图黑白

全文只留一张"大图"：`fig_roadmap`（论文里的图 1「分析流程图」）。它破例：
可以宽、可以有配色、可以信息密度高。它的位置是「问题重述」之后、「问题分析」之前
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

**除它之外的非数据图（流程图、示意图）一律：**

- 黑白 —— 灰阶 + 线型区分，不上彩色。理由与 norms 同：论文要经得起灰度打印，
  而满篇彩色小图会把读者的注意力从那张大图上拽走。`schematic.MAIN/ACCENT` 那套配色
  只给 `fig_roadmap` 用；`fig_flow_solve` / `fig_geometry` / `fig_q4_material`
  走灰阶（浅灰底 + 深灰边 + 黑字即可，参见现 `fig_flow_solve` 的浅色底做法，再统一去掉色相）。
- 几何/物理示意可以画三维（轴测） —— 圆柱、球、多层介质、
  空间坐标与方位这类本身就有三维结构的对象，用轴测图比硬压成二维剖切清楚得多。
  仍然守上面"黑白 + 小"两条；透视/正交要注明，遮挡要交代，投影有歧义时配一张
  二维剖切或投影。现成工具 `visualization.geometry.orthographic()` /
  `sphere_section()`，画法与验收见 `docs/GEOMETRY.md`（那份协议本来就是为三维写的）。
- 小 —— 半栏以内（≈80mm），与前一条配套：小图的作用是"把一句话讲清楚"，
  不是第二个展台。两张同构的小图并排放（`9Paper-writing` 用 `\paperfigurepair`），
  别各占一个整栏位置。
- **节点更少**：小图节点 ≤ 8 个、层级 ≤ 3 层。现有 11 个节点的 `fig_flow_solve`
  应按此精简（Picard 回路与终点判断是它的核心，保留；其余细节进正文）。

读取这些文件的目的不是提取数据作图，而是理解论文方法、章节结构、子问题关系和已有图表，避免重复。

## 工作流程

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

技术路线图 / 全文概览 / 研究框架图优先用 `paper-diagram` skill 的版式模板（`../paper-diagram/SKILL.md`）：
- `roadmap-5band`（五带技术路线图）、`roadmap-3phase`（三阶段问题驱动）、`framework-3col`（三栏研究框架）、`stageflow-3col`（三栏阶段流程）、`taskflow-land`（横版任务流水线）。
- 每个模板带 `example.json`（内容槽位）与渲染脚本 `../paper-diagram/scripts/roadmap_5band.py` 等，产可编辑 `.drawio`；用 `../paper-diagram/scripts/check_layout.py` 校验版式（文字溢出/重叠/箭头穿盒）。
- 若这些版式模板都不契合本题，再退回本 skill 的手写 `.drawio` 或 matplotlib 兜底。

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

| 节点类型 | 形状 | 填充/边框 |
| --- | --- | --- |
| 输入数据 / 已知条件 | 平行四边形 | 淡蓝 `#E3F2FD` / `#1565C0` |
| 过程 / 处理步骤 | 圆角矩形 | 淡绿 `#E8F5E9` / `#2E7D32` |
| 判断 / 条件分支 | 菱形 | 淡橙 `#FFF3E0` / `#E65100` |
| 模型 / 算法模块 | 矩形 | 淡紫 `#F3E5F5` / `#6A1B9A` |
| 输出 / 结论 | 圆角矩形（加粗边框） | 淡红 `#FCE4EC` / `#AD1457` |
| 反馈 / 迭代回路 | 虚线箭头 | 灰 `#333333` |

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
- 颜色用低饱和（灰蓝/灰绿），不用装饰性阴影/渐变；风格与 5coding 数据图一致（引用 `../_references/math_modeling_norms.md` 图表规范）。

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

### Step 6: 写生成记录

创建 `reports/DRAWIO_REPORT.md`，至少包含：

```markdown
# DrawIO 图示生成报告

## 图示清单
| 文件 | 类型 | 来源依据 | 用途 | 状态 |
| --- | --- | --- | --- | --- |

## 未生成图示及原因

## 导出与自检记录

## 给论文阶段的嵌入建议
```

嵌入建议只说明每张图适合放入哪个章节和建议 caption。最终的图表插入代码（LaTeX 的 `\begin{figure}...\end{figure}`）由 `9Paper-writing` 根据论文结构决定。

## 质量要求

- 图示服务论文论证，不为装饰而画。
- 每张图必须能对应到`reports/ANALYSIS_MODELING_REPORT.md` 中的真实方法。
- 数据型图表不得在本阶段重复生成。
- 论文阶段引用的非数据图都应有 `.drawio` 源文件和 PDF，或者在 `reports/DRAWIO_REPORT.md` 说明导出失败。

## 动态交回规则（发现前序阶段错了）

> **先看这一条：画法与图注文字类的缺陷，一律就地修，不许往上交**。
> 色标档界读不出、标注被轴裁掉、图例压线、caption 数字写错 —— 这些都在你的授权里
> （见「阶段边界」的四类白名单与三条硬判据）。**交回只留给"必须动数值或口径来源"那一类。**
> 一次这样的交回 = ④ 41 min + ⑤⑥ 58 min + ⑦⑧ 72 min ≈ 2h51m，换四行不碰数值的改动。

若发现**画图所需的关键数据缺失、或图与 `reports/RESULTS_REPORT.md` 对不上到"必须动数值/口径"的程度** —— 不要画一张「大概是这样」的示意图充数，那会变成论文里的假证据。

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
