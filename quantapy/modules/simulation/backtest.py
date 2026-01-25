#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Jun 22 10:08:30 2025

@author: andrewsimin
"""

import sys
sys.path.append("/home/andrewsimin/automating_alpha/v0.0.3")
from tradinglib.registry.component_registry import COMPONENT_REGISTRY
from tradinglib.utils.loader import load_plugins_from_folder
from pydantic import BaseModel
from typing import get_args, get_origin, List, Union
#from tradinglib.gui.pydantic_form import single_model, list_of_models
import pandas as pd
import optuna
from tradinglib.modules.evaluation.metrics import *
from joblib import Parallel, delayed

#import calculator

from abc import ABC, abstractmethod
from tradinglib.core.base_component import BaseComponentConfig
import pandas as pd
from typing import List,Union,Type
from pydantic import BaseModel,Field
from tradinglib.core.base_simulation import BaseSimulation
from tradinglib.registry.component_registry import register_component

#from tradinglib.modules.study.validation import permute_trades, gaussian_noise
import tradinglib.modules.calculator.technical

#from tradinglib.modules.simulation.backtest import RobustBacktest
    
@register_component(category="Simulation", function="Backtest", source="Internal")
class Backtest(BaseSimulation):
    
    config = {
      "title": "Backtest",
      "type": "object",
      "properties": {
        "initial_investment": {
          "type": "number",
          "default": 10000,
          "description": "Name of the signal",
          "advanced": False
        },
        "close_on_completion": {
          "type": "string",
          "default": "close",
          "description": "First variable",
          "use_variable_options": True, # Enums generated dynamically in base_class with get_config method
          "widget_type": "select",
          "advanced": False
        }
      }
    }

    def generate_signals(self,data,strategy):
        
        # Pass in single dataframe and strategy object
        
        
        # need to reset calculator data from __init__ since these are dynmically called
        # for each optimization trial 

        constraints = strategy.constraints

        
        start = data.index[0]
        end = data.index[-1]
        #if self.end == -1:
        #    self.end = len(self.transformed_data)
            
        simulation_outputs = pd.DataFrame(data["date"].iloc[start:end])
        
        # Should we take out of __init__ ? Issue with updates because of append
        event_signals = []
        
        #for i in range(self.start, len(self.transformed_data)):  # Loop over time
        for i in range(start, end):  # Loop over time
        
            entry_constraints = []
            exit_constraints = []

            for constraint in constraints: # Loop over constraints
                
                output, action, direction = constraint.check(data, i)
                #print(output)
                
                if action == "enter":
                    entry_constraints.append(output)
                elif action == "exit":
                    exit_constraints.append(output)
                
            if entry_constraints and all(entry_constraints):  # New method
                event_signals.append("enter")
            elif exit_constraints and all(exit_constraints):  # New method
                event_signals.append("exit")
            else:
                event_signals.append("no action")
        
        #print(self.event_signals)
        #self.transformed_data["signal"] = self.event_signals
        simulation_outputs["signal"] = event_signals
        
        return simulation_outputs
                
#    def simulate_returns(self,):
        
#        for i in range(0, len(self.transformed_data)): 
            
            #if self.position[0] == None and self.transformed_data["signal"] = "enter":
                
    def simulate_returns(self,simulation_outputs,data,strategy,initial_investment):
        
        orders = strategy.orders
        price_column = "close"
        
        cash = initial_investment
        position = 0  # shares held
        portfolio_values = []
        actions = []
        positions = []
        
        start = data.index[0]
        end = data.index[-1]
        
        for i in range(start,end):
            #signal = self.transformed_data.loc[i, "signal"]
            signal = simulation_outputs.loc[i, "signal"]
            #print(signal)
            executed_price = None
    
            # Use first matching order (can be extended to multi-order logic)
            for order in orders:
                #print(order)
                executed_price = order.execute(data, i, signal)
                if executed_price:
                    #print(executed_price)
                    pass
                if executed_price is not None:
                    break  # stop after first matching order
    
            if signal == "enter" and executed_price and position == 0:
                print("Found entry")
                position = cash / executed_price
                cash = 0
                actions.append("buy")
            elif signal == "exit" and executed_price and position > 0:
                cash = position * executed_price
                position = 0
                actions.append("sell")
            else:
                actions.append("hold")
    
            # Portfolio value at each step
            current_price = data.loc[i, price_column]
            portfolio_value = cash + position * current_price
            portfolio_values.append(portfolio_value)
            positions.append(position)
            #print(current_price,portfolio_value)
            
        #print(portfolio_value)
    
        # Store results in DataFrame
        #self.transformed_data["portfolio_value"] = portfolio_values
        #self.transformed_data["position"] = positions
        #self.transformed_data["action"] = actions
        
        #print(portfolio_values)
        simulation_outputs["portfolio_value"] = portfolio_values
        simulation_outputs["position"] = positions
        simulation_outputs["action"] = actions
        
        return simulation_outputs
        
        #print(portfolio_values)
        
    def execute(self,data,strategy):
        
        initial_investment = self.params["initial_investment"]
        start = 0
        end = -1
        
        simulation_outputs = self.generate_signals(data,strategy)
        print(simulation_outputs)
        simulation_outputs = self.simulate_returns(simulation_outputs,data,strategy,initial_investment)
        
        #return scalar_metrics(self.simulation_outputs)
        print(simulation_outputs)
        return simulation_outputs
    
#    def execute(self,input_data_dict,strategy,n_jobs=-1):
        
#        results = Parallel(
#            n_jobs=n_jobs,
#            backend="loky",
#        )(
#            delayed(self._execute_one)(data,strategy)
#            for data in input_data_dict
#        )
            
        return results
    
    #def execute(self):
        
    #    self
    
    # Use for trade permutation
    def execute_from_signals(self,signals):
        
        #signals is simulation_outputs dataframe
        
        self.initial_investment = self.params["initial_investment"]
        
        self.simulation_outputs['signals'] = signals
        self.simulate_returns()
        
        #return scalar_metrics(self.simulation_outputs)
        return self.simulation_outputs
    