# 通用科研绘图协议

本协议用于生成数据图、非数据图登记、写作选图和最终验收。公共 `lib/visualization/` 与 `config/visualization.json` 位于生成目录之外，换题保留，并随交付包分发。依赖见 `lib/visualization/requirements.txt`。从项目根目录运行 Python；子目录脚本须把项目根目录加入 sys.path，避免硬编码本机路径。

> **选型与统一画风先读 `skills/figure-studio/SKILL.md`。** 它把数据图型库、比较与拼版、投稿契约与质控、场图与 3D 内核合成一个入口；
> 数据图用 `skills/figure-studio/scripts/studio.py` 的 recipe，语言/宽度由
> `resolve_context.py` 从论文模板解析（CUMCM → 中文、160 mm、微软雅黑）。本文件的
> `charts` 函数仍是底层渲染与登记协议，二者不冲突。
>
> **④/⑦ 已解耦**：④ 只写 `figures/data/<id>.npz` + `figures/spec/<id>.json` +
> `figures/<id>.lock.json`（`studio.save_bundle`）；⑦ 是唯一渲染者，写
> `figures/make_figures.py` / PDF/SVG/PNG / source data / meta（`studio.save_figure`）。
> 数据层契约与 `[lock:data]` / `[lock:contract]` 路由见
> `skills/figure-studio/references/decoupling.md`。

## 论文主图：Nature-style plate

每问的论文主图用 `skills/plate-figure/SKILL.md` 的 plate 语法：kicker → 结论式 title → subtitle，
hero 面板占 40–55%，其余面板不等宽马赛克，底部 summary band。当前题的可运行模板是
`figures/plate_q3.py`（`fig_q3_plate`）与 `figures/plate_q2.py`（`fig_q2_plate`）。
`figures/spec` 的 9 张图是支撑面板/数据层，不直接替代 plate；单图 sci-box 模板在
`skills/mathmodel-figure-templates/`。plate 只读 bundle/results，不重算数值。

## 先规划，再画图

在 `reports/FIGURE_PLAN.md` 中记录每张图的稳定语义 ID、它回答的问题、来源文件和字段/单位、**2 个以上不同视觉编码的候选**、区间定义、正文/附录用途、最终宽度。按论证需求选图，不设“每问至少几张/至少一张非折线”的配额；折线是最后手段（支撑图折线面板受 `chart_mix.line_budget` 限制），场分布优先 `field_raincloud`/`raincloud`，离散时刻优先 `grouped_bars`/`dot_interval`，只有空间结构本身是 claim 时才用场图。同一 bundle + 同一视觉编码只出一张图。没有实际计算支持的统计区间、最优点和权衡曲线不进入计划。流程图根据实际子问题生成，节点每行约十字、最多两行，长公式留正文。

## 数据图契约（④ → ⑦）

```text
figures/data/<id>.npz        # ④：只读数据包
figures/spec/<id>.json       # ④：recipe + fields/field_mapping + claim/stats + layout
figures/<id>.lock.json       # ④：bundle/spec 语义/source/claim 的 sha256
figures/make_figures.py      # ⑦：渲染器（唯一写者）
figures/<id>.pdf/.svg/.png   # ⑦：成品
figures/source_data/<id>__<panel>.csv   # ⑦
figures/<id>.meta.json       # ⑦
```

- ④ 用 `studio.save_bundle(...)`；**不写画布、不写 PDF/PNG、不写 `make_figures.py`**。
- ⑦ 读 bundle + spec；可以换 recipe/layout/配色/标题/caption，**不能改** fields、
  field_mapping、statistics、claim、bundle、lock。
- 渲染前 `studio.save_figure` 会跑 `figure_lock.verify_one`；锁不过直接拒绝。
- `python skills/figure-studio/scripts/figure_lock.py verify --root .` 是 ⑦/⑧ 的必跑项；
  `audit_studio.py` 已内置它。
- 旧图没有三件套时只给 `[lock:advisory]`，下次 ④ 重跑补齐；不要求批量迁移。

## 数据图实现

从 `visualization.charts` 导入 `style, canvas` 和相应图型函数：

| 函数 | 输入及边界 |
| --- | --- |
| trend | 已排序 x/y，可选完整上下界和区间名称；不拟合、不生成区间 |
| comparison | 分类与点估计，可选上下界；排序由调用者明确决定 |
| distribution | 各组全部观测，共用分箱；显示实际 n；不做显著性检验 |
| heatmap | 已算好的矩阵；相关矩阵须显式 correlation=True，使用以零为中心的色标 |
| response | 已计算的二维参数网格与结果；二维等高线优先 |
| diagnostics | 已保存的观测与预测，组合一致性、残差及残差分布；不训练模型 |
| surface3d | 已算好的 (x, y) 网格与曲面值；默认细网格边（防淡色低值平台糊在白底上）、默认抽稀；`level=` 画该量等于某值的判据交线（逐列求交连成折线，不是 `contour`——mplot3d 的等值线集合会被曲面遮住）；并排共用色阶时传 `colorbar=False` |
| bars | 分类 × 若干序列的点估计（柱高即数值）；可选上下界（同 `comparison` 的口径，边界必须包含中心） |
| boxplot | 每组的整个分布；多组同图可比；`log_scale=True` 用于跨数量级的数据 |
| ecdf | 经验累积分布，直接读"小于某值的比例"；多组同图时竖直间距即两组之差 |
| contour | 填充等高线（与 `heatmap` 同为一个二维场，但读的是等值线形状）；`lines=` 标注若干层、`highlight=` 突出判据层；色阶按 `quantity` 取 |

这些函数操作 Axes，可在 GridSpec 中组合。数据存在 NaN/Inf 时明确处理并记录剔除原因，不静默丢弃。坐标轴、图例和 caption 说明单位、中心统计量、区间来源与含义。图内不放大标题。三维数据曲面用 `surface3d`（**别手写 `plot_surface`**：网格边、抽稀、放大盒子这些默认值是为「低值淡色平台糊在白底上」修的，住库才带得到下一题），仅在第三维确有意义时用，并配二维图。

**连续量的色阶按物理量取，不按审美取**：`heatmap` / `response` / `surface3d` 都收 `quantity=`，
查 `config/visualization.json` 的 `quantity_cmap` 登记处（如 `quantity="temperature"` → `inferno`）。
**同一个量跨图必同色，不同量必不同色** —— 这就是「颜色语义跨小问一致」的可执行形式。
表里没有的量往那张表加一行（写清哪一端是"大"），别在脚本里写死 `cmap=`；未登记的名字会发 warning 而不是静默退回。

低值平台会压平后段：场图的低值区常占一大片，线性色标下那一片被压成一个颜色
（实测一版二维投影 t≳22 h 占栏高 43.6% 是死色，干前沿只能靠外加的判据线读）。
`quantity_cmap` 里每个量的 `gamma`（`PowerNorm(γ<1)`）把低端拉开 —— 同一套色标、
同一 vmin/vmax 不变，后段色差重新可见。`heatmap` / `response` / `surface3d` 都收 `gamma=`，
缺省取登记表的值。它与 `slice` 分工不同：`slice` 治「最低端近白、吃掉白线」，`gamma` 治
「低值区占一大片、后段压平」。另：`export()` 会跑 `quality.near_monochrome` —— 非白像素里
同色占比 ≥75% 时打印一条提醒（不进 `auto_issues`），提示这张图可能该改成剖面/折线。

> 下面的 `export` 是**底层**登记协议，⑦ 或未接 `save_bundle` 的旧脚本仍可直接用；
> ④ 新写的图请走 `studio.save_bundle`，不要用这段直接出成品。

```python
from lib.visualization.charts import style, canvas, trend
from lib.visualization.export import export

with style() as settings:
    fig = canvas(settings)
    ax = fig.add_subplot()
    # x/y 是从当前已保存结果读入的数组。
    trend(ax, x, y, label="方案甲")
    ax.set(xlabel="年份", ylabel="收益（万元）")
    ax.legend()
    export(fig, project_root, "q1_revenue", sources=["code/outputs/revenue.csv"],
           script="figures/make_figures.py", claim="填写数据支持的结论",
           caption="填写变量、单位及必要的统计定义", settings=settings)
```

`export` 输出 PDF、可编辑文字 SVG 和 PNG 预览，保留指定物理尺寸，自动登记 `figures/manifest.json`。
画图脚本由 ⑦ 拥有，必须住 `figures/`（例如 `figures/make_figures.py`）；写进 `code/` 会让
改一行配色连锁触发 ⑤⑥⑦⑧ 重跑。默认宽 160 mm、字号 9 pt、最低 8 pt；这是本项目初始样式，不是比赛强制标准。使用半栏应按实际半栏宽重新排版，不能把复杂图直接缩小。不同方案跨图保持同色，并用线型/标记补充区分。自定义尺寸通过 `canvas(settings, width_mm=..., height_mm=...)`。

## 自定义图和 DrawIO

数学物理、几何或空间关系图先读取 [几何图分支](GEOMETRY.md)，再选择二维关系图、三维整体图和必要截面。选图及论文嵌入同时遵循 [篇幅与公式协议](PUBLICATION.md)。

自定义 Matplotlib 图仍用上述 export。外部 DrawIO 导出的资产用 `python -m lib.visualization register spec.json` 登记，spec 示例：

```json
{
  "figure_id": "roadmap",
  "artifacts": ["figures/roadmap.pdf", "figures/roadmap.png"],
  "sources": ["reports/ANALYSIS_MODELING_REPORT.md"],
  "script": "figures/roadmap.drawio",
  "claim": "说明本题的方法与子问题依赖",
  "caption": "本题技术路线",
  "width_mm": 160,
  "included": true
}
```

sources 列出所有实际依赖（不能仅列第一份数据），script 是生成脚本或可编辑源文件。每次重绘重新登记，自动重置复核。废弃/仅调试图也要登记，设 included=false，并在 caption 写清排除理由；正文实际引用须由写作和终验核对。资产路径均相对项目根，禁止越界。

## 视觉复核与验收

1. 生成者打开实际 PNG/PDF，检查缺字、裁切、图例遮挡、同色混淆、轴范围、单位和区间含义。自动检查能
   **文本框不许溢出它所在的框、也不许压到框线** ——
   这是流程框图/路线图最容易犯的一类（文字比框宽、或换行后最后一行越出框底）。判据（生成期就自检）：
   · matplotlib 侧：`t.get_window_extent()`（或 `TextPath`）与所在 `Rectangle`/`FancyBboxPatch` 的
     `get_window_extent()` 比，**任一方向越界即改**（缩字号 / 改文案 / 加宽框，别硬塞）；
   · drawio/`paper-diagram` 侧：在 `roadmap_*` 脚本里对每个文本算宽高与所在格比一遍（脚本里有几何，
     不靠目测）；
   · 位图层兜底：`visualization.quality.texts_overlap` 只查文字压文字，查不到字压线
     （`docs/KNOWN_GAPS.md` 附录里的「待办 8」）；所以这条目前**必须靠生成期自检 + 目检**，不许默认"应该没事"。捕获部分缺字、超出画布和过小字号，不能确认所有重叠或科学正确性。
2. 修复后重新导出。实际目检后另行运行 `python -m lib.visualization review q1_revenue --reviewer "当前审阅者" --note "记录实际看到的布局、文字、图例及仍存在的限制"`。生成脚本不得自动调用 review。
3. 运行 `python -m lib.visualization audit`。它只读检查所有已登记入选图的当前来源、脚本、配置、公共模块、图片哈希和复核签名；未登记的 PDF/PNG/SVG 会报错。零图场景由报告说明不适用依据。
4. 8Figure-gate（绘图门禁，紧跟 7Route-diagram）：⑦ 一跑完，全文的图就都在盘上了 —— 这是最早能对图全集做检查的位置。驱动在此直接跑 `python -m lib.visualization audit` + `figure_lock.py verify`（机械地板：过期资产/登记缺失/复核签名/位图质量/图例压数据/drawio 版式体检/数据锁），再加一轮机器看不见的核对（选型是否合适、读起来清不清楚、与 claim 是否一致）。**只判不改**：画法/契约 FAIL 回 7Route-diagram 重画；`[lock:data]` 是数据层问题，直接回 4Coding-and-computation。每条 issue 必须带 `figure_id`，⑦ 只重渲被点名的图。判据与逐张清单见 `skills/8Figure-gate/SKILL.md`。
5. 14Layout-and-format 核对正文选图、图注、引用与 included 标记，按最终纸面尺寸查看编译 PDF（编译与逐页视觉验收归它；9Paper-writing 只决定图放哪一节）；如需改图，重绘、重新登记、目检。图像内容改变后旧复核失效，caption/宽度/用途改变后签名也失效。
6. 15Verification 只读执行 `python -m lib.visualization audit` 与 `figure_lock.py verify`，并独立查看论文中所有入选图，记录页码和具体发现到 VERIFY_REPORT。发现问题给前序返修（图缺失/画错 → 7Route-diagram，category=diagram；版式/嵌入尺寸 → 14Layout-and-format，category=presentation）；不要在审查中改图或登记通过。Web 终验不能以总报告 PASS 绕过图表证据失败。
   > 8Figure-gate 与 15Verification 两条图闸门都在，分工是时间：前者管"图刚做出来"的早场，后者管"成稿之后图又被动过"（14Layout-and-format 会重渲染）的晚场。别互相替代。

### 「哪些文件算这张图的依赖」—— 只算产像素的

`snapshot()` 哈希的是：该图的 `sources` / `artifacts` / `script`、`config/visualization.json`，
以及 `lib/visualization/PIXEL_PRODUCERS`（`charts.py`、`schematic.py`、`geometry.py`、`dense.py`、
`export.py`）。**检查器 `quality.py` 与登记簿 `evidence.py` 不在里面** —— 它们不产像素。
④/⑦ 解耦后，`save_figure` 会把 `figures/data/<id>.npz`、`figures/spec/<id>.json`、
`figures/<id>.lock.json` 自动加进 `sources` —— 数据层一变，图就被判过期；这也是
`figure_lock` 之外的第二道保险。

若按 `lib/visualization/*.py` 整目录哈希：只往 `quality.py` 加一条 warning 判据，
19 张图全部会被判「数据、脚本、配置或图片已改变，需重新生成和复核」⇒ 逼着 ⑦/⑧ 把整套图
重画重看一遍，而像素一个都没动。这与 `docs/WORKFLOW_RELIABILITY.md` 记的
「共享文件被整目录哈希进每个阶段」是同一个病：**按真实依赖定指纹，不按目录归属**。
想让全部图重判（收紧了检查口径、或就是想重看一遍）⇒ 动 `config/visualization.json`
（它在快照里，这是有意的口子）。
反向不许松：**改了产像素的模块，图必须被判过期** ——
`regression/test_visualization.py::SnapshotScopeTests` 把正反两侧都钉住了。

### 位图第四查：单侧「贴边非白带」

`inspect_png` 现查四条边里有的贴着非白底块、有的干净（左+上有、右+下没有）。病因：
`fig_roadmap` 的 .drawio 里两个实心浅灰矩形（`#E2E8F0`、`strokeColor=none`）拼成的 L 形底块
（左 47 px / 顶 28 px）—— 放在白底正文里活像一副没对齐的边框，而只数"暗"像素的
`border.mean(axis=1) < 32` 对它天生失明：那个灰是 232.7 ⇒ 0 error / 0 warning 地放行。
只抓不对称（四边都贴 = 有意画的框，不报），`EDGE_MIN_WIDTH=6` 把 matplotlib 的轴线
（1~2 px）挡在门外，`EDGE_SCAN_FRACTION` 封顶扫描成本。
实测校准：19 张已登记图里恰好只命中 `fig_roadmap` 一张（报「左47px、上29px」，与
目视的 47/28 px 逐点吻合），其余 18 张（含带轴线的 matplotlib 图）全清白。

复核命令是带版本的审阅声明，不能技术上证明审阅者确实看图。论文嵌入尺寸、正文真实引用与图片科学含义仍须终验检查。样式变化触发保守重验，保证旧图不被当作新样式产物。

## 验证和示例

`python -m lib.visualization.example --output tmp/visualization-example` 只生成独立的合成数据示例，不读题目、不训练模型、不写生产 figures。示例不是赛题结果，不能引用进论文。

回归：`python -m unittest discover -s regression -v`；绘图测试需要 NumPy/Matplotlib，可在完整科学栈环境执行。真实赛题端到端效果仍需下一次完整运行验证。
# 高密度图补充

生成超过24行的热图、跨正负号比较不同指标，或把图嵌入论文时，读取 docs/WRITING_QUALITY.md 的“高密度图”。可复用 visualization.dense.faceted_heatmap；在 FIGURE_PLAN 中选择正文汇总或附录明细，并说明指标定义与共用色标。已保存数据可以重绘，不因排版重跑求解器。
