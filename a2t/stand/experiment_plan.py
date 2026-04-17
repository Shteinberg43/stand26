from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Union

ParamValue = Union[int, float, bool, str]


@dataclass(frozen=True)
class ParamSpec:
    name: str
    values: List[ParamValue]

    def validate(self) -> None:
        if not self.name:
            raise ValueError("ParamSpec.name must not be empty")
        if not self.values:
            raise ValueError("ParamSpec %s must contain at least one value" % self.name)
        for value in self.values:
            if not isinstance(value, (int, float, bool, str)):
                raise TypeError(
                    "Unsupported parameter type for %s: %s" % (self.name, type(value).__name__)
                )


@dataclass(frozen=True)
class ExperimentPlan:
    experiment_id: str
    algorithm_name: str
    params: List[ParamSpec]
    trials: int
    base_seed: int
    export_formats: List[str] = field(default_factory=lambda: ["csv", "json"])
    notes: str = ""

    def validate(self) -> None:
        if not self.experiment_id:
            raise ValueError("experiment_id must not be empty")
        if not self.algorithm_name:
            raise ValueError("algorithm_name must not be empty")
        if self.trials <= 0:
            raise ValueError("trials must be positive")
        for spec in self.params:
            spec.validate()
        for fmt in self.export_formats:
            if fmt not in ("csv", "txt", "json"):
                raise ValueError("Unsupported export format: %s" % fmt)
