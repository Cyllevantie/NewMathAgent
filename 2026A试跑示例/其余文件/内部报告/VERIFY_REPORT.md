# 验证和验收报告

- **本阶段**：`15Verification`（验收），**第 1 轮复评**（`13Repair-by-rubric-verdict` 改完回本门禁复评）
- **上一轮裁决**：`reports/VERIFY_REPORT.verdict.json`（`status=REVISE_CLAIM`，两条纯 `claim` 判词）
  —— 副本留在 `runtime/quality/_pending_markers/verify/`，判词原文见其 `issues`
- **被审对象**：`paper/`（正文）、`paper_appendix/`（附录）、`paper/ai_tools/`（AI 工具使用详情）、
  三份归档 PDF 与提交件
- **本阶段只审不改**：未改任何被审对象、未改上游报告、未向任何报告追加 APPROVED

## 结论

整题裁决：PASS

两条经复评复核**已在当前盘面落实**（`narrative_consistency` 由 failed 转 passed），
无越界改动、无新发现的硬错误，机械门禁全绿。全程**未发现需要返修前序阶段的问题**，
故不写 `reports/HANDBACK_REQUEST.md`。

### 本轮执行范围（复评，只审改动波及的范围）

按复评口令，本轮**不重跑全部检查项**，而是围绕「⑬ 改了什么、有没有改坏别的」取证：

| 动作 | 结果 |
| --- | --- |
| 改动面 | `paper/` 自 ⑬ 收口以来**零差异**；相对 ⑭ 收口那一版只差 2 个 `.tex` + 构建产物 + 2 份重绑登记件 |
| 清单内落实 | 两项判词的 `recheck` 判据逐条实测通过（见「数值一致性」） |
| 清单外越界 | **0 个**（见「仍需处理的问题 §A」的改动面自证） |
| 重编译 | **已做**（Step 7，两遍 xelatex，rc=0）——属于**空重编译**：与 ⑬ 收口那一版逐页文本 32/32 相同 |
| 页数/版心 | `python -m lib.publication check` → PASS（32 页；计入额度 30/30；摘要版心填充 0.9241） |
| 逐页视觉 | **只重看改动落到的那两页 p11、p14 + 抽检 p10、p15**；其余 29 页复用上一轮已签结论 |

> 复用其余 29 页的依据不是"省事"：本轮重编译与 ⑬ 收口那一版的**逐页归一化文本层 32/32 逐字符相同**
> （`_tmp/vfy3_recompile_null.py`），渲染又是确定性的 ⇒ 那些页的像素不可能与上一轮签发时有差异。

## 检查项

| 检查项 | 结果 | 说明 |
| --- | --- | --- |
| task_fidelity 原题符合性 | passed | 30 条题意契约要求全部 `mapped`、四语义字段一致、锚点逐字存在（`python lib/web/check_contract.py --root .` 通过）；四份 `result*.xlsx` 的网格/步长/小数位与题面逐项闭合 |
| optimality 数值最优性范围 | passed | 达标时刻定义为全场最坏点判据的首个零点（非启发式停止值）；三份归档 PDF 文本层扫「全局最优/最优/显著/全覆盖/无空档/保证了/证明了/已证」合计 **0 命中**；不确定度一律给区间并显式声明生产裕度不是统计保证 |
| proof_applicability 前提适用性 | passed | §5.3 是显式条件命题，三条前提 P1/P2/P3 在本题解上逐条数值验证（附录 A.1 表 A1）；同节有等式级推导块（式 `eq:prop1-flux`），附录 A.1 补轴心项阶积分 |
| narrative_consistency 摘要/正文/图注/结论与证据一致 | passed | 上一轮判 failed 的两处**已落实并复验**（见「数值一致性」）；旧写法在三份 PDF 文本层与 25 份 `.tex` 源里合计 **0 命中**；摘要/表 2–表 8/图注与登记值逐项相符 |
| figure_coverage 图文覆盖 | passed | 正文 12 张编号图 + 附录 7 张（图 A1–A7）覆盖四问、灵敏度、总体思路与几何；`python -m lib.visualization audit` 无 issue；三份 `main.log` 无未解析引用 |
| content_coverage 每问必要论证 | passed | 四问各有「具体分析／模型准备／模型建立／模型求解／结果分析」，另有第六节检验与第七节评价；题面要求的四表与四份结果文件齐备 |

## 章节结构

| 项 | 结论 |
| --- | --- |
| 入口 `\input` 数 | `paper/main.tex` 共 11 处正文 `\input`，与 `paper/sections/` 下 11 个 `.tex` 一一对应；无重复引用、无未被 main 引用的章节文件 |
| 条件分支 | `labels_appendix.tex` / `labels-appendix.tex` 两个命名都不存在，两处 `\IfFileExists`（`paper/main.tex:46–47`）静默跳过，属预期；三份 log 的 `!` 级错误为 0 |
| 标题层级 | 1/2/3/4/6/7 用 `\section{}`；`5_problem1..4` 各给 `\subsection`，挂在 `\section{模型的建立与求解}` 下；`A1_materials.tex` 自身无 `\section`，标题由 `_base/macros.tex` 的 `\appendixAcn` 宏体发出 `\section*{附录}` |
| 问题数 | 题面 4 问（不是 3 问），四问各自成节、顺序为一→二→三→四 |
| 附录 | `\appendixAcn[支撑材料清单]{A1_materials}` 收在正文最后一页 p32；`paper_appendix/` 独立编译为 9 页 `附录A.pdf`，公式编号自 (17) 接续正文 |
| 页序 | p1 摘要 / p2–p30 正文（一～七）/ p31 八、AI 工具使用说明＋九、参考文献 / p32 附录，与 `paper/page-map.json` 的声明一致 |
| 逐页边界复核 | p1 首块 y=68.0 = 论文标题、p2 首块 y=73.6 = 「一、问题重述」、p30 首块 = 「缺点四：…」、**p31 首块 y=73.6 = 「八、AI工具使用说明」**、p32 首块 y=73.6 = 「附录」（`_tmp/fix13r3_pagebound.py` 原样重跑）⇒ 各类别起始标记就是该页最上面那块文字，`bind_map` 的边界判据放行 |

## 图表引用

| 项 | 结论 |
| --- | --- |
| 正文图 | 12 张编号图（图 1–图 12），逐张在对应语义章节内被 `\paperfigure` 引用，均带中文图题 |
| 附录图 | 7 张（图 A1–A7），经 `\appfigure` 引用，出处 `paper_appendix/sections/A_appendix.tex` |
| 路径解析 | `\includegraphics` 只出现在 `paper/_base/macros.tex`，写相对路径 `figures/<stem>.pdf`，按编译工作目录 `paper/` 解析正确 |
| 未解析引用 | 三份 `main.log` 的 `Reference/Citation … undefined` 均为 0；成稿全文无 `??` |
| 归属 | `q1_*`→问题一、`q2_*`→问题二、`q3_*`→问题三、`q4_*`→问题四、`caliber_sensitivity`→第六节；非数据图 `fig_roadmap` 在第一节、`fig_geometry`/`fig_coupling` 在问题一模型准备节 |
| 中间文件 | 全库无 `*_latex_includes*` 一类中间文件，图表直接嵌在对应 section |
| 目检登记 | `python -m lib.visualization audit` → PASS（无 issue）；`figures/manifest.json` 的 19 条 `included` 全为真 |

脚本每轮报的 19 条「figure PDF not referenced in paper」是**假阳**：正文经 `\paperfigure{stem}{题}{label}`
只写 stem，脚本拿 `<name>.pdf` 做子串匹配。逐张核对：`paper/figures/` 下 19 张中 12 张由正文引用、
7 张（`convergence`、`fig_q4_material`、`q1_profiles`、`q2_diffusivity`、`q4_effects`、`rb_tornado`、
`rb_uncertainty`）由附录工程引用。本轮 19 张图件的登记与哈希**零改动**（§A 的改动面自证）。

## 数值一致性

逐项复核，**未发现任何关键数值与结果记录冲突**。上一轮判 failed 的两条，本轮逐条复验如下。

**复验 1 —— `q1-loss-third-caliber-label-mismatch`（取样点集合与登记口径不同源）**

上一轮的判词要求：把该句为第三口径给出的取样点集合写成与 `results/q1.json` 登记值一致的那一个，
且不得改动已登记数值、不得动同句另外两个百分数。当前盘面：

- 源 `paper/sections/5_problem1.tex:134` 已写为「按 $0/0.5/1.0/1.5/2.0$ cm 五点的粗梯形求积得 \textbf{12.88\%}」，
  交付 PDF 第 11 页渲染一致（本阶段亲自看图确认）。
- 独立复算（`_tmp/fix13r3_claim_recheck.py` 原样重跑，只读交付件 `results/result1.xlsx` 工作表「水分浓度」的
  `t=1800 s` 行、21 列、权重 $\xi=r/2.0$ cm；分母按 `results/q1.json :: moisture_loss.mean_initial = 1.275`）：
  五点（0/0.5/1.0/1.5/2.0 cm）复合梯形得 $\int_0^1C\xi\,d\xi=1.110837500$ ⇒ 失水 **12.8755%**；
  登记项 `name=五点梯形求积（0/0.5/1.0/1.5/2.0 cm）  value=1.110837500  drop_pct=12.875490`
  —— 与论文报出的 12.88% 逐位相符，且与按 0.1 cm 全 21 列复算的 10.17% **不再是同一支**。
- 同句另两个口径未动：表面通量积分 `drop_pct=8.3420` ⇒ 8.34%、体积加权均值 `drop_pct=10.0563` ⇒ 10.06%，
  两串在正文 PDF 中仍在位。
- 旧写法清零：在三份归档 PDF 的文本层与 `paper/`+`paper_appendix/` 全部 25 份 `.tex` 源（含注释）里，
  「0.1 cm 输出列」「输出列的粗梯形积分」等 **0 命中**（去空白匹配，`_tmp/vfy3_recheck.py`）。

**复验 2 —— `q2-convergence-subject-misattribution`（主语与证据不符）**

上一轮的判词要求：把主语改成与证据相符的单一对象，每个量的值/单位/场别/取样时刻都要与
`reports/ANALYSIS_MODELING_REPORT.md` 的场级收敛表对上，且不得改动这两个数值。当前盘面：

- 源 `paper/sections/5_problem2.tex:82` 已写为「…；水分场在 72 h 末的场级网格收敛量为 $2.4\times10^{-4}$
  （全场最大变化），其中量级更小的表面格为 $4.2\times10^{-6}$ kg/kg。」交付 PDF 第 14 页渲染一致。
- 归属核对：上游表的该行为「72 h 场：$160\to320$ 最大 $|ΔC|=2.36\times10^{-4}$（中心格 $5.36\times10^{-5}$、
  表面格 $4.20\times10^{-6}$）」——两个量**都是水分场 $\Delta C$**；温度侧的网格收敛只在 $t=1800$ s 那一档给出
  （附录 A.2 表 A4 四个档位全是 $t=1800$ s / $t=100$ s，**无 72 h 档**）。改后句子已不再出现温度侧量。
- 两个数值未动：正文 PDF 中 $2.4\times10^{-4}$ 与 $4.2\times10^{-6}$ 各命中 1 次，仍在同一句内。
- 旧写法清零：「两个场在 72 h 末的场级网格收敛量」「的场级网格收敛量分别为」在三份 PDF 与 25 份 `.tex`
  里 **0 命中**。

**其余数值面**（沿用既有登记，本轮只读复核）

- 摘要与正文里的每一个数字都能在 `paper/result-values.json` 或 `reports/` 的登记值里找到出处，
  逐位相符：33.5765 / 36.7863 / 2.5500 / 1.5103、8.34% / 10.06% / 12.88%、49.8494 / 49.9664、
  0.13737 / 0.05162、57.1383 / 0.1500、50.8333 / 50.8225、2.27 / 2.02 / 0.89、−8.4 / +12.7 h、
  7.0 / 7.5 h、2.98 h、71 / 67 h、76.35 h。
- 表 2/表 3 与 `results/result1.xlsx` 逐格相符（1800 s 行温度 `33.5765 … 36.7863`、
  水分 `2.5500 … 1.5103`）；表 4/表 5 与 `results/q2.json` 的 3.0 h 行相符；表 6/表 7 与
  `result3.xlsx` / `result4.xlsx` 相符。
- 温度单位口径无误：表 4 的数值等于 `q2.json` 的 °C 口径键，未误取 `results/q2.npz` 的 K 口径键。
- 定义式复算（本阶段亲算，口径取自交付件本身）：效应分解 57.1500/25.1333 = 2.2739 ⇒ 2.27；
  50.8333/25.1333 = 2.0225 ⇒ 2.02；50.8333/57.1500 = 0.8895 ⇒ 0.89。表 8 各行 = 名义值 + 登记移动量。
- 成稿数值审计：`python -m lib.result_contract audit --rendered` → 空问题表 `[]`。
- 大数末位：76.35 h 一致，取自 $n=320$ 档，不是笔误（脚本的 near-duplicate 扫描为 0 对）。

## 数学论证闭环

- 扫 `定理|命题|引理|推论|性质|证明|证明了|严格相同|严格一致|正交|一阶无偏|无偏|恒成立|已证`：
  三份归档 PDF 文本层里「保证了/证明了/已证/严格相同/严格一致/一阶无偏/恒成立」合计 **0 命中**。
- `paper/sections/5_problem3.tex:15` 的「命题」同节自带等式级推导块（式 `eq:prop1-flux`），
  扰动—指数吸收的完整论证在 `5_problem3.tex:19–25`；附录 A.1 补全轴心项的阶积分与 $M_\varepsilon$
  的紧集取法（式 17–19）。
- `paper/sections/5_problem4.tex` 的坐标变换等价性有 `eq:q4-conserve` → `eq:q4-rform` → `eq:q4-pde`
  三步等式级推导，附录 A.5 逐项展开。
- `paper/sections/5_problem1.tex` 的「严格解耦」由同节式 `eq:q1-pde` 直接读出（温度方程不含水分、
  水分方程不含温度）。
- 两处「性质」命中（问题二的温度沿半径单调性、第六节的「首次达标即稳定达标」）**显式自标为
  数值观察/稳健性结论**，不作证明宣称。
- 需门禁知晓的一面：`paper/sections/2_analysis.tex` 的创新点/分析段用了「证明…严格等价」字样，
  该节内无推导块 —— 它们是**前向引用**（推导分别在 §5.4、§5.3 与附录 A.5、A.1，均有等式级推导），
  故不计入硬错误。摘要区不含「证明/已证」字样。
- 本轮的改动面是**两句散文**，两个文件的**公式块一行未动**：`formula-review.json` 的 23 条提示项
  $(file,line,message)$ 集合与上一版逐一相同，且 23/23 条的旧登记页仍落在当前 PDF 重测出的命中集合里
  （见「编译」节的重绑自证）。

## 文本质量门禁

`bash skills/15Verification/scripts/writing_check.sh --paper-dir paper` 退出码 1，5 条 FAIL
**逐条复验后全部是脚本自身盲区**（不是"上一轮说它是误报所以本轮也当它是"）：

| 脚本判定 | 复验依据（本轮实查） |
| --- | --- |
| `included LaTeX file does not exist: labels_appendix.tex` / `labels-appendix.tex` | 两处都在 `paper/main.tex:46–47` 的 `\IfFileExists{…}{…}{}` 条件分支里，是允许缺失的可选桩；脚本的纯正则不解析条件守卫。真缺文件会让编译报 File not found，而三份 log 的 `!` 级错误为 0 |
| `section has no \section{} heading: A1_materials.tex` | 文件名前缀是 `A1_` 而非脚本豁免判据认的 `A_`。标题由 `paper/_base/macros.tex:64–69` 的 `\appendixAcn` 宏体发出 `\section*{附录}`，成稿 p32 页首即「附录」 |
| `internal workflow term leaked into paper text: paper\sections\5_problem4.tex` | 命中词 `_tmp/` 落在**行首为 `%` 的注释行**（`:33`），不进渲染面；三份 PDF 文本层对 deny 词表 0 命中 |
| `internal workflow term leaked … A1_materials.tex` | 同上，`:3` 也是 `%` 注释行（`_tmp/fmt_gen_a1.py`） |
| `symbols used in formulas but absent from the symbol table (9): D, M, U, e, i, k, m, q, r` | 抽取式只认「字母紧跟 `_`/`^`」（`writing_check.sh:505`）。逐条实测（`_tmp/vfy3_symbols.py`）：`D`、`U`、`i`、`k`、`m`、`q`、`r` **都在表 1 里**（以裸字母声明，如 `$D$` 在 `4_symbols.tex:34`、`$U$` 在 `:41`、`$q$` 在 `:47`、`$r$` 在 `:23`）；`e` 来自 $\tilde q=q\,e^{-\lambda t}$ 的指数底、不是符号；只有 **`M`（即 $M_\varepsilon$）确实没进表 1**，但它在正文首次出现处就地定义（`5_problem3.tex:25`「其中 $M_\varepsilon$ 取内区紧集 $[0,\varepsilon]\times[0,T]$ 上 $\partial_tC$ 的上确界」）⇒ 记 advisory（见「仍需处理的问题 §B」），不构成硬错误 |

其余扫描**未命中**，并含正对照（防假阴）：

- **占位符**：`TODO|PLACEHOLDER|待补充|待续写|示例数据|TBD|XXX` 在 `paper/**/*.tex`、`paper_appendix/**/*.tex` 全部 0 命中。
- **对三份归档 PDF 复扫内部词**（`skills/_references/internal_leak_words.md` 的【内部词 deny】：阶段代号、门禁 token、
  内部文件名、harness/门禁/回执/降级放行/SUBMIT、内部用例标签、内部版本口径串、内部路径、字面 LaTeX 泄漏）：
  正文、`附录A.pdf`、`AI工具使用详情.pdf` 三份 `pdftotext` 文本层**全部 0 命中**（`_tmp/vfy2_leak_scan.py` 原样重跑，
  去空白匹配）。对照：`.tex` 源里确有 `_tmp/`、`14Layout-and-format` 等命中，逐条核实**全部落在 `%` 注释行或
  合法宏定义**（`\newcolumntype{L}[1]{>{\raggedright\arraybackslash}p{#1}}` 是标准写法；`C-2` 是公式
  `\rho_d\partial_tC-2\rho_dC\dot R/R` 里的子串）⇒ 扫描有效而非假阴。
- **程度词-数据一致性**：`全局最优|最优|显著|全覆盖|无空档|保证了|证明了` 在三份 PDF 文本层**均 0 命中**。
- **列表式写作**：`paper/sections/` 全篇仅 1 处列表环境（假设节），无段落以「如图/由图」起首。
- **算法超参与复杂度**：全文未用任何元启发/智能优化算法，求解是确定性路线（柱坐标有限体积 + 半隐式欧拉 +
  标量事件定位），唯一迭代器是 Brent 求根，容差 $10^{-9}$ s 已在正文登记。
- **关键词**：5 个，不超过 6。**摘要页**：1 页，版心填充 0.9241（≥0.90 target）。
- **灵敏度可视化**：灵敏度不是纯数字表 —— 正文有图 12，附录有图 A3/A4。
- **符号表`WARN`对侧**：脚本另报 9 个「symbols absent from the symbol table」，其中 8 条已证为假阳（见上表）；
  「metrics appear in result file but are hard to find in paper text」是**假阳**：该扫描在
  `reports/RESULTS_REPORT.md` 里匹配到的 6 个"指标名"全部是内部回执 id `aud-precision-scope-earlytime`
  里的 `precision` 子串（以及一处 schema 字段名 `pointer/precision`），既不是指标、也不该出现在论文里。
- **3_assumptions.tex 偏短**（538 字符 vs 脚本阈值 800）：属警告面。该节按五条假设紧凑成文、每条带依据，
  内容完整，不构成缺陷。
- **参考文献真实性**：12 条逐条为真实文献；7 条非经典条目已做 Crossref 抽查，题名、期刊、卷、页、年均相符，
  无一捏造（上一轮结论，本轮文献面零改动 ⇒ 沿用）。
- **提交清单对账**：`python -m lib.delivery check` 仍报 5 条，**逐条核实为当前打包阶段的正常中间态**：
  4 条是 `lib/delivery/core.py` 的 `_carry` 机制把上一版包里、本轮 `exclude` 掉的附件搬回提交件根
  （`reports/SUBMISSION_MANIFEST.json` 的 `exclude` 段已逐条声明）；1 条是 `demo.html` 由整链最后一阶段
  `16Web-demo` 产出、此刻尚未跑。均非论文或清单写错，本阶段不据此判 FAIL。

## 编译

- **已按 Step 7 重编译**：在 `paper/` 内跑两遍 `xelatex -interaction=nonstopmode main.tex`，
  `pass1 rc=0  pass2 rc=0`（stdout 留 `_tmp/vfy3_xelatex_p1.out` / `_p2.out`）。
- 重编译前后 `paper/main.pdf`：`135ab0ecb35a0304…` → `aa72074797ab0c2f…`；**字节数逐位相同（1 107 181 B）**，
  页数 32、A4（595.28 × 841.89 pt）。
- **这是空重编译，不是新内容**：与 ⑬ 收口那一刻的交付 PDF（`…/按评分判词返修/paper/main.pdf`）逐页
  归一化文本层 **32/32 页逐字符相同**；与 ⑭ 收口那一版（`…/排版与版式/paper/main.pdf`）差异页**恰为 [11, 14]**，
  正是被返修的那两句（`_tmp/vfy3_recompile_null.py`）。
- 编译告警集合差分（对照面 = ⑭ 收口那次编译的 `main.log`）：`!` 级错误 0→0、`Reference/Citation undefined`
  0→0、`Overfull` 0→0、`Missing character` 0→0、`LaTeX Error` 0→0，仅 4 条无害 `Underfull \hbox`
  （都在参考文献段）**新增 0 / 消失 0**。
- `paper_appendix/main.pdf` 9 页 / 417 537 B；与 ⑭ 镜像逐页文本 9/9 相同（6:16:44 的空重建，早于本轮，
  非本轮改动）。`paper/ai_tools/main.pdf` 3 页 / 147 474 B。三份均远低于 20 MB 上限。
- **编译引起的绑定重建（本阶段所为，如实登记）**：重编译使 `paper/page-map.json` 与
  `paper/formula-review.json` 的 `pdf_sha256` 绑定同时失效（`lib.publication check` 随即报
  「页面映射未绑定当前PDF」）。已按仓库既定流程补齐，且每一步都先自证"内容没动"：
  1. `python -m lib.publication map _tmp/vfy3_pagemap_spec.json` —— spans 逐项沿用；重绑前先按现盘复核
     四类起始标记（见「章节结构」的逐页边界复核），`bind_map` 自带的边界校验放行。
  2. 重绑 `paper/formula-review.json`（`_tmp/vfy3_rebind_formula_review.py`，复用上一轮的定位逻辑）：
     ① 23/23 条 `source_sha256` 与现盘源文件一致；② 提示项 $(file,line,message)$ 集合与上一版逐一相同；
     ③ **旧登记页 23/23 全部仍落在当前 PDF 重测出的命中集合里** ⇒ `decision`/`reason`/`page` 原样沿用是诚实的。
  3. `python -m lib.publication report` 刷新 `reports/PUBLICATION_CHECK.json`（时刻快照，重编译后必须刷新）。
  4. 复跑 `python -m lib.publication check` → **PASS**（32 页、计入额度 30/30、摘要填充 0.9241、无 issues）。
- **输入指纹自证（本阶段只读的唯一硬判据）**：以配置的 python 现算
  `lib.web.server._input_split(verify)` / `_input_digest(verify)`，与驱动注入的 `input_digest` **逐段比对，5 段全等**
  （第 0 段 artifacts 与整份 digest 都是 MATCH，`_tmp/vfy3_digest.py`）。
  这成立的原因是驱动侧 `workflow_quality._is_paper_build_output` 已把 `paper/**/*.pdf`、`main.log/aux/out`
  与 `page-map.json`/`formula-review.json` 排除在输入指纹之外 ⇒ 本阶段按 SKILL Step 7 重编译并重绑
  **不会**被误判成"输入在执行期间被改动"。

## PDF 视觉检查

**已执行**，由本上下文亲自看图。

- **本轮重渲的页**：`pdftoppm -r 150` 从**现盘** `paper/main.pdf` 渲出 p10–p15（`_tmp/vfy3_pg/`），
  逐页看过：**改动落到的那两页 p11、p14 + 两侧抽检页 p10、p15**。
- **复用的页**：其余 29 页（正文 p1–p9、p12–p13、p16–p32）与 `附录A.pdf` 9 页、`AI工具使用详情.pdf` 3 页
  **沿用上一轮已签的结论** —— 依据是本轮重编译与 ⑬ 收口那一版的逐页文本层 **32/32 逐字符相同**，
  渲染是确定性的，那些页的像素不可能变。
- 逐页结论（本轮看的四页）：
  - **p11**：表 2 与表 3 并排，列对齐、无跨栏压线；返修句「…按 0/0.5/1.0/1.5/2.0 cm 五点的粗梯形求积得
    **12.88%**。三者的差异来自求积精度与权重定义…」正常折行、无溢出、未压到页边；
    公式 $\int_0^1C\xi\,\mathrm{d}\xi$ 与 $j_s$、$\rho_{d0}$ 均在版心内；页码 11 在底部居中。
  - **p14**：表 4 与表 5 并排、表头纵跨两行正确；返修句「…；水分场在 72 h 末的场级网格收敛量为
    $2.4\times10^{-4}$（全场最大变化），其中量级更小的表面格为 $4.2\times10^{-6}$ kg/kg。」折行正常、
    段末未留孤立残行；页码 14 正常。
  - **p10**（抽检）：式 (6)、(7) 与 $\Phi_{i+1/2}$ 定义式都在版心内，未越界；段间距正常。
  - **p15**（抽检）：图 5 与图 6 整幅落在版心内，色标与图例均在坐标区外、未压线穿字；图题在下方未被裁切。
- 未发现空白页、缺页、页数异常或页面尺寸异常；标题/摘要/正文/页眉页脚/页码无裁切；无表格越界、
  单元格重叠/溢出/截断；无图片/图题/表题/公式与正文重叠；中英数与数学符号无缺字、乱码或 fallback 异常。

## 仍需处理的问题

### A. 必须返修（进 issues）

**无。** 上一轮的两条 `claim` 判词已在当前盘面落实并复验通过；本轮未发现新的硬错误，
也未发现越界改动引入的问题。故 `issues` 为空，`status = PASS`。

**改动面自证（回答"有没有清单外越界改动"）** —— 两个对照面，逐文件 sha256：

| 对照面 | 结果 |
| --- | --- |
| `产物/各阶段产物/最新产物/按评分判词返修/paper/`（⑬ 收口那一刻的镜像） | `paper/` **50 份对 50 份，新增 0 / 消失 0 / 内容不同 0** ⇒ ⑬ 收口后**没有任何东西再动过被审对象** |
| `产物/各阶段产物/最新产物/排版与版式/paper/`（⑭ 收口那一版，即上一轮验收的对照面） | 内容不同 **6 份**，全部在预期内：`sections/5_problem1.tex`、`sections/5_problem2.tex`（清单内的两句）、`main.pdf`、`main.log`（构建产物）、`page-map.json`、`formula-review.json`（重编译后按现盘重绑）。**清单外改动 = 0** |
| `paper_appendix/` | 与 ⑭ 镜像只差 `main.log`、`main.pdf` —— 那是 **6:16:44 的空重建**（早于 ⑬ 12:16:39 的开工时刻），逐页文本 9/9 相同，非本轮改动引入 |
| 全工作区 mtime 扫描（12:16:39 之后被写过的文件） | 只有 `paper/` 下 8 份（两句 + 构建产物 + 两份重绑）、`reports/FIX_REPORT.*`（⑬ 自己写的）、以及本阶段的 `reports/VERIFY_REPORT.*` 与 `reports/PUBLICATION_CHECK.json`。**此外一处没有** |

⇒ 结论：**⑬ 的改动面 = 清单内 2 行散文；"修 A 坏 B" 未发生。**

### B. 建议（advisories）—— 不进 issues、不拦链

| # | id | 位置 | 事实 | 建议去向 |
| --- | --- | --- | --- | --- |
| B1 | `budget-ratio-upper-end` | `main.tex`、`6_check.tex`、`7_evaluation.tex` | 「比数值预算大 15 至 25 倍」上下端不同源：分母取同节自报的约定不确定度 ±0.5 h 时得 14–15；上端 25 只有换成单参数扩散系数的 +12.7 h 才凑得出。**已在 12Rubric-final 登记为 `budget-ratio-caliber-not-reproducible`（tier=optional）**，按用户口径「只剩 optional 残留时判通过」，本轮不重复拦链 | claim → write |
| B2 | `ref15-subtitle` | `paper/references.tex:15` | 副标题写作 `… water diffusivity and shrinkage`，Crossref 该 DOI 的真实题名是 `… water diffusivity and peel resistance estimation`。文献真实存在（非捏造），仅题录文字错 | presentation → format |
| B3 | `table-A5-pm-direction` | `paper_appendix/sections/A_appendix.tex` 表 A5 | 「初始含水率 ±1%」行写 $\mp0.048$ / $\mp0.046$，产物实测方向为 +1% ⇒ +0.047 h / +0.046 h。量级只有 0.05 h，远小于全文引用的 ±0.5 h 约定不确定度 | presentation → format |
| B4 | `internal-term-in-tex-comments` | `5_problem4.tex:33`、`A1_materials.tex:3` | 两条 `%` 注释里引用了 `_tmp/fmt_margin_overflow.py`、`_tmp/fmt_gen_a1.py` 与阶段名。不进渲染面、不进提交件，但会让 `writing_check.sh` 每轮报 FAIL | presentation → format |
| B5 | `paper-math-style-residual` | `paper/math-style.tex` | `paper/` 根下存在**未被任何文件引用**的残留副本（正文用的是 `_base/math-style.tex`），两份 sha256 不同。不参与编译、不在提交清单里 | presentation → format |
| B6 | `orphan-figure-copies` | `paper/figures/` | 19 张 PDF 中 7 张在正文未被 `\paperfigure` 引用（由附录工程引用，此处是副本）。属 SKILL 的「未引用的备用图片」警告面 | presentation → format |
| B7 | `internal-artifact-wording` | `5_problem2.tex:82`、`A1_materials.tex` | 两处指向内部产物的措辞：「与建模报告的登记值逐位一致」；清单表里 `summarize.py` 的说明「登记结构化指标，供正文以登记键引用数值」。未命中 deny 词表（三份 PDF 复扫 0 命中），但对评委而言会暴露内部产物 | claim → write |
| B8 | `advice-time-2sigma-arithmetic` | `reports/ROBUSTNESS_REPORT.md`、`7_evaluation.tex:47` | 建议时长末行 71 h / 67 h 来自上游报告，其自述判据是 $t_{\rm dry}+2\sigma$ 且 $2\sigma=$ 14–15 h：57.1+14 = 71.1 ⇒ 71，但 50.8+15 = 65.8 ≠ 67（差 1.2 h）。论文侧忠实抄录，**分叉在上游报告那一句** | report_wording → analysis |
| **B9** | `symbol-table-missing-M-epsilon` | `paper/sections/4_symbols.tex`（表 1） | **本轮新登记**：脚本报的 9 个「缺符号」里，只有 $M_\varepsilon$ 经核实确实没进表 1。它出现在 §5.3 的一条**行间公式**（`5_problem3.tex:25`）里，正文**首次出现处**已就地定义（「取内区紧集 $[0,\varepsilon]\times[0,T]$ 上 $\partial_tC$ 的上确界」），满足 SKILL Step 5「符号应在符号说明或正文首次出现处解释」。属登记完备性的可选改进，**不是**硬错误 | claim → write |

**★ 投递限制（必读）**：本阶段是链上倒数第二个门禁，`advisories` 里 `claim→write`、`presentation→format`、
`report_wording→analysis` 三个目标**都在上游**。上游目标**连回退都不投递**；且只有 `must/hard` 档的
advisories 会上面板。⇒ **上表 B1–B9 没有任何阶段会自动执行它们。** 想改其中任何一条，
请在黄灯面板上选「回退到所选阶段」显式指定目标阶段。

### C. 中间态事实（非缺陷，登记备查）

- 本阶段重编译后，提交件根的正文档 `基于变物性耦合传热传质与材料坐标的圆柱形药材烘干模型.pdf`
  的 sha256 仍是 ⑬ 收口那一版的 `135ab0ec…`，而现盘 `paper/main.pdf` 已是 `aa720747…`。
  二者**内容相同**（逐页归一化文本层 32/32 逐字符相同）⇒ 差异只是本轮空重编译写入的 PDF 时间戳/`/ID`；
  链尾正式打包时会以现盘为准重建。本阶段不据此判缺陷（上一轮同一形态已记录在案）。
- `reports/PUBLICATION_CHECK.json` 是**时刻快照**，已在本阶段重编译后按现盘刷新，其 `pdf_sha256`
  现指向 `aa720747…`。

### D. 本阶段取证脚本（留在 `_tmp/`，下轮原样重跑）

- `_tmp/vfy3_digest.py` —— verify 阶段 `input_digest` 的逐段自证（需要把 `lib/web` 也加进 `sys.path`，
  上一轮的 `vfy2_digest_check.py` 缺这一步、会 `ModuleNotFoundError`）。
- `_tmp/vfy3_change_surface.py` —— 改动面自证（两个对照面 + 全工作区 mtime 扫描）。
- `_tmp/vfy3_recompile_null.py` —— 重编译是不是空重编译（三个对照面的逐页文本层比对）。
- `_tmp/vfy3_rebind_formula_review.py` —— 重绑 `formula-review.json` 的三条自证。
- `_tmp/vfy3_recheck.py` —— 两条判词的旧写法清零 / 新写法在位 / 程度词复扫（三份 PDF + 25 份 `.tex`）。
- `_tmp/vfy3_symbols.py` —— 脚本报的 9 个「缺符号」逐条核实。
- 复用件（原样重跑，未覆盖）：`_tmp/vfy2_leak_scan.py`、`_tmp/vfy2_digest_check.py`、
  `_tmp/fix13r3_claim_recheck.py`、`_tmp/fix13r3_pagebound.py`、`_tmp/fix13r3_logdiff.py`、
  `_tmp/vfy_deliverable_closure.py`、`_tmp/vfy3_pagemap_spec.json`（spans 沿用 `fix13r3_pagemap_spec.json`）。
