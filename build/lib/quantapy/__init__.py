import sys
sys.path.append("/home/andrewsimin/automating_alpha/v0.0.3")
from fastapi import FastAPI, HTTPException
from uuid import uuid4
from tradinglib.orchestrator.data import Data
from tradinglib.utils.loader import load_plugins_from_folder
from tradinglib.registry.component_registry import COMPONENT_REGISTRY
from fastapi.middleware.cors import CORSMiddleware

from pydantic import BaseModel
from typing import get_args, get_origin, List
#from pydantic_form import default_payload
#from tview import line_plot
#import calculator
from tradinglib.modules.evaluation.metrics import *
import pandas as pd

# Composition Classes - can not be extended themselves, only their submodules can
from tradinglib.orchestrator.data import Data
from tradinglib.orchestrator.calculator import Calculator
from tradinglib.orchestrator.strategy import Strategy
from tradinglib.orchestrator.simulate import Simulate
from tradinglib.orchestrator.study import Study

load_plugins_from_folder("/home/andrewsimin/automating_alpha/v0.0.3/tradinglib/modules/strategy")
load_plugins_from_folder("/home/andrewsimin/automating_alpha/v0.0.3/tradinglib/modules/simulation")
load_plugins_from_folder("/home/andrewsimin/automating_alpha/v0.0.3/tradinglib/modules/data")
load_plugins_from_folder("/home/andrewsimin/automating_alpha/v0.0.3/tradinglib/modules/calculator")
load_plugins_from_folder("/home/andrewsimin/automating_alpha/v0.0.3/tradinglib/modules/study")

# Main entrypoint

class TradingLib():
    
    def __init__(self):
        
        self.data = Data("")
        self.calculator = Calculator(pd.DataFrame())
        self.strategy = Strategy(self.calculator)
        self.simulate = Simulate(self.strategy)
        self.study = Study(self.simulate)
        
