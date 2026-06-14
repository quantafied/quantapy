"""Trading portfolio analytics evaluator."""

from __future__ import annotations

from typing import Any, Dict

import pandas as pd

from quantapy.core.evaluators import EvaluationRequest
from quantapy.core.results import ResultArtifact, ResultBundle
from quantapy.modules.evaluation.portfolio import PortfolioAnalytics
from quantapy.registry.evaluator_registry import register_evaluator


@register_evaluator(
    "trading.portfolio_metrics",
    label="Portfolio Metrics",
    domain="trading",
    input_contract={
        "events": {
            "label": "Backtest events",
            "artifact": "backtest",
            "artifact_type": "table",
            "required_columns": ["date", "portfolio_value"],
        }
    },
    config_schema={
        "title": "Portfolio Metrics",
        "type": "object",
        "properties": {
            "risk_free_rate": {
                "type": "number",
                "default": 0.0,
                "description": "Annualized risk-free rate",
            }
        },
    },
    output_contract={
        "portfolio_series": {"artifact": "portfolio_outputs", "artifact_type": "timeseries"},
        "metrics": {"artifact": "portfolio_metrics", "artifact_type": "scalar_map"},
    },
)
class PortfolioMetricsEvaluator:
    """Compute portfolio analytics from a backtest event/equity table."""

    name = "trading.portfolio_metrics"

    def __init__(self, store):
        self.store = store

    def evaluate(self, request: EvaluationRequest) -> ResultBundle:
        """Evaluate portfolio series and return analytics artifacts."""
        input_id = request.inputs.get("events") or next(iter(request.inputs.values()), None)
        if not input_id:
            raise ValueError("Portfolio metrics evaluator requires an events input")
        df = self.store.to_dataframe(input_id)
        if df is None:
            raise ValueError(f"Input artifact '{input_id}' not found")
        missing = [column for column in ["date", "portfolio_value"] if column not in df.columns]
        if missing:
            raise ValueError(f"Portfolio metrics input missing required column(s): {', '.join(missing)}")

        risk_free_rate = float(request.config.get("risk_free_rate") or 0.0)
        analyzer = PortfolioAnalytics(df[["date", "portfolio_value"]], risk_free_rate=risk_free_rate)
        outputs, metrics = analyzer.compute()
        metrics_dict: Dict[str, Any] = metrics.to_dict(orient="records")[0] if not metrics.empty else {}

        return ResultBundle(
            artifacts=[
                ResultArtifact(
                    role="portfolio_series",
                    artifact_type="timeseries",
                    kind="metrics",
                    name=f"{request.name}-Portfolio-Outputs" if request.name else None,
                    data=outputs,
                    attrs={**request.attrs, "artifact": "portfolio_outputs"},
                    transform={"name": self.name, "output": "timeseries"},
                ),
                ResultArtifact(
                    role="metrics",
                    artifact_type="scalar_map",
                    kind="metrics",
                    name=f"{request.name}-Portfolio-Metrics" if request.name else None,
                    data=metrics,
                    attrs={**request.attrs, "artifact": "portfolio_metrics"},
                    transform={"name": self.name, "output": "summary"},
                ),
            ],
            metrics=metrics_dict,
            summary={"input_id": input_id, "risk_free_rate": risk_free_rate},
        )
