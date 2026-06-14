"""Generic evaluator interfaces for Quantapy workflows."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Protocol

from quantapy.core.evaluations import EvaluationSpec
from quantapy.core.results import ResultBundle


@dataclass
class EvaluationRequest:
    """Resolved artifact bindings and configuration for an evaluator."""

    inputs: Dict[str, str]
    config: Dict[str, Any] = field(default_factory=dict)
    name: str | None = None
    attrs: Dict[str, Any] = field(default_factory=dict)
    run_id: str | None = None
    spec_id: str | None = None
    spec: EvaluationSpec | None = None

    @classmethod
    def from_spec(cls, spec: EvaluationSpec) -> "EvaluationRequest":
        """Build a request from an EvaluationSpec."""
        return cls(
            inputs={binding.role: binding.id for binding in spec.inputs},
            config=dict(spec.config),
            name=spec.name,
            attrs={**dict(spec.attrs), "evaluation_spec_id": spec.id, "evaluator": spec.evaluator},
            run_id=spec.run_id,
            spec_id=spec.id,
            spec=spec,
        )


class Evaluator(Protocol):
    """Minimal contract implemented by post-processing plugins."""

    name: str

    def evaluate(self, request: EvaluationRequest) -> ResultBundle:
        """Evaluate bound input artifacts and return result artifacts."""
        ...
