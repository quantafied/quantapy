import talib
from quantapy.core.base_transform import BaseTransform
from quantapy.registry.component_registry import register_component
import pandas as pd
import numpy as np
from typing import List,Union,Type,Any
import random
import inspect

def random_hex_color():
    """Generates a random hexidecimal color"""
    
    return "#{:06x}".format(random.randint(0, 0xFFFFFF))

@register_component(category="Technical", function="Moving Average", source="Internal")
class sma(BaseTransform):
    
    config = {
        "title": "Simple Moving Average",
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "default": "SMA",
                "description": "Name of the transformation",
                "advanced": False
            },
            "real": {
                "type": "string",
                "default": "close",
                "description": "Price column to average",
                "enum": ["close", "open", "high", "low"],
                "widget_type": "select",
                "advanced": False
            },
            "timeperiod": {
                "type": "integer",
                "default": 20,
                "description": "Period for moving average",
                "advanced": False,
                "optimizable": {"min": 2, "max": 200}
            },
            "output_names": {
                "type": "object",
                "title": "Output Names",
                "properties": {
                    "output": {"type": "string", "default": "sma"}
                }
            },
            "display": {
                "type": "string",
                "default": "Overlay",
                "description": "Display type",
                "enum": ["Overlay", "Indicator"],
                "widget_type": "select",
                "advanced": False
            },
        }
    }
    
    def compute(self, df: pd.DataFrame):
    
        real_col = self.params["real"]
        period = self.params["timeperiod"]
        output_names = self.params["output_names"]

        result = talib.SMA(df[real_col], period)
        return {output_names["output"]: result}

@register_component(category="Technical", function="Relative Strength Index", source="Internal")
class rsi(BaseTransform):
    """Class to compute Relative Strength Index (RSI) indicator"""
    
    config = {
        "title": "Relative Strength Index",
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "default": "RSI",
                "description": "Name of the transformation",
                "advanced": False
            },
            "real": {
                "type": "string",
                "default": "close",
                "description": "Real value",
                "enum": ["close", "open", "high", "low"],
                "widget_type": "select",
                "advanced": False
            },
            "timeperiod": {
                "type": "integer",
                "default": 14,
                "description": "Time period",
                "advanced": False,
                "optimizable": {"min": 5, "max": 100}
            },
            "output_names": {
                "type": "object",
                "title": "Output Names",
                "description": "Names of outputs",
                "properties": {
                    "output": {"type": "string", "default": "rsi"}
                }
            },
            "optimizable": {
                "type": "object",
                "title": "Optimizable fields",
                "description": "Toggle which parameters are optimizable",
                "properties": {
                    "timeperiod": {"type": "boolean", "default": True}
                }
            },
            "display": {
                "type": "string",
                "default": "Indicator",
                "description": "Location to render outputs",
                "enum": ["Overlay", "Indicator"],
                "widget_type": "select",
                "advanced": False
            },
        }
    }
    
    def compute(self, df: pd.DataFrame):
        real_col = self.params["real"]
        period = self.params["timeperiod"]
        output_names = self.params["output_names"]

        result = talib.RSI(df[real_col], period)
        return {output_names["output"]: result}
    

    

