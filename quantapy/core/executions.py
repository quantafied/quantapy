"""Domain-neutral execution specifications and run records.

An execution spec describes what should be run, what artifacts it consumes, and
what configuration document should be handed to the runner. The runner may be an
in-process Python adapter today or an external binary/HPC job later.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional
from uuid import uuid4


@dataclass
class ArtifactBinding:
    """Named input artifact consumed by an execution."""

    id: str
    role: str = "primary"
    name: Optional[str] = None
    required: bool = True


@dataclass
class OutputBinding:
    """Expected output role produced by an execution."""

    role: str
    name: Optional[str] = None
    artifact_type: str = "table"
    kind: str = "result"
    attrs: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExecutionSpec:
    """Portable runnable document for a local, process, or remote executor."""

    runner: str
    inputs: List[ArtifactBinding]
    name: str
    id: str = field(default_factory=lambda: str(uuid4()))
    config: Dict[str, Any] = field(default_factory=dict)
    outputs: List[OutputBinding] = field(default_factory=list)
    resources: Dict[str, Any] = field(default_factory=dict)
    attrs: Dict[str, Any] = field(default_factory=dict)

    @property
    def primary_input_id(self) -> str:
        """Return the primary input artifact id."""
        primary = next((item for item in self.inputs if item.role == "primary"), None)
        if primary is None:
            if not self.inputs:
                raise ValueError("ExecutionSpec requires at least one input")
            primary = self.inputs[0]
        return primary.id

    def to_dict(self) -> Dict[str, Any]:
        """Return a JSON-friendly representation."""
        return asdict(self)


@dataclass
class ExecutionRun:
    """Recorded execution attempt and its observed outputs."""

    spec_id: str
    status: str
    id: str = field(default_factory=lambda: str(uuid4()))
    runner: Optional[str] = None
    input_ids: List[str] = field(default_factory=list)
    output_ids: List[str] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)
    summary: Dict[str, Any] = field(default_factory=dict)
    attrs: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Return a JSON-friendly representation."""
        return asdict(self)


def spec_input(input_id: str, role: str = "primary", name: Optional[str] = None) -> ArtifactBinding:
    """Convenience constructor for a spec input binding."""
    return ArtifactBinding(id=input_id, role=role, name=name)
