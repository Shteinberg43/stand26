from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from src.demo.bases.models.node import IASTNode
from src.demo.models.tokenizer_tokens import Token
from enum import Enum
from typing import TypeVar, Any

TASTNode = TypeVar("TASTNode", bound="ASTNode")


@dataclass
class ASTNode(IASTNode):
    """Узел абстрактного синтаксического дерева."""

    class IAttrEval(ABC):
        """Интерфейс для класса, считающего значение атрибута в узле АСД."""

        from src.demo.visitor.evalregistry import EvalContext

        @abstractmethod
        def __call__(
            self, value: str, children: list[TASTNode], context: EvalContext
        ) -> Any:
            pass

    class IdentityEval(IAttrEval):
        """Базовая реализация тождественного вычислителя атрибутов."""

        from src.demo.visitor.evalregistry import EvalContext

        def __call__(
            self, value: str, children: list[TASTNode], context: EvalContext
        ) -> Any:
            return value

    class Type(str, Enum):
        TOKEN = "TOKEN"
        NONTERMINAL = "NONTERMINAL"

    type: Type
    """Тип узла: терминал-нетерминал-ключ"""
    subtype: "str" = ""
    """Подтип нетерминала или терминала - используемые в вашем коде"""
    children: list[TASTNode] = field(default_factory=list)
    """Дочерние узлы"""
    nonterminalType: str = ""
    """Неизвестное на данный момент поле. Прописано явно для улучшения
    читаемости"""
    commands: list = field(default_factory=list)
    """Неизвестное на данный момент поле. Прописано явно для улучшения
    читаемости"""
    token: Token = None
    """Токен, сохраняемый в элементе дерева. Появилось в результате
    переписывания алгоритма псевдокода предыдущего года."""
    value: str = ""
    """Значение (для терминалов)"""
    attribute: Any = None
    """Вычисляемый атрибут. Для терминалов - после послесканера, для
    нетерминалов - при обсчете дерева."""
    position: tuple = None
    """(line, column)"""
    evaluation: IAttrEval = IdentityEval()
    """собственное значение, список значений дочерних узлов,
    # возвращаемый тип (любой)"""
    SHIFT = 4

    def __blank(self, offset: int):
        return " " * self.SHIFT * offset

    def evaluated(self, context: "EvalContext") -> Any:
        # self.attribute = self.evaluation(self.value, self.children)
        from src.demo.visitor.evalregistry import EvalRegistry

        evaluation = EvalRegistry.evaluation(self.type, self.subtype)
        self.attribute = evaluation(self.value, self.children, context)
        return self.attribute

    def attach_evaluators(self, evals: dict[tuple[Type, str], IAttrEval]) -> TASTNode:
        key = (self.type, self.subtype)
        # print(f'{key = }, {key in evals}, {evals = }')
        if key in evals:
            # print(f'Found {key}')
            self.evaluation = evals[key]
        for child in self.children:
            child.attach_evaluators(evals)
        return self

    def _clear_value(self):
        if self.value[0] == "'" and self.value[-1] == "'":
            return self.value[1:-1]
        else:
            return self.value

    def with_children(self, children: list["ASTNode"]) -> "ASTNode":
        """
        Создает копию узла с новыми детьми (для конструктора).
        """
        import copy

        new_node = copy.copy(self)
        new_node.children = children
        return new_node

    def json_no_newline(self, offset: int):
        json = (
            self.__blank(offset)
            + "{\n"
            + self.__blank(offset + 1)
            + f"type: '{self.type}',\n"
            + self.__blank(offset + 1)
            + f"subtype: '{self.subtype}',\n"
            + self.__blank(offset + 1)
            + f"value: '{self.value}',\n"
            + self.__blank(offset + 1)
            + f"attribute: '{'' if self.attribute is None else self.attribute}',\n"
            + self.__blank(offset + 1)
            + "children: ["
        )
        if self.children == []:
            json += "]\n" + self.__blank(offset) + "}"
        else:
            json += "\n"
            for child in self.children[:-1]:
                json += child.json_no_newline(offset + 2) + ",\n"
            json += self.children[-1].json_no_newline(offset + 2) + "\n"
            json += self.__blank(offset + 1) + "]\n" + self.__blank(offset) + "}"
        return json
