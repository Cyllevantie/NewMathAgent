# -*- coding: utf-8 -*-
"""上传守卫（`lib/web/upload_guard.py`）：路径白名单、体量上限、同名冲突、机械判定。

为什么值得逐条钉：上传改成一键传文件夹之后，**客户端能指定嵌套路径**了 ——
过去靠 `lib/web/server.py:6276` 的 `Path(f.filename).name` 把整条路径丢掉来"顺便"
挡住目录穿越。保留结构就等于把这层挡住的东西拿掉了，所以校验必须自己扛，
而且这是安全关键代码：
**真值表比解释便宜**，写死"这些收、这些拒"。
"""
import sys
import unittest
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "lib" / "web"))
import upload_guard as g  # noqa: E402


class SafeRelPathTests(unittest.TestCase):
    def test_accepted_shapes(self):
        """该收的：中文、空格、子目录、点号在中间 —— 都是这道题真实的文件名形状。"""
        for raw, want in (
            ("附件3/result1.xlsx", "附件3/result1.xlsx"),
            ("题目 一/问题.pdf", "题目 一/问题.pdf"),
            ("a/b/c/d.txt", "a/b/c/d.txt"),
            (r"附件3\result1.xlsx", "附件3/result1.xlsx"),   # 反斜杠归一化
            ("./题目.pdf", "题目.pdf"),                       # 开头的 ./ 去掉
            ("a//b/./c.txt", "a/b/c.txt"),                    # 空段与 . 段丢掉
            ("v1.2/数据.csv", "v1.2/数据.csv"),               # 中间的点不算"尾随点"
        ):
            with self.subTest(raw=raw):
                self.assertEqual(g.safe_rel_path(raw), want)

    def test_rejected_shapes(self):
        """该拒的：穿越、绝对路径、盘符、UNC、保留名、尾随点/空格、非法字符、超长。"""
        for raw, why in (
            ("../x.txt", "上跳"),
            ("a/../../x.txt", "中途上跳"),
            ("/abs/x.txt", "绝对路径"),
            ("//host/share/x.txt", "UNC"),
            ("C:/x.txt", "带盘符"),
            ("con", "保留名"),
            ("con.txt", "保留名带扩展名"),
            ("COM3.csv", "保留名大小写不敏感"),
            ("x.", "尾随点"),
            ("x ", "尾随空格"),
            (" x", "开头空格"),
            ("a<b.txt", "非法字符"),
            ('a"b.txt', "非法字符"),
            ("a:b.txt", "非法字符"),
            ("a\x01b.txt", "控制字符"),
            ("x" * (g.MAX_SEG_LEN + 1) + ".txt", "单段超长"),
            # 三段各 100 字（每段都不超单段上限）但整串 302 > MAX_REL_LEN ⇒ 走整串那条
            ("/".join(["目" * g.MAX_SEG_LEN] * 3), "整串超长"),
            ("", "空"),
            ("   ", "只有空格"),
            ("/", "只有斜杠"),
        ):
            with self.subTest(raw=raw):
                with self.assertRaises(g.UploadRejected, msg=why):
                    g.safe_rel_path(raw)

    def test_rejection_carries_something_actionable(self):
        """拒绝文案必须说清**怎么办** —— 面板上只有一行字的错，用户只能猜。"""
        try:
            g.safe_rel_path("../x.txt")
        except g.UploadRejected as exc:
            self.assertIn("..", str(exc))
            self.assertTrue(exc.hint, "没给下一步怎么办")
        else:
            self.fail("该拒没拒")


class PlanInboxTests(unittest.TestCase):
    def test_skips_editor_junk_but_tells_you(self):
        """垃圾文件跳过要**记下来**（调用方去打日志），不许静默丢。"""
        keep, skipped = g.plan_inbox(["题目.pdf", "Thumbs.db", "a/~$book.xlsx", ".DS_Store"])
        self.assertEqual(keep, ["题目.pdf"])
        self.assertEqual(sorted(skipped), [".DS_Store", "Thumbs.db", "a/~$book.xlsx"])

    def test_too_many_files(self):
        rels = [f"d{i}/f.xlsx" for i in range(g.MAX_FILES + 1)]
        with self.assertRaises(g.UploadRejected) as cm:
            g.plan_inbox(rels)
        self.assertIn("文件太多", str(cm.exception))
        self.assertIn("zip", cm.exception.hint, "得告诉用户出路（打包/放宽上限）")

    def test_a_package_of_only_junk_is_rejected(self):
        with self.assertRaises(g.UploadRejected):
            g.plan_inbox(["Thumbs.db", "a/desktop.ini"])

    def test_duplicate_records_are_rejected(self):
        with self.assertRaises(g.UploadRejected):
            g.plan_inbox(["a/x.txt", "a/x.txt"])

    def test_size_limits(self):
        with self.assertRaises(g.UploadRejected) as cm:
            g.plan_inbox(["big.bin"], [g.MAX_FILE_BYTES + 1])
        self.assertIn("单个文件超过", str(cm.exception))
        # 整批那条：每件都在单件上限之下，加起来超 —— 否则先撞的是单件那条，整批规则测不到
        each = g.MAX_FILE_BYTES - 1
        n = g.MAX_TOTAL_BYTES // each + 1
        self.assertLessEqual(n, g.MAX_FILES, "件数上限会先拦下，这条就测不到整批了")
        with self.assertRaises(g.UploadRejected) as cm:
            g.plan_inbox([f"f{i}.bin" for i in range(n)], [each] * n)
        self.assertIn("整批超过", str(cm.exception))

    def test_sizes_must_line_up_with_names(self):
        with self.assertRaises(g.UploadRejected):
            g.plan_inbox(["a.txt", "b.txt"], [1])

    def test_size_mismatch_fails_even_with_multiple_records(self):
        """位置对应关系错了就必须拒 —— 否则体积是按别人的名字算的，上限形同虚设。"""
        with self.assertRaises(g.UploadRejected):
            g.plan_inbox(["a.txt"], [1, 2])


class CollisionTests(unittest.TestCase):
    def test_case_insensitive_on_windows(self):
        """`A.xlsx` 与 `a.xlsx` 在 Windows 上是同一个文件 —— 必须算撞名。"""
        clash = g.collisions(["附件1/result.xlsx", "附件1/RESULT.XLSX"])
        self.assertEqual(len(clash), 1)
        self.assertEqual(sorted(next(iter(clash.values()))),
                         ["附件1/RESULT.XLSX", "附件1/result.xlsx"])

    def test_same_basename_in_different_folders_is_not_a_clash(self):
        """保住目录结构的收益：`附件3/result1.xlsx` 与 `结果/result1.xlsx` 落点不同，
        不该被当成撞名（扁平化的话两者会互相覆盖）。"""
        self.assertEqual(g.collisions(["附件3/result1.xlsx", "结果/result1.xlsx"]), {})

    def test_plan_inbox_refuses_on_clash(self):
        with self.assertRaises(g.UploadRejected) as cm:
            g.plan_inbox(["a/x.xlsx", "a/X.xlsx"])
        self.assertIn("同名冲突", str(cm.exception))




if __name__ == "__main__":
    unittest.main()
