"""Модуль сбора и вычисления робастных статистик по результатам экспериментов.

Поддерживает: среднее, медиану, стандартное отклонение, квантили,
IQR, min/max, коэффициент вариации.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence


@dataclass(frozen=True)
class CounterStats:
    """Робастные статистики для одного счётчика по множеству прогонов."""

    name: str
    count: int
    mean: float
    median: float
    stddev: float
    min: int
    max: int
    q25: float
    q75: float
    iqr: float
    cv: float  # коэффициент вариации (stddev / mean), 0 если mean == 0

    def as_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "count": self.count,
            "mean": self.mean,
            "median": self.median,
            "stddev": self.stddev,
            "min": self.min,
            "max": self.max,
            "q25": self.q25,
            "q75": self.q75,
            "iqr": self.iqr,
            "cv": self.cv,
        }


@dataclass
class RunResult:
    """Результат одного прогона алгоритма."""

    run_id: str
    input_size: int
    generator_name: str
    counters: Dict[str, int]
    status: str = "OK"
    elapsed_sec: float = 0.0

    def as_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "input_size": self.input_size,
            "generator_name": self.generator_name,
            "counters": dict(self.counters),
            "status": self.status,
            "elapsed_sec": self.elapsed_sec,
        }


class StatsCollector:
    """Сборщик и агрегатор экспериментальных результатов.

    Пример::

        stats = StatsCollector()

        for trial in range(10):
            # ... запуск алгоритма ...
            stats.add_run(RunResult(
                run_id=f"trial_{trial}",
                input_size=100,
                generator_name="random",
                counters=watchdog.counter_manager.snapshot().values,
            ))

        summary = stats.summary()
        # summary["comparisons"] -> CounterStats(mean=450, median=445, ...)
    """

    def __init__(self) -> None:
        self._runs: List[RunResult] = []

    @property
    def runs(self) -> List[RunResult]:
        return list(self._runs)

    @property
    def run_count(self) -> int:
        return len(self._runs)

    def add_run(self, result: RunResult) -> None:
        """Добавить результат прогона."""
        self._runs.append(result)

    def reset(self) -> None:
        """Очистить все накопленные результаты."""
        self._runs.clear()

    # -- основной анализ ------------------------------------------------------

    def summary(
        self,
        filter_status: str = "OK",
    ) -> Dict[str, CounterStats]:
        """Вычислить робастные статистики по всем счётчикам.

        Args:
            filter_status: Учитывать только прогоны с этим статусом.

        Returns:
            Словарь {имя_счётчика: CounterStats}.
        """
        filtered = [r for r in self._runs if r.status == filter_status]
        if not filtered:
            return {}

        counter_names = _all_counter_names(filtered)
        result: Dict[str, CounterStats] = {}

        for name in counter_names:
            values = [r.counters.get(name, 0) for r in filtered]
            result[name] = _compute_stats(name, values)

        return result

    def summary_by_size(
        self,
        filter_status: str = "OK",
    ) -> Dict[int, Dict[str, CounterStats]]:
        """Статистики, сгруппированные по размеру входных данных.

        Returns:
            {input_size: {counter_name: CounterStats}}.
        """
        filtered = [r for r in self._runs if r.status == filter_status]
        sizes = sorted({r.input_size for r in filtered})
        result: Dict[int, Dict[str, CounterStats]] = {}

        for size in sizes:
            group = [r for r in filtered if r.input_size == size]
            counter_names = _all_counter_names(group)
            result[size] = {}
            for name in counter_names:
                values = [r.counters.get(name, 0) for r in group]
                result[size][name] = _compute_stats(name, values)

        return result

    def summary_by_generator(
        self,
        filter_status: str = "OK",
    ) -> Dict[str, Dict[str, CounterStats]]:
        """Статистики, сгруппированные по типу генератора.

        Returns:
            {generator_name: {counter_name: CounterStats}}.
        """
        filtered = [r for r in self._runs if r.status == filter_status]
        generators = sorted({r.generator_name for r in filtered})
        result: Dict[str, Dict[str, CounterStats]] = {}

        for gen in generators:
            group = [r for r in filtered if r.generator_name == gen]
            counter_names = _all_counter_names(group)
            result[gen] = {}
            for name in counter_names:
                values = [r.counters.get(name, 0) for r in group]
                result[gen][name] = _compute_stats(name, values)

        return result

    def export_csv(self, path: str) -> None:
        """Экспорт всех результатов прогонов в CSV-файл."""
        if not self._runs:
            return

        counter_names = sorted(_all_counter_names(self._runs))
        header = ["run_id", "input_size", "generator_name", "status", "elapsed_sec"]
        header.extend(counter_names)

        lines = [",".join(header)]
        for r in self._runs:
            row = [r.run_id, str(r.input_size), r.generator_name, r.status, f"{r.elapsed_sec:.6f}"]
            row.extend(str(r.counters.get(name, 0)) for name in counter_names)
            lines.append(",".join(row))

        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")

    def export_summary_csv(self, path: str) -> None:
        """Экспорт сводной статистики в CSV-файл."""
        summary = self.summary()
        if not summary:
            return

        header = ["counter", "count", "mean", "median", "stddev", "min", "max", "q25", "q75", "iqr", "cv"]
        lines = [",".join(header)]

        for name, cs in sorted(summary.items()):
            row = [
                name, str(cs.count), f"{cs.mean:.4f}", f"{cs.median:.4f}",
                f"{cs.stddev:.4f}", str(cs.min), str(cs.max),
                f"{cs.q25:.4f}", f"{cs.q75:.4f}", f"{cs.iqr:.4f}", f"{cs.cv:.4f}",
            ]
            lines.append(",".join(row))

        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")


# -- вспомогательные функции -------------------------------------------------


def _all_counter_names(runs: List[RunResult]) -> List[str]:
    """Собрать все уникальные имена счётчиков из списка прогонов."""
    names: set[str] = set()
    for r in runs:
        names.update(r.counters.keys())
    return sorted(names)


def _compute_stats(name: str, values: Sequence[int]) -> CounterStats:
    """Вычислить робастные статистики для списка значений."""
    n = len(values)
    if n == 0:
        return CounterStats(
            name=name, count=0, mean=0.0, median=0.0, stddev=0.0,
            min=0, max=0, q25=0.0, q75=0.0, iqr=0.0, cv=0.0,
        )

    sorted_vals = sorted(values)
    total = sum(sorted_vals)
    mean = total / n

    # Медиана
    median = _percentile(sorted_vals, 0.5)

    # Стандартное отклонение (выборочное, N-1)
    if n > 1:
        variance = sum((x - mean) ** 2 for x in sorted_vals) / (n - 1)
        stddev = math.sqrt(variance)
    else:
        stddev = 0.0

    q25 = _percentile(sorted_vals, 0.25)
    q75 = _percentile(sorted_vals, 0.75)
    iqr = q75 - q25

    cv = (stddev / mean) if mean != 0 else 0.0

    return CounterStats(
        name=name,
        count=n,
        mean=mean,
        median=median,
        stddev=stddev,
        min=sorted_vals[0],
        max=sorted_vals[-1],
        q25=q25,
        q75=q75,
        iqr=iqr,
        cv=cv,
    )


def _percentile(sorted_vals: Sequence[int], p: float) -> float:
    """Вычислить p-й перцентиль линейной интерполяцией."""
    n = len(sorted_vals)
    if n == 1:
        return float(sorted_vals[0])

    k = (n - 1) * p
    f = math.floor(k)
    c = math.ceil(k)

    if f == c:
        return float(sorted_vals[int(k)])

    return sorted_vals[f] * (c - k) + sorted_vals[c] * (k - f)
