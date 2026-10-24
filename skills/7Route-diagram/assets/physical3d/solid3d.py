# -*- coding: utf-8 -*-
"""物理立体示意图 · Route B：自写矢量 3D 实心剖切渲染器。

为什么不用 ``mplot3d`` 画实心剖切：

- mplot3d 按“artist”做深度排序，半透明面/剖面/内腔经常排序错误；
- 3D 文字由 mplot3d 直接投影，标签会互相压、会被实体挡住、无法加引线；
- 实心剖切的隐藏面只能靠面的绘制顺序，mplot3d 不给逐面控制。

本模块把 3D 几何自己投影到 2D，按面片深度排序后用 Matplotlib 的
``Polygon`` 画；文字放在 2D 层，白描边 + 引线 + 碰撞避让。输出仍是
**纯矢量 PDF**，字体与论文其他图一致。

API 速览::

    configure_style(font=None, base_size=8.5)   # None = 读 FIGURE_CONTEXT 字体
    cam = Camera(azim=-58, elev=22)
    sc = Scene(cam)
    sc.cylinder(r=2.0, z0=0, z1=25, cut=(70, -35), color="#DBEAFE")
    sc.cylinder(r=2.0, z0=0, z1=25, inner=1.2, cut=(70, -35))
    sc.radial_face(r0=0, r1=2.0, z0=0, z1=25, theta=...)
    sc.label((0, 0, 12.5), "轴心", offset=(16, 0), color=AMBER)
    fig, ax = plt.subplots(figsize=(3.2, 3.2))
    sc.fit(ax)
    sc.draw(ax, fig)
    sc.save(fig, "fig_geometry_shared", "figures", width_mm=80)

约定：角度用**度**；z 轴为圆柱轴；正交投影为默认；``cut=(span, start)``
表示从 ``start`` 开始保留 ``span`` 度的扇区（即切掉其余部分）。
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Sequence

import numpy as np
import matplotlib as mpl
import matplotlib.pyplot as plt
import matplotlib.patheffects as pe
from matplotlib.patches import Polygon as MplPolygon, Circle, FancyArrowPatch
from matplotlib.path import Path as MplPath
from matplotlib.colors import to_rgb, Normalize
from matplotlib.cm import ScalarMappable

# ---------------------------------------------------------------------------
# 语义色（与论文其他图同一套）
# ---------------------------------------------------------------------------
INK = "#1F2937"
SUB = "#475569"
MUTED = "#64748B"
LINE = "#CBD5E1"
BLUE = "#1D4ED8"
TEAL = "#0F766E"
AMBER = "#B45309"
PURPLE = "#6D28D9"
GREEN = "#15803D"
RED = "#B91C1C"

FILL_BLUE = "#DBEAFE"
FILL_TEAL = "#CCFBF1"
FILL_AMBER = "#FEF3C7"
FILL_PURPLE = "#EDE9FE"
FILL_GRAY = "#F1F5F9"
FILL_GREEN = "#DCFCE7"

EPS = 1e-9


def _context_font() -> str | None:
    """The paper template's resolved font, if a workspace context exists."""
    for rel in ("reports/FIGURE_CONTEXT.json", "config/visualization.json"):
        try:
            data = json.loads((Path(__file__).resolve().parents[4] / rel)
                              .read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        font = str(data.get("font") or "").strip()
        if font:
            return font
    return None


def configure_style(font: str | None = None, base_size: float = 8.5,
                    pdf_fonttype: int = 42) -> None:
    """Apply the shared 3D style; ``font=None`` follows the template context."""
    font = font or _context_font() or "Microsoft YaHei"
    mpl.rcParams.update({
        "font.size": base_size,
        "font.family": "sans-serif",
        "font.sans-serif": [font, "Microsoft YaHei", "SimHei",
                            "Noto Sans CJK SC", "Arial", "DejaVu Sans"],
        "mathtext.fontset": "cm",
        "axes.unicode_minus": False,
        "pdf.fonttype": pdf_fonttype,
        "ps.fonttype": pdf_fonttype,
        "figure.dpi": 120,
        # 顶层 rcParams 可能被别的图模块设成 tight；这里钉死，避免
        # save() 的 PDF 宽度与 width_mm 不一致。
        "savefig.bbox": None,
        "savefig.pad_inches": 0.0,
    })


def _unit(v: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(v)
    return v / n if n > EPS else v


# ---------------------------------------------------------------------------
# 相机
# ---------------------------------------------------------------------------
@dataclass
class Camera:
    """正交/透视相机。``azim``/``elev`` 为度，``center`` 为世界坐标。

    屏幕坐标：x 向右、y 向上；``depth`` 越小越近（排序时先画远的）。
    """
    azim: float = -58.0
    elev: float = 22.0
    center: tuple[float, float, float] = (0.0, 0.0, 0.0)
    zoom: float = 1.0
    perspective: float | None = None   # None = 正交；数值 = 相机距离

    def basis(self):
        az = math.radians(self.azim)
        el = math.radians(self.elev)
        # f：从场景中心指向相机
        f = np.array([math.cos(el) * math.cos(az),
                      math.cos(el) * math.sin(az),
                      math.sin(el)], float)
        world_up = np.array([0.0, 0.0, 1.0])
        r = np.cross(world_up, f)
        if np.linalg.norm(r) <= EPS:
            # elev=±90 时 f 与 world_up 共线，叉积退化为零向量；
            # 取极限方向作为 right，否则所有点都会投到 (0,0)、整图空白。
            r = np.array([-math.sin(az), math.cos(az), 0.0])
        right = _unit(r)
        up = _unit(np.cross(f, right))
        return right, up, f

    def project(self, pts: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """返回 ``(xy, depth)``；xy 为 N×2，depth 为 N（越小越近）。"""
        pts = np.asarray(pts, float).reshape(-1, 3)
        right, up, f = self.basis()
        q = pts - np.asarray(self.center, float)
        if self.perspective is None:
            x = q @ right
            y = q @ up
            depth = -(q @ f)
        else:
            d = float(self.perspective)
            cam = np.asarray(self.center, float) + d * f
            v = pts - cam
            depth = -(v @ f)                  # 正数，越小越近
            focus = d
            x = (v @ right) * focus / np.maximum(depth, 1e-6)
            y = (v @ up) * focus / np.maximum(depth, 1e-6)
        return np.column_stack([x, y]) * self.zoom, depth


# ---------------------------------------------------------------------------
# 面 / 线 / 标签
# ---------------------------------------------------------------------------
@dataclass
class Face:
    verts: np.ndarray
    color: str = FILL_BLUE
    alpha: float = 1.0
    edge: str | None = None
    lw: float = 0.0
    shade: bool = True
    hatch: str | None = None
    layer: int = 0
    name: str = ""
    avoid_label: bool = True      # 标签避让时是否把该面当作“实体”
    _normal: np.ndarray | None = None

    def normal(self) -> np.ndarray:
        if self._normal is not None:
            return self._normal
        v = self.verts
        n = np.zeros(3)
        for i in range(len(v)):
            a, b = v[i], v[(i + 1) % len(v)]
            n += np.cross(a, b)
        self._normal = _unit(n)
        return self._normal

    def centroid(self) -> np.ndarray:
        return self.verts.mean(axis=0)


@dataclass
class Line3D:
    pts: np.ndarray
    color: str = SUB
    lw: float = 1.0
    ls: str | tuple = "-"
    alpha: float = 1.0
    layer: int = 0
    name: str = ""


@dataclass
class Arrow3D:
    p0: np.ndarray
    p1: np.ndarray
    color: str = SUB
    lw: float = 1.4
    style: str = "-|>"
    head: float = 8.0
    layer: int = 10
    name: str = ""


@dataclass
class Label3D:
    anchor: np.ndarray
    text: str
    offset: tuple[float, float] = (18.0, 8.0)   # points
    color: str = INK
    size: float = 8.5
    ha: str = "left"
    va: str = "center"
    bold: bool = False
    leader: bool = True
    leader_color: str | None = None
    leader_lw: float = 0.8
    halo: float = 2.6
    auto: bool = True             # False = 用手给的 offset，不再自动避让
    zorder: float = 40.0          # 必须高于箭头（30+layer*0.01）
    name: str = ""


@dataclass
class Note2D:
    x: float
    y: float
    text: str
    color: str = MUTED
    size: float = 8.0
    ha: str = "left"
    va: str = "center"
    bold: bool = False
    zorder: float = 45.0


# ---------------------------------------------------------------------------
# 场景
# ---------------------------------------------------------------------------
class Scene:
    """一个 3D 场景：面、线、箭头、标签；负责投影、排序、绘制与记录。"""

    def __init__(self, camera: Camera | None = None):
        self.camera = camera or Camera()
        self.faces: list[Face] = []
        self.lines: list[Line3D] = []
        self.arrows: list[Arrow3D] = []
        self.labels: list[Label3D] = []
        self.notes: list[Note2D] = []
        self.records: dict = {}

    # ------------------------------------------------------------------
    # 图元：圆柱 / 环 / 剖面
    # ------------------------------------------------------------------
    def cylinder(self, r: float, z0: float, z1: float, inner: float = 0.0,
                 cut: tuple[float, float] | None = None,
                 segments: int = 96, color: str = FILL_BLUE,
                 alpha: float = 1.0, edge: str | None = None,
                 lw: float = 0.0, shade: bool = True,
                 cut_color: str = FILL_GRAY, cut_hatch: str = "///",
                 cut_edge: str = "#94A3B8", cut_lw: float = 0.7,
                 caps: bool = True, cut_faces: bool = True,
                 cap_color: str | None = None, cap_alpha: float | None = None,
                 layer: int = 5, name: str = "cylinder") -> "Scene":
        """圆柱/圆环，可切掉一个角度楔形。

        ``cut=(angle, start)``：从 ``start`` 度开始**切掉** ``angle`` 度的楔形，
        保留其余部分。``cut=(70, -35)`` = 切掉 -35°..35° 的 70° 楔形。
        ``cut=None`` = 完整圆柱。``inner>0`` = 空心圆环。
        切掉楔形后自动生成两个径向剖面（``cut_faces``）。
        """
        if z1 < z0:
            z0, z1 = z1, z0
        r = float(r)
        inner = float(max(inner, 0.0))
        if r <= 0:
            return self
        if cut is None or abs(cut[0]) < EPS:
            a0, a1 = 0.0, 360.0
        else:
            gap, start = float(cut[0]), float(cut[1])
            gap = max(0.0, min(abs(gap), 359.999))
            a0 = (start + gap) % 360.0
            a1 = a0 + (360.0 - gap)
        span = a1 - a0
        n = max(8, int(round(segments * span / 360.0)))
        thetas = np.linspace(math.radians(a0), math.radians(a1), n + 1)
        zs = np.array([z0, z1], float)

        def shade_of(normal, base):
            return self._shade_color(base, normal) if shade else to_rgb(base)

        # 外侧侧面
        for i in range(n):
            t0, t1 = thetas[i], thetas[i + 1]
            tm = 0.5 * (t0 + t1)
            p = np.array([
                [r * math.cos(t0), r * math.sin(t0), z0],
                [r * math.cos(t1), r * math.sin(t1), z0],
                [r * math.cos(t1), r * math.sin(t1), z1],
                [r * math.cos(t0), r * math.sin(t0), z1],
            ])
            nrm = np.array([math.cos(tm), math.sin(tm), 0.0])
            self.faces.append(Face(p, color=color, alpha=alpha, edge=edge,
                                   lw=lw, shade=False, layer=layer,
                                   name=f"{name}:outer",
                                   _normal=nrm))
            if shade:
                self.faces[-1].color = shade_of(nrm, color)

        # 内侧侧面（空心）
        if inner > EPS:
            for i in range(n):
                t0, t1 = thetas[i], thetas[i + 1]
                tm = 0.5 * (t0 + t1)
                p = np.array([
                    [inner * math.cos(t0), inner * math.sin(t0), z0],
                    [inner * math.cos(t1), inner * math.sin(t1), z0],
                    [inner * math.cos(t1), inner * math.sin(t1), z1],
                    [inner * math.cos(t0), inner * math.sin(t0), z1],
                ])
                nrm = np.array([-math.cos(tm), -math.sin(tm), 0.0])
                self.faces.append(Face(p, color=color, alpha=alpha,
                                       edge=edge, lw=lw, shade=False,
                                       layer=layer, name=f"{name}:inner",
                                       _normal=nrm))
                if shade:
                    self.faces[-1].color = shade_of(nrm, color)

        # 端面（环形扇区）
        if caps and abs(z1 - z0) > EPS:
            for z, nz in ((z0, -1.0), (z1, 1.0)):
                ccol = cap_color or color
                calpha = alpha if cap_alpha is None else cap_alpha
                self._cap_sector(inner, r, z, thetas, nz, ccol, calpha,
                                 edge, lw, shade, layer, name)

        # 切掉楔形后的两个径向剖面
        if cut is not None and abs(cut[0]) > EPS and cut_faces and span < 359.999:
            for th, flip in ((math.radians(a0), True),
                             (math.radians(a1), False)):
                self.radial_face(inner, r, z0, z1, th, color=cut_color,
                                 alpha=1.0, edge=cut_edge, lw=cut_lw,
                                 hatch=cut_hatch, layer=layer + 1,
                                 name=f"{name}:cut", flip=flip)
        return self

    def _cap_sector(self, r0: float, r1: float, z: float,
                    thetas: np.ndarray, nz: float, color: str,
                    alpha: float, edge: str | None, lw: float,
                    shade: bool, layer: int, name: str) -> None:
        n = len(thetas) - 1
        for i in range(n):
            t0, t1 = thetas[i], thetas[i + 1]
            if r0 > EPS:
                p = np.array([
                    [r0 * math.cos(t0), r0 * math.sin(t0), z],
                    [r1 * math.cos(t0), r1 * math.sin(t0), z],
                    [r1 * math.cos(t1), r1 * math.sin(t1), z],
                    [r0 * math.cos(t1), r0 * math.sin(t1), z],
                ])
            else:
                p = np.array([
                    [0.0, 0.0, z],
                    [r1 * math.cos(t0), r1 * math.sin(t0), z],
                    [r1 * math.cos(t1), r1 * math.sin(t1), z],
                ])
            nrm = np.array([0.0, 0.0, nz])
            fill = self._shade_color(color, nrm) if shade else color
            # 一个端面由 ~90 个相邻多边形拼成；抗锯齿的半覆盖边会让
            # 后面的面透出来，端面出现放射状“太阳纹”。用同色 0.3 pt
            # 描边盖住接缝；外轮廓另画，避免每段都描成辐条。
            self.faces.append(Face(
                p, color=fill, alpha=alpha, edge=fill, lw=0.3,
                shade=False, layer=layer, name=f"{name}:cap",
                avoid_label=True, _normal=nrm))
        if edge is not None:
            t0, t1 = float(thetas[0]), float(thetas[-1])
            self.circle(r1, z, theta0=t0, theta1=t1, color=edge, lw=lw,
                        layer=layer + 1)
            if r0 > EPS:
                self.circle(r0, z, theta0=t0, theta1=t1, color=edge, lw=lw,
                            layer=layer + 1)
            if abs((t1 - t0) - 2 * math.pi) > 1e-6:
                for th in (t0, t1):
                    self.line([(r0 * math.cos(th), r0 * math.sin(th), z),
                               (r1 * math.cos(th), r1 * math.sin(th), z)],
                              color=edge, lw=lw, layer=layer + 1)

    def radial_face(self, r0: float, r1: float, z0: float, z1: float,
                    theta: float, degrees: bool = False,
                    color: str = FILL_GRAY,
                    alpha: float = 1.0, edge: str | None = "#94A3B8",
                    lw: float = 0.7, hatch: str | None = "///",
                    layer: int = 6, name: str = "cut",
                    flip: bool = False) -> "Scene":
        """r-z 平面上的径向剖面。``theta`` 默认弧度；``degrees=True`` 按度。"""
        if degrees:
            theta = math.radians(theta)
        c, s = math.cos(theta), math.sin(theta)
        p = np.array([
            [r0 * c, r0 * s, z0],
            [r1 * c, r1 * s, z0],
            [r1 * c, r1 * s, z1],
            [r0 * c, r0 * s, z1],
        ])
        nrm = np.array([-s, c, 0.0])
        if flip:
            nrm = -nrm
        self.faces.append(Face(p, color=color, alpha=alpha, edge=edge,
                               lw=lw, shade=False, hatch=hatch,
                               layer=layer, name=name, avoid_label=False,
                               _normal=nrm))
        return self

    def annulus_sector(self, r0: float, r1: float, z: float,
                       theta0: float, theta1: float,
                       degrees: bool = False, segments: int = 48,
                       color: str = FILL_GRAY,
                       alpha: float = 1.0, edge: str | None = LINE,
                       lw: float = 0.8, shade: bool = False,
                       layer: int = 6, name: str = "annulus") -> "Scene":
        """环形扇面；``theta0/theta1`` 默认弧度，``degrees=True`` 按度。"""
        if degrees:
            theta0, theta1 = math.radians(theta0), math.radians(theta1)
        n = max(4, segments)
        thetas = np.linspace(theta0, theta1, n + 1)
        self._cap_sector(r0, r1, z, thetas, 1.0, color, alpha, edge, lw,
                         shade, layer, name)
        return self

    def box(self, center: Sequence[float], size: Sequence[float],
            color: str = FILL_GRAY, alpha: float = 1.0,
            edge: str | None = "#94A3B8", lw: float = 0.7,
            shade: bool = True, layer: int = 5,
            name: str = "box") -> "Scene":
        c = np.asarray(center, float)
        h = np.asarray(size, float) / 2.0
        # 8 corners, 6 faces
        signs = np.array([[i, j, k] for i in (-1, 1)
                          for j in (-1, 1) for k in (-1, 1)], float)
        corners = c + signs * h
        idx = {
            "x-": [0, 1, 3, 2], "x+": [4, 6, 7, 5],
            "y-": [0, 4, 5, 1], "y+": [2, 3, 7, 6],
            "z-": [0, 2, 6, 4], "z+": [1, 5, 7, 3],
        }
        normals = {"x-": (-1, 0, 0), "x+": (1, 0, 0),
                   "y-": (0, -1, 0), "y+": (0, 1, 0),
                   "z-": (0, 0, -1), "z+": (0, 0, 1)}
        for key, ids in idx.items():
            nrm = np.array(normals[key], float)
            self.faces.append(Face(
                corners[ids], color=(self._shade_color(color, nrm)
                                     if shade else color),
                alpha=alpha, edge=edge, lw=lw, shade=False, layer=layer,
                name=f"{name}:{key}", _normal=nrm))
        return self

    def sphere(self, center: Sequence[float], radius: float,
               n_theta: int = 48, n_phi: int = 24,
               color: str = FILL_BLUE, alpha: float = 1.0,
               edge: str | None = None, lw: float = 0.0,
               shade: bool = True, layer: int = 5,
               name: str = "sphere") -> "Scene":
        c = np.asarray(center, float)
        th = np.linspace(0, 2 * math.pi, n_theta + 1)
        ph = np.linspace(0, math.pi, n_phi + 1)
        for i in range(n_phi):
            for j in range(n_theta):
                p = []
                for a, b in ((ph[i], th[j]), (ph[i], th[j + 1]),
                             (ph[i + 1], th[j + 1]), (ph[i + 1], th[j])):
                    p.append(c + radius * np.array([
                        math.sin(a) * math.cos(b),
                        math.sin(a) * math.sin(b),
                        math.cos(a)]))
                p = np.asarray(p)
                nrm = _unit(p.mean(axis=0) - c)
                self.faces.append(Face(
                    p, color=(self._shade_color(color, nrm)
                              if shade else color),
                    alpha=alpha, edge=edge, lw=lw, shade=False, layer=layer,
                    name=f"{name}:{i},{j}", _normal=nrm))
        return self

    def surface(self, X: np.ndarray, Y: np.ndarray, Z: np.ndarray,
                cmap: str = "viridis", vmin: float | None = None,
                vmax: float | None = None, alpha: float = 1.0,
                wire: bool = False, wire_color: str = "#334155",
                wire_lw: float = 0.35, layer: int = 5,
                name: str = "surface") -> "Scene":
        """参数曲面（数据场）：X/Y/Z 同形网格，按 Z 的平均值着色。"""
        X = np.asarray(X, float)
        Y = np.asarray(Y, float)
        Z = np.asarray(Z, float)
        if X.shape != Y.shape or X.shape != Z.shape:
            raise ValueError("X/Y/Z must have the same shape")
        finite = np.isfinite(Z)
        if not finite.any():
            return self
        zv = Z[finite]
        zmin = float(zv.min()) if vmin is None else float(vmin)
        zmax = float(zv.max()) if vmax is None else float(vmax)
        # np.nanmin/nanmax 会把 +/-inf 也算进范围：+inf 让所有有限面
        # 落到 cmap(0)，-inf 让它们变成透明的 bad 色。只用有限值定范围。
        if not np.isfinite(zmin) or not np.isfinite(zmax) or zmax <= zmin:
            zmin, zmax = float(zv.min()), float(zv.max())
            if zmax <= zmin:
                zmax = zmin + 1.0
        cm = plt.get_cmap(cmap)
        norm = Normalize(vmin=zmin, vmax=zmax)
        ny, nx = Z.shape
        for i in range(ny - 1):
            for j in range(nx - 1):
                zz = Z[i:i + 2, j:j + 2]
                if not np.all(np.isfinite(zz)):
                    continue
                p = np.array([
                    [X[i, j], Y[i, j], Z[i, j]],
                    [X[i, j + 1], Y[i, j + 1], Z[i, j + 1]],
                    [X[i + 1, j + 1], Y[i + 1, j + 1], Z[i + 1, j + 1]],
                    [X[i + 1, j], Y[i + 1, j], Z[i + 1, j]],
                ])
                col = cm(norm(float(np.mean(zz))))
                self.faces.append(Face(
                    p, color=col, alpha=alpha, edge=(wire_color if wire else None),
                    lw=(wire_lw if wire else 0.0), shade=False,
                    layer=layer, name=f"{name}:{i},{j}", avoid_label=False))
        return self

    # ------------------------------------------------------------------
    # 线 / 箭头 / 标签
    # ------------------------------------------------------------------
    def line(self, pts: Iterable[Sequence[float]], color: str = SUB,
             lw: float = 1.0, ls: str | tuple = "-", alpha: float = 1.0,
             layer: int = 10, name: str = "line") -> "Scene":
        self.lines.append(Line3D(np.asarray(list(pts), float), color=color,
                                 lw=lw, ls=ls, alpha=alpha, layer=layer,
                                 name=name))
        return self

    def circle(self, r: float, z: float, theta0: float = 0.0,
               theta1: float = 2 * math.pi, degrees: bool = False,
               n: int = 120,
               color: str = LINE, lw: float = 0.8, ls: str | tuple = "-",
               alpha: float = 1.0, layer: int = 10,
               name: str = "circle") -> "Scene":
        """圆/圆弧；``theta0/theta1`` 默认弧度，``degrees=True`` 按度。"""
        if degrees:
            theta0, theta1 = math.radians(theta0), math.radians(theta1)
        t = np.linspace(theta0, theta1, n)
        pts = np.column_stack([r * np.cos(t), r * np.sin(t),
                               np.full_like(t, z)])
        return self.line(pts, color=color, lw=lw, ls=ls, alpha=alpha,
                         layer=layer, name=name)

    def arrow(self, p0: Sequence[float], p1: Sequence[float],
              color: str = SUB, lw: float = 1.4, style: str = "-|>",
              head: float = 8.0, layer: int = 10,
              name: str = "arrow") -> "Scene":
        self.arrows.append(Arrow3D(np.asarray(p0, float),
                                   np.asarray(p1, float),
                                   color=color, lw=lw, style=style,
                                   head=head, layer=layer, name=name))
        return self

    def label(self, anchor: Sequence[float], text: str,
              offset: tuple[float, float] = (18.0, 8.0),
              color: str = INK, size: float = 8.5,
              ha: str = "left", va: str = "center", bold: bool = False,
              leader: bool = True, leader_color: str | None = None,
              leader_lw: float = 0.8, halo: float = 2.6,
              auto: bool = True, name: str = "label") -> "Scene":
        self.labels.append(Label3D(np.asarray(anchor, float), text,
                                   offset=offset, color=color, size=size,
                                   ha=ha, va=va, bold=bold, leader=leader,
                                   leader_color=leader_color,
                                   leader_lw=leader_lw, halo=halo,
                                   auto=auto, name=name))
        return self

    def note(self, x: float, y: float, text: str, color: str = MUTED,
             size: float = 8.0, ha: str = "left", va: str = "center",
             bold: bool = False) -> "Scene":
        """2D 注记（投影坐标）；用于面板短描述、单位说明等，不要写长解释。"""
        self.notes.append(Note2D(x, y, text, color=color, size=size,
                                 ha=ha, va=va, bold=bold))
        return self

    # ------------------------------------------------------------------
    # 投影 / 适配 / 绘制
    # ------------------------------------------------------------------
    def _all_points(self) -> np.ndarray:
        pts = []
        for f in self.faces:
            pts.append(f.verts)
        for l in self.lines:
            pts.append(l.pts)
        for a in self.arrows:
            pts.append(np.vstack([a.p0, a.p1]))
        for lb in self.labels:
            pts.append(lb.anchor.reshape(1, 3))
        if not pts:
            return np.zeros((1, 3))
        return np.vstack(pts)

    def projected_bounds(self) -> tuple[float, float, float, float]:
        xy, _ = self.camera.project(self._all_points())
        return (float(np.min(xy[:, 0])), float(np.max(xy[:, 0])),
                float(np.min(xy[:, 1])), float(np.max(xy[:, 1])))

    def fit(self, ax, margin: float = 0.08, equal: bool = True):
        x0, x1, y0, y1 = self.projected_bounds()
        dx, dy = x1 - x0, y1 - y0
        dx = dx if dx > EPS else 1.0
        dy = dy if dy > EPS else 1.0
        mx, my = dx * margin, dy * margin
        ax.set_xlim(x0 - mx, x1 + mx)
        ax.set_ylim(y0 - my, y1 + my)
        if equal:
            ax.set_aspect("equal", adjustable="box")
        ax.axis("off")
        return ax

    def suggest_figsize(self, width_mm: float,
                        extra_top_mm: float = 0.0,
                        extra_bottom_mm: float = 0.0) -> tuple[float, float]:
        x0, x1, y0, y1 = self.projected_bounds()
        dx, dy = x1 - x0, y1 - y0
        # 垂直线/单点场景 dx=0，直接除会得到 1e10 英寸高的画布。
        if dx < 1e-6 and dy < 1e-6:
            dx = dy = 1.0
        elif dx < 1e-6:
            dx = dy
        elif dy < 1e-6:
            dy = dx
        w_in = width_mm / 25.4
        h_in = w_in * dy / dx + (extra_top_mm + extra_bottom_mm) / 25.4
        return w_in, max(h_in, 0.6)

    def draw(self, ax, fig, *, label_layout: bool = True,
             background_lines: bool = True) -> dict:
        """按深度排序绘制；返回 QA 记录。"""
        # 1) 投影所有面
        items = []
        for f in self.faces:
            xy, dep = self.camera.project(f.verts)
            items.append((float(np.mean(dep)), f, xy))
        # 远的先画（depth 越小越近）
        items.sort(key=lambda z: -z[0])

        # 2) 画线：layer < 5 的先画（背景线），其余在面后画
        line_items = []
        for l in self.lines:
            xy, dep = self.camera.project(l.pts)
            line_items.append((float(np.mean(dep)), l, xy))
        line_items.sort(key=lambda z: -z[0])
        for dep, l, xy in line_items:
            if l.layer < 5:
                ax.plot(xy[:, 0], xy[:, 1], color=l.color, lw=l.lw, ls=l.ls,
                        alpha=l.alpha, solid_capstyle="round",
                        zorder=0.5 + l.layer * 0.01)

        # 3) 画面（按深度）
        for dep, f, xy in items:
            patch = MplPolygon(xy, closed=True, facecolor=f.color,
                               edgecolor=(f.edge or "none"),
                               linewidth=f.lw, alpha=f.alpha,
                               hatch=f.hatch, joinstyle="round",
                               zorder=1.0)
            if f.hatch:
                patch.set_edgecolor(f.edge or "#94A3B8")
                patch.set_linewidth(max(f.lw, 0.5))
            ax.add_patch(patch)

        # 4) 前景线
        for dep, l, xy in line_items:
            if l.layer >= 5:
                ax.plot(xy[:, 0], xy[:, 1], color=l.color, lw=l.lw, ls=l.ls,
                        alpha=l.alpha, solid_capstyle="round",
                        zorder=20 + l.layer * 0.01)

        # 5) 箭头（投影后在 2D 画，箭头大小不随深度变）
        for a in sorted(self.arrows, key=lambda a: -float(
                np.mean(self.camera.project(np.vstack([a.p0, a.p1]))[1]))):
            xy, _ = self.camera.project(np.vstack([a.p0, a.p1]))
            arr = FancyArrowPatch(
                tuple(xy[0]), tuple(xy[1]), arrowstyle=a.style,
                mutation_scale=a.head, color=a.color, lw=a.lw,
                shrinkA=0, shrinkB=0, zorder=30 + a.layer * 0.01,
                joinstyle="round", capstyle="round")
            arr.set_path_effects([
                pe.Stroke(linewidth=a.lw + 2.4, foreground="white"),
                pe.Normal()])
            ax.add_patch(arr)

        # 6) 标签
        records = self._draw_labels(ax, fig) if label_layout else []

        # 7) 2D 注记（白色底层文字做描边，保住字体嵌入）
        for n in self.notes:
            ax.text(n.x, n.y, n.text, color="white",
                    fontsize=n.size + 0.8, ha=n.ha, va=n.va,
                    fontweight=("bold" if n.bold else "normal"),
                    zorder=n.zorder - 0.1)
            ax.text(n.x, n.y, n.text, color=n.color, fontsize=n.size,
                    ha=n.ha, va=n.va,
                    fontweight=("bold" if n.bold else "normal"),
                    zorder=n.zorder)

        self.records = {
            "projection": ("orthographic" if self.camera.perspective is None
                           else "perspective"),
            "camera": {"azim": self.camera.azim,
                       "elev": self.camera.elev,
                       "zoom": self.camera.zoom,
                       "perspective": self.camera.perspective},
            "faces": len(self.faces),
            "lines": len(self.lines),
            "arrows": len(self.arrows),
            "labels": records,
            "bounds": self.projected_bounds(),
        }
        return self.records

    # ------------------------------------------------------------------
    # 标签布局
    # ------------------------------------------------------------------
    def _draw_labels(self, ax, fig) -> list[dict]:
        if not self.labels:
            return []
        fig.canvas.draw()
        renderer = fig.canvas.get_renderer()
        # 数据坐标 -> 点 的比例。注意：px_per_data 是“像素/数据”，
        # 1 pt = dpi/72 像素，所以 data_per_pt = dpi/(72*px_per_data)。
        p0 = ax.transData.transform((0, 0))
        p1 = ax.transData.transform((1, 1))
        px_per_data_x = abs(p1[0] - p0[0])
        px_per_data_y = abs(p1[1] - p0[1])
        data_per_pt_x = fig.dpi / (72.0 * max(px_per_data_x, 1e-9))
        data_per_pt_y = fig.dpi / (72.0 * max(px_per_data_y, 1e-9))

        # 不透明面的 2D 路径（用于避让）
        face_paths = []
        for f in self.faces:
            if f.alpha >= 0.92 and f.layer >= 5 and f.avoid_label:
                xy, _ = self.camera.project(f.verts)
                face_paths.append(MplPath(xy))
                if len(face_paths) >= 900:
                    break

        # 文字允许略超出坐标轴，但不能超出整张 figure（会被裁掉）
        fig_box = mpl.transforms.Bbox.from_bounds(
            0, 0, fig.get_figwidth() * fig.dpi, fig.get_figheight() * fig.dpi)
        fig_box_data = fig_box.transformed(ax.transData.inverted())
        fx0, fy0 = fig_box_data.x0, fig_box_data.y0
        fx1, fy1 = fig_box_data.x1, fig_box_data.y1

        placed = []
        records = []
        for lb in self.labels:
            leader_color = lb.leader_color or lb.color
            xy, _ = self.camera.project(lb.anchor.reshape(1, 3))
            ax_, ay_ = float(xy[0, 0]), float(xy[0, 1])

            candidates = (self._label_candidates(lb.offset) if lb.auto
                          else [tuple(lb.offset)])
            best = None
            for cand_i, (dx_pt, dy_pt) in enumerate(candidates):
                dx = dx_pt * data_per_pt_x
                dy = dy_pt * data_per_pt_y
                tx, ty = ax_ + dx, ay_ + dy
                # 预估 bbox：先用文字创建一个临时 text 量
                # 白描边用“白色底层文字”实现，而不是 path_effects：
                # path_effects 会把文字转成轮廓，PDF 里丢字体、不可检索。
                t_bg = ax.text(tx, ty, lb.text, color="white",
                               fontsize=lb.size + lb.halo * 0.28,
                               ha=lb.ha, va=lb.va,
                               fontweight=("bold" if lb.bold else "normal"),
                               zorder=lb.zorder - 0.1, clip_on=False)
                t = ax.text(tx, ty, lb.text, color=lb.color,
                            fontsize=lb.size, ha=lb.ha, va=lb.va,
                            fontweight=("bold" if lb.bold else "normal"),
                            zorder=lb.zorder, clip_on=False)
                fig.canvas.draw()
                bbox_disp = t.get_window_extent(renderer)
                bbox_data = bbox_disp.transformed(ax.transData.inverted())
                bx0, by0 = bbox_data.x0, bbox_data.y0
                bx1, by1 = bbox_data.x1, bbox_data.y1
                # 碰撞：其他标签
                overlap = 0.0
                for (ox0, oy0, ox1, oy1) in placed:
                    ix = max(0.0, min(bx1, ox1) - max(bx0, ox0))
                    iy = max(0.0, min(by1, oy1) - max(by0, oy0))
                    # 统一换算到 pt^2：offset/字号都以 pt 计，若用 data^2
                    # 打分，米制小场景的重叠会小到几乎不惩罚。
                    overlap += ((ix / max(data_per_pt_x, 1e-9)) *
                                (iy / max(data_per_pt_y, 1e-9)))
                # 碰撞：不透明面。用 9 个采样点判断标签是否真的压在面上；
                # 只比 bbox 会把“在实体旁边的空白标签”误判成压住。
                geom_hit = 0
                if face_paths:
                    cx, cy = (bx0 + bx1) / 2, (by0 + by1) / 2
                    samples = np.array([
                        [bx0, by0], [bx1, by0], [bx1, by1], [bx0, by1],
                        [cx, by0], [cx, by1], [bx0, cy], [bx1, cy], [cx, cy],
                    ])
                    for pth in face_paths:
                        ext = pth.get_extents()
                        if (ext.x1 < bx0 or ext.x0 > bx1 or
                                ext.y1 < by0 or ext.y0 > by1):
                            continue
                        if pth.contains_points(samples).any():
                            geom_hit += 1
                # 越界：以整张 figure 为界，而不是坐标轴
                out = 0
                if bx0 < fx0 or bx1 > fx1 or by0 < fy0 or by1 > fy1:
                    out = 1
                score = (out * 1e6 + geom_hit * 1e4 +
                         overlap * 1e2 + abs(dx_pt) + abs(dy_pt) * 0.5)
                # 手给的 preferred offset 若完全无碰撞，就直接用它；
                # 否则固定 12 pt 的兜底会因为“偏移更短”而抢走首选。
                if cand_i == 0 and out == 0 and geom_hit == 0 and overlap <= 0:
                    score = -1.0
                if best is None or score < best[0]:
                    if best is not None:
                        best[1].remove()
                        best[2].remove()
                    best = (score, t_bg, t, (bx0, by0, bx1, by1),
                            (dx_pt, dy_pt), geom_hit, out)
                else:
                    t_bg.remove()
                    t.remove()
                if score <= 0.01:
                    break
            score, t_bg, t, bbox, off, geom_hit, out = best
            placed.append(bbox)
            records.append({
                "text": lb.text,
                "anchor": [ax_, ay_],
                "bbox": list(bbox),
                "offset_pt": list(off),
                "geometry_hits": geom_hit,
                "out_of_bounds": out,
            })
            if lb.leader:
                # 从锚点连到文字 bbox 边缘
                cx, cy = (bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2
                ex, ey = self._bbox_exit(bbox, (ax_, ay_), (cx, cy))
                ln = ax.plot([ax_, ex], [ay_, ey], color=leader_color,
                             lw=lb.leader_lw, zorder=lb.zorder - 1,
                             solid_capstyle="round")[0]
                ln.set_path_effects([
                    pe.Stroke(linewidth=lb.leader_lw + 2.2,
                              foreground="white"), pe.Normal()])
                ax.plot([ax_], [ay_], marker="o", ms=2.4, color=leader_color,
                        zorder=lb.zorder + 1, markeredgewidth=0)
        return records

    @staticmethod
    def _label_candidates(preferred: tuple[float, float]):
        """首选偏移 + 8 个方向 × 4 个半径；保证水平和垂直方向都能试。"""
        dx, dy = float(preferred[0]), float(preferred[1])
        out = [(dx, dy)] if (abs(dx) + abs(dy) > 0) else []
        radii = (12.0, 18.0, 26.0, 36.0, 48.0)
        dirs = ((1, 0), (-1, 0), (0, 1), (0, -1),
                (0.707, 0.707), (0.707, -0.707),
                (-0.707, 0.707), (-0.707, -0.707))
        for r in radii:
            for ux, uy in dirs:
                out.append((ux * r, uy * r))
        if abs(dx) + abs(dy) > 0:
            for r in radii:
                out.append((dx * (r / max(abs(dx), abs(dy), 1.0)),
                            dy * (r / max(abs(dx), abs(dy), 1.0))))
        # 去重，保持顺序
        seen = set()
        uniq = []
        for c in out:
            key = (round(c[0], 2), round(c[1], 2))
            if key not in seen:
                seen.add(key)
                uniq.append(c)
        return uniq

    @staticmethod
    def _bbox_exit(bbox, anchor, center):
        """线段 center->anchor 与 bbox 边界的交点。"""
        x0, y0, x1, y1 = bbox
        ax_, ay_ = anchor
        cx, cy = center
        dx, dy = ax_ - cx, ay_ - cy
        ts = []
        if abs(dx) > EPS:
            for x in (x0, x1):
                t = (x - cx) / dx
                y = cy + t * dy
                if -EPS <= t <= 1 + EPS and y0 - EPS <= y <= y1 + EPS:
                    ts.append(t)
        if abs(dy) > EPS:
            for y in (y0, y1):
                t = (y - cy) / dy
                x = cx + t * dx
                if -EPS <= t <= 1 + EPS and x0 - EPS <= x <= x1 + EPS:
                    ts.append(t)
        if not ts:
            return cx, cy
        t = min(ts)
        return cx + t * dx, cy + t * dy

    # ------------------------------------------------------------------
    # 导出 / QA
    # ------------------------------------------------------------------
    def save(self, fig, stem: str, out_dir: str | Path,
             width_mm: float | None = None, dpi: int = 600,
             write_json: bool = True) -> tuple[Path, Path]:
        """导出 PDF/PNG。

        ``width_mm`` 必须与建图时的 ``figsize`` 一致；``draw()`` 已按当前
        画布把标签偏移换算成 data 坐标，导出时再改 figsize 会让标签重叠。
        """
        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)
        if width_mm is not None:
            want = width_mm / 25.4
            have = fig.get_figwidth()
            # draw() 已按当前画布宽度把标签 offset 换算成 data 坐标；
            # 保存时再改 figsize 会让这些 offset 被整体缩放、bbox 失效。
            if abs(have - want) > 0.02:
                raise ValueError(
                    "Scene.save(width_mm=...) 不能在 draw() 之后改变画布宽度："
                    f"当前 {have * 25.4:.1f} mm，请求 {width_mm:.1f} mm。"
                    "请用 figsize=(width_mm/25.4, ...) 建图后再 draw，"
                    "或传 width_mm=None 保持当前宽度。")
        pdf = out / (stem + ".pdf")
        png = out / (stem + ".png")
        fig.savefig(pdf, format="pdf", bbox_inches=None)
        fig.savefig(png, dpi=dpi, bbox_inches=None)
        if write_json:
            meta = dict(self.records)
            meta["width_mm"] = round(fig.get_figwidth() * 25.4, 2)
            meta["font"] = mpl.rcParams["font.sans-serif"][0]
            (out / (stem + ".scene.json")).write_text(
                json.dumps(meta, ensure_ascii=False, indent=2),
                encoding="utf-8")
        return pdf, png

    @staticmethod
    def _shade_color(color, normal: np.ndarray) -> str:
        base = np.array(to_rgb(color), float)
        n = _unit(np.asarray(normal, float))
        # 主光从左上偏前打来；两-sided：法线背光时翻转
        light = _unit(np.array([-0.45, -0.35, 0.82]))
        lam = abs(float(n @ light))
        # 浅色实体：只做轻微明暗，保持论文图的低饱和观感
        factor = 0.84 + 0.16 * lam
        rgb = np.clip(base * factor, 0.0, 1.0)
        return mpl.colors.to_hex(rgb)

