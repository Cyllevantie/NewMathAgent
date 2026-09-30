"""Small reusable checks for temporal semantics and strength of numerical claims."""
import math


def _number(value):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError("Expected finite number")
    return value


def trajectory(base, changes, *, reference):
    """Changes are fractional deviations, e.g. .02, not multipliers.

    fixed_base: each period relative to base; previous_period: compounded changes.
    Choosing the reference must be justified against the original problem statement.
    """
    base = _number(base)
    changes = list(changes)
    if not changes or reference not in {"fixed_base", "previous_period"}:
        raise ValueError("Declare a reference and nonempty changes")
    result, previous = [], base
    for change in changes:
        change = _number(change)
        if change < -1:
            raise ValueError("Fractional reduction cannot exceed 100 percent")
        previous = (base if reference == "fixed_base" else previous) * (1 + change)
        result.append(_number(previous))
    return result


def optimality_issues(*, termination, gap, claim, scope, certificate_scope=None,
                      proof_verified=False, tolerance=1e-4):
    """A solver certificate is bounded by its declared model and tolerance."""
    if claim not in {"feasible", "numerical_optimum", "exact_optimum"}:
        raise ValueError("Unknown claim")
    tolerance = _number(tolerance)
    if not 0 <= tolerance <= .01 or not isinstance(scope, str) or not scope:
        raise ValueError("Invalid tolerance/scope")
    if gap is not None and _number(gap) < 0:
        raise ValueError("Gap must be nonnegative")
    if claim == "feasible":
        return []  # Feasibility itself still needs independent constraint checks.
    errors = []
    if certificate_scope != scope:
        errors.append("最优性证据与声称的模型/样本/策略范围不同")
    if claim == "exact_optimum":
        if proof_verified is not True:
            errors.append("精确最优需要独立核验的解析证据，数值gap不足以证明")
    elif termination != "optimal" or gap is None or gap > tolerance:
        errors.append("未在声明容差内证得数值最优，保留为可行候选")
    return errors


def pareto_dominates(a, b, directions, *, atol=0.0):
    """Only compare metrics evaluated on the same data and in the same units."""
    if not a or len(a) != len(b) or len(a) != len(directions):
        raise ValueError("Metric dimension mismatch")
    atol = _number(atol)
    if atol < 0 or any(d not in {"max", "min"} for d in directions):
        raise ValueError("Invalid tolerance/direction")
    improvements = [(_number(x)-_number(y)) * (1 if d == "max" else -1)
                    for x, y, d in zip(a, b, directions)]
    return all(x >= -atol for x in improvements) and any(x > atol for x in improvements)
