# -*- coding: utf-8 -*-
"""按统一模板生成 `paper/ai_tools/AI工具使用详情.pdf`。

输入：`reports/AI_TOOL_USAGE.json`
输出：`paper/ai_tools/AI工具使用详情.tex` + `.pdf`

设计口径（2026-10-20 用户确认的模板）：
- 12pt 宋体、行距 1.375、页边距与论文正文模板一致；
- 不写队伍信息、使用起止时间、记录方式；
- 不写“问题重述由 AI 改写”；
- 记录用 `提示词：` / `AI：` / `队员：`，不出现“我”；
- 写盘前校验：普通文本字段不得出现“我”及“本参赛队”“使用起止时间”
  “未保留完整聊天截图”“问题重述”等禁用短语（`equation` / `ai_code` 原样排版，不查）；
- `--no-compile` 只写 `.tex` 时也删掉旧 PDF，免得 delivery 按“文件存在”把上一版交出去；
- 末尾只留“人工主导说明”，不再重复“详见支撑材料”的声明（本文件就是支撑材料）。

用法（项目根目录）::

    python skills/9Paper-writing/scripts/make_ai_tools_pdf.py
    python skills/9Paper-writing/scripts/make_ai_tools_pdf.py --no-compile
    python skills/9Paper-writing/scripts/make_ai_tools_pdf.py --data reports/AI_TOOL_USAGE.json

JSON schema 见 `skills/9Paper-writing/references/ai-tools-pdf.md`。
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

DEFAULT_DATA = "reports/AI_TOOL_USAGE.json"
DEFAULT_OUT = "paper/ai_tools"

# 正文口径（2026-10-20 用户确认）：普通文本不得出现“我”，也不得出现这些禁用短语。
FORBIDDEN_WORDS = ("我",)
FORBIDDEN_PHRASES = ("本参赛队", "使用起止时间", "未保留完整聊天截图", "问题重述")
CN_SECTION_NO = ("一", "二", "三", "四", "五", "六", "七", "八", "九", "十")


def _plain(value) -> str:
    return "" if value is None else str(value)


def _check_text(field: str, value: str) -> str:
    """拦禁用表述。只查普通文本字段；`equation` / `ai_code` 是原样排版的 LaTeX/代码，不查。"""
    for bad in FORBIDDEN_WORDS + FORBIDDEN_PHRASES:
        if bad in value:
            raise ValueError(f"{field} 含禁用表述“{bad}”")
    return value


def tex_escape(value) -> str:
    """把普通文本转成可排版的 LaTeX（不用于 equation / ai_code）。"""
    s = _plain(value).replace("\r\n", "\n").replace("\r", "\n")
    table = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    out = []
    for ch in s:
        out.append(table.get(ch, ch))
    s = "".join(out)
    s = re.sub(r"\n\s*\n+", r"\\par ", s)
    s = s.replace("\n", " ")
    return s.strip()


def _records(data):
    records = data.get("records")
    if not isinstance(records, list) or not records:
        raise ValueError("`records` 至少要有 1 条")
    out = []
    for i, rec in enumerate(records, 1):
        if not isinstance(rec, dict):
            raise ValueError(f"records[{i}] 必须是对象")
        title = _plain(rec.get("title")).strip()
        prompt = _plain(rec.get("prompt")).strip()
        ai = _plain(rec.get("ai")).strip()
        member = _plain(rec.get("member")).strip()
        if not (title and prompt and member):
            raise ValueError(f"records[{i}] 缺少 title/prompt/member")
        rec_out = {
            "title": title,
            "prompt": prompt,
            "equation": _plain(rec.get("equation")).strip(),
            "ai": ai,
            "ai_code": _plain(rec.get("ai_code")).strip(),
            "member": member,
            "adoption": _plain(rec.get("adoption")).strip(),
            "check": _plain(rec.get("check")).strip(),
        }
        for key in ("title", "prompt", "ai", "member", "adoption", "check"):
            _check_text(f"records[{i}].{key}", rec_out[key])
        out.append(rec_out)
    return out


def build_tex(data: dict) -> str:
    competition = _plain(data.get("competition")).strip() or "全国大学生数学建模竞赛（2026 年）"
    problem = _plain(data.get("problem")).strip()
    if not problem:
        raise ValueError("缺少 `problem`（题号与题目）")
    _check_text("competition", competition)
    _check_text("problem", problem)
    tools = data.get("tools")
    if not isinstance(tools, list) or not tools:
        raise ValueError("`tools` 至少要有 1 项")
    for i, tool in enumerate(tools, 1):
        if not isinstance(tool, dict):
            raise ValueError("`tools` 每一项必须是对象")
        for key in ("name", "access", "purpose"):
            value = _plain(tool.get(key)).strip()
            if not value:
                raise ValueError(f"tools[{i}] 缺少 {key}")
            _check_text(f"tools[{i}].{key}", value)
    records = _records(data)
    code_rows = data.get("code_rows") or []
    if not isinstance(code_rows, list):
        raise ValueError("`code_rows` 必须是数组")
    for i, row in enumerate(code_rows, 1):
        if not isinstance(row, dict):
            raise ValueError("`code_rows` 每一项必须是对象")
        for key in ("part", "ai"):
            value = _plain(row.get(key)).strip()
            if not value:
                raise ValueError(f"code_rows[{i}] 缺少 {key}")
            _check_text(f"code_rows[{i}].{key}", value)
    manual_note = _plain(data.get("manual_note")).strip()
    _check_text("manual_note", manual_note)

    lines = []
    add = lines.append
    add(r"\documentclass[12pt,a4paper]{ctexart}")
    add(r"\usepackage[top=2.42cm,bottom=2.27cm,left=2.50cm,right=2.18cm]{geometry}")
    add(r"\usepackage{booktabs,tabularx,array,xcolor,enumitem,hyperref}")
    add(r"\setCJKmainfont[BoldFont=SimHei]{SimSun}")
    add(r"\setCJKsansfont{SimHei}")
    add(r"\usepackage{longtable}")
    add(r"\usepackage{newunicodechar}")
    for ch, cmd in (
        ("α", r"\alpha"), ("β", r"\beta"), ("γ", r"\gamma"), ("δ", r"\delta"),
        ("ε", r"\varepsilon"), ("ζ", r"\zeta"), ("η", r"\eta"), ("θ", r"\theta"),
        ("ι", r"\iota"), ("κ", r"\kappa"), ("λ", r"\lambda"), ("μ", r"\mu"),
        ("µ", r"\mu"), ("ν", r"\nu"), ("ξ", r"\xi"), ("π", r"\pi"),
        ("ρ", r"\rho"), ("σ", r"\sigma"), ("τ", r"\tau"), ("υ", r"\upsilon"),
        ("φ", r"\varphi"), ("χ", r"\chi"), ("ψ", r"\psi"), ("ω", r"\omega"),
        ("Γ", r"\Gamma"), ("Δ", r"\Delta"), ("Θ", r"\Theta"), ("Λ", r"\Lambda"),
        ("Ξ", r"\Xi"), ("Π", r"\Pi"), ("Σ", r"\Sigma"), ("Φ", r"\Phi"),
        ("Ψ", r"\Psi"), ("Ω", r"\Omega"),
        ("≥", r"\geq"), ("≤", r"\leq"), ("≈", r"\approx"), ("≠", r"\neq"),
        ("±", r"\pm"), ("×", r"\times"), ("÷", r"\div"), ("∑", r"\sum"),
        ("∫", r"\int"), ("∂", r"\partial"), ("√", r"\sqrt{}"), ("∞", r"\infty"),
        ("→", r"\rightarrow"), ("←", r"\leftarrow"), ("↔", r"\leftrightarrow"),
        ("∈", r"\in"), ("∉", r"\notin"), ("⊂", r"\subset"), ("⊆", r"\subseteq"),
        ("∪", r"\cup"), ("∩", r"\cap"), ("·", r"\cdot"), ("°", r"^{\circ}"),
    ):
        add(r"\newunicodechar{" + ch + "}{$" + cmd + r"$}")
    add(r"\linespread{1.375}")
    add(r"\setlength{\parindent}{2em}")
    add(r"\setlength{\parskip}{0pt}")
    add(r"\renewcommand{\arraystretch}{1.35}")
    add(r"\setlength{\tabcolsep}{4pt}")
    add(r"\pagestyle{plain}")
    add(r"\begin{document}")
    add(r"\begin{center}")
    add(r"{\fontsize{17pt}{20.4pt}\selectfont\bfseries AI 工具使用详情}\\[4pt]")
    add(r"{\small " + tex_escape(competition) + r"}\\[2pt]")
    add(r"{\small 支撑材料}")
    add(r"\end{center}")
    add("")
    add(r"\section*{一、基本信息}")
    add(r"\begin{tabular}{@{}p{3.0cm}p{11.8cm}@{}}")
    add(r"\toprule")
    add(r"竞赛名称 & " + tex_escape(competition) + r" \\")
    add(r"题号与题目 & " + tex_escape(problem) + r" \\")
    add(r"\bottomrule")
    add(r"\end{tabular}")
    add("")
    add(r"\begin{tabular}{@{}p{3.2cm}p{3.6cm}p{8.0cm}@{}}")
    add(r"\toprule")
    add(r"工具及型号 & 访问方式 & 主要用途 \\")
    add(r"\midrule")
    for tool in tools:
        if not isinstance(tool, dict):
            raise ValueError("`tools` 每一项必须是对象")
        add(f"{tex_escape(tool.get('name'))} & {tex_escape(tool.get('access'))} & "
            f"{tex_escape(tool.get('purpose'))} \\\\")
    add(r"\bottomrule")
    add(r"\end{tabular}")
    add("")
    add(r"\section*{二、使用原则与范围}")
    add(r"AI 工具在本文中只承担辅助性工作：公式排版、代码框架、图表文字建议和语言润色。"
        r"核心建模与分析由参赛队员主导，包括问题理解、模型假设、控制方程、离散格式、边界条件、"
        r"求解路线、参数取值、结果分析和结论。AI 输出不直接进入论文或结果文件；每次输出都经过"
        r"队员逐项核对、修改或舍弃。论文数据均来自题面附件或队员计算，未使用 AI 生成数据、文献或结论。")
    add("")
    add(r"\newpage")
    add(r"\section*{三、具体使用记录}")
    add("")
    for i, rec in enumerate(records, 1):
        add(r"\subsection*{记录 " + str(i) + r"：" + tex_escape(rec["title"]) + "}")
        add(r"\textbf{提示词：}" + tex_escape(rec["prompt"]))
        add("")
        if rec["equation"]:
            add(r"\[")
            add(rec["equation"])
            add(r"\]")
            add("")
        if rec["ai"]:
            add(r"\textbf{AI：}" + tex_escape(rec["ai"]))
            add("")
        if rec["ai_code"]:
            add(r"\begin{verbatim}")
            add(rec["ai_code"])
            add(r"\end{verbatim}")
            add("")
        add(r"\textbf{队员：}" + tex_escape(rec["member"]))
        add("")
    # 节号随小节省略而顺延：采纳/核验全空时整节不出现，代码说明与人工主导说明各升一级。
    section_no = 3
    if any(rec["adoption"] or rec["check"] for rec in records):
        section_no += 1
        add(r"\section*{" + CN_SECTION_NO[section_no - 1] + r"、采纳与人工核验}")
        add(r"\begin{longtable}{@{}p{3.0cm}p{2.4cm}p{9.4cm}@{}}")
        add(r"\toprule")
        add(r"环节 & AI 采纳 & 人工核验重点 \\")
        add(r"\midrule")
        add(r"\endfirsthead")
        add(r"\toprule")
        add(r"环节 & AI 采纳 & 人工核验重点 \\")
        add(r"\midrule")
        add(r"\endhead")
        for rec in records:
            if rec["adoption"] or rec["check"]:
                add(f"{tex_escape(rec['title'])} & {tex_escape(rec['adoption']) or '—'} & "
                    f"{tex_escape(rec['check']) or '—'} \\\\")
        add(r"\bottomrule")
        add(r"\end{longtable}")
        add("")
    if code_rows:
        section_no += 1
        add(r"\section*{" + CN_SECTION_NO[section_no - 1] + r"、代码与数据说明}")
        add(r"\begin{longtable}{@{}p{3.4cm}p{11.4cm}@{}}")
        add(r"\toprule")
        add(r"部分 & AI 参与情况 \\")
        add(r"\midrule")
        add(r"\endfirsthead")
        add(r"\toprule")
        add(r"部分 & AI 参与情况 \\")
        add(r"\midrule")
        add(r"\endhead")
        for row in code_rows:
            add(f"{tex_escape(row.get('part'))} & {tex_escape(row.get('ai'))} \\\\")
        add(r"\bottomrule")
        add(r"\end{longtable}")
        add("")
    section_no += 1
    add(r"\section*{" + CN_SECTION_NO[section_no - 1] + r"、人工主导说明}")
    add(tex_escape(manual_note) or
        r"除上述辅助环节外，选题、模型建立、算法设计、参数选择、结果分析和结论均由队员完成。"
        r"AI 输出均经过人工审查与核验；语言润色未改变数值、公式和结论。")
    add("")
    add(r"\end{document}")
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="生成 AI工具使用详情.pdf（统一模板）")
    ap.add_argument("--root", type=Path, default=Path.cwd())
    ap.add_argument("--data", default=DEFAULT_DATA)
    ap.add_argument("--out-dir", default=DEFAULT_OUT)
    ap.add_argument("--no-compile", action="store_true", help="只写 .tex，不跑 xelatex")
    args = ap.parse_args(argv)

    root = args.root.resolve()
    data_path = root / args.data
    if not data_path.is_file():
        print(f"缺 {data_path}；schema 见 skills/9Paper-writing/references/ai-tools-pdf.md", file=sys.stderr)
        return 2
    try:
        data = json.loads(data_path.read_text(encoding="utf-8-sig"))
        if not isinstance(data, dict):
            raise ValueError("JSON 根节点必须是对象")
        tex = build_tex(data)
    except Exception as exc:  # noqa: BLE001
        print(f"AI_TOOL_USAGE.json 不合法：{exc}", file=sys.stderr)
        return 2

    out_dir = root / args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    tex_path = out_dir / "AI工具使用详情.tex"
    pdf_path = out_dir / "AI工具使用详情.pdf"
    tex_path.write_text(tex, encoding="utf-8")
    if args.no_compile:
        # 只写 .tex 也要清掉旧 PDF：delivery 只按 is_file() 认件，
        # 数据或模板改了之后留着旧 PDF，交付的就是上一版内容。
        pdf_path.unlink(missing_ok=True)
        print(f"已写 {tex_path}")
        return 0

    xelatex = shutil.which("xelatex")
    if not xelatex:
        print("找不到 xelatex；先安装 TeX Live，或仅用 --no-compile 生成 .tex", file=sys.stderr)
        return 2
    # 旧 PDF 先删：xelatex -halt-on-error 失败时可能已经写出半份，
    # 不能让它留在交付路径上被 delivery 的 is_file() 当成有效件。
    pdf_path.unlink(missing_ok=True)
    for _ in range(2):
        p = subprocess.run(
            [xelatex, "-interaction=nonstopmode", "-halt-on-error", tex_path.name],
            cwd=str(out_dir), capture_output=True, text=True,
            encoding="utf-8", errors="replace",
        )
        if p.returncode != 0:
            pdf_path.unlink(missing_ok=True)
            print(p.stdout[-3000:], file=sys.stderr)
            print(p.stderr[-1000:], file=sys.stderr)
            return 1
    if not pdf_path.is_file() or pdf_path.stat().st_size < 1000:
        pdf_path.unlink(missing_ok=True)
        print(f"PDF 未生成或过小：{pdf_path}", file=sys.stderr)
        return 1
    print(f"已生成 {pdf_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
