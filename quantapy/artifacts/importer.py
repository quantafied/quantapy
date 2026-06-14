"""Import files and folders into the Quantapy artifact catalog."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

from quantapy.core.artifacts import ArtifactCatalog, ArtifactRecord
from quantapy.core.timeseries import DataStore


TABLE_EXTENSIONS = {".csv", ".tsv", ".dat"}
TEXT_EXTENSIONS = {".txt", ".log", ".out", ".err"}
JSON_EXTENSIONS = {".json"}


@dataclass
class ImportResult:
    """Artifacts and datasets created by one import action."""

    artifacts: List[ArtifactRecord] = field(default_factory=list)
    dataset_ids: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


def import_path(
    path: str | Path,
    *,
    catalog: ArtifactCatalog,
    store: DataStore,
    name: Optional[str] = None,
    recursive: bool = True,
    max_files: int = 200,
    parent_ids: Optional[List[str]] = None,
    provenance: Optional[Dict[str, Any]] = None,
) -> ImportResult:
    """Import a file or directory and register detected artifacts."""
    source = Path(path).expanduser().resolve()
    if not source.exists():
        raise FileNotFoundError(str(source))
    if source.is_dir():
        return _import_directory(
            source,
            catalog=catalog,
            store=store,
            name=name,
            recursive=recursive,
            max_files=max_files,
            parent_ids=parent_ids,
            provenance=provenance,
        )
    return _import_file(
        source,
        catalog=catalog,
        store=store,
        name=name,
        parent_ids=parent_ids,
        provenance=provenance,
    )


def _import_directory(
    path: Path,
    *,
    catalog: ArtifactCatalog,
    store: DataStore,
    name: Optional[str],
    recursive: bool,
    max_files: int,
    parent_ids: Optional[List[str]],
    provenance: Optional[Dict[str, Any]],
) -> ImportResult:
    result = ImportResult()
    directory = catalog.add(
        name or path.name,
        "directory",
        role="artifact_collection",
        uri=path,
        parent_ids=parent_ids,
        metadata=_file_metadata(path),
        provenance={"origin": "import", **dict(provenance or {})},
    )
    result.artifacts.append(directory)
    files = [item for item in (path.rglob("*") if recursive else path.iterdir()) if item.is_file()]
    for file_path in files[:max_files]:
        child = _import_file(
            file_path,
            catalog=catalog,
            store=store,
            parent_ids=[directory.id],
            provenance=provenance,
        )
        result.artifacts.extend(child.artifacts)
        result.dataset_ids.extend(child.dataset_ids)
        result.warnings.extend(child.warnings)
    if len(files) > max_files:
        result.warnings.append(f"Imported first {max_files} file(s) from {path}; skipped {len(files) - max_files}.")
    return result


def _import_file(
    path: Path,
    *,
    catalog: ArtifactCatalog,
    store: DataStore,
    name: Optional[str] = None,
    parent_ids: Optional[List[str]] = None,
    provenance: Optional[Dict[str, Any]] = None,
) -> ImportResult:
    result = ImportResult()
    detected = detect_artifact_format(path)
    raw = catalog.add(
        name or path.name,
        "file",
        role="raw_file",
        uri=path,
        parent_ids=parent_ids,
        metadata={**_file_metadata(path), "detected_format": detected},
        provenance={"origin": "import", **dict(provenance or {})},
    )
    result.artifacts.append(raw)

    if detected == "text":
        catalog.add(
            f"{path.stem} Text",
            "text",
            role="text",
            uri=path,
            parent_ids=[raw.id],
            metadata={"preview": _read_text_preview(path)},
            provenance={"origin": "parsed_file", "parser": "text_reader"},
        )
        return result

    parsed = read_structured_file(path, detected)
    if parsed is None:
        return result

    dataset_name = _dataset_name(path, store)
    dataset_id = store.add_raw(
        dataset_name,
        parsed,
        source={"provider": "artifact_import", "path": str(path), "format": detected},
        attrs={
            "artifact": "source",
            "origin": "import",
            "artifact_type": "table",
            "source_path": str(path),
            "source_filename": path.name,
            "detected_format": detected,
            "raw_artifact_id": raw.id,
        },
    )
    parsed_artifact = catalog.add(
        dataset_name,
        "table",
        role="parsed_table",
        uri=path,
        parent_ids=[raw.id],
        dataframe_id=dataset_id,
        metadata={
            "columns": list(parsed.columns),
            "shape": [int(parsed.shape[0]), int(parsed.shape[1])],
            "detected_format": detected,
        },
        provenance={"origin": "parsed_file", "parser": f"{detected}_reader"},
    )
    record = store.get_record(dataset_id)
    if record is not None:
        record.attrs["artifact_ref_id"] = parsed_artifact.id
    result.artifacts.append(parsed_artifact)
    result.dataset_ids.append(dataset_id)
    return result


def detect_artifact_format(path: Path) -> str:
    """Return a coarse format label for a file."""
    suffix = path.suffix.lower()
    if suffix in TABLE_EXTENSIONS:
        return "table"
    if suffix in JSON_EXTENSIONS:
        return "json"
    if suffix in TEXT_EXTENSIONS:
        return "text"
    if _looks_like_text_table(path):
        return "table"
    return "binary"


def read_structured_file(path: Path, detected: str) -> Optional[pd.DataFrame]:
    """Read a supported structured artifact into a DataFrame."""
    if detected == "json":
        return _read_json(path)
    if detected == "table":
        return _read_table(path)
    return None


def _read_table(path: Path) -> Optional[pd.DataFrame]:
    suffix = path.suffix.lower()
    try:
        if suffix == ".tsv":
            df = pd.read_csv(path, sep="\t")
        elif suffix == ".dat":
            names = _comment_header(path)
            if names:
                df = pd.read_csv(path, sep=r"\s+", comment="#", names=names)
            else:
                df = pd.read_csv(path, sep=None, engine="python", comment="#")
        else:
            df = pd.read_csv(path)
    except Exception:
        try:
            df = pd.read_csv(path, sep=r"\s+", comment="#")
        except Exception:
            return None
    return df if not df.empty else None


def _comment_header(path: Path) -> Optional[List[str]]:
    """Return a whitespace header from a leading '# col_a col_b' line."""
    try:
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith("#"):
                tokens = stripped.lstrip("#").strip().split()
                if tokens and not all(_is_number(token) for token in tokens):
                    return tokens
                continue
            return None
    except Exception:
        return None
    return None


def _is_number(value: str) -> bool:
    try:
        float(value)
        return True
    except ValueError:
        return False


def _read_json(path: Path) -> Optional[pd.DataFrame]:
    try:
        return pd.read_json(path)
    except Exception:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None
    if isinstance(payload, list):
        return pd.DataFrame(payload)
    if isinstance(payload, dict):
        if all(isinstance(value, list) for value in payload.values()):
            return pd.DataFrame(payload)
        return pd.DataFrame([payload])
    return None


def _looks_like_text_table(path: Path) -> bool:
    try:
        sample = path.read_text(encoding="utf-8", errors="ignore")[:4096]
    except Exception:
        return False
    lines = [line for line in sample.splitlines() if line.strip() and not line.lstrip().startswith("#")]
    if len(lines) < 2:
        return False
    first = lines[0]
    return "," in first or "\t" in first or len(first.split()) > 1


def _read_text_preview(path: Path, limit: int = 4000) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")[:limit]
    except Exception:
        return ""


def _file_metadata(path: Path) -> Dict[str, Any]:
    stat = path.stat()
    return {
        "filename": path.name,
        "extension": path.suffix.lower(),
        "size_bytes": int(stat.st_size),
        "modified_time": stat.st_mtime,
    }


def _dataset_name(path: Path, store: DataStore) -> str:
    base = path.stem.replace("/", "-").replace(":", "-")
    if store.get_record(base) is None:
        return base
    suffix = path.suffix.lower().lstrip(".") or "file"
    candidate = f"{base}-{suffix}"
    if store.get_record(candidate) is None:
        return candidate
    index = 2
    while store.get_record(f"{candidate}-{index}") is not None:
        index += 1
    return f"{candidate}-{index}"
