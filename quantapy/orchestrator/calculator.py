"""
Calculator v2: Refactored to work with DataStore and support streaming.

Design:
- Works with TimeSeries/DataStore (not raw DataFrames)
- Derives new datasets from existing ones (maintains lineage)
- Supports incremental updates for streaming
- Composable: chain multiple transforms
"""

from typing import Dict, List, Optional, Any
import pandas as pd
import numpy as np
from joblib import Parallel, delayed

from quantapy.registry.component_registry import COMPONENT_REGISTRY
from quantapy.core.timeseries import TimeSeries, DataStore


class Calculator:
    """
    Derives technical indicators and features from TimeSeries data.
    
    Usage:
        # Register transforms
        calc = Calculator()
        calc.add_transform("Technical", "Moving Average", "Internal", 
                          timeperiod=20, real="close", output_names={"output": "sma_20"})
        
        # Derive from DataStore
        store = DataStore()
        store.add("OHLC_AAPL", raw_ts)
        
        derived_ts = calc.derive(store, "OHLC_AAPL", "Moving Average")
        store.add("OHLC_AAPL-SMA20", derived_ts)
        
        # Or derive all transforms at once
        store = calc.derive_all(store, "OHLC_AAPL")
        # Results: OHLC_AAPL-MovingAverage-0, OHLC_AAPL-MovingAverage-1, etc.
    """
    
    def __init__(self):
        """Initialize calculator with empty transform registry."""
        self.transforms: Dict[str, tuple] = {}  # {name: (category, function, source, kwargs)}
    
    def add_transform(self, category: str, function: str, source: str = "Internal", **kwargs) -> None:
        """
        Register a transform (technical indicator, feature engineer, etc.).
        
        Args:
            category: Registry category (e.g., "Technical", "Math")
            function: Transform function name (e.g., "Moving Average", "RSI")
            source: Provider source (default: "Internal")
            **kwargs: Transform-specific parameters (timeperiod, real, output_names, etc.)
        """
        # Get transform class from registry
        try:
            transform_cls = COMPONENT_REGISTRY[category][function][source]
        except KeyError:
            raise ValueError(
                f"Transform not found: {category}/{function}/{source}. "
                f"Available: {COMPONENT_REGISTRY.keys()}"
            )
        
        # Store registry info and instantiate (we'll re-instantiate on derive for fresh params)
        name = kwargs.get("name", f"{function}_{len(self.transforms)}")
        self.transforms[name] = {
            "category": category,
            "function": function,
            "source": source,
            "cls": transform_cls,
            "params": kwargs
        }
        
        print(f"✓ Registered transform '{name}': {category}/{function}")
    
    def remove_transform(self, name: str) -> None:
        """Remove a registered transform."""
        if name in self.transforms:
            del self.transforms[name]
            print(f"✓ Removed transform '{name}'")
        else:
            raise ValueError(f"Transform '{name}' not found")
    
    def derive(
        self, 
        store: DataStore, 
        source_dataset: str, 
        transform_name: str
    ) -> TimeSeries:
        """
        Derive a new TimeSeries by applying a single transform to source data.
        
        Args:
            store: DataStore containing source data
            source_dataset: Name of source dataset in store
            transform_name: Specific transform to apply.
        
        Returns:
            New TimeSeries with source columns + output columns from this transform
            
        Example:
            sma_ts = calc.derive(store, "OHLC_AAPL", "SMA_20")
            # Returns: TimeSeries with [timestamp, open, high, low, close, sma_20]
        """
        source_ts = store.get(source_dataset)
        if source_ts is None:
            raise ValueError(f"Dataset '{source_dataset}' not found in store")
        
        if transform_name not in self.transforms:
            raise ValueError(f"Transform '{transform_name}' not registered")
        
        # Convert to DataFrame for transforms (they expect DataFrames)
        df = source_ts.to_dataframe()
        
        xform_config = self.transforms[transform_name]
        
        # Instantiate transform with stored params
        transform_obj = xform_config["cls"](**xform_config["params"])
        
        # Compute derived columns
        derived_cols = transform_obj.compute(df)
        
        # Add to result DataFrame
        result_df = df.copy()
        for col_name, col_data in derived_cols.items():
            result_df[col_name] = col_data
        
        # Convert back to TimeSeries
        return TimeSeries.from_dataframe(result_df)
    
    def derive_combined(
        self,
        store: DataStore,
        source_dataset: str,
        transform_names: Optional[List[str]] = None
    ) -> TimeSeries:
        """
        Apply multiple transforms to a dataset and return a SINGLE TimeSeries with all columns.
        
        This is the recommended approach: all indicators in one dataset for easy analysis.
        
        Args:
            store: DataStore containing source data
            source_dataset: Name of source dataset in store
            transform_names: List of transforms to apply. If None, apply all registered transforms.
        
        Returns:
            Single TimeSeries with source columns + ALL derived columns combined
            
        Example:
            calc.add_transform("Technical", "Moving Average", ..., name="SMA_20")
            calc.add_transform("Technical", "Relative Strength Index", ..., name="RSI_14")
            calc.add_transform("Technical", "MACD", ..., name="MACD")
            
            # All indicators in ONE dataset
            all_indicators = calc.derive_combined(store, "OHLC_AAPL")
            # Returns: [timestamp, open, high, low, close, sma_20, rsi_14, macd_line, ...]
            
            store.add("OHLC_AAPL-AllIndicators", all_indicators)
        """
        source_ts = store.get(source_dataset)
        if source_ts is None:
            raise ValueError(f"Dataset '{source_dataset}' not found in store")
        
        # Determine which transforms to apply
        if transform_names is None:
            # Apply all registered transforms
            xforms_to_apply = list(self.transforms.items())
        else:
            # Apply specific transforms
            xforms_to_apply = []
            for name in transform_names:
                if name not in self.transforms:
                    raise ValueError(f"Transform '{name}' not registered")
                xforms_to_apply.append((name, self.transforms[name]))
        
        if not xforms_to_apply:
            raise ValueError("No transforms to apply")
        
        # Convert to DataFrame
        result_df = source_ts.to_dataframe()
        
        # Apply each transform and accumulate columns
        for transform_name, xform_config in xforms_to_apply:
            transform_obj = xform_config["cls"](**xform_config["params"])
            derived_cols = transform_obj.compute(result_df)
            
            # Add derived columns to result
            for col_name, col_data in derived_cols.items():
                result_df[col_name] = col_data
        
        # Convert back to TimeSeries
        return TimeSeries.from_dataframe(result_df)
    
    def derive_all(self, store: DataStore, source_dataset: str) -> DataStore:
        """
        Apply all registered transforms to a dataset and store results.
        
        Creates derived datasets named like "source_dataset-TransformName".
        Useful for batch processing during strategy development.
        
        Args:
            store: DataStore
            source_dataset: Source dataset name
        
        Returns:
            Updated DataStore with derived datasets added
        """
        for transform_name in self.transforms.keys():
            derived_ts = self.derive(store, source_dataset, transform_name)
            derived_name = f"{source_dataset}-{transform_name}"
            store.add_child(
                derived_name,
                derived_ts,
                parent_ids=[source_dataset],
                kind="derived",
                transform={
                    "name": transform_name,
                    "config": self.transforms[transform_name],
                },
            )
        
        return store
    
    def derive_batch(self, store: DataStore, dataset_names: List[str], n_jobs: int = -1) -> DataStore:
        """
        Apply all transforms to multiple datasets in parallel.
        
        Args:
            store: DataStore
            dataset_names: List of source dataset names
            n_jobs: Joblib parallelization (-1 = all cores)
        
        Returns:
            Updated DataStore
        """
        def _derive_one(ds_name):
            return ds_name, self.derive(store, ds_name)
        
        results = Parallel(n_jobs=n_jobs)(
            delayed(_derive_one)(name) for name in dataset_names
        )
        
        for source_name, derived_ts in results:
            for transform_name in self.transforms.keys():
                store.add_child(
                    f"{source_name}-{transform_name}",
                    derived_ts,
                    parent_ids=[source_name],
                    kind="derived",
                    transform={
                        "name": transform_name,
                        "config": self.transforms[transform_name],
                    },
                )
        
        return store
    
    def derive_streaming(
        self, 
        store: DataStore, 
        source_dataset: str, 
        new_rows: TimeSeries,
        transform_name: Optional[str] = None
    ) -> TimeSeries:
        """
        Incrementally derive data when new rows arrive (streaming scenario).
        
        This is more efficient than recomputing from scratch: only the new rows
        are transformed, then appended to existing derived data.
        
        Args:
            store: DataStore
            source_dataset: Source dataset name (must be updated in store before calling)
            new_rows: New rows that were appended to source_dataset
            transform_name: Specific transform. If None, apply all.
        
        Returns:
            TimeSeries with only the new derived rows (caller appends to existing derived_ts)
        
        Example:
            # Historical data processed
            store.add("OHLC", historical_ts)
            derived = calc.derive(store, "OHLC", "SMA")
            store.add("OHLC-SMA", derived)
            
            # New data arrives (e.g., live market data)
            new_data = TimeSeries.from_dict_list([...])
            
            # Update source and derive new rows
            source_ts = store.get("OHLC").append(new_data)
            store.add("OHLC", source_ts)
            
            new_derived = calc.derive_streaming(store, "OHLC", new_data, "SMA")
            
            derived_ts = store.get("OHLC-SMA").append(new_derived)
            store.add("OHLC-SMA", derived_ts)
        """
        # Only compute on new rows
        df_new = new_rows.to_dataframe()
        
        xforms_to_apply = []
        if transform_name:
            if transform_name not in self.transforms:
                raise ValueError(f"Transform '{transform_name}' not registered")
            xforms_to_apply = [(transform_name, self.transforms[transform_name])]
        else:
            xforms_to_apply = list(self.transforms.items())
        
        # Apply transforms only to new rows
        result_df = df_new.copy()
        for name, xform_config in xforms_to_apply:
            transform_obj = xform_config["cls"](**xform_config["params"])
            derived_cols = transform_obj.compute(result_df)
            for col_name, col_data in derived_cols.items():
                result_df[col_name] = col_data
        
        return TimeSeries.from_dataframe(result_df)
    
    def get_config(self, transform_name: str) -> Dict[str, Any]:
        """Get the config schema for a transform (for UI forms)."""
        if transform_name not in self.transforms:
            raise ValueError(f"Transform '{transform_name}' not found")
        
        transform_cls = self.transforms[transform_name]["cls"]
        # Instantiate with current params to get updated schema
        xform_obj = transform_cls(**self.transforms[transform_name]["params"])
        return xform_obj.get_config()
    
    def set_config(self, transform_name: str, new_params: Dict[str, Any]) -> None:
        """Update parameters for a transform."""
        if transform_name not in self.transforms:
            raise ValueError(f"Transform '{transform_name}' not found")
        
        self.transforms[transform_name]["params"].update(new_params)
        print(f"✓ Updated config for '{transform_name}'")
    
    def list_transforms(self) -> Dict[str, Dict[str, Any]]:
        """List all registered transforms with their parameters."""
        return {
            name: {
                "category": config["category"],
                "function": config["function"],
                "params": config["params"]
            }
            for name, config in self.transforms.items()
        }
