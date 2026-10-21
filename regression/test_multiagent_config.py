# -*- coding: utf-8 -*-
"""多 agent 配置哨兵：hooks / 自定义子 agent / 面板锁 / 驱动接线。

这些配置没有类型检查：settings.json 写错一个事件名、agents.json 少一个角色、
server.py 忘了传 --agents，都要等阶段真跑起来才发现。这里只做静态存在性与 JSON 校验。
"""
import json
import unittest
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]


class MultiAgentConfigTests(unittest.TestCase):
    def test_settings_hooks_point_to_existing_script(self):
        data = json.loads((PROJECT / ".claude/settings.json").read_text(encoding="utf-8"))
        hooks = data.get("hooks") or {}
        for event in ("PreToolUse", "PostToolUse", "SubagentStop", "Stop"):
            self.assertIn(event, hooks, event)
        specs = [h for rule in hooks["PreToolUse"] for h in rule.get("hooks", [])]
        self.assertTrue(specs)
        # exec form：command 是可执行文件，args 用 CLAUDE_PROJECT_DIR 占位，
        # 避免把绝对路径烤进 settings（换目录部署后 hook 会静默失效）。
        self.assertTrue(any(str(h.get("command", "")).lower().endswith("python")
                            for h in specs), specs)
        self.assertTrue(any("${CLAUDE_PROJECT_DIR}" in " ".join(h.get("args", []))
                            and "runtime/hooks/fma_hook.py" in " ".join(h.get("args", []))
                            for h in specs), specs)
        self.assertTrue((PROJECT / "runtime" / "hooks" / "fma_hook.py").is_file())

    def test_agents_json_has_panel_roles(self):
        agents = json.loads((PROJECT / "config" / "agents.json").read_text(encoding="utf-8"))
        need = {
            "idea-mechanism", "idea-data", "idea-adversarial", "idea-optimization",
            "review-math", "review-intent", "review-mechanism", "review-data-design",
            "review-innovation",
            "audit-metrics", "audit-leakage", "audit-repro",
            "robust-params", "robust-resample", "robust-extreme",
            "fig-candidate",
            "paper-claims", "paper-format",
            "verify-structure", "verify-text", "verify-math", "verify-build",
            "demo-design",
            "lit-mechanism", "lit-method", "lit-cn",
        }
        missing = need - set(agents)
        self.assertFalse(missing, "agents.json 缺角色：%s" % sorted(missing))
        for name, spec in agents.items():
            self.assertTrue(spec.get("description"), name)
            self.assertTrue(spec.get("prompt"), name)
        # 新加的两个角色不能只剩“有 prompt”：视角/台账关键词必须还在。
        self.assertIn("失败模式", agents["idea-adversarial"]["prompt"])
        self.assertIn("可证伪", agents["idea-adversarial"]["prompt"])
        self.assertIn("INNOVATION_LEDGER", agents["review-innovation"]["prompt"])
        self.assertIn("主答案护栏", agents["review-innovation"]["prompt"])

    def test_panel_lock_protocol_exists(self):
        text = (PROJECT / "skills" / "_references" / "stage_discipline.md").read_text(encoding="utf-8")
        self.assertIn(".fma_panel_lock", text)
        self.assertIn("多 agent 面板的锁协议", text)

    def test_server_wires_agents_mcp_and_effort(self):
        text = (PROJECT / "lib" / "web" / "server.py").read_text(encoding="utf-8")
        self.assertIn('"--agents"', text)
        self.assertIn("STAGE_MCP", text)
        self.assertIn("--mcp-config", text)
        self.assertIn("STAGE_EFFORT", text)
        self.assertIn('"--effort"', text)
        self.assertIn('env["FMA_STAGE"]', text)

    def test_hook_uses_utf8_and_additional_context(self):
        text = (PROJECT / "runtime" / "hooks" / "fma_hook.py").read_text(encoding="utf-8")
        self.assertIn('reconfigure(encoding="utf-8"', text)
        self.assertIn("hookSpecificOutput", text)
        self.assertIn("additionalContext", text)

    def test_stage_import_does_not_run_server_startup(self):
        """阶段 agent import server 只为拿 STAGES/门禁函数，不许顺带恢复状态、写日志。

        旧实现把 `_clock_load/_load_pending/_restore_*` 放在模块级：agent 一 import
        就会算指纹、跑机械地板、往 web_run.log 追加行，甚至重写 verdict 档。
        修复用 FMA_STAGE 区分"阶段子进程"与"服务器本进程"。
        """
        text = (PROJECT / "lib" / "web" / "server.py").read_text(encoding="utf-8")
        self.assertIn('if not os.environ.get("FMA_STAGE"):', text)
        self.assertIn("_clock_load()", text)
        self.assertIn("_load_pending()", text)


if __name__ == "__main__":
    unittest.main()
