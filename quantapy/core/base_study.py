#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon May 19 20:02:51 2025

@author: andrewsimin
"""

from abc import ABC, abstractmethod
import pandas as pd
from typing import List, Union, Type, Any, Dict, Union

class BaseStudy(ABC):
    """
    Simple hybrid base for transforms that can:
    - Accept JSON config from frontend (React)
    - Or be called directly with kwargs in Python
    """

    # Each subclass defines a JSON-schema-like config dict
    config: Dict[str, Any] = {}

    def __init__(self, simulation = None, config: Union[Dict[str, Any], None] = None, **kwargs):
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
        
        self.simulation = simulation
        
    def get_optimizable(self):
        
        # Optimizable from transforms
        
        self.optimizable_functions = []
        self.optimizable_conditions = []
        
        # Index transforms
        for name, transform in self.simulation.strategy.calculator.transforms.items():
            # Index ransfrom outputs
            #if any(name in self.simulation.strategy.transform_dependencies 
            #for name in list(transform.params["output_names"].values()):
            if any(name in self.simulation.strategy.transform_dependencies for name in list(transform.params["output_names"].values())):
                self.optimizable_functions.append(name)
        for name, signal in self.simulation.strategy.strategy_conditions.items():
            # Index ransfrom outputs
            #if any(name in self.simulation.strategy.transform_dependencies for name in transform.config.output_names):
            print(signal.params)
            try:
                if signal.params["optimizable"] == None:
                    print("Optimizable Signals = None")
                    pass
                else:
                    print("Optimizable Signal Found")
                    self.optimizable_conditions.append(name)
            except:
                print("Except Called on Optimizable Signal Params")
                pass
                
        # returns a list of transform names that depend on the strategy
        return list(set(self.optimizable_functions))

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
