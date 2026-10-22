# CLAUDE.md（NewMathAgent 工作区）

本目录是 NewMathAgent：分阶段 skill 链（答题姿态好、~1h 成稿）+ 专门化审查角色（统计严谨、门禁化）的数学建模全自动 agent。

## 代码在哪

**根目录只放入口、数据与配置；框架代码一律在 `lib/` 下**：`lib/web/`（驱动 + 门禁 + 前端）、
`lib/delivery/`、`lib/publication/`、`lib/visualization/`、`lib/result_contract/`。
`runtime/` 是入口脚本与运行期状态，`skills/` 是阶段指令，`regression/` 是测试。
⇒ 命令一律写 `python lib/web/…`、`python -m lib.publication …`；**别再按老的 `web/…` 位置写**。
`regression/test_lib_layout.py` 会扫全部 skill 与文档，断言"点名的路径真的在、且没人按旧位置写"
（这条哨兵存在的理由：那些路径字符串没有类型检查，漏改一处要等阶段真跑起来才炸）。

## 怎么开始

1. 把赛题放好。推荐：双击 `run.bat` 起服务 → 顶栏「⬆ 上传题目」直接弹文件夹选择框
   （也可以把文件夹拖进面板里那块高亮的拖放区）—— 一键传整个赛题包
   （题面+附件+数据一起，保留子目录）；⓪ 读题会先读一遍并停下等你核对 —— 左栏内嵌原 PDF、
   右栏是渲染后的题面（点「✎ 改文字」可直接改），下面那张表逐行核对"每份原件去哪"，
   有意见就在「更正说明」里写；确认后才从 ① 起跑。
   （也可以手工摆：`request/problem.md`（题面）、`request/attachments/`、`data/`。）
2. 运行总控 skill：让 Claude 调用 `0Start-mathmodel`（或直接说"开始跑 1start"）。
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

## 绝不许杀进程（硬红线，与"资源占用"无关）

**默认一个都不杀**：`taskkill` / `Stop-Process` / `kill` / `pkill` / `wmic process delete` 一律不要用，
包括看起来最无害的那种："清掉残留的 stray python"。**唯一例外**是你自己起的进程跑飞了 ——
那种情况也有严格三步（按 pid、先跳过驱动、拿不准就别杀），见 `skills/_references/stage_discipline.md` 第七节 7.3。

**为什么**：**驱动本身就是个 `python.exe`**（`lib/web/server.py`），在 `tasklist` 里跟你自己起的
后台计算进程长得一模一样。2026-10-15 真发生过一次：④编码计算的 agent 想清掉"残留 python"，
`tasklist | grep python` 数出两个 python.exe，`taskkill /F` 两个一起杀 —— 一个是它的旧后台任务，
**另一个就是驱动**：控制台窗口当场消失（`launch.py` 直接跑 `python.exe`，进程一死窗口就没了）、
日志断在半句、这一轮从 ④ 白跑；而 `taskkill /F` 不给对方任何写日志的机会，
事后只能靠翻阶段 agent 的会话转录才查得出是谁干的。

- **判据是结果，不是命令拼写**：凡是"让驱动结束 / 被重启 / 掉线"的动作一律不许 ——
  `shutdown` / `Restart-Computer` / `logoff`、**杀你的父进程（驱动就是你的父进程）**、
  按映像名杀（`taskkill /IM python.exe`、`Stop-Process -Name python`）、WMI 的 `Terminate()`、
  关掉承载它的控制台窗口 —— 命令里一个禁词都没有，后果一模一样。
- 驱动的 pid 记在 **`runtime/driver.pid`**（启动时更新，正常退出时撤掉），也**直接写在每个阶段的提示里**。
  **那个 pid 永远不许碰**；真要杀什么之前先读它、跳过它，**读不到就按最严处理（一个都不杀）**。
- 要停**自己的**后台任务：用 **`TaskStop`**。注意它**只停任务本身** —— 它拉起的长计算子进程可能
  还在跑，**那是正常的、不归你管**，不要去扫也不要杀。
- 自己起的进程**跑飞了**（死循环/停不下来）也不能按名字杀：只按 pid（`taskkill /PID <你记下的>`），
  **不许 `/IM`、不许 `/T`**；拿不准就别杀，请人在面板上按 ⏹。
- 看到"像是孤儿"的 python：**不要管** —— 驱动下次启动会自己收容（`_reap_orphan_agents`），那是它的活。
- 阶段侧的同一条纪律（含"跑飞了怎么办"的完整步骤）：`skills/_references/stage_discipline.md` 第七节
  —— 唯一权威表述在那边，这里只作入口。

## 禁止从 Git 历史取本轮依据（硬红线）

**阶段内禁止使用任何 `git` 命令** —— 尤其 `git show` / `git log` / `git cat-file` /
`git ls-tree` / `git checkout` / `git restore` / `git archive` / `git diff <rev>` /
`git grep <rev>`。只能读取**当前工作区文件**；用户已经删除的归档不得用 git 恢复，
历史版本也不得作为本轮结论、模型结构或探针内核的依据。需要规范/文献时读 `skills/` 与
`docs/`，不要读 Git 历史。

这条由两个地方机械执行：`runtime/hooks/fma_hook.py`（阶段进程带 `FMA_STAGE` 时直接拦
git 命令，主 agent 的版本管理不受影响）与 `prompt_for()` 的注入提示。完整口径见
`skills/_references/stage_discipline.md` 顶部的「Git 历史禁区」。

## 阶段读取表（唯一权威）

**每个阶段只读下表列出的 1–2 份；其余 docs 仅在对应命令报错时按需查。** 各 SKILL 不再重复声明读哪些 docs——需要领域判断时才查 `skills/_references/math_modeling_norms.md` 的对应小节。

| 阶段 | 必读（≤2） | 备注 |
|---|---|---|
| ① literature | norms「模型大分类与选型速查」 | |
| ② analysis | `docs/CONTENT_QUALITY.md`「题意契约」；norms「题型防错速查」 | **必须写 `reports/TASK_CONTRACT.json`** |
| ③ review | `docs/CONTENT_QUALITY.md`「阶段责任 + 问题分类与机器裁决」；norms 评审 Checklist A/B/C | 必查 ID 由驱动注入 |
| ④ code | `python -m lib.result_contract` / `python -m lib.visualization` 的报错即规范 | 环境用 `config/runtime.local.json` 的 python |
| ⑥ robustness | 同上（两个 CLI） | 排在 ⑤ 结果可信度审计之后：便宜的结果可信度审计先筛一遍，不可信就不白跑昂贵的扰动计算 |
| ⑤ audit | `docs/CONTENT_QUALITY.md`；`python -m lib.result_contract audit` | |
| ⑦ drawio | `docs/VISUALIZATION.md`；`docs/GEOMETRY.md` | |
| ⑨ write（9Paper-writing） | `docs/PUBLICATION.md`；`docs/VISUALIZATION.md`；`docs/PAPER_ROLES.md` | 篇幅预算见 `config/publication.json`；**写 `sections/`、`blocks/` 与结构生成物 `paper-structure.tex`，不碰 `paper/_base/` 与 `main.tex` 稳定外壳**；步骤 2.5 先跑 `lib.paper_structure assemble`；收尾产出提交清单 `reports/SUBMISSION_MANIFEST.json` 与正文末页清单表、运行说明.md、AI工具使用详情.pdf |
| ⑭ format（14Layout-and-format） | 模板层即规范（`paper/_base/*.tex` 的注释）；`docs/PUBLICATION.md`；`docs/VISUALIZATION.md` | **独占排版层（`paper/_base/` 与 `main.tex` 稳定外壳）**；`paper/paper-structure.tex` 归 ⑨，只读；对账并修补 ⑨ 首产的提交清单与末页清单表（塞不下/叠印归它）；机器判据 `skills/14Layout-and-format/scripts/measure_layout.py` |
| ⑩ mathproof（10Math-proof-gate） | `docs/CONTENT_QUALITY.md`「最优性与数学论证」；norms「证明-措辞契约」 | |
| ⑪ cross（10cross） | `docs/CONTENT_QUALITY.md`；norms 评审 Checklist | |
| ⑮ verify（15Verification） | `docs/PUBLICATION.md`（CLI）；`docs/VISUALIZATION.md`（CLI） | 必查 ID 由驱动注入 |
| ⑫ rubric（12Rubric-final） | `skills/12Rubric-final/references/precedence.md`（先读它）；四份 `rubric_*.md` 按子 agent 分读 | 必查 ID 由驱动注入；判词带 `tier`；每条先证伪再报。**版式/编译/数值一致/文献真实类不重复判**，只读 ⑭/⑮ 的报告结论 |
| ⑬ fix（13Repair-by-rubric-verdict） | `reports/RUBRIC_REVIEW.md` 的判词清单；`skills/_references/stage_discipline.md` 第五节 | **只改论文侧**；动手前逐条复核判词属实；建议加第一人称的一律写「本文」 |

## 阶段链

编号 ↔ skill ↔ 产出 的账本在 `docs/STAGE_CHAIN.md`（那里还列着「改链时要同步的各个面」）。
编排的权威顺序是 `lib/web/server.py` 的 `STAGES`。

> 这张表刻意不放在本文件里：本文件的全文哈希是各阶段「做法要求」指纹的一部分
> （`lib/web/server.py:_input_split` 的 `ins` 列表），放这里的话加一个阶段就会把每一个阶段
> 标成 `done(stale-instr)` —— 面板一片黄条，而它对各阶段的实际工作毫无信息量。
> 账本挪到 `docs/` 之后，改链不再产生 stale 噪音；真改 SKILL/规范才照旧触发。

Web 驱动门禁：建模失败→analysis，结果审计失败→code，数学论证/跨问失败→write，终验失败→format（版式/引用/编译/超页是 format 的活，不该重跑整篇写作）；评分标终审的论文侧判词→13Repair-by-rubric-verdict 就地改写，不回退 write（写是小时级，为几句摘要措辞重跑整篇不值当），模型/数值/实现类判词仍回退各自生产阶段；有明确前序 target 时按回执返修。**每个阶段只跑一次**，失败或超时一律转黄灯等人决策（不再自动重试、不再自动回退）。缺失、冲突或版本不符的裁决标为未验证，不自动放行。审查阶段只写本阶段报告及裁决 JSON，不修改被审查对象，也不向建模报告追加 APPROVED。此 Web 协议优先于技能中旧的追加标记或耗尽重试后放行规则。直接调用技能时不视为已通过 Web 交付门禁。

**人工决策五选一**（黄灯面板 / `POST /api/decision`）：再试一次 / 回退到所选阶段 / 延长本次限时（仅超时灯）/ 接受并披露（认下残余，写进论文，标 🔶）/ 我已手工修好（以当前盘面重新认证某阶段，先跑客观校验并留审计痕，标 🔧）。后者是为「agent 反复改不过门禁、人手工改好了却被判失效要重跑」那个死结准备的，见 `lib/web/attest.py`。

**「暂停」与「停止」是两个按钮**（`POST /api/pause` / `POST /api/stop`）：暂停从当前阶段停下
并转黄灯 —— 出口留着，面板上接着选再试/回退/披露/认证；停止是硬停，不给决策面板
（黄灯若亮着一并收起）。区别只在收尾时建不建黄灯，中断信号是同一个。

产物：整链收口时驱动把工作区打包成提交形状的提交件（⑨ 起每阶段收尾先同步一批，链尾收口做严格对账），落 `<产物根>/提交作品/最新作品/`
（产物根默认 `<项目根>/产物/`，前端工具栏「📁 产物」可改路径与题目标识）。那一层下只放要
提交的东西 + `其余文件/`；白名单与提交清单逐项对账由 `lib/delivery/` 负责（`python -m lib.delivery
check`，对象是提交件根不是产物根）。提交清单 `reports/SUBMISSION_MANIFEST.json` 由 9Paper-writing
收尾写（14Layout-and-format 保有对账与修补权），同时是论文末页清单表的来源。各阶段产物镜像在 `<产物根>/各阶段产物/最新产物/<阶段名>/`。
换题时（输入源变更）驱动把这两个「最新」整目录改名成 `<题目标识_日期_时间>/`（题目标识
留空只用日期）再建两个空的 —— 同一题反复重跑不需要任何清理。回退快照另落
`cache/<题目标识_日期_时间>/<阶段名>/`。`current output/` 是旧位置，不再使用。

维护 Web 编排、排查断点续跑或准备首次升级运行时，阅读 [驱动改动与验证说明](docs/WORKFLOW_RELIABILITY.md)。质量优先，不设全链总时长硬限制。

## 复用机制一览（**重跑/返修前先看这里**，都是驱动现成能力，别自己重造）

这些机制没有在 SKILL/docs 里系统列过 ⇒ agent 容易每轮从零重做。下表汇总。

| 手上有什么 | 在哪 | 怎么用 |
|---|---|---|
| 上一轮改了什么 | `runtime/quality/_rev_<阶段id>_before.md` + `reports/_REVISION_DIFF.md`（driver 每轮自动生成，仅在带返修回执重跑时） | 返修第一件事就是读它 —— 一页纸看清"改前改后"，比重新通读全篇便宜得多 |
| 上一版的产物（被回退/换题/清理搬走的） | `<产物根>/cache/<题目标识_日期_时间>/<本阶段中文名>/`、`…/工作区原件/`、`…/回执/` | 捞回来复用（`ls -dt 产物/cache/*/<阶段中文名> \| head -1`），别重算 |
| 所有阶段跑完的副本 | `<产物根>/各阶段产物/最新产物/<中文阶段名>/`（每阶段跑完自动镜像） | 翻某一阶段的产出、跨阶段对比同一文件 |
| 交付件 | `<产物根>/提交作品/最新作品/`（平铺） | 打包与 `python -m lib.delivery check` 的对象 |
| 自己写的探针/量测脚本 | `_tmp/`（新）与 `tmp/`（历史遗留，两处都看） | **保留不删**；下轮先原样重跑，只对新对象写新的（见 `skills/_references/stage_discipline.md` 一·1.1） |
| 图是否过期 / 目检是否还有效 | `python -m lib.visualization audit`（读 `figures/manifest.json`） | 别自己数文件 |
| 页数/页映射/A4/体积 | `python -m lib.publication check` / `map` / `report` | 别自己写页码爬取脚本 |
| 回执（"这一阶段的产物还是不是那一版"） | `runtime/quality/stages.json` | 由驱动判，人不必管；但知道它存在能解释"为什么这轮又被跳过了" |

## 设计要点（维护时遵守）

- **一个 skill 一个职责**；审查类角色绝不互相合并进同一上下文，评审维度用 Agent 子 agent 各跑各的。
- 审查必须给"具体怎么改"，禁止只写"不行"。
- 建模报告显式含：决策变量 / 目标函数 / 约束条件 / 求解算法 / 机理依据 / 代码契约。
- 论文数值必须来自 reports 报告，禁止编造；图与结果可复现。

绘制空间几何图时读取 [几何图协议](docs/GEOMETRY.md)；写作及终验时读取 [篇幅与公式协议](docs/PUBLICATION.md)，以 config/publication.json 的计页口径验收。


运行代码或服务前读取 [项目环境](docs/ENVIRONMENT.md)，统一使用 config/runtime.local.json 指定的 Python。

## 依赖

- 运行于 Claude Code（当前模型为 DeepSeek）。
- 写作排版依赖 xelatex（跑 9Paper-writing 前可用 `doctor` 预检环境）。
