import argparse
import json
from pathlib import Path
from .checks import bind_map, inspect
from lib.visualization.evidence import write_json


def main():
    parser = argparse.ArgumentParser(description="Page-budget and formula-presentation preflight")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("check", help="Read-only; suitable for final verification")
    sub.add_parser("report", help="Writing stage: save reports/PUBLICATION_CHECK.json")
    mapping = sub.add_parser("map", help="Bind explicitly checked physical page ranges to current PDF")
    mapping.add_argument("spec", type=Path)
    args = parser.parse_args()
    if args.action == "map":
        bind_map(args.root, args.spec)
        return 0
    result = inspect(args.root)
    if args.action == "report":
        write_json(args.root / "reports/PUBLICATION_CHECK.json", result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result["status"] != "PASS"


if __name__ == "__main__":
    raise SystemExit(main())
