from __future__ import annotations
from typing import Any, Dict, Callable
from a2t.common.types import StepEvent, OpType


class SemanticExecutor:
    """
    Контракт между семантическим обходом CST/AST и инфраструктурой стенда.
    Семантика не знает ничего про watchdog и batch-runner: она только испускает StepEvent.
    """
    def __init__(self, runtime, event_sink):
        self.runtime = runtime
        self.event_sink = event_sink

    def emit(self, op, **meta):
        self.event_sink(StepEvent(op=op, meta=meta))

    def eval_compare(self, left, right):
        self.emit(OpType.CMP, left=left, right=right)
        return left > right

    def eval_assign(self, name, value):
        self.emit(OpType.ASSIGN, name=name)
        self.runtime[name] = value
        return value

    def eval_array_read(self, arr, idx):
        self.emit(OpType.ARRAY_READ, index=idx)
        return arr[idx]

    def eval_array_write(self, arr, idx, value):
        self.emit(OpType.ARRAY_WRITE, index=idx)
        arr[idx] = value
        return value

    def eval_branch(self, condition):
        self.emit(OpType.BRANCH, condition=condition)
        return bool(condition)
