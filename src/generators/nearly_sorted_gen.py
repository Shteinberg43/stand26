"""Генератор почти отсортированных массивов."""

from src.generators._base import DataGenerator
from src.generators._core import _make_rng
from src.generators._registry import register_generator
from src.generators.config import (
    DEFAULT_NEARLY_SORTED_SWAP_FRACTION,
    DEFAULT_RANGE_HIGH,
    DEFAULT_RANGE_LOW,
)


@register_generator("nearly_sorted")
class NearlySortedGenerator(DataGenerator[int]):
    """Генерирует почти отсортированный массив.

    Сначала создаётся отсортированный массив, затем случайно
    выбранные пары элементов меняются местами. Количество свопов
    определяется как ``max(1, int(size * swap_fraction))``.

    Args:
        low: Нижняя граница значений (включительно).
        high: Верхняя граница значений (включительно).
        swap_fraction: Доля элементов, участвующих в свопах.
    """

    def __init__(
        self,
        low: int = DEFAULT_RANGE_LOW,
        high: int = DEFAULT_RANGE_HIGH,
        swap_fraction: float = DEFAULT_NEARLY_SORTED_SWAP_FRACTION,
    ) -> None:
        self._low = low
        self._high = high
        self._swap_fraction = swap_fraction

    def fill(self, inserter: 'OutputIterator[int]', size: int, seed: int) -> None:
        """Заполняет приемник почти отсортированными числами.

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
        arr = sorted(rng.randint(self._low, self._high) for _ in range(size))
        num_swaps = max(1, int(size * self._swap_fraction))
        for _ in range(num_swaps):
            i = rng.randint(0, size - 1)
            j = rng.randint(0, size - 1)
            arr[i], arr[j] = arr[j], arr[i]
        for val in arr:
            inserter.insert(val)
