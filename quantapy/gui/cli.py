#!/usr/bin/env_test python3
# -*- coding: utf-8 -*-
"""
Created on Thu Jun  5 23:55:06 2025

@author: andrewsimin
"""

from quantapy.registry.component_registry import COMPONENT_REGISTRY
from quantapy.utils.loader import load_plugins_from_folder
from typing import get_args, get_origin, List
from quantapy.modules.evaluation.metrics import *
import numpy as np


# Composition Classes - can not be extended themselves, only their submodules can
from quantapy.orchestrator.data import Data
from quantapy.orchestrator.calculator import Calculator
from quantapy.orchestrator.strategy import Strategy
from quantapy.orchestrator.simulate import Simulate
from quantapy.orchestrator.study import Study

"""We need to mutate parameters before sending to any parallel function"""

print("Imports successful")
load_plugins_from_folder("/home/andrewsimin/quantapy/quantapy/modules/strategy")
print("First plugin loaded")
load_plugins_from_folder("/home/andrewsimin/quantapy/quantapy/modules/simulation")
load_plugins_from_folder("/home/andrewsimin/quantapy/quantapy/modules/data")
load_plugins_from_folder("/home/andrewsimin/quantapy/quantapy/modules/calculator")
load_plugins_from_folder("/home/andrewsimin/quantapy/quantapy/modules/study")

print(COMPONENT_REGISTRY)

# what should we initialize data class with, if anything?
data = Data()
data.add("Market","OHLC","Internal", ticker=["AAPL","RGTI"],period="1 year")
data.add_synthetic("Noise", "Gaussian", "Internal", mean=0.0, stddev=0.5, n_trajectories=1000)
data.fetch_data()
market_data = data.data


# data = Data(df)
#historical = data.add("market","historical")
#fundamental = data.add("fundamental","insider_trading")

# Calculator

calculator = Calculator()
#sma_leading = calculator.add("Technical","Moving Average",name="SMA_LEADING",timeperiod=62,output_names={"output":"sma_leading"},optimizable={"timeperiod":(5,100)})
#sma_lagging = calculator.add("Technical","Moving Average",name="SMA_LAGGING",timeperiod=90,output_names={"output":"sma_lagging"})
calculator.add_transform("Technical","Moving Average",name="SMA_LEADING",timeperiod=62,output_names={"output":"sma_leading"})
calculator.add_transform("Technical","Moving Average",name="SMA_LAGGING",timeperiod=90,output_names={"output":"sma_lagging"})
#bbands = calculator.add("Technical","Bollinger Bands",name="BBANDS",output_names=["bbands_high","bbands_medium", "bbands_low"])
#bbands_test = calculator.add("Technical","Bollinger Bands",name="BBANDS_TEST")
#calculator.remove("SMA_LEADING")
res = calculator.apply_transformations_(data.data)

import matplotlib.pyplot as plt
plt.figure()
for dta in res["Gaussian"]["RGTI"]:
    plt.plot(dta["sma_leading"].to_numpy())
    plt.xlim(0,250)
    plt.ylim(5,15)
plt.plot(res["Raw"]["RGTI"][0]["sma_leading"].to_numpy(),"k--")

plt.figure()
for dta in res["Gaussian"]["RGTI"]:
    plt.plot(dta["close"].to_numpy())
    plt.xlim(0,250)
    plt.ylim(5,20)
plt.plot(res["Raw"]["RGTI"][0]["close"].to_numpy(),"k--")
#calculator.apply_transformations(data.data)
#transformed_data = calculator.transformed_data
#transformations = calculator.transforms

dt=1
plt.figure()
plt.psd(res["Raw"]["AAPL"][0]["close"].to_numpy(), NFFT=512, Fs=1 / dt)
plt.psd(res["Gaussian"]["AAPL"][0]["close"].to_numpy(), NFFT=512, Fs=1 / dt)

"""
#calculator.apply_transformations()

# Models

#model = Model(transformed_data)
#regressor = model.add("regression","linear") 
"""
# Strategy Builder

# Add data
strategy = Strategy(calculator)

# Signals
strategy.add("Signal","Crossover",name="Crossover",value1="sma_leading",value2="sma_lagging",action="enter",direction="long")
strategy.add("Signal","Crossunder",name="Crossover",value1="sma_leading",value2="sma_lagging",action="exit",direction="long")
#strategy.add("signal","greaterthanthreshold",value1="sma_leading",value2=12,action="enter",direction="long")

# Execution - agnostic to signals
#strategy.add("order", "limit", on_signal="entry", offset=0.5, input_type="absolute", on_bar="close")
strategy.add("Order", "Market", on_signal="entry", on_bar="close")
strategy.add("Order", "Market", on_signal="exit", on_bar="close")  # or stop with trailing params
#strategy.get_config()

# Risk Management
#strategy.add("risk","fixed_percent", risk_pct=1.0)
#strategy.add("risk","atr", multiplier=2)
#strategy.add("risk","r_multiple", r=2)

# Position Sizing
#strategy.add("position_size","fixed_risk", risk_pct=1.0)

# Actions
#strategy.add("action","parameterconditional",value1="atr",operator=">",value2="")
#strategy.add("action","optimize")
#strategy.add("action","rebalance")

# strategy is the input to the simulation :)
#simulation = Simulate(strategy)
#metrics = simulation.evaluate()

simulation = Simulate(strategy=strategy)
#simulation.add("Simulation","Robust Backtest","Internal",initial_investment=10000.,noise_trials=1000)#,start=0,end=400)
simulation.add("Simulation","Backtest","Internal",initial_investment=10000.)#,start=0,end=400)
simulation.add_evaluator("Evaluate","Portfolio","Internal")
#simulation_results, results, metrics, noise_results = simulation.execute()
#simulation_results, results, metrics = simulation.execute(res["Gaussian"]["RGTI"],strategy)
simulation_results = simulation.backtest(res["Gaussian"]["RGTI"],strategy)

#import matplotlib.pyplot as plt

#full = []
#for i in range(50):
#    full.append(float(noise_results[1][i]["Profit"]))  

#plt.figure()
#plt.hist(full,bins=20)

# wasserstein distance
# Includes bias and sensitivity

#w2 = np.sqrt((np.mean(hist)-float(metrics["Profit"]))**2 + np.std(hist)**2)
#w2 = np.sqrt((np.mean(full)-float(metrics["Profit"]))**2 + np.std(full)**2)/np.abs(float(metrics["Profit"]))
#evaluation = Evaluate(simulation=simulation)
"""
study = Study(simulation=simulation)
#study.add("Validation","Holdout","Internal",train_ratio=0.75)
study.add("Validation","Time Series K-Fold","Internal", n_splits=2, max_train_size=200, test_size=200)
#study.add("Optimization","Bayesian","Internal",trials=50,objectives=["Maximize Profit","Maximize Sharpe Ratio"])
study.add("Optimization","Bayesian","Internal",trials=50,objectives=["Maximize Profit"])

#in_sample_studies, in_sample_result, out_sample_result = study.execute()
in_sample_studies, in_sample_result, out_sample_result, in_sample_data, out_sample_data, in_sample_indicators, in_sample_overlays, out_sample_overlays, out_sample_indicators = study.execute()
#print(in_sample_studies[2].best_trial)

import json 
#def fetch_study_data(in_sample_studies, in_sample_result, out_sample_result, in_sample_data, out_sample_data):
    
in_sample_studies_json = [
    json.loads(study.trials_dataframe().to_json(orient="records")) for study in in_sample_studies
]

in_sample_result_json = []
in_sample_markers = []
for fold in in_sample_result:
    in_sample_result_json.append({"data": fold[0].to_json(orient="records"),
     "eval_results": fold[1].to_json(orient="records"),
     "metrics": fold[2].to_json(orient="records")})
    
out_sample_result_json = []
out_sample_markers = []
for fold in out_sample_result:
    out_sample_result_json.append({"data": fold[0].to_json(orient="records"),
     "eval_results": fold[1].to_json(orient="records"),
     "metrics": fold[2].to_json(orient="records")})
    
in_sample_data_json = [
    json.loads(data.to_json(orient="records")) for data in in_sample_data
]

out_sample_data_json = [
    json.loads(data.to_json(orient="records")) for data in out_sample_data
]
    
perm = permute_trades()
r = perm.execute(study.simulation.simulations[0].event_signals,50)


gn = gaussian_noise()
test = gn.execute(calculator.transformed_data,50)

#for noisy_series in test:
"""

"""
#import matplotlib.pyplot as plt
#import numpy as np
#plt.figure()
#plt.plot(transformed_data["sma_leading"])

#self.transformed_data["date"] = pd.to_datetime(self.transformed_data["date"])
#self.transformed_data = self.transformed_data.sort_values("date")#.reset_index(drop=True)

#plt.figure()
#plt.plot(np.array(strategy.transformed_data["close"]))
#plt.plot(np.array(transformed_data["sma_leading"]))
#plt.plot(np.array(calculator.transformed_data["sma_leading"]))
#plt.plot(np.array(strategy.transformed_data["sma_lagging"]))

#plt.figure()
#plt.plot(results["Drawdown"])
"""

#from tradinglib.modules.study.optimization import weighted_euclidean_distance_to_ideal

#best_trials = []
#for trial in in_sample_studies[3].best_trials:
#    best_trials.append(trial.values)
"""
def weighted_euclidean_distance_to_ideal_test(study_obj, weights):
    objectives = [direction.name.lower() for direction in in_sample_studies[0].directions]
    
    studies = study_obj.in_sample_studies
    
    optimals = []
    
    if len(objectives) > 1:
    
        for i,study in enumerate(studies):
            
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
            
    return optimals
    
weighted_euclidean_distance_to_ideal_test(study, weights=[0.25,0.75])
"""
#distances, optimal = weighted_euclidean_distance_to_ideal(best_trials, objectives=["maximize","maximize"], weights=[0.25,0.75])
#distances, optimal = weighted_euclidean_distance_to_ideal_test(study.in_sample_studies, objectives=["maximize","maximize"], weights=[0.25,0.75])

#simulation_results, evaluator_results, metrics = study.studies[0].run_trial(in_sample_studies[1].best_trials[optimal])

