"""Count physical PDF pages using an explicit, version-bound page classification.

No automatic deletion, equation rewriting, or guessed appendix boundaries.
"""
import json
import re
from pathlib import Path

from lib.visualization.evidence import path_in, sha, write_json

KINDS = {"cover", "abstract", "contents", "body", "references", "ai_statement", "appendix"}


def classify(total, mapping, policy):
    if policy.get("schema_version") != 1 or mapping.get("schema_version") != 1:
        raise ValueError("页数规则或页面映射版本无效")
    limit, target = policy["max_counted_pages"], policy["target_counted_pages"]
    if type(limit) is not int or type(target) is not int or not 0 < target <= limit:
        raise ValueError("页数目标须为正整数且不超过上限")
    # 下限（可选）：低于它只出 warning，不判 FAIL —— 国赛规则本身没有下限，
    # 这条是**本项目的写作口径**：宁多不少（多了能压缩，少了是真少）。
    floor = policy.get("min_counted_pages")
    if floor is not None and (type(floor) is not int or not 0 < floor <= target):
        raise ValueError("页数下限须为正整数且不超过目标页数")
    counted = policy["counted_kinds"]
    if not isinstance(counted, list) or not counted or not set(counted) <= KINDS or "body" not in counted:
        raise ValueError("计页类别无效或未包含正文")
    if not isinstance(policy.get("rule_basis"), str) or not policy["rule_basis"].strip():
        raise ValueError("缺少页数口径依据")
    pages = {}
    for span in mapping["spans"]:
        first, last, kind = span["first"], span["last"], span["kind"]
        if type(first) is not int or type(last) is not int or not 1 <= first <= last <= total or kind not in KINDS:
            raise ValueError("页面范围或类别无效（使用从1开始的PDF物理页码）")
        if not isinstance(span.get("title"), str) or not span["title"].strip():
            raise ValueError("每个页面区段须注明内容标题")
        for n in range(first, last + 1):
            if n in pages:
                raise ValueError(f"第{n}页重复分类")
            pages[n] = kind
    if set(pages) != set(range(1, total + 1)):
        raise ValueError("页面映射必须覆盖全部PDF物理页，不能遗漏超限页")
    if "body" not in pages.values():
        raise ValueError("页面映射没有正文")
    counts = {kind: sum(v == kind for v in pages.values()) for kind in sorted(KINDS)}
    forbidden = policy.get("forbidden_kinds", [])
    if not isinstance(forbidden, list) or not set(forbidden) <= KINDS:
        raise ValueError("禁止页面类别配置无效")
    for kind in forbidden:
        if counts[kind]:
            raise ValueError(f"当前提交规范不允许 {kind} 页面")
    if policy.get("first_kind") and pages[1] != policy["first_kind"]:
        raise ValueError("电子版第一页必须是指定的摘要专页")
    for kind, maximum in policy.get("max_kind_pages", {}).items():
        if kind not in KINDS or type(maximum) is not int or maximum < 1:
            raise ValueError("分类页数上限无效")
        if counts[kind] > maximum:
            raise ValueError(f"{kind} 超过 {maximum} 页")
    # 合计上限：有些类别是**一起**受约束的，单独看每类都合格、合起来超页也算超。
    # 本项目的实例：模板要求「八、AI 工具使用说明」与「九、参考文献」加起来不超过 1 页
    # （模板条文「九写在8下面，加起来不超过1页」）—— 用 max_kind_pages 表达不了这层约束。
    # 循环变量**不能**叫 limit/kinds —— 上面 `limit` 是正文页数上限，覆盖它会
    # 静默把 30 页额度改成 1 页（counted_pages=30 却被判超限 29 页）。
    for group in policy.get("max_group_pages", []):
        group_kinds, group_max = group.get("kinds"), group.get("limit")
        if (not isinstance(group_kinds, list) or not group_kinds
                or not set(group_kinds) <= KINDS
                or type(group_max) is not int or group_max < 1):
            raise ValueError("分类页数合计上限配置无效")
        label = group.get("title") or "+".join(sorted(group_kinds))
        grouped = sum(counts[kind] for kind in set(group_kinds))
        if grouped > group_max:
            raise ValueError(f"{label} 合计 {grouped} 页，超过 {group_max} 页")
    if policy.get("require_appendix"):
        appendix = [n for n in pages if pages[n] == "appendix"]
        if not appendix or any(pages[n] != "appendix" for n in range(min(appendix), total+1)):
            raise ValueError("须在正文之后保留附录，登记支撑文件清单与完整源程序")
    if policy.get("profile") == "cumcm_2026_electronic_user_supplied" and pages.get(2) != "body":
        raise ValueError("国赛电子版摘要之后应开始正文")
    used = sum(counts[k] for k in set(counted))
    return dict(total_pages=total, counts=counts, counted_pages=used, limit=limit,
                target=target, over_limit=max(0, used - limit), above_target=max(0, used - target),
                min_pages=floor, below_min=(max(0, floor - used) if floor else 0))


def boundary_page_issues(pdf, mapping, policy):
    """边界页归属检查 —— 堵「整页判给后一类」那个口子。

    为什么需要：`classify` **只信 `page-map.json` 声明的区间** —— 它校验"区间铺满全部物理页、
    互不重叠"，然后按 `last-first+1` 求和。它**没有办法知道某一页物理上装着两个类别的内容**。
    例：map 声明 `body 2–30`、`ai_statement 31`，而第 31 页**开头仍是正文**（表9 ＋「七」的
    用法段），八/九 从半页才开始 ⇒ 正文实际 30 页、计入额度 31 页，**超限**，
    而机械检查算出来 30 页、判 PASS；另一头第 32 页声明成 appendix，实际开头是
    参考文献 [10]–[17]。三条规则同时破、一条都没报出来。

    判据是**几何**的，不做语义判断：某类别的**起始页**上，**最上面那块文字**必须就是该类别的
    起始标记（容差 `boundary_top_tol`，默认 6pt）。标记上面还有别的文字 ⇒ 上一类没真正收在
    自己那一页 ⇒ 这一页横跨两个类别 ⇒ 映射无法诚实归属。
    找不到标记时**不报**：宁可漏，不可误伤 —— 误报会让一份合规的稿子连映射都绑不上。

    两个调用点：`inspect`（进 issues，判 FAIL）与 `bind_map`（**直接拒绑** ——
    不诚实的映射根本落不了盘）。
    """
    marks = policy.get("kind_start_markers") or {}
    tol = policy.get("boundary_top_tol", 6)
    if not isinstance(marks, dict) or not marks:
        return []
    if not isinstance(tol, (int, float)) or isinstance(tol, bool) or tol < 0:
        tol = 6
    out = []
    for span in (mapping.get("spans") or []):
        kind, first = span.get("kind"), span.get("first")
        if not isinstance(first, int) or isinstance(first, bool) or first <= 1 or first > len(pdf):
            continue                      # 第 1 页没有"前一类"，不判
        wanted = marks.get(kind)
        if not isinstance(wanted, list) or not wanted:
            continue
        page = pdf[first - 1]
        tops = []
        for needle in wanted:
            if isinstance(needle, str) and needle:
                tops += [r.y0 for r in page.search_for(needle)]
        if not tops:
            continue                      # 认不出标记 ⇒ 不判（见上面"宁可漏"）
        top = min(tops)
        # 判据：**这一页最上面那块文字**就得是该类别的起始标记 ——
        #   即"上一类必须真正收在自己那一页"。容差只留给"同一行里块框比字形框高一点"的度量差：
        #   同一行差 **0.0pt**，而"上一类漏两行下来"差 **55.5pt** ⇒ 6pt 分得干净。
        #   按"标记落在页面前 30%"判会放过 2–3 行的漏网 —— p31 的「八、」在 14.9% 处
        #   也判过，于是正文仍到 p31、计入 31 页；按"最上面那块文字"判才收得住。
        _blocks = [b for b in page.get_text("blocks") if b[6] == 0 and str(b[4]).strip()]
        if not _blocks:
            continue                      # 整页没有文字块（纯图页）⇒ 不判
        first_y = min(b[1] for b in _blocks)
        if top > first_y + tol:
            out.append(
                f"第{first}页被声明为「{span.get('title') or kind}」的起始页，但它**上面还有文字**"
                f"（页面最上面那块在 y={first_y:.0f}、该标记在 y={top:.0f}，差 {top - first_y:.0f}pt）"
                f"—— 说明**上一类没有收在自己那一页**，这一页横跨两个类别，页面映射无法诚实归属"
                f"（正文会被少数一页、合计上限会被多数一页）。改法二选一：把上一类**精简到真正"
                f"收在自己那一页**，或把这一页归回**前一个类别**、再按真实页数重算")
    return out


def formula_hints(root):
    """Heuristic review candidates only; never silently alter mathematical meaning."""
    hints = []
    for p in sorted((Path(root) / "paper").rglob("*")):
        if p.suffix != ".tex":
            continue
        for n, line in enumerate(p.read_text(encoding="utf-8-sig").splitlines(), 1):
            text = line.split("%", 1)[0]
            checks = []
            if "$$" in text:
                checks.append("用标准展示公式环境替代双美元写法")
            if re.search(r"\\(?:resizebox|scalebox)\b", text):
                checks.append("检查是否缩放公式；优先按关系符换行，不缩小数学文字")
            if "\\begin{eqnarray}" in text:
                checks.append("用 gather（每行一条）替代 eqnarray；**不要 equation 套 aligned** —— 实测公式后净空 −8.4pt 会压正文")
            if text.count("&") >= 3 and re.search(r"(?:=|\\le|\\ge|\\in)", text):
                checks.append("同一行存在多组对齐关系；独立约束各占一行，保留原索引和不等号")
            if text.count(r"\qquad") >= 2 and re.search(r"(?:=|\\le|\\ge)", text):
                checks.append("多条关系横向拼接；检查是否应拆为约束组")
            if "本文研究的问题涉及多维度数据分析与优化决策" in text:
                checks.append("问题重述仍有通用模板例文；按实际题面的任务与输出重写")
            if len(text) > 180 and ("=" in text or "\\frac" in text):
                checks.append("检查长公式是否混合定义、推导和数值代入；必要时分组")
            for message in checks:
                hints.append(dict(file=p.relative_to(root).as_posix(), line=n, message=message))
    return hints


# 指针：如图/见表/见附录图 A7 ……（含 `\ref{}` 与硬编码编号两种写法）
POINTER_RE = re.compile(
    r"(如|见|参见|详见|汇总于|列于|示于)\s*(附录)?\s*(附图|附表|图|表)\s*"
    r"(~?\s*\\ref\{[^}]*\}|[A-Za-z]?\d+(?:[.-]\d+)*)")
# 续接指针：**第二个及以后的指针不带动词**（`图 1 与图 2`、`表 2 与表 3`）——
# 漏了它会把「…如图 X 与图 Y 所示。」误判成"尾部不干净"⇒ 整类句子漏判。
CONT_POINTER_RE = re.compile(
    r"\s*[与和、，]\s*(?:附录)?\s*(?:附图|附表|图|表)\s*(~?\s*\\ref\{[^}]*\}|[A-Za-z]?\d+(?:[.-]\d+)*)")
# 非散文的正文块：这些环境里的「表 4」「图 2」不是引用，**必须先涂掉**（否则句子会跨表合并、整批漏判）
MASK_ENVS = ("table", "figure", "longtable", "tabular", "minipage", "equation", "align", "verbatim")
BOLD_RE = re.compile(r"\\(?:textbf|emph)\{([^{}]*)\}")
# C3 的「结论词」：残留里带上这些就是有信息的句子，不算纯指引。
# 只收**断言类**的词。**属性/方法类**的词（收敛、单调、等价、离散、边界…）不算 ——
# 它们出现在裸指针句里很正常（`网格收敛、步长收敛与场级收敛见图 4、图 5 与表 A3。`
# 是地道的"只在指路"），放进词表会把整类句子漏判。
CONCLUSION_WORDS = ("是", "为", "说明", "表明", "可见", "因此", "由于", "达到", "倍", "下降", "上升",
                    "大于", "小于", "相比", "分别", "意味着", "导致", "满足", "一致", "成立",
                    "取决于", "正比", "反比")


def _mask_nonprose(text):
    """把非散文块涂成空格 —— **保留换行与行长**（行号不失真），并**先查环境配对**。

    用跨行非贪婪正则掩 `table/figure/…` 时，遇到**不配对**的环境（写在注释里、
    或跨文件续写）会一路吃到文件尾 ⇒ 后面的句子**整批漏判**（对比"不掩码"时
    条数一样是巧合：吃的和漏的正好抵消）。所以：某个 env 在本文件里
    `\\begin` 与 `\\end` 数目不等 ⇒ **整个 env 都不掩** —— 宁可有噪声，不吃真句子。
    """
    lines = [l.split("%", 1)[0] for l in text.splitlines()]
    for env in MASK_ENVS:
        beg = re.compile(r"\\begin\{" + env + r"\*?\}")
        end = re.compile(r"\\end\{" + env + r"\*?\}")
        if sum(bool(beg.search(l)) for l in lines) != sum(bool(end.search(l)) for l in lines):
            continue                                   # 不配对 ⇒ 不掩（安全侧）
        i = 0
        while i < len(lines):
            if beg.search(lines[i]) and not end.search(lines[i]):
                j = i + 1
                while j < len(lines) and not end.search(lines[j]):
                    lines[j] = " " * len(lines[j])
                    j += 1
                i = j
            else:
                if beg.search(lines[i]):
                    lines[i] = " " * len(lines[i])
                i += 1
    return "\n".join(lines)


def _is_bare_pointer(sentence):
    """C1–C4：整句只在指路（把指针整段删掉后，句子不再表达结论/数值/机制）。"""
    hits = list(POINTER_RE.finditer(sentence))
    if not hits:                                                          # C1
        return False
    end_pos = hits[-1].end()
    while True:                                                           # 续接指针（与图 2 / 表 3）
        m = CONT_POINTER_RE.match(sentence, end_pos)
        if not m:
            break
        end_pos = m.end()
    tail = sentence[end_pos:].strip()
    if tail not in ("所示。", "。", "所示", ""):                            # C2 尾部干净
        return False
    residue = POINTER_RE.sub(" ", sentence)
    residue = re.sub(r"\\[a-zA-Z]+\*?(\[[^\]]*\])?(\{[^{}]*\})?", " ", residue)
    residue = re.sub(r"[{}\\&%_^~（）()\[\]、，；：.01-9\s]", "", residue)
    if len(residue) > 30 or any(w in residue for w in CONCLUSION_WORDS):   # C3 残留无信息
        return False
    head = sentence[:hits[0].start()]                                      # C4 前文短且无停顿
    return len(re.findall(r"[\u4e00-\u9fff]", head)) <= 25 and "，" not in head and "：" not in head


def style_hints(root):
    """文字层面的两条检查 —— 只给定位线索，不改任何东西。

    · **纯指引句**：一份真稿里有 18 处（`...路线如图 1 所示。` 这类，删掉后全文信息量为零）。
      判据只按「。」切句、**不按逗号/分号切** —— 否则 `…；结果如图 X 所示。` 会被切成裸指针，
      每一处尾部引用都成假阳性。**尾部引用不算缺陷。**
    · **结果型加粗**：`\\textbf{}` / `\\emph{}` 里**含数字**的那种。本模板把 `\\emph` 重定义成
      `\\textbf`（避 ctex 的 KaiTi），**不认它就漏检**。真稿里 74 处加粗**全是结构标签**，
      结果型 = **0** ⇒ 读者要逐字找结论数字。
    """
    hints = []
    for p in sorted((Path(root) / "paper").rglob("*.tex")):
        raw = p.read_text(encoding="utf-8-sig")
        rel = p.relative_to(Path(root)).as_posix()
        # 逐句扫，但**记的是源文件行号**（与 `formula_hints` 的 `line` 同口径）——
        # 记"第几句"会误导（行号才能直接跳过去看）。
        buf, start = "", 1
        for n, line in enumerate(_mask_nonprose(raw).splitlines(), 1):
            if not buf:
                start = n
            buf += line
            while "。" in buf:
                sent, buf = buf.split("。", 1)
                if _is_bare_pointer(sent + "。"):
                    hints.append({"file": rel, "line": start, "message":
                                  "整句只在指路（如图/见表 X 所示）：把图要支撑的结论/机制/量级写进正文，"
                                  "指针只作句尾出处（见 docs/WRITING_QUALITY.md 的「图表引用」一节）"})
    bold = [m.group(1) for p in sorted((Path(root) / "paper").rglob("*.tex"))
            for m in BOLD_RE.finditer(p.read_text(encoding="utf-8-sig"))]
    numbered = [b for b in bold if re.search(r"\d", b)]
    if bold and not numbered:
        hints.append({"file": "paper/", "line": 0, "message":
                      f"加粗 {len(bold)} 处**全是结构标签**，没有任何一处包住结果数字 ⇒ "
                      "关键结论数字要加粗，让读者一眼看到（见 docs/WRITING_QUALITY.md）"})
    # **按小问**核加粗：关键的比较、重要词汇与结果数字要让评委一眼看到。
    # 只要求"全文至少有一处含数字的加粗"不够 —— 某个小问一处都没有照样过。
    # 判据：每个 `5_problemN.tex` 至少 1 处；摘要（`\\abstractcn` 那段）至少 N 处
    # （N = 小问数）—— 摘要里每个小问的结论都要能被一眼看到。
    sections_dir = Path(root) / "paper" / "sections"
    problem_files = sorted(sections_dir.glob("5_problem*.tex")) if sections_dir.is_dir() else []
    for p in problem_files:
        got = [m.group(1) for m in BOLD_RE.finditer(p.read_text(encoding="utf-8-sig"))]
        if not any(re.search(r"\d", b) for b in got):
            hints.append({"file": str(p.relative_to(Path(root))).replace("\\", "/"), "line": 0,
                          "message": "本小问**一处结果数字都没加粗** ⇒ 结论数字（带单位/百分号的那个值）"
                                     "要 `\\textbf{}` 让评委一眼看到（用户 2026-09-27 口径）"})
    main_tex = Path(root) / "paper" / "main.tex"
    if problem_files and main_tex.is_file():
        text = main_tex.read_text(encoding="utf-8-sig")
        m = re.search(r"\\abstractcn\{(.{100,})", text, re.S)
        if m:
            abs_bold = [x.group(1) for x in BOLD_RE.finditer(m.group(1))]
            n_num = sum(1 for b in abs_bold if re.search(r"\d", b))
            if n_num < len(problem_files):
                hints.append({"file": "paper/main.tex", "line": 0,
                              "message": f"摘要里含数字的加粗只有 {n_num} 处，少于小问数 "
                                         f"{len(problem_files)} ⇒ 每个小问的结论数字在摘要里各要加粗一次"
                                         f"（用户 2026-09-27 口径）"})
    return hints


def formula_review_issues(root, hints, pdf_hash):
    """Bind explicit editorial decisions to current source and rendered PDF."""
    if not hints:
        return []
    root = Path(root)
    try:
        review = json.loads((root / "paper/formula-review.json").read_text(encoding="utf-8-sig"))
        if review.get("pdf_sha256") != pdf_hash:
            return ["公式复核记录未绑定当前PDF，需编译后逐项复核"]
        expected = {(h["file"], h["line"], h["message"]) for h in hints}
        seen = set()
        for item in review["items"]:
            key = (item["file"], item["line"], item["message"])
            if key in seen or key not in expected:
                raise ValueError("重复或过期的公式复核项")
            if item["source_sha256"] != sha(path_in(root, item["file"])):
                raise ValueError("公式源文件已变化")
            if item["decision"] not in {"retain", "reformatted"} or not str(item.get("reason", "")).strip():
                raise ValueError("缺少逐项保留或整理理由")
            if type(item.get("page")) is not int or item["page"] < 1:
                raise ValueError("缺少实际PDF物理页码")
            seen.add(key)
        if seen != expected:
            raise ValueError("公式复核未覆盖全部排版提示")
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        return ["公式排版待复核: " + str(exc)]
    return []


# ---------- 「写满那一页」：版心填充率 ----------
# （另见 inspect 内的长注释：只设**字符数下限**不够 —— 阈值容易落在坏样本之下，又只出 warning。）
FOOTER_BAND = 60.0        # 距纸底这么多 pt 以内只可能是页脚（页码），不算正文
MIN_FRAME_HEIGHT = 400.0  # 版心高不足此数 ⇒ 量不准（单页样张/整页是图），判据自动让位
DEFAULT_PITCH = 19.9      # 本模板行距；只在本稿量不出行距时兜底


def _text_frame(pdf):
    """本文**实际版心**的上下沿：所有页里排除页脚块之后的最小 top 与最大 bottom。

    不读 `paper/_base/preamble.tex` 的 geometry —— 判据要独自成立（换个模板族、拿到别人的稿子
    都不该失灵）。本稿量得 66.2~780.4pt（高 714.2），与 geometry 自报的 68.6~777.6 差不到
    3pt，够判"写满没写满"。量不出返回 None（此后由字符数下限兜底）。
    """
    top = bottom = None
    for page in pdf:
        for block in page.get_text("blocks"):
            if block[1] >= page.rect.height - FOOTER_BAND:
                continue
            top = block[1] if top is None else min(top, block[1])
            bottom = block[3] if bottom is None else max(bottom, block[3])
    if top is None or bottom - top < MIN_FRAME_HEIGHT:
        return None
    return top, bottom


def _line_pitch(pages):
    """行距估计：块 top 排序后取相邻差的**中位数**（行间公式会插队，所以不能取最小值）。"""
    tops = sorted({round(b[1], 1) for page in pages for b in page.get_text("blocks")
                   if b[1] < page.rect.height - FOOTER_BAND})
    gaps = [b - a for a, b in zip(tops, tops[1:]) if 8 <= b - a <= 40]
    return sorted(gaps)[len(gaps) // 2] if len(gaps) >= 4 else DEFAULT_PITCH


FORMULA_MIN_CLEARANCE = 3.0   # pt：编号 display 公式的「下净空」下限（正常档 11.68–18.96）


_EQNUM_RE = re.compile(r"^\(\d+\)$")


def formula_clearance_issues(pdf):
    """编号 display 公式的**下净空**：紧随其后的**正文行**顶 − 公式块底，< 3pt 即失败。

    为什么按几何判、不按环境名：本稿 19/20 条编号公式的下净空在 **11.68–18.96pt**，
    唯独式 (8) = **−8.36pt**（压住下一行正文）；成因是多行 display 写成了 `equation` 套
    `aligned` —— `aligned` 把整块包成**一个**盒子，公式后的净空不再落回常规档
    （同内容改 `gather` 就是 +13.78pt）。**「aligned 一律坏」不成立**：
    三行的 aligned 是 +11.09/+13.32pt（正的）⇒ 判据只能量净空。
    **必须靠右边的公式编号 `(N)` 认定公式块**：只按"非 SimSun 行"切块会把
    表格里的数字行、代码/文件名行误判成公式（5 条假阳性，还漏掉真的 (8)）。
    加上「块内要有 `(N)`」之后：本稿正文 20 条全认出、命中 1 条 = (8)、附录 0 条。
    """
    problems = []
    for pno, page in enumerate(pdf, 1):
        rows = []
        for block in page.get_text("rawdict")["blocks"]:
            if block.get("type") != 0:
                continue
            for line in block.get("lines", []):
                chars = [(s["font"], c["bbox"], c["c"])
                         for s in line["spans"] for c in s["chars"] if c["c"].strip()]
                if not chars:
                    continue
                rows.append({"y0": min(b[1] for _, b, _ in chars),
                             "y1": max(b[3] for _, b, _ in chars),
                             "nsun": sum(1 for f, _, _ in chars if f == "SimSun"),
                             "txt": "".join(c for _, _, c in chars)})
        rows.sort(key=lambda r: r["y0"])
        body = [r for r in rows if r["nsun"] >= 4]
        # 公式块 = 连续的非正文行（行距 < 9pt 合并）
        runs = []
        for r in [r for r in rows if r["nsun"] < 4]:
            if runs and r["y0"] - runs[-1][-1]["y1"] < 9.0:
                runs[-1].append(r)
            else:
                runs.append([r])
        for run in runs:
            numbers = [r for r in run if _EQNUM_RE.match(r["txt"].strip())]
            if not numbers:                      # 没有编号 ⇒ 不是编号公式（表格/代码/文件名）
                continue
            foot = max(r["y1"] for r in run)
            nline = numbers[0]
            after = [r for r in body if r["y0"] > nline["y0"]]
            if not after:
                continue
            nxt = min(after, key=lambda r: r["y0"])
            gap = nxt["y0"] - foot
            if gap < FORMULA_MIN_CLEARANCE:
                label = " ".join(r["txt"] for r in run)[:40]
                problems.append(
                    f"第 {pno} 页公式 {nline['txt'].strip()}「{label}」的下净空只有 {gap:.2f}pt"
                    f"（正常档 11.7–19.0pt）—— 压到下一行正文上了。多行公式多因写成 `equation` 套 "
                    f"`aligned`（净空被右侧盒子吃掉），或末行带 `\\frac`；改成 `gather` + 逐行 "
                    f"`\\notag\\\\[-12pt]`、末行改平（配方见 docs/WRITING_QUALITY.md）")
    return problems


def kind_fills(pdf, mapping, policy):
    """{kind: {"fill": 填充率, "rows": 还差几行, "chars": 非空白字符数}}。

    口径 = 该 kind 各页里**最低的那个非页脚块底边**，相对本文版心（`_text_frame`）占多少 ——
    即「尽量写满那一页」的机械形式。字数只是它的粗代理 —— 同样字数，标题占两行
    就少一行正文 —— 所以量得出填充率时**不再看字数下限**（`inspect` 里二者互斥）。
    """
    spec = policy.get("min_kind_fill")
    if not isinstance(spec, dict) or not spec:
        return {}
    frame = _text_frame(pdf)
    if frame is None:
        return {}
    top, bottom = frame
    height = bottom - top
    spans = {s.get("kind"): (s.get("first"), s.get("last"))
             for s in (mapping.get("spans") or [])}
    out = {}
    for kind, rule in spec.items():
        if kind not in spans or not isinstance(rule, dict):
            continue
        first, last = spans[kind]
        pages = [pdf[i - 1] for i in range(int(first), min(int(last), len(pdf)) + 1)]
        lows = [b[3] for page in pages for b in page.get_text("blocks")
                if b[1] < page.rect.height - FOOTER_BAND]
        if not lows:
            continue
        fill = (max(lows) - top) / height
        target = rule.get("target")
        rows = (round((target - fill) * height / _line_pitch(pages))
                if isinstance(target, (int, float)) else 0)
        out[kind] = {"fill": fill, "rows": max(0, rows),
                     "chars": sum(len(re.sub(r"\s", "", page.get_text())) for page in pages)}
    return out


def inspect(root):
    root = Path(root).resolve()
    result = {"schema_version": 1, "status": "UNVERIFIED", "issues": [], "warnings": [],
              "prose_issues": [], "kind_fills": {}}
    try:
        import pymupdf as fitz
        policy_path = path_in(root, "config/publication.json")
        mapping_path = path_in(root, "paper/page-map.json")
        pdf_path = path_in(root, "paper/main.pdf")
        policy = json.loads(policy_path.read_text(encoding="utf-8-sig"))
        mapping = json.loads(mapping_path.read_text(encoding="utf-8-sig"))
        pdf_hash = sha(pdf_path)
        if mapping.get("pdf_sha256") != pdf_hash:
            raise ValueError("页面映射未绑定当前PDF；编译后需重新核对物理页范围")
        with fitz.open(pdf_path) as pdf:
            count = classify(len(pdf), mapping, policy)
            result.update(count)
            # 边界页归属（见 `boundary_page_issues`）：`classify` 只信声明的区间，
            # 看不出"某一页物理上横跨两个类别"。这一条就是来堵那个口子的。
            result["issues"].extend(boundary_page_issues(pdf, mapping, policy))
            # 「写满那一页」的机械判据：
            # 只设字符数下限有两处致命伤：①阈值容易设在坏样本（919 字符 / 版心
            # 78.4%）**之下** ⇒ 判据对病灶毫无反应；②它只出 warning，而 warning 在本仓库里
            # 谁都不读 —— `_manual_checks` 与 `_mechanical_floor` 都是 `audit()` = `issues`。
            # 于是 ⑨ 的返修单里从来没有这一条，"重跑还是没解决摘要少"就是这么来的
            # （另一半原因在 ⑨ 的 SKILL/norms：那句「850–950 字内安全」读起来是个**上限**）。
            # 现在直接量**版心填充率**（即"尽量写满那一页"），分两档：
            #   < hard     ⇒ 进 `issues`，`lib/web/server.py::_mechanical_floor` 会判死；它据
            #                `prose_issues` 把回退目标由 ⑩排版改指 ⑨论文撰写（摘要文字只有 ⑨ 能改）
            #   [hard, target) ⇒ 只出 warning（差一点就别把小时级的链拖回去）
            _fills = kind_fills(pdf, mapping, policy)
            result["kind_fills"] = _fills          # 量出来的数就摆在这儿，省得人再去数
            # 公式净空的**几何判据**：
            # 量的是"编号公式块底 → 紧随其后正文行顶"的距离；本稿正常档 11.7–19.0pt、式(8) 是 −8.36pt。
            # 必须在 `with fitz.open(...)` **块内**算（pdf 出块就 close 了，否则报 "document closed"）。
            # **不**打 `prose_issues`：这不是措辞问题，改法是排版层的（换 `gather`/改末行）⇒
            # 按 `_mechanical_floor` 的路由判给 ⑭排版与版式，正是改 (14) 的那一方。
            # 判据零误报（本稿正文命中 1 条、附录 0 条；靠右边的 `(N)` 认公式块，不会把表格/代码行算进来）。
            _clearance = formula_clearance_issues(pdf)
            for _kind, _info in _fills.items():
                _rule = policy["min_kind_fill"][_kind]
                _target, _hard = _rule.get("target"), _rule.get("hard")
                if not isinstance(_target, (int, float)) or _info["fill"] >= _target:
                    continue
                _msg = (f"{_kind} 只填满版心的 {_info['fill']:.1%}（目标 ≥{_target:.0%}，"
                        f"现在 {_info['chars']} 个非空白字符"
                        + (f"，约需再补 {_info['rows']} 行" if _info["rows"] else "") +
                        "）—— 写满的办法是**加实质内容**（每问的方法要点、结论数字、"
                        "检验与灵敏度各写足），不是放大字号/加行距")
                if isinstance(_hard, (int, float)) and _info["fill"] < _hard:
                    _msg += f"；低于 {_hard:.0%} 属必须返修"
                    result["issues"].append(_msg)
                    result["prose_issues"].append(_msg)   # ← 文字层面的缺陷，归 ⑨
                else:
                    result["warnings"].append(_msg)
            # 字符数下限：只在**量不出填充率**的 kind 上兜底（量得出时上面那条更准，不重复报）
            _floors = policy.get("min_kind_chars")
            if isinstance(_floors, dict):
                _spans = {s.get("kind"): (s.get("first"), s.get("last"))
                          for s in (mapping.get("spans") or [])}
                for _kind, _floor in _floors.items():
                    if _kind in _fills or _kind not in _spans or type(_floor) is not int or _floor <= 0:
                        continue
                    _a, _b = _spans[_kind]
                    _chars = sum(len(re.sub(r"\s", "", pdf[i - 1].get_text()))
                                 for i in range(int(_a), min(int(_b), len(pdf)) + 1))
                    if _chars < _floor:
                        result["warnings"].append(
                            f"{_kind} 只有 {_chars} 个非空白字符，低于下限 {_floor}"
                            f"（配置 config/publication.json:min_kind_chars）—— 写满的办法是**加实质内容**"
                            "（每问的结论数字、方法要点、检验与灵敏度各写足），不是放大字号/加行距")
            for n, page in enumerate(pdf, 1):
                if policy.get("paper_size_mm"):
                    expected = policy["paper_size_mm"]
                    if (abs(page.rect.width * 25.4 / 72 - expected[0]) > .5 or
                            abs(page.rect.height * 25.4 / 72 - expected[1]) > .5):
                        result["issues"].append(f"第{n}页不是规范要求的A4纸面")
                for block in page.get_text("blocks"):
                    if block[0] < -1 or block[1] < -1 or block[2] > page.rect.width + 1 or block[3] > page.rect.height + 1:
                        result["issues"].append(f"第{n}页存在超出纸面的内容，需检查裁切")
                        break
        result["pdf_bytes"] = pdf_path.stat().st_size
        if "max_pdf_bytes" in policy:
            maximum = policy["max_pdf_bytes"]
            if type(maximum) is not int or maximum <= 0:
                raise ValueError("PDF大小上限配置无效")
            if result["pdf_bytes"] > maximum:
                result["issues"].append("PDF文件大小超过提交上限；应优化图片编码，保留文字和核心证据")
        if count["over_limit"]:
            result["issues"].append(f"计页内容{count['counted_pages']}页，上限{count['limit']}页；超出{count['over_limit']}页")
        elif count["above_target"]:
            result["warnings"].append("已超过初稿目标，仍在正式上限内；保留排版余量")
        if count.get("below_min"):
            result["warnings"].append(
                f"正文 {count['counted_pages']} 页，低于 {count['min_pages']} 页 —— "
                "篇幅不足**无法靠压缩弥补**（超了可以压，少了是真少），宁可写满不要留白。"
                "检查：每问的建模过程/求解细节/结果分析是否写足、图是否够、对照与检验是否只在附录")
        result["formula_hints"] = formula_hints(root)
        result["style_hints"] = style_hints(root)
        if result["style_hints"]:
            # 只提示、不进 issues：指引句与加粗都是**论文措辞**层面的活，回退目标写死成 ⑩ 会打转
            # （与上面 `min_kind_chars` 同一条理由）。修法：⑫评分标判词 → ⑬就地改，或 ⑨ 下一轮。
            result["warnings"].append(
                f"文字层提示 {len(result['style_hints'])} 条（纯指引句 / 结果型加粗）；"
                "见 style_hints，逐条按 docs/WRITING_QUALITY.md 处理")
        # 公式复核也是**文字/阅读**层面的活：逐条读公式、翻到物理页核对、再签这份记录。
        # 只有 ⑨ 做得了（⑩ 既不能读公式语义、也无权重签），故一并打 `prose_issues` 标记 ——
        # 否则它被判给 ⑩排版 ⇒ ⑩ 下一轮照样报同一条 ⇒ `_mechanical_floor` 死循环。
        _formula = formula_review_issues(root, result["formula_hints"], pdf_hash)
        result["issues"].extend(_formula)
        result["prose_issues"].extend(_formula)
        result["issues"].extend(_clearance)      # 几何净空（见上面 with 块内的说明）
        result["rule_basis"] = policy["rule_basis"]
        result["pdf_sha256"] = pdf_hash
        result["status"] = "FAIL" if result["issues"] else "PASS"
    except (ImportError, OSError, ValueError, KeyError, TypeError, AttributeError, RuntimeError) as exc:
        result["issues"].append(f"篇幅验收未完成: {exc}")
    return result


def audit(root, detail=False):
    """默认返回**问题清单**（谁拦门禁就看它）；`detail=True` 返回完整报告。

    需要 detail 的是 `lib/web/server.py::_mechanical_floor` —— 它得看 `prose_issues` 才知道这批问题
    该判给 ⑨（能改文字）还是 ⑩（只能改版式）。其余调用点（人工认证的 `_manual_checks`、
    各阶段自查）继续拿字符串清单，行为不变。
    """
    result = inspect(root)
    return result if detail else result["issues"]


def bind_map(root, spec):
    """An explicit author attestation after checking physical page boundaries."""
    root = Path(root).resolve()
    import pymupdf as fitz
    pdf = root / "paper/main.pdf"
    data = json.loads(Path(spec).read_text(encoding="utf-8-sig"))
    policy = json.loads((root / "config/publication.json").read_text(encoding="utf-8-sig"))
    with fitz.open(pdf) as document:
        classify(len(document), data, policy)
        # 边界页归属也在这里拦：**不诚实的映射根本绑不上盘**（见 `boundary_page_issues`）。
        # 只放进 inspect 的话，一份"整页判给后一类"的映射照样能绑上、照样显示 30 页 PASS。
        boundary = boundary_page_issues(document, data, policy)
        if boundary:
            raise ValueError("；".join(boundary))
    data["pdf_sha256"] = sha(pdf)
    write_json(root / "paper/page-map.json", data)
