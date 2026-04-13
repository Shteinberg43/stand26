"""Генератор массивов с дубликатами."""

from src.generators._base import DataGenerator
from src.generators._core import _make_rng
from src.generators._registry import register_generator


@register_generator("duplicates")
class DuplicatesGenerator(DataGenerator[int]):
    """Генерирует последовательность с гарантированными дубликатами.

    Значения выбираются из узкого диапазона ``[0, num_unique - 1]``,
    что гарантирует появление повторяющихся элементов при ``size > num_unique``.

    Args:
        num_unique: Количество уникальных значений в массиве.
    """

    def __init__(self, num_unique: int = 10) -> None:
        self._num_unique = num_unique

    def fill(self, inserter: 'OutputIterator[int]', size: int, seed: int) -> None:
        """Заполняет приемник данными с дубликатами.

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
            inserter.insert(rng.randint(0, self._num_unique - 1))
