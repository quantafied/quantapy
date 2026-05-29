# Study API

The study layer coordinates validation and optimization above the normal
pipeline. It can inspect calculator, strategy, order, and simulation components
for optimizable fields, then let users explicitly select the parameters to use.

## `Study`

Location: `quantapy.orchestrator.study.Study`

Primary methods:

- `discover_parameters()`: return structured candidates from component config schemas.
- `add_parameter(target, param, name=None, index=None, **kwargs)`: explicitly enable a parameter.
- `list_parameters()`: return enabled optimization parameters.
- `add(registered, function, source, **kwargs)`: add and return validation or optimization components.
- `execute()`: legacy validation/optimization execution hook.

## Structured Parameter Selection

Candidates are discovered automatically, but optimization parameters are enabled
explicitly:

```python
study = Study(simulation=simulation, store=store, calculator=calc, strategy=strategy)

candidates = study.discover_parameters()

study.add_parameter(
    target="Transform",
    name="SMA_20",
    param="timeperiod",
    dtype="integer",
    low=5,
    high=50,
)
```

Signals, orders, and simulations can be selected by `name` when available or by
`index` when they are anonymous:

```python
study.add_parameter(
    target="Signal",
    index=0,
    param="threshold",
    dtype="number",
    low=0.0,
    high=1.0,
)
```

This keeps the API consistent with QuantaPy's registry-oriented style while
still supporting GUI-friendly auto-discovery.

## Running Optuna

Once parameters are enabled, add the registered Bayesian optimizer and execute
it against a raw source dataset. The optimizer plugin owns Optuna and SQLite
storage; the `Study` orchestrator supplies context and selected parameters.

```python
optimizer = study.add(
    "Optimization",
    "Bayesian",
    "Internal",
    trials=10,
    objective_metric="Profit",
    direction="maximize",
    storage="sqlite:///asimin.sqlite3",
)

results = optimizer.execute_parameters(
    study=study,
    source_dataset="OHLC_AAPL",
    derived_name="OHLC_AAPL-AllIndicators",
)

print(results["best_trial"].params)
print(results["metrics"])
```
