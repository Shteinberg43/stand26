"""Тесты реестра генераторов."""

import pytest

from generators import get_generator, list_generators
from generators._base import DataGenerator
from generators._registry import _REGISTRY, register_generator


class TestListGenerators:
    """Тесты для list_generators()."""

    def test_returns_list_of_strings(self) -> None:
        result = list_generators()
        assert isinstance(result, list)
        assert all(isinstance(name, str) for name in result)

    def test_contains_all_builtin_generators(self) -> None:
        expected = {"random", "sorted", "reverse", "duplicates", "nearly_sorted"}
        actual = set(list_generators())
        assert expected.issubset(actual)


class TestGetGenerator:
    """Тесты для get_generator()."""

    def test_returns_data_generator(self) -> None:
        gen = get_generator("random")
        assert isinstance(gen, DataGenerator)

    def test_unknown_name_raises_key_error(self) -> None:
        with pytest.raises(KeyError, match="Unknown generator"):
            get_generator("nonexistent_generator")

    def test_passes_kwargs_to_constructor(self) -> None:
        gen = get_generator("random", low=5, high=15)
        result = gen.generate(size=10, seed=0)
        assert all(5 <= x <= 15 for x in result)


class TestRegisterGenerator:
    """Тесты для декоратора register_generator()."""

    def test_duplicate_name_raises_key_error(self) -> None:
        with pytest.raises(KeyError, match="already registered"):

            @register_generator("random")
            class _DuplicateGen(DataGenerator[list[int]]):
                def generate(self, size: int, seed: int) -> list[int]:
                    return []

    def test_custom_generator_registration(self) -> None:
        test_name = "__test_custom_gen__"
        try:

            @register_generator(test_name)
            class CustomGen(DataGenerator[list[int]]):
                def generate(self, size: int, seed: int) -> list[int]:
                    return [0] * size

            gen = get_generator(test_name)
            assert gen.generate(size=3, seed=0) == [0, 0, 0]
        finally:
            # Очистка реестра после теста
            _REGISTRY.pop(test_name, None)
