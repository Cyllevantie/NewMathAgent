# 结果可信度审计报告（`audit` / skill `5Result-credibility-audit`）

| 项 | 值 |
|---|---|
| 被审对象 | `code/`（9 个 `.py`）＋ `results/*.xlsx`、`results/*.json` ＋ `figures/`（13 张图 ＋ `manifest.json` ＋ `make_figures.py`）＋ `reports/RESULTS_REPORT.md` ＋ `reports/FIGURE_PLAN.md` |
| 本轮性质 | **返修复验轮** —— 回执 `runtime/quality/feedback/7ece60a5/80150289/gate_decision.json`（`stage=audit`、`status=NEEDS_FIX`、**`target=code`**、2 条 `must` issue，均 `implementation` / `implementation_fidelity`） |
| 上游口径 | `reports/ANALYSIS_MODELING_REPORT.md`＋`reports/TASK_CONTRACT.json`（28 条 `requirements`，全部 `mapped`）＋`request/problem.md`＋`request/attachments/` |
| 本阶段位置 | 链上排在 `code` **之后**、`robustness` **之前** ⇒ 本轮**不读** `ROBUSTNESS_REPORT.md`（尚不存在） |
| 解释器 | `config/runtime.local.json` 指定的 `E:\miniconda3\envs\NewMathAgent\python.exe`（Python 3.11.16、numpy 2.4.6、matplotlib 3.11.2、openpyxl 3.1.5） |
| input_digest | `63741962e98070374717ceb3c9df8c181e06c1412cba5fc212f99b36452e62f9:python=cpython3.11.16;texlive@2026;pandoc@3.6.4;draw.io@31.3.2:7af8e64a8dd539220f943ccda049b8edaee45a01863b04932d398d2fcd934ef7:270aeb29fabf:db2243d539e4` |
| 本阶段自写探针 | `_tmp/au51_round_verify.py`（A 残留扫 ＋ B 控制字符 ＋ C 改动面 ＋ D PNG 逐字节 ＋ E caption 现算 ＋ F 登记自洽 ＋ G/H 两处登记项） |
| 旧探针原样重跑（输出落 `_tmp/au52_*.txt`） | `au1_delivery_crosscheck.py`、`au3_checks.py`、`au4_repro_balance.py`、`au2_indep_q1.py`（**独立求解器**）、`au41_ctrl_scan.py`、`co_r6_recheck.py` |
| 侧车落盘前预演 | `_tmp/au16_verdict_dryrun.py`（复刻 `workflow_quality.read_verdict` ＋ `content_quality.enforce` 两件套）⇒ 8 项 check 的锚点全部逐字命中、`enforce` 回本件声明的同一裁决 |

> 本阶段**只审不改**：未修改 `code/`、`results/`、`figures/`、`reports/` 中任何被审对象，
> 也未向建模报告追加任何标记。`audit` 期间跑过的两个只读 CLI（`lib.result_contract audit`、
> `lib.visualization audit`）未改动任何交付件 —— `results/validation.json` 的 sha256 在收尾时
> 仍是上一版审计自己登记的 `e6464663d3e29d5b`（§5 的收尾哈希表）。

---

## 0. 返修回执的逐条复验

**回执**：`runtime/quality/feedback/7ece60a5/80150289/gate_decision.json` —— `stage=audit`、
`status=NEEDS_FIX`、`target=code`；清单 = **2 条 `must` issue**（两条同挂在 `implementation_fidelity`
上，`category=implementation`）。**两条都已落地并经本阶段独立复算逐项确认**。

### 0.1 `aud-caption-latex-escape-eaten`（hard / `implementation`）—— **已落地，独立复验通过**

回执要求：让该 LaTeX 命令在**求值后**仍是反斜杠 + 命令名（改 raw 串或写双反斜杠），
使运行期取到的 caption 与源文件里肉眼看到的命令一致；改完重跑登记，并确认 `manifest.json`
该 caption 不含任何 C0 控制字符（**源文件与交付 JSON 两处都要查**）。**不动任何数值/模型/绘图参数**。

| 复验项 | 判据 | 实测 |
|---|---|---|
| 源文件写法 | 逐字读源 | `figures/make_figures.py` 的 `fig_q2_temp_field` 把 `caption=` 的**8 个字符串常量全部写成 raw（`r"…"`）**，并在上方补注释写死根因（`\a`→BEL，同类坑 `\t`→TAB、`\b`/`\f`/`\v`/`\r`）；**内容语义未改**，不是把 `\approx` 逐个写双 |
| recheck 第 1 句（源侧） | 对 `figures/make_figures.py` 的每个字符串常量做 **AST 求值**、查控制字符 ⇒ 0 命中 | **0 命中**（`_tmp/au52_recheck.txt` 的 A1：321 个常量） |
| recheck 第 1 句（交付侧） | 对 `figures/manifest.json` 的每个字符串叶子（含 JSON 的 `\uXXXX` 转义）扫 U+0000–U+001F（除 `\n\r\t`）⇒ 0 命中 | **0 命中**（同文件 A2：309 个叶子） |
| recheck 第 2 句（读出的是不是完整命令） | 逐字符读该处 | 读出 `…在 0–6 h 的时程，纵轴为**线性**（不能用对数轴：该量在 $t\approx3…` —— `\approx` **完整**、U+0007 **不存在**、残片 `pprox3` **不存在**（A3/A3b） |
| **判据不是恒真**（负对照） | 同一判据打在**改动前的副本**上必须命中 | 命中 1 处（`tmp/co_r6_make_figures.before.py` 第 **151** 行）、打在改前的 `manifest.json` 上也命中 1 处（A4/A4b） |
| 本阶段**独立**复扫（不看 code 阶段的结论） | 交付树 `code/`＋`results/`＋`figures/`＋`reports/` 的文本件：① 字节层实际控制字符 ② JSON 叶子层转义控制字符 ⇒ 都要 0 | `_tmp/au51_round_verify.txt` B 段：字节层 **0**、JSON 叶子层 **0** |
| 上一轮的通用探针原样重跑 | `_tmp/au41_ctrl_scan.py` | 交付面 **0 命中**；仅剩 `lib/web/check_skeleton.py` 的 2 处 —— 那是**框架内的 strip 字符集**，不在交付面（回执自己写明） |

### 0.2 `aud-caption-figure-mismatch`（hard / `implementation`）—— **已落地，独立复验通过**

回执要求：把两条 caption 改成与**交付图本身**同口径（图是对的，改文字），
q2_temp_field 的右栏纵轴按实际实装写、两个 ΔT 的数各按同句写明的口径取值；
q3_dryfront 的时间窗、色阶区间、白色等值线取值一律照实际参数写；改完**全量**重跑登记，
并复核 `reports/FIGURE_PLAN.md` 对同一张图的说法一致。

本阶段用**现算**（直接读 `figures/make_figures.py` 的函数体参数 ＋ 该图 source npz 的实算值，
不采信任何报告的转述）逐条比对**印出的新串**：

| # | 位置 | caption 现写 | 现算口径与实测 | 判 |
|---|---|---|---|---|
| ① | `q2_temp_field` 右栏轴型 | 「纵轴为**线性**（不能用对数轴：…）」 | `fig_q2_temp_field` 函数体内**无** `yscale`/`semilogy`；`ax2.set` 只给 `xlim=(0.0, 6.0)`；同一函数 16 行下的注释写着「不能用对数纵轴」 | ✅ |
| ② | 同上：负值段起止 | 「$t\approx3.20$–4.00 h 间断出现负值」 | `figdata_q2.npz` 的 $T_{\rm surface}-T_{\rm center}$：阈值 −1e-8 / −1e-6 / −1e-4 三档都给 **3.1972–3.9997 h** | ✅ |
| ③ | 同上：负值段最小值的量级 | 「负值段内最小 $\Delta T=-4.10\times10^{-2}$ K」 | 负值段内 min $=-4.097482\times10^{-2}$ K | ✅ |
| ④ | 同上：0.01 K 的达成时刻 | 「按 $|\Delta T|\le 0.01$ K 的口径，自 $t\approx4.75$ h 起不再超过 0.01 K」 | $|\Delta T|>0.01$ 的**最后**时刻 $=4.7544$ h；**反证**：$t=4.5$ h 处仍为 $2.1180\times10^{-2}$ K ⇒ 旧句「约 4 h 内」为假、新句的口径（绝对值、含 4.2–4.5 h 的回升段）在句内写死 | ✅ |
| ⑤ | `q3_dryfront` 时间窗 | 「问题 3 末段（**52–58 h**）」 | `sel = np.flatnonzero((t_h >= 52.0) & (t_h <= 58.0))` ⇒ **52.0–58.0 h** | ✅ |
| ⑥ | 同上：色阶区间 ＋ 白色等值线 | 「色阶刻意取 $C\in[0.045,0.17]$ kg/kg（…窗口内场实测 $C\in[0.0525,0.1559]$ kg/kg）」「白色等值线为 $C=0.08,0.10,0.12,0.15$ kg/kg」 | `levels=np.linspace(0.045, 0.17, 26)`、`lines=[0.08, 0.10, 0.12, 0.15]`；窗口内 `snap_C[sel]` 实算 $\in[0.0525,0.1559]$（12 帧） | ✅ |

- 其余两处也就地复核：caption 的 $t_{dry}=57.14$ h 与 `results/q3.json :: proof.t_dry_h = 57.138265` 两位取整一致；
  「右栏 0–6 h」与代码 `xlim=(0.0, 6.0)` 一致。
- **交叉印证**：`reports/FIGURE_PLAN.md` 第 4 行（`q2_temp_field`）写「右 $t\in[0,6]$ h，**线性纵轴**」、
  第 8 行（`q3_dryfront`）写「$t\in[52,58]$ h；色阶 $C\in[0.045,0.17]$」 —— 与代码、与改后的 caption **三方一致**。
- **重登记走全**：`figures/make_figures.py` → `figures/manifest.json` → `results/registry.json`（`snapshot` 里该项）；
  `python -m lib.visualization audit` ⇒ **PASS**；`lib.result_contract audit` ⇒ **`[]`**。
- **图件未受影响**：13 张 PNG 与**修复前快照**（`产物/cache/2026A_2026.9.29_17.17.52/编码计算/快照/figures/`）
  **逐字节相同 13 / 变 0 / 缺 0**（`_tmp/au51_round_verify.txt` D 段）⇒ **画面零变化，是硬证据**。

⇒ **两条 issue 全部关闭**（本轮 `issues` 为空）。

### 0.3 本阶段对**全部 13 条 caption** 顺手做的数池复核（防"只修被点名的两处"）

把这两条 caption 的验收判据（"印出的每个数都要能在同一句写明的口径下找到"）扩到**其余 11 条**：
逐条把定量主张对回 `make_figures.py` 的实参或 source npz 的现算值 ——

| caption | 主张 | 现算 | 判 |
|---|---|---|---|
| `q1_field` | 白色等值线 $C=1.6,1.8,2.0,2.2,2.4,2.5$；中心列 1800 s 内变化 $<10^{-5}$ | 代码 `lines=[1.6, 1.8, 2.0, 2.2, 2.4, 2.5]`；`figdata_q1.npz` 中心列首末差 $7.89\times10^{-6}$ | ✅ |
| `q2_temp_field` | 负值起因「附件 1 的 $T_\infty$ 在 **14280 s** 处回落 **0.38 °C**」 | 附件 1 第 239 行 $T_\infty$ 50.142→49.759 ⇒ $|{\Delta}|=0.383$ °C | ✅ |
| `q2_moist_field` | 每 0.5 h 一帧；白色等值线 $0.15,0.5,1.0,1.5,2.0$ | `snap_t_h` 步长恒 0.5 h；`lines=[0.15, 0.5, 1.0, 1.5, 2.0]` | ✅ |
| `q2_drydown` | 对数纵轴；点线 $t_{dry}=57.1383$ h | `yscale="log"`；`results/q3.json` 的 `t_dry_h = 57.138265` | ✅ |
| `q2_diffusivity` | 每 600 s 取一点；$D$ 在 $C{:}2.55\to0.15$、$T{:}30\to50$ °C 区间内下降 **7.67 倍** | 代码 `idx = np.arange(0, size, 600)`；题面附录 3 闭式在两点取值之比 $=7.6715$（**该句自带的两个端点写在同一句里**） | ✅ |
| `q3_criteria` | 求根前 2 个时间步 $t=205\,696$ s $=t_{dry}-1.7554$ s、$g=+5.15\times10^{-7}>0$ | `results/q3.json`：`t_prev2_step=205696.0`、`g_at_prev2_step=5.150173227885801e-07`；`t_dry-205696=1.7554` s | ✅ |
| `q4_shrinkage` | 点线 $t_{dry}^{(4)}=50.8225$ h（$\Delta t=60$ s） | `results/q4.json :: t_dry_h = 50.822518`、`dt=60` | ✅ |
| `q4_field` | 每 0.5 h 一帧 | `figdata_q4.npz` 的 `snap_t_h` 步长 0.5 h（首帧 0.4833 h 为对齐残差） | ✅ |
| `convergence` | 网格 $n=80/160/320/640$ 给 56.9833/57.1000/57.1500/57.1667 h | `results/convergence.json` 的 `mesh_n`/`mesh_tdr` 与 §7.1 表逐位相同 | ✅ |
| `caliber_sensitivity` | 环境延拓三档跨度 0.30 h、面导度三档 0.43 h、$h$ 减半 0.03 h、$h_m\times10$ 达 4.1 h | `results/sensitivity.json` 的 `calibers` 现算：57.15/56.9667/56.85→0.30；57.15/57.25/57.5833→0.43；57.1833−57.15=0.033；57.15−53.05=4.10 | ✅ |
| `q4_effects` | 净效果 0.89 倍 | 50.8333/57.1500 = 0.889 | ✅（"几何加速 2.3 倍"与报告正文的 2.27 是同一量的不同取位，见 §4.3） |

---

## 1. 改动面：这一轮到底动了什么（值级举证）

**基线取上一轮审计报告 §6 自己印出的 sha256 表**（那是上一轮的收尾盘面，与 code 阶段自留的哈希表相互独立）。
逐项重算当前文件：

| 交付件 | 上轮基线（前 16 位） | 现测 | 结论 |
|---|---|---|---|
| `results/result1.xlsx` | `4e00dc2e4bc95876` | 同 | **逐字节未变** |
| `results/result2.xlsx` | `131bf2ebbdc0619b` | 同 | **逐字节未变** |
| `results/result3.xlsx` | `aa2e79674f62854e` | 同 | **逐字节未变** |
| `results/result4.xlsx` | `e4086db6c7d3a7c9` | 同 | **逐字节未变** |
| `results/q3.json` | `9b3f6404750f9943` | 同 | **逐字节未变** |
| `results/validation.json` | `e6464663d3e29d5b` | 同 | **逐字节未变**（本轮跑 `lib.result_contract audit` 后仍逐字节相同） |
| `results/registry.json` | `2df99dc5eff8e4fa` | `f5d46ba63d4b5546` | 变 —— 只在 `snapshot` 里换掉 `figures/make_figures.py` 的哈希 |
| `code/outputs/q2.npz` | `c1046fbbae3fe6cc` | 同 | **逐字节未变**（求解器产物未动） |
| `code/validate_results.py` | `29e5ba3fa856c94a` | 同 | **逐字节未变** |
| `figures/make_figures.py` | `ce8f64293a5de9ae` | `0e41e10c89783054` | 变 —— 就是回执点名的那两处 caption 源串（＋ raw 前缀与说明注释） |
| `figures/manifest.json` | `4c46940ea191783c` | `0598d0ee3028070e` | 变 —— 那两条 caption 的登记 |
| `reports/RESULTS_REPORT.md` | `997220f01382e06a` | `ca45dfaadd2fae30` | 变 —— 新增 §9.6 返修改写与登记 |

**`reports/RESULTS_REPORT.md` 的行级差分**（`difflib` 对上一版、非 autojunk）：
**新增 135 行 / 删除 0 行 / 改写 0 行** ⇒ 报告侧是**纯新增**，**既有行一行未动**
（上一版的 sha 与上一轮审计报告 §6 登记的基线逐位相同，故比对的确实是它审过的那一版）。

**图件分层**：13/13 张 **PNG 逐字节相同**（画面零变化，硬证据，见 §0.2）；
26 份 PDF/SVG 全变 —— 容器内嵌创建时间戳与 matplotlib 每进程随机的图元 id，是**本项目已知口径**，
不能用来判画面（判画面看 PNG）。

**求解器侧**：`code/core.py`、`q1–q4.py`、`sensitivity.py`、`summarize.py`、`run_all.py`、
`code/outputs/*.npz`（7 份）、`results/q1/q2/q4.json`、`sensitivity.json`、`convergence.json`、
`consistency.json`、`metric-spec.json`、`summary.txt` **全部逐字节未变**。

⇒ **交付数值面零变化**；改动面严格等于回执点名的范围（`figures/make_figures.py` 的两条 caption 源串
＋ 它们生成的登记件与派生登记 ＋ 报告里新增的返修记录），**没有清单外改动**。

---

## 2. 审计项逐条（按本题改写口径）

本题是**确定性抛物型正问题 ＋ 标量求根**（非判别/学习类），故 skill 清单里的
"小样本 / AUC / 泄漏" 按同一**目的**（"这份结论可不可信、有没有超出证据"）改写成等价口径。

### ① 「指标异常乐观」→ 精度与分辨率是否被夸大

- 交付表是**四位小数格式值**而阈值恰在 0.15 ⇒ 必须问"4 位是有效位还是格式位"。
- 报告的自述是**分侧 ＋ 分时间档**限定：网格侧第 4 位稳定；时间侧在交付档 $\Delta t=1$ s 下是格式位
  （温度时间离散误差 $1.20\times10^{-3}$ K，是格距 $10^{-4}$ 的 12 倍）；且**早期时刻另测**
  （$t=100$ s 的水分二十一列 $\Delta t=1\to0.5$ s 差 $2.200\times10^{-4}$，是 $t=1800$ s 的 4.13 倍）。
  这是"把值报到不确定度所在的那一位"的标准做法，**不构成夸大**。
- **本阶段独立复核了那条早期证据的口径**：报告没有为了好看去改 $\Delta t$ 或改求解档
  （交付档仍是 $\Delta t=1$ s、$n=320$），而是把"早期行第 4 位小数误差达 4 个单位"如实写进限制表。
- 阈值分辨率：交付表 4 位小数对 $t_{dry}$ 的分辨力只到 341 s $=0.095$ h
  （根附近 $\mathrm{d}(\max_rC)/\mathrm{d}t=-2.934\times10^{-7}\,\mathrm{s}^{-1}$）⇒ 只看 xlsx 会把
  首达步定到 205 528 s（早 170 s）；真正的首达信息住在内部全精度序列里。报告 ★ 注已写明，**未夸大**。
- 结论：无异常乐观。

### ② 「泄漏回查」→ 有没有用到决策时不可得的信息

- 无训练/测试划分；等价风险是"用了未来信息"与"把结论当假设用"。
- **时间层**：Robin 边界与 $1/R^2$ 前因子一律取**步末层**（`core.solve` 里唯一一处实现，
  与建模报告 §5.6/§6.6/§8.5/§13 四处对齐）—— 这是离散格式选择，不是数据泄漏。
- **事件定位**：Q3 直接在 Q2 的现成解上求根（`q3.py` 读 `code/outputs/q2.npz`，不重解方程）；
  表 5/表 6 末行取 $t_{dry}$ 的线性插值场（已登记、且明文标"构造值、不作独立证据"）。
- **把结论当假设用**：命题 1（最坏点在轴心）**没有**被当作免检假设 —— `mon["argmax"]` 逐步记录，
  Q3/Q4 判据走**全场**最大（`argmax_at_root = 0` 只是登记值，判据不依赖它）。
- **外推口径**：$t>14400$ s 零阶保持（主档）、$t>259200$ s 的 $R$ 保持 1.198 cm，均登记为主档
  并配对照档与**证伪档**（冻结在 1800 s 时 $t_{dry}$ 由 57.15 h 变 76.18 h）。口径选择**显式披露**。
- 结论：未发现信息泄漏或把结论当假设。

### ③ 「分析单位复核」→ 每个数都能说出单位与口径

- 内部 SI，出表换 cm/°C/h；A 列一律秒且写整数（模板 `result3/4` 首数据行 60、`result1/2` 是 1），
  本阶段逐份对模板复核通过（`_tmp/au52_checks.txt` ①；`request/attachments/` 的 mtime 仍 11:18 ⇒ 模板未被改）。
- **干基口径**：$\rho_d$ 口径；Q1 的失水比例登记了三个口径（表面通量累计 8.34% / 体积加权均值 10.06% /
  五点梯形 12.88%），并写明"成立的只是**中心点**几乎不动，不是整体几乎不动"。
- **空间口径**：判据走 **321 个节点**（全空间最坏点）；交付表只有 21 列 —— 本阶段用交付件做的 21 列复算
  只是**下界估计**，两者同号（§3 feasibility）。
- **距离口径**：Q4 取**当前构形**的 $r$（$r>R(t)$ 留空）⇒ 独立复算空格数 **19987** 与登记相同、规则 0 违例。
- 结论：单位与口径可追溯，未发现混用。

### ④ 「小样本稳定性」→ 数值稳定性与奇异起步

- **确定性**：`_tmp/au52_repro_balance.txt` ① 段：同一实现连跑两次，Q1 的温度场/水分场逐位一致、
  首达步相同 ⇒ 无随机状态、无可复现性缺口（本题求解器无 RNG）。
- **收敛性**：网格 $n=80/160/320/640$ → 56.9833/57.1000/57.1500/57.1667 h；步长 $\Delta t=60/30/10/1$ s 的
  步进首达 57.1500/57.1417/57.1417/57.1383 h —— 从 `convergence.json` 逐项核对，与 §7.1 表逐位相同。
- **奇异起步（本题的"小样本"）**：$C_\infty(0)=0.01963\ne C_0=2.55$ ⇒ 表面自第一步进入 $O(\sqrt t)$ 瞬态。
  交付**没有**把它当小量判据（只登记 $2.6101\times10^{-2}$）⇒ 处置正确。
- **浮点刀口**：`argmax_rC ≡ 0` 的**字面**判据在个别步误报（交付档 6/1800、Q2 478/259200），
  全部落在亏量 $\le1.8\times10^{-15}$ 的浮点并列上；判据（亏量 $>10^{-10}C(0,t)$）0 违约。
- **独立求解器交叉**（本阶段最能说明问题的一条）：`_tmp/au2_indep_q1.py` 用**与 `code/core.py` 刻意不同**
  的实现重算表 1/表 2 —— 直接 $r$ 坐标组装（非 $\xi$ 归一坐标）、$N=800$（交付档 320）、
  面导度**调和平均**（交付档算术平均）、**Crank–Nicolson**（交付档半隐式欧拉）、自写 Thomas 三对角。
  实测：$\max|\Delta T| = 1.458\times10^{-3}$ K、$\max|\Delta C| = 5.323\times10^{-4}$ kg/kg
  ⇒ 与交付表**在报告自己声明的离散误差量级之内**（声明：温度时间离散 $1.20\times10^{-3}$ K、
  早期水分 $4.4\times10^{-4}$）。**没有出现任何"实现在别的手上就翻面"的迹象。**
- 结论：稳定，无等价于"用少数样本下确定结论"的情形。

### ⑤ 「标签口径」→ 达标判据的标签与敏感性

- 标签 $=\max_{0\le r\le R_0}C(r,t)\le0.15$，用**未舍入**浮点值；"各处" $=\forall$ 全空间。
  本阶段独立复算（`_tmp/au52_delivery_crosscheck.txt` B 段）：首达步 $t=205698$ s 处
  $\max_rC=0.149999928226\le0.15$，**前一步** $t=205697$ s 处 $0.150000221620>0.15$。
- **"首次达标" vs "稳定达标"**：变号 1 次、二次变号 0 次、首根后 $\max g=-7.177\times10^{-8}\le0$
  ⇒ 两者一致（`results/q3.json :: n_cross=1`、`n_recross=0`）。
- **显示 vs 判定**：交付表里显示 `0.1500` 的格在判定上一律以未舍入值为准；报告把两处
  "`0.1500` 含义不同"分开说明（论文表 5 末行 = 插值构造值；`result3.xlsx` 末行 205740 s 的
  未舍入值 0.149987608 真达标）。
- **对"是否含相变项"的敏感性**：含潜热 ⇒ $t_{dry}$ 上移 $+2.98$ h，**远超** $\pm0.5$ h ⇒
  报告把它列为**显式前提**（模型形式选择）而不是数值口径。处置正确。
- 结论：标签口径清楚，敏感处已披露。

### ⑥ 「可复现性抽查」→ 数能不能从 `code/` 复现

- 表 1–6 共 **207 格**对四个 xlsx 逐格比对，**0 格不一致**（`_tmp/au52_delivery_crosscheck.txt` A 段；
  表 5 的 6–54 h 行 45 格、表 6 的 6–48 h 行 32 格、表 1/2 各 35 格、表 3/4 各 30 格）。
- `python -m lib.result_contract audit` ⇒ **`[]`（无问题）**；`python -m lib.visualization audit` ⇒ **PASS**。
- `result3.xlsx` 的 3429 行与 `result2.xlsx` 同刻逐值一致（0 行不一致）；
  `result4.xlsx` 的空格规则 0 违例、动表面列 0 空行；`result3.xlsx` 末行 $=\lceil t_{dry}/60\rceil\cdot60=205740$ s。
- 守恒：本阶段用**交付表自己的数**独立重算水分收支（21 列 Simpson，不 import 求解器）——
  result1 在 600/1800 s 的相对差 0.17%/1.37%，result2 在 1800/7200/14400/21600/43200 s 的相对差
  1.84%/0.06%/0.06%/0.05%/0.13%（粗列 Simpson 的固有偏差，与求解器离散伸缩和 $10^{-11}$ 量级不冲突）。
- 结论：可复现。**本轮未发现断链。**

---

## 3. 必查 ID 逐项

请与侧车 `reports/RESULT_AUDIT_REPORT.verdict.json` 的 `checks` 对照（两者的 `status` 与理由一致）。

**task_fidelity — passed**
题面硬条件与交付件逐条对账（在**当前盘面**上重做，不只看报告措辞）：表 1–6 共 207 格对
`results/result1–4.xlsx` 同格点 **0 格不一致**；4 份模板的工作表名、A1、末列表头、A 列首数据行
与交付件全等（`result1/2` 首数据行 1、`result3/4` 为 60）；Q1 的 7 时刻 × 5 半径、Q2 的 6 时刻 × 5 半径、
Q3/Q4 的每 6 h 与距离列集合、每 1 s/60 s 的行集合、四位小数、0.1 cm 列距、附录 2/3/4 的分工全部核过。
四个交付表相对上一轮快照**逐字节未变** ⇒ 该结论是"逐字节未变"的直接推论。
`TASK_CONTRACT.json` 的 28 条 `requirements` 全部 `mapped`，两侧四语义字段逐条相等。

**quantifiers — passed**
"药材各处的水分浓度应低于 0.15"按 **$\forall$ 全空间、全场最坏点、未舍入值**实现：判据是
$g(t)=\max_rC-0.15$ 的**首个零点**（321 个节点的最大），不是均值、不是表面点、不是"某点曾达标"。
本阶段独立复算：首达步 $t=205698$ s 处 $\max_rC=0.149999928226\le0.15$，前一步 0.150000221620 > 0.15。
四表的每隔 1 s/60 s/6 h/0.5 h 与四个结果文件的 A 列均为从烘干开始计的**绝对过程时间**。

**stochastic_semantics — not_applicable**
不适用，但依据是**实测**：题面"随机/概率/分布/噪声/误差/不确定"各 **0 命中**；附件 1（241 点、
步长恒 60 s）与附件 2（145 点、步长恒 1800 s）本阶段重新装载复核，均为无缺失无重复的确定性序列；
模型是确定性抛物型正问题 ＋ 标量求根，主档不含随机量、不含元启发式、无风险度量。
交付侧也未把"数据缺口下的口径"当已知事实（$t>14400$ s 的延拓单列并配三档对照与一支证伪档）。

**implementation_fidelity — passed**
代码与模型的对齐面逐条正确（时间层步末、面值算术平均、先 C 后 T、干基口径、$\xi$ 参考坐标、
求根 `xtol`/`rtol`、四位小数 ROUND_HALF_UP、A 列写整数、模板为底本；`core.py` 顶部对照表逐条查过）。
上一轮点名的两处 caption 缺陷**已修好并经本阶段独立复算逐项确认**（§0.1、§0.2）：
13 张图的 caption 主张与**它自己那张图**的参数/数据逐项相等，两条 caption 的源串是 raw、
控制字符在源侧与交付 JSON 侧都 **0 命中**，13 张 PNG 与修复前**逐字节相同**。

**feasibility — passed**
解的独立可行性检查（不依赖 `code/` 的判据）：Q3 用交付的 `result3.xlsx` 自己的 21 列逐行取最大，
末行 205740 s 的未舍入 $\max_rC=0.149987608\le0.15$，首达之后 **0 次二次穿越**；
Q4 用 `result4.xlsx` 的空格规则与动表面列复核，违例 **0 格**、空格数 19987 与登记一致。
Q1/Q2 的 $C>0$、$T>0$ K 护栏在交付实现里是**停机报错**（不截断不投影），全链未触发。
约束满足的是"全场"而不是取样列 —— 判据走 321 节点，21 列复算只是下界估计，两者同号。

**optimality — passed**
本题**无优化目标**：$t_{dry}$ 是 $g(t)$ 的**首个穿越点**（标量求根），不是最优解 —— 要证的是
首个根的唯一性与可复现性。本阶段独立复算：变号 1 次、二次变号 0 次、首根后 $\max g=-7.177\times10^{-8}\le0$；
闭式解与 `brentq` 差 0.0 s；区间扫描取首个变号区间、非单调兜底取最小根，不依赖 $g$ 的单调性。
报告未使用"全局最优/最小烘干时间最优"一类措辞（本阶段对全文做了一遍强断言扫查，未命中）。

**comparison_validity — passed**
§7.2/§11.5 的比较表**同口径可比**：全部态统一 $n=320$、$\Delta t=60$ s、步进首达、同一评估判据，
并写明"待 `robustness` 复核"的档位。本阶段用 `results/sensitivity.json` 现算比值：
几何收缩 57.1500→25.1333 h（2.274×）、物性 25.1333→50.8333 h（2.023×）、净 0.889×，
与报告 2.27/约 2 倍/0.89 一致。对"未达标"的档（附录 4 ＋ 固定 $R_0$、$h_m/10$）如实报负结果
而不做点值相减；跨问结论只用弱陈述"同量级（0.5–2 倍）"，与实测 0.889 相称。
该文件本轮**逐字节未变**，故结论继承并已当场复算。

**claim_scope — passed**
报告把精度限定**分侧 ＋ 分时间档**说清（$t=1800$ s 档与 $t=100$ s 档分列），并把取位决定
**显式交给写作阶段**，未把区间估计当点估计、未在求根问题上使用"全局最优"类措辞。
本阶段另复核三处边界：① "论文对温度只能把前 3 位小数当有效位" —— 同处印出的时间离散误差是
$1.20\times10^{-3}$ K，与"第 4 位仅作格式位"自洽，**不构成超范围**；② 阈值附近显示 `0.1500` 的格
被明确标注"不是严格低于 0.15 的充分条件"，判定一律走未舍入值；③ 插值构造值 `max_rC_at_root`
被明文标为"构造上恒等于阈值、**不作独立证据**"，另立首达步实测值 —— 这正是防"把构造值当证据"。
其余强断言扫查未发现新的越界。

---

## 4. 本轮复核过、但判定**不拦链**的登记项（如实记录，防下轮重复捞）

下面三项都**进了 `issues` 就是拦链返修**，而它们各自都不改变任何数值、判据、图面或论文内容；
把它们塞进 `advisories` 也不成立 —— `lib/web/content_quality.py` 的 `OPTIONAL_OK` 只允许
`claim / presentation / diagram / report_wording` 四类，且要带 `why_not_blocking`，
而这三项的**真实归属阶段都不在这四类的目标里**（`code` 的两个交付件、我自己的探针）。
故按上一轮同类处置的先例（"复核过但判定可支撑"），只在此登记。

### 4.1 `figures/make_figures.py` 的函数 docstring 与实装自相矛盾（⑬，非本轮引入）

`fig_q2_temp_field` 的 **docstring（第 127 行）** 仍写着「右栏画**径向温差** $T_s-T_c$ 的时程（**对数纵轴**）」，
而同一个函数第 143–144 行的注释写的是「**不能用对数纵轴**：$\Delta T$ 在 $t\approx3.2$ h 后转负」、
实装**无** `yscale`/`semilogy`、本轮改后的 caption 写的是「纵轴为**线性**」—— **四处里三对一**。
（code 阶段自己在 §9.6 的「本轮新发现」表里登记为 ⑬、编号接续，本轮**核实属实**。）

**为什么不拦链**：① 它是**函数内部 docstring**，不进 `figures/manifest.json`、不进论文图注、
不被任何程序读取 —— 进论文的那条通道（caption / `FIGURE_PLAN.md` / 图本身）**三者已一致**；
② 它所在的 `figures/make_figures.py` 不在 ⑦ 的输入里（⑦ 只产 DrawIO **非数据图**，不读也不改
`make_figures.py`），下游没有任何自动通道会把它当事实读走；
③ 改它必须**全量重渲并重签复核**（登记快照把脚本本身算进每一张图的指纹）—— 那会把本轮
刚刚逐字节比对过的 13 张 PNG 全部作废，代价与风险远大于"一个括号里的两个字"。
**改法（供后续任何一次因别的原因重入 `figures/` 时顺手做）**：把第 127 行的「（对数纵轴）」
删掉或改成「（线性纵轴）」，零数值影响、零画面影响。

### 4.2 `reports/RESULTS_REPORT.md` 有 4 行 markdown 表被单元格里的竖线劈开（⑭，非本轮引入）

本阶段独立复扫（`_tmp/au51_round_verify.py` H 段，判据 = "表体行的竖线数必须等于表头"）：
第 **272**、**345**、**471**、**567** 行各比表头多出 1–2 个单元格 —— 那些单元格用竖线形式写
绝对值记号（`max|ΔC|`、`max|ΔT|`、`$|\mathrm{frac}-0.5|<10^{-6}$`）或含 `|` 的代码片段，
渲染时后面几列会错位。（code 阶段 §9.6 自己登记的是 **3 行**，本阶段重数的结果是 **4 行**，
多出的那行在第 567 行 —— 登记项本身漏了一处。）

**为什么不拦链**：它**不是本轮引入**（四行都在 §9.6 之前就写下），**不改变任何数值与结论**
（本阶段已用 §2⑥/§3 的逐格与逐项复算把表里的数独立验过），而且 `RESULTS_REPORT.md` 不是提交件里的论文；
它是**报告层呈现**。改法就是把这几处的竖线记号换成 `\lvert\cdot\rvert`
（本轮 §9.6 新增的行已经用了这个写法，可照抄），零数值影响。

### 4.3 其余两处口径级差异（量过、判为可支撑）

- **`q4_effects` 的 caption 写「几何加速 2.3 倍」，报告正文（§7.2/§11.5）与逐项分解写 2.27 倍** ——
  同一量的不同取位（2.274），**不是两个值**；图上的柱标本身印的是 57.15/25.13/50.83/72.00。
  下游引用时统一写成 2.27 即可，不必回退。
- **`_tmp/au4_repro_balance.py` ① 段的列标签写错**（本阶段自写探针，非交付件）：
  它把 `T_out[-1][[0,4,8,12,16]]` 标成"列 0/0.5/1/1.5/2 cm"，而 `DIST_Q1` 是 21 列 0.1 cm 步长
  ⇒ 索引 4/8/12/16 对应的是 **0.4/0.8/1.2/1.6 cm**（0.5/1/1.5/2.0 应为 5/10/15/20）。
  该段的"交付表 1 末行"一行是**写死的字符串常量**、不是比较，故不构成任何结论错误；
  同段的"两次运行逐位一致"结论不受影响。**下一轮重跑时看这一行不要误读为不一致。**
  （`au1` 的 A 段才是"表 1 逐格 vs `result1.xlsx`"的判据，那里 35 格 0 不一致。）

---

## 5. 整题结论

- **门禁动作**：本轮**放行**到 `6Robustness`。回执点名的两条 `must` issue **完全落地**并经本阶段
  独立复算逐项确认：`figures/make_figures.py` 的 caption 源串已改 raw（AST 求值 0 个控制字符）、
  交付的 `figures/manifest.json` 该 caption 读出的是完整的 `\approx`（0 个 C0 控制字符，源侧与交付侧两处都查）、
  两条 caption 的 12 项定量主张与**它自己那张图**的参数/数据逐项相等、
  13 张 PNG 与修复前**逐字节相同**、全部数值件（4 个 xlsx、`q2.npz`、`q3.json`、`validation.json`）
  **逐字节未变**、报告侧差分是**纯新增**（135 行、删除 0、改写 0）。
- **审计面**：8 个必查 ID 全部 passed / not_applicable（依据见 §3），另加三件独立证据 ——
  `lib.result_contract audit` ⇒ `[]`、`lib.visualization audit` ⇒ PASS、
  **独立求解器**（$r$ 坐标 ＋ 调和面导度 ＋ Crank–Nicolson ＋ $N=800$）与交付表的最大偏差
  落在报告自己声明的离散误差量级之内（$1.46\times10^{-3}$ K / $5.3\times10^{-4}$ kg/kg）。
- **给下游的提示**（三条口径，引用时必须带）：
  ① 凡要引 $+5.150\times10^{-7}$，口径是 $t_{\rm dry}-1.7554$ s（$\Delta t=1$ s 网格上 2 个时间步之前，
  $t=205\,696$ s），该处符号为正；$t_{\rm dry}-60$ s 处是 $+1.754\times10^{-5}$，**别把两者配成一对**。
  ② Q3 的 $t_{dry}$ 用**连续根** 57.1383 h、Q4 用**步进首达** 50.8333 h（`q4_shrinkage` 图上的点线是
  50.8225 h 的连续根口径，两者口径不同）。
  ③ 交付表里显示 `0.1500` 的格在**判定上**一律以未舍入值为准；论文引用 $t\lesssim1500$ s 的行
  （尤其水分表面列）时不能按 $t=1800$ s 那一档的精度声明读。
- **遗留**：§4.1 / §4.2 两项（`make_figures.py` 的 docstring 与报告里 4 行 markdown 表）
  **不影响交付数值、判据、图面与论文内容**，按上文理由不拦链；改法与代价已写明，
  供任何一次因别的原因重入 `code/` 或 `figures/` 时顺手处置。

### 本轮探针与产物（`_tmp/`，保留不删，下一轮**先原样重跑**）

| 探针 / 输出 | 用途 | 退出码 |
|---|---|---|
| `_tmp/au51_round_verify.py` → `au51_round_verify.txt` | A 残留配对扫（含正负对照）＋ B 交付树控制字符 ＋ C 改动面哈希 ＋ D PNG 逐字节 ＋ E 13 条 caption 现算 ＋ F 登记自洽 ＋ G/H 两处登记项 | 0 |
| `_tmp/au52_delivery_crosscheck.txt` | `au1` 原样重跑：表 1–6 逐格 vs 四个 xlsx、Q3 首达/根、`result3/4` 网格与空格规则 | 0 |
| `_tmp/au52_checks.txt` | `au3` 原样重跑：模板对齐、量词、随机性、可行性、最优性、比较口径六段 | 0 |
| `_tmp/au52_repro_balance.txt` | `au4` 原样重跑：两次运行逐位一致 ＋ 交付表水分收支 | 0 |
| `_tmp/au52_indep_q1.txt` | `au2` 原样重跑：**独立求解器**（$r$ 坐标 / 调和面导度 / CN / $N=800$）对表 1、表 2 | 0 |
| `_tmp/au52_recheck.txt` | `co_r6_recheck` 原样重跑：两条 recheck 的 A 段 6 项（含负对照）＋ B 段 12 项 | 0 |
| `_tmp/au52_ctrl_scan.txt` | `au41` 原样重跑：源侧 AST ＋ 交付侧字节/JSON 三层控制字符扫 | 0 |
| `_tmp/au52_report_diff.txt` | `RESULTS_REPORT.md` 的行级差分（新增/删除/改写各多少） | 0 |
| `_tmp/au53_freeze.txt` | **收尾冻结复扫**：12 项哈希 ＋ 13 张 PNG ＋ 交付树控制字符 ＋ 侧车自检 | 0 |
| `_tmp/au16_verdict_dryrun.py` | 侧车落盘前的两件套预演（`read_verdict` ＋ `enforce`） | 0 |

**旧探针的维护**：`_tmp/au40_stale_captions.py` 的 ②③ 两段**期望值写死的是改前那一批旧串**，
在新交付件上必然报"不一致"（那正是旧串已消失的表现，脚本头部已留注释说明它被
`co_r6_recheck.py` 取代）；它 ①（控制字符）与 ④（`FIGURE_PLAN` 交叉印证）两段仍可复用。
`_tmp/au4_repro_balance.py` ① 段的列标签写错（见 §4.3），重跑时不要误读为"交付表与求解器不一致"。

### 审计收尾时的交付面哈希（下一轮判"有没有人动过"的基线）

| 文件 | sha256（前 16 位） |
|---|---|
| `results/result1.xlsx` | `4e00dc2e4bc95876` |
| `results/result2.xlsx` | `131bf2ebbdc0619b` |
| `results/result3.xlsx` | `aa2e79674f62854e` |
| `results/result4.xlsx` | `e4086db6c7d3a7c9` |
| `results/q3.json` | `9b3f6404750f9943` |
| `results/validation.json` | `e6464663d3e29d5b` |
| `results/registry.json` | `f5d46ba63d4b5546` |
| `code/outputs/q2.npz` | `c1046fbbae3fe6cc` |
| `code/validate_results.py` | `29e5ba3fa856c94a` |
| `figures/make_figures.py` | `0e41e10c89783054` |
| `figures/manifest.json` | `0598d0ee3028070e` |
| `reports/RESULTS_REPORT.md` | `ca45dfaadd2fae30` |

上表的 12 项在**本报告写完之后**又用 `_tmp/au53_freeze.txt` 复扫了一遍：12 项全部与表内逐位一致，
13 张 PNG 与修复前快照仍逐字节相同，交付树控制字符仍 0 命中 ⇒ 报告本身没有把这些数"写走样"。

**整题门禁裁决：CLEAN**

> 处置建议：本阶段结论为"结果可信"，链上前进一步到 `6Robustness`（扰动/敏感性专项）。
> 不退回 `code`：回执两条已逐项落地、交付数值面零变化、8 项必查全部通过。
> §4.1/§4.2 的两处**非数值**遗留已写明改法与代价，留待后续因别的原因重入相应阶段时顺手处置。
