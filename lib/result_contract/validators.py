"""Deterministic result checkers. Never import a solver or optimize a solution."""
import math


def numbers(values):
    if not isinstance(values, list) or not values:
        raise ValueError("Expected nonempty numeric list")
    if any(isinstance(v, bool) or not isinstance(v, (float, int)) or not math.isfinite(v) for v in values):
        raise ValueError("Nonfinite/nonnumeric value")
    return values


def linear(problem, solution):
    """Recompute c*x and each linear constraint from a separately prepared contract.

    Schema: c, lower, upper, integer_indices, constraints[{id,a,sense,rhs}],
    optional atol/rtol. Solution: x, objective. Feasibility is not optimality.
    """
    x, c = numbers(solution["x"]), numbers(problem["c"])
    n = len(x)
    lower, upper = problem["lower"], problem["upper"]
    if not len(c) == len(lower) == len(upper) == n:
        raise ValueError("Dimension mismatch")
    atol, rtol = problem.get("atol", 1e-7), problem.get("rtol", 1e-8)
    numbers([atol, rtol])
    if atol < 0 or rtol < 0 or atol > .01 or rtol > .001:
        raise ValueError("Tolerance outside conservative checker limits; rescale documented units")
    def close(a, b):
        return abs(a-b) <= atol + rtol*max(abs(a), abs(b))
    rows = []
    def record(key, passed, evidence):
        rows.append({"id": key, "passed": bool(passed), "evidence": evidence})
    for i, value in enumerate(x):
        for kind, bounds in (("lower", lower), ("upper", upper)):
            bound = bounds[i]
            if bound is not None:
                numbers([bound])
                ok = value >= bound if kind == "lower" else value <= bound
                record(f"{kind}.{i}", ok or close(value, bound), f"x={value}; {kind}={bound}")
        if lower[i] is not None and upper[i] is not None and lower[i] > upper[i]:
            raise ValueError("Inconsistent bounds")
    for i in problem.get("integer_indices", []):
        if type(i) is not int or not 0 <= i < n:
            raise ValueError("Invalid integer index")
        record(f"integer.{i}", abs(x[i]-round(x[i])) <= atol, f"x={x[i]}")
    ids = set()
    for con in problem["constraints"]:
        key = con["id"]
        if not isinstance(key, str) or not key or key in ids:
            raise ValueError("Constraint IDs must be unique")
        ids.add(key)
        a = numbers(con["a"])
        rhs = numbers([con["rhs"]])[0]
        if len(a) != n or con["sense"] not in {"le", "ge", "eq"}:
            raise ValueError("Invalid constraint")
        lhs = math.fsum(ai*xi for ai, xi in zip(a, x))
        numbers([lhs])
        ok = {"le": lhs <= rhs, "ge": lhs >= rhs, "eq": False}[con["sense"]] or close(lhs, rhs)
        record("constraint."+key, ok, f"lhs={lhs}; sense={con['sense']}; rhs={rhs}")
    objective = math.fsum(ci*xi for ci, xi in zip(c, x))
    reported = numbers([solution["objective"]])[0]
    numbers([objective])
    record("objective", close(objective, reported), f"recomputed={objective}; reported={reported}")
    return rows
