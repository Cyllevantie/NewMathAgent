# AI 工具使用详情 PDF：统一生成模板

> 2026-10-20 用户确认：`paper/ai_tools/AI工具使用详情.pdf` 统一按本模板生成。
> 生成器：`skills/9Paper-writing/scripts/make_ai_tools_pdf.py`。
> **不要手写 PDF，也不要手改生成后的 `.tex`**；改内容就改 `reports/AI_TOOL_USAGE.json` 后重跑脚本。

## 1. 口径

- 12pt 宋体、行距 1.375、页边距与论文正文模板一致（上 2.42 / 下 2.27 / 左 2.50 / 右 2.18 cm）；
- 不写队伍信息、使用起止时间、记录方式；
- 不写“问题重述由 AI 改写”；
- 记录统一用 `提示词：` / `AI：` / `队员：`，正文不出现“我”；
- 生成器在写盘前做内容校验（见下文“内容校验”）；不合规时退出码 2，不写任何产物；
- 末尾只写“人工主导说明”，不再重复“详见支撑材料”的声明（本文件本身就是支撑材料）；
- AI 只承担辅助：文献检索线索、公式排版、代码框架、图表文字建议、语言润色；
  核心建模、假设、推导、求解、结果分析与结论由队员完成。

## 2. JSON schema

`reports/AI_TOOL_USAGE.json`：

```json
{
  "competition": "全国大学生数学建模竞赛（2026 年）",
  "problem": "A 题：药材的烘干问题",
  "tools": [
    {
      "name": "ChatGPT-6 Astra",
      "access": "桌面应用 / 网页端",
      "purpose": "LaTeX 公式排版、图表文字建议、语言润色"
    },
    {
      "name": "DeepSeek-Flash",
      "access": "Visual Studio Code 插件",
      "purpose": "PSO 算法代码框架与调试辅助"
    }
  ],
  "records": [
    {
      "title": "LaTeX 公式排版",
      "prompt": "推导出的方程是……请只把它转成 LaTeX 代码，保持符号和上下标不变，不要解释。",
      "equation": "\\rho c_p\\frac{\\partial T}{\\partial t}=\\frac{1}{r}\\frac{\\partial}{\\partial r}\\left(k r\\frac{\\partial T}{\\partial r}\\right)",
      "ai": "给出了对应的 LaTeX 代码。",
      "ai_code": "\\rho c_p\\frac{\\partial T}{\\partial t}=...",
      "member": "核对偏导符号、上下标、括号和量纲，补上分母括号后放入论文公式环境。公式本身由队员推导。",
      "adoption": "约 80%",
      "check": "偏导、下标、括号、量纲与队员的推导逐符号一致"
    }
  ],
  "code_rows": [
    {"part": "数据读取与参数", "ai": "由队员完成；AI 未生成数据或参数"},
    {"part": "核心求解器", "ai": "由队员完成有限体积离散与阈值求根；AI 未参与核心推导"},
    {"part": "PSO 代码框架", "ai": "AI 给出骨架；队员按本题目标/约束重写并测试"},
    {"part": "论文文字", "ai": "队员撰写；AI 仅做 LaTeX 排版和语言润色"}
  ],
  "manual_note": "除上述辅助环节外，选题、模型建立、算法设计、参数选择、结果分析和结论均由队员完成。"
}
```

### 字段说明

| 字段 | 必填 | 说明 |
|---|---|---|
| `competition` | 是 | 竞赛名称 |
| `problem` | 是 | 题号与题目 |
| `tools[]` | 是 | `name` / `access` / `purpose`，三项都必须非空 |
| `records[]` | 是 | 至少 1 条；每条给 `title` / `prompt` / `member` |
| `records[].equation` | 否 | **原始 LaTeX**，不要带 `\[` `\]`；脚本会插入公式环境 |
| `records[].ai` | 否 | AI 输出摘要（普通文本） |
| `records[].ai_code` | 否 | 原始代码/LaTeX 文本，脚本用 `verbatim` 原样排出 |
| `records[].adoption` | 否 | 如“约 80%”；没有写 `—` |
| `records[].check` | 否 | 人工核验重点；所有记录的 `adoption` / `check` 全空时省略第四节 |
| `code_rows[]` | 否 | 代码与数据说明；`part` / `ai` 都必须非空 |
| `manual_note` | 否 | 人工主导说明；省略时用模板默认句 |

### 内容校验

`build_tex` 在写盘前逐字段检查，不合规直接报错（退出码 2），**不会**留下半成品 `.tex`：

- 普通文本字段不得出现“我”；
- 不得出现“本参赛队”“使用起止时间”“未保留完整聊天截图”“问题重述”；
- `tools[].name` / `access` / `purpose` 三项必须非空；
- `code_rows[].part` / `ai` 两项必须非空。

普通文本字段指 `competition` / `problem` / `tools` 三项 / `records` 的
`title` / `prompt` / `ai` / `member` / `adoption` / `check` / `code_rows` 两项 /
`manual_note`。`equation` 与 `ai_code` 是原样排版的 LaTeX/代码，**不参与**上述文字校验。

节号按实际小节顺延：`adoption` / `check` 全空时没有“采纳与人工核验”，
后面的“代码与数据说明”“人工主导说明”自动升一级（如 `四、代码与数据说明`、`五、人工主导说明`）。

## 3. 生成

```bash
python skills/9Paper-writing/scripts/make_ai_tools_pdf.py
# 只写 tex、不编译：
python skills/9Paper-writing/scripts/make_ai_tools_pdf.py --no-compile
```

输出：

```
paper/ai_tools/AI工具使用详情.tex
paper/ai_tools/AI工具使用详情.pdf
```

`--no-compile` 只写 `.tex`，但会**删掉**已有的 `paper/ai_tools/AI工具使用详情.pdf`：
delivery 只按“文件存在”认件，数据改了却留着旧 PDF，交付的就是上一版内容。
所以用过 `--no-compile` 之后盘上没有可交付 PDF，要交付必须重跑完整编译。

脚本会跑两遍 xelatex。源文件保持为生成物；不要手改。要改字体/页边距/版式，改脚本本身，
然后重跑并同步 `regression/test_ai_tools_pdf.py`。

## 4. 记录写法

每条记录固定三段：

```text
提示词：……
AI：……
队员：……
```

- 提示词用“请……”的原始请求，不要写成“让 AI 改写……”的概述；
- `队员：` 写人工核对/修改/舍弃，不写“我”；
- 不要写“问题重述由 AI 改写”这类条目；
- 不要写队伍信息、使用起止时间、记录方式；
- 以上禁用语由生成器强制校验（退出码 2）；命中时改 `reports/AI_TOOL_USAGE.json`，不要绕过脚本；
- 声明只写在论文正文参考文献前，不在本文件重复。
