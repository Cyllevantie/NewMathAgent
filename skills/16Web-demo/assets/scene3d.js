/*! scene3d v1 — 16Web-demo 内联三维内核（源文件 skills/16Web-demo/assets/scene3d.js）
 *
 * 为什么存在这个文件：⑯ 的交付件是一个**离线单文件** `demo/demo.html`（交付检查机械拒绝
 * 一切外链引用），而"数据驱动的动态三维模型"是本阶段主视图的默认形态。引 Three.js 这类库
 * 不划算（~600 KB 量级、ESM 不好整段内联），WebGL 在无头截图（msedge --headless
 * --disable-gpu，SKILL 第 5 步就是它）下也不保证；Canvas 2D 自绘与这个仓库既有 demo
 * 同一条路：零依赖、可回归、截图稳。
 *
 * 怎么用：把本文件**整段原文**原样复制进 demo.html 的 script 块里 —— 一个字符都不改。
 *   delivery 的 demo_3d_issues 会拿这个文件的整段原文在 demo.html 里做包含比对；
 *   改引擎请改**本文件**再重跑 ⑯，不要在产物里就地改（改了过不了交付检查）。
 * 用法速查与两种计算架构的接数据示范：skills/16Web-demo/references/scene3d.md。
 *
 * 确定性契约（回归夹具 regression/demo3d_check.js 按它钉）：本文件不读系统时钟、
 * 不用随机数，也不在加载时碰 document / window ——
 * 时间由调用方传入（动画归调用方驱动），所以同一个 URL hash 永远截出同一张图。
 * 另外：本文件里不出现任何 HTML 标签字面量（尖括号的 script/link 之类）——
 * 整段内联进 HTML 时那类文本会撞上解析器与交付检查。
 *
 * 坐标系：世界坐标 x/y/z，z 向上（数学模型的响应轴通常是 z）。相机是球坐标轨道式：
 * az（绕 z 轴方位角，度）、el（仰角，度，±88 夹紧 —— 再往上去 up 向量与视线共线，
 * 叉积退化）、dist（到中心距离，不给就按边界自动取景，边界不变则取景不变）。
 * 透视投影，fov 是竖直视场角。
 */
var Scene3D = (function () {
  'use strict';

  // ---------------- 小工具 ----------------
  function _fin(v) { return typeof v === 'number' && isFinite(v); }
  function _clamp(v, a, b) { return v < a ? a : (v > b ? b : v); }
  function _lerp(a, b, t) { return a + (b - a) * t; }
  function _dot(a, b) { return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]; }
  function _cross(a, b) {
    return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];
  }
  function _norm3(a) {
    var n = Math.sqrt(a[0] * a[0] + a[1] * a[1] + a[2] * a[2]) || 1;
    return [a[0] / n, a[1] / n, a[2] / n];
  }
  function _fmt(v) {
    if (!_fin(v)) return '';
    var a = Math.abs(v);
    if (a !== 0 && (a >= 1e4 || a < 1e-3)) return v.toExponential(1).replace('e+', 'e');
    var s = a >= 100 ? v.toFixed(0) : (a >= 10 ? v.toFixed(1) : v.toFixed(2));
    if (s.indexOf('.') >= 0) s = s.replace(/0+$/, '').replace(/\.$/, '');
    return s;
  }

  // ---------------- 色映射 ----------------
  // 控制点 + 分段线性。viridis/plasma/coolwarm 是常识配色方案的近似采样：不追求与
  // matplotlib 逐位一致，只保住两件可读性底线 —— ①亮度单调（低/高一眼分得开；
  // 色阶方向反了是最难发现的一类错：温度场用 viridis 会让冷=亮黄、热=暗紫）；
  // ②coolwarm 中点为中性色（发散量——偏差/正负——靠它）。
  var CMAPS = {
    viridis: [[68, 1, 84], [72, 40, 120], [62, 74, 137], [49, 104, 142], [38, 130, 142],
              [31, 158, 137], [53, 183, 121], [109, 205, 89], [180, 222, 44], [253, 231, 37]],
    plasma: [[13, 8, 135], [75, 3, 161], [125, 3, 168], [168, 34, 150], [203, 70, 121],
             [229, 107, 93], [248, 148, 65], [253, 195, 40], [240, 249, 33]],
    coolwarm: [[59, 76, 192], [98, 130, 234], [141, 176, 254], [184, 208, 249], [221, 221, 221],
               [245, 196, 173], [244, 154, 123], [222, 96, 77], [180, 4, 38]],
    gray: [[28, 28, 28], [242, 242, 242]]
  };
  function _stops(name) { return CMAPS[name] || CMAPS.viridis; }
  function _rgbAt(stops, t) {
    t = _clamp(_fin(t) ? t : 0, 0, 1) * (stops.length - 1);
    var i = Math.min(stops.length - 2, Math.floor(t)), f = t - i;
    var a = stops[i], b = stops[i + 1];
    return [_lerp(a[0], b[0], f), _lerp(a[1], b[1], f), _lerp(a[2], b[2], f)];
  }
  function _css(rgb, alpha) {
    var r = Math.round(_clamp(rgb[0], 0, 255)), g = Math.round(_clamp(rgb[1], 0, 255)),
        b = Math.round(_clamp(rgb[2], 0, 255));
    if (alpha == null || alpha >= 1) return 'rgb(' + r + ',' + g + ',' + b + ')';
    return 'rgba(' + r + ',' + g + ',' + b + ',' + _clamp(alpha, 0, 1) + ')';
  }
  function _asColor(c) { return Array.isArray(c) ? _css(c) : c; }
  var _FONT = '12px system-ui, "Segoe UI", "Microsoft YaHei", sans-serif';

  // ---------------- 边界 / 缩放 / 取景 ----------------
  // bounds 支持三种写法：数字（±b 的立方）、{x:[a,b],y:[..],z:[..]}、{lo:[..],hi:[..]}。
  function _bounds(b) {
    if (_fin(b)) return {lo: [-b, -b, -b], hi: [b, b, b]};
    if (b && b.lo && b.hi) return {lo: b.lo.slice(), hi: b.hi.slice()};
    if (b && b.x && b.y && b.z) return {lo: [b.x[0], b.y[0], b.z[0]], hi: [b.x[1], b.y[1], b.z[1]]};
    return {lo: [-1, -1, -1], hi: [1, 1, 1]};
  }
  // 显示空间的中点与半径：scale 只作用于**显示几何**，不作用于刻度值（见 setScale）。
  function _mid(S) {
    return [(S.bounds.lo[0] + S.bounds.hi[0]) / 2 * S.scale[0],
            (S.bounds.lo[1] + S.bounds.hi[1]) / 2 * S.scale[1],
            (S.bounds.lo[2] + S.bounds.hi[2]) / 2 * S.scale[2]];
  }
  function _autoDist(S) {
    var d = [(S.bounds.hi[0] - S.bounds.lo[0]) * S.scale[0],
             (S.bounds.hi[1] - S.bounds.lo[1]) * S.scale[1],
             (S.bounds.hi[2] - S.bounds.lo[2]) * S.scale[2]];
    var r = Math.max(1e-9, 0.5 * Math.sqrt(d[0] * d[0] + d[1] * d[1] + d[2] * d[2]));
    return r / Math.sin(S.fov * Math.PI / 360) * 1.12;
  }
  // 相机基向量每帧现算（代价微不足道），拖拽/滚轮改完直接 render 就生效。
  function _basis(S) {
    var el = _clamp(S.el, -88, 88) * Math.PI / 180;
    var az = S.az * Math.PI / 180;
    var dir = [Math.cos(el) * Math.cos(az), Math.cos(el) * Math.sin(az), Math.sin(el)];
    var c = _mid(S);
    var dist = _fin(S.dist) ? S.dist : _autoDist(S);
    var eye = [c[0] + dir[0] * dist, c[1] + dir[1] * dist, c[2] + dir[2] * dist];
    var f = [-dir[0], -dir[1], -dir[2]];              // 眼 → 中心（视线正方向）
    var r = _norm3(_cross(f, [0, 0, 1]));             // 屏幕右向量
    var u = _cross(r, f);                             // 屏幕上向量（r、f 单位正交 ⇒ u 已单位）
    return {eye: eye, f: f, r: r, u: u, dist: dist, focal: (S.H / 2) / Math.tan(S.fov * Math.PI / 360)};
  }
  // 投影。返回 {x, y, d}；点到相机后面（d 过小）或坐标非有限 ⇒ null ——
  // 调用方一律"接不到就整块跳过"，宁少画绝不画撕裂的半张脸。
  function _proj(S, B, p) {
    if (!p || !_fin(p[0]) || !_fin(p[1]) || !_fin(p[2])) return null;
    var vx = p[0] * S.scale[0] - B.eye[0],
        vy = p[1] * S.scale[1] - B.eye[1],
        vz = p[2] * S.scale[2] - B.eye[2];
    var d = vx * B.f[0] + vy * B.f[1] + vz * B.f[2];
    if (d < 1e-6) return null;
    var k = B.focal / d;
    return {x: S.W / 2 + (vx * B.r[0] + vy * B.r[1] + vz * B.r[2]) * k,
            y: S.H / 2 - (vx * B.u[0] + vy * B.u[1] + vz * B.u[2]) * k,
            d: d};
  }

  // ---------------- 画笔画手 ----------------
  // 显示表里每件东西一个类型标签（q 四边形 / seg 线段 / dot 圆点 / text / cbar / triad），
  // 全部经这一个函数落笔 —— 深度排序体与 HUD 才能走同一条绘制路径。
  function _paint(ctx, it) {
    if (it.t === 'q') {
      ctx.beginPath();
      ctx.moveTo(it.p[0].x, it.p[0].y);
      ctx.lineTo(it.p[1].x, it.p[1].y);
      ctx.lineTo(it.p[2].x, it.p[2].y);
      ctx.lineTo(it.p[3].x, it.p[3].y);
      ctx.closePath();
      ctx.fillStyle = it.c;
      ctx.fill();
      if (it.w) {
        ctx.strokeStyle = it.w;
        ctx.lineWidth = 0.6;
        ctx.stroke();
      }
    } else if (it.t === 'seg') {
      ctx.beginPath();
      ctx.moveTo(it.p0.x, it.p0.y);
      ctx.lineTo(it.p1.x, it.p1.y);
      ctx.strokeStyle = it.c;
      ctx.lineWidth = it.lw || 1.5;
      ctx.lineCap = 'round';
      if (it.dash) ctx.setLineDash(it.dash);
      ctx.stroke();
      if (it.dash) ctx.setLineDash([]);
    } else if (it.t === 'dot') {
      ctx.beginPath();
      ctx.arc(it.x, it.y, Math.max(0.5, it.r), 0, 6.283185307179586);
      ctx.fillStyle = it.c;
      ctx.fill();
      if (it.ring) {
        ctx.strokeStyle = it.ring;
        ctx.lineWidth = it.lw || 1.5;
        ctx.stroke();
      }
    } else if (it.t === 'text') {
      ctx.font = it.font || _FONT;
      ctx.textAlign = it.align || 'center';
      ctx.textBaseline = it.base || 'middle';
      if (it.halo) {
        ctx.lineWidth = 3;
        ctx.strokeStyle = it.halo;
        ctx.strokeText(it.s, it.x, it.y);
      }
      ctx.fillStyle = it.c;
      ctx.fillText(it.s, it.x, it.y);
    } else if (it.t === 'cbar') {
      var n = 48, i;
      for (i = 0; i < n; i++) {
        ctx.fillStyle = _css(_rgbAt(it.stops, 1 - i / (n - 1)));
        ctx.fillRect(it.x, it.y + it.h * i / n, it.w, it.h / n + 1);
      }
      ctx.strokeStyle = 'rgba(15,23,42,0.35)';
      ctx.lineWidth = 1;
      ctx.strokeRect(it.x, it.y, it.w, it.h);
      ctx.font = '11px system-ui, "Segoe UI", "Microsoft YaHei", sans-serif';
      ctx.textAlign = 'left';
      ctx.textBaseline = 'middle';
      ctx.fillStyle = it.c;
      ctx.fillText(_fmt(it.cmax), it.x + it.w + 4, it.y + 6);
      ctx.fillText(_fmt(it.cmin), it.x + it.w + 4, it.y + it.h - 6);
      if (it.label) {
        ctx.textAlign = 'center';
        ctx.textBaseline = 'top';
        ctx.fillText(it.label, it.x + it.w / 2, it.y + it.h + 6);
      }
    } else if (it.t === 'triad') {
      for (var j = 0; j < it.arms.length; j++) {
        var arm = it.arms[j];
        ctx.beginPath();
        ctx.moveTo(it.x, it.y);
        ctx.lineTo(arm.x, arm.y);
        ctx.strokeStyle = arm.c;
        ctx.lineWidth = 1.6;
        ctx.lineCap = 'round';
        ctx.stroke();
        ctx.font = 'bold 11px system-ui, "Segoe UI", "Microsoft YaHei", sans-serif';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillStyle = arm.c;
        ctx.fillText(arm.s, arm.lx, arm.ly);
      }
    }
  }

  // ---------------- 场景 ----------------
  function create(canvas, opts) {
    opts = opts || {};
    var S = {
      canvas: canvas,
      ctx: canvas.getContext('2d'),
      W: canvas.width || 640,                               // 逻辑尺寸只读一次，之后只认它
      H: canvas.height || 400,
      bounds: _bounds(opts.bounds == null ? 1 : opts.bounds),
      scale: (opts.scale || [1, 1, 1]).slice(),             // 各向异性显示缩放（见 setScale）
      az: _fin(opts.az) ? opts.az : -60,
      el: _fin(opts.el) ? opts.el : 26,
      dist: _fin(opts.dist) ? opts.dist : null,             // null ⇒ 每帧按边界自动取景
      fov: _fin(opts.fov) ? opts.fov : 35,                  // 竖直视场角（度）
      light: _norm3(opts.light || [0.45, -0.6, 0.75]),      // 世界坐标光源方向（会归一化）
      maxQuads: opts.maxQuads || 5000,                      // 每帧四边形预算（性能纪律的抓手）
      _items: [], _seq: 0, _stat: null
    };

    function _push(emit) { S._items.push(emit); return api; }

    // ---- 曲面：两种网格 ----
    //   rect（默认）: x[nx]、y[ny]、z[i][j]（i 沿 x、j 沿 y，行=x 列=y，别转置）
    //   polar       : x 给半径 r[nr]、y 给辐角 th[nth]（弧度）、z[j][i]（j 沿 th、i 沿 r）
    //                 —— 圆膜/圆盘/极坐标场必须用它，方网格去凑圆会在圆边出锯齿。
    // 每格拆成一个四边形，和所有其它图元统一进深度排序 —— 光路才会正确地"穿到膜后面"。
    function surface(o) {
      o = o || {};
      var xs = o.x || [], ys = o.y || [], zs = o.z;
      var f = typeof zs === 'function' ? zs : null;
      var polar = o.grid === 'polar';
      var cmapName = o.cmap || 'viridis';
      var alpha = o.alpha == null ? 1 : o.alpha;
      var wire = o.wire ? (typeof o.wire === 'string' ? o.wire : 'rgba(15,23,42,0.25)') : null;
      var shadeAmt = o.shade == null ? 0.45 : o.shade;
      function _z(i, j) {                       // i 沿第一维（rect 的 x / polar 的 r）
        if (f) return f(xs[i], ys[j]);
        if (polar) return zs[j] ? zs[j][i] : NaN;
        return zs[i] ? zs[i][j] : NaN;
      }
      function _xy(i, j) {
        if (polar) return [xs[i] * Math.cos(ys[j]), xs[i] * Math.sin(ys[j])];
        return [xs[i], ys[j]];
      }
      return _push(function (S, B, list, hud, stat) {
        var nu = xs.length, nv = ys.length, i, j;
        if (nu < 2 || nv < 2) return;
        // 顶点世界坐标 + 投影 + 有限性检查（NaN/Inf 一律丢，不许把坏点画成裂缝）
        var V = new Array(nu), P = new Array(nu), lo = Infinity, hi = -Infinity;
        for (i = 0; i < nu; i++) {
          V[i] = new Array(nv); P[i] = new Array(nv);
          for (j = 0; j < nv; j++) {
            var z = _z(i, j), xy = _xy(i, j);
            if (!_fin(z) || !_fin(xy[0]) || !_fin(xy[1])) {
              V[i][j] = null; P[i][j] = null; stat.skipped++; continue;
            }
            if (z < lo) lo = z;
            if (z > hi) hi = z;
            V[i][j] = [xy[0], xy[1], z];
            P[i][j] = _proj(S, B, V[i][j]);
          }
        }
        if (!(hi > lo)) hi = lo + 1e-9;                     // 常值曲面：色映射 span 不许为 0
        var cmin = _fin(o.cmin) ? o.cmin : lo, cmax = _fin(o.cmax) ? o.cmax : hi;
        var span = (cmax - cmin) || 1e-9;
        // 网格预算：超了按整数跨步降采样；ceil 的边缘情况会略超，循环外再守一道硬上限。
        var st = Math.max(1, Math.ceil(Math.sqrt(((nu - 1) * (nv - 1)) / Math.max(1, S.maxQuads))));
        while (Math.ceil((nu - 1) / st) * Math.ceil((nv - 1) / st) > S.maxQuads) st++;
        stat.stride = st;
        for (var i2 = 0; i2 < nu - 1; i2 += st) {
          var ix = Math.min(i2 + st, nu - 1);
          for (var j2 = 0; j2 < nv - 1; j2 += st) {
            var jy = Math.min(j2 + st, nv - 1);
            var a = P[i2][j2], b = P[ix][j2], c = P[ix][jy], d = P[i2][jy];
            if (!a || !b || !c || !d) { stat.skipped++; continue; }
            var zm = (V[i2][j2][2] + V[ix][j2][2] + V[ix][jy][2] + V[i2][jy][2]) / 4;
            var rgb = _rgbAt(_stops(cmapName), (zm - cmin) / span);
            // 兰伯特明暗：法向取"沿两边的叉积"（用真实顶点，rect/polar 通吃）；
            // 两面都可见（取 |cos|）—— 曲面转到背面看时不会变成一团纯黑。
            var e1 = [V[ix][j2][0] - V[i2][j2][0], V[ix][j2][1] - V[i2][j2][1], V[ix][j2][2] - V[i2][j2][2]];
            var e2 = [V[i2][jy][0] - V[i2][j2][0], V[i2][jy][1] - V[i2][j2][1], V[i2][jy][2] - V[i2][j2][2]];
            var nv3 = _cross(e1, e2);
            var nn = Math.sqrt(nv3[0] * nv3[0] + nv3[1] * nv3[1] + nv3[2] * nv3[2]);
            var sh = 1 - shadeAmt * 0.5;
            if (nn > 1e-12) sh = (1 - shadeAmt) + shadeAmt * Math.abs(_dot([nv3[0] / nn, nv3[1] / nn, nv3[2] / nn], S.light));
            list.push({t: 'q', d: (a.d + b.d + c.d + d.d) / 4, p: [a, b, c, d], seq: S._seq++,
                       c: _css([rgb[0] * sh, rgb[1] * sh, rgb[2] * sh], alpha), w: wire});
            stat.quads++;
          }
        }
      });
    }

    // ---- 点云：ps 里每项是 [x,y,z] 或 {p:[x,y,z], color, size} ----
    function points(ps, o) {
      o = o || {};
      return _push(function (S, B, list, hud, stat) {
        for (var i = 0; i < ps.length; i++) {
          var it = ps[i], p = Array.isArray(it) ? it : it.p;
          var a = _proj(S, B, p);
          if (!a) { stat.skipped++; continue; }
          list.push({t: 'dot', x: a.x, y: a.y, d: a.d, seq: S._seq++,
                     r: (it && !Array.isArray(it) && it.size) || o.size || 3,
                     c: _asColor((it && !Array.isArray(it) && it.color) || o.color || '#2563eb')});
          stat.dots++;
        }
      });
    }

    // ---- 折线：**逐段**进深度排序。整条线共用一个深度时，光路从曲面背后穿到前面
    //      会被整根排错（这正是 ⑯ 最常见的场景：光束穿过振动面）。----
    function polyline(ps, o) {
      o = o || {};
      var col = _asColor(o.color || '#0f172a'), lw = o.lw || o.width || 1.5, dash = o.dash || null;
      return _push(function (S, B, list, hud, stat) {
        var prev = null;
        for (var i = 0; i < ps.length; i++) {
          var a = _proj(S, B, ps[i]);
          if (!a) { prev = null; stat.skipped++; continue; }
          if (prev) {
            list.push({t: 'seg', d: (prev.d + a.d) / 2, seq: S._seq++, p0: prev, p1: a, c: col, lw: lw, dash: dash});
            stat.segs++;
          }
          prev = a;
        }
      });
    }

    // ---- 三轴 + 刻度 + 轴名（盒边式：三条轴沿"最小角"出发）----
    function axes(o) {
      o = o || {};
      var col = _asColor(o.color || '#64748b'), lw = o.width || 1.2;
      var n = o.ticks == null ? 5 : o.ticks;
      var names = o.labels || ['x', 'y', 'z'];
      var labelColor = o.labelColor || '#475569';
      return _push(function (S, B, list, hud, stat) {
        var lo = S.bounds.lo, hi = S.bounds.hi;
        var span = [hi[0] - lo[0], hi[1] - lo[1], hi[2] - lo[2]];
        var tick = 0.02 * Math.max(span[0], span[1], span[2]);   // 刻度短线长（世界单位）
        var corner = [lo[0], lo[1], lo[2]];
        var ends = [[hi[0], lo[1], lo[2]], [lo[0], hi[1], lo[2]], [lo[0], lo[1], hi[2]]];
        var k, ti;
        for (k = 0; k < 3; k++) {
          var a = _proj(S, B, corner), b = _proj(S, B, ends[k]);
          if (a && b) { list.push({t: 'seg', d: (a.d + b.d) / 2, seq: S._seq++, p0: a, p1: b, c: col, lw: lw}); stat.segs++; }
        }
        for (k = 0; k < 3; k++) {
          var nt = (typeof n === 'object') ? (n['xyz'[k]] || 5) : n;
          var other = (k + 1) % 3;
          for (ti = 0; ti <= nt; ti++) {
            var v = lo[k] + span[k] * ti / nt;
            var base = [lo[0], lo[1], lo[2]]; base[k] = v;
            var tip = base.slice(); tip[other] += tick;
            var pa = _proj(S, B, base), pb = _proj(S, B, tip);
            if (pa && pb) { list.push({t: 'seg', d: pa.d, seq: S._seq++, p0: pa, p1: pb, c: col, lw: lw}); stat.segs++; }
            if (pb && ti % (o.labelEvery || 1) === 0) {
              // 刻度数字走 HUD（永远压在最上层）—— 压在曲面下面就读不出来了。
              // 注意写的是**真实数据值**（scale 只改显示几何，不改这里）。
              hud.push({t: 'text', x: pb.x + 3, y: pb.y + 3, s: _fmt(v), c: labelColor,
                        font: '11px system-ui, "Segoe UI", "Microsoft YaHei", sans-serif',
                        align: 'left', base: 'middle', halo: 'rgba(255,255,255,0.85)'});
              stat.texts++;
            }
          }
          var pe = _proj(S, B, ends[k]);
          if (pe) {
            hud.push({t: 'text', x: pe.x + 8, y: pe.y - 6, s: names[k], c: col,
                      font: 'bold 12px system-ui, "Segoe UI", "Microsoft YaHei", sans-serif',
                      halo: 'rgba(255,255,255,0.85)'});
            stat.texts++;
          }
        }
      });
    }

    // ---- 状态指示：当前参数所在的三维点（可带竖直虚线读数线 + 标签）----
    function marker(p, o) {
      o = o || {};
      var col = _asColor(o.color || '#e11d48'), r = o.size || 4.5;
      return _push(function (S, B, list, hud, stat) {
        var a = _proj(S, B, p);
        if (!a) { stat.skipped++; return; }
        if (o.drop) {
          var b = _proj(S, B, [p[0], p[1], S.bounds.lo[2]]);
          if (b) { list.push({t: 'seg', d: (a.d + b.d) / 2, seq: S._seq++, p0: a, p1: b, c: col, lw: 1.2, dash: [4, 4]}); stat.segs++; }
        }
        list.push({t: 'dot', x: a.x, y: a.y, d: a.d, seq: S._seq++, r: r, c: col, ring: 'rgba(255,255,255,0.9)', lw: 1.6});
        stat.dots++;
        if (o.label) {
          hud.push({t: 'text', x: a.x + r + 5, y: a.y - r - 5, s: o.label, c: col,
                    font: 'bold 12px system-ui, "Segoe UI", "Microsoft YaHei", sans-serif',
                    align: 'left', halo: 'rgba(255,255,255,0.9)'});
          stat.texts++;
        }
      });
    }

    // ---- HUD：画布坐标的平面文字（读数/图例），永远压最上层 ----
    function text2d(x, y, s, o) {
      o = o || {};
      return _push(function (S, B, list, hud, stat) {
        hud.push({t: 'text', x: x, y: y, s: String(s), c: o.color || '#0f172a',
                  font: o.font || _FONT, align: o.align || 'left', base: o.base || 'middle',
                  halo: o.halo === false ? null : (o.halo || 'rgba(255,255,255,0.85)')});
        stat.texts++;
      });
    }

    // ---- 色标：曲面没有它读不出数（label 与两端数值都要画）----
    function colorbar(o) {
      o = o || {};
      return _push(function (S, B, list, hud, stat) {
        hud.push({t: 'cbar', x: o.x == null ? S.W - 74 : o.x, y: o.y == null ? 42 : o.y,
                  w: o.w || 14, h: o.h || Math.min(170, S.H - 90),
                  stops: _stops(o.cmap || 'viridis'), cmin: o.cmin, cmax: o.cmax, label: o.label,
                  c: o.labelColor || '#334155'});
      });
    }

    // ---- 角标三叉：看三维图最容易迷向，给一个"现在 x/y/z 朝哪"的小罗盘 ----
    function triad(o) {
      o = o || {};
      var px = o.x == null ? 46 : o.x, py = o.y == null ? S.H - 34 : o.y, L = o.size || 24;
      var cols = ['#dc2626', '#16a34a', '#2563eb'];
      return _push(function (S, B, list, hud, stat) {
        var arms = [];
        for (var i = 0; i < 3; i++) {
          var e = [0, 0, 0]; e[i] = 1;
          var dx = _dot(e, B.r), dy = -_dot(e, B.u);
          var ln = Math.sqrt(dx * dx + dy * dy) || 1;
          arms.push({x: px + dx / ln * L, y: py + dy / ln * L,
                     lx: px + dx / ln * (L + 9), ly: py + dy / ln * (L + 9),
                     c: cols[i], s: 'xyz'[i]});
        }
        hud.push({t: 'triad', x: px, y: py, arms: arms});
      });
    }

    // ---- 渲染：投影 → 深度排序（远的先画，同深度按入表序）→ 落笔 → HUD ----
    function render() {
      var ctx = S.ctx, B = _basis(S), i;
      S._stat = {quads: 0, segs: 0, dots: 0, texts: 0, skipped: 0, stride: 1, items: S._items.length};
      S._seq = 0;
      var list = [], hud = [];
      for (i = 0; i < S._items.length; i++) S._items[i](S, B, list, hud, S._stat);
      // painter's algorithm：整表统一排序（曲面/线段/点混排），tie-break 用入表序 ——
      // 没有显式 tie-break 的话"同相机连画两次逐位一致"就不能断言（V8 的稳定排序是
      // 实现细节，不是语言保证）。
      list.sort(function (a, b) { return (b.d - a.d) || (a.seq - b.seq); });
      // 放大量注记：藏起来就是把显示当数据 —— 这条注记调用方去不掉，只能改数字。
      var sc = [];
      if (S.scale[0] !== 1) sc.push('x ×' + _fmt(S.scale[0]));
      if (S.scale[1] !== 1) sc.push('y ×' + _fmt(S.scale[1]));
      if (S.scale[2] !== 1) sc.push('z ×' + _fmt(S.scale[2]));
      if (sc.length) {
        hud.push({t: 'text', x: 12, y: 14, s: '视觉放大：' + sc.join('，') + '（刻度为真实值）',
                  c: '#b45309', font: 'bold 12px system-ui, "Segoe UI", "Microsoft YaHei", sans-serif',
                  align: 'left', halo: 'rgba(255,255,255,0.9)'});
      }
      for (i = 0; i < list.length; i++) _paint(ctx, list[i]);
      for (i = 0; i < hud.length; i++) _paint(ctx, hud[i]);
      S._stat.drawn = list.length;
      S._stat.hud = hud.length;
      return S._stat;
    }

    function clear() { S._items.length = 0; return api; }
    function setCamera(o) {
      o = o || {};
      if (_fin(o.az)) S.az = o.az;
      if (_fin(o.el)) S.el = _clamp(o.el, -88, 88);
      if (_fin(o.dist)) S.dist = o.dist;
      if (o.dist === null) S.dist = null;               // 显式恢复自动取景
      return api;
    }
    function camera() { return {az: S.az, el: S.el, dist: S.dist}; }
    // 各向异性显示缩放：膜半径 3 cm × 位移 µm 这种量级差，按真实比例画就是一张平板。
    // 允许放大，但只作用在**显示几何**上 —— 刻度/色标/标签全是真实数据值，且 render()
    // 会自动在画布角上写一行放大量注记（去不掉）。
    function setScale(sc) {
      if (sc && _fin(sc[0]) && _fin(sc[1]) && _fin(sc[2])) S.scale = sc.slice();
      else if (sc && (_fin(sc.x) || _fin(sc.y) || _fin(sc.z))) {
        S.scale = [_fin(sc.x) ? sc.x : 1, _fin(sc.y) ? sc.y : 1, _fin(sc.z) ? sc.z : 1];
      }
      return api;
    }

    // 轨道交互：拖拽转（az/el）、滚轮缩（dist）。改完相机调 onChange —— **不**自己决定
    // 怎么重画：页面可能还有别的视图/读数/hash 要一起更新，重画权归调用方。
    function attachOrbit(o) {
      o = o || {};
      var c = o.target || S.canvas;
      var cb = o.onChange || render;
      var dragging = false, lx = 0, ly = 0;
      function down(ev) {
        dragging = true; lx = ev.clientX; ly = ev.clientY;
        try { if (c.setPointerCapture && ev.pointerId != null) c.setPointerCapture(ev.pointerId); } catch (e) { }
      }
      function move(ev) {
        if (!dragging) return;
        S.az -= (ev.clientX - lx) * 0.45;                    // 度/像素
        S.el = _clamp(S.el + (ev.clientY - ly) * 0.35, -88, 88);
        lx = ev.clientX; ly = ev.clientY;
        cb();
      }
      function up() { dragging = false; }
      function wheel(ev) {
        var auto = _autoDist(S);
        var cur = _fin(S.dist) ? S.dist : auto;
        S.dist = _clamp(cur * Math.exp((ev.deltaY || 0) * 0.0012), 0.35 * auto, 8 * auto);
        if (ev.preventDefault) ev.preventDefault();
        cb();
      }
      c.addEventListener('pointerdown', down);
      c.addEventListener('pointermove', move);
      c.addEventListener('pointerup', up);
      if (typeof window !== 'undefined' && window.addEventListener) {
        window.addEventListener('pointerup', up);            // 拖到画布外松手也要停
      }
      c.addEventListener('wheel', wheel, {passive: false});
      if (c.style) c.style.cursor = 'grab';
      return api;
    }

    var api = {
      canvas: canvas, width: S.W, height: S.H,
      clear: clear, surface: surface, points: points, polyline: polyline,
      axes: axes, marker: marker, text2d: text2d, colorbar: colorbar, triad: triad,
      render: render, setCamera: setCamera, camera: camera, setScale: setScale,
      attachOrbit: attachOrbit,
      project: function (p) { return _proj(S, _basis(S), p); },
      stats: function () { return S._stat; }
    };
    return api;
  }

  return {
    version: 'v1',
    create: create,
    cmaps: CMAPS,                    // 页面可自加：Scene3D.cmaps.名称 = [[r,g,b],…]
    cmap: _rgbAt,
    fmt: _fmt
  };
})();
