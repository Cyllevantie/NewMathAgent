"""Run from project root: python -m lib.visualization --help."""
import argparse
import json
from pathlib import Path

from .evidence import audit, register, review


def main():
    parser = argparse.ArgumentParser(description="Figure provenance and visual-review records")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("audit")
    check = sub.add_parser("review", help="Only after opening actual rendered images")
    check.add_argument("id")
    check.add_argument("--reviewer", required=True)
    check.add_argument("--note", required=True)
    reg = sub.add_parser("register", help="Register external DrawIO/custom assets using a JSON spec")
    reg.add_argument("spec", type=Path)
    args = parser.parse_args()
    if args.action == "review":
        review(args.root, args.id, reviewer=args.reviewer, note=args.note)
    elif args.action == "register":
        spec = json.loads(args.spec.read_text(encoding="utf-8"))
        register(args.root, **spec)
    else:
        problems = audit(args.root)
        print(json.dumps({"status": "FAIL" if problems else "PASS", "issues": problems}, ensure_ascii=False, indent=2))
        return bool(problems)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
