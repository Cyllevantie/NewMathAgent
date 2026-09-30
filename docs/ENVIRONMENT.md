# 项目 Python 环境

项目专用环境位于 E:\miniconda3\envs\NewMathAgent，配置入口 config/runtime.local.json。它与 conda base、llmxcpg 和其他项目环境隔离；启动器只为当前进程及其子进程配置 PATH，退出后还原，不修改全局 PATH。运行时优先使用配置中的解释器，不靠猜测哪个环境有库。

最快的一条路：双击根目录的 `run.bat` —— 它起 Web 驱动、等它就绪、然后自动打开前端面板（已经在跑就只开面板，不会起第二个）。`.bat` 不走 PowerShell 的脚本策略，所以在这台 `Restricted` 的机器上也不用带 `-ExecutionPolicy Bypass`。逻辑在 `runtime/launch.py`（为什么不全写在 `.bat` 里，见它的 docstring）。

要命令行精细控制时，在项目根目录的 PowerShell 使用：

```powershell
.\run.ps1                              # 只读检查依赖
.\run.ps1 -m unittest discover -s regression -v
.\run.ps1 lib/web/server.py --port 8901
.\run.ps1 -m lib.publication check
.\run.ps1 -m lib.visualization audit
```

若 PowerShell 的脚本策略阻止执行，直接调用 config/runtime.local.json 中的 Python 完整路径。不要为方便运行而全局降低脚本策略。未重启的旧 Web 服务仍使用它启动时的环境。

重建方式：使用已有 Python 3.11 或兼容版本创建专用 venv，再用该 venv 的 python -m pip install -r requirements.txt。安装缓存可通过当前进程 PIP_CACHE_DIR 指向 E:\venvs\pip-cache；不修改系统级 pip 设置。requirements.lock.txt 记录本机经过测试的精确版本。

缺包时先运行 runtime/doctor.py；该检查实际导入库，报告缺失或损坏及版本，不自动安装。未来题目确实需要额外求解器等依赖时，先列明用途、目标环境和安装方式，再按授权补装。不要预装与当前任务无关的大型深度学习或GPU环境。

外部工具分开处理：XeLaTeX 用于现有论文模板，Poppler 用于PDF查看；DrawIO CLI 与 Pandoc 分别用于相应导出，缺少不影响 Matplotlib 数据绘图。Python 包安装到E盘不代表这些外部工具也必须搬家。

本机已配置现有 XeLaTeX、Pandoc 和 DrawIO 的目录，供 run.ps1 启动的程序使用；没有重新安装这些工具。某些沙箱会重写子进程 PATH；遇到此情况使用配置中的工具完整路径。普通 Windows 进程中已验证启动器的 PATH 继承。

**环境状态**：14项直接依赖全部实际导入成功，pip check 无依赖冲突，51项完整回归在同一个新环境全部通过、没有跳过（未启动现有Web服务或模型链）。

## 新设备

仓库侧的配置（端点/密钥/模型档位/产物路径/看门狗参数）跟着仓库走；机器侧的东西没法也不该跟着走，新机器上必须重做下面这几步。按顺序做：

1. **整个目录拷过去**，别挑文件 —— 缺 `lib/web/static/` 会在 import 期就 `RuntimeError`，缺 `config/*.json` 会让对应门禁静默关闭。
2. Python 3.11 + 专用 venv，然后 `pip install -r requirements.txt`（要精确版本就照 `requirements.lock.txt`，它是本机环境的精确版本快照）。
3. 把 `config/runtime.local.json.example` 复制成 `config/runtime.local.json`，填两样：
   `python` = 新机器上那个 venv 的解释器绝对路径（**从这台拷过去的那份写的是本机路径，必须改**）；
   `tool_directories` = xelatex 所在 bin 目录（**硬依赖**，⑨写作/⑭排版/⑮验收全靠它）、pandoc、drawio（后两个可选）。
4. 装 claude CLI（VSCode 的 Claude Code 扩展即可）。驱动不是"调 API"，是每个阶段 shell 出一次 `claude -p`；自动找不到就退不出来，此时在 `.env` 里设 `WEBDRIVER_CLAUDE=<完整路径>`。
5. 把 `.env.example` 复制成 `.env`，填你自己的三样：`ANTHROPIC_BASE_URL`（端点）、`ANTHROPIC_AUTH_TOKEN`（密钥）、`ANTHROPIC_MODEL`（模型）。**一个模型走到底** —— 子 agent 与后台小活也用它，不需要档位别名（`CLAUDE_CODE_SUBAGENT_MODEL` / `ANTHROPIC_DEFAULT_*_MODEL` 那些行项目里已删）。**别用别人给的 `.env`**：里面是别人的密钥。
6. 中文字体：论文模板（ctexart）要 SimSun/SimHei/KaiTi，matplotlib 走 `config/visualization.json` 的字体链（有 DejaVu 兜底，但 DejaVu 没有 CJK 字形 ⇒ 中文会变方框）。英文版 Windows 会缺。
7. 换题：`request/`、`data/` 里现在是上一道题的题面与附件，开跑前替换；`runtime/periodic_check.py` 里的"串题残留"词表也要跟着题换（否则哨兵每次误报）。
8. 放在可写目录（别放 `Program Files`、只读共享、或实时同步/被反病毒锁的目录 —— 驱动 import 期就要建目录写文件）。
9. 双击 `run.bat` —— 起驱动 + 等就绪 + 打开面板。起不来它会列出按概率排的原因。
10. 自检：`run.ps1 runtime/doctor.py`（依赖逐项实际导入）、`python lib/web/healthcheck.py`（96 项结构检查）。

驱动本身是 Windows 专有的（`taskkill`、`ctypes`/`wintypes`、`winreg`、PowerShell 抓进程表），迁移目标得是 Windows。

## 模型 API 与出站代理（项目根 `.env`）

模型端点和密钥放在项目根 `.env`（模板见 `.env.example`），驱动启动时读进 `os.environ`，各阶段子进程自然继承 —— 配置跟着仓库走，不再依赖这台机器上 Claude CLI 自己的登录与设置。启动日志会打印一行（密钥打码）：`🧩 模型配置来源：…`。认的名字就是 CLI 自己的那几个：`ANTHROPIC_BASE_URL`、`ANTHROPIC_AUTH_TOKEN`（或 `ANTHROPIC_API_KEY`）、`ANTHROPIC_MODEL`、`ANTHROPIC_SMALL_FAST_MODEL`；**已存在的环境变量优先**（临时 `$env:X=...` 调试时那个生效，不被文件悄悄盖掉）。空值 = 没设（`KEY=` 只是把那行摆出来，不会往环境里塞空串）。`.env` 里有密钥，别连整个目录一起外发。

**口径：一个模型走到底。** 上面那三个键就够了 —— 主模型、门禁并行 spawn 的子 agent、后台小活全走同一个端点上的同一个模型；那 8 条档位别名（`CLAUDE_CODE_SUBAGENT_MODEL`、`ANTHROPIC_DEFAULT_{HAIKU,SONNET,OPUS,FABLE}_MODEL` 及 `_NAME`）已从项目里删掉，不再需要。

> 唯一一种要补回来的情况：把仓库拷到一台没有 `~/.claude/settings.json` 的新机器上跑，而 CLI 又去要官方模型 id。那时在 `.env` 里补一行 `CLAUDE_CODE_SUBAGENT_MODEL=<上面那个模型名>` 即可（怎么补、为什么，`.env.example` 里写着）。本机不需要 —— 各档位由 `~/.claude/settings.json` 提供。
> `regression/test_local_decoupling.py` 两条哨兵钉着这件事：模板里必须有那三个名字；干净环境（剥掉全部 `ANTHROPIC_*` / `CLAUDE_CODE_*`）下 `.env` 必须给得出它们。若哪天模板里又长出一串 `ANTHROPIC_DEFAULT_*` **必填**键，说明口径被改回去了。

代理由 `FMA_API_PROXY` 控制，默认 `auto`：**只把 API 主机摘出代理**（主机从 `ANTHROPIC_BASE_URL` 推出来，不写死任何厂商域名；换端点自动跟着换），外网搜索照旧走代理。为什么需要它：`claude`（Node/undici）只读 `HTTPS_PROXY` 这类环境变量，而 Python（urllib/requests）读 Windows 系统代理（Clash 的「系统代理」开关改的就是它，注册表 `ProxyServer=127.0.0.1:7897`）—— 梯子一关、7897 没人监听，Python 侧就是 connection refused。`no_proxy` 对两条路都有效，所以策略是"只摘 API"。另两个取值：`system` = 一个字节都不改（和你在终端里直接敲 `claude` 完全一致）、`off` = `NO_PROXY=*` 全部直连。启动日志同样打一行 `🌐 网络：策略=…`，写清这一轮到底走不走梯子。
