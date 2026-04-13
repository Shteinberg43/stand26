"""Сбор истории событий выполнения с временными метками и снимками счётчиков.

Подключается к EventBus как подписчик и накапливает полный
журнал StepEvent-ов для последующей визуализации и анализа.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


@dataclass(frozen=True)
class RecordedStep:
    """Одна зафиксированная операция в потоке выполнения."""

    step_index: int
    timestamp: float
    op: str
    meta: Dict[str, Any]
    counters: Dict[str, int]


class EventCollector:
    """Подписчик шины событий, накапливающий историю шагов.

    Использование::

        collector = EventCollector()
        bus.subscribe(collector.on_event)
        # ... выполнение алгоритма ...
        history = collector.history  # List[RecordedStep]
    """

    def __init__(
        self,
        counter_provider: Optional[Callable[[], Dict[str, int]]] = None,
    ) -> None:
        """
        Args:
            counter_provider: Вызываемый без аргументов объект, который
                возвращает текущий срез счётчиков (например,
                ``lambda: counter_manager.snapshot().values``).
                Если не указан, поле counters останется пустым словарём.
        """
        self._counter_provider = counter_provider
        self._steps: List[RecordedStep] = []
        self._start_time: Optional[float] = None

    # -- public API -----------------------------------------------------------

    @property
    def history(self) -> List[RecordedStep]:
        """Полный журнал зафиксированных шагов (копия)."""
        return list(self._steps)

    @property
    def step_count(self) -> int:
        return len(self._steps)

    def reset(self) -> None:
        """Очистить историю для повторного использования."""
        self._steps.clear()
        self._start_time = None

    # -- EventBus callback ----------------------------------------------------

    def on_event(self, event: Any) -> None:
        """Callback для ``bus.subscribe(collector.on_event)``."""
        now = time.monotonic()
        if self._start_time is None:
            self._start_time = now

        op_name = _extract_op_name(event)
        meta = _extract_meta(event)
        counters = self._counter_provider() if self._counter_provider else {}

        self._steps.append(
            RecordedStep(
                step_index=len(self._steps),
                timestamp=now - self._start_time,
                op=op_name,
                meta=meta,
                counters=dict(counters),
            )
        )

    # -- аналитические хелперы ------------------------------------------------

    def counters_at_step(self, index: int) -> Dict[str, int]:
        """Снимок счётчиков на конкретном шаге."""
        return dict(self._steps[index].counters)

    def final_counters(self) -> Dict[str, int]:
        """Счётчики после последнего шага (пустой dict если прогона не было)."""
        if not self._steps:
            return {}
        return dict(self._steps[-1].counters)

    def ops_sequence(self) -> List[str]:
        """Последовательность типов операций (для визуализации timeline)."""
        return [s.op for s in self._steps]

    def counter_series(self, counter_name: str) -> List[int]:
        """Временной ряд значения конкретного счётчика по шагам."""
        return [s.counters.get(counter_name, 0) for s in self._steps]

    def elapsed_sec(self) -> float:
        """Общее время выполнения от первого до последнего события."""
        if len(self._steps) < 2:
            return 0.0
        return self._steps[-1].timestamp - self._steps[0].timestamp


# -- helpers ------------------------------------------------------------------


def _extract_op_name(event: Any) -> str:
    """Извлечь имя операции из StepEvent или произвольного объекта."""
    if hasattr(event, "op"):
        op = event.op
        return op.name if hasattr(op, "name") else str(op)
    return type(event).__name__


def _extract_meta(event: Any) -> Dict[str, Any]:
    if hasattr(event, "meta") and isinstance(event.meta, dict):
        return dict(event.meta)
    return {}
