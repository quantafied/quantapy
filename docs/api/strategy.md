# Strategy API

Strategies combine registered signal and order components. Strategy outputs can
then be passed into the simulation layer.

## `Strategy`

Location: `quantapy.orchestrator.strategy.Strategy`

Primary methods:

- `add(registered, function, source="Internal", **kwargs)`: add a signal or order from the registry.
- `generate_signals(dataset_name=None)`: evaluate registered signals on a store dataset.
- `simulate_returns(dataset_name=None)`: simple strategy-level return simulation.
- `save()`: save signal and order params to JSON.
- `load()`: load signal and order params from JSON.
- `update_condition(name, **new_params)`: replace a signal condition.
- `update_order(name, **new_params)`: replace an order.
- `remove_condition(operation)`: remove a signal.
- `remove_order(operation)`: remove an order.
- `optimize()`: run the current Optuna optimization hook.

## Built-In Signals

Registered components:

- `Signal / Crossover / Internal`: detects when `value1` crosses above `value2`.
- `Signal / Crossunder / Internal`: detects when `value1` crosses below `value2`.

## Built-In Orders

Registered components:

- `Order / Market / Internal`: fills at a configured price column and bar offset.

Example:

```python
strategy = Strategy(calc, store=store)
strategy.add("Signal", "Crossover", value1="sma_20", value2="sma_50", action="enter")
strategy.add("Signal", "Crossunder", value1="sma_20", value2="sma_50", action="exit")
strategy.add("Order", "Market", on_signal="entry", on_price="close", on_bar="current")
strategy.add("Order", "Market", on_signal="exit", on_price="close", on_bar="current")
```

