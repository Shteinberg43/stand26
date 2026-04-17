from __future__ import annotations
from collections import deque
from dataclasses import dataclass
from typing import Optional


@dataclass
class ScheduledRun:
    run_id: str
    stepper: object
    watchdog: object
    status: str = "RUNNING"
    error_message: Optional[str] = None


class RoundRobinScheduler:
    def __init__(self, quantum):
        self.quantum = quantum

    def run(self, scheduled_runs):
        q = deque(scheduled_runs)
        completed = []

        while q:
            task = q.popleft()
            try:
                for _ in range(self.quantum):
                    event = task.stepper.step()
                    if event is None:
                        task.status = "OK"
                        completed.append(task)
                        break
                    task.watchdog.on_event(event)
                else:
                    q.append(task)

            except Exception as e:
                msg = str(e)
                task.error_message = msg
                task.status = "LIMIT" if "STOP_IF" in msg else "ERROR"
                completed.append(task)

        return completed
