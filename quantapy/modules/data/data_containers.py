import pandas as pd

class AssetDataContainer:
    def __init__(self, name: str):
        self.name = name
        
        self.raw: list[pd.DataFrame] = []
        self.synthetic: list[pd.DataFrame] = []
        self.augmented: list[pd.DataFrame] = []
        
        self.metadata = {}
