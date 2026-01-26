#!/usr/bin/env_test python3
# -*- coding: utf-8 -*-
"""
Created on Thu Jun  5 23:55:06 2025

@author: andrewsimin
"""

#import sys
#sys.path.append("/home/andrewsimin/automating_alpha")

from tradinglib.registry.component_registry import COMPONENT_REGISTRY
from tradinglib.utils.loader import load_plugins_from_folder
from pydantic import BaseModel
from typing import get_args, get_origin, List
from tradinglib.modules.evaluation.metrics import *
import numpy as np


# Composition Classes - can not be extended themselves, only their submodules can
from tradinglib.orchestrator.data import Data
from tradinglib.orchestrator.calculator import Calculator
from tradinglib.orchestrator.strategy import Strategy
from tradinglib.orchestrator.simulate import Simulate
from tradinglib.orchestrator.study import Study

"""We need to mutate parameters before sending to any parallel function"""

    
#load_plugins_from_folder("/home/andrewsimin/tradinglib/plugins")
load_plugins_from_folder("/home/andrewsimin/automating_alpha/v0.0.3/tradinglib/modules/strategy")
load_plugins_from_folder("/home/andrewsimin/automating_alpha/v0.0.3/tradinglib/modules/simulation")
load_plugins_from_folder("/home/andrewsimin/automating_alpha/v0.0.3/tradinglib/modules/data")
load_plugins_from_folder("/home/andrewsimin/automating_alpha/v0.0.3/tradinglib/modules/calculator")
load_plugins_from_folder("/home/andrewsimin/automating_alpha/v0.0.3/tradinglib/modules/study")

print(COMPONENT_REGISTRY)

# DataWarehouse is an orchestrator class that calls specific classes for each type of data we want stored
data_warehouse = DataWarehouse()
# add_market() calls the MarketData() class
data_warehouse.add_market("Market","OHLC","Internal", ticker="RGTI",period="1 year")
data_warehouse.add_market("Market","OHLC","Internal", ticker="AAPL",period="1 year")
# add_augmentation() calls the AugmentData() class
data_warehouse.add_augmentation("Noise", "Gaussian", "Internal", data_name="RGTI", mean=0.0, stddev=0.5, n_trajectories=1000)
# add_synthetic() calls the SyntheticData() class
data_warehouse.add_synthetic("Synthetic", "Brownian Motion", "Internal", data_name = "My Synthetic Data", mean=0.0, stddev=0.5)
data_warehouse.add_augmentation("Noise", "Gaussian", "Internal", data_name="My Synthetic Data", mean=0.0, stddev=0.5, n_trajectories=1000)
data_warehouse.fetch_data()

data_tranformations = DataTransformations()
data_tranformations.add_transform("Technical","Moving Average",ticker="RGTI",name="SMA_LEADING",timeperiod=62,output_names={"output":"sma_leading"})
data_tranformations.add_transform("Technical","Moving Average",ticker="RGTI",name="SMA_LAGGING",timeperiod=90,output_names={"output":"sma_lagging"})
res = data_transformations.apply_transformations_(data_warehouse.data) # This is fine for data exploration
# but for the workflow we want to declare them and not execute them quite yet

# Add data
strategy = Strategy()

strategy.create_strategy("Strategy","Rule Based",name="Crossover Strategy")
strategy.add_signal("Signal","Crossover", strategy_name="Crossover Strategy", name="Crossover", asset1="RGTI", value1="sma_leading", asset1="AAPL", value2="sma_lagging",action="enter", action_on_asset="RGTI", direction="long")
strategy.add_signal("Signal","Crossunder", strategy_name="Crossover Strategy",name="Crossover", asset1="RGTI", value1="sma_leading", asset1="AAPL", value2="sma_lagging",action="exit", action_on_asset="RGTI", direction="long")
strategy.add_order("Order", "Market", strategy_name="Crossover Strategy", on_signal="entry", on_bar="close")
strategy.add_order("Order", "Market", strategy_name="Crossover Strategy", on_signal="exit", on_bar="close")  # or stop with trailing params
strategy.add_fees("Fee", "Fixed Percentage", strategy_name="Crossover Strategy", value=0.01) 
strategy.add_slippage("Slippage", "Fixed Percentage", strategy_name="Crossover Strategy", value=0.01) 

portfolio = Portfolio()
portfolio.add_strategy(name="Crossover",weight=1)

# Got this far but now I dont know where simulation backtest, validation and optimization come into play
# Below was the origina design but please help

simulation = Simulate(strategy=strategy)
#simulation.add("Simulation","Robust Backtest","Internal",initial_investment=10000.,noise_trials=1000)#,start=0,end=400)
simulation.add_engine("Simulation","Backtest","Internal",initial_investment=10000.)#,start=0,end=400)
simulation.add_evaluator("Evaluate","Portfolio","Internal",aggregate="mean")


study = Study(simulation=simulation)
#study.add("Validation","Holdout","Internal",train_ratio=0.75)
study.add("Validation","Time Series K-Fold","Internal", n_splits=2, max_train_size=200, test_size=200)
#study.add("Optimization","Bayesian","Internal",trials=50,objectives=["Maximize Profit","Maximize Sharpe Ratio"])
study.add("Optimization","Bayesian","Internal",trials=50,objectives=["Maximize Profit"])

#in_sample_studies, in_sample_result, out_sample_result = study.execute()
in_sample_studies, in_sample_result, out_sample_result, in_sample_data, out_sample_data, in_sample_indicators, in_sample_overlays, out_sample_overlays, out_sample_indicators = study.execute()
#print(in_sample_studies[2].best_trial)

