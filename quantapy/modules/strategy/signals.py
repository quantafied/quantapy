#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Jun  9 23:10:01 2025

@author: andrewsimin
"""

import talib
from tradinglib.core.base_signal import BaseSignal
from tradinglib.registry.component_registry import register_component
from tradinglib.core.base_component import BaseComponentConfig
from tradinglib.core.base_signal import BaseSignal
import pandas as pd
from pydantic import BaseModel,Field
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
        
        value1 = self.params["value1"]
        value2 = self.params["value2"]
        action = self.params["action"]
        direction = self.params["direction"]
    
        #crossunder = (df[value1].shift(1) > df[value2].shift(1)) & (df[value1] <= df[value2])
        crossunder = (df[value1].iloc[index-1] > df[value2].iloc[index-1]) and (df[value1].iloc[index] <= df[value2].iloc[index])
        
        return crossunder, action, direction
    
class GreaterThanVariableConfig(BaseComponentConfig):
    """ Configuration schema for cross"""
    
    value1: str = Field(
        default="close",
        description="First variable",
        json_schema_extra={"advanced": False,
                           "options": ["vars_as_options"], 
                           "widget_type": "selectbox",
                           }
    )
    
    value2: str = Field(
        default="close",
        description="Second variable",
        json_schema_extra={"advanced": False,
                           "options": ["vars_as_options"], 
                           "widget_type": "selectbox",
                           }
    )
    
    action: str = Field(
        default="",
        description="Action",
        json_schema_extra={"advanced": False,
                           "options": ["enter", "exit"], 
                           "widget_type": "selectbox",
                           }
    )
    
    direction: str = Field(
        default="",
        description="Direction",
        json_schema_extra={"advanced": False,
                           "options": ["long", "short"], 
                           "widget_type": "selectbox",
                           }
    )
    
@register_component(category="Signal", function="Greater Than Variable", source="Internal")
class greaterthanvariable(BaseSignal):
    
    """Crossunder signal"""
    
    config_class = GreaterThanVariableConfig
    
    def check(self, df: pd.DataFrame, index: int = 0, value1: str = "close", value2: str = "close"):
        
        value1 = self.config.value1
        value2 = self.config.value2
        action = self.config.action
        direction = self.config.direction
        #index = self.config.index
    
        greaterthan = df[value1].iloc[index] > df[value2].iloc[index]
        
        return greaterthan, action, direction
    
class LessThanVariableConfig(BaseComponentConfig):
    """ Configuration schema for cross"""
    
    value1: str = Field(
        default="close",
        description="First variable",
        json_schema_extra={"advanced": False,
                           "options": ["vars_as_options"], 
                           "widget_type": "selectbox",
                           }
    )
    
    value2: str = Field(
        default="close",
        description="Second variable",
        json_schema_extra={"advanced": False,
                           "options": ["vars_as_options"], 
                           "widget_type": "selectbox",
                           }
    )
    
    action: str = Field(
        default="",
        description="Action",
        json_schema_extra={"advanced": False,
                           "options": ["enter", "exit"], 
                           "widget_type": "selectbox",
                           }
    )
    
    direction: str = Field(
        default="",
        description="Direction",
        json_schema_extra={"advanced": False,
                           "options": ["long", "short"], 
                           "widget_type": "selectbox",
                           }
    )
    
@register_component(category="Signal", function="Less Than Variable", source="Internal")
class lessthanvariable(BaseSignal):
    
    """Crossunder signal"""
    
    config_class = LessThanVariableConfig
    
    def check(self, df: pd.DataFrame, index: int = 0, value1: str = "close", value2: str = "close"):
        
        value1 = self.config.value1
        value2 = self.config.value2
        action = self.config.action
        direction = self.config.direction
        #index = self.config.index
    
        lessthan = df[value1].iloc[index] < df[value2].iloc[index]
        
        return lessthan, action, direction
    
class GreaterThanThresholdConfig(BaseComponentConfig):
    """ Configuration schema for cross"""
    
    value1: str = Field(
        default="close",
        description="First variable",
        json_schema_extra={"advanced": False,
                           "options": ["vars_as_options"], 
                           "widget_type": "selectbox",
                           }
    )
    
    value2: int = Field(
        default=1,
        description="Threshold",
        json_schema_extra={"advanced": False,
                           "optimizable": (1,100),
                           }
    )
    
    action: str = Field(
        default="",
        description="Action",
        json_schema_extra={"advanced": False,
                           "options": ["enter", "exit"], 
                           "widget_type": "selectbox",
                           }
    )
    
    direction: str = Field(
        default="",
        description="Direction",
        json_schema_extra={"advanced": False,
                           "options": ["long", "short"], 
                           "widget_type": "selectbox",
                           }
    )
    
    optimizable: dict = Field(
        default={"value2":[5,100],
                 })
    
@register_component(category="Signal", function="Greater Than Threshold", source="Internal")
class greaterthanthreshold(BaseSignal):
    
    """Crossunder signal"""
    
    config_class = GreaterThanThresholdConfig
    
    def check(self, df: pd.DataFrame, index: int = 0, value1: str = "close", value2: str = "close"):
        
        value1 = self.config.value1
        value2 = self.config.value2
        action = self.config.action
        direction = self.config.direction
        #index = self.config.index
    
        greaterthan = df[value1].iloc[index] > value2
        
        return greaterthan, action, direction
    
class LessThanThresholdConfig(BaseComponentConfig):
    """ Configuration schema for cross"""
    
    value1: str = Field(
        default="close",
        description="Real value",
        json_schema_extra={"options": ["vars_as_options"], 
                           "widget_type": "selectbox",
                           "advanced": False,
                           }
    )

    
    value2: int = Field(
        default=1,
        description="Threshold",
        json_schema_extra={"advanced": False,
                           "optimizable": (1,100),
                           }
    )
    
    action: str = Field(
        default="",
        description="Action",
        json_schema_extra={"advanced": False,
                           "options": ["enter", "exit"], 
                           "widget_type": "selectbox",
                           }
    )
    
    direction: str = Field(
        default="",
        description="Direction",
        json_schema_extra={"advanced": False,
                           "options": ["long", "short"], 
                           "widget_type": "selectbox",
                           }
    )
    
    optimizable: dict = Field(
        default={"value2":[5,100],
                 })
    
    
@register_component(category="Signal", function="Less Than Threshold", source="Internal")
class lessthanthreshold(BaseSignal):
    
    """Crossunder signal"""
    
    config_class = LessThanThresholdConfig
    
    def check(self, df: pd.DataFrame, index: int = 0, value1: str = "close", value2: str = "close"):
        
        value1 = self.config.value1
        value2 = self.config.value2
        action = self.config.action
        direction = self.config.direction
        #index = self.config.index
    
        lessthan = df[value1].iloc[index] < value2
        
        return lessthan, action, direction
    
