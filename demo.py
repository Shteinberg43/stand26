from a2t.common.types import OpType, StepEvent
from a2t.interpreter.counters import CounterManager, CounterRule
from a2t.interpreter.stop_conditions import Cmp, StopCondition
from a2t.interpreter.watchdog import Watchdog
from a2t.stand.batch_runner import BatchRunner
from a2t.stand.experiment_plan import ExperimentPlan, ParamSpec
from a2t.stand.generators import IntArrayGenerator
from a2t.stand.runner import TrialRunner
from a2t.stand.stats import StatsCollector


class DemoInterpreter:
    def reset_state(self):
        pass

    def execute_iter(self, program, inputs):
        data = inputs["array"]
        n = len(data)
        for _ in range(max(n, 1)):
            yield StepEvent(op=OpType.CMP, meta={"n": n})
        for _ in range(max(n // 2, 1)):
            yield StepEvent(op=OpType.ASSIGN, meta={"n": n})


def main():
    rules = [
        CounterRule("total_ops", OpType.ANY),
        CounterRule("comparisons", OpType.CMP),
        CounterRule("assignments", OpType.ASSIGN),
    ]
    counters = CounterManager(rules)
    watchdog = Watchdog(
        counter_manager=counters,
        stop_conditions=[StopCondition("total_ops", Cmp.GT, 1000)],
    )
    runner = TrialRunner(DemoInterpreter(), watchdog)

    plan = ExperimentPlan(
        experiment_id="stage4-demo",
        algorithm_name="quick_sort",
        params=[
            ParamSpec("n", [8, 16]),
            ParamSpec("mode", ["random", "sorted"]),
            ParamSpec("low", [0]),
            ParamSpec("high", [50]),
        ],
        trials=2,
        base_seed=100,
        export_formats=["csv", "txt"],
        notes="Stage 4 demo batch",
    )

    collector = StatsCollector()
    batch = BatchRunner(runner, IntArrayGenerator())
    batch.run_batch(plan, collector)

    print("RAW RUNS:")
    for row in collector.as_dicts():
        print(row)

    print("\nAGGREGATES:")
    for aggr in collector.aggregate_by_params():
        print(aggr)


if __name__ == "__main__":
    main()