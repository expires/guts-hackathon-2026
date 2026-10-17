"""Safe arithmetic expressions for data-driven event templates.

Templates hold formulas as strings, for example "clamp(0.25 + rent_change / 20, 0.05, 0.8)".
This module parses them with `ast` and walks the tree. It never calls `eval`.

Allowed: numbers, True/False, names, + - * / % **, unary - + not, comparisons, and/or,
`a if cond else b`, and the functions in `FUNCTIONS`. Booleans evaluate to 1.0 or 0.0.
Division by zero gives 0.0 so a template can never crash a life.
"""

from __future__ import annotations

import ast
import math
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field


class ExprError(ValueError):
    """A template formula is invalid or uses an unknown name."""


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def _round(x: float, ndigits: float = 0) -> float:
    return float(round(x, int(ndigits)))


FUNCTIONS: dict[str, Callable[..., float]] = {
    "min": lambda *a: float(min(a)),
    "max": lambda *a: float(max(a)),
    "abs": lambda x: float(abs(x)),
    "round": _round,
    "floor": lambda x: float(math.floor(x)),
    "ceil": lambda x: float(math.ceil(x)),
    "clamp": _clamp,
    "exp": lambda x: math.exp(min(x, 50.0)),
}


def _pow(a: float, b: float) -> float:
    try:
        v = a**b
    except (OverflowError, ZeroDivisionError):
        return 0.0
    return float(v) if isinstance(v, int | float) else 0.0


_BIN: dict[type[ast.operator], Callable[[float, float], float]] = {
    ast.Add: lambda a, b: a + b,
    ast.Sub: lambda a, b: a - b,
    ast.Mult: lambda a, b: a * b,
    ast.Div: lambda a, b: a / b if b != 0 else 0.0,
    ast.Mod: lambda a, b: a % b if b != 0 else 0.0,
    ast.Pow: _pow,
}

_CMP: dict[type[ast.cmpop], Callable[[float, float], bool]] = {
    ast.Lt: lambda a, b: a < b,
    ast.LtE: lambda a, b: a <= b,
    ast.Gt: lambda a, b: a > b,
    ast.GtE: lambda a, b: a >= b,
    ast.Eq: lambda a, b: a == b,
    ast.NotEq: lambda a, b: a != b,
}


@dataclass(frozen=True)
class Expr:
    """A parsed formula. `names` lists every variable the formula reads."""

    source: str
    tree: ast.expr = field(repr=False, compare=False)
    names: frozenset[str] = field(compare=False)

    @staticmethod
    def parse(source: str | float | int | bool) -> Expr:
        text = str(source) if not isinstance(source, bool) else ("1" if source else "0")
        try:
            module = ast.parse(text.strip(), mode="eval")
        except SyntaxError as exc:
            raise ExprError(f"bad formula {text!r}: {exc.msg}") from exc
        names: set[str] = set()
        _check(module.body, text, names)
        return Expr(source=text, tree=module.body, names=frozenset(names))

    def eval(self, env: Mapping[str, float]) -> float:
        return _eval(self.tree, env, self.source)


def _check(node: ast.expr, src: str, names: set[str]) -> None:
    if isinstance(node, ast.Constant):
        if not isinstance(node.value, int | float | bool):
            raise ExprError(f"only numbers allowed in {src!r}")
    elif isinstance(node, ast.Name):
        if node.id not in ("True", "False"):
            names.add(node.id)
    elif isinstance(node, ast.BinOp):
        if type(node.op) not in _BIN:
            raise ExprError(f"operator not allowed in {src!r}")
        _check(node.left, src, names)
        _check(node.right, src, names)
    elif isinstance(node, ast.UnaryOp):
        if not isinstance(node.op, ast.USub | ast.UAdd | ast.Not):
            raise ExprError(f"unary operator not allowed in {src!r}")
        _check(node.operand, src, names)
    elif isinstance(node, ast.BoolOp):
        for v in node.values:
            _check(v, src, names)
    elif isinstance(node, ast.Compare):
        if any(type(op) not in _CMP for op in node.ops):
            raise ExprError(f"comparison not allowed in {src!r}")
        _check(node.left, src, names)
        for c in node.comparators:
            _check(c, src, names)
    elif isinstance(node, ast.IfExp):
        _check(node.test, src, names)
        _check(node.body, src, names)
        _check(node.orelse, src, names)
    elif isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name) or node.func.id not in FUNCTIONS or node.keywords:
            raise ExprError(f"function not allowed in {src!r}")
        for a in node.args:
            _check(a, src, names)
    else:
        raise ExprError(f"syntax not allowed in {src!r}: {type(node).__name__}")


def _eval(node: ast.expr, env: Mapping[str, float], src: str) -> float:
    if isinstance(node, ast.Constant) and isinstance(node.value, int | float):
        return float(node.value)
    if isinstance(node, ast.Name):
        if node.id == "True":
            return 1.0
        if node.id == "False":
            return 0.0
        try:
            return float(env[node.id])
        except KeyError as exc:
            raise ExprError(f"unknown name {node.id!r} in {src!r}") from exc
    if isinstance(node, ast.BinOp):
        return _BIN[type(node.op)](_eval(node.left, env, src), _eval(node.right, env, src))
    if isinstance(node, ast.UnaryOp):
        v = _eval(node.operand, env, src)
        if isinstance(node.op, ast.USub):
            return -v
        if isinstance(node.op, ast.Not):
            return 0.0 if v else 1.0
        return v
    if isinstance(node, ast.BoolOp):
        if isinstance(node.op, ast.And):
            return 1.0 if all(_eval(v, env, src) for v in node.values) else 0.0
        return 1.0 if any(_eval(v, env, src) for v in node.values) else 0.0
    if isinstance(node, ast.Compare):
        left = _eval(node.left, env, src)
        for op, comp in zip(node.ops, node.comparators, strict=True):
            right = _eval(comp, env, src)
            if not _CMP[type(op)](left, right):
                return 0.0
            left = right
        return 1.0
    if isinstance(node, ast.IfExp):
        if _eval(node.test, env, src):
            return _eval(node.body, env, src)
        return _eval(node.orelse, env, src)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        return float(FUNCTIONS[node.func.id](*(_eval(a, env, src) for a in node.args)))
    raise ExprError(f"cannot evaluate {src!r}")
