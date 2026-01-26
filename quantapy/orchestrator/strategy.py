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
from quantapy.utils.loader import load_plugins_from_folder
from typing import get_args, get_origin, List, Union
import pandas as pd
import optuna
from quantapy.modules.evaluation.metrics import *
import json

#import calculator
        
class Strategy():
    
    def __init__(self, calculator):
        self.calculator = calculator
        self.constraints = []  # List of signal objects
        self.orders = []
        self.event_signals = []       # Store triggered signals
        self.transformed_data = calculator.transformed_data
        self.transform_dependencies = []
        self.strategy_conditions = {}
        
        self.initial_investment = 1000.
        self.portfolio_weights = [1.]
        self.position = [False]
        self.open_orders = [False]

    def add(self, registered: str, function: str, source: str = "Internal", **kwargs):
        strategy_class = COMPONENT_REGISTRY[registered][function][source]
        instance = strategy_class(config=config, **kwargs)
        
        
        # Carefule that the registery groups match this syntax
        if registered == "Signal":
            self.constraints.append(instance)
            
            # How do we map strategy logic to transform logic to keep track
            # of optimizable parameters
            print(instance.params)
            instance_inputs = list(instance.params.values())
            
            for inputs in instance_inputs:
                #if inputs not dict:
                self.transform_dependencies.append(inputs)
                
            self.condition_to_index()
                
        elif registered == "Order":
            self.orders.append(instance)
            self.order_to_index()
            
    def save(self):
        
        self.constraints_state = []
        self.orders_state = []
        
        for value in self.constraints:
            self.constraints_state.append(value.payload)
        for value in self.orders:
            self.orders_state.append(value.payload)
        
        with open("constraints.json", "w") as f:
            json.dump(self.constraints_state, f, indent=2)
        with open("orders.json", "w") as f:
            json.dump(self.orders_state, f, indent=2)
            
    def load(self):
        
        with open("constraints.json", "r") as f:
            loaded_constraints = json.load(f)
        with open("orders.json", "r") as f:
            loaded_orders = json.load(f)
            
        for config in loaded_constraints:
            
            strategy_class = COMPONENT_REGISTRY["Signal"][config["type"]]["Internal"]
            instance = strategy_class(config=config)
            
            self.constraints.append(instance)
            
            # How do we map strategy logic to transform logic to keep track
            # of optimizable parameters
            instance_inputs = list(instance.config)
            for inputs in instance_inputs:
                #if inputs not dict:
                self.transform_dependencies.append(inputs[1])
                
            self.condition_to_index()
            
        for config in loaded_orders:
            
            strategy_class = COMPONENT_REGISTRY["Order"][config["type"]]["Internal"]
            instance = strategy_class(config=config)
            
            self.orders.append(instance)
            self.order_to_index()
        
    def update_condition(self, name: str, **new_params):
        
        if name not in self.strategy_conditions:
            raise ValueError(f"No transform named '{name}' found.")
        
        old_transform = self.strategy_conditions[name]
        config_dict = old_transform.config.model_dump()
        config_dict.update(new_params)
        
        # Reconstruct the transform using original registry keys
        transform_class = type(old_transform)
        print(transform_class)
        new_instance = transform_class(config=config_dict)
        #st.write(config_dict)
        
        #st.write(self.strategy_conditions[0])
        self.constraints[int(name)] = new_instance
        self.strategy_conditions[name] = new_instance
        self.condition_to_index()
        #st.write(self.strategy_conditions[0])
            
    def condition_to_index(self):
        
        # I think this is the culprit, update is applied to strategy_conditions not constraints
        # Fixed 10/13/2025
        
        self.strategy_conditions = {}
        
        for i,constraint in enumerate(self.constraints):
            self.strategy_conditions[int(i)] = constraint
            
        return self.strategy_conditions
    
    def remove_condition(self,operation):
        
        #del self.strategy_conditions[operation]
        #self.constraints.remove()
        self.constraints = [obj for obj in self.constraints if obj is not self.strategy_conditions[operation]]
        self.condition_to_index()
    
    def update_order(self, name: str, **new_params):
        
        if name not in self.strategy_orders:
            raise ValueError(f"No transform named '{name}' found.")
        
        old_transform = self.strategy_orders[name]
        config_dict = old_transform.config.model_dump()
        config_dict.update(new_params)
        
        # Reconstruct the transform using original registry keys
        transform_class = type(old_transform)
        print(transform_class)
        new_instance = transform_class(config=config_dict)
        
        self.orders[int(name)] = new_instance
        self.strategy_orders[name] = new_instance
        self.order_to_index()
        
    def order_to_index(self):
        
        self.strategy_orders = {}
        
        for i,order in enumerate(self.orders):
            self.strategy_orders[int(i)] = order
            
        return self.strategy_orders
    
    def remove_order(self,operation):
        
        #del self.strategy_conditions[operation]
        #self.constraints.remove()
        self.orders = [obj for obj in self.orders if obj is not self.strategy_orders[operation]]
        self.order_to_index()
        
        
    def get_optimizable(self):
        
        # Optimizable from transforms
        
        self.optimizable_functions = []
        
        # Index transforms
        for name, transform in self.calculator.transforms.items():
            # Index ransfrom outputs
            if any(name in self.transform_dependencies for name in transform.config.output_names):
                self.optimizable_functions.append(name)
                
        # returns a list of transform names that depend on the strategy
        return self.optimizable_functions
    
    def get_config(self):
        
        return self
                
    def objective(self,trial):
        
        print(f"TRIAL: {trial}")
        
   #     "Callable objective function"
   
        #self.generate_signals()
        #self.simulate_returns()      
        #print(self.calculator.transformed_data["sma_leading"])
        self.get_optimizable()
        for optimizable in self.optimizable_functions:
            for parameter,bounds in self.calculator.transforms[optimizable].config.optimizable.items():
                suggestion = trial.suggest_int(f"{optimizable}_{parameter}", bounds[0], bounds[1])
                #suggestion = 27
                # update config # may want to do this and make the class/function callable from the instance config
                setattr(self.calculator.transforms[optimizable].config, parameter, suggestion)
            # update transformation
            self.calculator.update(**self.calculator.transforms[optimizable].config.model_dump())
        self.calculator.apply_transformations()
        print(self.calculator.transformed_data["sma_leading"])
        
        
        self.generate_signals()
        self.simulate_returns() 
        
        print(self.calculator.transformed_data.keys())
        
        metrics = scalar_metrics(self.transformed_data)
        
        objectives = ["Profit"]
        objective_list = []
        for obj in objectives:
            objective_list.append(metrics[obj])
            
        return tuple(objective_list)
    
    def optimize(self):
        
        directions = ["maximize"]
        n_trials=20
        
        file_path = "./optuna_journal_storage.log"
        storage = optuna.storages.JournalStorage(optuna.storages.journal.JournalFileBackend(file_path))
        
        sampler_algo = optuna.samplers.TPESampler()
        
        study = optuna.create_study(
            #study_name=,
            storage=f"sqlite:///asimin.sqlite3",#storage, #f"sqlite:///asimin.sqlite3",
            directions=directions,
            sampler=sampler_algo
        )

        study.optimize(self.objective, n_trials=n_trials)
        
                
                
                
                
            
            
