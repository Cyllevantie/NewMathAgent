# -*- coding: utf-8 -*-
"""裁决侧车自检：交之前先跑一遍，别让驱动替你发现问题。

    python lib/web/check_verdict.py --stage verify
    python lib/web/check_verdict.py --stage rubric --json

为什么要有它：要确认自己那份 `reports/VERIFY_REPORT.verdict.json` 会不会被打回，规格在
`docs/CONTENT_QUALITY.md` 和驱动注入的协议里都写着，但都是**散文**；而**校验器就在
这个仓库里** —— 于是只能去读驱动源码（`lib/web/workflow_quality.py` 读了好几遍、
grep `read_verdict` / `verdict_conflict` / `_evidence`，最后还试着把驱动模块 import 进来跑），
只为回答一个"这份侧车会不会被打回"。

本工具把那件事变成一条命令：**用驱动同一套函数**校验侧车，逐条说清哪里不合格。
`python lib/web/check_skeleton.py` 早就是同一套路（⑨⑭⑦ 的 SKILL 里都写着"跑它，别凭印象动"），
缺的只是裁决 JSON 这一份。

两条纪律：
  ① **判据只此一处** —— 直接调 `content_quality.enforce` 与 `workflow_quality.read_verdict`，
     绝不在这里重写一套规则。重写 = 造出第二个真相源，两边迟早漂移。
  ② **不 import `server.py`** —— 仓库里所有 CLI（`attest` / `healthcheck` / `check_receipts` /
     `check_contract`）都是这个规矩：要驱动的信息走 HTTP，不把整个 FastAPI 应用拖进来。
     阶段顺序因此从 `/api/state` 现取（那份字典的键就是 `STAGES` 的顺序，见 `state2dict`）。
     另外 `regression/test_check_verdict.py` 钉了一条：兜底表必须与 `server.STAGES` 逐项同序。

它只校验**格式与规则**。两件事**不在此列**（别拿它当免责）：
  · 「这份裁决是否**过期**」—— 那是"旧判据 vs 现判据"，由驱动按输入指纹判，改 JSON 改不动；
  · 机械地板（题意契约 / 结构化结果 / 版式 / 图表 / 提交清单）—— 由 `check_skeleton.py`
    与 `python -m lib.publication check` 各管一段，本工具不重复。

退出码：0 = 格式与规则都过（**不代表裁决内容是好消息**，status 可能是 NEEDS_FIX）；
        1 = 侧车会被打回重写（格式/覆盖/一致性问题，逐条列在下面）；
        2 = 找不到侧车、或环境配置不对（先修路径与配置，不是改 JSON）。
"""
import argparse
import json
import sys
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from content_quality import enforce          # noqa: E402
from workflow_quality import read_verdict    # noqa: E402

# 兜底用的阶段顺序。**只在驱动没在跑时才会用到**（正常路径是从 /api/state 现取）。
# 改 `lib/web/server.py` 的 STAGES 时必须同步这里 —— `regression/test_check_verdict.py`
#    有一条用例逐项比对，漏改会红。
FALLBACK_ORDER = [
    # ⓪ 读题（**必须与 `lib/web/server.py` 的 STAGES 逐项一致** ——
    #   `regression/test_check_verdict.py` 有一条用例逐项比对这张表）。
    #   它没有裁决侧车，排在这里只为"驱动没在跑时也能算出正确的阶段顺序"。
    "intake",
    "literature", "analysis", "review", "code", "audit", "robustness", "drawio",
    "figreview", "write", "mathproof", "cross", "rubric", "fix", "format", "verify", "demo",
]

# 这两类 reason 说明**侧车本身不可用**（要重写它），而不是"门禁判了不合格"。
# 其余（structured / verdict_stale / only_optional_remain / advisories_deferred / …）
# 都是**可用的裁决**，只是内容不同 —— 那时该看的是 status 与 issues，不是重写 JSON。
_BROKEN_REASONS = {"verdict_malformed", "verdict_schema", "verdict_conflict",
                   "stage_order_mismatch", "no_report", "missing_sidecar"}


def stage_order(port):
    """阶段顺序：优先问正在跑的驱动（那份字典的键就是 STAGES 的顺序）。"""
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/state", timeout=5) as r:
            data = json.loads(r.read().decode("utf-8"))
        ids = list((data.get("stages") or {}).keys())
        if ids:
            return ids, "驱动 /api/state"
    except Exception:                                   # noqa: BLE001 —— 驱动没跑就退回兜底表
        pass
    return list(FALLBACK_ORDER), "内置兜底表（驱动没在跑；顺序对不对由回归用例钉）"


def _load_sidecar(p):
    """返回 (数据, 错误串)。读不了就把原因原样带出去 —— 那正是要报出去的诊断。"""
    try:
        return json.loads(p.read_text(encoding="utf-8-sig")), None
    except Exception as exc:                            # noqa: BLE001
        return None, f"{exc.__class__.__name__}: {exc}"


def find_sidecar(reports, sid):
    """在 reports/ 下按侧车里的 `stage` 字段找。**不维护"阶段→报告名"第二张表**。

    返回 (命中的路径, 读不出来的候选列表)。第二项不是垃圾 —— `stage` 字段缺失/写坏的
    侧车**根本匹配不上**，而那恰好是最需要报出来的一种坏法。
    """
    hits, unreadable = [], []
    for p in sorted(reports.glob("*.verdict.json")):
        data, err = _load_sidecar(p)
        if err or not isinstance(data, dict):
            unreadable.append((p, err or "顶层不是对象"))
            continue
        if str(data.get("stage") or "").strip() == sid:
            hits.append(p)
        elif not str(data.get("stage") or "").strip():
            unreadable.append((p, "缺 `stage` 字段（匹配不上任何阶段）"))
    return hits, unreadable


def anchors_moved(root, sidecar, decision):
    """找出「引用的文件在**侧车写成之后**又被改过」的锚点。

    为什么必须先做这一步：一份裁决引用了 `paper/sections/6_check.tex` 里的
      `\\subsection{灵敏度分析}` 与一句原文，随后 ⑭ 排版与版式 合法地改了这个文件
      （它有义务"让 PDF 在标题层能指认出稳健性检验模块"）⇒ 引文对不上了。
      此时 `enforce()` 报的是 `verdict_malformed` + 「去补 .verdict.json」—— **处置是错的**：
      裁决内容没问题，是**被指的正文被下游合法改动挪走了**。照着它改 JSON 只会把
      一条正确的判词改坏。正确的处置是「本门禁重判」（驱动自己会判 `verdict_stale`）。

      判据取"文件 mtime 晚于侧车 mtime"——够用且无歧义：侧车写完之后只有**下游**会动那些
      文件，而下游动过就意味着引文位置可能已变。宁可多说一句（这句只是提示，不进 problems、
      不影响退出码），也不要让 agent 照着错处方去改 JSON。
    """
    try:
        side_m = sidecar.stat().st_mtime
    except OSError:
        return []
    out, seen = [], set()
    for check in decision.get("checks") or []:
        for e in (check.get("evidence") or []):
            if not isinstance(e, dict):
                continue
            rel = str(e.get("file") or "").strip()
            if not rel or rel in seen:
                continue
            f = root / rel
            try:
                fm = f.stat().st_mtime
            except OSError:
                continue
            if fm > side_m:
                seen.add(rel)
                import datetime as _dt
                out.append(f"{rel}（侧车 {_dt.datetime.fromtimestamp(side_m):%m-%d %H:%M} "
                           f"→ 该文件 {_dt.datetime.fromtimestamp(fm):%m-%d %H:%M}）")
    return out


def main(argv=None):
    # Windows 控制台默认 GBK，直接打印那个成功标记会 UnicodeEncodeError 崩掉 —— 而输出正是
    # 这个工具唯一的产品。**进程内**改成 utf-8（不依赖调用方先设 PYTHONIOENCODING）。
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:                               # noqa: BLE001
            pass
    ap = argparse.ArgumentParser(description="裁决侧车自检（与驱动同一套校验函数）")
    ap.add_argument("--stage", help="阶段 id，如 verify / rubric / cross")
    ap.add_argument("--verdict", help="直接指定侧车路径；给了它就不必给 --stage")
    ap.add_argument("--root", default=str(HERE.parent), help="项目根（默认取本文件的上一级）")
    ap.add_argument("--port", type=int, default=8901)
    ap.add_argument("--json", action="store_true", help="只输出机器可读的一行 JSON")
    a = ap.parse_args(argv)

    root = Path(a.root).resolve()
    reports = root / "reports"

    def say(msg):
        if not a.json:
            print(msg)

    # ---- 定位侧车 ----
    if a.verdict:
        side = Path(a.verdict)
        if not side.is_absolute():
            side = root / side
        if not side.is_file():
            say(f"✗ 找不到侧车：{side}")
            return 2
        data, err = _load_sidecar(side)
        # 顶层不是对象要在**这里**挡住：`_load_sidecar` 只兜 JSON 语法错，
        #   一份合法 JSON 但是数组/字符串的文件会带着 `data` 走到 `data.get(...)`
        #   ⇒ `AttributeError` 直接吐 traceback（而同一份文件走 `--stage` 时能优雅报"顶层不是对象"）。
        if err or not isinstance(data, dict):
            say(f"✗ 侧车读不出来：{side}\n   {err or '顶层不是对象（必须是 JSON 对象）'}")
            return 1
        sid = a.stage or str(data.get("stage") or "").strip()
        if not sid:
            say(f"✗ 侧车缺 `stage` 字段，无法判它是哪个门禁：{side}")
            return 1
        data = data          # 下面统一用它取 input_digest
    else:
        if not a.stage:
            say("✗ 要么给 --stage，要么给 --verdict")
            return 2
        sid = a.stage
        hits, unreadable = find_sidecar(reports, sid)
        if not hits:
            say(f"✗ reports/ 下没有 `stage: {sid}` 的侧车。")
            for p, why in unreadable:
                say(f"   ⚠ {p.name}：{why}")
            if not unreadable:
                say(f"   （reports/ 现有的侧车："
                    f"{[p.name for p in sorted(reports.glob('*.verdict.json'))] or '一个都没有'}）")
            say(f"   → 门禁必须先写 reports/<报告名>.verdict.json，驱动只认它。")
            return 2
        if len(hits) > 1:
            say(f"⚠ 找到多份 `stage: {sid}` 的侧车，取第一份：{[p.name for p in hits]}")
        side = hits[0]
        data, err = _load_sidecar(side)     # 上面 find_sidecar 已经读通过一次，这里再读一份干净的
        if err:
            say(f"✗ 侧车读不出来：{side}\n   {err}")
            return 1

    # 侧车名 = `<报告名>.verdict.json` ⇒ 去掉后缀得到的是**报告的主名**（`RUBRIC_REVIEW`），
    # 而真实报告是 `RUBRIC_REVIEW.md`。`read_verdict` 第一句就是 `report.is_file()` ——
    # 传主名会让它直接返回 `no_report`，把"报告不存在"当成侧车的问题报出来。
    # 所以按**字符串拼接**补回 `.md`（不用 `with_suffix`：报告名里可能本来就有个点）。
    # 先确认这个名字**真是** `<报告名>.verdict.json`：
    #   无条件按固定长度切后缀 —— 给一个不符合约定的文件名（例如 `foo.json`）
    #   会切出一段垃圾、算出根本不存在的报告路径，然后把「报告不存在」当成
    #   「侧车不可用」报出去（退出码还从 2 变成 1，把环境问题说成内容问题）。
    if not str(side).endswith(".verdict.json"):
        say(f"✗ 侧车名必须形如 `<报告名>.verdict.json`，收到的是：{side.name}\n"
            f"   （驱动也按这个名字找它 —— 名字不对，门禁根本读不到这份裁决）")
        return 2
    _stem = Path(str(side)[:-len(".verdict.json")])
    _md = Path(str(_stem) + ".md")
    report = _stem if _stem.is_file() else (_md if _md.is_file() else _stem)
    order, order_src = stage_order(a.port)
    strict = (root / "config/content_quality.json").exists()

    result = {"stage": sid, "sidecar": str(side.relative_to(root)) if side.is_relative_to(root) else str(side),
              "report": str(report.relative_to(root)) if report.is_relative_to(root) else str(report),
              "strict": strict, "stage_order_from": order_src, "ok": False, "problems": []}

    def fail(*msgs):
        result["problems"].extend(msgs)

    # ---- ① 侧车本身的格式（驱动用同一函数读） ----
    # 传侧车**自己记的** digest：本工具校验格式与规则，不校验"过期"。
    digest = str(data.get("input_digest") or "")
    # 缺 / 空 `input_digest` 必须**当场报**：本工具传的是
    #   "侧车自己记的 digest"，空串与空串相等 ⇒ 这一项**永远不会**被判过期 ⇒
    #   一份缺 digest 的侧车会被判「格式与规则都过」并 exit 0 —— 而驱动那边
    #   `_input_digest(stage)` 与空串不等 ⇒ 判 `verdict_stale` ⇒ 打回重判。
    #   工具说"过"、驱动说"过期"，这正是最坏的一种不一致。
    if not digest.strip():
        result["problems"].append(
            "侧车缺 `input_digest`（空或没有这个字段）—— 驱动会判它**过期**并要求重判。"
            "把驱动注入的 input_digest **原样抄写**进侧车（不要自己更新它去掩盖输入变更）")
    elif ":" not in digest:
        result["problems"].append(
            f"侧车的 `input_digest` 形状不对（{digest[:40]!r}）—— 它应当是 "
            f"`<artifacts>:<instructions>` 两段，驱动按同一形状比对")
    decision = read_verdict(report, sid, digest, allow_v2=strict)
    reason = str(decision.get("reason") or "")
    result["read_reason"] = reason

    if reason == "verdict_conflict":
        c = decision.get("conflict") or {}
        fail(f"报告的裁决行与侧车 JSON 冲突：报告={c.get('markdown')!r}，JSON status={c.get('json')!r}",
             "只改其一使其一致（报告末尾裁决行，或 .verdict.json 的 status）")
    elif reason in _BROKEN_REASONS:
        for i in decision.get("issues") or []:
            fail(f"[{i.get('id')}] {i.get('evidence')}", f"    → {i.get('fix')}")
        if not decision.get("issues"):
            fail(f"侧车不可用（reason={reason}）")

    # ---- ② 规则校验（覆盖、锚点、分类、路由） —— 全在 enforce 里，这里只调它 ----
    dec = decision
    if not (reason == "verdict_conflict"):
        try:
            dec = enforce(root, sid, decision, order)
        except Exception as exc:                        # noqa: BLE001 —— enforce 自己兜了，兜不住就如实报
            fail(f"enforce 抛异常（这通常是驱动侧的问题，不是你 JSON 的问题）："
                 f"{exc.__class__.__name__}: {exc}")

    r2 = str(dec.get("reason") or "")
    if r2 in _BROKEN_REASONS and r2 != reason:
        for i in dec.get("issues") or []:
            fail(f"[{i.get('id')}] {i.get('evidence')}", f"    → {i.get('fix')}")

    status = str(dec.get("status") or "")
    result.update(status=status, reason=r2,
                  issues=len(dec.get("issues") or []),
                  advisories=len(dec.get("advisories") or []),
                  target=dec.get("target"))
    result["ok"] = not result["problems"]

    # ---- ③ 输出 ----
    if a.json:
        print(json.dumps(result, ensure_ascii=False))
        return 0 if result["ok"] else 1

    say(f"侧车   {result['sidecar']}")
    say(f"报告   {result['report']}")
    say(f"严格模式（v2 必填）{'开' if strict else '关'} · 阶段顺序取自{order_src}")
    say("")
    # 只在**真的出了问题**时才提示"文件被改过"。否则它会在每份侧车上都刷一长串 ——
    #   而绝大多数引文其实仍然对得上，
    #   那点噪音会把这个提示本身的价值淹掉。格式过了就说明引文没问题，不必解释为什么。
    moved = anchors_moved(root, side, data if isinstance(data, dict) else {}) \
        if result["problems"] else []
    if moved:
        say("⚠ 这些被引用的文件在**侧车写成之后**又被改过 —— 引文对不上多半是这个原因，"
            "而**不是**你写错了：")
        for m in moved:
            say("   " + m)
        say("   → 正确处置是**本门禁重判**（驱动会判 `verdict_stale`：过期，只能重判）；"
            "不要去补 JSON —— 那会把一条正确的判词改坏。")
        say("")
    if result["problems"]:
        # 有 `moved` 时**不能**再念"改 .verdict.json"那句处方：
        #   上面刚说过"不要去补 JSON"，这里又说"改 JSON"，两段自相矛盾；而且引文对不上
        #   是因为被指的正文被下游挪走了 ⇒ 补 JSON 只会把一条正确的判词改坏。
        if moved:
            say("✗ 下面这些**不要靠改 JSON 去消**（引文对不上是正文被挪走造成的）——"
                "请按上面那条走「本门禁重判」；只有与引文无关的那些才按 docs/CONTENT_QUALITY.md 修：")
        else:
            say("✗ 会被驱动打回（按 docs/CONTENT_QUALITY.md 改 .verdict.json，**不要**重做审查、"
                "不要改报告本体）：")
        for m in result["problems"]:
            say("   " + m)
        say("")
    else:
        say("✓ 格式与规则都过（这**不代表**裁决是好消息 —— 下面才是它判了什么）")
        say("")
    say(f"这份裁决：status = {status or '(空)'} · reason = {r2 or '(空)'} · "
        f"issues {result['issues']} 条 · advisories {result['advisories']} 条"
        + (f" · target = {result['target']}" if result.get("target") else ""))
    if status in {"PASS", "APPROVED", "CLEAN"}:
        say("   → 门禁放行。若有 advisories，驱动会把它们投递给对应阶段的提示（可选项）或"
            "留在面板角标上（必做项）")
    elif status == "REVISE_CLAIM":
        say("   → 纯 claim 判词：交给写作阶段落实，**不拦链**")
    elif status in {"NEEDS_FIX", "REVISE", "REVISE_SOFT", "REVISE_HARD", "FAIL"}:
        say(f"   → 拦链：会转黄灯由人决定回退到哪个阶段"
            + (f"（推荐 {result['target']}）" if result.get("target") else ""))
    elif status == "UNVERIFIED":
        say("   → 未完成/不可用：驱动会要求补齐或重判")
    say("")
    say("提醒：本工具不判「裁决是否过期」（那是输入指纹的事，由驱动判），"
        "也不跑机械地板（题意契约/结构化结果/版式/图表/提交清单）。")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
