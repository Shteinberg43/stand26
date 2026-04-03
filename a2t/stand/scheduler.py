from __future__ import annotations
from collections import deque
from dataclasses import dataclass
from typing import Any, Deque, Iterable, List, Optional

from a2t.common.errors import ExecutionLimitExceeded, PseudoCodeRuntimeError


@dataclass
class ScheduledRun:
    run_id: str
    stepper: Any
    watchdog: Any
    status: str = "RUNNING"
    error_message: Optional[str] = None
    steps_executed: int = 0
    times_scheduled: int = 0


class RoundRobinScheduler:
    """
    Квазипараллельный планировщик.
    Каждый запуск получает квант времени (число шагов интерпретатора),
    затем либо завершается, либо возвращается в очередь.
    """

    def __init__(self, quantum: int):
        if quantum <= 0:
            raise ValueError("quantum must be positive")
        self.quantum = quantum

    def run(self, scheduled_runs: Iterable[ScheduledRun]) -> List[ScheduledRun]:
        queue: Deque[ScheduledRun] = deque(scheduled_runs)
        completed: List[ScheduledRun] = []

        while queue:
            task = queue.popleft()
            task.times_scheduled += 1

            try:
                for _ in range(self.quantum):
                    event = task.stepper.step()
                    if event is None:
                        task.status = "OK"
                        completed.append(task)
                        break

                    task.watchdog.on_event(event)
                    task.steps_executed += 1
                else:
                    queue.append(task)

            except ExecutionLimitExceeded as exc:
                task.error_message = str(exc)
                task.status = "LIMIT"
                completed.append(task)

            except PseudoCodeRuntimeError as exc:
                task.error_message = str(exc)
                task.status = "ERROR"
                completed.append(task)

            except Exception as exc:
                task.error_message = "UNCAUGHT: {0}: {1}".format(type(exc).__name__, exc)
                task.status = "ERROR"
                completed.append(task)

        return completed
