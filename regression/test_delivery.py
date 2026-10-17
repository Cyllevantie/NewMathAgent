"""提交形状的交付包：布局、白名单、清单对账、cache 归档。

守三条不变量：
  ① 产物根目录下**只**出现提交项 + `其余文件/` —— 「都得是需要提交的」靠白名单，不靠自觉；
  ② 清单是**声明**：声明了必须有、实物多了也不行；
  ③ 归档目录名在 Windows 上建得出来（冒号是 Windows 的保留字符，进不了目录名）。
"""
import errno
import json
import shutil
import subprocess
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock

import sys

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))
from lib.delivery.checks import (DEMO_3D_ENGINE, DEMO_3D_EXEMPT_TOKEN, _a1_table_names,
                                 check, checklist_consistency_issues, demo_3d_issues,
                                 demo_html_issues, precheck, report, required_items_issues)
from lib.delivery.core import (BODY_PDF, OTHER_DIR, SUBMISSION_PARENT, SUBMISSION_POINTER,
                           archive_into_cache, body_pdf_name, configured_output_dir,
                           delivery_name, load_manifest, package, provisional_items,
                           resolve_output_dir, resolve_source, resolve_stage_dir,
                           resolve_submission_dir, rotate_pointer, unique_boundary_name)

WHEN = datetime(2026, 9, 18, 19, 13, 0)
SUBMIT = ["正文.pdf", "附录A.pdf", "demo.html", "运行说明.md", "AI工具使用详情.pdf",
          "result1.xlsx", "result2.xlsx", "附件1.xlsx", "run_all.py", "core.py"]


def engine_text():
    """真引擎的整段原文（逐字内联进夹具的 demo.html）。

    夹具里的 demo.html 要代表**正常形态**（三维主视图在），`check(...) == []` 一类的
    断言才继续代表"真实通过态"；不然每个夹具都会栽在新增的三维判据上，而那些用例
    本来想考的不是这件事。
    """
    return (PROJECT / DEMO_3D_ENGINE).read_text(encoding="utf-8")


def make_workspace():
    root = Path(tempfile.mkdtemp())
    for rel, body in [
        # 一律用 str：bytes 字面量不能含非 ASCII，而这里的内容基本都有中文。
        ("paper/main.pdf", "%PDF-1.4 paper"),
        ("paper/main.tex", "\\documentclass{ctexart}"),
        ("paper/sections/1_restatement.tex", "\\section{问题重述}"),
        ("paper_appendix/main.pdf", "%PDF-1.4 appendix"),
        ("paper_appendix/main.tex", "\\documentclass{ctexart}"),
        ("paper/ai_tools/AI工具使用详情.pdf", "%PDF-1.4 ai-tools"),
        ("demo/demo.html", "<html><body><script>\n" + engine_text() + "\n</script></body></html>"),
        ("results/result1.xlsx", "xlsx-1"),
        ("results/result2.xlsx", "xlsx-2"),
        ("code/run_all.py", "# 主程序入口\n"),
        ("code/core.py", "# 有限体积离散\n"),
        ("code/plot_figures.py", "# 画图辅助，不作提交项\n"),
        ("code/outputs/q1.json", "{}"),
        ("reports/RESULTS_REPORT.md", "# 结果报告\n"),
        ("request/attachments/附件1.xlsx", b"attach"),
        ("运行说明.md", "# 运行说明\n"),
    ]:
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(body if isinstance(body, bytes) else body.encode())
    (root / "reports/SUBMISSION_MANIFEST.json").write_text(json.dumps({
        "schema_version": 1, "stage": "format",
        "items": [{"path": n, "desc": f"{n} 的说明"} for n in SUBMIT]}, ensure_ascii=False),
        encoding="utf-8")
    return root


class NameAndPathTest(unittest.TestCase):
    def test_delivery_name_matches_the_agreed_format(self):
        self.assertEqual(delivery_name("2026A", WHEN), "2026A_2026.9.18_19.13.00")
        # 题目标识留空 → 只用日期
        self.assertEqual(delivery_name("", WHEN), "2026.9.18_19.13.00")
        self.assertEqual(delivery_name("   ", WHEN), "2026.9.18_19.13.00")

    def test_delivery_name_rejects_windows_reserved_chars(self):
        """Windows 保留字符（冒号、正反斜杠、`*` `?` `"` `<` `|`）不许进交付目录名。

        钉住的是「宁可报错让人去改标识，也不要建出一个截断/诡异的目录名」——
        冒号在 Windows 上根本建不出目录，静默降级的后果要到交付时才看得见。
        """
        for bad in ("2026A:1", "A/B", "A\\B", "A*B", "A?B", 'A"B', "A<B", "A|B"):
            with self.assertRaises(ValueError, msg=bad):
                delivery_name(bad, WHEN)

    def test_output_dir_defaults_to_project_root_plus_产物(self):
        root = Path(tempfile.mkdtemp())
        self.assertEqual(resolve_output_dir(root, ""), root.resolve() / "产物")
        self.assertEqual(resolve_output_dir(root, "   "), root.resolve() / "产物")
        # 选成项目根 = 没选 → 仍然落到 产物/，不许把产物铺在项目根上
        self.assertEqual(resolve_output_dir(root, str(root)), root.resolve() / "产物")
        self.assertEqual(resolve_output_dir(root, "sub"), root.resolve() / "sub")
        outside = resolve_output_dir(root, str(root.parent / "elsewhere"))
        self.assertEqual(outside, root.parent.resolve() / "elsewhere")


class PackageTest(unittest.TestCase):
    def setUp(self):
        self.root = make_workspace()
        self.addCleanup(shutil.rmtree, self.root, True)
        self.out = self.root / "产物"

    def test_package_produces_only_submission_items_plus_other(self):
        package(self.root, self.out, load_manifest(self.root))
        names = sorted(p.name for p in self.out.iterdir())
        self.assertEqual(names, sorted(SUBMIT + [OTHER_DIR]))
        self.assertEqual(check(self.root, self.out), [])

    def test_flat_python_and_result_tables(self):
        package(self.root, self.out, load_manifest(self.root))
        for n in ("run_all.py", "core.py", "result1.xlsx", "result2.xlsx", "附件1.xlsx"):
            self.assertTrue((self.out / n).is_file(), n)
        # 源在 code/ 里，产物里必须**平铺**（清单写的是不带前缀的名字）
        self.assertFalse((self.out / "code").exists())

    def test_submitted_py_is_not_duplicated_in_aux(self):
        """同一份代码不能既平铺在根目录、又躺在 其余文件/辅助脚本/ —— 那样分不清哪个是提交件。"""
        package(self.root, self.out, load_manifest(self.root))
        aux = self.out / OTHER_DIR / "辅助脚本"
        self.assertFalse((aux / "run_all.py").exists())
        self.assertFalse((aux / "core.py").exists())
        # 不作提交项的那些照旧留档
        self.assertTrue((aux / "plot_figures.py").exists())
        self.assertTrue((aux / "outputs/q1.json").exists())

    def test_other_dir_holds_the_latex_projects_and_reports(self):
        package(self.root, self.out, load_manifest(self.root))
        self.assertTrue((self.out / OTHER_DIR / "正文/main.tex").exists())
        self.assertTrue((self.out / OTHER_DIR / "正文/main.pdf").exists())
        self.assertTrue((self.out / OTHER_DIR / "附录/main.tex").exists())
        self.assertTrue((self.out / OTHER_DIR / "内部报告/RESULTS_REPORT.md").exists())

    def test_missing_source_is_reported_not_silently_skipped(self):
        items = load_manifest(self.root)
        (self.root / "demo/demo.html").unlink()
        with self.assertRaises(ValueError) as cm:
            package(self.root, self.out, items)
        self.assertIn("demo", str(cm.exception))

    def test_failed_package_leaves_previous_delivery_intact(self):
        package(self.root, self.out, load_manifest(self.root))
        (self.out / "marker.txt").write_text("旧的一轮", encoding="utf-8")
        items = load_manifest(self.root)
        (self.root / "results/result1.xlsx").unlink()
        with self.assertRaises(ValueError):
            package(self.root, self.out, items)
        self.assertTrue((self.out / "marker.txt").exists(), "打包失败不该动上一份产物")

    def test_missing_manifest_is_an_error_not_a_fallback(self):
        (self.root / "reports/SUBMISSION_MANIFEST.json").unlink()
        with self.assertRaises(ValueError) as cm:
            load_manifest(self.root)
        # 2026-10-17 解耦：清单的首产者是 ⑨（⑭ 只保留对账/修补权）—— 报错文案跟着换。
        self.assertIn("9Paper-writing", str(cm.exception))


class ManifestOwnershipContractTest(unittest.TestCase):
    """2026-10-17 解耦的跨文件一致性哨兵：清单/末页表的**首产者 = 9Paper-writing**。

    这一层最容易漂移的形态是"文档说 A、代码 grep B"—— 所以把三处硬文案一起钉住：
    交付层的报错（人修的时候会读到它）、⑨ 的 SKILL（写的人读它）、两个模板（生成表的起点）。
    """

    def test_manifest_error_points_at_the_write_stage(self):
        text = (PROJECT / "lib/delivery/core.py").read_text(encoding="utf-8")
        self.assertIn("必须由 9Paper-writing 写出它", text)
        self.assertNotIn("必须由 14Layout-and-format 写出它", text)

    def test_skill_nine_carries_the_delivery_rules(self):
        text = (PROJECT / "skills/9Paper-writing/SKILL.md").read_text(encoding="utf-8")
        for token in ("reports/SUBMISSION_MANIFEST.json", "A1_materials",
                      "运行说明.md", "AI工具使用详情.pdf"):
            self.assertIn(token, text)

    def test_a1_templates_say_nine_generates_the_body(self):
        # 动态发现所有模板族，避免再出现「新增/删除一族，测试仍盯着旧路径」的漂移。
        templates = sorted(PROJECT.glob(
            "skills/9Paper-writing/templates/*/*/sections/A1_materials.tex"))
        self.assertTrue(templates, "找不到任何模板族的 A1_materials.tex")
        for path in templates:
            rel = path.relative_to(PROJECT).as_posix()
            text = path.read_text(encoding="utf-8")
            self.assertIn("9Paper-writing", text, rel)
            self.assertNotIn("由 14Layout-and-format 逐行生成", text, rel)
            # 反转归属句（「由 14Layout-and-format 生成（9Paper-writing 只是挂名）」）
            # 也不许出现 —— A1 模板里没有任何合法的「由 ⑭ …」句。
            self.assertNotIn("由 14Layout-and-format", text, rel)

    def test_skill_fourteen_keeps_reconciliation_not_authorship(self):
        text = (PROJECT / "skills/14Layout-and-format/SKILL.md").read_text(encoding="utf-8")
        self.assertIn("首产归 ⑨", text)
        self.assertIn("对账", text)

    def test_shared_template_layer_says_nine_generates_the_section(self):
        """`_base/macros.tex` 是共享层 —— ⑨ 复制它进两个工程，旧句会被 agent 当事实读。"""
        text = (PROJECT / "skills/9Paper-writing/templates/_base/macros.tex").read_text(encoding="utf-8")
        self.assertIn("9Paper-writing", text)
        self.assertNotIn("由 format 阶段生成", text)

    def test_agents_and_claude_agree_on_the_manifest_owner(self):
        """AGENTS.md 是 CLAUDE.md 的镜像（Codex 侧读它）—— 两份都得是 ⑨ 首产。"""
        for rel in ("AGENTS.md", "CLAUDE.md"):
            text = (PROJECT / rel).read_text(encoding="utf-8")
            self.assertIn("由 9Paper-writing", text, rel)
            # 负断言只钉「⑭ 写/生成清单」这类**旧归属**；「对账与修补由 ⑭ 负责」是合法句子。
            self.assertNotIn("由 14Layout-and-format 写", text, rel)
            self.assertNotIn("由 14Layout-and-format 生成", text, rel)


class ChecklistConsistencyTest(unittest.TestCase):
    """清单 ↔ 正文末页清单表 的名字集合机检（2026-10-17 解耦新增：两边不再同源产出）。

    解耦前两边由 ⑭ 同一份脚本产出、天然一致；现在 ⑨ 首产、⑬/⑭ 都可能只碰一边，
    "两边必须逐项一致" 只剩散文就是空的 —— 这组用例钉住机器判据本身。
    """

    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root, True)
        (self.root / "reports").mkdir()
        (self.root / "paper/sections").mkdir(parents=True)
        (self.root / "paper/main.tex").write_text(r"\papertitle{测试标题}", encoding="utf-8")
        (self.root / "reports/SUBMISSION_MANIFEST.json").write_text(json.dumps({
            "schema_version": 1, "stage": "write",
            "items": [{"path": n, "desc": "d"} for n in
                      ["测试标题.pdf", "附录A.pdf", "demo.html", "运行说明.md",
                       "AI工具使用详情.pdf", "q1.py", "q2.py", "run_all.py"]]},
            ensure_ascii=False), encoding="utf-8")

    def _write_table(self, rows):
        body = "\n".join(f"    {r} \\\\" for r in rows)
        (self.root / "paper/sections/A1_materials.tex").write_text(
            "\\begin{tableblock}\n"
            "\\begin{tabular}{@{}p{0.3\\textwidth}p{0.6\\textwidth}@{}}\n"
            "    \\toprule\n"
            "    \\textbf{文件} & \\textbf{说明} \\\\\n"
            "    \\midrule\n"
            + body + "\n"
            "    \\bottomrule\n"
            "  \\end{tabular}\n"
            "\\end{tableblock}\n", encoding="utf-8")

    def test_matching_sets_pass(self):
        self._write_table(["附录A.pdf & a", "demo.html & a", "运行说明.md & a",
                           "AI工具使用详情.pdf & a", "q1.py、q2.py & a", "run\\_all.py & a"])
        self.assertEqual(checklist_consistency_issues(self.root), [])

    def test_missing_and_extra_are_flagged(self):
        self._write_table(["附录A.pdf & a", "demo.html & a", "运行说明.md & a",
                           "AI工具使用详情.pdf & a", "q1.py、q2.py & a", "幽灵.py & a"])
        issues = checklist_consistency_issues(self.root)
        missing = [i for i in issues if "少了" in i]
        extra = [i for i in issues if "多了" in i]
        self.assertEqual(len(missing), 1, issues)       # 按内容找，别依赖输出顺序
        self.assertEqual(len(extra), 1, issues)
        self.assertIn("run_all.py", missing[0])         # 少的是清单里的 run_all.py
        self.assertIn("幽灵.py", extra[0])               # 多的是清单没有的

    def test_escaped_ampersand_and_wrappers_are_parsed(self):
        """2026-10-17 审计加固：`\\&`、`\\multicolumn`、行尾 `\\\\`（带空格）、行内 `%` 都要认。"""
        self._write_table(["\\multicolumn{1}{c}{q1.py} & a",
                           "q2.py \\\\ & a",
                           "run\\_all.py % 注 & a",
                           "A\\&B.py & a"])
        text = (self.root / "paper/sections/A1_materials.tex").read_text(encoding="utf-8")
        self.assertEqual(sorted(_a1_table_names(text)),
                         ["A&B.py", "q1.py", "q2.py", "run_all.py"])

    def test_placeholder_table_is_flagged(self):
        """占位符没填 = "最严重的形态问题" —— 机检必须当场拦住（⑮ 会判 FAIL）。"""
        self._write_table(["<由 9Paper-writing 依 reports/SUBMISSION\\_MANIFEST.json 逐行生成：文件名> & <一句话说清它做什么>"])
        issues = checklist_consistency_issues(self.root)
        self.assertTrue(issues and "少了这些提交项" in issues[0], issues)

    def test_without_one_side_it_does_not_judge(self):
        """旧工作区/大多数夹具没有 A1 表、或没有清单 ⇒ 不误报（与 precheck 的既有口径一致）。"""
        self.assertEqual(checklist_consistency_issues(self.root), [])
        self._write_table(["附录A.pdf & a"])
        (self.root / "reports/SUBMISSION_MANIFEST.json").unlink()
        self.assertEqual(checklist_consistency_issues(self.root), [])


class ChecklistWiringTest(unittest.TestCase):
    """接线哨兵：清单表核对必须真的挂在 `check()` 与 `precheck()` 上。

    2026-10-17 审计：删掉 checks.py 里两处 `issues.extend(checklist_consistency_issues(root))`
    后 65 个交付用例仍全绿 —— 函数测了、接线没人守。
    """

    def test_check_and_precheck_include_the_checklist_judge(self):
        root = make_workspace()
        self.addCleanup(shutil.rmtree, root, True)
        items = load_manifest(root)
        names = [i["path"] for i in items if i["path"] not in ("正文.pdf", "run_all.py")]
        rows = "\n".join(f"    {n} & 说明 \\\\" for n in names)
        (root / "paper/sections").mkdir(parents=True, exist_ok=True)
        (root / "paper/sections/A1_materials.tex").write_text(
            "\\begin{tabular}{ll}\n\\toprule\n\\textbf{文件} & \\textbf{说明} \\\\\n\\midrule\n"
            + rows + "\n\\bottomrule\n\\end{tabular}\n", encoding="utf-8")
        pre = precheck(root)
        self.assertTrue(any("少了这些提交项" in i and "run_all.py" in i for i in pre), pre)
        out = root / "产物"
        package(root, out, items)
        issues = check(root, out, items)
        self.assertTrue(any("少了这些提交项" in i and "run_all.py" in i for i in issues), issues)


class RequiredItemsTest(unittest.TestCase):
    """清单必须声明核心提交件（2026-10-17 审计：清单只写 run_all.py 也能 PASS）。"""

    def setUp(self):
        self.root = make_workspace()
        self.addCleanup(shutil.rmtree, self.root, True)
        self.manifest = self.root / "reports/SUBMISSION_MANIFEST.json"

    def _drop(self, *names):
        data = json.loads(self.manifest.read_text(encoding="utf-8"))
        data["items"] = [i for i in data["items"] if i["path"] not in names]
        self.manifest.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    def test_complete_manifest_passes(self):
        self.assertEqual(required_items_issues(self.root), [])

    def test_missing_body_or_appendix_or_ai_is_flagged(self):
        self._drop("正文.pdf", "附录A.pdf", "AI工具使用详情.pdf")
        joined = " ".join(required_items_issues(self.root))
        self.assertIn("正文 PDF", joined)
        self.assertIn("附录A.pdf", joined)
        self.assertIn("AI工具使用详情.pdf", joined)

    def test_demo_on_disk_but_undeclared_is_flagged(self):
        self._drop("demo.html")
        joined = " ".join(required_items_issues(self.root))
        self.assertIn("demo.html", joined, "盘上已有 demo 却被清单漏掉 ⇒ 必须报")

    def test_legit_demo_skip_is_not_flagged(self):
        """纯机理/纯证明题合法跳过 demo（盘上也没有）⇒ 不报。"""
        self._drop("demo.html")
        (self.root / "demo/demo.html").unlink()
        self.assertEqual(required_items_issues(self.root), [])


class CheckTest(unittest.TestCase):
    def setUp(self):
        self.root = make_workspace()
        self.addCleanup(shutil.rmtree, self.root, True)
        self.out = self.root / "产物"
        package(self.root, self.out, load_manifest(self.root))

    def test_junk_in_root_is_flagged_with_a_destination(self):
        """白名单的负对照：往产物根目录塞一个不该提交的东西。"""
        (self.out / "notes.tex").write_text("x", encoding="utf-8")
        issues = check(self.root, self.out)
        self.assertEqual(len(issues), 1)
        self.assertIn("notes.tex", issues[0])
        self.assertIn(OTHER_DIR, issues[0])       # 必须指出该挪去哪，不能只说"多了个东西"

    def test_declared_but_absent_is_flagged(self):
        items = load_manifest(self.root)
        items.append({"path": "不存在的.pdf", "desc": "x", "source": ""})
        issues = check(self.root, self.out, items)
        self.assertTrue(any("不存在的.pdf" in i for i in issues), issues)

    def test_empty_submission_file_is_flagged(self):
        (self.out / "run_all.py").write_bytes(b"")
        issues = check(self.root, self.out)
        self.assertTrue(any("空文件" in i for i in issues), issues)

    def test_report_status_follows_issues(self):
        self.assertEqual(report(self.root, self.out)["status"], "PASS")
        (self.out / "junk.bin").write_bytes(b"x")
        self.assertEqual(report(self.root, self.out)["status"], "FAIL")


class DemoHtmlTest(unittest.TestCase):
    """`demo/demo.html` 必须**自包含**：打开就能用，不依赖同目录或网络上的其它文件。

    只靠 SKILL 里「多文件开发 + 打包时合并」那句话的自觉，后果是：产物里的 `demo.html`
    打开**白屏**，而打包、清单对账、页数检查**全都不会报错** —— 一路绿到交付。
    所以这条落成机器判据。
    """

    def setUp(self):
        self.root = make_workspace()
        self.addCleanup(shutil.rmtree, self.root, True)
        self.html = self.root / "demo/demo.html"

    def test_self_contained_demo_passes(self):
        self.html.write_text(
            '<html><head><style>body{}</style></head><body>'
            '<img src="data:image/png;base64,iVBORw0KGgo=">'
            '<a href="#top">回顶</a><script>var D={a:1};</script></body></html>',
            encoding="utf-8")
        self.assertEqual(demo_html_issues(self.root), [])

    def test_local_script_reference_is_flagged(self):
        """负对照：这正是「多文件开发」必然产生的形态，交付后页面白屏。"""
        self.html.write_text('<html><script src="app.js"></script></html>', encoding="utf-8")
        issues = demo_html_issues(self.root)
        self.assertEqual(len(issues), 1)
        self.assertIn("app.js", issues[0])
        self.assertIn("白屏", issues[0])

    def test_local_stylesheet_and_image_are_flagged(self):
        for body, needle in [('<link href="style.css" rel="stylesheet">', "style.css"),
                             ('<img src="data/x.png">', "data/x.png"),
                             ('<script src="vendor/chart.js"></script>', "vendor/chart.js")]:
            self.html.write_text(f"<html>{body}</html>", encoding="utf-8")
            issues = demo_html_issues(self.root)
            self.assertTrue(any(needle in i for i in issues), (needle, issues))

    def test_network_resource_is_flagged(self):
        """比赛现场可能没网 —— 引 CDN 的库同样打不开。"""
        self.html.write_text('<html><script src="https://cdn.jsdelivr.net/npm/chart.js"></script></html>',
                             encoding="utf-8")
        issues = demo_html_issues(self.root)
        self.assertTrue(any("联网" in i for i in issues), issues)

    def test_no_demo_at_all_is_not_an_error(self):
        """有的题不做 demo（纯机理/纯证明），不判。"""
        self.html.unlink()
        self.assertEqual(demo_html_issues(self.root), [])

    def test_check_surfaces_it(self):
        self.html.write_text('<html><script src="app.js"></script></html>', encoding="utf-8")
        package(self.root, self.root / "产物", load_manifest(self.root))
        issues = check(self.root, self.root / "产物")
        self.assertTrue(any("自包含" in i for i in issues), issues)


class Demo3DMainViewTest(unittest.TestCase):
    """`demo/demo.html` 的主视图必须是数据驱动三维（引擎**整段原文**内联），或显式豁免。

    判据要防的故障族与 DemoHtmlTest 同一类：主视图悄悄退回二维曲线图，打包、清单对账、
    页数检查**全都不会报错** —— 一路绿到交付，打开才发现"说好的三维主视图"不在。
    逐字比对还有个副作用用法：引擎原文从此是事实上的接口，改引擎必须在源文件里改。
    """

    def setUp(self):
        self.root = make_workspace()
        self.addCleanup(shutil.rmtree, self.root, True)
        self.html = self.root / "demo/demo.html"
        self.report = self.root / "reports/DEMO_REPORT.md"

    def test_inlined_engine_verbatim_passes(self):
        """夹具默认形态就是"引擎整段原文内联"——这条是全部用例的基线。"""
        self.assertEqual(demo_3d_issues(self.root), [])

    def test_plain_2d_demo_without_exemption_is_flagged(self):
        """负对照：就是这次要防的形态（二维曲线图当主视图、报告里没一个字说明）。"""
        self.html.write_text("<html><body><canvas id='c1'></canvas></body></html>", encoding="utf-8")
        issues = demo_3d_issues(self.root)
        self.assertEqual(len(issues), 1)
        self.assertIn("三维", issues[0])
        self.assertIn(DEMO_3D_EXEMPT_TOKEN, issues[0])      # 报错里给出"写豁免行"这条路
        self.assertIn("重跑", issues[0])                     # 以及"重跑 ⑯ 内联引擎"那条
        # 全量 check 也必须把它捞出来（不能只活在单元层面）
        package(self.root, self.root / "产物", load_manifest(self.root))
        self.assertTrue(any("三维" in i for i in check(self.root, self.root / "产物")))

    def test_exemption_line_with_a_reason_unlocks(self):
        """合法豁免：纯判定卡/纯表格题 —— 理由是**人写的**，判据只认"写没写"。"""
        self.html.write_text("<html><body>纯判定卡</body></html>", encoding="utf-8")
        self.report.write_text("# Demo 报告\n" + DEMO_3D_EXEMPT_TOKEN + "本题为纯阈值判定卡，参数无空间维度\n",
                               encoding="utf-8")
        self.assertEqual(demo_3d_issues(self.root), [])

    def test_exemption_without_a_reason_is_still_flagged(self):
        """对照组：光一个前缀不算豁免 —— 「说了理由」才是判据，不能拿空壳糊弄。"""
        self.html.write_text("<html><body>纯判定卡</body></html>", encoding="utf-8")
        self.report.write_text("# Demo 报告\n" + DEMO_3D_EXEMPT_TOKEN + "\n", encoding="utf-8")
        self.assertEqual(len(demo_3d_issues(self.root)), 1)

    def test_one_character_changed_breaks_the_verbatim_match(self):
        """逐字就是逐字：缩进/内容改一个字符都不再是"内联原文"。

        为什么不宽恕内容改动：agent "顺手优化"引擎之后，产物的行为和源文件就不再是
        一件事，夹具测的、交付检查比的也就都不是产物在跑的东西了。
        """
        self.html.write_text("<html><body><script>\n"
                             + engine_text().replace("scene3d v1", "scene3d v1x")
                             + "\n</script></body></html>", encoding="utf-8")
        self.assertEqual(len(demo_3d_issues(self.root)), 1)

    def test_crlf_and_trailing_spaces_are_tolerated(self):
        """行尾格式（CRLF、行尾空白）是编辑器差异，只折叠行尾、不算内容改动。

        用 `write_bytes` 落盘：Windows 上 `write_text` 会把每个 `\\n` 再翻译成 `\\r\\n`，
        显式写的 `\\r\\n` 会变成 `\\r\\r\\n` —— 夹具自己先把文件写坏，测的就不是折叠逻辑了。
        """
        mangled = "\r\n".join(line + "   " for line in engine_text().split("\n"))
        self.html.write_bytes(("<html><body><script>\n" + mangled + "\n</script></body></html>")
                              .encode("utf-8"))
        self.assertEqual(demo_3d_issues(self.root), [])

    def test_no_demo_at_all_is_not_an_error(self):
        """有的题不做 demo（纯机理/纯证明），连 demo.html 都没有 ⇒ 不判。"""
        self.html.unlink()
        self.assertEqual(demo_3d_issues(self.root), [])


class PrecheckTest(unittest.TestCase):
    """verify 那一关的**早期**核对 —— 别等到整链收口才发现清单没写。"""

    def setUp(self):
        self.root = make_workspace()
        self.addCleanup(shutil.rmtree, self.root, True)

    def test_complete_workspace_passes(self):
        self.assertEqual(precheck(self.root), [])

    def test_missing_manifest_is_reported_early(self):
        (self.root / "reports/SUBMISSION_MANIFEST.json").unlink()
        issues = precheck(self.root)
        self.assertEqual(len(issues), 1)
        self.assertIn("SUBMISSION_MANIFEST", issues[0])

    def test_declared_but_absent_file_is_reported(self):
        (self.root / "code/run_all.py").unlink()
        os_issues = precheck(self.root)
        self.assertTrue(any("run_all.py" in i for i in os_issues), os_issues)

    def test_demo_html_is_allowed_to_be_late(self):
        """demo.html 由排在 verify **之后**的 16Web-demo 产出，此刻不该存在 ——

        不排除它的话，verify 会因为一个"还没轮到产出的文件"而卡住整链。
        """
        self.assertIn("demo.html", SUBMIT)                # 夹具清单里本来就有它
        (self.root / "demo/demo.html").unlink()          # 模拟 verify 时 demo 还没跑
        self.assertFalse((self.root / "demo/demo.html").exists())
        self.assertEqual(precheck(self.root), [],
                         "demo.html 还没产出不该拦住 verify —— 它是排在 verify 之后的阶段产的")
        # 反向对照：把清单里那一项换成**不晚**的名字，就必须报缺 —— 证明上面的通过
        # 是因为"它被允许迟到"，而不是因为 precheck 根本没查它。
        path = self.root / "reports/SUBMISSION_MANIFEST.json"
        manifest = json.loads(path.read_text(encoding="utf-8"))
        manifest["items"] = [dict(i, path="demo2.html") if i["path"] == "demo.html" else i
                             for i in manifest["items"]]
        path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
        self.assertTrue(any("demo2.html" in i for i in precheck(self.root)))


class ArchiveTest(unittest.TestCase):
    def test_archive_moves_contents_into_dated_folder(self):
        root = make_workspace()
        self.addCleanup(shutil.rmtree, root, True)
        out = root / "产物"
        package(root, out, load_manifest(root))
        dest = archive_into_cache(out, root / "cache", delivery_name("2026A", WHEN))
        self.assertEqual(dest, root / "cache" / "2026A_2026.9.18_19.13.00")
        self.assertTrue((dest / "正文.pdf").is_file())
        self.assertTrue((dest / OTHER_DIR / "正文/main.tex").is_file())
        self.assertFalse(out.exists(), "归档后产物目录应已切走")

    def test_archive_refuses_to_overwrite(self):
        root = make_workspace()
        self.addCleanup(shutil.rmtree, root, True)
        out = root / "产物"
        package(root, out, load_manifest(root))
        name = delivery_name("2026A", WHEN)
        archive_into_cache(out, root / "cache", name)
        package(root, out, load_manifest(root))
        with self.assertRaises(ValueError):
            archive_into_cache(out, root / "cache", name)


class CliDefaultTargetTests(unittest.TestCase):
    """`python -m lib.delivery check` 的对象是**提交件根**、且产物根读**面板配置**。

    这条命令被 `lib/web/server.py` 写进了给 agent 的 `recheck`，所以它查错地方是有代价的：
    ① 传产物根 ⇒ 白名单把 `cache/`、`各阶段产物/`、`提交作品/` 报成「不该提交的东西」，
       而报错文案**还会叫 agent 把它们挪去 `其余文件/`**（等于让 agent 搬走用户的归档目录）；
    ② 产物根硬编码 `<root>/产物` ⇒ 面板一改路径，它落在另一个目录上、报一串假 FAIL。
    """

    def _workspace(self):
        root = Path(tempfile.mkdtemp())
        (root / "config").mkdir(parents=True, exist_ok=True)
        (root / "reports").mkdir(parents=True, exist_ok=True)
        # 核心提交件必须齐（2026-10-17 起的完整性判据；demo 合法可缺，不进清单）
        (root / "reports/SUBMISSION_MANIFEST.json").write_text(json.dumps(
            {"schema_version": 1, "stage": "format",
             "items": [{"path": n, "desc": "d"} for n in
                       ("正文.pdf", "附录A.pdf", "运行说明.md", "AI工具使用详情.pdf")]},
            ensure_ascii=False), encoding="utf-8")
        return root

    def test_configured_output_dir_reads_the_panel_setting(self):
        root = self._workspace()
        self.assertEqual(configured_output_dir(root), "", "没配置时该给空串 ⇒ 退到默认")
        (root / "config/delivery.local.json").write_text(
            json.dumps({"output_dir": str(root / "别处")}, ensure_ascii=False), encoding="utf-8")
        self.assertEqual(configured_output_dir(root), str(root / "别处"))
        (root / "config/delivery.local.json").write_text("{ 坏 json", encoding="utf-8")
        self.assertEqual(configured_output_dir(root), "", "坏配置该退到默认，不该抛")

    def test_the_cli_does_not_fail_on_a_layout_that_has_archives(self):
        root = self._workspace()
        sub = root / "产物" / SUBMISSION_PARENT / SUBMISSION_POINTER
        sub.mkdir(parents=True)
        for n in ("正文.pdf", "附录A.pdf", "运行说明.md", "AI工具使用详情.pdf"):
            (sub / n).write_text("x", encoding="utf-8")
        # 产物根下另有三类**不是提交件**的目录 —— CLI 不许把它们当垃圾
        for extra in ("cache", "各阶段产物", "其他产物"):
            (root / "产物" / extra).mkdir(parents=True, exist_ok=True)

        # `--root` 是全局选项，必须在子命令**之前**（argparse 的规矩）
        proc = subprocess.run(
            [sys.executable, "-m", "lib.delivery", "--root", str(root), "check"],
            cwd=str(PROJECT), capture_output=True, text=True,
            encoding="utf-8", errors="replace")
        self.assertNotIn("不该提交的东西", proc.stdout,
                         "CLI 把指针/归档目录当成垃圾了 —— 而报错文案会叫 agent 把它们挪走")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    def test_the_cli_follows_the_configured_root(self):
        """面板把产物路径改到别处 ⇒ CLI 必须跟过去（否则 ⑬ 验收时 agent 拿到假 FAIL）。"""
        root = self._workspace()
        elsewhere = root / "别处"
        sub = elsewhere / SUBMISSION_PARENT / SUBMISSION_POINTER
        sub.mkdir(parents=True)
        for n in ("正文.pdf", "附录A.pdf", "运行说明.md", "AI工具使用详情.pdf"):
            (sub / n).write_text("x", encoding="utf-8")
        (root / "config/delivery.local.json").write_text(
            json.dumps({"output_dir": str(elsewhere)}, ensure_ascii=False), encoding="utf-8")

        proc = subprocess.run(
            [sys.executable, "-m", "lib.delivery", "--root", str(root), "check"],
            cwd=str(PROJECT), capture_output=True, text=True,
            encoding="utf-8", errors="replace")
        self.assertEqual(proc.returncode, 0,
                         "CLI 没跟去配置的产物根 —— 报的是别处的「还不存在」假 FAIL：\n"
                         + proc.stdout + proc.stderr)


class RotatePointerTests(unittest.TestCase):
    """两个「最新」指针的落点与轮转原语。

    头一条钉的是数据完整性：`rotate_pointer` 若把「文件被别的进程占用」当成「跨盘」处理，
    会**永久删数据** —— 被占文件之外的源文件全没了，而归档一份也没建成。
    """

    def _pointer(self, root, files=("正文.pdf", "其余文件/正文/main.tex")):
        p = root / SUBMISSION_POINTER
        for rel in files:
            f = p / rel
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(rel, encoding="utf-8")
        return p

    def test_resolvers_point_at_the_two_latest_dirs(self):
        root = Path(tempfile.mkdtemp())
        self.assertEqual(resolve_submission_dir(root),
                         root / "产物" / SUBMISSION_PARENT / SUBMISSION_POINTER)
        self.assertEqual(resolve_stage_dir(root),
                         root / "产物" / "各阶段产物" / "最新产物")
        # 显式给了产物根就不能再落回默认
        other = root / "别处"
        self.assertTrue(str(resolve_submission_dir(root, str(other))).startswith(str(other)))

    def test_empty_or_missing_pointer_is_a_noop(self):
        """首次运行 / 用户手工建的空样板 → 不轮转（否则会产出一堆空档案）。"""
        root = Path(tempfile.mkdtemp())
        self.assertIsNone(rotate_pointer(root / "不存在", root, "2026A_x"))
        (root / SUBMISSION_POINTER).mkdir()
        self.assertIsNone(rotate_pointer(root / SUBMISSION_POINTER, root, "2026A_x"))

    def test_refuses_to_overwrite_an_existing_archive(self):
        root = Path(tempfile.mkdtemp())
        pointer = self._pointer(root)
        (root / "2026A_x").mkdir()
        with self.assertRaises(ValueError):
            rotate_pointer(pointer, root, "2026A_x")
        self.assertTrue((pointer / "正文.pdf").is_file(), "被拒时不该动源")

    def test_a_locked_file_aborts_without_deleting_anything(self):
        """文件被占用 ⇒ **一件都不许少**，也不许留下半份归档。

        误判成「跨盘」会走成这条链：`最新作品/正文.pdf` 被外部进程开着 ⇒ Windows 上整目录
        rename 以 WinError 5 失败 ⇒ 当成跨盘 ⇒ `copytree` 成功（读被占文件是允许的）⇒
        `rmtree(pointer)` 删到被占文件时抛错 ⇒ 外层 `except` 把**完整的副本**清掉 ⇒
        **源里除被占文件外的文件全被永久删除**（`demo.html` 与 `其余文件/正文/main.tex`），
        而归档一份也没建成。
        """
        root = Path(tempfile.mkdtemp())
        pointer = self._pointer(root)
        before = sorted(p.relative_to(pointer).as_posix()
                        for p in pointer.rglob("*") if p.is_file())
        with open(pointer / "正文.pdf", "rb") as held:
            held.read(1)
            with self.assertRaises(OSError):
                rotate_pointer(pointer, root, "2026A_x")

        after = sorted(p.relative_to(pointer).as_posix()
                       for p in pointer.rglob("*") if p.is_file())
        self.assertEqual(after, before, "被占用时源里少了文件 —— 这是永久删数据")
        leftovers = [p.name for p in root.iterdir()
                     if p.name.startswith(".") or p.name == "2026A_x"]
        self.assertEqual(leftovers, [], f"留下了半份归档/临时目录：{leftovers}")

    def test_a_real_cross_device_error_still_falls_back_to_copy(self):
        """对照组：**真**跨盘（errno 18）仍必须退到复制。

        没有这条，占用判定就可能一路收紧成「跨盘直接失败」—— 而跨盘是受支持的用法
        （产物路径可以设到别的盘）。
        """
        root = Path(tempfile.mkdtemp())
        pointer = self._pointer(root)
        real = Path.rename
        calls = []

        def flaky(self_, target):
            calls.append(self_.name)
            if len(calls) == 1:                    # 只让第一次（整目录 rename）失败
                # 用 `errno.EXDEV` 而不是裸 18：判跨盘的那句读的正是这个常量
                #   （`lib/delivery/core.py:195`），两边同源才是"对照组"；换平台这个值不保证还是 18。
                raise OSError(errno.EXDEV, "Invalid cross-device link")
            return real(self_, target)

        with mock.patch.object(Path, "rename", flaky):
            dest = rotate_pointer(pointer, root, "2026A_x")
        self.assertTrue((dest / "正文.pdf").is_file(), "跨盘时该复制过去")
        self.assertTrue((dest / "其余文件/正文/main.tex").is_file())
        self.assertFalse(pointer.exists(), "复制成功后源该删掉")
        self.assertEqual([p.name for p in root.iterdir() if p.name.startswith(".")], [],
                         "不该留下 .copying- 临时目录")

    def test_unique_boundary_name_checks_every_parent(self):
        """必须**同时**查两个 parent：两处归档用同一个名字，才能把「这一题的提交件」
        与「这一题的阶段产物」对起来。各查各的会让两边算出不同的名字。"""
        root = Path(tempfile.mkdtemp())
        sub, stg = root / SUBMISSION_PARENT, root / "各阶段产物"
        (stg / "2026A_1.1_0.0.0").mkdir(parents=True)
        taken = unique_boundary_name([sub, stg], "2026A_1.1_0.0.0")
        # 精确断言：只断 "!=" 的话，一个「永远加 -2」的实现也能过全仓。
        self.assertEqual(taken, "2026A_1.1_0.0.0-2")
        # 没撞名时必须**原样**返回
        self.assertEqual(unique_boundary_name([sub, stg], "2026A_2.2_0.0.0"),
                         "2026A_2.2_0.0.0")

    def test_a_case_only_difference_counts_as_taken(self):
        """Windows 路径大小写不敏感：`2026A_x` 与 `2026a_x` 是**同一个**目录。

        判据若大小写敏感就会以为不撞名而放行 —— 随后 `rotate_pointer` 因「归档目标
        已存在」抛错，把换题/归档**整个中止**。
        """
        root = Path(tempfile.mkdtemp())
        (root / SUBMISSION_PARENT / "2026A_x").mkdir(parents=True)
        self.assertEqual(unique_boundary_name([root / SUBMISSION_PARENT], "2026a_x"),
                         "2026a_x-2", "大小写不同也算撞名 —— 该退到 -2")


class BodyPdfNamingTests(unittest.TestCase):
    """提交件里**正文 PDF 用论文标题命名**（对齐参考稿）。

    参考稿的正文叫 `基于变物性耦合传热传质与动域模型的.pdf`，而本项目的打包固定叫 `正文.pdf`
    ⇒ 对不上。工作区里那份仍叫 `paper/main.pdf`（所有阶段都按这个名字找它），**只在打包时改名**。
    名字从 `paper/main.tex` 的 `\\papertitle{}` 推导 —— 所以下面既钉"取得到"，也钉"取不到时的回落"
    （回落不能把老清单搞挂：打包名以清单声明的 path 为准，两种名字都映到同一个源）。
    """

    def _root(self, title=None):
        root = Path(tempfile.mkdtemp())
        (root / "paper").mkdir(parents=True)
        (root / "paper/main.pdf").write_bytes(b"%PDF-1.4\n" + b"x" * 40)
        tex = "%!TEX program = xelatex\n"
        if title is not None:
            tex += f"\\papertitle{{{title}}}\n"
        (root / "paper/main.tex").write_text(tex, encoding="utf-8")
        return root

    def test_the_name_comes_from_the_paper_title(self):
        root = self._root("圆柱形药材热风烘干过程的耦合传热传质模型与数值求解")
        name = body_pdf_name(root)
        self.assertEqual(name, "圆柱形药材热风烘干过程的耦合传热传质模型与数值求解.pdf")
        self.assertEqual(resolve_source(root, name), "paper/main.pdf",
                         "标题名必须映到工作区那唯一一份 main.pdf")

    def test_reserved_characters_are_stripped(self):
        """**ASCII** 保留字符进不了 Windows 文件名，必须清掉（题目标识那条同款纪律）。

        全角 `：？` 是**合法**字符、**不清** —— 这条钉的就是这个分界。本项目这道题的标题
        `圆柱形药材热风烘干过程的耦合传热传质模型与数值求解` 本来就没有标点，所以不受影响。
        """
        self.assertEqual(body_pdf_name(self._root('A题: 烘干?"问题"')), "A题 烘干问题.pdf")
        self.assertEqual(body_pdf_name(self._root("A题：烘干问题？")), "A题：烘干问题？.pdf",
                         "全角标点是合法字符，不许清")

    def test_falls_back_to_the_legacy_name(self):
        """取不到标题（老工作区/没有 main.tex）⇒ 回落 `正文.pdf`，且**老名字照样能打包**。"""
        for root in (self._root(None), Path(tempfile.mkdtemp())):
            self.assertEqual(body_pdf_name(root), BODY_PDF)
            self.assertEqual(resolve_source(root, BODY_PDF), "paper/main.pdf")

    def test_structure_title_wins_over_legacy_papertitle(self):
        """P1：structure.json 是角色化工作区的权威；main.tex 退居 legacy。"""
        root = self._root("旧标题")
        (root / "paper/structure.json").write_text(
            json.dumps({"schema_version": 1, "title": "新标题"}, ensure_ascii=False),
            encoding="utf-8")
        self.assertEqual(body_pdf_name(root), "新标题.pdf")

    def test_structure_placeholder_falls_back_to_title_block(self):
        root = self._root("旧标题")
        (root / "paper/blocks").mkdir()
        (root / "paper/blocks/title.tex").write_text(r"\papertitle{块标题}" + "\n", encoding="utf-8")
        (root / "paper/structure.json").write_text(
            json.dumps({"schema_version": 1, "title": "<论文标题>"}, ensure_ascii=False),
            encoding="utf-8")
        self.assertEqual(body_pdf_name(root), "块标题.pdf")

    def test_bad_structure_falls_back_without_crashing(self):
        root = self._root("旧标题")
        (root / "paper/structure.json").write_text("{bad json", encoding="utf-8")
        self.assertEqual(body_pdf_name(root), "旧标题.pdf")


class NestedAttachmentTests(unittest.TestCase):
    """题目附件常有子目录 —— 这道题的 `request/attachments/附件3/` 就是（4 个模板 xlsx）。

    `provisional_items` 只 `iterdir()` 看顶层、`resolve_source` 只按平铺名找的话，那些文件
    **一件都进不了提交包**，而且不报错（静默漏），交付出去就是"附件不全"。
    """

    def setUp(self):
        self.root = make_workspace()
        self.addCleanup(shutil.rmtree, self.root, True)
        self.out = self.root / "产物"

    def _nested(self, *rels):
        for rel in rels:
            p = self.root / "request/attachments" / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(rel, encoding="utf-8")

    def test_nested_attachments_reach_the_submission_package(self):
        self._nested("附件3/result1.xlsx", "附件3/说明.txt")
        items = provisional_items(self.root)
        srcs = {i["source"] for i in items}
        self.assertIn("request/attachments/附件3/result1.xlsx", srcs,
                      f"嵌套附件没进提交项：{[i['path'] for i in items]}")
        package(self.root, self.out, items)
        for i in items:
            if i["source"].startswith("request/attachments/附件3/"):
                self.assertTrue((self.out / i["path"]).is_file(),
                                f"{i['path']} 没落进提交件（源 {i['source']}）")

    def test_two_same_named_files_do_not_overwrite_each_other(self):
        """④ 算出来的 `results/result1.xlsx` 与附件模板 `附件3/result1.xlsx` 不许互相盖。"""
        self._nested("附件3/result1.xlsx")
        items = provisional_items(self.root)
        names = [i["path"] for i in items]
        self.assertEqual(len(names), len(set(names)), f"提交名撞了：{names}")
        package(self.root, self.out, items)
        self.assertTrue((self.out / "result1.xlsx").is_file(), "④ 的结果表不在")
        self.assertTrue((self.out / "附件3_result1.xlsx").is_file(),
                        "附件模板没换个名字落进来（会和结果表互相覆盖）")

    def test_resolve_source_prefers_a_unique_recursive_hit(self):
        self._nested("附件3/独一份.xlsx")
        self.assertEqual(resolve_source(self.root, "独一份.xlsx"),
                         "request/attachments/附件3/独一份.xlsx")

    def test_resolve_source_refuses_to_guess_between_two_matches(self):
        """两处同名 ⇒ 响亮失败并列出候选 —— 静默挑一个会让提交包装错文件且没人看得出来。"""
        self._nested("附件3/重名.xlsx", "附件4/重名.xlsx")
        with self.assertRaises(ValueError) as cm:
            resolve_source(self.root, "重名.xlsx")
        self.assertIn("2 处同名", str(cm.exception))

    def test_zero_matches_still_falls_back_to_the_name(self):
        """0 命中照旧返回原名：那是"清单里写了、工作区没有"，由调用方报缺失（不是异常）。"""
        self.assertEqual(resolve_source(self.root, "根本没有.xlsx"), "根本没有.xlsx")

    # ---- 附件完备性判据（`checks._missing_attachments`）----

    def _manifest_with(self, extra=None, exclude=None):
        items = load_manifest(self.root)
        items += (extra or [])
        spec = {"schema_version": 1, "items": items}
        if exclude is not None:
            spec["exclude"] = exclude
        (self.root / "reports").mkdir(parents=True, exist_ok=True)
        (self.root / "reports/SUBMISSION_MANIFEST.json").write_text(
            json.dumps(spec, ensure_ascii=False), encoding="utf-8")
        return items

    def test_a_nested_attachment_that_never_made_it_in_is_reported(self):
        """静默漏附件的那种情形：盘上有、清单里没有 —— 必须报出来。"""
        self._nested("附件3/漏掉的.xlsx")
        package(self.root, self.out, self._manifest_with())
        issues = check(self.root, self.out)
        hit = [i for i in issues if "题目附件" in i and "漏掉的" in i]
        self.assertTrue(hit, f"嵌套附件漏了却没报：{issues}")

    def test_declaring_it_in_exclude_silences_the_warning(self):
        """`exclude` 让「刻意不提交这份」成为**显式声明**，而不是沉默。"""
        self._nested("附件3/不交的.xlsx")
        package(self.root, self.out, self._manifest_with(
            exclude=[{"path": "request/attachments/附件3/不交的.xlsx", "why": "临时中间文件"}]))
        issues = check(self.root, self.out)
        self.assertFalse([i for i in issues if "不交的" in i], f"声明了还报：{issues}")

    def test_the_problem_statement_itself_is_not_an_attachment(self):
        """误报防线：`request/problem.md` 是链的**输入**，不是"题目附件" —— 不许因此报错。

        这条钉住判据的**范围**（只查 `request/attachments/**` 与 `data/**`）。范围写宽了
        每次都会对着题面误报，验收就成了狼来了 —— 而那比不查更糟。
        """
        (self.root / "request/problem.md").write_text("题面", encoding="utf-8")
        (self.root / "request/problem.pdf").write_bytes(b"%PDF-1.4")
        package(self.root, self.out, self._manifest_with())
        issues = check(self.root, self.out)
        self.assertFalse([i for i in issues if "problem" in i], f"对题面误报了：{issues}")

    def test_a_malformed_exclude_is_an_error_not_silently_ignored(self):
        """`exclude` 写了但结构不对 ⇒ 报错。静默忽略一条声明比拒绝它更危险。"""
        package(self.root, self.out, self._manifest_with(exclude=[{"why": "忘了写 path"}]))
        issues = check(self.root, self.out)
        self.assertTrue([i for i in issues if "exclude" in i], f"没报结构错：{issues}")


if __name__ == "__main__":
    unittest.main()
