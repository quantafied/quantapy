"""Registry for post-processing/evaluation plugins."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict


EVALUATOR_REGISTRY: Dict[str, Dict[str, Any]] = {}


def register_evaluator(evaluator: str, **metadata):
    """Register an evaluator class and its GUI/template metadata."""

    def decorator(cls):
        cls.evaluator = evaluator
        cls.evaluator_metadata = deepcopy(metadata)
        EVALUATOR_REGISTRY[evaluator] = {"evaluator": evaluator, "class": cls, **deepcopy(metadata)}
        return cls

    return decorator


def evaluator_metadata() -> Dict[str, Dict[str, Any]]:
    """Return JSON-friendly metadata for registered evaluators."""
    return {
        name: {key: value for key, value in metadata.items() if key != "class"}
        for name, metadata in EVALUATOR_REGISTRY.items()
    }


def evaluator_class(evaluator: str):
    """Return the registered evaluator class."""
    entry = EVALUATOR_REGISTRY.get(evaluator)
    if entry is None:
        raise KeyError(evaluator)
    return entry["class"]
