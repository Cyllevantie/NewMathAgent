---
name: 12Rubric-final
description: "评分标终审（成稿之后、13Repair-by-rubric-verdict 之前）。用四份评委视角评分标——模型适配性 15 维、AI 痕迹 10 维、2026 国赛 AI 合规红线 26 条、官方四大评分标准 16 维——对最终成稿逐项打分，产出「严重 / 中等 / 轻微」三级判词与获奖预测。只审不改；每条判词必须先证伪再报；轻微项只给成本估计不返修。"
allowed-tools: PowerShell, Read, Write, Grep, Glob, Agent
---

# 评分标终审

> 通用执行纪律（增量返修 / 缩比预估 / 分段落盘 / 方法标记 / 返修只动清单内）见 `../_references/stage_discipline.md`。
> 本阶段适用：一（增量返修，含 1.1 探针复用）、五（返修只动清单内）、六·6.1（先落骨架再深挖）。
> 探针/量测脚本要复用（通用纪律 一·1.1）：本轮写的取证/量测脚本一律留在 `_tmp/`
> （另有散落的在 `tmp/`，两个都要看）；下一轮开工第一步 = `ls _tmp/ tmp/` → 把上一轮
> 为同一批对象写过的脚本先原样重跑（秒级，确认数在当前版本里还成立）→ 只对本轮新出现或改过
> 的对象写新脚本。别每轮从零重写 —— 全链 776 个自写脚本里 **683 个（88%）只被用过一次**
> 就再也没人碰。复用探针 ≠ 跳过复核：探针只是取证手段，判定仍逐条对着当前版本做。
> 豁免：二（缩比预估）、三（分段落盘）、四（方法标记）—— 本阶段不跑长计算，只读稿与报告。

本阶段位于 11Cross-question-check 之后、13Repair-by-rubric-verdict 之前
（链路：… → 9Paper-writing → 10Math-proof-gate → 11Cross-question-check → 12Rubric-final
→ 13Repair-by-rubric-verdict → 14Layout-and-format → 15Verification → 16Web-demo）。
内容判据排在 ⑭排版（一次 ~2h）之前定稿，所以下表的 ⑭/⑮ 两项
在跑的这一刻还没跑、报告还不存在 —— 见下表的分流说明。
它是整链唯一的评委视角打分关，
也是唯一有正向出路的门禁：判词里属于论文侧的（措辞/摘要/结论表述）交给紧随其后的
`13Repair-by-rubric-verdict` 就地改写，不回退 write 重跑整篇。

## 四份评分标与优先级仲裁

四份评分标全文在 `references/` 下（已按本项目口径改写，不是原样照抄）：

| 文件 | 来源 | 维度 |
|---|---|---|
| `references/rubric_official.md` | 全维度自查与获奖预测 V1.3 | 16 维，官方四大评分标准 15/25/25/35 |
| `references/rubric_adaptation.md` | 模型适配性检查 V2.3 | 15 维，评委视角适配性 |
| `references/rubric_trace.md` | AI 痕迹检测 V5.0 | 10 维，AI 生成痕迹 |
| `references/rubric_redline.md` | 2026 国赛 AI 全自动自查表 | 6 维 26 条合规红线 |

**读它们之前先读 `references/precedence.md`** —— 那里写了优先级仲裁（用户要求 > 仓库
`config/`+`docs/`+模板的现行口径 > 评分标原文）和一份已核实的冲突清单。
冲突一律按前两级执行，并在报告里记一条 `precedence_override`。

## 阶段边界

| 做 | 不做 |
|---|---|
| 逐维度打分，定位问题到具体页/节/句 | 不改论文任何一个字（→ 13Repair-by-rubric-verdict） |
| 每条判词先证伪再报（见下） | 不重跑已有阶段（引用它们的报告结论，不重做） |
| 分级：严重 / 中等 / 轻微，轻微项给成本估计 | 不替代 `15Verification` 的硬错误检查 |
| 出获奖预测与致命问题一票否决 | 不重算任何数值 |

本阶段与其他阶段的分工（防重复报）：下列检查已有归属 ⇒ 不重做。
但「归属」分两种，别一律当成"别人已经查过、我不用管"：

① 归属在已经跑过的前置阶段 ⇒ 只读它的报告结论，不重做：

| 检查项 | 归属 |
|---|---|
| 检验是否真的做了（误差/灵敏度/稳健性） | `6Robustness` 的报告 |
| 图的产出（画错/缺图/与内容不符） | `8Figure-gate` 的 `FIGURE_REVIEW_REPORT.md` |
| 题意契约、模型与实现一致 | `2Modeling-design` 的报告 |

**② 归属在排在 ⑫ 之后的阶段 ⇒ 它们的报告此刻还不存在，不许拿"归它管"当挡箭牌放过去**：
你照样要判，只是判词的目标交给那个下游阶段（`presentation` → ⑭，数值/引用/编译 → ⑮）；
驱动会把这类判词延后投递给对应阶段（见 `lib/web/content_quality.py::_rubric_route`）。

| 检查项 | 它什么时候跑 |
|---|---|
| 页数口径、PDF 大小、A4 | ⑭ `14Layout-and-format`（在你之后；`python -m lib.publication check`） |
| 全局格式统一、图表公式排版、编译、逐页视觉 | ⑭ + ⑮（在你之后） |
| 数值与结果一致、图表引用、参考文献真实性 | ⑮ `15Verification` Step 5/6（在你之后） |
| 检验是否真的做了（误差/灵敏度/稳健性） | `6Robustness` 的报告 |
| 题意契约、模型与实现一致 | `3analysis` / `5Result-credibility-audit` |

本阶段实查的无主面：AI 使用痕迹与 AI 声明真实性、第一人称用词、匿名合规、
摘要字数与关键词数、假设条数、图表标题是否有洞察、引用模式、数据小数位与误差范围、
创新真伪、网红模型、可解释性、多基线对比、推广性、优缺点诚实性、获奖预测、致命问题。

## 执行方式（拆维度，别堆在一个上下文里）

开工第一步：先落骨架（§六·6.1）——写 `RUBRIC_REVIEW_REPORT.md` 与 `.verdict.json`
（`status=UNVERIFIED`、`issues: []`），**不要等打完分再写**。子 agent 极容易吃光整段时间；
产物留到最后写，一旦跑到没气现场就是一片空白 —— 驱动只报「阶段未成功完成：failed」，
读不出任何结论，本阶段那五条必查 ID（adaptation/originality/evidence/trace/redline）
也就一条都拿不到。骨架是占位不是结论，每回来一个维度必须回填、并把该维度的必查 ID 一并写进侧车。

照 `3Modeling-review-gate` 与 `10Math-proof-gate` 的既有做法 —— 审查维度堆在一起会互相稀释。
用 Agent 工具 spawn **3 个独立子 agent**，各写各的结论，本会话只做汇总、分级与写报告：

| 子 agent | 读哪几份 | 判分口径 |
|---|---|---|
| `rubric-model` | `rubric_adaptation` + `rubric_official` 的维度四/五/六/七/八/九/十/十四 | 假设的合理性 15 + 建模的创造性 25 |
| `rubric-wording` | `rubric_trace` + `rubric_official` 的维度一/二/三/十一/十二/十三/十五 | 文字表述的清晰性 35 |
| `rubric-redline` | `rubric_redline`（26 条） | 合规红线：合格 / 存在问题 / 待核实 |

3 个而不是 4 个：适配性与官方 16 维的检查点重合度高，硬拆成两个只会重复读一遍全稿。
结果的正确性 25 分由 `rubric-model` 与 `rubric-wording` 的实证部分共同支撑。

每个子 agent 只输出它那一维的「结论 + 证据（文件:行/页）+ 判词」，禁止越界评其它维度。

**不要自己造重算脚本去验证子 agent 的结论**——那是子 agent 的活，而且它会串行烧掉你在
关键路径上的时间（门禁里只有报告不可替代，你的复算有替代品）。抽查只验子 agent 给出的
具体数字，用几分钟内跑得完的短脚本。

## 先证伪再报（硬性动作，不是建议）

**每一条 `fatal` / `must` 判词在判 failed 之前，必须先走一遍反驳**。至少回答：

1. 论文里是不是已经有了？（换了个名字？写在附录里？在表格里？在图注里？）
2. 是不是在 `ROBUSTNESS_REPORT.md` / `ANALYSIS_MODELING_REPORT.md` 里做了但没写进正文？
3. 是不是评分标的过时口径（对照 `references/precedence.md` 的冲突清单）？

反驳不掉的才算数。**反驳不掉的必须附证据锚点**：`content_quality._evidence()` 的格式
（引用项目内文本文件的原文），不能只写「第 5 节」这种位置描述。

> 反例（真实教训的类型）：判「全文无灵敏度分析」，而附录 B 有一整节 —— 这类误报会让
> `13Repair-by-rubric-verdict` 去改本来正确的地方。**宁可不报，也不要报一条证伪不掉的**。

## 分级与去向

每条判词带 `tier`：

| tier | 判据 | 去向 |
|---|---|---|
| `fatal` | 致命问题一票否决：摘要严重不合格 / 完全无创新 / 排版混乱图表粗糙 / 全文无检验 | 不可降级；报告标红 |
| `must` | 严重 + 一般 | 走 category 路由 → `fix`（论文侧）或生产阶段（模型侧） |
| `optional` | 轻微/可选（「加个对比会更好」这类） | 不进返修；报告里列明，**必须附成本估计** |

**`optional` 项必须写清「要动哪个阶段、大概多久」** —— 判据是「值不值得为它多跑一轮」，
不是「它对不对」。例如「补一组对比实验」→ 估 `code` 要跑多久、要不要重出图、
会不会连锁改摘要与结论。

这段话要落进裁决 JSON 的 `cost` 字段（字符串），驱动会把它显示在黄灯面板的
「轻微建议」一块里。不填的话面板只显示判词本身，用户就没法判断值不值得。

**模型/数据/实现类判词不许标 `optional`**：`content_quality.enforce` 会把它们强制升回
`must`。理由：一份「模型不适配本题」不该被一句「影响不大」降级成建议。

## 打分与获奖预测

按官方四大评分标准（假设 15 / 创造性 25 / 结果 25 / 表述 35）给综合得分，
并给出审慎的获奖预测。**国奖获奖率约 3%、省奖约前 25%，国赛仅设国一与国二** ——
不得轻易写「国一水平」「国二水平」；默认区分「省奖稳拿」与「冲国奖潜力」两层，
并列出冲国奖的核心短板。存在 `fatal` 项时直接判「可能未获奖」。

## 必须产出

1. `reports/RUBRIC_REVIEW.md`：

```markdown
# 评分标终审报告

## 整题结论：PASS / NEEDS_FIX
## 综合得分
（四大项各得几分、总分；与上一版对比若有）
## 获奖预测
（省奖稳拿 / 冲国奖潜力 + 核心短板；有 fatal 项则写「可能未获奖」）
## 致命问题一票否决
（逐条列 fatal；无则写「无」）
## 判词清单
| # | tier | category | 位置(页/节) | 判词 | 证据(原文摘录) | 证伪尝试与结论 | 成本估计(optional 必填) |
## 各维度评价
| 维度 | 结论（合格/存在问题/严重问题） | 理由 | 建议 |
## 已改口径（precedence_override）
（评分标原文与仓库口径冲突、按仓库执行的每一条）
## 未处理项
（为何不在本阶段处理；属 optional 的写成本）
```

2. `reports/RUBRIC_REVIEW.verdict.json`（v2 侧车）。本阶段必查 ID 由驱动注入：
`rubric_adaptation` / `rubric_originality` / `rubric_evidence` / `rubric_trace` / `rubric_redline`。
结构、category 路由与锚点要求见 `docs/CONTENT_QUALITY.md`。
每条 issue 除通用字段外多一个 `tier`（`fatal` / `must` / `optional`），
只对 `claim` / `presentation` / `diagram` 三类认 `optional`，其余类别填了也会被升回 `must`。

报告末尾裁决行与 JSON `status` 必须一致。

## 阶段边界与动态交回

本阶段只审不改。发现的问题**不写 `HANDBACK_REQUEST.md`** —— 它是最后一关，
所有判词都通过裁决侧车路由（论文侧 → `13Repair-by-rubric-verdict`，模型侧 → 各自的生产阶段），
由用户经黄灯面板决定。运行中若发现某个阶段的报告本身不可信（例如 `VERIFY_REPORT.md`
声称 PASS 但盘上明显对不上），照实写进报告并判该判词为 `fatal`，不要在本阶段自行修。
