# -*- coding: utf-8 -*-
"""一键启动：把 Web 驱动起起来，然后**自动打开前端面板**（`run.bat` 的干活部分）。

为什么分成 `.bat` + 这个脚本，而不是全写在 `.bat` 里：
  · `.bat` 没法可靠地解析 `config/runtime.local.json`（值里带冒号和反斜杠，`findstr` 会切错）；
  · 这里要做几件需要判断力的事：先看**有没有已经在跑**（别起第二个驱动抢同一个端口）、
    起来之后**等它就绪**、起不来时把**最后的报错捞出来**给你看；
  · Windows 控制台默认 GBK，中文输出要重新配 UTF-8（本仓所有工具统一这么做）。
  · `.bat` 只负责"找得到 Python 就行"，本脚本再把自己**换成项目自己的解释器**跑
    —— 这样哪怕你机器上 `python` 指向别处，跑起来的仍是 `config/runtime.local.json` 里那个。

用法：
    run.bat                  # 双击的入口
    python runtime/launch.py [--port 8901] [--no-browser]
"""
import argparse
import io
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = Path(__file__).resolve().parents[1]
RUNTIME_CFG = ROOT / "config" / "runtime.local.json"
LOG = ROOT / "runtime" / "web_run.log"
SERVER = ROOT / "lib" / "web" / "server.py"
DEFAULT_PORT = 8901
# 起来之后等它答应多久（秒）。驱动 import 期要建 FastAPI、读回执、收容孤儿，
# 冷启动几秒；装依赖不全时它会当场退出，这段等待就是给那种情况留的余地。
STARTUP_WAIT = 60


def say(msg=""):
    print(msg, flush=True)


def configured_python():
    """`config/runtime.local.json` 里的解释器；读不到返回 None（不报错，交给调用方说人话）。"""
    try:
        import json
        return (json.loads(RUNTIME_CFG.read_text(encoding="utf-8-sig")).get("python") or "").strip()
    except (OSError, ValueError, AttributeError):
        return ""


def tool_directories():
    """`config/runtime.local.json` 里的外部工具目录（xelatex / pandoc / drawio 所在）。"""
    try:
        import json
        cfg = json.loads(RUNTIME_CFG.read_text(encoding="utf-8-sig"))
        return [d.strip() for d in (cfg.get("tool_directories") or []) if isinstance(d, str) and d.strip()]
    except (OSError, ValueError, AttributeError):
        return []


def apply_tool_dirs():
    """把那几个工具目录**拼进 PATH**（与 `run.ps1` 做的同一件事），返回实际加进去的。

    为什么这里必须自己做一遍：`tool_directories` 目前**只有启动器**会把它们拼进 PATH
      （Python 侧读它只是为了算指纹，从不动 PATH）。走 `run.ps1` 时它拼了；走 `run.bat`
      这条路时若不拼，⑨ 抄完模板执行 `xelatex -interaction=nonstopmode main.tex` 就是
      「找不到命令」⇒ 整链卡在写作那一步，而报错看起来像"模板坏了"。
      （xelatex 本身也在全局 PATH 里的机器上不会暴露这个问题。）
    """
    added = []
    cur = os.environ.get("PATH", "")
    have = {p.rstrip("\\/").lower() for p in cur.split(os.pathsep) if p.strip()}
    for d in tool_directories():
        if Path(d).is_dir() and d.rstrip("\\/").lower() not in have:
            added.append(d)
    if added:
        os.environ["PATH"] = os.pathsep.join(added + [cur])
    return added


def maybe_reexec_into_project_python(argv):
    """如果当前解释器不是项目配置的那个 ⇒ 换成它再跑一遍（同一个控制台，输出照旧）。"""
    want = configured_python()
    if not want:
        say("⚠ 没读到 config/runtime.local.json 的 python —— 先用当前的解释器跑。"
            "（新机器上要先把 config/runtime.local.json.example 复制成 "
            "config/runtime.local.json 并填好，见 docs/ENVIRONMENT.md）")
        return None
    if not Path(want).exists():
        say(f"⚠ 项目配置的解释器不在：{want}")
        say("  照 docs/ENVIRONMENT.md 重建环境，或修 config/runtime.local.json 里的 python。")
        return None
    try:
        same = Path(want).resolve() == Path(sys.executable).resolve()
    except OSError:
        same = False
    if same:
        return None
    say(f"↻ 换成项目解释器：{want}")
    return subprocess.run([want, str(Path(__file__).resolve()), *argv], cwd=str(ROOT))


def driver_state(port, timeout=2):
    """已经有一个驱动在听这个端口吗？返回 /api/state 的原文，没有则 None。

    显式**绕开代理**：`urlopen` 在 Windows 上会读注册表里的系统代理（Clash 那个），
      别为了探一个 127.0.0.1 反倒去问梯子要连接（见 `lib/web/server.py` 里「出站代理」那段）。
    """
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(f"http://127.0.0.1:{port}/api/state", timeout=timeout) as r:
            return r.read().decode("utf-8", "replace")
    except (urllib.error.URLError, OSError, ValueError):
        return None


def tail(path, n=20):
    try:
        return "\n".join(path.read_text(encoding="utf-8", errors="replace")
                         .splitlines()[-n:]).rstrip()
    except OSError:
        return ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=DEFAULT_PORT)
    ap.add_argument("--no-browser", action="store_true", help="只起服务，不开浏览器")
    a = ap.parse_args()

    if not SERVER.is_file():
        say(f"✗ 找不到 {SERVER} —— 这个文件得跟整个项目一起拷过来。")
        return 2

    # 已经在跑就别起第二个：同端口会抢，而且两条链同时写产物（见 CLAUDE.md）
    state = driver_state(a.port)
    if state is not None:
        say(f"✔ 驱动**已经在跑**（{a.port}），不再起第二个。")
        url = f"http://127.0.0.1:{a.port}/"
        say(f"→ 面板：{url}")
        if not a.no_browser:
            import webbrowser
            webbrowser.open(url)
        return 0

    added = apply_tool_dirs()
    if added:
        say("＋ 外部工具目录已加进 PATH（与 run.ps1 同一件事）：" + "、".join(added))

    say(f"▶ 启动驱动：{SERVER.name} --port {a.port}")
    flags = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)   # 独立的窗口 ⇒ 它的日志看得见、
    #   而且**不会**被重定向进 runtime/web_run.log（那个文件另一个写者是驱动自己的 log()，
    #   两个写者会互相覆盖 —— 详见 docs/WORKFLOW_RELIABILITY.md）
    try:
        subprocess.Popen([sys.executable, str(SERVER), "--port", str(a.port)],
                         cwd=str(ROOT), creationflags=flags)
    except OSError as exc:
        say(f"✗ 起不来：{exc}")
        return 2
    say("  （它开了一个新窗口 —— 那个窗口别关，服务在里面跑；本窗口可以先关）")

    url = f"http://127.0.0.1:{a.port}/"
    say("… 等它就绪")
    deadline = time.time() + STARTUP_WAIT
    ok = False
    while time.time() < deadline:
        if driver_state(a.port, timeout=2) is not None:
            ok = True
            break
        time.sleep(0.5)
        print(".", end="", flush=True)
    say()

    if not ok:
        say(f"✗ {STARTUP_WAIT} 秒内没起来。可能的原因按概率排：")
        say("   ① 依赖没装全 —— 跑 `run.ps1 runtime/doctor.py`（或 python runtime/doctor.py）看缺什么")
        say("   ② 没找到 claude —— 在 .env 里设 WEBDRIVER_CLAUDE=<claude 可执行文件完整路径>")
        say("   ③ 端口被别的程序占了 —— 换一个：run.bat --port 8902")
        say(f"   ④ 驱动窗口里应该有原因；它最后写进日志的是：")
        t = tail(LOG)
        if t:
            for ln in t.splitlines():
                say("      " + ln[:160])
        return 1

    say(f"✔ 驱动就绪：{url}")
    if not a.no_browser:
        try:
            import webbrowser
            webbrowser.open(url)
            say("→ 已经帮你打开面板（没弹出来的话，手动点上面那个地址）")
        except Exception as exc:                      # noqa: BLE001 —— 开不了浏览器不算启动失败
            say(f"（浏览器没能自动打开：{exc}；手动点上面那个地址即可）")
    return 0


if __name__ == "__main__":
    code = maybe_reexec_into_project_python(sys.argv[1:])
    sys.exit(main() if code is None else code.returncode)
