# -*- coding: utf-8 -*-
"""出图后的两道机器闸门：**位图三查** 与 **图例压数据**。

`q1_profiles` 左面板的图例是 `legend(ncol=2, loc="upper left")`，而 `charts.style()`
全局设了 `legend.frameon: False` —— 图例**没有底色**，曲线直接从 `t = 1200 s` /
`t = 1800 s` 两行字上穿过去，标签读不出来；两列排布还让 `数值解 1800 s` 与
`级数解 1800 s` 挤成一行。人眼一看就废，机器却查不出来 —— `export()` 只管字号与
出画布，管不到"图例盖住数据"，所以这一条要单独守。

位图三查：分辨率下限 / 近似纯色 / 边界暗像素比例。

纯离线：造图 → 调 `visualization.quality`，不需要 `figures/` 里任何真图。
"""
import contextlib
import io
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))
from PIL import Image  # noqa: E402

import lib.visualization.charts as charts  # noqa: E402
import lib.visualization.evidence as ev  # noqa: E402
from lib.visualization.quality import (inspect_png, legend_data_overlap, near_monochrome,
                                    texts_overlap)  # noqa: E402


def _nm(path):
    """近乎单色检测的薄封装（测试里反复用）。"""
    return near_monochrome(path)

FAN = [(100, 2.32), (300, 2.20), (600, 2.06), (900, 1.90), (1200, 1.72), (1800, 1.52)]


def _field(x, low):
    """**先平后降** —— 真实的水分浓度剖面就是这样：r < 1.0 上六个时刻全平在 2.55。

    这个形状是关键：一路向右抬升的曲线在左上角本就空着，盖不住图例。
    """
    return 2.55 - (2.55 - low) * np.clip(x - 1.0, 0, 1) ** 2


class LegendOverlapTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def _figure(self, loc, *, labels=None, ncol=2):
        ctx = charts.style()
        settings = ctx.__enter__()
        self.addCleanup(lambda: ctx.__exit__(None, None, None))
        x = np.linspace(0, 2, 200)
        fig = charts.canvas(settings)
        ax = fig.add_subplot(111)
        for t, low in FAN:
            lb = (labels or "t = {t} s").format(t=t)
            charts.trend(ax, x, _field(x, low), label=lb)
        ax.set_xlabel("到药材中心的距离 / cm")
        ax.set_ylabel("水分浓度 / (kg/kg)")
        ax.legend(ncol=ncol, loc=loc)
        return fig, settings

    def test_a_legend_that_sits_on_the_curves_is_reported(self):
        """左上角两列图例落在"平的那一段"曲线上 —— 就是要报的形状。"""
        fig, _ = self._figure("upper left")
        issues = legend_data_overlap(fig)
        self.assertTrue(issues, "图例明明压在曲线上，却没报")
        self.assertIn("图例压住曲线", issues[0])
        self.assertIn("t = 100 s", issues[0], "要点名是哪几条，不然不知道往哪挪")
        self.assertIn("点", issues[0], "要给出压住的量级")

    def test_a_legend_in_an_empty_corner_is_not_reported(self):
        """不能全量误报 —— 图例待在空角落就该放行。"""
        ctx = charts.style()
        settings = ctx.__enter__()
        self.addCleanup(lambda: ctx.__exit__(None, None, None))
        x = np.linspace(0, 2, 200)
        fig = charts.canvas(settings)
        ax = fig.add_subplot(111)
        # 曲线**从左上往右下**降，右上角是空的，图例放右上角
        for t, low in FAN:
            charts.trend(ax, x, _field(x, low) + 0.6 * (1 - x / 2), label=f"t = {t} s")
        ax.legend(ncol=2, loc="lower left")
        self.assertEqual(legend_data_overlap(fig), [])

    def test_a_figure_without_a_legend_is_clean(self):
        ctx = charts.style()
        settings = ctx.__enter__()
        self.addCleanup(lambda: ctx.__exit__(None, None, None))
        fig = charts.canvas(settings)
        ax = fig.add_subplot(111)
        charts.trend(ax, np.linspace(0, 2, 50), np.linspace(0, 1, 50), label="a")
        self.assertEqual(legend_data_overlap(fig), [])


class PngQualityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.settings = {"quality": {"minimum_width_px": 800, "minimum_height_px": 480,
                                     "maximum_dark_border_ratio": 0.35}}

    def _png(self, name, size, color="white", ink=None):
        p = self.root / name
        img = Image.new("RGB", size, color)
        if ink:
            for xy in ink:
                img.putpixel(xy, (0, 0, 0))
        img.save(p)
        return p

    def test_a_resolution_below_the_floor_is_an_error(self):
        errs, _ = inspect_png(self._png("small.png", (400, 300), ink=[(10, 10)]),
                              self.settings, figure_id="f")
        self.assertTrue(any("400x300" in e for e in errs), errs)

    def test_a_near_blank_bitmap_is_an_error(self):
        """峰谷差 < 3 判纯色 —— 图渲染成空白时唯一的机器信号。"""
        errs, _ = inspect_png(self._png("blank.png", (1000, 600)), self.settings,
                              figure_id="f")
        self.assertTrue(any("纯色" in e for e in errs), errs)

    def test_a_dark_border_is_a_warning_not_an_error(self):
        """边界暗像素是**启发式**，只提醒不挡 —— 误伤真图不值当。

        注意阈值是 0.35：**只暗一条边**（1/3.2 ≈ 31%）就不该报 —— 这条同时钉住了
        "边距不是越小越好"，乱调低阈值会让正常带边框的图全红。
        """
        p = self.root / "dark.png"
        img = Image.new("RGB", (1000, 600), "white")
        for x in range(1000):                       # 上下两边全黑 → 边框暗像素 2000/3200
            img.putpixel((x, 0), (0, 0, 0))
            img.putpixel((x, 599), (0, 0, 0))
        img.save(p)
        errs, warns = inspect_png(p, self.settings, figure_id="f")
        self.assertEqual(errs, [])
        self.assertTrue(any("边界暗像素" in w for w in warns), warns)

    def test_one_dark_edge_alone_stays_below_the_warning_threshold(self):
        p = self.root / "one_edge.png"
        img = Image.new("RGB", (1000, 600), "white")
        for x in range(1000):
            img.putpixel((x, 0), (0, 0, 0))          # 只有上面一条 → 1000/3200 ≈ 31%
        img.save(p)
        errs, warns = inspect_png(p, self.settings, figure_id="f")
        self.assertEqual(errs, [])
        self.assertEqual(warns, [])

    def test_a_healthy_bitmap_passes_clean(self):
        ctx = charts.style()
        settings = ctx.__enter__()
        self.addCleanup(lambda: ctx.__exit__(None, None, None))
        fig = charts.canvas(settings)
        ax = fig.add_subplot(111)
        x = np.linspace(0, 2, 200)
        for t, low in FAN:
            charts.trend(ax, x, _field(x, low), label=f"t = {t} s")
        out = self.root / "ok.png"
        fig.savefig(out, dpi=settings["dpi"], facecolor="white")
        errs, warns = inspect_png(out, settings, figure_id="f")
        self.assertEqual(errs, [])
        self.assertEqual(warns, [])

    def test_a_missing_bitmap_is_an_error(self):
        errs, _ = inspect_png(self.root / "nope.png", self.settings, figure_id="f")
        self.assertTrue(any("不存在" in e for e in errs), errs)


class EdgeBandTests(unittest.TestCase):
    """「单侧贴边非白带」判据。

    `fig_roadmap` 的 .drawio 里两个**实心浅灰矩形**（`#E2E8F0`、`strokeColor=none`）
    拼成 L 形底块 —— 左带 47 px / 顶带 28 px，右/下干净。白底正文里活像一副没对齐的
    边框。只数"暗"像素的判据（`border.mean(axis=1) < 32`）对它天生失明：这个灰是 232.7
    ⇒ 0 error / 0 warning 全量放行。
    """

    GREY = (226, 232, 240)      # 就是 .drawio 里的 #E2E8F0

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.settings = {"quality": {"minimum_width_px": 200, "minimum_height_px": 150,
                                     "maximum_dark_border_ratio": 0.35}}

    def _png(self, name, draw):
        img = Image.new("RGB", (1000, 600), "white")
        draw(img)
        p = self.root / name
        img.save(p)
        return p

    def _bands_warning(self, path):
        errs, warns = inspect_png(path, self.settings, figure_id="f")
        self.assertEqual(errs, [], errs)
        return [w for w in warns if "贴着非白底块" in w]

    def test_a_partial_edge_band_is_flagged(self):
        """左 + 上有底块、右 + 下干净 ⇒ 报（就是流程图的形状）。"""
        def draw(img):
            for y in range(600):
                for x in range(40):
                    img.putpixel((x, y), self.GREY)
            for x in range(1000):
                for y in range(30):
                    img.putpixel((x, y), self.GREY)
        warns = self._bands_warning(self._png("l_shape.png", draw))
        self.assertEqual(len(warns), 1, warns)
        self.assertIn("左40px", warns[0])
        self.assertIn("上30px", warns[0])
        self.assertIn("右、下干净", warns[0])

    def test_a_thin_axis_spine_is_not_a_band(self):
        """反向守卫：matplotlib 默认的**左+下轴线**只有 1~2 px，不许误伤。

        （这正是判据里那条 `EDGE_MIN_WIDTH = 6` 的用处 —— 只看"非白"会把每条轴线都算成带。）
        """
        def draw(img):
            for y in range(600):
                for x in range(2):
                    img.putpixel((x, y), (0, 0, 0))
            for x in range(1000):
                for y in range(598, 600):
                    img.putpixel((x, y), (0, 0, 0))
        self.assertEqual(self._bands_warning(self._png("spines.png", draw)), [])

    def test_a_full_frame_is_not_flagged(self):
        """四边都贴 = 有意画的框，不报 —— 要拦的是"左+上有、右+下没有"这种半拉子。"""
        def draw(img):
            for y in range(600):
                for x in list(range(12)) + list(range(988, 1000)):
                    img.putpixel((x, y), self.GREY)
            for x in range(1000):
                for y in list(range(12)) + list(range(588, 600)):
                    img.putpixel((x, y), self.GREY)
        self.assertEqual(self._bands_warning(self._png("frame.png", draw)), [])

    def test_a_clean_bitmap_has_no_band_warning(self):
        """干净图 = 四边留白（有内容但不是贴边带）。注意得**有墨**：整幅纯白会先被
        「近似纯色」那道判死，走不到这一查。"""
        def draw(img):
            for y in range(200, 400):
                for x in range(300, 700):
                    img.putpixel((x, y), (30, 30, 30))
        self.assertEqual(self._bands_warning(self._png("clean.png", draw)), [])


class StyleDefaultsTests(unittest.TestCase):
    def test_the_legend_has_a_background_by_default(self):
        """全局 `legend.frameon: False` 让图例没有底色，曲线穿字而过 —— 默认必须是 True。

        这条钉住默认值 —— 谁要改回 False，得先解释怎么保证图例永远落不到数据上。
        """
        import matplotlib as mpl
        with charts.style():
            self.assertTrue(mpl.rcParams["legend.frameon"],
                            "图例必须有底色，否则曲线会从标签上穿过去")
            self.assertGreaterEqual(mpl.rcParams["legend.framealpha"], 0.8)

    def test_the_config_declares_the_chart_mix_doctrine(self):
        """别把每张图都画成折线 —— 二维场该先想热力图/等高线。"""
        import json
        cfg = json.loads((PROJECT / "config/visualization.json").read_text(encoding="utf-8"))
        self.assertIn("heatmap", cfg["chart_mix"]["field_over_spacetime"])
        self.assertTrue(cfg["chart_mix"]["require_one_non_line_per_question"])
        self.assertEqual(cfg["quality"]["minimum_width_px"], 800)



class DrawioLayoutTests(unittest.TestCase):
    """`check_layout.py` 的两类豁免与它们带来的盲区。

    `fig_roadmap` 里
        b4_mid    value="统一判据/最坏情形/横向可比"  y 845–900   （裸文字标签）
        b4_double shape=doubleArrow（那条 ↔）          y 894–917   （实体形状）
    两者真的相交，箭杆从「横向可比」三个字上压过去，而体检报 `FAIL 0 WARN 0`。

    成因：裸文字刻意不进 `solid` 重叠矩阵（"文字压在背景块上属正常"的豁免），
    于是**任何东西盖住它们都没人管**。要补的是"裸文字 vs 实体盒/连线"这条判据，
    同时**必须保住另外两条豁免**（背景块、文字压文字），否则会全量误报。
    """

    CHECKER = PROJECT / "skills/paper-diagram/scripts/check_layout.py"

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def _drawio(self, cells):
        body = "".join(cells)
        return ("<mxfile><diagram><mxGraphModel pageWidth='850' pageHeight='1100'><root>"
                "<mxCell id='0'/><mxCell id='1' parent='0'/>" + body +
                "</root></mxGraphModel></diagram></mxfile>")

    def _vertex(self, cid, x, y, w, h, style, value=""):
        return (f"<mxCell id='{cid}' value='{value}' style='{style}' "
                f"vertex='1' parent='1'><mxGeometry x='{x}' y='{y}' "
                f"width='{w}' height='{h}' as='geometry'/></mxCell>")

    BARE = "text;html=1;strokeColor=none;fillColor=none;fontSize=16;"
    SOLID = "rounded=0;whiteSpace=wrap;html=1;fillColor=#ffffff;strokeColor=#333333;fontSize=16;"

    def _run(self, name, cells):
        f = self.root / f"{name}.drawio"
        f.write_text(self._drawio(cells), encoding="utf-8")
        proc = subprocess.run([sys.executable, str(self.CHECKER), str(f)],
                              capture_output=True, text=True, encoding="utf-8",
                              errors="replace")
        return proc.returncode, (proc.stdout or "") + (proc.stderr or "")

    def test_a_solid_shape_covering_bare_text_fails(self):
        """实体形状压在没有底色的文字上 —— 必须报的形状。"""
        rc, out = self._run("solid_over_text", [
            self._vertex("lbl", 448, 845, 95, 55, self.BARE, "统一判据"),
            self._vertex("arr", 442, 894, 82, 23,
                         "shape=doubleArrow;html=1;fillColor=#f2f2f2;strokeColor=#333333;", ""),
        ])
        self.assertEqual(rc, 1, out)
        self.assertIn("盖住文字", out)
        self.assertIn("统一判据", out)

    def test_a_background_block_is_still_exempt(self):
        """背景块豁免必须保住：`strokeColor=none` + **有 fillColor** 是背景块，
        被实体形状压住是**设计意图**，不许报 —— 报了这一条，整张图会全量误报。"""
        rc, out = self._run("bg_ok", [
            self._vertex("bg", 100, 100, 300, 200,
                         "rounded=1;html=1;strokeColor=none;fillColor=#eef4fb;fontSize=16;", "底色说明"),
            self._vertex("box", 150, 150, 120, 40, self.SOLID, "实体盒"),
        ])
        self.assertEqual(rc, 0, out)

    def test_two_bare_text_labels_may_overlap(self):
        """文字压文字是排版常态，不许报。"""
        rc, out = self._run("text_ok", [
            self._vertex("t1", 100, 100, 120, 30, self.BARE, "甲"),
            self._vertex("t2", 110, 105, 120, 30, self.BARE, "乙"),
        ])
        self.assertEqual(rc, 0, out)

    def test_a_label_with_an_opaque_background_may_be_covered(self):
        """有 `labelBackgroundColor` 的标签，线会被挡住、字仍可读 —— 放行。"""
        rc, out = self._run("lblbg_ok", [
            self._vertex("lbl", 100, 100, 120, 30,
                         self.BARE + "labelBackgroundColor=#ffffff;", "有底"),
            self._vertex("box", 100, 100, 120, 30, self.SOLID, "实体盒"),
        ])
        self.assertEqual(rc, 0, out)

    def test_the_repo_template_passes_its_own_checker(self):
        """模板生成的路线图**必须过自己的体检** —— 那条 ↔ 压字正是要拦的形状。"""
        content = PROJECT / "figures/fig_roadmap.content.json"
        if not content.is_file():
            self.skipTest("没有路线图内容文件")
        out_drawio = self.root / "roadmap.drawio"
        gen = PROJECT / "skills/paper-diagram/scripts/roadmap_5band.py"
        proc = subprocess.run([sys.executable, str(gen), str(content), "-o", str(out_drawio)],
                              capture_output=True, text=True, encoding="utf-8",
                              errors="replace", cwd=str(PROJECT))
        self.assertEqual(proc.returncode, 0, (proc.stdout or "") + (proc.stderr or ""))
        rc, out = self._run_direct(out_drawio)
        self.assertEqual(rc, 0, out)

    def _run_direct(self, f):
        proc = subprocess.run([sys.executable, str(self.CHECKER), str(f)],
                              capture_output=True, text=True, encoding="utf-8",
                              errors="replace")
        return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


class StrayFigureScriptTests(unittest.TestCase):
    """画图脚本住 `code/` 下要**提醒**（只提醒、不拦）。

    典型形状：④编码计算 把 `make_figures.py` 写到 `code/` 下，
    `figures/manifest.json` 里登记的 `script` 也是它。危害不是"文件放错地方"这么轻 ——
    `code/` 在 ⑤⑥⑦⑧ 的**输入指纹**里，而图的内容不含任何数值结论 ⇒ 在那个工作区里
    "改一行画图代码"与"改求解器"在驱动眼里**没有区别**，改配色就连锁重跑下游。
    `figures/` 刻意不进任何阶段的指纹，所以正解是让脚本住 `figures/`。

    在库里加提醒而不是在门禁里判死：登记本身没错，搬个家就好；判死会把一次
    已经在飞的阶段当场打死。`register()` 报一次（防新增），`audit()` 每次也报
    （**已登记过的那笔**光靠 register 那次就再也不响了，而它正是不改就一直拖着的那个）。
    """

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "config").mkdir()
        shutil.copy2(PROJECT / "config/visualization.json",
                     self.root / "config/visualization.json")
        shutil.copytree(PROJECT / "lib" / "visualization",
                        self.root / "lib" / "visualization")
        (self.root / "figures").mkdir()
        (self.root / "code").mkdir()
        for name in ("figures/make.py", "code/make.py"):
            (self.root / name).write_text("# 画图脚本\n", encoding="utf-8")
        for fid in ("fig_a",):
            for suf in (".pdf", ".png", ".svg"):
                (self.root / "figures" / f"{fid}{suf}").write_bytes(b"%PDF-1.4 " + b"x" * 120)
            (self.root / "figures" / f"{fid}.src").write_text("src", encoding="utf-8")

    def _reg(self, script):
        return ev.register(self.root, "fig_a",
                           artifacts=[f"figures/fig_a{s}" for s in (".pdf", ".png", ".svg")],
                           sources=["figures/fig_a.src"], script=script,
                           claim="结论", caption="图注", width_mm=80)

    def _capture(self, fn):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            out = fn()
        return out, buf.getvalue()

    def test_register_warns_when_the_script_lives_under_code(self):
        _, log = self._capture(lambda: self._reg("code/make.py"))
        self.assertIn("住在 `code/` 下", log, "脚本住 code/ 下没提醒 —— 改配色又会连锁重跑下游")

    def test_register_is_silent_for_a_script_under_figures(self):
        _, log = self._capture(lambda: self._reg("figures/make.py"))
        self.assertNotIn("住在 `code/` 下", log, "住在 figures/ 下是正解，不该报警")

    def test_audit_keeps_reporting_an_already_registered_stray(self):
        """已登记过的旧账每次 audit 都要再报一次，而且**只提醒不进 issues**。

        这条钉两件事：① 光靠 `register()` 的提醒，对**已经写进 manifest** 的那笔旧账
        永远不响（它正是拖着连锁重跑的那一笔）；② 提醒**不许**变成硬失败 ——
        否则一次已经在飞的 ⑦/⑧ 会被一条"文件位置"当场打死。
        """
        self._reg("figures/make.py")
        ev._mutate(self.root, lambda d: d["figures"]["fig_a"].__setitem__("script", "code/make.py"))
        issues, log = self._capture(lambda: ev.audit(self.root))
        self.assertIn("住在 `code/` 下", log, "旧账没被再报一次")
        self.assertFalse([i for i in issues if "住在 `code/` 下" in i],
                         f"提醒被写进了 issues ⇒ 会把在飞的阶段判死：{issues}")


class ManifestLostUpdateTests(unittest.TestCase):
    """`figures/manifest.json` 不许丢更新。

    `register`/`review` 若按「进来读一份快照 → 改 → 整份写回」来写就会丢更新。平时写者
    只有一个（画图脚本逐张 register），但**重画那一轮不是** —— `make_figures.run()` 连着
    register 8 张，而 ⑨ 的「重画图的口子」也可能在同一工作区跑。两个快照交叠时，后写的
    那个会把中间 register 的那几条**整段抹掉**；`audit` 随后报「未登记图表」（文件在盘上、
    registry 里没有），看起来像**图丢了**，其实是**登记**丢了 —— 与"回退清空 figures/"
    完全是两回事。`write_json` 本来就是原子的，所以这里防的不是写坏，是丢更新。
    """

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        # `snapshot()` 会哈希 `config/visualization.json` 与 `lib/visualization/*.py` —— 沙盒里
        # 缺了它们，register 会在读文件时抛 FileNotFoundError。
        (self.root / "config").mkdir()
        shutil.copy2(PROJECT / "config/visualization.json",
                     self.root / "config/visualization.json")
        shutil.copytree(PROJECT / "lib" / "visualization",
                        self.root / "lib" / "visualization")
        (self.root / "figures").mkdir()
        (self.root / "figures/make.py").write_text("# 画图脚本\n", encoding="utf-8")
        self.assets = []
        for fid in ("fig_a", "fig_b", "fig_c"):
            for suf in (".pdf", ".png", ".svg"):
                p = self.root / "figures" / f"{fid}{suf}"
                p.write_bytes(b"%PDF-1.4 " + b"x" * 120)
                self.assets.append(f"figures/{fid}{suf}")
            (self.root / "figures" / f"{fid}.src").write_text("src", encoding="utf-8")

    def _reg(self, fid):
        return ev.register(self.root, fid,
                           artifacts=[f"figures/{fid}{s}" for s in (".pdf", ".png", ".svg")],
                           sources=[f"figures/{fid}.src"], script="figures/make.py",
                           claim=f"{fid} 的结论", caption=f"{fid} 的图注", width_mm=80)

    def _ids(self):
        return sorted(ev.load(self.root)["figures"])

    def test_registrations_one_after_another_accumulate(self):
        """顺序登记不丢（**真正咬住 lost update 的是下面并发那条**）。

        说清楚：`register` 是**函数式**的（没有"持有旧快照的对象"），所以顺序调用本来就
        不会丢 —— 这条守的是"别改成重置整份"这个底线，不是复现 lost update。
        只有 `test_concurrent_registrations_*` 那种快照交叠的时序才会让它露头。
        """
        self._reg("fig_b")
        self._reg("fig_a")
        self.assertEqual(self._ids(), ["fig_a", "fig_b"], "登记丢了 —— 谁把整份重置了？")

    def test_many_registrations_in_a_row_keep_every_entry(self):
        """一次重画就是连着 8 张 —— 顺序登记完必须 8 条都在。"""
        for i in range(8):
            fid = f"fig_r{i}"
            for suf in (".pdf", ".png", ".svg"):
                (self.root / "figures" / f"{fid}{suf}").write_bytes(b"%PDF-1.4 " + b"y" * 120)
            (self.root / "figures" / f"{fid}.src").write_text("s", encoding="utf-8")
            ev.register(self.root, fid,
                        artifacts=[f"figures/{fid}{s}" for s in (".pdf", ".png", ".svg")],
                        sources=[f"figures/{fid}.src"], script="figures/make.py",
                        claim="c", caption="图注够长就行", width_mm=80)
        got = self._ids()
        self.assertEqual(len(got), len(set(got)))
        self.assertTrue(all(f"fig_r{i}" in got for i in range(8)), got)

    def test_concurrent_registrations_keep_every_entry(self):
        """真并发：多线程同时 register，一条都不许丢。"""
        import concurrent.futures
        n = 12
        for i in range(n):
            fid = f"fig_c{i}"
            for suf in (".pdf", ".png", ".svg"):
                (self.root / "figures" / f"{fid}{suf}").write_bytes(b"%PDF-1.4 " + b"z" * 120)
            (self.root / "figures" / f"{fid}.src").write_text("s", encoding="utf-8")
        with concurrent.futures.ThreadPoolExecutor(max_workers=n) as ex:
            list(ex.map(lambda i: ev.register(
                self.root, f"fig_c{i}",
                artifacts=[f"figures/fig_c{i}{s}" for s in (".pdf", ".png", ".svg")],
                sources=[f"figures/fig_c{i}.src"], script="figures/make.py",
                claim="c", caption="图注够长就行", width_mm=80), range(n)))
        got = self._ids()
        self.assertEqual(len(got), n, f"并发登记丢了 {n - len(got)} 条：{got}")

    def test_review_refuses_when_the_entry_is_stale(self):
        """复核的校验也要在锁内对着刚读进来的那条做 —— 别替一张没看过的图签字。"""
        self._reg("fig_a")
        (self.root / "figures/fig_a.pdf").write_bytes(b"%PDF-1.4 " + b"CHANGED" * 40)
        with self.assertRaises(ValueError):
            ev.review(self.root, "fig_a", reviewer="我", note="目检过了没有重叠问题")


class HeatmapColorbarTests(unittest.TestCase):
    """连续量热力图**必须画色标**。

    `heatmap()` 的 `colorbar_label` 是**必填**关键字参数 —— 每个调用方都得传 —— 但只有
    `correlation=True` 与**分类**两支会真画色标，连续量那一支会把它**静默丢掉**：⑧绘图门禁
    据此逮到 `q1_field`/`q2_field`/`q3_field`/`q4_field` 四张场图一个色标都没有，
    而 `figures/make_figures.py` 在 7 处都老实传了 `colorbar_label`。

    配套更要命：格子数 > 60 时 `annotate` 默认关闭 —— 143/121 格的场图于是
    **既无色标又无格内数字**，读者没有任何途径把颜色读回数值。
    `response()` 却画色标 → 同一批交付里前后不一致，本身就是缺陷信号。
    """

    def _draw(self, **kw):
        ctx = charts.style()
        settings = ctx.__enter__()
        self.addCleanup(lambda: ctx.__exit__(None, None, None))
        fig = charts.canvas(settings)
        ax = fig.add_subplot(111)
        a = np.arange(12.0).reshape(3, 4) * 1.7      # 12 个互异值 → 连续量
        charts.heatmap(ax, a, ["r0", "r1", "r2"], ["c0", "c1", "c2", "c3"],
                       colorbar_label="浓度 / (kg/kg)", **kw)
        return fig, ax

    def test_a_continuous_heatmap_draws_a_colorbar(self):
        fig, _ = self._draw()
        self.assertTrue(fig.axes[1:], "连续量热力图没画色标 —— colorbar_label 被静默丢了")
        # colorbar 的标签落在它那条轴的 **yaxis label** 上（不是 `Axes.label`，那个属性不存在）
        self.assertTrue(any("浓度" in (b.get_ylabel() or "") for b in fig.axes[1:]),
                        "色标画了，但没有把 colorbar_label 用上")

    def test_a_categorical_heatmap_still_draws_one(self):
        ctx = charts.style()
        settings = ctx.__enter__()
        self.addCleanup(lambda: ctx.__exit__(None, None, None))
        fig = charts.canvas(settings)
        ax = fig.add_subplot(111)
        charts.heatmap(ax, np.array([[0, 1], [2, 1]]), ["a", "b"], ["c", "d"],
                       colorbar_label="方案")
        self.assertTrue(fig.axes[1:], "分类热力图的色标也不许丢")

    def test_a_correlation_heatmap_is_not_double_drawn(self):
        """`correlation=True` 那支本来就画色标 —— 加了新的一支后不许变成两个。"""
        ctx = charts.style()
        settings = ctx.__enter__()
        self.addCleanup(lambda: ctx.__exit__(None, None, None))
        fig = charts.canvas(settings)
        ax = fig.add_subplot(111)
        a = np.array([[1.0, .3], [.3, 1.0]])
        charts.heatmap(ax, a, ["x", "y"], ["x", "y"], colorbar_label="r", correlation=True)
        self.assertEqual(len(fig.axes[1:]), 1, "相关系数矩阵画了两个色标")


class DrawioCheckerCrashTests(unittest.TestCase):
    """体检脚本**自己崩了** ≠ 图不合格。

    症状：`fig_roadmap` 被 ⑧ 判成「版式体检不过（rc=1）」，而那条消息里**一条 FAIL 行都
    没有**；同一份 drawio、同一个脚本手工跑却是 rc=0。真检出问题时会带 FAIL 行，
    所以"**没有 FAIL 行的非零 rc**"必是脚本级故障（读取时撞上写入/杀毒之类的瞬时失败）。

    放行**必须 return []**：若改成返回一条 message，`audit()` 会把它并进 issues →
    照样判 FAIL，等于没放行。可见性靠 stderr。
    """

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "figures").mkdir()
        (self.root / "skills/paper-diagram/scripts").mkdir(parents=True)
        (self.root / "figures/x.drawio").write_text("<mxfile/>", encoding="utf-8")

    def _entry(self):
        return {"script": "figures/x.drawio", "artifacts": [], "sources": [],
                "review": {"status": "pending"}, "auto_issues": []}

    def _with_checker(self, body):
        # 桩必须自己把 stdout 定成 UTF-8：真脚本都带
        #   `sys.stdout.reconfigure(encoding="utf-8")`（与 `lib/delivery/__main__.py`、
        #   `lib/web/healthcheck.py` 同一处置），而**桩没有** ⇒ 它按 cp936 输出、而测试按
        #   utf-8 解 ⇒ 中文断言变乱码。这是脚手架的脆弱点，不是产品缺陷：给桩补上同一段，
        #   测试就不再依赖 `PYTHONIOENCODING=utf-8` 这种外部环境变量。
        prologue = ("import sys\n"
                    "try:\n"
                    "    sys.stdout.reconfigure(encoding='utf-8', errors='replace')\n"
                    "except Exception:\n"
                    "    pass\n")
        (self.root / "skills/paper-diagram/scripts/check_layout.py").write_text(
            prologue + body, encoding="utf-8")

    def test_a_crashing_checker_passes_and_warns_on_stderr(self):
        """脚本抛异常 → rc=1 且无 FAIL 行 → 放行（返回 []），stderr 留痕。"""
        self._with_checker("import sys\nraise RuntimeError('boom')\n")
        buf = io.StringIO()
        with contextlib.redirect_stderr(buf):
            out = ev._drawio_layout_issues(self.root, "x", self._entry())
        self.assertEqual(out, [], "崩了的体检被当成了'图不合格' —— 一次瞬时故障就卡住整条链")
        self.assertIn("未能完成", buf.getvalue(), "放行可以，但必须留痕")

    def test_a_real_fail_still_reports(self):
        """对照组：真检出问题（有 FAIL 行）必须照旧报出来。"""
        self._with_checker("import sys\nprint('  FAIL  A 盖住文字 B')\nsys.exit(1)\n")
        out = ev._drawio_layout_issues(self.root, "x", self._entry())
        self.assertTrue(out and "盖住文字" in out[0], out)

    def test_a_missing_drawio_source_is_still_reported(self):
        """源文件不在盘上仍是真问题（那条消息带文件名，能查）。"""
        (self.root / "figures/x.drawio").unlink()
        out = ev._drawio_layout_issues(self.root, "x", self._entry())
        self.assertTrue(out and "不在盘上" in out[0], out)


class QuantityCmapAndSurfaceTests(unittest.TestCase):
    """色阶按**物理量**取 与 三维**数据曲面**家族。

    症状：同一批交付里 8 个连续量面板全是 viridis（蓝→黄）。"颜色单调"只是表面，
    真正的问题是**语义反了** —— 温度场用 viridis 时冷=亮黄、热=暗紫，得读数值才知道
    哪边热。成因是"选色阶"这件事压在每个画图者身上，而多数人不会去选 → 给他 `quantity=`：
    报出"这是什么量"，色阶由 `config/visualization.json` 的 `quantity_cmap` 登记处给，
    跨图、跨小问一致。

    另一半是三维数据曲面：每个画图者各写各的 `plot_surface`，于是
    "低值平台是淡色、铺在白底上糊成一块"**每题重犯一次**，
    而修法（细网格边 + 抽稀 + 放大盒子）住在某个脚本里、下一题带不走 → `surface3d()`。
    """

    def _style(self):
        ctx = charts.style()
        settings = ctx.__enter__()
        self.addCleanup(lambda: ctx.__exit__(None, None, None))
        return settings

    def _field(self):
        x = np.linspace(0.0, 2.0, 21)
        y = np.linspace(0.0, 72.0, 73)
        return x, y, 2.55 * np.exp(-np.meshgrid(x, y)[1] / 8.0)

    def _heatmap_cmap(self, quantity):
        fig = charts.canvas(self._style())
        ax = fig.add_subplot(111)
        charts.heatmap(ax, np.arange(12.0).reshape(3, 4) * 1.7, ["r0", "r1", "r2"],
                       ["c0", "c1", "c2", "c3"], colorbar_label="量", quantity=quantity)
        return ax.images[0].cmap.name

    def _surface_ax(self, **kw):
        fig = charts.canvas(self._style(), width_mm=90, height_mm=90)
        ax = fig.add_subplot(111, projection="3d")
        x, y, z = self._field()
        charts.surface3d(ax, x, y, z, colorbar_label="C / (kg/kg)", quantity="moisture", **kw)
        return ax

    def test_two_different_quantities_never_share_a_cmap(self):
        self.assertNotEqual(self._heatmap_cmap("temperature"), self._heatmap_cmap("moisture"),
                            "两个不同物理量又画成了同一种色阶 —— 这正是实缺陷")

    def test_the_temperature_scale_is_aligned_with_intuition(self):
        """温度必须"越大越亮/暖"：viridis 的冷=亮黄、热=暗紫与人对热的直觉相反。"""
        self.assertEqual(self._heatmap_cmap("temperature"), "inferno")

    def test_an_unregistered_quantity_warns_instead_of_silently_passing(self):
        """名字写错/没登记时**发告警**，不静默退回 —— 静默正是"换了色却没人发现"的成因。"""
        with self.assertWarns(UserWarning):
            self.assertIsNone(charts.quantity_cmap("vorticity"))

    def test_an_explicit_cmap_still_wins(self):
        """登记处是**默认**不是强制：既有脚本要写死色阶仍可以，不必全部重写。"""
        fig = charts.canvas(self._style())
        ax = fig.add_subplot(111)
        charts.heatmap(ax, np.arange(12.0).reshape(3, 4), ["r0", "r1", "r2"],
                       ["c0", "c1", "c2", "c3"], colorbar_label="量",
                       quantity="temperature", cmap="magma")
        self.assertEqual(ax.images[0].cmap.name, "magma")

    def test_response_takes_a_quantity_too(self):
        """响应面与热力图是同一族的口径，色阶不该两套。"""
        fig = charts.canvas(self._style())
        ax = fig.add_subplot(111)
        x = np.linspace(0, 1, 5)
        charts.response(ax, x, x, np.add.outer(x, x), colorbar_label="C", quantity="moisture")
        # 断言**取自登记表**（不写死色阶名 —— 那是登记表的内容，换配色测试不该碎）
        want = charts.quantity_cmap("moisture")
        name = want if isinstance(want, str) else want.name
        self.assertEqual(ax.collections[0].cmap.name, name)

    def test_the_surface_family_turns_mesh_edges_on_by_default(self):
        """细网格边是这个家族的**默认**：淡色平台没有它就会糊在白底上。"""
        ax = self._surface_ax()
        surf = [c for c in ax.collections if hasattr(c, "get_edgecolor")]
        self.assertTrue(surf, "没画出曲面")
        ec = np.asarray(surf[0].get_edgecolor())
        self.assertEqual(ec.dtype.kind, "f",
                         f"网格边被关掉了（edgecolor={ec.ravel()[0]}）—— 淡色平台又会糊在白底上")
        self.assertLess(float(ec.reshape(-1, 4)[:, :3].mean()), 0.95)
        self.assertGreater(float(np.asarray(surf[0].get_linewidth())[0]), 0.0)

    def test_the_level_line_is_drawn_as_a_visible_line(self):
        """判据交线**不许用 `ax.contour`**：mplot3d 的等值线集合会被曲面本身遮住，画了也看不见。"""
        ax = self._surface_ax(level=0.15)
        self.assertTrue(ax.lines, "判据交线没画成线 —— 用 contour 会被曲面挡住，画了也看不见")
        self.assertEqual(len(ax.lines[0].get_xdata()), 21, "交线该逐列与曲面相交，每列一个点")

    def test_the_surface_box_is_zoomed_and_draws_one_colorbar(self):
        ax = self._surface_ax(box_aspect=(1.0, 1.45, 0.9))
        self.assertEqual(len(ax.figure.axes), 2, "曲面该有且只有一个色标")

    def test_the_config_registers_the_quantity_scales_with_directions(self):
        """登记处**必须写明方向**（哪一端是"大"）—— 不写方向就还会有人把温度场画反。"""
        import json
        cfg = json.loads((PROJECT / "config/visualization.json").read_text(encoding="utf-8"))
        q = cfg["quantity_cmap"]
        # 不写死色阶名（那是登记表的内容，会随审美调整）：验"登记齐全 + 两量不同阶"
        self.assertTrue(q["temperature"]["cmap"])
        self.assertTrue(q["moisture"]["cmap"])
        self.assertNotEqual(q["temperature"]["cmap"], q["moisture"]["cmap"],
                            "温度与水分又用同一种色阶了")
        for name, entry in q.items():
            self.assertTrue(entry.get("direction"), f"{name} 没写方向")
            self.assertTrue(entry.get("why"), f"{name} 没写为什么这么选")
        self.assertLess(int(cfg["surface"]["rcount"]), 73, "曲面抽稀：73 行全画会密成一片灰")


class TextOverlapTests(unittest.TestCase):
    """注记互相压。

    症状：`export()` 查越界与小字号、`legend_data_overlap` 查图例压曲线，而"一段注记压住
    另一段注记"没人管 —— `fig_geometry` 里标签间距取 4.6 时「对流传质／水分出」第二行
    压到下方四行首行，只能靠目检发现。

    本类**故意钉住判据的边界**：它抓"压"（bbox 重叠面积占比 ≥ 30%），
    **不抓"挤"**（净空只剩几像素）—— 6.2 间距下净空 5.0 px，缩小看就像压着，
    很容易被读成重叠。把边界钉住，免得以后有人以为"没报 = 排版没问题"。
    """

    def _fig(self, dy):
        import matplotlib
        matplotlib.use("Agg")
        from matplotlib import pyplot as plt
        fig = plt.figure(figsize=(4, 3))
        ax = fig.add_subplot(111)
        ax.text(0.5, 0.5, "第一段注记", fontsize=10, ha="center")
        ax.text(0.5, 0.5 + dy, "第二段注记", fontsize=10, ha="center")
        return fig

    def test_two_notes_on_top_of_each_other_are_reported(self):
        errs, _ = texts_overlap(self._fig(0.0))
        self.assertTrue(errs, "两段注记叠在一起却没报 —— 这道闸就等于没有")
        self.assertIn("文字互相压", errs[0])

    def test_a_tight_but_clear_gap_is_not_reported(self):
        """挨得近但没压住 → 不报（判据是重叠面积，不是距离）。"""
        self.assertEqual(texts_overlap(self._fig(0.12)), ([], []))

    def test_axis_labels_and_ticks_are_not_candidates(self):
        """刻度/轴标签互相靠近是**布局**该解决的，报出来只会让闸门变吵。"""
        import matplotlib
        matplotlib.use("Agg")
        from matplotlib import pyplot as plt
        fig = plt.figure(figsize=(3, 3))
        ax = fig.add_subplot(111)
        ax.plot([0, 1], [0, 1])
        ax.set_xlabel("到药材中心的距离 $r$ / cm")
        ax.set_xticks([0, 1], ["0", "1"])
        self.assertEqual(texts_overlap(fig), ([], []))


class NewChartFamilyTests(unittest.TestCase):
    """四类新家族：柱状 / 箱线 / ECDF / 填充等高线。

    本工作流要求的图型清单里，柱状、分布、二维场等高线都是必备类别，而本项目
    **只有折线/散点/热力图**三样能走库 —— 其余都得画图者手写 `ax.bar`/`ax.contourf`。
    手写的东西住不进库，于是"每题重写一遍、每题的毛病也重犯一遍"（与 `surface3d` 同病）。

    每一类都用**本题真数据**实跑过：
    柱状 = 达标时刻两口径（q2q3/q4 summary）、箱线+ECDF = 三档 Δt 的逐点差（q1_level_*）、
    等高线 = 问题2 的 C(r,t) 场（q2q3_fields）。
    """

    def _style(self):
        ctx = charts.style()
        settings = ctx.__enter__()
        self.addCleanup(lambda: ctx.__exit__(None, None, None))
        return settings

    def _ax(self, **kw):
        fig = charts.canvas(self._style(), **kw)
        return fig, fig.add_subplot(111)

    # ── bars ────────────────────────────────────────────────────────────────
    def test_bars_draw_one_container_per_series(self):
        _, ax = self._ax()
        charts.bars(ax, ["Q3", "Q4"], {"判据口径": [57.2, 50.8], "均值口径": [35.8, 34.8]},
                    unit="h")
        self.assertEqual(len(ax.containers), 2, "两个序列该画两组柱")
        self.assertEqual([t.get_text() for t in ax.get_xticklabels()], ["Q3", "Q4"])
        self.assertEqual([p.get_height() for p in ax.containers[0]], [57.2, 50.8])

    def test_bars_reject_an_interval_that_does_not_contain_the_centre(self):
        """边界穿心的柱子画不出来 —— 由 `interval()` 当场挡下，别画出一张骗人的图。"""
        _, ax = self._ax()
        with self.assertRaises(ValueError):
            charts.bars(ax, ["a"], {"s": [1.0]}, low={"s": [2.0]}, high={"s": [3.0]})

    def test_bars_reject_a_length_mismatch(self):
        _, ax = self._ax()
        with self.assertRaises(ValueError):
            charts.bars(ax, ["a", "b"], {"s": [1.0]})

    # ── boxplot ─────────────────────────────────────────────────────────────
    def test_boxplot_puts_n_in_the_tick_labels(self):
        """读者要能判断"这个分布由几个点撑起来"。"""
        _, ax = self._ax()
        charts.boxplot(ax, {"Δt 0.0625": [1e-12, 1e-9, 1e-8], "Δt 0.25": [2e-12, 2e-9]})
        labels = [t.get_text() for t in ax.get_xticklabels()]
        self.assertTrue(all("(n=" in lb for lb in labels), labels)
        self.assertIn("n=3", labels[0])

    def test_boxplot_can_span_orders_of_magnitude(self):
        _, ax = self._ax()
        charts.boxplot(ax, {"g": [1e-15, 1e-12, 1e-8]}, log_scale=True)
        self.assertEqual(ax.get_yscale(), "log")

    # ── ecdf ────────────────────────────────────────────────────────────────
    def test_ecdf_is_monotone_and_ends_at_one(self):
        _, ax = self._ax()
        charts.ecdf(ax, {"g": [3.0, 1.0, 2.0, 4.0]})
        y = ax.lines[0].get_ydata()
        self.assertTrue(np.all(np.diff(y) >= 0), "ECDF 必须单调不减")
        self.assertEqual(float(y[-1]), 1.0)
        self.assertEqual(float(ax.lines[0].get_xdata()[0]), 1.0)

    def test_ecdf_draws_one_line_per_group(self):
        _, ax = self._ax()
        charts.ecdf(ax, {"a": [1.0, 2.0], "b": [2.0, 3.0], "c": [1.0, 3.0]})
        self.assertEqual(len(ax.lines), 3)

    # ── contour ─────────────────────────────────────────────────────────────
    def _field(self):
        x = np.linspace(0, 2, 21)
        y = np.linspace(0, 1, 25)
        return x, y, 2.55 * np.exp(-np.meshgrid(x, y)[1] / 0.3)

    def test_contour_draws_a_colorbar_and_takes_the_semantic_scale(self):
        fig, ax = self._ax()
        x, y, z = self._field()
        charts.contour(ax, x, y, z, colorbar_label="C / (kg/kg)", quantity="moisture")
        self.assertTrue(fig.axes[1:], "等高线图必须带色标（没有色标读者无法把颜色读回数值）")
        # 断言取**主轴**的 mappable：色标轴上还挂着别的 collection（第一条常是残留的
        #   viridis），拿 axes[1].collections[0] 判会得到假失败。
        # 断言**取自登记表**（不写死色阶名 —— 那是登记表的内容，换配色测试不该碎）
        want = charts.quantity_cmap("moisture")
        name = want if isinstance(want, str) else want.name
        self.assertEqual(ax.collections[0].cmap.name, name)

    def test_contour_highlight_adds_the_criterion_line(self):
        """判据线是这个家族相对 `heatmap` 的**主要理由** —— 它得真画出来。"""
        _, ax = self._ax()
        x, y, z = self._field()
        before = len(ax.collections)
        charts.contour(ax, x, y, z, colorbar_label="C", quantity="moisture", highlight=0.15)
        self.assertGreater(len(ax.collections), before, "highlight 层没画出来")

    def test_contour_rejects_a_bad_grid(self):
        _, ax = self._ax()
        with self.assertRaises(ValueError):
            charts.contour(ax, [0, 1], [0, 1], np.zeros((5, 5)), colorbar_label="C")


class ColormapLowEndTests(unittest.TestCase):
    """色阶**低端不许近白**。

    症状：ColorBrewer 顺序色阶（YlGnBu）的原始低端是近白 `#ffffd9`，
    而场图的低值区常是**一大片**（干区/平台）⇒ 整片米白底色把**白网格线与白虚线全吃掉**。
    处置：`config/visualization.json` 的 `quantity_cmap` 每项加 `slice`，把低端裁到实色。

    这条钉住 `slice` 不许被去掉 —— 去掉就是把米白底色放回来（判据：色阶最浅处的亮度）。
    """

    def test_every_registered_scale_starts_at_a_visible_colour(self):
        """**登记表里每个量**的低端都不许近白 —— 不限带 slice 的那些。

        水分/浓度现在用 `viridis`（低端深紫），`slice` 只剩 residual 用；
        但判据与实现无关：任何色阶只要低端近白，一大片低值区就会变成米白底、吃掉白线。
        """
        import json
        cfg = json.loads((PROJECT / "config/visualization.json").read_text(encoding="utf-8"))
        names = [k for k, v in cfg["quantity_cmap"].items() if isinstance(v, dict)]
        self.assertIn("moisture", names)
        for name in names:
            c = charts.quantity_cmap(name)
            if isinstance(c, str):            # 没有 slice 的量返回色阶名（调用方两者都收）
                import matplotlib as mpl
                c = mpl.colormaps[c]
            r, g, b = (float(x) for x in c(0.0)[:3])
            lum = 0.299 * r + 0.587 * g + 0.114 * b
            self.assertLess(lum, 0.88,
                            f"{name} 的色阶低端太浅（亮度 {lum:.2f}）—— 白网格线又会被吃掉")

    def test_the_direction_of_the_moisture_scale_is_not_inverted(self):
        """"干↔湿"的方向不许反：高值（湿）必须比低值（干）**亮**。

        具体用哪个色阶可以换，方向必须一致 —— 否则读者会把干湿读反。
        """
        import matplotlib as mpl
        cmap = charts.quantity_cmap("moisture")
        if isinstance(cmap, str):
            cmap = mpl.colormaps[cmap]
        lo = sum(float(v) for v in cmap(0.0)[:3]) / 3
        hi = sum(float(v) for v in cmap(1.0)[:3]) / 3
        self.assertGreater(hi, lo, "湿端不再比干端亮 —— 方向反了")


class NearMonochromeTests(unittest.TestCase):
    """**近乎单色**检测：场图低值区占一大片时，色阶低端会把整块画成同色。

    症状：`q1_field` 的水分栏被 YlGnBu 的近白画成 76% 米白（白网格线对比 1.21:1），
    人眼能看出来，却没有任何机器信号。这条判据把它变成机器可查的**提醒**
    （不是判决 —— 折线图的大片白底也会命中，所以只打印、不进 auto_issues）。
    """

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_a_flat_field_is_flagged(self):
        """一大片同色 + 白网格线 = 典型"场近乎平坦"的形态 → 必须报。"""
        p = self.root / "flat.png"
        img = Image.new("RGB", (900, 600), (253, 236, 84))     # 亮黄底
        for y in range(0, 600, 60):                            # 白色网格线
            for x in range(900):
                img.putpixel((x, y), (255, 255, 255))
        img.save(p)
        ratio, modal = _nm(p)
        self.assertGreaterEqual(ratio, 0.75, f"平场没被报出来（{ratio:.0%}）")
        self.assertGreater(modal[2], 0, "众数色应取自非白像素")

    def test_a_multi_series_line_chart_is_not_flagged(self):
        """正常折线图（多色细线 + 大片白底）不该报 —— 否则闸门变吵。"""
        ctx = charts.style()
        settings = ctx.__enter__()
        self.addCleanup(lambda: ctx.__exit__(None, None, None))
        fig = charts.canvas(settings)
        ax = fig.add_subplot(111)
        x = np.linspace(0, 2, 200)
        for t, low in FAN:
            charts.trend(ax, x, _field(x, low), label=f"t = {t} s")
        ax.legend()
        out = self.root / "chart.png"
        fig.savefig(out, dpi=settings["dpi"], facecolor="white")
        ratio, _ = _nm(out)
        self.assertLess(ratio, 0.75, f"折线图被误报为近乎单色（{ratio:.0%}）")


if __name__ == "__main__":
    unittest.main()
