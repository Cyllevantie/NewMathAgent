# -*- coding: utf-8 -*-
"""骨架与版式对账：正文小节的标题、符号表的列、表的并排、措辞。

**给 `9Paper-writing` 收尾自检用**（也给人工排查用）。

四类检查：

1. **骨架**（`skeleton_issues`）——章节标题序列对不对。
2. **符号表形制**（`_symbols_problems`）——`4_symbols.tex` 必须是**三列：符号 / 含义 / 单位**，
   单位**单独成列**，不得塞进含义列的括号里（参考件
   `基于变物性耦合传热传质与动域模型的.pdf` 即此形制）。写成两列
   `$\rho$ & 湿基密度（kg/m$^3$）` 即版式不符，故机械核。
3. **表的并排**（`_table_pairing_problems`）——列结构与行数**完全相同**的两张表
   （典型：温度表与水分浓度表，同一批时刻 × 同一批距离）必须并排，各自独占会白占
   约一页高度（参考件的表 2/3、表 4/5 即如此）。
4. **措辞**（`_wording_problems`）——**全文不要引号**（`""` `“”` `「」` `『』`）、
   **括号里不写解释**。

为什么要有它：模板 `sections/*.tex` 是**骨架** ——
`\\subsection{}`/`\\subsubsection{}` 的**名称、层级、顺序都是给定的**，`9Paper-writing` 只能往里填内容。
但骨架的约束若只写在 LaTeX **注释**里（"% 篇幅：全节 ≤ 一页、每个问题的分析 ≤ 3 行"），
**没有任何东西强制它** —— 不核就会把骨架当"参考"自行重排：

| 节 | 模板骨架 | 偏离写法 |
|---|---|---|
| 二、问题分析 | 问题一/二/三的分析 + **本文主要创新点** | 几何/数据/四问/求解方案，**创新点整节没了** |
| 三、模型假设 | 3–6 条、**每条不长** | 6 条（条数够）但每条 200–400 字 |
| 五、模型建立与求解 | **5.1 = 问题一**（具体分析/模型准备/模型建立/模型求解） | 前面插了"四问共用框架/共用方案"两节，问题一被挤到 5.3 |
| 六、模型检验与分析 | 误差分析 / 灵敏度分析 | 数值误差与收敛性 / 守恒性与解析校核 / 灵敏度分析 / 前提与稳健性 |
| 七、模型的评价与推广 | 优点 / 缺点 / 改进与推广 | **结论汇总** / 优点 / 缺点与局限 / 改进与推广 |

判据：**实际标题序列与某一族模板骨架完全一致即通过**（不指定用哪族 —— 谁的骨架对得上就是谁）。
都不一致时，报**最接近那一族**的逐条差异：多了哪个标题、少了哪个、哪个改了名、顺序哪里不对。

用法：

    python lib/web/check_skeleton.py                 # 在项目根跑
    python lib/web/check_skeleton.py --root <其它工作区>
    python lib/web/check_skeleton.py --json

返回码 `0 = 通过`、`1 = 与骨架不一致`、`2 = 找不到模板骨架（配置问题）`。
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

TEMPLATES_REL = "skills/9Paper-writing/templates"
PAPER_SECTIONS_REL = "paper/sections"
# 六种标准标题：section / subsection / subsubsection（含带星号的不编号变体）
HEADING_RE = re.compile(r"\\(section|subsection|subsubsection)\*?\{")
LEVELS = {"section": 1, "subsection": 2, "subsubsection": 3}
# `3_assumptions.tex` 的每一条：模板说「篇幅上限：一页；条数 3--6 条，每条不长」。
ASSUMPTIONS_FILE = "3_assumptions.tex"
ASSUMPTION_MIN, ASSUMPTION_MAX = 3, 5      # 模型假设最多 5 条
ASSUMPTION_INTRO = "为了适当地对模型进行合理简化"   # 标题下必须先写这句引入语
# 「每条不长」：参考件 `框架模板.pdf` 的假设每条 40~70 字；给足余量，200 字以上判超。
ASSUMPTION_CHARS_WARN, ASSUMPTION_CHARS_FAIL = 120, 200

# `2_analysis.tex` 的篇幅：**全节 ≤ 一页半**，且**每个问题的分析 ≤ 3 行**、**每条创新点 ≤ 5 行**。
#   「3 行」「1.23 页」都是按参考件 `基于变物性耦合传热传质与动域模型的.pdf` 量出来的 ——
#   它的 2.1~2.4 各占 2~3 行、创新点每条 4~5 行、全节 1.23 页。本模板排版下 1 行 ≈ 38 字，
#   所以 3 行 ≈ 100 字。没有机械抓手时实测写出过 2205 字 = 2.23 页（四问分析各 400+ 字）。
# 定标（同一把尺子 `_prose_len`）：本模板正文页 ≈ **989 字**（2205 字 ÷ 2.23 页）。
ANALYSIS_FILE = "2_analysis.tex"
ANALYSIS_CHARS_PER_PAGE = 989   # 页↔字的换算基准；改它等于改下面的阈值
ANALYSIS_CHARS_WARN = 1300      # ≈1.31 页 —— 提醒线。参考件 1.23 页、4 条创新点约 1.27 页，
                                #   都在这条线以内 ⇒ 合法形状不会被念
ANALYSIS_CHARS_FAIL = 1480      # **一页半** —— 全节硬上限，不是一页
ANALYSIS_PER_LINE = 38          # 正文一行约几个字（参考件实测 33~38，取上限）
# 每个「问题N的分析」≤ 3 行（参考件 2.1~2.4 实测 2~3 行）—— 只讲要什么、难在哪、走什么路线。
ANALYSIS_MAX_LINES = 3
ANALYSIS_SUB_CHARS_FAIL = ANALYSIS_PER_LINE * ANALYSIS_MAX_LINES
# 每条「创新点X：」≤ 5 行（参考件实测 4~5 行、120~165 字）。
# 创新点比问题分析长是**对的**：它要写「做了什么 + 带来什么实质改进」，参考件里每条还会
#   引一个关键数字当证据。别拿 3 行去卡它 —— 那比参考件还紧。
ANALYSIS_INNO_MAX_LINES = 5
ANALYSIS_INNO_CHARS_FAIL = ANALYSIS_PER_LINE * ANALYSIS_INNO_MAX_LINES
# ★ **下限是硬的，而且它才是关键的一条**：上限只能拦住"写太长"，拦不住"只写一句"。
#   只写一句（≈2 行）时所有上限都满足 ⇒ **"复用了旧稿没改"与"复用了且合规"在机械上无法区分**，
#   阶段重跑几次都看不出问题。参考件每条 4~5 行，取 3 行当地板。
ANALYSIS_INNO_MIN_LINES = 3
ANALYSIS_INNO_CHARS_MIN = ANALYSIS_PER_LINE * ANALYSIS_INNO_MIN_LINES


def _strip_comment(line):
    """去掉 LaTeX 行内注释 —— 骨架的约束全写在注释里，但它们不是标题。"""
    out, i = [], 0
    while i < len(line):
        if line[i] == "%" and (i == 0 or line[i - 1] != "\\"):
            break
        out.append(line[i])
        i += 1
    return "".join(out)


def _prose_len(text):
    """一把尺子：去掉注释与 LaTeX 命令后数**字**（汉字、数字、拉丁词各算一个字符）。

    假设节（每条 ≤200 字）与问题分析节（全节 ≤1320 字）共用它 —— 阈值之所以能写成
    "页"，靠的是一份**页↔字**换算（见 `ANALYSIS_CHARS_PER_PAGE`：989 字/页）。
    """
    text = "\n".join(_strip_comment(l) for l in text.splitlines())
    text = re.sub(r"\\[a-zA-Z]+\*?(\[[^\]]*\])?(\{[^{}]*\})*", "", text)
    return len(re.sub(r"[\s${}\\]", "", text))


def _balanced(text, start):
    """从 `{` 后取到配对的 `}`（标题里会有 `\\textbf{}` 这类嵌套）。"""
    depth, i, out = 1, start, []
    while i < len(text):
        ch = text[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return "".join(out)
        out.append(ch)
        i += 1
    return "".join(out)


def headings_of(path):
    """一个 .tex 文件里的标题序列：[(层级, 标题原文)]，按出现顺序。"""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    text = "\n".join(_strip_comment(l) for l in text.splitlines())
    out, pos = [], 0
    while True:
        m = HEADING_RE.search(text, pos)
        if not m:
            break
        title = _balanced(text, m.end()).strip()
        out.append((LEVELS[m.group(1)], re.sub(r"\s+", " ", title)))
        pos = m.end()
    return out


def items_of(path):
    """`\\item` 的正文（已去注释、去空白），用于「条数 3–6、每条不长」。"""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    text = "\n".join(_strip_comment(l) for l in text.splitlines())
    heads = [m.start() for m in re.finditer(r"\\item\b", text)]
    return [re.sub(r"\s+", " ", text[a:b]).strip()
            for a, b in zip(heads, heads[1:] + [len(text)])]


def _skeletons(root):
    """所有模板族的骨架：{族名: {文件名: [(层级, 标题)]}}。"""
    base = root / TEMPLATES_REL
    out = {}
    if not base.is_dir():
        return out
    for main in sorted(base.glob("*/*/main.tex")):
        fam = main.parent.relative_to(base).as_posix()
        sec = main.parent / "sections"
        if not sec.is_dir():
            continue
        out[fam] = {p.name: headings_of(p) for p in sorted(sec.glob("*.tex"))}
    return out


PROBLEM_FILE_RE = re.compile(r"^5_problem(\d+)\.tex$")
PROBLEM_TOKEN_RE = re.compile(r"问题[一二三四五六七八九十\d]+")
# 文件名用阿拉伯数字（`5_problem4.tex`），正文标题用汉字（「问题四的…」）——
# 展开期望骨架时要把 `4` 换成 `四`，否则比对必然不等。
_CN_DIGITS = "零一二三四五六七八九"


def _cn_num(n):
    if n < 10:
        return _CN_DIGITS[n]
    if n < 20:
        return "十" + (_CN_DIGITS[n % 10] if n % 10 else "")
    return "".join(_CN_DIGITS[int(d)] for d in str(n))
# 模板里标注为「**选加**」的小节（`(选加5.1.5 结果分析)`）—— 骨架的样例文件
# 未必每个都带它（`5_problem1.tex` 就没有、`5_problem3.tex` 有），所以：
# 实际里出现它**不算多出**，不出现**也不算缺**。
OPTIONAL_HEADINGS = {"结果分析"}


def _expand_problem_sections(skel, actual):
    """`5_problem4.tex` 这类**按题面子问题数往后加**的节，骨架里本来就只有样例。

    模板 `main.tex` 的注释：「题目不止三问时按同样的命名往后加 `5_problem4…`；
    子问题数由题面决定，不硬凑。」—— 所以实际出现的 `5_problemN`（N≥2）即使骨架里没有，
    也**不算多出**；它的期望骨架取 `5_problem1.tex`，把其中的「问题一」换成「问题N」比对。
    """
    skel = dict(skel)
    sample = skel.get("5_problem1.tex")
    if sample:
        for name in actual:
            m = PROBLEM_FILE_RE.match(name)
            if not m or name in skel:
                continue
            token = f"问题{_cn_num(int(m.group(1)))}"
            skel[name] = [(lvl, PROBLEM_TOKEN_RE.sub(token, title)) for lvl, title in sample]
    return skel


# 「问题三的分析」→「问题N的分析」：子问题数是**题面定的**，模板里的三只是举例
# （有几个问题就写几个问题分析，不固定死）。
# 若照抄模板只写到「问题三的分析」，题面四问时问题四的分析会整节漏掉 ——
# 而两边都是三节，逐条比对反而看不出问题。故此处既做归一（形状比对不误报「多出」），
# 又另设 `_question_count_problems` 按子问题数核**条数**。
QNUM_RE = re.compile(r"问题[零一二三四五六七八九十百\d]+")
QHEAD_RE = re.compile(r"^问题[零一二三四五六七八九十百\d]+的")


def _norm_title(t):
    return QNUM_RE.sub("问题N", t)


def _collapse(titles):
    """相邻且归一后相同的标题合成一项（`问题一/二/三的分析` → 一项「问题N的分析」）。"""
    out = []
    for t in titles:
        n = _norm_title(t)
        if not out or out[-1] != n:
            out.append(n)
    return out


def _same_headings(expected, actual):
    """两个标题序列算不算「一致」—— 「选加」的小节两边都不计（见 OPTIONAL_HEADINGS）。"""
    e = _collapse([t for _, t in expected if t not in OPTIONAL_HEADINGS])
    a = _collapse([t for _, t in actual if t not in OPTIONAL_HEADINGS])
    return e == a


def _diff(expected, actual, label, problems):
    """逐条比对两个标题序列，报「多了 / 少了 / 改名 / 顺序」。

    比对用的是**归一 + 合并后的形状**（见 `_collapse`）：`问题一/二/三的分析` 在骨架里
    只是举例，实际写到「问题四的分析」不该被判「多出」。真正的条数由
    `_question_count_problems` 按子问题数核。
    """
    e, a = [t for _, t in expected], [t for _, t in actual]
    if _collapse(e) == _collapse(a):
        return
    e_cmp = _collapse([t for t in e if t not in OPTIONAL_HEADINGS])
    a_cmp = _collapse([t for t in a if t not in OPTIONAL_HEADINGS])
    if e_cmp == a_cmp:
        return
    if set(e_cmp) == set(a_cmp):
        problems.append(f"{label}: 标题齐全但**顺序**与骨架不同 —— 骨架给的是 "
                        f"{' → '.join(e_cmp)}")
        return
    for t in e_cmp:
        if t not in a_cmp:
            problems.append(f"{label}: **缺**骨架给定的标题「{t}」")
    for t in a_cmp:
        if t not in e_cmp:
            problems.append(f"{label}: **多出**骨架里没有的标题「{t}」（骨架是给定的，"
                            f"只能往它里面填内容）")


def skeleton_issues(root):
    """比对 `paper/sections/*.tex` 与模板骨架。返回问题串列表（空 = 通过）。"""
    root = Path(root).resolve()
    skels = _skeletons(root)
    if not skels:
        return [f"找不到模板骨架：{TEMPLATES_REL}/<语言>/<族名>/sections/ 下没有 .tex"]
    actual_dir = root / PAPER_SECTIONS_REL
    if not actual_dir.is_dir():
        return [f"找不到正文小节目录：{PAPER_SECTIONS_REL}"]
    actual = {p.name: headings_of(p) for p in sorted(actual_dir.glob("*.tex"))}
    if not actual:
        return [f"{PAPER_SECTIONS_REL}/ 下没有 .tex"]

    for raw in skels.values():
        skel = _expand_problem_sections(raw, actual)
        if set(skel) == set(actual) and all(_same_headings(skel[k], actual[k]) for k in skel):
            # 骨架对得上 → 只报「骨架之外」的版式问题（假设条数/长度、符号表列数），
            # 不套「与骨架对不上」那句标题（否则读起来像骨架又错了）。
            return (_assumption_problems(root) + _symbols_problems(root)
                    + _table_pairing_problems(root) + _wording_problems(root)
                    + _topic_label_problems(root) + _nested_cell_problems(root)
                    + _question_count_problems(root) + _analysis_length_problems(root)
                    + _roadmap_placement_problems(root)
                    + _figure_pairing_problems(root) + _caption_problems(root))
    # 都不完全一致 → 报**最接近**那一族的差异（差得最少 = 最可能是它）
    def distance(item):
        _, raw = item
        s = _expand_problem_sections(raw, actual)
        return sum(1 for k in set(s) | set(actual) if s.get(k) != actual.get(k))
    fam, skel = min(skels.items(), key=distance)
    skel = _expand_problem_sections(skel, actual)
    problems = [f"正文小节与模板骨架 `{fam}/sections/` 对不上："]
    for name in sorted(set(skel) | set(actual), key=lambda n: (n not in skel, n)):
        if name not in actual:
            problems.append(f"  · **缺文件** {name}（骨架里有）")
        elif name not in skel:
            problems.append(f"  · **多出文件** {name}（骨架里没有）")
        else:
            _diff(skel[name], actual[name], f"  · {name}", problems)
    problems += (_assumption_problems(root) + _symbols_problems(root)
                 + _table_pairing_problems(root) + _wording_problems(root)
                 + _topic_label_problems(root) + _nested_cell_problems(root)
                 + _question_count_problems(root) + _analysis_length_problems(root)
                 + _roadmap_placement_problems(root)
                 + _figure_pairing_problems(root) + _caption_problems(root))
    return problems


SYMBOLS_FILE_RE = re.compile(r"^\d+_symbols?\.tex$")
SYMBOLS_HEADER = ("符号", "含义", "单位")
# 单位列该写什么：纯 ASCII/数学的单位串（`kg/m$^3$`、`J/(kg$\cdot$K)`、`m$^{-2}$`）。
# 允许「无量纲」这个中文特例。含义列里整段括号只有这种内容 = 单位本该另立一列。
_UNIT_ONLY_RE = re.compile(r"^(?:无量纲|[A-Za-z0-9/^.\-\\{}$\u00b7,; ]+)$")
_PAREN_RE = re.compile(r"（([^（）]*)）")
_TABLE_BEGIN_RE = re.compile(r"\\begin\{(longtable|tabular)\}")
_TABLE_END_RE = re.compile(r"\\end\{(longtable|tabular)\}")


def _table_blocks(text):
    """取出所有 `longtable`/`tabular` 环境的**列格式**、**表体文本**与**在原文中的位置**。"""
    out, pos = [], 0
    while True:
        m = _TABLE_BEGIN_RE.search(text, pos)
        if not m:
            return out
        # m.end() 指向列格式的 `{`，其内容由 _balanced 取出（列型如 L{0.19\textwidth} 会嵌套）
        spec = _balanced(text, m.end() + 1)
        body_start = m.end() + len(spec) + 2          # 跳过 `{colspec}`
        end = _TABLE_END_RE.search(text, body_start)
        if not end:
            return out
        body = text[body_start:end.start()]
        # 表体里的子环境（如 aligned）会带 `&`，先整体拿掉避免污染列计数
        body = re.sub(r"\\begin\{[^}]*\}.*?\\end\{[^}]*\}", "", body, flags=re.S)
        body = body.replace(r"\&", "\x00")
        for rule in (r"\endfirsthead", r"\endhead", r"\endfoot", r"\endlastfoot",
                     r"\toprule", r"\midrule", r"\bottomrule", r"\addlinespace"):
            body = body.replace(rule, "")
        out.append((spec, body, m.start(), end.end()))
        pos = end.end()


def _cell_text(cell):
    """一格里的可见文字：去掉 `\\textbf{}` 这类命令，只留内容（`\\textbf{符号}` → `符号`）。"""
    out = re.sub(r"\\[a-zA-Z]+\*?", "", cell)
    return re.sub(r"\s+", "", out).strip("{}").strip()


def _table_rows(body):
    """按 `\\\\` 切行，保留含 `&` 的那些；单元格原文已还原 `\\&`。"""
    rows = []
    for seg in body.split(r"\\"):
        seg = seg.strip()
        if "&" not in seg:
            continue
        rows.append([c.replace("\x00", r"\&").strip() for c in seg.split("&")])
    return rows


def _column_count(spec):
    """列格式里数出列数：`@{}`/`|`/`>{\\raggedright}` 不是列；`L{0.19\\textwidth}`/`p{2cm}` 各算一列。"""
    n, i = 0, 0
    while i < len(spec):
        ch = spec[i]
        if ch in "lcrXpmbLCR":
            n += 1
            i += 1
            if i < len(spec) and spec[i] == "{":      # 带参列型：`{...}` 是列宽，不是列
                i += len(_balanced(spec, i + 1)) + 2
        elif ch in ">|@!":                            # 前置修饰 `@{}`、`>{\raggedright...}`
            if i + 1 < len(spec) and spec[i + 1] == "{":
                i += len(_balanced(spec, i + 2)) + 3  # 跳过 `X{内容}`
            else:
                i += 1
        else:
            i += 1
    return n


# 标题下、第一个环境之前，允许多少**散文**字。口径是「标题下直接出表」⇒ 本该是 0；
# 给 8 个字的余量是因为那一小段里合法地会出现「表 1 符号说明」这种**表题行**（5 个汉字）。
# 判据只数**散文**（见 `_prose_chars`），不数排版代码 —— 那些是必需的排版命令，删不得。
PROSE_HEAD_MAX = 8


def _prose_chars(text):
    """只数**散文**字数：去掉 LaTeX 命令/花括号骨架/可选参数后剩下的中日韩文字。

    为什么必须这么数：`4_symbols.tex` 的表**必须**把
      `\\setlength{\\LTleft}{\\fill}`、居中表题行 `{\\centering…}`、`\\nopagebreak`、`\\vspace`
      放在 `\\begin{longtable}` **之前**（表题放进表内会被压成 5.5pt，见模板注释），删不掉。
      按"非注释行**总字数** > 40"判 ⇒ **按模板写的任何一份都判不过**（模板自己就 297 字，
      逐字都是排版代码），既误报，又会让人去删表题/间距补丁
      （那会把符号表压坏）。改成只数散文之后：真有一段总述 ⇒ 照样报；只有排版代码 ⇒ 不报。
    """
    t = re.sub(r"\\[A-Za-z@]+\*?", " ", text)        # \command / \command*
    t = re.sub(r"\[[^\]]*\]", " ", t)                # [可选参数]
    t = re.sub(r"[{}$&_^~]", " ", t)                 # 骨架与数学上下标
    t = re.sub(r"\d+(?:\.\d+)?", " ", t)             # 数字（表号、字号）不算散文
    return "".join(re.findall(r"[\u4e00-\u9fff][\u4e00-\u9fff，。；：、（）《》…—·]*", t))


def _symbols_problems(root):
    """`*_symbols.tex` 里那张表：必须三列、第三列表头是「单位」、单位不塞进含义的括号。"""
    d = Path(root) / PAPER_SECTIONS_REL
    if not d.is_dir():
        return []
    files = [p for p in sorted(d.glob("*.tex")) if SYMBOLS_FILE_RE.match(p.name)]
    problems = []
    for p in files:
        text = "\n".join(_strip_comment(l) for l in
                         p.read_text(encoding="utf-8", errors="replace").splitlines())
        # **标题下不写开头总述段**（不要开头总结）：
        #   形如「除特别说明外，温度用摄氏度…全文所用符号的含义与单位汇总于表 1。」的
        #   总述/元话语不是符号说明；读者要的是表。单位口径确要交代就写表注或正文。
        #   判据：`\section{符号说明}` 之后、第一个环境/表格之前，不该有**非注释的成段文字**。
        _after = text.split("\\section", 1)[-1]
        _after = _after.split("}", 1)[-1] if "}" in _after else _after
        _head = re.split(r"\\begin\{|\n\s*\\\\", _after, maxsplit=1)[0]
        _para = [l for l in _head.splitlines() if l.strip()]
        _prose = _prose_chars("".join(_para))
        if len(_prose) > PROSE_HEAD_MAX:
            problems.append(
                f"{p.name}: 标题下有一段的开头总述（约 {len(_prose)} 字散文）—— "
                f"用户 2026-09-27 明确要求**不要开头总结**，标题下直接出表；"
                f"单位口径若确要交代，写进表注或正文该量出现处")
        blocks = _table_blocks(text)
        if not blocks:
            continue                    # 没表格：交给骨架/人工，不在本检查的能力范围
        spec, body = max(blocks, key=lambda b: len(b[1]))[:2]
        rows = _table_rows(body)
        if not rows:
            continue
        ncol = _column_count(spec)
        header = [_cell_text(c) for c in rows[0]]
        shown = " / ".join(header) or "（未读到表头）"
        if len(header) != ncol:
            problems.append(f"{p.name}: 列格式写了 {ncol} 列、表头只有 {len(header)} 格"
                            f"（「{shown}」）—— 两者对不上，先对齐列格式与表头")
            continue
        if ncol != 3:
            problems.append(
                f"{p.name}: 符号表是 **{ncol} 列**（表头「{shown}」）—— 参考件"
                f" `基于变物性耦合传热传质与动域模型的.pdf` 是**三列**，列头依次为"
                f"「符号 / 含义 / 单位」，**单位单独成列**（不要塞进含义的括号里）")
            continue
        if "单位" not in header[2]:
            problems.append(f"{p.name}: 符号表第 3 列表头是「{header[2]}」，参考件是「单位」——"
                            f" 单位该独占一列，列头就写「单位」")
            continue
        for n, cells in enumerate(rows[1:], 1):
            if len(cells) != 3:
                problems.append(f"{p.name}: 第 {n} 行 {len(cells)} 格，应为 3 格"
                                f"（符号 & 含义 & 单位）—— 一行里每格一个 `&`")
                continue
            if not cells[2].strip():
                problems.append(f"{p.name}: 第 {n} 行（{cells[0]}）**单位列为空** ——"
                                f" 无量纲也要写明「无量纲」")
            for inner in _PAREN_RE.findall(cells[1]):
                if _UNIT_ONLY_RE.match(inner.strip()):
                    problems.append(
                        f"{p.name}: 第 {n} 行（{cells[0]}）把单位「{inner.strip()}」"
                        f"写进了含义列的括号里 —— 移到**单位列**，含义列只写「是什么」")
                    break
    return problems


FLOAT_BEGIN_RE = re.compile(r"\\begin\{table\}")
FLOAT_END_RE = re.compile(r"\\end\{table\}")
THREELINE_RE = re.compile(r"\\threelinetable")
TABLE_NUM_RE = re.compile(r"表\s*\d+")
SECTION_SPLIT_RE = re.compile(r"\\(?:sub)*section\*?\{")


def _three_line_units(text):
    """`\\threelinetable{表题}{列格式}{表头}{表体}` 调用 → 表单元。

    这是本项目**最常用的建表方式**，它产出 `center` + `tabular`、**没有浮动体**，
    所以只扫 `\\begin{table}` 会整片漏掉（正文里 `table` 浮动体可能一个都没有，
    全靠这个宏）。
    """
    out = []
    for m in THREELINE_RE.finditer(text):
        i = m.end()
        groups = []
        for _ in range(4):
            while i < len(text) and text[i] in " \t\r\n":
                i += 1
            if i >= len(text) or text[i] != "{":
                break
            g = _balanced(text, i + 1)
            groups.append(g)
            i += len(g) + 2
        if len(groups) == 4:
            # 行数要按「表头 + 表体」算：宏把表头单独当第 3 个参数，而手写的 tabular
            # 把表头写在体内 —— 只数表体的话，宏建的表永远比手写的少一行，两者比不到一起。
            nrows = len([r for r in _table_rows(groups[2]) + _table_rows(groups[3])
                         if len(r) > 1])
            out.append({"start": m.start(), "end": i, "specs": [groups[1].strip()],
                        "rows": [nrows]})
    return out


def _table_units(text):
    """按文档顺序列出所有**表单元**：`table` 浮动体 / `\\threelinetable` / 裸 tabular。

    每单元给出内含的 tabular 列格式与数据行数。含 **两张** tabular 的浮动体
    （即已经用 minipage 并排过的）也算一个单元，但 `len(specs) > 1` 会让并排判断跳过它。
    """
    masked, units = list(text), []
    for m in re.finditer(r"\\begin\{table\}[\s\S]*?\\end\{table\}", text):
        specs, rows = [], []
        for spec, body, _, _ in _table_blocks(m.group(0)):
            specs.append(spec)
            rows.append(len([r for r in _table_rows(body) if len(r) > 1]))
        units.append({"start": m.start(), "end": m.end(), "specs": specs, "rows": rows})
        for i in range(m.start(), m.end()):
            masked[i] = " "                   # 挖掉，免得下面的裸 tabular 重复计数
    for u in _three_line_units(text):
        units.append(u)
        for i in range(u["start"], min(u["end"], len(masked))):
            masked[i] = " "
    holey = "".join(masked)
    for spec, body, a, b in _table_blocks(holey):
        units.append({"start": a, "end": b, "specs": [spec],
                      "rows": [len([r for r in _table_rows(body) if len(r) > 1])]})
    return sorted(units, key=lambda u: u["start"])


def _norm_spec(spec):
    """列格式归一，只为了让**写法不同、含义相同**的两种列格式能比到一起。

    - `@{}` 只影响边缘留白，去掉；
    - `*{5}{c}` 与 `ccccc` 是同一件事，展开；
    - `\\threelinetable` 惯写 `@{}c*{5}{c}@{}`，而手写的 `tabular` 常写 `cccccc` ——
      不归一的话，「宏建的表」与「手写的表」永远比不到一起。
    """
    s = re.sub(r"\s+", "", spec)
    s = s.replace("@{}", "")
    while True:
        m = re.search(r"\*\{(\d+)\}\{([^{}]*)\}", s)
        if not m:
            return s
        s = s[:m.start()] + m.group(2) * int(m.group(1)) + s[m.end():]


def _table_num(blk):
    m = TABLE_NUM_RE.search(blk)
    return m.group(0).replace(" ", "") if m else "（无表号）"


def _table_pairing_problems(root):
    """两张**同构**的表各自独占一处 → 该并排（两个 `papertablehalf` 装进一个 `table`）。

    判据照参考件 `基于变物性耦合传热传质与动域模型的.pdf` 自己的做法反推，
    三条同时成立才报：

    1. 两个表单元在文档里**相邻**，且中间没有 `\\section`/`\\subsection`（隔了小标题就不是一处）；
    2. 各自**只含一张** tabular —— 已经用 minipage 并排过的单元含两张，自动跳过；
    3. 两张的**列格式与数据行数完全相同** —— 即同一张网格的两种量。

    参考件里：表 2/表 3（温度 / 水分浓度）列格式同为 `cccccc`、行数同 → **并排**；
    表 6/表 7、表 8/表 9 的列格式不同（`L{0.38}L{0.58}` vs `cccccc`）→ **不并排**。
    生成稿把 4 对温度/水分表全拆成独立表，白占约一页高度（正文超页的主因之一）。
    """
    d = Path(root) / PAPER_SECTIONS_REL
    if not d.is_dir():
        return []
    problems = []
    for p in sorted(d.glob("*.tex")):
        text = "\n".join(_strip_comment(l) for l in
                         p.read_text(encoding="utf-8", errors="replace").splitlines())
        units = _table_units(text)
        for a, b in zip(units, units[1:]):
            if len(a["specs"]) != 1 or len(b["specs"]) != 1:
                continue                      # 已并排，或不是「单表单元」
            if (_norm_spec(a["specs"][0]) != _norm_spec(b["specs"][0])
                    or a["rows"] != b["rows"]):
                continue                      # 列结构/行数不同 —— 不是同一张网格，并排会挤
            if SECTION_SPLIT_RE.search(text[a["end"]:b["start"]]):
                continue                      # 中间隔了小标题 —— 不属同一处
            problems.append(
                f"{p.name}: {_table_num(text[a['start']:a['end']])} 与 "
                f"{_table_num(text[b['start']:b['end']])} **列结构与行数完全相同**，"
                f"却各占一处 —— 这是同一张网格的两种量，应**并排**放进同一个 `table`"
                f"（两个 `papertablehalf` 环境、中间 `\\hfill`），可省约一页高度")
    return problems


# 全文不要引号：直的、弯的、直角的全在内。
QUOTE_RE = re.compile(r'["“”「」『』]|``|\'\'')
# 解释型括号：括号里是补充/限定/对比/点名/换算，而不是单位或首次定义。
# 只收能枚举的几种字面（而非…、一律…、只在…成立、…档、单位：），不做语义判断，
# 所以不会误伤 `（kg/m$^3$）` 之外的正常括号 —— 代价是漏报，可以接受。
#
# `档` 不能写成 `\d+\s*档`（要求档字前有数字）⇒ 那样 **`（对照档）`、`（主档）`
#   一个都抓不到**，而这两处正是会写进摘要的形态。9Paper-writing 的硬判据④原文是
#   「…档」这类补充/限定/对比小句，**没限定必须有数字**；要求数字就是把判据收窄了。
#   现在 `档` 单字命中：合法括号里不会出现「档」（它是档位/口径的专名），误报面可以忽略。
EXPLAIN_PAREN_RE = re.compile(r"（[^）]{0,40}(?:而非|一律|只在|仅当|只对|单位：|档)[^）]{0,40}）")


def _topic_label_problems(root):
    """段首加粗标签**不许以句号收尾**。

    反例：「6.1 这里 守恒校核。网格与步长收敛。离散化误差的量化。——」这类每段开头的
    没用的总结句。

    规则出处：`skills/9Paper-writing/SKILL.md` 的「段落不要用『（一）……。』这种概括句开头」——
    括号编号换掉之后，终止符只给了**举例**（正例 `\\textbf{时间方向的离散误差：}`、
    反例 `\\textbf{（一）不是刀刃解。}`）；只抓"段首加粗"这个形态、**不把句号当违规信号**
    就会漏掉。
    判据（零误报）：段落（空行分隔）去掉前导空白后以 `\\textbf{...}` / `\\emph{...}` 开头，
    且大括号内**最后一个字符是全角句号 `。`** ⇒ 报。冒号收尾放行、无标签放行。
    """
    d = Path(root) / PAPER_SECTIONS_REL
    if not d.is_dir():
        return []
    lead = re.compile(r"^\s*\\(?:textbf|emph)\{([^{}]{1,40})\}")
    hits = []
    for p in sorted(d.glob("*.tex")):
        text = "\n".join(_strip_comment(l) for l in
                         p.read_text(encoding="utf-8", errors="replace").splitlines())
        for para in text.split("\n\n"):
            m = lead.match(para)
            if m and m.group(1).rstrip().endswith("。"):
                hits.append(f"{p.name}: 段首标签以句号收尾 —— 「{m.group(1)}」"
                            f"（用户 2026-09-27 明确要求：段首标签用名词短语 + 全角冒号，"
                            f"句号收尾的就是被禁的「总结的一句话」）")
    return hits


def _nested_cell_problems(root):
    """表格源码里 `\\begin{tabular}` 的嵌套深度必须 = 1（**格内不许再套 tabular**）。

    格内嵌套 tabular 不带位置参数时，会在行的基线上**竖直居中** ⇒
    同行数据落在两行中间（表 6 偏 8.58pt、表 7 偏 8.58pt，正常行距 18.x pt），
    看上去就是「烘干结束时间下面那一排数字不对齐」。唯一正确写法是带 `[t]`（或模板宏 `\\twolinecell`）。
    """
    d = Path(root) / PAPER_SECTIONS_REL
    if not d.is_dir():
        return []
    problems = []
    for p in sorted(d.glob("*.tex")):
        depth = 0
        for n, raw in enumerate(p.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            line = _strip_comment(raw)
            opens = len(re.findall(r"\\begin\{(?:tabular|longtable|tabularx)\}", line))
            closes = len(re.findall(r"\\end\{(?:tabular|longtable|tabularx)\}", line))
            if depth + opens > 1:
                problems.append(f"{p.name}:{n}: 表格里嵌套了第二层 tabular —— "
                                f"改用模板宏 `\\twolinecell{{第一行}}{{第二行}}`（或带 `[t]` 的嵌套）"
                                f"；不带位置参数的嵌套会在基线上竖直居中，把同行数据挤到两行中间 ✗")
            depth += opens - closes
    return problems


def _wording_problems(root):
    """措辞两条硬规矩：**全文不出现引号**、**括号里不许写解释**。

    两条都是**全文**口径。只报**非注释行**（注释里的例子不算），
    每条给行号与原文，便于逐处改。

    摘要也要扫：摘要住在 `paper/main.tex`、**不在**
      `paper/sections/` 下。只扫 `paper/sections/` 的话，写在摘要里的
      `（对照档）`/`（主档）` 这类解释型括号根本扫不到，判据等于没生效。
      这里把 `main.tex` 一并纳入。
    """
    d = Path(root) / PAPER_SECTIONS_REL
    files = list(sorted(d.glob("*.tex"))) if d.is_dir() else []
    main_tex = Path(root) / "paper" / "main.tex"
    if main_tex.is_file():
        files.append(main_tex)
    if not files:
        return []
    problems = []
    for p in files:
        quotes, parens = [], []
        for n, raw in enumerate(p.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            line = _strip_comment(raw)
            if not line.strip():
                continue
            if QUOTE_RE.search(line):
                quotes.append((n, line.strip()))
            m = EXPLAIN_PAREN_RE.search(line)
            if m:
                parens.append((n, m.group(0)))
        if quotes:
            shown = "；".join(f"L{n} {t[:34]}" for n, t in quotes[:3])
            problems.append(
                f"{p.name}: {len(quotes)} 处**引号**（全文不要引号，「」『』与弯引号都在内）—— "
                f"要强调用粗体、要引用原件题名用书名号。例：{shown}")
        if parens:
            shown = "；".join(f"L{n} {t}" for n, t in parens[:3])
            problems.append(
                f"{p.name}: {len(parens)} 处**解释型括号**（括号只放单位与首次定义，"
                f"解释/限定/对比/点名一律不要）—— 例：{shown}")
    return problems


def _question_count_problems(root):
    """`2_analysis.tex` 里「问题N的分析」的**条数**必须等于题面的子问题数。

    子问题数从 `5_problemN.tex` 的文件名取（编号 1..Q，取最大者）—— 这是本项目里
    子问题数的唯一机械来源。模板 `2_analysis.tex` 只写了三节作**举例**，不是固定三节。
    题目四问而正文只有三节分析时，问题四会整节漏掉。
    """
    d = Path(root) / PAPER_SECTIONS_REL
    analysis = d / ANALYSIS_FILE
    if not analysis.is_file():
        return []
    qs = [int(m.group(1)) for p in d.glob("5_problem*.tex")
          if (m := PROBLEM_FILE_RE.match(p.name))]
    if not qs:
        return []
    want = max(qs)
    got = [t for _, t in headings_of(analysis) if QHEAD_RE.match(t)]
    if len(got) == want:
        return []
    missing = [f"问题{_cn_num(n)}" for n in range(1, want + 1)
               if not any(QNUM_RE.search(t) and _cn_num(n) in t for t in got)]
    detail = (f"缺 {'、'.join(missing)} 的分析" if missing
              else f"多出 {len(got) - want} 节")
    return [f"{ANALYSIS_FILE}: 有 {len(got)} 节问题分析（{'、'.join(got)}），"
            f"但正文有 {want} 个问题（`5_problem1…{want}.tex`）—— {detail}。"
            f"模板里「问题一/二/三的分析」是**举例**，题面有几问就写几节，"
            f"一节不缺、一节不多"]


def _analysis_sections(text):
    """把 `2_analysis.tex` 切成 (小节名, 正文)；标题下那段算「（标题下总述）」。"""
    key, cuts, pos = "\\subsection{", [], 0
    while True:
        i = text.find(key, pos)
        if i < 0:
            cuts.append(("（标题下总述）", text[pos:]))
            break
        if i > pos:
            cuts.append(("（标题下总述）", text[pos:i]))
        j = text.find("}", i)
        k = text.find(key, j)
        cuts.append((text[i + len(key):j], text[j + 1: k if k > 0 else len(text)]))
        if k < 0:
            break
        pos = k
    return cuts


def _analysis_pieces(title, body):
    """一个小节里要**分别**计量哪几段，各段的上限是多少 —— 返回 `(名字, 正文, 上限)`。

    普通小节整段算一条，上限 3 行；`本文主要创新点` 里装的是多条，按「创新点X：」逐条算
    —— 否则三条各 4~5 行的创新点合起来会被当成"这个小节超了"。创新点上限放宽到 5 行，
    理由见 `ANALYSIS_INNO_CHARS_FAIL` 那段注释。
    """
    if "创新点" in title:
        parts = body.split("\\textbf{创新点")[1:]
        if parts:
            return [(f"{title} 第{_cn_num(i + 1)}条", s, ANALYSIS_INNO_CHARS_FAIL)
                    for i, s in enumerate(parts)]
    return [(title, body, ANALYSIS_SUB_CHARS_FAIL)]


def _analysis_detail(cuts):
    return "、".join(f"{t} {_prose_len(b)} 字" for t, b in cuts if _prose_len(b))


def _analysis_length_problems(root):
    """`2_analysis.tex` 的篇幅：**全节 ≤ 一页**、**每个问题的分析 ≤ 3 行**。

    两个上限都按参考件量出来（见 `ANALYSIS_CHARS_PER_PAGE` 那段注释）。量不了页数就量
    字数，换算基准是 989 字/页、33 字/行。

    超了要报**分节明细**：只说"整节太长"，写手不知道该砍哪一段 —— 而超额的通常正是
    每一问的分析。
    """
    p = Path(root) / PAPER_SECTIONS_REL / ANALYSIS_FILE
    if not p.is_file():
        return []
    text = p.read_text(encoding="utf-8", errors="replace")
    cuts = _analysis_sections(text)
    problems = []

    n = _prose_len(text)
    if n > ANALYSIS_CHARS_FAIL:
        problems.append(
            f"{ANALYSIS_FILE}: 全节约 {n} 字 ≈ {n / ANALYSIS_CHARS_PER_PAGE:.2f} 页，"
            f"**超一页半上限**（> {ANALYSIS_CHARS_FAIL} 字判超）。分节：{_analysis_detail(cuts)}")
    elif n > ANALYSIS_CHARS_WARN:
        problems.append(
            f"{ANALYSIS_FILE}: 全节约 {n} 字 ≈ {n / ANALYSIS_CHARS_PER_PAGE:.2f} 页，偏长"
            f"（> {ANALYSIS_CHARS_WARN} 字提醒；> {ANALYSIS_CHARS_FAIL} 判超）。"
            f"分节：{_analysis_detail(cuts)}")

    for title, body in cuts:
        for name, piece, limit in _analysis_pieces(title, body):
            k = _prose_len(piece)
            # 空占位符（模板里的 `\textbf{创新点一：}` 后面还没写字）不算"写太短" —— 那是没写。
            if "创新点" in name and 0 < k < ANALYSIS_INNO_CHARS_MIN:
                problems.append(
                    f"{ANALYSIS_FILE}: {name} 约 {k} 字 ≈ {k / ANALYSIS_PER_LINE:.1f} 行，"
                    f"**不足 {ANALYSIS_INNO_MIN_LINES} 行**（< {ANALYSIS_INNO_CHARS_MIN} 字判短）。"
                    f"创新点只写一句撑不起这一节：写清「做了什么 + 带来什么实质改进」，"
                    f"并引一个关键数字当证据（参考件每条 4~5 行）。")
            elif k > limit:
                lines = limit // ANALYSIS_PER_LINE
                if "创新点" in name:
                    how = ("创新点写「做了什么 + 带来什么实质改进」，可以引一个关键数字当证据，"
                           "但别铺开做结果分析 —— 那是第五节与第六节的事。")
                else:
                    how = ("这一节只写「这一问要什么、难在哪、走什么路线」—— 数字、倍数、量级、"
                           "参数明细都是**结果**，归第五节求解与第六节检验，写在这里既超页又与后面重复。")
                problems.append(
                    f"{ANALYSIS_FILE}: {name} 约 {k} 字 ≈ {k / ANALYSIS_PER_LINE:.1f} 行，"
                    f"**超 {lines} 行上限**（> {limit} 字判超）。{how}")
    return problems


# 四种图命令的**实参表**（照 `skills/9Paper-writing/templates/_base/macros.tex` 抄，别猜）：
#   \paperfigure[宽]{文件}{图注}{标签}
#   \paperfigurepair {左图}{左题}{左标签}{右图}{右题}{右标签}          ← 各占半栏
#   \paperfigurestack{上图}{上题}{上标签}{下图}{下题}{下标签}          ← 上下排，各自编号
#   \paperfigurepairw{左宽}{左图}{左题}{左标签}{右宽}{右图}{右题}{右标签}
# 后三种都要认：只认 `\paperfigure` 的话，写在 pair/stack 里的图注
#   **完全绕开图题检查** —— 而"图题只能是短名词短语/不许报读数"这套规矩对每条图注都成立，
#   绕过去等于白加。双图的每一半各有自己的图注，
#   所以这里**摊平成"子图"**，`_caption_problems` 一行都不用改就覆盖到了。
_FIG_MACROS = {
    "paperfigure": (("file",), ("caption",), ("label",)),
    "paperfigurepair": (("file",), ("caption",), ("label",),
                        ("file",), ("caption",), ("label",)),
    "paperfigurestack": (("file",), ("caption",), ("label",),
                         ("file",), ("caption",), ("label",)),
    "paperfigurepairw": (("width",), ("file",), ("caption",), ("label",),
                         ("width",), ("file",), ("caption",), ("label",)),
}
# 双图半边的**实际**宽度（宏自己写死的）：pair 是 0.49\linewidth，stack 是 0.85\textwidth。
# 记准它是为了让「图 1 必须整栏」那条判据在双图里也说实话（pairw 由实参给，不在这里）。
_GROUP_WIDTH = {"paperfigurepair": r"0.49\textwidth", "paperfigurestack": r"0.85\textwidth"}
_FIG_RE = re.compile(r"\\(paperfigurepairw|paperfigurestack|paperfigurepair|paperfigure)"
                     r"\s*(\[[^\]]*\])?\s*\{")
ROADMAP_ID = "fig_roadmap"
ROADMAP_HOME = "1_restatement.tex"
FULL_WIDTH = r"\textwidth"
# 图 1 的最小栏宽。口径照**参考件**取，不是"整栏"：参考件 `1_restatement.tex:40`
# 写的是 `\paperfigure[0.85\textwidth]{fig_roadmap}{分析流程图}{fig_roadmap}` ——
# **0.85 栏**。`0.7\textwidth` 且放进 `2_analysis.tex` 即属放错。
# 阈值定在 0.85：`\textwidth` 与 `0.85\textwidth` 都收，`0.7` 及以下判缩得太小。
ROADMAP_MIN_WIDTH = 0.85


def _width_factor(width):
    """`\\textwidth` → 1.0；`0.85\\textwidth` → 0.85；绝对宽度（`120mm`）→ None（不判）。"""
    w = (width or "").strip()
    if w == FULL_WIDTH:
        return 1.0
    m = re.fullmatch(r"([0-9]*\.?[0-9]+)\s*\\textwidth", w)
    return float(m.group(1)) if m else None


def _paperfigures(text):
    """文中所有图命令 —— **每个子图一条**：
    `[{width, file, caption, label, start, end, macro, group}]`（已去注释）。

    · `macro`：它由哪条命令画出来的；`group`：属于哪个双图命令（`None` = 独立的一整张）。
    · 摊平成子图是为了让**逐条图注**的检查（`_caption_problems`）不用知道有双图这回事。
    """
    out = []
    for m in _FIG_RE.finditer(text):
        macro = m.group(1)
        i = m.end() - 1                                # 正则把 `{` 也吃进去了，回退一格
        width = (m.group(2) or "").strip("[]").strip() or FULL_WIDTH
        vals = []
        for (name,) in _FIG_MACROS[macro]:
            if i >= len(text) or text[i] != "{":
                vals = []
                break
            g = _balanced(text, i + 1)
            vals.append((name, g.strip()))
            i += len(g) + 2
        if not vals:
            continue                                   # 参数没读全（写坏了）⇒ 当作没这张图
        cur = {"width": _GROUP_WIDTH.get(macro, width)}
        for name, v in vals:
            cur[name] = v
            if name == "label":                        # 「图注 + 标签」= 一张子图收尾
                out.append({**cur, "start": m.start(), "end": i, "macro": macro,
                            "group": None if macro == "paperfigure" else macro})
                cur = {"width": _GROUP_WIDTH.get(macro, width)}
    return out


# ---------------- 图题只能是**短名词短语** ----------------
# 不合格的图题形如：「图 1：分析流程图；图中结果框标注的结果时长为 N=320、
# Δt=60 s 对照档，与正文主档的 57.1661 h 与 50.8238 h 不同档」「图 4：问题1 的温度场与
# 水分浓度场：1800 s 时表面 36.79 °C、中心 33.58 °C」—— 都是把解释塞进了图题。
#
# 根因是**两条规矩打架**（门禁自己的 advisory 都写出来过：
#   「图注一行的纪律 与 图内数字须与正文主档区分 这两条要求目前互相冲突」）：
#     · ⑫ 的合规项要求「图内数字必须与正文主档区分开」 ⇒ 档位说明就被塞进图题；
#     · 而「图注要短、一行」这条只在 SKILL 里以「一行约 40 字」的排版口径出现，
#       **没有任何机械判据**，顺手就写成了一句解释。
#   结果两边都"满足"了，交付的却是一句塞进图题的小作文。
#
# 判据（**内容**而不是纯字数，免得误伤「问题 3 的收敛曲线」这类正常图题）：
#   ① 出现 `；` —— 图题不是分句的地方；
#   ② 数字出现 ≥2 次 —— 图题里不该报读数（读数属于正文或图内标注）；
#   ③ 去掉 LaTeX 命令与空白后超过 40 个字符。
# 口径：档位/主档对照、关键读数这些**一律不进图题** —— 放**图内标注**或**正文**。
MAX_CAPTION_CHARS = 40
# 「图题里不报读数」的判据是**数字带单位**，不是"有几个数字"：
#   按"数字出现 ≥2 次就报"判，「问题 3 与问题 4 的烘干时长对比」有**两个编号**
#   就会被误报（而它正是 `q4_effects` 的正确改法）。
#   编号、尺寸参数、`\cite{}` 里的年份都不该算读数 —— 读数一定有单位。
CAPTION_READING_RE = re.compile(
    r"[0-9]+(?:\.[0-9]+)?\s*(?:h|s|min|℃|°C|K|cm|mm|kg|g|%|倍)")
# 图题里的冒号只该引出**短标签**（「图 2：圆柱形药材的几何…」那种冒号是排版加的，不在 caption 参数里）。
# 冒号后面接一整个小句（≥12 字）就是在图题里写句子了。
CAPTION_CLAUSE_MIN = 12
# 长度统计要剥掉的 LaTeX：`\alpha`、`\,`、`\%`、`\\`、`\{` 全都算排版噪声，不算字
_PLAIN_STRIP_RE = re.compile(r"\\[a-zA-Z]+\s*|\\.|[\s{}$~^_]+")


def _plain_caption(cap):
    """图题去 LaTeX 命令与空白，只留人读得出来的字（判长度用）。

    只剥 `\\字母命令名` 不够：`\\,`、`\\%`、`\\\\`、`\\{` 这些会**残留**进长度统计，
    一个 37 字的图题会被算成 41 字而误报。
    """
    return _PLAIN_STRIP_RE.sub("", cap)


def _cite_stripped(cap):
    """去掉 `\\cite{...}` / `\\ref{...}` / `\\label{...}` 的内容再找读数。

    那些键里带年份/编号（`\\cite{wang2024}`），不剥掉会被当成读数误报。
    """
    return re.sub(r"\\(?:cite|ref|eqref|label|autoref)\s*\{[^}]*\}", "", cap)


def _caption_problems(root):
    """图题必须是**短名词短语**：不许分句解释、不许报读数、不许超长。"""
    d = Path(root) / PAPER_SECTIONS_REL
    files = list(sorted(d.glob("*.tex"))) if d.is_dir() else []
    main_tex = Path(root) / "paper" / "main.tex"
    if main_tex.is_file():
        files.append(main_tex)
    problems = []
    for p in files:
        text = "\n".join(_strip_comment(l) for l in
                         p.read_text(encoding="utf-8", errors="replace").splitlines())
        for fig in _paperfigures(text):
            cap = fig["caption"]
            if not cap:
                continue
            plain = _plain_caption(cap)
            why = []
            if "；" in cap:
                why.append("含分号（图题不是分句的地方）")
            # 读数 = 数字**带单位**。编号（问题 3、图 4）、`\cite{}` 里的年份都不算 ——
            # 用"有几个数字"当判据会把正确图题一起打掉（见 CAPTION_READING_RE 的注释）。
            reads = CAPTION_READING_RE.findall(_cite_stripped(cap))
            if reads:
                why.append(f"报了读数（{'、'.join(reads[:3])}）—— 图题里不给数")
            # 冒号后面接一整个小句 = 在图题里写句子
            m_colon = cap.split("：", 1)
            if len(m_colon) == 2 and len(_plain_caption(m_colon[1])) >= CAPTION_CLAUSE_MIN:
                why.append(f"冒号后接了 {len(_plain_caption(m_colon[1]))} 字的小句（图题只放短标签）")
            if len(plain) > MAX_CAPTION_CHARS:
                why.append(f"去命令后 {len(plain)} 字 > {MAX_CAPTION_CHARS}")
            if why:
                problems.append(
                    f"{p.name}: 图 `{fig['file']}` 的图题不合格 —— {'；'.join(why)}。"
                    f"原图题：「{cap[:70]}{'…' if len(cap) > 70 else ''}」。"
                    f"图题只写**短名词短语**（如「问题 1 的温度场与水分浓度场」）；"
                    f"档位/主档对照、关键读数一律**不进图题** —— 放图内标注或正文"
                    f"（用户 2026-09-28 明确要求，别再塞回图题）")
    return problems


def _roadmap_placement_problems(root):
    """图 1（`fig_roadmap`）必须**正好一次**，放在 `1_restatement.tex`、**整栏**。

    大流程图（图1：分析流程图）该放在问题重述之后、问题分析之前，
    且全文只需要那一个。两种放错：① 整张漏掉；② 塞进 `2_analysis.tex`
    并缩到 `0.7\\textwidth` —— 954×1297 的竖版大图缩到七成栏宽，节点字直接糊掉。
    """
    d = Path(root) / PAPER_SECTIONS_REL
    if not d.is_dir():
        return []
    found, problems = [], []
    for p in sorted(d.glob("*.tex")):
        text = "\n".join(_strip_comment(l) for l in
                         p.read_text(encoding="utf-8", errors="replace").splitlines())
        for f in _paperfigures(text):
            if f["file"] == ROADMAP_ID:
                found.append((p.name, f["width"]))
    if not found:
        return [f"图 1 缺失：正文里没有 `\\paperfigure{{...}}{{{ROADMAP_ID}}}...` ——"
                f" 分析流程图是全文唯一的大图，必须排在**问题重述之后、问题分析之前**"
                f"（即 `{ROADMAP_HOME}` 末尾），栏宽 ≥ `[{ROADMAP_MIN_WIDTH:.2f}{FULL_WIDTH}]`"
                f"（参考件写的就是 `[0.85{FULL_WIDTH}]`）"]
    if len(found) > 1:
        where = "、".join(f"{n}（{w}）" for n, w in found)
        problems.append(f"图 1 出现了 {len(found)} 次（{where}）—— 它只该出现一次")
    for name, width in found:
        if name != ROADMAP_HOME:
            problems.append(f"图 1（{ROADMAP_ID}）放在 `{name}` 里了 ——"
                            f" 该放 `{ROADMAP_HOME}`（问题重述之后、问题分析之前）")
        factor = _width_factor(width)
        if factor is not None and factor < ROADMAP_MIN_WIDTH:
            problems.append(
                f"图 1（{ROADMAP_ID}）是 `[{width}]` = {factor:.2f} 栏 —— 它是全文唯一的大图，"
                f"缩不得（实测缩到 0.70 栏时节点字就糊了）。参考件用的是 "
                f"`[0.85{FULL_WIDTH}]`，照它写")
    return problems


def _figure_pairing_problems(root):
    """两张**同宽、非整栏**的图各占一行 → 该并排（`\\paperfigurepair`）。

    判据比表的并排**弱**（图没有"列结构/行数"这种硬身份），所以取得保守：只报
    「相邻、宽度相同、且都不是整栏、中间没小标题」这一种 —— 这已经是"作者自己也当它们
    是一对"的强信号。整栏图不在此列（它们本来就该独占一行）。

    `\\paperfigurepair`/`\\paperfigurestack` 画出来的**子图一条都不进这里**（`group` 非空就跳过）：
      pair 已经并排了；stack 是**故意**上下排的（两块宽高比差得大，并排会压成扁条，
      见 `macros.tex` 那段注释）⇒ 拿"同宽就该并排"去报它，是**把设计当缺陷**。
    """
    d = Path(root) / PAPER_SECTIONS_REL
    if not d.is_dir():
        return []
    problems = []
    for p in sorted(d.glob("*.tex")):
        text = "\n".join(_strip_comment(l) for l in
                         p.read_text(encoding="utf-8", errors="replace").splitlines())
        figs = _paperfigures(text)
        for a, b in zip(figs, figs[1:]):
            if a["group"] or b["group"]:               # 双图已经摆好了，别再劝它"该并排"
                continue
            if a["width"] != b["width"] or a["width"].strip() == FULL_WIDTH:
                continue
            if SECTION_SPLIT_RE.search(text[a["end"]:b["start"]]):
                continue
            problems.append(
                f"{p.name}: `{a['file']}` 与 `{b['file']}` **同为 `[{a['width']}]`**、"
                f"中间没有小标题，却各占一行 —— 两张同宽的图应**并排**成一个 `\\paperfigurepair`"
                f"（各自独立编号），可省一页高度")
    return problems


def _assumption_problems(root):
    """「篇幅上限：一页；条数 3–6 条，**每条不长**」—— 条数与长度都能机械核。"""
    p = Path(root) / PAPER_SECTIONS_REL / ASSUMPTIONS_FILE
    if not p.is_file():
        return []
    its = items_of(p)
    problems = []
    if its and not (ASSUMPTION_MIN <= len(its) <= ASSUMPTION_MAX):
        problems.append(f"{ASSUMPTIONS_FILE}: 假设 {len(its)} 条，骨架要求 "
                        f"{ASSUMPTION_MIN}–{ASSUMPTION_MAX} 条"
                        f"（用户 2026-09-27：「模型假设最多5条」；篇幅上限一页）")
    # 标题下必须先写引入语再出列表。
    # 只在本节**确实有假设**时才查（没写假设的草稿不该被这条拦）。
    body = "\n".join(_strip_comment(l) for l in p.read_text(encoding="utf-8").splitlines())
    if its and ASSUMPTION_INTRO not in body:
        problems.append(f"{ASSUMPTIONS_FILE}: 缺标题下的引入语 —— 列表前要先写一句"
                        f"「{ASSUMPTION_INTRO}，本文给出如下假设：」（用户 2026-09-27 要求）")
    elif its:
        # 引入语必须**顶格**（照参考件
        #   `框架模板.pdf` / `模型假设.txt`）—— 正文段落的 `\parindent` 会给它缩进两格，
        #   所以这一行要以 `\noindent` 开头。缺了就报，别让它悄悄按正文段落排。
        _line = next((l for l in body.splitlines() if ASSUMPTION_INTRO in l), "")
        if not _line.lstrip().startswith("\\noindent"):
            problems.append(f"{ASSUMPTIONS_FILE}: 引入语没有顶格 —— 该行要以 `\\noindent` 开头"
                            f"（用户 2026-09-27：这句左边不空格；参考件 `框架模板.pdf`）")
    # 条目编号用「假设 N：」、**不要项目符号**（不要「• 假设 1」这种）。
    #   判据：本节不得出现 itemize（那是圆点列表），
    #   且 enumerate 要带 `label=假设 …`。
    if its:
        if "\\begin{itemize}" in body:
            problems.append(f"{ASSUMPTIONS_FILE}: 用了 `itemize`（圆点列表）—— "
                            f"假设条目用 `enumerate` + `[label=\\textbf{{假设\\chinese{{enumi}}：}}]`（不要 •）")
        elif not re.search(r"\\begin\{enumerate\}\[[^\]]*假设", body):
            problems.append(f"{ASSUMPTIONS_FILE}: 条目编号不是「假设一：/假设二：…」—— "
                            f"enumerate 要写 `[label=\\textbf{{假设\\chinese{{enumi}}：}}]`"
                            f"（用户 2026-09-27：中文数字、**标签与冒号加粗**，照「优点一：」的写法）")
        elif "\\textbf{假设" not in body:
            problems.append(f"{ASSUMPTIONS_FILE}: 「假设N：」这个标签没有加粗 —— "
                            f"要写 `\\textbf{{假设\\chinese{{enumi}}：}}`（用户 2026-09-27，照「优点一：」）")
    for n, body in enumerate(its, 1):
        # 只数中文字与拉丁词，别把 LaTeX 命令算进长度（与问题分析节同一把尺子）
        words = _prose_len(body)
        if words > ASSUMPTION_CHARS_FAIL:
            problems.append(f"{ASSUMPTIONS_FILE}: 假设{n} 正文约 {words} 字 —— 骨架要求"
                            f"「每条不长」（> {ASSUMPTION_CHARS_FAIL} 字判超）。"
                            f"参考件 `框架模板.pdf` 的假设每条 40–70 字："
                            f"只写「假设什么 + 一句依据/放宽影响」，"
                            f"敏感性数字、量级论证移到检验与讨论节。")
        elif words > ASSUMPTION_CHARS_WARN:
            problems.append(f"{ASSUMPTIONS_FILE}: 假设{n} 正文约 {words} 字，偏长"
                            f"（> {ASSUMPTION_CHARS_WARN} 字提醒；> {ASSUMPTION_CHARS_FAIL} 判超）")
    return problems


def main():
    ap = argparse.ArgumentParser(description="正文小节与模板骨架的对账")
    ap.add_argument("--root", type=Path, default=Path.cwd())
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    root = args.root.resolve()
    problems = skeleton_issues(root)
    if args.json:
        print(json.dumps({"root": str(root), "status": "PASS" if not problems else "FAIL",
                          "issues": problems}, ensure_ascii=False, indent=2))
    elif problems:
        print(f"骨架对账不过（{len(problems)} 条）：\n")
        for i, p in enumerate(problems, 1):
            print(f"  {i}. {p}")
        print("\n修法：模板 `sections/*.tex` 里的 `\\subsection{}`/`\\subsubsection{}` "
              "**是给定的骨架** ——\n"
              "  只能往它们里面填正文，不得增、删、改名、换顺序；那些「四问共用…」之类的"
              "自有结构，\n"
              "  并进骨架已有的小节里（例如每问的「模型准备/模型建立」），而不是另开一节。\n"
              "  符号表照模板 `4_symbols.tex` 的**三列**（符号 / 含义 / 单位）排，"
              "单位单独成列，不塞进含义的括号。\n"
              "  列结构与行数完全相同的两张表（如温度表与水分浓度表）并排放进同一个 "
              "`table`\n"
              "  （两个 `papertablehalf` 环境 + `\\hfill`），别各占一个浮动体。")
    else:
        print(f"骨架对账通过：{root}")
    # 配置类失败（找不到模板/正文目录）与内容类失败分开：前者该去修路径，后者该去改论文
    missing = any("找不到模板骨架" in p or "找不到正文小节目录" in p for p in problems)
    return 0 if not problems else (2 if missing else 1)


if __name__ == "__main__":
    raise SystemExit(main())
