"""Safe calculator: evaluates arithmetic through the AST, never through eval()."""
from __future__ import annotations

import ast
import math
import operator as op
import statistics

from app.tools.base import ToolError

_BIN = {
    ast.Add: op.add, ast.Sub: op.sub, ast.Mult: op.mul,
    ast.Div: op.truediv, ast.Pow: op.pow, ast.Mod: op.mod, ast.FloorDiv: op.floordiv,
}
_UN = {ast.USub: op.neg, ast.UAdd: op.pos}
_CONSTS = {"pi": math.pi, "e": math.e}


def _pct_change(old: float, new: float) -> float:
    return (new - old) / old * 100


_FUNCS = {
    "round": round, "abs": abs, "min": min, "max": max, "sum": sum,
    "mean": statistics.fmean, "sqrt": math.sqrt, "log": math.log, "pct_change": _pct_change,
}
_MAX_BITS = 10_000


def _eval(node: ast.AST):
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
        return node.value
    if isinstance(node, ast.Name) and node.id in _CONSTS:
        return _CONSTS[node.id]
    if isinstance(node, ast.BinOp) and type(node.op) in _BIN:
        left, right = _eval(node.left), _eval(node.right)
        if isinstance(node.op, ast.Pow):
            if isinstance(left, int) and isinstance(right, int) and left.bit_length() * abs(right) > _MAX_BITS:
                raise ToolError("result too large")
            if abs(right) > 1000:
                raise ToolError("exponent too large")
        try:
            return _BIN[type(node.op)](left, right)
        except ZeroDivisionError:
            raise ToolError("division by zero") from None
        except OverflowError:
            raise ToolError("result too large") from None
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UN:
        return _UN[type(node.op)](_eval(node.operand))
    if isinstance(node, (ast.List, ast.Tuple)):
        return [_eval(item) for item in node.elts]
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in _FUNCS and not node.keywords:
        try:
            return _FUNCS[node.func.id](*[_eval(arg) for arg in node.args])
        except (TypeError, ValueError, ZeroDivisionError, OverflowError, statistics.StatisticsError) as exc:
            raise ToolError(f"{node.func.id}() failed: {exc}") from None
    raise ToolError("unsupported expression (only arithmetic and the listed functions are allowed)")


def evaluate(expression: str):
    if len(expression) > 500:
        raise ToolError("expression too long")
    try:
        tree = ast.parse(expression.strip(), mode="eval")
    except SyntaxError as exc:
        raise ToolError(f"invalid expression: {exc.msg}") from None
    return _eval(tree.body)


def format_number(value) -> str:
    if isinstance(value, list):
        return "[" + ", ".join(format_number(v) for v in value) + "]"
    return str(value) if isinstance(value, int) else f"{value:.10g}"


def calculator_tool(args: dict) -> str:
    expression = str(args.get("expression", "")).strip()
    if not expression:
        raise ToolError("missing 'expression'")
    return format_number(evaluate(expression))
