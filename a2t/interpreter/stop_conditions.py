from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from a2t.interpreter.counters import CounterSnapshot


class Cmp(Enum):
    GT = ">"
    GE = ">="
    LT = "<"
    LE = "<="
    EQ = "=="
    NE = "!="


@dataclass(frozen=True)
class StopCondition:
    counter_name: str
    op: Cmp
    threshold: int

    def is_triggered(self, snapshot: CounterSnapshot) -> bool:
        value = snapshot.get(self.counter_name)
        if self.op == Cmp.GT:
            return value > self.threshold
        if self.op == Cmp.GE:
            return value >= self.threshold
        if self.op == Cmp.LT:
            return value < self.threshold
        if self.op == Cmp.LE:
            return value <= self.threshold
        if self.op == Cmp.EQ:
            return value == self.threshold
        if self.op == Cmp.NE:
            return value != self.threshold
        raise ValueError("Unknown comparator: %s" % self.op)
