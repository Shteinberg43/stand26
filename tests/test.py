import tempfile
import unittest
from pathlib import Path

from a2t.common.errors import PseudoCodeRuntimeError
from a2t.common.types import OpType, StepEvent
from a2t.interpreter.counters import CounterManager, CounterRule
from a2t.interpreter.stop_conditions import Cmp, StopCondition
from a2t.interpreter.watchdog import Watchdog
from a2t.stand.batch_runner import BatchRunner, iter_param_grid
from a2t.stand.experiment_plan import ExperimentPlan, ParamSpec
from a2t.stand.exporter import Exporter
from a2t.stand.generators import IntArrayGenerator
from a2t.stand.runner import TrialRunner
from a2t.stand.stats import RawRunRecord, StatsCollector


class MockInterpreter:
    def __init__(self, behavior="ok"):
        self.behavior = behavior

    def reset_state(self):
        pass

    def execute_iter(self, program, inputs):
        n = inputs.get("n", 3)
        if self.behavior == "ok":
            for i in range(n):
                yield StepEvent(op=OpType.CMP, meta={"i": i})
        elif self.behavior == "limit":
            for i in range(100):
                yield StepEvent(op=OpType.CMP, meta={"i": i})
        elif self.behavior == "error":
            yield StepEvent(op=OpType.CMP, meta={"i": 0})
            raise PseudoCodeRuntimeError("division by zero")
        else:
            raise ValueError("unknown behavior")


class TestStage4(unittest.TestCase):
    def _build_runner(self, behavior="ok", limit=100):
        rules = [
            CounterRule(name="total_ops", on_op=OpType.ANY),
            CounterRule(name="comparisons", on_op=OpType.CMP),
        ]
        counters = CounterManager(rules)
        watchdog = Watchdog(
            counter_manager=counters,
            stop_conditions=[StopCondition("total_ops", Cmp.GT, limit)],
        )
        return TrialRunner(MockInterpreter(behavior), watchdog)

    def test_same_seed_same_input(self):
        gen = IntArrayGenerator()
        params = {"n": 10, "mode": "random", "low": 0, "high": 100}
        self.assertEqual(gen.generate(params, 42), gen.generate(params, 42))

    def test_different_seed_different_input(self):
        gen = IntArrayGenerator()
        params = {"n": 10, "mode": "random", "low": 0, "high": 100}
        self.assertNotEqual(gen.generate(params, 1), gen.generate(params, 2))

    def test_param_grid(self):
        grid = list(iter_param_grid([
            ParamSpec("n", [10, 20]),
            ParamSpec("mode", ["random", "sorted"]),
        ]))
        self.assertEqual(len(grid), 4)

    def test_raw_record_fields(self):
        row = RawRunRecord(
            experiment_id="exp1",
            algorithm_name="quick_sort",
            params={"n": 100},
            trial_index=0,
            seed=123,
            status="OK",
            counters={"comparisons": 1000},
        )
        self.assertEqual(row.seed, 123)
        self.assertEqual(row.counters["comparisons"], 1000)

    def test_batch_continues_after_limit_and_error(self):
        plan = ExperimentPlan(
            experiment_id="exp-stage4",
            algorithm_name="quick_sort",
            params=[ParamSpec("n", [3])],
            trials=3,
            base_seed=100,
            export_formats=["csv", "txt"],
        )
        collector = StatsCollector()
        gen = IntArrayGenerator()

        class MixedRunner:
            def __init__(self):
                self.calls = 0

            def run_trial(self, program, inputs):
                self.calls += 1
                if self.calls == 1:
                    return self_runner_limit.run_trial(program, inputs)
                if self.calls == 2:
                    return self_runner_error.run_trial(program, inputs)
                return self_runner_ok.run_trial(program, inputs)

        self_runner_ok = self._build_runner("ok", limit=100)
        self_runner_limit = self._build_runner("limit", limit=5)
        self_runner_error = self._build_runner("error", limit=100)

        batch = BatchRunner(MixedRunner(), gen)
        batch.run_batch(plan, collector)

        self.assertEqual(len(collector.rows), 3)
        self.assertEqual(collector.rows[0].status, "LIMIT")
        self.assertEqual(collector.rows[1].status, "ERROR")
        self.assertEqual(collector.rows[2].status, "OK")

    def test_aggregate(self):
        collector = StatsCollector()
        collector.add(RawRunRecord("e1", "alg", {"n": 10}, 0, 1, "OK", {"ops": 10}))
        collector.add(RawRunRecord("e1", "alg", {"n": 10}, 1, 2, "OK", {"ops": 20}))
        aggr = collector.aggregate_by_params()

        self.assertEqual(len(aggr), 1)
        self.assertEqual(aggr[0].counter_stats["ops"]["mean"], 15.0)

    def test_exporter(self):
        rows = [
            {
                "experiment_id": "e1",
                "params": {"n": 10},
                "status": "OK",
                "counters": {"ops": 12},
            }
        ]
        exporter = Exporter()

        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            csv_path = td_path / "rows.csv"
            txt_path = td_path / "rows.txt"

            exporter.export_csv(csv_path, rows)
            exporter.export_txt(txt_path, rows)

            self.assertTrue(csv_path.exists())
            self.assertTrue(txt_path.exists())


if __name__ == "__main__":
    unittest.main()