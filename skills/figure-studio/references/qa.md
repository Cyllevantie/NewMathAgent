# QA：机器能查的 + 必须眼睛看的

> 机器全绿不等于图没问题。⑧ 的价值是“打开图、说出看到了什么、再判”。
> 本文件是 ⑧ 的逐项清单，也是 ⑦ 交付前的自检表。

## 1. 机器地板

```powershell
python -m lib.visualization audit
python skills/figure-studio/scripts/figure_lock.py verify --root .
python skills/figure-studio/scripts/audit_studio.py --root .
```

`figure_lock.py` 查数据层契约：

- `[lock:data]`：bundle/source 的 sha256 与锁不一致，或字段缺失/形状/dtype 变 ⇒ 回 ④；
- `[lock:contract]`：spec 的 fields/field_mapping/claim/statistics 被改，或 meta.claim
  与锁不一致 ⇒ 回 ⑦ 改回锁定值；要改语义就交回 ④；
- `[lock:advisory]`：旧图没有三件套，或 caption 数字不在 claim 里 ⇒ 迁移提示。

`lib.visualization audit` 查：

- 登记：`figures/manifest.json` 是否覆盖所有已登记资产；未登记 PNG/PDF/SVG 报错；
- 过期：sources / artifacts / script / `config/visualization.json` / 产像素模块的哈希是否变化；
- 自动检查：字号、越界、图例压数据、文字互压、位图质量、drawio 版式；
- 目检签名：`review` 是否对当前版本签名。

`export()` 还会打印两类**不挡复核**的提醒（⑦ 自评要读）：

- 近单色：非白像素 ≥75% 是同一个颜色 —— 场图可能近乎平坦；
- 信息密度：内容框（非白像素的包围盒）<30% 画布 —— 可能“一大片空白只用上很小一块”。
  它只是数字，不判死：地图/稀疏散点可能本来就这样，结合 claim 判断。

`audit_studio.py` 查：

- 迁移期：旧图没有 `figures/<id>.meta.json` 且脚本未使用 `studio` 时只给 advisory；新用
  `studio` 的图缺 meta 则判 issue。这样不会第一次接入就把历史图全部打红。
- `FigureBrief` **存在时**校验语言/宽度/required_fields/候选编码；没有 brief 时只给 advisory
  （迁移期不硬打红，但新图应补）。
- 每个已登记图的 `figures/<id>.meta.json` 是否有 language/template/width/counts/intervals/exclusions；
- 每个面板的 source_data CSV 是否存在；`counts` 按 panel id 记录时严格对账，未按 panel 记时只给
  advisory（迁移期）。
- 脚本里是否有 `cmap=jet/rainbow/hsv`、是否使用 `studio.style`/`charts.style`、图内文字行是否出现
  内部文件名。字体/字号的最终判据仍是 `export` 的最小字号 + 目检，**不是**按脚本里的数字猜。

## 2. 眼睛清单（逐张打开最终 PNG/PDF）

### 选型

- [ ] 二维场用了场图/等高线，不是只有折线；
- [ ] 有阈值/前沿的场用了等高线或带判据线的热图；
- [ ] 配对数据保留了配对结构，不是两组独立柱；
- [ ] 有真实区间才画区间；没有就写“无区间”；
- [ ] 二分类有真实标签才画 ROC；AUC≈1 时说明任务本身易分，不吹模型；
- [ ] 第三维真有变量才用 3D；3D 配了二维投影；
- [ ] 没有 3D 柱/3D 饼/瀑布替代曲面。

### 读得清

- [ ] 图例不压曲线；文字不压文字；轴标签没有被裁；
- [ ] 字号 ≥ 模板下限（中文 7.5/7 pt，英文 6 pt）；
- [ ] **信息密度**：有效绘图区占画布的大部分；没有“一大片空白只用上很小一块”
      （典型：右侧 55% 空白、九宫格只用了 1 格、色标只用了 2–3 档）；
- [ ] 灰度打印下 ≥5 条序列仍能区分（线型/标记）；
- [ ] 场图不是一片死色；低值平台有 gamma 或改剖面；
- [ ] 色标有量与单位；同图多栏共用范围；
- [ ] 面板字母/标题对齐，不压数据。

### 说到做到

- [ ] 图里的数值与 `results/`、`figures/source_data/` 对得上；
- [ ] 图支撑 `claim`，不是“图很漂亮但证明不了”；
- [ ] 图注写清 n、单位、区间定义、排除规则；
- [ ] 图内没有内部文件名/试算代号（`result3.xlsx`、`2026A`、`figdata_sens.npz`）；
- [ ] 中文图没有英文解释句；英文图没有中文解释句。

### 叙事

- [ ] 一张图只回答一个问题；
- [ ] 每个面板有不同 role；
- [ ] 面板顺序是论证顺序，不是数据表顺序；
- [ ] 拼版大图有一句叙事条/主标题；
- [ ] 没有重复面板（同一证据换图型再画一遍）。

## 3. 统计清单

- [ ] 独立单位是什么：时间点、对象、seed、实验重复，还是一组汇总？
- [ ] n 是多少？每个面板的 n 是否写清？
- [ ] 区间是 SD、SE、95% CI、预测区间还是情景区间？定义写清；
- [ ] 配对数据是否按对象配对？有没有把配对拆成独立样本？
- [ ] 有没有假设检验？如果有，什么检验、什么多重比较校正？
- [ ] 有没有 p 值？没有检验就不写 p；
- [ ] 有没有把“标准差”叫“95% CI”？
- [ ] 有没有把“模型在测试集上的表现”说成“因果”？
- [ ] 有没有为了图好看删点/平滑/截断？如果有，图注写清。

详见 [`statistics.md`](statistics.md)。

## 4. 来源数据清单

- [ ] 每个面板有 tidy CSV：`figures/source_data/<id>__<panel>.csv`；
- [ ] CSV 保留全部参与绘图的观测；聚合/分箱规则写清；
- [ ] `figures/<id>.meta.json` 有 `counts / intervals / exclusions`；
- [ ] 原始数据文件路径写进 `sources`；派生数据写清派生规则；
- [ ] 没有把试算/其他题数据混进提交版图；
- [ ] 排除的行/列有 before/after 计数和理由。

详见 [`source-data.md`](source-data.md)。

## 5. 阻断规则（FAIL）

以下任一条出现，⑧ 判 FAIL，回 ⑦：

- 图与 claim/正文数值不一致；
- 没有真实区间却画了误差棒/CI，或把 SD 叫 CI；
- 没有真实标签却画 ROC/PR/校准；
- 把试算/其他题数据当提交版结果；
- 图内出现内部文件名/试算代号，可能误导读者；
- 中文模板图内全是英文解释句（或反之）；
- 3D 曲面没有二维投影且遮挡严重、读者无法读数；
- 图例压数据/文字互压/轴标签被裁，且不是轻微；
- 来源数据缺失且无法追溯。

以下只记 advisory，不阻断：

- 面板标题略长；
- 图例位置不是最优但没压数据；
- 色阶不是最理想但语义正确；
- 单张图视觉不够“惊艳”。

## 6. 复核记录

```powershell
python -m lib.visualization review <figure_id> --reviewer "当前审阅者" \
  --note "写实际看到的：面板布局、图例位置、色标、仍存在的限制"
```

- 必须打开实际 PNG/PDF 后再签名；
- note 至少 12 字，写“看到了什么”，不要写“已检查”；
- 图重渲染/改数据/改宽度/改 caption 后，旧签名失效；
- 生成脚本不得自动调用 `review`。

## 7. 回归与示例

- `python -m lib.visualization.example --output tmp/visualization-example` 只生成合成数据示例，不写生产 `figures/`；
- `python -m unittest discover -s regression -v` 跑项目回归；
- 本 skill 的 demo：`评价对比/图工作室/make_gallery.py` + `build_gallery.py`；
- 真实赛题端到端仍需下一次完整运行验证。
