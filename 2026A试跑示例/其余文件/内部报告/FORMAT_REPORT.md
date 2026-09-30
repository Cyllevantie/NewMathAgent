# 排版与版式验收报告

阶段：**14Layout-and-format**（skill `14Layout-and-format`），2026-09-30。
上游：13Repair-by-rubric-verdict（回执 `reports/RUBRIC_REVIEW.verdict.json`，`rubric_redline` failed，
驱动投递到本阶段）。本轮**只做定点版式手术 + 交付层产物，不改一句话的措辞、不改任何数值**。

## 整题结论：PASS

| 判据 | 命令 | 结果 |
|---|---|---|
| 页数口径 / 物理页映射 / A4 / 体积 | `python -m lib.publication report` | **PASS**，`counted 30/30`、`total 32`、`over_limit 0`、1.06 MB |
| 行距刚性与页边距 | `python skills/14Layout-and-format/scripts/measure_layout.py paper/main.pdf` | **PASS**（左 25.0 / 右 21.5 / 上 23.4 / 下 13.4 mm，规范行距占比 0.812） |
| 骨架与并排表 | `python lib/web/check_skeleton.py` | **PASS**（"骨架对账通过"） |
| 图件登记 / 资产 / 目检复核 | `python -m lib.visualization audit` | **PASS**（无 issue） |
| 提交清单到齐 | `_tmp/fmt_precheck.py`（`lib.delivery.checks.precheck`） | **PASS**（无 issue；`demo.html` 按 `LATE_ITEMS` 跳过） |
| 交付.pdf 右侧越界（文字层） | `_tmp/fmt_right_edge_list.py`（正文 / 附录） | 0 行越过版心右边界 |
| 交付.pdf 右侧越界（**墨迹**层） | `_tmp/fmt_ink_bbox.py`（逐页像素扫描） | 0 页越界；正文各页右边距 21.7–44.6mm、附录 21.7–23.4mm（模板值 21.8） |
| 逐页视觉验收 | 41 页逐页 PNG（`_tmp/pdf-pages/`，110 dpi） | 未见重叠 / 溢出 / 裁切 / 乱码 |

**末页清单表已填全**（回执 `appendix-manifest-table-still-placeholder` 的必做项），
正文表号已恢复连续（回执 `body-table-number-gap-no-8` 的必做项），
`AI工具使用详情.pdf` 已产出并登记。**无 HANDBACK_REQUEST**（本轮未发现内容缺陷）。

## 一、规范层核对

- **`paper/_base/` 与 `paper_appendix/_base/` 未被改动、也未绕过**：三份 `_base` 文件
  （`preamble.tex` / `macros.tex` / `math-style.tex`）与打包副本逐字节相同（`_tmp/fmt_change_surface.py`
  的 sha 对账里属"未变的 14 份"）。导言区设置与 SKILL「模板层」一节逐条对得上，
  没有在新加的 `.tex` 里手写 `\vspace` / 字号 / 行距覆盖。
- **正文都在用宏**：`paper/sections/*.tex` 里**手写 `figure` 环境 0 处**、手写 `\includegraphics` 0 处；
  图一律走 `\paperfigure` / `\paperfigurepair` / `\appfigure`。手写 `table` 浮动体 2 处
  （`5_problem1.tex:84`、`5_problem2.tex:44`）—— 那是**并排双表**的规定写法（同一个 `table` 里两个
  `\papertablehalf`，SKILL 明确"不要拆回去"），不是绕过；其余表走 `\tableblock` / `\threelinetable`，
  符号表用 `longtable`。
- `check_skeleton.py` 报 0 条问题（假设 5 条 ≤5、标题下有引入语、符号说明无开头总述段、并排表判据全过）。
  既没有"引号/解释型括号"这类措辞项需要交回 write，也没有骨架项需要改。

## 二、行距与页边距实测

```
python skills/14Layout-and-format/scripts/measure_layout.py paper/main.pdf
status PASS   pages 32   body_lines 1770   intra_paragraph_pairs 559
main_baseline_pt 19.9    nominal_share 0.812（判据 ≥0.15）
distribution: 19.9×454, 18.6×17, 30.9×16, 36.6×11, 12.2×11, 33.8×5, …
margins_mm: left 25.0  right 21.5  top 23.4  bottom 13.4      issues: []
skipped: []（样本充足，两项判据都判了）
```

- **`right` 21.5mm**：修好 p22 的公式溢出之前这里是 **0.1mm**（正文块伸到纸面右缘，
  见下「版式缺陷 #1」）。修完落到 21.5，与模板值 21.8 差 0.3mm，在 `MARGIN_TOL_MM=1.0` 内。
- `top` 23.4mm 比模板值 24.2 高 0.8mm（同样在 1.0mm 容差内）：全稿最上面那块文字在 **p18**
  （y=66.2pt=23.4mm，页首是行间公式，公式框上沿比正文首行略高），次高的 p9/p16 是 23.8mm、
  p1 是 24.0mm —— 属页首为公式时的正常浮动，未做处理。
- 附录工程（`--no-margins`，附录不判页边距）：`PASS`、规范行距占比 0.766、主行距 19.9pt。

## 三、篇幅

```
python -m lib.publication report          # → reports/PUBLICATION_CHECK.json
status PASS   total_pages 32   counted_pages 30 / limit 30
counts: abstract 1, body 29, ai_statement 1, appendix 1, references 0（并入 ai_statement 段）
kind_fills.abstract: fill 0.924（chars 1099；target 0.90 / hard 0.80）
pdf_bytes 1107147（上限 20000000）   pdf_sha256 80d0e196…
formula_hints 23（全部 retain，见下）   style_hints 0
```

- **不计入额度**的两段：八/九 合计仍为 1 页（p31），附录 1 页（p32），都不占 30 页额度。
- **没有做任何超页迁移**：正文（一～七）仍在 p2–30 的 29 页里，本轮新增的符号表 4 行与
  p22 公式拆行都被这一额度吸收（正文末页正文止于 y=730.7pt，版心底 777.6pt）。
- 未低于 `min_counted_pages=25`，不出 warning。
- 附录 A4 尺寸通过（595.3×841.9pt）、417 KB；`AI工具使用详情.pdf` 3 页、147 KB、A4。

## 四、前序回执处置

### 4.1 必做延后项（回执固定投递给本阶段，本轮必须落地）

**① `body-table-number-gap-no-8` —— 正文表号恢复连续：已落地。**
按回执要求"只改编号字符串，不动表体、数值与图件"，且**与末页清单表填全同批落地**（一次编译）：

| 位置 | 改前 | 改后 |
|---|---|---|
| `paper/sections/7_evaluation.tex:36`（表题） | 表 9 | **表 8** |
| `paper/sections/7_evaluation.tex:52`（交叉引用） | 表 9 | **表 8** |
| `paper/sections/A1_materials.tex:33`（表题） | 表 10 | **表 9** |

复验（`_tmp/fmt_final_checks2.py`，原始文本层、按行统计，不做空白剥离 —— 剥离会把
「…见表 2」与下行首的「3 处…」粘成「表23」这种伪值）：**交付 PDF 正文表号集合 = {1,2,3,4,5,6,7,8}，
缺号 0**，最大表号 8；图号 1–12 连续、附录 表A1–A5 / 图A1–A7 连续；正文里指不到表题的孤立引用 0
（"表 8" 的两处命中分别落在表题与同节交叉引用上）。

**② `appendix-manifest-table-still-placeholder` —— 末页清单表填全 + AI工具使用详情.pdf：已落地。**

- 先写 `reports/SUBMISSION_MANIFEST.json`（**20 条** items + 4 条 `exclude`），
  再由 `_tmp/fmt_gen_a1.py` **依清单生成** `paper/sections/A1_materials.tex` ——
  不让两边各抄一次（SKILL：「这份清单同时是末页清单表的来源，两边必须逐字一致」）。
- 清单条目：正文 PDF（题名）、附录A.pdf、AI工具使用详情.pdf、运行说明.md、demo.html、
  result1–4.xlsx、附件1/2.xlsx、9 个 `.py`（core / q1–q4 / run_all / sensitivity / summarize /
  validate_results）。**附件逐个有交代**：`附件1/2.xlsx` 进 items；
  `request/attachments/附件3/result1–4.xlsx` 在 `exclude` 里声明"题目给定的结果填写模板，
  提交件的 result*.xlsx 已按模板填写"（`_tmp/fmt_manifest_precheck.py` 复验"未交代：无"）。
  `desc` 逐条按该文件自己的头注释/实测写，不编。
- **末页表 = 清单的支撑材料部分**（SKILL：范围不含论文本身 ⇒ 正文 PDF 那条**不入表**）：
  19 项排成 **15 行**（同类合并 2 组：`附件1.xlsx、附件2.xlsx` 与 `q1.py、q2.py、q3.py、q4.py`，
  与用户样板同一粒度）。**为什么非合不可**：19 行 1:1 排下来整表 688pt，而「附录」标题之下
  只剩 657pt ⇒ 题注留在 p32、表体被挤到 p33（**题注与表体分处分页**，正是本 SKILL 点名的版式事故）；
  合并后整表落回 p32 一页（末行 y1=774.7 < 版心底 777.6）。**覆盖仍全**：每个文件名在「文件」格里逐字保留。
- 逐项对账（`_tmp/fmt_final_checks2.py`）：**清单里除正文 PDF 外的每一条，都能在交付 PDF 末页
  文本层里按名逐字找到，缺失 0**。末页占位符扫描：「由14Layout」「一句话说清」「生成：文件名」「<」
  命中均为 **0**。末页填充 968 个非空白字符，与用户样板的 1022 属同一量级（旧版是 56 个字符的占位符）。
- **`AI工具使用详情.pdf`** 产出于 `paper/ai_tools/`（源路径已登记在 `lib/delivery/core.py` 的
  `FIXED_SOURCES`，**没有**改那个文件）：用与正文同一套 `_base/preamble.tex` 编译，四节
  （用了哪些工具 / 用在哪些环节 / 如何核验 / 使用边界与责任），逐环节列全，并如实写明
  运行时经 Anthropic 兼容接口调用 DeepSeek 模型、数值全部由确定性程序算出。
  末页表第 1 行登记它，正文 §八「详细使用情况见支撑材料」因此有了落点（悬空引用消除）。

**③ `ai-statement-on-body-page-30` —— 取"另起一页"这条路：已落地。**

- 回执给的两条路里选**第二条**：在 `paper/main.tex` 的正文第八节之前显式 `\clearpage`。
- **为什么选它**：第一条路（认下混合页、把 `page-map.json` 里 AI 说明那段的标题改成"九、参考文献"）
  虽然零风险，但它靠的是 `boundary_page_issues` 的"起始页上找不到标记时放行"这条兜底 ——
  **声明与事实脱节却判 PASS**。第二条路让「八/九 独占 p31」成为可机械复核的事实：
  现在 p31 最上面那块文字就是「八、」，距页顶 **0.0pt**（`_tmp/fix13r2_pagebound.py` 复量），
  `bind_map` 不再走兜底。
- 取舍的代价（回执预告的"正文末页底部空出约 160 点"）**实测小得多**：正文止于 p30 的
  y=730.7pt、版心底 777.6pt ⇒ 空 **46.9pt**。原因如实写明：回执那个预估值是对**改动前**的版面
  算的，而本轮同时做了符号表 +4 行与 p22 公式拆行，正文整体下移约 130pt，把这处空白吃掉了大半。
- 复验：`python -m lib.publication check` **PASS**，`counted_pages 30 ≤ 30`、`boundary_page_issues`
  为空、`total_pages 32` 不变（与回执"两条路总页数都不变"一致）。

### 4.2 可选建议（回执标 optional，本阶段按成本决定）

**④ `adv-table-number-gap-no-8`：与 ① 同一条现象，已随之落地。**

**⑤ `symbol-table-incomplete-and-unreferenced` —— 已落地。**
在 `paper/sections/4_symbols.tex` 的表 1 **追加** 4 行（不改既有各行、不改三列三线表结构）：

| 符号 | 含义（只写是什么） | 单位（单独成格） |
|---|---|---|
| $\mathrm{Fo}_h,\ \mathrm{Fo}_m$ | 热傅里叶数 $\alpha t/R_0^2$、质傅里叶数 $Dt/R_0^2$ | 无量纲 |
| $q$ | 命题证明里的径向通量变量 $q=rD\,\partial_rC$ | m$^2$/s |
| $c$ | 扩散系数的对数导数 $c=\partial_t\ln D$ | s$^{-1}$ |
| $\lambda$ | 对数导数在解上的上确界 $\lambda=\sup c$ | s$^{-1}$ |

- 单位核对：$q$ 的量纲是 $[r][D][\partial_rC]=$ m·m²/s·(kg/kg)/m $=$ **m²/s**，
  与正文同一量在 `5_problem3.tex:25` 的积分式 $q=\int_0^rs\,\partial_tC\,\mathrm ds$ 一致（说明列里
  写的就是 $rD\partial_rC$，不是另写一个定义）。
- **标签与引用**：表 1 的编号在本文是手工字面（全篇 9 张表同一写法），没有 `\caption` 计数器，
  所以挂了一个只服务本表的 `\newcounter{symtab}` + `\refstepcounter` + `\label{tab:symbols}`，
  并把正文那处早就存在的「表 1 的符号一律以米计」由字面改成 `表~\ref{tab:symbols}`。
  这不是新增措辞（那句话原本就在），是把字面编号换成可随编号重排而自动跟随的引用。
  复验：交付 PDF 该处渲染为「表 1」，全稿 `??` 未解析引用 **0 处**。
- 未越页：`measure_layout` 与 `publication check` 均 PASS，`counted_pages` 仍 30。
  符号表在 p6→p7 断页**不是本轮引入的**——打包副本（编辑前）同样在 p7 首页以「C₀ 初始干基含水率」
  起头，两版逐块比对一致。

**⑥ `budget-ratio-caliber-not-reproducible` —— 核查了，本轮**不改**，登记为未处理项（见第六节）。**
自行复算证伪了证据本身：分子 7.0 h / 分母 0.5 h 给 14、7.5/0.5 给 15，而上端 25 只有换成
单参数 $D$ 的 +12.7 h 才凑得出（12.67/0.5 = 25.3）—— 回执这一条**属实**。但它是
`category=claim` 的**措辞**改动（四处正文 + 上游 `reports/ROBUSTNESS_REPORT.md` 同一句），
按 SKILL「不改一句话的措辞（→ write）」与回执自己的成本说明（口径的最终归属在 analysis 的
报告层措辞通道），**不在本阶段职权内**，故不动。

## 五、版式缺陷与修复

| # | 位置(页/文件:行) | 现象 | 修法 | 复验 |
|---|---|---|---|---|
| 1 | `paper/main.pdf` p22 / `5_problem4.tex:32-40` | 三点边界条件挤在同一个 `equation` 里用 `\qquad` 相连，**溢出到纸面右缘**：该行 x1=594.9pt，正文块右边距 **0.12mm**（模板值 21.8mm），`measure_layout` 判 FAIL | 改 `gather` 每行一条（与 `5_problem1.tex` 定解条件同一写法），前两行 `\notag` ⇒ 编号总数不变、附录 `\setcounter{equation}{16}` 不用改 | `measure_layout` **PASS**（right 21.5mm）；`_tmp/fmt_right_edge_list.py` 0 行越界；式(13) 三行居中、编号在末行，p22 目检正常 |
| 2 | `paper_appendix/main.pdf` p1 / `A_appendix.tex:6-11` | 式(17) 两个等价写法挤在一行，**超版心右边界 31.75pt（11.2mm）** | 同上改 `gather`（前置 `\notag`），编号仍为 (17) | 附录右侧越界行数 0；公式编号仍 17–27、与正文 1–16 接续 |
| 3 | `paper_appendix/main.pdf` p2 / `A_appendix.tex:39` | 表 A1 的 `tabular` **没加 `@{}`**，每列两侧各留一份 `\tabcolsep(8pt)`、3 列即 48pt 固定开销；Σp 宽 0.92\textwidth 时总宽 473.7pt > 版心 462.7pt ⇒ 表内文字右缘 536.3pt（超 2.7pt）、三线右端 535.0pt | 中间列 `p{0.52}`→`p{0.50}`（总宽 464.1pt，横线仍长出 1.4pt）⇒ 再收到 `p{0.49}`（459.5pt） | 表内文字右缘 **527.1pt**、三线右端 **531.9pt**，整张表连同三线落在版心内；表 A1 仍三列、仍在 p2 一页 |
| 4 | `paper_appendix/main.pdf` p3 / `A_appendix.tex:120` | 表 A4 的列宽由表头「水分（21 个距离列）/kg/kg」撑出，右缘 540.2pt（超 6.6pt） | 首列 `p{0.42}` → `p{0.36}`，整表左移 27.8pt | 右缘回到版心内；表 A4 仍 4 行、仍在 p3 一页 |
| 5 | `paper/sections/A1_materials.tex` 全表 | 整表是模板占位符（56 字符）；且 19 行 1:1 会**题注与表体分页** | 依清单生成表体；同类合并 2 组压到 15 行；列型由 `p{}` 改 `L{}`（`p` 的中文列两端对齐会把长串拉出大空隙） | 末页一页装下（末行 y1=774.7 < 777.6）、占位符命中 0、逐项同名 0 缺 |
| 6 | `paper/main.tex:90-104` | p30 是「正文 + 八」的混合页，`page-map` 声明与事实脱节（见 4.1③） | 正文第八节前显式 `\clearpage` | p31 首块 = 「八、」（距页顶 0.0pt）、check PASS、总页数不变 |
| 7 | `paper/_base/*` 未动 | —— | 本轮没有改任何导言区设置 | 三份 `_base` 与打包副本 sha 相同 |

**"没改数"的机械举证**（`_tmp/fmt_numeric_diff.py`，用数值字面量集合代替逐行 diff、对格式重排免疫）：
1_restatement / 2_analysis / 3_assumptions / 5_problem1 / 5_problem2 / 5_problem3 / 6_check
**七份逐字面量集合完全相同**；有差的五份逐条裁决都是**注释或编号**——

- `7_evaluation.tex`：唯一变化是字面 `9` → `8`（本次的表号返修）；
- `4_symbols.tex`：新增字面量只有 `9`（来自新加的注释「全篇 9 张表同一写法」），表体的 4 行新符号不含数字；
- `5_problem4.tex`：新增 `16 / 21.8 / 22`，全部出自新加的注释（式号、页边距模板值、页码）；
- `A1_materials.tex`：整文件本就是占位符，被清单内容替换（新增的都是清单里的既有事实数）；
- `A_appendix.tex`：新增 13 个字面量全部出自新加的注释（列宽与越界量测值）。

⇒ **交付面上没有一个数值被改动。**

## 六、未处理项

| # | 事项 | 为什么不能在本阶段处理 | 应交回 |
|---|---|---|---|
| 1 | 回执 `budget-ratio-caliber-not-reproducible`：把「比数值预算大 15 至 25 倍」的分子分母写成同口径、四处统一（摘要 / 问题三数值口径段 / 6.2 灵敏度 / 7.2 缺点四） | 属 `category=claim` 的**措辞**改动，本阶段不改一句话的措辞；且回执自己写明口径的最终归属在 analysis 的报告层措辞通道（要它与 `reports/ROBUSTNESS_REPORT.md` 同一句同批确定），否则论文与上游报告各写一个数。本轮已自行复算确认回执属实（见 4.2⑥），但**只登记不改** | **analysis**（定口径）→ **write**（四处落地） |
| 2 | 表 1 断页后**表头不重复**（`longtable` 的 `\endfirsthead`/`\endhead` 之间是空块，续页无「符号/含义/单位」表头行） | 模板原件就是如此（`4_symbols.tex` 的 `\endfirsthead`/`\endhead` 为空块），**不是本轮引入**；打包副本同样在 p7 断页续排。补一段重复表头会再加 1 行、有把符号表推出当前排布的风险，属"可改可不改"，本轮按"只做定点手术"不动 | 记此备查（若后续要改，归 write/format 同批） |
| 3 | `paper/_base/preamble.tex` 第 89–91 行注释称符号表"自动重复表头"，与 #2 的实际行为不符 | 同上：这是**模板注释**与模板实现的出入，改注释属版式层，但改它不会改变任何交付面，且本轮已在 #2 如实登记 | 记此备查 |
| 4 | 正文 p14 有 1 行两端对齐的文字右缘超出 0.30mm（x1=534.5 vs 版心 533.6） | 小于半个汉字宽，属两端对齐的舍入；`measure_layout` 的 1.0mm 容差判 PASS | 不处理 |
| 5 | 收口打包**之前**，`提交作品/最新作品/` 里会短暂留着上一轮临时包的 `附件3_result1–4.xlsx` | 这是 `lib/delivery/core.package()` 的 `_carry` 行为：`allow_missing=True`（阶段性打包）时，旧包里**本轮没产出**的名字会被原样搬过来 —— 而它们在**本轮清单里被 exclude 了**（题目给的填写模板，不必重复提交）。**正式交付那次 `package(final=True)` 不带 `allow_missing`，staging 从清单从零建起、`_carry` 为空** ⇒ 收口包里不会有它们，`check()` 的白名单判据成立。中途没有任何门禁跑 `check`（⑮ 只跑 `precheck`，驱动在它的 `recheck` 里也写明"仅收口打包后"可跑），故只在链中途提前停下、有人去翻那个文件夹时可见 | **不需要本阶段处理**；如实登记以免下一个看包的人误以为清单漏了它们 |

## 七、逐页视觉验收

- 交付 PDF **41 页全部渲染**（`_tmp/pdf-pages/` 固定目录，110 dpi，与 ⑮ 共用；正文 32 张
  `body-*.png`、附录 9 张 `app-*.png`），逐页目检。
- **逐页未见**：表格叠印（表题压表头）、单元格文字重叠、图/图题/公式编号与正文重叠、
  公式越界、孤立残行、标题被裁切、中文缺字乱码。
- 重点复核的几处：
  - p6–p7 符号表两行表头/三线表结构未变，新增的 $\mathrm{Fo}$/$q$/$c$/$\lambda$ 四行与既有行同字号同行距；
  - 两对**并排双表**（p11 表2/表3、p14 表4/表5）的两行表头：标题行与子表头行不叠印、
    行标签纵跨两行、`\cmidrule` 只走数据列（判据来自 SKILL「两行表头」一节，机器查不出，逐页看）；
    单张的数据表（p19 表6、p24 表7、p30 表8）同一条目照查；
  - **墨迹层**复核（文字层扫描之外另做的一道）：`get_drawings()` 在附录 p6 报告了一条到 x=548.25pt 的斜线
    （超版心 14.6pt），但那是 matplotlib axes 的**裁剪路径之外**的几何 —— 渲染出来那一带是纯白。
    ⇒ 加了一道以**像素**为判据的 `_tmp/fmt_ink_bbox.py`（逐页找最右墨迹列）：两个 PDF 共 41 页
    **无一页越界** —— 正文各页右边距 21.7–44.6mm（p3 是整页流程图，两侧留白天然更大）、
    附录各页 21.7–23.4mm、末页清单表所在页 25.3mm，与模板值 21.8mm 相符。这条也说明"越界"的
    两个机器判据各有盲区（文字块扫描看不见图，`get_drawings` 看不见裁剪），
    只有像素才是读者看得见的东西；
  - p22 式(13) 三行居中、编号在末行、左右都在版心内；
  - p30 末页正文收尾处底部空 46.9pt（`\clearpage` 的代价，见 4.1③），不是异常大空白；
  - p31 八/九 独占一页；p32 末页清单表题在表体正上方、15 行逐行可读、不跨页；
  - 附录 p1–p9：式(17) 两行、表 A1–A5 与图 A1–A7 位置与编号正确，无越界。
- 页脚页码连续（1–32 / 1–9），无 `??`、无空白页。

## 八、本轮产物与绑定

| 产物 | 说明 |
|---|---|
| `paper/main.pdf` | 32 页，`sha256 80d0e196…`，1 107 147 bytes（= 提交件"基于变物性耦合传热传质与材料坐标的圆柱形药材烘干模型.pdf"） |
| `paper_appendix/main.pdf` | 9 页，`sha256 9c2152f7…`，417 537 bytes（= 提交件 `附录A.pdf`）；`\setcounter{equation}{16}` 经复量仍正确（正文公式仍 16 个，附录编号 17–27 与正文接续） |
| `paper/ai_tools/AI工具使用详情.pdf` | 3 页，`sha256 9a9f1ebe…`，147 474 bytes（本轮新产出） |
| `reports/SUBMISSION_MANIFEST.json` | 20 条 items + 4 条 exclude（本轮新产出，打包依据 + 末页表来源） |
| `paper/sections/A1_materials.tex` | 由 `_tmp/fmt_gen_a1.py` 依清单生成（末页清单表，表 9） |
| `运行说明.md` | 四段：文件准备 / 安装依赖（抄 `requirements.lock.txt` 的精确版本）/ 运行程序 / 补充计算；文件清单用**平铺后**的名字 |
| `paper/page-map.json` | 重绑到 `80d0e196…`（spans 未变：abstract 1 / body 2–30 / ai_statement 31 / appendix 32） |
| `paper/formula-review.json` | 重绑到 `80d0e196…`；23 条提示项按**行文本**匹配（`5_problem4.tex` 行号因本轮改动平移 +2），判词全部 `retain` 并逐条复量物理页 |
| `reports/PUBLICATION_CHECK.json` | 本轮 `report` 全量重写，status=PASS |

**改动面自证**：`_tmp/fmt_change_surface.py` 对 20 份 `.tex` 逐份比 sha ——
**只有 6 份变**（`paper/main.tex`、`paper/sections/{4_symbols,5_problem4,7_evaluation,A1_materials}.tex`、
`paper_appendix/sections/A_appendix.tex`），其余 14 份（含全部 `_base`、`paper_appendix/main.tex`、
`5_problem1/2/3`、`6_check`、`1_restatement`、`2_analysis`、`3_assumptions`）**逐字节未动**。
对照面 = 打包副本 `产物/提交作品/最新作品/其余文件/{正文,附录}/`，其 `正文/main.pdf` 的 sha
仍等于 `page-map.json` 里记的旧值 `f2a4b36e…`，可确认它确实是本轮编辑前那一版。

**探针复用**：本轮先重跑了上一轮留下的 `_tmp/fix13r2_pagebound.py`（页边界）与
`_tmp/fix13r2_rebind_formula_review.py` 的判定逻辑（重绑脚本按本轮改名另存为
`_tmp/fmt_rebind_formula_review.py`，不覆盖上一轮取证件）；本轮新写的探针一律留在 `_tmp/`：
`fmt_margin_overflow.py`、`fmt_overflow_scan.py`、`fmt_right_edge_list.py`、`fmt_ink_bbox.py`、`fmt_page_dump.py`、
`fmt_xlsx_facts{,2}.py`、`fmt_manifest_precheck.py`、`fmt_gen_a1.py`、`fmt_make_spec.py`、
`fmt_pubcheck_view.py`、`fmt_final_checks{,2}.py`、`fmt_precheck.py`、`fmt_change_surface.py`、
`fmt_numeric_diff.py`、`fmt_render_pages.py`。原样保留，下一轮可直接复用。
