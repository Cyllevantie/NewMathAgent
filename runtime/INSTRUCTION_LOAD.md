# 指令负载对照表（减负前后）

> **本表是减负效果的对照记录**，不是当前口径。此后新增了 `9format` 阶段（其必读为模板层
> `paper/_base/*.tex` 的注释 + `docs/PUBLICATION.md` + `docs/VISUALIZATION.md`）。
> **当前权威**见 `CLAUDE.md` 的「阶段读取表（唯一权威）」。

目的：证明"减负"减的是**重复与噪音**，不是**要求**。每阶段的拦截要求仍在（norms / docs / 门禁 ID 各有一处唯一权威），
只是不再让每个 headless agent 一开场就背 3–6 份 docs。

## 每阶段必读 docs 数

| 阶段 | 改前 | 改后 | 改后读什么 |
|---|---|---|---|
| 2literature | 0 | 0 | —（norms 按需） |
| 3analysis | 3 | 1 | CONTENT_QUALITY（题意契约；另需写 TASK_CONTRACT.json） |
| 4review | 1 | 1 | CONTENT_QUALITY |
| 5coding | 3 | 1 | RESULT_CONTRACT（CLI 报错即规范） |
| 6robustness | 3 | 1 | RESULT_CONTRACT（CLI） |
| 7result-audit | 3 | 2 | CONTENT_QUALITY + RESULT_CONTRACT（CLI） |
| 8drawio | 4 | 2 | VISUALIZATION + GEOMETRY |
| 9writing | 5 | 2 | PUBLICATION + VISUALIZATION |
| 9mathproof | 1 | 1 | CONTENT_QUALITY |
| 10cross | 1 | 1 | CONTENT_QUALITY |
| 11verity | 6 | 2–3 | PUBLICATION + VISUALIZATION（CONTENT_QUALITY 按需） |

合计：**28 → 14**（每阶段平均 2.5 → 1.3）。权威读取表在 `CLAUDE.md`「阶段读取表（唯一权威）」。

## 行数

| 文件 | 改前 | 改后 |
|---|---|---|
| skills/9writing | 490 | 341 |
| skills/11verity | 297 | 292 |
| skills/4review-model | 121 | 116 |
| skills/9mathproof | 114 | 109 |
| skills/10cross-review | 66 | 62 |
| skills/7result-audit | 70 | 65 |
| docs/ 文档数 | 14 | 9（5 份零引用归档到 `runtime/docs_archive_20260908/`） |

## 去重（唯一权威）

- v2 裁决侧车规格：只在 `docs/CONTENT_QUALITY.md`（5 份门禁 skill 各留 1 行指针）。
- RESULT_CONTRACT：改成各阶段 CLI 命令，报错信息即规范。
- 摘要/关键词/灵敏度、假设节纪律、证明-措辞契约：唯一权威在 `skills/_references/math_modeling_norms.md`，skill 只留检查点+指针。
- 模板章节枚举：改为"以模板 `main.tex` 的 `\input{}` 为准"+ 两个示例。

## 拦截力未降的证据

`regression/test_defect_fixtures.py` 把 2024C 的四条真缺陷写成离线夹具（随机过程连乘、覆盖弱化、未证最优背书、求解不足当风险机制），
**A–D 全过**；E（前向路由不再 brick）为新增行为。
