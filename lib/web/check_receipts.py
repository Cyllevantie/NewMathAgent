# -*- coding: utf-8 -*-
"""返修台账自检：返修记录里每句「已实施」，正文里真的找得到吗？

**给 `3analysis` 收尾自检用**（也给人工排查用）。

为什么要有它：返修记录里每句「已实施」都得在正文里找得到。若直接拿记录里那句
「① §15.1 该句改『≤0.98%』」做「全文检索 ≤0.98%」自检，**记录本身就是那次命中** ——
记录把自己证明了。这类假通过有三种：`≤0.98%` / `66600 s` / `M3`+`热供给` 的命中
**全在版本表或返修记录里**、正文一处未改；另有前缀碰撞（`q4.moist_max_at_tend` 被
`..._minus_60s` 撞上）。不查出来就 review 每轮重查、每轮打回，白烧几十分钟。

判据见 `skills/_references/stage_discipline.md` 六·6.3，实现在 `lib/web/receipt_ledger.py`。
门禁侧（`4review`）与本检查**读的是同一份台账**，不另写一套。

用法：

    python lib/web/check_receipts.py                 # 在项目根跑
    python lib/web/check_receipts.py --root <其它工作区>
    python lib/web/check_receipts.py --require       # 没有回执也必须交台账（驱动刚发过回执时用）

返回码 `0 = 通过`、`1 = 有问题`、`2 = 台账缺失/不可读`。
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


def check(root, require=False):
    import receipt_ledger
    return receipt_ledger.receipt_ledger_issues(root, require=require)


def main():
    ap = argparse.ArgumentParser(description="返修台账自检（探针不许落在版本/返修记录里）")
    ap.add_argument("--root", type=Path, default=Path.cwd())
    ap.add_argument("--require", action="store_true",
                    help="没有回执也必须有台账（驱动刚给本阶段发过返修回执时用）")
    ap.add_argument("--json", action="store_true", help="以 JSON 输出，便于程序消费")
    args = ap.parse_args()
    root = args.root.resolve()
    problems = check(root, require=args.require)
    if args.json:
        print(json.dumps({"root": str(root), "status": "PASS" if not problems else "FAIL",
                          "issues": problems}, ensure_ascii=False, indent=2))
    elif problems:
        print(f"返修台账自检不过（{len(problems)} 条）：\n")
        for i, p in enumerate(problems, 1):
            print(f"  {i}. {p}")
        print("\n修法：`reports/RECEIPT_LEDGER.json` 里每条回执项给 **probes** ——"
              "「改完之后才会出现在正文里」的检索串，**复合判词一个探针一个，逐小项给**。\n"
              "  · 探针在正文里 0 命中 → 说明没真改（记录里那句「已改为 X」不算）；\n"
              "  · 只出现在版本/返修记录区 → 记录自证，同样不算；\n"
              "  · 回执的 `fix` 里编了 ①②③ 的，`applied` 就必须给同样多条互不包含的探针；\n"
              "  · 只做了一部分 → disposition 写 `partial` 并写清 `remaining`，别写 applied；\n"
              "  · 没做 → 写 `not_applied` + `reason`，诚实登记比谎报便宜（review 下一轮照样会查）。")
    else:
        print(f"返修台账自检通过：{root}")
    missing = any(("缺返修台账" in p) or ("不可读" in p) for p in problems)
    return 0 if not problems else (2 if missing else 1)


if __name__ == "__main__":
    raise SystemExit(main())
