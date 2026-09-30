# -*- coding: utf-8 -*-
"""药材热风烘干：共用内核（环境驱动 / 物性 / 有限体积求解器 / 舍入 / xlsx 交付 / 方法标记）。

口径全部来自 `reports/ANALYSIS_MODELING_REPORT.md`（v1.5），逐条对应：

| 本文件的实现 | 报告出处 |
|---|---|
| 内部一律 SI（m, s, K, kg/kg） | §5.8 第 1 条、§13 统一代码契约 |
| 面值物性取**算术平均** `kappa_{i+1/2}=(kappa_i+kappa_{i+1})/2` | §5.6、§13（写死） |
| 半隐式欧拉：物性系数按状态场**滞后一步**、不迭代 | §5.6、§6.6、§8.5 |
| Robin 边界与 1/R^2 前因子里的 T_inf, C_inf, R 取**步末层** t_{n+1} | §5.6/§6.6/§8.5 第 1 条/§13（四处各写一次） |
| 每步**先更新 C、再用新 C 更新 T**（C -> rho*cp,k 当步生效） | §4.1、§6.6 |
| 水分方程用**干物质密度**口径 ⇒ 实装为纯 Fick 式（rho_d 已除掉） | §4.3、§8.4 |
| xi = r/R(t) 参考坐标（Q4），前因子 1/R^2 + 边界因子 R(t) | §8.4、§9.3 |
| C<=0 或 T<=0 K 立即停机报错（不截断/不投影） | §5.6、§6.8 第 4 条 |
| 舍入用十进制 `ROUND_HALF_UP`（不用内建 `round`） | §5.8 第 2 条 |
| 逐时刻 argmax_r C 自检 + 亏量护栏 1e-10*C(0,t) | §5.8 第 6 条 |
| `result*.xlsx` 以附件 3 模板为底本，表头/工作表名从模板复制；A 列写整数 | §5.8 第 3-4 条、§13 |
| 交付档 N>=320、dt=1 s | §5.8 第 5 条、§6.6 |
| 求根用 `brentq`，xtol/rtol 登记 | §7.5、§13 |

代码之间**同目录裸名导入**（`import core`），即提交件里全部 `.py` 平铺也能跑。
数据/结果的路径一律**相对当前工作目录**（项目根）解析。
"""
from __future__ import annotations

import datetime as _dt
import json
import math
import os
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

import numpy as np
from scipy.linalg import solve_banded

# ── 项目根：相对**当前工作目录**解析（提交件平铺时可从任意 cwd 跑） ──────────────
ROOT = Path(os.environ.get("NMA_ROOT") or Path.cwd()).resolve()

STAGE = "code"
# 驱动在 prompt 里注入的 code/ 指纹；落 code/outputs/*.meta.json 时原样抄进 `_code_fp`。
CODE_FP = "dc8e04c98fa0"

# ── 题面给定的参数（附录 2 的 h、h_m 在四问中沿用，§3.3 第 4 条） ──────────────
R0 = 0.02            # 初始半径 2 cm（H1）
H_C = 25.0           # 对流换热系数 W/(m^2 K)（附录 2）
HM = 8e-7            # 对流传质系数 m/s（附录 2）
T0_C = 28.0          # 初温 °C（H2）
T0 = T0_C + 273.15   # 内部一律 K（H9）
C0 = 2.55            # 初始干基含水率 kg/kg（H2）
THRESH = 0.15        # 题面问题 3 的达标阈值 kg/kg（H10）
T_END_ENV = 14400.0  # 附件 1 的记录上界
R_END_T = 259200.0   # 附件 2 的记录上界（72 h）
R_END = 0.01198      # 附件 2 末值 1.198 cm
LV = 2.383e6         # 汽化潜热（**仅对照档**；题面未给，§3.1 A3、§11.4）
T_MAX = 259200.0     # Q2/Q3/Q4 输出窗上界（A7=A，72 h）
GUARD = 1e-10        # argmax 亏量护栏系数（§5.8 第 6 条，写死）
BRENTQ_XTOL = 1e-9   # brentq 的 xtol（s）—— §13 要求登记实际取值
BRENTQ_RTOL = 1e-12  # brentq 的 rtol

SHEETS_12 = ["温度", "水分浓度"]                        # result1/2 的两个工作表（模板实测）
SHEET_34 = ["Sheet1"]                                   # result3/4 的单表（模板实测）
DIST_Q1 = [i * 0.1 for i in range(21)]                  # result1/2/3：0..2.0 cm（21 列）
DIST_T5 = [0.0, 0.5, 1.0, 1.5, 2.0]                     # 表 1–5 的 5 个半径列
DIST_T6 = [0.0, 0.5, 1.0]                               # 表 6 的 3 个固定距离列
SURFACE_LABEL = "药材表面"                               # 表 6 / result4 的末列文字（模板实测）


# ═══════════════════════════════════════════════════════════════════════════
# 1. 舍入与通用工具
# ═══════════════════════════════════════════════════════════════════════════
def round4(x):
    """十进制 ROUND_HALF_UP 保留 4 位小数（§5.8 第 2 条；**不用**内建 `round`）。

    内建 `round()` 是银行家舍入（0.12345 → 0.1234），与 Excel/评委口径不一致。
    向量化实现 + 对"第 5 位恰为 5"的近边界项回落到 `decimal.Decimal` 精确判定
    （纯浮点 `floor(y+0.5)` 在 0.12345 这类十进制半值上会因二进制表示误差给出 0.1234）。

    ⚠️ 两处都踩过坑，改这一段前先读：
      ① 近边界的判据必须是 **小数部分 |frac-0.5|<1e-6**，不是 `|y+0.5-floor(y+0.5)|<1e-6`
         —— 后者对 y=1234.4999999999998 给出 |1234.9999999999998-1234|≈1 ⇒ 漏判；
      ② `Decimal` 分支量化的是 **v×10⁴**（`scaleb(4)`），不是 v 本身
         —— 对 v 直接 `quantize(Decimal(1))` 会把 50.16465 变成 50，再除以 10⁴ 得 **0.005**，
         即把一个正确值打成一个差 4 个数量级的错值（实测在交付件 `result2.xlsx` 里
         造出过 1 个这样的坏格，靠 `validate_results.py` 的逐行单调性检查抓到）。
    """
    a = np.asarray(x, dtype=float)
    flat = a.ravel()
    s = np.where(flat < 0, -1.0, 1.0)
    y = np.abs(flat) * 1e4
    r = np.floor(y + 0.5)
    frac = y - np.floor(y)
    near = np.flatnonzero(np.abs(frac - 0.5) < 1e-6)
    one = Decimal(1)
    for i in near:
        v = float(flat[i])
        r[i] = float(Decimal(repr(v)).scaleb(4).quantize(one, rounding=ROUND_HALF_UP))
    return (s * r / 1e4).reshape(a.shape)


def write_json(path, data):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.name + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(p)


def out_dir():
    d = ROOT / "code" / "outputs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def results_dir():
    d = ROOT / "results"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _produced_at():
    return _dt.datetime.now().replace(microsecond=0).isoformat()


def log(msg):
    print(msg, flush=True)


def scale_estimate(tag, scale, elapsed, total_est):
    """缩比预估的机器可读行（stage_discipline §2）。"""
    log("[SCALE_ESTIMATE] tag=%s scale=%.3f elapsed=%.1fs total_est=%.0fs"
        % (tag, scale, elapsed, total_est))


# ── 分段落盘 + 方法标记（stage_discipline §3/§4，一个工具两条纪律） ────────────
class Checkpoint:
    """滚动状态片：`save(state, monitor=…)` 覆盖写 `<outputs>/<name>.npz` 并顺手写 `.meta.json`。"""

    def __init__(self, name, method, params, dir_=None):
        self.name = name
        self.method = method
        self.params = params
        self.dir = Path(dir_) if dir_ else out_dir()
        self.dir.mkdir(parents=True, exist_ok=True)
        self.monitor = []

    def _paths(self):
        return (self.dir / (self.name + ".npz"), self.dir / (self.name + ".monitor.json"))

    def save(self, state, monitor=None):
        npz, mon = self._paths()
        np.savez_compressed(npz, **state)
        if monitor:
            self.monitor.append(monitor)
            mon.write_text(json.dumps(self.monitor, ensure_ascii=False), encoding="utf-8")
        (self.dir / (self.name + ".npz.meta.json")).write_text(json.dumps(
            {"_method": self.method, "_code_fp": CODE_FP, "_params": self.params,
             "_produced_at": _produced_at(), "_stage": STAGE,
             "_note": "滚动续跑状态片（每段覆盖写）；meta 名与产物名严格同名（<name>.npz）"}, ensure_ascii=False, indent=1),
            encoding="utf-8")

    def restore(self):
        npz, mon = self._paths()
        if not npz.is_file():
            return None
        with np.load(npz) as z:
            st = {k: z[k] for k in z.files}
        if mon.is_file():
            try:
                self.monitor = json.loads(mon.read_text(encoding="utf-8"))
            except Exception:                                    # noqa: BLE001
                self.monitor = []
        return st

    def clear(self):
        for p in list(self._paths()) + [self.dir / (self.name + ".npz.meta.json")]:
            if p.exists():
                p.unlink()


def meta_map():
    """扫 `code/outputs/*.meta.json` —— 复用判定（§4.2）的输入。"""
    rows = []
    for m in sorted(out_dir().glob("*.meta.json")):
        try:
            rows.append(dict(name=m.name[: -len(".meta.json")],
                             **json.loads(m.read_text(encoding="utf-8"))))
        except Exception:                                        # noqa: BLE001
            rows.append(dict(name=m.name[: -len(".meta.json")], _method="<unreadable>", _params=None))
    return rows


def scan_reuse(verbose=True):
    """重跑时逐项比对 `_method`/`_params`（§4.2）：一致才可复用，不一致必须重算。

    返回 (指纹一致名单, 需作废名单)。**交付数值一律由本轮实跑产生** —— 这里只做登记与提示。
    """
    rows = meta_map()
    fp = str(CODE_FP)
    stale = [r for r in rows if str(r.get("_code_fp")) != fp]
    fresh = [r for r in rows if str(r.get("_code_fp")) == fp]
    if verbose:
        log("[复用判定] 扫到 %d 份 .meta.json：指纹一致 %d、不一致 %d" % (len(rows), len(fresh), len(stale)))
        for r in stale:
            log("  · 作废旧产物（方法/指纹变更）：%s（_code_fp=%s）" % (r["name"], r.get("_code_fp")))
        for r in fresh:
            log("  · 指纹一致：%-24s method=%s" % (r["name"], str(r.get("_method"))[:46]))
    return [r["name"] for r in fresh], [r["name"] for r in stale]


# ═══════════════════════════════════════════════════════════════════════════
# 2. 附件 1（环境）与附件 2（半径）
# ═══════════════════════════════════════════════════════════════════════════
def _load_sheet(path):
    from openpyxl import load_workbook
    wb = load_workbook(path, data_only=True)
    ws = wb[wb.sheetnames[0]]
    rows = [r for r in ws.iter_rows(values_only=True)]
    return ws.title, rows[0], rows[1:]


def load_env(path=None):
    """附件 1：241 点、60 s 等步长、0–14400 s（T1）。返回 (t[s], T[°C], C[kg/kg])。"""
    path = Path(path or (ROOT / "request" / "attachments" / "附件1.xlsx"))
    _, _, rows = _load_sheet(path)
    t = np.array([float(r[0]) for r in rows], float)
    T = np.array([float(r[1]) for r in rows], float)
    C = np.array([float(r[2]) for r in rows], float)
    assert len(t) == 241, f"附件1 点数应为 241，实测 {len(t)}"
    assert np.allclose(np.diff(t), 60.0), "附件1 步长应严格 60 s"
    return t, T, C


class Env:
    """环境驱动：t<=14400 s 线性插值；t>14400 s 按档延拓（默认零阶保持，§3.3 第 2 条）。

    `mode` 三档（T1 的"三档参数化"，供 `robustness` 直接复用，§6.8 第 2 条）：
      · `hold`    零阶保持 50.165 °C / 0.04986 kg/kg（**主档**）
      · `peak`    保持峰值 50.246 °C / 0.05025 kg/kg
      · `plateau` 一阶饱和逼近 T_f=50.30 °C（k=3e-4 s^-1）
    返回 (T[K], C[kg/kg]) —— **温度统一 K**（H9）。
    """

    def __init__(self, t, Tc, C, mode="hold"):
        self.t, self.Tc, self.C = np.asarray(t, float), np.asarray(Tc, float), np.asarray(C, float)
        self.mode = mode

    def at(self, t):
        t = float(t)
        # ⚠️ `cut1800` 的冻结必须**排在基础插值分支之前** —— 否则 t∈(1800,14400] 会被基础分支
        #    提前返回插值值、冻结永远不生效（实测该写法把 t_dry 由 76.35 h 错成 75.83 h）。
        if self.mode == "cut1800":
            if t <= 1800.0:
                return (float(np.interp(t, self.t, self.Tc)) + 273.15,
                        float(np.interp(t, self.t, self.C)))
            return 41.513 + 273.15, 0.03307
        if t <= T_END_ENV:
            return (float(np.interp(t, self.t, self.Tc)) + 273.15,
                    float(np.interp(t, self.t, self.C)))
        if self.mode == "hold":
            return float(self.Tc[-1]) + 273.15, float(self.C[-1])
        if self.mode == "peak":
            return float(self.Tc.max()) + 273.15, float(self.C.max())
        if self.mode == "plateau":
            Tf, kk = 50.30, 3.0e-4
            return (Tf - (Tf - float(self.Tc[-1])) * math.exp(-kk * (t - T_END_ENV)) + 273.15,
                    float(self.C[-1]))
        raise ValueError("未知环境延拓档: %s" % self.mode)

    def stage(self, t):
        """两阶段判别（§6.8 第 3 条）：阶段差别**只在环境**。"""
        return "预热平衡段" if float(t) <= T_END_ENV else "恒温干燥段"


def load_radius(path=None):
    """附件 2：145 点、1800 s 等步长、2.000→1.198 cm（T2）。返回 (t[s], R[m])。"""
    path = Path(path or (ROOT / "request" / "attachments" / "附件2.xlsx"))
    _, _, rows = _load_sheet(path)
    t = np.array([float(r[0]) for r in rows], float)
    R = np.array([float(r[1]) for r in rows], float) * 0.01      # cm → m
    assert len(t) == 145, f"附件2 点数应为 145，实测 {len(t)}"
    assert np.allclose(np.diff(t), 1800.0), "附件2 步长应严格 1800 s"
    assert abs(R[0] - R0) < 1e-12 and abs(R[-1] - R_END) < 1e-12
    assert np.all(np.diff(R) <= 1e-15), "附件2 半径应单调不增"
    return t, R


class Radius:
    """R(t)：主档**分段线性**（`np.interp`）；`step` 档＝零阶保持（对照，§8.7 第 1 条）。"""

    def __init__(self, t, R, mode="linear"):
        self.t, self.R, self.mode = np.asarray(t, float), np.asarray(R, float), mode

    def at(self, t):
        t = float(min(t, R_END_T))
        if self.mode == "step":
            i = int(np.searchsorted(self.t, t, side="right")) - 1
            i = max(0, min(i, len(self.R) - 1))
            return float(self.R[i])
        return float(np.interp(t, self.t, self.R))


# ═══════════════════════════════════════════════════════════════════════════
# 3. 物性（附录 2/3/4；温度支一律 K）
# ═══════════════════════════════════════════════════════════════════════════
def props(kind, C, T):
    """返回 (rho, cp, k, D)。`rho` 是**湿态**密度（只进 rho*cp）；`T` 必须 K。"""
    C = np.asarray(C, float)
    T = np.asarray(T, float)
    if kind == "q1":                       # 附录 2（常数 + D(C)）
        rho = np.full_like(C, 820.0)
        cp = np.full_like(C, 2600.0)
        k = np.full_like(C, 0.36)
        D = 7e-9 * np.exp(-0.89 / C)
    elif kind == "q23":                    # 附录 3
        rho = 650.0 + 128.0 * C
        cp = 1450.0 + 2736.0 * C / (C + 1.0)
        k = 0.21 + 0.38 * C / (C + 1.0)
        D = 2.4e-3 * np.exp(-0.45 / C) * np.exp(-3850.0 / T)
    elif kind == "q4":                     # 附录 4
        rho = 760.0 + 90.0 * C
        cp = 1850.0 + 2150.0 * C / (C + 1.0)
        k = 0.12 + 0.20 * C / (C + 1.0)
        D = 4.2e-4 * np.exp(-0.30 / C) * np.exp(-3850.0 / T)
    else:
        raise ValueError("未知物性档: %s" % kind)
    return rho, cp, k, D


def d_rho_cp_dC(kind, C):
    """$\\partial(\\rho c_p)/\\partial C$ 的**解析式**（只服务焓守恒改写档的口径）。

    附录 3：$\\rho=650+128C$、$c_p=1450+2736C/(1+C)$ ⇒ $\\partial_C c_p=2736/(1+C)^2$；
    附录 4 同形（$90$ 与 $2150$）。附录 2 是常数物性 ⇒ 恒为 0
    （这正是 §11.1「第二项在 Q1 归零」的由来）。
    """
    C = np.asarray(C, float)
    if kind == "q1":
        return np.zeros_like(C)
    if kind == "q23":
        rho = 650.0 + 128.0 * C
        cp = 1450.0 + 2736.0 * C / (C + 1.0)
        return 128.0 * cp + rho * 2736.0 / (C + 1.0) ** 2
    if kind == "q4":
        rho = 760.0 + 90.0 * C
        cp = 1850.0 + 2150.0 * C / (C + 1.0)
        return 90.0 * cp + rho * 2150.0 / (C + 1.0) ** 2
    raise ValueError("未知物性档: %s" % kind)


def rho_d0(kind):
    """初始**干物质**密度 rho_d0 = rho(C0)/(1+C0)（§4.2 的取值口径）。

    Q1 230.99 / Q2-Q3 275.04 / Q4 278.73 kg/m³。只用于**物理质量通量** j_s 与口径说明；
    实装的 C 方程是守恒式除以空间均匀 rho_d 之后的纯 Fick 式（§4.3），方程里不出现它。
    """
    rho, _, _, _ = props(kind, np.array([C0]), np.array([T0]))
    return float(rho[0] / (1.0 + C0))


# ═══════════════════════════════════════════════════════════════════════════
# 4. 有限体积（柱坐标 xi 网格；Q1–Q3 的 R≡R0 是其特例）
# ═══════════════════════════════════════════════════════════════════════════
def grid(n_cell):
    """xi 网格（§5.6）：V 为柱坐标有限体积，r=0 处面积为零 ⇒ 对称条件自动成立。"""
    xi = np.linspace(0.0, 1.0, n_cell + 1)
    dx = xi[1] - xi[0]
    xf = 0.5 * (xi[:-1] + xi[1:])
    V = np.empty(n_cell + 1)
    V[0] = xf[0] ** 2 / 2.0
    V[-1] = (1.0 - xf[-1] ** 2) / 2.0
    V[1:-1] = (xf[1:] ** 2 - xf[:-1] ** 2) / 2.0
    return xi, xf, dx, V


FACE_MODES = ("arith", "geom", "harm")


def face_value(kap, mode="arith"):
    """面值物性 kappa_{i+1/2}：**主档算术平均**（§5.6，写死）。

    `geom`/`harm` 只供 `sensitivity.py` 的口径对照档（§11.2 的三档实测）；交付档不得切换。
    """
    kap = np.asarray(kap, float)
    if mode == "arith":
        return 0.5 * (kap[:-1] + kap[1:])
    if mode == "geom":
        return np.sqrt(kap[:-1] * kap[1:])
    if mode == "harm":
        return 2.0 * kap[:-1] * kap[1:] / (kap[:-1] + kap[1:])
    raise ValueError("未知面导度取法: %s" % mode)


def implicit_step(U, V, xf, dx, kap, dt, cap, h_bc, U_inf, scale, bfac, src=None,
                  face="arith"):
    """半隐式欧拉一步（隐式主项 + 系数已冻结；**不迭代**，§5.6）。

    离散式：V_i(U_i^{n+1}-U_i^n)/dt = Phi_{i-1/2} - Phi_{i+1/2}，
    Phi_{i+1/2} = scale * r_{i+1/2} * kappa_{i+1/2} * (U_i-U_{i+1})/dx，
    末面 Phi_{N+1/2} = scale * R * h_bullet * (U_N - U_inf)。
    `scale`=1/R^2（Q4 的动域前因子），`bfac`=R（边界因子里那个 R）。
    """
    n = len(U)
    af = face_value(kap, face)
    G = scale * xf * af / dx
    capv = V * (np.ones(n) if cap is None else np.asarray(cap, float)) / dt
    diag = capv.copy()
    diag[:-1] += G
    diag[1:] += G
    diag[-1] += scale * bfac * h_bc
    rhs = capv * U
    rhs[-1] += scale * bfac * h_bc * U_inf
    if src is not None:
        rhs = rhs + V * np.asarray(src, float)
    ab = np.empty((3, n))
    ab[0, 1:] = -G
    ab[1, :] = diag
    ab[2, :-1] = -G
    return solve_banded((1, 1), ab, rhs)


def sample_out(U, q):
    """把节点值插到输出网格 `q`（xi ∈ [0,1]）；命中节点时**直接取节点值**（逐位可复现）。"""
    n = len(U) - 1
    xi = np.linspace(0.0, 1.0, n + 1)
    q = np.asarray(q, float)
    idx = q * n
    if np.all(np.abs(idx - np.rint(idx)) < 1e-9):
        j = np.rint(idx).astype(int)
        if j.min() >= 0 and j.max() <= n:
            return np.asarray(U, float)[j]
    return np.interp(q, xi, np.asarray(U, float))


# ═══════════════════════════════════════════════════════════════════════════
# 5. 主求解器
# ═══════════════════════════════════════════════════════════════════════════
MON_KEYS = ("t", "maxC", "C0", "Cs", "Tc", "Ts", "deficit", "Tinf", "Cinf", "R",
            "Tmin", "Cmin", "meanC", "meanT")
CONS_KEYS = ("t", "dC_int", "bcC", "dE", "bcT")


def solve(kind, t_end, dt, n_cell=320, *, shrink=False, env_mode="hold", radius_mode="linear",
          face="arith", env=None, rad=None, snap_every=None, sample=True,
          latent=False, sensible=False, sensible_scale="K", hm=HM, hc=H_C, label="",
          keep_cons=True):
    """推进求解。返回 dict（含 21 列输出网格、监控序列、快照、收支增量）。

    时间层（写死）：`Te, Ce = env.at(t_{n+1})`、`Rcur = rad.at(t_{n+1})`；
    物性系数 `props(kind, Cn, Tn)` 取**上一步**的状态场（滞后一步）。
    每步顺序：`Cn_new = step(C, D(Cn,Tn))` -> `props(Cn_new, Tn)` -> `Tn_new = step(T)`。
    """
    if env is None:
        env = Env(*load_env(), mode=env_mode)
    if rad is None:
        rad = Radius(*load_radius(), mode=radius_mode)
    xi, xf, dx, V = grid(n_cell)
    n = n_cell

    Tn = np.full(n + 1, T0)
    Cn = np.full(n + 1, C0)
    nsteps = int(round(t_end / dt))
    q_out = np.array(DIST_Q1) * 0.01 / R0            # xi 坐标下的输出网格（R=R0 时恒定）

    T_out = np.full((nsteps, len(DIST_Q1)), np.nan) if sample else None
    C_out = np.full((nsteps, len(DIST_Q1)), np.nan) if sample else None
    mon = {k: np.zeros(nsteps) for k in MON_KEYS}
    mon["argmax"] = np.zeros(nsteps, dtype=np.int64)
    cons = {k: np.zeros(nsteps) for k in CONS_KEYS} if keep_cons else None
    snaps = {"t": [], "R": [], "T": [], "C": []}
    cap_prev = None
    t = 0.0
    t_dry_step = None
    stage_seen = set()
    for k in range(nsteps):
        h = min(dt, t_end - t)
        tn = t + h
        # ── 步末层的环境与几何（§5.6/§6.6/§8.5 第 1 条/§13 四处各写一次，这里是唯一实现处）
        Te, Ce = env.at(tn)
        stage_seen.add(env.stage(tn))
        Rcur = rad.at(tn) if shrink else R0
        scale = 1.0 / (Rcur ** 2)
        # ── 物性用上一步的状态场（滞后一步）；变量名避开步序 k
        rho, cp, kk, D = props(kind, Cn, Tn)
        # ── 先更新 C
        Cn_new = implicit_step(Cn, V, xf, dx, D, h, None, hm, Ce, scale, Rcur,
                               face=face)
        rho2, cp2, k2, _ = props(kind, Cn_new, Tn)       # C -> (rho,cp,k) 当步生效
        cap_used = rho2 * cp2
        # ── 再更新 T（源项只在对照档非零）
        srcT = None
        if sensible:
            # 焓守恒改写档：源项 = -T ∂_t(ρc_p)，温标取 K（§10 第 2 行写死）。
            # ⚠️ ∂(ρc_p)/∂C **必须解析求导**：用差分 `(ρc_p(C+ε)-ρc_p(C))/ε` 时，
            #    若基点评在**不同的 C**（旧 C 与新 C）上，差值会被 C 的变化量主导
            #    （实测 ε=1e-6、ΔC=-0.19 ⇒ dP 虚高到 -1.26e11、T 一步掉到 -1.97e5 K）；
            #    即使基准一致，ρc_p≈3.3e6 的一阶差分也只有 ~0.65 的有效位 ⇒ 相差一个 eps 就失真。
            dP = d_rho_cp_dC(kind, Cn)
            srcT = -(Tn - 273.15 if sensible_scale == "C" else Tn) * dP * (Cn_new - Cn) / h
        if latent:
            # 潜热档：表面汇 = -L_v * rho_d * h_m (C_s - C_inf)，按 ξ 度量的最后单元体积折算。
            # ⚠️ 密度因子 rho_d **不能漏**（§3.2/§11.4：h_m ΔC 是质量比通量、单位 m/s；
            #    乘 rho_d 才是 kg/(m²s)）。实测漏乘时该档**完全不起作用**（t_dry 与基准逐位相同），
            #    含 rho_d 时复现 §11.3 登记的 59.9667 h。
            rho_d = rho_d0(kind) * (R0 / Rcur) ** 2          # Q4：rho_d(t)=rho_d0 (R0/R)^2（§4.2）
            j = hm * (Cn_new[-1] - Ce)                       # 质量比通量 m/s
            s = np.zeros(n + 1)
            s[-1] = -j * LV * rho_d / (Rcur * max(V[-1], 1e-300))
            srcT = s if srcT is None else srcT + s
        Tn_new = implicit_step(Tn, V, xf, dx, k2, h, cap_used, hc, Te, scale, Rcur,
                               src=srcT, face=face)
        # ── 数值护栏（§5.6/§6.8 第 4 条）：不截断、不投影，直接停机
        if not (np.all(np.isfinite(Cn_new)) and np.all(np.isfinite(Tn_new))):
            raise FloatingPointError("非有限值：t=%.1f s（%s）" % (tn, label))
        if Cn_new.min() <= 0.0:
            raise FloatingPointError("C<=0 于 t=%.1f s（%.3e）（%s）" % (tn, Cn_new.min(), label))
        if Tn_new.min() <= 0.0:
            raise FloatingPointError("T<=0 K 于 t=%.1f s（%.3e）（%s）" % (tn, Tn_new.min(), label))
        # ── 收支核对用的离散增量（§11.1 的伸缩和，逐项对齐；见 check_conservation）
        if cons is not None:
            cons["t"][k] = tn
            cons["dC_int"][k] = np.sum(V * (Cn_new - Cn))
            cons["bcC"][k] = -h * scale * Rcur * hm * (Cn_new[-1] - Ce)
            if cap_prev is not None:
                cons["dE"][k] = np.sum(cap_used * (Tn_new - Tn) * V)
                cons["bcT"][k] = h * scale * Rcur * hc * (Te - Tn_new[-1])
            cap_prev = cap_used
        # ── 采样与监控
        if sample:
            if shrink:
                qq = (np.array(DIST_Q1) * 0.01) / Rcur
                ok = qq <= 1.0 + 1e-12
                vT = np.full(len(DIST_Q1), np.nan)
                vC = np.full(len(DIST_Q1), np.nan)
                if ok.any():
                    vT[ok] = sample_out(Tn_new, qq[ok])
                    vC[ok] = sample_out(Cn_new, qq[ok])
                T_out[k], C_out[k] = vT, vC
            else:
                T_out[k] = sample_out(Tn_new, q_out)
                C_out[k] = sample_out(Cn_new, q_out)
        mC = float(Cn_new.max())
        mon["t"][k] = tn
        mon["maxC"][k] = mC
        mon["C0"][k] = Cn_new[0]
        mon["Cs"][k] = Cn_new[-1]
        mon["Tc"][k] = Tn_new[0]
        mon["Ts"][k] = Tn_new[-1]
        mon["deficit"][k] = mC - Cn_new[0]
        mon["argmax"][k] = int(np.argmax(Cn_new))
        mon["Tinf"][k] = Te
        mon["Cinf"][k] = Ce
        mon["R"][k] = Rcur
        mon["Tmin"][k] = Tn_new.min()
        mon["Cmin"][k] = Cn_new.min()
        # Σ_i V_i C_i = ∫_0^1 C ξ dξ（柱坐标中点求积；ΣV_i = 1/2 已核）= 体积加权均值
        mon["meanC"][k] = float(np.sum(V * Cn_new))
        mon["meanT"][k] = float(np.sum(V * Tn_new))
        if t_dry_step is None and mC <= THRESH:
            t_dry_step = tn
        if snap_every and (k % snap_every == 0 or k == nsteps - 1):
            snaps["t"].append(tn); snaps["R"].append(Rcur)
            snaps["T"].append(Tn_new.copy()); snaps["C"].append(Cn_new.copy())
        Cn, Tn, t = Cn_new, Tn_new, tn
    out = dict(kind=kind, n=n_cell, dt=dt, t_end=t_end, shrink=bool(shrink),
               env_mode=env.mode, radius_mode=rad.mode, face=face, stages=sorted(stage_seen),
               T_out=T_out, C_out=C_out, mon=mon, cons=cons, snaps=snaps,
               t_dry_step=t_dry_step, label=label)
    return out


def first_step_field(kind, dt=1.0, n_cell=320, *, shrink=False, env_mode="hold", face="arith",
                     env=None, rad=None):
    """从初值推进**一步**，返回 (Cn, Tn, xi, V) —— 供 §5.8 第 6 条的 t=1 s 自检用。"""
    if env is None:
        env = Env(*load_env(), mode=env_mode)
    if rad is None:
        rad = Radius(*load_radius())
    xi, xf, dx, V = grid(n_cell)
    Tn = np.full(n_cell + 1, T0)
    Cn = np.full(n_cell + 1, C0)
    Te, Ce = env.at(dt)
    Rcur = rad.at(dt) if shrink else R0
    scale = 1.0 / Rcur ** 2
    _, _, _, D = props(kind, Cn, Tn)
    Cn = implicit_step(Cn, V, xf, dx, D, dt, None, HM, Ce, scale, Rcur, face=face)
    _, cp2, k2, _ = props(kind, Cn, Tn)
    rho2 = props(kind, Cn, Tn)[0]
    Tn = implicit_step(Tn, V, xf, dx, k2, dt, rho2 * cp2, H_C, Te, scale, Rcur, face=face)
    return Cn, Tn, xi, V


def selfcheck_q1(kind="q1", n_cell=320, dt=1.0, env=None, rad=None, r_inner_cm=1.9):
    """Q1 交付档自检（§5.8 第 6 条，按回执 `rev-q1-selfcheck-tolerance` 改成的**分节点区**判据）。

    · 温度侧（全节点）：|T-T0| < 1e-3 K —— T_inf(0)=T0 ⇒ 零阶相容，可达。
    · 水分侧 · 内部（r<=1.9 cm）：|C-C0| < 1e-4。
    · 水分侧 · 表面节点与最外约 0.04 cm：**只登记实测值**，不作小量判据
      （C_inf(0)=0.01963 != C0 ⇒ Robin 零阶相容不成立，表面是 O(sqrt(t)) 瞬态）。
    另返回 Q1 全窗的 argmax 护栏统计（由调用方传入 `mon`）。
    """
    Cn, Tn, xi, V = first_step_field(kind, dt=dt, n_cell=n_cell, env=env, rad=rad)
    inner = xi <= (r_inner_cm / 100.0) / R0 + 1e-12     # r <= r_inner_cm（xi 坐标）
    dT = float(np.max(np.abs(Tn - T0)))
    dC_in = float(np.max(np.abs(Cn[inner] - C0)))
    dC_surf = float(abs(Cn[-1] - C0))
    r_surf_band = float((1.0 - np.max(xi[inner])) * R0 * 100.0)
    return dict(t_check=dt, kind=kind, n=n_cell, dt=dt,
                温度侧全节点=dict(max_abs_dev=dT, tol=1e-3, passed=bool(dT < 1e-3),
                              note="T_inf(0)=28.000 °C=T0 ⇒ 零阶相容成立、容差可达"),
                水分侧内部=dict(r_max_cm=r_inner_cm, max_abs_dev=dC_in, tol=1e-4,
                                passed=bool(dC_in < 1e-4)),
                水分侧表面=dict(r_cm=2.0, band_cm=r_surf_band, abs_dev=dC_surf, passed=None,
                                note="不作小量判据、只登记实测值；该值是物理瞬态 "
                                     "(C_inf(0)=0.01963 != C0)，随 dt 减小向 §9.5 的角点标度收敛"),
                max_abs_C_dev_all=float(np.max(np.abs(Cn - C0))))


def argmax_guard(mon, kind="", n_cell=320, dt=1.0):
    """argmax / 亏量护栏统计（§5.8 第 6 条）——与报告同一门限 1e-10*C(0,t)。

    ⚠️ 判「违约」的门限是**亏量** $\\max_rC-C(0,t)>10^{-10}C(0,t)$，**不是**字面上的
    "某个节点严格大于中心节点"：中心与其邻点的浮点并列（1–5 ulp）会让字面判据在个别步误报。
    故 `argmax_all_zero`（原始布尔）与 `guarded_argmax_violations`（判据）**分列**，
    并打印窗口内最大亏量，使"是否只是浮点并列"可被复核。
    """
    guard = GUARD * mon["C0"]
    dev = mon["argmax"] != 0
    real = dev & (mon["deficit"] > guard)
    return dict(kind=kind, n=n_cell, dt=dt,
                argmax_all_zero=bool(np.all(mon["argmax"] == 0)),
                argmax_raw_deviations=int(np.sum(dev)),
                guarded_argmax_violations=int(np.sum(real)),
                guard_threshold_min=float(np.min(guard)),
                literal_violations=int(np.sum(mon["deficit"] > 0.0)),
                guarded_violations=int(np.sum(mon["deficit"] > guard)),
                max_deficit=float(np.max(mon["deficit"])),
                判据="亏量 max_rC - C(0,t) > 1e-10*C(0,t) 才算违约（原始 argmax!=0 只登记）")


# ═══════════════════════════════════════════════════════════════════════════
# 6. 达标时刻（连续求根，§7.4/§7.5）
# ═══════════════════════════════════════════════════════════════════════════
def locate_crossing(times, g, xtol=BRENTQ_XTOL, rtol=BRENTQ_RTOL):
    """在 g(t)=max_r C(t)-0.15 上找**首个**零点（连续时间，§7.4）。

    做法（§7.5 第 3–4 条）：区间扫描定位首个变号区间 → 时间上做**线性插值** →
    对插值函数用 `brentq` 求根，并给出闭式解作交叉核对。
    非单调兜底：扫描天然取**最小**根，不依赖 g 的单调性（§7.5 第 4 条）。
    """
    from scipy.optimize import brentq
    t = np.asarray(times, float)
    g = np.asarray(g, float)
    sign = g <= 0.0
    idx = np.flatnonzero(sign)
    n_cross = int(np.sum(np.diff(sign.astype(np.int8)) == 1))
    if idx.size == 0 or int(idx[0]) == 0:
        return dict(t_root=None, reason="窗内未达标（或首步即达标）", n_cross=n_cross)
    i = int(idx[0])
    t_lo, t_hi = float(t[i - 1]), float(t[i])
    g_lo, g_hi = float(g[i - 1]), float(g[i])

    def lin(x):
        return g_lo + (g_hi - g_lo) * (float(x) - t_lo) / (t_hi - t_lo)

    root = float(brentq(lin, t_lo, t_hi, xtol=xtol, rtol=rtol, maxiter=200))
    closed = t_lo + (0.0 - g_lo) * (t_hi - t_lo) / (g_hi - g_lo)
    after = g[i:]
    return dict(t_root=root, closed_form=float(closed), method="时间线性插值 + scipy.brentq",
                xtol=xtol, rtol=rtol, t_lo=t_lo, t_hi=t_hi, g_lo=g_lo, g_hi=g_hi,
                max_rC_at_root=float(THRESH + lin(root)),
                t_lo_step=float(t[i - 1]), g_at_prev_step=float(g[i - 1]),
                g_at_prev_step_60=None if i < 2 else float(g[i - 2]),
                t_prev_step_60=None if i < 2 else float(t[i - 2]),
                t_step_first_hit=float(t[i]),
                n_cross=n_cross,
                t_after_max_g=float(t[i + int(np.argmax(after))]),
                after_max_g=float(np.max(after)), n_recross=int(np.sum(np.diff((after <= 0).astype(np.int8)) == 1)))


# ═══════════════════════════════════════════════════════════════════════════
# 7. 交付件：result*.xlsx（以附件 3 模板为底本）
# ═══════════════════════════════════════════════════════════════════════════
def template_dir():
    return ROOT / "request" / "attachments" / "附件3"


def template_info(name):
    """从模板复制**工作表名、表头文本、A 列首数据行**（§5.8 第 3–4 条：不许自造版式，H12）。

    模板骨架是 5 行 × 6 列（0, 0.1, 0.2, '…', 2）；`'…'` 是**列占位** ⇒ 实际列集合由
    §8.5 第 4 条写死（result1/2/3 为 0..2.0 共 21 列；result4 为 0..1.9 + `药材表面`）。
    """
    from openpyxl import load_workbook
    wb = load_workbook(template_dir() / name)
    info = []
    for ws in wb.worksheets:
        head = [c.value for c in ws[1]]
        info.append(dict(sheet=ws.title, a1=head[0], d_first=head[1], d_last=head[-1],
                         first_time=ws.cell(row=2, column=1).value))
    return info


def write_result_xlsx(path, sheets):
    """写交付 xlsx。`sheets` = [dict(sheet=表名, head=完整表头列表, times=[...], values=(n,k) 数组)]。

    ⚠️ 用 `openpyxl` 的 **write_only** 模式：`result2.xlsx` 是 259200 行 × 22 列 × 2 表
    ≈ 1.1×10⁷ 个单元格 —— 普通模式下每个单元格一个 `Cell` 对象（>500 MB 内存 + 分钟级）；
    write_only 流式写入。表头文本从模板逐字复制（模板无任何特殊格式，全部 `General`，
    见 `_tmp/cd1_introspect.py` 的逐格实测）。
    数值写**四位小数的十进制值**（`round4`）；A 列写**整数**（§5.8 第 3 条）。
    """
    from openpyxl import Workbook
    wb = Workbook(write_only=True)
    for sp in sheets:
        ws = wb.create_sheet(title=sp["sheet"])
        ws.append(list(sp["head"]))
        times = sp["times"]
        vals = sp["values"]
        for i, t in enumerate(times):
            ti = int(round(t)) if abs(t - round(t)) < 1e-9 else float(t)
            row = [ti]
            for v in vals[i]:
                row.append(None if (v is None or not np.isfinite(v)) else float(v))
            ws.append(row)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    wb.save(str(path))


def head_list(dists, last_label=None):
    """构造交付的距离表头（A1 文本由调用方从模板取）。

    模板里首个距离是**整数** `0`、result1/2/3 的末列是**整数** `2` ⇒ 这两处逐字沿用整数写法；
    中间列写成 0.1 的十进制浮点。
    `result4`：`dists = 0..1.9`（20 列）**再追加**末列 `药材表面`（共 21 个数据列，§8.5 第 4 条）
    —— 追加而不是替换（`药材表面` 占的是模板里数字 `2` 的那一格，而 `1.9` 另有自己的列）。
    """
    out = []
    last = len(dists) - 1
    for i, d in enumerate(dists):
        if i == 0:
            out.append(0)
        elif i == last and last_label is None:
            out.append(int(round(float(d))))
        else:
            out.append(round(float(d), 10))
    if last_label is not None:
        out = out + [last_label]
    return out


def last_row_time(t_dry, dt=60.0):
    """交付件末行 = ceil(t_dry/dt)*dt（§7.4 末行口径）。"""
    return float(math.ceil(t_dry / dt - 1e-12) * dt)
