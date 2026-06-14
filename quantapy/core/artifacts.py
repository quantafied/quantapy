"""Generic artifact catalog for files, folders, and parsed data products."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4


@dataclass
class ArtifactRecord:
    """Catalog entry for a raw or parsed artifact."""

    id: str
    name: str
    artifact_type: str
    role: str = "artifact"
    uri: Optional[str] = None
    parent_ids: List[str] = field(default_factory=list)
    dataframe_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    provenance: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Return a JSON-friendly representation."""
        return asdict(self)


class ArtifactCatalog:
    """Small artifact registry used beside DataStore."""

    def __init__(self):
        self._records: Dict[str, ArtifactRecord] = {}

    def add(
        self,
        name: str,
        artifact_type: str,
        *,
        role: str = "artifact",
        uri: Optional[str | Path] = None,
        parent_ids: Optional[List[str]] = None,
        dataframe_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        provenance: Optional[Dict[str, Any]] = None,
        artifact_id: Optional[str] = None,
    ) -> ArtifactRecord:
        """Register an artifact and return its record."""
        record = ArtifactRecord(
            id=artifact_id or str(uuid4()),
            name=name,
            artifact_type=artifact_type,
            role=role,
            uri=str(uri) if uri is not None else None,
            parent_ids=parent_ids or [],
            dataframe_id=dataframe_id,
            metadata=metadata or {},
            provenance=provenance or {},
        )
        self._records[record.id] = record
        return record

    def get(self, artifact_id: str) -> Optional[ArtifactRecord]:
        """Return an artifact record by id."""
        return self._records.get(artifact_id)

    def records(self) -> List[ArtifactRecord]:
        """Return all artifact records in insertion order."""
        return list(self._records.values())

    def children(self, artifact_id: str) -> List[ArtifactRecord]:
        """Return artifacts that reference artifact_id as a parent."""
        return [record for record in self._records.values() if artifact_id in record.parent_ids]
