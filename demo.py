from a2t.common.types import OpType
from a2t.interpreter.counters import CounterRule, CounterManager
from a2t.interpreter.stop_conditions import StopCondition, Cmp
from a2t.interpreter.watchdog import Watchdog
from a2t.stand.runner import TrialRunner
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
        self._events = []

    def reset_state(self):
        self.runtime = {}
        self._events = []

    def execute_iter(self, program, inputs):
        semantic = SemanticExecutor(self.runtime, self._events.append)
        bridge = CSTBridge(semantic)
        bridge.execute_nodes(self.cst_nodes)
        for event in self._events:
            yield event


def main():
    rules = [
        CounterRule("total_ops", OpType.ANY),
        CounterRule("comparisons", OpType.CMP),
        CounterRule("assignments", OpType.ASSIGN),
        CounterRule("array_reads", OpType.ARRAY_READ),
        CounterRule("array_writes", OpType.ARRAY_WRITE),
    ]
    watchdog = Watchdog(CounterManager(rules), [StopCondition("total_ops", Cmp.GT, 50)])

    cst_nodes = [
        {"kind": "assign", "name": "x", "value": 10},
        {"kind": "compare", "left": 10, "right": 5},
        {"kind": "array_write", "array": [1, 2, 3], "index": 1, "value": 99},
        {"kind": "array_read", "array": [1, 2, 3], "index": 2},
        {"kind": "branch", "condition": True},
    ]

    runner = TrialRunner(SemanticInterpreterAdapter(cst_nodes), watchdog)
    plan = ExperimentPlan(
        experiment_id="final-stage6",
        algorithm_name="demo_alg",
        params=[
            ParamSpec("n", [5, 8]),
            ParamSpec("mode", ["random", "sorted"]),
        ],
        trials=2,
        base_seed=100,
        export_formats=["csv", "json"],
        notes="Stage 6 final integration demo",
    )

    collector = StatsCollector()
    batch = BatchRunner(runner, IntArrayGenerator())
    batch.run_batch(plan, collector)

    rows = collector.as_dicts()
    aggr = collector.aggregate_by_params()

    exporter = Exporter()
    exporter.export_csv("stage6_raw.csv", rows)
    exporter.export_json("stage6_raw.json", rows)

    print("RAW ROWS:", len(rows))
    for row in rows[:2]:
        print(row)
    print("AGGREGATES:", len(aggr))
    for item in aggr[:2]:
        print(item)


if __name__ == "__main__":
    main()
