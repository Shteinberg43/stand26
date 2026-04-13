"""Интерфейсы для взаимодействия генераторов с приемниками данных."""

from collections import deque
from queue import Queue
from typing import Any, Callable, Dict, Generic, List, Protocol, TypeVar

T = TypeVar("T")

class OutputIterator(Protocol[T]):
    """Протокол (интерфейс) для приемников сгенерированных данных.
    
    Любая структура, которая хочет заполняться генераторами, 
    должна реализовывать этот интерфейс или быть обернутой в совместимый адаптер.
    """
    def insert(self, item: T) -> None:
        """Добавляет один элемент в структуру данных."""
        ...

class ListInserter(Generic[T]):
    """Адаптер для встроенного списка (list)."""
    def __init__(self, target: list[T] | None = None) -> None:
        self.target = target if target is not None else []

    def insert(self, item: T) -> None:
        self.target.append(item)

class DequeInserter(Generic[T]):
    """Адаптер для двусторонней очереди (collections.deque)."""
    def __init__(self, target: deque[T] | None = None) -> None:
        self.target = target if target is not None else deque()

    def insert(self, item: T) -> None:
        self.target.append(item)

class QueueInserter(Generic[T]):
    """Адаптер для потокобезопасной очереди (queue.Queue)."""
    def __init__(self, target: Queue | None = None) -> None:
        self.target = target if target is not None else Queue()

    def insert(self, item: T) -> None:
        self.target.put(item)

class DictInserter(Generic[T]):
    """Адаптер для встроенного словаря (dict).
    
    В качестве ключей использует автоинкрементный счетчик (индексы).
    Подходит для эмуляции хеш-таблиц с последовательными ключами.
    """
    def __init__(self, target: dict[int, T] | None = None, start_index: int = 0) -> None:
        self.target = target if target is not None else {}
        self.current_idx = start_index

    def insert(self, item: T) -> None:
        self.target[self.current_idx] = item
        self.current_idx += 1
