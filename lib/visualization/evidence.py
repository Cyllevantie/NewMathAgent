"""Dependency-free provenance and review gate. Recording a review is an attestation,
not proof that a person or model actually inspected the image.
"""
import hashlib
import json
import re
import subprocess
import sys
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

# `figures/manifest.json` 是**整份读—改—写**的，而写者不止一个 —— 见 `_mutate`。
# 与 `workflow_quality._RECEIPT_LOCK` 同构。RLock 因为 `_mutate` 内部
# 不再嵌套调用（但留着它，将来谁在锁内再调一次不会自己死锁）。
_MANIFEST_LOCK = threading.RLock()


def path_in(root, rel):
    root = Path(root).resolve()
    p = (root / rel).resolve()
    if not p.is_relative_to(root):
        raise ValueError(f"Path escapes project: {rel}")
    return p


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(path)


def load(root):
    p = path_in(root, "figures/manifest.json")
    if not p.exists():
        return {"schema_version": 1, "figures": {}}
    data = json.loads(p.read_text(encoding="utf-8"))
    if data.get("schema_version") != 1 or not isinstance(data.get("figures"), dict):
        raise ValueError("Invalid figure manifest")
    return data


def _mutate(root, change):
    """改 `figures/manifest.json`：**锁内重读 → 改 → 写**。

    与 `workflow_quality.StageReceipts._mutate` 同构。不这样做就会丢更新：若各自
    「进来读一份快照 → 改 → 整份写回」，平时写者只有一个（画图脚本逐张 register），
    但**重画那一轮恰恰不是** —— `make_figures.run()` 会连着 register 8 张，而 ⑨ 排版
    阶段的「重画图的口子」也可能在同一工作区里跑；两个快照交叠时，后写的那个会把它读快照
    之后才 register 的那几条**整段抹掉**。症状是 `audit` 报「未登记图表」（文件在盘上、
    registry 里没有），看起来像**图丢了**，其实是**登记**丢了 —— 与"回退清空 figures/"
    那种猜测完全是两回事。

    （`write_json` 本身已经是原子的 temp+replace，所以这里防的不是写坏，是丢更新。）
    """
    with _MANIFEST_LOCK:
        data = load(root)
        change(data)
        write_json(path_in(root, "figures/manifest.json"), data)


# 图的**像素**由这几个模块产出 —— 只有它们变了，图才可能变。
# 这里不能用 `lib/visualization/*.py` 整目录：那是把**检查器**也哈希进了每一张图。
#   只改 `quality.py` 里一条 warning 判据（加"单侧贴边非白带"），11 张图会**全部**被判
#   「数据、脚本、配置或图片已改变，需重新生成和复核」⇒ 逼着 ⑦/⑧ 把整套图重画重看一遍，
#   而像素一个都没动。这与 `docs/WORKFLOW_RELIABILITY.md` 记的「共享文件被整目录哈希进每个阶段」
#   是同一条道理：**按真实依赖定指纹，不按目录归属**。
#   `quality.py`（检查器）、`evidence.py`（登记簿本身）、`__main__.py`/`example.py`/`__init__.py`
#   都不产像素，故不在列。要让全部图重判（例如收紧了检查口径、想重看一遍），动
#   `config/visualization.json` —— 它在快照里，这是有意的口子。
PIXEL_PRODUCERS = ("charts.py", "schematic.py", "geometry.py", "dense.py", "export.py")


def snapshot(root, entry):
    root = Path(root).resolve()
    files = set(entry["sources"] + entry["artifacts"] + [entry["script"], "config/visualization.json"])
    files.update(f"lib/visualization/{name}" for name in PIXEL_PRODUCERS
                 if (root / "lib" / "visualization" / name).is_file())
    return {rel: sha(path_in(root, rel)) for rel in sorted(files)}


def stray_script_note(script):
    """画图脚本**必须住 `figures/`** —— 住在 `code/` 下的会连锁触发下游重跑。

    为什么：`code/` 在 ⑤⑥⑦⑧ 的**输入指纹**里（`lib/web/server.py:_input_split` 的 artifacts
    半份），而图的内容不含任何数值结论 ⇒ 脚本一放进去，"改一行配色"就等于"改了 ④ 的代码"，
    整条下游一起失效。`figures/` 刻意不进任何阶段的指纹（同 `figures/` 下的成品图）。
    `figures/manifest.json` 里登记的 `script` 若指向 `code/` 下，那份工作区里"改画图代码"
    与"改求解器"在驱动眼里就没有区别。

    只**提醒**不拦：登记这个动作本身没错，搬个家就好；硬拦会把一次已经在飞的阶段当场打死。
    返回提示串或 None。
    """
    s = str(script or "").replace("\\", "/").strip().lstrip("./").lower()
    if s.startswith("code/") and s.endswith(".py"):
        return (f"画图脚本 `{script}` 住在 `code/` 下 —— 请把它挪到 `figures/` 下"
                f"（例如 `figures/make_figures.py`）并重新登记。`code/` 在 ⑤⑥⑦⑧ 的输入"
                f"指纹里，脚本留在那儿 ⇒ 改一行画图代码会连锁触发下游重跑。")
    return None


def register(root, figure_id, *, artifacts, sources, script, claim, caption, width_mm,
             auto_issues=(), included=True):
    if not re.fullmatch(r"[a-zA-Z0-9_-]+", figure_id):
        raise ValueError("Use a stable semantic figure id (letters/digits/_/-)")
    if not sources or not artifacts or not claim.strip() or not caption.strip() or width_mm <= 0:
        raise ValueError("Sources, assets, claim, caption and positive final width are required")
    entry = dict(artifacts=list(artifacts), sources=list(sources), script=script,
                 claim=claim, caption=caption, width_mm=width_mm, included=included,
                 auto_issues=list(auto_issues), review={"status": "pending"})
    entry["snapshot"] = snapshot(root, entry)
    _mutate(root, lambda data: data["figures"].__setitem__(figure_id, entry))
    note = stray_script_note(script)
    if note:
        print(f"⚠️ {note}", flush=True)
    return entry


def signature(entry):
    payload = {k: v for k, v in entry.items() if k != "review"}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def review(root, figure_id, *, reviewer, note):
    if not reviewer.strip() or len(note.strip()) < 12:
        raise ValueError("Identify reviewer and describe actual visual findings (at least 12 characters)")

    def _apply(data):
        # 校验必须在**锁内、对着刚读进来的那条**做：拿到快照之后、写盘之前，
        #   别人可能已经把这张图重画了（那它的 snapshot 就变新了），拿旧快照去判
        #   会把一条已经过期的复核签名盖上去 —— 等于替一张没看过的图签了字。
        entry = data["figures"][figure_id]
        if entry["auto_issues"] or snapshot(root, entry) != entry["snapshot"]:
            raise ValueError("Fix automatic failures or regenerate stale figure before review")
        entry["review"] = dict(status="passed", reviewer=reviewer, note=note,
                               signature=signature(entry),
                               at=datetime.now(timezone.utc).isoformat())

    _mutate(root, _apply)     # `_apply` 里抛错 → 不落盘（write 在 change 之后）


LAYOUT_CHECKER = "skills/paper-diagram/scripts/check_layout.py"


def _drawio_layout_issues(root, key, entry):
    """`script` 是 `.drawio` 的图，跑一遍 `check_layout.py` 的版式体检。

    为什么接进 `audit()`：`check_layout.py` 若只是个独立脚本，就**只有 ⑦ 的
      agent 想起来才会跑** —— 它不是 `visualization audit` 的一部分，于是
      `figure_evidence_failed` 那条驱动级闸门（`lib/web/server.py:2044`）**看不到版式问题**：
      版式体检报 FAIL 而整条链的图闸门报 PASS 的情况因此能溜过去。接进来之后，版式问题与
      "资产过期/没复核"走同一条路：`figure_evidence_failed` → 交回 ⑨ 重画。

    体检不可用（脚本不在、python 缺、drawio 坏了）时**只提醒不判死** —— 它是辅助检查，
    不该让"环境缺个脚本"变成"图不合格"。
    """
    script = str(entry.get("script") or "")
    if not script.endswith(".drawio"):
        return []
    src = Path(root) / "figures" / Path(script).name
    checker = Path(root) / LAYOUT_CHECKER
    if not src.is_file():
        return [f"{key}: 登记的 drawio 源不在盘上（{src.name}）"]
    if not checker.is_file():
        return []
    try:
        proc = subprocess.run([sys.executable, str(checker), str(src)],
                              capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=60)
    except Exception:                     # noqa: BLE001 —— 辅助检查，绝不许把 audit 弄崩
        return []
    if proc.returncode == 0:
        return []
    bad = [ln.strip() for ln in (proc.stdout or "").splitlines() if ln.strip().startswith("FAIL")]
    if not bad:
        # 非零 rc **但一条 FAIL 都没打** = 体检脚本自己崩了（traceback 进了 stderr），
        #   不是"图有问题"。这种情况**放行** —— 与上面 `except` 同一条道理：
        #   辅助检查不该把"检查器挂了"判成"图不合格"。
        #   真检出问题时会带 FAIL 行，所以"没有 FAIL 行的非零 rc"必是脚本级故障
        #   （读取时撞上写入/杀毒等瞬时失败）。若按原样判死，一次瞬时故障就能卡住整条链，
        #   而且**无法复现、无法排查**。
        #   这里**必须 return []（真放行）**：若改成返回一条 message，`audit()` 会把它
        #   并进 issues → 照样判 FAIL，等于没放行。可见性靠 stderr，不靠加一条 issue。
        print(f"⚠️ {key}: 版式体检脚本未能完成（rc={proc.returncode}）—— 已放行，"
              f"不据此判图不合格。stderr 末 200 字：{(proc.stderr or '')[-200:]}",
              file=sys.stderr)
        return []
    # 这条 return 不能少：漏了它，`bad` 非空（**真检出问题**）时函数走到末尾返回 None，
    #   `audit()` 的 `issues.extend(None)` 会 **TypeError 崩掉整个审计** —— 比误报更糟。
    return [f"{key}: 版式体检不过 —— " + "；".join(bad[:4])]


def audit(root):
    """Read only; fail closed on malformed, stale or unreviewed registered figures."""
    root = Path(root).resolve()
    issues = []
    try:
        data = load(root)
        assets = [p for p in (Path(root) / "figures").rglob("*")
                  if p.suffix.lower() in {".pdf", ".png", ".svg"}]
        if not data["figures"] and assets:
            issues.append("图表存在但没有登记清单")
        registered = set()
        stray_seen = set()
        for key, entry in data["figures"].items():
            registered.update(entry["artifacts"])
            # 已经写在盘上的"脚本住 code/"也要**每次都报一次**（只提醒、不进 issues）：
            # 光靠 register() 那次提醒，对**已经登记过**的旧账就再也不响了 ——
            # 而它正是不改就会一直拖着连锁重跑的那一笔。
            note = stray_script_note(entry.get("script"))
            if note and note not in stray_seen:
                stray_seen.add(note)
                print(f"⚠️ [{key}] {note}", flush=True)
            if not entry["included"]:
                continue
            if snapshot(root, entry) != entry["snapshot"]:
                issues.append(f"{key}: 数据、脚本、配置或图片已改变，需重新生成和复核")
            if entry["auto_issues"]:
                issues.append(f"{key}: 自动检查未通过: {entry['auto_issues']}")
            issues.extend(_drawio_layout_issues(root, key, entry))
            checked = entry["review"]
            if checked.get("status") != "passed" or checked.get("signature") != signature(entry):
                issues.append(f"{key}: 缺少当前版本的视觉复核")
        for p in assets:
            if p.relative_to(Path(root)).as_posix() not in registered:
                issues.append(f"未登记图表: {p.name}（登记用途或明确排除）")
    except (ValueError, KeyError, TypeError, AttributeError, OSError) as exc:
        issues.append(f"图表证据无效: {exc}")
    return issues
