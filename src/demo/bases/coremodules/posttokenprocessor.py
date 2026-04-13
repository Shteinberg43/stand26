from abc import ABC, abstractmethod
from src.demo.models.tokenizer_tokens import Token
from typing import List


class PostTokenizerBase(ABC):

    def __init__(self, meta_grammar):
        self.meta_grammar = meta_grammar
        pass

    @abstractmethod
    def post_process(self, tokens: List[Token]) -> List[Token]:
        return tokens
