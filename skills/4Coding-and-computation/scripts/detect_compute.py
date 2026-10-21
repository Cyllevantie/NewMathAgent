#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""只读的算力探测 + 后端建议：CPU 核数/内存/GPU/可用 GPU 工具链。

用法（项目根目录）::

    python skills/4Coding-and-computation/scripts/detect_compute.py --problem 1d-pde
    python skills/4Coding-and-computation/scripts/detect_compute.py --problem monte-carlo --batch 200000

输出 JSON；不安装依赖、不启动训练、不改任何文件。

后端选择原则见 skills/4Coding-and-computation/references/compute-backends.md：
- 1D 径向 PDE / 三对角时间推进：CPU 串行（GPU 的 kernel 启动开销 > 小数组收益）；
- 独立实验（多问、参数扫描、Monte Carlo、PSO 重启）：CPU 多进程；
- 大型稠密线性代数/响应面：有 GPU 且规模够大时才 GPU；
- 2D 轴对称稀疏 LU：CPU 多进程，但按内存峰值限制并发（默认 ≤3）。
"""
from __future__ import annotations

import argparse
import ctypes
import json
import os
import shutil
import subprocess
import sys


def _cpu():
    logical = os.cpu_count() or 1
    physical = logical
    try:
        import psutil  # type: ignore
        physical = psutil.cpu_count(logical=False) or logical
        ram_gb = round(psutil.virtual_memory().total / (1024 ** 3), 1)
        return physical, logical, ram_gb
    except Exception:
        pass
    # 无 psutil：Windows 用 GlobalMemoryStatusEx；其他平台退回 logical。
    ram_gb = None
    try:
        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [("dwLength", ctypes.c_ulong),
                        ("dwMemoryLoad", ctypes.c_ulong),
                        ("ullTotalPhys", ctypes.c_ulonglong),
                        ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong),
                        ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong),
                        ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
        st = MEMORYSTATUSEX()
        st.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(st)):
            ram_gb = round(st.ullTotalPhys / (1024 ** 3), 1)
    except Exception:
        pass
    return physical, logical, ram_gb


def _gpus():
    """返回 (gpu_info_list, toolkits)。只探测，不安装。"""
    gpus = []
    exe = shutil.which("nvidia-smi")
    if exe:
        try:
            p = subprocess.run(
                [exe, "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
                capture_output=True, text=True, encoding="utf-8", errors="replace",
                timeout=5)
            if p.returncode == 0:
                for line in p.stdout.strip().splitlines():
                    parts = [x.strip() for x in line.split(",")]
                    if parts and parts[0]:
                        gpus.append({"name": parts[0],
                                     "memory_mb": int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else None})
        except Exception:
            pass
    toolkits = {}
    for mod in ("torch", "cupy", "jax"):
        try:
            m = __import__(mod)
            if mod == "torch":
                toolkits[mod] = bool(m.cuda.is_available())
            elif mod == "cupy":
                toolkits[mod] = bool(m.cuda.runtime.getDeviceCount())
            else:
                toolkits[mod] = any(getattr(d, "platform", "") == "gpu"
                                    for d in m.devices())
        except Exception:
            toolkits[mod] = False
    return gpus, toolkits


def _recommend(problem: str, batch: int, gpus, toolkits, physical, logical, ram_gb):
    problem = (problem or "auto").lower()
    gpu_ok = bool(gpus) and any(toolkits.values())
    reasons = []
    if problem in ("1d-pde", "tridiagonal", "ode", "pde1d"):
        return "cpu-serial", 1, [
            "1D 径向 PDE/三对角时间推进是顺序依赖的，GPU kernel 启动与小数组开销大于收益",
            "单次求解通常秒–分钟级；没必要为它引入 GPU 运行时",
        ]
    if problem in ("2d-pde", "sparse-lu", "pde2d"):
        workers = min(3, max(1, physical - 1))
        reasons += [
            "2D 轴对称稀疏 LU 的峰值内存在分解阶段，不是稳态内存；并发按内存封顶",
            "默认最多 3 路；有实测 12 路全部 MemoryError/SUPERLU_MALLOC 的记录",
        ]
        if gpu_ok and batch >= 2_000_000:
            reasons.append("若已用 cuDSS/cuSPARSE 且网格足够大，可另做 GPU 原型；SciPy/SuperLU 不会自动上 GPU")
        return "cpu-parallel", workers, reasons
    if problem in ("monte-carlo", "pso", "parameter-sweep", "sweep", "mc"):
        if gpu_ok and batch >= 100_000:
            return "gpu-batched", 1, [
                f"批量 {batch:,} 且检测到 GPU + 工具链；目标函数可向量化时 GPU 有优势",
                "若目标函数内部仍是逐样本时间推进/稀疏求解，GPU 收益有限，先用缩比基准测 CPU vs GPU",
            ]
        workers = max(1, logical - 2)
        if ram_gb:
            workers = min(workers, max(1, int(ram_gb // 2)))
        return "cpu-parallel", workers, [
            "独立样本/粒子/参数组之间可并行；CPU 多进程最稳",
            "每个 worker 只写自己的临时结果，主进程串行合并，保证单一交付写者",
            "GPU 只在批量足够大且目标函数已向量化时才值得",
        ]
    if problem in ("dense-la", "response-surface", "dense"):
        if gpu_ok:
            return "gpu-batched", 1, ["大型稠密线性代数/响应面可用 GPU；先确认矩阵能放进显存"]
        workers = max(1, logical - 2)
        if ram_gb:
            workers = min(workers, max(1, int(ram_gb // 4)))
        return "cpu-parallel", workers, ["没有可用 GPU 工具链，退回 CPU 多进程/多线程"]
    return "cpu-serial", 1, ["未给出问题形态；默认串行，先量测再决定并行/GPU"]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--problem", default="auto",
                    help="1d-pde | 2d-pde | sparse-lu | monte-carlo | pso | parameter-sweep | dense-la | auto")
    ap.add_argument("--batch", type=int, default=0, help="Monte Carlo/PSO 的样本或粒子数")
    args = ap.parse_args()

    physical, logical, ram_gb = _cpu()
    gpus, toolkits = _gpus()
    backend, workers, reasons = _recommend(
        args.problem, args.batch, gpus, toolkits, physical, logical, ram_gb)
    payload = {
        "cpu": {"physical": physical, "logical": logical, "ram_gb": ram_gb},
        "gpus": gpus,
        "gpu_toolkits": toolkits,
        "problem": args.problem,
        "batch": args.batch,
        "recommended_backend": backend,
        "workers": workers,
        "reasons": reasons,
        "note": "只读探测；GPU 不是默认目标。先跑缩比 CPU/GPU 基准，再决定是否重写内核。",
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
