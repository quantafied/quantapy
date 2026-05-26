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

from quantapy.registry.component_registry import COMPONENT_REGISTRY
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
    
    def __init__(self, strategy, store=None):
        
        # Information we need from our strategy object
        self.strategy = strategy
        self.store = store
        self.simulations = [] 
        self.evaluator = None
        
    def add(self, registered: str, function: str, source: str = "Internal", **kwargs):
        
        # Get the class from the registry
        transform_class = COMPONENT_REGISTRY[registered][function][source]
        data_s_instance = transform_class(**kwargs)
    
        self.simulations.append(data_s_instance)
        
    def add_evaluator(self, registered: str, function: str, source: str = "Internal", **kwargs):
        
        # Get the class from the registry
        transform_class = COMPONENT_REGISTRY[registered][function][source]
        data_s_instance = transform_class(**kwargs)
    
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

    def execute(self, dataset_name: str, store=None, name: str = None):
        """
        Execute registered simulations on a committed DataStore dataset.

        Returns:
            (simulation_results, evaluator_outputs, metrics)
        """
        active_store = store or self.store or self.strategy.store
        if active_store is None:
            raise ValueError("Simulate.execute requires a DataStore")
        if not self.simulations:
            raise ValueError("No simulations registered")

        df = active_store.to_dataframe(dataset_name)
        if df is None:
            raise ValueError(f"Dataset '{dataset_name}' not found")

        parent = active_store.get_record(dataset_name)
        prefix = name or f"{dataset_name}-{self.simulations[0].__class__.__name__}"

        simulation_results = self.simulations[0].execute(df, self.strategy)
        active_store.add_child(
            prefix,
            simulation_results,
            parent_ids=[parent.id],
            kind="backtest",
            transform={
                "name": self.simulations[0].__class__.__name__,
                "params": getattr(self.simulations[0], "params", {}),
            },
        )

        evaluator_outputs = None
        metrics = None
        if self.evaluator is not None:
            evaluator_outputs, metrics = self.evaluator.execute(simulation_results)
            active_store.add_child(
                f"{prefix}-Portfolio-Outputs",
                evaluator_outputs,
                parent_ids=[prefix],
                kind="metrics",
                transform={"name": self.evaluator.__class__.__name__, "output": "timeseries"},
            )
            active_store.add_child(
                f"{prefix}-Portfolio-Metrics",
                metrics,
                parent_ids=[prefix],
                kind="metrics",
                transform={"name": self.evaluator.__class__.__name__, "output": "summary"},
            )

        self.simulation_results = simulation_results
        self.evaluation_results = evaluator_outputs
        self.backtest_metrics = metrics
        return simulation_results, evaluator_outputs, metrics
        
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
        

   

                
                
                
                
                
            
            
