# -*- coding: utf-8 -*-
"""返修台账自检：**返修记录不许自证**。

为什么要有它：门禁给出的回执被逐条「处置」后，报告里会出现
一张「本轮返修复验记录」表，写着「① §15.1 该句改『≤0.98%』」。问题在于 —— **这句话本身就是
`≤0.98%` 的一次出现**，于是拿「全文检索 ≤0.98%」当自检，记录自己把自己证明了。

被判成"通过"的典型形态（正文一字未改）：

| 回执要求 | 返修记录写 | 正文实际 |
|---|---|---|
| §15.1「偏差 ≤0.4%」→ ≤0.98% | 「③ 已改」 | 正文仍写 ≤0.4%；`≤0.98%` 只在版本表/记录里 |
| §15.2 改「自 66600 s 起」 | 「① 已改」 | `66600` 三处命中全在版本表/记录里 |
| §2 A3/§9.9 T4 补 `M3`、`热供给` | 「已做」 | 两串只在记录里出现，正文 0 命中 |

另一类是 **前缀碰撞**：回执要求增 `q4.moist_max_at_tend`，实际只加了
`q4.moist_max_at_tend_minus_60s`，而回执给的「检索 ≥1 命中」照样通过。

本模块只做两件机械的事：

1. **自证隔离** —— 探针必须落在「版本 / 修订 / 返修 / 变更」这类记录节**之外**。
2. **前缀防护** —— ASCII 探针按标识符边界匹配，不许被更长的串撞上。

它**不**判断改动对不对（那是门禁的活），只保证「已实施」这句话是**可证伪的**。
"""
import json
import re
from pathlib import Path

from content_quality import _norm

LEDGER_REL = "reports/RECEIPT_LEDGER.json"
LEDGER_DEFAULT_REPORT = "reports/ANALYSIS_MODELING_REPORT.md"
DISPOSITIONS = {"applied", "partial", "not_applied", "deferred"}
# 「记录节」= 版本/修订/返修/变更历史所在的节。它**不能当证据**：
# 记录里那句「已改为 X」本身含 X，拿它检索必然命中 —— 这就是「记录自证」。
RECORD_HEADING_RE = re.compile(r"(版本|修订|返修|变更|更改|修改记录|changelog|revision|history)", re.I)
# 回执 `fix` 里的分项标记：①②③…（U+2460–U+2473 覆盖到 ⑳，够用）。
# 为什么需要它：一条回执项**可以是复合的**。回执的 `fix` 里有 ①②③④ 四小项
# （补假设 / 改写理由 / 换论证 / 补披露清单）时，只给一个探针就签了 `applied`
# —— 「改了一半、记 applied」照样过。数出小项个数，才知道该要几个探针。
SUBDIGIT_RE = re.compile(r"[①-⑳]")


def _fold(text):
    """探针与正文用同一套折叠比对（全角标点 / 空白 / 减号变体），避免排版差异造成假失败。"""
    return _norm(text).replace("−", "-").replace("–", "-").replace("—", "-")


def _record_zone(lines):
    """逐行标出是否落在「记录节」里 —— **任何层级**的祖先标题命中都算。

    只看自己那一级不够：`### 15.1 本轮返修复验记录` 挂在 `## 15. 版本与修订历史` 下，
    两级都得算记录区。
    """
    stack, flags = [], []
    for line in lines:
        m = re.match(r"^(#{1,6})\s+(.*)$", line)
        if m:
            lvl = len(m.group(1))
            while stack and stack[-1][0] >= lvl:
                stack.pop()
            stack.append((lvl, bool(RECORD_HEADING_RE.search(m.group(2)))))
        flags.append(any(rec for _, rec in stack))
    return flags


def _probe_hits(lines, flags, probe):
    """返回 (证据区命中行号, 记录区命中行号)。ASCII 探针按标识符边界匹配，防前缀碰撞。"""
    needle = _fold(probe)
    if not needle:
        return [], []
    # 边界只对 ASCII 探针生效：Python 的 `str.isalnum()` 对汉字也返回 True，
    # 若不分流，中文探针会被要求"两侧不能是汉字" → 永远匹配不到。
    ascii_probe = all(ord(c) < 128 for c in needle)
    wordish = (lambda ch: ch.isalnum() or ch == "_") if ascii_probe else (lambda ch: False)
    ev, rec = [], []
    for i, raw in enumerate(lines):
        hay = _fold(raw)
        start = 0
        while True:
            j = hay.find(needle, start)
            if j < 0:
                break
            start = j + 1
            if wordish(needle[0]) and j > 0 and wordish(hay[j - 1]):
                continue                              # 撞在更长的串尾巴上（前缀碰撞）
            end = j + len(needle)
            if wordish(needle[-1]) and end < len(hay) and wordish(hay[end]):
                continue                              # 撞在更长的串头上
            (rec if flags[i] else ev).append(i + 1)
    return ev, rec


def _count_subitems(text):
    """回执项的 `fix` 里列了几个小项（①②③… 各算一个，去重后计数）。

    没有标记 → 1（整条就是一项）。判据只取 `fix`，**不取 `recheck`** ——
    `recheck` 常把「复跑某脚本」「复算某常数」这类验证步骤也编号进去（例如 fix 4 项、
    recheck 6 项），拿它当分母会把"验证步骤"也算成必须交探针的改动，
    逼人给验证步骤编一个假探针。
    """
    found = []
    for ch in SUBDIGIT_RE.findall(text or ""):
        if ch not in found:
            found.append(ch)
    return max(1, len(found))


def _as_probes(item):
    """台账项的探针：新写法 `probes: [...]`；旧写法 `probe: "..."` 当单元素列表。"""
    probes = item.get("probes")
    if isinstance(probes, list):
        return probes, "probes"
    if isinstance(item.get("probe"), str):
        return [item["probe"]], "probe"
    return [], "probes"


def _receipts(root):
    """`runtime/quality/feedback/**` 下带 issues 的回执，按 mtime 升序。"""
    base = root / "runtime/quality/feedback"
    if not base.is_dir():
        return []
    found = []
    for p in sorted(base.glob("*/*/*.json")):
        try:
            obj = json.loads(p.read_text(encoding="utf-8-sig"))
            found.append((p.stat().st_mtime, p))
        except (OSError, UnicodeError, ValueError, AttributeError):
            continue
    return [p for _, p in sorted(found)]


def receipt_ledger_issues(root, require=False):
    """核对 `reports/RECEIPT_LEDGER.json`。返回问题串列表（空 = 通过）。

    `require=True`：驱动在**刚给该阶段发过返修回执**时用 —— 此时即使 glob 找不到回执
    （比如反馈目录被清过），也必须交台账。默认 False：没有回执 = 首轮，不算问题。
    """
    root = Path(root).resolve()
    receipts = _receipts(root)
    ledger_path = root / LEDGER_REL
    if not ledger_path.is_file():
        if not receipts and not require:
            return []
        newest = receipts[-1].relative_to(root).as_posix() if receipts else "（无回执）"
        return [f"缺返修台账 {LEDGER_REL}：本轮是带着返修回执跑的（最新回执 {newest}），"
                f"必须逐条交代每条回执项的处置，并给出**可证伪的探针**。"
                f"格式见 skills/_references/stage_discipline.md 六·6.3。"]
    try:
        led = json.loads(ledger_path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, ValueError) as exc:
        return [f"返修台账不可读：{LEDGER_REL}（{exc}）"]
    if not isinstance(led, dict):
        return [f"返修台账结构错误：{LEDGER_REL} 顶层必须是对象"]
    if led.get("schema_version") != 1:
        return [f"返修台账 schema_version 必须是 1（现为 {led.get('schema_version')!r}）"]
    items = led.get("items")
    if not isinstance(items, list) or not items:
        return [f"返修台账 items 必须是非空列表（{LEDGER_REL}）"]

    problems, seen = [], []

    # ---- 回执对账：声明的 receipt 必须存在、且就是最近那一份 ----
    declared = led.get("receipt")
    receipt_obj = None
    if not isinstance(declared, str) or not declared.strip():
        problems.append("返修台账缺 receipt 字段：必须写明这一轮答的是哪份回执")
    else:
        rp = (root / declared).resolve()
        try:
            rp.relative_to(root)
        except ValueError:
            problems.append(f"receipt 越出工作区：{declared}")
            rp = None
        if rp is not None and not rp.is_file():
            problems.append(f"receipt 指向的文件不存在：{declared}")
        elif rp is not None:
            try:
                receipt_obj = json.loads(rp.read_text(encoding="utf-8-sig"))
            except (OSError, UnicodeError, ValueError) as exc:
                problems.append(f"receipt 不可读：{declared}（{exc}）")
        if receipts:
            newest = receipts[-1].relative_to(root).as_posix()
            if declared.strip() != newest:
                problems.append(f"receipt 指错了：台账写 {declared}，最近一次回执是 {newest}"
                                "（答错回执 = 答非所问）")

    # 回执项 id → 它 `fix` 里列了几个小项（复合判词要几个探针，见 _count_subitems）
    need = {}
    if isinstance(receipt_obj, dict):
        for i in receipt_obj.get("issues") or []:
            if isinstance(i, dict) and str(i.get("id") or "").strip():
                need[str(i["id"])] = _count_subitems(i.get("fix"))
    want = list(need)

    rep_rel = str(led.get("report") or LEDGER_DEFAULT_REPORT)
    lines, flags = None, None
    if any(isinstance(i, dict) and i.get("disposition") in {"applied", "partial"} for i in items):
        rp = (root / rep_rel).resolve()
        if not rp.is_file():
            problems.append(f"报告不存在：{rep_rel}")
        else:
            try:
                lines = rp.read_text(encoding="utf-8-sig").splitlines()
                flags = _record_zone(lines)
            except (OSError, UnicodeError) as exc:
                problems.append(f"报告不可读：{rep_rel}（{exc}）")

    for n, item in enumerate(items, 1):
        if not isinstance(item, dict):
            problems.append(f"台账第 {n} 项不是对象")
            continue
        iid = str(item.get("id") or "").strip()
        if not iid:
            problems.append(f"台账第 {n} 项缺 id")
            continue
        seen.append(iid)
        disp = item.get("disposition")
        if disp not in DISPOSITIONS:
            problems.append(f"[{iid}] disposition 非法：{disp!r}（合法值 {sorted(DISPOSITIONS)}）")
            continue
        probes, field = _as_probes(item)
        probes = [p for p in probes if isinstance(p, str) and p.strip()]
        if disp in {"not_applied", "deferred"}:
            if probes:
                problems.append(f"[{iid}] 标了 {disp} 却给了 {field}：没做的事不能有证据")
            why = item.get("reason")
            if not isinstance(why, str) or not why.strip():
                problems.append(f"[{iid}] 标了 {disp}，必须写 reason（为什么没做）")
            continue
        # ---- 以下是 applied / partial：必须有可证伪的探针，**且复合判词要逐小项给** ----
        n = need.get(iid, 1)
        if not probes:
            problems.append(f"[{iid}] 标了 {disp}，必须给 probes —— 每个 ≥2 字符、"
                            "**改动后才会出现在正文里**的检索串")
            continue
        # `applied` 不能只看"有没有一个探针"，因为回执项**可以是复合的**：
        #   回执的 `fix` 里是 ①②③④ 四小项时，只给一个探针就签 applied
        #   —— 「改了一半、记 applied」照样过关。所以按 `fix` 里的小项个数要探针。
        if disp == "applied" and len(probes) < n:
            problems.append(f"[{iid}] 标了 applied，但这**不是单一小项**：回执的 `fix` 里有 {n} 个"
                            f"（①②③…），只给了 {len(probes)} 个探针 —— 一个探针证不了另外几项真落到了正文。"
                            f"要么逐小项各给一个探针，要么改成 partial 并把没做的写进 remaining。")
        if disp == "partial":
            rem = item.get("remaining")
            if not isinstance(rem, str) or not rem.strip():
                problems.append(f"[{iid}] 标了 partial，必须写 remaining（哪几条没做）"
                                " —— 只做一半却标 applied 正是这次的病灶")
        # 探针之间不许互相包含：否则 ["μ·J₁(μ) = Bi·J₀(μ)", "μ·J₁(μ)"] 这种
        # 一个句子的两截就能凑够数，等于换一种方式拿一个证据签整条。
        for a in probes:
            for b in probes:
                if a != b and a.strip() in b:
                    problems.append(f"[{iid}] 探针 {a!r} 是 {b!r} 的一截 —— "
                                    "拿同一句话的片段凑数不算逐小项给证据")
                    break
            else:
                continue
            break
        if lines is None:
            continue
        for probe in probes:
            ev, rec = _probe_hits(lines, flags, probe)
            if ev:
                continue
            if rec:
                problems.append(
                    f"[{iid}] 探针 {probe!r} **只**出现在版本/返修记录区（第 {rec[:5]} 行），"
                    f"正文里一次都没有 —— 这就是「返修记录自证」：记录里那句「已改为 {probe}」"
                    f"自己就是命中。要么真改到正文，要么改成 not_applied/partial 并写清哪几条没做。")
            else:
                problems.append(f"[{iid}] 探针 {probe!r} 在 {rep_rel} 全文 0 命中 —— 它证明不了任何事。"
                                "换一个改动后才会出现的串（并注意别被更长的串前缀撞上）。")

    if want:
        missing = [i for i in want if i not in seen]
        extra = [i for i in seen if i not in want]
        if missing:
            problems.append(f"返修台账漏了回执里的 {len(missing)} 条：{missing[:8]}"
                            " —— 每条回执项都要交代，不许挑着答")
        if extra:
            problems.append(f"返修台账有回执里不存在的 id：{extra[:8]}")
    return problems
