> **本文件是 2025 年 A 题的历史执行清单，不是当前流程。**
> 阶段顺序、失败策略（当时写的「两轮后挂起」）、门禁回退目标都已过时。
> **当前权威**：`CLAUDE.md` 的「阶段链」表 + `web/server.py` 的 `STAGES`。
> 保留它只为回溯当时的跑法，不要照它执行。

# 2025A 重跑盯跑清单（新 harness）

目的：跑完要能回答两个问题——① 链稳不稳（机械故障少没少）；② **建模与公式质量是否到位**。
所以盯的时候不只盯"跑通没有"，还要在几个关键节点停下来看**内容**。

---

## 0. 开跑前 30 秒自检

```bash
cd "C:/Users/Cyl/Downloads/new math agent"
curl -s http://127.0.0.1:8901/api/workspace      # 应看到 request/problem.md + result1-3.xlsx
python -m unittest discover -s regression        # 应 90 tests OK
```
- 服务器没起 → `python web/server.py --port 8901`，开 `http://127.0.0.1:8901/`。
- **别中途往 `request/`、`data/` 加文件**——会触发"执行期间输入变更→unverified"。

---

## 1. 每阶段盯什么

| 阶段 | 正常表现 | 异常信号 | 处理 |
|---|---|---|---|
| ①literature | WebSearch + Crossref 核验，出 LITERATURE_DIRECTION.md | 长时间无检索动作 | 等；>25min 无 CPU 输出 → 看门狗会杀并重试 |
| ②analysis | 出 ANALYSIS_MODELING_REPORT.md **和 TASK_CONTRACT.json** | **缺 TASK_CONTRACT.json** | 会门禁 NEEDS_FIX→analysis 循环 2 轮后挂起；需人工介入 |
| ③review 门禁 | 可能 REVISE→回 analysis 返修（≤2 轮） | 连续 3 次同一路径 | 会挂起并留 `_KNOWN_WRITING_RESIDUALS.md` |
| ④code | 出 RESULTS_REPORT.md + code/outputs/*.json | 2 分钟 Bash 超时(Exit 143) 反复出现 | 正常噪音，它会改后台跑；连续卡住则人工介入 |
| ⑤drawio | 出 fig_roadmap/fig_flow_q*.pdf | — | — |
| ⑥robustness | 并行扰动求解（多 python 满核） | 求解进程全消失且无新日志 | 看门狗兜底；>20min 静默则人工介入 |
| ⑦audit 门禁 | 可能 NEEDS_FIX→回 code | 反复同一 Fix 项 | 2 轮后挂起，人工介入 |
| ⑧write | 出 paper/main.pdf | — | — |
| ⑨mathproof 门禁 | 可能 REVISE_HARD/SOFT→回 write | HARD 不降级（挂起等人工） | HARD 挂起=正常设计，需人工定夺 |
| ⑩cross / ⑪verify | PASS 或 FAIL→write | — | — |
| ⑫demo | DEMO_REPORT.md | — | 可选 |

**这些是噪音，不用管**：`python -c` 的 SyntaxError（agent 会改写文件重试）、`unrecognized_model` 提示、HiGHS 的 `threads` RuntimeWarning、单次 Bash 10 分钟超时(Exit 143)、DeepSeek 长静默（几分钟无输出但 CPU 在涨）。

---

## 2. 三条速查命令

```bash
# 一行快照（阶段 + 控制台最近活动 + 串题残留 + 产物时间戳）
PYTHONIOENCODING=utf-8 python runtime/periodic_check.py --line

# 原始状态
curl -s http://127.0.0.1:8901/api/state | python -c "import sys,json;d=json.load(sys.stdin);print(d.get('cur'),{k:v for k,v in d['stages'].items() if v!='idle'})"

# 最近日志
tail -20 runtime/web_run.log
```

判"卡死 vs 在算"：`Get-Process python | Select Id,CPU` 看 CPU 是否在涨；涨=在算，不涨且无连接=看门狗会处理。

---

## 3. 质量专项检查点（重点，跑完要逐项看内容）

### 3.1 analysis 阶段（最该停下来看的一步）
打开 `reports/TASK_CONTRACT.json` 与 `request/problem.md` 对照：
- [ ] 每条硬条件都有 requirement，且 `source.quote` **真在题面里**（逐字）
- [ ] `source_semantics` 与 `model_semantics` 是否**忠实**（不是自洽就行）：
  - 量词：题面"每架无人机投放两枚至少间隔 1 s" → 模型是否真按"同机两弹 ≥1s"约束（而不是全局 1s）
  - 范围：题面"5 架无人机，每架至多 3 枚" → 模型是否按"每机≤3"而不是"总共≤3"
  - 时间基准：题面"受领任务 1.5 s 后投放" → 模型的时间零点是否一致
  - 单位：m / m·s⁻¹ / s 是否统一
- [ ] 建模报告是否给了**候选方案对比**（≥2 种建模路线 + 为何选这个），而不是直接给一个
- [ ] 假设节：是否只有"建模约定"（题面给定/物理必然不该进假设节）

**若 3.1 有问题，立刻停下等人工处理** —— 这是最省事的拦截点。

### 3.2 review 阶段
- 报告里是否**逐条对题面**（有引用题面原文），而不是只审建模报告内部自洽
- REVISE 的修改清单是否具体到"哪条公式/哪个约束怎么改"

### 3.3 code 阶段
- `code/outputs/*.json` 的关键数字能否在 RESULTS_REPORT 找到
- 求解器状态是否披露（gap / 是否收敛 / 时间上限）——**未收敛不得称最优**

### 3.4 write 阶段
- 公式是否有**推导**（不是直接给结果式）
- 符号表是否覆盖正文所有符号
- 量纲/边界（极限情形）是否检查
- 数值是否与 code/outputs 一致

**（机器检查：跑 11verity 时会在日志里出现）**：
- `WARN: symbols used in formulas but absent from the symbol table` → 符号表漏项（如漏登记 `\bar p` 这类公式里用到的符号）
- `WARN: near-duplicate large numbers` → 疑似同一数字两处写法不一致（如 65,156,865 与 65,156,867）
- 这两条是 WARN 不是 FAIL；但 11verity 的报告里必须逐条回查并写结论。

### 3.5 mathproof 阶段
- 带"命题/定理/证明"字样的断言，同小节内是否有等式级推导
- 是否把数值/仿真当证明

---

## 4. 停止 / 续跑 / 换题

- **暂停**：页面"⏹ 停止"（会结算计时，产物保留）。
- **续跑**：直接"▶ 开始全链"——已完成的阶段按回执跳过，从断点继续。
- **换题**：把根目录产物移进 `cache/<题>_archive/`，同时清 `runtime/.runclock.json` 与 `runtime/quality/`（否则旧计时/回执带进新题）。
- **从某阶段重跑**：页面"↺ 从所选阶段重跑"（会清该阶段及之后产物，可恢复）。

---

## 5. 收口与取件

链正常收口后，`current output/` 会自动出现：`main.pdf`、`main.docx`、`reports/`、`figures/`、`code/`（含 outputs 的 xlsx/json）、`request/`、`data/`。
对照基线：`cache/A2025_20260906_rerun_archive/`（同题早期产物）。

---

## 6. 出问题时报告的一句话

格式：**「卡在哪个阶段 + 最后一条日志 + 状态面板显示什么」**，例如
> 卡在 code，最后日志是 19:30 的 `Read: c2024_milp.py`，面板显示 code=running 已 40 分钟

这三项就够定位。
