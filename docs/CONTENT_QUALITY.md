# 内容质量：题意、实现、证据与结论

本协议用于维护通用Agent，不预设某个赛题的模型或答案。启用条件为 config/content_quality.json 存在。Web门禁要求裁决JSON版本2；旧报告保留，但不能仅靠旧PASS作为新版合格证据。程序能检查结构、引用与已声明语义，不能自动理解全部题意或证明审查结论真实。

## 阶段责任

| 阶段 | 完成要求 |
|---|---|
| 3analysis | 对照原题与实际附件，生成TASK_CONTRACT.json；识别量词、空间/时间范围、单位、基期与信息到达；说明假设是否改变题面要求 |
| 4review | 独立读原题，复核契约解释和模型公式；不是只批准建模报告的自述 |
| 5coding | 按契约实现；提供能区分错误解释的反例检查，输出结构化结果、求解状态与独立校验 |
| 7audit | 同时复核原题→模型→实现→结果，发现前序模型错误仍须返修analysis；不修改被审对象。**排在 robustness 之前**：结果不可信时不该白跑昂贵的扰动计算 |
| 6Robustness | 分清固定方案重评估和重新优化；区分抽样误差、参数敏感性与求解误差，核对候选支配关系 |
| 9Paper-writing | 结论受证据范围限制；摘要、正文、图注、结论同步；保留每问的关键论证和必要总览图。只写正文各节与摘要 |
| 14Layout-and-format | 独占排版层（paper/_base/ 导言区）：字号字体行距标题图题表题统一、浮体位置与溢出重叠、篇幅预算、正文/附录编号接续、编译与逐页视觉验收。只做定点版式手术；措辞与数值不归它 |
| 10Math-proof-gate | 独立验证推导，并逐项核对前提在实际模型/代码中成立；抽象定理不能认证尚未求优的数值 |
| 10cross | 写作后检查跨问结论、比较基准、指标方向和全文强断言一致性 |
| 15Verification | 原题要求、结论证据、图文计划与成稿逐项闭合；不能以免责声明替代正确性 |
| 12Rubric-final | 四份评委视角评分标（适配性15维/AI痕迹10维/合规红线26条/官方四大项16维）逐项打分，出「严重/中等/轻微」三级判词。**每条先证伪再报**；轻微项只给成本估计、不返修。只审不改 |
| 13Repair-by-rubric-verdict | 按 rubric 判词做论文侧定点返修（措辞/结构/摘要/结论表述）。动手前逐条复核判词属实，不属实的记 `not_reproduced` 不动稿。**模型/数值/实现类判词不回这里**，仍退各自生产阶段 |

## 题意契约

建模阶段写 reports/TASK_CONTRACT.json，随建模报告一起版本更新：

```json
{
  "schema_version": 1,
  "requirements": [{
    "id": "demand_reference",
    "source": {"file": "request/problem.md", "quote": "原题中实际存在的完整条件"},
    "source_semantics": {"quantifier": "each", "scope": "each period", "unit": "items", "time_reference": "fixed_base"},
    "model_semantics": {"quantifier": "each", "scope": "each period", "unit": "items", "time_reference": "fixed_base"},
    "model_anchor": {"file": "reports/ANALYSIS_MODELING_REPORT.md", "quote": "实际模型定义原文"},
    "status": "mapped"
  }]
}
```

按本题替换示例，覆盖所有影响主结果的硬条件及交付要求；不适用的单位/时间基准写not_applicable并在模型中说明。程序要求四个语义字段一致，但评审必须独立检查它们是否忠于引用原文，不能通过两边一起填错来声称通过。变化时更新锚点，不保留已经失效的原文引用。

附加假设与题面要求分开登记。题面“所有子单元满足”不能弱化为“至少一个满足”；“覆盖全部面积”不能用“发生过一次事件”替代；累计面积足够不自动证明空间覆盖。给出同一区域被重复覆盖而其他区域未覆盖的反例，检查模型是否错误放行。只有题面允许、或题面明确调整过的边界，才可作为主模型；其他放宽设定只能是对照，不能替代主解。

文件存在状态以实际附件清单为准，核对模板的表名、行列、单元格与来源；旧problem.md中的“待补”备注不自动等同缺文件。自建模板不得冒充官方模板。发现输入说明矛盾时记录证据，不能编造缺失或来源认证。

## 随机过程与信息结构

每个随机量写出：基期、时间索引、单位、范围、分布来源、变化属于水平还是增量、是否累积、不同年份/对象的依赖性、在做决策前能观测什么。

固定基期波动与相对上期增长分开实现，可复用 result_contract.semantics.trajectory。至少检查两个以上时期：固定基期偏差不应无声地变成连乘，增长过程也不能丢掉累计；确定性趋势与随机扰动分别说明。驱动增量独立不等于状态水平独立；跨期约束也不因期望可加而消失。

编码者为本题添加检查，审查者用原题含义独立构造期望结果。通用函数有测试不代表赛题代码实际使用了正确过程，需查实际调用路径。两条场景生成/评估路径均要核对。

## 最优性与数学论证

每个结果记录termination、gap、界、容差、样本范围、策略范围；论文区分“可行候选”“给定容差内的数值最优”“有解析证明的精确最优”。可复用 optimality_issues 做范围和状态检查；它不替代可行性重算。启发式/时间耗尽不得因值稳定就自动称最优。小gap只有在正确模型下才有意义。

有限样本问题的求解证据不能跨到原随机总体，更不能自动跨到自适应策略空间。命题审核逐条列“前提→模型/代码实际证据→推导有效步骤→结论适用范围”。数值反例、拟合或仿真不能替代证明；也不能假定“形式上像推导”的内核通常正确。

独立证明若用了更强前提，先证明实际问题满足该前提；否则只支持收窄后的命题。跨期耦合和信息可得性逐项检查，不用“期望可加”跳过。与主模型正确性相关的假命题或失效前提返修analysis；独立的文稿命题错误返修write，且不能改称经验结论后继续沿用其后续推论。

## 比较与机制解释

比较表写明共同数据/场景、单位、目标、可行域、样本内外、是否重优化及各方案求解状态。预算相同不代表求解精度相当；固定几个方案跨种子排序稳定不证明模型机制稳健。

用 pareto_dominates 检查在同一评估下的候选双指标。如果某候选期望和尾部表现均更差，不能直接将其解释为“主动牺牲收益换风险”。先说明候选求解不足或不同可行域等可验证原因。风险效应、模型效应、优化误差分别讨论。

当结论差异小而求解误差未受控时，保留“当前候选的观察差异”，机制归因须有受控对照或其他充分证据。不要把不同目标下的gap百分比直接与样本外收益差相减。相关符号也不能单独决定收入或组合风险方向，需依据实际收益函数和数据验证。

图声明的结论必须与所画指标一致。绝对量不能承担相对变化的论证，分面不能独立拉伸色标；被筛选对象、零值和分母明确披露。

## 问题分类与机器裁决

版本2沿用 schema_version、stage、input_digest、status、issues，增加checks。必查ID由Web提示提供，定义如下：

- task_fidelity / quantifiers / stochastic_semantics：原题符合性、量词范围、随机过程及信息结构。
- model_assumptions / implementation_fidelity / feasibility：假设合法性、实际代码匹配模型、解的独立可行性检查。
- optimality / comparison_validity：数值最优性范围、比较与机制解释是否有证据。
- proof_validity / proof_applicability：推导是否成立、前提是否适用于本题。
- narrative_consistency：摘要、正文、图注、结论是否都与证据一致。
- claim_scope：报告里的结论表述是否超出了证据支持的范围 —— 模型、实现、验证都没错，
  只是「话说满了」（如小样本上称「高精度」、best-known 称「全局最优」、区间估计当点估计报）。
  它不在 `RESULT_CHECK_CATEGORY` 反推表里，是 audit 唯一能发 `REVISE_CLAIM` 的通道：
  category 填 `claim` → 交接给后序的写作阶段降级表述，**不触发回退重算**。
- figure_coverage / content_coverage：最终图文与每问必要论证是否齐全（见WRITING_QUALITY）。
- rubric_adaptation / rubric_originality / rubric_evidence / rubric_trace / rubric_redline：
  仅 12Rubric-final 阶段。依次是「模型与问题是否适配（含硬套网红模型）」「创新真伪与效果是否量化」
  「检验在成稿里是否真的写了」「AI 痕迹（词汇/句式/段落长度/图表标题/引用模式）」
  「合规红线（匿名/摘要页与字数/关键词数/AI声明真实性/结构完整）」。
  前两项中只有 `rubric_adaptation` 进 `RESULT_CHECK_CATEGORY` —— 模型层判断不许被填成 `claim`；
  另外三项刻意不反推：两侧都可能（「创新点没写清楚」是 `claim`、便宜；
  「模型确实没有针对性改进」是设计缺口、很贵），程序判不了，交审查者按证据选。

每个check写 id、status（passed/failed/not_applicable）、reason、evidence（非空数组，每项file与quote；须为项目内文本文件的原文）。不适用也给实际依据。issues只列尚未解决项，包含id、severity、evidence、fix、recheck、category、check_ids（关联failed检查）；解决后从issues删除、更新检查证据。

| category | 返修阶段 | 处理 |
|---|---|---|
| task_interpretation / constraint_model / stochastic_model | analysis | 模型问题，强制hard |
| implementation / data_integrity / validation | code | 实现或结果问题，强制hard |
| experiment | robustness | 验证设计或比较证据不足，强制hard |
| proof | write | 文稿推导错误，强制hard；若影响模型本身另列模型类问题 |
| claim | write | 仅当模型、计算及必要验证已正确，剩余强措辞可独立修复 |
| presentation | format | 版式/排版/图文编辑缺陷 —— 定点手术，不该重跑整篇写作 |
| diagram | drawio | 图画错、缺图、图与数据不符（画得对不对归它；排得好不好归 presentation） |
| report_wording | analysis | 报告层措辞/登记/自述/引用/计数 —— 只改报告里的几句话，走 `advisories`。 |
| | | 单开这一类是因为 `claim`→write、`presentation`→format、`diagram`→drawio 都回不到 analysis， |
| | | 于是"建模报告某句措辞不成立"只能去 ⑧ 绕一圈，而 write 不改编报告 ⇒ 那句错话一直在报告里， |
| | | 下一轮门禁重新记一遍。只对 `advisories` 有意义：作为 `issues` 的 category 时照样按 |
| | | `check_ids` 反推成实质类，该拦的一条不会漏。 |

### `tier`：12Rubric-final 独有的三级判词

`12Rubric-final` 的 issue 比别的门禁多一个 `tier` 字段（`fatal` / `must` / `optional`），
因为评分标的产出是分级建议而不是"通过/不通过"：

| tier | 含义 | 去向 |
|---|---|---|
| `fatal` | 致命问题一票否决（摘要严重不合格/完全无创新/排版混乱/全文无检验） | 不可降级 |
| `must` | 严重 + 一般 | 走上面的 category 路由 |
| `optional` | 轻微/可选（「加个对比会更好」这类） | **不进返修**，进 `advisories`，必须附成本估计 |

两条约束：

1. **只有 `claim` / `presentation` / `diagram` 允许标 `optional`**。模型/数据/实现/验证类
   即使标了也一律**升回 `must`** —— 一份「模型不适配本题」不该被一句「影响不大」降级成建议。
   这与 `RESULT_CHECK_CATEGORY` 是同一套反洗白哲学。
2. **`tier` 只对 `rubric` 有效**。别的门禁的裁决里出现 `tier != must` 会被判 `verdict_malformed` ——
   不给"标了 optional 就不拦"这个错觉。

**只剩 `optional` 残留时判 PASS**（`reason: only_optional_remain`）：评分不必全部完美，
严重的和中等的都处理完即可 —— 一条「加个对比会更好」不该把整链卡住。

### rubric 的正向出路

`12Rubric-final` 是唯一有正向目标的门禁：`claim` 类判词（措辞/摘要/结论表述）
交给紧随其后的 `13Repair-by-rubric-verdict` 就地改写，**不回退 write 重跑整篇**（write 是小时级）。
只要判词里混有任何一条模型/数值/实现类，就整单回退到那个最靠前的生产阶段，
`fix` 这轮不跑 —— 否则一份「模型不适配」会被改成一段漂亮话交上去。

`13Repair-by-rubric-verdict` 跑完，`fix` 改了 `paper/`，于是所有"在成稿上做的判断"都失效了。
但驱动不做整轮重判。 它对内容判官不做收尾复验 —— 按 `RECHECK_STAGES`
（`mathproof → cross → rubric → format → verify`）对当前版本重跑一遍、有界只跑一轮这条路不成立
（`server.py` 里「收尾不再对内容判官重判」；`healthcheck` 反过来校验 `server.py`
**不许**定义 `RECHECK_STAGES`）。

现在的口径分三条：

- ⑫ 的复评没丢，但它走的是 ⑫↔⑬ 环路：判词处置完立刻回 ⑫ 复评（`_back_to_judge`，
  它按 `_FIX_HANDOFF_JUDGES = {"rubric", "cross", "verify"}` 决定回哪个判官），
  由 `RUBRIC_FIX_MAX_ROUNDS = 3` 限轮次。
  别写成 `_back_to_rubric` —— 那个函数不存在，只在几条注释里以旧名残留过。
- ⑩⑪ 以及被版式打磨过的内容判官：进 `state["layout_superseded"]` / `state["stale_instr"]`，
  面板上显眼地列出来，需要时手动重跑。理由是"文件字节变了"分不清"改了内容"与"挪了个浮体、
  改了句措辞"，拿它把内容判官拉回来重判等于把打磨当成改内容（每轮多三次门禁复评、
  每次十几分钟，而它们判的东西一个字没变）。
- ⑮验收 排在 ⑭ 之后，对着的一直是定稿版式。

`13Repair-by-rubric-verdict` 没事时会跳过：`12Rubric-final` 明确通过（`PASS`/`APPROVED`/`CLEAN`）且没有未解决项时，
驱动不调起它 —— 没有判词可处置，白跑一次 agent 调用不值当。判据是现读裁决，不是内存标志：
断点续跑时 rubric 靠回执被跳过、`state["fix_required"]` 是空的，用标志判会把该做的返修一起跳掉。
判不出来（异常/UNVERIFIED/裁决缺失）一律**不跳** —— 宁可多跑一次也不要漏掉返修。

### `13Repair-by-rubric-verdict` 的逐条处置对账

`13Repair-by-rubric-verdict` 除 `FIX_REPORT.md` 外必须写 `reports/FIX_REPORT.json`（schema_version 1），
每条 `must`/`fatal` 判词一条记录，`disposition` ∈ `fixed` / `not_reproduced` / `deferred` /
`out_of_scope`，**每条都要带 `evidence`**，`fixed` 还要带 `recheck`。

驱动用 `content_quality.fix_disposition_issues()` 逐条对账，不合规就停机转黄灯。
必需 id 在本阶段就地从 rubric 裁决里取出存进 `state["fix_required"]` ——
不能事后重读：`13Repair-by-rubric-verdict` 一改 `paper/`，rubric 的 `input_digest` 就变了，只会读到 UNVERIFIED。

为什么值得单设一道机械校验：`13Repair-by-rubric-verdict` 的 SKILL 要求「改之前先复核每条判词是不是真的」，
但那是散文。没有这道校验，一份"什么都没做、也没说为什么"的报告，与一份"逐条核过、
两条判词被证伪所以没改"的报告，在驱动眼里完全一样 —— 而后者恰恰是合格产出。

程序按类别选择最早的必要返修阶段，不接受用soft/info把模型问题降级；审核者仍必须正确分类，程序不靠关键词猜测科学含义。audit 发 REVISE_CLAIM 的通道是 `claim_scope`（唯一不在反推表里的必查项）：
只有它的未解决项全部为 claim 时才允许交接；模型类问题即使被填为 REVISE_CLAIM 也转为 NEEDS_FIX。
纯版式问题归 format（category=presentation），图画错归 drawio（category=diagram）；两者都不是 audit 的审计失败项，作为建议投递即可。最终 verify 检查完成情况。

旧Markdown单行PASS、缺少检查项、引用不存在或不匹配，都标记UNVERIFIED，不绕过协议。**每个阶段只跑一次**；失败或超时一律转黄灯（`awaiting_user`）等人工决策 —— 再试一次 / 回退到某阶段 / 接受并披露 / 我已手工修好。**不能以重试次数或免责声明放行。**现有报告不会被维护脚本补签或改判。
