from abc import ABC, abstractmethod
from typing import Any


class IASTNode(ABC):
    """Элемент абстрактного синтаксического дерева."""

    @abstractmethod
    def evaluated(self, context) -> Any:
        pass
