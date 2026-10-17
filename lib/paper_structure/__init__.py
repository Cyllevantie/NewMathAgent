"""Role-based paper structure assembly (P1).

Public API:
  - assemble(root, profile_path=None, template=None, out_dir=None)
  - check(root, out_dir=None)
  - sync_title(root, out_dir=None)
  - load_roles / load_profile / resolve_problem_count
"""
from .core import (  # noqa: F401
    PAGE_KINDS,
    StructureError,
    assemble,
    build_plan,
    canonical_json,
    check,
    cn_num,
    load_profile,
    load_roles,
    render_tex,
    resolve_problem_count,
    resolve_template,
    sha256_file,
    sha256_text,
    sync_title,
)

__all__ = [
    "PAGE_KINDS",
    "StructureError",
    "assemble",
    "build_plan",
    "canonical_json",
    "check",
    "cn_num",
    "load_profile",
    "load_roles",
    "render_tex",
    "resolve_problem_count",
    "resolve_template",
    "sha256_file",
    "sha256_text",
    "sync_title",
]
