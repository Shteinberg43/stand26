"""Внутренние утилиты модуля генераторов."""

import random


def _make_rng(seed: int) -> random.Random:
    """Создаёт изолированный ГПСЧ с заданным зерном.

    Args:
        seed: Зерно генератора для воспроизводимости.

    Returns:
        Экземпляр ``random.Random`` с заданным seed.
    """
    return random.Random(seed)
