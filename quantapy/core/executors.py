"""Generic executor interfaces for Quantapy workflows."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, Protocol

from quantapy.core.executions import ExecutionSpec
from quantapy.core.results import ResultBundle


@dataclass
class ExecutionRequest:
    """Input artifact and configuration document for an executor run."""

    input_id: str
    config: Dict[str, Any] = field(default_factory=dict)
    name: str | None = None
    attrs: Dict[str, Any] = field(default_factory=dict)
    spec_id: str | None = None
    spec: ExecutionSpec | None = None

    @classmethod
    def from_spec(cls, spec: ExecutionSpec) -> "ExecutionRequest":
        """Build a request from a portable execution spec."""
        return cls(
            input_id=spec.primary_input_id,
            config=dict(spec.config),
            name=spec.name,
            attrs={**dict(spec.attrs), "execution_spec_id": spec.id, "runner": spec.runner},
            spec_id=spec.id,
            spec=spec,
        )


@dataclass
class PreparedExecution:
    """Prepared executor request plus metadata about staged inputs."""

    request: ExecutionRequest
    input_id: str
    metadata: Dict[str, Any] = field(default_factory=dict)


class Executor(Protocol):
    """Minimal contract implemented by local, process, or remote tools."""

    name: str

    def run(self, request: ExecutionRequest) -> ResultBundle:
        """Execute a tool and return a domain-neutral result bundle."""
        ...


class InputPreparer(Protocol):
    """Prepare one executor input artifact from a source artifact and config."""

    def prepare(
        self,
        source_id: str,
        prepared_name: str,
        attrs: Dict[str, Any] | None = None,
        selected_params: Dict[str, Any] | None = None,
    ) -> PreparedExecution:
        """Return an execution request pointed at a prepared input artifact."""
        ...


class ParameterMutator(Protocol):
    """Apply optimization/search parameters to an executor configuration."""

    def apply(self, parameter: Any, value: Any) -> None:
        """Apply one parameter value to the underlying configuration."""
        ...

    def apply_many(self, updates: Iterable[tuple[Any, Any]]) -> None:
        """Apply multiple parameter values to the underlying configuration."""
        ...
