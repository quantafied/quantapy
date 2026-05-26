from abc import ABC, abstractmethod
import pandas as pd
from typing import List, Union, Type, Any, Dict, Union

class BaseData(ABC):
    """
    Simple hybrid base for transforms that can:
    - Accept JSON config from frontend (React)
    - Or be called directly with kwargs in Python
    """

    # Each subclass defines a JSON-schema-like config dict
    config: Dict[str, Any] = {}

    def __init__(self, config: Union[Dict[str, Any], None] = None, variable_options=None, **kwargs):
        """
        Supports initialization from:
        - JSON config (React) with or without 'config_values'
        - Direct Python kwargs
        """
        # Load class-level schema
        schema = self.__class__.config.copy()
        props = schema.get("properties", {})

        # Normalize frontend payload
        if config and "config_values" in config:
            config_values = config["config_values"]
        else:
            config_values = config or {}

        # Merge JSON + kwargs (kwargs override)
        merged = {**config_values, **kwargs}

        # Build simple parameter dict (defaults overwritten by user input)
        #self.params = {
        #    k: merged.get(k, v.get("default"))
        #    for k, v in props.items()
        #}

        self.params = {}

        for k, v in props.items():
            default = v.get("default")

            if config and "config_values" in config:
                self.params[k] = config["config_values"].get(k, default)
            elif config:
                self.params[k] = config.get(k, default)
            else:
                self.params[k] = merged.get(k, default)

        # Include any direct kwargs or merged config values not declared in the schema
        for k, v in merged.items():
            if k not in self.params:
                self.params[k] = v

        # Add variable selection options
        self.params["variable_options"] = variable_options
        

    @abstractmethod
    def execute(self,*args,**kwargs):
        """Subclasses must implement."""
        pass

    def get_config(self) -> Dict[str, Any]:
        """
        Return the config schema with dynamic defaults AND dynamic enum options.
        """
        import copy
        schema = copy.deepcopy(self.__class__.config)
        props = schema.get("properties", {})
    
        variable_options = self.params.get("variable_options", [])
    
        for key, prop in props.items():
            # Update defaults
            if key in self.params:
                prop["default"] = self.params[key]
    
            # Inject variable_options dynamically if marked
            if prop.get("use_variable_options", False):
                prop["enum"] = variable_options
                prop["widget_type"] = prop.get("widget_type", "select")
    
        schema["properties"] = props
        return schema

    def set_config(self, new_config: Dict[str, Any]):
        """Update params (from frontend submission or backend call)."""
        for k, v in new_config.items():
            if k in self.params:
                self.params[k] = v
    
