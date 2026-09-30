"""Generic workflow evidence, verdict parsing and reusable-stage receipts.

No model calls, solver imports or competition-specific logic belong here.
"""
import hashlib
import json
import re
import threading
import uuid
from pathlib import Path

# 回执文件是**整份读—改—写**的，而写者不止一个 —— 见 `StageReceipts._mutate`。
# 进程内一把锁就够：写者全在 lib/web/server.py 里（run_all 线程、uvicorn 事件循环线程、
# 看门狗线程），跨进程没有写者。RLock 是因为 `flush()` 会在锁内被再调一次。
_RECEIPT_LOCK = threading.RLock()

SCHEMA_VERSION = 1
VERDICTS = {"PASS", "APPROVED", "CLEAN", "FAIL", "REVISE", "REVISE_SOFT",
            "REVISE_HARD", "NEEDS_FIX", "REVISE_CLAIM", "UNVERIFIED"}
IGNORED = {"__pycache__", ".git", ".venv", "node_modules"}
BUILD_SUFFIXES = {".aux", ".toc", ".synctex", ".out", ".log", ".xdv", ".fls",
                  ".fdb_latexmk", ".blg", ".bbl", ".nav", ".snm", ".vrb", ".bcf"}


def _is_paper_build_output(p):
    """paper/ 下由 xelatex 每次编译重写的文件。

    为什么必须排除：15Verification 的 SKILL **要求**跑 xelatex 编译论文（skills/15Verification/SKILL.md「Step 7:
    编译」，且「tex 无而 pdf 有 → 先重编译再判」），而 main.log 首行带编译时刻、main.pdf 带
    /CreationDate 与 /ID —— 内容一字未改、只重编译一次，字节也必然变化。若把它们算进指纹：
    ① verify 会在跑完后被判"输入发生变更" → 整链在最后一关硬挂、交付包永不收集；
    ② write 的回执下一轮必然失配 → 整篇论文被无谓重写。
    main.tex 保留（改 tex 才是真的改论文），figures/ 里的图保留（不是 main 的构建产物）。
    """
    if p.name.endswith(".synctex.gz"):
        return True
    # `paper/page-map.json` 与 `paper/formula-review.json` **也是构建派生的登记件**
    #   （⑭/⑮ 重编译后按物理页**重绑**映射、**重测**公式页）。不排除它们的代价与上面 ①
    #   写的是同一件事：⑮ 的 SKILL 要求它重编译并重绑映射，而它的输入指纹里塞着
    #   **整个 `paper/`**（⑨ 的报告名是 `paper/main`）⇒ 它自己写出的 `page-map.json` 让指纹变了
    #   ⇒ 判「输入在该阶段执行期间被改动」→ `unverified` **硬挂、交付包永不收集**。
    #   （`_LAYOUT_OWNED_PATHS` 里早有 `paper/page-map.json`，但那张表只对 `_CONTENT_SIDE_STAGES`
    #    生效，⑮ 刻意不在其中 —— 它要看含版式的最终成品。所以得在**这里**排。）
    #   判据与 `main.tex` 同一条：**改 `.tex` 才算真的改论文**，登记件是构建的副产品。
    if p.name in ("page-map.json", "formula-review.json"):
        return True
    if p.suffix in BUILD_SUFFIXES:
        return True
    # 只豁免 `main.*` 不够：`paper/` 下还躺着 `baseline.pdf/.aux/.log` 这类历史构建物，
    # 重编译一次基线就会让所有 `paper/` 相关回执（write/format）无故失配。
    # 判据改为：`paper/` 下的 pdf（以及上面的 xelatex 中间文件）一律不入指纹 ——
    # 改 `.tex` 才算真的改论文。
    return p.suffix == ".pdf" or (p.stem == "main" and p.suffix != ".tex")


def fingerprint(root, rels, exclude=()):
    """Hash names and bytes, including missing inputs. Never follow links outside root.

    exclude：相对路径（posix）黑名单，用于共享目录里"别的阶段写的文件"。
    """
    root = Path(root).resolve()
    excluded = {str(e).replace("\\", "/") for e in exclude}
    records = {}
    for rel in sorted(set(rels)):
        base = root / rel
        if not base.resolve().is_relative_to(root):
            raise ValueError(f"Path outside workspace: {rel}")
        if not base.exists():
            records[rel] = None
            continue
        paths = [base] if base.is_file() else sorted(base.rglob("*"))
        records[rel + "/"] = "directory" if base.is_dir() else "file"
        for p in paths:
            local = p.relative_to(root)
            if any(part in IGNORED for part in local.parts):
                continue
            # 排除项 = 精确路径**或它的子路径**：只比精确相等的话，
            #   `exclude=["paper/_base"]` 这种**目录**写法会是个静默空操作
            #   （`lib/web/server.py` 用它做「内容侧不看版式侧」的解耦，就解不开）。
            #   对已有调用点（都传具体文件）行为不变。
            _rel = local.as_posix()
            if _rel in excluded or any(
                    _rel.startswith(e.rstrip("/") + "/") for e in excluded if e):
                continue
            if local.parts[0] == "paper" and _is_paper_build_output(p):
                continue
            if not p.resolve().is_relative_to(root):
                raise ValueError(f"Linked path outside workspace: {local}")
            if p.is_file():
                h = hashlib.sha256()
                with p.open("rb") as f:
                    for block in iter(lambda: f.read(1024 * 1024), b""):
                        h.update(block)
                records[local.as_posix()] = h.hexdigest()
    return hashlib.sha256(json.dumps(records, sort_keys=True).encode()).hexdigest()


def atomic_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(path)


def read_verdict(report, stage_id, input_digest, *, allow_v2=False):
    """Prefer a bound JSON verdict; strict legacy anchors never default to approval."""
    report = Path(report)
    if not report.is_file():
        return {"status": "UNVERIFIED", "reason": "no_report", "issues": []}
    sidecar = report.with_suffix(".verdict.json")
    if sidecar.exists():
        try:
            data = json.loads(sidecar.read_text(encoding="utf-8-sig"))
            if (data.get("schema_version") not in ({1, 2} if allow_v2 else {1}) or data.get("stage") != stage_id
                    or data.get("status") not in VERDICTS
                    or not isinstance(data.get("issues"), list)):
                raise ValueError("invalid verdict identity/schema")
            # 「这份裁决过期了」与「这份裁决写坏了」是**两类**问题，处置完全相反，必须分开报。
            #   两句若共用一条 `raise ValueError`，前者就会被当成"JSON 格式错"：
            #   侧车的 input_digest 与当前对不上（判据文件被改过，而它在门禁的
            #   instructions 指纹里）→ 驱动会交给**改不了它的上游生产阶段**
            #   一句「去补 .verdict.json」⇒ **真发现被整份丢弃**，上游白重写一遍报告。
            #   指纹失配的正确含义是：**这份裁决是按旧判据/旧输入写的，只有重判才有意义** ——
            #   改 JSON 改不动"这份裁决是按另一套要求写下的"这件事。
            #   这里把 findings 原样带出去（`stale_issues`），给人和面板看，但不参与路由。
            if data.get("input_digest") != input_digest:
                # 过期分两种，出路**相反**，所以要把"是哪一段变了"一起报出去：
                #   · 段 0（artifacts = 被审的事实）变了 → findings 指向的正文已经不是现在这份
                #     → 只能在**新正文上重判**；
                #   · 只有段 1+（instructions/注入指令/判据）变了 → 被审的正文**一个字没动**
                #     → findings 仍然指着真实存在的文字，**对上游依旧是有效回执**，
                #     不该把"退给上游"那条路堵死。
                #   只改一次判据文件（如 `skills/_references/stage_discipline.md`）就会让
                #   在飞裁决被判过期，而上游的报告没变 —— 那种情况下要求重判纯属浪费（分钟级）。
                old = str(data.get("input_digest") or "").split(":")
                new = str(input_digest or "").split(":")
                return {"status": "UNVERIFIED", "reason": "verdict_stale", "issues": [],
                        "stale_issues": [i for i in data["issues"] if isinstance(i, dict)],
                        # advisories 也要带上：它是**同一个理由**（被审正文没动时，
                        # 指的文字仍然真实存在）。漏了它，「延后建议随回退投递」那条路
                        # 在过期裁决上就成空转 —— 而正文没动恰恰是这里最常见的情形。
                        "advisories": [a for a in (data.get("advisories") or [])
                                       if isinstance(a, dict)],
                        "stale_digest": {"recorded": data.get("input_digest"),
                                         "current": input_digest,
                                         "artifacts_changed": old[:1] != new[:1]}}
            for issue in data["issues"]:
                if (not isinstance(issue, dict) or not all(isinstance(issue.get(k), str) and issue[k].strip()
                        for k in ("id", "severity", "evidence", "fix", "recheck"))
                        or issue["severity"] not in {"hard", "soft", "info"}):
                    raise ValueError("invalid issue evidence")
            if data["schema_version"] == 1 and data["status"] in {"PASS", "APPROVED", "CLEAN"} and any(
                    i["severity"] != "info" for i in data["issues"]):
                raise ValueError("approval contradicts unresolved issues")
            if data["schema_version"] == 1 and data["status"] == "REVISE_CLAIM" and any(i["severity"] == "hard" for i in data["issues"]):
                raise ValueError("claim-only handoff contains a hard error")
            if "target" in data and (not isinstance(data["target"], str) or not data["target"].strip()):
                raise ValueError("invalid repair target")
            written = _legacy_verdict(report)
            normalize = lambda status: "PASS" if status in {"PASS", "APPROVED", "CLEAN"} else status
            if written["reason"] == "conflicting_verdict":
                # Markdown 自身出现互斥判词：无法判断，保守判 UNVERIFIED
                return {"status": "UNVERIFIED", "reason": "conflicting_verdict", "issues": []}
            # 侧车是 `UNVERIFIED` ⇒ **本阶段还没跑完**（各门禁的"先落骨架"协议：开工第一步就写
            #   报告 + `status=UNVERIFIED` 的侧车，防中断后一片空白）。此时报告末尾那行是**占位**，
            #   不是裁决 —— 拿它跟 UNVERIFIED 比、判成 `verdict_conflict` 是**误判**：
            #   比如一次暂停让 ⑩ 停在骨架上（报告占位行写了 REVISE_HARD、侧车 UNVERIFIED）
            #   ⇒ 下次续跑就会被判「裁决冲突」⇒ 整链停机；而它的 fix 文案是
            #   「使报告末尾裁决行与侧车一致」—— 人改了占位行也还是没判定过，链照样停。
            #   所以跳过这条：让 `read_verdict` 落到下面的结构化校验，交 UNVERIFIED（= 未完成）
            #   ⇒ 驱动走"整段重跑"那条路（`_protocol_repair` 只认 verdict_malformed ⇒ 不会
            #   只补侧车把没判过的报告洗成通过）。
            if (written["status"] != "UNVERIFIED" and data["status"] != "UNVERIFIED"
                    and normalize(written["status"]) != normalize(data["status"])):
                # JSON 与 Markdown 裁决不一致：取更保守的非 PASS 并记冲突项，
                # 而不是整条 UNVERIFIED（那会丢掉诊断并触发整段重跑）。
                conservative = written["status"] if normalize(data["status"]) == "PASS" else data["status"]
                if normalize(conservative) == "PASS":
                    conservative = "REVISE"
                conflict = {"id": "verdict_conflict", "severity": "hard",
                            "evidence": f"Markdown={written['status']} JSON={data['status']}",
                            "fix": "使报告末尾裁决行与 .verdict.json 的 status 一致（只改其一）",
                            "recheck": "重读报告末尾裁决行与侧车 JSON"}
                return dict(data, reason="verdict_conflict", status=conservative,
                            issues=list(data["issues"]) + [conflict],
                            conflict={"markdown": written["status"], "json": data["status"]})
            return dict(data, reason="structured")
        except (ValueError, TypeError, AttributeError, OSError) as exc:
            return {"status": "UNVERIFIED", "reason": str(exc), "issues": []}
    return _legacy_verdict(report)


def _legacy_verdict(report):
    """从 Markdown 正文里读整题裁决。

    两条正则**必须分开**：很多报告会逐问写「- 结论：PASS（Q1 数值正确）」，末尾再写
    「整题结论：NEEDS_FIX」。若只用一个"前缀可选"的正则，逐问行也会被当成整题裁决，
    于是 found={PASS, NEEDS_FIX} → 判 conflicting_verdict → 整份合法 v2 侧车被丢弃，
    而驱动的修复提示又只让"补侧车、别动报告本体"，两轮后必然挂起。
    规则：只要报告里出现了**显式整题**判词，就以它为准，逐问行一律不算数；
    完全没有显式整题行时，才回退到旧行为（保证历史报告仍可读）。
    """
    tokens = "|".join(sorted(VERDICTS, key=len, reverse=True))
    tail = rf"({tokens})(?=$|\s|[（(：:，,。])"
    overall = r"(?:整题(?:门禁)?|总体|最终|本阶段|评审|全题|本题)"
    explicit = re.compile(rf"^(?:{overall}\s*(?:裁决|结论|门禁动作)\s*[:：]\s*|整题\s+){tail}", re.I)
    loose = re.compile(rf"^(?:{overall}?\s*(?:裁决|结论|门禁动作)\s*[:：]\s*|整题\s+)?{tail}", re.I)
    strict, anything = set(), set()
    in_code = False
    for line in report.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        if line.strip().startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            continue
        line = re.sub(r"^[\s#>*\-]+", "", line).replace("**", "").strip()
        mark = explicit.match(line)
        if mark:
            strict.add(mark.group(1).upper())
        mark = loose.match(line)
        if mark:
            anything.add(mark.group(1).upper())
    found = strict or anything
    # Synonymous passing markers are compatible; mixed/historical decisions are not.
    if found and found <= {"PASS", "APPROVED", "CLEAN"}:
        return {"status": "PASS", "reason": "legacy_explicit", "issues": []}
    if len(found) == 1:
        return {"status": found.pop(), "reason": "legacy_explicit", "issues": []}
    return {"status": "UNVERIFIED", "reason": "conflicting_verdict" if found else "missing_verdict", "issues": []}


class StageReceipts:
    def __init__(self, path):
        self.path = Path(path)
        self._load()

    def _load(self):
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
            self.records = value["stages"] if value.get("schema_version") == SCHEMA_VERSION else {}
            if not isinstance(self.records, dict):
                self.records = {}
        except (OSError, ValueError, KeyError, AttributeError):
            self.records = {}

    def _mutate(self, change):
        """改盘上的回执：**锁内重读 → 改 → 写**。

        为什么必须锁内重读：「构造时读一份快照 → 保存时整份写回」的写法下，写者不止一个
          —— run_all 线程、uvicorn 事件循环（`/api/redo`、`/api/decision`）、看门狗 ——
          于是把**旧快照**写回去的那个，会连**中间新增的回执**一起盖掉。丢的是
          `self.records[stage] = ...` 之外的一切，**没有任何日志**，症状就是某个阶段
          「明明成功跑完了，却像没跑过」→ 下次重启从它重来（小时级重跑）。
          具体形态：黄灯期间「任务继续运行」、旧链没被杀，两次回退的写者各持一份
          快照，后写的那份把先写的整份盖掉 ⇒ 某个阶段刚写下的回执消失 ⇒
          重启时它读不到回执、全链从该阶段重来。
        锁内重读之后：「后写者赢」不再是丢更新的理由，它只是覆盖**同一条**回执。
        """
        with _RECEIPT_LOCK:
            self._load()
            change()
            self.flush()

    def matches(self, stage, inputs, outputs):
        r = self.records.get(stage)
        return isinstance(r, dict) and r.get("inputs") == inputs and r.get("outputs") == outputs

    def save(self, stage, inputs, outputs, run_id, manual=False, artifacts=None, instructions=None):
        """`manual=True` 表示这张回执是**人工认证**写下的（见 lib/web/server.py 的 attest 动作）。

        为什么要在回执里记这个：`run_all` 每次都会把所有阶段重置成 idle，attest 设下的
        `done(manual)` 会被立刻抹掉；而前端要求「三种完成长得不一样」
        （干净通过 / 已披露放行 / 人工认证），把人工认证画成干净通过等于对读报告
        的人撒谎。阶段**真跑过一次**就会以 `manual=False` 覆盖它，标记自然消失。
        """
        record = {"inputs": inputs, "outputs": outputs, "run_id": run_id,
                  "manual": bool(manual),
                  # 输入拆两半存（见 server._input_split）：`artifacts` 变了必须重做，
                  # 只有 `instructions` 变了只需标记。旧回执没有这两个字段 → None，
                  # 与任何当前值都不相等 → 走正常重跑，安全。
                  "artifacts": artifacts, "instructions": instructions}
        self._mutate(lambda: self.records.__setitem__(stage, record))

    def is_manual(self, stage):
        r = self.records.get(stage)
        return bool(isinstance(r, dict) and r.get("manual"))

    def invalidate(self, stages):
        # `stages` 常常是生成器（`(s["id"] for s in STAGES[index:])`）—— 锁内重读后
        # 只能迭代一次，所以**先取出来**再进锁。
        names = list(stages)
        self._mutate(lambda: [self.records.pop(n, None) for n in names])

    def flush(self):
        with _RECEIPT_LOCK:
            atomic_json(self.path, {"schema_version": SCHEMA_VERSION, "stages": self.records})
