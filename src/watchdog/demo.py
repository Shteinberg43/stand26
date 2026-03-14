from __future__ import annotations

from watchdog.common.events import EventBus
from watchdog.common.types import StepEvent, OpType
from watchdog.interpreter.counters import CounterManager, CounterRule
from watchdog.interpreter.stop_conditions import parse_stop_if
from watchdog.interpreter.watchdog import Watchdog, ExecutionLimitExceeded


def build_demo_watchdog(limit: int = 10):
    bus = EventBus()
    manager = CounterManager(
        [
            CounterRule("comparisons", OpType.CMP),
            CounterRule("reads", OpType.ARRAY_READ),
            CounterRule("writes", OpType.ARRAY_WRITE),
            CounterRule("total_ops", OpType.ANY),
        ]
    )
    cond = parse_stop_if(f"STOP_IF total_ops > {limit}")
    watchdog = Watchdog(manager, [cond])
    bus.subscribe(watchdog.on_event)
    return bus, watchdog


def main() -> None:
    bus, watchdog = build_demo_watchdog(limit=10)
    events = [
        StepEvent(OpType.CMP, {"i": 1}),
        StepEvent(OpType.ARRAY_READ, {"array": "A", "index": 0}),
        StepEvent(OpType.ASSIGN, {"target": "x"}),
        StepEvent(OpType.CMP, {"i": 2}),
        StepEvent(OpType.CMP, {"i": 3}),
        StepEvent(OpType.ARRAY_WRITE, {"array": "A", "index": 1}),
        StepEvent(OpType.CMP, {"i": 4}),
        StepEvent(OpType.ASSIGN, {"target": "y"}),
        StepEvent(OpType.CMP, {"i": 5}),
        StepEvent(OpType.CALL, {"name": "swap"}),
        StepEvent(OpType.RETURN, {"name": "swap"}),
    ]

    for idx, event in enumerate(events, start=1):
        try:
            snapshot = watchdog.on_event(event)
            print(f"step={idx:02d} op={event.op.name:>11} snapshot={snapshot.values}")
        except ExecutionLimitExceeded as exc:
            print(f"step={idx:02d} op={event.op.name:>11} LIMIT: {exc}")
            break


if __name__ == "__main__":
    main()
