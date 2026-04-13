from abc import ABC, abstractmethod


class CSTBuilder(ABC):
    @abstractmethod
    def build(self, tokens):
        pass
