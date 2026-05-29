import pandas as pd
import numpy as np
from typing import Optional, List, Dict, Union


class Dataset:
    """Generic dataset container: name + data (array or DataFrame).
    
    No domain assumptions — works with financial data, time series, generic arrays, etc.
    """

    def __init__(self, name: str, data: Union[np.ndarray, pd.DataFrame]):
        """Create a dataset from a NumPy array or DataFrame."""
        self.name = name
        if isinstance(data, np.ndarray):
            self.data = pd.DataFrame(data)
        elif isinstance(data, pd.DataFrame):
            self.data = data.copy()
        else:
            raise TypeError(f"Expected ndarray or DataFrame, got {type(data)}")

    def to_dataframe(self) -> pd.DataFrame:
        """Return a copy of the underlying DataFrame."""
        return self.data.copy()

    def __repr__(self):
        return f"Dataset(name={self.name!r}, shape={self.data.shape})"


class DataStore:
    """Simple registry of named datasets.
    
    Provides basic CRUD and query operations.
    """

    def __init__(self):
        """Initialize an empty dataset registry."""
        self._datasets: Dict[str, Dataset] = {}

    def add(self, name: str, data: Union[np.ndarray, pd.DataFrame, Dataset]):
        """Add a dataset by name."""
        if isinstance(data, Dataset):
            self._datasets[name] = data
        else:
            self._datasets[name] = Dataset(name, data)

    def get(self, name: str) -> Optional[Dataset]:
        """Retrieve a dataset by name."""
        return self._datasets.get(name)

    def to_dataframe(self, name: str) -> pd.DataFrame:
        """Convenience: get a dataset as a DataFrame."""
        ds = self.get(name)
        return ds.to_dataframe() if ds else pd.DataFrame()

    def list(self) -> List[str]:
        """List all dataset names."""
        return list(self._datasets.keys())

    def filter(self, pattern: str) -> List[str]:
        """Filter dataset names by pattern (e.g., "Gaussian" returns all datasets containing "Gaussian")."""
        return [name for name in self._datasets.keys() if pattern in name]

    def available(self) -> Dict[str, tuple]:
        """Return a dict of all datasets with (shape, dtypes)."""
        return {
            name: (ds.data.shape, dict(ds.data.dtypes))
            for name, ds in self._datasets.items()
        }

    def __repr__(self):
        return f"DataStore(datasets={self.list()})"
