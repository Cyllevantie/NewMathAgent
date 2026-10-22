# AGENTS.md（NewMathAgent 工作区）

本目录是 NewMathAgent：分阶段 skill 链（答题姿态好、~1h 成稿）+ 专门化审查角色（统计严谨、门禁化）的数学建模全自动 agent。

**代码在 `lib/` 下**（`lib/web/`、`lib/delivery/`、`lib/publication/`、`lib/visualization/`、`lib/result_contract/`）——
根目录只放入口、数据与配置；命令写 `python lib/web/…` / `python -m lib.<包> …`，别按老的 `web/…` 位置写
（`regression/test_lib_layout.py` 是这条的哨兵）。

## 怎么开始

1. 把赛题放好：`request/problem.md`（题面）、`request/attachments/`、`data/`。
2. 运行总控 skill：让 Codex 调用 `0Start-mathmodel`（或直接说"开始跑 1start"）。
3. 按 `plan.md` + `todo.md` 顺序推进各阶段（阶段清单见 `docs/STAGE_CHAIN.md`）。

## 运行与巡检（盯 Web 驱动时）

- 跑：`python lib/web/server.py --port 8901`，浏览器开 `http://127.0.0.1:8901/`（阶段面板 + SSE 实时控制台）。
  **别把 stdout 重定向到 `runtime/web_run.log`**（`python lib/web/server.py > runtime/web_run.log 2>&1`）。
  那个文件**只能由 `log()` 写**：进程 stdout 是块缓冲的，冲下来时会把 `log()` 刚追加的行整段覆盖，
  于是日志出现成段缺失（成段缺失的日志不能作为事后排查的依据）。
  要留 stdout 就导到别处（如 `<别的>.log`）；启动时会自检并在冲突时打警告。
- 盯：`PYTHONIOENCODING=utf-8 python runtime/periodic_check.py` 打完整快照；`--line` 打一行紧凑快照。输出含阶段状态、控制台最近活动、串题残留词检查、关键产物时间戳。
- 串题残留 = 把整段流水线日志按词表粗扫，防上一赛题领域词泄漏进本次（换题回归哨兵）。**换新题后更新** `runtime/periodic_check.py` 顶部 `DEFAULT_LEAK_WORDS`：把刚跑完那题的领域词 append 进去。
- 定时唤醒（cron/ScheduleWakeup）只在会话空闲触发、会被新消息顶掉；可靠兜底 = 链结束的后台通知，或随时喊一句"看下"手动查。

> 每阶段该读哪些 docs：见 `CLAUDE.md` 的「阶段读取表（唯一权威）」（每阶段 ≤2 份）。 本节不重复。

## 绝不许杀进程（硬红线，与"资源占用"无关）

**默认一个都不杀**：`taskkill` / `Stop-Process` / `kill` / `pkill` / `wmic process delete` 一律不要用，
包括看起来最无害的那种："清掉残留的 stray python"。**唯一例外**是你自己起的进程跑飞了 ——
那种情况也有严格三步（按 pid、先跳过驱动、拿不准就别杀），见 `skills/_references/stage_discipline.md` 第七节。

**为什么**：**驱动本身就是个 `python.exe`**（`lib/web/server.py`），在 `tasklist` 里跟你自己起的
后台计算进程长得一模一样。2026-10-15 真发生过一次：④编码计算的 agent 想清掉"残留 python"，
`tasklist | grep python` 数出两个 python.exe，`taskkill /F` 两个一起杀 —— 一个是它的旧后台任务，
**另一个就是驱动**：控制台窗口当场消失、日志断在半句、这一轮从 ④ 白跑；
而 `taskkill /F` 不给对方任何写日志的机会，事后只能靠翻会话转录才查得出是谁干的。

- **判据是结果，不是命令拼写**：凡是"让驱动结束 / 被重启 / 掉线"的动作一律不许 ——
  `shutdown` / `Restart-Computer` / `logoff`、**杀你的父进程（驱动就是你的父进程）**、
  按映像名杀（`taskkill /IM python.exe`、`Stop-Process -Name python`）、WMI 的 `Terminate()`、
  关掉承载它的控制台窗口 —— 命令里一个禁词都没有，后果一模一样。
- 驱动的 pid 记在 **`runtime/driver.pid`**，也直接写在每个阶段的提示里。**那个 pid 永远不许碰**；
  真要杀什么之前先读它、跳过它，**读不到就按最严处理（一个都不杀）**。
- 要停**自己的**后台任务：用 **`TaskStop`**。它**只停任务本身** —— 它拉起的长计算子进程可能还在跑，
  **那是正常的、不归你管**，不要去扫也不要杀。
- 自己起的进程**跑飞了**（死循环/停不下来）也不能按名字杀：只按 pid（`taskkill /PID <你记下的>`），
  **不许 `/IM`、不许 `/T`**；拿不准就别杀，请人在面板上按 ⏹。
- 看到"像是孤儿"的 python：**不要管** —— 驱动下次启动会自己收容（`_reap_orphan_agents`）。
- 阶段侧的唯一权威表述（含"跑飞了怎么办"的完整步骤）：`skills/_references/stage_discipline.md` 第七节。

## 禁止从 Git 历史取本轮依据（硬红线）

**阶段内禁止使用任何 `git` 命令** —— 尤其 `git show` / `git log` / `git cat-file` /
`git ls-tree` / `git checkout` / `git restore` / `git archive` / `git diff <rev>` /
`git grep <rev>`。只能读取**当前工作区文件**；用户已经删除的归档不得用 git 恢复，
历史版本也不得作为本轮结论、模型结构或探针内核的依据。需要规范/文献时读 `skills/` 与
`docs/`，不要读 Git 历史。

这条由 `runtime/hooks/fma_hook.py`（阶段进程带 `FMA_STAGE` 时拦 git）和
`prompt_for()` 的注入提示机械执行；完整口径见 `skills/_references/stage_discipline.md`
顶部的「Git 历史禁区」。

## 阶段链

编号 ↔ skill ↔ 产出 的账本在 `docs/STAGE_CHAIN.md`（那里还列着「改链时要同步的各个面」）。
编排的权威顺序是 `lib/web/server.py` 的 `STAGES`。

> 这张表刻意不放在本文件里：本文件的全文哈希是各阶段「做法要求」指纹的一部分
> （`lib/web/server.py:_input_split` 的 `ins` 列表），放这里的话加一个阶段就会把每一个阶段
> 标成 `done(stale-instr)` —— 面板一片黄条，而它对各阶段的实际工作毫无信息量。
> 账本挪到 `docs/` 之后，改链不再产生 stale 噪音；真改 SKILL/规范才照旧触发。

Web 驱动门禁：建模失败→analysis，结果审计失败→code，数学论证/跨问失败→write，终验失败→format；评分标终审的论文侧判词→13Repair-by-rubric-verdict 就地改写，不回退 write（模型/数值/实现类判词仍回退各自生产阶段）；有明确前序 target 时按回执返修。**每个阶段只跑一次**，失败或超时一律转黄灯等人决策（不再自动重试、不再自动回退）。缺失、冲突或版本不符的裁决标为未验证，不自动放行。审查阶段只写本阶段报告及裁决 JSON，不修改被审查对象，也不向建模报告追加 APPROVED。此 Web 协议优先于技能中旧的追加标记或耗尽重试后放行规则。直接调用技能时不视为已通过 Web 交付门禁。

**人工决策五选一**（黄灯面板 / `POST /api/decision`）：再试一次 / 回退到所选阶段 / 延长本次限时（仅超时）/ 接受并披露（认下残余，写进论文，标 🔶）/ 我已手工修好（以当前盘面重新认证某阶段，先跑客观校验并留审计痕，标 🔧）。后者是为「agent 反复改不过门禁、人手工改好了却被判失效要重跑」那个死结准备的，见 `lib/web/attest.py`。

**「暂停」与「停止」是两个按钮**（`POST /api/pause` / `POST /api/stop`）：暂停从当前阶段停下
并转黄灯 —— 出口留着，面板上接着选再试/回退/披露/认证；停止是硬停，不给决策面板
（黄灯若亮着一并收起）。区别只在收尾时建不建黄灯，中断信号是同一个。

产物：整链收口时驱动把工作区打包成提交形状的提交件（⑨ 起每阶段收尾先同步一批，链尾收口
做严格对账），落 `<产物根>/提交作品/最新作品/`
（产物根默认 `<项目根>/产物/`，前端工具栏「📁 产物」可改路径与题目标识）。那一层下只放要
提交的东西 + `其余文件/`；白名单与提交清单逐项对账由 `lib/delivery/` 负责（`python -m lib.delivery
check`，对象是提交件根不是产物根）。提交清单 `reports/SUBMISSION_MANIFEST.json` 由 9Paper-writing
收尾写（14Layout-and-format 保有对账与修补权），同时是论文末页清单表的来源。各阶段产物镜像在 `<产物根>/各阶段产物/最新产物/<阶段名>/`。
换题时（输入源变更）驱动把这两个「最新」整目录改名成 `<题目标识_日期_时间>/`（题目标识
留空只用日期）再建两个空的 —— 同一题反复重跑不需要任何清理。回退快照另落
`cache/<题目标识_日期_时间>/<阶段名>/`。`current output/` 是旧位置，不再使用。

维护 Web 编排、排查断点续跑或准备首次升级运行时，阅读 [驱动改动与验证说明](docs/WORKFLOW_RELIABILITY.md)。质量优先，不设全链总时长硬限制。

**动手改这些地方之前，先看一眼 [已知缺口台账](docs/KNOWN_GAPS.md)** —— 那里记着「我们已经知道、但此刻故意没做」的事（含一条真实真空：两个门禁模块的模块级判据表不在任何指纹里，以及一条没有区分性测试的接管口径）。**别把它们当新缺陷重复报一遍**。

## 设计要点（维护时遵守）

- **一个 skill 一个职责**；审查类角色绝不互相合并进同一上下文，评审维度用 Agent 子 agent 各跑各的。
- 审查必须给"具体怎么改"，禁止只写"不行"。
- 建模报告显式含：决策变量 / 目标函数 / 约束条件 / 求解算法 / 机理依据 / 代码契约。
- 论文数值必须来自 reports 报告，禁止编造；图与结果可复现。

绘制空间几何图时读取 [几何图协议](docs/GEOMETRY.md)；写作及终验时读取 [篇幅与公式协议](docs/PUBLICATION.md)，以 config/publication.json 的计页口径验收。

运行代码或服务前读取 [项目环境](docs/ENVIRONMENT.md)，统一使用 config/runtime.local.json 指定的 Python。

## 依赖

- 运行于 Codex（当前模型为 DeepSeek）。
- 写作排版依赖 xelatex（跑 9Paper-writing 前可用 `doctor` 预检环境）。

**改文档 ≠ 全链重跑**：驱动把阶段输入拆成两半 —— 「产物所依据的事实」（题面/数据/前序报告/code/结果）变了自动重做；「做法要求」（SKILL / `_references` / `CLAUDE.md` / 驱动注入指令）变了只标记不重跑（面板上一条蓝条，阶段上标「按旧要求交付」），由人决定要不要按新要求重来。门禁也走同一条路：驱动在字节层面分不清「改了错别字」与「改了判据」，所以不替人做这个判断；要按新判据重判就从该阶段重跑。事实（被审对象）变了仍旧自动重判 —— 那是「论文里的数与你交出去的代码不是一回事」的唯一防线。
