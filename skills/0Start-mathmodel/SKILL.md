---
name: 0Start-mathmodel
description: "数学建模竞赛工作流入口。用于启动完整建模流程：询问用户偏好，生成 plan.md 和 todo.md，并按阶段调用赛题分析、建模、代码与图表、流程图、论文撰写、验证验收等 skills。"
allowed-tools: PowerShell, Read, Write, Edit, Grep, Glob, Agent, WebSearch, WebFetch
---

# 数学建模工作流

> 通用执行纪律（增量返修 / 缩比预估 / 分段落盘 / 方法标记）见 `../_references/stage_discipline.md`。
> 本阶段四条均不适用：只询问偏好并生成 plan.md / todo.md，不跑计算、不产数值中间件、也不因上游回退而重跑。

本 skill 是数学建模竞赛项目的总控入口。它不替代后续阶段 skill，而是负责启动流程、询问偏好、记录决策、生成计划，并按顺序调用各阶段 skill。

## 数学建模规范参考

如需领域判断，读取 `../_references/math_modeling_norms.md`。该文件只提供数学建模基本规范和防错知识，不改变本 skill 的阶段顺序和产出约定。

## 必须产出

在当前工作目录中创建或更新以下文件：

- `plan.md`：整体流程方案、建模方向、阶段顺序、预期产物和风险控制。
- `todo.md`：具体待办事项列表，记录每个阶段的任务和状态。

## 工作流

### 1. 询问用户偏好 AskUserQuestions

在规划前，只询问会实质影响流程的问题。问题要少而关键。

优先询问（按重要性排序）：

1. 排版引擎：本项目固定使用 LaTeX — 决定 9Paper-writing 使用的模板与编译命令：`xelatex` 编译（需跑两遍解决交叉引用）。
2. 竞赛类型：国赛/华为杯/华中杯/MCM/...— 决定模板选择，见 9Paper-writing 的模板族清单。
3. 论文语言：中文/英文 — MCM/ICM/COMAP 强制英文，其他默认中文。
4. 子问题数量是否已知：影响章节文件生成数量。若未知，由 2Modeling-design 阶段根据题面确定。

将用户的选择记录到 `plan.md` 的"方案"小节中。


### 2. 制定方案

按以下结构编写 `plan.md`：

```markdown
# 方案

要依次调用这些 skill，按照里面要求完成任务。

用户偏好：
- 排版引擎：LaTeX
- 竞赛类型：<国赛 / 华为杯 / MCM / ...>
- 论文语言：<中文 / 英文>
- 子问题数量：<已知 N 个 / 待分析确定>

workflow:
   step      skills
1. 文献定向与机理锚定 - `1Literature-orientation`
2. 赛题分析与建模设计 - `2Modeling-design`
3. 建模评审门禁（数学/题意/机理/数据设计） - `3Modeling-review-gate`
4. 编程实现和图表生成 - `4Coding-and-computation`
5. 数据与结果可信度审计 - `5Result-credibility-audit`      ← 便宜的先跑，结果不可信就不白跑第 6 步
6. 稳健性与敏感性分析 - `6Robustness`
7. 流程与架构图绘制 - `7Route-diagram`
8. 绘图门禁（全部图都在盘上后统一复核） - `8Figure-gate`   ← 最早能对图的全集做检查的位置
9. 竞赛论文撰写 - `9Paper-writing`
10. 数学论证门禁 - `10Math-proof-gate`
11. 跨子问题一致性审查 - `11Cross-question-check`
12. 评分标终审（四份评委视角评分标打分） - `12Rubric-final`
13. 按评分判词定点返修（论文侧） - `13Repair-by-rubric-verdict`  ← 12 的判词处理后回到 12 复评
14. 排版与版式 - `14Layout-and-format`（独占导言区并编译；排在内容判据之后）
15. 验证和验收 - `15Verification`
16. 交互式 Demo（可跳过） - `16Web-demo`
```

> 本工作流在"分析→代码→绘图→写作→验收"主链上加了专门化门禁——文献定向（建模前）、建模评审（进代码前）、可信度审计（出结果后）、数学论证（成稿后）、跨问一致性、终验、评分标终审，共 6 道门禁。
>
> 其中 `12Rubric-final` 是唯一有正向出路的门禁：它的判词分三层（严重/中等/轻微），
> 措辞类交给紧随其后的 `13Repair-by-rubric-verdict` 就地改写，不回退 `9Paper-writing`（那是小时级）；
> 模型/数值/实现类判词仍回退各自的生产阶段。`13Repair-by-rubric-verdict` 改完会自动对新版本重评一次。
> 只有「严重 + 中等」处理完才算过 —— 轻微项只列成本估计，不必改到满分。
>
> 失败策略：每个阶段只跑一次；失败或超时一律转黄灯等人决策（再试一次 / 回退到某阶段 / 接受并披露 / 我已手工修好），不再自动重试、不再自动回退。质量优先，不设强制的总时长。

## 项目目录结构

各阶段按此骨架创建和填充文件：

```text
.
├── plan.md                      # 1: 本文件
├── todo.md                      # 1: 待办事项
├── reports/                     # 各阶段文档报告
│   ├── LITERATURE_DIRECTION.md       # 1: 文献定向与机理锚定（1Literature-orientation）
│   ├── ANALYSIS_MODELING_REPORT.md   # 2: 赛题分析-建模报告（2Modeling-design）
│   ├── MODELING_REVIEW_REPORT.md     # 3: 建模评审门禁报告（3Modeling-review-gate）
│   ├── RESULTS_REPORT.md             # 4: 结果报告（4Coding-and-computation）
│   ├── RESULT_AUDIT_REPORT.md        # 5: 数据与结果可信度审计（5Result-credibility-audit）
│   ├── ROBUSTNESS_REPORT.md          # 6: 稳健性与敏感性（6Robustness）
│   ├── DRAWIO_REPORT.md              # 7: 非数据图说明（7Route-diagram）
│   ├── FORMAT_REPORT.md              # 9: 排版与版式验收（14Layout-and-format）
│   ├── MATH_PROOF_REPORT.md          # 10: 数学论证门禁（10Math-proof-gate）
│   ├── CROSS_QUESTION_REVIEW.md      # 11: 跨问一致性审查（11Cross-question-check）
│   ├── VERIFY_REPORT.md              # 12: 验收报告（15Verification）
│   ├── RUBRIC_REVIEW.md              # 13: 评分标终审报告（12Rubric-final）
│   ├── FIX_REPORT.md                 # 14: 按评分判词返修报告（13Repair-by-rubric-verdict）
│   ├── DEMO_REPORT.md                # 15: 交互式 Demo 说明（16Web-demo）
│   ├── HANDBACK_REQUEST.md           # 任一阶段发现上游有错时写它交回（见各 SKILL）
├── code/                        # 4: 代码（4Coding-and-computation）
│   ├── problem1.py
│   ├── problem2.py
│   ├── problem3.py               # 问题的数量应该更具题目动态调整
│   ├── ... 
│   └── utils.py
├── results/                     # 4: 结果记录（4Coding-and-computation）
├── figures/                     # 4+7: 所有图表（5coding 数据图 + 7Route-diagram 非数据图）
│   ├── manifest.json            #     逐张登记来源/脚本/sha256 + 目检复核（visualization audit）
│   ├── *.pdf                    #     数据图 + 非数据图 PDF
│   ├── *.drawio                 #     非数据图源文件
├── paper/                       # 8-9: 论文（9Paper-writing 写各节；14Layout-and-format 独占导言区与版式）
│   ├── _base/                  #     共享模板层（preamble/macros/math-style）—— 14Layout-and-format 独占
│   ├── main.tex                 #     论文主文件
│   └── sections/                #     各节文件（.tex）
```

方案必须明确每个阶段由哪个下游 skill 负责，以及该阶段应产出什么文件。

### 3. 生成待办

将 `todo.md` 写成阶段性 checklist，格式如下：

```markdown
# 待办事项

- [ ] 0. 总控初始化 - `0Start-mathmodel`
- [ ] 1. 文献定向与机理锚定 - `1Literature-orientation`
- [ ] 2. 赛题分析与建模设计 - `2Modeling-design`
- [ ] 3. 建模评审门禁 - `3Modeling-review-gate`
- [ ] 4. 编程实现和图表生成 - `4Coding-and-computation`
- [ ] 5. 数据与结果可信度审计 - `5Result-credibility-audit`
- [ ] 6. 稳健性与敏感性分析 - `6Robustness`
- [ ] 7. 流程与架构图绘制 - `7Route-diagram`（产出技术路线图等非数据图；matplotlib 兜底）
- [ ] 8. 绘图门禁 - `8Figure-gate`（图全在盘上后统一复核：登记/过期资产/位图质量）
- [ ] 9. 竞赛论文撰写 - `9Paper-writing`
- [ ] 10. 数学论证门禁 - `10Math-proof-gate`
- [ ] 11. 跨子问题一致性审查 - `11Cross-question-check`
- [ ] 12. 评分标终审 - `12Rubric-final`（四份评委视角评分标打分；出严重/中等/轻微三级判词）
- [ ] 13. 按评分判词定点返修 - `13Repair-by-rubric-verdict`（只改论文侧；处理完回到 ⑫ 复评）
- [ ] 14. 排版与版式 - `14Layout-and-format`（行距/页边距/篇幅/编译/逐页视觉）
- [ ] 15. 验证和验收 - `15Verification`
- [ ] 16. 交互式 Demo - `16Web-demo`（题不含"条件/参数→结果"式结论时跳过并说明）
```

每完成一个阶段，都要更新 `todo.md` 中对应任务的状态。

### 4. 依次执行阶段

按以下顺序调用下游 skills：

| 阶段 | Skill | 作用 | 主要产物 |
| --- | --- | --- | --- |
| 文献定向与机理锚定 | `1Literature-orientation` | WebSearch 近 3-5 年文献，给每问"主流建模方向 + 领域机理基线"，供建模与评审作外部参照。 | `LITERATURE_DIRECTION.md` |
| 赛题分析与建模设计 | `2Modeling-design` | 解析题意、识别变量/约束/数据/评价指标，建立数学模型（决策变量/目标函数/约束/求解算法）与代码契约。 | `ANALYSIS_MODELING_REPORT.md` |
| 建模评审门禁 | `3Modeling-review-gate` | 独立评审数学正确性/题意权衡（防退化解）/领域机理/数据设计预检；FAIL 附修改清单退回建模手。 | `MODELING_REVIEW_REPORT.md` |
| 编程实现和图表生成 | `4Coding-and-computation` | 实现可复现代码，运行实验，生成结果表和图表。 | `code/`, `results/`, `RESULTS_REPORT.md`, `figures/图表` |
| 数据与结果可信度审计 | `5Result-credibility-audit` | 专项审计指标乐观性/泄漏/样本单位/小样本/标签口径，防"不严谨结论"。排在稳健性之前：结果不可信时不该白跑昂贵的扰动计算。 | `RESULT_AUDIT_REPORT.md` |
| 稳健性与敏感性分析 | `6Robustness` | 对关键结论做参数扰动/bootstrap/留组/口径对照，标出稳健与敏感项。 | `ROBUSTNESS_REPORT.md` |
| 流程与架构图绘制 | `7Route-diagram` | 绘制技术路线图、各问求解流程图、数据处理流程图等非数据图。 | `figures/*.pdf`、`figures/*.drawio`、`DRAWIO_REPORT.md` |
| 绘图门禁 | `8Figure-gate` | 图全在盘上之后统一复核：登记与过期资产、位图质量（图例压数据/分辨率）、文字压框。只回 7Route-diagram（数据图的问题由它写 HANDBACK_REQUEST 交回 4Coding-and-computation）。 | `FIGURE_REVIEW_REPORT.md` |
| 竞赛论文撰写 | `9Paper-writing` | 基于各报告与图表撰写论文各节并插入图表。只写 `sections/` 与摘要，不碰 `paper/_base/` 导言区。 | `paper/sections/` |
| 数学论证门禁 | `10Math-proof-gate` | 成稿里以定理/命题/证明命名或做强解析声称的对象，须带可逐行复核的等式级推导 + 前提声明；数值/图表不得充当证明。 | `MATH_PROOF_REPORT.md` |
| 跨子问题一致性审查 | `11Cross-question-check` | 核对符号/数据口径/结论自洽/数值协调。 | `CROSS_QUESTION_REVIEW.md` |
| 评分标终审 | `12Rubric-final` | 用四份评委视角评分标（适配性15维/AI痕迹10维/合规红线26条/官方四大项16维）对成稿逐项打分，出「严重/中等/轻微」三级判词与获奖预测。每条判词先证伪再报；轻微项只给成本估计、不返修。只审不改。 | `RUBRIC_REVIEW.md` |
| 按评分判词定点返修 | `13Repair-by-rubric-verdict` | 按判词做论文侧修改（措辞/结构/摘要/结论表述）。动手前逐条复核判词属实，不属实的记 `not_reproduced` 不动稿。模型/数值类判词不在这里改。 | `FIX_REPORT.md` |
| 排版与版式验收 | `14Layout-and-format` | 独占排版层：字号字体行距标题图题表题统一、浮体位置与溢出重叠、篇幅预算、正文/附录编号接续、编译与逐页视觉验收。只做定点版式手术。 | `paper/` 版式、`FORMAT_REPORT.md` |
| 验证和验收 | `15Verification` | 结构/图表/数值/编译/数学论证措辞-内容扫描；只审不改。 | `VERIFY_REPORT.md` |
| 交互式 Demo | `16Web-demo` | 把"条件/参数→结果"式结论做成可交互网页（真实数据、实时重算）。排在最后，不影响论文。 | `demo/`、`DEMO_REPORT.md` |

## 阶段边界与门禁节奏

阶段边界：
- `1Literature-orientation` 只出文献方向与机理基线，不建正式模型、不写代码。
- `3Modeling-review-gate` / `5Result-credibility-audit` / `8Figure-gate` / `10Math-proof-gate` / `11Cross-question-check` / `12Rubric-final` / `15Verification`
  是门禁（共 7 道）：只判 PASS/FAIL 并给修改清单，不亲自动手改模型/跑数/写论文。只审不改 ——
  修改由对应生产阶段按回执执行。职责单一、不越界，避免把多个审查堆进同一上下文（会稀释质量）。
- `12Rubric-final` 是唯一有正向出路的门禁：它的判词分「严重/中等/轻微」三层，
  措辞类交 `13Repair-by-rubric-verdict` 就地改写（不回退 `9Paper-writing`），模型/数值/实现类仍回退生产阶段。
  只要判词里混有任一条模型类，就整单回退、`13Repair-by-rubric-verdict` 这轮不跑 —— 措辞改不掉一个错的模型。
- `4Coding-and-computation` 负责生成所有依赖计算结果或实验输出的数据图。
- `7Route-diagram` 只负责概念图、算法流程图、架构图、路线图等非数据图；不重复绘制数据图。
- `9Paper-writing` 决定每张图放进哪一节并写入插图代码；**用 `_base/macros.tex` 的宏，不要手写环境**：
  `\paperfigure[0.85\textwidth]{fig_q1_error}{问题一预测误差分布}{q1_error}`
  （在 `paper/` 内编译，所以宏内部的相对路径是 `figures/xxx.pdf`）。
- `14Layout-and-format` 独占 `paper/_base/` 与 `main.tex` 导言区。`9Paper-writing` 不碰；正文里**不要手工
  `\vspace` 调间距** —— 「正文所有东西的间距、距离上下行、大小都一样」这条由
  `_base/preamble.tex` 机械保证，手工调一处就破坏一处。
- 不要让 `9Paper-writing` 编造数值结论。论文中的数值必须来自 `RESULTS_REPORT.md`、结果表或已生成图表的数据。

失败与门禁节奏（质量优先，不设强制总时长）：
- 每个阶段只跑一次。 失败或超时一律转黄灯（`awaiting_user`）停下等人，
  不再自动重试、不再自动回退。人在面板上有五个动作：
  `再试一次` / `回退到所选阶段` / `延长本次限时`（仅超时）/ `接受并披露` / `我已手工修好`。
- 超时不杀进程：超过墙钟上限或假死阈值时只是亮黄灯、任务继续跑；等人决定延长（回绿灯）
  或取消重试；若等待期间它自己跑完了，自动回绿灯。
- 默认回退目标（面板上的推荐值，人可改）：`3Modeling-review-gate→3analysis`、`5Result-credibility-audit→5coding`、
  `10Math-proof-gate→9Paper-writing`、`11Cross-question-check→9Paper-writing`、`15Verification→14Layout-and-format`（版式/引用/编译/超页
  是 format 的活，不该重跑整篇写作）、`12Rubric-final→13Repair-by-rubric-verdict`（论文侧判词就地改写；
  但要判词里全是论文侧才走这条 —— 混有模型类就转成对那个生产阶段的回退）。
- 分类路由：缺图/图画错（`diagram`）→ `7Route-diagram`；版式/排版（`presentation`）→ `14Layout-and-format`；
  措辞/结论（`claim`/`proof`）→ `9Paper-writing`；模型类 → `3analysis`；实现/数据类 → `5coding`。
- 发现上游错了（不是本阶段能修的）：按各 SKILL 的「动态交回规则」写 `reports/HANDBACK_REQUEST.md`
  并结束本轮 —— 驱动会把它作为回退建议交给用户，确认后补跑并自动回到本阶段续跑。
- 每完成一阶段更新 `todo.md` 勾选。
