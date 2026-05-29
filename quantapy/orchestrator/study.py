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
from quantapy.modules.evaluation.metrics import *
from quantapy.modules.study.optimization import weighted_euclidean_distance_to_ideal_test
import copy
from dataclasses import asdict, dataclass
from typing import Any, Dict, Optional


@dataclass
class OptimizableParameter:
    """Structured description of a parameter selected for optimization."""

    target: str
    param: str
    name: Optional[str] = None
    index: Optional[int] = None
    dtype: Optional[str] = None
    low: Optional[float] = None
    high: Optional[float] = None
    choices: Optional[list] = None
    default: Any = None
    enabled: bool = True

class Study():
    """Coordinate validation, optimization, and evaluation studies."""
    
    def __init__(self,simulation, store=None, calculator=None, strategy=None):
        """Initialize a study from a simulation orchestrator."""
        
        self.simulation = simulation
        self.store = store or getattr(simulation, "store", None)
        self.strategy = strategy or getattr(simulation, "strategy", None)
        self.calculator = calculator or getattr(self.strategy, "calculator", None)
        self.studies = []
        self.validation = None
        self.best_trial = None
        self.parameters = []
        
    def update_simulation_object(self,simulation):
        """Replace the simulation object with a deep copy."""
        
        self.simulation = copy.deepcopy(simulation)
        self.store = getattr(self.simulation, "store", self.store)
        self.strategy = getattr(self.simulation, "strategy", self.strategy)
        self.calculator = getattr(self.strategy, "calculator", self.calculator)

    def _candidate_from_schema(
        self,
        target: str,
        param: str,
        schema_node: Dict[str, Any],
        name: Optional[str] = None,
        index: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        """Build a structured candidate from an optimizable schema field."""
        optimizable = schema_node.get("optimizable")
        if not optimizable:
            return None

        candidate = OptimizableParameter(
            target=target,
            name=name,
            index=index,
            param=param,
            dtype=schema_node.get("type"),
            default=schema_node.get("default"),
            enabled=False,
        )

        if isinstance(optimizable, dict):
            candidate.low = optimizable.get("min", optimizable.get("low"))
            candidate.high = optimizable.get("max", optimizable.get("high"))
            candidate.choices = optimizable.get("choices")
        elif isinstance(optimizable, (list, tuple)) and len(optimizable) == 2:
            candidate.low = optimizable[0]
            candidate.high = optimizable[1]

        if candidate.choices is None and "enum" in schema_node:
            candidate.choices = schema_node["enum"]

        return asdict(candidate)

    def discover_parameters(self):
        """Return structured optimizable parameter candidates."""
        candidates = []
        strategy_dependencies = set(getattr(self.strategy, "transform_dependencies", []))

        if self.calculator is not None:
            for name, info in self.calculator.transforms.items():
                transform_obj = info["cls"](**info["params"])
                config = transform_obj.get_config()
                output_names = list(info["params"].get("output_names", {}).values())
                for param, schema_node in config.get("properties", {}).items():
                    candidate = self._candidate_from_schema(
                        target="Transform",
                        name=name,
                        param=param,
                        schema_node=schema_node,
                    )
                    if candidate:
                        candidate["outputs"] = output_names
                        candidate["used_by_strategy"] = any(
                            output in strategy_dependencies
                            for output in output_names
                        )
                        candidates.append(candidate)

        if self.strategy is not None:
            for i, signal in enumerate(self.strategy.constraints):
                config = signal.get_config() if hasattr(signal, "get_config") else {}
                name = signal.params.get("name") if hasattr(signal, "params") else None
                for param, schema_node in config.get("properties", {}).items():
                    candidate = self._candidate_from_schema(
                        target="Signal",
                        name=name,
                        index=i,
                        param=param,
                        schema_node=schema_node,
                    )
                    if candidate:
                        candidates.append(candidate)

            for i, order in enumerate(self.strategy.orders):
                config = order.get_config() if hasattr(order, "get_config") else {}
                name = order.params.get("name") if hasattr(order, "params") else None
                for param, schema_node in config.get("properties", {}).items():
                    candidate = self._candidate_from_schema(
                        target="Order",
                        name=name,
                        index=i,
                        param=param,
                        schema_node=schema_node,
                    )
                    if candidate:
                        candidates.append(candidate)

        for i, simulation in enumerate(getattr(self.simulation, "simulations", [])):
            config = simulation.get_config() if hasattr(simulation, "get_config") else {}
            name = simulation.__class__.__name__
            for param, schema_node in config.get("properties", {}).items():
                candidate = self._candidate_from_schema(
                    target="Simulation",
                    name=name,
                    index=i,
                    param=param,
                    schema_node=schema_node,
                )
                if candidate:
                    candidates.append(candidate)

        return candidates

    def add_parameter(
        self,
        target: str,
        param: str,
        name: Optional[str] = None,
        index: Optional[int] = None,
        dtype: Optional[str] = None,
        low: Optional[float] = None,
        high: Optional[float] = None,
        choices: Optional[list] = None,
        default: Any = None,
    ):
        """Enable a structured parameter for optimization."""
        parameter = OptimizableParameter(
            target=target,
            name=name,
            index=index,
            param=param,
            dtype=dtype,
            low=low,
            high=high,
            choices=choices,
            default=default,
        )
        self.parameters.append(parameter)
        return asdict(parameter)

    def list_parameters(self):
        """Return explicitly enabled optimization parameters."""
        return [asdict(parameter) for parameter in self.parameters]

    def _apply_parameter(self, parameter: OptimizableParameter, value):
        """Apply a suggested value to calculator, strategy, or simulation state."""
        target = parameter.target.lower()

        if target in {"transform", "calculator"}:
            if parameter.name not in self.calculator.transforms:
                raise ValueError(f"Transform '{parameter.name}' not found")
            self.calculator.transforms[parameter.name]["params"][parameter.param] = value
            return

        if target == "signal":
            signal = (
                self.strategy.constraints[parameter.index]
                if parameter.index is not None
                else next(
                    sig for sig in self.strategy.constraints
                    if getattr(sig, "params", {}).get("name") == parameter.name
                )
            )
            signal.params[parameter.param] = value
            return

        if target == "order":
            order = (
                self.strategy.orders[parameter.index]
                if parameter.index is not None
                else next(
                    order for order in self.strategy.orders
                    if getattr(order, "params", {}).get("name") == parameter.name
                )
            )
            order.params[parameter.param] = value
            return

        if target == "simulation":
            simulation = (
                self.simulation.simulations[parameter.index]
                if parameter.index is not None
                else next(
                    sim for sim in self.simulation.simulations
                    if sim.__class__.__name__ == parameter.name
                )
            )
            simulation.params[parameter.param] = value
            return

        raise ValueError(f"Unsupported optimization target '{parameter.target}'")
        
    def add(self, registered: str, function: str, source: str, **kwargs):
        """Instantiate a validation or study component from the registry."""
        
        # Get the class from the registry
        transform_class = COMPONENT_REGISTRY[registered][function][source]
        print(transform_class)
        
        if registered == "Validation":
            data_s_instance = transform_class(simulation=self.simulation, **kwargs)
            self.validation = data_s_instance
        elif registered == "Best Trial":
            data_s_instance = transform_class(**kwargs)
            self.best_trial = data_s_instance
        else:
            data_s_instance = transform_class(simulation=self.simulation, **kwargs)
            self.studies.append(data_s_instance)

        return data_s_instance
 
    def run_in_sample(self):   
        """Run optimization studies over all in-sample folds."""
        
        self.in_sample_studies = []
             
        for study in self.studies:
            
            # Need to store the studies
            
            for fold in self.folds:
            # Compute the output of each transform
                
                # Index the calculator Data
                print(fold,file=open("folds.txt","a"))
                study.simulation.strategy.calculator.index_data(fold[0][0],fold[0][1])
                print(study.simulation.strategy.calculator.start,study.simulation.strategy.calculator.end,file=open("folds.txt","a"))
                print(study.simulation.strategy.calculator.transformed_data,file=open("folds.txt","a"))
                study.simulation.strategy.calculator.apply_transformations()
                #print(study.simulation.strategy.calculator.transformed_data)
                in_sample_study = study.execute()
                
                self.in_sample_studies.append(in_sample_study)
            
        return self.in_sample_studies
    
    def evaluate_in_sample(self):
        """Evaluate selected trials on in-sample folds."""
        
        self.optimal_ind = weighted_euclidean_distance_to_ideal_test(self, weights=[0.25,0.75])
        
        self.in_sample_results = []
        self.in_sample_data = []
        self.in_sample_overlays = []
        self.in_sample_indicators = []
        
        for study in self.studies:
            
            for i,fold in enumerate(self.folds):
            # Compute the output of each transform
            
                print("FOLD")
                print(self.in_sample_studies[i].best_trials)
                
                # Out Sample
                study.simulation.strategy.calculator.index_data(fold[0][0],fold[0][1])
                study.simulation.strategy.calculator.apply_transformations()
                in_sample_result = study.run_trial(self.in_sample_studies[i].best_trials[self.optimal_ind[i]])
                self.in_sample_data.append(study.simulation.strategy.calculator.transformed_data)
                self.in_sample_overlays.append(study.simulation.strategy.calculator.overlays)
                self.in_sample_indicators.append(study.simulation.strategy.calculator.indicators)
                
                
                self.in_sample_results.append(in_sample_result)
            
        #return in_sample_result, out_sample_result
        return self.in_sample_results  
    
    def evaluate_out_sample(self):   
        """Evaluate selected trials on out-of-sample folds."""
        
        self.out_sample_results = []
        self.out_sample_data = []
        self.out_sample_overlays = []
        self.out_sample_indicators = []
        
        for study in self.studies:
            
            for i,fold in enumerate(self.folds):
            # Compute the output of each transform
                
                # Out Sample
                study.simulation.strategy.calculator.index_data(fold[1][0],fold[1][1])
                study.simulation.strategy.calculator.apply_transformations()
                out_sample_result = study.run_trial(self.in_sample_studies[i].best_trials[self.optimal_ind[i]])
                self.out_sample_data.append(study.simulation.strategy.calculator.transformed_data)
                self.out_sample_overlays.append(study.simulation.strategy.calculator.overlays)
                self.out_sample_indicators.append(study.simulation.strategy.calculator.indicators)
                
                self.out_sample_results.append(out_sample_result)
            
        #return in_sample_result, out_sample_result
        return self.out_sample_results   

    def execute(self):
        """Run validation, in-sample optimization, and out-of-sample evaluation."""
        
        if self.validation:
            print("FOUND VALIDATION")
            print(self.validation)
            self.folds = self.validation.execute(self.simulation.strategy.calculator.transformed_data)
        
        in_sample_studies = self.run_in_sample()
        
        # I dont think we want to run in_sample evaluation because we need to select the 
        #pareto optimal solution to run
        
        in_sample_result = self.evaluate_in_sample()
        out_sample_result = self.evaluate_out_sample()
        
        # need to reset index to original    
            
        return in_sample_studies, in_sample_result, out_sample_result, self.in_sample_data, self.out_sample_data, self.in_sample_indicators, self.in_sample_overlays, self.out_sample_overlays, self.out_sample_indicators
        
    
        
    
                

    
                
                
                
                
            
            
