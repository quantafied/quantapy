# app/ta_functions.py


import talib
from quantapy.core.base_data import BaseData
from quantapy.registry.component_registry import register_component
import pandas as pd
import numpy as np
from typing import List,Union,Type,Dict,Any
import random
import inspect

# This should be moved since permutation acts on backtest results
@register_component(category="Noise", function="Trade Permutation", source="Internal")
class permute_trades(BaseData):
    """Performs trade permutations to assess insignificance of timing"""
    
    config = {
      "title": "Trade Permutations",
      "type": "object",
      "properties": {
        "n_permutations": {
        "type": "integer",
        "default": 50,
        "description": "Number of permutation trials",
        },
      }
    }
    
    def extract_trades(self,actions: List[str]) -> List[Dict]:
        trades = []
        in_trade = False
        entry_idx = None
    
        for i, a in enumerate(actions):
            if not in_trade and a == "enter":
                entry_idx = i
                in_trade = True
    
            elif in_trade and a == "exit":
                trades.append({
                    "entry_idx": entry_idx,
                    "exit_idx": i,
                    "holding": i - entry_idx
                })
                in_trade = False
                entry_idx = None
    
        # IMPORTANT:
        # If in_trade is still True here, it is an open trade.
        # We intentionally DROP it (right-censored).
    
        return trades
    
    
    # -----------------------------
    # Step 2: Permute trades in time
    # -----------------------------
    
    def permute_trades(self,
        trades: List[Dict],
        n_bars: int,
        max_attempts: int = 1000
    ) -> List[Dict]:
        """
        Randomly reassigns entry times to entire trade blocks
        while preventing overlaps.
        """
    
        if len(trades) == 0:
            return []

        for _ in range(max_attempts):
            occupied = np.zeros(n_bars, dtype=bool)
            permuted = []
            success = True
    
            # Randomize placement order to avoid bias
            order = np.random.permutation(len(trades))
    
            for idx in order:
                trade = trades[idx]
                h = trade["holding"]
    
                valid_starts = np.arange(0, n_bars - h)
                np.random.shuffle(valid_starts)
    
                placed = False
                for start in valid_starts:
                    end = start + h
                    if not occupied[start:end].any():
                        occupied[start:end] = True
                        permuted.append({
                            "entry_idx": start,
                            "exit_idx": end,
                            "holding": h
                        })
                        placed = True
                        break
    
                if not placed:
                    success = False
                    break
    
            if success:
                return permuted
    
        raise RuntimeError("Failed to permute trades without overlap")
    
    
    # -----------------------------
    # Step 3: Rebuild action timeline
    # -----------------------------
    
    def rebuild_actions(self,permuted_trades: List[Dict], n_bars: int) -> List[str]:
        actions = np.array(["no action"] * n_bars, dtype=object)
    
        for t in permuted_trades:
            actions[t["entry_idx"]] = "enter"
            actions[t["exit_idx"]] = "exit"
    
        return actions.tolist()
    
    
    # -----------------------------
    # Convenience wrapper
    # -----------------------------
    
    def permute_action_sequence(self,actions: List[str]) -> List[str]:
        n = len(actions)
        trades = self.extract_trades(actions)
        permuted_trades = self.permute_trades(trades, n)
        return self.rebuild_actions(permuted_trades, n)
    
    def compute(self, actions, n_trajectories=50):
        
        peturbed_time_series = []
        
        for _ in range(n_trajectories):
            
            peturbed_time_series.append(self.permute_action_sequence(actions))
        
        return peturbed_time_series
    
@register_component(category="Noise", function="Gaussian", source="Internal")
class gaussian_noise(BaseData):
    
    config = {
        "title": "Gaussian Noise",
        "type": "object",
        "properties": {
            "mean": {
                "type": "number",
                "default": 0.0,
                "description": "Mean",
                "advanced": False,
            },
            "stddev": {
                "type": "number",
                "default": 1.0,
                "description": "Standard Deviation",
                "advanced": False,
            },
            "n_trajectories": {
                "type": "integer",
                "default": 50,
                "description": "Number of Synthetic Trajectories",
                "advanced": False,
            },
        }
    }
    
    def execute(self, original_time_series_dict, mean=0.0, stddev=1.0, n_trajectories=50):
        """
        Adds Gaussian noise to a time series.
    
         Options:
         time_series (array-like): A time series to which noise is added.
         mean (float): The average value of the noise. Default is 0.0.
         stddev (float): Standard deviation of noise. Default is 1.0.
    
         Returns:
         noisy_series (np.array): Time series with added noise
         """
         
        print(self.params["mean"],self.params["stddev"])
         
        noisy_series = {}
        
        for asset, original_time_series in original_time_series_dict.items():
        
            noisy_time_series = []
            
            for _ in range(self.params["n_trajectories"]):
                
                #time_series = original_time_series
                time_series = original_time_series[0].copy(deep=True)
            
                # Gaussian noise generation
                noise = pd.Series(np.random.normal(self.params["mean"], self.params["stddev"], len(time_series)))
                #noisy_columns = time_series.select_dtypes(exclude=["datetime64[ns]"]).columns
                noisy_columns = ["open", "high", "low", "close", "volume"]
                time_series[noisy_columns] = time_series[noisy_columns].add(noise, axis=0)
                noisy_time_series.append(time_series)
                print("TIME SERIES")
                print(time_series)
                
            noisy_series[asset] = noisy_time_series
        
        return noisy_series
