---
name: 4Coding-and-computation
description: "数学建模编程实现与数据图表生成阶段。根据 ANALYSIS_MODELING_REPORT.md 编写可复现代码、运行求解、验证约束、输出 RESULTS_REPORT.md 并生成论文可用的数据驱动图表 PDF。"
allowed-tools: PowerShell, Read, Write, Edit, Grep, Glob, Agent, WebSearch, WebFetch
---

# 编程实现与数据图表生成

> 通用执行纪律（增量返修 / 缩比预估 / 分段落盘 / 方法标记 / 返修只动清单内）见 `../_references/stage_discipline.md`。
> 本阶段适用：一（增量返修，含 1.1 探针复用）、二（缩比预估）、三（分段落盘）、四（方法标记）、五（返修只动清单内）。
> **探针/量测脚本要复用（通用纪律 一·1.1）**：本轮写的取证/量测脚本一律留在 `_tmp/`
> （另有散落的在 `tmp/`，两个都要看）；下一轮开工第一步 = `ls _tmp/ tmp/` → 把上一轮
> 为同一批对象写过的脚本先原样重跑（秒级，确认数在当前版本里还成立）→ 只对本轮新出现或改过
> 的对象写新脚本。别每轮从零重写 —— 全链 776 个自写脚本里 **683 个（88%）只被用过一次**
> 就再也没人碰。复用探针 ≠ 跳过复核：探针只是取证手段，判定仍逐条对着当前版本做。

本 skill 承接 `2Modeling-design`。目标是把 `reports/ANALYSIS_MODELING_REPORT.md` 里的模型和算法落实为可复现程序，跑出可信结果，并生成论文中需要的数据型图表。

## 结构化数值与独立校验

本阶段：`python -m lib.result_contract build`（产出结构化结果与独立校验）；报错信息即规范，需要细节才读 docs/RESULT_CONTRACT.md。

## 通用绘图协议

按 `python -m lib.visualization` 的规范：先写 FIGURE_PLAN，再从公共绘图库选型；导出、登记全部来源、目检后单独记录复核。完成条件为 `python -m lib.visualization audit` 通过，且 RESULTS_REPORT 引用图表对应真实结果。

## 数学建模规范参考

如需领域判断，读取 `../_references/math_modeling_norms.md` 中的“题型防错速查”“代码实现与结果”“编码阶段常见错误”和“图表与可视化”小节。该文件只作为规范知识库，不新增本阶段的固定产物。

## 阶段边界

- 本阶段负责：代码、实验运行、结果、结果表、数据驱动图表。
- 本阶段不负责：技术路线图、算法流程图、系统架构图、概念示意图。这些交给 `7Route-diagram`。
- 本阶段不写论文正文，只为 `9Paper-writing` 提供可信数值和图表资产。

**交付出去的代码要能平铺运行**：提交件里**没有 `code/` 前缀** —— 全部 `.py` 平铺在同一目录。
所以代码之间的 import 必须是同目录裸名（`import core`，不是 `from code import core`），
读数据/写结果的路径要相对当前工作目录解析，不能写死 `code/outputs/…`。
至少提供一个主入口（约定 `run_all.py`），依次跑完「读附件 → 各问求解 → 收支核对 → 导出结果 → 检验」。
分问脚本（`q1.py`…）与辅助脚本保留，由 `14Layout-and-format` 决定哪些进提交清单、哪些只进产物的 `其余文件/`。

## 被退回重跑时：上一版的 `code/`+`results/` 就在盘上，先捞回来（别重算）

④ 被下游门禁退回后，上一版的产物已经被驱动整包暂存走了，
而 SKILL 从没说过它们在哪 ⇒ 每轮都靠 agent 自己想到 `Copy-Item`；想不起来就是小时级重算。

**事实（驱动侧现成能力）**：任何回退/换题/清理都会把本阶段的产物移（不是删）到

```
<产物根>/cache/<题目标识_日期_时间>/<本阶段中文名>/…        ← 回退暂存，按阶段分文件夹
<产物根>/cache/<题目标识_日期_时间>/工作区原件/…             ← 换题时的工作区原件
```

捞法：`ls -dt 产物/cache/*/编码计算 | head -1`（取最新一份），再 `cp -r` 回来；
`results/*.json` 与 `code/outputs/*.json` 都在里面，先复用它们，只在清单要求时才重算受影响的量
（增量重算清单见 `../_references/stage_discipline.md` 第一节）。报告里如实写「复用上一版（未受影响：〈理由〉）」。

## 返修只动清单内（被门禁退回时必读）

按回执返修时，**改动范围必须严格等于回执清单**。四条硬纪律的权威表述见
`../_references/stage_discipline.md` 第五节 —— 此处不复制正文（复制必然漂移：
同一条纪律在不同阶段措辞不同，新加的阶段直接没有）。

**本阶段的典型踩坑点**：代码尤其危险 —— 改一处数值会影响下游全部派生量，顺手改动会被 5Result-credibility-audit 当成新缺陷抓出来。改完必须重跑受影响子问题及其全部下游（派生指标 → 汇总 → 图表 → result_contract）。

## 运行环境
## 数据读取与预处理
## 问题一结果
## 问题二结果
## 问题三结果
## 灵敏度分析
## 约束与一致性校验
## 与建模报告的一致性说明
## 可复现运行方式
```

所有数据和图表结果都必须出现在 `reports/RESULTS_REPORT.md` 中引用

### Step 4: 生成数据驱动图表

根据 `reports/ANALYSIS_MODELING_REPORT.md` 和 `reports/RESULTS_REPORT.md` 规划图表，生成 PDF 到 `figures/`。

> **分工**：本阶段负责数据图的首次生成，以及数据/口径变更后的重画
> （`sources` 的 npz 变了、claim 的语义要改、色标口径要按新判据定 —— 这些是 ④ 的活）。
> 而"图画得好不好"（图例位置、遮挡、档界读得出读不出、标注被裁、caption 数字写错）
> 由 ⑦技术路线图在后续轮次就地优化，不再回退本阶段 —— 那是纯图片面的活，一行数值都不动。
> 所以：本阶段交出的图不必一次就尽善尽美，但**数值、claim 语义、`sources` 必须是对的**。

> **画图脚本住 `figures/`，不住 `code/`** —— 数据图脚本命名为 `figures/make_figures.py`
> （登记进 `figures/manifest.json` 的 `script` 字段时也写这个相对路径）。
> `code/` 在 ⑤⑥⑦⑧ 的输入指纹里，而图的内容不含任何数值结论 ——
> 脚本放进 `code/` 之后，改一行画图代码（换个配色、调个字号）就会连锁触发 ⑤⑥ 重跑，
> 白烧几十分钟；放 `figures/` 就没这个连锁（`figures/` 刻意不进任何阶段的输入指纹）。
> 脚本写到 `code/make_figures.py`、`figures/manifest.json` 里登记的也是它，会被
> `regression/test_stale_noise.py` 的 `test_the_data_figure_script_lives_under_figures`
> 抓到（它只在 ④ 跑完、`figures/` 存在时才判）。

典型图表：

- 预测类：真实值-预测值对比、误差分布、指标对比。
- 优化类：收敛曲线、成本对比、资源利用率、方案前后对比。
- 评价类：综合得分排序、雷达图、热力图、敏感性曲线。
- 数据理解：分布图、趋势图、相关性图、箱线图。

图表要求：

- PDF 矢量输出，适合论文。
- 不在图内写大标题，标题交给论文 caption（LaTeX 的 `\caption{}`）。
- 中文论文图表使用中文坐标轴和图例；英文论文使用英文。
- 不生成流程图/架构图/路线图。

**别把每张图都画成折线**（典型错误：12 张图里 11 张是 trend/comparison，
热力图/等高线一张没有）。先问"我要画的量在几个维度上有结构"：

| 量的结构 | 该用的图 | 别用什么 |
|---|---|---|
| 场 —— 标量在 (空间 × 时间) 或 (空间 × 空间) 上 | 热力图（`charts.heatmap`，逐格读数）或填充等高线（`charts.contour`，有阈值/前沿时它把"哪里是 0.15"画成一条线） | 折线：一条线只能切出一片剖面，场本身的结构看不见 |
| 沿某个 x 或 t 的切片 | 折线（`charts.trend`；要画不确定度就传 `low=/high=` 加区间带） | —— 这才是折线的位置 |
| 类别间比较 / 排序 | 柱状（`charts.bars`，2–5 个类别、要直接读数）、误差棒（`charts.comparison`，十几个类别横排） | 折线（类别不是连续量，连起来是假的） |
| 两变量的关系 / 响应面 | 散点、`charts.response`、三维 `charts.surface3d` | 折线 |
| 分布 | 直方图（`charts.distribution`，看形状）、箱线（`charts.boxplot`，多组同图比较、可 `log_scale`）、累积分布（`charts.ecdf`，直接读"小于某值的比例"） | 折线；小提琴图库里没有（要核密度估计）——要那层信息就用箱线 + ECDF 顶上 |

本类问题的状态量 —— 温度 $T(r,t)$、水分浓度 $C(r,t)$ —— 各是一张二维场。
典型失手：整题只给了"六个时刻的剖面族"，于是穿透深度、干前沿推进、热点移动这些
只有从场里才看得见的东西全都没画出来。场用热力图/等高线，再配一两张关键切片折线，
信息量比六张折线大得多。

选型权仍在画图者（配置里的 `encouraged_when_semantically_useful`），但
二维场默认先想热力图/等高线，折线是它的补充而不是默认。

三维：物理/数学相关的内容可以且应当考虑。判据只有一条 ——
第三维真有变量含义，不是"图好看"：空间结构（圆柱/球/多层介质里的场）、响应面
（两个参数 → 一个指标）、三维轨迹、多变量关系、优化地形。这类内容硬压成折线或热力图，
会把"两个参数怎么共同影响结果"这层信息丢掉。

用三维必须配齐三件事（`config/visualization.json` 的 `_three_d_note` 也记着）：

1. 视角可读 —— 别用看不穿的等轴投影把遮挡糊住；该转的角度要转对。
2. 查遮挡 —— 前后哪一块盖住哪一块，得说清。
3. 投影有歧义就配一张二维图 —— 切片、投影或等高线，跟三维图并排（`\paperfigurepair`）。

**三维数据曲面用 `charts.surface3d()`，不要手写 `ax.plot_surface`**。
这个家族不是"封装一下"，它修的是两个每题都会重犯的缺陷，默认值在
`config/visualization.json` 的 `surface`、理由在 `_surface_note`：

① 淡色低值平台会糊在白底上（典型：米色背景配白线看不清）—— 地表/浓度场这类曲面
   的低值区常是一大片平台，而感知均匀色阶的低端多是淡色（`YlGnBu` 的浅黄、`viridis` 的暗紫），
   一大片淡色铺在白底上就看不出形状了。细网格边（`edgecolor`+`linewidth`）让起伏与走向重新可见，
   `rcount` 抽稀行数（全画会密成一片灰）。
② mplot3d 默认把盒子缩在面板正中，四周大片空白 —— 这就是"三维图特别丑"的另一半原因。

判据线/阈值线用 `level=`（如 `level=0.15` 画"C = 0.15 与曲面的交线"）——
它不是 `ax.contour`：mplot3d 的等值线集合会被曲面本身遮住（画了、层数也在，眼睛看不见），
本函数改为逐列求交连成三维折线。三维盒子的长宽比是数据决定的，要改就显式传
`box_aspect=`（不给则完全不动轴）。视角默认 `elev 25 / azim 45`，可用 `view=` 覆盖。

现成工具：`visualization.geometry.orthographic()`（Nx3 → 二维视平面）与
`sphere_section()`；画法与验收标准见 `docs/GEOMETRY.md`。
`config/visualization.json` 的 `chart_mix` 记着这条口径与每问的下限
（每问 ≥2 张数据图，且至少一张不是折线）。

**图例与配色（两道机器闸门，改不动就过不了复核）**：

- **图例必须有底色** —— `charts.style()` 全局已设 `legend.frameon: True`。别改回 False：
  图例一旦落在曲线区上，曲线会从标签文字里穿过去，标签就读不出来了（如 `q1_profiles`）。
- 图例别压在稠密数据上 —— `export()` 会算出图例框内有几个采样点属于可见曲线，
  超阈值就进 `auto_issues`，而 `evidence.review()` 拒绝复核带 auto_issues 的图。
  报出来就把 `loc` 挪到空的地方，或缩掉曲线区间。
- **一条线一个颜色**：`config/visualization.json` 的 palette 有 8 色、linestyles 与之并行循环。
  **单图序列不要超过 8 条** —— 超了颜色会回绕、两条线同色，`_palette_note` 里写了"必须拆面板"。
- 连续量的色阶按物理量选，不按审美选 —— 传 `quantity=`（`heatmap` / `response` /
  `surface3d` 都收），色阶由 `config/visualization.json` 的 `quantity_cmap` 登记处给：
  `quantity="temperature"` → `inferno`（热=亮）、`quantity="moisture"` → `YlGnBu`（湿=深蓝）。
  **别自己写死 `cmap="viridis"`**：同一批交付里 8 个连续量面板全成了同一种蓝→黄色，
  且温度场用 viridis 时冷=亮黄、热=暗紫——语义与直觉相反，读者得读数值才知道哪边热。
  表里没有的量：往 `quantity_cmap` 加一行（**必须写清哪一端是"大"**），别在脚本里就地编 ——
  就地编会让同一个量在两张图上换色。用 `quantity=` 还顺带满足"颜色语义跨小问一致"。
- **手写 `ax.plot` 时必须显式给 `linestyle`** —— 一个容易踩的陷阱
  （如 `fig_geometry` 的圆柱"断成虚线"）：`charts.style()` 的 `axes.prop_cycle`
  同时含颜色与线型，所以每调用一次 `ax.plot(...)` 就吃掉循环里的下一个线型 ——
  只给 `color=` 不够，第二条自动变虚线、第三条变点线，而 `rcParams` 里明明写着实线。
  示意图/几何图这类线的连续性有含义的图尤其致命（圆柱母线断成一节节）。
  走 `schematic.Scene` 的图元不受影响（它内部显式传了 `linestyle`）。
- 注记别互相压 —— `export()` 现在会两两比对显式注记的框（`quality.texts_overlap`），
  重叠占较小那个框 ≥ 55% 即进 `auto_issues`（挡复核），30–55% 只打印提醒。
  例（`fig_geometry`）：标签间距取 4.6 时「对流传质／水分出」第二行压到下方四行首行。
  它按面积判，所以"挤但没压"（净空只剩几像素）它不报 ——
  别把它的沉默当成"排版没问题"，余量仍靠目检。
- 位图另有分辨率下限（800×480 px）与"近似纯色"检查，空白图会被挡下。

**换了配色，就要在 `reports/FIGURE_PLAN.md` 里点名受影响的非数据图资产**

本阶段是图规划的作者 —— 而**配色改动不会自动传到 `.drawio` 资产**：那些图的颜色是
「烤」在文件里的，`config/visualization.json` 怎么改都碰不到它们。全局换了现代配色后，
三张示意图跟着配置自动重渲，而 `fig_roadmap` 一点没变 —— ⑦ 读到了 SKILL 里的规矩，
但它的任务清单来自输入 ⇒ 清单里没有这一项，它不会自己推断出来。

**所以**：只要本轮动过 `config/visualization.json` 的 `palette` 或语义键，计划里就要写一条
「受影响的非数据图：`figures/*.drawio`（逐个列名）+ 按语义键重画 + 判据（PNG 里能看到
`palette[0]` 或 `warn`）」。

—— 「改生成器」不等于「把规矩写进 SKILL」就算完：还要让执行者读到它。

准备给论文并排的图，两张的宽高比要一致 —— `\paperfigurepair` 让它们各占半栏；
一个 4:3、一个 16:9 并排放会一高一矮。同构的两张图（如两个时刻、两种口径）
优先做成一对，别各发一张整栏的。

图表可以由主程序或独立脚本生成，不强制固定脚本名。无论采用哪种方式，都必须保存图表对应的数据来源和生成记录。


## 项目运行环境

用 config/runtime.local.json 指定的解释器运行代码与依赖检查；缺包先执行 `runtime/doctor.py`，记录缺少内容，不凭旧环境清单换解释器。

## 动态交回规则（发现前序阶段错了）

若发现建模报告里的公式实现不出来、自相矛盾、或与题面/数据对不上 —— 这不是编码问题，硬写只会把错误固化进结果。

创建 `reports/HANDBACK_REQUEST.md`：

```
target: <literature | analysis | review>   # 只能写本阶段的前序阶段：
                                            #   code 是第 4 步，写 robustness/audit/drawio
                                            #   之类后继阶段会被 check_handback 静默归档忽略（不报错）
reason: <一句话说清：哪里不对、期望改什么>
```

然后停止本阶段并结束本轮（不要继续往下做，更不要编造数值把坑填上）。
编排器会把它作为回退建议交给用户决策（黄灯面板），确认后才补跑；补跑完自动回到本阶段续跑（届时 `HANDBACK_REQUEST.md` 已被清除）。**不再自动回退** —— 失败/超时一律转黄灯等人。

> 机制事实：驱动对每一个阶段都调 `check_handback()`，并为「阶段写了 HANDBACK」专门开了
> 非失败通道 —— 所以交回不等于本阶段失败，不会污染回执。已用上它的 7 个阶段：
> 5coding / 6Robustness / 7Route-diagram / 14Layout-and-format / 9Paper-writing / 11Cross-question-check / 15Verification。
