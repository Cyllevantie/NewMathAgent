# 绘图门禁报告（⑧ figreview · 2026-09-29 · 第 3 轮）

> 本阶段**只判不改**：除本报告与 `reports/FIGURE_REVIEW_REPORT.verdict.json` 外，没有动过任何一张图、
> 任何一份论文/报告、任何 `code/`、`results/`、`config/`、`lib/` 文件。本轮取证脚本与产物全在 `_tmp/`
> （新写 7 支：`fig8c_ink_overlap.py`、`fig8c_redline_text.py`、`fig8c_geom_final.py`、`fig8c_nolegend.py`、
> `fig8c_fp_check.py`、`fig8c_change_face.py`、`fig8c_detail.py`；其余为复用上一轮的）。
> 收口时 `python -m lib.visualization audit` 仍 PASS（`_tmp/fig8c_audit.txt`）。

## 结论

**本阶段结论：PASS**（与 `reports/FIGURE_REVIEW_REPORT.verdict.json` 的 `status` 一致；`target` 不填 —— 不回退任何阶段）

一句话：回执那唯一一条未解决项（`fig-5-caliber-baseline-through-label`）**已落地并经交付像素三级复量**；
本轮盘面相对上一轮只动了 1 张 PNG 的画面（`caliber_sensitivity`），数值面（`code/` + `results/`）逐文件
零变化；机械地板 PASS；无新增未解决项。

## 0. 起点：回执逐条在**现盘**复验

本轮回执 = `runtime/quality/feedback/a705ae79/f8efc38e/gate_decision.json`
（`stage=figreview`、`status=FAIL`、`target=drawio`、**1 条 soft issue `fig-5`** + 2 条 info advisory）。
它是驱动对上一轮本报告的裁决，也是交给 ⑦ 的修复单；⑦ 已就地修完（`reports/DRAWIO_REPORT.md` §1.1，21:48）。
**不采信任何自述** —— 逐条按回执自己给的 `recheck` 现读交付件 + 现算：

| recheck 要求（回执原文） | 本轮独立复验（真实输出） | 结论 |
|---|---|---|
| 重跑 `_tmp/fig8b_line_text_cross.py` `ref` 模式 ⇒ `caliber_sensitivity` 命中数 **0** | 13 张全报「线穿字：无」，`caliber_sensitivity` 一整节为空（`_tmp/fig8c_line_text_cross_ref.txt`） | ✅ |
| 同上 `all` 模式 | 唯一残留是 `数据线 _nolegend_ 穿过 '53.05'`；本轮**用像素级判据独立重判**为探针假阳（见 §3.1），不是图的问题 | ✅ |
| 放大交付像素目检 `56.85` 与 `56.97` 两处无压字 | 打开 `figures/caliber_sensitivity.png` 直接裁放（`_tmp/fig8_crops/fig8c_two_labels_r3.png`，×3）：`56.85` 在其蓝点**左侧**、红线距其字身 46.3 px；`56.97` 在右侧，红线只从首字「5」**左侧留白**经过、笔画未触及 | ✅ |
| 列出 `figures/caliber_sensitivity.png` 的 sha256（与其余被改图一起） | 现算 `39a7dea5766cb249cc3f64ce8f562526244f73f7274c775b5a155dd1084ab801`；**其余 18 张 PNG 相对上一轮盘面逐字节未变**（§1） | ✅ |
| `_tmp/fig8_repro_check.py` 仍 13/13 | `⇒ 沙箱重渲与交付 PNG 逐字节相同：13/13`（`_tmp/fig8c_repro_check.txt`） | ✅ |
| `python -m lib.visualization audit` 仍 PASS | `{"status": "PASS", "issues": []}`、退出码 0（`_tmp/fig8c_audit.txt`） | ✅ |

**issue `fig-5` 的三级复量**（字框 → 墨迹 → 交付像素几何），全部落在**交付 dpi=220** 的同一套坐标上：

| 量 | 值 | 来源 |
|---|---|---|
| 基准线（`axvline(vals[0]=57.15, color=WARN, lw=1.2, linestyle="--")`）中心列 | x = **1086.33**，半宽 1.83 px ⇒ 列区间 **[1084.50, 1088.17]** | `_tmp/fig8c_geom_final.txt`（`transData` 变换，与渲染路径无关） |
| `56.85`（`env_plateau` 档）字框 | x[980.0, 1042.0]（**改前** x[1078.7, 1140.7]，整行翻到点的左侧） | 同上（自证帧 == 交付 PNG） |
| `56.85` 字**墨迹** | x[982, 1040] ⇒ 距基准线列 **46.33 px** | 同上 |
| `56.97`（`env_peak` 档）字框 / 墨迹 | x[1088.8, 1150.8] / x[1090, 1149] ⇒ 距基准线列 **3.67 px**（距线右缘 1.84 px） | 同上 |
| 字框含竖线的档数 / 墨迹含竖线的档数 | **0 / 0**（7 档全量） | 同上 |
| 「参考线墨迹 ∩ 非图例文字墨迹」像素数（13 张交付图） | **0**（`caliber_sensitivity` 最小净空 3 px，是全集合里最紧的一张） | `_tmp/fig8c_ink_overlap.txt` |

（⑦ 自述的「净空 +44.34 px」与本阶段测的 46.33 px 不矛盾：它按**字框右缘**量、本阶段按**墨迹右缘**量，
差 2 px 就是字框自带的 ascent/descent/pad 留白。两种锚点都指向同一事实：线已完全离开该标注。）

**落实面的独立证据**：`figures/make_figures.py` 对**驱动回退快照**（`产物/cache/2026A_2026.9.29_21.31.50/技术路线图/快照/`，
`.snapshot.json` 记 `at=21:10:22`）的逐行 diff **只有两处**：把 7 条标注收进 `anns` 列表，以及新增
「画完一版、量字框、凡字框含基准线列且点在基准线左侧的翻到左侧」的自适应块（含注释）。
**caption / claim / 数值 / `xlim` / 色阶 / 参考线本身一字未动** —— 与 §1 的像素面结论互证。

## 1. 改动面：只重渲染，没有重算（独立于 ⑦ 自述）

参照物 = **驱动自己**在本轮开工时存档的盘面（上面那份快照），逐文件 sha256（`_tmp/fig8c_change_face.txt`）：

- `code/` 快照 4 项、`results/` 快照 4 项：**相同 4、变化 0、缺失 0** ⇒ 数值面一个字节没动；
- `figures/*.png`：**逐字节相同 18 张、变化 1 张（共 19）**，变化的那张正是
  `figures/caliber_sensitivity.png` —— 与回执唯一一条 issue 的落点**一一对应**；
- `figures/**` 里其余变化全是 13 张数据图的 `.pdf`/`.svg`（内嵌时间戳 + 因
  `make_figures.py` 进了每张图的 snapshot 而整批重渲，属既定机制，**PNG 逐字节相同即画面零变化**）
  加上 `figures/make_figures.py` 本身；
- `reports/` 快照 3 项：2 项未变（含 `ANALYSIS_MODELING_REPORT.md`）、1 项变化 = ⑦ 自己的 `DRAWIO_REPORT.md`；
- `request/` 2 项未变。

⇒ 本轮就是「**重渲染 + 重登记 + 重目检**」，没有任何重算，也没有越权改前序报告。

## 机械地板

```json
{
  "status": "PASS",
  "issues": []
}
```

`python -m lib.visualization audit` → **PASS / `issues=[]`**，退出码 0（原样输出 `_tmp/fig8c_audit.txt`）。
19 张图的 sources/script/config/图片哈希快照与复核签名都是当前版本。

**地板过 ≠ 本关过**：本关的价值在机器闸**结构上查不到**的那一半 —— `quality.texts_overlap` 只查
文字与文字、`legend_data_overlap` 只查图例框与数据线，**参考线 / 判据线穿过文字**没有任何闸门覆盖。
上一轮判出的 `fig-5` 正是这一类。

## 2. 逐张复核

增量返修纪律：本轮只有 `caliber_sensitivity` 的像素变了（§1），故**重判它一张**；其余 18 张 PNG
逐字节未变 ⇒ 画面与结论继承上一轮，不自证重签。判据一律以**交付像素**为准，前置自证
`_tmp/fig8c_repro_check.txt` = 13/13 沙箱重渲与交付 PNG 逐字节相同。

| 图 | 本轮像素 | 选型 | 读得清 | 不超载 | 与 claim 一致 | 结论 |
|---|---|---|---|---|---|---|
| `caliber_sensitivity` | **变**（标注落点） | 横排点图 ✓ | ✓ 基准线不再与任何标注的字框或**字身**相交（字框含线 0 档、墨迹含线 0 档，最小净空 3.67 px）；图例外置在坐标区下方、不压数据；7 档 y 轴长标签逐行分开 | 7 档 ✓ | ✓ 四个跨度 0.30 / 0.43 / 0.03 / 4.1 h 复算成立（数值未动） | 通过 |
| `q3_criteria` | 未变 | 折线 ×2 ✓ | ✓ 两栏图例在轴下；`t_dry` 点线全程连续 | 3 条 ✓ | ✓ `t_dry=57.1383 h`、`g=+5.15e-7` 复算成立 | 通过 |
| `q1_profiles` | 未变 | 折线 ×2 ✓ | ✓ 7 条两两可辨（颜色/线型/标记至少一重不同） | 7 条 > 配色循环 6，已由线型+标记补足 ✓ | ✓ 表 1/表 2 格点口径不变 | 通过 |
| `q2_diffusivity` | 未变 | 响应面 + 轨迹 ✓ | ✓ 轨迹 vs 局部背景 L1 最小 118 | 1 条 ✓ | ✓ caption 的「红」字已同句去掉、7.67 倍仍在 | 通过 |
| `rb_uncertainty` | 未变 | 直方图 + 代价曲线 ✓ | ✓ 图例在轴下、不遮均值线 | ✓ | ✓ 「本阶段自设区间」已在 caption 明写 | 通过 |
| 其余 14 张（`q1_field`、`q2_moist_field`、`q2_temp_field`、`q2_drydown`、`q3_dryfront`、`q4_shrinkage`、`q4_field`、`q4_effects`、`convergence`、`rb_tornado`、`fig_roadmap`、`fig_geometry`、`fig_coupling`、`fig_q4_material`） | **逐字节未变** | 继承上一轮 ✓ | 继承 ✓（本轮另以新探针对其中 12 张数据图做了**墨迹级**复量，见 §2.1） | 继承 ✓ | 继承 ✓ | 通过 |

### 2.1 覆盖与选型（全集口径，未变）

Q1 2 图 / Q2 4 图 / Q3 2 图 / Q4 3 图，每问 ≥2 张且每问至少一张非折线 ✓；唯一真有三维结构的是圆柱几何
（已用轴测图 + 径向截面），`D(C,T)` 走二维响应面 + 色标（不是压成折线的二维剖切）；13 张数据图最小
字号 **8.0 pt**、最大 9.0 pt（`min_font_size=8` 无违例）；「一张大图」只约束**非数据图**（判据在
`skills/7Route-diagram/SKILL.md` 第 113 行那节的原文），4 张非数据图本轮 PNG 全未变。

### 2.2 本轮新做的两项墨迹级复量（对上一轮结论的加强，不是推翻）

上一轮与本轮的既有探针里，「线穿字」一直只有**字框**判据；回执 `fig-5` 的判词与 `recheck` 却都是按
**字身**下的。本轮因此补了两支**遮罩差分**探针（把 artist 单独 `set_alpha(0)` 再存一帧，差分即它的像素），
把判据落到墨迹这一层，覆盖到 13 张数据图的**全部**参考线与全部文字：

- `_tmp/fig8c_ink_overlap.py`：**参考线墨迹 ∩ 非图例文字墨迹 = 0 像素**（13 张合计；含
  `q3_criteria`/`q4_shrinkage`/`q2_drydown`/`q4_effects`/`q2_temp_field` 的 `axhline`/`axvline`）；
- `_tmp/fig8c_redline_text.py`：三张场图的**红色判据线**（`contour(highlight=TH)` 那一层住
  `ax.collections`、**不在 `ax.lines`**，机器闸全盲）与全部非图例文字墨迹 **0 像素相交**，最小净空 >8 px。

## 3. 本轮免于误报的四处（判据写清，供下一轮直接引用）

1. **`_nolegend_ 数据线穿过 '53.05'` 是探针假阳 —— 但上一轮给的理由不完整，本轮已改正。**
   上一轮写「该线 `get_linestyle() == 'None'` ⇒ 根本不画」。实测（`_tmp/fig8c_nolegend.txt`）：这条
   `Line2D` 的 `marker='o'`、`linestyle='None'` —— 它**确实画了 2835 个像素**（7 个蓝色数据点，
   主色 `(29,78,216)`），只是**不描连接线段**。`fig8b_line_text_cross.py` 的 `disp_pts()` 是按
   `get_xydata()` 逐点连线采样，于是量出一条**并不存在**的折线穿过 `53.05`。正确判据 = **按"该 artist
   实际画出的像素"过滤**，而不是按 `get_linestyle()` 反推。该 artist 实画的像素与文字墨迹**相交 0 像素**。
2. **`q3_criteria` 的 `−0.5`、`rb_uncertainty` 的 `−5`「文字入框」是假阳，本轮给了决定性判据。**
   上一轮用放大目检判的，本轮改成机械判据（`_tmp/fig8c_fp_check.txt`）：把该 `Text` 单独 `set_alpha(0)`
   再存一帧，**差分像素 = 0** ⇒ 它在交付画面里一个像素都没画（不是"被图例盖住"——盖住也会有差分）。
   两个对象都 `不在任何 Axes 上`，两张图的自证帧都 == 交付 PNG。
3. **「红像素紧贴深色像素」这类颜色阈值判据不能用在场图上。** 本轮试过一版纯交付像素的
   颜色距离探针（`_tmp/fig8c_delivery_ink.py`），它在 `q1_field` 上报出 6.5 万个「相邻」像素 ——
   根因是色阶高端本身就是红的、而坐标轴脊线是深色的，两者天然相邻。**颜色阈值只能判"这一条线"，
   判"线穿字"必须用艺术家遮罩差分。** 已作废该探针的判据（脚本留档）。
4. **`caliber_sensitivity` 的 `56.97` 是"擦框不压字"**：7 档里它与基准线最近（墨迹净空 3.67 px、
   距线右缘 1.84 px），但字身未触及。这条是上一轮就判定的既有事实，本轮数值化留存，**不是缺陷**；
   回执「不许让它变坏」的要求满足（改前 2.44 px、改后 3.67 px，反而更宽）。

## 4. 三条渲染口径（**下一轮必须先读**，本轮实测踩出来的）

本阶段所有「遮罩差分」探针都栽在同一个坑上，写下来免得下一轮重踩：

1. **每一次 `savefig` 都必须在 `charts.style()` 的 `rc_context` 之内。** 出了 `with` 就退回默认
   `DejaVu Sans`，渲出来的**不是交付画面**（实测：context 外存帧的 sha256 ≠ 交付，context 内存才 ==）。
2. **每一帧都要按生产 `export()` 的后缀顺序存：`.pdf → .svg → .png`。** 只存 png 时 13 张里 **9 张**
   与交付**不同字节**；先存矢量再存位图才复现交付字节。（别自作主张"只存 png 更快"。）
3. **每张图先做一次"不改任何东西再存一帧"的确定性对照**，必须与首帧逐字节相同；不过就先修口径，
   否则差分测的是渲染抖动而不是 artist 的去留。（本轮修好口径前，`q4_field` 曾因此报出 2 个像素的
   假命中，其 bbox 与「两次空渲染」的差分 bbox **一模一样**，可据此认出这是抖动而不是图的问题。）

配套：`_tmp/dr7_probe_lib.py` 的 `render()` 在 `with` **之外**又 `canvas.draw()` 了一次，会写脏
Text 的 layout 缓存 —— 直接用它的 `fig` 去差分（而不是用它存好的 PNG）会命中陷阱 1。本轮三支新探针
都改用自带 `build()`（全程在 context 内建图并首渲），并把「首帧 sha256 == 交付 PNG」当硬断言。

## 5. checks

完整的 `reason` 与 `evidence`（每项含 `file` 与逐字 `quote`）见 `reports/FIGURE_REVIEW_REPORT.verdict.json`。

| id | status | 要点 |
|---|---|---|
| `mechanical_floor` | passed | `{"status":"PASS","issues":[]}`，退出码 0 |
| `receipt_fig5_baseline_through_label` | passed | 回执唯一一条 issue 已落地：字框含线 0 档、墨迹含线 0 档、最小净空 3.67 px；交付像素目检无压字 |
| `refline_ink_overlap`（新） | passed | 13 张数据图「参考线墨迹 ∩ 文字墨迹」= 0 像素 |
| `red_criterion_line_ink`（新） | passed | 三张场图的红色判据线（`ContourSet`）与文字墨迹 0 像素相交 |
| `receipt_fig1_caption_caliber` | passed | `q1_field` caption 的 6.19 mm 与 `1e-5` 半句现算逐位相符，旧串已不在交付串 |
| `receipt_fig2_drydown_caliber` | passed | `q2_drydown`/`q2_moist_field` 的 0.02 kg/kg 与 22.2 h 现算相符 |
| `receipt_fig3_legend_refline` | passed | 15 张图（含图级图例）图例×参考线命中 = 0 |
| `receipt_fig4_series_styles` | passed | 每栏 (色,线型) 组合 = 7、7 个标记互不相同 |
| `change_face_isolation` | passed | 对**驱动快照**：`code/`+`results/` 逐文件零变化；PNG 恰 1 张变 |
| `sandbox_repro` | passed | 13/13 沙箱重渲 == 交付 PNG（判据都落在交付件上） |
| `type_selection` / `dimension_use` | passed | 场→填充等高线、切片/指标→折线、类别比较→点图；三维结构用轴测 |
| `claim_match` | passed | 变化的 1 张 + 继承的 12 张，caption/claim 均与现算值相符 |
| `readability` | passed | 本轮唯一变化项已修，且全集合墨迹级复量无命中（上一轮此项为 failed） |
| `series_overload` / `field_dead_color` / `font_size` / `big_figure_rule` | passed | 逐条复量，口径见 `.verdict.json` |

## 6. 未解决项

（无 —— 本轮没有需要派给任何阶段的 issue。）

## 7. 延后建议（advisories，随回退投递；本轮无回退，仅供下游阶段读取）

两条均为上一轮登记、本轮复核仍成立的**非本阶段处置面**事项：

| id | category | severity | 实测 | 建议 | 去向 |
|---|---|---|---|---|---|
| `adv-roadmap-print-font` | presentation | info | `figures/fig_roadmap.pdf` 的 MediaBox 687.12×932.88 pt（242.4 mm），源 `FS=16 px` ⇒ PDF 内 11.52 pt；按登记宽 138.7 mm（=0.85\textwidth）排印折算 ≈ **6.6 pt** < `min_font_size=8`（本阶段独立复算，与 `DRAWIO_REPORT.md` §7 相符；本轮该 PNG 逐字节未变） | 不在 ⑦ 的处置面（实测提字号会被 `check_layout.py` 判 14/24/38/49 条版式失败）。按 `docs/VISUALIZATION.md` 第 6 条归 ⑭：在「整页横排 / 精简重排 / 接受 6.6 pt 并在图注注明」之间定夺 | format |
| `adv-analysis-d-drop-3mm` | report_wording | info | `reports/ANALYSIS_MODELING_REPORT.md:358`（③ 的产物，本阶段与 ⑦ 都不改，本轮实测该文件逐字节未变）：「本段含水率变化极小，$D$ 的下降只发生在最外层 3 mm」—— 与本轮回执 issue 同族的**无口径量级句**，按同表同段自己用的 `\|ΔC\|>0.1 kg/kg` 口径现算是 6.19 mm | 只改报告里的这一句：把口径写进同句、数按该口径现算（或删去括号里的量级判断）。不涉及任何图与数值 | analysis |

## 8. 复评轮须知（下一轮 ⑧ 直接从这里开始）

- 机械地板由驱动直接跑，先看它在不在 PASS；**本轮无未解决项，正常路径下本阶段应当收口**。
- 本轮**已核为真、不必重查**：回执一条 issue 的落地（§0，三级复量）；改动面隔离（§1，对**驱动快照**）；
  13/13 沙箱自证；13 张图的墨迹级「参考线穿字」= 0（§2.2）；三张场图的红判据线穿字 = 0；字号无违例；
  `q1_field` 的 6.19 mm / `1e-5`、`q2_drydown`+`q2_moist_field` 的 0.02 kg/kg / 22.2 h、
  `q1_profiles` 的 7 组样式、`q2_diffusivity` 的轨迹对比度。
- 复用本轮探针（都在 `_tmp/`，下一轮**先原样重跑**）：`fig8c_ink_overlap.py`（参考线墨迹 vs 文字墨迹）、
  `fig8c_redline_text.py`（红判据线）、`fig8c_geom_final.py`（逐档净空）、`fig8c_nolegend.py`
  （逐条线"实画了多少像素"）、`fig8c_fp_check.py`（文字是否真绘制）、`fig8c_change_face.py`
  （对**驱动快照**的改动面）、`fig8b_line_text_cross.py`（字框判据；`all` 模式要按"实画像素"过滤）、
  `fig8b_legend_geom.py`/`fig8b_legend_zero.py`（图例几何，含图级图例）、`fig8b_issue_recheck.py`
  （现读交付串 + 现算）、`fig8_repro_check.py` + `dr7_probe_lib.py`（13/13 沙箱自证）。
  ⚠️ 跑前先读 §4 的三条渲染口径。

## 整题门禁裁决：PASS

（与 `reports/FIGURE_REVIEW_REPORT.verdict.json` 的 `status` 一致；本阶段不回退任何上游。）
