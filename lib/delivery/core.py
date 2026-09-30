"""产物布局、打包与归档。

**提交件根目录下只放要提交的东西**（外加 `其余文件/`）。这条由 `checks.py` 机械化校验 ——
不靠自觉，靠白名单。

    产物/                                    ← 产物根（`resolve_output_dir`，路径可由面板设置）
    ├── 提交作品/
    │   ├── <题目标识_日期_时间>/             ← 换题时由「最新作品」整目录改名而来
    │   └── 最新作品/                         ← **提交件根**（下表就是它的内容）
    │       ├── <论文标题>.pdf / 附录A.pdf / demo.html / 运行说明.md / AI工具使用详情.pdf
    │       ├── result*.xlsx / 题目附件 / *.py   ← 平铺，不带 code/ 前缀
    │       └── 其余文件/
    │           ├── 正文/      正文的 LaTeX 工程（.tex + _base + sections + figures + 编译中间件）
    │           ├── 附录/      附录的 LaTeX 工程
    │           ├── 辅助脚本/  code/ 里不作提交项的文件 + code/outputs/ 中间数据
    │           └── 内部报告/  reports/ 全部（审查报告不提交）
    ├── 各阶段产物/
    │   ├── <题目标识_日期_时间>/             ← 换题时由「最新产物」改名而来（与上面**同名**）
    │   └── 最新产物/<中文阶段名>/…           ← 每阶段跑完镜像一份，供翻账
    ├── cache/                                ← 回退快照 cache/<题目标识_日期_时间>/<中文阶段名>/
    └── 其他产物/                             ← 「🧹 清理全部残留」的落点

`package` / `check` / `archive_into_cache` **刻意保持布局无关** —— 它们只认调用方给的
`output_dir`，所以上表里 `提交作品/最新作品` 这一层由调用方（`lib/web/server.py`）用
`resolve_submission_dir()` 给出，本模块一行都不用知道「提交作品」这四个字怎么拼。
"""
import errno
import json
import re
import shutil
import uuid
from datetime import datetime
from pathlib import Path

try:                                     # 包内导入（正常用法）；直接跑本文件时退回同级
    from .safe_walk import walk_files
except ImportError:                      # pragma: no cover
    from safe_walk import walk_files

OTHER_DIR = "其余文件"
OTHER_SUBDIRS = ("正文", "附录", "辅助脚本", "内部报告")

# 提交项（产物根）的**类别**规则。清单（SUBMISSION_MANIFEST.json）声明具体有哪些文件，
# 这里只负责「这个名字该从工作区的哪里取」。
BODY_PDF = "正文.pdf"
APPENDIX_PDF = "附录A.pdf"
DEMO_HTML = "demo.html"
MANUAL = "运行说明.md"
# 论文研究与写作过程中 AI 工具使用情况的说明（独立一件，平铺在提交件根）。
#   由 14Layout-and-format 在交付层产出（`skills/14Layout-and-format/SKILL.md`「交付包」节，依参考样板补）
#   —— 正文 §八 那句「详细使用情况见支撑材料」与末页清单表都指向它，缺了就是悬空引用。
AI_TOOLS_PDF = "AI工具使用详情.pdf"


def body_pdf_name(root):
    """提交件里**正文 PDF 的文件名** —— 用**论文标题**，不是写死的 `正文.pdf`。

    依据：赛题条文对文件名**没有规定**，而参考稿用的是论文标题
    （`基于变物性耦合传热传质与动域模型的.pdf`）⇒ 对齐它。
    来源 = `paper/main.tex` 的 `\\papertitle{...}`（排版阶段保证它在）。取不到就回落 `BODY_PDF`。

    回落**不会**让老清单打不了包：打包名以**清单声明的 `path`** 为准，这里只回答
    "那个名字该从工作区的哪里取"，而 `resolve_source()` 对**两种名字都认**。
    标题里的 Windows 保留字符与首尾空白一律清掉（赛题标题出现过冒号/问号）。
    """
    try:
        tex = (Path(root) / "paper" / "main.tex").read_text(encoding="utf-8", errors="replace")
    except OSError:
        return BODY_PDF
    m = re.search(r"\\papertitle\s*\{([^}]*)\}", tex)
    if not m:
        return BODY_PDF
    title = re.sub(r"[\s\u3000]+", " ", "".join(ch for ch in m.group(1) if ch not in _ILLEGAL)).strip()
    return (title + ".pdf") if title else BODY_PDF
# 工作区里的构建产物仍叫 `main.pdf`（`publication` / `15Verification` / `14Layout-and-format` 全都按这个名字
# 找它），**只在打包时改名**。少改一处就少一处漂移。
# 正文 PDF 的名字**不在这张表里**（= **论文标题**，见 `body_pdf_name()`）——
# 它是**动态的**，所以由 `resolve_source()` 前面那条分支专门处理（两种名字都认）。
FIXED_SOURCES = {APPENDIX_PDF: "paper_appendix/main.pdf",
                 DEMO_HTML: "demo/demo.html",      # 单文件，产出来就叫这个名字
                 AI_TOOLS_PDF: "paper/ai_tools/AI工具使用详情.pdf",
                 MANUAL: MANUAL}

MANIFEST_REL = "reports/SUBMISSION_MANIFEST.json"
# Windows 上文件名保留字符。产物路径与题目标识都可能来自用户输入，必须挡。
_ILLEGAL = '\\/:*?"<>|'


def delivery_name(problem_id, when=None):
    """cache 里的归档目录名：`<题目标识>_<YYYY.M.D_H.M.S>`；题目标识空则只有时间。

    归档名里的分隔符用下划线：**冒号在 Windows 上是保留字符**
    （Win32 会把它当数据流分隔符），`2026A:2026.9.18:19.13.00` 这种名字建不出目录。
    """
    when = when or datetime.now()
    stamp = (f"{when.year}.{when.month}.{when.day}_"
             f"{when.hour:02d}.{when.minute:02d}.{when.second:02d}")
    pid = (problem_id or "").strip()
    if not pid:
        return stamp
    bad = sorted({c for c in pid if c in _ILLEGAL})
    if bad:
        raise ValueError(f"题目标识含 Windows 保留字符 {''.join(bad)!r}：{pid!r}（换成字母数字或下划线）")
    return f"{pid}_{stamp}"


def resolve_output_dir(root, output_dir):
    """产物路径：空 / 等于项目根 → `<项目根>/产物/`；否则用给定路径。"""
    root = Path(root).resolve()
    raw = (output_dir or "").strip()
    if not raw:
        return root / "产物"
    p = Path(raw)
    if not p.is_absolute():
        p = root / p
    p = p.resolve()
    if p == root:
        return root / "产物"
    return p


# ---------------- 两个「最新」指针 + 换题归档 ----------------
#
# 产物根下多两层，各含一个**恒指向当前这道题**的指针目录：
#     提交作品/最新作品/      ← 提交件（`package`/`check` 的对象）
#     各阶段产物/最新产物/     ← 每阶段跑完镜像一份，按中文阶段名分目录
# 换一道题（输入源变更）时，这两个指针**整目录改名**成 `<题目标识_日期_时间>`，
# 再建两个空的 —— 于是「当前」与「历史」永远分得清，且全程不需要人工清理。
#
# 为什么 `package/check` 一行都不改：`checks.py:80-85` 的判据全在**传入目录那一层**
# 的 `iterdir()`。把 `提交作品/最新作品` 当 `output_dir` 传进去，那一层仍是
# 「平铺提交件 + 其余文件/」，白名单与清单对账原样成立。所以这两层只活在调用方。
SUBMISSION_PARENT = "提交作品"
SUBMISSION_POINTER = "最新作品"
STAGES_PARENT = "各阶段产物"
STAGES_POINTER = "最新产物"


def resolve_submission_dir(root, output_dir=""):
    """提交件根：`<产物根>/提交作品/最新作品/`。`package` / `check` 的落点。"""
    return resolve_output_dir(root, output_dir) / SUBMISSION_PARENT / SUBMISSION_POINTER


def resolve_stage_dir(root, output_dir=""):
    """阶段快照根：`<产物根>/各阶段产物/最新产物/`。"""
    return resolve_output_dir(root, output_dir) / STAGES_PARENT / STAGES_POINTER


DELIVERY_CFG_REL = "config/delivery.local.json"


def configured_output_dir(root):
    """面板里存着的产物根（`config/delivery.local.json` 的 `output_dir`）；读不到返回 ""。

    CLI **必须**用它当默认，不能硬编码 `<root>/产物/`：门禁交给 agent 的
    `recheck` 就是 `python -m lib.delivery check`，面板一改产物路径，那条命令就会落在
    **另一个目录**上，报出一串「提交件根还不存在」的**假 FAIL**。
    读不到配置（或字段为空）才退到 `resolve_output_dir` 的默认。
    """
    try:
        cfg = json.loads((Path(root).resolve() / DELIVERY_CFG_REL).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return ""
    if not isinstance(cfg, dict):
        return ""
    return str(cfg.get("output_dir") or "").strip()


def unique_boundary_name(parents, name):
    """在**全部** parent 里都不撞名的归档名；撞了退到 `<name>-2`、`-3`…

    必须一次查两个 parent：`提交作品` 与 `各阶段产物` 里那两份归档**是同名的**
    （靠同名把「这一题的提交件」与「这一题的阶段产物」对起来）。
    各查各的会让两边算出不同的名字，那条对应关系就断了。
    """
    # 必须**大小写不敏感**地比：Windows 上路径大小写不敏感，
    # `2026A_x` 与 `2026a_x` 判为不撞名、盘上却是同一个目录 —— 那时
    # `rotate_pointer` 会因为「归档目标已存在」抛错，把换题/归档**整个中止**。
    taken = set()
    for parent in parents:
        parent = Path(parent)
        if parent.is_dir():
            taken |= {c.name.casefold() for c in parent.iterdir()}
    if name.casefold() not in taken:
        return name
    for n in range(2, 1000):
        candidate = f"{name}-{n}"
        if candidate.casefold() not in taken:
            return candidate
    raise ValueError(f"归档名用尽了：{name}")


def is_cross_device_error(exc):
    """这个 OSError 是不是「换了盘」？**只有它是**才该退到复制。

    跨盘：POSIX `errno.EXDEV`(18) / Windows `WinError 17`（ERROR_NOT_SAME_DEVICE）。
    被占用**不是**跨盘 —— Windows 上目录里有文件被开着时整目录 rename 会以
    `WinError 5`（拒绝访问）失败，那是 `errno 13`。把两者混为一谈会**永久删数据**。
    """
    return (getattr(exc, "errno", None) == errno.EXDEV
            or getattr(exc, "winerror", None) == 17)


def rotate_pointer(pointer, dest_root, name):
    """把 `pointer` 整目录改名成 `dest_root/<name>`；**不存在或为空 → None**（不动）。

    同盘 rename / 跨盘复制 / 拒绝覆盖 —— 与 `archive_into_cache` 同一套语义，
    只多两条「空就不动」与「占用绝不当跨盘」（见下）。

    `Windows` 上**目录里有文件被别的进程开着**时，整目录 `rename` 会以
    **WinError 5（拒绝访问）**失败 —— 那**不是**跨盘。所以占用类 OSError
    **什么都不动、原样上抛**，由调用方回滚/转黄灯；绝不能一律退到
    `copytree + rmtree(pointer)`：那会**永久删数据** —— `copytree` 读被占文件是允许的、
    能成功；而 `rmtree` 边走边删、删到被占文件时抛错；外层 `except` 再把**完整的那份
    副本**清掉 ⇒ **源里除被占文件外的文件全被删掉、归档一份也没建成**。
    """
    pointer = Path(pointer)
    if not pointer.is_dir() or not any(pointer.iterdir()):
        return None
    dest = Path(dest_root) / name
    if dest.exists():
        raise ValueError(f"归档目标已存在：{dest}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        pointer.rename(dest)
        return dest
    except OSError as exc:
        if not is_cross_device_error(exc):
            raise                      # 被占用之类 —— 一件都不许动
        # 真跨盘：先拷到**临时名** → 原子改名过去 → **最后**才删源。
        # 中途任何一步失败都不动源、也不在 dest 留半份（不用 shutil.move：
        # 它中途失败会留下半份）。
        tmp = dest.with_name(f".{dest.name}.copying-{uuid.uuid4().hex[:8]}")
        try:
            shutil.copytree(pointer, tmp)
            tmp.rename(dest)
        except Exception:
            shutil.rmtree(tmp, ignore_errors=True)
            raise
        try:
            shutil.rmtree(pointer)
        except OSError:
            # 源删不干净（跨盘上仍有被占文件）—— **归档已经完整了**，
            # 宁可留一份残源，也绝不动它。
            pass
        return dest


def load_manifest(root):
    """读 `14Layout-and-format` 写的提交清单。**缺失即报错** —— 不猜、不静默兜底。"""
    path = Path(root).resolve() / MANIFEST_REL
    try:
        spec = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, ValueError) as exc:
        raise ValueError(
            f"提交清单缺失或不可读：{MANIFEST_REL}（{exc}）。"
            "打包前必须由 14Layout-and-format 写出它 —— 它同时是论文末页清单表的来源，"
            "两边必须一致。") from exc
    if not isinstance(spec, dict) or spec.get("schema_version") != 1:
        raise ValueError(f"{MANIFEST_REL} 结构错误：schema_version 必须为 1")
    items = spec.get("items")
    if not isinstance(items, list) or not items:
        raise ValueError(f"{MANIFEST_REL} 结构错误：items 必须是非空列表")
    out = []
    for item in items:
        if not isinstance(item, dict) or not isinstance(item.get("path"), str) or not item["path"].strip():
            raise ValueError(f"{MANIFEST_REL} 结构错误：每个 item 必须有非空的 path")
        name = item["path"].strip().replace("\\", "/")
        if "/" in name:
            raise ValueError(f"{MANIFEST_REL}: path 必须是产物根目录下的**文件名**，收到 {name!r}")
        out.append({"path": name, "desc": str(item.get("desc") or "").strip(),
                    "source": (item.get("source") or "").strip().replace("\\", "/")})
    seen = [i["path"] for i in out]
    dup = sorted({n for n in seen if seen.count(n) > 1})
    if dup:
        raise ValueError(f"{MANIFEST_REL}: 重复的 path {dup}")
    return out


def load_excludes(root):
    """清单里可选的 `exclude`：**显式声明"这份题目附件刻意不提交"**，附理由。

    为什么要它：`checks.check` 有一条判据 —— `request/attachments/**` 与
    `data/**` 下的每个文件都得有个交代（进清单，或在这儿声明排除）。没有这个字段，
    "某个大文件刻意不提交"就只能靠不写清单 —— 而那与"忘了写"在机器眼里一模一样，
    正是"静默漏附件"的来源。字段缺失/为空都返回 `[]`；**写了但结构不对则报错**（与清单本体的
    「缺失即报错」同一纪律：安静地忽略一条声明，比拒绝它更危险）。
    """
    path = Path(root).resolve() / MANIFEST_REL
    try:
        spec = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, ValueError):
        return []
    raw = spec.get("exclude") if isinstance(spec, dict) else None
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ValueError(f"{MANIFEST_REL}: exclude 必须是列表")
    out = []
    for e in raw:
        if not isinstance(e, dict) or not str(e.get("path") or "").strip():
            raise ValueError(f"{MANIFEST_REL}: exclude 的每一项都必须有 path")
        out.append({"path": str(e["path"]).strip().replace("\\", "/"),
                    "why": str(e.get("why") or "").strip()})
    return out


def resolve_source(root, rel):
    """提交项的名字 → 它在工作区里的相对位置。清单给了 `source` 就用它。"""
    root = Path(root).resolve()
    name = rel.split("/")[-1]
    # 正文 PDF 的两种名字都认：现行规则是**论文标题**（对齐参考稿），
    # 老清单可能还写着 `正文.pdf` —— 两种都映到同一个源，免得历史清单打不了包。
    if rel == body_pdf_name(root) or rel == BODY_PDF:
        return "paper/main.pdf"
    if rel in FIXED_SOURCES:
        return FIXED_SOURCES[rel]
    if re.fullmatch(r"result\d+\.xlsx", name, re.I):
        for cand in (f"results/{name}", f"code/outputs/{name}"):
            if (root / cand).is_file():
                return cand
        return f"results/{name}"                       # 交给调用方报「缺失」
    if name.lower().endswith(".py"):
        return f"code/{name}"
    for base in ("request/attachments", "data", "request"):
        if (root / base / name).exists():
            return f"{base}/{name}"
    # 平铺找不到 ⇒ **递归找基名**：附件常有子目录（`附件3/result1.xlsx`），
    # 而清单里只写得出平铺名（`load_manifest` 明禁 `path` 含 `/`）。
    # 只在**唯一命中**时采用：0 个或 ≥2 个都让它走下面的 `return rel`（调用方报"缺失"）
    # 或直接抛错 —— 静默挑一个会让提交包里装错文件，而且**没人看得出来**。
    # 三个搜索根**互相包含**（`request/` 套着 `request/attachments/`）⇒ 必须按真实路径去重，
    # 否则同一个文件会被数好几遍，"≥2 命中"就成了假警报。
    hits_by_real = {}
    for base in ("request/attachments", "data", "request"):
        d = root / base
        if d.is_dir():
            for p, _ in walk_files(d):
                if p.name.lower() == name.lower():
                    hits_by_real[p.resolve()] = p
    hits = list(hits_by_real.values())
    if len(hits) == 1:
        return hits[0].relative_to(root).as_posix()
    if len(hits) > 1:
        where = "、".join(sorted(str(p.relative_to(root)).replace("\\", "/") for p in hits[:5]))
        raise ValueError(
            f"「{name}」在工作区里有 {len(hits)} 处同名（{where}…）—— 清单里请把 `source` 写成"
            f"完整相对路径，别只给文件名（驱动不敢替你猜是哪一份）")
    return rel


def provisional_items(root):
    """⑭ 还没写出 `reports/SUBMISSION_MANIFEST.json` 之前，**先按能认出来的提交件**收一批。

    为什么要有它：清单由 **⑭** 写，而 ⑭ 排在 ⑨ 之后 ⇒ 链一旦在 ⑨~⑬ 之间停下，
    `最新作品/` 里**什么都没有**，尽管正文 PDF、附录、`result*.xlsx` 早就做好了 ——
    翻那个文件夹时看到的是"白干了一天"。所以 ⑨ 收尾时先把已经做好的移入，
    剩下的做好再移。

    与 `load_manifest` 的分工**不重叠**：那份清单是**完整口径**（含每一件的说明文字、
    同时是论文末页清单表的来源），⑭ 跑完由它**整份重建**；本函数只是 ⑭ 之前的
    **临时占位**，收完会记一行日志说明"这是临时的"。
    名字的权威仍在本模块：正文用 `body_pdf_name()`、其余用 `FIXED_SOURCES` 的键 ⇒
    与 ⑭ 那份清单**不可能起名不一致**（不会出现"先叫 result1.xlsx、后改叫结果1.xlsx"）。
    只收**盘上真的有**的项，缺的不编 —— 编一个不存在的名字会让 `check()` 判不合规。
    """
    root = Path(root).resolve()
    out, seen = [], set()

    def add(name, desc, src):
        # 去重按 **casefold**：提交件根最终落在 Windows 上，
        # 而那儿路径**大小写不敏感** —— `A.xlsx` 与 `a.xlsx` 是同一个文件，大小写敏感的去重
        # 会让两份都进清单，打包时后写的静默盖掉先写的（而且 `load_manifest` 的重复检查
        # 也是大小写敏感的，同样拦不住）。
        key = name.casefold()
        if key in seen or not (root / src).is_file():
            return
        seen.add(key)
        out.append({"path": name, "desc": desc, "source": src})

    add(body_pdf_name(root), "论文正文", "paper/main.pdf")
    for name, desc in ((APPENDIX_PDF, "附录 A"), (AI_TOOLS_PDF, "AI 工具使用详情"),
                       (DEMO_HTML, "交互演示"), (MANUAL, "运行说明")):
        add(name, desc, FIXED_SOURCES[name])
    results = root / "results"
    if results.is_dir():
        for p in sorted(results.glob("result*.xlsx")):
            add(p.name, "计算结果", f"results/{p.name}")
    code = root / "code"
    if code.is_dir():
        for p in sorted(code.glob("*.py")):
            add(p.name, "程序源码", f"code/{p.name}")
    # 附件/数据必须**递归**收：只看 `iterdir()` 的顶层会漏掉真实附件包里的子目录 ——
    # `request/attachments/附件3/` 这类目录里若有 4 个模板 xlsx，就**一件都进不了提交包**，
    # 而且不报错（静默漏；`check` 也看不见，因为它压根不认这些文件）。
    # 提交件是**平铺**的（`load_manifest` 明禁 `path` 含 `/`），所以这里把子目录拍平：
    # 基名不撞就用基名；撞了用「父目录_基名」；再撞才加序号（后缀保住，别把 .xlsx 吃掉）。
    for base in ("request/attachments", "data"):
        d = root / base
        if not d.is_dir():
            continue
        for p, rel in walk_files(d):
            name = p.name if "/" not in rel else f"{Path(rel).parent.name}_{p.name}"
            if name.casefold() in seen:
                stem, suffix = Path(name).stem, Path(name).suffix
                n = 2
                while f"{stem}-{n}{suffix}".casefold() in seen:
                    n += 1
                name = f"{stem}-{n}{suffix}"
            add(name, "题目附件 / 数据", f"{base}/{rel}")
    return out


def build_plan(root, items):
    """展开成 [(源相对路径, 产物内相对路径)]；两份清单：提交项 / 其余文件。"""
    root = Path(root).resolve()
    submission, other = [], []

    for item in items:
        src = item["source"] or resolve_source(root, item["path"])
        submission.append((src, item["path"]))

    for sub, src in (("正文", "paper"), ("附录", "paper_appendix")):
        if (root / src).is_dir():
            other.append((src, f"{OTHER_DIR}/{sub}"))
    if (root / "reports").is_dir():
        other.append(("reports", f"{OTHER_DIR}/内部报告"))
    # code/：提交项已在根目录平铺，剩下的（子目录、非 .py、outputs/）整份留档。
    if (root / "code").is_dir():
        other.append(("code", f"{OTHER_DIR}/辅助脚本"))
    return submission, other


def _copy(src, dst):
    dst.parent.mkdir(parents=True, exist_ok=True)
    if src.is_dir():
        shutil.copytree(src, dst, dirs_exist_ok=True)
    else:
        shutil.copy2(src, dst)


def _merge_dir(src, dst):
    """把 `src` 里 `dst` **还没有**的文件补进 `dst`；同名以 `dst` 已有的为准（这轮的新版优先）。

    只用于"归档目录只增不减"这一条口径：`其余文件/` 这一层的东西不是提交件，
    它存在的意义是**留档**，所以这一轮没重新生成的部分不该被抹掉。
    """
    for p in sorted(src.rglob("*")):
        rel = p.relative_to(src)
        if "__pycache__" in rel.parts:
            continue
        target = dst / rel
        if p.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        elif not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, target)


def _recover_swap_leftovers(out):
    """把上次**换包崩在中间**留下的残局收回来（`package()` 一进来就调）。

    · `.最新作品.building-*` = 没换上去的 staging ⇒ 直接清掉（半成品，没人要）；
    · `.最新作品.old-*` = 换包前的旧包 ⇒ **指针不在时把最新那份改名回指针**，
      其余留着（换题时 `_rotate_pointers` 会一并收编）。
    收完记一行日志 —— 这一发如果发生过，日志里该看得见包是被收回来的。
    """
    parent, name = out.parent, out.name
    if not parent.is_dir():
        return
    for p in list(parent.glob(f".{name}.building-*")):
        shutil.rmtree(p, ignore_errors=True)
    olds = sorted((p for p in parent.glob(f".{name}.old-*") if p.is_dir()),
                  key=lambda p: p.stat().st_mtime)
    if olds and not out.exists():
        olds[-1].rename(out)
        print(f"[delivery] 上次换包崩在中途：已把 {olds[-1].name} 收回 {name}/")
        olds = olds[:-1]
    if olds:
        print(f"[delivery] 另有一份更早的包留在 {olds[0].parent}（换题时会一并归档）")


def package(root, output_dir, items, *, clean_other_submitted=True, allow_missing=False):
    """把产物**原子地**建起来：先在旁边建，成功了再换上去。

    失败时保持上一份产物不动 —— 不冒充本轮成功（先构建、后归档、再切换）。

    `clean_other_submitted=True`：`其余文件/辅助脚本/` 里会先剔掉已经平铺到根目录的
    提交用 `.py`，避免同一份代码在产物里出现两次、让人分不清哪个是提交件。

    `allow_missing=True`（**阶段性打包**用）：清单里**还没产出**的项
    跳过不报错，返回跳过的名字列表。

    为什么必须有它：⑨ 结束要先把已做好的移入，剩下的做好再移。而 ⑭ 写的
    清单**声明了 `demo.html`**，可那要等 ⑯ 才产出 ⇒ 中途打包必然撞上"清单里有、
    工作区还没有" ⇒ 直接抛错、**一个文件都收不进去**（⑭ 跑完后
    `提交作品/最新作品/` 仍然是空的）。
    "缺项即报错"对**链尾那次**是对的（那是正式交付，缺一件都不行），对**中途**是错的。
    """
    root = Path(root).resolve()
    out = Path(output_dir).resolve()
    # 先把上次换包崩在中间留下的残局收回来：
    # 换包是**两次独立 rename**（`out.rename(backup)` → `staging.rename(out)`），中间没有原子性。
    # 断电/强杀正好落在那之间 ⇒ `out` 整个不见了、完好的旧包躺在隐藏的 `.最新作品.old-*` 里，
    # 而**收编它的代码只在 `_rotate_pointers` 里**（只在换题 / 手动归档时跑）⇒
    # 同一题续跑**永远不会自愈**，面板就一直显示"没有提交件"（而包其实好好的）。
    _recover_swap_leftovers(out)
    submission, other = build_plan(root, items)

    missing = [src for src, _ in submission if not (root / src).exists()]
    if missing and not allow_missing:
        raise ValueError("清单里这些提交项在工作区找不到：" + "、".join(sorted(missing)))
    # 允许缺项时**不要把"子集"整体顶掉已经交付的那一份**：
    # 口径是"已做好的先移入、后续阶段改动了就把旧的替代" —— **只增不减**。
    # 而 `_redo_from` 回退时会把 `demo/`、`运行说明.md`、`SUBMISSION_MANIFEST.json` 搬进
    # cache ⇒ 工作区一时没有它们 ⇒ 若照旧整体替换，**刚交付的 `demo.html` / 运行说明.md
    # 会从 `最新作品/` 里消失**，而链若停在 ⑯ 之前就一直缺着、
    # 与论文末页的清单表对不上。处置：被跳过的项**从旧包里原样搬进 staging**（保留上一版），
    # 等它真产出时自然被新版替换。
    # 判据是「**旧包顶层已有 − 本轮已产出**」，不是"本轮 items 里源缺失的那些"：
    # 后者的漏洞在 **provisional 那条路**上 —— 回退会把
    # `reports/SUBMISSION_MANIFEST.json` 与 `运行说明.md` 一起搬进 cache（`ARTIFACTS["format"]`），
    # 于是中途收走的是"临时清单 = 盘上现在有的东西"，而 `demo.html` / 运行说明.md
    # **连名字都没进清单** ⇒ 整体替换直接把它们从 `最新作品/` 抹掉。
    # 换成"旧包里有、这轮没产出"就两条路都覆盖：真产出了新版的按名字被替换，
    # 这轮没产出的从旧包原样搬过来。
    # 按**文件名**搬运；旧清单用的是老名字（如 `正文.pdf`）而 `body_pdf_name()` 给的是
    # 论文标题时，包里会同时出现两份 —— 那是历史清单才会有的情形，且 ⑭ 会用清单整份重建
    # 收回来。刻意**不**去"钉名字"：钉了反而会在上面那种情况下造出重复。
    # 两条都要，**取并集**（只取第二条会把"清单列了但源缺失"那条覆盖掉，
    # 被 `test_a_partial_rebuild_does_not_delete_already_delivered_files` 逮住）：
    # · 本轮 items 里**源缺失**的项（名字在清单里，但工作区那份被搬走了）；
    # · 旧包里**这轮根本没产出**的项（provisional 那条路下，名字压根没进清单）。
    _carry = []
    if allow_missing:
        produced = {d for _, d in submission}
        if out.is_dir():
            # **目录也要带上**：`其余文件/` 是个**目录**，只收 `p.is_file()` 会让它永远
            # 进不了 `_carry`。可它装着 `内部报告/`、`辅助脚本/`、
            # `正文/`、`附录/` 四棵子树，而 `build_plan` **只在对应源目录还在盘上时**才重建它 ——
            # 于是"回退把 `paper_appendix/` 挪进 cache"这种事一旦发生，旧包里的
            # `其余文件/附录/` 就会**静静消失**（提交件那一层有 `_carry` 兜着，归档这一层没有）。
            _carry += [p.name for p in sorted(out.iterdir()) if p.name not in produced]
    if missing:
        skip = set(missing)
        _carry += [d for s, d in submission if s in skip]
        submission = [(s, d) for s, d in submission if s not in skip]
    _carry = list(dict.fromkeys(_carry))          # 去重（两条路可能点到同一个名字）

    out.parent.mkdir(parents=True, exist_ok=True)
    staging = out.parent / f".{out.name}.building-{uuid.uuid4().hex[:8]}"
    if staging.exists():
        shutil.rmtree(staging)
    try:
        for src, dst in submission:
            _copy(root / src, staging / dst)
        for src, dst in other:
            _copy(root / src, staging / dst)
        # 这轮工作区暂时没有的项：从**旧包**里把上一版搬过来（只在 allow_missing 时才非空）
        for name in _carry:
            old = out / name
            if not old.exists():
                continue
            new = staging / name
            if old.is_dir() and new.is_dir():
                # **合并**，不是替换：这一轮照旧生成了 `其余文件/`（源目录都在
                # 盘上时），只把旧包里**它没覆盖到**的文件补进来 —— 口径是"只增不减"。
                # 整体替换会让这轮没重建的那几棵子树凭空消失。
                _merge_dir(old, new)
            else:
                _copy(old, new)
        if clean_other_submitted:
            flat = {d for _, d in submission}
            aux = staging / OTHER_DIR / "辅助脚本"
            for name in flat:
                if name.lower().endswith(".py"):
                    (aux / name).unlink(missing_ok=True)
        # 旧产物先挪到旁边，成功了再删；失败就还原。
        backup = None
        if out.exists():
            backup = out.parent / f".{out.name}.old-{uuid.uuid4().hex[:8]}"
            out.rename(backup)
        try:
            staging.rename(out)
        except OSError:
            if backup is not None and not out.exists():
                backup.rename(out)
            raise
        if backup is not None:
            shutil.rmtree(backup, ignore_errors=True)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return out


def archive_into_cache(output_dir, cache_dir, name):
    """把产物**内容**切进 `cache/<name>/`（不是 `cache/<ts>_产物/`）。

    同盘时用 rename（快、原子）；跨盘时退回复制 + 删除。`cache/` 必须在项目内。
    """
    out = Path(output_dir).resolve()
    cache = Path(cache_dir).resolve()
    if not out.is_dir():
        raise ValueError(f"产物目录不存在：{out}")
    dest = cache / name
    if dest.exists():
        raise ValueError(f"归档目标已存在：{dest}")
    cache.mkdir(parents=True, exist_ok=True)
    try:
        out.rename(dest)
    except OSError:
        # 跨盘 / 被占用 → 复制过去再删源。不用 shutil.move：它在中途失败时
        # 会留下半份，而这里要的是"要么整份过去、要么原地不动"。
        shutil.copytree(out, dest)
        shutil.rmtree(out)
    return dest
