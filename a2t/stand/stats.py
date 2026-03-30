from __future__ import annotations

from dataclasses import asdict, dataclass
from statistics import mean, median, pstdev
from typing import Any, Dict, List


@dataclass
class RawRunRecord:
    experiment_id: str
    algorithm_name: str
    params: Dict[str, Any]
    trial_index: int
    seed: int
    status: str
    counters: Dict[str, int]
    error_message: str | None = None


@dataclass
class AggregateMetric:
    group_key: Dict[str, Any]
    status_counts: Dict[str, int]
    counter_stats: Dict[str, Dict[str, float]]


class StatsCollector:
    def __init__(self):
        self.rows: List[RawRunRecord] = []

    def add(self, row: RawRunRecord) -> None:
        self.rows.append(row)

    def as_dicts(self) -> List[Dict[str, Any]]:
        return [asdict(r) for r in self.rows]

    def aggregate_by_params(self) -> List[AggregateMetric]:
        groups: Dict[tuple, List[RawRunRecord]] = {}

        for row in self.rows:
            key = tuple(sorted(row.params.items()))
            groups.setdefault(key, []).append(row)

        result: List[AggregateMetric] = []

        for key, rows in groups.items():
            group_key = dict(key)
            status_counts: Dict[str, int] = {}
            all_counter_names = set()

            for row in rows:
                status_counts[row.status] = status_counts.get(row.status, 0) + 1
                all_counter_names.update(row.counters.keys())

            counter_stats: Dict[str, Dict[str, float]] = {}
            for counter_name in sorted(all_counter_names):
                values = [row.counters.get(counter_name, 0) for row in rows]
                counter_stats[counter_name] = {
                    "mean": float(mean(values)),
                    "median": float(median(values)),
                    "std": float(pstdev(values)) if len(values) > 1 else 0.0,
                }

            result.append(
                AggregateMetric(
                    group_key=group_key,
                    status_counts=status_counts,
                    counter_stats=counter_stats,
                )
            )

        return result