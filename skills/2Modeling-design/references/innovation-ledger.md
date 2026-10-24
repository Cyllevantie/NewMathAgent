# 创新台账：从“方法名”到“可证伪的增量”

> 这份文件是 ② 建模设计的创新判据与四份台账文件的 schema 出处：
> `reports/INNOVATION_LEDGER.json`（design，②）、
> `reports/INNOVATION_MEASUREMENT.json`（measurement，④）、
> `reports/INNOVATION_ROBUSTNESS.json`（robustness，⑥）、
> `reports/INNOVATION_PAPER.json`（paper，⑨）。
> 每份文件只由它的拥有者写；③ 只读 design，⑤ 的复核另写
> `reports/INNOVATION_AUDIT.json`。**下游不得改设计台账** —— 否则 ② 的回执每轮自失效。
> 机械检查：`python lib/web/check_innovation.py --stage design`（后续换 `code/audit/robustness/write`）。

## 1. 为什么需要它

竞赛论文里最常见的“创新点”是：

- “采用了有限体积/PSO/机器学习”；
- “考虑了收缩/端面/变物性”；
- “做了灵敏度分析/网格收敛”；
- “精度更高/误差更小”；
- “把三个模型拼在一起”。

这些大多是**标准方法、验证工作或工程改进**，不是评委能感知的建模创造性。真正能站住的创新要能回答：

1. **基线**是什么，头条数字/决策是什么；
2. 基线在什么条件下会错（**失败模式**）；
3. 改了什么，为什么这个改动能修掉它（**可证伪命题**）；
4. 改完哪个数字变了多少；如果没变，是否诚实降级。

一句话：

> 基线在 X 条件下会给出 Y 错误；我们引入/证明 Z，使 Y 改变 Δ；用 W 对照可以证伪；如果 Δ 不出现，我们放弃。

## 2. 创新分级

| 级别 | 定义 | 竞赛里怎么算 | 例子 |
|---|---|---|---|
| L0 | 正确实现标准方法 | 不算；但必须有 | 有限体积、Brent、PSO |
| L1 | 标准方法适配本题 | 弱；只能叫“关键处理” | 材料坐标处理收缩 |
| L2 | 任务特定的结构观察/判据 | 可算创新，但必须有可测 delta | 单调性 → 一次求根 |
| L3 | 新机制/新状态/新决策链，改变结论 | 强创新；目标 | 收缩作为状态、风险冗余 |
| L4 | 新通用方法 | 罕见；不要求 | — |

判据四因子：

```
创新 = 反常识洞察 × 可证伪机制 × 可测量改变 × 任务相关性
```

- **反常识洞察**：题面/文献没有直接给出，需要推导或对照才能看见；
- **可证伪机制**：能写出“若……则……”，并有一个可能失败的 test；
- **可测量改变**：对头条数字/决策给出方向与量级，或定性翻转；
- **任务相关性**：改变的是题目要回答的东西，不是顺手多算一个指标。

## 3. schema

`reports/INNOVATION_LEDGER.json`：

```json
{
  "schema_version": 1,
  "report": "reports/ANALYSIS_MODELING_REPORT.md",
  "panel": {
    "lenses": ["mechanism", "data", "adversarial", "closure"],
    "candidates": 9,
    "adopted": 1
  },
  "baselines": [
    {
      "id": "BASE-Q4",
      "question": "Q4",
      "model": "材料坐标一维径向有限体积，R(t) 取题给实测",
      "headline": "达标时间 t_dry",
      "unit": "h"
    },
    {
      "id": "BASE-Q4-N",
      "question": "Q4",
      "model": "固定域一维径向有限体积（R 固定，不用材料坐标），作为朴素基线",
      "headline": "达标时间 t_dry",
      "unit": "h"
    },
    {
      "id": "BASE-Q2",
      "question": "Q2",
      "model": "一维径向有限体积 + 题给物性",
      "headline": "72 h 末含水率",
      "unit": "kg/kg"
    },
    {
      "id": "BASE-Q1",
      "question": "Q1",
      "model": "一维径向有限体积 + 题给物性",
      "headline": "1800 s 末含水率",
      "unit": "kg/kg"
    }
  ],
  "items": [
    {
      "id": "INN-1",
      "question": "Q4",
      "lens": "mechanism",
      "type": "mechanism",
      "core": true,
      "baseline_id": "BASE-Q4",
      "failure_mode": "R(t) 只作为输入，收缩与失水的关系没有被检验；若两者不一致，t_dry 的几何解释不成立",
      "intervention": "用干物质守恒和失水量推导 R(t)，与附件实测 R(t) 对照，差异反演孔隙率",
      "claim": "若收缩由失水驱动，则预测 R(t) 与实测 R(t) 的相对误差应在 3% 内；否则该闭合不成立",
      "predicted_delta": "t_dry 相对基线变化 3%–10%，且 R(t) 预测误差可单独报告",
      "test": "同一套物性下跑 baseline（R(t) 取实测）与 intervention（R(t) 由失水预测），比较 t_dry 与 R(t) 误差",
      "kill_if": "预测 R(t) 误差 >10%，或 t_dry 变化 <1% 且无法解释",
      "status": "adopted",
      "primary_guard": {
        "metric": "t_dry",
        "allowed_relative_change": 0.10,
        "why": "题给物性与多数模型给出的量级；超过 10% 必须有独立证据"
      }
    },
    {
      "id": "INN-2",
      "question": "Q2",
      "lens": "adversarial",
      "type": "criterion",
      "core": false,
      "baseline_id": "BASE-Q2",
      "failure_mode": "用平均含水率判达标会掩盖局部未达标",
      "intervention": "改用全场最大值判据",
      "claim": "若存在局部未达标，则平均判据会提前报达标",
      "predicted_delta": "达标时间推迟 5% 以上",
      "test": "同一结果分别按平均值与最大值判据计算 t_dry",
      "kill_if": "两种判据给出相同 t_dry",
      "status": "rejected",
      "reject_reason": "题面已明确要求全场最大值，属于题意硬约束，不作为创新"
    },
    {
      "id": "INN-3",
      "question": "Q1",
      "lens": "data",
      "type": "mechanism",
      "core": false,
      "baseline_id": "BASE-Q1",
      "failure_mode": "表面活度取 Ce=Y 可能高估干燥速率",
      "intervention": "引入 GAB 等温线并做可辨识性检验",
      "claim": "若等温线参数可辨识，则 t_dry 相对基线增加 10% 以上",
      "predicted_delta": "t_dry 增加 10%–25%",
      "test": "用干燥曲线拟合 GAB 参数，比较 baseline 与 intervention",
      "kill_if": "参数置信区间跨越两个数量级（不可辨识）",
      "status": "rejected",
      "reject_reason": "当前附件没有平衡含水率数据，参数不可辨识；留作改进方向"
    }
  ],
  "no_adoption_reason": null
}
```

下游三份 sidecar 的格式（`items` 按 id 合并；只写本阶段字段）：

```json
// reports/INNOVATION_MEASUREMENT.json（④）
{"schema_version": 1,
 "items": {"INN-1": {
   "measurement": {
     "kind": "quantitative",
     "baseline_value": 50.8333, "intervention_value": 52.4,
     "delta": 1.5667, "delta_unit": "h", "relative": 0.0308,
     "source": "results/innovation_checks.json", "passed": true,
     "primary": {"metric": "t_dry", "baseline_value": 50.8333,
                 "intervention_value": 52.4, "relative_change": 0.0308,
                 "guard_passed": true}
   }
 }}}
```

```json
// reports/INNOVATION_ROBUSTNESS.json（⑥）
{"schema_version": 1,
 "items": {"INN-1": {
   "robustness": {
     "survives": true,
     "evidence": "⑥ 对 D0、Ea、h_m 各 ±10% 扰动，t_dry 变化方向一致，R(t) 误差仍 <4%",
     "checks": [
       {"what": "D0 ±10%", "result": "t_dry 变化 4.2%，结论不变"},
       {"what": "h_m ±10%", "result": "t_dry 变化 2.8%，结论不变"}
     ]
   }
 }}}
```

```json
// reports/INNOVATION_PAPER.json（⑨）
{"schema_version": 1,
 "items": {"INN-1": {
   "paper": {"section": "2.5", "claim_id": "C-INN-1",
             "wording": "把收缩从题给输入改为由失水预测的状态，预测半径与实测最大偏差 2.1%，t_dry 相应变化 3.1%"}
 }}}
```

④ 若测失败，在 measurement sidecar 里加 `status: "downgraded"` 与 `downgrade_reason`；
⑥ 若 core 项不稳，在 robustness sidecar 里加 `core: false` / `status: "downgraded"` +
`claim_scope`。**不要把这些写回设计台账。**

⑤ 的复核**不写回任何台账**（它是门禁，改自己的输入会被驱动判成“执行期间输入变更”），
另写 `reports/INNOVATION_AUDIT.json`：

```json
{
  "schema_version": 1,
  "items": {
    "INN-1": {"verdict": "PASS",
              "evidence": "⑤ 复算 results/innovation_checks.json，baseline/intervention 两列与代码输出一致"}
  }
}
```

`evidence` 不能只写一句结论：至少 12 字，并含 `reports/`、`code/`、`results/`、
`figures/`、`paper/` 之一的路径样 token（写 `"x"` 或「两列一致」会被机械检查打回）。

## 3b. 两类正面内容：innovation 与 contribution

台账里的 `adopted` 项分两类，**论文 2.5 不能为空**：

| `kind` | 基线 | 判据 | 论文写在哪 |
|---|---|---|---|
| `innovation`（默认） | **主模型** | 干预的实测 delta + `primary_guard`；不得把主答案带偏 | 2.5「本文主要创新点」，带数字 |
| `contribution` | **朴素/不完整模型**（固定域、体积平均判据、把 R(t) 与 ρ(C) 同时当独立输入等） | 任务特定的闭合/结构/判据；用一致性、必要性或**差值**证明，不要求主答案变化 | 2.5「模型特点与关键处理」，写“朴素基线 → 本文处理 → 证据/差值” |

两类都有时，2.5 标题写「本文主要创新点与模型特点」；innovation 用 `\textbf{创新点X：}`，
contribution 用 `\textbf{关键处理X：}`，两类都逐条计量（每条 3–5 行）。

contribution 的必填字段（在 `DESIGN_FIELDS` 之外）：

```json
{
  "id": "INN-4", "question": "Q4", "lens": "closure", "type": "closure",
  "kind": "contribution", "core": false, "baseline_id": "BASE-Q4-N",
  "failure_mode": "把 R(t) 与 ρ_s(C) 同时当独立输入，干物质审计漂移 −10.98%",
  "intervention": "ρ_s∝R⁻² + 固体连续性；ρ_b(C) 只进热容，热容密度与 ρ_s 一致",
  "claim": "若闭合自洽，则 M_s 在模型闭包下守恒，且 t_dry 变化 ≤0.01%",
  "predicted_delta": "干物质漂移 0；t_dry 51.2257 → 51.2205 h（−0.0052 h）",
  "test": "同 solver 跑 appendix 与 consistent 热密度；复算 M_s 与 t_dry",
  "kill_if": "M_s 漂移仍 >1% 或 t_dry 变化 >1% 且无独立证据",
  "status": "adopted",
  "contribution": "材料坐标下的自洽收缩闭合（密度与固体连续性一致）",
  "baseline_is_naive": "朴素基线把 R(t) 与 ρ_s(C) 同时当独立物理输入，干物质审计 −10.98%",
  "contribution_evidence": "results/q4_checks.json#heat_capacity"
}
```

- **contribution 的 `baseline_id` 必须指向朴素基线卡**：如果它与该问的主基线不同，就在
  `baselines[]` 里单独建一张（如 `BASE-Q4-N`：固定域、体积平均、把 R(t) 与 ρ(C) 同时当
  独立输入等），不要复用主模型基线卡 —— 否则 ④ 会把主模型当 baseline，差值没有意义。
- ④ 在 `INNOVATION_MEASUREMENT.json` 写 `kind / passed / source / evidence`；定量可写
  `baseline_value / intervention_value / delta / delta_unit`，不定性写 `evidence` 路径。
- ⑤ 对 contribution 也逐条回源审计；⑥ 只对 `core=true` 做扰动（contribution `core` 必须 false）。
- ⑨ 的 `INNOVATION_PAPER.json` 里 contribution 也登记 `paper.section`（2.5）与 `claim_id`。
- `check_innovation --stage write` 要求至少 1 条 innovation 或 contribution；只有
  `no_adoption_reason` 会让 2.5 为空，直接打回 ②。

## 4. 主答案护栏（最重要的一条，仅适用于 `kind=innovation`）

**创新默认只能让主答案在护栏内变化；主答案大幅偏离基线，不等于创新，先按模型错误处理。**
`kind=contribution` 的基线是朴素/不完整模型，不是主答案，**不套这一条**；它用一致性、
必要性或差值证明，但仍要 ⑤ 回源审计。

为什么：竞赛阅卷会拿你的主结果和题面、常见模型、其他队伍的量级对照。一个“创新”如果把
主答案带到完全不同的量级，而你没有独立证据证明是基线错了，评委会直接判错，不会因为
“方法高级”给分。你论文里那次温度异常就是典型：

```text
基线（不计潜热/简化边界）：1800 s 中心温度 33.6 ℃、表面 36.8 ℃
创新（加分布式潜热）：      中心 5.4 ℃、表面 12.9 ℃
空气温度：                  41.5 ℃
相对变化：                  -84% / -65%
```

这不是“更精细的模型”，而是**能量闭合没做完**：潜热汇把温度压到远低于空气，却没有
相应的表面活度/相变/边界闭合来解释。正确做法不是把潜热删掉了事，而是：

1. 先把 `primary_guard` 写出来：主答案是什么、允许变化多少、为什么；
2. 跑 baseline 与 intervention，报告 `primary.relative_change`；
3. 如果超出 `allowed_relative_change`，必须有 `independent_evidence`
   （实验数据、文献量级、题面给定值、多模型一致、解析极限）；
4. 没有独立证据 → `guard_passed=false`，该项只能 `downgraded`，写进局限/负结果，
   **不能**放进 2.5 叫“创新”。

推荐的护栏写法：

- 主答案 = 阅卷人最可能对照的那个数（温度、t_dry、成本、分组数），不是只对你有利的指标；
- `allowed_relative_change` 默认 0.10（10%）；题面有明确量级/容差时按题面；
- `why` 写清依据（题给值、文献、多数模型量级、解析解），不能写“我觉得可以”。

## 5. 字段说明

设计台账只放 design 字段；`measurement` / `robustness` / `paper` / `audit` 分别住
`INNOVATION_MEASUREMENT.json` / `INNOVATION_ROBUSTNESS.json` / `INNOVATION_PAPER.json` /
`INNOVATION_AUDIT.json`。本表最后四行标了归属。

| 字段 | 必填 | 说明 |
|---|---|---|
| `panel.lenses` | 是 | 至少 4 个不同视角；`closure` 与 `adversarial` 各至少要有一个（纯优化/决策题可用 `optimization` 顶替其中一项；不能两项都靠同一个 optimization 顶替） |
| `panel.candidates` | 是 | 本轮候选总数，≥3 |
| `baselines[]` | 是 | 每问的主基线卡；contribution 另建朴素基线卡（如 `BASE-Q4-N`）并让 `baseline_id` 指向它 |
| `items[]` | 是 | 全部候选（含 rejected），≥3 条 |
| `id` | 是 | 唯一，如 `INN-1` |
| `question` | 是 | 对应子问题，如 `Q4` |
| `lens` | 是 | `mechanism/data/adversarial/closure/optimization` |
| `type` | 是 | `mechanism/structure/criterion/evidence/closure` |
| `kind` | 否 | `innovation`（默认，主模型增量）或 `contribution`（朴素基线→本文结构，写「模型特点与关键处理」）；contribution 必须有 `contribution / baseline_is_naive / contribution_evidence`，`core` 必须 false |
| `core` | adopted 必填 | 是否核心创新；全篇最多 1 个 |
| `baseline_id` | 是 | 指向 `baselines[].id` |
| `failure_mode` | 是 | 基线在什么条件下会错，写具体 |
| `intervention` | 是 | 加/换/证明什么 |
| `claim` | 是 | 可证伪命题（若……则……） |
| `predicted_delta` | 是 | 对哪个头条数字/决策，方向与量级 |
| `test` | 是 | 什么对照/实验能证伪它 |
| `kill_if` | 是 | 什么结果算失败；失败就降级 |
| `status` | 是 | `adopted/rejected/downgraded` |
| `primary_guard` | `kind=innovation` 必填；contribution 不应有 | `metric/allowed_relative_change/why`：主答案护栏；默认允许 10% |
| `reject_reason` | rejected 必填 | 为什么不用 |
| `downgrade_reason` | downgraded 必填 | 为什么测失败/降级 |
| `measurement` | ④ 所有 adopted 必填；写 `INNOVATION_MEASUREMENT.json` | innovation：`baseline_value/intervention_value/delta/delta_unit/source/passed`；contribution：定量同上，或定性 `evidence`+`source`+`passed`，**不写 primary** |
| `measurement.primary` | ④ `kind=innovation` 必填；contribution 不写 | `metric/baseline_value/intervention_value/relative_change/guard_passed`；超护栏时加 `independent_evidence`；定性主答案用 `kind=qualitative`，值可写文字 |
| `audit` | ⑤ adopted 必填；写 `INNOVATION_AUDIT.json` | `items[id] = {verdict,evidence}`；`evidence` ≥12 字且含 `reports/`、`code/`、`results/`、`figures/`、`paper/` 之一的路径；非 PASS 必须降级 |
| `robustness` | ⑥ core innovation 必填；写进 2.5 的 innovation 也必须 `survives=true`；contribution 不强制；写 `INNOVATION_ROBUSTNESS.json` | `survives/evidence/checks`；`checks` ≥2 项，每项 `what/result` 非空且 `what` 不重复；不稳时写 `claim_scope` 与 `core=false`/`downgraded`，且不能进 2.5 |
| `paper` | ⑨ 所有 adopted（含 contribution）必填；写 `INNOVATION_PAPER.json` | `section/claim_id`；core innovation 必须写 `2.5`；contribution 也写 `2.5` |
| `no_adoption_reason` | 无任何 adopted（innovation/contribution）时必填 | 为什么本题没有值得做的增量；⑨ 仍会因 2.5 为空打回 ② |

## 6. 阶段职责

| 阶段 | 动作 | 检查 |
|---|---|---|
| ② 建模设计 | 写**设计台账**：基线卡、闭合检查、主答案护栏、全部候选、1 core innovation + 至多 1 supporting + 至多 3 contribution | `--stage design` |
| ③ 建模评审 | 审“失败模式是否具体、test 是否能证伪、innovation 的 delta/主答案护栏、contribution 的朴素基线/证据”；只读设计台账；全 rejected + no_adoption_reason 退回补模型贡献 | `--stage design` + 人工判断 |
| ④ 编码计算 | 跑 baseline 与 intervention；innovation 含 `primary`，contribution 写 delta/一致性证据 | `--stage code` |
| ⑤ 结果审计 | 复核测量/主答案/贡献证据是否真实可复现，写 `reports/INNOVATION_AUDIT.json`（evidence 指认产物路径） | `--stage audit` |
| ⑥ 稳健性 | 对 core 做 ≥2 类扰动/重抽样/口径对照，写 `INNOVATION_ROBUSTNESS.json` 的 `what/result` | `--stage robustness` |
| ⑨ 论文撰写 | innovation 按 `adopted+passed+PASS+guard+survives` 写 2.5；contribution 按 `adopted+passed+PASS` 写「模型特点与关键处理」；写 `INNOVATION_PAPER.json` | `--stage write` |

## 7. 反模式

- **只记 adopted**：没有 rejected 候选，说明面板没真跑或没敢淘汰；台账要求 ≥3 条候选。
- **failure_mode 写“精度不够”**：这不是失败模式，是结果；要写清哪个方程/边界/判据/数据口径会错。
- **test 写“做灵敏度分析”**：灵敏度不是证伪；要写“baseline vs intervention 的哪个数字、什么结果算失败”。
- **predicted_delta 写“效果更好”**：没有方向与量级，④ 无法判断是否算通过。
- **测失败还叫创新**：`passed=false` 必须 `downgraded`，可以在“模型评价/局限”里写负结果，不能放在 2.5。
- **主答案偏离大还叫创新（仅 kind=innovation）**：温度 33 ℃ → 5 ℃、空气 41 ℃ 这种，先查
  能量/边界/口径是否闭合；没有独立证据就写进局限，不能放进 2.5。评委先看答案对不对，再看方法新不新。
- **把标准方法包装成 L3**：材料坐标、有限体积、Brent、PSO 本身都是 L0/L1。作为
  `kind=innovation` 仍需新结构 + 实测 delta；作为 `kind=contribution` 必须写成
  “朴素基线 → 本文处理 → 证据/差值”（如固定域 130.5 h → 材料坐标 51.2 h），且不能叫核心创新。
- **core 超过 1 个**：一篇论文最多 1 个核心创新；其余是 supporting/关键处理，否则评委会觉得都在自称创新。
