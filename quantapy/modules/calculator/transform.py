#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Mar  3 00:01:38 2025

@author: andrewsimin
"""

#from imports import *
#from data.base import BaseAPI
#from transformations import ta_functions
#from transformations.registry import FUNCTION_REGISTRY
import inspect
import pandas as pd


#class Transform():
    
#    """
#    Apply transformation to pandas DataFrame
#    """
    
#    def __init__(self, data):
#        self.data = data
        
#    def compute(self, *args, **kwargs):
#        self.function = args[0]
#        self.func = FUNCTION_REGISTRY[self.function]["function"]

#        # Inspect function parameters
#        func_signature = inspect.signature(self.func)
#        bound_args = func_signature.bind(*args, **kwargs)
#        bound_args.apply_defaults()
#        self.runtime_args = {key: value for key, value in bound_args.arguments.items()}
        
#        # Remove 'data' key since it's passed separately
#        del self.runtime_args["data"]

#        # Compute the transformation
#        result = self.func(self.data, **kwargs)

#        # Store results in DataFrame
#        for i, (key, value) in enumerate(result.items()):
#            self.data[self.runtime_args["output_names"][i]] = value
        
#    def optimization_bounds(self, bounds):
#        self.bounds = bounds
        
class CustomDataFrame(pd.DataFrame):
    
    """
    Extends pandas so transformations can be called on DataFrames directly
    """
    
    _metadata = ['transforms']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.transforms = []  # Custom attribute to store transformations
    
    @property
    def _constructor(self):
        return CustomDataFrame

    def add_transform(self, *args, **kwargs):
        transform = Transform(self)
        transform.compute(*args, **kwargs)
        self.transforms.append(transform)
        return transform
    
    def save(self):
        print("Hello")
        
