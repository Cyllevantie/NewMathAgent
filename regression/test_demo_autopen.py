# -*- coding: utf-8 -*-
"""整链跑完时自动用系统浏览器打开 ⑯ 的 demo（`lib/web/server.py::_open_demo_page`）。

要守的行为：整链跑完（末尾 ⑯ 结束）时自动打开刚生成的那个 demo 页面。

为什么必须由**驱动**开：链尾那一下没有用户手势，浏览器会把前端的 `window.open` 拦掉；
`webbrowser` 调的是系统默认浏览器，不受这条限制。

用 AST 抠函数来测，**不 import server.py** —— 那会拉起 FastAPI 并执行模块级副作用
（同 `test_proxy.py` / `test_dotenv.py`）。

最要紧的一条是 `test_a_broken_browser_never_breaks_the_run`：这一行跑在
`state["run_completed"] = True` 之后，真抛异常会被 `run_all` 的 `except` 变成**驱动级 halt** ——
交付明明成功了，面板上却挂成"驱动异常"。所以它必须吞掉一切。
"""
import ast
import os
import sys
import types
import unittest
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
_FUNCS = ("_open_demo_page",)
ENV_KEY = "NEWMATHAGENT_NO_OPEN"


def _load(root, opener):
    """把 `_open_demo_page` 抠出来，注进桩 `ROOT` 与桩 `webbrowser`。"""
    tree = ast.parse((PROJECT / "lib/web/server.py").read_text(encoding="utf-8-sig"))
    mod = types.ModuleType("autopen_probe")
    mod.os = os
    mod.ROOT = Path(root)
    mod.webbrowser = types.SimpleNamespace(open=opener)
    got = set()
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in _FUNCS:
            exec(compile(ast.Module([node], []), "<probe>", "exec"), mod.__dict__)
            got.add(node.name)
    if set(_FUNCS) - got:
        raise AssertionError(f"server.py 里少了：{sorted(set(_FUNCS) - got)}")
    return mod


class DemoAutoOpenTests(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.root = Path(tempfile.mkdtemp())
        self.calls = []
        self.saved = os.environ.pop(ENV_KEY, None)
        self.addCleanup(self._restore_env)

    def _restore_env(self):
        os.environ.pop(ENV_KEY, None)
        if self.saved is not None:
            os.environ[ENV_KEY] = self.saved

    def _opener(self, ret=True, boom=False):
        def f(url):
            self.calls.append(url)
            if boom:
                raise RuntimeError("no browser here")
            return ret
        return f

    def _demo(self):
        d = self.root / "demo"
        d.mkdir(parents=True, exist_ok=True)
        (d / "demo.html").write_text("<!doctype html><title>demo</title>", encoding="utf-8")

    # ---- 正路 ----

    def test_the_demo_is_opened_as_a_file_uri(self):
        self._demo()
        m = _load(self.root, self._opener())
        self.assertTrue(m._open_demo_page())
        self.assertEqual(len(self.calls), 1)
        url = self.calls[0]
        self.assertTrue(url.startswith("file:///"), url)
        self.assertTrue(url.endswith("demo/demo.html"), url)
        # demo 是**离线单文件**（双击即用）—— 反斜杠进 URL 在部分浏览器上会打不开
        self.assertNotIn("\\", url)

    def test_no_demo_no_browser(self):
        """⑯ 没产出（或链根本没跑到 ⑯）时不许开浏览器、也不许报错。"""
        m = _load(self.root, self._opener())
        self.assertFalse(m._open_demo_page())
        self.assertEqual(self.calls, [])

    # ---- 对照组 ----

    def test_the_env_switch_silences_it(self):
        """不想被弹窗打扰时 `NEWMATHAGENT_NO_OPEN=1` 整条关掉。"""
        self._demo()
        os.environ[ENV_KEY] = "1"
        m = _load(self.root, self._opener())
        self.assertFalse(m._open_demo_page())
        self.assertEqual(self.calls, [])

    def test_no_browser_available_is_not_an_error(self):
        """`webbrowser.open` 返回 False = 系统没找到可用浏览器。"""
        self._demo()
        m = _load(self.root, self._opener(ret=False))
        self.assertFalse(m._open_demo_page())

    def test_a_broken_browser_never_breaks_the_run(self):
        """抛异常必须被吞掉：这一行跑在 `run_completed = True` 之后，
        真抛出去会被 `run_all` 的 except 变成驱动级 halt —— 交付成功了却显示"驱动异常"。"""
        self._demo()
        m = _load(self.root, self._opener(boom=True))
        self.assertFalse(m._open_demo_page(), "异常必须吞掉并返回 False")


class CallSiteTests(unittest.TestCase):
    """调用点必须在「整链收口」那一支里，且在 `run_completed = True` **之后**。"""

    def test_it_is_called_after_run_completed_is_set(self):
        src = (PROJECT / "lib/web/server.py").read_text(encoding="utf-8-sig")
        i = src.index("if index == len(STAGES)")
        block = src[i:src.index("\n    except Exception", i)]
        self.assertIn("state[\"run_completed\"] = True", block)
        self.assertIn("_open_demo_page()", block, "整链收口没挂上这个调用")
        self.assertLess(block.index("state[\"run_completed\"] = True"),
                        block.index("_open_demo_page()"),
                        "先置位再开浏览器：即使开失败，前端该弹的赠言浮层也照弹")


if __name__ == "__main__":
    unittest.main()
