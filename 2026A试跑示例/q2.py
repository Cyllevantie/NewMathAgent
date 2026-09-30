# -*- coding: utf-8 -*-
"""问题 2：整个烘干过程（0–259200 s = 72 h，附录 3 变物性，两阶段）。

交付：表 3（T，°C）/表 4（C，kg/kg）各 6 时刻 × 5 半径；`results/result2.xlsx`
（259200 行 × 21 个距离列 × 2 表，A 列 = 时间/s）。
口径：N=320、dt=1 s（§6.6「求解与输出都用 dt=1 s 直接产出」）、面值算术平均、
环境/几何取**步末层**、物性滞后一步；环境 4 h 后**零阶保持**（§3.3 第 2 条）。
运行：`python code/q2.py`
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np                                                # noqa: E402
import core                                                       # noqa: E402
from core import C0, T0                                           # noqa: E402

T_SNAP_H = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0]                          # 表 3/表 4 的 6 个时刻（题面）


def run(n_cell=320, dt=1.0, write_xlsx=True, keep_bulk=False):
    core.log("── Q2 求解：0–259200 s，附录 3，N=%d，dt=%g s" % (n_cell, dt))
    res = core.solve("q23", core.T_MAX, dt, n_cell,
                     snap_every=int(round(1800 / dt)), label="Q2")
    mon = res["mon"]
    t_out = mon["t"]
    T_C = core.round4(res["T_out"] - 273.15)
    C_4 = core.round4(res["C_out"])
    core.log("   求解完成：%d 步；阶段=%s；末步 max_rC=%.5f"
             % (len(t_out), "+".join(res["stages"]), mon["maxC"][-1]))

    # ── 表 3/表 4（0.5–3 h）
    idx = [int(np.argmin(np.abs(t_out - h * 3600.0))) for h in T_SNAP_H]
    assert all(abs(t_out[i] - h * 3600.0) < 1e-9 for i, h in zip(idx, T_SNAP_H))
    j5 = [int(round(x / 0.1)) for x in core.DIST_T5]
    table3 = [[float(T_C[i, j]) for j in j5] for i in idx]
    table4 = [[float(C_4[i, j]) for j in j5] for i in idx]

    # ── 60 s 子样本（= result3/4 的时间网格；Q3 复用同一份场）
    i60 = np.arange(int(round(60 / dt)) - 1, len(t_out), int(round(60 / dt)))
    t60 = t_out[i60]
    C21_60 = C_4[i60]
    T21_60 = T_C[i60]

    # ── 守恒/收支校核（§11.1 的离散伸缩和）
    cons = res["cons"]
    ok = np.arange(1, len(cons["t"]))
    rC = cons["dC_int"][ok] - cons["bcC"][ok]
    # 能量侧：Δ[Σ (ρc_p)_used T V] - Σ T Δ(ρc_p) V - Δt h (T∞ - T_N)/R = 0
    rE = cons["dE"][ok] - cons["bcT"][ok]
    conservation = dict(
        水分离散伸缩和=dict(max_abs_residual=float(np.max(np.abs(rC))),
                        max_abs_rhs=float(np.max(np.abs(cons["bcC"][ok]))),
                        max_rel=float(np.max(np.abs(rC)) / max(float(np.max(np.abs(cons["bcC"][ok]))), 1e-300))),
        能量离散伸缩和=dict(max_abs_residual=float(np.max(np.abs(rE))),
                        max_abs_rhs=float(np.max(np.abs(cons["bcT"][ok]))),
                        max_rel=float(np.max(np.abs(rE)) / max(float(np.max(np.abs(cons["bcT"][ok]))), 1e-300))),
        恒等式="水分 d/dt∫Cξdξ = -(h_m/R)(C(1,t)-C∞)；能量 Δ[Σ(ρc_p)T V] - ΣT Δ(ρc_p) V = Δt h(T∞-T_N)/R"
               "（Δ(ρc_p) 取**相邻两步实际使用过的容量数组**之差，§11.1）",
    )
    if not np.any(rE):
        conservation["能量离散伸缩和"]["note"] = "第 1 步无前一步容量数组，从第 2 步起计"

    # ── 自检：argmax / 单调性
    guard = core.argmax_guard(mon, kind="q23", n_cell=n_cell, dt=dt)
    mono_r = dict(C_forward_jumps=int(np.sum(np.diff(C_4, axis=1) > 0.0)),
                  T_backward_jumps=int(np.sum(np.diff(T_C, axis=1) < 0.0)))
    sc = dict(argmax护栏=guard, 空间单调性=mono_r, stages=res["stages"])

    out = dict(problem_id="2026A", stage="code", problem="Q2", n=n_cell, dt=dt,
               t_end=core.T_MAX, env_mode="hold", table3_T_C=table3, table4_C=table4,
               table_times_h=T_SNAP_H, table_radii_cm=core.DIST_T5,
               anchors=dict(
                   maxC_72h=float(mon["maxC"][-1]), C_center_72h=float(mon["C0"][-1]),
                   C_surface_72h=float(mon["Cs"][-1]),
                   T_center_72h_C=float(mon["Tc"][-1] - 273.15),
                   T_surface_72h_C=float(mon["Ts"][-1] - 273.15),
                   C_inf_72h=float(mon["Cinf"][-1]), T_inf_72h_C=float(mon["Tinf"][-1] - 273.15),
                   meanC_72h=float(mon["meanC"][-1])),
               selfcheck=sc, conservation=conservation,
               rows_in_result2=dict(n=int(len(t_out)), first=float(t_out[0]),
                                    last=float(t_out[-1]), cols=len(core.DIST_Q1)))
    core.write_json(core.results_dir() / "q2.json", out)

    if write_xlsx:
        info = core.template_info("result2.xlsx")
        head_T = [info[0]["a1"]] + core.head_list(core.DIST_Q1)
        head_C = [info[1]["a1"]] + core.head_list(core.DIST_Q1)
        core.write_result_xlsx(
            core.results_dir() / "result2.xlsx",
            [dict(sheet=info[0]["sheet"], head=head_T, times=t_out, values=T_C),
             dict(sheet=info[1]["sheet"], head=head_C, times=t_out, values=C_4)])
        core.log("   → results/result2.xlsx（%d 行 × %d 列 × 2 表）" % (len(t_out), len(core.DIST_Q1)))

    ck = core.Checkpoint(
        "q2", "Q2_全过程_附录3变物性_两阶段环境(0-4h插值,4h后零阶保持)_步末层",
        dict(kind="q23", n=n_cell, dt=dt, t_end=core.T_MAX, face="arith", env="hold",
             time_layer="step-end", rho_d="275.04 常数，已从 C 方程约去"))
    state = dict(t=t_out, t60=t60, C21_60=C21_60, T21_60=T21_60,
                 C5_1=C_4[:, j5], T5_1=T_C[:, j5], j5=np.array(j5),
                 snap_t=np.array(res["snaps"]["t"]),
                 snap_R=np.array(res["snaps"]["R"]),
                 snap_T_C=np.array(res["snaps"]["T"]) - 273.15,
                 snap_C=np.array(res["snaps"]["C"]),
                 r_cm=np.linspace(0.0, 2.0, n_cell + 1))
    for kk in ("maxC", "C0", "Cs", "Tc", "Ts", "deficit", "argmax", "Tinf", "Cinf",
               "R", "meanC", "meanT", "Tmin", "Cmin"):
        state["mon_" + kk] = mon[kk]
    if keep_bulk:
        state["T_C"] = T_C
        state["C_4"] = C_4
    ck.save(state, monitor=dict(name="q2", n=n_cell, dt=dt, t_dry_step=res["t_dry_step"],
                                maxC_72h=float(mon["maxC"][-1])))

    # 图件用的轻量数据源（figures 只依赖它，不依赖上面那个大 npz）
    core.write_json(core.out_dir() / "figdata_q2.npz.meta.json", dict(
        _method="Q2 图件数据：场快照（每 0.5 h）+ 关键时程（中心/表面/体积均值/max）+ D(C,T) 网格",
        _code_fp=core.CODE_FP, _produced_at=core._produced_at(), _stage="code",
        _params=dict(n=n_cell, dt=dt, t_end=core.T_MAX, snap_every_s=1800.0,
                     D_grid=dict(C=[0.05, 2.60, 60], T_C=[28, 52, 60],
                                 公式="附录 3 的 D(C,T)；C<0.15 段为公式外推（§10 第 5 行）"))))
    # D(C,T) 网格（**题面附录 3 的闭式**，不是对数据拟合）—— 供 q2_diffusivity 画降速曲面。
    # C 的下端取 0.05：表面状态轨迹在 72 h 末降到 C≈0.052，若网格从 0.16 起会被裁掉一截。
    # 注：$C<0.15$ 段属公式外推（§10 第 5 行已登记），图上按同一闭式绘制。
    _Cs = np.linspace(0.05, 2.60, 60)
    _Ts = np.linspace(28.0, 52.0, 60)
    _CC, _TT = np.meshgrid(_Cs, _Ts)
    _, _, _, _DD = core.props("q23", _CC, _TT + 273.15)
    np.savez_compressed(
        core.out_dir() / "figdata_q2.npz",
        t_h=mon["t"] / 3600.0, maxC=mon["maxC"], C_center=mon["C0"], C_surface=mon["Cs"],
        meanC=mon["meanC"], T_center_C=mon["Tc"] - 273.15, T_surface_C=mon["Ts"] - 273.15,
        T_inf_C=mon["Tinf"] - 273.15, C_inf=mon["Cinf"],
        snap_t_h=np.array(res["snaps"]["t"]) / 3600.0,
        snap_R=np.array(res["snaps"]["R"]),
        snap_T_C=np.array(res["snaps"]["T"]) - 273.15,
        snap_C=np.array(res["snaps"]["C"]),
        r_cm=np.linspace(0.0, 2.0, n_cell + 1),
        table3=np.array(table3), table4=np.array(table4),
        table_t_h=np.array(T_SNAP_H), table_r=np.array(core.DIST_T5),
        t60=t60, C21_60=C21_60,
        D_C=_Cs, D_T_C=_Ts, D_grid=_DD)

    core.log("   表 4 @3 h（kg/kg）: " + " ".join("%.4f" % v for v in table4[-1]))
    core.log("   72 h：max_rC=%.5f  中心 %.5f  表面 %.5f"
             % (mon["maxC"][-1], mon["C0"][-1], mon["Cs"][-1]))
    core.log("   守恒：水分 |残差|_max=%.3e（相对右端 %.3e）；能量 |残差|_max=%.3e（相对 %.3e）"
             % (conservation["水分离散伸缩和"]["max_abs_residual"],
                conservation["水分离散伸缩和"]["max_rel"],
                conservation["能量离散伸缩和"]["max_abs_residual"],
                conservation["能量离散伸缩和"]["max_rel"]))
    core.log("   argmax：全 0=%s（护栏违约 %d 步；字面违约 %d 步）"
             % (guard["argmax_all_zero"], guard["guarded_violations"], guard["literal_violations"]))
    return out, res


if __name__ == "__main__":
    core.ROOT = Path(__file__).resolve().parents[1]
    run()
