![Quantapy Logo](https://github.com/quantafied/quantapy/blob/main/quantapy_logo.png)

# QuantaPy

QuantaPy is a Python library for quantitative trading research, strategy development, and backtesting with an emphasis on developing robust models considering uncertainty. 

# Motivation

Automated trading and market strategy models developed using historical backtests suffer from overfitting and unrealistic assumptions. Plenty of seemingly phenomenal strategies have been shared across many platforms. While these results may be accurate, the assumptions of the simulated environment do not emulate the reality of live trading in which many of these strategies fail. Historical data is a single observation sampled from an underlying distribution of a stochastic process. Hindsight bias convinces us that the observation is true, when in reality, many possible outcomes existed before any data was actually observed. This mindset must be adopted to create performant models that can survive the uncertainty of live trading environments. A model is only as good as the assumptions used to emulate real world behaviour, which in most cases, fall short of a complete representation of the underlying process.

"All models are wrong, but some are useful" - George E.P. Box

This libraries intent is to provide the tools and infrastructure to develop more useful models with better assumptions and probablistic model development. 

# Features

* API
  * High-level of abstraction for simple programming
  * Custom plugin syntax - extensible
  *Orchestration of data, model building and evaluation
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
  * Minimize input parameter sensitivity
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
  * 
# Status

This library is under active development and does not contain a stable release yet
