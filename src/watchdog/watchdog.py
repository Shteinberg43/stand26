from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable, List

from src.common.types import StepEvent
from src.watchdog.counters import CounterManager, CounterSnapshot
from src.watchdog.stop_conditions import StopCondition


class ExecutionLimitExceeded(RuntimeError):
    pass


@dataclass
class WatchdogState:
    triggered: bool = False
    reason: str | None = None


class Watchdog:
    def __init__(self, counter_manager: CounterManager, stop_conditions: Iterable[StopCondition]):
        self.counter_manager = counter_manager
        self.stop_conditions: List[StopCondition] = list(stop_conditions)
        self.state = WatchdogState()

    def reset(self) -> None:
        self.counter_manager.reset()
        self.state = WatchdogState()

    def on_event(self, event: StepEvent) -> CounterSnapshot:
        self.counter_manager.on_event(event)
        snapshot = self.counter_manager.snapshot()

        for cond in self.stop_conditions:
            if cond.is_triggered(snapshot):
                self.state.triggered = True
                self.state.reason = (
                    f"STOP_IF {cond.counter_name} {cond.op.value} {cond.threshold}; "
                    f"actual={snapshot.get(cond.counter_name)}"
                )
                raise ExecutionLimitExceeded(self.state.reason)

        return snapshot