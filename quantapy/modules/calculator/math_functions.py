from quantapy.core.base_data import BaseData
from quantapy.registry.component_registry import register_component
import pandas as pd
import numpy as np
from typing import List

@register_component(category="Math", function="Difference", source="Internal")
class diff(BaseData):
    
    def diff(data: pd.DataFrame, array: str = 'close', n_diff: int = 1, output_names: list = ["diff"]):
        output = np.diff(data[array], n_diff)
        return {f"{output_names[0]}": output}
