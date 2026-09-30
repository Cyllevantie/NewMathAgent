#!/usr/bin/env python3
"""Render a three-phase, problem-driven research roadmap as editable draw.io XML.

Usage:
    python3 roadmap_3phase.py content.json -o out.drawio
    python3 roadmap_3phase.py content.json --theme color -o out-color.drawio
    python3 roadmap_3phase.py content.json --check

The 980x1260 geometry is fixed from a supplied reference figure. Content remains
editable and comes exclusively from JSON. Every text slot is checked before the
file is written (CJK/fullwidth = fontSize px, latin/space = fontSize/2).
"""
import argparse
import html
import json
import pathlib
import sys
import unicodedata

try:  # Windows 控制台/管道默认 GBK：中文判据直接 print 会 UnicodeEncodeError 崩掉，
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # 而驱动会把崩溃当「脚本故障」静默放行
except Exception:
    pass


# --------------------------------------------------------------------- geometry
CANVAS_W, CANVAS_H = 980, 1260
FS, LINE_H = 16, 19
FONT = 'Microsoft YaHei,PingFang SC,Hiragino Sans GB,Helvetica'

PHASE2 = (24, 520, 812, 330)
PHASE3 = (24, 875, 812, 363)
MAIN_CX = 430

P1_BRANCH_SPAN = (44, 816)
P2_GROUP_SPANS = ((46, 414), (446, 814))
P3_OUTCOME_SPAN = (74, 786)


# ----------------------------------------------------------------------- themes
PAGE = '#ffffff'
TEXT = '#222222'
BOX_FILL = '#f2f2f2'
BOX_STROKE = '#d9d9d9'
CALLOUT_FILL = '#f2f2f2'
CALLOUT_STROKE = '#d9d9d9'
CELL_FILL = '#ffffff'
CELL_STROKE = '#666666'
EDGE = '#555555'
DASH = '#777777'
ACCENT = '#555555'
QUESTION_FILL = '#ffffff'
QUESTION_STROKE = '#666666'


def configure_theme(name):
    """Switch visual tokens without changing the measured layout."""
    global PAGE, TEXT, BOX_FILL, BOX_STROKE, CALLOUT_FILL, CALLOUT_STROKE
    global CELL_FILL, CELL_STROKE, EDGE, DASH, ACCENT
    global QUESTION_FILL, QUESTION_STROKE

    if name == 'mono':
        PAGE = '#ffffff'
        TEXT = '#222222'
        BOX_FILL, BOX_STROKE = '#f2f2f2', '#d9d9d9'
        CALLOUT_FILL, CALLOUT_STROKE = '#e8e8e8', '#cccccc'
        CELL_FILL, CELL_STROKE = '#ffffff', '#666666'
        EDGE, DASH, ACCENT = '#555555', '#777777', '#b3b3b3'
        QUESTION_FILL, QUESTION_STROKE = '#ffffff', '#666666'
    elif name == 'color':
        PAGE = '#ffffff'
        TEXT = '#252525'
        BOX_FILL, BOX_STROKE = '#f3f3f3', '#dedede'
        CALLOUT_FILL, CALLOUT_STROKE = '#edf4e9', '#d8e3d2'
        CELL_FILL, CELL_STROKE = '#f8faef', '#7f8975'
        EDGE, DASH, ACCENT = '#565b61', '#7d817b', '#c7bce8'
        QUESTION_FILL, QUESTION_STROKE = '#ffffff', '#74787d'
    else:
        raise ValueError(f'未知主题: {name}')


# ---------------------------------------------------------------------- helpers
cells = []
problems = []


def esc(value):
    return html.escape(str(value), quote=True)


def text_w(line, fs=FS):
    return sum(fs if unicodedata.east_asian_width(ch) in ('W', 'F') else fs / 2
               for ch in line)


def lines_of(value):
    if value is None:
        return ['']
    if isinstance(value, (list, tuple)):
        return [str(v) for v in value]
    return str(value).split('\n')


def markup(value):
    return '&lt;br&gt;'.join(esc(line) for line in lines_of(value))


def fit(slot, value, width, height, fs=FS):
    lines = lines_of(value)
    usable = width - 8
    for line in lines:
        needed = text_w(line, fs)
        if needed > usable:
            problems.append(
                f'{slot}: "{line}" 宽 {needed:.0f}px > 可用 {usable:.0f}px'
                f'（约 {int(usable // fs)} 个汉字）')
    line_h = fs + 3
    if len(lines) * line_h > height:
        problems.append(
            f'{slot}: {len(lines)} 行需 {len(lines) * line_h}px，槽高仅 {height:g}px'
            f'（最多 {int(height // line_h)} 行）')


def need(mapping, key, ctx):
    if not isinstance(mapping, dict) or key not in mapping:
        sys.exit(f'content 缺少字段: {ctx}.{key}')
    return mapping[key]


def require_list(value, ctx, low, high):
    if not isinstance(value, list) or not low <= len(value) <= high:
        sys.exit(f'{ctx} 必须为 {low}–{high} 项列表')
    return value


def slots(start, end, count, gap):
    size = (end - start - (count - 1) * gap) / count
    return [(start + i * (size + gap), size) for i in range(count)]


def add(cid, x, y, width, height, style, value=''):
    cells.append(
        f'        <mxCell id="{cid}" value="{value}" style="{style}" vertex="1" parent="1">\n'
        f'          <mxGeometry x="{x:g}" y="{y:g}" width="{width:g}" height="{height:g}" as="geometry" />\n'
        f'        </mxCell>')


def edge(cid, points, stroke=None, width=1.4, end='block', dashed=False,
         dash_pattern='6 4'):
    stroke = stroke or EDGE
    (sx, sy), (tx, ty) = points[0], points[-1]
    dash_style = f'dashed=1;dashPattern={dash_pattern};' if dashed else ''
    style = (
        f'edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;endArrow={end};'
        f'endFill=1;endSize=5;strokeColor={stroke};strokeWidth={width};'
        f'{dash_style}fontSize={FS};fontFamily={FONT};')
    waypoints = ''
    if len(points) > 2:
        waypoints = ('\n            <Array as="points">\n' + '\n'.join(
            f'              <mxPoint x="{x:g}" y="{y:g}" />' for x, y in points[1:-1]) +
            '\n            </Array>')
    cells.append(
        f'        <mxCell id="{cid}" value="" style="{style}" edge="1" parent="1">\n'
        f'          <mxGeometry relative="1" as="geometry">\n'
        f'            <mxPoint x="{sx:g}" y="{sy:g}" as="sourcePoint" />\n'
        f'            <mxPoint x="{tx:g}" y="{ty:g}" as="targetPoint" />{waypoints}\n'
        f'          </mxGeometry>\n        </mxCell>')


def box_style(fill=None, stroke=None, rounded=True, dashed=False, bold=True):
    fill = fill or BOX_FILL
    stroke = stroke or BOX_STROKE
    dash_style = 'dashed=1;dashPattern=5 4;' if dashed else ''
    return (
        f'rounded={1 if rounded else 0};arcSize=12;whiteSpace=wrap;html=1;'
        f'fillColor={fill};strokeColor={stroke};strokeWidth=1;{dash_style}'
        f'fontSize={FS};fontStyle={1 if bold else 0};fontColor={TEXT};fontFamily={FONT};'
        'align=center;verticalAlign=middle;spacingLeft=2;spacingRight=2;')


def tbox(cid, x, y, width, height, value, fill=None, stroke=None,
         rounded=True, dashed=False, bold=True):
    fit(cid, value, width, height)
    add(cid, x, y, width, height,
        box_style(fill, stroke, rounded=rounded, dashed=dashed, bold=bold),
        markup(value))


def container(cid, x, y, width, height):
    add(cid, x, y, width, height,
        f'rounded=1;arcSize=8;html=1;fillColor=none;strokeColor={DASH};'
        'strokeWidth=1.2;dashed=1;dashPattern=8 4 2 4;')


def rail_cap(cid, y):
    edge(cid, [(858, y), (950, y)], DASH, 1.1, 'none', True, '7 5')


# ---------------------------------------------------------------- schema check
def validate(c):
    questions = need(c, 'questions', 'root')
    if not isinstance(questions, list) or len(questions) != 3:
        sys.exit('questions 必须正好 3 项（分别对应三个阶段）')

    p1 = need(c, 'phase1', 'root')
    need(p1, 'data', 'phase1')
    prep = need(p1, 'prep', 'phase1')
    for key in ('left', 'center', 'right'):
        need(prep, key, 'phase1.prep')
    indicator = need(p1, 'indicator', 'phase1')
    for key in ('method', 'center', 'dimensions'):
        need(indicator, key, 'phase1.indicator')
    dims = require_list(indicator['dimensions'], 'phase1.indicator.dimensions', 2, 3)
    cols = None
    for i, row in enumerate(dims):
        row = require_list(row, f'phase1.indicator.dimensions[{i}]', 2, 3)
        cols = cols or len(row)
        if len(row) != cols:
            sys.exit('phase1.indicator.dimensions 每行列数必须一致')
    need(p1, 'analysis', 'phase1')
    require_list(need(p1, 'branches', 'phase1'), 'phase1.branches', 3, 5)
    need(p1, 'relation_method', 'phase1')
    need(p1, 'relation', 'phase1')

    p2 = need(c, 'phase2', 'root')
    groups = need(p2, 'groups', 'phase2')
    if not isinstance(groups, list) or len(groups) != 2:
        sys.exit('phase2.groups 必须正好 2 组（左右两个融合组）')
    for gi, group in enumerate(groups):
        models = require_list(need(group, 'models', f'phase2.groups[{gi}]'),
                              f'phase2.groups[{gi}].models', 2, 3)
        for mi, model in enumerate(models):
            need(model, 'name', f'phase2.groups[{gi}].models[{mi}]')
            need(model, 'result', f'phase2.groups[{gi}].models[{mi}]')
        need(group, 'fusion', f'phase2.groups[{gi}]')
        need(group, 'output', f'phase2.groups[{gi}]')

    p3 = need(c, 'phase3', 'root')
    for key in ('scenario_label', 'stage', 'model', 'forecast', 'final'):
        need(p3, key, 'phase3')
    require_list(need(p3, 'scenarios', 'phase3'), 'phase3.scenarios', 2, 4)
    require_list(need(p3, 'parameters', 'phase3'), 'phase3.parameters', 3, 6)
    require_list(need(p3, 'outcomes', 'phase3'), 'phase3.outcomes', 2, 3)


# ---------------------------------------------------------------------- build
def build(c):
    validate(c)
    p1, p2, p3 = c['phase1'], c['phase2'], c['phase3']

    # Phase 1: data -> preprocessing -> indicators -> analysis -> parallel -> merge.
    tbox('p1_data', 220, 24, 420, 42, p1['data'])
    prep = p1['prep']
    tbox('p1_prep_left', 40, 96, 200, 42, prep['left'])
    tbox('p1_prep_center', 320, 96, 220, 42, prep['center'])
    tbox('p1_prep_right', 620, 96, 200, 42, prep['right'])
    edge('e_p1_data_prep', [(MAIN_CX, 67), (MAIN_CX, 95)])
    edge('e_p1_prep_left', [(319, 117), (241, 117)])
    edge('e_p1_prep_right', [(541, 117), (619, 117)])

    indicator = p1['indicator']
    tbox('p1_indicator_method', 50, 165, 205, 66, indicator['method'],
         CALLOUT_FILL, CALLOUT_STROKE)
    tbox('p1_indicator', 320, 176, 220, 42, indicator['center'])
    edge('e_p1_prep_indicator', [(MAIN_CX, 139), (MAIN_CX, 175)])
    edge('e_p1_method_indicator', [(256, 198), (319, 198)], dashed=True)

    dims = indicator['dimensions']
    row_h = 72 / len(dims)
    col_w = 240 / len(dims[0])
    for ri, row in enumerate(dims):
        for ci, value in enumerate(row):
            tbox(f'p1_dim_{ri}_{ci}', 590 + ci * col_w, 158 + ri * row_h,
                 col_w, row_h, value, CELL_FILL, CELL_STROKE,
                 rounded=False, dashed=True, bold=False)
    edge('e_p1_indicator_dims', [(541, 197), (589, 197)])

    tbox('p1_analysis', 320, 260, 220, 42, p1['analysis'])
    edge('e_p1_indicator_analysis', [(MAIN_CX, 219), (MAIN_CX, 259)])

    branches = p1['branches']
    branch_slots = slots(*P1_BRANCH_SPAN, len(branches), 12)
    centers = []
    for i, ((x, width), value) in enumerate(zip(branch_slots, branches)):
        center = x + width / 2
        centers.append(center)
        tbox(f'p1_branch_{i}', x, 350, width, 42, value)
    edge('e_p1_analysis_stem', [(MAIN_CX, 303), (MAIN_CX, 330)], end='none')
    edge('e_p1_branch_bus', [(centers[0], 330), (centers[-1], 330)], end='none')
    for i, center in enumerate(centers):
        edge(f'e_p1_branch_in_{i}', [(center, 330), (center, 349)])
        edge(f'e_p1_branch_out_{i}', [(center, 393), (center, 412)], end='none')
    edge('e_p1_merge_bus', [(centers[0], 412), (centers[-1], 412)], end='none')

    tbox('p1_relation_method', 50, 428, 205, 58, p1['relation_method'],
         CALLOUT_FILL, CALLOUT_STROKE)
    tbox('p1_relation', 320, 438, 220, 46, p1['relation'])
    edge('e_p1_merge_relation', [(MAIN_CX, 412), (MAIN_CX, 437)])
    edge('e_p1_relation_method', [(256, 461), (319, 461)], dashed=True)

    # Phase 2: two model groups, each merging into its own fusion and output.
    container('phase2_frame', *PHASE2)
    groups = p2['groups']
    group_centers = []
    all_model_centers = []
    group_layout = []
    for gi, (group, span) in enumerate(zip(groups, P2_GROUP_SPANS)):
        model_slots = slots(*span, len(group['models']), 10)
        model_centers = [x + width / 2 for x, width in model_slots]
        all_model_centers.extend(model_centers)
        group_center = sum(span) / 2
        group_centers.append(group_center)
        group_layout.append((model_slots, model_centers, group_center))

    edge('e_phase12', [(MAIN_CX, 485), (MAIN_CX, 547)], ACCENT, 5)
    edge('e_p2_model_bus', [(all_model_centers[0], 548),
                            (all_model_centers[-1], 548)], end='none')

    for gi, (group, layout) in enumerate(zip(groups, group_layout)):
        model_slots, model_centers, group_center = layout
        for mi, ((x, width), center, model) in enumerate(
                zip(model_slots, model_centers, group['models'])):
            tbox(f'p2_g{gi}_model_{mi}', x, 566, width, 42, model['name'])
            result_width = min(width, 150)
            tbox(f'p2_g{gi}_result_{mi}', center - result_width / 2, 626,
                 result_width, 38, model['result'])
            edge(f'e_p2_g{gi}_model_in_{mi}', [(center, 548), (center, 565)])
            edge(f'e_p2_g{gi}_model_result_{mi}', [(center, 609), (center, 625)])
            edge(f'e_p2_g{gi}_result_merge_{mi}', [(center, 665), (center, 680)], end='none')
        edge(f'e_p2_g{gi}_merge_bus', [(model_centers[0], 680),
                                      (model_centers[-1], 680)], end='none')
        tbox(f'p2_g{gi}_fusion', group_center - 120, 696, 240, 42, group['fusion'])
        tbox(f'p2_g{gi}_output', group_center - 100, 766, 200, 40, group['output'])
        edge(f'e_p2_g{gi}_merge_fusion', [(group_center, 680), (group_center, 695)])
        edge(f'e_p2_g{gi}_fusion_output', [(group_center, 739), (group_center, 765)])
        edge(f'e_p2_g{gi}_output_merge', [(group_center, 807), (group_center, 824)], end='none')

    edge('e_p2_output_bus', [(group_centers[0], 824), (group_centers[-1], 824)], end='none')

    # Phase 3: scenarios + parameters -> combined model -> forecast -> outcomes -> path.
    container('phase3_frame', *PHASE3)
    scenario_lines = [p3['scenario_label']] + [str(x) for x in p3['scenarios']]
    tbox('p3_scenarios', 50, 906, 155, 96, scenario_lines,
         CALLOUT_FILL, CALLOUT_STROKE)
    tbox('p3_stage', 280, 900, 300, 44, p3['stage'])
    tbox('p3_parameters', 650, 898, 160, 126, p3['parameters'],
         CALLOUT_FILL, CALLOUT_STROKE)
    tbox('p3_model', 260, 978, 340, 48, p3['model'])
    tbox('p3_forecast', 300, 1052, 260, 42, p3['forecast'])

    edge('e_phase23', [(MAIN_CX, 824), (MAIN_CX, 899)], ACCENT, 5)
    edge('e_p3_scenarios_stage', [(206, 924), (279, 924)], dashed=True)
    edge('e_p3_stage_model', [(MAIN_CX, 945), (MAIN_CX, 977)])
    edge('e_p3_parameters_model', [(649, 1001), (601, 1001)], dashed=True)
    edge('e_p3_model_forecast', [(MAIN_CX, 1027), (MAIN_CX, 1051)])

    outcomes = p3['outcomes']
    # Two outcomes keep the narrower, separated proportions measured from the
    # reference. Three outcomes use the whole span and equal-width slots.
    outcome_slots = ([(74, 300), (486, 300)] if len(outcomes) == 2
                     else slots(*P3_OUTCOME_SPAN, len(outcomes), 16))
    outcome_centers = []
    for i, ((x, width), value) in enumerate(zip(outcome_slots, outcomes)):
        center = x + width / 2
        outcome_centers.append(center)
        tbox(f'p3_outcome_{i}', x, 1122, width, 48, value)
    edge('e_p3_forecast_stem', [(MAIN_CX, 1095), (MAIN_CX, 1108)], end='none')
    edge('e_p3_outcome_bus', [(outcome_centers[0], 1108),
                              (outcome_centers[-1], 1108)], end='none')
    for i, center in enumerate(outcome_centers):
        edge(f'e_p3_outcome_in_{i}', [(center, 1108), (center, 1121)])
        edge(f'e_p3_outcome_merge_{i}', [(center, 1171), (center, 1180)], end='none')
    edge('e_p3_final_bus', [(outcome_centers[0], 1180),
                            (outcome_centers[-1], 1180)], end='none')
    tbox('p3_final', 200, 1192, 460, 38, p3['final'])
    edge('e_p3_final', [(MAIN_CX, 1180), (MAIN_CX, 1191)])

    # Right-side question rail: each stage interval converges on one question.
    for i, y in enumerate((22, 520, 850, 1238)):
        rail_cap(f'rail_cap_{i}', y)
    q_boxes = ((208, 256), (660, 708), (1040, 1088))
    boundaries = ((22, 520), (520, 850), (850, 1238))
    for i, (question, (top, bottom), (bound_top, bound_bottom)) in enumerate(
            zip(c['questions'], q_boxes, boundaries), 1):
        tbox(f'question_{i}', 865, top, 78, bottom - top, question,
             QUESTION_FILL, QUESTION_STROKE, rounded=False)
        edge(f'e_question_{i}_top', [(904, bound_top), (904, top - 1)],
             DASH, 1.2, dashed=True, dash_pattern='7 5')
        edge(f'e_question_{i}_bottom', [(904, bound_bottom), (904, bottom + 1)],
             DASH, 1.2, dashed=True, dash_pattern='7 5')


# ------------------------------------------------------------------------ main
def main():
    ap = argparse.ArgumentParser(
        description='Render a three-phase problem-driven research roadmap .drawio')
    ap.add_argument('content', help='content JSON path')
    ap.add_argument('-o', '--out', default=None, help='output .drawio path')
    ap.add_argument('--theme', choices=('mono', 'color'), default='mono',
                    help='visual theme: grayscale paper-style mono (default) or color')
    ap.add_argument('--check', action='store_true', help='only run capacity checks')
    args = ap.parse_args()

    content = json.loads(pathlib.Path(args.content).read_text(encoding='utf-8'))
    configure_theme(args.theme)
    build(content)

    if problems:
        print(f'✗ 容量检查未通过（{len(problems)} 处超框）：', file=sys.stderr)
        for problem in problems:
            print(f'  - {problem}', file=sys.stderr)
        print('\n请缩短文案或用 "\\n" 手动断行，再重新渲染。', file=sys.stderr)
        sys.exit(2)
    print('✓ 容量检查通过')
    if args.check:
        return

    out = pathlib.Path(args.out or pathlib.Path(args.content).with_suffix('.drawio'))
    xml = (
        '<mxfile host="app.diagrams.net" agent="codex" version="24.7.17" pages="1">\n'
        '  <diagram id="roadmap-3phase" name="三阶段技术路线图">\n'
        f'    <mxGraphModel dx="{CANVAS_W}" dy="{CANVAS_H}" grid="0" gridSize="10" '
        'guides="1" tooltips="1" connect="1" arrows="1" fold="1" page="1" '
        f'pageScale="1" pageWidth="{CANVAS_W}" pageHeight="{CANVAS_H}" '
        f'background="{PAGE}" math="0" shadow="0">\n'
        '      <root>\n        <mxCell id="0" />\n        <mxCell id="1" parent="0" />\n' +
        '\n'.join(cells) +
        '\n      </root>\n    </mxGraphModel>\n  </diagram>\n</mxfile>\n')
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(xml, encoding='utf-8')
    print(f'✓ 已写出 {out}（{len(cells)} 个图元）')


if __name__ == '__main__':
    main()
