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
from quantapy.core.timeseries import DataStore, TimeSeries
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# Load all plugins
load_plugins_from_folder("/Users/andysimin/Desktop/projects/quantapy/quantapy/modules/strategy")
load_plugins_from_folder("/Users/andysimin/Desktop/projects/quantapy/quantapy/modules/simulation")
load_plugins_from_folder("/Users/andysimin/Desktop/projects/quantapy/quantapy/modules/data")
load_plugins_from_folder("/Users/andysimin/Desktop/projects/quantapy/quantapy/data/providers")
load_plugins_from_folder("/Users/andysimin/Desktop/projects/quantapy/quantapy/modules/calculator")
load_plugins_from_folder("/Users/andysimin/Desktop/projects/quantapy/quantapy/modules/study")

data = Data()
data.add_provider("Market", "OHLC", "FMP", source_ids=["AAPL"], interval="1hour")
store = DataStore()
fetched_data = data.fetch()

for dataset_name, dataset in fetched_data.items():
    store.add_raw(
        dataset_name,
        dataset,
        source={"provider": "OHLC"},
    )

aapl_data = store.get("OHLC_AAPL")

calc = Calculator()

# Add SMA (faster moving average)
calc.add_transform(
    category="Technical",
    function="Moving Average",
    source="Internal",
    name="SMA_20",
    timeperiod=20,
    real="close",
    output_names={"output": "sma_20"},
    display="Overlay"
)

# Add another SMA (slower moving average) for crossover signals
calc.add_transform(
    category="Technical",
    function="Moving Average",
    source="Internal",
    name="SMA_50",
    timeperiod=50,
    real="close",
    output_names={"output": "sma_50"},
    display="Overlay"
)

all_indicators = calc.derive_combined(store, "OHLC_AAPL")
store.add_child(
    "OHLC_AAPL-AllIndicators",
    all_indicators,
    parent_ids=["OHLC_AAPL"],
    kind="derived",
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
    value1="sma_20",
    value2="sma_50",
    action="enter",
    direction="long"
)

# Add Exit Signal: SMA_20 crosses below SMA_50 (bearish crossunder)
strategy.add(
    "Signal",
    "Crossunder",
    value1="sma_20",
    value2="sma_50",
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
simulation_results, portfolio_outputs, portfolio_metrics = simulation.execute(
    dataset_name="OHLC_AAPL-AllIndicators",
    name="OHLC_AAPL-SMA-Crossover-Backtest",
)

print("\nPORTFOLIO METRICS")
print("=" * 80)
print(portfolio_metrics.to_string(index=False))

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
        print(f"       P&L:    ${trade['pnl']:.2f} ({trade['pnl_pct']:.2f}%)")
else:
    print("  ✗ No completed trades")

# ============================================================================
# Step 7: Visualize Results
# ============================================================================
print("\n[7] Visualizing strategy execution...")

df = store.to_dataframe("OHLC_AAPL-AllIndicators")

if not df.empty and len(df) > 20:
    fig, ax = plt.subplots(figsize=(14, 8))
    
    # Plot price and moving averages
    ax.plot(range(len(df)), df['close'], 'b-', label='Close Price', linewidth=2)
    ax.plot(range(len(df)), df['sma_20'], 'r--', label='SMA(20)', linewidth=1.5, alpha=0.7)
    ax.plot(range(len(df)), df['sma_50'], 'g--', label='SMA(50)', linewidth=1.5, alpha=0.7)
    
    # Mark entry and exit signals
    for sig in strategy.event_signals:
        if sig['action'] == 'enter':
            ax.scatter(sig['index'], sig['price'], color='green', marker='^', s=100, label='Entry' if sig == strategy.event_signals[0] else '')
        elif sig['action'] == 'exit':
            ax.scatter(sig['index'], sig['price'], color='red', marker='v', s=100, label='Exit' if sig == strategy.event_signals[0] else '')
    
    ax.set_title('AAPL - SMA Crossover Strategy Execution', fontsize=14, fontweight='bold')
    ax.set_ylabel('Price ($)', fontsize=12)
    ax.set_xlabel('Time Index', fontsize=12)
    ax.legend(loc='best')
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.show()

# ============================================================================
# Summary
# ============================================================================
print("\n" + "=" * 80)
print("STRATEGY INTEGRATION SUMMARY")
print("=" * 80)

print(f"""
✓ Updated Strategy class works with new architecture:

  1. CALCULATOR v2 INTEGRATION
     • Uses Calculator.add_transform() to register indicators
     • Uses Calculator.derive_combined() to compute all at once
     • No direct access to calculator.transforms (abstracted)

  2. DATASTORE INTEGRATION
     • Strategy accepts store parameter in __init__
     • Uses store.to_dataframe() to get data for signal processing
     • Datasets accessed by name: "OHLC_AAPL-AllIndicators"

  3. SIGNAL & ORDER LOGIC UNCHANGED
     • Strategy.add() still registers signals/orders
     • Signal.check() detects entry/exit conditions
     • Order.execute() fills orders at specified prices

  4. WORKFLOW
     • Register indicators → Calculate with derive_combined()
     • Generate GaussianNoise datasets from raw OHLC data
     • Apply the same indicators to each noisy child dataset
     • Inspect raw/synthetic/derived datasets with DataStore records
     • Create Strategy(calc, store=store)
     • Add Signal/Order objects
     • Call strategy.generate_signals()
     • Call strategy.simulate_returns()
     • Inspect strategy.event_signals and strategy.trades

✓ Key Changes for Backward Compatibility:
     • Old: calculator.transformed_data dict access → New: store.to_dataframe()
     • Old: calculator.transforms dict access → New: calculator.list_transforms()
     • Old: Strategy(calc) → New: Strategy(calc, store=store)

✓ Next Steps:
     1. Extend signals (RSI overbought/oversold, Bollinger Band breaks)
     2. Optimize parameters with strategy.optimize()
     3. Backtest each synthetic AllIndicators dataset
     4. Compare raw vs augmented performance
""")

print("\n✅ Strategy integration complete!")
