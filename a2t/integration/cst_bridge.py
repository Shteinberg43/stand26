from __future__ import annotations
from a2t.common.errors import PseudoCodeRuntimeError


class CSTBridge:
    """
    Минимальный мост от сгенерированного CST к семантическому исполнителю.
    Для stage 6 достаточно фиксированного контракта по видам узлов.
    """

    def __init__(self, semantic_executor):
        self.semantic = semantic_executor

    def execute_nodes(self, nodes):
        for node in nodes:
            kind = node.get("kind")
            if kind == "assign":
                value = node["value"]
                self.semantic.eval_assign(node["name"], value)
            elif kind == "compare":
                self.semantic.eval_compare(node["left"], node["right"])
            elif kind == "array_read":
                self.semantic.eval_array_read(node["array"], node["index"])
            elif kind == "array_write":
                self.semantic.eval_array_write(node["array"], node["index"], node["value"])
            elif kind == "branch":
                self.semantic.eval_branch(node["condition"])
            else:
                raise PseudoCodeRuntimeError("Unsupported CST node kind: %s" % kind)
