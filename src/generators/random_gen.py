"""Генератор случайных массивов."""

from src.generators._base import DataGenerator
from src.generators._core import _make_rng
from src.generators._registry import register_generator
from src.generators.config import DEFAULT_RANGE_HIGH, DEFAULT_RANGE_LOW


@register_generator("random")
class RandomGenerator(DataGenerator[int]):
    """Генерирует последовательность случайных целых чисел.

    Используется для оценки поведения алгоритма на среднем случае.

    Args:
        low: Нижняя граница значений (включительно).
        high: Верхняя граница значений (включительно).
    """

    def __init__(
        self,
        low: int = DEFAULT_RANGE_LOW,
        high: int = DEFAULT_RANGE_HIGH,
    ) -> None:
        self._low = low
        self._high = high

    def fill(self, inserter: 'OutputIterator[int]', size: int, seed: int) -> None:
        """Заполняет приемник случайными числами.

        Args:
            inserter: Объект-приемник.
            size: Количество элементов.
            seed: Зерно ГПСЧ.

        Raises:
            ValueError: Если ``size`` меньше или равен нулю.
        """
        if size <= 0:
            raise ValueError(f"size must be positive, got {size}")
        rng = _make_rng(seed)
        for _ in range(size):
            inserter.insert(rng.randint(self._low, self._high))
