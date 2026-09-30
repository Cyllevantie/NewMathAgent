import json
import re
import subprocess
import sys
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from lib.visualization.evidence import path_in, sha, write_json
from .validators import linear

ID = re.compile(r"[a-z][a-z0-9_.-]*\Z")


def read(root, path):
    # 与 content_quality._read_text 同理：Windows 中文环境下 agent 自写的 json 常是 GBK，
    # 严格 utf-8 解码会抛 UnicodeDecodeError → 被吞成"结果证据无效" → audit FAIL → 退回 code
    # 重跑小时级，而症状里看不出是编码问题。
    raw = path_in(root, path).read_bytes()
    for encoding in ("utf-8-sig", "gbk", "cp936"):
        try:
            return json.loads(raw.decode(encoding))
        except UnicodeDecodeError:
            continue
    return json.loads(raw.decode("utf-8", errors="replace"))


def pointer(data, key):
    if key == "":
        return data
    if not key.startswith("/"):
        raise ValueError("Use a JSON pointer, e.g. /objective")
    for part in key[1:].split("/"):
        part = part.replace("~1", "/").replace("~0", "~")
        if isinstance(data, list):
            if not re.fullmatch(r"0|[1-9][0-9]*", part):
                raise ValueError("Invalid JSON pointer array index")
            data = data[int(part)]
        else:
            data = data[part]
    return data


def snapshot(root, paths):
    root = Path(root).resolve()
    paths = set(paths)
    paths.update(p.relative_to(root).as_posix() for p in (root / "lib" / "result_contract").glob("*.py"))
    return {name: sha(path_in(root, name)) for name in sorted(paths)}


def metrics(root, spec):
    if spec.get("schema_version") != 1 or not spec.get("problem_id") or not spec.get("run_id"):
        raise ValueError("Result spec needs schema_version, problem_id and run_id")
    if not spec.get("inputs") or not spec.get("scripts") or not spec.get("metrics"):
        raise ValueError("Result spec requires inputs, scripts, metrics")
    values = {}
    for item in spec["metrics"]:
        key = item["id"]
        if not ID.fullmatch(key) or key in values:
            raise ValueError("Invalid/duplicate metric id")
        if any(not isinstance(item.get(k), str) or not item[k].strip() for k in ("label", "unit", "scenario")):
            raise ValueError("Metric needs label, unit, scenario")
        raw = pointer(read(root, item["source"]), item["pointer"])
        if isinstance(raw, bool) or not isinstance(raw, (str, int, float)):
            raise ValueError("Metric source must be a finite scalar")
        value = Decimal(str(raw))
        precision = item["precision"]
        if not value.is_finite() or type(precision) is not int or not 0 <= precision <= 12:
            raise ValueError("Nonfinite metric or invalid precision")
        displayed = value.quantize(Decimal(1).scaleb(-precision), rounding=ROUND_HALF_UP)
        values[key] = dict(item, value=str(value), display=format(displayed, "f"))
    return values


def build(root, spec_path="results/metric-spec.json"):
    spec = read(root, spec_path)
    values = metrics(root, spec)
    paths = spec["inputs"] + spec["scripts"] + [spec_path] + [v["source"] for v in values.values()]
    registry = dict(schema_version=1, problem_id=spec["problem_id"], run_id=spec["run_id"], spec=spec_path,
                    metrics=values, snapshot=snapshot(root, paths))
    write_json(path_in(root, "results/registry.json"), registry)
    return registry


def render_text(registry):
    # Values alone are generated; semantic unit/scenario definitions stay in the registry.
    lines = [r"% Generated from results/registry.json; edit the source results, then regenerate.",
             r"\newcommand{\ResultValue}[1]{\ifcsname resultvalue@#1\endcsname\csname resultvalue@#1\endcsname\else\PackageError{results}{Unknown metric #1}{Rebuild the result registry}\fi}"]
    for key, item in sorted(registry["metrics"].items()):
        lines.append(r"\expandafter\def\csname resultvalue@"+key+r"\endcsname{"+item["display"]+"}")
    tex = "\n".join(lines)+"\n"
    # 机器可读副本，值与 registry 的 display 一致。
    data = json.dumps({k: v["display"] for k,v in registry["metrics"].items()}, ensure_ascii=False, indent=2)+"\n"
    return {"paper/result-values.tex": tex, "paper/result-values.json": data}


def export(root):
    errors = audit(root, validation=False)
    if errors:
        raise ValueError("; ".join(errors))
    for name, text in render_text(read(root, "results/registry.json")).items():
        path = path_in(root, name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")


def validate(root, spec_path="results/validation-spec.json"):
    root = Path(root).resolve()
    spec = read(root, spec_path)
    if spec.get("schema_version") != 1 or not spec.get("inputs") or not spec.get("checks_required"):
        raise ValueError("Validator spec requires inputs and named required checks")
    paths = [spec_path] + spec["inputs"]
    if spec["kind"] == "linear":
        paths += [spec["problem"], spec["solution"]]
    elif spec["kind"] == "custom":
        paths += [spec["script"]]
    else:
        raise ValueError("Unknown validator kind")
    before = snapshot(root, paths)
    if spec["kind"] == "linear":
        rows = linear(read(root, spec["problem"]), read(root, spec["solution"]))
    else:
        script = path_in(root, spec["script"])
        if script.suffix != ".py":
            raise ValueError("Custom validator must be a Python script")
        timeout = spec.get("timeout_seconds", 120)
        if type(timeout) is not int or not 1 <= timeout <= 300:
            raise ValueError("Invalid validator timeout")
        completed = subprocess.run([sys.executable, str(script)], cwd=root, capture_output=True,
                                   text=True, encoding="utf-8", timeout=timeout)
        if completed.returncode:
            raise ValueError("Validator process failed: "+completed.stderr[-1500:])
        rows = json.loads(completed.stdout)["checks"]
    if before != snapshot(root, paths):
        raise ValueError("Validator mutated its declared inputs")
    check_rows(rows, spec["checks_required"])
    receipt = dict(schema_version=1, spec=spec_path, checks=rows, snapshot=before,
                   status="PASS" if all(r["passed"] for r in rows) else "FAIL")
    write_json(root / "results/validation.json", receipt)
    return receipt


def check_rows(rows, required):
    if not isinstance(rows, list) or not rows or not isinstance(required, list) or not required:
        raise ValueError("Empty validation coverage")
    seen = set()
    for row in rows:
        if not isinstance(row["id"], str) or not row["id"] or row["id"] in seen or type(row["passed"]) is not bool:
            raise ValueError("Malformed validation check")
        if not isinstance(row.get("evidence"), str) or not row["evidence"].strip():
            raise ValueError("Missing check evidence")
        seen.add(row["id"])
    if not set(required) <= seen:
        raise ValueError("Required validation checks omitted")


def audit(root, *, rendered=False, validation=True):
    problems = []
    try:
        registry = read(root, "results/registry.json")
        spec = read(root, registry["spec"])
        current = metrics(root, spec)
        paths = spec["inputs"] + spec["scripts"] + [registry["spec"]] + [v["source"] for v in current.values()]
        if (registry["metrics"] != current or registry["snapshot"] != snapshot(root, paths)
                or registry["problem_id"] != spec["problem_id"] or registry["run_id"] != spec["run_id"]):
            problems.append("结构化结果已过期或被修改，重新build")
        if validation:
            receipt = read(root, "results/validation.json")
            vspec = read(root, receipt["spec"])
            check_rows(receipt["checks"], vspec["checks_required"])
            # The validator must cover all result input files and metric source files.
            needed = set(spec["inputs"] + [v["source"] for v in current.values()])
            needed.update([receipt["spec"]] + vspec["inputs"])
            if vspec["kind"] == "linear":
                needed.update([vspec["problem"], vspec["solution"]])
                if receipt["checks"] != linear(read(root, vspec["problem"]), read(root, vspec["solution"])):
                    problems.append("线性约束校验回执与独立重算不一致")
            elif vspec["kind"] == "custom":
                needed.add(vspec["script"])
            else:
                raise ValueError("Unknown validator kind")
            bound = receipt["snapshot"]
            if not needed <= set(bound) or bound != snapshot(root, list(bound)):
                problems.append("独立校验未覆盖全部结果来源，或校验已过期")
            if receipt["status"] != "PASS" or not all(r["passed"] for r in receipt["checks"]):
                problems.append("独立校验未通过")
        if rendered:
            for name, content in render_text(registry).items():
                if path_in(root, name).read_text(encoding="utf-8") != content:
                    problems.append("论文数值引用文件过期: "+name)
    except (OSError, ValueError, KeyError, IndexError, TypeError, AttributeError, ArithmeticError) as exc:
        problems.append("结果证据无效: "+str(exc))
    return problems
