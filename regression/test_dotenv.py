# -*- coding: utf-8 -*-
"""项目根 `.env` 的解析（`lib/web/server.py::_load_dotenv`）。

为什么值得钉：这是「驱动到底打哪个地址、用哪个模型」唯一显式的地方 —— 配置的口径是
项目里的 `.env`，不是机器上的隐式环境。解析出错的症状是**最难查的那一类**：
填了没生效 / 生效了但不是你以为的那个值。所以逐条把规则钉住。

用 AST 抠函数来测，**不 import server.py** —— 那会拉起 FastAPI 并执行模块级副作用。
"""
import ast
import os
import sys
import re
import tempfile
import types
import unittest
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]


def _load_fn():
    tree = ast.parse((PROJECT / "lib/web/server.py").read_text(encoding="utf-8-sig"))
    mod = types.ModuleType("dotenv_probe")
    mod.__file__ = str(PROJECT / "lib/web/server.py")
    # 这个探针只把 `_load_dotenv` 单个函数抠出来 exec，所以函数体里用到的**每一个**模块级名字
    #   都得在这儿补上 —— 漏一个就是 `NameError`（例如函数里新加一句 `re.split(...)`，
    #   整族用例会全红，而**产品本身是好的**）。
    #   加一句 `re` 就是为此：这一步是"测试在替函数声明依赖"，改函数体时别忘了回头补。
    mod.os, mod.Path, mod.re = os, Path, re
    mod.ROOT = PROJECT
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "_load_dotenv":
            exec(compile(ast.Module([node], []), "<probe>", "exec"), mod.__dict__)
            return mod._load_dotenv
    raise AssertionError("没找到 _load_dotenv")


class DotenvTests(unittest.TestCase):
    def setUp(self):
        self.fn = _load_fn()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.p = Path(self.tmp.name) / ".env"

    def tearDown(self):
        for k in ("T_A", "T_B", "T_C", "T_D", "T_E", "T_F"):
            os.environ.pop(k, None)

    def test_basic_comments_export_and_quotes(self):
        self.p.write_text("# 注释\n\n"
                          "T_A=plain\n"
                          "export T_B=exported\n"
                          'T_C="双引号"\n'
                          "T_D='x=y=z'\n", encoding="utf-8")
        got, bad = self.fn(self.p)
        self.assertEqual(bad, [])
        self.assertEqual(sorted(got), ["T_A", "T_B", "T_C", "T_D"])
        self.assertEqual(os.environ["T_D"], "x=y=z", "值里可以有 `=`（只按第一个切）")
        self.assertEqual(os.environ["T_C"], "双引号", "成对引号要剥掉")

    def test_an_inline_comment_is_not_part_of_the_value(self):
        """未加引号的值：` #` 起是行内注释，要切掉；**加了引号的里头的 `#` 是内容**。

        为什么值得单钉：`.env.example` 里那批旋钮就是 `# KEY=值  # 说明` 的形状，
        取消注释就会踩到 —— 注释被算进值 ⇒ 数字退回默认（以为设了其实没有）、
        或者模型名带着注释去调用（直接失败且看不出为什么）。
        """
        self.p.write_text("T_A=300        # 判假死\n"
                          "T_B=x#y\n"              # 井号前没空白 ⇒ 是值本身
                          'T_C="a # b"\n'          # 引号里的井号 ⇒ 内容
                          "T_D= # 只有注释\n"      # 等号后先空白再井号 ⇒ 整段注释 ⇒ 等于没设
                          "T_E=#开头像注释\n"      # 井号紧跟等号 ⇒ 是**值**（口令可能是这形状）
                          "T_F=a#b\n",             # 值里带井号、前面无空白 ⇒ 值本身
                          encoding="utf-8")
        got, bad = self.fn(self.p)
        self.assertEqual(bad, [])
        self.assertEqual(os.environ["T_A"], "300")
        self.assertEqual(os.environ["T_B"], "x#y", "井号前没有空白，不该当注释切掉")
        self.assertEqual(os.environ["T_C"], "a # b", "引号里的井号是内容")
        self.assertEqual(os.environ["T_E"], "#开头像注释",
                         "井号紧跟等号 ⇒ 是值；当成注释会让以 # 开头的口令静默变成没设")
        self.assertEqual(os.environ["T_F"], "a#b")
        self.assertNotIn("T_D", got, "只写注释的行等于空值 ⇒ 没设")

    def test_a_broken_line_is_reported_not_fatal(self):
        """手滑一行不该让驱动起不来 —— 但要**告诉你第几行**。"""
        self.p.write_text("T_A=ok\n这一行没有等号\n", encoding="utf-8")
        got, bad = self.fn(self.p)
        self.assertEqual(got, ["T_A"])
        self.assertEqual(len(bad), 1)
        self.assertIn("第 2 行", bad[0])

    def test_an_existing_env_var_wins(self):
        """已存在的环境变量优先：临时 `$env:ANTHROPIC_MODEL=...` 调试时，那个优先 ——
        否则 `.env` 会把人当场设的值悄悄盖掉（最难查的一类故障）。"""
        os.environ["T_A"] = "来自环境"
        self.p.write_text("T_A=来自文件\n", encoding="utf-8")
        got, _ = self.fn(self.p)
        self.assertEqual(os.environ["T_A"], "来自环境")
        self.assertEqual(got, [], "没被采用的不该出现在返回值里")

    def test_a_missing_file_is_not_an_error(self):
        """有人就是不用 .env（用机器配置跑）—— 文件不在不是错误。"""
        self.assertEqual(self.fn(Path(self.tmp.name) / "不存在"), ([], []))

    def test_an_empty_value_means_unset(self):
        """`KEY=` = **没设**，不许往环境里塞一个空字符串。

        为什么较真：`.env` / `.env.example` 里成片是 `KEY=` 这种"把键摆出来"的写法
        （`ANTHROPIC_API_KEY=`、`ANTHROPIC_SMALL_FAST_MODEL=` 就是）。塞空串进去，
        按 `"KEY" in os.environ` 判"存在"的工具会以为"设了但为空"，那是另一回事；
        而且返回的"读到的键"也会虚报，让启动日志说"读到了 API_KEY"。
        """
        self.p.write_text("T_A=\nT_B=   \nT_C=真有值\n", encoding="utf-8")
        got, bad = self.fn(self.p)
        self.assertEqual(bad, [])
        self.assertEqual(got, ["T_C"], "空值不该算「读到了」")
        self.assertNotIn("T_A", os.environ, "空值被塞进环境了")
        self.assertNotIn("T_B", os.environ)


if __name__ == "__main__":
    unittest.main()
