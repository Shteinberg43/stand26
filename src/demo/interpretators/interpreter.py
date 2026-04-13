from src.demo.bases.coremodules.interpretator import InterpreterBase
from src.demo.cstbuilders.rbnf import CSTRBNFBuilder
from src.demo.models.grammar import GrammarObject
from src.demo.tokenizers.rbnf import RBNFTokenizer
from src.demo.visitor.evalregistry import EvalContext
from typing import Optional


class InternalInterpreter(InterpreterBase):
    def __init__(
        self,
        meta_grammar: "GrammarObject",
        tokenizer: Optional["TokenizerBase"] = None,
        post_tokenizer: Optional["PostTokenizerBase"] = None,
        cst_builder: Optional["CSTBuilder"] = None,
    ):
        # 1. Определяем дефолтные реализации, если пользователь не передал свои

        # Пример: RBNFTokenizer(meta_grammar)
        actual_tokenizer = tokenizer if tokenizer else RBNFTokenizer(meta_grammar)

        # Пример: CSTRBNFBuilder(meta_grammar)
        actual_builder = cst_builder if cst_builder else CSTRBNFBuilder(meta_grammar)

        # Пост-процессор может быть None по умолчанию
        actual_post = post_tokenizer

        # 2. Передаем всё в базовый класс
        super().__init__(
            meta_grammar,
            tokenizer=actual_tokenizer,
            post_tokenizer=actual_post,
            cst_builder=actual_builder,
        )

    def run(
        self, elements: str, initial_context: Optional["EvalContext"] = None
    ) -> GrammarObject:
        from src.demo.semantic_handlers.ebnfgrammar import register_evaluators
        from src.demo.visitor.evalregistry import EvalContext

        register_evaluators()
        head_node = super().run_syntax_analyzer(elements)
        context = initial_context if initial_context else EvalContext()
        return head_node.evaluated(context)
