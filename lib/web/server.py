# -*- coding: utf-8 -*-
"""NewMathAgent Web 驱动：以 headless claude -p 逐阶段驱动 skill 链。
FastAPI + SSE；阶段编排 + 门禁回退；可复用 reports 断点续跑。
用法: python server.py [--port 8901]   （在 new math agent 根目录下启动）
"""
import asyncio, ctypes, hashlib, io, json, os, re, shutil, stat, subprocess, sys, threading, time, uuid
import webbrowser   # 整链跑完时把 ⑯ 的 demo 用系统默认浏览器打开（见 `_open_demo_page`）
from ctypes import wintypes
from urllib.parse import urlparse
from pathlib import Path
from datetime import datetime
from collections import deque
from workflow_quality import StageReceipts, atomic_json, fingerprint, read_verdict

import uvicorn
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.responses import (HTMLResponse, FileResponse, JSONResponse,
                               StreamingResponse)
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from lib.visualization.evidence import audit as audit_figures
from lib.publication.checks import audit as audit_publication
from lib.result_contract.core import audit as audit_results
import content_quality, workflow_quality
import upload_guard                      # 上传路径/体量守卫（纯函数，见 lib/web/upload_guard.py）
# 去哪儿找 claude 可执行文件 —— 实现单独一个模块，好让 `runtime/doctor.py` 共用（无副作用）
from claude_bin import find_claude, explain as explain_claude
from receipt_ledger import receipt_ledger_issues
from content_quality import (enforce as enforce_content, REQUIRED as CONTENT_CHECKS,
                             TARGETS as CONTENT_TARGETS, task_contract_issues,
                             fix_disposition_issues)

# ---------------- 项目自己的模型配置：`.env` ----------------
# 模型、地址、密钥来自项目根目录的 `.env`：启动时读进来塞进 `os.environ`，
# 子进程（每个阶段的 agent）自然继承。
#
# 为什么需要它：不读 `.env` 时，`_call()` 里 `env = os.environ.copy()` 起的 `claude -p`
# 只能拿**这台机器**上 Claude CLI 自己的登录与设置（`~/.claude/`）——换台机器/Runner
# 就跑不起来，而且"现在到底在用哪个模型、打哪个地址"在仓库里**看不见**。
# 有了 `.env`，配置**跟着这个仓库走**，且面板/日志里能看见（密钥打码）。
DOTENV = ROOT / ".env"
# 只认识这几个名字（Claude Code CLI 自己的变量名）—— 不另造一套别名，
# 免得"填了没生效"这种最难查的故障。
_DOTENV_KNOWN = ("ANTHROPIC_BASE_URL", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_API_KEY",
                 "ANTHROPIC_MODEL", "ANTHROPIC_SMALL_FAST_MODEL",
                 "ANTHROPIC_DEFAULT_HAIKU_MODEL", "ANTHROPIC_DEFAULT_SONNET_MODEL",
                 "ANTHROPIC_DEFAULT_OPUS_MODEL", "CLAUDE_CODE_SUBAGENT_MODEL",
                 # 出站代理策略，见下面「出站代理」那段
                 "FMA_API_PROXY", "FMA_NO_PROXY_EXTRA",
                 # claude 可执行文件的显式路径（不填就按 ~/.vscode 等目录动态找，见 _find_claude）
                 "WEBDRIVER_CLAUDE")


def _load_dotenv(path=None):
    """读项目根 `.env` 并**塞进 `os.environ`**。返回 (读到的键, 出问题的行)。

    规则刻意从简（不引第三方库）：
      · 一行一条 `KEY=VALUE`；`#` 起头的整行是注释；空行忽略；
      · 允许 `export KEY=VALUE`；值两侧成对的 `'` 或 `"` 会被剥掉；
      · 值里可以有 `=`（只按**第一个** `=` 切）；
      · **空值 = 没设**（`KEY=` 只是把那行摆出来，不会塞一个空串进环境）；
      · **不覆盖已存在的环境变量** —— 显式 `set` 的（或临时调试时 `$env:X=...`）优先，
        否则 `.env` 会把人当场设的值悄悄盖掉，那是最难查的一类故障；
      · 文件不存在 = 什么都不做（**不是错误**：有人就用机器配置跑）；
      · 格式坏的行（没有 `=`）跳过并记下来，不炸 —— 一行手滑不该让驱动起不来。
    """
    p = Path(path or DOTENV)
    got, bad = [], []
    try:
        text = p.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError):
        return got, bad
    for n, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export "):].lstrip()
        if "=" not in line:
            bad.append(f"第 {n} 行没有 `=`：{raw.strip()[:60]}")
            continue
        k, v = line.split("=", 1)
        k = k.strip()
        if v[:1].isspace() and v.lstrip().startswith("#"):
            # `KEY= # 说明` ⇒ **值是空的**（等号后先空白再井号 = 整段是注释）。
            # 判据必须看**strip 之前**：`KEY=#abc`（井号紧跟等号）是**值** —— 密钥/口令以 `#`
            #   开头是常见的，把它当注释会静默变成"没设"。这两条的区别只在等号后那一个空白。
            v = ""
        v = v.strip()
        if len(v) >= 2 and v[0] == v[-1] and v[0] in "'\"":
            v = v[1:-1]                      # 成对引号：里面的 `#` 是**内容**，不当注释
        else:
            # 未加引号的值：` #`（空白 + 井号）起是**行内注释**，切掉。
            #   不加这一步，`.env.example` 里那一批"取消注释就能用"的行会出错 ——
            #   例如 `# FMA_STALL_SILENT=300        # 判假死` 取消注释后，注释会被算进值
            #   ⇒ 数字解析失败退回默认（以为设了 300，其实没有）；
            #   更糟的是 `ANTHROPIC_MODEL=x # 主力模型` ⇒ 模型名带着注释去调用，直接失败且看不出原因。
            #   规则照 POSIX dotenv 惯例：`#` **只有前面有空白**时才算注释（`a#b` 是值本身）。
            v = re.split(r"\s+#", v, 1)[0].strip()
        if not k:
            bad.append(f"第 {n} 行的键是空的：{raw.strip()[:60]}")
            continue
        if not v:
            # 空值 = **没设**，不往环境里塞一个空字符串：
            #   `KEY=` 写在 `.env` 里只是"把这行显式摆出来"（`.env.example` 整个就是这形状），
            #   而塞进去的空串会让按 `"KEY" in env` 判存在的工具以为"设了但值是空的"。
            #   驱动自己那几处读的都是真值判断（`os.environ.get(k) or ""`），不受影响。
            continue
        if k in os.environ and os.environ[k]:
            continue                      # 已存在的优先（见上面的规则）
        os.environ[k] = v
        got.append(k)
    return got, bad


_DOTENV_KEYS, _DOTENV_BAD = _load_dotenv()


def _mask_key(v):
    # 只露头 4 位、尾 2 位 —— 够你确认"是不是那一把"，又不至于把密钥打进日志（日志会被翻）
    v = str(v or "")
    return (v[:4] + "…" + v[-2:]) if len(v) > 10 else ("（已设）" if v else "（未设）")


def _model_config_note():
    """给人看的一行：现在用的是哪套配置（**密钥打码**）。"""
    # 三种来源要分清：`.env` 在、但它每一条都被环境里已有的值挡回去时，
    #   不能报成"没有 .env"，否则日志会一直显示"没有 .env"，而文件明明在
    #   （VSCode 跑的子进程环境里就自带 ANTHROPIC_BASE_URL）。
    if _DOTENV_KEYS:
        src = f"项目 `.env`（{DOTENV.name}）"
    elif DOTENV.is_file():
        src = f"项目 `.env` 在，但里面的键环境里已有 ⇒ **以环境为准**"
    else:
        src = "机器上的 Claude CLI 配置（没有 .env）"
    parts = [f"ANTHROPIC_BASE_URL={os.environ.get('ANTHROPIC_BASE_URL') or '（未设，用 CLI 默认）'}",
             f"ANTHROPIC_MODEL={os.environ.get('ANTHROPIC_MODEL') or '（未设，用 CLI 默认）'}"]
    key = os.environ.get("ANTHROPIC_AUTH_TOKEN") or os.environ.get("ANTHROPIC_API_KEY")
    parts.append(f"密钥={_mask_key(key)}")
    return f"🧩 模型配置来源：{src}；" + "；".join(parts)


#: 配置页认的三件套（与 `.env.example`、`regression/test_local_decoupling.py` 同一份口径）
_MODEL_KEYS = ("ANTHROPIC_BASE_URL", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_MODEL")


def _model_config_status():
    """开屏配置页要的"配好没有"。**密钥只回打码值，绝不回明文。**

    判据只看**生效值**，不看文件：`.env` 只是一个来源，`:95-96` 的规则是"已存在的环境变量
      优先"（VSCode 集成终端就是带着 `ANTHROPIC_*` 起来的）。文件里写了、环境把它挡回去时，
      真实生效的**不是**文件那份 —— 所以"配好了"必须以 `os.environ` 为准，否则配置页会说
      "配好了"而实际用的是别的。
    """
    key = os.environ.get("ANTHROPIC_AUTH_TOKEN") or os.environ.get("ANTHROPIC_API_KEY")
    missing = [k for k in _MODEL_KEYS
               if not (key if k == "ANTHROPIC_AUTH_TOKEN" else os.environ.get(k))]
    return {"configured": not missing, "missing": missing,
            "base_url": os.environ.get("ANTHROPIC_BASE_URL") or "",
            "model": os.environ.get("ANTHROPIC_MODEL") or "",
            "has_key": bool(key), "key_masked": _mask_key(key),
            "dotenv_exists": DOTENV.is_file(),
            "blocked_by_env": bool(DOTENV.is_file() and not _DOTENV_KEYS),
            "note": _model_config_note()}


def _write_dotenv_keys(values):
    """更新 `.env` 里指定的几行，**其余行一字不动**（注释、`FMA_*` 旋钮、`WEBDRIVER_*` 都得留着）。

    `values[k] is None` = **不动这一项**（不重写、也不新加）。这是给"留空 = 不改"用的：
    面板上密钥是打码显示的，用户不改就不会重填，此时绝不能把原来那条有效值抹成空
    —— `_load_dotenv` 里空值等于没设（`:89-94`），写进去等于把密钥删了。

    三条硬边界（都是**改一个文件里唯一那份密钥**该有的谨慎）：
      ① **读不出来就抛**，绝不 `lines = []` 继续 —— 那会把整个 `.env` 截成三行、把别的配置
         静默删光，还回一句"已保存"。
      ② **原子写**：写同目录临时文件再 `os.replace`。`.env` 里是唯一一份密钥，写一半崩就没了。
      ③ **值里不许有换行/回车**：值会被原样拼成 `键=值`，一个换行就能在文件里**伪造出**任意
         配置键（能注入 `WEBDRIVER_CLAUDE=<任意 exe>`，下次启动 `_find_claude()` 指哪用哪）。
         键名同理（现在是硬编码三件套，防的是将来加键时手滑）。
    """
    for k, v in values.items():
        if v is None:
            continue
        # 判据必须与**读取端**一致：`_load_dotenv` 用 `text.splitlines()` 切行，而
        #   `str.splitlines()` 认的不止 `\r\n` —— 还有 `\x0b \x0c \x1c \x1d \x1e \x85
        #      `（只挡 `\r\n` 时，
        #   值里塞一个 `\x0c` 照样能在 .env 里伪造出 `WEBDRIVER_CLAUDE=…` 那样的独立键，
        #   而下次启动 `_find_claude()` 指哪用哪）。
        #   所以直接拿"切完之后还是不是一行"当判据，别自己列字符集 —— 以后读取端改口径，
        #   这里自动跟着走，不会再漂。
        if len(str(k).splitlines()) > 1 or len(str(v).splitlines()) > 1:
            raise ValueError(f"配置值不能包含换行：{k}")
    bom = False
    if DOTENV.is_file():
        raw = DOTENV.read_bytes()                                     # 见 ①：读不出来就让它抛
        bom = raw[:3] == b"\xef\xbb\xbf"
        lines = raw.decode("utf-8-sig").splitlines()
    else:
        lines = []
    done, out = set(), []
    for line in lines:
        s = line.strip()
        if not s or s.startswith("#"):          # 注释与空行原样留着（`# KEY=` 不算键）
            out.append(line)
            continue
        body = s[7:].strip() if s.lower().startswith("export ") else s
        k = body.split("=", 1)[0].strip() if "=" in body else ""
        if k in values and values[k] is not None and k not in done:
            out.append(f"{k}={values[k]}")
            done.add(k)
        else:
            out.append(line)
    for k, v in values.items():                  # 文件里没有的键，补到末尾
        if v is not None and k not in done:
            out.append(f"{k}={v}")
            done.add(k)
    text = "\n".join(out) + "\n"
    tmp = DOTENV.with_name(DOTENV.name + "." + uuid.uuid4().hex[:8] + ".tmp")
    # 原文件有 BOM 就带回去（`utf-8-sig` 读会把它吃掉，写的时候得自己补）
    tmp.write_bytes((("﻿" if bom else "") + text).encode("utf-8"))
    os.replace(tmp, DOTENV)                      # 见 ②：原子替换
    return sorted(done)


# ---------------- 出站代理：只把 **API 端点** 摘出代理 ----------------
# 目标：API 端点直连，其余（外网搜索等）照旧走系统/环境代理。
# 方向要记清：项目里**没有**任何"允许 7897 端口"的适配（7897 只出现在这段注释里）；
# 策略是**反过来的** —— 把 API 主机从代理里**摘出去**。
#
# 为什么要按主机摘代理 —— 卡在「谁读环境变量、谁读注册表」不一致：
#   · `claude -p`（Node/undici）**不读** Windows 系统代理（注册表 ProxyEnable=1、
#     ProxyServer=127.0.0.1:7897，Clash 的「系统代理」开关改的就是它），只读 HTTPS_PROXY
#     这类**环境变量** ⇒ 环境里没有就直连 ⇒ 梯子开不开都通。
#     在终端里手敲 claude 一直好使，就是因为走的是这条路，不是运气。
#   · Python（urllib/requests）**读**注册表：本机 `urllib.request.getproxies()` 会返回
#     `{'https': 'http://127.0.0.1:7897', ...}`（环境变量一个都没有）⇒ 梯子一关、7897 没人听，
#     就是 connection refused。驱动自己、以及阶段 agent 跑的 Python 脚本都在这条路上。
#   · `no_proxy` 环境变量对**两条路都有效**（Node 读它；Python 的 `proxy_bypass()` 拿它去拦
#     注册表来的代理）⇒ 正确做法是**只把 API 主机摘出代理**，外网搜索照旧走梯子。
#
# 两条实现约束：
#   ① 不许把厂商域名（如 `api.deepseek.com`）**硬编码**进来。端点由 `.env` 里的
#      `ANTHROPIC_BASE_URL` 显式配置，硬编码一个域名 = **换端点那天静默失效**
#      （新端点悄悄走梯子，梯子一关又是 connection refused）。要从配置推导。
#   ② 光改 claude 子进程那一次 `env` 拷贝不够 ⇒ **驱动自己跑的 Python 没被保护**（上面第二条）。
#      所以策略要写在模块级 `os.environ` 里，整棵进程树一致。
# 放模块级而不放 `__main__`：要覆盖"驱动 spawn 的 Python 工具"，就得改自身的 `os.environ`；
# 而 agent `from server import STAGES` 时跟着改一遍是**无害**的（只往 NO_PROXY 加主机）。

_PUBLIC_SUFFIX_SLD = {"co", "com", "net", "org", "gov", "edu", "ac", "mil"}
_FMA_PROXY_MODES = ("auto", "system", "off")


def _api_proxy_mode():
    """出站代理策略（`.env` 里的 `FMA_API_PROXY`）：

      · `auto`（默认）：**API 端点直连**，其余（外网搜索等）照旧走系统/环境代理；
      · `system`：一个字节都不改 —— 和你在终端里直接敲 `claude` 完全一致，梯子怎么设就怎么走；
      · `off`：`NO_PROXY=*`，**所有**出站都直连（没梯子、或不想让任何东西走代理时用）。
    """
    m = (os.environ.get("FMA_API_PROXY") or "auto").strip().lower()
    return m if m in _FMA_PROXY_MODES else "auto"


def _api_direct_hosts(base_url=None):
    """从 `ANTHROPIC_BASE_URL` 推出「该直连的主机」——**不写死任何厂商域名**。"""
    url = base_url if base_url is not None else os.environ.get("ANTHROPIC_BASE_URL", "")
    try:
        host = (urlparse(url or "").hostname or "").strip().lower()
    except ValueError:
        host = ""
    if not host:
        return []
    out = [host]
    parts = host.split(".")
    # 顺带把父域也摘掉（api.deepseek.com → .deepseek.com）：同一家的其它子域也不必绕代理。
    # 但要躲开 `com.cn` / `co.uk` 这类公共后缀 —— 否则会把整个顶级域都摘出去（太过头）。
    if (len(parts) >= 3 and parts[-1].isalpha()
            and not host.replace(".", "").isdigit()
            and parts[-2] not in _PUBLIC_SUFFIX_SLD):
        out.append("." + ".".join(parts[-2:]))
    return out


def _api_no_proxy_extra():
    """`FMA_NO_PROXY_EXTRA`：手填的额外直连主机（逗号/分号/空格分隔）。"""
    return [h.strip().lower() for h in re.split(r"[,;\s]+", os.environ.get("FMA_NO_PROXY_EXTRA", ""))
            if h.strip()]


def _proxy_policy_hosts(base_url=None):
    return _api_direct_hosts(base_url) + _api_no_proxy_extra()


def _apply_proxy_policy(env=None, base_url=None):
    """把「API 直连」写进 `NO_PROXY`/`no_proxy`（两个名字都写：Node 认大写的，urllib 两个都认）。

    幂等：重复调用不会把同一个主机堆两遍。`env=None` 时改的是 `os.environ` 本身。
    `base_url`：显式给一个端点（而不是读 `os.environ`）——「测试连接」要按**刚填、还没保存**
      的那个端点推直连主机，否则测的是**旧端点**的代理策略。
    返回本次**新增**的主机（日志用）。
    """
    e = os.environ if env is None else env
    mode = _api_proxy_mode()
    if mode == "system":
        return []
    if mode == "off":
        hosts = ["*"]
    else:
        hosts = _proxy_policy_hosts(base_url)
        if not hosts:
            return []
    base = {x.strip() for name in ("NO_PROXY", "no_proxy")
            for x in (e.get(name) or "").split(",") if x.strip()}
    added = [h for h in hosts if h not in base]      # 两个名字里都没有过，才算"本次新增"
    for name in ("NO_PROXY", "no_proxy"):
        cur = [x.strip() for x in (e.get(name) or "").split(",") if x.strip()]
        cur += [h for h in hosts if h not in cur]
        e[name] = ",".join(cur)
    return added


def _mask_proxy_url(v):
    """代理地址里可能带 `user:pass@`（公司代理常见）—— 日志会被翻，把凭据打掉（同 `_model_config_note`）。"""
    v = str(v or "")
    if "@" in v:
        pre, _, post = v.partition("@")
        scheme = pre.split("//")[0] + "//" if "//" in pre else ""
        return f"{scheme}***@{post}"
    return v


def _detected_proxy():
    """这台机器现在**有没有**东西在拦出站？环境变量优先，其次 Windows 注册表（Clash 改的是它）。"""
    for k in ("HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy", "ALL_PROXY", "all_proxy"):
        if os.environ.get(k):
            return f"环境变量 {k}={_mask_proxy_url(os.environ[k])}"
    if sys.platform == "win32":
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                r"Software\Microsoft\Windows\CurrentVersion\Internet Settings") as k:
                if winreg.QueryValueEx(k, "ProxyEnable")[0]:
                    return f"Windows 系统代理 {_mask_proxy_url(winreg.QueryValueEx(k, 'ProxyServer')[0])}"
        except (OSError, ImportError, IndexError):
            pass
    return ""


def _proxy_note():
    """给人看的一行：这一轮 API 到底走不走梯子。

    为什么值得单列一行：这类故障的症状是"梯子开着/关着时好时坏"，而原因藏在
    "谁读环境变量、谁读注册表"里 —— 日志里不写明，下次还得从零查一遍。
    """
    mode = _api_proxy_mode()
    det = _detected_proxy()
    tail = (f"；本机探测到 {det}，API 不走它（外网搜索仍走）" if det
            else "；本机没探测到任何代理，全是直连")
    if mode == "system":
        return f"🌐 网络：策略=system（一个字节都不改，完全跟随环境）{tail}"
    if mode == "off":
        return f"🌐 网络：策略=off（NO_PROXY=*，所有出站都直连）{tail}"
    hosts = _proxy_policy_hosts()
    if not hosts:
        return ("🌐 网络：策略=auto，但 `ANTHROPIC_BASE_URL` 没设（或没解析出主机）"
                "⇒ **没给任何主机摘代理**；要的就是这个就没事，不是的话填 `ANTHROPIC_BASE_URL` "
                f"或 `FMA_NO_PROXY_EXTRA`{tail}")
    src = "ANTHROPIC_BASE_URL" if _api_direct_hosts() else "FMA_NO_PROXY_EXTRA"
    return f"🌐 网络：策略=auto；API 直连名单 [{', '.join(hosts)}]（来自 {src}）{tail}"


_apply_proxy_policy()


def _find_claude():
    """动态发现 claude(.exe)。**实现在 `lib/web/claude_bin.py`**。

    为什么单独成一个模块：`runtime/doctor.py`（新机器上第一个该跑的自检）也要报 claude
    的情况，而本文件是在 **import 期**发现找不到就地退出的 ⇒ 分开实现会撞出"doctor 全绿、
    驱动却起不来"这种最难查的组合。共用同一份实现后，doctor 也能报出
    "去哪儿找过、为什么没找到"。

    这里保留这个名字：`_find_claude` 是对外契约（回归用例直接调 `server._find_claude`），
    且 `_call()` 每次 spawn 都现取一次（扩展更新会换目录名，缓存会过期）。
    """
    return find_claude()

CLAUDE = _find_claude()
if CLAUDE is None:
    raise SystemExit(explain_claude())
REPORTS = ROOT / "reports"; REPORTS.mkdir(exist_ok=True)
LOG_DIR = ROOT / "runtime"; LOG_DIR.mkdir(exist_ok=True)

MODEL = os.environ.get("WEBDRIVER_MODEL", "")          # 空=用 claude 默认（取 CLI 自己的配置）
PERMS = os.environ.get("WEBDRIVER_PERMS", "bypass")     # bypass|acceptEdits

# ---------------- 阶段链（与 skills/ 一致） ----------------
STAGES = [
    # ⓪ 读题：上传的原件交给 AI 读一遍、亮黄灯等人确认了才往下跑。
    #   插在**下标 0**，①…⑯ 的 id 与显示编号**一个都不动**（重排编号会牵连全仓引用）。
    #   **不给 gate**：门禁的 target 必须是严格前序（见 ⑧ 那段"⑦ 不能指自己"的注释），
    #      第 0 个阶段没有前序，配 gate 只会拿到一个点不动的推荐目标。
    #   它只在"`request/_inbox/` 里还有没确认的原件"时才亮灯（判据 `_intake_unconfirmed`）
    #   —— 所以既有的全链跑法（没有 inbox）行为一字不变。
    {"id": "intake", "name": "题目读取", "skill": "0Intake-readproblem",
     "report": "INTAKE_REPORT.md", "gate": None},
    {"id": "literature", "name": "文献定向",  "skill": "1Literature-orientation", "report": "LITERATURE_DIRECTION.md",   "gate": None},
    {"id": "analysis", "name": "建模设计",    "skill": "2Modeling-design",     "report": "ANALYSIS_MODELING_REPORT.md","gate": None},
    {"id": "review", "name": "建模评审门禁",      "skill": "3Modeling-review-gate",          "report": "MODELING_REVIEW_REPORT.md", "gate": "REVISE->analysis"},
    {"id": "code", "name": "编码计算",        "skill": "4Coding-and-computation",         "report": "RESULTS_REPORT.md",         "gate": None},
    # audit 排在 robustness **之前**：audit 只读 + 小脚本复核（便宜），robustness 要跑
    #   扰动/bootstrap（贵）。audit 审的是「这份结果可不可信」（泄漏/分析单位/样本量/标签口径），
    #   结果不可信时 robustness 在它上面做的所有扰动全是白做 —— 便宜的放前面先筛废品。
    #   关于 experiment 路由：audit 的 7 个必查项**全部**在 RESULT_CHECK_CATEGORY
    #     反推表里，所以 audit 上任何 failed 的 category 都会被掰回 analysis/code ——
    #     `TARGETS["experiment"]="robustness"` 在 audit 上**根本不可达**。
    #     换序的收益因此只有成本论那一条，与路由无关。守着这条事实的用例是
    #     regression/test_defect_fixtures.py 的
    #     `test_E_reviewer_category_is_overridden_by_check_id_at_audit`。
    {"id": "audit", "name": "结果可信度审计",       "skill": "5Result-credibility-audit",          "report": "RESULT_AUDIT_REPORT.md",    "gate": "NEEDS_FIX->code"},
    {"id": "robustness", "name": "稳健性",  "skill": "6Robustness",            "report": "ROBUSTNESS_REPORT.md",      "gate": None},
    {"id": "drawio", "name": "技术路线图",      "skill": "7Route-diagram",                "report": "DRAWIO_REPORT.md",          "gate": None},
    # 绘图门禁：⑦ 之后**所有图都在盘上了**（8 张数据图来自 ④，4 张非数据图来自 ⑦），
    #   这是最早能对**全集**做检查的位置。在这一步拦住，就不必让 ⑨⑩⑪⑫ 在注定被退回的
    #   图上接着干活；而 ⑫ 验收那条图闸门仍在（它管"成稿后图又被动过"的晚场）。
    #   失败只回 ⑦ —— 它的下标严格小于这里，所以 `_target_index` 合法（这正是它比
    #   "把 ⑦ 自己变成门禁"好的地方：门禁的 target 必须是**前序**阶段，⑦ 不能指自己）。
    #   ⑦ 若查明根子在数据图，按它自己的交回规则写 HANDBACK_REQUEST 交回 ④。
    {"id": "figreview", "name": "绘图门禁", "skill": "8Figure-gate", "report": "FIGURE_REVIEW_REPORT.md", "gate": "FAIL->drawio"},
    {"id": "write", "name": "论文撰写",       "skill": "9Paper-writing",               "report": "paper/main",                "gate": None},
    {"id": "mathproof", "name": "数学论证门禁",   "skill": "10Math-proof-gate",             "report": "MATH_PROOF_REPORT.md",      "gate": "REVISE->write"},
    {"id": "cross", "name": "跨问一致性",       "skill": "11Cross-question-check",         "report": "CROSS_QUESTION_REVIEW.md",  "gate": "FAIL->write"},
    {"id": "rubric", "name": "评分标终审",      "skill": "12Rubric-final",               "report": "RUBRIC_REVIEW.md",          "gate": "FAIL->fix"},
    # fix：按评分判词定点返修。**不是 write 的替代品** —— write 在 mathproof/cross 上的
    #   回退边一字未动；fix 只服务 rubric 一家，只做论文侧（措辞/结构/摘要/结论表述）。
    #   动手前须逐条复核判词属实，不属实的记 not_reproduced 不动稿。不带门禁：
    #   它本身就是门禁的产物；跑完由 ⑫↔⑬ 环路把判词交回 ⑫ 复评（见 `_back_to_judge`）。
    {"id": "fix", "name": "按评分判词返修",         "skill": "13Repair-by-rubric-verdict",                  "report": "FIX_REPORT.md",             "gate": None},
    # format 独占模板/排版层（`paper/_base/` 与 main.tex 导言区），写作者不碰。
    #   它排在**内容判据之后**：先把内容判据定稿，再排这一道 ~2h 的工序，
    #   否则每改一句措辞都要重排一次。它改过 `paper/` 之后那几个内容判官的**回执会失配，
    #   但那不算"判决过期"** —— 见 `_review_object_stale` 的例外与 `state["layout_superseded"]`
    #   （口径：版式改动不作废内容判据；收尾也不再重判它们）。
    #   它不带 gate —— 它的失败模式是「改不干净」，由它自己的编译 + 逐页视觉验收发现并继续修；
    #   真需要动内容时，由它写 HANDBACK_REQUEST.md 交回 write（驱动已支持）。
    {"id": "format", "name": "排版与版式",      "skill": "14Layout-and-format",                "report": "FORMAT_REPORT.md",          "gate": None},
    # verify 的默认回退目标是 14Layout-and-format 而不是 9Paper-writing：终验查出的多是
    #   版式/引用/编译/超页，那些是 ⑭ 的活（秒级），不该为此重跑整篇写作。措辞/结论类仍可由
    #   裁决的 target 指定回 write；图缺失由 category=diagram 路由到 7Route-diagram。
    {"id": "verify", "name": "验收",      "skill": "15Verification",               "report": "VERIFY_REPORT.md",          "gate": "FAIL->format"},
    # rubric：评委视角的**评分与合规终审**。四份评分标（适配性15维 / AI痕迹10维 /
    #   合规红线26条 / 官方四大项16维）逐项打分，产出「严重/中等/轻微」三级判词。
    #   它是唯一有**正向**出路的门禁：claim 类判词交给紧随其后的 13Repair-by-rubric-verdict 就地改写，
    #   不回退 write 重跑整篇（write 是小时级，为几句摘要措辞重写全篇不值当）。
    #   模型/数值/实现类判词仍回退各自的生产阶段 —— 措辞改不掉一个错的模型，
    #   那条约束由 content_quality.RUBRIC_FORWARD_CATEGORY 与反推表钉死。
    {"id": "demo", "name": "交互Demo",        "skill": "16Web-demo",               "report": "DEMO_REPORT.md",            "gate": None},
]

# **收尾不再对内容判官重判**（原 `RECHECK_STAGES` 复验循环已删）：⑩数学论证门禁 / ⑪跨问一致性
#   判的是**内容**，它们过了就是内容定稿；
#   ⑫评分标终审 / ⑬按评分判词返修 / ⑭排版与版式 之后只动措辞与版式。拿"文件字节变了"把内容
#   判官拉回来重判，等于**把打磨当成改内容**（每轮会多三次门禁复评、每次十几分钟，
#   而它们判的东西一个字没变）。
#   · ⑫ 的复评**没有丢**：那是 ⑫↔⑬ 环路的事（判词处理完立刻回 ⑫，见 `_back_to_judge`）。
#   · ⑮验收 排在 ⑭ 之后、⑯Demo 之前 ⇒ 它对着的一直是**正文**的最终稿。
#     一个已知的例外：⑯ 不再"只写 `demo/`"，它还会往 `paper_appendix/`
#       里补 demo 那一节（标题 + 图 A1 + 介绍）并重编 `附录A.pdf`。所以**附录**在 ⑮ 之后还会
#       变一次。这是可接受的：那一节是**新增的展示内容**，不改动任何已有推导/数值，与"版式打磨"
#       同一性质；而且 `附录A.pdf` 没有哈希绑定，不会让任何已通过的裁决失效。
#   · 谁在什么时候被打磨过，痕迹留在 `state["layout_superseded"]`（面板可见），需要时手动重跑。
# （原 SKIP_OPTIONAL 已删：全项目无读取方，且 7Route-diagram 早已接入正式链。）

# ---------------- 运行状态 ----------------
app = FastAPI(title="NewMathAgent Web Driver")
state = {"running": False, "stopping": False, "run_id": None, "cur": None,
         "log": deque(maxlen=4000),
         "stages": {s["id"]: "idle" for s in STAGES},
         "stage_t": {s["id"]: {"elapsed": 0.0, "start": None} for s in STAGES},
         "progress": {"done": 0, "total": len(STAGES)}, "rounds": {},
         "run_start": None, "elapsed_base": 0.0, "run_completed": False,
         "halt_gate": False, "halt_reason": "",
         # start_index：本轮 **从第几个阶段起跑**（`/api/start` 带 `from_stage` 时置）。
         # 一次性：`run_all` 读走就归零（与 seed_hints 同一范式），免得下一次点「开始全链」被陈旧起点带走。
         "start_index": 0,
         # ---- 人工决策（黄灯）----
         # pending：待决策上下文，前端全靠它渲染面板。None = 无待决策
         "pending": None,
         # retry_cap: sid → 本次生效的墙钟上限覆盖值（面板点「延长」时写）。run_all 绝不可清它
         "retry_cap": {},
         # seed_hints: sid → 决策续跑时注入给该阶段的 hint（一次性，用完清空）
         "seed_hints": {},
         # hint_src: sid → 该阶段**上一轮拿到的回执目录**（回退投递时记）。交回那条路上
         # 要用它回查"它被要求修的是什么"（见 `_borrowed_upstream_issues`）。
         # 不随 run_all 清：交回发生在**下一轮**（决策后才跑），清了就查不到了。
         "hint_src": {},
         # attempts: sid → 累计被执行了几次（跨决策累加，仅供面板显示）
         "attempts": {},
         # waived: sid → {digest, at, note} 「接受并披露」的机器可读留痕
         "waived": {},
         # force_retry: sid → 在超时黄灯上选了「取消并重试」，看门狗读到它才杀进程
         "force_retry": None,
         # last_tail: 最近一次失败阶段的原始输出尾巴，供 _halt 带进 pending
         "last_tail": "",
         # stale_instr: 已交付、但**做法要求**（SKILL/规范/驱动注入指令）在其后变过的阶段。
         # 它们不自动重跑（见 _input_split 的说明），但必须让人看得见 —— 面板上会显示
         # 「N 个阶段是按旧要求交付的」并提供「按新指令重跑」入口，否则就是静默放行。
         "stale_instr": set(),
         # adv_by_stage: sid → 该阶段裁决里的**轻微/可选项**（带成本估计）。它们不进返修，
         #   但要不要为它多跑一轮得看它们 —— 只躺在报告里等于看不见。
         "adv_by_stage": {},
         # issues_by_stage: sid → 该阶段裁决里**未解决的门禁判据**（`decision["issues"]`）。
         #   为什么要有它：这批东西只活在 `state["pending"]` 里 —— **黄灯一收就没了**
         #     （回退时它们被折进上游提示带走，此后没有任何地方按阶段看得到"这一关判了什么"）。
         #     存一份之后，阶段行上的建议角标既能看建议、也能看判据，且**判据还在**这件事本身就有信息量。
         #   口径与 `adv_by_stage` 对齐：门禁没过就留着、过了就撤。
         "issues_by_stage": {},
         # fix_required: 12Rubric-final 判词里 must/fatal 的 issue id，供 13Repair-by-rubric-verdict 交处置表时逐条对账。
         #   必须**在 rubric 那一关就地**存下：13Repair-by-rubric-verdict 一改 paper/，rubric 的 input_digest
         #     就变了，事后重读裁决只会读到 UNVERIFIED。
         "fix_required": [],
         # pause_to_halt: 按了「暂停」—— 从当前阶段停下后**转黄灯**，把出口留好。
         #   与「停止」（硬停、不给决策入口）是两件事，见 /api/pause 与 /api/stop。
         "pause_to_halt": False,
         # autopilot：**一键托管**。开着的时候驱动自己处理两类挂起：
         #   · `kind == "overtime"` ⇒ **自动延长**本次限时（不杀进程，任务继续跑）；
         #   · 有 `recommended` 回退目标 ⇒ **按它推荐的那个阶段自动回退**。
         #   其余挂起（没有可自动执行的动作）照旧留给人 —— 托管不是"无条件放行"。
         # `autopilot_armed`：本轮挂起后要不要在 `run_all` 收尾时落实（见 `_autopilot_fire`）。
         "autopilot": False, "autopilot_armed": False,
         # 托管**自动回退**的时刻表。**跨 run 累计**（`run_all` 刻意不清它）—— 每次回退都会
         #   起一条新链，而新链会清 `fix_rounds` ⇒ 各门禁自己的"最多 3 轮"挡不住跨 run 的循环
         #   （不设闸时曾 30 秒起 22 条链）。闸只能加在这里，见 `AUTOPILOT_SPIN_WINDOW`。
         #   闸拦的是**速率**不是**次数**：慢循环（一轮一小时、每轮都在真干活）与快自旋（门禁秒判
         #     失败、一轮几秒）**都是 3 次**，次数分不开这两者，却会把前者掐死。曾用次数闸把
         #     audit→code 挡住 3 次，而每一轮 ④ 都把被点名的那条**真修好了**（5 个 hard id 无一重复，
         #     每轮点名的项都被下一轮独立复验确认落地）。所以只留"窗口内回退过密"这一条。
         #   另外：**不许再按键分桶计数**。曾有一版 `auto_rollback_counts` 按 "sid->target" 分桶，
         #     从来没生效过 —— 写计数在 `_autopilot_fire` 里、`await _apply_decision(req)`
         #     **之后**才求键，而那一刻 `_redo_from` 已经把 `state["pending"]` 清成 None
         #     ⇒ 写进 `"None->code"`；判据读的却是 `"audit->code"` ⇒ 两个桶永不相等、`n >= 3`
         #     恒假，闸是死的。不按键分桶 ⇒ 这一类错不可能再犯。
         "auto_rollback_times": []}
_sub = []          # SSE 订阅者

@app.middleware("http")
async def no_store(request, call_next):
    """给页面/静态加 no-store（避免浏览器缓存旧 JS 导致按钮失效），并挡掉跨站写请求。

    为什么要挡：`multipart/form-data` 与 `urlencoded` 属于 CORS **simple request**，
    不触发预检，因此任意网页都能在本服务开着时向 127.0.0.1:8901 发 POST。
    带 `Origin: http://evil.example` 的 `POST /api/upload`（multipart）与
    `POST /api/problem-text` 都会被受理 —— 也就是可以把 `request/problem.md` 整体换掉，
    而链随后以 bypass 权限把题面喂给 agent。
    规则：**不带 Origin/Referer 的放行**（curl/CLI/脚本都不带），带了就必须是本机。
    """
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        origin = request.headers.get("origin") or request.headers.get("referer") or ""
        if origin and not re.match(r"^https?://(127\.0\.0\.1|localhost|\[::1\])(:\d+)?(/|$)",
                                   origin, re.I):
            return JSONResponse({"detail": "跨站请求被拒：Origin 不是本机"}, status_code=403)
    resp = await call_next(request)
    resp.headers["Cache-Control"] = "no-store"
    return resp
HANDBACK = REPORTS / "HANDBACK_REQUEST.md"

def emit(evt, data):
    msg = json.dumps({"evt": evt, "data": data}, ensure_ascii=False)
    for q in list(_sub):
        try: q.put_nowait(msg)
        except Exception: pass

def _stdout_shadows_the_log():
    """自检：本进程的 stdout 是不是**就指向** `runtime/web_run.log`？

    是的话，这个文件上就有**两个写者**：`log()` 用 `open("a")` 自己写，进程 stdout
      也往里写。stdout 是块缓冲的，冲下来时按它自己的 fd 位置落盘 —— 会把 `log()`
      刚追加的行**整段覆盖掉**。
      症状：文件前段全是 `log()` 的行，从某个偏移起全是 `INFO:` 行，分界点正是用
      `nohup … >> runtime/web_run.log 2>&1` 启动服务的时刻；同期 `web 就绪`/超时黄灯行
      全部消失。这个文件是排查问题时唯一的依据，丢了它等于事后无据可查。
      返回 True 表示检测到冲突（调用方负责打警告）。
    """
    try:
        import os
        logf = LOG_DIR / "web_run.log"
        if not logf.exists():
            return False
        a, b = os.stat(logf), os.fstat(1)
        return (a.st_dev, a.st_ino) == (b.st_dev, b.st_ino)
    except Exception:
        return False


def log(msg):
    line = f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
    state["log"].append(line)
    emit("log", line)
    # 写文件必须**留痕**，不能静默丢。
    #   症状：`runtime/web_run.log` 里 `log()` 写的行会出现成段缺失（`web 就绪`、那一刻起的
    #   超时黄灯行都不在文件里，而同期的 🧹 / 暂停行在），而同样的代码在 `python -c` 进程里
    #   写同一个文件又是好的 —— 原因见 `_stdout_shadows_the_log`：同一文件被两个写者覆盖。
    #   不能写成 `open(…).write(…)`：那靠**临时对象被 refcount 回收时 close** 来落盘，
    #   失败路径既不留痕也不上抛（写得进写不进，调用方看不出来）。
    #   这个文件是排查问题的唯一依据，丢了它等于事后无据可查。
    #   所以：显式 `with`（保证 close/flush）+ 失败记进 `state["log_write_errors"]`
    #   （面板 `/api/state` 能看到），并原样打给 stdout。
    try:
        with (LOG_DIR / "web_run.log").open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception as exc:
        err = f"{datetime.now().strftime('%H:%M:%S')} {type(exc).__name__}: {exc}"
        errs = state.setdefault("log_write_errors", [])
        errs.append(err[:200])
        del errs[:-20]                      # 只留最近 20 条
        try:
            print(f"⚠️ 日志写文件失败：{err}", flush=True)
        except Exception:
            pass

def prompt_for(stage, first):
    sid, skill, rep = stage["id"], stage["skill"], stage["report"]
    base = f"""你在工作区 {ROOT} 执行「NewMathAgent」建模工作流。
先读取工作区根 CLAUDE.md 了解阶段链与产物契约（阶段清单见 docs/STAGE_CHAIN.md），再打开 skills/{skill}/SKILL.md，按其全部要求完成「{sid}」阶段。
只做该阶段，不要跳级、不要动其它阶段的产出。完成后按该 SKILL.md 要求写报告。
输入契约（若存在）来自 reports/ 下前序报告；README/CLAUDE.md 里有每个报告含义。"""
    # 这里不再有「第 N 轮评审」提示：`MAX_ATTEMPTS_PER_STAGE=1` 之后调用点传的 attempt 恒为 1
    #   （除非环境类错误重试），而且它把 attempt 当"轮次"，语义也不对。真要按轮次提示，
    #   数据源是 state["rounds"]；而门禁回执已经通过 _save_feedback 落盘并由 seed_hint 送达，
    #   不缺这一句。
    if sid == "write" and (REPORTS / "RESULT_AUDIT_REPORT.md").exists():
        # audit 可能给出 REVISE_CLAIM / 写作红线：写论文前必须读 audit 报告并按其"写作红线/§结论表述"落实
        base += ("\n\n注意：reports/RESULT_AUDIT_REPORT.md 是 5Result-credibility-audit 审计报告。若其整题结论为 REVISE_CLAIM 或含"
                 "「写作红线/须如实表述/不得夸大/须明示」等条目，写论文时必须逐条落实到对应结论表述里"
                 "（如 f5 语义、判据代理、同义反复断言改写、模型假设披露），不得把需修正的表述原样写进论文。")
    if sid == "write" and (REPORTS / "MATH_PROOF_REPORT.md").exists():
        # mathproof REVISE 回退：成稿被数学论证门禁拦下 → 按修改清单补推导/降级，不推倒整篇
        base += ("\n\n注意：reports/MATH_PROOF_REPORT.md 是 10Math-proof-gate 数学论证门禁回执。若其「整题门禁裁决：REVISE」，"
                 "请逐条按其中「修改清单」修订论文：对需补推导的断言在对应小节补等式级推导（显式写所用前提；"
                 "依赖整周期/均匀加权等理想化的结论补一致余项上界，或把『恒等于零』改称『有界可忽略』）；"
                 "对需降级的断言按清单建议措辞改写（删去或替换『定理|证明|命题』字样，改称数值观测/经验断言并如实披露）。"
                 "数值仿真/合成谱只作推导后的一致性校验，不得充当证明。修改清单给出的可替换句/式必须逐字采纳或写成逐字等价的 LaTeX，"
                 "禁止意译重述（意译是此前引入斜率写反等新错误的根源）；只改动 M-清单列出的文件/行，不重写其它小节。"
                 "改完自检镜像一致性：命题正文/图注/摘要/后文引用/代码回归的斜率、系数、符号、方向、量级须与修复后方程自洽（修 A 不许引 B 翻转反转），"
                 "定量归因不靠放宽参数凑界。改完重编译 paper/main.pdf；保留其余正确内容，不推倒重写。")
    if sid == "analysis" and (REPORTS / "MODELING_REVIEW_REPORT.md").exists():
        # REVISE 回退重做建模：必须按评审回执修订，不能从零盲写
        base += ("\n\n注意：reports/MODELING_REVIEW_REPORT.md 是 4review 门禁的上一轮评审回执。"
                 "若其裁决为 REVISE，请逐项按其中「修改清单」修订你这份建模报告（修正数学错误、补口径），"
                 "并更新版本号与修订历史说明如何吸收回执；保留正确的主干，不要从零重写整套框架。")
    if sid == "analysis" and (ROOT / "config/content_quality.json").exists():
        # content-quality 契约：题意→模型 映射必须在建模阶段落盘，否则后续门禁全部 NEEDS_FIX→analysis
        base += ("\n\n本工作区启用了 content-quality（config/content_quality.json 存在）。"
                 "除建模报告外，**必须另写 reports/TASK_CONTRACT.json**，格式与逐字锚点要求见 docs/CONTENT_QUALITY.md「题意契约」"
                 "及 3analysis SKILL 的 TASK_CONTRACT 说明：覆盖题面每条硬条件/交付要求，"
                 "source.quote 为 request/ 下文件原样文本，model_anchor.quote 为本报告原文，"
                 "source_semantics/model_semantics 的 quantifier/scope/unit/time_reference 如实对照且一致。"
                 "题面『每年相对 2023 ±5%』是固定基期波动而非逐年连乘；『所有土地/全部面积』不得弱化为『种过即可/发生过一次』。"
                 "写完后自测 quotes 能在对应文件中逐字命中（子串匹配）。")
    if sid in ("code", "robustness"):
        # 【方法标记】纪律（_references/stage_discipline.md 第四节）要求凡落盘到
        # code/outputs/ 的中间产物都写同名 .meta.json，并把「驱动注入的 code/ 指纹」抄进
        # `_code_fp`，好让「改了脚本」这一最常见的方法变更在**产物层可机器比对**。
        # 这里必须真把 `_code_fp()` 注入 prompt：以前只定义了函数却没注入，纪律文档与实现是断的，
        #   `.meta.json` 里那个字段无从填写。
        base += (f"\n\n【方法标记】当前 code/ 目录指纹：`{_code_fp()}`。"
                 "凡落盘到 `code/outputs/` 的中间产物，必须同时写一个同名 `.meta.json`，"
                 "把上面这个值**原样**抄进 `_code_fp` 字段（连同 `_method` 与 `_params`）。"
                 "重跑时先扫 `code/outputs/*.meta.json` 逐项比对：方法与参数都一致才可复用，"
                 "不一致的必须重算并标注「作废旧产物（方法变更：A → B）」——"
                 "不得因为「文件在、名字对」就复用。口径见 stage_discipline.md 第四节。")
    # 这里没有 `_audit_needsfix_current.md` 分支：全项目**没有任何代码或技能写这个文件**，
    #   永远不触发。「audit NEEDS_FIX → code」的实际通道是 _save_feedback() + rollback seed_hint。

    if stage.get("gate"):
        digest = _input_digest(stage)
        verdict = Path(rep).with_suffix(".verdict.json").name
        example = {"schema_version": 1, "stage": sid, "input_digest": digest,
                   "status": "UNVERIFIED", "issues": []}
        if (ROOT / "config/content_quality.json").exists():
            example["schema_version"] = 2
            example["checks"] = []
            base += ("\n先读取 docs/CONTENT_QUALITY.md。逐项核对题面、模型、实现与成稿；"
                     "前序审查PASS不免除题意复查。每项问题填写category与check_ids；"
                     "题意/模型/实现/实验缺陷不能通过写入局限变成措辞问题。"
                     f"本阶段必查ID：{json.dumps(CONTENT_CHECKS.get(sid, []))}。"
                     "checks每项含id、status(passed/failed/not_applicable)、reason、"
                     "evidence数组（每项file为相对路径、quote为文件中原样存在的文本）。"
                     "不适用也需依据；失败项必须关联具体修复issue。")
        base += ("\n\nWeb 驱动裁决协议（补充技能中的报告格式）：完成 Markdown 审查报告后，另写 "
                 f"reports/{verdict}，JSON 结构为 {json.dumps(example, ensure_ascii=False)}。"
                 "status 必须按证据填写 PASS/APPROVED/CLEAN/FAIL/REVISE/REVISE_SOFT/REVISE_HARD/"
                 "NEEDS_FIX/REVISE_CLAIM/UNVERIFIED 之一。未执行检查不得当作通过；未完成必要检查用 UNVERIFIED。"
                 "每个尚未解决问题须有 id、severity(hard/soft/info)、evidence、fix、recheck 字符串；"
                 "全部问题解决才可 PASS，不能以重试耗尽为由放行。可选 target 指定需要返修的前序阶段 id。"
                 # `fix` 写的是**要求**、不是范文：
                 #   门禁判词里若写出整句现成措辞（例如「…加速约 2.27 倍（对照档）…0.889 倍（主档）」），
                 #   ⑨ 会逐字照抄进摘要 —— 而「（…档）」正是 9Paper-writing 明令禁止的
                 #   括注形态（硬判据④）。根因：门禁只读 CONTENT_QUALITY.md、**不受写作规范约束**，
                 #   于是"判词教出来的措辞"能一路漏过写作侧的机械检查。
                 "★ `fix` 写的是**要求**（该改成什么事实、什么口径），**不是给下游抄的成品句**："
                 "不要为了示范而写出整句现成措辞；确需举例时，示例里**不许**出现写作规范明令禁止的形态"
                 "（括注补充、引号、以及「…档」这类限定小句）—— 实测「（对照档）」「（主档）」"
                 "就是这么被照抄进摘要的。落地措辞一律服从 skills/9Paper-writing 的写作规范，"
                 "由该阶段自己决定怎么表达；你只需在 recheck 里写清**核查判据**。"
                 "本阶段只审查，不修改被审查的代码、论文或上游报告（包括追加 APPROVED 标记）；"
                 "input_digest 原样抄写，不得自行更新以掩盖审核期间的输入变更。")
    log(f"启动阶段 {sid}: claude -p ...")
    return base

# （原 TOOL_STAGES 已删：定义后从未被读取，「驱动层硬 ReAct」并不存在。）

def _artifact_ok(stage):
    rep = stage["report"]
    m = REPORTS / rep if not rep.startswith("paper") else (ROOT / "paper" / "main.pdf")
    if not m.exists(): return False
    if rep == "RESULTS_REPORT.md":
        # 编码阶段要求：结果报告 + code/ 非空
        return m.stat().st_size > 200 and (ROOT / "code").exists() and any((ROOT / "code").iterdir())
    return m.stat().st_size > 80


def _receipt_store():
    return StageReceipts(LOG_DIR / "quality" / "stages.json")


def _source_digest():
    """「题目本身」的摘要 —— 只含**题目给的事实**。

    `plan.md` **不在**这里：它是 ① 文献定向（`0Start-mathmodel`）
      **自己写的产出**（`skills/0Start-mathmodel/SKILL.md` 明写「生成/更新 plan.md」），
      不能被当成题目输入。把它算进来的后果四连：某一轮之后 `plan.md` 出现或内容变化 ⇒ 下一次点「开始全链」
      就被判成「换题」⇒ ① 刚打包好的 `提交作品/最新作品` 被**整目录改名归档**、指针清空；
      ② `各阶段产物/最新产物` 同样被归档清空；③ 工作区原件（reports/code/…）全搬进 cache；
      ④ `_invalidate_from(0)` 把**全部**回执照废 ⇒ 整链从 ① 重跑（④ 是小时级）。
      而题目根本没换 —— 「重启/再点一次就整链重跑」的诡异感有一半来自这里。

    改了 `plan.md` 仍然**会**让读它的阶段失效 —— 那由 `_input_split` 的 artifacts 半份管
    （`art` 里保留着 `plan.md`），作用域精确，不再顺带清空提交件。
    """
    return fingerprint(ROOT, ["request", "data"])


def _prepare_workspace():
    """A new problem/input set cannot inherit generated files from the previous one."""
    path = LOG_DIR / "quality" / "workspace.json"
    digest = _source_digest()
    try:
        previous = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        previous = {}
    if not isinstance(previous, dict) or previous.get("source_digest") != digest:
        # 换题 = 归档两个「最新」指针（`提交作品/最新作品`、`各阶段产物/最新产物`）。
        #   题目标识必须取**上一轮记下的那个**，不能用当前配置 —— `/api/start` 是
        #   **先落盘新 problem_id、再起链**的，用当前配置会把旧题的产物装进新题的名字里
        #   （2026B_… 装 2026A 的东西）。
        # 记录值优先，旧文件没有该字段时退到面板配置
        # （否则**第一次**轮转的归档名只剩时间戳，题目标识在磁盘上哪一处都没体现）。
        old_pid = str(previous.get("problem_id") or _delivery_config()["problem_id"] or "")
        info = _rotate_pointers(reason="输入已变更（换题）", problem_id=old_pid)
        # 轮转**在搬源之前**：轮转失败会抛 RotationBlocked，此时工作区原件一件未动、
        #   还能原地救人；顺序反过来的话源已搬走而归档又没成。落点跟着本轮归档名走，
        #   于是 cache 里的「工作区原件」与两个「最新」归档**同名**，从 cache 里一眼对得上。
        RELS = ["reports", "code", "results", "figures", "paper", "demo",
                "paper_appendix", "运行说明.md"]
        _stash_paths(RELS, dest_root=_cache_dir() / info["name"] / "工作区原件")
        # 返修回执也必须搬走（与 `_redo_from` 的 start_i==0 分支同一处置）：
        #   `receipt_ledger_issues()` 读 `runtime/quality/feedback/` 是**无 run_id 过滤的
        #   全目录 glob**，残留一条上一题的 `gate_decision.json` 就会让新一轮 ② 建模设计
        #   **必然**挂在「缺返修台账」自检上 —— 而且那条提示是**假事实**（本轮根本没收到
        #   回执），「再试一次」也出不来，只有回退到 ① 才顺带清掉；不搬走就会每次换题
        #   都在第 2 步白亮一次黄灯。
        _stash_paths(["runtime/quality/feedback"],
                     dest_root=_cache_dir() / info["name"] / "回执")
        # 它与 RELS 是**同一步**要搬的两批（见上一段），搬不动同样会让
        #   新一轮 ② 挂在假台账上 —— 所以它也要进 stuck 判据。
        stuck = [r for r in RELS + ["runtime/quality/feedback"] if _has_content(ROOT / r)]
        if stuck:
            # 换题的全部意义就是「新题不许继承旧题的产物」。搬不走就**不能往下跑**：
            #   否则新题会在上一题的 reports/paper/code 上面跑，而回执紧接着就被
            #   `_invalidate_from(0)` 清空 ⇒ 没有任何人会发现问题（跨盘搬不动时
            #   会 8/8 一件都没搬走，链却照常往下跑，还 log「已归档」）。
            #   此刻两个「最新」**已经归档**了；但 `rotate_pointer` 对**空指针**返回 None，
            #   所以重试只会重建空骨架、**不会产出第二份归档** —— 关掉占用的程序再按「开始全链」即可。
            raise RotationBlocked(
                f"工作区原件没能全部搬走：{stuck} —— 关掉占用它们的程序"
                f"（Acrobat / Excel / 编辑器）后重试。两个「最新」已归档到 {info['name']}/，"
                f"重试不会重复归档。")
        REPORTS.mkdir(exist_ok=True)
        _invalidate_from(0)
        atomic_json(path, {"source_digest": digest, "run_id": state["run_id"],
                           "problem_id": _delivery_config()["problem_id"]})
        log("首次建立版本记录或输入已变更：两个「最新」已归档，当前轮使用独立输入版本。")
    elif not str(previous.get("problem_id") or "").strip():
        # 旧版 workspace.json 只有 source_digest/run_id。
        #   在这里补记一次题目标识，否则**手动归档**与下一次自动轮转都会拿到空标识 ——
        #   归档名只剩时间戳，与既有 `2026A_…` 的命名及「提交件归档 / 阶段产物归档 /
        #   工作区原件 三处同名」那条对账约定都不符。
        pid = _delivery_config()["problem_id"]
        if pid:
            atomic_json(path, {**previous, "problem_id": pid})


def _canon(value, code_type):
    """常量的规范化文本表示：集合/字典按排序输出，避免 PYTHONHASHSEED 导致的跨进程顺序漂移。"""
    if isinstance(value, code_type):
        return _code_fingerprint(value)
    if isinstance(value, (set, frozenset)):
        return "{" + ",".join(sorted(_canon(v, code_type) for v in value)) + "}"
    if isinstance(value, dict):
        return "{" + ",".join(f"{_canon(k, code_type)}:{_canon(v, code_type)}"
                              for k, v in sorted(value.items(), key=lambda kv: repr(kv[0]))) + "}"
    if isinstance(value, (list, tuple)):
        return "[" + ",".join(_canon(v, code_type) for v in value) + "]"
    return repr(value)


def _code_fingerprint(code):
    """对已加载的 code 对象取指纹（递归包含常量里的嵌套 code；常量表示规范化）。"""
    h = hashlib.sha256()
    h.update(code.co_code)
    h.update(repr(code.co_names).encode("utf-8"))
    h.update(repr(code.co_varnames).encode("utf-8"))
    parts = [_canon(const, type(code)) for const in code.co_consts]
    h.update("|".join(parts).encode("utf-8"))
    return h.hexdigest()


def _module_fingerprint(mod):
    """模块内**已加载**函数的指纹。不读磁盘——服务无热重载，磁盘改动在重启前并未生效。"""
    h = hashlib.sha256()
    for name, obj in sorted(vars(mod).items()):
        code = getattr(obj, "__code__", None)
        if code is not None and getattr(obj, "__module__", "") == mod.__name__:
            h.update(name.encode("utf-8"))
            h.update(_code_fingerprint(code).encode("utf-8"))
    return h.hexdigest()


def _prompt_fingerprint():
    """发给 agent 的注入指令指纹——取**已加载**的 prompt_for（进程内真正会被交付的那份）。

    不能读磁盘源码：边跑边改文件会让指纹变化、但交付的仍是旧函数，从而写出"已按新指令执行"
    的假回执。改盘后重启，指纹才变 → 该阶段失效并重跑。
    """
    return _code_fingerprint(prompt_for.__code__)[:12]


def _gate_logic_fingerprint():
    """门禁裁决逻辑指纹——同样取已加载模块（理由同上）。"""
    return (_module_fingerprint(content_quality) + _module_fingerprint(workflow_quality))[:12]


# 库/规范 → **真正依赖它的阶段**。为什么要有这张表：
#
# 不能用 `if index >= at("code"): ins += ["visualization", "result_contract", ...]`
# 这样的 blanket（"④ 及之后一律打包给"）：改一行画图库（`lib/visualization/*`）
# ⇒ **每个下游阶段一起失效**，包括只审数值/口径/泄漏的 ⑤。这条 blanket 必须拆。
#
# 代价恰好落在最不该的地方：④⑥ 这类小时级生产阶段有 `stale-instr` 宽待保着，
# 而门禁**重判要真花时间**（⑤ 一次 163.7 min）。
#
# 门禁现在也**只标记不重跑了**（见 `_input_split`）⇒ 加一条真依赖的代价
#   从"163 分钟"降成"面板上一行蓝条"。这个不对称消失之后，就该往"真"的方向靠 ——
#   漏一条的代价（拿着旧判据静默判过）一点没变，多一条的代价却没了。
#
# 表的依据 = **会话原始记录里的每一次工具调用**（`tmp/deps_classify.py` 读
# `~/.claude/projects/<本工作区>/*.jsonl`，**含 PowerShell/Grep/Glob**）。
#   **别用 `runtime/web_run.log` 当依据**：日志渲染器有个**工具名白名单**，
#      只记 Read/Write/Edit/WebSearch/WebFetch/Task 七个名字 ⇒ `PowerShell` 的调用
#      **一条都不进日志**（白名单已删，但按旧日志挖出来的结论是残的）。
#   按完整记录重挖 + 分类（`tmp/deps_classify.py`：`Get-Item`/`Test-Path`/列目录这类
#   **只探文件**的不算，只算真读了内容 / 真跑了那个模块）——
#     ⑤ 结果可信度审计：`visualization` **5 次**（`& $py -m lib.visualization audit` 真在跑它）、
#        `result_contract` 8 次
#     ⑥ 稳健性：`visualization` 1 次、`result_contract` 4 次（`-m lib.result_contract audit/validate`）
#     ⑭ 排版与版式：`result_contract` 1 次（`Select-String lib/result_contract/*.py` 真读）
#     ⑦ 技术路线图：`config/result_contract.json` 1 次（python 里真的 open 了它）
#   ⇒ 按日志挖出来的"0 命中 ⇒ 摘"有三条是错的（⑤ 的 `visualization`、⑥ 的两条都在
#     那三条里）—— 根因就是白名单漏记：它们**全是经 PowerShell 用的**。
#
# 两条纪律：
#   ① **没有运行证据的阶段保守给全**（⑬验收/⑭评分标/⑮返修/⑯Demo 等）。给多了只是多跑
#      一轮；给少了会让阶段**漏掉真变化** —— 后者危险得多。
#   ② 只在**有足够访问量且零命中**时才敢摘（本表用的门槛是 ≥50 次记录访问）。样本太小的
#      "没读到"分不清"不需要"还是"这次恰好没读"。摘错了的代价同上。
# 改动这张表后，跑一次 `tmp/deps_classify.py`（读**会话原始记录**，不是日志）与表对照
# —— 那是它的对账单。从 `runtime/web_run.log` 挖的旧脚本已删：日志只记七个工具名，
# 拿它当依据会**系统性漏掉经 PowerShell 的访问**，那样会摘错条。
# `results/` 下**派生的登记/校验件**：**两侧都不进指纹** —— 与 `figures/` 同一条理由
# （见 `_output_digest` 里那段论证）：负责它们的机制是 `python -m lib.result_contract audit`
# （驱动在 `_gate_decision` 里对 ⑤/⑬ 直接跑它），不是指纹。
#
# 为什么要把它们排除：
#   ⑤ 的判词会要求"重新 build"结构化结果，并且同时写着"**先复用已保存结果，
#   不默认重跑优化器**"。可 `results/registry.json` 住在 ④ 的输入与产物指纹里 ⇒
#   一执行那句判词，④ 的哈希就失配 ⇒ **小时级的 ④ 从零重跑**，两句话自相矛盾。
#   更糟的是 ④ 一旦被启动，它的回执就地作废（不可逆），修好指纹也回不去了。
#   交付物 `result1–4.xlsx` 照旧进指纹 —— 它们是真交付，变了就该让下游失效。
_DERIVED_RESULT_FILES = ("results/registry.json", "results/validation.json",
                         "results/metric-spec.json", "results/validation-spec.json")

# 内容 ↔ 版式 的解耦（见 `_input_split` 末尾那段注释）：
#   `_LAYOUT_OWNED_PATHS` = `14Layout-and-format` 独占或由它产出的路径（导言区、编译产物、
#   版式报告与提交清单）；`_CONTENT_SIDE_STAGES` = 只认内容的那几个阶段。
#   两者只在 `_input_split` 的 artifacts 指纹里用 —— **不是**把它们从产物里删掉，
#   只是"它们变了不算内容变了"。13 真改了 `paper/sections/` 时，10/11/12 仍会失效。
_LAYOUT_OWNED_PATHS = ("paper/_base", "paper/math-style.tex", "paper/main.pdf",
                       # 表里凡是 `paper/**/*.pdf` 与 `paper/main.<ext>` 的条目其实**永远不会生效**
                       #    —— `workflow_quality._is_paper_build_output` 已经把所有编译产物排除在
                       #    指纹之外了。留着是**声明"这些归 ⑭"**（人读），不是运行需要；
                       #    真起作用的只有 `paper/_base`、`paper/math-style.tex`、
                       #    `reports/FORMAT_REPORT.md`、`reports/SUBMISSION_MANIFEST.json`、`运行说明.md` 这几条。
                       "paper/page-map.json", "paper/main.aux", "paper/main.log",
                       "paper/main.out", "paper/texput.log", "reports/FORMAT_REPORT.md",
                       "reports/SUBMISSION_MANIFEST.json", "运行说明.md")
_CONTENT_SIDE_STAGES = {"mathproof", "cross", "rubric", "fix"}

# ⑫评分标终审 ↔ ⑬按评分判词返修 的**自动来回修上限**：
#   ⑬ 只是 ⑫ 的工具步骤 —— ⑫ 变绿则 ⑬ 自动也绿（`_rubric_hands_off()` 直接跳过它）；
#   ⑫ 没过则把判词交给 ⑬ 就地改写，**改完回到 ⑫ 复评**，最多来回这么多轮；
#   到顶还不过 ⇒ 转黄灯问人（不再自动回 13）。轮数按门禁记在 `state["fix_rounds"]`，每轮 run_all 清零。
RUBRIC_FIX_MAX_ROUNDS = 3
# 哪些门禁可以走「论文侧判词 ⇒ 交 ⑬ 定点改写 ⇒ 改完回本门禁复评」这条正向路。
#   · ⑫ 评分标终审：命中 claim 类判词时亮黄灯，等 ⑬ 处理后再返回 ⑫ 复评；
#   · ⑮ 验收：与 ⑫ 同理（判完给 ⑬ 改，改完直接跳回 ⑮ 再检）。⑮ 自己会重新编译
#     （SKILL 的 Step 7/8），所以跳过 ⑭ 不会留下一份旧 PDF；真把版式弄坏了，⑮ 会判出
#     presentation 类判词、目标正是 ⑭，那时才去跑它 —— 自纠正。
#   · ⑪ 跨问一致性：非走这条路不可。⑪ 的纯 claim 判词本该走
#     `hints["write"]`（把清单塞给 ⑨），可 ⑨ 排在 ⑪ **之前** ⇒ 那句是死代码，
#     于是它落到 `_halt("REVISE_CLAIM 缺少后续写作阶段", kind="driver")` ——
#     不但停下，还因为 kind=driver 把「接受并披露」那个出口一起收掉了。
#     而它的判词全是文稿措辞，⑬ 正是干这个的；⑬ 在 ⑪ 之后 ⇒ 顺理成章。
_FIX_HANDOFF_JUDGES = {"rubric", "cross", "verify"}
# 一键托管**自动回退**的「自旋闸」。
#   为什么必须有闸：托管看到"有推荐回退目标"就回退，而**每一次回退都会起一条新的 `run_all`**，
#     新链开头把 `state["fix_rounds"]`（⑫/⑮ 的"最多 3 轮"）清空 ⇒ **上限永远从 0 重数**。
#     （⑮ 恒判 REVISE_CLAIM + 托管开：30 秒起了 **22 条链、194 次 agent 调用**仍在继续，
#     每 cycle 是 1×⑭（~2h）+ 4×⑮（89min/次）+ 3×⑬ —— 无人值守会一直烧下去。）
#   而且**不止 ⑮**：凡是 `_default_repair_target` 指向合法前序的门禁（review→analysis、
#     audit→code、mathproof→write、cross→write、verify→format、figreview→drawio）都中招，
#     **普通失败（非 claim、根本没有轮数计数器）也一样循环**（review 恒判 NEEDS_FIX 时
#     12 秒起了 75 条链）。⑫ 是唯一安全的 —— 它的默认目标是后序的 ⑬，会被 `_target_index` 拒掉。
#   ⇒ 闸只能加在**托管自己**的动作上，**不能**指望各门禁自己的轮数。
#   闸拦的是**速率**，不是"总次数 ≤ 3"：要防的是**自旋**（门禁秒判失败 ⇒ 一轮几秒），
#     而慢循环（一轮一小时、每轮都在真干活）与快自旋**都是 3 次** —— 次数分不开这两者，
#     却把慢循环掐死了：audit→code 曾被次数闸挡住 3 次，而那三次 ④ 都把被点名的那条
#     **修好了**（R1/R2/R3 共 5 个 hard id 无一重复，每轮点名的项都被下一轮独立复验确认落地）。
#     ⇒ 只拦**速率**：窗口内回退过密才算自旋。
#     判据用"窗内次数"而不是"两条之间的间隔"，是因为**一轮跑多久**取决于阶段本身（④ 一小时、
#     门禁几分钟），固定间隔阈值会把"正常的快门禁"误判成自旋。
# `state["auto_rollback_times"]` **刻意不在 run_all 里清** —— 清了就等于没闸（见上）。
#   守着这条的是 `regression/test_workflow.py::test_the_spin_guard_survives_a_new_run`
#   （AST 找 run_all 的赋值目标 + 一条"它确实会清 fix_rounds"的正对照）。
# 两个字面量（不读环境变量）：`_num` 定义在 2217 行、比这一段**晚**，模块级用不了它。
#   与旧的 `AUTOPILOT_ROLLBACK_MAX = 3` 同一风格 —— 要调就改这里。
AUTOPILOT_SPIN_WINDOW = 1800     # 观察窗（秒）= 30 分钟
AUTOPILOT_SPIN_MAX = 4           # 窗内允许的自动回退次数；到第 5 次判自旋

_LIB_INSTRUCTION_USERS = {
    "lib/visualization": {"code", "drawio", "figreview", "write", "format",
                      "audit", "robustness",              # ← 加回（见上：白名单漏记）
                      "verify", "mathproof", "cross", "rubric", "fix", "demo"},
    "config/visualization.json": {"code", "drawio", "figreview", "write", "format",
                                  "verify", "cross", "rubric", "fix", "demo"},
    "docs/VISUALIZATION.md": {"code", "drawio", "figreview", "write", "format",
                              "verify", "cross", "rubric", "fix", "demo"},
    "docs/GEOMETRY.md": {"drawio", "figreview"},
    "lib/result_contract": {"code", "audit", "robustness", "drawio", "format",
                        "write", "verify"},
    "config/result_contract.json": {"code", "audit", "drawio", "verify"},
    "docs/RESULT_CONTRACT.md": {"code", "audit", "robustness", "verify"},
}

# `skills/_references/**` → **真正读它的阶段**。为什么拆掉"整目录"：
#
# 不能用 `ins = [..., "skills/_references", ...]` —— **整个目录**进每个阶段的指纹。
# 后果：往 `math_modeling_norms.md` 加一节「行文用词：不要用故」（一条**只管论文措辞**的
# 规矩）⇒ 目录哈希变 ⇒ **全部 16 个阶段**的「做法要求」指纹一起变。生产阶段有 stale
# 宽待保着（只标 `done(stale-instr)`，不重跑）；**门禁不享受宽待**（见 `_input_split`
# 的说明：判据一变必须重判）⇒ ③⑤ 真的从头重判一遍。这条规矩跟建模评审毫无关系。
#
# 与 `_LIB_INSTRUCTION_USERS` 同一套办法、同一套纪律（上面的两条，此处不重复）：
# 表的依据 = **会话原始记录里的每一次工具调用**（`tmp/deps_classify.py`，含 PowerShell）。
# （不能用"运行日志里的真实文件访问"当依据 —— 那个依据是**残的**，见上面 `_LIB_INSTRUCTION_USERS`
#   那段：日志只记七个工具名。按完整记录**重核过这张表**：成员一条不改，
#   下面这些数字随之更新为"真读了内容"的口径。）
# 各阶段的访问量表（数字见下）：
#
#   阶段            带路径的工具调用   norms  discipline
#   ② 建模设计          4210           18       11
#   ③ 建模评审门禁       2883           38        5
#   ④ 编码计算          2697            0       15
#   ⑦ 技术路线图         1481            0*       7      （*探过 1 次，没读内容）
#   ⑨ 论文撰写          1423            2        3
#   ⑤ 结果可信度审计     1396          **0**   **0**    ← 两条都 ≥50 且零命中 ⇒ 敢摘。
#                                                      这个"0"是**按完整记录重新核过**的
#                                                        （只按日志算时依据是残的）
#   ⑧ 绘图门禁          1305            0        4
#   ⑥ 稳健性            1017            0        8
#   ⑭ 排版与版式         1013            0        1
#   ⑩ 数学论证门禁        124            4        0
#   ① 文献定向           114            7        3      ← 命中是真的，但访问量本就小 ⇒ 保守给全
#   ⑫⑬⑭⑮⑯              从未运行                  ⇒ 无证据 ⇒ 保守给全
#
# `internal_leak_words.md` 全阶段 0 命中，但**不是**没人用：它的消费者是 SKILL 文本里
# 点名它的那两个阶段（`skills/15Verification/SKILL.md` 两处、`skills/9Paper-writing/SKILL.md` 一处）
# —— 摘"零命中"要靠这个交叉证据，不能只看访问记录。
# 同一份记录也把 `_LIB_INSTRUCTION_USERS` 的三条"零命中"**证伪了**（见那段注释）：
#   "零命中 ⇒ 摘"这个方法本身没问题，问题在**依据残了** —— 换依据重核之后，这里一条没改。
_REFERENCE_USERS_DEFAULT = {"cross", "verify", "rubric", "fix", "demo", "literature"}

_REFERENCE_USERS = {
    "math_modeling_norms.md": {"literature", "analysis", "review", "write", "mathproof"},
    "stage_discipline.md": {"literature", "analysis", "review", "code", "robustness",
                            "drawio", "figreview", "write", "format"},
    "internal_leak_words.md": {"write", "verify"},
    "SKILL.md": set(),          # `_references/` 的目录索引，记录里无人读
}
# 上面每条都并入"证据不足"的阶段 —— 纪律①：给多了只是多跑一轮，给少了会让阶段漏掉真变化。
_REFERENCE_USERS = {f: users | _REFERENCE_USERS_DEFAULT
                    for f, users in _REFERENCE_USERS.items()}


# ---------- 前序报告：哪些**不必**进本阶段的输入指纹 ----------
# `_input_split` 的默认是"**所有**前序阶段的报告全收"（保守，见下面的纪律）。这条默认
# 有一个代价：**上游阶段写自己的报告，会把所有后继阶段一起作废** —— 哪怕它报告里说的
# 那件事一个字没变。⑬⑭ 正卡在 ⑮ 前面，于是每次 ⑬/⑭ 落笔（哪怕它判"判词不属实、不动稿"，
# 报告照样重写一份）⑮ 就失配一次；`_back_to_judge` 的「⑬ 有没有动稿」判据读的也是这份
# 指纹 ⇒ ⑬ 自己的记录成了"改过稿"的自证（同 `lib/web/receipt_ledger.py` 那句「**返修记录不许
# 自证**」）。⑭ 的输入里 ⑬ 的返修记录同理 —— 那是 ~2h 一次的空跑。
#
# 摘的依据与纪律（与上面两张表同一套，`tmp/deps_classify.py` 那条线）：
#   依据 = **会话原始记录里的每一次工具调用**（`~/.claude/projects/<本工作区 slug>/*.jsonl`），
#   不是 `web_run.log`（那份只记 7 个工具名，是残的）。
#   统计口径（"提过这个报告名"的调用次数 / 该阶段可认身份的会话数）：
#     ① ⑬ fix（4 个会话）：只碰自己的 FIX_REPORT.md。
#     ② ⑭ format（5 个会话）：**0 次**提到 FIX_REPORT.md —— 它只排 paper/，不关心 ⑬ 说了什么。
#     ③ ⑮ verify（3 个会话）：FIX_REPORT.md **1 次**、FORMAT_REPORT.md **1 次** ——
#        都是 `Get-Content ... -First 200 / -Tail 14`，当**上下文**扫一眼，不是它的判据来源。
#
# 为什么摘了**不会漏掉真变化**（这条是关键，不是"零命中就摘"）：
#   ⑬ 除了报告只有 `paper/`；⑭ 除了报告只有 `paper/`、`paper_appendix/`、
#   `reports/SUBMISSION_MANIFEST.json`、`运行说明.md`（见 `ARTIFACTS`）。而这些**全都**
#   在 ⑮ 的输入里（附录与提交件这次一并补上，见 `_EXTRA_INPUT_PATHS`）——
#   报告只是叙述"改了什么"，东西本身已经由产物那一份盯着了。
#   ⇒ 摘掉叙述**不会**让任何一个真改动漏网；反过来，叙述重写不再冒充"审查对象变了"。
_REPORT_INPUT_EXCLUDE = {
    "format": {"FIX_REPORT.md"},                      # ⑭ 只排 paper/，从不读 ⑬ 的记录
    "verify": {"FIX_REPORT.md", "FORMAT_REPORT.md"},  # ⑮ 的两份"都只是扫过一眼"
}

# 阶段 → 除前序报告外**还要算进输入**的路径（补的是"真在看、但以前没进指纹"的东西）。
# ⑮ 验收逐项对账的就是提交件本身，可 `paper_appendix/`（附录A.pdf 的 LaTeX 工程）、
#   `reports/SUBMISSION_MANIFEST.json`（提交清单）、`运行说明.md` **此前谁都没进指纹** ——
#   改了附录，⑮ 的回执照样判"新鲜"，这是**漏**（给少了那一侧），与上面的"给多了"一起修。
_EXTRA_INPUT_PATHS = {
    "verify": ["paper_appendix", "reports/SUBMISSION_MANIFEST.json", "运行说明.md"],
}


def _tool_dirs():
    """`config/runtime.local.json` 里配的外部工具目录（texlive/pandoc/drawio…）。读不到 = 空。"""
    try:
        cfg = json.loads((ROOT / "config/runtime.local.json").read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return []
    dirs = cfg.get("tool_directories") if isinstance(cfg, dict) else None
    return [d.strip() for d in (dirs or []) if isinstance(d, str) and d.strip()]


def _tool_identity(path):
    """把一个工具目录折成 `(名字, 版本)` —— **不看盘符与父目录**。

    `D:\\texlive\\2026\\bin\\windows` → `("texlive", "2026")`；
    `E:\\pandoc\\pandoc-3.6.4` → `("pandoc", "3.6.4")`。
    找不到版本号的（自己手工放的一堆二进制）退回末级目录名、版本记 `""` ——
    那种情况挪目录仍会让指纹变，这是**明知**的取舍（没有版本就只剩路径可认）。
    """
    parts = [p for p in Path(path).parts if not re.fullmatch(r"[A-Za-z]:[\\/]?", p)]
    for i, part in enumerate(parts):
        m = re.search(r"\d+(?:\.\d+)*", part)
        if m:
            name = parts[i - 1] if i else (part[:m.start()].strip("-_ .") or part)
            return name, m.group(0)
    return (parts[-1] if parts else str(path)), ""


def _env_identity():
    """解释器与工具链的**身份**（版本口径）——**不含它们在盘上的位置**。

    为什么要有它（见 `_input_paths` 里那条）：不这么做就得把
      `config/runtime.local.json` **整份按字节**哈希进 ④ 及下游的输入指纹。可那文件的内容
      就是几条**本机绝对路径**（python 在哪、texlive/pandoc/drawio 在哪）——
      换盘符、换安装目录、重装到别处，**字节变了而事实没变** ⇒ 整条链从 ④ 起重跑
      （④ 是小时级）。这正是「改一处怎么又整链重跑」那一类：**把指针当成了事实**。
    所以哈希事实而不是位置：解释器版本 + 每个工具目录的 (名字, 版本)。工具升级 ⇒ 变（该变）；
      换个目录装同一个版本 ⇒ 不变（不该变）。
    """
    bits = [f"python={sys.implementation.name}{'.'.join(map(str, sys.version_info[:3]))}"]
    for d in _tool_dirs():
        name, ver = _tool_identity(d)
        bits.append(f"{name}@{ver or '?'}")
    return ";".join(bits)


def _stage_index(sid, stages=None):
    """该 id 在**当前链**里的下标；不在链里返回 `None`。

    不许写成 `next(i for i, s in enumerate(STAGES) ...)` —— 阶段链是**可裁剪**的
      （回归用例常把 `STAGES` 换成单个阶段，真实链也可能被换题/回退改短）：
      链里没有 `code` / `write` 时它会抛 `StopIteration`，而那两个异常类**自己的 `str()` 是空的**
      ⇒ `run_all` 的兜底 except 记成「驱动异常：」+ 什么都没有 ⇒ 面板上一个查不出原因的黄灯。
      三个 `never_collects` 用例就是被它噎住的 —— 链在门禁之前就崩了，
      而 `assert_not_called` 照样通过 ⇒ 那三条断言**恒真**。
    """
    for i, s in enumerate(STAGES if stages is None else stages):
        if s["id"] == sid:
            return i
    return None


def _input_paths(stage):
    """本阶段「产物所依据的事实」的**路径清单** —— `_input_split` 那半份指纹就是它的哈希。

    单独抽出来是为了**可测**：`regression/test_stale_noise.py` 要断言「某份报告摘掉之后
      没有任何真产物漏网」（`test_dropping_a_record_loses_no_deliverable`），而那需要看
      **清单**，不是看哈希值。行为一字未变（同一个列表进同一个 `fingerprint`）。
    """
    index = _stage_index(stage["id"])
    i_code = _stage_index("code")
    art = ["request", "data", "plan.md"]
    # 前序报告**按阶段各摘各的**：默认全收（保守），只摘 `_REPORT_INPUT_EXCLUDE` 里
    #   有证据、且"报告说的东西已经由产物那一份盯着"的那些（见那张表的说明）。
    _skip_reports = _REPORT_INPUT_EXCLUDE.get(stage["id"], ())
    for previous in STAGES[:index]:
        rep = previous["report"]
        if rep in _skip_reports:
            continue
        art.append("paper" if rep.startswith("paper") else "reports/" + rep)
    art += _EXTRA_INPUT_PATHS.get(stage["id"], [])
    if any(s["id"] == "code" for s in STAGES[:index]):
        art += ["code", "results"]
        # `figures/` **刻意不在**这里（`skills/8Figure-gate/SKILL.md` 说的"它搬过家"就是这件）：
        #   画图脚本住 `figures/make_figures.py`，而图的内容里没有任何数值结论 ——
        #   把它算进输入指纹，改一行配色就要连锁重跑 ⑤⑥⑦⑧。图谱自己靠
        #   `visualization.evidence` 的登记表（脚本/数据/配置的签名）判"过期了要重渲"，
        #   比整目录哈希精确。脚本若被写进 `code/` 就落回这个指纹里 ⇒
        #   `regression/test_stale_noise.py::test_the_data_figure_script_lives_under_figures` 抓它。
    if i_code is not None and index >= i_code:
        # 依赖决定所有数值结果 —— 那是**事实**变了，不是要求变了。
        # `config/runtime.local.json` **不在**这里：它是"工具装在哪"的
        #   **指针**（本机绝对路径），按字节哈希进去 ⇒ 换盘符/换安装目录就把 ④ 及下游整条链
        #   重跑一遍。改成在 `_input_split` 末尾按**身份**（版本）计入，见 `_env_identity`。
        art += ["requirements.txt", "requirements.lock.txt"]
    # 裁决侧车（`<report>.verdict.json`）**不放这里** —— 它是本阶段的**产物**，不是输入。
    #   放进去会让阶段自我失效：跑完写出侧车 → 输入指纹变了 → 下一句 `_input_digest(stage)
    #   != inputs` 判定「执行期间输入被改动」→ 整链 UNVERIFIED 硬挂（会把 22 个用例打红）。
    #   侧车已经在 `_output_digest` 里（那边才是它该在的地方）。
    return art


def _input_split(stage):
    """把阶段的输入拆成两半。**它们失效的语义完全不同，混在一起是错的。**

    - `artifacts`（返回第 1 项）——**产物所基于的事实**：题面/数据/plan/前序阶段的报告/
      code/结果/解释器环境。变了 ⇒ 产物真的可能过期，**必须重做**。
    - `instructions`（返回第 2 项）——**做法要求**：本阶段的 SKILL、`_references`、工作区说明
      `CLAUDE.md`/`AGENTS.md`、驱动发给它的注入指令、各模块与规范文档。变了 ⇒ 产物**可能**
      要按新要求重做 —— 但「要不要」是**价值判断**，驱动判不了：改一个错别字和改一条门禁
      规则，在字节层面一模一样。

    两半混在同一个 digest 里时，后果有两个，都很疼：
      ① **改一个错别字 = 全链从零重跑**（其中 code 一步就是小时级）；
      ② **人手工认证过的产物，会被一句文档改动推翻** —— 而「人手工修好 agent 改不过的东西」
         正是 `attest` 存在的理由，等于它的出口被它自己要修的那件事堵死了。

    现在的处置：
      · `artifacts` 变了 → 照旧**自动重做**（这是真的过期，没得商量）；
      · `instructions` 变了 → 贵的生产阶段**只标记不重跑**（状态 `done(stale-instr)` +
        `state["stale_instr"]`），由人看着标记决定要不要按新要求重来；
      · **门禁也走同一条路**：不能把门禁排除在外（「重做便宜、判据一变
        必须重判」），但那条理由自相矛盾 —— 既然承认「字节层面分不清错别字与判据变更」，
        就不该对门禁假定分得清。那样做的代价：加一条只管论文措辞的规矩，把 ③ 建模评审门禁
        整段拉起来重判。现在统一为**只标记、不重跑**；**事实（artifacts）变了仍旧自动重跑**
        —— 那是「论文里的数与你交出去的代码不是一回事」的唯一防线。
    """
    index = _stage_index(stage["id"])
    i_write = _stage_index("write")
    i_code = _stage_index("code")

    # ---------- artifacts：题目给的事实 + 上游产物 + 环境 ----------
    art = _input_paths(stage)

    # ---------- instructions：做法要求 ----------
    ins = ["skills/" + stage["skill"], "CLAUDE.md", "AGENTS.md"]
    # `skills/_references` **按文件**给，不再是整目录—— 见 _REFERENCE_USERS
    #   上面那段：整目录进指纹会让该目录下任何一次编辑命中**全部 16 个阶段**，而门禁不享受
    #   stale 宽待 ⇒ 改一条只管论文措辞的规矩也要把 ③⑤ 拖起来真重判。
    for _ref, _users in _REFERENCE_USERS.items():
        if stage["id"] in _users:
            ins.append("skills/_references/" + _ref)
    # 库/规范：**按阶段真实依赖**给，不再是"≥④ 一律打包"（见 _LIB_INSTRUCTION_USERS 的表）
    for path, users in _LIB_INSTRUCTION_USERS.items():
        if stage["id"] in users:
            ins.append(path)
    if i_write is not None and index >= i_write:
        ins += ["lib/publication", "config/publication.json", "docs/PUBLICATION.md",
                "docs/CUMCM_2026_REQUIREMENTS.md", "docs/WRITING_QUALITY.md"]
    if stage.get("gate"):
        ins += ["docs/CONTENT_QUALITY.md", "config/content_quality.json"]
    ins_fp = fingerprint(ROOT, ins) + ":" + _prompt_fingerprint()
    if stage.get("gate"):
        ins_fp += ":" + _gate_logic_fingerprint()   # 裁决逻辑就是判据，一变必须重判
    # 内容侧阶段（判内容的与按判词改文字的）**不看版式侧**：
    #   `14Layout-and-format` 排在它们**之后**，而它独占 `paper/_base/`（导言区）并重编 PDF。
    #   若仍按整份 `paper/` 判，它每动一次版式就作废一次 10/11/12/13 的回执 ⇒ 下一轮
    #   重修 13→14→15（14 一次 ~2h）。
    #   ⇒ 对这四个阶段，**版式侧的文件不进输入指纹**；`paper/sections/`、`main.tex`（含摘要）、
    #     `references.tex` 这些**内容**照旧算 —— 所以 13 真改了文字，10/11/12 仍会被判失效。
    #   `15Verification` **不在**这个名单里：它要看的正是最终成品（含版式）。
    excl = list(_DERIVED_RESULT_FILES)
    if stage["id"] in _CONTENT_SIDE_STAGES:
        excl += list(_LAYOUT_OWNED_PATHS)
    art_fp = fingerprint(ROOT, art, exclude=excl)
    # 解释器/工具链按**身份**计入，不按"装在哪"（见 `_env_identity`）：
    #   ④ 及下游的数值结果取决于**哪个版本**的 python 与求解器，不取决于它的盘符。
    if i_code is not None and index >= i_code:
        art_fp += ":" + _env_identity()
    return art_fp, ins_fp


def _input_digest(stage):
    art, ins = _input_split(stage)
    return art + ":" + ins


# ---------------- 版式改动不作废内容判据 ----------------
# ⑭排版只做版式手术（浮体/间距/表宽/页数压缩），它改完**不该**把
# ⑩数学论证门禁 / ⑪跨问一致性 / ⑫评分标终审 拉回来重判 —— 排版不改正确性。
# 代价：⑭ 每次落笔 `paper/sections/*.tex`（例如式(14) 后的 `\par\vspace{9pt}`），
# 收尾复验就要把三个内容判官各重跑一遍（十几分钟 ×3），而它们判的东西一个字没变。
#
# 判据不能是"⑭ 跑过没有"（那会把**⑬ 刚返修过**的情形一起吃进去 —— ⑫ 必须复评！），
#   所以 ⑭ 跑完时**盖一个戳**：`paper/` 的**内容视图**（与内容判官看到的同一套排除规则）的指纹。
#   「被版式覆盖」= 当前内容视图指纹 == 戳 ⇒ 说明**此后没人再改过正文**，只有 ⑭ 动过版式
#   ⇒ 内容判官的旧裁决仍然有效，不重判。
#   ⑬ 一改正文，指纹就与戳不符 ⇒ 照旧重判（这条是安全的那一侧，不能松）。
# 已知代价（明确接受）：⑭ 压页数时若真**删了段落**，内容判官也不会重判 ——
#   字节层面分不清"删段"与"挪浮体"。痕迹留在 `state["layout_superseded"]` 与日志里，
#   需要时手动从该阶段重跑。
_CONTENT_JUDGE_STAGES = ("mathproof", "cross", "rubric")


def _later_paper_owner(stage, owners=None):
    """本阶段**之后**有没有「拥有 `paper/` 且回执有效」的阶段？返回它的 id，否则 None。

    = 「论文此后又被合法打磨过（⑬ 按判词返修 / ⑭ 排版与版式）」这件事的机器判据。
    只比**事实半份**（`artifacts` + `outputs`），**不比 `instructions`** —— 改一条共享的做法
    要求（`CLAUDE.md`）不该让这条失效；与 `_taken_over_by` 用的是同一套判据。

    为什么要有它：⑩⑪⑫ 是**内容判官**，它们判完就是内容定稿；
      之后 ⑫⑬⑭ 只打磨措辞与版式，却因为「它读的那个 `paper/sections/*.tex` 字节变了」被
      拉回来重判 —— 口径：「11 过后，已经表示正文就是没问题了，12 和 13 只是打磨一下语句，
      那肯定和之前做的对不上啊」。判据放在**命令序列**上（"此后只有打磨者动过论文"），
      而不是"哪个文件变了"——字节层面分不清打磨与改内容。
    """
    store = _receipt_store()
    for ostage in STAGES[STAGE_IDX[stage["id"]] + 1:]:
        if "paper" not in ARTIFACTS.get(ostage["id"], []):
            continue
        if owners is not None and ostage["id"] not in owners:
            continue
        orec = store.records.get(ostage["id"]) or {}
        try:
            oart, _oins = _input_split(ostage)
            oout = _output_digest(ostage)
        except Exception:                       # noqa: BLE001 —— 判据算不出来就当他没打磨
            continue
        if (orec.get("artifacts") == oart and orec.get("outputs") == oout
                and _artifact_ok(ostage)):
            return ostage["id"]
    return None


def _polisher_owners(sid):
    """该内容判官的"打磨者"名单 —— **单一出处**（`_layout_superseded` 与它那条日志都读这里）。

    为什么要有这个函数：「谁算打磨者」只能有一个地方知道。名单若同时写进
      `_layout_superseded` 和 `_back_to_judge` 的日志各一份 ⇒ 两处真值就会漂
      （`cross` 的名单收成 `("format",)` 后，日志还可能在说"此后只有⑬⑭打磨过论文"）。
    """
    # `rubric` 与 `cross` 都**只认 `format`**：
    #   · ⑫（rubric）判完就结束了，⑬ 只是它的**工具步骤** ⇒ ⑬ 改完必须回 ⑫ 复评，
    #     所以 ⑬ 不能算"不重判的打磨者"（把 `fix` 算进去会静默掐掉那条设计路径）。
    #   · ⑪（cross）：⑪ 把 claim 判词交给 ⑬ 时它自己还没结束 ⇒ ⑬ 的改动作废它的裁决 ⇒ 必须回评。
    #     代价：⑬ 可能把附录表里的 `\mp0.013` 改成 `-0.013/+0.020`（**动了数值**），
    #     而那条判词正是 ⑪ 为这张表提的，却没人复查。
    #   · `mathproof`（⑩）保留 `("fix","format")` —— 它不在 `_FIX_HANDOFF_JUDGES` 里，
    #     从不把判词交给 ⑬，所以 ⑬ 对它而言确实只是打磨。
    return ("format",) if sid in ("rubric", "cross") else ("fix", "format")


def _layout_superseded(stage):
    """内容判官的裁决是不是**仍然有效**（此后只有打磨者动过论文）？是 → 不重判。

    谁算"打磨者"**一律看 `_polisher_owners`**（单一出处）：
      · ⑫评分标终审 / ⑪跨问一致性 → **只有 `format`**。⑬ 对这两关都不是"打磨者"：
        对 ⑫ 它是**工具步骤**（「13 只是负责处理 12 的工具步骤…当 12 没过，
        就亮黄灯，等待 13 处理后再返回 12」）；对 ⑪ 是同样的关系，口径也明确：
        「13、14 只打磨，但是 **11 这里还没结束**」⇒ ⑬ 改完必须回 ⑪ 复评。
      · ⑩数学论证门禁 → `fix`、`format`：⑩ 从不把判词交给 ⑬（不在 `_FIX_HANDOFF_JUDGES`），
        所以 ⑬ 对它而言确实只是打磨 ⇒ 不重判。
    """
    sid = stage["id"]
    if sid not in _CONTENT_JUDGE_STAGES:
        return False
    return _later_paper_owner(stage, owners=_polisher_owners(sid)) is not None


def _review_object_stale(stage):
    """该阶段的**审查对象**（artifacts + 自己的产物）是否已变 —— **不看 instructions**。

    为什么不能用 `store.matches`（整份 digest）判：只看指令变了的阶段会被标成
      `done(stale-instr)` 并且**刻意不重存回执**（见 `_input_split` 的宽待），于是整份
      digest 必然失配。用 matches 判的话，收尾复验会把它们统统重跑一遍 ——
      正好把「贵的阶段只标记不重跑」那套宽待整个抵消掉（改一处说明就会把 14Layout-and-format
      重跑了一遍）。这里只比 `artifacts` 与 `outputs`：**指令变了不算审查对象变了**。

    旧回执没有 `artifacts` 字段（值为 None）→ 与任何当前值都不等 → 照旧重跑，安全。

    内容判官的**例外**（口径「版式改动不作废内容判据」）：`paper/` 的
      内容视图与 ⑭ 离开时的戳一致（= 此后只有版式被改过）⇒ 它们的裁决仍然有效，
      **不算审查对象变了**。见 `_layout_superseded` 那段说明与它写明的已知代价。
    """
    rec = _receipt_store().records.get(stage["id"])
    if not isinstance(rec, dict):
        return True                       # 没跑过 → 当作需要跑
    if _layout_superseded(stage):
        state.setdefault("layout_superseded", set()).add(stage["id"])
        return False
    art, _ = _input_split(stage)
    return rec.get("artifacts") != art or rec.get("outputs") != _output_digest(stage)


def _save_receipt(stage, manual=False):
    """按当前盘面写回执。**所有写回执的地方都走这里。**

    三处各写各的迟早会漏字段 —— `artifacts`/`instructions` 是拆开存的两半，
    漏了就会让「只有指令变了」的宽待判定永远不成立（静默退回"一改就全跑"的老毛病）。
    """
    art, ins = _input_split(stage)
    _receipt_store().save(stage["id"], art + ":" + ins, _output_digest(stage),
                          state["run_id"], manual=manual,
                          artifacts=art, instructions=ins)
    # 刚按当前盘面重写过 = 它不再"按旧要求交付"，标记录到此为止。
    state["stale_instr"].discard(stage["id"])


# def _input_legacy_rels():
#     """（占位，无调用者）说明 `figures/` 为何**两侧都不进指纹**：
#     把整目录 `figures/` 算进输入，后果是「6Robustness 往 figures/ 写 27 张稳健性图」
#     就把 code/drawio 的回执全部弄失效（code 的 out-digest 由
#     `19da02c7…` 变 `6dff5918…`，而 code 自己的交付物一个没动）。
#     图的「完整性 + 新鲜度」已有专用机制：`figures/manifest.json` 逐张记 sha256 +
#     `python -m lib.visualization audit` 对过期资产直接 FAIL（15Verification 会跑它）——
#     驱动再整目录哈希一遍是重复劳动，口径还更粗（谁写的都算）。
#     `code/` 与 `results/` 保留在 artifacts 里：它们变了数值真的会变，且没有别的机制兜底。
#     """
#     return None


def _output_digest(stage):
    rels = list(ARTIFACTS.get(stage["id"], []))
    # `figures/` **刻意完全不进指纹**（输入侧见 _input_digest，输出侧这里同一条理由）。
    #   若把整目录 figures/ 塞进 code 的产物，再按 `ARTIFACTS["drawio"]` 白名单去排除
    #   drawio 写的图 —— 那个白名单是静态的，而**画什么图由题目决定**：
    #   上一题的 fig_flow_q1..q4 / fig_pipeline 根本不存在，而 drawio 真正写的
    #   fig_coupling / fig_geometry / fig_mesh / fig_shrink_coord 一个都没被排除。
    #   后果是第一轮跑完 drawio 后，续跑 code 时输出指纹必然失配 → 最重的阶段
    #   （小时级优化/仿真）从零重跑，并级联拖垮整条下游。
    #   图的**完整性 + 新鲜度**由 figures/manifest.json 逐张 sha256 + `python -m
    #   visualization audit` 负责（15Verification 会跑它）—— 那才是为这件事造的机制。
    #   代价：重做 code 时不会自动清理它上一轮画的数据图；过期图由 manifest 失配抓出。
    if stage.get("gate"):
        rels.append("reports/" + str(Path(stage["report"]).with_suffix(".verdict.json")))
    return fingerprint(ROOT, rels, exclude=_DERIVED_RESULT_FILES)


def _invalidate_from(index):
    """作废 index 及之后**全部**阶段的回执。仅用于"输入源变更/用户指定重做"这类整体失效。"""
    _receipt_store().invalidate(s["id"] for s in STAGES[index:])
    for s in STAGES[index:]:
        state["stages"][s["id"]] = "idle"


def _invalidate_stage(index):
    """只作废该阶段自身的回执——下游是否重跑**由其输入指纹决定**（见 run_stage 的复用判定）。

    若把"阶段重跑即作废其后全部"当成规则，drawio 重绘几张流程图片也会把 robustness
    （1 小时级）拖下水 —— 而它的输入没变，回执本可复用。所以判据必须落在**输入指纹**上：
    某阶段重跑后产出若与上次**逐字节相同**，其下游指纹不变 ⇒ 下游直接复用跳过。
    """
    s = STAGES[index]
    _receipt_store().invalidate([s["id"]])
    state["stages"][s["id"]] = "idle"


def _record_quality(stage, status, reason, **extra):
    path = LOG_DIR / "quality" / "events.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    event = {"time": datetime.now().isoformat(), "run_id": state["run_id"],
             "stage": stage["id"], "status": status, "reason": reason, **extra}
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


def _write_hil_decision(stage, reason, pending=None):
    """挂起时自动生成一页纸的人工决策清单。

    不生成它，挂起就只留一行日志，人工要翻 30 条 issue 才知道卡在哪、该怎么定 —— 这一步把
    "看在哪、有哪几个选项、每个选项的代价"直接落成 reports/HIL_DECISION.md。

    `pending` 由 _build_pending 构造；有它就把「agent 推荐回退到哪个阶段、候选有哪些、
    来源是哪」一并写进去 —— 界面上的下拉默认值取的就是这里的 recommended。
    """
    dec = _gate_decision(stage) if stage.get("gate") else {"issues": []}
    issues = dec.get("issues") or []
    L = [f"# 人工决策清单（{datetime.now().strftime('%m-%d %H:%M')}）", "",
         f"- **卡在阶段**：`{stage['id']}`（skill `{stage.get('skill', '')}`）",
         f"- **原因**：{reason}",
         f"- **本轮返修轮次**：`{json.dumps(state.get('rounds', {}), ensure_ascii=False)}`", ""]
    if issues:
        L += ["## 门禁未解决项（按 category 标出应返修的阶段）", "",
              "| id | severity | category | 建议返修阶段 | 证据（截断） |", "|---|---|---|---|---|"]
        for i in issues:
            L.append(f"| {i.get('id')} | {i.get('severity')} | {i.get('category')} | "
                     f"{CONTENT_TARGETS.get(i.get('category'), '?')} | {str(i.get('evidence'))[:90]} |")
        L.append("")
    if pending:
        rec = pending.get("recommended")
        src_label = {"handback": "agent 主动交回", "verdict": "门禁裁决给出",
                     "default": "默认映射"}.get(pending.get("recommended_source"), "—")
        L += ["## agent 的建议", "",
              f"- **推荐回退到**：`{rec or '（无）'}`（来源：{src_label}）",
              f"- 可选前序阶段："
              + "、".join((f"**{c['id']}**" if c["id"] == rec else c["id"])
                          + ("（产物未变，回退过去会直接跳过）" if c.get("unchanged") else "")
                          for c in (pending.get("candidates") or []))
              or "（无前序阶段）", ""]
        if pending.get("kind") == "overtime":
            L += ["## 任务状态", "",
                  f"- ⏱ **超时但进程仍在运行**（{pending.get('limit_kind')}）—— 不杀进程，等你决定",
                  f"- 当前限时：{int(pending.get('retry_cap_default', 0))} 秒"
                  f"（可延长至 {int(pending.get('retry_cap_max', 0))} 秒）", ""]
            if pending.get("estimate"):
                e = pending["estimate"]
                L.append(f"- 缩比预估：按 {e['scale']:.0%} 规模试跑得总时长约 "
                         f"**{int(e['total_est_s'] / 60)} 分钟**")
            else:
                L.append("- 缩比预估：**该阶段无法预估剩余时间**（脚本未打印 `[SCALE_ESTIMATE]`）")
            L.append("")
    L += ["## 三个选项（界面上的按钮，选一个即可）", "",
          "1. **接受并披露**：把未解决项记入 `reports/_KNOWN_WRITING_RESIDUALS.md` 后继续，"
          "并写机器可读的 `runtime/quality/waivers.json`（**输入一变豁免自动失效、门禁重新生效**）；"
          "适合「残余增益极小 / 纯措辞」类问题。",
          "2. **回退重跑**：退到你选的那个阶段重跑——该阶段及之后的产物会**移入 `cache/`（不删除，可恢复）**，"
          "已完成且输入未变的阶段按回执自动跳过。",
          "3. **再试一次**：本阶段原样重跑（可临时把本次限时设长一些）；"
          "重跑提示里会带上上次失败的原始输出。", "",
          f"> 原始回执：`reports/{stage['report']}`；返修回执副本见 `runtime/quality/feedback/`。"]

    (REPORTS / "HIL_DECISION.md").write_text(chr(10).join(L), encoding="utf-8")
    log("已生成人工决策清单 reports/HIL_DECISION.md")


# ---------------- ⓪ 读题：上传原件 → AI 读 → 人确认 ----------------
# 契约：上传题目就是**上传一个文件夹**，交给 AI 自己读取并分析，AI 读完之后
#   把读到的东西展示给用户、让用户核对"读得对不对"，核对通过才进链。
#
# 两条地基（改动前先读一遍）：
#   ① **agent 绝不能在阶段内搬文件**：`run_stage` 入口取 `_source_digest()`（:2745），成功
#      分支比对不等就判 `unverified`（:2956-2962），而那个 digest 就是 `request/`+`data/`
#      的内容哈希（:639-653）⇒ 任何阶段执行期间改动这两个目录都会被当场挂起。
#      ⇒ AI 只**提案**（机读 JSON），搬文件由服务端在链外（确认那一刻）做。
#   ② **确认时的搬运会触发一次换题轮转**：`_prepare_workspace()`（:656-705）比对 digest，
#      不等就把 `reports/` 整份搬进 cache（`RELS` 见 :676-677）并 `_invalidate_from(0)`。
#      ⇒ 读题产物必须**另存一份在 `runtime/quality/intake/`**（`runtime/` 既不在 RELS、
#      也不在 `_source_digest` 里，轮转搬不走），确认时快照、短路时幂等恢复回 `reports/`。
INTAKE_DIR = LOG_DIR / "quality" / "intake"
INBOX_REL = "request/_inbox"
INBOX_NEW_REL = "request/_inbox.new"
INTAKE_JSON_REL = "reports/INTAKE.json"
INTAKE_REPORT_REL = "reports/INTAKE_REPORT.md"


def _inbox_path():
    return ROOT / INBOX_REL


def _inbox_files():
    """inbox 里**原件**的相对路径（posix、相对仓库根），稳定排序。

    用 `_walk_tree`（:4991）而不是 `rglob`：它不跟随符号链接/Windows 目录联结点
      —— 上传内容是不可信输入，遍历时跟出去读到工作区外面是实打实的越界。
    """
    base = _inbox_path()
    if not base.is_dir():
        return []
    out = []
    for p, _rel in _walk_tree(base, ROOT):          # 产出 (路径, 工作区相对路径) 两个值
        if p.is_file():
            out.append(INBOX_REL + "/" + p.relative_to(base).as_posix())
    return sorted(out)


def _inbox_has_content():
    return bool(_inbox_files())


def _intake_confirmed():
    """人工确认的留痕（`runtime/quality/intake/confirmed.json`）；没有/读坏都返回 None。

    落在 `runtime/quality/intake/` 而不是 `runtime/quality/manual/`（attest 那个）：
      attest 的语义是"以当前盘面重新认证某阶段"，这里是"人做了一次判断" —— 混在一个目录里
      日后必被误读。
    """
    try:
        rec = json.loads((INTAKE_DIR / "confirmed.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return rec if isinstance(rec, dict) else None


def _intake_proposal():
    """AI 的机读提案（`reports/INTAKE.json`）。缺失/写坏都返回 `{}`（面板照常能画）。

    **这是不可信输入**（AI 写的），所以在**读这一层**做一次类型归一化：
      `subquestions`/`files` 被写成字符串、`problem` 被写成列表时，下游的 `len(...)`、
      `.get(...)` 会当场抛 ⇒ `/api/intake` 500、确认页**整张表消失**（而那时链正停在黄灯上，
      用户既看不到也不能确认）。收口在这里，所有调用点一次覆盖。
    """
    try:
        rec = json.loads((ROOT / INTAKE_JSON_REL).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(rec, dict):
        return {}
    if not isinstance(rec.get("files"), list):
        rec["files"] = []
    rec["files"] = [x for x in rec["files"] if isinstance(x, dict)]
    prob = rec.get("problem")
    if not isinstance(prob, dict):
        rec["problem"] = {}
    else:
        if not isinstance(prob.get("subquestions"), list):
            prob["subquestions"] = []
        if not isinstance(prob.get("uncertain"), list):
            prob["uncertain"] = []
    if not isinstance(rec.get("notes"), list):
        rec["notes"] = []
    return rec


def _intake_unconfirmed():
    """本题有一批**上传原件还没被人工确认**。纯盘面推导，不引入任何一次性状态位。

    为什么判据必须是纯盘面的：`regression/test_workflow.py`
      里有 94 处 `run_all()` 调用，主流写法是从下标 0 跑全链 + 断言 `expected_full_chain()`。
      若读题跑完**无条件**亮黄灯，这几十条用例当场全红。改成"盘面里有 `request/_inbox/`
      才算没确认"之后：测试不建 inbox ⇒ 恒为 False ⇒ 既有行为一字不变；真实流程必建 inbox
      ⇒ 天然生效。而确认时会删掉 inbox ⇒ 确认之后这条自然变 False，链照常往下走。
    """
    if not _inbox_has_content():
        return False
    rec = _intake_confirmed()
    return rec is None or rec.get("digest") != _source_digest()


def _default_target(rel):
    """这份原件确认后该去哪：默认全进 `request/attachments/`（保留原相对结构）。

    为什么默认不是 `data/`：只有**落在 `request/` 内**的文件才能当题意锚点
      （`lib/web/content_quality.py:212-213` 硬判 `source.file` 必须在 `request/` 下），
      而 `data/` 在 skills 层没有任何契约。所以 `data/` 只留给"明显是数据集、本来也当不了
      锚点"的大文件，由 AI 显式指定。
    """
    return f"request/attachments/{rel}"


def _intake_ai_facts():
    """AI **自称**读到的量（页数/字数/小问数/附件数）。

    这几个数字是**纯信息**，不参与判定：绿/黄 chips 需要"机械抽取 vs AI"的确定性对照，
    而机械读题整条已拆 ⇒ 只剩"和原 PDF 对得上吗"这条线索，不再有绿/黄判定。
    """
    prop = _intake_proposal()
    ai_problem = (prop.get("problem") or {}) if isinstance(prop.get("problem"), dict) else {}
    return {"chars": ai_problem.get("chars"), "pages": ai_problem.get("pages"),
            "subquestions": len(ai_problem.get("subquestions") or []) or None,
            "files": len(prop.get("files") or []) or None}


def _intake_panel_fields():
    """确认页要的数据。**每次都从盘上现算**，不靠 pending 快照。

    为什么不能只存快照：`_load_pending()` 的"旧版本驱动写的快照"分支（:2500）会调
      `_build_pending(...)` 整份重算 —— 只存在于快照里的字段会被静默丢掉，用户重启之后
      看到一个只有「再试一次」的空面板，而且**看不出少了东西**。
    长文本（题面、机械抽取、AI 报告）**不进这里**：`/api/state` 每 4 秒轮询一次，
      把几万字的正文塞进每一轮会把面板拖慢。前端按 `paths` 现取。
    """
    prop = _intake_proposal()
    # 按**整条相对路径**配对，基名只在**全表唯一**时兜底 ——
    #   若改成按基名直接 `ai_rows[Path(p).name] = item`（后写顶前写），两份不同子目录下的
    #   **同名**附件（`附件3/result1.xlsx` 与 `附件4/result1.xlsx`，正是附件包的常态）会被
    #   渲染成**同一个目标**：用户不改直接确认 ⇒ 后写的盖前写的、两份原件一起被删，毫无提示。
    by_full, by_base = {}, {}
    for item in (prop.get("files") or []):
        if not isinstance(item, dict):
            continue
        p = str(item.get("path") or "").replace("\\", "/").strip()
        if not p:
            continue
        by_full[p] = item
        by_base.setdefault(Path(p).name, []).append(item)
    rows = []
    for rel in _inbox_files():
        sub = rel[len(INBOX_REL) + 1:]
        uniq = by_base.get(Path(rel).name) or []
        hit = by_full.get(sub) or by_full.get(rel) or (uniq[0] if len(uniq) == 1 else {})
        rows.append({
            "path": rel,
            # 缺 role 时一律按最保守的 `attachment` 落，即"当普通附件收进 request/attachments/"：
            #   机械读题拆掉后没有机械判定可回退，而 AI 没给角色本不该发生（SKILL 的 schema
            #   要求每份都填）；真缺了也不能猜成 problem/data 那种有更强语义的角色。
            "role": str(hit.get("role") or "attachment"),
            "target": str(hit.get("target") or _default_target(sub)),
            "why": str(hit.get("why") or ""),
        })
    return {
        "files": rows,
        "facts": _intake_ai_facts(),
        "json_path": INTAKE_JSON_REL,
        "report_path": INTAKE_REPORT_REL,
        "problem_path": "request/problem.md",
    }


def _snapshot_intake():
    """把读题产物抄一份到 `runtime/quality/intake/`（轮转搬不走的地方）。返回抄了几个。"""
    INTAKE_DIR.mkdir(parents=True, exist_ok=True)
    n = 0
    for rel in (INTAKE_JSON_REL, INTAKE_REPORT_REL):
        src = ROOT / rel
        if src.is_file():
            (INTAKE_DIR / Path(rel).name).write_bytes(src.read_bytes())
            n += 1
    return n


def _restore_intake_artifacts():
    """把快照幂等地恢复到 `reports/`（内容相同就跳过）。返回恢复的文件名。"""
    done = []
    for name in (Path(INTAKE_JSON_REL).name, Path(INTAKE_REPORT_REL).name):
        src = INTAKE_DIR / name
        dst = REPORTS / name
        if not src.is_file():
            continue
        try:
            if dst.is_file() and dst.read_bytes() == src.read_bytes():
                continue
            REPORTS.mkdir(exist_ok=True)
            dst.write_bytes(src.read_bytes())
            done.append(name)
        except OSError as exc:                       # noqa: BLE001 —— 恢复失败不该让链停下
            log(f"⚠️ 读题产物恢复失败（{name}）：{exc}")
    return done


def _intake_hint():
    """交给 ① 的提示：读题结论在哪、人工改过什么。

    为什么要它：确认之后从 ① 起跑，而那次 `_prepare_workspace` 会把 `reports/` 整份
      搬进 cache（换题轮转）⇒ `reports/INTAKE_REPORT.md` 可能正躺在归档里。这份快照路径
      **跨换题存活**，所以 ① 照这个指针一定读得到。
    """
    rec = _intake_confirmed() or {}
    parts = [f"【读题结论】上一轮已人工确认（{rec.get('at', '')}）。"
             f"报告：`runtime/quality/intake/{Path(INTAKE_REPORT_REL).name}`"
             f"（`reports/` 下那份可能已被换题轮转归档）；机读提案："
             f"`runtime/quality/intake/{Path(INTAKE_JSON_REL).name}`。"
             f"请以它为准理解题意，但**仍要自己逐字核对 `request/` 原文**。"]
    if rec.get("corrections"):
        parts.append("【人工更正】" + str(rec["corrections"]))
    if rec.get("human_edits"):
        parts.append("【人工改过的分类】" + "；".join(map(str, rec["human_edits"])))
    return "\n".join(parts)


INTAKE_ROLES = ("problem", "attachment", "data", "ignore", "needs_manual")


def _validate_roles(rows):
    """把确认页那张表校验成 `[(原件, 落点 or None, 角色)]`。不合法抛 `HTTPException(400)`。

    只算不落盘 —— 这是"全成或全不动"的第一步：校验不过时**一件都不许动**。
    """
    inbox = set(_inbox_files())
    if not rows:
        raise HTTPException(400, "确认表是空的 —— 重新选一次文件夹再传")
    plan, seen_problem = [], 0
    for row in rows:
        if not isinstance(row, dict):
            raise HTTPException(400, "确认表里有格式不对的行")
        rel = str(row.get("path") or "").replace("\\", "/").strip()
        role = str(row.get("role") or "").strip()
        if rel not in inbox:
            raise HTTPException(400, f"确认表里有一份不在待确认清单里的原件：{rel!r}")
        if role not in INTAKE_ROLES:
            raise HTTPException(400, f"「{rel}」的角色不认识：{role!r}"
                                     f"（只能是 {'/'.join(INTAKE_ROLES)}）")
        if role == "problem":
            seen_problem += 1
        if role in ("ignore", "needs_manual"):
            plan.append((rel, None, role))
            continue
        raw = str(row.get("target") or "").strip()
        if not raw:
            raise HTTPException(400, f"「{rel}」要挪位置但没给目标路径")
        try:
            target = upload_guard.safe_rel_path(raw)
        except upload_guard.UploadRejected as exc:
            raise HTTPException(400, f"「{rel}」的目标路径不合法：{exc}") from exc
        if not (target.startswith("request/") or target.startswith("data/")):
            raise HTTPException(
                400, f"「{rel}」的目标只能落在 request/ 或 data/ 下（收到 {target!r}）"
                     "—— 只有 work 区里的这两处会进链的输入指纹")
        # 目标不许还在 `_inbox` 里：确认的最后一步会把 `_inbox` 整个删掉 ⇒ 搬进它自己
        #   = **原件静默消失**，而确认记录还写着"已搬运"。这不是假想的路径 —— AI 的
        #   提案里 `problem.file` 就是 `request/_inbox/…` 这个形状，写串了会被原样预填进来。
        if target.startswith(INBOX_REL + "/") or target.startswith(INBOX_NEW_REL + "/"):
            raise HTTPException(400, f"「{rel}」的目标不能还在 {INBOX_REL}/ 里 ——"
                                     "那个目录在确认的最后会被整个删掉，等于把原件丢了")
        dst = (ROOT / target)
        try:
            if not dst.resolve().is_relative_to(ROOT.resolve()):
                raise HTTPException(400, f"「{rel}」的目标跑到工作区外面了：{target!r}")
        except OSError as exc:
            raise HTTPException(400, f"「{rel}」的目标路径无法解析：{exc}") from exc
        plan.append((rel, target, role))
    if seen_problem > 1:
        raise HTTPException(400, f"标成了 {seen_problem} 份「题面」—— 只能有一份")
    # 表内部**两行指向同一个落点**也要拦，与上一条同源但方向不同：预演只比"目标位置上
    #   **已存在**的文件"，而那时目标还不存在 ⇒ 判不出来；真搬的时候后一件会**静默盖掉**
    #   前一件，然后 `_inbox` 一删，两份原件都没了。
    #   最常见的触发路径不是人手写错，而是确认页把两份不同子目录下的**同名**附件渲染成同一个目标。
    by_target = {}
    for rel, target, _role in plan:
        if target:
            by_target.setdefault(target, []).append(rel)
    dup = {t: v for t, v in by_target.items() if len(v) > 1}
    if dup:
        bad = "；".join(f"{t} ← {' 与 '.join(v)}" for t, v in list(dup.items())[:3])
        raise HTTPException(400, f"有 {len(dup)} 处**两行指向同一个落点**（会互相覆盖）：{bad} ——"
                                 "把其中一行的目标路径改掉（例如加上父目录名）再确认")
    # **反向完备性**（与上面两条同一族，后果最重）：上面的校验只管"表里的每一行都在 inbox
    #   里"，**从不检查反方向**。而 `_materialize_inbox` 最后会把整个 `_inbox/` 删掉 —— 于是
    #   只要表**短了一行**，那一份原件既不会被搬（不在 plan 里）、也不会进 `kept/`（那里只收
    #   表里标了 ignore/needs_manual 的）⇒ **直接消失、无任何留痕**。
    #   可达路径不止"人少写一行"：面板按 DOM 行数收集（`_ikCollect`），DOM 表比服务端的
    #   `files` 短时就会少收；CLI/接口调用方同理。所以这一条必须堵在服务端。
    missing = sorted(set(_inbox_files()) - {rel for rel, _t, _r in plan})
    if missing:
        raise HTTPException(
            400, f"确认表里少了 {len(missing)} 份原件：{'、'.join(missing[:5])}"
                 f"{'…' if len(missing) > 5 else ''} —— 确认的最后一步会把整个 `_inbox/` 清掉，"
                 f"没列进表的原件会**直接丢失**（既不会被搬走、也不会留底）。"
                 f"把它们补进表里（标「忽略（不动它）」也行）再确认")
    return plan


def _materialize_inbox(plan, problem_text):
    """按确认表把原件搬到各就各位。**全成或全不动**：任一失败则 inbox 原样保留。

    次序照 `_prepare_workspace`（轮转在搬源之前）与 `delivery.package`（先建新的再切换）：
      ① 先查与**已存在文件**的冲突（同路径同字节放行，否则 400 列出）；
      ② 逐件先写 `.tmp` 再 `os.replace`（跨盘/中断都安全）；
      ③ 逐件核验到位；
      ④ 全过之后才删 `_inbox/`。
    """
    moved, kept = [], []
    # ⓪ 先把**题面正文**定下来并验一遍，再动任何文件。
    #   题面以**人确认过的那份**为准；面板没回传就回退 AI 在 `reports/INTAKE.json` 里给的
    #   `problem.text`。
    #   为什么必须提前：这个函数承诺"**全成或全不动**"，而这里唯一可能以**用户可修复的
    #     400**（题面为空）退出。若把它排在搬运**之后**，一命中就是"文件搬了一半、
    #     `_inbox/` 还没删"，而重试时那些目标已经存在（内容相同会被 ① 放行，不同则报冲突）
    #     ⇒ 用户面对的是一团说不清的状态。
    #   为什么必须**无条件**写：机械读题拆掉之后，这里是 `request/problem.md` 唯一的写点
    #     （从前上传时的机械抽取会先写一份）。详见下面写盘处那段。
    if problem_text is not None:
        t = problem_text
    else:
        _prop = _intake_proposal()
        _pr = _prop.get("problem") if isinstance(_prop.get("problem"), dict) else {}
        t = (_pr or {}).get("text")
    if not str(t or "").strip():
        raise HTTPException(400, "题面文本是空的（AI 的读题结果里也没有题面文本）—— 不能这么确认")
    problem_md = str(t)
    # ① 预演冲突：目标已存在且**内容不同**的，一律拒绝（不许静默覆盖）
    for rel, target, role in plan:
        if not target:
            continue
        src, dst = ROOT / rel, ROOT / target
        if dst.exists() and dst.is_file() and src.is_file() and dst.read_bytes() != src.read_bytes():
            raise HTTPException(
                400, f"「{target}」已经有一份不一样的文件了 —— 不覆盖。"
                     f"把目标改个名（或先删掉旧的）再确认")
    # ②③ 逐件落盘 + 核验
    for rel, target, role in plan:
        src = ROOT / rel
        if not target:
            kept.append(f"{rel}（{role}，留在 _inbox 里不动）")
            continue
        dst = ROOT / target
        try:
            dst.parent.mkdir(parents=True, exist_ok=True)
            tmp = dst.with_name(dst.name + ".tmp-intake")
            tmp.write_bytes(src.read_bytes())
            os.replace(tmp, dst)
        except OSError as exc:
            raise HTTPException(500, f"搬运失败（{rel} → {target}）：{exc}"
                                     f" —— `_inbox/` 未删，修好后可重新确认") from exc
        if not dst.is_file() or dst.stat().st_size != src.stat().st_size:
            raise HTTPException(500, f"搬运后核验不过（{target}）—— `_inbox/` 未删，可重试")
        moved.append({"from": rel, "to": target, "role": role})
        if role == "problem":
            # 题面同时留一份规范名（今天 `kind=problem` 就是这么落 `request/problem.pdf` 的）
            ext = Path(rel).suffix.lower()
            pr = ROOT / "request" / ("problem" + ext)
            try:
                pr.write_bytes(dst.read_bytes())
            except OSError as exc:                       # noqa: BLE001
                log(f"⚠️ 题面副本写不进去（{pr.name}）：{exc}")
    # 题面正文（内容与空判已在函数开头做完）—— **无条件**写。
    # 这里是**无条件**写的，不能写成 `if problem_text is not None:` —— 从前**上传时的机械抽取**
    #   必然已经写过一份 `request/problem.md`，那一步只是"人改过就覆盖"；机械读题拆掉之后，
    #   这里成了**唯一**的写点 ⇒ 面板没回传（用户没动过那个框、或走的是 CLI/接口）就一个字
    #   都不写，而 `content_quality._evidence()` 硬判 `source.file` 必须位于 `request/` 下并
    #   逐字读它、`verify` 门禁的机械地板也依赖它 ⇒ **①–⑯ 全部失去题意锚点**，
    #   且这里不报错，要等门禁以"找不到题面原文"的形式炸。
    #   `regression/test_intake.py::test_confirm_writes_the_problem_even_when_the_panel_sends_nothing`
    #   钉着这条。
    (ROOT / "request").mkdir(exist_ok=True)
    (ROOT / "request" / "problem.md").write_text(problem_md, encoding="utf-8")
    # ④ 先给"留着不动"的那几件搬个家，再删 inbox：
    #    直接 `rmtree(_inbox)` 会把 `ignore`/`needs_manual` 的原件**一起删掉** —— 而人明确
    #    选了"不动它"（比如一个 `.zip` 压缩包、别人的旧文件），不该被静默销毁。
    #    挪到 `runtime/quality/intake/kept/`：那儿既不在轮转的 RELS 里、也不在输入指纹里，
    #    而且在确认页/日志里说得清它被放到哪了。
    if kept:
        keep_dir = INTAKE_DIR / "kept"
        keep_dir.mkdir(parents=True, exist_ok=True)
        for rel, _target, role in plan:
            if _target:
                continue
            src = ROOT / rel
            if not src.is_file():
                continue
            dst = keep_dir / Path(rel).relative_to(INBOX_REL)
            try:
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
            except OSError as exc:                       # noqa: BLE001
                log(f"⚠️ 留着不动的原件搬不进 {keep_dir}（{rel}）：{exc}")
    # ⑤ 全过之后才删 inbox（`ignore`/`needs_manual` 的那几件已经搬到 kept/ 了 —— 留在
    #    inbox 里只会让 `_intake_unconfirmed()` 永远为真）
    shutil.rmtree(_inbox_path(), ignore_errors=True)
    return {"moved": moved, "kept": kept,
            "kept_dir": "runtime/quality/intake/kept" if kept else ""}


def _record_confirmation(plan, problem_text, corrections, run_id):
    """写确认留痕（专用目录，别混进 attest 的 manual/）。返回记录。"""
    human_edits = []
    prop = _intake_proposal()
    ai_roles = {}
    for item in (prop.get("files") or []):
        if isinstance(item, dict):
            ai_roles[str(item.get("path") or "").replace("\\", "/")] = str(item.get("role") or "")
    for rel, target, role in plan:
        was = ai_roles.get(rel) or ai_roles.get(Path(rel).name) or ""
        if was and was != role:
            human_edits.append(f"{Path(rel).name}：AI 判 {was} → 人改 {role}")
    rec = {
        "stage": "intake",
        "at": datetime.now().isoformat(),
        "run_id": run_id,
        # digest 必须取**搬完之后**的 `_source_digest()`：确认之后链真正吃的就是这份输入，
        #   而 `_intake_unconfirmed()` 是拿它跟当前盘面比的（差一位就要求重新确认）。
        "digest": _source_digest(),
        "problem_sha256": hashlib.sha256(str(problem_text or "").encode("utf-8")).hexdigest(),
        "table": [{"path": r, "target": t, "role": g} for r, t, g in plan],
        "human_edits": human_edits,
        # 键名必须是 `corrections`：`_intake_hint`（交给 ① 的那段提示）读的就是它。
        #   写单边（这里叫 `note`、那边读 `corrections`）会让人在确认页写的"更正说明"
        #   **从来没进过 ①**。两处必须对齐，改的时候别只改一边。
        "corrections": corrections or "",
    }
    INTAKE_DIR.mkdir(parents=True, exist_ok=True)
    atomic_json(INTAKE_DIR / "confirmed.json", rec)
    return rec


def _append_confirm_section(rec):
    """往 `reports/INTAKE_REPORT.md` 追加一段人工确认记录（照 `_append_residual` 的惯例：
    追加、带机器可 grep 的标记）。给提交件与评委看"题面读法经人工核对"。"""
    p = ROOT / INTAKE_REPORT_REL
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [f"\n\n## [HIL-CONFIRM {stamp}] 人工确认", "",
             f"- 确认时间：{rec['at']}（run_id={rec['run_id']}）",
             f"- 题面文本哈希：`{rec['problem_sha256'][:16]}`"]
    if rec["human_edits"]:
        lines.append("- 人工改过分类：" + "；".join(rec["human_edits"]))
    else:
        lines.append("- 人工改过分类：无（与 AI 的判定一致）")
    if rec.get("corrections"):
        lines += ["", "人工更正说明：", "",
                  "> " + str(rec["corrections"]).replace("\n", "\n> ")]
    try:
        with open(p, "a", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
    except OSError as exc:                               # noqa: BLE001
        log(f"⚠️ 确认记录追加不进 {INTAKE_REPORT_REL}：{exc}")


async def _do_intake_confirm(stage, p, req):
    """`/api/decision` 的 `confirm` 分支：把确认页的结果落到盘上，然后从 ① 起跑。"""
    if not (ROOT / INTAKE_JSON_REL).is_file():
        raise HTTPException(400, "AI 的读题结果不在盘上（缺 reports/INTAKE.json）"
                                 "—— 先点「再试一次」让它读一遍")
    plan = _validate_roles(req.roles or [])
    made = _materialize_inbox(plan, req.problem_text)
    rec = _record_confirmation(plan, req.problem_text, req.corrections, state.get("run_id", ""))
    _append_confirm_section(rec)
    # 快照必须放在**追加人工确认段之后**：快照是"轮转之后幸存的唯一一份"，提交件与 ① 读
    #   的都是它 ⇒ 它得带上 `[HIL-CONFIRM …]` 那段，否则"题面读法经人工核对"这件事在
    #   交付物里看不出来。
    _snapshot_intake()
    _record_quality(stage, "confirmed",
                    f"人工确认读题（题面 {len(str(req.problem_text or ''))} 字；"
                    f"搬运 {len(made['moved'])} 件；人工改过 {len(rec['human_edits'])} 项）")
    state.setdefault("seed_hints", {})["literature"] = _intake_hint()
    _set_pending(None)
    log("✅ [intake] 读题结果已人工确认 → 搬运 " + str(len(made["moved"])) +
        f" 件、inbox 已清；从 ① 文献定向 起跑（读题结论快照在 runtime/quality/intake/）")
    return {"ok": True, "action": "confirm",
            "resume_from": "literature", "resume_index": STAGE_IDX["literature"],
            "resumed": True}


def _driver_exc_text(exc):
    """兜底 except 里那句"驱动异常"的人话 —— **一定带上异常类型名**。

    为什么不能只写 `f"驱动异常：{exc}"`：`StopIteration`、`KeyError` 这类异常
      异常**自己的 `str()` 是空的** ⇒ 面板上只剩「驱动异常：」四个字 + 什么都没有，
      既看不出是驱动挂了还是阶段挂了，也看不出挂在哪一步 —— 查不出原因的哑谜。
      真实代价：三个阶段状告"never_collects"的用例被这个噎住之后，`assert_not_called`
      照样通过，于是它们**恒真**了好几个月没人发现（见 `_stage_index` 那段）。
    """
    msg = str(exc).strip()
    return f"驱动异常：{type(exc).__name__}" + (f"：{msg}" if msg else "（这个异常自己不带消息）")


def _halt(stage, reason, status="blocked", *, kind="failure", decision=None, tail=None, handback=None):
    """挂起并转黄灯等人工决策。

    技术状态（failed/unverified/blocked）降级存进 pending["status"]，
      `state["stages"][sid]` 统一置 `awaiting_user` —— 前端据此显示黄灯。
      events.jsonl 仍按技术状态记一条，保留「这一步技术上确实失败了」这个事实。
    """
    sid = stage["id"]
    if tail is None:
        # run_stage 失败时把原始输出留在 state["last_tail"] —— 重试的 prompt 必须带上它，
        # 否则就是把同一个 prompt 原样再发一遍，大概率同样失败。
        tail = state.get("last_tail", "")
    state["halt_gate"] = True
    state["halt_reason"] = reason
    try:
        p = _build_pending(stage, kind, status, reason, decision=decision, tail=tail, handback=handback)
    except Exception as exc:
        log(f"（待决策上下文构造失败：{exc}）")
        p = None
    _set_pending(p)
    # 托管：只**置位**，不在这里落实。`_halt` 是在 `run_all` 内部调的，那一刻 `running`
    #   还是 True ⇒ `_apply_decision` 会以"链正在运行"回 409、`_start_chain` 也会抢 state。
    #   真正的落实在 `run_all` 的 finally（那里 `running` 已置 False）。
    if p is not None and state.get("autopilot"):
        state["autopilot_armed"] = True
    state["stages"][sid] = "awaiting_user"
    _record_quality(stage, status, reason)
    log(f"{sid} 挂起：{reason}；保留草稿，不收集为正式交付。**等待人工决策**。")
    _tick(sid)
    try:
        _write_hil_decision(stage, reason, p)
    except Exception as exc:            # 决策清单生成失败不影响挂起语义
        log(f"（人工决策清单生成失败：{exc}）")
    try:
        emit("pending", state2dict())   # 面板立刻出现，不等 run_all 的 finally（最坏会晚 WAIT_AFTER_KILL 秒）
    except Exception:
        pass

# ---------------- Windows 存活探测（ctypes，无第三方依赖） ----------------
# 目的：区分「子进程真在远程长推理（握着 ESTABLISHED 连接）」与「代理静默掐断连接后子进程干等假死」。
_tcp_pid_cache = None
def _established_tcp_pids():
    """返回持有任意 ESTABLISHED TCP 连接的 PID 集合（GetExtendedTcpTable）。"""
    global _tcp_pid_cache
    if _tcp_pid_cache is not None:
        return _tcp_pid_cache
    sz = wintypes.DWORD(0)
    fn = ctypes.windll.iphlpapi.GetExtendedTcpTable
    fn(None, ctypes.byref(sz), False, 2, 5, 0)                     # AF_INET, TCP_TABLE_OWNER_PID_ALL
    buf = ctypes.create_string_buffer(max(int(sz.value), 256))
    r = fn(ctypes.cast(buf, ctypes.c_void_p), ctypes.byref(sz), False, 2, 5, 0)
    pids = set()
    if r == 0:
        n = ctypes.c_ulong.from_buffer(buf).value
        for i in range(n):
            off = 4 + i * 24
            if off + 24 > len(buf): break
            row = (ctypes.c_ulong * 6).from_buffer(buf, off)
            if row[0] == 5:                                        # MIB_TCP_STATE_ESTABLISHED
                pids.add(row[5])
    _tcp_pid_cache = pids
    return pids

def _refresh_tcp():
    global _tcp_pid_cache
    _tcp_pid_cache = None
    return _established_tcp_pids()

def _proc_cpu_seconds(pid):
    """进程累计 CPU 秒；进程已退出/查不到返回 None。"""
    h = ctypes.windll.kernel32.OpenProcess(0x1000 | 0x00100000, False, pid)  # QUERY_LIMITED|SYNCHRONIZE
    if not h:
        return None
    try:
        c, e, k, u = wintypes.FILETIME(), wintypes.FILETIME(), wintypes.FILETIME(), wintypes.FILETIME()
        if not ctypes.windll.kernel32.GetProcessTimes(h, ctypes.byref(c), ctypes.byref(e), ctypes.byref(k), ctypes.byref(u)):
            return None
        def _s(ft): return (ft.dwHighDateTime << 32 | ft.dwLowDateTime) / 1e7
        return _s(k) + _s(u)
    finally:
        ctypes.windll.kernel32.CloseHandle(h)

def _snapshot_pids():
    """{pid: ppid} 快照（CreateToolhelp32Snapshot），用于找进程树的全部后代。"""
    procs = {}
    INVALID = wintypes.HANDLE(-1).value
    snap = ctypes.windll.kernel32.CreateToolhelp32Snapshot(0x2, 0)   # TH32CS_SNAPPROCESS
    if snap in (None, INVALID, 0): return procs
    class PE(ctypes.Structure):
        _fields_ = [("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD),
                    ("th32ProcessID", wintypes.DWORD),
                    ("th32DefaultHeapID", ctypes.POINTER(ctypes.c_ulong)),
                    ("th32ModuleID", wintypes.DWORD), ("cntThreads", wintypes.DWORD),
                    ("th32ParentProcessID", wintypes.DWORD), ("pcPriClassBase", ctypes.c_long),
                    ("dwFlags", wintypes.DWORD), ("szExeFile", ctypes.c_wchar * 260)]
    try:
        e = PE(); e.dwSize = ctypes.sizeof(PE)
        ok = ctypes.windll.kernel32.Process32FirstW(snap, ctypes.byref(e))
        while ok:
            procs[int(e.th32ProcessID)] = int(e.th32ParentProcessID)
            ok = ctypes.windll.kernel32.Process32NextW(snap, ctypes.byref(e))
    except Exception:
        pass
    finally:
        ctypes.windll.kernel32.CloseHandle(snap)
    return procs

def _tree_cpu_seconds(pid):
    """进程树(claude + 它 spawn 的全部子进程)的累计 CPU 秒。计算子进程在烧 CPU 时也算"活着"，
    避免 claude 空闲等本地长计算却被误判假死。取不到则退回只看单进程。"""
    try:
        procs = _snapshot_pids()
        desc = set()
        stack = [pid]
        while stack:
            p = stack.pop()
            for k, v in procs.items():
                if v == p and k not in desc and k != pid:
                    desc.add(k); stack.append(k)
    except Exception:
        return _proc_cpu_seconds(pid)
    total = 0.0; seen = False
    for p in ([pid] + sorted(desc)):
        s = _proc_cpu_seconds(p)
        if s is not None:
            total += s; seen = True
    return total if seen else None

def _kill_tree(pid):
    try:
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)],
                       capture_output=True, timeout=20)
    except Exception:
        pass

# ---------------- claude 调用（线程读 stdout + 异步看门狗判活/强杀） ----------------
def _claude_worker(cmd, sh):
    """在线程里跑 claude。Windows 事件循环对管道 readline 的 wait_for 取消不可靠，
    故把阻塞读取移出事件循环；看门狗在外部用 ctypes 探测子进程是否真在干活。
    线程内只往 sh 里写（GIL 保护下安全），日志交给主循环定时排空（emit 只能在事件循环线程）。"""
    # 出站代理：**只把 API 端点摘出代理**（规则、真因与原来那版的毛病见上面
    # `_apply_proxy_policy()` 那段）。模块级已经改过 `os.environ`，这里这份拷贝自然带着；
    # 再调一次是**幂等**的兜底 —— `_claude_worker` 是可被单测直接调用的入口，
    # 而单测（以及任何 import 后才设 `ANTHROPIC_BASE_URL` 的用法）晚于模块级那次。
    env = os.environ.copy()
    _apply_proxy_policy(env)
    # 必须关掉 CLI 的「等后台任务」10 分钟上限，否则门禁阶段会被**静默掐死**。
    #   3Modeling-review-gate / 10Math-proof-gate / 11Cross-question-check / 12Rubric-final 的 SKILL 都要求「并行 spawn N 个
    #   独立子 agent 分维度审」；Agent 工具默认 run_in_background=true，于是主 agent 的回合在
    #   "等子 agent"处结束，`claude -p` 进入等待。CLI 那边默认等 600s 就打印
    #     「Background tasks still running after 600s; terminating.」
    #   然后**直接结束整个 -p 会话**——子 agent 被杀、主 agent 再没机会写报告、进程 rc=0。
    #   表现为：`review 执行第 1 次失败 rc=0 stalled=False artifact=False`——一个"成功退出却没产物"
    #   的哑谜，日志里查不出原因（进程 rc=0 正常退出，报告文件却从未写出）。
    #   注意 600s 是 CLI 自己起算的，与阶段真实进度无关：子 agent 陆续回来、主 agent
    #   只要还在等，到点就整个 -p 会话被终止。
    #   设 0 = 无限等。**不会**因此无限挂起：本驱动的看门狗仍在管——无输出且无 CPU 且无连接
    #   满 STALL_SILENT=300s（或有连接满 STALL_CONN=1200s）→ 转黄灯交人工；墙钟上限
    #   _effective_limits 默认 30 分钟 → 同样转黄灯（OVERTIME_KILL=False 不杀，等你决定）；
    #   /api/stop 与「取消并重试」随时强杀进程树。这些都比 CLI 那个 600s 更懂"慢但在干活"。
    env["CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS"] = "0"
    p = subprocess.Popen(cmd, cwd=str(ROOT), stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, env=env)
    sh["pid"] = p.pid
    # 登记 pid：服务被外部强杀时子进程会变孤儿，下次启动靠这份登记把它们收掉。
    _register_stage_pid(p.pid)
    short = lambda s, n=110: (s or "").replace("\n", " ")[:n]
    L = sh["lines"].append
    tail = ""
    sid = sh["sid"]
    try:
        for raw in io.TextIOWrapper(p.stdout, encoding="utf-8", errors="replace"):
            sh["last_out"] = time.time()
            # 把 tail **边跑边**发布到 sh，不能只在收尾时 `sh["tail"] = tail`：超时黄灯是在
            #   进程**还活着**时构造的（_call 里读 `sh.get("tail","")`）⇒ 只在收尾发布的话，
            #   空 tail，`_parse_scale_estimate` 恒 None，面板永远显示「无法预估剩余时间」，
            #   而 stage_discipline.md 第二节明确要求驱动从输出里抓 `[SCALE_ESTIMATE]` 给用户看。
            #   放在循环开头发布，最多滞后一轮，无所谓。
            sh["tail"] = tail
            raw = raw.strip()
            if not raw:
                continue
            try:
                obj = json.loads(raw)
                msg = obj.get("message") or {}
                content = msg.get("content", []) or []
                if isinstance(content, str):
                    if content.strip(): tail = (tail + content)[-4000:]
                    continue
                for c in content:
                    if not isinstance(c, dict): continue
                    if c.get("type") == "text" and c.get("text", "").strip():
                        tail = (tail + c["text"])[-4000:]
                    elif c.get("type") == "tool_use":
                        nm = c.get("name", "")
                        # 名字白名单**不许有**。只记某几个名字的话，`PowerShell`/`Grep`/`Glob`
                        #   的调用**一条都不进日志** —— 唯一的痕迹是它报错时那条「工具报错」日志行
                        #   （那里只看 is_error）。而日志是**唯一**的事后依据：漏记之后，
                        #   "日志里没有"会被读成"没发生"，连"某个阶段自己搬过文件"都看不出来
                        #   （典型的误判形态：以为是回退的暂存没搬走，实际是它自己搬回来的）。
                        #   所以跑过的每条工具调用都要留痕，不许按名字挑着记。`short()` 已限长。
                        arg = c.get("input", {})
                        a = short(str(arg.get("command") or arg.get("file_path")
                                       or arg.get("pattern") or arg.get("description") or arg))
                        L(f"  🛠 [{sid}] {nm}: {a}")
                    elif c.get("type") == "tool_result" and c.get("is_error"):
                        e = short(str(c.get("content", ""))[-400:])
                        L(f"  ✗ [{sid}] 工具报错: {e}")
            except Exception:
                # 非 JSON 行：可能是 claude 报错/提示，保留供诊断
                if raw:
                    tail = (tail + raw)[-4000:]
                    if any(k in raw for k in ("Error", "error", "失败", "denied")):
                        L(f"  ⚠ [{sid}] 非JSON: {short(raw, 160)}")
    except Exception as exc:
        # 不能裸 `pass`：worker 里除 Popen 之外的任何异常（读管道出错、解码、p.wait 竞态）
        #   若不留痕迹，`_call` 只还回 (-1, "", False)，run_stage 只打一句
        #   「执行第 1 次失败 rc=-1 stalled=False artifact=False」—— 诊断为空，人查不出原因。
        L(f"  ✗ [{sid}] 读输出线程异常: {type(exc).__name__}: {str(exc)[:200]}")
    try:
        p.wait()
    except Exception as exc:
        L(f"  ⚠ [{sid}] 等待进程退出时异常: {type(exc).__name__}: {str(exc)[:120]}")
    sh["rc"] = p.returncode if p.returncode is not None else -1
    sh["tail"] = tail
    sh["done"] = True

# ---------------- 运行参数：默认值在代码里，可被 `.env` / 环境变量覆盖 ----------------
# 为什么放 `.env` 而**不是** `config/runtime.local.json`：后者被整份哈希进 ④ 及下游的
#   **输入指纹**（见 `_env_identity`）—— 往那儿加一个旋钮 = 动一下就让 ④ 起整链重跑。
#   `.env` 不进任何阶段的指纹 ⇒ 改它只影响驱动自己，重启即生效。
# 默认值与代码里那一版**一字不差** ⇒ 不填 = 老行为，没有任何既有回执因此失配。
# 填了但填错（不是数字）⇒ 用默认值并在启动日志里报一行，**不**让驱动起不来。
_RUNTIME_ENV_BAD = []


def _num(name, default):
    """读一个数值型运行参数（秒/次数）。空 = 用默认；非法值 = 用默认**并记一行**。"""
    raw = (os.environ.get(name) or "").strip()
    if not raw:
        return default
    try:
        return int(float(raw))              # 容忍 `1800` 与 `1800.0`
    except ValueError:
        _RUNTIME_ENV_BAD.append(f"{name}={raw!r} 不是数字 ⇒ 用默认 {default}")
        return default


def _flag(name, default):
    """读一个开关。认 `1/true/yes/on` 与 `0/false/no/off`；别的值用默认并记一行。"""
    raw = (os.environ.get(name) or "").strip().lower()
    if not raw:
        return default
    if raw in ("1", "true", "yes", "on"):
        return True
    if raw in ("0", "false", "no", "off"):
        return False
    _RUNTIME_ENV_BAD.append(f"{name}={raw!r} 不是开关值（1/0/true/false）⇒ 用默认 {default}")
    return default


STALL_SILENT = _num("FMA_STALL_SILENT", 300)   # 无输出+无连接+无CPU 连续这么久 → 判假死
STALL_CONN = _num("FMA_STALL_CONN", 1200)      # 仅有半开连接而无输出/CPU 的最长容忍
STALL_SAMPLE = _num("FMA_STALL_SAMPLE", 5)     # 看门狗采样间隔（秒）

# ---- 人工决策（黄灯）----
MAX_ATTEMPTS_PER_STAGE = 1   # 每阶段只执行 1 次：失败即转黄灯交用户决定（见 CLAUDE.md 工作流说明）
# 「延长本次限时」的口径：
#     默认 30 分钟 → 到点亮黄灯问 → 你**追加** 10 分钟 ⇒ 本次临时上限 40 分钟
#     → 40 到点**再问一次** → 再追加…（反复迭代，直到 CALL_HARD_CAP）
#     这一轮的临时上限**只属于这一次执行**：`run_stage` 收尾会 pop 掉，下次重跑退回 30。
#
#   默认上限与延长天花板必须是**两个**量：合成一个 `RETRY_CAP_MAX = 1800`（既是默认上限、
#   又是天花板）会让「延长」**永远延不出去**；而 extend 若实现成**替换**
#   （`retry_cap = 你填的值`），填 10 就把上限从 30 **缩短**成 10 —— 与按钮上的「延长」二字
#   正好相反，且已跑过的时间仍算数 ⇒ 超限条件恒成立，那一轮等于被直接掐死。
RETRY_CAP_DEFAULT = _num("FMA_RETRY_CAP_DEFAULT", 1800)   # 不延长时的单次墙钟上限 = 30 分钟
RETRY_CAP_EXTRA_MAX = _num("FMA_RETRY_EXTRA_MAX", 3600)   # 一次「延长」最多**追加**多少 = 60 分钟
#   这个常量是**唯一出处**：面板输入框的 max 由 /api/hil 里 `retry_extra_max` 下发
#     （index.html 把它写进 `$('dc_cap').max`），前端提交时的钳位也照那个 max 走。
#     别在 HTML 或 JS 里再写一个硬编码的 30 —— 改一处不改另一处会出现"能填 60 但只发 30"。
RETRY_CAP_EXTRA_MIN = _num("FMA_RETRY_EXTRA_MIN", 600)    # 一次「延长」至少追加多少 = 10 分钟
# 天花板压在 CALL_HARD_CAP（3h）：那本来就是单次调用的墙钟硬上限，再高也没意义。
# （假死容忍**不跟**这个上限走 —— 它封在 STALL_SILENT / STALL_CONN，见 _effective_limits。）
RETRY_CAP_MAX = _num("FMA_RETRY_CAP_MAX", 10800)          # 反复延长后的**总上限天花板**
RETRY_CAP_MIN = RETRY_CAP_EXTRA_MIN          # 兼容旧名：等于 RETRY_CAP_EXTRA_MIN
# 超限（墙钟上限 / 假死）时是否仍强杀。False = 转黄灯但让任务继续跑，由用户决定（默认）；
# 置 True 则退回旧行为（立即强杀并走失败路径）。
OVERTIME_KILL = _flag("FMA_OVERTIME_KILL", False)
# 环境类错误（claude 路径失效）自动重试一次，不打扰用户 —— 这不是阶段失败
AUTO_RETRY_ENV_ERROR = _flag("FMA_AUTO_RETRY_ENV_ERROR", True)
CALL_HARD_CAP = _num("FMA_CALL_HARD_CAP", 10800)   # 单次 claude 调用硬上限（秒）= 3h。抬高它的唯一理由是：
                        # **这个上限拦的是"慢但真在干活"，不是假死** —— 真假死由看门狗负责（无输出+无
                        # CPU+无连接 300s；仅有连接宽限 STALL_CONN=1200s），比它灵敏得多。下面这一例：
                        # code 跑 112min 仍在做真活（网格 N 400→3200、长时间步 60→5s、26 项校验、
                        # 重导 result1-4.xlsx），被 120min 掐断后重试要从头读上下文+重写报告，
                        # 代价远超多等 30 分钟。改需重启生效。
CALL_PROTOCOL_CAP = _num("FMA_CALL_PROTOCOL_CAP", 900)  # 协议级修复（只补写 .verdict.json）的短上限
WAIT_AFTER_KILL = _num("FMA_WAIT_AFTER_KILL", 60)       # 看门狗强杀后最多再等读循环结束多久（秒）


# ---------------- 人工决策（黄灯）：上限、预估解析、待决策上下文 ----------------

# 单次墙钟上限的**按阶段默认值**。只有一个全局默认（30 分钟）时，
#   各阶段的固有耗时差着一个量级：④ 编码计算实测一轮 **51.9 min**（`tmp/repair/run_all_r3.log`
#   的「== 完成：总用时 3113.7 s ==」）⇒ **每轮必然**弹一次超时黄灯要人点「延长」
#   而「🛑 停止」就在同一面板上 —— 离丢掉整段重算只差一次点错，所以这个默认值必须按阶段给。
#   这里只给**有实测证据**的阶段抬高默认值；用户点过「延长」仍以他的值为准，
#   天花板仍是 `RETRY_CAP_MAX`。
#   **别因此关掉这盏灯**：它管的是"长时间没动静"，该看见的时候还得看见（假死由
#      `STALL_SILENT`/`STALL_CONN` 管，比它灵敏得多）。想全局调就改 `.env` 的
#      `FMA_RETRY_CAP_DEFAULT`；想给别的阶段也抬，往这张表里加。
STAGE_CAP_DEFAULT = {"code": 5400}          # ④：90 分钟（实测 51.9 min 的 1.7 倍）


def _default_cap(sid):
    """该阶段**不延长时**的默认墙钟上限（秒）。**单一出处** ——
    `_effective_limits` 与面板下发的 `retry_cap_default` 都走它，否则会出现
    「面板说默认 30 分钟、实际给 ④ 的是 90 分钟」这种自相矛盾。"""
    return STAGE_CAP_DEFAULT.get(sid) or RETRY_CAP_DEFAULT


def _effective_limits(sid, cap=None, has_conn=False):
    """本次调用实际生效的 (墙钟上限, 静默容忍)。

    用户点「延长本次限时」会把覆盖值写进 state["retry_cap"][sid]；这里**每轮现读**——
    与 state["stopping"] 同一范式，所以看门狗每 5s 采样都能拿到最新值，
    「点了按钮就救回正在跑的那一次」由此成立。

    cap（协议级修复的短上限）优先于用户覆盖：格式修复不该被延长到几小时。

    **墙钟上限与假死容忍是解耦的**。不要把用户给的总时长也拿去抬静默容忍，理由曾是
      "否则 STALL_CONN=1200 会先于 CALL_HARD_CAP 触发，用户设的 3 小时等于没设" ——
      这条不成立：先触发只是**问你一次**（黄灯不杀进程，任务照跑），而绑在一起的
      代价是**真·死进程要等满上限才被发现** —— 上限能一路追加到 3 小时，就是瞎等 3 小时。
      所以：上限可以往上追加，假死容忍**封在 STALL_SILENT / STALL_CONN**。
      代价如实说：慢但在等 API 的阶段会每 20 分钟亮一次黄灯问你，答一次「再延长」继续。
    """
    override = (state.get("retry_cap") or {}).get(sid)
    # 不给延长的**默认**上限是 RETRY_CAP_DEFAULT（30 分钟）；用户延长过就用他的（已累加），
    # 两者都夹在 RETRY_CAP_MAX（= CALL_HARD_CAP）之内 —— 天花板高于默认值，
    # 「延长」才真的能延长（两者同为 1800 时等于延不动）。
    cap_s = min(cap or override or _default_cap(sid), RETRY_CAP_MAX)
    limit = STALL_CONN if has_conn else STALL_SILENT
    return cap_s, limit


SCALE_RE = re.compile(r"\[SCALE_ESTIMATE\]\s*scale=([\d.]+)\s+elapsed=([\d.]+)s\s+total_est=(\d+)s")


def _parse_scale_estimate(text):
    """从子进程输出里抓最近一条 [SCALE_ESTIMATE] 行（SKILL 要求长脚本打印）。

    抓不到返回 None —— 面板就写「该阶段无法预估剩余时间」，**不编数字**。
    """
    hits = SCALE_RE.findall(text or "")
    if not hits:
        return None
    scale, elapsed, total = hits[-1]
    return {"scale": float(scale), "elapsed_s": float(elapsed), "total_est_s": int(total)}


def _code_fp():
    """code/ 目录指纹。注入 prompt 供 SKILL 写进产物 .meta.json 的 _code_fp，
    使「方法变没变」在产物层面可机器比对（详见 _references/stage_discipline.md 第四节）。"""
    try:
        return fingerprint(ROOT, ["code"])[:12]
    except Exception:
        return ""


def _default_repair_target(stage_id):
    """门禁失败时的默认回退目标。这张表与 STAGES[].gate 字符串必须一致，
    由 regression 的 test_gate_strings_agree_with_default_repair_map 强制。"""
    return {"review": "analysis", "audit": "code", "mathproof": "write",
            "cross": "write", "verify": "format", "rubric": "fix",
            # 图的缺陷只回 ⑦：它是唯一产出图的**前序**阶段（数据图来自 ④，真需要时由 ⑦
            # 写 HANDBACK_REQUEST 交回）。这也是它比"把 ⑦ 自己变成门禁"好的地方 ——
            # 门禁的 target 必须是前序阶段，⑦ 不能指自己。
            "figreview": "drawio"}.get(stage_id)


def _rubric_hands_off():
    """12Rubric-final 有没有 must/fatal 判词要 13Repair-by-rubric-verdict 处理？没有就该跳过 fix（省一次 agent 调用）。

    **现读裁决，不看内存标志**：断点续跑时 rubric 靠回执被跳过、`state["fix_required"]`
      是空的，用标志判会把该做的返修一起跳掉。
    只在裁决**明确通过**（PASS/APPROVED/CLEAN）且没有未解决项时才跳过。
      读不出来、UNVERIFIED、裁决缺失 → 一律返回 True（要跑）—— **宁可多跑一次 fix，
      也不要漏掉该做的返修**。
    """
    stage = next((s for s in STAGES if s["id"] == "rubric"), None)
    if stage is None:
        return True                     # 没有 rubric 阶段 → 不做跳过判断
    # ⑫ 已被人「接受并披露 / 豁免」⇒ ⑬ 也跳过：⑬ 只是 ⑫ 的工具步骤，跳过 ⑫ 就该跟着
    #   跳过 ⑬。豁免后裁决里那条 FAIL 还在，只看裁决会误判成"要修"。
    if str(state["stages"].get("rubric") or "").startswith("done(disclosed"):
        return False
    try:
        decision = _gate_decision(stage)
    except Exception:
        return True
    if decision.get("status") not in {"PASS", "APPROVED", "CLEAN"}:
        return True
    return bool(decision.get("issues"))


# ---------------- 人工定点修复后的重新认证（attest）----------------
# 问题：回执答的是「盘面跟上次成功时一样吗」。人工修好的产物，答案必然是「不一样」——
# 于是驱动认为该阶段需要重做，而重做恰恰要**推翻刚做好的人工修正**。回执模型在
# 「人工修改」这一种情况下是反的。
#
# 这件事必须有**一等**的动作，不能靠手改 runtime/quality/stages.json 绕过 —— 手改容易
# 把别的工程的旧产物从 cache 里按文件名捞回来。`attest` 就是为此设的。
MANUAL_DIR = LOG_DIR / "quality" / "manual"


# 每个阶段对应哪些**客观校验**。空列表 = 该阶段本来就没有客观可验的东西
# （纯文稿类：文献方向、数学论证、跨问一致性）—— 那时由人来担这个判断，不阻塞。
#
# 必须**按阶段**选，不能一把梭全跑：这几个校验都是**全工作区级**的
#   （result_contract 查 results/、publication 查 paper/、visualization 查 figures/）。
#   全跑的话，认证任何一个阶段都会被**与它无关**的过期图/过期结果挡死 ——
#   例如上一轮留下的 7 张图快照过期，会让连 `attest literature` 这样的纯文稿阶段都被拒。
#   那样 attest 在中途基本没法用，等于没做。
_MANUAL_CHECK_FOR = {
    "analysis":   ["task_contract", "receipt_ledger"],
    "review":     ["task_contract"],
    "code":       ["result_contract", "visualization"],
    "robustness": ["result_contract"],
    "audit":      ["result_contract"],
    "drawio":     ["visualization"],
    "write":      ["publication", "visualization"],
    "format":     ["publication", "visualization"],
    "mathproof":  [], "cross": [],
    "verify":     ["publication", "visualization", "result_contract"],
    "fix":        ["publication", "visualization"],
    "literature": [], "demo": [],
}


def _manual_checks(stage_id):
    """人工认证前必跑的**客观校验**（按阶段选，见 `_MANUAL_CHECK_FOR`）。

    返回 {"ran": [...], "failed": [...]}。原则：**能客观验的必须验，验不过就不许认证** ——
    否则等于替驱动撒谎，重演 `reports/_KNOWN_WRITING_RESIDUALS.md` §0 记的那次
    「人手改 verdict 洗成 PASS」。但**没得验的就不验**，不能拿无关阶段的检查当门。
    """
    ran, failed = [], []
    want = _MANUAL_CHECK_FOR.get(stage_id, [])

    def run(label, fn):
        try:
            problems = fn()
        except Exception as exc:                     # 跑不起来也算失败，不放行
            failed.append(f"{label} 无法执行：{exc}")
            return
        ran.append(label)
        if problems:
            failed.append(f"{label}：{'; '.join(str(p) for p in problems)[:400]}")

    if "result_contract" in want and (ROOT / "config/result_contract.json").exists():
        run("result_contract audit", lambda: audit_results(ROOT, rendered=False))
    if "publication" in want and (ROOT / "config/publication.json").exists() \
            and (ROOT / "paper" / "main.pdf").exists():
        run("publication check", lambda: audit_publication(ROOT))
    if "visualization" in want and (ROOT / "config/visualization.json").exists() \
            and (ROOT / "figures" / "manifest.json").exists():
        run("visualization audit", lambda: audit_figures(ROOT))
    if "task_contract" in want and (ROOT / "config/content_quality.json").exists() \
            and (REPORTS / "TASK_CONTRACT.json").exists():
        run("task contract", lambda: task_contract_issues(ROOT))
    # 人工认证也不能替"返修记录自证"背书：探针只在版本/返修记录里出现 = 正文没改。
    if "receipt_ledger" in want and (ROOT / "config/content_quality.json").exists():
        run("receipt ledger", lambda: receipt_ledger_issues(ROOT))
    return {"ran": ran, "failed": failed}


def _taken_over(idx, store):
    """本阶段的「产物变了」是否已被某个**后序阶段**的合法回执解释掉？

    典型情形：`format` 的职责就是改 `write` 写出来的 `paper/`（浮体位置、表宽、溢出压缩）。
    format 跑完且回执有效之后，write 自己的产出指纹必然与它上次成功的回执对不上 ——
    但那是 **format 干的**，不是「有人改了 write 的产物」。不排除的话：
      · 面板会永久把 `产物已改` 挂在 write 头上（本文件自己的注释说这个标记的用途是
        「人工改过哪个阶段」的机器判据）；
      · `_attest_default` 会默认把 attest 指向 write，诱导人去认证一份自己没动过的东西。
    （此前靠「接管路径顺手重存一次 write 回执」把标记压掉；那条重存又会抹掉「人工认证」标记，
    所以改成在**读取侧**解释，两边都不牺牲。）

    判据：存在后序阶段 T，其回执有效，且 T 的产物集与本阶段的产物集有交集。
    """
    mine = set(ARTIFACTS.get(STAGES[idx]["id"], []))
    for t in STAGES[idx + 1:]:
        theirs = set(ARTIFACTS.get(t["id"], []))
        if not (mine & theirs):
            continue
        try:
            if store.matches(t["id"], _input_digest(t), _output_digest(t)):
                return t["id"]
        except Exception:
            continue
    return None


def _attest_default(cur_sid):
    """attest 的默认目标 = **最后一个「产物被改过」的非门禁阶段**（含当前阶段自身）。

    为什么不能读 `pending["attest_default"]`：那个值是黄灯亮起那一刻算的，
    而人**总是先改文件、再点认证**，所以盘面已经又变了。必须现算。
    """
    idx = STAGE_IDX[cur_sid]
    store = _receipt_store()
    best = None
    for s in STAGES[:idx + 1]:
        if s.get("gate") or not _artifact_ok(s):
            continue                          # 门禁不做 attest；产物不在盘上不能认证
        try:
            rec = store.records.get(s["id"]) or {}
            # 同上：被后序阶段（如 format）解释掉的变更不算「有人改了这个阶段」。
            changed = (bool(rec) and rec.get("outputs") != _output_digest(s)
                       and _taken_over(STAGE_IDX[s["id"]], store) is None)
        except Exception:
            changed = False
        if changed:
            best = s["id"]
    if best is None:
        cur = STAGES[idx]
        if not cur.get("gate") and _artifact_ok(cur):
            best = cur["id"]      # 卡在非门禁阶段自己（如 code 崩了、人手工跑完脚本）
    return best


def _artifact_hashes(stage_id):
    """被认证阶段声明的产物的 sha256 —— 审计留痕用，让「人改了什么」事后可追。"""
    out = {}
    for rel in ARTIFACTS.get(stage_id, []):
        p = ROOT / rel
        if p.is_file():
            out[rel] = hashlib.sha256(p.read_bytes()).hexdigest()[:16]
        elif p.is_dir():
            for f in sorted(p.rglob("*")):
                if f.is_file():
                    out[str(f.relative_to(ROOT))] = hashlib.sha256(f.read_bytes()).hexdigest()[:16]
    return out


def _do_attest(target, note, cur_sid=None):
    """人工定点修复后的重新认证。`cur_sid=None` 表示当前没有黄灯（CLI 独立调用）。

    所有校验都在这儿，缺一不可：
      · 目标必须是已知阶段（且当有黄灯时，必须是当前阶段或其**前序**）
      · **门禁阶段不能认证** —— 要放行门禁请用 disclose，否则重演
        `_KNOWN_WRITING_RESIDUALS.md` §0 记的那次「手改 verdict 洗成 PASS」
      · 产物必须真的在盘上 —— 对不存在的产物写回执等于撒谎
      · 客观校验（页数/结果契约/图证据）必须过 —— 过不了就不许认证
      · 写盘后**重新读盘**自检，确认落盘的是它自己算的那份
    """
    if target not in STAGE_IDX:
        raise HTTPException(400, f"未知的认证目标 {target!r}")
    ti = STAGE_IDX[target]
    if cur_sid is not None and ti > STAGE_IDX[cur_sid]:
        raise HTTPException(400, f"认证目标必须是当前阶段或其前序阶段，收到 {target!r}")
    st = STAGES[ti]
    if st.get("gate"):
        raise HTTPException(400, "门禁阶段不能人工认证 —— 要放行门禁请用「接受并披露」"
                                 "（人工把 verdict 洗成 PASS 那次污染就是这么来的）")
    if target == "intake":
        # ⓪ 读题用「确认」而不是「人工认证」：认证的语义是"产物没坏、只是被手工重做了"，
        #   它会写 manual 回执并把这一阶段直接标完成 —— 那就把"这批上传原件还没被人核对过"
        #   这件事绕过去了，而**核对正是这一步的全部意义**。
        raise HTTPException(400, "读题这一步请用「确认」而不是「人工认证」——"
                                 "确认会把你核对过的题面与分类落盘并留下审计痕")
    if not _artifact_ok(st):
        raise HTTPException(400, f"{target} 的产物不在盘上（reports/{st['report']}），"
                                 "不能凭空认证 —— 那等于往 stages.json 里撒谎")
    checks = _manual_checks(target)
    if checks["failed"]:
        raise HTTPException(400, "客观校验未通过，不能认证：" + "；".join(checks["failed"]))
    _in_art, _in_ins = _input_split(st)
    in_d, out_d = _in_art + ":" + _in_ins, _output_digest(st)
    try:
        store = _receipt_store()
        store.save(target, in_d, out_d, state["run_id"], manual=True,
                   artifacts=_in_art, instructions=_in_ins)
        # 自检必须**重新读盘**再比，不能写成 `store.matches(...)`：那是同一个内存对象刚被
        # 自己写过，恒为 True，这条「防污染最后一道」就成了假的。
        if not StageReceipts(LOG_DIR / "quality" / "stages.json").matches(target, in_d, out_d):
            raise HTTPException(500, "回执落盘后自检失败，拒绝继续（防污染的最后一道）")
        trail = _record_manual(target, note, in_d, out_d, checks)
    except HTTPException:
        raise
    except Exception as exc:
        # 回执可能已写、留痕没写成。回执本身是对的（当前盘面），所以不清；只如实报错。
        raise HTTPException(500, f"认证过程中出错（回执可能已写入，请刷新查看）：{exc}")
    state["stages"][target] = "done(manual)"
    # 回执刚按**当前盘面**（含最新指令）重写过 → 它不再"按旧要求交付"，标记到此为止。
    # 不摘的话面板会同时说「人工认证」和「按旧要求交付」，自相矛盾。
    state["stale_instr"].discard(target)
    _set_pending(None)
    _tick(target)
    where = f"[{cur_sid}]" if cur_sid else "[CLI]"
    log(f"🔧 {where} 人工认证 {target}：以当前盘面重新认证（校验 {checks['ran'] or '无可用项'}）；"
        f"留痕 {trail.relative_to(ROOT)}")
    emit("state", state2dict())
    return {"ok": True, "action": "attest", "attested": target,
            "checks_ran": checks["ran"], "trail": str(trail.relative_to(ROOT)),
            # 认证的语义是「这一步的产物已被人工修好、按盘面复用」⇒ 起点就是它自己
            # （`run_stage` 会命中刚重写的回执、判复用），随后往下走。
            "resume_from": target,
            "resume_index": STAGE_IDX.get(target, 0), "resumed": True}


async def _attest_without_pending(req):
    """没有黄灯时的 attest（CLI 独立调用）。必须显式给 `--stage`。"""
    if not req.stage:
        raise HTTPException(400, "没有待决策项时必须用 --stage 指定要认证的阶段")
    return _do_attest(req.stage, req.note)


def _record_manual(stage_id, note, in_digest, out_digest, checks):
    """把人工认证落成审计留痕。**没有这一步的「重新认证」就是污染** ——
    上次手改 verdict 之所以被登记为一次污染，正是因为什么都没留下。"""
    MANUAL_DIR.mkdir(parents=True, exist_ok=True)
    path = MANUAL_DIR / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{stage_id}.json"
    atomic_json(path, {"stage": stage_id, "at": datetime.now().isoformat(),
                       "note": note, "run_id": state["run_id"],
                       "input_digest": in_digest, "output_digest": out_digest,
                       "checks_ran": checks["ran"],
                       "artifacts": _artifact_hashes(stage_id)})
    return path


def _action_set(sid, kind, status, has_artifact, attest_default,
                *, stale=False, stale_findings_ok=False, limit_kind="cap", capped=False):
    """这个黄灯**现在**允许哪些处置。

    单一事实来源：`_build_pending`（算黄灯）与 `_load_pending`（复活旧黄灯时对账）
      都调它。分开写迟早漂移，而漂移的后果是面板给出**做不成事的按钮**。

    为什么要单独抽出来：复活一条**旧快照**时，字段齐全、语义也没过期，
      但驱动的**动作集变了**（例如新增了「只重做图（不重算）」）—— 旧快照的 `actions`
      里没有它，重启后那个按钮**根本不会出现**，看起来像功能没生效。
      所以不能走"在复活路径里**直接调 `_build_pending` 重算整份**"这条路：
      `test_a_current_pending_survives_untouched` 钉着它（那条护栏 monkeypatch `_build_pending`
      抛异常，测的就是"本版写的 pending 不许重算"）；而且 `_build_pending` 一旦抛错，
      外层的 `except` 会把**整个黄灯**吞掉（比少个按钮严重得多）。
      所以：只算动作集，拿现成的输入，不碰别的东西。
    """
    if kind == "overtime":
        # 超时的出路与**裁决新鲜度无关**，必须排在两条 stale 分支之前：
        #   排在它们之后的话，只要那份裁决同时是"过期"的（复活旧黄灯时按当前盘面重算
        #   就会撞上），actions 被压成 `['retry']` ⇒ 面板上延长控件整组不显示
        #   （⑪跨问一致性超时那盏灯就是这么把控件整组丢掉的）。
        #   延长的语义是"别杀它、再给点时间"，跟"那份裁决是否按旧判据写的"毫不相干。
        #   它同时**先于**下面的「读题确认」：超时说明这一步还没跑完，那时给「确认」按钮
        #     等于让人在不存在的结论上签字。
        #   「延长」只对**墙钟上限**那一类有意义：
        #     · 假死/静默灯（`limit_kind="stall"`）：延长的是墙钟上限，而它管的是"没输出"，
        #       点了不但没用，还会因为 cap_s 变了让键变化 ⇒ **下一轮 5 秒后又原样亮一遍**；
        #     · 协议级修复（`capped=True`，`CALL_PROTOCOL_CAP=900`）：`_effective_limits` 里
        #       `cap` 永远压过用户覆盖 ⇒ 点「延长」只写进 state 却对它毫无作用，日志还写
        #       「追加 10 分钟」是骗人的（状态栏会写 40 分钟、实际仍是 15 分钟）。
        #     这两种情况**不给延长按钮**，文案里另说该用什么。
        actions = (["retry", "extend"] if (limit_kind == "cap" and not capped) else ["retry"])
    elif sid == "intake":
        # ⓪ 读题这一步的出路只有两条：
        #   · `confirm`：把人核对过的题面与分类落盘、然后从 ① 起跑（这是它的放行动作）；
        #   · `retry`：让它重读一遍（`kind != "intake"` 时 —— 例如它自己跑失败了 —— 只有重试）。
        # 不给 `rollback`：它在链首，`_target_index` 必拒（target 必须是严格前序，见 ⑧
        #   那段"⑦ 不能指自己"的注释）⇒ 那会是一个"点下去必然 400"的按钮；
        # 不给 `disclose`：disclose 的语义是"认下已知残余、写进论文"（会写 `waivers.json`
        #   与 `_KNOWN_WRITING_RESIDUALS.md`）—— 这里根本没有产物缺陷，是让人**确认一份事实**，
        #   套上去会把审计痕写歪；
        # 不给 `attest`：人工认证会写 manual 回执，反而把"这批原件还没被确认"绕过去。
        actions = ["confirm", "retry"] if kind == "intake" else ["retry"]
    elif stale and not stale_findings_ok:
        # 被审正文已经变了 → 只有一条出路：重跑本门禁。**不给 rollback** ——
        # findings 指向的文字已不存在，退过去等于拿旧地图找新路。
        actions = ["retry"]
    elif stale_findings_ok:
        # 正文没动，只是要求/判据变了 → findings 仍然指着真实存在的文字，回退是有意义的。
        # 两条路都给：重判（拿一份按新要求写的裁决）或直接退上游改（省一次 20 分钟重审）。
        actions = ["retry", "rollback", "disclose"]
    elif kind == "driver":
        # 驱动异常 / 交付包收集失败：没有可披露的产物结论
        actions = ["retry", "rollback"]
    elif not has_artifact or status == "unverified":
        # 无产物 → 没东西可披露；unverified → 产物与被审对象不对应，披露它不安全
        actions = ["retry", "rollback"]
    else:
        actions = ["retry", "rollback", "disclose"]
    # attest 与上面的动作**正交**：上面答的是「这个卡住的阶段怎么办」，
    # attest 答的是「手工改了**前面某个阶段**的产物，别让它重跑」。
    # 只要存在可认证的目标（有产物 + 非门禁）就提供，与当前黄灯类型无关。
    # `attest`（人工认证）**不给读题的黄灯**：认证会写 manual 回执、把这一阶段
    #   直接标完成 —— 那就把"这批上传原件还没被人核对过"这件事绕过去了，而**核对正是这一步的
    #   全部意义**。要放行请用它的专属动作 `confirm`（见 `_do_intake_confirm`）。
    if attest_default and sid != "intake":
        actions = actions + ["attest"]
    return actions


def _borrowed_upstream_issues(stage):
    """非门禁阶段**交回**时，把它上一轮拿到的**上游门禁回执**里的未解决项借过来。

    为什么需要它：⑦技术路线图 交回 ④编码计算 时，
    它自己**不是门禁**（`gate=None`）⇒ `_build_pending` 给它 `{}` ⇒ pending 的 `issues`
    天然为空，两个消费者于是**一起失明**：

      · `_figure_only_defects([])` = False ⇒ 明明是纯图缺陷（⑧ 那 6 条 `category` 全是
        `diagram`），也把 ④ 的 `code/`+`results/` **整包**搬进 cache（86 MB / 4 个阶段）
        ⇒ ④ 回来得自己 robocopy 搬回（约 90 s；**想不起来就是从零重算，小时级**）；
      · `_has_actionable_feedback({})` = False ⇒ 给 ④ 的提示词写成「上游门禁这次**没有跑完**…
        **仅供排查**…**与本阶段无关**」—— 而那张交回单**正是**它要执行的返修单。

    借的对象 = **本阶段上一轮拿到的回执**（回退时记进 `state["hint_src"][sid]` 的那个
    feedback 目录）—— 那正是它被要求去修的那批缺陷。两条硬边界（**宁可少借，不可借错**）：

      · 只认**门禁**的裁决（`gate` 非空）：非门禁的"裁决"是空壳，没有判据可言；
      · **不判"前序/下游"**：判一个阶段的那个门禁常常排在它**之后**（⑧绘图门禁 在 ⑦ 之后，
        它才是审 ⑦ 的图的那个门禁）—— 写成"只认前序"会把它误杀；
      · 查不到 / 读不出 ⇒ 返回 `None` ⇒ 调用方按**空**处理，与今天一样保守
        （与 `_figure_only_defects` 同一条纪律：宁可多算一次，不可拿旧数当新数）。

    **残余风险（已知，接受）**：判据是"⑦ 上一轮拿到的回执全 diagram"，而 ⑦ 交回的**动机**
      不在回执里（它 SKILL 的另一条触发词是"画图所需的关键数据缺失"）。若它这次的动机其实是
      数据缺失、而上一轮回执恰好是 ⑧ 那份全 diagram 的 FAIL ⇒ 会被判成纯图 ⇒ 数值产物不搬。
      为什么接受：`figure_only` 只决定**搬不搬**，不决定**跑不跑** —— ④ 照样跑、照样拿到交回单，
      真要重算随时能重算；数值真出问题还有 ⑤ 在盯。**保守那一侧没动**（借不到 ⇒ 照搬）。
    """
    if stage.get("gate"):
        return None                     # 门禁自己有裁决，不需要借
    folder = (state.get("hint_src") or {}).get(stage["id"])
    if not folder:
        return None
    try:
        obj = json.loads((ROOT / folder / "gate_decision.json").read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, ValueError):
        return None
    src = str(obj.get("stage") or "")
    # **刻意不要求它是"前序"**：判一个阶段的那个门禁常常排在它**之后** —— ⑧绘图门禁 在
    #   ⑦技术路线图 之后，它才是审 ⑦ 的图的那个门禁 —— 写成"只认前序"会把它**误杀**。
    #   真正的"相关性"由 `hint_src` 本身保证 —— 那条记录**只在回退投递时**写下，
    #   也就是"这个阶段被要求按这份回执返修"的那一刻。
    if src not in STAGE_IDX or not STAGES[STAGE_IDX[src]].get("gate"):
        return None
    issues = [i for i in (obj.get("issues") or []) if isinstance(i, dict)]
    return issues or None


def _build_pending(stage, kind, status, reason, *, verdict="", decision=None, tail="",
                   handback=None, limit_kind="cap", capped=False):
    """构造待决策上下文。前端面板全靠它渲染。

    `handback` 由调用方（run_all）预先算好并传入 —— 本函数**不自己调 check_handback**，
    因为那个函数有副作用（会把上轮遗留的 HANDBACK 归档放行），埋在「构造一个 dict」里不合适。
    """
    sid = stage["id"]
    idx = next((i for i, s in enumerate(STAGES) if s["id"] == sid), 0)
    dec = decision if decision is not None else ({} if not stage.get("gate") else _gate_decision(stage))
    if handback is not None and not dec.get("issues"):
        # 交回那条路（见 `_borrowed_upstream_issues`）：借上游门禁的未解决项，否则
        #   `_figure_only_defects` 与 `_has_actionable_feedback` 会一起失明。
        dec = dict(dec, issues=_borrowed_upstream_issues(stage) or [])
    # 裁决过期时 `issues` 是空的（那份裁决按旧要求写的，不参与路由），但它查出来的东西
    # **不能丢** —— 人对下一轮该怎么办，靠的就是这批 findings。放进 `stale_issues` 里展示。
    stale = dec.get("reason") == "verdict_stale"
    # 过期里还要再分一层：**被审的正文动没动**。
    #   · 正文动了（artifacts 段变）→ findings 指的东西已经不是现在这份，只能重判；
    #   · 只是做法要求/判据/驱动代码变了 → 正文一个字没动，findings 仍然成立，
    #     退给上游是**有意义**的，不该堵死（改一次
    #     `skills/_references/` 就让在飞裁决作废，而上游报告没变 —— 那种情况要重判 20+ 分钟纯属浪费）。
    stale_findings_ok = stale and not (dec.get("stale_digest") or {}).get("artifacts_changed")
    issues = ((dec.get("stale_issues") if stale else dec.get("issues")) or [])[:12]

    # 推荐的回退目标，优先级：agent 显式交回 > 裁决给的 target > 默认映射
    # 正文真的动了才例外：上游没有可修的东西，该重做的是**本门禁**。
    if stale and not stale_findings_ok:
        recommended, source = None, "none"
    elif handback is not None:
        recommended, source = STAGES[handback]["id"], "handback"
    else:
        raw = dec.get("target")
        fb = _default_repair_target(sid)
        # 逐条**验真**再采用：`_target_index` 只认**前序**阶段，而默认映射
        #   表里有指向**后序**的目标 —— ⑫评分标终审 的默认目标是 ⑬fix，⑬ 排在 ⑫ 之后 ⇒
        #   `_target_index('fix', 11)` 抛 ValueError。若 except 直接回落成 `(fb, "default")` 而
        #   **不再校验**，面板副标题就会写「推荐回退 ⑬按评分判词返修」—— 而回退下拉里
        #   根本没有 ⑬（candidates 只含前序），点下去也只会 400（⑫ 到顶转黄灯时就是如此）。
        #   所以：候选按「裁决给的 → 默认映射的」顺序试，**第一个真能回退过去的**才算数；
        #   都不行就不推荐（下拉不预选，逼用户显式选一个前序阶段）。
        recommended, source = None, "none"
        for cand, src in ((raw, "verdict"), (fb, "default")):
            if not cand:
                continue
            try:
                recommended, source = STAGES[_target_index(cand, idx)]["id"], src
                break
            except Exception:
                continue

    # 候选 = 当前阶段之前的全部前序阶段。unchanged=True 的项回退过去会直接 done(skip)，
    # 前端灰显并加注，免得用户以为「回退了却什么都没发生」。
    #
    # `out_changed` 单独算：它答的是「这个阶段的**产物**跟它上次成功时比变了吗」。
    # 这正是「人工改过哪个阶段的产物」的机器判据 —— attest 的默认目标就选它。
    store = _receipt_store()
    candidates = []
    for i, s in enumerate(STAGES[:idx]):
        try:
            out_cur = _output_digest(s)
            rec = store.records.get(s["id"]) or {}
            # `and not _taken_over(...)`：format 改过 paper 之后，write 的产出指纹必然
            #   与它自己的回执对不上 —— 但那是 format 干的，不该挂「产物已改」到 write 头上。
            out_changed = (bool(rec) and rec.get("outputs") != out_cur
                           and _taken_over(i, store) is None)
            unch = bool(store.matches(s["id"], _input_digest(s), out_cur))
        except Exception:
            out_changed, unch = False, False
        candidates.append({"id": s["id"], "unchanged": unch, "out_changed": out_changed,
                           "attestable": s.get("gate") is None})

    # attest 默认目标见 _attest_default()：最后一个「产物被改过」的非门禁前序阶段。
    # 这个值是**黄灯亮起那一刻**算的；人改文件必然在其后，所以界面上的按钮可能滞后。
    #    `_apply_decision` 里的 attest 分支**不看这里**，以当前盘面重算 —— 否则
    #    「先改文件再点认证」会被一个过期的 actions 列表挡在门外。
    attest_default = _attest_default(sid)
    # 默认目标可能是**当前阶段自己**（卡在非门禁阶段，如 code 崩了、人手工跑完脚本）。
    # 而 candidates 只含严格前序 —— 不补进去的话，前端把默认值赋给下拉会赋不中，
    # 整个单选框被反选成空、用户也没法显式选它。服务端靠 `req.stage or _attest_default`
    # 恰好兜住，但面板表现为空白。
    if attest_default and not any(c["id"] == attest_default for c in candidates):
        # out_changed 要算**真值**：硬编码 True 会让面板给一个其实没被改过的阶段
        #   挂上「产物已改」（demo 全链跑完后就会这样）。
        _cur = store.records.get(sid) or {}
        try:
            _oc = bool(_cur) and _cur.get("outputs") != out_digest
        except Exception:
            _oc = False
        candidates.append({"id": attest_default, "unchanged": False, "out_changed": _oc,
                           "attestable": not stage.get("gate"),
                           # 它不是合法回退目标时（== 当前阶段、或已排到当前阶段之后）
                           #   打标，前端据此注明「仅用于人工认证」并在回退时拦下 ——
                           #   否则面板会给一个点下去必然 400 的选项 —— 非门禁阶段失败时
                           #   attest_default 常是**当前阶段自己**。
                           "only_attest": STAGE_IDX.get(attest_default, -1) >= idx})

    has_artifact = _artifact_ok(stage)
    # 动作集见 `_action_set`（单一事实来源 —— 复活旧黄灯时也要拿它现算对账）。
    actions = _action_set(sid, kind, status, has_artifact, attest_default,
                          stale=stale, stale_findings_ok=stale_findings_ok,
                          limit_kind=limit_kind, capped=capped)

    out = {"stage": sid, "kind": kind, "status": status, "reason": reason,
            "verdict": verdict, "report": stage.get("report", ""), "issues": issues,
            # 轻微/可选项**不进返修、不拦链**，但必须让人在决策面板上看得见 ——
            # 「加个对比会更好」这类要靠成本估计判断值不值得为它多跑一轮，
            # 只写在报告里等于没提。见 12Rubric-final 的 tier 设计。
            # 轻微/可选：面板默认**折叠**显示（见 index.html 的 renderDecision）。
            # 一轮定点返修会留下几十条文字痕迹（一轮 23 条是常见量级，全是"只改一句/
            # 不改任何数值/订正引用"级），全铺开会把面板淹掉、也让人误以为"问题这么多"。
            # 上限放到 40（一次展开够看完），同时给总数 —— 前端要如实说「共 N 条」，
            # 不能只报"显示几条"让人以为是全部。
            "advisories": (dec.get("advisories") or [])[:40],
            "advisories_total": len(dec.get("advisories") or []),
            "recommended": recommended, "recommended_source": source,
            "candidates": candidates, "actions": actions,
            "attest_default": attest_default,
            # 「延长」是**追加**：默认追加 RETRY_CAP_EXTRA_MIN（10 分钟），一次最多追加
            # RETRY_CAP_EXTRA_MAX（60 分钟），反复追加总天花板 RETRY_CAP_MAX。
            # `retry_cap_default` 是**当前已生效的上限**（含之前追加过的），面板拿它显示
            # 「30 → 40 分钟」。
            "retry_cap_default": _effective_limits(sid)[0],
            "retry_extra_default": RETRY_CAP_EXTRA_MIN,
            "retry_extra_max": RETRY_CAP_EXTRA_MAX,
            "retry_cap_max": RETRY_CAP_MAX,
            "retry_cap_min": RETRY_CAP_MIN,
            "attempts": dict(state.get("attempts") or {}), "tail": (tail or "")[-1500:],
            "has_artifact": bool(has_artifact),
            "estimate": _parse_scale_estimate(tail),
            "created_at": datetime.now().isoformat()}
    # ⓪ 读题的面板字段**从盘上现算**合进来，不靠快照：
    #   `_load_pending()` 的"旧版本驱动写的快照"分支会调本函数**整份重算** ——
    #   只存在于快照里的字段会被静默丢掉 ⇒ 重启之后用户看到一个只有「再试一次」的空面板，
    #   而且**看不出少了东西**。现算既修这个，也让重启前后的黄灯内容一致。
    if sid == "intake" and kind == "intake":
        try:
            out.update(_intake_panel_fields())
        except Exception as exc:                      # noqa: BLE001 —— 面板画不全也不该吞掉黄灯
            log(f"⚠️ 读题面板字段构造失败（不影响「确认 / 再试一次」两个按钮）：{exc}")
    return out


# ---------------- 披露豁免（机器可读）----------------
# 「接受并披露」必须落成显式标记，不能靠写 reason 散文 ——
# reports/_KNOWN_WRITING_RESIDUALS.md §0 记着这条：机器只读 status 不读 reason ——
# 只靠写 reason 散文的话，人只能去手改 .verdict.json 把 REVISE 洗成 PASS。
WAIVER_FILE = LOG_DIR / "quality" / "waivers.json"


def _load_waivers():
    try:
        return json.loads(WAIVER_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_waivers(w):
    WAIVER_FILE.parent.mkdir(parents=True, exist_ok=True)
    WAIVER_FILE.write_text(json.dumps(w, ensure_ascii=False, indent=2), encoding="utf-8")


def _waived(sid, stage):
    """该阶段是否被人工豁免**且输入未变**。输入一变豁免自动失效、门禁重新生效。"""
    rec = _load_waivers().get(sid)
    if not rec:
        return None
    try:
        if rec.get("digest") != _input_digest(stage):
            return None
    except Exception:
        return None
    return rec


def _append_residual(stage, reason, verdict, issues, note, run_id):
    """把披露写进 _KNOWN_WRITING_RESIDUALS.md（**追加**，不重写）。

    该文件是下游 agent 会读的活交付件，现有内容被逐字引用 —— 所以新章节必须带
    [HIL-DISCLOSE ...] 标记，让人和 grep 都能把它与人工撰写的章节区分开。
    """
    p = REPORTS / "_KNOWN_WRITING_RESIDUALS.md"
    hdr = (f"\n\n## [HIL-DISCLOSE {datetime.now().strftime('%Y-%m-%d %H:%M')}] "
           f"人工降级披露：{stage['id']}\n\n"
           f"> 由 Web 驱动 `/api/decision(action=disclose)` 写入。**未经修复**；"
           f"下游引用本阶段结论时必须回源复核。\n\n"
           f"- 卡住原因：{reason}\n- 门禁裁决：`{verdict or '—'}`\n"
           f"- 用户批注：{note or '（无）'}\n"
           f"- 机器可读标记：`runtime/quality/waivers.json` 的 `{stage['id']}`（输入一变即失效）\n")
    if issues:
        hdr += ("\n| 编号 | 严重度 | 类别 | 证据 | 处置 |\n|---|---|---|---|---|\n"
                + "".join(f"| HIL-{run_id}-{k+1} | {i.get('severity','')} | {i.get('category','')} | "
                          f"{str(i.get('evidence',''))[:80]} | 未修复，按门禁裁决承担 |\n"
                          for k, i in enumerate(issues[:20])))
    with p.open("a", encoding="utf-8") as f:
        f.write(hdr)
    return p


# ---------------- 阶段 agent 的 pid 登记 + 孤儿收容 ----------------
# 为什么需要：驱动把每个阶段 spawn 成 `claude -p` **子进程**。走界面上的「停止」时驱动
#   会 `taskkill /T` 强杀进程树；但用 `taskkill /F` 杀**服务本身**（外部强杀、任务管理器
#   结束进程、崩溃）时，**子进程不会被一起杀** —— 它们变成孤儿继续跑、继续往 reports/ 写。
#   孤儿的危害：它和新起一轮的 analysis 会并发改写**同一份报告与题意契约**，
#   结果是契约锚点对不上、门禁判 task_contract_failed —— 现场看起来只是"随机失败"。
STAGE_PIDS = LOG_DIR / "quality" / "stage_pids.json"


def _register_stage_pid(pid):
    """记下刚 spawn 的阶段 agent pid，供下次启动时收容。只留最近 50 个，防无限增长。"""
    try:
        STAGE_PIDS.parent.mkdir(parents=True, exist_ok=True)
        try:
            data = json.loads(STAGE_PIDS.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data = []
        data = [p for p in data if isinstance(p, int) and p != pid]
        atomic_json(STAGE_PIDS, (data + [int(pid)])[-50:])
    except Exception:
        pass


def _claude_processes():
    """一次查询拿回所有 claude.exe 的 (pid, 命令行)。

    一个一个 pid 去查会为每个起一次 PowerShell（每次 1~2 秒）；进程表很小，一次全拿更省。
    """
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "Get-CimInstance Win32_Process -Filter \"Name='claude.exe'\" | "
             "Select-Object ProcessId,CommandLine | ConvertTo-Json -Compress"],
            capture_output=True, text=True, timeout=25, encoding="utf-8", errors="replace")
        raw = (r.stdout or "").strip()
        if not raw:
            return []
        data = json.loads(raw)
        if isinstance(data, dict):
            data = [data]
        return [(int(d["ProcessId"]), str(d.get("CommandLine") or ""))
                for d in data if isinstance(d, dict) and d.get("ProcessId")]
    except Exception:
        return []


def _reap_orphan_agents(kill=None):
    """启动时收掉上一轮遗留的**孤儿阶段 agent**，返回收掉的个数。

    只杀「pid 在驱动自己的登记表里」**且**「命令行确实指向本工作区」的进程 ——
    用户别的 claude 会话（包括正在跑这个服务的 VSCode 扩展）命令行里没有本工作区路径，
    不会被误伤。杀进程树（`/T`），因为阶段 agent 自己还会 spawn 子 agent。

    **绝不杀自己**：当前进程的 pid 一律跳过。这一条不是多余的 —— `_register_stage_pid()`
      把正在跑的阶段 agent 自己也登记进表里，若这段逻辑从 agent 进程内被触发（模块级调用
      时就会），它会把自己 `taskkill /F /T` 掉，以 exit code 1 静默死亡。
      见 `if __name__ == "__main__"` 处那段说明。
    """
    try:
        if not STAGE_PIDS.is_file():
            return 0
        pids = {p for p in json.loads(STAGE_PIDS.read_text(encoding="utf-8")) if isinstance(p, int)}
        STAGE_PIDS.unlink(missing_ok=True)
    except Exception:
        return 0
    pids.discard(os.getpid())          # 不杀自己（见 docstring）
    if not pids:
        return 0
    root = str(ROOT).replace("\\", "/").lower()
    kill = kill or (lambda pid: subprocess.run(
        ["taskkill", "/F", "/T", "/PID", str(pid)], capture_output=True, timeout=15))
    killed = []
    for pid, cmdline in _claude_processes():
        if pid not in pids or pid == os.getpid():
            continue
        if root not in cmdline.replace("\\", "/").lower():
            continue                      # pid 被复用，或不是本工作区的调用 —— 不动
        try:
            kill(pid)
            killed.append(pid)
        except Exception:
            pass
    if killed:
        log(f"🧹 收掉上一轮遗留的阶段 agent 孤儿进程 {len(killed)} 个（pid {killed}）——"
            "它们的父进程（服务）被外部强杀时没被一起带走，会继续往 reports/ 写。")
    return len(killed)


# ---------------- 待决策项的落盘（重启存活）----------------
PENDING_FILE = LOG_DIR / "quality" / "pending_decision.json"


def _set_pending(p):
    """设置/清除待决策项并落盘。不落盘的话，黄灯状态下关掉服务器，用户回来只会看到「已停止」。"""
    state["pending"] = p
    try:
        PENDING_FILE.parent.mkdir(parents=True, exist_ok=True)
        if p:
            PENDING_FILE.write_text(json.dumps(p, ensure_ascii=False, indent=2), encoding="utf-8")
        else:
            PENDING_FILE.unlink(missing_ok=True)
    except Exception:
        pass


# `_build_pending` **总会**算出来的字段。重启时从盘上复活的那份 pending 若缺其中任何一个，
# 说明它是**旧版本驱动**序列化下来的 —— 那时它剩下的字段（截断上限、默认值、推荐的落点…）
# 都是旧口径，照原样复活等于把旧代码的判断当成现状显示给用户。
# 缺字段的三种典型形态：`retry_cap_max=1800`（实际已是 10800）、`retry_extra_default` 缺失
# （面板算不出"追加 N 分钟后上限 = …"）、`advisories_total` 缺失（面板把 12 条说成全部）。
PENDING_FRESH_KEYS = ("advisories_total", "retry_extra_default", "retry_extra_max")


def _pending_from_an_older_driver(p):
    """这份复活的 pending 是旧版本驱动写的吗？（缺任一 PENDING_FRESH_KEYS 即判是）"""
    return any(k not in (p or {}) for k in PENDING_FRESH_KEYS)


def _stage_ran_this_round(stage):
    """这一轮该阶段是**真跑了**，还是被**复用**（输入与回执一致）？

    收尾自检（题意契约锚点 / 返修台账）只在**真跑过**时才做。
      `run_stage` 在复用那条路上也返回 "ok"，但状态置的是 `done(skip)` —— 那一轮阶段
      **根本没执行**，盘上的契约/台账是**上一轮留下的**。拿它自检等于让一个没跑过的阶段
      为上一轮的残留负责；而它改不了（重试还是复用，输入没变）⇒ **死循环，出不来**。
      典型形态：回退到 ⑧ write 后走到 ②，analysis 被复用，台账却是上一轮的、答的是旧回执
      → 自检报「receipt 指错了」当场挂起；重试仍复用 → 卡死。

      执行的标志是 `done`：复用是 `done(skip)`；人工认证/披露另有 `attest` 那条路的客观校验把关。
    """
    return state["stages"].get(stage["id"]) == "done"


def _pending_went_stale(p):
    """复活的黄灯所依据的那份**门禁裁决**，现在还成立吗？

    成立条件：阶段仍是门禁、产物还在、且 `_gate_decision` 不是因为「裁决过期」而失效。
    任何一条不满足都返回 False（照旧原样复活）—— 这个函数**只负责认出过期**，
    其余情形一律不动，免得把好黄灯也重算没了。
    """
    sid = (p or {}).get("stage")
    if sid not in STAGE_IDX:
        return False
    stage = STAGES[STAGE_IDX[sid]]
    if not stage.get("gate") or not _artifact_ok(stage):
        return False
    try:
        return _gate_decision(stage).get("reason") == "verdict_stale"
    except Exception:
        return False


def _load_pending():
    """启动时读回待决策项（与 _clock_load 同一套路）。

    必须校验 `stage` 仍然是已知阶段。理由：这个文件是**跨版本存活**的 —— 阶段被增删或
    改名之后（新增 format、调换 audit/robustness 顺序都会发生），旧文件会被原样复活，
    而 `_apply_decision` 第一行就是 `next(s for s in STAGES if s["id"] == sid)` →
    StopIteration → **每个决策动作都 500**，且黄灯清不掉（只能 /api/start 或手删文件）。
    宁可在读入时丢掉它并记一条日志。
    """
    def _mark(p):
        """把黄灯对应的阶段行也标上。

        只恢复 `pending` 的话，面板说「等待决策」、进度里那一行却是 idle ——
        两处自相矛盾，而且阶段行不再高亮，人容易以为面板是上一次的残留。
        """
        sid = (p or {}).get("stage")
        if sid in state["stages"]:
            state["stages"][sid] = "awaiting_user"

    try:
        if PENDING_FILE.exists():
            p = json.loads(PENDING_FILE.read_text(encoding="utf-8"))
            if p and p.get("kind") == "overtime" and p.get("stage") in STAGE_IDX:
                # 超时黄灯的语义是「**进程还在跑**，只是超了限时，等你决定延长还是取消」。
                #   进程一死这个语义就不成立了 —— 原样复活会给出两个**报成功却什么都不做**的
                #   按钮（extend 只写 retry_cap 不起链；retry 只设 force_retry/resume_action，
                #   而消费它们的那条链已经不存在），面板还会把不存在的任务画成「运行中」。
                #   降级成失败类：保留「要不要重来」的决定权，但不再假装任务还活着。
                # 去掉 overtime 专有字段：`limit_kind` / `estimate` / `retry_cap_default`
                # 在失败黄灯里没有意义，而前端**不看 kind** 就渲染「缩比预估」——
                # 会对着一个已经死掉的任务报预估（残留字段就是这三个）。
                p = {k: v for k, v in p.items()
                     if k not in ("limit_kind", "estimate", "retry_cap_default")}
                p = dict(p, kind="failure", status="interrupted",
                         # 降级后要**和普通失败黄灯一样能选**。原来想「保留原 actions 里的
                         # disclose」，但 overtime 的 actions 是 ["retry","extend"](+attest)，
                         # 永远不含 disclose —— 于是重启后拿不到「接受并披露」这个最省的出口。
                         # 中断的产物能不能披露本来就是人判断的事，直接给。
                         actions=["retry", "rollback", "disclose"],
                         reason=("【进程已不在】" + str(p.get("reason") or "")
                                 + " —— 服务在超时等待期间退出/重启，超时状态无法继续；"
                                   "原任务是死是活请自行核实产物后再决定。"))
                _set_pending(p)
                state["halt_gate"] = True
                _mark(p)
                log("⚠️ 发现遗留的超时黄灯：进程已不在，已降级为失败类黄灯（不再提供「延长」）。")
            elif p and p.get("stage") in STAGE_IDX and _pending_went_stale(p):
                # 复活的黄灯里存着**旧的裁决结论**（issues/target/actions 都是上次算的）。
                #   若这期间判据或驱动代码变过，那份裁决已经作废 —— 按旧结论渲染会给出
                #   一个**做不成事的按钮**：推荐回退上游，而回退时交出去的回执其实是
                #   「裁决过期」，上游拿着一句"去补 .verdict.json"白忙一场。
                #   所以按当前盘面重算一份。
                st = STAGES[STAGE_IDX[p["stage"]]]
                #   文案必须跟实现一致：`_build_pending` 会**看被审正文动没动**来决定给不给
                #   回退那条路（见那里的 stale_findings_ok）。这里不许写成"不管三七二十一就重跑"：
                #   那样面板会一边写着"只提供重跑"、一边把 rollback 按钮摆在下面，自相矛盾。
                _sd = (_gate_decision(st).get("stale_digest") or {})
                if _sd.get("artifacts_changed"):
                    _why = ("门禁裁决**过期**：被审的报告在这份裁决之后被改过 —— findings 指向的文字"
                            "已经不在现在这份里，只能**重跑本门禁**。下面列的是上一轮查出的，仅供参考。")
                    _note = "被审报告变过 → 只能重跑本门禁"
                else:
                    _why = ("门禁裁决**过期**：只有做法要求/判据变了，**被审的报告一个字没动** —— "
                            "它上一轮查出的条目仍指着现在这份报告里真实存在的文字，"
                            "可以当普通回执**退给上游**，也可以**重跑本门禁**拿一份按新要求写的裁决。")
                    _note = "被审报告没动 → 回退与重跑都可选"
                p = _build_pending(st, p.get("kind") or "failure", "stale", _why)
                _set_pending(p)
                state["halt_gate"] = True
                _mark(p)
                log(f"⚠️ 复活的黄灯所依据的裁决已过期（判据/输入变过）→ 已按当前盘面重算：{_note}")
            elif p and p.get("stage") in STAGE_IDX and _pending_from_an_older_driver(p):
                # 旧版本驱动序列化下来的 pending：它剩下的字段都是**旧口径**，照原样复活
                #   等于把旧代码的判断当成现状显示给用户（`retry_cap_max=1800`
                #   而实际已是 10800、缺 `retry_extra_default` 导致面板算不出追加后的上限、
                #   缺 `advisories_total` 导致面板把"带下来的 12 条"说成全部）。
                #   按当前盘面重算一份 —— 黄灯本身留着，只是字段换成本版的。
                st = STAGES[STAGE_IDX[p["stage"]]]
                p = _build_pending(st, p.get("kind") or "failure", p.get("status") or "blocked",
                                   p.get("reason") or "见回执")
                _set_pending(p)
                state["halt_gate"] = True
                _mark(p)
                log("⚠️ 复活的黄灯是旧版本驱动写的（缺新字段）→ 已按当前盘面重算，"
                    "避免用旧口径的值渲染面板。")
            elif p and p.get("stage") in STAGE_IDX:
                # `actions` 必须**按当前驱动现算**。
                #   面板上的按钮**只由这份快照决定**：驱动新增一个动作之后（例如
                #   「只重做图（不重算）」），旧快照的 actions 里没有它 —— 重启后那个新按钮
                #   **根本不会出现**，看起来像功能没生效。收窄时更糟：旧快照给出一个
                #   后端已不认的动作，点下去只会拿到 400。
                #   上面三条分支各管一种"旧"（超时语义已失效 / 裁决过期 / 缺新字段），
                #   这一条管第四种：**字段齐全、语义没过期，但动作集变了** —— 前三条都放它过。
                #
                #   只换 `actions`，**不整体重建**：`_build_pending` 在不带 `handback`
                #   参数时会算出另一套 recommended（丢掉 agent 主动交回给出的那个建议）。
                #   `actions` 是"这个黄灯现在允许你怎么处置"，与推荐谁是两件事。
                _st = STAGES[STAGE_IDX[p["stage"]]]
                # 只算动作集，**不调 `_build_pending`** —— 那个会连 recommended 一起重算
                # （丢掉 agent 主动交回给的建议），而且它一旦抛错，外层 except 会把整个
                # 黄灯吞掉。`stale*` 传 False：真的过期会在上面那条分支就重算了，走到这儿
                # 的都是没过期的好黄灯。
                _fresh = _action_set(_st["id"], p.get("kind") or "failure",
                                     p.get("status") or "blocked", _artifact_ok(_st),
                                     p.get("attest_default"))
                if sorted(_fresh) != sorted(p.get("actions") or []):
                    log(f"⚠️ 复活的黄灯里 actions={sorted(p.get('actions') or [])} 与当前驱动现算的 "
                        f"{sorted(_fresh)} 不一致 → 已按当前盘面重算动作集，免得面板少给/多给按钮。")
                    p = dict(p, actions=_fresh)
                _set_pending(p)
                state["halt_gate"] = True
                _mark(p)
            elif p:
                log(f"⚠️ 忽略过期的待决策项（stage={p.get('stage')!r} 已不是已知阶段）—— "
                    f"多半是阶段增删/改名前的残留；黄灯未恢复，链可从当前进度继续。")
    except Exception as exc:
        log(f"⚠️ 待决策项读取失败，已忽略：{exc}")


async def _call(prompt, sid, cap=None):
    # 每次 spawn 现取当前 claude.exe（扩展更新会换目录名；启动缓存会过期导致全链秒失败）
    cbin = _find_claude() or CLAUDE
    if cbin is None:
        log("⚠️ 未找到 claude.exe（VSCode 扩展可能正在更新），本次调用放弃。")
        return (-1, "claude.exe not found (extension updating?)", False)
    cmd = [str(cbin), "-p", prompt, "--output-format", "stream-json", "--verbose"]
    if MODEL: cmd += ["--model", MODEL]
    if PERMS == "bypass": cmd += ["--dangerously-skip-permissions"]
    else: cmd += ["--permission-mode", "acceptEdits"]
    sh = {"pid": None, "rc": None, "tail": "", "done": False,
          "stalled": False, "sid": sid, "last_out": time.time(), "lines": []}
    task = asyncio.create_task(asyncio.to_thread(_claude_worker, cmd, sh))
    pid = None
    def drain():
        # worker 线程只往 lines 里攒；这里在事件循环线程里真正 log/emit（线程安全）
        if sh["lines"]:
            for s in sh["lines"]:
                log(s)
            sh["lines"].clear()
    try:
        # 等 worker 把子进程 pid 写出（进程刚拉起）
        for _ in range(200):
            if sh["pid"] is not None:
                pid = sh["pid"]; break
            await asyncio.sleep(0.05)
        idle_since, last_cpu, t0 = time.time(), None, time.time()
        # 循环条件**不能**写成 `and pid is not None`：Popen 若慢于那 10 秒（首次启动时
        #   杀毒软件扫描 claude.exe 是常见情形），`pid` 永远是 None → 整个看门狗**一次都不进**
        #   → `state["stopping"]` 永远不会被读到、`/api/stop` 对这次调用完全无效、阶段永久
        #   停在 running、`state["running"]` 恒 True —— 与下面那段注释描述的故障同源。
        #   改成一进循环就重读 pid（worker 写进 sh 之后立刻可见），没拿到就只跳过"需要 pid 的"
        #   动作（强杀/CPU/连接探测），**但 stopping 检查与 drain 照常做**。
        while not sh["done"]:
            await asyncio.sleep(STALL_SAMPLE)
            drain()
            if pid is None:
                pid = sh["pid"]
            if sh["done"]:
                break
            if state["stopping"]:
                if pid is not None:
                    _kill_tree(pid)
                sh["stalled"] = True
                log(f"{sid} 被用户停止，已强杀进程树"); break
            # 用户在超时黄灯上选了「取消并重试」→ 这时才杀（这是唯一在超时后杀进程的路径）
            if state.get("force_retry") == sid:
                state["force_retry"] = None
                if pid is not None:
                    _kill_tree(pid)
                sh["stalled"] = True
                log(f"  🔁 [{sid}] 用户选择「取消并重试」→ 已强杀进程树")
                break
            now = time.time()
            if pid is None:
                # 还没拿到 pid（Popen 慢）：做不了强杀/CPU/连接探测，也**不该**按超时判它
                # —— 但也不能无限等下去（那正是"看门狗永不生效"）。给 5 分钟宽限。
                if now - t0 > 300:
                    sh["stalled"] = True
                    log(f"  🔴 [{sid}] 300 秒仍未拿到子进程 pid（Popen 未返回）→ 放弃等待")
                    break
                continue
            out_recent = (now - sh["last_out"]) < 8
            cpu = _tree_cpu_seconds(pid)          # 整棵进程树(claude+其计算子进程)的 CPU，长计算不误判
            cpu_up = (cpu is not None and last_cpu is not None and cpu - last_cpu > 0.4)
            if cpu is not None:
                last_cpu = cpu
            has_conn = pid in _refresh_tcp()
            if out_recent or cpu_up:
                idle_since = now                      # 有真实进展(输出/CPU)才重置计时
            # 上限与静默容忍都从 state 现读（用户可临时延长；见 _effective_limits）
            cap_s, limit = _effective_limits(sid, cap, has_conn)
            over_stall = (now - idle_since) > limit
            over_cap = (now - t0) > cap_s
            if not (over_stall or over_cap):
                # 已回到限内（用户延长了 / 输出与 CPU 恢复）→ 自动解除黄灯回绿
                p = state.get("pending")
                if p and p.get("kind") == "overtime" and p.get("stage") == sid:
                    _set_pending(None)
                    state["stages"][sid] = "running"
                    log(f"  🟢 [{sid}] 已回到限内 → 黄灯解除，继续运行")
                    emit("state", state2dict())
                # 重新武装黄灯 —— 放在 pending 判断**外面**。
                #   复位若写在 `if p and p.get("kind")=="overtime"` 里面就不成立：
                #   `/api/decision(action=extend)` 自己就 `_set_pending(None)` 了，
                #   于是下一轮采样时 p 恒为 None → 复位**永不执行** → 这个阶段从此
                #   不再亮超时黄灯（code 延长 10 分钟后就再没亮过，
                #   人以为只是没到点，实际它已经跑了 58 分钟）。
                sh.pop("overtime_at", None)
                continue
            if OVERTIME_KILL:
                _kill_tree(pid); sh["stalled"] = True
                log(f"  🔴 [{sid}] {'假死检测' if over_stall else '单次调用硬上限'}超限 → 已强杀，交由重试")
                break
            # —— 转黄灯：**不杀进程**，任务继续跑，等用户决定 ——
            # 去重键必须是「**在这个限值下**报过没有」，不能是"报过没有"这一个布尔。
            #   布尔的话：用户延长限时 → 到点后**再也不会**亮（即上面那个
            #   跑了 58 分钟没人管的另一半）。限值一变就重新武装，才是「延长十分钟
            #   → 十分钟后再问你一次」那个设计意图。
            #   仍然每 STALL_SAMPLE=5s 一轮，但不加锁的话同一限值下会 5 秒刷一次面板。
            # 键里**不能带 `limit`**：`limit` 由 `has_conn` 决定
            #   （有连接时 1200、闲着 300），而 `has_conn` 是每 5 秒现查一次 OS 连接表 ——
            #   于是同一盏灯在两次采样之间键就变，**反复重发**。日志里的形态（`runtime/web_run.log`）：
            #   同一阶段、同一上限 60/70 分钟的两条记录相隔只有 10 秒，一串一串地来。
            #   `kind` 也一并改成**不依赖连接**的判据（否则 idle 落在 300~1200 秒之间时
            #   kind 会在 stall/cap 间翻转，照样重发）：超了墙钟上限就是 cap，否则是 stall。
            overtime_key = (int(cap_s), "cap" if over_cap else "stall")
            if sh.get("overtime_at") != overtime_key:
                st = next(s for s in STAGES if s["id"] == sid)
                # 两种超限可能同时成立，以**墙钟上限**为准（与上面那个键同一判据，别两处不一样）
                _is_cap = bool(over_cap)
                desc = (f"已运行 {int((now - t0) / 60)} 分钟（上限 {int(cap_s / 60)} 分钟）" if _is_cap
                        else f"{int(now - idle_since)} 秒无输出/无 CPU（容忍 {int(limit)} 秒）")
                p = _build_pending(st, "overtime", "overtime",
                                   f"超时，但**任务仍在运行**：{desc}。不杀进程，等你决定。",
                                   decision={}, tail=sh.get("tail", ""),
                                   limit_kind="cap" if _is_cap else "stall", capped=bool(cap))
                p["limit_kind"] = "cap" if _is_cap else "stall"
                p["cap_forced"] = bool(cap)          # 协议级修复的短上限：延长对它无效（见 _action_set）
                _set_pending(p)
                state["stages"][sid] = "awaiting_user"
                sh["overtime_at"] = overtime_key
                log(f"  ⏱ [{sid}] {desc} → 转黄灯等待决策（**任务继续运行**）")
                emit("pending", state2dict())
                # 一键托管：超时这一档**当场**落实（不能等整链停下 —— 那就不叫延长了）。
                #   `_apply_decision` 对 overtime 是明确放行的（链还在跑正是它的场景），
                #   而 extend 只写 retry_cap、不启新链（resumed=False）。
                if state.get("autopilot"):
                    await _autopilot_fire()
    except Exception as e:
        # 看门狗自己出错时**必须补杀**：只记日志就往下走的话，子进程变成孤儿，
        #   而 run_stage 立刻判 failed 并允许重试 → 同工作区两个 agent 并写产物。
        log(f"[{sid}] watchdog 异常: {e} → 已补杀进程树以免孤儿")
        try:
            if pid is not None:
                _kill_tree(pid)
            sh["stalled"] = True
        except Exception:
            pass
    # 必须有上限：worker 线程阻塞在 `for raw in TextIOWrapper(p.stdout…)` 上，只要还有进程
    # 持有那个管道的写端（taskkill 被吞掉/失败的脱离孙进程），读循环就永不 EOF →
    # run_stage 永不返回 → 该阶段永远显示 running、state["running"] 恒 True、/api/stop 失效。
    #
    # 这里**不能**用 `asyncio.wait_for(task, ...)`：`task` 是 `asyncio.to_thread(...)` 包出来的，
    #   线程已经在跑，executor future **不可取消** —— wait_for 超时后会继续等这个 future，
    #   那个"60 秒上限"是假的（WAIT_AFTER_KILL=2 时仍然等满子进程的 30 秒）。
    #   改成轮询 `sh["done"]`（worker 收尾时置位）—— 它是真正的"读循环结束了"信号，
    #   而且不依赖取消能力。超时后**不等** task，直接带着当前 sh 返回，让链按 stalled 走重试。
    deadline = time.time() + WAIT_AFTER_KILL
    while not sh["done"] and time.time() < deadline:
        try:
            drain()
        except Exception:
            pass
        await asyncio.sleep(0.25)
    if not sh["done"]:
        log(f"[{sid}] 强杀后子进程读循环仍未结束（{WAIT_AFTER_KILL}s 超时）→ 放弃等待，按失败重试")
        sh["stalled"] = True
    try:
        drain()
    except Exception:
        pass
    return (sh["rc"] if sh["rc"] is not None else -1), sh["tail"], bool(sh["stalled"])

# ---------------- 计时：跨重跑/跨重启累计（不中途归零） ----------------
# 规则：阶段 elapsed = 该阶段历次运行片段的累计；总耗时 = elapsed_base + 本次 run_all 的墙钟。
# run_all 完整收口(run_completed)后，下一次 start 才整体归零（换题/重跑起点）；中途 stop/关机/挂起一律续跑累计。
CLOCK_FILE = LOG_DIR / ".runclock.json"

def _clock_persist():
    try:
        data = {
            "base": float(state.get("elapsed_base", 0.0) or 0.0),
            "done": bool(state.get("run_completed", False)),
            "stage": {s: float(state["stage_t"][s]["elapsed"] or 0.0) for s in state["stage_t"]},
        }
        CLOCK_FILE.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass

def _clock_load():
    """服务器启动时读回上次计时：未收口(关机/中断) → 续跑累计；已收口 → 数值仍显示，待下次 start 归零。"""
    try:
        if not CLOCK_FILE.exists():
            return
        data = json.loads(CLOCK_FILE.read_text(encoding="utf-8"))
        state["elapsed_base"] = float(data.get("base", 0.0) or 0.0)
        state["run_completed"] = bool(data.get("done", False))
        for s, e in (data.get("stage") or {}).items():
            if s in state["stage_t"]:
                state["stage_t"][s]["elapsed"] = float(e or 0.0)
    except Exception:
        pass

def _finalize_stage(sid):
    """结算某阶段"进行中片段"的耗时（累加进 elapsed 并清 start），防止 stop/杀进程时丢计时。"""
    st = state["stage_t"][sid]
    if st["start"]:
        st["elapsed"] = round(float(st["elapsed"]) + (time.time() - st["start"]), 1)
        st["start"] = None

async def run_stage(stage, round_hint="", repair_only=False, fix_handoff=False):
    sid = stage["id"]; state["cur"] = sid
    state["stages"][sid] = "running"
    emit("state", state2dict())
    art_digest, ins_digest = _input_split(stage)
    inputs = art_digest + ":" + ins_digest
    source_inputs = _source_digest()
    store = _receipt_store()
    out_digest = _output_digest(stage)
    # 返修跑：先把**改前**那一版报告留一份快照，跑完 diff 成一页（`_write_revision_diff`）。
    #   判据是 `round_hint` 非空 —— `run_all` 只在带着回执/人工要求重跑时才传它，新跑与复用
    #   都不会有，于是不留快照（"改前改后"在那两种情形下不成立）。
    #   要防的坏法是**修 A 坏 B**：回执里写着"可放行部分／保留，勿重写"，可那是散文 ——
    #   下一轮评审得重读整份报告才可能发现越界改动，极容易漏（出过这种情况：已独立验证正确的
    #   一个数值在返修里被改错）。落成一页 diff，门禁与人都能直接看到清单外的改动在哪。
    _rev_before = None
    if round_hint:
        _rep = REPORTS / stage["report"]
        if _rep.is_file():
            _rev_before = LOG_DIR / "quality" / f"_rev_{sid}_before.md"
            _rev_before.parent.mkdir(parents=True, exist_ok=True)
            try:
                shutil.copy2(_rep, _rev_before)
            except OSError:
                _rev_before = None
    # 「只有指令变了」的宽待：产物所基于的**事实**没变、产物本身也没被改，只是做法要求
    #   （SKILL / _references / CLAUDE.md / 驱动注入指令）变了 —— 那**不自动重跑**，
    #   只标 `done(stale-instr)` 并记进 state["stale_instr"] 让人看得见。
    #   理由：改一个错别字和改一条门禁规则在字节层面一模一样，驱动判不了「要不要重做」；
    #   而错判成"要重做"的代价是小时级的 code 从零重来，且会**推翻人手工认证的产物**
    #   （那正是 attest 要解决的问题，不能被它自己要修的东西堵死）。
    #   **门禁也走这条路**，不许额外把它排除在外：
    #   "门禁重做很便宜、判据一变必须重判"这条理由本身就自相矛盾 ——
    #   既然承认「驱动用字节分不清错别字与判据变更」，凭什么对门禁就假定它分得清？
    #   否则的后果：往 `_references` 加一条**只管论文措辞**的规矩，就会把 ③ 建模评审门禁
    #   整段拉起来真重判。所以口径统一：**只标记、不重跑**，由人看着标记决定要不要
    #   按新要求重来（面板上那条蓝条会列出来）。**事实（artifacts）变了仍旧自动重跑** ——
    #   那是「论文里的数与你交出去的代码不是一回事」的唯一防线。
    # 人工「接受并披露」的豁免**必须在回执复用之前问**：
    #   排在三条复用近路（stale / ok(skip) / taken-over）**之后**的话，"回执与当前
    #   盘面一致"会先一步返回 `ok`，人明确点过的披露根本没人读 ⇒ 黄灯原地再现、出不去。
    #   触发路径：⑫评分标终审 的 `12 → 13` 交接会**重存一份与当前输入相符的回执**
    #   （`_save_receipt`），此后用户对着 ⑫ 点「接受并披露」→ 下一次跑 ⑫ 命中复用
    #   ⇒ 返回 `ok` ⇒ 裁决里那条 FAIL 被重新读出来 ⇒ 又是同一盏黄灯。
    #   语义上也该如此：豁免是**人的显式决定**，优先级高于"回执说没人动过"。
    #   （输入一变豁免自动失效 —— `_waived` 比的是 digest；`round_hint`/`repair_only`
    #    这两条强制重跑的通道照旧不被豁免拦住。）
    _wrec = _waived(sid, stage)
    # 带交接单来的 ⑬ **不能被豁免吞掉**：⑫/⑮ 刚判出
    #   NEEDS_FIX 把活交给它，若它挂着人工「接受并披露」就 `return "waived"` ——
    #   判词一次都没被重新看过、链却报成功。豁免是人对**那一次**判词的放行，
    #   而这一次是**新的**判词（`fix_loop_return` 非空），照旧要跑。
    if _wrec and not round_hint and not repair_only and not fix_handoff:
        state["stages"][sid] = "done(disclosed)"
        log(f"{sid}: 已由人工披露放行（{_wrec.get('at', '')}），且输入未变 → 跳过执行。")
        _tick(sid)
        return "waived"
    _rec = store.records.get(sid) or {}
    if (_artifact_ok(stage) and not round_hint and not repair_only and not fix_handoff
            and _rec.get("artifacts") == art_digest
            and _rec.get("outputs") == out_digest
            and not store.matches(sid, inputs, out_digest)
            # 门禁的**机械地板**在复用路径上也要过：地板是程序说了算的
            #   客观审计（题意契约/结构化结果/版式/图表/提交清单），便宜且不需要人。
            #   若门禁一走 `stale` 就早返回，它们**整批停摆**；又因为这条路刻意不重存回执
            #   ⇒ 之后每一轮都还是 stale ⇒ **永远不跑**。
            #   地板不过就不走近路、让它真跑 —— `_gate_decision` 会拿同一条地板判失败，
            #   并把正确的返修目标（analysis/code/format/drawio）交给黄灯。
            and _mechanical_floor(stage) is None):
        state["stale_instr"].add(sid)
        # 人工认证过的阶段继续显示为「人工认证」 —— attest 的整个意义就是留下「这一阶段是人放行的」
        #   这个可见痕迹，被 stale 覆盖掉等于又把信息弄丢了（前端明确要求几种完成长得不一样）。
        #   它仍然进 stale_instr（蓝条会列出来），两个信息都在。
        state["stages"][sid] = "done(manual)" if store.is_manual(sid) else "done(stale-instr)"
        log(f"{sid}: 产物与其依据的事实都没变，只有**做法要求**（SKILL/规范/注入指令）变了 "
            f"→ 不重跑，标 {state['stages'][sid]}。要按新要求重来请用「按新指令重跑」"
            f"（门禁也一样：从该阶段重跑）。")
        _tick(sid)
        return "stale"
    if (_artifact_ok(stage) and not round_hint and not repair_only and not fix_handoff
            and _receipt_store().matches(sid, inputs, out_digest)):
        # 人工认证过的阶段不能被画成「干净通过」—— 前端明确要求三种完成长得不一样
        # （干净 / 已披露 / 人工认证）。attest 写回执时打了 manual 标记，
        # 这里按标记复现状态；只要该阶段后来真的重跑过，标记就没了。
        if store.is_manual(sid):
            state["stages"][sid] = "done(manual)"
            log(f"{sid}: 人工认证的产物仍在盘上且输入未变 → 复用（done(manual)）。")
            _tick(sid)
            return "manual"      # 单独一个返回值：run_all 必须据此跳过后面的「重存回执」，
                                 #   那条 save 用默认 manual=False，会把认证标记抹掉。
        state["stages"][sid] = "done(skip)"
        log(f"{sid}: 输入及产物哈希与成功回执一致，复用。")
        _tick(sid)
        return "ok"
    # 「被 format 接管」：format 排在 write 之后，它的职责就是**改 write 写的节文件**
    #   （浮体位置、表宽、溢出压缩…）。那是精修，不是让 write 重做的理由 ——
    #   write 重做会推翻 format 的成果，然后 format 再跑一次，形成乒乓。
    #   判定放在**只读侧**：不重写任何回执，只看「format 是不是刚跑过且之后没人动过」。
    #   一旦 format 的输入/产物任一失配（format 自己也要重跑），这条就不成立，自动回到正常判定。
    # 「被下游接管」的适用面：
    #   · ⑨ 的产物是 `paper/` + `paper_appendix/`、⑬ 的产物含 `paper/`，这两个目录会被
    #     **后继阶段合法改写**（⑭ 版式精修、⑮ 并不写）⇒ 它们的 `outputs` 半份必然对自己的
    #     回执失配，走不到上面那条 `stale` 近路。
    #   · 只认 ⑨ 一家是不够的。⑬ 少了这条的后果：⑭ 每跑一次（它的版式手术会落进
    #     `paper/sections/*.tex`），⑬ 的回执必失配 ⇒ 下一轮 ⑬ 又被拉起来重跑一遍
    #     —— 这正是要解耦掉的那条环路：⑭⑮ 不该跟 ⑫⑬ 绑在一起。
    #   · **⑬ 还要多一个闸**：⑫ 刚刚判出判词、把活交下来时（`fix_loop_return`），
    #     这一轮**必须真跑** ⑬，不能被"被接管"吞掉 —— 否则「12 没过 → 等 13 处理 → 回 12」
    #     这条设计路径会被静默跳过。只有**没有新判词要处置**的那些轮次才适用接管。
    if ((sid in _PAPER_OWNED_STAGES or sid in _CONTENT_JUDGE_STAGES)
            and not round_hint and not repair_only and _artifact_ok(stage)
            and not fix_handoff):
        # 判据抽成 `_taken_over_by()`，与启动反推（`_restore_stale_instr`）共用同一份 ——
        #   否则同一盘面「链上算的」与「重启反推的」会不一致。
        owner = _taken_over_by(stage)
        if owner is not None:
            rec_self = store.records.get(sid) or {}
            if rec_self.get("instructions") != ins_digest:
                # write **自己的**做法要求也变了（例如改了 skills/9Paper-writing）→ 按 stale 处理：
                # 产物保留、但如实标出来"它是按旧要求做的"。不能因为被接管了就把它
                # 画成干净通过（前端明确要求几种完成长得不一样）。
                state["stale_instr"].add(sid)
                state["stages"][sid] = ("done(manual)" if store.is_manual(sid)
                                        else "done(stale-instr)")
                log(f"{sid}: 已被 {owner} 接管，但本阶段的**做法要求**也变过 → "
                    f"标 {state['stages'][sid]}（不重写，以免推翻下游改动）。")
                _tick(sid)
                return "stale"
            # 必须返回一个**独立** outcome：返回 "ok" 会落进 run_all 的公共尾巴，
            #   被那里的 `_save_receipt()`（默认 manual=False）把「人工认证」标记抹掉 ——
            #   第 3 轮就退化成 `done`，面板从此把「人放行的」画成「干净通过」。
            state["stages"][sid] = "done(manual)" if store.is_manual(sid) else "done(skip)"
            if sid in _CONTENT_JUDGE_STAGES:
                # 内容判官的例外：被打的是**审查对象**（`paper/`）的版式侧，不是它的产物。
                state.setdefault("layout_superseded", set()).add(sid)
                log(f"{sid}: 它的审查对象此后只被 {owner} 的**版式**改过（正文一字未动）→ "
                    f"按「版式改动不作废内容判据」保留原裁决、不重判。"
                    f"要重判请从该阶段重跑（面板上选它）。")
            else:
                log(f"{sid}: 论文已被 {owner} 接管（它的产物未被改动）→ 不重写，避免推翻下游改动。")
            _tick(sid)
            return "taken-over"
    # 人工「接受并披露」的豁免（机器可读）。输入一变 digest 就对不上 → 豁免自动失效、门禁重新生效。
    # （人工「接受并披露」的检查已上移到回执复用之前 —— 见那段注释；这里不再重复。）
    # ⓪ 读题：人工已确认、且输入没变 ⇒ **不重跑 AI**。
    #   放在 `_invalidate_stage` **之前**：这是一次"复用"，不该作废自己的回执；
    #   也放在 `_stash_markers_for_restore` 之前：不该把自己的产物搬走。
    #   `round_hint` 非空 = 用户点了「再试一次」⇒ 必须真重跑（那是"重读一遍"的唯一出口）。
    if sid == "intake" and not round_hint and not repair_only:
        _crec = _intake_confirmed()
        if _crec and _crec.get("digest") == _source_digest():
            restored = _restore_intake_artifacts()
            state["stages"][sid] = "done(confirmed)"
            _save_receipt(stage)
            _tick(sid)
            log("⓪ 读题：已由人工确认（" + str(_crec.get("at", "")) + "）⇒ 不重跑"
                + ("，并恢复产物 " + "、".join(restored) if restored else "")
                + " —— 直接进 ① 文献定向")
            return "confirmed"
    index = next(i for i, st in enumerate(STAGES) if st["id"] == sid)
    _invalidate_stage(index)
    state["stages"][sid] = "running"
    _finalize_stage(sid)
    state["stage_t"][sid]["start"] = time.time()
    rc, tail, stalled = -1, "", False
    env_retry_left = 1 if AUTO_RETRY_ENV_ERROR else 0
    attempt, limit_attempts = 0, MAX_ATTEMPTS_PER_STAGE
    markers_restore = None            # 见 `_stash_markers_for_restore` 的 docstring
    _succeeded = False                # 本轮走到了"成功"分支吗（见 finally 里那条判据）
    # Remove only the completion marker; keep implementation/sections available for repair.
    # Archiving prevents a no-op or failed invocation from passing on an old report/PDF.
    # repair_only：仅裁决格式/一致性问题 → 只清侧车，保留报告本体（审查结论仍有效）。
    #
    # **暂存只做一次，放在重试循环之外**：
    #   若每次尝试都重建一份闭包：第 1 次尝试已经把源件**搬进** `_pending_markers/`，
    #   第 2 次再调时 `tgt.exists()` ⇒ 全跳过 ⇒ 拿到的是**空 mapping** ⇒ 这次若被打断，
    #   `markers_restore(force=True)` 遍历空表什么都不做、随后 rmtree 把那份删掉
    #   ⇒ `reports/` 与暂存**两头都没有**（下游回执的 artifacts 半份随即失配 ⇒ 下游整段重跑）。
    #   可复现的触发路径：环境类错误 `rc=-1 + "not found"`（claude.exe 换了目录）触发第 2 次尝试。
    #   `rep` / `markers` 三个分支与 attempt 无关，hoist 出来语义不变。
    rep = stage["report"]
    if repair_only and not rep.startswith("paper"):
        _markers = ["reports/" + str(Path(rep).with_suffix(".verdict.json"))]
    else:
        _markers = (["paper/main.pdf"] if rep.startswith("paper") else
                    ["reports/" + rep, "reports/" + str(Path(rep).with_suffix(".verdict.json"))])
    markers_restore = _stash_markers_for_restore(sid, _markers)
    try:
        while attempt < limit_attempts:
            attempt += 1
            if state["stopping"]:
                break
            note = round_hint
            if attempt > 1:
                note += f"\n第 {attempt} 次执行：上次失败或未生成有效产物。失败摘要：{tail[-1500:]}"
            state["attempts"][sid] = int((state.get("attempts") or {}).get(sid, 0)) + 1
            rc, tail, stalled = await _call(prompt_for(stage, attempt) + "\n" + note, sid,
                                            cap=CALL_PROTOCOL_CAP if repair_only else None)
            if state["stopping"]:
                break
            if rc == 0 and not stalled and not _artifact_ok(stage) and HANDBACK.exists():
                # agent 按 SKILL 主动交回上游（9Paper-writing/11Cross-question-check：发现前序问题 → 写
                # reports/HANDBACK_REQUEST.md 并结束本轮，此时本就不该产出产物）。产物门禁在此不适用：
                # 若照常判失败，会"重试全部无产物 → 挂起"，正确的动作（退回 code 补算）永远执行不到，
                # 而且每次重试都被催产物，等于逼 agent 在未核实的数值上硬把论文写出来。
                # 交给 run_all 的 check_handback 消费它。
                state["stages"][sid] = "awaiting_review"
                _record_quality(stage, "handback", "阶段按 SKILL 交回上游问题，本轮不产生产物")
                log(f"{sid}: 检测到 reports/HANDBACK_REQUEST.md，按交回上游处理（不判失败）。")
                # 这条出路**必须把上一份原路搬回**：
                #   它有意不产出报告，于是 `finally` 里两个分支都不成立（没 stopping、
                #   `_artifact_ok` 也假）⇒ 上一份报告与裁决侧车被**扣在 `_pending_markers/` 里**，
                #   `reports/` 空着 ⇒ `gate_result()` 只能给 UNVERIFIED ⇒ run_all 在裁决检查
                #   那儿就 halt，**根本走不到 `check_handback`** ⇒ 交回单推荐的"退回 code 补算"
                #   永远执行不到（MODELING_REVIEW_REPORT.md 与侧车会双双消失）。
                if markers_restore is not None:
                    markers_restore()
                    log(f"↩️ [{sid}] 按交回上游处理且本轮不产生产物 —— 把开跑前搬走的那一份搬回来了")
                _tick(sid)
                return "ok"
            if rc == 0 and not stalled and _artifact_ok(stage):
                # 门禁这一路只比 **artifacts 半份**。
                #   若写成 `_input_digest(stage) != inputs` —— 那是**整份**（事实 + 做法要求），
                #   于是「门禁执行期间改了一句 CLAUDE.md / SKILL」就会被判成
                #   "输入在该阶段执行期间被改动，不能冒充成功交付"**硬挂**。
                #   而 `_input_split` 的整套设计恰恰相反：改了做法要求 → 只标 stale，不硬挂
                #   （见该函数 docstring 与上面那段宽待注释）。两处自相矛盾。
                #   典型后果：加 ⑧ 的同时顺手改了 CLAUDE.md/AGENTS.md，正在跑的 ③ 建模评审
                #   门禁当场挂成 `unverified`，而它审的那份报告一个字都没动 —— 而它给出的
                #   提示还指错了方向（"往 request/data 放文件、或改了被审论文/代码"，两件都没发生）。
                #   真正要防的是**门禁改了被审对象**，那在 artifacts 半份里；做法要求变了交给
                #   回执/stale 机制在下一轮处理。
                if (_source_digest() != source_inputs
                        or (stage.get("gate")
                            and _input_split(stage)[0] != art_digest)):
                    _record_quality(stage, "unverified", "审核/执行期间输入发生变更")
                    state["stages"][sid] = "unverified"
                    _tick(sid)
                    return "unverified"
                # 成功：清掉可能存在的超时黄灯 —— 「等待决策期间它自己跑完了 → 自动转绿」
                pend = state.get("pending")
                if pend and pend.get("stage") == sid:
                    _set_pending(None)
                    log(f"  🟢 [{sid}] 任务在等待决策期间自行完成 → 黄灯解除")
                state["stages"][sid] = "done" if not stage.get("gate") else "awaiting_review"
                _succeeded = True          # ← 见 finally 里那条"保留新产物还是原路搬回"的判据
                if not stage.get("gate"):
                    _save_receipt(stage)
                _record_quality(stage, "executed", "进程成功且本次生成完成产物")
                if _rev_before is not None:
                    # 辅助留证，**绝不许**它把阶段带崩：出错只记一行日志。
                    try:
                        _write_revision_diff(sid, _rev_before)
                    except Exception as exc:      # noqa: BLE001
                        log(f"⚠️ {sid}: 返修改动对照生成失败（不影响本阶段结果）：{exc}")
                _tick(sid)
                return "ok"
            # 环境类错误（claude.exe 路径失效）自动重试一次，不打扰用户 —— 这不是阶段失败
            if rc == -1 and env_retry_left > 0 and "not found" in (tail or ""):
                env_retry_left -= 1
                limit_attempts += 1          # 不占用阶段尝试额度
                log(f"{sid} 环境错误（claude.exe 未找到）→ 自动重试一次")
                continue
            log(f"{sid} 执行第 {attempt} 次失败 rc={rc} stalled={stalled} artifact={_artifact_ok(stage)}")
    finally:
        state["retry_cap"].pop(sid, None)    # 「临时延长」只生效于这一次执行
        # 开跑前搬走的那一份怎么处置（见 `_stash_markers_for_restore`）：
        #   · 阶段**被打断**且没产出有效产物 ⇒ **原路搬回** —— 「只不过按了暂停」不该
        #     让上一份完好的报告永久躺进 cache、更不该顺带把 ④–⑯ 全判成要重跑；
        #   · 产出了有效产物 ⇒ 旧副本作废，丢掉；
        #   · 失败（非打断）⇒ 副本留在 `runtime/quality/_pending_markers/<sid>/` 可恢复，
        #     下一轮成功时清掉。（失败那条路**不**回填：`test_noop_cannot_reuse_old_completion_marker`
        #     钉的就是「不出产物就不许拿旧产物冒充完成」。）
        if markers_restore is not None:
            # 判据不能只是「产物在不在」，要看「**这次有没有真的产出可接受的东西**」——
            #   只看产物会**丢数据**：门禁的 SKILL 要求「先落骨架」（§6.1），而 `_artifact_ok` 只看
            #   "文件在、>80 字节"，一份 **562 字节的骨架**照样通过 ⇒ "写了骨架就被打断" 会被
            #   当成"产出了有效产物" ⇒ 驱动把开跑前那份**完好的裁决丢掉**。
            #   实例：⑮验收 的 26 KB 报告 + 15 KB 裁决被 562 字节的骨架顶掉，按一次暂停
            #   就没了（要从 redo 的 cache 里捞回来才能复原）。
            #   回执是**跑之前刚被作废**的（`_invalidate_stage`），只有真正成功才会被重新写上
            #   ⇒ 拿它当判据既准确、又不用猜"多大算真产物"。
            #   必须**新读一份**：`store` 是 run_stage 进来时的快照，那时回执还在，
            #     拿它判会永远为真。
            #   但**只看回执又会漏掉门禁**：门禁的回执由 `run_all`
            #   在裁决定下之后才写，`run_stage` 这一层不写 ⇒ 门禁**真跑成功**时 `_produced`
            #   也是 False ⇒ `drop` 那条永不执行 ⇒ 副本一直留着，而下一轮
            #   `_stash_markers_for_restore` 见到 `tgt.exists()` 就跳过（"多尝试要累积"）
            #   ⇒ 开跑前那份既没被保护、打断时还跟着 `rmtree` 一起被删。
            #   所以判据是**三条取或**（任一成立 = 本轮真的产出了可接受的东西）：
            #     ① 走到了成功分支（`_succeeded`，最准）
            #     ② 回执已被写下（`_produced`）
            #     ③ 进程正常退出、产物在盘上、且门禁的裁决侧车**不是** UNVERIFIED
            #        —— 兜住"agent 刚写完就被按暂停"那一瞬间：那种新产物是完整的，
            #        不该被旧版换回去。骨架会被 ③ 排除（骨架的 status 就是 UNVERIFIED）。
            _produced = bool(_receipt_store().records.get(sid))
            _keep_new = _succeeded or _produced or (
                rc == 0 and not stalled and _artifact_ok(stage)
                and not _looks_like_a_skeleton(stage))
            if state["stopping"] and not _keep_new:
                markers_restore(force=True)      # 覆盖盘上那份半成品（骨架）—— 见 _restore 的说明
                log(f"↩️ [{sid}] 被打断且未产出有效产物 —— 把开跑前搬走的那一份搬回来了")
                # **回执也要跟着恢复**：
                #   `run_stage` 一开跑就 `_invalidate_stage(index)` 把回执照废，而这里
                #   又把产物**原路搬回** ⇒ 盘面已经等于开跑前那一版 ⇒ **旧回执重新成立**
                #   （裁决侧车也在 `_stage_rels` 里、一并搬回 ⇒ 裁决与产物仍然对应）。
                #   不补这一步的后果：**暂停一次**，该阶段从此**永远没有回执**
                #   ⇒ 之后每一轮点「开始全链」都重跑它（③ 建模评审门禁 会被反复重判）。
                #   只在**这一条路**补：产物已原路搬回、盘面确实等于旧版 ⇒ 如实；
                #   失败/部分产出那条路**照旧不回填**（「不出产物就不许拿旧产物冒充完成」，
                #   由 `test_noop_cannot_reuse_old_completion_marker` 钉着）。
                _save_receipt(stage)
            elif _keep_new:
                # 只有**真的成功过**才作废旧副本。写成 `elif _artifact_ok(stage)` 就自相矛盾：
                #   它和本函数上方写的"失败（非打断）⇒ 副本留在 _pending_markers 可恢复"打架，
                #   一次失败的尝试只要留下了半份报告，旧副本就被 drop 掉了。
                markers_restore(drop=True)
    status = "stopped" if state["stopping"] else "failed"
    state["stages"][sid] = status
    state["last_tail"] = tail          # 供 _halt 带进 pending，重试时拼回 prompt
    _record_quality(stage, status, f"rc={rc}; stalled={stalled}")
    _tick(sid)
    return status


def _tick(sid):
    """推进：累计更新耗时（不清零，多次运行片段叠加）并广播。"""
    st = state["stage_t"][sid]
    if st["start"]:
        st["elapsed"] = round(float(st["elapsed"]) + (time.time() - st["start"]), 1)
        st["start"] = None
    state["progress"]["done"] = sum(1 for s in STAGES if str(state["stages"][s["id"]]).startswith("done"))
    _clock_persist()
    emit("state", state2dict())

# 阶段别名表（**单一出处**：`_resolve_stage_id` 与 `_target_index` 共用一份）。
# 表里只有"主表（skill 目录名 → id）之外"的额外写法。
#
# 查表必须两侧同一套归一化：查表用的是 `.lower()`，而键若是**原样大小写**的 skill
#    目录名，那么目录按「序号+英文」命名（`9Paper-writing` / `14Layout-and-format`）时，
#    **16 个 skill 名就一个都查不中**（查表侧小写、键侧大写）。后果两条，都不轻：
#      ① `HANDBACK_REQUEST.md` 写 `target: 9Paper-writing` ⇒ `check_handback` 抛
#         「target 不是已知阶段」⇒ 整链按"驱动异常"停机；
#      ② 裁决里的 target 写 skill 名 ⇒ `_target_index` 静默退回默认映射 ⇒ 黄灯推荐的回退
#         阶段是错的（不报错，最坏的一种）。
#    所以：键统一小写（表里照旧写人类可读的原名，构建时 lower 一遍）。
_LEGACY_STAGE_ALIASES = {
    # 改名前的旧目录名 —— 老工作区遗留的 HANDBACK/裁决里可能就是这些，照旧认，不要 400/停机。
    "1literature": "literature", "2modeling": "analysis", "4review": "review",
    "5coding": "code", "6robustness": "robustness", "7drawio": "drawio",
    "8figreview": "figreview", "10figreview": "figreview", "9writing": "write",
    "9format": "format", "14format": "format", "10mathproof": "mathproof",
    "10cross": "cross", "12rubric": "rubric", "13fix": "fix", "14fix": "fix",
    "11verity": "verify", "15verify": "verify", "web-demo": "demo",
    # 更早的一批名字（`lib/web/healthcheck.py` 的「无旧编号残留」清单里就有它们）
    "2analysis-modeling": "analysis", "3coding-visual": "code",
    "5writing": "write", "6verity": "verify",
    # 人类口语/文档里出现过的写法（3analysis 是 CLAUDE.md 与 CONTENT_QUALITY.md 里的旧行标签）
    "3analysis": "analysis", "writing": "write", "formatting": "format",
    "绘图门禁": "figreview",
}


def _stage_aliases():
    """skill 目录名（小写）+ 旧名 + 口语名 → 阶段 id。**键一律小写**，查表侧同样 lower。"""
    table = {s["skill"].lower(): s["id"] for s in STAGES}
    table.update({k.lower(): v for k, v in _LEGACY_STAGE_ALIASES.items()})
    return table


def _resolve_stage_id(name):
    """把 HANDBACK 里写的 target（阶段 id 或 skill 名/别名）解析成 STAGES 里的 id；不认识返回 None。"""
    aliases = _stage_aliases()
    t = aliases.get((name or "").strip().lower(), (name or "").strip().lower())
    return t if any(s["id"] == t for s in STAGES) else None


def check_handback(cur_idx):
    """Return a validated earlier stage; malformed requests block instead of disappearing.

    区分两种"不行"，处置相反：
    - **target 不是已知阶段**（缺字段/拼错/乱写）→ 真·格式错误，抛错拦住，不许无声消失。
    - **target 是已知阶段但不是当前阶段的前序**（index >= cur_idx）→ 只可能是**上一轮遗留**的
      HANDBACK（本轮还没跑到它，不可能是本轮提出的）。这类必须归档放行：本函数在每个阶段都被
      无条件调用，而旧实现对 index >= cur_idx 一律抛 ValueError —— 链首 cur_idx=0 时任何 target
      都满足该条件，于是上一轮 write 按 SKILL 交回 code 后留下的 HANDBACK 会把整条链顶死在
      ① 文献阶段（被 run_all 的 except 吞成"驱动异常"），每次重启 100% 复现，HIL_DECISION 给的
      三条建议都治不好 —— 这就是"砖"。
    """
    if not HANDBACK.exists():
        return None
    text = HANDBACK.read_text(encoding="utf-8", errors="replace")
    match = re.search(r"^\s*target\s*[:：]\s*([a-z0-9_-]+)\s*$", text, re.M | re.I)
    if not match:
        raise ValueError("HANDBACK_REQUEST.md 缺少有效 target")
    name = match.group(1)
    resolved = _resolve_stage_id(name)
    if resolved is None:
        raise ValueError(f"HANDBACK_REQUEST.md 的 target 不是已知阶段：{name}")
    index = next(i for i, s in enumerate(STAGES) if s["id"] == resolved)
    if index >= cur_idx:
        # 落点必须走**选定产物目录**下的 cache：不传 `dest_root`
        #   会落到旧常量 `CACHE = ROOT/"cache"` —— 那是**项目根**下的第二个 cache 根，
        #   不在 `CLEANUP_RELS` 里 ⇒ 🧹清理永远不动它、面板的产物视图也看不见它。
        #   这曾是改版漏搬的最后一个默认落点调用者。
        from lib.delivery.core import delivery_name
        # `delivery_name` 对含 `\/:*?"<>|` 的题目标识**会抛 ValueError**（它自己的约定），
        #   而题目标识是 `.env`/面板可填的。这里不设防的话 ⇒ 一个手滑的标识（例如
        #   `2026A:B`）会把链炸成"驱动异常"，而不是一条能看懂的提示。照 `_delivery_status`
        #   与 `_redo_from` 那两处的处置一致（同一类问题）。
        try:
            _stamp = delivery_name(_recorded_problem_id())
        except ValueError as exc:
            _stamp = "题目标识非法"
            log(f"⚠️ 题目标识不能用作归档目录名（{exc}）—— 这份交回单改按「{_stamp}」暂存")
        _stash_paths(["reports/HANDBACK_REQUEST.md"],
                     dest_root=_cache_dir() / _stamp / "旧交回单")
        log(f"⚠️ 发现上轮遗留的 HANDBACK_REQUEST.md（target={name} 在第 {cur_idx + 1} 阶段"
            f"不构成前序返修）→ 已移入 <产物>/cache/ 暂存并继续全链，不阻断本轮。")
        return None
    return index


def _target_index(target, cur_idx):
    aliases = _stage_aliases()
    # 与姊妹函数 _resolve_stage_id 保持同一套归一化（strip+lower）。只在那一边做的话，
    # verdict 里写 "Drawio" / " drawio " 会**静默**退回默认映射（write），
    # 而同样的写法写在 HANDBACK_REQUEST.md 里却能解析 —— 同义不同命的坑。
    t = (target or "").strip().lower()
    target = aliases.get(t, t)
    index = next((i for i, s in enumerate(STAGES) if s["id"] == target), None)
    if index is None or index >= cur_idx:
        raise ValueError(f"返修目标必须是有效前序阶段，收到 {target!r}")
    return index


def _mechanical_floor(stage):
    """门禁的**机械地板**：程序说了算的客观审计（题意契约/结构化结果/版式/图表/提交清单）。

    与 agent 的裁决分开：这批检查便宜、客观、不需要人，所以门禁在
      **复用路径**（`stale`）上也要过一遍 —— 若它一走早返回，地板整批停摆，
      又因为那条路刻意不重存回执 ⇒ 之后每一轮都还是 stale ⇒ **永远不跑**。
    返回一个 decision dict（不返回 = 地板通过）或 None。
    """
    if not stage.get("gate"):
        return None
    if (ROOT / "config/content_quality.json").exists() and stage["id"] in {"review", "audit", "cross", "verify"}:
        problems = task_contract_issues(ROOT)
        if problems:
            return {"status": "NEEDS_FIX", "reason": "task_contract_failed", "target": "analysis",
                    "issues": [{"id": "task_contract", "severity": "hard", "evidence": "; ".join(problems),
                                "fix": "按 docs/CONTENT_QUALITY.md 对照原题修复题意到模型的映射，不能只改披露措辞",
                                "recheck": "逐项复核 reports/TASK_CONTRACT.json 与原题及模型"}]}
    if stage["id"] in {"audit", "verify"} and (ROOT / "config/result_contract.json").exists():
        problems = audit_results(ROOT, rendered=stage["id"] == "verify")
        if problems:
            return {"status": "FAIL", "reason": "result_contract_failed", "target": "code",
                    "issues": [{"id": "result_contract", "severity": "hard", "evidence": "; ".join(problems),
                                "fix": "按 docs/RESULT_CONTRACT.md 补全或刷新结构化结果及独立校验；先复用已保存结果，不默认重跑优化器",
                                "recheck": "python -m lib.result_contract audit"}]}
    if stage["id"] == "verify" and (ROOT / "config/publication.json").exists():
        report = audit_publication(ROOT, detail=True)
        problems = report["issues"]
        if problems:
            # 回退目标按「**谁有权改**」分，不按「哪一类检查」：
            #   `publication` 类的默认目标是 ⑩排版，但**摘要写没写满**是文字层面的缺陷，
            #   ⑩ 只管版式、无权动内容 ⇒ 判给 ⑩ 必然来回打转（摘要是 ⑨ 写在 main.tex 的
            #   `\abstractcn{}` 里的）。判据 = checks.py 打的 `prose_issues` 标记。
            #   条件取「**沾上文字缺陷就归 ⑨**」而不是「只有文字缺陷才归 ⑨」：⑨ 在 ⑩ 的**上游**，
            #   回退到 ⑨ 会把 ⑩ 一起重跑（版式那几条照样会在 ⑩ 的机械地板里被再查一遍）；
            #   反过来判给 ⑩，文字那一条谁也改不了 ⇒ 下一轮还是 FAIL ⇒ **死循环**。
            #   宁可多跑一轮 ⑨，也不能让链子转不出去。
            _prose = set(report.get("prose_issues") or [])
            _has_prose = bool(_prose) and not set(problems).isdisjoint(_prose)
            return {"status": "FAIL", "reason": "publication_check_failed",
                    "target": "write" if _has_prose else "format",
                    "issues": [{"id": "publication", "severity": "hard", "evidence": "; ".join(problems),
                                "fix": ("按 docs/PUBLICATION.md 补写摘要正文（每问的方法要点、结论数字、"
                                        "检验与灵敏度各写足，把版心填充做到 ≥90%；规则见 ⑨ 的 SKILL"
                                        "「摘要与关键词纪律」），改完重编译两遍并重新绑定 page-map；"
                                        "同批里的页数/映射/裁切问题由下游的 ⑩ 一并处理"
                                        if _has_prose else
                                        "按 docs/PUBLICATION.md 修复页数、物理页映射或裁切问题，保留核心证据"),
                                "recheck": "python -m lib.publication check"}]}
    if stage["id"] == "verify" and (ROOT / "config/visualization.json").exists():
        problems = audit_figures(ROOT)
        if problems:
            # 图表登记/过期资产/视觉复核 → format（重渲染脚本、重新登记、重新目检都是它的活）。
            # 若根子在图本身画错了，format 按「返修只动清单内」交回 drawio / code。
            return {"status": "FAIL", "reason": "figure_evidence_failed", "target": "format",
                    "issues": [{"id": "figures", "severity": "hard", "evidence": "; ".join(problems),
                                "fix": "按 docs/VISUALIZATION.md 修复图表登记、过期资产或视觉复核",
                                "recheck": "python -m lib.visualization audit"}]}
    # 绘图门禁的**机械地板**（⑧，紧跟 ⑦）。与上面三条客观审计同一写法：程序说了不合格
    #   就直接判失败，不看 agent 的裁决 —— 免得一个宽松的审查者把机器已判死的图放行。
    #   通过时**不返回**，落到下面读 agent 的侧车：它可能因为"选型不合适、可读性差"这类
    #   程序看不见的理由判 FAIL（那正是这一阶段存在的意义）。
    #   只回 ⑦：它按自己的交回规则处理（数据图的问题写 HANDBACK_REQUEST 交回 ④）。
    if stage["id"] == "figreview" and (ROOT / "config/visualization.json").exists():
        problems = audit_figures(ROOT)
        if problems:
            return {"status": "FAIL", "reason": "figure_evidence_failed", "target": "drawio",
                    "issues": [{"id": "figures", "severity": "hard", "evidence": "; ".join(problems),
                                "fix": "按 docs/VISUALIZATION.md 修复。**先分清是哪一类**："
                                       "① 过期资产/复核签名失效（多半是改了 `config/visualization.json` "
                                       "或 `lib/visualization/*.py`）→ **只需重跑 `figures/make_figures.py` "
                                       "重渲染、重新登记、重新目检，绝不要重算数值**（重算是小时级，"
                                       "而图的内容没变）；② 位图质量/图例压数据 → 改画图脚本的那一张；"
                                       "③ drawio 版式体检不过 → 改 .drawio 的形状/位置。"
                                       "**别只补登记记录** —— 那是洗白。",
                                "recheck": "python -m lib.visualization audit"}]}
    # 与上面四个客观审计同一个开关约定：只在**启用该配置**的工作区里跑。
    #   少了这个 gate 时，任何没有提交清单的工作区都会在 verify 卡死 —— 会把
    #   22 个全链用例一次打红（它们大多不碰交付层）。
    if stage["id"] == "verify" and DELIVERY_CFG.exists():
        # 提交清单的**早期**核对。打包发生在整链收口时，那时才发现「清单没写 / 清单里
        # 少了一个 .py」，已经白跑好几小时（demo 之后还要再跑一遍 format+verify+rubric）。
        # verify 是 demo 之前最后一关，在这里拦住最划算。
        # `demo.html` 是例外：它由排在 verify **之后**的 16Web-demo 产出，此刻本就不该存在。
        from lib.delivery.checks import precheck
        problems = precheck(ROOT)
        if problems:
            return {"status": "FAIL", "reason": "delivery_manifest_incomplete", "target": "format",
                    "issues": [{"id": "delivery_manifest", "severity": "hard",
                                "evidence": "; ".join(problems),
                                "fix": "补齐 reports/SUBMISSION_MANIFEST.json，并确保它声明的每个文件都在盘上"
                                       "（`python -m lib.delivery check` 可本地复核 —— **只在收口打包之后跑**："
                                       "链中途提交目录还是空的，跑了必然 FAIL，那是时序问题不是缺件）",
                                # 不能写 `--root .` —— argparse 的全局选项必须在子命令**之前**，
                                #   那个形式会报 "unrecognized arguments"。
                                #   命令在项目根跑，`--root` 默认就是 cwd。
                                "recheck": "python -m lib.delivery check  # 仅收口打包后"}]}
    return None


def _read_sidecar_digest(report_path):
    """读裁决侧车里记的 input_digest（没有/读不出返回 None）。只给 _gate_decision 用。"""
    try:
        data = json.loads(Path(report_path).with_suffix(".verdict.json").read_text(encoding="utf-8"))
        digest = data.get("input_digest")
        return digest if isinstance(digest, str) and digest else None
    except Exception:                       # noqa: BLE001 —— 读不到就当没有，走原来的严格判据
        return None


def _gate_decision(stage):
    if not stage.get("gate"):
        return {"status": "PASS", "reason": "not_gate", "issues": []}
    # 先过机械地板 —— 程序说了算的那几条，与 agent 的裁决分开（见 _mechanical_floor）。
    floor = _mechanical_floor(stage)
    if floor is not None:
        return floor
    strict = (ROOT / "config/content_quality.json").exists()
    # 门禁裁决也享受「只有做法要求变了 ⇒ 不重判」那条宽待（与回执同口径）。
    #   背景：侧车记的是"这份裁决是在哪版输入上做的"（`input_digest` = artifacts:instructions）。
    #   而**批量改 SKILL / 规范**会让每个门禁的 instructions 半份都变 ⇒ 侧车一律判"过期" ⇒
    #   每个门禁都会白重判一遍（点「开始全链」之后 ①② 复用、③ 却被拉起重判）。
    #   这与上面那条口径矛盾（"改一个错别字和改一条门禁规则在字节层面一模一样" ⇒
    #   不能因此把贵的阶段拉起来；**事实（artifacts）变了才必须重判**）。
    #   做法：侧车记的 artifacts 半份与当前**相同** ⇒ 拿侧车记的那份 digest 去读它自己
    #   （两边自洽 ⇒ 裁决有效）；artifacts 不同 ⇒ 照旧判过期（正文/报告真变了）。
    _digest = _input_digest(stage)
    _recorded = _read_sidecar_digest(REPORTS / stage["report"])
    if _recorded and _recorded.split(":")[0] == _digest.split(":")[0]:
        _digest = _recorded
    decision = read_verdict(REPORTS / stage["report"], stage["id"], _digest, allow_v2=strict)
    if strict:
        if decision.get("reason") == "verdict_conflict":
            # 正文裁决行与侧车 JSON 冲突：两侧结论不可信，且侧车的 status/target 是 agent 写的、
            # 未经 enforce 校验 —— 绝不放行（否则可被洗成 REVISE_CLAIM 条件放行或拿非法 target
            # 崩驱动）。统一判 UNVERIFIED 并要求重产一致裁决。
            conflict = decision.get("conflict") or {}
            return {"status": "UNVERIFIED", "reason": "verdict_conflict",
                    "issues": [{"id": "verdict_conflict", "severity": "hard",
                                "evidence": f"报告末尾裁决行={conflict.get('markdown')!r}，"
                                            f"侧车 JSON status={conflict.get('json')!r}；两者必须一致",
                                "fix": "只改其一使其一致（报告末尾裁决行或 .verdict.json 的 status），"
                                       "并保证 v2 侧车含 checks 与 typed issues",
                                "recheck": "重读报告末尾裁决行与侧车 JSON"}]}
        decision = enforce_content(ROOT, stage["id"], decision, [s["id"] for s in STAGES])
    return decision


def gate_result(stage):
    decision = _gate_decision(stage)
    status = decision["status"]
    if status in {"PASS", "APPROVED", "CLEAN"}:
        return "ok"
    # A claim correction is an explicit conditional handoff to writing, not a numerical failure.
    # 可达路径：门禁的必查项里有**不在 `RESULT_CHECK_CATEGORY` 反推表**里的那几条
    #   （audit 的 `claim_scope`、cross 的 `narrative_consistency`、
    #   verify 的 `content_coverage` / `narrative_consistency`），审查者把它们填成
    #   category=claim，且**全部**未解决项都是 claim 时，`enforce` 才判 REVISE_CLAIM。
    #   rubric 走 `_rubric_route`，只会给 PASS / NEEDS_FIX，不会给出这个状态 ⇒
    #   非门禁与 rubric 都不受影响。
    #   这里不能写死 `and stage["id"] == "audit"` —— 那是只有 audit 有这条通道的年代
    #   留下的，`cross` 加进来时不跟着改 ⇒ **⑪ 的纯 claim
    #   判词就根本走不到 `claim_revision`**，落进下面 `verdict not in {...}` 的通用分支
    #   当场 `_halt` 转黄灯（⑪ 一直判失败的成因有一半是这个）。
    #   所以不再列举阶段名：能产出 REVISE_CLAIM 的只有上面那三条必查项，
    #     而 `enforce` 已经保证"没有具体 failed 检查就不许挂这个状态"。
    if status == "REVISE_CLAIM":
        return "claim_revision"
    return status


# 门禁「**没跑完**」而不是「判你不合格」时的 reason。这类裁决里没有可执行的修法 ——
# 它们说的是「裁决侧车缺了 / 格式错了 / 根本没报告」，而那是**门禁自己**该交的东西。
PROTOCOL_REASONS = {"no_report", "verdict_malformed", "verdict_conflict", "verdict_stale"}


def _fold_in_deferred_advisories(hints, stage, target, sid):
    """把门禁的**延后建议**按去向折进各阶段的 `hints`，返回实际投递的条数。

    为什么需要它：`run_all` 那条投递的条件是
    `any(s["id"] == dest for s in STAGES[index + 1:])` —— **只发下游**。
    而 advisory 的正当去处**多数在上游**：`claim`→write、`presentation`→format、
    `diagram`→drawio（对 rubric 都是上游）；`constraint_model`→analysis（对 review 也是上游）。
    否则这个机制只有面板可见、从不落地：一条明写
    「会改变论文报出的不确定性」的建议就这么躺着，没有任何阶段会去执行它。

    回退**正是被指的那个阶段唯一会再跑一次的时机**，所以在这里补上：**从 `target` 到链尾**
    每个待重跑的阶段（上界若写成门禁 `sid`，format/verify/demo 排在门禁之后就会漏发），把它名下的建议接在自己的返修回执后面。
    """
    try:
        dec = _gate_decision(stage)
    except Exception:
        return 0
    lo = STAGE_IDX[target]          # 上界**不是** sid —— 见本函数上方注释：
    sent = 0
    for s in STAGES[lo:]:           # 门禁之后还会重跑的阶段（format/verify/demo）也要发到

        mine = [a for a in (dec.get("advisories") or [])
                if CONTENT_TARGETS.get(a.get("category"), "write") == s["id"]]
        # 去掉**已经投过**的那些：`run_all` 的 `by_target`
        #   在**决策那一刻**就往 `hints[dest]` 追加过同一批建议（它管"目标阶段排在门禁之后"
        #   的那些），而这里回退时又追加一遍 ⇒ 同一个 `hints[dest]` 里同一句话出现两次，
        #   agent 会当成两条要求逐条处置。判据用文本包含（`_adv_text` 带 id，够唯一）。
        _have = str(hints.get(s["id"], ""))
        mine = [a for a in mine if _adv_text(a) not in _have]
        if not mine:
            continue
        # 与 `run_all` 那条投递同款：**按 severity 分两段**（见 `_adv_is_must`）——
        #   一律写「按成本决定是否落实」的话，会把降级下来的 hard/must 项说成可选。
        musts = [a for a in mine if _adv_is_must(a)]
        opts = [a for a in mine if not _adv_is_must(a)]
        segs = []
        if musts:
            segs.append(f"前序门禁**必做**的延后项（{len(musts)} 条，必须落实）："
                        + "；".join(_adv_text(a) for a in musts))
        if opts:
            segs.append(f"前序门禁可选建议（{len(opts)} 条，可核查、按成本决定是否落实并说明）："
                        + "；".join(_adv_text(a) for a in opts))
        hints[s["id"]] = (str(hints.get(s["id"], "")) + "\n" + "\n".join(segs)).strip()
        sent += len(mine)
    if sent:
        log(f"  ↪ [{sid}] 的 {sent} 条延后建议已随回执交给回退路径上的阶段")
    return sent


def _has_actionable_feedback(decision):
    """这份裁决是不是一份**能给回退目标执行的**返修回执？

    为什么必须分：回退到某阶段时，驱动把失败门禁的裁决当「返修回执」投给回退目标
      （`_apply_decision` 的 rollback 分支）。但门禁**执行失败**时（没写出报告、裁决侧车
      格式错），它的裁决是 `UNVERIFIED`、`stage/target` 都是 None，issues 里只有一条
      「去补 `.verdict.json`」—— **那是门禁自己的产物**。把它投给 `analysis` 的后果：
      于是 analysis 跑去追 `reports/MODELING_REVIEW_REPORT.verdict.json`（4review 的东西），
      拿着一条与本阶段无关、也无法执行的指令干活，最后整段失败。
    """
    if not decision:
        return False
    if decision.get("reason") == "verdict_stale":
        # 过期裁决的 findings **可能**照样是有效回执：被审的正文没动过时，它们指的就是
        # 现在这份报告里真实存在的文字（变的只是做法要求/判据）。那种情况下对上游来说
        # 这就是一份普通返修回执，不能说成"门禁没跑完"。
        return bool(decision.get("stale_issues")) and not (
            (decision.get("stale_digest") or {}).get("artifacts_changed"))
    if not decision.get("issues"):
        return False
    return decision.get("reason") not in PROTOCOL_REASONS


def _save_feedback(stage):
    folder = LOG_DIR / "quality" / "feedback" / (state["run_id"] or "manual") / uuid.uuid4().hex[:8]
    folder.mkdir(parents=True, exist_ok=True)
    # 回退端点紧跟着就会把它记进 `state["hint_src"]`（见那里的注释）—— 交回那条路要用。
    state["_last_feedback_folder"] = str(folder.relative_to(ROOT))
    # Include machine-detected failures even if the model's report said PASS.
    decision = _gate_decision(stage)
    # 过期裁决投给回退目标时要**当成普通回执**写下去：上游读的是 `issues`，
    #   而过期裁决的 issues 是空的（findings 在 `stale_issues` 里、不参与路由）。
    #   被审正文没动过时那批 findings 就是真回执 —— 照原样转过去，别让上游拿到一份空壳。
    if decision.get("reason") == "verdict_stale" and _has_actionable_feedback(decision):
        decision = dict(decision, issues=decision["stale_issues"],
                        reason="content_repair_required")
    atomic_json(folder / "gate_decision.json", decision)
    for p in (REPORTS / stage["report"], HANDBACK):
        if p.is_file():
            shutil.copy2(p, folder / p.name)
    # 投递即出队：交回单拷进 feedback 目录之后，从 `reports/` 移除。
    #
    #   泄漏是真的会发生的：⑦ 写完交回单停下等决策；选了「只重做图」，
    #   那条动作**没有走 `_redo_from`** → 连带跳过了它的清理 → 交回单留在盘上 →
    #   链条从 ① 重走，走到 ③ 时 `check_handback` 看到它 —— `target: code`（下标 3）
    #   在 ③（下标 2）看来是**下游**，不构成「前序返修」→ 判无效 → **搬进 cache**。
    #   于是 ④ 真正开跑时清单已不在 `reports/`，而提示还让它去那儿读 —— **投递失败**。
    #
    #   `_redo_from` **也会**清它（它清的理由不同：黄灯要跟着灭）。所以这一句在
    #   正常回退路径上是**冗余**的（把那句拿掉测试照样绿）。
    #   留着它是因为**投递**才是语义上的"消息已送达"时刻：将来再有谁写出一条绕过
    #   `_redo_from` 的回退路径，交回单也不会再泄漏到下游去。
    hb = HANDBACK.is_file()
    if hb:
        HANDBACK.unlink(missing_ok=True)
    _record_quality(stage, "repair_requested", "保留返修证据", feedback=str(folder.relative_to(ROOT)))
    if _has_actionable_feedback(decision):
        return f"先读取 {folder} 中的返修回执，按具体问题修复并说明复验结果。保留正确内容。"
    # 交回那条路：被交回的阶段**不是门禁** ⇒ 它自己的"裁决"是空壳
    #   （`_gate_decision` 返回 `not_gate` / issues 为空）⇒ `_has_actionable_feedback` 必然
    #   False ⇒ 会落进下面那条「没有跑完…仅供排查…与本阶段无关」的模板，而那份交回单
    #   **正是**本轮要执行的返修单 —— **提示词是反的**。全靠 ④ 自己没听（它照样去读了
    #   交回单）才没出事。这里必须把它说正。
    if hb:
        return (f"下游「{stage.get('name') or stage['id']}」上一轮按 SKILL **交回上游**："
                f"它修不了的那批问题在 {folder}（`HANDBACK_REQUEST.md` 就是清单，"
                f"同目录还有它自己的报告）。**那份清单就是本轮要执行的返修单**，"
                f"逐条执行并说明复验结果；清单之外的正确产物直接复用，别顺手重写。")
    # 门禁没跑完 → 如实说清，别把「它自己缺产物」伪装成「你错了」。
    return (f"⚠️ 上游门禁「{stage['id']}」这次**没有跑完**（它自己的产物缺失或裁决未生成），"
            f"不是它判你不合格。它的原始输出留在 {folder}，**仅供排查**，"
            f"里面那条修法是针对门禁自己产物的，与本阶段无关。"
            "你按本阶段 SKILL 的自检清单重做并交齐产物即可，不要去补别的阶段的产物。")


def _write_revision_diff(sid, before_path):
    """返修跑完后，把「改前 / 改后」两版报告 diff 成一页，落到 reports/_REVISION_DIFF.md。

    为什么要有它：返修最典型的坏法不是"没改对"，而是**改 A 时顺手弄坏了本来正确的 B**
    （已独立验证正确的 4.14×10⁻³ 曾在返修中被改错）。评审回执里虽然写了
    「可放行部分／保留，勿重写」，但那是散文——下一轮评审得重读整份报告才可能发现越界改动，
    极容易漏。这里把两版逐行对比**落成一页**，门禁和人工都能直接看到「清单外的改动」在哪，
    也正好配合 `_references/math_modeling_norms.md` 的「返修只动清单内」纪律（agent 自证 + 驱动留证）。
    """
    stage = next((s for s in STAGES if s["id"] == sid), None)
    if stage is None or str(stage["report"]).startswith("paper"):
        return
    rep = stage["report"]
    cur, before = REPORTS / rep, Path(before_path)
    if not (cur.is_file() and before.is_file()):
        return
    import difflib
    a = before.read_text(encoding="utf-8", errors="replace").splitlines()
    b = cur.read_text(encoding="utf-8", errors="replace").splitlines()
    diff = list(difflib.unified_diff(a, b, fromfile=rep + "（返修前）",
                                     tofile=rep + "（返修后）", lineterm="", n=2))
    added = sum(1 for x in diff if x.startswith("+") and not x.startswith("+++"))
    removed = sum(1 for x in diff if x.startswith("-") and not x.startswith("---"))
    head = [
        "# 返修改动对照（" + sid + "）", "",
        "- 改动：**+" + str(added) + " / -" + str(removed) + " 行**（原报告 " + str(len(a)) + " 行）",
        "- **逐行确认每一处改动都能对应到上一轮回执的某一条**；出现回执清单**之外**的改动，",
        "  就是「修 A 坏 B」的候选，必须回退或在本轮说明理由。",
        "- 上一轮回执（含「可放行部分／保留，勿重写」清单）见 runtime/quality/feedback/ 下对应目录。",
        "", "```diff",
    ]
    (REPORTS / "_REVISION_DIFF.md").write_text(
        chr(10).join(head + diff + ["```", ""]), encoding="utf-8")
    log(f"{sid}: 已生成返修改动对照 reports/_REVISION_DIFF.md（+{added}/-{removed} 行）")


_FILE_IN_TEXT_RE = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_./-]*\.(?:md|tex|py|json|xlsx|csv)")
# 判词里对被审文字的**引用形态**：直角引号、行内代码、加粗。三种都当"原句"候选。
_QUOTED_RE = re.compile(r"[「『]([^」』\n]{6,160})[」』]|`([^`\n]{6,160})`|\*\*([^*\n]{6,160})\*\*")


def _locate_targets(*texts, limit=4):
    """从判词文本里**定位要改哪儿**：候选文件 → 在其中搜引用的原句 → 给出 文件:行。

    为什么要它：黄灯上原本只有「我已手工修好」一个按钮，
      而判词说的是「§8 第 5 条的 Δr 分句」「§5.6 的 (v) 行」这类**章节坐标** ——
      人拿到手得去 1700+ 行的报告里自己找。所以把位置机械地算出来。

    判词通常**同时含两样东西**：文件路径（`reports/RESULTS_REPORT.md`）与
    **引用的原句**（「Δr 口径（网格，V10）」）。拿后者在前者里搜，命中即给行号 ——
    这是纯文本检索，不猜语义，找不到就老实返回空（前端会显示「未定位到，请手工检索」）。
    """
    text = "\n".join(str(t or "") for t in texts)
    files = []
    for m in _FILE_IN_TEXT_RE.finditer(text):
        cand = m.group(0).lstrip("./")
        if cand not in files and (ROOT / cand).is_file():
            files.append(cand)
        if len(files) >= limit:
            break
    quoted = []
    for m in _QUOTED_RE.finditer(text):
        s = (m.group(1) or m.group(2) or m.group(3) or "").strip()
        s = re.sub(r"\*+", "", s)                    # 去掉加粗星号再搜
        if len(s) >= 6 and s not in quoted and not s.endswith((".md", ".py", ".json")):
            quoted.append(s)
    out = []
    for rel in files:
        try:
            lines = (ROOT / rel).read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        # 取**最具体**的那处命中，不是第一处：判词里既有
        #   「**Δr 口径**（网格，V10）」（长、全文只此一处）也有「**不动任何数值**」
        #   （短、通用、文件前部就命中）—— 取第一个会把位置指到无关的行上去。
        #   判据取「引文最长者胜」（越长越具体），并列时取靠前的行。
        # 判词常要求改**多处**（例如写着「两处定点文字修改」）→ 每个文件报最多 4 处。
        # 滤掉短引文：`不动任何数值` 这类只有 6 个字的通用短语会命中文件随便一处，
        # 而真正要改的那句（`**Δr 口径**（网格，V10）`、`比 3analysis §17.2 …`）都长得多。
        # 匹配前两边都要归一化：判词引的常是**加粗**或**行内代码**里的原句
        #   （`**Δr 口径**（网格，V10）`、`` `t_dry` ``…），而报告里那行**带着标记**。
        #   只去引文一侧的标记 = 粗体引文永远匹配不上（⑤ 那条判词引的正是带 `**` 的
        #   句子，只归一化一侧就会一处都定位不到）。展示的上下文仍用**原文**，不动它。
        norm = lambda s: re.sub(r"[*`]", "", s)          # noqa: E731
        hits = []
        for q in quoted[:24]:
            if len(q) < 12:
                continue
            nq = norm(q)
            at = next((i for i, ln in enumerate(lines, 1) if nq in norm(ln)), None)
            if at is not None:
                hits.append((len(q), at, q))
        # 引文越长越具体 → 排前面；**并列时取靠前的行**（`reverse=True` 会把行号也倒过来，
        # 否则会指到后一处 —— 同一个引文在报告里出现两次时，先出现的那处才是
        # 判词在说的那处）。
        hits.sort(key=lambda x: (-x[0], x[1]))
        seen_lines = set()
        for _, hit, q in hits:
            if hit in seen_lines:
                continue
            seen_lines.add(hit)
            # 连**上下文一起给**：只给行号，人还得自己去第 971 行数 —— 与"找不到位置"没差。
            lo, hi = max(1, hit - 3), min(len(lines), hit + 3)
            out.append({"file": rel, "line": hit, "snippet": lines[hit - 1].strip()[:110],
                        "matched": q[:60],
                        "context": [{"n": i, "text": lines[i - 1][:150], "hit": i == hit}
                                    for i in range(lo, hi + 1)]})
            if len(out) >= limit:
                break
        if len(out) >= limit:
            break
    return out


def _protocol_repair(decision, report_path):
    """只在"报告本体已写好、只是没给出合法 v2 侧车"时允许只补侧车。

    其它协议失败（引文不实、必查项缺失、issue 结构错、md/json 冲突、身份/摘要不符）一律整段重审——
    宁可多花时间，也不让"只补一张格式合法的侧车"把上一轮的错误结论洗成通过。
    """
    if str(decision.get("reason") or "") != "verdict_malformed":
        return False
    evidence = " ".join(str(i.get("evidence") or "") for i in (decision.get("issues") or [])
                        if isinstance(i, dict))
    return "需要 version 2 结构化裁决" in evidence and Path(report_path).is_file()


def _verdict_repair_hint(decision):
    issues = decision.get("issues") or []
    detail = str(issues[0].get("evidence") or "")[:300] if issues and isinstance(issues[0], dict) else ""
    return ("报告本体已写好，只是缺少合法的 v2 裁决侧车：**只补写 reports/<REPORT>.verdict.json**"
            "（schema_version=2 + stage + input_digest 原样 + status + issues + checks），"
            "不要改动报告本体、不要重做审查。问题：" + (detail or str(decision.get("reason") or "")))


def _adv_is_must(adv):
    """这条**延后建议**是不是必做的？

    必须有这个判据：`_rubric_route` 会把「目标阶段排在门禁
      **之后**」的**硬项**降级进 `advisories` —— 它们此刻确实修不了（那个阶段还没跑），
      放行并留痕是对的。但这样一来 `advisories` 里就**混着两种完全不同的东西**：
        · `tier: optional` 的真·可选项；
        · `severity: hard` / `tier: must` 的**必做项**。
      ⑫ 那一轮的实际情形：13 条里有 **RB-6、RB-19 两条是 hard+must** ——
      「figures/fig_roadmap.content.json 里那 10 处含内部词的图内文字」（内部词泄漏进图，
      评委直接看得见）与「交付 PDF 在标题层认不出稳健性检验模块」（官方四大项之一）。
      而投递文案统一写着「可选建议、按成本决定是否落实」⇒ 把两条红线级要求说成了可以不做。
      降级时 `tier`/`severity` 被原样保留（`dict(i, deferred=True)`）⇒ 这里判得出来。
    """
    if str(adv.get("tier") or "").strip().lower() in {"must", "hard", "fatal", "blocker"}:
        return True
    return str(adv.get("severity") or "").strip().lower() in {"hard", "fatal"}


def _adv_text(adv):
    """一条建议摊成一行提示文本（带 id，便于下游与报告对账）。"""
    body = str(adv.get("fix") or adv.get("evidence") or adv.get("id") or "")
    aid = str(adv.get("id") or "").strip()
    return (f"[{aid}] {body}" if aid else body)


def _rubric_recheck_hint(sid="rubric"):
    """⑫ 的**复评轮**提示：只复核上一轮判词的落实情况，不必重打整份评分标。

    为什么要有增量复评：⑫ 之前判过一次，⑬ 修完再回 ⑫ 重判本该快很多 ——
      （担心的是"判完交给 ⑬ 就删了"）。
      · **没删** —— ⑫ 上一次的回执、裁决、以及 `state["fix_required"]`（上一轮点名要 ⑬ 处置的
        判词 id）全都还在，不存在"判完就删、逼人重判"这回事。
      · 但**驱动做不到增量**：`_back_to_judge` 把 index 指回 ⑫ 后，⑫ 的输入指纹
        因为 `paper/` 被 ⑬ 动过而失配 ⇒ `run_stage` 照旧**从零重打整份评分标**。
      · 而 ⑬ 的 SKILL 明写「只动清单内」⇒ 变更面是**已知且很小**的，增量复核在语义上成立。
      两条护栏，防止它拿"这是复评"当放水的借口：① 结论仍须是**完整**的 status 与逐项打分
        口径；② 若发现清单外的新问题（含越界改动引入的）**照旧报**，该 FAIL 就 FAIL。
    """
    ids = [str(x) for x in (state.get("fix_required") or []) if str(x).strip()]
    tail = (("上一轮点名要 ⑬ 处置的是：" + "、".join(ids) + "（判词原文在上一版裁决里）。")
            if ids else
            "上一轮未记录具体判词 id —— 直接读上一版裁决，逐条复核它点名的那些项。")
    # 增量到什么程度，**按门禁分档**：
    #   ⑮ 判出来后交给 ⑬ 处理，⑬ 处理完交回 ⑮，然后 ⑮ **不重新全部审核、只审查改过的**，
    #   不然太浪费时间 —— ⑮ 一条实测 **89 分钟**，全量重跑一遍纯属浪费。
    n = int((state.get("fix_rounds") or {}).get(sid, 0))
    if sid == "verify":
        head = (f"【这是第 {n} 轮**复评**，不是首评 —— 只审改动波及的范围】"
                "上一轮你已判过并交 ⑬ 定点改写，本轮**不必重跑全部检查项**。")
        # ⑮ 独有的「不许省」：它判的是**成品 PDF**，而 ⑬ 改的是 `.tex` ——
        # 少了重编译，它审的就是一份与正文不符的旧 PDF（那是它存在的主要理由）。
        scope = ("**仍必须做的三件（不能省）**：① 重新编译（`Step 7`，两遍 xelatex）——"
                 "⑬ 改的是 `.tex`，不重编译就是在审一份旧 PDF；② 核页数/版心（`publication check`）；"
                 "③ 只对**改动落到的那几页**重跑逐页视觉（其余页沿用上一轮已签的结论，"
                 "在报告里写明哪些页是复用的）。")
        guard = ("⚠️ 三条不许省的：结论仍须是**完整**的 status；发现新问题（含越界改动引入的）"
                 "**照旧报**，该 FAIL 就 FAIL；**编译与计页不是可选项** —— 复评不是放行通道。")
    else:
        head = (f"【这是第 {n} 轮**复评**，不是首评 —— 走增量】上一轮你已判过并交 ⑬ 按判词定点改写，"
                "本轮**不必重打整份评分标**。")
        scope = ""
        guard = ("⚠️ 两条不许省的：结论仍须是**完整**的 status 与逐项打分；发现新问题"
                 "（含越界改动引入的）**照旧报**，该 FAIL 就 FAIL —— 复评不是放行通道。")
    return (head + tail
            + "再对照 `reports/_REVISION_DIFF.md`（驱动自动生成的改动前后一页对照）确认："
              "① 点名的那几项是否真的落实；② 有没有**清单外**的越界改动"
              "（动了清单外的东西 = 修 A 坏 B，要单独指出）。"
            + scope + guard)


def _looks_like_a_skeleton(stage):
    """盘上那份**确证**是门禁按 §6.1 先落的骨架吗？

    确证的判据 = 裁决侧车在盘上、且 `status` 是 `UNVERIFIED`（骨架的固定特征）——
    门禁的骨架**必须**同时写报告与侧车，所以这一条抓得住它。

    侧车**不在**时返回 False（="不知道"）—— 这一侧是**保守**的那一侧：宁可留着盘上
      那份可能的新产物，也不要拿旧版把它盖掉（"agent 写完报告、还没写侧车就被杀"是真实存在的
      时序；把新的换回旧的，比留着骨架更糟）。
    与之相对，`run_stage` 里判"本轮有没有产出可接受的东西"用的是它**取反** ——
      那里"不知道"要按"没产出"处理（保守方向相反，因为那边的问题是"要不要把旧的搬回来"）。
    """
    if not stage.get("gate"):
        return False
    path = REPORTS / str(Path(stage["report"]).with_suffix(".verdict.json"))
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, ValueError):
        return False
    return str(data.get("status") or "").strip().upper() == "UNVERIFIED"


def _open_demo_page():
    """整链跑完时，把 ⑯ 产出的 `demo/demo.html` 用**系统默认浏览器**打开。

    契约：链条跑到末尾 ⑯ 结束时，自动打开它创建的 demo 页面。

    为什么由**驱动**开、而不是前端 `window.open`：链尾那一下**没有用户手势**，浏览器会把
      没有手势的 `window.open` 直接拦掉（GitHub 标识那处的口径不同 —— 那里选的
      是"前端试、拦了就明说"，因为标识本来就要能单独点）。驱动走 `webbrowser` 调系统默认
      浏览器，不受这条限制。
    **静默失败**：没装浏览器、无 GUI、文件不存在、`webbrowser` 自己抛异常 —— 一律只是"没开成"，
      返回值说明结果，**绝不让交付收尾挂掉**（`run_all` 里这行在 `run_completed` 之后，
      真抛出去会把它变成驱动级 halt）。
    不想被弹窗打扰：设环境变量 `NEWMATHAGENT_NO_OPEN=1` 整条关掉。
    """
    if os.environ.get("NEWMATHAGENT_NO_OPEN"):
        return False
    demo = ROOT / "demo" / "demo.html"
    if not demo.is_file():
        return False
    try:
        # `as_uri()` 给出 `file:///…`（反斜杠会转成正斜杠）—— demo 是离线单文件，
        # 双击即用，所以 file:// 打开与交付件的行为一致，不需要驱动再挂一条路由。
        return bool(webbrowser.open(demo.resolve().as_uri()))
    except Exception:
        return False


def _maybe_collect_outputs(stage):
    """⑨ 论文撰写 / ⑭ 排版与版式 一跑完，就先把**已就绪的提交件**收一批。

    契约：⑨ 结束、进 ⑩ 的时候，就把需要提交的移入 `产物/提交作品/最新作品`；
      先移已经做好的，剩下的做好一个移一个。
      只在**整链收口**时收一次的话，链一旦中途停下（停在 ⑮ 黄灯上就会），那个文件夹
      一片空白，尽管正文 PDF / 附录 / result*.xlsx 早就做好了 —— 翻它的人看到的是"白干了一天"。

    **覆盖 ⑨ 及之后的每一个阶段**（不是"只在 ⑨/⑭ 收两次"）：
      契约：⑨ 结束后先把它目前能移入的移入，还没移入的**等它们的阶段完成再移入**；
      后续阶段的产物若改动了，就**移入后把之前的产物替代**。
      于是口径是**每完成一个阶段就同步一次**：
      新产出的项补进去、改动过的项由 `package()` 的原子整体替换换成新版。
      （只挂 ⑨/⑭ 两个点是个诱人的错：理由是 `package()` 会重建 `其余文件/`（`reports/`+`code/`），
      而这个量级在本地盘上是**秒级**、不是小时级 —— "太贵"判断错了。）

    失败不上抛：展示区不是交付件，它的失败不该让小时级的链停下。
    （这句里**刻意不写那个镜像函数的名字** —— `regression/test_workflow.py` 有一条
    源码级钉子，按 `async def run_stage` → `async def run_all` 切片判"镜像不许挂进
    run_stage 内部"，本函数正好落在那段切片里，写上名字会让那条钉子误报。）
    """
    if STAGE_IDX[stage["id"]] < STAGE_IDX["write"] or state["stopping"]:
        return
    try:
        # **必须 `final=False`**：缺省 `final=True` 走严格分支，
        #   而 ⑭ 写的清单声明了要等 ⑯ 才产出的 `demo.html` ⇒ `package()` 抛「找不到」
        #   ⇒ 被这里吞成一行日志 ⇒ **从 ⑭ 起每一次同步都失败**、`提交作品/最新作品/` 再也
        #   不更新（"每阶段把已做好的移入"等于没生效）。只有 ⑨~⑬ 那几次因为清单还没写
        #   出来、走 provisional 分支才碰巧成功。
        _collect_outputs(final=False)
    except Exception as exc:                        # noqa: BLE001
        log(f"⚠️ {stage['id']}: 阶段性打包跳过（不影响本阶段结果）：{exc}")


def _intake_passed_without_receipt():
    """⓪ 读题**走过人工确认那条路**时算不算"过" —— 纯盘面判据，不看回执。

    为什么 ⓪ 需要一条**自己的**判据：它的"通过"是**人工确认**，而 `_do_intake_confirm`
      （`/api/decision` 的 confirm 分支）只做三件事 —— 把题面/附件落盘
      （`_materialize_inbox`）、记一条 confirmation、然后从 ① 起跑；**它从来不写 ⓪ 的回执**，
      也不设 `state["stages"]["intake"]`。所以 `runtime/quality/stages.json` 里会有
      literature/analysis/review/code/audit/robustness/drawio/figreview 的条目，
      drawio/figreview 的条目，**唯独没有 `intake`**。
      ⇒ `_backfill_before` 那套"产物在盘 + 回执对得上"的复用判据对 ⓪ **永远不成立**，
        于是用户在确认页点完确认、链从 ① 起跑之后，⓪ 就被画成灰色（面板上明明显示着耗时 7m47s）。

    判据三条**同时**成立才算过，少一条留灰（宁可留灰也不撒谎）：
      · `reports/INTAKE_REPORT.md` 在盘上且非空 —— 与 `_artifact_ok` 同一把尺；
      · `request/problem.md` 在盘上 —— 那是 `_materialize_inbox` **无条件**写下的题面，
        它存在就说明确认这一步真的落地了（不是"AI 读完了但没人确认"）；
      · `_intake_unconfirmed()` 为假 —— inbox 已清空（或本来就空）⇒ 没有等着人确认的原件。
    """
    stage = next((s for s in STAGES if s["id"] == "intake"), None)
    if stage is None or not _artifact_ok(stage):
        return False
    if not (ROOT / "request" / "problem.md").is_file():
        return False
    return not _intake_unconfirmed()


def _backfill_before(index):
    """「从所选阶段起跑」时，把 index **之前**的阶段按盘面如实标上（**不调 agent**）。

    为什么需要：起点改成可选之后，上游那些阶段
    `run_all` 这一轮**根本不会走到**，`for sid in state["stages"]: idle` 刚把它们全刷成
    idle ⇒ 面板会把「上一轮已经做完、回执也齐」的 ①–⑧ 画成灰色，看着像"白跑了"。

    判据与 `run_stage` 的复用近路**同一套**（产物在盘上 + 回执的事实半份/产物半份都对得上），
    对不上的**留 idle 并记一行日志** —— 如实说"这一段这次没跑、且它并不满足复用条件"，
    绝不画成绿的（那才是真正的谎）。

    这里**不做展示区镜像**：`code/` 实测 108M，为一次"跳过"再走一遍整棵产物树不值当，
    而那些阶段的快照本来就是上一轮留下的、与盘面一致。
    （写这句时**刻意不写那个函数名** —— `regression/test_workflow.py` 有一条源码级钉子，
    按 `async def run_stage` → `async def run_all` 切片判"镜像不许挂进 run_stage 内部"，
    本函数正好落在那段切片里，写上函数名会让那条钉子误报。）
    """
    store = _receipt_store()
    for s in STAGES[:index]:
        sid = s["id"]
        try:
            art, _ins = _input_split(s)
            out = _output_digest(s)
        except Exception as exc:                       # noqa: BLE001 —— 判据算不出就如实留灰
            log(f"⚠️ [{sid}] 复用判定算不出来（{exc}）→ 状态留 idle")
            continue
        rec = store.records.get(sid) or {}
        reused = _artifact_ok(s) and rec.get("artifacts") == art and rec.get("outputs") == out
        # ⓪ 是唯一一个「通过」不写回执的阶段（人工确认那条路，见
        #   `_intake_passed_without_receipt` 的说明）—— 不补这一条，它一被确认就画成灰色。
        if sid == "intake" and not reused:
            reused = _intake_passed_without_receipt()
        if reused:
            # 判据只看**事实半份**（与 `run_stage` 的复用近路同口径），所以「只有做法要求
            #   变过」的阶段在这里也会算"复用" —— 但那不该被画成干净通过：`_restore_stale_instr`
            #   启动时刚把它标成 `done(stale-instr)`（「按旧要求交付」的唯一可见痕迹），
            #   回填若写成 `done(skip)` 就把这条信息抹了。两个信息都给：状态带 stale 标记。
            _stale = sid in (state.get("stale_instr") or ())
            state["stages"][sid] = ("done(manual)" if store.is_manual(sid)
                                    else ("done(stale-instr)" if _stale else "done(skip)"))
        else:
            log(f"⚠️ [{sid}] 不满足复用条件（产物或回执对不上）—— 本轮从「"
                f"{STAGES[index]['name'] if index < len(STAGES) else '链尾'}」起跑、"
                f"没走它，状态如实留 idle。要它跑就把起点选到它或更早。")
    state["progress"]["done"] = sum(1 for s in STAGES
                                    if str(state["stages"][s["id"]]).startswith("done"))


async def run_all():
    state["run_id"] = uuid.uuid4().hex[:8]
    state["stopping"] = False
    # pause_to_halt 是**一次性信号**：上一轮暂停过、这一轮是重新起的，
    # 不清掉的话这轮会因为一个陈旧信号在收尾时莫名转黄灯。
    # （与 force_retry / resume_action 同一范式。）
    state["pause_to_halt"] = False
    state["halt_gate"] = False
    state["halt_reason"] = ""
    if state.get("run_completed"):
        for value in state["stage_t"].values():
            value.update(elapsed=0.0, start=None)
        state["elapsed_base"] = 0.0
    state["run_completed"] = False
    state["running"] = True
    for sid in state["stages"]:
        state["stages"][sid] = "idle"
    state["rounds"] = {}
    # 这轮会重新推导：每个阶段跑过 run_stage 时若仍"只有指令变了"会重新加回来。
    # 但**只清起点及之后**的：起点之前的阶段这一轮
    #   **根本走不到**，run_stage 不会把它们的标记重新加回来；而 `_backfill_before`
    #   正是读这一份集合来如实保留「按旧要求交付」的标记。整份清掉 ⇒ 那些阶段被画成
    #   干净的 ✅ 复用、面板蓝条上一整排 chip 当场消失 —— 正是上面那句注释要避免的
    #   "静默放行"（8 个阶段由 `done(stale-instr)` 变 `done(skip)`，蓝条 15 项掉到 7 项）。
    _start_i = int(state.get("start_index") or 0)
    state["stale_instr"] = {s for s in (state.get("stale_instr") or ())
                            if s in STAGE_IDX and STAGE_IDX[s] < _start_i}
    state["fix_rounds"] = {}            # 各门禁↔⑬ 自动来回修的轮数（见 RUBRIC_FIX_MAX_ROUNDS）
    # ⑬ 的交接单：哪一关把「论文侧定点改写」交给了它。取值见 `_FIX_HANDOFF_JUDGES`。
    state["fix_loop_return"] = ""
    # 只被 ⑭ 版式改过、因此免于重判的内容判官（见 _layout_superseded）
    state["layout_superseded"] = set()
    # 清掉可能泄漏下来的两个「一次性信号」：`force_retry` 只被 `_call` 的看门狗**循环体内**
    #   消费，若子进程赶在下一次采样（STALL_SAMPLE=5s）前自己成功结束，循环直接从条件处退出，
    #   标志就留下了 —— 之后任何一次重跑该阶段都会在 5 秒内被误杀。`resume_action` 同理，
    #   会被**下一个**失败阶段 pop 走，把指名道姓属于别的阶段的 hint 塞进它的 prompt。
    #   （泄漏由代码结构决定；危害是时序相关的，所以这是防漏而非已复现的缺陷。）
    state["force_retry"] = None
    state["resume_action"] = None
    state["progress"] = {"done": 0, "total": len(STAGES)}
    state["run_start"] = time.time()
    # 绝不清 state["retry_cap"]：用户点「延长本次限时」是先写它、再让链继续，
    #   在这里清掉等于把用户的延长静默吃掉。清空只发生在 /api/start。
    hints = dict(state.get("seed_hints") or {})     # 决策续跑时注入的提示（一次性）
    state["seed_hints"] = {}
    # 起点：`/api/start` 的 `from_stage` 落在这里（一次性 —— 读走就归零，
    #   免得下一次点「开始全链」还被上一轮的起点带走）。缺省 0 = 从 ① 走、靠回执逐级复用。
    index = int(state.get("start_index") or 0)
    state["start_index"] = 0
    if index:
        # 起点**可以等于 `len(STAGES)`**（"链尾"）：⑯ 被「接受并披露」时
        #   `_set_start_index(STAGE_IDX['demo'] + 1)` = 16，语义是"直接去收交付"。
        #   直接写 `STAGES[index]['name']` ⇒ IndexError，而这一行在下面的
        #   `try:` **之外** ⇒ 异常逃出线程、`finally` 不执行 ⇒ `state["running"]` 永远停在
        #   True ⇒ 之后点「开始全链」回「已在运行」、任何决策 409、链尾收交付也走不到，
        #   只能重启驱动（而黄灯已被 `_set_start_index` 清掉，看着像"点了没反应"）。
        #   两处一起管：取值兜住链尾 + 整块进 try（任何起跑期异常都转黄灯，不再死线程）。
        pass
    if index:
        # 这一块**必须自带兜底**：它在下面那个大 `try:` 之外，
        #   异常一旦逃出去，`finally`（唯一把 `state["running"]` 置回 False 的地方）就不会执行
        #   ⇒ 链死了但面板说"在运行" ⇒ 点「开始全链」回「已在运行」、决策回 409、只能重启驱动。
        try:
            log(f"▶️ 本次从「{STAGES[index]['name'] if index < len(STAGES) else '链尾'}」起跑"
                f"（上游不跑、按盘面如实回填状态）。")
            _backfill_before(index)
        except Exception as exc:                        # noqa: BLE001
            _halt(STAGES[min(index, len(STAGES) - 1)], _driver_exc_text(exc), "failed", kind="driver")
            state["running"] = False
            state["cur"] = None
            emit("state", state2dict())
            return
    normal_end = False
    log(f"开始全链 run_id={state['run_id']}")
    # 本链的**栅栏令牌**。`state["run_id"]` 是全局的，谁后起谁覆盖它；于是「旧链还活着、
    #   新链已起」时，旧链会**毫无察觉地继续跑**，两条链同时写产物与回执（起过一次：
    #   新链起了之后，旧链的 ④ 编码计算 才跑完并写下回执，随后被新链的写者用旧快照盖掉
    #   —— 下一次重启时 ④ 被当成「没跑过」而整段重来）。
    #   旧链在阶段边界发现令牌变了就收手：产物与回执只留新链那一份。
    my_run = state["run_id"]
    try:
        try:
            _prepare_workspace()
        except RotationBlocked as exc:
            # 换题归档没做成 ⇒ **本轮根本没开始**：工作区原件一件未动、已改的指针名已回滚。
            #   转黄灯让用户处理（多半是归档目录被别的程序占着），别硬着头皮往下跑 ——
            #   那样新题会继承旧题的工作区产物，正是 `_prepare_workspace` 要防的那件事。
            # 挂到 ① 文献定向 上，不是 `STAGES[0]`（插了 ⓪ 读题之后，
            #   `STAGES[0]` 已经变成"读题"了 —— 会让这条归档失败挂成"读题阶段没归档"，
            #   指错方向）。
            _halt(STAGES[STAGE_IDX["literature"]],
                  f"换题归档未完成，本轮未开始（工作区原件一件未动）：{exc}",
                  "blocked", kind="failure")
            return

        # 已确认的读题产物**每一轮都要在盘上**。
        #   病因链：确认那一步（换题轮转）会把 `reports/` 整份搬进 cache ⇒ `reports/INTAKE_REPORT.md`
        #   在**从 ① 起跑的那一轮**里是**缺席**的，而 `_input_paths` 把前序阶段的报告全收进
        #   `art`（intake 也是前序）⇒ ①–⑯ 的回执记下的是"这个文件不存在"。
        #   下一轮点「开始全链」：`run_stage` 的 intake 短路恢复那份报告 ⇒ 文件**从无到有** ⇒
        #   ①–⑯ 的输入指纹**全变** ⇒ 整链真重跑一遍（15 个阶段，含小时级的 ④⑥）。
        #   ⇒ 恢复必须挪到"每轮都走"的位置：轮转之后、任何阶段之前。
        #   （不去改 `_REPORT_INPUT_EXCLUDE` 把读题报告排除掉：那等于让 16 个阶段对"读题结论
        #     被改过"永远失敏，代价更大。）
        if (_intake_confirmed() or {}).get("digest") == _source_digest():
            _restore_intake_artifacts()

        def _back_to_judge(ret_sid):
            """⑬ 处理完这一轮 ⇒ **回到把它交下来的那一关复评**。返回 True = 已指回 `index`。

            口径：⑫ 没过就亮黄灯，等 ⑬ 处理后再返回 ⑫；
            ⑮ 判完给 ⑬ 改，正如 ⑫ 判完给 ⑬ 改一样，⑬ 改完后直接跳回 ⑮。
            ⇒ 同一个机制服务两个门禁，`ret_sid` 就是"改完回哪一关"。

            两个闸：
              ① **那一关得真会重判**（`_review_object_stale`）—— ⑬ 若只写了 `FIX_REPORT.md` 而
                 没动 `paper/`，它的审查对象一字未变、裁决不可能变，回去只是空转（
                 3 轮里只有第 1 轮真叫过 ⑬，却对外宣称修了 3 轮）。不动稿就不回。
              ② **限量** `RUBRIC_FIX_MAX_ROUNDS`（按门禁分别计数）—— 到顶不再回，让那一关
                 自己转黄灯问人。
            """
            nonlocal index
            j = next((s for s in STAGES if s["id"] == ret_sid), None)
            if j is None:
                return "forward"
            # **轮数先记，再判"有没有动稿"** —— 反过来会无界空转：
            #   ⑬ 若按 SKILL「判词不属实就不动稿」，先判后记的话 `fix_rounds` 永远不涨
            #   ⇒ 上限 `RUBRIC_FIX_MAX_ROUNDS` 永不命中 ⇒ 控制流 `index += 1` 从 ⑬ 往前走、
            #   经 ⑭ 又撞回 ⑮ ⇒ ⑮ 读到的还是那份 claim 裁决 ⇒ 再交接 ⑬ …… **无限循环**
            #   （run_stage 被调 61 次仍在 fix→format→verify 打转、run_completed 永远 False；
            #    ⑬ 回执仍新鲜时更省 —— **agent 调用 0 次**，链既不前进也不亮黄灯，只能手点 ⏹）。
            #   代价：不动稿的轮次也占额度 ⇒ 最坏空转 3 轮就转黄灯，可接受。
            rounds = int((state.get("fix_rounds") or {}).get(ret_sid, 0))
            if rounds >= RUBRIC_FIX_MAX_ROUNDS:
                # 到顶**转黄灯**，不是静默往前走（口径是「先最多 3 轮…还不过就转黄灯问人」）。
                #   只 `return False` 的话 ⇒ 调用方 `index += 1`
                #   一路往下、链报成功，而那一关的判词**一次都没被处置**。
                log(f"{j['name']} 已自动来回修 {rounds} 轮（上限 {RUBRIC_FIX_MAX_ROUNDS}）"
                    f"仍未过 ⇒ 转黄灯交人决定（可回退、可披露，也可再点「再试一次」再加一轮）")
                _halt(j, f"{j['name']} 的返修环路已到上限（{RUBRIC_FIX_MAX_ROUNDS} 轮）仍未通过"
                         f"—— 判词没被处置完，交人决定", "blocked", kind="failure")
                return "halt"
            state.setdefault("fix_rounds", {})[ret_sid] = rounds + 1
            if not _review_object_stale(j):
                # 两种原因**必须分开说**：
                #   一律报"没有改动"是错的，实际有两种情形 ——
                #   ① ⑬ 真没动稿；② ⑬ 动了稿，但**按内容判官豁免口径**不算数
                #      （`_layout_superseded`：此后只有打磨者动过论文 ⇒ 裁决仍有效）。
                #   据那句错日志误判过一整轮「13 怎么没改啊」，所以这里如实区分。
                if _layout_superseded(j):
                    # 名单从 `_polisher_owners` 现取 —— 别在这里再写一份（
                    #   硬编码名单的话，`cross` 一收窄它当场就说错）。
                    _who = " / ".join({"format": "⑭ 排版与版式",
                                       "fix": "⑬ 按判词返修"}[o] for o in _polisher_owners(j["id"]))
                    log(f"13 改过 {j['name']} 的审查对象，但按**内容判官豁免**口径"
                        f"（此后只有{_who}打磨过论文）⇒ 它的裁决仍有效，不复评，越过它继续往下。")
                else:
                    # ⑬ 没动稿（判词不属实 / 判它 not_reproduced）⇒ 那一关的裁决不会变，回评是空转。
                    # **这一轮也占额度**（见上），所以不会无限来回；这里按"越过它继续往下"处理，
                    # 由调用方把 index 指到 `ret_sid + 1` —— 从 ⑬ 直接 `index += 1` 只会撞回 ⑮。
                    log(f"13 这一轮没有改动 {j['name']} 的审查对象（paper/ 的正文）⇒ "
                        f"它的裁决不会变，不复评，越过它继续往下（这一轮已计入上限）。")
                return "forward"
            index = STAGE_IDX[ret_sid]
            log(f"13 处理完成 ⇒ 回 {j['name']} 复评（第 {rounds + 1} / {RUBRIC_FIX_MAX_ROUNDS} 轮）")
            return "back"

        while index < len(STAGES) and not state["stopping"]:
            if state["run_id"] != my_run:
                log(f"⚠️ 本链（run_id={my_run}）已被 run_id={state['run_id']} 取代，"
                    f"停止后续阶段 —— 免得两条链同时写产物与回执。")
                return
            stage = STAGES[index]
            round_hint = hints.pop(stage["id"], "")
            # ⑫ 的**复评轮**走增量（⑬ 修完再回 ⑫ 重判本该快很多，因为 ⑫ 之前判过一次），
            #   而驱动做不到：
            #   `_back_to_judge` 把 index 指回 ⑫ 后，⑫ 的输入指纹因为 `paper/` 被 ⑬ 改过而失配
            #   ⇒ 照旧**从零重打整份评分标**（全维度重读全篇）。
            #   但**没有任何东西被删**：⑫ 上一次的回执与裁决都还在盘上
            #   （`state["fix_required"]` 还专门存了上一轮点名要 ⑬ 处置的判词 id）。
            #   ⇒ 这一轮完全有条件只做增量：逐条复核那几项 + 用 `_REVISION_DIFF.md` 看清单外
            #     有没有越界改动。提示里写清"仍要给完整 status、仍可判 FAIL"，避免它为了省事放水。
            if (stage["id"] in _FIX_HANDOFF_JUDGES
                    and int((state.get("fix_rounds") or {}).get(stage["id"], 0)) > 0):
                round_hint = (round_hint + "\n" + _rubric_recheck_hint(stage["id"])).strip()

            # 「⑫ 交接时置的复评意向」在这里**取走**：它只对**紧接其后的 ⑬**
            #   有意义，而且必须在**每一条**出路（真跑 / 被接管 / 豁免 / stale / manual / 失败）
            #   上被消费掉，否则会留下一个悬空标志 —— ⑬ 那几条 `continue` 早返回正好都跳过
            #   唯一的消费点（下面 fix 跑完那段跳回），后果：⑬ 失败挂黄灯 → 人工修好后
            #   认证续跑 ⇒ ⑫ 一次都不复评、`fix_loop_return` 却还挂着，链
            #   照样跑完 ⑭⑮⑯ 并报成功，而 ⑫ 的 NEEDS_FIX 裁决从未被重新看过。
            # 用「读 + 显式置 False」而不是 `state.pop(...)`：pop 会把键**从 state 里删掉**
            #   （`and` 的右操作数在 ⑬ 那一轮必然被求值），于是跑完一轮后 `/api/state` 里
            #   时有时无 —— 状态字典的形状不该随跑到哪而变（首轮与后续轮不一致的坑）。
            # 交接单：**哪一关**把"论文侧定点改写"交给了 ⑬。取走即清空（一次性）。
            #   口径：⑮ 判完给 ⑬ 改，正如 ⑫ 判完给 ⑬ 改一样，⑬ 改完后直接跳回 ⑮。
            _fix_handoff = ""
            if stage["id"] == "fix":
                # 这里**就地清空**是刻意设计，有用例钉着（`test_the_handoff_marker_is_
                #   consumed_even_when_the_repair_fails`：「标志不许悬空」）。试过
                #   改成"跑完才消费"以救「⑬ 被打断后重试会跳过 ⑫」，那条用例当场变红 ⇒ 只能撤回。
                #   代价如实记下：**⑬ 被暂停/失败后人工点「再试一次」，跑完不会回跳本门禁**，
                #     于是 `index` 从 ⑬ 直接走到 ⑭ —— 若交接方是 ⑪（⑫ 从没跑过），⑫ 就被跨过。
                #     要补 ⑫ 得手动从它起跑一次。
                _fix_handoff = str(state.get("fix_loop_return") or "")
                state["fix_loop_return"] = ""
            # ---- 13Repair-by-rubric-verdict 无事可做时跳过 ----
            # rubric 明确通过、没有 must/fatal 判词时，fix 没有任何东西要改 ——
            # 每次干净跑都白调一次 agent 不值当。带 hint（面板上点了「再试一次」）时不跳。
            #   `and not _fix_handoff`：带着交接单来的 ⑬ **必须真跑** ——
            #     ⑫ 可能刚刚 PASS（`_rubric_hands_off()` 于是返回 False ⇒ 判"无事可做"），
            #     但 ⑮ 的判词正等着它改。少了这一条，⑮ 那份交接单会被静默吞掉。
            if stage["id"] == "fix" and not round_hint and not _fix_handoff \
                    and not _rubric_hands_off():
                log("12Rubric-final 没有 must/fatal 判词，跳过 13Repair-by-rubric-verdict（省一次调用）。"
                    "要强制跑就从 12Rubric-final 重跑 —— 它会重新判词。")
                state["stages"]["fix"] = "done(skip)"
                _save_receipt(stage)
                # 这条跳过**同样要镜像**：它是唯一一条"阶段完成却不经过
                #   `run_stage` 尾部"的路径（其余复用路径都在下面 `_snapshot_stage` 之后），
                #   少了它，「每个阶段每轮镜像一次」这条不变量就有一条缝 —— 展示区里 ⑬ 那格
                #   会停在上一轮的副本上，而别的阶段都是新的。`fig_before=None` = 不做图差分，
                #   照上一轮记下的图键回填（⑬ 不画图，正合适）。
                _snapshot_stage(stage)
                _tick(stage["id"])
                index += 1
                continue
            # 记下跑之前的图登记表 —— 跑完比一比就知道这一阶段画/重渲了哪些图
            # （`figures/` 不在 `ARTIFACTS` 里，图的归属只能这样现算）。
            fig_before = _figure_index()
            outcome = await run_stage(stage, round_hint=round_hint,
                                      fix_handoff=_fix_handoff)
            if state["stopping"]:
                break
            if outcome not in ("ok", "waived", "manual", "stale", "taken-over", "confirmed"):
                # 超时黄灯上用户选了「取消并重试 / 回退」→ 由本链落实，不 _halt
                nxt = _consume_resume_action(stage, index, hints)
                if nxt is not None:
                    index = nxt
                    continue
                hint = ("输入（题面/数据/plan.md 或门禁阶段的被审对象）在该阶段执行期间被改动，"
                        "本轮产物与进入时的输入不再对应，不能冒充成功交付。"
                        "常因：运行中往 request//data/ 放了文件、或门禁阶段自己改了被审的论文/代码。"
                        if outcome == "unverified" else "")
                _halt(stage, f"阶段未成功完成：{outcome}" + (f" —— {hint}" if hint else ""),
                      outcome, kind="failure")
                break
            # 阶段完成（含 5 条复用路径：`ok(skip)` / `manual` / `stale` / `taken-over` /
            #   `waived`）→ 镜像进「各阶段产物」。放在这里而不是 `run_stage` 内部，三个理由：
            #   ① `run_stage` 的成功分支在**门禁裁决之前**，会把被否的产物先摆进展示区；
            #   ② 它有 6 条早返回，都不是「阶段完成」；
            #   ③ 只有放在这里才**同时覆盖复用路径** —— 否则功能上线后第一次按「开始全链」、
            #      16 个阶段全 `ok(skip)` 秒过时，「最新产物」是空的。
            # 非门禁阶段在这里就落定；**门禁**不行：它的裁决要等下面
            #   `gate_result()` 才算，协议返修还会**重写裁决侧车** —— 在这里镜像等于把
            #   「被门禁否掉的那一版」和「被取代的 UNVERIFIED 裁决」先摆进展示区。
            #   门禁的镜像挪到裁决定下来之后（见 `_record_quality(stage, verdict, …)` 下面）。
            if not stage.get("gate"):
                _snapshot_stage(stage, fig_before)
                _maybe_collect_outputs(stage)
            # ⓪ 读题跑完 ⇒ **停在这儿等人核对**（AI 读完后把读到的东西展示给用户、
            #   让用户核对"读得对不对"，确认了才继续）。判据是**纯盘面**的（inbox 里还有没被
            #   确认过的原件，见 `_intake_unconfirmed`）—— 所以既有的全链跑法（工作区里没有
            #   `request/_inbox/`，包括几十条回归用例）行为一字不变。
            #   必须**自己补一次 `_save_receipt`**：通用那条回执在这句 `break` 之后才写，
            #   少了它读题产物就没有回执 ⇒ 每点一次「开始全链」都重烧一次读题（一次是分钟级）。
            if stage["id"] == "intake" and _intake_unconfirmed():
                _save_receipt(stage)
                _halt(stage, "题目已读完，请核对 AI 读到的内容（题面正文 / 每份原件的去向）"
                             "—— 确认后从 ① 文献定向 起跑；不认可就点「再试一次」重读",
                      "awaiting_confirm", kind="intake")
                break
            if outcome == "waived":
                # 人工已「接受并披露」：该阶段的门禁结论**不再生效** ——
                # 否则报告里那条 FAIL 会被重新读出来、又把它打回黄灯，形成死循环。
                # 豁免本身绑定输入指纹，输入一变 _waived() 就返回 None、门禁自动重新生效。
                state["stages"][stage["id"]] = "done(disclosed)"
                _tick(stage["id"])
                index += 1
                # 这里**刻意不处理 `_fix_handoff`**：④ 条复用近路（waived/stale/manual/taken-over）
                #   都带 `and not fix_handoff` 的闸 ⇒ 带着交接单的 ⑬ **不可能**从这些路返回 ⇒
                #   这段是死代码。交接单的三种结局统一由**唯一活着的**那个调用点处理（⑬ 真跑完
                #   之后，见 `_back_to_judge` 的调用处）—— 一处实现，不会两处说法不一致。
                continue
            if outcome == "confirmed":
                # ⓪ 读题：人工已确认、产物已恢复 ⇒ 状态由 `run_stage` 置好了，
                #   这里只越过"复用态被覆写成 done"那段（与 `waived` 同一处置）。
                index += 1
                continue
            if outcome == "stale":
                # 只有「做法要求」变了 → 不重跑，保留产物，只标状态 + 记进 stale_instr。
                # 与 manual 同理：必须**跳过下面那条重存回执**，否则状态会被打回 done，
                # 面板上的提示就没了（而且重存会把当前 digest 写进去，"要求变过"这件事被抹掉）。
                # 人工认证过的保持「人工认证」标记（两个信息叠加，不互相覆盖）。
                state["stages"][stage["id"]] = ("done(manual)" if _receipt_store().is_manual(stage["id"])
                                                else "done(stale-instr)")
                _tick(stage["id"])
                index += 1
                # 这里**刻意不处理 `_fix_handoff`**：④ 条复用近路（waived/stale/manual/taken-over）
                #   都带 `and not fix_handoff` 的闸 ⇒ 带着交接单的 ⑬ **不可能**从这些路返回 ⇒
                #   这段是死代码。交接单的三种结局统一由**唯一活着的**那个调用点处理（⑬ 真跑完
                #   之后，见 `_back_to_judge` 的调用处）—— 一处实现，不会两处说法不一致。
                continue
                continue
            if outcome == "taken-over":
                # 被 14Layout-and-format 精修接管：状态已由 run_stage 按 is_manual 设好，
                # 这里**只负责跳过下面那条重存回执** —— 它会用默认 manual=False 抹掉认证标记。
                _tick(stage["id"])
                index += 1
                # 这里**刻意不处理 `_fix_handoff`**：④ 条复用近路（waived/stale/manual/taken-over）
                #   都带 `and not fix_handoff` 的闸 ⇒ 带着交接单的 ⑬ **不可能**从这些路返回 ⇒
                #   这段是死代码。交接单的三种结局统一由**唯一活着的**那个调用点处理（⑬ 真跑完
                #   之后，见 `_back_to_judge` 的调用处）—— 一处实现，不会两处说法不一致。
                continue
                continue
            if outcome == "manual":
                # 人工认证过的阶段：标 done(manual) 并**跳过下面的重存回执** ——
                # 那条 save 不带 manual 标记，会把认证标记抹掉，前端就再也画不出「人工认证」标记。
                state["stages"][stage["id"]] = "done(manual)"
                _tick(stage["id"])
                index += 1
                # 这里**刻意不处理 `_fix_handoff`**：④ 条复用近路（waived/stale/manual/taken-over）
                #   都带 `and not fix_handoff` 的闸 ⇒ 带着交接单的 ⑬ **不可能**从这些路返回 ⇒
                #   这段是死代码。交接单的三种结局统一由**唯一活着的**那个调用点处理（⑬ 真跑完
                #   之后，见 `_back_to_judge` 的调用处）—— 一处实现，不会两处说法不一致。
                continue
                continue
            verdict = gate_result(stage)
            # 裁决缺失/格式错只重试 1 次（重试 2 次会把最坏耗时翻倍）；格式/一致性类失败只补侧车，
            # 不重做审查、不清报告本体。
            if verdict == "UNVERIFIED" and not state["stopping"]:
                pending = _gate_decision(stage)
                if _protocol_repair(pending, REPORTS / stage["report"]):
                    outcome = await run_stage(stage, round_hint=_verdict_repair_hint(pending),
                                              repair_only=True)
                else:
                    outcome = await run_stage(stage, round_hint=
                        "裁决缺失、冲突或版本不符。请核对当前对象并输出明确裁决及 JSON；不能假定之前审核已完成。")
                if outcome == "ok":
                    verdict = gate_result(stage)
            if state["stopping"]:
                break
            if outcome not in ("ok", "waived") or verdict == "UNVERIFIED":
                _halt(stage, "未获得当前版本的明确有效裁决", "unverified", kind="failure")
                break
            decision = _gate_decision(stage)
            _record_quality(stage, verdict, decision["reason"], issues=decision.get("issues", []))
            # 门禁的镜像/阶段性打包**不在这里**（见下面 `index += 1` 之前那段）：
            #   这里只算出了 `decision`，**裁决还没被处置** —— FAIL/stale/到顶的交回都排在
            #   下面好几十行（`_halt(...)` + `break`）。在这儿就镜像+打包的话，等于
            #   「被门禁否掉的那一版」照样进了展示区、还进了 `提交作品/最新作品/`，
            #   而紧接着的挂起文案写着「保留草稿，**不收集为正式交付**」—— 自相矛盾。
            #   形态（三个 `never_collects` 用例钉着）：
            #   `cross` 判 FAIL 的那一轮，`_collect_outputs` 会被调 1 次、
            #   快照日志先于「cross 挂起」出现。
            # 门禁**通过**之后就不再挂「N 条建议」的角标（
            #   12 评审过了之后那个带 13 的建议角标就不需要显示）。两条理由：
            #   ① 自相矛盾 —— 那一行已经是 ✅ 了，旁边还挂个"还有 13 件要不要做"，
            #      读面板的人不知道该信哪个；
            #   ② 该投递的机器侧**在决策那一刻就已经投递了** —— 下面 `by_target` 那段会把
            #      目标阶段在后面（⑬⑭…）的建议折进那个阶段的提示里（标着"可选、按成本决定"）。
            #   原文一个字都不会丢：整份建议仍在 `reports/RUBRIC_REVIEW.md` 的裁决里、
            #   也仍在 HIL 决策面板上；这里撤掉的只是**阶段行上那个入口**。
            #   代价（如实记下）：目标阶段**在前面**的建议（`CONTENT_TARGETS` 映射回
            #   ②/④ 那些，例如 `report_wording`→analysis）不会被任何后续阶段带走 ⇒
            #   它们此后只存在于报告里，面板上不再提醒。这是已知且接受的取舍。
            if decision.get("advisories"):
                # 这段是**机器侧唯一的投递通道**，PASS 与否都要走（差一点就被
                #   跟"角标"一起关掉）：建议的目标阶段若排在后面（⑬⑭…），就折进那个阶段的提示。
                # 而且必须**按 severity 分两段写**（见 `_adv_is_must`）：`advisories` 里混着
                #   「真·可选项」与「降级下来的必做项」，一句话盖过去就会把红线级要求说成可选。
                by_target = {}
                for adv in decision["advisories"]:
                    dest = CONTENT_TARGETS.get(adv.get("category"), "write")
                    by_target.setdefault(dest, []).append(adv)
                for dest, advs in by_target.items():
                    if not any(s["id"] == dest for s in STAGES[index + 1:]):
                        continue
                    lines = []
                    for must, label in ((True, f"**必做**的延后项（{dest} 阶段必须落实，"
                                               f"它排在门禁之后、门禁当时修不了）："),
                                        (False, f"可选建议（{dest} 阶段可核查、"
                                                f"按成本决定是否落实）：")):
                        picked = [a for a in advs if _adv_is_must(a) is must]
                        if picked:
                            lines.append("前序门禁" + label + "；".join(_adv_text(a) for a in picked))
                    if lines:
                        hints[dest] = (hints.get(dest, "") + "\n" + "\n".join(lines)).strip()
            # 阶段行上的建议角标：
            #   · 门禁未通过 ⇒ 全部留着（用户靠它按成本决定做不做）；
            #   · 门禁通过   ⇒ 只留**必做项**。**不能全撤**：⑫ 是 PASS 的，
            #     可那 13 条里有 2 条是 hard+must（图内内部词泄漏、PDF 标题层认不出稳健性检验
            #     模块）—— 一个 ✅ 行旁边什么都不挂，这两条就再没有任何人看得到。
            #     要撤的是"13 条可选建议"那堆噪音，不是把必做项一起藏起来。
            if verdict != "ok":
                if decision.get("advisories"):
                    state["adv_by_stage"][stage["id"]] = decision["advisories"]
                else:
                    # 复评后**一条建议都没有**时，旧的必须撤掉（
                    #   "这个随着每次复评更新"）。缺这个 `else` ⇒ 那一批**上一轮的**
                    #   建议会原封不动挂在阶段行上 —— 面板显示的是旧裁决的建议，
                    #   而它对应的裁决早就不存在了（谎报）。判据本身仍由 `issues_by_stage` 那段
                    #   如实反映（🚧 那一栏不吃这条路径）。
                    state["adv_by_stage"].pop(stage["id"], None)
            else:
                _must = [a for a in (decision.get("advisories") or []) if _adv_is_must(a)]
                if _must:
                    state["adv_by_stage"][stage["id"]] = _must
                else:
                    state["adv_by_stage"].pop(stage["id"], None)
            # 判据角标（见 `issues_by_stage`）：门禁没过就留着这一关判了什么，过了就撤 ——
            #   过了还挂着会让人以为"这条还没修"。
            if verdict != "ok" and decision.get("issues"):
                state["issues_by_stage"][stage["id"]] = decision["issues"]
            else:
                state["issues_by_stage"].pop(stage["id"], None)
            # ---- 门禁失败 / agent 交回上游 ----
            # 不能按默认映射**自动回退**：那条路把最坏耗时放大到 6 次执行，
            # 且人在关键决策上插不上手。现在一律转黄灯，把「agent 推荐退到哪个阶段」
            # 算出来交给用户定（界面上的下拉默认选中它就是）。
            hb = check_handback(index)
            if hb is not None:
                _halt(stage, f"{stage['id']} 按 SKILL 交回上游：建议退到 `{STAGES[hb]['id']}`",
                      "blocked", kind="failure", handback=hb, decision=decision)
                break
            # ---- rubric 的正向出路 ----
            # 其余四个门禁只有"回退"一条路；rubric 多一条：claim 类判词（措辞/摘要/结论表述/
            # 创新点的表达）交给紧随其后的 13Repair-by-rubric-verdict 就地改写，不回退 write 重跑整篇。
            # 这里**不停机**：裁决仍留在 RUBRIC_REVIEW.verdict.json 里，13Repair-by-rubric-verdict 读它当判词。
            #   模型/数值/实现类判词不会走到这儿 —— _rubric_route 遇到它们就改成向后回退，
            #   落到下面的通用 _halt（黄灯，由用户定退到哪个生产阶段）。
            if (stage["id"] in _FIX_HANDOFF_JUDGES and decision.get("target") == "fix"
                    and verdict not in {"ok", "claim_revision"}):
                # 自动来回修到了上限 ⇒ 不再前进给 13，落到下面的通用 `_halt` 转黄灯交人
                #   （口径：「先最多 3 轮…还不过就转黄灯问人」）。
                _done = int((state.get("fix_rounds") or {}).get(stage["id"], 0))
                if _done >= RUBRIC_FIX_MAX_ROUNDS:
                    log(f"{stage['name']} 已自动来回修 {_done} 轮仍未过 ⇒ "
                        f"转黄灯交人决定（可回退、可披露，也可再点「再试一次」再加一轮）")
                else:
                    log(f"{stage['id']} 判词为论文侧修改（{len(decision.get('issues') or [])} 项），"
                        f"交 13Repair-by-rubric-verdict 定点改写，改完回本门禁复评"
                        f"（第 {_done + 1} / {RUBRIC_FIX_MAX_ROUNDS} 轮）")
                    # 把必须逐条处置的判词 id 就地存下，供 13 交处置表时对账。
                    # 事后重读不行：13 一改 paper/，本门禁的 input_digest 就变了。
                    state["fix_required"] = [str(i.get("id")) for i in (decision.get("issues") or [])
                                             if str(i.get("id") or "").strip()]
                    state["stages"][stage["id"]] = "done(conditional)"
                    state["fix_loop_return"] = stage["id"]   # 13 跑完据此跳回本门禁
                    _save_receipt(stage)
                    _tick(stage["id"])
                    # 用 `STAGE_IDX["fix"]` 而不是 `index += 1`：对 ⑫ 是等价的（⑬ 紧跟其后），
                    #   但 ⑮ 验收 排在 ⑬ **之后** ⇒ 只有显式跳回去才到得了 ⑬。
                    index = STAGE_IDX["fix"]
                    continue
            if verdict not in {"ok", "claim_revision"}:
                if decision.get("reason") == "verdict_stale":
                    # 裁决过期 ≠ 门禁判了不合格。它是**按旧要求**写的（判据/输入在那之后变过：
                    # 改过 `skills/_references/`、门禁 SKILL、或驱动代码），改 `.verdict.json`
                    # 改不动"它是在另一套要求下审出来的"这件事。
                    # 但出路要看**被审的正文动没动**（见 `_build_pending` 那段说明）：
                    d = decision.get("stale_digest") or {}
                    n = len(decision.get("stale_issues") or [])
                    if d.get("artifacts_changed"):
                        why = (f"门禁裁决**过期**：被审的报告在这份裁决之后被改过，"
                               f"findings 指向的文字已经不在现在这份里 —— 只能在新正文上重判"
                               f"（不是它判了不合格，也不是上游的错）。上一轮它查出 {n} 条，仅供参考。")
                    else:
                        why = (f"门禁裁决**过期**：只有做法要求/判据变了，**被审的报告一个字没动** —— "
                               f"它上一轮查出的 {n} 条仍然指着现在这份报告里真实存在的文字，"
                               f"可以当普通回执退给上游，也可以重跑本门禁拿一份按新要求写的裁决。")
                    _halt(stage, why + f"（记录指纹 {str(d.get('recorded'))[-12:]}，"
                                       f"当前 {str(d.get('current'))[-12:]}）",
                          "stale", kind="failure", decision=decision)
                    break
                _halt(stage, f"门禁未通过（{verdict}）：{decision.get('reason', '') or '见回执'}",
                      "blocked", kind="failure", decision=decision)
                rec = (state.get("pending") or {}).get("recommended")
                if rec:      # 计数降级为「这条返修路径被回退过几次」，供面板参考，不再当闸
                    k = f"{stage['id']}->{rec}"
                    state["rounds"][k] = state["rounds"].get(k, 0) + 1
                break
            if verdict == "claim_revision":
                if not any(s["id"] == "write" for s in STAGES[index + 1:]):
                    # ⑮ 验收 这一档（口径：「15 判完给 13 改，正如 12 判完给 13 改一样」）：
                    #   它后面没有写作阶段，但「论文侧定点改写」这件活 ⑬ 就是为它造的 ——
                    #   交给 ⑬、改完跳回 ⑮ 复评（与 ⑫↔⑬ 同一套）。⑮ 自己会**重新编译**
                    #   （SKILL 的 Step 7 编译 + Step 8 逐页视觉），所以跳过 ⑭ 不会留下一份
                    #   旧 PDF；万一 ⑬ 那一改把版式弄坏（补一行表格顶超页），⑮ 判出的
                    #   presentation 类判词目标正是 ⑭ ⇒ 那时才去跑 ⑭，自纠正。
                    _done = int((state.get("fix_rounds") or {}).get(stage["id"], 0))
                    if stage["id"] in _FIX_HANDOFF_JUDGES and _done < RUBRIC_FIX_MAX_ROUNDS:
                        log(f"{stage['id']} 判词全为论文侧（{len(decision.get('issues') or [])} 项）"
                            f"且本关之后没有写作阶段 ⇒ 交 13Repair-by-rubric-verdict 定点改写，"
                            f"改完回本门禁复评（第 {_done + 1} / {RUBRIC_FIX_MAX_ROUNDS} 轮）")
                        state["fix_required"] = [str(i.get("id"))
                                                 for i in (decision.get("issues") or [])
                                                 if str(i.get("id") or "").strip()]
                        state["stages"][stage["id"]] = "done(conditional)"
                        state["fix_loop_return"] = stage["id"]
                        _save_receipt(stage)
                        _tick(stage["id"])
                        index = STAGE_IDX["fix"]
                        continue
                    if stage["id"] in _FIX_HANDOFF_JUDGES:
                        log(f"{stage['name']} 已自动来回修 {_done} 轮仍未过 ⇒ 转黄灯交人决定")
                        _halt(stage, f"{stage['name']} 的论文侧判词自动来回修已达上限"
                                     f"（{RUBRIC_FIX_MAX_ROUNDS} 轮）", "blocked",
                              kind="failure", decision=decision)
                        break
                    _halt(stage, "REVISE_CLAIM 缺少后续写作阶段", kind="driver")
                    break
                # 报告名要**跟着当前阶段走**：写死 `RESULT_AUDIT_REPORT.md` 的话，
                #   而 cross（11Cross-question-check）现在也走这条纯 claim 通道 ⇒ ⑨ 会被指去看一份
                #   ⑨ 会被指去看一份跟它无关的报告。用 `stage["report"]`：audit 仍是
                #   RESULT_AUDIT_REPORT.md，cross 就是 CROSS_QUESTION_REVIEW.md。
                hints["write"] = (f"必须逐项落实 {stage['report']} 中的 REVISE_CLAIM；"
                                  f"后续终验须核查。")
            # `_ran_now` 必须在下面那条状态赋值**之前**取。
            #   `_stage_ran_this_round()` 读的就是 `state["stages"][sid]`，而下面那句会把
            #   复用留下的 `done(skip)` 覆盖成 `done` ⇒ 复用的阶段被当成「这一轮真跑过」。
            #   典型形态：⑪结果可信度审计 判 NEEDS_FIX → 回退到 ⑤编码计算
            #   → ②建模设计 被复用，可它的返修台账答的是 ③建模评审 那份回执，而回退时
            #   `_save_feedback` 又把审计的裁决另存进了 feedback/（成了最新的一份）
            #   ⇒ 自检报「receipt 指错了」当场挂起；重试仍是复用 ⇒ **死循环，出不来**。
            _ran_now = _stage_ran_this_round(stage)   # 见该函数的注释：复用不能做收尾自检
            # 状态回写：**只跳过"复用"那一种**（`done(skip)`），别的一律写。
            #   别拿 `_ran_now` 当这里的条件 —— 那个函数的判据是 `status == "done"`，而
            #   **门禁真跑完时状态是 `awaiting_review`**（等裁决，见 `run_stage` 里那句
            #   `"done" if not gate else "awaiting_review"`）⇒ 拿它当条件会把门禁的状态**写漏**，
            #   于是门禁永远停在 `awaiting_review`、面板渲染成 ⏸/黑 —— 看着像"没通过"，
            #   而裁决其实早就 PASS、链早就走到下一阶段了。有人报过
            #   "绘图门禁怎么是黑的、不是通过了吗"，根因就是 `if _ran_now:` 这个条件。
            #   能走到这一行的只有三种：真跑完的非门禁（`done`，写回同值）、**真跑完的门禁**
            #   （`awaiting_review`，必须写）、**复用**（`done(skip)`，不写）；其余路径
            #   （manual / stale / taken-over / waived / rubric→fix）都在上面 `continue` 掉了。
            if state["stages"].get(stage["id"]) != "done(skip)":
                state["stages"][stage["id"]] = ("done(conditional)" if verdict == "claim_revision"
                                                else "done")
            _save_receipt(stage)
            _tick(stage["id"])
            # 门禁的镜像 + 阶段性打包**在这里**：上面所有「否掉 / 过期 / 到顶 / 交回上游」
            #   的出路都已经 `_halt(...)` + `break` 走了，能走到这一行的门禁 = **这一版被认可**
            #   （通过，或判词交给 ⑬ 定点改写走的是更上面那条 `continue`）⇒ 摆进展示区、
            #   收进 `提交作品/最新作品/` 才是诚实的。非门禁阶段在上面（`if not stage.get("gate")`）
            #   已经镜像+打包过，这里只补门禁。
            if stage.get("gate"):
                _snapshot_stage(stage, fig_before)
                _maybe_collect_outputs(stage)
            index += 1
            # ---- 3analysis 收尾自检：题意契约的锚点还指得到原文吗 ----
            # 契约（先写）与建模报告（后定稿）是**同一个阶段的两个产物**，却以必然互相
            # 矛盾的顺序产出 —— 报告一改，契约里逐字引用的原文就找不到了。撞过这种情况：
            # 门禁 4review 在 40 分钟后才拦下，那时 agent 上下文早没了、人也被卡在下一个阶段。
            # 前移到这儿：当场挂起、指名哪几条锚点、也不用白跑一轮 review。
            # 只在**契约文件存在**时才判。这条检查的语义是「你交出去的契约与报告自洽吗」，
            #   缺文件/结构错是**另一类**失败（产物没交），由下游门禁报 —— 那儿的文案本来
            #   就写清了"必须先写该契约"。不这么分的话：断点续跑时 analysis 靠回执被跳过，
            #   这里仍会拿一个"本来就没有契约"的工作区把链拦下（全链用例当场变红）。
            if (stage["id"] == "analysis" and _ran_now and not state["stopping"]
                    and (ROOT / "config/content_quality.json").exists()
                    and (REPORTS / "TASK_CONTRACT.json").is_file()):
                problems = task_contract_issues(ROOT)
                if problems:
                    _halt(stage, f"题意契约自检不过（{len(problems)} 条）：{problems[0]}",
                          "blocked", kind="failure")
                    for p in problems[:6]:
                        log(f"  · {p}")
                    break
            # ---- 返修台账：返修记录**不许自证** ----
            # 「本轮返修复验记录」里写「§15.1 该句改『≤0.98%』」时，那句话本身就是 `≤0.98%`
            # 的一次出现 —— 拿"全文检索"当自检，记录自己把自己证明了。
            # 同一份报告里可能有三处这类假命中：`≤0.98%` / `66600 s` / `M3`+`热供给` 全在版本表
            # 或返修记录里，正文一处未改；还有一种前缀碰撞（要 `q4.moist_max_at_tend`，只加了
            # `..._minus_60s`）。后果是 review 每轮重查、每轮打回，白烧几十分钟。
            # 前移到阶段收尾：当场挂起、指名哪条探针是"自证"，不用白跑一轮 review。
            # 与题意契约自检同一个开关约定：只在启用严格模式时生效。
            if (stage["id"] == "analysis" and _ran_now and not state["stopping"]
                    and (ROOT / "config/content_quality.json").exists()):
                problems = receipt_ledger_issues(ROOT)
                if problems:
                    _halt(stage, f"返修台账自检不过（{len(problems)} 条）：{problems[0]}",
                          "blocked", kind="failure")
                    for p in problems[:6]:
                        log(f"  · {p}")
                    break
            # ---- 13Repair-by-rubric-verdict 的逐条处置对账 ----
            # 没有这道校验，一份「什么都没做、也没说为什么」的 FIX_REPORT 与一份
            # 「逐条核过、两条判词被证伪所以没改」的在驱动眼里完全一样。
            # 与其它 content-quality 检查一致：只在启用严格模式时生效。
            if (stage["id"] == "fix" and not state["stopping"]
                    and (ROOT / "config/content_quality.json").exists()):
                problems = fix_disposition_issues(ROOT, state.get("fix_required") or [])
                if problems:
                    _halt(stage, "13Repair-by-rubric-verdict 的逐条处置不合规：" + problems[0], kind="failure")
                    break
            # 13Repair-by-rubric-verdict 修完 ⇒ **回到 12Rubric-final 复评**（
            #   ⑫ 没过就亮黄灯，等 ⑬ 处理后再返回 ⑫）。13 改的是正文 ⇒ 给 rubric
            #   的输入指纹换了一版 ⇒ 回到 12 时它被判失效、真重判。
            #   必须放在**上面那段逐条处置对账之后**：放前面会把它整段跳过
            #   （`test_fix_must_hand_back_a_disposition_for_every_verdict` 钉着这条）。
            if _fix_handoff:
                # 这是**唯一活着**的交接单落地点（⑬ 真跑完之后）—— 三种结局都在这里处理，
                #   别在别处再写一份（在四条复用近路上也各写一份的话，那些路现在都被
                #   `and not fix_handoff` 挡住 ⇒ 那四份是死代码，还打着"越过它继续往下"的日志
                #   骗人）。
                _act = _back_to_judge(_fix_handoff)
                if _act == "back":
                    continue
                if _act == "halt":
                    break                # 到轮数上限 ⇒ 已 _halt 转黄灯，别再往前走
                # "forward"（⑬ 没动稿：判词不属实 / 判它 not_reproduced）⇒ **越过**刚交接的
                # 那一关再往前。从 ⑬ 直接 `index += 1` 走到的是 ⑭，再往前就**又撞回 ⑮** ⇒
                # 而 ⑮ 读到的还是那份没变的裁决 ⇒ 再交接 ⑬ …… 无界空转。
                # 越过是安全的：`forward` 的判据是"那一关的审查对象**一个字没动**"
                # ⇒ **已经跑过**的阶段都没有需要重跑的新输入。
                # 但"没跑过"的不算（暂停之后续跑就会撞上）：
                #   交接单可能来自**排在 ⑬ 前面**的门禁（⑪ 跨问一致性 / ⑫ 评分标终审）——
                #   ⑪ 交接时 `index` 被直接指到 ⑬，**⑫ 从没跑过**；此时 `forward` 的
                #   `max(index + 1, 11 + 1)` = `max(14, 12)` = 14 ⇒ 直接落到 ⑭，
                #   **⑫ 一次都不评**，尾段「收尾不再重判任何判官」⇒ 此后永远不跑。
                #   所以这里改成：**只跳过已经跑过（done*）的阶段**，第一个没跑过的就回去跑它。
                _after = STAGE_IDX[_fix_handoff] + 1
                while (_after < index
                       and str(state["stages"].get(STAGES[_after]["id"], "")).startswith("done")):
                    _after += 1
                # `_after < index` 不成立时（交接的是 ⑫ 自己、或中间全跑过了）保持原语义，
                # 也就不会把 `index` 指回 ⑬ 自己而空转。
                index = _after if _after < index else max(index + 1, _after)
        # **收尾不再重判任何判官**（原 `RECHECK_STAGES` 复验循环已删）。
        #   原循环的用途是「谁在成稿上做的判断，其结论必须对应当前版本」——但新顺序里排在
        #   内容判官之后的是 ⑫评分标终审 / ⑬按评分判词返修 / ⑭排版与版式，它们只**打磨措辞与版式**：
        #   口径：「11 过后，已经表示正文就是没问题了，12 和 13 只是打磨一下语句，那肯定和
        #   之前做的对不上啊」⇒ 用"文件字节变了"把 ⑩⑪ 拉回来重判，就是把打磨当成改内容
        #   （每轮多三次门禁复评、每次十几分钟，而它们判的东西一个字没变）。
        #   兜底没丢：⑮验收 本来就排在 ⑭ 之后、⑯Demo 之前（⑯ 还会往
        #   `paper_appendix/` 补一节 demo 展示，见 `_open_demo_page` 上面那段 —— 那是**新增展示**，
        #   不改已有推导，与打磨同性质）；⑫ 的复评由
        #   ⑫↔⑬ 环路负责（见 `_back_to_judge`）；⑬ 的处置对账由 `fix_disposition_issues` 负责。
        #   痕迹：被打磨过的内容判官进 `state["layout_superseded"]`，面板上看得见、需要时可手动重跑。
        if index == len(STAGES) and not state["stopping"] and not state["halt_gate"]:
            if _collect_outputs() is False:
                _halt(STAGES[-1], "交付包收集失败", "failed", kind="driver")
            else:
                normal_end = True
                state["run_completed"] = True
                # 整链跑完 → 把 ⑯ 产出的 demo 用系统默认浏览器打开。
                # 放在 `run_completed` **之后**：面板的状态与"自动开"是同一件事的两面，
                # 先置位再开浏览器，即使开失败，前端该弹的赠言浮层照弹。
                _open_demo_page()
    except Exception as exc:
        _halt(STAGES[min(index, len(STAGES) - 1)], _driver_exc_text(exc), "failed", kind="driver")
    finally:
        state["running"] = False
        state["cur"] = None
        if state["run_start"]:
            state["elapsed_base"] = round(float(state["elapsed_base"]) + time.time() - state["run_start"], 1)
            state["run_start"] = None
        for sid in state["stage_t"]:
            _finalize_stage(sid)
        state["progress"]["done"] = sum(str(v).startswith("done") for v in state["stages"].values())
        # 按的是「暂停」→ 停到**黄灯**，不是硬停。
        #   硬停会把链丢在一个没有决策入口的死状态里：产物停在半路，人却只能干看着，
        #   要接着做只能重新点「开始全链」（还得自己猜从哪续）。转黄灯后，
        #   面板上就能直接选「再试一次 / 回退到某阶段 / 接受并披露 / 我已手工修好」。
        if state.pop("pause_to_halt", False) and not normal_end and not state["halt_gate"]:
            try:
                _halt(STAGES[min(index, len(STAGES) - 1)],
                      "你按了暂停：下面是停在这一步的上下文，接着选下一步",
                      "paused", kind="paused")
            except Exception as exc:
                log(f"（暂停转黄灯失败，按硬停处理：{exc}）")
        # 一键托管：走到这里 `state["running"]` 已经是 False ⇒ 可以安全地落实
        #   （回退 + 起新链）。置位见 `_halt`；超时那一档在 `_call` 的看门狗里当场落实。
        if state.pop("autopilot_armed", False):
            try:
                await _autopilot_fire()
            except Exception as exc:                    # noqa: BLE001 —— 托管绝不拖垮收尾
                log(f"⚠️ 托管自动执行异常（已转人工）：{exc}")
        _clock_persist()
        emit("state", state2dict())
        emit("end", state2dict())
        log("链完成并收集交付物" if normal_end else "链停止或挂起；未产生本轮正式交付")


def state2dict():
    el = float(state.get("elapsed_base", 0.0) or 0.0)
    if state.get("run_start"):
        el += time.time() - state["run_start"]
    elapsed = round(el, 1)
    return {"running": state["running"], "cur": state["cur"], "run_id": state["run_id"],
            "stages": dict(state["stages"]), "stage_t": {k: dict(v) for k, v in state["stage_t"].items()},
            "progress": dict(state["progress"]), "rounds": dict(state["rounds"]),
            "elapsed_total": elapsed,
            # 做法要求变过、但产物没重跑的已完成阶段。**必须暴露** —— 不暴露就是静默放行。
            "stale_instr": sorted(state.get("stale_instr") or []),
            # 只被 ⑭ 版式改过、因此**免于重判**的内容判官。必须暴露 —— 不暴露就是静默放行
            # （用户口径见 _layout_superseded 那段：需要时从该阶段手动重跑）。
            "layout_superseded": sorted(state.get("layout_superseded") or []),
            # 日志写文件失败过几次 —— 不暴露就又是"静默丢证据"（见 log() 的注释）。
            "log_write_errors": list(state.get("log_write_errors") or [])[-5:],
            # 一键托管开着没有 —— 前端那个按钮的高亮全靠它（不暴露的话刷新后按钮会显示成关的，
            # 而驱动其实还在托管，两边说的不是一回事）。
            "autopilot": bool(state.get("autopilot")),
            "run_completed": state["run_completed"], "halt_gate": state.get("halt_gate", False),
            "halt_reason": state.get("halt_reason", ""),
            # 人工决策（黄灯）：pending 是前端渲染面板的唯一依据
            "pending": state.get("pending"),
            # 各阶段的轻微/可选项。带 pending 的那些已经进了面板，这里另外暴露是为了
            # **判词全部通过（只剩轻微项）时也看得见** —— 那时没有黄灯，面板不出现。
            "advisories": {k: v for k, v in (state.get("adv_by_stage") or {}).items() if v},
            # 各阶段**未解决的门禁判据**（会阻断的那批）。与 `advisories` 同一套口径暴露 ——
            # 面板把两者分段显示：判据在上、建议在下。
            "issues": {k: v for k, v in (state.get("issues_by_stage") or {}).items() if v},
            # 产物落在哪、归档会叫什么名字。工具栏要显示它 —— 路径是用户选的，得能一眼看到。
            "delivery": _delivery_status(),
            # 「清理全部残留」按钮的显隐依据（只在整链跑完且还有残留时为真）
            "can_cleanup": _can_cleanup(),
            "retry_cap": dict(state.get("retry_cap") or {}),
            "attempts": dict(state.get("attempts") or {}),
            "log": list(state["log"])[-200:]}

# ---------------- 质量护栏清单（前端"质量护栏"面板；以后加护栏=在此加一行） ----------------
GUARDRAILS = [
    {"g": "门禁/审查", "items": [
        {"n": "建模门禁 4review", "d": "数学/题意/机理/数据 4 维独立子 agent 评审；两轮修复仍失败则挂起，缺失或冲突裁决不放行"},
        {"n": "结果审计 5Result-credibility-audit", "d": "拦泄漏(训练/测试)、小样本高 AUC 虚高、非识别点值当结论、可复现性抽查"},
        {"n": "跨问一致 10cross", "d": "全链符号/口径/数值自洽；抓论文与 code 矛盾"},
        {"n": "数学论证 10Math-proof-gate", "d": "成稿定理/命题/证明字样须带可复核等式推导+前提声明；禁仿真代证明；独立复推后 APPROVED / REVISE(回 write)；不自动重试，失败转黄灯由人决定"},
        {"n": "终验 15Verification", "d": "编译/结构/图表引用/文本门禁/数值溯源终检"},
        {"n": "评分终审 12Rubric-final", "d": "四份评委视角评分标（适配性15维/AI痕迹10维/合规红线26条/官方四大项16维）"
                                       "逐项打分，产出严重/中等/轻微三级判词；只报证伪不掉的项；"
                                       "只剩轻微项即放行，不必满分。带判词的正向出路：论文侧交 13Repair-by-rubric-verdict 就地改"},
        {"n": "按评分判词返修 13Repair-by-rubric-verdict", "d": "只做论文侧（措辞/结构/摘要/结论表述）。动手前逐条复核判词属实，"
                                      "不属实的记 not_reproduced 不动稿；评分标建议加的主观第一人称一律写成「本文」。"
                                      "模型/数值类判词不在这里改，回退各自生产阶段"},
    ]},
    {"g": "质量纪律", "items": [
        {"n": "诚实降级", "d": "不夸大结论；标签循环/依据不足如实写明，可执行交付并置(REVISE_CLAIM)"},
        {"n": "任务交付完备性", "d": "不因统计不显著/方差大/样本少回避题面要求的产出物；负结果转译成可执行策略"},
        {"n": "数学结构挖掘", "d": "进代码前先找单调/凸/可分/对偶结构；定理须被用到、防假定理"},
        {"n": "数学推理双层验证", "d": "独立反证复核(子 agent 找反例/重推) + 数值交叉探测(单调/凸/判据/上界抽查)，出反例即退回"},
        {"n": "经验结论对照 code 输出", "d": "write 不沿用建模前旧推测句；凡由算才知的结论先对 outputs 核实"},
        {"n": "写作用词规范", "d": "论文用学术语，禁 harness 术语泄漏(速查卡/审计/交付/口径等)，定稿自检"},
    ]},
    {"g": "工程能力", "items": [
        {"n": "非破坏暂存 cache", "d": "回退/打断前产物移入 cache/ 可恢复，不误删；断点续跑"},
        {"n": "看门狗判活", "d": "ctypes 查 EST/CPU 区分假死与长计算，300s 静默强杀重试"},
        {"n": "技术路线图 drawio", "d": "verify 后产出 fig_roadmap + 各问流程（paper-diagram 模板 + matplotlib 兜底）"},
        {"n": "交互落地 16Web-demo", "d": "PDF 定稿后产出可运行交互工具 + UI 截图入论文"},
        {"n": "全阶段计时", "d": "总耗时 + 每阶段耗时实时显示"},
    ]},
]

@app.get("/api/guardrails")
async def guardrails():
    return {"groups": GUARDRAILS}

class StartReq(BaseModel):
    stages: list[str] | None = None   # None=全链；或指定子集 id
    output_dir: str | None = None     # 产物路径；None/空/项目根 → <根>/产物/
    problem_id: str | None = None     # 题目标识，进 cache 归档目录名；空 → 只用日期
    # from_stage：**从哪个阶段起跑**（缺省 = ① 开始，靠回执逐级复用）。
    # 为什么要有它：不设起点时 `run_all` 的起点恒为 0，
    #   于是"从 ⑨ 重跑"实际是"从 ① 走一遍、靠回执跳过"—— 而**上游门禁会把它拦下来**：
    #   复用的门禁若裁决过期（`gate_result == "UNVERIFIED"`），`run_all` 会当场把它**真跑一遍**
    #   （见那里 `if verdict == "UNVERIFIED"` 那段）。上游那些问题不必再管
    #   （「回到 9 才对」），而"从所选阶段重跑"这个按钮的字面意思本来就是"从那里开始"。
    from_stage: str | None = None


def _set_start_index(i):
    """记下本轮**从第几个阶段起跑**（下标级）；返回该下标。**顺带丢掉"起点之前"那盏黄灯。**

    为什么顺手丢：链这一轮**不会**走到起点之前（起点已明确选在这里），留着那盏灯
      等于在面板上挂一个关于"链永远不去的那一步"的问题 —— 点它还回 409（`running=True`），
      看着像界面坏了（点「暂停→清空→从 ⑨ 重跑」后，⑤ 的 paused 黄灯会留在面板上）。
      只丢**起点之前**的：起点及其之后的黄灯照留 —— 链真的会走到它，那是真问题。
    """
    i = max(0, min(int(i or 0), len(STAGES)))
    # ⓪ 读题还没确认时，**不许从它后面起跑**（口径：「确认后才能跑」）。
    #   为什么必须拦：那时 `request/` 里还是**没定稿**的输入 —— 题面可能还是机械抽取那份、
    #   附件还堆在 `_inbox/` 里没各就各位。从 ① 起跑等于拿半成品开跑，而后面每一步都建在
    #   "题读对了"这个假设上，最后交付出去才发现附件不全/题意理解偏了 —— 那时候返工是小时级。
    #   只拦"从 ⓪ 之后起跑"：从 ⓪ 起跑（含上传后的自动起跑）正是**产生**那份确认的路径，
    #     拦了它这个功能就永远启动不了。确认过之后 `_intake_unconfirmed()` 自动为假 ⇒ 不拦。
    if i > STAGE_IDX["intake"] and _intake_unconfirmed():
        raise HTTPException(
            409, "这批上传的原件**还没确认读题结果**（`request/_inbox/` 里还有东西）——"
                 "请先在面板的 ⓪ 读题那盏灯上核对并点「✓ 确认并开始跑链」，"
                 "或者从 ⓪ 重跑让 AI 重读一遍。"
                 "现在从后面起跑，用的是没定稿的题面与还没各就各位的附件。")
    state["start_index"] = i
    if not i:
        return i
    p = state.get("pending") or {}
    psid = p.get("stage")
    if psid in STAGE_IDX and STAGE_IDX[psid] < i:
        log(f"↪️ 本次从「{STAGES[i]['name'] if i < len(STAGES) else '链尾'}」起跑 ⇒ "
            f"丢弃起点之前的黄灯（{STAGES[STAGE_IDX[psid]]['name']}）—— 这一轮不会走到那一步。")
        _set_pending(None)
        state["halt_gate"] = False
        state["halt_reason"] = ""
        state["stages"][psid] = "idle"
    return i


def _set_start_from(sid):
    """`_set_start_index` 的阶段名版本（`from_stage` 那条路用）。"""
    return _set_start_index(STAGE_IDX[sid] if sid else 0)


@app.post("/api/start")
async def start(req: StartReq):
    if state["running"]: raise HTTPException(400, "已在运行")
    # 「不归档删除本题」正在跑 ⇒ 别起链（见 `wipe_problem` 开头那段独占闸的说明）。
    #   300 秒自动失效：万一那次删除半路挂了没清掉标志，也不该把起链永久锁死。
    if time.time() - (state.get("wiping_at") or 0.0) < 300:
        raise HTTPException(409, "正在删除本题的产物 —— 等它跑完再起链")
    if req.stages is not None:
        raise HTTPException(400, "当前只支持全链运行；请使用阶段重跑接口选择续跑起点")
    if req.from_stage is not None and req.from_stage not in STAGE_IDX:
        raise HTTPException(400, f"未知阶段 {req.from_stage}")
    _set_start_from(req.from_stage)
    # 产物设置随本轮生效并落盘（下次打开页面还在）。
    if req.output_dir is not None or req.problem_id is not None:
        cfg = _delivery_config()
        pid = cfg["problem_id"] if req.problem_id is None else req.problem_id
        # 先校验题目标识再落盘：含 Windows 保留字符（例如
        #   `2026A:2026.9.18`）的标识一旦存进配置，之后每一次回退/清空都会 500 ——
        #   而黄灯那条路会因此在清掉面板之后才炸，连重试入口都没有。
        #   唯一会校验的 `POST /api/delivery` 前端从来不调，所以必须在这里挡。
        from lib.delivery.core import delivery_name
        try:
            delivery_name(pid)
        except ValueError as exc:
            raise HTTPException(400, f"题目标识不能这么写：{exc}")
        try:
            _save_delivery_config(cfg["output_dir"] if req.output_dir is None else req.output_dir,
                                  pid)
        except OSError as exc:
            raise HTTPException(400, f"产物设置写不进去：{exc}")
    # 全链重开才清「临时延长」与决策遗留。run_all 绝不清 retry_cap（见那里的注释）。
    state["retry_cap"] = {}
    state["seed_hints"] = {}
    state["attempts"] = {}
    state["force_retry"] = None
    state["running"] = True
    threading.Thread(target=lambda: asyncio.run(run_all()), daemon=True).start()
    return {"ok": True}

# 每阶段的产物（用于"从某阶段重跑"时清其后）
ARTIFACTS = {
    # ⓪ 读题的两个产物：人读的报告 + **机读的提案**。提案必须一起列进来 —— 否则
    #   `_output_digest` 管不住它（改了它回执照样算新鲜），而确认页读的正是它。
    "intake": ["reports/INTAKE_REPORT.md", "reports/INTAKE.json"],
    "literature": ["reports/LITERATURE_DIRECTION.md"],
    # 3analysis 有两个**以上**产物，别只列报告：题意契约与返修台账都是它写的，
    #   回退/清空时漏掉它们，新的一轮就会在旧契约/旧台账上开跑 ——
    #   台账尤其危险：旧台账答的是旧回执，新的一轮若没写台账，`check_receipts` 会拿
    #   旧的那份去核对，要么假通过、要么因为"答错回执"把全新的一轮当场挂起。
    "analysis": ["reports/ANALYSIS_MODELING_REPORT.md", "reports/TASK_CONTRACT.json",
                 "reports/RECEIPT_LEDGER.json"],
    "review": ["reports/MODELING_REVIEW_REPORT.md"],
    "code": ["reports/RESULTS_REPORT.md", "reports/FIGURE_PLAN.md", "code", "results"],
    # drawio 的产物是**非数据图**。这里列的是**归档提示**（_redo_from 暂存时用），
    # 不是穷举清单 —— 画了哪些图由题目决定（实测画过 fig_roadmap / fig_coupling /
    # fig_geometry / fig_mesh / fig_shrink_coord 这些名字；而 fig_flow_q1..q4、
    # fig_pipeline 这五个则从来不存在）。完整性由 figures/manifest.json 管。
    "drawio": ["reports/DRAWIO_REPORT.md"],
    "figreview": ["reports/FIGURE_REVIEW_REPORT.md"],
    "robustness": ["reports/ROBUSTNESS_REPORT.md"],
    "audit": ["reports/RESULT_AUDIT_REPORT.md"],
    # write/format 现在管**两个** LaTeX 工程：paper/（正文）与 paper_appendix/（附录A）。
    # 附录是独立编译的第二个 PDF，`A_code`/`\appendixBcn` 那条「源码排进论文」的路已按用户
    # 要求去掉（源码改以散装 .py 提交）。
    "write": ["paper", "paper_appendix"],
    # format 的产物是**整个 paper/**（导言区 + 各节版式 + 编译出的 PDF），
    # 回退/暂存时与 write 同样处理：整目录进 cache/。
    # 它还负责提交清单、正文末页的清单表、运行说明.md。
    "format": ["reports/FORMAT_REPORT.md", "paper", "paper_appendix",
               "reports/SUBMISSION_MANIFEST.json", "运行说明.md"],
    "mathproof": ["reports/MATH_PROOF_REPORT.md"],
    "cross": ["reports/CROSS_QUESTION_REVIEW.md"],
    "verify": ["reports/VERIFY_REPORT.md"],
    "rubric": ["reports/RUBRIC_REVIEW.md"],
    "fix": ["reports/FIX_REPORT.md", "reports/FIX_REPORT.json", "paper"],
    # demo 也写 `paper_appendix/`：把首屏截图安成附录第一页的图 A1 并重编
    # 附录A.pdf。这是本阶段唯一的"越界"产物（契约如此要求）；正文 `paper/` 仍然不碰。
    # ⑯ 是链尾阶段，没有下游会接管 `paper_appendix`，所以不必进 `_PAPER_OWNED_STAGES`。
    "demo": ["reports/DEMO_REPORT.md", "demo", "paper_appendix"],
}
STAGE_IDX = {s["id"]: i for i, s in enumerate(STAGES)}

# 产物里**含整份 `paper/`** 的非门禁阶段 ⇒ 它们会被后继阶段合法改写（⑭ 的版式手术落进
# `paper/_base/` 与 `paper/sections/*.tex`），产物指纹必然对自己的回执失配。
# `run_stage` 据此走「被下游接管」那条近路（判据见 `_taken_over_by`），而不是重做一遍。
# 加阶段时若它的 ARTIFACTS 里也有 `paper`，必须加进这里 —— 否则它会每轮被无谓重跑。
_PAPER_OWNED_STAGES = {"write", "fix"}

# ---------- 非破坏性暂存：回退/打断前把产物移入 cache/，绝不删除（可恢复） ----------
CACHE = ROOT / "cache"
DELIVERY_CFG = ROOT / "config" / "delivery.local.json"


def _delivery_config():
    """产物路径设置。读不到 / 字段缺失都用默认（空 → `<根>/产物/`）。"""
    try:
        value = json.loads(DELIVERY_CFG.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        value = {}
    if not isinstance(value, dict):
        value = {}
    return {"output_dir": str(value.get("output_dir") or "").strip(),
            "problem_id": str(value.get("problem_id") or "").strip()}


def _save_delivery_config(output_dir, problem_id):
    """存产物设置。**归一化在这一层做** —— 单一收口。

    为什么不让各调用方自己 `_store_output_dir`：写这份配置的路有**四条**
      （`POST /api/delivery`、`POST /api/start`、`POST /api/archive`、以及页面上的「选…」后随链保存），
      只在其中一条上归一化等于没做 —— 用户实际走的是 `/api/start` 那条。
      放错那一条的话，归一化等于没接到真正在用的落盘入口。
    """
    atomic_json(DELIVERY_CFG, {"output_dir": _store_output_dir(output_dir),
                              "problem_id": problem_id or ""})


def _store_output_dir(picked):
    """把用户**选/填**的产物目录归一化成要落盘的写法。

    为什么仓内存**相对**路径：`config/delivery.local.json` 是跟着仓库一起被拷走的
      （本仓无 git）—— 存绝对路径会让新机器把产物写到**旧机器**的路径去（或凭空新建一棵
      `C:\\Users\\...` 树）。落在仓内就存相对，跟着仓库走。
      `regression/test_local_decoupling.py::test_the_shipped_delivery_config_is_not_pinned_to_a_machine`
      就是为这条立的哨兵。
    仓外只能存绝对 —— 那是**显式**选的（`resolve_output_dir` 本来就允许产物落仓外，
      `regression/test_delivery.py` 钉着这条）。选仓外是合法用法，不是错误。
    选中的正好是仓库根 ⇒ 存空串：`resolve_output_dir` 对"等于 root"本来就回落 `<root>/产物`
      （`lib/delivery/core.py:107-119`），存相对串 `"."` 反而会让它在仓根**原地**归档。
    """
    s = str(picked or "").strip()
    if not s:
        return ""
    p = Path(s)
    if not p.is_absolute():
        p = ROOT / p
    try:
        p = p.resolve()
        rel = p.relative_to(ROOT.resolve())
    except (OSError, ValueError):
        return str(p)                      # 仓外（或解析不了）：只能存绝对
    rels = rel.as_posix()
    return "" if rels in (".", "") else rels


def _delivery_dir():
    from lib.delivery.core import resolve_output_dir
    return resolve_output_dir(ROOT, _delivery_config()["output_dir"])


def _cache_dir():
    """归档落点：`<选定目录>/cache/` —— 产物路径可改，cache 跟着走。

    用户的要求：「回退暂存放入选定文件夹里新建的 cache，按时间命名一个文件夹放进去」。
    默认产物目录是 `<项目根>/产物/`，所以默认落点是 `<项目根>/产物/cache/`。
    """
    return _delivery_dir() / "cache"


def _recorded_problem_id():
    """`workspace.json` 里记着的「**当前这道题**」的标识 —— 两个「最新」指针里装的就是它的产物。

    归档（手动 `/api/archive` 或自动换题）**必须**用它命名，不能用面板的当前配置：
      面板那个框描述的是「**接下来**要跑的题」，而归档的是「**已经**跑完的那道题」——
      换题那一刻两者正好不同。弄错的形态：面板把 2026A 改成 2026B 再点「📦 归档本题并换新」
      ⇒ **2026A 的提交件被盖上 2026B 的名字**；反过来，换到 B 题后自动轮转又拿记录值
      把 **B 题的提交件** 归成 2026A。同一件事两个入口两套口径，两次都贴错标签。

    读不到（首次运行、或升级前写的旧文件没有该字段）就退到面板配置 —— 再没有才给空串
    （`delivery_name("")` 只用时间戳），这样第一次轮转也**不会**把题目标识丢掉。
    """
    try:
        prev = json.loads((LOG_DIR / "quality" / "workspace.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        prev = {}
    if isinstance(prev, dict) and str(prev.get("problem_id") or "").strip():
        return str(prev["problem_id"]).strip()
    return _delivery_config()["problem_id"]


def _submission_dir():
    """**提交件根**：`<产物根>/提交作品/最新作品/` —— `package` / `check` 的对象。

    与 `_delivery_dir()`（产物根）的分工要一直分清：产物根下面还有 `cache/`、
      `各阶段产物/`、`其他产物/` 三个**不是提交件**的目录，而 `checks.py` 的白名单
      只看传入目录那一层 ⇒ 传产物根进去必然 FAIL（23 条，前三条还叫 agent
      把 `各阶段产物` 挪进 `其余文件/`）。
    """
    from lib.delivery.core import resolve_submission_dir
    return resolve_submission_dir(ROOT, _delivery_config()["output_dir"])


def _stage_dir():
    """**阶段快照根**：`<产物根>/各阶段产物/最新产物/` —— 每阶段跑完往里镜像一份。"""
    from lib.delivery.core import resolve_stage_dir
    return resolve_stage_dir(ROOT, _delivery_config()["output_dir"])


def _delivery_status():
    """前端工具栏显示用：产物落在哪、归档会叫什么名字。"""
    from lib.delivery.core import delivery_name, resolve_output_dir
    cfg = _delivery_config()
    out = resolve_output_dir(ROOT, cfg["output_dir"])
    try:
        # 面板显示的「下一个归档名」必须与**实际会用的**一致（见 _recorded_problem_id）
        name, error = delivery_name(_recorded_problem_id()), ""
    except ValueError as exc:
        name, error = "", str(exc)
    sub, stg = _submission_dir(), _stage_dir()
    # `output_dir` 给**配置原值**（可能为空串）、解析后的绝对路径另放 `resolved` ——
    #   与 `GET /api/delivery` 口径一致。给解析值的话，前端 `fillDelivery` 同时被
    #   `/api/delivery`（原值）与 `/api/state`（解析值）喂 ⇒ 每次 SSE 推事件与 4s 轮询都把
    #   用户刚填进「产物路径」框的内容冲成已保存的绝对路径，「留空 = 用默认」在界面上消失。
    # `*_exists` 看**有没有东西**、不是「目录在不在」：轮转为了保证结构立即可见会无条件
    #   建回两个**空**指针，只看 is_dir() 会让面板对一个空提交件报绿灯。
    return {"output_dir": cfg["output_dir"], "resolved": str(out),
            "problem_id": cfg["problem_id"],
            "archive_name": name, "error": error, "exists": out.is_dir(),
            # 两个「最新」指针的落点（换题时的归档就是把这俩整目录改名）。
            "submission_dir": str(sub), "stage_dir": str(stg),
            "submission_exists": sub.is_dir() and any(sub.iterdir()),
            "stage_exists": stg.is_dir() and any(stg.iterdir()),
            # 项目根：前端据此把路径显示成相对形式，项目内一眼看得懂、项目外才显示全路径。
            "root": str(ROOT)}


class RotationBlocked(Exception):
    """换题/手动归档做不下去（指针目录被占用等）。

    抛出即**中止本轮**，且此时工作区原件一件未动、已改的指针名已回滚 ——
    「要么整份归档、要么原地不动」，不留半改半没的中间态。
    """


def _rotate_pointers(reason, problem_id):
    """把两个「最新」指针整目录改名成 `<题目标识_日期_时间>/`，再建两个空的。

    与 `package()` 的分工：**轮转管指针目录这个名字，`package()` 管指针目录里面的内容。**
      `package()` 只在自己的 `out.parent` 里造 `.{name}.building-<uuid8>` / `.{name}.old-<uuid8>`
      然后换 `out` 自己，从不碰兄弟目录；轮转只 rename 整个指针、从不进它的内容。
      两者时间上也是互斥的：轮转只发生在 `_prepare_workspace`（每轮开头，还没打包）
      或 `/api/archive`（该端点在 `state["running"]` 时 409）。

    为什么不再"把产物整包切进 cache"：那个语义在新结构下是错的
      —— 会把 `cache/`、两个指针、`其他产物/` 一起端进 cache（而且它那道「cache 在产物目录里
      就跳过」的自守卫在默认布局下恒为真，这个按钮本来就是空转的）。

    返回 `{"name": 归档名, "rotated": [被改名的目录…]}`；`name` 也用作 cache 里
    「工作区原件」的子目录名，于是三处同名、一眼对得上。
    """
    from lib.delivery.core import (STAGES_PARENT, STAGES_POINTER, SUBMISSION_PARENT,
                               SUBMISSION_POINTER, delivery_name, rotate_pointer,
                               unique_boundary_name)
    root = _delivery_dir()
    pairs = [(root / SUBMISSION_PARENT / SUBMISSION_POINTER, root / SUBMISSION_PARENT),
             (root / STAGES_PARENT / STAGES_POINTER, root / STAGES_PARENT)]

    try:
        name = delivery_name(problem_id)
    except ValueError:
        # 题目标识带 Windows 保留字符 → 退到只用时间。不因为一个名字挡住整个归档。
        name = delivery_name("")
    # 撞名要查**三个**地方：两个指针的 parent，**以及 `cache/`** —— 同一个 name
    #   既当 `提交作品/<name>/`、`各阶段产物/<name>/`，也当 `cache/<name>/`（工作区原件
    #   与返修回执落在它下面）。只查前两个的话，同一秒内连续两次换题会拿到同名，
    #   于是 `工作区原件/reports` 已存在 → 移动撞名失败 → 整批搬不走。
    try:
        name = unique_boundary_name([parent for _, parent in pairs] + [_cache_dir()], name)
    except ValueError as exc:
        raise RotationBlocked(str(exc)) from exc

    # ① 先探测可写性 —— 把「改到一半才发现搬不动」的窗口压到最小。
    #   每一步的 OSError 都要收敛成 RotationBlocked：放它裸逃出去，
    #   /api/archive 会变成 HTTP 500、run_all 会把它记成「驱动异常」，都不是这条路的语义。
    for _, parent in pairs:
        try:
            parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise RotationBlocked(f"建不出 {parent}（{exc}）") from exc
        probe = parent / f".rotate-probe-{uuid.uuid4().hex[:8]}"
        try:
            probe.write_text("", encoding="utf-8")
            probe.unlink()
        except OSError as exc:
            raise RotationBlocked(
                f"{parent} 不可写（{exc}）—— 关掉占用它的程序后重试") from exc

    # ②′ 处理 `package()` 崩溃留下的中间件：
    #   · `.<指针名>.old-<uuid8>` —— `package()` 在两次 rename 之间被杀留下的**完整**上一份包。
    #     认它、当作待归档对象，崩一次也自愈。**挑最新那份**：多份残留说明崩过多次，
    #     旧的那份内容更旧（取 `sorted()[0]` = 最旧的一份，可能把很旧的包当成本轮边界，
    #     而更新的那份永远躺在隐藏目录里没人看得见）。其余留着不删，但在日志里点名。
    #   · `.<指针名>.building-<uuid8>` —— 还在建的**半成品**，永远没人收，直接清掉。
    orphaned = {}          # parent → [没位置可归的残留]，② 之后一并交给归档
    for pointer, parent in pairs:
        for junk in sorted(parent.glob(f".{pointer.name}.building-*")):
            try:
                _remove_path(junk)
                log(f"🧹 清掉上次打包中断留下的半成品：{junk.name}")
            except OSError:
                pass
        try:
            leftovers = [p for p in sorted(parent.glob(f".{pointer.name}.old-*"),
                                            key=lambda p: p.stat().st_mtime, reverse=True)
                         if p.is_dir()]      # 只收编**目录**：残留若是文件，rename 上去会把
        except OSError:                       # 指针路径变成文件，后面 mkdir 就抛 FileExistsError
            leftovers = []
        if len(leftovers) > 1:
            log(f"⚠️ {parent.name}/ 下有 {len(leftovers)} 份打包残留，收编最新的那份，"
                f"其余留着：{', '.join(p.name for p in leftovers[1:])}")
        if leftovers and pointer.exists():
            # 指针还在（说明没崩在两次 rename 之间）⇒ 这份残留**没有位置可归**。
            #   直接 `continue` 的话 ⇒ 它永久留在盘上、连一行日志都没有，而 dot 目录
            #   面板看不见。现在把它交给本轮归档，看得见、有日期、可恢复。
            orphaned.setdefault(id(parent), []).append(leftovers[0])
        elif leftovers:
            try:
                leftovers[0].rename(pointer)
            except OSError as exc:
                raise RotationBlocked(f"收编打包残留失败（{leftovers[0].name}）：{exc}") from exc
            log(f"↩️ 收编上次打包中断留下的残留 → {pointer.name}")

    # ② 逐个改名；任一失败就**把已改的改回来**，不留半截状态。
    done = []
    orphaned_moved = []
    orphaned_moved_paths = []
    try:
        for pointer, parent in pairs:
            dest = rotate_pointer(pointer, parent, name)
            if dest is not None:
                done.append((pointer, dest))
            # 把没位置可归的残留一并交给本轮归档（见上面 `orphaned` 那段）
            for extra in orphaned.get(id(parent), []):
                try:
                    bucket = (dest if dest is not None else (parent / name))
                    # 记下「这个 bucket 是刚建的」—— 回滚时要把它一起收掉，
                    #   否则失败会留下一个空的归档目录。
                    made_bucket = (dest is None and not bucket.exists())
                    bucket.mkdir(parents=True, exist_ok=True)
                    tgt = bucket / ("旧残留-" + extra.name.lstrip("."))
                    extra.rename(tgt)
                    orphaned_moved.append((tgt, extra, bucket if made_bucket else None))
                    orphaned_moved_paths.append(str(tgt))
                    log(f"📦 顺带收走一份没位置可归的打包残留 → {tgt.name}")
                except OSError as exc:
                    log(f"⚠️ 打包残留 {extra.name} 搬不走（{exc}）—— 它仍在原地")
    except Exception as exc:
        for tgt, extra, made in reversed(orphaned_moved):   # 残留也要跟着回滚，不留半截状态
            try:
                if tgt.exists() and not extra.exists():
                    tgt.rename(extra)
                if made is not None:                        # 顺带收掉刚建的空 bucket
                    try:
                        made.rmdir()
                    except OSError:
                        pass
            except OSError:
                log(f"⚠️ 残留回滚失败：{tgt} → {extra}（请手工改回）")
        for pointer, dest in reversed(done):
            try:
                if dest.is_dir() and not pointer.exists():
                    dest.rename(pointer)
            except OSError:
                log(f"⚠️ 轮转回滚失败：{dest} → {pointer}（请手工改回）")
        raise RotationBlocked(str(exc)) from exc

    # ③ 建回两个空指针：结构立即可见，且下一轮的产物有地方落。
    for pointer, _ in pairs:
        try:
            pointer.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise RotationBlocked(f"建不回空指针 {pointer}（{exc}）："                                   f"已归档的 {name}/ 不受影响") from exc

    detail = "、".join(d.name for _, d in done) or "两个指针都是空的，只建了骨架"
    log(f"📦 {reason}：归档 → {name}/（{detail}）")
    return {"name": name, "rotated": [str(d) for _, d in done],
            "orphaned": orphaned_moved_paths}


# ---------------- 各阶段产物：每阶段跑完镜像一份 ----------------
#
# 落点 `<产物根>/各阶段产物/最新产物/<中文阶段名>/`，供人按阶段翻账。
# 换题时整个「最新产物」被 `_rotate_pointers` 改名归档 —— 所以这里只管往里写。

def _stage_rels(sid, *, figure_only=False, own_only=False):
    """该阶段该有的产物相对路径。**单一事实来源** —— 回退暂存与阶段镜像共用这一份。

    依据是 `ARTIFACTS`，而它自己的注释就写着「这是归档提示、**不是穷举清单**」——
      `figures/` 一个阶段都没列（完整性由 `figures/manifest.json` 管）。所以图**不走这张表**，
      由 `_figure_paths_changed()` 从登记表差分里现算。

    `own_only=True`（**回退暂存**用）：**只留"本阶段是它的第一声明者"的那些路径**。

      为什么必须有它：`paper/` 同时被 ⑨ 论文撰写
      （第一声明者 = 它的产物）、⑬ 按评分判词返修、⑭ 排版与版式 三处声明 —— 因为后两者
      都要**就地改**论文。于是「从 ⑫ 评分标终审 重跑」时，`_redo_from` 把 ⑪..⑮ 的声明
      统统暂存，**`paper/` 与 `paper_appendix/` 被整目录搬进 cache** ⇒ ⑫ 的审查对象没了、
      面板上"论文不见了"（cache 里会躺着 51 个 paper 文件 + 29 个附录文件）。

      语义上也该如此：⑬⑭ 是「读着现有论文再改」的阶段，它们的重跑**不需要**旧论文先消失
      （产物"是不是新的一版"由 `run_stage` 的完成标记负责，`paper/main.pdf` 在它那儿）。
      而 ⑨ 重跑时 `paper/` 仍会被搬走 —— 它是第一声明者。

    只对**暂存**开这个开关，**镜像**（展示区）仍按原样：⑭ 那一格本来就该看到论文。
    """
    if figure_only and sid == "code":
        return []
    rels = list(ARTIFACTS.get(sid, []))
    stage = next((s for s in STAGES if s["id"] == sid), None)
    if stage and stage.get("gate"):
        rels += [r[:-3] + ".verdict.json" for r in rels if r.startswith("reports/")]
    if own_only:
        me = next((i for i, s in enumerate(STAGES) if s["id"] == sid), None)
        first = {}
        for i, s in enumerate(STAGES):
            for rel in ARTIFACTS.get(s["id"], []):
                first.setdefault(rel, i)
        rels = [r for r in rels if me is None or first.get(r, me) >= me]
    return rels


def _figure_index():
    """`{图语义键: 该条登记的内容签名}`；读不到就 None（放弃图这一路，只记一行日志）。"""
    from lib.visualization.evidence import load, signature
    try:
        return {k: signature(v) for k, v in (load(ROOT).get("figures") or {}).items()}
    except Exception:
        return None


def _read_snapshot(dest):
    """读该阶段上一轮的 `.snapshot.json`；没有或坏了 → `{}`。"""
    try:
        data = json.loads((dest / ".snapshot.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _figure_paths_changed(before):
    """阶段跑前/跑后比图登记表：**新增或内容变了的**图 → `(文件相对路径, 图键)`。

    为什么不用一张手维护的「阶段 → 图」映射：`ARTIFACTS` 里 `figures/` 无人认领，
      而图的真正归属由**登记表自己**记着（每条有 `script`）。差分因此自动覆盖
      ④（数据图 `figures/make_figures.py`）、⑦（`make_flow_figures.py` + `fig_roadmap`）、
      ⑥（若画了稳健性图）—— 不需要事先知道脚本叫什么，也不会因为换张图就漏。
      `before is None`（登记表读不到）⇒ 返回空，宁可少镜像也不瞎猜。
    """
    after = _figure_index()
    if before is None or after is None:
        return [], []
    keys = sorted(k for k, sig in after.items() if before.get(k) != sig)
    return _figure_rels_for(keys), keys


_FIGURE_ATTR = ROOT / "runtime" / "quality" / "figure_attribution.json"


def _figure_attr_path():
    """阶段↔图 归属表的落点：`runtime/quality/figure_attribution.json`。

    为什么不放在快照目录里：`.snapshot.json` 住在
      `产物/各阶段产物/最新产物/<阶段>/`，而**换题归档**与**回退**都会把这个目录整份搬走 ⇒
      归属随之丢失 ⇒ 纯复用的一轮里，那个阶段的图**整批不进展示区**，而且盘上没有任何
      标记说明漏了图（`missing: []` + `complete: true` 读起来像"这一阶段本来就没有图"）。
      `runtime/` 这两条路都不动它 ✓。
    """
    return _FIGURE_ATTR


def _load_figure_attr():
    try:
        data = json.loads(_figure_attr_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _save_figure_attr(data):
    try:
        _figure_attr_path().parent.mkdir(parents=True, exist_ok=True)
        atomic_json(_figure_attr_path(), data)
    except OSError as exc:              # 展示区，绝不拖垮本轮
        log(f"⚠️ 阶段↔图 归属表写不进去（不影响本轮）：{exc}")


def _figure_rels_for(keys):
    """给定图键 → 它名下**当前在盘上**的所有文件 + 它的脚本。

    登记表每条自己的 `artifacts`/`sources` **与** `glob(key.*)` 一起用：
      只按 key 前缀 glob 会漏掉**文件名与 key 不同名**（或只差大小写）的图 ——
      登记表才是权威。
    """
    from lib.visualization.evidence import load
    try:
        figs = load(ROOT).get("figures") or {}
    except Exception:
        return []
    rels, seen = [], set()
    for key in keys:
        entry = figs.get(key) or {}
        cands = [str(a) for a in (entry.get("artifacts") or [])]
        cands += [str(s) for s in (entry.get("sources") or [])]
        cands.append(str(entry.get("script") or ""))
        try:
            cands += [p.relative_to(ROOT).as_posix()
                      for p in sorted((ROOT / "figures").glob(f"{key}.*"))]
        except OSError:
            pass
        for rel in cands:
            if rel and rel not in seen and (ROOT / rel).exists():
                seen.add(rel)
                rels.append(rel)
    return rels


_CONTENT_COMPARE_MAX = 1 << 20          # ≤1 MiB 的文件直接比内容


def _copy_if_changed(src, dst):
    """没变就跳过；变了才覆盖（`copy2` 保留 mtime）。

    小文件**比内容**、大文件比 `(size, mtime_ns)`：后者会在
      「内容变了、但大小与 mtime 恰好相同」时漏更新（脚本刻意回写 mtime、或同一秒内
      两次写同样长度），而展示区漏更新的代价是**你以为看到的是这一轮的**。
      报告与脚本都在 1 MiB 以内，比内容是廉价的；大文件（`code/outputs/*.npz` 那种）
      仍走 size+mtime —— 哈希一遍的 IO 成本≈复制一遍，省不下来。
    """
    if dst.is_file():
        s, d = src.stat(), dst.stat()
        if s.st_size == d.st_size:
            if s.st_size > _CONTENT_COMPARE_MAX:
                if s.st_mtime_ns == d.st_mtime_ns:
                    return False
            elif src.read_bytes() == dst.read_bytes():
                return False
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return True


def _is_reparse_point(p):
    """是不是「会把你带到别处去」的重解析点（符号链接 / 目录联结点 / 装入点）。

    `Path.is_symlink()` **抓不住 Windows 目录联结点**（联结点的
      `is_symlink()` 返回 **False**，而 `st_reparse_tag` 是 0xA0000003）。靠它就是错的：守卫
      那样做，联结点会被 `_walk_tree` 跟进去，把**外部目录整份拷进产物树**。
      改用 reparse 属性位 —— 它对符号链接、联结点、装入点一视同仁。
    """
    try:
        st = os.lstat(p)
    except OSError:
        return False
    return bool(getattr(st, "st_file_attributes", 0)
                & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0))


def _walk_tree(src, root):
    """遍历 `src`（**不跟随符号链接/联结点**），依次产出 `(路径, 工作区相对路径)`。

    必须自己走、不能用 `Path.rglob`：`rglob` 会**跟进联结点** ——
      自指的联结点让它抛错、把整次镜像半途作废；指向外部的会把**外部内容整份拷进
      产物树**。判据是 reparse 属性位（`_is_reparse_point`）：`is_symlink()` **抓不住**
      Windows 目录联结点（返回 False），只有属性位对符号链接与联结点一视同仁。
    """
    if _is_reparse_point(src):
        # 根也要查：`src` 本身若是联结点（例如把 `figures/`
        #   变成一个指向别处的联结点），只查子项的话 ⇒ 它会被整个跟进/整体跳过，
        #   两种后果都不对。这里直接**不看**它，由调用方按「源里没东西」处理。
        return
    stack = [src]
    while stack:
        cur = stack.pop()
        try:
            children = sorted(cur.iterdir(), key=lambda p: p.name)
        except OSError:
            continue
        for p in children:
            if "__pycache__" in p.parts or _is_reparse_point(p):
                continue
            yield p, p.relative_to(root).as_posix()
            if p.is_dir():
                stack.append(p)


def _remove_path(p):
    """删一个文件/目录（目录容忍非空）。**调用方负责兜异常。**"""
    if p.is_dir():
        shutil.rmtree(p, ignore_errors=True)
    elif p.exists():
        p.unlink(missing_ok=True)


def _mirror_paths(rels, dest, *, extra_delete=()):
    """把 `ROOT/<rel>` **增量镜像**到 `dest/<rel>`（保留工作区相对结构）。返回失败清单。

    幂等 = **对齐**，不是累加：源里有的更新/新增，源里没有的在目标里删掉。
      累加会让上轮画过、这轮不画的图继续挂着 —— 看起来像现在的产物，
      正撞「不冒充本轮成功」那条纪律。`extra_delete` 是「上一轮镜像过、这一轮不在
      集合里」的那些（图会改名/退役，光靠逐 rel 对齐盖不到它们）。
    目录**保留工作区相对结构**（`编码计算/code/outputs/…`），与 cache 用基名的约定
      **故意不同**：展示区要能直接跟 `reports/RESULTS_REPORT.md` 这类路径对上、
      能跨阶段同名对比（`论文撰写/paper/` vs `排版与版式/paper/`）。
    不用 `package()` 那套 staging+swap：`code/`(108M)+`results/`(34M) 全量拷一次 142M，
      而重跑与收尾复验很常见；增量让第二次近乎为零。
    **每一步都兜异常**：一个被占用的文件不该让整次镜像半途作废 ——
      否则盘上留着上一轮的 `.snapshot.json` 继续自称 `complete: true`，比明说"没做全"更糟。
    """
    failed = []

    def _try(what, fn):
        try:
            fn()
        except OSError as exc:
            failed.append(f"{what}（{exc.__class__.__name__}）")

    for rel in dict.fromkeys(extra_delete):
        _try(f"清旧 {rel}", lambda r=rel: _remove_path(dest / r))

    for rel in dict.fromkeys(rels):
        src, tgt = ROOT / rel, dest / rel
        if not src.exists():
            # 源没了 → 目标里那份也删掉（对齐）。回退把源搬走是常态。
            _try(f"删旧 {rel}", lambda t=tgt: _remove_path(t))
            continue
        if not src.is_dir():
            _try(rel, lambda s=src, t=tgt: _copy_if_changed(s, t))
            continue
        wanted = set()
        for p, r in _walk_tree(src, ROOT):
            wanted.add(r)
            if p.is_dir():
                _try(r, lambda d=dest / r: d.mkdir(parents=True, exist_ok=True))
            else:
                # 单文件被占（Acrobat/Excel 开着报告是常态）→ 跳过继续，不拖垮整批
                _try(r, lambda s=p, t=dest / r: _copy_if_changed(s, t))
        if not tgt.is_dir():
            continue
        # 对齐：目标里多出来的（源已不产出的）删掉
        def _prune(t=tgt, w=wanted):
            # 用 `_walk_tree`（**不跟随符号链接/联结点**）而不是 `t.rglob`：
            #   `rglob` 会**跟进联结点** —— 镜像区里若有一个指向工作区外的联结点，
            #   这一趟「对齐删除」就会去删**工作区外**的文件（这正是把拷贝那趟
            #   守卫换掉时漏掉的另一半：只换了拷贝，没换删除）。深的先删靠相对路径排序保证。
            for p, rel_p in sorted(_walk_tree(t, dest), key=lambda x: x[1], reverse=True):
                if "__pycache__" in p.parts:
                    continue
                # 相对 **`dest`** 算（不是 ROOT）：`p` 在目标目录下，而 `wanted` 是
                #   工作区相对路径 —— 拿 ROOT 去算会得到 `产物/各阶段产物/…/code/x`，
                #   与 `wanted` 里的 `code/x` 对不上 ⇒ **刚镜像过去的文件被自己删光**
                #   （`_mirror_paths` 之后目标里只剩空目录，就是这么来的）。
                if rel_p in w:
                    continue
                # 逐条兜异常：一个被占用的旧文件不该让**其余**的对齐删除全被跳过
                try:
                    if p.is_file():
                        p.unlink(missing_ok=True)
                    elif p.is_dir():
                        try:
                            p.rmdir()
                        except OSError:
                            pass            # 还非空（有没删掉的）→ 留着，下轮再说
                except OSError as exc:
                    failed.append(f"{rel_p}（删不掉 {exc.__class__.__name__}）")
        _try(f"清理 {rel}", _prune)
    return failed


def _snapshot_stage(stage, fig_before=None):
    """把该阶段的产物镜像一份进 `各阶段产物/最新产物/<中文阶段名>/`。

    **绝不抛**：展示区不是交付件，它的失败不该让小时级的链停下来
      （与 `_write_revision_diff` 同一范式）。失败如实记进 `.snapshot.json` 的
      `complete: false` + `failed`/`missing` 清单 —— 比一个看起来完整实则半旧的目录诚实。

    `.snapshot.json` **先写一份 `complete: false`**、跑完再改成终值：
      否则镜像中途崩掉时，盘上留着的是**上一轮**那份 `complete: true`，读起来像这一轮
      做全了。（同一处也钉住 `complete` 的判据：`failed` 为空**且** `missing` 为空 ——
      清单里声明了却不在盘上的产物若被按存在性过滤掉，标记照样会报 true。）

    图那一侧靠**记录键**对齐：`.snapshot.json` 里记着这个阶段名下
      有哪些图键；下一轮即便被复用跳过（差分为空），也照记录把它们的**当前文件**再镜像
      一次（#21 的回填），而登记表里已经消失的键、以及上一轮镜像过而这一轮不在集合里的
      图文件，会被删掉（#16/#17/#20 的对齐）—— 否则“幂等=对齐”这句话对 `figures/`
      根本不成立。
    """
    try:
        sid = stage["id"]
        declared = list(dict.fromkeys(_stage_rels(sid)))
        missing = [r for r in declared if not (ROOT / r).exists()]
        present = [r for r in declared if (ROOT / r).exists()]
        name = str(stage.get("name") or sid).strip()
        if not name or any(c in name for c in '\\/:*?"<>|'):
            name = sid                              # 防御性：展示名不该带保留字符
        dest = _stage_dir() / name
        prev = _read_snapshot(dest)

        fig_rels, new_keys = _figure_paths_changed(fig_before)
        registry = _figure_index()
        # 归属的**权威**放在 `runtime/` 下、**不随快照被搬走**（见
        #   `_figure_attr_path`）：`.snapshot.json` 里的那份会被**归档/回退**整目录搬走 ⇒
        #   纯复用的一轮里该阶段的图整批不进展示区，而盘上没有任何标记说明漏了图。
        attr = _load_figure_attr()
        known = set(attr.get(sid) or []) | set(prev.get("figure_keys") or [])
        if registry is None:
            # 登记表读不到 ⇒ 只保留已知的键（宁可少动，也别把好图删了）
            keys = sorted(known)
        else:
            keys = sorted((known | set(new_keys)) & set(registry))
        attr[sid] = keys
        _save_figure_attr(attr)
        fig_rels = _figure_rels_for(keys)
        prev_rels = set(prev.get("figure_rels") or []) | set(_figure_rels_for(sorted(known - set(keys))))
        stale_figs = [r for r in prev_rels if r not in set(fig_rels)]

        rels = list(dict.fromkeys(present + [r for r in fig_rels if (ROOT / r).exists()]))
        if not rels and not stale_figs:
            # 一条都不在盘上 → **不建目录**（与 `_stash_paths`「不预建空目录」同一纪律：
            # 一次回退建 12 个空文件夹，从里面反而看不出哪几步真有内容）。
            return None

        stamp = {"stage": sid, "name": name,
                 "at": datetime.now().isoformat(timespec="seconds")}
        # 第一次写失败时，盘上留着的是**上一轮**那份（可能是 `complete: true`）——
        #   读起来像这一轮做全了。所以写失败就把它删掉：**没有标记**比一个说谎的标记诚实。
        try:
            atomic_json(dest / ".snapshot.json",
                        {**stamp, "complete": False, "rels": rels,
                         "figure_keys": keys, "figure_rels": fig_rels,
                         "failed": [], "missing": []})
        except OSError as exc:
            try:
                (dest / ".snapshot.json").unlink(missing_ok=True)
            except OSError:
                pass
            log(f"⚠️ [{sid}] 阶段快照的标记写不进去（{exc}）—— 已删掉旧标记，免得它冒充本轮")
            return None
        failed = _mirror_paths(rels, dest, extra_delete=stale_figs)
        # `complete` 只看**镜像本身**有没有失败；`missing`（清单里声明了却不在盘上）
        #   如实记进同一个文件、**不**翻 complete —— 因为 `ARTIFACTS` 自己写着
        #   「这是归档提示、不是穷举清单」（`analysis` 的 TASK_CONTRACT/RECEIPT_LEDGER
        #   本来就是条件性的），拿它当"该到齐"的判据会天天误报。要判「齐没齐」的读者
        #   直接看 `missing` 字段。
        atomic_json(dest / ".snapshot.json", {
            **stamp, "complete": not failed, "failed": failed,
            "missing": missing, "rels": rels, "figure_keys": keys, "figure_rels": fig_rels})
        if failed or missing:
            log(f"⚠️ [{sid}] 阶段快照不完整（不影响本轮）："
                f"镜像失败 {len(failed)} 项、清单里缺 {len(missing)} 项"
                + (f"；例：{'; '.join((failed + missing)[:3])}" if (failed or missing) else ""))
        return dest
    except Exception as exc:                        # noqa: BLE001 —— 展示区，绝不拖垮本轮
        log(f"⚠️ [{stage.get('id')}] 阶段快照失败（不影响本轮）：{exc}")
        return None


def _move_or_copy(src, dst):
    """把 `src` 搬到 `dst`：同盘 `rename`；**只有真跨盘**才退到「先拷临时名 → 原子改名 → 删源」。

    为什么不能 `except OSError` 一律退复制（那是一条**永久删数据**的缺陷）：
      Windows 上目录里有文件被别的进程开着时，整目录 `rename` 会以 `WinError 5`
      （`errno 13`）失败 —— 那是**被占用**，不是跨盘。旧写法一律退复制：`copytree` 读
      被占文件是允许的、能成功；`rmtree(源)` 走到被占文件才抛错；外层再把**完整的副本**
      清掉 ⇒ 源里除被占文件外的文件全没了、归档一份没建成。
      现在：占用类错误**原样上抛**（由调用方跳过它继续搬其余的），只有 `errno 18` /
      `winerror 17` 才走复制。
    """
    from lib.delivery.core import is_cross_device_error
    try:
        src.rename(dst)
        return
    except OSError as exc:
        if not is_cross_device_error(exc):
            raise
    tmp = dst.with_name(f".{dst.name}.copying-{uuid.uuid4().hex[:8]}")
    try:
        if src.is_dir():
            shutil.copytree(src, tmp)
        else:
            shutil.copy2(src, tmp)
        tmp.rename(dst)
    except Exception:
        if tmp.is_dir():
            shutil.rmtree(tmp, ignore_errors=True)
        else:
            tmp.unlink(missing_ok=True)
        raise
    try:
        shutil.rmtree(src) if src.is_dir() else src.unlink()
    except OSError:
        pass          # 源删不干净 → 留着残源，绝不动已经落好的那一份


_PENDING_MARKERS = ROOT / "runtime" / "quality" / "_pending_markers"


def _has_content(p):
    """这个路径里**有没有真东西**？空目录算「没有」。

    `reports/` 在模块加载时就被建出来了（`REPORTS.mkdir`），所以首跑时它是个空目录 ——
    把它当「工作区原件」搬进 cache 只会留下 `cache/<名>/工作区原件/reports/` 这种空壳
    （看到过这种空壳），也违反「不预建空目录」那条纪律。
    """
    p = Path(p)
    return p.is_file() or (p.is_dir() and any(p.iterdir()))


def _stash_markers_for_restore(sid, markers):
    """把「完成标记 + 报告本体」搬到一个**固定、可原路搬回**的暂存位。

    与 `_stash_paths` 的区别只有一个，但很关键：落点固定、**能搬回来**。

    为什么需要它（「诡异重跑」的成因）：`run_stage` 在**开跑前**把
      markers 搬走，本意是「防半成品冒充完成」（`test_noop_cannot_reuse_old_completion_marker`
      钉着这条）。但它把**报告本体**也搬了，而落点是 `cache/<ts>_reports_*.md` 这种
      一次性名字、没人会去搬回。于是：**阶段被打断（暂停/强杀）⇒ 上一份完好的报告
      永远躺在 cache 里**，而所有下游回执的 artifacts 半份随即失配 ⇒ 整链从 ① 重跑。
      形态：③ 被暂停三次 ⇒ 三份 `MODELING_REVIEW_REPORT.md`（连同侧车）全进
      `cache/20260925_00*_...`，④–⑯ 全部被判「要重跑」—— 而实际只是按了一下暂停。

    返回一个 callable：`f()` = 把还没被重新产出的那些**搬回原位**；
    `f(drop=True)` = 丢弃副本（本轮已产出新产物 ⇒ 旧副本作废）。
    """
    dest = _PENDING_MARKERS / sid
    dest.mkdir(parents=True, exist_ok=True)
    mapping = []
    for rel in dict.fromkeys(markers):
        src = ROOT / rel
        tgt = dest / rel.replace("/", "_").replace("\\", "_")
        if tgt.exists():          # 前一次尝试已经搬过 ⇒ 别覆盖（多尝试要累积，不能只剩最后一次）
            continue
        if not src.exists():
            continue
        try:
            _move_or_copy(src, tgt)
        except OSError:
            continue
        mapping.append((tgt, src))

    def _restore(drop=False, force=False):
        """`drop=True` = 丢弃副本（本轮**真的**产出了新产物 ⇒ 旧副本作废）。
        `force=True` = **覆盖**盘上那份半成品。

        `force` 解决的是这个问题：只用 `and not src.exists()` 是"别覆盖本阶段
          已经写出来的东西"，在**半成品**（门禁按 §6.1 先落的骨架）面前正好帮倒忙：
          骨架「存在」⇒ 旧那份完好的报告搬不回来。⑮验收 的 26 KB 报告被 562 字节
          的骨架顶掉，按一次暂停就没了。判"这轮到底有没有真产出"是 `run_stage` 的事
          （它看回执），这里只按它的结论执行。
        """
        if not drop:
            for tgt, src in mapping:
                if not tgt.exists():
                    continue
                if src.exists() and not force:
                    continue
                try:
                    # 用 `os.replace`（Windows 上是 MOVEFILE_REPLACE_EXISTING）**一步**覆盖。
                    #   写成"先 `src.unlink()` 再 `_move_or_copy`"就错了：
                    #   high）：目标被 Acrobat/Word 占着时 unlink 抛 PermissionError
                    #   → `except OSError: continue` 跳过这个文件（正确地没搬回去），
                    #   可下一行**无条件** `rmtree(dest)` 把 `_pending_markers/` 里那份
                    #   **唯一的好副本也删了** ⇒ 骨架留着、原件永久消失。
                    #   `os.replace` 失败时两边都还在，注释里说的"副本仍在可恢复"才是真的。
                    os.replace(tgt, src)
                except OSError:
                    # 单个文件搬不动（被占用）就留着它，**绝不**顺手删掉 —— 下一轮还能恢复
                    log(f"⚠️ 恢复 {src.name} 失败（多半被别的程序占着），副本仍在 "
                        f"{dest} 里，可手动取回")
                    continue
        # 只清**已经搬走**的那些；搬不动的连同目录一起留着（无条件 rmtree 会连它一起删）
        for tgt, _ in mapping:
            tgt.unlink(missing_ok=True)
        try:
            dest.rmdir()
        except OSError:
            pass              # 还有没搬回去的文件 → 目录留着，人可以来取

    return _restore


def _stash_paths(rels, dest_root=None):
    """把给定产物（相对 ROOT）暂存走 —— **移动，不删除**。

    两种落点：
      · `dest_root=None`（默认）→ `cache/<时间戳>_<名>/`，每个 rel 一个独立子目录；
      · 传了 `dest_root` → **全部塞进同一个目录** `dest_root/<名>/`。回退/重跑走这条，
        落点是 `<选定目录>/cache/<题目标识_日期_时间>/`（用户要的"按时间命名一个文件夹，
        把残留阶段都放进去"，这样从 cache 里一眼能看出是哪一轮、哪几个阶段）。

    单个文件搬不动（被别的进程占着 → WinError 32、权限、跨盘）时**跳过它继续搬其余的**：
    中断会留下「一半在 cache/、一半在原地」的坏状态，异常还会被上层吞成「驱动异常」。
    失败清单只写进日志（返回值仍是"成功暂存的列表"，调用方语义不变）。
    """
    failed = []
    if not rels: return []
    root = ROOT.resolve()
    cache = CACHE.resolve()
    dest_root = Path(dest_root).resolve() if dest_root is not None else None
    # 源**必须**在工作区内（这是真正要守的：不许把工作区外的东西搬走）。
    #   落点则允许在工作区外 —— 用户可以把产物目录选到项目外面去；那条
    #   "暂存目录必须位于工作区内"的旧守卫只对默认 cache/ 有意义，所以只对它保留。
    if dest_root is None and not cache.is_relative_to(root):
        raise ValueError("暂存目录必须位于当前工作区内")
    # 不在这里预建目录：回退会把「该阶段起」的**每一段**都试搬一次，而大多数阶段
    #   这次根本没产物 —— 预建的话 cache 里会多出一堆空文件夹（一次回退建了 12 个
    #   空目录，只有 1 个真装了东西）。改成**有东西要搬时**才建（见下面 dest.parent.mkdir）。
    stashed = []
    ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f") + "_" + uuid.uuid4().hex[:6]
    for rel in dict.fromkeys(rels):
        p = ROOT / rel
        resolved = p.resolve()
        if resolved == root or not resolved.is_relative_to(root):
            raise ValueError(f"拒绝越界或无效暂存路径: {rel}")
        if resolved.is_relative_to(dest_root or cache):
            raise ValueError(f"拒绝把暂存落点自己搬走: {rel}")
        if not _has_content(p): continue        # 不存在的、以及**空目录**：没有可保留的东西
        # 传了 dest_root 时用**基名** —— 上层已经按阶段分了文件夹（`<时间>/建模设计/`），
        # 再拼成 `reports_ANALYSIS_MODELING_REPORT.md` 就是同一件事说两遍。
        name = (Path(rel).name if dest_root is not None
                else rel.replace("\\", "_").replace("/", "_").rstrip("_"))
        dest = (dest_root / name) if dest_root is not None else (CACHE / f"{ts}_{name}")
        if dest_root is None and not dest.resolve().is_relative_to(cache):
            raise ValueError("暂存目标越界")
        dest.parent.mkdir(parents=True, exist_ok=True)   # 真要搬了才建
        try:
            _move_or_copy(p, dest)
        except OSError as exc:
            # 单个文件搬不动（被别的进程占着、权限）不该让整批中断 ——
            # 那会留下"一半在 cache/、一半在原地"的状态，且异常还会被上层吞成
            # 「驱动异常」。跳过它、记下来，其余照搬。（跨盘**不算**搬不动：
            # `_move_or_copy` 会复制过去。）
            failed.append(f"{rel}（{exc.__class__.__name__}）")
            continue
        stashed.append(rel)
    if failed:
        log(f"⚠️ 有 {len(failed)} 个产物未能暂存（仍留在原地，不影响继续运行）：{'; '.join(failed)}")
    return stashed

# （原 _stash_stage() 已删：无调用方，实际用的是 _stash_paths() / _redo_from()。）

# （原 _export_docx() 已删：不需要 word 版本，后续也不更新。）

def _collect_outputs(final=True):
    """整链正常收口后，把工作区打包成**提交形状**的产物（不是工作归档）。

    `final=False` = **阶段性**收（⑨ 及之后每完成一个阶段各一次，见 `_maybe_collect_outputs`）：
    清单里还没产出的项（`demo.html` 要等 ⑯）跳过、不严格校验。
    `final=True`（缺省）= **正式交付**那次：缺一件都不行、`check()` 全量校验。

    落点是 **`提交作品/最新作品/`**（`_submission_dir()`），不是产物根 ——
    产物根下还有 `cache/`、`各阶段产物/`、`其他产物/`，那不是提交件（判据见 `_submission_dir`）。

    布局：提交件根下只放提交项（正文.pdf / 附录A.pdf / demo.html / 运行说明.md /
    result*.xlsx / 题目附件 / *.py 平铺）+ `其余文件/`；论文的 .tex 工程、辅助脚本、
    中间数据、内部报告全部进 `其余文件/`。清单是 `14Layout-and-format` 写的
    `reports/SUBMISSION_MANIFEST.json` —— 它同时是论文末页清单表的来源，两边必须一致，
    所以**缺失即报错**，不猜、不静默兜底。

    `package()` 自带原子性：在 `最新作品` 旁边建 staging、成功了才换上去，失败保留上一份。
    换题归档不在这一步 —— 那是 `_rotate_pointers()` 把 `最新作品` **整目录改名**的事。
    """
    try:
        from lib.delivery.checks import check
        from lib.delivery.core import load_manifest, package, provisional_items
        out = _submission_dir()
        provisional = False
        # 只有**清单文件不存在**才退到内置最小清单：
        #   用 `except ValueError` 一把兜会把「结构写坏了」也当成「还没写」⇒ 静默改用临时清单，
        #   链尾还会判 PASS 并报「链完成并收集交付物」—— 一份**残缺的**提交包被当成正式交付。
        #   存在但坏 ⇒ 让它照常抛（中途那次由 `_maybe_collect_outputs` 兜成一行日志；
        #   链尾那次判失败，转黄灯让人去修清单，这才是对的）。
        _manifest = ROOT / "reports" / "SUBMISSION_MANIFEST.json"
        if _manifest.is_file():
            items = load_manifest(ROOT)      # 存在但坏 ⇒ 照常抛（见上面注释）
        else:
            items = None
        if items is None:
            # ⑭ 之前没有清单（它才写）⇒ 先按内置最小清单把**已就绪的**收进去
            #   （口径：「9 结束的时候先把已经做好的移入，剩下的做好再移」）。
            #   为什么值得：清单由 ⑭ 写、而 ⑭ 排在 ⑨ 之后 ⇒ 链一旦在 ⑨~⑬ 停下，
            #   `最新作品/` 里会一片空白，尽管正文 PDF、附录、result*.xlsx 早就做好了。
            #   这只是**临时占位**：⑭ 跑完会用清单**整份重建**（名字同源、不会打架）。
            items = provisional_items(ROOT)
            if not items:
                log("打包产物：提交清单还没写出来（⑭ 才写），盘上也还没有可收的提交件 ⇒ 先不建包")
                return False
            provisional = True
            log(f"打包产物：提交清单还没写出来（⑭ 才写）⇒ 先按内置最小清单把**已就绪的 "
                f"{len(items)} 项**收进 提交作品/最新作品/；⑭ 跑完会用清单整份重建")
        if not final:
            # 中途收：清单里**还没产出**的项（`demo.html` 要等 ⑯）跳过，不报错。
            #   不跳过的坑：⑭ 写的清单声明了 demo.html ⇒ 在 ⑭ 跑完那一次就会抛
            #   「清单里这些提交项在工作区找不到」，**一个文件都收不进去** ——
            #   于是"⑨ 跑完先收一批"这条等于没生效（用户翻那个文件夹还是空的）。
            from lib.delivery.core import build_plan
            left = sorted(p for p, _ in build_plan(ROOT, items)[0] if not (ROOT / p).exists())
            package(ROOT, out, items, allow_missing=True)
            if left:
                log(f"阶段性打包：已把已就绪的收进 提交作品/最新作品/；还差 {len(left)} 项"
                    f"（{'、'.join(left)[:140]}）—— 后面的阶段产出后会再收一次")
            else:
                log("阶段性打包：提交件已全部就绪，收进 提交作品/最新作品/")
            return True
        package(ROOT, out, items)
        problems = check(ROOT, out, items)
        if problems:
            if provisional:
                # 临时包**本来就不完整**（demo.html / 运行说明 之类还没产出）⇒ 不合规是预期的，
                # 不能当成失败上报：链尾那次调用会据此判"未产生本轮正式交付"而停链。
                # 如实记一行，正式校验留给 ⑭ 之后那次（那时用清单、provisional=False）。
                log(f"阶段性打包：临时包不完整是预期的（{len(problems)} 条，"
                    f"例如 {problems[0]}）—— ⑭ 写出清单后会整份重建并严格校验")
                return True
            raise ValueError("产物不合规：" + problems[0]
                             + (f"（另有 {len(problems) - 1} 条）" if len(problems) > 1 else ""))
        return True
    except Exception as e:
        log(f"打包产物失败: {e}")
        return False

# 「清理全部残留」搬哪些。**只搬本轮的生成物**，不碰框架本身
# （lib/web/ skills/ docs/ regression/ lib/delivery/ config/ 这些是代码不是产物），
# 也不碰产物目录自己（那是落点）。
CLEANUP_RELS = ["reports", "code", "results", "figures", "paper", "paper_appendix",
                "demo", "运行说明.md"]


def _can_cleanup():
    """按钮显不显示：**整链跑完**且工作区里确实还有残留。

    只写完还不够 —— 中途把 reports/code 搬走，回退与重跑就没东西可用了
    （它们读的正是这些目录）。
    """
    return bool(state["run_completed"]) and any((ROOT / r).exists() for r in CLEANUP_RELS)


def _figure_only_defects(issues):
    """这批未解决项是不是**全是"图本身的产出"缺陷**（`category == "diagram"`）。

    是的话，回退到 ④ 只该**重画图**，不该动它的数值产物 —— 见 `_redo_from` 的 `figure_only`。

    口径收紧到"**每一条**都是 diagram 且至少有一条"：只要混进一条别的类别
      （implementation / data_integrity / validation…），就说明数值本身也可能有问题，
      那必须照旧把 `code/`、`results/` 搬走、让它重算。宁可多算一次，不可拿旧数当新数。
    """
    cats = [str(i.get("category") or "") for i in (issues or []) if isinstance(i, dict)]
    return bool(cats) and all(c == "diagram" for c in cats)


def _taken_over_by(stage):
    """本阶段（⑨ 论文撰写 / ⑬ 按评分判词返修 / ⑩⑪⑫ 三个内容判官）被哪个**后继的论文打磨者**接管了？

    为什么 ⑬ 也在内：⑭排版排在 ⑬ 之后，而它的版式手术会落进
      `paper/sections/*.tex`（定点位移 `\\par\\vspace{9pt}`，见 `reports/FORMAT_REPORT.md` 的 F-1），
      与 ⑬ 改的是**同一批文件** —— 路径层面分不开"这是版式改的还是内容改的"。
      `_LAYOUT_OWNED_PATHS` 那条解耦只覆盖 `paper/_base/` 等少数路径，够不着 `sections/`，
      于是 ⑭ 每跑一次、⑬ 的回执必失配 ⇒ 下一轮 ⑬ 又被拉起来重跑一遍（只改
      `paper/_base/preamble.tex` 并重编 PDF，下一轮 `calls = ['fix']`；不改则零调用）。
      口径：「如果 12 判断过了，那就没 13 什么事了，后续什么 14、15 都跟 12 和 13 没关系了」。

    判「接管者的产物还在盘上」只比**事实半份**（`artifacts` + `outputs`），**不比
      `instructions`**：改一条**共享的**做法要求（`CLAUDE.md`）会让拥有者
      自己的回执也失效 —— 拿整份 digest 去比必然落空 ⇒ 接管失效 ⇒ **⑨ 整篇重写**。
      而这条分支的本意只是「论文已被下游合法改写过（⑭ 版式精修 / ⑬ 按判词返修），
      别再重写一遍把它推翻」。所以判据就该是「它的产物还没被动过」。
    """
    sid = stage["id"]
    # 两类适用：① 产物含 `paper/` 的（⑨⑬，被下游改写的是**产物**）；② 内容判官（⑩⑪⑫，
    # 被改写的是**审查对象** —— 口径「打磨不作废内容判决」，见 `_layout_superseded`）。
    if sid in _CONTENT_JUDGE_STAGES:
        return "format" if _layout_superseded(stage) else None
    if sid not in _PAPER_OWNED_STAGES:
        return None
    return _later_paper_owner(stage)


def _purge_stage_snapshots(sids, dest):
    """把被回退阶段的**展示区快照**移进 `dest/<阶段名>/快照/`（移动，不删除）。

    为什么必须动它：回退把工作区产物搬进 cache 了，而展示区里那份是
    **同一批产物的副本** —— 留着它，用户翻账时会看到"这一轮明明退掉了、快照却还在"，
    和「当前与历史分得清」这条设计相冲。
    """
    moved = 0
    for sid in sids:
        stage = next((s for s in STAGES if s["id"] == sid), None)
        if stage is None:
            continue
        name = str(stage.get("name") or sid)
        src = _stage_dir() / name
        if not src.is_dir():
            continue
        try:
            tgt = dest / name / "快照"
            if tgt.exists():
                shutil.rmtree(tgt, ignore_errors=True)
            tgt.parent.mkdir(parents=True, exist_ok=True)
            src.rename(tgt)
            moved += 1
        except OSError as exc:              # 展示区，别把回退带崩
            log(f"⚠️ 展示区快照搬不动（{name}）：{exc}")
    if moved:
        log(f"🧹 已把 {moved} 个阶段的展示区快照一并移入 cache（可恢复）")


def _purge_pointers(dest):
    """整链清空时，把两个「最新」指针里的内容移进 `dest/最新/`（移动，不删除），再建回空骨架。"""
    from lib.delivery.core import (STAGES_PARENT, STAGES_POINTER, SUBMISSION_PARENT,
                               SUBMISSION_POINTER)
    root = _delivery_dir()
    moved = []
    for pointer in (root / SUBMISSION_PARENT / SUBMISSION_POINTER,
                    root / STAGES_PARENT / STAGES_POINTER):
        if not pointer.is_dir() or not any(pointer.iterdir()):
            continue
        try:
            tgt = dest / "最新" / pointer.parent.name
            if tgt.exists():
                shutil.rmtree(tgt, ignore_errors=True)
            tgt.parent.mkdir(parents=True, exist_ok=True)
            pointer.rename(tgt)             # 整个指针搬走，再懒建回空骨架
            pointer.mkdir(parents=True, exist_ok=True)
            moved.append(pointer.name)
        except OSError as exc:
            log(f"⚠️ 两个「最新」指针搬不动（{pointer.name}）：{exc}")
    if moved:
        log(f"🧹 整链清空：已把 {'、'.join(moved)} 里的旧内容移入 cache（可恢复）")


def _redo_from(sid, keep_rounds=False, figure_only=False):
    """作废 sid 及其后全部回执，并把它们的产物**非破坏性**暂存到 cache/。返回暂存清单。

    抽出来是为了让 /api/redo（用户手动重跑）与「回退」决策共用同一套经过验证的语义。
    """
    start_i = STAGE_IDX[sid]
    # 先暂存、后作废：反过来（先 _invalidate_from）时若暂存中途抛错（Windows 上
    #   有别的进程占着文件 → WinError 32，Excel/Acrobat/编辑器开着报告是常态），
    #   回执已经清空、产物只搬了一半 —— 状态是错的。先搬，搬不动就不作废。
    # 落点：`<选定目录>/cache/<题目标识_日期_时间>/` —— 残留阶段全部塞进**同一个**时间文件夹，
    # 而不是每个 rel 一个 `cache/<ts>_<名>/`。这样从 cache 里一眼能看出是哪一轮、哪几个阶段。
    from lib.delivery.core import delivery_name
    # 题目标识非法时**退化**，绝不为一个名字把整条回退路炸掉：
    #   形态 —— 面板里填了 `2026A:2026.9.18`（`delivery_name` 文档里记的原始
    #   写法），而 `/api/start` 只 `except OSError` 没校验就落了盘，于是之后每一次
    #   `/api/redo`、每一次「回退到 X」都是 ValueError → FastAPI 500；而黄灯那条路在
    #   调用本函数**之前**就把 pending 清了 ⇒ **面板消失、产物没搬、链也没起**，
    #   人只看到一个 500，还被告知「请先停止」（链根本没在跑）。
    try:
        # 用**记录值**（这道题的标识），与两个「最新」的归档、以及面板显示的落点同口径；
        #   用面板框里的值的话 ⇒ 在面板改了标识后，提示写 A 而实际建的是 B。
        _stamp = delivery_name(_recorded_problem_id())
    except ValueError:
        log("⚠️ 题目标识含 Windows 保留字符 —— 本次暂存目录名退到只用时间戳")
        _stamp = delivery_name("")
    dest = _cache_dir() / _stamp
    # **按阶段分文件夹**：`<时间>/建模设计/ANALYSIS_MODELING_REPORT.md`、`<时间>/编码计算/code/`…
    #   而不是把 `reports/xxx.md`、`paper/` 通通拍平进同一个目录。用户要的就是这个形状：
    #   从 cache 里一眼看出"这一轮退到了哪几步、每步留下了什么"。
    # 门禁的**裁决侧车**也是产物（`run_stage` 的 markers 同此口径）——
    # 漏了它，新一轮门禁会带着旧裁决开跑；而旧裁决的指纹必然对不上，白亮一次「裁决过期」。
    # **纯图缺陷：不搬 ④ 的数值产物**。
    #
    #   动机与判据（这件事该**自动**判，不该让人在两个按钮里选）：
    #   ⑦ 的图缺陷按 `category=diagram` 路由回 ④（它是唯一拥有 `figures/make_figures.py` 的
    #   **前序**阶段）。而 `ARTIFACTS["code"] = ["reports/RESULTS_REPORT.md", "code", "results"]`
    #   —— 照搬的话，为了修一个色标与两处图例位置，`code/outputs/*.npz` 与 `results/*.xlsx`
    #   被整包搬进 cache，④ 只能**从零重算**。而交回单 §4 自己就写着
    #   「这一单**一条都不许触发重算**」，`recommended_source=handback` 的建议也是 `code`
    #   —— 即驱动一边听说"只重画图"，一边把数值搬走逼它重算。
    #
    #   判据由 `_figure_only_defects` 给（**每一条**未解决项都是 diagram）。此时：
    #     · 该阶段的**产物一件不搬** —— 数值没问题，搬走只会白烧小时级；
    #     · 但它的**回执照样作废**（下面的 `_invalidate_from`）→ 它仍会重跑
    #       （重跑 ≠ 重算：提示会明确要求只改画图脚本、只重渲染）。
    #   非纯图缺陷（混进 implementation / data_integrity / validation 等）走原路，照搬不误。
    # 「哪个阶段有哪些产物」的唯一出处是 `_stage_rels()` —— 阶段镜像（`_snapshot_stage`）
    #   用的是同一份，免得两处各维护一套、迟早漂移。
    def _rels(s):
        # `own_only=True`：只搬"本阶段是第一声明者"的产物。见 `_stage_rels` 的说明 ——
        #   少了它，「从 ⑫ 重跑」会把 ⑬⑭ 共同声明的 `paper/`、`paper_appendix/` 整目录
        #   搬进 cache，⑫ 的审查对象当场就没了。
        return _stage_rels(s["id"], figure_only=figure_only, own_only=True)

    # 「整链从头重跑」的判据：目标阶段是**链上第一个真正干活的阶段**。
    #   三处都写死 `start_i == 0` 的话 —— ⓪ 读题（只读题、只写自己的报告）插到下标 0 之后，
    #   那个条件对"从 ① 文献定向 重跑"**永远不再成立** ⇒ 上一轮的提交件指针与返修回执不再
    #   被收走，面板会挂着"提交件 → …（已生成）"，而那份包其实是上一轮的（两条既有用例
    #   `test_a_full_wipe_also_clears_the_showcase_and_the_two_pointers` /
    #   `test_full_wipe_archives_artifacts_and_receipts` 当场变红）。
    _from_top = start_i <= STAGE_IDX["literature"]
    cleared = []
    for s in STAGES[start_i:]:
        cleared += _stash_paths(_rels(s), dest_root=dest / s["name"])
    _invalidate_from(start_i)
    for s in STAGES[start_i:]:                       # 非破坏性：移入 cache/，可恢复
        cleared += _stash_paths(_rels(s), dest_root=dest / s["name"])
    if _from_top:
        # **整链清空**（从 ① 文献定向 重跑）时必须把**回执**一起收走，否则新的一轮会当场卡死：
        #   回执留在 runtime/quality/feedback/ 里，而新的一轮 ② 建模设计 是**没有回执**的一轮
        #   —— 收尾自检 `check_receipts` 会看到「有回执、没台账」，要它凭空交一份台账
        #   （台账要答的那份回执根本不属于这一轮），于是全链在第 2 步挂起、白跑一遍。
        #   只清产物不清回执 = 把上一轮的语义泄漏进新一轮。
        #   只在整链从头重跑时做（`_from_top`）：**局部回退**（回退到 ② 建模设计）时那份回执正是
        #     analysis 要答的，收了就等于把返修回执弄丢了。
        cleared += _stash_paths(["runtime/quality/feedback"], dest_root=dest / "回执")
    # 展示区也要跟着走：工作区产物已经搬进 cache 了，而
    #   `各阶段产物/最新产物/<阶段名>/` 里还挂着**同一批已经被搬走的**东西 ——
    #   用户翻账时会看到"不存在的东西"。这里把被回退阶段的快照也移进 cache
    #   （与工作区原件落进同一个时间文件夹、`<阶段名>/快照/`），可恢复、不删除。
    _purge_stage_snapshots([s["id"] for s in STAGES[start_i:]], dest)
    if _from_top:
        # 整链清空 = 从头画，阶段↔图的归属也跟着归零（否则新的一轮会带着旧的归属）
        _save_figure_attr({})
        # 整链清空：「两个最新」指针里装的是**上一题/上一轮**的提交件与阶段快照，
        #   而它们不在工作区里 —— 不处理的话 `submission_exists` 仍是 True、面板显示
        #   "有提交件"，链其实停在 ①；对那份旧包跑 `delivery check` 还会判 PASS
        #   （它确实是上一轮合规的包）。移进 cache 的 `最新/` 下，可恢复。
        _purge_pointers(dest)
    HANDBACK.unlink(missing_ok=True)
    # 黄灯必须跟着一起灭。`_redo_from` 把阶段全打回 idle、产物也搬走了，
    #   而 pending 描述的是**某个阶段的某个产物现在该拿它怎么办** —— 产物都不在了，
    #   留着它等于让面板对着一个不存在的对象等决策（整链清空后 UI 仍显示
    #   「等待你决策：重跑本门禁」，而那份报告已经被搬进 cache）。
    #   局部回退（rollback 决策）那条路本来就在调用方清过，这里再清一次是幂等的。
    _set_pending(None)
    state["halt_gate"] = False
    state["halt_reason"] = ""
    state["last_tail"] = ""
    if _from_top:
        # 整链清空连**人工决策清单**一起收走：它记的是上一轮那次挂起的判据与回执，
        # 新一轮从头跑时它已经没有任何指代对象，留着只会误导（`_halt` 每次都会重写它）。
        cleared += _stash_paths(["reports/HIL_DECISION.md"], dest_root=dest / "回执")
    for k in state["stages"]:
        state["stages"][k] = "idle"
    state["progress"] = {"done": 0, "total": len(STAGES)}
    if not keep_rounds:
        state["rounds"] = {}
    return cleared


class StageReq(BaseModel):
    stage: str

@app.post("/api/redo")
async def redo(req: StageReq):
    """清空某阶段及其后全部产物 → 重跑会从该阶段开始（前序已有产物会自动跳过）。"""
    if state["running"]:
        raise HTTPException(409, "运行中不能移动阶段产物，请先停止并等待执行结束")
    sid = req.stage
    if sid not in STAGE_IDX:
        raise HTTPException(400, f"未知阶段 {sid}")
    cleared = _redo_from(sid)
    # 被清掉的阶段，它的**决策面板也要跟着作废**。
    #   点「暂停当前阶段→清空→从⑨重跑」后，⑩ 的 `paused` 黄灯会**留在面板上** ——
    #   那个阶段的产物与回执都已被清空，面板却还在问"这一步怎么办"（而 `running=True` 时
    #   点它还回 409），看起来像"没反应"或"界面错乱"。`/api/start` 不清 pending
    #   （它只清 retry_cap / seed_hints / attempts —— `paused` 是留给用户决策的入口）。
    #   判据：pending 指向的阶段 **≥ 被清空的阶段** ⇒ 它的上下文已被清掉 ⇒ 丢弃。
    p = state.get("pending")
    if p and p.get("stage") in STAGE_IDX and STAGE_IDX[p["stage"]] >= STAGE_IDX[sid]:
        log(f"已清空 {sid} 及之后 ⇒ 丢弃指向 {p['stage']} 的残留决策面板（它的产物已作废）")
        _set_pending(None)
    log(f"已把 {sid} 及之后产物暂存至 cache/（未删除，可恢复）: {cleared}")
    return {"ok": True, "cleared": cleared}


class DeliveryReq(BaseModel):
    output_dir: str | None = None
    problem_id: str | None = None


@app.get("/api/delivery")
async def get_delivery():
    """当前产物设置 + 解析后的绝对路径 + 归档会用到的目录名（顺带校验保留字符）。"""
    from lib.delivery.core import delivery_name, resolve_output_dir
    cfg = _delivery_config()
    out = resolve_output_dir(ROOT, cfg["output_dir"])
    try:
        archive_name, error = delivery_name(_recorded_problem_id()), ""
    except ValueError as exc:
        archive_name, error = "", str(exc)
    # `output_dir` 给的是**配置里的原值**（可能为空字符串）—— 前端要拿它回填那个输入框，
    #   填成解析后的绝对路径会让「留空 = 用默认」这个语义在面板上消失。解析后的值走 `resolved`。
    sub, stg = _submission_dir(), _stage_dir()
    return {"output_dir": cfg["output_dir"], "problem_id": cfg["problem_id"],
            "resolved": str(out), "archive_name": archive_name, "error": error,
            "exists": out.is_dir(), "root": str(ROOT),
            "submission_dir": str(sub), "stage_dir": str(stg),
            # 看**有没有东西**（空骨架不算「已生成」，与 `_delivery_status` 同口径）
            "submission_exists": sub.is_dir() and any(sub.iterdir()),
            "stage_exists": stg.is_dir() and any(stg.iterdir())}


@app.post("/api/delivery")
async def set_delivery(req: DeliveryReq):
    """保存产物设置。题目标识先过一遍校验 —— 含 Windows 保留字符就拒，别等归档时才炸。"""
    from lib.delivery.core import delivery_name, resolve_output_dir
    cfg = _delivery_config()
    out_dir = cfg["output_dir"] if req.output_dir is None else req.output_dir
    pid = cfg["problem_id"] if req.problem_id is None else req.problem_id
    try:
        delivery_name(pid)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    _save_delivery_config(out_dir, pid)          # 归一化在 _save_delivery_config 里收口
    return {"ok": True, "resolved": str(resolve_output_dir(ROOT, out_dir))}


class ArchiveReq(BaseModel):
    problem_id: str | None = None
    output_dir: str | None = None


@app.post("/api/archive")
async def archive_delivery(req: ArchiveReq):
    """**手动轮转**：把两个「最新」指针归档成 `<题目标识_日期_时间>/`，再建两个空的。

    换题时这件事是自动的（`_prepare_workspace` → `_rotate_pointers`）；这个按钮留给两种
    正当需求：① 输入没变也想划一条边界（把这题冻结成一份归档再在其上做实验）；
    ② 自动轮转被占用文件挡回时的手动恢复出口。

    顺带把前端那两个框一起存下来 —— 「保存」按钮删掉之后，这里是唯一"改完设置
    还能落盘"的入口（`/api/start` 是另一个），不存的话改完路径点归档会白改。
    """
    if state["running"]:
        raise HTTPException(409, "运行中不能归档产物，请先停止")
    if req.problem_id is not None or req.output_dir is not None:
        cfg = _delivery_config()
        _save_delivery_config(cfg["output_dir"] if req.output_dir is None else req.output_dir,
                              cfg["problem_id"] if req.problem_id is None else req.problem_id)
    try:
        # 用**记录值**（这道题的标识），不是面板当前配置 —— 面板那个框描述的是
        #   「接下来要跑的题」，把 A 题的成果盖上 B 题的名字就是这么错的。
        info = _rotate_pointers(reason="手动归档", problem_id=_recorded_problem_id())
    except RotationBlocked as exc:
        raise HTTPException(400, f"归档未完成（两个「最新」都还在原地）：{exc}") from exc
    # 如实回答：两个「最新」都是空的时候 `rotate_pointer` 只建骨架、**不建归档目录**
    #   （`rotated` 为空）。此时回一个 `archived_to` 指向不存在的路径，前端就会打出
    #   「已归档 → X/」——冒充成功。旧实现在同等情形回 400，这里保留那个诚实度。
    # 只收编了残留也算「有事发生」—— 否则接口说「两个「最新」都是空的，什么都没有」，
    #   而盘上明明多出一个带日期的归档目录。
    created = bool(info["rotated"] or info.get("orphaned"))
    resp = {"ok": True, "name": info["name"], "rotated": info["rotated"], "created": created}
    if created:
        # 报**真正被改名的那些落点**：硬编码成 `提交作品/<name>` 的话，
        #   而「链只跑到一半就点归档」是常态 —— 那时只有 `各阶段产物/最新产物` 非空、
        #   `提交作品/最新作品` 还没东西（它要等整链收口打包）⇒ 回的是一个**从未建过**的
        #   路径，正是同一个函数上面那条注释要防的「冒充成功」。
        resp["archived_to"] = list(info["rotated"])
    else:
        resp["note"] = "两个「最新」都是空的（没有什么可归档的），只把骨架目录建了回来"
    return resp


class WipeReq(BaseModel):
    confirm: str = ""


#: 删本题要原样打出来的暗号（照 `#wipe_btn` 手输"清空"的先例：不可逆的操作不能一键完成）
WIPE_CONFIRM_WORD = "删除本题"


@app.post("/api/wipe-problem")
async def wipe_problem(req: WipeReq):
    """**不归档、直接删掉本题的产物与状态**（「不归档删除本题……清理干净一点」）。

    这是全仓**第一条真删数据的路径**。别的都是 `rename`（归档）或 `move`（🧹 清理、
      「清空全部」也是移进 cache）—— 所以这里三道闸：运行中 409、必须原样打暗号、
      每一步删了什么逐条回给面板并写日志（人要能看出"到底动了什么"）。
    边界：**删产物 + 删状态，保留题面与附件**。
      `request/`（题面、附件、`_inbox/`）与 `data/` **一个字节都不动** —— 那是传进来的原件，
      删了不可恢复；框架本体（`lib/ skills/ docs/ regression/ config/`、`CLAUDE.md`、`.env`）更不碰。
    必须自己补的三件事（归档靠 `rename` 天然办到，删除得显式做）：
      ① 重建两个**空**的「最新」指针 —— `_delivery_status` 与 `lib/delivery/checks.py` 都假定
         那两层结构在（`resolve_output_dir` 只拼路径、不建目录）；
      ② 收掉内存里的黄灯与轮次态，否则面板上还挂着一盏指向已删文件的灯；
      ③ **把 `workspace.json` 重写成当前的 `_source_digest()`** —— 否则下一次点「开始全链」会因为
         digest 对不上被当成**换题**，白跑一轮 `_rotate_pointers` + `_invalidate_from(0)`
         （产物已经没了，那一轮转只会产出两个空归档目录）。
    """
    if state["running"]:
        raise HTTPException(409, "有链正在跑 —— 先停掉再删（绝不在它跑着的时候动它的文件）")
    if (req.confirm or "").strip() != WIPE_CONFIRM_WORD:
        raise HTTPException(400, f"没确认：请原样输入「{WIPE_CONFIRM_WORD}」")
    # 一个真正的独占闸：光看 `state["running"]` 是
    #   "先查后做"，中间那个窗口里 `/api/start` 照样能起链 —— 而这条删除要遍历好几个目录，
    #   期间链已经把阶段状态写成 stage2 了，wipe 第⑥步又把它刷回 idle ⇒ 黄灯重新点亮、
    #   托管模式下还会"删完又起链"。用一个**带时间戳**的标志把窗口关掉，`/api/start` 侧也认它。
    #   用时间戳而不是布尔：万一中途抛异常没能清掉，300 秒后自动失效 —— 免得一次失败把
    #   "起链"永久锁死（那种故障比它要防的竞态更烦人）。**放在确认暗号之后**：暗号打错不该占着闸。
    state["wiping_at"] = time.time()
    from lib.delivery.core import (STAGES_PARENT, STAGES_POINTER, SUBMISSION_PARENT,
                                   SUBMISSION_POINTER)
    out_root = _delivery_dir()
    removed = []

    def _rm(p, label):
        """删一个文件/目录，**删不掉也不算失败**（只记进日志）—— 被别的程序占着时
        宁可留个尾巴让人看见，也不要删到一半抛异常、留下说不清的状态。"""
        try:
            if p.is_dir():
                shutil.rmtree(p)
            elif p.exists():
                p.unlink()
            else:
                return
            removed.append(label)
        except OSError as exc:                                        # noqa: BLE001
            log(f"⚠️ 删不掉 {label}：{exc}（被别的程序占着？关掉再删一次）")

    # ① 本题在工作区里的产物（清单与 🧹 清理**同一份**，不另立一套）
    for rel in CLEANUP_RELS:
        _rm(ROOT / rel, rel + ("/" if (ROOT / rel).is_dir() else ""))
    # ② 两个「最新」指针的**内容**（指针本身马上重建）
    for pointer in (out_root / SUBMISSION_PARENT / SUBMISSION_POINTER,
                    out_root / STAGES_PARENT / STAGES_POINTER):
        _rm(pointer, str(pointer.relative_to(out_root)) + "/")
        try:
            pointer.mkdir(parents=True, exist_ok=True)                # 骨架要留
        except OSError as exc:                                        # noqa: BLE001
            log(f"⚠️ 空指针建不回来（{pointer}）：{exc}")
    # ③ 归档与清理的落点 —— **只清本题的那一份，别动往届**。
    #    `cache/<归档名>/` 里躺着的是**被轮转出去的那道题**的产物原件；`cache/` 下按题分目录，
    #    把整棵 rmtree 会**连带删掉上一题唯一的副本** —— 那正是确认框里承诺"保留"的东西。
    #    归档名就是 `<题目标识>_<日期_时间>`，而本题的标识由 `workspace.json` 记着
    #    （`_recorded_problem_id()`），按前缀精确匹配即可。
    pid_prefix = str(_recorded_problem_id()).strip()
    cache = out_root / "cache"
    if cache.is_dir():
        if not pid_prefix:
            # 认不出"本题"是谁（`workspace.json` 里没记题目标识）⇒ **一个都不删**。
            #   猜错的代价是删掉上一题唯一的副本，而那是不可恢复的；留着最多是占点空间。
            log(f"⚠️ 认不出本题标识，cache/ 一律保留（{len(list(cache.iterdir()))} 项）")
        else:
            for child in sorted(cache.iterdir()):
                if not child.name.startswith(pid_prefix + "_"):
                    log(f"（保留往届归档：cache/{child.name}）")
                    continue
                _rm(child, f"cache/{child.name}")
            if cache.is_dir() and not any(cache.iterdir()):
                _rm(cache, "cache/")             # 空了就把壳也收掉
    _rm(out_root / "其他产物", "其他产物/")
    # ④ 本题状态：回执 / 黄灯 / 工作区记录 / 返修台账（`feedback/` 尤其要清 ——
    #    它是**无 run_id 过滤的全目录 glob**，残留一条旧回执会让新一轮 ② 必然假报"缺返修台账"）
    qdir = LOG_DIR / "quality"
    kept_dir = INTAKE_DIR / "kept"
    if qdir.is_dir():
        for child in sorted(qdir.iterdir()):
            # `runtime/quality/intake/kept/` **不能删**：
            #   那是"明确要求不动它"（角色选 `ignore`/`needs_manual`）的原件的**唯一一份** ——
            #   `_materialize_inbox` 是把它们 copy 进 kept/ **再** rmtree 掉 `_inbox/` 的。
            #   删了就正好毁掉确认框里承诺"会留"的东西（与 R4 那个 cache 错法是同一类）。
            #   它的位置在 `runtime/quality/` 下，而这一层是整目录遍历删 —— 必须显式绕开。
            if kept_dir.is_dir() and child == INTAKE_DIR:
                # intake/ 下只删状态（confirmed.json 等），kept/ 整棵留着
                for sub in sorted(child.iterdir()):
                    if sub == kept_dir:
                        log(f"（保留「不动它」的原件：{kept_dir.relative_to(ROOT)}）")
                        continue
                    _rm(sub, f"runtime/quality/intake/{sub.name}")
                continue
            _rm(child, f"runtime/quality/{child.name}")
    for name in ("web_run.log", ".runclock.json", "_chk.js"):
        _rm(LOG_DIR / name, f"runtime/{name}")
    # ⑤ 重建工作区记录（digest 记成**现在**的 —— 见上面第 ③ 条）
    try:
        qdir.mkdir(parents=True, exist_ok=True)
        atomic_json(qdir / "workspace.json",
                    {"source_digest": _source_digest(), "run_id": state["run_id"],
                     "problem_id": _delivery_config()["problem_id"]})
    except OSError as exc:                                            # noqa: BLE001
        log(f"⚠️ 工作区记录写不回去：{exc}")
    # ⑥ 内存态：黄灯、轮次、进度，以及**阶段状态全部回到 idle**
    #    （产物和回执都删了，面板上还留着一排完成标记就是撒谎；照 `_start_chain` 重置的那几项来）
    state["wiping_at"] = 0.0                     # 独占闸放行（见开头那段注释）
    _set_pending(None)                           # 用文档化的那一个（它同时把盘上那份删掉）
    # 光清 `pending` 不够：页头的「已挂起 · <原因>」读的是 `halt_gate`/`halt_reason`，
    #   不清就会在删干净之后继续显示**上一轮**的失败原因。
    #   照 `_redo_from` 与 `/api/stop` 那两处的处置，一并收掉。
    state["halt_gate"] = False
    state["halt_reason"] = ""
    state["stale_instr"] = set()
    state["layout_superseded"] = set()
    state["run_completed"] = False
    state["attempts"] = {}
    state["retry_cap"] = {}
    state["seed_hints"] = {}
    state["force_retry"] = None
    state["rounds"] = {}
    state["adv_by_stage"] = {}          # 阶段行上的 📝N 建议条数
    state["issues_by_stage"] = {}       # 📝 面板上半段：该阶段未解决的门禁判据
    state["waived"] = set()
    state["fix_required"] = set()
    state["elapsed_base"] = 0.0
    for value in state["stage_t"].values():
        value.update(elapsed=0.0, start=None)
    for sid in state["stages"]:
        state["stages"][sid] = "idle"
    state["progress"] = {"done": 0, "total": len(STAGES)}
    log(f"🗑 不归档删除本题：删了 {len(removed)} 项（{', '.join(removed[:8])}"
        f"{'…' if len(removed) > 8 else ''}）；**保留** request/（题面与附件）、data/、框架本体")
    return {"ok": True, "removed": removed,
            "kept": ["request/（题面与附件）", "data/",
                     "框架本体（lib/ skills/ docs/ regression/ config/）"],
            "resolved": str(out_root)}


@app.post("/api/cleanup")
async def cleanup():
    """把工作区里剩下的生成物**移进** `<选定目录>/其他产物/`。

    只在整链跑完之后可用 —— 中途搬走 `reports/`、`code/` 这些，回退与重跑就没东西可读了
    （它们读的正是这些目录）。是**移动**不是复制：搬完项目根就干净了，
    产物目录里那份（提交件 + 其他产物/）才是留下的一整套。
    """
    if state["running"]:
        raise HTTPException(409, "运行中不能清理，请先暂停或停止")
    if not state["run_completed"]:
        raise HTTPException(400, "整链还没跑完 —— 中途搬走这些，回退和重跑就没东西可用了")
    present = [rel for rel in CLEANUP_RELS if (ROOT / rel).exists()]
    if not present:
        return {"ok": True, "moved": [], "dest": str(_delivery_dir() / "其他产物")}
    dest_root = _delivery_dir() / "其他产物"
    moved = _stash_paths(present, dest_root=dest_root)
    log(f"🧹 已把 {len(moved)} 项残留移入 {dest_root}")
    # 说清代价：搬走的正是 `stage_discipline` 第一节要求"返修时直接复用"
    #   的那批产物，而**驱动的回退暂存只找 `cache/`**（`_stash_paths` 的落点是 `<产物>/其他产物/`，
    #   两个地方）⇒ 清理之后再回退/重跑，agent 会以为盘上什么都没有，受影响的量就得重算
    #   （④ 编码计算那种是小时级）。要复用就先手动 cp 回去（前端确认框里也写了同样的提示）。
    log("   （清理后若要从某阶段重跑：上一版产物在这个目录下按阶段名分文件夹，"
        "先 cp 回对应工作区目录再点重跑，否则会重算）")
    return {"ok": True, "moved": moved, "dest": str(dest_root)}


# ---------------- 人工决策（黄灯）入口 ----------------

class DecisionReq(BaseModel):
    action: str                       # retry | rollback | disclose | extend | attest | confirm
    stage: str | None = None          # rollback / attest 的目标阶段
    extra_seconds: int | None = None  # extend：**追加**多少秒（不是新的总上限，见 RETRY_CAP_* 注释）
    note: str = ""
    # ---- 只有 `confirm`（⓪ 读题确认）用得上；缺省一律不影响既有调用方 ----
    problem_text: str | None = None   # 人核对/改过的题面正文（None = 不改，用 AI/机械那份）
    roles: list | None = None         # 逐份原件的去向：[{path, role, target}, …]
    corrections: str | None = None    # 人工更正说明（会进 ① 的提示）


def _autopilot_decision(p):
    """托管模式下，**这一次挂起**该自动做什么？返回 `DecisionReq` 或 None（交给用户）。

    用户口径：「阶段超时**自动延长**，推荐回退什么就**自动按照他说的回退**，
    再点一次就取消托管」。所以只认这两类，其余一律交人 —— 尤其是**没有推荐目标**的
    失败、以及「接受并披露」这种要担责任的放行，托管**不替用户做**。
    """
    if not state.get("autopilot") or not isinstance(p, dict):
        return None
    acts = p.get("actions") or []
    sid = p.get("stage")
    if p.get("kind") == "overtime" and "extend" in acts:
        return DecisionReq(action="extend", stage=sid)          # 不传 extra_seconds ⇒ 用默认追加量
    rec = p.get("recommended")
    if isinstance(rec, str) and rec.strip() and "rollback" in acts:
        rec = rec.strip()
        # 自旋闸：只看**速率**，不看总次数 —— 见 `AUTOPILOT_SPIN_WINDOW`。
        #   慢循环（一轮一小时、每轮都在真干活）永远够不到这个阈值 ⇒ 托管就一直开着；
        #   秒判自旋（一轮几秒）几十秒内就撞上 ⇒ 那时停下来才是对的。
        #   这里**不按键分桶**（按 `"<挂起阶段>-><目标>"` 分桶的话，写计数那侧求键晚一步、
        #     求出了 `"None->code"`，两个桶永不相等 ⇒ 闸是死的）。自旋是**全局**性质，
        #     本来也不该按键分 —— 换个键接着自旋一样是自旋。
        now = time.time()
        recent = _recent_rollbacks(now)
        if len(recent) >= AUTOPILOT_SPIN_MAX:
            log(f"🤖 托管：最近 {AUTOPILOT_SPIN_WINDOW // 60} 分钟内已自动回退 {len(recent)} 次"
                f"（上限 {AUTOPILOT_SPIN_MAX}）⇒ 每一轮都短到不可能是真在干活，判为**自旋**"
                f"⇒ **自动关掉托管**，这一盏交给你决定")
            state["autopilot"] = False
            state["autopilot_armed"] = False
            return None
        return DecisionReq(action="rollback", stage=rec)
    return None


def _recent_rollbacks(now=None):
    """窗口**内**的自动回退时刻（升序）。窗口外的一律不算 —— 这正是"慢循环不触发闸"的实现。

    单一出处：判闸（`_autopilot_decision`）与记账（`_autopilot_fire`）都走它，
    免得两边各写一遍过滤条件、日后又长出第二个"两边不一致"（旧闸就是这么死的）。
    """
    now = time.time() if now is None else now
    return sorted(t for t in (state.get("auto_rollback_times") or [])
                  if now - float(t) < AUTOPILOT_SPIN_WINDOW)


async def _autopilot_fire():
    """把托管该做的那一步落地。**只能在 `state["running"]` 已经是 False 之后调**。

    为什么不能在 `_halt` 里当场做：`_halt` 是在 `run_all` 内部调的，那一刻 `running`
      还是 True，`_apply_decision` 会以「链正在运行」为由回 409（超时那一档例外，见下），
      而 `_start_chain()` 也会与正在收尾的这条链抢 state。所以挂起时只**置位**
      `autopilot_armed`，等 `run_all` 的 `finally`（那里 `running` 已置 False）再落实。
    超时那一档是例外：它本来就是"链还在跑、等人工说话"，`_apply_decision` 明确放行，
      所以在看门狗里**当场**调 —— 不这样就得等到整链停下才延长，等于没延。
    """
    p = state.get("pending")
    req = _autopilot_decision(p)
    if req is None:
        if state.get("autopilot") and p:
            log(f"🤖 托管：这次挂起（{p.get('kind')}）没有可自动执行的动作 ⇒ 留给你决定")
        return
    log(f"🤖 托管：自动执行 `{req.action}`" + (f" → {req.stage}" if req.stage else "")
        + ("（阶段超时自动延长）" if req.action == "extend" else "（按推荐目标回退）"))
    try:
        r = await _apply_decision(req)
    except Exception as exc:                            # noqa: BLE001 —— 托管失败就退回人工
        log(f"⚠️ 托管自动执行失败（已转人工）：{exc}")
        return
    if r.get("resumed"):
        if req.action == "rollback":
            # 记进**跨 run** 的时刻表（`run_all` 刻意不清它 —— 清了闸就没了，见
            #   AUTOPILOT_SPIN_WINDOW 那段）。只记"真的落实了"的那些。
            #   时刻表的读写都走 `_recent_rollbacks`；这里**不按键分桶** —— 按键分桶的话
            #     `state["pending"]["stage"]` 求键，而这一行是在 `await _apply_decision(req)`
            #     **之后**跑的，那一刻 `_redo_from` 已经把 pending 清成 None ⇒ 记到了
            #     `"None->code"`，与判据读的 `"audit->code"` 永不相等，闸形同虚设。
            now = time.time()
            recent = _recent_rollbacks(now) + [now]
            state["auto_rollback_times"] = recent
            log(f"🤖 托管：自动回退（最近 {AUTOPILOT_SPIN_WINDOW // 60} 分钟内第 {len(recent)} 次；"
                f"≥{AUTOPILOT_SPIN_MAX} 次判自旋并关掉托管）")
        _set_start_index(r.get("resume_index", 0))
        _start_chain()


def _start_chain():
    """起一条新的整链线程。端点必须自己先置 running —— 与 /api/start 同一模式：
    run_all 是进线程后才置的，中间有窗口，用户连点两次会起两条链。

    已经有一条链在跑时**喊一声**：新链会覆盖 `state["run_id"]`，旧链下一处阶段边界
      就会靠栅栏令牌自己收手（见 run_all 顶部），但那之前它会继续写 —— 有一条日志
      才知道发生过「两条链」。这正是「莫名其妙作废」的入口条件，不该是静默的。
    """
    if state["running"]:
        log("⚠️ 已有一条链在跑，仍起新链 —— 旧链会在下一处阶段边界凭 run_id 栅栏自行收手。"
            "若旧链此刻正阻塞在 _call 的看门狗里，它的产物与回执仍可能与新链交叠。")
    state["running"] = True
    threading.Thread(target=lambda: asyncio.run(run_all()), daemon=True).start()


def _retry_hint(sid, pending, note):
    """重试的提示。必须带上上次失败的原始输出 —— 否则就是把同一个 prompt 再发一遍。"""
    h = f"【人工重试】上一次执行 {sid} 失败。原始失败输出：\n" + (pending.get("tail") or "")[:1500]
    if note:
        h += "\n用户要求：" + note
    return h


def _consume_resume_action(stage, index, hints):
    """把「超时黄灯」上的决定交给**正在跑的那条链**落实。

    为什么不让端点自己起新链：超时黄灯时旧 run_all 还活着（阻塞在 _call 的看门狗里），
    起新链会与它抢 state。所以端点只把决定写进 state["resume_action"]，
    看门狗杀完进程、run_stage 返回失败后，由这里落实。

    返回新的 index（继续跑）或 None（按普通失败处理）。
    """
    act = state.pop("resume_action", None)
    if not act:
        return None
    # 必须校验这个决定**属于哪个阶段**。`resume_action` 是全局一次性槽位，而它的写入方
    #   （超时黄灯上的 retry/rollback）与消费方隔着看门狗：若目标阶段赶在看门狗下一轮采样
    #   （≤5s）之前自己成功退出，槽位就没人消费、一路留到**后面某个失败阶段**手里
    #   —— 对 robustness 选的「回退到 code」会被 verify 的失败执行掉：产物被搬进
    #   cache/、从 code 重跑 9 个阶段、还把 verify 的返修回执当 code 的修复指令注入 prompt。
    if act.get("stage") != stage["id"]:
        log(f"⚠️ 丢弃一个不属于本阶段的遗留决定：resume_action(stage={act.get('stage')!r}) "
            f"出现在 {stage['id']} —— 它的目标阶段当时自己跑完了，没人消费它。")
        state["force_retry"] = None
        return None
    state["force_retry"] = None          # 决定已被消费，把「取消并重试」的信号一起收走
    if act["action"] == "retry":
        hints[stage["id"]] = act.get("hint", "")
        _set_pending(None)
        log(f"🔁 [{stage['id']}] 按用户决定取消并重试本阶段")
        return index
    if act["action"] == "rollback":
        tgt = act["target"]
        # 纯图缺陷 → 不搬 ④ 的数值产物（判据见 `_figure_only_defects`）。这里按**当前阶段**
        # 的裁决取 issues（本函数消费的是超时黄灯的决定，pending 已清）；非门禁阶段的裁决是
        # 空壳 ⇒ 借它上一轮拿到的上游门禁回执（见 `_borrowed_upstream_issues`），借不到就保守按"非纯图"。
        cleared = _redo_from(tgt, keep_rounds=True,
                             figure_only=_figure_only_defects(
                                 (_gate_decision(stage).get("issues")
                                  or _borrowed_upstream_issues(stage) or [])))
        for s in STAGES[STAGE_IDX[tgt]:index + 1]:
            hints[s["id"]] = act.get("hint", "")
        _set_pending(None)
        log(f"↩ [{stage['id']}] 按用户决定回退到 {tgt}；产物已暂存 cache/（未删除）: {cleared}")
        return STAGE_IDX[tgt]
    return None


async def _apply_decision(req: DecisionReq) -> dict:
    """校验并落实一个人工决策。协程 —— 测试要直接 await 它，不走 HTTP 线程。"""
    p = state.get("pending")
    # attest 是唯一允许"无黄灯"执行的动作（它答的是「手工改了某阶段的产物，以当前盘面
    #   重新认证」，与有没有黄灯无关），但它**不能**在链正在跑时执行：
    #   `_do_attest` 一律返回 resumed=True，端点据此再起一条 run_all —— 而 run_all 既不看
    #   state["running"]、一进来就把所有阶段重置为 idle，于是两条链共享同一份 state、
    #   都在写回执、都在调模型（超时黄灯期间链**确实还在跑**，那正是它的定义）。
    if req.action == "attest" and state["running"]:
        raise HTTPException(409, "链正在运行，不能做人工认证 —— 请先「⏹ 停止」，"
                                 "或等它跑完/亮黄灯后再认证")
    if not p and req.action != "attest":
        raise HTTPException(409, "当前没有待决策项")
    if not p:
        return await _attest_without_pending(req)
    # `overtime` 的语义是「**进程还在跑**，只是超了限时」。链已死时它不成立 ——
    #   形态：超时黄灯期间按 ⏹ 停止后，run_all 走 stopping 出口 break（既不走 _halt
    #   也不清 pending），盘上留下一个没有链的 overtime pending。此时点「延长」会把
    #   阶段设成 running 且永不回绿、点「再试一次」只写一个没人消费的信号 —— 两个按钮
    #   都报成功却什么都不做。降级成失败黄灯，让它走正常那套（起新链）。
    overtime = p.get("kind") == "overtime" and state["running"]
    # 超时黄灯时链仍在跑，那正是要决策的场景 → 必须放行；其余运行中一律拒绝
    if state["running"] and not overtime:
        raise HTTPException(409, "链正在运行且不是超时等待态，请先停止")
    # attest 例外：它答的是「手工改了前面某个阶段的产物」，与黄灯发生在哪一阶段无关，
    # 而 p["actions"] 是黄灯那一刻的快照（人改文件在其后，快照必然过期）。它自带完整校验
    # （非门禁 / 产物在盘上 / 客观校验通过 / 回执自检），所以不走这张白名单。
    if req.action != "attest" and req.action not in (p.get("actions") or []):
        raise HTTPException(400, f"当前场景不支持动作 {req.action}（可用：{p.get('actions') or []}）")
    sid = p["stage"]
    stage = next(s for s in STAGES if s["id"] == sid)
    eff = None
    if req.extra_seconds is not None:
        eff = max(RETRY_CAP_EXTRA_MIN, min(RETRY_CAP_EXTRA_MAX, int(req.extra_seconds)))

    # ① 延长本次限时：不杀进程、不起链，任务一秒没停，看门狗下一轮采样就现读到新上限
    if req.action == "extend":
        # **追加**，不是替换。口径：默认 30 分钟到点 → 问 → 加 10 ⇒ 临时上限 40
        #   → 40 到点再问 → 再加…（上限为 CALL_HARD_CAP）。
        #   写成替换的话，填 10 会把上限从 30 **缩短**成 10，而阶段此时已跑 30 分钟 ⇒
        #   超限恒成立、黄灯立刻又亮（配合那个一次性布尔锁还会把它永久压住，58 分钟没提醒）。
        #   按钮上写着「延长」，语义就该是往上加。
        # 到顶就别再"假延长"：`new_cap <= cur`
        #   时照样清黄灯、置 running，并声称"下一次超限会立刻再问你"—— 而**键没变**
        #   （`(cap_s, kind)` 一模一样）⇒ 它再也不会亮，那次调用从此没有墙钟兜底。
        #   现在直接告诉用户"到顶了、这条按钮没用了"，不改任何状态、也不清黄灯。
        cur = _effective_limits(sid)[0]
        eff = eff or RETRY_CAP_EXTRA_MIN
        if cur >= RETRY_CAP_MAX:
            raise HTTPException(
                400, f"已经是总上限 {RETRY_CAP_MAX // 60} 分钟，不能再延长了 —— "
                     f"要么让它继续跑（不点任何按钮，黄灯不影响它），要么「再试一次」/「回退」")
        new_cap = min(cur + eff, RETRY_CAP_MAX)
        state["retry_cap"][sid] = new_cap
        _set_pending(None)
        state["stages"][sid] = "running"
        log(f"⏱ [{sid}] 用户延长本次限时：追加 {eff // 60} 分钟 "
            f"（{cur // 60} → {new_cap // 60} 分钟）→ 任务继续运行")
        emit("state", state2dict())
        return {"ok": True, "action": "extend", "effective_seconds": new_cap,
                "resume_from": sid, "resumed": False}

    # ② 再试一次
    if req.action == "retry":
        hint = _retry_hint(sid, p, req.note)
        if overtime:
            # 取消正在跑的那一次：看门狗每 5s 采样会读到 force_retry 并强杀，
            # 随后由 _consume_resume_action 在本链内重跑本阶段（不起新链）
            state["force_retry"] = sid
            state["resume_action"] = {"action": "retry", "hint": hint, "stage": sid}
            _set_pending(None)
            log(f"🔁 [{sid}] 用户选择取消并重试 → 已通知看门狗强杀，随后在本链内重跑")
            emit("state", state2dict())
            return {"ok": True, "action": "retry", "effective_seconds": eff,
                    "resume_from": sid, "resumed": False}
        state["seed_hints"] = {sid: hint}
        if eff:
            state["retry_cap"][sid] = eff
        _set_pending(None)
        log(f"🔁 [{sid}] 用户选择再试一次（本次限时 {eff or '默认'}）")
        return {"ok": True, "action": "retry", "effective_seconds": eff,
                "resume_from": sid, "resume_index": STAGE_IDX[sid], "resumed": True}

    # ③ 回退到指定阶段
    if req.action == "rollback":
        target = req.stage or p.get("recommended")
        if target not in STAGE_IDX:
            raise HTTPException(400, f"未知的回退目标 {target!r}")
        try:
            _target_index(target, STAGE_IDX[sid])   # 复用同一套校验：必须是当前阶段的前序
        except ValueError as e:
            raise HTTPException(400, str(e))
        feedback = _save_feedback(stage)
        hints = {s["id"]: feedback for s in STAGES[STAGE_IDX[target]:]}   # 见上：不含 sid 上界
        # 记下「这一轮谁拿到了哪一份回执」—— 交回那条路要用它回查缺陷清单
        #   （见 `_borrowed_upstream_issues`）。记在**回退区间内每个阶段**头上：
        #   它们唯一会再跑一次的时机就是现在，而其中一个可能交回上游。
        _src = state.pop("_last_feedback_folder", None)
        if _src:
            for _s in STAGES[STAGE_IDX[target]:]:
                state["hint_src"][_s["id"]] = _src
        # 指向上游的 advisories 不这么接就**永远送不到**（见 `_fold_in_deferred_advisories`）。
        #   回退正是那个阶段唯一会再跑一次的时机 —— 在这里把它名下的建议一并交给它。
        _fold_in_deferred_advisories(hints, stage, target, sid)
        # 人工在**回退**时补的要求也要带上 —— 与 `retry` 那条路（`_retry_hint(note)`）对齐。
        #   只有 retry 用 `req.note`、回退把它丢掉的话：在面板上写了要求，回退过去的
        #   生产阶段却看不到（口径改成「摘要计入正文额度」后想让 ⑭ 排版与版式
        #   顺手压掉超出的那一页，这句话传不进去，只能靠它自己跑检查才发现）。
        if (req.note or "").strip():
            for _k in list(hints):
                hints[_k] = (str(hints[_k]) + f"\n用户要求：{req.note.strip()}").strip()
        if overtime:
            state["force_retry"] = sid
            state["resume_action"] = {"action": "rollback", "target": target,
                                      "hint": hints.get(target, feedback), "stage": sid}
            _set_pending(None)
            log(f"↩ [{sid}] 用户选择回退到 {target} → 已通知看门狗强杀，随后在本链内回退")
            emit("state", state2dict())
            return {"ok": True, "action": "rollback", "target": target,
                    "resume_from": target, "resumed": False}
        # 纯图缺陷（未解决项**全是** category=diagram）→ 不搬 ④ 的数值产物：
        #   数值没问题，搬了只会逼它从零重算（交回单 §4 自己写着"一条都不许重算"）。
        #   判据在 `_figure_only_defects`，**自动**判 —— 不给人多一个按钮去选。
        _fig_only = _figure_only_defects(p.get("issues") or [])
        # `_redo_from` **自己会** `_set_pending(None)`（在它把事情办成之后）。
        #   这里先清一次的话 —— `_redo_from` 中途抛错（例如题目标识非法）
        #   就变成「面板已消失、产物没搬、链也没起」：只看到一个 500，连重试的
        #   入口都没了。清 pending 必须**晚于**回退成功。
        cleared = _redo_from(target, keep_rounds=True, figure_only=_fig_only)
        state["seed_hints"] = hints
        if _fig_only:
            log(f"↩ [{sid}] 用户选择回退到 {target}；**缺陷全是图本身的产出** → "
                f"该阶段的数值产物原地保留（不重算），只作废回执让它重画。清理清单: {cleared}")
        else:
            log(f"↩ [{sid}] 用户选择回退到 {target}；产物已暂存 cache/（未删除，可恢复）: {cleared}")
        return {"ok": True, "action": "rollback", "target": target,
                "resume_from": target, "resume_index": STAGE_IDX[target],
                "cleared": cleared, "resumed": True}

    # ③b 人工定点修复后重新认证（attest）
    # 场景：门禁/某阶段怎么改都过不去，人手工把产物改好了。此时**不能**让驱动把
    # 「盘面变了」当成「该阶段要重做」—— 重做恰恰会推翻人工修正。
    # 本动作以当前盘面**重新写回执**，让该阶段被复用，链从它后面继续。
    if req.action == "attest":
        # 不读 p["attest_default"]（那是黄灯那一刻的快照，人改文件在其后），也不看
        #   p["actions"]（同理）—— 以当前盘面现算，否则「先改文件再点认证」会被挡在门外。
        return _do_attest(req.stage or _attest_default(sid), req.note, cur_sid=sid)

    # ⑤ 确认读题（⓪）：把核对过的题面与分类落盘，然后从 ① 文献定向 起跑。
    #   只有这一处做**文件搬运** —— 因为 `run_stage` 里"阶段执行期间改 request/data
    #     就判 unverified"（见 `_intake_unconfirmed` 上面那段），搬文件绝不能在
    #     阶段内做。放在这里 = 链没在跑，安全。
    if req.action == "confirm":
        if sid != "intake":
            raise HTTPException(400, "「确认」只在 ⓪ 读题那盏灯上有意义")
        return await _do_intake_confirm(stage, p, req)

    # ④ 接受并披露：必须写机器可读的豁免，不能只写 reason 散文
    if req.action == "disclose":
        rec = {"digest": _input_digest(stage), "at": datetime.now().isoformat(), "note": req.note}
        w = _load_waivers(); w[sid] = rec; _save_waivers(w)
        state["waived"][sid] = rec
        _append_residual(stage, p.get("reason", ""), p.get("verdict", ""),
                         p.get("issues") or [], req.note, state.get("run_id", ""))
        _set_pending(None)
        log(f"✅ [{sid}] 用户选择接受并披露 → 已写 runtime/quality/waivers.json 与 "
            f"reports/_KNOWN_WRITING_RESIDUALS.md；**输入一变该豁免自动失效、门禁重新生效**")
        # 「披露」的语义是**这一步收下了、继续往下**⇒ 起点是**它的下一阶段**，不是它自己。
        #   用 sid 当起点会让链走到它、命中豁免、`continue` —— 结果一样，但白走一趟；
        #   而如果它是最后一个阶段，起点 = 链尾 ⇒ run_all 直接去收交付。
        _nxt = STAGE_IDX[sid] + 1
        return {"ok": True, "action": "disclose",
                "resume_from": (STAGES[_nxt]["id"] if _nxt < len(STAGES) else ""),
                "resume_index": _nxt, "resumed": True}

    raise HTTPException(400, f"未知动作 {req.action}")


@app.post("/api/decision")
async def decision(req: DecisionReq):
    # 起链放在端点：_apply_decision 只改状态，测试才能直接 await 它驱动整条路径
    r = await _apply_decision(req)
    if r.get("resumed"):
        # 续跑的**起点**必须由决定说了算：
        #   无条件 `_start_chain()` 的话 ⇒ `run_all` 从 ① 走一遍。①–④ 靠回执能跳过，
        #   但**上游那条裁决过期的门禁**（这里是 ⑤ 结果可信度审计）会在复用之后被
        #   `run_all` 当场真跑一遍 ⇒ 点「接受并披露」⑪、期望去 ⑫，结果**回到了 ⑤**。
        #   `_apply_decision` 一直有 `resume_from` 字段，端点却从没读过它 —— 这次接上。
        _set_start_index(r.get("resume_index", 0))
        _start_chain()
    return r

@app.get("/api/hil")
async def hil():
    """「手工修复」面板的数据：逐条未解决项 + **改哪儿（文件:行）** + 判词原文。

    为什么单独一个端点，而不是塞进 `/api/state`：
      ① **位置会变** —— 人每改一处，它下面所有行的行号就挪了；每次打开面板都现读现算才对。
      ② **`attest_default` 必须现算** —— 它自己的 docstring 就写着「那个值是黄灯亮起那一刻
         算的，而人**总是先改文件、再点认证**」。可面板一直读的是 `pending` 里的**快照**，
         于是"人改完文件之后，认证按钮反而不出现"（把 ⑤ 判词要求的三处
         改完之后，按钮整个不见了 —— 因为它算的是改之前的盘面）。这里改成调用时现算。
    """
    p = state.get("pending") or {}
    sid = p.get("stage")
    stage = next((s for s in STAGES if s["id"] == sid), None)
    issues = []
    for it in (p.get("issues") or []):
        if not isinstance(it, dict):
            continue
        issues.append({
            "id": it.get("id"), "severity": it.get("severity"), "category": it.get("category"),
            "evidence": it.get("evidence"), "fix": it.get("fix"), "recheck": it.get("recheck"),
            "targets": _locate_targets(it.get("evidence"), it.get("fix"), it.get("recheck")),
        })
    try:
        att = _attest_default(sid) if sid in STAGE_IDX else None
    except Exception:                          # noqa: BLE001 —— 面板数据，绝不许 500
        att = None
    return {"stage": sid, "stage_name": (stage or {}).get("name", ""),
            "report": (stage or {}).get("report", ""), "reason": p.get("reason"),
            "attest_default": att, "issues": issues,
            "advisories_total": p.get("advisories_total", 0)}


@app.post("/api/pause")
async def pause():
    """**暂停**：从当前阶段停下，并**转黄灯** —— 面板上接着选「再试一次 / 回退到某阶段 /
    接受并披露 / 我已手工修好」。当前阶段的在跑进程会被收掉，回来时从它重试。

    与「停止」的分工：暂停把**出口留好**（停在这儿还能接着做）；停止是硬停，不给决策入口。
    """
    if not state["running"]:
        raise HTTPException(400, "链没在跑，无需暂停")
    state["stopping"] = True          # 与停止复用同一个"请求中断"信号
    state["pause_to_halt"] = True     # 区别只在收尾时要不要建黄灯
    _clock_persist()
    log("收到暂停请求：从当前阶段停下并转黄灯，由你决定下一步")
    return {"ok": True}


@app.post("/api/stop")
async def stop():
    """**停止**：硬停，不给决策面板（黄灯若已亮着则一并收起）。

    要"停下但保留出口"用 `POST /api/pause`。
    """
    state["stopping"] = True
    state["pause_to_halt"] = False    # 硬停：即使之前请求过暂停，也不建黄灯
    if state.get("halt_gate"):
        state["halt_gate"] = False
        state["halt_reason"] = ""
        _set_pending(None)
        for sid, value in state["stages"].items():
            if value == "awaiting_user":
                state["stages"][sid] = "stopped"
    _clock_persist()          # 尽快落盘，防停机丢累计计时
    return {"ok": True}

class AutopilotReq(BaseModel):
    on: bool

@app.post("/api/autopilot")
async def autopilot(req: AutopilotReq):
    """一键托管开关。开着时驱动自动做两件事：
      · 阶段**超时** ⇒ 自动延长本次限时；
      · 有 `recommended`（agent 推荐的回退目标）⇒ 自动按它回退。
    再点一次即取消。其余挂起（没有可自动执行的动作）照旧留给用户 —— 托管不是无条件放行。
    """
    state["autopilot"] = bool(req.on)
    state["autopilot_armed"] = False          # 关掉时顺手撤销还没落实的那一步
    if req.on:
        log("🤖 已开启一键托管：阶段超时自动延长、有推荐目标时自动按其回退"
            "（再点一次取消）")
    else:
        log("🤖 已取消一键托管：之后的挂起都交给你决定")
    # 开启时若**此刻**正挂着一个可自动执行的决定，立刻落实（不用等到下一次挂起）
    if req.on:
        try:
            await _autopilot_fire()
        except Exception as exc:                        # noqa: BLE001
            log(f"⚠️ 托管开启时自动执行异常（已转人工）：{exc}")
    emit("state", state2dict())
    return {"ok": True, "autopilot": state["autopilot"]}

@app.get("/api/state")
async def get_state(): return state2dict()

@app.get("/api/files")
async def files(kind: str = "reports"):
    base = REPORTS if kind == "reports" else ROOT / "figures"
    if not base.exists(): return {"files": []}
    out = []
    for p in sorted(base.rglob("*.md" if kind == "reports" else "*.png"))[:200]:
        out.append({"name": str(p.relative_to(ROOT)).replace("\\","/"), "size": p.stat().st_size,
                    "mtime": datetime.fromtimestamp(p.stat().st_mtime).isoformat()})
    return {"files": out}


async def _save_inbox(files, paths):
    """一键传文件夹：保住结构收进 `request/_inbox/`，然后自动起链读题。

    这里不返回**机械抽取**的题面当确认页的对照列：机械读题整条已拆
      （见 `_intake_panel_fields` 的说明），上传现在只负责把原件收好。
    """
    if paths and len(paths) != len(files):
        raise HTTPException(400, f"相对路径的条数与文件数对不上（{len(paths)} vs {len(files)}）"
                                 "—— 请用页面上的「选文件夹」，不要手工拼 FormData")
    rels = list(paths) if paths else [(f.filename or "") for f in files]
    sizes = [getattr(f, "size", None) for f in files]
    know_sizes = sizes if all(isinstance(x, int) for x in sizes) else None
    try:
        keep, skipped = upload_guard.plan_inbox(rels, know_sizes)
    except upload_guard.UploadRejected as exc:
        raise HTTPException(400, str(exc)) from exc
    keep_set = set(keep)
    # 先写 `_inbox.new/` 再整目录切换：中途失败不能留下半份 inbox（那会让确认页少列文件，
    #   而用户以为传完了）—— 与 `delivery.package` 的"先建新的再切换"同一手法。
    staging = ROOT / INBOX_NEW_REL
    if staging.exists():
        shutil.rmtree(staging, ignore_errors=True)
    saved, total = [], 0
    try:
        for f, raw in zip(files, rels):
            rel = upload_guard.safe_rel_path(raw)
            if rel not in keep_set:
                continue
            dst = staging / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            n = 0
            with open(dst, "wb") as out:
                while True:                            # 流式：`await f.read()` 会整份进内存
                    chunk = await f.read(1 << 20)
                    if not chunk:
                        break
                    n += len(chunk)
                    total += len(chunk)
                    if n > upload_guard.MAX_FILE_BYTES or total > upload_guard.MAX_TOTAL_BYTES:
                        raise HTTPException(
                            400, "超过体量上限（单件 "
                                 f"{upload_guard.MAX_FILE_BYTES // (1024 * 1024)} MiB / 整批 "
                                 f"{upload_guard.MAX_TOTAL_BYTES // (1024 * 1024)} MiB）"
                                 "—— 只传这道题需要的材料；确实需要就这么传的话告诉我，我调上限")
                    out.write(chunk)
            saved.append(rel)
    except HTTPException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    except OSError as exc:
        shutil.rmtree(staging, ignore_errors=True)
        raise HTTPException(500, f"落盘失败：{exc}") from exc
    if not saved:
        shutil.rmtree(staging, ignore_errors=True)
        raise HTTPException(400, "这批上传里没有可用的文件")
    old = _inbox_path()
    if old.exists():
        shutil.rmtree(old, ignore_errors=True)
    try:
        staging.rename(old)
    except OSError as exc:
        raise HTTPException(500, f"切换 _inbox 失败：{exc}") from exc
    log(f"📥 上传文件夹：收了 {len(saved)} 件到 {INBOX_REL}/"
        + (f"（跳过 {len(skipped)} 件系统垃圾：{'、'.join(skipped[:3])}…）" if skipped else "")
        + " ⇒ 自动开始读题（读完会停下等你确认）")
    # 自动起链读题。只跑 ⓪：`_intake_unconfirmed()` 会在它跑完后把链停在黄灯上。
    # 起链前**再查一次**运行态：入口那次 409 检查与这里
    #   隔着一整段流式落盘（大文件夹要几十秒），中间完全可能已经有链起来了（用户点了「开始全链」、
    #   或上一批上传的自动起链还在跑）⇒ 无条件起链会变成**两条链同时写产物与回执**，
    #   而那正是 `_start_chain` 自己警告过的场景。这里收下文件但不起链，并说清怎么继续。
    if state["running"]:
        log("⚠️ 上传已收好，但**有链正在跑** ⇒ 不起新链。停掉之后从 ⓪ 重跑即可读题。")
        return {"ok": True, "saved": saved, "skipped": skipped, "reading": False,
                "note": "文件已收好；但有链正在跑，没有自动开始读题 —— 停掉之后从 ⓪ 重跑即可。"}
    state["retry_cap"] = {}
    state["seed_hints"] = {}
    state["attempts"] = {}
    state["force_retry"] = None
    _set_start_index(0)
    _start_chain()
    return {"ok": True, "saved": saved, "skipped": skipped, "reading": True}


@app.get("/api/intake")
async def intake_texts():
    """读题确认页要的**长文本**：AI 读到的那份题面。

    为什么单开一个端点、而不是塞进 `/api/state`：那个 payload 每 4 秒轮询一次，
      把几万字的题面塞进去会把面板拖慢（`_intake_panel_fields` 里刻意只给路径，就是为了这条）。
    这里不再返回**机械抽取**的正文与"机械 vs AI"的逐字差异：
      机械读题整条已拆 —— 它对扫描件与多列排版基本没用，而"对照原题"用户手上有 PDF，
      自己做得更好（确认页现在是"内嵌原 PDF + 渲染后的 AI 题面"）。
    """
    fields = _intake_panel_fields()
    prop = _intake_proposal()
    pr = prop.get("problem") if isinstance(prop.get("problem"), dict) else {}
    return {"ok": True, "ai": str((pr or {}).get("text") or ""),
            "report_path": fields.get("report_path", "")}


@app.post("/api/upload")
async def upload(kind: str = Form(...), files: list[UploadFile] = File(...),
                 paths: list[str] = Form(default=[])):
    """上传。kind 四种：

      · `folder`（**主入口**）：一键传整个文件夹 —— 保住目录结构收进
        `request/_inbox/`，然后**自动起链读题**，读完停下等人确认（见 `_intake_unconfirmed`）。
      · `problem` / `attachment` / `data`：老三条（CLI/回退/回归仍在用），行为不变。
    """
    if state["running"]:
        raise HTTPException(409, "运行中不能更换题目或数据，请先停止")
    if kind == "folder":
        return await _save_inbox(files, paths or [])
    saved = []
    try:
        if kind == "problem":
            target = ROOT / "request"; target.mkdir(exist_ok=True)
            if not files: raise HTTPException(400, "题面不能为空")
            f0 = files[0]; raw = await f0.read()
            # 空内容必须拒：`/api/problem-text`（纯文本路径）明确拒绝空文本，而这里
            #   照样写盘的话 —— 一个 0 字节的 p.txt 就能把 request/problem.md 清空，
            #   且 _source_digest 变化会连带把旧产物归档，链随后以空题面开跑。
            if not raw.strip():
                raise HTTPException(400, "上传的题面文件是空的（0 字节），已拒绝")
            name = (f0.filename or "problem").lower()
            if name.endswith((".pdf",)):
                (target / "problem.pdf").write_bytes(raw); saved.append("request/problem.pdf")
                import fitz
                text = "\n".join(p.get_text() for p in fitz.open(stream=raw, filetype="pdf"))
                if len(text.strip()) < 15:
                    raise HTTPException(400, "该 PDF 无文字层（像是扫描件）。请上传可复制文字的 PDF，或把题面贴成 .txt")
                (target / "problem.md").write_text("# 上传的题目（自 problem.pdf 提取）\n\n" + text, encoding="utf-8")
                saved.append("request/problem.md（PDF 提取文本）")
            elif name.endswith((".md", ".txt")):
                (target / "problem.md").write_bytes(raw); saved.append("request/problem.md")
            elif name.endswith((".doc", ".docx")):
                raise HTTPException(400, "暂不直接支持 .doc/.docx 题面；请在 Word 里另存为 PDF 或用复制粘贴存成 .txt 再传")
            else:
                raise HTTPException(400, f"题面只支持 .pdf/.md/.txt（收到 .{name.rsplit('.',1)[-1]}）")
        else:
            if kind == "attachment": target = ROOT / "request" / "attachments"
            elif kind == "data": target = ROOT / "data"
            else: raise HTTPException(400, "kind 必须是 problem/attachment/data")
            target.mkdir(parents=True, exist_ok=True)
            for f in files:
                name = Path(f.filename or "file").name
                data = await f.read()
                (target / name).write_bytes(data)
                saved.append(str((target / name).relative_to(ROOT)).replace("\\", "/"))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))
    log(f"上传完成: {saved}")
    return {"ok": True, "saved": saved}

@app.post("/api/problem-text")
async def set_problem_text(text: str = Form(...)):
    """手动覆盖题面（PDF 抽取不准时用）。"""
    if state["running"]:
        raise HTTPException(409, "运行中不能更换题面，请先停止")
    t = text.strip()
    if not t: raise HTTPException(400, "题面不能为空")
    (ROOT / "request").mkdir(exist_ok=True)
    (ROOT / "request" / "problem.md").write_text(t, encoding="utf-8")
    log("已手动覆盖 request/problem.md")
    return {"ok": True, "path": "request/problem.md"}

@app.get("/api/workspace")
async def workspace():
    """列出 request/ 与 data/ 下现有文件，方便确认题目已放好。"""
    out = {"request": [], "data": []}
    for sub in ("request", "data"):
        d = ROOT / sub
        if d.exists():
            for p in sorted(d.rglob("*")):
                if p.is_file():
                    out[sub].append(str(p.relative_to(ROOT)).replace("\\", "/"))
    return out

@app.get("/api/pdf")
async def pdfs():
    paper = ROOT / "paper"; out = []
    if paper.exists():
        for p in sorted(paper.rglob("*.pdf")):
            out.append({"name": str(p.relative_to(ROOT)).replace("\\", "/"), "size": p.stat().st_size,
                        "mtime": datetime.fromtimestamp(p.stat().st_mtime).isoformat()})
    return {"pdfs": out}

#: 「测试连接」的墙钟上限。够慢网络握一次手 + 回一句短话；再久就不是"慢"了，是通不了。
TEST_CONNECT_TIMEOUT = 120


class ModelConfigReq(BaseModel):
    base_url: str | None = None
    auth_token: str | None = None
    model: str | None = None


@app.get("/api/model_config")
async def get_model_config():
    """开屏配置页问一次：配好了没、现在生效的是什么。

    为什么不塞进 `/api/state`：那个 payload 每 4 秒轮询一次，而"配没配好"是**启动期**的
      一次性状态（同 `/api/hil`、`/api/intake` 那两条"位置会变/长文本别进轮询"的纪律）。
    """
    return {"ok": True, **_model_config_status()}


@app.post("/api/model_config")
async def set_model_config(req: ModelConfigReq):
    """保存配置：写 `.env` + **直写 `os.environ`** + 重跑代理策略。

    为什么必须直写 `os.environ`：`_load_dotenv()` **只在 import 期跑一次**（`:102`），而且
      `:95-96` 是"已存在的环境变量优先" ⇒ 从带 `ANTHROPIC_*` 的 shell 里起的进程（VSCode
      集成终端就是这样）会把刚写进文件的值**静默挡回去**，表现就是"存了却没生效"。
    为什么不重启也不担心回执：`.env` 不进任何阶段的指纹（`:2072-2074` 那条设计约束），
      阶段 agent 是子进程、会继承新的 `os.environ` ⇒ 就地生效是安全的。
    留空 = 不改这一项（见 `_write_dotenv_keys`）：密钥在面板上只显示打码值，
      用户不改就不该重填、更不该被抹掉。
    """
    values = {"ANTHROPIC_BASE_URL": (req.base_url or "").strip() or None,
              "ANTHROPIC_AUTH_TOKEN": (req.auth_token or "").strip() or None,
              "ANTHROPIC_MODEL": (req.model or "").strip() or None}
    try:
        wrote = _write_dotenv_keys(values)
    except ValueError as exc:                    # 值里含换行等非法内容 ⇒ 400，别写坏 .env
        raise HTTPException(400, str(exc)) from exc
    except OSError as exc:                       # 读不出来 / 写不进去 —— **不**静默继续（见 ①）
        raise HTTPException(500, f".env 读写失败：{exc} —— 文件没被改动，先确认它可读写") from exc
    for k, v in values.items():
        if v is not None:
            os.environ[k] = v
    _apply_proxy_policy()
    log("🧩 模型配置已更新：" + _model_config_note())
    return {"ok": True, "wrote": wrote, **_model_config_status()}


@app.post("/api/model_config/test")
async def test_model_config(req: ModelConfigReq | None = None):
    """真打一次 `claude -p`，看能不能通 —— 这就是"测试连接"。

    为什么**不**自己发 HTTP 打 `ANTHROPIC_BASE_URL`（`:134-143` 有这条约定）：
      `claude`（Node/undici）只读 `HTTPS_PROXY` 这类**环境变量**，而 Python（urllib/requests）
      读 **Windows 注册表系统代理**（梯子改的就是它）。两条路的代理来源不同 ⇒ 用 Python 测的是
      **另一条网络路径**，测通了真跑仍可能不通、反之亦然。所以这里照 `_claude_worker` 的 env
      构造（`os.environ.copy()` + `_apply_proxy_policy(env)`）spawn 一次真调用。
    `req` 是**可选的**覆盖值：面板上刚填、**还没保存**的那三个键。给了就按它测 —— 否则
      填完点"测试连接"，测的是**上一条**配置，通了也说明不了他刚填的这组能用。
      覆盖只作用于**这次子进程的 env 副本**，不写文件、也不动 `os.environ`。
    用**默认输出**（不是 `stream-json`）：这里只要"通没通、回没回话"，不需要逐行解析。
    绝不缓存"这次成功了" —— 每次都真打一次。缓存的"配好了"会在密钥过期后骗人。
    """
    cbin = _find_claude() or CLAUDE
    if cbin is None:                             # 正常情况下 import 期就 SystemExit 了，兜底而已
        return {"ok": False, "detail": "没找到 claude 可执行文件（在 .env 里设 WEBDRIVER_CLAUDE）",
                "proxy": _proxy_note(), "note": _model_config_note()}
    ov_base = (req.base_url or "").strip() if req else ""
    env = os.environ.copy()
    if req:
        for key, val in (("ANTHROPIC_BASE_URL", ov_base),
                         ("ANTHROPIC_AUTH_TOKEN", (req.auth_token or "").strip()),
                         ("ANTHROPIC_MODEL", (req.model or "").strip())):
            if val:
                env[key] = val
    # 代理策略必须按**这次用的端点**推（见 `_apply_proxy_policy` 的 `base_url` 参数）
    _apply_proxy_policy(env, base_url=ov_base or None)
    env["CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS"] = "0"   # 与真调用同一条（`:2000`）
    cmd = [str(cbin), "-p", "只回两个字：可以"]
    t0 = time.time()
    try:
        # 必须丢线程跑：这是同步阻塞调用，直接放在 async 端点里会把整个事件循环（含 SSE 与
        #   4 秒轮询）一起冻住，面板在测试期间完全不响应。
        p = await asyncio.to_thread(
            subprocess.run, cmd, cwd=str(ROOT), env=env, capture_output=True,
            text=True, encoding="utf-8", errors="replace", timeout=TEST_CONNECT_TIMEOUT)
    except subprocess.TimeoutExpired:
        return {"ok": False, "detail": f"{TEST_CONNECT_TIMEOUT} 秒内没有回应 —— 多半是端点或代理不通",
                "ms": int((time.time() - t0) * 1000), "proxy": _proxy_note(),
                "note": _model_config_note()}
    except OSError as exc:
        return {"ok": False, "detail": f"起不来：{exc}", "proxy": _proxy_note(),
                "note": _model_config_note()}
    # 把回显里的密钥抹掉再往回送：CLI 报认证错时**有可能**把请求头/令牌打进 stderr，
    #   而这段会原样进浏览器与日志。这里只是兜底 —— 按长度阈值来，短串不动（免得把
    #   正常文本里的子串误抹）。
    def _scrub(s):
        tok = env.get("ANTHROPIC_AUTH_TOKEN") or env.get("ANTHROPIC_API_KEY") or ""
        return s.replace(tok, _mask_key(tok)) if len(tok) > 8 else s
    out = _scrub((p.stdout or "").strip())
    err = _scrub((p.stderr or "").strip())
    return {"ok": p.returncode == 0 and bool(out),
            "returncode": p.returncode, "ms": int((time.time() - t0) * 1000),
            "reply": out[:400], "detail": (err or out)[:600],
            "proxy": _proxy_note(), "note": _model_config_note()}


@app.get("/api/browse")
async def browse(path: str = ""):
    """列**子目录名**（产物路径选择器用）。只给目录名，不给文件、不给大小/内容。

    为什么必须有它：
      浏览器出于安全**不会**把本地文件夹的绝对路径交给网页（`webkitdirectory` 只给相对路径），
      所以"点着选一个目录"这件事只能由服务端来列。
    为什么**不**套 `/api/read` 那条 `is_relative_to(ROOT)`：产物目录**允许落在仓外**
      （`lib/delivery/core.py:resolve_output_dir`，`regression/test_delivery.py` 钉着），
      而"选一个仓外目录"必须先能浏览到仓外 —— 套 ROOT 包含性会让这条路走不通。
    因此这是一条**比 `/api/read` 宽**的读端点：它能在本机任意目录里**枚举子目录名**。
      可接受的边界是：① 服务只绑 `127.0.0.1`；② 有 Origin 中间件挡跨站驱动（`:456` 起，注释里
      记着攻击形态）；③ 它**只回目录名**，不回文件、不回内容、不回大小/mtime；④ 不跟随
      符号链接/联结点（照 `lib/delivery/safe_walk.is_reparse_point`），免得顺着软链跑出预期范围。
      要收紧的话，收在这里：把下面的 `roots` 换成白名单。
    """
    raw = str(path or "").strip()
    # **UNC 一律拒**：这条端点走 GET，而 Origin 中间件只查
    #   非 GET 方法（见 `no_store` 的注释：simple request 才需要挡）。于是恶意页面可以用
    #   `GET /api/browse?path=\\攻击者主机\share` 让**本机**去连那台机器的 SMB（NTLM 凭据转发面）。
    # 判据必须**归一化分隔符之后再判**，而且要判**解析之后**的路径：Windows 把 `/` 与 `\`
    #   当同一个字符，只看 `\\` / `//` 开头会被这些写法绕开（三条都
    #   一路走到了 `is_dir()`）：
    #       `\/evil-host\share`   `/\evil-host/share`   `./\\evil-host/share`
    #   归一化 + `resolve()` 之后再查，这几条、三反斜杠、`\\?\` 扩展前缀就都盖住了。
    def _is_unc(p):
        s = str(p).replace("/", "\\")
        return s.startswith("\\\\") or Path(s).drive.startswith("\\\\")
    if not raw:
        base = ROOT
    elif _is_unc(raw):
        raise HTTPException(400, "不支持网络路径（UNC）—— 产物目录请选本机磁盘上的目录")
    else:
        base = Path(raw) if Path(raw).is_absolute() else ROOT / raw
    try:
        base = base.resolve()
    except OSError as exc:                                   # 坏路径（含非法字符）
        raise HTTPException(400, f"路径读不了：{exc}") from exc
    if _is_unc(base):                                        # 解析之后又变成 UNC 的那种
        raise HTTPException(400, "不支持网络路径（UNC）—— 产物目录请选本机磁盘上的目录")
    if not base.is_dir():
        raise HTTPException(404, f"不是一个目录：{base}")
    # 丢线程 + `os.scandir`：
    #   ① 这是同步 IO，直接放在 async 端点里会把整个事件循环（SSE、4 秒轮询）**冻住**；
    #   ② `sorted(iterdir())` 会先把**整层**目录物化再排序，500 的上限在排序**之后**才生效
    #      ⇒ 一个几十万项的目录（或慢速网络盘）照样能把内存与时间吃满。`scandir` 边走边收、
    #      够了就停，且 `entry.is_dir()` 直接来自目录扫描（不再每项一次 stat）。
    def _list():
        # `entry.is_symlink()` 免费但从目录扫描里来，只认符号链接；Windows 的**目录联结点**
        # 同样是重解析点，得走 `is_reparse_point`（一次 stat）—— 好在循环本身就卡在 500 项。
        from lib.delivery.safe_walk import is_reparse_point
        names, more = [], False
        with os.scandir(base) as it:
            for entry in it:
                try:
                    if entry.is_dir() and not entry.is_symlink() \
                            and not is_reparse_point(Path(entry.path)):
                        # 早停判据放在"这一项**确实会被收进 names**"之后（
                        #   在循环头上判 `len(names) >= 500` 的话，而一个目录里
                        #   完全可能有一堆**文件**夹在目录之间 ⇒ 收满 500 个目录之后，只要后面
                        #   还有任意一个条目（哪怕又是文件），就会把 truncated 报成真 ⇒
                        #   面板提示"目录太多只列了前 500 个"，其实**已经列全了**。
                        if len(names) >= 500:
                            more = True
                            break
                        names.append(entry.name)
                except OSError:
                    continue
        return sorted(names, key=str.lower), more
    try:
        dirs, truncated = await asyncio.to_thread(_list)
    except OSError as exc:
        raise HTTPException(403, f"列不了这个目录：{exc}") from exc
    parent = "" if base.parent == base else str(base.parent)   # 到了盘根就没有上级
    return {"ok": True, "path": str(base), "parent": parent, "dirs": dirs,
            "truncated": truncated,
            "is_repo": base == ROOT.resolve(),
            "is_output": base == _delivery_dir().resolve()}


@app.get("/api/read")
async def read(path: str):
    # 必须用**路径包含关系**，不能用字符串前缀：`str(fp).startswith(str(ROOT))` 会把
    #   名字以工作区名开头的**兄弟目录**放进来 —— ROOT=`…\w` 时
    #   `GET /api/read?path=../w-evil/secret.txt` 返回 200 并吐出目录外的文件内容。
    #   原来的 `exists()` 也不够：`path=""` 时 `ROOT/"" == ROOT`，读到的是**目录**，
    #   抛 PermissionError → 未捕获的 500。改成要求「非空 + 在根内 + 是文件」。
    if not path.strip():
        raise HTTPException(400, "path 不能为空")
    fp = (ROOT / path).resolve()
    if not fp.is_relative_to(ROOT.resolve()): raise HTTPException(403, "越界")
    if not fp.is_file(): raise HTTPException(404, "不存在或不是文件")
    if fp.suffix.lower() in (".png",".jpg",".pdf"):
        return FileResponse(str(fp))
    txt = fp.read_text(encoding="utf-8", errors="replace")
    return {"text": txt}

@app.get("/api/stream")
async def stream():
    q = asyncio.Queue(); _sub.append(q)
    async def gen():
        try:
            yield "data: " + json.dumps({"evt":"hello"}) + "\n\n"
            while True:
                msg = await q.get()
                yield "data: " + msg + "\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            if q in _sub: _sub.remove(q)
    return StreamingResponse(gen(), media_type="text/event-stream")

app.mount("/static", StaticFiles(directory=str(ROOT/"lib"/"web"/"static")), name="static")

@app.get("/", response_class=HTMLResponse)
async def index():
    # 必须 `no-store`：整个前端是**内联**在这一个文件里的，浏览器一旦
    #   缓存住旧版，驱动换了新逻辑、面板却还在发老请求 —— 用户会看到"功能没生效"，
    #   而重启驱动**不会**让浏览器重新取页面（修好的「自动开始」按了没反应）。
    #   面板本身每次都要 `/api/state`，多这几百字节的 HTML 传输没有代价。
    return HTMLResponse((ROOT/"lib"/"web"/"static"/"index.html").read_text(encoding="utf-8"),
                        headers={"Cache-Control": "no-store, must-revalidate",
                                 "Pragma": "no-cache", "Expires": "0"})

def _restore_stale_instr():
    """启动时从**回执**反推「按旧要求交付」的那批阶段，填回 `state["stale_instr"]`。

    为什么必须反推：`state["stale_instr"]` 是**内存态**，而阶段的
      `done(stale-instr)` 是**持久态**（在回执里）。重启之后面板会写成「已完成交付」、
      那条蓝条也消失 —— 于是「这一阶段是按旧要求做的、要不要按新要求重来」这个**唯一
      的可见痕迹**没了，人再也想不起来该不该重判。
      判据与 `run_stage` 里那条完全一致：回执里的 `artifacts`/`outputs` 两半都与当前
      一致，**只有 `instructions` 对不上** ⇒ 就是「做法要求变了、产物没变」。
    """
    store = _receipt_store()
    for stage in STAGES:
        sid = stage["id"]
        rec = store.records.get(sid) or {}
        try:
            # 三样都要在同一个 try 里：只兜 `_input_split` 的话，
            #   `_output_digest` 一抛就把**模块导入**打崩 —— 服务根本起不来，
            #   而这是启动期自检，绝不许把服务带崩。
            art_digest, ins_digest = _input_split(stage)
            out_digest = _output_digest(stage)
        except Exception:                       # noqa: BLE001 —— 启动期自检，绝不许把服务带崩
            continue
        # 必须 `_artifact_ok`：蓝条那句「产物仍在盘上，只是按旧要求做的」
        #   不能对着一个**产物根本不在盘上**的阶段说（例如 `fix` 跳过执行却存了回执）。
        if (rec.get("artifacts") != art_digest or rec.get("instructions") == ins_digest
                or not _artifact_ok(stage)):
            continue
        # 判据必须与 `run_stage` 那条**逐条对齐**，否则同一盘面
        #   「重启反推的集合」与「链上算的集合」会不一致：
        #   · ⑨ 这类「产物被下游合法改写」的阶段，outputs 半份**必然**对不上 ——
        #     只看 outputs 就永远反推不出它，蓝条在重启后对它那一格还是消失；
        #   · 门禁的**机械地板**不过时链上不会标 stale（会真跑）—— 反推也必须跟着排除。
        if rec.get("outputs") != out_digest and _taken_over_by(stage) is None:
            continue
        # 机械地板也要**在 try 里**：它会走
        #   `precheck` → `resolve_source`，而那条路现在可能因"清单里的基名有歧义"抛错 ⇒
        #   抛在这里就是把**模块导入**打崩（服务根本起不来、agent 一 import 就死）。
        #   这是启动期自检 —— 按本函数的既定纪律，任何异常都只跳过这一个阶段。
        try:
            if stage.get("gate") and _mechanical_floor(stage) is not None:
                continue
        except Exception:                       # noqa: BLE001 —— 启动期自检，绝不许把服务带崩
            continue
        state["stale_instr"].add(sid)
        if state["stages"].get(sid) in (None, "idle"):
            state["stages"][sid] = ("done(manual)" if store.is_manual(sid)
                                    else "done(stale-instr)")


def _recover_pending_markers():
    """启动时把「**开跑前搬走、进程却没了**」的那些原件搬回原位。

    为什么必须有它（"任意阶段如果没电了暂停续跑，会不会出现东西
      丢失的情况，能不能续跑上"）—— 结论是**能续跑，但会丢一份东西、还会连带下游重跑**：

      `_stash_markers_for_restore` 在**开跑前**把报告（门禁连裁决侧车）从 `reports/`
      **搬进** `runtime/quality/_pending_markers/<sid>/`，而把它们搬回去的 `_restore` 只活在
      **那个进程的内存里**。断电 / 硬杀（不是按暂停 —— 那条路会走 `interrupt` 分支并搬回）
      之后它就不存在了 ⇒ 上一份**完好的报告**永远扣在暂存里，`reports/` 里是骨架或空白。
      后果两条：
        ① 被打断的那个阶段：回执已被 `_invalidate_stage` 作废 ⇒ 重跑（这条是对的）；
        ② 它的**下游**：那些报告在 `_input_split` 的 artifacts 半份里 ⇒ 文件不在盘上 ⇒
           指纹成片失配 ⇒ 下游整段重跑（小时级）—— 而那份报告其实完好地躺在暂存里。
      而且**下一轮还会继续恶化**：重跑时 `_stash_markers_for_restore` 见 `tgt.exists()` 就跳过
      ⇒ 新一次的 mapping 是空的 ⇒ 连"打断时搬回"这条兜底也失效了。
      启动时搬回来，盘面就等于"那次跑之前"的样子 ⇒ 下游回执重新成立，而被中断的那一阶段
      自己仍然没有回执 ⇒ 照旧重跑（"不出产物就不许冒充完成"没被破坏）。

    判据（**只在盘上那份不在了、或明显是骨架时才搬回**）：
      · 目标文件不存在 ⇒ 搬回；
      · 门禁且裁决侧车是 `UNVERIFIED`（= §6.1 的骨架）⇒ 搬回；
      · 其余（盘上已有一份像样的新产物）⇒ **不动它**，只记一行日志说明暂存里还留着上一版
        —— 绝不拿旧版冒充新一轮的产物。
    """
    base = _PENDING_MARKERS
    if not base.is_dir():
        return
    for d in sorted(base.iterdir()):
        if not d.is_dir() or d.name not in STAGE_IDX:
            continue
        st = STAGES[STAGE_IDX[d.name]]
        rep = st["report"]
        rels = (["paper/main.pdf"] if rep.startswith("paper") else
                ["reports/" + rep, "reports/" + str(Path(rep).with_suffix(".verdict.json"))])
        for rel in rels:
            stash = d / rel.replace("/", "_")
            target = ROOT / rel
            if not stash.is_file():
                continue
            if target.exists() and not _looks_like_a_skeleton(st):
                # 盘上那份是**新的**（不是骨架）⇒ 不搬回，而且**要把暂存清掉**
                #   留着它不只是"多占点地方" ——
                #   `_stash_markers_for_restore` 见 `tgt.exists()` 就跳过、不进 mapping
                #   ⇒ 该阶段的**防半成品机制从此永久失效**（mapping 永远为空，被打断也搬不回
                #   任何东西），而且每次启动都重记一行同样的日志。
                #   删掉是安全的：盘上那份是更新的产物，这份旧副本已经作废（与 in-process 那条
                #   `_restore(drop=True)` 的语义一致）。
                try:
                    stash.unlink()
                    log(f"ℹ️ [{st['name']}] 的 `{rel}`：盘上已是更新的产物 ⇒ 丢弃暂存里的旧副本")
                except OSError:
                    pass
                continue
            try:
                target.parent.mkdir(parents=True, exist_ok=True)
                os.replace(stash, target)
            except OSError as exc:
                log(f"⚠️ 恢复 [{st['name']}] 的 `{rel}` 失败（{exc}）—— 副本仍在 "
                    f"runtime/quality/_pending_markers/{d.name}/ 里")
                continue
            log(f"↩️ [{st['name']}] 上次开跑前搬走的 `{rel}` 已搬回（进程当时被强杀/断电，"
                f"没人搬它）—— 下游回执因此重新成立；该阶段自己没有回执，照旧重跑")
        try:
            d.rmdir()               # 都搬回去了才删目录；还有剩的就留着（人能来取）
        except OSError:
            pass


_clock_load()               # 服务器启动即读回计时（中途关机/中断后续跑累计；收口后待下次 start 归零）
_load_pending()             # 读回待决策项：黄灯状态下重启服务器，面板应当还在
_restore_stale_instr()      # 从回执反推「按旧要求交付」，重启后蓝条不许消失
# `_recover_pending_markers()` **不能放在模块级**：
#   它**搬文件**，而门禁/生产阶段的 agent 正是被鼓励 `from server import STAGES` 的
#   ⇒ agent 一 import 就把**正在被审的那份报告**从 `_pending_markers/` 搬回 `reports/`
#   （把它自己刚写的那一份顶掉），整轮产物与裁决从此对不上。
#   与 `_reap_orphan_agents()` 同一个道理（见下面 `__main__` 里那段说明）。改在 `__main__` 里调。
# `_reap_orphan_agents()` **不能放在模块级**，见 `if __name__ == "__main__"` 里的说明。

if __name__ == "__main__":
    import argparse
    # 收容孤儿必须**只在「作为服务器启动」时**跑，不能放模块级。
    #   模块级的那一版会让**任何一个 import 本文件的进程**执行它 —— 而门禁/生产阶段的 agent
    #   正是被鼓励这么干的（"用项目自带的门禁函数验证产物"，如
    #   `sys.path.insert(0, .../web); from server import STAGES`）。
    #   而 `_register_stage_pid()` 恰恰把**当前正在跑的那个阶段 agent 自己**登记在表里，
    #   `_reap_orphan_agents()` 又只按「pid 在登记表里 且 命令行含项目根」两条匹配 ——
    #   于是 agent 一 import 就把**自己**`taskkill /F /T` 掉，进程以 **exit code 1** 退出。
    #   现场表现：`阶段执行第 1 次失败 rc=1`，无任何诊断，且产物可能已写了一半。
    #   日志里的形态（🧹 行号与 rc=1 行号相邻）：
    #   · 三次都一样：回收器跑完几秒内，某个阶段的 agent 以 rc=1 退出；
    #   · 退出码恒为 1、没有任何诊断输出 —— 典型的"被外部杀掉"。
    #   即「驱动自己的孤儿回收器在杀正在干活的阶段 agent」，不是模型的问题。
    # **先搬回原件，再读黄灯**（顺序不能反）：
    #   `_load_pending()` 在**模块级**（import 时就跑了）—— 那时报告还扣在
    #   `_pending_markers/` 里 ⇒ `_action_set` 判 `_artifact_ok(stage)` 为假
    #   ⇒ 复活的黄灯**丢掉「接受并披露」那个按钮**（明明有产物可披露）。
    #   所以这里再读一次：上面刚把文件搬回盘上，这一次算得出来。
    _recover_pending_markers()
    _load_pending()          # 幂等：按 PENDING_FILE 重建 pending 与阶段状态
    # 把「现在用的是哪套模型配置」打出来（密钥打码）—— 要的就是"显式"：
    #   不打开 `.env` 也能从日志里确认这一轮到底打哪个地址、用哪个模型。
    log(_model_config_note())
    log(_proxy_note())     # 这一轮 API 到底走不走梯子（这类故障的症状是"时好时坏"）
    for line in _DOTENV_BAD:
        log(f"⚠️ .env 这一行没读懂（已跳过）：{line}")
    for line in _RUNTIME_ENV_BAD:
        # 填错一个看门狗参数不该让驱动起不来，但**必须说出来** —— 否则就是"填了没生效"
        log(f"⚠️ 运行参数没读懂（改用默认值）：{line}")
    if DOTENV.is_file() and not _DOTENV_KEYS:
        log(f"⚠️ {DOTENV.name} 在，但里面一条可用配置都没读到 —— 是不是键写错了？"
            f"认这些名字：{'、'.join(_DOTENV_KNOWN)}")
    _reap_orphan_agents()
    ap = argparse.ArgumentParser(); ap.add_argument("--port", type=int, default=8901)
    a = ap.parse_args()
    if _stdout_shadows_the_log():
        # 必须**在第一次 log() 之前**报出来：那时文件还没被覆盖，人还来得及改启动方式。
        print("⚠️ stdout 正指向 runtime/web_run.log —— 这个文件上就有两个写者，"
              "`log()` 写的行会被进程自身的输出缓冲整段覆盖掉（实测丢过一整晚）。"
              "请改成 `python lib/web/server.py > 别处.log 2>&1`，或干脆不重定向。",
              flush=True)
    log(f"web 就绪 http://127.0.0.1:{a.port}  claude={CLAUDE.name}")
    uvicorn.run(app, host="127.0.0.1", port=a.port)
