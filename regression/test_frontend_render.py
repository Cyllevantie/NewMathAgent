"""把前端**真跑一遍**（桩 DOM + node），而不是只做字符串断言。

为什么要有这一层：纯字符串哨兵只能钉"某个字面量还在"，钉不住**行为**。有两类缺陷
它必然漏过去 ——
  · 勾选框"把后缀写进模型框"：字符串哨兵只验到"函数在、change 接了、别处没重复拼"，
    而**写回那一行**被删掉时它照样绿；桩 DOM 那条会当场变红。
  · ⓪ 重跑后确认页卡在旧读题上：纯字符串验不到"换了那份读题到底重不重画"。

两个 JS 夹具（`frontend_render_check.js` / `frontend_splash_check.js`）是**可执行的判据**：
它们把 `index.html` 里那几段函数抠出来，配上桩 `document`/`fetch`/定时器跑一遍，自己断言
（标签配平、元素齐不齐、启动门控、勾选框效果、换读题要重画），rc≠0 即失败。
依赖 `node`（仓库的 `lib/web/healthcheck.py` 早就用它做 JS 语法检查，所以这不是新依赖）。
"""
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
HERE = PROJECT / "regression"


def _run(fixture):
    node = shutil.which("node")
    if node is None:
        raise unittest.SkipTest("没有 node —— 跳过前端真跑（healthcheck 也用它，装了才有这层）")
    r = subprocess.run([node, str(HERE / fixture)], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", cwd=str(PROJECT))
    return r.returncode, (r.stdout or "") + (r.stderr or "")


class FrontendRenderTests(unittest.TestCase):
    def test_the_intake_panel_renders_balanced_and_complete(self):
        """确认页那几段真跑：四种输入下标签配平、不抛错、该有的都在、无机械残留。"""
        rc, out = _run("frontend_render_check.js")
        self.assertEqual(rc, 0, "确认页渲染夹具失败：\n" + out[-1500:])

    def test_the_splash_gates_the_main_ui_and_the_1m_box_works(self):
        """开屏页真跑：配好了才进主界面、没配好不建 SSE/不起轮询、勾选框把后缀写进模型框。"""
        rc, out = _run("frontend_splash_check.js")
        self.assertEqual(rc, 0, "开屏页夹具失败：\n" + out[-1500:])

    def test_no_top_level_lookup_runs_before_its_element_exists(self):
        """脚本顶层 `$('x')` 抓的元素必须出现在脚本标签之前。

        把赠言浮层放到 `</script>` 之后 ⇒ `$('gh_close')` 是 null ⇒ 那一行抛
        `TypeError` ⇒ **整段脚本连同 `boot()` 一起没了**：面板"什么都没了"
        （阶段列表空、日志空、SSE 不建）。这条夹具就是钉那个类别。
        """
        rc, out = _run("frontend_id_order_check.js")
        self.assertEqual(rc, 0, "标记与脚本的先后顺序不符：\n" + out[-1500:])

    def test_the_github_badge_sits_centered_with_a_closable_card(self):
        """第二排正中的 GitHub 标识 + 赠言浮层。

        「居中」这条不是靠读 CSS 猜的：夹具查 `.auxrow` 是 `1fr auto 1fr` 三栏、
          标识钉在中间那栏、**且**没有 `space-between` —— 后者会让标识
          偏离行中心 **103px**（无头 Chrome 量出来的），所以"还在不在"是会被改回去的硬判据。
        """
        rc, out = _run("frontend_github_check.js")
        self.assertEqual(rc, 0, "GitHub 标识/赠言浮层夹具失败：\n" + out[-1500:])


if __name__ == "__main__":
    unittest.main()
