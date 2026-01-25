#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon May 19 20:02:51 2025

@author: andrewsimin
"""

from abc import ABC, abstractmethod
import pandas as pd
from typing import Any, Dict, Union


class BaseTransform(ABC):
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
        def deep_defaults(schema_node):
            if "default" in schema_node:
                return schema_node["default"]
            if schema_node.get("type") == "object":
                return {k: deep_defaults(v) for k, v in schema_node.get("properties", {}).items()}
            return None
        
        def deep_merge(defaults, incoming):
            if not isinstance(defaults, dict) or not isinstance(incoming, dict):
                return incoming if incoming is not None else defaults
            out = defaults.copy()
            for k, v in incoming.items():
                out[k] = deep_merge(defaults.get(k), v)
            return out
        
        self.params = {}
        for key, schema_node in props.items():
            defaults = deep_defaults(schema_node)  # recursively build defaults
            value = merged.get(key, None)
            self.params[key] = deep_merge(defaults, value)
        
        # Add variable selection options
        self.params["variable_options"] = variable_options

    @abstractmethod
    def compute(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Subclasses must implement."""
        pass

    def get_config(self) -> Dict[str, Any]:
        """
        Return the config schema with updated defaults (for React forms).
        """
        schema = self.__class__.config.copy()
        props = schema.get("properties", {})
        for k, v in self.params.items():
            if k in props:
                props[k]["default"] = v
        schema["properties"] = props
        return schema

    def set_config(self, new_config: Dict[str, Any]):
        """Update params (from frontend submission or backend call)."""
        for k, v in new_config.items():
            if k in self.params:
                self.params[k] = v