# -*- coding: utf-8 -*-
"""⑯ 的 demo 整段进附录最前面（标题 + 图 A1 + 介绍）—— 纯离线，不碰真仓库。

盯三件事：**整段在 A.x 之前**（图不能劈开 A.1 的标题与正文）、
**编号顺延要对**（含行文里的按号指路）、**跑第二遍结果不变**（⑯ 可能重跑）。

目标形状（对着参考件 `最终拆分/其余文件/附录/main.pdf` 第 1 页核）：
      demo 交互式网页与工程实现展示        ← 与 A.x 同级的小节标题
      图A1：药材烘干交互式网页截图
      页面把论文的建模链路（…）整条做成了可交互的形态…
      A.1 问题一、二的误差与守恒汇总       ← 原有小节跟在后面

小节标题不要带全角括号后缀「（展示）」；标题文案以 `adf.DEMO_HEADING` 为准。
"""
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib" / "web"))
import appendix_demo_figure as adf  # noqa: E402

INTRO = ("页面把本文的建模链路整条做成了可交互的形态。\n"
         "方法贯通可视化：同一套离散、四条命题、逐问差异只在物性表与几何是否随动。\n"
         "工程可用性：单个离线 HTML，双击即用。")

# 两份图 + 两处行文按号指路 + 一张表（表号是另一套，不许被图号的顺延碰到）
FIXTURE = """\\subsection*{A.1\\quad 命题的完整推导与前提的数值验证}

正文给出的命题把全场最坏值归约到轴心。三条前提的实测值见表 A1。

\\subsection*{A.2\\quad 收敛性与守恒校核}

\\appfigure[\\textwidth]{convergence}{图 A1：达标时刻对空间网格与时间步长的收敛}

图 A1 是两条独立的扫描，每减半约降一半，即一阶收敛。

\\appfigure[\\textwidth]{q1_profiles}{图 A2：问题一的温度与水分浓度剖面族}

图 A2 把表 2 与表 3 的七个时刻画成剖面族，数值即交付结果文件的同名格点值。
"""


class DemoSectionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        sec = self.tmp / "paper_appendix" / "sections"
        sec.mkdir(parents=True)
        self.tex = sec / "A_appendix.tex"
        self.tex.write_text(FIXTURE, encoding="utf-8")
        self.png = self.tmp / "shot_1_default.png"
        import fitz
        fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 8, 8)).save(str(self.png))

    def run_it(self, intro=INTRO):
        return adf.ensure_demo_figure(self.tmp, self.png, intro)

    def lines(self):
        return self.tex.read_text(encoding="utf-8").split("\n")

    def numbers(self):
        """文件里出现过的所有图号（图题 + 行文指路）。"""
        return sorted(int(m.group(1)) for m in
                      adf.FIG_LABEL_RE.finditer(self.tex.read_text(encoding="utf-8")))

    # ---- ① 整段必须在 A.x 之前，且不劈开 A.1 ----

    def test_the_demo_section_sits_before_every_a_x_section(self):
        self.run_it()
        lines = self.lines()
        subs = [i for i, l in enumerate(lines) if l.startswith("\\subsection*")]
        self.assertTrue(subs, "一个小节都没有？")
        self.assertIn(adf.DEMO_HEADING, lines[subs[0]],
                      "第一行小节标题必须是 demo 那一段（参考件就是它打头）")
        self.assertIn("A.1", lines[subs[1]], "A.1 必须紧跟在 demo 段之后")

    def test_the_figure_does_not_split_a1_from_its_own_body(self):
        """图不许挤在 `\\subsection*{A.1…}` 与它自己的正文之间 —— 那等于把 A.1 的正文劈开。"""
        self.run_it()
        lines = self.lines()
        i = next(i for i, l in enumerate(lines) if l.startswith("\\subsection*{A.1"))
        nxt = next(l for l in lines[i + 1:] if l.strip())
        self.assertFalse(nxt.startswith("\\appfigure"),
                         f"A.1 的标题下面紧跟着一张图，正文被劈开了：{nxt!r}")

    def test_heading_then_figure_then_intro_in_that_order(self):
        self.run_it()
        t = self.tex.read_text(encoding="utf-8")
        i_head = t.index(adf.DEMO_HEADING)
        i_fig = t.index(f"{{图 A1：{adf.DEMO_CAPTION}}}")
        i_intro = t.index("页面把本文的建模链路")
        self.assertLess(i_head, i_fig, "标题要在图上面")
        self.assertLess(i_fig, i_intro, "介绍要在图下面")
        self.assertIn("工程可用性", t, "介绍没写进去")

    def test_the_block_is_delimited_so_it_can_be_replaced_wholesale(self):
        self.run_it()
        t = self.tex.read_text(encoding="utf-8")
        self.assertEqual(t.count(adf.BLOCK_BEGIN), 1)
        self.assertEqual(t.count(adf.BLOCK_END), 1)
        self.assertLess(t.index(adf.BLOCK_BEGIN), t.index(adf.BLOCK_END))

    # ---- ② 编号顺延 ----

    def test_every_old_figure_number_shifts_by_one(self):
        self.run_it()
        # demo 占 A1，后面两张顺延成 A2/A3 —— 图题与行文指路**都要**跟着走。
        # 1=demo 图题；2=原 A1 的图题+指路句；3=原 A2 的图题+指路句。
        self.assertEqual(self.numbers(), [1, 2, 2, 3, 3], self.tex.read_text(encoding="utf-8"))
        t = self.tex.read_text(encoding="utf-8")
        self.assertIn("图 A2 是两条独立的扫描", t)
        self.assertIn("图 A3 把表 2 与表 3", t)

    def test_the_table_numbers_are_a_separate_namespace(self):
        self.run_it()
        self.assertEqual(len(re.findall(r"表\s*A\d+", self.tex.read_text(encoding="utf-8"))), 1)

    # ---- ③ 幂等 / 迁移 / 边界 ----

    def test_running_twice_changes_nothing(self):
        """⑯ 会重跑：第二次必须**不**再插一段、也不把号再顺延一遍。"""
        self.run_it()
        once = self.tex.read_bytes()
        second = self.run_it()
        self.assertEqual(second["dropped"], 1, "第二次应当整段摘掉再插，而不是又插一段")
        self.assertEqual(self.tex.read_bytes(), once)
        self.assertEqual(once.decode("utf-8").count(adf.DEMO_HEADING), 1,
                         "标题只该出现一次 —— 只摘图不摘标题就会攒出第二份")

    def test_it_upgrades_a_v1_appendix_that_only_had_a_bare_figure(self):
        """兼容没有界标、图还插在 A.1 标题之后的旧附录：也要整段归位。"""
        v1 = FIXTURE.replace("正文给出的命题把全场最坏值归约到轴心。",
                             "\\appfigure[\\textwidth]{demo_shot}{图 A1：交互式网页首屏}\n\n"
                             "正文给出的命题把全场最坏值归约到轴心。", 1)
        self.tex.write_text(v1, encoding="utf-8")
        self.run_it()
        t = self.tex.read_text(encoding="utf-8")
        self.assertEqual(t.count(adf.DEMO_HEADING), 1)
        self.assertEqual(t.count("demo_shot"), 1, "旧的裸图行必须被摘掉，不能留成孤儿")
        # 而且位置要挪对：A.1 标题下紧跟着的是正文，不是那张图
        lines = t.split("\n")
        i = next(i for i, l in enumerate(lines) if l.startswith("\\subsection*{A.1"))
        self.assertFalse(next(l for l in lines[i + 1:] if l.strip()).startswith("\\appfigure"))

    def test_an_empty_intro_is_an_error_not_a_silent_bare_figure(self):
        """只放一张光图、没有介绍，不许静默退化 —— 那等于交付一张没有说明的截图。"""
        with self.assertRaises(ValueError):
            self.run_it(intro="   \n  ")

    def test_a_bare_percent_in_the_intro_is_escaped(self):
        """中文散文里「完成度 100%」很常见，而 `%` 会把整行**静默**注释掉。"""
        self.run_it(intro="达标完成度 100% 时提示。")
        t = self.tex.read_text(encoding="utf-8")
        self.assertIn("100\\%", t)
        self.assertRegex(t, r"100\\% 时提示。")

    def test_the_figure_file_lands_in_the_appendix_figures_dir(self):
        self.run_it()
        figdir = self.tmp / "paper_appendix" / "figures"
        self.assertTrue((figdir / f"{adf.DEMO_FIGURE_ID}.pdf").is_file(), "LaTeX 读的是 .pdf")
        self.assertTrue((figdir / f"{adf.DEMO_FIGURE_ID}.png").is_file(), "原始截图留档")

    def test_an_appendix_without_any_subsection_still_gets_the_block(self):
        self.tex.write_text("正文，一个小节都没有。\n", encoding="utf-8")
        self.run_it()
        t = self.tex.read_text(encoding="utf-8")
        self.assertIn(adf.DEMO_HEADING, t)
        self.assertIn("正文，一个小节都没有。", t, "原有内容不许丢")

    def test_a_missing_screenshot_is_an_error_not_a_silent_skip(self):
        self.png.unlink()
        with self.assertRaises(FileNotFoundError):
            self.run_it()


if __name__ == "__main__":
    unittest.main()
