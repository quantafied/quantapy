"""Domain-neutral evaluation specifications and run records."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional
from uuid import uuid4

from quantapy.core.executions import ArtifactBinding


@dataclass
class EvaluationSpec:
    """Portable document for post-processing previously produced artifacts."""

    evaluator: str
    inputs: List[ArtifactBinding]
    name: str
    id: str = field(default_factory=lambda: str(uuid4()))
    run_id: Optional[str] = None
    config: Dict[str, Any] = field(default_factory=dict)
    attrs: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Return a JSON-friendly representation."""
        return asdict(self)


@dataclass
class EvaluationRun:
    """Recorded evaluation attempt and its output artifacts."""

    spec_id: str
    evaluator: str
    status: str
    id: str = field(default_factory=lambda: str(uuid4()))
    source_run_id: Optional[str] = None
    input_ids: List[str] = field(default_factory=list)
    output_ids: List[str] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)
    summary: Dict[str, Any] = field(default_factory=dict)
    attrs: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Return a JSON-friendly representation."""
        return asdict(self)
