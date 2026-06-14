"""Calculator-backed dataframe preparation.

This module belongs to orchestration, not to a specific executor. It turns a
source dataframe artifact plus a calculator recipe into a prepared dataframe
artifact that any dataframe-consuming executor can use.
"""

from __future__ import annotations

from typing import Any, Dict

from quantapy.core.executors import ExecutionRequest, PreparedExecution


class CalculatorInputPreparer:
    """Prepare an executor-ready dataframe by deriving calculator transforms."""

    def __init__(self, store, calculator):
        self.store = store
        self.calculator = calculator

    def prepare(
        self,
        source_id: str,
        prepared_name: str,
        attrs: Dict[str, Any] | None = None,
        selected_params: Dict[str, Any] | None = None,
    ) -> PreparedExecution:
        """Derive transforms, store the prepared artifact, and return a request."""
        attrs = dict(attrs or {})
        prepared = self.calculator.derive_combined(self.store, source_id)
        prepared_id = self.store.add_child(
            prepared_name,
            prepared,
            parent_ids=[source_id],
            kind="derived",
            attrs={**attrs, "artifact": "prepared_data"},
            transform={
                "name": "CalculatorPreparation",
                "transforms": self.calculator.list_transforms(),
                **({"selected_params": selected_params} if selected_params else {}),
            },
        )
        return PreparedExecution(
            input_id=prepared_id,
            request=ExecutionRequest(input_id=prepared_id, attrs=attrs),
            metadata={"selected_params": selected_params or {}},
        )

    def prepare_from_dataframe(
        self,
        source_id: str,
        prepared_name: str,
        dataframe,
        parent_ids: list[str],
        attrs: Dict[str, Any] | None = None,
        selected_params: Dict[str, Any] | None = None,
        transform_metadata: Dict[str, Any] | None = None,
    ) -> PreparedExecution:
        """Store an already-prepared dataframe as an executor input artifact."""
        attrs = dict(attrs or {})
        prepared_id = self.store.add_child(
            prepared_name,
            dataframe,
            parent_ids=parent_ids,
            kind="derived",
            attrs={**attrs, "artifact": "prepared_data"},
            transform={
                "name": "CalculatorPreparation",
                "transforms": self.calculator.list_transforms(),
                **({"selected_params": selected_params} if selected_params else {}),
                **(transform_metadata or {}),
            },
        )
        return PreparedExecution(
            input_id=prepared_id,
            request=ExecutionRequest(input_id=prepared_id, attrs=attrs),
            metadata={"selected_params": selected_params or {}},
        )
