# Simulation API

The simulation layer uses the same registry pattern as providers, transforms,
signals, and orders.

## `Simulate`

Location: `quantapy.orchestrator.simulate.Simulate`

Primary methods:

- `add(registered, function, source="Internal", **kwargs)`: register a simulation component.
- `add_evaluator(registered, function, source="Internal", **kwargs)`: register an evaluator component.
- `execute(dataset_name, store=None, name=None)`: run the simulation and evaluator on a committed dataset.
- `backtest(input_data_dict, strategy, n_jobs=-1)`: legacy parallel backtest helper.

`execute()` stores simulation output as `kind="backtest"` and evaluator output as
`kind="metrics"` children in the `DataStore`.

## Built-In Backtest

Registered component:

- `Simulation / Backtest / Internal`

Produces a DataFrame with:

- `date`
- `signal`
- `portfolio_value`
- `position`
- `action`

## Portfolio Evaluation

Registered component:

- `Evaluate / Portfolio / Internal`

Returns:

- rolling output series
- one-row summary metrics including CAGR, Sharpe Ratio, Sortino Ratio, Max Drawdown, Value at Risk, and Profit

Example:

```python
simulation = Simulate(strategy=strategy, store=store)
simulation.add("Simulation", "Backtest", "Internal", initial_investment=10000)
simulation.add_evaluator("Evaluate", "Portfolio", "Internal")

simulation_results, portfolio_outputs, portfolio_metrics = simulation.execute(
    dataset_name="OHLC_AAPL-AllIndicators",
    name="OHLC_AAPL-SMA-Crossover-Backtest",
)
```

