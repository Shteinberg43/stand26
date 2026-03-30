from __future__ import annotations

from itertools import product
from typing import Any, Dict, Iterable

from a2t.stand.experiment_plan import ExperimentPlan, ParamSpec
from a2t.stand.stats import RawRunRecord, StatsCollector


def iter_param_grid(param_specs: list[ParamSpec]) -> Iterable[Dict[str, Any]]:
    if not param_specs:
        yield {}
        return

    names = [p.name for p in param_specs]
    values_product = product(*[p.values for p in param_specs])

    for values in values_product:
        yield dict(zip(names, values))


class BatchRunner:
    def __init__(self, trial_runner, generator):
        self.trial_runner = trial_runner
        self.generator = generator

    def run_batch(self, plan: ExperimentPlan, collector: StatsCollector) -> None:
        plan.validate()

        for params in iter_param_grid(plan.params):
            for trial_idx in range(plan.trials):
                seed = plan.base_seed + trial_idx
                inputs = self.generator.generate(params, seed)
                result = self.trial_runner.run_trial(plan.algorithm_name, inputs)

                collector.add(
                    RawRunRecord(
                        experiment_id=plan.experiment_id,
                        algorithm_name=plan.algorithm_name,
                        params=dict(params),
                        trial_index=trial_idx,
                        seed=seed,
                        status=result.status.value,
                        counters=dict(result.counters),
                        error_message=result.error_message,
                    )
                )