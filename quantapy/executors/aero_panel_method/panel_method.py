"""Example executor plugin for a simple dataframe column operation."""

from __future__ import annotations

from typing import Any, Dict

import pandas as pd

from quantapy.core.executors import ExecutionRequest
from quantapy.core.results import ResultArtifact, ResultBundle
from quantapy.registry.executor_registry import register_executor


@register_executor(
    "python.column_math",
    label="Python Column Math",
    domain="python",
    template_type="python.column_math",
    input_contract={
        "primary": {
            "label": "Dataframe",
            "required_columns": [],
            "preferred_artifacts": ["prepared_data", "calculator", "source"],
        }
    },
    config_schema={
        "title": "Column Math",
        "type": "object",
        "properties": {
            "column": {
                "type": "string",
                "default": "close",
                "description": "Input column",
                "use_variable_options": True,
                "widget_type": "select",
            },
            "operation": {
                "type": "string",
                "default": "multiply",
                "description": "Operation",
                "enum": ["add", "subtract", "multiply", "divide"],
                "widget_type": "select",
            },
            "scalar": {
                "type": "number",
                "default": 1.0,
                "description": "Scalar value",
            },
            "output_column": {
                "type": "string",
                "default": "column_math",
                "description": "Output column name",
            },
        },
    },
    template_format="json",
)
class ColumnMathExecutor:
    """Run a simple Python dataframe operation from an execution config."""

    name = "python.column_math"

    def __init__(self, store):
        self.store = store

    def run(self, request: ExecutionRequest) -> ResultBundle:
        """Execute the configured column operation."""
        df = self.store.to_dataframe(request.input_id)
        if df is None:
            raise ValueError(f"Dataset '{request.input_id}' not found")

        config = dict(request.config or {})
        column = str(config.get("column") or "close")
        operation = str(config.get("operation") or "multiply")
        scalar = float(config.get("scalar") if config.get("scalar") is not None else 1.0)
        output_column = str(config.get("output_column") or f"{column}_{operation}")

        if column not in df.columns:
            raise ValueError(f"Column '{column}' not found")

        result = df.copy()
        values = pd.to_numeric(result[column], errors="coerce")
        if operation == "add":
            result[output_column] = values + scalar
        elif operation == "subtract":
            result[output_column] = values - scalar
        elif operation == "multiply":
            result[output_column] = values * scalar
        elif operation == "divide":
            result[output_column] = values / (scalar if scalar else float("nan"))
        else:
            raise ValueError(f"Unsupported operation '{operation}'")

        metrics = {
            "rows": int(len(result)),
            "input_mean": _safe_float(values.mean()),
            "output_mean": _safe_float(pd.to_numeric(result[output_column], errors="coerce").mean()),
        }
        metrics_df = pd.DataFrame([metrics])

        return ResultBundle(
            artifacts=[
                ResultArtifact(
                    role="result_table",
                    artifact_type="table",
                    kind="derived",
                    name=f"{request.name}-Result" if request.name else None,
                    data=result,
                    attrs={**request.attrs, "artifact": "prepared_data"},
                    transform={
                        "name": "ColumnMath",
                        "config": config,
                    },
                ),
                ResultArtifact(
                    role="metrics",
                    artifact_type="scalar_map",
                    kind="metrics",
                    name=f"{request.name}-Metrics" if request.name else None,
                    data=metrics_df,
                    attrs={**request.attrs, "artifact": "operation_metrics"},
                    transform={"name": "ColumnMath", "output": "summary"},
                ),
            ],
            metrics=metrics,
            summary={"operation": operation, "column": column, "output_column": output_column},
        )


def _safe_float(value: Any) -> float | None:
    if pd.isna(value):
        return None
    return float(value)
