# 计算后端：CPU 串行 / CPU 并行 / GPU

> 核心原则：**先看问题形状，再选后端；GPU 不是默认目标。**
> 运行时先用
> `python skills/4Coding-and-computation/scripts/detect_compute.py --problem <形态> --batch <规模>`
> 看建议；它只探测、不安装、不启动训练。

## 0. 先分清三个“时间”

| 时间 | 是什么 | 不是 |
|---|---|---|
| `CALL_HARD_CAP`（3h） | 单个阶段 agent 调用的墙钟**安全上限** | 不是求解器实际耗时 |
| `code` 阶段默认 90 min | 阶段不延长时的默认上限 | 不是方法复杂度 |
| `run_all.py` 十几分钟 | A 题主流程实际计算时间（320 单元、1 s 步长、四问） | 不是 GPU 才能达到 |

先量测，再谈并行/GPU。**不要因为别人 PSO 跑了 30h 就把自己的 10 分钟确定性求解改成 30h。**

## 1. 选择树

```
单次求解是 1D 径向 PDE / 三对角时间推进吗？
  是 → CPU 串行（GPU 的 kernel 启动、小数组、顺序依赖都不划算）
  否 → 有大量彼此独立的样本/参数组/粒子/问吗？
         是 → CPU 多进程（最稳）；只有批量足够大且目标函数已向量化时才考虑 GPU
         否 → 单次大规模稠密线性代数/响应面？
                是 → 有 GPU 工具链且规模够大 → GPU；否则 CPU
                否 → CPU 串行
```

### 1.1 CPU 串行

适合：

- 1D 径向有限体积、三对角/Thomas、逐时间步推进；
- 问题规模小（N ≤ 数千、时间步数千–数万）；
- 单次运行秒–分钟级。

A 题就是这个形态：`run_all.py` 十几分钟；GPU 版本要重写内核，收益为负。

### 1.2 CPU 多进程

适合：

- 多个独立问（Q1/Q2/Q4 可并行；Q3 依赖 Q2）；
- 几十–几百组参数扫描；
- Monte Carlo / bootstrap / PSO 多次重启；
- 独立网格/步长收敛实验。

写法：

```python
from concurrent.futures import ProcessPoolExecutor, as_completed

def run_one(cfg):
    out = solve(cfg)
    (tmp / f"{cfg.tag}.json").write_text(json.dumps(out))
    return cfg.tag

with ProcessPoolExecutor(max_workers=workers) as ex:
    for tag in as_completed([ex.submit(run_one, c) for c in cfgs]):
        ...
# 主进程最后串行读取 tmp、排序、写 code/outputs/ 与 results/
```

硬规则：

- **单一交付写者**：worker 只写 `_tmp/` 或 `code/outputs/<tag>.json` 这类按任务分开的文件；
  主进程最后串行合并，不在 worker 里写 `results/`、`figures/data`、manifest。
- **内存按峰值算**：2D 轴对称稀疏 LU 的峰值在 SuperLU 分解阶段；默认
  `max_workers ≤ 3`（实测 12 路全部 `MemoryError`/`SUPERLU_MALLOC`）。不要按稳态内存估。
- **确定性**：每个 worker 固定 seed；结果按 tag 排序后再合并。
- **可续跑**：每完成一项立刻落盘；重跑读回已完成 tag 跳过（与 `fma-2d-parallelism-limit` 的约定一致）。

### 1.3 GPU

适合：

- 大型稠密线性代数/矩阵乘法、响应面、图像/场的大批量数组运算；
- Monte Carlo / PSO **且目标函数已整体向量化**、批量足够大（经验阈值：≥10⁵ 样本或
  ≥10³ 粒子且单次目标评估很便宜）；
- 2D/3D 大网格、可用 cuDSS/cuSPARSE 等 GPU 稀疏求解器（不是 SciPy/SuperLU 自动加速）。

不适合：

- 1D 三对角/逐时间步顺序推进；
- 小规模、Python 循环、稀疏 LU（SciPy/SuperLU）；
- 每次评估要读文件/调用 Python 函数的 PSO——GPU 会把开销放大。

纪律：

- 先写一个**缩比基准**（如 10% 网格/样本），CPU 与 GPU 各跑一次；GPU **≥2×** 快且显存够，
  才保留 GPU 内核；否则回 CPU。
- GPU 代码必须有 CPU fallback；检测不到 `torch/cupy/jax` 或 GPU 时自动回退。
- 不要为了“用 GPU”而预装大型深度学习环境；`docs/ENVIRONMENT.md` 明确不预装无关的 GPU 环境。
- GPU worker 也只写自己的临时结果，主进程串行合并。

## 2. 本机探测

```bash
python skills/4Coding-and-computation/scripts/detect_compute.py --problem 1d-pde
python skills/4Coding-and-computation/scripts/detect_compute.py --problem 2d-pde
python skills/4Coding-and-computation/scripts/detect_compute.py --problem monte-carlo --batch 200000
```

输出包含 CPU 物理/逻辑核、内存、GPU 型号/显存、`torch/cupy/jax` 是否真的能用 GPU，以及
`recommended_backend` / `workers` / 理由。它不会安装任何东西。

## 3. A 题实例

- 主流程：`python run_all.py`，普通笔记本约十几分钟；**CPU 串行**即可。
- 想更快：Q1/Q2/Q4 三问独立，可 `ProcessPoolExecutor(max_workers=2–3)` 并行；
  Q3 依赖 Q2，放最后。主进程串行写 `result*.xlsx`。
- 想更多证据：网格/步长/物性/收缩参数扫描，几十组独立任务 → CPU 多进程；不需要 GPU。
- 2D 轴对称端面：CPU 多进程，`max_workers ≤ 3`；GPU 只有在换成 cuDSS/cuSPARSE 且网格足够大时再评估。
- Monte Carlo 不确定性：≥10⁵ 样本且目标函数能整体向量化时，才值得写 CuPy/JAX/Torch 版本；
  否则 CPU 多进程更稳。

## 4. 租服务器怎么选

- **优先多核 CPU + 足够内存**：独立实验按核并行，16–32 核通常比一张 GPU 更直接。
- **GPU 只在有 GPU 原生内核时租**：确认代码用 CuPy/JAX/Torch/cuDSS，而不是“装了 GPU 就能快”。
- **内存比核数更关键**：2D 稀疏 LU 的峰值内存决定并发上限；先按 3 路估内存。
- **先在本机跑通并行/缩比**，再迁服务器；不要在服务器上第一次调试并行。
