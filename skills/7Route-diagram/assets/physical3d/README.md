# physical3d：物理立体 / 3D 剖切示意图工具包

第五类非数据图（`fig_geometry_3d`）的后端。完整规范见
`../../references/physical-3d.md`；这里只列文件和最短用法。

## 文件

| 文件 | 作用 |
|---|---|
| `style3d.py` | **Route A**：Matplotlib 3D 透明线框 + 2D 剖切；`annotate3d` 固定屏幕偏移并画引线 |
| `solid3d.py` | **Route B**：自写矢量投影 + 逐面深度排序的实心剖切；剖面填充、标签避让、QA 记录 |
| `qa_physical3d.py` | PDF 矢量/字体/宽度、标签越界/压实体/互相重叠检查 |
| `templates/route_a_wireframe.py` | 透明线框 + 2D 横截面（共用模型型） |
| `templates/route_b_cutaway.py` | 实心楔形剖切（实体型） |
| `templates/route_a_shrinkage.py` | 动域/材料坐标双面板（收缩型） |
| `templates/route_a_event.py` | 最坏点 + 事件求根（判据型） |

## 最短用法

```python
import sys
sys.path.insert(0, "skills/7Route-diagram/assets/physical3d")
import solid3d as S

S.configure_style("Microsoft YaHei", 8.5)
sc = S.Scene(S.Camera(azim=-58, elev=20, zoom=1.10))
sc.cylinder(r=2.0, z0=0, z1=12.5, cut=(70, -35), cut_hatch="///")
sc.label((0, 0, 12.6), "轴心 $r=0$", offset=(-12, 18), ha="right", auto=False)
fig, ax = plt.subplots(figsize=(90 / 25.4, 90 / 25.4 * 1.05))
sc.fit(ax, margin=0.12)
sc.draw(ax, fig)
sc.save(fig, "fig_geometry_3d", "figures", width_mm=90)
```

```bash
python skills/7Route-diagram/assets/physical3d/qa_physical3d.py \
    --pdf figures/fig_geometry_3d.pdf \
    --png figures/fig_geometry_3d.png \
    --scene figures/fig_geometry_3d.scene.json \
    --width-mm 90 --font "Microsoft YaHei"
```

## 两条纪律

1. **字体与论文其他图一致**：只调一次 `configure_style(font, base_size)`；
   不要为 3D 图另起一套 rcParams。
2. **文字不要用 `path_effects` 描边**：它会把文字转成轮廓，PDF 丢字体、不可检索。
   用“白色底层文字 + 彩色文字”双写；白底框会切断几何，也不要。
3. **画布宽度在 `draw()` 前定死**：`Scene.save(width_mm=...)` 不会再改 figsize；
   宽度不一致会直接报错。请用 `figsize=(width_mm/25.4, ...)` 建图，再 `fit/draw/save`。
