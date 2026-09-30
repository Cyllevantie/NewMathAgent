# 编辑改动记录（`9Paper-writing` / 第 9 阶段）

> 逐条登记本轮对论文正文的删、移、合并与改写：原位置、原因、新位置、正文保留的证据、交叉引用。
> 本阶段只写 `paper/sections/` 与摘要（`paper/main.tex` 的 `\abstractcn`），未碰 `paper/_base/` 与导言区。

## 一、为压到 30 页计页额度而做的迁移

### 1.1 四张支撑性图移入附录 A

| 图 | 原位置 | 新位置 | 原因 | 正文保留的证据与交叉引用 |
|---|---|---|---|---|
| `q1_profiles` | 5.1 结果分析 | 附录 A.3（图 A2） | 表 2/表 3 已给出同一批格点的数值，剖面族是它们的可视化，属支撑性图 | 正文写明「把表 2 与表 3 的七个时刻画成剖面族（附录 A.3）」，5.1 的结论仍由表 2/表 3 与图 4 承担 |
| `convergence` | 6.1 误差分析 | 附录 A.2（图 A1） | 收敛序列已在正文给出数字，图属补充证据 | 正文写明「达标时刻随网格与步长的变化见附录 A.2」，并把两档关键数字（$8.0\times10^{-7}$ K、$6.0\times10^{-4}$ K）留在 6.1 |
| `rb_tornado` | 6.2 灵敏度分析 | 附录 A.4（图 A3） | 单参数档的位移已在正文逐项给数 | 正文写明「逐项结果见附录 A.4」，弹性 $-0.88$ 与 $D\times0.75$ 翻面两条关键结论留在 6.2 |
| `rb_uncertainty` | 6.2 灵敏度分析 | 附录 A.4（图 A4） | 联合分布与阈值代价的结论句已在正文给出 | 正文写明「分布见附录 A.4」，联合标准差 7.0 / 7.5 h、窗外比例 10\% / 1\% 留在 6.2；「抽样区间为自设」的披露随图同时出现 |

### 1.2 两张结果图移入附录 A

| 图 | 原位置 | 新位置 | 原因 | 正文保留的证据与交叉引用 |
|---|---|---|---|---|
| `q2_diffusivity` | 5.2 结果分析 | 附录 A.4（图 A5） | 降速段的机理结论已由文中的 7.67 / 16.84 / 2.20 倍三条数字给出 | 正文改为「降速段的机理见附录 A.4 …」，并保留三条数字与「为什么第一敏感参数是扩散系数」的推理 |
| `q4_effects` | 5.4 结果分析 | 附录 A.4（图 A6） | 效应分解的四档数值已全部写在正文 | 正文保留 57.1500 / 25.1333 / 50.8333 h 与 2.27 / 2.02 / 0.89 三组倍数，并写明第四档是按窗上界绘制的下界 |

### 1.3 两张示意图与一张数据表移入附录

| 项 | 原位置 | 新位置 | 原因 |
|---|---|---|---|
| `fig_q4_material` | 5.4 结果分析 | 附录 A.5（图 A7） | 同一物质点被压向中心的三组数字（1.600 / 1.200 / 0.960 cm）已写在正文，图的几何示意属补充材料；正文仍保有图 2／图 3 两张题意示意图 |
| 守恒校核表（原表 8） | 6.1 误差分析 | 附录 A.2（表 A3） | 残差数量级已写进正文，逐问的四列明细属数据表 |
| `q1_profiles` 等图的图注口径句 | 原在正文句内 | 随图移入附录 | 与图同处，避免正文复述图上自明的内容 |

### 1.4 段落压缩（内容重复处）

| 原位置 | 处置 | 新位置 / 改法 | 保留的证据 |
|---|---|---|---|
| 5.4「坐标变换的等价性」中的两支展开式 | 删（两式合并为一句） | 逐项展开移入附录 A.5；正文保留守恒式、当前构形等价式与「换帧项与对流项逐点相消」这一步 | 守恒式的等价性推导在附录 A.5 完整给出，正文给出结论与前提 |
| 5.3 命题的轴心项阶与扰动细节 | 删（压缩为两句） | 完整推导移入附录 A.1 | 正文保留命题陈述、P1–P3 前提、通量变量方程与「条件命题」的限定 |
| 6.1 守恒校核的逐问明细 | 删（改为一句） | 明细移入附录 A.2 | 正文保留相邻两步容量数组的口径要求与残差量级 |
| 6.2「环境抖动的两档对照」 | 改写（压缩一句） | 正文保留两档的跨度与包络宽度 | 12 个独立实现、极差、中位仍写在正文 |
| 5.3「口径敏感性」段 | 改写（两句） | 与 6.2 的分工不变 | 六条口径档的数值全部保留 |

## 二、按 `RESULT_AUDIT_REPORT.md` 的下游提示落实的表述（写作红线）

审计整题结论为 **CLEAN**（不属 REVISE_CLAIM），但其 §5「给下游的提示（三条口径，引用时必须带）」与
`reports/RESULTS_REPORT.md` §12 的「交付边界与已知限制（必须随结果一起引用）」逐条落到了正文：

| 审计/报告的提示 | 在论文中的落点 |
|---|---|
| ① 凡引 $+5.150\times10^{-7}$，口径是 $t_{\rm dry}-1.7554$ s（$t=205\,696$ s，$\Delta t=1$ s 网格上 2 个时间步之前），**不得与 $t_{\rm dry}-60$ s 处的值配成对** | 5.3 模型求解的判据自证段：两个时间步的值分别写全时刻（$t=205\,697$ s、$t=205\,696$ s）与各自到达标时刻的差（0.7554 s、1.7554 s），全文未出现「达标时刻前一分钟」那一格的数值 |
| ② 问题三的 $t_{\rm dry}$ 用**连续根** 57.1383 h；问题四用**步进首达** 50.8333 h；`q4_shrinkage` 图上的点线是 50.8225 h 的连续根口径，两者口径不同 | 5.3 与 5.4 分别在式 (16) 与式 (17) 的框内写明两个口径；5.4 正文另补「同一实现的连续根为 50.8225 h，两者相差一个步长」，摘要同样两个数并列 |
| ③ 显示为 `0.1500` 的格在判定上一律以未舍入值为准；引用 $t\lesssim1500$ s 的行不能按 $t=1800$ s 那一档的精度声明读 | 5.3 表 6 的表注句、5.3 模型求解段与 6.1 的三处同时写；早期档的实测（$2.20\times10^{-4}$ 与 4.13 倍）写进 6.1，并在摘要里以「网格与口径的合计不确定度约 ±0.5 h」概括 |
| 精度按侧、按时间分档（网格侧第 4 位稳定，时间侧在 $\Delta t=1$ s 下为格式位，温度只宜前 3 位有效） | 5.1 模型求解段与 6.1 误差分析：前者给出两条收敛数字并点明「时间侧第四位只是格式位」，后者给出 6.1 的完整分档声明与「凡涉及有效数字的讨论或逐位比较都以三位为准」的取位规则；表内仍按题面要求保留四位小数的格式承诺 |
| $t_{\rm dry}$ 的绝对不确定度 ≈ ±0.5 h，**给区间不给伪精确点值** | 摘要、5.3 结果分析、6.2、7.2（缺点四）四处 |
| **能量方程不含相变项是模型形式选择**，必须作为显式前提披露；按 $\rho_d$ 口径潜热流是对流供热的 5.6–6.7 倍，计入潜热 $t_{\rm dry}$ 上移 2.98 h | 第三节假设二、5.1 结果分析末段、6.2「相变前提的披露」、7.2 缺点一；量级 5.6–6.7 倍与 +2.98 h 同句给出，**未**写成「潜热是小项」 |
| 附件 1 的 $T_\infty$ 有回落步，**不得无条件引用「$T$ 关于 $r$ 单调」** | 5.2 结果分析：写明 $t\approx14280$ s 的 0.383 $^\circ$C 回落、负温差最小值 $-4.10\times10^{-2}$ K，并给出使用边界「温度沿半径单调只在问题一窗口内严格成立」；6.1 另说明驱动非单调不构成数值缺陷 |
| 交付件末行与论文表末行相差 ≤60 s，由表注说明 | 5.3 表 6 的表注句（42.24 s）、5.4 表 7 的对应句 |
| Q1 失水比例的三个口径**不得并列比较** | 5.1 结果分析写明三条口径的定义与差异来源，并声明「正文引用时一律注明所用定义」 |
| 命题只在显式前提下成立（P1–P3），且前提是 **a posteriori** 验证 | 5.3 命题陈述与证明要点、附录 A.1（含表 A1 的实测值与 P2 的裕度警示） |
| 面导度取法的 0.43 h 是 $O(\Delta r^2)$ 网格伪影，不该计入口径预算 | 5.3 结果分析、6.2、附录 A.4 三处都给出 0.4264→0.0788→0.0175 h 的塌缩序列 |

## 三、按本阶段 SKILL 的写作纪律所做的调整

- **全文无引号**（`"`、`“”`、`「」`、`『』` 零命中），要强调处一律用粗体。
- **括号只装数值与附录指引**：删去了解释型括号（如题面复述、状态说明、指路语）。交稿自检的两条 grep 零命中。
- **段首标签一律用「名词短语 + 全角冒号」**，句号收尾的「总结的一句话」已清零（`python lib/web/check_skeleton.py` 通过）。
- **「故」全部改为「所以 / 即 / 则」**。
- **重复的题面条件不复述**（如「一般持续 2～3 天」只在问题重述与结果对照处按题意引用一次）。
- **图题只写短名词短语**：口径与读数一律不进图题（`check_skeleton.py` 的图题检查通过）。
- **公式写法纪律**：多行 display 用 `gather`，未使用 `equation` + `aligned`；公式紧跟引出句、不留空行；`python -m lib.publication check` 的公式净空判据无告警。
- **两行表头**：表 2～表 7 全部用 `\multirow{2}{*}{时间/…}` + `\cmidrule(lr)`，并在合并标题行后显式补出行高（`\\[1.5pt]`），逐页目检确认两行表头无叠印、行标签竖直居中。
- **同构表并排**：表 2/表 3、表 4/表 5 各装入同一个 `table` 浮动体的两个 `papertablehalf`。
- **用宏写作**：图表一律走 `\paperfigure` / `\paperfigurepair` / `papertablehalf` / `tableblock`，未手写 `figure` 环境。
- **骨架对账**：`paper/sections/` 的标题序列与模板骨架逐条一致（`check_skeleton.py` 通过）。

## 四、未采用与不作的处理

- **源程序不排进论文**：按项目口径，代码以散装 `.py` 提交并在末页清单表登记，正文与附录都不排源码。
- **末页支撑材料清单表**仍为模板占位符，按分工由 `14Layout-and-format` 依 `reports/SUBMISSION_MANIFEST.json` 生成。
- **`paper/_base/` 与两个 `main.tex` 的导言区未改动**；唯一例外是在 `paper/main.tex` 的正文部分补了一行 `\input{sections/5_problem4}`（模板注释明确「题目不止三问时按同样的命名往后加」），并在 `paper_appendix/main.tex` 里把 `\setcounter{equation}` 由占位符 0 改为实数 16（正文实测公式总数）。
- **未删任何图**：`figures/manifest.json` 的 19 张图全部 `included=true`，只是按「正文 / 附录」分工重新分配了位置。

## 五、本轮返修回执的逐条复验（`runtime/quality/feedback/a705ae79/f8efc38e/`）

回执来自 **`8Figure-gate`**（`stage=figreview`、`status=FAIL`、**`target=drawio`**）：

| 项 | 内容 |
|---|---|
| issue `fig-5-caliber-baseline-through-label`（soft / `readability`） | `figures/caliber_sensitivity.png` 的主档基准红虚线纵贯数值标注 `56.85` 的字身；要求让基准线不再与任何数值标注的字身相交，且不得让相邻的 `56.97` 变成新的相交；不许动数值、坐标范围与色阶，也不许用 `xmax=`/`ymax=` 截短参考线 |
| advisory `adv-roadmap-print-font`（info → ⑭） | `fig_roadmap` 按 138.7 mm 排印折算约 6.6 pt，低于 8 pt 下限；按 `docs/VISUALIZATION.md` 第 6 条归 14Layout-and-format 定夺 |
| advisory `adv-analysis-d-drop-3mm`（info → analysis 的报告措辞） | `reports/ANALYSIS_MODELING_REPORT.md` 第 358 行的无口径量级句 |

**处置与复验（本阶段只做只读复验，不改图）**：

该 issue 的 `target` 是 **`drawio`**，且驱动随后已经重跑过该阶段（`run_id 30a26d73` 的 `drawio` → `figreview` 于 22:13 判 **ok**）。因此本阶段**不重做**它，只按回执的 `recheck` 在**当前盘面**上逐条复验：

| 回执 recheck 要求 | 本阶段实测 | 探针与输出 |
|---|---|---|
| 重跑 `_tmp/fig8b_line_text_cross.py`（ref 模式）⇒ `caliber_sensitivity.png` 的「参考线穿字」命中数为 **0** | 13 张图**全部**报「线穿字：无」，`caliber_sensitivity` 亦为无 | `_tmp/fig8b_line_text_cross.py`，输出 `_tmp/wr8_recheck_fig8b.txt`（退出码 0） |
| `all` 模式下若又报 `_nolegend_` 数据线命中，先看该线 `linestyle` 是否为 None（`errorbar(fmt="o")` 的连线不绘制） | 在隔离沙箱里重跑该图的生成函数并读回线属性：命中那条 `_nolegend_` 线 `linestyle='None'` ⇒ **不绘制**，属探针假阳；参考线 `_child1` 的 `linestyle='--'`（真画出），其穿字命中为 0 | `_tmp/wr8_caliber_falsepos.py`（退出码 0） |
| 放大交付像素目检 `56.85` 与 `56.97` 两处标注均无压字 | 打开交付 PNG 目检：`56.85` 的标注已被翻到该点的**左侧**、与基准线不接触；`56.97` 的字框右缘紧邻基准线但字身未被穿过 | 目检（本阶段另留一张 200 dpi 的渲染图 `_tmp/wr8_pages/caliber.png`） |
| `_tmp/fig8_repro_check.py` 仍 13/13 逐字节相同 | 原样重跑，13 张 PNG 的沙箱副本与交付件逐字节相同 | `_tmp/fig8_repro_check.py`，输出 `_tmp/wr8_recheck_repro.txt`（退出码 0） |
| `python -m lib.visualization audit` 仍 PASS | **PASS** | 见下 |

**两条 advisory 的处置（都不属本阶段）**：`adv-roadmap-print-font` 是**版式/嵌入尺寸**，按 `docs/VISUALIZATION.md` 第 6 条归 **14Layout-and-format**，本阶段不处置；`adv-analysis-d-drop-3mm` 指向 `reports/ANALYSIS_MODELING_REPORT.md`，属上游报告措辞，本阶段不改上游报告。

**★ 本阶段自查发现并已修复的一处副作用（如实登记）**：为复验上面的 `_nolegend_` 假阳，本阶段写了一个在沙箱里重跑 `fig_caliber_sensitivity` 的探针；该图的 `export()` 使用的模块级 `ROOT` 指向项目根，于是**在项目根**里重渲染了 `figures/caliber_sensitivity.{png,pdf,svg}` 并重写了 `figures/manifest.json`（该图的 `review.status` 被重置为 `pending`）。处置与证据：

- **画面零变化（硬证据）**：重渲染产生的 PNG 与本阶段探针运行**之前**的交付 PNG sha256 相同（`39a7dea5766cb249…`）——这一对哈希由 `_tmp/fig8b_line_text_cross.py` 的「沙箱 PNG == 交付 PNG」自证段在副作用发生**之前**给出；PDF/SVG 的字节变化来自容器内嵌时间戳，与本项目已知口径一致。
- **复核签名已按当前快照重签**：`python -m lib.visualization review caliber_sensitivity`（reviewer 记为 `9Paper-writing（目检复核）`，note 记录目检所见与上面这处副作用的来龙去脉）⇒ `python -m lib.visualization audit` 恢复 **PASS**；其余 18 张图的复核记录未受影响。
- **两个工程的图件副本已重新同步**：`paper/figures/` 与 `paper_appendix/figures/` 的 19 个 `.pdf` 逐份 sha256 与 `figures/` 相同（0 处不一致），两个工程各自重编译。

## 六、本轮返修回执的逐条复验（`runtime/quality/feedback/30a26d73/caa2ae53/`，10 条）

回执来自 **`10Math-proof-gate`**（`gate_decision.json` 的 `stage=mathproof`、`status=NEEDS_FIX`、
`target=write`；报告 `MATH_PROOF_REPORT.md` 的整题裁决为 `REVISE_HARD`）。其中 **3 条 `hard`**
（两条方向/配对写反、一条链式法则符号滑误）、**7 条 `soft`**（口径未写明、登记值不符）。
本阶段按「返修只动清单内」逐条落地，**改动面 = 5 个正文节文件 + 附录节文件共 6 份**
（`diff` 实测，见「6.3 改动面自证」），`paper/main.tex`（含摘要）、`references.tex`、
`1_restatement` / `2_analysis` / `3_assumptions` / `4_symbols` / `7_evaluation` / `A1_materials` /
`paper_appendix/main.tex` **一字未动**。

### 6.1 逐条处置

| # | issue（severity） | 原表述 | 现表述（改动落在哪） | 复验判据与实测 |
|---|---|---|---|---|
| 1 | `mp-d-pm20-pairing-reversed`（hard / `narrative_consistency`） | §6.2「把它乘 1.2 或 0.8，达标时刻分别移动 $+12.68$ h 与 $-8.37$ h」，把乘 1.2 配到了时间**延长** | §6.2 改为「把它乘 1.2 时达标时刻**缩短** 8.37 h（问题三）与 7.42 h（问题四），乘 0.8 时**延长** 12.67 h 与 11.19 h，弹性为 $-0.88$」；表 A5 该行标签写成 `扩散系数 $+20\%$／$-20\%$`、格内按同序写 `$-8.37$／$+12.67$`，$+12.68$ 改为产物登记的 $+12.67$ | `tmp/rob/out/cv_q23_D_times1.2.json` 的 `t_dry_step_h`=48.7833、`cv_q23_D_times0.8.json`=69.8167；基准 `results/convergence.json :: mesh_tdry.320.t_dry_step_h`=57.15 ⇒ $\Delta=-8.37$ / $+12.67$，与正文同号；表 9 第 4 行仍 69.8 / 62.0（未动） |
| 2 | `mp-temperature-radial-direction-inverted`（hard） | §5.2「温度沿半径**单调不增**这一性质只在问题一的窗口内严格成立」 | §5.2 改为「温度关于半径**单调不减、表面最高而中心最低**这一性质只在问题一的窗口内严格成立…」；使用边界与 72 h 内部极值的披露原样保留 | `results/q1.json :: table1_T_C` 末行 33.5765→36.7863、`results/q2.json :: table3_T_C` 六行逐格递增；与 `ANALYSIS_MODELING_REPORT.md` §5.8 第 6 条、`RESULTS_REPORT.md` §8.1 的「单调不减（表面最高）」一致 |
| 3 | `mp-appendix-a5-chainrule-sign`（hard / `proof_validity`） | 附录 A.5「固定 $\xi$ 时 $\partial_tC|_\xi=\partial_tC|_r+\partial_t\xi\,\partial_\xi C$」，把两个代入值代进去得 $-(\dot R/R)r\partial_rC$，与紧接的式 (eq:a-frame) 符号相反 | 附录 A.5 中间式改为 $\partial_tC|_\xi=\partial_tC|_r+(\partial_t r|_\xi)\,\partial_rC$，并写明固定 $\xi$ 的物质点满足 $\mathrm dr/\mathrm dt=\xi\dot R$、$(\partial_t r|_\xi)=\xi\dot R=r\dot R/R$；等价形式写成**减去** $(\partial_t\xi|_r)\partial_\xi C$ | `sympy`：$(\partial_t r|_\xi)$ 与 $-(\partial_t\xi|_r)(\partial_\xi C)$ 都化简为 $\xi\dot R$，在 $r=\xi R$ 上又与 $(\dot R/R)r$ 相等 ⇒ 与式 (eq:a-frame) 同号（`_tmp/w9_recheck.py` 判据 ③） |
| 4 | `mp-q2-argmax-unqualified`（soft / `proof_applicability`） | §5.2「最坏点位置逐时刻自检，259200 步中没有任何一步出现最坏点偏离中心」 | §5.2 补护栏口径：「护栏判据取亏量 $\max_rC-C(0,t)$ 超过 $10^{-10}C(0,t)$ 才算一次违约，259200 步中违约次数为 0；同一自检在原始布尔口径下有 478 步因浮点并列被判为偏离，最大亏量 $9.3\times10^{-15}$ kg/kg」 | `results/q2.json :: selfcheck.argmax护栏`：`argmax_raw_deviations`=478、`guarded_violations`=0、`max_deficit`=9.326e-15、`guard_threshold_min`=1.374e-11 ⇒ 三字段与句内口径一一对应 |
| 5 | `mp-appendix-a2-residual-and-leak-caliber`（soft） | 附录 A.2 一句里 (a) 漏项比例未写 $\dot R$ 的差分口径；(b)「逐时间步的离散残差不超过 $1.1\times10^{-16}$」与表 A3 的 $1.1\times10^{-15}$ 不同口径 | (a) 同句写入口径「$\dot R$ 取对分段线性的 $R(t)$ 作中心差分」，并说明 $t=22$ h 依赖跨段中心差分、改用相邻采样节点斜率口径时变成 132/46/14/7%；(b) 正文界改为 $1.1\times10^{-15}$ 并注明「与表 A3 的问题四行同口径」 | `results/consistency.json :: conservation_q4_60s.water_max_abs`=1.12367e-15（`code/sensitivity.py` 的 `rC = dC_int - bcC` 对全部时间步取 $\max|\cdot|$）⇒ 正文界 = 表 A3 值，不再小于表里的界 |
| 6 | `mp-appendix-tableA2-caliber-mashup`（soft） | 表 A2 同时列「网格 $n$（$\Delta t=60$ s）」与「步长 $\Delta t$/s（$n=320$）」，却只有一个「达标时刻/h」列，四个值全是网格序列的**步进首达**；表后那句收敛阶断言引用的也是同一串 | 表 A2 拆成两个并列栏，各带自己的达标时刻列；两栏都改用**连续根**口径；表后那句改为引用网格连续根的相邻差 0.1204 / 0.0518 / 0.0206 h。**§5.3 正文里同构的那一句一并改**（回执复验要求「正文与附录的收敛阶断言引用的序列与其口径描述一致」） | `results/convergence.json`：`mesh_tdry` 的连续根 56.9707/57.0911/57.1429/57.1635（相邻差 0.1204/0.0518/0.0206）、`step_tdry` 的连续根 57.1429/57.1406/57.1390/57.1383；表内任一行的三数可指认到同一条 |
| 7 | `mp-appendix-tableA5-tinf-row`（soft） | 表 A5 环境温度行 Q3 格只给 $\pm1.81$，而正文 §6.2 与表 9 用 1.90（上游配对两端不对称：$-1$ °C ↦ $+1.90$ / $+1.68$、$+1$ °C ↦ $-1.81$ / $-1.61$） | 该行标签写成 `环境温度 $-1$／$+1$ $^\circ$C`，格内按同序写 `$+1.90$／$-1.81$`（Q3）与 `$+1.68$／$-1.61$`（Q4）。表 9 第 3 行 59.0 / 52.5 与 §6.2 的 1.9 / 1.7 **未动** | 全文该量只剩一组数；与 `ROBUSTNESS_REPORT.md` §3 的 `$T_\infty-1$ °C → +1.90 h / +1.68 h` 一致 |
| 8 | `mp-analytic-moisture-span-240`（soft） | §5.1「水分侧在 $t=1800$ s 的偏差为 $1.13\times10^{-4}$ kg/kg，对应场跨 **2.40** kg/kg」 | 改为 **2.45** kg/kg | 按 `code/sensitivity.py` 的同一实装在 $\mathrm{Fo}=0.0222194$ 上现算得 2.449938 kg/kg（`_tmp/mp1_claims_probe.txt`）；与「场量程 2.45」一致 |
| 9 | `mp-surface-rise-six-tenths`（soft） | §5.1「表面温度的抬升幅度约为环境在 30 min 内升幅的**六成**」 | 改为**六成五**；与 $\mathrm{Bi}_h$ 接近 1 相称的定性结论保留 | 由附件 1 现取 $T_\infty(0)=28.000$、$T_\infty(1800)=41.513$（升幅 13.513 K），配表 2 表面列 36.7863（升幅 8.7863 K）⇒ 比值 0.6502 |
| 10 | `mp-q4-temperature-equation-derivation-gap`（soft / `proof_validity`） | §问题四把参考坐标下的温度方程直接写出、缺与水分侧对称的换帧理由；「守恒式除以 $\rho_d$」挂在同时含 $C$ 与 $T$ 的式 (eq:q4-pde) 之下；「含 $\dot R/R$ 的两支逐点相消」按字面会被读成所有含 $\dot R/R$ 的支都消掉 | §5.4 (a) 补一段温度侧的可核理由（能量平衡本是物质导数形式 $\rho c_p(\partial_tT|_r+v_s\partial_rT)=\frac1r\partial_r(rk\partial_rT)$，而该物质导数恰等于换帧导数 $\partial_tT|_\xi$，故对流项被换帧项逐点吸收、帧坐标下不再出现对流项）；(b)「守恒式除以干物质密度」改为只挂在含水率方程上；(c) §5.4 与附录 A.5 两处都把相消项写清为正比于 $C$、不含 $\partial_rC$ 的两支（$\partial_t\rho_d+\rho_d\nabla\!\cdot\!v_s=0$ 的体现），并点明幸存的 $\rho_dv_s\partial_rC$ 由换帧项配掉 | 三项均逐字核过（`_tmp/w9_recheck.py` 判据 ⑩a/⑩b/⑩c）；替换式与 `ANALYSIS_MODELING_REPORT.md` §8.4 的写法对齐 |

### 6.2 复验汇总

`_tmp/w9_recheck.py`（本轮新写的复验探针，只读论文源码 / `results/*.json` / `tmp/rob/out/*.json`）
把回执的 **10 条 `recheck` 拆成 25 条可判据的断言**逐条实跑，**25/25 通过**（输出 `_tmp/w9_recheck.txt`，
退出码 0）。回执点名的探针 `_tmp/mp1_claims_probe.py`、`_tmp/mp1_monotone_probe.py` 上一轮为同一批
对象写过，本轮**原样重跑**（换用项目环境 `config/runtime.local.json` 指定的 Python，退出码 0），
A–I 各段的数在当前盘面上逐位复现。

### 6.3 改动面自证

以回退快照 `产物/cache/2026A_2026.9.29_23.25.45/论文撰写/` 为「改前」基准逐文件 `diff`：

| 项 | 实测 |
|---|---|
| 被改的源文件 | 6 份：`5_problem1.tex`、`5_problem2.tex`、`5_problem3.tex`、`5_problem4.tex`、`6_check.tex`、`paper_appendix/sections/A_appendix.tex` |
| 未动的文件 | `paper/main.tex`（含摘要）、`references.tex`、`1_restatement`、`2_analysis`、`3_assumptions`、`4_symbols`、`7_evaluation`、`A1_materials`、`paper_appendix/main.tex` —— 全部逐字节相同 |
| hunk 数 | 13 处（`_tmp/w9_diff/all.diff`），与回执清单一一对应，无越界改动 |
| 图与数值 | `figures/`、`results/`、`code/` 一字未动（本轮不改图、不重算）；`python -m lib.result_contract export` 重跑后 `paper/result-values.json` 与 `.tex` 逐字节相同 |

### 6.4 镜像一致性（同一量在摘要/正文/表/附录反复出现的那种）

改动过的量在全文各处的落点已逐处核过：

| 量 | 落点 | 现状 |
|---|---|---|
| $D\pm20\%$ 的时移 | 摘要、§6.2（首句与「留裕度」对照段）、§7.3 缺点四、表 A5、表 9 第 4 行 | 摘要与两处正文写「$-8.4$ 与 $+12.7$ h」（先加后减），§6.2 首句与表 A5 写全乘子绑定；表 9 第 4 行 69.8 / 62.0 不变 |
| 温度径向方向 | §5.2 结果分析 | 唯一一处方向陈述，已改为「单调不减、表面最高而中心最低」；§5.2 模型准备的「不能无条件引用温度沿半径单调」保持方向中性 |
| 水分侧单调方向 | §5.3 命题、§5.3 结果分析、§5.4 具体分析、附录 A.1 | 四处仍是 $C$ 关于 $r$ **单调不增**（表面最干），与本轮改动无关、方向正确 |
| 收敛序列 | §5.3 结果分析、附录表 A2 与表后句 | 两处都用连续根口径，数值与 `results/convergence.json` 逐位一致 |
| 离散残差上界 | 附录 A.2 正文、表 A3 问题四行 | 同一口径、同一个 $1.1\times10^{-15}$ |
| 环境温度 $\mp1$ °C 的时移 | 表 A5、§6.2、表 9 第 3 行 | 表 A5 给两端各自的数，§6.2 与表 9 用低 1 °C 那一端（1.9 / 1.7、59.0 / 52.5），互不冲突 |
| 水分场跨 / 表面升幅比 | §5.1 模型求解段、§5.1 结果分析段 | 2.45 kg/kg 与「六成五」各只出现一次，无第二处引用 |

### 6.5 编译与门禁自查

| 检查 | 结果 |
|---|---|
| `xelatex` 两遍（`paper/`） | 退出码 0，`!` 错误 0 条；`Overfull` 1 条（74.6 pt，与改前**同一条**，见 6.6） |
| `xelatex` 两遍（`paper_appendix/`） | 退出码 0，`!` 错误 0 条；`Overfull` 3 条（与改前同数同量级） |
| `python lib/web/check_skeleton.py` | 「骨架对账通过」 |
| `python -m lib.publication check` | **PASS**，issues / warnings / prose_issues 全空 |
| `python -m lib.publication report` | **PASS**：总 32 页、计入 30 / 上限 30、摘要版心填充 91.7%（目标 ≥0.90） |
| `python -m lib.visualization audit` | **PASS**（本轮未改图，19 张图的复核记录全部未受影响） |
| `python -m lib.result_contract export` | 退出码 0；`result-values.json` / `.tex` 内容逐字节未变 |
| 全文引号 / 文言「故」/ 解释型括号 | 三条自检零命中（用 Python 复扫；`grep` 在 GBK 控制台下对多字节字符会误报，见 6.6 第 4 条） |
| `paper/formula-review.json` | 已重绑当前 `main.pdf`：提示项由 18 增至 20（`5_problem4.tex` 新增两行长文本、旧行号 61/107 平移到 63/109），逐项 `decision=retain`、`page` 按现 PDF 实测重填、`source_sha256` 更新（`_tmp/w9_rebind_formula_review.py`） |
| `paper/page-map.json` | 已重绑：物理页分类与改前**相同**（abstract 1、body 2–30、八/九 31、附录 32） |

### 6.6 如实登记的三处观察（不在回执清单内，本轮**未改**）

1. **页数与附录长度**：正文工程仍 32 页、计入 30 页，与改前相同；但**附录工程由 8 页变为 9 页**
   （本轮按回执要求补写的内容挤出约半页），末页只有约 241 个字符。附录页数不受 `config/publication.json`
   约束（「附录单独起页、不限页数」），故未为压页而删改回执要求的内容。
2. **`Overfull \hbox (74.6 pt)`**：`paper/main.log` 第 1402 行的这一条在**改前的同一位置**就有
   （`产物/cache/…/paper/main.log` 第 1400 行，数值逐位相同），不是本轮引入；附录工程的三条同理。
3. **表 A5 其余各行仍用 $\pm$ 记号**：本轮只把回执点名的两行（扩散系数、环境温度）改成不含歧义的
   端点写法；为使该表在新记号下不自相矛盾，另把「活化能 $\pm2\%$」改为「活化能 $-2\%$／$+2\%$」
   —— 该行的格序（$-10.63/+13.64$）原本就是「先减后加」，与 $\pm$ 的读法相反。其余四行
   （传质系数、环境水分浓度、初始含水率、换热系数）经 `_tmp/w9_a5_pairings.py` 逐格核过：
   其记号与格序**自洽**，故未改，以避免超出回执范围。另有两处**上游口径本身不齐**、本轮**不改**：
   表中「初始含水率」与「换热系数」两格取的是连续根口径（$\pm0.048$、$\pm0.013$），
   其余各行取的是 $\Delta t=60$ s 的步进口径。
4. **`check_skeleton.py` 之外的自检脚本**：`skills/15Verification/scripts/writing_check.sh`
   对 `paper/` 报 5 条 `FAIL`（`labels_appendix.tex` 条件 `\input`、`A1_materials.tex` 的 `A1_`
   前缀与「无 `\section` 标题」、图件「未被引用」——`\paperfigure` 只写 stem），全是该脚本的
   已知误报类；本轮改动未新增任何一类命中。

## 七、本轮定点修复（数学论证门禁回执 `9c60b380 / a91dda5f`）

被退回的阶段产物已按回退快照复原（`产物/cache/2026A_2026.9.29_23.59.49/论文撰写/`，与工作区根逐字节相同），
本轮只动回执 issues 点名的两处，**不重写任何小节**。

### 7.1 issue `mp-q4-rform-convective-term-label`（must）：§5.4 把项名挂到了不含它的式子上

| 项 | 内容 |
|---|---|
| 文件 | `paper/sections/5_problem4.tex`（§5.4 模型建立，换帧那一句） |
| 改前 | 换帧项与式~(`\ref{eq:q4-rform}`) **幸存的对流项 $\rho_dv_s\partial_rC$** 逐点相消 |
| 改后 | 换帧项与式~(`\ref{eq:q4-rform}`) **的对流项 $\frac{\dot R}{R}r\,\partial_rC$** 逐点相消 |
| 依据 | 式 (`eq:q4-rform`) 是**同除 $\rho_d>0$ 之后**的式子，它的对流项就是 $(\dot R/R)r\partial_rC$（即 $v_s\partial_rC$），不含 $\rho_d$；$\rho_dv_s\partial_rC$ 是**除之前**那一支的幸存项，仍正确地留在上一句与附录 A.5 里 |
| 未动 | 推导链、结论式 (`eq:q4-pde`)、全部数值、表 7 与 §5.4 其它段落 |

### 7.2 issue `mp-a2-energy-identity-domain`（must）：附录 A.2 的能量恒等式未与适用口径绑定

| 项 | 内容 |
|---|---|
| 文件 | `paper_appendix/sections/A_appendix.tex`（A.2 表 A3 之后） |
| 改动 | ① 原式改称「能量侧**在定域下**（$R$ 为常数，问题一至问题三）的恒等式」；② 新增一段：说明把 $R$ 提到导数号之外在动域会多出 $2(\dot R/R)\int_0^R\rho c_pT\,r\,\mathrm{d}r$，并给出平凡反例（$T$ 与 $\rho c_p$ 为常数、$R$ 收缩时左端 $\rho c_pTR\dot R$ 而右端为零）；③ 给出该式的来历（把正文问题四一节参考坐标下的能量方程乘 $\xi\,\mathrm{d}\xi$ 积分、再用其表面条件消去边界通量）并新增参考坐标形式式 (`eq:a-q4energy`)：$\mathrm{d}/\mathrm{d}t[\int_0^1\rho c_pT\xi\,\mathrm{d}\xi]-\int_0^1T\partial_t(\rho c_p)|_\xi\xi\,\mathrm{d}\xi=(k/R^2)\partial_\xi T|_{\xi=1}=-(h/R)(T(1,t)-T_\infty(t))$，与水分侧式 (`eq:a-q4bal`) 同一种写法；④ 写明表 A3 的问题四能量行取自该式，与 §5.4「守恒校核也按参考坐标形式进行」对应 |
| 依据 | 该式正是一致抛物实装的那一支：`code/core.py` 的 $V$ 是 $\xi$ 权重、$bcT=\Delta t\,(1/R^2)R\,h_c(T_\infty-T_s)$、$dE=\sum\mathrm{cap}_{\rm used}\Delta T\,V$；探针重跑该支**逐位复现** `results/consistency.json` 的 `conservation_q4_60s`（$3.991299\times10^{-5}$、$8.821076\times10^{-11}$） |
| 未动 | 减号论断与三处实测数（$-2.7446$ / $-4.9850$ / $+2.2404$ 与 $-445\%$）、表 A3 全部数字、水分侧 (`eq:a-q4bal`) 那一整段 |

### 7.3 改动面自证

| 检查 | 结果 |
|---|---|
| 改动文件数 | **2**（`paper/sections/5_problem4.tex` 改 1 行内的一句；`paper_appendix/sections/A_appendix.tex` 改 1 句 + 新增 2 段与 1 式）。逐文件核对（sha256 对回退快照）：另只动了由它们派生的 `paper/main.pdf`、`paper_appendix/main.{pdf,aux,log}` 与两处绑定 `paper/formula-review.json`、`paper/page-map.json`；`main.tex`、`_base/*`、`references.tex`、`result-values.*`、其余 11 份节文件全部逐字节未变 |
| 与回执清单的关系 | 一一对应、无清单外改动；其余各节、`main.tex`、`_base/`、`references.tex`、`results/`、`figures/` 零改动 |
| 页映射可继承（不是假设） | `_tmp/w9c_page_structure.py`：改前那一版 PDF 与现 PDF **逐页**比对 —— 32 对 32 页，**31 页文本层逐字节相同**，唯一有差异的第 23 页其差异窗口只有 10 / 8 个字、且正是本轮改掉的记号（公共前缀 388 字、公共后缀 697 字）⇒ 没有发生任何重排 |

### 7.4 复验（探针与结果）

| 探针 | 覆盖 | 结果 |
|---|---|---|
| `_tmp/w9c_energy_identity.py` → `.txt` | 两条 issue 的 recheck 各分项：项名与所引式子一致（含式内不含 $\rho_d$）、结论链未动、上游那句仍挂 (`eq:q4-conserve`)、A.2 的定域限定/多余项/反例/参考坐标式/表 A3 指认；sympy 三条（$\dot G-2(\dot R/R)G=R^2\mathrm{d}/\mathrm{d}t\int_0^1X\xi\,\mathrm{d}\xi$、平凡反例、换帧项＝该式对流项）；数值（实装口径逐位复现注册残差；r 口径逐步残差 / $\Delta t\cdot2(\dot R/R)G=1.0011$）；两份 PDF 文本层 | **26/26 通过** |
| `_tmp/w9_recheck.py`（上一轮为同一批对象写的探针，**原样重跑**） | 上一轮回执 10 条的 25 个分项 | **25/25 通过**（零漂移） |
| `_tmp/w9_a5_pairings.py`（同上，原样重跑） | 表 A5 每行「乘子 → 时移」的逐格指认 | 与产物一致（hm 行：$+20\%\to-1.05/-0.40$、$-20\%\to+1.70/+0.69$，步进口径） |
| `_tmp/w9c_selfcheck.py` → `.txt` | 引号 / 解释型括号 / 文言「故」/ harness 词的源码层复扫（**含附录工程两份 .tex**：上一轮的扫描面漏了它们）；两份交付 PDF 文本层扫内部词表 deny 全表；本轮目标串抽查（含新增的来历句与「即得参考坐标下的能量恒等式」） | 源码层 **0 命中**、PDF 文本层「无」命中、目标串全部在、旧串全部不在 |
| `_tmp/w9c_formula_pages2.py` → `.txt` | 20 个公式提示项的物理页：先在改前那一版 PDF 上自证判别法（0/20 失败），再核登记页是否落在现 PDF 的命中集合里 | **20/20 在集合内** |
| `_tmp/w9c_rebind_formula_review.py` → `_tmp/w9c_rebind.txt` | 重绑 `paper/formula-review.json`：提示项集合与上一版逐项相同（20 项，无增无减），`decision/reason` 沿用、`source_sha256` 按现源码刷新、`pdf_sha256` 绑定现 PDF | 已重绑 |
| `python lib/web/check_skeleton.py` | 骨架对账 | 通过 |
| `python -m lib.publication check` / `report` | 计页与公式复核绑定 | **PASS**：总 32 页、计入 30 / 上限 30、摘要版心填充 **91.7%**（与改前逐位相同）、issues / warnings / prose_issues 全空 |
| `python -m lib.visualization audit` | 19 张图 | **PASS**（本轮未改图） |
| `xelatex` 两遍（两个工程各两遍） | 编译 | 退出码 0，`!` 错误 0 条 |

### 7.5 回执 advisories 的处置（**均不在本轮改动面内**，逐条说明）

| advisory | 严重度 | 指向的文件 | 本轮处置与理由 |
|---|---|---|---|
| `adv-fig-rb-tornado-caption-12p68` | info | `figures/manifest.json` 的 `rb_tornado.caption` | **不改**：该串属图件注册层，是 ⑥稳健性／⑦⑧ 的产物，不在本阶段改动面内；交付件正文不含这两个数（见 `_tmp/w9c_selfcheck.txt` 的 PDF 文本层扫描） |
| `adv-fig-convergence-step-vs-root-caliber` | info | 同上，`convergence` 图注 | **不改**：同上；且两处各自已声明口径、不含假陈述 |
| `adv-tableA5-hm-row-ambiguous-label` | info | `paper_appendix/sections/A_appendix.tex` 表 A5 传质系数行 | **本轮不改**：属本轮清单**之外**的 info 项，改动面严格等于回执 issues；已用 `_tmp/w9_a5_pairings.py` 核过该行两个数与乘子一一对应（$+20\%\to-1.05$、$-20\%\to+1.70$），留给后续轮次按类目处理 |
| `adv-abstract-duplicated-word` | info | `paper/main.tex` 摘要末段「比数值数值预算」 | **本轮不改**：同上（且改摘要会动版心填充这一计页判据）；已确认该串仍在、位置与回执描述一致 |
| `adv-analysis-frame-chainrule-slip` | info | `reports/ANALYSIS_MODELING_REPORT.md` §9.3 | **不改**：被审对象不属本阶段，本阶段不改编模报告 |
| `adv-analysis-p3-corner-basis` | info | 同上 §9.1 | **不改**：同上 |

---

## 八、本轮重跑（2026-09-30，回退到 write 之后；按 `11Cross-question-check` 的 6 条判词 ＋ 现行 SKILL 自检清单定点改写）

### 8.0 本轮的起点与清单（先把"为什么是这一轮"写清楚）

| 项 | 事实 |
|---|---|
| 起点 | 上一轮交付件被回退归档在 `产物/cache/2026A_2026.9.30_01.16.54/论文撰写/`（`paper/`、`paper_appendix/` 连同 10/11 两关的报告）。本阶段按复用纪律**原样捞回**（逐字节相同）作为起点，不从零重写 |
| `fix` 那一关 | **未跑完**：`runtime/quality/feedback/manual/e770a816/gate_decision.json` 的内容是 `{"status":"PASS","reason":"not_gate","issues":[]}`（schema 占位，无 issues）。所以本轮**不存在**"按 fix 回执返修"这回事 |
| 本轮的清单 | ① 上一关 `CROSS_QUESTION_REVIEW.md` 的 **6 条成稿侧判词**（整题裁决 REVISE_CLAIM）；② 现行 `skills/9Paper-writing/SKILL.md`（**2026-09-30 0:41:39 更新**）的自检清单 |
| 上游输入 | **未变**：`reports/` 下各报告（`RESULTS_REPORT.md` 17:45、`RESULT_AUDIT_REPORT.md` 18:00、`ROBUSTNESS_REPORT.md` 19:21、`DRAWIO_REPORT.md` 21:48、`FIGURE_REVIEW_REPORT.md` 22:12）mtime 全部早于上一轮成稿（9/30 0:04），本阶段**未改任何上游产物** |
| 交付数值面 | **零变化**：本阶段只改 `paper/`、`paper_appendix/` 两棵树里的 `.tex`（外加两件由命令生成的登记件），`code/`、`results/`、`figures/`、`reports/` 全部未动 |

### 8.1 跨问一致性 6 条判词，逐条处置（全部按**现盘**独立复算，不采信回执转述）

复算脚本：`_tmp/w10_facts.py` → `_tmp/w10_facts.txt`（附件 1 的温度列、`code/outputs/figdata_q2.npz`、`tmp/rob/out/*.json`、`results/sensitivity.json`）。

| id | 位置 | 改前 | 改后 | 现盘复算依据 |
|---|---|---|---|---|
| `xq-q2-tinf-maxfall-0797` | §5.2（`5_problem2.tex` 模型准备） | 单步最大**回落** 0.797 $^\circ$C | 单步最大**升幅** 0.797 $^\circ$C、单步最大**回落** 0.450 $^\circ$C | 附件 1 的 240 个相邻差：最大升幅 $+0.7970$（$t=240$ s，$30.037\to30.834$）、最大回落 $-0.4500$（$t=13500\to13560$ s，$50.212\to49.762$）、回落步 95 步；0.797 是 \|Δ\| 的最大值而不是回落的 |
| `xq-abstract-surface-env-002h` | 摘要 vs §5.2 | 摘要写"表面在 24 h 后与环境之差已不足 0.02 kg/kg" | 摘要改写为"表面与环境之差自**约 22.2 h** 起一直不足 0.02 kg/kg" | `figdata_q2.npz` 的 $C_{\rm surface}-C_\infty$：首次 $<0.02$ 且此后一直保持的时刻 $=22.1517$ h；22.2 h 处 0.019891、24 h 处 0.016433 ⇒ 24 h 不是该事件时刻。摘要与 §5.2 的"约 22.2 h"现同值 |
| `xq-env-extension-caliber-mixed` | §5.3 / §6.2 / 附录 A.4 / 假设三 | §5.3 的**读数**取自 $n=160$ 步进首达（56.9667、56.8500），**跨度** 0.24 h 取自 $n=320$ 连续根；附录 A.4 表内 0.24、表后正文 $\pm0.25$；假设三写"不超过 0.25 h" | 读数改用**同一份产物**：`$n=320$ 连续根为 57.0055 与 56.9011 h`（`tmp/rob/out/cal_env_peak_n320.json` / `cal_env_plateau_n320.json` 的 `t_dry_root_h`）；§5.3 与 §6.2 的跨度都写明"$n=320$ 连续根口径下"；附录 A.4 表后正文改为"加环境延拓三档的 $0.24$ h"；假设三改为"达标时刻的跨度为 0.24 h" | 三档连续根 57.1429 / 57.0055 / 56.9011 ⇒ 跨度 **0.2418 → 0.24 h**（步进首达那一组是 0.2333）；§6.2 另加一句点明"图中该两档是 $n=160$ 对照实现上的读数，与这个跨度不是同一口径，不能直接相减"。**预算总数 ±0.32 h 与 ±0.5 h 一字未动** |
| `xq-q3-h-half-shift-003` | §5.3（口径敏感性段） | "对流换热系数减半时只移动 0.03 h" | "对流换热系数减半时只移动 **0.08 h**" | `tmp/rob/out/sw_q23_hc_1.json` 与 `sw_q23_hc_0p5.json`：连续根 $57.1429\to57.2228$ ⇒ $+0.0799$（步进首达同档 $+0.0833$）；0.03 h 是 $\rho,c_p,k$ 的 ±10% 那条通道的值，属另一条 |
| `xq-tableA5-q4-c0-shift-0048` | 附录表 A5"初始含水率 ±1%"行 | 问题四列写 $\mp0.048$ | 问题四列改为 $\mp0.046$ | `cv_q4_C0_times1.01/.99.json` 相对 `cv_q4_base.json` 的连续根：$+0.0458/-0.0463$；$\mp0.048$ 是问题三那一列（$+0.0472/-0.0477$）。问题三两列不动 |
| `xq-table-lastrow-timecell-label` | §5.3（两处）与 §5.4（一处） | "结果表末行保留题面给定的行标签，**时间列写本档达标时刻的四位小数格式值**"；"表末行的时间是连续达标时刻" | 改为"结果表的末行沿用题面给定的行标签，**行内各距离列取该档达标时刻的场**"；"表末行的行内数值取自连续达标时刻的插值场" | 表 6 / 表 7 末行的时间格印的是题面标签 **烘干结束时间**（`request/problem.md` 表 5 的末行标签即为此），0.1500 落在**距离列**（0 cm）而不是时间格；达标时刻写在正文与表注里 |

### 8.2 现行 SKILL 自检清单里本轮补做的三项

| 项 | 判据（SKILL 出处） | 改前 | 改后 |
|---|---|---|---|
| **参考文献条数** | 步骤 5："全表 **8–12 条**……超过 12 条就停手：剩下的引用需求靠合并同类项或改写成本句直接陈述" | **17 条**（`ref1`–`ref10`、`ref12`–`ref18`） | **12 条**：删 `ref2`、`ref8`、`ref12`、`ref14`、`ref18`，并把 4 处引用改成直接陈述（§1 的"是主流的干燥方式"只留 `ref16`；§5.1 删"内部与表面温度剖面存在瞬态差异的直接证据见文献"；§5.2 删"近年耦合热湿传递仿真的实现范式见文献"；§5.3 改为"用干燥均匀性与最差点表征薄层干燥的研究说明，平均含水率不能代替各处达标"；§5.4 删"各向同性收缩的有限元实现见文献"）。闭环由 `_tmp/w10_refs.py` 核：**条目 12、每条被引、每个 `\cite` 有条目、每条带 DOI** |
| **符号表闭环** | 步骤 4 写作完整性自检 ⑥："正文每个符号都在符号表、符号表每条都在正文出现"；跨问回执的建议 `adv-symbol-table-unused-st` 亦点名 | 表 1 有 `$s_T$`（能量方程的体积源项）与 `$T_0$`，两者在正文与附录**一次也没出现**（`_tmp/w10_symbols.py` 实测 0 命中） | 删去 `$s_T$` 整行；`$T_0,\ C_0$` 行改为 `$C_0$ & 初始干基含水率，$C_0=2.55$ & kg/kg`（`$C_0$` 在正文出现 6 次） |
| **摘要重复词** | 跨问回执建议 `adv-abstract-duplicated-word` | `main.tex` 摘要末段"比**数值数值**预算大 15 至 25 倍" | "比数值预算大 15 至 25 倍"（§6.2 同句本来就是这个写法） |

### 8.3 页边界归属：本轮顺带修好的一处（实测，不是推断）

`config/publication.json` 的判据 `boundary_top_ratio = 0.30`：某类别的**起始页**上，该类别的起始标记必须落在页面上部（`kind_start_markers`）。它对**上一轮交付件**的判定是：

| 类别起始页 | 上一轮交付件 | 本轮 |
|---|---|---|
| p2 `body`（标记"一、"） | 8.7% 合规 | 8.7% 合规 |
| p31 `ai_statement`（标记"八、"） | **40.7% 不合规**（该页开头是表 9 与「七」的用法段） | **14.9% 合规** |
| p32 `appendix`（标记"附录"） | **41.7% 不合规**（该页开头是参考文献 [10]–[17]） | **8.7% 合规**（附录现在整页从页首开始） |

也就是说：**上一轮那一版按现在的判据根本绑不上页映射**（该判据是 2026-09-30 0:40 才加进 `lib/publication/checks.py` 的，晚于上一轮绑定），而本轮的改动把它推到了合规区间。两条成因与处置：

1. p31 开头的表 9 与用法段 —— §8.1 的第 ⑥ 项与参考文献瘦身把表 9 推回 p30；剩余 2 行正文仍在 p31 页首（14.9%，判据内）。
2. p32 开头的参考文献 —— 参考文献由 17 条减到 12 条后，**九、参考文献 现在整段收在 p31**，附录整页从 p32 页首开始。

### 8.4 改动面自证（逐文件 sha256 ＋ 逐行 diff）

基线 = 回退归档的那一版（`产物/cache/2026A_2026.9.30_01.16.54/论文撰写/`）。探针 `_tmp/w10_changeset.py` → `.txt`。

| 工程 | 文本件 | 逐字节相同 | 变化 |
|---|---|---|---|
| `paper/` | 21 | 8 | **13**：`main.tex`、`references.tex`、`sections/1_restatement`、`3_assumptions`、`4_symbols`、`5_problem1`、`5_problem2`、`5_problem3`、`5_problem4`、`6_check`、`7_evaluation`、以及由命令生成的 `page-map.json`、`formula-review.json` |
| `paper_appendix/` | 6 | 5 | **1**：`sections/A_appendix.tex` |

**图件零改动**：`figures/*.pdf` 与两个工程 `figures/` 副本的 sha256 **19/19 逐份相同、不一致 0 份**。`code/`、`results/`、`figures/`、`reports/` 中任何上游产物**均未修改**。

**页结构**：`_tmp/w10_pdf_textdiff.py` 实测（旧 32 页 vs 新 32 页）—— 全部小节标题的物理页**一处未动**（一→2、二→4、三→6、四→6、5.1→8、5.2→12、5.3→16、5.4→21、六→26、七→29、八→31、九→31），正文内只有**表 9** 从 {30,31} 收到 {30}（这正是 8.3 要的结果）；附录工程 9 页不变、逐页比对 8/9 页文本层逐字节相同，唯一差异页是表 A5 那一格。因而 `paper/page-map.json` 的区段声明（abstract 1 / body 2–30 / ai_statement 31 / appendix 32）**沿用不变**，只重绑了 PDF 哈希；`paper/formula-review.json` 的 23 条提示项**重测了物理页**（页内确有浮动体重排，不整体继承）。

### 8.5 本轮探针（`_tmp/`，保留不删，下一轮先原样重跑）

| 探针 | 用途 | 结果 |
|---|---|---|
| `w10_facts.py` → `.txt` | 6 条判词所依据的数值（附件 1 相邻差、$C_s-C_\infty$ 穿越、$n=320$ 环境三档、$h$ 减半、$C_0\pm1\%$） | 全部按现盘复算成立 |
| `w10_selfcheck.py` → `.txt` | ①引号 ②解释括号 ③「故」④harness 词 ⑤两份交付 PDF 文本层内部词 ⑥6 条判词的目标串（旧串消失/新串在）⑦残留 0.25/0.30 扫描 | 14 份 `.tex` 源码层 **0 命中**；两份 PDF 文本层**无内部词**；6 条判词的旧串**全部消失**、新串**全部在** |
| `w10_symbols.py` → `.txt` | 符号表闭环（表 1 每行 → 正文命中数） | 删除后表内无孤立行（剩余"未命中"提示是脚本分词器的假阳，已逐条用 `grep` 复核） |
| `w10_refs.py` → `.txt` | 参考文献闭环（8–12／被引／有条目／带 DOI） | 条目 12、闭环**合格** |
| `w10_pdf_textdiff.py` → `.txt` | 全文档文本层差分 ＋ 锚点页定位 | 见 8.4 |
| `w10_boundary.py` → `.txt` | 边界页归属（旧 vs 新，按 `boundary_top_ratio`） | 见 8.3 |
| `w10_formula_pages.py` → `.txt`/`.json` | 公式提示项的物理页重测（判别串从源码行现取、要求同页共现；先在旧 PDF 上自证） | 自证 18/20 复现（两处不符见 8.7），23 项现测页全部落位 |
| `w10_rebind_formula_review.py` | 重绑公式复核记录 | 23 项、20 项沿用原 decision/reason、3 项新写 |
| `w10_changeset.py` → `.txt` | 改动面逐文件哈希 | 见 8.4 |

### 8.6 编译与门禁自查（本阶段自己的四项门禁 + 驱动那两项）

| 检查 | 命令 | 结果 |
|---|---|---|
| 篇幅与摘要填充 | `python -m lib.publication report` | **PASS**；总计 32 页、计入 **30/30**、`over_limit=0`；摘要版心填充 **91.7%**（1099 字、`rows=0`）；`warnings`、`prose_issues` 均空 |
| 页映射绑定 | `python -m lib.publication map` / `check` | 已绑定当前 PDF（`164598bf…`），`check` **PASS** |
| 公式复核 | `paper/formula-review.json` | 23 条逐项 retain ＋ 理由 ＋ 物理页，绑定同一 PDF 哈希；`check` 无公式类 issue |
| 骨架对账 | `python lib/web/check_skeleton.py` | **通过** |
| 图件一致性 | `python -m lib.visualization audit` | **PASS** |

### 8.7 如实登记：本轮**未改**的遗留（附为什么不改）

1. **p31 页首仍有 2 行正文**（"…才用第四行。第五行依据自设参数区间下的两倍标准差…"）：边界判据是 14.9% ≤ 30%，**合规**；本轮已用去重把上一版的 10 行压到 2 行，再往下压要动 §7.3 方案查用表的用法段（决策卡的落地说明），代价大于收益，故登记不改。若 ⑭ 认为要零残留，可在排版层处理。
2. **`figures/manifest.json` 里 `caliber_sensitivity` 的注册图注仍写"环境延拓三档跨度 0.30 h"**（跨问建议 `adv-figregistry-env-span-030`，`report_wording` 类）：那是 $n=160$ 步进首达那组点与 $n=320$ 主档相减的值，与正文的 0.24 h 不同源。**交付 PDF 的文本层里不出现 0.30 h**（`_tmp/w10_selfcheck.py` 实测），且该注册件属 `figures/`（⑦/④ 的产物），本阶段不改他阶段产物；正文已按 8.1 第 ③ 项点明这批点的口径关系。
3. **`figures/make_figures.py` 的 `fig_q2_temp_field` docstring 与实装不符**（`RESULT_AUDIT_REPORT.md` §4.1）：函数内部 docstring，不进任何交付通道；改它要全量重渲并重签 13 张图的复核，代价远大于收益，不改。
4. **`reports/RESULTS_REPORT.md` 4 行 markdown 表被竖线劈开**（`RESULT_AUDIT_REPORT.md` §4.2）：属报告层呈现，不改论文，不改上游报告。
5. **`paper/formula-review.json` 两处旧登记页值不准**（本轮重测时发现）：`5_problem1.tex:19` 旧登记 4（实测该行在 **p8**）、`5_problem4.tex:63` 旧登记 **1**（实测在 **p23**）。本轮 23 项全部按当前 PDF 重测落页，两处已更正。
6. **`reports/PUBLICATION_CHECK.json` 是时刻快照**：上一轮那一版（0:07:16，status=FAIL、只差公式复核未重绑）已随本轮 `report` 全量重写；旧内容另存于提交件 `产物/提交作品/最新作品/其余文件/内部报告/PUBLICATION_CHECK.json`（7033 字节，未丢失）。本轮最终版绑定 `164598bf…`、status=PASS。

## 九、本轮重跑（2026-09-30 02:5x，第二次回退到 write）

### 9.0 为什么又有一轮：**触发信号是判据收紧，不是门禁回执**

`runtime/quality/feedback/2c23e64d/3cecb5db/gate_decision.json` 只有一条 `verdict_schema`
（`status=UNVERIFIED`、`reason=verdict_malformed`），按 [[verdict-malformed-round-policy]] 的口径它
**不含任何内容项**；`events.jsonl` 里 `mathproof` 那一轮是被用户**暂停强杀**的
（`01:55:15 mathproof stopped rc=1; stalled=True`），没有产出判词。随后驱动托管自动
`rollback → write`，把 `paper/` 与 `paper_appendix/` 整目录搬进
`产物/cache/2026A_2026.9.30_01.55.16/论文撰写/`。

真正的触发源在盘面上：`config/publication.json` 的 **mtime = 02:52:08**（`regression/` = 02:32），
其中新增了 `kind_start_markers` ＋ `boundary_top_tol = 6`（判据由「起始标记落在页面前 30%」
收紧为「该类别起始标记必须就是这一页最上面那块文字」）。**同一份 PDF、同一份 `page-map.json`**：
上一轮 `report` 判 PASS，本轮 `check` 判 FAIL。所以本轮不是"按回执改字"，而是
**按收紧后的判据把页面归属做实**。

### 9.1 起点：先把被搬走的那一版原样捞回来（不重写）

`产物/cache/2026A_2026.9.30_01.55.16/论文撰写/` 下同时有**工作副本**（`paper/`、`paper_appendix/`）
与 `快照/`。按 [[writing-reentry-mechanical-gates]] 的登记取**工作副本**（快照会回退掉别的会话已落地的版式改动）。
先与回退基准逐文件 sha256 对账，确认起点就是上一轮交付件（`paper/main.pdf = 164598bf…`）。

### 9.2 唯一的失败项与它的病灶（几何取证）

`python -m lib.publication check` 报 1 条：

> 第 31 页被声明为「八、…与九、参考文献」的起始页，但**上面还有文字**（页首块 y=70、该标记 y=126，差 55pt）。

`_tmp/w11_p3031_blocks.py` 逐块量得 p30 的版心：末段之前的最后一行底边 779.2pt，正文区实测最低底边
784.5pt（p11）⇒ **只剩约 5pt，装不下一行（19.8pt）**。漏到 p31 的两行是 §7.3 方案查用表用法段的
第 3、4 行（y=70.3 与 y=90.1，共 33pt）。所以要合规就必须让**表与用法段整体上移 2 行**。

### 9.3 处置一：§7.3 末尾去重（唯一一处正文改动）

原形态是 **1 行独立段落 ＋ 4 行用法段 = 5 行**：

```text
各节的数值汇总于表 9，每行只引用正文已给出的结果，不引入新结论。

表 9 的用法是按现场可得的信息选一行：只按名义条件排产取第一行；要留出余量时优先用第二行
收紧判据，它的代价最小；只有在扩散系数已另行标定、确认偏离名义值两成以上时才用第四行。
第五行依据自设参数区间下的两倍标准差，不是统计意义上的保证。无论选哪一行，都应带上约定
不确定度约 ±0.5 h。
```

压成 **3 行一段**，四层信息逐条保留、只删同义重复：

```text
表 9 汇总各节数值，只引用正文已给出的结果。用法是按现场可得信息选行：名义条件取第一行，
留余量取第二行，扩散系数另行标定后才取第四行；第五行由自设区间的两倍标准差给出，不是统计
保证。各行都要带约定不确定度约 ±0.5 h。
```

| 原句要素 | 处置 | 依据 |
|---|---|---|
| 「各节的数值汇总于表 9」 | 并入用法段首句（「表 9 汇总各节数值」） | 独立成段只占一行、无独立信息量 |
| 「每行只引用正文已给出的结果」 | **保留**（作「只引用正文已给出的结果」） | 决策卡的来源声明，SKILL 要求卡片只引用正文已给的数 |
| 「不引入新结论」 | 删 | 与上一句同义 |
| 「只按名义条件排产取第一行」 | 改为「名义条件取第一行」 | 同义压缩 |
| 「要留出余量时优先用第二行收紧判据，它的代价最小」 | 改为「留余量取第二行」 | 代价最小的论证已在 §6.2「留裕度与留参数的代价对比」给全 |
| 「只有在…确认偏离名义值两成以上时才用第四行」 | 改为「扩散系数另行标定后才取第四行」 | 同义压缩，档位量级在表内行标签「低于名义值 20%」已给 |
| 「第五行依据自设参数区间下的两倍标准差，不是统计意义上的保证」 | **保留**（作「第五行由自设区间的两倍标准差给出，不是统计保证」） | 与 `RESULT_AUDIT_REPORT.md` §5 的下游提示口径一致，**必须保留的披露** |
| 「无论选哪一行，都应带上约定不确定度约 ±0.5 h」 | **保留**（作「各行都要带约定不确定度约 ±0.5 h」） | 同上，属可执行结论的必要限定 |

**文字纪律复核**：新句无括号（唯一括号类内容是数值 `$\pm0.5$ h`）、无引号、无「故」、
括号内不出现「问题N」、段落不以判断句标签开头。

### 9.4 处置二：`paper/main.tex` 附录前补一行显式分页（像素中立）

正文收回 p30 之后，p31 上的九、参考文献整体上移 **52pt**（末条底边 648.3 → 596.2），
`\appendixAcn` **不强制分页**（`_base/macros.tex`）⇒ 附录与表 10 顺势挤进 p31
（实测：31 页、p31 上同时有「八、」「九、」「附录」）。

`config/publication.json` 的 `require_appendix = true` ＋ `kind_start_markers` 与
`docs/PUBLICATION.md` 的「附录单独起页、不限页」都要求附录自成一项；不修则要么
`appendix` 起始页对不上、要么这一页横跨两类。故在 `\appendixAcn` 前加 `\clearpage`，
并在原注释处写明为什么旧口径（「这里不加 `\clearpage`」）在此结构下不适用。

**该行是像素中立的**（不是推断，是实测）：`paper_appendix/` 的 29 份文件**逐字节相同**，
正文 p32 与回退归档那一版的 p32 **逐字节相同** —— 即这一行只把"本来恰好会换页"变成"确定换页"。

### 9.5 收口链（按 `writing-stage-closeout-chain` 的顺序，不跳步）

```text
① xelatex ×2（正文工程）           → rc=0、日志无 `!`、无 Overfull \vbox
② python -m lib.publication map   → 绑定当前 PDF（28e1ee70…），rc=0（新判据下**没有拒绑**）
③ python -m lib.publication report→ 拿到 23 条 formula_hints（此时仍 FAIL：公式复核未重绑，属正常步骤）
④ _tmp/w11_rebind_formula_review.py → 重绑 23 项（先在同一方法上做自证，见 9.6）
⑤ python -m lib.publication report → PASS
```

### 9.6 公式复核的**方法自证**（不是"沿用上一轮的页值"）

`_tmp/w11_rebind_formula_review.py` 的判别串**从源码那一行现取**（剥掉数学与 LaTeX 命令后取最长的
两个 CJK 串、要求同页共现）。自证分两步：

1. 在**上一轮交付件**（`paper/main.pdf = 164598bf…` 那一版）上跑同一方法 ⇒ 上一轮登记的 23 个物理页
   **23/23 全部复现**（命中集合都是单元素且等于登记值）；
2. 说明判别串本身是有分辨力的（不是"任何页都命中"）。

然后才在当前 PDF（`28e1ee70…`）上重测 —— 23 项的页值**与上一轮完全相同**（正文页结构未动，
见 9.7），`source_sha256` 逐项现算（两份 `.tex` 中只有 `7_evaluation.tex` 变了，而它不在提示项内），
`decision`/`reason` 对 23 条原样沿用（公式语义一字未改）。

### 9.7 改动面自证（`_tmp/w11_changeset.py` / `_tmp/w11_pagediff.py`）

与回退归档那一版逐文件 sha256：

| 工程 | 逐字节相同 | 变化 |
|---|---|---|
| `paper/`（44 份） | 38 | **6**：`sections/7_evaluation.tex`（正文改动）、`main.tex`（显式分页）、由命令生成的 `paper/main.pdf`、`page-map.json`、`formula-review.json`、`main.log` |
| `paper_appendix/`（29 份） | **29（全部）** | 0 |
| `figures/`、`code/`、`results/` | — | **0**（目录内最新 mtime 仍为 09-29 22:59 / 17:42 / 18:32，均早于本轮） |

逐页文本层差分（旧 32 页 vs 新 32 页）：

| 页 | 差分 |
|---|---|
| p1–p29 | **逐字节相同** |
| p30 | 777 字前缀相同 ＋ 2 字后缀相同；中段 225 字 → 227 字（用法段改写，表体与表题一字未动） |
| p31 | 前缀 0、**后缀 2329 字相同**；旧中段是那 66 字的两行漏文，新中段为空 |
| p32 | **逐字节相同** |
| 合计 | 逐字节相同页 **30 / 32** |

关键哈希（sha256 前 16 位）：`paper/main.pdf = 28e1ee707c29c04c`、
`paper/sections/7_evaluation.tex = 083d70136b6ddb97`、`paper/main.tex = 0c210aaba5fefde7`、
`paper/page-map.json = 9d0f75da144ad652`、`paper/formula-review.json = 9c51eade737eebd8`、
`reports/PUBLICATION_CHECK.json = 6e5cf8cf0ff88265`、`paper_appendix/main.pdf = 6196cb4b23aebfe9`。

### 9.8 门禁自查（本阶段四项 ＋ 驱动那项）

| 检查 | 命令 | 结果 |
|---|---|---|
| 骨架对账 | `python lib/web/check_skeleton.py` | **通过** |
| 篇幅与页边界 | `python -m lib.publication check` / `report` | **PASS**；32 页、计入 **30/30**、`over_limit=0`；`prose_issues` 空；三个类别起始页的标记差**全为 0.0pt**（容差 6pt） |
| 摘要版心填充 | `report` 的 `min_kind_fill` | **91.7%**（≥0.90；`rows=0`） |
| 图件一致性 | `python -m lib.visualization audit` | **PASS** |
| 图 ↔ 引用双向 | `_tmp/w11_figref.py` | 19/19 included 全部被引用、被引用的全部 included、两工程 `figures/` 副本与原件**不一致 0 份** |
| 源码/交付文本层自检 | `_tmp/w11_selfcheck.py` | 14 份 `.tex`：引号 0、解释型括号 0、「故」0、harness 词 0；两份交付 PDF 文本层**无内部词**；上一轮 6 条跨问判词的旧串全部消失、新串全部在 |

### 9.9 如实登记：本轮**未改**的遗留

1. **回执 `2c23e64d/3cecb5db` 只有 `verdict_schema` 一条**（`reason=verdict_malformed`）：
   它的 `fix` 明写"只补/改 `.verdict.json`，不要改动报告本体"，而那是 `mathproof` 自己的侧车件，
   **不属于本阶段产物** ⇒ 本轮 `not_applied`，理由登记在此。同目录下没有该轮的原始判词报告
   （那一轮被暂停强杀，`MATH_PROOF_REPORT.md` 未落盘），故无可作为定点返修依据的内容项。
2. **`figures/manifest.json` 的 `caliber_sensitivity` 注册图注仍写"环境延拓三档跨度 0.30 h"**：
   与第八节 8.7 第 2 条同一项，本轮复查**未变**（该文件 sha256 `374b0a6c11e87b88`、mtime 09-29 22:59）。
   它属 `figures/`（⑦/④ 的产物），本阶段不改他阶段产物；交付 PDF 文本层里不出现 0.30 h。
3. **`figures/make_figures.py` 的 `fig_q2_temp_field` docstring 与实装不符**、**`reports/RESULTS_REPORT.md`
   4 行 markdown 表被竖线劈开**：均为 `RESULT_AUDIT_REPORT.md` §4 已判**不拦链**的登记项，
   不改，理由同 8.7。
4. **p31 页首现在是「八、」（差 0.0pt）**，即本阶段的页归属已做实；若后续 ⑭ 改动版式
   使正文再长出一行，需要重跑 `map → report → formula-review → report` 这一条链
   （任何一次重编译都会同时作废 `page-map` 与 `formula-review` 的两处绑定）。

## 十、本轮收口（2026-09-30 16:5x＋，把两次被中断的重跑做完）

### 10.0 本轮是什么轮：没有回执，任务是把上一轮没做完的收口补完

| 项 | 事实 |
|---|---|
| 触发 | ⑯ 交互 Demo 超时转黄灯后，用户选择**回退到论文撰写**；`paper/` 与 `paper_appendix/` 连同下游报告被驱动整目录暂存进 `产物/cache/2026A_2026.9.30_16.31.44/论文撰写/` |
| 前两次 write 轮 | `16:31:45` 起一轮（写到 `16:43:18` 被用户停止）、`16:49:03` 起一轮（写到 `16:54:25` 被暂停、`16:54:31` 强杀）⇒ 两次都**未产出正式交付**，产物被再暂存进 `…16.49.02/`、`…16.58.01/` |
| 本轮的起点 | 把 `…16.58.01/论文撰写/` 那一份**原样捞回**（`paper/`、`paper_appendix/`），不从零重写 |
| 回执 | **无**：`runtime/quality/_pending_markers/write` 是**空目录**，`runtime/quality/feedback/` 下没有本轮 `run_id`（`fe3e4a89`）的目录，`reports/HIL_DECISION.md` 的「本轮返修轮次」为 `{}`。⇒ 本轮不是"按判词返修"，而是把我接手的这一版**按现盘逐项复核、补完收口** |

### 10.1 上一轮已落在盘上的改动面（本轮逐条复核，未回退）

| 文件 | 上一轮改了什么 | 本轮的复核 |
|---|---|---|
| `sections/2_analysis.tex` | 四问分析由 43 行压到 29 行 | **必须压**：`check_skeleton.py` 的「问题分析全节 ≤ 一页、每个问题的分析 ≤ 3 行」是硬约束。逐条核对**删掉的都是与 §5.1–§5.4 重复的段**：热/质特征时间 2368.9 s 与 81010 s、34 倍、表层约 3 mm、密度/比热/导热下降 31\%/47\%/46\%、热扩散率升 48\%、时间窗 144 倍、$D$ 净降 7.67 倍、平均值与表面点判据的后果、插值求根的理由、收缩的两个反向通道 —— 全部已在 `5_problem1.tex:19/21`、`5_problem2.tex:5/7/17`、`5_problem3.tex:5/9`、`5_problem4.tex:19` 内（`_tmp/w9r8_r4_diff.py` 逐行差分 + 逐串 grep） |
| `sections/4_symbols.tex` | 补 `$M_\varepsilon$` 一行 | 正确：§5.3 的行间推导用到它；`_tmp/vfy3_symbols.py` 复核它在表 1 且首次出现处就地定义 |
| `sections/5_problem2.tex:82`、`sections/A1_materials.tex:55–56` | 「与建模报告的登记值逐位一致」→「求解结果有三条可直接核对的特征」；「不改交付口径」→「不改最终结果」 | 正确：去掉指向内部产物的措辞（⑮ 的 advisory `internal-artifact-wording`）。本轮 grep 复核：正文已无「建模报告」字样 |
| `main.tex:68`、`sections/6_check.tex:23`、`sections/7_evaluation.tex:21` | 「这个预算比数值预算大 15 至 25 倍」→「参数取值的区间比…大 15 至 25 倍」 | 采纳：把**分子**写明是"参数取值的区间"，与 ⑮ 的 advisory `budget-ratio-upper-end`（分母 ±0.5 h、上下端不同源）相称；三个方向的数字（$-8.4$/$+12.7$ h、7.0/7.5 h 的联合标准差）一字未动 |
| `figures/`（19 张）与 `figures/manifest.json` | **重渲 + 重登记** | 见 10.2 第 1 条：定因是**并发会话改了像素产出模块**，重渲是规定的处置 |

### 10.2 本轮做的两件事

**处置一：补完 19 张图的视觉复核重签。** 上一轮"重登记"使 `signature(entry)` 改变 ⇒ 旧复核签名全部失效，
`python -m lib.visualization audit` 报 **19 条「缺少当前版本的视觉复核」**（注意：**不是**「已改变」，
即快照本身已对齐、只差目检签名）。按 SKILL「通用绘图协议」的"重新登记和目检；完成前运行 audit"办：

1. **先证画面零变化**（`_tmp/w9r6_figentry_diff.py`）：现盘 19 张 PNG 与旧副本
   `_tmp/w9_figbackup/figures/`（旧复核 note 被写下时的对象）**逐字节相同 19/19、不同 0**；
   19 条的 `claim/caption/width_mm/sources/script/artifacts/included/auto_issues` **八个登记字段逐项相同**，
   只有 `snapshot` 因重渲而变。PNG 是 matplotlib 唯一逐字节稳定的产物（PDF/SVG 带容器时间戳），
   与 [[fig-rerender-layer-separation]] 的口径一致。
2. **再逐张重签**（`_tmp/w9r7_resign_figs.py`）：走 `lib.visualization.evidence.review` 的库调用（与
   `python -m lib.visualization review` 同一条路径），带**前置守卫** —— 任何一张 PNG 与旧副本不同就整体拒签
   （不签没看过的图）。note 沿用旧目检结论并在尾部写明"本轮凭什么沿用"，另由本阶段重开交付 PNG 复核。
3. 结果：`python -m lib.visualization audit` ⇒ **PASS**（19/19，无其它条目）。

**处置二：附录工程去直角引号。** `_tmp/w10_selfcheck.py` 扫全部 14 份 `.tex`（两工程）报
`paper_appendix/sections/A_appendix.tex:18` 有 `「` 与 `」`；SKILL 的「全文不要引号」把
**直角引号 `「」『』` 明确列入**。改法是把演示工具在下界无解时显示的那行提示写成粗体
（`\textbf{窗内未达标}`），语义不变、只是把引号换成强调。重编译附录工程两遍：
**10 页不变**、`Output written on main.pdf (10 pages)`、日志无 `!`；
逐页文本层对账（`_tmp/w9rB_apx_text.py`）：**只有 p1 的哈希变**，p2–p10 **逐字节相同**。

### 10.3 数值面与交付面零变化的证据

| 面 | 证据 |
|---|---|
| `paper/` | **一个字节未改**（本轮只在 `paper_appendix/sections/A_appendix.tex` 改了一处措辞） |
| `paper/main.pdf` | sha256 仍 `a6843a1cc449b535`（未重编译）⇒ `paper/page-map.json` 与 `paper/formula-review.json` 的绑定**原样有效**（都绑这一份 PDF） |
| 结构化结果 | `python -m lib.result_contract export` 原样重跑：`paper/result-values.tex` 与 `.json` 内容**逐字节相同**（`508d70fd…` / `cd20cb82…`，只有 mtime 前进 —— 与 [[audit-cli-rewrites-validation-json]] 记的同一现象） |
| 结果契约 | `python -m lib.result_contract audit` ⇒ `[]` |
| 交付表 | `_tmp/w9_num_tables.py`：表 2–表 7 与 `results/result1–4.xlsx` **逐格 0 不一致**（表 6/表 7 的末行按登记的"连续达标时刻插值场"口径单独核对，`0.0525` 等逐格相符） |
| 图件副本 | `_tmp/w9rA_figcopy.py`：`paper/figures/` **19/19**、`paper_appendix/figures/` **19/19** 与项目根 `figures/` 同源（不一致 0）；`demo_shot.pdf` 是附录工程专有件 |

### 10.4 收口自查（本阶段四项机械门 ＋ 三条内容闭环）

| 检查 | 命令 / 探针 | 结果 |
|---|---|---|
| 骨架对账 | `python lib/web/check_skeleton.py` | **通过** |
| 篇幅与页边界 | `python -m lib.publication check` / `report` | **PASS**；31 页、计入 **29/30**、`over_limit=0`、`prose_issues` 空；四个类别起始页的标记差：`body` p2 差 0.0pt、`ai_statement` p30 差 0.0pt、`appendix` p31 差 0.0pt（容差 6pt） |
| 摘要版心填充 | `report` 的 `min_kind_fill` | **92.44\%**（1103 个非空白字符、`rows=0`；≥0.90） |
| 图件一致性 | `python -m lib.visualization audit` | **PASS**（19/19） |
| 文本自检 | `_tmp/w10_selfcheck.py` | 14 份 `.tex`：**引号 0、解释型括号 0、「故」0、harness 词 0**（改前是 2 处引号）；两份交付 PDF 文本层**无内部词**；上一轮 6 条跨问判词的旧串全部消失、新串全部在 |
| 符号表闭环 | `_tmp/vfy3_symbols.py` | `M_\varepsilon` 已在表 1；其余 8 条是脚本抽取式的假阳（裸字母在表内为 True） |
| 参考文献闭环 | `_tmp/w10_refs.py` | **条目 12**（8–12 内）、12 条全被 `\cite`、正文无表外引用、**每条带 DOI** |
| 结论数字加粗（渲染级） | `_tmp/w9rF_boldprobe.py`（按 `Span.font` 认粗体） | 摘要 p1 四问结论值各 ≥1 处、§5.1 p11、§5.2 p13、§5.3 p17/p18、§5.4 p22/p23 各自的结论值都在粗体 span 内（`TimesNewRomanPS-BoldMT`） |
| 数值出处扫 | `_tmp/w9_num_prose.py` | 1534 个字面量；"完全找不到登记来源"仅 3 个，逐个查清见 10.6 第 8 条 |
| 页边界归属（精确值） | `_tmp/w9rG_boundary.py` | `body` p2 / `ai_statement` p30 / `appendix` p31 的标记差**全为 0.0pt**（容差 6pt）；`abstract` p1 按判据不判 |

**本轮收尾哈希**（sha256 前 16 位）：`paper/main.pdf = a6843a1cc449b535`（未重编译）、
`paper_appendix/main.pdf = bbb6ae3fb997182a`、`paper/page-map.json = fdcdda4c6ecb7215`、
`paper/formula-review.json = f1560bddeff4f8e7`、`figures/manifest.json = ea420d0faedb9a09`（19 条复核重签后）、
`reports/PUBLICATION_CHECK.json = 7bd540a1e30a5415`、`paper_appendix/sections/A_appendix.tex = 8161cf80f111ef83`。

### 10.5 篇幅：计入 29/30 的成因与判断（**为什么不补写**）

实测（`_tmp/w9r9_pagefill.py`，已剔除页脚）：正文工程 **31 页** = 摘要 1（p1）＋ 正文 **28**（p2–p29）＋
八/九 1（p30）＋ 附录 1（p31）；`counted_pages = 29`。**成因**：§2 由 43 行压到 29 行使正文少了一页
（这次压缩是 `check_skeleton` 的硬约束要求的，见 10.1 第 1 行；删掉的内容都在 §5/§6）。

**判断：不补写。** 三条理由：

1. **硬线已满足**：`config/publication.json` 是 `max_counted_pages = 30`、`min_counted_pages = 25`，
   29 在区间内、`over_limit = 0`、`above_target = 0`（`report` 对"低于目标"只登记不判死）。
2. **评分标的篇幅口径也在区间内**：四份评分标的对应条目写的是「正文（一～七）25–30 页为理想、
   不超过 30 页」（`skills/12Rubric-final/references/rubric_*.md`），本稿正文 **28 页**落在理想区间上端。
3. **补的只能是水**：SKILL 说"若实在写不满，在 `WRITING_PLAN` 里写明为什么……不要靠排版花活填"。
   本轮把四问的建模过程、求解细节、结果分析、对照与检验、失败结果与局限逐节读过一遍，
   **找不到可补的论证缺口** —— 再写只能是重复或拆句。
   **另有一条算术上的判别**：p29 正文止于 **y=600.1**、实测版心底 **778.9** ⇒ 底部空 **178.8pt ≈ 9 行**（行距 19.9pt）；
   而"再长出一个正文页"至少要跨页多排 10 行以上 ⇒ 补 9 行以内**页数一点不变**（只把 p29 填实），
   补得更多又必然挤动 p30/p31 的类属。既然页数上界只有 30、且当前在理想区间内，
   为"顶格"去写非必要内容，收益为零、风险为正，故不做。

### 10.6 如实登记：本轮**未改**的遗留（附为什么不改）

1. **`figures/manifest.json` 里 `caliber_sensitivity` 的注册图注仍写"环境延拓三档跨度 0.30 h"**
   （承 8.7-②、9.9-②）：那是 $n=160$ 步进首达那组点与 $n=320$ 主档相减的值，与正文的 0.24 h 不同源。
   它属 `figures/`（⑦/④ 的产物），本阶段不改他阶段产物；交付 PDF 文本层里不出现 `0.30`。
2. **`figures/make_figures.py` 的 `fig_q2_temp_field` docstring 与实装不符**（`RESULT_AUDIT_REPORT.md` §4.1）：
   函数内部 docstring，不进 `manifest.json`、不进论文图注、不被任何程序读取；改它要**全量重渲并重签 19 张图的复核**，
   代价远大于收益，不改。
3. **`reports/RESULTS_REPORT.md` 4 行 markdown 表被单元格里的竖线劈开**（§4.2）：报告层呈现，
   不改变任何数值与结论，不改论文、不改上游报告。
4. **⑮ 验收的 9 条 advisory 的处置**（`产物/cache/2026A_2026.9.30_16.31.44/验收/VERIFY_REPORT.verdict.json`，
   该轮 `PASS`、无 issues）：`ref15-subtitle` 与 `internal-artifact-wording` **已由前轮落地**
   （本轮复核：`references.tex` 的 ref15 题名已是 Crossref 的真实题名；正文已无「建模报告」字样）；
   `table-A5-pm-direction` 按本项目既有惯例记 advisory（上游两种写法并存）；
   `symbol-table-missing-M-epsilon` 已由 10.1 的 `4_symbols.tex` 改动解决；
   其余 4 条属 `presentation` / `report_wording` 类，归 ⑭ 排版侧与上游报告，本阶段不改。
5. **图件复核重签的时效性**：任何一次重渲、或共享库/`config/visualization.json` 再变一次，
   19 张的签名即失效（`audit` 会再报「缺少当前版本的视觉复核」）。本轮在签名后**立刻**跑了 `audit` 复核（PASS）；
   若下游发现盘面被再次改动，按 [[concurrent-session-shared-lib-race]] 的"先核哈希再信结论"重跑收口。
6. **`reports/HIL_DECISION.md`** 是 `16:54` 那次暂停留下的清单（「本轮返修轮次：{}」），不是本阶段产物；
   驱动会按需重写，本轮不动。
7. **正文里「口径」一词出现 18 处**：逐处看过，都作"计算约定 / 定义 / 判据约定"义
   （如"口径唯一"、"同一口径"、"不是同一口径"），属数学建模的常规用语，不是流水线词，故保留。
8. **数值出处扫的 3 个"找不到登记来源"字面量，逐个查清**（`_tmp/w9_num_prose.py`）：
   - `22.2`（摘要与 `5_problem2.tex:96`）：来自 `code/outputs/figdata_q2.npz` 现算的 $C_s-C_\infty$
     首次 $<0.02$ 且此后保持的时刻（22.1517 h）；该探针的来源池不含 `.npz`，是**探针口径**而非缺出处
     （[[content-quality-contract-quotes]] 同族的"来源池命中只是必要不充分"）。
   - `58.6` 与 `52.5`（表 8 第 3、4 行）：都是**正文已给数值的和**——
     58.6 = 57.1 + 1.45（`ROBUSTNESS_REPORT.md:253` 的 Q3 阈值收紧 1\\% 代价 +1.45 h），
     52.5 = 50.8 + 1.68（`ROBUSTNESS_REPORT.md:200` 的 Q4 环境温度 $-1$ °C 通道 $+1.68$ h）
     ⇒ 逐字搜索找不到、按式相加对得上，符合"表 8 只引用正文已给出的结果"的定位。
   另：表 8 末行的 71 / 67 = 联合抽样均值 + 2σ（57.15+2×6.98、52.20+2×7.54），
   与 `ROBUSTNESS_REPORT.md:292` 的**均值口径**一致（**不是**用主档点值 50.8 加 15 h，见 ⑮ 的
   `advice-time-2sigma-arithmetic`）。

### 10.7 本轮探针（`_tmp/`，**保留不删**；下一轮开工先原样重跑）

| 探针 / 输出 | 用途 |
|---|---|
| `w9r5_reviewstate.py` | 现盘 manifest 与旧副本的逐张 reviewer/note 对照 |
| `w9r6_figentry_diff.py` | ① PNG 逐字节对账 ② 八个登记字段逐条对账 ③ `auto_issues` 现状 |
| `w9r7_resign_figs.py` | 19 张重签（带"PNG 不同就拒签"的前置守卫） |
| `w9r8_r4_diff.py` → `.out` | 现盘 `paper/` 与 `16:31:44` 回退归档版的逐文件行级 diff |
| `w9r9_pagefill.py` | 逐页版心填充（**已剔除页脚块**，否则末块恒为页码） |
| `w9rA_figcopy.py` | 两个工程 `figures/` 副本与根目录的同源性 |
| `w9rB_apx_text.py` → `_before/_after.json` | 附录 PDF 的逐页文本层快照（改前 / 改后） |
| `w9rD_numprose.out`、`w9rE_sens.txt` | 数值出处扫（原样重跑）；`sensitivity.json` 的结构与通道 |
| `w9rF_boldprobe.py` | 结论数字加粗的渲染级复核（按 `Span.font` 认粗体） |

**旧探针的维护**：
- 上一轮 `_tmp/w9_text_selfcheck.py` 的 `HARNESS` 词表含「口径」，命中 18 处属**词表口径问题**
  （见 10.6 第 7 条）；本轮改用 `_tmp/w10_selfcheck.py`（其词表不含「口径」）作为主判据。
- `_tmp/w10_selfcheck.py` 的 ⑥ 段里 `（"③ 新 0.24 跨度（假设三）", ["达标时刻的跨度为0.24h"]）`
  是一条**过时期望**：该措辞属第八节那一版的假设三，其后 13Repair 轮按"敏感性数字不进假设节"
  把假设三改回了环境延拓的表述 ⇒ 现稿报"**不在**"是**正确状态**，不是缺项。
  同一段其余期望串（含 `WANT_APP` 内部）本轮实测全部命中。

---

## 十一、本轮重入（2026-09-30 17:1x＋，第三次被中断后的重跑）：零改动面的全量复核

### 11.0 本轮是什么轮：没有回执，改动面为零，任务是把"这一版还成不成立"重新证一遍

| 项 | 事实 |
|---|---|
| 触发 | 第十节那一轮在 `17:15:45` 被用户停止（`write 被用户停止，已强杀进程树`），驱动把 `paper/`、`paper_appendix/` 整目录暂存进 `产物/cache/2026A_2026.9.30_17.15.47/论文撰写/`，随后 `17:18:31` 又暂存一次进 `…17.18.31/论文撰写/` |
| 本轮起点 | 把 `…17.18.31/论文撰写/{paper,paper_appendix}` **原样捞回**，不从零重写 |
| 回执 | **无**：`runtime/quality/_pending_markers/write` 是**空目录**（0 个子项）、`reports/HIL_DECISION.md` 的「本轮返修轮次」为 `{}`、`runtime/quality/feedback/` 下没有本轮 `run_id` 的目录 ⇒ 本轮不是"按判词返修"，而是**复核并交付我接手的这一版** |
| 改动面 | **零**（见 11.2 的逐字节自证）；本轮的全部工作都是**取证**，不是编辑 |

### 11.1 起点自证：捞回来的这一份与回退归档那一份**逐字节相同**

`_tmp/w9s6_restore_identity.py` 对 `paper/` 与 `paper_appendix/` 做**全文件** sha256 对账（含 PDF、PNG、JSON，
不是只比 `.tex`）：**paper 50/50 同、paper_appendix 31/31 同，异 0、缺 0、多 0** ⇒
本轮的起点就是第十节收尾时那一版，没有在搬运中走样。
存量探针 `_tmp/w9s1_draft_diff.py` 原样重跑的结果与之相符：对 `…17.15.47` 快照 **改过 0 / 新增 0 / 消失 0**。

### 11.2 改动面为零的哈希自证（与第十节收尾哈希逐位相同）

| 文件 | sha256（前 16 位） | 与 10.3 收尾表比 |
|---|---|---|
| `paper/main.pdf` | `a6843a1cc449b535` | **相同**（未重编译） |
| `paper_appendix/main.pdf` | `bbb6ae3fb997182a` | **相同** |
| `paper/page-map.json` | `fdcdda4c6ecb7215` | **相同**（绑定仍有效） |
| `paper/formula-review.json` | `f1560bddeff4f8e7` | **相同** |
| `figures/manifest.json` | `ea420d0faedb9a09` | **相同** |
| `reports/PUBLICATION_CHECK.json` | `7bd540a1e30a5415` | **相同** |
| `paper_appendix/sections/A_appendix.tex` | `8161cf80f111ef83` | **相同** |
| `paper/sections/3_assumptions.tex` | `7583163b108a1795` | —— |
| `paper/sections/2_analysis.tex` | `cbc7b17505b07a95` | —— |
| `paper/main.tex` | `22612137cb3d0c27` | —— |

**一处如实登记的副作用**：本轮按 SKILL 跑了 `python -m lib.publication report`，它会重写
`reports/PUBLICATION_CHECK.json` ⇒ **mtime 前进**，但该文件 sha256 仍是 `7bd540a1e30a5415`、
**内容逐字节未变**（与 [[audit-cli-rewrites-validation-json]] 记的同一现象，登记以备下轮不误判）。

### 11.3 独立复算：不承继任何前轮结论，按现盘自己重做一遍

**（1）四张结果表逐格对账 216 格，0 不一致**（`_tmp/w9s5_tables_full.py`）。审计报告已做过同类对账，
但它不是本轮做的 ⇒ 本轮**自己按表源串重新抽格**，对象是当前盘面上的四个交付件：

| 表 | 对象 | 格数 | 结果 |
|---|---|---|---|
| 表 2 / 表 3 | `results/result1.xlsx` 的**温度** / **水分浓度**两个工作表，7 时刻 × 0/0.5/1.0/1.5/2.0 cm | 70 | 0 不一致 |
| 表 4 / 表 5 | `results/result2.xlsx` 的**温度** / **水分浓度**两个工作表，6 时刻 × 同上 5 列 | 60 | 0 不一致 |
| 表 6 | `results/q3.json :: table5`（10 行 × 5 列，含「烘干结束时间」末行） | 50 | 0 不一致 |
| 表 7 | `results/q4.json :: table6`（9 行 × 4 列，末列为药材表面） | 36 | 0 不一致 |

抽检的首行末行都对上：表 2 末行 $t=1800$ s 的 `33.5765 … 36.7863`、表 3 末行的 `2.5500 … 1.5103`、
表 6 末行 `0.1500 0.1477 0.1402 0.1249 0.0525`、表 7 末行 `0.1500 0.1413 0.1081 0.0525`。
另外抽验 `result4.xlsx` 的**末列**表头确实是「药材表面」、末行时间 `183000` s 是 60 s 的整数倍、
末行末格 `0.0525` 有值 ⇒ §5.4 与表 6/表 7 表注里"移动表面是末列、末行是该档 60 s 网格点上的剖面"
这套说法与交付文件的实际结构一致。

**（2）`RESULT_AUDIT_REPORT.md` §5 的「给下游的三条口径，引用时必须带」逐条核**（这是唯一的写作侧指令面）：

| 口径 | 论文落地处 | 判定 |
|---|---|---|
| ① $+5.150\times10^{-7}$ 的口径是 $t_{\rm dry}-1.7554$ s（$\Delta t=1$ s 网格 2 步之前，$t=205\,696$ s），**别**与 $t_{\rm dry}-60$ s 的 $+1.754\times10^{-5}$ 配成一对 | `5_problem3.tex:52` 明写「前者的口径是 $t=205\,697$ s、即达标时刻前 $0.7554$ s，后者的口径是 $t=205\,696$ s、即达标时刻前 $1.7554$ s，两处都按 $\Delta t=1$ s 的网格给出」 | **合规**，且那两个数没有被配成一对 |
| ② Q3 用**连续根** 57.1383 h、Q4 用**步进首达** 50.8333 h（`q4_shrinkage` 的 50.8225 h 是连续根口径） | 摘要 `main.tex:64/66` 同时给出 50.8333 h 与 50.8225 h 并注明后者是连续根；§5.3 给 57.1383 h | **合规** |
| ③ 显示 `0.1500` 的格一律按未舍入值判定；引用 $t\lesssim1500$ s 的行（尤其水分表面列）不能按 $t=1800$ s 那一档的精度读 | `5_problem3.tex:7`、`5_problem3.tex:80`、`5_problem4.tex:99` 三处写"未舍入数组为准"；`6_check.tex:7` 整段「早期时刻要另给一档」给 $t=100$ s 口径 | **合规** |

**（3）`verify` 回执两条 `must` 的落地复核**（回执见 `events.jsonl` 的 `run_id=0ed9200d`）：
`q1-loss-third-caliber-label-mismatch` ⇒ 现稿 `5_problem1.tex:134` 已写作「按 $0/0.5/1.0/1.5/2.0$ cm **五点的粗梯形求积**得 12.88\%」，
与 `results/q1.json` 登记的第三口径同名，同句的 8.34\% 与 10.06\% 未被动过；
`q2-convergence-subject-misattribution` ⇒ 现稿 `5_problem2.tex:82` 写作「**水分场**在 72 h 末的场级网格收敛量为 $2.4\times10^{-4}$（全场最大变化），
其中量级更小的表面格为 $4.2\times10^{-6}$ kg/kg」，主语已收成单一对象。

**（4）`cross` 回执三条 `must` 的落地复核**：表 A5 的换热系数行现为 `$-0.013/+0.020$` 与 `$-0.012/+0.018$`（两侧并列，
不再是单向值）；`6_check.tex:29` 的环境抖动句已把两个量各自标明所属问；`5_problem4.tex:99` 已改写成"末列是移动表面值"。

### 11.4 收口自查（本阶段四项机械门 ＋ 三条内容闭环 ＋ 页边界/填充）

| 检查 | 命令 / 探针 | 结果 |
|---|---|---|
| 骨架对账 | `python lib/web/check_skeleton.py` | **通过**（exit 0） |
| 篇幅与页边界 | `python -m lib.publication check` / `report` | **PASS**；31 页、计入 **29/30**、`over_limit=0`、`above_target=0`、`prose_issues` 空 |
| 摘要版心填充 | `report` 的 `min_kind_fill` | **92.44\%**（1103 个非空白字符、`rows=0`；≥0.90、硬线 0.80） |
| 图件一致性 | `python -m lib.visualization audit` | **PASS**（19/19，无其它条目） |
| 结果契约 | `python -m lib.result_contract audit` ⇒ `[]`；`export` 原样重跑，`paper/result-values.tex` 逐字节不变 | **通过** |
| 文本自检 | `_tmp/w10_selfcheck.py` 原样重跑 | 14 份 `.tex`：**引号 0、解释型括号 0、「故」0、harness 词 0**；`paper/main.pdf` 与 `paper_appendix/main.pdf` 的**文本层**（含图内文字）**内部词 0 命中** |
| 假设节 K2 | `_tmp/w9s3_layout_probe.py`（**先按文本层定位该节所在页**） | 假设一～五**各恰 2 行**、条数 **5**、节内「放宽后」**0** 命中 |
| 页边界归属 | `_tmp/w9rG_boundary.py` | `body` p2 / `ai_statement` p30 / `appendix` p31 的起始标记差**全为 0.0pt**（容差 6pt） |
| 正文末页填充 | `_tmp/w9r9_pagefill.py` | p29 末块底边 **600.1**、版心底 778.9 ⇒ 底部空 **178.8pt ≈ 9 行**（与 10.5 同） |
| 参考文献闭环 | `_tmp/w10_refs.py` | **12 条**（8–12 内）、12 条全被 `\cite`、正文无表外引用、**每条带 DOI / 链接** |
| 摘要关键词 | `_tmp/w9s3_layout_probe.py` | **5 个**（≤6），全部为本题特有短语 |
| 图 1 位置与栏宽 | `1_restatement.tex:21` | `\paperfigure[0.85\textwidth]{fig_roadmap}{分析流程图}{fig_roadmap}`，排在「问题提出」之后、第二节之前，落在交付 PDF **p3** |
| 图件副本同源 | 全文件 sha256 对账 | `paper/figures` 与 `paper_appendix/figures` 共 **40 份**，与项目根 `figures/` 同源；仅 `paper_appendix/figures/demo_shot.{pdf,png}` 是附录专有件（被 `A_appendix.tex:4` 引为**图 A1 交互式网页首屏**，非数据图，故不在 `manifest.json` 内） |
| 附录工程 | `paper_appendix/main.pdf` | **10 页**（`Output written on main.pdf (10 pages)`），日志无 `!` |

### 11.5 本轮**修好的是探针，不是论文**：两处探针缺陷（防下轮踩同一个坑）

1. **`_tmp/fix13r2_k2_linecount2.py` 的页码写死，已经静默失效**（真·假通过）。
   它把「三、模型假设」所在的页写死成 `PAGE = 6`；而正文经 §2 压缩后该节**已上移到第 5 页** ⇒
   它在第 6 页一条「假设X：」都没收到，却照样打印「判据 K2：每条 1.5–2 行 ⇒ 超 2 行的条数 = **0**」——
   **看着像合格，其实是判据一次都没跑**（[[self-check-scope-and-silent-skip]] 的同一族）。
   本轮改用 `_tmp/w9s3_layout_probe.py`：**先按文本层找该节所在页**，再数行，并在"一条都没收到"时
   显式打出「判据未执行（禁止把这种情况当通过）」。实测该节在 **p5**、五条**各 2 行** ⇒ 合格是**真的**。
   旧探针**保留不删**（按纪律），但下一轮**不要**再拿它的输出当 K2 判据。
2. **本轮自写探针的第一版把水分表当成了温度表**（已修，登记以备后人）。
   `results/result1.xlsx` / `result2.xlsx` 是**双工作表**（`温度` / `水分浓度`），第一版只取了 `sheetnames[0]`，
   于是表 3 与表 5 被拿去和温度列比 ⇒ 报出 65 处"不一致"（例：`2.5500(交付=28.0001)`）。
   **这是探针取错了参照面，不是论文错**；`_tmp/w9s5_tables_full.py` 按工作表分别取（温度用第 0 张、
   水分浓度用第 1 张）后为 **216 格 0 不一致**。

### 11.6 如实登记：本轮**未改**的遗留（承 10.6，逐条复核后结论不变）

1. `figures/manifest.json` 里 `caliber_sensitivity` 的注册图注仍写"环境延拓三档跨度 0.30 h"（$n=160$ 步进口径，
   与正文 0.24 h 不同源）。属 `figures/` 的产物，本阶段不改；交付 PDF 文本层不出现 `0.30`。
2. `figures/make_figures.py` 的 `fig_q2_temp_field` docstring 与实装不符（审计 §4.1）。函数内部注释，
   不进 `manifest.json`、不进图注、不被程序读取；改它要全量重渲并重签 19 张图，代价大于收益。
3. `reports/RESULTS_REPORT.md` 有 4 行 markdown 表被单元格里的竖线劈开（审计 §4.2）。报告层呈现，
   不改数值与结论，不改论文。
4. 正文「口径」一词 18 处，都作"计算约定 / 定义 / 判据约定"义，属数学建模常规用语，保留。
5. 篇幅仍是**计入 29/30**。成因与判断同 10.5（§2 按 `check_skeleton` 硬约束压缩后正文 28 页），
   本轮复核后**结论不变：不补写** —— 正文末页只空 9 行，补 9 行以内页数一点不变、补更多必挤动 p30/p31 的类属；
   在硬线 ≤30 且评分标"25–30 页为理想"的口径下，为顶格而写非必要内容收益为零、风险为正。

### 11.7 本轮探针（`_tmp/`，**保留不删**；下一轮开工先原样重跑）

| 探针 / 输出 | 用途 |
|---|---|
| `w9s6_restore_identity.py` → `.txt` | 捞回来的 `paper/`＋`paper_appendix/` 与回退归档版**逐文件 sha256 全等**（81 份、异 0） |
| `w9s1_draft_diff.py` → `.txt` | 存量探针原样重跑：四个候选快照的逐文件/逐行差分 |
| `w9s2_auditcheck.py` → `.txt` | 审计与前序回执点名的**写作侧落地项**分组扫（A–J 十组） |
| `w9s3_layout_probe.py` → `.txt` | 假设节行数（**先定位页码**）＋ 摘要关键词 ＋ 图题/表题 span 清单 |
| `w9s4_table_crosscheck.py` → `.txt` | 表格抽检第一版（**含已知的 sheet 取值缺陷**，见 11.5-2，留作负面对照） |
| `w9s5_tables_full.py` → `.txt` | 四张结果表与交付件**逐格 216 格**对账（工作簿双表分别取） |

**旧探针的维护**：`_tmp/fix13r2_k2_linecount2.py` 的 `PAGE = 6` 已失效（见 11.5-1），
下一轮**先改页码或直接用 `w9s3_layout_probe.py`**，不要照抄它的"0 超行"当结论。
