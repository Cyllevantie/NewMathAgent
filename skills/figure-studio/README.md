# Figure Studio

一个共享绘图 skill，把四套方法收进同一个入口：

- **数据图型库（data-recipe-library）**：11 个模板全部有通用实现（云雨、ROC+CI、Taylor、相关矩阵、预测边缘、3D 调参曲面、SHAP、半边小提琴、环形热图、组成组合、和弦）；数据不适配时按 fallback 降级；
- **比较与拼版（comparison-and-composition）**：分组柱、消融、组成分解、宽画布、黑边柱、hatch、legend panel、拼版；
- **投稿契约与质控（publication-contract）**：Figure contract、hero+evidence、多面板证据架构、渲染 QA、source data；
- **场图与 3D 内核（field-and-3d-core）**：场图/等高线/3D 曲面/语义色阶/导出登记/目检签名。

## 快速开始

```powershell
python skills/figure-studio/scripts/resolve_context.py --write
python skills/figure-studio/scripts/check_brief.py reports/FIGURE_BRIEF.json --context reports/FIGURE_CONTEXT.json
python skills/figure-studio/scripts/figure_lock.py verify --root .
python skills/figure-studio/scripts/audit_studio.py --root .
```

④ 交数据层（不画布）：

```python
import sys
sys.path.insert(0, "skills/figure-studio/scripts")
import studio

ctx = studio.context(".")
studio.save_bundle(
    ".", "q3_field", {"r": r, "t": t, "C": C}, ctx,
    claim="干前沿由表面推进到中心。",
    sources=["results/q3.json", "code/q3.py"],
    panels=[{"id": "a", "recipe": "field_contour",
             "fields": ["r", "t", "C"],
             "field_mapping": {"x": "r", "y": "t", "z": "C"},
             "claim": "干前沿随时间向内推进。",
             "options": {"quantity": "moisture", "level": 0.15}}],
    statistics={"interval": {"kind": "none", "method": "不适用"},
                "test": {"kind": "none", "p_values": False},
                "unit": "确定性模拟", "paired": False},
)
```

⑦ 渲染（唯一写者）：

```python
bundle = studio.load_bundle(".", "q3_field")
spec = studio.load_spec(".", "q3_field")
with studio.style(ctx) as settings:
    fig = studio.canvas(ctx, width_mm=160, height_mm=110)
    ax = studio.axes_mm(fig, 12, 20, 90, 70, width_mm=160, height_mm=110)
    studio.field_panel(ax, bundle["r"], bundle["t"], bundle["C"], ctx, kind="contour",
                       quantity="moisture")
    studio.save_figure(fig, ".", "q3_field", ctx, settings,
                       sources=studio.lock_sources(".", "q3_field"),
                       script="figures/make_figures.py",
                       claim=spec["claim"], caption="...",
                       source_data={"a": (("t_h", "r_cm", "C"), rows)},
                       meta={"intervals": "无统计区间", "exclusions": "无"})
```

声明式 spec 可直接用 `scripts/render_specs.py`；它逐图验锁，一张失败只跳过该图。
特殊拼版在 spec 里写 `render.mode="custom"`。

## 文件

- `SKILL.md`：入口与阶段边界；
- `references/catalog.md`：42+ 图型的数据契约；
- `references/composition.md`：hero+evidence / plate / 面板角色；
- `references/style.md`：配色、字体、字号、3D、导出；
- `references/language.md`：模板语言解析；
- `references/qa.md` / `statistics.md` / `source-data.md`：门禁；
- `references/ecosystem.md`：外部参考与授权原则；
- `references/module-map.md`：数据图型库 / 比较与拼版 / 投稿契约的逐项落点与实现状态；
- `references/decoupling.md`：④/⑦ 解耦契约、figure lock、权限与回退路由；
- `assets/style.tokens.json`：分类色/字体/字号/画布/3D 边线的唯一来源；连续量色阶仍走 `config/visualization.json` 的 `quantity_cmap`；
- `scripts/figure_lock.py`：bundle/spec 语义/source/claim 的锁，`build` / `verify`；
- `scripts/render_specs.py`：⑦ 的默认声明式渲染器（可复制成 `figures/make_figures.py`）；
- `scripts/smoke_recipes.py`：对 6 个通用模板（SHAP 组合、ROC+CI、半边小提琴相关矩阵、环形热图、组成+云雨+箱线、和弦）做形状/API 冒烟渲染（合成数据，不写生产图）。
- `scripts/studio.py`：已实现 recipe、`save_bundle`、`save_figure`、`render_spec`。半栏图先
  `with studio.style(ctx, width_mm=80)`，再用 `studio.canvas(ctx, width_mm=80)`；两处宽度要一致。

## 边界

- 数据/claim/bundle/spec/lock 归 ④；所有数据图渲染与图面/构图归 ⑦；⑧ 只判不改。
- ⑦ 只能改 recipe/layout/配色/标题/caption，不能改 fields/field_mapping/statistics/claim/bundle/lock。
- 不新增阶段，不改 17 阶段编号。
- 非数据图（draw.io 路线图/流程图）继续走 `skills/paper-diagram`。
- 外部模板的模拟数据必须替换；没有真实区间/标签就不画 CI/ROC。
