---
name: 14Layout-and-format
description: "论文排版与版式验收阶段（9Paper-writing 与内容判据之后、15Verification 之前）。独占模板/排版层（paper/_base/ 与 main.tex 导言区）：统一字号字体行距标题图题表题、修浮体位置与溢出重叠、执行篇幅预算、维护正文/附录跨 PDF 的编号接续、编译并逐页视觉验收。只做定点版式手术，不改一句话的措辞、不改任何数值 —— 需要动内容时写 HANDBACK_REQUEST.md 交回 write。"
allowed-tools: PowerShell, Read, Write, Edit, Grep, Glob, Agent
---

# 论文排版与版式验收

> 通用执行纪律（增量返修 / 缩比预估 / 分段落盘 / 方法标记 / 返修只动清单内）见 `../_references/stage_discipline.md`。
> 本阶段适用：一（增量返修，含 1.1 探针复用）、五（返修只动清单内）。
> 探针/量测脚本要复用（通用纪律 一·1.1）：本轮写的取证/量测脚本一律留在 `_tmp/`
> （另有散落的在 `tmp/`，两个都要看）；下一轮开工第一步 = `ls _tmp/ tmp/` → 把上一轮
> 为同一批对象写过的脚本先原样重跑（秒级，确认数在当前版本里还成立）→ 只对本轮新出现或改过
> 的对象写新脚本。别每轮从零重写 —— 全链 776 个自写脚本里 **683 个（88%）只被用过一次**
> 就再也没人碰。复用探针 ≠ 跳过复核：探针只是取证手段，判定仍逐条对着当前版本做。

本阶段位于 13Repair-by-rubric-verdict 之后、15Verification 之前（链路：… → 12Rubric-final →
13Repair-by-rubric-verdict → 14Layout-and-format → 15Verification → 16Web-demo）。

为什么内容判官（⑩⑪⑫）排在它之前：内容判据先定稿、再排版 ——
否则每改一句措辞都要重排一次（本阶段一次约 2h）。代价是它改过 `paper/` 之后，那几个判官
判过的对象已经变了。处理方式是「标出来、不自动重判」：它们进 `state["layout_superseded"]`，
面板上显眼地列着，需要时手动重跑（正文措辞打磨之后，那些判官的结论必然与当前版本对不上）。
收尾不必对内容判官重判：驱动不做收尾复验循环（见 `server.py` 里「收尾不再对内容判官重判」
那段，`healthcheck` 还专门加了条"不许它悄悄回来"的守卫）。以为"改了版式也会自动重判"是错的。
它本身便宜（改一行 LaTeX、重编译 3 秒），但逐页目检把它推到了小时级 ⇒ 别让它白跑一轮。
反过来说，**版式问题绝不该回退到 write 去重跑整篇写作**。

**为什么它必须是独立阶段而不是塞进 9Paper-writing**：LaTeX 没有干净的内容/格式分离层。
「这张图放这段论证旁边」是论证流、不是排版；`\label`/`\ref`/`\cite` 与公式环境跟正文是一体的。
所以本阶段不"重新组装内容"，只做定点版式手术。要求是：

> 正文所有东西的间距，距离上下行，大小都一样，标题自己进行统一
> （一定是这样，包括如果后续改，也遵守这个规则）

这条要求由模板层机械保证，不靠自觉 —— 见下面「模板层」一节。

## 阶段边界（做 / 不做）

| 做 | 不做 |
|---|---|
| 施加并维护模板导言区（**本阶段独占 `paper/_base/` 与 `main.tex` 导言区**） | 不改一句话的措辞（→ write） |
| 检查正文是否都在用宏（`\paperfigure` 而非手写 `figure` 环境） | 不重写论证结构、不增删结论 |
| 把「列结构与行数完全相同的两张表」并排（见下「并排双表」） | 不把已并排的表拆回 `\threelinetable` |
| 浮体位置、表格列宽字号、图宽、caption 格式 | 不改任何数值（→ code） |
| 溢出、重叠、孤立残行、公式压正文 | 不重新建模（→ analysis） |
| 篇幅预算（`python -m lib.publication`）与超页处置 | 不改数据、不改绘图方法（见下方「重画图的口子」） |
| 正文/附录跨 PDF 的编号接续 | |
| 编译（xelatex ×2）+ 逐页 PNG 视觉验收 | |

判断准则：动手前先问「这是不是定点修改」。若是重写一段、换一个结论、改一个数 ——
那不属于本阶段，写 `HANDBACK_REQUEST.md`（格式见本文末）交回对应阶段。

## 模板层（`_base/`）—— 格式规则的唯一来源

9Paper-writing 复制模板时把 `skills/9Paper-writing/templates/_base/` 一并复制到 `paper/_base/`。三层：

```
paper/_base/preamble.tex    页面/字体/行距/标题/caption/表格/浮动体/代码/断行
paper/_base/macros.tex      \papertitle \abstractcn \referencescn \appendixAcn
                            \threelinetable \papertablehalf \paperfigure
                            \paperfigurepair \paperfigurepairw
                            \paperfigurestack \appfigure
paper/_base/math-style.tex  数学字体与环境
```

`main.tex` 只写 `\input{_base/preamble.tex}` + `\input{_base/macros.tex}` + 赛事差异。

**`preamble.tex` 里几乎每条设置都带「现象 → 原因 → 改法」注释。删任何一条前先读注释** ——
多数看似多余的设置都是为了修具体的排版问题。几条最容易被人"顺手清理掉"的：

| 设置 | 删了会怎样 |
|---|---|
| `\lineskiplimit=-20pt` + `\lineskip=0pt` | 含上下标的行内公式改用 `\lineskip`，同一段里出现两种行距 —— 正是「不同行间距不一样」的来源 |
| `\raggedbottom` + `\baselineskip` 去伸缩 | `\flushbottom` 把页内胶水拉伸压缩，同段出现 18.3/20.4 成对偏差 |
| `\xeCJKsetup{CJKecglue={\hskip 0pt}}` | 设成空 `{}` 会连换行点一起删掉，行末溢出纸边（最右 19.8mm） |
| `\xeCJKsetup{PunctStyle=plain}` | 行首标点悬挂出版心（左边界 22.1mm vs 版心 25.0mm） |
| `\renewcommand{\emph}[1]{\textbf{#1}}` | ctex 把 `\emph` 映射到 KaiTi，正文出现第三种中文字体 |
| 四值同取的 `14pt` 公式间距 | 短公式与长公式到上下文的距离不一致（原为 6pt 带伸缩，两行高公式会压住下文 7.64pt） |
| `\jot=8pt` | `\jot` 是同一行间公式内相邻两行（`align`/`gather`/`cases`/`aligned`）的附加间距，LaTeX 默认只有 3pt —— 而正文行距是 19.9pt，于是"公式内部"比"公式↔文字"紧一个量级。有的公式两行挤在一起（如 (17)），而公式与公式/文字之间又显得远 ⇒ 设 8pt，让公式内 / 公式间 / 公式与文字三处净空落在同一档 |

**表格内必须重置行距**：preamble 的全局刚性行距会让表内上下相邻两行落到同一基线（叠印）。
凡多行单元格的表，表内加：
> 表题也要罩进这个组：只有表体在组里、表题留在组外时，表题那一行
> 仍带全局刚性行距 ⇒ 表题与表格第一行只隔 4.0 pt，`bbox` 重叠 6.5×6.7 pt
> （正文末页那张"支撑材料文件清单"会渲染成「说明9 支撑材料文件清单」叠印；其余表的表题到表头基线距是 24–36 pt）。修法见 `templates/zh/*/sections/A1_materials.tex`。


```latex
{\small
  \setlength{\lineskiplimit}{0pt}%
  \setlength{\lineskip}{\baselineskip}%
  \renewcommand{\arraystretch}{1.0}%
  ...
}
```

## 两行表头的横线：**既要那条线，又不许叠印**（逐页目检项）

数据表的 `时间/s` 应纵跨两行表头、且
「到药材中心的距离/cm」与紧下的 `0/0.5/1/1.5/2` 之间要有一条只覆盖数据列的横线
（`\cmidrule(lr){2-6}`）—— 不许因 booktabs 的行间胶问题把这条线撤掉。
完整规则与已知坑见 `../9Paper-writing/SKILL.md`
「数据表的两行表头」一节（含基线距数据 21.45pt → 5.41pt）。

本阶段的把关动作：逐页渲染后亲眼看每张数据表的两行表头 ——
判据是"标题行与子表头行不叠印、行标签竖直居中、局部横线只走数据列"。
这一条机器查不出来（表格叠印在 PDF 里不报错），是这个阶段存在的理由之一。

## 并排双表（`\papertablehalf`）—— **别把它拆回去**

判据不是「表窄」，而是列结构与行数完全相同 —— 同一张网格的两种量。典型就是
温度表 + 水分浓度表：同一批时刻 × 同一批距离，只是数值与单位不同。这类表要并排
放在同一个 `table` 浮动体里，两半各用 `\papertablehalf{表 N\quad 标题}` 包起来、
中间 `\hfill`：

```latex
\begin{table}[htbp]
  \centering
  \begin{papertablehalf}{表 2\quad 30 分钟内药材的温度（单位：$^\circ$C）}
    \begin{tabular}{cccccc} ... \end{tabular}
  \end{papertablehalf}\hfill
  \begin{papertablehalf}{表 3\quad 30 分钟内药材的水分浓度（单位：kg/kg）}
    \begin{tabular}{cccccc} ... \end{tabular}
  \end{papertablehalf}
\end{table}
```

**列结构或行数不同的表不要并排**（会挤）——参考件的「主要结果表 + 水分浓度表」列格式
不同，就是分开排的。

审版式时看到「两张表在同一个 `table` 里、各占半栏」，那是对的，不要因为
「正文都该用 `\threelinetable`」就把它拆回两个独立表 —— 拆开会白占约一页高度，
足以把正文顶到超页。判据与负对照由
`python lib/web/check_skeleton.py` 机械核（含**假设条数≤5、标题下有引入语、符号说明不写开头总述段**），跑它，别凭印象动。

## 重画图的口子（`figure_evidence_failed` 会路由到本阶段）

`python -m lib.visualization audit` 报「图有问题」时，三类成因、三条不同的处置——
不分清就会干出「只重新登记、没重画」这种把过期图洗成合规的事：

| 成因 | 处置 |
|---|---|
| 资产过期：`lib/visualization/*.py`、`config/visualization.json` 或绘图脚本改了 | 可以在本阶段重跑纯渲染脚本（只重画，不重算），再重新登记 + 目检。数值一步不重算 |
| 缺登记 / 缺目检复核（`未登记图表`、`缺少当前版本的视觉复核`） | 本阶段的活：登记来源 + `visualization review` 目检 |
| 数据本身变了（`code/outputs/*.npz` 变了） | 不是本阶段能修的 —— 写 `HANDBACK_REQUEST.md` 交回 `code`（重画要用新数据，那是它的产物） |

**两条硬禁止**：
1. **不得只重新登记而不重画**。资产过期意味着当前那张图不是按当前代码/配置生成的，
   只补一条登记记录会让 `visualization audit` 变绿，但交付物里的图仍是旧的 —— 那是洗白，
   也正是这个 audit 存在的意义。
2. **不得借重画改数值**。重跑渲染脚本只允许读已落盘的 `code/outputs/*`；若发现脚本里
   夹带了重新求解，那是 `code` 的活，交回。

判断顺序：先看 `visualization audit` 的 issue 文案是哪一类 → 再看 `manifest.json` 里
该图的 `sources` 有没有变 → 变了就是「数据变了」（交回 code），只有脚本/配置变了才是重画。

## 工具（都用现成的，不要另起炉灶）

| 命令 | 用途 |
|---|---|
| `python skills/14Layout-and-format/scripts/measure_layout.py paper/main.pdf` | 量行距刚性与页边距（见下） |
| `python -m lib.publication check` | 页数口径、物理页映射、A4 尺寸、20MB 上限 |
| `python -m lib.publication map <页面区段JSON>` | **重绑 `paper/page-map.json`**（按当前 `main.pdf` 的 SHA256）。重编译后只跑这一条就够，别从零手写那份 JSON —— 盘上通常已有一份，先看它是否仍匹配（`check` 会报"未绑定当前PDF"）：匹配就直接用；只需重跑 map 把新 PDF 的 SHA 绑上去。**区段必须按内容实际归属声明**：一页横跨两个类别时归前一类，或让后一类别另起一页。声明成"整页判给后一类"会被 `boundary_page_issues` 当场识破 —— `map` 直接拒绑，`check` 判 FAIL（判据：某类别的起始页上，它的起始标记必须就是这一页最上面那块文字，见 `config/publication.json` 的 `kind_start_markers`/`boundary_top_tol`）。一份声明正文 2–30 的映射会藏住"正文实际到 31 页"，机械检查算出 30 页判 PASS，超限被静默放行。 | 
| `python -m lib.publication report` | 同上但落盘 `reports/PUBLICATION_CHECK.json` |
| `python -m lib.visualization audit` | 图已登记、资产不过期、目检复核有效 |
| `xelatex -interaction=nonstopmode main.tex`（在 `paper/` 内跑两遍） | 编译 |

### 行距与页边距的机器判据

```bash
python skills/14Layout-and-format/scripts/measure_layout.py paper/main.pdf
```

判据（任一不过 = FAIL；另有不判定的情形）：

1. **规范行距 19.9pt 的占比 ≥ 15%**（`12pt × 1.2 × 1.375`，取整 19.9pt）。
   —— 不要读成"主行距必须等于 19.9"：脚本判的是占比，公式密集的稿子主行距会是
   31.6pt 之类却照样 PASS（超高的公式行成了众数，而正文行距完全正常）。
2. 页边距 = 左 25.0 / 右 21.8 / 上 24.2 / 下 13.5 mm（模板实际值，不是标称 2.5cm）。

不判定：段内相邻行不足 20 对时，行距判据单列进 `skipped`（不是 FAIL，也不是通过）——
模板刚脚手架出来、正文还很少时就是这种情形。页边距不受影响，照常判。

其它参数：`--json <路径>` 把结果同时落盘；`--no-margins` 跳过页边距检查（测非正文 PDF 时用）；
返回码 `0 = PASS`、`1 = FAIL`。（模板实际值，不是标称 2.5cm）

> 该脚本刻意没做「不得出现被挤紧的行」那条判据：它分辨不出真假（破坏
> `\lineskiplimit` 前后参数确实不同、PDF 哈希也不同，但几何量测逐档一致）。
> 那两行是否生效只能靠破坏性实验确认，脚本里写了完整记录。

### 逐页视觉验收（**必做，不能只靠文本扫描**）

纯文本扫描和编译器都看不出版式问题。必须把编译后的 PDF 每页导成 PNG 逐页看：

```bash
mkdir -p _tmp/pdf-pages
pdftoppm -png -r 160 paper/main.pdf _tmp/pdf-pages/page   # 或 mutool draw / magick
```

别每轮整本重渲（重复渲染会在 `tmp/` 下积下成百张 PNG，而 ⑮验收 Step 8 又会把同一件事做第二遍）：
- 渲染目录**固定用 `_tmp/pdf-pages/`，与 ⑮ 共用** —— ⑮ 要看的同一批页直接复用，别自己再渲一遍；
- 先比 PDF 的 SHA（`python -m lib.publication check` 会告诉你页面映射有没有失效）：
  没变 ⇒ 整批复用上一轮的 PNG，只看不渲；
- 变了 ⇒ 按 `reports/_REVISION_DIFF.md` 定位改动页 + 用 `paper/page-map.json` 的区段换算成物理页，
  **只重渲这几页 + 抽检 2–3 页**；重编译只影响页码偏移时，旧 PNG 还能按偏移复用。

逐页检查：表格是否超页边/单元格文字重叠、图片图题公式编号是否与正文重叠、公式是否越界、
是否有孤立残行或异常大空白、标题是否被裁切、中文是否有缺字乱码。
**发现问题要改 `.tex` 并重新编译，不要只在报告里说明。**

## 篇幅预算与超页处置（两段式）

读 `config/publication.json`（国赛电子版：摘要独立 1 页、正文（一～七）≤30 页、
「八、AI 工具使用说明」与「九、参考文献」合计 ≤1 页、附录不限、总计 ≤32 页、不要目录）。
参考文献不占正文额度 —— 它和 AI 说明合占 1 页，不算进 30 页。
篇幅口径是**写满 30 页、宁多不少**（超了能压，少了是真少）；低于 25 页 `publication check`
会出 warning，不判 FAIL，但要在报告里写明为什么。补页数归 `9Paper-writing`，不归本阶段 ——
本阶段只做定点版式手术，不许用缩字号/压页边距/转图片凑页，也不许自己加内容。

超页时按两段处理：

① 先做机械迁移（本阶段自己做，不必回 write）：

- 整张补充图、整张补充表、完整推导块、更细的参数表 → 移进附录
- 逐字重复的段落 → 直接删（不是迁移）

**能迁的只有「补充图」；示意图 / 求解流程图 / 关键结果图一律不在其中。** 下面那张
「哪些图必须在正文」的分配表优先级高于本条 —— 即便正文超页，也不许把示意图赶进附录腾地方。
赶走示意图是拆东墙补西墙：页数好看了，读者却再也看不懂模型是什么。
例如 `fig_q4_material`（问题四的动边界与材料坐标）按分配表属正文，不许随其它图一起迁进附录。
规则写了、没人核，就等于没有。

判据：抽掉之后正文论证仍然完整。迁完重编译，重新跑 `publication check`。

那正文装不下怎么办？ 按这个顺序，而不是动示意图：① 删逐字重复的段落；② 迁补充图 /
补充表 / 推导块；③ 仍超页 → 走下面的 ② 回 write，由 write 决定重写哪一节。
根子在 ⑨ 写作时没给图留位 —— 正文的图是**必须项**，文字才是可压的那一头（口径见
`9Paper-writing` 的「篇幅目标是写满 30 页」：先给图留位、再拿文字填满剩下的）。把 30 页
全填成文字，本阶段就只剩「赶图」这一条歪路可走。

② 仍超页 → 才回 write：写 `reports/HANDBACK_REQUEST.md` 交回，由它决定删什么迁什么。
回退时不重写整篇 —— 按 `stage_discipline.md` 第一节只重写受影响的小节。

## 哪些图必须在正文、哪些才进附录

正文一张示意图都没有是典型错误 —— 圆柱几何与边界（`fig_geometry`）、求解流程
（`fig_flow_solve`）、物质坐标与收缩（`fig_q4_material`）这类图全被放进附录即违规，
正文只剩数据图与路线图，读者读到"模型准备"时看不到模型长什么样。

分配判据（写作阶段选图、本阶段核对）：

| 进正文 | 进附录 |
|---|---|
| 题意示意图（几何、边界、坐标系、机制） | 写不下的数学推导与证明 |
| 求解流程图 / 算法框图 | 数据表（正文只留关键几行） |
| 每一问的关键结果图（判据、前沿、对比） | 支撑性图：完整场图、残差、收敛细节、灵敏度分解 |

即：读者不翻附录就能看懂"模型是什么、怎么解的、结论是什么"。
示意图（尤其是三维几何那种）不是装饰，它是"模型准备"那节的正文内容别往附录塞。

## 正文 / 附录的编号接续

正文与附录分成两个 PDF 时，**编号必须接续**，否则附录里出现「式(1)」与正文第 1 式撞号。

- 公式：数出正文的公式总数 N 后，在附录 `main.tex` 里写 `\setcounter{equation}{N}`（放在
  `\appendixAcn` 调用之前）。这个 N 是算出来的，不是写死的 —— 每次正文公式增减都要重算。
- 图：附录的图号是手打的纯文本，不是自动编号 —— 附录插图走 `\appfigure`，它用
  `\caption*`（带星号 = 不产生编号），「图 A1：」是图题里的字面量。
  附录的图号不由 `\appendixAcn` 管：附录工程 `paper_appendix/main.tex` 是直接
  `\input{sections/A_appendix}`，从不调用 `\appendixAcn`，那个计数器在附录里一次都没执行过。
  所以插一张图就要手工把后面所有图号连同行文里的按号指路一起顺延（7 张图 + 6 处指路 = 13 个号）。这件事由 `lib/web/appendix_demo_figure.py` 代劳（幂等），
  别手改。附录节文件一律以大写 `A` 起名（`A1_materials.tex`、`A_appendix.tex`）。
- 两个工程、两个 PDF：正文工程 `paper/`（末页是 `A1_materials` 清单表）与附录工程
  `paper_appendix/`（只有 `A_appendix`）。附录工程的 `\setcounter{equation}{N}` 里
  N = 正文公式总数，正文公式一有增减就要重算。源码不排进论文。

## 附录内容与 demo

- 附录最前面是 demo 交互式网页与工程实现展示 一节（标题不带括号），
  底下依次是 demo 首屏截图（图 A1）和一段介绍；原有的 `A.1`、`A.2`… 完整地跟在它后面。
- 这一节不由本阶段插，也不该由本阶段插。 demo 阶段（16Web-demo）排在整链最后，
  首次跑 format 时 demo 还没做 —— 所以它由⑯ 自己在收尾时补进去（做法与理由见
  `16Web-demo/SKILL.md` 第 6 步，命令是 `lib/web/appendix_demo_figure.py`）。
- **本阶段不要再去动附录的 demo 节。**
  ① 收尾不复验对内容判官的重判（见 `server.py` 里那段
  「收尾不再对内容判官重判」），没有任何机制会把本阶段拉回来跑第二遍；
  ② 附录里那张 demo 截图是 ⑯ 的 headless 截图
  `paper_appendix/figures/demo_shot.pdf`，不是 `figures/fig_demo.pdf` —— 去插 `fig_demo` 只会插到一张缺图。
- 本阶段对附录只做版式的事（页边界、浮动体、公式编号接续），demo 节的内容与编号归 ⑯。

## 交付包：两个 PDF、清单表、运行说明

提交出去的是一个目录（默认 `<项目根>/产物/提交作品/最新作品/`，产物根路径用户可改），形状固定：

```
产物/                                    ← 产物根（用户可选）
└── 提交作品/最新作品/                    ← 提交件根，形状固定：
    ├── 正文.pdf / 附录A.pdf / demo.html / 运行说明.md
    ├── result*.xlsx / 题目附件 / *.py（平铺，不带 code/ 前缀）
    └── 其余文件/  ← 正文/ 附录/（两个 LaTeX 工程）、辅助脚本/、内部报告/
```

提交件根下只放要提交的东西 —— 这条由 `python -m lib.delivery check` 的白名单机械校验，

> 链跑到本阶段时，提交件根还不存在（打包发生在整链收口，见 `lib/delivery/core.py` 的
> `package()`）⇒ **不要在本阶段跑 `python -m lib.delivery check`**：它必然报「提交件根还不存在」，
> 而那条报错里没有任何关于"该写哪些文件"的信息，读了 `lib/delivery/checks.py`/`core.py`/`产物` 树也是白花时间。
> 要写 A1 清单就**按白名单规则 + `reports/SUBMISSION_MANIFEST.json` 写**；要自查就用
> `lib/delivery/checks.py` 的判据逐项对照，**不要求那条命令跑通**。
不是靠自觉。多出任何一个东西都会报错并指出它该去哪。

> 产物根下另有 `各阶段产物/最新产物/<阶段名>/`（每阶段产物的镜像，供按阶段翻账）与
> `cache/`（回退快照）—— 都不是提交件，不归本阶段管，也不许往那里写。换题时驱动把
> 两个「最新」整目录改名成 `<题目标识_日期_时间>/` 再建两个空的。

本阶段负责的交付件（其余由各生产阶段产出、驱动打包）：

**① `reports/SUBMISSION_MANIFEST.json` —— 提交清单，也是打包依据。**

```json
{"schema_version": 1, "stage": "format",
 "items": [{"path": "正文.pdf", "desc": "本文正文"},
           {"path": "run_all.py", "desc": "主程序入口，依次完成附件读取、四问求解、收支核对、结果导出与检验。"}],
 "exclude": [{"path": "request/attachments/附件3/临时表.xlsx", "why": "中间产物，题目要交的是填好的 result*.xlsx"}]}
```

- `path` 是提交件根下的文件名（不带任何前缀、不带 `提交作品/` 之类的上层目录名 ——
  上层由驱动钉死，清单只描述提交件根那一层）；`desc` 一句话说清它做什么。
- **题目附件必须**每件都有交代（`lib/delivery/checks.py` 会逐件核）：
  `request/attachments/` 与 `data/` 下的每个文件，要么进 `items`、要么在
  `exclude` 里声明一句为什么不用交。漏一件都会被 `delivery check` 报出来 ——
  这条是补上"附件悄悄没进提交包、一路绿灯到交付"那个洞。
  - 附件常有子目录（如 `request/attachments/附件3/result1.xlsx`）：`items` 的 `path` 只能
    是平铺文件名，所以用 `source` 指真实相对路径（`{"path": "附件3_result1.xlsx",
    "source": "request/attachments/附件3/result1.xlsx"}`）；不写 `source` 时驱动会按基名递归找，
    只在唯一命中时采用，同名两处会报错让你写清楚。
  - `request/problem.md` / `problem.pdf` 是链的输入、不算附件，不必进清单。
- 正文 PDF 的 `path` = 论文标题 + `.pdf`（对齐参考稿
  `基于变物性耦合传热传质与动域模型的.pdf`）；工作区里那份仍叫 `paper/main.pdf`，
  只在打包时改名 —— 驱动按 `paper/main.tex` 的 `\papertitle{}` 推出这个名字
  （`lib/delivery/core.py:body_pdf_name()`，取不到回落 `正文.pdf`，两种名字都能打包）。
- 逐项核对：每个 `.py` 读它的文件头注释来写 `desc`，不要凭空编。
- 这份清单同时是正文末页清单表的来源，两边必须逐字一致。

清单表的行粒度与「说明」怎么写（照下面这份口径写，它就是样板）：

- 粒度：一行一个提交件；同类可合并成一行 —— 样板里 `附件1.xlsx、附件2.xlsx` 合一行、
  `q1.py、q2.py、q3.py、q4.py` 合一行，其余各占一行。
- **`说明` 必须带读者能用的信息，不许只写空话**。样板的写法可直接套：
  - `resultN.xlsx` ⇒ 行数 / 时间间隔 / 径向位置数 / 列语义。例：
    「问题二的温度与水分浓度结果，分为两个工作表；每表 10800 个数据行，时间间隔 1 s，包含 21 个径向位置。」
  - 源程序 ⇒ 它实现什么。例：`core.py`「实现传热传质方程的有限体积离散、隐式时间推进、
    非线性迭代和达标时刻求根。」；`export_xlsx.py`「按题目模板导出 result1.xlsx 至 result4.xlsx。」
  - `附录A.pdf` ⇒ 它补充了什么。例：「补充推导、误差与守恒检验、补充图表，以及二维端面效应和灵敏度分析的详细结果。」
  - `附件*.xlsx` ⇒ 「题目给定的输入数据，分别记录…」。
  - `AI工具使用详情.pdf` ⇒ 「说明论文研究与写作过程中 AI 工具的使用情况。」
- 覆盖要全：提交件根下每一个要提交的文件都要有一行（`.py` 也不许漏），
  与 `SUBMISSION_MANIFEST.json` 逐项对上 —— 这张表空着或只剩占位符是最严重的形态问题
  （只剩模板占位符时这一页只有几十个字符；样板那页 1022 字符）。
- 登记范围 = 「支撑材料」，不含论文本身：
  样板的表 10 登记 **AI工具使用详情.pdf / 附录A.pdf / result1–4.xlsx / 附件1–2.xlsx / 全部 .py**，
  没有 `正文.pdf` —— 论文是论文，不是"支撑材料"，末页表里去掉它
  （`SUBMISSION_MANIFEST.json` 是打包清单，照样要含正文，两者口径不同，
  别混：清单=全部提交项；末页表=支撑材料）。
- **`AI工具使用详情.pdf` 必须产出并登记**：它在提交件根放一件，
  表 10 第 1 行登记它（说明写「说明论文研究与写作过程中 AI 工具的使用情况。」），
  而正文 §八 只写一句摘要 + 「详细使用情况见支撑材料（文件清单见表 10）」。
  缺了这件，而 `paper/main.tex` 里同一句话已存在 ⇒ 悬空引用。
  做法：⑩ 在交付层产出该 PDF（内容 = 正文八节的展开：用了哪些工具、用在哪些环节、怎么核验），
  写进 `SUBMISSION_MANIFEST.json`，并在 `lib/delivery/core.py` 的 `FIXED_SOURCES` 登记源路径
  （否则打包会抛「清单里这些提交项在工作区找不到」）。

**② `paper/sections/A1_materials.tex` —— 正文末页的清单表**，照 `SUBMISSION_MANIFEST.json`
逐行生成。**表内必须重置行距**（`\lineskiplimit=0pt`/`\lineskip=\baselineskip`/
`\arraystretch=1.0`，模板里已写好）—— preamble 的全局刚性行距会让表内上下相邻两行
落到同一基线、叠印到看不清。

**③ `运行说明.md`（项目根）** —— 四段：文件准备（哪些是输入、哪些由程序生成）/
安装依赖（从 `requirements.lock.txt` 抄精确版本，不写"最新版"）/ 运行程序（入口命令）/
补充计算（灵敏度、二维对照这类不进主流程的脚本）。**文件清单必须是平铺后的名字** ——
提交件里没有 `code/` 前缀，写成 `code/run_all.py` 就与实际对不上。

④ 编译两个 PDF（各跑两遍）：
- `paper/` → `正文.pdf`（31 页正文 + 1 页清单表）
- `paper_appendix/` → `附录A.pdf`（不限页）
- 附录工程的 `\setcounter{equation}{N}` 里 N 用正文公式总数填。

> 循环依赖：清单表在 `正文.pdf` 里，而 `正文.pdf` 又在产物里。解法是清单是声明 ——
> 本阶段先声明、驱动按声明打包、`delivery check` 再逐项对账。
> 声明的那一刻 `demo.html` 还不存在（⑯ 排在链尾），这件事靠两处收口，不靠本阶段重跑：
>   ① `lib/delivery/checks.py` 的 `LATE_ITEMS = {"demo.html"}` —— 早期那关 `precheck` 直接跳过它；
>   ② 驱动在每个阶段收尾都会重打包一次（`_maybe_collect_outputs`，⑨ 及之后全覆盖），
>      ⑯ 跑完那次 `demo.html` 已就位，链尾 `final=True` 的 `package() + check()` 才逐项对账。
> 本阶段不会被拉回来跑第二遍（它跑第二次时清单不会更准，只有 demo 那次重打包会让它准）。

## 必须产出

版式层
- `paper/` 的版式修改（导言区、各节 `.tex` 的浮体/表格/图宽）
- 编译通过的 `paper/main.pdf`（= 提交件 `正文.pdf`，末页是清单表）
- 编译通过的 `paper_appendix/main.pdf`（= 提交件 `附录A.pdf`，独立工程）

交付层（见上面「交付包」一节 —— 漏了这几样，整链会在 `15Verification` 被拦下）
- `reports/SUBMISSION_MANIFEST.json` —— 提交清单，同时是打包依据与末页清单表的来源
- `paper/sections/A1_materials.tex` —— 正文末页的清单表，逐项照 manifest 生成
- `运行说明.md`（项目根）—— 文件准备 / 安装依赖 / 运行程序 / 补充计算

报告
- `reports/FORMAT_REPORT.md`：

```markdown
# 排版与版式验收报告

## 整题结论：PASS / FAIL
## 规范层核对
（preamble 是否为当前版本、有无被绕过；正文是否都在用宏，列出仍手写 figure/table 的位置）
（跑 `python lib/web/check_skeleton.py`，逐条列出它报的问题与处置：骨架与表并排是版式，
本阶段可改；引号与解释型括号是措辞，交回 write 或记在「未处理项」）
## 行距与页边距量测
（measure_layout.py 的输出：主行距、分布、页边距四项量测值）
## 篇幅
（publication check 输出：各类页数、是否超限、超限时迁了什么去附录）
## 版式缺陷与修复
| # | 位置(页/文件:行) | 现象 | 修法 | 复验 |
## 逐页视觉验收
（页数、逐页发现或"逐页未见重叠/溢出/裁切/乱码"）
## 未处理项
（为何不能在本阶段处理；需要交回哪个阶段）
```

## 返修纪律

本阶段经常被 `15Verification` 退回（它的默认回退目标就是本阶段）。按回执返修时，
改动范围必须严格等于回执清单，四条硬纪律见 `../_references/stage_discipline.md` 第五节。
版式改动尤其容易"顺手改了别的"：**改一处必须重新量一次 `measure_layout.py`**，
确认没有把已经对齐的间距弄歪。

## 动态交回规则（发现前序阶段错了）

若发现内容缺陷（措辞、结论、数值、模型）或图本身画错了，不要在本阶段硬改。创建
`reports/HANDBACK_REQUEST.md`：

```
target: <write | drawio | code | analysis | robustness | audit>   # 该问题需回退到哪个生产阶段
reason: <一句话说清：哪里不对、期望改什么>
```

然后停止本阶段并结束本轮。编排器会把它作为回退建议交给用户决策（黄灯面板），确认后才补跑。
（届时 `HANDBACK_REQUEST.md` 已被清除）。仅当问题属"版式即可弥合"时不触发。
