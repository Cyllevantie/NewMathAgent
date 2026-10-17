// 把 skills/16Web-demo/assets/scene3d.js 用**桩 canvas** 真跑一遍。
// 为什么要有它：三维渲染最容易"看起来没事、其实错了"的四类毛病 —— 投影算错（图还在，只是
// 不对）、深度排反（前后穿帮，静态截图看不出来）、色阶/文字通道错（文字被排进深度表里，
// 顺序未定义）、退化输入出 NaN（某个参数档才出现，滑块拖过去就没了）。纯字符串哨兵一条都
// 抓不住，桩画布真跑是**没有浏览器时能拿到的最硬证据**（同 frontend_render_check.js 的路子）。
// 每条断言都配对照组：要么反控（换个相机/换个数据，结论必须翻转），要么正控（先证明这条
// 判据真的有可能变红，防"恒真断言"）。
//
// 判据来自命令输出：node regression/demo3d_check.js，rc≠0 即红。
const fs = require('fs');
const path = require('path');

const ROOT = path.join(__dirname, '..');
const SRC = fs.readFileSync(path.join(ROOT, 'skills', '16Web-demo', 'assets', 'scene3d.js'), 'utf8');
const DOC = fs.readFileSync(path.join(ROOT, 'skills', '16Web-demo', 'references', 'scene3d.md'), 'utf8');

let bad = 0;
function ck(cond, msg) {
  console.log((cond ? '✓' : '✗') + ' ' + msg);
  if (!cond) bad++;
}

// ---------------- 桩画布：**连属性赋值也要记** ----------------
// ctx.lineWidth = NaN 不会抛、也不报错，图会静默画不出来 —— 只查方法参数会漏掉这一类。
function stubCanvas(w, h) {
  const ops = [];
  const props = {};
  const ctx = {
    canvas: {width: w, height: h},
    beginPath() { ops.push(['call', 'beginPath']); },
    moveTo(x, y) { ops.push(['call', 'moveTo', x, y]); },
    lineTo(x, y) { ops.push(['call', 'lineTo', x, y]); },
    closePath() { ops.push(['call', 'closePath']); },
    arc(x, y, r, a0, a1) { ops.push(['call', 'arc', x, y, r, a0, a1]); },
    fill() { ops.push(['call', 'fill']); },
    stroke() { ops.push(['call', 'stroke']); },
    fillRect(x, y, w2, h2) { ops.push(['call', 'fillRect', x, y, w2, h2]); },
    strokeRect(x, y, w2, h2) { ops.push(['call', 'strokeRect', x, y, w2, h2]); },
    fillText(s, x, y) { ops.push(['call', 'fillText', String(s), x, y]); },
    strokeText(s, x, y) { ops.push(['call', 'strokeText', String(s), x, y]); },
    setLineDash(d) { ops.push(['call', 'setLineDash', JSON.stringify(d)]); },
    save() { ops.push(['call', 'save']); },
    restore() { ops.push(['call', 'restore']); },
  };
  for (const p of ['fillStyle', 'strokeStyle', 'lineWidth', 'font', 'textAlign',
                   'textBaseline', 'lineCap', 'lineJoin', 'globalAlpha']) {
    Object.defineProperty(ctx, p, {
      get: () => props[p],
      set: (v) => { props[p] = v; ops.push(['set', p, v]); },
    });
  }
  const canvas = {width: w, height: h, style: {}, getContext: () => ctx,
                  addEventListener() {}, setPointerCapture() {}};
  return {canvas, ctx, ops};
}

// 从 op 里还原"每次 fill 时用的颜色 / 每次 fillText 的内容"，以及首个/末个位置。
function fills(ops) {
  const out = [];
  let cur = null;
  for (const op of ops) {
    if (op[0] === 'set' && op[1] === 'fillStyle') cur = op[2];
    if (op[0] === 'call' && op[1] === 'fill') out.push({color: cur, i: out.length});
  }
  return out;
}
function texts(ops) {
  return ops.filter((o) => o[0] === 'call' && o[1] === 'fillText').map((o) => o[2]);
}
function firstIndex(ops, pred) { return ops.findIndex(pred); }
function lastIndex(ops, pred) {
  for (let i = ops.length - 1; i >= 0; i--) if (pred(ops[i])) return i;
  return -1;
}
function allFinite(ops) {
  for (const op of ops) {
    for (let i = 1; i < op.length; i++) {
      if (typeof op[i] === 'number' && !Number.isFinite(op[i])) return false;
    }
    if (op[0] === 'set' && typeof op[2] === 'number' && !Number.isFinite(op[2])) return false;
  }
  return true;
}

// 桩里也需要 Promise 之外的全局不碰：引擎不该在加载时碰 document/window。
const S3 = new Function(SRC + '\n;return Scene3D;')();

function lin(a, b, n) {
  const out = [];
  for (let i = 0; i < n; i++) out.push(a + (b - a) * i / (n - 1));
  return out;
}
function grid(xs, ys, fn) { return xs.map((x) => ys.map((y) => fn(x, y))); }

// ---------------- A. 资产卫生：自包含 + 确定性 + 内联安全 ----------------
ck(typeof S3.version === 'string' && S3.version.length > 0, 'A1 资产可加载，Scene3D.version 是字符串（' + S3.version + '）');
ck(Array.isArray(S3.cmaps.viridis) && S3.cmaps.viridis.length >= 2, 'A1b 内置色阶在（viridis 控制点数 ' + S3.cmaps.viridis.length + '）');

const BAD_SUB = [[/<\/?script/i, 'HTML script 标签字样'], [/<!--/, 'HTML 注释起头'],
                 [/https?:\/\//, '裸 URL'], [/\bfetch\s*\(/, 'fetch('], [/\brequire\s*\(/, 'require('],
                 [/XMLHttpRequest/, 'XMLHttpRequest'], [/\bimport\s/, 'import 语句']];
{
  const hits = BAD_SUB.filter(([re]) => re.test(SRC)).map(([, n]) => n);
  ck(hits.length === 0, 'A2 引擎源码不含外联/内联危险字样' + (hits.length ? '：' + hits.join('、') : ''));
  // 正控：正则不是死的 —— 喂一条诱饵必须抓到（防"什么都匹配不到"也算过）
  const bait = '<' + '/script' + '> 与 https://cdn.example/x.js 与 fetch(';
  ck(BAD_SUB.some(([re]) => re.test(bait)), 'A2c 正控：诱饵串能被这套正则抓到（判据不是恒真）');
}
{
  const hits = [/Date\.now/, /Math\.random/, /new\s+Date/, /performance\.now/,
                /requestAnimationFrame/, /setTimeout/, /setInterval/].filter((re) => re.test(SRC));
  ck(hits.length === 0, 'A3 引擎不取时钟、不用随机数（截图可复现的根）' + (hits.length ? '：' + hits.join('、') : ''));
}

// ---------------- B. 投影：手算定点 ----------------
// 手算推导（与引擎代码相互独立）：W=800,H=600, fov=35°, bounds=±1, dist=10, az=0, el=0
//   focal = (600/2)/tan(17.5°) = 300/0.3152987759 ≈ 951.4785；k = focal/dist ≈ 95.14785 px/单位
//   az=0 ⇒ 眼在 +x，右向量 = +y，上向量 = +z
//   [0,1,0] ⇒ 中心右移 95.148px；[0,0,1] ⇒ 中心上移 95.148px
//   az=90 ⇒ 眼在 +y，右向量 = −x ⇒ [1,0,0] 左移 95.148px（同一世界点两次差约 190px）
const FOCAL_K = 95.14785;
function mkScene(opts) {
  const st = stubCanvas(800, 600);
  const sc = S3.create(st.canvas, Object.assign({bounds: 1, az: 0, el: 0, dist: 10, fov: 35}, opts || {}));
  return {sc, ops: st.ops, canvas: st.canvas};
}
function near(a, b, tol) { return Math.abs(a - b) <= (tol == null ? 0.02 : tol); }
{
  const {sc} = mkScene();
  const c = sc.project([0, 0, 0]);
  ck(c && near(c.x, 400, 1e-6) && near(c.y, 300, 1e-6), 'B1 目标点投到画布中心（±1e-6）');
  const py = sc.project([0, 1, 0]), pz = sc.project([0, 0, 1]);
  ck(near(py.x, 400 + FOCAL_K) && near(py.y, 300), '+y 方向投到中心右侧 95.148px（实测 ' + py.x.toFixed(3) + '）');
  ck(near(pz.x, 400) && near(pz.y, 300 - FOCAL_K), '+z 方向投到中心上方 95.148px（实测 ' + pz.y.toFixed(3) + '）');
  sc.setCamera({az: 90});
  const px = sc.project([1, 0, 0]);
  ck(near(px.x, 400 - FOCAL_K) && near(px.y, 300), 'B4 转 90° 后 +x 点移到中心左侧 95.148px（实测 ' + px.x.toFixed(3) + '）');
  ck(Math.abs(px.x - py.x) > 150, 'B4c 对照组：同一世界点在两个方位角下横坐标差 >150px（投影真的随相机变）');
}
{
  const {sc} = mkScene();
  sc.setCamera({az: 45}); const a45 = sc.project([0.3, -0.4, 0.5]);
  sc.setCamera({az: 405}); const a405 = sc.project([0.3, -0.4, 0.5]);
  ck(near(a45.x, a405.x, 1e-6) && near(a45.y, a405.y, 1e-6), 'B5 az+360° 投影逐位一致（角度不漂）');
}
{
  const {sc} = mkScene();
  const angles = [89.9, -89.9, 1e9, -1e9];
  let ok = true, clamped = null;
  for (const el of angles) {
    sc.setCamera({el: el});
    clamped = sc.camera().el;
    const p = sc.project([0.2, 0.3, 0.9]);
    if (!p || !Number.isFinite(p.x) || !Number.isFinite(p.y) || !Number.isFinite(p.d)) ok = false;
  }
  ck(ok, 'B6 俯仰角到 ±90° 之外（含 1e9）不抛错、投影保持有限');
  ck(Math.abs(sc.camera().el) <= 88, 'B6b 仰角被夹在 ±88（极点上 up 向量与视线共线，叉积会退化）');
  sc.setCamera({dist: 0.01});
  const p2 = sc.project([0, 0, 0]);
  ck(Number.isFinite(p2.x) && Number.isFinite(p2.y), 'B6c 视距极小不产生 NaN');
}

// ---------------- C. 深度排序（画家算法）与控制组 ----------------
{
  const st = stubCanvas(800, 600);
  const sc = S3.create(st.canvas, {bounds: 1, az: 0, el: 0, dist: 10});
  sc.points([[1, 0, 0]], {color: '#ff0000'});
  sc.points([[-1, 0, 0]], {color: '#00ff00'});
  sc.render();
  const fl = fills(st.ops);
  const red = fl.findIndex((f) => f.color === '#ff0000');
  const green = fl.findIndex((f) => f.color === '#00ff00');
  ck(green >= 0 && red >= 0 && green < red, 'C1 远点先画、近点后画（az=0 时 −x 远）');
  st.ops.length = 0;
  sc.setCamera({az: 180});
  sc.render();
  const fl2 = fills(st.ops);
  const red2 = fl2.findIndex((f) => f.color === '#ff0000');
  const green2 = fl2.findIndex((f) => f.color === '#00ff00');
  ck(red2 >= 0 && green2 >= 0 && red2 < green2, 'C1c 对照组：转 180° 后顺序翻转（不是贴死插入顺序）');
}
{
  // 混合类型：一个点在曲面之上/之下，画的先后必须跟着换
  const xs = lin(-1, 1, 5), ys = lin(-1, 1, 5);
  const zs = grid(xs, ys, () => 0);
  function run(pt) {
    const st = stubCanvas(800, 600);
    const sc = S3.create(st.canvas, {bounds: 1, az: -90, el: 60, dist: 10});
    sc.surface({x: xs, y: ys, z: zs});
    sc.points([pt], {color: '#ff0000', size: 5});
    sc.render();
    const fl = fills(st.ops);
    return {dot: fl.findIndex((f) => f.color === '#ff0000'), quad: fl.findIndex((f) => /^rgb\(/.test(String(f.color)))};
  }
  const above = run([0, 0, 0.5]);
  ck(above.quad >= 0 && above.dot > above.quad, 'C2 曲面之上的点画在曲面之后（盖在上面）');
  const below = run([0, 0, -0.5]);
  ck(below.quad >= 0 && below.dot >= 0 && below.dot < below.quad, 'C2c 对照组：点移到曲面之下，先后关系翻转（真是按深度排的）');
}

// ---------------- D. 网格预算 / 退化输入 ----------------
{
  const st = stubCanvas(800, 600);
  const sc = S3.create(st.canvas, {bounds: 1});
  const xs = lin(-1, 1, 5), ys = lin(-1, 1, 5);
  sc.surface({x: xs, y: ys, z: grid(xs, ys, (x, y) => x + y)});
  const s1 = sc.render();
  ck(s1.quads === 16, 'D1 5×5 网格恰好 16 片（' + s1.quads + '）');
  ck(s1.skipped === 0, 'D1b 干净网格 skipped=0（正控：坏网格那条判据才有意义）');
}
{
  const st = stubCanvas(800, 600);
  const sc = S3.create(st.canvas, {bounds: 1, maxQuads: 1000});
  const xs = lin(-1, 1, 201), ys = lin(-1, 1, 201);
  st.ops.length = 0;
  const s = sc.render.call(sc.clear().surface({x: xs, y: ys, z: grid(xs, ys, (x, y) => x * y)}));
  ck(s.quads <= 1000 && s.quads > 0, 'D2 201×201 网格被跨步降采样进预算（' + s.quads + ' ≤ 1000）');
  ck(s.stride > 1, 'D2b stride>1（' + s.stride + '）');
  ck(fills(st.ops).length === s.quads, 'D2c 实际落笔的四边形数 = stats.quads（统计不撒谎）');
}
{
  const st = stubCanvas(800, 600);
  const sc = S3.create(st.canvas, {bounds: 1});
  const xs = lin(-1, 1, 6), ys = lin(-1, 1, 6);
  const zs = grid(xs, ys, () => 1);
  zs[2][2] = NaN;
  sc.surface({x: xs, y: ys, z: zs});
  const s = sc.render();
  ck(s.quads === 21 && s.skipped >= 1, 'D3 一个 NaN 顶点吃掉相邻 4 片、其余照画（quads=' + s.quads + '，skipped=' + s.skipped + '）');
  ck(allFinite(st.ops), 'D3b NaN 没有传播进任何画布调用（宁少画，不画坏）');
}
{
  const st = stubCanvas(800, 600);
  const sc = S3.create(st.canvas, {bounds: 1});
  const xs = lin(-1, 1, 5), ys = lin(-1, 1, 5);
  sc.surface({x: xs, y: ys, z: grid(xs, ys, () => 3.14)});   // 常值平面：法向叉积为 0
  const s = sc.render();
  ck(s.quads === 16 && allFinite(st.ops), 'D4 常值平面（法向退化）不产生 NaN');
}
{
  // 极坐标网格（圆膜）：r=0 处顶点全塌到圆心，是退化四边形的高发区
  const st = stubCanvas(800, 600);
  const sc = S3.create(st.canvas, {bounds: {x: [-1, 1], y: [-1, 1], z: [-1, 1]}});
  const r = [0, 0.5, 1], th = [0, Math.PI / 2, Math.PI, 3 * Math.PI / 2];
  const zs = th.map(() => r.map(() => 0.3));
  sc.surface({grid: 'polar', x: r, y: th, z: zs});
  const s = sc.render();
  ck(s.quads === 6, 'D5 极坐标网格 3×4 出 6 片（' + s.quads + '）');
  ck(allFinite(st.ops), 'D5b 圆心退化四边形不产生 NaN');
}
{
  const st = stubCanvas(800, 600);
  const sc = S3.create(st.canvas, {bounds: 1});
  sc.points([[0, 0, 0], [NaN, 0, 0], [0, Infinity, 0], [0.5, 0.5, 0.5]]);
  const s = sc.render();
  ck(s.dots === 2 && s.skipped === 2, 'D6 坏点被跳过并计数（dots=' + s.dots + '，skipped=' + s.skipped + '）');
  ck(allFinite(st.ops), 'D6b 坏点没到画布');
}

// ---------------- E. 通道与注记（文字必须在 3D 之后；放大量必须自曝） ----------------
{
  // 这条钉的是"文字被排进深度表"那个坑：text2d **先**入表，落笔仍必须在所有 3D 图元之后
  const st = stubCanvas(800, 600);
  const sc = S3.create(st.canvas, {bounds: 1, az: -60, el: 26});
  const xs = lin(-1, 1, 4), ys = lin(-1, 1, 4);
  sc.text2d(10, 10, '先入表的 HUD 文字');
  sc.surface({x: xs, y: ys, z: grid(xs, ys, (x, y) => x + y)});
  sc.marker([0, 0, 0.2], {label: 'm'});
  sc.axes({labels: ['x', 'y', 'z']});
  sc.render();
  const lastFill = lastIndex(st.ops, (o) => o[0] === 'call' && o[1] === 'fill');
  const firstText = firstIndex(st.ops, (o) => o[0] === 'call' && o[1] === 'fillText');
  ck(lastFill >= 0 && firstText > lastFill, 'E1 HUD 文字全部落在 3D 通道之后（先入表也不例外）');
}
{
  const st = stubCanvas(800, 600);
  const sc = S3.create(st.canvas, {bounds: {x: [0, 1], y: [0, 1], z: [0, 100]}});
  sc.setScale({z: 2});
  sc.axes({labels: ['x', 'y', 'z']});
  sc.colorbar({label: '响应', cmin: 0, cmax: 100});
  sc.render();
  const tx = texts(st.ops);
  ck(tx.some((s) => String(s).indexOf('视觉放大') >= 0 && String(s).indexOf('×2') >= 0),
     'E2 各向异性缩放自动落"视觉放大 ×2"注记（藏起来就是把显示当数据）');
  ck(tx.indexOf('100') >= 0, 'E2b 刻度写的仍是真实值 100（不是放大后的 200）');
  ck(tx.indexOf('响应') >= 0, 'E2c 色标带着标签与数值刻度（没有数值可读的色标等于没画）');
  ck(st.ops.filter((o) => o[0] === 'call' && o[1] === 'fillRect').length >= 40, 'E2d 色标有条带（fillRect 计数）');
  // 对照组：scale 全 1 时不许出现注记
  const st2 = stubCanvas(800, 600);
  const sc2 = S3.create(st2.canvas, {bounds: 1});
  sc2.setScale({x: 1, y: 1, z: 1});
  sc2.render();
  ck(!texts(st2.ops).some((s) => String(s).indexOf('视觉放大') >= 0), 'E2e 对照组：无缩放时没有这条注记');
}

// ---------------- F. 确定性：同相机连画两次逐位一致 ----------------
{
  const st = stubCanvas(800, 600);
  const sc = S3.create(st.canvas, {bounds: 1, az: -60, el: 26});
  const xs = lin(-1, 1, 7), ys = lin(-1, 1, 7);
  function draw() {
    sc.clear();
    sc.surface({x: xs, y: ys, z: grid(xs, ys, (x, y) => Math.sin(2 * x) * Math.cos(2 * y))});
    sc.axes({labels: ['x', 'y', 'z']});
    sc.triad();
    sc.render();
  }
  st.ops.length = 0;
  draw();
  const once = JSON.stringify(st.ops);
  const n1 = st.ops.length;
  st.ops.length = 0;
  draw();
  const twice = JSON.stringify(st.ops);
  ck(n1 > 300, 'F1 前置：真的画了东西（' + n1 + ' 个画布操作，防"两次都空"也算过）');
  ck(once === twice, 'F1b 同相机连画两次，画布操作序列逐位一致');
  ck(st.canvas.width === 800 && st.canvas.height === 600, 'F1c 引擎从不改写 canvas 的尺寸（backing store 幂等）');
  st.ops.length = 0;
  sc.setCamera({az: 40});
  draw();
  ck(JSON.stringify(st.ops) !== once, 'F1d 对照组：改相机后画面必须不同');
}

// ---------------- G. 文档 ↔ 代码 API 一致（防文档漂移） ----------------
{
  const REQUIRED = ['clear', 'surface', 'points', 'polyline', 'axes', 'marker', 'text2d',
                    'colorbar', 'triad', 'render', 'setCamera', 'camera', 'setScale',
                    'attachOrbit', 'project', 'stats'];
  const st = stubCanvas(10, 10);
  const sc = S3.create(st.canvas, {bounds: 1});
  const missingCode = REQUIRED.filter((n) => typeof sc[n] !== 'function');
  ck(missingCode.length === 0, 'G1 引擎实现了全部约定 API' + (missingCode.length ? '：缺 ' + missingCode.join('、') : ''));
  const missingDoc = REQUIRED.filter((n) => DOC.indexOf('scene.' + n) < 0);
  ck(missingDoc.length === 0, 'G2 references/scene3d.md 逐个写了这些 API' + (missingDoc.length ? '：缺 ' + missingDoc.join('、') : ''));
  const documented = Array.from(new Set((DOC.match(/scene\.(\w+)\(/g) || [])
    .map((m) => m.slice(6, -1))));
  const ghost = documented.filter((n) => REQUIRED.indexOf(n) < 0);
  ck(ghost.length === 0 && documented.length >= 10,
     'G3 文档里提到的 API 都在清单内（文档提了 ' + documented.length + ' 个' + (ghost.length ? '，越界 ' + ghost.join('、') : '') + '）');
  ck(DOC.indexOf(S3.version) >= 0, 'G4 文档标着与资产一致的版本号（' + S3.version + '）—— 改引擎忘改文档这条会红');
}

console.log(bad ? ('★ ' + bad + ' 例不通过') : '全部通过（投影/深度/预算/退化/通道/确定性/文档一致）');
process.exit(bad ? 1 : 0);
