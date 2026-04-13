"""Модуль визуализации и сбора статистики для стенда экспериментов.

Компоненты:
    - EventBus          — синхронная шина событий
    - EventCollector    — журнал шагов выполнения
    - StatsCollector    — агрегация робастных статистик
    - CounterTracker    — кумулятивные счётчики операций
"""

from src.event_bus import EventBus
from src.event_collector import EventCollector, RecordedStep
from src.stats_collector import StatsCollector, RunResult, CounterStats
from src.counter_tracker import CounterTracker

__all__ = [
    "EventBus",
    "EventCollector",
    "RecordedStep",
    "StatsCollector",
    "RunResult",
    "CounterStats",
    "CounterTracker",
]
