# -*- coding: utf-8 -*-
"""去哪儿找 `claude` 可执行文件 —— **唯一的实现**，驱动与 `runtime/doctor.py` 共用。

为什么单开一个模块：若这段发现逻辑只长在 `lib/web/server.py` 里，
而 `runtime/doctor.py`（新机器上第一个该跑的自检）**压根不检查 claude** —— 它只看
Python 包与 xelatex/pandoc 这些外部工具。于是新机器上会出现"doctor 全绿、驱动却起不来"
这种最难查的组合：`server.py` 是在 **import 期**发现找不到 claude 就地退出的。

本模块**必须无副作用**（不建目录、不读 .env、不 print、不 sys.exit）：
  `doctor.py` 会 import 它，而 doctor 的 docstring 写死了
  "Read-only dependency check; never install packages or launch models"。
  同理它**不能** import `server.py`（那会拉起 FastAPI 并执行模块级副作用，
  仓库里所有 CLI 都守着这条）。
"""
import os
import shutil
import sys
from pathlib import Path

# 支持 claude 的四个编辑器；顺序只为可读，真正的择优是"按 mtime 取最新"
EXT_SUBDIRS = (".vscode/extensions",
               ".vscode-server/extensions",      # 远端 / WSL
               ".vscode-insiders/extensions",
               ".cursor/extensions")
# 兼容两种布局：新版扩展把二进制放 `resources/native-binary/`，旧版放扩展根目录。
# Linux/macOS 上没有 `.exe` 后缀，所以两个名字都试。
BIN_NAMES = ("claude.exe", "claude")
OVERRIDE_KEY = "WEBDRIVER_CLAUDE"


def search_dirs():
    """会去扫的扩展目录（不存在的也返回，好让报错说清"去过哪些地方找"）。"""
    home = Path.home()
    return [home / d for d in EXT_SUBDIRS]


def candidates():
    """扩展目录里所有**像 claude 的**可执行文件，按 mtime 新→旧。"""
    pats = []
    for ext in search_dirs():
        if not ext.is_dir():
            continue
        for n in BIN_NAMES:
            pats += list(ext.glob(f"anthropic.claude-code-*/resources/native-binary/{n}"))
            pats += list(ext.glob(f"anthropic.claude-code-*/{n}"))
    good = [p for p in pats if "vsctmp" not in str(p) and p.is_file()]
    return sorted(good, key=lambda p: p.stat().st_mtime, reverse=True)


def find_claude():
    """找到 claude(.exe) 就返回路径，找不到返回 `None`（**调用方负责说人话**）。

    三条路，按优先级：
      ① `WEBDRIVER_CLAUDE`（环境变量或 `.env` 里同名键）—— 显式指定，指哪用哪。
         指了个**不存在**的路径时返回 None，**不**回退到别处 —— 悄悄换一个更坑人
           （回归用例 `test_find_claude_has_an_explicit_override` 钉着这条）。
      ② 扩展目录（见 `search_dirs()`），按 mtime 取最新 —— 扩展自动更新会换目录名，
         所以**每次调用都要现取**，不能在模块级缓存住。
      ③ PATH 里的 `claude`。

    全程 `Path.home()` 推路径，**不写死任何人的家目录** —— 把某个人的
      家目录写进源码，换个人/换台机器直接找不到，而且报的是"请确认 VSCode 扩展已安装"，
      把"路径写死了"说成"你没装"（回归用例 `test_find_claude_has_an_explicit_override`
      会去 `server.py` 里断言这段实现不含某个家目录字面量）。
    """
    override = (os.environ.get(OVERRIDE_KEY) or "").strip()
    if override:
        p = Path(override)
        return p if p.exists() else None
    c = candidates()
    if c:
        return c[0]
    which = shutil.which("claude")
    return Path(which) if which else None


def explain():
    """一句话说清**找到没 / 走的哪条路 / 找不到时去哪儿找过了**。

    给两类调用方用：`server.py` 那句 import 期 SystemExit，与 `runtime/doctor.py` 的输出。
    光说"未找到 claude"会让用户去翻 `.env`，而真因常常是"这台机器压根没装 Claude Code"
    或"`WEBDRIVER_CLAUDE` 填错了、指着一个不存在的文件"。
    """
    override = (os.environ.get(OVERRIDE_KEY) or "").strip()
    found = find_claude()
    if found:
        if override:
            return f"claude = {found}（来自 {OVERRIDE_KEY}，指哪用哪）"
        return f"claude = {found}（由扩展目录/PATH 自动发现）"
    if override:
        return (f"未找到 claude：{OVERRIDE_KEY} 指向 {override!r}，但那个文件**不存在** —— "
                f"改对路径，或删掉这个键让它自动发现")
    tried = "、".join(str(d) for d in search_dirs())
    return (f"未找到 claude：扩展目录（{tried}）里没有，PATH 里也没有。"
            f"装 Claude Code（VSCode/Cursor 扩展，或独立 CLI），"
            f"或在 .env 里设 {OVERRIDE_KEY}=<claude 可执行文件的完整路径>")


def doctor_report():
    """给 `runtime/doctor.py` 用的结构化结果（纯函数，不打印）。"""
    found = find_claude()
    return {
        "status": "OK" if found else "MISSING",
        "path": str(found) if found else None,
        "source": (OVERRIDE_KEY if (os.environ.get(OVERRIDE_KEY) or "").strip()
                   else ("extension-dir" if found else None)),
        "searched": [str(d) for d in search_dirs()],
        "detail": explain(),
    }
