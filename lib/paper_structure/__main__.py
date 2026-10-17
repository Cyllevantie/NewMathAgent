# -*- coding: utf-8 -*-
"""CLI for role-based paper structure assembly."""
import argparse
import json
import sys
from pathlib import Path

from .core import StructureError, assemble, check, sync_title

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def _common():
    p = argparse.ArgumentParser(add_help=False)
    p.add_argument("--root", type=Path, default=Path.cwd())
    p.add_argument("--profile", type=Path, default=None)
    p.add_argument("--template", default=None)
    p.add_argument("--out", type=Path, default=None)
    return p


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Assemble the paper structure from roles.json")
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("assemble", parents=[_common()], help="write paper-structure.tex + structure.json")
    sub.add_parser("check", parents=[_common()], help="read-only structure check")
    sub.add_parser("sync-title", parents=[_common()], help="copy \\papertitle from blocks/title.tex")
    args = parser.parse_args(argv)

    try:
        if args.action == "assemble":
            plan = assemble(args.root, args.profile, args.template, args.out)
            print(json.dumps({
                "status": "PASS",
                "template": plan["template"],
                "profile": plan["profile"],
                "profile_source": plan["profile_source"],
                "problem_count": plan["problem_count"],
                "problem_count_source": plan["problem_count_source"],
                "enabled": plan["enabled"],
                "warnings": plan["warnings"],
            }, ensure_ascii=False, indent=2))
            return 0
        if args.action == "check":
            result = check(args.root, args.out)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0 if result["status"] == "PASS" else 1
        if args.action == "sync-title":
            plan = sync_title(args.root, args.out)
            print(json.dumps({"title": plan.get("title"), "title_source": plan.get("title_source"),
                              "warnings": plan.get("warnings", [])}, ensure_ascii=False, indent=2))
            return 0
    except StructureError as exc:
        print(f"paper_structure: {exc}", file=sys.stderr)
        return exc.code
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
