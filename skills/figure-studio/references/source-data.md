# 来源数据：每个面板都能追溯

> 图不是“最终产物”，是“数据 + 变换 + 编码”的结果。来源数据的作用是让审稿人/队友/未来的你
> 能在不看绘图脚本的情况下，重画同一张图。

## 1. 目录约定

```text
figures/
  data/<id>.npz              # ④：只读数据包
  spec/<id>.json             # ④：recipe + fields/field_mapping + claim/stats
  <id>.lock.json             # ④：bundle/spec 语义/source/claim 哈希
  make_figures.py            # ⑦：渲染器
  <id>.pdf / .svg / .png     # ⑦：成品
  <id>.meta.json             # ⑦：渲染元数据
  source_data/
    <id>__a.csv              # ⑦：逐面板 tidy CSV
    <id>__b.csv
  manifest.json              # ⑦：登记（sources 含 bundle/spec/lock）
```

- ④ 只写 `data` / `spec` / `lock`；⑦ 只读这三件并写其余。
- 每个面板一个 tidy CSV；文件名 `<figure_id>__<panel>.csv`；
- 首行是列名；一行一个观测；不要合并单元格/多级表头；
- 大场图可以一个面板一个 CSV（`t_h, r_cm, C`），不要只给截图；
- 原始数据（xlsx/npz/csv）路径写进 `figures/manifest.json` 的 `sources`；
- 派生数据写清派生规则（插值/分箱/归一化/排序）。

## 2. meta 侧车

`figures/<id>.meta.json` 至少包含：

```json
{
  "schema_version": 1,
  "figure_id": "q3_field",
  "language": "zh",
  "template": "zh/cumcm-latex",
  "width_mm": 160,
  "height_mm": 110,
  "font": "Microsoft YaHei",
  "claim": "干前沿由表面推进到中心。",
  "caption": "问题三含水率场；红虚线为 C=0.15。",
  "source_data": {
    "a": "figures/source_data/q3_field__a.csv",
    "b": "figures/source_data/q3_field__b.csv"
  },
  "counts": {"a": 19362, "b": 84},
  "intervals": "无统计区间；判据为 C=0.15。",
  "exclusions": "无。",
  "spec": "figures/spec/q3_field.json",
  "figure_lock": "figures/q3_field.lock.json",
  "data": "figures/data/q3_field.npz"
}
```

- `counts`：每个面板参与绘图的观测数/点数/格数；
- `intervals`：区间类型、方法、水平；没有就写“无”；
- `exclusions`：排除了哪些行/列/点，before/after 计数和理由；没有就写“无”；
- `claim/caption` 与 `manifest.json` 一致。

## 3. counts / intervals / exclusions 怎么写

### counts

- 场图：`t` 行 × `r` 列 = 总格数；如果有 NaN，写 `total` 和 `finite`；
- 剖面：时刻数 × 半径数；
- 配对：对数；
- 点图：类别数/口径数；
- 预测诊断：观测数/预测数（多模型要分开）。

### intervals

- `无统计区间；每条曲线是一个确定性模拟时刻。`
- `95% CI of mean paired change; 5,000 subject-level bootstrap replicates.`
- `±1 sample SD across 20 seed-level means; not a confidence interval.`
- `情景区间：17 个计算口径的最小/最大值；不是 CI。`

### exclusions

- `无。`
- `排除 t<60 s 的 1 行预热数据；绘图用 3,686/3,687 行。`
- `环境截断口径 76.2 h 超出 72 h 观察窗；保留并标注，不参与均值。`

## 4. 原始 vs 派生

| 类型 | 例子 | 写法 |
|---|---|---|
| 原始观测 | 实验测量、题目附件 | 路径 + 字段 + 单位 |
| 模拟输出 | result3.xlsx 的水分场 | 路径 + 网格 + 时间基准 |
| 派生 | 归一化时间配对、粗网格重建、分类标签 | 路径 + 派生规则 + 原始来源 |
| 试算 | 同模型敏感性/收敛 | 标“同模型试算”，不与提交版混用 |
| 外部 | 文献/其他题 | 不进入本论文图；如必须，明确标注 |

## 5. FAIR 最小检查

- **可发现**：`sources` 路径存在；文件名有意义；
- **可访问**：不依赖本机绝对路径；交付包里能打开；
- **可互操作**：CSV UTF-8（Excel 兼容可用 UTF-8-SIG）；列名英文/拼音，单位写列名或 meta；
- **可复用**：脚本 + meta + source_data 一起交付；不只有 PNG。

## 6. 常见错误

| 错误 | 后果 | 改法 |
|---|---|---|
| 只有 PNG，没有 CSV | 无法复核/重画 | 每面板 tidy CSV |
| CSV 是透视表/多级表头 | 机器读不了 | 一行一个观测 |
| 只给汇总均值 | 无法判断分布/配对 | 保留个体观测或明确写“只有汇总” |
| 排除点不写 | 读者不知道 | meta 写 before/after + 理由 |
| 试算数据不标 | 被当提交版 | meta/图注写“同模型试算” |
| 绝对路径 | 换机打不开 | 项目相对路径 |
| CSV 与图数值对不上 | 信任崩塌 | 图从 CSV/原始数据重算，不手抄 |

## 7. 与 `lib.visualization` 的关系

`studio.save_figure(..., source_data={...})` 会自动：

1. 写 `figures/source_data/<id>__<panel>.csv`；
2. 把 CSV 路径加入 `sources`；
3. 调 `lib.visualization.export` 登记并做自动检查；
4. 写 `figures/<id>.meta.json`。

如果图是外部 DrawIO/示意，仍用 `python -m lib.visualization register spec.json` 登记，
并在 spec 里列全 `sources`（不能只列第一份数据）。
