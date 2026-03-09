"""Абстрактные базовые классы генераторов данных."""

from abc import ABC, abstractmethod
from typing import Generic, TypeVar, Any

from generators.interfaces import OutputIterator, ListInserter

T = TypeVar("T")


class DataGenerator(ABC, Generic[T]):
    """Обобщённый генератор данных для экспериментального стенда.

    Основан на паттерне Итератор Вывода (OutputIterator).
    Генератор заполняет переданный приемник данных (inserter).
    """

    @abstractmethod
    def fill(self, inserter: OutputIterator[T], size: int, seed: int) -> None:
        """Заполняет приемник (inserter) сгенерированными данными.

        Args:
            inserter: Объект-адаптер структуры данных с методом insert().
            size: Количество элементов, которое нужно сгенерировать.
            seed: Зерно ГПСЧ для воспроизводимости.
        """
        ...

    def generate(self, size: int, seed: int) -> list[T]:
        """Вспомогательный метод: генерирует стандартный встроенный список (list).
        
        Создает пустой ListInserter, делегирует генерацию методу `fill` 
        и возвращает результирующий список.

        Args:
            size: Количество элементов в генерируемой структуре.
            seed: Зерно ГПСЧ для воспроизводимости.

        Returns:
            Сгенерированный список элементов типа ``T``.
        """
        inserter = ListInserter[T]()
        self.fill(inserter, size, seed)
        return inserter.target



