# scene3d v1 速查（16Web-demo 三维内核）

> 版本串 `scene3d v1` 与资产里 `Scene3D.version`、本文件、SKILL 三处对账（回归夹具钉着）。

**源文件**：`skills/16Web-demo/assets/scene3d.js`（零依赖、Canvas 2D、约 17 KB）。
**用法**：读它，把**整段原文**原样复制进 `demo/demo.html` 的 script 块里 —— 一个字符都不改。
交付检查（`lib/delivery/checks.py` 的 `demo_3d_issues`）会拿源文件的整段原文在 demo.html 里
做包含比对；回归夹具 `regression/demo3d_check.js` 对同一份资产做行为测试。
**要改引擎**：改源文件、把版本号 +1（源文件与本文标题两处）、重跑 ⑯ —— 不要在产物里就地改。

---

## 一分钟上手

```js
// 1) 画布：尺寸写死在属性上（引擎只读一次，之后从不改写 —— backing store 幂等）
//    style 里 width:100%;max-width 只许缩小不许放大；touch-action:none 否则触屏拖动会滚页面
var sc = Scene3D.create(document.getElementById('cv3Main'), {
  bounds: {x: [-1, 1], y: [-1, 1], z: [0, 2]},   // 数据坐标边界（取景用；刻度/标签是真实值）
  az: -55, el: 26, fov: 35                        // 相机；dist 不给就按边界自动取景
});
sc.attachOrbit({onChange: draw});                 // 拖拽转、滚轮缩；松手/滚完回调你的重画函数

// 2) 重画 = 清空 → 摆图元 → render()。相机变化只重投影，不重算你的数据
function draw() {
  sc.clear();
  sc.surface({x: XS, y: YS, z: ZS, cmap: 'viridis', cmin: 0, cmax: 1});
  sc.marker([xNow, yNow, zNow], {drop: true, label: '当前 ' + Scene3D.fmt(zNow)});
  sc.axes({labels: ['x', 'y', '响应']});
  sc.colorbar({label: '|X| (mm)', cmin: 0, cmax: 1});
  sc.triad();
  sc.render();
}
```

## API

### 场景
| 调用 | 说明 |
|---|---|
| `Scene3D.create(canvas, opts)` | `opts`: `bounds`（数字 / `{x,y,z}` / `{lo,hi}`）、`az` `el` `dist` `fov`、`scale`、`light`、`maxQuads`（默认 5000）。`canvas` 只要有 `width/height/getContext('2d')`（所以 node 桩也能跑） |
| `scene.clear()` | 清空显示表（每次重画第一步） |
| `scene.render()` | 投影 → 深度排序 → 落笔 → HUD；返回 stats |
| `scene.project([x,y,z])` | 世界坐标 → 画布像素 `{x,y,d}`；不可见/非有限返回 `null` |
| `scene.stats()` | 最近一次 render 的 `{quads, segs, dots, texts, skipped, stride, items, drawn, hud}` —— 自检与 DEMO_REPORT 的网格数从这里来 |
| `scene.setCamera({az, el, dist})` | `el` 自动夹到 ±88；`dist: null` 恢复自动取景 |
| `scene.camera()` | 读回 `{az, el, dist}` —— 写 URL hash 深链用它 |
| `scene.setScale({z: 200})` | 各向异性**显示**缩放（见下"不许说谎"一条） |
| `scene.attachOrbit({onChange})` | 拖拽/滚轮/触摸交互；`onChange` 里做重画 + 写 hash |

### 图元（都追加进当前帧，`render()` 统排深度）
| 调用 | 说明 |
|---|---|
| `scene.surface({x, y, z, grid, cmap, cmin, cmax, shade, wire, alpha})` | `z` 是二维数组——rect：`z[i][j]`（i 沿 x、j 沿 y，**行=x 列=y，别转置**）；`grid:'polar'`：`x` 给半径 `r[nr]`、`y` 给辐角 `th[nth]`（弧度）、`z[j][i]`（j 沿 th、i 沿 r），顶点落在 `(r·cosθ, r·sinθ)`。圆膜/圆盘/极坐标场必须用 polar，方网格凑圆会在圆边出锯齿。也可传 `z` 为函数 `f(x,y)`。超过 `maxQuads` 自动跨步降采样（stats.stride 可见） |
| `scene.points(ps, {color, size})` | `ps` 每项 `[x,y,z]` 或 `{p, color, size}`；坏点跳过并计数 |
| `scene.polyline(ps, {color, lw, dash})` | **逐段**进深度排序——光束从曲面背后穿到前面才会正确穿插 |
| `scene.axes({labels, ticks, color, labelEvery})` | 三轴 + 刻度短线 + 数值标签（标签走 HUD 层，永远可读；写的是真实数据值） |
| `scene.marker(p, {color, size, drop, label})` | 当前状态指示：亮点 + 可选竖直虚线读数线 + 标签 |
| `scene.colorbar({label, cmap, cmin, cmax, x, y, w, h})` | 色标（条带 + 两端数值 + 标签）——曲面没有它读不出数 |
| `scene.triad({x, y, size})` | 角标三叉（"现在 x/y/z 朝哪"的小罗盘） |
| `scene.text2d(x, y, s, {color, font, align})` | 画布坐标文字（HUD 层，永远压最上层） |

内置色阶：`viridis` `plasma` `coolwarm`（发散量用它，中点为中性色）`gray`；页面可自加：
`Scene3D.cmaps.名称 = [[r,g,b],…]`。`Scene3D.fmt(v)` 是统一的数字格式化。

## 四条纪律（写 demo 时照着做）

1. **数据真实**：曲面上的每个点要么来自 `results/*.json`、要么按论文模型在**前端现算**
   （见下两节）。NaN/Inf 不许当 0 画 —— 引擎会跳过并计入 `stats.skipped`，自检里盯住它。
2. **bounds 给一次就粘住**：跨参数档、跨时间帧都不要重设 bounds（自动取景会把振幅变化
   归一化成"没变化"，两张截图也不可比）。要看振幅变化，就让同一套 bounds 里的面真的鼓起来。
3. **不许说谎（各向异性缩放）**：膜半径 3 cm、位移 µm 这类量级差，按真实比例画就是一张平板。
   用 `setScale({z: 200})` 放大**显示**，但刻度/色标/标签全是真实值，且 render 会自动在
   左上角写一行"视觉放大 ×200（刻度为真实值）"——这条注记去不掉。把放大量藏起来，
   就是把显示当数据。
4. **时间由你传进来**：引擎没有时钟（不读 Date / 不用随机数），同一个 URL hash 永远截出
   同一张图。动画归你驱动（`requestAnimationFrame` 在你手里，**首帧要同步先画一次** ——
   无头截图可能拍到 rAF 之前的空白画布）。命中 `prefers-reduced-motion: reduce` 时默认暂停。

## 两种计算架构怎么接数据（对应 SKILL 的 A/B）

**A. 前端重算（公式简单时）**——每帧按当前参数重算 z 矩阵再 surface：
```js
function zAt(r, th) { return Math.sin(2*th) * Math.cos(k(r)); }   // 论文里的模型，原样搬
function rebuild() {
  ZS = TH.map(th => RS.map(r => zAt(r, th)));      // polar：z[j][i]，j 沿 th
}
```
**B. 预计算查表（公式复杂时）**——python 算好一组网格内联成 JS 数据块，前端查表 + 线性
插值（插值方法与误差写进 DEMO_REPORT）。**不许**把逐帧动画帧预计算内联（那是 +MB 级）；
与时间/参数无关的部分预计算一次（模态形状、径向剖面、系数表），帧内只做加权求和。

## 性能预算

- 每帧四边形 ≤ 5000（`maxQuads` 默认值；超了引擎自动降采样并在 `stats.stride` 里如实标注）。
  动画（每帧重算+重画）建议 40×40 左右；滑杆式静态视图可以到 80×80。
- 拖动/滚轮只重投影（引擎只做这个）；**参数变化才重建数据**——把贵的那部分缓存在闭包里。
- 点云多的时候优先 `points` 一次给完（引擎一次遍历），别开几十个 `points()` 调用。
- 不够流畅时的降格顺序：先减网格 → 再关网格线（`wire:false`）→ 最后冻结动画。**不许静默掉帧**；
  实测帧时间写进 DEMO_REPORT。

## URL hash 深链（截图与分享共用一条路）

相机与状态都进 hash，用户转完相机松手时 `syncHash()`（挂在 `attachOrbit` 的 `onChange` 里）：

```js
// 建议命名（在既有 v=/f=/th=/t= 风格上扩展）
//   &az=-55&el=26&dist=1.4   相机
//   &t=0.30&play=0           时间定格/播放
function curHash() {
  var c = sc.camera();
  return '#az=' + c.az.toFixed(1) + '&el=' + c.el.toFixed(1) +
         (c.dist == null ? '' : '&dist=' + c.dist.toFixed(3)) +
         '&t=' + T.toFixed(3) + '&play=' + (PLAYING ? 1 : 0);
}
```
无头截图流程：`msedge --headless=new --disable-gpu --window-size=1400,900
--screenshot=demo/shot_2_rotated.png "file:///…/demo/demo.html#az=40&el=18&t=0.30&play=0"`
—— 先定格（`play=0` + 固定 `t`）、再截，两张截图的差异才是**可复现**的。

## 已知边界（诚实清单）

- 画家算法对**互相穿插**的大四边形会画错（z-buffer 才根治）。缓解：网格别太粗
  （默认 37 格量级起），穿插明显的场景把网格加密。
- 光照是世界坐标固定光；相机转到背面时明暗会变（两面都取 |cos|，不会全黑）。
- 色阶是近似采样，与 matplotlib 同名色阶观感一致但**不逐位相同**；论文里的正式图仍由
  matplotlib 出，本引擎服务交互 demo。
- `el` 夹在 ±88：极点附近 up 向量退化，再上去会出现翻转抖动的观感问题（不是 NaN）。
