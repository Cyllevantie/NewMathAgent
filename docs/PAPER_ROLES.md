# 论文角色与结构计划（设计稿）

> 状态：2026-10-17 设计稿，**只定义角色与迁移口径，不改代码**。
> 用途：把“论文有哪些节、按什么顺序、哪些可关”从 `main.tex` 与检查器里抽出来，
> 变成一份**角色计划**。以后换赛题/换结构改数据，不改 Python。
>
> **AI 工具使用说明只是“可开关角色”的例子；当前国赛默认仍然启用，不删。**

---

## 0. 一句话结论

- **模板**负责“这个角色长什么样”（block / section 文件 / 独立工程）。
- **赛题 profile**负责“这篇论文要哪些角色、按什么顺序”。
- **驱动**把两者合成为 `effective_profile.json`，并生成 `paper/paper-structure.tex`。
- **检查器/交付/页映射**都读同一份解析结果，不再各自写死章节名。

---

## 1. 术语

| 术语 | 含义 |
|---|---|
| 角色（role） | 论文里的一个结构单元，例如“摘要”“问题重述”“AI 工具使用说明” |
| 模板角色表 | 模板目录里的 `roles.json`：角色 → 实现（block / file / external）+ 期望标题 |
| 赛题结构计划 | 赛题 profile 里的 `structure`：启用哪些角色、顺序、是否禁用 |
| 有效计划 | 驱动合并“模板默认 + 赛题覆盖”后的结果，落到 `runtime/effective_profile.json` |
| block | 直接写在正文主文件里的片段（摘要、AI 说明、参考文献、末页清单） |
| file | `sections/*.tex` 里的一个节文件 |
| external | 独立编译/独立交付的工程（`paper_appendix/` → `附录A.pdf`） |
| repeat | 按子问题数展开的角色（`model` 的 `5_problemN.tex`） |
| disablable | 该角色是否允许被赛题 profile 关掉；核心角色应为 `false` |

---

## 2. 当前国赛（cumcm-latex）角色表

> 说明：`page_kind` 是 `lib/publication` 的页面类别；`appendix` 指**正文最后一页的支撑材料清单**，
> 不是独立的 `附录A.pdf`。两者名字容易混，见 `appendix_pdf` 行。

| role id | 中文名 | 当前实现 | 编号/层级 | 默认必需 | 可禁用 | page_kind | 交付物/备注 |
|---|---|---|---|---|---|---|---|
| `title` | 论文标题 | `\papertitle{}`，正文主文件 | 不编号 | 是 | 否 | —（与摘要同页） | 正文 PDF 文件名来源 |
| `abstract` | 摘要 + 关键词 | `\abstractcn{}{}`，正文主文件 | 不编号 | 是 | 否 | `abstract` | 限 1 页；关键词数量由赛题 profile 定 |
| `restatement` | 问题重述 | `sections/1_restatement.tex` | 一级 | 是 | 否 | `body` | 末尾放 `fig_roadmap`（图 1） |
| `analysis` | 问题分析 | `sections/2_analysis.tex` | 一级 | 是 | 否 | `body` | 含“问题一/二/…的分析”+“本文主要创新点” |
| `assumptions` | 模型假设 | `sections/3_assumptions.tex` | 一级 | 是 | 否 | `body` | 3–5 条（赛题/评分标） |
| `symbols` | 符号说明 | `sections/4_symbols.tex` | 一级 | 是 | 否 | `body` | 三列符号表 |
| `model` | 模型的建立与求解 | 正文主文件的 `\section{模型的建立与求解}` + `sections/5_problemN.tex` | 一级 + 每个子问题一个 `\subsection` | 是 | 否 | `body` | `repeat=problem`；N 由题面决定 |
| `check` | 模型检验与分析 | `sections/6_check.tex` | 一级 | 是 | 否 | `body` | 误差分析 / 灵敏度分析 |
| `evaluation` | 模型的评价与推广 | `sections/7_evaluation.tex` | 一级 | 是 | 否 | `body` | 优点 / 缺点 / 改进与推广 |
| `ai_statement` | AI 工具使用说明 | 正文主文件的 `\section{AI 工具使用说明}` + 一段声明 | 一级 | 国赛是 | **是**（示例开关） | `ai_statement` | 交付 `AI工具使用详情.pdf`；关掉时两件一起关 |
| `references` | 参考文献 | `\referencescn` + `references.tex` | 一级 | 是 | 否 | `references` | `\referencescn` 发出 `\section{参考文献}` |
| `materials_list` | 支撑材料清单（正文末页） | `\appendixAcn[支撑材料清单]{A1_materials}` + `sections/A1_materials.tex` | 不编号附录 | 是 | 是 | `appendix` | 正文 PDF 最后一页；表体由清单生成；可单独关闭 |
| `appendix_pdf` | 独立附录（补充推导/图表） | `paper_appendix/` 独立工程：`main.tex` + `sections/A_appendix.tex` | 独立 PDF 的 `A.x` | 国赛是 | **是** | —（不在正文 page-map） | 交付 `附录A.pdf`；与 `materials_list` 不是同一件事 |

### 2.1 不在角色表里的东西

- `result-values.tex`、`_base/preamble.tex`、`_base/macros.tex`：模板基础设施，不是论文角色。
- `paper/page-map.json`、`paper/formula-review.json`：发布登记件，由角色计划解析后生成/重绑。
- `reports/SUBMISSION_MANIFEST.json`、`运行说明.md`：交付层文件，不是论文角色。
- `demo.html`：⑯ 的交付物，不是论文角色。
- `AI工具使用详情.pdf`、`附录A.pdf`：**挂在角色上的交付物**，不是独立角色；角色关掉时它们一起关。

---

## 3. 模板角色表 `roles.json`（建议 schema）

位置建议：`templates/<语言>/<族>/roles.json`（与 `main.tex` 同目录）。
只描述“角色怎么实现”，不描述“这场比赛要不要它”。

```json
{
  "schema_version": 1,
  "template": "zh/cumcm-latex",
  "roles": {
    "title": {
      "label": "论文标题",
      "placement": "block",
      "block": "blocks/title.tex",
      "required": true,
      "disablable": false,
      "numbering": "unnumbered",
      "pinned": "first",
      "page_kind": null
    },
    "abstract": {
      "label": "摘要",
      "placement": "block",
      "block": "blocks/abstract.tex",
      "required": true,
      "disablable": false,
      "numbering": "unnumbered",
      "pinned": "after:title",
      "page_kind": "abstract",
      "headings": ["摘要"]
    },
    "restatement": {
      "label": "问题重述",
      "placement": "file",
      "file": "sections/1_restatement.tex",
      "required": true,
      "disablable": false,
      "numbering": "section",
      "page_kind": "body",
      "headings": ["问题重述", "问题背景", "问题提出"]
    },
    "analysis": {
      "label": "问题分析",
      "placement": "file",
      "file": "sections/2_analysis.tex",
      "required": true,
      "disablable": false,
      "mode": "section",
      "numbering": "section",
      "page_kind": "body",
      "headings": ["问题分析", "问题一的分析", "问题二的分析", "问题三的分析", "本文主要创新点"],
      "repeat": {"kind": "problem", "headings_per_problem": ["问题{N}的分析"]}
    },
    "assumptions": {
      "label": "模型假设",
      "placement": "file",
      "file": "sections/3_assumptions.tex",
      "required": true,
      "disablable": false,
      "mode": "section",
      "numbering": "section",
      "page_kind": "body",
      "headings": ["模型假设"]
    },
    "symbols": {
      "label": "符号说明",
      "placement": "file",
      "file": "sections/4_symbols.tex",
      "required": true,
      "disablable": false,
      "mode": "section",
      "numbering": "section",
      "page_kind": "body",
      "headings": ["符号说明"]
    },
    "model": {
      "label": "模型的建立与求解",
      "placement": "file",
      "wrapper_block": "blocks/model_section.tex",
      "file": "sections/5_problem1.tex",
      "required": true,
      "disablable": false,
      "numbering": "section",
      "page_kind": "body",
      "repeat": {
        "kind": "problem",
        "file_pattern": "sections/5_problem{N}.tex",
        "heading_pattern": "问题{N}的模型的建立和求解",
        "headings": ["具体分析", "模型准备", "模型建立", "模型求解"],
        "optional_headings": ["结果分析"]
      }
    },
    "check": {
      "label": "模型检验与分析",
      "placement": "file",
      "file": "sections/6_check.tex",
      "required": true,
      "disablable": false,
      "numbering": "section",
      "page_kind": "body",
      "headings": ["模型检验与分析", "误差分析", "灵敏度分析"]
    },
    "evaluation": {
      "label": "模型的评价与推广",
      "placement": "file",
      "file": "sections/7_evaluation.tex",
      "required": true,
      "disablable": false,
      "numbering": "section",
      "page_kind": "body",
      "headings": ["模型的评价与推广", "模型的优点", "模型的缺点", "模型的改进与推广"]
    },
    "ai_statement": {
      "label": "AI 工具使用说明",
      "placement": "block",
      "block": "blocks/ai_statement.tex",
      "required": true,
      "disablable": true,
      "numbering": "section",
      "page_kind": "ai_statement",
      "headings": ["AI 工具使用说明"],
      "deliverables": ["AI工具使用详情.pdf"]
    },
    "references": {
      "label": "参考文献",
      "placement": "block",
      "block": "blocks/references.tex",
      "required": true,
      "disablable": false,
      "numbering": "section",
      "page_kind": "references",
      "headings": ["参考文献"]
    },
    "materials_list": {
      "label": "支撑材料清单",
      "placement": "block",
      "block": "blocks/materials_list.tex",
      "required": true,
      "disablable": true,
      "numbering": "unnumbered-appendix",
      "pinned": "last",
      "page_kind": "appendix",
      "headings": ["附录"]
    },
    "appendix_pdf": {
      "label": "独立附录 A",
      "placement": "external",
      "project": "paper_appendix/",
      "main": "main.tex",
      "body": "sections/A_appendix.tex",
      "required": true,
      "disablable": true,
      "numbering": "appendix-A",
      "page_kind": null,
      "deliverables": ["附录A.pdf"]
    }
  }
}
```

要点：

- `required` 是模板默认；`disablable` 才决定赛题能不能关。
- **核心内容角色**（`analysis`/`assumptions`/`symbols`）`disablable: false`；
  它们可以换 `mode`（见 3.1），但不允许用 `disabled` 静默删除。
- `pinned` 只用于结构性位置（标题在最前、支撑材料在正文最后）；普通角色可在 `order` 里任意排。
- `repeat` 的 `N` 来自**题面子问题数**，不是赛题格式；`analysis` 与 `model` 必须用同一个 N。
- `page_kind` 与 `lib/publication` 的 `KINDS` 对齐；`appendix_pdf` 不属于正文 page-map，所以是 `null`。
- `headings` 是“期望标题”，检查器按角色校验，不再按文件名一刀切。

### 3.1 核心角色的 `mode`：不删除，只换形态

赛题差异经常是“这一节要不要单独成节”，不是“内容要不要存在”。因此核心角色用
`mode` 表达形态，而不是用 `disabled` 表达删除：

| mode | 含义 | 检查器怎么核 |
|---|---|---|
| `section` | 独立成节，默认 | 角色有自己的标题与文件 |
| `inline` | 内容并入 `host` 角色（例如假设写进模型建立开头） | 不出现独立标题；内容必须能在 `host` 里找到 |
| `merged` | 内容并入 `host` 的导语/分析（例如问题分析并入模型建立的“具体分析”） | 不出现独立标题；内容必须能在 `host` 里找到 |
| `none` | 内容完全不存在 | 必须带 `waiver` 理由；检查器记成“结构偏离”，不静默通过 |

例子：

```json
"assumptions": {"mode": "inline", "host": "model"},
"symbols":     {"mode": "inline", "host": "model"},
"analysis":    {"mode": "section"}
```

规则：

- `inline`/`merged` 必须声明 `host`，且 `host` 必须是启用角色；
- `none` 必须带非空 `waiver`，否则 profile 校验失败；
- `mode` 只用于核心内容角色；`ai_statement`/`appendix_pdf`/`materials_list` 这类
  真正可选的件仍然用 `disabled`；
- 检查器不会因为 `mode: inline` 就免检内容——它只改变“内容在哪里”，不改变“内容必须存在”。

---

## 4. 赛题结构计划（profile 里的 `structure`）

### 4.1 当前国赛（全部启用，保持现状）

```json
{
  "structure": {
    "order": [
      "title",
      "abstract",
      "restatement",
      "analysis",
      "assumptions",
      "symbols",
      "model",
      "check",
      "evaluation",
      "ai_statement",
      "references",
      "materials_list"
    ],
    "disabled": [],
    "supplement": ["appendix_pdf"],
    "problem_count_source": "reports/INTAKE.json#problem.subquestions"
  }
}
```

### 4.2 关掉 AI 说明（只是示例，默认不关）

```json
{
  "structure": {
    "order": [
      "title", "abstract", "restatement", "analysis", "assumptions",
      "symbols", "model", "check", "evaluation",
      "references", "materials_list"
    ],
    "disabled": ["ai_statement"],
    "supplement": ["appendix_pdf"]
  }
}
```

关掉后必须自动连带：

1. 不生成 `blocks/ai_statement.tex` 的包含；
2. 正文节号顺延（参考文献从“九、”变“八、”）；
3. `page_kind=ai_statement` 从 page-map 的类别与 `max_group_pages` 规则里消失；
4. 交付不再要求 `AI工具使用详情.pdf`；
5. ⑨ 的写作指令不再要求写“§八”；
6. `paper/page-map.json` 重新声明并 `map`，`formula-review.json` 重新签页号。

### 4.3 调顺序（示例）

```json
{
  "structure": {
    "order": [
      "title", "abstract", "restatement", "assumptions", "analysis",
      "symbols", "model", "check", "evaluation", "ai_statement",
      "references", "materials_list"
    ],
    "disabled": []
  }
}
```

调顺序只改 `order`；生成器按顺序输出。检查器按 `paper/structure.json` 的实际顺序校验；
页映射需要重新 `map`，公式复核需要重新签物理页。

### 4.4 新增/替换结构

- **只多一个可选节**：模板 `roles.json` 加一条 + 一个 block/file，profile 的 `order` 引用它。
- **整族骨架不同**（如 MCM）：profile 写 `"overlay": "mcm"`，模板提供 `roles.mcm.json`；
  角色 id 尽量复用（abstract/restatement/model/...），实现与顺序按族给。
  这是模板层的一次性扩展，不是每个赛题改 Python。

---

## 5. 生成的中间文件

### 5.1 `paper/paper-structure.tex`（正文组合文件）

由 ⑨ 依据 `effective_profile.json` 生成；**不要手改**。`paper/main.tex` 保持稳定：

```latex
\input{_base/preamble.tex}
\input{_base/macros.tex}
\begin{document}
\input{paper-structure.tex}
\end{document}
```

生成物示例（国赛、AI 启用）：

```latex
% generated from effective_profile.json; don't hand-edit
\input{blocks/title}
\input{blocks/abstract}
\input{sections/1_restatement}
\input{sections/2_analysis}
\input{sections/3_assumptions}
\FloatBarrier
\input{sections/4_symbols}
\input{blocks/model_section}
\input{sections/5_problem1}
\input{sections/5_problem2}
\input{sections/5_problem3}
\input{sections/6_check}
\input{sections/7_evaluation}
\input{blocks/ai_statement}
\input{blocks/references}
\input{blocks/materials_list}
```

AI 关闭时，生成器直接不写 `blocks/ai_statement` 那一行；其余顺序不变。

### 5.2 `paper/structure.json`（解析结果，给检查器/交付/页映射读）

```json
{
  "schema_version": 1,
  "profile": "cumcm_2026",
  "template": "zh/cumcm-latex",
  "problem_count": 3,
  "enabled": ["title", "abstract", "restatement", "analysis", "assumptions",
              "symbols", "model", "check", "evaluation", "ai_statement",
              "references", "materials_list"],
  "disabled": [],
  "supplement": ["appendix_pdf"],
  "page_kinds": {
    "abstract": ["title", "abstract"],
    "body": ["restatement", "analysis", "assumptions", "symbols", "model", "check", "evaluation"],
    "ai_statement": ["ai_statement"],
    "references": ["references"],
    "appendix": ["materials_list"]
  },
  "section_numbers": {
    "restatement": "一",
    "analysis": "二",
    "assumptions": "三",
    "symbols": "四",
    "model": "五",
    "check": "六",
    "evaluation": "七",
    "ai_statement": "八",
    "references": "九"
  },
  "deliverables": ["正文.pdf", "附录A.pdf", "AI工具使用详情.pdf", "运行说明.md"]
}
```

`section_numbers` 由启用的一级角色按顺序算出；AI 关闭时 `references` 自动变“八”。
这样 `publication` 的 `kind_start_markers` 不再写死“八、”“九、”。

### 5.3 生成时机：⑨ 的步骤 2.5

位置固定在 ⑨ 工作流的：

1. **步骤 2 复制模板之后**；
2. **步骤 3 图表规划 / 步骤 4 写各节之前**。

理由：

- `paper/` 已经存在；
- 模板 `roles.json`、驱动解析好的 `effective_profile.json`、`reports/INTAKE.json` 都已可用；
- 写手在动笔前就知道“要写哪些角色、按什么顺序”；
- ⑭ 不参与结构生成，边界清楚。

执行方式（assembler 的最终模块名待定，先用占位符表示）：

```bash
python -m <assembler> assemble \
  --profile runtime/effective_profile.json \
  --template zh/cumcm-latex \
  --out paper/
```

输入：

- `runtime/effective_profile.json`（驱动已解析好）；
- `templates/<语言>/<族>/roles.json`；
- `reports/INTAKE.json#problem.subquestions`（子问题数）。

输出：

- `paper/paper-structure.tex`
- `paper/structure.json`

约定：

- **幂等**：重跑 ⑨ 覆盖这两个文件；
- `problem_count` 缺失或 `uncertain` ⇒ **直接失败，不猜**；
- 生成文件头写“generated from effective_profile.json; don't hand-edit”；
- `fix` / `format` 不改这两个文件；要改结构，走 `HANDBACK_REQUEST.md` 回 ⑨；
- 生成成功后，`paper/structure.json` 进入 ⑨ 的产物声明，并作为 ⑭/⑮ 的输入。

---

## 6. 各类消费者怎么改

| 消费者 | 现在 | 改成读 |
|---|---|---|
| ⑨ 生成正文 | `main.tex` 固定 `\input` | `effective_profile.json` + 模板 `roles.json` → `paper-structure.tex` |
| `lib/web/check_skeleton.py` | 文件集合 + 标题序列必须等于某一族 | `paper/structure.json` + `roles.json`，按角色校验 |
| `lib/publication` | `kind_start_markers` 写死“摘要/一、/八、/附录” | `structure.json` 的 `page_kinds` + `section_numbers` |
| `lib/delivery` | 固定要求 AI PDF/附录 PDF | 只看启用角色的 `deliverables`；正文名从 `structure.json` 的 `title` 取 |
| ⑨ SKILL / prompt | 写死“§八 只写一句” | 注入启用角色列表；禁用角色不写 |
| ⑭ 排版 | 拥有 `paper/_base` 与 `main.tex` 导言区 | `main.tex` 只留稳定外壳；`paper-structure.tex` / `blocks` / `sections` 只做版式，不改结构 |
| ⑮ 验收 | 逐页看结果 | 读 `structure.json` 核对实际结构 |
| page-map / formula-review | 写死页段 | 按 `structure.json` 的页类别和物理页重新声明/重签 |

---

## 7. 检查器规则（按角色，而不是按文件名）

`check_skeleton` 的目标从“找一族完全匹配的模板”改成“核对有效角色计划”：

1. **必需角色**：`required && !disabled` 的角色必须出现且只出现一次。
2. **禁用角色**：`disabled` 里的角色必须不出现。
3. **顺序**：实际顺序必须等于 `order`；`pinned` 角色必须满足 first/last。
4. **重复角色**：`model` 的 `5_problemN` 数量必须等于 `problem_count`；
   `analysis` 的“问题N的分析”数量也必须等于它。
5. **形态**：`mode=section` 必须有独立标题与文件；`mode=inline/merged` 不出现独立标题，
   但内容必须能在声明的 `host` 角色里找到；`mode=none` 必须有非空 `waiver`。
6. **标题**：每个角色文件内的标题序列必须等于 `roles.json` 的 `headings`；
   `optional_headings`（如“结果分析”）可多可少。
7. **孤儿文件**：`paper/sections/*.tex` 里出现没有被任何启用角色引用的文件 ⇒ 报错
   （防止从上一个赛题/上一套结构残留）。
8. **交付**：`materials_list` 启用时核对 A1 表与清单；`appendix_pdf` 启用时核对
   `paper_appendix/main.tex` 可编译、`附录A.pdf` 有源。
9. **页标记**：`structure.json` 的 `section_numbers/page_kinds` 必须与 page-map 声明一致；
   换结构/顺序后必须重新 `map`，旧绑定直接报“未绑定当前 PDF”。

---

## 8. 关 AI 说明时，为什么不会再漏

如果没有角色计划，关 AI 要改 6 处（`main.tex`、`check_skeleton`、`publication.json`、
`delivery`、SKILL、page-map）。有角色计划后，只有一处：

```json
"disabled": ["ai_statement"]
```

其余全部从 `structure.json` 派生：

- 生成器不写 block；
- 检查器不要求；
- `section_numbers` 自动顺延；
- `page_kinds` 没有 `ai_statement`；
- `deliverables` 没有 `AI工具使用详情.pdf`；
- prompt 不注入“写 §八”；
- page-map 重新声明时没有该类别。

**前提是：`materials_list`、`appendix_pdf`、`AI工具使用详情.pdf` 的“必交”状态也来自角色计划，
而不是各自写死。**

---

## 9. 迁移顺序（建议）

### P1：角色化，行为不变
- 给当前国赛模板加 `roles.json`；
- 把 `paper/main.tex` 改成**稳定外壳**（`\documentclass` + `_base` 输入 +
  `\input{paper-structure.tex}`）；
- 把 `\papertitle` / `\abstractcn` 移到 `paper/blocks/title.tex` / `abstract.tex`；
- 在 ⑨ 步骤 2.5 生成 `paper/paper-structure.tex` 与 `paper/structure.json`；
- `check_skeleton` 改成按角色校验；
- `lib/delivery` 的正文名改读 `structure.json` 的 `title`；
- 现有论文**内容等价**（`main.tex` 拆分、标题摘要搬家不算内容变化）。

### P2：开关 / 形态 / 顺序用例
- 关 `ai_statement`：正文无该节、节号顺延、交付不要求 AI PDF、page-map 类别消失；
- 调换 `assumptions` 与 `symbols` 顺序：生成器顺序变、检查器过、重新 `map`；
- 把 `assumptions` 设为 `mode=inline, host=model`：不出现独立节，内容必须能在模型建立里找到；
- 结构生成失败用例：`INTAKE.json` 标 `uncertain` ⇒ assembler **直接失败**，不猜。
- 这些只作为**能力测试**；国赛默认配置保持 AI 启用、核心角色 `mode=section`。

### P3：加第二个赛题 profile
- 只写 `contests/<id>.json`，不写 Python；
- 验证“加赛题 = 加 JSON”。

### P4：MCM/英文 overlay
- 需要不同骨架/语言时，加 `roles.mcm.json` 与语言包，不提前抽象。

---

## 10. 已决定（2026-10-17）

1. **`title` 独立成 metadata 角色，不并进 `abstract`。**
   它永远第一个、永远不禁用，但允许不同赛题换“标题页/封面”实现；
   `abstract` 只负责摘要正文与关键词。
2. **`materials_list` 与 `appendix_pdf` 分成两个独立角色，国赛默认都启用，但都可以单独关闭。**
   - `materials_list`：正文 PDF 最后一页的支撑材料清单表（当前 P32），`page_kind=appendix`；
   - `appendix_pdf`：独立编译的 `附录A.pdf`，不在正文 page-map 里；
   - 关 `materials_list` 时同步关 A1/清单一致性检查与 `require_appendix`；
     关 `appendix_pdf` 时同步从交付必交件与 A1 表里去掉 `附录A.pdf`。
3. **`problem_count` 的唯一来源是 `reports/INTAKE.json#problem.subquestions`；题面没分问时由建模设计自命题。**
   它是列表就取长度，是计数就直接取；读题阶段标了 `uncertain` 或字段缺失时，
   用 `reports/ANALYSIS_MODELING_REPORT.md` 的结构化子问题列表确认——**题面没有明确分问时，
   由 ② 建模设计自行决定拆成几问，§1.2 是这项决策的记录；INTAKE 的读数只做审计**
   （`intake_subquestion_count`），不强行决定论文问数。
   `paper/sections/5_problem*.tex` 的文件数只做“至少有一个问题文件、编号连续”的健全性检查，
   **不再作为 N 的来源**——否则“题面 4 问、两边都只写 3 问”会被静默放过。
4. **核心内容角色（`analysis`/`assumptions`/`symbols`）不允许用 `disabled` 删除；允许 `mode` 变形态。**
   - 模板里 `disablable: false`；
   - `mode=section|inline|merged|none`，其中 `inline/merged` 必须给 `host`，
     `none` 必须给非空 `waiver`；
   - 真正可关闭的只有 `ai_statement`、`appendix_pdf`、`materials_list` 这类可选项。
5. **结构文件在 ⑨ 的步骤 2.5 生成：步骤 2 复制模板之后、步骤 3/4 写内容之前。**
   - 输入：`runtime/effective_profile.json` + `templates/<语言>/<族>/roles.json` +
     `reports/INTAKE.json#problem.subquestions`；
   - 输出：`paper/paper-structure.tex` + `paper/structure.json`；
   - `problem_count` 缺失或 `uncertain` ⇒ 直接失败，不猜；
   - 幂等覆盖；`fix`/`format` 不改这两个文件。
6. **`paper/main.tex` 与 ⑭ 的边界采用“稳定外壳 + 生成结构 + 内容 blocks”。**

   | 文件 | Owner | 说明 |
   |---|---|---|
   | `paper/main.tex` | ⑭ | 只留 `\documentclass` + `_base` 输入 + `\input{paper-structure.tex}`；⑨ 复制后不再改 |
   | `paper/paper-structure.tex` | ⑨（生成） | 正文角色顺序；⑭ 只读，改结构必须交回 ⑨ |
   | `paper/blocks/title.tex`、`abstract.tex`、`ai_statement.tex`、`references.tex`、`materials_list.tex` | ⑨ | 内容；⑭ 只做版式 |
   | `paper/sections/*.tex` | ⑨ | 内容；⑭ 只做定点版式手术 |
   | `paper/_base/*.tex` | ⑭ | 模板运行副本；⑨ 不碰 |
   | `paper/structure.json` | 生成器/⑨ | ⑭/⑮ 只读 |

   - `paper/main.tex` 加入版式侧指纹（`_LAYOUT_OWNED_PATHS`），⑭ 改导言区不再让内容判官重判；
   - `paper/paper-structure.tex`、`blocks/`、`sections/` 保持内容侧；
   - `\papertitle`/`\abstractcn` 移到 `blocks/` 后，`lib/delivery.body_pdf_name`
     改读 `structure.json` 的 `title`，不再正则解析 LaTeX；
   - ⑭ 发现结构问题写 `HANDBACK_REQUEST.md` 回 ⑨，不直接改结构文件。

---

## 11. 实施检查点（不是开放问题）

1. P1 必须验证正文**内容等价**；`main.tex` 拆分与标题/摘要搬家要有逐字对照。
2. P2 必须覆盖：AI 关闭、顺序调换、`mode=inline`、`INTAKE uncertain` 时 assembler 失败。
3. 任何结构/角色变化都必须进 ⑨ 的输入指纹；结构文件归 ⑨，⑭ 不改。

---

## 附录 A：当前国赛正文的实际顺序（改造前）

```text
\papertitle{...}
\abstractcn{...}{...}
sections/1_restatement
sections/2_analysis
sections/3_assumptions
\FloatBarrier
sections/4_symbols
\section{模型的建立与求解}
sections/5_problem1
sections/5_problem2
sections/5_problem3
sections/6_check
sections/7_evaluation
\section{AI 工具使用说明}
\referencescn
\appendixAcn[支撑材料清单]{A1_materials}
```

## 附录 B：当前国赛章节标题清单

| 文件 | 期望标题 |
|---|---|
| `1_restatement.tex` | 问题重述 / 问题背景 / 问题提出 |
| `2_analysis.tex` | 问题分析 / 问题一的分析、问题二的分析、问题三的分析 / 本文主要创新点 |
| `3_assumptions.tex` | 模型假设 |
| `4_symbols.tex` | 符号说明 |
| `5_problem1.tex` | 问题一的模型的建立和求解 / 具体分析 / 模型准备 / 模型建立 / 模型求解（结果分析可选） |
| `5_problem2.tex` | 问题二的模型的建立和求解 / 具体分析 / 模型准备 / 模型建立 / 模型求解（结果分析可选） |
| `5_problem3.tex` | 问题三的模型的建立和求解 / 具体分析 / 模型准备 / 模型建立 / 模型求解 / 结果分析（可选） |
| `6_check.tex` | 模型检验与分析 / 误差分析 / 灵敏度分析 |
| `7_evaluation.tex` | 模型的评价与推广 / 模型的优点 / 模型的缺点 / 模型的改进与推广 |
| `A1_materials.tex` | 无 `\section`；由 `\appendixAcn` 发出“附录”，表题为“表 N 支撑材料文件清单” |

## 附录 C：独立附录工程

| 文件 | 说明 |
|---|---|
| `paper_appendix/main.tex` | 独立编译；`\setcounter{equation}{N}`（N=正文公式总数） |
| `paper_appendix/sections/A_appendix.tex` | 附录正文；小节用 `\subsection*{A.1\quad ...}`；图用 `\appfigure`，图号“图 A1：”是文字 |
| 交付名 | `附录A.pdf` |

> `materials_list`（正文末页清单表）与 `appendix_pdf`（独立 `附录A.pdf`）是两件事：
> 前者在正文 PDF 的最后一页，后者是另一个 PDF；角色表里分开建模，避免再次混用“附录”一词。
