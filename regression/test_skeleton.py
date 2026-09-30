# -*- coding: utf-8 -*-
"""骨架对账：正文小节的标题必须还是模板给定的那一套。

模板 `sections/*.tex` 的 `\\subsection{}`/`\\subsubsection{}` 是**给定的骨架**，但约束
只写在 LaTeX 注释里，没有任何东西强制它 —— 写手容易把它当"参考"自行重排（问题分析丢了
「本文主要创新点」、模型建立与求解前面插了两节把 5.1 挤走、检验与分析两节改名、
评价与推广多了「结论汇总」、模型假设每条写到 177–322 字）。这些用例把那五处形状各取一个。

纯离线：造一份最小模板 + 一份正文，直接调 `lib/web/check_skeleton.py`。
"""
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "lib" / "web"))
import check_skeleton as cs  # noqa: E402

# 符号表：**三列「符号 / 含义 / 单位」，单位单独成列**（要求的形制，
# 参考件 `基于变物性耦合传热传质与动域模型的.pdf` 即此形制）。下面是合规的那一份。
SPEC3 = "@{}L{0.19\\textwidth}C{0.57\\textwidth}R{0.19\\textwidth}@{}"
INTRO = ("\\section{模型假设}\n"
         "\\noindent 为了适当地对模型进行合理简化，本文给出如下假设：\n")

SYMBOLS_OK = ("\\section{符号说明}\n"
              "\\begin{longtable}{" + SPEC3 + "}\n"
              "\\toprule\n符号 & 含义 & 单位 \\\\\n\\midrule\n"
              "$\\rho$ & 湿基密度 & kg/m$^3$ \\\\\n"
              "$\\xi$ & 径向物理坐标（$\\xi = r/R(t)$） & m \\\\\n"
              "$Bi$ & 传热 Biot 数 & 无量纲 \\\\\n"
              "\\end{longtable}\n")

# 最小骨架：两个节文件，一个带选加小节、一个用于 5_problemN 的展开
SKEL = {
    # 图 1（分析流程图）排在问题重述之后、问题分析之前，整栏 —— 见 `_roadmap_placement_problems`
    "1_restatement.tex": "\\section{问题重述}\n\\subsection{问题背景}\n"
                         "\\subsection{问题提出}\n"
                         "\\paperfigure[0.85\\textwidth]{fig_roadmap}{分析流程图}{fig_roadmap}\n",
    "2_analysis.tex": "\\section{问题分析}\n"
                      "\\subsection{问题一的分析}\n\\subsection{本文主要创新点}\n",
    "5_problem1.tex": "\\section{模型的建立与求解}\n"
                      "\\subsection{问题一的模型的建立和求解}\n"
                      "\\subsubsection{具体分析}\n\\subsubsection{模型建立}\n",
    "3_assumptions.tex": "\\section{模型假设}\n"
                         "\\noindent 为了适当地对模型进行合理简化，本文给出如下假设：\n"
                         "\\begin{enumerate}[label=\\textbf{假设\\chinese{enumi}：}]\n"
                         "  \\item 甲。放宽影响：一。\n"
                         "  \\item 乙。放宽影响：二。\n"
                         "  \\item 丙。放宽影响：三。\n\\end{enumerate}\n",
    "3_symbols.tex": SYMBOLS_OK,
}


def tbl(num, spec="cccccc", nrows=3):
    """造一个**独立**的 table 浮动体：标题里带表号 `num`，列格式 `spec`，nrows 行数据。"""
    body = "".join(f"      {i} & a & b & c & d & e \\\\\n" for i in range(nrows))
    return (f"\\begin{{table}}[htbp]\n  \\centering\n"
            f"  {{\\bfseries 表 {num}\\quad 标题{num}}}\n"
            f"  \\begin{{tabular}}{{{spec}}}\n    \\toprule\n"
            f"    时间/s & 0 & 1 & 2 & 3 & 4 \\\\\n    \\midrule\n"
            f"{body}    \\bottomrule\n  \\end{{tabular}}\n\\end{{table}}\n")


def analysis(n):
    """造一份 `2_analysis.tex`：n 节「问题N的分析」+ 创新点（子问题数由题面定）。"""
    cn = "一二三四五六七八九十"
    body = "".join(f"\\subsection{{问题{cn[i]}的分析}}\n" for i in range(n))
    return "\\section{问题分析}\n" + body + "\\subsection{本文主要创新点}\n"


def symbols(rows, spec=SPEC3, header="符号 & 含义 & 单位"):
    """造一份符号表：`rows` 是若干行的原文（不带结尾的 `\\\\`）。"""
    body = "".join(f"    {r} \\\\\n" for r in rows)
    return ("\\section{符号说明}\n\\begin{longtable}{" + spec + "}\n"
            "\\toprule\n" + header + " \\\\\n\\midrule\n" + body + "\\end{longtable}\n")


class SkeletonTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        tpl = self.tmp / cs.TEMPLATES_REL / "zh" / "fam" / "sections"
        tpl.mkdir(parents=True)
        (tpl.parent / "main.tex").write_text("\\input{sections/2_analysis}\n", encoding="utf-8")
        for name, text in SKEL.items():
            (tpl / name).write_text(text, encoding="utf-8")
        self.paper = self.tmp / cs.PAPER_SECTIONS_REL
        self.paper.mkdir(parents=True)
        for name, text in SKEL.items():          # 起点：与骨架完全一致
            (self.paper / name).write_text(text, encoding="utf-8")

    def write(self, name, text):
        (self.paper / name).write_text(text, encoding="utf-8")

    def check(self):
        return cs.skeleton_issues(self.tmp)

    # ---- 通过基线 ----

    def test_a_paper_that_matches_the_skeleton_passes(self):
        self.assertEqual(self.check(), [])

    def test_body_text_under_a_heading_is_not_a_new_heading(self):
        """往骨架的小节里**填正文**不算改结构 —— 这正是该做的。

        创新点那条要写到下限（3 行 ≈114 字）以上，否则它会因为"太短"被报 —— 那是另一条规则，
        会把这条用例想验的东西（填正文不改结构）淹掉。
        """
        self.write("2_analysis.tex", "\\section{问题分析}\n"
                                     "几句总结性话语。\n"
                                     "\\subsection{问题一的分析}\n"
                                     "这里是一大段分析，含 \\textbf{粗体} 与 $x^2$。\n"
                                     "\\subsection{本文主要创新点}\n"
                                     "\\textbf{创新点一：}做了什么，带来什么实质改进。常规做法是把两个场"
                                     "联立迭代，每一步都要来回扫几遍；本文先判定其中一个场自封闭，"
                                     "于是拆成先后两步走，外层那层迭代整个省掉，单次推进的代价也随之"
                                     "降下来。实测在这一档参数下把某量从一万多降到几百，误差仍在同一个"
                                     "量级内，口径与对照见第五节的表。\n")
        self.assertEqual(self.check(), [])

    # ---- 五处典型形状，各一个 ----

    def test_a_renamed_subsection_is_reported(self):
        """二、问题分析：丢了「本文主要创新点」，换成自有一节。"""
        self.write("2_analysis.tex", "\\section{问题分析}\n"
                                     "\\subsection{问题一的分析}\n"
                                     "\\subsection{求解方案的总体考虑}\n")
        probs = self.check()
        self.assertTrue(any("缺" in p and "本文主要创新点" in p for p in probs), probs)
        self.assertTrue(any("多出" in p and "求解方案的总体考虑" in p for p in probs), probs)

    def test_a_heading_inserted_before_the_required_one_is_reported(self):
        """五、在骨架节前面插「四问共用…」两节，把问题一挤走。"""
        self.write("5_problem1.tex", "\\section{模型的建立与求解}\n"
                                     "\\subsection{四问共用的模型框架}\n"
                                     "\\subsubsection{控制方程}\n"
                                     "\\subsection{问题一的模型的建立和求解}\n"
                                     "\\subsubsection{具体分析}\n\\subsubsection{模型建立}\n")
        probs = self.check()
        self.assertTrue(any("四问共用的模型框架" in p and "多出" in p for p in probs), probs)
        self.assertTrue(any("控制方程" in p and "多出" in p for p in probs), probs)

    def test_reordering_is_reported_as_order_not_as_missing(self):
        self.write("2_analysis.tex", "\\section{问题分析}\n"
                                     "\\subsection{本文主要创新点}\n"
                                     "\\subsection{问题一的分析}\n")
        probs = self.check()
        self.assertTrue(any("顺序" in p for p in probs), probs)
        self.assertFalse(any("缺" in p for p in probs), probs)

    def test_an_extra_file_is_reported(self):
        self.write("9_bonus.tex", "\\section{额外一章}\n")
        self.assertTrue(any("多出文件" in p and "9_bonus" in p for p in self.check()))

    # ---- 放宽的两处（别误报） ----

    def test_a_fourth_problem_file_is_allowed_even_if_the_skeleton_has_three(self):
        """模板注释：「题目不止三问时按同样的命名往后加 5_problem4…」。不许当多出。"""
        self.write("5_problem4.tex", "\\section{模型的建立与求解}\n"
                                     "\\subsection{问题四的模型的建立和求解}\n"
                                     "\\subsubsection{具体分析}\n\\subsubsection{模型建立}\n")
        # 四问就得有四节分析 —— 分析节跟着子问题数走，不是固定三节
        self.write("2_analysis.tex", analysis(4))
        self.assertEqual(self.check(), [])

    # ---- 问题分析的节数 = 子问题数（模板里的三节只是举例） ----

    def test_a_fourth_analysis_section_is_not_reported_as_extra(self):
        """写到「问题四的分析」不该被判「多出骨架里没有的标题」。"""
        self.write("5_problem4.tex", "\\section{模型的建立与求解}\n"
                                     "\\subsection{问题四的模型的建立和求解}\n"
                                     "\\subsubsection{具体分析}\n\\subsubsection{模型建立}\n")
        self.write("2_analysis.tex", analysis(4))
        probs = self.check()
        self.assertFalse(any("多出" in p and "问题" in p for p in probs), probs)

    def test_a_missing_question_analysis_is_reported(self):
        """题面四问、正文只写到「问题三的分析」时，问题四整节漏掉必须报出来。

        骨架两边都是三节，逐条比对看不出问题 —— 靠子问题数才抓得住。
        """
        self.write("5_problem4.tex", "\\section{模型的建立与求解}\n"
                                     "\\subsection{问题四的模型的建立和求解}\n"
                                     "\\subsubsection{具体分析}\n\\subsubsection{模型建立}\n")
        probs = self.check()
        self.assertTrue(any("问题四 的分析" in p for p in probs), probs)

    def test_the_analysis_count_may_be_three_when_there_are_three_questions(self):
        self.assertEqual(cs._question_count_problems(self.tmp), [])

    def test_the_analysis_count_may_be_five(self):
        for n in (4, 5):
            self.write(f"5_problem{n}.tex",
                       f"\\section{{模型的建立与求解}}\n"
                       f"\\subsection{{问题{'四五'[n - 4]}的模型的建立和求解}}\n"
                       f"\\subsubsection{{具体分析}}\n\\subsubsection{{模型建立}}\n")
        self.write("2_analysis.tex", analysis(5))
        self.assertEqual(cs._question_count_problems(self.tmp), [])

    def test_the_optional_result_subsection_may_appear_or_not(self):
        """模板写的是「(选加5.x.5 结果分析)」—— 出现或不出现都不该报。"""
        self.write("5_problem1.tex", "\\section{模型的建立与求解}\n"
                                     "\\subsection{问题一的模型的建立和求解}\n"
                                     "\\subsubsection{具体分析}\n\\subsubsection{模型建立}\n"
                                     "\\subsubsection{结果分析}\n")
        self.assertEqual(self.check(), [])

    # ---- 模型假设：条数 3–6、每条不长 ----

    def test_an_overlong_assumption_is_reported(self):
        """一条 322 字的假设必须报出来。参考件 `框架模板.pdf` 是 40–70 字。"""
        long_item = "药材视为无限长圆柱，" + "因为题面给定的长度远大于半径，" * 20
        self.write("3_assumptions.tex", INTRO + "\\begin{enumerate}[label=\\textbf{假设\\chinese{enumi}：}]\n"
                                        f"  \\item {long_item}\n"
                                        "  \\item 乙。放宽影响：二。\n"
                                        "  \\item 丙。放宽影响：三。\n\\end{enumerate}\n")
        self.assertTrue(any("每条不长" in p for p in self.check()))

    def test_too_many_assumptions_are_reported(self):
        """模型假设**最多 5 条**：写到第 6 条必须报出上限。"""
        items = "".join(f"  \\item 第{i}条。放宽影响：{i}。\n" for i in range(1, 7))
        self.write("3_assumptions.tex", INTRO + "\\begin{enumerate}[label=\\textbf{假设\\chinese{enumi}：}]\n" + items + "\\end{enumerate}\n")
        self.assertTrue(any("3–5 条" in p for p in self.check()),
                        f"6 条应当报「最多 5 条」，实际 {self.check()}")

    def test_a_missing_intro_sentence_is_reported(self):
        """标题下必须先写「为了适当地对模型进行合理简化，本文给出如下假设：」再出列表。"""
        self.write("3_assumptions.tex", "\\section{模型假设}\n\\begin{enumerate}\n"
                                        "  \\item 甲。放宽影响：一。\n\\end{enumerate}\n")
        self.assertTrue(any("引入语" in p for p in self.check()),
                        f"缺引入语应当被报出，实际 {self.check()}")

    def test_the_symbols_section_must_not_open_with_a_summary_paragraph(self):
        """符号说明标题下**直接出表**：不许写「除特别说明外，温度用摄氏度…」这类总述段。"""
        self.write("3_symbols.tex", SYMBOLS_OK.replace(
            "\\begin{longtable}",
            "除特别说明外，温度用摄氏度（物性经验式在求值处换算为开尔文），长度用米，"
            "结果文件的时间列用秒；论文表格的时间列按表头注明用秒或小时。各问共用同一套符号"
            "与同一套单位，全文所用符号的含义与单位汇总于表 1。\n\\begin{longtable}", 1))
        self.assertTrue(any("开头总述" in p for p in self.check()),
                        f"总述段应当被报出，实际 {self.check()}")

    # ---- 符号表：三列、单位单独成列 ----
    #
    # 写成两列 `\textbf{符号} & \textbf{含义（单位）}`、把单位塞进含义的括号里，
    # 与参考件 `基于变物性耦合传热传质与动域模型的.pdf` 的三列形制不符。
    # 下面把「对/两列/塞括号/列头不对/单位留空」各钉一个用例。

    def test_a_three_column_symbol_table_passes(self):
        self.write("3_symbols.tex", SYMBOLS_OK)
        self.assertEqual(self.check(), [])

    def test_a_two_column_symbol_table_is_reported(self):
        """`p{0.17\\textwidth}p{0.73\\textwidth}` 加
        `\\textbf{符号} & \\textbf{含义（单位）}` —— 单位没有自己的列，必须报。"""
        self.write("3_symbols.tex", symbols(
            ["$\\rho$ & 湿基密度（kg/m$^3$）"],
            spec="p{0.17\\textwidth}p{0.73\\textwidth}", header="符号 & 含义（单位）"))
        probs = self.check()
        self.assertTrue(any("2 列" in p for p in probs), probs)

    def test_a_header_that_does_not_match_the_column_spec_is_reported(self):
        self.write("3_symbols.tex", symbols(["$\\rho$ & 湿基密度 & kg/m$^3$"],
                                            header="符号 & 含义"))
        self.assertTrue(any("对不上" in p for p in self.check()))

    def test_a_unit_in_the_meaning_parens_is_reported_even_in_three_columns(self):
        """列数对了，但单位还塞在含义的括号里 —— 同样要报。"""
        self.write("3_symbols.tex", symbols(["$\\rho$ & 湿基密度（kg/m$^3$） & "]))
        self.assertTrue(any("写进了含义列的括号里" in p for p in self.check()))

    def test_a_unit_column_left_empty_is_reported(self):
        self.write("3_symbols.tex", symbols(["$\\rho$ & 湿基密度 & "]))
        self.assertTrue(any("单位列为空" in p for p in self.check()))

    def test_dimensionless_must_be_written_out_not_left_blank(self):
        self.write("3_symbols.tex", symbols(["$Bi$ & 传热 Biot 数 & 无量纲"]))
        self.assertEqual(self.check(), [])

    def test_a_meaning_paren_that_is_not_a_unit_is_not_reported(self):
        """`（$\\xi = r/R(t)$）` 是含义的一部分，不是单位 —— 不许误报。"""
        self.write("3_symbols.tex", symbols(["$\\xi$ & 径向物理坐标（$\\xi = r/R(t)$） & m"]))
        self.assertEqual(self.check(), [])

    def test_a_third_header_that_is_not_the_unit_column_is_reported(self):
        self.write("3_symbols.tex", symbols(["$\\rho$ & 湿基密度 & kg/m$^3$"],
                                            header="符号 & 含义 & 备注"))
        self.assertTrue(any("列头" in p for p in self.check()))

    def test_a_third_header_naming_the_unit_among_others_is_accepted(self):
        """`单位/取值` 仍是**单位自己那一列** —— 只在列数上计较，不在列名上吹毛求疵。"""
        self.write("3_symbols.tex", symbols(["$\\rho$ & 湿基密度 & kg/m$^3$"],
                                            header="符号 & 含义 & 单位/取值"))
        self.assertEqual(self.check(), [])

    def test_a_symbols_problem_is_reported_even_when_the_skeleton_matches(self):
        """骨架对得上时也要报符号表问题 —— 不能因为标题对了就整体放行。"""
        self.write("3_symbols.tex", symbols(["$\\rho$ & 湿基密度（kg/m$^3$） & "]))
        probs = self.check()
        self.assertTrue(any("写进了含义列的括号里" in p for p in probs), probs)
        self.assertFalse(any("对不上" in p for p in probs), probs)   # 骨架是好消息，不该报

    def test_the_reference_papers_rows_pass(self):
        """参考件 `基于变物性…动域模型的.pdf` 的原样几行 —— 检查器不得比参考件更严。"""
        self.write("3_symbols.tex", symbols([
            r"$r,\ \xi$      & 径向物理坐标；材料坐标 $\xi = r/R(t)$ & m；无量纲",
            r"$t,\ t_s$      & 时间；预热段与恒温段的切换时刻 & s；s",
            r"$T,\ T_\infty$ & 药材温度、烘房温度 & $^\circ$C",
            r"$C_0$          & 初始干基含水率，$C_0=2.55$ & kg/kg",
            r"$C_{lo}$       & 环境含湿量的下确界，$C_{lo}=\inf_{t\ge0}C_\infty(t)$ & kg/kg",
            r"$c_p,\ k$      & 比热容、热传导系数 & J/(kg$\cdot$K)、W/(m$\cdot$K)",
            r"$\mu_1,\ \lambda_1$ & Robin 特征方程 $\mu J_1(\mu)=Bi_mJ_0(\mu)$ 的首个正根"
            r" & 无量纲；m$^{-2}$",
            r"$\varepsilon_C$ & 扩散系数求值前的含水率下限保护 & kg/kg",
        ]))
        self.assertEqual(self.check(), [])

    def test_the_plain_p_column_spec_is_counted_correctly(self):
        """列型换成 `p{}` 也要数对（老写法，三列仍算合规）。"""
        self.write("3_symbols.tex", symbols(["$\\rho$ & 湿基密度 & kg/m$^3$"],
                                            spec="p{2.8cm}p{9.2cm}p{2.4cm}"))
        self.assertEqual(self.check(), [])

    # ---- 同构的两张表要并排 ----
    #
    # 判据照参考件 `基于变物性耦合传热传质与动域模型的.pdf` 反推：**列格式与数据行数
    # 完全相同**的两张表（表 2/表 3 温度与水分浓度、表 4/表 5 同）并排放在同一个 table
    # 浮动体里（两个 minipage 各占半栏）；而列格式不同的（表 6/表 7、表 8/表 9）分开排。
    # 生成稿若把 4 对全拆成独立浮动体，白占约一页高度。

    def pairs(self):
        return cs._table_pairing_problems(self.tmp)

    def test_two_identical_tables_each_in_its_own_float_are_reported(self):
        self.write("7_tables.tex", tbl("1") + "\n正文一句。\n\n" + tbl("2"))
        probs = self.pairs()
        self.assertEqual(len(probs), 1, probs)
        self.assertIn("表1", probs[0])
        self.assertIn("表2", probs[0])
        self.assertIn("并排", probs[0])

    def test_tables_with_different_column_specs_are_not_paired_reported(self):
        """参考件的「主要结果表 + 水分浓度表」就是这一情形 —— 不许报。"""
        self.write("7_tables.tex",
                   tbl("6", spec="@{}L{0.38\\textwidth}L{0.58\\textwidth}@{}") + tbl("7"))
        self.assertEqual(self.pairs(), [])

    def test_tables_with_different_row_counts_are_not_reported(self):
        self.write("7_tables.tex", tbl("1", nrows=3) + tbl("2", nrows=5))
        self.assertEqual(self.pairs(), [])

    def test_tables_split_by_a_heading_are_not_reported(self):
        """中间隔了小标题 —— 不是同一处，并排反而错。"""
        self.write("7_tables.tex",
                   tbl("1") + "\n\\subsection{另一件事}\n\n" + tbl("2"))
        self.assertEqual(self.pairs(), [])

    def test_tables_already_side_by_side_are_not_reported(self):
        """已经并排过的浮动体含两张 tabular —— 自动跳过。"""
        half = ("  \\begin{minipage}[t]{0.49\\textwidth}\n"
                "    \\begin{tabular}{cccccc}\n      \\toprule\n"
                "      时间/s & 0 & 1 & 2 & 3 & 4 \\\\\n      \\midrule\n"
                "      1 & a & b & c & d & e \\\\\n      \\bottomrule\n"
                "    \\end{tabular}\n  \\end{minipage}\\hfill\n")
        self.write("7_tables.tex",
                   "\\begin{table}[htbp]\n  \\centering\n" + half + half + "\\end{table}\n")
        self.assertEqual(self.pairs(), [])

    def test_a_single_table_is_not_reported(self):
        self.write("7_tables.tex", tbl("1"))
        self.assertEqual(self.pairs(), [])

    def test_two_three_line_tables_are_reported(self):
        """稿子实际是这么建的：`\\threelinetable` 产出 center+tabular、没有浮动体。

        只扫 `\\begin{table}` 会整片漏掉（正文里可能一个 table 浮动体都没有，
        表全靠这个宏），所以要按「表单元」而不是「浮动体」来找。
        """
        def tl(num):
            return (f"\\threelinetable{{表 {num}\\quad 标题{num}}}{{@{{}}c*{{5}}{{c}}@{{}}}}\n"
                    f"{{ 时间/s & 0 & 1 & 2 & 3 & 4 }}\n"
                    f"{{ 100 & a & b & c & d & e \\\\\n  300 & f & g & h & i & j }}\n\n")
        self.write("5_problem1.tex", tl("1") + tl("2"))
        probs = self.pairs()
        self.assertEqual(len(probs), 1, probs)
        self.assertIn("表1", probs[0])
        self.assertIn("表2", probs[0])

    def test_a_three_line_table_and_a_float_are_compared_too(self):
        """混用两种建表方式也要能比到一起（`@{}c*{5}{c}@{}` 与 `cccccc` 是同一件事）。

        行数与 `tbl()` 对齐（1 行表头 + 3 行数据），否则比的是「行数不同」而不是列格式。
        """
        tl = ("\\threelinetable{表 1\\quad 标题1}{@{}cccccc@{}}\n"
              "{ 时间/s & 0 & 1 & 2 & 3 & 4 }\n"
              "{ 100 & a & b & c & d & e \\\\\n  200 & f & g & h & i & j \\\\\n"
              "  300 & k & l & m & n & o }\n\n")
        self.write("5_problem1.tex", tl + tbl("2"))
        self.assertTrue(any("表1" in p and "表2" in p for p in self.pairs()))

    # ---- 图 1（分析流程图）的位置与栏宽 ----
    #
    # 图 1 该放在问题重述之后、问题分析之前，而且**只该有那一个**。两种放错要报：
    # ① 整张漏掉；② 塞进 2_analysis.tex 并缩到 0.7\textwidth（954×1297 的竖版大图
    # 缩七成，节点字糊掉）。

    def roadmap(self):
        return cs._roadmap_placement_problems(self.tmp)

    def test_the_roadmap_in_the_right_place_at_full_width_passes(self):
        self.assertEqual(self.roadmap(), [])

    def test_a_missing_roadmap_is_reported(self):
        self.write("1_restatement.tex", "\\section{问题重述}\n\\subsection{问题背景}\n")
        probs = self.roadmap()
        self.assertTrue(any("图 1 缺失" in p for p in probs), probs)

    def test_a_roadmap_shrunk_below_the_width_floor_is_reported(self):
        """缩到 `0.7\\textwidth` 必须报出来。

        下限 0.85 是**照参考件定的**，不是"整栏" —— 参考件 `1_restatement.tex:40`
        写的就是 `[0.85\\textwidth]`。检查器不许比参考件更严。
        """
        self.write("1_restatement.tex",
                   "\\section{问题重述}\n\\subsection{问题背景}\n"
                   "\\paperfigure[0.7\\textwidth]{fig_roadmap}{流程图}{fig_roadmap}\n")
        self.assertTrue(any("0.70" in p or "缩不得" in p for p in self.roadmap()),
                        self.roadmap())

    def test_the_reference_width_0_85_is_accepted(self):
        """参考件用的就是 0.85 —— 它必须通过。"""
        self.write("1_restatement.tex",
                   "\\section{问题重述}\n\\subsection{问题背景}\n"
                   "\\paperfigure[0.85\\textwidth]{fig_roadmap}{分析流程图}{fig_roadmap}\n")
        self.assertEqual(self.roadmap(), [])

    def test_a_roadmap_in_the_analysis_section_is_reported(self):
        """位置错了：该在「问题重述之后」，不在「问题分析」里。"""
        self.write("1_restatement.tex", "\\section{问题重述}\n\\subsection{问题背景}\n")
        self.write("2_analysis.tex",
                   "\\section{问题分析}\n\\subsection{问题一的分析}\n"
                   "\\subsection{本文主要创新点}\n"
                   "\\paperfigure[\\textwidth]{fig_roadmap}{流程图}{fig_roadmap}\n")
        probs = self.roadmap()
        self.assertTrue(any("1_restatement.tex" in p for p in probs), probs)

    def test_a_duplicated_roadmap_is_reported(self):
        self.write("1_restatement.tex",
                   "\\section{问题重述}\n\\subsection{问题背景}\n"
                   "\\paperfigure[\\textwidth]{fig_roadmap}{流程图}{fig_roadmap}\n"
                   "\\paperfigure[\\textwidth]{fig_roadmap}{又一张}{fig_roadmap2}\n")
        self.assertTrue(any("只该出现一次" in p for p in self.roadmap()))

    # ---- 两张同宽非整栏的图该并排 ----

    def test_two_figures_of_equal_partial_width_are_reported(self):
        """两张同宽、非整栏、相邻 → 该并成一个 `\\paperfigurepair`。"""
        self.write("7_figs.tex",
                   "\\paperfigure[0.7\\textwidth]{q1_a}{左}{qa}\n"
                   "\\paperfigure[0.7\\textwidth]{q1_b}{右}{qb}\n")
        probs = cs._figure_pairing_problems(self.tmp)
        self.assertEqual(len(probs), 1, probs)
        self.assertIn("paperfigurepair", probs[0])

    def test_the_caption_rule_truth_table(self):
        """图题判据的**误报/漏报对照表** —— 一遍说清这条规则认什么、不认什么。

        判据是"数字**带单位**才算读数"：只按"数字出现 ≥2 次就报"来判，会把
        「问题 3 与问题 4 的烘干时长对比」这种**两个编号**的合规图题误报，
        而那正是 `q4_effects` 的正确写法。这张表把它钉住。
        冒号那条同理：写手把分号换成冒号接小句就能把被点名的小作文图题原样写回来，
        所以两样都要判。
        """
        cases = [
            (True, "分析流程图"),
            (True, "问题 1 的温度场与水分浓度场"),
            (True, "问题 3 与问题 4 的烘干时长对比"),        # ← 两个编号，不是读数
            (True, r"基于文献 \cite{wang2024} 的两模型对比"),  # ← 引用键里的年份
            (False, r"分析流程图；图中结果框标注的结果时长为 $N=320$、$\Delta t=60$ s "
                    r"对照档，与正文主档的 57.1661 h 与 50.8238 h 不同档"),
            (False, r"问题 1 的温度场与水分浓度场：1800 s 时表面 36.79 $^\circ$C、"
                    r"中心 33.58 $^\circ$C"),
            (False, r"收敛曲线：这条曲线说明网格加密之后时长趋于稳定不再变化"),   # 冒号接小句
        ]
        for should_pass, cap in cases:
            self.write("7_figs.tex", "\\paperfigure{a}{" + cap + "}{qa}\n")
            probs = cs._caption_problems(self.tmp)
            if should_pass:
                self.assertEqual(probs, [], f"这条是合规图题，不该报：{cap}")
            else:
                self.assertTrue(probs, f"这条必须报（用户 2026-09-28 明确不要）：{cap}")

    def test_the_symbols_head_judge_ignores_layout_code(self):
        """标题下的「开头总述」判据只该数**散文**，不该把排版代码当散文。

        若按"非注释行**总字数** > 40"来判 ⇒ **按模板写的任何一份都判不过**：那一段里必须放
        `\\setlength{\\LTleft}{\\fill}`、居中表题行、`\\nopagebreak`、`\\vspace`（表题放进表内
        会被压成 5.5pt）⇒ 每轮 ⑨ 都会在这里卡住，还诱导人去删那些补丁（会把符号表压坏）。
        两边都要钉住：模板自己**通过**，而真加一段总述**必须报**。
        """
        tpl = PROJECT / "skills/9Paper-writing/templates/zh/cumcm-latex/sections/4_symbols.tex"
        self.write("4_symbols.tex", tpl.read_text(encoding="utf-8"))
        self.assertEqual([p for p in cs._symbols_problems(self.tmp) if "开头总述" in p], [],
                         "模板自己被判成有开头总述 —— 排版代码又被当成散文了")
        # 对照组：真写一段总述
        body = tpl.read_text(encoding="utf-8").replace(
            "\\section{符号说明}",
            "\\section{符号说明}\n\n除特别说明外，温度用摄氏度、时间用秒，"
            "全文所用符号的含义与单位汇总于表 1。")
        self.write("4_symbols.tex", body)
        self.assertTrue([p for p in cs._symbols_problems(self.tmp) if "开头总述" in p],
                        "真有一段总述却不报了 —— 判据被改废了")

    def test_a_sentence_like_caption_is_reported(self):
        """图题被写成小作文时必须报。例：「图 1：分析流程图；图中结果框标注的结果时长为
        N=320、Δt=60 s 对照档，与正文主档的 57.1661 h 与 50.8238 h 不同档」。

        成因是**两条规矩打架**（合规项要求披露档位 × 图注要一行），写手只好都塞进图题。
        判据：含 `；` / 出现 ≥2 处数字 / 去命令后 > 40 字，任一即报，并且要说清该挪去哪。
        """
        self.write("7_figs.tex",
                   "\\paperfigure{a}{分析流程图；图中结果框标注的结果时长为 $N=320$、"
                   "$\\Delta t=60$ s 对照档，与正文主档的 57.1661 h 与 50.8238 h 不同档}{qa}\n")
        probs = cs._caption_problems(self.tmp)
        self.assertEqual(len(probs), 1, probs)
        self.assertIn("分号", probs[0])
        self.assertIn("图内标注或正文", probs[0], "只说'不合格'不够 —— 得说清该挪去哪")

    def test_numbers_in_a_caption_are_reported(self):
        """报读数也不许进图题（读数属于正文）。"""
        self.write("7_figs.tex",
                   "\\paperfigure{a}{问题 1 的温度场与水分浓度场：1800 s 时表面 36.79 "
                   "$^\\circ$C、中心 33.58 $^\\circ$C}{qa}\n")
        self.assertEqual(len(cs._caption_problems(self.tmp)), 1)

    def test_a_short_noun_phrase_caption_passes(self):
        """合规的图题：短名词短语（带一个编号数字不算读数）。"""
        self.write("7_figs.tex",
                   "\\paperfigure{a}{分析流程图}{qa}\n"
                   "\\paperfigure{b}{问题 1 的温度场与水分浓度场}{qb}\n")
        self.assertEqual(cs._caption_problems(self.tmp), [])

    # ---- 双图命令里的图注同样要查 ----

    def test_captions_inside_a_pair_or_stack_are_checked_too(self):
        """写在 `\\paperfigurepair` / `\\paperfigurestack` 里的图注**也**受图题规矩管。

        若只有 `\\paperfigure` 被解析 ⇒ 换个命令就能把"小作文图题"原样塞回去。
        双图的**两半各有一条图注**，所以两边都要报（下面 `D` 那条是另一半的）。
        """
        bad = r"问题 1 的温度场：1800 s 时表面 36.79 $^\circ$C"     # 冒号接小句 + 报读数
        self.write("7_figs.tex",
                   "\\paperfigurepair{A}{" + bad + "}{la}{B}{左图题}{lb}\n")
        probs = cs._caption_problems(self.tmp)
        self.assertEqual(len(probs), 1, f"pair 里的坏图注没被查：{probs}")
        self.assertIn("A", probs[0])
        self.write("7_figs.tex",
                   "\\paperfigurestack{C}{上图题}{lc}{D}{" + bad + "}{ld}\n")
        probs = cs._caption_problems(self.tmp)
        self.assertEqual(len(probs), 1, f"stack 里**第二半**的坏图注没被查：{probs}")
        self.assertIn("D", probs[0])

    def test_good_captions_inside_a_pair_pass(self):
        """对照组：双图里写的合规图题（短名词短语）不许报 —— 免得"能查"变成"逢双图必报"。"""
        self.write("7_figs.tex",
                   "\\paperfigurepair{q1_a}{数值解与级数解的剖面对照}{la}"
                   "{q1_b}{温度场的径向分布}{lb}\n")
        self.assertEqual(cs._caption_problems(self.tmp), [])

    def test_the_pairw_arguments_line_up(self):
        """8 个实参的 `\\paperfigurepairw` 不许串位（先宽、再图、再题、再标签 ×2）。

        串位的症状很隐蔽：图注检查会拿**宽度**去当图题、把 `0.42\\textwidth` 当文件名 ——
        于是既报不出真问题，又报出一堆不存在的。这条直接钉解析结果。
        """
        figs = cs._paperfigures(
            r"\paperfigurepairw{0.42\textwidth}{qa}{左图题}{la}"
            r"{0.55\textwidth}{qb}{右图题}{lb}")
        self.assertEqual([f["width"] for f in figs], [r"0.42\textwidth", r"0.55\textwidth"])
        self.assertEqual([f["file"] for f in figs], ["qa", "qb"])
        self.assertEqual([f["caption"] for f in figs], ["左图题", "右图题"])
        self.assertEqual([f["label"] for f in figs], ["la", "lb"])

    def test_a_deliberate_stack_is_not_told_to_go_side_by_side(self):
        """误报对照：`\\paperfigurestack` 是**故意**上下排的，别拿"同宽就该并排"去报它。

        宏自己写死两半都是 `0.85\\textwidth` ⇒ 正好落进「相邻、同宽、非整栏」那条判据里。
        它的存在理由写在 `macros.tex`：两块宽高比差得大，并排会压成又宽又扁的条。
        """
        self.write("7_figs.tex",
                   "\\paperfigurestack{c}{上图题}{lc}{d}{下图题}{ld}\n")
        self.assertEqual(cs._figure_pairing_problems(self.tmp), [],
                         "把故意上下排的 stack 判成「该并排」了 —— 拿设计当缺陷")
        # 对照组：两张独立的同宽小图**仍然**要报（别把判据整个关掉）
        self.write("7_figs.tex",
                   "\\paperfigure[0.7\\textwidth]{q1_a}{左}{qa}\n"
                   "\\paperfigure[0.7\\textwidth]{q1_b}{右}{qb}\n")
        self.assertEqual(len(cs._figure_pairing_problems(self.tmp)), 1)

    def test_full_width_figures_are_not_reported(self):
        """整栏图本来就该独占一行。"""
        self.write("7_figs.tex",
                   "\\paperfigure{a}{左}{qa}\n\\paperfigure{b}{右}{qb}\n")
        self.assertEqual(cs._figure_pairing_problems(self.tmp), [])

    def test_figures_of_different_widths_are_not_reported(self):
        self.write("7_figs.tex",
                   "\\paperfigure[0.7\\textwidth]{a}{左}{qa}\n"
                   "\\paperfigure[0.5\\textwidth]{b}{右}{qb}\n")
        self.assertEqual(cs._figure_pairing_problems(self.tmp), [])

    def test_figures_split_by_a_heading_are_not_reported(self):
        self.write("7_figs.tex",
                   "\\paperfigure[0.7\\textwidth]{a}{左}{qa}\n"
                   "\\subsection{另一件事}\n"
                   "\\paperfigure[0.7\\textwidth]{b}{右}{qb}\n")
        self.assertEqual(cs._figure_pairing_problems(self.tmp), [])

    def test_an_already_paired_figure_pair_is_not_counted_as_two(self):
        """`\\paperfigurepair` 不能被当成两个 `\\paperfigure`（前缀相同，容易误匹配）。"""
        self.write("7_figs.tex",
                   "\\paperfigurepair{a}{左图题}{qa}{b}{右图题}{qb}\n"
                   "\\paperfigurepair{c}{左图题}{qc}{d}{右图题}{qd}\n")
        self.assertEqual(cs._figure_pairing_problems(self.tmp), [])
        self.assertEqual(cs._roadmap_placement_problems(self.tmp), [])

    # ---- 配置类失败要和内容类失败分开 ----

    def test_missing_template_is_its_own_kind_of_problem(self):
        shutil.rmtree(self.tmp / cs.TEMPLATES_REL)
        probs = self.check()
        self.assertTrue(any("找不到模板骨架" in p for p in probs), probs)

    def test_comments_are_not_headings(self):
        """骨架的约束写在 LaTeX 注释里 —— 注释不能被当成标题。"""
        self.write("2_analysis.tex", "% \\subsection{这是注释，不是标题}\n"
                                     "\\section{问题分析}\n"
                                     "\\subsection{问题一的分析}\n"
                                     "\\subsection{本文主要创新点}\n")
        self.assertEqual(self.check(), [])

    # ---- 问题分析：**全节 ≤ 一页**、**每个问题的分析 ≤ 3 行** ----
    #
    # 三个上限都按参考件 `基于变物性耦合传热传质与动域模型的.pdf` 量出来：它的 2.1~2.4
    # 各占 3 行、创新点每条 3 行、全节 1.23 页。本模板排版下 1 行 ≈ 33 字、1 页 ≈ 989 字。
    # 这条约束若只写在模板注释与 SKILL.md 里、没有任何抓手，交付稿就可以把四问分析
    # 各写成 400+ 字、全节 2205 字 = 2.23 页，而所有机械检查都是绿的。

    def _analysis_filled(self, per_q, head=0, innovation=0, questions=4, items=3):
        """每个「问题N的分析」正好 `per_q` 字；创新点写成 `items` 条，每条 `innovation` 字。"""
        cn = "一二三四五六七八"
        for n in range(2, questions + 1):
            self.write(f"5_problem{n}.tex",
                       f"\\section{{模型的建立与求解}}\n"
                       f"\\subsection{{问题{cn[n - 1]}的模型的建立和求解}}\n"
                       f"\\subsubsection{{具体分析}}\n\\subsubsection{{模型建立}}\n")
        body = "".join(f"\\subsection{{问题{cn[i]}的分析}}\n{'字' * per_q}\n"
                       for i in range(questions))
        inno = "".join(f"\\textbf{{创新点{cn[i]}：}}{'字' * innovation}\n"
                       for i in range(items))
        self.write("2_analysis.tex",
                   "\\section{问题分析}\n" + "字" * head + "\n" + body
                   + "\\subsection{本文主要创新点}\n" + inno + "\n")

    def test_a_section_within_the_limits_passes(self):
        """各节都落在上下限之间：4×90 + 总述 60 + 创新点 3×130 ≈ 810 字。"""
        self._analysis_filled(per_q=90, head=60, innovation=130)
        self.assertEqual([p for p in self.check() if "2_analysis.tex" in p], [])

    def test_an_overlong_per_question_analysis_is_reported(self):
        """每一问的分析最多 3 行（≈99 字）—— 写到 150 字就该报，并点名是哪一问。"""
        self._analysis_filled(per_q=150, head=60, innovation=90)
        probs = [p for p in self.check() if "2_analysis.tex" in p]
        self.assertTrue(any(f"超 {cs.ANALYSIS_MAX_LINES} 行上限" in p for p in probs), probs)
        self.assertTrue(any("问题一的分析" in p for p in probs), probs)

    def test_the_reference_shape_is_accepted(self):
        """参考件的形状必须能过 —— 否则写手照参考件写反而被判错。

        参考件实测：每问 3 行（96/113/75/105 非空白字符）、创新点每条 4~5 行
        （120~165 字）、全节 1.23 页。这里取它的中间尺寸，全节落在 989 字以内。
        """
        self._analysis_filled(per_q=110, head=100, innovation=178, items=3)
        self.assertEqual([p for p in self.check() if "2_analysis.tex" in p], [])

    def test_an_innovation_point_is_measured_item_by_item(self):
        """创新点整节装的是多条 —— 要**逐条**量，不能因为"这一节有 12 行"就判超。

        参考件里创新点每条 4~5 行（比问题分析长），所以逐条的上限也放宽到 5 行。
        """
        self._analysis_filled(per_q=50, head=50, innovation=185, items=3)
        self.assertEqual([p for p in self.check() if "2_analysis.tex" in p], [])

    def test_a_too_short_innovation_point_is_reported(self):
        """★ 下限才是关键那条：只写一句时**所有上限都满足**，于是"按新要求改过"与
        "把上一版原样拿来用"在机械上分不出来 —— 重跑几遍都发现不了。"""
        self._analysis_filled(per_q=90, head=60, innovation=55, items=3)   # 每条 ≈57 字 ≈1.5 行
        probs = [p for p in self.check() if "2_analysis.tex" in p]
        self.assertTrue(any("不足" in p and "行" in p for p in probs), probs)
        self.assertTrue(any("第一条" in p for p in probs), probs)

    def test_an_overlong_innovation_point_is_reported(self):
        """但创新点也不能无限长：一条写到 250 字（≈6.6 行）就该报，并点名是第几条。"""
        self._analysis_filled(per_q=60, head=60, innovation=250, items=3)
        probs = [p for p in self.check() if "2_analysis.tex" in p]
        self.assertTrue(any(f"超 {cs.ANALYSIS_INNO_MAX_LINES} 行上限" in p for p in probs), probs)
        self.assertTrue(any("创新点" in p and "第一条" in p for p in probs), probs)

    def test_a_section_over_the_cap_is_reported(self):
        """全节一页半是硬上限；明细要点出每一节的字数，写手才知道砍哪一段。"""
        self._analysis_filled(per_q=114, head=114, innovation=188, questions=6, items=4)
        probs = [p for p in self.check() if "2_analysis.tex" in p]
        self.assertTrue(any("超一页半上限" in p for p in probs), probs)
        self.assertTrue(any("问题一的分析" in p and "问题六的分析" in p for p in probs), probs)

    def test_a_slightly_long_section_is_a_nudge_not_a_breach(self):
        """一页之下、提醒线之上：只说偏长，不读成"超上限"（否则写手分不清该砍多少）。"""
        self._analysis_filled(per_q=110, head=100, innovation=200, questions=6)
        probs = [p for p in self.check() if "2_analysis.tex" in p]
        self.assertTrue(any("偏长" in p for p in probs), probs)
        self.assertFalse(any("超一页半上限" in p for p in probs), probs)

    def test_a_bare_backslash_percent_is_not_a_comment(self):
        """`\\%` 是转义百分号（`31\\%` 这种），不是注释 —— 按裸 `%` 切行会**少算**字数。

        按裸 `%` 切行会把两行 `\\%` 后面的正文全丢掉：算出 1954 字（真值 2205），
        页↔字的换算因此差 12%。尺子得先跟真值对账。
        """
        head, tail = "水分下降约 31\\% 与 47\\%，", "两处都带转义百分号。"
        self.assertEqual(cs._prose_len(head + tail), cs._prose_len(head) + cs._prose_len(tail),
                         "转义百分号后面的字被当成注释截掉了")


if __name__ == "__main__":
    unittest.main()
