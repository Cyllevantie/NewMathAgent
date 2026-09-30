# -*- coding: utf-8 -*-
"""出站代理策略：**只把 API 端点摘出代理**（`lib/web/server.py::_apply_proxy_policy` 那一族）。

为什么要钉：这类故障的症状是"梯子开着/关着时好时坏"，而真因藏在
「谁读环境变量、谁读注册表」里 —— `claude`（Node/undici）只读环境变量，所以一直好使；
Python（urllib/requests）读 **Windows 注册表**的系统代理（Clash 的「系统代理」开关
改的就是它），梯子一关就是 connection refused。
`no_proxy` 对两条路都有效 —— 所以策略是「只把 API 主机摘出去，外网搜索照旧走代理」。

这里最要紧的一条是 `test_no_vendor_host_is_hardcoded`：把 `api.deepseek.com` 写死进
`_claude_worker` 的话，端点一换就**静默失效**（新端点默默走梯子，梯子一关又是不明不白的
connection refused）。主机必须从 `ANTHROPIC_BASE_URL` 推，这条用例就是防止它再被写回去。

用 AST 抠函数来测，**不 import server.py** —— 那会拉起 FastAPI 并执行模块级副作用。
"""
import ast
import os
import re
import sys
import types
import unittest
from pathlib import Path
from urllib.parse import urlparse

PROJECT = Path(__file__).resolve().parents[1]

_FUNCS = ("_api_proxy_mode", "_api_direct_hosts", "_api_no_proxy_extra", "_proxy_policy_hosts",
          "_apply_proxy_policy", "_mask_proxy_url", "_detected_proxy", "_proxy_note")
_CONSTS = ("_PUBLIC_SUFFIX_SLD", "_FMA_PROXY_MODES")
# 这些是测试自己会动的环境变量，每条用例前后都清干净
_TOUCHED = ("ANTHROPIC_BASE_URL", "FMA_API_PROXY", "FMA_NO_PROXY_EXTRA",
            "NO_PROXY", "no_proxy", "HTTPS_PROXY", "https_proxy")


def _load_proxy_module():
    tree = ast.parse((PROJECT / "lib/web/server.py").read_text(encoding="utf-8-sig"))
    mod = types.ModuleType("proxy_probe")
    mod.__file__ = str(PROJECT / "lib/web/server.py")
    mod.os, mod.re, mod.sys, mod.Path, mod.urlparse = os, re, sys, Path, urlparse
    got = set()
    for node in tree.body:
        if isinstance(node, ast.Assign):
            names = [t.id for t in node.targets if isinstance(t, ast.Name)]
            if names and names[0] in _CONSTS:
                exec(compile(ast.Module([node], []), "<probe>", "exec"), mod.__dict__)
                got.add(names[0])
        if isinstance(node, ast.FunctionDef) and node.name in _FUNCS:
            exec(compile(ast.Module([node], []), "<probe>", "exec"), mod.__dict__)
            got.add(node.name)
    missing = (set(_FUNCS) | set(_CONSTS)) - got
    if missing:
        raise AssertionError(f"server.py 里少了：{sorted(missing)}")
    return mod


class ProxyPolicyTests(unittest.TestCase):
    def setUp(self):
        self.m = _load_proxy_module()
        self._saved = {k: os.environ.get(k) for k in _TOUCHED}
        for k in _TOUCHED:
            os.environ.pop(k, None)
        self.addCleanup(self._restore)

    def _restore(self):
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    # ---------- 主机从配置推导（不是写死的厂商域名） ----------

    def test_no_vendor_host_is_hardcoded(self):
        """回归钉：厂商域名不许以**代码字面量**的形式出现在 server.py 里。

        把 `api.deepseek.com` 写死在 `_claude_worker` 的话，换端点就**静默失效** ——
        新端点默默走梯子，梯子一关又是不明不白的 connection refused。注释里提它是允许的，
        所以按 AST 只看**字符串常量**，不扫注释。
        """
        tree = ast.parse((PROJECT / "lib/web/server.py").read_text(encoding="utf-8-sig"))
        bad = sorted({n.value for n in ast.walk(tree)
                      if isinstance(n, ast.Constant) and isinstance(n.value, str)
                      and "deepseek.com" in n.value.lower()})
        self.assertEqual(bad, [], f"又有把厂商域名写死的字面量了：{bad}")

    def test_hosts_follow_the_configured_endpoint(self):
        os.environ["ANTHROPIC_BASE_URL"] = "https://api.deepseek.com/anthropic"
        self.assertEqual(self.m._api_direct_hosts(), ["api.deepseek.com", ".deepseek.com"])
        # 换成别家 —— 名单必须跟着换（主机写死的话这里会原地不动）
        os.environ["ANTHROPIC_BASE_URL"] = "https://relay.some-other-vendor.io/v1"
        self.assertEqual(self.m._api_direct_hosts(), ["relay.some-other-vendor.io", ".some-other-vendor.io"])

    def test_public_suffix_parent_is_not_stripped(self):
        """`foo.com.cn` 的父域是 `com.cn`（公共后缀）—— 摘它会连累整个顶级域，不摘。"""
        os.environ["ANTHROPIC_BASE_URL"] = "https://api.example.com.cn/anthropic"
        self.assertEqual(self.m._api_direct_hosts(), ["api.example.com.cn"])
        os.environ["ANTHROPIC_BASE_URL"] = "https://api.example.co.uk/x"
        self.assertEqual(self.m._api_direct_hosts(), ["api.example.co.uk"])

    def test_unset_or_unparsable_endpoint_yields_nothing(self):
        """留空 = 不摘任何主机（用 CLI 默认地址的人有自己的代理策略，不该由本工具猜）。"""
        for url in ("", "   ", "这不是一个地址", "api.deepseek.com", "https://"):
            os.environ["ANTHROPIC_BASE_URL"] = url
            self.assertEqual(self.m._api_direct_hosts(), [], f"{url!r} 不该推出主机")

    def test_extra_hosts_from_env(self):
        os.environ["FMA_NO_PROXY_EXTRA"] = "mirrors.aliyun.com, pypi.tuna.tsinghua.edu.cn;x.com"
        self.assertEqual(self.m._api_no_proxy_extra(),
                         ["mirrors.aliyun.com", "pypi.tuna.tsinghua.edu.cn", "x.com"])

    # ---------- 落到 NO_PROXY 上 ----------

    def test_apply_appends_without_clobbering_and_is_idempotent(self):
        os.environ["ANTHROPIC_BASE_URL"] = "https://api.deepseek.com/anthropic"
        env = {"NO_PROXY": "localhost,127.0.0.1"}
        added = self.m._apply_proxy_policy(env)
        self.assertEqual(added, ["api.deepseek.com", ".deepseek.com"])
        self.assertTrue(env["NO_PROXY"].startswith("localhost,127.0.0.1,"), "既有条目不能被顶掉")
        self.assertIn("api.deepseek.com", env["no_proxy"], "小写那个也要写：urllib 两个都认")
        self.assertEqual(self.m._apply_proxy_policy(env), [], "第二次调用不该再堆一遍")
        self.assertEqual(env["NO_PROXY"].count("api.deepseek.com"), 1)

    def test_apply_writes_both_env_copies_when_given_none(self):
        """`env=None` 时改的是 `os.environ` 本身 —— 整棵进程树（含驱动自己跑的 Python）才一致。"""
        os.environ["ANTHROPIC_BASE_URL"] = "https://api.deepseek.com/anthropic"
        self.m._apply_proxy_policy()
        self.assertIn("api.deepseek.com", os.environ.get("NO_PROXY", ""))
        self.assertIn("api.deepseek.com", os.environ.get("no_proxy", ""))

    def test_system_mode_changes_nothing(self):
        """`system` = 和你在终端里直接敲 `claude` 完全一致 —— 一个字节都不改。"""
        os.environ["ANTHROPIC_BASE_URL"] = "https://api.deepseek.com/anthropic"
        os.environ["FMA_API_PROXY"] = "system"
        env = {}
        self.assertEqual(self.m._apply_proxy_policy(env), [])
        self.assertEqual(env, {})

    def test_off_mode_makes_everything_direct(self):
        """`off` = 没梯子（或不想让任何东西走代理）：`NO_PROXY=*` 一刀切。"""
        os.environ["FMA_API_PROXY"] = "off"
        env = {}
        self.assertEqual(self.m._apply_proxy_policy(env), ["*"])
        self.assertEqual(env["NO_PROXY"], "*")

    def test_auto_with_no_endpoint_is_a_no_op(self):
        """自动模式下没有端点 ⇒ **什么都不写**（不是写个空的 NO_PROXY 把系统代理搅乱）。"""
        env = {}
        self.assertEqual(self.m._apply_proxy_policy(env), [])
        self.assertEqual(env, {})

    def test_unknown_mode_falls_back_to_auto(self):
        os.environ["FMA_API_PROXY"] = "什么鬼"
        self.assertEqual(self.m._api_proxy_mode(), "auto")

    # ---------- 日志行 ----------

    def test_note_says_what_it_did(self):
        os.environ["ANTHROPIC_BASE_URL"] = "https://api.deepseek.com/anthropic"
        self.m._apply_proxy_policy()
        note = self.m._proxy_note()
        self.assertIn("api.deepseek.com", note)
        self.assertIn("ANTHROPIC_BASE_URL", note, "要说清名单是从哪来的")
        self.assertIn("网络", note)

    def test_note_warns_when_the_endpoint_is_missing(self):
        note = self.m._proxy_note()
        self.assertIn("没设", note)

    def test_proxy_credentials_are_masked_in_the_log(self):
        """代理地址常带 `user:pass@` —— 日志会被翻，凭据不能原样进去。"""
        os.environ["ANTHROPIC_BASE_URL"] = "https://api.deepseek.com/anthropic"
        os.environ["HTTPS_PROXY"] = "http://alice:s3cr3t@corp-proxy:8080"
        note = self.m._proxy_note()
        self.assertNotIn("s3cr3t", note)
        self.assertIn("corp-proxy:8080", note, "主机要留着，不然没法诊断")


if __name__ == "__main__":
    unittest.main()
