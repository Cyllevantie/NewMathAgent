# 语言：图内文字跟着论文模板走

## 1. 解析顺序

`scripts/resolve_context.py` 按以下顺序判定：

1. 命令行 `--template zh/cumcm-latex`（显式覆盖）；
2. `config/delivery.local.json` 的 `template`；
3. `paper/structure.json` 的 `template`；
4. `skills/9Paper-writing/templates/*/*/roles.json` 只有一个模板族时；
5. `paper/main.tex` / `paper/paper-structure.tex` 的 CJK 比例（≥3% 判中文）；
6. 都没有：默认 `zh/cumcm-latex`（本仓库当前只有 CUMCM 模板），并在 `template_reason` 里写“default”。

输出 `reports/FIGURE_CONTEXT.json`：

```json
{
  "template": "zh/cumcm-latex",
  "template_reason": "config/delivery.local.json:template",
  "language": "zh",
  "width_mm": 160.0,
  "half_width_mm": 80.0,
  "font": "Microsoft YaHei",
  "labels_path": "skills/figure-studio/assets/labels.zh.json",
  "rule": "图内解释性文字用中文；方法名/模型名可保留英文；图注在 LaTeX 中写。"
}
```

## 2. 语言规则

| 模板 | 图内文字 | 全宽 | 半栏 | 字体 |
|---|---|---:|---:|---|
| `zh/cumcm-latex` | 中文 | 160 mm | 80 mm | Microsoft YaHei |
| `en/**`、Nature 系 | English | 183 mm | 88 mm | Arial |
| 未知 | 看正文 CJK 比例 | 160/183 | 80/88 | 对应字体 |

- 一张图只使用一种解释性语言；不要中文标题 + 英文轴标签 + 英文图例混排。
- 方法名/模型名/指标名可保留拉丁写法：TPE、SHAP、AUC、RMSE、R²、p、LSTM、CNN。但解释性文字必须是模板语言。
- 中文单位写法：`时间 / h`、`含水率 C / (kg/kg)`、`温度 T / °C`、`扩散系数 D / (m2/s)`。不要用 `$C$` 作为单位；不要把 `kg·kg⁻¹` 写成缺字方框。
- 英文单位写法：`Time (h)`、`Moisture content C (kg kg⁻¹)`、`Temperature T (°C)`、`Diffusivity D (m² s⁻¹)`。
- 图注语言与正文一致；图内短标题与图注不要重复。

## 3. 中文图的常见错误

| 错误 | 例子 | 改法 |
|---|---|---|
| 英文解释句 | `Dry front moves inward` | `干前沿向内推进` |
| 中英混排 | `中心 moisture` | `中心含水率` |
| 单位用数学模式 | `$kg/kg$` | `kg/kg` |
| 上下标缺字 | `kg·kg⁻¹` 显示方框 | `kg/kg` 或确认字体覆盖 |
| 方法名翻译 | `随机森林` 可以；`SHAP` 不译 | 保留 SHAP |
| 内部文件名 | `result3.xlsx`、`2026A` | `问题三提交版`、`同模型试算` |
| 图内大标题 | 一段话当标题 | 一句短 claim + 图注 |

## 4. 英文图的常见错误

- 中文解释句漏进英文图；
- 单位用中文中点（`kg·kg⁻¹`）而不是空格（`kg kg⁻¹`）；
- 方法名首字母大小写不统一；
- 图注用中文、图内用英文；
- 把 `p` 值写成 `P` 值。

## 5. 词表

`assets/labels.zh.json` 与 `labels.en.json` 是唯一词表。常用键：

```text
time_h, radius_cm, moisture, moisture_short, temperature, diffusivity,
dry_time, front_position, center, surface, mean, stage, shell, caliber,
relative_change, frequency, observed, predicted, residual, correlation,
std_ratio, auc, sample_size, before, after, wet, dry, front, threshold,
q1..q4, model, method, baseline, sensitivity, convergence, mesh, time_step,
feature, importance, contribution, group, paired_change, mean_change,
confidence_interval, standard_deviation, standard_error
```

加新词时同时改中英两份 JSON，不要在图脚本里硬编码翻译。

## 6. 语言与图型

- 中文图的面板标题可以短到 2–6 字（“径向剖面”“口径敏感性”）；英文图用 sentence case（“Radial profiles”“Caliber sensitivity”）。
- 中文图例条目可以短（“中心”“表面”）；英文用“Centre”“Surface”。
- 中文图里 `t_dry` 可以写作 `干燥时间 t_dry`；英文写 `Drying time t_dry`。
- 中文图不要为了“国际范”把全部标签换成英文；CUMCM 评委读的是中文正文。

## 7. 验收

- [ ] 图内解释性文字与模板语言一致；
- [ ] 方法名/单位/符号没有被误译；
- [ ] 没有缺字方框；
- [ ] 中文标点使用全角（，。；：），英文用半角；
- [ ] 图内没有整图标题（标题/图注都在 LaTeX）；面板短描述与图注不重复；
- [ ] 没有内部文件名/试算代号。
