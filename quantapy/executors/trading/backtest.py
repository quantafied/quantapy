"""Trading backtest executor adapter.

This wrapper is the migration point from the current in-process trading object
graph to the more general executor model. It delegates to the existing
``Simulate`` orchestrator for now, then reports the outputs as a ResultBundle.
"""

from __future__ import annotations

from typing import Any, Dict

import pandas as pd

from quantapy.core.executors import ExecutionRequest
from quantapy.core.results import ResultArtifact, ResultBundle
from quantapy.orchestrator.calculator import Calculator
from quantapy.orchestrator.simulate import Simulate
from quantapy.orchestrator.strategy import Strategy
from quantapy.registry.executor_registry import register_executor


@register_executor(
    "trading.backtest",
    label="Trading Backtest",
    domain="trading",
    template_type="trading.backtest",
    input_contract={
        "primary": {
            "label": "Market data",
            "required_columns": ["date", "open", "high", "low", "close"],
            "preferred_artifacts": ["calculator", "indicators", "source"],
        }
    },
    config_builder={
        "mode": "structured",
        "sections": [
            {
                "key": "strategy.signals",
                "label": "Signals",
                "component_category": "Signal",
                "multiple": True,
                "column_options": True,
            },
            {
                "key": "strategy.orders",
                "label": "Orders",
                "component_category": "Order",
                "multiple": True,
                "column_options": True,
            },
            {
                "key": "simulation",
                "label": "Simulation",
                "component_category": "Simulation",
                "multiple": False,
                "default_function": "Backtest",
                "default_source": "Internal",
                "column_options": True,
            },
        ],
    },
    template_format="json",
)
class BacktestExecutor:
    """Run a configured trading simulation against one DataStore dataset."""

    name = "trading.backtest"

    def __init__(self, simulation=None, store=None):
        self.simulation = simulation
        self.store = store

    def run(self, request: ExecutionRequest) -> ResultBundle:
        """Execute the backtest and return standardized result artifacts."""
        simulation = self._resolve_simulation(request)
        simulation_results, evaluator_outputs, metrics = simulation.execute(
            dataset_name=request.input_id,
            store=self.store,
            name=request.name,
            attrs=request.attrs,
        )
        metrics_dict: Dict[str, Any] = {}
        if metrics is not None:
            metrics_dict = metrics.to_dict(orient="records")[0]

        artifacts = [
            ResultArtifact(
                role="events",
                artifact_type="table",
                kind="backtest",
                name=request.name,
                data=simulation_results,
                attrs={**request.attrs, "artifact": "backtest"},
            )
        ]
        if evaluator_outputs is not None:
            artifacts.append(
                ResultArtifact(
                    role="portfolio_series",
                    artifact_type="timeseries",
                    kind="metrics",
                    name=f"{request.name}-Portfolio-Outputs" if request.name else None,
                    data=evaluator_outputs,
                    attrs={**request.attrs, "artifact": "portfolio_outputs"},
                )
            )
        if metrics is not None:
            artifacts.append(
                ResultArtifact(
                    role="metrics",
                    artifact_type="scalar_map",
                    kind="metrics",
                    name=f"{request.name}-Portfolio-Metrics" if request.name else None,
                    data=metrics,
                    attrs={**request.attrs, "artifact": "portfolio_metrics"},
                )
            )

        return ResultBundle(
            artifacts=artifacts,
            metrics=metrics_dict,
            summary={
                "signals": _value_counts(simulation_results, "signal"),
                "actions": _value_counts(simulation_results, "action"),
            },
        )

    def _resolve_simulation(self, request: ExecutionRequest):
        """Return an in-process simulation from a config document or fallback object."""
        if request.config.get("strategy") and request.config.get("simulation"):
            return self._simulation_from_config(request.config)
        if self.simulation is None:
            raise ValueError("BacktestExecutor requires a simulation object or strategy/simulation config")
        return self.simulation

    def _simulation_from_config(self, config: Dict[str, Any]):
        """Build the trading object graph from an execution config document."""
        if self.store is None:
            raise ValueError("BacktestExecutor requires a DataStore when running from config")

        strategy_config = config.get("strategy") or {}
        simulation_config = config.get("simulation") or {}

        strategy = Strategy(Calculator(), store=self.store)
        for signal in strategy_config.get("signals", []):
            strategy.add(
                signal.get("category", "Signal"),
                signal["function"],
                signal.get("source", "Internal"),
                **dict(signal.get("params") or {}),
            )
        for order in strategy_config.get("orders", []):
            strategy.add(
                order.get("category", "Order"),
                order["function"],
                order.get("source", "Internal"),
                **dict(order.get("params") or {}),
            )

        simulation = Simulate(strategy=strategy, store=self.store)
        simulation.add(
            simulation_config.get("category", "Simulation"),
            simulation_config["function"],
            simulation_config.get("source", "Internal"),
            **dict(simulation_config.get("params") or {}),
        )
        return simulation


def _value_counts(df: pd.DataFrame, column: str) -> Dict[str, int]:
    if column not in df:
        return {}
    return df[column].value_counts().to_dict()
