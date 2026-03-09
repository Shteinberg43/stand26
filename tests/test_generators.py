"""Тесты свойств конкретных генераторов массивов."""

import pytest

from generators import get_generator
from generators._base import DataGenerator
from generators.interfaces import DequeInserter, DictInserter, ListInserter, QueueInserter
import queue


class TestRandomGenerator:
    """Тесты для генератора случайных последовательностей."""

    def test_returns_list_of_int(self, default_seed: int) -> None:
        gen = get_generator("random")
        ins = ListInserter()
        gen.fill(ins, size=10, seed=default_seed)
        result = ins.target
        assert isinstance(result, list)
        assert all(isinstance(x, int) for x in result)

    def test_correct_length(
        self, default_seed: int, array_size: int
    ) -> None:
        gen = get_generator("random")
        ins = ListInserter()
        gen.fill(ins, size=array_size, seed=default_seed)
        result = ins.target
        assert len(result) == array_size

    def test_reproducibility(self, default_seed: int) -> None:
        gen = get_generator("random")
        ins1 = ListInserter()
        gen.fill(ins1, size=50, seed=default_seed)
        first = ins1.target
        ins2 = ListInserter()
        gen.fill(ins2, size=50, seed=default_seed)
        second = ins2.target
        assert first == second

    def test_different_seed_gives_different_result(self) -> None:
        gen = get_generator("random")
        ins_a = ListInserter()
        gen.fill(ins_a, size=50, seed=1)
        a = ins_a.target
        ins_b = ListInserter()
        gen.fill(ins_b, size=50, seed=2)
        b = ins_b.target
        assert a != b

    def test_values_in_range(self, default_seed: int) -> None:
        gen = get_generator("random", low=10, high=20)
        ins = ListInserter()
        gen.fill(ins, size=100, seed=default_seed)
        result = ins.target
        assert all(10 <= x <= 20 for x in result)

    def test_invalid_size_raises(self, default_seed: int) -> None:
        gen = get_generator("random")
        with pytest.raises(ValueError):
            ins = ListInserter()
            gen.fill(ins, size=0, seed=default_seed)
        with pytest.raises(ValueError):
            ins = ListInserter()
            gen.fill(ins, size=-5, seed=default_seed)


class TestSortedGenerator:
    """Тесты для генератора отсортированных последовательностей."""

    def test_is_sorted(self, default_seed: int) -> None:
        gen = get_generator("sorted")
        ins = ListInserter()
        gen.fill(ins, size=100, seed=default_seed)
        result = ins.target
        assert result == sorted(result)

    def test_correct_length(
        self, default_seed: int, array_size: int
    ) -> None:
        gen = get_generator("sorted")
        ins = ListInserter()
        gen.fill(ins, size=array_size, seed=default_seed)
        result = ins.target
        assert len(result) == array_size

    def test_reproducibility(self, default_seed: int) -> None:
        gen = get_generator("sorted")
        ins1 = ListInserter()
        gen.fill(ins1, size=50, seed=default_seed)
        first = ins1.target
        ins2 = ListInserter()
        gen.fill(ins2, size=50, seed=default_seed)
        second = ins2.target
        assert first == second

    def test_invalid_size_raises(self, default_seed: int) -> None:
        gen = get_generator("sorted")
        with pytest.raises(ValueError):
            ins = ListInserter()
            gen.fill(ins, size=0, seed=default_seed)


class TestReverseSortedGenerator:
    """Тесты для генератора обратно отсортированных последовательностей."""

    def test_is_reverse_sorted(self, default_seed: int) -> None:
        gen = get_generator("reverse")
        ins = ListInserter()
        gen.fill(ins, size=100, seed=default_seed)
        result = ins.target
        assert result == sorted(result, reverse=True)

    def test_correct_length(
        self, default_seed: int, array_size: int
    ) -> None:
        gen = get_generator("reverse")
        ins = ListInserter()
        gen.fill(ins, size=array_size, seed=default_seed)
        result = ins.target
        assert len(result) == array_size

    def test_reproducibility(self, default_seed: int) -> None:
        gen = get_generator("reverse")
        ins1 = ListInserter()
        gen.fill(ins1, size=50, seed=default_seed)
        first = ins1.target
        ins2 = ListInserter()
        gen.fill(ins2, size=50, seed=default_seed)
        second = ins2.target
        assert first == second

    def test_invalid_size_raises(self, default_seed: int) -> None:
        gen = get_generator("reverse")
        with pytest.raises(ValueError):
            ins = ListInserter()
            gen.fill(ins, size=0, seed=default_seed)


class TestDuplicatesGenerator:
    """Тесты для генератора последовательностей с дубликатами."""

    def test_has_duplicates(self, default_seed: int) -> None:
        gen = get_generator("duplicates")
        ins = ListInserter()
        gen.fill(ins, size=100, seed=default_seed)
        result = ins.target
        assert len(set(result)) < len(result)

    def test_values_in_narrow_range(self, default_seed: int) -> None:
        gen = get_generator("duplicates", num_unique=5)
        ins = ListInserter()
        gen.fill(ins, size=100, seed=default_seed)
        result = ins.target
        assert all(0 <= x < 5 for x in result)

    def test_correct_length(
        self, default_seed: int, array_size: int
    ) -> None:
        gen = get_generator("duplicates")
        ins = ListInserter()
        gen.fill(ins, size=array_size, seed=default_seed)
        result = ins.target
        assert len(result) == array_size

    def test_reproducibility(self, default_seed: int) -> None:
        gen = get_generator("duplicates")
        ins1 = ListInserter()
        gen.fill(ins1, size=50, seed=default_seed)
        first = ins1.target
        ins2 = ListInserter()
        gen.fill(ins2, size=50, seed=default_seed)
        second = ins2.target
        assert first == second

    def test_invalid_size_raises(self, default_seed: int) -> None:
        gen = get_generator("duplicates")
        with pytest.raises(ValueError):
            ins = ListInserter()
            gen.fill(ins, size=0, seed=default_seed)


class TestNearlySortedGenerator:
    """Тесты для генератора почти отсортированных последовательностей."""

    def test_differs_from_fully_sorted(self, default_seed: int) -> None:
        gen = get_generator("nearly_sorted")
        ins = ListInserter()
        gen.fill(ins, size=100, seed=default_seed)
        result = ins.target
        assert result != sorted(result)

    def test_mostly_sorted(self, default_seed: int) -> None:
        """Проверяет, что большая часть элементов стоит на своих местах."""
        gen = get_generator("nearly_sorted", swap_fraction=0.02)
        ins = ListInserter()
        gen.fill(ins, size=1000, seed=default_seed)
        result = ins.target
        sorted_result = sorted(result)
        same_positions = sum(
            1 for a, b in zip(result, sorted_result) if a == b
        )
        # Не менее 80% элементов совпадают с полностью отсортированным
        assert same_positions / len(result) >= 0.80

    def test_correct_length(
        self, default_seed: int, array_size: int
    ) -> None:
        gen = get_generator("nearly_sorted")
        ins = ListInserter()
        gen.fill(ins, size=array_size, seed=default_seed)
        result = ins.target
        assert len(result) == array_size

    def test_reproducibility(self, default_seed: int) -> None:
        gen = get_generator("nearly_sorted")
        ins1 = ListInserter()
        gen.fill(ins1, size=50, seed=default_seed)
        first = ins1.target
        ins2 = ListInserter()
        gen.fill(ins2, size=50, seed=default_seed)
        second = ins2.target
        assert first == second

    def test_invalid_size_raises(self, default_seed: int) -> None:
        gen = get_generator("nearly_sorted")
        with pytest.raises(ValueError):
            ins = ListInserter()
            gen.fill(ins, size=0, seed=default_seed)


class TestAllGeneratorsInheritance:
    """Проверяет, что все генераторы — подклассы DataGenerator."""

    @pytest.fixture(params=["random", "sorted", "reverse", "duplicates", "nearly_sorted"])
    def generator_name(self, request: pytest.FixtureRequest) -> str:
        return request.param

    def test_is_data_generator(self, generator_name: str) -> None:
        gen = get_generator(generator_name)
        assert isinstance(gen, DataGenerator)


class TestAdaptersFeatures:
    """Тесты для встроенных адаптеров (Inserter)."""

    def test_queue_inserter(self, default_seed: int) -> None:
        gen = get_generator("random")
        ins = QueueInserter[int]()
        gen.fill(ins, size=15, seed=default_seed)
        assert ins.target.qsize() == 15
        val = ins.target.get()
        assert isinstance(val, int)

    def test_deque_inserter(self, default_seed: int) -> None:
        gen = get_generator("sorted")
        ins = DequeInserter[int]()
        gen.fill(ins, size=15, seed=default_seed)
        assert len(ins.target) == 15
        assert ins.target[0] <= ins.target[-1]

    def test_dict_inserter(self, default_seed: int) -> None:
        gen = get_generator("reverse")
        ins = DictInserter[int](start_index=5)
        gen.fill(ins, size=10, seed=default_seed)
        assert len(ins.target) == 10
        assert 5 in ins.target
        assert 14 in ins.target
        assert ins.target[5] >= ins.target[14]

