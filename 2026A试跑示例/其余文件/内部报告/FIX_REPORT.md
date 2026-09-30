# 按评分判词返修报告

- **本阶段**：`13Repair-by-rubric-verdict`（fix），run 起于 2026-09-30 12:16:39
- **输入裁决**：`reports/VERIFY_REPORT.verdict.json`（stage=`verify`、status=`REVISE_CLAIM`）
  —— **本轮的上游是 ⑮ 验收，不是 ⑫ 评分标终审**。依据 `runtime/web_run.log` 12:16:39：
  「verify 判词全为论文侧（2 项）且本关之后没有写作阶段 ⇒ 交 13Repair-by-rubric-verdict 定点改写，
  改完回本门禁复评（第 1 / 3 轮）」，随后「启动阶段 fix」。驱动在 `lib/web/server.py:5031` 就地存下
  `fix_required = [q1-loss-third-caliber-label-mismatch, q2-convergence-subject-misattribution]`。
  ⑮ 的 `narrative_consistency` 刻意**不在** `content_quality.RESULT_CHECK_CATEGORY` 反推表里，
  所以两条 `claim` 判词原样落到本阶段（其余检查项在 ⑮ 里全 passed）。
- **被改对象**：`paper/sections/5_problem1.tex:134` 与 `paper/sections/5_problem2.tex:82`
  （两句正文散文），随后按 SKILL 第 5 步重编译 `paper/main.pdf`，并按 memory
  [[fix-stage-recompile-rebind-chain]] 一并重绑 `paper/formula-review.json`、`paper/page-map.json`，
  再跑 `python -m lib.publication report` 刷新 `reports/PUBLICATION_CHECK.json`。
- **改前基准**：`产物/各阶段产物/最新产物/排版与版式/paper/main.pdf`（sha256 `80d0e196ceab6923…`
  —— ⑭ 收口那一版，也是 ⑮ 刚刚验收过的现盘对照面）；自建文件级基线
  `_tmp/fix13r3_before_hashes.json`（79 份）+ 副本 `tmp/fix13r3_5_problem1.tex.before`、
  `tmp/fix13r3_5_problem2.tex.before`（驱动本轮**没有**新建 cache 快照目录，最新那份
  `产物/cache/2026A_2026.9.30_04.21.04/…` 是**上一轮** ⑬ 的基线，故本阶段自建）。

## 整题结论：DONE

本阶段职责内的判词（`claim`）**已全部落地**：⑮ 的 2 条 `claim` 判词经现盘逐条复核**均属实**，
按判词定点改写并逐项复验（取样点集合、主语归属、两个数值未动、旧写法清零、页数、版式、改动面）。
另有 1 条同类 advisory 与 1 条 `claim` advisory 按「不动 + 给依据」登记，
4 条 `presentation` advisory 与 1 条 `report_wording` advisory 按驱动 `TARGETS` 路由到各自阶段。

## 逐条处置

| # | 判词 id | tier / category | 位置 | disposition | 动作 | 复验输出（真实） |
|---|---|---|---|---|---|---|
| 1 | `q1-loss-third-caliber-label-mismatch` | 判词 / `claim` | 源 `paper/sections/5_problem1.tex:134`；交付 PDF p11 | **fixed** | 「按 0.1 cm 输出列的粗梯形积分得 **12.88%**」→「按 $0/0.5/1.0/1.5/2.0$ cm 五点的粗梯形求积得 **12.88%**」（取样点集合逐字取自登记名 `results/q1.json :: moisture_loss.calibers[2].name`）；数值与同句另两个百分数一字未动 | 「0/0.5/1.0/1.5/2.0」源侧 1 处 / PDF p11；旧写法源侧与 PDF **均 0 命中**；8.34 仍 PDF p1+p11、10.06 仍 PDF p1+p11+p19 |
| 2 | `q2-convergence-subject-misattribution` | 判词 / `claim` | 源 `paper/sections/5_problem2.tex:82`；交付 PDF p14 | **fixed** | 「，两个场在 72 h 末的场级网格收敛量分别为 $2.4\times10^{-4}$ 与量级更小的表面格 $4.2\times10^{-6}$ kg/kg。」→「；**水分场**在 72 h 末的场级网格收敛量为 $2.4\times10^{-4}$（全场最大变化），其中量级更小的表面格为 $4.2\times10^{-6}$ kg/kg。」（主语改为与证据相符的单一对象） | 新主语源侧 1 处 / PDF p14；旧写法源侧与 PDF **均 0 命中**；两个数值源侧各 1 处、仍在句内 |
| 3 | `budget-ratio-upper-end` | advisory / `claim` | 摘要、`5_problem3.tex:90`、`6_check.tex:23`、`7_evaluation.tex:21` | **deferred** | 属实，但与 ⑫ 的 `budget-ratio-caliber-not-reproducible`（tier=optional）同一件事，且口径须与上游 `ROBUSTNESS_REPORT.md` 同批定；未改一字 | 见「deferred」一节 |
| 4 | `ref15-subtitle` | advisory / `presentation` | `paper/references.tex:15` | **out_of_scope** | 未改一字；`TARGETS[presentation] = format` | `paper/references.tex` 与基线逐字节相同 |
| 5 | `table-A5-pm-direction` | advisory / `presentation` | `paper_appendix/sections/A_appendix.tex` 表 A5 | **out_of_scope** | 未改一字；交 `14Layout-and-format` | `paper_appendix/` 全目录与基线逐字节相同 |
| 6 | `internal-term-in-tex-comments` | advisory / `presentation` | `5_problem4.tex:33`、`A1_materials.tex:3` | **out_of_scope** | 未改一字 —— 是 ⑭ 自己写的施工备注，删它属 ⑭ 收口 | `5_problem4.tex` 与基线逐字节相同 |
| 7 | `paper-math-style-residual` | advisory / `presentation` | `paper/math-style.tex` | **out_of_scope** | 未改一字 —— `paper/` 根与 `_base/` 的文件取舍属 ⑭ 模板层 | `paper/math-style.tex` 与基线逐字节相同 |
| 8 | `orphan-figure-copies` | advisory / `presentation` | `paper/figures/` 7 张副本 | **out_of_scope** | 未改一字 —— 删副本会让附录读不到图，属 ⑭ 的文件层收口 | 两处 `figures/` 目录零改动 |
| 9 | `internal-artifact-wording` | advisory / `claim` | `5_problem2.tex:82`、`A1_materials.tex` | **deferred** | 判词性质属本阶段能改的措辞面，但它是 **advisory 而非判词**、不在本轮 `fix_required` 里 ⇒ 按 discipline 五·1 只改清单内，不动 | 该句只动了判词 2 点名的那半句；`A1_materials.tex` 与基线逐字节相同 |
| 10 | `advice-time-2sigma-arithmetic` | advisory / `report_wording` | 上游 `reports/ROBUSTNESS_REPORT.md:536-538` | **out_of_scope** | 未改一字 —— 分叉在上游报告的推导句，本阶段不改编 `reports/` 下的上游报告 | `reports/` 下除 `FIX_REPORT.*` 与 `PUBLICATION_CHECK.json` 外无写入 |

## not_reproduced（判词不属实，未改稿）

**本轮 0 条。** 两条归本阶段的判词都经现盘独立取证后判**属实**（见下），故按 `fixed` 处置，
没有使用这一栏。

- 判词 1 的取证（探针 `_tmp/fix13r3_claim_recheck.py`，分母按 `code/q1.py` 的登记口径
  `m0 = q1.json.moisture_loss.mean_initial = 1.275`）：对**交付件** `results/result1.xlsx`
  工作表「水分浓度」的 `t=1800 s` 行（21 列，半径 0.0 … 2.0 cm）分别按两种取样集合复算 ——

  ```
  0.1 cm 输出列（全 21 列）      ∫Cξdξ = 1.145313750  ⇒ 失水 10.1715%
  0/0.5/1.0/1.5/2.0 cm 五点      ∫Cξdξ = 1.110837500  ⇒ 失水 12.8755%
  q1.json 第三口径登记：name=五点梯形求积（0/0.5/1.0/1.5/2.0 cm）  value=1.110837500  drop_pct=12.875490
  ⇒ 12.88% 出自【0/0.5/1.0/1.5/2.0 cm 五点】这一支（逐位相符：True）；按 0.1 cm 全 21 列复算得 10.17%，不是 12.88%
  ```

  与 `code/q1.py:65-69` 的实装一致（口径 3 = `table2[-1]` 的五点梯形）⇒ 判词属实，
  数值本身正确、错的只是句子里给的取样点集合。

- 判词 2 的取证（同一探针）：`reports/ANALYSIS_MODELING_REPORT.md:868` 的场级收敛行原文为
  「72 h 场：$160\to320$ 最大 $|ΔC|=2.36\times10^{-4}$（中心格 $5.36\times10^{-5}$、
  表面格 $4.20\times10^{-6}$）」—— 两个量**都是 $|\Delta C|$**；同行的温度侧只在**取材时刻
  $t=1800$ s** 给出（$\max|\Delta T|=3.3\times10^{-6}$ K）。附录 A.2 的**表 A4** 四个档位全是
  $t=1800$ s / $t=100$ s，**没有 72 h 档**；`paper/` 全目录含「72 h」且含「收敛/网格」的句子
  **只有这一处**。⇒ 判词属实。

## deferred（属实但不改稿）

| 判词 id | 为何不改 | 成本估计 |
|---|---|---|
| `budget-ratio-upper-end`（≈ ⑫ 的 `budget-ratio-caliber-not-reproducible`，tier=optional） | 分子分母的新写法必须与上游 `reports/ROBUSTNESS_REPORT.md` 的同一句同批确定，而那份报告按 `TARGETS` 的 `report_wording → analysis` 归 3analysis；本阶段只改论文侧，单独改会把「论文 15–25 倍 ↔ 报告 15–25 倍」的一致性打破，而 ⑮ 正是按「论文数值来自 reports」复核的 | 要同时改四处（`main.tex:68`、`5_problem3.tex:90`、`6_check.tex:23`、`7_evaluation.tex:21`）并补一句口径说明，约 +1～2 行正文、20–30 min；⑮ 已明写它不进入任何交付数值与判据 |
| `internal-artifact-wording` | 它是 **advisory**、不在本轮 `fix_required` 里；判据本身是「未命中 deny 词表、不进提交件」，⑮ 已判非阻断。按 discipline 五·1「只改回执点名的位置」不动 | 两处措辞，分钟级；但它与 `A1_materials.tex` 的清单表生成链（`reports/SUBMISSION_MANIFEST.json` → ⑭）耦合，改动宜随 ⑭ |

## 不属本阶段的判词

| 判词 id | category | 该退到哪个阶段 | 为什么本阶段改不了 |
|---|---|---|---|
| `ref15-subtitle` | presentation | `14Layout-and-format` | 驱动 `TARGETS[presentation] = format`。本阶段边界表里的「引用位置与格式」指**引用点与著录格式**，这一条是**题录内容与外部真实题名不符**（属文献真实性面，⑮ 已按分工复核并判非阻断）。且不在 `fix_required` 里，改它即清单外改动 |
| `table-A5-pm-direction` | presentation | `14Layout-and-format` | 附录表体的数值方向登记；本阶段只改论文侧措辞、不改数值 |
| `internal-term-in-tex-comments` | presentation | `14Layout-and-format` | 是 ⑭ 自己写的两条 LaTeX 注释（不进渲染面、不进提交件），删它属 ⑭ 的收口动作 |
| `paper-math-style-residual` | presentation | `14Layout-and-format` | `paper/` 根与 `paper/_base/` 的模板层取舍是 ⑭ 独占职责 |
| `orphan-figure-copies` | presentation | `14Layout-and-format` | 图件副本的增删属文件层收口；删副本会让附录工程读不到图（`paper_appendix/sections/A_appendix.tex` 经 `\appfigure` 引用同名副本） |
| `advice-time-2sigma-arithmetic` | report_wording | `3analysis` | 分叉点在**上游报告** `reports/ROBUSTNESS_REPORT.md:536-538` 的推导句上；论文侧表 8 末行与报告一致。本阶段只改 `paper/`，不改编上游报告 |

## 改动范围自查

全部输出均来自命令实跑，不是意图。

**① 改动行 diff（`python _tmp/fix13r3_diff.py`）—— 合计 `+2 / -2` 行，一判词一行**

```
tmp/fix13r3_5_problem1.tex.before  →  paper/sections/5_problem1.tex
@@ -134 +134 @@
- …按 0.1 cm 输出列的粗梯形积分得 \textbf{12.88\%}。三者的差异来自求积精度与权重定义…
+ …按 $0/0.5/1.0/1.5/2.0$ cm 五点的粗梯形求积得 \textbf{12.88\%}。三者的差异来自求积精度与权重定义…

tmp/fix13r3_5_problem2.tex.before  →  paper/sections/5_problem2.tex
@@ -82 +82 @@
- …能量侧为 $7.4\times10^{-7}$、相对 $9.6\times10^{-11}$，两个场在 72 h 末的场级网格收敛量分别为 $2.4\times10^{-4}$ 与量级更小的表面格 $4.2\times10^{-6}$ kg/kg。
+ …能量侧为 $7.4\times10^{-7}$、相对 $9.6\times10^{-11}$；水分场在 72 h 末的场级网格收敛量为 $2.4\times10^{-4}$（全场最大变化），其中量级更小的表面格为 $4.2\times10^{-6}$ kg/kg。

合计：+2 / -2 行
```

逐行确认：改的第 1 行只对应判词 `q1-loss-third-caliber-label-mismatch`，
第 2 行只对应判词 `q2-convergence-subject-misattribution`。**清单外改动 = 0。**

**② 改动面自证（`python _tmp/fix13r3_change_surface.py`，逐文件 sha256 对自建基线）**

```
基线 79 个文件 → 现盘 79 个
新增 0 / 消失 0 / 内容不同 6
   ~ paper/formula-review.json                  06fc21555649 → 6b319bf62900
   ~ paper/main.log                             f064e9c6ce12 → 690616377bf7
   ~ paper/main.pdf                             7f31500c7581 → 135ab0ecb35a
   ~ paper/page-map.json                        bccf4c55be58 → eed65b208ef0
   ~ paper/sections/5_problem1.tex              5b9ffd1e8bb1 → 57eca6b7bf7f
   ~ paper/sections/5_problem2.tex              30f30115e86d → c4dc51b98268

清单外改动（paper/ 与 paper_appendix/ 内）= 0 个 （无）
```

（`main.aux` / `main.out` 重编译后***逐字节相同*** —— 交叉引用与编号一个都没动。
扫描还列出窗口内被写过的其它文件：`reports/PUBLICATION_CHECK.json`（本阶段按 SKILL 第 5 步
用 `publication report` 刷新的时刻快照）、`reports/_REVISION_DIFF.md` 与 `runtime/*`（**驱动**自己写的）、
以及 `lib/web/workflow_quality.py`（11:05）与 `regression/test_stale_noise.py`（11:03）——
后两个都**早于**本阶段 12:16:39 的开工时刻，是别处的改动，不在本轮改动面内。
`figures/`、`code/`、`results/` 与 `reports/` 下的**被审对象**（`VERIFY_REPORT.*`、`RUBRIC_REVIEW.*` 等）
**一字未动**。没有「修 A 坏 B」。**）

**③ 逐页文本层差分（`python _tmp/fix13r3_pagetext_diff.py`）—— 交付内容只变两句、零连带重排**

```
基准 main.pdf sha=80d0e196ceab6923 页数=32
现盘 main.pdf sha=135ab0ecb35a0304 页数=32
页数相同 = True
有差异的页 = [11, 14]
逐页文本完全相同的页数 = 30 / 32

--- p11 差异 ---
  replace  改前「.1」→ 改后「/0.5/1.0/1.5/2.0」
  replace  改前「输出列」→ 改后「五点」
  insert   改前「」→ 改后「求」
  delete   改前「分」→ 改后「」
--- p14 差异 ---
  replace  改前「，两个」→ 改后「；水分」
  delete   改前「分别」→ 改后「」
  replace  改前「与」→ 改后「（全场最大变化），其中」
  insert   改前「」→ 改后「为」
```

（重编译必然改 PDF 字节 —— 时间戳与 `/ID`；「内容有没有变、变在哪」只能用逐页文本层判，
见 memory [[null-recompile-changes-pdf-hash]]。）

**④ 重编译与篇幅（`xelatex -interaction=nonstopmode main.tex` 在 `paper/` 内跑两遍；`python -m lib.publication check`）**

```
pass1 rc=0   pass2 rc=0
main.pdf sha before = 7F31500C7581546D6C70275D506E9A499AF4258D8F19CDD797B84AF37E1BC3E1
main.pdf sha after  = 135AB0ECB35A0304C0A0F271B4D40456CD3ED210749B5477AB2CF6B406F52ADD

{"status": "PASS", "issues": [], "warnings": [],
 "total_pages": 32, "counted_pages": 30, "limit": 30, "over_limit": 0, "above_target": 0,
 "counts": {"abstract": 1, "body": 29, "ai_statement": 1, "appendix": 1},
 "kind_fills": {"abstract": {"fill": 0.9240825982433686, "chars": 1099}},
 "pdf_bytes": 1107181}
```

**页数没涨**（total 32 → 32、counted 30/30、over_limit 0），故无需动用 SKILL 第 6 条
「从『5 模型的建立与求解』里压缩」的兜底。

**⑤ 编译告警集合差分（`python _tmp/fix13r3_logdiff.py`；对照面 = ⑭ 收口那次编译的 `main.log`）**

```
error         改前 0 条 / 现盘 0 条 | 新增 0 | 消失 0
ref-undef     改前 0 条 / 现盘 0 条 | 新增 0 | 消失 0
cite-undef    改前 0 条 / 现盘 0 条 | 新增 0 | 消失 0
overfull      改前 0 条 / 现盘 0 条 | 新增 0 | 消失 0
underfull     改前 4 条 / 现盘 4 条 | 新增 0 | 消失 0
missing-char  改前 0 条 / 现盘 0 条 | 新增 0 | 消失 0
latex-error   改前 0 条 / 现盘 0 条 | 新增 0 | 消失 0

结论：新增告警 = 0
```

**⑥ 版式一致性（SKILL 硬约束一；`python _tmp/fix13r3_style_census.py`）**

```
基准 = 产物/各阶段产物/最新产物/排版与版式/paper/main.pdf  sha256 = 80d0e196ceab6923
现盘 = paper/main.pdf                                       sha256 = 135ab0ecb35a0304
(font,size) 组合：改前 48 个 / 改后 48 个
新增组合 = 无
消失组合 = 无
字符数变化的组合 = 3 个
   SimSun                          size=11.96  改前 17776 → 改后 17784 (+8)
   TeXGyreTermesMath-Regula        size=11.96  改前  2502 → 改后  2522 (+20)
   TimesNewRomanPSMT               size=11.96  改前  2489 → 改后  2486 (-3)
```

改动段与同节未改动段**逐项同款**：p11 的 `y0=560.5` / `y0=580.3` 与同页正文行同为
SimSun 11.96pt、续行 `x0=70.9`、段首行 `x0=94.8`、行距 19.8–19.9pt；
p14 的 `y0=629.4` / `y0=647.1` 同为 SimSun 11.96pt、`x0=70.9`、行距 19.8/17.7pt。
**没有引入任何新的字号/字体/行距/缩进**（三个组合的字符数变化正是被改写那两句本身 ——
SimSun 面是中文净增 8 字、TeXGyreTermesMath 面是新写入的 `$0/0.5/1.0/1.5/2.0$` 数学串、
TimesNewRomanPSMT 面是替换掉的 3 个 ASCII 字符）。

**⑦ 重编译作废的两处绑定 + 记录，全部按现盘重绑（`python _tmp/fix13r3_binding_diff.py`）**

```
page-map.json
  spans 逐项相同 = True
  pdf_sha256: 7f31500c7581546d → 135ab0ecb35a0304

formula-review.json
  items 数 23 → 23
  (file,line,message,decision,reason,page) 六元组集合逐项相同 = True
  pdf_sha256: 7f31500c7581546d → 135ab0ecb35a0304

reports/PUBLICATION_CHECK.json
  pdf_bytes          变化：1107147 → 1107181
  pdf_sha256         变化：80d0e196ceab6923… → 135ab0ecb35a0304…
  status: PASS → PASS | counted: 30 → 30 | total: 32 → 32
```

- `formula-review.json` 的 23 条提示项**逐条重测物理页**（`python _tmp/fix13r3_rebind_formula_review.py`，
  复用上一轮 `_tmp/fix13r2_rebind_formula_review.py` 的定位逻辑、不覆盖它）：
  **旧的登记页 23/23 全部仍落在当前 PDF 重测出的命中集合里**，
  `decision` / `reason` 原样沿用是诚实的 —— 本轮改的两句散文都不在公式提示行上。
- `page-map.json` 重绑前先核过 spans 仍属实（`python _tmp/fix13r3_pagebound.py`）：
  p1 首块 = 标题、p2 首块 = 「一、问题重述」、p30 首块 = 「缺点四：…」、
  **p31 首块 = 「八、AI工具使用说明」y=73.6**、p32 首块 = 「附录」，32 页 ⇒
  abstract 1–1 / body 2–30 / ai_statement 31–31 / appendix 32–32 原样成立，
  `bind_map` 自带的边界校验也放行。
- `reports/PUBLICATION_CHECK.json` 是**时刻快照**，重编译后必须刷新（否则它的 `pdf_sha256`
  指向一个已不存在的 PDF，见 memory [[publication-check-record-may-be-stale]]）；
  顺带修掉了它此前指向 `80d0e196…`（⑭ 之前那一版）的过期状态。

**⑧ 被改文件的字节级完整性（`python _tmp/fix13r3_bytecheck.py`）**

```
paper/sections/5_problem1.tex：13903 字节  BOM = False  控制字符 = 无  行尾 = CRLF  花括号配平 = True  $ 计数 = 186（偶数）
paper/sections/5_problem2.tex：10634 字节  BOM = False  控制字符 = 无  行尾 = CRLF  花括号配平 = True  $ 计数 = 96（偶数）
reports/FIX_REPORT.json：10857 字节，BOM = False
FIX_REPORT.json：schema_version=1 stage=fix items=10 dispositions=[fixed, fixed, deferred, out_of_scope ×5, deferred, out_of_scope]
```

（两道 memory 坑都过了：没有 PowerShell 带 BOM 的写入、没有反斜杠被转义吃掉。
报告里扫出的 4 行「裸 `%`」经逐行核对全是**既有的**表格前导 `\footnotesize\setlength{\tabcolsep}{2.4pt}%`
续行标记，与本次改动无关。）

**⑨ 逐条处置表的机器校验**：`lib/web/content_quality.py::fix_disposition_issues`
以 `required_ids = [q1-loss-third-caliber-label-mismatch, q2-convergence-subject-misattribution]`
对账本报告 —— 两条都在 `items` 里、disposition 合法、`evidence` 非空、`fixed` 两条都有 `recheck`；
其余 8 条 advisory 一并列出（对账器只查"缺"，多列不违规）。

## 需 14Layout-and-format 复看

本轮没有让版式出问题（页数、告警集合、字号字体行距三项都核过），故**无需** ⑭ 复看。
`reports/FIX_REPORT.md` 里登记的 5 条 `presentation` 类项（`ref15-subtitle`、`table-A5-pm-direction`、
`internal-term-in-tex-comments`、`paper-math-style-residual`、`orphan-figure-copies`）
都不是本轮改动引入的，⑮ 已各自写明 `why_not_blocking`，交驱动按 `TARGETS` 投递给对应阶段。

## 本轮新发现（未改）

- **无。** 本轮改动面只有两行，取证过程中未发现判词清单之外的新缺陷；
  §11.2 的场级收敛行本身（`ANALYSIS_MODELING_REPORT.md:868`）措辞与论文改后一致，无需动上游。
