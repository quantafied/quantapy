"""
Columnar time series data structure with schema.

Designed for efficiency and streaming support:
- NumPy-backed arrays (no DataFrame overhead until needed)
- Schema awareness (column types, metadata)
- Append-friendly (for streaming ingestion)
- Lazy DataFrame materialization
"""
from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional, Union, Any
from uuid import uuid4
import numpy as np
import pandas as pd


class TimeSeries:
    """
    Columnar time series data with schema.
    
    Stores data as separate numpy arrays per column, with schema metadata.
    Designed for memory efficiency and streaming append operations.
    """
    
    def __init__(self, schema: Dict[str, str], data: Dict[str, np.ndarray]):
        """
        Initialize TimeSeries with schema and data.
        
        Args:
            schema: {column_name: dtype_str} e.g., {"timestamp": "int64", "value": "float64"}
            data: {column_name: numpy_array}
        """
        self.schema = schema
        self.data = {k: np.asarray(v) for k, v in data.items()}
        self._validate()
    
    def _validate(self):
        """Ensure data matches schema and is internally consistent."""
        if set(self.data.keys()) != set(self.schema.keys()):
            raise ValueError("Data columns must exactly match schema keys")
        
        # Check all arrays have same length
        if self.data:
            lengths = [len(arr) for arr in self.data.values()]
            if len(set(lengths)) > 1:
                raise ValueError(f"All arrays must have same length, got {set(lengths)}")
    
    @property
    def shape(self) -> Tuple[int, int]:
        """Return (num_rows, num_cols)."""
        if not self.data:
            return (0, 0)
        num_rows = len(next(iter(self.data.values())))
        num_cols = len(self.data)
        return (num_rows, num_cols)
    
    @property
    def columns(self) -> List[str]:
        """Return column names (in schema order)."""
        return list(self.schema.keys())
    
    @property
    def num_rows(self) -> int:
        """Number of rows."""
        return self.shape[0]
    
    @property
    def num_cols(self) -> int:
        """Number of columns."""
        return self.shape[1]
    
    def to_dataframe(self) -> pd.DataFrame:
        """Materialize to pandas DataFrame."""
        if not self.data:
            return pd.DataFrame()
        return pd.DataFrame(self.data)
    
    def get_column(self, col: str) -> np.ndarray:
        """Get a single column array."""
        if col not in self.data:
            raise KeyError(f"Column '{col}' not found in schema: {self.columns}")
        return self.data[col]
    
    def slice(self, start: int, end: int) -> 'TimeSeries':
        """Return a slice (rows start:end) as new TimeSeries."""
        new_data = {
            col: self.data[col][start:end]
            for col in self.schema.keys()
        }
        return TimeSeries(self.schema.copy(), new_data)
    
    def append(self, other: 'TimeSeries') -> 'TimeSeries':
        """
        Append another TimeSeries to this one (returns new instance).
        """
        if self.schema != other.schema:
            raise ValueError(
                f"Cannot append: schema mismatch.\n"
                f"  Self: {self.schema}\n"
                f"  Other: {other.schema}"
            )
        
        new_data = {
            col: np.concatenate([self.data[col], other.data[col]])
            for col in self.schema.keys()
        }
        return TimeSeries(self.schema.copy(), new_data)
    
    def copy(self) -> 'TimeSeries':
        """Return a deep copy."""
        return TimeSeries(
            self.schema.copy(),
            {col: arr.copy() for col, arr in self.data.items()}
        )
    
    @staticmethod
    def from_dataframe(df: pd.DataFrame) -> 'TimeSeries':
        """Create TimeSeries from pandas DataFrame."""
        if df.empty:
            raise ValueError("Cannot create TimeSeries from empty DataFrame")
        
        schema = {col: str(df[col].dtype) for col in df.columns}
        data = {col: df[col].values for col in df.columns}
        return TimeSeries(schema, data)
    
    @staticmethod
    def from_dict_list(records: List[Dict[str, Any]]) -> 'TimeSeries':
        """
        Create TimeSeries from list of dicts (common provider output format).
        
        E.g., [{"timestamp": 1, "value": 1.5}, {"timestamp": 2, "value": 2.1}]
        """
        if not records:
            raise ValueError("Cannot create TimeSeries from empty records list")
        
        # Extract columns
        data_dict = {k: [] for k in records[0].keys()}
        for rec in records:
            for k, v in rec.items():
                data_dict[k].append(v)
        
        # Convert to numpy arrays, infer dtypes
        data = {}
        inferred_schema = {}
        for col, values in data_dict.items():
            arr = np.array(values)
            data[col] = arr
            inferred_schema[col] = str(arr.dtype)
        
        return TimeSeries(inferred_schema, data)
    
    @staticmethod
    def from_numpy(arr: np.ndarray, columns: Optional[List[str]] = None) -> 'TimeSeries':
        """
        Create TimeSeries from numpy array.
        
        Args:
            arr: 2D numpy array (rows x columns)
            columns: column names (auto-generated if None)
        """
        if arr.ndim == 1:
            arr = arr.reshape(-1, 1)
        elif arr.ndim != 2:
            raise ValueError(f"Expected 2D array, got shape {arr.shape}")
        
        if columns is None:
            columns = [f"col_{i}" for i in range(arr.shape[1])]
        
        if len(columns) != arr.shape[1]:
            raise ValueError(f"Expected {arr.shape[1]} columns, got {len(columns)}")
        
        schema = {col: str(arr.dtype) for col in columns}
        data = {columns[i]: arr[:, i] for i in range(arr.shape[1])}
        return TimeSeries(schema, data)


@dataclass
class DatasetRecord:
    """Metadata wrapper for a stored TimeSeries."""

    id: str
    name: str
    data: TimeSeries
    kind: str = "unknown"
    parent_ids: List[str] = field(default_factory=list)
    transform: Optional[Dict[str, Any]] = None
    source: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    stale: bool = False


class DataStore:
    """
    Registry of named TimeSeries datasets.
    
    Supports:
    - Adding TimeSeries, DataFrames, numpy arrays, or raw dicts
    - Querying by name, listing, filtering
    - Metadata inspection (shape, columns, dtypes)
    """
    
    def __init__(self):
        self._records: Dict[str, DatasetRecord] = {}
        self._name_to_id: Dict[str, str] = {}

    @property
    def _datasets(self) -> Dict[str, TimeSeries]:
        """Backward-compatible view of datasets by name."""
        return {record.name: record.data for record in self._records.values()}

    def _resolve_id(self, id_or_name: str) -> Optional[str]:
        if id_or_name in self._records:
            return id_or_name
        return self._name_to_id.get(id_or_name)

    def _coerce_timeseries(
        self,
        data: Union[TimeSeries, np.ndarray, pd.DataFrame, List[Dict]]
    ) -> TimeSeries:
        if isinstance(data, TimeSeries):
            return data
        if isinstance(data, pd.DataFrame):
            return TimeSeries.from_dataframe(data)
        if isinstance(data, np.ndarray):
            return TimeSeries.from_numpy(data)
        if isinstance(data, list) and data and isinstance(data[0], dict):
            return TimeSeries.from_dict_list(data)
        raise TypeError(
            f"Unsupported data type: {type(data)}. "
            f"Expected TimeSeries, DataFrame, numpy array, or list of dicts."
        )
    
    def add(
        self, 
        name: str, 
        data: Union[TimeSeries, np.ndarray, pd.DataFrame, List[Dict]],
        *,
        kind: str = "unknown",
        parent_ids: Optional[List[str]] = None,
        transform: Optional[Dict[str, Any]] = None,
        source: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
        stale: bool = False,
        dataset_id: Optional[str] = None,
    ) -> str:
        """
        Add data to store, auto-converting to TimeSeries if needed.
        
        Args:
            name: dataset name (used for lookups)
            data: TimeSeries, DataFrame, 2D numpy array, or list of dicts
        """
        ts = self._coerce_timeseries(data)
        existing_id = self._resolve_id(name)
        record_id = dataset_id or existing_id or str(uuid4())
        old_record = self._records.get(record_id)
        if old_record is not None:
            if kind == "unknown":
                kind = old_record.kind
            if parent_ids is None:
                parent_ids = old_record.parent_ids
            if transform is None:
                transform = old_record.transform
            if source is None:
                source = old_record.source
            if tags is None:
                tags = old_record.tags
        resolved_parent_ids = [
            self._resolve_id(parent) or parent
            for parent in (parent_ids or [])
        ]

        if old_record and old_record.name != name:
            self._name_to_id.pop(old_record.name, None)

        self._records[record_id] = DatasetRecord(
            id=record_id,
            name=name,
            data=ts,
            kind=kind,
            parent_ids=resolved_parent_ids,
            transform=transform,
            source=source or {},
            tags=tags or [],
            stale=stale,
        )
        self._name_to_id[name] = record_id
        return record_id

    def add_raw(
        self,
        name: str,
        data: Union[TimeSeries, np.ndarray, pd.DataFrame, List[Dict]],
        **metadata
    ) -> str:
        """Add a root dataset."""
        return self.add(name, data, kind="raw", **metadata)

    def add_child(
        self,
        name: str,
        data: Union[TimeSeries, np.ndarray, pd.DataFrame, List[Dict]],
        parent_ids: List[str],
        kind: str = "derived",
        **metadata
    ) -> str:
        """Add a dataset derived from one or more parent datasets."""
        return self.add(name, data, kind=kind, parent_ids=parent_ids, **metadata)
    
    def get(self, name: str) -> Optional[TimeSeries]:
        """Get TimeSeries by name."""
        record = self.get_record(name)
        return record.data if record else None

    def get_record(self, id_or_name: str) -> Optional[DatasetRecord]:
        """Get a dataset record by id or name."""
        record_id = self._resolve_id(id_or_name)
        return self._records.get(record_id) if record_id else None
    
    def to_dataframe(self, name: str) -> Optional[pd.DataFrame]:
        """Get TimeSeries as DataFrame."""
        ts = self.get(name)
        return ts.to_dataframe() if ts else None
    
    def list(self) -> List[str]:
        """List all dataset names."""
        return [record.name for record in self._records.values()]

    def records(self) -> List[DatasetRecord]:
        """List all dataset records."""
        return list(self._records.values())

    def by_kind(self, kind: str) -> List[DatasetRecord]:
        """Return records matching a dataset kind."""
        return [record for record in self._records.values() if record.kind == kind]

    def raw(self) -> List[DatasetRecord]:
        """Return raw/root datasets."""
        return self.by_kind("raw")

    def synthetic(self) -> List[DatasetRecord]:
        """Return synthetic datasets."""
        return self.by_kind("synthetic")

    def derived(self) -> List[DatasetRecord]:
        """Return derived datasets."""
        return self.by_kind("derived")

    def children(self, id_or_name: str) -> List[DatasetRecord]:
        """Return direct children for a dataset."""
        record_id = self._resolve_id(id_or_name)
        if record_id is None:
            return []
        return [
            record for record in self._records.values()
            if record_id in record.parent_ids
        ]

    def parents(self, id_or_name: str) -> List[DatasetRecord]:
        """Return direct parents for a dataset."""
        record = self.get_record(id_or_name)
        if record is None:
            return []
        return [
            self._records[parent_id]
            for parent_id in record.parent_ids
            if parent_id in self._records
        ]

    def lineage(self, id_or_name: str) -> Dict[str, Any]:
        """Return a small lineage tree for GUI inspection."""
        record = self.get_record(id_or_name)
        if record is None:
            return {}
        return {
            "id": record.id,
            "name": record.name,
            "kind": record.kind,
            "parents": [parent.name for parent in self.parents(record.id)],
            "children": [child.name for child in self.children(record.id)],
        }
    
    def filter(self, pattern: str) -> List[str]:
        """
        Filter datasets by name pattern (regex).
        
        E.g., store.filter(".*-gaussian.*") returns all Gaussian-transformed datasets.
        """
        import re
        try:
            regex = re.compile(pattern)
            return [record.name for record in self._records.values() if regex.search(record.name)]
        except re.error as e:
            raise ValueError(f"Invalid regex pattern '{pattern}': {e}")
    
    def available(self) -> Dict[str, Dict[str, Any]]:
        """
        Return metadata for all datasets.
        
        Returns:
            {dataset_name: {shape, columns, dtype, num_rows, num_cols}}
        """
        return {
            name: {
                "id": record.id,
                "kind": record.kind,
                "parent_ids": record.parent_ids,
                "children": [child.id for child in self.children(record.id)],
                "stale": record.stale,
                "shape": record.data.shape,
                "num_rows": record.data.num_rows,
                "num_cols": record.data.num_cols,
                "columns": record.data.columns,
                "dtypes": record.data.schema,
            }
            for name, record in ((record.name, record) for record in self._records.values())
        }
    
    def remove(self, name: str, cascade: bool = False) -> bool:
        """Remove a dataset. Returns True if removed, False if not found."""
        record_id = self._resolve_id(name)
        if record_id is None:
            return False

        child_ids = [child.id for child in self.children(record_id)]
        if child_ids and not cascade:
            child_names = [self._records[child_id].name for child_id in child_ids]
            raise ValueError(
                f"Dataset has children: {child_names}. "
                "Pass cascade=True to remove them too."
            )

        for child_id in child_ids:
            self.remove(child_id, cascade=True)

        record = self._records.pop(record_id)
        self._name_to_id.pop(record.name, None)
        for other in self._records.values():
            if record_id in other.parent_ids:
                other.parent_ids = [pid for pid in other.parent_ids if pid != record_id]
                other.stale = True
        return True

    def mark_stale(self, id_or_name: str, recursive: bool = True) -> None:
        """Mark a dataset and optionally all descendants as stale."""
        record = self.get_record(id_or_name)
        if record is None:
            return
        record.stale = True
        if recursive:
            for child in self.children(record.id):
                self.mark_stale(child.id, recursive=True)

    def rename(self, id_or_name: str, new_name: str) -> None:
        """Rename a dataset without changing its stable id or lineage."""
        record = self.get_record(id_or_name)
        if record is None:
            raise ValueError(f"Dataset '{id_or_name}' not found")
        self._name_to_id.pop(record.name, None)
        record.name = new_name
        self._name_to_id[new_name] = record.id
    
    def clear(self) -> None:
        """Remove all datasets."""
        self._records.clear()
        self._name_to_id.clear()
