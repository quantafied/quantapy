#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Jun  9 23:10:01 2025

@author: andrewsimin
"""

import talib
from quantapy.core.base_signal import BaseSignal
from quantapy.registry.component_registry import register_component
from quantapy.core.base_signal import BaseSignal
import pandas as pd
import numpy as np
from typing import List,Union,Type
import random

@register_component(category="Signal", function="Crossover", source="Internal")
class crossover(BaseSignal):
    """Class to compute bollinger bands indicator"""
    
    config = {
      "title": "Crossover Signal",
      "type": "object",
      "properties": {
        "name": {
          "type": "string",
          "default": "Crossover",
          "description": "Name of the signal",
          "advanced": False
        },
        "value1": {
          "type": "string",
          "default": "close",
          "description": "First variable",
          "use_variable_options": True, # Enums generated dynamically in base_class with get_config method
          "widget_type": "select",
          "advanced": False
        },
        "value2": {
          "type": "string",
          "default": "close",
          "description": "Second variable",
          "use_variable_options": True,
          "widget_type": "select",
          "advanced": False
        },
        "action": {
          "type": "string",
          "default": "enter",
          "description": "Action to perform on signal",
          "enum": ["enter", "exit"],
          "widget_type": "select",
          "advanced": False
        },
        "direction": {
          "type": "string",
          "default": "long",
          "description": "Order side direction",
          "enum": ["long", "short"],
          "widget_type": "select",
          "advanced": False
        },
      }
    }
    
    def check(self, df: pd.DataFrame, index: int = 0, value1: str = "close", value2: str = "close"):
        """Return whether value1 crosses above value2 at the given row index."""
        
        value1 = self.params["value1"]
        value2 = self.params["value2"]
        action = self.params["action"]
        direction = self.params["direction"]
        #index = self.config.index
    
        #crossover = (df[value1].shift(1) < df[value2].shift(1)) & (df[value1] >= df[value2])
        crossover = (df[value1].iloc[index-1] < df[value2].iloc[index-1]) and (df[value1].iloc[index] >= df[value2].iloc[index])
        
        return crossover, action, direction
        
@register_component(category="Signal", function="Crossunder", source="Internal")
class crossunder(BaseSignal):
    
    """Crossunder signal"""
    
    config = {
      "title": "Crossunder Signal",
      "type": "object",
      "properties": {
        "name": {
          "type": "string",
          "default": "Crossunder",
          "description": "Name of the signal",
          "advanced": False
        },
        "value1": {
          "type": "string",
          "default": "close",
          "description": "First variable",
          "use_variable_options": True, 
          "widget_type": "select",
          "advanced": False
        },
        "value2": {
          "type": "string",
          "default": "close",
          "description": "Second variable",
          "use_variable_options": True,
          "widget_type": "select",
          "advanced": False
        },
        "action": {
          "type": "string",
          "default": "enter",
          "description": "Action to perform on signal",
          "enum": ["enter", "exit"],
          "widget_type": "select",
          "advanced": False
        },
        "direction": {
          "type": "string",
          "default": "long",
          "description": "Order side direction",
          "enum": ["long", "short"],
          "widget_type": "select",
          "advanced": False
        },
      }
    }
    
    def check(self, df: pd.DataFrame, index: int = 0, value1: str = "close", value2: str = "close"):
        """Return whether value1 crosses below value2 at the given row index."""
        
        value1 = self.params["value1"]
        value2 = self.params["value2"]
        action = self.params["action"]
        direction = self.params["direction"]
    
        #crossunder = (df[value1].shift(1) > df[value2].shift(1)) & (df[value1] <= df[value2])
        crossunder = (df[value1].iloc[index-1] > df[value2].iloc[index-1]) and (df[value1].iloc[index] <= df[value2].iloc[index])
        
        return crossunder, action, direction
    
    
