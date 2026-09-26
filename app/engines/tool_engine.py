"""
Tool Engine: dusuk riskli araclarin kontrollu calistirilmasi.

NOT (onemli): Bu MVP surumu gercek bir isletim-sistemi-seviyesi sandbox
(ör. ayri process/container, kaynak/sure limiti) SAGLAMAZ - sadece
whitelist edilmis araclarla sinirli, hatalari yakalayan bir katmandir.
Production'a gecmeden once araclar gercekten izole bir surecte/
container'da calistirilmali (Bolum 0.1: "Sandbox icinde, yetkilendirilmis").
"""
import ast
import operator
from abc import ABC, abstractmethod
from typing import Any, Dict


class ToolError(Exception):
    pass


class BaseTool(ABC):
    name: str = "base"
    description: str = ""

    @abstractmethod
    def execute(self, **kwargs) -> Any:
        raise NotImplementedError


_ALLOWED_OPS = {
    ast.Add: operator.add, ast.Sub: operator.sub,
    ast.Mult: operator.mul, ast.Div: operator.truediv,
    ast.Pow: operator.pow, ast.USub: operator.neg,
    ast.Mod: operator.mod,
}


def _safe_eval(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _ALLOWED_OPS:
        return _ALLOWED_OPS[type(node.op)](_safe_eval(node.left), _safe_eval(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _ALLOWED_OPS:
        return _ALLOWED_OPS[type(node.op)](_safe_eval(node.operand))
    raise ToolError("Desteklenmeyen ifade")


class CalculatorTool(BaseTool):
    name = "calculator"
    description = "Temel matematik ifadelerini guvenli sekilde hesaplar (ör. '(3+4)*2')."

    def execute(self, expression: str) -> float:
        try:
            tree = ast.parse(expression, mode="eval").body
            return _safe_eval(tree)
        except Exception as e:
            raise ToolError(f"Hesaplama hatasi: {e}")


class ToolRegistry:
    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}

    def register(self, tool: BaseTool):
        self._tools[tool.name] = tool

    def get(self, name: str) -> BaseTool:
        if name not in self._tools:
            raise ToolError(f"Bilinmeyen arac: {name}")
        return self._tools[name]

    def list_tools(self):
        return [{"name": t.name, "description": t.description} for t in self._tools.values()]


registry = ToolRegistry()
registry.register(CalculatorTool())
