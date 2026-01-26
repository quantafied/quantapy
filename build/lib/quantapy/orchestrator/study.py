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
from tradinglib.modules.study.optimization import weighted_euclidean_distance_to_ideal_test
import copy

class Study():
    
    def __init__(self,simulation):
        
        self.simulation = simulation
        self.studies = []
        self.validation = None
        
    def update_simulation_object(self,simulation):
        
        self.simulation = copy.deepcopy(simulation)
        
    def add(self, registered: str, function: str, source: str, config: Union[BaseModel, None] = None, **kwargs):
        
        # Get the class from the registry
        transform_class = COMPONENT_REGISTRY[registered][function][source]
        print(transform_class)
        
        if registered == "Validation":
            data_s_instance = transform_class(simulation=self.simulation, config=config, **kwargs)
            self.validation = data_s_instance
        else:
            data_s_instance = transform_class(simulation=self.simulation, config=config, **kwargs)
            self.studies.append(data_s_instance)
 
    def run_in_sample(self):   
        
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
        
    
        
    
                

    
                
                
                
                
            
            