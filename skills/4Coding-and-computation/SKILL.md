---
name: 4Coding-and-computation
description: "数学建模编程实现与数据交付阶段。根据 ANALYSIS_MODELING_REPORT.md 编写可复现代码、运行求解、验证约束、输出 RESULTS_REPORT.md，并把每张数据图的只读数据包、图 spec 与 figure lock 交给 7Route-diagram 渲染。"
allowed-tools: PowerShell, Read, Write, Edit, Grep, Glob, Agent, WebSearch, WebFetch
---

# 编程实现与数据交付

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

## 计算后端：CPU 串行 / CPU 并行 / GPU（先量测再选）

> 详细规则与代码模板见 `references/compute-backends.md`；开工先跑
> `python skills/4Coding-and-computation/scripts/detect_compute.py --problem <形态> --batch <规模>`。
> 它只探测 CPU/内存/GPU 与 `torch/cupy/jax` 是否真的可用，不安装、不启动训练。

- **1D 径向 PDE / 三对角时间推进**：CPU 串行。GPU 的 kernel 启动、小数组和顺序依赖
  会让它更慢；A 题主流程十几分钟，不要为它引入 GPU。
- **独立实验**（多问、参数扫描、Monte Carlo、PSO 重启、收敛实验）：CPU 多进程
  `ProcessPoolExecutor`，`max_workers` 按逻辑核与**峰值内存**取，不是越多越好；
  2D 轴对称稀疏 LU 默认 ≤3 路（实测 12 路全部 `MemoryError`）。
- **GPU**：只用于大型稠密线性代数/响应面，或批量足够大且目标函数已整体向量化的
  Monte Carlo/PSO；先用 10% 缩比基准测 CPU vs GPU，**≥2×** 才保留 GPU 内核，并必须有 CPU fallback。
  不要为了“用 GPU”预装大型深度学习环境；SciPy/SuperLU 不会自动上 GPU。
- **单一交付写者**：并行 worker 只写 `_tmp/` 或按任务分开的临时结果，主进程最后串行合并、
  写 `code/`/`results/`/`figures/data`；不要多个 worker 同时写正式产物。
- 下面「默认不并行」说的是**方法对照的子 agent**（避免多个写者改 `code/`），
  不是禁止数值程序内部用多进程/GPU。

## 数值方法对照（按需，不默认）

**默认不并行（写正式产物）**：④ 是单一数据源，`code/`、`results/`、`figures/data`
只能有一个写者。返修时的**只读诊断**可以并行，见下文「返修编排」。
只有同时满足下面两条时才开方法对照：

1. ② 选定的数值路线存在 **≥2 个可行离散/求解方案**（如固定网格 vs 材料坐标、半隐式 vs 全隐式、
   Brent vs 二分、直接法 vs 迭代法）；
2. 选择会**显著影响**精度、成本或稳健性，且看论文/报告无法直接定夺。

做法：

- 用 2–3 个子 agent，在 `_tmp/method_bakeoff/<name>/` 各写一个**最小原型**，跑同一个缩比问题、
  同一套指标（误差/收敛阶、耗时/内存、参数与网格扰动下的稳健性）；
- 子 agent **只写 `_tmp/method_bakeoff/`**，不写 `code/`、`results/`、`figures/data`、`*.lock.json`；
- 主 agent 看结果选 1 个，写进 `code/`，在 `RESULTS_REPORT.md` 记一行「方法对照与选择理由」
  （候选、指标、为什么选它）；
- 方法唯一、或对照只会重复教科书的结论 → 直接实现，不要为对照而对照。

独立复算的「影子计算」优先放 ⑤/⑮ 的审计里，不在 ④ 里重复做。

## 创新台账：baseline vs intervention 必须真跑

② 的 `reports/INNOVATION_LEDGER.json` 里每个 `status=adopted` 项都预注册了
`claim / predicted_delta / test / kill_if`。本阶段的任务不是“让 delta 出现”，而是**按预注册的
test 真跑 baseline 与 intervention，把结果如实写进自己的 sidecar**。

1. 读设计台账；对每条 adopted：
   - `baseline` 用 `baseline_id` 对应的基线方案跑一遍；
   - `intervention` 只改该候选声明的那一处（方程/边界/判据/状态量），其余口径、网格、
     时间步、参数、随机种子与 baseline 完全一致；否则 delta 不可归因。
   - 两边都走同一套结果导出与校验；结果文件写到 `results/`，不得只写 `_tmp/`。
   - 对 `kind="contribution"` 的项：`baseline` 用 `baseline_id` 指向的**朴素基线卡**
     （如 `BASE-Q4-N`：固定域、体积平均判据、把 R(t) 与 ρ_s(C) 同时当独立输入等），
     不是主模型；`intervention` 只换那一处闭合/结构/判据。两边同网格/同参数，报 `delta`
     或一致性证据（干物质漂移、守恒残差、t_dry 变化）。**不写 `primary`/`primary_guard`**
     ——contribution 的基线不是主答案，主答案护栏不适用。
2. 在主 agent（单写者）里把实测值写进 **`reports/INNOVATION_MEASUREMENT.json`** 的
   `items[<id>].measurement`（不要改设计台账）：
   ```json
   {"schema_version": 1,
    "items": {"INN-1": {"measurement": {
     "kind": "quantitative",
     "baseline_value": 50.8333,
     "intervention_value": 52.4,
     "delta": 1.5667,
     "delta_unit": "h",
     "relative": 0.0308,
     "source": "results/innovation_checks.json",
     "passed": true,
     "note": "预测 R(t) 最大相对误差 2.1%",
     "primary": {
       "metric": "t_dry",
       "baseline_value": 50.8333,
       "intervention_value": 52.4,
       "relative_change": 0.0308,
       "guard_passed": true,
       "independent_evidence": ""
     }
   }}}}
   ```
   - **`kind=innovation` 必须同时报主答案**（`primary`）：baseline 与 intervention 下同一个
     主答案的值、相对变化、是否在 `primary_guard` 内。不能只报一个对创新有利的次要指标。
   - `delta` 必须等于 `intervention_value - baseline_value`（同一单位）；`primary.relative_change`
     必须等于 `(intervention-baseline)/|baseline|`。检查器会重算，自报一个对不上的数会被打回。
   - 主答案超出护栏时，`guard_passed=false`，并在 `independent_evidence` 写独立证据
     （实验/文献/题面给定值/多模型一致/解析极限）；**没有证据就不要写 `true`**，
     按“创新不成立/模型没闭合”处理：把该项改 `downgraded`，写清原因。
   - **innovation** 的定性结果（如“证明最大值只在中心/表面”）用 `kind="qualitative"` +
     `evidence` + `passed`，不要硬编一个数；`primary` 仍要写能对照的主答案。
   - **contribution 例外**：不写 `primary`；定量写 `baseline_value / intervention_value /
     delta / delta_unit`，定性写 `evidence`（路径 + 数值/一致性结论）；`source` 与 `passed` 必填。
     校验器对 contribution 走独立分支，不会要求主答案护栏。
   - `source` 必须指向真实结果文件；⑤ 会按它复算。
3. 若 test 失败、测不出，或 **`kind=innovation` 的主答案偏离护栏且没有独立证据**：
   - 在 measurement sidecar 里给该项加 `status="downgraded"` 与 `downgrade_reason`；
     不要改设计台账里的 `status`（那是 ② 的字段）；
   - **不许**改 `predicted_delta` / `test` 去迎合结果，也不许把失败项继续叫“创新”；
   - 负结果可以写进 `RESULTS_REPORT.md` 的“与建模报告的一致性说明”，由 ⑨ 放到局限/讨论。
   - innovation 的主答案偏离不是“更精细”，先查能量/边界/口径是否闭合；没有证据就按失败处理。
4. 在 `RESULTS_REPORT.md` 增一张「创新增量核验」表：
   `ID / kind / baseline / intervention / delta / 单位 / 主答案 baseline / 主答案 intervention /
   主答案相对变化 / 护栏 / 贡献证据 / 来源文件 / 是否通过`。
   - `kind=innovation`：主答案列不能空着——它是判断“创新有没有把模型带偏”的第一证据；
     题定结果表与主结论仍以 baseline 为准，intervention 只作为增量对照并列，除非 ③ 已批准
     “主答案变更 + 独立证据”。
   - `kind=contribution`：主答案/护栏列写“—”，填「贡献证据」列（朴素基线 → 本文处理 →
     差值/残差/判据差）；不要为了凑表硬写一个主答案。
5. 收尾自检：
   ```bash
   python lib/web/check_innovation.py --stage code
   ```

并行/多进程时，worker 只写自己的临时结果；`INNOVATION_MEASUREMENT.json` 与
`RESULTS_REPORT.md` 只由主 agent 串行写，避免多个写者把 `measurement` 覆盖掉。

## 数据图交付协议（与 ⑦ 解耦）

数据图先读 `../figure-studio/SKILL.md`。本阶段**只交数据层，不画布**：
每张主图写 FigureBrief，然后用 `studio.save_bundle(...)` 落三件——
`figures/data/<id>.npz`、`figures/spec/<id>.json`、`figures/<id>.lock.json`。
成品 PDF/SVG/PNG、`figures/make_figures.py`、`figures/source_data/*`、`figures/<id>.meta.json`
全部由 `7Route-diagram` 渲染和写。**论文主图**还要写 plate 叙事（title / subtitle / hero claim /
2–3 个 supporting claim），⑦ 按 `../plate-figure/SKILL.md` 生成
`figures/fig_<id>_plate.png/.pdf`；`spec` 小图是支撑面板，不直接替代 plate。
plate 叙事用**模板语言**（`reports/FIGURE_CONTEXT.json` 的 language；CUMCM→中文，
英文模板→英文）：title 是结论句，subtitle 只写数据口径（≤ 约 40 字），
说明性句子写进 FigureBrief 的 caption，**不要**写进图内。每问一张 plate，问数=题目
实际问数（不固定四问）；构图由 ⑦ 按各自的证据链自己设计，不套模板；只要求任意两张
不要是同一骨架换数据。

1. 解析模板语言与画布（CUMCM → 中文、160 mm、微软雅黑）：

   ```powershell
   python skills/figure-studio/scripts/resolve_context.py --write
   ```

2. 每张主图写 `reports/FIGURE_BRIEF.json`（或 `reports/figure_briefs/<id>.json`），
   至少写 claim、数据字段/单位/n、**至少 2 个不同视觉编码的候选 recipe**、区间定义、退路；
   候选要能用 bundle 里已有的字段渲染，不能只在 brief 里写一个数据层没有的图型。
   若选中项是折线族，候选里**必须有一个非折线编码**（`raincloud` /
   `field_raincloud` / `grouped_bars` / `dot_interval`）；同一 bundle + 同一视觉编码
   只出一张图，plate hero 已经画的 3D 曲面不再写同源支撑 spec。校验：

   ```powershell
   python skills/figure-studio/scripts/check_brief.py reports/FIGURE_BRIEF.json --context reports/FIGURE_CONTEXT.json
   ```

3. 把**图要用的数组**原样存进 bundle，不在这里做“为了好看”的裁剪/平滑/抽稀；
   claim 的数字、面板字段、统计口径一次性写进 spec：

   ```python
   import sys
   sys.path.insert(0, "skills/figure-studio/scripts")
   import studio
   ctx = studio.context(".")
   studio.save_bundle(
       ".", "q3_dryfront", {"r": r, "t": t, "C": C}, ctx,
       claim="干前沿由表面推进到中心，表面与中心达标相差约 46 h。",
       sources=["results/q3.json", "code/q3.py"],
       panels=[{"id": "a", "role": "hero", "recipe": "field_contour",
                "fields": ["r", "t", "C"],
                "field_mapping": {"x": "r", "y": "t", "z": "C"},
                "claim": "干前沿随时间向内推进。",
                "options": {"quantity": "moisture", "level": 0.15}}],
       statistics={"interval": {"kind": "none", "method": "不适用"},
                   "test": {"kind": "none", "p_values": False},
                   "unit": "每条曲线是一个确定性模拟时刻", "paired": False},
   )
   ```

   字段名就是 ⑦ 能用的名字；`field_mapping` 必须覆盖 recipe 的 `required_fields`
   （`assets/recipes.json`）。同一张图的所有数组放同一个 bundle，不要跨文件引用。
   **算过的状态量都要进 bundle**：一个问同时解了温度 T 和含水率 C，就同时存
   `T_field`/`C_field`（含对应的 `r`/`t`），哪怕本轮只想画 C。只存 C 会让 ⑦
   永远画不出温度/双场对照，事后为补一个字段回 ④ 重出 bundle + lock 很贵。

4. 交付前跑数据锁与 FigureBrief 两道检查：

   ```powershell
   python skills/figure-studio/scripts/figure_lock.py verify --root .
   python skills/figure-studio/scripts/check_brief.py reports/FIGURE_BRIEF.json --context reports/FIGURE_CONTEXT.json
   ```

   `figure_lock` 应 PASS（旧图迁移期的 `[lock:advisory]` 不算失败）。**不要**在这里跑
   `python -m lib.visualization audit` —— 那是 ⑦ 渲染完之后的检查；④ 交完数据层就结束。

**边界**：FigureBrief 里的 claim/数值/统计口径属于本阶段；⑦ 只能改图面与构图（recipe、
layout、配色、caption 文字），不能改字段映射、统计口径、claim 或 bundle。
如果 recipe 与数据契约不匹配（如没有配对 ID、没有真实区间），在本阶段就降级并写清退路，
不要到 ⑦ 才发现。

## 数学建模规范参考

如需领域判断，读取 `../_references/math_modeling_norms.md` 中的“题型防错速查”“代码实现与结果”“编码阶段常见错误”和“图表与可视化”小节。该文件只作为规范知识库，不新增本阶段的固定产物。

## 阶段边界

- 本阶段负责：代码、实验运行、结果、结果表、数据图的数据包/spec/lock（`figures/data`、
  `figures/spec`、`figures/*.lock.json`）与 FigureBrief，以及
  `reports/INNOVATION_MEASUREMENT.json`（innovation：baseline/intervention 与主答案护栏；
  contribution：delta 或一致性证据）。
- 本阶段**不负责画布**：成品 PDF/SVG/PNG、`figures/make_figures.py`、`figures/source_data/*`、
  `figures/<id>.meta.json` 全部由 `7Route-diagram` 渲染和写。
- 本阶段不负责：技术路线图、算法流程图、系统架构图、概念示意图。这些交给 `7Route-diagram`。
- 本阶段不写论文正文，只为 `9Paper-writing` 提供可信数值和图表资产。

**交付出去的代码要能平铺运行**：提交件里**没有 `code/` 前缀** —— 全部 `.py` 平铺在同一目录。
所以代码之间的 import 必须是同目录裸名（`import core`，不是 `from code import core`），
读数据/写结果的路径要相对当前工作目录解析，不能写死 `code/outputs/…`。
至少提供一个主入口（约定 `run_all.py`），依次跑完「读附件 → 各问求解 → 收支核对 → 导出结果 → 检验」。
分问脚本（`q1.py`…）与辅助脚本保留，由 `9Paper-writing` 收尾写提交清单时决定哪些进提交、哪些只进产物的 `其余文件/`（`14Layout-and-format` 对账）。

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

### 返修编排：诊断可并行，写入只有一个

返修问题多时，**不要**把 `code/`、`results/`、`figures/data|spec` 拆给多个子 agent 同时改 —— 多个写者会互相覆盖，也会让「改 A 坏 B」无法逐条归因。正确分工：

1. 主 agent 先按回执把问题拆成互不重叠的文件/子问题组。只有 **≥2 组确实互不依赖**
   （不同 `q*.py`、不同结果文件、不同图 bundle）时才考虑并行。
2. 并行只用于**只读诊断**：子 agent 读当前代码/结果/日志，可在
   `_tmp/repair_diag/<issue>/` 写探针，返回「证据 + 根因 + 精确 patch（`file:line`，旧→新）
   + 复验命令 + 风险」。子 agent **不得**写 `code/`、`results/`、`figures/`、`reports/`、
   `*.lock.json`，也不得改 `INNOVATION_MEASUREMENT.json`。
3. 主 agent **串行**应用 patch；每应用一条就重跑受影响的子问题及其下游
   （派生指标 → 汇总 → 图表 → result_contract），不要等所有 patch 落完再统一跑。
   涉及共享模块、共享数值或 `run_all.py` 的改动不分给子 agent，直接主 agent 做。
4. 回执要求的复验必须由主 agent 亲自执行，并把**命令输出**写进 `RESULTS_REPORT.md`
   的本轮改动/复验段；子 agent 的「已修好」只能当线索，不能当复验证据
   （与 `receipt_ledger` 的「返修记录不许自证」同一条纪律）。
5. 只有一条问题、或问题都在同一个数值链上时，**不要开子 agent**：直接主 agent 修，
   省下的协调时间比并行多。

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

### Step 4: 交付数据图 bundle / spec / lock

根据 `reports/ANALYSIS_MODELING_REPORT.md` 和 `reports/RESULTS_REPORT.md` 规划图，按
`../figure-studio/SKILL.md` 的 3.1 节把每张主图拆成：

```text
figures/data/<id>.npz       # 图要用的数组，原样
figures/spec/<id>.json      # recipe + fields/field_mapping + claim/stats + layout
figures/<id>.lock.json      # bundle/spec 语义/source/claim 的哈希
```

> **分工**：本阶段负责数据、claim、统计口径、字段映射和数据锁；⑦ 负责画布与构图。
> 数据/口径变更（`sources` 的 npz 变了、claim 语义要改、色标口径要按新判据定）由本阶段
> **重出 bundle + lock**；图画得好不好（图例、遮挡、档界、标注、caption 文字）由 ⑦ 就地改，
> 不再回退本阶段。本阶段交出的数据层不必一次就尽善尽美，但**数值、字段、claim、统计口径
> 必须是对的**。

> **不要写 `figures/make_figures.py`，也不要生成 PDF/PNG。** 渲染脚本归 ⑦；
> 它住在 `figures/` 而不是 `code/`，改配色不会连锁触发 ⑤⑥ 重跑。
> 本阶段若把绘图代码写进 `code/`，或在 `figures/` 里直接画成品，都会破坏这条解耦：
> 前者把“改一行配色”变成“改了数值代码”，后者让 ⑦ 没有可改的渲染层。
> 数据包与 spec 落在 `figures/` 下，但它们**不含像素**，不会触发 ⑤⑥ 的输入指纹。

图型选择仍由本阶段在 spec 里声明（⑦ 可以换图型，但不能换字段/claim）。典型图表：

- 预测类：真实值-预测值对比、误差分布、指标对比。
- 优化类：收敛曲线、成本对比、资源利用率、方案前后对比。
- 评价类：综合得分排序、雷达图、热力图、敏感性曲线。
- 数据理解：分布图、趋势图、相关性图、箱线图。

spec 要求（画布由 ⑦ 执行）：

- 每个面板写清 `fields` / `field_mapping` / `claim`；字段映射必须覆盖 recipe 的
  `required_fields`。中文模板的坐标轴/图例词由 `studio` 的 labels 提供，不在 spec 里
  手写英文解释句。
- 图上不放大标题，标题交给论文 caption（LaTeX 的 `\caption{}`）；spec 里的 `title`
  只作面板短标题。
- 不把流程图/架构图/路线图塞进数据图 spec；那类走 ⑦（`skills/7Route-diagram/references/route-diagram.md`）。
- 宽高按模板：CUMCM 全宽 160 mm、半栏 80 mm；英文 183/88 mm。spec 里写宽度，⑦ 按它排版。

**别把每张图都画成折线**（典型错误：一整批图里绝大多数是 trend/comparison，
热力图/等高线一张没有）。先问"我要画的量在几个维度上有结构"：

| 量的结构 | 该用的图 | 别用什么 |
|---|---|---|
| 场 —— 标量在 (空间 × 时间) 或 (空间 × 空间) 上，且空间结构本身是 claim | 热力图（`charts.heatmap`，逐格读数）或填充等高线（`charts.contour`，有阈值/前沿时它把"哪里是 0.15"画成一条线） | 折线：一条线只能切出一片剖面，场本身的结构看不见 |
| 场 —— 但 claim 是"分布怎么移动/变窄/整体下移" | `field_raincloud`（把每个时刻或每个半径带切成一组，sci-box 半小提琴 + 箱线 + 散点） | 一整墙 `profiles`/`field_waterfall`；也不要只靠一张热力图让读者自己找分布 |
| 多组分布（每组多个观测） | `raincloud` / `distribution_box` | 每组 <3 个观测硬画小提琴；用线把类别连起来 |
| 每个时间窗内两组空间带的分布差 | `field_split_raincloud`（sci-box 05 背靠背半小提琴） | 硬做相关矩阵；确定性场的空间自相关不是独立样本 |
| 沿某个 x 或 t 的切片，且只需比较少数检查点 | `sampled_bars`（按 x 抽样成柱）或 `grouped_bars` | 为了“连续感”画整条折线；抽样点要在图注写清 |
| 沿某个 x 或 t 的切片，且连续变化/斜率/交点是 claim | 折线（`charts.trend`；要画不确定度就传 `low=/high=` 加区间带） | —— 这才是折线的位置 |
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

用三维时在 spec 里声明 `recipe: surface3d`（或 `surface3d-response`）与
`options.view`/`options.level`；渲染由 ⑦ 用 `charts.surface3d()` 执行，并配一张二维
投影/切片（`projection` 面板或另开一栏）。**③ 维没有真实变量含义时不要为了好看选 3D**：
空间结构、响应面、三维轨迹、多变量关系、优化地形才算。视角可读、遮挡交代、投影配图
这三条是 ⑦ 的验收项，④ 只需在 spec 里把“为什么是三维”写进面板 claim。

现成工具：`visualization.geometry.orthographic()`（Nx3 → 二维视平面）与
`sphere_section()`；画法与验收标准见 `docs/GEOMETRY.md`。
`config/visualization.json` 的 `chart_mix.selection` 是**候选制**：每张图至少给 2 个不同视觉编码的候选，由 ⑦ 渲染后按 claim 选择。**折线不是“最后手段”，也不是“全都不要”**：支撑图折线族（`profiles` / `field_waterfall` / `small_multiples`）保留 4–6 个面板；场图/热力图共 2（1 张场图 + 1 张带数字的矩阵热力图），雨云/分布 ≤1，柱/抽样柱 ≤3。连续剖面/历史序列用折线；收敛/离散网格用点图；场分布才用 `field_raincloud`/`raincloud`；只在少数检查点比较才用 `sampled_bars`。空间结构本身是 claim 时才用场图；同一 bundle + 同一视觉编码只出一张图（plate hero 已画的 3D 曲面不再出同源支撑图）。

**渲染细节由 ⑦ 按 `figure-studio` 执行**：图例底色/不压数据、8 色序列、连续量 `quantity=`
色阶、线型不误用、注记不重叠、位图分辨率 —— 都是画布层的事。④ 只需在 spec 里声明
`quantity`/`level`/`series`/`view`，不要把渲染参数硬编码进数据层，也不要为了图好看
在 bundle 里改数值（裁剪、平滑、抽稀都要在图注写清，并交给 ⑦ 在渲染层做）。

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

本阶段不生成成品图。数据来源与字段记录由 `figures/data/<id>.npz` + `figures/spec/<id>.json`
+ `figures/<id>.lock.json` 承担；生成记录（PDF/SVG/PNG、source data、meta）由 ⑦ 在渲染时写。
若本阶段需要临时看一眼数据形状，把诊断图渲染到 `tmp/`，不要写进 `figures/` 的登记路径。


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
