from quantapy.core.base_data import BaseData
from quantapy.registry.component_registry import register_component
import pandas as pd
import numpy as np
from typing import List

@register_component(category="Math", function="Difference", source="Internal")
class diff(BaseData):
    """Difference transform for a numeric DataFrame column."""
    
    def diff(data: pd.DataFrame, array: str = 'close', n_diff: int = 1, output_names: list = ["diff"]):
        """Return the n-th discrete difference for a named column."""
        output = np.diff(data[array], n_diff)
        return {f"{output_names[0]}": output}
