import argparse
import json
import sys
from pathlib import Path

# 判据里全是中文。Windows 控制台默认 GBK，直接 print 会乱码；在真有问题时更糟 ——
# 调用方按 UTF-8 解就得到一串替换符，看不出到底哪一条不合规。与 lib/web/healthcheck.py 同一处置。
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from lib.visualization.evidence import write_json

from .checks import check, report
from .core import configured_output_dir, load_manifest, package, resolve_submission_dir


def main():
    parser = argparse.ArgumentParser(description="提交形状的交付包：打包 / 校验")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--output-dir", default=None,
                        help="**产物根**路径；不给则读 config/delivery.local.json（面板里设的那个），"
                             "再退到项目根下的 产物/。传空串 = 强制用默认。"
                             "提交件根是它下面的 提交作品/最新作品/（本 CLI 的操作对象）")
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("check", help="只读校验：提交件根白名单 + 清单对账")
    sub.add_parser("package", help="按清单打包出提交件")
    sub.add_parser("report", help="校验并把结果落盘 reports/DELIVERY_CHECK.json")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    # 操作对象是**提交件根**（`<产物根>/提交作品/最新作品`），不是产物根 ——
    # 白名单判据只在那一层成立（见 core.py 顶部布局图）。产物根下还有 cache/、
    # 各阶段产物/、提交作品/ 三个目录，传产物根会一跑就 FAIL，报错还会告诉 agent
    # 把 `各阶段产物` 挪进 `其余文件/`（而这条命令就在 agent 的 recheck 里）——
    # 会把归档目录搬走。
    # 产物根默认**读面板配置**：硬编码 `<root>/产物` 会让面板一改路径、这条命令就查错
    # 目录并报假 FAIL（门禁把它交给 agent 当 recheck）。
    out_dir = configured_output_dir(root) if args.output_dir is None else args.output_dir
    out = resolve_submission_dir(root, out_dir)

    if args.action == "package":
        items = load_manifest(root)
        package(root, out, items)
        print(f"已打包 → {out}")
        # 打完**立刻**校验并如实返回非零。驱动侧本来就是 package→check 两步；
        # 而直接敲 `package` 时，会得到一份**已知不合规**却看似成功的包
        # （白名单、demo 白屏这些都只有 check 能发现）。
        problems = check(root, out, items)
        if problems:
            print("但产物不合规：")
            for p in problems:
                print("  ✗", p)
            return 1
        return 0

    result = report(root, out)
    if args.action == "report":
        write_json(root / "reports/DELIVERY_CHECK.json", result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result["status"] != "PASS"


if __name__ == "__main__":
    raise SystemExit(main())
