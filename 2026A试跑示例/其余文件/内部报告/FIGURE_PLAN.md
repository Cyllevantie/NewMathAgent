# 图表规划（`code` / 4Coding-and-computation）

> 本文件是本阶段图件的**规划与登记账本**：每张图的稳定语义 ID、它回答的问题、来源文件与字段/单位、
> 图型、区间定义、正文/附录用途、最终宽度。生成脚本是 `figures/make_figures.py`（**住 `figures/`，
> 不住 `code/`** —— `code/` 在 ⑤⑥⑦⑧ 的输入指纹里，画图脚本放进去会让"改一行配色"连锁触发下游重跑）。
> 只读**已保存的结果**（`code/outputs/figdata_*.npz`、`results/*.json`），本脚本不重跑求解器、不做拟合。

## 0. 选型口径（为什么这样分栏）

本题的状态量 $T(r,t)$、$C(r,t)$ **各是一张二维场**：空间一维 + 时间一维。所以

- **场** → 填充等高线（`charts.contour`，配 `quantity=` 取语义色阶）；
- **沿 $r$ 或沿 $t$ 的切片** → 折线（`charts.trend`）；
- **类别比较 / 排序** → 横排点图（`charts.comparison`）或柱状（`charts.bars`）。

★ **两处必须分栏/裁范围，否则图会退化成死色块**（生成期实测后改的，不是预判）：

1. **温度场不能画 72 h 全窗口**：温度在约 4 h 内就与环境同步，全窗口的 $T(r,t)$ 图上 93% 的
   非白像素是同一个颜色。⇒ `q2_temp_field` 左栏只画 0–8 h，右栏改用**径向温差**时程。
2. **贴近判据的场必须把色阶裁到前沿的取值区间**：`q3_dryfront` 取 $C\in[0.045,0.17]$、
   `q4_field` 取非均匀层（前沿区间 [0,0.5] 上密、湿区单层）。

## 1. 图件清单

| # | 稳定 ID | 回答什么问题 | 来源（文件 :: 字段 :: 单位） | 图型 | 区间定义 | 用途 | 宽度 |
|---|---|---|---|---|---|---|---|
| 1 | `q1_field` | 预热段温度/水分场的**结构**：温度整体抬升、水分只在最外层 | `code/outputs/figdata_q1.npz :: t, r_cm, T_C(°C), C(kg/kg)` | 等高线 ×2 | $t\in[0,1800]$ s 每 60 s 一帧；$r\in[0,2.0]$ cm | 正文（问题 1） | 160 mm |
| 2 | `q1_profiles` | 表 1/表 2 的 7 个时刻剖面长什么样 | `figdata_q1.npz :: table1, table2, table_t(s), table_r(cm)` | 折线 ×2（带标记） | 7 时刻 × 5 半径（= 表 1/表 2 的格点） | 正文（问题 1） | 160 mm |
| 3 | `q2_moist_field` | 全程干前沿的推进与到达中心的时刻 | `figdata_q2.npz :: snap_t_h(h), r_cm, snap_C` | 等高线（含 0.15 判据线） | $t\in[0,72]$ h 每 0.5 h；$r\in[0,2.0]$ cm | 正文（问题 2/3） | 160 mm |
| 4 | `q2_temp_field` | 热响应比水分快多少 | 左：`figdata_q2.npz :: snap_T_C`；右：`T_surface_C - T_center_C`（K） | 等高线 + 折线 | 左 $t\in[0,8]$ h；右 $t\in[0,6]$ h，线性纵轴 | 正文（问题 2） | 160 mm |
| 5 | `q2_drydown` | 中心/表面/均值/环境四条含水率时程与达标时刻 | `figdata_q2.npz :: t_h, C_center, C_surface, meanC, C_inf`；`results/q3.json :: t_dry_h` | 折线（对数纵轴） | $t\in[0,72]$ h，60 s 抽样 | 正文（问题 2/3） | 130 mm |
| 6 | `q2_diffusivity` | $D(C,T)$ 的降速结构与表面状态走过的路径 | `figdata_q2.npz :: D_C(kg/kg), D_T_C(°C), D_grid(m²/s)`；轨迹 `C_surface/T_surface_C` | 响应面 + 轨迹 | $C\in[0.05,2.60]$、$T\in[28,52]$ °C；轨迹每 600 s 一点 | 正文（问题 2） | 160 mm |
| 7 | `q3_criteria` | 判据函数 $g(t)$ 的单调性与零点位置 | `figdata_q2.npz :: t_h, maxC(kg/kg)`；`results/q3.json :: t_dry_h` | 折线 ×2（左全程、右零点放大） | 左 $t\in[0,72]$ h；右 $t_{dry}\pm0.25$ h（$\Delta t=1$ s 网格） | 正文（问题 3） | 160 mm |
| 8 | `q3_dryfront` | 末段干前沿的形状与抵达中心的时刻 | `figdata_q2.npz :: snap_t_h, r_cm, snap_C` | 等高线（色阶裁到前沿区间） | $t\in[52,58]$ h；色阶 $C\in[0.045,0.17]$ | 正文（问题 3） | 160 mm |
| 9 | `q4_shrinkage` | 收缩的时间分布 + 动域上的达标过程 | `figdata_q4.npz :: t_h, R_cm, C_center, C_surface`；`results/q4.json :: t_dry_h` | 折线 ×2（左对数横轴、右对数纵轴） | $t\in[0,72]$ h；$R\in[1.15,2.05]$ cm | 正文（问题 4） | 160 mm |
| 10 | `q4_field` | 物质坐标下前沿的推进（与固定几何形态一致） | `figdata_q4.npz :: xi, snap_t_h, snap_C` | 等高线（非均匀色阶层） | $t\in[0,72]$ h；$\xi\in[0,1]$ | 正文（问题 4） | 160 mm |
| 11 | `q4_effects` | 几何加速 vs 物性减速的效应分解 | `results/sensitivity.json :: calibers.decomp_*` | 柱状（4 档，含 1 个下界档） | 统一 $n=320$、$\Delta t=60$ s 的步进首达 | 正文（问题 4） | 120 mm |
| 12 | `caliber_sensitivity` | 哪些口径是主要不确定度来源 | `results/sensitivity.json :: calibers.*` | 横排点图（7 档） | 各档各自的 $n$/$\Delta t$，标签内写明 | 正文（检验节） | 150 mm |
| 13 | `convergence` | $t_{dry}$ 对网格/步长的收敛 | `results/convergence.json :: mesh_tdry, step_tdry` | 折线 ×2（左对数横轴） | 左 $n\in\{80,160,320,640\}$；右 $\Delta t\in\{1,10,30,60\}$ s | 附录/正文（收敛证据） | 160 mm |

**区间口径**：除 `q2_temp_field` 右栏与 `q3_criteria` 右栏外，图中所有时刻轴都是**从烘干开始计的
绝对过程时间**（与题面/附件/交付件同基准）。图中的一切数值都直接来自上表列出的来源字段，
没有在画图脚本里做任何拟合或参数标定。

## 2. 每问的覆盖核对（`config/visualization.json` 的 `chart_mix`）

| 小问 | 图件数 | 其中非折线图 |
|---|---|---|
| Q1 | 2（`q1_field`、`q1_profiles`） | `q1_field`（等高线 ×2） |
| Q2 | 4（`q2_moist_field`、`q2_temp_field`、`q2_drydown`、`q2_diffusivity`） | `q2_moist_field`、`q2_temp_field`、`q2_diffusivity` |
| Q3 | 2（`q3_criteria`、`q3_dryfront`） | `q3_dryfront` |
| Q4 | 3（`q4_shrinkage`、`q4_field`、`q4_effects`） | `q4_field`、`q4_effects` |

⇒ 每问 ≥2 张数据图，且每问至少一张非折线图 ✓。

## 3. 换配色时要同步的**非数据图**资产

本阶段**没有**修改 `config/visualization.json` 的 `palette` 或语义键（只**新增**了一行
`quantity_cmap.diffusivity`：`viridis`、方向"大=扩散快=亮黄"、`gamma=0.45`——`q2_diffusivity`
需要一个**有语义登记**的色阶，不能就地编一个）。

因此 `figures/*.drawio` 这类**颜色烤在文件里**的非数据图**不受影响**；本题的非数据图
（技术路线图、耦合结构图、几何与网格示意、动边界坐标变换示意）由 **7Route-diagram** 产出，
本阶段不生成、也不改动它们。**若后续任何阶段改动了 `palette` 或语义键**，必须回头
逐张重画 `figures/*.drawio` 并按新语义键校验（判据：PNG 里能看到 `palette[0]` 或 `warn`）。
`lib/visualization/evidence.py::snapshot` 把 `config/visualization.json` 哈希进每张图的指纹，
所以改配置会让全部数据图自动判为过期 —— 那是**有意留的口子**。

## 4. 目检与验收

- 13 张全部目检（打开 PNG 逐张看：缺字、裁切、图例遮挡、同色混淆、轴范围与单位），
  复核记录写在 `figures/manifest.json` 的 `review` 字段（`python -m lib.visualization review <id>`）。
- `python -m lib.visualization audit` ⇒ **PASS**（无过期资产、无未登记图、无自动检查项未过）。
- 配色与线型：`q1_profiles` 的 7 条剖面用**颜色 + 线型 + 标记**三重区分（灰度打印与色盲可读）；
  连续量一律走 `quantity=`（温度 `inferno` 亮=热、水分/扩散系数 `viridis` 亮=湿/快），
  跨图同量同色。
- **判据线只用 `warn` 红**（`C=0.15`），不当普通序列色。
- 手写 `ax.plot` 一律显式给 `linestyle`（`style()` 的 `prop_cycle` 同时含颜色与线型，
  不给就会被轮换成虚线）；`q2_diffusivity` / `q4_field` 的红线都显式写死了 `"-"`。

### 4.1 返修轮的重画与复核（本轮）

返修改了 `results/q3.json` 与 `code/outputs/figdata_sens.npz`（写入时间戳），`audit` 据此报 4 张陈旧：
`q2_drydown`、`q3_criteria`、`q3_dryfront`（源含 `q3.json`）与 `convergence`（源含 `figdata_sens.npz`
/`convergence.json`）。这 4 张**已重画并重新目检、重签 `review`**；其余 9 张 PNG 逐字节未变。
重画后这 4 张的 **PNG 逐字节相同**（画面零变化；PDF/SVG 因内嵌时间戳必变，不能用它判画面）。
证据：`_tmp/r5_fig_and_artifact_probe.py` 的 B/C 段。

> ⚠️ **本轮目检新发现两处可读性缺陷（未改，交 ⑦ 就地优化）**：① `q3_criteria` 右栏横轴
> `56.95`/`57.1` 刻度标签相压、`convergence` 左栏对数轴 `80 160 320 640` 挤成一串 ——
> 三道机器闸（越界/小字号/图例压数据/**文字互压**）**都不查刻度标签之间**；
> ② `q3_dryfront` 的白色等值线标注 `0.15` 与红阈值线同层、红线从数字中间穿过。
> 两处都是"图画得好不好"，按 SKILL 归 ⑦；重画前后 PNG 逐字节相同 ⇒ **非本轮引入**。
