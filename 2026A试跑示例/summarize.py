# -*- coding: utf-8 -*-
"""汇总各问结果并登记结构化指标（`results/metric-spec.json` → `lib.result_contract build`）。

为什么要有这一层（`docs/RESULT_CONTRACT.md`）：写作阶段用 `\\ResultValue{id}` 引用核心数值，
来源必须是**机器可读的登记项**，而不是从报告里手抄。这里把 `results/q*.json` 里的标量
按稳定 ID 登记，`build` 会记录输入/脚本/来源的哈希与统一四位小数的显示值。

运行：`python code/summarize.py`
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import core                                                       # noqa: E402

RUN_ID = "code-" + core.CODE_FP          # 批次标识：本阶段指纹（同一次交付内稳定）

# (id, label, unit, scenario, source, pointer, precision)
METRICS = [
    ("q1.t_center_1800s", "问题1 t=1800 s 中心温度", "°C", "Q1 附录2 交付档",
     "results/q1.json", "/table1_T_C/6/0", 4),
    ("q1.t_surface_1800s", "问题1 t=1800 s 表面温度", "°C", "Q1 附录2 交付档",
     "results/q1.json", "/table1_T_C/6/4", 4),
    ("q1.c_center_1800s", "问题1 t=1800 s 中心干基含水率", "kg/kg", "Q1 附录2 交付档",
     "results/q1.json", "/table2_C/6/0", 4),
    ("q1.c_surface_1800s", "问题1 t=1800 s 表面干基含水率", "kg/kg", "Q1 附录2 交付档",
     "results/q1.json", "/table2_C/6/4", 4),
    ("q1.moisture_loss_flux_pct", "问题1 1800 s 失水比例（表面通量累计口径）", "%",
     "Q1 附录2 交付档", "results/q1.json", "/moisture_loss/calibers/0/drop_pct", 2),
    ("q1.moisture_loss_mean_pct", "问题1 1800 s 失水比例（全场体积加权均值口径）", "%",
     "Q1 附录2 交付档", "results/q1.json", "/moisture_loss/calibers/1/drop_pct", 2),
    ("q1.moisture_loss_5pt_pct", "问题1 1800 s 失水比例（五点梯形口径）", "%",
     "Q1 附录2 交付档", "results/q1.json", "/moisture_loss/calibers/2/drop_pct", 2),
    ("q1.conservation_water_rel", "问题1 水分离散伸缩和最大相对残差", "1", "Q1 守恒校核",
     "results/q1.json", "/conservation/离散伸缩和/max_rel_residual", 12),
    ("q2.c_center_72h", "问题2 72 h 中心干基含水率", "kg/kg", "Q2 附录3 交付档",
     "results/q2.json", "/anchors/C_center_72h", 4),
    ("q2.c_surface_72h", "问题2 72 h 表面干基含水率", "kg/kg", "Q2 附录3 交付档",
     "results/q2.json", "/anchors/C_surface_72h", 4),
    ("q2.t_surface_72h", "问题2 72 h 表面温度", "°C", "Q2 附录3 交付档",
     "results/q2.json", "/anchors/T_surface_72h_C", 4),
    ("q3.t_dry_h", "问题3 烘干时长（连续根，Δt=1 s 交付档）", "h", "Q3 附录3 固定几何",
     "results/q3.json", "/t_dry_h", 4),
    ("q3.last_row_h", "问题3 交付件末行时刻", "h", "Q3 交付口径",
     "results/q3.json", "/last_row_h", 4),
    # ★ 这两个是**两个不同口径**、必须分列引用（审计 `aud-q3-root-label`）：前者是插值构造（恒等于阈值），
    #   后者才是"首达计算步实测"的独立证据。引用时一律带上各自的口径（JSON 里的 `_口径` 字段）。
    ("q3.max_rc_at_root", "问题3 t_dry 的线性插值场在该时刻的 max_rC（构造上 = 阈值，非独立证据）",
     "kg/kg", "Q3 判据自证（插值构造口径）", "results/q3.json", "/proof/max_rC_at_root", 6),
    ("q3.max_rc_at_first_hit_step", "问题3 首个满足判据的计算步（t=205698 s）的 max_rC（未舍入，独立证据）",
     "kg/kg", "Q3 判据自证（首达步口径）", "results/q3.json", "/proof/max_rC_at_first_hit_step", 12),
    ("q4.t_dry_h", "问题4 烘干时长（连续根，Δt=60 s 交付档）", "h", "Q4 附录4 收缩动边界",
     "results/q4.json", "/t_dry_h", 4),
    ("q4.t_dry_step_h", "问题4 步进首达时刻（3050 步）", "h", "Q4 附录4 收缩动边界",
     "results/q4.json", "/step60/t_dry_step_first_hit_h", 4),
    ("q4.v1_max_abs_dc", "V1 恒等校验 收缩/固定域 表面含水率最大逐位差", "kg/kg",
     "Q4 恒等校验", "results/q4.json", "/v1/max_abs_dC", 12),
    ("q4.last_row_h", "问题4 交付件末行时刻", "h", "Q4 交付口径",
     "results/q4.json", "/last_row_h", 4),
    ("sens.tdry_q3_n320_dt60", "口径基准 t_dry（附录3 固定几何，n=320，Δt=60 s）", "h",
     "口径敏感性", "results/sensitivity.json", "/calibers/main_n320_dt60/t_dry_step_h", 4),
    ("sens.tdry_shrink_appendix3", "只开几何收缩（附录3 物性）的 t_dry", "h",
     "口径敏感性", "results/sensitivity.json", "/calibers/decomp_shrink_appendix3/t_dry_step_h", 4),
    ("sens.tdry_face_harm", "面导度取调和平均的 t_dry", "h",
     "口径敏感性", "results/sensitivity.json", "/calibers/face_harm_n320_dt60/t_dry_step_h", 4),
    ("sens.tdry_env_peak", "环境延拓取峰值的 t_dry", "h",
     "口径敏感性", "results/sensitivity.json", "/calibers/env_peak_n160_dt60/t_dry_step_h", 4),
    ("sens.tdry_latent_n80", "含汽化潜热对照档的 t_dry", "h",
     "口径敏感性", "results/sensitivity.json", "/calibers/phase_latent_n80_dt60/t_dry_step_h", 4),
    ("sens.tdry_enthalpy_k_n80", "焓守恒改写档（源项温标 K）的 t_dry", "h",
     "口径敏感性", "results/sensitivity.json", "/calibers/phase_enthalpy_rewrite_K_n80_dt60/t_dry_step_h", 4),
    ("conv.tdry_n640_dt60", "网格 n=640 的 t_dry（Δt=60 s 步进首达）", "h", "收敛性",
     "results/convergence.json", "/mesh_tdry/640/t_dry_step_h", 4),
    ("conv.field_step_dt_1_to_0p5", "表 1 五列在 Δt=1→0.5 s 的最大差", "K", "收敛性",
     "results/convergence.json", "/field_step/1->0.5/max_dT_5cols", 12),
    ("conv.field_step_dc_1_to_0p5", "表 2 二十一列在 Δt=1→0.5 s 的最大差（t=1800 s 取材）", "kg/kg",
     "收敛性", "results/convergence.json", "/field_step/1->0.5/max_dC_21cols", 12),
    # ★ 早期时刻的同一档序列 —— 交付表还含 t=100–1500 s 的行，那一档不能按上面这条的精度去读
    #   （审计 `aud-precision-scope-earlytime`；本轮实测 $t=100$ s 是 $t=1800$ s 的 **4.13 倍**）。
    ("conv.field_step_early_dc_1_to_0p5",
     "表 2 二十一列在 Δt=1→0.5 s 的最大差（t=100 s 取材，早期时刻）", "kg/kg",
     "收敛性", "results/convergence.json", "/field_step_early/1->0.5/max_dC_21cols", 12),
    ("cons.steady_limit_hold_t_max", "稳态极限（主档 hold：T∞=50.165 °C）末刻最高温度", "°C",
     "守恒校核", "results/consistency.json", "/steady_limit/T_max_C", 12),
    ("cons.steady_limit_const50_t_max", "稳态极限（常数支 T∞≡50 °C）末刻最高温度", "°C",
     "守恒校核", "results/consistency.json", "/steady_limit_const50/T_max_C", 12),
    ("cons.water_max_rel_q1", "问题1 水分离散伸缩和最大相对残差", "1", "守恒校核",
     "results/consistency.json", "/conservation_q1/water_max_rel", 12),
    ("cons.energy_max_rel_q1", "问题1 能量离散伸缩和最大相对残差", "1", "守恒校核",
     "results/consistency.json", "/conservation_q1/energy_max_rel", 12),
    ("cons.analytic_dt", "解析级数校核 温度最大偏差", "K", "解析校核",
     "results/consistency.json", "/analytic/temperature/max_abs_dT", 12),
    ("cons.analytic_dc", "解析级数校核 水分最大偏差", "kg/kg", "解析校核",
     "results/consistency.json", "/analytic/moisture/max_abs_dC", 12),
]

INPUTS = [
    "request/problem.md",
    "request/attachments/附件1.xlsx",
    "request/attachments/附件2.xlsx",
    "request/attachments/附件3/result1.xlsx",
    "request/attachments/附件3/result2.xlsx",
    "request/attachments/附件3/result3.xlsx",
    "request/attachments/附件3/result4.xlsx",
    "reports/ANALYSIS_MODELING_REPORT.md",
    "reports/TASK_CONTRACT.json",
    "results/q1.json", "results/q2.json", "results/q3.json", "results/q4.json",
    "results/convergence.json", "results/sensitivity.json", "results/consistency.json",
    "results/result1.xlsx", "results/result2.xlsx", "results/result3.xlsx",
    "results/result4.xlsx",
    "code/outputs/q1.npz", "code/outputs/q2.npz", "code/outputs/q4.npz",
    "code/outputs/figdata_q1.npz", "code/outputs/figdata_q2.npz",
    "code/outputs/figdata_q4.npz", "code/outputs/figdata_sens.npz",
]

SCRIPTS = [
    "code/run_all.py", "code/core.py", "code/q1.py", "code/q2.py", "code/q3.py",
    "code/q4.py", "code/sensitivity.py", "code/summarize.py", "code/validate_results.py",
    "figures/make_figures.py",
]

SCHEMA_VERSION = 1


def build_spec():
    metrics = []
    for mid, label, unit, scenario, source, pointer, precision in METRICS:
        metrics.append(dict(id=mid, label=label, unit=unit, scenario=scenario,
                            source=source, pointer=pointer, precision=precision))
    r = core.results_dir()
    core.write_json(r / "metric-spec.json", dict(
        schema_version=SCHEMA_VERSION, problem_id="2026A", run_id=RUN_ID,
        inputs=INPUTS, scripts=SCRIPTS, metrics=metrics))
    core.log("→ results/metric-spec.json（%d 项指标）" % len(metrics))
    return len(metrics)


def build_validation_spec():
    """`kind=custom`：独立校验脚本从**交付件本身**重算约束/残差，不调用求解器。"""
    core.write_json(core.results_dir() / "validation-spec.json", dict(
        schema_version=SCHEMA_VERSION, kind="custom",
        script="code/validate_results.py", timeout_seconds=300,
        inputs=INPUTS,
        checks_required=[
            "xlsx_sheet_headers_from_template",
            "xlsx_row_and_column_sets",
            "xlsx_values_are_4dp_half_up",
            "xlsx_time_column_integer",
            "initial_condition_per_zone",
            "monotone_in_radius",
            "row_wise_max_matches_reported_series",
            "water_balance_from_delivered_table",
            "energy_balance_from_delivered_table",
            "q3_last_row_threshold",
            "q4_surface_column_and_blanks",
            "q3_is_q2_on_its_own_grid",
            "column_temporal_smoothness",
            "result_jsons_agree_with_metric_spec",
        ]))
    core.log("→ results/validation-spec.json（14 项必查）")


def header():
    lines = []

    def add(s=""):
        lines.append(s)

    q1 = json.loads((core.results_dir() / "q1.json").read_text(encoding="utf-8"))
    q2 = json.loads((core.results_dir() / "q2.json").read_text(encoding="utf-8"))
    q3 = json.loads((core.results_dir() / "q3.json").read_text(encoding="utf-8"))
    q4 = json.loads((core.results_dir() / "q4.json").read_text(encoding="utf-8"))
    sens = json.loads((core.results_dir() / "sensitivity.json").read_text(encoding="utf-8"))
    conv = json.loads((core.results_dir() / "convergence.json").read_text(encoding="utf-8"))
    cons = json.loads((core.results_dir() / "consistency.json").read_text(encoding="utf-8"))
    add("=== 交付数值摘要（唯一来源：results/*.json） ===")
    add("Q1  t=1800 s  T(0,0.5,1,1.5,2 cm) = " + ", ".join("%.4f" % v for v in q1["table1_T_C"][-1]) + " °C")
    add("Q1  t=1800 s  C                      = " + ", ".join("%.4f" % v for v in q1["table2_C"][-1]) + " kg/kg")
    add("Q1  失水比例三口径 = %.2f%% / %.2f%% / %.2f%%"
        % tuple(c["drop_pct"] for c in q1["moisture_loss"]["calibers"]))
    add("Q2  72 h 中心/表面 C = %.5f / %.5f kg/kg" % (q2["anchors"]["C_center_72h"],
                                                   q2["anchors"]["C_surface_72h"]))
    add("Q3  t_dry = %.4f h（连续根，Δt=1 s 交付档）；交付件末行 %.0f s"
        % (q3["t_dry_h"], q3["last_row_s"]))
    add("Q3  max_rC 两口径：根处（插值构造，t=%.4f s）= %.9f；首达步（t=%.0f s，独立证据）= %.9f"
        % (q3["t_dry_s"], q3["proof"]["max_rC_at_root"],
           q3["proof"]["t_first_hit_step"], q3["proof"]["max_rC_at_first_hit_step"]))
    add("Q4  t_dry = %.4f h（连续根，Δt=60 s 交付档）；步进首达 %.4f h（%d 步）"
        % (q4["t_dry_h"], q4["step60"]["t_dry_step_first_hit_h"], q4["step60"]["n_steps"]))
    add("Q4  V1 恒等 max|ΔC|=%.1e、max|ΔT|=%.1e（逐位一致 %s）"
        % (q4["v1"]["max_abs_dC"], q4["v1"]["max_abs_dT"], q4["v1"]["bitwise"]))
    add("收敛 网格 n=80/160/320/640 → %s h"
        % "/".join("%.4f" % conv["mesh_tdry"][k]["t_dry_step_h"] for k in ("80", "160", "320", "640")))
    add("守恒 Q1 水分相对残差 %.2e、能量相对残差 %.2e"
        % (cons["conservation_q1"]["water_max_rel"], cons["conservation_q1"]["energy_max_rel"]))
    add("解析 温度 max|ΔT|=%.3e K；水分 max|ΔC|=%.3e"
        % (cons["analytic"]["temperature"]["max_abs_dT"], cons["analytic"]["moisture"]["max_abs_dC"]))
    add("场级步长收敛（Δt=1→0.5 s）t=1800 s：5 列 %.3e K / 21 列 %.3e；t=100 s：5 列 %.3e K / 21 列 %.3e"
        % (conv["field_step"]["1->0.5"]["max_dT_5cols"], conv["field_step"]["1->0.5"]["max_dC_21cols"],
           conv["field_step_early"]["1->0.5"]["max_dT_5cols"],
           conv["field_step_early"]["1->0.5"]["max_dC_21cols"]))
    add("稳态极限：主档 hold（T∞=%.3f °C）→ T_max=%.12f °C；常数支（T∞≡50 °C）→ T_max=%.12f °C"
        % (cons["steady_limit"]["T_inf_C"], cons["steady_limit"]["T_max_C"],
           cons["steady_limit_const50"]["T_max_C"]))
    add("口径 面导度 算术/几何/调和 = %s h；环境 保持/峰值/饱和 = %s h"
        % ("/".join("%.4f" % sens["calibers"][k]["t_dry_step_h"]
                    for k in ("main_n320_dt60", "face_geom_n320_dt60", "face_harm_n320_dt60")),
           "/".join("%.4f" % sens["calibers"][k]["t_dry_step_h"]
                    for k in ("main_n320_dt60", "env_peak_n160_dt60", "env_plateau_n160_dt60"))))
    text = "\n".join(lines)
    (core.results_dir() / "summary.txt").write_text(text + "\n", encoding="utf-8")
    core.log(text)
    return text


if __name__ == "__main__":
    core.ROOT = Path(__file__).resolve().parents[1]
    build_spec()
    build_validation_spec()
    header()
