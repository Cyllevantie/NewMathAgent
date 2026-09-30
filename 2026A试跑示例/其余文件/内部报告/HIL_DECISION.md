# 人工决策清单（09-30 16:54）

- **卡在阶段**：`write`（skill `9Paper-writing`）
- **原因**：你按了暂停：下面是停在这一步的上下文，接着选下一步
- **本轮返修轮次**：`{}`

## agent 的建议

- **推荐回退到**：`（无）`（来源：—）
- 可选前序阶段：intake、literature、analysis、review、code、audit、robustness、drawio、figreview、write

## 三个选项（界面上的按钮，选一个即可）

1. **接受并披露**：把未解决项记入 `reports/_KNOWN_WRITING_RESIDUALS.md` 后继续，并写机器可读的 `runtime/quality/waivers.json`（**输入一变豁免自动失效、门禁重新生效**）；适合「残余增益极小 / 纯措辞」类问题。
2. **回退重跑**：退到你选的那个阶段重跑——该阶段及之后的产物会**移入 `cache/`（不删除，可恢复）**，已完成且输入未变的阶段按回执自动跳过。
3. **再试一次**：本阶段原样重跑（可临时把本次限时设长一些）；重跑提示里会带上上次失败的原始输出。

> 原始回执：`reports/paper/main`；返修回执副本见 `runtime/quality/feedback/`。