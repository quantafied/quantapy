"""Execution spec factories for simple Python operation examples."""

from __future__ import annotations

from typing import Any, Dict, Optional

from quantapy.core.executions import ExecutionSpec, OutputBinding, spec_input


def column_math_spec(
    dataset_id: str,
    name: str,
    attrs: Optional[Dict[str, Any]] = None,
    config: Optional[Dict[str, Any]] = None,
) -> ExecutionSpec:
    """Build a generic execution spec for a dataframe column math operation."""
    attrs = dict(attrs or {})
    return ExecutionSpec(
        runner="python.column_math",
        name=name,
        inputs=[spec_input(dataset_id, role="primary", name="dataframe")],
        config=dict(config or {}),
        attrs=attrs,
        outputs=[
            OutputBinding(
                role="result_table",
                name=f"{name}-Result",
                artifact_type="table",
                kind="derived",
                attrs={"artifact": "prepared_data"},
            ),
            OutputBinding(
                role="metrics",
                name=f"{name}-Metrics",
                artifact_type="scalar_map",
                kind="metrics",
                attrs={"artifact": "operation_metrics"},
            ),
        ],
    )
