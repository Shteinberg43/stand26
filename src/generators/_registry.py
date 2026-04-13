"""Реестр генераторов данных с автоматической регистрацией через декоратор."""

from typing import Any

from src.generators._base import DataGenerator

_REGISTRY: dict[str, type[DataGenerator[Any]]] = {}


def register_generator(name: str):
    """Декоратор для регистрации генератора в глобальном реестре.

    Args:
        name: Строковый ключ генератора (например, ``"random"``).

    Returns:
        Декоратор, регистрирующий класс и возвращающий его без изменений.

    Raises:
        KeyError: Если генератор с таким именем уже зарегистрирован.
    """

    def decorator(
        cls: type[DataGenerator[Any]],
    ) -> type[DataGenerator[Any]]:
        if name in _REGISTRY:
            raise KeyError(f"Generator '{name}' already registered")
        _REGISTRY[name] = cls
        return cls

    return decorator


def get_generator(name: str, **kwargs: Any) -> DataGenerator[Any]:
    """Возвращает экземпляр генератора по строковому ключу.

    Args:
        name: Ключ из реестра (например, ``"random"``).
        **kwargs: Аргументы, передаваемые в конструктор генератора.

    Returns:
        Экземпляр зарегистрированного генератора.

    Raises:
        KeyError: Если генератор с таким именем не найден.
    """
    if name not in _REGISTRY:
        available = list(_REGISTRY.keys())
        raise KeyError(
            f"Unknown generator '{name}'. Available: {available}"
        )
    return _REGISTRY[name](**kwargs)


def list_generators() -> list[str]:
    """Возвращает список имён всех зарегистрированных генераторов.

    Returns:
        Список строковых ключей.
    """
    return list(_REGISTRY.keys())
