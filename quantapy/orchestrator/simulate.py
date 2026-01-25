#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Jun 11 22:09:29 2025

@author: andrewsimin
"""

# Data and Calulator are passed to strategy since they can be seperate from the
# from the strategy pipeline likeall other stock software

# Calculator is a non extendable component and is primarily for managing 
# multiple transformation components which are extendable

from tradinglib.registry.component_registry import COMPONENT_REGISTRY
from tradinglib.utils.loader import load_plugins_from_folder
from pydantic import BaseModel
from typing import get_args, get_origin, List, Union
#from tradinglib.gui.pydantic_form import single_model, list_of_models
import pandas as pd
import optuna
from tradinglib.modules.evaluation.metrics import *

#import calculator

from abc import ABC, abstractmethod
from tradinglib.core.base_component import BaseComponentConfig
import pandas as pd
from typing import List,Union,Type
from pydantic import BaseModel,Field

from joblib import Parallel, delayed

class Simulate():
    
    # Strategy remains the same so we dont need to wory about mutating data
    # The issue with parallelizing backtest is that we need to mutate data object to update transforms
    # Ideally we need completely seperate objects data from the backtest object
    # Backtest cannot inherit the data object otherwise hundreds of copies will be created and we will run into issues with workers mutating shared data object in parallel
    # perhaps only share objects at the orchestrator level
    # pass that in to the RobustBacktest function and split from there
    
    # Or instead of mutating data with self, isolate functions to take in mutable inputs as local copies instead of global 
    
    # data = data
    # strategy = Strategy(data)
    # backtest = Backtest(data,strategy)
    # study = Study(data,strategy,backtest)
    
    def __init__(self, strategy):
        
        # Information we need from our strategy object
        self.strategy = strategy
        self.simulations = [] 
        
    def add(self, registered: str, function: str, source: str = "Internal", config: Union[BaseModel, None] = None, **kwargs):
        
        # Get the class from the registry
        transform_class = COMPONENT_REGISTRY[registered][function][source]
        data_s_instance = transform_class(strategy=self.strategy,config=config, **kwargs)
    
        self.simulations.append(data_s_instance)
        
    def add_evaluator(self, registered: str, function: str, source: str = "Internal", config: Union[BaseModel, None] = None, **kwargs):
        
        # Get the class from the registry
        transform_class = COMPONENT_REGISTRY[registered][function][source]
        data_s_instance = transform_class(strategy=self.strategy,config=config, **kwargs)
    
        self.evaluator = data_s_instance
        
    def _simulate_one(self,simulation,data,strategy):
        
            simulation_results = simulation.execute(data,strategy)
            return simulation_results
            
    def backtest(self,input_data_dict,strategy,n_jobs=-1):
        
        for simulation in self.simulations:
        
            results = Parallel(
                        n_jobs=n_jobs,
                        backend="loky",
                    )(
                        delayed(self._simulate_one)(simulation,data,strategy)
                        for data in input_data_dict
                    )
                        
        return results
        
#    def execute(self):
#        
#        for simulation in self.simulations:
#            simulation_results = simulation.execute() # we should return a list here for noise studies
#            print(len(simulation_results))
#            evaluator_results, metrics = self.evaluator.execute(simulation_results[0])
#            noise_results = []
#            noise_metrics = []
#            for i in range(len(simulation_results[1])):
#                res, met = self.evaluator.execute(simulation_results[1][i])
#                noise_results.append(res)
#                noise_metrics.append(met)
#                
#            
#        print(evaluator_results)   
#        #for evaluator in self.evaluators:
#        #    results = evaluator.execute()
#        self.simulation_results = simulation_results
#        self.evaluation_results = evaluator_results
#        self.backtest_metrics = metrics
#            
#        return simulation_results, evaluator_results, metrics, (noise_results,noise_metrics)
        

   

                
                
                
                
                
            
            