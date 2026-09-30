import argparse
import json
from pathlib import Path
from .core import audit, build, export, validate


def main():
    parser = argparse.ArgumentParser(description="Source-bound metrics and independent validation")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("build")
    sub.add_parser("export")
    sub.add_parser("validate")
    check = sub.add_parser("audit")
    check.add_argument("--rendered", action="store_true")
    args = parser.parse_args()
    if args.action == "build": build(args.root)
    elif args.action == "export": export(args.root)
    elif args.action == "validate":
        result = validate(args.root)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return result["status"] != "PASS"
    else:
        problems = audit(args.root, rendered=args.rendered)
        print(json.dumps(problems, ensure_ascii=False, indent=2))
        return bool(problems)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
