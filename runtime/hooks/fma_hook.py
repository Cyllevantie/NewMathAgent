# -*- coding: utf-8 -*-
"""NewMathAgent 的 Claude Code hook：工具日志 + 写入后自检 + 面板期路径护栏。

由 `.claude/settings.json` 在 PreToolUse / PostToolUse / SubagentStop / Stop 时调用。
只依赖标准库；任何异常都吞掉并 exit 0（PostToolUse 不能把一次成功写入变成失败）。
PostToolUse 的自检失败用 `hookSpecificOutput.additionalContext` 回注给 agent，
不阻断写入；普通 stdout 只进 transcript，agent 看不到。
PreToolUse 只在「面板锁存在且写受保护目录」时 exit 2，其余一律放行。
"""
import json
import os
import re
import shlex
import subprocess
import sys
import time
from pathlib import Path

# Claude Code 通过 stdio 传 UTF-8 JSON；Windows 的 Python 默认 GBK，
# 不显式改会把中文路径/命令读成代理字符，日志写入也会失败。
for _stream in (sys.stdin, sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[2]
LOG = ROOT / "runtime" / "tool_calls.jsonl"
LOCK = ROOT / ".fma_panel_lock"
PROTECTED = ("code", "results", "figures", "paper", "paper_appendix",
             "reports", "runtime", "demo")


def _event():
    try:
        raw = sys.stdin.read()
        return json.loads(raw) if raw.strip() else {}
    except Exception:
        return {}


def _log(ev, extra=None):
    try:
        ti = ev.get("tool_input") or {}
        rec = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "stage": os.environ.get("FMA_STAGE", ""),
            "event": ev.get("hook_event_name", ""),
            "tool": ev.get("tool_name", ""),
            "session": ev.get("session_id", ""),
            "cwd": ev.get("cwd", ""),
            "path": ti.get("file_path") or ti.get("path") or "",
            "command": (ti.get("command") or "")[:500],
        }
        if extra:
            rec.update(extra)
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with LOG.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception:
        pass


def _path_of(ev):
    ti = ev.get("tool_input") or {}
    raw = ti.get("file_path") or ti.get("path") or ""
    if not raw:
        return None
    try:
        p = Path(raw)
        if not p.is_absolute():
            p = Path(ev.get("cwd") or ROOT) / p
        return p.resolve()
    except Exception:
        return None


def _under_protected(p):
    try:
        rel = p.relative_to(ROOT.resolve())
    except Exception:
        return False
    return bool(rel.parts) and rel.parts[0] in PROTECTED


# 面板锁存在时只拦 Write/Edit/MultiEdit 不够：Bash/PowerShell 的 tool_input
# 只有 command，_path_of 返回 None，cp/mv/rm/tee/重定向/python -c 都能绕过锁
# 直接写正式目录。下面做保守解析：同时命中「受保护目录路径」和「写类动作」
# 才拦；grep/cat/ls 这类纯读命令不拦。
_WRITE_VERBS = {
    "cp", "copy", "mv", "move", "rm", "del", "erase", "rmdir", "tee",
    "robocopy", "xcopy", "truncate", "dd", "mkdir",
    "set-content", "add-content", "out-file", "new-item", "remove-item",
    "copy-item", "move-item", "rename-item", "clear-content", "set-item",
}
_SHELLS = {"bash", "sh", "zsh", "cmd", "powershell", "pwsh"}
_PYTHONS = {"python", "python3", "py"}
_WRAPPERS = {"sudo", "env", "command", "time", "nohup", "exec"}
# python -c 里的写文件特征；只读 open(...)/read_text() 不算写动作。
_PY_WRITE_RE = re.compile(
    r"(?:open\s*\([^)]*['\"][wax]|\.write(?:text|bytes)?\s*\(|"
    r"shutil\.(?:copy|move|rmtree|copytree)|"
    r"os\.(?:remove|unlink|rename|replace|makedirs|mkdir)|"
    r"\.(?:mkdir|unlink|rmdir|touch)\(|to_csv|savefig|np\.save|"
    r"json\.dump|pickle\.dump)", re.I)
_REDIRECT_RE = re.compile(r"(?<![=<>-])>>?(?![&=])")
_QUOTED_RE = re.compile(r"'[^']*'|\"[^\"]*\"")


def _segments(cmd):
    # 按未加引号的 | ; & 换行切成命令段，避免 `cat x|tee y` 把 tee 黏进参数。
    out, buf, quote = [], [], ""
    for ch in cmd:
        if quote:
            buf.append(ch)
            if ch == quote:
                quote = ""
        elif ch in "\"'":
            quote = ch
            buf.append(ch)
        elif ch in "|;&\n":
            out.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
    out.append("".join(buf))
    return [s for s in out if s.strip()]


def _tokens(cmd):
    # posix=False 保留反斜杠（Windows 路径）；引号包住的 token 保留引号。
    try:
        raw = shlex.split(cmd, posix=False)
    except Exception:
        raw = cmd.split()
    out = []
    for t in raw:
        quoted = len(t) >= 2 and t[0] == t[-1] and t[0] in "\"'"
        out.append((t[1:-1] if quoted else t, quoted))
    return out


def _path_candidates(cmd, depth=0):
    # 命令里的路径候选：普通 token、--out=path、2>path，以及引号包住的内层
    # 代码/内层命令（python -c "open('code/x','w')"、bash -c "rm code/x"）。
    cands = []
    for seg in _segments(cmd):
        for text, _quoted in _tokens(seg):
            t = text.strip().lstrip("&@")
            t = re.sub(r"^[0-9&]*(?:>>?|<)+", "", t)  # 2>code/x、>>paper/x
            for part in re.split(r"[<>]+", t):
                part = part.strip()
                if "=" in part:
                    part = part.split("=", 1)[1]
                elif part.startswith("-") and ":" in part:
                    part = part.split(":", 1)[1]  # PowerShell -Path:code/x
                part = part.strip().strip("\"'`(){}[],;")
                if part:
                    cands.append(part)
    if depth < 2:
        # 单双引号分开找，避免相邻的两种引号互相吞掉。
        for inner in re.findall(r"'([^']+)'", cmd) + re.findall(r'"([^"]+)"', cmd):
            if inner and inner != cmd:
                cands.extend(_path_candidates(inner, depth + 1))
    return cands


def _mentions_protected(cmd, cwd):
    base = Path(cwd) if cwd else ROOT
    for cand in _path_candidates(cmd):
        if not cand or cand.startswith("-"):
            continue
        try:
            p = Path(cand)
            if not p.is_absolute():
                p = base / p
            if _under_protected(p.resolve()):
                return True
        except Exception:
            continue
    return False


def _has_write_action(cmd, depth=0):
    if depth > 2:
        return False
    for seg in _segments(cmd):
        tokens = _tokens(seg)
        if not tokens:
            continue
        # 只看每个命令段的首个命令词：`grep cp code` 里的 cp 是参数，不算写动作。
        idx = 0
        while idx < len(tokens) and (
                tokens[idx][0].lower() in _WRAPPERS or
                re.match(r"^[A-Za-z_]\w*=", tokens[idx][0])):
            idx += 1
        if idx >= len(tokens):
            continue
        name = os.path.basename(tokens[idx][0].strip().lstrip("&")).lower()
        if name.endswith(".exe"):
            name = name[:-4]
        rest = [t for t, _q in tokens[idx + 1:]]
        low = [t.lower() for t in rest]
        if name in _SHELLS:
            # 内层命令：bash -c "..." / cmd /c ... / powershell -Command "..."
            for flag in ("-c", "/c", "-command"):
                if flag in low:
                    inner = " ".join(rest[low.index(flag) + 1:])
                    if inner and _has_write_action(inner, depth + 1):
                        return True
        if name in _PYTHONS and "-c" in low:
            code = " ".join(rest[low.index("-c") + 1:])
            if _PY_WRITE_RE.search(code):
                return True
        if name in _WRITE_VERBS:
            return True
        # > / >> 重定向（排除 2>&1、>=、=> 这类非文件写入）
        if _REDIRECT_RE.search(_QUOTED_RE.sub(" ", seg)):
            return True
    return False


def _command_writes_protected(cmd, cwd):
    return bool(cmd) and _has_write_action(cmd) and _mentions_protected(cmd, cwd)


_WARNINGS = []


def _warn(msg):
    # PostToolUse 的普通 stdout 只进 transcript，不进模型上下文；
    # 用 hookSpecificOutput.additionalContext 才能让 agent 看到自检失败。
    _WARNINGS.append("[fma-hook] " + msg)


def _flush_warnings():
    if not _WARNINGS:
        return
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": "\n".join(_WARNINGS),
        }
    }, ensure_ascii=False))


def _run_check(cmd, label):
    try:
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"  # 子进程中文错误也按 UTF-8 回传
        p = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=25,
                           env=env)
        if p.returncode != 0:
            tail = ((p.stdout or "") + (p.stderr or "")).strip().splitlines()
            _warn(label + " 失败：" + (" | ".join(tail[-3:])[:600]))
    except Exception as exc:
        _warn(label + " 未执行：" + str(exc)[:200])


def main():
    try:
        return _main()
    finally:
        _flush_warnings()


def _main():
    ev = _event()
    event = ev.get("hook_event_name", "")
    tool = ev.get("tool_name", "")
    _log(ev)

    if event == "PreToolUse":
        # 面板锁存在时，子 agent / 主 agent 都只许写 _tmp/ 或 tmp/。
        # 超过 2h 的锁视为崩溃残留，自动失效，避免永久卡住后续阶段。
        if LOCK.exists():
            try:
                if time.time() - LOCK.stat().st_mtime > 7200:
                    LOCK.unlink(missing_ok=True)
            except Exception:
                pass
            if LOCK.exists():
                blocked = False
                if tool in ("Write", "Edit", "MultiEdit"):
                    p = _path_of(ev)
                    blocked = p is not None and _under_protected(p)
                elif tool in ("Bash", "PowerShell"):
                    # Bash/PowerShell 没有 file_path，只能解析 command；
                    # 兜住 cp/mv/rm/重定向/python -c 绕过锁写正式目录。
                    cmd = str((ev.get("tool_input") or {}).get("command") or "")
                    blocked = _command_writes_protected(cmd, ev.get("cwd"))
                if blocked:
                    print("面板进行中（.fma_panel_lock 存在）：只许写 _tmp/ 或 tmp/；"
                          "收齐候选后由主 agent 删锁再写正式产物。", file=sys.stderr)
                    return 2
        return 0

    if event == "PostToolUse" and tool in ("Write", "Edit", "MultiEdit"):
        p = _path_of(ev)
        if p is None or not p.exists():
            return 0
        suffix = p.suffix.lower()
        if suffix == ".py":
            _run_check([sys.executable, "-m", "py_compile", str(p)], "py_compile " + p.name)
        elif suffix == ".drawio":
            checker = ROOT / "skills" / "paper-diagram" / "scripts" / "check_layout.py"
            if checker.exists():
                _run_check([sys.executable, str(checker), str(p)], "check_layout " + p.name)
        return 0

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except Exception:
        sys.exit(0)
