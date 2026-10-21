# Recipe 目录：先看数据契约，再看图型

> 图型不是菜单。先回答“这组数据是什么形状、独立单位是什么、读者要回答什么问题”，再从表里选。
> 每张主图至少写 3 个**不同视觉编码**的候选（不是 3 个配色）；不适合就降级并说明。
> 机器可读版本：`assets/recipes.json`。标 `external` 的 recipe 需要按本文件适配外部模板，不能假装已内置。

## 0. 快速路由

| 数据形状 | 先想 | 再想 | 不要 |
|---|---|---|---|
| 网格 `x × y → z` | `contour-field` / `matrix-heatmap` | `surface3d-response` + 投影 | 只用几条折线代替场 |
| 长表 `series × x → y` | `trend-line` | `small-multiples` / `parameter-sweep` | 无序类别连线 |
| 配对 `subject × before/after` | `paired-raincloud` / `paired-dumbbell` | 变化量分布 | 两组独立柱 |
| 类别 × 估计 + 区间 | `horizontal-dot-interval` | `forest-plot` | 只有均值、没有区间 |
| 类别 × 序列 | `grouped-bars` | `stacked-composition` | 总和没意义时堆叠 |
| 多变量 | `correlation-heatmap` / `correlation-pairgrid` | `scatter_matrix` | 变量 >12 硬塞 |
| 观测 × 预测 | `prediction-diagnostics` | `marginal-joint-scatter` | 只画拟合线 |
| 二分类标签 × 分数 | `roc-curve-ci` | PR / 校准 | AUC≈1 还当卖点 |
| 模型 × (相关, 标准差) | `taylor-diagram` | `horizontal-dot-interval` | 只比相关系数 |
| 方法 × 维度 | `radar` | `grouped-bars` | 维度 >8 |
| 来源 × 去向 | `chord-diagram` | 邻接矩阵 | 连接稀疏硬画和弦 |
| 机理/几何 | `cylinder_schematic` / `paper-diagram` | 2D 剖切 | 纯数据题硬画示意 |
| 物理立体/内部结构 | `7Route-diagram` 的 `physical3d`（Route A 透明线框 / B 实心剖切） | 2D 剖切或投影 | 每个同构问各画一张；用 `schematic.scene3d` 硬画实心剖切 |

## 1. 场与矩阵

| id | 数据契约 | 什么时候用 | 避免 | 退路 |
|---|---|---|---|---|
| `contour-field` | `x, y, z`，`z.shape=(len(y),len(x))`；可选阈值层 | 场里有阈值、前沿、相界、分区 | 稀疏散点、无规则网格 | `matrix-heatmap` |
| `matrix-heatmap` | `row × column × value`；可选格内文字 | 逐格读数、离散矩阵、表格热图 | 行列 >24 不分面；连续场有明确前沿 | `contour-field` / `faceted-heatmap` |
| `correlation-heatmap` | 方阵 `variable × variable × r`，`r∈[-1,1]` | 多变量两两相关；下三角 | 样本小、相关不稳；变量 >12 | `correlation-pairgrid` |
| `signed-error-heatmap` | `row × column × signed error` | 正负误差、偏差方向；以 0 为中心 | 误差量单向、零值该退底 | `matrix-heatmap` |
| `faceted-heatmap` | `facet × row × column × value` | 行数 >24 或多个同构矩阵 | 分面太多、每格太小 | `matrix-heatmap` |
| `correlation-pairgrid` | 宽表：观测 × 3–8 个连续变量 | 联合结构、非线性、离群 | 变量 >8；样本巨大 | `correlation-heatmap` |
| `split-violin-corr-matrix` | 相关矩阵 + `feature × group × value` | 相关 + 组间分布同屏 | 组别 >3、样本小 | `correlation-heatmap` |
| `circular-heatmap` | `item × trait × value` 极坐标 | 条目有周期/分组含义 | 普通无序列表 | `matrix-heatmap` |
| `response-surface-2d` | `p1 × p2 × response`，坐标递增 | 两参数响应面、最优区 | 参数是类别、无顺序 | `contour-field` |
| `dotplot-matrix` | `row × column × size × color` | 两个编码维度（比例 + 强度） | 两个编码语义重复 | `matrix-heatmap` |

## 2. 趋势、扫描、收敛

| id | 数据契约 | 什么时候用 | 避免 | 退路 |
|---|---|---|---|---|
| `trend-line` | 长表 `series, x, y`；同 series 内 x 严格递增；可选 low/high | 时间序列、迭代、随参数变化 | 无序 x；只有 2–3 个点；>6 条不直接标注 | `horizontal-dot-interval` / `small-multiples` |
| `parameter-sweep` | `parameter × metric × series`，3–8 个检查点 | 超参数、阈值、规模扫描；拐点/饱和 | 参数类别型；检查点 <3；多量纲共用 y 轴 | `trend-line` / `grouped-bars` |
| `optimization-convergence` | `iteration × objective × method`，可选 best-so-far | 梯度/启发式/TPE 收敛 | 只有最终值；预算不同不说明 | `grouped-bars` |
| `decomposition-stl` | `time × observed × trend × seasonal × residual`（后三列已算好） | 趋势/周期/残差分解 | 序列短于两个周期；方法未说明 | `trend-line` / `wavelet-scalogram` |
| `wavelet-scalogram` | `time × scale × power`（已算好） | 非平稳周期、突变、间歇 | 序列太短；把未检验功率当结论 | `decomposition-stl` / `trend-line` |
| `trajectory-2d` | `trajectory_id × time × x × y`，可选 group | 相平面、状态空间、优化轨迹 | >20 条不聚合；无时间顺序 | `trend-line` 双面板 / hexbin |

## 3. 分布、配对、区间

| id | 数据契约 | 什么时候用 | 避免 | 退路 |
|---|---|---|---|---|
| `histogram-distribution` | `group × observation`，保留全部观测 | 看形状（双峰/偏尾/离群）；1–3 组 | 组 >3；n<20；只关心中位数 | `boxplot` / `ecdf` |
| `boxplot` | `group × observation`，可选 log y | 多组分布、四分位、离群 | n<5；双峰是重点 | `histogram-distribution` / `distribution-strip` |
| `ecdf` | `group × observation` | 直接读“小于某值的比例” | 只需均值/中位数 | `boxplot` |
| `paired-raincloud` | `subject_id × condition(2–3) × group × value` | 同一对象前后测；原始点+分布+效应 | 只有汇总均值；没有配对 ID | `paired-dumbbell` |
| `paired-dumbbell` | `pair_id × condition(恰好2) × value` | 小样本配对；每对都要看见 | 样本大、分布形状是重点 | `paired-raincloud` |
| `ridgeline` | `group × observation`（有序组） | 多组分布沿有序维度堆叠 | 组序无意义；组 >8 | `boxplot` / `small-multiples` |
| `distribution-composite` | `group × metric × observation` + 组成 | 一张图同时看分布与构成 | 面板只是重复同一证据 | `boxplot` + `stacked-composition` |
| `horizontal-dot-interval` | `category × estimate × low × high` | 十几个方法/情景的均值与区间 | 区间定义未说明；类别 <5；上下界不包含中心 | `grouped-bars` / `boxplot` |
| `forest-plot` | `category × estimate × low × high × reference` | 效应量、比值、差值；有零线 | 区间不是从数据算的 | `horizontal-dot-interval` |
| `sensitivity-tornado` | `parameter × low_case × high_case × baseline` | 单因素敏感性排序 | 参数强相关；阈值/非单调 | `parameter-sweep` / `grouped-bars` |

## 4. 比较、组成、消融

| id | 数据契约 | 什么时候用 | 避免 | 退路 |
|---|---|---|---|---|
| `grouped-bars` | `category × series × value`，可选 low/high | 2–12 类 × 2–5 序列；直接读数 | >5 序列或 >12 类；跨数量级 | `horizontal-dot-interval` / `matrix-heatmap` |
| `multi-metric-bar-panel` | `method × metric × value` | 3–4 指标 × 5–12 方法；分面板 | 指标 >4；方法名太长 | `grouped-bars` / `horizontal-dot-interval` |
| `ablation-bars` | `variant × component_set × metric × value` | 消融/剥离；基线虚线 | 组件强交互不说明；变体 >8 | `grouped-bars` / `waterfall-contribution` |
| `log-scale-bars` | `method × value`，跨 ≥2 个数量级 | 时间、吞吐、误差跨量级 | 含 0/负数；同量级 | `horizontal-dot-interval` |
| `stacked-composition` | `category × component × value`，总和有意义 | 构成/占比随类别/时间变化 | 组件 >7；需精确比较中间层 | `grouped-bars` / 绝对值堆叠+总量线 |
| `waterfall-contribution` | `step × delta`，可选 start/end | 从基线到最终值的增量分解 | >12 步；delta 不可加 | `stacked-composition` / `ablation-bars` |

## 5. 诊断、分类、模型比较

| id | 数据契约 | 什么时候用 | 避免 | 退路 |
|---|---|---|---|---|
| `prediction-diagnostics` | `observed × predicted`，残差由两者推出 | 预测-观测一致性、残差 | 没有真实观测 | `marginal-joint-scatter` |
| `marginal-joint-scatter` | `x × y`，可选 group | 联合结构 + 边缘分布 | 点太密不 hexbin/密度 | `prediction-diagnostics` |
| `roc-curve-ci` | `fpr × tpr × model × fold` | 真实二分类；各折插值后均值+波动带 | 任务几乎完美可分；没有真实标签 | `prediction-diagnostics` |
| `volcano-plot` | `feature × effect_size × adjusted_p` | 高维差异特征 | 未做多重比较校正 | `horizontal-dot-interval` |
| `shap-combo` | `sample × feature × shap_value × feature_value × class` | 真实加性解释 | 把回归系数冒充 SHAP；类别不平衡未处理 | `ablation-bars` |
| `taylor-diagram` | `model × correlation × std × reference_std` | 多模型形状+幅度同时比较 | 只有两个模型；不可比 | `horizontal-dot-interval` |
| `radar` | `method × dimension × value` + 归一化范围 | 3–8 维指纹；少量方法 | 维度 >8；量纲不可比 | `grouped-bars` / `matrix-heatmap` |
| `chord-diagram` | `source × target × weight` | 来源-去向流量/连接 | 连接稀疏；用矩阵更清楚 | `matrix-heatmap` |
| `multipanel-grid` | panel spec 列表：id/type/source/宽高比 | 多面板总装；共享图例 | 面板无叙事关系 | `hero-evidence` |

## 6. 3D 与示意

| id | 数据契约 | 什么时候用 | 避免 | 退路 |
|---|---|---|---|---|
| `surface3d-response` | `x × y × z`，可选阈值层 | 第三维真有变量（响应面、参数地形、流形） | 只是把二维场硬抬三维；视角遮挡 | `contour-field` + 投影 |
| `tuning-surface-3d` | `trial × p1 × p2 × objective`，曲面由试验点插值/平滑 | 调参试验点 + 响应面；标最优点 | 试验点太少；插值外推 | `response-surface-2d` |
| `cylinder_schematic` | 几何 + 径向场 + 标注 | 圆柱/圆盘/多层介质；几何与场同屏 | 纯数据题；没有几何对象 | `schematic-generic` |
| `schematic-generic` | `entities × relations` | 流程、结构、边界条件、变量关系 | 一张数据图能说清 | `cylinder-schematic`（数值示意）或交回 `paper-diagram`（draw.io） |
| `hero-evidence` | 1 hero + 2–4 evidence panels | 主结果 + 支撑证据 | 面板重复同一证据 | `quantitative-grid` |
| `quantitative-grid` | 等权面板 | 多个同等重要指标/条件 | 有明显主结果 | `hero-evidence` |
| `plate` | 机理 + 结果 + 背景 | 竞赛“一张大图讲完整故事” | 面板无叙事关系、纯拼贴 | `hero-evidence` |
| `diagnostic-strip` | 主图 + 残差/误差条带 | 预测图要交代误差和偏差 | 没有独立误差数据 | `prediction-diagnostics` |

## 7. 数据图型库 11 个模板的落点

| 数据图型库模板 | 本目录 recipe | 备注 |
|---|---|---|
| 多分类 SHAP 柱状+蜂群 | `shap-combo` | 必须是真 SHAP 或明确加性分解；不要把回归系数冒充 |
| 配对云雨 | `paired-raincloud` | 有配对 ID；没有就改 `paired-dumbbell` |
| 交叉验证 ROC+CI | `roc-curve-ci` | 真实标签；AUC≈1 时改预测诊断 |
| Taylor | `taylor-diagram` | 本 skill 用笛卡尔四分之一圆，避免极坐标刻度打架 |
| 相关矩阵组合 | `correlation-pairgrid` | 变量 3–8 |
| 预测—真实边缘分布 | `marginal-joint-scatter` | 大样本 hexbin |
| RF/TPE 3D 曲面 | `tuning-surface-3d` / `surface3d-response` | 平滑曲面，不画瀑布 |
| 下三角相关+半边小提琴 | `split-violin-corr-matrix` | 组别 ≤3 |
| 分组环形热图 | `circular-heatmap` | 类别有周期/分组含义才用 |
| 城市公园降温组合 | `distribution-composite` | 堆叠+云雨+箱线，注意总和无意义时别堆叠 |
| Nature 和弦 | `chord-diagram` | 连接稀疏改矩阵 |

## 8. 比较与拼版的落点

| 比较与拼版图型 | 本目录 recipe |
|---|---|
| 分组柱 / 多指标柱 | `grouped-bars` / `multi-metric-bar-panel` |
| 消融条 | `ablation-bars` |
| 组成分解 / 堆叠 | `stacked-composition` |
| 正确率/分类分解 | `grouped-bars` + `matrix-heatmap` |
| 趋势 / 事件时间线 | `trend-line` / `timeline` |
| 优化热图 / 双热图 | `signed-error-heatmap` / `matrix-heatmap` |
| 速度/扫描 | `log-scale-bars` / `parameter-sweep` |
| 雷达 | `radar` |
| 3D 流形 / 带灰块曲面 | `surface3d-response`（数据没有多井结构就老实说） |
| 轨迹 / 相图 | `trajectory-2d` |
| 预测诊断 | `prediction-diagnostics` |
| 综合拼版 | `plate` / `hero-evidence` |

## 9. 投稿契约与质控的落点

| 投稿契约模板 | 本目录 recipe |
|---|---|
| paired | `paired-raincloud` / `paired-dumbbell` |
| marginal | `marginal-joint-scatter` |
| dotplot | `horizontal-dot-interval` |
| ROC | `roc-curve-ci` |
| volcano | `volcano-plot` |
| quantitative grid | `quantitative-grid` |
| schematic-led composite | `schematic-generic` / `cylinder_schematic` |
| image plate + quant | 本 skill 不处理显微/图像板；走对应领域工具 |
| asymmetric mixed-modality | `hero-evidence` / `plate` |

## 10. 选择纪律

1. **先看独立单位**：每条曲线是一个时间点、一个对象、一个 seed，还是一组重复？没有独立单位就不要画 CI/检验。
2. **先看配对**：同一对象前后测、同一任务多方法，优先配对差；不要用两条边缘分布代替。
3. **先看总和是否有意义**：组成图只在“部分相加=整体”时用。
4. **先看第三维是否真有变量**：没有就 2D；有就 3D + 投影。
5. **先看读者要回答什么**：排序/区间/形状/结构/机制，各自对应不同图型。
6. **复杂图不自动加分**：真实时间序列用折线完全合理；不要为图型数量牺牲可读性。
