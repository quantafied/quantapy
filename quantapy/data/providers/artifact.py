"""Registered artifact file/folder data provider."""

from __future__ import annotations

from pathlib import Path
from typing import Dict

import pandas as pd

from quantapy.artifacts.importer import import_path
from quantapy.core.artifacts import ArtifactCatalog
from quantapy.core.timeseries import DataStore
from quantapy.data.providers.base import BaseProvider
from quantapy.registry.component_registry import register_component


@register_component(category="Dataset", function="Artifact", source="Local")
class Artifact(BaseProvider):
    """Import supported local files/folders as registered artifacts and tables."""

    config = {
        "title": "Local Artifact",
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "default": "",
                "description": "File or folder path",
                "widget_type": "file",
            },
            "recursive": {
                "type": "string",
                "default": "true",
                "description": "Scan folders recursively",
                "enum": ["true", "false"],
                "widget_type": "select",
            },
            "max_files": {
                "type": "integer",
                "default": 200,
                "description": "Maximum files to scan from a folder",
            },
        },
    }

    def __init__(self, **kwargs):
        """Initialize artifact import parameters."""
        super().__init__(**kwargs)
        self.catalog = ArtifactCatalog()
        self.store = DataStore()
        self.import_result = None
        self.fetch_metadata: Dict[str, Dict] = {}

    def execute(self) -> Dict[str, pd.DataFrame]:
        """Import the configured path and return parsed table artifacts."""
        path = Path(str(self.params.get("path") or "")).expanduser()
        if not path.exists():
            raise FileNotFoundError(f"Artifact path does not exist: {path}")

        recursive = str(self.params.get("recursive", "true")).lower() == "true"
        max_files = int(self.params.get("max_files") or 200)
        self.import_result = import_path(
            path,
            catalog=self.catalog,
            store=self.store,
            recursive=recursive,
            max_files=max_files,
            provenance={"provider": "Dataset.Artifact.Local"},
        )

        outputs: Dict[str, pd.DataFrame] = {}
        for record in self.store.records():
            outputs[record.name] = record.data.to_dataframe()
            self.fetch_metadata[record.name] = {
                **dict(record.attrs),
                "artifact": "source",
                "provider": "Local",
                "function": "Artifact",
                "category": "Dataset",
            }
        return outputs
