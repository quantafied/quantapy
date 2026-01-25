#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat Jun 14 17:31:29 2025

@author: andrewsimin
"""

import talib
from tradinglib.core.base_order import BaseOrder
from tradinglib.registry.component_registry import register_component
from tradinglib.core.base_component import BaseComponentConfig
import pandas as pd
from pydantic import BaseModel,Field
import numpy as np
from typing import List,Union,Type,Optional
import random
    
@register_component(category="Order", function="Market", source="Internal")
class market(BaseOrder):
    """Class to compute bollinger bands indicator"""
    
    config = {
      "title": "Market Order",
      "type": "object",
      "properties": {
        "on_signal": {
          "type": "string",
          "default": "entry",
          "description": "Execute order on signal side",
          "enum": ["entry", "exit"],
          "widget_type": "select",
          "advanced": False
        },
        "on_price": {
          "type": "string",
          "default": "close",
          "description": "Fill price",
          "enum": ["open", "close", "high", "low"],
          "widget_type": "select",
          "advanced": False
        },
        "on_bar": {
          "type": "string",
          "default": "current",
          "description": "Placement of order",
          "enum": ["previous", "current", "next"],
          "widget_type": "select",
          "advanced": False
        },
      }
    }
        
    def execute(self, df: pd.DataFrame, index: int, signal: str) -> Optional[float]:
        """
        Called from Strategy loop. Executes order if signal matches and returns price.
        """
        on_signal = self.params["on_signal"]
        on_price = self.params["on_price"]
        on_bar = self.params["on_bar"]

        # Determine bar offset
        if on_bar == "previous":
            target_index = index - 1
        elif on_bar == "current":
            target_index = index
        elif on_bar == "next":
            target_index = index + 1
        else:
            target_index = index

        # Ensure target index is in bounds
        if 0 <= target_index < len(df):
            return df.loc[target_index, on_price]
        else:
            return None
    
