from abc import ABC
from src.demo.bases.coremodules.cstbuilder import CSTBuilder
from src.demo.bases.coremodules.posttokenprocessor import PostTokenizerBase
from src.demo.bases.coremodules.tokenizer import TokenizerBase
from src.demo.models.nodes import ASTNode
from src.demo.models.tokenizer_tokens import Token
from src.demo.visitor.evalregistry import EvalContext
from typing import Optional, List, Any


class InterpreterBase(ABC):
    """
    Базовый класс-оркестратор.
    Берет на себя всю рутину по хранению компонентов и запуску пайплайна.
    """

    def __init__(
        self,
        meta_grammar,
        tokenizer: Optional["TokenizerBase"] = None,
        post_tokenizer: Optional["PostTokenizerBase"] = None,
        cst_builder: Optional["CSTBuilder"] = None,
    ):
        self.meta_grammar = meta_grammar

        # Компоненты (стратегии)
        self._tokenizer = tokenizer
        self._post_tokenizer = post_tokenizer
        self._cst_builder = cst_builder

    # region Properties для доступа с проверкой

    @property
    def tokenizer(self) -> "TokenizerBase":
        if not self._tokenizer:
            raise ValueError("Tokenizer is not set for this interpreter.")
        return self._tokenizer

    @tokenizer.setter
    def tokenizer(self, value: "TokenizerBase"):
        self._tokenizer = value

    @property
    def post_tokenizer(self) -> Optional["PostTokenizerBase"]:
        return self._post_tokenizer

    @post_tokenizer.setter
    def post_tokenizer(self, value: "PostTokenizerBase"):
        self._post_tokenizer = value

    @property
    def cst_builder(self) -> "CSTBuilder":
        if not self._cst_builder:
            raise ValueError("CSTBuilder is not set for this interpreter.")
        return self._cst_builder

    @cst_builder.setter
    def cst_builder(self, value: "CSTBuilder"):
        self._cst_builder = value

    # endregion

    # region Pipeline Steps

    def tokenize(self, elements: str) -> List["Token"]:
        return self.tokenizer.tokenize(elements)

    def post_process_tokens(self, tokens: List["Token"]) -> List["Token"]:
        """
        Если пост-токенайзер установлен — используем его.
        Если нет — просто возвращаем токены как есть.
        """
        if self._post_tokenizer:
            return self._post_tokenizer.post_process(tokens)
        return tokens

    def cst_build(self, tokens: List["Token"]) -> "ASTNode":
        return self.cst_builder.build(tokens)

    # endregion

    # region Way to Run

    def run_syntax_analyzer(self, elements: str) -> ASTNode:
        raw_tokens = self.tokenize(elements)
        processed_tokens = self.post_process_tokens(raw_tokens)
        return self.cst_build(processed_tokens)

    def run(
        self, elements: str, initial_context: Optional["EvalContext"] = None
    ) -> Any:
        root_node = self.run_syntax_analyzer(elements)
        context = initial_context if initial_context else EvalContext()
        return root_node.evaluated(context)

    # endregion
