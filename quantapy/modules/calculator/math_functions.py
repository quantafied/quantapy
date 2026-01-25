from tradinglib.core.base_data import BaseData
from tradinglib.registry.component_registry import register_component
from tradinglib.core.base_component import BaseComponentConfig
import pandas as pd
from pydantic import BaseModel,Field
import numpy as np
from typing import List

class DiffConfig(BaseComponentConfig):
    array: str = Field("close", description="Array")
    n_diff: int = Field(1, description="number of differences", json_schema_extra={"optimizable": (5,100)})
    output_names: List[str] = Field(default_factory=list, json_schema_extra={"options": ["diff"], "widget_type": "text"})

@register_component(category="Math", function="Difference", source="Internal")
class diff(BaseData):
    
    def __init__(self, config: DiffConfig):
        
        super().__init__(config)
        
    def diff(data: pd.DataFrame, array: str = 'close', n_diff: int = 1, output_names: list = ["diff"]):
        output = np.diff(data[array], n_diff)
        return {f"{output_names[0]}": output}