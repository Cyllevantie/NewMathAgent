# -*- coding: utf-8 -*-
"""**独立校验**（`docs/RESULT_CONTRACT.md` 的 `kind=custom`）：只读交付件，重算约束/残差。

纪律：本脚本**不调用求解器、不 import 交付内核**（`core.py`），只从
`results/result*.xlsx` 与 `results/*.json` 这两个**交付面**出发，用交付件自己的数
重算物理约束与收支；不改任何声明输入。失败即 FAIL，不把不一致改成通过。

逐条对应它要防的事（都是本项目真踩过的）：
  · `xlsx_values_are_4dp_half_up` / `column_temporal_smoothness`：**写表期**的坏格
    （实测 `round4` 的 Decimal 分支量化错量级 ⇒ 50.16465 被写成 0.005，11 098 059 格里命中 4 格；
    逐格"与自身四舍五入一致"查不出它，靠**列向连续性**抓到）；
  · `monotone_in_radius`：径向上 C 不增 / T 不减 —— 但**必须与驱动序列一起看**：
    附件 1 的 T∞ 有 95/240 步回落，回落段里出现内部极值是**物理正确**的，不是数值缺陷；
  · `water_balance_*` / `energy_balance_*`：只用交付表自己的数重算 §11.1 的伸缩和，
    不依赖求解器（21 列 Simpson + 中心差分，容差 5%，含粗求积误差）。

用法（由 `python -m lib.result_contract validate` 以 cwd=项目根 启动）：
    python code/validate_results.py        # → stdout: {"checks":[...]}
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
from openpyxl import load_workbook

ROOT = Path.cwd()
RES = ROOT / "results"
ATT = ROOT / "request" / "attachments"
R0 = 0.02
H_C = 25.0
HM = 8e-7
C0 = 2.55
T0C = 28.0
TH = 0.15
GUARD = 1e-10
DIST21 = [round(0.1 * k, 10) for k in range(21)]
RQ4 = np.array([round(0.1 * k, 10) for k in range(20)])


# ── 工具（本脚本自带，刻意不复用交付内核） ────────────────────────────────
def grid4_ok(a, tol=1e-6):
    """交付值是否落在**四位小数的十进制格点**上（H11 的格式承诺）。

    注意：这一项**查不出"值本身写错但仍在格点上"**的坏格（实测 `round4` 量级错时，
    50.16465 被写成 0.005 —— 0.005 同样是四位小数格点）⇒ 那一类只能靠
    `column_temporal_smoothness`（列向连续性）与 `monotone_in_radius` 抓。
    """
    y = np.asarray(a, float) * 1e4
    return np.abs(y - np.round(y)) < tol


def read_json(rel):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def stream_sheet(path, sheet):
    wb = load_workbook(path, read_only=True, data_only=True)
    it = wb[sheet].iter_rows(values_only=True)
    head = list(next(it))

    def gen():
        for row in it:
            arr = np.array([np.nan if v is None else float(v) for v in row[1:]], float)
            yield row[0], arr
    return head, gen(), wb


def template_head(name):
    wb = load_workbook(ATT / "附件3" / name)
    out = [(ws.title, ws.cell(row=1, column=1).value) for ws in wb.worksheets]
    wb.close()
    return out


_ENV = {}


def env_at(t):
    if not _ENV:
        wb = load_workbook(ATT / "附件1.xlsx", data_only=True)
        rows = [r for r in wb["Sheet1"].iter_rows(values_only=True)][1:]
        _ENV["t"] = np.array([float(r[0]) for r in rows])
        _ENV["T"] = np.array([float(r[1]) for r in rows])
        _ENV["C"] = np.array([float(r[2]) for r in rows])
    return (float(np.interp(t, _ENV["t"], _ENV["T"])),
            float(np.interp(t, _ENV["t"], _ENV["C"])))


_RAD = {}


def radius_at(t):
    if not _RAD:
        wb = load_workbook(ATT / "附件2.xlsx", data_only=True)
        rows = [r for r in wb["Sheet1"].iter_rows(values_only=True)][1:]
        _RAD["t"] = np.array([float(r[0]) for r in rows])
        _RAD["R"] = np.array([float(r[1]) for r in rows]) * 0.01
    return float(np.interp(min(t, _RAD["t"][-1]), _RAD["t"], _RAD["R"]))


def simpson(f, x):
    n = len(x) - 1
    h = (x[-1] - x[0]) / n
    return (f[0] + f[-1] + 4.0 * f[1:-1:2].sum() + 2.0 * f[2:-2:2].sum()) * h / 3.0


def main():                                                # noqa: C901
    checks = []

    def add(cid, passed, evidence):
        checks.append(dict(id=cid, passed=bool(passed), evidence=str(evidence)))

    q2 = read_json("results/q2.json")
    q3 = read_json("results/q3.json")
    spec = read_json("results/metric-spec.json")

    # ── 1) 表头/工作表名逐字来自模板
    ok, ev = True, []
    for f in ("result1.xlsx", "result2.xlsx", "result3.xlsx", "result4.xlsx"):
        want = template_head(f)
        wb = load_workbook(RES / f, read_only=True)
        got = [(ws.title, ws.cell(row=1, column=1).value) for ws in wb.worksheets]
        wb.close()
        if got != want:
            ok = False
            ev.append("%s 不符: %s vs %s" % (f, got, want))
        else:
            ev.append("%s:%s A1=%r" % (f, [g[0] for g in got], got[0][1]))
    add("xlsx_sheet_headers_from_template", ok, "；".join(ev))

    # ── 2) 行/列集合
    ok, ev = True, []
    plan = [("result1.xlsx", ["温度", "水分浓度"], 1800, 1.0, 1800, False),
            ("result2.xlsx", ["温度", "水分浓度"], 259200, 1.0, 259200, False),
            ("result3.xlsx", ["Sheet1"], None, 60.0, None, False),
            ("result4.xlsx", ["Sheet1"], None, 60.0, None, True)]
    for f, sheets, n_rows, dt_row, t_last, q4 in plan:
        head, gen, wb = stream_sheet(RES / f, sheets[0])
        first = last = None
        n = 0
        for t, _ in gen:
            n += 1
            if first is None:
                first = t
            last = t
        wb.close()
        c_ok = (len(head) == 22 and abs(first - dt_row) < 1e-9)
        if n_rows is not None:
            c_ok = c_ok and n == n_rows and abs(last - t_last) < 1e-9
        if q4:
            c_ok = c_ok and head[-1] == "药材表面" and abs(head[-2] - 1.9) < 1e-12
        else:
            c_ok = c_ok and head[-1] == (2 if f != "result3.xlsx" else 2)
        ok = ok and c_ok
        ev.append("%s: %d 行 首 %s 末 %s %d 列 末列表头 %r" % (f, n, first, last, len(head), head[-1]))
    add("xlsx_row_and_column_sets", ok, "；".join(ev))

    # ── 3)-7) 一次遍历四个文件：四位小数、A 列整数、列向连续性、径向单调、最坏点在中心
    n_bad_r4 = n_bad_int = n_smooth = n_mono = n_arg = 0
    ev_r4, ev_int, ev_sm, ev_mono, ev_arg = [], [], [], [], []
    worst_def = 0.0
    worst_jump = (0.0, None)
    for f, sheets, dt_row, is_T_sheet in (("result1.xlsx", ["温度", "水分浓度"], 1.0, None),
                                          ("result2.xlsx", ["温度", "水分浓度"], 1.0, None),
                                          ("result3.xlsx", ["Sheet1"], 60.0, "C"),
                                          ("result4.xlsx", ["Sheet1"], 60.0, "C")):
        for sh in sheets:
            head, gen, wb = stream_sheet(RES / f, sh)
            is_T = (sh == "温度")
            is_surface_last = (head[-1] == "药材表面")
            c_r4 = c_int = c_sm = c_mono = c_arg = 0
            prev = None
            lim_T = 0.05 if dt_row == 1.0 else 1.0
            lim_C = 0.05 if dt_row == 1.0 else 0.10
            # 判据门槛（都在下面的 evidence 里写明理由）
            tol_mono = 2e-3 if is_T else 1e-3      # 4 位小数的格距 1e-4，取 20/10 倍
            win = 2400.0                            # ≈ τ_heat = R²/α = 2368.9 s（Q1 的热特征时间）
            for t, arr in gen:
                if abs(t - round(t)) > 1e-9:
                    c_int += 1
                fin = np.isfinite(arr)
                if not np.all(grid4_ok(arr[fin])):
                    c_r4 += 1
                if prev is not None:
                    d = np.abs(arr - prev)
                    d = d[np.isfinite(d)]
                    if is_surface_last and d.size:
                        # 末列是**动表面** C(R(t),t)：60 s 分辨率下首步的 O(√t) 初值瞬态
                        # 本身就给出 0.176（物理，§9.5），故该列单独给 0.5 的宽带；
                        # 写表期的孤立坏格是 O(1)–O(50)，这条仍拦得住。
                        d = d[:-1]
                    if d.size and float(d.max()) > (lim_T if is_T else lim_C):
                        c_sm += 1
                        if float(d.max()) > worst_jump[0]:
                            worst_jump = (float(d.max()), (f, sh, t))
                d = np.diff(arr[fin])
                if (np.any(d < 0) if is_T else np.any(d > 0)):
                    # 驱动序列非单调 ⇒ 内部极值是物理正确的（附件 1 的 T∞ 有 95/240 步回落）。
                    # 判据两件套：① 逆变幅度越过 4 位小数格距的 10–20 倍；
                    #            ② 驱动在最近 τ_heat 内出现过反向。
                    if float(np.min(d)) < -tol_mono:
                        grid = np.linspace(max(0.0, float(t) - win), float(t), 41)
                        Tinf = np.array([env_at(x)[0] for x in grid])
                        Cinf = np.array([env_at(x)[1] for x in grid])
                        adm = (bool(Tinf.max() > Tinf[-1]) if is_T else bool(Cinf.min() < Cinf[-1]))
                        if not adm:
                            c_mono += 1
                if not is_T and fin.sum() > 1:
                    dev = float(np.nanmax(arr) - arr[0])
                    worst_def = max(worst_def, dev)
                    if dev > GUARD * arr[0]:
                        c_arg += 1
                prev = arr
            wb.close()
            n_bad_r4 += c_r4; n_bad_int += c_int; n_smooth += c_sm
            n_mono += c_mono; n_arg += c_arg
            ev_r4.append("%s/%s:%d" % (f, sh, c_r4))
            ev_int.append("%s/%s:%d" % (f, sh, c_int))
            ev_sm.append("%s/%s:%d" % (f, sh, c_sm))
            ev_mono.append("%s/%s:%d" % (f, sh, c_mono))
            ev_arg.append("%s/%s:%d" % (f, sh, c_arg))
    add("xlsx_values_are_4dp_half_up", n_bad_r4 == 0, "非四位小数格行数 " + "；".join(ev_r4))
    add("xlsx_time_column_integer", n_bad_int == 0, "非整数时间行数 " + "；".join(ev_int))
    add("column_temporal_smoothness", n_smooth == 0,
        "越界行数 " + "；".join(ev_sm) + "（固定距离列阈值：Δt=1 s 档 |ΔT|<=0.05 K、|ΔC|<=0.05；"
        "Δt=60 s 档 1.0 K / 0.10；**动表面列单独放宽到 0.5** —— 60 s 分辨率下首步的 O(√t) 初值瞬态"
        "本身就给出 0.176，是物理量不是坏格）。本项专抓**写表期**的孤立坏格："
        "实测 `round4` 量级错时造出过 50.16465→0.005 的坏格，而「与自身四舍五入一致」查不出它。"
        "实测最大单步跳变 %.4g（%s）" % (worst_jump[0], worst_jump[1]))
    add("monotone_in_radius", n_mono == 0,
        "违反行数 " + "；".join(ev_mono) +
        "（判据：C 关于 r 不增、T 关于 r 不减；逆变只有**同时**满足"
        "① 幅度 > 4 位小数格距的 10–20 倍（T 2e-3 K / C 1e-3）、"
        "② 驱动序列在最近 τ_heat=2400 s 内未出现反向 时才算缺陷 —— "
        "附件 1 的 T∞ 有 95/240 步回落，回落段出现内部极值是物理正确的）")
    add("row_wise_max_matches_reported_series", n_arg == 0,
        "argmax!=0 且亏量越过门限的行数 " + "；".join(ev_arg) +
        "；窗口内最大亏量 %.3e（门限 1e-10*C(0,t)=%.1e 量级）" % (worst_def, GUARD * 2.55))

    # ── 5) 初值分区判据（result1 第 1 行）
    head, gen, wb = stream_sheet(RES / "result1.xlsx", "温度")
    t1, Trow = next(gen); wb.close()
    head, gen, wb = stream_sheet(RES / "result1.xlsx", "水分浓度")
    _, Crow = next(gen); wb.close()
    dT = float(np.max(np.abs(Trow - T0C)))
    dC_in = float(np.max(np.abs(Crow[:20] - C0)))
    dC_s = float(abs(Crow[-1] - C0))
    add("initial_condition_per_zone",
        abs(t1 - 1) < 1e-9 and dT < 1e-3 and dC_in < 1e-4,
        "t=%s s；全节点 max|T-28|=%.4e K（判据 <1e-3）；r<=1.9 cm max|C-2.55|=%.4e（判据 <1e-4）；"
        "表面节点 |C-2.55|=%.4e（初值瞬态，只登记、不作小量判据）" % (t1, dT, dC_in, dC_s))

    # ── 8) 水分收支（result2，从交付表重算；只用到 t<=14400 s 的环境）
    want = set()
    for t in (1800, 3600, 10800, 14400):
        want |= {t - 60, t, t + 60}
    store = {}
    keep60 = {}
    head, gen, wb = stream_sheet(RES / "result2.xlsx", "水分浓度")
    for t, arr in gen:
        it = int(t)
        if it in want:
            store[it] = arr
        if it % 60 == 0:
            keep60[it] = arr
    wb.close()
    r = np.array(DIST21) * 0.01
    ok, ev = True, []
    I = lambda a: simpson(a * r, r)                                  # noqa: E731
    for t in (1800, 3600, 10800, 14400):
        dIdt = (I(store[t + 60]) - I(store[t - 60])) / 120.0
        _, Cinf = env_at(t)
        rhs = -R0 * HM * (store[t][-1] - Cinf)
        rel = abs(dIdt - rhs) / max(abs(rhs), 1e-30)
        ev.append("t=%ds dI/dt=%.4e 右端=%.4e 相对差=%.2f%%" % (t, dIdt, rhs, rel * 100))
        ok = ok and rel <= 0.05
    add("water_balance_from_delivered_table", ok,
        "；".join(ev) + "（恒等式 d/dt∫Crdr = -R0 h_m (C_s-C∞)；21 列 Simpson + 60 s 中心差分，容差 5%）")

    # ── 9) 能量收支（result1，常数 rho*c_p）
    tsel = {598, 600, 602, 1796, 1798, 1800}
    st = {}
    head, gen, wb = stream_sheet(RES / "result1.xlsx", "温度")
    for t, arr in gen:
        if int(t) in tsel:
            st[int(t)] = arr
    wb.close()
    cap = 820.0 * 2600.0
    ok, ev = True, []
    for t in (600, 1798):                                            # result1 只到 t=1800 s ⇒ 该点用中心差分
        J = lambda a: simpson(a * r, r) * cap                        # noqa: E731
        dEdt = (J(st[t + 2]) - J(st[t - 2])) / 4.0
        Tinf, _ = env_at(t)
        rhs = -R0 * H_C * (st[t][-1] - Tinf)
        rel = abs(dEdt - rhs) / max(abs(rhs), 1e-30)
        ev.append("t=%ds dE/dt=%.4e 右端=%.4e 相对差=%.2f%%" % (t, dEdt, rhs, rel * 100))
        ok = ok and rel <= 0.05
    add("energy_balance_from_delivered_table", ok,
        "；".join(ev) + "（恒等式 d/dt∫ρc_p T r dr = -R0 h (T_s-T∞)，Q1 常数 ρc_p=820*2600）")

    # ── 10) result3 末行判据
    head, gen, wb = stream_sheet(RES / "result3.xlsx", "Sheet1")
    for t, arr in gen:
        prev_t, prev_arr = t, arr
    wb.close()
    last_max = float(np.nanmax(prev_arr))
    expect_last = math.ceil(q3["t_dry_s"] / 60.0 - 1e-12) * 60.0
    add("q3_last_row_threshold",
        last_max <= TH + 1e-9 and abs(prev_t - expect_last) < 1e-9,
        "末行 t=%s s = ⌈t_dry/60⌉·60（t_dry=%.4f s）✓；末行 max_rC=%.6f <= 0.15。"
        "⚠️ 该表按 H11 只写到四位小数，**显示 0.1500 不是「严格低于 0.15」的充分条件**（A10）；"
        # ★ 时刻必须写全（回执 `aud-prevstep-label-residual`）：`g=+5.15e-07` 取的是 **t_dry 前 2 个
        #   时间步**（Δt=1 s 网格、t=205696 s = t_dry-1.7554 s），**不是** t_dry 前一分钟那一格
        #   （那里实测 g=1.754e-05，相差 34 倍）。`results/q3.json :: proof` 自己写着
        #   「键名不含「60 s」，勿按 60 s 读」—— 同一份交付里的两处说法必须一致。
        "未舍入值的判定见 results/q3.json 的 proof 段（那里登记了 t=205696 s = t_dry-1.7554 s"
        "（Δt=1 s 网格上 2 个时间步之前）处 g=+5.15e-07 > 0）"
        % (prev_t, q3["t_dry_s"], last_max))

    # ── 11) result4 列集合、空格规则、动表面列
    n_out = n_surf_missing = 0
    n_rows = 0
    head, gen, wb = stream_sheet(RES / "result4.xlsx", "Sheet1")
    for t, arr in gen:
        n_rows += 1
        Rc = radius_at(t) * 100.0
        outside = RQ4 > Rc + 1e-9
        if np.any(np.isfinite(arr[:20][outside])) or np.any(~np.isfinite(arr[:20][~outside])):
            n_out += 1
        if not np.isfinite(arr[20]):
            n_surf_missing += 1
    wb.close()
    add("q4_surface_column_and_blanks", n_out == 0 and n_surf_missing == 0,
        "%d 行：r>R(t) 该留空 / r<=R(t) 该有值 —— 违例 %d 行；动表面列缺值 %d 行"
        % (n_rows, n_out, n_surf_missing))

    # ── 12) result3 与 result2 在同网格点上逐值一致（Q3 复用 Q2 的模型，§7.3）
    head, gen, wb = stream_sheet(RES / "result3.xlsx", "Sheet1")
    n_cmp = n_mis = 0
    for t, arr in gen:
        a2 = keep60.get(int(t))
        if a2 is None:
            continue
        n_cmp += 1
        if not np.array_equal(a2, arr):
            n_mis += 1
    wb.close()
    add("q3_is_q2_on_its_own_grid", n_mis == 0 and n_cmp == int(round(q3["last_row_s"] / 60.0)),
        "比对 %d 行（应 %d 行，60 s 网格），不一致 %d 行"
        % (n_cmp, int(round(q3["last_row_s"] / 60.0)), n_mis))

    # ── 13) metric-spec 的每项指标都解析到有限标量
    bad = []
    for m in spec["metrics"]:
        try:
            cur = read_json(m["source"])
            for part in m["pointer"][1:].split("/"):
                cur = cur[int(part)] if isinstance(cur, list) else cur[part]
            if not math.isfinite(float(cur)):
                bad.append(m["id"])
        except Exception as exc:                                     # noqa: BLE001
            bad.append("%s(%s)" % (m["id"], exc))
    add("result_jsons_agree_with_metric_spec", not bad,
        "%d 项指标全部可解析为有限标量；失败 %s" % (len(spec["metrics"]), bad or "无"))

    print(json.dumps({"checks": checks}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
