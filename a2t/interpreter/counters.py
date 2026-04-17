from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Iterable, List
from a2t.common.types import StepEvent, OpType


@dataclass
class CounterRule:
    name: str
    on_op: OpType


@dataclass
class CounterSnapshot:
    values: Dict[str, int]

    def get(self, name: str) -> int:
        return self.values.get(name, 0)


class CounterManager:
    def __init__(self, rules: Iterable[CounterRule]):
        self.rules = list(rules)
        self.values = dict((rule.name, 0) for rule in self.rules)  # type: Dict[str, int]

    def reset(self) -> None:
        for key in self.values:
            self.values[key] = 0

    def on_event(self, event: StepEvent) -> None:
        for rule in self.rules:
            if rule.on_op == OpType.ANY or rule.on_op == event.op:
                self.values[rule.name] += 1

    def snapshot(self) -> CounterSnapshot:
        return CounterSnapshot(values=dict(self.values))
