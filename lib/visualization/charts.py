"""Six evidence-oriented chart families. Inputs are saved results, never fitted here."""
import json
import warnings
from contextlib import contextmanager
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
from matplotlib import font_manager

CONFIG = Path(__file__).resolve().parents[2] / "config/visualization.json"


MARKERS = ["o", "s", "^", "D", "v"]      # 与 config/visualization.json 的 markers 一致；只按需启用


def _cycle(settings):
    """颜色 + 线型。**刻意不含 marker**——各分量按最短的截齐（mpl.cycler 要求等长）。

    为什么 marker 不能进全局 prop_cycle：标记对**稀疏**图是加分项（6 个点的收敛曲线一眼可读），
    但对**密集**曲线是灾难——21 个点的剖面曲线会变成一串珠子、几十上百点的时序图会糊成"毛毛虫"，
    曲线本身反而看不清了。
    线型循环保留：它同样能帮灰度打印/色盲读者区分系列，且不会造成视觉拥挤。
    需要标记时由调用方显式开（如 `trend(..., markers=True)`），只用在稀疏对比图上。
    """
    parts = {"color": list(settings["palette"]),
             "linestyle": list(settings.get("linestyles") or ["-"])}
    n = min(len(v) for v in parts.values())
    return {k: v[:n] for k, v in parts.items()}


@contextmanager
def style(config=CONFIG):
    settings = json.loads(Path(config).read_text(encoding="utf-8"))
    available = {f.name for f in font_manager.fontManager.ttflist}
    fonts = [f for f in settings["fonts"] if f in available]
    if not fonts:
        raise ValueError("No configured font available")
    with mpl.rc_context({
        "font.family": "sans-serif", "font.sans-serif": fonts,
        "font.size": settings["font_size"], "axes.labelsize": settings["font_size"],
        "xtick.labelsize": settings["font_size"], "ytick.labelsize": settings["font_size"],
        "legend.fontsize": settings["font_size"], "axes.spines.top": False,
        "axes.spines.right": False, "axes.linewidth": 0.8,   # 减少粗边框（模板口径）
        # 颜色**之外**再给标记与线型：多系列图若只靠颜色区分，灰度打印与色盲读者都分不出来
        # （顶刊规范里明确要求"≥5 系列用 颜色+标记+线型 三重区分"）。
        # cycler 要求各分量**等长**，故按最短的截齐（改 config 时不必三者数量一致）。
        "axes.prop_cycle": mpl.cycler(**_cycle(settings)),
        # 网格必须画在数据**下方**，否则网格线会压在折线/柱子上，看起来又乱又脏
        "axes.axisbelow": True,
        # 图例**必须有底色**：`frameon: False` 时，调用方放在曲线区里的图例（如
        #   `legend(ncol=2, loc="upper left")`）会被红线与棕线直接从
        #   `t = 1200 s` / `t = 1800 s` 两行字上穿过去，标签根本读不出来；
        #   两列排布还让 `数值解 1800 s` 与 `级数解 1800 s` 挤成一行。
        #   白色半透明底把线压在文字之下，且不像实心边框那么重；
        #   有底色也就不依赖"图附近正好有空白角落"这一偶然条件。
        #   `lib/visualization/quality.legend_data_overlap` 会把"图例压在稠密数据上"的图挡下，
        #   但那是兜底 —— 默认就该有底，别指望每张图都能找到一个空角落。
        "legend.frameon": True, "legend.framealpha": 0.92,
        "legend.edgecolor": settings.get("box", "#CBD5E1"),
        "legend.facecolor": "white", "legend.fancybox": False,
        "figure.facecolor": "white", "axes.facecolor": "white",
        # 三层视觉层级：主文字 ink、主结构线 line、辅助 grid。
        #   辅助元素**明显退后** —— 网格用很浅的灰、轴脊用中灰、文字用近黑蓝，三者拉开档次。
        "text.color": settings.get("ink", "#1F2937"),
        "axes.labelcolor": settings.get("ink", "#1F2937"),
        "xtick.color": settings.get("ink", "#1F2937"),
        "ytick.color": settings.get("ink", "#1F2937"),
        "axes.edgecolor": settings.get("line", "#475569"),
        "grid.color": settings.get("grid", "#E2E8F0"),
        "grid.linewidth": 0.7,
        # 线宽：统一由这里的 `line_width` 定，不许在画图函数里写死常量。
        #   1.8pt 在 160 mm 宽的图上是可接受的，但在 110 mm 这类紧凑图上明显偏粗，
        #   且调用方无从覆盖。现在统一由 config 的 `line_width` 定，
        #   调用方还能逐条覆盖（`trend(..., linewidth=)`）。
        "lines.linewidth": float(settings.get("line_width", 1.5)),
        "pdf.fonttype": 42, "svg.fonttype": "none", "text.usetex": False,
    }):
        yield settings


def quantity_cmap(quantity, settings=None):
    """按**物理量**取色阶 —— 查 `config/visualization.json` 的 `quantity_cmap` 登记处。

    为什么要它：色阶若由每个画图者各自决定，多数人就不决定 —— 于是同一批交付里
    8 个连续量热力图面板全是 viridis（蓝→黄）。
    单调只是表面问题，真正的问题是**语义反了**：温度场用 viridis 时冷=亮黄、热=暗紫，
    与人对"热"的直觉相反。让画图者回答"这是什么量"，比让他选颜色可靠：
    `heatmap(..., quantity="temperature")` 拿到的色阶跨图、跨小问一致。

    未登记的量**不静默退回**（静默回退正是"跨小问换了色却没人发现"的成因）——
    退回默认色阶，但发一条 warning 提醒去表里加一行。

    `slice`：把色阶的**低端裁掉**（见 config 的 `_slice_note`）。为什么必须有它：
    ColorBrewer 顺序色阶的原始低端是**近白**（YlGnBu 的 `#ffffd9`），而场图里低值区常是
    **一大片**（干区/平台）⇒ 整片米白底色把白网格线与白虚线全吃掉。
    裁到 [0.375, 1.0] 后最浅处是青绿，白线重新可见，且"干↔湿"的方向不变。
    """
    if not quantity:
        return None
    cfg = settings or json.loads(Path(CONFIG).read_text(encoding="utf-8"))
    entry = (cfg.get("quantity_cmap") or {}).get(str(quantity))
    if entry is None:
        warnings.warn(
            f"quantity={quantity!r} 不在 config/visualization.json 的 quantity_cmap 登记处；"
            "已退回默认色阶。要把这个量的颜色语义固定下来，请在表里加一行（含方向）。",
            stacklevel=2)
        return None
    if not isinstance(entry, dict):
        return entry                      # 只给色阶名的简写写法仍兼容
    name = entry["cmap"]
    sl = entry.get("slice")
    if not sl:
        return name
    lo, hi = float(sl[0]), float(sl[1])
    base = mpl.colormaps[name]
    return mpl.colors.LinearSegmentedColormap.from_list(
        f"{name}[{lo:g}-{hi:g}]", base(np.linspace(lo, hi, 256)))


def quantity_gamma(quantity):
    """该量的**非线性色标指数**（`quantity_cmap` 登记表里的 `gamma`，缺省 1.0=线性）。

    为什么要它：场图的低值平台常占一大片 —— 线性色标下
    那一片被压成**一个颜色**（`q2_surface3d` 右栏 t≳22 h 占栏高 43.6% 是死色），
    干前沿只能靠外加的判据线读 ⇒ "议题转移而非两全"。
    `PowerNorm(γ<1)` 把色阶**低端拉开**：同一套色标、同一 vmin/vmax 不变，后段色差重新可见。

    与 `slice`（裁低端）分工不同：`slice` 解决"最低端近白、把白线吃掉"，
    `gamma` 解决"低值区占一大片、后段压平"。两者可同时用。
    """
    if not quantity:
        return 1.0
    cfg = json.loads(Path(CONFIG).read_text(encoding="utf-8"))
    entry = (cfg.get("quantity_cmap") or {}).get(str(quantity))
    if not isinstance(entry, dict):
        return 1.0
    return float(entry.get("gamma", 1.0))


def _field_norm(gamma, z, vmin=None, vmax=None):
    """按 gamma 造 PowerNorm；gamma 为 1 且没给 vmin/vmax 时返回 None（走默认线性）。

    `vmin`/`vmax` 是给**同一张图的多栏**用的：各栏若各按自身数据
    范围归一化，同一个颜色在两栏读出的值能差半个量级（`q2_field` 左 [0.53,2.55]、
    右 [0.05,2.55] ⇒ 最深那色左读 0.53、右读 0.05）。同图同量必须**共用一套范围**。
    """
    a = np.asarray(z, dtype=float)
    lo = float(a.min()) if vmin is None else float(vmin)
    hi = float(a.max()) if vmax is None else float(vmax)
    if (not gamma or abs(float(gamma) - 1.0) < 1e-9) and vmin is None and vmax is None:
        return None
    return mpl.colors.PowerNorm(float(gamma or 1.0), vmin=lo, vmax=hi)


def numeric(values, ndim=1):
    a = np.asarray(values, dtype=float)
    if a.ndim != ndim or a.size == 0 or not np.isfinite(a).all():
        raise ValueError("Expected nonempty finite numeric data; handle missing data explicitly")
    return a


def paired(x, y):
    x, y = numeric(x), numeric(y)
    if len(x) != len(y):
        raise ValueError("Length mismatch")
    return x, y


def interval(center, low, high):
    center, low = paired(center, low)
    _, high = paired(center, high)
    if np.any(low > center) or np.any(high < center):
        raise ValueError("Interval must contain the supplied center")
    return low, high


def trend(ax, x, y, *, label, low=None, high=None, interval_label=None,
          markers=False, markevery=None, markersize=5.5, linewidth=None):
    x, y = paired(x, y)
    if np.any(np.diff(x) <= 0):
        raise ValueError("Trend x must be strictly increasing; order data explicitly")
    if (low is None) != (high is None):
        raise ValueError("Both interval bounds are required")
    # markers=True → 每个数据点都标（由调用方判断数据够稀疏才开）。
    # 标记**要小**（默认 3pt）：标记大了在多点序列上会连成"珠子串"，把曲线本身糊掉。
    # 想只标某几个点就传 markevery（列表=下标，或 int=间隔，或 0.25=比例）。
    mk = MARKERS[len(ax.lines) % len(MARKERS)] if markers else None
    extra = {"marker": mk, "markersize": markersize} if mk else {}
    if mk and markevery is not None:
        extra["markevery"] = markevery
    # 线宽默认取 `style()` 设的 `lines.linewidth`（= config 的 `line_width`）——
    # 不许在函数里写死常量：那样会比 matplotlib 默认还粗，且调用方无从覆盖。
    line, = ax.plot(x, y, label=label,
                    linewidth=linewidth if linewidth is not None
                    else mpl.rcParams["lines.linewidth"], **extra)
    if low is not None:
        if not interval_label:
            raise ValueError("Name the interval: confidence, prediction, scenario range, etc.")
        low, high = interval(y, low, high)
        ax.fill_between(x, low, high, color=line.get_color(), alpha=.17, label=interval_label)
    ax.grid(axis="y")
    return ax


def comparison(ax, labels, values, *, low=None, high=None):
    values = numeric(values)
    if len(labels) != len(values):
        raise ValueError("Category count mismatch")
    if (low is None) != (high is None):
        raise ValueError("Both interval bounds are required")
    y = np.arange(len(labels))
    errors = None
    if low is not None:
        low, high = interval(values, low, high)
        errors = np.array([values - low, high - values])
    ax.errorbar(values, y, xerr=errors, fmt="o", capsize=3, linewidth=1.3)
    ax.set_yticks(y, labels)
    ax.invert_yaxis()
    ax.grid(axis="x")
    return ax


def distribution(ax, groups, *, bins=16):
    if not groups:
        raise ValueError("At least one group is required")
    arrays = [numeric(v) for v in groups.values()]
    edges = np.histogram_bin_edges(np.concatenate(arrays), bins=bins)
    for (name, _), values in zip(groups.items(), arrays):
        ax.hist(values, bins=edges, histtype="step", linewidth=1.7, label=f"{name} (n={len(values)})")
    ax.set_ylabel("频数")
    ax.grid(axis="y")
    return ax


def boxplot(ax, groups, *, unit="", ylabel=None, log_scale=False, showfliers=False):
    """箱线图：一组的**整个分布**，不是只看均值/单点。

    与 `distribution()` 的分工：直方图看**形状**（双峰、长尾），箱线看**组间比较**
    （中位、四分位、离群）而**多组同图也读得下** —— 直方图超过三组就互相糊住。
    适用场景：三档时间步长的逐点差跨 4 个数量级，直方图要先把值取对数
    才看得出形状，而箱线在 `log_scale=True` 下**中位与四分位直接可比**。

    `groups` 是 {组名: 一维数值}，与 `distribution()` 同一写法。`unit` 写进轴标签，
    组名后自动带 `n=`（读者要能判断"这个分布由几个点撑起来"）。
    """
    if not groups:
        raise ValueError("At least one group is required")
    arrays = [numeric(v) for v in groups.values()]
    ax.boxplot(arrays, tick_labels=[f"{k}\n(n={len(v)})" for k, v in zip(groups, arrays)],
               showfliers=showfliers, widths=.5)
    if log_scale:
        ax.set_yscale("log")
    ax.set_ylabel(ylabel or f"数值{f' / {unit}' if unit else ''}")
    ax.grid(axis="y")
    return ax


def ecdf(ax, groups, *, xlabel=""):
    """经验累积分布（ECDF）：直接回答"**小于某个值的比例是多少**"。

    普通直方图要读者自己在脑子里积分才能回答这类问题（"多少比例的步差 < 10⁻⁹？"），
    ECDF 把答案画成纵轴。阶梯向右、单调不减；同一张图上多组的**竖直间距**就是两组分布的差。
    """
    if not groups:
        raise ValueError("At least one group is required")
    for name, values in groups.items():
        v = np.sort(numeric(values))
        y = np.arange(1, v.size + 1) / v.size
        ax.step(v, y, where="post", label=f"{name} (n={v.size})")
    ax.set(xlabel=xlabel or "数值", ylabel="累积比例", ylim=(0, 1.02))
    ax.grid(alpha=.16)
    return ax


def bars(ax, labels, groups, *, low=None, high=None, unit="", ylabel=None,
         fmt="{:.3g}", width=.8):
    """分组柱状：分类 × 若干序列的**点估计**（可选上下界）。

    与 `comparison()` 的分工：那个画"点估计 + 区间"的误差棒，适合十几个分类横排；
    这个是"柱高即数值"，适合 2–5 个分类、读者要**直接读数**的场合。
    两者都要求区间包含中心（`interval()` 会校验）—— 边界穿心的柱子在图上画不出来。

    `groups` 是 {序列名: 一维数值}，长度须与 `labels` 一致；`low`/`high` 同样按**序列名**给。
    """
    labels = list(labels)
    if not groups:
        raise ValueError("At least one series is required")
    for name, values in groups.items():
        if len(values) != len(labels):
            raise ValueError(f"Series {name!r} does not match the category count")
    names = list(groups)
    n = len(names)
    x = np.arange(len(labels), dtype=float)
    for i, name in enumerate(names):
        values = numeric(groups[name])
        offset = (i - (n - 1) / 2) * (width / n)
        bars_ = ax.bar(x + offset, values, width / n, label=name)
        if low is not None:
            lo, hi = interval(values, low[name], high[name])
            ax.errorbar(x + offset, values, yerr=np.array([values - lo, hi - values]),
                        fmt="none", ecolor="#333333", capsize=3, linewidth=1)
        ax.bar_label(bars_, fmt=fmt, padding=2, fontsize=8)
    ax.set_xticks(x, labels)
    ax.set_ylabel(ylabel or f"数值{f' / {unit}' if unit else ''}")
    if n > 1:
        ax.legend(loc="upper center", bbox_to_anchor=(.5, -.12), ncol=n)
    ax.grid(axis="y")
    return ax


def dumbbell(ax, labels, left, right, *, left_label="", right_label="", xlabel="",
             fmt="{:.1f}", gap_fmt="{:.1f}", style="capsule", gap_unit=""):
    """哑铃图：每类**两个值 + 它们之间的差** —— 柱状图在这里的替代品。

    为什么不用柱状：这张图要读者看的是**同一类两个口径差多少**，
    柱状图得让他拿两根柱子的高度自己去减；哑铃把那个"差"
    直接画成两点之间那条连线，差值写在连线中点上方。

    - `style="capsule"`（默认）：连线画成一条**浅色胶囊带**（粗而浅），端点突出、连接最轻；
      `style="line"`：细线连接；两种都显式给 `linestyle` —— `style()` 的 prop_cycle 会
      轮换**颜色与线型**，只给 color 的话第二条会变成虚线。
    - 端点用调色板的第 1、2 色（与其它图同一套色）；端点值各自着色、标在点下方。
    - 图例标签**要短**：`constrained_layout` 会把面板压窄去迁就**比它更宽的图例** ——
      两个长标签（`判据口径（中心含水率）`+`均值口径（整柱平均）`）会把半栏面板挤成细长条。
      口径说明写进 caption 或正文，别塞进图例。
    """
    left, right = numeric(left), numeric(right)
    if len(left) != len(labels) or len(right) != len(labels):
        raise ValueError("Dumbbell needs one left and one right value per category")
    if style not in ("capsule", "line"):
        raise ValueError("style must be capsule or line")
    pal = mpl.rcParams["axes.prop_cycle"].by_key().get("color") or ["#1D4ED8", "#93C5FD"]
    # 两端取色序的**两端**、不取相邻两项：
    #   新色序是**同族明度阶**（深蓝→浅蓝），相邻两项 dots 大小下几乎分不出来 ——
    #   而哑铃恰恰靠"两端颜色不同"读两个口径。深蓝 vs 浅蓝（pal[0] vs pal[3]）才分得开。
    c_left, c_right = pal[0], (pal[3] if len(pal) > 3 else pal[1])
    y = np.arange(len(labels))
    for i, (lo, hi) in enumerate(zip(left, right)):
        a, b = sorted((float(lo), float(hi)))
        if style == "capsule":
            ax.plot([a, b], [i, i], color="#E4E4E4", linewidth=11, linestyle="-",
                    zorder=1, solid_capstyle="round")
        else:
            ax.plot([a, b], [i, i], color="#C9C9C9", linewidth=1.7, linestyle="-",
                    zorder=1, solid_capstyle="round")
        # 颜色按**序列顺序**分配（第一个参数 = c_left/pal[0]，第二个 = c_right）——
        #   不许按"数值大的那个"分配（`hi_is_right`）：在红/蓝时代无所谓，换成**同族明度阶**
        #   之后就反了 —— 主结论往往是较大的那个值，反而拿到最浅的色。
        #   连接线仍跨 min–max，只是两端颜色跟参数走。
        ax.plot([float(left[i])], [i], "o", color=c_left, markersize=7.5, zorder=3)
        ax.plot([float(right[i])], [i], "o", color=c_right, markersize=7.5, zorder=3)
        ax.annotate(gap_fmt.format(abs(b - a)) + gap_unit, xy=((a + b) / 2, i),
                    xytext=(0, 10), textcoords="offset points", ha="center",
                    fontsize=max(mpl.rcParams["font.size"] - 1, 8), color="#333333")
        # 端点数值用 `ink`（不是各自序列色）：最浅那档蓝对白只有 1.80:1，
        #   当文字色读起来发虚 —— 颜色映射交给旁边的圆点，文字只管读得清。
        for v in (float(hi), float(lo)):
            ax.annotate(fmt.format(v), xy=(v, i), xytext=(0, -14),
                        textcoords="offset points", ha="center",
                        fontsize=max(mpl.rcParams["font.size"] - 1, 8),
                        color=mpl.rcParams["text.color"])
    ax.set_yticks(y, list(labels))
    ax.set(xlabel=xlabel or "数值", ylim=(-0.6, len(labels) - 0.4))
    ax.grid(axis="x")
    if left_label and right_label:
        ax.plot([], [], "o", color=c_left, markersize=8, label=left_label)
        ax.plot([], [], "o", color=c_right, markersize=8, label=right_label)
        ax.legend(loc="upper center", bbox_to_anchor=(.5, -.28), ncol=2)
    return ax


def contour(ax, x, y, z, *, colorbar_label, quantity=None, cmap=None, levels=14,
            lines=None, line_fmt="%.3g", highlight=None, highlight_color="#E41A1C",
            highlight_label=None, label_lines=True, gamma=None, vmin=None, vmax=None):
    """填充等高线：与 `heatmap()` 同为二维场，但读的是**等值线的形状**而不是格子。

    什么时候用它而不是 `heatmap`：场里有明确的**阈值/前沿/分区**（干前沿、相界、达标线）
    —— 等值线把"哪里是 0.15"画成一条线，而格子图只能靠读者比对色标。
    反过来，格子图更适合"逐格读数 + 锚定离散数据"（实验表、矩阵），等高线会把格子抹掉。

    `z` 形状 `(len(y), len(x))`（与 `response()` 一致）。`lines` 给要标注的等值线层
    （白线 + 数值标签），`highlight` 给**要突出的那一层**（判据线，默认红色）——
    两者都不给时就是纯填充，与 `heatmap` 的差别只在渲染方式。
    色阶同 `heatmap`：按 `quantity` 到 `quantity_cmap` 取。

    - gamma / vmin / vmax：与 `heatmap` / `response` / `surface3d` **同口径**。
      本函数**必须**接这三个参数，否则 `quantity_cmap` 里登记的 `gamma`
      （moisture 0.5 / temperature 0.6，见 config 的 `_gamma_note`）在**所有场图上无从生效**
      —— `q1_field` 右栏 77.6%、`q2_field` 左栏 56.4%、`q4_field` 右栏 54.2% 的
      非白像素是同一个颜色，干前沿只能靠外加的白色等值线读出来 ⇒ 正是 `_gamma_note`
      想避免的「议题转移」。
      `gamma=None` 时取登记值（缺省 1.0=线性）；`vmin`/`vmax` 留给"同一张图的多栏共用
      一套范围"（见 `_field_norm` 的注释）。
    """
    x, y, z = numeric(x), numeric(y), numeric(z, ndim=2)
    if len(x) < 2 or len(y) < 2 or z.shape != (len(y), len(x)):
        raise ValueError("Contour requires a grid shaped (len(y), len(x))")
    cm = cmap or quantity_cmap(quantity) or "viridis"
    _g = quantity_gamma(quantity) if gamma is None else gamma
    # 与 `surface3d` 同一条：matplotlib 不允许**同时**给 norm 与 vmin/vmax ——
    #   有 norm 时范围已含在 norm 里，故只在没有 norm 时传 vmin/vmax。
    _norm = _field_norm(_g, z, vmin, vmax)
    _scale = {"norm": _norm} if _norm is not None else {}
    filled = ax.contourf(x, y, z, levels=levels, cmap=cm, **_scale)
    ax.figure.colorbar(filled, ax=ax, label=colorbar_label, shrink=.85)
    if lines:
        cs = ax.contour(x, y, z, levels=list(lines), colors="white", linewidths=.7)
        if label_lines:
            # 字号取 rcParams（`style()` 按 config 的 font_size 设），**不写死 7**：
            #   写死会低于 `min_font_size`，`export()` 的"文字小于最小字号"当场拦下。
            ax.clabel(cs, fmt=line_fmt, fontsize=mpl.rcParams["font.size"])
    if highlight is not None:
        ax.contour(x, y, z, levels=[float(highlight)], colors=highlight_color,
                   linewidths=1.6)
        if highlight_label:
            ax.plot([], [], color=highlight_color, linewidth=1.6, label=highlight_label)
            ax.legend(loc="upper right")
    return ax


def _cell_edges(ax, nrows, ncols):
    """给每个单元格描边，防相邻同色格"糊成一大块"。

    imshow 画出来的格子默认没有边界，取值相近的两格颜色几乎一样 → 视觉上连成一整块色斑，
    读图的人分不清有几格、边界在哪。细线 + 弱色即可解决，且不喧宾夺主。
    """
    ax.set_xticks(np.arange(ncols + 1) - .5, minor=True)
    ax.set_yticks(np.arange(nrows + 1) - .5, minor=True)
    ax.grid(which="minor", color="white", linewidth=.8)
    ax.tick_params(which="minor", length=0)


def _annotate_cells(ax, a, texts):
    """逐格写数值。文字色按格的明暗自动取黑/白，保证任何色阶上都读得清。"""
    norm = ax.images[0].norm
    cmap = ax.images[0].cmap
    for (i, j), text in np.ndenumerate(np.asarray(texts, dtype=object)):
        rgba = cmap(norm(a[i, j]))
        lum = 0.299 * rgba[0] + 0.587 * rgba[1] + 0.114 * rgba[2]
        ax.text(j, i, text, ha="center", va="center", fontsize=7,
                color="black" if lum > .55 else "white")


def heatmap(ax, values, rows, columns, *, colorbar_label, correlation=False,
            kind="auto", annotate=None, fmt="{:.3g}", square=None, rotate=None,
            cmap=None, quantity=None, gamma=None, vmin=None, vmax=None):
    """格子图。**先判数据是"连续量"还是"离散类别"，再选色阶**。

    这一步是必须的，不是可选的审美问题：把"离散类别"（如 0/1 指派矩阵、A/B/C 方案选择）
    丢给连续色阶（viridis）时，相邻类别的颜色差别极小 → 整张图糊成一大块，看不出有几类、
    更看不出边界。反过来把连续量当类别上色，又会丢掉量级信息。

    - kind="auto"：取值**互异个数 <= 10** 视为离散类别，否则视为连续量。
    - kind="categorical"：按取值排序取**定性色板**（相邻类别颜色差异最大化）+ 离散色标；
      相邻类别绝不共用颜色，这是它和连续色阶的关键区别。
    - kind="continuous"：感知均匀色阶；若取值层数少（<= 10）也顺带加等值线，强化层次。
    - annotate：默认在格子数 <= 60 时逐格标数值（读图的人不必猜颜色）。
    - quantity：连续量的**物理量名**（如 "temperature"/"moisture"），到 `quantity_cmap`
      登记处取与量纲方向对齐的色阶。**连续量请优先传它而不是 `cmap=`** ——
      写死某一支色阶正是 8 个面板同色的成因；给了 `cmap=` 则以 `cmap=` 为准。
    """
    a = numeric(values, ndim=2)
    if a.shape != (len(rows), len(columns)):
        raise ValueError("Heatmap labels do not match matrix")
    if correlation and np.any(np.abs(a) > 1):
        raise ValueError("Correlation values must lie in [-1, 1]")
    if kind not in {"auto", "categorical", "continuous"}:
        raise ValueError("kind must be auto/categorical/continuous")
    nrows, ncols = a.shape
    uniques = np.unique(a)
    if kind == "auto":
        kind = "categorical" if uniques.size <= 10 else "continuous"
    if kind == "categorical" and uniques.size > 20:
        raise ValueError("Too many distinct values for a categorical scale; use continuous")

    if correlation:
        im, kw = None, {"cmap": "RdBu_r", "vmin": -1, "vmax": 1}
        im = ax.imshow(a, aspect="auto", **kw)
    elif kind == "categorical":
        # 定性色板 + 边界归一化：保证每个类别拿到**不同**的颜色（这正是不糊成一块的关键）。
        # 用 ColorBrewer 的标准色板（Set1/Set2/Dark2/Paired），按类别数取——
        # 它们是为"相邻类别必须可区分"设计的，比自己拼颜色可靠。
        palette = ["#E41A1C", "#377EB8", "#4DAF4A", "#984EA3", "#FF7F00",
                   "#FFFF33", "#A65628", "#F781BF", "#999999", "#66C2A5",
                   "#FC8D62", "#8DA0CB", "#E78AC3", "#A6D854", "#FFD92F",
                   "#E5C494", "#B3B3B3", "#1B9E77", "#D95F02", "#7570B3"]
        if uniques.size > len(palette):
            raise ValueError("Not enough distinct colours for this many categories")
        colors = [palette[i] for i in range(uniques.size)]
        cmap = mpl.colors.ListedColormap(colors)
        index = {v: i for i, v in enumerate(uniques)}
        norm = mpl.colors.BoundaryNorm(np.arange(uniques.size + 1) - .5, cmap.N)
        im = ax.imshow(np.vectorize(index.get)(a), aspect="auto", cmap=cmap, norm=norm,
                       interpolation="nearest")
        cb = ax.figure.colorbar(im, ax=ax, label=colorbar_label, shrink=.85,
                                ticks=range(uniques.size),
                                boundaries=np.arange(uniques.size + 1) - .5)
        cb.ax.set_yticklabels([fmt.format(v) for v in uniques])
    else:
        # 色阶**按物理量选**，不许把 `cmap="viridis"` 写死在函数里，
        #   也不许让函数没有 `cmap` 参数（那样调用方无从覆盖）：
        #   写死会让同一批交付里 8 张连续量热力图长得一模一样（蓝→黄）。
        #   单调只是表面问题，真正的问题是**语义反了**：温度场用 viridis 时
        #   冷=亮黄、热=暗紫，跟人对"热"的直觉相反，得读数值才知道哪边热。
        #   物理量应交由调用方给一个与量纲/方向对齐的色阶：
        #     温度（越大越热）→ 暖色阶 `inferno`/`magma`；含水率（越大越湿）→ `YlGnBu`。
        #   默认仍取 `viridis` —— 它是感知均匀的默认色阶，不指定时是安全的。
        _g = quantity_gamma(quantity) if gamma is None else gamma
        # matplotlib **不允许**同时给 norm 与 vmin/vmax（会抛 `ValueError: Passing a
        #   Normalize instance simultaneously with vmin/vmax is not supported`）——
        #   有 norm 时范围已含在 norm 里；只在没有 norm（线性）时才传 vmin/vmax。
        _norm = _field_norm(_g, a, vmin, vmax)
        _scale = {"norm": _norm} if _norm is not None else {"vmin": vmin, "vmax": vmax}
        im = ax.imshow(a, aspect="auto", cmap=cmap or quantity_cmap(quantity) or "viridis",
                       **_scale)
        # 连续量分支**必须自己画色标**。`colorbar_label` 是**必填**
        #   关键字参数 —— 也就是说每个调用方都得传它 —— 静默丢掉它，
        #   连续量这一支就不画色标（只有 `correlation=True` 与**分类**两支会画）。
        #   更要命的是配套：格子数 > 60 时 `annotate` 默认关闭（见本函数末尾）——
        #   143/121 格的两类图于是**既无色标又无格内数字**，读者没有任何途径把颜色读回数值。
        #   （绘图门禁会逮这种图：`q1_field`/`q2_field`/`q3_field`/`q4_field` 四张场图
        #   一个色标都没有，而 `code/make_figures.py` 在 7 处都传了 `colorbar_label`。）
        #   同一批交付里 `response()` 是画色标的 → 前后不一致本身就是缺陷信号。
        ax.figure.colorbar(im, ax=ax, label=colorbar_label, shrink=.85)
        if uniques.size <= 10:
            # 层数少时，色阶本身梯度弱 → 叠等值线把层次显出来
            if nrows > 1 and ncols > 1:
                ax.contour(a, levels=uniques, colors="white", linewidths=.5, alpha=.6)

    # 行列标签过长时旋转，否则标签互相挤压/溢出（顶刊规范里的"行列标签过长未旋转"）
    if rotate is None:
        longest = max([len(str(c)) for c in columns] + [len(str(r)) for r in rows] or [0])
        rotate = 45 if (longest > 6 and ncols > 4) else 0
    ax.set_xticks(range(ncols), columns)
    ax.set_yticks(range(nrows), rows)
    if rotate:
        mpl.pyplot.setp(ax.get_xticklabels(), rotation=rotate, ha="right",
                        rotation_mode="anchor")
    if square is None:
        square = correlation          # 相关系数矩阵用正方形格最易读出聚类结构
    if square:
        ax.set_aspect("equal", adjustable="box")
    if not correlation:
        _cell_edges(ax, nrows, ncols)
    if correlation:
        ax.figure.colorbar(im, ax=ax, label=colorbar_label, shrink=.85)
    if annotate is None:
        annotate = nrows * ncols <= 60          # 格子多时逐格写字反而糊，交给色标
    if annotate:
        _annotate_cells(ax, a, [[fmt.format(v) for v in row] for row in a])
    return ax


def response(ax, x, y, z, *, colorbar_label, cmap=None, quantity=None, levels=14,
             gamma=None, vmin=None, vmax=None):
    """两参数 → 一指标的响应面（二维投影）。色阶同 `heatmap`：按 `quantity` 取。"""
    x, y, z = numeric(x), numeric(y), numeric(z, ndim=2)
    if len(x) < 2 or len(y) < 2 or z.shape != (len(y), len(x)):
        raise ValueError("Response requires a grid shaped (len(y), len(x))")
    if np.any(np.diff(x) <= 0) or np.any(np.diff(y) <= 0):
        raise ValueError("Response grid coordinates must increase")
    _g = quantity_gamma(quantity) if gamma is None else gamma
    norm = _field_norm(_g, z, vmin, vmax)
    if norm is not None:
        # 等**归一化**间距取层：`contourf` 的色带边界
        #   在**数据空间**等距 —— 只给 `norm` 的话 γ 只改颜色、不改边界，低值那一段
        #   照样是一整条死色带（占栏高 41.7%）。按 `norm.inverse(均匀网格)` 取层，
        #   低端才会真的多分出几条带 ⇒ γ 的意图（拉开低端）才落实到**边界**上。
        levels = norm.inverse(np.linspace(0.0, 1.0, int(levels) + 1))
    im = ax.contourf(x, y, z, levels=levels, cmap=cmap or quantity_cmap(quantity) or "viridis",
                     **({"norm": norm} if norm is not None else {"vmin": vmin, "vmax": vmax}))
    # 色标与色带**对齐**：非等距层要用 proportional，否则刻度按等高度块排布、颜色却取自
    # 非线性 norm ⇒ 同一个 RGB 在两张图里读出不同的值（低端差 0.1 kg/kg）。
    cb = ax.figure.colorbar(im, ax=ax, label=colorbar_label, shrink=.85,
                            spacing="proportional" if norm is not None else "uniform")
    if norm is not None:
        # 刻度数要跟着减：proportional 把低端刻度压得很近，
        #   默认自动刻度会挤出 8 个标签，底部两个直接叠在一起（0.092 压 0.000）。
        #   注意：**刻度标签不在 `quality.texts_overlap` 的检查范围内**（那是有意排除的 ——
        #   刻度互相靠近属布局问题），所以这条叠印机器看不见，只能靠这里定死上限 + 目检。
        cb.ax.yaxis.set_major_locator(mpl.ticker.MaxNLocator(nbins=6))
    return ax


def _warn_color():
    """警示色（阈值/异常/判据线专用）—— 从 config 的 warn 取，别在库里写死红色。"""
    try:
        cfg = json.loads(Path(CONFIG).read_text(encoding="utf-8"))
        return cfg.get("warn", "#EF4444")
    except Exception:
        return "#EF4444"


def surface3d(ax, x, y, z, *, colorbar_label=None, colorbar=True, quantity=None, cmap=None,
              gamma=None, vmin=None, vmax=None,
              level=None, level_color=None, box_aspect=None, view=None, settings=None,
              label=None):
    """三维**数据曲面**：z 是 (len(y), len(x)) 网格上的量，画在调用方建好的三维轴上。

    为什么要有这一族：若由每个画图者自己手写 `ax.plot_surface(...)`，
    两个缺陷会**每题重犯一次**：
      ① 曲面低值区常是一大片平台，而色阶低端多为**淡色**（YlGnBu 的浅黄、viridis 的暗紫）
         —— 淡色平台铺在白底上糊成一块，形状读不出来；
      ② mplot3d 默认把盒子缩在面板正中、四周大片空白。
    修法（细网格边 + 抽稀 + 放大盒子）必须住在库里，才不会被下一题带走；
    默认值在 `config/visualization.json` 的 `surface`。

    - quantity：物理量名（同 `heatmap`），到 `quantity_cmap` 取色阶；给了 `cmap=` 以它为准。
    - colorbar：默认画。**并排的图共用一套色阶时传 `colorbar=False`** —— 同一张画布上
      两个色标会让人以为有两套刻度（`q2_surface3d`：三维曲面与二维投影同色阶，
      色标只画在二维那侧）。`colorbar=True` 时 `colorbar_label` 必填 —— 没有数值可读的
      色标等于没画（这与 `heatmap` 的口径一致）。
    - level：可选，画"该量等于 level"的**交线** —— 判据线/阈值线的常见需求
      （如"水分降到 C = 0.15 的那一刻"），语义与二维图上的等值线一致。
      实现**不是** `ax.contour`：mplot3d 的等值线集合会被曲面本身遮住
      （画了、层数也在，但眼睛看不见 —— 而这条线正是这张图的关键信息）。
      改为**逐列求交、连成三维折线**：线在 mplot3d 里的前后关系比面可靠得多。
      每列取**第一个**交点（场非单调时可能有多个交点，判据线的语义就是"第一次到达"）。
    - box_aspect：给了才设 `set_box_aspect(..., zoom=...)`；不给就完全不动轴
      （三维盒子的长宽比是**数据**决定的，库不该替调用方猜）。
    - `rcount`/`ccount` 从 `config/visualization.json` 的 `surface` 取（行/列抽样上限，
      只为**画法**服务，不动 `z` 本身 ⇒ `level=` 求交仍按全网格算）。`ccount` 缺省=画满。
    - label：曲面的图例名，给了才进图例（单曲面图不需要）。
    """
    x, y, z = numeric(x), numeric(y), numeric(z, ndim=2)
    if len(x) < 2 or len(y) < 2 or z.shape != (len(y), len(x)):
        raise ValueError("Surface requires a grid shaped (len(y), len(x))")
    if np.any(np.diff(x) <= 0) or np.any(np.diff(y) <= 0):
        raise ValueError("Surface grid coordinates must increase")
    s = settings or json.loads(Path(CONFIG).read_text(encoding="utf-8"))
    st = s.get("surface") or {}
    X, Y = np.meshgrid(x, y)
    v = view or st.get("view")
    if v:
        ax.view_init(elev=v["elev"], azim=v["azim"])
    _g = quantity_gamma(quantity) if gamma is None else gamma
    # matplotlib **不允许**同时给 norm 与 vmin/vmax（会抛 `ValueError: Passing a Normalize
    #   instance simultaneously with vmin/vmax is not supported`）——有 norm 时范围已含在 norm 里。
    _norm = _field_norm(_g, z, vmin, vmax)
    _scale = {"norm": _norm} if _norm is not None else {"vmin": vmin, "vmax": vmax}
    # `ccount` 不许**写死** `len(x)`：`rcount` 能从 config 调，列方向却
    #   没有任何口子 —— 于是"网格边让平台重新可见"这条默认在**采样点多的那根轴**上失控。
    #   `q2_surface3d`：len(x)=865 个时间列 × 20 行 ⇒ SVG `<path>` 计数 **17 328**
    #   （同批数据图只有 42–77），平台区被 `edgecolor` #5A5A5A 整片盖成灰板，
    #   色标上任何一档都读不到平台值 ⇒ 从"淡色平台糊在白底上"翻成了"平台糊成线色板"。
    #   `surface.ccount`（config）给上限；不给时维持原行为（画满）。
    _cc = int(st.get("ccount") or 0) or len(x)
    mesh = ax.plot_surface(
        X, Y, z, cmap=cmap or quantity_cmap(quantity) or "viridis", **_scale,
        antialiased=True, rcount=int(st.get("rcount", 37)), ccount=_cc,
        edgecolor=st.get("edgecolor", "#5A5A5A"), linewidth=float(st.get("linewidth", 0.35)),
        label=label)
    if colorbar:
        if not colorbar_label:
            raise ValueError("Colorbar requires a label; pass colorbar=False when a "
                             "neighbouring panel already carries the scale")
        ax.figure.colorbar(mesh, ax=ax, label=colorbar_label, shrink=.6, pad=.1)
    if level is not None:
        lv = float(level)
        level_color = level_color or _warn_color()
        xs, ys = [], []
        for j in range(len(x)):
            col = z[:, j]
            for i in range(len(y) - 1):
                a, b = col[i], col[i + 1]
                if a != b and (a - lv) * (b - lv) <= 0:
                    xs.append(x[j])
                    ys.append(y[i] + (lv - a) / (b - a) * (y[i + 1] - y[i]))
                    break
        if xs:
            ax.plot(xs, ys, [lv] * len(xs), color=level_color, linewidth=2.4,
                    linestyle="-")   # 显式给线型：style() 的 prop_cycle 会轮换线型（见 _cycle 注释）
    if box_aspect:
        ax.set_box_aspect(box_aspect, zoom=float(st.get("zoom", 1.30)))
    return ax


def diagnostics(fig, observed, predicted):
    observed, predicted = paired(observed, predicted)
    residual = observed - predicted
    gs = fig.add_gridspec(2, 2, width_ratios=[1.5, 1])
    main = fig.add_subplot(gs[:, 0])
    scatter = fig.add_subplot(gs[0, 1])
    hist = fig.add_subplot(gs[1, 1])
    main.scatter(observed, predicted, s=14, alpha=.5, rasterized=True)
    bounds = [min(observed.min(), predicted.min()), max(observed.max(), predicted.max())]
    main.plot(bounds, bounds, "--", color="#697884", linewidth=1)
    main.set(xlabel="观测值", ylabel="预测值")
    scatter.scatter(predicted, residual, s=10, alpha=.45, rasterized=True)
    scatter.axhline(0, color="#697884", linestyle="--", linewidth=1)
    scatter.set(xlabel="预测值", ylabel="残差")
    distribution(hist, {"残差": residual})
    hist.set_xlabel("残差")
    return main, scatter, hist


def canvas(settings, *, width_mm=None, height_mm=None):
    return plt.figure(figsize=((width_mm or settings["width_mm"]) / 25.4,
                               (height_mm or settings["height_mm"]) / 25.4), layout="constrained")
