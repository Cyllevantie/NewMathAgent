"""`lib/` 布局的哨兵：**写在 skill 与文档里的每一条路径都必须真的能跑**。

阶段 agent 的"做事依据"就是 `skills/*/SKILL.md` 里那些命令 —— `python lib/web/check_skeleton.py`、
`python -m lib.publication check`。这些字符串**没有类型检查**：目录搬家只要漏改一处，
测试全绿（因为测试自己会把 `lib/web` 加进 `sys.path`），要到**那个阶段真跑起来**才炸，
而那时已经烧了几十分钟的模型时间。所以判据不是"文件搬对了吗"，而是
**"skill 说的每一条路径，盘上都真的在吗"**。

两条性质 + 一组对照组：
  · 性质一：扫描范围内**不许**再出现旧的扁平根（`web/…`、`delivery/…`、…）；
  · 性质二：出现的 `lib/…`、`skills/…`、`config/…` 路径**必须存在**；
  · 对照组：把一条旧式引用种到临时目录里，检查器**必须红** —— 否则上面两条可能只是恒真
    （恒真的哨兵比没有更糟）。

沿用 `test_stale_noise.py` 的手法：性质 + 对照组，检查器本身当纯函数被单测。
"""
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))

#: 扫描范围：**agent 会照着做**的文件（skill、规范、根文档、配置）。
SCAN_GLOBS = ("skills/**/*.md", "skills/**/*.py", "docs/**/*.md",
              "config/*.json", "*.md", ".env.example")

#: 五个库包的旧顶层目录名。任何一条引用只要拿它们当**路径前缀**，就是漏改。
OLD_ROOTS = ("web", "delivery", "publication", "visualization", "result_contract")

#: 路径形态（含中文目录名，skills 里有 `产物/` 这类）。
PATH_RX = re.compile(
    r"(?<![\w/])((?:lib/)?(?:web|delivery|publication|visualization|result_contract"
    r"|runtime|regression|skills|docs|config)/[\w一-鿿./\-]+"
    r"\.(?:py|md|json|html|tex|example|sh|bat|ps1))")

#: `-m <模块>` 形态。宽匹配、随后**按前缀过滤**：`-m unittest` 这类标准库调用不该被扫进来，
#: 但 `-m lib.随便什么` 一定要扫 —— 否则新增一个 `lib/` 包、忘记写 `__main__.py` 时它静默放行。
MODULE_RX = re.compile(r"(?<![\w-])-m\s+([\w.]+)(?=\s|$)")

#: **明知**盘上没有、但引用是对的：运行期状态文件 + 只在你自己机器上的本地配置。
INTENTIONALLY_ABSENT = ("config/runtime.local.json",)
ABSENT_PREFIXES = ("runtime/",)


def scan(root, globs=SCAN_GLOBS):
    """返回 (旧式引用, 缺失引用, 缺失模块)。纯函数 ⇒ 对照组能拿临时目录直接调它。"""
    files = []
    for pat in globs:
        files += [p for p in Path(root).glob(pat) if p.is_file()]
    old, missing, no_main = {}, {}, {}
    for path in files:
        rel = path.relative_to(root).as_posix()
        text = path.read_text(encoding="utf-8-sig", errors="replace")
        for m in PATH_RX.finditer(text):
            ref = m.group(1).replace("*", "")
            head = ref.split("/")[0]
            if head in OLD_ROOTS:
                old.setdefault(ref, set()).add(rel)
            elif ref not in INTENTIONALLY_ABSENT \
                    and not ref.startswith(ABSENT_PREFIXES) \
                    and not (Path(root) / ref).exists():
                missing.setdefault(ref, set()).add(rel)
        for m in MODULE_RX.finditer(text):
            mod = m.group(1)
            if not mod.startswith("lib.") and mod.split(".")[0] not in OLD_ROOTS:
                continue                             # 标准库/第三方，不在本仓范围内
            if not mod.startswith("lib."):
                old.setdefault("-m " + mod, set()).add(rel)   # 老的裸包名调用
                continue
            pkg = mod.replace(".", "/")
            if not ((Path(root) / pkg / "__main__.py").exists()
                    or (Path(root) / (pkg + ".py")).exists()):
                no_main.setdefault(mod, set()).add(rel)
    return old, missing, no_main


class LibLayoutSentinelTests(unittest.TestCase):
    def test_no_reference_still_uses_the_old_flat_roots(self):
        """性质一：谁都不许再按老的 `web/…` 扁平位置写路径。

        它红了只有两种可能：要么漏改一处，要么有人又在 skill 里按旧位置写命令 ——
        两种都得当场改，不能留到阶段跑起来才发现。
        """
        old, _, _ = scan(PROJECT)
        self.assertFalse(old, "还在按旧的扁平位置引用代码：\n" + "\n".join(
            f"  {ref}  ←  {sorted(files)[:3]}" for ref, files in sorted(old.items())))

    def test_every_named_path_really_exists(self):
        """性质二：skill/文档里点名的框架文件，盘上必须真的在。"""
        _, missing, _ = scan(PROJECT)
        self.assertFalse(missing, "点名的文件不存在：\n" + "\n".join(
            f"  {ref}  ←  {sorted(files)[:3]}" for ref, files in sorted(missing.items())))

    def test_every_module_invocation_has_a_main(self):
        """`python -m lib.publication check` 要有 `lib/publication/__main__.py`。

        少一个 `__main__.py` 时，那条命令会以 "No module named lib.publication.__main__"
        失败 —— 而它散在十来个 skill 的收尾检查里。
        """
        _, _, no_main = scan(PROJECT)
        self.assertFalse(no_main, "`-m` 调了没有 __main__.py 的包：\n" + "\n".join(
            f"  {mod}  ←  {sorted(files)[:3]}" for mod, files in sorted(no_main.items())))

    def test_the_checker_catches_a_planted_old_style_reference(self):
        """对照组：种一条旧式引用进临时目录，检查器**必须**红。

        没有它，上面三条可能只是恒真（扫描范围写错、正则永远不匹配都长得一模一样）。
        """
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, True)
        (tmp / "skills" / "fake").mkdir(parents=True)
        good = tmp / "skills" / "fake" / "SKILL.md"
        good.write_text("跑 `python lib/web/check_skeleton.py x`。\n", encoding="utf-8")
        self.assertEqual(scan(tmp)[0], {}, "干净的引用不该被误报")

        good.write_text("跑 `python web/check_skeleton.py x`。\n", encoding="utf-8")
        old, _, _ = scan(tmp)
        self.assertIn("web/check_skeleton.py", old, "旧式引用必须被抓到")

        good.write_text("跑 `python lib/web/no_such_tool.py x`。\n", encoding="utf-8")
        _, missing, _ = scan(tmp)
        self.assertIn("lib/web/no_such_tool.py", missing, "不存在的文件必须被抓到")

        good.write_text("跑 `python -m lib.nosuchpkg check`。\n", encoding="utf-8")
        _, _, no_main = scan(tmp)
        self.assertIn("lib.nosuchpkg", no_main, "没有 __main__.py 的包必须被抓到")

        good.write_text("跑 `python -m publication check`。\n", encoding="utf-8")
        old, _, _ = scan(tmp)
        self.assertIn("-m publication", old, "老的裸包名调用必须被抓到")

        good.write_text("跑 `python -m unittest discover`。\n", encoding="utf-8")
        self.assertEqual(scan(tmp), ({}, {}, {}), "标准库调用不该被误报")


if __name__ == "__main__":
    unittest.main()
