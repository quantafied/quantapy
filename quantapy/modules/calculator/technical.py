# app/ta_functions.py


import talib
from tradinglib.core.base_transform import BaseTransform
from tradinglib.registry.component_registry import register_component
from tradinglib.core.base_component import BaseComponentConfig
import pandas as pd
from pydantic import BaseModel,Field
import numpy as np
from typing import List,Union,Type
import random

import inspect
from pydantic import Field, create_model
from typing import Any, Type

def function_to_schemas(func, schema_name=None, extras: dict | None = None, base_class=None) -> Type[BaseModel]:
    """
    Convert a function signature into a Pydantic schema.
    - func: the user-defined function
    - extras: optional UI metadata per field
    - base_class: optional Pydantic base (e.g. BaseComponentConfig)
    """
    sig = inspect.signature(func)
    fields = {}
    for name, param in sig.parameters.items():
        ann = param.annotation if param.annotation != inspect.Parameter.empty else Any
        default = param.default if param.default != inspect.Parameter.empty else ...
        json_schema_extra = extras.get(name, {}) if extras else {}
        fields[name] = (ann, Field(default=default, json_schema_extra=json_schema_extra))
    return create_model(
        schema_name or f"{func.__name__.capitalize()}Config",
        __base__=base_class or BaseModel,
        **fields
    )

def function_to_schema(func, schema_name=None, extras=None, base_class=None):
    sig = inspect.signature(func)
    fields = {}
    for name, param in sig.parameters.items():
        ann = param.annotation if param.annotation != inspect.Parameter.empty else Any
        default = param.default if param.default != inspect.Parameter.empty else ...
        extra = (extras or {}).get(name, {})

        # 👇 Default color/thickness for arrays if not explicitly set
        if ann == list[str] and name == "output_names":
            extra.setdefault("widget_type", "text")
            extra.setdefault("color", [random_hex_color()])
            extra.setdefault("thickness", [10])

        fields[name] = (ann, Field(default=default, json_schema_extra=extra))
    return create_model(
        schema_name or f"{func.__name__.capitalize()}Config",
        __base__=base_class or BaseComponentConfig,
        **fields
    )


"""
json_schema_exra:

    advanced: Will display the parameter and any of its additional attributes 
    in an advanced dropdown container
"""

def random_hex_color():
    """Generates a random hexidecimal color"""
    
    return "#{:06x}".format(random.randint(0, 0xFFFFFF))

class BbandsConfig(BaseComponentConfig):
    """ Configuration schema for Bollinger Bands technical indicator"""
    
    name: str = Field(
        default="BBANDS",
        description="Name of the transformation",
        json_schema_extra={"advanced": False,
                           }
    )
    
    real: str = Field(
        default="close",
        description="Real value",
        json_schema_extra={"options": ["vars_as_options"],
                           "widget_type": "selectbox",
                           "advanced": False,
                           }
    )
    
    timeperiod: int = Field(
        default = 5, 
        description="timeperiod", 
        json_schema_extra={"advanced": False,
                           "optimizable": (5,100),
                           }
    )
    
    nbdevup: int = Field(
        default=2, 
        description="nbdevup", 
        json_schema_extra={"advanced": False,
                           "optimizable": (5,100),
                           }
    )
    
    nbdevdn: int = Field(
        default=2, 
        description="nbdevdn", 
        json_schema_extra={"advanced": False,
                           "optimizable": (5,100),
                           }
    )
    
    matype: int = Field(
        default=0, 
        description="matype", 
        json_schema_extra={"advanced": False,
                           "optimizable": (0,3),
                           }
    )
    
    output_names: List[str] = Field(
        default=["upperband", "middleband", "lowerband"], 
        json_schema_extra={"advanced": False,
                           "options": ["upperband", "middleband", "lowerband"], 
                           "widget_type": "text",
                           "color": [random_hex_color(),
                                     random_hex_color(),
                                     random_hex_color()
                                     ],
                           "thickness": [10,10,10]
                           }
    )
    
    plot_type: List[str] = Field(
        default_factory=list, 
        json_schema_extra={"options": ["overlay", "indicator", "seperate"], 
                           "widget_type": "selectbox"
                           }
    )
    
    optimizable: dict = Field(
        default={"timeperiod":[5,100],
                 "nbdevup":[5,100],
                 "nbdevdn":[5,100],
                 "matype":[0,3]
                 })
    
@register_component(category="Technical", function="Bollinger Bands", source="Internal")
class bbands(BaseTransform):
    """Class to compute bollinger bands indicator"""
    
    config_class = BbandsConfig
    
    def compute(
        self, 
        df: pd.DataFrame, 
        real: str = 'close', 
        timeperiod: int = 5, 
        nbdevup: int = 2, 
        nbdevdn: int = 2, 
        matype: int = 0, 
        output_names: list = ["upperband","middleband","lowerband"]
        ):
        
        upperband, middleband, lowerband = talib.BBANDS(
            df[self.config.real], 
            self.config.timeperiod, 
            self.config.nbdevup, 
            self.config.nbdevdn, 
            self.config.matype
            )
        
        return {f"{self.config.output_names[0]}": upperband, 
                f"{self.config.output_names[1]}": middleband, 
                f"{self.config.output_names[2]}": lowerband
                }
"""
class SmaConfig(BaseComponentConfig):
    
    name: str = Field(
        default="SMA"
    )
    
    real: str = Field(
        default="close",
        description="Real value",
        json_schema_extra={"options": ["vars_as_options"], 
                           "widget_type": "selectbox",
                           "advanced": False,
                           }
    )
    
    timeperiod: int = Field(
        default=5, 
        description="timeperiod", 
        json_schema_extra={"optimizable": (5,100)}
    )
    
    output_names: List[str] = Field(
        default=["sma"], 
        json_schema_extra={"options": ["sma"], 
                           "widget_type": "text", 
                           "color":[random_hex_color()], 
                           "thickness":[10]
                           }
    )
    
    plot_type: List[str] = Field(
        default_factory=list, 
        json_schema_extra={"options": ["overlay", "indicator", "seperate"], 
                           "widget_type": "selectbox"
                           }
    )
    
    optimizable: dict = Field(
        default={"timeperiod":[5,100],
                 })

@register_component(category="Technical", function="Moving Average", source="Internal")
class sma(BaseTransform):
    
    config_class = SmaConfig  # Exposed for Streamlit or other tools
    
    def compute(self, df: pd.DataFrame):
        output = talib.SMA(df[self.config.real], self.config.timeperiod)
        return {f"{self.config.output_names[0]}": output}
"""

@register_component(category="Technical", function="Moving Average", source="Internal")
class sma(BaseTransform):
    """Class to compute Simple Moving Average indicator"""
    
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
      "enum": ["close", "open", "high", "low"],
      "description": "Real value",
      "widget_type": "select",
      "advanced": False
    },
    "timeperiod": {
      "type": "integer",
      "default": 5,
      "description": "Time period",
      "advanced": False
    },
    "output_names": {
      "type": "object",
      "title": "Output Names",
      "properties": {
        "output": { "type": "string", "default": "sma" }
      }
    },
    "optimizable": {
      "type": "object",
      "title": "Optimizable fields",
      "properties": {
        "timeperiod": {
          "type": "boolean",
          "default": True,
          "description": "Whether to optimize timeperiod"
        },
        "timeperiod_min": {
          "type": "integer",
          "default": 5
        },
        "timeperiod_max": {
          "type": "integer",
          "default": 100
        }
      }
    },
    "display": {
      "type": "string",
      "default": "Overlay",
      "enum": ["Overlay", "Indicator"],
      "widget_type": "select",
      "advanced": False
    }
  },

  "allOf": [
    {
      "if": {
        "properties": {
          "optimizable": {
            "properties": {
              "timeperiod": { "const": True }
            }
          }
        }
      },
      "then": {
        "properties": {
          "optimizable": {
            "properties": {
              "timeperiod_min": { "type": "integer" },
              "timeperiod_max": { "type": "integer" }
            },
            "required": ["timeperiod_min", "timeperiod_max"]
          }
        }
      },
      "else": {
        "properties": {
          "optimizable": {
            "properties": {
              "timeperiod_min": False,
              "timeperiod_max": False
            }
          }
        }
      }
    }
  ]
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
    
class AdoscConfig(BaseComponentConfig):
    """ Configuration schema for Simple Moving Average technical indicator"""
    
    name: str = Field(
        default="ADOSC"
    )
    
    high: str = Field(
        default="high",
        description="High value",
        json_schema_extra={"options": ["vars_as_options"], 
                           "widget_type": "selectbox",
                           "advanced": False,
                           }
    )
    
    low: str = Field(
        default="low",
        description="Low value",
        json_schema_extra={"options": ["vars_as_options"], 
                           "widget_type": "selectbox",
                           "advanced": False,
                           }
    )
    
    close: str = Field(
        default="close",
        description="Close value",
        json_schema_extra={"options": ["vars_as_options"], 
                           "widget_type": "selectbox",
                           "advanced": False,
                           }
    )
    
    volume: str = Field(
        default="volume",
        description="Volume value",
        json_schema_extra={"options": ["vars_as_options"], 
                           "widget_type": "selectbox",
                           "advanced": False,
                           }
    )
    
    fastperiod: int = Field(
        default=3, 
        description="fastperiod", 
        json_schema_extra={"optimizable": (5,100)}
    )
    
    slowperiod: int = Field(
        default=10, 
        description="slowperiod", 
        json_schema_extra={"optimizable": (5,100)}
    )
    
    output_names: List[str] = Field(
        default=["adosc"], 
        json_schema_extra={"options": ["adosc"], 
                           "widget_type": "text", 
                           "color":[random_hex_color()], 
                           "thickness":[10]
                           }
    )
    
    plot_type: List[str] = Field(
        default_factory=list, 
        json_schema_extra={"options": ["overlay", "indicator", "seperate"], 
                           "widget_type": "selectbox"
                           }
    )
    
#    optimizable: dict = Field(
#        default={"timeperiod":[5,100],
#                 })

@register_component(category="Technical", function="Chaikin A/D Oscillator", source="Internal")
class adosc(BaseTransform):
    """Class to compute Simple Moving Average indicator"""
    
    config_class = AdoscConfig  # Exposed for Streamlit or other tools
    
    def compute(self, df: pd.DataFrame, high: str = 'high', low: str = 'low', close: str = 'close', volume: str = 'volume', fastperiod: int = 3, slowperiod: int = 10):
        output = talib.ADOSC(df[self.config.high], df[self.config.low], df[self.config.close], df[self.config.volume], self.config.fastperiod, self.config.slowperiod)
        return {f"{self.config.output_names[0]}": output}
    
class AdxConfig(BaseComponentConfig):
    """ Configuration schema for Simple Moving Average technical indicator"""
    
    name: str = Field(
        default="ADX"
    )
    
    high: str = Field(
        default="high",
        description="High value",
        json_schema_extra={"options": ["vars_as_options"], 
                           "widget_type": "selectbox",
                           "advanced": False,
                           }
    )
    
    low: str = Field(
        default="low",
        description="Low value",
        json_schema_extra={"options": ["vars_as_options"], 
                           "widget_type": "selectbox",
                           "advanced": False,
                           }
    )
    
    close: str = Field(
        default="close",
        description="Close value",
        json_schema_extra={"options": ["vars_as_options"], 
                           "widget_type": "selectbox",
                           "advanced": False,
                           }
    )
    
    timeperiod: int = Field(
        default=14, 
        description="fastperiod", 
        json_schema_extra={"optimizable": (5,100)}
    )
    
    output_names: List[str] = Field(
        default=["adx"], 
        json_schema_extra={"options": ["adx"], 
                           "widget_type": "text", 
                           "color":[random_hex_color()], 
                           "thickness":[10]
                           }
    )
    
    plot_type: List[str] = Field(
        default_factory=list, 
        json_schema_extra={"options": ["overlay", "indicator", "seperate"], 
                           "widget_type": "selectbox"
                           }
    )
    
#    optimizable: dict = Field(
#        default={"timeperiod":[5,100],
#                 })

@register_component(category="Technical", function="Average Directional Movement Index", source="Internal")
class adx(BaseTransform):
    """Class to compute Simple Moving Average indicator"""
    
    config_class = AdxConfig  # Exposed for Streamlit or other tools
    
    def compute(self, df: pd.DataFrame):
        output = talib.ADX(df[self.config.high], df[self.config.low], df[self.config.close], self.config.timeperiod)
        return {f"{self.config.output_names[0]}": output}
    

