"""
Example: Using Calculator v2 with DataStore for derived data.

Demonstrates:
1. Batch processing (historical data)
2. Streaming processing (incremental updates)
3. Lineage tracking (raw → derived)
"""

import numpy as np
import pandas as pd
from quantapy.core.timeseries import TimeSeries, DataStore
from quantapy.orchestrator.calculator_v2 import Calculator
from quantapy.utils.loader import load_plugins_from_folder

# Load technical indicator plugins
load_plugins_from_folder("/Users/andysimin/Desktop/projects/quantapy/quantapy/modules/calculator")

print("=" * 80)
print("EXAMPLE: Calculator v2 with DataStore")
print("=" * 80)

# ============================================================================
# Part 1: Setup (batch/historical data)
# ============================================================================
print("\n[1] Setting up raw data in DataStore")

# Create sample historical OHLC data
historical_data = [
    {"timestamp": i, "open": 100 + i, "high": 102 + i, "low": 99 + i, "close": 101 + i}
    for i in range(50)
]

store = DataStore()
historical_ts = TimeSeries.from_dict_list(historical_data)
store.add("OHLC_AAPL", historical_ts)

print(f"  Added 'OHLC_AAPL' to store: shape {store.get('OHLC_AAPL').shape}")

# ============================================================================
# Part 2: Register technical indicators
# ============================================================================
print("\n[2] Registering technical transforms")

calc = Calculator()

# Register Moving Average
calc.add_transform(
    category="Technical",
    function="Moving Average",
    source="Internal",
    name="SMA_20",
    timeperiod=20,
    real="close",
    output_names={"output": "sma_20"}
)

# Register RSI
calc.add_transform(
    category="Technical",
    function="Relative Strength Index",
    source="Internal",
    name="RSI_14",
    timeperiod=14,
    real="close",
    output_names={"output": "rsi_14"}
)

print(f"  Registered transforms: {list(calc.list_transforms().keys())}")

# ============================================================================
# Part 3: Batch derive (process all historical data)
# ============================================================================
print("\n[3] Deriving indicators for historical data")

# Derive SMA
sma_ts = calc.derive(store, "OHLC_AAPL", "SMA_20")
store.add("OHLC_AAPL-SMA_20", sma_ts)
print(f"  Derived SMA_20: shape {sma_ts.shape}, columns {sma_ts.columns}")

# Derive RSI
rsi_ts = calc.derive(store, "OHLC_AAPL", "RSI_14")
store.add("OHLC_AAPL-RSI_14", rsi_ts)
print(f"  Derived RSI_14: shape {rsi_ts.shape}, columns {rsi_ts.columns}")

# View derived data
sma_df = store.to_dataframe("OHLC_AAPL-SMA_20")
print(f"\n  Sample SMA_20 data (last 5 rows):")
print(sma_df[["timestamp", "close", "sma_20"]].tail())

# ============================================================================
# Part 4: Streaming scenario (incremental updates)
# ============================================================================
print("\n[4] Simulating streaming data arrival")

# New real-time data comes in (e.g., one new bar)
new_data = [
    {"timestamp": 50, "open": 150, "high": 152, "low": 149, "close": 151},
    {"timestamp": 51, "open": 151, "high": 153, "low": 150, "close": 152},
]

print(f"  Received {len(new_data)} new bar(s) from market")

# Step 1: Update source data in store
new_ts = TimeSeries.from_dict_list(new_data)
source_ts = store.get("OHLC_AAPL")
updated_source_ts = source_ts.append(new_ts)
store.add("OHLC_AAPL", updated_source_ts)
print(f"  Updated source 'OHLC_AAPL': shape {updated_source_ts.shape}")

# Step 2: Derive only the new rows (efficient!)
print(f"\n  Deriving indicators for {len(new_data)} new row(s)...")
new_sma = calc.derive_streaming(store, "OHLC_AAPL", new_ts, "SMA_20")
new_rsi = calc.derive_streaming(store, "OHLC_AAPL", new_ts, "RSI_14")

# Step 3: Append to existing derived datasets
existing_sma = store.get("OHLC_AAPL-SMA_20")
updated_sma = existing_sma.append(new_sma)
store.add("OHLC_AAPL-SMA_20", updated_sma)

existing_rsi = store.get("OHLC_AAPL-RSI_14")
updated_rsi = existing_rsi.append(new_rsi)
store.add("OHLC_AAPL-RSI_14", updated_rsi)

print(f"  Updated SMA_20: shape {updated_sma.shape}")
print(f"  Updated RSI_14: shape {updated_rsi.shape}")

# View updated data
sma_df = store.to_dataframe("OHLC_AAPL-SMA_20")
print(f"\n  Sample SMA_20 data (last 5 rows after streaming update):")
print(sma_df[["timestamp", "close", "sma_20"]].tail())

# ============================================================================
# Part 5: Query derived data
# ============================================================================
print("\n[5] Querying derived data from store")

print(f"\n  All datasets in store: {store.list()}")
print(f"\n  Store metadata:")
for name, meta in store.available().items():
    print(f"    {name}: shape {meta['shape']}, columns {meta['columns']}")

# ============================================================================
# Summary
# ============================================================================
print("\n" + "=" * 80)
print("SUMMARY: Recommended Approach")
print("=" * 80)
print("""
✓ Data Flow:
  1. Raw data → DataStore (add)
  2. Register transforms in Calculator
  3. Derive: calc.derive(store, source_dataset, transform_name)
  4. Store derived: store.add(derived_name, derived_ts)
  5. Stream: update source, derive_streaming(new_rows), append to derived

✓ Advantages:
  - Clean separation: raw vs. derived (lineage tracking)
  - Efficient streaming: only new rows computed
  - Composable: chain multiple transforms
  - Reusable: transforms registered once, used on many datasets
  
✓ Next Steps:
  - Integrate with Strategy for signal generation
  - Add more transforms (custom indicators, feature engineering)
  - Optimize: cache transform results, lazy evaluation
  - Visualization: plot raw + derived together
""")

print("\n✅ Example complete!")
