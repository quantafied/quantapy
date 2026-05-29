import talib
from quantapy.core.base_transform import BaseTransform
from quantapy.registry.component_registry import register_component
import pandas as pd
import numpy as np
from typing import List,Union,Type,Any
import random
import inspect
from talib import abstract

def random_hex_color():
    """Generates a random hexidecimal color"""
    
    return "#{:06x}".format(random.randint(0, 0xFFFFFF))

@register_component(category="Technical", function="Moving Average", source="Internal")
class sma(BaseTransform):
    """Simple moving average transform backed by TA-Lib."""
    
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
        """Compute an SMA column from the configured input column and period."""
    
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
        """Compute an RSI column from the configured input column and period."""
        real_col = self.params["real"]
        period = self.params["timeperiod"]
        output_names = self.params["output_names"]

        result = talib.RSI(df[real_col], period)
        return {output_names["output"]: result}
    

def _talib_display(function_name: str) -> str:
    """Return a readable display name for a TA-Lib function."""
    return abstract.Function(function_name).info.get("display_name", function_name)


def _talib_display_mode(function_name: str) -> str:
    """Return the default chart display mode for a TA-Lib function."""
    group = abstract.Function(function_name).info.get("group", "")
    return "Overlay" if group == "Overlap Studies" else "Indicator"


def _talib_param_schema(name: str, default: Any) -> dict:
    """Build a JSON-schema field for a TA-Lib parameter."""
    if isinstance(default, int):
        field = {
            "type": "integer",
            "default": default,
            "description": name,
            "advanced": False,
        }
        if "period" in name:
            field["optimizable"] = {"min": 2, "max": 200}
        if "matype" in name:
            field["enum"] = list(range(9))
            field["widget_type"] = "select"
        return field

    return {
        "type": "number",
        "default": default,
        "description": name,
        "advanced": False,
    }


def _talib_config(function_name: str) -> dict:
    """Generate a BaseTransform-compatible config for a TA-Lib function."""
    func = abstract.Function(function_name)
    properties = {
        "name": {
            "type": "string",
            "default": function_name,
            "description": "Name of the transformation",
            "advanced": False,
        }
    }

    for input_name, default in func.input_names.items():
        if isinstance(default, list):
            for column in default:
                properties[column] = {
                    "type": "string",
                    "default": column,
                    "description": f"{column} input column",
                    "use_variable_options": True,
                    "widget_type": "select",
                    "advanced": False,
                }
        else:
            properties[input_name] = {
                "type": "string",
                "default": default,
                "description": f"{input_name} input column",
                "use_variable_options": True,
                "widget_type": "select",
                "advanced": False,
            }

    for param_name, default in func.parameters.items():
        properties[param_name] = _talib_param_schema(param_name, default)

    output_properties = {}
    for output_name in func.output_names:
        default_name = (
            function_name.lower()
            if len(func.output_names) == 1
            else f"{function_name.lower()}_{output_name}"
        )
        output_properties[output_name] = {"type": "string", "default": default_name}

    properties["output_names"] = {
        "type": "object",
        "title": "Output Names",
        "description": "Names of outputs",
        "properties": output_properties,
    }
    properties["display"] = {
        "type": "string",
        "default": _talib_display_mode(function_name),
        "description": "Location to render outputs",
        "enum": ["Overlay", "Indicator"],
        "widget_type": "select",
        "advanced": False,
    }

    return {
        "title": _talib_display(function_name),
        "type": "object",
        "properties": properties,
    }


def _talib_args(function_name: str, df: pd.DataFrame, params: dict) -> list:
    """Build positional TA-Lib inputs from configured DataFrame columns."""
    func = abstract.Function(function_name)
    args = []
    for input_name, default in func.input_names.items():
        if isinstance(default, list):
            for column in default:
                args.append(df[params[column]])
        else:
            args.append(df[params[input_name]])
    return args


def _talib_kwargs(function_name: str, params: dict) -> dict:
    """Build keyword TA-Lib parameters from configured transform params."""
    func = abstract.Function(function_name)
    return {
        param_name: params[param_name]
        for param_name in func.parameters.keys()
    }


def _make_talib_transform(function_name: str):
    """Create a BaseTransform wrapper class for one TA-Lib function."""

    class TALibTransform(BaseTransform):
        """Auto-generated TA-Lib transform wrapper."""

        config = _talib_config(function_name)

        def compute(self, df: pd.DataFrame):
            """Compute configured TA-Lib outputs."""
            result = getattr(talib, function_name)(
                *_talib_args(function_name, df, self.params),
                **_talib_kwargs(function_name, self.params),
            )
            output_names = self.params["output_names"]
            output_keys = abstract.Function(function_name).output_names

            if len(output_keys) == 1:
                return {output_names[output_keys[0]]: result}

            return {
                output_names[output_key]: output_value
                for output_key, output_value in zip(output_keys, result)
            }

    TALibTransform.__name__ = function_name.lower()
    TALibTransform.__qualname__ = function_name.lower()
    TALibTransform.__doc__ = f"Auto-generated wrapper for TA-Lib {function_name}."
    return TALibTransform


for _talib_function in talib.get_functions():
    _talib_transform = _make_talib_transform(_talib_function)
    register_component(
        category="Technical",
        function=_talib_function,
        source="TA-Lib",
    )(_talib_transform)
    register_component(
        category="Technical",
        function=_talib_function,
        source="Internal",
    )(_talib_transform)

    
