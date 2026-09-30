# -*- coding: utf-8 -*-
"""题意契约自检：`reports/TASK_CONTRACT.json` 的锚点还指得到原文吗？

**给 `3analysis` 收尾自检用**（也给人工排查用）。

为什么要有它：契约里的 `source.quote` / `model_anchor.quote` 是**逐字引用**，而报告会被改写 ——
两者是同一个阶段的两个产物，**契约先写、报告后定稿**，于是"契约引的原文在新报告里找不到"
是必然会发生的一类不一致。门禁（`4review`）查得出来，但那已经是**下一个阶段**了：
agent 的上下文早没了，人也被拦在 40 分钟之后。

所以把它前移到阶段收尾自己跑一遍 —— 判据与门禁**共用同一个函数**
（`content_quality.task_contract_issues`），不另写一套。

用法：

    python lib/web/check_contract.py            # 在项目根跑
    python lib/web/check_contract.py --root <其它工作区>

返回码 `0 = 通过`、`1 = 有问题`、`2 = 读不出来（缺文件/结构错）`。
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def check(root):
    import content_quality
    return content_quality.task_contract_issues(root)


def main():
    ap = argparse.ArgumentParser(description="题意契约锚点自检（与门禁同一判据）")
    ap.add_argument("--root", type=Path, default=Path.cwd())
    ap.add_argument("--json", action="store_true", help="以 JSON 输出，便于程序消费")
    args = ap.parse_args()
    root = args.root.resolve()
    problems = check(root)
    if args.json:
        print(json.dumps({"root": str(root), "status": "PASS" if not problems else "FAIL",
                          "issues": problems}, ensure_ascii=False, indent=2))
    elif problems:
        print(f"题意契约自检不过（{len(problems)} 条）：\n")
        for i, p in enumerate(problems, 1):
            print(f"  {i}. {p}")
        print("\n修法：把 reports/TASK_CONTRACT.json 里对不上的 quote **换成新报告里的原文**"
              "（逐字，含标点），或改引一个确实存在的段落。不要删条目 —— 删了就是少映射一条题面硬条件。")
    else:
        print(f"题意契约自检通过：{root}")
    # 缺文件/结构错也是一种「问题」，但对调用方要能区分开，所以单给一个返回码。
    missing = any(("缺失或不可读" in p) or ("结构错误" in p) for p in problems)
    return 0 if not problems else (2 if missing else 1)


if __name__ == "__main__":
    raise SystemExit(main())
