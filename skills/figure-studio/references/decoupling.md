# ④/⑦ 解耦与 figure lock（第二阶段，已落地）

> 状态：**已实现**（2026-10-18）。17 阶段编号不变，`7Route-diagram` 的 id 不变；
> 变的是 ④ 与 ⑦ 的**产物契约**：④ 只交数据层，⑦ 是唯一渲染者。
>
> 第一阶段（共享 skill + 统一画风 + 图型库）仍然有效；本文件只讲第二阶段的数据契约、
> 权限和回退路由。

## 1. 三件套：bundle / spec / lock

```text
figures/data/<id>.npz       # ④ 写：只读数据包（字段名 = 图里用的字段名）
figures/spec/<id>.json      # ④ 写：recipe + fields/field_mapping + claim/stats + layout
figures/<id>.lock.json      # ④ 写：bundle/spec 语义/source/claim 的 sha256
figures/make_figures.py     # ⑦ 写：读三件 -> 渲染
figures/<id>.pdf/.svg/.png  # ⑦ 写：成品
figures/source_data/<id>__<panel>.csv  # ⑦ 写：逐面板 tidy CSV
figures/<id>.meta.json      # ⑦ 写：language/width/counts/intervals/exclusions/claim
```

`reports/FIGURE_BRIEF.json`（或 `reports/figure_briefs/<id>.json`）仍是④写的“图意契约”；
`save_bundle` 会在存在对应 brief 时校验 claim/panel/fields 一致，并把 brief 的哈希写进锁。

### 1.1 ④ 的接口

```python
studio.save_bundle(
    ".", figure_id, {"r": r, "t": t, "C": C}, ctx,
    claim="...", sources=["results/q3.json", "code/q3.py"],
    panels=[{"id": "a", "recipe": "field_contour",
             "fields": ["r", "t", "C"],
             "field_mapping": {"x": "r", "y": "t", "z": "C"},
             "claim": "...", "options": {"quantity": "moisture", "level": 0.15}}],
    statistics={...}, caption="...", width_mm=160, height_mm=110,
)
```

它写三件，返回路径；**不写画布**。

### 1.2 ⑦ 的接口

```python
bundle = studio.load_bundle(root, figure_id)   # 只读
spec = studio.load_spec(root, figure_id)       # 只读
# ... 用 studio 的 recipe 画 ...
studio.save_figure(fig, root, figure_id, ctx, settings,
                   sources=studio.lock_sources(root, figure_id),
                   script="figures/make_figures.py",
                   claim=spec["claim"], caption="...",
                   source_data={...}, meta={...})
```

声明式 spec 可直接用 `skills/figure-studio/scripts/render_specs.py`（或复制成
`figures/make_figures.py`）。特殊拼版在 spec 里写 `render.mode = "custom"`，由 ⑦ 自己排。

## 2. 语义 vs 表现：锁的边界

`figure_lock.py` 只锁**语义部分**：

| 锁住（④ 的权限） | 不锁（⑦ 的权限） |
|---|---|
| `panels[].fields` | `recipe`（换图型） |
| `panels[].field_mapping` | `options`（gamma/level/quantity/labels…） |
| `panels[].claim` / `spec.claim` | `title`、`caption` 文字 |
| `statistics`（区间/检验/配对/单位） | `layout`、`axes_mm`、宽高、面板顺序 |
| `language` / `template` | 配色、线型、图例位置、字号 |
| `data.path` | `render.mode` / `script` 名 |
| `sources` 的字节 | `figures/make_figures.py` 的实现 |

判断标准：**这句话还成不成立**。换一种画法/颜色/面板顺序，claim 仍然成立 ⇒ ⑦ 可以改；
换字段、换统计口径、换 claim、换数据源 ⇒ 只有 ④ 能改。

## 3. 校验与路由

```powershell
python skills/figure-studio/scripts/figure_lock.py verify --root .
```

返回三类：

| 前缀 | 触发条件 | 路由 |
|---|---|---|
| `[lock:data]` | bundle/source 的 sha256 与锁不一致；字段缺失/形状/dtype 变 | **回 ④**：重出 bundle + lock。⑦ 修不了 |
| `[lock:contract]` | spec 的 fields/field_mapping/claim/statistics 变；meta.claim 与锁不一致；brief 在锁后被改 | **回 ④** 改语义；⑦ 只能把 spec 改回锁定值 |
| `[lock:advisory]` | 旧图还没有 bundle/spec/lock；caption 数字不在 claim 数字里 | 迁移提示；下次 ④ 重跑补齐 |

`audit_studio.py` 已内置 `figure_lock.verify`，所以 ⑧ 的机械地板会自动看到这三类。
驱动 `_gate_decision` 在 ⑧ 对 `[lock:data]` 直接回 `code`（category=`data_integrity`），
其余回 `drawio`（category=`diagram`）。这比“⑧ 先回 ⑦、⑦ 再写 HANDBACK 交回 ④”少一跳，
也避免 ⑦ 在数据不对时白重画一遍。

## 4. 权限表

| 阶段 | 只写 | 只读/不改 |
|---|---|---|
| ④ 编码计算 | `FIGURE_BRIEF.json`、`figures/data/*`、`figures/spec/*`、`figures/*.lock.json` | 不写画布、PDF/PNG、`make_figures.py`、source_data、meta |
| ⑦ 技术路线图/绘图 | `figures/make_figures.py`、`figures/*.pdf/.svg/.png`、`figures/source_data/*`、`figures/*.meta.json`、非数据图 `.drawio` | 不改 `figures/data/*`、spec 语义、`*.lock.json`、`code/`、`results/` |
| ⑧ 绘图门禁 | 只写 `FIGURE_REVIEW_REPORT.md` + verdict | 不改图、不改数据、不改 spec |

`save_figure` 在渲染前会 `verify_one`；锁不过直接抛错，不会“用旧数据画新图”。
它还会把 bundle/spec/lock 自动加进 manifest 的 `sources`，所以数据层一变，图就被
`python -m lib.visualization audit` 判过期。

## 5. 驱动侧改动

| 位置 | 改动 |
|---|---|
| `ARTIFACTS["code"]` | 加 `figures/data`、`figures/spec`、`figures/*.lock.json`（通配展开） |
| `_output_digest("code")` | 包含数据层；bundle/lock 被改 ⇒ ④ 的回执失配 |
| `_input_paths("drawio"/"figreview")` | 加 `figures/data`、`figures/spec` + 盘上现算的 `*.lock.json` |
| `_gate_decision("figreview")` | `[lock:data]` → target `code`，category `data_integrity`；其余 → `drawio` |
| `_stage_rels` / `_output_digest` | `_expand_rels()` 展开 `figures/*.lock.json` |

⑤⑥ 不读图，不受影响。⑨/⑭ 只读成品图，不变。

## 6. 向后兼容与迁移

- **旧图**：没有 `figures/data`/`spec`/lock 的图，`figure_lock.verify` 只给
  `[lock:advisory]`，`audit_studio` 也按迁移提示处理，不判 FAIL。下一次 ④ 重跑时补齐。
- **旧 ④ 脚本**：仍然可以直接 `save_figure`（不经过锁），行为与以前一致；但新写的图
  应走 `save_bundle`。迁移完成前允许两套并存。
- **旧 ⑦ 行为**：仍可改 `figures/make_figures.py` 重渲；只是现在它读 bundle，不读
  `code/outputs/*.npz` 的临时变量。
- **不需要重跑全链**：第一次 ④ 重跑会产出三件套；⑦ 的输入指纹因此变化，会自动重渲一次。
  已经跑完的旧题不必批量迁移，除非要再交付。

## 7. 出图与返修循环（⑦/⑧）

解耦后的 ⑦ 不是“拿到 spec 就画”，而是一个**选图—候选—自评—优化—按图返修**的循环：

1. **triage**：读 spec/bundle，判断数据形态是否撑得起 claim；不适合就按 `recipes.json`
   的 `fallback` 换图型（不改 fields/claim）；数据本身不够就交回 ④。
2. **候选**：每个主图至少 2 个不同视觉编码的候选，落 `tmp/figures/<id>/cand_*.png`，
   不登记、不写 `figures/`。
3. **自评**：打开最终尺寸的 PNG，按 claim 支持 / 信息密度 / 可读性 / 灰度 / 语言统计 /
   冗余六条打分；“右侧 55% 空白”“九宫格只用 1 格”“色标只用 2 档”都算信息密度失败。
4. **优化**：选中的候选改 layout/recipe/options 后定稿，串行 `save_figure` 登记。
5. **并行**：图多时用 `Agent` 按 `figure_id` 分组并行**只做候选与自评**；子 agent 只写
   `tmp/figures/<id>/`，不得写 `figures/manifest.json`（整份读—改—写，跨进程会丢条目）；
   主 agent 收齐后串行登记。
6. **⑧ 返修**：⑧ 的每条 issue 必须带 `figure_id`；⑦ 只重渲被点名的图，其余图的
   PDF/SVG/PNG/source data/meta 保持逐字节不变（改前/改后 sha256 对账）。
   未打回但可优化的项写 `reports/FIGURE_POLISH_QUEUE.json`；不阻塞链，⑦ 下次运行时按图处理。
7. **逐图隔离**：`render_specs.py` 逐图验锁；某张失败只跳过该图并报错，其余照渲 ——
   一张坏图不会拖住整批，也不会把“只改这一张”变成“全量重渲”。

这样 ⑧ 的“这批图里某几张太丑/太空”不会变成“⑦ 全量重渲 12 张”，也不会把数据层问题
误送到 ⑦ 白跑一轮。

## 8. 没做的部分（明确边界）

- 锁是**契约**，不是密码学签名：能抓“改完忘了重签”，抓不住“同时改数据、spec 和 lock
  且三者自洽”的恶意操作。竞赛场景不需要对抗性签名。
- 没有把 ⑤/⑥ 的稳健性图纳入三件套；它们仍是普通 `export()` 登记。若将来它们也要
  走 ⑦ 渲染，按同一契约加 `save_bundle` 即可。
- 没有强制所有旧图批量重渲；迁移是“下次 ④ 重跑时补”。
- 没有把 `figures/spec` 做成 JSON Schema 强校验；`save_bundle` + `figure_lock.build`
  已经校验字段/claim/形状，`check_brief` 仍校验 FigureBrief。
