"""Generic optimization helpers for executor-backed studies."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List

import pandas as pd

from quantapy.core.results import ResultBundle


@dataclass
class ObjectiveSpec:
    """Metrics and directions used to score executor results."""

    metric_names: List[str]
    directions: List[str]


class ExecutorObjectiveRunner:
    """Run an executor and score its ResultBundle metrics."""

    def __init__(self, executor: Any, objective: ObjectiveSpec):
        self.executor = executor
        self.objective = objective

    def run(self, request: Any) -> tuple[Any, ResultBundle]:
        """Execute a request and return objective score plus full result bundle."""
        bundle = self.executor.run(request)
        return self.score(bundle.metrics), bundle

    def score(self, metrics: dict[str, Any]) -> Any:
        """Extract objective values from a ResultBundle metrics mapping."""
        values = []
        for metric_name, direction in zip(self.objective.metric_names, self.objective.directions):
            value = metrics.get(metric_name)
            if pd.isna(value):
                value = -1e12 if direction == "maximize" else 1e12
            values.append(float(value))
        return values[0] if len(values) == 1 else tuple(values)

    def failure_score(self) -> Any:
        """Return objective values that make a failed trial unattractive."""
        values = [-1e12 if direction == "maximize" else 1e12 for direction in self.objective.directions]
        return values[0] if len(values) == 1 else tuple(values)
