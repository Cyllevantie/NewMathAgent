---
name: 8Figure-gate
description: "绘图门禁（紧跟 7Route-diagram 之后）。⑦ 一跑完全文 12 张图就都在盘上了 —— 这是最早能对图全集做检查的位置。机械地板由驱动跑 `python -m lib.visualization audit` + `figure_lock.py verify`，本阶段负责机器看不见的那一半：图的选型对不对、读起来是否清楚、与正文讲的话是否一致。只判不改：画法/契约 FAIL 回 ⑦，数据层 `[lock:data]` 回 ④。"
allowed-tools: PowerShell, Read, Write, Edit, Grep, Glob, Agent
---

# 绘图门禁（⑧）

> 通用执行纪律（增量返修 / 缩比预估 / 分段落盘 / 方法标记 / 返修只动清单内）见 `../_references/stage_discipline.md`。
> 本阶段适用：一（增量返修，含 1.1 探针复用）、六·6.1（先落骨架再深挖） —— 先写 `FIGURE_REVIEW_REPORT.md` 与 `.verdict.json`
> 的骨架（`status=UNVERIFIED`、`issues: []`），每查完一项回填一次，别等查完再一起写。
> 探针/量测脚本要复用（通用纪律 一·1.1）：本轮写的取证/量测脚本一律留在 `_tmp/`
> （另有散落的在 `tmp/`，两个都要看）；下一轮开工第一步 = `ls _tmp/ tmp/` → 把上一轮
> 为同一批对象写过的脚本先原样重跑（秒级，确认数在当前版本里还成立）→ 只对本轮新出现或改过
> 的对象写新脚本。别每轮从零重写 —— 全链 776 个自写脚本里
> **683 个（88%）只被用过一次**就再也没人碰。
> 复用探针 ≠ 跳过复核：探针只是取证手段，判定仍逐条对着当前版本做。

本阶段是完整工作流的第 8 步，位于技术路线图（7Route-diagram）之后、论文撰写（9Paper-writing）之前。

## 为什么要有这一关

①–⑦ 把图都造出来了；但在写论文之前必须先确认这堆图值得写进论文。三条理由：

1. 时间。图到 ⑮ 验收才被查出来，中间已经白跑了 ⑨ 论文撰写、⑩ 数学论证、⑪ 跨问一致性、⑫ 评分标终审、⑬ 按评分判词返修、⑭ 排版与版式
   四个阶段 —— 而 ⑨ 是小时级的。这一关的全部价值就是把发现提前。
2. 机器看不见一半。`visualization audit` 能查资产过期、登记缺失、目检复核签名、
   位图质量、图例压数据、drawio 版式体检 —— 但它查不出「12 张图里 11 张是折线、
   二维场一张热力图都没有」这种选型问题：机器全绿、人一眼看出全是折线，是常态。
3. ⑮ 验收那条图闸门只管晚场。它管的是"成稿之后图又被动过"（⑭ 排版会重渲染）。
   本阶段管早场。**两条都在，不要互相替代。**

## 只判不改（硬边界）

**本阶段一个字都不许改图，也不许改论文。** 判 FAIL 默认回 ⑦ —— ⑦ 按自己的交回规则处理：
非数据图它自己重画；数据图的画法与图注文字它就地改（授权见
`skills/7Route-diagram/SKILL.md` 的「阶段边界」）。唯一例外是 `[lock:data]`：
bundle/source 在锁之后变了，⑦ 不能改数据，驱动会把这一类直接回 ④（见「机械地板」）。
换句话说：**只有数值或口径来源变了才回 ④；画法、构图、图注文字一律回 ⑦ 就地修**。

为什么不让本阶段顺手改：改了图就没人再复核它了 —— 审查者与执行者合一，
等于把这一关变成自我认证。这与 `3Modeling-review-gate` 不亲自改模型、`5Result-credibility-audit` 不亲自重算是同一条纪律。

## 输入

1. `figures/manifest.json` —— 逐张图的登记（来源、脚本、claim、caption），图的唯一权威清单。
2. `figures/*.pdf|png|svg` —— 逐张打开看。
3. `figures/data/*.npz` + `figures/spec/*.json` + `figures/*.lock.json` —— 数据层契约：
   图用的字段、claim、统计口径与 ④ 交付的是否一致。
4. `reports/DRAWIO_REPORT.md`（⑦ 产出）与 `reports/RESULTS_REPORT.md`（④ 产出）—— 图想说什么。
5. `config/visualization.json` —— 尺子：非数据图语义色（`palette`/`ink`/`line`/`box`/`grid`/`warn`）、
   `quantity_cmap`（物理量→色阶）、`quality` 阈值、`chart_mix` 选型口径。数据图的分类色/字体/字号/
   面板字母以 `figure-studio/assets/style.tokens.json` 为准（中文全宽/半栏 `min_pt` 7.5/7，英文 6）。

## 两道检查

### 一、机械地板（驱动会自己跑，你不必代劳，但要读结果）

```bash
python -m lib.visualization audit     # 必须 PASS
python skills/figure-studio/scripts/figure_lock.py verify --root .   # 数据层契约
```

驱动在 `_gate_decision` 里对本阶段直接跑这两个检查：它报问题就直接判 FAIL，不看你的裁决。
`figure_lock` 的三类输出要分清：

- `[lock:data]`：bundle/source 在锁之后变了 ⇒ **数据层问题，回 ④**。⑦ 改不了，
  不要在回执里让它“重画试试”。
- `[lock:contract]`：spec 的 fields/field_mapping/claim/statistics 被改过 ⇒ **回 ⑦**，
  让它把 spec 改回锁定值；要改语义就交回 ④。
- `[lock:advisory]`：旧图迁移提示或 caption 数字提示，不拦链。

再跑统一绘图 skill 的静态检查（语言/来源数据/meta 侧车）：

```bash
python skills/figure-studio/scripts/audit_studio.py --root .
```

它查 `reports/FIGURE_CONTEXT.json` 的模板语言与每张图 `figures/<id>.meta.json` 是否一致、
每个面板的 `figures/source_data/<id>__<panel>.csv` 是否存在、`claim/caption` 有没有内部文件名、
脚本有没有 `cmap=jet/rainbow` 或绕过 `studio.style`，以及 `figure_lock`。驱动在本阶段的机械
地板里也会跑同一个脚本；它只查静态项，不替代下面的目检。

### 二、机器看不见的那一半（这才是本阶段存在的理由）

逐张打开图，按 `config/visualization.json` 的 `chart_mix` 与
`../4Coding-and-computation/SKILL.md` 的选型表核对：

| 查什么 | 判据 | 反例 |
|---|---|---|
| 选型 | 二维场（空间 × 时间）该是热力图/等高线；折线只用于切片与指标对比 | 12 张图 11 张折线，温度场/水分场一张热力图都没有 |
| 该用三维却压成了二维 | 物理/数学相关且第三维真有变量含义的（空间结构、响应面、三维轨迹、多变量关系）—— 硬压成折线或二维剖切会把"两个参数怎么共同影响结果"这层信息丢掉。可以且应当用三维，但必须配齐：视角可读、遮挡交代、投影有歧义时配一张二维投影/切片 | 圆柱三点位的空间结构只用一张径向剖切表达，方位与端面看不出来 |
| 3D 图重复/该合并 | 只差时间窗/参数/输出、几何同构的两个问应合并成一张（同相机、同比例双面板或共用模型 + 参数标注）；每个问各画一张同构 3D 图 = 版面翻倍、读者看不出差别 | Q1/Q2 同一圆柱模型各画一张；控制体在每个问里重复画 |
| 3D 标签/剖面/遮挡 | 标签不压实体、不穿几何、不互相压；剖面有填充/剖面线，不是空壳；内部线不穿出实体；投影与遮挡在 caption 交代；字体字号与其他图一致 | 标签白底框切断圆柱；剖面空白像空壳；`max_r C` 公式被曲线穿过 |
| 读得清 | 图例不压曲线、线不穿字、字号 ≥ `style.tokens.json` 的 `typography.<lang>[_half].min_pt`（中 7.5/7，英 6）、灰度打印下仍能区分 | `q1_profiles` 图例没底色、曲线从标签上穿过 |
| 场图别是一片死色 | 低值区占一大片、线性色标把它压成一个颜色时，先加 `gamma`（PowerNorm）把低端拉开；拉开还平就改成剖面/折线 —— 别靠「再画一条判据线」绕过去 | `q2_surface3d` 右栏 t≳22 h 占栏高 43.6% 死色；`q1_field` 水分栏 76% 同色 |
| 不超载 | 单图序列 ≤ 8（超了颜色回绕、两条线同色）；非数据图节点 ≤ 8 | 数值解/级数解 8 条线挤一张，图例糊成一行 |
| 说到做到 | 图里画的与 `claim`、正文那句一致；数值与 `results/` 对得上 | —— |
| 一张大图 | 图 1（分析流程图）是唯一的整栏大图；其余非数据图半栏以内，**配色可沿用图 1 的同一套语义色**（低饱和、灰度可读），不再强制黑白；同类同色、同语义同色 | 大图缩到 0.7 栏、节点字糊掉；小图用高饱和装饰色抢图 1 的注意力 |
| 语言 | 图内解释性文字与模板一致（CUMCM→中文；英文模板→英文）；方法名/单位符号可保留拉丁写法 | 中文论文里全英文标题/图例；英文图里夹中文解释句 |
| 画风 | 配色/字体/字号/面板字母走 `figure-studio/assets/style.tokens.json`；≥5 序列同时用线型/标记 | 每张图一套 rcParams；红蓝只靠色相区分 |
| 来源数据 | 每个面板有 `figures/source_data/<id>__<panel>.csv`；meta 有 counts/intervals/exclusions；`figure_lock verify` 无 `[lock:data]`/`[lock:contract]` | 只有 PNG，数值无法追溯；bundle/spec 被改过 |

完整的选型/语言/统计/来源数据清单见 `../figure-studio/references/qa.md`；本阶段按它逐张核，
但**仍然只判不改**。

不达标就填 `issues`（`category: "diagram"`，硬伤），别写进 `advisories` ——
`diagram` 那一路本来就是给"图本身的产出缺陷"准备的，路由回 ⑦。

## 必须产出

在当前工作目录的 `reports/` 下创建/更新 `FIGURE_REVIEW_REPORT.md`：

```markdown
# 绘图门禁报告

## 结论
PASS / FAIL（与 .verdict.json 的 status 一致）

## 机械地板
（`python -m lib.visualization audit` 的原样输出或逐条摘录）

## 逐张复核
| 图 | 选型 | 读得清 | 不超载 | 与 claim 一致 | 结论 |
|---|---|---|---|---|---|

## 未解决项
| id | figure_id | 严重度 | category | 证据 | 修法 | 复验 |
|---|---|---|---|---|---|---|

## 未打回但可优化（同步写入 reports/FIGURE_POLISH_QUEUE.json）
| figure_id | 现象 | 修法 | 复验 |
|---|---|---|---|
```

Web 裁决侧车：另写 `reports/FIGURE_REVIEW_REPORT.verdict.json`（v2）。结构与通道纪律
**照 `../3Modeling-review-gate/SKILL.md` 的侧车小节写** —— 那里把「`issues` 拦链、`advisories` 不拦链」
讲得最细，别自己发明格式。要点：

- `status`：`PASS` / `FAIL`；`target`：`"drawio"`；数据层 `[lock:data]` 的问题由驱动
  直接回 `code`，你的裁决不用再把它们写成 `target=code`（写了也不会被机械地板覆盖）。
- 每条 issue 必须带 `figure_id`（`figures/manifest.json` 的键）、`category: "diagram"`、
  `severity`、`evidence`（具体到哪张图的哪个位置，例如“右侧 55% 空白”“图例压住 3 条曲线”）、
  `fix`（⑦ 能执行的动作：重画/换图型/改 loc/拆面板/裁 xlim）、`recheck`。
  **没有 `figure_id` 的 issue 不算可执行回执** —— ⑦ 无法判断该动哪张图，只能全量重渲。
- 报告末尾裁决行与 JSON `status` 必须一致；不一致一律判 `verdict_conflict`、整条不放行。
- 本阶段不在 `content_quality.REQUIRED` 里，所以 `enforce()` 会原样放行你的裁决 ——
  没有第二道校验兜着。自己把住：塞进 `issues` 的必须是真能让 ⑦ 动手的东西，
  别把"我觉得这张图不够好看"写成硬伤。

### 未打回但可优化的项：写 `FIGURE_POLISH_QUEUE.json`

有些问题不值得为它把整个 ⑦ 打回（比如“右侧留白偏多”“色标少了一档”“图例可以再靠左”），
但 ⑦ 下次跑的时候应该顺手改。把它们写进 `reports/FIGURE_POLISH_QUEUE.json`：

```json
{
  "schema_version": 1,
  "generated_by": "8Figure-gate",
  "figures": {
    "q3_dryfront": [
      {"id": "POLISH-q3_dryfront-1", "severity": "soft", "category": "diagram",
       "evidence": "右侧约 55% 空白，色标只用了 3 档",
       "fix": "改半栏或裁 xlim；按 quantity 取 gamma 拉开低端",
       "recheck": "打开 PNG，确认信息密度和色阶档数"}
    ]
  }
}
```

- 只有**不影响 claim 成立**的版面/可读性问题进这个队列；影响结论的进 `issues` 并判 FAIL。
- ⑦ 每次开工先读它：只改 `figures` 里点名的图，改完在 `reports/DRAWIO_REPORT.md`
  写一行“本轮按 polish queue 改了哪些图”；没点名的图保持逐字节不变。
- 队列不会自己触发 ⑦ 重跑（⑧ PASS 后链继续走 ⑨）；它在 ⑦ 下一次因任何原因运行时生效。

## 交回规则

判 FAIL 时**不要**自己去改图。写完报告与侧车即可 —— 驱动默认按 `FAIL->drawio` 回退到 ⑦，
并把你的 issue 清单作为回执交给它。⑦ 只重渲被 `figure_id` 点名的图；**画法与图注文字类它必须
就地修完**（见 `docs/KNOWN_GAPS.md` 的 G12）。
唯一例外：机械地板报 `[lock:data]` 时，驱动直接回 ④（`target=code`），因为 ⑦ 只读 bundle、
改不了数据。你的侧车里把这类写成 `category: "data_integrity"`，并写清是哪个 bundle/source 变了。

**回执里必须把"重渲染"和"重算"分清楚**，这是这一关最贵的一处判断：

| 机械地板报的 | 真因 | 该做的事 |
|---|---|---|
| `数据、脚本、配置或图片已改变，需重新生成和复核` | 多半是改了 `config/visualization.json` 或 `lib/visualization/*.py`（配色/字号/风格库） | **重跑 `figures/make_figures.py` 重渲染 + 重新登记 + 重新目检** —— 图的内容没变，**不要重算数值**。（脚本住在 `figures/`，不在 `code/`，见 `_input_split` 的注释。）也可能是别人在登记路径之外重渲过：`.pdf`/`.svg` 内嵌时间戳，任何重跑都换字节 ⇒ 单看这两种文件变了而 PNG 没变，就是这一类 |
| `[lock:data]` | bundle/source 在锁之后变了（数值/来源被改，或 ④ 改了却忘了重出锁） | **回 ④**：重出 `figures/data` + lock；⑦ 只读数据，修不了 |
| `[lock:contract]` | spec 的 fields/field_mapping/claim/statistics 被改过 | **回 ⑦**：把 spec 改回锁定值；要改语义就交回 ④ |
| 位图质量 / 图例压数据 | 那一张图的画法有问题 | 改画图脚本的那一张（只重渲被点名的 `figure_id`） |
| 版式体检不过 | `.drawio` 的形状/位置撞了 | 改 drawio 几何 |

**为什么必须写清**：⑦ 只能把这单子交给 ④，而 ④ 一看"图不合格"最容易整段重跑
（小时级）。只是换了个配色，没有理由把数值重算一遍。

复查：⑦ 改完回来后，本阶段会重跑一次。只需复核上一轮的未解决项
（增量返修，见 `stage_discipline.md` 一），不要把全部 12 张从头再怀疑一遍。
