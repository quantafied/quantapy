#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat Jun 14 21:59:20 2025

@author: andrewsimin
"""

from abc import ABC, abstractmethod
from tradinglib.core.base_component import BaseComponentConfig
import pandas as pd
from typing import List,Union,Type
from pydantic import BaseModel,Field
from typing import Any, Dict, Union


class BaseOrder(ABC):
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
        self.params = {
            k: merged.get(k, v.get("default"))
            for k, v in props.items()
        }
        
        # Add variable selection options
        self.params["variable_options"] = variable_options

    @abstractmethod
    def execute(self):
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