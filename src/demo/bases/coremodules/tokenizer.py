from abc import ABC, abstractmethod


class TokenizerBase(ABC):

    def __init__(self, meta_grammar):
        self.warnings = []
        self.patterns = []
        self.terminal_list = [term.name for term in meta_grammar.terminals.values()]
        self.key_list = [value for key, value in meta_grammar.keys]

    @abstractmethod
    def tokenize(self, elements):
        pass
