# 已知缺口台账（G1–G16）：故意没做的那些事

> 这份文件不是缺陷清单，而是「已经知道、但此刻故意没做」的那些事的台账 ——
> 目的是别忘。每条写清：是什么、为什么现在没做、怎么关掉（可执行步骤）、以及影响面。
> **改之前先看这里**：别把已知的取舍当新缺陷重复报。
>
> 来源是两轮对抗性审查（`fma-post-fix-audit` 与 `fma-post-fix-round2`：5 个维度找问题 →
> 每条 3 视角反证 → 完备性批判）；审查本身刻意要求分辨「真缺陷」与「审查者自己判断错了」
> —— 后者不进这份台账。
>
> 16 条逐条核验过：两条不是取舍、而是判据/默认值本身错了，已改（G8/G16 各自的「已改」标注）；
> 其余是真的故意不做，原样保留。
>
> （原 `需要改/` 两份文件的结论已并入本台账与 `docs/STAGE_CHAIN.md` 的迁移清单，不再单独留档。）
>
> 维护约定：谁关掉了某条，就在该条下加一行「已关闭（怎么关的）」；
> 别直接删，留着能看出这个坑曾经存在过。

---

## G1 · `write` 的「被下游接管」分支整个在夹具里不可达 ⇒ 零覆盖

> 已关闭 —— 关闭方式与修正后的根因记在下面，别删。

是什么：`lib/web/server.py` 里 ⑨论文撰写 的 `taken-over` 分支 —— 它从
「只认 ⑩ `format` 一家接管」扩成 `for owner in ("fix", "format")`，随后判据又从
整份 digest 改成只比事实半份（`_taken_over_by`）。动机：⑨ 的产物是
`paper/` + `paper_appendix/`，而 ⑩排版 与 ⑮按评分判词返修 都会合法改写它们 ⇒
⑨ 的 `outputs` 半份必然对自己的回执失配 ⇒ 走不到 `stale` 那条近路；
而拿整份 digest 比「拥有者的回执有效」时，改一条共享的做法要求（`CLAUDE.md`）
会让拥有者自己的回执也失效 ⇒ 接管必然落空 ⇒ ⑨ 整篇重写（小时级，且推翻下游成果）。

缺口（修正后，比最初记的更大）：不是「`fix` 那一支没覆盖」，而是
整个接管分支在夹具里根本走不到 —— `install_successful_runner` 造出的链里
⑩ 从不写 `paper/` ⇒ ⑨ 的 `outputs` 从不变 ⇒ 它永远走的是 `stale` 近路
⇒ 接管分支一行代码都没被执行到。那条 `test_an_instruction_change_does_not_rewrite_the_paper`
因此改前改后两版都绿（覆盖不到）。

怎么关掉的（已做）：

1. 在测试自己的夹具里让 ⑩ 真的写 `paper/`（不动全局 `install_successful_runner`，
   免得搅动几十条既有用例）：
   `after = lambda sid: (self.root/"paper/main.tex").write_text(...) if sid == "format" else None`
   ⇒ ⑨ 的 `outputs` 因此漂移 ⇒ 才到得了接管分支。
2. 新增 `test_the_paper_is_not_rewritten_when_the_owner_is_only_instruction_stale`
   （`regression/test_workflow.py`）：改 `CLAUDE.md` 后断言 `write` 不在 `calls` 里、
   且 `write` 在 `state["stale_instr"]` 里。
3. 验了它是真守卫：把 `_taken_over_by` 桩回改之前的判据（只认 `format`、比整份 digest）
   ⇒ ⑨ 重跑 ⇒ 这条测试变红（改后 False / 改前 True）。

留下的通用教训：**夹具到不了的分支 = 零覆盖**。
写「这条测试守住了 X」之前，先问两件事 ——
① 夹具能不能走到那条分支？② 把 X 的代码桩掉，这条测试会不会红？
两轮审查里被判「审查者自己判断错了」的候选，有一半栽在 ① 上。

---

## G2 · 两个门禁模块的模块级判据表不在任何指纹里（真空）

> 已决策：不修。 理由：改判据表之后显式「从该阶段重跑」来验证就够了，
> 不指望 ▶ 自动带上；为它引入一套新机制（见下面两条路）不值。
> 正式用时也不会轻易改代码，列出来没必要。

> 留给将来的一句话（这就是这条缺口唯一的代价，别的没有）：
> 改了 `REQUIRED` / `TARGETS` / `RESULT_CHECK_CATEGORY` / `FATAL_CHECK_CATEGORY` / `TIERS`
> 或 `VERDICTS` / `IGNORED` / `BUILD_SUFFIXES` 之后，按 ▶ 时已经跑过的门禁会直接跳过
> （它们的回执照旧匹配）⇒ 那一轮它压根没跑，但看起来像"按新判据过了"。
> 要让新判据生效：显式「从该阶段重跑」。

是什么：`_gate_logic_fingerprint()` 只哈希 `lib/web/content_quality.py` 与
`lib/web/workflow_quality.py` 里带 `__code__` 的东西（即函数体）。这两个文件里的
模块级判据表 —— `content_quality.py` 的 `REQUIRED` / `TARGETS` /
`RESULT_CHECK_CATEGORY` / `FATAL_CHECK_CATEGORY` / `TIERS`、`workflow_quality.py` 的
`VERDICTS` / `IGNORED` / `BUILD_SUFFIXES` —— 一个都不在指纹里。

⇒ 改这些表 = 判据变了，却没有任何回执失效 ⇒ 一份按旧判据通过的裁决会继续生效。
这与这套代码一直在修的「判据一变必须重判」正好相反，是这条原则唯一的真空。

为什么现在没做：它会扩大自动重判面（改这些表会让 7 个门禁各重判一次），
而口径已收窄成「做法要求变了只标记不重跑」——
两个方向相反，得先想清楚「判据表」该归哪一类：
- 归「做法要求」⇒ 只标记、不重跑（与现行口径一致，但真空仍在）；
- 归「判据」⇒ 一变就重判（安全，但与现行口径冲突）。

怎么关掉（二选一）：

1. 收窄版（推荐，与现行口径一致）：把这两张表挪进它们自己的小节并在
   `_input_split` 里作为 `ins` 的一员 —— 于是它们和 SKILL 一样，变了只标
   `done(stale-instr)`、由人决定要不要重判。真空消失，且不引入自动重跑。
2. 严格版：把模块级表纳入 `_gate_logic_fingerprint()`（例如哈希
   `{k: v for k, v in vars(mod).items() if not callable(v)}` 的规范化文本）。
   代价：改一次表 ⇒ 7 个门禁各重判一次。
3. 无论选哪个，都要回归测一次：往表里加一行，确认「该失效的阶段失效了、
   不该失效的没动」（照 `regression/test_stale_noise.py` 里
   `ReferenceDependencyTests` 的正/反向守卫写法）。

影响面：真实。改这两个表不会有任何提示 —— 而它们决定门禁判什么。

---

## G3 · Windows 长路径（>260）没人量过，且失败是静默的

是什么：本机注册表 `LongPathsEnabled = 0`，而 `lib/delivery/`、`lib/web/server.py` 里
没有任何 `\\?\` 前缀（grep 为空）。当前 `产物/` 下最深的绝对路径 145 字符 ⇒ 余量约 115。

真撞上去时失败是 `OSError`，而被下面四个落点吞掉：
`_mirror_paths._try`、`_stash_paths`、`_purge_stage_snapshots`、`_remove_path(ignore_errors=True)`
⇒ 表现是「某个文件没镜像过去 / 没搬走」，没有任何报错。

为什么现在没做：没有证据表明常规一轮能撞到（唯一撞到过的是自指联结点那个 loop）；
而在没测过的情况下加 `\\?\` 前缀会改动所有路径的语义（风险大于收益）。

怎么关掉：跑完一轮之后量一次 ——

```bash
find 产物 -type f -printf '%p\n' | awk 'length($0)>225 {print length($0)+35, $0}'
grep -c "阶段快照不完整\|未能暂存" runtime/web_run.log      # 期望 0
```

若真出现 >225 的路径，就按 `docs/VISUALIZATION.md` 的命名纪律缩短图文件名，
或把「阶段快照」的目录层级减一层。**不要**先上手改 `\\?\`。

影响面：未知（没量过）。有这个量测命令之后，它就从「未知」变成「有证据的否」。

---

## G4 · 从未运行过的阶段在 `_REFERENCES_USERS` 里是「保守给全」

是什么：`lib/web/server.py` 的 `_REFERENCE_USERS_DEFAULT` 把
`⑫跨问一致性 / ⑬验收 / ⑭评分标终审 / ⑮按评分判词返修 / ⑯交互Demo` 以及 ①文献定向
（访问量 20，低于门槛 50）算作「证据不足」，于是 `skills/_references/` 下任何
文件的改动都会让它们失效。

为什么是「设计如此」而不是缺口：这是项目自己定的两条纪律 ——
「没有运行证据的阶段保守给全」（给多了只是多跑一轮，给少了会让阶段漏掉真变化）
与「只在访问量 ≥50 且零命中时才敢摘」。不是缺陷。

怎么关掉：等它们真跑过一轮、`runtime/web_run.log` 里攒够访问记录之后，
照 `tmp/deps_from_transcripts.py` + `tmp/deps_classify.py` 的对账口径重新挖一次，就能按真实依赖收紧。

影响面：低（多跑一轮，不是漏失效）。记在这里是为了将来别再当成缺陷报一次。

---

## G5 · `core.Checkpoint` 定义了却零调用 ⇒ 小时级求解不可切段、一崩就从头

是什么：`code/core.py:703` 定义了 `class Checkpoint`，而 `grep -c "Checkpoint(" code/*.py`
= 0。可 `skills/_references/stage_discipline.md` §三 明文要求：超过 5 分钟的计算要
"切成 ≤5 分钟片段、逐段落盘"，并点名"用现成的 `core.Checkpoint`"。

后果：`tmp/repair/run_all_r3.log` 里 Q2/Q3 = 1711.6 s、Q4 = 1121.0 s，
都是整块不可切。任何中断（崩溃 / 手停 / 超时）都从头再来 —— 这是"回退后重算要两小时"里
最大的一笔，也是唯一一笔"纪律写了、生成物没做到"。（两轮返修实测。）

怎么关掉：④ 的 SKILL 把 §三 落成可验收的产物要求（`run_all.py` 必须分段，并把检查点
路径写进 `_params` 供核），或在 `result_contract` 里加一条客观判据："单段求解 >5 min 的必须有
检查点文件"。**别只加一句"请分段"** —— 没有判据的要求等于没有。

---

## G6 · 回退把 `code/`+`results/` 搬进 cache，驱动不还原 ⇒ 靠 ④ 自己想起来手搬

是什么：`lib/web/server.py:3458-3464` 的 `_stage_rels("code")` = `[RESULTS_REPORT.md,
FIGURE_PLAN.md, code, results]`，回退时全部搬进 `cache/<题名>/编码计算/`（`runtime/web_run.log:1694`
实证）。而 `_stash_markers_for_restore`（`lib/web/server.py:3853-3877`）只处理 `reports/` 的标记文件
—— `code/`、`results/` 没有任何还原路径。

后果：④ 回来时工作区是空的；第 4 次是 agent 自己用
`Copy-Item` 从 `产物/cache/2026A_2026.9.26_00.58.29/编码计算/` 搬回（716 K 代码 + 34 M 结果，
约 2 min）。想不起来就是把上一版解重造一遍（小时级）—— 同一件事每次都要 agent 自己发明。

怎么关掉：回退到生产阶段那条路，把 cache 落点显式写进 hint（"你的上一版在
`<cache 落点>`，无缺陷的部分按 §一 直接复用"）；或驱动在回退后把这两项复制回来（cache 副本
保留）。**别改成"自动还原成已完成"** —— 回执作废的语义不能丢，只是别让 agent 去猜东西在哪。

---

## G7 · `figures/make_figures.py:432` 一个裸 `%` 让整个出图段崩

是什么：该行被当作 `%`-格式串用，却含一个字面的 `%（`（全角括号 U+FF08）：

```
File "figures/make_figures.py", line 432
    "半径在烘干前段快速收缩、10 h 完成总收缩量的 90%（此后进入平台 R → %s cm）；"
ValueError: unsupported format character '?' (0xff08) at index 28
```

后果：`run_all.py --figures` 在出图段 rc=1（`tmp/repair/run_all_new.log:160-162`）
⇒ 要三次手补渲染（约 6 min），且那一次的"全量流程"并不完整。

怎么关掉：生成器层加 lint —— 用作 `%`-格式的字符串里不许出现裸 `%`（要么 `%%`、要么 f-string）。
放在 `visualization` 的导出助手或 ④ SKILL 的图段自检里，附一条冒烟（`python -c "import figures.make_figures"`）。

---

## G8 · `RETRY_CAP_DEFAULT = 30 min` 小于 ④ 自己的求解 51.9 min ⇒ 每轮必然弹黄灯

> 已改：新增 `lib/web/server.py::STAGE_CAP_DEFAULT = {"code": 5400}`（90 分钟，
> 实测 51.9 min 的 1.7 倍），`_effective_limits` 按 `cap or override or 阶段默认 or 全局默认` 取。
> 只给有实测证据的阶段抬高 —— 别的阶段仍是 30 分钟（一起抬会把「超时」这盏灯钝掉）。
> 手动点过「延长」的，以手动填入的值为准；协议级短上限仍最高优先。
> 回归：`test_workflow.py::test_the_coding_stage_gets_a_longer_wall_clock_budget`。

是什么：`lib/web/server.py:1044` `RETRY_CAP_DEFAULT = 1800`（30 min），而
`tmp/repair/run_all_r3.log:178` `== 完成：总用时 3113.7 s ==`（51.9 min）。

后果：每一轮 ④ 必然触发超时黄灯要人手动点"延长"（一轮里点了四次），
而"停止"就在同一面板上 —— 离丢掉整段只差一次点击。
（`OVERTIME_KILL=False` 所以灯只问不杀，这个设计是对的。）

怎么关掉：给每阶段自己的单次上限（④ 取 ≥90 min），或让"延长"的默认值取"预计剩余时间"。
**别关掉这盏灯** —— 长时间无输出时要能看见它，问题只在于"默认值比该阶段的固有耗时还小"。

---

## G9 · 交回单那条黄灯不带 issue ⇒ "纯图缺陷别搬数值产物"的机制空转

> 已关闭 —— 关闭方式记在下面，别删。

是什么：`_figure_only_defects(issues)`（`lib/web/server.py:4006`）的口径是「每一条都是
`category == "diagram"` 且至少有一条」⇒ 纯图缺陷回退到 ④ 时不搬 `code/`、`results/`
（只作废回执让它重画）。但它的输入是 pending 的 `issues`：

- 门禁那条路（有效）：⑧绘图门禁 FAIL 的裁决带 6 条 issues，全 `cat=diagram`
  ⇒ 回退到 ⑦ 时机制正确触发（`cache/…08.45.53/` 里只有
  `技术路线图` + `绘图门禁`，④ 的数值一个没动 ⇒ ①②③④⑤⑥ 六个全复用）。
- 交回那条路（空转）：⑦技术路线图 不是门禁（`gate=None`）⇒ 它交回时
  `_halt(..., handback=hb, decision=⑦的裁决)` 里的 `decision` 是空壳 ⇒ pending 的 `issues` 为空
  ⇒ `_figure_only_defects([])` = `False` ⇒ 照搬 `code/`+`results/`（`cache/…09.49.38/编码计算/{code,results,…}`
  被搬走）。

后果：同一批"纯图缺陷"，走⑧的灯不搬、走⑦的交回单就搬 —— ④ 回来得自己从 cache 搬回
（~35 MB，约 2 min；想不起来就是从零重算，小时级），且与 G6 叠乘。

同一根因的第二个症状（更要紧）：给 ④ 的提示词是反的。
`_has_actionable_feedback`（`lib/web/server.py:2500` 起）也以 `issues` 非空为前提
（`:2508` `if not decision.get("issues"): return False`）⇒ 同一条"issues 为空"既让
`figure_only` 失明，也让 `_save_feedback` 落进"门禁没跑完"那条模板（`:2556-2560`）：

> 上游门禁「drawio」这次没有跑完…它的原始输出留在 <folder>，仅供排查，
> 里面那条修法是针对门禁自己产物的，与本阶段无关。你按本阶段 SKILL 的自检清单重做即可…

而事实上那份"原始输出"正是本阶段要执行的返修单（⑦ 的 `HANDBACK_REQUEST.md`）。
字符串随 `round_hint` 拼进 ④ 的 prompt（`:2755` → `:2181`）。
那次没出事全靠 ④ 自己没听（它已经在读 `HANDBACK_REQUEST.md`）—— 那是运气，不是机制。

怎么关掉（已关掉，四处 + 两条用例）：
1. `lib/web/server.py:_borrowed_upstream_issues(stage)` —— 非门禁阶段交回时，读
   `state["hint_src"][sid]` 指向的那份回执（它上一轮被投递的那份），只认门禁的裁决。
   刻意不判"前序/下游"：审一个阶段的那个门禁常常排在它之后（⑧在⑦之后）——
   写成"只认前序"会把 ⑧ 误杀，正题用例变红才发现。
2. `_build_pending` 在 `handback is not None and not dec.get("issues")` 时借这批 issues
   ⇒ 一处补丁同时修好两个症状（`figure_only` 与提示词），面板也终于显示得出那 6 条。
3. `state["hint_src"]`（新字段）：回退投递时把那份回执目录记在回退区间内每个阶段头上；
   不随 `run_all` 清（交回发生在下一轮，清了就查不到）。
4. `_save_feedback`：交回那条路改用"那份清单就是本轮返修单"的措辞，不再说
   "没有跑完…仅供排查…与本阶段无关"；`_consume_resume_action` 的超时回退同步用借来的 issues。
5. 用例 7 条（`regression/test_workflow.py::FigureOnlyRollbackTests`）：借到/借不到、
   混类别仍整包搬、非门禁源不借、下游源不借、无记录保守、提示词不反向。
   真实回执上验过：`hint_src["drawio"] = runtime/quality/feedback/08d033ca/0218b3c2`
   ⇒ 借到 F-2…F-7 共 6 条、`category` 全是 `diagram` ⇒ `figure_only=True`。
口径别放宽：`_figure_only_defects` 要求"每一条都是 diagram"是故意保守的
（混进一条 implementation/validation 就说明数值也可能有问题，宁可多算一次）。

---

## G10 · 交回链路不转发上游门禁的原始判词 ⇒ 拿判据的人只能按转述改

是什么：`_save_feedback(stage)` 的拷贝循环只拷当前阶段的 `REPORTS/stage["report"]`
+ `HANDBACK`（`lib/web/server.py:2535-2537`）。⑦ 交回 ④ 时，`stage` 是 ⑦，于是交出去的是
`DRAWIO_REPORT.md` + 交回单；⑧绘图门禁的那份原始 FAIL 判词压根不进去。

实证：feedback 目录 `f8d654e7/eed026c7/` 里只有 3 个文件 ——
`DRAWIO_REPORT.md`(30 KB) + `HANDBACK_REQUEST.md`(10 KB) + `gate_decision.json`(66 B，
内容全文 `{"status":"PASS","reason":"not_gate","issues":[]}`)；而 ⑧ 的
`FIGURE_REVIEW_REPORT.md` 早被上一次回退搬进 `cache/…08.45.53/绘图门禁/`（另有一份在上一轮的
feedback 目录 `08d033ca/0218b3c2/`）⇒ ④ 手里没有 F-2~F-7 的权威版本，只有 ⑦ 的转述。

为什么现在没出事：⑦ 的转述写得很细（逐条给位置/现象/怎么改/复验判据，还附了自己的复量数字）
⇒ ④ 照着改通常够。但两条风险是真的：① 转述漏一条、或把口径转歪（⑦ 与 ⑧ 的判据不完全同源）；
② ④ 改完无法自查"⑧ 那 6 条的原文判据"是否逐条满足 ⇒ ⑧ 重跑时可能因同一批项再 FAIL 一次。

怎么关掉：`_save_feedback` 顺着 `handback` 找到判 FAIL 的那个门禁，把它的报告与裁决一并拷进去
（`check_handback` 已经知道是哪个门禁判的）；或在 pending 里带上 `source_stage`，由它定位源报告。

---

## G11 · 回退把下游一起搬走+作废 ⇒ ⑤⑥ 被与自己无关的缺陷拖着重跑

是什么：`_redo_from(target)` 现在从 `target` 起逐阶段搬产物（`_stash_paths(_rels(s))`）
并 `_invalidate_from(target)` 把从 ④ 起的回执整批作废 ⇒ 下游阶段既没有产物、也没有回执
⇒ 必跑。不是指纹让他们跑，是这条粗粒度规则让他们跑。

代价：一批纯绘图缺陷（F-2 挪 `loc` / F-3 加 `bbox`+抬 `ylim` /
F-5 抽稀+去边线）让 ④ 回退一轮，连带 ⑤结果可信度审计 37 min + ⑥稳健性 61 min ≈ 1.6 h
—— 而 ⑤ 审的是数值/口径、⑥ 做扰动/bootstrap，与"图例压不压线"毫无关系。
对照：同一个 ⑦ 轮次（读判词→改图→重渲→重登记→写交回单）14.5 分钟。

本可怎样：只作废目标阶段的回执与产物，让下游按指纹自己决定 ——
④ 重跑后若 `reports/RESULTS_REPORT.md`/`code`/`results` 字节没变，⑤⑥ 的输入指纹自然匹配 ⇒ 复用；
只有当 ④ 真的改了报告它们才跑（那才是它们该跑的时候）。F-6 确实要动报告 ⇒ 这一轮省不到，
但 F-2/F-3/F-5 单独出现时就是 1.6 小时。

改之前必须想清的：① 「从该阶段重跑」按钮在 UI 上写的就是"清空该阶段及之后全部产物"
（`lib/web/static/index.html`）⇒ 改语义要同步改文案与用例；② 目标阶段必须仍然真跑
（现在靠"产物被搬走 ⇒ `_artifact_ok` False"保证，改成只作废目标后这条保证仍在）；
③ 得验一遍"上游真改了、下游确实重跑"这条正向守卫没被打掉。

---

## G12 · ⑦/⑧「不许改数据图」：边界画在文件上，而不是画在改动的性质上

> 已关闭 —— 关闭方式与代价的实测数记在下面，别删。

是什么：`skills/7Route-diagram/SKILL.md:57-61`（数据图由 `4Coding-and-computation` 生成、不改 `code/`）
与 `skills/8Figure-gate/SKILL.md:27-33`（只判不改，硬边界）。两条规则性质不同，别一起评：

- ⑧ 那条 = 地基级，不该动：门禁能自己动手 ⇒ 缺陷从台账里消失、裁决不可证伪（与
  「返修记录自证」同形）。
- ⑦ 那条 = 方向对、边界偏宽：`figures/make_figures.py` / `lib/visualization/*` 里混着两类东西 ——
  内容/叙事（claim 文字、色标口径 `gamma`、画什么、与 `RESULTS_REPORT.md` 的一致性）确实归 ④；
  纯渲染参数（`legend(loc=)`、`bbox=`、`ylim` 余量、`ccount/rcount` 抽稀、`edgecolor`/`linewidth`、
  字号）不碰数据、不产生叙事，却因为"住在那个文件里"而必须 mobilise 一个有小时级固有成本的
  生产阶段，并把 ⑤⑥ 一起拖下水（见 G11）。

反对放宽的那条也是真的：`figures/manifest.json` 的 `review.note` 是目检签字，而 ⑧ 实测抓到
4 处 note 被交付像素反证（`q2_surface3d` 写"未见遮挡混色或糊成一片"，实测 34.78% 是灰）
—— 让 ⑦ 一边改图一边签字，正是"自证"的形状。（公平地说：⑦ 现在已经在给自己的非数据图签字，
放宽只是把同一风险面铺大，不是新增一类。）

若要动：边界按改动的性质画 + **必须配一条可机械核的判据**（渲染参数白名单 + ⑦ 必须交出
"只改了这些键"的 diff），否则白名单会变成改内容的漏洞 —— "没有判据的要求等于没有要求"（见 G5）。
候选白名单：`loc` / `bbox` / `ylim` / `xlim` / `ccount` / `rcount` / `linewidth` / `edgecolor` /
`fontsize` / `pad` / `alpha`（落在图片面的参数），不含 `cmap` / `levels` / `gamma` / `vmin` /
`vmax` / claim / caption / 数据来源。

怎么关掉的：

1. 授权（三处 SKILL，驱动一行没改 —— ⑧ 的 `FAIL->drawio` 本来就把回执交给 ⑦）：
   - `skills/7Route-diagram/SKILL.md`「阶段边界」：数据图的首次生成归 `4Coding-and-computation`；
     画法与图注文字的后续优化归 ⑦，白名单 = `legend(loc=)`/`bbox=`/`xlim`·`ylim`/`clip_on`/
     色标档界 `levels`/`gamma`/字号/线宽/`edgecolor`/抽稀 `ccount`·`rcount`/caption 与 claim 里按现算改正的数字；
     **仍然不许**：`code/`、`results/`、`*.npz`、`sources`、claim 的语义、报告数值结论、重跑模型。
   - **三条硬判据**（缺一 ⇒ 说明要动数值/口径 ⇒ 才走交回）：① `code/`·`results/`·`*.npz`·`sources`
     逐字节相同；② 重渲 + 重新登记 + 重新目检；③ `python -m lib.visualization audit` PASS。
   - `skills/8Figure-gate/SKILL.md` 的两处去向：画法类由 ⑦ 就地改，只有数值或口径来源才交回 ④。
   - `skills/4Coding-and-computation/SKILL.md` 写明分工，并说明"本阶段交出的图不必一次尽善尽美"。
2. 守卫：`regression/test_stale_noise.py::FigurePolishAuthorityTests`（4 条）钉住上面这些措辞
   —— 授权只写在文本里，文本被改回去 = 结构被改回去。
3. 代价对比：旧边界一次"画法类"交回 = ④ 41 min + ⑤⑥ 58 min + ⑦⑧ 72 min ≈ 2h51m；
   新边界 = ⑦ ~15 min + ⑧ ~35 min ≈ 50 min，且 ⑤⑥ 完全不碰（回退点是 ⑦，实测两次
   `①②③④⑤⑥` 全复用）。
   顺带纠正一个反证的误判：`severity: soft/info` 在 `issues` 里完全不起作用
   （`3Modeling-review-gate/SKILL.md:50-56` 自己写着"写 soft/info 完全不起作用"；`content_quality.py:455-456`
   把 `category=diagram` 一律算 hard）⇒ 面板显示 "soft" 会让人误读成"可放行的打磨项"。

---

## G13 · ⑧绘图门禁是全链唯一没有"轻微项阀门"的门禁 ⇒ 1 条 soft 就等于 FAIL

是什么：全系统唯一的"只剩轻微项就放行"阀门是 ⑫评分标终审的 `tier=optional`
（`lib/web/content_quality.py:311-316` → `status=PASS, reason=only_optional_remain`）；
别的阶段写 `tier != must` 直接判 `verdict_malformed`（`:446-448`）。而 ⑧ 不在
`content_quality.REQUIRED` 里（`:111-134`）⇒ `enforce()` 在 `:342-343` 原样放行，
既没有归一化、也没有任何软通道 ⇒ ⑧ 写进 `issues` 的每一条都是拦链项，`severity` 标什么都不读
（驱动 `lib/web/server.py:2505-2515` 只看 `status`）。

后果：3 条 soft + 1 info（`category` 全是 `diagram`）判 FAIL
⇒ ⑦ 交回 ④ ⇒ 整链重跑一轮。而其中判据最勉强的那条（G-1 的"显著低于 50%"，是 ⑧ 那一轮
新设的阈值；同量纲的两把旧尺子 —— ⑧ 自己 SKILL 里的反例 76% 同色、`lib/visualization/export.py:71`
的 `mono >= 0.75` —— 它都没过线）与最铁的那条（G-4 的 caption 数字 3/3 与现算不符 = SKILL
写的"说到做到"行）被 ⑧ 分别标成了 soft 与 info ⇒ 标尺在活动、标签在误导。

为什么现在没改：给门禁加"软阀门"是政策变更（它决定"什么能不经人放行"），而且
G12 关掉之后，一次"画法类 FAIL"的代价已从 2h51m 降到 ~50 min ⇒ 紧迫性下降。
怎么关掉（若将来要）：
1. 给 ⑧ 一条与 rubric `optional` 同源的通道（例如 `category=diagram` 且 `severity in {soft,info}`
   且没有 hard ⇒ `status=PASS` + 把这些项走 `advisories`，并强制写 `why_not_blocking`）；
2. 或先做最小的一步：把"`issues` 里的 `severity` 是装饰性的"这件事从显示上去掉
   （面板对 `issues` 一律渲染成"拦链"，或干脆不许 agent 写 severity）—— 免得人误读；
3. 无论选哪个，都要回归一条：混进一条 hard 时必须仍然 FAIL（照
   `regression/test_stale_noise.py` 的正/反向守卫写法）。

---

## G14 · 判据"在册、却不生效"：阈值设在坏样本之下 + 只出 warning ⇒ 谁也没看见

是什么：摘要「写得少、尽量写满那一页」这条要求加了
`config/publication.json:min_kind_chars.abstract = 900`，还在 `docs/PUBLICATION.md` 里写了
上下限与依据 —— 看起来修好了。当轮 ⑨ 重跑、⑩ 重编之后，摘要一点没变长。查下来四处全断：

| # | 断点 | 事实 |
|---|---|---|
| 1 | 阈值低于坏样本 | 当时那份摘要实测 919 个非空白字符，下限设的是 900 ⇒ 判据对它毫无反应。（坏样本的数 990/78.6% 已经量过并写进了注释，然后设了一个能从它下面穿过去的阈值 —— 这是本条最该记的一笔） |
| 2 | warning 在本仓库无人消费 | `_manual_checks` 与 `_mechanical_floor` 都是 `audit()` = `inspect()["issues"]`；`reports/PUBLICATION_CHECK.json` 的 `warnings` 全仓库没有一处读（grep 确认）⇒ 提示级判据等于没写 |
| 3 | 规则层反向指标 | `norms`「摘要写作要点」与 ⑨ 的 SKILL 都写着「约 850–950 字内安全」—— 读起来是上限，实践上每份摘要都收在 900 上下 |
| 4 | 就算判死也回错人 | `publication` 类问题的回退目标被 `_mechanical_floor` 写死 ⑩排版，而摘要文字是 ⑨ 的产出（⑩ 无权改内容）⇒ 判给 ⑩ 必然下一轮同样 FAIL |

最硬的一条证据：⑨ 自己的报告 `reports/WRITING_REPORT.md:115` 白纸黑字写着 ——
「摘要：第 1 页非空白字符 919（机器下限 `min_kind_chars.abstract = 900` 通过、
1 000 字天花板未触）」⇒ 它核过判据、判据说"合格"，于是收工。不是没人查，是尺子在骗人。

怎么修：①判据换成要求的机械形式 —— **版心填充率**（`lib/publication/checks.py::kind_fills`，
量本文自己的版心，不靠字数估算），两档 `target=0.90 / hard=0.80`；②`< hard` 进 `issues`
并打 `prose_issues` 标记，`lib/web/server.py::_mechanical_floor` 见标记就把回退目标改指 ⑨
（判据取"**沾文字就归 ⑨**"：⑨ 在 ⑩ 上游，回退它会连 ⑩ 一起重跑；判给 ⑩ 则转不出去）；
③`min_kind_chars` 降级为"量不出填充率时"的兜底，二者互斥、不重复报；④`norms` 与 SKILL 的
「850–950 内」改写成下限 + 实测标尺（参考件 92.7%、本稿 78.4%）。
回归：`regression/test_publication.py` 新增 9 条（含"阈值必须高于已知坏样本"与
"沾文字就归 ⑨"两条），`PublicationRollbackTargetTests` 钉住回退目标。

给下次的判据（通用）：**加判据时，必须拿"已知坏样本"当反向用例** ——
阈值要从病灶上面过；只出 warning 的判据要同时给出"谁读它"的答案，
否则写 `issues`。

---

## G15 · `fig_roadmap` 整栏排印下字号 7.756 pt < `min_font_size = 8`（已知披露项，本轮不动像素）

是什么：⑧ 绘图门禁的延后建议 ADV-4。⑩ 在交付件上实测（不采信转述）：

| 量 | 实测值 | 来源 |
|---|---|---|
| `figures/fig_roadmap.pdf` 自然尺寸 | 687.12 × 932.88 pt（宽 242.4 mm） | PDF 页盒 |
| 图内文字字号 | 11.52 pt（172 个 span 全同值） | PDF 文本层 |
| `.drawio` 里 `fontSize` | 16（156 处全一致） | `figures/fig_roadmap.drawio` |
| 论文排印宽 | 163.2 mm = 版心（`\paperfigure[\textwidth]`，210 − 25.0 − 21.8） | `paper/sections/1_restatement.tex:21` |
| 缩放 | 0.6733 | 462.6 / 687.12 pt |
| 实际排印字号 | **7.756 pt** | 11.52 × 0.6733 |

低于 `config/visualization.json` 的 `min_font_size = 8`（本项目初始样式，`docs/VISUALIZATION.md`
原话「不是比赛强制标准」）。整栏 163.8 mm 口径下是 7.785 pt。

本轮处置（⑩）：
- 登记宽 `width_mm` 163.8 → 163.2 mm（`figures/manifest.json`），即"改成实际排印宽"，改后重签复核；
- **不改像素**：三个资产 `fig_roadmap.{drawio,pdf,png}` 的 sha256 与登记时逐字节相同
  （`39e052788bd10d22…` / `f787c6baff68bead…` / `7ba2af6fb9f5fe58…`）；
- 目检结论：整栏目检可读、无叠印/缺字/裁切，作已知披露项（详见 `reports/FORMAT_REPORT.md` 未处理项 1）。

怎么彻底解决（留下轮 ⑦）：把自然宽从 242.4 mm 压到 **≤235 mm**（或把字号抬到 ≈11.9 pt）⇒
整张重排 + 重新登记 + 重新目检。生成器是 `skills/paper-diagram/scripts/roadmap_5band.py`
（改它等于改下一轮）。⑦ 已实测：只提字号会触发 drawio 版式体检 14/24/38/49 条失败，
所以这不是"改一个数"的事。

---

## G16 · `check_skeleton.py` 的「符号说明开头总述」判据把排版代码当成散文 ⇒ 连它自己的模板都判不过

> 已改：判据改成只数散文 —— 新增 `_prose_chars()`（去掉 `\命令`、
> `[可选参数]`、花括号骨架、数字之后只留中日韩文字），阈值 `PROSE_HEAD_MAX = 8`
> （给「表 1 符号说明」这类表题行留余量，它合法地就住在那一段里）。
> 两端验证：拿模板自己喂它 ⇒ 通过（改前判 297 字）；真加一句「除特别说明外…」⇒ 照样报（98 字散文）。
> 回归：`test_skeleton.py::test_the_symbols_head_judge_ignores_layout_code`。

是什么：`lib/web/check_skeleton.py::_symbols_problems` 按「`\section{符号说明}` 之后、第一个
`\begin{` 之前的非注释行总字数 > 40」判「标题下有一段开头总述」。但这个区间里除了散文，
还必然含有排版代码：`\setlength{\LTleft}{\fill}`、`\setlength{\LTright}{\fill}`、
`\par\vspace{0.25\baselineskip}`、表题行 `{\centering…表 1\quad 符号说明\par}`、
`\nopagebreak`、`\vspace{0.5em}`、`{\small`、表内行距补丁两行 —— 这些**必须**在
`\begin{longtable}` 之前（表题放进表内会被压成 5.5pt，见模板注释），删不掉。

实测：把本 SKILL 自己的模板 `skills/9Paper-writing/templates/zh/cumcm-latex/sections/4_symbols.tex`
喂给该函数的判据，得 297 字、照样判不过；本稿按要求删掉开头的总述段之后，
读数恰好也是 297 字（398 − 101）——两者逐字相同，说明剩下的全是那段排版代码。
即：按模板写的任何一份 `4_symbols.tex` 都过不了这条判据，在「符号说明」这一项上无法
让 `python lib/web/check_skeleton.py` 转绿。

怎么关掉（可执行）：把该判据的「非注释行」改成「非注释、且不是纯 LaTeX 命令/间距的行」
—— 例如忽略以 `\setlength`/`\vspace`/`\par`/`\nopagebreak`/`\renewcommand` 开头的行，
以及 `{...}` 包裹的居中表题行（或直接把阈值改成"至少 N 个连续中文散文字符、且不含 `\`"）。

影响面：论文本身没有那种要禁的开头总述段（那段已删，单位口径按模板注释的指引
移进了表注）；被误报的只是「排版代码的必要前置行」。所以这条不影响论文内容与版式，
只影响该自检命令的结论 —— 但每一轮 ⑨ 都会在这里卡一次，且容易诱导后来者去删表题/间距补丁
（那会把符号表压坏）。

---

## 附：已处置、别重复报的候选

两轮审查的候选处置如下 —— 详见 `runtime/web_run.log` 与各文件内的注释：

- 22 条确认全部修完（含两条 high：门禁的「机械地板」在 `stale` 路径上停摆；
  `plan.md`/`write` 接管的相关口径）。
- 13 条判为「审查者自己判断错了」，不进本台账。典型错法（供下次自查）：
  机制真、可达性假（把一个真实盘面上不可能出现的状态当缺陷）；
  把夹具行为当产品行为（mock runner 会确定性地重写报告，导致「改了被审对象」的测试假绿）；
  后果链跳步（说「没有任何日志」，而那行日志就在那里）；
  落点判错（把 A 路径的现象安到 B 路径头上）。
- 诊断口诀：遇到「有问题」先问一句「这是不是判错了」 ——
  第一轮 35 条候选里，45% 的判词是「审查者自己判断错了」（`refuted` 为 0：
  没有一条是「跑不出来」，全是「跑得出来但那不算缺陷」）。

---

## 附：待办核验结论（编号沿用原清单）

> 这份核验覆盖原 `需要改/` 的 13 条清单与 `待修台账.md`；当前仍开放的只有第 8 条。

| 原编号 | 事项 | 核验结论 |
|---|---|---|
| 1 | ⑩ 别在链中途跑 `delivery check` | 已落实（`docs/CUMCM_2026_REQUIREMENTS.md` 与 `lib/web/server.py` 两处调用点都写明「只在收口打包之后跑」）|
| 2 | `AI工具使用详情.pdf` 产出并登记 | 已做 |
| 3 | 图复核 / 摘要填充 / 公式复核重签 | 已做（摘要 78.1% → 94.8%）|
| 4 | 驱动窗口可见 vs 隐藏 | 已有答案：`run.bat` 起的是独立可见窗口，关掉启动器不会带走驱动 |
| 8 | 「注记压框 / 文本越出框」的机器判据 | 仍未做（`quality.texts_overlap` 只查"文字压文字"，查不到"字压线/越出框"）。当前防线是生成期自检（绘图脚本里量 `get_window_extent()` vs 所在框）+ 位图第四查（四边贴边带）。要真做，得先攒够坏样本再定阈值（G14 的教训）|
| 9 | 参考文献字号/行距 | 已达标（`preamble.tex` 的 `\fontsize{10pt}{8.9pt}` + `\bibitem` 包一层）|
| 11/12 | 关键词质量 / 假设条目太长 | 规则已写 ⇒ 不是待改项；本稿要变只能重跑 ⑨ |
| 13 | 中文文献支线进 ① | 已写进 `skills/1Literature-orientation/SKILL.md` |

`待修台账.md` 的 P1–P10 全部闭环（P1–P6、P8、P8b、P9、P10 早先已做；P7 即上表第 1 条）。
其中 P5（流程图那个 L 形灰底块）的病因与守卫写在 `skills/paper-diagram/scripts/roadmap_5band.py`
的注释与 `lib/visualization/quality.py::_edge_band_width` 里 —— 知识跟着代码走，不需要台账。
