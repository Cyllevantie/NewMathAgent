# -*- coding: utf-8 -*-
"""模板族本身必须编译得过。

为什么单独钉这一条：模板里把 `\\paperfigure[...]{fig_roadmap}` 从注释放成**活代码**，
而模板目录下没有对应的 `figures/*.pdf` 时编译必失败 —— `9Paper-writing` 复制模板当骨架，
编译不过整条链就卡在第一步，而这一步此前**没有任何自动化看着**
（`test_workflow` 里提到 xelatex 的地方讲的是**论文**编译，不是模板）。

判据：每个 `<语言>/<族名>/main.tex` 连同 `_base/` 复制到临时目录，`xelatex` 跑一遍，
要求 rc=0 且产出 main.pdf。本机没有 xelatex 就**跳过**（不在 CI 上假装通过）。
"""
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
TEMPLATES = PROJECT / "skills/9Paper-writing/templates"
RUNTIME_CFG = PROJECT / "config/runtime.local.json"
# 找个路径**不改产物**，只是决定这一族测试跑不跑。


def _find_xelatex():
    """按 **run.ps1 的同一口径**找 xelatex，返回 (路径 or None, 跳过时的原因)。

    为什么不能只靠 `shutil.which`：xelatex 可能装在**只有 `run.ps1` 会拼进 PATH** 的目录里
      （例如 `D:\\texlive\\2026\\bin\\windows`；`tool_directories` 在 *.py 里没有任何消费者）。
      于是「是不是走启动器跑的」就决定了这一族测试跑不跑 —— 绕过启动器、或换台没装 TeX 的机器，
      它会**静默跳过**，总输出仍然是 OK，而它守的恰恰是「模板编译不过 ⇒ 整链卡在第一步」。
      这是本仓最典型的「换台机器静默变绿」。
    保留 skipIf 语义：没装 TeX 是**合法状态**，不能把跳过改成硬失败（那会整片红）。
      只是把"为什么跳过"分成两句 —— 装了但没进 PATH，提示多半是没走 run.ps1。
    """
    env = (__import__("os").environ.get("FMA_XELATEX") or "").strip()
    if env and Path(env).exists():
        return env, ""
    tool_dirs = []
    try:
        import json
        cfg = json.loads(RUNTIME_CFG.read_text(encoding="utf-8-sig"))
        tool_dirs = [d for d in (cfg.get("tool_directories") or []) if isinstance(d, str)]
    except (OSError, ValueError, AttributeError):
        pass
    names = ("xelatex.exe", "xelatex") if sys.platform == "win32" else ("xelatex",)
    for d in tool_dirs:
        for n in names:
            cand = Path(d) / n
            if cand.exists():
                return str(cand), ""
    found = shutil.which("xelatex")
    if found:
        return found, ""
    hint = (f"本机没有 xelatex（config/runtime.local.json 的 tool_directories 里也没有）；"
            f"要跑这一族就在那里补上，或设 FMA_XELATEX")
    if tool_dirs:
        hint = (f"PATH 里没有 xelatex，而 {RUNTIME_CFG.name} 的 tool_directories 里那几个目录"
                f"也没有 —— 多半是没走 `run.ps1`（只有它会把那些目录拼进 PATH）")
    return None, hint


XELATEX, XELATEX_WHY = _find_xelatex()


def families():
    if not TEMPLATES.is_dir():
        return []
    return [m.parent for m in sorted(TEMPLATES.glob("*/*/main.tex"))]


@unittest.skipIf(XELATEX is None, XELATEX_WHY)
class TemplateCompileTests(unittest.TestCase):
    def test_every_template_family_compiles(self):
        fams = families()
        self.assertTrue(fams, "找不到任何模板族")
        failures = []
        for fam in fams:
            with tempfile.TemporaryDirectory() as td:
                box = Path(td) / fam.name
                shutil.copytree(fam, box)
                base = TEMPLATES / "_base"
                if base.is_dir():
                    shutil.copytree(base, box / "_base")
                (box / "figures").mkdir(exist_ok=True)   # 模板里引用的图由写作阶段产出
                proc = subprocess.run(
                    [XELATEX, "-interaction=nonstopmode", "main.tex"],
                    cwd=box, capture_output=True, text=True,
                    encoding="utf-8", errors="replace", timeout=180)
                name = f"{fam.parent.name}/{fam.name}"
                if proc.returncode != 0 or not (box / "main.pdf").exists():
                    bad = [ln for ln in (proc.stdout or "").splitlines()
                           if ln.startswith("!")][:4]
                    failures.append(f"{name}: rc={proc.returncode} " + " | ".join(bad))
        self.assertEqual(failures, [], "模板编译不过：\n" + "\n".join(failures))

    def test_templates_do_not_reference_missing_figures(self):
        """模板里的 `\\paperfigure` 若被放开，它引的图必须在模板里存在 —— 否则上面的编译必红。

        这条把上面那条的失败**提前成一条可读的诊断**：直接指出是哪个族、哪个文件、
        引了哪个不存在的图，不用去翻 xelatex 日志。
        """
        import re
        missing = []
        for fam in families():
            sec = fam / "sections"
            if not sec.is_dir():
                continue
            for p in sorted(sec.glob("*.tex")):
                text = p.read_text(encoding="utf-8", errors="replace")
                for line in text.splitlines():
                    if line.lstrip().startswith("%"):
                        continue                       # 注释掉的槽位不算
                    for m in re.finditer(r"\\paperfigure(?:pair|pairw|stack)?"
                                         r"(?:\[[^\]]*\])?\{([^}]*)\}", line):
                        ref = m.group(1).strip()
                        if not ref or "\\" in ref:
                            continue
                        if not (fam / "figures" / f"{ref}.pdf").exists():
                            missing.append(f"{fam.parent.name}/{fam.name}/{p.name}: {ref}")
        self.assertEqual(missing, [],
                         "模板里放开了引用不存在图片的 \\paperfigure（放成注释，"
                         "或把图一起放进模板）：\n" + "\n".join(missing))


if __name__ == "__main__":
    unittest.main()
