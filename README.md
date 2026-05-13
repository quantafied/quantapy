![Quantapy Logo](https://github.com/quantafied/quantapy/blob/main/quantapy_logo.png)

# QuantaPy

QuantaPy is a Python library for quantitative trading research, strategy development, and backtesting with an emphasis on developing robust models considering uncertainty. 

## Motivation

Quantitative trading strategies that perform well in historical backtests often fail in live markets. Overfitting, hindsight bias, and unrealistic assumptions can easily produce strategies that appear profitable but are fragile in practice.

Historical price data represents a **single realization** sampled from an underlying stochastic process. Backtesting on a single deterministic trajectory can create a false sense of confidence, as many alternative market paths were possible before the data was observed.

In this context, it is often better to accept an imperfect solution to the *right* problem than a precise solution to the *wrong* one. The wrong problem is assuming that performance on a single historical trajectory is representative of the underlying process when it is not.

Robust strategies must be developed with this uncertainty in mind. A model is only as useful as the assumptions used to approximate real market behavior — assumptions that are often incomplete or overly optimistic.

> “All models are wrong, but some are useful.” — George E. P. Box

QuantaPy aims to provide the tools and infrastructure needed to develop **more useful models** by emphasizing uncertainty-aware evaluation, probabilistic thinking, and scientifically grounded backtesting workflows.

# Features

Testing

* API
  * High-level of abstraction for simple programming
  * Custom plugin syntax - extensible
  * Orchestration of data, model building and evaluation
* Data
  * Financial Modeling Prep
  * Bring your own data (BYOD)
  * Data augmentation
  * Synthetic data
* Transformations
  * Technical indicators
  * Math
  * Vector operations
* Strategy
  * Multi-asset
  * Order types
  * Signals
* Backtest
  * Event driven
* Portfolio
  * Multi-asset
  * Multi-strategy
* Evaluation
  * Portfolion metrics
  * Individual strategy metrics
  * Metric aggregation
  * Cross validation
  * Identification of failure modes 
  * Parameter sensitivity 
* Optimization using Bayesian and evolutionary algorithms
  * Feature importance
  * Parameter sensitivity
    
# Status

This library is under active development and does not contain a stable release yet
