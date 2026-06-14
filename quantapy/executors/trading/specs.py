"""Execution spec factories for trading workflows."""

from __future__ import annotations

from typing import Any, Dict, Optional

from quantapy.core.executions import ExecutionSpec, OutputBinding, spec_input

# ResultArtifact = one output
# ResultBundle   = all outputs from one run

def backtest_spec(
    dataset_id: str,
    name: str,
    attrs: Optional[Dict[str, Any]] = None,
    config: Optional[Dict[str, Any]] = None,
) -> ExecutionSpec:
    """Build a generic execution spec for a trading backtest."""
    attrs = dict(attrs or {})
    return ExecutionSpec(
        runner="trading.backtest",
        name=name,
        inputs=[spec_input(dataset_id, role="primary", name="market_data")],
        config=dict(config or {}),
        attrs=attrs,
        outputs=[
            OutputBinding(
                role="events",
                name=name,
                artifact_type="table",
                kind="backtest",
                attrs={"artifact": "backtest"},
            ),
            OutputBinding(
                role="portfolio_series",
                name=f"{name}-Portfolio-Outputs",
                artifact_type="timeseries",
                kind="metrics",
                attrs={"artifact": "portfolio_outputs"},
            ),
            OutputBinding(
                role="metrics",
                name=f"{name}-Portfolio-Metrics",
                artifact_type="scalar_map",
                kind="metrics",
                attrs={"artifact": "portfolio_metrics"},
            ),
        ],
    )
