"""Export vector PDF/SVG and PNG preview at the intended physical size."""
import warnings
from pathlib import Path

from matplotlib.text import Text

from .evidence import path_in, register
from .quality import inspect_png, legend_data_overlap, near_monochrome, texts_overlap


def export(fig, root, figure_id, *, sources, script, claim, caption, settings, included=True):
    # Do not use tight cropping: it changes the declared physical width.
    issues = []
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        fig.canvas.draw()
        renderer = fig.canvas.get_renderer()
        # Locators keep extra tick artists beyond the visible limits; those are
        # not drawn by Axis and must not be reported as clipped visible text.
        hidden_ticks = set()
        for ax in fig.axes:
            for axis in (ax.xaxis, ax.yaxis):
                low, high = sorted(axis.get_view_interval())
                for tick in axis.get_major_ticks() + axis.get_minor_ticks():
                    if not low <= tick.get_loc() <= high:
                        hidden_ticks.update((id(tick.label1), id(tick.label2)))
        for text in fig.findobj(Text):
            if id(text) in hidden_ticks or not text.get_visible() or not text.get_text().strip():
                continue
            if text.get_fontsize() < settings["min_font_size"]:
                issues.append("文字小于最小字号: " + text.get_text())
            box = text.get_window_extent(renderer)
            if box.width and box.height and (box.x0 < -1 or box.y0 < -1 or
                    box.x1 > fig.bbox.width + 1 or box.y1 > fig.bbox.height + 1):
                issues.append("文字超出画布: " + text.get_text())
        # 图例压数据：在**画完但还没存**时查最准（需要 renderer 的显示坐标）。
        # 挡下来的是"图例落在稠密曲线上"这类人眼一看就废的问题。
        issues.extend(legend_data_overlap(fig))
        # 注记互相压：越界、小字号、图例压曲线各有人管，
        # 而"一段注记压住另一段注记"三道都不管。`fig_geometry` 里标签间距取 4.6 时，
        # 「对流传质／水分出」的第二行会压到下方四行首行（改 6.2 才够）。
        # 判据是 bbox 重叠**面积占比**，所以"挤但没压"（6.2 时净空仅 5 px）它抓不到 ——
        # 那属于排版余量，仍靠目检；别把它当"排版没问题"的证明。
        # 压掉一大半才挡复核，压住一角只报（避免标点/上下标挨着就拦下整条链）。
        overlap_errors, overlap_warnings = texts_overlap(fig)
        issues.extend(overlap_errors)
        for w in overlap_warnings:
            print(f"⚠️ 注记提醒：{w}", flush=True)
        artifacts = []
        # Validate identifier before constructing output filenames.
        import re
        if not re.fullmatch(r"[a-zA-Z0-9_-]+", figure_id):
            raise ValueError("Invalid figure id")
        for suffix in (".pdf", ".svg", ".png"):
            rel = f"figures/{figure_id}{suffix}"
            out = path_in(root, rel)
            out.parent.mkdir(parents=True, exist_ok=True)
            fig.savefig(out, dpi=settings["dpi"], facecolor="white")
            artifacts.append(rel)
            if suffix == ".png":
                # 位图三查。**error 进 auto_issues 挡复核**，
                # warning（边界暗像素偏多）只报不挡 —— 它是启发式，误伤真图不值当。
                png_errors, png_warnings = inspect_png(out, settings, figure_id=figure_id)
                issues.extend(png_errors)
                for w in png_warnings:
                    print(f"⚠️ 位图提醒：{w}", flush=True)
                # 近乎单色**只提醒**（不进 auto_issues）：折线图的大片白底、流程图的同色方框
                # 都会命中，误伤真图不值当。它给的是"值得看一眼"的信号 —— 场图低值区占 76%
                # 时，色阶低端会把一大片画成同色、白网格线全被吃掉，正是它要提示的情形。
                mono, modal = near_monochrome(out)
                if mono >= 0.75:
                    print(f"⚠️ 近单色提醒：{figure_id} 的非白像素 {mono:.0%} 是同一个颜色"
                          f" rgb{modal} —— 若这是场图，说明该窗口内场近乎平坦，"
                          f"考虑改成剖面/折线，或裁色阶低端（config 的 _slice_note）", flush=True)
        issues.extend(str(w.message) for w in caught if "Glyph" in str(w.message)
                      or "constrained_layout" in str(w.message))
    return register(root, figure_id, artifacts=artifacts, sources=sources, script=script,
                    claim=claim, caption=caption, width_mm=float(fig.get_figwidth() * 25.4),
                    auto_issues=sorted(set(issues)), included=included)
