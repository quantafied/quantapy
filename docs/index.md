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
from quantapy.data import Data
from quantapy.calculator import Calculator
from quantapy.strategy import Strategy
from quantapy.simulation import Backtest

data = Data()
data.add("historical", "OHLC", "Internal", ticker="AAPL", period="1y")

calculator = Calculator(data.fetch_data())
calculator.add("SMA", window=20)

strategy = Strategy(calculator)
backtest = Backtest(strategy)

results = backtest.execute()

