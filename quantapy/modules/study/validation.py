#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Jun 23 20:51:01 2025

@author: andrewsimin
"""

import talib
from tradinglib.core.base_study import BaseStudy
from tradinglib.registry.component_registry import register_component
from tradinglib.core.base_component import BaseComponentConfig
import pandas as pd
from pydantic import BaseModel,Field
import numpy as np
from typing import List,Union,Type
import random
import optuna
from sklearn.model_selection import TimeSeriesSplit
import math
from typing import List, Dict
        
"""
json_schema_exra:

    advanced: Will display the parameter and any of its additional attributes 
    in an advanced dropdown container
"""
    
@register_component(category="Validation", function="None", source="Internal")
class none(BaseStudy):
    """Bayesian optimizer"""
    
    config = {
      "title": "Holdout",
      "type": "object",
      "properties": {
      }
    }
    
    def execute(self,
                df: pd.DataFrame):
        
        splits = [([0,-1],[0,-1])]
        
        return splits

@register_component(category="Validation", function="Holdout", source="Internal")
class holdout(BaseStudy):
    """Bayesian optimizer"""
    
    config = {
      "title": "Holdout",
      "type": "object",
      "properties": {
        "train_ratio": {
          "type": "number",
          "default": 0.75,
          "description": "Ratio of training data",
        },
      }
    }
    
    def execute(self,
                df: pd.DataFrame,
                train_ratio: float = 0.75):
            
        test_size = math.ceil(len(df)*(1.0-self.params["train_ratio"]))
        train_size = len(df) - test_size
        
        splits = [([0,train_size],[train_size+1,train_size+test_size-1])]
        
        return splits
    
@register_component(category="Validation", function="Time Series K-Fold", source="Internal")
class time_series_k_fold(BaseStudy):
    """
    Perform TimeSeriesSplit for cross-validation.

    Parameters:
    - df: DataFrame with time series data
    - n_splits: Number of splits
    - max_train_size: Max training size per fold
    - test_size: Test size per fold
    - gap: Gap between train and test sets

    Returns:
    - List of (train_df, test_df) tuples
    """
    
    config = {
      "title": "Time Series K-Fold",
      "type": "object",
      "properties": {
        "n_splits": {
          "type": "integer",
          "default": 4,
          "description": "Number of folds to split data",
        },
        "max_train_size": {
          "type": "integer",
          "default": 10,
          "description": "Max size of the training data for each fold",
        },
        "test_size": {
          "type": "integer",
          "default": 10,
          "description": "Test size per fold",
        },
        "gap": {
          "type": "integer",
          "default": 0,
          "description": "Gap between folds",
        },
      }
    }
    
    def execute(self,
                df: pd.DataFrame, 
                n_splits: int = 5, 
                max_train_size: int = 1, 
                test_size: int = 1, 
                gap: int = 0):
    
        tscv = TimeSeriesSplit(n_splits=self.params["n_splits"], max_train_size=self.params["max_train_size"], test_size=self.params["test_size"], gap=self.params["gap"])
        #splits = [(df.iloc[train_idx], df.iloc[test_idx]) for train_idx, test_idx in tscv.split(df)]
        splits = [([train_idx[0],train_idx[-1]], [test_idx[0],test_idx[-1]]) for train_idx, test_idx in tscv.split(df)]
        
        #plot_time_series_splits(df, [(train.index, test.index) for train, test in splits])
    
        return splits
    
