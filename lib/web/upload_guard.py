# -*- coding: utf-8 -*-
"""上传守卫：把"浏览器给的相对路径"变成"工作区里安全的落点"，并管住体量与重名。

为什么单独成模块：上传支持"一键传整个文件夹"，**客户端能指定嵌套路径** ——
  而 `lib/web/server.py:6276` 那句 `Path(f.filename).name` 会把整条路径丢掉、只留基名，
  挡不住目录穿越。要保住目录结构（本题的 `request/attachments/附件3/` 就是
  子目录，既有 code 按写死的相对路径找它），就必须自己逐段校验。
  这是**安全关键**代码，所以做成纯函数、脱服务可单测（照 `attest.py` / `workflow_quality.py`
  的先例）—— 不许藏在 endpoint 里靠手工点几下验证。

纪律（与 `lib/delivery/core.py:81` 的 `_ILLEGAL`、`delivery_name()` 的"只拒绝不替换"同源）：
  **不合法就拒绝并说清怎么办，绝不静默改名或悄悄丢弃** —— 静默处理会让"哪份文件是哪份"
  事后无法追，而上传的东西正是整条链的事实基准。
"""
import re

# ---- 体量上限 ----
# 数字口径（见过的最大的附件包**没超过 20 MB**）：所以这里取
# 3~6 倍余量、只当"选错文件夹"的护栏，不当配额 —— 真超了文案会告诉他怎么放宽。
#   · 件数上限另有用处：starlette 自己的硬顶是 1000，超了抛的错读不懂。
MAX_FILES = 300                       # 件数
MAX_TOTAL_BYTES = 128 * 1024 * 1024   # 整批 128 MiB
MAX_FILE_BYTES = 64 * 1024 * 1024     # 单件 64 MiB
MAX_REL_LEN = 240                     # 整条相对路径（Windows MAX_PATH 余量）
MAX_SEG_LEN = 100                     # 单段

# 系统/编辑器自动生成的垃圾，浏览器目录上传时一定会带出来 —— 跳过并**记日志**（不静默）。
SKIP_NAMES = {"thumbs.db", "desktop.ini", ".ds_store"}

# Windows 保留设备名：**带扩展名也算**（`con.txt` 在 Windows 上照样打不开）
_WIN_RESERVED = ({"con", "prn", "aux", "nul"}
                 | {f"com{i}" for i in range(1, 10)}
                 | {f"lpt{i}" for i in range(1, 10)})
# 与 `lib/delivery/core.py:81` 同一张表（Windows 文件名非法字符）
_ILLEGAL_CHARS = set('\\/:*?"<>|')
_CONTROL_RE = re.compile(r"[\x00-\x1f]")


class UploadRejected(ValueError):
    """带**中文可执行文案**的拒绝：`message` 说清哪里不对，`hint` 说清怎么办。"""

    def __init__(self, message, hint=""):
        super().__init__(message)
        self.message = message
        self.hint = hint

    def __str__(self):
        return f"{self.message}（{self.hint}）" if self.hint else self.message


def safe_rel_path(raw):
    """浏览器给的相对路径 → 工作区内安全的正斜杠相对路径。不合法抛 `UploadRejected`。

    先做的三件归一化（都无歧义、也都不放宽安全性）：
      · 反斜杠 → 正斜杠（`webkitRelativePath` 用的是 `/`；命令行客户端可能给 `\\`）；
      · 去掉开头的 `./`；
      · 丢掉空的与 `.` 段（`a//b`、`a/./b` 都归一成 `a/b`）。

    然后逐段卡：`..` 段、盘符/绝对路径/UNC、Windows 保留名（含 `con.txt`）、
    尾随点或空格（Windows 会把它悄悄吃掉）、非法字符与控制字符、单段/整串超长。
    只做**词法**校验，落盘前调用方**必须**再用 `resolve()` + `is_relative_to()`
      复核一次（照 `lib/web/server.py:6329-6330` 的写法：`startswith` 的字符串前缀
      会把兄弟目录放进来）。
    """
    if not isinstance(raw, str) or not raw.strip():
        raise UploadRejected("上传里有一条没有文件名的记录", "请用页面的「选文件夹」重传")
    # 只归一化斜杠，**不做整串 strip**（整串 strip 会把单段的 `"x "` 悄悄改成 `"x"` 收下 ——
    #   名字是上传者的东西，驱动无权替他改；首尾空白一律按段拒绝）。
    s = raw.replace("\\", "/")
    if s.startswith("/") or s.startswith("//"):
        raise UploadRejected(f"这是一条绝对路径，不能作为上传落点：{raw!r}",
                             "请用页面的「选文件夹」按钮，浏览器只给相对路径")
    if re.match(r"^[A-Za-z]:", s):
        raise UploadRejected(f"路径里带盘符，不能作为上传落点：{raw!r}",
                             "请用页面的「选文件夹」按钮")
    segs = []
    for seg in s.split("/"):
        if seg in ("", "."):
            continue
        if seg == "..":
            raise UploadRejected(f"路径里有 `..`，会被判成越界：{raw!r}",
                                 "上传只接受文件夹内部的相对路径")
        if len(seg) > MAX_SEG_LEN:
            raise UploadRejected(f"目录/文件名太长（{len(seg)} 字，上限 {MAX_SEG_LEN}）：{seg[:40]}…",
                                 "把这一层名字改短些再传")
        if seg != seg.strip() or seg.endswith("."):
            raise UploadRejected(f"名字以空格或点开头/结尾，Windows 上会被悄悄改掉：{seg!r}",
                                 "去掉首尾的空格与点")
        if _CONTROL_RE.search(seg):
            raise UploadRejected(f"名字里有控制字符：{seg!r}", "重命名后再传")
        bad = sorted(set(seg) & _ILLEGAL_CHARS)
        if bad:
            raise UploadRejected(f"名字里有 Windows 不允许的字符 {' '.join(bad)}：{seg!r}",
                                 "把这些字符去掉或换成别的再传")
        # 保留名：整名或"主名"命中都算（`nul`、`nul.txt`、`COM3.csv`）
        if seg.split(".")[0].lower() in _WIN_RESERVED:
            raise UploadRejected(
                f"这是 Windows 的保留设备名，建不出这个文件：{seg!r}",
                "换个名字（例如加个前缀）再传")
        segs.append(seg)
    if not segs:
        raise UploadRejected(f"路径里没有有效的文件名：{raw!r}", "重命名后再传")
    rel = "/".join(segs)
    if len(rel) > MAX_REL_LEN:
        raise UploadRejected(
            f"整条相对路径太长（{len(rel)} 字，上限 {MAX_REL_LEN}）：{rel[:60]}…",
            "把外层文件夹名改短些再传（Windows 对整条路径有长度限制）")
    return rel


def is_skippable(rel):
    """系统/编辑器生成的垃圾文件（大小写不敏感）。跳过它们要**记日志**，不许悄悄丢。"""
    name = rel.rsplit("/", 1)[-1]
    return name.lower() in SKIP_NAMES or name.startswith("~$")


def plan_inbox(rels, sizes=None):
    """校验整批并给出落盘清单：`(要收的相对路径, 跳过的垃圾)`。超限抛 `UploadRejected`。

    `sizes` 给了就一并查单件/整批体量与件数（没给就只做路径校验，便于单测）。
    """
    if not rels:
        raise UploadRejected("这批上传里没有文件", "重新选一次文件夹")
    keep, skipped = [], []
    for raw in rels:
        rel = safe_rel_path(raw)
        if is_skippable(rel):
            skipped.append(rel)
            continue
        if rel in keep:
            # 同一条相对路径出现两次（同一个包的重复条目）—— 不是上传方能修的错，拒绝更诚实
            raise UploadRejected(f"同一个包里出现了两条同名记录：{rel}",
                                 "文件夹里可能有一份是副本，去掉重复的再传")
        keep.append(rel)
    if not keep:
        raise UploadRejected("这批上传里全是系统生成的临时文件（Thumbs.db 之类）",
                             "选真正的题目文件夹再传")
    clash = collisions(keep)
    if clash:
        # 在**计划阶段**就拒，而不是落盘时才发现：落盘时两份原件已经都在暂存区，
        #   只能靠"后写的盖掉先写的"，而上传方拿不到任何提示（`server.py:6278` 就这样）。
        bad = "、".join(f"{v[0]} ↔ {v[1]}" for v in list(clash.values())[:4])
        raise UploadRejected(
            f"有 {len(clash)} 处同名冲突（Windows 上大小写也算同名）：{bad}",
            "把重名的文件改掉，或分别放进不同子文件夹再传")
    if len(keep) > MAX_FILES:
        raise UploadRejected(
            f"文件太多（{len(keep)} 件，上限 {MAX_FILES}）：这个包可能选错了文件夹",
            "只传这道题需要的材料；数据文件多的话打包成 .zip 一起传（或告诉我要放宽上限）")
    if sizes is not None:
        if len(sizes) != len(rels):
            raise UploadRejected("上传的体积信息与文件数不匹配", "用页面的「选文件夹」重传")
        # sizes 与 rels 位置对应；被跳过的也要计入，否则上限能被垃圾文件绕过
        for raw, size in zip(rels, sizes):
            if not is_skippable(safe_rel_path(raw)) and size > MAX_FILE_BYTES:
                raise UploadRejected(
                    f"单个文件超过 {MAX_FILE_BYTES // (1024 * 1024)} MiB："
                    f"{raw}（{size / (1024 * 1024):.1f} MiB）",
                    "大文件先裁剪或压缩；确实需要就这么传的话告诉我，我调上限")
        total = sum(sizes)
        if total > MAX_TOTAL_BYTES:
            raise UploadRejected(
                f"整批超过 {MAX_TOTAL_BYTES // (1024 * 1024)} MiB（"
                f"{total / (1024 * 1024):.1f} MiB）",
                "只传这道题需要的材料；或告诉我实际包多大，我调上限")
    return keep, skipped


def collisions(rels):
    """同一落点被两份原件指向 ⇒ `{落点: [原件…]}`。按**整条相对路径**比、大小写不敏感。

    为什么大小写不敏感：Windows 上 `A.xlsx` 与 `a.xlsx` 是**同一个文件**，两份原件会
      静默互相覆盖（`server.py:6278` 的 `write_bytes` 就是无条件截断）。
    为什么按整条路径而不是基名：`附件3/result1.xlsx` 与 `结果/result1.xlsx` 结构不同、
      落点就不同，不该算撞名（这也正是"保住目录结构"的收益）。
    """
    seen = {}
    for rel in rels:
        seen.setdefault(rel.lower(), []).append(rel)
    return {v[0]: v for k, v in seen.items() if len(v) > 1}
