# -*- coding: utf-8 -*-
"""把 ⑯ 的 demo **整段**安进 `附录A.pdf` 的**最前面**（标题 + 图 A1 + 一段介绍）。

附录第 1 页的版式形状是：

    demo 交互式网页与工程实现展示          ← 与 A.x 同级的小节标题（14.9pt 粗体）
    图A1：药材烘干交互式网页截图            ← 图
    页面把论文的建模链路（统一建模内核→…）   ← 几段介绍
    ……
    A.1  问题一、二的误差与守恒汇总          ← 原有的 A.x 小节**跟在后面**

**demo 段必须整段放在 A.1 之前**：若把图插在 `\\subsection*{A.1 …}` 标题**之后**、正文之前，
A.1 的标题会与它自己的正文被一张图劈开。demo 自成一段、整段放在 A.1 之前，
A.1 及其正文才能保持挨着。

**为什么要有这个脚本，而不是让 ⑯ 的 agent 手工插这一整段**：
附录的图号是**手打的纯文本**（`\\appfigure` 用 `\\caption*`，`\\caption*` 不产生编号，
「图 A1：」是图题里的字面量 —— 见 `_base/macros.tex` 的 `\\appfigure`）。所以「在最前面
插入一张新图」意味着**把后面所有图号顺延 1**，而这个文件里图号出现 **13 处**：
7 个 `\\appfigure` 图题 + 6 处行文按号指路（「图 A2 把表 2 与表 3…」）。手工顺延每轮都要
重来一遍、错一个号就与正文对不上。

**幂等**：整段用注释标记包起来（`BLOCK_BEGIN`/`BLOCK_END`），重跑时**整段**摘掉再插一遍 ——
不是只摘那张图（只摘图会把标题与介绍留成孤儿，再来一轮就攒出第二份）。重跑的结果与首次
**逐字节相同**。也能从只有"裸图行"的旧形状迁移过来（见 `_strip_demo_block`）。

用法：

    python lib/web/appendix_demo_figure.py --png demo/shot_1_default.png --intro _tmp/demo_intro.tex
    python lib/web/appendix_demo_figure.py --png <png> --intro <txt> --root <其它工作区> --json
"""
import argparse
import json
import re
import shutil
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

APPENDIX_TEX = "paper_appendix/sections/A_appendix.tex"
APPENDIX_FIGDIR = "paper_appendix/figures"
# 判断「上一轮插过没有」只看这一个标识，别去猜图题文字。
DEMO_FIGURE_ID = "demo_shot"
DEMO_CAPTION = "交互式网页首屏"
# 这一段的小节标题（与 A.x 同级 —— 14.9pt 粗体）。
# 用**不带括号**的写法：小节标题里不加全角括号。
#   带全角括号的写法是错的，别照抄。
DEMO_HEADING = "demo 交互式网页与工程实现展示"
# 整段的界标：重跑时按它**整段**替换，理由见模块 docstring。
BLOCK_BEGIN = "% >>> demo 展示段（⑯ 自动生成，重跑会整段替换，别手改这一段）"
BLOCK_END = "% <<< demo 展示段"
# 图号：`图 A3` / `图 A12`（容忍中间空格）。只在**附录**里用，表号是另一套（表 A1…）。
FIG_LABEL_RE = re.compile(r"图\s*A(\d+)")
# `\appfigure[宽]{文件}{图题}` —— 宽可选，文件与图题不含嵌套花括号。
APPFIGURE_RE = re.compile(r"\\appfigure(?:\[[^\]]*\])?\{([^{}]*)\}\{([^{}]*)\}")
# 小节标题（附录里一律是带星号的 `\subsection*`，见 A_appendix.tex 顶部那段约定）
SUBSECTION_RE = re.compile(r"\\subsection\*?\{")


def _png_to_pdf(png: Path, out_pdf: Path) -> None:
    """截图转成 PDF —— 图件目录的既有惯例是「每张图一个 `.pdf`」（`figures/*.pdf`）。"""
    import fitz  # PyMuPDF：仓库已依赖（`lib/publication/checks.py` 在用）
    with fitz.open(png) as doc:
        pdf_bytes = doc.convert_to_pdf()
    with fitz.open("pdf", pdf_bytes) as out:
        out.save(str(out_pdf))


def _latex_safe(text: str) -> str:
    """把介绍里的**裸百分号**转义。

    中文散文里「完成度 100%」这种极常见，而 LaTeX 会把 `%` 之后整行**静默注释掉** ——
    编译照样成功、字却少了，是最难发现的一类失效。只处理 `%`：`&`/`_`/`#` 撞上会直接
    编译报错（响的），不会静默丢内容。
    """
    return re.sub(r"(?<!\\)%", r"\\%", text)


def _strip_demo_block(text):
    """摘掉上一轮的 demo 展示段。返回 `(新文本, 摘掉了几段)`。

    两条路：
      · 有界标 → 从 `BLOCK_BEGIN` 到 `BLOCK_END` **整段**剪掉（含两端），再吃掉紧随的空行；
      · 没有 → 兼容只有**裸图行**的旧形状：`\\appfigure{…demo_shot…}` 行（这种形状没有标题、
        也没有介绍，所以只需摘那一行 + 它的空行）。
    """
    n = 0
    i = text.find(BLOCK_BEGIN)
    if i >= 0:
        j = text.find(BLOCK_END, i)
        if j >= 0:                       # 界标成对 ⇒ 整段剪掉
            j += len(BLOCK_END)
            while j < len(text) and text[j] == "\n":
                j += 1
            text = text[:i] + text[j:]
            n += 1
    # 兜底（含"只有前半段界标"的残缺情形）：剩下的裸 demo 图行也摘掉
    src, kept, k = text.split("\n"), [], 0
    while k < len(src):
        if DEMO_FIGURE_ID in src[k] and "\\appfigure" in src[k] and BLOCK_BEGIN not in src[k]:
            n += 1
            k += 1
            while k < len(src) and not src[k].strip():   # 连同配对的那个空行
                k += 1
            continue
        kept.append(src[k])
        k += 1
    return "\n".join(kept), n


def _build_block(intro: str, caption: str):
    """整段的行列表：标题 / 图 A1 / 介绍。编号写死 `图 A1` —— 它就是最前面那一张。"""
    body = [l for l in _latex_safe(intro).strip().split("\n")]
    return [BLOCK_BEGIN,
            f"\\subsection*{{{DEMO_HEADING}}}",
            "",
            f"\\appfigure[\\textwidth]{{{DEMO_FIGURE_ID}}}{{图 A1：{caption}}}",
            "",
            *body,
            BLOCK_END]


def ensure_demo_figure(root, png, intro, caption=DEMO_CAPTION):
    """把 demo 整段安到附录最前面。`intro` 是那几段介绍（纯文本）。"""
    root = Path(root)
    tex = root / APPENDIX_TEX
    if not tex.is_file():
        raise FileNotFoundError(f"找不到附录正文：{APPENDIX_TEX}")
    png = Path(png)
    if not png.is_file():
        raise FileNotFoundError(f"找不到截图：{png}")
    if not (intro or "").strip():
        # 不许静默退化：只放一张光图、没有介绍，就丢了这一段必须有的「标题 + 图 + 介绍」
        raise ValueError("介绍是空的 —— 这一段要「标题 + 图 + 介绍」，不能只插图")

    text = tex.read_text(encoding="utf-8")

    # ---- 1) 摘掉上一轮那一段（幂等）----
    text, n_dropped = _strip_demo_block(text)

    # ---- 2) 剩下的图按文中先后重新编号：第 i 张（0 基）→ A(i+2)（demo 占 A1）----
    #    旧号从**每个 `\appfigure` 的图题**里取（那才是图真正出现的先后）。
    old_nums = []
    for m in APPFIGURE_RE.finditer(text):
        label = FIG_LABEL_RE.search(m.group(2))
        if label:
            old_nums.append(int(label.group(1)))
    mapping = {old: i + 2 for i, old in enumerate(old_nums)}
    # 先把映射整个算完再替换 —— 边替边算会把刚写进去的新号再映射一次。
    if mapping:
        text = FIG_LABEL_RE.sub(
            lambda m: f"图 A{mapping.get(int(m.group(1)), int(m.group(1)))}", text)

    # ---- 3) 图件落盘（.pdf 供 LaTeX，.png 留档，与根 figures/ 的惯例一致）----
    figdir = root / APPENDIX_FIGDIR
    figdir.mkdir(parents=True, exist_ok=True)
    _png_to_pdf(png, figdir / f"{DEMO_FIGURE_ID}.pdf")
    shutil.copy2(png, figdir / f"{DEMO_FIGURE_ID}.png")

    # ---- 4) 整段插到**所有 A.x 小节之前**（= 附录第一页）----
    lines = text.split("\n")
    at = next((i for i, l in enumerate(lines) if SUBSECTION_RE.match(l)), 0)
    block = _build_block(intro, caption)
    while at > 0 and not lines[at - 1].strip():      # 别攒空行：紧跟在本段前的空行先吃掉
        at -= 1
    lines[at:at] = block + [""]
    tex.write_bytes("\n".join(lines).encode("utf-8"))
    return {"tex": str(tex), "dropped": n_dropped, "figures": mapping,
            "figdir": str(figdir), "heading": DEMO_HEADING,
            "intro_lines": len(block) - 6}


def main():
    ap = argparse.ArgumentParser(description="把 demo 整段（标题+图A1+介绍）安进附录最前面")
    ap.add_argument("--png", required=True, help="⑯ 截出来的那张首屏图")
    ap.add_argument("--intro", required=True, help="那几段介绍的纯文本文件（UTF-8）")
    ap.add_argument("--root", type=Path, default=Path.cwd())
    ap.add_argument("--caption", default=DEMO_CAPTION)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    try:
        intro = Path(args.intro).read_text(encoding="utf-8")
    except OSError as e:
        print(f"读不到介绍文件：{e}")
        return 1
    try:
        r = ensure_demo_figure(args.root.resolve(), args.png, intro, args.caption)
    except (OSError, ValueError) as e:
        print(f"插入失败：{e}")
        return 1
    if args.json:
        print(json.dumps(r, ensure_ascii=False, indent=2))
    else:
        print(f"已把 demo 整段安到附录最前面：「{r['heading']}」+ 图 A1 + {r['intro_lines']} 行介绍")
        print(f"  原有 {len(r['figures'])} 张图号已顺延：{r['figures']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
