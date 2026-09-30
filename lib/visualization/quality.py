# -*- coding: utf-8 -*-
"""出图后的两道机器检查：**位图质量** 与 **图例压数据**。

为什么要有它：

1. 图例是 `legend(ncol=2, loc="upper left")` 而 `charts.style()` 全局设了
   `legend.frameon: False` —— 图例**没有底色**，红色与棕色两条曲线会直接从
   `t = 1200 s` / `t = 1800 s` 两行字上穿过去，标签读不出来；两列排布还可能让
   `数值解 1800 s` 与 `级数解 1800 s` 挤成一行。人眼一看就废，但**机器一路放行** ——
   `export()` 只查字号与出画布，查不到"图例盖住数据"。
2. 位图本身没人查：`export()` 存完 PNG 就登记，`register()` 只校 sources/claim 非空。
   图万一渲染成空白、或被裁掉一半，照样进 manifest。

第一道是**位图三查**（分辨率下限、
近似纯色、边界暗像素比例）；第二道是本项目针对该缺口的补充（重合即要求重渲）。

两道都返回**问题串**，由 `export()` 并进 `auto_issues`；而 `evidence.register()` 要求
`auto_issues` 为空才允许 `review()` 通过 —— 于是"机器不放过"成为硬闸，而不是靠自觉。
"""
from pathlib import Path

import numpy as np


# ---------------------------------------------------------------- 位图质量

# 「贴边非白带」判据：
# 实心浅灰矩形（如 `#E2E8F0`、`strokeColor=none`）拼成的 L 形底块 —— 左带 47 px、
# 顶带 28 px，右/下干净 —— 放在白底正文里活像一副没对齐的边框。
# 只数"暗"像素的判据（`border.mean(axis=1) < 32`）对它天生失明：这个灰是 232.7
# （既不够暗、又不够白）⇒ 0 error / 0 warning 放行。
# 判据只抓**不对称**：四条边里有的贴着非白带、有的干净 ⇒ warning。四边都贴（成框）视为
# 有意的设计，不报 —— 左+上有、右+下没有这种半拉子才要报。
EDGE_MIN_SHARE = 0.60   # 某条边上非白像素占比达到它，才算"这条边贴着东西"
EDGE_MIN_WIDTH = 6      # 且带子要够宽：matplotlib 的轴线只有 1~2 px，不是带
EDGE_SCAN_FRACTION = 0.10   # 最多向内扫这么多（再宽就不是"贴边带"了），顺带把开销钉死
NEAR_WHITE = 245        # 比它亮就算白（正文纸色）


def _edge_band_width(rgb, side):
    """从某条边向内走，返回"非白贴边带"的宽度（px）；干净边返回 0。

    逐层判：这一层里非白像素占比 ≥ `EDGE_MIN_SHARE` 就继续往里，一旦某层白回来就停。
    """
    height, width = rgb.shape[0], rgb.shape[1]
    limit = max(EDGE_MIN_WIDTH, int(EDGE_SCAN_FRACTION * (height if side in "左右" else width)))
    span = height if side in "左右" else width
    for step in range(min(limit, span)):
        if side == "左":
            layer = rgb[:, step]
        elif side == "右":
            layer = rgb[:, width - 1 - step]
        elif side == "上":
            layer = rgb[step, :]
        else:
            layer = rgb[height - 1 - step, :]
        if float(np.mean(layer.mean(axis=1) < NEAR_WHITE)) < EDGE_MIN_SHARE:
            return step
    return min(limit, span)


def inspect_png(path, settings, *, figure_id=""):
    """位图四查（前三查 = 位图三查）。返回 (errors, warnings)。

    - 分辨率低于 `quality.minimum_width_px/height_px` → **error**
    - 近似纯色（峰谷差 < 3）→ **error**：渲染成空白了
    - 边界暗像素占比 > `maximum_dark_border_ratio` → **warning**：疑似裁切/边框异常
    - 单侧"贴边非白带"（见上）→ **warning**：白底正文里像半拉子边框

    暗像素阈值取 32（0–255 的均值）。
    """
    from PIL import Image

    q = (settings.get("quality") or {})
    min_w = int(q.get("minimum_width_px", 800))
    min_h = int(q.get("minimum_height_px", 480))
    max_dark = float(q.get("maximum_dark_border_ratio", 0.35))
    errors, warnings = [], []
    p = Path(path)
    if not p.is_file():
        return [f"{figure_id}: 位图不存在：{p}"], []
    with Image.open(p) as image:
        image.load()
        width, height = image.size
        rgb = np.asarray(image.convert("RGB"), dtype=np.uint8)
    if width < min_w or height < min_h:
        errors.append(f"{figure_id}: 位图 {width}x{height} px，低于 {min_w}x{min_h} ——"
                      f" 检查 config/visualization.json 的 dpi 与 width_mm/height_mm")
    if rgb.size == 0 or int(np.ptp(rgb.astype(np.int16), axis=(0, 1)).max()) < 3:
        errors.append(f"{figure_id}: 位图近似纯色（峰谷差 < 3）—— 图渲染成空白了")
        return errors, warnings
    border = np.concatenate((rgb[0], rgb[-1], rgb[:, 0], rgb[:, -1]), axis=0)
    dark = float(np.mean(border.mean(axis=1) < 32))
    if dark > max_dark:
        warnings.append(f"{figure_id}: 边界暗像素占比 {dark:.0%}（阈值 {max_dark:.0%}）——"
                        f" 疑似裁切或边框异常")
    bands = {side: _edge_band_width(rgb, side) for side in "左上右下"}
    thick = {side: w for side, w in bands.items() if w >= EDGE_MIN_WIDTH}
    if thick and len(thick) < 4:
        clean = "、".join(side for side in "左上右下" if side not in thick)
        solid = "、".join(f"{side}{w}px" for side, w in thick.items())
        warnings.append(
            f"{figure_id}: 部分边贴着非白底块（{solid}；{clean}干净）——"
            f" 放在白底正文里像一副没对齐的边框。去掉这块底色，或让四边一致")
    return errors, warnings


# ------------------------------------------------------------ 图例压数据


def _densify(xy, step_px=6.0):
    """把折线按显示坐标加密到约每 `step_px` 一个点。

    直接拿原始数据点判"在不在图例框里"会漏：曲线在框内可能只跨两三个采样点，
    框却横跨半个坐标区。加密后判据才稳。
    """
    if len(xy) < 2:
        return xy
    seg = np.diff(xy, axis=0)
    length = np.hypot(seg[:, 0], seg[:, 1])
    total = float(length.sum())
    if total <= 0:
        return xy
    n = max(int(total / step_px), len(xy))
    # 沿累计弧长等距取样
    s = np.concatenate(([0.0], np.cumsum(length)))
    want = np.linspace(0.0, total, n)
    return np.column_stack([np.interp(want, s, xy[:, 0]), np.interp(want, s, xy[:, 1])])


def legend_data_overlap(fig, *, min_points=8):
    """图例盖住数据的清单。返回问题串（空 = 没盖住）。

    判据是**图例框内有几个加密采样点属于可见曲线**（`min_points` 起报）。
    不是 bbox 相交 —— 一条长曲线的 bbox 几乎总是覆盖全图，那样报等于全量误报。

    只查折线（`ax.lines`）。`fill_between` 的色带与散点不在内：它们被判"被压住"的
    语义模糊（色带本就允许被压），报出来会让闸门变吵而非变准。
    """
    issues = []
    axes_with_legend = [ax for ax in fig.axes if ax.get_legend() is not None]
    if not axes_with_legend:
        return issues
    fig.canvas.draw()
    for ax in axes_with_legend:
        legend = ax.get_legend()
        if not legend.get_visible():
            continue
        box = legend.get_window_extent(fig.canvas.get_renderer())
        hits = []
        for line in ax.lines:
            if not line.get_visible():
                continue
            xy = line.get_xydata()
            if xy is None or len(xy) < 2:
                continue
            disp = ax.transData.transform(np.asarray(xy, dtype=float))
            disp = _densify(disp)
            inside = ((disp[:, 0] >= box.x0) & (disp[:, 0] <= box.x1)
                      & (disp[:, 1] >= box.y0) & (disp[:, 1] <= box.y1))
            n = int(inside.sum())
            if n >= min_points:
                hits.append((n, line.get_label()))
        if hits:
            hits.sort(reverse=True)
            shown = "、".join(f"{lb}（{n} 点）" for n, lb in hits[:3])
            issues.append(
                f"图例压住曲线：{shown}"
                f"{' 等' if len(hits) > 3 else ''}"
                f" —— 图例框落在数据上。改 loc 挪开、或缩小曲线区间，别让标签压线")
    return issues


def texts_overlap(fig, *, warn_ratio=0.30, error_ratio=0.55):
    """**文字互相压**的清单 → `(errors, warnings)`。

    为什么要有它：`export()` 只查**越界**与**小字号**，
    `legend_data_overlap` 只查**图例压曲线** —— 而"一段注记压住另一段注记"三道全都不管。
    `fig_geometry` 里标签间距取 4.6 时，「对流传质／水分出」的第二行会压到
    下方四行首行（改 6.2 才够；6.2 时净空只剩 5 px —— 挤，但不重叠）。

    **它抓不到"挤"**：判据是 bbox 重叠面积占比，净空只有几像素的情况不会报。
    别把它的沉默当成"排版没问题"——余量仍靠目检。

    只查**显式注记**（`ax.text` / `ax.annotate` 落的文字、以及 figure 级 `fig.text`）——
    刻度标签、轴标签、图例文字不在内：它们互相靠近是**布局该解决的**，报出来只会让闸门变吵。
    判据是**重叠面积占较小那个框的比例**（不是 bbox 相交：相邻不等长的文字 bbox 相交
    但字并不压字，那会全量误报）。

    分两档（与 `inspect_png` 的 error/warning 同构）：压掉一大半 = error（挡复核），
    压住一角 = warning（只报不挡，可能是标点或下标挨着）。
    """
    errors, warnings_out = [], []
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    boxes = []
    for ax in fig.axes:
        for text in list(getattr(ax, "texts", [])) + list(fig.texts):
            if not text.get_visible() or not text.get_text().strip():
                continue
            try:
                box = text.get_window_extent(renderer)
            except Exception:            # 极端字号/空文本下 extent 可能算不出来
                continue
            if box.width <= 0 or box.height <= 0:
                continue
            boxes.append((box, " ".join(text.get_text().split())[:24]))
    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            (a, ta), (b, tb) = boxes[i], boxes[j]
            w = min(a.x1, b.x1) - max(a.x0, b.x0)
            h = min(a.y1, b.y1) - max(a.y0, b.y0)
            if w <= 1 or h <= 1:
                continue
            ratio = (w * h) / min(a.width * a.height, b.width * b.height)
            if ratio < warn_ratio:
                continue
            msg = f"文字互相压：『{ta}』×『{tb}』（重叠 {ratio:.0%}）—— 挪开其中一条注记"
            (errors if ratio >= error_ratio else warnings_out).append(msg)
    return errors, warnings_out


def near_monochrome(png_path, *, bucket=16, warn_ratio=0.75,
                    bg_lum=0.85, bg_sat=0.15):
    """**近乎单色**检测 → `(ratio, modal_rgb)`：非白像素里"同一个颜色"占多少。

    为什么要有它：场图会出这类缺陷 —— 低值区占 76–91% 时，色阶的低端（YlGnBu 的近白、
    viridis 的亮黄）把**一大片**画成同色，白网格线与白虚线全被吃掉。
    判据就是这条：非白像素里同色占比 ≥ `warn_ratio` ⇒ 这张图其实只有一个色块，
    很可能"该画成剖面/折线"，或者色阶低端该裁（见 config 的 `_slice_note`）。

    只报**提醒**、不进 `auto_issues`（不挡复核）：折线图的大片白底、流程图的同色方框
    都会命中这条，误伤真图不值当 —— 它给的是"值得看一眼"的信号，不是判决。

    实现：降到 `bucket=16` 级量化后数众数（够快且对抖动不敏感）；白/近白像素先排除
    （背景不是"场"）。
    """
    from PIL import Image
    img = Image.open(png_path).convert("RGB")
    a = np.asarray(img, dtype=np.int16)
    flat = a.reshape(-1, 3)
    # 背景/纸面色：**既亮又淡**（白底、浅灰填充）。不能只排近白 —— 示意图的
    # `#E8E8E8` 填充（Δ=23/通道）会漏过去，把"浅灰方框"误判成"一片同色场"。
    # 而"亮黄"(253,236,84) 饱和度 0.67 ⇒ 不受影响，照旧能被抓到。
    mx = flat.max(axis=1).astype(np.float64)
    mn = flat.min(axis=1).astype(np.float64)
    sat = np.divide(mx - mn, np.maximum(mx, 1.0))
    is_bg = (mx / 255.0 > bg_lum) & (sat < bg_sat)
    non_white = flat[~is_bg]
    if non_white.size == 0:
        return 0.0, (255, 255, 255)
    q = (non_white // bucket).astype(np.int32)
    keys = q[:, 0] * 1000000 + q[:, 1] * 1000 + q[:, 2]
    vals, counts = np.unique(keys, return_counts=True)
    k = int(np.argmax(counts))
    ratio = float(counts[k]) / float(keys.size)
    modal = tuple(int(v) for v in q[keys == vals[k]][0] * bucket + bucket // 2)
    return ratio, modal
