# QuantaPy

**QuantaPy** is a Python framework for quantitative trading research, strategy
development, and backtesting with an explicit focus on uncertainty.

Most trading libraries optimize for producing a single backtest result.
QuantaPy treats historical data as *one realization of a stochastic process*,
and provides tools to stress, perturb, and evaluate strategies under uncertainty.

---

## Who is this for?

QuantaPy is designed for:

- Retail traders transitioning to quantitative research
- Developers building modular trading systems
- Researchers who care about robustness, not just performance

If you are tired of curve-fit strategies that collapse out-of-sample,
this library is for you.

---

## Core ideas

- **Uncertainty-first**: synthetic data, perturbations, and robustness testing
- **Modular architecture**: data, transforms, signals, execution, simulation
- **Explicit contracts**: registries, typed configs, reproducible pipelines
- **Scientific mindset**: falsification over hindsight

---

## High-level workflow

```python
from quantapy.orchestrator.data import Data
from quantapy.orchestrator.calculator import Calculator
from quantapy.orchestrator.strategy import Strategy
from quantapy.orchestrator.simulate import Simulate
from quantapy.core.timeseries import DataStore

data = Data()
data.add_provider("Market", "OHLC", "FMP", source_ids=["AAPL"], interval="1hour")

store = DataStore()
for name, dataset in data.fetch().items():
    store.add_raw(name, dataset, source={"provider": "OHLC"})

calculator = Calculator()
calculator.add_transform(
    "Technical",
    "Moving Average",
    name="SMA_20",
    timeperiod=20,
    real="close",
    output_names={"output": "sma_20"},
)

indicators = calculator.derive_combined(store, "OHLC_AAPL")
store.add_child(
    "OHLC_AAPL-AllIndicators",
    indicators,
    parent_ids=["OHLC_AAPL"],
    kind="derived",
)

strategy = Strategy(calculator, store=store)
simulation = Simulate(strategy=strategy, store=store)
simulation.add("Simulation", "Backtest", "Internal", initial_investment=10000)
simulation.add_evaluator("Evaluate", "Portfolio", "Internal")

simulation_results, portfolio_outputs, portfolio_metrics = simulation.execute(
    dataset_name="OHLC_AAPL-AllIndicators"
)
```

QuantaPy uses an explicit compute-then-commit model. Providers,
transformers, calculators, strategies, and simulations return outputs first.
The `DataStore` records committed datasets and lineage through
`add_raw()` and `add_child()`.
