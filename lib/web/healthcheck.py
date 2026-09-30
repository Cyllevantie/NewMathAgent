# -*- coding: utf-8 -*-
"""NewMathAgent 健康检查：技能一致性 / 模板 / 引用 / Web 端点 / 上传往返 / JS。"""
import json, re, sys, urllib.request
from pathlib import Path

# 让输出在 GBK 控制台下也不崩：打印报错行会在异常**非空**时抛
#   UnicodeEncodeError —— 也就是**这个工具只在"真有问题"的时候崩掉**，恰好在最需要它
#   说话的时候闭嘴（负对照 exit=1，却一行报错都看不见，就是这么来的）。
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# 仓库根**从本文件位置推**，不写死绝对路径：
#   写死 `Path(r"…")` 的话，换台机器、换个目录名、
#   或者把仓库拷到别处，这个体检就会去检查**另一个不存在的树**（而且它会报"缺 skill"，
#   看起来像仓库坏了，其实是它自己找错了地方）。本文件住 `lib/web/` ⇒ parents[2] 才是根。
ROOT = Path(__file__).resolve().parents[2]
SK = ROOT / "skills"
ok, bad = [], []
def ck(cond, msg):
    (ok if cond else bad).append(msg)

# 1) skills 一致性
# 新增阶段必须加进这张表 —— 否则体检**不会检查它**（静默漏检，不报错）。
#   表里顺序只为可读，真正权威的顺序是 lib/web/server.py 的 STAGES。
workflow = [
    "0Intake-readproblem", "1Literature-orientation", "2Modeling-design", "3Modeling-review-gate", "4Coding-and-computation", "5Result-credibility-audit", "6Robustness", "7Route-diagram", "8Figure-gate", "9Paper-writing", "10Math-proof-gate", "11Cross-question-check", "12Rubric-final", "13Repair-by-rubric-verdict", "14Layout-and-format", "15Verification", "16Web-demo"
]
for d in workflow:
    p = SK / d / "SKILL.md"
    ck(p.exists(), f"缺 skill 目录/文件 {d}")
    if p.exists():
        t = p.read_text(encoding="utf-8")
        m = re.match(r"^---\n(.*?)\n---", t, re.S)
        ck(m and f"name: {d}" in m.group(1), f"{d}: frontmatter name 不匹配")
        ck("allowed-tools" in (m.group(1) if m else ""), f"{d}: 缺 allowed-tools")
        # 每个阶段必须对通用纪律「明确表态」：引用 stage_discipline.md（豁免理由也写在同一行块里）。
        # 这条是防漂移的关键 —— 新增阶段忘了加会被体检直接抓出来，而不是靠人记得。
        ck("_references/stage_discipline.md" in t,
           f"{d}: 未引用通用纪律（应在 SKILL 里引用 _references/stage_discipline.md 并写明适用项或豁免理由）")
for extra in ["doctor", "_references"]:
    ck((SK / extra / "SKILL.md").exists(), f"缺辅助 skill {extra}")
ck((SK / "_references" / "stage_discipline.md").exists(), "缺通用纪律文件 _references/stage_discipline.md")
# 2) 模板
for fam in ["cumcm-latex", "default-latex"]:
    root = SK / "9Paper-writing" / "templates" / "zh" / fam
    main = root / "main.tex"
    ck(main.exists(), f"模板缺失 zh/{fam}/main.tex")
# 3) 引用无残留旧编号
hits = []
for p in SK.rglob("SKILL.md"):
    t = p.read_text(encoding="utf-8")
    for old in ["2analysis-modeling","3coding-visual","5writing","6verity"]:
        if re.search(rf"(?<![0-9a-z-]){old}", t): hits.append(f"{p.name}: 残留 {old}")
ck(not hits, "无旧编号残留 " + ("; ".join(hits[:5]) if hits else ""))
# 4) 前端 JS 语法
try:
    import subprocess
    html = (ROOT / "lib" / "web" / "static" / "index.html").read_text(encoding="utf-8")
    js = "\n".join(re.findall(r"<script>(.*?)</script>", html, re.S))
    tmp = ROOT / "runtime" / "_chk.js"; tmp.parent.mkdir(exist_ok=True); tmp.write_text(js, encoding="utf-8")
    r = subprocess.run(["node", "--check", str(tmp)], capture_output=True, text=True)
    ck(r.returncode == 0, "index.html JS 语法: " + r.stderr[:200])
except Exception as e:
    ck(False, "JS 检查异常 " + str(e))
# 5) python 编译
try:
    import py_compile
    for f in ["server.py", "content_quality.py", "workflow_quality.py", "attest.py", "healthcheck.py"]:
        py_compile.compile(str(ROOT / "lib" / "web" / f), doraise=True)
    ck(True, "lib/web/*.py 全部编译通过")
    # 交付包模块：忘了建/写坏时这里直接红，而不是等到收口打包才发现。
    for f in ["__init__.py", "core.py", "checks.py", "__main__.py"]:
        ck((ROOT / "lib" / "delivery" / f).exists(), f"缺 lib/delivery/{f}")
        py_compile.compile(str(ROOT / "lib" / "delivery" / f), doraise=True)
    ck(True, "lib/delivery/*.py 全部编译通过")
    sys.path.insert(0, str(ROOT))
    from lib.delivery.core import (OTHER_DIR, STAGES_PARENT, STAGES_POINTER, SUBMISSION_PARENT,
                               SUBMISSION_POINTER, delivery_name)
    ck(OTHER_DIR == "其余文件", "产物里的归档子目录名变了（打包与校验必须一致）")
    ck((SUBMISSION_PARENT, SUBMISSION_POINTER, STAGES_PARENT, STAGES_POINTER)
       == ("提交作品", "最新作品", "各阶段产物", "最新产物"),
       "两个「最新」指针的目录名变了（CLI、归档、前端都按这四个名字认）")
    try:
        delivery_name("2026A", __import__("datetime").datetime(2026, 9, 18, 19, 13, 0))
        ck(True, "归档目录名可生成")
    except Exception as e:
        ck(False, "归档目录名生成失败 " + str(e))
except Exception as e:
    ck(False, "lib/web/delivery 模块编译或自检失败 " + str(e))

BASE = "http://127.0.0.1:8901"
def get(p):
    try: return urllib.request.urlopen(BASE + p, timeout=5).status
    except Exception as e: return str(e)
ck(get("/") == 200, f"GET / -> {get('/')}")
for ep in ["/api/state", "/api/workspace", "/api/pdf", "/api/files?kind=reports", "/api/guardrails"]:
    code = get(ep)                      # 只发一次请求：每条断言各发两次是多余的往返，且 BASE 端口写死
    ck(code == 200, f"GET {ep} -> {code}")

# 7) 前端阶段表必须与后端 STAGES 一致
#    前端 STAGE_ORDER / STAGE_NAME / STAGE_GATE 是**第二事实来源**，不校验就会漂移 ——
#    加阶段或调顺序时只改后端，面板会静默出错：`STAGE_ORDER.map(...)` 是遍历渲染，
#    漏加的阶段在界面上**根本不存在**（而后端照样在跑），顺序不符则面板与实际执行序不一致。
#    与 test_gate_strings_agree_with_default_repair_map 同一套思路：把「两处说法必须一致」
#    钉成机器判据，而不是靠人记得同时改两处。
try:
    srv = (ROOT / "lib" / "web" / "server.py").read_text(encoding="utf-8")
    blk = re.search(r"^STAGES = \[(.*?)^\]", srv, re.S | re.M)
    # 逐条解析，不要用「`{` 紧跟 `"id":`」这种正则：只要某个条目被写成多行
    #   （black/人工整理后的常见写法），它整条就解析不到 —— 那样的情况下
    #   non_gate 变成 0、后端被当成 13 个门禁阶段，于是 healthcheck **报前端的错**，
    #   把维护者引到完全正确的那一侧。按 `},` 切条目、再在条目内找字段才对。
    body_src = "\n".join(l for l in (blk.group(1) if blk else "").splitlines()
                         if not l.strip().startswith("#"))
    entries = [e for e in re.split(r"\},", body_src) if '"id"' in e]
    ids, non_gate = [], []
    for e in entries:
        m = re.search(r'"id":\s*"([a-z0-9_-]+)"', e)
        if not m:
            continue
        ids.append(m.group(1))
        if re.search(r'"gate":\s*None', e):
            non_gate.append(m.group(1))
    ck(bool(ids), f"从 server.py 解析 STAGES（得到 {len(ids)} 个）")
    # 真正要查的是「**每个条目都写了 gate 键**」。漏写某个条目的
    #   `"gate": "NEEDS_FIX->code"` 整个键时，healthcheck 输出一字不变 —— 因为
    #   `gate_ids` 是「ids 减去字面写着 `"gate": None` 的那些」的**补集**，
    #   「缺 gate 键」与「有 gate 字符串」在补集里不可区分，而前端的 STAGE_GATE
    #   用的是同一个补集 → 两侧对同一个错误答案"达成一致"，比对通过。
    #   丢 gate 键的后果是那个门禁**静默变成非门禁**：不跑 content-quality、
    #   不吃 gate 逻辑指纹、gate_result 恒 "ok"。
    has_gate = sum(1 for e in entries if re.search(r'"gate"\s*:', e))
    ck(has_gate == len(ids),
       f"STAGES 每个条目都写了 gate 字段（{has_gate}/{len(ids)}）—— 缺键会让门禁静默失效")
    ck(len(entries) == len(ids),
       f"STAGES 每个条目都能解析出 id（{len(ids)}/{len(entries)} 条）")
    gate_ids = sorted(i for i in ids if i not in non_gate)

    # 补齐「每个阶段的 skill 目录确实进了上面的 `workflow` 表」这条对账。
    #   没有它的话：往 STAGES 加一个阶段、却忘了同步 `workflow` 时，体检**照样全绿** ——
    #   只是从此不再检查那个阶段的 SKILL 是否存在、frontmatter 对不对、有没有引用通用纪律。
    #   这正是本文件开头那句「新增阶段必须加进这张表 —— 否则体检不会检查它（静默漏检）」
    #   的机械化版本：把"靠人记得"换成"机器对账"。
    skills_in_stages = []
    for e in entries:
        m = re.search(r'"skill":\s*"([A-Za-z0-9_-]+)"', e)
        if m:
            skills_in_stages.append(m.group(1))
    unchecked = sorted(set(skills_in_stages) - set(workflow))
    ck(len(skills_in_stages) == len(ids),
       f"STAGES 每个条目都能解析出 skill（{len(skills_in_stages)}/{len(ids)}）")
    ck(not unchecked,
       f"这些阶段的 skill 没进 healthcheck 的 workflow 表，等于不被体检：{unchecked}")

    # 收尾**不重判内容判官**：`server.py` 里不许再长出"收尾按名单重跑判官"那段循环 ——
    #   11 过后正文就定了，12/13/14 只打磨措辞与版式；重判内容会把已定的正文拉回来重跑，
    #   所以这里守住这条约束，别让那段循环静默回来。
    ck(not re.search(r"^RECHECK_STAGES\s*=", srv, re.M),
       "server.py 里又定义了 RECHECK_STAGES —— 收尾重判已被用户明确删除，别让它悄悄回来；"
       "注释里可以提到它（说明为什么删），但**不许再有那个名单**")
    ck("_later_paper_owner" in srv,
       "缺 `_later_paper_owner`：内容判官会因 ⑬/⑭ 打磨措辞而被拉回来重跑（用户明确不要）")

    html2 = (ROOT / "lib" / "web" / "static" / "index.html").read_text(encoding="utf-8")
    ob = re.search(r"const STAGE_ORDER=\[(.*?)\];", html2, re.S)
    front = re.findall(r'"([a-z0-9_-]+)"', ob.group(1)) if ob else []
    ck(front == ids,
       f"前端 STAGE_ORDER 与后端 STAGES 不一致\n      前端 {front}\n      后端 {ids}")
    gb = re.search(r"const STAGE_GATE=\{(.*?)\};", html2, re.S)
    fg = sorted(re.findall(r'"([a-z0-9_-]+)"\s*:', gb.group(1))) if gb else []
    ck(fg == gate_ids, f"前端 STAGE_GATE 与后端带门禁的阶段不一致：前端 {fg} / 后端 {gate_ids}")
    nb = re.search(r"const STAGE_NAME=\{(.*?)\};", html2, re.S)
    fn = set(re.findall(r'"([a-z0-9_-]+)"\s*:', nb.group(1))) if nb else set()
    _miss = sorted(set(ids) - fn)
    ck(fn == set(ids),
       (f"前端 STAGE_NAME 未覆盖全部阶段：缺 {_miss}" if _miss
        else f"前端 STAGE_NAME 解析异常（拿到 {len(fn)} 个键、后端 {len(ids)} 个阶段）"))
except Exception as e:
    ck(False, "前后端阶段表一致性检查异常 " + str(e))

print(f"通过 {len(ok)} 项；异常 {len(bad)} 项：")
for b in bad: print("  ✗", b)
print("OK:" if not bad else f"共 {len(ok)} 项通过")
sys.exit(1 if bad else 0)
