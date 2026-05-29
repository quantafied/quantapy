import pandas as pd

class AssetDataContainer:
    """Container grouping raw, synthetic, and augmented data for one asset."""

    def __init__(self, name: str):
        """Initialize empty data groups for an asset."""
        self.name = name
        
        self.raw: list[pd.DataFrame] = []
        self.synthetic: list[pd.DataFrame] = []
        self.augmented: list[pd.DataFrame] = []
        
        self.metadata = {}
