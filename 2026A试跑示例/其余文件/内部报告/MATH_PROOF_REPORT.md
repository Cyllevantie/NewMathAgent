# 数学论证门禁报告

本阶段为**只审不改**：未修改 `paper/`、`paper_appendix/`、`figures/`、`results/`、`code/` 与任何上游报告，也未向建模报告追加任何标记。全部判定对着**当前盘面**（现版本的 `paper/**`、`paper_appendix/**`、`figures/make_figures.py` 与 `figures/manifest.json`、`results/*.json`、`tmp/rob/out/*.json`、`code/outputs/*.npz`，以及交付 `paper/main.pdf` 与 `paper_appendix/main.pdf` 的文本层）逐条做；取证脚本一律只读、全部留在 `_tmp/`（含上一轮探针的**原样重跑**）。

## 门禁结论

本阶段的入参回执是上一轮自己被驱动打回的那份（`runtime/quality/feedback/2c23e64d/3cecb5db/gate_decision.json`，`reason=verdict_malformed`，唯一一条是侧车 schema 问题，没有实质判词），因此本轮按纪律**对现盘重做实质审计**，而不是照抄上一轮。

本轮为**第 5 轮增量审计**。改动面（对上一版被完整审过的快照 `产物/cache/2026A_2026.9.30_01.16.54/论文撰写/` 逐文件 sha256 + 逐行 diff，见 `_tmp/mp5_diff.txt`）只落在 11 份文本的 20 余处句子，**没有一处改方程、改实现或改交付数值**。逐条复量后：

- 摘要的阈值穿越时刻、`§5.1` 的六成五与场跨 2.45、`§5.2` 的最大升幅/最大回落与护栏口径句、`§5.3` 的环境延拓读数与跨度、`h` 减半的位移、表末行的说明、表 A5 的问题四格、`§6.2` 与图件的口径关系句 —— **每一处都能指认到唯一一份产物字段，且与该字段逐位相符**；
- 唯一的带标签命题（问题三「最坏点归约到轴心」）与其附录推导 **本轮零改动**，仍带完整等式级推导、显式前提与余项界；两个只读复核员（其一独立重推命题、其二逐条复量改动面）与本阶段自算三方**均无反例、无缺前提**；
- 交付 PDF 文本层复核：本轮新串**全部在**，被替换掉的旧串（「24 h 后」「六成」「单步最大回落 0.797」「0.03 h」「56.9667 与 56.8500」）**均已不出现**；两张交付 PDF 与工作区逐字节相同（`正文 28e1ee70…`、`附录 6196cb4b…`）。

故判 **APPROVED**：无未解决项。另有四条不影响交付的登记级建议（表 A5 的方向记号、预算合成方式与同句口径混用、图件注册图注落后于正文口径、末页占位表），写在侧车 `advisories` 与本文「未纳入项」里；其中第一条是本阶段**唯一**保留的意见，理由与可核判据见断言清单 27。

## 扫描范围

- 只读源码：`paper/main.tex`、`paper/sections/*.tex`（11 份）、`paper_appendix/main.tex`、`paper_appendix/sections/A_appendix.tex`、`paper/_base/*.tex`（用于确认图题来源）。交叉对读：`reports/RESULTS_REPORT.md`、`reports/ROBUSTNESS_REPORT.md`、`reports/ANALYSIS_MODELING_REPORT.md`、`reports/EDITORIAL_CHANGES.md`、`results/*.json`、`tmp/rob/out/cal_env_*_n320.json`、`code/outputs/q2.npz`、`figures/make_figures.py`、`figures/manifest.json`。
- **标签词扫描**（`定理|命题|引理|推论|性质|证明|证毕`）命中三类：真命题 1 条（`5_problem3.tex` 的「命题：」）＋「证明要点」1 处＋附录 A.1「命题的完整推导」1 节；其余为「结构性性质」「使用边界」「解的性质」等非标签用法（不判）。
- **强解析声称扫描**（`证明了|已证|严格相同|严格一致|严格等价|恒成立|恒等|精确成立|正交|无偏|严格单调|严格解耦|解析解|闭式解|二阶精度|无条件稳定`）归并后仍是**第 1 轮登记的那 23 条**（A 类命题 1 条、B 类强声称 22 条）；本轮对**改动面命中的 9 条**与**上轮 flagged 的 10 条所在小节**逐条重判，其余按「未改动不再整条重推」处理并注明。
- **C 类（不判）**：各表的数值本身（属 `results/` 登记值，已由上游审计与图件门禁核过）；`5_problem4.tex` 的材料坐标与 $v_s$ 定义；`4_symbols.tex` 的符号定义；附录 3/4 的物性经验式复述。
- 本阶段必查四项 `proof_validity` / `proof_applicability` / `optimality` / `narrative_consistency` 全部给出结论与逐条 `evidence` 锚点（引文均为项目内文本文件的**原样切片**，落盘前由生成脚本逐条做过「逐字存在」断言）。

## 断言清单（本轮重判部分）

| # | 位置(文件:行) | 原句摘录 | 类型 | 推导? | 前提显式? | 余项界? | 独立复推 | 处置 |
|---|--------------|---------|------|-------|----------|--------|---------|------|
| 1 | `paper/sections/5_problem3.tex:15-27`；`paper_appendix/sections/A_appendix.tex:1-50` | 命题：…则 $C(\cdot,t)$ 关于 $r$ 单调不增，特别地 $\max_{0\le r\le R}C(r,t)=C(0,t)$ | A 命题 | 有（通量方程＋极值原理＋扰动＋内区范数＋极限顺序） | 显式（P1/P2/P3 写在命题里；轴心项界、角点零阶不相容、λ 实测值都写明） | 有（$O(\varepsilon^2)$ 与内区范数 $M_\varepsilon$） | **支持**（复核员独立重推：$q_t=Dq_{rr}-\frac Drq_r+cq$ 逐项一致；扰动项的算子严格负那一支复算为 $\varepsilon_0((c-\lambda)t-1)$，与论文逐项相同；**确实不需要 $D$ 的二阶导数符号条件**；三段极限无循环；把 $C_\infty$ 置 3.0 的对抗算例确实推翻结论 ⇒ P2 是承重前提而非免检） | OK |
| 1P | `paper_appendix/sections/A_appendix.tex:43-45`（表 A1）＋`5_problem3.tex:27` | 三条前提的实测量：$D\in[2.6\times10^{-12},1.3\times10^{-8}]$；出流裕度最小值 $1.76\times10^{-3}$ kg/kg；$\lambda\approx1.9\times10^{-4}$ s$^{-1}$ | B 数值型 | — | 前提逐条给量 | — | **支持**（复核员从 `q2.npz`/`q4.npz` 的 145 张全场快照独立算：$D\in[2.648\times10^{-12},1.252\times10^{-8}]$；裕度 $1.76299\times10^{-3}$ / $1.25784\times10^{-3}$，逐点无一为负；$\lambda$ 为 $1.93\sim2.07\times10^{-4}$） | OK |
| 3 | `paper/sections/5_problem1.tex:5`；`2_analysis.tex:7` | 两个场严格解耦 | B 强声称 | 直接由参数集可见 | 显式 | 不适用 | **上轮结论继续有效**（所在小节本轮零改动；且 §6.2 的「只扰动一侧时另一场逐位不变」把它做成了数值强结论） | OK |
| 11 | `paper/sections/5_problem1.tex:124` | 水分侧在 $t=1800$ s 的偏差为 $1.13\times10^{-4}$ kg/kg，对应场跨 2.45 kg/kg | B 数值型 | — | 口径写明（只作校核、不作离散精度的界） | — | **支持**（原样重跑上一轮探针：同一实装的级数式在 $\mathrm{Fo}=0.0222194$ 上给场跨 $2.449938$ kg/kg，四舍五入即 2.45；旧值 2.40 已不在交付件里） | OK |
| 13 | `paper/sections/5_problem2.tex:82` | 护栏判据取亏量 $\max_rC-C(0,t)$ 超过 $10^{-10}C(0,t)$ 才算一次违约，259200 步中违约次数为 0；原始布尔口径下有 478 步被判偏离，最大亏量 $9.3\times10^{-15}$ | B 数值型 | — | **本轮已把护栏口径与门限写进同句** | — | **支持**（原样重跑探针：`results/q2.json` 的 `argmax_raw_deviations=478`、`guarded_violations=0`、`max_deficit=9.326e-15`；三个字段与句子的口径一一对应；复核员另从 `q2.npz` 的 `mon_maxC/mon_C0` 独立算出同三个数） | OK |
| 18 | `paper/sections/5_problem1.tex:132` | 表面温度的抬升幅度约为环境在 30 min 内升幅的六成五 | B 数值型 | — | — | — | **支持**（原样重跑探针：$T_\infty(0)=28.000$、$T_\infty(1800)=41.513$ ⇒ 环境升幅 $13.5130$ K；表 2 表面列 $36.7863$ ⇒ 表面升幅 $8.7863$ K；比值 $0.6502$。旧值「六成」本轮已改） | OK |
| 23 | `paper_appendix/sections/A_appendix.tex:157`（表 A5） | 初始含水率 $\pm1\%$ & 自设工程经验档 & $\mp0.048$ & $\mp0.046$ | B 数值型 | — | 取值依据（自设档）写明；**方向记号未定型**（见 27） | — | **量值支持**（产物复算：问题三 $+0.0472/-0.0477$ ⇒ 0.048；问题四 $+0.0458/-0.0463$ ⇒ 0.046。旧版把问题四那格写成 ∓0.048，本轮已改成该问自己的 0.046） | OK（量值）；记号见 27 |
| 24 | `paper/sections/5_problem3.tex:90`、`:94`；`6_check.tex:19`；`3_assumptions.tex:8`；`paper_appendix/sections/A_appendix.tex:161,171` | 环境延拓三档在 $n=320$ 连续根口径下的跨度为 0.24 h；峰值/饱和为 57.0055 与 56.9011 h；对流换热系数减半时只移动 0.08 h | B 数值型 | — | **本轮已把 n 与「连续根」口径写进同句** | — | **支持**（`tmp/rob/out/cal_env_{hold,peak,plateau}_n320.json` 的 `t_dry_root_h` = 57.1429 / 57.0055 / 56.9011 ⇒ 跨度 $0.2419$；`h` 减半 $57.2228$ 对同 n 基准 $57.1429$ 差 $+0.0799$。四处（正文、假设三、表 A5、表后正文）现在同值同口径） | OK |
| 25 | `paper/main.tex:62`；`paper/sections/5_problem2.tex:96` | 表面与环境之差自约 22.2 h 起一直不足 0.02 kg/kg | B 数值型 | — | 两处同值 | — | **支持**（`q2.npz` 的表面/环境序列复算：首次跌破在 $t=79746$ s $=22.1517$ h，其后 179455 点无回升越阈） | OK |
| 26 | `paper/sections/6_check.tex:19` | 图中该两档是 $n=160$ 对照实现上的读数，与这个跨度不是同一口径，不能直接相减 | B 强声称 | — | 口径关系写明 | — | **支持**（`figures/make_figures.py` 的 `fig_caliber_sensitivity` 实取 `env_peak_n160_dt60`/`env_plateau_n160_dt60` 的 `t_dry_step_h`，刻度标签自带 $(n=160, 60\ \mathrm s)$；与句子相符） | OK |
| 8 | `paper/sections/5_problem3.tex:84` | 判据函数在全程单调不增、只有一个零点 | B 数值型 | — | — | — | **上轮结论继续有效**（同小节本轮零改动；探针重跑：全过程 $g$ 只在浮点并列量级上有 $10^{-15}$ 级上跳、转正 0 次，与「判据函数是否单调不由算法假设」一致） | OK |
| 27 | `paper_appendix/sections/A_appendix.tex:157` | 初始含水率 $\pm1\%$ … $\mp0.048$ / $\mp0.046$ | B 数值型（记号） | — | **记号未定型** | — | **量值对、方向按行标签顺序读会读反**：产物是 $+1\% \Rightarrow +0.0472$ h（问题三）、$+1\% \Rightarrow +0.0458$ h（问题四），即初值越湿烘干越久；而同表已改过的两行（扩散系数、环境温度）是**按档位逐数绑定**的写法。写作阶段自己的记录对同一格同时写过 $\pm0.048$ 与 $\mp0.048$（`reports/EDITORIAL_CHANGES.md` 两处），说明 $\pm$／$\mp$ 记号在该表尚未定型 | OK（量值）；**记号入 advisories** |

## 未纳入项

- **误报/不判**：「结构性性质」「使用边界」「解的性质」这类非标签用法；`5_problem2.tex:13-17` 的物性经验式复述；`5_problem3.tex:37` 的优化形式定义式；`4_symbols.tex` 的符号定义；各表的数值本身。
- **本轮复核后仍判成立、只是表述偏简的两处**（不含假陈述，本阶段不改）：
  1. 附录 A.1 把两套收尾并列 —— 第 16 行的扰动论证（$\tilde q_{\varepsilon_0}\le0$ 于**全柱体**）与第 18–31 行的内区范数细化（$|q|\le r^2M_\varepsilon/2$）。第 26–31 行那句「固定 $\varepsilon$ 得 $\tilde q_{\varepsilon_0}\le O(\varepsilon^2)$，再令 $\varepsilon_0\to0^+$ …」若**单独**读，$O(\varepsilon^2)$ 只控住 $r=\varepsilon$ 一点。但把两段合起来读是自洽的：$[0,\varepsilon]$ 上由积分式得 $O(\varepsilon^2)$、$[\varepsilon,R]$ 上由极值原理得 $\le0$，取其大者即全柱体 $O(\varepsilon^2)$，再令 $\varepsilon\to0$ 得 $\tilde q\le0$。复核员判「结论由第 16 行那一支承担，第 31 行是冗余收尾」，与本文处置一致：不构成逻辑闭环缺口，只是读者需自行合并两段。
  2. 命题陈述没有把「初值径向均匀」单列成一条前提。它由「式 (eq:q2-pde) **的初边值问题**的经典解」按引用带入（式 (eq:q1-ic) 就是均匀初值），且证明里 $q(r,0)=0$ 正来自该条；换成非均匀初值命题即失效 —— 属引用式前提，不属缺前提。
- **登记观察（不构成本阶段缺陷、不进 issues）**：
  1. `code/outputs/q2.npz` 里温度键**混用两套单位**：`T5_1`/`T21_60`/`snap_T_C` 是摄氏度（首值 28），而 `mon_Tc`/`mon_Ts`/`mon_Tinf`/`mon_Tmin`/`mon_meanT` 是开尔文（首值 301.15）。这是该派生文件对自己的订约不显式，**与本交付无关**：论文里的温度、$\lambda$（$1.9\times10^{-4}$ s$^{-1}$）与全部表格数都按正确的那一支取得，`code/q2.py`/`q4.py` 取用也自洽。已提醒：后续阶段若直接读该 npz 复算，须先看键名不要拿错温标。
  2. `paper/sections/A1_materials.tex` 仍是占位形态（表体为尖括号占位符），交付末页（p31）文本层能读到「一句话说清它做什么」。按分工那一页由 `14Layout-and-format` 据 `reports/SUBMISSION_MANIFEST.json` 逐行生成，该阶段排在 mathproof **之后**、尚未运行 —— 已在侧车 `advisories` 里以 `presentation` 登记，本阶段不代改。
  3. 图件登记表 `figures/manifest.json` 的 `caliber_sensitivity` 行（源头在 `figures/make_figures.py` 的 `caption`/`claim` 参数）仍写「环境延拓三档跨度 0.30 h、面导度三档跨度 0.43 h、$h$ 减半 0.03 h」，与论文现口径（同 n 的 0.24 h 与 0.08 h）不一致。**该行不进交付件**：本阶段用 `pdftotext` 扫过两张交付 PDF 的文本层，「0.30 h」「0.03 h」均不出现；正文§6.2 也已写明图中那两档的口径关系。已在侧车 `advisories` 里以 `diagram` 登记（修它要重渲该图并重做目检）。
  4. 「±0.32 h 与 ±0.5 h 的合成方式」在正文里没写出来（`§5.3` 给 0.2 与 0.24 两个分量后直接给合计 ±0.32，段末又落到 ±0.5）。两个数都在上游登记（`RESULTS_REPORT`：「离散化 + 环境延拓的合计不确定度 ≈ ±0.3 h；把面导度取法也计入则 ≈ ±0.5 h」；`ROBUSTNESS_REPORT` §8.3 的建议口径是「离散化 ±0.2 h + 环境延拓 ±0.25 h」合计 ±0.32 h），方向偏保守、不改任何数值。同段还有一处同类：三个通道的读数在一句话里用了两种口径（界面物性那对数取 `results/sensitivity.json` 的 `t_dry_step_h` 步进首达，环境延拓与 $h$ 减半那几对取连续根），后半标了口径、前半没有；差 0.014 h，且每个读数都能在产物里唯一指认。已在侧车 `advisories` 里以 `report_wording` 登记。
  5. 表 A5「初始含水率 $\pm1\%$」格的记号未定型 —— 已在侧车 `advisories` 里以 `claim` 登记（见断言清单 27 与本文件「本轮复验记录」末段）：量值 0.048 / 0.046 正确，但按行标签的 $\pm$ 顺序读会把 +1% 那一档读成「推前 0.048 h」，与产物（推后 0.0472 h）相反。之所以**不判为假陈述**：该记号在写作阶段自己的记录里同时出现过 $\pm$ 与 $\mp$ 两种写法（说明未定型），全文没有任何结论/判据/建议时长建立在这条通道的**方向**上（§6.2 只用量值「都在 0.05 h 之内」），且同表该行本轮**已按同口径改成该问自己的值**，只是在量值上而非记号上。按「先证伪再报」的口径，本阶段不把它升成拦链项，但如实登记并给出可核的钉死办法。
- **低于报告阈**：`5_problem2.tex:19` 举例「典型的一处在 $t\approx14280$ s，环境温度由 50.142 掉到 49.759」—— 逐点复算该步是 $14220\to14280$（50.1420→49.7590，$\Delta=-0.3830$），故「在 $t\approx14280$ s ... 掉到」的落点是这一段的**终点**，与同段 0.383 °C 的降幅自洽，属近似表述不构成假陈述。
- **无标签命题的题不制造证明**：本文确有一条真命题、且带完整推导，故按命题审查处理；本阶段未把任何普通结论升级为命题，也未新增任何命题。

## 本轮复验记录

**入参回执**：`runtime/quality/feedback/2c23e64d/3cecb5db/gate_decision.json`（`reason=verdict_malformed`，唯一一条 issue 是侧车 schema 问题）。按「只剩 schema 项时取同阶段的实质判词」的纪律核对该目录：那里只有 `gate_decision.json`（474 字节），**没有报告本体**，说明上一轮是**停滞中断**而不是判出结论后被 schema 打回 —— 故本轮按现盘重做实质审计。

**改动面定位**（`_tmp/mp5_diff.py` → `.txt`）：与上一版被完整审过的快照逐文件 sha256 + 逐行 diff，改动只落在 `paper/main.tex`、`sections/1_restatement.tex`、`3_assumptions.tex`、`4_symbols.tex`、`5_problem1-4.tex`、`6_check.tex`、`7_evaluation.tex`、`references.tex`、`paper_appendix/sections/A_appendix.tex` 与两份登记 JSON 的 sha 字段；`2_analysis.tex`、`A1_materials.tex`、`_base/`、`result-values.*` **零改动**。

**探针复用（通用纪律一·1.1）**：开工第一步 `ls _tmp/`，把上一轮为同批对象写的探针**原样重跑**（解释器取 `config/runtime.local.json`）：

- `_tmp/mp1_claims_probe.py`、`_tmp/mp1_monotone_probe.py`、`_tmp/mp2_sympy_frame.py`、`_tmp/mp2_energy_measure.py`、`_tmp/mp4_news.py`、`_tmp/mp4_news2.py` → 输出与各自存档**逐行相同**（另存 `_tmp/mp5_rerun_*.txt`）⇒ 上一轮判 OK 的数值面在本轮**零漂移**。
- `_tmp/mp3_energy_identity.py`、`_tmp/mp3_subA_verify.py`、`_tmp/mp3_subA_pde.py`、`_tmp/mp3_subB_coordcheck.py`、`_tmp/mp3_a3_rows.py` → 与存档 `*.r3.txt` **逐行相同**（`diff` 差异行 0）⇒ 换帧链式法则、两条守恒恒等式、表 A3 逐行的结论不变。

本轮新写/新跑的探针（均只读，留在 `_tmp/`）：`mp5_diff.py`（改动面）、`mp5_probe.py`（环境延拓三档 n=320 连续根、界面物性/h 减半档、图件实取字段）、`mp5_pdf.py`（交付 PDF 文本层新旧串 + 登记图注是否进交付件）、`mp5_rv.py`（正文 `\ResultValue` 与登记表/PDF 的一致性）、`mp5_cite.py`（引用完整性）、`mp5_npz.py`（npz 键的温标核查）。

**独立复推（Step 3）**：两个只读 `paper/**` 的复核员各自独立作业，**不引用**原推导：
（1）命题的独立重推 + 前提实测 + 反例检验 —— 结论 **支持**：方程逐项一致、扰动项复算为 $\varepsilon_0((c-\lambda)t-1)$、「不需要 $D$ 的二阶导数符号条件」成立、三段极限无循环；从 145 张全场快照独立算出 $D$ 值域、P2 裕度（$1.76299\times10^{-3}$ 与 $1.25784\times10^{-3}$）与 λ；把 $C_\infty$ 置 3.0 的对抗算例把最坏点推到表面（3600/3600 步），**证实 P2 承重**；另有 $145$ 张快照上 $\max_r\partial_rC=8.88\times10^{-16}$（浮点并列量级）。
（2）改动面逐条复量 —— 对摘要与 §5.1–§5.4、§6.2、表 A5、A.4 预算的每一处读数独立重算并指认产物字段。逐条结论：摘要 22.2 h **成立**（`q2.npz` 的 `mon_Cs`/`mon_Cinf`：首次跌破 $t=79746$ s $=22.1517$ h，其后最大值 $0.0199996$，无回升越阈）；六成五与场跨 2.45 **成立**（$8.7861/13.513$ $=0.6502$；级数式同口径现算 $2.4499$）；附件 1 的 241/95/0.797/−0.450 与护栏 478/0/9.326e-15 **成立**；§6.2 与图件口径关系 **相符**（图取 `env_peak_n160_dt60`/`env_plateau_n160_dt60` 的 `t_dry_step_h`）；表 A5 初始含水率格 **量值对、记号见 27**；A.4 的预算合成 **数字对但口径不严谨**（两项都是全跨：离散化 0.1927、环境延拓 0.2419，字面相加 $0.435$、RSS $0.31$，论文的 ±0.32 要按「0.2 当半宽 + 0.24 当全跨」才凑得出）。
两个复核员各自指出的偏简之处（A.1 两段收尾并列、命题未单列均匀初值、表 A1 未列 Q4 的 λ′、npz 混用温标）经主审逐条复核后，均判为**不构成缺陷**，理由见「未纳入项」。

**交付面复核**：`paper/main.pdf`（09-30 02:57:48，晚于最后改动的 `7_evaluation.tex` 02:56:55 与 `main.tex` 02:57:39）与 `paper_appendix/main.pdf`（01:27:18，晚于 `A_appendix.tex` 01:26:13）的文本层逐串扫过（`_tmp/mp5_pdf.txt`）：本轮新串 19/23 直接命中，另 4 条首轮未命中经查是**检查串自带 `$` 数学标记**所致，改用折叠空白的纯文本片段后全部命中（如「环境延拓三档在𝑛=320连续根口径下的跨度为0.24h」「图中该两档是𝑛=…」「∓0.048…∓0.046」）。`paper/main.tex` 里两处 `\ResultValue` 渲染值与 `result-values.tex` 登记值一致（57.1383 已印出）。`reference` 侧：12 条 bibitem 与 12 个 `\cite` 键一一对应，无悬空引用、交付 PDF 无 `??`。

## 程序校验

- 报告末尾裁决行与 `reports/MATH_PROOF_REPORT.verdict.json` 的 `status` 同为通过（报告行 `APPROVED`、侧车 `APPROVED`，归一后均为 PASS）；`input_digest` 原样抄录入参，未自行更新。
- 必查四项 `proof_validity` / `proof_applicability` / `optimality` / `narrative_consistency` 全部给出结论与逐条 `evidence` 锚点（引文均为项目内文本文件的原文切片，落盘前经生成脚本逐条断言「逐字存在」）；本轮**无未解决项**，故 `issues` 为空数组；四条 `advisories` 均带 `why_not_blocking`（它们的 category 分别是 `claim` / `report_wording` / `diagram` / `presentation`，都在允许降级的那几类里）。
- 自检（对照 SKILL 末节）：每条处置都写了依据（哪一行、缺什么）；没有把合成谱/数值/图表当证明放行过任何一条；没有修改 `paper/`、`paper_appendix/` 下任何文件；没有发明或升级任何命题；项目根无本阶段留下的 scratch（全部在 `_tmp/`）。
- 落盘前已用驱动同一套函数预演：`python lib/web/check_verdict.py --stage mathproof --root .` 返回 exit 0（格式与规则都过）。

## 整题门禁裁决：APPROVED
