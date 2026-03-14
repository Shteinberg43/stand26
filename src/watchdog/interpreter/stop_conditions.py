from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
import re
from typing import Mapping, Optional

from watchdog.interpreter.counters import CounterSnapshot


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
        raise ValueError(f"Unknown comparator: {self.op}")


_STOP_IF_RE = re.compile(
    r"^\s*STOP_IF\s+(?P<counter>[A-Za-z_][A-Za-z0-9_]*)\s*"
    r"(?P<op>>=|<=|==|!=|>|<)\s*"
    r"(?P<threshold>[A-Za-z_][A-Za-z0-9_]*|\d+)\s*$"
)


def parse_stop_if(text: str, symbols: Optional[Mapping[str, int]] = None) -> StopCondition:
    match = _STOP_IF_RE.match(text)
    if not match:
        raise ValueError(f"Invalid STOP_IF expression: {text!r}")

    counter_name = match.group("counter")
    op = Cmp(match.group("op"))
    raw_threshold = match.group("threshold")

    if raw_threshold.isdigit():
        threshold = int(raw_threshold)
    else:
        if symbols is None or raw_threshold not in symbols:
            raise ValueError(f"Unknown threshold symbol: {raw_threshold}")
        threshold = int(symbols[raw_threshold])

    return StopCondition(counter_name=counter_name, op=op, threshold=threshold)
