"""产物的合规判据。

核心一条：**产物根目录下只允许提交项 + `其余文件/`** —— 不靠自觉，用白名单钉住，
多出任何一个东西都报错并指出它该去哪。
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

    # ④·5 题目附件**一个都不能漏**
    #   为什么值得单列：`provisional_items` 只看顶层，所以 `request/attachments/附件3/`
    #   这类嵌套目录里的 4 个模板 xlsx 会**一件都进不了提交包**，而且**没有任何东西会告诉你** ——
    #   一路绿灯到交付，打开才发现附件不全。这类"静默漏"比"明确报错"贵得多。
    #   范围刻意收窄到 `request/attachments/**` + `data/**`：那才是"题目附件/数据"的
    #   无歧义定义（⑭ 的清单本来就在收这两处）。`request/problem.md`/`problem.pdf` 是链的
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
    return issues


# 提交清单里这几个文件由**排在 format 之后**的阶段产出，verify 时还不该存在。
LATE_ITEMS = {"demo.html"}


def precheck(root, items=None):
    """verify 那一关就能跑的**早期**校验：清单在不在、声明的东西到齐没有。

    为什么要早查：打包发生在整链收口时，那时才发现「清单没写」或「清单里少了一个 .py」，
    已经白跑了好几个小时（demo 之后还要再跑一遍 format → verify → rubric）。
    verify 是 demo 之前最后一关，在那里拦住最划算。

    `demo.html` 是例外 —— 它由排在 verify 之后的 `16Web-demo` 产出，此刻本就不该存在。
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
    return issues


def report(root, output_dir, items=None):
    issues = check(root, output_dir, items)
    return {"schema_version": 1, "output_dir": str(Path(output_dir).resolve()),
            "status": "PASS" if not issues else "FAIL", "issues": issues}
