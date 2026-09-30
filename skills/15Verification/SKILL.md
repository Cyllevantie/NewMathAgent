---
name: 15Verification
description: "数学建模竞赛最终验证和验收阶段，针对 LaTeX（xelatex）论文。用于论文写完后检查章节数量、标题顺序、图表引用、数值一致性、占位符、内部文件泄露、参考文献、代码可复现性、编译和提交就绪状态。"
allowed-tools: PowerShell, Read, Write, Edit, Grep, Glob, Agent, WebSearch, WebFetch
---

# 验证和验收（LaTeX）

> 通用执行纪律（增量返修 / 缩比预估 / 分段落盘 / 方法标记 / 返修只动清单内）见 `../_references/stage_discipline.md`。
> 本阶段适用：一（增量返修，含 1.1 探针复用）、五（返修只动清单内）、六·6.1（先落骨架再深挖）。
> 探针/量测脚本要复用（通用纪律 一·1.1）：本轮写的取证/量测脚本一律留在 `_tmp/`
> （另有散落的在 `tmp/`，两个都要看）；下一轮开工第一步 = `ls _tmp/ tmp/` → 把上一轮
> 为同一批对象写过的脚本先原样重跑（秒级，确认数在当前版本里还成立）→ 只对本轮新出现或改过
> 的对象写新脚本。别每轮从零重写 —— 全链 776 个自写脚本里 **683 个（88%）只被用过一次**
> 就再也没人碰。复用探针 ≠ 跳过复核：探针只是取证手段，判定仍逐条对着当前版本做。

本 skill 是验收门禁。其后还有三段：`12Rubric-final`（评分标终审）→ `13Repair-by-rubric-verdict`（按评分判词返修）
→ `16Web-demo`（交互式 Demo，整链最后一阶段）。它不重新建模、不生成新结果、不代替写作阶段重写论文；
它负责发现硬错误、提出具体返修要求，并输出 `reports/VERIFY_REPORT.md`。

> 分工：本阶段查硬错误（编译/结构/图表引用/数值一致/泄漏/视觉），
> `12Rubric-final` 查评委视角的评分与合规（适配性/创新/AI痕迹/匿名/获奖预测）。
> 两者不重复：`12Rubric-final` 只读本报告的结论，不重跑本阶段的检查。

Web 裁决侧车（content-quality 启用时）：另写 `reports/VERIFY_REPORT.verdict.json`（v2；本阶段必查 ID 由驱动注入：task_fidelity/optimality/proof_applicability/narrative_consistency/figure_coverage/content_coverage）。结构、category 路由与锚点要求见 `docs/CONTENT_QUALITY.md`「问题分类与机器裁决」——把「原题要求 → 模型 → 结果 → 图文成稿」逐项闭合：题面每条硬条件与交付都须在成稿可核验；**不得以「已写入局限/免责声明」替代正确性**，未证最优不得称最优。 报告末尾裁决行与 JSON `status` 必须一致；程序校验不通过一律 UNVERIFIED，重试或披露不构成放行。

## 结构化数值与独立校验

本阶段：`python -m lib.result_contract audit --rendered`（只读审计成稿数值）；不补写被审结果。

## 国赛提交规范

国赛电子版：不要目录、摘要首张连续编号、附录完整代码及支撑清单、论文与支撑包分别限 20MB、身份匿名化。其他赛事依据明确规则另设口径。

## 正文编辑复核

逐项检查问题重述、材料到位状态、约束逐行排版和高密度图；按成稿页码记录证据——模板加载不代表排版合格。

## 几何表达与篇幅排版

最终验收读取项目根目录 docs/PUBLICATION.md，只读运行 python -m lib.publication check；核对页面类别与实际内容，逐页检查公式及图表。超限、映射过期或无法计数不得 PASS。报告指出需返修的内容与位置，不自动删论文。

## 通用绘图协议

读取项目根目录 `docs/VISUALIZATION.md`，只读运行 `python -m lib.visualization audit`，并逐张检查论文嵌入后的最终尺寸、图注、正文引用与 included 标记。VERIFY_REPORT 记录页码与实际发现；证据过期、缺失或未完成目检时不得 PASS。Web 审查只写本阶段报告及裁决，修复交前序。

## 数学建模规范参考

如需领域判断，读取 `../_references/math_modeling_norms.md` 中的"论文验收与一致性"小节。该文件只是规范知识库，不是固定执行流程；具体目录、入口文件、结果文件和图表目录由当前项目结构决定。

## 阶段边界

- 本阶段负责：结构验收、文本质量门禁、图表引用检查、结果一致性检查、LaTeX 编译检查、PDF 视觉检查、提交清单。
- 本阶段不负责：重新设计模型、重新跑大规模实验、重新组织整篇论文。
- 发现硬错误时，在 `reports/VERIFY_REPORT.md` 指明修复位置、方法和前序阶段，并标记未通过；审查不修改被审查对象。

## 输入

由模型先根据当前工作区判断项目布局，再把实际路径传给检查脚本。常见输入包括但不限于：

1. 论文入口文件：`main.tex`。
2. 正文章节目录或若干正文文件（`.tex`）。
3. 参考文献文件（`references.tex`）。
4. 前序阶段的分析、建模、结果、图示报告。
5. 图表目录
6. 可复现代码目录。
7. 编译后的 PDF，或可由入口文件编译得到的输出 PDF。

不要假设论文目录一定叫 `paper/`，也不要假设结果文件一定在项目根。若项目使用不同命名，按实际结构传参并在 `reports/VERIFY_REPORT.md` 中说明。

## 执行方式（关键：维度拆开，别堆在一个上下文里）

开工第一步：先落骨架（§六·6.1）——写 `reports/VERIFY_REPORT.md` 与 `reports/VERIFY_REPORT.verdict.json`
（`status=UNVERIFIED`、`issues: []`），**不要等查完再写**。本阶段是全链审查面最大的一关，
子 agent + 逐页看图极容易吃光整段时间；产物留到最后写，一旦跑到没气现场就是一片空白 ——
驱动只报「阶段未成功完成：failed」，读不出任何结论。骨架是占位不是结论，每查完一个 Step 必须回填。

本阶段是全链审查面最大的一关（9 个 Step、13 类硬错误，横跨结构/图表/写作质量/泄漏/
数学闭环/数值一致性/参考文献/编译/PDF 视觉）。`3Modeling-review-gate` 的做法值得照搬，理由它写过：

> **不要在一个上下文里同时审「数学 + 题意 + 机理 + 数据」四件事** ——
> 审查维度堆在一起会互相稀释，每个都审不深。

所以：用 Agent 工具按维度 spawn 独立子 agent，各写各的结论，本会话只做汇总与写报告。

| 子 agent | 只负责 |
|---|---|
| `verify-structure` | Step 2 章节结构与标题顺序、Step 3 图表与章节匹配 |
| `verify-text` | Step 4 写作质量与三重泄漏（占位符 / harness 词 / LaTeX 命令泄漏 / 程度词-数据一致性） |
| `verify-math` | Step 4b 数学论证措辞-内容扫描、Step 5 数值与结果一致性、公式质量与定义式复算 |
| `verify-build` | Step 1 文本门禁脚本、Step 6 引用与模板、Step 7 编译、Step 8 逐页视觉检查 |

每个子 agent 只输出它那一维的 `PASS/FAIL + 证据（文件:行）+ 修法`，**禁止越界评其它维度**。
汇总时任一维 FAIL 即整题 FAIL —— 但要写清是哪一维、卡在哪一条硬错误。

**视觉检查（Step 8）不要分包**：逐页看图必须由有视觉能力的那一个上下文亲自看完，
转述会丢掉「看起来不对」的那类信息 —— 而那恰恰是纯文本扫描唯一抓不到的东西。

**不要自己造重算脚本去验证子 agent 的结论**——那是子 agent 的活，而且它会串行烧掉你在
关键路径上的时间（门禁里只有报告不可替代，你的复算有替代品）。抽查只验子 agent 给出的
具体数字，用几分钟内跑得完的短脚本。

## 工作流程


### Step 1: 运行文本质量门禁

优先运行本 skill 的脚本。脚本针对 LaTeX 论文执行检查：`--main` 默认 `<paper-dir>/main.tex`，`--references` 默认 `<paper-dir>/references.tex`，章节按 `.tex` 扫描，编译用 xelatex 跑两遍。

```bash
set -o pipefail
mkdir -p _tmp
SCRIPT_PATH="<按当前 skill 实际位置确定>/scripts/writing_check.sh"
bash "$SCRIPT_PATH" \
  --paper-dir "$PAPER_DIR" \
  --main "$MAIN_FILE" \
  --sections-dir "$SECTIONS_DIR" \
  --references "$REFERENCES_FILE" \
  --figures-dir "$FIGURES_DIR" \
  --results-file "$RESULTS_FILE" \
  --problem-analysis "$PROBLEM_ANALYSIS_FILE" \
  --all-results "$ALL_RESULTS_FILE" \
  | tee _tmp/writing_check.log
```

如果本 skill 被复制到其他目录，使用实际脚本路径。可以先运行 `bash <script> --help` 查看参数。不要把脚本路径、论文目录或文件名写死在验收逻辑中。

脚本只扫描文本，不生成论文，也不编译 PDF。它的 `FAIL` 属于硬错误，必须修复后重跑。

### Step 2: 章节数量和标题顺序

检查：

- 入口 `.tex` 文件中 `\input{...}` 或 `\include{...}` 的数量是否与实际正文结构匹配。
- 章节顺序是否符合文件名前缀顺序。
- 每个 section 是否有 `\section{}` 或对应级别标题。
- 标题顺序是否符合所选论文类型。
- 章节文件是否缺失、重复引用、未被引用。
- 如果题目不是三问，不强行要求三段问题章节；按 `ANALYSIS_MODELING_REPORT.md` 的子问题数量核对。

### Step 3: 图表和章节匹配

检查：

- 图表目录中的 PDF 是否在正文中被引用。
- `\includegraphics{}` 引用的图片是否存在；按 LaTeX 编译工作目录解析路径，不能按被 input 的章节文件目录解析。
- `\caption{}` 是否存在。
- 数据图是否放在对应结果/分析章节，非数据流程图是否放在方法/总体思路章节。
- 连续图表之间是否有足够解释文字。
- caption 是否过长、过泛或与图意不一致。
- 图表编号、正文引用和章节语义是否一致。

不要生成 `*_latex_includes.tex`；图表必须直接嵌在对应 section 中。

### Step 4: 写作质量和泄露检查

检查并修复：

- `TODO`、`PLACEHOLDER`、`待补充`、`待续写`、`示例数据` 等占位符。
- 论文正文出现内部工作流文件名、临时目录名、代码目录名或结果 JSON 路径。
- 过多列表式写作（大量 `\begin{itemize}`、`\begin{enumerate}`）。
- 段落反复以"如图""由图""图 X 展示了"开头。
- 图表后没有解释、公式后没有变量含义、结论只报数不解释。
- LaTeX 命令泄漏字面：扫编译产物/源里正文是否出现应渲染而未渲染的 LaTeX 原样字面，如 `arraybackslash`、`\hline`、`\\`、裸 `&`、`\ref`/宏名出现在正文文本中（用 pdftotext 导文本搜 `\\`、`array`、`hline` 等）→ 出现即硬错误（列格/转义 bug 的直接观感事故）。
- 程度词-数据一致性：扫"完整链/完整/全覆盖/无空档/有利/最优/全局最优/显著"等绝对化词，与对应数据/图表对照：带时间空档却称"完整遮蔽链"、称"有利组合"但结果为负向、称"全局最优"实为 best-known、称"全覆盖"但判据只统计单体独立等 → 不一致即硬错误（对照 norms 最优性分级/判据 scoping）。

- 内部代号/版本串残留（对最终 pdf 复扫，防"tex 干净但 pdf 是旧构建"漏检）：把提交/归档用的最终 pdf 用 `pdftotext` 导出纯文本，对照 `../_references/internal_leak_words.md` 的【内部词 deny】复扫——命中阶段/流程代号（9Paper-writing/6Robustness/…）、内部用例标签（C16/A5/H7/N3/…）、内部版本口径串（v1.1.1/M-2 口径/…）、内部路径（code/outputs/…json、RESULTS §x）→ 硬错误（对照【题内合法词 allow】避免误伤 M1/FY1/Q1 等题目自带编号）。对账/校验数据若进正文或附录，必须改语义列名（如"算例/场景"而非 C16），不得带内部标签。若 tex 无而 pdf 有 → 先重编译再判（残留多半来自已删的中间稿）。
- 算法超参与复杂度（对照提交代码）：元启发/迭代算法（DE/GA/PSO/SA/禁忌/B&B…）是否在正文或附录给出"算法名 + 关键超参（DE 的 mutation(F)/CR/种群/最大迭代/多起点初值/收敛 tol）+ 复杂度一句"；超参须与提交代码一致（从代码抄写，不许写默认值）→ 缺即硬错误。
- 公式质量（脚本 `writing_check.sh` 已扫，须在 VERIFY_REPORT 记录结论）：① 正文/公式用到的符号必须都在符号表（脚本给 missing 列表）→ 缺即硬错误；② 符号表条目须在正文被用到 → 未用即 WARN；③ 论文多处出现的大数若只差末 1–2 位 → 必须回查是否笔误（脚本给疑似对）→ 确认笔误即硬错误；④ **凡正文给出指标定义式（如 gap=(UB−π)/UB），必须按该式复算表中至少一个数字**并在报告记录复算结果 → 不符即硬错误（2024C 实际发生过：定义式与所报数字口径不一致，评审一算即穿）。
- 摘要页/关键词/灵敏度可视化：CUMCM 摘要页 ≤1 页（溢出即硬错误）、**且版心填充 ≥0.90**（`python -m lib.publication report` 的 `min_kind_fill`；< 0.80 是硬失败、由机械地板直接判给 ⑨，[0.80,0.90) 只出提示）——摘要写没写满不是本阶段能改的（版式无权动文字），所以发现欠写就如实判，别自己补字；关键词 ≤6；灵敏度章节若整节纯数字表无任何图 → WARN 并尽量补 1 张可视化（对照 norms「摘要写作要点/灵敏度可视化」）。

### Step 4b: 数学证明措辞-内容一致性扫描（L2，硬错误项）

对 `main.tex` 与 `sections/*.tex` 逐文件扫标签/强声称词：
`定理|命题|引理|推论|性质|证明|证明了|严格相同|严格一致|正交|一阶无偏|无偏|恒成立|已证`
对每个命中，检查同小节内是否存在等式级推导块（`equation`/`align` 环境或成块 `\[…\]`）来支撑该断言；仅靠"合成谱自检/拟合数值/图表/自然语言叙述"的 → 记为该小节"证明字样无推导块"，列 `数学论证闭环` 检查项并判硬错误（除非该断言已显式自标为"数值观测/经验断言/仅报告量级"，不作证明宣称）。同时在摘要区同样扫一遍：摘要称"证明了…"而正文无推导 → 硬错误。判 FAIL 时在"仍需处理的问题"写明文件/行与缺什么，把结论交回写作修复（本阶段不改论文）。

### Step 5: 数值和结果一致性

检查：

- 论文中的关键数值必须来自当前工作流声明的结果记录或结果 JSON。
- 目标函数值、误差指标、排名、权重、阈值、灵敏度结果不得与结果记录冲突。
- 如果存在汇总结果 JSON，抽取关键指标并确认论文正文中有对应结果。
- 公式中的符号应在符号说明或正文首次出现处解释。

发现数值冲突时，不要自行发明新结果；应回到结果记录或代码输出修正论文。

### Step 6: 引用和模板规范

检查：

- 参考文献文件是否存在，或模板是否采用了其他真实参考文献机制。
- 正文引用标记（LaTeX 的 `\cite{}`）是否能对应到真实参考文献。
- 中文论文 caption、表题、摘要语言保持中文；英文论文保持英文。
- 选定的模板入口是否保留所选比赛模板的必要封面、摘要、编号、页眉页脚或提交格式。
- 不要把模板结构误删成普通空白文档。


参考文献真实性核验（best-effort 门禁，防虚构/张冠李戴）：从参考文献文件（`references.tex`/`thebibliography`）提取每条题名与作者，对非经典、非网址、非标准/规范类条目做 Crossref 抽查（每条 1 次请求）：

```bash
curl -s --max-time 25 "https://api.crossref.org/works?rows=1&query.bibliographic=<题名作者>"   # 或已知 DOI 直接 api.crossref.org/works/<DOI>
```

命中且题名/期刊/年份一致 → 在 VERIFY_REPORT 记 "已核验 DOI: …"（可顺手建议把 DOI 补进文献表）；解析不到 → 记"待人工核验（知网/期刊官网）"，**不要凭"标题像定制"就自动删**——以检索结果为证。无网络时整项跳过并在报告注明，不判 FAIL；仅当能联网且条目确无任何期刊/会议可对应（疑似捏造）时判 FAIL。

### Step 7: 编译

```bash
command -v xelatex >/dev/null 2>&1 && xelatex -interaction=nonstopmode "$MAIN_FILE" && xelatex -interaction=nonstopmode "$MAIN_FILE"
```

xelatex 需跑两遍解决目录和交叉引用。

编译失败必须修复语法、路径、图片引用或模板问题后重跑。编译通过后确认输出 PDF 非空。

### Step 8: PDF 视觉检查

如果模型有视觉能力，必须把编译后的 PDF 每页导出为 PNG 并逐页查看。这个步骤用于发现纯文本扫描和编译器无法发现的版式错误。

优先使用系统已有工具导出页面 PNG；不要为了视觉检查引入沉重依赖。可选命令示例：

**先看 `_tmp/pdf-pages/` 有没有现成的**：⑭排版与版式 的逐页视觉验收渲的是同一个目录
（`_tmp/pdf-pages/`）⇒ 若 PDF 没变（比 `paper/main.pdf` 的 SHA，或看 `python -m lib.publication check`
的绑定状态），整批复用、别自己再渲一遍（两阶段各渲一遍，三轮下来 `tmp/` 里会积下成百张 PNG）。
只有 PDF 变了才重渲，且只渲**改动页 + 抽检 2–3 页**。

```bash
mkdir -p _tmp/pdf-pages
if command -v pdftoppm >/dev/null 2>&1; then
  pdftoppm -png -r 160 "$OUTPUT_PDF" _tmp/pdf-pages/page
elif command -v mutool >/dev/null 2>&1; then
  mutool draw -r 160 -o _tmp/pdf-pages/page-%03d.png "$OUTPUT_PDF"
elif command -v magick >/dev/null 2>&1; then
  magick -density 160 "$OUTPUT_PDF" _tmp/pdf-pages/page-%03d.png
else
  echo "No PDF rasterizer found; record visual check as not run."
fi
```

导出后逐页检查：

- 页面是否空白、缺页、页数异常或页面尺寸异常。
- 标题、摘要、正文、页眉页脚、页码是否被裁切或位置明显错误。
- 表格是否超出页边距，单元格文字是否重叠、溢出、被截断。
- 图片、图题、表题、公式、编号是否与正文重叠。
- 公式是否越界，长公式是否压到页边距或下一段文字。
- 列表、段落、脚注、参考文献是否出现异常大空白、重叠或孤立残行。
- 中文/英文/数学符号字体是否明显缺字、乱码或 fallback 异常。
- 封面、摘要页、目录、附录等模板关键页面是否保留比赛要求的视觉结构。

如果是模板转换或已有参考 PDF 的项目，还应将本稿 PDF 与参考 PDF 都逐页导出 PNG，按页对比版式差异；页数或页面尺寸不一致必须记录为硬错误或明确说明原因。

如果模型没有视觉能力，必须在 `reports/VERIFY_REPORT.md` 中明确写出“未执行视觉检查”的原因，并至少完成 PDF 非空、页数、页面尺寸等可程序化检查。

### Step 9: 写验收报告

创建 `reports/VERIFY_REPORT.md`：

```markdown
# 验证和验收报告

## 结论
PASS / FAIL

## 检查项
| 检查项 | 结果 | 说明 |
| --- | --- | --- |

## 章节结构

## 图表引用

## 数值一致性

## 数学论证闭环

## 文本质量门禁

## 编译

## PDF 视觉检查

## 仍需处理的问题
```

只有当硬错误都修复、文本门禁通过、核心图表都引用、数值一致、编译通过或明确说明不可编译原因、视觉检查通过或明确说明无法执行原因时，才写 `PASS`。

## 硬错误标准

以下问题必须判定 `FAIL`：

- 缺少论文入口文件（`main.tex`）或核心正文。
- 论文入口引用的章节文件不存在。
- 入口缺少 `\input`/`\include`。
- 正文章节缺少标题（`\section{}` 缺失）。
- 章节顺序明显错误或重复。
- 正文仍有占位符。
- 正文泄露内部工作流文件名。
- 以"定理/命题/引理/证明"命名或声称"证明了…"的对象，其小节内无等式级推导、仅以数值/图表/合成谱充当证明（见 Step 4b）。
- 引用的图片不存在。
- 关键数值与结果记录冲突。
- 编译器可用但论文编译失败。
- 编译后的 PDF 为空、缺页、页数异常或页面尺寸异常且无法解释。
- 视觉检查发现正文、表格、图片、公式、页眉页脚、页码等关键元素重叠、裁切、越界或乱码。
- 最终提交/归档 pdf（pdftotext 复扫）检出内部代号/阶段名/内部版本口径串/内部路径残留（对照 `../_references/internal_leak_words.md` deny 词表），或正文算法节缺失关键超参与复杂度且无附录可查。

## 警告标准

以下问题可判定为 `WARN`，但应尽量修复：

- 未引用的备用图片。
- 某章节过短或明显不均衡。
- caption 偏长。
- 参考文献偏少。
- 图表后解释文字不足。
- 视觉检查工具不可用，但已经记录原因并完成基础 PDF 元数据检查。
- 代码完整复现耗时过长，只做了轻量检查。

## 动态交回规则（发现前序阶段错了）

若发现**论文数值与 `code/outputs/*.json` 或结果记录不符，而根子在代码/结果本身错了**（不是论文抄错）—— 本阶段只审不改，也不是重算的地方。
若只是论文抄错，直接写进 VERIFY_REPORT 的返修清单（默认回退目标是 14Layout-and-format / 9Paper-writing）。

创建 `reports/HANDBACK_REQUEST.md`：

```
target: <code | robustness | analysis | drawio | write | format>
reason: <一句话说清：哪里不对、期望改什么>
```

然后**停止本阶段并结束本轮**（不要继续往下做，更不要编造数值把坑填上）。
编排器会把它作为**回退建议**交给用户决策（黄灯面板），确认后才补跑；补跑完自动回到本阶段续跑（届时 `HANDBACK_REQUEST.md` 已被清除）。**不再自动回退** —— 失败/超时一律转黄灯等人。

> 机制事实：驱动对**每一个阶段**都调 `check_handback()`，并为「阶段写了 HANDBACK」专门开了
> 非失败通道 —— 所以交回不等于本阶段失败，不会污染回执。已用上它的 7 个阶段：
> 5coding / 6Robustness / 7Route-diagram / 14Layout-and-format / 9Paper-writing / 11Cross-question-check / 15Verification。
