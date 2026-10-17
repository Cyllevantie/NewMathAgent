# P1：论文角色化（行为不变）实施清单

> 仓库根：`C:/Users/Cyl/Downloads/new math agent/`。下文所有 `path:line` 均相对此根，拼接后即绝对路径。
> 依据：四份只读调研报告（模板侧 / 消费者侧 / 测试侧 / 对抗审查）与 `docs/PAPER_ROLES.md`。
>
> **实施状态（2026-10-17）**：P1 已落地。模板 `roles.json` / `blocks/` / 默认结构、
> `lib/paper_structure`、live `paper/` 迁移、稳定外壳、checker/publication/delivery/server/SKILL/healthcheck
> 均已改；全量回归 **880 tests OK (skipped=3)**；live 的
> `check_skeleton` / `structure check` / `publication` / `delivery` / `writing_check` 全部 PASS。
> 下面保留原始实施清单作为审计记录，`需要拍板` 一节已全部确认。

## 0. 基线与结论

本计划起草时实测（**动手当天必须重测，论文内容若已变化则以新基线为准**）：

- `python lib/web/check_skeleton.py --json` → PASS，`issues=[]`（`lib/web/check_skeleton.py:271-316`）。
- `python -m lib.publication report` → PASS；`total_pages=32`，counts：abstract 1 / body 29 / ai_statement 1 / appendix 1，counted 30/30，摘要 fill 0.9983（1245 个非空白字符），`pdf_sha256=bc9b825b…`（`lib/publication/checks.py:466-583`）。
- `paper/page-map.json:2-29`：abstract 1、body 2–30、ai_statement 31、appendix 32；`paper/formula-review.json:3` 绑定同一 PDF sha；`paper/formula-review.json:10-19` 的源锚是 `paper/sections/5_problem1.tex:96`、page 9。
- 设计稿的四个 P0/P1 阻断点必须先解决：`problem_count` 双口径、`runtime/effective_profile.json` 无生产者、⑨ 无结构完成判据、稳定外壳不能丢 `result-values`/断行设置。

**总原则：双路径。** `paper/structure.json` 不存在 → 完整保留现有 legacy 行为（旧工作区、以及早于 ⑨ 的 ⑦ 仍能跑）；存在但非法 → 响亮失败，绝不回落 legacy。P1 不删 legacy 分支。

---

## 1. 目标与非目标

### 1.1 目标

1. **角色化**：把“论文有哪些节、什么顺序、哪些可关”从 `main.tex` 与检查器里抽到模板 `roles.json` + 生成物 `paper/structure.json`，Python 不再写死章节名。
2. **模板新增**：`templates/zh/cumcm-latex/roles.json`（13 个角色）、`blocks/` 六个内容块、模板默认 `paper-structure.tex`、`structure.default.json`。
3. **`main.tex` 收缩为稳定外壳**：只留 `\documentclass` + `_base` 输入 + 结果登记/断行/孤行/附录 labels 基础设施 + `\input{paper-structure.tex}`；标题、摘要、AI 段、参考文献、末页清单搬进 `paper/blocks/`。
4. **⑨ 步骤 2.5**：复制模板之后、写内容之前，运行 `python -m <paper_structure> assemble` 生成 `paper/paper-structure.tex` 与 `paper/structure.json`。
5. **检查器/发布/交付读同一份结构**：`check_skeleton` 按角色校验（legacy 回退）；`lib.publication` 用 `page_markers`；`lib.delivery` 正文名与必交件按启用角色派生。
6. **指纹语义修正**：`paper/main.tex` 归版式侧；`blocks/`、`paper-structure.tex`、`structure.json` 留在内容侧；`reports/INTAKE.json`、`runtime/effective_profile.json` 进 ⑨ 的 artifacts。
7. **行为不变**：当前论文源级逐字等价、编译后页数/逐页文本/TOC/`main.aux` 等价、`check_skeleton` 与 `publication` 迁移前后均 PASS。
8. **可回滚**：每步有独立验证与文件级回滚，不依赖“整链重跑”。

### 1.2 非目标

1. 不实现 P2 的整链能力：AI 关闭全链、顺序调换全链、`mode=inline/merged/none` 真实写作与检查（P1 只落 schema 与失败规则）。
2. 不删除 legacy 检查路径；不强制旧工作区生成 `roles.json`/`structure.json`。
3. 不改 `lib/result_contract`、`\ResultValue`、`paper/result-values.tex/json`、`_DERIVED_RESULT_FILES`。
4. 不改 `paper_appendix/` 独立工程、⑯ demo 逻辑、`_DEMO_OWNED_PATHS`、`main.pdf` 构建名。
5. 不改 `config/publication.json` 的页数口径与阈值；不把 `kind_start_markers` 在 P1 删掉（仅作为 legacy 回退）。
6. 不改 `check_skeleton` 的内容阈值（假设 3–5 条/120/200 字、分析 1480 字/3/5 行、符号表三列、roadmap 0.85、图题 40 字）。
7. 不改 `lib/delivery` 的 demo 自包含/三维判据、A1 表解析、manifest schema_version 1。
8. 不新增赛题 profile、不新增 MCM/英文 overlay、不新增阶段（步骤 2.5 是 SKILL 步骤，不是 `STAGES` 条目）。
9. 不用 PDF 字节哈希做内容等价判据；不产出 Word/docx。
10. 不重写论文内容；标题/摘要/AI 段/参考文献/末页清单/模型节标题只做**逐字搬家**。

---

## 2. 新文件与 schema

### 2.1 `templates/zh/cumcm-latex/roles.json`（新增；完整路径在 `skills/9Paper-writing/` 下）

`schema_version=1`，`template="zh/cumcm-latex"`，`roles` 为对象（id → 定义）。每个角色统一字段：

`label`、`placement`（`block`/`file`/`external`）、`block`/`wrapper_block`/`file`/`file_pattern`/`project`+`main`+`body`、`required`、`disablable`、`numbering`、`pinned`、`mode`、`host`、`waiver`、`repeat`、`page_kind`、`shares_page_with`、`source_headings`、`emitted_headings`、`deliverables`、`marker`（机器可核的实现标记）。

13 个角色：

| id | 实现 | required | disablable | numbering / page_kind | repeat / 说明 |
|---|---|---|---|---|---|
| `title` | block `blocks/title.tex` | 是 | 否 | unnumbered / null | `pinned=first`，`shares_page_with=abstract`，marker `\papertitle`，是正文 PDF 文件名来源 |
| `abstract` | block `blocks/abstract.tex` | 是 | 否 | unnumbered / `abstract` | `pinned=after:title`，`emitted_headings=["摘要"]`，marker `\abstractcn` |
| `restatement` | file `sections/1_restatement.tex` | 是 | 否 | section / `body` | `source_headings=["问题重述","问题背景","问题提出"]` |
| `analysis` | file `sections/2_analysis.tex` | 是 | 否 | section / `body` | `mode=section`；`source_headings=["问题分析"]`；`repeat={kind:"problem",count_from:"problem_count",heading_pattern:"问题{N}的分析",level:"subsection",after:"问题分析",before:"本文主要创新点",in_same_file:true}`；`source_headings_after=["本文主要创新点"]` |
| `assumptions` | file `sections/3_assumptions.tex` | 是 | 否 | section / `body` | `mode=section` |
| `symbols` | file `sections/4_symbols.tex` | 是 | 否 | section / `body` | `mode=section`；`barrier_before=true`（对应 `main.tex:77` 的 `\FloatBarrier`） |
| `model` | `wrapper_block=blocks/model_section.tex` + `file_pattern=sections/5_problem{N}.tex` | 是 | 否 | section / `body` | `repeat={kind:"problem",count_from:"problem_count",heading_pattern:"问题{N}的模型的建立和求解",level:"subsection",source_subheadings:["具体分析","模型准备","模型建立","模型求解"],optional_subheadings:["结果分析"]}` |
| `check` | file `sections/6_check.tex` | 是 | 否 | section / `body` | `source_headings=["模型检验与分析","误差分析","灵敏度分析"]` |
| `evaluation` | file `sections/7_evaluation.tex` | 是 | 否 | section / `body` | `source_headings=["模型的评价与推广","模型的优点","模型的缺点","模型的改进与推广"]` |
| `ai_statement` | block `blocks/ai_statement.tex` | 是 | **是** | section / `ai_statement` | `emitted_headings=["AI 工具使用说明"]`；`deliverables=["AI工具使用详情.pdf"]`；marker `\section{AI 工具使用说明}` |
| `references` | block `blocks/references.tex` + 辅助 `file=references.tex` | 是 | 否 | section / `references` | `emitted_headings=["参考文献"]`；`shares_page_with=ai_statement`；marker `\referencescn`；底层 `references.tex` 由宏自己 `\input` |
| `materials_list` | block `blocks/materials_list.tex` + 辅助 `file=sections/A1_materials.tex` | 是 | **是** | unnumbered-appendix / `appendix` | `pinned=last`；`emitted_headings=["附录"]`；marker `\appendixAcn[支撑材料清单]{A1_materials}` |
| `appendix_pdf` | external `paper_appendix/`（`main.tex` + `sections/A_appendix.tex`） | 是 | **是** | appendix-A / null | `deliverables=["附录A.pdf"]`；不在正文 page-map |

**必须写清的三条实现口径：**

1. `materials_list.disablable=true`，按 `docs/PAPER_ROLES.md:561-565` 的决定 2；设计稿 §3 样例已同步为 `true`。核心角色 `analysis`/`assumptions`/`symbols` 必须 `disablable=false`（`docs/PAPER_ROLES.md:571-575`）。
2. **`source_headings` 与 `emitted_headings` 必须分开**：`title`/`abstract`/`references`/`materials_list` 的标题由 `\papertitle`/`\abstractcn`/`\referencescn`/`\appendixAcn` 宏发出，源码里没有 `\section`；若把 `"摘要"`/`"参考文献"`/`"附录"` 当 `source_headings` 扫源码，`check_skeleton` 会误报缺标题（`lib/web/check_skeleton.py:57-58` 只认 section/subsection/subsubsection）。
3. `references`/`materials_list` 的 `block` 是**包装块**（块内调用宏），生成器只发 `\input{blocks/references}` / `\input{blocks/materials_list}`，不再直接 `\input{references}` 或 `\input{sections/A1_materials}`；`file` 字段只给孤儿检查与 A1 对账用。对应宏的硬编码路径见 `skills/9Paper-writing/templates/_base/macros.tex:42-46` 与 `:64-72`。

### 2.2 `templates/zh/cumcm-latex/structure.default.json`（新增，P1 兼容层；完整路径在 `skills/9Paper-writing/` 下）

`runtime/effective_profile.json` 全仓不存在（grep 只命中 `docs/PAPER_ROLES.md`），P1 必须给 assembler 一个模板默认 profile：

- `schema_version=1`、`profile="template_default_cumcm"`、`template="zh/cumcm-latex"`；
- `structure.order` 按现状：`title, abstract, restatement, analysis, assumptions, symbols, model, check, evaluation, ai_statement, references, materials_list`；
- `structure.disabled=[]`、`structure.supplement=["appendix_pdf"]`；
- `structure.problem_count_source="auto"`（优先级：effective_profile → `reports/INTAKE.json#problem.subquestions`（certain）→ `reports/ANALYSIS_MODELING_REPORT.md §1.2`；当前工作区因 INTAKE uncertain 解析为 `analysis_report:1.2`，见 §4）。

assembler 在 `runtime/effective_profile.json` 缺失时读它，并在 `structure.json` 记 `profile_source="template-default"`；P3 驱动真正产出 profile 后删除该回退。生成器读 `templates/.../structure.default.json` 源文件（完整路径在 `skills/9Paper-writing/` 下），不读 `paper/` 下的副本，避免副本被改后结果漂移。

### 2.3 `paper/paper-structure.tex`（模板默认 + 生成物）

固定格式（无时间戳、无随机键序、POSIX 相对 `paper/` 路径、`\input` 不带 `.tex`）：

```latex
% generated by lib.paper_structure from <profile>; don't hand-edit
% template=zh/cumcm-latex profile=<profile> problem_count=<N>
\input{blocks/title}
\input{blocks/abstract}
\input{sections/1_restatement}
\input{sections/2_analysis}
\input{sections/3_assumptions}
\FloatBarrier
\input{sections/4_symbols}
\input{blocks/model_section}
\input{sections/5_problem1}
...
\input{sections/5_problemN}
\input{sections/6_check}
\input{sections/7_evaluation}
\input{blocks/ai_statement}
\input{blocks/references}
\input{blocks/materials_list}
```

规则：

- `title` 必须是 `\begin{document}` 后第一个被 `\input` 的块（`\papertitle` 设置 parskip/lineskip/abovedisplayskip）。
- `symbols` 前按 `barrier_before` 发 `\FloatBarrier`（保住 `main.tex:77` 的版面）。
- `model` 先发一次 `blocks/model_section`，再按 `1..N` 发 `sections/5_problem{i}`。
- AI 关闭时整行不写；`references`/`materials_list` 只发包装块。
- 模板自带一份默认文件，供 ⑨ 步骤 2 的空跑编译；步骤 2.5 幂等覆盖它。

### 2.4 `paper/structure.json`（生成物）

必备字段：

| 字段 | 类型 | 来源/算法 | 消费者 |
|---|---|---|---|
| `schema_version` | int | 1 | 全体 |
| `profile` | str | profile 文件名/ID | 审计 |
| `profile_source` | str | `effective_profile` 或 `template-default` | 审计 |
| `template` | str | `zh/cumcm-latex` | 检查器选 roles.json |
| `template_roles_sha256` | 64 hex | 模板源 `templates/zh/cumcm-latex/roles.json` 字节（完整路径在 `skills/9Paper-writing/` 下） | 漂移检测 |
| `title` | str/null | 步骤 2.5 置 `null`；步骤 7 `sync-title` 回填 | delivery |
| `title_source` | str | `unset`/`blocks/title.tex` | 审计 |
| `keywords` | list/null | 从 `blocks/abstract.tex` 可选解析 | 审计 |
| `problem_count` | int | 论文模型分节数 N（见 §4） | 生成器/检查器/delivery |
| `problem_count_source` | str | `effective_profile` / `intake:problem.subquestions` / `analysis_report:1.2` | 审计 |
| `intake_subquestion_count` | int/null | 题面官方读数（审计，不驱动 N） | 审计 |
| `enabled` | list[str] | `order` 减 `disabled`，保序 | 检查器 |
| `disabled` | list[str] | profile | 检查器/delivery |
| `supplement` | list[str] | profile（默认 `appendix_pdf`） | delivery |
| `order` | list[str] | profile 顺序 | 检查器 |
| `modes` | map | role → `section/inline/merged/none` | 检查器 |
| `page_kinds` | map | 物理页组 → 角色列表（`abstract=[title,abstract]`、`body=[...]`、`ai_statement=[ai_statement,references]`、`appendix=[materials_list]`） | publication/page-map |
| `page_kind_aliases` | map | `{"references":"ai_statement"}`（共页时） | publication |
| `section_numbers` | map | 启用的一级角色 → 中文数字（restatement 一 … model 五 … references 九） | publication/prompt |
| `page_markers` | map | kind → 起始标记，当前必须逐字等于 `config/publication.json:45-50` | publication/page-map |
| `paper_structure_sha256` | 64 hex | `paper/paper-structure.tex` 字节 | 检查器 |
| `files` | list[str] | 展开后的实际文件（含 repeat） | 检查器 |
| `roles` | map | 生效角色快照（含 source/emitted headings、repeat、deliverables） | 检查器 |
| `deliverables` | list[str] | 启用角色 deliverables 的并集（不含正文；正文名由 title 派生） | delivery |
| `warnings` | list[str] | 计数不一致、孤儿文件等 | 审计 |

JSON 序列化固定 `ensure_ascii=False, indent=2, sort_keys=True`，结尾换行；重跑必须字节一致。**语义摘要** `structure_sha256`（写进 `paper/page-map.json`）只对 `schema_version/template/problem_count/enabled/disabled/supplement/page_kinds/page_kind_aliases/section_numbers/page_markers/title` 做 `sort_keys` 哈希，不用文件字节，避免格式化差异造成假失效。

### 2.5 `lib/paper_structure/`（新包）

> 模块名定为 `lib/paper_structure`；下面命令里的 `<paper_structure>` 是实现后的占位符，
> 落地时替换为 `lib.paper_structure`。设计稿先不创建该包，避免文档哨兵把“计划中的模块”当成缺失。

- `__init__.py`：导出 `assemble/check/sync_title/resolve_problem_count`。
- `__main__.py`：argparse 子命令 `assemble | check | sync-title`；`--root`（默认 cwd）、`--profile`、`--template`、`--out`；`sys.stdout.reconfigure(encoding="utf-8", errors="replace")`（与 `lib/publication/__main__.py:12-16` 同款）；必须有 `__main__.py`，否则 `regression/test_lib_layout.py:60-70` 的 `MODULE_RX` 会红。
- `core.py`：`load_roles/load_profile/resolve_problem_count/build_plan/render_tex/build_structure/canonical_json/sha/sync_title/check`；`_cn_num` 在 1..99 正确转换（现有 `lib/web/check_skeleton.py:183-188` 对 20+ 会输出“二零”，当前只有 9 个编号节不受影响；若共享必须先修）。
- 不 import `lib.web.check_skeleton`（该脚本把 `lib/web` 而非仓库根放进 `sys.path`，见 `lib/web/check_skeleton.py:49`）；`check_skeleton` 也不 import 本包，直接 `json.load`。

---

## 3. 按文件的精确改动清单

### 3.1 模板侧

| 文件:行 | 现状 | 改动 |
|---|---|---|
| `skills/9Paper-writing/templates/zh/cumcm-latex/main.tex:1-50` | preamble、`_base` 输入、`result-values.tex` 的 `IfFileExists`（:29）、`\providecommand{\ResultValue}`（:35）、`clubpenalty/widowpenalty/pretocmd`（:38-40）、`labels_appendix`（:46-47）、`\begin{document}`/`\hypersetup`（:49-50） | **全部保留**。这是编译与版面必需项，不能随“只留 documentclass + _base + paper-structure”一句删掉 |
| `.../main.tex:52-113` | `\papertitle`（:55）、`\abstractcn`（:57-69）、10 个 `\input`（:74-87）、`\section{模型的建立与求解}`（:80）、AI 段（:93-95）、`\referencescn`（:97）、`\appendixAcn`（:113） | 整段替换为唯一一行 `\input{paper-structure.tex}`；`\end{document}`（:115）保留 |
| `.../main.tex:17` | 注释说“format 独占 _base 与导言区；write 只写 sections/ 和摘要” | 改为“format 独占 `_base/` 与 `main.tex` 外壳；write 写 `sections/`、`blocks/` 与生成结构” |
| `.../blocks/title.tex`（新增） | — | 逐字接收模板 `main.tex:55` 的 `\papertitle{<论文标题>}` 与 :52-54 注释 |
| `.../blocks/abstract.tex`（新增） | — | 逐字接收 `main.tex:57-69` 的完整 `\abstractcn{...}{...}` 与 :56/:58-60 注释 |
| `.../blocks/model_section.tex`（新增） | — | 逐字接收 `main.tex:80` 的 `\section{模型的建立与求解}` |
| `.../blocks/ai_statement.tex`（新增） | — | 逐字接收 `main.tex:93-95` 的 `\section{AI 工具使用说明}` + 声明段 |
| `.../blocks/references.tex`（新增） | — | 接收 `main.tex:97` 的 `\referencescn`（宏自己发 `\section{参考文献}` 并 `\input{references}`） |
| `.../blocks/materials_list.tex`（新增） | — | 接收 `main.tex:113` 的 `\appendixAcn[支撑材料清单]{A1_materials}` |
| `.../paper-structure.tex`（新增默认） | — | 按 §2.3 的现顺序清单，供步骤 2 空跑编译 |
| `.../roles.json`（新增） | — | 按 §2.1 |
| `.../structure.default.json`（新增） | — | 按 §2.2 |
| `templates/_base/macros.tex:42-46,64-72` | `\referencescn` 硬编码 `\input{references}`；`\appendixAcn` 硬编码 `\input{sections/#2}` | **不改宏**。P1 用包装块适配现状；若以后要参数化，另开改动并加双工程编译测试 |

### 3.2 当前工作区 `paper/` 一次性迁移

| 文件:行 | 改动 |
|---|---|
| `paper/main.tex:1-50` | 保留（与模板外壳同构） |
| `paper/main.tex:55` | 逐字搬入 `paper/blocks/title.tex` |
| `paper/main.tex:57-93` | 逐字搬入 `paper/blocks/abstract.tex` |
| `paper/main.tex:98-111` | 删除，改由 `paper/paper-structure.tex` 发出；`paper/main.tex:144-145` `\end{document}` 保留 |
| `paper/main.tex:104` | `\section{模型的建立与求解}` 逐字搬入 `paper/blocks/model_section.tex` |
| `paper/main.tex:117-124` | 逐字搬入 `paper/blocks/ai_statement.tex` |
| `paper/main.tex:126` | `\referencescn` 逐字搬入 `paper/blocks/references.tex` |
| `paper/main.tex:142` | `\appendixAcn[支撑材料清单]{A1_materials}` 逐字搬入 `paper/blocks/materials_list.tex` |
| `paper/blocks/*`（新增） | 上述六个块；`paper/blocks` 当前不存在 |
| `paper/paper-structure.tex`（新增） | 按 §2.3 生成；首发可由 assembler 生成，不等同手写 |
| `paper/structure.json`（新增） | assembler 生成；`roles` 快照是检查器的权威；`title=null`，步骤 7 回填 |

注意：`\abstractcn` 末尾自带 `\newpage`（`macros.tex:25-40` 区域），拆文件后 block 之间不要手工加 `\par`/`\vspace`；vertical mode 的空格 token 会被忽略，不会多出空行。

### 3.3 ⑨ SKILL 与 prompt

| 文件:行 | 改动 |
|---|---|
| `skills/9Paper-writing/SKILL.md:253-254` | “本阶段只写 `sections/` 与摘要，不碰 `paper/_base/` 与 `main.tex` 导言区” → “本阶段写 `sections/`、`blocks/`（内容）与 `paper-structure.tex`（生成物），不碰 `paper/_base/` 与 `main.tex` 外壳” |
| `skills/9Paper-writing/SKILL.md:395-427` | 步骤 2 复制模板：增加复制后自检（`paper/blocks/`、`paper/paper-structure.tex` 必须存在；缺一即复制不完整）；把整目录覆盖改为“缺失才复制/先归档”（见 §9 D5） |
| `skills/9Paper-writing/SKILL.md:427-430` 之间 | 插入“步骤 2.5：生成论文结构（角色化）”，内容按 §4 |
| `skills/9Paper-writing/SKILL.md:540-543` | “章节文件名以 main.tex 的 `\input` 为准” → “以 `roles.json` + `paper/paper-structure.tex` 为准，不再从 main.tex 反推” |
| `skills/9Paper-writing/SKILL.md:662` | 保留 `paper/references.tex`，补“正文由 `blocks/references.tex` 的 `\referencescn` 引入” |
| `skills/9Paper-writing/SKILL.md:686` | 摘要位置改为 `paper/blocks/abstract.tex`（保留“返修轮次最容易漏摘要”的警告，提醒同时扫 `blocks/`） |
| `skills/9Paper-writing/SKILL.md:698-709` | 步骤 7 在重编译前插入 `python -m <paper_structure> sync-title --root .`；顺序：写 title → sync-title → 重编译两遍 → `publication map` → `report` |
| `lib/web/server.py:640-739` `prompt_for` | 在 write 分支注入：步骤 2.5 命令、`paper-structure.tex`/`structure.json` 是生成物不许手改、`main.tex` 是 ⑭ 的稳定外壳、启用角色顺序与 `section_numbers`、disabled 角色不写。无 profile 时用模板默认也注入 |

### 3.4 `lib/paper_structure/`

按 §2.5。额外规则：

- `assemble` 只写 `paper/paper-structure.tex` 与 `paper/structure.json`；先写临时文件再原子替换，失败时不留半成品。
- `check` 只读：核对 `paper-structure.tex` 的 `\input` 序列与 `structure.json.files` 完全一致、`problem_count` 与 5_problemN 输入数一致、`template_roles_sha256` 与模板源 `roles.json` 一致、`paper_structure_sha256` 与文件字节一致。
- `sync-title` 只从 `paper/blocks/title.tex` 的 `\papertitle` 回填 `title`/`title_source`，其余字段逐字节不动；`structure.json` 不存在时失败，不新建；`\papertitle` 仍是 `<论文标题>` 占位符时拒绝回填并记 warning。

### 3.5 `lib/web/check_skeleton.py`

| 行 | 改动 |
|---|---|
| `:49` | 保持只把 `lib/web` 放进 `sys.path`；**不** import `lib.paper_structure` |
| `:55-58` | 增加 `BLOCKS_REL="paper/blocks"`；`HEADING_RE` 不变 |
| `:161-173` `_skeletons` | 原样保留（legacy 发现模板族） |
| `:271-316` `skeleton_issues` | 开头增加：若 `paper/structure.json` 存在 → 走 `_role_issues(root)`；否则原样 legacy。config/结构非法返回 2，内容不符返回 1 |
| 新增 `_load_structure/_role_issues` | ① required && !disabled 恰好出现一次；② disabled 不得出现在 `paper-structure.tex` 的 `\input` 序列；③ 顺序等于 `structure.order`，title first、materials_list last；④ enabled 角色的 file/block 存在（model 按 1..N 展开）；⑤ `source_headings` 按文件比对（只比标题文本、不比层级，保持现口径）；`emitted_headings` 只记录；⑥ 孤儿：`paper/sections/*.tex` 与 `paper/blocks/*.tex` 未被任何角色（含 disabled 的 `file`/`file_pattern`）引用即报错；⑦ mode 规则（section 有独立标题；inline/merged 有 host + anchor；none 有非空 waiver）；⑧ `problem_count` 用 `structure.problem_count`，不再用 5_problemN 最大编号；⑨ `main.tex` 不得出现 `\papertitle`/`\abstractcn`/`\section`/`\input{sections|blocks}`；⑩ `paper_structure_sha256` 对账 |
| `:665-705` `_wording_problems` | 扫描列表从 `paper/sections/*.tex + paper/main.tex` 改为 `paper/sections/*.tex + paper/blocks/*.tex + paper/main.tex`（legacy） |
| `:708-735` `_question_count_problems` | structure 存在时用 `structure.problem_count` 核 analysis 的“问题N的分析”条数；legacy 保留 max 文件号逻辑 |
| `:948-985` `_caption_problems` | 同 `_wording_problems`，增加 `paper/blocks/*.tex` |
| `:1061` `_assumption_problems`、`:412` `_symbols_problems`、`:849-850` `ROADMAP_HOME` | structure 存在时按角色解析实际文件；常量只作 legacy 默认 |
| `:319` `SYMBOLS_FILE_RE` | legacy 保留；角色模式先查 `symbols.file` |

### 3.6 `lib/publication/checks.py` 与 `config/publication.json`

- `:11` `KINDS` 不变。
- 新增 `effective_policy(root, policy)`：structure 缺失 → 原样返回 policy（legacy）；存在 → 用 `structure.page_markers` 覆盖 `kind_start_markers`；把 `max_group_pages` 按 `page_kind_aliases` 归一化（references 共页归并到 ai_statement；AI 关闭时整组丢弃）；`max_kind_pages/min_kind_fill/min_kind_chars` 只保留 `page_kinds` 里存在的 kind；`require_appendix = "appendix" in page_kinds`。
- `:14-83` `classify` 增加可选 structure 参数（保持三参调用兼容）；page-map 的每个 span.kind 必须属于 structure.page_kinds。
- `:86-142` `boundary_page_issues` 的 `kind_start_markers` 改从 effective policy 取；保留“找不到标记不报”的现状（`:124-125`），但用 structure_sha256 兜底。
- `:466-583` `inspect`：加载 structure；用 effective policy 调 classify/boundary/kind_fills；校验 `mapping.structure_sha256` 与语义摘要一致，不匹配报“页面映射未绑定当前结构”；新增 `result["structure_issues"]` 供 `_mechanical_floor` 路由。
- `:597-612` `bind_map`：用同一 effective policy 校验，写入 `pdf_sha256` 与 `structure_sha256`；拒绝 kind 不在 structure.page_kinds 的映射。
- `:289-300` `style_hints`：摘要来源改为 `paper/blocks/abstract.tex` 优先、`paper/main.tex` 回落；hint 的 `file` 写实际路径。
- `config/publication.json:45-50` 的 `kind_start_markers` **P1 不删**，作 legacy 回退；P2 稳定后再删。
- 可选新增 `python -m lib.publication markers` 只读打印 page_markers，供 ⑭ 对边界。

### 3.7 `lib/delivery/core.py` 与 `lib/delivery/checks.py`

- `core.py:57-76` `body_pdf_name` 四级回落：① `paper/structure.json` 的 `title`（非空、非 `<...>` 占位符）→ ② `paper/blocks/title.tex` 的 `\papertitle`（同占位符守卫）→ ③ `paper/main.tex` 的 `\papertitle`（legacy）→ ④ `BODY_PDF`。保留 `_ILLEGAL` 清洗与空白归一。
- 新增 `load_structure(root)`：文件不存在返回 `None`（legacy）；存在但 schema/字段非法抛 `StructureError`，不静默回落。
- `checks.py:350-379` `required_items_issues`：`need = {MANUAL} ∪ structure.deliverables`（structure 为 None 时用现有三件套）；body 恒必交；`body_ok` 增加“清单任一项 `source == paper/main.pdf`”即算有正文；structure.deliverables 出现被禁用角色的交付物 → 报错。
- `core.py:354-413` `provisional_items`：正文 + MANUAL 恒收；AI/附录按 structure.deliverables 收；demo 仍按盘上是否存在收；structure 为 None 时保持现有全收逻辑。
- `checks.py:382-413` `checklist_consistency_issues`：`expect = declared - 所有 source 解析为 paper/main.pdf 的项`，不再只减当前 `body_pdf_name`/`BODY_PDF`（否则旧标题 manifest 会把正文误算成“表里少了”）。
- `FIXED_SOURCES`（`core.py:81-84`）不动；新角色交付物若不在表里，必须在 manifest 写 `source`。

### 3.8 `lib/web/server.py` 指纹、产物、门控

| 行 | 改动 |
|---|---|
| `:939-949` `_LAYOUT_OWNED_PATHS` | **在 title/abstract 真正搬进 blocks 的同一步**加入 `"paper/main.tex"`；**不要**加入 `paper/paper-structure.tex`、`paper/blocks`、`paper/structure.json` |
| `:1272-1273` 注释 | 改为“main.tex 是版式侧稳定外壳（导言区）；内容侧是 sections/、blocks/、paper-structure.tex、references.tex、structure.json” |
| `:1106-1112` `_EXTRA_INPUT_PATHS` | 为 `write` 增加 `["reports/INTAKE.json", "runtime/effective_profile.json"]` |
| `:1176-1213` `_input_paths` | write 动态解析 profile 的 template 并追加 `templates/<template>/roles.json` 与 `structure.default.json`（完整路径在 `skills/9Paper-writing/` 下；缺失记 None，fingerprint 既有语义） |
| `:640-739` `prompt_for` | 见 §3.3 |
| `:743-750` `_artifact_ok` | write 在角色化模板（模板源 `roles.json` 存在）时额外要求 `paper/structure.json` 与 `paper/paper-structure.tex`，并校验 structure.json 可解析、`problem_count>=1`、`enabled` 非空；否则返回 False |
| `:4046-4153` `_mechanical_floor` | publication 报告新增 `structure_issues`：结构类问题 `target="write"`（⑨ 拥有结构），page-map 绑定类问题仍 `target="format"`；delivery precheck 前先跑结构文件存在/合法检查，结构类问题 `target="write"` |
| `:1002-1020` `_LIB_INSTRUCTION_USERS` | 新增 `"lib/paper_structure": {"write","format","verify"}`；`"lib/web/check_skeleton.py"` 保持 `{"write","format","drawio"}`（若 ⑮ 也直接跑它，再加 `verify` 并同步 `test_doc_drift.py:202` 的期望集合） |
| `:1260-1262` | `index>=i_write` 的 ins 列表加 `"lib/paper_structure"` |
| `:5776-5819` `ARTIFACTS` | **不改**：`write` 已含整个 `paper`，新文件自动进产物指纹；`_output_digest`（`:1430-1448`）会自动管住它们 |
| `:870-876` `_prompt_fingerprint` | 不改；prompt_for 一改会让全阶段一次性 stale-instr（只标记不重跑，预期成本） |

### 3.9 `lib/web/workflow_quality.py`

- `_is_paper_build_output`（`:25-55`）**不要**排除 `paper/structure.json`：它必须进 write/format/verify 的指纹；`page-map.json`/`formula-review.json` 的排除（`:47-48`）保持不动。
- 不加 `paper/blocks` 或 `paper-structure.tex` 到任何构建产物豁免。

### 3.10 tests / docs / scripts

见 §8 与 §3.11。

### 3.11 文档与机器脚本

| 文件:行 | 改动 |
|---|---|
| `docs/PAPER_ROLES.md:200-210` | `materials_list.disablable` 已统一为 `true`；实现时加测试锁住 |
| `docs/PAPER_ROLES.md:388-417` | `structure.json` 样例补 `title/title_source/keywords/order/page_markers/paper_structure_sha256/roles/warnings`；`:416` 的 `deliverables` 不再写死“正文.pdf”，正文名由 title 派生 |
| `docs/PAPER_ROLES.md:108-119` | `analysis` 的扁平 `headings` 改为 `source_headings + repeat` 结构 |
| `docs/PAPER_ROLES.md:96,198,209` | `abstract/references/materials_list` 的标题改记 `emitted_headings`，`source_headings=[]` |
| `docs/PAPER_ROLES.md:244-247` | 给 `inline/merged` 补机器锚点（`anchor` 注释标记或固定子标题），P2 前先写进 schema |
| `docs/PAPER_ROLES.md:460,566-570` | 统一 `uncertain` 语义：P1 用 `confidence in {low,uncertain}` 或计数相关 `uncertain` 项；P2 增加机读 `count_status` |
| `docs/PAPER_ROLES.md:530-538` | P1 清单补 `effective_profile` 的生产者/回退（P1 用 `structure.default.json`，P3 驱动） |
| `docs/PUBLICATION.md` | 说明 `page_markers` 由 structure 派生、page-map 绑定 `structure_sha256`、摘要位置在 `blocks/abstract.tex` |
| `skills/14Layout-and-format/SKILL.md:42,68,345` | `:42` “独占 `paper/_base/` 与 `main.tex` 稳定外壳（导言区）”；`:68` “main.tex 只留 documentclass + _base + result-values/断行 + `\input{paper-structure.tex}`；赛事差异在 roles.json/blocks/paper-structure.tex，归 ⑨”；`:345` 结构文件不许 ⑭ 改，结构问题写 `HANDBACK_REQUEST.md` 回 ⑨ |
| `skills/15Verification/SKILL.md:61,108,174,294` | 读 `structure.json` 核对结构；说明 main.tex 是入口但正文由 paper-structure 组合；`writing_check.sh` 递归解析 |
| `skills/15Verification/scripts/writing_check.sh:117-149,281-333,408,480` | `\input` 解析改为递归（main.tex → paper-structure.tex → blocks/sections），或直接以 `structure.json.enabled/files` 作为包含顺序权威；扫描集合加入 `paper/blocks/*.tex`；`--references` 默认仍 `paper/references.tex` |
| `lib/web/healthcheck.py:45-53,71-81` | 每个模板族必须有 `roles.json`、`blocks/`、默认 `paper-structure.tex`；roles.json 可解析且角色实现文件存在；main.tex 含 `\input{paper-structure.tex}` 且不含 `\papertitle/\abstractcn`；py_compile 清单加入 `lib/paper_structure` 包内的 `.py` 文件 |
| `docs/ENVIRONMENT.md:44` | “96 项结构检查”按实际数量更新（若 healthcheck 检查项变化） |

---

## 4. ⑨ 步骤 2.5：生成流程与失败/幂等规则

### 4.1 位置与命令

- 位置：`skills/9Paper-writing/SKILL.md:427`（步骤 2 复制模板与空跑编译）之后、`:430`（步骤 3 图表规划）之前。
- 命令：

```bash
python -m <paper_structure> assemble --root . \
  --profile runtime/effective_profile.json \
  --template zh/cumcm-latex --out paper/
```

- 输入：`runtime/effective_profile.json`（缺失时回退 `templates/zh/cumcm-latex/structure.default.json`，完整路径在 `skills/9Paper-writing/` 下；记 `profile_source=template-default`）、模板 `roles.json`、`reports/INTAKE.json#problem.subquestions`、`reports/ANALYSIS_MODELING_REPORT.md §1.2`。
- 输出：`paper/paper-structure.tex`、`paper/structure.json`。

### 4.2 `problem_count` 解析（P1 第一风险）

**先定义两个数：**

- `intake_subquestion_count`：题面官方读数，只做审计；
- `problem_count`：**论文内部模型分节数 N**，驱动 `5_problemN` 与 analysis 的“问题N的分析”。

**确定性优先级：**

1. `effective_profile.structure.problem_count` 是显式正整数 → 直接用，`source=effective_profile`。
2. `reports/INTAKE.json#problem.subquestions` 是 **list**、非空，且没有“计数相关 uncertain”（`confidence in {"low","uncertain"}` 或 `uncertain` 任一项匹配 `小问|子问题|分几问|拆成|分问|几问`）→ `N=len(list)`，`source=intake:problem.subquestions`。**绝不是对字符串取 len**；非 list 视为缺失。
3. 读 `reports/ANALYSIS_MODELING_REPORT.md` 中标题匹配“子问题”的 `###` 小节（当前为 `### 1.2 三个子问题`，`reports/ANALYSIS_MODELING_REPORT.md:65-73`），数表格数据行（跳过表头与 `|---|` 分隔行）→ `N=行数`，`source=analysis_report:1.2`。
4. 仍无法确定（文件缺失/表不存在/行数<1）→ **退出码 5，不写任何输出**；错误信息同时点名 `reports/INTAKE.json#problem.subquestions` 与 `reports/ANALYSIS_MODELING_REPORT.md §1.2`。

**当前工作区判定：** INTAKE 的 `subquestions` 长度 1（`reports/INTAKE.json:8-10`），`confidence=medium`，`uncertain` 第 2 条明确写“题面没有分问……是否拆成多问需人拍板”（`reports/INTAKE.json:14`）→ 命中计数相关 uncertain → 走第 3 步；`ANALYSIS_MODELING_REPORT.md:65-73` 的 §1.2 表有 3 行（P1/P2/P3）→ **N=3**，`source=analysis_report:1.2`，`intake_subquestion_count=1`。这与现有 `paper/sections/5_problem1..3.tex` 三问一致。

**用户确认（2026-10-17）：** 题面没有分问时，**由建模设计自行决定拆成几问（可以自命题）**；`ANALYSIS_MODELING_REPORT.md §1.2` 是这项建模决策的记录，`INTAKE.json` 的读数只做审计，不强行决定论文问数。

**健全性检查：** `5_problem*.tex` 文件数只做“至少一个、编号连续、最大编号与 N 比较”，不一致写 `structure.json.warnings`，**绝不作为 N 的来源**。若 `intake_subquestion_count` 与 N 不一致，也写 warning（防止“题面 1 问、论文 3 问”静默放过）。

### 4.3 生成算法

1. 读 profile（或默认）与 roles.json；校验 `template` 字段一致。
2. 校验 `order` 里的角色都存在；`disabled` 只含 `disablable=true` 的角色；核心角色不得 disabled。
3. 按 `order` 遍历：disabled 跳过；`mode=inline/merged` 不单独发 `\input`（由 host 承载）；`mode=none` 只记 waiver；`placement=external` 只进 `supplement`；`placement=block` 发 `\input{<block 去 .tex>}`；`model` 先发 wrapper 再按 1..N 发 file_pattern；`symbols` 前按 `barrier_before` 发 `\FloatBarrier`；`references`/`materials_list` 只发包装 block。
4. 计算 `section_numbers`（只给一级角色；model wrapper 占一号；重复的 5_problemN 不占号）。
5. 计算 `page_kinds`、`page_kind_aliases`、`page_markers`（默认必须逐字等于 `config/publication.json:45-50`）。
6. 展开 `files`（含 repeat），写 `roles` 快照、`deliverables`、`warnings`。
7. 写 `paper-structure.tex`（头两行固定，第二行记录 template/profile/problem_count），计算 `paper_structure_sha256`，写 `structure.json`。
8. 原子替换两个输出；失败时不留半成品。

### 4.4 失败规则（退出码）

| 退出码 | 条件 |
|---|---|
| 0 | 成功 |
| 2 | `roles.json` 缺失/非法、template 不一致、profile JSON 非法、`paper/` 或 `paper/sections/` 不存在 |
| 3 | profile 引用未知角色、核心角色被 disabled、`mode=inline/merged` 缺 host、`mode=none` 缺非空 waiver、enabled 角色的 block/file 缺失、pinned 被挪动 |
| 4 | 生成文件写入失败/目录不可写 |
| 5 | `problem_count` 无法确定 |
| 6 | `sync-title` 时 `structure.json` 不存在，或 `\papertitle` 仍是占位符（后者记 warning 不写 title） |

### 4.5 幂等规则

- 重跑覆盖，不写时间戳；JSON `sort_keys`、固定缩进、结尾换行；`paper-structure.tex` 头固定、无随机顺序。
- 连跑两遍，两个输出文件的 sha256 必须相同。
- 生成物不许手改；`fix`/`format` 不运行生成器、不改这两个文件；结构问题写 `HANDBACK_REQUEST.md` 回 ⑨。
- 步骤 2 末尾自检：`paper/blocks/`、`paper/paper-structure.tex` 必须存在；缺任何一个都是复制不完整，先修模板再编译。
- 步骤 2 的空跑编译使用模板默认 `paper-structure.tex`，步骤 2.5 覆盖它；顺序不能颠倒。

---

## 5. 指纹与回执语义

### 5.1 文件归属

| 路径 | 归属 | 进 artifacts | 进 instructions | 说明 |
|---|---|---|---|---|
| `skills/9Paper-writing/SKILL.md` | 做法要求 | 否 | write | 现有 `_input_split` 已收 `skills/<skill>` |
| `templates/zh/cumcm-latex/roles.json`（完整路径在 `skills/9Paper-writing/` 下） | 模板源 | 否 | write（随 skill 目录）、format/verify（显式） | 不放进 `paper/` 的副本 |
| `.../structure.default.json` | 模板源 | 否 | write/format/verify | 同上 |
| `runtime/effective_profile.json` | 赛题事实 | **write** | 否 | `_EXTRA_INPUT_PATHS`；缺失按 None，稳定 |
| `reports/INTAKE.json` | 题面事实 | **write** | 否 | 现在只是 `INTAKE_REPORT.md` 进指纹，JSON 没进 |
| `paper/main.tex` | **版式侧**（迁移后） | 是（paper 目录） | 否 | `_LAYOUT_OWNED_PATHS`；内容判官排除，verify 仍看 |
| `paper/blocks/*` | **内容侧** | 是 | 否 | 不进 `_LAYOUT_OWNED_PATHS` |
| `paper/paper-structure.tex` | **内容侧**（生成物） | 是 | 否 | ⑭ 只读，改它内容判官失效 |
| `paper/structure.json` | **内容侧**（生成物） | 是 | 否 | `_is_paper_build_output` 不得排除 |
| `paper/sections/*` | 内容侧 | 是 | 否 | 现状 |
| `paper/references.tex` | 内容侧 | 是 | 否 | 现状 |
| `paper/_base/*`、`paper/main.pdf`、`paper/main.aux/log/out` | 版式侧 | 是 | 否 | 现状 |
| `paper/page-map.json`、`paper/formula-review.json` | 版式侧/构建派生 | 是，但 `_is_paper_build_output` 排除 | 否 | 现状不变 |
| `reports/SUBMISSION_MANIFEST.json`、`运行说明.md` | 版式侧 | 是 | 否 | 现状 |
| `lib/paper_structure` | 做法要求 | 否 | write/format/verify | 新增 `_LIB_INSTRUCTION_USERS` |
| `lib/web/check_skeleton.py` | 做法要求 | 否 | write/format/drawio | 现状 |

### 5.2 回执语义

- **artifacts 变** → 自动重做（真过期）；**instructions 变** → 只标 `done(stale-instr)`，不重跑（`lib/web/server.py:1216-1287`）。
- `prompt_for` 一改，`_prompt_fingerprint`（`:870-876`）变化，全阶段一次性 stale-instr；这是预期成本，不是零成本。
- `structure.json` 变化 → 内容判官（mathproof/cross/rubric/fix）与 verify 都失效；`paper/main.tex` 变化 → 内容判官**不**失效，verify 失效。
- `page-map.json` 的 `structure_sha256` 是 publication 自己的语义绑定，不依赖文件指纹；`paper/page-map.json` 与 `formula-review.json` 仍按 `_is_paper_build_output` 豁免构建字节。
- `ARTIFACTS["write"]` 已含 `paper`（`lib/web/server.py:5803`），两个新文件自动进 `_output_digest`；不要重复声明。回退暂存也会连它们一起进 cache。

---

## 6. 内容等价的验收方案

### 6.1 基线冻结（动手前）

1. 把 `paper/` 复制到 `_tmp/equiv/before/paper/`（含 `main.tex`、`main.pdf`、`main.aux`、`page-map.json`、`formula-review.json`）。
2. 记录：`check_skeleton` JSON、`publication report` JSON、PDF 页数、逐页 `page.get_text()`、`doc.get_toc()`、`main.aux` 的 `\newlabel`/`\contentsline`。
3. 当前基线：32 页、39 条 TOC、29,233 个非空白字符、20 条 `\newlabel`、摘要 fill 0.9983、counted 30/30。**动手当天重测，若论文已变化则更新基线。**

### 6.2 四级 oracle（按优先级）

1. **源级重建对照（最强、最便宜）**：把 `before/main.tex` 的 `\begin{document}...\end{document}` 之间内容按 `paper-structure.tex` 的 `\input` 顺序展开 `blocks/` 与 `sections/`，去掉 `%` 注释、空白与空行后必须逐字符相等。这一步证明标题/摘要/AI 段/参考文献/末页清单是“搬家不换字”。
2. **渲染级**：xelatex 跑两遍，断言页数仍 32；PyMuPDF 逐页 `get_text()`，每页 `re.sub(r"\s+","",text)` 后完全相等；总非空白字符数与基线一致。
3. **结构级**：`doc.get_toc()` 仍 39 条，标题、层级、页码完全一致；`main.aux` 的 20 条 `\newlabel` 键/编号/页码与 39 条 `\contentsline` 与 before 完全一致（aux 无时间戳，适合做版式不变量）。
4. **字节级（仅二次判据）**：同机、同 TeX Live、`SOURCE_DATE_EPOCH=0 FORCE_SOURCE_DATE=1` 时比较 PDF sha；**不能替代**文本/页数判据。

### 6.3 发布登记

- 重编译后必须重新 `bind_map`（写新 `pdf_sha256` + `structure_sha256`），并重签 `paper/formula-review.json` 的 `pdf_sha256`；`source_sha256`/`page` 不变（当前锚 `paper/sections/5_problem1.tex:96`、page 9）。
- 这不是内容变化，是发布登记；不重绑/重签 → `python -m lib.publication check` 必红（`lib/publication/checks.py:478-479,311`）。

### 6.4 不可用判据

- PDF 字节哈希（xelatex 的 `/CreationDate`、`/ID` 每次都变）；
- `main.log`（含时间戳与路径）；
- docx/Word 对照（P1 不产出）；
- 只做源文件 diff 而不看 PDF（会漏版面漂移）。

### 6.5 验收产物

一次性脚本 `_tmp/equiv/equiv_check.py`（用 Write 工具落盘，避免 heredoc 吃反斜杠），产物存 `_tmp/equiv/`（`before.pdf`、`after.pdf`、`report.json`），**不进正式回归**（依赖本机 TeX 与当前论文内容）。

---

## 7. 分步实施顺序（每步可单独验证/回滚）

> 工作区不是干净的实验分支：每步动手前把受影响文件复制到 `_tmp/p1_backup/<step>/`，回滚 = 复制回来；不依赖 VCS。

| 步 | 动作 | 验证 | 回滚 |
|---|---|---|---|
| 0 | 冻结基线（§6.1）；修 `docs/PAPER_ROLES.md` 五处规范矛盾（§3.11） | 文档自检；`test_lib_layout`/`test_doc_drift` 仍绿 | 恢复文档备份 |
| 1 | 新增模板 `roles.json`、`structure.default.json`、`blocks/`、默认 `paper-structure.tex`；模板 `main.tex` **暂不动** | `regression/test_templates_compile.py` 仍绿；roles schema 单测 | 删除新增文件 |
| 2 | 新增 `lib/paper_structure/` + 单测；对 `_tmp/equiv/struct/` 空跑 `assemble`（不碰 `paper/`） | 连跑两遍字节一致；`problem_count=3`；`python -m <paper_structure> check` 通过 | 删除包与 `_tmp` 输出 |
| 3 | 迁移当前 `paper/`：blocks 六个文件 + `paper-structure.tex` + `main.tex` 外壳 | 源级重建对照；编译 32 页；逐页文本/TOC/aux 对照；`check_skeleton` 仍 PASS | 从 `_tmp/p1_backup/step3/paper/` 恢复 |
| 4 | 模板 `main.tex` 切稳定外壳 | `test_templates_compile.py` 两遍 xelatex rc=0；模板默认结构可编译 | 恢复模板 `main.tex` |
| 5 | `check_skeleton` 角色模式（双路径）+ scans 加 blocks | 旧 `test_skeleton.py` 全绿；新增角色用例；当前论文 role 路径 PASS | 恢复 `check_skeleton.py` |
| 6 | `lib/publication` 结构驱动 + `structure_sha256`；重绑 page-map/重签 formula-review | `test_publication.py` 全绿；当前论文 PASS；markers 逐字等于 config | 恢复 checks.py/page-map/formula-review 备份 |
| 7 | `lib/delivery` 正文名/必交件/清单对账 | `test_delivery.py` 全绿；当前正文名仍“看见声音：….pdf”；清单对账 PASS | 恢复 delivery 文件 |
| 8 | `server.py` 指纹/prompt/`_artifact_ok`/`_mechanical_floor`；`workflow_quality.py` 确认不排除 structure.json | `test_stale_noise.py`/`test_workflow.py` 新用例；`_artifact_ok` 缺结构文件返回 False | 恢复 server.py |
| 9 | SKILL 9/14/15、`writing_check.sh`、`docs/PUBLICATION.md`、healthcheck | `test_doc_drift.py`/`test_lib_layout.py`；`writing_check.sh` 无假 warning；healthcheck 通过 | 恢复文档/脚本 |
| 10 | 全量回归 + 真实论文 A/B + `python lib/web/healthcheck.py` | §8 的最小验收 A/B/C 全绿 | 逐步回滚到任一步 |

**依赖顺序不可颠倒的点：**

- 第 3 步（title/abstract 搬家）必须先于第 6 步（`body_pdf_name` 改读 structure）和第 8 步（`main.tex` 进 `_LAYOUT_OWNED_PATHS`）。
- 第 1 步（模板 blocks）必须先于第 4 步（模板 main.tex 切壳），否则 `test_templates_compile.py` 与 ⑨ 步骤 2 空编译必红。
- 第 2 步（assembler）必须先于第 3 步（生成 `paper/paper-structure.tex`）。

---

## 8. 测试清单

### 8.1 新增 `regression/test_paper_roles`（离线、快；实现时加 `.py`）

| 类 | 方法（至少） | 断言 |
|---|---|---|
| `RolesSchemaTests` | `test_template_roles_json_is_valid`、`test_every_role_implementation_file_exists`、`test_core_roles_are_not_disablable`、`test_optional_roles_are_disablable`、`test_page_kinds_are_known`、`test_repeat_contract_is_complete`、`test_broken_roles_json_is_rejected` | 13 个角色、路径存在、核心/可选 disablable 矩阵、page_kind 属于 `KINDS`（`lib/publication/checks.py:11`）、repeat 能展开 N |
| `ProblemCountTests` | `test_profile_explicit_count_wins`、`test_intake_list_used_when_certain`、`test_intake_string_is_not_len`、`test_count_uncertain_falls_back_to_analysis`、`test_no_source_exits_5_without_writing`、`test_current_workspace_resolves_to_3` | 四级优先级；当前 N=3、source=analysis_report:1.2；失败不写半成品 |
| `AssemblerTests` | `test_default_assembly_matches_current_main_tex`、`test_default_assembly_is_byte_idempotent`、`test_no_timestamps_in_outputs`、`test_model_repeats_expand_to_problem_count`、`test_floatbarrier_preserved`、`test_ai_block_omitted_when_disabled`、`test_pinned_first_last`、`test_disabled_core_role_fails` | 输入顺序与 `paper/main.tex:98-142` 等价；两遍 sha 相同；AI 关闭仅作 P2 能力单测 |
| `StructureJsonTests` | `test_title_is_null_before_sync`、`test_sync_title_fills_from_title_block`、`test_sync_title_refuses_placeholder`、`test_sync_title_does_not_touch_other_bytes`、`test_enabled_equals_order_minus_disabled`、`test_section_numbers_follow_enabled_order`、`test_page_kinds_partition_enabled_roles`、`test_page_markers_equal_current_config`、`test_structure_tex_sha256_matches`、`test_deliverables_follow_enabled_roles` | 当前 markers 逐字等于 `config/publication.json:45-50` |
| `MainShellTests` | `test_main_tex_is_shell`、`test_result_values_and_penalties_remain`、`test_title_and_abstract_are_blocks`、`test_no_sections_in_main` | 外壳只允许 documentclass/_base/result-values/penalties/labels/paper-structure |
| `TitleAbstractMoveTests` | `test_title_block_is_verbatim`、`test_abstract_block_is_verbatim` | 用 `check_skeleton._balanced`（`:115-128`）从冻结旧稿取参数逐字比对 |
| `EffectivePolicyTests` | `test_default_markers_equal_legacy_config`、`test_ai_off_renumbers_references`、`test_references_shares_ai_page`、`test_bind_and_inspect_use_same_policy`、`test_broken_structure_is_reported` | 默认行为不变；共页归并；坏 JSON 响亮失败 |

### 8.2 新增 `regression/test_paper_roles_pdf`（xelatex，慢；实现时加 `.py`）

| 类 | 方法 | 断言 |
|---|---|---|
| `P1PdfEquivalenceTests` | `test_rendered_page_count_is_unchanged`、`test_per_page_text_is_identical`、`test_toc_is_identical`、`test_aux_newlabels_are_identical`、`test_no_unresolved_references`、`test_reproducible_bytes_with_source_date_epoch`（可选） | 32 页、逐页文本、TOC 39 条、aux 20 newlabel；字节只在同机同版本可复现 |
| `LivePaperEquivalenceTests` | `test_live_paper_pages_and_text_match_baseline` | env `P1_BASELINE_PAPER` 指向改动前 `paper/` 快照；不在干净检出上跑 |

### 8.3 扩展既有测试

| 文件 | 类/方法 | 断言 |
|---|---|---|
| `regression/test_skeleton.py:81-92` | 保留 `SkeletonTests.setUp`，新增 `RoleSkeletonTests`：`test_role_workspace_passes`、`test_missing_required_role`、`test_disabled_role_leftover`、`test_order_mismatch`、`test_orphan_block_or_section`、`test_problem_count_from_structure_not_files`、`test_main_tex_with_section_fails`、`test_structure_hash_mismatch`、`test_wording_and_caption_scan_blocks`、`test_legacy_fixture_still_passes` | 不把 67 条 legacy 用例改写成 role 用例 |
| `regression/test_publication.py:24-121` | 保留 POLICY/POLICY_MARKS；新增 `StructureMarkerPolicyTests`、`StructureDigestBindingTests`、`AbstractBoldFromBlocksTests` | 默认 markers 等于 config；改 structure 后报未绑定；摘要加粗从 blocks 读 |
| `regression/test_delivery.py:761-802` | `BodyPdfNamingTests` 增加 `test_name_comes_from_structure_json`、`test_structure_wins_over_legacy_papertitle`、`test_legacy_fallback_still_works`、`test_bad_or_empty_structure_falls_back`、`test_reserved_characters_are_stripped`、`test_round_trip_to_paper_main_pdf` | 四级回落；当前标题名不变 |
| `regression/test_delivery.py:225-236` | `ChecklistConsistencyTest.setUp` 补写 `paper/structure.json`；新增 `RoleDrivenRequiredItemsTests`、`ManifestBodySourceTests` | AI/附录禁用时不要求对应 PDF；`source=paper/main.pdf` 认正文 |
| `regression/test_stale_noise.py:555-630` | `ContentLayoutDecouplingTests` 增加 `test_main_tex_is_layout_owned`、`test_blocks_are_content_side`、`test_structure_json_is_content_side`、`test_paper_structure_tex_is_content_side`、`test_verify_still_sees_layout` | main.tex 变 → 内容判官不变；blocks/structure 变 → 内容判官变 |
| `regression/test_workflow.py:1922-1965` | 新增 `WriteStructurePromptTests`、`WriteArtifactOkTests`、`MechanicalFloorStructureRoutingTests` | prompt 含启用角色顺序且不含 disabled；缺结构文件 `_artifact_ok=False`；结构问题 target=write、page-map 未绑定 target=format |
| `regression/test_doc_drift.py:182-203` | `CheckerInstructionDependencyTest` 若 ⑮ 新增跑 check_skeleton 则期望集合加 `verify`；新增 `PaperRolesDocsTests`、`LayoutOwnedPathsSentinelTests`（AST：`paper/main.tex` 在 tuple、`paper/paper-structure.tex` 不在） | 文档不再说“摘要在 main.tex 的 \abstractcn”；旧口径哨兵 |
| `regression/test_templates_compile.py:66-95` | 新增 `test_template_has_roles_blocks_and_default_structure`；缺图扫描（`:97-123`）范围加 `blocks/` | 模板默认结构可编译；blocks 里的图引用也核 |
| `regression/test_lib_layout.py:44-70` | 现有扫描自动覆盖 `-m <paper_structure>` | `__main__.py` 存在 |
| `lib/web/healthcheck.py:45-53,71-81` | 新增模板 roles.json/blocks/paper-structure 检查；py_compile 新包 | 体检红在写坏时 |

### 8.4 最小验收命令

```bash
# A 快速（不需要 xelatex）
python -m unittest discover -s regression -p "test_paper_roles.py" -v
python -m unittest discover -s regression -p "test_skeleton.py" -v
python -m unittest discover -s regression -p "test_publication.py" -v
python -m unittest discover -s regression -p "test_delivery.py" -v
python -m unittest discover -s regression -p "test_stale_noise.py" -v
python -m unittest discover -s regression -p "test_doc_drift.py" -v
python -m unittest discover -s regression -p "test_lib_layout.py" -v

# B 渲染（需要 xelatex）
FMA_XELATEX=D:/texlive/2026/bin/windows/xelatex.exe \
  python -m unittest discover -s regression -p "test_paper_roles_pdf.py" -v
python -m unittest discover -s regression -p "test_templates_compile.py" -v

# C 真实论文 A/B
python lib/web/check_skeleton.py --json
python -m lib.publication check
python -m lib.delivery check
python lib/web/healthcheck.py
python -m unittest discover -s regression -v
```

---

## 9. 风险与需要用户拍板的事项

### 9.1 风险（按严重度）

1. **P0 `problem_count` 双口径**：`reports/INTAKE.json:8-14` 官方 subquestions=1（`confidence=medium`，uncertain 是 15 条字符串），而论文实际有 `5_problem1..3.tex` 三问、`2_analysis.tex` 三节。按 `len()` 直接生成会把 3 问论文改成 1 问，5_problem2/3 成孤儿，页数/内容全变。缓解：§4.2 双字段 + `analysis_report:1.2` 回退；当前 N=3。**需要用户拍板。**
2. **P0 `effective_profile.json` 无生产者**：全仓 grep 只在 `docs/PAPER_ROLES.md` 出现；P1 用 `structure.default.json` 桥接，P3 由驱动产出。若不桥接，步骤 2.5 无输入可读。
3. **P1 ⑨ 无 gate**：`lib/web/server.py:438` 的 write 没有 gate，`_artifact_ok`（`:743-750`）只查 `paper/main.pdf >80B`。assembler 失败、structure 缺半份都不会被驱动拦住。缓解：§3.8 的 `_artifact_ok` 加结构文件校验；必要时在 write 收尾跑 `python -m <paper_structure> check`。
4. **P1 稳定外壳丢编译必需项**：`result-values.tex`（模板 `main.tex:29`）、`\providecommand{\ResultValue}`（`:35`）、`clubpenalty/widowpenalty/pretocmd`（`:38-40`）、`labels_appendix`（`:46-47`）必须留在外壳，否则编译失败或版面变化。设计稿 `docs/PAPER_ROLES.md:353-359` 的极简示例不能照抄。
5. **P1 模板缺 blocks/paper-structure 会红**：`regression/test_templates_compile.py:66-95` 与 ⑨ 步骤 2 空编译都直接编译模板 `main.tex`。必须先加 blocks 与默认 `paper-structure.tex`，再切模板外壳。
6. **P1 `main.tex` 进 `_LAYOUT_OWNED_PATHS` 的时序**：该表语义是“对内容判官排除”（`lib/web/server.py:939-949,1275-1281`）。在 title/abstract 搬家前加入，会让 ⑩⑪⑫ 漏看摘要/标题修改（假 PASS）。必须第 3 步之后再加。
7. **P1 摘要页 99.83% 填充、counted 30/30 满额**：任何版面漂移都会让 `publication` FAIL（`config/publication.json:3-5,15-18`）。必须做 §6 的逐页文本/页数/TOC/aux 对照。
8. **P1 page-map/formula-review 的 sha 绑定**：重编译必然改 `pdf_sha256`；不重绑/重签，`publication` 必红（`lib/publication/checks.py:478-479,311`）。这是最容易被误判成“P1 改坏了”的地方。
9. **references 与 ai_statement 共页**：当前 `paper/page-map.json:18-24` 的 p31 是 `ai_statement`（AI+参考文献同页），设计稿 §5.2 示例却把 `references` 单列。照示例实现会让 `page_kinds` 校验失败或让“八+九合计≤1页”整组失效。必须用 `shares_page_with`/`page_kind_aliases` 归并。
10. **搬家导致检查静默失效**：`check_skeleton._wording_problems`（`:665-705`）与 `_caption_problems`（`:948-985`）只扫 `paper/sections` + `paper/main.tex`；`publication.style_hints`（`:289-300`）从 main.tex 抓 `\abstractcn`。摘要搬到 `blocks/abstract.tex` 后不补扫描就是假绿。
11. **生成物确定性**：`paper-structure.tex`/`structure.json` 不能写时间戳或随机键序，否则每次 assembler 重跑都改指纹，拖 write/format/verify 连锁重跑。
12. **`_base` 所有权与 `cp -r` 覆盖**：`skills/9Paper-writing/SKILL.md:405-408` 每次整目录 `cp -r`，会覆盖 ⑭ 的 `paper/_base` 与 `main.tex` 导言区；`skills/14Layout-and-format/SKILL.md:70-73` 又说发现不一致按模板重拷。P1 必须改为“缺失才复制/先归档”，否则稳定外壳被覆盖。
13. **`materials_list.disablable` 文档一致性**：已在 `docs/PAPER_ROLES.md` 统一为 `true`；实现时用测试锁住，防止再次漂移。
14. **`mode=inline/merged/none` 无机器锚点**：`docs/PAPER_ROLES.md:244-247` 只说“内容必须能在 host 里找到”，checker 无法机械判定。P1 只做 schema 校验与“P2 未实现”错误，锚点定义留 P2。
15. **`_cn_num` 20+ 错误**：`lib/web/check_skeleton.py:183-188` 对 20 以上输出“二零”；当前国赛 9 个编号节不受影响，若抽成共享函数必须先修 1..99。
16. **legacy 测试体量大**：`test_skeleton.py` 约 67 条、`test_delivery.py` 约 71 条；任何“必须 roles.json”的硬切换都会红。双路径是 P1 的必要代价。

### 9.2 已确认（2026-10-17）

| # | 事项 | 结论 |
|---|---|---|
| D1 | `problem_count` 的权威来源与 uncertain 语义 | **已确认**：双字段 `intake_subquestion_count`（审计）+ `problem_count`（驱动）；优先级 profile > INTAKE（certain）> ANALYSIS §1.2 > 失败；**题面没分问时由建模设计自命题**，§1.2 是决策记录；当前 N=3 |
| D2 | `materials_list` 是否可禁用 | **已确认**：可以，`disablable=true`；文档已统一 |
| D3 | 标题的权威与时机 | **按建议执行**：只由 ⑨ 写 `blocks/title.tex`，步骤 7 `sync-title` 回填；`fix`/`format` 不得改标题；若 `fix` 确需改标题，必须重跑 sync-title 并重绑 page-map |
| D4 | P1 是否包含 publication 的 structure 驱动 page_markers | **按建议执行**：包含；用“默认 markers 逐字等于 config”的金标测试锁住行为 |
| D5 | `_base`/`main.tex` 的复制与所有权 | **已确认**：⑨ 步骤 2 只在文件缺失时复制；`paper/_base` 与 `main.tex` 外壳归 ⑭，⑨ 不覆盖；加“⑨ 重跑不覆盖版式”测试 |
| D6 | references 与 AI 是否共页 | **按现状**：p31 共页；P1 用 alias 归并，不改版面 |
| D7 | P1 对 `mode=inline/merged/none` 的范围 | **按建议执行**：P1 只落 schema 校验与明确错误；真实 inline/none 写作与锚点检查放 P2 |
| D8 | 是否接受 prompt_for 改动导致全阶段一次性 stale-instr | **已确认**：接受（只标记、不重跑）；`server.py` 的任何 P1 改动都会带来这一轮提示 |

---

## 10. 明确不做的事

1. **不做 P2 整链能力**：不实现 AI 关闭全链、顺序调换全链、`mode=inline/merged/none` 的真实写作/检查；P1 只落 schema、失败规则与单元级能力测试。
2. **不删 legacy**：`check_skeleton` 的模板族比对、publication 的 `kind_start_markers`、delivery 的 `main.tex` 标题回退全部保留。
3. **不改 `lib/result_contract`**：`\ResultValue` 宏名、`render_text` 输出路径 `paper/result-values.tex/json`、registry/validation/audit 逻辑、`_DERIVED_RESULT_FILES`（`lib/web/server.py:930-931`）都不动。
4. **不改 demo/附录工程**：`_DEMO_OWNED_PATHS`（`lib/web/server.py:957-959`）、`lib/web/appendix_demo_figure.py`、`paper_appendix/sections/A_appendix.tex`、`paper_appendix/main.pdf`、⑯ 行为都不动。
5. **不改 `paper/main.pdf` 构建名**：所有按 `main.pdf` 找文件的调用（publication/verify/format）保持不变；只在打包时改名。
6. **不改 page-map/formula-review 路径与构建产物豁免**：`workflow_quality._is_paper_build_output:47-48` 保持；不把 `structure.json` 加进豁免。
7. **不改 publication 阈值/口径**：`config/publication.json:3-5`（30/30/25）、`:15`（first_kind）、`:19-28`（max_group_pages）、`:29`（require_appendix）、`:36-43`（fill）、`:45-50`（legacy markers）在 P1 保持数值不变。
8. **不改 check_skeleton 内容阈值**：假设 3–5 条/120/200 字（`:62-65`）、分析 1480 字/3/5 行（`:72-90`）、符号表三列（`:319-380`）、roadmap 0.85（`:849-856`）、图题 40 字（`:948-985`）。
9. **不改 delivery 语义**：demo 自包含/三维判据、A1 表解析（`lib/delivery/checks.py:292-343`）、manifest schema_version 1、`FIXED_SOURCES` 四条映射（`lib/delivery/core.py:81-84`）。
10. **不新增阶段/赛题 profile/MCM overlay**：步骤 2.5 是 SKILL 步骤；P3/P4 才加 profile 与英文族。
11. **不做 PDF 字节等价验收**、不产出 Word/docx、不拿 `main.log` 做判据。
12. **不重写论文内容**：标题/摘要/AI 段/参考文献/末页清单/模型节标题只逐字搬家；不改任何数值、措辞、图、表。
13. **不改历史目录**：`产物/`、`2026A试跑示例/`、`reports/` 历史记录、`_tmp/`、`tmp/`、`paper/` 旧稿（除 §3.2 的六个 block 与原文件搬空）。
14. **不让 ⑭ 改结构**：`paper-structure.tex`、`blocks/` 结构、`sections/` 结构由 ⑨ 负责；⑭ 只做版式手术，结构问题写 `HANDBACK_REQUEST.md` 回 ⑨。
