# -*- coding: utf-8 -*-
"""文字层判据：**纯指引句** 与 **结果型加粗**。

要守的两条：

  * 「四个问题的求解与检验路线如图 1 所示。」这类整句只在指路、删掉指针后不再表达
    结论/数值/机制的句子，算缺陷。
  * 关键的比较、重要词汇、关键数字要加粗，让评委一眼就看到结果。

判据实现在 `lib/publication/checks.py` 的 `style_hints()` / `_is_bare_pointer()`，只出**提示**
（进 `reports/PUBLICATION_CHECK.json` 的 warnings 与 `style_hints`），**不拦门禁** ——
理由写在那边：`publication` 类硬拦的回退目标被写死成 ⑩排版，而措辞是 ⑨ 的产出（⑩ 无权改内容）
⇒ 判死只会来回打转。修法走 ⑫评分标判词 → ⑬就地改，或 ⑨ 下一轮。

下面钉的是**它认得出什么、也认得住不误伤什么**。前 6 个该判（真稿里都是这样），后 6 个不许判
（**尾部引用不是缺陷**）。另有一条钉 `line` 字段必须是**源文件行号**。
"""
import tempfile
import unittest
from pathlib import Path

import sys

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))
from lib.publication.checks import _is_bare_pointer, style_hints  # noqa: E402

BARE = [   # 该判：整句只在指路（删掉指针后不再表达结论/数值/机制）
    r"四个问题的求解与检验路线如图~\ref{fig:fig_roadmap} 所示。",
    r"整个烘干过程的两个场如图~\ref{fig:q2_field} 与图~\ref{fig:q2_surface3d} 所示。",
    r"温度场与水分浓度场的整体结构如图~\ref{fig:q1_field} 所示，沿半径的剖面随时间的变化见附录图 A7。",
    r"按上述格式算出的温度与水分浓度如表 2 与表 3 所示。",
    r"网格收敛、步长收敛与场级收敛见图 4、图 5 与表 A3。",
    r"结果见表 A2。",
]
FINE = [   # 不许判：尾部引用 / 冒号后给内容 / 句子本身已经承载信息
    r"这正是把动域问题写成固定域形式的物理含义，如图~\ref{fig:fig_q4_material} 所示；食品等温干燥的动边界模型见文献~\cite{ref5}。",
    r"因此它们之间可以互相比较，但与主档的定义不可混减；结果如图~\ref{fig:q4_effects} 所示。",
    r"水分场在最后时段的形态见图 6：在达标前的最后 17 h 里，等值线自 $r\approx1.4$ cm 收敛到中心。",
    r"温度场则完全不同，它在 1.5 h 内就基本完成升温，所以图~\ref{fig:q2_field} 的温度栏只画升温段。",
    r"网格支只细化网格、固定时间步，逐列的含水率差如图 A1 所示。",
    r"含湿量下降得极快，见图 3：附录 3 的物性使 $D$ 下降 16.84 倍。",
]


class BarePointerSentenceTests(unittest.TestCase):
    def test_it_flags_bare_pointers(self):
        for s in BARE:
            self.assertTrue(_is_bare_pointer(s), f"该判却没判：{s}")

    def test_it_never_flags_a_tail_reference(self):
        """反向守卫：`…；结果如图 X 所示。` 这类**尾部引用**必须放过。

        判据只按「。」切句、**不按逗号/分号切** —— 否则每一处尾部引用都会被切成裸指针，
        整批假阳性。
        """
        for s in FINE:
            self.assertFalse(_is_bare_pointer(s), f"误伤了尾部引用：{s}")

    def test_it_reads_the_source_line_number(self):
        """`line` 必须是**源文件行号**：给"第几句"会把人指到错的地方。"""
        root = Path(tempfile.mkdtemp())
        (root / "paper/sections").mkdir(parents=True)
        body = "\n".join(["开头一句。", "",
                          r"四个问题的求解与检验路线如图~\ref{fig:a} 所示。",
                          "后一句。", ""])
        (root / "paper/sections/x.tex").write_text(body, encoding="utf-8")
        hits = [h for h in style_hints(root) if h["line"]]
        self.assertEqual([h["line"] for h in hits], [3], "行号应指向第 3 行那一句")

    def test_a_prose_only_file_has_no_hints(self):
        root = Path(tempfile.mkdtemp())
        (root / "paper/sections").mkdir(parents=True)
        (root / "paper/sections/x.tex").write_text(
            "本文建立了一维径向模型。\n温度在 30 min 内抬升到 \\textbf{33.5753}$^\\circ$C。\n",
            encoding="utf-8")
        self.assertEqual(style_hints(root), [], "没有纯指引句时不该报")


if __name__ == "__main__":
    unittest.main()
