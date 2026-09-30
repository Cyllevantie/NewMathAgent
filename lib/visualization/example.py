"""Explicit synthetic-data gallery; never writes production figures or solves a task."""
import argparse
import json
import shutil
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from .charts import canvas, comparison, diagnostics, distribution, heatmap, response, style, trend
from .evidence import write_json
from .export import export


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    project = Path(__file__).resolve().parents[2]
    root = args.output.resolve()
    # Keep demo assets separate even when a mistaken CLI argument is supplied.
    if root == project or root.name in {"figures", "paper", "code", "results"}:
        raise ValueError("Use a separate example workspace, e.g. tmp/visualization-example")
    root.mkdir(parents=True, exist_ok=True)
    (root / "config").mkdir(exist_ok=True)
    shutil.copy2(project / "config/visualization.json", root / "config/visualization.json")
    (root / "lib" / "visualization").mkdir(parents=True, exist_ok=True)
    for module in (project / "lib" / "visualization").glob("*.py"):
        shutil.copy2(module, root / "lib" / "visualization" / module.name)
    (root / "example.py").write_text(Path(__file__).read_text(encoding="utf-8"), encoding="utf-8")
    rng = np.random.default_rng(23)
    x = np.arange(2024, 2031)
    y = np.array([90, 96, 103, 109, 111, 118, 122.])
    observed = rng.normal(100, 12, 100)
    predicted = observed + rng.normal(0, 6, 100)
    a = rng.normal(100, 9, 160)
    b = rng.normal(113, 12, 160)
    grid_x = np.linspace(.8, 1.2, 30)
    grid_y = np.linspace(.7, 1.3, 30)
    z = 100 * np.outer(grid_y, grid_x)
    matrix = np.array([[1, .6, -.3], [.6, 1, -.1], [-.3, -.1, 1]])
    write_json(root / "synthetic_data.json", dict(x=x.tolist(), y=y.tolist(), observed=observed.tolist(),
               predicted=predicted.tolist(), a=a.tolist(), b=b.tolist(), grid_x=grid_x.tolist(),
               grid_y=grid_y.tolist(), z=z.tolist(), matrix=matrix.tolist()))
    with style(root / "config/visualization.json") as settings:
        for kind in ("trend", "comparison", "distribution", "heatmap", "response", "diagnostics"):
            fig = canvas(settings, height_mm={"diagnostics": 112, "comparison": 65}.get(kind, 100))
            if kind == "diagnostics":
                diagnostics(fig, observed, predicted)
            else:
                ax = fig.add_subplot()
                if kind == "trend":
                    trend(ax, x, y, label="示例方案", low=y-9, high=y+9, interval_label="示例范围（非置信区间）")
                    ax.set(xlabel="年份", ylabel="收益（示例单位）")
                    ax.legend()
                elif kind == "comparison":
                    comparison(ax, ["方案甲", "方案乙", "方案丙"], [98, 112, 108], low=[92, 104, 100], high=[104, 120, 116])
                    ax.set_xlabel("收益及示例范围（非置信区间）")
                elif kind == "distribution":
                    distribution(ax, {"方案甲": a, "方案乙": b})
                    ax.set_xlabel("收益（示例单位）")
                    ax.legend()
                elif kind == "heatmap":
                    heatmap(ax, matrix, ["变量甲", "变量乙", "变量丙"], ["变量甲", "变量乙", "变量丙"], colorbar_label="示例相关系数", correlation=True)
                else:
                    response(ax, grid_x, grid_y, z, colorbar_label="收益（示例单位）")
                    ax.set(xlabel="价格系数", ylabel="产量系数")
            fig.suptitle("合成数据 · 仅用于模板验证", fontsize=9, color="#697884")
            export(fig, root, kind, sources=["synthetic_data.json"], script="example.py",
                   claim="验证模板布局，不代表赛题结论", caption="合成数据图型示例，不用于论文", settings=settings)
            plt.close(fig)
    print(root)


if __name__ == "__main__":
    main()
