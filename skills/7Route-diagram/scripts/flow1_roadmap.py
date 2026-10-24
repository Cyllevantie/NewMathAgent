# -*- coding: utf-8 -*-
"""flow1 样式的问题路由树——**本题的参考实现，不是必选模板**。

每题的输入、真实分支、支链数量都不同；可以改内容/列数/结果文档排布，甚至另写
生成器，只要满足 `references/route-diagram.md` §5 的硬规则与 §6 的 8 条自检。
本文件只负责当前题的一份合法构图（中文；英文模板按同一语法用英文重写），写成
drawio 源；PNG/PDF 由 draw.io CLI 导出。

结构（719 x 1015 units == 160 mm 宽；W:H≈0.71，按一页 A4 设计）：
  顶部：开始 -> 4 个输入平行四边形 -> 共用模型容器（2x3）
  中轴：D1（t<=1800 s?）-> 变物性 -> 环境 -> D2（加收缩?）-> Q2 -> D3（复用 Q2?）
  左列：Q1（D1 是）在上，Q3（D3 是）在下
  右列：Q4（D2 是）
每条支链用 config/visualization.json 的 question_palette 着色；
支链末端是结果文档 + 绿色「结果」胶囊。

只写 figures/fig_roadmap.drawio；PNG/PDF 由 draw.io CLI 导出。
"""
from __future__ import annotations

import html
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
OUT = PROJECT_ROOT / "figures" / "fig_roadmap.drawio"

INK = "#1F2937"
MUTED = "#64748B"
LINE = "#475569"
FONT = "Microsoft YaHei"

_DEFAULT_Q = {
    "Q1": ("#E8F5E9", "#A5C9A7", "#2E7D32"),
    "Q2": ("#E8F0FE", "#A9C1ED", "#1D4ED8"),
    "Q3": ("#FFF3E0", "#E2C08D", "#B45309"),
    "Q4": ("#F3E8FF", "#C4B5FD", "#6D28D9"),
}


def _question_colors():
    try:
        cfg = json.loads((PROJECT_ROOT / "config" / "visualization.json")
                         .read_text(encoding="utf-8"))
        pal = cfg.get("roadmap_question_palette") or cfg["question_palette"]
        return {q: (pal[q]["fill"], pal[q]["stroke"],
                    pal[q].get("text", INK)) for q in _DEFAULT_Q}
    except (OSError, ValueError, KeyError, TypeError):
        return dict(_DEFAULT_Q)


QCOL = _question_colors()
verts: list[tuple] = []
edges: list[tuple] = []


def V(i, x, y, w, h, text, style):
    # Process/head cards are horizontal bars, not tall cards: a lower box
    # with the same y anchor leaves a longer visible arrow shaft.
    if style.startswith("rounded=1") and h == 32:
        # keep the original y-span centered: shift up by half the reduction,
        # so existing edge endpoints stay within the 5 px anchor tolerance.
        y += (h - 26) / 2
        h = 26
    verts.append((i, x, y, w, h, text, style))


def _shrink(pts, d=1.0):
    """Pull both ends 1 px into the segment so they do not touch box borders."""
    pts = [(float(x), float(y)) for x, y in pts]
    if len(pts) < 2:
        return pts
    (x0, y0), (x1, y1) = pts[0], pts[1]
    L = max((x1 - x0) ** 2 + (y1 - y0) ** 2, 1e-9) ** 0.5
    pts[0] = (x0 + (x1 - x0) / L * d, y0 + (y1 - y0) / L * d)
    (xa, ya), (xb, yb) = pts[-2], pts[-1]
    L = max((xb - xa) ** 2 + (yb - ya) ** 2, 1e-9) ** 0.5
    pts[-1] = (xb - (xb - xa) / L * d, yb - (yb - ya) / L * d)
    return pts


def E(i, pts, color=LINE, arrow=True, width=1.0):
    edges.append((i, _shrink(pts), color, arrow, width))


def T(i, x, y, w, h, text, color=INK, size=12.2, bold=False, align="left"):
    V(i, x, y, w, h, text,
      "text;html=1;strokeColor=none;fillColor=none;align=%s;verticalAlign=middle;"
      "whiteSpace=wrap;fontSize=%g;fontStyle=%d;fontColor=%s;fontFamily=%s;"
      "labelBackgroundColor=#FFFFFF;" % (align, size, 1 if bold else 0, color, FONT))


def head(q, fs=12.7):
    fill, stroke, text = QCOL[q]
    return ("rounded=1;whiteSpace=wrap;html=1;arcSize=14;fillColor=%s;strokeColor=%s;"
            "strokeWidth=0.9;fontColor=%s;fontFamily=%s;fontSize=%g;fontStyle=1;"
            % (fill, stroke, text, FONT, fs))


def proc(q, fs=12.2):
    fill, stroke, _text = QCOL[q]
    return ("rounded=1;whiteSpace=wrap;html=1;arcSize=10;fillColor=%s;strokeColor=%s;"
            "strokeWidth=0.8;fontColor=%s;fontFamily=%s;fontSize=%g;"
            % (fill, stroke, INK, FONT, fs))


def doc(q, fs=12.2):
    fill, stroke, text = QCOL[q]
    return ("shape=document;size=0.06;whiteSpace=wrap;html=1;boundedLbl=1;fillColor=%s;"
            "strokeColor=%s;fontColor=%s;fontFamily=%s;fontSize=%g;"
            % (fill, stroke, text, FONT, fs))


def endcap():
    return ("rounded=1;whiteSpace=wrap;html=1;arcSize=50;fillColor=#E8F5E9;"
            "strokeColor=#2E7D32;strokeWidth=0.9;fontColor=%s;fontFamily=%s;fontSize=12.2;"
            % (INK, FONT))


def diamond():
    return ("rhombus;whiteSpace=wrap;html=1;fillColor=#FFF7E6;strokeColor=#B45309;"
            "strokeWidth=1.2;fontColor=%s;fontFamily=%s;fontSize=12.2;"
            % (INK, FONT))


def model_box():
    return ("rounded=1;whiteSpace=wrap;html=1;arcSize=10;fillColor=#EEF2F7;"
            "strokeColor=#64748B;strokeWidth=0.8;fontColor=%s;fontFamily=%s;fontSize=12.2;"
            % (INK, FONT))


def inp():
    return ("shape=parallelogram;perimeter=parallelogramPerimeter;fixedSize=1;size=10;"
            "whiteSpace=wrap;html=1;fillColor=#E8F5E9;strokeColor=#2E7D32;"
            "strokeWidth=0.8;fontColor=%s;fontFamily=%s;fontSize=12.2;" % (INK, FONT))


def frame(color):
    return ("rounded=1;whiteSpace=wrap;html=1;arcSize=6;dashed=1;dashPattern=4 4;"
            "fillColor=none;strokeColor=%s;strokeWidth=0.8;fontFamily=%s;" % (color, FONT))


# ---------------------------------------------------------------------------
# start (no in-figure figure title; the LaTeX caption / ⑨ owns it)
# ---------------------------------------------------------------------------
V("start", 262, 24, 80, 24, "开始",
  "rounded=1;whiteSpace=wrap;html=1;arcSize=50;fillColor=#F1F5F9;"
  "strokeColor=%s;fontColor=%s;fontFamily=%s;fontSize=12.2;" % (LINE, INK, FONT))
E("e_start_in", [(302, 48), (302, 60)], color=LINE)

# ---------------------------------------------------------------------------
# input band
# ---------------------------------------------------------------------------
V("in_frame", 18, 60, 569, 76, "", frame("#2E7D32"))
# 标签原在 (24,62)，正压在输入带虚线边框与第一个平行四边形的左上角上
# （PNG 放大可见「入」被框线穿过）。移到带子上方，作为带的标题。
T("in_label", 22, 42, 50, 14, "输入", color="#2E7D32", size=12.2, bold=True)
INS = [
    ("i1", 30, "环境序列<br>241 点 × 60 s<br>T_a(t), C_a(t)"),
    ("i2", 170, "半径序列<br>145 点 × 1800 s<br>2.000→1.198 cm"),
    ("i3", 310, "物性经验式<br>ρ, c_p, k, D(C,T)<br>附录 3"),
    ("i4", 450, "几何与初值<br>L=25 cm, R0=2 cm<br>28 °C, 2.55 kg/kg"),
]
for iid, x, txt in INS:
    V(iid, x, 74, 130, 48, txt, inp())

# 输入汇流：母线离卡底 10 units，四张卡各一条竖向短引线（读成大括号），
# 母线中点一根主干直接穿过虚线带边进模型带（允许穿虚线，不要开白口/分段）。
E("e_bus", [(94, 132), (516, 132)], color="#2E7D32", arrow=False, width=1.2)
for iid, xc in (("i1", 95), ("i2", 235), ("i3", 375), ("i4", 515)):
    # 引线画到母线下方 1 unit：_shrink 收完正好停在母线上。
    E("e_tap_" + iid, [(xc, 122), (xc, 133)], color="#2E7D32", arrow=False)
E("e_in_model", [(302, 132), (302, 149)], color="#2E7D32")

# ---------------------------------------------------------------------------
# shared model band
# ---------------------------------------------------------------------------
V("m_frame", 18, 149, 569, 108, "", frame("#94A3B8"))
T("m_label", 24, 151, 220, 14, "共用模型：柱坐标一维径向 ξ",
  color=MUTED, size=12.2, bold=True)
MOD = [
    ("m1", 32, 164, "守恒基准<br>干物质 ρ_s、C 干基计"),
    ("m2", 212, 164, "控制方程<br>柱坐标 1D；热-质耦合"),
    ("m3", 392, 164, "表面边界<br>Robin 热/质通量"),
    ("m4", 32, 212, "离散格式<br>FV N=800；Picard 2 次"),
    ("m5", 212, 212, "物性处理<br>D(C,T) 查表；ρc_p、k"),
    ("m6", 392, 212, "事件定位<br>max C ≤ 0.15；400 细分"),
]
for mid, x, y, txt in MOD:
    V(mid, x, y, 168, 38, txt, model_box())
E("e_model_d1", [(302, 257), (302, 270)], color=LINE)

# ---------------------------------------------------------------------------
# routing trunk
# ---------------------------------------------------------------------------
V("d1", 227, 270, 150, 48, "t ≤ 1800 s？", diamond())
E("e_d1_q1", [(227, 294), (163, 294)], color="#2E7D32")
T("l_d1_q1", 18, 258, 90, 14, "是 · 预热段", color="#2E7D32", size=12.2)
E("e_d1_down", [(302, 318), (302, 332)], color=LINE)
T("l_d1_down", 307, 318, 84, 14, "否 · 全过程", color=MUTED, size=12.2)

V("c1", 245, 332, 114, 32, "变物性 D(C,T)", model_box())
V("c2", 245, 372, 114, 32, "环境：4 h 后保持", model_box())
E("e_c1_c2", [(302, 364), (302, 372)], color=LINE)
V("d2", 227, 414, 150, 48, "加入收缩与<br>材料坐标？", diamond())
E("e_c2_d2", [(302, 404), (302, 414)], color=LINE)
E("e_d2_q4", [(377, 438), (440, 438)], color="#6D28D9")
T("l_d2_q4", 382, 390, 90, 14, "是 · 收缩", color="#6D28D9", size=12.2)
E("e_d2_down", [(302, 462), (302, 476)], color=LINE)
T("l_d2_down", 307, 462, 76, 14, "否 · 定域", color=MUTED, size=12.2)

V("q2h", 245, 476, 114, 32, "Q2 定域 0–72 h", head("Q2"))
V("c3", 245, 514, 114, 32, "双向耦合 T→D", proc("Q2"))
E("e_q2h_c3", [(302, 508), (302, 514)], color="#1D4ED8")

V("c4a", 231, 559, 72, 34, "水分守恒", proc("Q2"))
V("c4b", 303, 559, 70, 34, "320→640", proc("Q2"))
E("e_c3_split", [(302, 546), (302, 550), (267, 550), (267, 559)],
  color="#1D4ED8")
E("e_c3_split2", [(302, 550), (335, 550), (335, 559)], color="#1D4ED8")

V("d3", 227, 598, 150, 48, "复用 Q2 解？", diamond())
E("e_c4_join", [(267, 593), (267, 594), (302, 594), (302, 598)],
  color="#1D4ED8", arrow=False)
E("e_c4_join2", [(335, 593), (335, 594), (302, 594)], color="#1D4ED8",
  arrow=False)
# 两个时刻并排（不是上下叠），既对齐参考图的阅读节奏，也把中轴缩短一截；
# 并列项各自成框，不塞进同一个框（§5 第 7 条）。
# 结果文档必须与正文同字号（12.2 px → 160 mm 置入 ~9.6 pt）；9.6 px 只有 8.25 pt。
# 加宽到 98 让 "1.766 / 1.008"（13.9 px 渲染）仍留出边距（check_layout 需 90px）。
V("q2doc1", 202, 661, 98, 50,
  "3 h<br>1.766 / 1.008", doc("Q2"))
V("q2doc2", 304, 661, 98, 50,
  "72 h<br>0.138 / 0.138", doc("Q2"))
E("e_d3_doc1", [(302, 646), (302, 652), (251, 652), (251, 661)], color="#1D4ED8")
E("e_d3_doc2", [(302, 646), (302, 652), (353, 652), (353, 661)], color="#1D4ED8")
# 原在 (338,642)：D3 到两个结果文档的分叉横线正好从文字中间穿过
# （「否」「仅」被蓝线压住）。移到菱形右下方的空白处：上边避开菱形右下边
# （y=630 处边缘 x≈340），下边离分叉横线 8 单位，右边不碰 Q4 支链（x=440）。
T("l_d3_down", 382, 600, 54, 14, "否·仅Q2", color=MUTED, size=12.2)
E("e_doc1_end", [(251, 712), (251, 714), (302, 714)], color="#2E7D32",
  arrow=False)
E("e_doc2_end", [(353, 712), (353, 714), (302, 714)], color="#2E7D32",
  arrow=False)
V("q2end", 262, 726, 80, 22, "结果", endcap())
E("e_doc_end", [(302, 714), (302, 726)], color="#2E7D32")

# ---------------------------------------------------------------------------
# Q1 branch (left, aligned with D1)
# ---------------------------------------------------------------------------
V("q1h", 18, 278, 145, 32, "Q1 预热段 0–1800 s", head("Q1"))
V("q1b2", 18, 318, 145, 32, "常数物性，两场解耦", proc("Q1"))
V("q1b3", 18, 358, 145, 32, "FV N=320，Δt=1 s", proc("Q1"))
V("q1doc", 18, 398, 145, 68,
  "1800 s 中心/表面<br>33.58 / 36.79 °C<br>2.550 / 1.510 kg/kg<br>校验 4.2×10⁻⁶ K",
  doc("Q1"))
V("q1end", 50, 476, 80, 22, "结果", endcap())
for a, b in ((("q1h", 310), ("q1b2", 318)), (("q1b2", 350), ("q1b3", 358)),
             (("q1b3", 390), ("q1doc", 398)), (("q1doc", 466), ("q1end", 476))):
    E("e_%s_%s" % (a[0], b[0]), [(90.5, a[1]), (90.5, b[1])], color="#2E7D32")

# ---------------------------------------------------------------------------
# Q3 branch (left, aligned with D3)
# ---------------------------------------------------------------------------
V("q3h", 18, 606, 145, 32, "Q3 达标（复用 Q2）", head("Q3"))
V("q3b2", 18, 646, 145, 32, "判据 max_r C ≤ 0.15", proc("Q3"))
V("q3b3", 18, 686, 145, 32, "事件定位：扫描+细分", proc("Q3"))
V("q3doc", 18, 726, 145, 68,
  "t<sub>dry</sub> = 57.570 h<br>表面 12.55 h<br>滞后 45.02 h<br>GCI 0.40% · 表 5",
  doc("Q3"))
V("q3end", 50, 804, 80, 22, "结果", endcap())
# D3 的「是」出口必须真的连到 Q3 支链；旧版只有标签、没有箭头，
# check_layout --flow 会把它判成「支链没有入口」。
E("e_d3_q3", [(227, 622), (163, 622)], color="#B45309")
T("l_d3_q3", 18, 586, 90, 14, "是 · 复用解", color="#B45309", size=12.2)
for a, b in ((("q3h", 638), ("q3b2", 646)), (("q3b2", 678), ("q3b3", 686)),
             (("q3b3", 718), ("q3doc", 726)), (("q3doc", 794), ("q3end", 804))):
    E("e_%s_%s" % (a[0], b[0]), [(90.5, a[1]), (90.5, b[1])], color="#B45309")

# ---------------------------------------------------------------------------
# Q4 branch (right, aligned with D2)
# ---------------------------------------------------------------------------
# 单行 "Q4 收缩工况 0–51.23 h" 在 FS=1.08 下右留白只剩 0.7 px（居中探针判 <4 px）；
# 改双行 + 把该框加高到 40（416→410 上移，底边仍在 450，与 q4b2 留 6 单位）。
V("q4h", 440, 410, 145, 38, "Q4 收缩工况<br>0–51.23 h", head("Q4"))
V("q4b2", 440, 456, 145, 32, "R(t)：2.000→1.198 cm", proc("Q4"))
V("q4b3", 440, 496, 145, 32, "材料坐标 + 固定网格", proc("Q4"))
V("q4b4", 440, 536, 145, 32, "max C(ξ,t) ≤ 0.15", proc("Q4"))
V("q4b5", 440, 576, 145, 32, "FV N=200，Δt=2 s", proc("Q4"))
V("q4b6", 440, 616, 145, 32, "固定 R 负控制 2/1.198", proc("Q4"))
V("q4doc", 440, 656, 145, 68,
  "t<sub>dry</sub> = 51.226 h<br>R(t<sub>dry</sub>) = 1.200 cm<br>固定 R 对照 130.5 h<br>表 6",
  doc("Q4"))
V("q4end", 472, 734, 80, 22, "结果", endcap())
for a, b in ((("q4h", 448), ("q4b2", 456)), (("q4b2", 488), ("q4b3", 496)),
             (("q4b3", 528), ("q4b4", 536)), (("q4b4", 568), ("q4b5", 576)),
             (("q4b5", 608), ("q4b6", 616)), (("q4b6", 648), ("q4doc", 656)),
             (("q4doc", 724), ("q4end", 734))):
    E("e_%s_%s" % (a[0], b[0]), [(512.5, a[1]), (512.5, b[1])], color="#6D28D9")

# ---------------------------------------------------------------------------
# emit
# ---------------------------------------------------------------------------
def esc(s):
    return html.escape(str(s), quote=False)


import re

# SX/SY 把框与间距拉开（内容 bbox 612 units ≈ 160 mm）。字体必须同比放大：
# FS=1.0 时 12.2 px 落在 612 units 的画布上只有 8.97 pt（160 mm 置入），
# 低于「正文 ≥9 pt」的地板；FS=1.08 恢复设计比例 ⇒ 正文 9.69 pt、t_dry 下标 8.07 pt。
SX, SY, FS = 1.20, 1.22, 1.188


def _sx(v):
    return float(v) * SX


def _sy(v):
    return float(v) * SY


def _style(st):
    return re.sub(r"fontSize=([\d.]+)",
                  lambda m: "fontSize=%g" % (float(m.group(1)) * FS), st)


def _snap_vertical_endpoints():
    """Attach vertical arrow ends to the *actual* box borders.

    Box heights were shortened to make horizontal bars; existing edge
    coordinates still point at the old, taller borders.  Without this snap the
    arrow shaft hides inside the old gap and the reader sees only a triangle.

    Only real connectors (``arrow=True``) are snapped: input-bus taps are
    decoration and must stay on the bus.  Snapping them would pull the tap onto
    the nearest frame border and the "大括号" disappears.  After snapping, the
    end is pulled 1 unit back so it touches the border without sitting on it
    (an endpoint exactly on the border is reported as line-through-box).
    """
    for _eid, pts, _color, arrow, _width in edges:
        if not arrow or len(pts) < 2:
            continue
        for j, neighbor in ((0, pts[1]), (-1, pts[-2])):
            pt = pts[j]
            if abs(pt[0] - neighbor[0]) > 0.1:      # not a vertical segment
                continue
            best = None
            for _i, x, y, w, h, _text, _style in verts:
                # frames (dashed) and bare text are grouping/decoration, not
                # connectors' targets — snapping to a frame border disconnects
                # the arrow from the bus it is supposed to start on.
                if "dashed=1" in _style or "strokeColor=none" in _style:
                    continue
                if not (x - 1 <= pt[0] <= x + w + 1):
                    continue
                for yy in (y, y + h):
                    d = abs(pt[1] - yy)
                    if d <= 8 and (best is None or d < best[0]):
                        best = (d, pt[0], yy)
            if best is not None:
                step = 1.0 if neighbor[1] > best[2] else -1.0
                pts[j] = (best[1], best[2] + step)


_snap_vertical_endpoints()

parts = []
parts.append('<mxfile host="app.diagrams.net" type="device">')
parts.append('  <diagram id="fig_roadmap" name="Page-1">')
parts.append('    <mxGraphModel dx="900" dy="700" grid="0" gridSize="10" guides="1" '
             'tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" '
             'pageWidth="719" pageHeight="1015" math="0" shadow="0">')
parts.append('      <root>')
parts.append('        <mxCell id="0"/>')
parts.append('        <mxCell id="1" parent="0"/>')
for i, x, y, w, h, text, style in verts:
    parts.append('        <mxCell id="%s" value="%s" style="%s" vertex="1" parent="1">'
                 % (i, esc(text), _style(style)))
    parts.append('          <mxGeometry x="%g" y="%g" width="%g" height="%g" as="geometry"/>'
                 % (_sx(x), _sy(y), _sx(w), _sy(h)))
    parts.append('        </mxCell>')
for i, pts, color, arrow, width in edges:
    style = ("edgeStyle=orthogonalEdgeStyle;rounded=1;html=1;endArrow=%s;endFill=%d;"
             "endSize=4;strokeColor=%s;strokeWidth=%g;"
             % ("classic" if arrow else "none", 1 if arrow else 0, color, width))
    if not pts:
        continue
    (sx, sy), (tx, ty) = pts[0], pts[-1]
    sx, sy, tx, ty = _sx(sx), _sy(sy), _sx(tx), _sy(ty)
    way = [(_sx(px), _sy(py)) for px, py in pts[1:-1]]
    parts.append('        <mxCell id="%s" value="" style="%s" edge="1" parent="1">'
                 % (i, style))
    parts.append('          <mxGeometry relative="1" as="geometry">')
    parts.append('            <mxPoint x="%g" y="%g" as="sourcePoint"/>' % (sx, sy))
    parts.append('            <mxPoint x="%g" y="%g" as="targetPoint"/>' % (tx, ty))
    if way:
        parts.append('            <Array as="points">')
        for px, py in way:
            parts.append('              <mxPoint x="%g" y="%g"/>' % (px, py))
        parts.append('            </Array>')
    parts.append('          </mxGeometry>')
    parts.append('        </mxCell>')
parts.append('      </root>')
parts.append('    </mxGraphModel>')
parts.append('  </diagram>')
parts.append('</mxfile>')

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text("\n".join(parts) + "\n", encoding="utf-8")
print("wrote", OUT, len(verts), "vertices", len(edges), "edges")
