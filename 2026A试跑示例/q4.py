# -*- coding: utf-8 -*-
"""问题 4：尺寸变化下的烘干时长（附录 4 + 动边界 R(t)）。

交付：$t_{dry}^{(4)}$；表 6（每 6 h × 0/0.5/1.0/药材表面 4 列）；`results/result4.xlsx`
（60 s × 21 个数据列 = `0..1.9` + `药材表面`）。
口径（§8.5 第 1 条，与 §11.5 的登记值**同档**）：N=320、**dt=60 s**、ξ=r/R(t) 参考坐标、
1/R² 前因子 + 边界因子 R(t)、环境/几何取**步末层**、物性滞后一步。dt=1 s 作步长收敛对照。
空格规则：$r>R(t)$ 的格**留空**（不填 0、不填表面值，§8.5 第 4 条）。
运行：`python code/q4.py`
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np                                                # noqa: E402
import core                                                       # noqa: E402

TH = core.THRESH
Q4_DISTS = [round(0.1 * k, 10) for k in range(20)]                # 0 .. 1.9 cm


def run(n_cell=320, dt=60.0, label="Q4"):
    core.log("── Q4 求解：动边界 + 附录 4，N=%d，dt=%g s（交付档）" % (n_cell, dt))
    res = core.solve("q4", core.T_MAX, dt, n_cell, shrink=True,
                     snap_every=int(round(1800 / dt)), label=label)
    mon = res["mon"]
    t = mon["t"]
    g = mon["maxC"] - TH
    cross = core.locate_crossing(t, g)
    if cross["t_root"] is None:
        raise SystemExit("Q4：72 h 内未达标（应报负结果而不是给数，§7.5 停止条件）")
    t_dry = cross["t_root"]
    td_h = t_dry / 3600.0
    n_steps = int(round(cross["t_hi"] / dt))
    core.log("   t_dry = %.4f h = %.1f s；步进首达 %d 步 = %.4f h"
             % (td_h, t_dry, n_steps, cross["t_hi"] / 3600.0))

    step60 = dict(t_dry_step_first_hit_s=float(cross["t_hi"]),
                  t_dry_step_first_hit_h=float(cross["t_hi"] / 3600.0),
                  n_steps=n_steps,
                  口径="dt=60 s 网格上的步进首达（§8.5 第 1 条 / §11.5 同档）")
    proof = dict(cross_method=cross["method"], brentq_xtol=cross["xtol"], brentq_rtol=cross["rtol"],
                 g_at_prev_step=float(cross["g_at_prev_step"]),
                 g_at_prev_step_60s=float(cross["g_at_prev_step_60"]),
                 closed_form_root_s=float(cross["closed_form"]),
                 closed_form_vs_brentq_s=float(abs(cross["closed_form"] - t_dry)),
                 max_rC_at_root=float(cross["max_rC_at_root"]),
                 n_cross=cross["n_cross"], n_recross=cross["n_recross"],
                 after_max_g=float(cross["after_max_g"]),
                 t_after_max_g=float(cross["t_after_max_g"]),
                 argmax_at_root=int(mon["argmax"][int(np.argmax(t >= t_dry))]),
                 argmax_all_zero_raw=bool(np.all(mon["argmax"] == 0)))
    proof["首达后复核"] = ("t_dry 之后 max g=%.3e（<=0）、二次变号 %d 次 ⇒ 首次达标=稳定达标"
                     % (cross["after_max_g"], cross["n_recross"]))

    # ── 表 6：0 / 0.5 / 1.0 / 药材表面
    jc = [0, 5, 10]
    h6 = [6.0 * k for k in range(1, int(t_dry // (6 * 3600.0)) + 1)]
    idx6 = [int(np.argmin(np.abs(t - hh * 3600.0))) for hh in h6]
    assert all(abs(t[j] - hh * 3600.0) < 1e-9 for j, hh in zip(idx6, h6))
    table6 = []
    for hh, j in zip(h6, idx6):
        Rcm = mon["R"][j] * 100.0
        row = [float(hh)]
        for k in jc:
            rcm = core.DIST_Q1[k]
            row.append(float(core.round4(res["C_out"][j, k])) if rcm <= Rcm + 1e-9 else None)
        row.append(float(core.round4(mon["Cs"][j])))
        table6.append(row)
    last_row = [float(core.round4(td_h))]
    for k in jc:
        last_row.append(float(core.round4(np.interp(t_dry, t, res["C_out"][:, k]))))
    last_row.append(float(core.round4(np.interp(t_dry, t, mon["Cs"]))))
    table6.append(last_row)

    # ── result4.xlsx：60 s 网格，末行 >= t_dry；末列 = 动表面
    last_t = core.last_row_time(t_dry, 60.0)
    sel = np.arange(int(round(last_t / dt)))                     # 交付档 dt=60 s ⇒ 直接是行号
    assert abs(t[sel[-1]] - last_t) < 1e-9
    C20 = res["C_out"][sel][:, :20]
    Csurf = mon["Cs"][sel].reshape(-1, 1)
    vals = np.concatenate([C20, Csurf], axis=1)
    vals = core.round4(vals)
    vals = np.where(np.isnan(vals), np.nan, vals)
    info = core.template_info("result4.xlsx")
    head = [info[0]["a1"]] + core.head_list(Q4_DISTS, last_label=core.SURFACE_LABEL)
    assert head[-1] == core.SURFACE_LABEL and len(head) == 22
    core.write_result_xlsx(core.results_dir() / "result4.xlsx",
                           [dict(sheet=info[0]["sheet"], head=head, times=t[sel], values=vals)])
    n_blank = int(np.sum(np.isnan(vals)))
    core.log("   → results/result4.xlsx（%d 行 × %d 数据列；r>R(t) 留空格 %d 个）"
             % (len(sel), 21, n_blank))

    # ── dt=60 s 与 dt=1 s 的步长对照（§11.2 的步长收敛行同精神；Q4 单独一行）
    res1 = core.solve("q4", core.T_MAX, 1.0, n_cell, shrink=True, sample=False,
                      keep_cons=False, label="Q4 dt1")
    c1 = core.locate_crossing(res1["mon"]["t"], res1["mon"]["maxC"] - TH)
    step_conv = dict(dt60_h=float(td_h),
                     dt60_step_first_hit_h=float(cross["t_hi"] / 3600.0),
                     dt1_h=float(c1["t_root"] / 3600.0) if c1["t_root"] else None,
                     dt1_step_first_hit_h=float(c1["t_hi"] / 3600.0) if c1["t_root"] else None,
                     diff_h=float(abs(td_h - c1["t_root"] / 3600.0)) if c1["t_root"] else None)

    # ── V1 恒等校验（§8.5 第 2 条）：R≡R0 时收缩求解器必须与固定域求解器逐位一致
    rad0 = core.Radius(np.array([0.0, 1.0e9]), np.array([core.R0, core.R0]))
    a = core.solve("q23", 7200.0, 60.0, n_cell, shrink=True, rad=rad0, sample=False,
                   keep_cons=False, label="V1-shrink-const")
    b = core.solve("q23", 7200.0, 60.0, n_cell, shrink=False, sample=False,
                   keep_cons=False, label="V1-fixed")
    v1 = dict(note="同实现内两分支走同一算式、同序运算 ⇒ 逐位一致（§8.5 第 2 条、§11.2 表）",
              max_abs_dC=float(np.max(np.abs(a["mon"]["Cs"] - b["mon"]["Cs"]))),
              max_abs_dT=float(np.max(np.abs(a["mon"]["Ts"] - b["mon"]["Ts"]))),
              bitwise=bool(np.array_equal(a["mon"]["Cs"], b["mon"]["Cs"]) and
                           np.array_equal(a["mon"]["Ts"], b["mon"]["Ts"])),
              未用T比较="用表面温度/浓度序列逐位比较（全场需另存；同源同序 ⇒ 等价判据）")

    out = dict(problem_id="2026A", stage="code", problem="Q4", n=n_cell, dt=dt,
               t_end=core.T_MAX, shrink=True, radius_mode="linear", face="arith",
               t_dry_s=float(t_dry), t_dry_h=float(td_h), t_dry_h_4dp=float(core.round4(td_h)),
               step60=step60, step_conv=step_conv, proof=proof, v1=v1,
               table6=table6, table6_radii_cm=core.DIST_T6 + ["药材表面"],
               last_row_s=float(last_t), last_row_h=float(last_t / 3600.0),
               delta_last_row_minus_tdry_s=float(last_t - t_dry),
               n_blank_cells=n_blank,
               R_at_6h_cm=float(mon["R"][idx6[0]] * 100.0) if idx6 else None,
               R_end_cm=float(mon["R"][-1] * 100.0),
               rows_in_result4=dict(n=int(len(sel)), first=float(t[sel[0]]),
                                    last=float(t[sel[-1]]), cols=22))
    core.write_json(core.results_dir() / "q4.json", out)

    ck = core.Checkpoint(
        "q4", "Q4_动边界_附录4_ξ参考坐标_1overR2前因子+边界R因子_步末层_面值算术平均",
        dict(kind="q4", n=n_cell, dt=dt, t_end=core.T_MAX, shrink=True, face="arith",
             env="hold", time_layer="step-end", radius="附件2 分段线性",
             rho_d="rho_d0*(R0/R)^2（干物质守恒+仿射收缩+定长圆柱）"))
    ck.save(dict(t=t, C5_1=res["C_out"][:, [0, 5, 10, 15, 20]], T5_1=res["T_out"][:, [0, 5, 10, 15, 20]],
                 R=mon["R"], Cs=mon["Cs"], C0=mon["C0"], maxC=mon["maxC"],
                 snap_t=np.array(res["snaps"]["t"]), snap_R=np.array(res["snaps"]["R"]),
                 snap_T_C=np.array(res["snaps"]["T"]) - 273.15,
                 snap_C=np.array(res["snaps"]["C"]),
                 xi=np.linspace(0.0, 1.0, n_cell + 1)),
            monitor=dict(name="q4", n=n_cell, dt=dt, t_dry_step=float(cross["t_hi"]),
                         n_steps=n_steps))

    core.write_json(core.out_dir() / "figdata_q4.npz.meta.json", dict(
        _method="Q4 图件数据：ξ 场快照（每 0.5 h）+ R(t) + maxC/中心/表面时程",
        _code_fp=core.CODE_FP, _produced_at=core._produced_at(), _stage="code",
        _params=dict(n=n_cell, dt=dt, t_end=core.T_MAX, shrink=True, snap_every_s=1800.0)))
    np.savez_compressed(
        core.out_dir() / "figdata_q4.npz",
        t_h=t / 3600.0, maxC=mon["maxC"], C_center=mon["C0"], C_surface=mon["Cs"],
        R_cm=mon["R"] * 100.0, T_center_C=mon["Tc"] - 273.15, T_surface_C=mon["Ts"] - 273.15,
        snap_t_h=np.array(res["snaps"]["t"]) / 3600.0,
        snap_R_cm=np.array(res["snaps"]["R"]) * 100.0,
        snap_C=np.array(res["snaps"]["C"]),
        snap_T_C=np.array(res["snaps"]["T"]) - 273.15,
        xi=np.linspace(0.0, 1.0, n_cell + 1),
        table6=np.array([[v if v is not None else np.nan for v in r] for r in table6]),
        t_dry_h=float(td_h), last_row_h=float(last_t / 3600.0))

    core.log("   表 6 末行（%.4f h）: %s" % (td_h, " ".join(
        "—" if v is None else "%.4f" % v for v in last_row[1:])))
    core.log("   V1 恒等：max|ΔC|=%.3e  max|ΔT|=%.3e（逐位一致=%s）"
             % (v1["max_abs_dC"], v1["max_abs_dT"], v1["bitwise"]))
    core.log("   步长对照：dt=60 s → %.4f h；dt=1 s → %s h（差 %s h）"
             % (td_h, "%.4f" % step_conv["dt1_h"] if step_conv["dt1_h"] else "—",
                "%.4f" % step_conv["diff_h"] if step_conv["diff_h"] is not None else "—"))
    return out, res


if __name__ == "__main__":
    core.ROOT = Path(__file__).resolve().parents[1]
    run()
