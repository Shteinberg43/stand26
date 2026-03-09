"""Библиотека генераторов входных данных для A2→T Lab.

Публичный API предоставляет доступ к генераторам через реестр::

    from generators import get_generator, list_generators

    gen = get_generator("random")
    data = gen.generate(size=100, seed=42)

Доступные генераторы массивов:
    - ``"random"``        — случайный массив
    - ``"sorted"``        — отсортированный по возрастанию
    - ``"reverse"``       — отсортированный по убыванию
    - ``"duplicates"``    — массив с дубликатами
    - ``"nearly_sorted"`` — почти отсортированный массив
"""

from generators._base import DataGenerator
from generators._registry import get_generator, list_generators, register_generator

# Импорт модулей-генераторов для срабатывания декораторов @register_generator.
from generators import (  # noqa: F401
    duplicates_gen,
    nearly_sorted_gen,
    random_gen,
    reverse_gen,
    sorted_gen,
)

__all__ = [
    "DataGenerator",
    "register_generator",
    "get_generator",
    "list_generators",
]
