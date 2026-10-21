# 第五类非数据图：物理立体 / 3D 剖切示意图（`fig_geometry_3d`）

> 适用：对象本身有三维结构（圆柱、球、多层介质、空间机构、三维轨迹），
> 或第三维真的承载变量（径向分层、厚度、方位、三维场）。
> 不适用：纯数据/统计题硬凑立体图；把“输入→模型→输出”三格画成 3D 方块。
>
> 这一类的目标不是“好看”，而是让读者**少读一段文字**就看懂：对象在哪、
> 内部长什么样、边界条件加在哪、哪一问的几何变了。
>
> 核心纪律：**按问判重**——先判断这一问的几何是否真的与前面不同，再决定
> 画、合并、还是不画；不要每个问都套一张同构的 3D 图。

## 0. 先决定：这一问到底要不要画

数模论文的非数据图不是越多越好。每个子问题先过下面四问：

1. **这一问有独立的几何对象吗？** 没有（纯判定、纯查表、纯统计）⇒ 不画。
2. **它和前面某一问的几何差得多吗？** 只差时间窗/参数/输出，几何同构 ⇒
   **不重复画**；把两问合并成一张（双面板或“共用模型 + 参数标注”）。
3. **它是不是所有问共用的方法细节？** 是（如有限体积控制体、离散格式）⇒
   只画一张小图，不放进每一问。
4. **画出来能讲清一个别处讲不清的关系吗？** 不能 ⇒ 不画，在
   `reports/DRAWIO_REPORT.md` 写一句“本题无独立几何对象/与 Qx 同构，故不画”。

推荐的成图结构（以 2026A 为例）：

| 内容 | 画几张 | 理由 |
|---|---|---|
| Q1 预热段 + Q2 全过程 | **1 张** | 同一圆柱、同一径向模型，只差时间窗；合并成一张共用模型图 |
| Q3 达标事件 | **1 张** | 新增“轴心最坏点 + g(t) 求根”，几何/判据与共用模型不同 |
| Q4 收缩 | **1 张** | 新增动边界 R(t) 与材料坐标 ξ=r/R(t)，几何真的变了 |
| 有限体积控制体 | **可选 1 张小图** | 所有问共用的方法细节；若共用模型图里已能讲清，可不单独画 |

“合并”不是把两张图硬拼：优先**同一相机、同一比例**的双面板；
两个问只差一个参数时，也可以一张图 + 一个参数标注。**不要**每个问都画一张
同构的 3D 图——那会占掉半页版面，读者还看不出差别。

## 1. 四条渲染路线（由 agent 按内容选，不是固定模板）

| 路线 | 什么时候选 | 入口 | 输出 |
|---|---|---|---|
| **A 透明线框 + 2D 剖切** | 要讲内部径向分层、坐标映射、场量位置；实体不透明会挡住内部；想快 | `assets/physical3d/style3d.py` | Matplotlib mplot3d + 2D 面板，矢量 PDF |
| **B 实心剖切** | 对象是实体（圆柱/球/多层），要真的“剖开”看内部；隐藏面和剖面填充重要 | `assets/physical3d/solid3d.py` | 自写矢量投影 + 深度排序，矢量 PDF |
| **C 数据场曲面/切片** | 要画计算结果 T(r,t)/C(r,t)、响应面、三维轨迹 | `figure-studio` + `solid3d.surface()` 或 mplot3d | 数据图管线，必须读 `figures/data` |
| **D 交互 3D** | 网页 demo、答辩演示，不是论文静态图 | 交 ⑯，用 `skills/16Web-demo/assets/scene3d.js` 整段内联 | `demo/demo.html`（由 ⑯ 产出） |

### 1.1 选型判据（按顺序问）

```
是网页交互 / demo 吗？
  是 → Route D（交 ⑯，用 scene3d.js 内联），同时给一张 A/B/C 的静态图进论文
  否 → 有真实三维物理对象吗？
         否 → 2D 几何图（paper-diagram / visualization.geometry），不要硬上 3D
         是 → 是计算结果场吗？
                是 → Route C（读 figures/data，不重算）
                否 → 第三维承载信息吗？
                       否 → 2D 剖切/投影足够
                       是 → 主要讲“内部结构/分层/坐标”？
                              是 → Route A（透明线框）或 B（实心剖切）
                              否，主要讲“实体外形 + 剖开” → Route B
```

Route A 与 Route B 的分界：

- **A**：透明/线框，能看见内部所有层；适合“模型结构 + 坐标 + 边界”。
  代价是遮挡关系弱，不适合强调“实体感”。
- **B**：不透明实体，只露出剖面；适合“真的剖开一个实体”的论文插图。
  代价是内部不可见部分必须靠剖面表达，几何构造要自己想清楚。

同一内容可以两条路线各做一个候选（见 §5 多 agent 面板），主 agent 选一张，
**不要两张都进论文**。

> **实现说明**：本机 Asymptote 3.09 + TeX Live 2026 在标签测量阶段会挂起
> （`asy` 调 latex 的管道问题），因此 Route B 没有依赖 Asymptote，而是用
> `solid3d.py` 自写正交投影 + 逐面深度排序；输出仍是纯矢量 PDF，字体走
> Matplotlib（与论文其他图同一套）。若换到 Asymptote 正常的机器，可以再评估，
> 但不要把“能跑 Asymptote”当成质量前提——现有后端已能过 QA。

## 2. Route A：透明线框 + 2D 剖切

### 2.1 构图

- 左边（或上边）2D 横截面：圆/环 + 等 r 虚线 + 轴心 + 边界箭头 + 半径。
- 右边（或下边）3D 透明圆柱：外轮廓环、少量母线、内部等 r 环、轴心。
- 两个面板**同一轴向比例**；3D 用正交投影，避免透视把“等 r”画成不等。
- 3D 透明面 `alpha` 0.12–0.18；内部线用浅蓝虚线；外轮廓用主色实线。
- 不要给透明面加网格线；线框已经够多。

### 2.2 标签

用 `style3d.annotate3d(ax, p, text, xytext=(dx,dy), ...)`：

- 锚点跟着 3D 点走，文字位置由**屏幕偏移（points）**决定；
- 自动画引线；白描边用“白色底层文字”，不要 `path_effects`（会把字转曲、丢字体）；
- 文字不要压在实体轮廓上；引线不要穿过圆柱体。放不下就换到轴端/外侧。

### 2.3 箭头方向（物理正确性）

- 对流**加热**：热量从环境进入表面 ⇒ 箭头指向表面内部。
- 水分**蒸发**：水分从表面离开 ⇒ 箭头指向外部。
- 收缩：R0 → R(t) 的箭头指向内。
- 通量 q：从内表面指向外表面为正方向；箭头画在圆弧中点，不要画在弦上。

## 3. Route B：实心剖切

### 3.1 剖切方式

- 圆柱：`cut=(angle, start)` 表示从 `start` 度开始切掉 `angle` 度的楔形，
  保留其余部分；自动生成两个径向剖面。
- 半剖：`cut=(180, 0)`；四分之一剖：`cut=(90, 0)`。
- 空心圆柱：`inner>0`，自动生成内壁和环形端面。
- 剖面必须**有填充/剖面线**（`cut_hatch="///"`），否则读者会以为是空壳。
- 剖面内的分层用 `sc.line(...)` 画在切面平面上；不要画完整的 3D 圆环
  （会被实体挡住或穿出来）。

### 3.2 隐藏面与深度

`solid3d` 自己投影 + 按面片深度排序（远→近），不依赖 mplot3d 的 artist 排序。
注意事项：

- 面片数控制在 ~300–3000；超过 3000 先降 `segments`。
- 透明面与不透明面混排时，透明面按同一深度顺序画；不要靠 `zorder` 硬压。
- 内部线框只画在**剖面/端面**上；不要画完整 3D 圆环，否则会穿出实体。
- 轮廓线：外缘环、剖面边界、端面边界；不要给每个面片描边（会出现网格纹）。

### 3.3 尺寸与标注

- 半径用双箭头，沿剖面从轴心到外缘；箭头不要穿过剖面线文字。
- 轴向长度如果只画了截取段，必须在图内或 caption 里写“示意截取 L=25 cm”，
  否则读者会按图量比例。
- 投影类型（正交/透视）写在 caption；`scene.json` 也会记录。

### 3.4 标签布局

- `label(..., auto=False)` 用**手给偏移**，再用 QA 检查 `geometry_hits`；
  自动避让只作为兜底。
- 标签放在实体轮廓外的空白区，或剖面内的空白区；不要压在剖面线上。
- 标签互相重叠是硬缺陷（QA 会报），不是“差不多”。
- 文字用白色底层文字描边，不要白底框——白框会切断几何。

## 4. Route C / D

### 4.1 Route C 数据场

- 只读 `figures/data/*.npz` + `figures/spec/*.json`；不重算、不从
  `code/outputs` 另取一份。
- 三维曲面只用于“第三维是数值”的场；轴和色标保留物理单位。
- 低值区一片死色时先加 `gamma`/PowerNorm，再考虑换切片。
- 数据场图仍走 `figure-studio` 的登记/审计，不走 `solid3d` 的 scene.json。

### 4.2 Route D 交互

- 只在 ⑯ 网页 demo / 答辩演示里用；论文静态图仍用 A/B/C。
- 静态图与交互图用**同一相机/参数**：Route B 的 `*.scene.json` 记录了
  `camera.azim/elev/zoom`，⑯ 可以用它初始化交互相机，保证论文图与网页首帧视角一致。
- ⑯ 读 `skills/16Web-demo/assets/scene3d.js` 整段原文内联进单文件 `demo.html`，不依赖 CDN；
  相机/参数/时间用 hash 深链定格，无头 Edge 截图前先定格再拍。
- 交付检查按引擎整段原文比对；要改引擎就改源文件并重跑 ⑯，不在产物里就地改。

## 5. 多 agent 候选（默认 2–3 个结构候选）

对一张重要的 3D 图，主 agent 先定“要讲什么”，再并行 2–3 个候选：

- C1：Route A 透明线框 + 2D 剖切；
- C2：Route B 实心剖切；
- C3：合并版（两个相近问的双面板 / 共用模型 + 参数标注）。

子 agent 只写 `tmp/figures/<id>/cand_<n>.{py,pdf,png}`，不写 `figures/`；
主 agent 收齐后按“claim 支持 / 信息密度 / 可读性 / 语言 / 是否重复”选一张，
自己重画/合并定稿。登记、导出、QA 只由主 agent 做。

## 6. 字体 / 语言 / 宽度

- 开工先跑 `python skills/figure-studio/scripts/resolve_context.py --write`。
- 中文论文 → 微软雅黑、中文标签、正文 ≥8 pt；英文 → Arial。
- **3D 图的字体和字号必须与其他图完全一致**：不要因为换了 3D 后端就用另一套
  rcParams；`configure_style(font, base_size)` 只设一次。
- 画布按最终印刷宽度定：半栏 ≈80 mm，合并双面板 ≈120 mm；
  不要画 1500 px 屏幕稿再缩。
- 图内不写长解释、不写主标题；标题交 LaTeX caption。

## 7. 后端调用

### 7.1 Route A

```python
import sys
sys.path.insert(0, "skills/7Route-diagram/assets/physical3d")
import style3d as S

S.configure_style("Microsoft YaHei", 8.5)
fig = plt.figure(figsize=(120/25.4, 120/25.4*0.56))
ax = fig.add_axes([...], projection="3d")
S.setup_ax(ax, elev=18, azim=-62, ...)
S.half_cyl(ax, 2.0, 0, 6, 0, 2*np.pi, color=S.FILL_BLUE, alpha=0.15)
S.annotate3d(ax, (0,0,6), "轴心", xytext=(18,12), color=S.AMBER)
S.save_fixed(fig, "fig_geometry_3d", "figures", width_mm=120)
```

### 7.2 Route B

```python
import sys
sys.path.insert(0, "skills/7Route-diagram/assets/physical3d")
import solid3d as S

S.configure_style("Microsoft YaHei", 8.5)
sc = S.Scene(S.Camera(azim=-58, elev=20, zoom=1.10))
sc.cylinder(r=2.0, z0=0, z1=12.5, cut=(70, -35),
            color="#DBEAFE", cut_hatch="///")
sc.label((0,0,12.6), "轴心 $r=0$", offset=(-12,18), ha="right", auto=False)
fig, ax = plt.subplots(figsize=(90/25.4, 90/25.4*1.05))
sc.fit(ax, margin=0.12)
sc.draw(ax, fig)
sc.save(fig, "fig_geometry_3d", "figures", width_mm=90)
```

> 画布宽度必须在 `draw()` 前定死（`figsize=(width_mm/25.4, ...)`）；
> `Scene.save(width_mm=...)` 不会在 draw 之后改 figsize（会直接报错），
> 否则标签偏移会被整体缩放、scene.json 的 bbox 也会失真。

模板（可改，不是固定版式）：

- `assets/physical3d/templates/route_a_wireframe.py`：透明线框 + 2D 横截面
- `assets/physical3d/templates/route_b_cutaway.py`：实心楔形剖切
- `assets/physical3d/templates/route_a_shrinkage.py`：动域/材料坐标双面板
- `assets/physical3d/templates/route_a_event.py`：最坏点 + 事件求根

## 8. 生成后强制自检（10 条）

打开实际 PNG，在最终印刷尺寸看；每条都要量化/复验，不能只写“已检查”。

1. **投影/遮挡**：正交或透视写清楚；多面板共用同一相机与比例；没有
   “正交的图却按透视读”的歧义。
2. **剖面**：剖切面有填充/剖面线/边线；不是空壳；内壁与端面交代清楚。
3. **隐藏面**：内部线不穿出实体；被挡住的部分不画；透明面不混色成脏灰。
4. **标签**：不压文字、不压实体、不穿几何；引线从锚点到文字；白描边不是白底框。
5. **箭头方向**：热流入、水分流出、收缩向内、通量正方向——逐根核对。
6. **字体/语言**：与数据图/路线图同一字体、字号、语言；中文图不夹整句英文。
7. **越界/裁切**：文字完整落在画布内；最小字号 ≥8 pt；不在最终宽度下糊掉。
8. **比例/尺寸**：半径、长度、角度按真实比例；截取段注明；单位齐全。
9. **版面**：半栏 ≈80 mm 或合并双面板 ≈120 mm；没有大片空白；同构问已合并。
10. **不重复**：同一几何不在两问各画一张；一张图只讲一件事；没有解释性长句。

量化工具：`qa_physical3d.py` 会查 PDF 矢量/字体/宽度、标签越界/压实体/互相重叠；
`scene.json` 记录投影、相机、面片数、每个标签的 bbox 与偏移。

```bash
python skills/7Route-diagram/assets/physical3d/qa_physical3d.py \
    --pdf figures/fig_geometry_3d.pdf \
    --png figures/fig_geometry_3d.png \
    --scene figures/fig_geometry_3d.scene.json \
    --width-mm 90 --font "Microsoft YaHei" \
    --report reports/FIG_GEOMETRY_3D_QA.json
```

## 9. 常见反例

- 一张 3D 图里塞三层含义（模型 + 场 + 事件）⇒ 拆成 2–3 张，或 3D + 2D 面板。
- 每个问都画一张同构圆柱 ⇒ 合并；读者看不出差别，版面却翻倍。
- 透明面加网格线 + 内部再画 8 条母线 ⇒ 线太多，读者不知道看哪。
- 剖面没有填充 ⇒ 像空壳；加 `///` 或浅灰底。
- 热流箭头画成向外 ⇒ 物理方向错误；对流加热应指向表面内部。
- 白底框标签 ⇒ 切断几何；用白色底层文字描边。
- `path_effects` 给文字描边 ⇒ PDF 里文字转曲、丢字体；用双写文字。
- 3D 图用另一套字体/字号 ⇒ 与论文其他图不一致；统一 `configure_style`。
