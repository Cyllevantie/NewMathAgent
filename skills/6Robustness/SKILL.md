---
name: 6Robustness
description: "稳健性与敏感性分析（结论要能自证稳健）。对 5coding 跑出的关键结论做：参数扰动、bootstrap/重抽样、样本子集/留组、模型口径对照，量化每个结论对什么敏感、对什么稳健，产出供 9Paper-writing 的灵敏度分析与讨论节使用的 ROBUSTNESS_REPORT.md。"
allowed-tools: PowerShell, Read, Write, Edit, Grep, Glob, Agent, WebSearch, WebFetch
---

# 稳健性与敏感性分析

> 通用执行纪律（增量返修 / 缩比预估 / 分段落盘 / 方法标记 / 返修只动清单内）见 `../_references/stage_discipline.md`。
> 本阶段适用：一（增量返修，含 1.1 探针复用）、五（返修只动清单内）。
> 探针/量测脚本要复用（通用纪律 一·1.1）：本轮写的取证/量测脚本一律留在 `_tmp/`
> （另有散落的在 `tmp/`，两个都要看）；下一轮开工第一步 = `ls _tmp/ tmp/` → 把上一轮
> 为同一批对象写过的脚本先原样重跑（秒级，确认数在当前版本里还成立）→ 只对本轮新出现或改过
> 的对象写新脚本。别每轮从零重写 —— 全链 776 个自写脚本里 **683 个（88%）只被用过一次**
> 就再也没人碰。复用探针 ≠ 跳过复核：探针只是取证手段，判定仍逐条对着当前版本做。

本阶段是完整工作流的第 6 步，位于可信度审计（5Result-credibility-audit）之后、绘图与写作（7Route-diagram/9Paper-writing）之前。它对代码阶段产出的关键结论做系统稳健性检验，回答"这个结论换个参数/抽一批子样/换种口径还成不成立"。

结论要能自证稳健，不能只给一个"最优值"。同时要避开"无差别全量重跑"那条路——本阶段围绕关键结论做定向扰动与重抽样，而非无差别地重跑全部计算。

## 结构化数值与独立校验

本阶段：`python -m lib.result_contract build`（复用已存结果，不默认重跑优化器）；细节见 docs/RESULT_CONTRACT.md。

## 通用绘图协议

新增或修订稳健性图时复用公共样式与模板（规范见 `python -m lib.visualization`）。区间来自实际计算并标明定义；更新来源后重新导出与目检，不能沿用旧图的复核。

## 输入

- `reports/RESULTS_REPORT.md`（5coding 产出，逐子问题的结论、结果文件、图）。
- `reports/RESULT_AUDIT_REPORT.md`（5Result-credibility-audit 产出：哪些结论可信、哪些已标为可疑）。
- `reports/ANALYSIS_MODELING_REPORT.md` 中的关键参数与约束。
- `reports/INNOVATION_LEDGER.json`（② 的设计台账，只读）。
- `reports/INNOVATION_MEASUREMENT.json`（④ 的实测值，只读）。
- `reports/INNOVATION_AUDIT.json`（⑤ 的独立复核结论，只读）。

## 必须产出

在当前工作目录的 `reports/` 下创建 `ROBUSTNESS_REPORT.md`：

- 逐子问题的「稳健性结论表」：关键结论 × 扰动维度 × 结果（保持/改变/仅高敏感参数改变）
- 敏感参数清单（按影响大小排序，注明取值依据与不确定性来源）
- 给 9Paper-writing 的「灵敏度分析」节与「讨论/局限」节的可直接引用素材（数值 + 一句话解读）
- 明确标记：哪些结论强稳健（换口径/扰动均不变）、哪些对某参数敏感（写作时必须披露并解释）
- **`reports/INNOVATION_ROBUSTNESS.json`**：每个 `core=true` 的 adopted 项至少做 2 类
  扰动/重抽样/口径对照，写
  `{"schema_version":1,"items":{"INN-1":{"robustness":{"survives":true/false,"evidence":"...","checks":[{"what":"...","result":"..."}]}}}}`；
  `kind="innovation"` 的 supporting 项写进论文 2.5 仍要有 `survives=true`。
  `kind="contribution"`（关键处理）**不强制** `survives`，但建议在报告里给 1 类口径对照
  （如换网格/换边界读法后干物质漂移或判据差值不变），作为“贡献成立”的旁证。
  不稳时在同一条目里写 `claim_scope`，把结论限定到实际成立的范围内。
  **若 `survives=false`，不能继续保留 `core=true`**：在 sidecar 里写 `core=false`
  （supporting/关键处理）或 `status=downgraded` + `downgrade_reason`；**不要改设计台账**
  （`INNOVATION_LEDGER.json` 是 ② 的字段）。否则 ⑨ 的 write 检查会拒绝它。
  **主答案护栏（只对 kind=innovation；contribution 不适用）**：若该项让主答案偏离基线超过
  `primary_guard.allowed_relative_change`，
  稳健性检验必须包含“这个偏离在扰动下是否仍存在、是否有独立证据支持”；只是“扰动后仍然偏离”
  不构成证据。没有独立证据 → 该项应已在 ④ 被降级；若仍 `adopted`，回 ④ 补降级，不要在本阶段
  用 `survives=false` 替它洗白。

## 稳健性检验维度（按子问题类型选用）

### 优化/决策类子问题（如"分组+时点"）
- 权重/代价敏感性：对目标函数中的权衡权重（如 λ、两类风险权重）做网格扰动（覆盖偏早/偏晚两种偏好），记录最优方案是否改变、如何改变。
- 保障率水平敏感性：若方案含"保障率 q ≥ x%"，对 q 做 85%→99% 扰动，记录时点/分组漂移。
- 断点/阈值敏感性：对离散分组断点 ±扰动（如 ±1 单位），记录结论变化幅度。
- 边界退化检查：若最优解贴边界（如全组同一时点、K=1），重抽样确认这是否稳定，并给"若该边界约束放宽/收紧结论是否翻面"的检验。
- **刀刃解必须并列"留裕度/鲁棒变体"（不能只报告灵敏度）**：若某最优解落在"高瘦脊"上（执行层面窄容差——如速度 ±1 m/s、延时 ±0.05 s、航向 ±0.1–0.5° 即损失 74%~全失），不能只交灵敏度表然后披露。**必须另给一版留裕度鲁棒次优**：做法 = max-min 目标 / 对关键执行参数加裕度约束重优 / 蒙特卡洛 ±σ 执行噪声下仍保 K% 通道的最优，并报其相对名义最优的代价 Δ。若无利可图也明说并披露所需执行精度。
- 现实哨兵（防"纸面极端解"）：逐一审视最优解是否靠题设理想化"钻空子"才成立——例如：纯垂直下沉且无漂移/无扩散时"空沉很久才被视线扫到"、云团收益挤在寿命最后几秒（贴 20 s 边界）、τ 贴人为下界、用满资源只为近乎零边际覆盖、让弹在目标长时间后才生效等。命中此类 → 建议加"驻留/寿命占比/最小有效时长"一类约束重优，或至少移交 9Paper-writing 在局限节明写"该方案依赖题设无漂移/无扩散/寿命窗口的理想化"。

### 判别/分类类子问题
- 重抽样/留组：按数据自然聚类单元（个体/批次/站点等）留组交叉验证，确认性能不是靠个别样本或批次。
- 类别不平衡处理：对照是否用平衡权重/重采样，性能差异多大。
- 随机种子：多种子确认无异常折。
- 特征扰动：对关键特征 ±5%~15% 扰动，AUC/系数是否稳定。

### 统计/机理类子问题
- bootstrap/留一重估：对关键系数/指标给置信区间（B 取 100~500，足够稳定即可）。
- 口径对照：换指标/换窗口/换缺失处理，主结论是否保持。
- 离群剔除：剔除极端样本后结论是否不变。

## 职责边界（与其他 skill 分开，避免上下文过载）

- 本 skill 只做参数扰动 / 重抽样 / 口径对照，量化每个结论对什么敏感。
- "结果可不可信"（指标乐观性、泄漏、样本单位、标签口径）由独立 skill `5Result-credibility-audit` 专门审查，本阶段不重复做，避免两个角色挤在一个上下文里都审不深。
- 运行顺序：5coding 出结果 → 5Result-credibility-audit 做可信度审计（便宜，先筛一遍） → 本 6Robustness 做扰动/稳健性 → 都通过才进绘图/写作。

## 执行方式

1. 读 RESULTS_REPORT 找出每个子问题的关键结论（通常 2-4 条）。
2. 对每条结论，从"稳健性检验维度"里挑 2-4 个最相关的扰动执行。能复用 5coding 的代码函数就复用（读 code/），优先小改小跑，不重写整条流程。
3. 用表格汇总结果。**凡是结论改变或敏感度高的，必须在报告里给出数值与解释**，禁止含糊带过。
4. 计算统一记录 seed 与随机状态，保证可复现。
5. **先读 `reports/RESULT_AUDIT_REPORT.md`**（本阶段排在 5Result-credibility-audit 之后）：它已经判过「这份结果可不可信」，并把可疑点写在其中。按它标记的可疑点重点打，不要把扰动档数平均撒在所有结论上。
   若在本阶段发现新的可信度怀疑（指标异常乐观、疑似泄漏、口径存疑），按文末「动态交回规则」交回 5Result-credibility-audit 或对应阶段 —— **不要再往报告里写"待审计项"一栏等它来看**，它已经跑过了。
6. 对设计台账里每个 `core=true` 的 adopted 项，把 `robustness` 块写进
   **`reports/INNOVATION_ROBUSTNESS.json`**（不要改设计台账），然后跑
   `python lib/web/check_innovation.py --stage robustness`。若 core 项在扰动下不稳（`survives=false`），
   不要硬说稳健：写 `claim_scope` 并在 `ROBUSTNESS_REPORT.md` 明写“该创新只在 X 条件下成立”；
   同时在 sidecar 里把该项 `core=false`（或 `status=downgraded` + 原因），不要保留 `core=true`——
   否则 ⑨ 的 write 检查会拒绝它。

### 场景面板（2–3 个子 agent，按结论/扰动拆）

只在有 **≥2 组独立结论**或 **≥3 类扰动**时开；否则单 agent 顺序跑。
开工先按 `../_references/stage_discipline.md` 八建 `.fma_panel_lock`，收齐后删锁再写正式报告。

- 拆分建议：A 参数扰动（±20%、档位、边界值）、B 重抽样/留一/口径对照、C 极端情景/失效边界；
- 每个子 agent 先读 `reports/RESULT_AUDIT_REPORT.md` 的可疑点，只打自己那组，不要重复审计；
- 子 agent 只在 `_tmp/robust/<lens>/` 写脚本与结果表，**不写 `code/`、`results/`、`figures/data`**；
  计算统一记录 seed、参数档与口径，返回 `数值表 + 结论是否改变 + 敏感度`；
- 主 agent 收齐后统一口径、去重、合并成正式报告；发现新的可信度问题仍按「动态交回规则」处理；
- 子 agent 不可用，或扰动只涉及 1–2 个参数 → 主 agent 顺序跑，不要为并行而拆。

## 阶段边界

- 不建立新模型、不换主方法（那属于 4review 后 3analysis 的修改）。
- 不写论文正文；只产出数值证据与素材。
- 质量优先：若某项稳健性检验成本可控但对结论关键，就做；不受"必须 1 小时"约束。


## 项目运行环境

用 config/runtime.local.json 指定的解释器运行代码与依赖检查；缺包先执行 `runtime/doctor.py`，记录缺少内容，不凭旧环境清单换解释器。

## 动态交回规则（发现前序阶段错了）

若发现结论不稳健的根子在模型设计（判据口径错、主变量选错、约束漏了）—— 本阶段不做建模修改，硬凑扰动档数只会掩盖问题。

创建 `reports/HANDBACK_REQUEST.md`：

```
target: <analysis | code | audit>
reason: <一句话说清：哪里不对、期望改什么>
```

然后停止本阶段并结束本轮（不要继续往下做，更不要编造数值把坑填上）。
编排器会把它作为回退建议交给用户决策（黄灯面板），确认后才补跑；补跑完自动回到本阶段续跑（届时 `HANDBACK_REQUEST.md` 已被清除）。不再自动回退 —— 失败/超时一律转黄灯等人。

> 机制事实：驱动对每一个阶段都调 `check_handback()`，并为「阶段写了 HANDBACK」专门开了
> 非失败通道 —— 所以交回不等于本阶段失败，不会污染回执。已用上它的 7 个阶段：
> 5coding / 6Robustness / 7Route-diagram / 14Layout-and-format / 9Paper-writing / 11Cross-question-check / 15Verification。
