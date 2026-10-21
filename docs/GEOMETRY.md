# 几何图分支

用于一般数学物理、空间结构与教学示意。7Route-diagram 负责解释性几何图；由计算结果驱动的实际曲面（数值场/响应面）由 4Coding-and-computation 只交数据层（figures/data + spec + lock），仍由 7Route-diagram 渲染并写成品，④ 不写画布。图怎么排（嵌入尺寸、图注格式、浮体位置）归 14Layout-and-format —— 也就是：图画得对不对归 7Route-diagram（category=diagram），图排得好不好归 14Layout-and-format（category=presentation）。两者复用 docs/VISUALIZATION.md 的登记、导出和实际目检流程。

## 选型

先在 FIGURE_PLAN 中列出对象、必要关系、坐标/单位、图中符号、用途和是否按比例。图必须对应已确认的模型关系，而非漂亮但未经核实的猜想。

- 局部角度、截面、尺寸和共面关系：二维等比例矢量图。
- 必须理解空间结构：三维整体图，搭配需要的截面或投影。示意投影注明类型；不能把正交投影当透视关系或遮挡判断。
  **物理/数学相关的内容，三维是"可以且应当"，不是备选**：
  对象本身有三维结构（圆柱/球/多层介质/空间坐标与方位）、或量随两个参数变化（响应面、
  多变量关系、优化地形）时，硬压成二维会把一整层信息丢掉。判据只有"第三维真有变量含义"
  一条 —— 不是"图好看"。配齐三件：视角可读、遮挡交代、**投影有歧义就配一张二维投影/切片**。
  非数据示意图仍守"半栏以内"；流程图/结构图/物理立体图都可以沿用正文图 1
  `fig_roadmap` 的同一套低饱和语义色（灰度可读），不再强制黑白。
- 数值场、响应曲面：复用实际计算网格；轴和色标保留物理单位。
- 流程与模块关系：继续使用 paper-diagram/DrawIO，避免将几何解释改画成文字框图。

## 第五类：物理立体 / 3D 剖切示意图（`fig_geometry_3d`）

三维几何不再只有 `visualization.geometry.orthographic()` 这一条投影工具。
第五类图有专用后端，完整规范（按问判重、四条路线、10 条自检）见
`../skills/7Route-diagram/references/physical-3d.md`。要点：

| 路线 | 适用 | 入口 |
|---|---|---|
| A 透明线框 + 2D 剖切 | 内部径向分层、坐标映射、边界；实体不透明会挡住内部 | `skills/7Route-diagram/assets/physical3d/style3d.py` |
| B 实心剖切 | 实体圆柱/球/多层介质的楔形/半剖；隐藏面、剖面填充 | `skills/7Route-diagram/assets/physical3d/solid3d.py` |
| C 数据场曲面/切片 | 计算结果场 $T(r,t)$ / $C(r,t)$；读 `figures/data`，不重算 | `figure-studio` + `solid3d.surface()` |
| D 交互 3D | 网页 demo，不是论文静态图；交 ⑯ | ⑯ 用 `skills/16Web-demo/assets/scene3d.js` 整段内联实现 |

**画几张**：每个子问题先判“几何是否真的不同”。只差时间窗/参数/输出的两个问合成一张
（同相机、同比例双面板）；所有问共用的方法细节只画一张；不要每个问各画一张同构的 3D 图。

**验收**：`qa_physical3d.py` 查 PDF 矢量/字体/宽度、标签越界/压实体/互相重叠；
Route B 还会写 `*.scene.json`（投影、相机、面片数、标签 bbox）。`docs/GEOMETRY.md`
原有验收条目（坐标、端点、截面、标签、透明面混色）继续适用。

## 公共工具

`visualization.geometry` 提供：

- orthographic(points, azimuth=30, elevation=20)：Nx3 坐标到二维视平面，返回投影坐标；不计算遮挡或物理判据。
- angle_marker(ax, vertex, ray1, ray2, radius=..., label=...)：给定三点标注较小夹角，拒绝退化射线。
- sphere_section(fig, radius=..., height=...)：普通球体与水平截圆的空间图/子午截面组合，检查半径及截面合法性。这个例子用于布局复用，不规定每道题画球。

三维物理立体图的成图工具在 `skills/7Route-diagram/assets/physical3d/`：

- `style3d.py`：Route A，Matplotlib 3D 透明线框/2D 剖切；`annotate3d` 把标签固定在屏幕偏移并画引线。
- `solid3d.py`：Route B，自写矢量投影 + 深度排序的实心剖切；剖面填充/剖面线、标签自动避让/QA 记录。
- `qa_physical3d.py`：PDF 矢量/字体/宽度、标签越界/压实体/重叠检查。
- `templates/`：四份可改的设计样例（共用模型、实心剖切、收缩材料坐标、最坏点事件）。

用 charts.style/canvas 创建画布，几何图保持等比例；自定义节点、连线、对象轮廓后使用 export 导出和登记。三维图使用适合的视角和相同空间轴比例，克制使用透明面，减少网格。重要点、线、角度高对比，辅助线细且弱化；虚线与实线的含义在 caption 交代。复杂几何不强行套球体函数，按已核实坐标构建对应对象。

## 验收

先检查坐标、端点连接、截面/投影一致性、角度和尺寸，再检查标签重叠、线穿文字、透明面混色和缩放可读性。几何计算验证与图像目检分别记录；示意图不能代替数学证明。正文只保留能解释核心模型的图，其余放附录并建立引用。
