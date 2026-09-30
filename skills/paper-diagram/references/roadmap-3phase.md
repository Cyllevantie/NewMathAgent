# 模板 roadmap-3phase · 三阶段问题驱动技术路线图

竖版三阶段骨架：主栏＝数据与指标 → 两组建模预测 → 情景路径规划，右栏＝三个研究问题导轨。第二、三阶段用圆角点划线容器区分，适合建模论文、课题申请和答辩中的“问题—模型—决策”技术路线。

渲染：`python3 scripts/roadmap_3phase.py content.json -o out.drawio`。默认输出灰白论文版；显式加 `--theme color` 才使用浅绿注释块与淡紫阶段箭头；`--check` 只做结构与容量校验。

- [一、语义约定](#一语义约定)
- [二、JSON 字段](#二json-字段)
- [三、数量边界](#三数量边界)
- [四、字数预算](#四字数预算)
- [五、已知近似](#五已知近似)

## 一、语义约定

- `questions` 固定三项，分别对应三个阶段。右侧上下虚线都朝问题框收敛，表示该阶段的工作共同回答该问题，而不是阶段之间的因果箭头。
- 阶段一的 `prep.center` 是主预处理节点，向 `prep.left` / `prep.right` 分发；`indicator.method` 是点线注入的方法依据，`indicator.dimensions` 是指标体系的并列维度。
- `branches` 是从 `analysis` 同时分发的并行任务，随后共同汇入 `relation`。不要把前后顺序的步骤放进 `branches`。
- 阶段二固定左右两个 `groups`。每组的 `models` 并列运行，模型结果只在组内汇入 `fusion`，再形成该组 `output`；两组输出只在阶段末汇流，不互相替代。
- 阶段三的 `scenarios` 点线注入情景设定，`parameters` 点线注入组合模型；`outcomes` 是同一预测结果的并列决策指标，最后共同汇入 `final`。
- 实线箭头表示处理/推导顺序，点线箭头表示外部方法、情景或参数注入，粗箭头表示阶段切换。三种语义不可混用。

## 二、JSON 字段

```jsonc
{
  "questions": ["问题一", "问题二", "问题三"],
  "phase1": {
    "data": "基础数据",
    "prep": {"left": "侧处理一", "center": "主预处理", "right": "侧处理二"},
    "indicator": {
      "method": "指标方法",
      "center": "指标体系构建",
      "dimensions": [["维度一", "维度二"], ["维度三", "维度四"]]
    },
    "analysis": "现状分析",
    "branches": ["并行任务一", "并行任务二", "并行任务三"],
    "relation_method": "关系方法",
    "relation": "关系分析"
  },
  "phase2": {
    "groups": [
      {"models": [{"name": "模型一", "result": "结果一"}, {"name": "模型二", "result": "结果二"}],
       "fusion": "组内融合", "output": "组输出"},
      {"models": [{"name": "模型三", "result": "结果三"}, {"name": "模型四", "result": "结果四"}],
       "fusion": "组内融合", "output": "组输出"}
    ]
  },
  "phase3": {
    "scenario_label": "情景类型",
    "scenarios": ["情景一", "情景二"],
    "stage": "情景设定",
    "model": "组合模型",
    "forecast": "情景预测",
    "parameters": ["参数一", "参数二", "参数三"],
    "outcomes": ["结果一", "结果二"],
    "final": "最终路径"
  }
}
```

完整的挖空占位示例见 `assets/roadmap-3phase/example.json`：按其他内置模板的约定，用 `____`、`①②③` 与 `A/B/C` 标示待替换槽位，不预填某个领域的研究结论。

## 三、数量边界

| 字段 | 允许数量 | 版式含义 |
|---|---:|---|
| `questions` | 固定 3 | 三阶段各一个问题 |
| `phase1.indicator.dimensions` | 2–3 行 × 2–3 列，且每行等列 | 并列指标维度 |
| `phase1.branches` | 3–5 | 同时分发、共同汇流 |
| `phase2.groups` | 固定 2 | 左右两个模型融合组 |
| 每组 `models` | 2–3 | 组内并行模型 |
| `phase3.scenarios` | 2–4 | 情景注释行 |
| `phase3.parameters` | 3–6 | 参数注释行 |
| `phase3.outcomes` | 2–3 | 并列决策结果 |

脚本在写文件前拦截所有越界数量；数量取上限时槽位会自动等分变窄。

## 四、字数预算

统一字号 16 px，行高 19 px；下表按最窄允许配置给出保守预算。拉丁字母约占半个汉字宽，实际以 `--check` 报告为准。

| 槽位 | 几何 | 保守预算 |
|---|---:|---|
| `phase1.data` | 420×42 | 每行 ≤25 汉字，≤2 行 |
| `prep.left/right` | 200×42 | 每行 ≤12 汉字，≤2 行 |
| `prep.center` / `indicator.center` / `analysis` | 220×42 | 每行 ≤13 汉字，≤2 行 |
| `indicator.method` | 205×66 | 每行 ≤12 汉字，≤3 行 |
| `indicator.dimensions[][]` | 3 列时 80×24 | 单行 ≤4 汉字 |
| `branches[]` | 5 项时约 145×42 | 每行 ≤8 汉字，≤2 行 |
| `relation_method` | 205×58 | 每行 ≤12 汉字，≤3 行 |
| `relation` | 220×46 | 每行 ≤13 汉字，≤2 行 |
| `questions[]` | 78×48 | 每行 ≤4 汉字，≤2 行 |
| `models[].name/result` | 每组 3 项时约 116×42/38 | 每行约 ≤6 汉字，≤2 行 |
| `fusion` | 240×42 | 每行 ≤14 汉字，≤2 行 |
| `output` | 200×40 | 每行 ≤12 汉字，≤2 行 |
| `scenario_label` / `scenarios[]` | 合计 155×96 | 每行 ≤9 汉字，合计 ≤5 行 |
| `stage` | 300×44 | 每行 ≤18 汉字，≤2 行 |
| `parameters[]` | 合计 160×126 | 每行 ≤9 汉字，合计 ≤6 行 |
| `model` | 340×48 | 每行 ≤20 汉字，≤2 行 |
| `forecast` | 260×42 | 每行 ≤15 汉字，≤2 行 |
| `outcomes[]` | 3 项时约 227×48 | 每行 ≤13 汉字，≤2 行 |
| `final` | 460×38 | 单行 ≤28 汉字，≤2 行（建议单行） |

## 五、已知近似

- 参考图中的自由曲线点线箭头改为正交点线，便于 draw.io 后续编辑并减少重路由漂移。
- 不复制论文图号、章节正文、水印、截图轮播控件及扫描噪声。
- 默认灰白主题是本模板的正式输出；彩色主题只保留参考图中低饱和浅绿和淡紫的提示关系。
