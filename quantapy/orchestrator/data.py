from quantapy.registry.component_registry import COMPONENT_REGISTRY
from quantapy.utils.loader import load_plugins_from_folder
from typing import Dict, Any
import pandas as pd


class Data:
    """
    Orchestrator class for managing and fetching market and synthetic data.

    The Data class is responsible for:
    - Registering raw data components (e.g. OHLC, order book data)
    - Registering synthetic or augmented data generators
    - Executing data pipelines and returning structured results

    Data components are dynamically loaded from the COMPONENT_REGISTRY
    and instantiated based on category, name, and source.
    """

    def __init__(self) -> None:
        """
        Initialize the Data orchestrator.

        Attributes:
            data_objects (dict): Mapping of data name to raw data component instances.
            synthetic_data_objects (dict): Mapping of synthetic data name to generator instances.
            data (dict): Nested dictionary storing fetched raw and synthetic data outputs.
        """
        self.data_objects: Dict[str, Any] = {}
        self.synthetic_data_objects: Dict[str, Any] = {}
        self.data: Dict[str, Dict[str, pd.DataFrame]] = {}

    def add(self, category: str, name: str, source: str, **kwargs) -> None:
        """
        Add a raw data component to the data pipeline.

        Args:
            category (str): Component category (e.g. "historical", "market").
            name (str): Component name (e.g. "OHLC").
            source (str): Data source identifier (e.g. "Internal", "FMP").
            **kwargs: Keyword arguments passed to the component constructor.

        Raises:
            KeyError: If the specified component is not found in the registry.
        """
        transform_class = COMPONENT_REGISTRY[category][name][source]
        data_instance = transform_class(**kwargs)
        self.data_objects[name] = data_instance

    def add_synthetic(self, category: str, name: str, source: str, **kwargs) -> None:
        """
        Add a synthetic or augmented data generator.

        Synthetic data generators are applied to raw data outputs
        if the raw data component is marked as synthesizable.

        Args:
            category (str): Component category.
            name (str): Synthetic data name (e.g. "GaussianNoise").
            source (str): Synthetic data source identifier.
            **kwargs: Keyword arguments passed to the component constructor.
        """
        transform_class = COMPONENT_REGISTRY[category][name][source]
        synthetic_instance = transform_class(**kwargs)
        self.synthetic_data_objects[name] = synthetic_instance

    def fetch_data(self) -> Dict[str, Dict[str, pd.DataFrame]]:
        """
        Execute all registered data components and return fetched data.

        For each raw data component:
        - Fetch raw data via `execute()`
        - Optionally apply all registered synthetic generators

        Returns:
            dict: Nested dictionary structured as:
                {
                    "<data_name>": {
                        "Raw": pd.DataFrame,
                        "<synthetic_name>": pd.DataFrame
                    }
                }
        """
        for data_name, data_object in self.data_objects.items():
            self.data[data_name] = {}

            raw_data = data_object.execute()
            self.data[data_name]["Raw"] = raw_data

            if getattr(data_object, "synthesizable", False):
                for synthetic_name, synthetic_object in self.synthetic_data_objects.items():
                    synthetic_data = synthetic_object.execute(raw_data)
                    self.data[data_name][synthetic_name] = synthetic_data

        return self.data
