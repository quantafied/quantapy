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

class CustomDataFrame(pd.DataFrame):
    
    """
    Extends pandas so transformations can be called on DataFrames directly
    """
    
    _metadata = ['transforms']
    
    def __init__(self, *args, **kwargs):
        """Create a DataFrame that tracks applied transforms."""
        super().__init__(*args, **kwargs)
        self.transforms = []  # Custom attribute to store transformations
    
    @property
    def _constructor(self):
        return CustomDataFrame

    def add_transform(self, *args, **kwargs):
        """Apply and remember a transform on this DataFrame."""
        transform = Transform(self)
        transform.compute(*args, **kwargs)
        self.transforms.append(transform)
        return transform
    
    def save(self):
        """Placeholder persistence hook for transformed data."""
        print("Hello")
        
