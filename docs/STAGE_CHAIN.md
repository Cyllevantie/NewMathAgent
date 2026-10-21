# 阶段链（编号 ↔ skill ↔ 产出）

> 这份文件是「账本」，不是「操作手册」 —— 它只登记阶段编号与产物。
> 每个阶段该读哪些 docs 见 `CLAUDE.md` 的「阶段读取表」；编排的权威顺序是
> `lib/web/server.py` 的 `STAGES`（前端 `lib/web/static/index.html` 的 `STAGE_ORDER`/`STAGE_NAME`/
> `STAGE_GATE` 是第二事实来源，由 `lib/web/healthcheck.py` 自动对账）。

为什么这张表不在 `CLAUDE.md`/`AGENTS.md` 里：
`CLAUDE.md` 与 `AGENTS.md` 的全文哈希是各阶段「做法要求」指纹的一部分
（`lib/web/server.py:_input_split` 的 `ins` 列表）。加一个阶段、改一次编号就会把
每一个阶段标成 `done(stale-instr)`（面板顶部一条黄条 + 阶段上的提示）——
这些标记对"文献定向怎么读题""编码怎么算"毫无信息量，纯属噪音。
账本放在被哈希的文件之外，改链就不产生 stale 标记；真改 SKILL/规范才照旧触发。
（`docs/` 下的文件只有被 `_input_split` 点名的才进指纹，本文件不在其中。）

| # | Skill | 作用 | 产出 |
|---|---|---|---|
| ⓪ | 0Intake-readproblem | 读题：把上传的整个文件夹读一遍（题面+附件+数据），产出"我读到了什么"，**跑完停下等人确认**（确认页＝左内嵌原 PDF / 右渲染后的题面／可改＋更正说明） | INTAKE_REPORT.md / INTAKE.json |
| 0 | 0Start-mathmodel | 问偏好→plan/todo（链外入口，不在 `STAGES` 里） | plan.md / todo.md |
| 1 | 1Literature-orientation | 文献定向+机理基线（WebSearch） | LITERATURE_DIRECTION.md |
| 2 | 2Modeling-design | 赛题分析+建模设计（三要素+代码契约+创新台账） | ANALYSIS_MODELING_REPORT.md, INNOVATION_LEDGER.json |
| 3 | 3Modeling-review-gate | 建模评审门禁（数学/题意/机理/数据设计/创新，独立子 agent 五查） | MODELING_REVIEW_REPORT.md |
| 4 | 4Coding-and-computation | 实现/计算/图/溯源 + 创新 baseline/intervention 复算 | code/, RESULTS_REPORT.md, INNOVATION_LEDGER.json（measurement） |
| 5 | 5Result-credibility-audit | 数据与结果可信度审计（防小样本高 AUC/泄漏/口径 + 创新增量复核） | RESULT_AUDIT_REPORT.md, INNOVATION_AUDIT.json |
| 6 | 6Robustness | 稳健性/敏感性（扰动/boot/留组/口径 + 核心创新稳健性） | ROBUSTNESS_REPORT.md, INNOVATION_LEDGER.json（robustness） |
| 7 | 7Route-diagram | 技术路线图（**必出图 1 分析流程图**）+ 按需示意图（含第五类 3D 物理立体/剖切，`fig_geometry_3d`） | DRAWIO_REPORT.md |
| 8 | 8Figure-gate | 绘图门禁（⑦ 之后图就全了 —— 机械地板 `visualization audit` + 查机器看不见的选型/可读性；**只判不改**，FAIL→回 7） | FIGURE_REVIEW_REPORT.md |
| 9 | 9Paper-writing | 按角色计划（`roles.json` + `paper/structure.json`）分节撰写论文（模板+图与排版风格参考）+ 收尾交付层（提交清单/末页清单表/运行说明/AI工具使用详情） | paper/（含 paper-structure.tex / structure.json）、SUBMISSION_MANIFEST.json、运行说明.md、AI工具使用详情.pdf |
| 10 | 10Math-proof-gate | 数学论证门禁（成稿定理/命题/证明字样须带等式级推导+前提声明；禁仿真代证明；REVISE→回 9） | MATH_PROOF_REPORT.md |
| 11 | 11Cross-question-check | 跨问一致性审查 | CROSS_QUESTION_REVIEW.md |
| 12 | 12Rubric-final | 评分标终审（四份评委视角评分标逐项打分；先证伪再报；轻微项只给成本估计不返修） | RUBRIC_REVIEW.md |
| 13 | 13Repair-by-rubric-verdict | 按评分判词论文侧定点返修（措辞/摘要/结论表述；不属实的记 not_reproduced 不改稿） | FIX_REPORT.md |
| 14 | 14Layout-and-format | 排版与版式验收（独占 `paper/_base/` 导言区；行距/页边距/篇幅/编译/逐页视觉；对账修补 ⑨ 首产的提交清单与末页清单表） | paper/ 版式 + FORMAT_REPORT.md |
| 15 | 15Verification | 验收（结构/图表/数值/编译/数学论证措辞-内容扫描） | VERIFY_REPORT.md |
| 16 | 16Web-demo | 交互式 Demo | DEMO_REPORT.md |

## 改链时要同步的地方（漏一处会被体检或单测抓住）

1. `lib/web/server.py` 的 `STAGES` —— 唯一的权威顺序与门禁声明（每个条目都要**显式**写 `gate` 键）。
2. `lib/web/server.py` 的 `ARTIFACTS`（漏了**不会红**：镜像/回退暂存/接管判定都会静默看不见该阶段产物）
   与 `_default_repair_target`（门禁的 `FAIL->x` 必须与它一致，有单测逐项比对）。
3. `lib/web/static/index.html` 的 `STAGE_ORDER` / `STAGE_NAME` / `STAGE_GATE` —— 三个常量（healthcheck 对账）。
4. `lib/web/healthcheck.py` 顶部的 `workflow` 表（漏了直接判红）与 `py_compile` 清单（新增 lib 模块时）。
5. `skills/<新 skill>/SKILL.md`：frontmatter `name` 必须等于目录名、`allowed-tools` 要有、必须引用
   `_references/stage_discipline.md`；`skills/skills.sh.json` 的技能索引也加一条。
6. `regression/test_content_quality.py` 与 `regression/test_defect_fixtures.py` 里各自的 `STAGES` 副本
   （两份现在都有与驱动对账的用例；加阶段漏改会红，别删那两条守卫）。
7. `lib/web/check_verdict.py` 的 `FALLBACK_ORDER`（驱动没在跑时的阶段顺序兜底；
   `regression/test_check_verdict.py` 有一条用例逐项比对它与 `STAGES`）。
8. `regression/test_intake.py::test_adding_intake_renumbered_nothing` 里那份顺序清单
   （它钉的就是"⓪ 只许插在链首、其余一字不动"）。
9. 条件语义表（**按新阶段职责决定加不加**，漏了静默）：`lib/web/content_quality.py` 的 `REQUIRED`、
   `lib/web/server.py` 的 `_MANUAL_CHECK_FOR`、`_CONTENT_SIDE_STAGES` / `_CONTENT_JUDGE_STAGES` /
   `_polisher_owners` / `_FIX_HANDOFF_JUDGES`、`lib/delivery/checks.py` 的 `LATE_ITEMS` 与
   `lib/delivery/core.py` 的 `FIXED_SOURCES`。
10. 文档账本（人工）：本文件、`CLAUDE.md` / `AGENTS.md`、`README.md`、
    `skills/0Start-mathmodel/SKILL.md`（顺序表/待办/职责表）、开屏页的「经过 N 个阶段」、
    `lib/web/server.py` 的 `GUARDRAILS`、`docs/CONTENT_QUALITY.md` 阶段责任表、
    `docs/PUBLICATION.md:3`、`skills/_references/internal_leak_words.md`。

指纹与别名：`_input_split` 里新阶段自己的 `skills/<skill>` 目录**自动**进 instructions；共享的
`_references` 与 `lib/*` 依赖要按 `_REFERENCE_USERS` / `_LIB_INSTRUCTION_USERS` **显式**加
（漏了 = 改那些共享文件不会让它标 stale）。`_target_index` / `_resolve_stage_id` 共用**同一张别名表**（`_stage_aliases`：skill 名从
`STAGES` 自动派生，少量历史别名在 `_LEGACY_STAGE_ALIASES` 手维护）；加阶段不用改这两个函数。

## 改目录布局时要同步的地方

阶段 agent 的做事依据就是 skill 里写着的那些命令（`python lib/web/check_skeleton.py`、
`python -m lib.publication check`）—— 这些字符串没有类型检查，漏改一处，
全套单测照样绿（测试自己会把 `lib/web` 加进 `sys.path`），要到那个阶段真跑起来才炸。

⇒ `regression/test_lib_layout.py` 是这件事的哨兵：它扫全部 skill/文档/配置，断言
「点名的路径真的存在」「没人按旧的扁平位置写」「`-m` 调用的包都有 `__main__.py`」，
并自带一条对照组（种一条旧式引用进去，检查器必须红 —— 防它变成恒真的摆设）。
搬动 `lib/` 下的任何东西、或往 skill 里新写一条命令之后，跑它就够了。

### ⓪ 读题的两条地基（改上传/确认前先读）

- **agent 绝不能在阶段内搬文件**：`run_stage` 入口与收尾各取一次 `_source_digest()`
  （= `request/` + `data/` 的内容哈希），不等就判 `unverified` 硬挂。⇒ AI 只提案
  （`reports/INTAKE.json`），搬文件由服务端在链外做（`/api/decision` 的 `confirm`）。
- 确认时的搬运会让下一次 ▶ 触发换题轮转：`_prepare_workspace` 会把 `reports/` 整份
  搬进 `cache/`（`RELS` 见 `lib/web/server.py`）⇒ 读题产物另存一份在 `runtime/quality/intake/`
  （轮转搬不走），intake 短路时幂等恢复；① 还会拿到一条指向那份快照的 seed hint。

> **别给阶段重新编号**：⓪ 是插在链首的读题，①…⑯ 的编号固定。重排编号会牵连全仓
> 上千处引用（`13Repair-by-rubric-verdict` 这类名字本身就是编号）。
