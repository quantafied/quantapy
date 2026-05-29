#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Jun 22 10:08:30 2025

@author: andrewsimin
"""

import pandas as pd
from quantapy.core.base_simulation import BaseSimulation
from quantapy.registry.component_registry import register_component

@register_component(category="Simulation", function="Backtest", source="Internal")
class Backtest(BaseSimulation):
    """Event-style long-only backtest simulation component."""
    
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

    def generate_signals(self, data, strategy):
        """Evaluate strategy constraints on each bar and return signal rows."""
        constraints = strategy.constraints
        date_col = "date" if "date" in data.columns else None
        simulation_outputs = pd.DataFrame({
            "date": data[date_col] if date_col else data.index
        })
        signals = ["no action"] * len(data)
        strategy.event_signals = []

        for i in range(1, len(data)):
            entry_constraints = []
            exit_constraints = []

            for constraint in constraints:
                output, action, direction = constraint.check(data, i)
                if action == "enter":
                    entry_constraints.append(output)
                elif action == "exit":
                    exit_constraints.append(output)
                
            if entry_constraints and all(entry_constraints):
                signals[i] = "enter"
            elif exit_constraints and all(exit_constraints):
                signals[i] = "exit"

            if signals[i] != "no action":
                strategy.event_signals.append({
                    "index": i,
                    "action": signals[i],
                    "direction": "long",
                    "price": data.loc[i, "close"] if "close" in data.columns else None,
                })

        simulation_outputs["signal"] = signals
        
        return simulation_outputs
                
#    def simulate_returns(self,):
        
#        for i in range(0, len(self.transformed_data)): 
            
            #if self.position[0] == None and self.transformed_data["signal"] = "enter":
                
    def simulate_returns(self,simulation_outputs,data,strategy,initial_investment):
        """Apply market orders to signals and build a portfolio equity curve."""
        
        orders = strategy.orders
        price_column = "close"
        
        cash = initial_investment
        position = 0  # shares held
        entry_index = None
        entry_price = None
        entry_shares = None
        portfolio_values = []
        actions = []
        positions = []
        strategy.trades = []
        
        for i in range(len(data)):
            signal = simulation_outputs.loc[i, "signal"]
            executed_price = None
    
            # Use first matching order (can be extended to multi-order logic)
            for order in orders:
                executed_price = order.execute(data, i, signal)
                if executed_price is not None:
                    break  # stop after first matching order
    
            if signal == "enter" and executed_price and position == 0:
                position = cash / executed_price
                cash = 0
                entry_index = i
                entry_price = executed_price
                entry_shares = position
                actions.append("buy")
            elif signal == "exit" and executed_price and position > 0:
                cash = position * executed_price
                pnl_per_share = executed_price - entry_price
                pnl = entry_shares * pnl_per_share
                entry_value = entry_shares * entry_price
                pnl_pct = (pnl / entry_value) * 100 if entry_value else 0
                strategy.trades.append({
                    "entry_index": entry_index,
                    "exit_index": i,
                    "entry_price": entry_price,
                    "exit_price": executed_price,
                    "shares": entry_shares,
                    "pnl_per_share": pnl_per_share,
                    "pnl": pnl,
                    "pnl_pct": pnl_pct,
                })
                position = 0
                entry_index = None
                entry_price = None
                entry_shares = None
                actions.append("sell")
            else:
                actions.append("hold")
    
            # Portfolio value at each step
            current_price = data.loc[i, price_column]
            portfolio_value = cash + position * current_price
            portfolio_values.append(portfolio_value)
            positions.append(position)
            #print(current_price,portfolio_value)

        close_col = self.params.get("close_on_completion")
        if position > 0 and close_col in data.columns:
            final_index = len(data) - 1
            final_price = data.loc[final_index, close_col]
            cash = position * final_price
            pnl_per_share = final_price - entry_price
            pnl = entry_shares * pnl_per_share
            pnl_pct = (pnl / (entry_shares * entry_price)) * 100 if entry_price else 0
            strategy.trades.append({
                "entry_index": entry_index,
                "exit_index": final_index,
                "entry_price": entry_price,
                "exit_price": final_price,
                "shares": entry_shares,
                "pnl_per_share": pnl_per_share,
                "pnl": pnl,
                "pnl_pct": pnl_pct,
                "closed_on_completion": True,
            })
            actions[-1] = "sell"
            portfolio_values[-1] = cash
            positions[-1] = 0
            position = 0
            
        simulation_outputs["portfolio_value"] = portfolio_values
        simulation_outputs["position"] = positions
        simulation_outputs["action"] = actions
        
        return simulation_outputs
        
    def execute(self,data,strategy):
        """Run signal generation and return simulation outputs."""
        
        initial_investment = self.params["initial_investment"]
        if "date" in data.columns:
            data = data.sort_values("date").reset_index(drop=True)
        simulation_outputs = self.generate_signals(data,strategy)
        simulation_outputs = self.simulate_returns(simulation_outputs,data,strategy,initial_investment)
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
        """Run the simulation from a precomputed signal sequence."""
        
        #signals is simulation_outputs dataframe
        
        self.initial_investment = self.params["initial_investment"]
        
        self.simulation_outputs['signals'] = signals
        self.simulate_returns()
        
        #return scalar_metrics(self.simulation_outputs)
        return self.simulation_outputs
    
