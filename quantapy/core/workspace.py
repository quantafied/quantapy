"""Workspace-level model for organizing research components.

DataStore remains the artifact ledger. WorkspaceStore owns the product-level
objects a GUI needs to navigate: transform sets, strategies, simulations, and
study configs.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional
from uuid import uuid4

from quantapy.core.evaluations import EvaluationRun, EvaluationSpec
from quantapy.core.executions import ExecutionRun, ExecutionSpec
from quantapy.core.timeseries import DataStore
from quantapy.orchestrator.calculator import Calculator
from quantapy.orchestrator.simulate import Simulate
from quantapy.orchestrator.strategy import Strategy


@dataclass
class ComponentSpec:
    """Registered component plus user-selected parameters."""

    id: str
    category: str
    function: str
    source: str = "Internal"
    name: Optional[str] = None
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TransformSet:
    """Named collection of transform components."""

    id: str
    name: str
    transforms: List[ComponentSpec] = field(default_factory=list)


@dataclass
class StrategyDefinition:
    """Named collection of signal and order components."""

    id: str
    name: str
    runner: str = "trading.backtest"
    signals: List[ComponentSpec] = field(default_factory=list)
    orders: List[ComponentSpec] = field(default_factory=list)


@dataclass
class SimulationConfig:
    """Simulation component and optional evaluator component."""

    id: str
    name: str
    simulation: ComponentSpec
    evaluator: Optional[ComponentSpec] = None


@dataclass
class ExecutionTemplate:
    """Runner-specific config template assembled from registered components."""

    id: str
    name: str
    runner: str
    sections: Dict[str, Any] = field(default_factory=dict)
    config: Dict[str, Any] = field(default_factory=dict)


class WorkspaceStore:
    """High-level workspace model backed by a DataStore."""

    def __init__(self, store: Optional[DataStore] = None):
        self.store = store or DataStore()
        self.transform_sets: Dict[str, TransformSet] = {}
        self.strategies: Dict[str, StrategyDefinition] = {}
        self.simulations: Dict[str, SimulationConfig] = {}
        self.execution_templates: Dict[str, ExecutionTemplate] = {}
        self.execution_specs: Dict[str, ExecutionSpec] = {}
        self.execution_runs: Dict[str, ExecutionRun] = {}
        self.evaluation_specs: Dict[str, EvaluationSpec] = {}
        self.evaluation_runs: Dict[str, EvaluationRun] = {}
        self.active_transform_set_id: Optional[str] = None
        self.active_strategy_id: Optional[str] = None
        self.active_simulation_id: Optional[str] = None
        self.active_execution_template_id: Optional[str] = None

    def add_transform_set(self, name: str = "Default Transforms") -> TransformSet:
        """Create and activate a transform set."""
        transform_set = TransformSet(id=str(uuid4()), name=name)
        self.transform_sets[transform_set.id] = transform_set
        self.active_transform_set_id = transform_set.id
        return transform_set

    def ensure_transform_set(self) -> TransformSet:
        """Return the active transform set, creating a default if needed."""
        if self.active_transform_set_id in self.transform_sets:
            return self.transform_sets[self.active_transform_set_id]
        return self.add_transform_set()

    def add_transform(
        self,
        category: str,
        function: str,
        source: str = "Internal",
        name: Optional[str] = None,
        params: Optional[Dict[str, Any]] = None,
        transform_set_id: Optional[str] = None,
    ) -> ComponentSpec:
        """Add a transform component to a transform set."""
        transform_set = (
            self.transform_sets[transform_set_id]
            if transform_set_id
            else self.ensure_transform_set()
        )
        spec = ComponentSpec(
            id=str(uuid4()),
            category=category,
            function=function,
            source=source,
            name=name or function,
            params=params or {},
        )
        transform_set.transforms.append(spec)
        return spec

    def calculator(self, transform_set_id: Optional[str] = None) -> Calculator:
        """Build a Calculator from a transform set."""
        transform_set = self.transform_sets.get(transform_set_id or self.active_transform_set_id)
        if transform_set is None:
            raise ValueError("No transform set configured")
        calculator = Calculator()
        for spec in transform_set.transforms:
            calculator.add_transform(
                spec.category,
                spec.function,
                spec.source,
                name=spec.name,
                **spec.params,
            )
        return calculator

    def add_strategy(
        self,
        name: str,
        signals: List[Dict[str, Any]],
        orders: List[Dict[str, Any]],
        runner: str = "trading.backtest",
    ) -> StrategyDefinition:
        """Create and activate a strategy definition."""
        strategy = StrategyDefinition(
            id=str(uuid4()),
            name=name,
            runner=runner,
            signals=[ComponentSpec(id=str(uuid4()), **spec) for spec in signals],
            orders=[ComponentSpec(id=str(uuid4()), **spec) for spec in orders],
        )
        self.strategies[strategy.id] = strategy
        self.active_strategy_id = strategy.id
        return strategy

    def strategy(
        self,
        calculator: Calculator,
        strategy_id: Optional[str] = None,
    ) -> Strategy:
        """Build a Strategy from a strategy definition."""
        definition = self.strategies.get(strategy_id or self.active_strategy_id)
        if definition is None:
            raise ValueError("No strategy configured")
        strategy = Strategy(calculator, store=self.store)
        for spec in definition.signals:
            strategy.add(spec.category, spec.function, spec.source, **spec.params)
        for spec in definition.orders:
            strategy.add(spec.category, spec.function, spec.source, **spec.params)
        return strategy

    def add_simulation(
        self,
        name: str,
        simulation: Dict[str, Any],
        evaluator: Optional[Dict[str, Any]] = None,
    ) -> SimulationConfig:
        """Create and activate a simulation configuration."""
        config = SimulationConfig(
            id=str(uuid4()),
            name=name,
            simulation=ComponentSpec(id=str(uuid4()), **simulation),
            evaluator=ComponentSpec(id=str(uuid4()), **evaluator) if evaluator else None,
        )
        self.simulations[config.id] = config
        self.active_simulation_id = config.id
        return config

    def add_execution_template(
        self,
        name: str,
        runner: str,
        sections: Optional[Dict[str, Any]] = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> ExecutionTemplate:
        """Create and activate a generic execution template."""
        template = ExecutionTemplate(
            id=str(uuid4()),
            name=name,
            runner=runner,
            sections=sections or {},
            config=config or {},
        )
        self.execution_templates[template.id] = template
        self.active_execution_template_id = template.id
        return template

    def simulation(
        self,
        strategy: Strategy,
        simulation_id: Optional[str] = None,
    ) -> Simulate:
        """Build a Simulate orchestrator from a simulation config."""
        config = self.simulations.get(simulation_id or self.active_simulation_id)
        if config is None:
            raise ValueError("No simulation configured")
        simulation = Simulate(strategy=strategy, store=self.store)
        spec = config.simulation
        simulation.add(spec.category, spec.function, spec.source, **spec.params)
        if config.evaluator is not None:
            evaluator = config.evaluator
            simulation.add_evaluator(evaluator.category, evaluator.function, evaluator.source, **evaluator.params)
        return simulation

    def add_execution_spec(self, spec: ExecutionSpec) -> ExecutionSpec:
        """Store a portable execution spec."""
        self.execution_specs[spec.id] = spec
        return spec

    def record_execution_run(self, run: ExecutionRun) -> ExecutionRun:
        """Store an observed execution run."""
        self.execution_runs[run.id] = run
        return run

    def add_evaluation_spec(self, spec: EvaluationSpec) -> EvaluationSpec:
        """Store a portable evaluation spec."""
        self.evaluation_specs[spec.id] = spec
        return spec

    def record_evaluation_run(self, run: EvaluationRun) -> EvaluationRun:
        """Store an observed evaluation run."""
        self.evaluation_runs[run.id] = run
        return run

    def execution_summary(self) -> Dict[str, Any]:
        """Return execution specs and runs for orchestration UIs."""
        return {
            "specs": [spec.to_dict() for spec in self.execution_specs.values()],
            "runs": [run.to_dict() for run in self.execution_runs.values()],
        }

    def evaluation_summary(self) -> Dict[str, Any]:
        """Return evaluation specs and runs for orchestration UIs."""
        return {
            "specs": [spec.to_dict() for spec in self.evaluation_specs.values()],
            "runs": [run.to_dict() for run in self.evaluation_runs.values()],
        }

    def summary(self) -> Dict[str, Any]:
        """Return a GUI-friendly workspace model."""
        return {
            "data": self.store.navigation(),
            "transforms": [asdict(item) for item in self.transform_sets.values()],
            "strategies": [asdict(item) for item in self.strategies.values()],
            "simulations": [asdict(item) for item in self.simulations.values()],
            "templates": [asdict(item) for item in self.execution_templates.values()],
            "executions": self.execution_summary(),
            "evaluations": self.evaluation_summary(),
            "studies": self.store.study_runs(),
            "active": {
                "transform_set_id": self.active_transform_set_id,
                "strategy_id": self.active_strategy_id,
                "simulation_id": self.active_simulation_id,
                "execution_template_id": self.active_execution_template_id,
            },
        }
