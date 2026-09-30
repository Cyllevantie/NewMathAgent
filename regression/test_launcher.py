# -*- coding: utf-8 -*-
"""一键启动器：`run.bat`（薄壳）+ `runtime/launch.py`（干活的那个）。

为什么要测：这是**双击**入口 —— 出错时没人看得到堆栈，只会看到一个闪一下就没的窗口。
所以两条硬性质：① 已经在跑就**不许再起第二个**（同端口会抢，两条链还会同时写产物与回执）；
② 起不来时要把**能照着做的原因**打出来（缺依赖 / 没找到 claude / 端口被占），别只留一句"失败"。

`test_it_starts_waits_and_reports` 是**真跑一遍**：把 launch.py 复制进一个临时目录，
旁边放一个假 `lib/web/server.py`（只答 `/api/state`），让它真起进程、真轮询、真报 URL。
沙箱化之后既不碰正在跑的那个驱动，也不给 `runtime/web_run.log` 添第二个写者。
"""
import http.server
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))
sys.path.insert(0, str(PROJECT / "runtime"))
import launch  # noqa: E402


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


STUB_SERVER = '''\
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
class H(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path != "/api/state":
            self.send_error(404); return
        body = json.dumps({"running": False, "cur": None}).encode()
        self.send_response(200); self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body))); self.end_headers()
        self.wfile.write(body)
    def log_message(self, *a):
        pass
HTTPServer(("127.0.0.1", PORT), H).serve_forever()
'''


class LauncherTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        (self.tmp / "lib" / "web").mkdir(parents=True)
        (self.tmp / "runtime").mkdir()
        (self.tmp / "config").mkdir()
        # 把模块里的路径指到这个沙箱（都是模块级常量，调用时才读）
        for name, rel in (("ROOT", ""), ("SERVER", "lib/web/server.py"),
                          ("RUNTIME_CFG", "config/runtime.local.json"),
                          ("LOG", "runtime/web_run.log")):
            old = getattr(launch, name)
            self.addCleanup(setattr, launch, name, old)
            setattr(launch, name, self.tmp / rel if rel else self.tmp)
        old_wait = launch.STARTUP_WAIT
        self.addCleanup(setattr, launch, "STARTUP_WAIT", old_wait)

    def _stub_server(self, port, wait=False):
        (self.tmp / "lib/web/server.py").write_text(
            STUB_SERVER.replace("PORT", str(port)), encoding="utf-8")

    def _run_main(self, argv, wait=None):
        if wait is not None:
            launch.STARTUP_WAIT = wait
        with mock.patch.object(sys, "argv", ["launch.py", *argv]):
            return launch.main()

    # ---- 哨兵：入口文件本身 ----

    def test_the_bat_is_ascii_only_and_points_at_the_launcher(self):
        """`run.bat` 必须**纯 ASCII**（cmd 按 OEM 代码页读它，中文会让它花屏甚至解析错），
        并且它要调的是 `runtime\\launch.py`（逻辑不许在 .bat 里重写一份）。"""
        p = PROJECT / "run.bat"
        self.assertTrue(p.is_file(), "缺 run.bat —— 用户要的是双击就能跑")
        raw = p.read_bytes()
        self.assertTrue(all(b < 128 for b in raw), "run.bat 里有非 ASCII 字节，换个代码页就花")
        t = raw.decode("ascii")
        self.assertIn(r"runtime\launch.py", t)
        self.assertIn("chcp 65001", t, "没有 chcp 65001 ⇒ Python 打的 UTF-8 中文会花屏")
        self.assertNotIn("web_run.log", t, "别把驱动输出重定向进日志文件 —— 那文件已有写者")

    # ---- 探活 ----

    def test_driver_state_tells_up_from_down(self):
        port = free_port()
        srv = http.server.HTTPServer(("127.0.0.1", port),
                                     type("H", (http.server.BaseHTTPRequestHandler,), {
                                         "do_GET": lambda self: (self.send_response(200),
                                                                self.end_headers(),
                                                                self.wfile.write(b'{"running": false}')),
                                         "log_message": lambda *a: None}))
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        self.addCleanup(srv.shutdown)
        self.assertIsNotNone(launch.driver_state(port), "活着的服务该被认出")
        self.assertIsNone(launch.driver_state(free_port()), "没人听的端口该是 None")

    def test_an_already_running_driver_is_not_started_twice(self):
        """已经在跑就只开浏览器。同端口起第二个 = 抢端口 + 两条链同时写产物/回执。"""
        port = free_port()
        self._stub_server(port)          # `main()` 先检查 lib/web/server.py 在不在，再探活
        with mock.patch.object(launch, "driver_state", return_value='{"running": false}'), \
                mock.patch.object(subprocess, "Popen",
                                  side_effect=AssertionError("不许起第二个驱动")), \
                mock.patch("webbrowser.open") as opened:
            self.assertEqual(self._run_main(["--port", str(port)]), 0)
        self.assertTrue(opened.called, "已经在跑时也该把面板带出来")

    # ---- 真起一遍（沙箱里） ----

    def test_it_starts_waits_and_reports(self):
        port = free_port()
        self._stub_server(port)
        self.assertEqual(self._run_main(["--port", str(port), "--no-browser"], wait=15), 0)
        self.addCleanup(self._kill_stub, port)
        self.assertIsNotNone(launch.driver_state(port), "启动器说就绪了，可服务没在听")

    def test_the_browser_opens_unless_told_not_to(self):
        port = free_port()
        self._stub_server(port)
        with mock.patch("webbrowser.open") as opened:
            self.assertEqual(self._run_main(["--port", str(port)], wait=15), 0)
        self.addCleanup(self._kill_stub, port)
        self.assertTrue(opened.called, "一键启动的「顺带打开前端」没发生")
        self.assertIn(str(port), opened.call_args[0][0])

    def test_tool_directories_enter_PATH_like_run_ps1_does(self):
        """`tool_directories` **只有启动器**会拼进 PATH（Python 侧读它只为算指纹）。

        走 `run.ps1` 时它拼了；走 `run.bat` 这条新路若不拼，⑨ 抄完模板执行 `xelatex …`
        就是「找不到命令」⇒ 整链卡在写作那一步，而症状看起来像模板坏了。
        这条钉住：launch.py 必须自己做同一件事。
        """
        import json
        tool = self.tmp / "假工具目录"
        tool.mkdir()
        (self.tmp / "config/runtime.local.json").write_text(
            json.dumps({"python": sys.executable, "tool_directories": [str(tool), str(self.tmp / "不存在")]}),
            encoding="utf-8")
        old = os.environ.get("PATH", "")
        self.addCleanup(lambda: os.environ.__setitem__("PATH", old))
        added = launch.apply_tool_dirs()
        self.assertEqual(added, [str(tool)], "存在的目录该加；不存在的别塞进去")
        self.assertIn(str(tool), os.environ["PATH"].split(os.pathsep))
        self.assertEqual(launch.apply_tool_dirs(), [], "第二次调用不该重复加")

    def test_a_dead_start_fails_with_something_actionable(self):
        """起不来时**必须**给出可照做的原因 —— 别只留一句"失败"。"""
        port = free_port()
        (self.tmp / "lib/web/server.py").write_text("import sys; sys.exit(1)\n", encoding="utf-8")
        buf = []
        with mock.patch("sys.stdout", type("S", (), {
                "write": lambda self, s: buf.append(s), "flush": lambda self: None})()):
            code = self._run_main(["--port", str(port), "--no-browser"], wait=1)
        out = "".join(buf)
        self.assertEqual(code, 1)
        for hint in ("doctor", "WEBDRIVER_CLAUDE", "port"):
            self.assertIn(hint, out, f"没提示 {hint}：{out[-400:]}")

    def _kill_stub(self, port):
        """沙箱里那个假服务的收尾：它是本测试起的，必须收掉。"""
        try:
            out = subprocess.run(["netstat", "-ano"], capture_output=True, text=True,
                                 encoding="utf-8", errors="replace", timeout=20).stdout
            for line in out.splitlines():
                if f":{port}" in line and "LISTENING" in line:
                    subprocess.run(["taskkill", "/F", "/PID", line.split()[-1]],
                                   capture_output=True, timeout=15)
        except Exception:                                   # noqa: BLE001
            pass


if __name__ == "__main__":
    unittest.main()
