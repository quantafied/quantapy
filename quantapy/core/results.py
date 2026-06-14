"""Generic execution result contracts.

These classes are intentionally domain-neutral. A trading backtest, CFD solve,
ML training run, or external binary can all report outputs as named artifacts
with roles and lightweight metadata.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ResultArtifact:
    """One output produced by an executor."""

    role: str
    data: Any
    artifact_type: str = "table"
    name: Optional[str] = None
    kind: str = "unknown"
    attrs: Dict[str, Any] = field(default_factory=dict)
    transform: Optional[Dict[str, Any]] = None


@dataclass
class ResultBundle:
    """Collection of artifacts and summary metadata from one executor run."""

    artifacts: List[ResultArtifact] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)
    summary: Dict[str, Any] = field(default_factory=dict)
    run_id: Optional[str] = None

    def artifact(self, role: str) -> Optional[ResultArtifact]:
        """Return the first artifact with a matching role."""
        return next((artifact for artifact in self.artifacts if artifact.role == role), None)
