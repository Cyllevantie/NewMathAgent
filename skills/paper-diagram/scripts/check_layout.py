#!/usr/bin/env python3
"""check_layout.py — 对任意 .drawio 做版式体检（针对中文示意图调校）。

    python3 check_layout.py fig.drawio            # 体检
    python3 check_layout.py fig.drawio --strict   # WARN 也算失败

FAIL：文字溢出、元素越界、id 重复、盒子重叠、连线穿盒、内嵌位图。
WARN：端点压在盒边、疑似空盒、字号种类过多、填充色发散。
--flow 额外查流程图连通性：悬空节点/缺入口支链/单出口菱形/悬空箭头，以及输入母线
        贴卡底/缺短引线（母线要读成大括号，不是卡片下划线；可选，默认关闭）。

用中文字宽模型（全角=字号、半角=字号/2、行高=字号+3）；**不**对紧密堆叠的行列间距报警——
学术示意图里 3px 贴合的表格式堆叠是刻意的，不是缺陷。规则详解见 references/preflight-rules.md。
"""
import argparse
import re
import sys
import unicodedata
import xml.etree.ElementTree as ET

try:  # Windows 控制台/管道默认 GBK：中文判据直接 print 会 UnicodeEncodeError 崩掉，
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # 而驱动会把崩溃当「脚本故障」静默放行
except Exception:
    pass

FAIL, WARN = [], []


def style_of(s):
    d = {}
    for kv in (s or '').split(';'):
        if '=' in kv:
            k, v = kv.split('=', 1)
            d[k.strip()] = v.strip()
        elif kv.strip():
            d[kv.strip()] = '1'
    return d


def text_w(line, fs):
    return sum(fs if unicodedata.east_asian_width(c) in ('W', 'F') else fs / 2 for c in line)


def plain(v):
    v = re.sub(r'<br\s*/?>', '\n', v or '', flags=re.I)
    v = re.sub(r'<[^>]+>', '', v)
    return v.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>').replace('&quot;', '"')


def rect_rect(a, b):
    """两个矩形是否相交（含边界接触）。"""
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    return ax < bx + bw and bx < ax + aw and ay < by + bh and by < ay + ah


def _has_bg(b):
    """这个纯文字顶点有没有**不透明底色** —— 有的话线穿过去会被挡住，不算重叠。

    只有 `labelBackgroundColor` 不算 `none` 时才算有底（drawio 里它就是给标签上底色的
    那个键）。自身 `fillColor` 走的是 `solid` 那条路，不在这里重复判。
    """
    bg = (b['st'].get('labelBackgroundColor') or '').strip().lower()
    return bg not in ('', 'none')


def seg_rect(x1, y1, x2, y2, r):
    """线段与矩形是否相交（含边界接触）。"""
    rx, ry, rw, rh = r
    if max(x1, x2) < rx or min(x1, x2) > rx + rw or max(y1, y2) < ry or min(y1, y2) > ry + rh:
        return False
    if x1 == x2 or y1 == y2:                     # 正交线段：包围盒相交即相交
        return True
    for ax, ay, bx, by in ((rx, ry, rx + rw, ry), (rx, ry + rh, rx + rw, ry + rh),
                           (rx, ry, rx, ry + rh), (rx + rw, ry, rx + rw, ry + rh)):
        d1 = (x2 - x1) * (ay - y1) - (y2 - y1) * (ax - x1)
        d2 = (x2 - x1) * (by - y1) - (y2 - y1) * (bx - x1)
        d3 = (bx - ax) * (y1 - ay) - (by - ay) * (x1 - ax)
        d4 = (bx - ax) * (y2 - ay) - (by - ay) * (x2 - ax)
        if ((d1 > 0) != (d2 > 0)) and ((d3 > 0) != (d4 > 0)):
            return True
    return False


def point_rect_boundary(p, r):
    """点到矩形边框的距离（点在内部时取到最近边的距离）。"""
    x, y = p
    rx, ry, rw, rh = r
    if rx <= x <= rx + rw and ry <= y <= ry + rh:
        return min(x - rx, rx + rw - x, y - ry, ry + rh - y)
    dx = max(rx - x, 0.0, x - (rx + rw))
    dy = max(ry - y, 0.0, y - (ry + rh))
    return (dx * dx + dy * dy) ** 0.5


def point_seg(p, a, b):
    x, y = p
    x1, y1 = a
    x2, y2 = b
    dx, dy = x2 - x1, y2 - y1
    if dx == 0 and dy == 0:
        return ((x - x1) ** 2 + (y - y1) ** 2) ** 0.5
    t = max(0.0, min(1.0, ((x - x1) * dx + (y - y1) * dy) / (dx * dx + dy * dy)))
    px, py = x1 + t * dx, y1 + t * dy
    return ((x - px) ** 2 + (y - py) ** 2) ** 0.5


def _flow_checks(boxes, edges):
    """Connectivity checks for a flowchart (opt-in ``--flow``).

    The generic layout check only sees geometry.  It cannot tell that a whole
    branch has no incoming arrow, or that a diamond has only one labelled exit
    — both happened in ``fig_roadmap`` while the old check said 0 FAIL.
    """
    nodes = [b for b in boxes if b["solid"]]
    frames = [b for b in boxes if b.get("frame")]
    anchor = 5.0

    def touches(pt, box):
        return point_rect_boundary(pt, box["r"]) <= anchor

    def in_frame(box):
        x, y = box["r"][0] + box["r"][2] / 2, box["r"][1] + box["r"][3] / 2
        return any(fr["r"][0] <= x <= fr["r"][0] + fr["r"][2]
                   and fr["r"][1] <= y <= fr["r"][1] + fr["r"][3]
                   for fr in frames)

    for b in nodes:
        if in_frame(b):
            # A container member is wired through its container (the input bus /
            # shared-model band), not by an individual arrow on every chip.
            continue
        label = b["txt"].strip().split("\n")[0][:16]
        incoming = sum(1 for _cid, pts, _st in edges if touches(pts[-1], b))
        outgoing = sum(1 for _cid, pts, _st in edges if touches(pts[0], b))
        low = label.lower()
        is_start = label.startswith("开始") or low.startswith(("start", "begin"))
        is_end = ("结果" in label or label.startswith("结束")
                  or low.startswith(("result", "end", "output", "finish")))
        if not incoming and not is_start:
            FAIL.append(f'{b["id"]}: 支链/节点没有入口箭头（「{label}」）——'
                        f' 它悬空了，读者不知道从哪来')
        if not outgoing and not is_end:
            FAIL.append(f'{b["id"]}: 节点没有出口箭头（「{label}」）——'
                        f' 流程在这里断掉')
        if "rhombus" in b["st"] and outgoing < 2:
            FAIL.append(f'{b["id"]}: 判断菱形只有 {outgoing} 个出口（「{label}」）——'
                        f' 真分支必须两个出口都画出来')
        if "rhombus" in b["st"]:
            lines = b["txt"].split(chr(10)) or [""]
            max_w = max((text_w(ln, b["fs"]) for ln in lines), default=0)
            usable = max(1.0, b["r"][2] - 8)
            if max_w > 0.62 * usable:
                FAIL.append(
                    f'{b["id"]}: 菱形文字占宽 {max_w / usable:.0%}（>62%）——'
                    f'菱形太窄，文字快贴边；加宽/加高菱形，不要只缩字号')

    # --- 输入汇流要读成“大括号”，不是卡片下划线 ---------------------------
    # 4 张输入卡 + 一条贴着卡底的横线 + 看不出长度的短引线，渲染出来只是四条
    # 下划线。母线必须落到卡底下方至少 BUS_GAP，且每张卡有一条可见引线。
    BUS_GAP = 6.0       # 母线离卡片底边的最小距离（px）
    TAP_MIN = 6.0       # 引线最短可见长度（px）
    segs = [(cid, a, b, st) for cid, pts, st in edges
            for a, b in zip(pts, pts[1:])]
    taps = [s for s in segs
            if abs(s[1][0] - s[2][0]) <= 0.6
            and abs(s[1][1] - s[2][1]) >= TAP_MIN - 1]
    seen_bus = set()
    for cid, a, b, _st in segs:
        if abs(a[1] - b[1]) > 0.6:                 # 只看水平段
            continue
        lo, hi = sorted((a[0], b[0]))
        if hi - lo < 40:                            # 太短，不像母线
            continue
        y = a[1]
        above = [n for n in nodes
                 if lo - 2 <= n["r"][0] + n["r"][2] / 2 <= hi + 2
                 and -0.5 <= y - (n["r"][1] + n["r"][3]) <= 26]
        if len(above) < 3 or (cid, round(y, 1)) in seen_bus:
            continue
        seen_bus.add((cid, round(y, 1)))
        gap = min(y - (n["r"][1] + n["r"][3]) for n in above)
        if gap < BUS_GAP:
            FAIL.append(
                f"{cid}: 输入母线离卡片底边只有 {gap:.0f}px（<{BUS_GAP:g}）——"
                f"看起来是卡片下划线，不是汇流母线；把母线移到卡底下方 ≥{BUS_GAP:g}px")
        missing = []
        for n in above:
            xc = n["r"][0] + n["r"][2] / 2
            bb = n["r"][1] + n["r"][3]
            if not any(abs(p[0] - xc) <= 4
                       and min(p[1], q[1]) <= bb + 1.5
                       and max(p[1], q[1]) >= y - 1.5
                       for _c, p, q, _s in taps):
                missing.append(n["id"])
        if missing:
            FAIL.append(
                f"{cid}: 输入母线缺竖向引线（{', '.join(missing[:4])}）——"
                f"每张卡要有一条 ≥{TAP_MIN:g}px 的短引线落到母线，读成一个大括号")

    anchors = nodes + frames
    for cid, pts, st in edges:
        # Arrowhead must not eat the shaft: a 7 px gap with a 6 px head reads
        # as "only a triangle" in the rendered PNG.
        if str(st.get("endArrow", "classic")).lower() not in ("none", "0"):
            try:
                head = float(st.get("endSize", 6))
            except (TypeError, ValueError):
                head = 6.0
            a, b = pts[-2], pts[-1]
            last = ((b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2) ** 0.5
            if last < head * 1.8 + 2:
                FAIL.append(
                    f"{cid}: 箭头头几乎占满箭杆（末段 {last:g}px，endSize={head:g}）——"
                    f"加大框间距或减小箭头头；读者现在只看到三角形")
        for pt in (pts[0], pts[-1]):
            if any(point_rect_boundary(pt, b["r"]) <= anchor for b in anchors):
                continue
            if any(point_seg(pt, q1, q2) <= anchor * 0.6
                   for ocid, opts, _ost in edges if ocid != cid
                   for q1, q2 in zip(opts, opts[1:])):
                continue
            FAIL.append(f"{cid}: 端点 ({pt[0]:g},{pt[1]:g}) 悬空 —— "
                        f"既不接框也不接另一条母线")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('drawio')
    ap.add_argument('--strict', action='store_true')
    ap.add_argument('--flow', action='store_true',
                    help='额外检查流程图连通性：悬空节点/缺入口支链/单出口菱形/悬空箭头')
    a = ap.parse_args()

    root = ET.parse(a.drawio).getroot()
    model = root.iter('mxGraphModel').__next__()
    pw, ph = float(model.get('pageWidth', 0) or 0), float(model.get('pageHeight', 0) or 0)

    boxes, edges, ids = [], [], {}
    for c in root.iter('mxCell'):
        cid = c.get('id')
        if cid in ids:
            FAIL.append(f'id 重复: {cid}')
        ids[cid] = 1
        st = style_of(c.get('style'))
        g = c.find('mxGeometry')
        if c.get('vertex') == '1' and g is not None:
            x, y = float(g.get('x', 0)), float(g.get('y', 0))
            w, h = float(g.get('width', 0)), float(g.get('height', 0))
            fs = float(st.get('fontSize', 12))
            txt = plain(c.get('value'))
            raw_style = c.get('style') or ''
            if 'data:image/png' in raw_style or 'data:image/jpeg' in raw_style:
                FAIL.append(f'{cid}: 内嵌位图（要求可编辑时整块不可再改）')
            is_text = st.get('strokeColor') == 'none' or st.get('style', '').startswith('text')
            is_frame = st.get('dashed') == '1' and st.get('fillColor') == 'none'
            is_shape = 'shape=' in raw_style
            boxes.append(dict(id=cid, r=(x, y, w, h), fs=fs, txt=txt, st=st, shape=is_shape,
                              fill=st.get('fillColor'), solid=not (is_text or is_frame),
                              text=is_text, frame=is_frame))
            if (not txt.strip() and not is_text and not is_frame and not is_shape
                    and st.get('fillColor') not in (None, 'none')):
                WARN.append(f'{cid}: 有填充有描边却没有文字，疑似漏填')
            if pw and (x < -1 or y < -1 or x + w > pw + 1 or y + h > ph + 1):
                FAIL.append(f'{cid}: 越出画布 ({x:g},{y:g} {w:g}×{h:g})')
            if txt.strip() and w and h and 'shape=singleArrow' not in (c.get('style') or ''):
                lines = txt.split('\n')
                for ln in lines:
                    # 单字居中时边距极小（竖排堆叠常见），多字才按两侧各 4px 估
                    usable = w - (8 if len(ln) > 1 else 2)
                    if text_w(ln, fs) > usable:
                        FAIL.append(f'{cid}: 文字溢出 "{ln[:18]}" 需 {text_w(ln, fs):.0f}px'
                                    f' > 可用 {usable:.0f}px')
                        break
                if len(lines) * (fs + 3) > h * (1.4 if is_text else 1.0):
                    FAIL.append(f'{cid}: {len(lines)} 行放不下（槽高 {h:g}px）')
        elif c.get('edge') == '1' and g is not None:
            pts = []
            sp, tp = g.find("mxPoint[@as='sourcePoint']"), g.find("mxPoint[@as='targetPoint']")
            arr = g.find("Array[@as='points']")
            if sp is not None:
                pts.append((float(sp.get('x')), float(sp.get('y'))))
            if arr is not None:
                pts += [(float(p.get('x')), float(p.get('y'))) for p in arr]
            if tp is not None:
                pts.append((float(tp.get('x')), float(tp.get('y'))))
            if len(pts) >= 2:
                edges.append((cid, pts, st))

    if a.flow:
        _flow_checks(boxes, edges)

    solid = [b for b in boxes if b['solid']]
    for i in range(len(solid)):
        for j in range(i + 1, len(solid)):
            (x1, y1, w1, h1), (x2, y2, w2, h2) = solid[i]['r'], solid[j]['r']
            if x1 < x2 + w2 and x2 < x1 + w1 and y1 < y2 + h2 and y2 < y1 + h1:
                FAIL.append(f"{solid[i]['id']} 与 {solid[j]['id']} 重叠")

    # 「裸文字」也要防被盖。它们**刻意**不进 `solid`：
    #   文字压在背景块上是正常的，进了会全量误报。但那就意味着**任何东西盖住它们都没人管**。
    #   例（`fig_roadmap`）：
    #       b4_mid    value="统一判据/最坏情形/横向可比"  x=448 y=845 w=95 h=55  → y 845–900
    #       b4_double shape=doubleArrow（那条 ↔）        x=442 y=894 w=82 h=23  → y 894–917
    #   两者在 y 894–900、x 448–524 上**真的相交**，箭杆从「横向可比」三个字上压过去，
    #   而体检报 `FAIL 0 WARN 0` —— 人眼一看就废，机器说没问题。渲染侧也没有底色，
    #   所以线是真的盖在字上（与 `lib/visualization/charts.py` 那个 `legend.frameon=False`
    #   是同一类错，不同渲染器）。
    #
    #   判据：**没有不透明底的裸文字，不许被实体盒或连线盖住**。要区分两种 `strokeColor=none`：
    #   - 背景色块：`fillColor` 有值 → 它垫在底下，**豁免**（保持原豁免，防误报）
    #   - 裸文字标签：`fillColor` 也是 none → 被盖即失败
    bare_text = [b for b in boxes
                 if b['txt'].strip() and not b['solid']
                 and b['st'].get('fillColor') in (None, 'none') and not _has_bg(b)]

    for s in solid:
        for t in bare_text:
            if rect_rect(s['r'], t['r']):
                first = t['txt'].split('\n')[0][:14]
                FAIL.append(f'{s["id"]} 盖住文字「{first}」（{t["id"]}）——'
                            f' 该文字没有不透明底色，会被压在下面看不见')

    for cid, pts, _st in edges:
        for k in range(len(pts) - 1):
            x1, y1 = pts[k]
            x2, y2 = pts[k + 1]
            for b in solid:
                bx, by, bw, bh = b['r']
                on_border = (abs(x1 - bx) < 0.6 or abs(x1 - bx - bw) < 0.6 or
                             abs(y1 - by) < 0.6 or abs(y1 - by - bh) < 0.6)
                ends_here = (k == 0 and bx - 0.6 <= x1 <= bx + bw + 0.6
                             and by - 0.6 <= y1 <= by + bh + 0.6)
                if ends_here and on_border:
                    WARN.append(f'{cid}: 端点压在 {b["id"]} 边界上，建议外移 1px')
                    continue
                if seg_rect(x1, y1, x2, y2, b['r']):
                    FAIL.append(f'{cid}: 穿过盒子 {b["id"]}')
                    break
            for b in bare_text:
                if seg_rect(x1, y1, x2, y2, b['r']):
                    first = b['txt'].split('\n')[0][:14]
                    FAIL.append(f'{cid}: 穿过文字「{first}」（{b["id"]}）——'
                                f' 该文字没有不透明底色，线会盖在字上。'
                                f'把线挪开，或给它加 labelBackgroundColor')
                    break

    # 字号与配色收敛度
    sizes = sorted({b['fs'] for b in boxes if b['txt'].strip()})
    if len(sizes) > 4:
        WARN.append(f'字号 {len(sizes)} 种（{sizes}），层级过多，建议收敛到 2–3 种')
    fills = {b['fill'] for b in solid if b['fill'] not in (None, 'none')}
    if len(fills) > 20:
        WARN.append(f'填充色 {len(fills)} 种，配色发散，建议同语义同色')

    seen = set()
    fails = [x for x in FAIL if not (x in seen or seen.add(x))]
    warns = [x for x in WARN if not (x in seen or seen.add(x))]
    print(f'{a.drawio}: 顶点 {len(boxes)} / 连接器 {len(edges)}'
          f'  FAIL {len(fails)}  WARN {len(warns)}')
    for x in fails:
        print(f'  FAIL  {x}')
    for x in warns:
        print(f'  WARN  {x}')
    if fails or (a.strict and warns):
        sys.exit(1)
    print('✓ 版式体检通过')


if __name__ == '__main__':
    main()
