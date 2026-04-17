from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable, List, Optional
from a2t.common.types import StepEvent
from a2t.interpreter.counters import CounterManager, CounterSnapshot
from a2t.interpreter.stop_conditions import StopCondition


class ExecutionLimitExceeded(RuntimeError):
    pass


@dataclass
class WatchdogState:
    triggered: bool = False
    reason: Optional[str] = None


class Watchdog:
    def __init__(self, counter_manager: CounterManager, stop_conditions: Iterable[StopCondition]):
        self.counter_manager = counter_manager
        self.stop_conditions = list(stop_conditions)  # type: List[StopCondition]
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
                    "STOP_IF %s %s %s; actual=%s"
                    % (cond.counter_name, cond.op.value, cond.threshold, snapshot.get(cond.counter_name))
                )
                raise ExecutionLimitExceeded(self.state.reason)

        return snapshot
