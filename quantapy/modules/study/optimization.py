# app/ta_functions.py

import talib
from quantapy.core.base_study import BaseStudy
from quantapy.registry.component_registry import register_component
import pandas as pd
import numpy as np
from typing import List,Union,Type
import random
import optuna
import numpy as np

"""
json_schema_exra:

    advanced: Will display the parameter and any of its additional attributes 
    in an advanced dropdown container
"""

#class BayesianOptConfig(BaseComponentConfig):
#    """ Configuration schema for Bollinger Bands technical indicator"""
#    
#    objectives: List[str] = Field(
#        default_factory=list, 
#        json_schema_extra={"options": ["Maximize Profit",
#                                       "Minimize Profit",
#                                       "Maximize Sharpe Ratio", 
#                                       "Minimize Sharpe Ratio", 
#                                       "Maximize CAGR",
#                                       "Minimize CAGR"], 
#                           "widget_type": "multiselect"
#                           }
#    )
#    
#    trials: int = Field(
#        default = 25, 
#        description="Number of optimization trials", 
#        json_schema_extra={"advanced": False,
#                           }
#    )
    
@register_component(category="Optimization", function="Bayesian", source="Internal")
class bayesian(BaseStudy):
    """Bayesian optimizer"""
    
    config = {
      "title": "Bayesian Optimizer",
      "type": "object",
      "properties": {
        "trials": {
          "type": "integer",
          "default": 50,
          "description": "Number of optimization trials",
        },
        "objectives": {
        "type": "array",
        "title": "Objectives",
        "description": "Select objectives to maximize/minimize",
        "items": {
          "type": "string",
          "enum": ["Maximize Profit", "Minimize Profit", "Maximize Sharpe Ratio", "Minimize Sharpe Ratio"]
          },
          "uniqueItems": True,
          "default": ["close"]
          },
        }
      }
    
    def objective(self,trial):
        
        print(f"TRIAL: {trial}")
        
        self.get_optimizable()
        
        # Original
        #for optimizable in self.optimizable_functions:
        #    for parameter,bounds in self.simulation.strategy.calculator.transforms[optimizable].params["optimizable"].items():
        #        parameter = list(self.simulation.strategy.calculator.transforms[optimizable].params["optimizable"].keys())[0]
        #        bounds = [self.simulation.strategy.calculator.transforms[optimizable].params["optimizable"][f"{parameter}_min"],self.simulation.strategy.calculator.transforms[optimizable].params["optimizable"][f"{parameter}_max"]]
        #        suggestion = trial.suggest_int(f"{optimizable}_{parameter}", bounds[0], bounds[1])
        #        #suggestion = 27
        #        # update config # may want to do this and make the class/function callable from the instance config
        #        setattr(self.simulation.strategy.calculator.transforms[optimizable].config, parameter, suggestion)
        #    # update transformation
        #    self.simulation.strategy.calculator.update(**self.simulation.strategy.calculator.transforms[optimizable].config.model_dump())
        #self.simulation.strategy.calculator.apply_transformations()
        
        for optimizable in self.optimizable_functions:

            parameter = list(self.simulation.strategy.calculator.transforms[optimizable].params["optimizable"].keys())[0]
            bounds = [self.simulation.strategy.calculator.transforms[optimizable].params["optimizable"][f"{parameter}_min"],self.simulation.strategy.calculator.transforms[optimizable].params["optimizable"][f"{parameter}_max"]]
            suggestion = trial.suggest_int(f"{optimizable}_{parameter}", bounds[0], bounds[1])
            #suggestion = 27
            # update config # may want to do this and make the class/function callable from the instance config
            print(optimizable,parameter,suggestion)
            self.simulation.strategy.calculator.transforms[optimizable].params[parameter]=suggestion
            # update transformation
            #self.simulation.strategy.calculator.update(**self.simulation.strategy.calculator.transforms[optimizable].params)
        self.simulation.strategy.calculator.apply_transformations()
        
        for optimizable in self.optimizable_conditions:
            for parameter,bounds in self.simulation.strategy.strategy_conditions[optimizable].config.optimizable.items():
                suggestion = trial.suggest_int(f"{optimizable}_{parameter}", bounds[0], bounds[1])
                setattr(self.simulation.strategy.strategy_conditions[optimizable].config, parameter, suggestion)
            # update transformation
            self.simulation.strategy.update_condition(optimizable,**self.simulation.strategy.strategy_conditions[optimizable].config.model_dump())
        #self.simulation.strategy.calculator.apply_transformations()
        
        simulation_results, evaluator_results, metrics = self.simulation.execute()
        print("5555555555555555555")
        print(type(metrics))
        
        objective_list = []
        for obj in self._objectives:
            objective_list.append(metrics[obj])
            
        return tuple(objective_list)
    
    
    def execute(
        self, 
        objectives: list[str] = ["Maximize Profit"], 
        trials: int = 25,
        ):
        
        trials = self.params["trials"]
        self.objectives = self.params["objectives"]
        self._objectives = []
                
        directions = []
        
        for objective in self.objectives:
            directions.append(objective.split()[0].lower())
            self._objectives.append(" ".join(objective.split()[1:]))
        
        file_path = "./optuna_journal_storage.log"
        storage = optuna.storages.JournalStorage(optuna.storages.journal.JournalFileBackend(file_path))
        
        sampler_algo = optuna.samplers.TPESampler()
        
        study = optuna.create_study(
            #study_name=,
            storage=f"sqlite:///asimin.sqlite3",#storage, #f"sqlite:///asimin.sqlite3",
            directions=directions,
            sampler=sampler_algo
        )

        study.optimize(self.objective, n_trials=trials)
        
        self.opt_study = study
        
        return study
    
    def run_trial(self,trial):
        
        print(f"TRIAL: {trial}")
        
        self.get_optimizable()
        
        for optimizable in self.optimizable_functions:

            parameter = list(self.simulation.strategy.calculator.transforms[optimizable].params["optimizable"].keys())[0]
            bounds = [self.simulation.strategy.calculator.transforms[optimizable].params["optimizable"][f"{parameter}_min"],self.simulation.strategy.calculator.transforms[optimizable].params["optimizable"][f"{parameter}_max"]]
            suggestion = trial.suggest_int(f"{optimizable}_{parameter}", bounds[0], bounds[1])
            #suggestion = 27
            # update config # may want to do this and make the class/function callable from the instance config
            print(optimizable,parameter,suggestion)
            self.simulation.strategy.calculator.transforms[optimizable].params[parameter]=suggestion
            # update transformation
            #self.simulation.strategy.calculator.update(**self.simulation.strategy.calculator.transforms[optimizable].params)
        self.simulation.strategy.calculator.apply_transformations()
        
        simulation_results, evaluator_results, metrics = self.simulation.execute()
        print("5555555555555555555")
        print(type(metrics))
        
        objective_list = []
        for obj in self._objectives:
            objective_list.append(metrics[obj])
            
        return simulation_results, evaluator_results, metrics

#class WrightedDistanceConfig(BaseComponentConfig):
#    """ Configuration schema for Bollinger Bands technical indicator"""
#    
#    "My Schema Here"
    
@register_component(category="Optimization", function="Weighted Distance to Ideal", source="Internal")
def weighted_euclidean_distance_to_ideal_test(study_obj, weights):
    """
    Compute weighted Euclidean distance of each solution to the ideal solution.
    
    Parameters:
    - pareto_solutions (np.array): 2D array (rows: solutions, columns: objectives).
    - objectives (list): List of 'max' or 'min' indicating the type of each objective.
    - weights (list): List of weights corresponding to each objective (must sum to 1 or be relative).

    Returns:
    - distances (np.array): Weighted Euclidean distances for each solution.
    """
    
    objectives = [direction.name.lower() for direction in study_obj.in_sample_studies[0].directions]
    
    studies = study_obj.in_sample_studies
    
    optimals = []
    
    for i,study in enumerate(studies):
        
        if len(objectives) > 1:
        
            print("Inspecting")
            
            pareto_solutions = []
            for trial in study.best_trials:
                pareto_solutions.append(trial.values)
    
            if len(pareto_solutions) < 1:
                print("Pareto Set Empty")
                continue
    
            unique_data = []
            seen = set()
            
            for item in pareto_solutions:
                t = tuple(item)
                if t not in seen:
                    seen.add(t)
                    unique_data.append(item) # get unique
            
            print(pareto_solutions)
            pareto_solutions = np.array(unique_data)
            print(pareto_solutions)
            # sometime returns same objective value so we take the first by using unique
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
                
            optimals.append(optimal)
            
        else:
            
            optimals.append(0)
            
    return optimals
    
