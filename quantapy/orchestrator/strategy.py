#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Jun 11 22:09:29 2025

@author: andrewsimin
"""

# Data and Calculator are passed to strategy since they can be separate from the
# strategy pipeline like all other stock software

# Calculator is a non-extendable component and is primarily for managing 
# multiple transformation components which are extendable

from quantapy.registry.component_registry import COMPONENT_REGISTRY
from quantapy.utils.loader import load_plugins_from_folder
from typing import get_args, get_origin, List, Union, Dict
import pandas as pd
import optuna
from quantapy.modules.evaluation.metrics import *
import json

#import calculator
        
class Strategy():
    
    def __init__(self, calculator, store=None):
        """
        Initialize strategy with Calculator and DataStore.
        
        Args:
            calculator: Calculator v2 instance for managing transforms
            store: DataStore instance (Dict[name, TimeSeries]) with derived data
        """
        self.calculator = calculator
        self.store = store  # DataStore: Dict[dataset_name, TimeSeries]
        self.constraints = []  # List of signal objects
        self.orders = []
        self.event_signals = []       # Store triggered signals
        self.transform_dependencies = []
        self.strategy_conditions = {}
        
        self.initial_investment = 1000.
        self.portfolio_weights = [1.]
        self.position = [False]
        self.open_orders = [False]
        self.trades = []

    def add(self, registered: str, function: str, source: str = "Internal", **kwargs):
        """
        Add a signal or order to the strategy.
        
        Note: Transforms (indicators) should be added to Calculator v2 directly
        using calculator.add_transform() BEFORE creating the Strategy instance.
        """
        strategy_class = COMPONENT_REGISTRY[registered][function][source]
        # Create instance without config parameter - let class handle params
        instance = strategy_class(**kwargs)
        
        # Careful that the registry groups match this syntax
        if registered == "Signal":
            self.constraints.append(instance)
            
            # Track transform dependencies from signal params
            if hasattr(instance, 'params'):
                instance_inputs = list(instance.params.values())
                for inputs in instance_inputs:
                    self.transform_dependencies.append(inputs)
                
            self.condition_to_index()
                
        elif registered == "Order":
            self.orders.append(instance)
            self.order_to_index()
            
    def save(self):
        """Save strategy signals and orders to JSON files."""
        self.constraints_state = []
        self.orders_state = []
        
        for value in self.constraints:
            if hasattr(value, 'params'):
                self.constraints_state.append(value.params)
            elif hasattr(value, 'payload'):
                self.constraints_state.append(value.payload)
                
        for value in self.orders:
            if hasattr(value, 'params'):
                self.orders_state.append(value.params)
            elif hasattr(value, 'payload'):
                self.orders_state.append(value.payload)
        
        with open("constraints.json", "w") as f:
            json.dump(self.constraints_state, f, indent=2)
        with open("orders.json", "w") as f:
            json.dump(self.orders_state, f, indent=2)
            
    def load(self):
        """Load strategy signals and orders from JSON files."""
        try:
            with open("constraints.json", "r") as f:
                loaded_constraints = json.load(f)
        except FileNotFoundError:
            print("constraints.json not found")
            loaded_constraints = []
            
        try:
            with open("orders.json", "r") as f:
                loaded_orders = json.load(f)
        except FileNotFoundError:
            print("orders.json not found")
            loaded_orders = []
            
        for params in loaded_constraints:
            signal_type = params.get("name", "Crossover")
            strategy_class = COMPONENT_REGISTRY["Signal"][signal_type]["Internal"]
            instance = strategy_class(**params)
            
            self.constraints.append(instance)
            
            # Track dependencies
            if hasattr(instance, 'params'):
                instance_inputs = list(instance.params.values())
                for inputs in instance_inputs:
                    self.transform_dependencies.append(inputs)
                
            self.condition_to_index()
            
        for params in loaded_orders:
            order_type = params.get("name", "Market")
            strategy_class = COMPONENT_REGISTRY["Order"][order_type]["Internal"]
            instance = strategy_class(**params)
            
            self.orders.append(instance)
            self.order_to_index()
        
    def update_condition(self, name: str, **new_params):
        """Update a signal condition with new parameters."""
        if name not in self.strategy_conditions:
            raise ValueError(f"No condition at index '{name}' found.")
        
        old_signal = self.strategy_conditions[name]
        # Create new instance with updated params
        updated_params = {}
        if hasattr(old_signal, 'params'):
            updated_params.update(old_signal.params)
        updated_params.update(new_params)
        
        # Reconstruct the signal using the same class
        signal_class = type(old_signal)
        new_instance = signal_class(**updated_params)
        
        self.constraints[int(name)] = new_instance
        self.strategy_conditions[name] = new_instance
        self.condition_to_index()
            
    def condition_to_index(self):
        """Map conditions (signals) to indices."""
        self.strategy_conditions = {}
        
        for i, constraint in enumerate(self.constraints):
            self.strategy_conditions[int(i)] = constraint
            
        return self.strategy_conditions
    
    def remove_condition(self, operation):
        """Remove a signal condition."""
        self.constraints = [obj for obj in self.constraints if obj is not self.strategy_conditions[operation]]
        self.condition_to_index()
    
    def update_order(self, name: str, **new_params):
        """Update an order with new parameters."""
        if name not in self.strategy_orders:
            raise ValueError(f"No order at index '{name}' found.")
        
        old_order = self.strategy_orders[name]
        # Create new instance with updated params
        updated_params = {}
        if hasattr(old_order, 'params'):
            updated_params.update(old_order.params)
        updated_params.update(new_params)
        
        # Reconstruct the order using the same class
        order_class = type(old_order)
        new_instance = order_class(**updated_params)
        
        self.orders[int(name)] = new_instance
        self.strategy_orders[name] = new_instance
        self.order_to_index()
        
    def order_to_index(self):
        """Map orders to indices."""
        self.strategy_orders = {}
        
        for i, order in enumerate(self.orders):
            self.strategy_orders[int(i)] = order
            
        return self.strategy_orders
    
    def remove_order(self, operation):
        """Remove an order."""
        self.orders = [obj for obj in self.orders if obj is not self.strategy_orders[operation]]
        self.order_to_index()
        
        
    def get_optimizable(self):
        """
        Get list of optimizable transforms from the Calculator.
        
        In the new architecture, use Calculator v2's list_transforms()
        to get all registered transforms.
        """
        self.optimizable_functions = []
        
        # Get all transforms registered with Calculator v2
        transforms = self.calculator.list_transforms()
        
        # All transforms are optimizable if they depend on strategy signals
        for name, transform_info in transforms.items():
            # Check if transform outputs are used by strategy
            if any(name in self.transform_dependencies for name in self.transform_dependencies):
                self.optimizable_functions.append(name)
        
        # If no specific dependencies, all are optimizable
        if not self.optimizable_functions:
            self.optimizable_functions = list(transforms.keys())
                
        return self.optimizable_functions
    
    def get_config(self):
        """Get strategy configuration."""
        return self

    def _get_dataset_name(self, dataset_name: str = None) -> str:
        """Resolve the dataset to use for strategy logic."""
        if dataset_name is not None:
            return dataset_name

        if self.store is None:
            return None

        datasets = self.store.list()
        for candidate in ["OHLC_AAPL-AllIndicators", "OHLC_AAPL", "OHLC_RGTI-AllIndicators", "OHLC_RGTI"]:
            if candidate in datasets:
                return candidate

        return datasets[0] if datasets else None

    def _get_dataframe(self, dataset_name: str = None) -> pd.DataFrame:
        """Get a DataFrame from the active DataStore."""
        if self.store is None:
            return None

        resolved_name = self._get_dataset_name(dataset_name)
        if resolved_name is None:
            return None

        return self.store.to_dataframe(resolved_name)

    def _calculate_scalar_metrics(self):
        """Return a small set of scalar metrics for optimization."""
        if not hasattr(self, "trades"):
            self.trades = []

        total_profit = sum(float(trade.get("pnl", 0.0)) for trade in self.trades)
        num_trades = len(self.trades)

        return {
            "Profit": total_profit,
            "Trades": num_trades,
            "Average PnL": total_profit / num_trades if num_trades else 0.0,
        }
                
    def objective(self, trial):
        """
        Objective function for Optuna optimization.
        
        Tries different parameter combinations and evaluates strategy performance.
        Works with the new DataStore/Calculator v2 architecture.
        """
        print(f"TRIAL: {trial}")
        
        # Get optimizable transforms
        self.get_optimizable()
        
        # For each optimizable transform, suggest parameters
        transform_list = self.calculator.list_transforms()
        
        for optimizable in self.optimizable_functions:
            if optimizable in transform_list:
                # Get the transform configuration to find optimizable params
                transform_info = transform_list[optimizable]
                
                # For now, suggest some basic parameters
                # You can extend this to read from config.optimizable if available
                # Example: suggest timeperiod for moving average
                if "timeperiod" in str(transform_info):
                    suggestion = trial.suggest_int(f"{optimizable}_timeperiod", 5, 50)
                    # Note: In the new architecture, you'd update the calculator
                    # by re-adding the transform with new parameters
        
        # Generate signals from current data
        self.generate_signals()
        
        # Simulate returns
        self.simulate_returns()
        
        # Calculate metrics from the results
        metrics = self._calculate_scalar_metrics()
        
        objectives = ["Profit"]
        objective_list = []
        for obj in objectives:
            objective_list.append(metrics.get(obj, 0.0))
            
        return tuple(objective_list)
    
    def optimize(self):
        """
        Run Optuna optimization to find best strategy parameters.
        """
        directions = ["maximize"]
        n_trials = 20
        
        file_path = "./optuna_journal_storage.log"
        storage = optuna.storages.JournalStorage(
            optuna.storages.journal.JournalFileBackend(file_path)
        )
        
        sampler_algo = optuna.samplers.TPESampler()
        
        study = optuna.create_study(
            storage=f"sqlite:///asimin.sqlite3",
            directions=directions,
            sampler=sampler_algo
        )

        study.optimize(self.objective, n_trials=n_trials)
    
    def generate_signals(self, dataset_name: str = None):
        """
        Generate trading signals from the current data.
        
        Uses all registered Signal objects to detect entry/exit conditions.
        Stores triggered signals in self.event_signals.
        
        Args:
            dataset_name: Name of dataset in store to use. If None, uses first available.
        """
        if self.store is None or len(self.store.list()) == 0:
            print("No data available in store")
            return

        df = self._get_dataframe(dataset_name)
        if df is None:
            print("No datasets found in store")
            return
        
        self.event_signals = []
        
        # Process each bar in the data
        for index in range(1, len(df)):
            # Check each signal
            for signal in self.constraints:
                try:
                    signal_triggered, action, direction = signal.check(df, index)
                    if signal_triggered:
                        self.event_signals.append({
                            'index': index,
                            'action': action,
                            'direction': direction,
                            'signal': signal,
                            'price': df.loc[index, 'close'] if 'close' in df.columns else None
                        })
                except Exception as e:
                    print(f"Error checking signal: {e}")
    
    def simulate_returns(self, dataset_name: str = None):
        """
        Simulate trading returns based on generated signals and orders.
        
        Processes each signal by executing orders and tracking P&L.
        
        Args:
            dataset_name: Name of dataset in store to use. If None, uses first available.
        """
        if self.store is None or len(self.store.list()) == 0:
            print("No data available in store")
            return

        df = self._get_dataframe(dataset_name)
        if df is None:
            return
        
        # Reset position state
        self.position = [False]
        self.open_orders = [False]
        self.entry_price = None
        self.entry_index = None
        self.trades = []
        
        # Process each signal
        for signal_event in self.event_signals:
            index = signal_event['index']
            action = signal_event['action']
            direction = signal_event['direction']
            
            # Check if we should enter or exit
            if action == "enter" and not self.position[0]:
                # Find matching order to execute
                for order in self.orders:
                    try:
                        fill_price = order.execute(df, index, action)
                        if fill_price is not None:
                            self.entry_price = fill_price
                            self.entry_index = index
                            self.position[0] = True
                            print(f"ENTRY at index {index}, price {fill_price}")
                            break
                    except Exception as e:
                        print(f"Error executing order: {e}")
                        
            elif action == "exit" and self.position[0]:
                # Execute exit order
                for order in self.orders:
                    try:
                        fill_price = order.execute(df, index, action)
                        if fill_price is not None:
                            pnl = fill_price - self.entry_price
                            pnl_pct = (pnl / self.entry_price) * 100 if self.entry_price else 0
                            self.position[0] = False
                            self.trades.append({
                                'entry_index': self.entry_index,
                                'exit_index': index,
                                'entry_price': self.entry_price,
                                'exit_price': fill_price,
                                'pnl': pnl,
                                'pnl_pct': pnl_pct
                            })
                            print(f"EXIT at index {index}, price {fill_price}, P&L {pnl:.2f} ({pnl_pct:.2f}%)")
                            break
                    except Exception as e:
                        print(f"Error executing exit order: {e}")
