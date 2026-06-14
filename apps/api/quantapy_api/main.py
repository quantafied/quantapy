from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

import numpy as np
import pandas as pd
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

import quantapy
from quantapy.artifacts import (
    apply_calculator_to_artifact_or_collection,
    create_raw_collection,
    gaussian_noise_collection,
    import_path,
    split_artifact_or_collection,
)
from quantapy.artifacts.collections import create_dataset_artifact
from quantapy.core.artifacts import ArtifactCatalog
from quantapy.core.evaluations import EvaluationRun, EvaluationSpec
from quantapy.core.evaluators import EvaluationRequest as CoreEvaluationRequest
from quantapy.core.executions import ExecutionRun, ExecutionSpec, spec_input
from quantapy.core.timeseries import DataStore
from quantapy.core.runners import ExecutionSpecRunner
from quantapy.core.workspace import WorkspaceStore
from quantapy.executors.trading import BacktestExecutor, backtest_spec
from quantapy.orchestrator.calculator import Calculator
from quantapy.orchestrator.data import Data
from quantapy.orchestrator.simulate import Simulate
from quantapy.orchestrator.strategy import Strategy
from quantapy.orchestrator.study import Study
from quantapy.registry.component_registry import COMPONENT_REGISTRY
from quantapy.registry.evaluator_registry import evaluator_class, evaluator_metadata
from quantapy.registry.executor_registry import executor_class, executor_metadata
from quantapy.utils.loader import load_plugins_from_folder, load_plugins_from_package


PACKAGE_ROOT = Path(quantapy.__file__).resolve().parent
UPLOAD_ROOT = Path("/private/tmp/quantapy-uploads")


def load_quantapy_plugins() -> None:
    """Load bundled Quantapy plugins once at API startup."""
    for folder in [
        PACKAGE_ROOT / "modules" / "strategy",
        PACKAGE_ROOT / "modules" / "simulation",
        PACKAGE_ROOT / "modules" / "data",
        PACKAGE_ROOT / "data" / "providers",
        PACKAGE_ROOT / "modules" / "calculator",
        PACKAGE_ROOT / "modules" / "study",
        PACKAGE_ROOT / "modules" / "evaluation",
    ]:
        load_plugins_from_folder(str(folder))
    load_plugins_from_package("quantapy.executors")
    load_plugins_from_package("quantapy.evaluators")
    for folder in os.environ.get("QUANTAPY_PLUGIN_PATHS", "").split(os.pathsep):
        if folder:
            load_plugins_from_folder(folder)


load_quantapy_plugins()


@dataclass
class Workspace:
    """In-memory Quantapy workspace used by the MVP API."""

    id: str
    project: WorkspaceStore = field(default_factory=WorkspaceStore)
    artifacts: ArtifactCatalog = field(default_factory=ArtifactCatalog)
    calculator: Optional[Calculator] = None
    strategy: Optional[Strategy] = None
    simulation: Optional[Simulate] = None
    latest_run_id: Optional[str] = None
    provider_keys: Dict[str, str] = field(default_factory=dict)

    @property
    def store(self) -> DataStore:
        return self.project.store


WORKSPACES: Dict[str, Workspace] = {}


class WorkspaceCreate(BaseModel):
    name: str = "Untitled"


class SampleDataRequest(BaseModel):
    symbol: str = "AAPL"
    rows: int = Field(default=240, ge=30, le=5000)
    interval: str = "1h"
    seed: int = 7


class FetchDataRequest(BaseModel):
    category: str = "Market"
    function: str = "OHLC"
    source: str = "FMP"
    params: Dict[str, Any] = Field(default_factory=dict)


class ArtifactImportRequest(BaseModel):
    path: str
    name: Optional[str] = None
    recursive: bool = True
    max_files: int = Field(default=200, ge=1, le=5000)


class ProviderKeyRequest(BaseModel):
    provider: str = "FMP"
    api_key: str


class SyntheticRequest(BaseModel):
    dataset_id: str
    n_trajectories: int = Field(default=3, ge=1, le=50)
    mean: float = 0.0
    stddev: float = 0.01


class CollectionMutationRequest(BaseModel):
    source_id: str
    name: Optional[str] = None
    n_trajectories: int = Field(default=5, ge=1, le=5000)
    mean: float = 0.0
    stddev: float = 0.01
    numeric_only: bool = True


class CollectionSplitRequest(BaseModel):
    source_id: str
    name: Optional[str] = None
    method: str = "holdout"
    train_ratio: float = 0.7
    val_ratio: float = 0.15
    test_ratio: float = 0.15
    n_folds: int = Field(default=3, ge=1, le=100)


class CollectionPrepareRequest(BaseModel):
    source_id: str
    name: Optional[str] = None
    recipe_record_id: Optional[str] = None
    operations: List[Dict[str, Any]] = Field(default_factory=list)


class TransformRequest(BaseModel):
    category: str = "Technical"
    function: str
    source: str = "Internal"
    name: str
    params: Dict[str, Any] = Field(default_factory=dict)


class DeriveRequest(BaseModel):
    dataset_id: str
    name: Optional[str] = None


class BasicTransformRequest(BaseModel):
    dataset_id: str
    operation: str = "add"
    left: str
    right: Optional[str] = None
    scalar: Optional[float] = None
    window: Optional[int] = Field(default=None, ge=1, le=10000)
    output: str = "calculated"
    name: Optional[str] = None


class CalculatorOperationPatch(BaseModel):
    operation: Dict[str, Any] = Field(default_factory=dict)


class StrategyRequest(BaseModel):
    dataset_id: str
    runner: str = "trading.backtest"
    executor_config: Dict[str, Any] = Field(default_factory=dict)
    template_id: Optional[str] = None
    leading: Optional[str] = None
    lagging: Optional[str] = None
    initial_investment: float = 10000.0
    transform_set_id: Optional[str] = None
    strategy_id: Optional[str] = None
    simulation_id: Optional[str] = None


class ValidationRequest(BaseModel):
    dataset_id: str
    runner: str = "trading.backtest"
    transform_set_id: Optional[str] = None
    strategy_id: Optional[str] = None
    simulation_id: Optional[str] = None
    validation: ComponentRequest = Field(
        default_factory=lambda: ComponentRequest(
            category="Validation",
            function="Holdout",
            source="Internal",
            params={"train_ratio": 0.75},
        )
    )


class ComponentRequest(BaseModel):
    category: str
    function: str
    source: str = "Internal"
    name: Optional[str] = None
    params: Dict[str, Any] = Field(default_factory=dict)


class StrategyDefinitionRequest(BaseModel):
    name: str = "Strategy"
    runner: str = "trading.backtest"
    signals: List[ComponentRequest] = Field(default_factory=list)
    orders: List[ComponentRequest] = Field(default_factory=list)


class ExecutionTemplateRequest(BaseModel):
    name: str = "Execution Template"
    runner: str
    sections: Dict[str, Any] = Field(default_factory=dict)
    config: Dict[str, Any] = Field(default_factory=dict)


class EvaluationRunRequest(BaseModel):
    evaluator: str
    run_id: Optional[str] = None
    input_ids: Dict[str, str] = Field(default_factory=dict)
    config: Dict[str, Any] = Field(default_factory=dict)
    name: Optional[str] = None


class SimulationConfigRequest(BaseModel):
    name: str = "Backtest"
    simulation: ComponentRequest = Field(
        default_factory=lambda: ComponentRequest(
            category="Simulation",
            function="Backtest",
            source="Internal",
            params={"initial_investment": 10000},
        )
    )
    evaluator: Optional[ComponentRequest] = None


class OptimizeParameter(BaseModel):
    target: str = "Transform"
    name: Optional[str] = None
    index: Optional[int] = None
    param: str
    dtype: str = "integer"
    low: Optional[float] = None
    high: Optional[float] = None
    choices: Optional[List[Any]] = None


class OptimizeRequest(BaseModel):
    dataset_id: str
    runner: str = "trading.backtest"
    derived_name: Optional[str] = None
    transform_set_id: Optional[str] = None
    strategy_id: Optional[str] = None
    simulation_id: Optional[str] = None
    validation: ComponentRequest = Field(
        default_factory=lambda: ComponentRequest(
            category="Validation",
            function="Holdout",
            source="Internal",
            params={"train_ratio": 0.75},
        )
    )
    best_trial: ComponentRequest = Field(
        default_factory=lambda: ComponentRequest(
            category="Best Trial",
            function="Distance from Ideal",
            source="Internal",
            params={},
        )
    )
    optimizer: ComponentRequest = Field(
        default_factory=lambda: ComponentRequest(
            category="Optimization",
            function="Bayesian",
            source="Internal",
            params={},
        )
    )
    train_ratio: float = Field(default=0.75, gt=0.1, lt=0.95)
    trials: int = Field(default=50, ge=1, le=500)
    objectives: List[str] = Field(default_factory=lambda: ["Maximize Profit"])
    parameters: List[OptimizeParameter]


app = FastAPI(title="Quantapy Workbench API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_workspace(workspace_id: str) -> Workspace:
    workspace = WORKSPACES.get(workspace_id)
    if workspace is None:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return workspace


def json_safe(value: Any) -> Any:
    """Convert numpy/pandas values into JSON-safe Python values."""
    if isinstance(value, dict):
        return {key: json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    if isinstance(value, np.ndarray):
        return [json_safe(item) for item in value.tolist()]
    if pd.isna(value):
        return None
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, (pd.Timestamp,)):
        return value.isoformat()
    return value


def record_to_dict(store: DataStore, record) -> Dict[str, Any]:
    parents = store.parents(record.id)
    children = store.children(record.id)
    return {
        "id": record.id,
        "name": record.name,
        "label": store.label(record),
        "kind": record.kind,
        "artifact": record.attrs.get("artifact"),
        "run_id": record.attrs.get("run_id"),
        "fold": record.attrs.get("fold"),
        "split": record.attrs.get("split"),
        "phase": record.attrs.get("phase"),
        "internal": store.is_internal(record),
        "shape": record.data.shape,
        "columns": record.data.columns,
        "attrs": record.attrs,
        "transform": record.transform,
        "parents": [{"id": parent.id, "name": parent.name} for parent in parents],
        "children": [{"id": child.id, "name": child.name} for child in children],
    }


def artifact_to_dict(artifact) -> Dict[str, Any]:
    """Return a JSON-safe artifact catalog record."""
    return json_safe(artifact.to_dict())


def store_summary(workspace: Workspace) -> Dict[str, Any]:
    records = [record_to_dict(workspace.store, record) for record in workspace.store.records()]
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for record in records:
        grouped.setdefault(record["kind"], []).append(record)
    return {
        "workspace_id": workspace.id,
        "latest_run_id": workspace.latest_run_id,
        "records": records,
        "visible_records": [
            record_to_dict(workspace.store, record)
            for record in workspace.store.visible_records()
        ],
        "navigation": workspace.store.navigation(),
        "artifacts": [artifact_to_dict(artifact) for artifact in workspace.artifacts.records()],
        "study_runs": workspace.store.study_runs(),
        "workspace": workspace.project.summary(),
        "grouped": grouped,
    }


def dataset_fetch_name(dataset_name: str, params: Dict[str, Any]) -> str:
    """Build a stable dataset name for a provider fetch configuration."""
    if not any(params.get(key) for key in ["interval", "date_range", "from_date", "to_date"]):
        return dataset_name.replace("/", "-").replace(":", "-")

    interval = str(params.get("interval") or "").replace(" ", "")
    date_range = str(params.get("date_range") or "")
    from_date = str(params.get("from_date") or "")
    to_date = str(params.get("to_date") or "")

    parts = [dataset_name]
    if interval:
        parts.append(interval)
    if date_range == "custom":
        if from_date or to_date:
            parts.append(f"{from_date or 'start'}_to_{to_date or 'latest'}")
        else:
            parts.append("custom")
    elif date_range:
        parts.append(date_range)

    return "_".join(
        part.replace("/", "-").replace(":", "-")
        for part in parts
        if part
    )


def dataset_date_bounds(dataset: Any) -> Dict[str, Optional[str]]:
    """Return first and last date values for list/DataFrame-like fetched data."""
    if isinstance(dataset, list):
        dates = [row.get("date") for row in dataset if isinstance(row, dict) and row.get("date") is not None]
    elif isinstance(dataset, pd.DataFrame) and "date" in dataset.columns:
        dates = dataset["date"].dropna().astype(str).tolist()
    else:
        dates = []

    if not dates:
        return {"actual_from": None, "actual_to": None}
    ordered = sorted(str(value) for value in dates)
    return {"actual_from": ordered[0], "actual_to": ordered[-1]}


def coverage_metadata(
    requested_window: Dict[str, str],
    actual_bounds: Dict[str, Optional[str]],
    fetch_metadata: Optional[Dict[str, Any]] = None,
    grace_days: int = 3,
) -> Dict[str, Any]:
    """Return metadata describing whether provider coverage matched the request."""
    fetch_metadata = fetch_metadata or {}
    if fetch_metadata.get("missing_data"):
        empty_chunks = fetch_metadata.get("empty_chunks", 0)
        partial_chunks = fetch_metadata.get("partial_chunks", 0)
        return {
            "coverage": "partial",
            "coverage_warning": (
                f"Provider returned {empty_chunks} empty chunk(s) and "
                f"{partial_chunks} partial chunk(s)."
            ),
        }

    requested_from = requested_window.get("from")
    actual_from = actual_bounds.get("actual_from")
    if requested_from and actual_from:
        requested_date = datetime.strptime(requested_from, "%Y-%m-%d").date()
        actual_date = datetime.strptime(str(actual_from)[:10], "%Y-%m-%d").date()
        if (actual_date - requested_date).days <= grace_days:
            return {"coverage": "complete", "coverage_warning": None}
        return {
            "coverage": "partial",
            "coverage_warning": (
                f"Provider returned data starting {actual_from}, "
                f"but the request started {requested_from}."
            ),
        }
    return {"coverage": "complete", "coverage_warning": None}


def calculator_dataset_name(source_name: str) -> str:
    """Return the stable derived dataset name for calculator outputs."""
    return f"{source_name}-Calculator"


def calculator_context(workspace: Workspace, record) -> tuple[Any, Any, pd.DataFrame]:
    """Return source record, calculator record, and cumulative calculator DataFrame."""
    if record.attrs.get("artifact") == "calculator":
        source_id = record.attrs.get("source_record_id") or (record.parent_ids[0] if record.parent_ids else record.id)
        source_record = workspace.store.get_record(str(source_id)) or record
        calculator_record = record
    else:
        source_record = record
        calculator_record = next(
            (
                candidate
                for candidate in workspace.store.records()
                if candidate.attrs.get("artifact") == "calculator"
                and candidate.attrs.get("source_record_id") == source_record.id
            ),
            None,
        )

    base_record = calculator_record or source_record
    df = workspace.store.to_dataframe(base_record.id)
    if df is None:
        raise HTTPException(status_code=400, detail="Dataset could not be loaded")
    return source_record, calculator_record, df.copy()


def calculator_operations(calculator_record) -> List[Dict[str, Any]]:
    if calculator_record and isinstance(calculator_record.transform, dict):
        operations = calculator_record.transform.get("operations", [])
        if isinstance(operations, list):
            return [dict(operation) for operation in operations if isinstance(operation, dict)]
    return []


def apply_basic_operation(df: pd.DataFrame, operation: Dict[str, Any]) -> pd.DataFrame:
    left_name = str(operation.get("left") or "")
    if left_name not in df.columns:
        raise HTTPException(status_code=400, detail=f"Left column not found: {left_name}")

    left = pd.to_numeric(df[left_name], errors="coerce")
    right = None
    right_name = operation.get("right")
    if right_name:
        if str(right_name) not in df.columns:
            raise HTTPException(status_code=400, detail=f"Right column not found: {right_name}")
        right = pd.to_numeric(df[str(right_name)], errors="coerce")

    operation_name = str(operation.get("operation") or "add")
    scalar = operation.get("scalar")
    if scalar is None:
        scalar = 0.0
    if operation_name in {"add", "subtract", "multiply", "divide"} and right is None and operation.get("scalar") is None:
        raise HTTPException(status_code=400, detail="Choose a right column or scalar")

    if operation_name == "add":
        result = left + (right if right is not None else float(scalar))
    elif operation_name == "subtract":
        result = left - (right if right is not None else float(scalar))
    elif operation_name == "multiply":
        result = left * (right if right is not None else float(scalar))
    elif operation_name == "divide":
        denominator = right if right is not None else float(scalar)
        if isinstance(denominator, pd.Series):
            result = left / denominator.replace(0, np.nan)
        else:
            result = left / (denominator if denominator else np.nan)
    elif operation_name == "diff":
        result = left.diff(int(operation.get("window") or 1))
    elif operation_name == "pct_change":
        result = left.pct_change(int(operation.get("window") or 1))
    elif operation_name == "rolling_mean":
        result = left.rolling(int(operation.get("window") or 20), min_periods=1).mean()
    elif operation_name == "rolling_std":
        result = left.rolling(int(operation.get("window") or 20), min_periods=2).std()
    elif operation_name == "normalize":
        span = left.max() - left.min()
        result = (left - left.min()) / (span if span else np.nan)
    elif operation_name == "zscore":
        std = left.std()
        result = (left - left.mean()) / (std if std else np.nan)
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported operation: {operation_name}")

    output = str(operation.get("output") or operation_name).strip() or operation_name
    next_df = df.copy()
    next_df[output] = result
    return next_df


def apply_registered_operation(df: pd.DataFrame, operation: Dict[str, Any]) -> pd.DataFrame:
    transforms = operation.get("transforms", [])
    if isinstance(transforms, dict):
        transforms = [
            {"name": name, **config}
            for name, config in transforms.items()
            if isinstance(config, dict)
        ]
    if not isinstance(transforms, list) or not transforms:
        raise HTTPException(status_code=400, detail="Registered operation has no transform recipe")

    temp_store = DataStore()
    temp_store.add_raw("__calculator_input__", df)
    calculator = Calculator()
    for transform in transforms:
        if not isinstance(transform, dict):
            continue
        params = dict(transform.get("params") or {})
        name = transform.get("name") or params.get("name") or transform.get("function")
        calculator.add_transform(
            str(transform.get("category") or "Technical"),
            str(transform.get("function")),
            str(transform.get("source") or "Internal"),
            name=str(name),
            **{key: value for key, value in params.items() if key != "name"},
        )

    try:
        result = calculator.derive_combined(temp_store, "__calculator_input__")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return result.to_dataframe() if hasattr(result, "to_dataframe") else result


def calculator_from_operations(operations: List[Dict[str, Any]]) -> Calculator:
    """Build an optimizable calculator from registered calculator operations."""
    calculator = Calculator()
    for operation in operations:
        if operation.get("type") != "registered":
            continue
        transforms = operation.get("transforms", [])
        if isinstance(transforms, dict):
            transforms = [
                {"name": name, **config}
                for name, config in transforms.items()
                if isinstance(config, dict)
            ]
        if not isinstance(transforms, list):
            continue
        for transform in transforms:
            if not isinstance(transform, dict):
                continue
            params = dict(transform.get("params") or {})
            name = (
                transform.get("name")
                or operation.get("name")
                or params.get("name")
                or transform.get("function")
            )
            if not transform.get("function"):
                continue
            calculator.add_transform(
                str(transform.get("category") or "Technical"),
                str(transform.get("function")),
                str(transform.get("source") or "Internal"),
                name=str(name),
                **{key: value for key, value in params.items() if key != "name"},
            )
    return calculator


def constrain_optimization_parameters(study: Study) -> None:
    """Clamp user-provided optimization ranges to component schema limits."""
    for parameter in study.parameters:
        if parameter.target.lower() not in {"transform", "calculator"}:
            continue
        if parameter.name not in study.calculator.transforms:
            continue
        transform_config = study.calculator.transforms[parameter.name]
        transform_obj = transform_config["cls"](**transform_config["params"])
        schema = transform_obj.get_config() if hasattr(transform_obj, "get_config") else {}
        field_schema = (schema.get("properties") or {}).get(parameter.param) or {}
        optimizable = field_schema.get("optimizable")
        if not isinstance(optimizable, dict):
            continue

        minimum = optimizable.get("min", optimizable.get("low"))
        maximum = optimizable.get("max", optimizable.get("high"))
        if minimum is not None and parameter.low is not None:
            parameter.low = max(float(parameter.low), float(minimum))
        if maximum is not None and parameter.high is not None:
            parameter.high = min(float(parameter.high), float(maximum))
        if parameter.low is not None and parameter.high is not None and parameter.low > parameter.high:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Invalid optimization bounds for {parameter.name}.{parameter.param}: "
                    f"{parameter.low}..{parameter.high}"
                ),
            )


def replay_calculator_dataset(
    workspace: Workspace,
    source_record,
    calculator_record,
    operations: List[Dict[str, Any]],
) -> Any:
    source_df = workspace.store.to_dataframe(source_record.id)
    if source_df is None:
        raise HTTPException(status_code=400, detail="Source dataset could not be loaded")

    output_df = source_df.copy()
    normalized_operations = []
    for operation in operations:
        next_operation = dict(operation)
        next_operation.setdefault("id", str(uuid4()))
        op_type = next_operation.get("type")
        if op_type == "basic":
            output_df = apply_basic_operation(output_df, next_operation)
        elif op_type == "registered":
            output_df = apply_registered_operation(output_df, next_operation)
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported calculator operation type: {op_type}")
        normalized_operations.append(next_operation)

    attrs = {
        **source_record.attrs,
        "artifact": "calculator",
        "source_record_id": source_record.id,
        "source_record_name": source_record.name,
        "calculator_operation_count": len(normalized_operations),
    }
    derived_id = workspace.store.add_child(
        calculator_dataset_name(source_record.name),
        output_df,
        parent_ids=[source_record.id],
        kind="derived",
        attrs=attrs,
        transform={"name": "Calculator", "operations": normalized_operations},
        dataset_id=calculator_record.id if calculator_record else None,
    )
    return workspace.store.get_record(derived_id)


def upsert_calculator_dataset(
    workspace: Workspace,
    source_record,
    calculator_record,
    df: pd.DataFrame,
    operation: Dict[str, Any],
) -> Any:
    """Create or update the single calculator copy for a raw source dataset."""
    operations = calculator_operations(calculator_record)
    operation = dict(operation)
    operation.setdefault("id", str(uuid4()))
    operations.append(operation)
    return replay_calculator_dataset(workspace, source_record, calculator_record, operations)


def latest_transform_operation(workspace: Workspace, fallback_name: str) -> Dict[str, Any]:
    transform_set = workspace.project.transform_sets.get(workspace.project.active_transform_set_id or "")
    if transform_set is None or not transform_set.transforms:
        raise HTTPException(status_code=400, detail="No registered transform is configured")
    spec = transform_set.transforms[-1]
    return {
        "type": "registered",
        "name": fallback_name or spec.name or spec.function,
        "transforms": [
            {
                "id": spec.id,
                "category": spec.category,
                "function": spec.function,
                "source": spec.source,
                "name": spec.name or spec.function,
                "params": dict(spec.params),
            }
        ],
    }


def make_sample_ohlc(request: SampleDataRequest) -> pd.DataFrame:
    rng = np.random.default_rng(request.seed)
    dates = pd.date_range(end=pd.Timestamp.now().floor("h"), periods=request.rows, freq=request.interval)
    drift = rng.normal(0.02, 0.9, request.rows).cumsum()
    close = 100 + drift + np.linspace(0, 12, request.rows)
    open_ = close + rng.normal(0, 0.35, request.rows)
    high = np.maximum(open_, close) + rng.uniform(0.1, 1.2, request.rows)
    low = np.minimum(open_, close) - rng.uniform(0.1, 1.2, request.rows)
    volume = rng.integers(100_000, 1_000_000, request.rows)
    return pd.DataFrame({
        "date": dates,
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume,
    })


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.post("/workspaces")
def create_workspace(request: WorkspaceCreate) -> Dict[str, Any]:
    workspace = Workspace(id=str(uuid4()))
    WORKSPACES[workspace.id] = workspace
    return {"id": workspace.id, "name": request.name}


@app.get("/components")
def components() -> Dict[str, Any]:
    return {
        category: {
            function: {
                source: cls.config if hasattr(cls, "config") else {}
                for source, cls in sources.items()
            }
            for function, sources in functions.items()
        }
        for category, functions in COMPONENT_REGISTRY.items()
    }


@app.get("/executors")
def executors() -> Dict[str, Any]:
    """Return registered executor plugins and their template metadata."""
    return executor_metadata()


@app.get("/evaluators")
def evaluators() -> Dict[str, Any]:
    """Return registered evaluator plugins and their metadata."""
    return evaluator_metadata()


@app.put("/workspaces/{workspace_id}/provider-keys")
def set_provider_key(workspace_id: str, request: ProviderKeyRequest) -> Dict[str, Any]:
    workspace = get_workspace(workspace_id)
    workspace.provider_keys[request.provider] = request.api_key
    return {"providers": sorted(workspace.provider_keys.keys())}


@app.get("/workspaces/{workspace_id}/store")
def get_store(workspace_id: str) -> Dict[str, Any]:
    return store_summary(get_workspace(workspace_id))


@app.post("/workspaces/{workspace_id}/uploads")
async def upload_data_file(workspace_id: str, file: UploadFile = File(...)) -> Dict[str, Any]:
    get_workspace(workspace_id)
    filename = Path(file.filename or "upload").name
    upload_dir = UPLOAD_ROOT / workspace_id
    upload_dir.mkdir(parents=True, exist_ok=True)
    destination = upload_dir / f"{uuid4()}-{filename}"
    destination.write_bytes(await file.read())
    return {"path": str(destination), "filename": filename}


@app.post("/workspaces/{workspace_id}/artifacts/import")
def import_artifact_path(workspace_id: str, request: ArtifactImportRequest) -> Dict[str, Any]:
    workspace = get_workspace(workspace_id)
    try:
        result = import_path(
            request.path,
            catalog=workspace.artifacts,
            store=workspace.store,
            name=request.name,
            recursive=request.recursive,
            max_files=request.max_files,
            provenance={"method": "path"},
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Path not found: {request.path}") from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    collection = create_raw_collection(
        workspace.artifacts,
        workspace.store,
        name=request.name or Path(request.path).expanduser().name,
        artifact_ids=[artifact.id for artifact in result.artifacts],
        dataset_ids=result.dataset_ids,
        provenance={"method": "path"},
    )
    return {
        "store": store_summary(workspace),
        "artifacts": [artifact_to_dict(artifact) for artifact in result.artifacts],
        "collection": artifact_to_dict(collection),
        "dataset_ids": result.dataset_ids,
        "warnings": result.warnings,
    }


@app.post("/workspaces/{workspace_id}/artifacts/upload")
async def upload_and_import_artifact(workspace_id: str, file: UploadFile = File(...)) -> Dict[str, Any]:
    uploaded = await upload_data_file(workspace_id, file)
    return import_artifact_path(
        workspace_id,
        ArtifactImportRequest(path=uploaded["path"], name=uploaded["filename"]),
    )


@app.get("/workspaces/{workspace_id}/model")
def get_workspace_model(workspace_id: str) -> Dict[str, Any]:
    workspace = get_workspace(workspace_id)
    return workspace.project.summary()


@app.get("/workspaces/{workspace_id}/artifacts/{artifact_id}/text")
def get_text_artifact(workspace_id: str, artifact_id: str, limit: int = 200000) -> Dict[str, Any]:
    workspace = get_workspace(workspace_id)
    artifact = workspace.artifacts.get(artifact_id)
    if artifact is None:
        raise HTTPException(status_code=404, detail="Artifact not found")
    if artifact.artifact_type not in {"text", "file"} and artifact.role not in {"text", "raw_file"}:
        raise HTTPException(status_code=400, detail="Artifact is not a text/file artifact")
    text = str(artifact.metadata.get("preview") or "")
    if artifact.uri:
        path = Path(artifact.uri)
        if path.exists() and path.is_file():
            text = path.read_text(encoding="utf-8", errors="replace")[:limit]
    return {"artifact": artifact_to_dict(artifact), "text": text}


@app.get("/workspaces/{workspace_id}/records/{record_id}/frame")
def get_record_frame(workspace_id: str, record_id: str, limit: int = 1000) -> Dict[str, Any]:
    workspace = get_workspace(workspace_id)
    record = workspace.store.get_record(record_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Record not found")
    df = workspace.store.to_dataframe(record)
    if "date" in df.columns:
        sorted_df = df.copy()
        sorted_df["_quantapy_sort_date"] = pd.to_datetime(sorted_df["date"], errors="coerce")
        sorted_df = sorted_df.sort_values(["_quantapy_sort_date", "date"], kind="mergesort")
        df = sorted_df.drop(columns=["_quantapy_sort_date"])
    df = df.head(limit)
    return {
        "record": record_to_dict(workspace.store, record),
        "columns": list(df.columns),
        "rows": [
            {column: json_safe(value) for column, value in row.items()}
            for row in df.to_dict(orient="records")
        ],
    }


@app.delete("/workspaces/{workspace_id}/records/{record_id}")
def delete_record(workspace_id: str, record_id: str, cascade: bool = False) -> Dict[str, Any]:
    workspace = get_workspace(workspace_id)
    record = workspace.store.get_record(record_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Record not found")
    try:
        workspace.store.remove(record.id, cascade=cascade)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return store_summary(workspace)


@app.post("/workspaces/{workspace_id}/data/sample")
def add_sample_data(workspace_id: str, request: SampleDataRequest) -> Dict[str, Any]:
    workspace = get_workspace(workspace_id)
    name = f"OHLC_{request.symbol.upper()}"
    dataset_id, artifact = create_dataset_artifact(
        workspace.artifacts,
        workspace.store,
        name=name,
        dataframe=make_sample_ohlc(request),
        kind="raw",
        role="raw_data",
        attrs={"symbol": request.symbol.upper(), "artifact": "source"},
        provenance={"provider": "sample"},
    )
    create_raw_collection(
        workspace.artifacts,
        workspace.store,
        name=name,
        artifact_ids=[artifact.id],
        dataset_ids=[dataset_id],
        provenance={"provider": "sample"},
    )
    return store_summary(workspace)


@app.post("/workspaces/{workspace_id}/data/fetch")
def fetch_data(workspace_id: str, request: FetchDataRequest) -> Dict[str, Any]:
    workspace = get_workspace(workspace_id)
    if request.category == "Dataset" and request.function == "Artifact" and request.source == "Local":
        params = dict(request.params)
        try:
            result = import_path(
                params.get("path", ""),
                catalog=workspace.artifacts,
                store=workspace.store,
                name=params.get("name"),
                recursive=str(params.get("recursive", "true")).lower() == "true",
                max_files=int(params.get("max_files") or 200),
                provenance={"provider": "Dataset.Artifact.Local", "method": "data_provider"},
            )
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=f"Path not found: {params.get('path', '')}") from exc
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        create_raw_collection(
            workspace.artifacts,
            workspace.store,
            name=str(params.get("name") or Path(str(params.get("path", ""))).expanduser().name or "Imported Data"),
            artifact_ids=[artifact.id for artifact in result.artifacts],
            dataset_ids=result.dataset_ids,
            provenance={"provider": "Dataset.Artifact.Local", "method": "data_provider"},
        )
        summary = store_summary(workspace)
        if result.warnings:
            summary["artifact_warnings"] = result.warnings
        return summary

    data = Data()
    params = dict(request.params)
    if request.source in workspace.provider_keys and "api_key" not in params:
        params["api_key"] = workspace.provider_keys[request.source]
    data.add_provider(request.category, request.function, request.source, **params)
    requested_window = {}
    if data.providers and hasattr(data.providers[0][1], "_date_window"):
        requested_window = data.providers[0][1]._date_window()
    fetched = data.fetch()
    provider_metadata = (
        getattr(data.providers[0][1], "fetch_metadata", {})
        if data.providers
        else {}
    )
    raw_dataset_ids: List[str] = []
    raw_artifact_ids: List[str] = []
    for dataset_name, dataset in fetched.items():
        record_name = dataset_fetch_name(dataset_name, params)
        symbol = dataset_name.replace("OHLC_", "") if dataset_name.startswith("OHLC_") else dataset_name
        fetch_metadata = provider_metadata.get(symbol, {})
        date_bounds = dataset_date_bounds(dataset)
        coverage = coverage_metadata(
            requested_window,
            date_bounds,
            fetch_metadata,
            grace_days=int(params.get("coverage_grace_days") or 3),
        )
        dataset_id, artifact = create_dataset_artifact(
            workspace.artifacts,
            workspace.store,
            name=record_name,
            dataframe=dataset.to_dataframe() if hasattr(dataset, "to_dataframe") else pd.DataFrame(dataset),
            kind="raw",
            role="raw_data",
            attrs={
                "symbol": symbol,
                "artifact": "source",
                "provider": request.source,
                "function": request.function,
                "category": request.category,
                "interval": params.get("interval"),
                "date_range": params.get("date_range"),
                "from_date": params.get("from_date"),
                "to_date": params.get("to_date"),
                "requested_from": requested_window.get("from"),
                "requested_to": requested_window.get("to"),
                "limit": params.get("limit"),
                **date_bounds,
                **fetch_metadata,
                **coverage,
            },
            provenance={"provider": request.function, "source": request.source, "params": params},
        )
        raw_dataset_ids.append(dataset_id)
        raw_artifact_ids.append(artifact.id)
    if raw_dataset_ids or raw_artifact_ids:
        create_raw_collection(
            workspace.artifacts,
            workspace.store,
            name=f"{request.source} {request.function}",
            artifact_ids=raw_artifact_ids,
            dataset_ids=raw_dataset_ids,
            provenance={"provider": request.function, "source": request.source, "params": params},
        )
    return store_summary(workspace)


@app.post("/workspaces/{workspace_id}/data/synthetic")
def add_synthetic_data(workspace_id: str, request: SyntheticRequest) -> Dict[str, Any]:
    workspace = get_workspace(workspace_id)
    record = workspace.store.get_record(request.dataset_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Dataset not found")
    data = Data()
    data.add_transformer(
        "Noise",
        "GaussianNoise",
        "Internal",
        n_trajectories=request.n_trajectories,
        mean=request.mean,
        stddev=request.stddev,
    )
    for name, synthetic in data.transform(record.name, record.data).items():
        workspace.store.add_child(
            name,
            synthetic,
            parent_ids=[record.id],
            kind="synthetic",
            attrs={**record.attrs, "synthetic": True, "artifact": "source"},
            transform={"name": "GaussianNoise"},
        )
    return store_summary(workspace)


@app.post("/workspaces/{workspace_id}/collections/mutate/gaussian-noise")
def mutate_gaussian_collection(workspace_id: str, request: CollectionMutationRequest) -> Dict[str, Any]:
    workspace = get_workspace(workspace_id)
    try:
        result = gaussian_noise_collection(
            workspace.artifacts,
            workspace.store,
            source_id=request.source_id,
            name=request.name,
            n_trajectories=request.n_trajectories,
            mean=request.mean,
            stddev=request.stddev,
            numeric_only=request.numeric_only,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "store": store_summary(workspace),
        "collection": artifact_to_dict(result.collection),
        "dataset_ids": result.dataset_ids,
        "artifact_ids": result.artifact_ids,
    }


@app.post("/workspaces/{workspace_id}/collections/split")
def split_collection(workspace_id: str, request: CollectionSplitRequest) -> Dict[str, Any]:
    workspace = get_workspace(workspace_id)
    try:
        result = split_artifact_or_collection(
            workspace.artifacts,
            workspace.store,
            source_id=request.source_id,
            name=request.name,
            method=request.method,
            train_ratio=request.train_ratio,
            val_ratio=request.val_ratio,
            test_ratio=request.test_ratio,
            n_folds=request.n_folds,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "store": store_summary(workspace),
        "collection": artifact_to_dict(result.collection),
        "dataset_ids": result.dataset_ids,
        "artifact_ids": result.artifact_ids,
    }


@app.post("/workspaces/{workspace_id}/collections/prepare/calculator")
def prepare_collection_with_calculator(workspace_id: str, request: CollectionPrepareRequest) -> Dict[str, Any]:
    workspace = get_workspace(workspace_id)
    operations = list(request.operations or [])
    if request.recipe_record_id:
        recipe_record = workspace.store.get_record(request.recipe_record_id)
        if recipe_record is None:
            raise HTTPException(status_code=404, detail="Calculator recipe record not found")
        operations = calculator_operations(recipe_record)
    if not operations:
        raise HTTPException(status_code=400, detail="No calculator operations provided")
    calculator = calculator_from_operations(operations)
    try:
        result = apply_calculator_to_artifact_or_collection(
            workspace.artifacts,
            workspace.store,
            source_id=request.source_id,
            calculator=calculator,
            name=request.name,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "store": store_summary(workspace),
        "collection": artifact_to_dict(result.collection),
        "dataset_ids": result.dataset_ids,
        "artifact_ids": result.artifact_ids,
    }


@app.post("/workspaces/{workspace_id}/calculator/transforms")
def add_transform(workspace_id: str, request: TransformRequest) -> Dict[str, Any]:
    workspace = get_workspace(workspace_id)
    spec = workspace.project.add_transform(
        request.category,
        request.function,
        request.source,
        name=request.name,
        params=request.params,
    )
    workspace.calculator = workspace.project.calculator()
    return {"transform": spec, "transforms": workspace.calculator.list_transforms()}


@app.post("/workspaces/{workspace_id}/calculator/derive")
def derive_indicators(workspace_id: str, request: DeriveRequest) -> Dict[str, Any]:
    workspace = get_workspace(workspace_id)
    record = workspace.store.get_record(request.dataset_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Dataset not found")
    source_record, calculator_record, _ = calculator_context(workspace, record)
    operation = latest_transform_operation(workspace, request.name or "Indicators")
    working_df = workspace.store.to_dataframe((calculator_record or source_record).id)
    if working_df is None:
        raise HTTPException(status_code=400, detail="Dataset could not be loaded")
    output_df = apply_registered_operation(working_df, operation)
    calculator_record = upsert_calculator_dataset(
        workspace,
        source_record,
        calculator_record,
        output_df,
        operation,
    )
    summary = store_summary(workspace)
    return {"store": summary, "record": record_to_dict(workspace.store, calculator_record)}


@app.post("/workspaces/{workspace_id}/calculator/basic")
def derive_basic_transform(workspace_id: str, request: BasicTransformRequest) -> Dict[str, Any]:
    workspace = get_workspace(workspace_id)
    record = workspace.store.get_record(request.dataset_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Dataset not found")

    source_record, calculator_record, df = calculator_context(workspace, record)
    if df is None or request.left not in df.columns:
        raise HTTPException(status_code=400, detail="Left column not found")

    left = pd.to_numeric(df[request.left], errors="coerce")
    right = None
    if request.right:
        if request.right not in df.columns:
            raise HTTPException(status_code=400, detail="Right column not found")
        right = pd.to_numeric(df[request.right], errors="coerce")

    operation = request.operation
    scalar = request.scalar if request.scalar is not None else 0.0
    if operation in {"add", "subtract", "multiply", "divide"} and right is None and request.scalar is None:
        raise HTTPException(status_code=400, detail="Choose a right column or scalar")

    if operation == "add":
        result = left + (right if right is not None else scalar)
    elif operation == "subtract":
        result = left - (right if right is not None else scalar)
    elif operation == "multiply":
        result = left * (right if right is not None else scalar)
    elif operation == "divide":
        denominator = right if right is not None else scalar
        if isinstance(denominator, pd.Series):
            result = left / denominator.replace(0, np.nan)
        else:
            result = left / (denominator if denominator else np.nan)
    elif operation == "diff":
        result = left.diff(int(request.window or 1))
    elif operation == "pct_change":
        result = left.pct_change(int(request.window or 1))
    elif operation == "rolling_mean":
        result = left.rolling(int(request.window or 20), min_periods=1).mean()
    elif operation == "rolling_std":
        result = left.rolling(int(request.window or 20), min_periods=2).std()
    elif operation == "normalize":
        span = left.max() - left.min()
        result = (left - left.min()) / (span if span else np.nan)
    elif operation == "zscore":
        std = left.std()
        result = (left - left.mean()) / (std if std else np.nan)
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported operation: {operation}")

    output = request.output.strip() or operation
    output_df = df.copy()
    output_df[output] = result
    calculator_record = upsert_calculator_dataset(
        workspace,
        source_record,
        calculator_record,
        output_df,
        {
            "type": "basic",
            "operation": operation,
            "left": request.left,
            "right": request.right,
            "scalar": request.scalar,
            "window": request.window,
            "output": output,
        },
    )
    summary = store_summary(workspace)
    return {"store": summary, "record": record_to_dict(workspace.store, calculator_record)}


@app.get("/workspaces/{workspace_id}/calculator/{record_id}/operations")
def get_calculator_operations(workspace_id: str, record_id: str) -> Dict[str, Any]:
    workspace = get_workspace(workspace_id)
    record = workspace.store.get_record(record_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Calculator dataset not found")
    _, calculator_record, _ = calculator_context(workspace, record)
    if calculator_record is None:
        return {"operations": []}
    return {
        "record": record_to_dict(workspace.store, calculator_record),
        "operations": calculator_operations(calculator_record),
    }


@app.patch("/workspaces/{workspace_id}/calculator/{record_id}/operations/{operation_id}")
def update_calculator_operation(
    workspace_id: str,
    record_id: str,
    operation_id: str,
    request: CalculatorOperationPatch,
) -> Dict[str, Any]:
    workspace = get_workspace(workspace_id)
    record = workspace.store.get_record(record_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Calculator dataset not found")
    source_record, calculator_record, _ = calculator_context(workspace, record)
    if calculator_record is None:
        raise HTTPException(status_code=404, detail="Calculator dataset not found")

    operations = calculator_operations(calculator_record)
    for index, operation in enumerate(operations):
        if operation.get("id") == operation_id:
            old_output = operation.get("output")
            operations[index] = {**operation, **request.operation, "id": operation_id}
            new_output = operations[index].get("output")
            if old_output and new_output and old_output != new_output:
                for later_operation in operations[index + 1:]:
                    if later_operation.get("left") == old_output:
                        later_operation["left"] = new_output
                    if later_operation.get("right") == old_output:
                        later_operation["right"] = new_output
                    for transform in later_operation.get("transforms", []) if isinstance(later_operation.get("transforms"), list) else []:
                        params = transform.get("params", {}) if isinstance(transform, dict) else {}
                        for key, value in list(params.items()):
                            if value == old_output:
                                params[key] = new_output
            next_record = replay_calculator_dataset(workspace, source_record, calculator_record, operations)
            summary = store_summary(workspace)
            return {"store": summary, "record": record_to_dict(workspace.store, next_record)}
    raise HTTPException(status_code=404, detail="Calculator operation not found")


@app.delete("/workspaces/{workspace_id}/calculator/{record_id}/operations/{operation_id}")
def delete_calculator_operation(workspace_id: str, record_id: str, operation_id: str) -> Dict[str, Any]:
    workspace = get_workspace(workspace_id)
    record = workspace.store.get_record(record_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Calculator dataset not found")
    source_record, calculator_record, _ = calculator_context(workspace, record)
    if calculator_record is None:
        raise HTTPException(status_code=404, detail="Calculator dataset not found")

    operations = calculator_operations(calculator_record)
    next_operations = [operation for operation in operations if operation.get("id") != operation_id]
    if len(next_operations) == len(operations):
        raise HTTPException(status_code=404, detail="Calculator operation not found")
    next_record = replay_calculator_dataset(workspace, source_record, calculator_record, next_operations)
    summary = store_summary(workspace)
    return {"store": summary, "record": record_to_dict(workspace.store, next_record)}


def ensure_execution_defaults(workspace: Workspace, request: StrategyRequest) -> None:
    if request.strategy_id is not None:
        workspace.project.active_strategy_id = request.strategy_id
    elif workspace.project.active_strategy_id is None and request.leading and request.lagging:
        workspace.project.add_strategy(
            f"Crossover Strategy ({request.leading}/{request.lagging})",
            runner=request.runner,
            signals=[
                {
                    "category": "Signal",
                    "function": "Crossover",
                    "source": "Internal",
                    "params": {
                        "value1": request.leading,
                        "value2": request.lagging,
                        "action": "enter",
                        "direction": "long",
                    },
                },
                {
                    "category": "Signal",
                    "function": "Crossunder",
                    "source": "Internal",
                    "params": {
                        "value1": request.leading,
                        "value2": request.lagging,
                        "action": "exit",
                        "direction": "long",
                    },
                },
            ],
            orders=[
                {
                    "category": "Order",
                    "function": "Market",
                    "source": "Internal",
                    "params": {"on_signal": "entry", "on_price": "close", "on_bar": "current"},
                },
                {
                    "category": "Order",
                    "function": "Market",
                    "source": "Internal",
                    "params": {"on_signal": "exit", "on_price": "close", "on_bar": "current"},
                },
            ],
        )
    elif workspace.project.active_strategy_id is None:
        raise HTTPException(status_code=400, detail="Save an execution template before running")

    if workspace.project.active_simulation_id is None:
        workspace.project.add_simulation(
            "Default Backtest",
            simulation={
                "category": "Simulation",
                "function": "Backtest",
                "source": "Internal",
                "params": {"initial_investment": request.initial_investment},
            },
            evaluator=None,
        )


def active_strategy_definition(workspace: Workspace, strategy_id: Optional[str] = None):
    definition = workspace.project.strategies.get(strategy_id or workspace.project.active_strategy_id or "")
    if definition is None:
        raise HTTPException(status_code=400, detail="Save an execution template before running")
    return definition


def required_strategy_columns(workspace: Workspace, request: StrategyRequest) -> List[str]:
    """Return dataset columns referenced by the configured strategy/simulation."""
    definition = active_strategy_definition(workspace, request.strategy_id)
    required = {"close"}
    for spec in [*definition.signals, *definition.orders]:
        for key in ["value1", "value2", "on_price", "price", "real"]:
            value = spec.params.get(key)
            if isinstance(value, str) and value:
                required.add(value)

    simulation_config = workspace.project.simulations.get(request.simulation_id or workspace.project.active_simulation_id or "")
    if simulation_config is not None:
        close_on_completion = simulation_config.simulation.params.get("close_on_completion")
        if isinstance(close_on_completion, str) and close_on_completion:
            required.add(close_on_completion)
    return sorted(required)


def configure_pipeline(workspace: Workspace, request: StrategyRequest) -> None:
    ensure_execution_defaults(workspace, request)
    try:
        workspace.calculator = workspace.project.calculator(request.transform_set_id)
    except ValueError:
        workspace.calculator = Calculator()
    workspace.strategy = workspace.project.strategy(workspace.calculator, request.strategy_id)
    workspace.simulation = workspace.project.simulation(workspace.strategy, request.simulation_id)


def component_config(spec) -> Dict[str, Any]:
    """Return a portable component config for executor templates."""
    return {
        "category": spec.category,
        "function": spec.function,
        "source": spec.source,
        "name": spec.name,
        "params": dict(spec.params or {}),
    }


def portable_component_config(spec: Any) -> Dict[str, Any]:
    """Return a component config from pydantic, dataclass, or plain dict input."""
    if hasattr(spec, "model_dump"):
        payload = spec.model_dump()
    elif hasattr(spec, "__dataclass_fields__"):
        payload = component_config(spec)
    else:
        payload = dict(spec or {})
    return {
        "category": payload.get("category"),
        "function": payload.get("function"),
        "source": payload.get("source", "Internal"),
        "name": payload.get("name"),
        "params": dict(payload.get("params") or {}),
    }


def set_nested_config(target: Dict[str, Any], path: str, value: Any) -> None:
    """Set a dotted config path on a nested dictionary."""
    parts = [part for part in path.split(".") if part]
    if not parts:
        return
    cursor = target
    for part in parts[:-1]:
        next_value = cursor.get(part)
        if not isinstance(next_value, dict):
            next_value = {}
            cursor[part] = next_value
        cursor = next_value
    cursor[parts[-1]] = value


def active_execution_template(workspace: Workspace, runner: str, template_id: Optional[str] = None):
    """Return the selected generic execution template for a runner, if present."""
    candidate_id = template_id or workspace.project.active_execution_template_id
    template = workspace.project.execution_templates.get(candidate_id or "")
    if template is None or template.runner != runner:
        return None
    return template


def execution_template_config_document(workspace: Workspace, runner: str, template_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Build a runner config document from a generic execution template."""
    template = active_execution_template(workspace, runner, template_id)
    if template is None:
        return None
    config = {
        **dict(template.config or {}),
        "runner": runner,
        "template": {
            "id": template.id,
            "name": template.name,
            "type": runner,
        },
    }
    for key, value in template.sections.items():
        if isinstance(value, list):
            section_value = [portable_component_config(item) for item in value]
        elif value:
            section_value = portable_component_config(value)
        else:
            section_value = [] if key.endswith("s") else None
        set_nested_config(config, key, section_value)
    return config


def execution_config_document(workspace: Workspace, request: StrategyRequest) -> Dict[str, Any]:
    """Build the config document passed to the active execution runner."""
    if request.runner != "trading.backtest":
        config = execution_template_config_document(workspace, request.runner, request.template_id) or {}
        return {**config, **request.executor_config, "runner": request.runner}
    template_config = execution_template_config_document(workspace, request.runner, request.template_id)
    if template_config is not None:
        if not template_config.get("strategy"):
            raise HTTPException(status_code=400, detail="Execution template is missing a strategy section")
        if not template_config.get("simulation"):
            raise HTTPException(status_code=400, detail="Execution template is missing a simulation section")
        return template_config
    ensure_execution_defaults(workspace, request)
    strategy_id = request.strategy_id or workspace.project.active_strategy_id
    simulation_id = request.simulation_id or workspace.project.active_simulation_id
    strategy = workspace.project.strategies.get(strategy_id or "")
    simulation = workspace.project.simulations.get(simulation_id or "")
    if strategy is None:
        raise HTTPException(status_code=400, detail="Save a configuration template before executing")
    if simulation is None:
        raise HTTPException(status_code=400, detail="Save a runner config before executing")
    if getattr(strategy, "runner", request.runner) != request.runner:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Template '{strategy.name}' belongs to runner "
                f"'{getattr(strategy, 'runner', 'unknown')}', not '{request.runner}'"
            ),
        )

    return {
        "domain": "trading",
        "runner": request.runner,
        "template": {
            "id": strategy.id,
            "name": strategy.name,
            "type": request.runner,
        },
        "strategy": {
            "id": strategy.id,
            "name": strategy.name,
            "signals": [component_config(signal) for signal in strategy.signals],
            "orders": [component_config(order) for order in strategy.orders],
        },
        "simulation": component_config(simulation.simulation),
        "evaluation": component_config(simulation.evaluator) if simulation.evaluator else None,
    }


def run_backtest_executor(workspace: Workspace, dataset_id: str, name: str, attrs: Dict[str, Any], config: Optional[Dict[str, Any]] = None):
    """Run a trading backtest through the generic execution spec layer."""
    config = config or execution_config_document(
        workspace,
        StrategyRequest(
            dataset_id=dataset_id,
            runner="trading.backtest",
            strategy_id=workspace.project.active_strategy_id,
            simulation_id=workspace.project.active_simulation_id,
            template_id=workspace.project.active_execution_template_id,
        ),
    )
    spec = backtest_spec(
        dataset_id=dataset_id,
        name=name,
        attrs={
            **attrs,
            "runner": config["runner"],
            "strategy_id": workspace.project.active_strategy_id,
            "simulation_id": workspace.project.active_simulation_id,
        },
        config=config,
    )
    workspace.project.add_execution_spec(spec)
    runner = ExecutionSpecRunner({"trading.backtest": BacktestExecutor(store=workspace.store)})
    bundle = runner.run(spec)
    output_ids = [
        record.id
        for record in workspace.store.records()
        if record.attrs.get("execution_spec_id") == spec.id
    ]
    run = workspace.project.record_execution_run(
        ExecutionRun(
            spec_id=spec.id,
            runner=spec.runner,
            status="complete",
            input_ids=[binding.id for binding in spec.inputs],
            output_ids=output_ids,
            metrics=bundle.metrics,
            summary=bundle.summary,
            attrs=spec.attrs,
        )
    )
    bundle.run_id = run.id
    return bundle


def store_result_bundle(workspace: Workspace, spec, bundle) -> List[str]:
    """Persist ResultBundle artifacts that were not stored by the executor."""
    output_ids = []
    parent_ids = [binding.id for binding in spec.inputs]
    for artifact in bundle.artifacts:
        artifact_name = artifact.name or f"{spec.name}-{artifact.role}"
        record_id = workspace.store.add_child(
            artifact_name,
            artifact.data,
            parent_ids=parent_ids,
            kind=artifact.kind,
            attrs={
                **spec.attrs,
                **artifact.attrs,
                "execution_spec_id": spec.id,
                "runner": spec.runner,
            },
            transform=artifact.transform or {"name": spec.runner, "role": artifact.role},
        )
        output_ids.append(record_id)
    return output_ids


def instantiate_executor(workspace: Workspace, runner: str):
    """Create a registered executor with host-provided dependencies."""
    cls = executor_class(runner)
    try:
        return cls(store=workspace.store)
    except TypeError:
        try:
            return cls(workspace.store)
        except TypeError:
            return cls()


def default_execution_name(workspace: Workspace, dataset_id: str, runner: str) -> str:
    """Build a readable run name for a generic executor."""
    record = workspace.store.get_record(dataset_id)
    base = record.name if record is not None else dataset_id
    label = executor_metadata().get(runner, {}).get("label", runner)
    safe_label = str(label).replace(" ", "")
    return f"{base}-{safe_label}"


def run_registered_executor(
    workspace: Workspace,
    dataset_id: str,
    runner: str,
    name: Optional[str] = None,
    attrs: Optional[Dict[str, Any]] = None,
    config: Optional[Dict[str, Any]] = None,
):
    """Run any registered executor that follows the ResultBundle contract."""
    if runner not in executor_metadata():
        raise HTTPException(status_code=400, detail=f"Unsupported runner: {runner}")

    spec = ExecutionSpec(
        runner=runner,
        name=name or default_execution_name(workspace, dataset_id, runner),
        inputs=[spec_input(dataset_id, role="primary", name="dataframe")],
        attrs={**dict(attrs or {}), "runner": runner},
        config={**dict(config or {}), "runner": runner},
    )
    workspace.project.add_execution_spec(spec)
    bundle = ExecutionSpecRunner({runner: instantiate_executor(workspace, runner)}).run(spec)
    output_ids = store_result_bundle(workspace, spec, bundle)
    run = workspace.project.record_execution_run(
        ExecutionRun(
            spec_id=spec.id,
            runner=spec.runner,
            status="complete",
            input_ids=[binding.id for binding in spec.inputs],
            output_ids=output_ids,
            metrics=bundle.metrics,
            summary=bundle.summary,
            attrs=spec.attrs,
        )
    )
    bundle.run_id = run.id
    return bundle


def instantiate_evaluator(workspace: Workspace, evaluator: str):
    """Create a registered evaluator with host-provided dependencies."""
    cls = evaluator_class(evaluator)
    try:
        return cls(store=workspace.store)
    except TypeError:
        try:
            return cls(workspace.store)
        except TypeError:
            return cls()


def record_matches_contract(record, contract: Dict[str, Any]) -> bool:
    """Return whether a DataStore record satisfies an evaluator input contract."""
    expected_artifact = contract.get("artifact")
    if expected_artifact and record.attrs.get("artifact") != expected_artifact:
        return False
    required_columns = contract.get("required_columns") or []
    if any(column not in record.data.columns for column in required_columns):
        return False
    return True


def default_evaluation_inputs(workspace: Workspace, evaluator: str, run_id: Optional[str]) -> Dict[str, str]:
    """Auto-bind evaluator inputs from a selected execution run."""
    metadata = evaluator_metadata().get(evaluator)
    if metadata is None:
        raise HTTPException(status_code=400, detail=f"Unsupported evaluator: {evaluator}")
    input_contract = metadata.get("input_contract") or {}
    source_run_id = run_id or workspace.latest_run_id
    execution_run = workspace.project.execution_runs.get(source_run_id or "")
    candidate_ids = execution_run.output_ids if execution_run else [record.id for record in workspace.store.records()]
    candidates = [workspace.store.get_record(record_id) for record_id in candidate_ids]
    candidates = [record for record in candidates if record is not None]
    bindings: Dict[str, str] = {}
    for role, contract in input_contract.items():
        match = next((record for record in candidates if record_matches_contract(record, contract)), None)
        if match is None:
            raise HTTPException(
                status_code=400,
                detail=f"No artifact from the selected run satisfies evaluator input '{role}'",
            )
        bindings[role] = match.id
    return bindings


def store_evaluation_bundle(workspace: Workspace, spec: EvaluationSpec, bundle) -> List[str]:
    """Persist artifacts produced by an evaluator."""
    output_ids = []
    parent_ids = [binding.id for binding in spec.inputs]
    for artifact in bundle.artifacts:
        artifact_name = artifact.name or f"{spec.name}-{artifact.role}"
        record_id = workspace.store.add_child(
            artifact_name,
            artifact.data,
            parent_ids=parent_ids,
            kind=artifact.kind,
            attrs={
                **spec.attrs,
                **artifact.attrs,
                "evaluation_spec_id": spec.id,
                "evaluator": spec.evaluator,
                "source_run_id": spec.run_id,
            },
            transform=artifact.transform or {"name": spec.evaluator, "role": artifact.role},
        )
        output_ids.append(record_id)
    return output_ids


def run_evaluator(workspace: Workspace, request: EvaluationRunRequest):
    """Run a registered evaluator against selected/bound artifacts."""
    if request.evaluator not in evaluator_metadata():
        raise HTTPException(status_code=400, detail=f"Unsupported evaluator: {request.evaluator}")
    input_ids = dict(request.input_ids or {}) or default_evaluation_inputs(workspace, request.evaluator, request.run_id)
    bindings = [spec_input(artifact_id, role=role, name=role) for role, artifact_id in input_ids.items()]
    name = request.name or evaluator_metadata()[request.evaluator].get("label") or request.evaluator
    spec = EvaluationSpec(
        evaluator=request.evaluator,
        name=str(name),
        inputs=bindings,
        run_id=request.run_id or workspace.latest_run_id,
        config=dict(request.config or {}),
        attrs={"artifact_group": "evaluation", "evaluator": request.evaluator},
    )
    workspace.project.add_evaluation_spec(spec)
    evaluator_obj = instantiate_evaluator(workspace, request.evaluator)
    bundle = evaluator_obj.evaluate(CoreEvaluationRequest.from_spec(spec))
    output_ids = store_evaluation_bundle(workspace, spec, bundle)
    run = workspace.project.record_evaluation_run(
        EvaluationRun(
            spec_id=spec.id,
            evaluator=spec.evaluator,
            status="complete",
            source_run_id=spec.run_id,
            input_ids=[binding.id for binding in spec.inputs],
            output_ids=output_ids,
            metrics=bundle.metrics,
            summary=bundle.summary,
            attrs=spec.attrs,
        )
    )
    bundle.run_id = run.id
    return bundle


@app.post("/workspaces/{workspace_id}/strategies")
def add_strategy(workspace_id: str, request: StrategyDefinitionRequest) -> Dict[str, Any]:
    workspace = get_workspace(workspace_id)
    strategy = workspace.project.add_strategy(
        request.name,
        [signal.model_dump() for signal in request.signals],
        [order.model_dump() for order in request.orders],
        runner=request.runner,
    )
    return {"strategy": strategy, "workspace": workspace.project.summary(), "store": store_summary(workspace)}


@app.post("/workspaces/{workspace_id}/execution-templates")
def add_execution_template(workspace_id: str, request: ExecutionTemplateRequest) -> Dict[str, Any]:
    workspace = get_workspace(workspace_id)
    template = workspace.project.add_execution_template(
        name=request.name,
        runner=request.runner,
        sections=request.sections,
        config=request.config,
    )

    if request.runner == "trading.backtest":
        signals = request.sections.get("strategy.signals", [])
        orders = request.sections.get("strategy.orders", [])
        simulation = request.sections.get("simulation")
        evaluation = request.sections.get("evaluation")
        if signals or orders:
            workspace.project.add_strategy(
                request.name,
                [portable_component_config(item) for item in signals],
                [portable_component_config(item) for item in orders],
                runner=request.runner,
            )
        if simulation:
            workspace.project.add_simulation(
                request.name,
                portable_component_config(simulation),
                portable_component_config(evaluation) if evaluation else None,
            )

    return {"template": template, "workspace": workspace.project.summary(), "store": store_summary(workspace)}


@app.post("/workspaces/{workspace_id}/simulations")
def add_simulation(workspace_id: str, request: SimulationConfigRequest) -> Dict[str, Any]:
    workspace = get_workspace(workspace_id)
    simulation = workspace.project.add_simulation(
        request.name,
        request.simulation.model_dump(),
        request.evaluator.model_dump() if request.evaluator else None,
    )
    return {"simulation": simulation, "workspace": workspace.project.summary(), "store": store_summary(workspace)}


@app.post("/workspaces/{workspace_id}/backtest")
def run_backtest(workspace_id: str, request: StrategyRequest) -> Dict[str, Any]:
    """Compatibility endpoint for the trading backtest runner."""
    return run_execution(workspace_id, request)


@app.post("/workspaces/{workspace_id}/execute")
def run_execution(workspace_id: str, request: StrategyRequest) -> Dict[str, Any]:
    """Run the active execution runner against a dataset."""
    workspace = get_workspace(workspace_id)
    record = workspace.store.get_record(request.dataset_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Dataset not found")
    if request.runner != "trading.backtest":
        config = execution_config_document(workspace, request)
        result = run_registered_executor(
            workspace,
            dataset_id=record.id,
            runner=request.runner,
            attrs={"artifact_group": "manual_execution"},
            config=config,
        )
        workspace.latest_run_id = result.run_id
        return {
            "store": store_summary(workspace),
            "run_id": result.run_id,
            "metrics": result.metrics,
            "summary": result.summary,
        }
    ensure_execution_defaults(workspace, request)
    required_columns = required_strategy_columns(workspace, request)
    missing_columns = [column for column in required_columns if column not in record.data.columns]
    if missing_columns:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Execution dataset is missing column(s) required by the configured template: {', '.join(missing_columns)}. "
                f"Available columns: {', '.join(record.data.columns)}"
            ),
    )
    config = execution_config_document(workspace, request)
    result = run_backtest_executor(
        workspace,
        dataset_id=record.id,
        name=f"{record.name}-{config['simulation']['function']}",
        attrs={"artifact_group": "manual_execution"},
        config=config,
    )
    workspace.latest_run_id = result.run_id
    return {
        "store": store_summary(workspace),
        "run_id": result.run_id,
        "metrics": result.metrics,
        "signals": result.summary.get("signals", {}),
        "actions": result.summary.get("actions", {}),
    }


@app.post("/workspaces/{workspace_id}/evaluate")
def evaluate_run(workspace_id: str, request: EvaluationRunRequest) -> Dict[str, Any]:
    """Run a post-processing evaluator against execution artifacts."""
    workspace = get_workspace(workspace_id)
    result = run_evaluator(workspace, request)
    return {
        "store": store_summary(workspace),
        "evaluation_run_id": result.run_id,
        "metrics": result.metrics,
        "summary": result.summary,
    }


def _slice_range(df: pd.DataFrame, range_pair: List[int]) -> pd.DataFrame:
    start, end = int(range_pair[0]), int(range_pair[1])
    if end < 0:
        end = len(df) - 1
    start = max(start, 0)
    end = min(end, len(df) - 1)
    if end < start:
        return df.iloc[0:0].copy().reset_index(drop=True)
    return df.iloc[start : end + 1].copy().reset_index(drop=True)


@app.post("/workspaces/{workspace_id}/study/validate")
def run_validation(workspace_id: str, request: ValidationRequest) -> Dict[str, Any]:
    workspace = get_workspace(workspace_id)
    record = workspace.store.get_record(request.dataset_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Dataset not found")

    strategy_request = StrategyRequest(
        dataset_id=record.id,
        runner=request.runner,
        transform_set_id=request.transform_set_id,
        strategy_id=request.strategy_id,
        simulation_id=request.simulation_id,
    )
    ensure_execution_defaults(workspace, strategy_request)
    required_columns = required_strategy_columns(workspace, strategy_request)
    missing_columns = [column for column in required_columns if column not in record.data.columns]
    if missing_columns:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Validation dataset is missing column(s) required by the configured template: {', '.join(missing_columns)}. "
                f"Available columns: {', '.join(record.data.columns)}"
            ),
        )
    configure_pipeline(workspace, strategy_request)

    validation_class = COMPONENT_REGISTRY[request.validation.category][request.validation.function][request.validation.source]
    validation = validation_class(**request.validation.params)
    df = workspace.store.to_dataframe(record.id)
    if df is None:
        raise HTTPException(status_code=400, detail="Dataset could not be loaded")
    if "date" in df.columns:
        df = df.sort_values("date").reset_index(drop=True)

    run_id = str(uuid4())
    run_attrs = {
        "run_id": run_id,
        "artifact_group": "validation_backtest",
        "validation_method": request.validation.function,
    }
    ordered_id = workspace.store.add_child(
        f"{record.name}-ValidationOrdered",
        df,
        parent_ids=[record.id],
        kind="validation",
        attrs={**run_attrs, "artifact": "ordered_source"},
        transform={"name": "ValidationOrdered", "validation": request.validation.model_dump()},
    )

    folds = []
    for fold_index, (train_range, test_range) in enumerate(validation.execute(df)):
        train_df = _slice_range(df, train_range)
        test_df = _slice_range(df, test_range)
        if test_df.empty:
            continue

        fold_attrs = {**run_attrs, "fold": fold_index}
        train_id = workspace.store.add_child(
            f"{record.name}-Fold{fold_index}-Train",
            train_df,
            parent_ids=[ordered_id],
            kind="validation",
            attrs={**fold_attrs, "split": "train", "artifact": "source"},
        )
        test_id = workspace.store.add_child(
            f"{record.name}-Fold{fold_index}-Test",
            test_df,
            parent_ids=[ordered_id],
            kind="validation",
            attrs={**fold_attrs, "split": "test", "artifact": "source"},
        )
        train_result = run_backtest_executor(
            workspace,
            dataset_id=train_id,
            name=f"{record.name}-Fold{fold_index}-Train-ValidationBacktest",
            attrs={**fold_attrs, "split": "train", "phase": "fixed"},
        )
        test_result = run_backtest_executor(
            workspace,
            dataset_id=test_id,
            name=f"{record.name}-Fold{fold_index}-Test-ValidationBacktest",
            attrs={**fold_attrs, "split": "test", "phase": "fixed"},
        )
        folds.append(
            {
                "fold": fold_index,
                "train_range": train_range,
                "test_range": test_range,
                "train_rows": len(train_df),
                "test_rows": len(test_df),
                "train_record_id": train_id,
                "test_record_id": test_id,
                "train_metrics": train_result.metrics,
                "test_metrics": test_result.metrics,
                "metrics": test_result.metrics,
                "train_signals": train_result.summary.get("signals", {}),
                "test_signals": test_result.summary.get("signals", {}),
                "signals": test_result.summary.get("signals", {}),
                "train_actions": train_result.summary.get("actions", {}),
                "test_actions": test_result.summary.get("actions", {}),
                "actions": test_result.summary.get("actions", {}),
            }
        )

    if folds:
        workspace.store.add_child(
            f"{record.name}-ValidationSummary",
            pd.DataFrame(
                [
                    {
                        "fold": fold["fold"],
                        "train_rows": fold["train_rows"],
                        "test_rows": fold["test_rows"],
                        **{f"train_{key}": value for key, value in fold["train_metrics"].items()},
                        **{f"test_{key}": value for key, value in fold["test_metrics"].items()},
                    }
                    for fold in folds
                ]
            ),
            parent_ids=[ordered_id],
            kind="study",
            attrs={**run_attrs, "artifact": "validation_summary"},
            transform={"name": "ValidationSummary", "validation": request.validation.model_dump()},
        )

    workspace.latest_run_id = run_id
    return {"store": store_summary(workspace), "run_id": run_id, "folds": folds}


@app.post("/workspaces/{workspace_id}/study/optimize")
def run_optimization(workspace_id: str, request: OptimizeRequest) -> Dict[str, Any]:
    workspace = get_workspace(workspace_id)
    record = workspace.store.get_record(request.dataset_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Dataset not found")
    if workspace.simulation is None or workspace.strategy is None:
        configure_pipeline(
            workspace,
            StrategyRequest(
                dataset_id=record.id,
                runner=request.runner,
                transform_set_id=request.transform_set_id,
                strategy_id=request.strategy_id,
                simulation_id=request.simulation_id,
            ),
        )
    else:
        configure_pipeline(
            workspace,
            StrategyRequest(
                dataset_id=record.id,
                runner=request.runner,
                transform_set_id=request.transform_set_id,
                strategy_id=request.strategy_id,
                simulation_id=request.simulation_id,
            ),
        )

    optimization_source_record = record
    source_record, calculator_record, _ = calculator_context(workspace, record)
    operations = calculator_operations(calculator_record)
    recipe_calculator = calculator_from_operations(operations)
    if recipe_calculator.transforms:
        workspace.calculator = recipe_calculator
        if workspace.strategy is not None:
            workspace.strategy.calculator = recipe_calculator
        if workspace.simulation is not None and workspace.strategy is not None:
            workspace.simulation.strategy = workspace.strategy
        optimization_source_record = source_record

    study = Study(
        simulation=workspace.simulation,
        store=workspace.store,
        calculator=workspace.calculator,
        strategy=workspace.strategy,
    )
    study.project = workspace.project
    study.execution_config = execution_config_document(
        workspace,
        StrategyRequest(
            dataset_id=record.id,
            runner=request.runner,
            transform_set_id=request.transform_set_id,
            strategy_id=request.strategy_id,
            simulation_id=request.simulation_id,
        ),
    )
    for parameter in request.parameters:
        study.add_parameter(**parameter.model_dump())
    missing_transforms = [
        parameter.name
        for parameter in study.parameters
        if parameter.target.lower() in {"transform", "calculator"}
        and parameter.name not in study.calculator.transforms
    ]
    if missing_transforms:
        raise HTTPException(
            status_code=400,
            detail=(
                "Optimization transform(s) not found in the selected dataset recipe: "
                f"{', '.join(str(name) for name in missing_transforms)}. "
                f"Available transforms: {', '.join(study.calculator.transforms.keys()) or 'none'}"
            ),
        )
    constrain_optimization_parameters(study)
    validation_params = dict(request.validation.params)
    if "train_ratio" not in validation_params:
        validation_params["train_ratio"] = request.train_ratio
    study.add(request.validation.category, request.validation.function, request.validation.source, **validation_params)

    best_trial_params = dict(request.best_trial.params)
    if request.best_trial.function == "Distance from Ideal" and "weights" not in best_trial_params:
        best_trial_params["weights"] = [1.0] * len(request.objectives)
    study.add(request.best_trial.category, request.best_trial.function, request.best_trial.source, **best_trial_params)

    optimizer_params = {
        **request.optimizer.params,
        "trials": request.trials,
        "objectives": request.objectives,
        "storage": f"sqlite:////private/tmp/quantapy-optuna-{workspace.id}.sqlite3",
    }
    optimizer = study.add(
        request.optimizer.category,
        request.optimizer.function,
        request.optimizer.source,
        **optimizer_params,
    )
    results = optimizer.execute_validated(
        study=study,
        source_dataset=optimization_source_record.id,
        derived_name=request.derived_name or f"{record.name}-OptimizedIndicators",
    )
    if results:
        workspace.latest_run_id = results[-1]["run_id"]
        workspace.store.add_child(
            f"{record.name}-OptimizationSummary",
            pd.DataFrame(
                [
                    {
                        "fold": result["fold"],
                        **{
                            f"train_{key}": value
                            for key, value in result["train"]["metrics"].to_dict(orient="records")[0].items()
                        },
                        **{
                            f"test_{key}": value
                            for key, value in result["test"]["metrics"].to_dict(orient="records")[0].items()
                        },
                        **{f"param_{key}": value for key, value in result["best_trial"].params.items()},
                    }
                    for result in results
                ]
            ),
            parent_ids=[record.id],
            kind="study",
            attrs={
                "run_id": workspace.latest_run_id,
                "artifact": "optimization_summary",
                "artifact_group": "optimization",
            },
            transform={"name": "OptimizationSummary", "objectives": request.objectives},
        )
    return {
        "store": store_summary(workspace),
        "run_id": workspace.latest_run_id,
        "folds": [
            {
                "fold": result["fold"],
                "selected_params": result["best_trial"].params,
                "selected_values": result["best_trial"].values,
                "train_metrics": result["train"]["metrics"].to_dict(orient="records")[0],
                "test_metrics": result["test"]["metrics"].to_dict(orient="records")[0],
            }
            for result in results
        ],
    }
