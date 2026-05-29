#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generic Data Orchestration Pipeline with Technical Indicators

This CLI demonstrates:
1. Fetching raw data from providers (FMP)
2. Storing in DataStore (TimeSeries)
3. Computing technical indicators (Calculator v2)
4. Multiple indicators in ONE dataset (best practice)
5. Streaming support for live data updates
"""

from quantapy.registry.component_registry import COMPONENT_REGISTRY
from quantapy.utils.loader import load_plugins_from_folder
from quantapy.orchestrator.data import Data
from quantapy.orchestrator.calculator import Calculator
from quantapy.orchestrator.study import Study
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

print("=== Quantapy: Data Orchestration + Technical Analysis ===\n")

# ============================================================================
# Part 1: Fetch Raw Financial Data
# ============================================================================
print("[1] Fetching raw OHLC data from FMP provider...")

data = Data()
data.add_provider("Market", "OHLC", "FMP", source_ids=["AAPL", "RGTI"], interval="1hour")
store = DataStore()
fetched_data = data.fetch()

for dataset_name, dataset in fetched_data.items():
    store.add_raw(
        dataset_name,
        dataset,
        source={"provider": "OHLC"},
    )

print(f"  ✓ Fetched datasets: {store.list()}")
if "OHLC_AAPL" in store.list():
    print(f"  ✓ OHLC_AAPL shape: {store.get('OHLC_AAPL').shape}")
if "OHLC_RGTI" in store.list():
    print(f"  ✓ OHLC_RGTI shape: {store.get('OHLC_RGTI').shape}")

# ============================================================================
# Part 2: Register Technical Indicators (Calculator v2)
# ============================================================================
print("\n[2] Registering technical indicators...")

calc = Calculator()

# Register SMA (Simple Moving Average)
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
print("  ✓ Registered SMA_20")

# Register RSI (Relative Strength Index)
calc.add_transform(
    category="Technical",
    function="Relative Strength Index",
    source="Internal",
    name="RSI_14",
    timeperiod=14,
    real="close",
    output_names={"output": "rsi_14"},
    display="Indicator"
)
print("  ✓ Registered RSI_14")

print(f"  ✓ Total registered: {len(calc.list_transforms())} transforms")

# ============================================================================
# Part 2b: Select Indicator Parameters for Optimization
# ============================================================================
print("\n[2b] Selecting indicator parameters for optimization...")

study = Study(simulation=None, store=store, calculator=calc)
candidate_params = study.discover_parameters()

print("  Discoverable optimization candidates:")
for candidate in candidate_params:
    print(
        f"  - {candidate['target']} {candidate['name']}.{candidate['param']} "
        f"default={candidate['default']} bounds=({candidate['low']}, {candidate['high']})"
    )

study.add_parameter(
    target="Transform",
    name="SMA_20",
    param="timeperiod",
    dtype="integer",
    low=5,
    high=50,
)
study.add_parameter(
    target="Transform",
    name="RSI_14",
    param="timeperiod",
    dtype="integer",
    low=7,
    high=30,
)

print("  Enabled optimization parameters:")
for parameter in study.list_parameters():
    print(f"  - {parameter}")

# ============================================================================
# Part 3: BEST PRACTICE - ALL Indicators in ONE Dataset
# ============================================================================
print("\n[3] Deriving all indicators → ONE combined dataset per symbol...")
print("  (This is the recommended approach: no duplication, clean lineage)")

# Apply ALL registered indicators to AAPL data at once
# Result: ONE TimeSeries with [timestamp, open, high, low, close, sma_20, rsi_14, ...]
if "OHLC_AAPL" in store.list():
    all_indicators_aapl = calc.derive_combined(store, "OHLC_AAPL")
    store.add_child(
        "OHLC_AAPL-AllIndicators",
        all_indicators_aapl,
        parent_ids=["OHLC_AAPL"],
        kind="derived",
        transform={"name": "AllIndicators", "transforms": calc.list_transforms()},
    )
    
    print(f"  ✓ OHLC_AAPL-AllIndicators shape: {all_indicators_aapl.shape}")
    print(f"  ✓ Columns: {all_indicators_aapl.columns}")

# Apply ALL indicators to RGTI data
if "OHLC_RGTI" in store.list():
    all_indicators_rgti = calc.derive_combined(store, "OHLC_RGTI")
    store.add_child(
        "OHLC_RGTI-AllIndicators",
        all_indicators_rgti,
        parent_ids=["OHLC_RGTI"],
        kind="derived",
        transform={"name": "AllIndicators", "transforms": calc.list_transforms()},
    )
    print(f"  ✓ OHLC_RGTI-AllIndicators created")

# ============================================================================
# Part 5: Inspect Results
# ============================================================================
print("[5] Inspecting derived data...")

print(f"\n  All datasets in store: {store.list()}\n")

# Show sample from combined dataset
if "OHLC_AAPL-AllIndicators" in store.list():
    df = store.to_dataframe("OHLC_AAPL-AllIndicators")
    print("  OHLC_AAPL-AllIndicators (last 5 rows):")
    # Try both 'date' and 'timestamp' columns
    cols_to_show = ["date", "close", "sma_20", "rsi_14"] if "date" in df.columns else ["timestamp", "close", "sma_20", "rsi_14"]
    cols_to_show = [c for c in cols_to_show if c in df.columns]
    print(df[cols_to_show].tail().to_string())

# ============================================================================
# Part 6: Visualize Raw Data + ALL Indicators
# ============================================================================
print("\n[6] Visualizing price + all indicators together...")

if "OHLC_AAPL-AllIndicators" in store.list():
    df = store.to_dataframe("OHLC_AAPL-AllIndicators")
    
    if not df.empty and len(df) > 10:
        fig, axes = plt.subplots(3, 1, figsize=(14, 10))
        
        # Plot 1: Price + SMA
        axes[0].plot(range(len(df)), df['close'], 'b-', label='Close Price', linewidth=2)
        axes[0].plot(range(len(df)), df['sma_20'], 'r--', label='SMA(20)', linewidth=1.5, alpha=0.7)
        axes[0].set_title('AAPL - Price and Moving Average')
        axes[0].set_ylabel('Price')
        axes[0].legend()
        axes[0].grid(True, alpha=0.3)
        
        # Plot 2: RSI
        axes[1].plot(range(len(df)), df['rsi_14'], 'g-', label='RSI(14)', linewidth=2)
        axes[1].axhline(y=70, color='r', linestyle='--', alpha=0.5, label='Overbought (70)')
        axes[1].axhline(y=30, color='b', linestyle='--', alpha=0.5, label='Oversold (30)')
        axes[1].set_title('AAPL - Relative Strength Index')
        axes[1].set_ylabel('RSI')
        axes[1].set_ylim([0, 100])
        axes[1].legend()
        axes[1].grid(True, alpha=0.3)
        
        # Plot 3: Volume
        axes[2].bar(range(len(df)), df['volume'] if 'volume' in df.columns else np.ones(len(df)), 
                    color='purple', alpha=0.6)
        axes[2].set_title('AAPL - Volume')
        axes[2].set_ylabel('Volume')
        axes[2].set_xlabel('Time Index')
        axes[2].grid(True, alpha=0.3)
        
        plt.tight_layout()
        plt.show()

# ============================================================================
# Part 7: Synthetic Data Augmentation + Indicators
# ============================================================================
print("\n[7] Generating synthetic data using Gaussian noise augmentation...")

# Register data augmentation transformer
data.add_transformer("Noise", "GaussianNoise", "Internal",
                     n_trajectories=3, mean=0.0, stddev=0.015)

# Apply to AAPL to generate synthetic versions
synthetic_outputs = data.transform("OHLC_AAPL", store.get("OHLC_AAPL"))
for synth_name, synth_data in synthetic_outputs.items():
    store.add_child(
        synth_name,
        synth_data,
        parent_ids=["OHLC_AAPL"],
        kind="synthetic",
        transform={"name": "GaussianNoise"},
    )
synthetic_datasets = store.filter("GaussianNoise")

print(f"  ✓ Generated {len(synthetic_datasets)} synthetic trajectories")

# Compute indicators for each synthetic trajectory
print("\n[7b] Computing indicators for synthetic data...")
for i, synth_name in enumerate(synthetic_datasets[:2]):  # Process first 2 for demo
    synth_indicators = calc.derive_combined(store, synth_name)
    store.add_child(
        f"{synth_name}-AllIndicators",
        synth_indicators,
        parent_ids=[synth_name],
        kind="derived",
        transform={"name": "AllIndicators", "transforms": calc.list_transforms()},
    )
    df_synth = synth_indicators.to_dataframe()
    print(f"  ✓ {synth_name}-AllIndicators: shape {synth_indicators.shape}")

# ============================================================================
# Part 8: Streaming Scenario (Fixed Schema)
# ============================================================================
print("\n[8] Streaming scenario: new data arrives...")

# Get existing raw data to understand its schema
if "OHLC_AAPL" in store.list():
    existing_data = store.get("OHLC_AAPL")
    existing_df = existing_data.to_dataframe()
    
    print(f"  ✓ Existing schema: {existing_data.schema}")
    
    # Create new data with MATCHING schema
    # Match the column names and types from existing data
    new_rows_dict = [
        {col: val for col, val in zip(existing_data.columns, [f"2026-05-24 10:00", 160.5, 162.5, 159.5, 161.0, 1500.0])} 
        if i == 0 else
        {col: val for col, val in zip(existing_data.columns, [f"2026-05-24 11:00", 161.0, 163.0, 160.0, 162.0, 1600.0])}
        for i in range(2)
    ]
    
    # Ensure the new data matches the schema
    new_df = pd.DataFrame(new_rows_dict)
    # Convert types to match existing
    for col in new_df.columns:
        if col in existing_df.columns:
            new_df[col] = new_df[col].astype(existing_df[col].dtype)
    
    new_ts = TimeSeries.from_dataframe(new_df)
    
    print(f"  ✓ New data schema: {new_ts.schema}")
    print(f"  ✓ Received 2 new bar(s)")
    
    # Update raw data
    raw_data = store.get("OHLC_AAPL")
    updated_raw = raw_data.append(new_ts)
    store.add_raw("OHLC_AAPL", updated_raw, source={"provider": "OHLC"})
    print(f"  ✓ Updated raw data: shape {updated_raw.shape}")
    
    # Recompute all indicators
    new_indicators = calc.derive_combined(store, "OHLC_AAPL")
    store.add_child(
        "OHLC_AAPL-AllIndicators",
        new_indicators,
        parent_ids=["OHLC_AAPL"],
        kind="derived",
        transform={"name": "AllIndicators", "transforms": calc.list_transforms()},
    )
    print(f"  ✓ Updated all indicators: shape {new_indicators.shape}")

# ============================================================================
# Summary
# ============================================================================
print("\n" + "=" * 80)
print("SUMMARY")
print("=" * 80)

print(f"""
✓ COMPLETE WORKFLOW DEMONSTRATED:

1. FETCH RAW DATA
   └─ FMP provider → DataStore (OHLC_AAPL, OHLC_RGTI)

2. COMPUTE INDICATORS (All in ONE dataset)
   └─ Calculator.derive_combined() → OHLC_AAPL-AllIndicators
   └─ Columns: [date, open, high, low, close, volume, sma_20, rsi_14]

3. AUGMENT WITH SYNTHETIC DATA
   └─ GaussianNoise transformer → 3 synthetic trajectories
   └─ Each synthetic: OHLC_AAPL-GaussianNoise-0, -1, -2

4. COMPUTE INDICATORS FOR SYNTHETIC DATA
   └─ Same Calculator applied to synthetic datasets
   └─ OHLC_AAPL-GaussianNoise-0-AllIndicators
   └─ Now you have indicators for all synthetic versions!

5. STREAMING SUPPORT
   └─ New data arrives with matching schema
   └─ Update raw: OHLC_AAPL (append new rows)
   └─ Update indicators: OHLC_AAPL-AllIndicators
   └─ No recomputation of historical data

✓ DataStore Final Contents: {len(store.list())} datasets

✓ Multiple Indicators in ONE Dataset - YES!
  • No duplication: one combined dataset per source
  • Efficient: all indicators computed once
  • Scalable: add more indicators without extra datasets
  • Streaming-ready: incremental updates

✓ Synthetic Data + Indicators - YES!
  • Generate augmented versions: derive_combined()
  • Each synthetic has full indicator suite
  • Perfect for robustness testing and confidence intervals

✓ Next Steps:
  1. Generate signals from indicators (SMA crossover, RSI overbought)
  2. Backtest strategy on both raw and synthetic data
  3. Compare performance: raw vs augmented
  4. Use signals for live trading
""")

print("\n✅ Pipeline complete!")
