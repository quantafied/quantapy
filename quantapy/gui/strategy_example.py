#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Strategy Integration Example with New Architecture

This demonstrates how to use the updated Strategy class with:
- Calculator v2 for managing technical indicators
- DataStore for managing derived data
- Signal and Order objects for trading logic

"""

from quantapy.registry.component_registry import COMPONENT_REGISTRY
from quantapy.utils.loader import load_plugins_from_folder
from quantapy.orchestrator.data import Data
from quantapy.orchestrator.calculator import Calculator
from quantapy.orchestrator.strategy import Strategy
from quantapy.orchestrator.simulate import Simulate
from quantapy.orchestrator.study import Study
from quantapy.core.timeseries import DataStore, TimeSeries
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from pathlib import Path

# Load all plugins
PACKAGE_ROOT = Path(__file__).resolve().parents[1]
load_plugins_from_folder(str(PACKAGE_ROOT / "modules" / "strategy"))
load_plugins_from_folder(str(PACKAGE_ROOT / "modules" / "simulation"))
load_plugins_from_folder(str(PACKAGE_ROOT / "modules" / "data"))
load_plugins_from_folder(str(PACKAGE_ROOT / "data" / "providers"))
load_plugins_from_folder(str(PACKAGE_ROOT / "modules" / "calculator"))
load_plugins_from_folder(str(PACKAGE_ROOT / "modules" / "study"))

data = Data()
data.add_provider("Market", "OHLC", "FMP", source_ids=["AAPL"], interval="1hour", period="3mo")
store = DataStore()
fetched_data = data.fetch()

for dataset_name, dataset in fetched_data.items():
    store.add_raw(
        dataset_name,
        dataset,
        source={"provider": "OHLC"},
        attrs={"symbol": dataset_name.replace("OHLC_", ""), "artifact": "source"},
    )

aapl_data = store.get("OHLC_AAPL")

calc = Calculator()

# Add SMA (faster moving average)
calc.add_transform(
    category="Technical",
    function="Moving Average",
    source="Internal",
    name="Leading",
    timeperiod=20,
    real="close",
    output_names={"output": "Leading"},
    display="Overlay"
)

# Add another SMA (slower moving average) for crossover signals
calc.add_transform(
    category="Technical",
    function="Moving Average",
    source="Internal",
    name="Lagging",
    timeperiod=50,
    real="close",
    output_names={"output": "Lagging"},
    display="Overlay"
)

all_indicators = calc.derive_combined(store, "OHLC_AAPL")
store.add_child(
    "OHLC_AAPL-AllIndicators",
    all_indicators,
    parent_ids=["OHLC_AAPL"],
    kind="derived",
    attrs={"symbol": "AAPL", "artifact": "indicators", "indicator_set": "AllIndicators"},
    transform={"name": "AllIndicators", "transforms": calc.list_transforms()},
)

# Generate synthetic AAPL datasets with Gaussian noise.
data.add_transformer(
    "Noise",
    "GaussianNoise",
    "Internal",
    n_trajectories=3,
    mean=0.0,
    stddev=0.015,
)
synthetic_outputs = data.transform("OHLC_AAPL", store.get("OHLC_AAPL"))

for synth_name, synth_data in synthetic_outputs.items():
    store.add_child(
        synth_name,
        synth_data,
        parent_ids=["OHLC_AAPL"],
        kind="synthetic",
        attrs={"symbol": "AAPL", "artifact": "source", "synthetic": True},
        transform={"name": "GaussianNoise"},
    )

# Apply the same indicators to every noisy dataset.
for record in store.synthetic():
    noisy_indicators = calc.derive_combined(store, record.name)
    store.add_child(
        f"{record.name}-AllIndicators",
        noisy_indicators,
        parent_ids=[record.id],
        kind="derived",
        attrs={
            "symbol": "AAPL",
            "artifact": "indicators",
            "indicator_set": "AllIndicators",
            "synthetic": True,
        },
        transform={"name": "AllIndicators", "transforms": calc.list_transforms()},
    )

print("\nDATASTORE CONTENTS")
print("=" * 80)
for record in store.records():
    parent_names = [parent.name for parent in store.parents(record.id)]
    print(
        f"{record.kind:9} | {record.name:40} | "
        f"shape={record.data.shape} | parents={parent_names}"
    )

print("\nRaw datasets:       ", [record.name for record in store.raw()])
print("Synthetic datasets: ", [record.name for record in store.synthetic()])
print("Derived datasets:   ", [record.name for record in store.derived()])
print("AAPL lineage:       ", store.lineage("OHLC_AAPL"))

# Create strategy instance with Calculator and DataStore
strategy = Strategy(calc, store=store)

# Add Entry Signal: SMA_20 crosses above SMA_50 (bullish crossover)
strategy.add(
    "Signal", 
    "Crossover",
    value1="Leading",
    value2="Lagging",
    action="enter",
    direction="long"
)

# Add Exit Signal: SMA_20 crosses below SMA_50 (bearish crossunder)
strategy.add(
    "Signal",
    "Crossunder",
    value1="Leading",
    value2="Lagging",
    action="exit",
    direction="long"
)

strategy.add(
    "Order",
    "Market",
    on_signal="entry",
    on_price="close",
    on_bar="current"
)

strategy.add(
    "Order",
    "Market",
    on_signal="exit",
    on_price="close",
    on_bar="current"
)

simulation = Simulate(strategy=strategy, store=store)
simulation.add("Simulation", "Backtest", "Internal", initial_investment=10000)
simulation.add_evaluator("Evaluate", "Portfolio", "Internal")

# ============================================================================
# Optimization Parameter Selection
# ============================================================================
print("\nOPTIMIZATION PARAMETER SETUP")
print("=" * 80)

study = Study(
    simulation=simulation,
    store=store,
    calculator=calc,
    strategy=strategy,
)

print("Discoverable optimization candidates:")
for candidate in study.discover_parameters():
    outputs = candidate.get("outputs")
    used_by_strategy = candidate.get("used_by_strategy")
    dependency_note = (
        f" outputs={outputs} used_by_strategy={used_by_strategy}"
        if outputs is not None
        else ""
    )
    print(
        f"- {candidate['target']} "
        f"{candidate['name'] if candidate['name'] is not None else candidate['index']}."
        f"{candidate['param']} default={candidate['default']} "
        f"bounds=({candidate['low']}, {candidate['high']}) "
        f"choices={candidate['choices']}"
        f"{dependency_note}"
    )

# Indicator parameters target transform names, not output columns.
# Discovery maps strategy-used outputs back to their parent transforms.
study.add_parameter(
    target="Transform",
    name="Leading",
    param="timeperiod",
    dtype="integer",
    low=5,
    high=40,
)
study.add_parameter(
    target="Transform",
    name="Lagging",
    param="timeperiod",
    dtype="integer",
    low=20,
    high=120,
)

# Strategy parameters: explicitly selected from the strategy definition.
#study.add_parameter(
#    target="Signal",
#    index=0,
#    param="value1",
#    dtype="categorical",
#    choices=["sma_20", "sma_50", "close"],
#)
#study.add_parameter(
#    target="Signal",
#    index=0,
#    param="value2",
#    dtype="categorical",
#    choices=["sma_20", "sma_50", "close"],
#)
#study.add_parameter(
#    target="Order",
#    index=0,
#    param="on_bar",
#    dtype="categorical",
#    choices=["current", "next"],
#)

print("\nEnabled optimization parameters:")
for parameter in study.list_parameters():
    print(f"- {parameter}")

study.add("Validation", "Holdout", "Internal", train_ratio=0.75)
study.add("Best Trial", "Distance from Ideal", "Internal", weights=[0.75, 0.25])

optimizer = study.add(
    "Optimization",
    "Bayesian",
    "Internal",
    trials=100,
    objectives=["Maximize Profit", "Maximize Sharpe Ratio"],
    storage="sqlite:///asimin.sqlite3",
)

validation_results = optimizer.execute_validated(
    study=study,
    source_dataset="OHLC_AAPL",
    derived_name="OHLC_AAPL-AllIndicators",
)
optimization_results = validation_results[-1]
run_id = optimization_results["run_id"]
simulation_results = optimization_results["test"]["simulation_results"]
portfolio_outputs = optimization_results["test"]["evaluator_outputs"]
portfolio_metrics = optimization_results["test"]["metrics"]

print("\nSELECTED OPTUNA TRIAL")
print("=" * 80)
print(f"Values: {optimization_results['best_trial'].values}")
print(f"Params: {optimization_results['best_trial'].params}")

print("\nOPTUNA TRIALS")
print("=" * 80)
print(optimization_results["trials"].tail().to_string(index=False))

print("\nPORTFOLIO METRICS")
print("=" * 80)
print("Train:")
print(optimization_results["train"]["metrics"].to_string(index=False))
print("\nHeld out:")
print(portfolio_metrics.to_string(index=False))
final_profit = float(portfolio_metrics["Profit"].iloc[0])
print(f"\nHeld-out optimized backtest profit: ${final_profit:.2f}")

print("\nDATASTORE CONTENTS AFTER BACKTEST")
print("=" * 80)
for record in store.records():
    parent_names = [parent.name for parent in store.parents(record.id)]
    print(
        f"{record.kind:9} | {record.name:40} | "
        f"shape={record.data.shape} | parents={parent_names}"
    )

# Display trade results
if hasattr(strategy, 'trades') and strategy.trades:
    print(f"  ✓ Completed {len(strategy.trades)} trade(s)")
    for i, trade in enumerate(strategy.trades):
        print(f"\n     Trade {i+1}:")
        print(f"       Entry:  index {trade['entry_index']}, price ${trade['entry_price']:.2f}")
        print(f"       Exit:   index {trade['exit_index']}, price ${trade['exit_price']:.2f}")
        print(f"       Shares: {trade.get('shares', 0):.4f}")
        print(f"       P&L:    ${trade['pnl']:.2f} ({trade['pnl_pct']:.2f}%)")
        if trade.get("closed_on_completion"):
            print("       Note:   closed on final bar")
else:
    print("  ✗ No completed trades")

# ============================================================================
# Step 7: Visualize Results
# ============================================================================
print("\n[7] Visualizing strategy execution...")

fig, axes = plt.subplots(
    len(validation_results),
    2,
    figsize=(18, 6 * len(validation_results)),
    squeeze=False,
)

for row, fold_result in zip(axes, validation_results):
    fold = fold_result["fold"]
    plot_specs = [
        ("Train", "train", fold_result["train"], row[0]),
        ("Held Out", "test", fold_result["test"], row[1]),
    ]

    for label, split, result, ax in plot_specs:
        indicator_record = store.find_one(
            kind="derived",
            run_id=run_id,
            fold=fold,
            split=split,
            artifact="indicators",
        )
        fold_df = store.to_dataframe(indicator_record)
        if "date" in fold_df.columns:
            fold_df = fold_df.sort_values("date").reset_index(drop=True)
        fold_simulation = result["simulation_results"]

        ax.plot(range(len(fold_df)), fold_df["close"], "b-", label="Close Price", linewidth=2)
        ax.plot(range(len(fold_df)), fold_df["Leading"], "r--", label="Leading", linewidth=1.5, alpha=0.7)
        ax.plot(range(len(fold_df)), fold_df["Lagging"], "g--", label="Lagging", linewidth=1.5, alpha=0.7)

        buy_points = fold_simulation[fold_simulation["action"] == "buy"]
        sell_points = fold_simulation[fold_simulation["action"] == "sell"]
        if not buy_points.empty:
            ax.scatter(
                buy_points.index,
                fold_df.loc[buy_points.index, "close"],
                color="green",
                marker="^",
                s=100,
                label="Buy",
            )
        if not sell_points.empty:
            ax.scatter(
                sell_points.index,
                fold_df.loc[sell_points.index, "close"],
                color="red",
                marker="v",
                s=100,
                label="Sell",
            )

        ax.set_title(f"AAPL - {label} Fold {fold}", fontsize=14, fontweight="bold")
        ax.set_ylabel("Price ($)", fontsize=12)
        ax.set_xlabel("Fold Time Index", fontsize=12)
        ax.legend(loc="best")
        ax.grid(True, alpha=0.3)

if validation_results:
    plt.tight_layout()
    plt.show()

print(store.list())

print("\nStructured study artifacts:")
for record in store.find(run_id=run_id):
    print(f"{record.kind:9} | {record.attrs} | {record.name}")
