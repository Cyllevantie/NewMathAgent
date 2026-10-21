# 按阶段挂 MCP

驱动只在**文件存在**时给对应阶段加 `--mcp-config`，不存在就完全保持旧行为：

| 阶段 | 文件 | 建议挂什么 |
|---|---|---|
| ① 文献定向 `literature` | `config/mcp/literature.json` | PubMed / Crossref / arXiv / Scopus 等文献 MCP |
| ⑯ 交互 Demo `demo` | `config/mcp/browser.json` | Playwright / 浏览器 MCP（点滑块、拖三维、截图） |

## 怎么写

`literature.json` / `browser.json` 就是 Claude Code 的标准 MCP 配置（`mcpServers` 对象）。
例如（命令与包名按你本机实际安装的改，别照抄占位符）：

```json
{
  "mcpServers": {
    "pubmed": {
      "command": "npx",
      "args": ["-y", "@your/pubmed-mcp"],
      "env": {"NCBI_API_KEY": "${NCBI_API_KEY}"}
    }
  }
}
```

```json
{
  "mcpServers": {
    "playwright": {
      "command": "npx",
      "args": ["-y", "@playwright/mcp@latest"]
    }
  }
}
```

硬规则：

- **不要把密钥写进仓库**；用 `${ENV_VAR}` 或 MCP 自己的凭据机制。
- 不加 `--strict-mcp-config`：这两个文件只**追加**服务器，不会屏蔽你已有的 MCP。
- 写完先单独跑一次对应阶段（或 `claude -p --mcp-config ...`）确认服务器能起；
  起不来就删掉文件，驱动会回到不挂 MCP 的旧行为。
- 其他阶段不挂 MCP；不要为了“统一”给所有阶段塞同一个配置。
