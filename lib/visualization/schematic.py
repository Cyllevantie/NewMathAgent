"""Generic scene primitives for problem-driven illustrative diagrams (题意示意图).

设计约束（与 geometry.py 一致）：本模块**只渲染调用方给定的对象**，不含任何题目机理或判据。
坐标、关系、比例、符号来自题面与已确认的模型关系，全部由调用方提供。

为什么要有它：`geometry.py` 只有三个高度专用的函数（正交投影 / 夹角 / 球截面），
模型画示意图时只能套库里现成的形状——最常见的后果是"不管什么题都画个球"。
这里给一套**通用图元**（点/线/向量/区域/尺寸标注/坐标轴），让图跟着题意走，而不是跟着库里有啥走。

三维一律用**正交投影投到二维再画**，不用 mplot3d：后者自带透视网格与遮挡混色，
是"三维图很丑"的主因。投影只表达空间关系，不计算遮挡（见 docs/GEOMETRY.md）。
"""
import numpy as np
import matplotlib as mpl

from .charts import numeric, style, canvas
from .geometry import orthographic

# 深色主对象 + 弱化辅助线：主次分明，避免"整张图一个灰度"
MAIN = "#285F86"
ACCENT = "#D88736"
AUX = "#697884"


class Scene:
    """一个二维绘图场景。传了 camera 就按三维处理（点先投影再画）。"""

    def __init__(self, ax, *, camera=None, palette=None, font_size=None, fonts=None):
        self.ax = ax
        self.camera = camera                     # (azimuth, elevation) 或 None
        self.palette = list(palette or [MAIN, ACCENT, "#548C78", "#8B719F", AUX])
        self.font_size = font_size or 9
        # 必须显式带上字体：charts.style() 是 rc_context，出块即还原 rcParams，
        # 而调用方是在 scene2d() 返回**之后**才逐条画图元的——那时中文字体已经不在上下文里，
        # 中文会全变成方框。所以每个 text/annotate 都显式指定 fontfamily。
        self.fonts = list(fonts or [])
        self._color_i = 0

    # ---------- 投影 ----------
    def project(self, p):
        a = np.asarray(p, dtype=float)
        if self.camera is None:
            if a.shape[-1] != 2:
                raise ValueError("2D scene expects 2D points; pass camera= for 3D")
            return a
        if a.ndim == 1:
            if a.size != 3:
                raise ValueError("3D scene expects 3D points")
            return orthographic(a.reshape(1, 3), azimuth=self.camera[0],
                                elevation=self.camera[1])[0]
        if a.shape[-1] != 3:
            raise ValueError("3D scene expects 3D points")
        return orthographic(a, azimuth=self.camera[0], elevation=self.camera[1])

    def color(self, i=None):
        return self.palette[(self._color_i if i is None else i) % len(self.palette)]

    def _next_color(self):
        c = self.color()
        self._color_i += 1
        return c

    def _label(self, xy, text, *, offset, color, bold=False):
        if not text:
            return
        self.ax.annotate(text, xy, xytext=offset, textcoords="offset points",
                         fontsize=self.font_size, color=color or "#333333",
                         fontfamily=self.fonts or None,
                         fontweight="bold" if bold else "normal",
                         ha="center", va="center", zorder=6)

    # ---------- 图元 ----------
    def point(self, p, *, label=None, offset=(8, 8), color=None, size=26, halo=True):
        """一个点 + 文字标签。halo 给标签加白描边，压在线上也读得清。"""
        xy = self.project(p)
        c = color or MAIN
        if halo:
            self.ax.scatter([xy[0]], [xy[1]], s=size * 2.4, color="white", zorder=4)
        self.ax.scatter([xy[0]], [xy[1]], s=size, color=c, zorder=5, clip_on=False)
        if label:
            self.ax.annotate(label, xy, xytext=offset, textcoords="offset points",
                             fontsize=self.font_size, color=c, zorder=6, ha="center",
                             va="center", fontfamily=self.fonts or None,
                             path_effects=[_halo()])
        return xy

    def segment(self, p, q, *, label=None, color=None, width=1.4, style="-",
                arrow=False, offset=(8, 8)):
        """线段；arrow=True 时在终点加箭头（方向/指向关系用，不是矢量大小）。"""
        a, b = self.project(p), self.project(q)
        c = color or MAIN
        if arrow:
            self.ax.annotate("", xy=b, xytext=a, zorder=3,
                             arrowprops=dict(arrowstyle="-|>", color=c, linewidth=width,
                                             shrinkA=0, shrinkB=0))
        else:
            self.ax.plot([a[0], b[0]], [a[1], b[1]], color=c, linewidth=width,
                         linestyle=style, zorder=3, solid_capstyle="round")
        self._label((a + b) / 2, label, offset=offset, color=c)
        return a, b

    def arrow(self, start, vec, *, label=None, color=None, width=1.8, scale=1.0,
              label_gap=10):
        """矢量（力/速度/方向）：从 start 沿 vec 画箭头，长度按 scale 缩放。

        矢量必须**按已确认的物理量**给；本函数不做任何物理解释或判据。
        """
        a = self.project(start)
        d = self.project(np.asarray(start, dtype=float) + np.asarray(vec, dtype=float) * scale)
        c = color or ACCENT
        self.ax.annotate("", xy=d, xytext=a, zorder=4,
                         arrowprops=dict(arrowstyle="-|>", color=c, linewidth=width,
                                         shrinkA=0, shrinkB=0, mutation_scale=14))
        if label:
            mid = (a + d) / 2
            n = d - a
            n = n / (np.linalg.norm(n) or 1.0)
            off = np.array([-n[1], n[0]]) * label_gap
            self._label(mid, label, offset=tuple(off), color=c)
        return a, d

    def region(self, points, *, label=None, color=None, alpha=.15, style_out="--",
               width=1.0):
        """多边形区域（阴影/可行域/截面）。顶点顺序按调用方给定，本函数不排序修正。"""
        pts = self.project(points)
        c = color or self.color()
        self.ax.fill(pts[:, 0], pts[:, 1], color=c, alpha=alpha, zorder=1,
                     edgecolor=c, linewidth=width, linestyle=style_out)
        if label:
            self._label(pts.mean(axis=0), label, offset=(0, 0), color=c)
        return pts

    def dimension(self, p, q, *, label, offset=0.6, color=AUX, width=.9):
        """尺寸/距离标注：两端引线 + 中间标注线 + 数值文字。

        只画"这里有一段距离"，**不判定**该距离是否满足题面约束。
        """
        a, b = self.project(p), self.project(q)
        d = b - a
        n = np.linalg.norm(d)
        if n <= 1e-12:
            raise ValueError("Dimension endpoints must differ")
        nrm = np.array([-d[1], d[0]]) / n * offset
        a2, b2 = a + nrm, b + nrm
        self.ax.plot([a[0], a2[0]], [a[1], a2[1]], color=color, linewidth=width * .8, zorder=2)
        self.ax.plot([b[0], b2[0]], [b[1], b2[1]], color=color, linewidth=width * .8, zorder=2)
        self.ax.annotate("", xy=b2, xytext=a2, zorder=2,
                         arrowprops=dict(arrowstyle="<|-|>", color=color, linewidth=width,
                                         shrinkA=0, shrinkB=0, mutation_scale=8))
        self._label((a2 + b2) / 2, label, offset=tuple(nrm / (np.linalg.norm(nrm) or 1) * 12),
                    color=color)
        return a2, b2

    def path(self, xy, *, label=None, color=None, width=1.6, style="--", offset=(8, 8)):
        """轨迹/曲线（由调用方按已确认关系给出采样点）。"""
        pts = self.project(xy)
        c = color or ACCENT
        self.ax.plot(pts[:, 0], pts[:, 1], color=c, linewidth=width, linestyle=style,
                     zorder=3)
        if label:
            self._label(pts[len(pts) // 2], label, offset=offset, color=c)
        return pts

    def axes(self, origin, vectors, labels, *, color=AUX, width=1.1, scale=1.0):
        """坐标轴/基向量三脚架。vectors 每行一个方向，labels 对应符号。"""
        o = self.project(origin)
        for vec, name in zip(vectors, labels):
            tip = self.project(np.asarray(origin, dtype=float) + np.asarray(vec, float) * scale)
            self.ax.annotate("", xy=tip, xytext=o, zorder=2,
                             arrowprops=dict(arrowstyle="-|>", color=color, linewidth=width,
                                             shrinkA=0, shrinkB=0, mutation_scale=10))
            self._label(tip, name, offset=(9, 7), color=color)
        return o


def _halo():
    """给标签加白描边——压在网格线/曲线上仍可读。"""
    import matplotlib.patheffects as pe
    return pe.withStroke(linewidth=2.4, foreground="white")


def _settings(config=None):
    import json
    from .charts import CONFIG
    return json.loads((config or CONFIG).read_text(encoding="utf-8"))


def _cjk_fonts(settings):
    """配置里**实际装着**的中文字体（保序）。返回 [] 时退化为默认字体。"""
    from matplotlib import font_manager
    available = {f.name for f in font_manager.fontManager.ttflist}
    return [f for f in settings["fonts"] if f in available]


def scene2d_panels(rows, cols, *, xlim, ylim, equal=True, show_frame=False, settings=None,
                   titles=None):
    """多面板共享画布——用于"前后对比 / 多时刻 / 多方案"这类示意图。

    所有面板必须**共享同一坐标范围**（这里由 xlim/ylim 统一给定）：每个面板各自 autoscale
    会让两幅图的比例不一致，读者没法比较"变了多少"——对比图也就白画了。
    titles 按行优先给每个面板一个小标题（如 "(a) $t=0$"、"(b) $t=T$"）。
    """
    if not all(isinstance(v, int) and v >= 1 for v in (rows, cols)):
        raise ValueError("rows/cols must be positive integers")
    s = settings or _settings()
    if titles is not None and len(titles) != rows * cols:
        raise ValueError("titles must match the panel count")
    with style():
        fig = canvas(s, height_mm=float(s["height_mm"]) * 0.8 * rows)
        axs = fig.subplots(rows, cols, squeeze=False)   # layout 由 canvas() 在 figure 上设好
        scenes = []
        for i, ax in enumerate(axs.flat):
            ax.set_xlim(*xlim)
            ax.set_ylim(*ylim)
            if equal:
                ax.set_aspect("equal", adjustable="box")
            if show_frame:
                ax.grid(alpha=.14, linewidth=.5)
            else:
                ax.set_axis_off()
            if titles:
                ax.set_title(titles[i], fontsize=s["font_size"], loc="left", pad=3,
                             fontfamily=_cjk_fonts(s) or None)
            scenes.append(Scene(ax, palette=s["palette"], font_size=s["font_size"],
                                fonts=_cjk_fonts(s)))
    return fig, scenes


def scene3d_panels(rows, cols, *, azimuth=30, elevation=20, limits, show_frame=False,
                   settings=None, titles=None):
    """三维多面板：**所有面板共用同一 camera 与同一 limits**，否则形变会毁掉可比性。"""
    if not all(isinstance(v, int) and v >= 1 for v in (rows, cols)):
        raise ValueError("rows/cols must be positive integers")
    s = settings or _settings()
    if titles is not None and len(titles) != rows * cols:
        raise ValueError("titles must match the panel count")
    (x0, x1), (y0, y1), (z0, z1) = limits
    corners = np.array([[x, y, z] for x in (x0, x1) for y in (y0, y1) for z in (z0, z1)])
    proj = orthographic(corners, azimuth=azimuth, elevation=elevation)
    span = np.ptp(proj, axis=0)
    aspect = span[1] / span[0] if span[0] > 1e-9 else 1.0
    row_mm = float(np.clip(s["width_mm"] / cols * aspect, 45.0, 200.0))
    pad = 0.08 * max(span.max(), 1e-9)
    with style():
        fig = canvas(s, height_mm=row_mm * rows)
        axs = fig.subplots(rows, cols, squeeze=False)   # layout 由 canvas() 在 figure 上设好
        scenes = []
        for i, ax in enumerate(axs.flat):
            ax.set_xlim(proj[:, 0].min() - pad, proj[:, 0].max() + pad)
            ax.set_ylim(proj[:, 1].min() - pad, proj[:, 1].max() + pad)
            ax.set_aspect("equal", adjustable="box")
            if show_frame:
                ax.grid(alpha=.12, linewidth=.5)
            else:
                ax.set_axis_off()
            if titles:
                ax.set_title(titles[i], fontsize=s["font_size"], loc="left", pad=3,
                             fontfamily=_cjk_fonts(s) or None)
            scenes.append(Scene(ax, camera=(azimuth, elevation), palette=s["palette"],
                                font_size=s["font_size"], fonts=_cjk_fonts(s)))
    return fig, scenes


def scene2d(*, xlim, ylim, equal=True, xlabel="", ylabel="", show_frame=False,
            settings=None):
    """二维等比例场景。示意图默认不画坐标框（框会让人误以为有数据坐标）。"""
    s = settings or _settings()
    with style():
        fig = canvas(s)
        ax = fig.add_subplot(111)
        ax.set_xlim(*xlim)
        ax.set_ylim(*ylim)
        if equal:
            ax.set_aspect("equal", adjustable="box")
        if show_frame:
            ax.set_xlabel(xlabel)
            ax.set_ylabel(ylabel)
            ax.grid(alpha=.14, linewidth=.5)
        else:
            ax.set_axis_off()
        scene = Scene(ax, palette=s["palette"], font_size=s["font_size"],
                      fonts=_cjk_fonts(s))
    return fig, scene


def scene3d(*, azimuth=30, elevation=20, limits, show_frame=False, settings=None):
    """三维场景：正交投影到二维后复用同一套图元（比 mplot3d 干净，且没有遮挡混色）。

    limits：((xmin,xmax),(ymin,ymax),(zmin,zmax))，用来定画布范围；
    投影是按调用方给的坐标算的，范围只影响视野，不改变对象。
    """
    s = settings or _settings()
    (x0, x1), (y0, y1), (z0, z1) = limits
    corners = np.array([[x, y, z] for x in (x0, x1) for y in (y0, y1) for z in (z0, z1)])
    proj = orthographic(corners, azimuth=azimuth, elevation=elevation)
    # 画布按投影内容的真实长宽比定高：等比例轴 + 固定 160x100 画布会让图形缩在正中一小块，
    # 四周全是空白——这是"三维图特别丑"的一半原因（另一半是 mplot3d 的灰网格）。
    span = np.ptp(proj, axis=0)
    aspect = span[1] / span[0] if span[0] > 1e-9 else 1.0
    height_mm = float(np.clip(s["width_mm"] * aspect, 45.0, 200.0))
    with style():
        fig = canvas(s, height_mm=height_mm)
        ax = fig.add_subplot(111)
        pad = 0.08 * max(span.max(), 1e-9)
        ax.set_xlim(proj[:, 0].min() - pad, proj[:, 0].max() + pad)
        ax.set_ylim(proj[:, 1].min() - pad, proj[:, 1].max() + pad)
        ax.set_aspect("equal", adjustable="box")
        if show_frame:
            ax.grid(alpha=.12, linewidth=.5)
        else:
            ax.set_axis_off()
        scene = Scene(ax, camera=(azimuth, elevation), palette=s["palette"],
                      font_size=s["font_size"], fonts=_cjk_fonts(s))
    return fig, scene
