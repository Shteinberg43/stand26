"""Генератор отсортированных массивов."""

from generators._base import DataGenerator
from generators._core import _make_rng
from generators._registry import register_generator
from generators.config import DEFAULT_RANGE_HIGH, DEFAULT_RANGE_LOW


@register_generator("sorted")
class SortedGenerator(DataGenerator[int]):
    """Генерирует отсортированную по возрастанию последовательность.

    Используется для оценки поведения алгоритма на лучшем случае.

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
        """Заполняет приемник отсортированными числами.

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
        sorted_vals = sorted(rng.randint(self._low, self._high) for _ in range(size))
        for val in sorted_vals:
            inserter.insert(val)
