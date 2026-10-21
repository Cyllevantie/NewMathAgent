# 可选：阶段最终回复的 JSON Schema

驱动里 `STAGE_JSON_SCHEMA` 默认是空表。只有某个阶段的**最终回复**确实要机器可读 JSON 时，
才把该阶段映射到这里的 schema 文件；驱动会读取文件内容并传 `--json-schema`。

例子（给一个只做只读审计的阶段）：

```json
{
  "type": "object",
  "properties": {
    "status": {"type": "string", "enum": ["PASS", "FAIL", "UNKNOWN"]},
    "issues": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "id": {"type": "string"},
          "severity": {"type": "string", "enum": ["hard", "soft"]},
          "evidence": {"type": "string"}
        },
        "required": ["id", "severity", "evidence"]
      }
    }
  },
  "required": ["status", "issues"]
}
```

注意：

- `--json-schema` **只约束最终回复**，不约束文件产物；你的报告/`*.verdict.json` 仍按现有方式写。
- 如果一个阶段既要写报告、又要返回 JSON，必须在 SKILL 里明确写“先写报告，再输出 JSON 摘要”，
  否则 agent 可能只返回 JSON、把报告省掉。
- 没有明确消费者时不要启用：多一层格式约束只会增加失败面。
