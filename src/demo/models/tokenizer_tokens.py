from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Union


class Token:
    """Объект токена в потоке токенов. Посмотри класс Token.Type для
    уточнения."""

    class IAttrEval(ABC):
        """Интерфейс для класса, считающего значение атрибута в токене."""

        @abstractmethod
        def calc(self, value: str) -> Any:
            pass

    class IdentityEval(IAttrEval):
        def calc(self, value: str) -> Any:
            return value

    class Type(str, Enum):
        TERMINAL = "terminal"
        KEY = "key"

    def __init__(
        self,
        token_type: Union["Token.Type", str],
        value: str = None,
        line: int = None,
        column: int = None,
        evaln: "Token.IAttrEval" = IdentityEval(),
        terminalType: str = None,
        str_value: str = None,
    ):

        self.terminalType: str = terminalType
        self.str: str = str_value

        self.token_type = token_type
        """Тип токена берем из грамматики."""
        self.value = value
        """Лексическое значение."""
        self.line = line
        """Позиция в исходном коде."""
        self.column = column
        """Позиция в исходном коде."""
        self.attribute = None
        """Поле под вычисляемый атрибут."""
        self.eval = evaln
        """Объект, вычисляющий атрибут токена."""

    SHIFT = 4

    def __blank(self, offset: int):
        return " " * self.SHIFT * offset

    def evaluated(self) -> Any:
        self.attribute = self.eval.calc(self.value)
        return self.attribute

    def __repr__(self):
        return f"Token({self.terminalType = }, {self.str = }, {self.token_type = }, '{self.value = }', pos: (l: {self.line}, c: {self.column}), {self.attribute = }"

    def to_text(self):

        str_value = f"'{self.str}'" if self.str is not None else self.str
        terminalType = (
            f"'{self.terminalType}'"
            if self.terminalType is not None
            else self.terminalType
        )
        value = f"{self.value = }"[5:]
        return (
            f"Token(terminalType = {terminalType}, "
            f"str_value = {str_value}, "
            f"token_type = Token.{self.token_type}, "
            f"{value}, "
            f"line = {self.line},"
            f"column = {self.column})"
        )

    def repr(self) -> str:
        res = "Token: "
        res += (
            f"terminal = {self.terminalType}, value = {self.value}"
            if self.token_type == self.Type.TERMINAL
            else f"key = {self.value}"
        )
        res += "; "
        return res + f"pos = (l: {self.line}, c: {self.column})"