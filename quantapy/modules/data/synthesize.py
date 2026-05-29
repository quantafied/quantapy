"""
Generic data augmentation transformers.

These transformers generate synthetic versions of data for:
- Robustness testing
- Confidence interval estimation
- Data augmentation for ML
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Any, Optional

from quantapy.data.providers.base import BaseTransformer
from quantapy.core.timeseries import TimeSeries
from quantapy.registry.component_registry import register_component


@register_component(category="Noise", function="GaussianNoise", source="Internal")
class GaussianNoise(BaseTransformer):
    """
    Generate synthetic trajectories by adding Gaussian noise.
    
    Works with any numeric data (OHLC, temperature, sensor values, etc.).
    
    Parameters:
        n_trajectories: number of synthetic versions to generate (default: 5)
        mean: mean of noise distribution (default: 0.0)
        stddev: standard deviation of noise (default: 0.01)
        numeric_only: if True, add noise only to numeric columns (default: True)
    """
    
    def __init__(self, **kwargs):
        """Initialize Gaussian noise parameters with defaults."""
        defaults = {
            "n_trajectories": 5,
            "mean": 0.0,
            "stddev": 0.01,
            "numeric_only": True,
        }
        defaults.update(kwargs)
        super().__init__(**defaults)
    
    def execute(self, data_dict: Dict[str, List[Any]]) -> Dict[str, List[Any]]:
        """
        Generate synthetic trajectories by adding Gaussian noise.
        
        Args:
            data_dict: {dataset_name: [TimeSeries or DataFrame]}
        
        Returns:
            {dataset_name: [synthetic_copy_1, synthetic_copy_2, ...]}
        """
        result = {}
        n_traj = self.params["n_trajectories"]
        mean = self.params["mean"]
        stddev = self.params["stddev"]
        numeric_only = self.params["numeric_only"]
        
        for name, data_list in data_dict.items():
            trajectories = []
            
            for data_item in data_list:
                # Convert to DataFrame if needed
                if isinstance(data_item, TimeSeries):
                    df = data_item.to_dataframe()
                else:
                    df = data_item
                
                # Generate n_traj synthetic versions
                for _ in range(n_traj):
                    synthetic_df = df.copy()
                    
                    # Select columns to augment
                    if numeric_only:
                        numeric_cols = synthetic_df.select_dtypes(
                            include=[np.number]
                        ).columns
                    else:
                        numeric_cols = synthetic_df.columns
                    
                    # Add Gaussian noise to selected columns
                    for col in numeric_cols:
                        noise = np.random.normal(
                            mean, stddev, len(synthetic_df)
                        )
                        synthetic_df[col] = synthetic_df[col] + noise
                    
                    # Convert back to TimeSeries if input was TimeSeries
                    if isinstance(data_item, TimeSeries):
                        synthetic_df = TimeSeries.from_dataframe(synthetic_df)
                    
                    trajectories.append(synthetic_df)
            
            result[name] = trajectories
        
        return result


@register_component(category="Noise", function="TradePermutation", source="Internal")
class TradePermutation(BaseTransformer):
    """
    Generate synthetic action sequences by permuting trade timing.
    
    Takes action sequences ["enter", "exit", "no action", ...] and randomly
    reassigns entry/exit times while preserving trade statistics.
    
    Parameters:
        n_trajectories: number of permuted sequences to generate (default: 50)
    """
    
    def __init__(self, **kwargs):
        """Initialize trade permutation parameters with defaults."""
        defaults = {"n_trajectories": 50}
        defaults.update(kwargs)
        super().__init__(**defaults)
    
    def extract_trades(self, actions: List[str]) -> List[Dict]:
        """Extract trade blocks from action sequence."""
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
        
        # Drop unclosed trades (right-censored)
        return trades
    
    def permute_trades(
        self, trades: List[Dict], n_bars: int, max_attempts: int = 1000
    ) -> List[Dict]:
        """Randomly reassign entry times while preventing overlaps."""
        if not trades:
            return []
        
        for _ in range(max_attempts):
            occupied = np.zeros(n_bars, dtype=bool)
            permuted = []
            success = True
            
            # Randomize placement order
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
    
    def rebuild_actions(self, permuted_trades: List[Dict], n_bars: int) -> List[str]:
        """Reconstruct action sequence from trade blocks."""
        actions = np.array(["no action"] * n_bars, dtype=object)
        
        for t in permuted_trades:
            actions[t["entry_idx"]] = "enter"
            actions[t["exit_idx"]] = "exit"
        
        return actions.tolist()
    
    def execute(self, data_dict: Dict[str, List[Any]]) -> Dict[str, List[Any]]:
        """
        Generate permuted action sequences.
        
        Args:
            data_dict: {dataset_name: [action_list]}
                      where action_list is List[str] of ["enter", "exit", "no action", ...]
        
        Returns:
            {dataset_name: [permuted_1, permuted_2, ...]}
        """
        result = {}
        n_traj = self.params["n_trajectories"]
        
        for name, data_list in data_dict.items():
            trajectories = []
            
            for actions in data_list:
                # Extract trades from original sequence
                trades = self.extract_trades(actions)
                
                # Generate n_traj permuted versions
                for _ in range(n_traj):
                    permuted_trades = self.permute_trades(trades, len(actions))
                    permuted_actions = self.rebuild_actions(permuted_trades, len(actions))
                    trajectories.append(permuted_actions)
            
            result[name] = trajectories
        
        return result
