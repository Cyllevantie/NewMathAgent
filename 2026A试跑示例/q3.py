# -*- coding: utf-8 -*-
"""问题 3：烘干所需时间（全场达标，判据 max_r C <= 0.15）。

模型与 Q2 **完全一致**（§7.3：本问不引入新的建模约定）⇒ 直接在 Q2 的解上做事件定位，
不重解。交付：$t_{dry}$（h）；表 5（每 6 h × 0.5 cm，末行「烘干结束时间」）；
`results/result3.xlsx`（60 s × 0.1 cm，单表）。
运行：`python code/q3.py`（需先跑 `code/q2.py`）
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np                                                # noqa: E402
import core                                                       # noqa: E402

TH = core.THRESH


def load_q2():
    p = core.out_dir() / "q2.npz"
    if not p.is_file():
        raise SystemExit("找不到 %s —— 请先运行 code/q2.py" % p)
    # ⚠️ `Checkpoint.save` 写的方法标记是 **`<name>.npz.meta.json`**（stage_discipline §4.1 的
    #    「同名 `.meta.json`」= 与**产物**同名，产物是 `q2.npz`）。早先这里读的是 `q2.meta.json`
    #    —— 那个文件**从来没有**被任何代码写过 ⇒ `python code/q3.py`（以及 `run_all.py` 里
    #    的 `Q3.run()`）在本步直接 FileNotFoundError。**可复现性缺陷**，只有真去跑 q3.py 才暴露
    #    （本轮返修被门禁要求重跑 q3.py 才撞上；已在报告末节登记）。
    import json
    for cand in ("q2.npz.meta.json", "q2.meta.json"):
        meta = core.out_dir() / cand
        if meta.is_file():
            break
    else:
        raise SystemExit("找不到 q2 的方法标记（试过 q2.npz.meta.json / q2.meta.json）"
                         " —— 请先运行 code/q2.py")
    m = json.loads(meta.read_text(encoding="utf-8"))
    return dict(np.load(p)), m


def run():
    d, meta = load_q2()
    t = d["t"]
    maxC = d["mon_maxC"]
    C5 = d["C5_1"]                       # 1 s 分辨率、5 个半径列
    j5 = list(d["j5"])
    g = maxC - TH

    core.log("── Q3 事件定位（在 Q2 的 %s 上，dt=%g s）" % (meta["_method"][:28], meta["_params"]["dt"]))
    cross = core.locate_crossing(t, g)
    t_dry = cross["t_root"]
    if t_dry is None:
        raise SystemExit("Q3：72 h 内未达标，按 §7.5 停止条件报负结果而不给数")
    td_h = t_dry / 3600.0

    # ── 判据自证（§7.8）
    # ⚠️ 两个**不同口径**的值必须分列登记、各自带全时刻（审计 `aud-q3-root-label`）：
    #   · `max_rC_at_root`             = t_dry 的**线性插值场**在该时刻的 max_rC
    #                                    （`locate_crossing` 的 THRESH+lin(root)，构造上恒等于阈值）；
    #   · `max_rC_at_first_hit_step`   = **首个满足判据的计算步**（1 s 网格上 t=205698 s）实测 max_rC。
    #   后者才是**独立的物理证据**（前者是插值构造，不能当独立证据引）。
    #   旧实现给末项配了**常量 0 的插值权重**，整式退化成「阈值 + 前一步的 g」—— 于是这个字段记的是
    #   **前一步**的值（且字面上 >0.15）。该死表达式已删除（改动面见 §9.4 的复验记录）。
    #   ⚠️ 注释里**刻意不原样复述那句被删的表达式** —— 否则下一轮用字面检索复核"它删没删"会假阳。
    i = int(np.argmax(t >= t_dry))
    g_prev = float(g[i - 1])
    g_at = float(maxC[i] - TH)
    proof = dict(
        t_dry_s=float(t_dry), t_dry_h=float(td_h),
        max_rC_at_root=float(cross["max_rC_at_root"]),
        max_rC_at_root_口径="t_dry 的**线性插值场**在该时刻的 max_rC（构造上 = 0.15，"
                            "是插值构造、不是独立物理证据；独立证据见 max_rC_at_first_hit_step）",
        max_rC_at_first_hit_step=float(maxC[i]),
        max_rC_at_first_hit_step_口径="**首个满足判据的计算步**（1 s 网格 t=205698 s）实测 max_rC"
                                      "（未舍入；独立于插值构造）",
        g_at_step_before=float(cross["g_at_prev_step"]),
        # ⚠️ 键名里的 "60s" 是**误读陷阱**：`g[i-2]` 是「2 步之前」，在 1 s 网格上等于 **1.7554 s 之前**
        #    （t=205696 s），不是 60 s 之前。读数时一律以同组的 t_prev2_step 为准（审计 `adv-q3-prevstep-label`）。
        g_at_prev2_step=float(g[i - 2]),
        t_prev2_step=float(t[i - 2]),
        g_at_prev2_step_口径="2 个时间步之前（Δt=1 s ⇒ 1.7554 s 之前，t=205696 s）的 g；"
                             "键名不含「60 s」，勿按 60 s 读",
        g_at_first_hit_step=float(cross["g_hi"]),
        t_first_hit_step=float(cross["t_hi"]),
        cross_method=cross["method"], brentq_xtol=cross["xtol"], brentq_rtol=cross["rtol"],
        closed_form_root_s=float(cross["closed_form"]),
        closed_form_vs_brentq_s=float(abs(cross["closed_form"] - t_dry)),
        n_cross=cross["n_cross"], n_recross=cross["n_recross"],
        after_max_g=float(cross["after_max_g"]), t_after_max_g=float(cross["t_after_max_g"]),
        C_center_at_root=float(np.interp(t_dry, t, d["mon_C0"])),
        argmax_at_root=int(d["mon_argmax"][i]),
        argmax_at_root_口径="取**首个满足判据的计算步**（1 s 网格 t=205698 s）的 argmax_rC；"
                            "该步 argmax=0 与根处一致（最坏点在轴心）",
    )
    proof["判据"] = ("首达之后 max_rC<=0.15 保持：after_max_g=%.3e <= 0；"
                   "二次变号 %d 次 ⇒ 首次达标与稳定达标一致（§7.5 第 5 条）"
                   % (cross["after_max_g"], cross["n_recross"]))

    # ── 表 5（每 6 h 直到最后一个 <= t_dry 的 6 h 倍数，然后末行 = t_dry）
    t60 = d["t60"]
    C21_60 = d["C21_60"]
    h6 = [6.0 * k for k in range(1, int(t_dry // (6 * 3600.0)) + 1)]
    idx6 = [int(np.argmin(np.abs(t60 - hh * 3600.0))) for hh in h6]
    assert all(abs(t60[j] - hh * 3600.0) < 1e-9 for j, hh in zip(idx6, h6))
    rows = [[float(hh)] + [float(C21_60[j, k]) for k in j5] for hh, j in zip(h6, idx6)]
    last_vals = [float(np.interp(t_dry, t, C5[:, k])) for k in range(C5.shape[1])]
    rows.append([float(core.round4(td_h))] + list(core.round4(last_vals)))
    table5 = rows
    table5_label = "烘干结束时间"

    # ── result3.xlsx（60 s 网格，末行 >= t_dry）
    last_t = core.last_row_time(t_dry, 60.0)
    n_last = int(round(last_t / 60.0))
    sel = np.arange(0, n_last)
    assert abs(t60[sel[-1]] - last_t) < 1e-9, "末行必须落回 60 s 网格点"
    core.log("   t_dry = %.4f h = %.1f s；交付件末行 = %.0f s（%d 行）" % (td_h, t_dry, last_t, n_last))
    info = core.template_info("result3.xlsx")
    head_C = [info[0]["a1"]] + core.head_list(core.DIST_Q1)
    core.write_result_xlsx(core.results_dir() / "result3.xlsx",
                           [dict(sheet=info[0]["sheet"], head=head_C,
                                 times=t60[sel], values=C21_60[sel])])
    core.log("   → results/result3.xlsx（%d 行 × %d 列 × 1 表）" % (n_last, len(core.DIST_Q1)))

    # ── 与「首个达标 60 s 行」的一致性（§7.4 末行口径）
    i60 = int(np.argmax(t60 >= t_dry))
    out = dict(problem_id="2026A", stage="code", problem="Q3", dt=float(meta["_params"]["dt"]),
               n=int(meta["_params"]["n"]), reuse="Q2 的解（同模型，§7.3 不引入新约定）",
               t_dry_s=float(t_dry), t_dry_h=float(td_h),
               t_dry_h_4dp=float(core.round4(td_h)),
               t_dry_step_first_hit_h=float(cross["t_hi"] / 3600.0),
               first_达标_60s_row_h=float(t60[i60] / 3600.0),
               last_row_s=float(last_t), last_row_h=float(last_t / 3600.0),
               delta_last_row_minus_tdry_s=float(last_t - t_dry),
               table5_times_h=[r[0] for r in table5], table5=table5,
               table5_radii_cm=core.DIST_T5, table5_last_label=table5_label,
               proof=proof, rows_in_result3=dict(n=int(n_last), first=float(t60[0]),
                                                 last=float(t60[sel[-1]]),
                                                 cols=len(core.DIST_Q1)),
               display_note="显示为 0.1500 的格，其未舍入值可能仍 >= 0.15（§7.7 第 1 条、A10）")
    core.write_json(core.results_dir() / "q3.json", out)

    core.log("   判据自证（两口径分列）：2 步前（t=%.0f s = t_dry-%.4f s）g=%.3e > 0；"
             "首达步 t=%.0f s（Δt=1 s）max_rC=%.9f <= 0.15；"
             "根处（t=%.4f s 的线性插值场）max_rC=%.6f（构造上 = 阈值）"
             % (t[i - 2], t_dry - t[i - 2], g[i - 2], t[i], maxC[i], t_dry,
                cross["max_rC_at_root"]))
    core.log("   首达后复核：max g=%.3e（<=0）、二次变号 %d 次" % (cross["after_max_g"], cross["n_recross"]))
    core.log("   闭式根与 brentq 差 %.3e s（线性插值下二者应同值）"
             % abs(cross["closed_form"] - t_dry))
    return out


if __name__ == "__main__":
    core.ROOT = Path(__file__).resolve().parents[1]
    run()
