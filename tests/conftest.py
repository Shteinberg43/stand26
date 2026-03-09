"""Общие фикстуры для тестов генераторов."""

import pytest


@pytest.fixture()
def default_seed() -> int:
    """Фиксированное зерно ГПСЧ для воспроизводимости тестов."""
    return 42


@pytest.fixture(params=[1, 10, 100, 1000])
def array_size(request: pytest.FixtureRequest) -> int:
    """Параметризованный размер массива для тестов."""
    return request.param
