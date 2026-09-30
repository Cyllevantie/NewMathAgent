# -*- coding: utf-8 -*-
"""主入口：读附件 → 各问求解 → 收支核对 → 导出结果 → 检验。

    python code/run_all.py                 # 交付档（N=320、Q1/Q2/Q3 Δt=1 s、Q4 Δt=60 s）
    python code/run_all.py --scale 0.25    # 缩比冒烟（只改网格/步长，不改方法）
    python code/run_all.py --skip-contract # 跳过 lib.result_contract 的登记与校验

口径写死于 `core.py` 顶部注释（对应 `reports/ANALYSIS_MODELING_REPORT.md` v1.5 的各节）。
**代码之间同目录裸名导入**（`import core` 等）：提交件里全部 `.py` 平铺也能直接跑；
数据/结果的路径一律**相对当前工作目录**（项目根）解析。
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import core                                                       # noqa: E402


def scale_params(scale):
    """缩比只改**规模参数**（网格数、时间步），不改方法（stage_discipline §2）。"""
    n = max(40, int(round(320 * scale / 20.0)) * 20)      # 保持 20 的整数倍（对齐 0.1 cm 输出网格）
    dt = 1.0 if scale >= 0.5 else 5.0
    dt4 = 60.0 if scale >= 0.5 else 300.0
    return n, dt, dt4


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--scale", type=float, default=1.0, help="0.01–1 的规模缩放因子")
    ap.add_argument("--skip-contract", action="store_true")
    ap.add_argument("--skip-xlsx", action="store_true", help="只求解与登记，不写 result*.xlsx")
    args = ap.parse_args(argv)
    core.ROOT = Path.cwd()
    if not (core.ROOT / "request" / "attachments" / "附件1.xlsx").is_file():
        raise SystemExit("当前工作目录 %s 下找不到 request/attachments —— 请在项目根运行" % core.ROOT)

    n, dt, dt4 = scale_params(args.scale)
    t0 = time.perf_counter()
    print("=" * 78)
    print("药材热风烘干 · 编码计算阶段（code / 4Coding-and-computation）")
    print("工作区 %s" % core.ROOT)
    print("规模 scale=%g ⇒ N=%d、Q1/Q2/Q3 Δt=%g s、Q4 Δt=%g s" % (args.scale, n, dt, dt4))
    print("=" * 78)

    core.scan_reuse()

    import q1 as Q1
    import q2 as Q2
    import q3 as Q3
    import q4 as Q4
    import sensitivity as SENS
    import summarize as SUM

    Q1.run(n_cell=n, dt=dt, write_xlsx=not args.skip_xlsx)
    Q2.run(n_cell=n, dt=dt, write_xlsx=not args.skip_xlsx)
    Q3.run()
    Q4.run(n_cell=n, dt=dt4)
    SENS.convergence()
    SENS.sensitivity()
    SENS.consistency()
    SUM.build_spec()
    SUM.build_validation_spec()
    SUM.header()

    if not args.skip_contract:
        for cmd in (["-m", "lib.result_contract", "build"],
                    ["-m", "lib.result_contract", "validate"]):
            print("$ python %s" % " ".join(cmd), flush=True)
            r = subprocess.run([sys.executable, *cmd], cwd=str(core.ROOT),
                               capture_output=True, text=True, encoding="utf-8",
                               errors="replace")
            print((r.stdout or "")[-1500:])
            if r.returncode:
                print((r.stderr or "")[-1500:], file=sys.stderr)
                raise SystemExit("结果契约步骤失败：%s" % " ".join(cmd))

    el = time.perf_counter() - t0
    core.log("── 全链用时 %.1f s" % el)
    core.scale_estimate("run_all", args.scale, el, el)
    print("提示：图件由 `figures/make_figures.py` 生成（独立于数值链，可随时重画）。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
