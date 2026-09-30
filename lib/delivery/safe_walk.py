# -*- coding: utf-8 -*-
"""安全递归遍历：**不跟随符号链接 / Windows 目录联结点**。

为什么单独成一个模块：镜像、暂存（`lib/web/server.py` 的 `_walk_tree`）与
收附件（`lib/delivery/core.py`）都要递归，就需要同一套判据 —— 各写一份迟早漂移。
放这里共用，**只有一处实现**。

判据是 reparse 属性位（`_is_reparse_point`）：`Path.is_symlink()` **抓不住** Windows 目录
联结点（对它返回 False），只有属性位对符号链接与联结点一视同仁。
"""
import os
import stat


def is_reparse_point(p):
    """这个路径是符号链接/联结点吗？（Windows 上判属性位；取不到就退回 `is_symlink`）"""
    try:
        st = os.lstat(str(p))
    except OSError:
        return True                       # 读不到的，当作"别进去"
    attr = getattr(st, "st_file_attributes", 0)
    if attr & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0):
        return True
    return stat.S_ISLNK(st.st_mode)


def walk_files(src, *, skip_names=("__pycache__",)):
    """递归产出 `(路径, 相对 src 的 posix 串)`。不跟随联结点/符号链接，不进入 `skip_names`。

    根自己若是联结点就**什么都不产**（调用方按"源里没东西"处理）—— 只查子项的话，
    它会被整体跟进（把外部内容拷进来）或整体跳过，两种后果都不对。
    """
    from pathlib import Path
    src = Path(src)
    if is_reparse_point(src):
        return
    stack = [src]
    while stack:
        cur = stack.pop()
        try:
            entries = sorted(cur.iterdir(), key=lambda p: p.name)
        except OSError:
            continue
        for p in entries:
            if p.name in skip_names:
                continue
            if is_reparse_point(p):
                continue
            if p.is_dir():
                stack.append(p)
            else:
                yield p, p.relative_to(src).as_posix()
