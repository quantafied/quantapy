"""Collection-level artifact operations.

Collections let data preparation operate on one artifact or on a grouped set of
artifacts with the same code path. The functions here are intentionally small
and library-first so the API/GUI can remain thin wrappers.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional
from uuid import uuid4

import numpy as np
import pandas as pd

from quantapy.core.artifacts import ArtifactCatalog, ArtifactRecord
from quantapy.core.timeseries import DataStore
from quantapy.modules.data.synthesize import GaussianNoise
from quantapy.modules.study import validation as _validation_components  # noqa: F401 - import registers components
from quantapy.orchestrator.calculator import Calculator
from quantapy.registry.component_registry import COMPONENT_REGISTRY


@dataclass
class CollectionResult:
    """Result of a collection operation."""

    collection: ArtifactRecord
    dataset_ids: List[str]
    artifact_ids: List[str]


def create_dataset_artifact(
    catalog: ArtifactCatalog,
    store: DataStore,
    *,
    name: str,
    dataframe: pd.DataFrame,
    parent_ids: Optional[List[str]] = None,
    kind: str = "derived",
    role: str = "data",
    attrs: Optional[Dict[str, Any]] = None,
    transform: Optional[Dict[str, Any]] = None,
    provenance: Optional[Dict[str, Any]] = None,
) -> tuple[str, ArtifactRecord]:
    """Store a dataframe and register a linked table artifact."""
    dataset_id = store.add(
        name,
        dataframe,
        kind=kind,
        parent_ids=parent_ids,
        attrs=attrs or {},
        transform=transform,
        source={"provider": "artifact_collection", **dict(provenance or {})},
    )
    artifact = catalog.add(
        name,
        "table",
        role=role,
        parent_ids=parent_ids,
        dataframe_id=dataset_id,
        metadata={"shape": [int(dataframe.shape[0]), int(dataframe.shape[1])], "columns": list(dataframe.columns)},
        provenance=provenance,
    )
    record = store.get_record(dataset_id)
    if record is not None:
        record.attrs["artifact_ref_id"] = artifact.id
    return dataset_id, artifact


def create_collection(
    catalog: ArtifactCatalog,
    *,
    name: str,
    collection_type: str,
    members: List[Dict[str, Any]],
    parent_ids: Optional[List[str]] = None,
    metadata: Optional[Dict[str, Any]] = None,
    provenance: Optional[Dict[str, Any]] = None,
) -> ArtifactRecord:
    """Register a collection artifact."""
    return catalog.add(
        name,
        "collection",
        role=collection_type,
        parent_ids=parent_ids,
        metadata={**dict(metadata or {}), "collection_type": collection_type, "members": members},
        provenance=provenance,
    )


def mark_collection_members(catalog: ArtifactCatalog, store: DataStore, collection: ArtifactRecord) -> None:
    """Mark collection leaf datasets so the GUI can hide them as top-level items."""
    for leaf in leaf_dataset_members(catalog, store, collection.id):
        dataset_id = leaf.get("dataset_id")
        record = store.get_record(str(dataset_id)) if dataset_id else None
        if record is None:
            continue
        collection_ids = list(record.attrs.get("collection_ids") or [])
        if collection.id not in collection_ids:
            collection_ids.append(collection.id)
        record.attrs["collection_ids"] = collection_ids
        record.attrs["collection_member"] = True


def create_raw_collection(
    catalog: ArtifactCatalog,
    store: DataStore,
    *,
    name: str,
    artifact_ids: Optional[List[str]] = None,
    dataset_ids: Optional[List[str]] = None,
    parent_ids: Optional[List[str]] = None,
    metadata: Optional[Dict[str, Any]] = None,
    provenance: Optional[Dict[str, Any]] = None,
) -> ArtifactRecord:
    """Create a raw data collection from existing artifacts and/or datasets."""
    artifacts_by_id = {artifact.id: artifact for artifact in catalog.records()}
    artifacts_by_dataset_id = {
        artifact.dataframe_id: artifact
        for artifact in catalog.records()
        if artifact.dataframe_id
    }
    members: List[Dict[str, Any]] = []
    seen: set[str] = set()

    for artifact_id in artifact_ids or []:
        artifact = artifacts_by_id.get(artifact_id)
        if artifact is None or artifact.artifact_type == "collection":
            continue
        if artifact.dataframe_id is None and artifact.artifact_type not in {"text"}:
            continue
        key = artifact.dataframe_id or artifact.id
        if key in seen:
            continue
        seen.add(key)
        members.append({
            "label": artifact.name,
            "artifact_id": artifact.id,
            "dataset_id": artifact.dataframe_id,
            "role": artifact.role,
        })

    for dataset_id in dataset_ids or []:
        record = store.get_record(dataset_id)
        if record is None or dataset_id in seen:
            continue
        artifact = artifacts_by_dataset_id.get(dataset_id)
        members.append({
            "label": record.name,
            "artifact_id": artifact.id if artifact else None,
            "dataset_id": dataset_id,
            "role": "raw_data",
        })
        seen.add(dataset_id)

    collection = create_collection(
        catalog,
        name=name,
        collection_type="raw_data",
        members=members,
        parent_ids=parent_ids,
        metadata={"n_members": len(members), **dict(metadata or {})},
        provenance={"origin": "raw_data", **dict(provenance or {})},
    )
    mark_collection_members(catalog, store, collection)
    return collection


def collection_members(catalog: ArtifactCatalog, collection_id: str) -> List[Dict[str, Any]]:
    """Return collection member descriptors."""
    collection = catalog.get(collection_id)
    if collection is None or collection.artifact_type != "collection":
        raise ValueError(f"Collection '{collection_id}' not found")
    return list(collection.metadata.get("members") or [])


def leaf_dataset_members(catalog: ArtifactCatalog, store: DataStore, artifact_or_collection_id: str) -> List[Dict[str, Any]]:
    """Return all leaf dataframe artifacts below an artifact or collection."""
    artifact = catalog.get(artifact_or_collection_id)
    if artifact is None:
        record = store.get_record(artifact_or_collection_id)
        if record is None:
            raise ValueError(f"Artifact or dataset '{artifact_or_collection_id}' not found")
        return [{"label": record.name, "artifact_id": None, "dataset_id": record.id, "path": []}]
    if artifact.artifact_type != "collection":
        if artifact.dataframe_id is None:
            return []
        return [{"label": artifact.name, "artifact_id": artifact.id, "dataset_id": artifact.dataframe_id, "path": []}]

    leaves: List[Dict[str, Any]] = []
    for member in collection_members(catalog, artifact.id):
        member_id = member.get("artifact_id")
        if not member_id:
            continue
        child = catalog.get(str(member_id))
        if child is None:
            continue
        if child.artifact_type == "collection":
            for leaf in leaf_dataset_members(catalog, store, child.id):
                leaves.append({**leaf, "path": [member.get("label") or child.name, *leaf.get("path", [])]})
        elif child.dataframe_id:
            leaves.append({
                "label": member.get("label") or child.name,
                "artifact_id": child.id,
                "dataset_id": child.dataframe_id,
                "path": [member.get("label") or child.name],
            })
    return leaves


def gaussian_noise_collection(
    catalog: ArtifactCatalog,
    store: DataStore,
    *,
    source_id: str,
    name: Optional[str] = None,
    n_trajectories: int = 5,
    mean: float = 0.0,
    stddev: float = 0.01,
    numeric_only: bool = True,
) -> CollectionResult:
    """Create an ensemble collection from one dataset using GaussianNoise."""
    source_artifact = catalog.get(source_id)
    if source_artifact and source_artifact.artifact_type == "collection":
        base_name = name or f"{source_artifact.name}-GaussianNoise-{n_trajectories}"
        child_members = []
        dataset_ids: List[str] = []
        artifact_ids: List[str] = []
        for leaf in leaf_dataset_members(catalog, store, source_artifact.id):
            child = gaussian_noise_collection(
                catalog,
                store,
                source_id=leaf["artifact_id"] or leaf["dataset_id"],
                name=f"{base_name}-{'-'.join(leaf.get('path') or [leaf['label']])}",
                n_trajectories=n_trajectories,
                mean=mean,
                stddev=stddev,
                numeric_only=numeric_only,
            )
            child_members.append({"label": leaf["label"], "artifact_id": child.collection.id, "dataset_ids": child.dataset_ids})
            dataset_ids.extend(child.dataset_ids)
            artifact_ids.extend(child.artifact_ids)
        collection = create_collection(
            catalog,
            name=base_name,
            collection_type="ensemble",
            members=child_members,
            parent_ids=[source_artifact.id],
            metadata={"n_source_members": len(child_members), "n_samples_per_member": n_trajectories},
            provenance={"origin": "mutation", "recipe": "GaussianNoise"},
        )
        mark_collection_members(catalog, store, collection)
        return CollectionResult(collection=collection, dataset_ids=dataset_ids, artifact_ids=artifact_ids)

    source_record = store.get_record(source_id)
    if source_record is None and source_artifact and source_artifact.dataframe_id:
        source_record = store.get_record(source_artifact.dataframe_id)
    if source_record is None:
        raise ValueError(f"Source dataset '{source_id}' not found")
    source_df = source_record.data.to_dataframe()
    transformer = GaussianNoise(
        n_trajectories=n_trajectories,
        mean=mean,
        stddev=stddev,
        numeric_only=numeric_only,
    )
    outputs = transformer.execute({source_record.name: [source_df]})[source_record.name]
    dataset_ids: List[str] = []
    artifact_ids: List[str] = []
    members: List[Dict[str, Any]] = []
    ensemble_name = name or f"{source_record.name}-GaussianNoise-{n_trajectories}"

    for index, synthetic in enumerate(outputs):
        df = synthetic.to_dataframe() if hasattr(synthetic, "to_dataframe") else synthetic
        dataset_id, artifact = create_dataset_artifact(
            catalog,
            store,
            name=f"{ensemble_name}-sample-{index:03d}",
            dataframe=df,
            parent_ids=[source_record.id],
            kind="synthetic",
            role="synthetic_sample",
            attrs={**source_record.attrs, "artifact": "source", "synthetic": True, "sample_index": index},
            transform={"name": "GaussianNoise", "params": dict(transformer.params), "sample_index": index},
            provenance={"origin": "mutation", "recipe": "GaussianNoise"},
        )
        dataset_ids.append(dataset_id)
        artifact_ids.append(artifact.id)
        members.append({"label": f"sample_{index:03d}", "artifact_id": artifact.id, "dataset_id": dataset_id, "sample_index": index})

    collection = create_collection(
        catalog,
        name=ensemble_name,
        collection_type="ensemble",
        members=members,
        parent_ids=[source_record.attrs.get("artifact_ref_id") or source_record.id],
        metadata={"n_samples": n_trajectories, "source_dataset_id": source_record.id},
        provenance={"origin": "mutation", "recipe": "GaussianNoise", "params": dict(transformer.params)},
    )
    mark_collection_members(catalog, store, collection)
    return CollectionResult(collection=collection, dataset_ids=dataset_ids, artifact_ids=artifact_ids)


def split_artifact_or_collection(
    catalog: ArtifactCatalog,
    store: DataStore,
    *,
    source_id: str,
    name: Optional[str] = None,
    method: str = "holdout",
    train_ratio: float = 0.7,
    val_ratio: float = 0.15,
    test_ratio: float = 0.15,
    n_folds: int = 3,
) -> CollectionResult:
    """Split one dataset or every dataset in a collection."""
    source_artifact = catalog.get(source_id)
    source_record = store.get_record(source_id)
    base_name = name or (source_artifact.name if source_artifact else source_record.name if source_record else source_id)

    if source_artifact and source_artifact.artifact_type == "collection":
        child_collections = []
        dataset_ids: List[str] = []
        artifact_ids: List[str] = []
        for leaf in leaf_dataset_members(catalog, store, source_artifact.id):
            child = split_artifact_or_collection(
                catalog,
                store,
                source_id=leaf["artifact_id"] or leaf["dataset_id"],
                name=f"{base_name}-{'-'.join(leaf.get('path') or [leaf['label']])}",
                method=method,
                train_ratio=train_ratio,
                val_ratio=val_ratio,
                test_ratio=test_ratio,
                n_folds=n_folds,
            )
            child_collections.append({"label": leaf["label"], "artifact_id": child.collection.id, "dataset_ids": child.dataset_ids})
            dataset_ids.extend(child.dataset_ids)
            artifact_ids.extend(child.artifact_ids)
        collection = create_collection(
            catalog,
            name=f"{base_name}-{method}",
            collection_type="split_set",
            members=child_collections,
            parent_ids=[source_artifact.id],
            metadata={"method": method, "n_members": len(child_collections)},
            provenance={"origin": "split", "method": method},
        )
        mark_collection_members(catalog, store, collection)
        return CollectionResult(collection=collection, dataset_ids=dataset_ids, artifact_ids=artifact_ids)

    record = source_record
    if source_artifact and source_artifact.dataframe_id:
        record = store.get_record(source_artifact.dataframe_id)
    if record is None:
        raise ValueError(f"Source dataset '{source_id}' not found")
    df = record.data.to_dataframe().reset_index(drop=True)
    splits = _split_dataframe(df, method=method, train_ratio=train_ratio, val_ratio=val_ratio, test_ratio=test_ratio, n_folds=n_folds)
    dataset_ids = []
    artifact_ids = []
    members = []
    for label, split_df in splits:
        split_metadata = _split_label_metadata(label)
        dataset_id, artifact = create_dataset_artifact(
            catalog,
            store,
            name=f"{base_name}-{label}",
            dataframe=split_df,
            parent_ids=[record.id],
            kind="validation",
            role=split_metadata["split"],
            attrs={**record.attrs, "artifact": "source", "split": split_metadata["split"], "fold": split_metadata.get("fold"), "split_label": label, "split_method": method},
            transform={"name": method, "split": split_metadata["split"], "fold": split_metadata.get("fold"), "label": label},
            provenance={"origin": "split", "method": method},
        )
        dataset_ids.append(dataset_id)
        artifact_ids.append(artifact.id)
        members.append({"label": label, "artifact_id": artifact.id, "dataset_id": dataset_id, **split_metadata})
    collection = create_collection(
        catalog,
        name=f"{base_name}-{method}",
        collection_type="split_set",
        members=members,
        parent_ids=[source_artifact.id if source_artifact else record.id],
        metadata={"method": method, "source_dataset_id": record.id, "n_splits": len(members)},
        provenance={"origin": "split", "method": method},
    )
    mark_collection_members(catalog, store, collection)
    return CollectionResult(collection=collection, dataset_ids=dataset_ids, artifact_ids=artifact_ids)


def apply_calculator_to_artifact_or_collection(
    catalog: ArtifactCatalog,
    store: DataStore,
    *,
    source_id: str,
    calculator: Calculator,
    name: Optional[str] = None,
) -> CollectionResult:
    """Apply a calculator recipe to one dataset or all leaves in a collection."""
    artifact = catalog.get(source_id)
    record = store.get_record(source_id)
    base_name = name or (artifact.name if artifact else record.name if record else source_id)

    if artifact and artifact.artifact_type == "collection":
        child_members = []
        dataset_ids: List[str] = []
        artifact_ids: List[str] = []
        for leaf in leaf_dataset_members(catalog, store, artifact.id):
            child_name = f"{base_name}-{'-'.join(leaf.get('path') or [leaf['label']])}"
            child = apply_calculator_to_artifact_or_collection(
                catalog,
                store,
                source_id=leaf["artifact_id"] or leaf["dataset_id"],
                calculator=calculator,
                name=child_name,
            )
            child_members.append({"label": leaf["label"], "artifact_id": child.collection.id, "dataset_ids": child.dataset_ids})
            dataset_ids.extend(child.dataset_ids)
            artifact_ids.extend(child.artifact_ids)
        collection = create_collection(
            catalog,
            name=f"{base_name}-prepared",
            collection_type="prepared_set",
            members=child_members,
            parent_ids=[artifact.id],
            metadata={"recipe": calculator.list_transforms(), "n_members": len(child_members)},
            provenance={"origin": "calculator", "recipe": "Calculator"},
        )
        mark_collection_members(catalog, store, collection)
        return CollectionResult(collection=collection, dataset_ids=dataset_ids, artifact_ids=artifact_ids)

    if artifact and artifact.dataframe_id:
        record = store.get_record(artifact.dataframe_id)
    if record is None:
        raise ValueError(f"Source dataset '{source_id}' not found")
    prepared = calculator.derive_combined(store, record.id)
    df = prepared.to_dataframe() if hasattr(prepared, "to_dataframe") else prepared
    dataset_id, prepared_artifact = create_dataset_artifact(
        catalog,
        store,
        name=base_name,
        dataframe=df,
        parent_ids=[record.id],
        kind="derived",
        role="prepared_data",
        attrs={**record.attrs, "artifact": "prepared_data"},
        transform={"name": "CalculatorPreparation", "transforms": calculator.list_transforms()},
        provenance={"origin": "calculator", "recipe": "Calculator"},
    )
    collection = create_collection(
        catalog,
        name=f"{base_name}-prepared",
        collection_type="prepared_set",
        members=[{"label": prepared_artifact.name, "artifact_id": prepared_artifact.id, "dataset_id": dataset_id}],
        parent_ids=[artifact.id if artifact else record.id],
        metadata={"recipe": calculator.list_transforms(), "n_members": 1},
        provenance={"origin": "calculator", "recipe": "Calculator"},
    )
    mark_collection_members(catalog, store, collection)
    return CollectionResult(collection=collection, dataset_ids=[dataset_id], artifact_ids=[prepared_artifact.id])


def _split_dataframe(
    df: pd.DataFrame,
    *,
    method: str,
    train_ratio: float,
    val_ratio: float,
    test_ratio: float,
    n_folds: int,
) -> List[tuple[str, pd.DataFrame]]:
    method = method.lower()
    if method in {"walk_forward", "walk-forward", "folds"} and n_folds > 1:
        return _walk_forward_splits(df, n_folds=n_folds, val_ratio=val_ratio, test_ratio=test_ratio)
    return _holdout_splits(df, train_ratio=train_ratio, val_ratio=val_ratio, test_ratio=test_ratio)


def _holdout_splits(df: pd.DataFrame, *, train_ratio: float, val_ratio: float, test_ratio: float) -> List[tuple[str, pd.DataFrame]]:
    total = max(train_ratio + val_ratio + test_ratio, 1e-9)
    train_ratio, val_ratio, test_ratio = train_ratio / total, val_ratio / total, test_ratio / total
    n = len(df)
    train_end = int(np.floor(n * train_ratio))
    val_end = int(np.floor(n * (train_ratio + val_ratio)))
    return [
        ("train", df.iloc[:train_end].reset_index(drop=True)),
        ("val", df.iloc[train_end:val_end].reset_index(drop=True)),
        ("test", df.iloc[val_end:].reset_index(drop=True)),
    ]


def _split_label_metadata(label: str) -> Dict[str, Any]:
    parts = label.split("_")
    if len(parts) >= 3 and parts[0] == "fold":
        try:
            fold = int(parts[1])
        except ValueError:
            fold = None
        return {"fold": fold, "split": parts[2]}
    return {"fold": None, "split": label}


def _walk_forward_splits(df: pd.DataFrame, *, n_folds: int, val_ratio: float, test_ratio: float) -> List[tuple[str, pd.DataFrame]]:
    n = len(df)
    if n_folds < 1:
        n_folds = 1
    requested_val_size = max(1, int(np.floor(n * val_ratio)))
    requested_test_size = max(1, int(np.floor(n * test_ratio)))
    max_window = max(1, (n - 1) // n_folds)
    if requested_val_size + requested_test_size > max_window:
        requested_val_size = max(1, max_window // 2)
        requested_test_size = max(1, max_window - requested_val_size)
    val_size = requested_val_size
    test_size = requested_test_size
    future_size = val_size + test_size
    effective_n_folds = min(n_folds, max(1, (n - 1) // future_size))
    validation_cls = COMPONENT_REGISTRY["Validation"]["Time Series K-Fold"]["Internal"]
    validation = validation_cls(
        n_splits=effective_n_folds,
        max_train_size=n,
        test_size=future_size,
        gap=0,
    )
    splits: List[tuple[str, pd.DataFrame]] = []
    for fold, (train_range, future_range) in enumerate(validation.execute(df)):
        train_start, train_end = train_range
        future_start, future_end = future_range
        val_start = future_start
        val_end = min(val_start + val_size - 1, future_end)
        test_start = val_end + 1
        test_end = min(test_start + test_size - 1, future_end)
        splits.append((f"fold_{fold}_train", df.iloc[train_start:train_end + 1].reset_index(drop=True)))
        splits.append((f"fold_{fold}_val", df.iloc[val_start:val_end + 1].reset_index(drop=True)))
        splits.append((f"fold_{fold}_test", df.iloc[test_start:test_end + 1].reset_index(drop=True)))
    return splits
