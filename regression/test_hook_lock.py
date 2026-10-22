# -*- coding: utf-8 -*-
"""面板锁 PreToolUse 护栏哨兵：Bash/PowerShell 也不许绕过锁写正式目录。

旧实现只拦 Write/Edit/MultiEdit；Bash 的 tool_input 只有 command，_path_of
返回 None，cp/mv/rm/重定向/python -c 都能直接写 code/。测试在临时项目根里
复制一份 hook 并造锁文件，真实调用进程断言退出码，不碰仓库里真实的
.fma_panel_lock。
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
HOOK = PROJECT / "runtime" / "hooks" / "fma_hook.py"


class HookLockTests(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.root = Path(self._td.name)
        (self.root / "runtime" / "hooks").mkdir(parents=True)
        shutil.copy2(HOOK, self.root / "runtime" / "hooks" / "fma_hook.py")
        (self.root / "code").mkdir()
        (self.root / "_tmp").mkdir()

    def tearDown(self):
        self._td.cleanup()

    def _run(self, tool, tool_input, locked=True, stage=None):
        lock = self.root / ".fma_panel_lock"
        if locked:
            lock.write_text("sentinel", encoding="utf-8")
        else:
            lock.unlink(missing_ok=True)
        ev = {"hook_event_name": "PreToolUse", "tool_name": tool,
              "tool_input": tool_input, "cwd": str(self.root),
              "session_id": "hook-lock-test"}
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        if stage:
            env["FMA_STAGE"] = stage
        else:
            env.pop("FMA_STAGE", None)
        p = subprocess.run(
            [sys.executable, str(self.root / "runtime" / "hooks" / "fma_hook.py")],
            input=json.dumps(ev, ensure_ascii=False), capture_output=True,
            text=True, encoding="utf-8", errors="replace", env=env,
            cwd=str(self.root), timeout=30)
        return p.returncode, (p.stderr or "")

    # —— 反向对照 1：修复前下面这些命令返回 0（绕过锁），修复后必须是 2 ——
    def test_bash_write_into_protected_blocked(self):
        for cmd in ("cp _tmp/a.py code/a.py",
                    "mv _tmp/a.py results/a.csv",
                    "rm -rf code",
                    "cd code && rm a.py",
                    "cd code&&rm a.py",
                    "a;rm code/x",
                    "cat _tmp/x|tee code/a.py",
                    "echo x>code/a.py",
                    "A=1 rm code/x",
                    "sudo rm code/x",
                    'bash -c "rm code/a.py"',
                    "robocopy _tmp reports /E",
                    "mkdir code/x",
                    'python -c "open(\'code/a.py\',\'w\').write(\'x\')"',
                    'python -c "import shutil; shutil.copy(\'_tmp/a\', \'figures/a\')"'):
            with self.subTest(cmd=cmd):
                rc, err = self._run("Bash", {"command": cmd})
                self.assertEqual(rc, 2, cmd)
                self.assertIn(".fma_panel_lock", err)

    def test_redirection_into_protected_blocked(self):
        for cmd in ("echo x > code/a.py",
                    "echo x 2>code/a.py",
                    "echo x >> paper/main.tex",
                    "cat code/a.py > _tmp/a.txt"):  # 保守口径：提到受保护目录即拦
            with self.subTest(cmd=cmd):
                rc, _err = self._run("Bash", {"command": cmd})
                self.assertEqual(rc, 2, cmd)

    def test_powershell_write_into_protected_blocked(self):
        for cmd in ("Set-Content -Path code/a.py -Value x",
                    "New-Item -ItemType File -Path reports/a.md",
                    'powershell -Command "Remove-Item -Path code/a.py"'):
            with self.subTest(cmd=cmd):
                rc, _err = self._run("PowerShell", {"command": cmd})
                self.assertEqual(rc, 2, cmd)

    # —— 反向对照 2：纯读和写 _tmp 必须放行，防止护栏变成「一律拦」 ——
    def test_read_only_allowed(self):
        for cmd in ("grep -rn foo code",
                    "grep -n cp code/a.py",
                    "grep -n rm code",
                    "cat code/a.py",
                    "ls -la code results",
                    "python -m pytest regression/test_hook_lock.py -q",
                    'python -c "print(open(\'code/a.py\').read())"'):
            with self.subTest(cmd=cmd):
                rc, _err = self._run("Bash", {"command": cmd})
                self.assertEqual(rc, 0, cmd)

    def test_write_tmp_allowed(self):
        for cmd in ("cp _tmp/a.py _tmp/b.py",
                    "echo x > _tmp/a.txt",
                    "mkdir -p _tmp/x",
                    "cp _tmp/a.py _tmp/code/a.py"):  # _tmp 下的 code 不是正式目录
            with self.subTest(cmd=cmd):
                rc, _err = self._run("Bash", {"command": cmd})
                self.assertEqual(rc, 0, cmd)

    def test_write_tool_guard_unchanged(self):
        rc, _err = self._run("Write", {"file_path": "code/a.py", "content": "x"})
        self.assertEqual(rc, 2)
        rc, _err = self._run("Write", {"file_path": "_tmp/a.py", "content": "x"})
        self.assertEqual(rc, 0)

    def test_no_lock_allows_bash_write(self):
        rc, _err = self._run("Bash", {"command": "cp _tmp/a.py code/a.py"}, locked=False)
        self.assertEqual(rc, 0)

    # —— 阶段内禁止 git：② 曾用 `git show HEAD:2026A试跑示例/...` 捞回已删归档 ——
    def test_stage_git_is_blocked(self):
        for cmd in (
            "git show HEAD:2026A试跑示例/其余文件/内部报告/ANALYSIS_MODELING_REPORT.md",
            "cd . && git log -1 --oneline",
            "git cat-file -p HEAD:.env",
            "git ls-tree -r --name-only HEAD | grep 2026A",
            'bash -c "git show HEAD:2026A试跑示例/core.py"',
            'python -c "import subprocess; subprocess.run([\'git\',\'show\',\'HEAD:x\'])"',
        ):
            with self.subTest(cmd=cmd):
                rc, err = self._run("Bash", {"command": cmd}, locked=False, stage="analysis")
                self.assertEqual(rc, 2, cmd)
                self.assertIn("禁止使用 git", err)
        rc, err = self._run("PowerShell", {"command": "git show HEAD:x"}, locked=False,
                            stage="analysis")
        self.assertEqual(rc, 2)
        self.assertIn("禁止使用 git", err)

    def test_main_agent_git_is_allowed(self):
        rc, _err = self._run("Bash", {"command": "git status --short"}, locked=False)
        self.assertEqual(rc, 0)

    def test_stage_non_git_read_is_allowed(self):
        rc, _err = self._run("Bash", {"command": "grep -n git reports/x.md"}, locked=False,
                             stage="analysis")
        self.assertEqual(rc, 0)


if __name__ == "__main__":
    unittest.main()
