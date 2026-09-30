# 内部泄漏词表（15Verification 复扫最终 pdf 用）

15Verification 把提交/归档用的最终那份 pdf `pdftotext` 成纯文本，扫下方【内部词 deny】，
命中即硬错误，去对应页改写；本表是工作流自维护词表，遇到新的内部代号先加进来。
对照【题内合法词 allow】避免误伤题目/模型自带的编号。只扫最终 pdf，不扫中间构建——
若 tex 干净而 pdf 有残留，说明 pdf 是旧构建，先重编译再判。

## 内部词（deny：出现即疑点，逐一判定；命中多数判硬错误）

- 阶段/流程代号：`9Paper-writing 6Robustness 5Result-credibility-audit 15Verification 5coding 7Route-diagram 10Math-proof-gate 10cross 3analysis 3Modeling-review-gate 2literature 12Rubric-final 13Repair-by-rubric-verdict`、
  门禁 token `REVISE APPROVED NEEDS_FIX REVISE_HARD REVISE_SOFT`、内部文件名 `RESULT_AUDIT_REPORT REVIEW_REPORT MODELING_REVIEW_REPORT VERIFY_REPORT RUBRIC_REVIEW FIX_REPORT`、
  流水线词 `harness 门禁 回执 降级放行 SUBMIT`（对照 9Paper-writing 词表，凡软件工程/harness 语义均禁）。
- 内部用例/校验标签（字母+数字 内部 QA 代号）：`C16 A5/H7 C4/C5 N3` 及同类（新增时续）。
- 内部版本/口径串：`v1.1.1 M-2 口径 R2-2 C-2 口径 v1.0 主口径`（口径仅在"统计口径"学术语境可留）。
- 内部路径/文件名残留：`code/outputs …/result_*.json RESULTS §x`（正文不得出现内部路径）。
- 字面 LaTeX 泄漏（与 15Verification Step4 同源）：`arraybackslash \hline 裸 &`。

## 题内合法词（allow：题目/模型自带编号，不算泄漏，复扫时跳过）

- 无人机：`FY1…FY5`；导弹：`M1 M2 M3`；题目：`Q1…Q5 问题一…五`；官方结果表：`result1 result2 result3`。
- 模型量/判据：`C_cyl F4 OD rim 闭段 严格中间 D_m f5` 及 `D_M1…D_M3`（逐导弹遮蔽时长，合法）。
- 通用英文：`RESULTS` 若属正常英文句义（"results are in §5"）需人看上下文，不加词表误伤。
- 若某题模型自带其它 字母+数字 量名（如算例编号 Case 1…、组件 H7 是题目实体），写该题时先把它们移入本 allow 区，再跑复扫。
