"""
Generic data orchestrator supporting batch and streaming workflows.

Design principles:
- Domain-agnostic: works with financial data, time series, sensor data, etc.
- Columnar: TimeSeries uses NumPy arrays for efficiency
- Composable: providers → fetch, transformers → transform, explicit store commit
- Streaming-ready: designed to support append operations and streaming sinks
"""
from typing import Dict, Any, Optional, List, Union
import pandas as pd
import numpy as np

from quantapy.registry.component_registry import COMPONENT_REGISTRY
from quantapy.core.timeseries import TimeSeries


class Data:
    """
    Generic data orchestrator for batch and streaming workflows.
    
    Supports:
    - add_provider(): register data sources (FMP, CSV, database, Kafka, etc.)
    - add_transformer(): register transformations (synthetic, indicators, normalization, etc.)
    - fetch(): execute all providers and return named outputs
    - transform(): apply transformations and return named outputs
    - ingest(): wrap manually supplied data as a named output
    - stream(): (future) subscribe to streaming data sources
    
    Example (financial):
        data = Data()
        data.add_provider("Market", "OHLC", "FMP", source_ids=["AAPL", "GOOGL"], date_range="2020-2024")
        data.add_transformer("Augmentation", "GaussianNoise", "Internal", n_trajectories=10, stddev=0.01)
        fetched = data.fetch()
        synthetic = data.transform("OHLC_AAPL", fetched["OHLC_AAPL"])
    
    Example (time series):
        data = Data()
        data.add_provider("Sensors", "Temperature", "CSV", path="/data/temps.csv")
        data.add_transformer("Analysis", "Normalize", "Internal")
        fetched = data.fetch()
        normalized = data.transform("Temperature", fetched["Temperature"])
    """

    def __init__(self):
        """Initialize provider and transformer registries."""
        self.providers = []
        self.transformers = []

    def add_provider(self, category: str, name: str, source: str, **kwargs) -> None:
        """
        Register a data provider.
        
        Args:
            category: Provider category (e.g., "Market", "Sensors", "Weather")
            name: Provider name (e.g., "OHLC", "Temperature", "Precipitation")
            source: Provider source/implementation (e.g., "FMP", "CSV", "Kafka")
            **kwargs: Provider-specific parameters (source_ids, date_range, path, etc.)
        """
        cls = COMPONENT_REGISTRY[category][name][source]
        self.providers.append((name, cls(**kwargs)))

    def add_transformer(self, category: str, name: str, source: str, **kwargs) -> None:
        """
        Register a transformer/synthesizer.
        
        Args:
            category: Transformer category (e.g., "Augmentation", "Analysis", "Feature")
            name: Transformer name (e.g., "GaussianNoise", "Normalize", "MovingAverage")
            source: Transformer source/implementation (e.g., "Internal", "TensorFlow")
            **kwargs: Transformer-specific parameters (n_trajectories, stddev, window_size, etc.)
        """
        cls = COMPONENT_REGISTRY[category][name][source]
        self.transformers.append((name, cls(**kwargs)))

    def fetch(self) -> Dict[str, Any]:
        """
        Execute all registered providers and return named outputs.
        
        Providers are expected to return:
        - Dict[source_id, List[Dict]]
        - Dict[source_id, TimeSeries]
        - Dict[source_id, DataFrame]
        
        Returns:
            Dict mapping dataset names to provider outputs.
        """
        outputs = {}

        for provider_name, provider_obj in self.providers:
            result = provider_obj.execute()

            if isinstance(result, dict):
                for source_id, data in result.items():
                    dataset_name = f"{provider_name}_{source_id}"
                    outputs[dataset_name] = data
            else:
                # Single dataset result
                outputs[provider_name] = result

        return outputs

    def transform(
        self,
        dataset_name: str,
        data: Union[TimeSeries, np.ndarray, pd.DataFrame, List[Dict]],
        transformer_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Apply transformer(s) to a dataset and return named outputs.
        
        Transformers are expected to:
        - Accept Dict[dataset_name, List[TimeSeries]] via execute()
        - Return Dict[dataset_name, List[TimeSeries]] with transformed data
        
        Multiple trajectories (e.g., 10 synthetic versions) are indexed: 
        "dataset-Transformer-0", "dataset-Transformer-1", etc.
        
        Args:
            dataset_name: Name to use for the source dataset.
            data: Source data to transform.
            transformer_name: Specific transformer to apply. If None, apply all.
        
        Returns:
            Dict mapping output names to transformed outputs.
        """
        ts = TimeSeries.from_dataframe(data) if isinstance(data, pd.DataFrame) else data
        outputs_by_name = {}

        # select transformers to apply
        xforms_to_apply = [
            t for t in self.transformers
            if transformer_name is None or t[0] == transformer_name
        ]

        for xform_name, xform_obj in xforms_to_apply:
            # Execute transformer
            # Transformers work with TimeSeries or DataFrames
            try:
                # Try TimeSeries-aware interface first
                result = xform_obj.execute({dataset_name: [ts]})
            except (TypeError, AttributeError):
                # Fall back to DataFrame-based interface
                try:
                    result = xform_obj.execute({dataset_name: [ts.to_dataframe()]})
                except TypeError as e:
                    raise TypeError(
                        f"Transformer {xform_name} signature mismatch. "
                        f"Expected execute(dict[name, list[data]]), got error: {e}"
                    )

            # Store results
            if isinstance(result, dict) and dataset_name in result:
                outputs = result[dataset_name]
                if isinstance(outputs, list):
                    for i, output in enumerate(outputs):
                        # Generate output name with index if multiple trajectories
                        output_name = (
                            f"{dataset_name}-{xform_name}-{i}"
                            if len(outputs) > 1
                            else f"{dataset_name}-{xform_name}"
                        )
                        outputs_by_name[output_name] = output
                else:
                    # Single output
                    outputs_by_name[f"{dataset_name}-{xform_name}"] = outputs

        return outputs_by_name

    def ingest(
        self, name: str, data: Union[TimeSeries, np.ndarray, pd.DataFrame, List[Dict]]
    ) -> Dict[str, Union[TimeSeries, np.ndarray, pd.DataFrame, List[Dict]]]:
        """
        Return manually supplied data as a named output.
        
        Accepts:
        - TimeSeries: stored directly
        - NumPy array: converted to TimeSeries with auto-generated column names
        - DataFrame: converted to TimeSeries
        - List of dicts: converted to TimeSeries
        
        Args:
            name: Dataset name.
            data: Data in any supported format.
        
        Returns:
            Dict mapping the supplied name to data.
        """
        return {name: data}
