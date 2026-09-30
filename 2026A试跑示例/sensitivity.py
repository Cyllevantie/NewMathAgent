# -*- coding: utf-8 -*-
"""收敛性（§11.2）与口径敏感性（§11.3/§11.5）、守恒与恒等校核（§11.1）、解析级数校核。

本模块**只做诊断与对照**：所有档位都复用 `core.solve` 的同一实现（只换档位开关），
**不改交付口径**；交付数值一律取主档（面值算术平均 + 零阶保持 + 步末层 + 参考坐标纯 Fick）。
产物：`results/convergence.json`、`results/sensitivity.json`、`code/outputs/figdata_sens.npz`。
运行：`python code/sensitivity.py`
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np                                                # noqa: E402
import core                                                       # noqa: E402
from core import C0, T0                                           # noqa: E402

TH = core.THRESH


class ConstEnv(core.Env):
    """**全程常数**环境（T∞、C∞ 与 t 无关）—— 只给 `steady_limit_const50` 那一支用。

    为什么在 sensitivity.py 里子类化、而不是往 `core.Env` 加档：`core.Env` 的档位开关会进
    `out["env_mode"]` 并影响交付链的默认值，而这一支**不支撑任何交付数值**、只是稳态校核。
    `core.solve` 本来就接受外部 `env=` 实例，子类化对其余分支零影响。
    """

    def __init__(self, T_inf_C, C_inf):
        super().__init__(np.array([0.0, 1.0]), np.array([T_inf_C, T_inf_C]),
                         np.array([C_inf, C_inf]), mode="const")
        self.T_inf_C, self.C_inf = float(T_inf_C), float(C_inf)

    def at(self, t):
        return self.T_inf_C + 273.15, self.C_inf

    def stage(self, t):
        return "恒温干燥段"


def tdry(kind="q23", n=320, dt=60.0, shrink=False, **kw):
    """跑一档并返回 t_dry（步进首达 + 连续根）。"""
    t_end = kw.pop("t_end", core.T_MAX)
    res = core.solve(kind, t_end, dt, n, shrink=shrink, sample=False, keep_cons=False, **kw)
    cross = core.locate_crossing(res["mon"]["t"], res["mon"]["maxC"] - TH)
    return dict(n=n, dt=dt, t_dry_step_s=res["t_dry_step"],
                t_dry_step_h=(None if res["t_dry_step"] is None else res["t_dry_step"] / 3600.0),
                n_steps=(None if res["t_dry_step"] is None else int(round(res["t_dry_step"] / dt))),
                t_dry_root_s=cross["t_root"],
                t_dry_root_h=(None if cross["t_root"] is None else cross["t_root"] / 3600.0),
                maxC_end=float(res["mon"]["maxC"][-1]))


def _field21(kind, n, dt, t_end=1800.0):
    """在公共 0.1 cm 网格上取 t_end 时刻的场（用于场级收敛）。"""
    r = core.solve(kind, t_end, dt, n, sample=True, keep_cons=False, snap_every=None)
    return r["T_out"][-1] - 273.15, r["C_out"][-1]


def convergence():
    core.log("── 收敛性（§11.2）")
    mesh = {}
    for n in (80, 160, 320, 640):
        mesh[n] = tdry(n=n, dt=60.0)
        core.log("   网格 n=%-4d t_dry=%.4f h（步进首达）" % (n, mesh[n]["t_dry_step_h"]))
    step = {}
    for dt in (60.0, 30.0, 10.0, 1.0):
        step[dt] = tdry(n=320, dt=dt)
        core.log("   步长 dt=%-5g t_dry=%.4f h（步进首达）/ %.4f h（连续根）"
                 % (dt, step[dt]["t_dry_step_h"], step[dt]["t_dry_root_h"]))
    # 场级网格收敛（表 1 取 5 个半径列、表 2 取全 21 列 —— §11.2 的取值范围注）
    j5 = [int(round(x / 0.1)) for x in core.DIST_T5]
    fmesh = {}
    T320, C320 = _field21("q1", 320, 1.0)
    for n in (160, 640):
        Tf, Cf = _field21("q1", n, 1.0)
        fmesh[f"{n}->320" if n < 320 else "320->640"] = dict(
            N_pair=[n, 320] if n < 320 else [320, 640],
            max_dT_5cols=float(np.max(np.abs(Tf[j5] - T320[j5]))) if n < 320
            else float(np.max(np.abs(T320[j5] - Tf[j5]))),
            max_dC_21cols=float(np.max(np.abs(Cf - C320))))
    # 场级步长收敛（n=320）。★ **两个时刻都要报**：交付表含 t=100–1500 s 的行，
    #   而精度限定原先只在 t=1800 s 取材 ⇒ 覆盖不到早期行（审计 `aud-precision-scope-earlytime`）。
    #   同一实现、同一档序列，只换取样时刻，两处并列给出。
    def _step_sweep(t_end):
        sweep, prev, fields = {}, None, {}
        for dt in (60.0, 10.0, 5.0, 2.0, 1.0, 0.5):
            Tf, Cf = _field21("q1", 320, dt, t_end=t_end)
            fields[dt] = (Tf, Cf)
            if prev is not None:
                sweep[f"{prev[0]:g}->{dt:g}"] = dict(
                    dt_pair=[prev[0], dt],
                    max_dT_5cols=float(np.max(np.abs(Tf[j5] - prev[1][j5]))),
                    max_dC_21cols=float(np.max(np.abs(Cf - prev[2]))),
                    dC_surface=float(abs(Cf[-1] - prev[2][-1])),
                    dT_max=float(np.max(np.abs(Tf - prev[1]))))
            prev = (dt, Tf, Cf)
        T05, C05 = fields[0.5]
        T1, C1 = fields[1.0]
        rich = dict(T_center_1s=float(T1[0]), T_center_0p5=float(T05[0]),
                    T_center_limit=float(T05[0] + (T05[0] - T1[0])),
                    T_surface_limit=float(T05[-1] + (T05[-1] - T1[-1])),
                    C_limit_max_abs=float(np.max(np.abs((C05 + (C05 - C1)) - C1))),
                    C_surface_1s=float(C1[-1]), C_surface_0p5=float(C05[-1]),
                    dT_surface_1s_to_0p5=float(T05[-1] - T1[-1]),
                    dC_surface_1s_to_0p5=float(C05[-1] - C1[-1]),
                    note="一阶（隐式欧拉）Richardson：f* ≈ f_{Δ/2} + (f_{Δ/2} - f_Δ)")
        return sweep, rich

    fstep, rich = _step_sweep(1800.0)
    fstep_early, rich_early = _step_sweep(100.0)
    core.log("   场级步长收敛 t=1800 s：表1 5 列最细档差 %.3e K、表2 21 列 %.3e"
             % (fstep["1->0.5"]["max_dT_5cols"], fstep["1->0.5"]["max_dC_21cols"]))
    core.log("   场级步长收敛 t=100  s：表1 5 列最细档差 %.3e K、表2 21 列 %.3e（早期时刻更大）"
             % (fstep_early["1->0.5"]["max_dT_5cols"], fstep_early["1->0.5"]["max_dC_21cols"]))
    out = dict(problem_id="2026A", stage="code",
               mesh_tdry={str(k): v for k, v in mesh.items()},
               step_tdry={("%g" % k): v for k, v in step.items()},
               field_mesh=fmesh, field_step=fstep, richardson=rich,
               field_step_early=fstep_early, richardson_early=rich_early,
               note_mesh="§11.2：n=80/160/320/640 → 56.9833/57.1000/57.1500/57.1667 h（Δt=60 s 步进首达）",
               note_step="§11.2：Δt=60 与 0.5 s 使表 1 的 5 列差 6.001e-4 K、表 2 的 21 列差 5.323e-5",
               note_early="早期时刻（t=100 s）的**同一**档序列：时间离散误差比 t=1800 s 大得多 —— "
                          "交付表的 t=100–1500 s 行不能按 t=1800 s 那一档的精度声明去读"
                          "（审计 `aud-precision-scope-earlytime`）")
    core.write_json(core.results_dir() / "convergence.json", out)
    return out


def sensitivity():
    core.log("── 口径敏感性（§11.3/§11.5）")
    rows = {}
    rows["main_n320_dt60"] = tdry(n=320, dt=60.0)
    for face in ("geom", "harm"):
        rows[f"face_{face}_n320_dt60"] = tdry(n=320, dt=60.0, face=face)
        core.log("   面导度 %-5s n=320 dt=60: %.4f h" % (face, rows[f"face_{face}_n320_dt60"]["t_dry_step_h"]))
    for mode in ("peak", "plateau"):
        rows[f"env_{mode}_n160_dt60"] = tdry(n=160, dt=60.0, env_mode=mode)
        core.log("   环境 %-8s n=160 dt=60: %.4f h" % (mode, rows[f"env_{mode}_n160_dt60"]["t_dry_step_h"]))
    rows["env_cut1800_n160_dt60"] = tdry(n=160, dt=60.0, env_mode="cut1800", t_end=120 * 3600.0)
    core.log("   环境 切换点1800 s（证伪档）n=160: %.4f h（跑到 120 h）"
             % (rows["env_cut1800_n160_dt60"]["t_dry_step_h"] or -1))
    for tag, kw in (("hm_x10", dict(hm=core.HM * 10)),
                    ("hm_x0p1", dict(hm=core.HM * 0.1)),
                    ("h_half", dict(hc=core.H_C * 0.5))):
        rows[f"{tag}_n160_dt60"] = tdry(n=160, dt=60.0, **kw)
        core.log("   %-8s n=160 dt=60: %s h"
                 % (tag, "72 h 内未达标" if rows[f"{tag}_n160_dt60"]["t_dry_step_h"] is None
                    else "%.4f" % rows[f"{tag}_n160_dt60"]["t_dry_step_h"]))
    # 相变两档（§11.3，n=80、Δt=60 s，基准 = n=80 主档 56.9833 h）
    base80 = tdry(n=80, dt=60.0)
    rows["phase_base_n80_dt60"] = base80
    for tag, kw in (("latent", dict(latent=True)),
                    ("enthalpy_rewrite_K", dict(sensible=True)),
                    ("enthalpy_rewrite_C", dict(sensible=True, sensible_scale="C")),
                    ("both", dict(latent=True, sensible=True))):
        rows[f"phase_{tag}_n80_dt60"] = tdry(n=80, dt=60.0, **kw)
        v = rows[f"phase_{tag}_n80_dt60"]["t_dry_step_h"]
        core.log("   相变 %-16s n=80 dt=60: %s h（偏移 %+.4f h）"
                 % (tag, "—" if v is None else "%.4f" % v, 0.0 if v is None else v - base80["t_dry_step_h"]))
    # §11.5 效应分解（统一 n=320、Δt=60 s）
    rows["decomp_q3_appendix3_fixed"] = rows["main_n320_dt60"]
    rows["decomp_shrink_appendix3"] = tdry(kind="q23", n=320, dt=60.0, shrink=True)
    rows["decomp_q4_appendix4_shrink"] = tdry(kind="q4", n=320, dt=60.0, shrink=True)
    rows["decomp_appendix4_fixed"] = tdry(kind="q4", n=320, dt=60.0, shrink=False)
    core.log("   §11.5 分解：Q3 %.4f / 收缩+附3 %.4f / Q4 %.4f / 附4不收缩 %s"
             % (rows["decomp_q3_appendix3_fixed"]["t_dry_step_h"],
                rows["decomp_shrink_appendix3"]["t_dry_step_h"],
                rows["decomp_q4_appendix4_shrink"]["t_dry_step_h"],
                "72 h 内未达标" if rows["decomp_appendix4_fixed"]["t_dry_step_h"] is None else "%.4f"
                % rows["decomp_appendix4_fixed"]["t_dry_step_h"]))
    # R(t) 阶梯档（§10 第 13 行）
    rows["radius_step_n320_dt60"] = tdry(kind="q4", n=320, dt=60.0, shrink=True, radius_mode="step")
    core.log("   R(t) 阶梯档：%.4f h（主档分段线性 %.4f h）"
             % (rows["radius_step_n320_dt60"]["t_dry_step_h"],
                rows["decomp_q4_appendix4_shrink"]["t_dry_step_h"]))

    out = dict(problem_id="2026A", stage="code", calibers=rows,
               note="全部为 Δt=60 s 网格上的**步进首达**（§11.5 的档位标签）；"
                    "主档 = 面值算术平均 + 零阶保持 + 无相变项 + ξ 参考坐标纯 Fick",
               phase_base_n80_h=base80["t_dry_step_h"])
    core.write_json(core.results_dir() / "sensitivity.json", out)
    return out


def consistency():
    """守恒（§11.1）、V1 恒等（§8.5 第 2 条）、两次运行逐位一致（§13 统一契约）。"""
    core.log("── 一致性与可复现（§11.1 / §8.5 / §13）")
    rep = {}
    # (1) 两次运行逐位一致（Q1 全窗；Q4 60 s 档全程）
    a = core.solve("q1", 1800.0, 1.0, 320, sample=True, keep_cons=True)
    b = core.solve("q1", 1800.0, 1.0, 320, sample=True, keep_cons=True)
    rep["determinism_q1"] = dict(
        T_bitwise=bool(np.array_equal(a["T_out"], b["T_out"])),
        C_bitwise=bool(np.array_equal(a["C_out"], b["C_out"])),
        tdry_bitwise=bool(a["t_dry_step"] == b["t_dry_step"]))
    c = core.solve("q4", core.T_MAX, 60.0, 320, shrink=True, sample=False, keep_cons=False)
    d = core.solve("q4", core.T_MAX, 60.0, 320, shrink=True, sample=False, keep_cons=False)
    rep["determinism_q4"] = dict(maxC_bitwise=bool(np.array_equal(c["mon"]["maxC"], d["mon"]["maxC"])),
                                 tdry_bitwise=bool(c["t_dry_step"] == d["t_dry_step"]))
    core.log("   两次运行逐位一致：Q1 %s / Q4 %s"
             % (rep["determinism_q1"], rep["determinism_q4"]))
    # (2) 守恒残差（Q1、Q2、Q4 各一份）
    for tag, kind, dt, shrink in (("q1", "q1", 1.0, False), ("q4_60s", "q4", 60.0, True)):
        r = core.solve(kind, 1800.0 if kind == "q1" else core.T_MAX, dt, 320,
                       shrink=shrink, sample=False, keep_cons=True)
        cons = r["cons"]
        ok = np.arange(1, len(cons["t"]))
        rC = cons["dC_int"][ok] - cons["bcC"][ok]
        rE = cons["dE"][ok] - cons["bcT"][ok]
        rep[f"conservation_{tag}"] = dict(
            water_max_abs=float(np.max(np.abs(rC))),
            water_max_rel=float(np.max(np.abs(rC)) / max(float(np.max(np.abs(cons["bcC"][ok]))), 1e-300)),
            energy_max_abs=float(np.max(np.abs(rE))),
            energy_max_rel=float(np.max(np.abs(rE)) / max(float(np.max(np.abs(cons["bcT"][ok]))), 1e-300)))
    core.log("   守恒：Q1 %s；Q4 %s" % (rep["conservation_q1"], rep["conservation_q4_60s"]))
    # (3) 解析级数校核（常数物性、第一类边界极限）
    rep["analytic"] = analytic_check()
    core.log("   解析级数校核：%s" % rep["analytic"]["temperature"]["text"])
    core.log("                    %s" % rep["analytic"]["moisture"]["text"])
    # (4) 稳态极限（**两支**，环境值一律与"实际用的那一档"同口径 —— 审计 `aud-steady-limit-source`）
    #   旧实现的 note 写「T∞=50 °C、C∞=0.15」而该支实跑 `env_mode="hold"` ⇒ 环境是
    #   **附件 1 的 14400 s 末值** 50.165 °C / 0.04986 kg/kg（0.15 是 Q3 的**达标阈值**，不是环境值），
    #   报告据此印出的「温度精确趋于 50.000000 °C」在它自己的来源里找不到。现按实际档写全，
    #   并另跑一支 T∞ ≡ 50 °C 的**真正常数环境**档，单独登记。
    _t_env, _Tc_env, _C_env = core.load_env()
    T_INF_HOLD = float(_Tc_env[-1])          # 50.165 °C（附件 1 末值）
    C_INF_HOLD = float(_C_env[-1])           # 0.04986 kg/kg
    assert abs(T_INF_HOLD - 50.165) < 1e-12 and abs(C_INF_HOLD - 0.04986) < 1e-12

    def _steady(run, note, **extra):
        return dict(note=note, t_end_s=200000.0, n=40, dt=200.0,
                    T_min_C=float(run["mon"]["Tmin"][-1] - 273.15),
                    T_max_C=float(run["mon"]["Tc"][-1] - 273.15),
                    C_min=float(run["mon"]["Cmin"][-1]),
                    C_max=float(run["mon"]["C0"][-1]), **extra)

    r = core.solve("q23", 200000.0, 200.0, 40, sample=False, keep_cons=False,
                   env=None, label="steady", env_mode="hold")
    rep["steady_limit"] = _steady(
        r,
        "固定环境 = **交付主档的零阶保持档 `hold`** 的续用值（T∞ = %.3f °C、C∞ = %.5f kg/kg，"
        "取自附件 1 的 t=14400 s 末值；**不是** 50 °C / 0.15 —— 0.15 是 Q3 的达标阈值而非环境值）"
        "长时间推进：温度应处处趋于 T∞" % (T_INF_HOLD, C_INF_HOLD),
        档名="hold", T_inf_C=T_INF_HOLD, C_inf=C_INF_HOLD,
        T_inf_source="附件 1（request/attachments/附件1.xlsx）第 241 点、t=14400 s 的末值")

    rc = core.solve("q23", 200000.0, 200.0, 40, sample=False, keep_cons=False,
                    env=ConstEnv(50.0, C_INF_HOLD), label="steady-const50")
    rep["steady_limit_const50"] = _steady(
        rc,
        "固定环境（**全程常数**支：T∞ ≡ 50.000 °C，C∞ = %.5f kg/kg 同主档）长时间推进："
        "温度应精确趋于 50.000000 °C" % C_INF_HOLD,
        档名="const50", T_inf_C=50.0, C_inf=C_INF_HOLD,
        T_inf_source="该支显式给定 T∞≡50 °C（不由附件 1 取）；仅作温度侧稳态校核，"
                     "**不支撑任何交付数值**")
    core.log("   稳态极限（hold）：T∈[%.12f, %.12f] °C（T∞=%.3f）"
             % (rep["steady_limit"]["T_min_C"], rep["steady_limit"]["T_max_C"], T_INF_HOLD))
    core.log("   稳态极限（const50）：T∈[%.12f, %.12f] °C（T∞=50.000）"
             % (rep["steady_limit_const50"]["T_min_C"], rep["steady_limit_const50"]["T_max_C"]))
    out = dict(problem_id="2026A", stage="code", **rep)
    core.write_json(core.results_dir() / "consistency.json", out)
    return out


def analytic_check():
    """常数物性 + 第一类边界极限 vs 无限长圆柱级数解（§11.2 的温度行/水分行）。"""
    from scipy.special import j0, j1, jn_zeros

    def series(fo, rr, nterm=24):
        s = np.zeros_like(np.atleast_1d(np.asarray(rr, float)))
        for m in jn_zeros(0, nterm):
            s = s + (2.0 / (m * j1(m))) * j0(m * np.asarray(rr, float)) * np.exp(-m * m * fo)
        return s

    def march(n, dt, tstop, kap, h_bc, u_inf, u0):
        xi, xf, dx, V = core.grid(n)
        U = np.full(n + 1, u0)
        for _ in range(int(round(tstop / dt))):
            U = core.implicit_step(U, V, xf, dx, np.full(n + 1, kap), dt, None,
                                   h_bc, u_inf, 1.0 / core.R0 ** 2, core.R0)
        return U

    # 温度：α = 0.36/(820·2600)、h=1e6（第一类极限）、T∞=50 °C、t=600 s、n=200、dt=0.5 s
    alpha = 0.36 / (820.0 * 2600.0)
    U = march(200, 0.5, 600.0, alpha, 1e6, 323.15, T0)
    Fo = alpha * 600.0 / core.R0 ** 2
    Tser = 323.15 - (323.15 - T0) * series(Fo, np.linspace(0, 1, 201))
    dT = float(np.max(np.abs(U - Tser)))
    # 水分：D=C0 处的附录 2 值、表面值固定 0.10、t=1800 s、n=200、dt=0.5 s
    Df = float(core.props("q1", np.array([C0]), np.array([T0]))[3][0])
    C = march(200, 0.5, 1800.0, Df, 1e6, 0.10, C0)
    FoC = Df * 1800.0 / core.R0 ** 2
    Cser = 0.10 + (C0 - 0.10) * series(FoC, np.linspace(0, 1, 201))
    dC = float(np.max(np.abs(C - Cser)))
    return dict(
        calibration="常数物性 + 第一类边界极限（h=1e6）+ 常数环境；级数 θ=Σ 2/(μ_n J1(μ_n)) J0(μ_n ρ) e^{-μ_n²Fo}"
                    "，μ_n = jn_zeros(0,n)；**该差值含模型差异，不得当离散精度的界引用**（§11.2 口径注）",
        series_root="scipy.special.jn_zeros(0,n)（不得自写二分：n≥2 会重复返回首个零点）",
        temperature=dict(t=600.0, n=200, dt=0.5, Fo=float(Fo), max_abs_dT=dT,
                         field_span_K=float(U.max() - U.min()),
                         report_value=7.5e-3,
                         text="温度 max|ΔT|=%.3e K（报告 §11.2 探针 7.5e-3 K；场跨 %.2f K）"
                              % (dT, U.max() - U.min())),
        moisture=dict(t=1800.0, n=200, dt=0.5, Fo=float(FoC), D_frozen=float(Df),
                      max_abs_dC=dC, report_value=1.13e-4,
                      text="水分 max|ΔC|=%.3e（报告探针 1.13e-4）" % dC))


if __name__ == "__main__":
    core.ROOT = Path(__file__).resolve().parents[1]
    t0 = time.perf_counter()
    conv = convergence()
    sens = sensitivity()
    cons = consistency()
    el = time.perf_counter() - t0
    core.log("── 全部诊断用时 %.1f s" % el)
    # 图件数据源（只依赖本模块的诊断结果）
    core.write_json(core.out_dir() / "figdata_sens.npz.meta.json", dict(
        _method="口径敏感性 / 收敛性的图件数据（各档 t_dry 与场级收敛差）",
        _code_fp=core.CODE_FP, _produced_at=core._produced_at(), _stage="code",
        _params=dict(source="results/sensitivity.json + results/convergence.json")))
    mesh = [("n=80", conv["mesh_tdry"]["80"]["t_dry_step_h"]),
            ("n=160", conv["mesh_tdry"]["160"]["t_dry_step_h"]),
            ("n=320", conv["mesh_tdry"]["320"]["t_dry_step_h"]),
            ("n=640", conv["mesh_tdry"]["640"]["t_dry_step_h"])]
    step = [(("%g s" % dt), conv["step_tdry"]["%g" % dt]["t_dry_step_h"]) for dt in (60, 30, 10, 1)]
    cal = [(k, v["t_dry_step_h"]) for k, v in sens["calibers"].items()
           if v["t_dry_step_h"] is not None]
    np.savez_compressed(core.out_dir() / "figdata_sens.npz",
                        mesh_n=np.array([80, 160, 320, 640], float),
                        mesh_tdr=np.array([m[1] for m in mesh], float),
                        step_dt=np.array([60, 30, 10, 1], float),
                        step_tdr=np.array([s[1] for s in step], float),
                        cal_labels=np.array([c[0] for c in cal], dtype=object),
                        cal_tdr=np.array([c[1] for c in cal], float),
                        field_mesh_keys=np.array(list(conv["field_mesh"].keys()), dtype=object),
                        field_mesh_dT=np.array([v["max_dT_5cols"] for v in conv["field_mesh"].values()]),
                        field_mesh_dC=np.array([v["max_dC_21cols"] for v in conv["field_mesh"].values()]),
                        field_step_keys=np.array(list(conv["field_step"].keys()), dtype=object),
                        field_step_dT=np.array([v["max_dT_5cols"] for v in conv["field_step"].values()]),
                        field_step_dC=np.array([v["max_dC_21cols"] for v in conv["field_step"].values()]),
                        allow_pickle=True)
    core.scale_estimate("sensitivity", 1.0, el, el)
