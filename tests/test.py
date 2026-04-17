import shutil
import tempfile
import unittest

from a2t.common.types import OpType
from a2t.interpreter.counters import CounterRule, CounterManager
from a2t.interpreter.stop_conditions import StopCondition, Cmp
from a2t.interpreter.watchdog import Watchdog
from a2t.stand.runner import TrialRunner, RunStatus
from a2t.stand.experiment_plan import ExperimentPlan, ParamSpec
from a2t.stand.generators import IntArrayGenerator
from a2t.stand.stats import StatsCollector
from a2t.stand.batch_runner import BatchRunner
from a2t.stand.exporter import Exporter
from a2t.integration.ast_semantics import SemanticExecutor
from a2t.integration.cst_bridge import CSTBridge


class SemanticInterpreterAdapter:
    def __init__(self, cst_nodes):
        self.cst_nodes = cst_nodes
        self.runtime = {}
        self._event_sink = None

    def bind_event_sink(self, event_sink):
        self._event_sink = event_sink

    def reset_state(self):
        self.runtime = {}

    def execute_iter(self, program, inputs):
        # program ignored in this stage demo: CST is already produced by parser team
        semantic = SemanticExecutor(self.runtime, self._event_sink)
        bridge = CSTBridge(semantic)
        before = []
        semantic.event_sink = before.append
        bridge.execute_nodes(self.cst_nodes)
        for event in before:
            yield event


class Stage6Tests(unittest.TestCase):
    def _build_runner(self, cst_nodes, limit=100):
        rules = [
            CounterRule("total_ops", OpType.ANY),
            CounterRule("comparisons", OpType.CMP),
            CounterRule("assignments", OpType.ASSIGN),
            CounterRule("array_reads", OpType.ARRAY_READ),
            CounterRule("array_writes", OpType.ARRAY_WRITE),
        ]
        cm = CounterManager(rules)
        wd = Watchdog(cm, [StopCondition("total_ops", Cmp.GT, limit)])
        interp = SemanticInterpreterAdapter(cst_nodes)
        interp.bind_event_sink(lambda event: wd.on_event(event))
        # runner will call watchdog again, so bind a collector sink instead
        interp.bind_event_sink(lambda event: None)
        return TrialRunner(interp, wd)

    def test_semantic_executor_emits_counters(self):
        nodes = [
            {"kind": "assign", "name": "x", "value": 10},
            {"kind": "compare", "left": 10, "right": 5},
            {"kind": "array_write", "array": [1, 2], "index": 1, "value": 7},
            {"kind": "array_read", "array": [1, 2], "index": 0},
        ]
        runner = self._build_runner(nodes, limit=100)
        result = runner.run_trial("alg", {})
        self.assertEqual(result.status, RunStatus.OK)
        self.assertEqual(result.counters["assignments"], 1)
        self.assertEqual(result.counters["comparisons"], 1)
        self.assertEqual(result.counters["array_writes"], 1)
        self.assertEqual(result.counters["array_reads"], 1)

    def test_watchdog_limit_from_semantic_layer(self):
        nodes = [{"kind": "assign", "name": "x", "value": i} for i in range(15)]
        runner = self._build_runner(nodes, limit=10)
        result = runner.run_trial("alg", {})
        self.assertEqual(result.status, RunStatus.LIMIT)

    def test_batch_export_json_csv(self):
        nodes = [{"kind": "assign", "name": "x", "value": 1}]
        runner = self._build_runner(nodes, limit=100)
        plan = ExperimentPlan(
            experiment_id="exp-stage6",
            algorithm_name="demo_alg",
            params=[ParamSpec("n", [3, 5])],
            trials=2,
            base_seed=123,
            export_formats=["csv", "json"],
        )
        collector = StatsCollector()
        batch = BatchRunner(runner, IntArrayGenerator())
        batch.run_batch(plan, collector)
        rows = collector.as_dicts()

        tmp = tempfile.mkdtemp(prefix="stage6_")
        try:
            exporter = Exporter()
            exporter.export_csv(tmp + "/raw.csv", rows)
            exporter.export_json(tmp + "/raw.json", rows)
            self.assertTrue(len(rows) == 4)
        finally:
            shutil.rmtree(tmp)

    def test_reproducibility_same_seed_same_input(self):
        gen = IntArrayGenerator()
        params = {"n": 6, "mode": "random", "low": 0, "high": 9}
        a = gen.generate(params, seed=77)
        b = gen.generate(params, seed=77)
        self.assertEqual(a, b)


if __name__ == "__main__":
    unittest.main()
