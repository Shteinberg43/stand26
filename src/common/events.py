from __future__ import annotations
from typing import Callable, List, Any


class EventBus:
    """Синхронная шина событий этапа 2.

    Публикация события не означает внешнее аппаратное прерывание.
    Все подписчики вызываются в том же потоке исполнения.
    """

    def __init__(self) -> None:
        self._listeners: List[Callable[[Any], None]] = []

    def subscribe(self, listener: Callable[[Any], None]) -> None:
        self._listeners.append(listener)

    def publish(self, event: Any) -> None:
        for listener in list(self._listeners):
            listener(event)