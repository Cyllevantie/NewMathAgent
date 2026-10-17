"""产物的合规判据。

核心一条：**产物根目录下只允许提交项 + `其余文件/`** —— 不靠自觉，用白名单钉住，
多出任何一个东西都报错并指出它该去哪。

本模块的判据**不在任何阶段的 instructions 指纹里**（设计取舍，见 `lib/web/server.py`
`_LIB_INSTRUCTION_USERS` 段的注释）：交付件在链尾 `final=True` 的打包里总会用当前代码
重跑 `check()`，所以**交付层**不受「旧回执」影响；受影响的只有 ⑮ 门禁早查的结论 ——
改这里的判据后，显式「从 ⑮ 重跑」一次即可。
"""
import re
from pathlib import Path

from .core import DEMO_HTML, OTHER_DIR, OTHER_SUBDIRS, load_manifest, walk_files

# 会去**加载资源**的标签。`<a href>` 不算 —— 那是跳转，不加载，离线也不影响渲染。
_RESOURCE_REF = re.compile(
    r"""<(script|link|img|iframe|source|embed|object)\b[^>]*?\b(?:src|href)\s*=\s*["']([^"']*)["']""",
    re.I)
_ABS_URL = re.compile(r"^[a-z][a-z0-9+.-]*://", re.I)


def demo_html_issues(root):
    """`demo/demo.html` 必须**自包含**：双击即用、离线可用。

    为什么是机器判据而不是散文：这条规矩一旦破，产物里的 `demo.html` 打开就是**白屏**，
    而打包本身、清单对账、页数检查**全都不会报错** —— 一路绿到交付，打开才发现。
    「多文件开发 + 打包时合并」的写法还会额外漏掉 `vendor/` 里的库，所以从源头就要求单文件。

    判据：文件里不得出现指向**本地文件**的资源引用；也不得引 `http(s)://` 资源
    （离线环境加载不到，且比赛现场可能没网）。`data:` 内联与 `#` 锚点放行。
    """
    root = Path(root).resolve()
    path = root / "demo/demo.html"
    if not path.is_file():
        return []                                   # 没有 demo 的题不判（有的题不做 demo）
    try:
        html = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return [f"{DEMO_HTML} 读不出来：{exc}"]
    bad = []
    for tag, url in _RESOURCE_REF.findall(html):
        url = url.strip()
        if not url or url.startswith("#") or url.startswith("data:"):
            continue
        if _ABS_URL.match(url):
            bad.append(f"<{tag.lower()}> 引了联网资源 {url!r} —— 离线打不开，把库内联进去")
        else:
            bad.append(f"<{tag.lower()}> 引了本地文件 {url!r} —— 提交件里没有它，页面会白屏")
    if bad:
        return [f"{DEMO_HTML} 不是自包含的单文件（必须双击即用、离线可用）：" + "；".join(sorted(set(bad)))]
    return []


# 三维豁免的固定前缀：SKILL 教产物写这一行、这里认这一行 —— 同一个 token 只此一处定义，
# 防"文档说 A、代码 grep B"的漂移（回归哨兵按这个常量对 SKILL 文本）。
DEMO_3D_EXEMPT_TOKEN = "三维豁免："
DEMO_3D_ENGINE = "skills/16Web-demo/assets/scene3d.js"
# 引擎是**框架**（住在仓库里、和判据同一个包），按 __file__ 定位而不是按 root ——
# 否则对着一份没有 skills/ 的导出工作区跑 check 会假报"找不到引擎源文件"。
_DEMO_ENGINE_FILE = Path(__file__).resolve().parents[2] / DEMO_3D_ENGINE


def _fold_eol(text):
    """逐字比对的宽恕范围：只折叠行尾（CRLF → LF、去行尾空白），不折叠内容。

    为什么只宽恕行尾：agent 抄引擎时行尾/末尾空格会因编辑器不同而变化（那是格式），
    但改一个字符（哪怕是缩进）就不是"内联原文"了（那是内容）—— 后者必须报出来。
    """
    return "\n".join(line.rstrip()
                     for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"))


def demo_3d_issues(root):
    """`demo/demo.html` 必须**逐字内联**三维内核（或显式声明豁免）。

    为什么是机器判据：⑯ 的主视图形态是"数据驱动的动态三维模型"，这条纪律如果只写在
    SKILL 里，agent 装作没看见、继续出二维曲线图时**没有任何东西会报错** —— 一路绿到
    交付，打开才发现主视图还是折线。仓库惯例是每条纪律带一个机械抓手，抓手就是：
    引擎（`skills/16Web-demo/assets/scene3d.js`）的**整段原文**必须出现在 demo.html 里；
    否则必须有一行 `三维豁免：<理由>`。判据不猜"这题能不能三维"，只要求
    "内联了"或"说清了为什么没有"——纯判定卡/纯表格题合法豁免。

    逐字比对还有第二个作用：引擎原文从此是事实上的接口 —— 改引擎要在**源文件**里改，
    源文件一动，盘上所有 demo.html 都"对不上原文"直到 ⑯ 重跑（与指令指纹把 ⑯ 标成
    stale-instr 是同一时刻，口径一致）。
    """
    root = Path(root).resolve()
    path = root / "demo/demo.html"
    if not path.is_file():
        return []                                  # 没有 demo 的题不判（有的题不做 demo）
    engine_path = _DEMO_ENGINE_FILE
    if not engine_path.is_file():
        return [f"找不到三维引擎源文件 {DEMO_3D_ENGINE} —— 这条判据拿它做逐字比对，缺了它判不了"]
    try:
        html = _fold_eol(path.read_text(encoding="utf-8", errors="replace"))
        engine = _fold_eol(engine_path.read_text(encoding="utf-8", errors="replace"))
    except OSError as exc:
        return [f"{DEMO_HTML} 或引擎源文件读不出来：{exc}"]
    if engine and engine in html:
        return []
    try:
        report = (root / "reports/DEMO_REPORT.md").read_text(encoding="utf-8-sig", errors="replace")
    except OSError:
        report = ""
    for line in report.splitlines():
        if DEMO_3D_EXEMPT_TOKEN in line:
            if line.split(DEMO_3D_EXEMPT_TOKEN, 1)[1].strip():
                return []                          # 豁免要带理由，光一个前缀不算
    return [f"{DEMO_HTML} 里没有内联三维内核（{DEMO_3D_ENGINE} 的整段原文，逐字、只折叠行尾），"
            f"reports/DEMO_REPORT.md 里也没有「{DEMO_3D_EXEMPT_TOKEN}理由」这样一行。"
            f"两条出路：① 重跑 ⑯，按 skills/16Web-demo/SKILL.md「动态三维模型」一节把引擎"
            f"原文整段内联进 script 块；② 这题确实没有可三维化的维度（纯判定卡/纯表格）⇒ "
            f"在报告里写一行「{DEMO_3D_EXEMPT_TOKEN}……」，把理由写出来。"]


def _suggest(name):
    """一个不该出现在根目录的东西，该挪去哪。"""
    low = name.lower()
    if low.endswith((".tex", ".aux", ".log", ".out", ".toc", ".bbl", ".blg", ".synctex.gz")):
        return f"{OTHER_DIR}/正文/（LaTeX 工程）"
    if low.endswith((".py", ".sh", ".bat")) or low.endswith((".json", ".npz", ".csv")):
        return f"{OTHER_DIR}/辅助脚本/（不作提交项的脚本与中间数据）"
    if low.endswith(".md"):
        return f"{OTHER_DIR}/内部报告/（审查报告）"
    if low.endswith((".pdf", ".xlsx", ".html", ".png", ".svg")):
        return "要么进提交清单（reports/SUBMISSION_MANIFEST.json），要么进 " + OTHER_DIR
    return OTHER_DIR


def _missing_attachments(root, items):
    """`request/attachments/**` 与 `data/**` 下有没有"没进提交件、也没声明排除"的文件。

    `items` 里每一项的**真实源**（`resolve_source` 给的，可能带子目录）算"已交代"；
    清单里的 `exclude` 声明的也算。两者都没有的，逐条报出来。
    """
    from .core import load_excludes, resolve_source
    try:
        excludes = load_excludes(root)
    except ValueError as exc:
        return [str(exc)]
    covered = set()
    for i in items:
        try:
            src = (i.get("source") or "").strip() or resolve_source(root, i["path"])
        except ValueError:
            continue                                   # 重名歧义等由打包那步报，这里不重复
        covered.add(Path(src).as_posix().lower())
    for e in excludes:
        covered.add(e["path"].lower())
    missing = []
    for base in ("request/attachments", "data"):
        d = Path(root).resolve() / base
        if not d.is_dir():
            continue
        for _p, rel in walk_files(d):
            if f"{base}/{rel}".lower() not in covered:
                missing.append(f"{base}/{rel}")
    if not missing:
        return []
    show = "、".join(missing[:6]) + ("…" if len(missing) > 6 else "")
    return [f"这些**题目附件/数据**没进提交件（共 {len(missing)} 件）：{show} —— "
            f"要么写进清单 items（嵌套的用 source 指真实路径），要么在清单的 exclude 里"
            f"声明为什么不用提交（如「临时中间文件」）"]


def check(root, output_dir, items=None):
    """返回问题清单（空 = 合规）。`items` 省略时从清单文件重读。"""
    root = Path(root).resolve()
    out = Path(output_dir).resolve()
    issues = []
    if not out.is_dir():
        return [f"产物目录不存在：{out}"]
    try:
        items = items if items is not None else load_manifest(root)
    except ValueError as exc:
        return [str(exc)]

    declared = [i["path"] for i in items]

    # ① 根目录白名单
    actual = sorted(p.name for p in out.iterdir())
    allowed = set(declared) | {OTHER_DIR}
    for name in actual:
        if name not in allowed:
            issues.append(f"产物根目录出现不该提交的东西：{name!r} —— 应挪去 {_suggest(name)}")

    # ② 清单声明的每一项都要在产物里，且非空
    for name in declared:
        p = out / name
        if not p.exists():
            issues.append(f"清单声明了 {name!r}，但产物里没有（打包时漏了，或清单写错）")
        elif p.is_file() and p.stat().st_size == 0:
            issues.append(f"{name!r} 是空文件（0 字节）—— 提交件不能是空壳")

    # ③ 其余文件的分层
    other = out / OTHER_DIR
    if other.is_dir():
        for name in sorted(p.name for p in other.iterdir()):
            if name not in OTHER_SUBDIRS and (other / name).is_dir():
                issues.append(f"{OTHER_DIR}/ 下多了一个分类目录 {name!r} —— "
                              f"约定只有 {list(OTHER_SUBDIRS)}")
    elif OTHER_DIR in actual:
        issues.append(f"{OTHER_DIR} 是文件，应该是目录")

    # ④ demo 必须自包含（白屏是"一路绿到交付、打开才发现"的那类故障）
    issues.extend(demo_html_issues(root))

    # ④·2 demo 主视图必须是数据驱动的三维（引擎逐字内联）或显式豁免 —— 与④同一个故障族：
    #     主视图悄悄退回二维曲线，打包/清单/页数检查全都不会报错。
    issues.extend(demo_3d_issues(root))

    # ④·5 题目附件**一个都不能漏**
    #   为什么值得单列：`provisional_items` 只看顶层，所以 `request/attachments/附件3/`
    #   这类嵌套目录里的 4 个模板 xlsx 会**一件都进不了提交包**，而且**没有任何东西会告诉你** ——
    #   一路绿灯到交付，打开才发现附件不全。这类"静默漏"比"明确报错"贵得多。
    #   范围刻意收窄到 `request/attachments/**` + `data/**`：那才是"题目附件/数据"的
    #   无歧义定义（提交清单本来就在收这两处）。`request/problem.md`/`problem.pdf` 是链的
    #   **输入**、不是附件，不进这条判据 —— 否则每次都会对着它误报，验收就成了狼来了。
    issues.extend(_missing_attachments(root, items))

    # ⑤ 同一份代码不能既是提交件又躺在辅助脚本里
    aux = other / "辅助脚本"
    if aux.is_dir():
        both = sorted({n for n in declared
                       if n.lower().endswith(".py") and (aux / n).exists()})
        if both:
            issues.append(f"这些 .py 既平铺在产物根目录、又留在 {OTHER_DIR}/辅助脚本/：{both} —— "
                          "提交件只能有一份，否则分不清哪个是提交的")

    # ⑤·2 核心提交件必须在清单里（2026-10-17 审计：白名单只挡"多了什么"，
    #   "少声明了正文 PDF/附录/运行说明/AI 说明"可以一路绿到交付）。
    issues.extend(required_items_issues(root, items))

    # ⑥ 提交清单 ↔ 正文末页（P32）清单表 的名字集合（2026-10-17 解耦新增，
    #   说明见 `checklist_consistency_issues`）—— 解耦后两边不再同源产出，
    #   "两边必须一致"必须有人机械核。
    issues.extend(checklist_consistency_issues(root))
    return issues


# 提交清单里这几个文件由**排在 format 之后**的阶段产出，verify 时还不该存在。
LATE_ITEMS = {"demo.html"}


def precheck(root, items=None):
    """verify 那一关就能跑的**早期**校验：清单在不在、声明的东西到齐没有。

    为什么要早查：**严格对账**发生在整链收口时（中途的阶段性打包只收不判），
    那时才发现「清单没写」或「清单里少了一个 .py」，已经白跑了好几个小时
    （demo 之后还要再跑一遍 format → verify → rubric）。
    verify 是 demo 之前最后一关，在那里拦住最划算。

    `demo.html` 是例外 —— 它由排在 verify 之后的 `16Web-demo` 产出，此刻本就不该存在。
    另核一件（2026-10-17 新增）：清单 ↔ 正文末页清单表的名字集合一致 ——
    见 `checklist_consistency_issues`。
    """
    from .core import resolve_source
    root = Path(root).resolve()
    try:
        items = items if items is not None else load_manifest(root)
    except ValueError as exc:
        return [str(exc)]
    issues = []
    for item in items:
        name = item["path"]
        if name in LATE_ITEMS:
            continue
        # `resolve_source` 会因"基名在工作区里 ≥2 处"（递归唯一命中）抛 ValueError ——
        # 而**本函数没有兜它**，调用链却是致命的：
        # `precheck` ← `_mechanical_floor` ← `_gate_decision`/复用近路，以及
        # `_restore_stale_instr`（**模块级调用**，它自己的 docstring 写着"启动期自检，
        # 绝不许把服务带崩"）⇒ 一条有歧义的清单会让**服务根本起不来**，
        # 而 agent `from server import STAGES` 一 import 就当场死（症状就是那个出了名的
        # 「rc=1 无诊断」）。这里按 `_missing_attachments` 的成例兜成一条可读 issue。
        try:
            src = item["source"] or resolve_source(root, name)
        except ValueError as exc:
            issues.append(f"提交清单里的 {name!r} 无法定位：{exc}")
            continue
        if not (root / src).exists():
            issues.append(f"提交清单声明了 {name!r}，但工作区里没有对应的 {src!r}")
    issues.extend(required_items_issues(root, items))
    issues.extend(checklist_consistency_issues(root))
    return issues


# ---- 提交清单 ↔ 正文末页清单表（P32）的一致性 —— 解耦后的机器判据 ----
# 2026-10-17 之前，清单与末页表由同一个阶段（⑭）用同一份脚本产出、天然一致；
#   解耦后 ⑨ 首产、⑬/⑭ 又都可能合法地只碰其中一边 ⇒ 「两边必须逐项一致」这条
#   从"同源保证"变成必须**机械核**（规则写了、没人核，就等于没有 —— 14 SKILL 原话）。
A1_TABLE_REL = "paper/sections/A1_materials.tex"


_CELL_SPLIT_RE = re.compile(r"(?<!\\)&")          # 未转义的 & 才是分列
_INLINE_COMMENT_RE = re.compile(r"(?<!\\)%")     # 未转义的 % 才是行内注释
_CELL_WRAPPERS_RE = (
    re.compile(r"\\multicolumn\{[^{}]*\}\{[^{}]*\}\{([^{}]*)\}"),
    re.compile(r"\\multirow\{[^{}]*\}\{[^{}]*\}\{([^{}]*)\}"),
    re.compile(r"\\(?:makecell|textbf|texttt|emph|underline)\{([^{}]*)\}"),
)
_A1_HEADER_NAMES = {"文件", "文件名", "说明"}


def _a1_table_names(text):
    """末页清单表表体里每行第一列登记的名字（`、` 拆开；转义与常见命令还原）。

    只看 `\\midrule`/`\\hline` 之后、`\\bottomrule`/`\\end{tabular}` 之前的行；
    模板占位符（`<由 … 生成：文件名>` 这类尖括号片段）不算名字 —— 占位符没填
    恰恰是要抓的形态（"只剩占位符"是最严重的形态问题）。

    2026-10-17 审计加固（原实现的假 FAIL 面）：先按**未转义的** `&`/`%` 切分
    （否则文件名里的 `\\&` 在主列切分时就被截断）；剥 `\\multicolumn`/`\\makecell`
    等包装命令；容忍行尾带空格的 `\\\\`；跳过表头词（`\\hline` 起表的稿子）。
    """
    names, in_body = [], False
    for ln in text.splitlines():
        s = ln.strip()
        if s.startswith("\\midrule") or s.startswith("\\hline"):
            in_body = True
            continue
        if s.startswith("\\bottomrule") or s.startswith("\\end{tabular"):
            break
        if not in_body or not s or s.startswith("%"):
            continue
        if not s or "&" not in s:
            continue
        first = _CELL_SPLIT_RE.split(s, 1)[0]
        # **先切列、再切行内注释**：`q1.py % 注 & 说明` 里注释符出现在列分隔之前，
        #   先切注释会把 `&` 一起吃掉 ⇒ 整行被跳过（2026-10-17 自测抓到的解析 bug）。
        first = _INLINE_COMMENT_RE.split(first, 1)[0].strip()
        first = re.sub(r"\\+\s*$", "", first.strip()).strip()   # 行尾 `\\`（后面可能带空格）
        for rx in _CELL_WRAPPERS_RE:            # 允许两层包装（如带样式的 multicolumn）
            prev = None
            while prev != first:
                prev, first = first, rx.sub(r"\1", first)
        for part in first.split("、"):
            for a, b in (("\\_", "_"), ("\\%", "%"), ("\\&", "&"), ("\\#", "#")):
                part = part.replace(a, b)
            part = part.strip().strip("{}").strip()
            if part and not part.startswith("<") and part not in _A1_HEADER_NAMES:
                names.append(part)
    return names


# 清单可以不声明任何东西也过白名单/对账 —— 2026-10-17 审计实测：清单只写 run_all.py 时，
#   打包里没有正文 PDF / 附录A / 运行说明 / AI 工具说明，而 `check()` 仍 PASS（静默漏交付）。


def required_items_issues(root, items=None):
    """清单必须声明**核心提交件**（正文 PDF / 附录A / 运行说明 / AI 工具说明）。

    为什么要有它：白名单只挡「多了什么」，②只核「声明了的在不在」——一份**漏掉**正文 PDF
    的清单可以一路绿到交付。`demo.html` **不在**必交集合里：纯机理/纯证明题合法跳过 demo
    （`16Web-demo` SKILL），但只要盘上已经有 `demo/demo.html` 而清单没声明它，就报 ——
    那才是「⑯ 产出了但清单漏了」的形态。
    """
    root = Path(root).resolve()
    from .core import (AI_TOOLS_PDF, APPENDIX_PDF, BODY_PDF, DEMO_HTML, MANUAL,
                       body_pdf_name)
    try:
        items = items if items is not None else load_manifest(root)
    except ValueError as exc:
        return [str(exc)]
    declared = {str(i["path"]) for i in items}
    need = {APPENDIX_PDF, MANUAL, AI_TOOLS_PDF}
    missing = sorted(n for n in need if n not in declared)
    body_ok = body_pdf_name(root) in declared or BODY_PDF in declared
    issues = []
    if not body_ok:
        issues.append("提交清单没有声明正文 PDF（论文标题.pdf 或 正文.pdf）—— "
                      "这是必交件，漏声明 = 它不会被打包")
    if missing:
        issues.append("提交清单没有声明核心提交件：" + "、".join(missing)
                      + "（这些是必交件；漏声明 = 它们不会被打包/不会被对账）")
    if (root / "demo/demo.html").is_file() and DEMO_HTML not in declared:
        issues.append("盘上已有 demo/demo.html，但提交清单没有声明它 —— "
                      "⑯ 的产物会被漏出提交包")
    return issues


def checklist_consistency_issues(root):
    """清单 ↔ 正文末页清单表 的**名字集合**必须相等（减掉论文本身）。两边不都在就不判。

    口径（两处 SKILL 同一条）：清单 = 全部提交项；末页表 = 支撑材料、不含正文 PDF。
    合并行（`q1.py、q2.py、q3.py`）按顿号拆开 —— 所以比的是**名字集合**；
    `desc` 与「说明」的文字对应关系机器判不了，仍需 ⑭ 对账时人核。
    修复方向：表缺 → ⑨ 的生成脚本按清单重跑（或 ⑭ 依「交付包」节的修补权处理）；
    表多/清单少 → 先核哪边是真实提交面（打包以**清单**为准），两边改到一致。
    """
    root = Path(root).resolve()
    from .core import BODY_PDF, MANIFEST_REL, body_pdf_name
    table = root / A1_TABLE_REL
    if not (table.is_file() and (root / MANIFEST_REL).is_file()):
        return []                       # 两边不都在 ⇒ 不判（旧工作区 / 无交付层夹具）
    try:
        items = load_manifest(root)
    except ValueError:
        return []                       # 清单坏了/缺了：load_manifest 那一路的文案已经有人管
    declared = {str(i["path"]) for i in items}
    expect = declared - {body_pdf_name(root), BODY_PDF}
    try:
        got = set(_a1_table_names(table.read_text(encoding="utf-8", errors="replace")))
    except OSError as exc:
        return [f"正文末页清单表读不出来：{exc}"]
    issues = []
    if expect - got:
        issues.append("正文末页清单表少了这些提交项：" + "、".join(sorted(expect - got))
                      + "（表与清单两边必须逐项一致；表还是模板占位符？）")
    if got - expect:
        issues.append("正文末页清单表多了清单里没有的名字：" + "、".join(sorted(got - expect))
                      + "（改了表没改清单？两边必须逐项一致）")
    return issues


def report(root, output_dir, items=None):
    issues = check(root, output_dir, items)
    return {"schema_version": 1, "output_dir": str(Path(output_dir).resolve()),
            "status": "PASS" if not issues else "FAIL", "issues": issues}
