#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat May 24 11:45:20 2025

@author: andrewsimin
"""

from tradinglib.core.base_data import BaseData
from tradinglib.registry.component_registry import register_component
from tradinglib.core.base_component import BaseComponentConfig
import pandas as pd
from pydantic import BaseModel,Field
import numpy as np
from typing import List

class CustomDiffConfig(BaseComponentConfig):
    array: str = Field("close", description="Array")
    n_diff: int = Field(1, description="number of differences", json_schema_extra={"optimizable": (5,100)})
    output_names: List[str] = Field(default_factory=list, json_schema_extra={"options": ["diff"], "widget_type": "text"})

@register_component(category="Custom", function="Custom Difference", source="Internal")
class Customdiff(BaseData):
    
    def __init__(self, config: CustomDiffConfig):
        
        super().__init__(config)
        
    def diff(data: pd.DataFrame, array: str = 'close', n_diff: int = 1, output_names: list = ["diff"]):
        output = np.diff(data[array], n_diff)
        return {f"{output_names[0]}": output}