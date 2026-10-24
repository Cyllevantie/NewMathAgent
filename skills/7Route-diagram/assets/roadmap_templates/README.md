# `fig_roadmap` 参考模板

这两张是用户给的**视觉/内容参考**，不是要逐像素复制的成品：

- `flow1.png`：问题路由树（Q1–Q4 分色、方法小框、结果文档、结束胶囊）。**首选**。
- `flow2.png`：四问泳道（并列问题、共享上下母线）。**flow1 装不下或没有真实路由条件时**才用。

生成纪律：

1. 图内数值必须来自**当前题目**的 `ANALYSIS_MODELING_REPORT.md` / `RESULTS_REPORT.md`；
   不得把参考图里的旧数值抄进来。
2. Q1–Q4 的语义色取 `config/visualization.json` 的 `question_palette`，不用参考图像素值。
3. 先按 `flow1` 的“路由树 + Q 分色 + 结果文档”生成；若内容/页面放不下，改用 `flow2` 泳道；
   两者都不适合时才回退到紧凑 route tree，并在 `DRAWIO_REPORT.md` 写清原因。
4. 参考图只用于结构、层级和配色语义；文字、数值、方法名、判据必须逐项对当前报告核实。
5. 生成后跑 `skills/paper-diagram/scripts/check_layout.py`，并打开 PNG 目检；不能用“XML 看起来对”代替目检。
