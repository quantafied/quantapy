#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Jun 23 20:51:01 2025

@author: andrewsimin
"""

import talib
from quantapy.core.base_study import BaseStudy
from quantapy.registry.component_registry import register_component
import pandas as pd
import numpy as np
from typing import List,Union,Type
import random
import optuna
from sklearn.model_selection import TimeSeriesSplit
import math
        
"""
json_schema_exra:

    advanced: Will display the parameter and any of its additional attributes 
    in an advanced dropdown container
"""
    
# We only define GUI parameters in the config and all else in the 
# actual function

@register_component(category="Best Trial", function="Distance from Ideal", source="Internal")
class weighted_euclidean_distance_to_ideal():
    
    def execute(self, 
                pareto_solutions: np.array, 
                objectives: list[str] = ["max"], 
                weights: list[float] = [1.0]):
        """
        Compute weighted Euclidean distance of each solution to the ideal solution.
        
        Parameters:
        - pareto_solutions (np.array): 2D array (rows: solutions, columns: objectives).
        - objectives (list): List of 'max' or 'min' indicating the type of each objective.
        - weights (list): List of weights corresponding to each objective (must sum to 1 or be relative).
    
        Returns:
        - distances (np.array): Weighted Euclidean distances for each solution.
        """
        pareto_solutions = np.array(pareto_solutions)
        weights = np.array(weights) / np.sum(weights)  # Normalize weights to sum to 1
    
        if len(pareto_solutions) > 1:
        # Step 1: Normalize objectives
            norm_solutions = np.zeros_like(pareto_solutions, dtype=float)
            
            for j, obj_type in enumerate(objectives):
                col = pareto_solutions[:, j]
                if obj_type == 'maximize':
                    norm_solutions[:, j] = (col - np.min(col)) / (np.max(col) - np.min(col))
                elif obj_type == 'minimize':
                    norm_solutions[:, j] = (np.max(col) - col) / (np.max(col) - np.min(col))
                else:
                    raise ValueError(f"Invalid objective type: {obj_type}. Use 'max' or 'min'.")
        
            # Step 2: Define the ideal solution
            ideal_solution = np.max(norm_solutions, axis=0)
        
            # Step 3: Compute Weighted Euclidean Distance
            squared_diff = (norm_solutions - ideal_solution) ** 2
            weighted_diff = squared_diff * weights  # Apply weights element-wise
            distances = np.sqrt(np.sum(weighted_diff, axis=1))
            
            optimal = np.argmin(distances)
            
        elif len(pareto_solutions) == 1:
            distances = [1.0]
            optimal = 0
            
        return distances, optimal
