# -*- coding: utf-8 -*-
"""问题 1：预热平衡段（0–1800 s，附录 2 参数集）。

交付：表 1（T，°C）/表 2（C，kg/kg）各 7 时刻 × 5 半径；`results/result1.xlsx`
（1800 行 × 21 个距离列，A 列 = 时间/s）。
口径：N=320、dt=1 s、面值算术平均、环境/几何取**步末层**、物性系数滞后一步（§5.6）。
运行：`python code/q1.py`
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))     # 同目录裸名导入（提交件平铺也能跑）

import numpy as np                                                # noqa: E402
import core                                                       # noqa: E402
from core import C0, T0, R0                                       # noqa: E402

T_SNAP = [100, 300, 600, 900, 1200, 1500, 1800]                   # 表 1/表 2 的 7 个时刻（题面）


def run(n_cell=320, dt=1.0, write_xlsx=True, write_npz=True):
    core.log("── Q1 求解：0–1800 s，附录 2，N=%d，dt=%g s" % (n_cell, dt))
    res = core.solve("q1", 1800.0, dt, n_cell, snap_every=int(round(60 / dt)),
                     label="Q1")
    # ── 单位换算与舍入（§5.8 第 1–2 条：内部 SI，出表换 cm/°C 后 ROUND_HALF_UP）
    T_C = core.round4(res["T_out"] - 273.15)      # 温度表用 °C
    C_4 = core.round4(res["C_out"])               # 水分表用 kg/kg
    t_out = res["mon"]["t"]

    # ── 表 1/表 2
    idx_t = [int(np.argmin(np.abs(t_out - s))) for s in T_SNAP]
    assert all(abs(t_out[i] - s) < 1e-9 for i, s in zip(idx_t, T_SNAP)), "取样时刻不在网格上"
    j_r = [int(round(x / 0.1)) for x in core.DIST_T5]
    table1 = [[float(T_C[i, j]) for j in j_r] for i in idx_t]
    table2 = [[float(C_4[i, j]) for j in j_r] for i in idx_t]

    # ── 自检（§5.8 第 6 条，分节点区）
    sc = core.selfcheck_q1("q1", n_cell=n_cell, dt=dt)
    Cn1, Tn1, xi1, _ = core.first_step_field("q1", dt=dt, n_cell=n_cell)
    jN = [int(round(x / 2.0 * n_cell)) for x in core.DIST_Q1]      # 21 个输出列在全网格上的节点号
    bitwise = bool(np.array_equal(T_C[0], core.round4(Tn1 - 273.15)[jN]) and
                   np.array_equal(C_4[0], core.round4(Cn1)[jN]))
    sc["首步与求解器逐位一致"] = bitwise
    sc["argmax护栏"] = core.argmax_guard(res["mon"], kind="q1", n_cell=n_cell, dt=dt)

    # ── 守恒/收支校核（§5.9/§11.1）：本问 rho_d 为常数、已约去 ⇒ 右端不乘 rho_d0
    cons = res["cons"]
    ok = np.arange(1, len(cons["t"]))
    resid = cons["dC_int"][ok] - cons["bcC"][ok]
    scale_ref = float(np.max(np.abs(cons["bcC"][ok])))
    conservation = dict(
        恒等式="d/dt∫_0^R0 C r dr = R0 D ∂_rC|_R0 = -R0 h_m (C_s - C_∞)（除以 rho_d 之后的 C 方程口径）",
        离散伸缩和=dict(max_abs_residual=float(np.max(np.abs(resid))),
                        max_abs_rhs=scale_ref,
                        max_rel_residual=float(np.max(np.abs(resid)) / max(scale_ref, 1e-300))),
        口径注="右端不乘 rho_d0；乘上 rho_d0 才是 §3.2 的物理质量通量 j_s（§11.1 同注）",
    )

    # ── 1800 s 内失水比例的**三个口径**（§3.2 验算 1 的三行表，量级 8%–13%）
    _, _, _, V = core.grid(n_cell)
    m0 = float(core.C0 * V.sum())                      # = C0/2 = 1.275000（∫_0^1 C0 ξ dξ）
    m1 = float(res["mon"]["meanC"][-1])           # 口径 2：全场体积加权均值（n=320、dt=1 s）
    # 口径 3：同一剖面只在 0/0.5/1.0/1.5/2.0 cm 五点梯形上积分（粗求积，偏大）
    r5 = np.array(core.DIST_T5) * 0.01
    f5 = np.array([table2[-1][k] for k in range(5)]) * r5
    dr5 = r5[1] - r5[0]
    m2 = float((dr5 * (0.5 * f5[0] + f5[1] + f5[2] + f5[3] + 0.5 * f5[4])) / core.R0 ** 2)
    # 口径 1：表面通量累计（恒定近似）j_s = rho_d0 * h_m * (C_s - C_inf)
    rho_d = core.rho_d0("q1")
    Cs, Cinf = table2[-1][-1], res["mon"]["Cinf"][-1]
    js = rho_d * core.HM * (Cs - Cinf)
    area = 2.0 * np.pi * core.R0 * 0.25
    w0 = 820.0 * (np.pi * core.R0 ** 2 * 0.25) * core.C0 / (1.0 + C0)
    moist_loss = dict(
        calibers=[
            dict(name="表面通量累计（恒定近似）", value_X=m0,
                 value=float(m0 - js * area * 1800.0 / w0 * (m0)),
                 j_s=float(js), area_m2=float(area), water_initial_kg=float(w0),
                 drop_pct=float(js * area * 1800.0 / w0 * 100.0)),
            dict(name="全场体积加权均值 ∫_0^1 C ξ dξ（n=320、dt=1 s）",
                 value_X=m0, value=m1, drop_pct=float((m0 - m1) / m0 * 100.0)),
            dict(name="五点梯形求积（0/0.5/1.0/1.5/2.0 cm）",
                 value_X=m0, value=m2, drop_pct=float((m0 - m2) / m0 * 100.0)),
        ],
        mean_initial=float(m0), mean_1800s=float(m1),
        rho_d0=float(rho_d),
        note="三个口径同量级（§3.2：8.34% / 10.06% / 12.88%）",
    )

    out = dict(problem_id="2026A", stage="code", problem="Q1", n=n_cell, dt=dt,
               t_end=1800.0, table1_T_C=table1, table2_C=table2,
               table_times_s=T_SNAP, table_radii_cm=core.DIST_T5,
               selfcheck=sc, conservation=conservation, moisture_loss=moist_loss,
               stages=res["stages"],
               rows_in_result1=dict(n=int(len(t_out)), first=float(t_out[0]),
                                    last=float(t_out[-1]), cols=len(core.DIST_Q1)))
    core.write_json(core.results_dir() / "q1.json", out)

    if write_npz:
        ck = core.Checkpoint(
            "q1", "Q1_预热段_附录2_有限体积ξ网格_半隐式欧拉_面值算术平均_步末层环境",
            dict(kind="q1", n=n_cell, dt=dt, t_end=1800.0, face="arith",
                 env="hold(0-1800s 全在附件1 内，无延拓)", time_layer="step-end",
                 rho_d="常数 230.99，已从 C 方程约去"))
        ck.save(dict(t=t_out, T_C=T_C, C=C_4,
                     mon_t=res["mon"]["t"], mon_maxC=res["mon"]["maxC"],
                     mon_C0=res["mon"]["C0"], mon_Cs=res["mon"]["Cs"],
                     mon_argmax=res["mon"]["argmax"], mon_deficit=res["mon"]["deficit"],
                     r_cm=np.array(core.DIST_Q1),
                     snap_t=np.array(res["snaps"]["t"]),
                     snap_T=np.array(res["snaps"]["T"]) - 273.15,
                     snap_C=np.array(res["snaps"]["C"])),
                monitor=dict(name="q1", t_dry=None, n=n_cell, dt=dt))
        core.write_json(core.out_dir() / "figdata_q1.npz.meta.json", dict(
            _method="Q1 场快照（每 60 s 一帧，ξ 全场）+ 交付表 1/表 2 数值 —— 供 figures 读取",
            _code_fp=core.CODE_FP, _produced_at=core._produced_at(), _stage="code",
            _params=dict(source="code/outputs/q1.npz", n=n_cell, dt=dt,
                         snap_every_s=60.0)))
        np.savez_compressed(core.out_dir() / "figdata_q1.npz",
                            t=np.array(res["snaps"]["t"]),
                            r_cm=np.linspace(0.0, 2.0, n_cell + 1),
                            T_C=np.array(res["snaps"]["T"]) - 273.15,
                            C=np.array(res["snaps"]["C"]),
                            table1=np.array(table1), table2=np.array(table2),
                            table_t=np.array(T_SNAP, float),
                            table_r=np.array(core.DIST_T5),
                            t_out=t_out, out_T_C=T_C, out_C=C_4,
                            r_out_cm=np.array(core.DIST_Q1),
                            mon_t=res["mon"]["t"], mon_maxC=res["mon"]["maxC"])

    if write_xlsx:
        info = core.template_info("result1.xlsx")
        head_T = [info[0]["a1"]] + core.head_list(core.DIST_Q1)
        head_C = [info[1]["a1"]] + core.head_list(core.DIST_Q1)
        assert info[0]["sheet"] == "温度" and info[1]["sheet"] == "水分浓度"
        core.write_result_xlsx(
            core.results_dir() / "result1.xlsx",
            [dict(sheet=info[0]["sheet"], head=head_T, times=t_out, values=T_C),
             dict(sheet=info[1]["sheet"], head=head_C, times=t_out, values=C_4)])
        core.log("   → results/result1.xlsx（%d 行 × %d 列 × 2 表）"
                 % (len(t_out), len(core.DIST_Q1)))

    core.log("   t=1800 s 表 1（°C）: " + " ".join("%.4f" % v for v in table1[-1]))
    core.log("   t=1800 s 表 2（kg/kg）: " + " ".join("%.4f" % v for v in table2[-1]))
    core.log("   自检：温度侧 max|T-T0|=%.4e K（<1e-3 %s）；水分内部 max|C-C0|=%.4e（<1e-4 %s）；"
             "表面 |C-C0|=%.4e（只登记）"
             % (sc["温度侧全节点"]["max_abs_dev"], sc["温度侧全节点"]["passed"],
                sc["水分侧内部"]["max_abs_dev"], sc["水分侧内部"]["passed"],
                sc["水分侧表面"]["abs_dev"]))
    return out, res


if __name__ == "__main__":
    core.ROOT = Path(__file__).resolve().parents[1]
    run()
