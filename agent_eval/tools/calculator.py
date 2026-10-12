"""Safe arithmetic evaluator built on the ``ast`` module (no ``eval``)."""

from __future__ import annotations

import ast
import operator
from collections.abc import Callable
from typing import Any

from agent_eval.tools.base import Tool, ToolError, obj_schema
from agent_eval.tools.sandbox import Sandbox

_BINARY: dict[type[ast.operator], Callable[[float, float], float]] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_UNARY: dict[type[ast.unaryop], Callable[[float], float]] = {
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}
_FUNCS: dict[str, Callable[..., float]] = {"abs": abs, "round": round, "min": min, "max": max}


def _eval(node: ast.AST) -> float:
    if isinstance(node, ast.Constant) and isinstance(node.value, int | float):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _BINARY:
        if isinstance(node.op, ast.Pow) and abs(_eval(node.right)) > 64:
            raise ToolError("exponent too large (limit 64)")
        return _BINARY[type(node.op)](_eval(node.left), _eval(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY:
        return _UNARY[type(node.op)](_eval(node.operand))
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in _FUNCS:
        if node.keywords:
            raise ToolError("keyword arguments are not supported")
        return _FUNCS[node.func.id](*(_eval(a) for a in node.args))
    raise ToolError(f"unsupported syntax: {type(node).__name__}")


def evaluate(expression: str) -> float:
    try:
        tree = ast.parse(expression.strip(), mode="eval")
    except SyntaxError as exc:
        raise ToolError(f"invalid expression: {exc.msg}") from exc
    except (ValueError, RecursionError, MemoryError) as exc:
        raise ToolError(f"invalid expression: {exc}") from exc
    try:
        return _eval(tree.body)
    except ZeroDivisionError as exc:
        raise ToolError("division by zero") from exc
    except OverflowError as exc:
        raise ToolError("result too large") from exc
    except RecursionError as exc:
        raise ToolError("expression too deeply nested") from exc
    except (TypeError, ValueError) as exc:  # e.g. min() with no arguments, abs(1, 2)
        raise ToolError(f"invalid call: {exc}") from exc


def _format(value: float) -> str:
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return f"{value:.10g}" if isinstance(value, float) else str(value)


def _calc(_: Sandbox, args: dict[str, Any]) -> str:
    return _format(evaluate(args["expression"]))


CALCULATOR_TOOLS: list[Tool] = [
    Tool(
        "calculator",
        "Evaluate an arithmetic expression (+ - * / // % ** and abs/round/min/max).",
        obj_schema({"expression": {"type": "string"}}, ["expression"]),
        _calc,
    )
]
