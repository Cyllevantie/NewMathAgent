"""⑯ 的三维主视图：引擎夹具真跑 + SKILL/资产/交付判据三者互相对账。

分工（各管一段，不重复）：
  · `regression/demo3d_check.js`（node 直跑）—— 引擎的**行为**：投影/深度排序/网格预算/
    退化输入/通道顺序/确定性。纯字符串哨兵钉不住这些，桩画布真跑能。
  · 本文件 —— **跨文件一致性**：SKILL 真的在教三维、教的是这个资产、豁免 token 与
    `lib/delivery/checks.py` 里那条判据同一个字面量（防"文档说 A、代码 grep B"）；
    以及盘上已产出的 demo.html 是否真的逐字内联了引擎。
  · `lib/delivery/checks.demo_3d_issues` —— 交付侧的机械抓手（正式打包时跑）。
"""
import re
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
HERE = PROJECT / "regression"
sys.path.insert(0, str(PROJECT))
from lib.delivery.checks import DEMO_3D_EXEMPT_TOKEN, DEMO_3D_ENGINE, _RESOURCE_REF, _fold_eol

ENGINE = PROJECT / DEMO_3D_ENGINE
DOC = PROJECT / "skills/16Web-demo/references/scene3d.md"
SKILL = PROJECT / "skills/16Web-demo/SKILL.md"


def _run_fixture():
    node = shutil.which("node")
    if node is None:
        raise unittest.SkipTest("没有 node —— 跳过引擎真跑（healthcheck 也用它，装了才有这层）")
    r = subprocess.run([node, str(HERE / "demo3d_check.js")], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", cwd=str(PROJECT))
    return r.returncode, (r.stdout or "") + (r.stderr or "")


class EngineFixtureTests(unittest.TestCase):
    def test_the_engine_renders_and_behaves(self):
        """桩画布真跑：44 条行为断言（每条都有对照组），rc≠0 即红。"""
        rc, out = _run_fixture()
        self.assertEqual(rc, 0, "三维引擎夹具失败：\n" + out[-2000:])

    def test_the_engine_reaches_for_nothing_outside_its_text(self):
        """引擎必须自包含：复用交付检查的资源引用正则（单一事实来源），而不是另写一份。

        `.js` 不在 `test_lib_layout` 的路径扫描扩展名里 —— 它对外界的依赖只能在这里钉。
        """
        text = ENGINE.read_text(encoding="utf-8")
        refs = _RESOURCE_REF.findall(text)
        self.assertEqual(refs, [], f"引擎里出现了资源引用（内联后要么白屏、要么交付判红）：{refs[:3]}")
        self.assertNotIn("</scr" + "ipt", text, "引擎文本里不许出现结束脚本标签（内联会把 HTML 撕开）")
        self.assertNotIn("<!--", text, "引擎文本里不许出现 HTML 注释起头（内联会进入转义态）")


class SkillMandateTests(unittest.TestCase):
    """SKILL 必须真的在教三维 —— 逐字钉住判据的落脚点（改措辞可以，改口径必须过这关）。"""

    def setUp(self):
        self.text = SKILL.read_text(encoding="utf-8")

    def test_the_skill_mandates_the_3d_main_view(self):
        self.assertIn("## 动态三维模型", self.text)
        # 判据是"**每一个**带空间结构的子问题/页签都三维"（2026-10-16 用户：
        # 「这个网页好像只有第一个题有，别的题怎么没有」）——不只首屏那一个。
        self.assertIn("不只首屏那一个", self.text)
        self.assertIn("三维豁免", self.text)                     # 豁免口径在同一节里写明
        self.assertIn("不许为了三维而三维", self.text)

    def test_the_skill_carries_the_canvas_idempotency_lesson(self):
        """画布尺寸幂等 + 它的无头盲区（dpr=1 掩盖）必须留在 SKILL 里。

        这是 2026-10-16 实际事故的落点：2D 画布尺寸表按裸 id 填、查询用 "#id"，
        回退自引用 ⇒ 用户屏幕上拖两下就撑爆、几十次后白屏；无头截图 dpr=1 完全隐形。
        """
        self.assertIn("画布尺寸幂等", self.text)
        self.assertIn("force-device-scale-factor=1.25", self.text)
        self.assertIn("播放控制做成**显式 ▶ 播放 / ⏸ 暂停按钮**", self.text)

    def test_the_skill_points_at_this_engine_and_its_doc(self):
        self.assertIn(f"skills/16Web-demo/assets/{ENGINE.name}", self.text)
        self.assertIn("skills/16Web-demo/references/scene3d.md", self.text)
        self.assertTrue(ENGINE.is_file(), "SKILL 指了引擎文件，但它不在盘上")
        self.assertTrue(DOC.is_file(), "SKILL 指了 API 文档，但它不在盘上")

    def test_the_exemption_token_matches_the_delivery_check(self):
        """豁免 token 是**同一个字面量**：SKILL 教产物写什么，交付判据就认什么。"""
        self.assertIn(DEMO_3D_EXEMPT_TOKEN, self.text,
                      "SKILL 里的豁免前缀与 lib/delivery/checks.DEMO_3D_EXEMPT_TOKEN 不一致 —— "
                      "agent 写出来的行会过不了交付判据")
        doc = DOC.read_text(encoding="utf-8")
        self.assertIn("scene3d v1", doc, "API 文档缺版本号（与引擎 Scene3D.version 对账的第一环）")

    def test_healthcheck_literals_survive(self):
        """healthcheck.py 对每个阶段 SKILL 逐条断言的三样 —— 这轮编辑不许碰坏。"""
        head = self.text.split("---", 2)[1]                     # frontmatter
        self.assertIn("name: 16Web-demo", head)
        self.assertIn("allowed-tools", head)
        self.assertIn("_references/stage_discipline.md", self.text)


class ShippedDemoTests(unittest.TestCase):
    """盘上已产出的 demo.html 是否内联了引擎、是否每张三维主视图都真的挂上了场景。

    这三条与交付检查 `demo_3d_issues` 同一根判据，提前到回归层，省一次"打包才发现"。
    （历史：本类第一版写的是"预期的红" —— 当时盘上还是升级前的二维 demo，要等 ⑯ 重跑才转绿。
    2026-10-16 ⑯ 重跑后已转绿，那句话就删掉了，别让"预期失败"的注释留在绿着的测试上。）
    `demo/` 不进版本库（干净检出上它不存在）⇒ 一律 skipUnless，runner/CI 不会因缺产物炸。
    """

    @unittest.skipUnless((PROJECT / "demo/demo.html").is_file(), "没有 demo 产物（干净检出）")
    def test_the_shipped_demo_inlines_the_engine_verbatim(self):
        html = _fold_eol((PROJECT / "demo/demo.html").read_text(encoding="utf-8", errors="replace"))
        engine = _fold_eol(ENGINE.read_text(encoding="utf-8"))
        if engine not in html:
            report = (PROJECT / "reports/DEMO_REPORT.md")
            text = report.read_text(encoding="utf-8-sig", errors="replace") if report.is_file() else ""
            marked = any(line.strip().startswith(DEMO_3D_EXEMPT_TOKEN)
                         and line.strip()[len(DEMO_3D_EXEMPT_TOKEN):].strip()
                         for line in text.splitlines())
            self.assertTrue(marked, "demo.html 没有逐字内联三维引擎，且 DEMO_REPORT 里也没有"
                                    "【" + DEMO_3D_EXEMPT_TOKEN + "理由】的豁免行 —— 重跑 ⑯ "
                                    "或补一行豁免（见 skills/16Web-demo/SKILL.md「动态三维模型」）")
        # 无论走哪条路，都不许留"引擎副本"在 demo/ 里（只有 demo.html 里内联的那一份）
        for extra in (PROJECT / "demo").iterdir():
            self.assertNotEqual(extra.name, "scene3d.js", "引擎副本不许放进 demo/（交付件只认内联那一份）")

    @unittest.skipUnless((PROJECT / "demo/demo.html").is_file(), "没有 demo 产物（干净检出）")
    def test_every_shipped_3d_canvas_really_gets_a_scene(self):
        """升级后的 SKILL 要的是"**每一个**带空间结构的页签都有三维主视图"，不是只有首屏。

        （2026-10-16 用户原话：「这个网页好像只有第一个题有，别的题怎么没有」。）
        所以判据不能停在"内联了引擎"——那对一张三维图也成立。这里钉两层：
        ① 每个 `class="c3d"` 的画布都真的被 `Scene3D.create` 接管（不是摆着好看的死画布）；
        ② 这些画布分散在**至少 5 个不同的页签**里（本题三问：膜面/响应面/空时/分区/分辨率）。
        只做字符串计数、不开浏览器 —— 行为那一层由 `_tmp/demo_verify.py` 的逐状态断言管。
        """
        text = (PROJECT / "demo/demo.html").read_text(encoding="utf-8", errors="replace")
        if "Scene3D" not in text:
            self.skipTest("盘上这份还是升级前的二维 demo（等 ⑯ 重跑）—— 本条对它无从谈起")
        canvases = re.findall(r'<canvas id="([^"]+)"[^>]*class="c3d"', text)
        self.assertGreaterEqual(len(canvases), 2,
                                "只有一个三维画布 —— 升级后的 SKILL 要求每个带空间结构的页签各一张")
        created = set(re.findall(r'Scene3D\.create\(\$\("#([^"]+)"\)', text))
        self.assertEqual(set(canvases) - created, set(),
                         "这些三维画布没有挂场景（画出来是空的）：%s" % sorted(set(canvases) - created))
        # 每个三维画布所属的页签（往回找最近的 <section id="vN" class="view…">）。
        # `class="view on"` 也要认 —— 首屏那个 section 是 `view on`，只写 `"view"` 会漏掉它，
        # 漏掉之后 owner 里多出一个 None，把 None 也算进"页签数"会让这条断言假绿（实测踩过）。
        owner = {}
        for cv in canvases:
            head = text[:text.index('id="%s"' % cv)]
            sec = re.findall(r'<section id="(v\d+)" class="view[^"]*"', head)
            owner[cv] = sec[-1] if sec else None
        self.assertNotIn(None, owner.values(), "有三维画布不在任何页签里：%s" % owner)
        self.assertGreaterEqual(len(set(owner.values())), 5,
                                "三维主视图只落在 %d 个页签里：%s" % (len(set(owner.values())), owner))

    @unittest.skipUnless((PROJECT / "demo/demo.html").is_file(), "没有 demo 产物（干净检出）")
    def test_the_shipped_demo_freezes_time_and_camera_in_the_hash(self):
        """三维截图的"可复现"前提：时间定格与相机都走 hash（`t=`/`play=`/`az=`）。"""
        text = (PROJECT / "demo/demo.html").read_text(encoding="utf-8", errors="replace")
        if "Scene3D" not in text:
            self.skipTest("盘上这份还是升级前的二维 demo（等 ⑯ 重跑）—— 本条对它无从谈起")
        for key in ("&t=", "play=", "az="):
            self.assertIn(key, text, f"三维 demo 的深链里缺 {key!r} —— 无头截图复现不出来")


if __name__ == "__main__":
    unittest.main()
