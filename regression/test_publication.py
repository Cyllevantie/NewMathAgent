"""Physical page counts, current-PDF binding, and release gate fault injection."""
import copy
import json
import tempfile
import unittest
from pathlib import Path

from lib.publication.checks import bind_map, classify, inspect, sha
from lib.visualization.evidence import write_json

POLICY = {"schema_version": 1, "max_counted_pages": 30, "target_counted_pages": 28,
          "counted_kinds": ["abstract", "body", "references"], "rule_basis": "fixture"}


def span(kind, first, last):
    return {"kind": kind, "first": first, "last": last, "title": kind}


# 边界页那一族要的配置：起始标记 + 判"落在页面上部"的比例（照 config/publication.json 的形状）。
# 标记故意用 **ASCII**：夹具靠 `page.insert_text()` 造 PDF，而 PyMuPDF 的默认字体
#    **编码不了中日韩字** —— 写进去的 CJK 回读成 `···`，`search_for("八、")` 命中 0，
#    于是"认不出标记就不判"那条分支会把整条判据变成恒真，夹具假绿。
#    真实稿子是 xelatex 排的、文字可抽取，能报出正确百分比。
POLICY_MARKS = dict(POLICY,
                    kind_start_markers={"abstract": ["ABSTRACT"], "body": ["1. BODY"],
                                        "ai_statement": ["8. AI"], "appendix": ["APPENDIX"]},
                    boundary_top_tol=6)


class PageCountTests(unittest.TestCase):
    def test_cumcm_electronic_profile_counts_abstract_and_body(self):
        """计页额度 = **摘要 + 正文**（赛区补充规定）。

        国赛《格式规范》只写「正文（一～七）不超过30页」「摘要单独成页1页」，**没写摘要算不算**；
        若按「不算」（`counted_kinds: ["body"]`）计，一份 摘要1+正文30 的稿子会被判成合规，
        而赛区是「算」⇒ 实际超 1 页。这条测试钉住「算」这个口径。

        仍**不计**的：八、AI 工具使用说明 / 九、参考文献（另有 `max_group_pages` 合计 ≤1 页）、
        附录（不限页）、目录与封面（`forbidden_kinds`）。
        """
        policy = json.loads((Path(__file__).resolve().parents[1] / "config/publication.json").read_text(encoding="utf-8"))
        mapping = {"schema_version": 1, "spans": [span("abstract", 1, 1), span("body", 2, 31),
                   span("ai_statement", 32, 32), span("appendix", 33, 36)]}
        result = classify(36, mapping, policy)
        self.assertEqual(result["counted_pages"], 31, "摘要 1 + 正文 30 = 31，应计入")
        self.assertEqual(result["over_limit"], 1, "31 > 30，必须判超页 —— 旧口径在这里漏掉的那一页")
        # 收掉一页（正文压到 29）就回到限内
        ok = {"schema_version": 1, "spans": [span("abstract", 1, 1), span("body", 2, 30),
              span("ai_statement", 31, 31), span("appendix", 32, 35)]}
        self.assertEqual(classify(35, ok, policy)["over_limit"], 0)
        # 结构类错误照旧不许蒙混（缺摘要段 / 摘要超一页 / 出现目录或封面）
        for spans in ([span("abstract", 1, 1), span("contents", 2, 2), span("body", 3, 34), span("appendix", 35, 35)],
                      [span("cover", 1, 1), span("abstract", 2, 2), span("body", 3, 34), span("appendix", 35, 35)],
                      [span("abstract", 1, 2), span("body", 3, 34), span("appendix", 35, 35)]):
            with self.assertRaises(ValueError): classify(35, {"schema_version": 1, "spans": spans}, policy)

    def test_ai_statement_and_references_share_one_page(self):
        """模板原文「九写在8下面，加起来不超过1页」—— 八+九 是**合计**上限。

        同占一页（映射里归成 ai_statement）合格；分开占两页即超。这正是为什么
        `max_kind_pages` 表达不了、需要 `max_group_pages`。
        """
        policy = json.loads((Path(__file__).resolve().parents[1] / "config/publication.json").read_text(encoding="utf-8"))
        shared = {"schema_version": 1, "spans": [span("abstract", 1, 1), span("body", 2, 31),
                  span("ai_statement", 32, 32), span("appendix", 33, 33)]}
        self.assertEqual(classify(33, shared, policy)["counts"]["ai_statement"], 1)
        split = {"schema_version": 1, "spans": [span("abstract", 1, 1), span("body", 2, 31),
                 span("ai_statement", 32, 32), span("references", 33, 33), span("appendix", 34, 34)]}
        with self.assertRaises(ValueError) as cm:
            classify(34, split, policy)
        self.assertIn("合计 2 页", str(cm.exception))

    def test_body_below_floor_is_flagged_but_does_not_fail(self):
        """篇幅下限（写满 30、宁多不少）：低于下限只出 warning，不判 FAIL。

        国赛规则本身没有下限，这条是**本项目的写作口径** —— 多了能压缩，少了是真少。
        所以它不能变成一道会拦下合法交付的硬门。
        """
        policy = json.loads((Path(__file__).resolve().parents[1] / "config/publication.json").read_text(encoding="utf-8"))
        thin = {"schema_version": 1, "spans": [span("abstract", 1, 1), span("body", 2, 21),
                span("appendix", 22, 24)]}
        result = classify(24, thin, policy)
        self.assertEqual(result["counted_pages"], 21, "摘要 1 + 正文 20")
        self.assertEqual(result["below_min"], policy["min_counted_pages"] - 21)
        self.assertEqual(result["over_limit"], 0, "低于下限不该被判超限")
        # 打满：摘要 1 + 正文 29 = 30 ⇒ 既不超限也不低于下限
        full = {"schema_version": 1, "spans": [span("abstract", 1, 1), span("body", 2, 30),
                span("appendix", 31, 33)]}
        f = classify(33, full, policy)
        self.assertEqual(f["below_min"], 0)
        self.assertEqual(f["over_limit"], 0)

    def test_invalid_floor_cannot_exceed_target(self):
        for floor in (0, -1, 31, "25"):
            policy = copy.deepcopy(POLICY)
            policy["min_counted_pages"] = floor
            with self.assertRaises(ValueError):
                classify(1, {"schema_version": 1, "spans": [span("body", 1, 1)]}, policy)

    def test_appendix_and_contents_excluded_but_references_counted(self):
        mapping = {"schema_version": 1, "spans": [span("abstract", 1, 1), span("contents", 2, 3),
                   span("body", 4, 31), span("references", 32, 32), span("appendix", 33, 45)]}
        result = classify(45, mapping, POLICY)
        self.assertEqual(result["counted_pages"], 30)
        self.assertEqual(result["over_limit"], 0)

    def test_35_body_pages_fail_even_with_large_appendix(self):
        result = classify(40, {"schema_version": 1, "spans": [span("body", 1, 35), span("appendix", 36, 40)]}, POLICY)
        self.assertEqual(result["over_limit"], 5)

    def test_gap_overlap_unknown_category_rejected(self):
        for spans in ([span("body", 1, 2)], [span("body", 1, 3), span("appendix", 3, 3)],
                      [span("body", 1, 2), span("unknown", 3, 3)]):
            with self.assertRaises(ValueError): classify(3, {"schema_version": 1, "spans": spans}, POLICY)

    def test_invalid_policy_cannot_disable_body_count(self):
        policy = copy.deepcopy(POLICY)
        policy["counted_kinds"] = ["references"]
        with self.assertRaises(ValueError):
            classify(1, {"schema_version": 1, "spans": [span("body", 1, 1)]}, policy)


def project_policy():
    return json.loads((Path(__file__).resolve().parents[1] / "config/publication.json")
                      .read_text(encoding="utf-8-sig"))


def build_pdf(path, abstract_lines, body_pages=1, fitz=None):
    """造一份「版心撑得开」的稿子：正文页 35 行铺满纸面，摘要页只写 abstract_lines 行。

    版心靠正文页量出来（`_text_frame` 取全稿非页脚块的最小 top ~ 最大 bottom），
    所以夹具不需要知道 geometry —— 判据怎么量，夹具就怎么给。
    末页是附录：本项目的口径要求正文之后必须有附录（`require_appendix`）。
    """
    doc = fitz.open()
    abstract = doc.new_page()
    for i in range(abstract_lines):
        abstract.insert_text((50.0, 100.0 + 20.0 * i), "摘要正文行 " * 3)
    for _ in range(body_pages):
        page = doc.new_page()
        for i in range(35):
            page.insert_text((50.0, 70.0 + 20.0 * i), "正文行 " * 4)
    doc.new_page().insert_text((50.0, 100.0), "附录：支撑材料清单")
    doc.save(path)
    doc.close()


class AbstractFillTests(unittest.TestCase):
    """摘要「写满那一页」＝ 版心填充率判据。

    纯按字符数下限（如 `min_kind_chars.abstract = 900`）守不住：919 字符的坏样本能从下面
    穿过去，而且只出 warning（本仓库没有一处读 warning）⇒ ⑨ 的返修单里永远不会有这一条，
    摘要欠写就会一路放行。下面这几条把这个口径钉住。
    """

    def setUp(self):
        try:
            import pymupdf as fitz
        except ImportError:
            self.skipTest("Requires PyMuPDF")
        self.fitz = fitz
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "paper").mkdir()
        write_json(self.root / "config/publication.json", project_policy())

    def inspect_with(self, abstract_lines, policy=None):
        if policy is not None:
            write_json(self.root / "config/publication.json", policy)
        build_pdf(self.root / "paper/main.pdf", abstract_lines, fitz=self.fitz)
        write_json(self.root / "spec.json",
                   {"schema_version": 1,
                    "spans": [span("abstract", 1, 1), span("body", 2, 2), span("appendix", 3, 3)]})
        bind_map(self.root, self.root / "spec.json")
        return inspect(self.root)

    def test_a_short_abstract_page_is_a_hard_failure_marked_as_prose(self):
        """阈值必须**高于**已知坏样本。

        摘要页 919 字符时占版心 78.4%，下限若定在 900，判据就会对它沉默。
        """
        result = self.inspect_with(abstract_lines=1)
        fill = result["kind_fills"]["abstract"]["fill"]
        self.assertLess(fill, 0.80, "夹具要点：够短才落得到 hard 之下")
        self.assertEqual(result["status"], "FAIL")
        self.assertTrue(any("版心" in i for i in result["issues"]), result["issues"])
        self.assertEqual(result["prose_issues"], result["issues"],
                         "摘要欠写是**文字**缺陷 ⇒ 必须打 prose 标记，否则会被判给 ⑩ 打转")

    def test_a_full_abstract_page_is_clean(self):
        result = self.inspect_with(abstract_lines=33)
        self.assertGreaterEqual(result["kind_fills"]["abstract"]["fill"], 0.90)
        self.assertEqual(result["status"], "PASS")
        self.assertFalse([w for w in result["warnings"] if "版心" in w], result["warnings"])

    def test_a_slightly_short_abstract_page_only_warns(self):
        """[hard, target) 只提示：差一点就别把小时级的链拖回去。"""
        result = self.inspect_with(abstract_lines=29)
        self.assertTrue(0.80 <= result["kind_fills"]["abstract"]["fill"] < 0.90,
                        result["kind_fills"])
        self.assertEqual(result["status"], "PASS")
        self.assertTrue([w for w in result["warnings"] if "版心" in w], result["warnings"])
        self.assertEqual(result["issues"], [])

    def test_the_char_floor_defers_to_the_fill_criterion(self):
        """两把尺子不许同时开火：量得出填充率时，chars 那条闭嘴（否则同一件事报两遍）。"""
        result = self.inspect_with(abstract_lines=29)
        self.assertLess(result["kind_fills"]["abstract"]["chars"], 1040, "夹具要点：字符数应低于兜底下限")
        self.assertFalse([w for w in result["warnings"] if "低于下限" in w], result["warnings"])

    def test_an_unmeasurable_frame_falls_back_to_the_char_floor(self):
        """量不出版心（整份就两三行字的样张）时，字符数下限照旧兜底。"""
        doc = self.fitz.open()
        for text in ("摘要只有一行", "正文只有一行", "附录只有一行"):
            doc.new_page().insert_text((50.0, 100.0), text)
        doc.save(self.root / "paper/main.pdf")
        doc.close()
        write_json(self.root / "spec.json",
                   {"schema_version": 1, "spans": [span("abstract", 1, 1), span("body", 2, 2),
                                                   span("appendix", 3, 3)]})
        bind_map(self.root, self.root / "spec.json")
        result = inspect(self.root)
        self.assertEqual(result["kind_fills"], {}, "版心高不足 400pt ⇒ 量不出来")
        self.assertTrue([w for w in result["warnings"] if "低于下限" in w], result["warnings"])

    def test_a_stale_formula_review_is_also_marked_as_prose(self):
        """公式复核记录过期 ⇒ 同样打 prose 标记。

        它也是"读公式"的活（只有 ⑨ 能重签这份记录）⇒ 判给 ⑩排版必然下一轮再报同一条。
        """
        (self.root / "paper/sections").mkdir(parents=True)
        (self.root / "paper/sections/x.tex").write_text(
            "前文。\n$$a=b$$\n后文。\n", encoding="utf-8")
        write_json(self.root / "paper/formula-review.json",
                   {"pdf_sha256": "0" * 64, "items": []})
        build_pdf(self.root / "paper/main.pdf", 33, fitz=self.fitz)
        write_json(self.root / "spec.json",
                   {"schema_version": 1, "spans": [span("abstract", 1, 1), span("body", 2, 2),
                                                   span("appendix", 3, 3)]})
        bind_map(self.root, self.root / "spec.json")
        result = inspect(self.root)
        stale = [i for i in result["issues"] if "公式复核记录未绑定" in i]
        self.assertTrue(stale, result["issues"])
        self.assertIn(stale[0], result["prose_issues"])

    def test_audit_still_returns_a_plain_list(self):
        from lib.publication.checks import audit
        build_pdf(self.root / "paper/main.pdf", 1, fitz=self.fitz)
        write_json(self.root / "spec.json",
                   {"schema_version": 1, "spans": [span("abstract", 1, 1), span("body", 2, 2), span("appendix", 3, 3)]})
        bind_map(self.root, self.root / "spec.json")
        self.assertIsInstance(audit(self.root), list)
        self.assertIsInstance(audit(self.root, detail=True), dict)


class PublicationRollbackTargetTests(unittest.TestCase):
    """`_mechanical_floor` 的回退目标按「谁有权改」分：沾文字 ⇒ ⑨论文撰写，纯版式 ⇒ ⑩排版。

    判错目标的代价不是多跑一轮，而是**转不出去**：⑩ 无权改摘要文字 ⇒ 下一轮同样的 FAIL。
    """

    def setUp(self):
        try:
            import pymupdf as fitz
        except ImportError:
            self.skipTest("Requires PyMuPDF")
        from test_workflow import load_server
        self.fitz = fitz
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "paper").mkdir()
        write_json(self.root / "spec.json",
                   {"schema_version": 1, "spans": [span("abstract", 1, 1), span("body", 2, 2), span("appendix", 3, 3)]})
        write_json(self.root / "config/publication.json", project_policy())
        self.s = load_server(self.root)
        self.stage = next(st for st in self.s.STAGES if st["id"] == "verify")

    def floor(self, abstract_lines, tweak=None):
        build_pdf(self.root / "paper/main.pdf", abstract_lines, fitz=self.fitz)
        policy = project_policy()
        if tweak:
            tweak(policy)
        write_json(self.root / "config/publication.json", policy)
        bind_map(self.root, self.root / "spec.json")
        return self.s._mechanical_floor(self.stage)

    def test_a_prose_defect_goes_back_to_the_writing_stage(self):
        decision = self.floor(1)
        self.assertEqual(decision["reason"], "publication_check_failed")
        self.assertEqual(decision["target"], "write", "摘要欠写只有 ⑨ 能改")

    def test_a_pure_layout_defect_still_goes_to_the_format_stage(self):
        decision = self.floor(33, tweak=lambda p: p.update(max_pdf_bytes=10))
        self.assertEqual(decision["reason"], "publication_check_failed")
        self.assertEqual(decision["target"], "format")

    def test_a_mixed_bag_follows_the_prose_side(self):
        """文字 + 版式混在一起 ⇒ 判给 ⑨：⑨ 在 ⑩ 上游，回退它会连 ⑩ 一起重跑；
        反过来判给 ⑩，文字那条谁也改不了 ⇒ 死循环。"""
        decision = self.floor(1, tweak=lambda p: p.update(max_pdf_bytes=10))
        self.assertEqual(decision["target"], "write")


class BoundaryPageTests(unittest.TestCase):
    """边界页归属：`classify` 只信声明的区间，**看不出「某一页横跨两个类别」**。

    一份声明 `body 2–30` / `ai_statement 31` 的映射，若第 31 页**开头还是正文**
    （表9 + 七的用法段），照样算出 30 页、判 PASS —— 正文被少数一页、`八+九 ≤1 页`
    的合计上限被多数一页。这一族测试钉的就是这个口子：跨界页必须报出来，
    而合规的映射不许被误伤。
    """

    def setUp(self):
        try:
            import pymupdf as fitz
        except ImportError:
            self.skipTest("Requires PyMuPDF")
        self.fitz = fitz
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "paper").mkdir()
        write_json(self.root / "config/publication.json", POLICY_MARKS)

    def _pdf(self, shared):
        """`shared=True` ⇒ 第 3 页先写一整页正文、「8. AI」压到半页才开始（跨界页）。"""
        doc = self.fitz.open()
        doc.new_page().insert_text((50, 100), "ABSTRACT")
        doc.new_page().insert_text((50, 70), "1. BODY")
        page = doc.new_page()
        if shared:
            for i in range(18):
                page.insert_text((50, 70 + 20 * i), "body line body line")
            page.insert_text((50, 430), "8. AI statement")     # 半页处才起 ⇒ 横跨两类别
        else:
            page.insert_text((50, 70), "8. AI statement")      # 页首起 ⇒ 边界干净
        doc.new_page().insert_text((50, 70), "APPENDIX file list")
        doc.save(self.root / "paper/main.pdf")
        doc.close()
        mapping = {"schema_version": 1,
                   "spans": [span("abstract", 1, 1), span("body", 2, 2),
                             span("ai_statement", 3, 3), span("appendix", 4, 4)]}
        # 手工绑 SHA：这一族要验的正是"`bind_map` 会拒绑"（见最后一条），不能借它来绑。
        mapping["pdf_sha256"] = sha(self.root / "paper/main.pdf")
        return mapping

    def test_classify_alone_cannot_see_a_shared_page(self):
        """对照组：这**不是** `classify` 的活 —— 它算出来是"没超"。"""
        mapping = self._pdf(shared=True)
        self.assertEqual(classify(4, mapping, POLICY_MARKS)["over_limit"], 0)

    def test_a_page_shared_by_two_kinds_is_reported(self):
        write_json(self.root / "paper/page-map.json", self._pdf(shared=True))
        r = inspect(self.root)
        self.assertEqual(r["status"], "FAIL", "跨界页没被判出来")
        self.assertTrue(any("上面还有文字" in i and "横跨两个类别" in i for i in r["issues"]),
                        f"报的不是边界页那条：{r['issues']}")

    def test_a_clean_boundary_is_not_false_flagged(self):
        """反面同样要钉住：误报会让一份**合规**的稿子连映射都绑不上。"""
        write_json(self.root / "paper/page-map.json", self._pdf(shared=False))
        r = inspect(self.root)
        self.assertEqual(r["status"], "PASS", f"合规的映射被误伤了：{r['issues']}")

    def test_a_few_lines_of_the_previous_kind_still_count(self):
        """只漏两行的跨界页也要拦住 —— 宽松的判据抓不到它。

        p31 的「八、」在 **14.9%** 处（上面只漏了两行正文）时，若判据是"标记落在页面前
        30%"，它就会判过 ⇒ 正文仍到 p31、计入 31 页、**超限静默放行**。判据收紧成
        "标记必须是这一页**最上面那块文字**"才拦得住。
        这条与上面那条的区别：上面那份漏了 18 行（两种判据都会拦），**这条只漏两行**。
        """
        doc = self.fitz.open()
        doc.new_page().insert_text((50, 100), "ABSTRACT")
        doc.new_page().insert_text((50, 70), "1. BODY")
        page = doc.new_page()
        page.insert_text((50, 70), "body tail line one")
        page.insert_text((50, 90), "body tail line two")     # ← 只漏两行（≈ 14%）
        page.insert_text((50, 120), "8. AI statement")
        doc.new_page().insert_text((50, 70), "APPENDIX file list")
        doc.save(self.root / "paper/main.pdf")
        doc.close()
        write_json(self.root / "paper/page-map.json",
                   {"schema_version": 1, "pdf_sha256": sha(self.root / "paper/main.pdf"),
                    "spans": [span("abstract", 1, 1), span("body", 2, 2),
                              span("ai_statement", 3, 3), span("appendix", 4, 4)]})
        r = inspect(self.root)
        self.assertEqual(r["status"], "FAIL",
                         "起始页上只漏两行就没报 —— 那正是用户在 14.9% 处抓到的那个漏网")

    def test_bind_map_refuses_a_dishonest_map(self):
        """关键落点：`bind_map` 绑之前就校验 ⇒ **不诚实的映射根本落不了盘**。
        只放进 `inspect` 的话，那份"整页判给后一类"的映射照样绑得上、照样显示 30 页 PASS。"""
        write_json(self.root / "spec.json", self._pdf(shared=True))
        with self.assertRaises(ValueError):
            bind_map(self.root, self.root / "spec.json")


class PdfBindingTests(unittest.TestCase):
    def setUp(self):
        try:
            import pymupdf as fitz
        except ImportError:
            self.skipTest("Requires PyMuPDF")
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "paper").mkdir()
        write_json(self.root / "config/publication.json", POLICY)
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((50, 60), "Test body")
        doc.save(self.root / "paper/main.pdf")
        doc.close()
        write_json(self.root / "spec.json", {"schema_version": 1, "spans": [span("body", 1, 1)]})

    def test_missing_mapping_unverified_then_current_binding_passes(self):
        self.assertEqual(inspect(self.root)["status"], "UNVERIFIED")
        bind_map(self.root, self.root / "spec.json")
        self.assertEqual(inspect(self.root)["status"], "PASS")

    def test_changed_pdf_invalidates_mapping(self):
        bind_map(self.root, self.root / "spec.json")
        with (self.root / "paper/main.pdf").open("ab") as stream:
            stream.write(b"\n% new build\n")
        self.assertEqual(inspect(self.root)["status"], "UNVERIFIED")

    def test_pdf_file_size_limit_blocks(self):
        policy = copy.deepcopy(POLICY)
        policy["max_pdf_bytes"] = 10
        write_json(self.root / "config/publication.json", policy)
        bind_map(self.root, self.root / "spec.json")
        self.assertEqual(inspect(self.root)["status"], "FAIL")

    def test_overall_pass_cannot_bypass_missing_page_map(self):
        from test_workflow import load_server
        s = load_server(self.root)
        stage = next(st for st in s.STAGES if st["id"] == "verify")
        (s.REPORTS / stage["report"]).write_text("PASS\n" + "evidence "*30)
        self.assertEqual(s._gate_decision(stage)["reason"], "publication_check_failed")
        bind_map(self.root, self.root / "spec.json")
        self.assertEqual(s.gate_result(stage), "ok")
