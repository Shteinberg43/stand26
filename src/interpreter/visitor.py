# src/interpreter/visitor.py
from __future__ import annotations
from typing import Any

from src.common.events import EventBus
from src.common.types import StepEvent, OpType
from src.interpreter.env import Environment
import src.interpreter.ast_nodes as ast

class Visitor:
    """Обходит AST, вычисляет значения и публикует события выполнения."""

    def __init__(self, bus: EventBus, env: Environment) -> None:
        self.bus = bus
        self.env = env

    def visit(self, node: ast.Node) -> Any:
        method_name = f'visit_{type(node).__name__}'
        visitor_method = getattr(self, method_name, self.generic_visit)
        return visitor_method(node)

    def generic_visit(self, node: ast.Node) -> None:
        raise Exception(f'No visit_{type(node).__name__} method defined')

    def visit_Number(self, node: ast.Number) -> int:
        return node.value

    def visit_Var(self, node: ast.Var) -> Any:
        return self.env.get(node.name)

    def visit_Assign(self, node: ast.Assign) -> Any:
        value = self.visit(node.expr)
        self.bus.publish(StepEvent(OpType.ASSIGN, {"target": node.target}))
        try:
            self.env.assign(node.target, value)
        except RuntimeError:
            self.env.define(node.target, value)
        return value

    def visit_BinaryOp(self, node: ast.BinaryOp) -> Any:
        left = self.visit(node.left)
        right = self.visit(node.right)
        
        # Если это операция сравнения, публикуем событие CMP
        if node.op in ('>', '<', '==', '!=', '>=', '<='):
            self.bus.publish(StepEvent(OpType.CMP, {"op": node.op}))
            if node.op == '>': return left > right
            if node.op == '<': return left < right
            if node.op == '==': return left == right
            if node.op == '!=': return left != right
            if node.op == '>=': return left >= right
            if node.op == '<=': return left <= right

        # Иначе это просто математика (для простоты тут не выделен отдельный OpType)
        if node.op == '+': return left + right
        if node.op == '-': return left - right
        raise ValueError(f"Unknown operator: {node.op}")

    def visit_Block(self, node: ast.Block) -> None:
        for stmt in node.statements:
            self.visit(stmt)

    def visit_While(self, node: ast.While) -> None:
        while True:
            self.bus.publish(StepEvent(OpType.BRANCH, {"type": "while_cond"}))
            condition = self.visit(node.condition)
            if not condition:
                break
            self.visit(node.body)

    def visit_ArrayAlloc(self, node: ast.ArrayAlloc) -> None:
        size = self.visit(node.size)
        self.bus.publish(StepEvent(OpType.ALLOC, {"name": node.name, "size": size}))
        self.env.define(node.name, [0] * size)

    def visit_ArrayRead(self, node: ast.ArrayRead) -> Any:
        index = self.visit(node.index)
        self.bus.publish(StepEvent(OpType.ARRAY_READ, {"array": node.name, "index": index}))
        arr = self.env.get(node.name)
        return arr[index]

    def visit_ArrayWrite(self, node: ast.ArrayWrite) -> Any:
        index = self.visit(node.index)
        value = self.visit(node.expr)
        self.bus.publish(StepEvent(OpType.ARRAY_WRITE, {"array": node.name, "index": index}))
        arr = self.env.get(node.name)
        arr[index] = value
        return value