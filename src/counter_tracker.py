"""Подписчик EventBus, накапливающий кумулятивные счётчики операций."""

from __future__ import annotations
from typing import Any, Dict


class CounterTracker:
    """Накапливает счётчики операций из StepEvent.meta["counters"].

    Метод ``snapshot()`` возвращает копию текущих кумулятивных счётчиков.
    """

    def __init__(self) -> None:
        self._counters: Dict[str, int] = {}

    def on_event(self, event: Any) -> None:
        meta = getattr(event, "meta", None)
        if isinstance(meta, dict):
            for k, v in meta.get("counters", {}).items():
                self._counters[k] = self._counters.get(k, 0) + v

    def snapshot(self) -> Dict[str, int]:
        return dict(self._counters)

    def reset(self) -> None:
        self._counters.clear()
