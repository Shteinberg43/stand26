from __future__ import annotations
import unittest

from src.common.types import StepEvent, OpType
from src.watchdog.counters import CounterManager, CounterRule
from src.watchdog.stop_conditions import parse_stop_if
from src.watchdog.watchdog import Watchdog, ExecutionLimitExceeded


class WatchdogTests(unittest.TestCase):
    def make_watchdog(self, stop_if: str):
        manager = CounterManager(
            [
                CounterRule("comparisons", OpType.CMP),
                CounterRule("reads", OpType.ARRAY_READ),
                CounterRule("total_ops", OpType.ANY),
            ]
        )
        cond = parse_stop_if(stop_if, symbols={"LIMIT": 10}) if 'LIMIT' in stop_if else parse_stop_if(stop_if)
        return Watchdog(manager, [cond])

    def test_cmp_only_increments_comparisons(self):
        wd = self.make_watchdog("STOP_IF total_ops > 100")
        snapshot = wd.on_event(StepEvent(OpType.CMP))
        self.assertEqual(snapshot.get("comparisons"), 1)
        self.assertEqual(snapshot.get("reads"), 0)
        self.assertEqual(snapshot.get("total_ops"), 1)

    def test_array_read_only_increments_reads(self):
        wd = self.make_watchdog("STOP_IF total_ops > 100")
        snapshot = wd.on_event(StepEvent(OpType.ARRAY_READ))
        self.assertEqual(snapshot.get("comparisons"), 0)
        self.assertEqual(snapshot.get("reads"), 1)
        self.assertEqual(snapshot.get("total_ops"), 1)

    def test_any_increments_total_ops(self):
        wd = self.make_watchdog("STOP_IF total_ops > 100")
        for event in [StepEvent(OpType.CMP), StepEvent(OpType.ASSIGN), StepEvent(OpType.CALL)]:
            snapshot = wd.on_event(event)
        self.assertEqual(snapshot.get("total_ops"), 3)

    def test_stop_if_total_ops_gt_10_stops_on_11th_event(self):
        wd = self.make_watchdog("STOP_IF total_ops > 10")
        for _ in range(10):
            snapshot = wd.on_event(StepEvent(OpType.ASSIGN))
        self.assertEqual(snapshot.get("total_ops"), 10)
        with self.assertRaises(ExecutionLimitExceeded):
            wd.on_event(StepEvent(OpType.ASSIGN))

    def test_stop_if_comparisons_ge_5_stops_when_reaches_5(self):
        wd = self.make_watchdog("STOP_IF comparisons >= 5")
        for _ in range(4):
            snapshot = wd.on_event(StepEvent(OpType.CMP))
        self.assertEqual(snapshot.get("comparisons"), 4)
        with self.assertRaises(ExecutionLimitExceeded):
            wd.on_event(StepEvent(OpType.CMP))

    def test_parse_stop_if_with_symbol_table(self):
        cond = parse_stop_if("STOP_IF total_ops > LIMIT", symbols={"LIMIT": 42})
        self.assertEqual(cond.counter_name, "total_ops")
        self.assertEqual(cond.threshold, 42)


if __name__ == "__main__":
    unittest.main()