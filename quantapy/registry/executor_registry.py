"""Registry for executable workflow plugins.

Component plugins describe small building blocks. Executor plugins describe a
complete runnable contract: input requirements, template sections, and the
runner name used by ExecutionSpec.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict


EXECUTOR_REGISTRY: Dict[str, Dict[str, Any]] = {}


def register_executor(runner: str, **metadata):
    """Register an executor class and its GUI/template metadata."""

    def decorator(cls):
        cls.runner = runner
        cls.executor_metadata = deepcopy(metadata)
        EXECUTOR_REGISTRY[runner] = {"runner": runner, "class": cls, **deepcopy(metadata)}
        return cls

    return decorator


def executor_metadata() -> Dict[str, Dict[str, Any]]:
    """Return JSON-friendly metadata for registered executors."""
    return {
        runner: {
            key: value
            for key, value in metadata.items()
            if key != "class"
        }
        for runner, metadata in EXECUTOR_REGISTRY.items()
    }


def executor_class(runner: str):
    """Return the registered executor class for a runner."""
    entry = EXECUTOR_REGISTRY.get(runner)
    if entry is None:
        raise KeyError(runner)
    return entry["class"]
