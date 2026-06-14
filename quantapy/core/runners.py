"""Helpers for running domain-neutral execution specs."""

from __future__ import annotations

from typing import Dict

from quantapy.core.executions import ExecutionSpec
from quantapy.core.executors import ExecutionRequest, Executor
from quantapy.core.results import ResultBundle


class ExecutionSpecRunner:
    """Dispatch execution specs to registered executor adapters."""

    def __init__(self, executors: Dict[str, Executor]):
        self.executors = executors

    def run(self, spec: ExecutionSpec) -> ResultBundle:
        """Run a spec with the executor named by ``spec.runner``."""
        executor = self.executors.get(spec.runner)
        if executor is None:
            raise ValueError(f"No executor registered for runner '{spec.runner}'")
        return executor.run(ExecutionRequest.from_spec(spec))
