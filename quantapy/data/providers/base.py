"""
Base classes and interfaces for generic providers and transformers.

Providers fetch data from external sources (APIs, files, streams).
Transformers process data (synthesis, normalization, feature engineering, etc.).

All work with TimeSeries for efficiency and consistency.
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Union
import pandas as pd
import numpy as np

from quantapy.core.timeseries import TimeSeries


class BaseProvider(ABC):
    """
    Abstract base class for all data providers.
    
    Providers fetch data from external sources and return it as TimeSeries.
    
    Example:
        class CSVProvider(BaseProvider):
            def __init__(self, paths: Dict[str, str]):
                self.paths = paths  # {source_id: file_path}
            
            def execute(self) -> Dict[str, TimeSeries]:
                result = {}
                for source_id, path in self.paths.items():
                    df = pd.read_csv(path)
                    result[source_id] = TimeSeries.from_dataframe(df)
                return result
    """
    
    def __init__(self, **kwargs):
        """Initialize provider with parameters."""
        self.params = kwargs
    
    @abstractmethod
    def execute(self) -> Dict[str, Any]:
        """
        Fetch and return data.
        
        Returns:
            Dict mapping source_id to data (TimeSeries, DataFrame, list[dict], or numpy array).
            The Data orchestrator will convert these to TimeSeries.
            
            E.g., {"AAPL": TimeSeries(...), "GOOGL": TimeSeries(...)}
        """
        pass
    
    def validate(self) -> bool:
        """
        Validate provider parameters before execution.
        
        Override in subclass to add parameter validation.
        Returns True if valid, False otherwise.
        """
        return True


class BaseTransformer(ABC):
    """
    Abstract base class for all transformers/synthesizers.
    
    Transformers process data, potentially producing multiple trajectories
    (e.g., 10 synthetic versions of a time series).
    
    Example:
        class GaussianNoiseTransformer(BaseTransformer):
            def __init__(self, n_trajectories: int = 5, stddev: float = 0.01):
                super().__init__(n_trajectories=n_trajectories, stddev=stddev)
            
            def execute(self, data_dict: Dict[str, List[TimeSeries]]) -> Dict[str, List[TimeSeries]]:
                result = {}
                for name, ts_list in data_dict.items():
                    trajectories = []
                    for ts in ts_list:
                        df = ts.to_dataframe()
                        for _ in range(self.params['n_trajectories']):
                            noisy_df = df.copy()
                            noisy_df = noisy_df + np.random.normal(0, self.params['stddev'], df.shape)
                            trajectories.append(TimeSeries.from_dataframe(noisy_df))
                    result[name] = trajectories
                return result
    """
    
    def __init__(self, **kwargs):
        """Initialize transformer with parameters."""
        self.params = kwargs
    
    @abstractmethod
    def execute(self, data_dict: Dict[str, List[Any]]) -> Dict[str, List[Any]]:
        """
        Transform data, potentially generating multiple trajectories.
        
        Args:
            data_dict: Dict mapping dataset_name to List of data items.
                      Each item can be TimeSeries, DataFrame, or raw array.
                      Usually contains a single item from the Data orchestrator.
        
        Returns:
            Dict mapping dataset_name to List of transformed data items.
            Output list length can differ from input (e.g., 1 input → 10 synthetic outputs).
            
            E.g., input:  {"data": [TimeSeries]}
                 output: {"data": [TimeSeries, TimeSeries, ..., TimeSeries]}  # 10 items
        """
        pass
    
    def validate(self) -> bool:
        """
        Validate transformer parameters before execution.
        
        Override in subclass to add parameter validation.
        Returns True if valid, False otherwise.
        """
        return True
