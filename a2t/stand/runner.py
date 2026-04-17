from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional

from a2t.common.errors import PseudoCodeRuntimeError
from a2t.interpreter.watchdog import Watchdog, ExecutionLimitExceeded


class RunStatus(Enum):
    OK = "OK"
    LIMIT = "LIMIT"
    ERROR = "ERROR"


@dataclass
class RunResult:
    status: RunStatus
    counters: Dict[str, int]
    error_message: Optional[str] = None
    payload: Dict[str, Any] = field(default_factory=dict)


class TrialRunner:
    def __init__(self, interpreter, watchdog):
        self.interpreter = interpreter
        self.watchdog = watchdog

    def run_trial(self, program, inputs):
        self.interpreter.reset_state()
        self.watchdog.reset()

        try:
            for event in self.interpreter.execute_iter(program, inputs):
                self.watchdog.on_event(event)

            snapshot = self.watchdog.counter_manager.snapshot()
            return RunResult(
                status=RunStatus.OK,
                counters=dict(snapshot.values),
            )

        except ExecutionLimitExceeded as e:
            snapshot = self.watchdog.counter_manager.snapshot()
            return RunResult(
                status=RunStatus.LIMIT,
                counters=dict(snapshot.values),
                error_message=str(e),
            )

        except PseudoCodeRuntimeError as e:
            snapshot = self.watchdog.counter_manager.snapshot()
            return RunResult(
                status=RunStatus.ERROR,
                counters=dict(snapshot.values),
                error_message=str(e),
            )

        except Exception as e:
            snapshot = self.watchdog.counter_manager.snapshot()
            return RunResult(
                status=RunStatus.ERROR,
                counters=dict(snapshot.values),
                error_message="UNCAUGHT: %s: %s" % (type(e).__name__, e),
            )
