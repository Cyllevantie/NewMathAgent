# -*- coding: utf-8 -*-
"""绑定本机：更换别的机器/目录也正常运行。
这一族共三类，问题都是更换机器暴露：

1. **把指针当事实**：`config/runtime.local.json` 里就是几条本机绝对路径（python 在哪、
   texlive/pandoc 在哪）。若把它**整份按字节**哈希进 ④ 及下游的输入指纹，
   换个盘符/重装到别处就会字节变了而事实没变 ⇒ 整链从 ④ 重跑（小时级）。
   这里按**身份**（解释器版本 + 工具的 (名字,版本)）计入，见 `_env_identity`。
2. **绑定本机路径**：`lib/web/healthcheck.py` 的 ROOT、`lib/web/server.py::_find_claude()` 的
   VS Code 扩展目录。
3. **运行参数只有源码一处出处**：看门狗/墙钟那些常量，换台快慢不同的机器只能改源码。
   这里可被 `.env` 覆盖（`FMA_*`），**默认值保持原值不变**。

用 `load_server` 把 ROOT 指到临时目录（AST 改写），不 import 真 server.py。
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))
sys.path.insert(0, str(PROJECT / "regression"))
from test_workflow import load_server  # noqa: E402


class ToolIdentityTests(unittest.TestCase):
    """`_tool_identity`：把「装在哪」折成「是什么」。"""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for rel in ("CLAUDE.md", "AGENTS.md"):
            shutil.copy2(PROJECT / rel, self.root / rel)
        for rel in ("skills", "docs"):
            shutil.copytree(PROJECT / rel, self.root / rel)
        self.s = load_server(self.root)

    def _with_tools(self, dirs, python="E:/x/python.exe"):
        # 用 json.dumps 写：`%r` 出来的是**单引号**，那不是 JSON，`_tool_dirs()` 读不动
        #   （写成 `%r` 的话两个用例都会退化成"空身份"，升级那条对照组当场变红）。
        import json
        (self.root / "config").mkdir(parents=True, exist_ok=True)
        (self.root / "config/runtime.local.json").write_text(
            json.dumps({"python": python, "tool_directories": list(dirs)}), encoding="utf-8")

    def test_tool_identity_ignores_the_drive_and_parents(self):
        for path, want in ((r"D:\texlive\2026\bin\windows", ("texlive", "2026")),
                           (r"E:\pandoc\pandoc-3.6.4", ("pandoc", "3.6.4")),
                           (r"E:\draw.io-31.3.2", ("draw.io", "31.3.2"))):
            with self.subTest(path=path):
                self.assertEqual(self.s._tool_identity(path), want)

    def test_tool_identity_falls_back_when_there_is_no_version(self):
        """手工放的一堆二进制没有版本号 ⇒ 只剩名字可认（**明知**的取舍，写在这里备查）。"""
        self.assertEqual(self.s._tool_identity(r"C:\tools\mytool"), ("mytool", ""))

    def test_moving_a_tool_does_not_change_the_identity(self):
        """重装到别的盘、同一个版本 ⇒ 身份不变 ⇒ **不该**判"事实变了"。"""
        self._with_tools([r"D:\texlive\2026\bin\windows", r"E:\pandoc\pandoc-3.6.4"])
        before = self.s._env_identity()
        self._with_tools([r"C:\tools\texlive\2026\bin\windows", r"D:\pandoc\pandoc-3.6.4"])
        self.assertEqual(self.s._env_identity(), before,
                         "只是换了个安装目录，不该让 ④ 及下游整链重跑")

    def test_upgrading_a_tool_does_change_the_identity(self):
        """对照组：真升级（版本变了）必须变 —— 否则上面那条可能只是恒真。"""
        self._with_tools([r"D:\texlive\2026\bin\windows"])
        before = self.s._env_identity()
        self._with_tools([r"D:\texlive\2025\bin\windows"])
        self.assertNotEqual(self.s._env_identity(), before, "工具升级了，指纹得跟着变")
        self.assertIn("texlive@2025", self.s._env_identity())

    def test_the_interpreter_is_in_the_identity(self):
        self._with_tools([])
        ident = self.s._env_identity()
        self.assertTrue(ident.startswith("python="), ident)
        self.assertIn(f"{sys.version_info[0]}.{sys.version_info[1]}", ident)

    def test_the_raw_config_file_is_no_longer_fingerprinted(self):
        """`config/runtime.local.json` 不许进**任何**阶段的输入清单。

        它装的是本机绝对路径（指针），不是事实；按字节哈希就是把"换台机器"当成"内容变了"。
        """
        self._with_tools([r"D:\texlive\2026\bin\windows"])
        offenders = [st["id"] for st in self.s.STAGES
                     if "config/runtime.local.json" in self.s._input_paths(st)]
        self.assertEqual(offenders, [], f"这些阶段的输入里又有那个指针文件了：{offenders}")
        # 依赖那两份仍要在（它们是仓库文件，内容变了就是真的变了）
        code = next(st for st in self.s.STAGES if st["id"] == "code")
        self.assertIn("requirements.lock.txt", self.s._input_paths(code))


class RuntimeKnobTests(unittest.TestCase):
    """`FMA_*` 运行参数：默认值不变，填错不炸。"""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for rel in ("CLAUDE.md", "AGENTS.md"):
            shutil.copy2(PROJECT / rel, self.root / rel)
        for rel in ("skills", "docs"):
            shutil.copytree(PROJECT / rel, self.root / rel)
        self.s = load_server(self.root)
        self._saved = {k: os.environ.get(k) for k in
                       ("FMA_STALL_SILENT", "FMA_OVERTIME_KILL", "FMA_NOPE")}
        for k in self._saved:
            os.environ.pop(k, None)
        self.addCleanup(self._restore)

    def _restore(self):
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def test_defaults_are_unchanged(self):
        """不填时各项取默认值 —— 这条钉住"解耦没有顺手改口径"。"""
        self.assertEqual(self.s.STALL_SILENT, 300)
        self.assertEqual(self.s.STALL_CONN, 1200)
        self.assertEqual(self.s.STALL_SAMPLE, 5)
        self.assertEqual(self.s.RETRY_CAP_DEFAULT, 1800)
        self.assertEqual(self.s.RETRY_CAP_EXTRA_MAX, 3600)
        self.assertEqual(self.s.RETRY_CAP_EXTRA_MIN, 600)
        self.assertEqual(self.s.RETRY_CAP_MIN, 600)
        self.assertEqual(self.s.CALL_HARD_CAP, 10800)
        self.assertEqual(self.s.CALL_PROTOCOL_CAP, 900)
        self.assertEqual(self.s.WAIT_AFTER_KILL, 60)
        self.assertIs(self.s.OVERTIME_KILL, False)
        self.assertIs(self.s.AUTO_RETRY_ENV_ERROR, True)

    def test_env_overrides_are_read(self):
        os.environ["FMA_STALL_SILENT"] = "600"
        self.assertEqual(self.s._num("FMA_STALL_SILENT", 300), 600)
        os.environ["FMA_STALL_SILENT"] = "600.0"          # 容忍小数写法
        self.assertEqual(self.s._num("FMA_STALL_SILENT", 300), 600)
        os.environ["FMA_OVERTIME_KILL"] = "yes"
        self.assertIs(self.s._flag("FMA_OVERTIME_KILL", False), True)
        os.environ["FMA_OVERTIME_KILL"] = "0"
        self.assertIs(self.s._flag("FMA_OVERTIME_KILL", False), False)

    def test_a_bad_value_falls_back_and_is_reported(self):
        """填错**不**让驱动起不来 —— 用默认值，并把这一行记下来（启动日志里会报）。"""
        n = len(self.s._RUNTIME_ENV_BAD)
        os.environ["FMA_STALL_SILENT"] = "半小时"
        self.assertEqual(self.s._num("FMA_STALL_SILENT", 300), 300)
        os.environ["FMA_NOPE"] = "也许"
        self.assertIs(self.s._flag("FMA_NOPE", True), True)
        self.assertEqual(len(self.s._RUNTIME_ENV_BAD), n + 2, self.s._RUNTIME_ENV_BAD)


class NoMachinePathTests(unittest.TestCase):
    """本机路径不许写死在会跑到的代码里。"""

    def test_healthcheck_root_follows_the_file(self):
        """`lib/web/healthcheck.py` 的 ROOT 必须从 `__file__` 推 —— 写死的话，换台机器它会去
        检查**另一棵不存在的树**，然后报"缺 skill"，看起来像仓库坏了。"""
        src = (PROJECT / "lib/web/healthcheck.py").read_text(encoding="utf-8")
        head = "\n".join(l for l in src.splitlines() if l.strip().startswith("ROOT"))
        self.assertIn("__file__", head, f"ROOT 又不是从文件位置推的了：{head}")
        self.assertNotIn("C:\\", head)

    def test_find_claude_has_an_explicit_override(self):
        """装 claude 的地方可配置（`WEBDRIVER_CLAUDE`），且**指了就必须用**。"""
        sys.path.insert(0, str(PROJECT / "lib" / "web"))
        import server as real  # noqa: E402 —— 这里的 claude.exe 本机确实存在，import 得起来
        old = os.environ.get("WEBDRIVER_CLAUDE")
        self.addCleanup(lambda: os.environ.__setitem__("WEBDRIVER_CLAUDE", old)
                        if old is not None else os.environ.pop("WEBDRIVER_CLAUDE", None))
        os.environ["WEBDRIVER_CLAUDE"] = sys.executable
        self.assertEqual(real._find_claude(), Path(sys.executable))
        os.environ["WEBDRIVER_CLAUDE"] = str(PROJECT / "根本没有这个文件")
        self.assertIsNone(real._find_claude(), "指了个不存在的路径，该报错而不是悄悄换一个")
        self.assertNotIn("Users\\Cyl", (PROJECT / "lib/web/server.py").read_text(encoding="utf-8")
                         .split("def _find_claude", 1)[1].split("\ndef ", 1)[0],
                         "实现里又写死了某个人的家目录")

    def test_the_three_model_keys_are_documented_in_the_template(self):
        """哨兵：`.env` 该有的就是**这三个**。

        钉两件：模板里有这三个名字；**别名不在这三个之外被当成必填**（模板里若又长出一串
        `ANTHROPIC_DEFAULT_*` 必填键，说明口径被改回去了 —— 口径是"一个模型走到底"）。
        """
        tpl = (PROJECT / ".env.example").read_text(encoding="utf-8")
        for key in ("ANTHROPIC_BASE_URL", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_MODEL"):
            self.assertIn(key, tpl, f".env.example 里没有 {key}")

    def test_a_configured_dot_env_provides_all_three_model_keys(self):
        """本机的 `.env` 只要**动过**（有端点），就必须把端点 + 密钥 + 主模型三样交代齐。

        `.env` 不在仓库里（`.gitignore` 挡着），所以这条是**本机配置体检**，不是可移植用例：
        新克隆下来的仓库 `.env` 根本不存在，那是"还没配"，不是"配错了" —— 直接跳过，
        免得每个克隆下来的人都看到一条红的。判据是"配了就得配全"，不是"必须存在"。
        """
        import os
        import subprocess
        script = ("import sys; sys.path.insert(0, 'lib/web'); import server; "
                  "print(server._DOTENV_KEYS)")
        clean = {k: v for k, v in os.environ.items() if not k.startswith("ANTHROPIC_")
                 and not k.startswith("CLAUDE_CODE_")}
        out = subprocess.run([sys.executable, "-c", script], cwd=str(PROJECT), env=clean,
                             capture_output=True, text=True, encoding="utf-8",
                             errors="replace").stdout
        if "ANTHROPIC_BASE_URL" not in out:
            self.skipTest("本机 .env 还没配（仓库里本来就不带它）—— 这条只管「配了就得配全」")
        for key in ("ANTHROPIC_BASE_URL", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_MODEL"):
            self.assertIn(key, out, f"干净环境下 .env 没提供 {key}（输出：{out.strip()[:120]}）")

    def test_the_shipped_delivery_config_is_not_pinned_to_a_machine(self):
        """仓库里那份 `config/delivery.local.json` 的 `output_dir` 不许**钉死一个本机路径**。

        本仓无 git，这份配置是跟着仓库一起被拷走的 —— 钉死一个绝对路径，新机器就会把产物写到
        旧机器的路径去（或凭空新建一棵 `C:\\Users\\...` 树）。空值 = 用 `<仓库根>/产物/`，跟着仓库走。

        产物路径改成"点着选"之后，**显式选仓外目录**是合法用法（`resolve_output_dir` 本来就
        允许它，`regression/test_delivery.py` 钉着这条），那种情况下只能存绝对 —— 一刀切禁绝对
        会让这个测试对**合法操作**报红，那是坏测试。所以判据按"是不是真的能用"分档：
          · 空   ⇒ OK（回落 `<根>/产物`）；
          · 相对 ⇒ 必须落在仓内；
          · 绝对 ⇒ **必须真实存在** —— 真正要防的是"从别的机器拷来的陈旧路径"，
            那种路径 `is_dir()` 为假，这里照样红。
        "仓内必须存成相对"这条**归一化**由 `regression/test_setup.py::StoreOutputDirTests` 钉。
        """
        import json
        cfg = json.loads((PROJECT / "config/delivery.local.json").read_text(encoding="utf-8-sig"))
        out = str(cfg.get("output_dir") or "")
        if not out:
            return
        p = Path(out)
        if p.is_absolute():
            self.assertTrue(p.is_dir(),
                            f"output_dir 是个**不存在**的绝对路径：{out!r} —— 多半是从别的机器"
                            f"拷过来的陈旧路径。改成空串（默认 <根>/产物/）或重新选一个")
        else:
            self.assertNotIn(":", out, f"相对路径里不该有盘符：{out!r}")
            self.assertTrue((PROJECT / out).resolve().is_relative_to(PROJECT.resolve()),
                            f"相对路径越出仓库了：{out!r}")


def load_claude_bin():
    """加载 `lib/web/claude_bin.py`（**无副作用**，可以直接 import）。"""
    sys.path.insert(0, str(PROJECT / "lib" / "web"))
    import claude_bin
    return claude_bin


class ClaudeDiscoveryTests(unittest.TestCase):
    """claude 去哪找 —— 驱动与 `runtime/doctor.py` **共用同一份实现**。

    为什么单测这一层：新机器上最容易撞的坏组合是「doctor 全绿、驱动却起不来」——
    因为驱动是在 **import 期**发现找不到 claude 就地 SystemExit 的，而 doctor 若不看
    claude（它只查 Python 包与 xelatex 这类外部工具），两处逻辑一旦各写一份，
    迟早漂移成"doctor 说有、驱动说没有"。
    """

    def setUp(self):
        self.cb = load_claude_bin()
        self._old = os.environ.get(self.cb.OVERRIDE_KEY)
        self.addCleanup(self._restore)

    def _restore(self):
        os.environ.pop(self.cb.OVERRIDE_KEY, None)
        if self._old is not None:
            os.environ[self.cb.OVERRIDE_KEY] = self._old

    # ---- 契约 ----

    def test_the_override_is_honoured_and_a_typo_is_not_silently_worked_around(self):
        """指了就必须用；指错了要报错，**不许**悄悄换一个（悄悄换更坑人）。"""
        os.environ[self.cb.OVERRIDE_KEY] = sys.executable
        self.assertEqual(self.cb.find_claude(), Path(sys.executable))
        os.environ[self.cb.OVERRIDE_KEY] = str(PROJECT / "根本没有这个文件")
        self.assertIsNone(self.cb.find_claude())

    def test_the_driver_uses_this_same_implementation(self):
        """单一事实来源：`server._find_claude` 不许另长一份，退出时的报错也要走同一份诊断。

        这里**只做静态断言**：import `server.py` 会拉起 FastAPI、还会启动孤儿回收器
        —— 那东西会去杀正在干活的阶段 agent，所以任何用例都别为了测一行 import 期代码
        去真 import 它。
        """
        src = (PROJECT / "lib/web/server.py").read_text(encoding="utf-8")
        body = src.split("def _find_claude", 1)[1].split("\ndef ", 1)[0]
        self.assertIn("return find_claude()", body, f"_find_claude 不再转发到共享实现了：{body}")
        self.assertIn("raise SystemExit(explain_claude())", src,
                      "import 期那句退出不再用共享诊断了 —— 新机器上只会看到一句"
                      "『未找到 claude』，不知道该装什么、去哪儿装")

    def test_no_home_directory_is_hardcoded(self):
        """发现逻辑里不许出现写死的家目录 —— 换台机器就该还能用。"""
        for name in ("lib/web/claude_bin.py", "runtime/doctor.py"):
            src = (PROJECT / name).read_text(encoding="utf-8")
            self.assertNotIn("Users\\Cyl", src, f"{name} 里又写死了某个人的家目录")
            self.assertNotIn("Users/Cyl", src, f"{name} 里又写死了某个人的家目录")

    # ---- 诊断信息（找不到时要**说清楚**）----

    def test_a_missing_override_is_reported_as_such_not_as_no_claude(self):
        """`WEBDRIVER_CLAUDE` 填错时，不能报成"请在 .env 里设 WEBDRIVER_CLAUDE"—— 明明已经设了。

        报错要说清是「你填的那个路径不存在」，否则人会去翻一个其实填对了的键。"""
        os.environ[self.cb.OVERRIDE_KEY] = str(PROJECT / "根本没有这个文件")
        msg = self.cb.explain()
        self.assertIn("不存在", msg, msg)
        self.assertIn(self.cb.OVERRIDE_KEY, msg, msg)

    def test_the_report_lists_where_it_looked(self):
        """找不到时要说清"去哪儿找过"，否则不知道该把 claude 装到哪。"""
        r = self.cb.doctor_report()
        self.assertIn(r["status"], ("OK", "MISSING"))
        self.assertEqual(len(r["searched"]), len(self.cb.EXT_SUBDIRS))
        for d in self.cb.search_dirs():
            self.assertIn(str(d), r["searched"])
        if r["status"] == "OK":
            self.assertTrue(Path(r["path"]).is_file(), r["path"])

    # ---- 接进 doctor ----

    def test_doctor_actually_reports_claude(self):
        """`runtime/doctor.py` 必须把 claude 报出来，且缺了就算 missing。

        **不断言 rc==0**：doctor 的返回码是"有没有缺任何东西"，而测试用的解释器未必是
        项目那个（`config/runtime.local.json` 里指的那个），缺 scipy/matplotlib 之类很正常。
        这里只验"claude 这一项在、且与 missing 清单自洽"。
        """
        r = subprocess.run([sys.executable, str(PROJECT / "runtime" / "doctor.py")],
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace", cwd=str(PROJECT), timeout=120)
        self.assertTrue(r.stdout.strip(), f"doctor 没输出：{r.stderr[-800:]}")
        d = json.loads(r.stdout)
        self.assertIn("claude", d, "doctor 的输出里没有 claude 这一项")
        self.assertIn(d["claude"]["status"], ("OK", "MISSING"))
        self.assertEqual(d["claude"]["status"] == "OK", "claude" not in d["missing"],
                         "claude 的 OK/MISSING 与 missing 清单必须一致，否则读的人会被误导")


if __name__ == "__main__":
    unittest.main()
