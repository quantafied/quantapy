# Calculator API

The calculator manages registered transform components and derives new
`TimeSeries` outputs from committed datasets.

## `Calculator`

Location: `quantapy.orchestrator.calculator.Calculator`

Primary methods:

- `add_transform(category, function, source="Internal", **kwargs)`: register a transform from the component registry.
- `derive(store, source_dataset, transform_name)`: apply one transform and return a new `TimeSeries`.
- `derive_combined(store, source_dataset, transform_names=None)`: apply multiple transforms and return one combined `TimeSeries`.
- `derive_all(store, source_dataset)`: derive each registered transform and commit outputs as child datasets.
- `derive_batch(store, dataset_names, n_jobs=-1)`: derive transforms across multiple datasets.
- `derive_streaming(store, source_dataset, new_rows, transform_name=None)`: derive only newly appended rows.
- `get_config(transform_name)`: return a transform config schema.
- `set_config(transform_name, new_params)`: update transform parameters.
- `list_transforms()`: inspect registered transforms.

## Built-In Technical Transforms

Registered components:

- `Technical / Moving Average / Internal`: simple moving average backed by TA-Lib.
- `Technical / Relative Strength Index / Internal`: RSI backed by TA-Lib.

Typical usage:

```python
calc = Calculator()
calc.add_transform(
    "Technical",
    "Moving Average",
    name="SMA_20",
    timeperiod=20,
    real="close",
    output_names={"output": "sma_20"},
)

indicators = calc.derive_combined(store, "OHLC_AAPL")
store.add_child("OHLC_AAPL-AllIndicators", indicators, parent_ids=["OHLC_AAPL"])
```

