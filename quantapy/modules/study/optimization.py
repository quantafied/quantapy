# app/ta_functions.py

import talib
from quantapy.core.base_study import BaseStudy
from quantapy.registry.component_registry import register_component
import pandas as pd
import numpy as np
from typing import List,Union,Type
import random
import optuna
import numpy as np
from uuid import uuid4
import copy
from quantapy.core.executions import ExecutionRun
from quantapy.core.optimization import ExecutorObjectiveRunner, ObjectiveSpec
from quantapy.core.runners import ExecutionSpecRunner
from quantapy.executors.trading import (
    BacktestExecutor,
    backtest_spec,
)
from quantapy.core.results import ResultArtifact
from quantapy.modules.evaluation.portfolio import PortfolioAnalytics
from quantapy.preparation import CalculatorInputPreparer

"""
json_schema_exra:

    advanced: Will display the parameter and any of its additional attributes 
    in an advanced dropdown container
"""

#class BayesianOptConfig(BaseComponentConfig):
#    """ Configuration schema for Bollinger Bands technical indicator"""
#    
#    objectives: List[str] = Field(
#        default_factory=list, 
#        json_schema_extra={"options": ["Maximize Profit",
#                                       "Minimize Profit",
#                                       "Maximize Sharpe Ratio", 
#                                       "Minimize Sharpe Ratio", 
#                                       "Maximize CAGR",
#                                       "Minimize CAGR"], 
#                           "widget_type": "multiselect"
#                           }
#    )
#    
#    trials: int = Field(
#        default = 25, 
#        description="Number of optimization trials", 
#        json_schema_extra={"advanced": False,
#                           }
#    )
    
@register_component(category="Optimization", function="Bayesian", source="Internal")
class bayesian(BaseStudy):
    """Bayesian optimizer"""
    
    config = {
      "title": "Bayesian Optimizer",
      "type": "object",
      "properties": {
        "trials": {
          "type": "integer",
          "default": 50,
          "description": "Number of optimization trials",
        },
        "objective_metric": {
          "type": "string",
          "default": "Profit",
          "description": "Metric column to optimize",
        },
        "direction": {
          "type": "string",
          "default": "maximize",
          "description": "Optimization direction",
          "enum": ["maximize", "minimize"],
        },
        "storage": {
          "type": "string",
          "default": "sqlite:///asimin.sqlite3",
          "description": "Optuna storage URL",
        },
        "objectives": {
        "type": "array",
        "title": "Objectives",
        "description": "Select objectives to maximize/minimize",
        "items": {
          "type": "string",
          "enum": ["Maximize Profit", "Minimize Profit", "Maximize Sharpe Ratio", "Minimize Sharpe Ratio"]
          },
          "uniqueItems": True,
          "default": ["close"]
          },
        }
      }

    def _parameter_label(self, parameter):
        """Return a stable Optuna parameter label."""
        parts = [parameter.target]
        parts.append(str(parameter.name if parameter.name is not None else parameter.index))
        parts.append(parameter.param)
        return ".".join(parts)

    def _suggest_parameter(self, trial, parameter):
        """Ask Optuna for a value matching an enabled study parameter."""
        label = self._parameter_label(parameter)

        if parameter.choices:
            return trial.suggest_categorical(label, parameter.choices)

        dtype = (parameter.dtype or "").lower()
        if dtype in {"integer", "int"}:
            return trial.suggest_int(label, int(parameter.low), int(parameter.high))

        return trial.suggest_float(label, float(parameter.low), float(parameter.high))

    def _objective_spec(self):
        """Return Optuna directions and metric names from optimizer params."""
        objectives = self.params.get("objectives")
        if objectives and objectives != ["close"]:
            directions = [objective.split()[0].lower() for objective in objectives]
            metrics = [" ".join(objective.split()[1:]) for objective in objectives]
        else:
            directions = [self.params["direction"]]
            metrics = [self.params["objective_metric"]]
        return directions, metrics

    def _score_metrics(self, metrics, metric_names, directions):
        """Extract objective values from a metrics DataFrame."""
        values = []
        for metric_name, direction in zip(metric_names, directions):
            value = metrics[metric_name].iloc[0]
            if pd.isna(value):
                value = -1e12 if direction == "maximize" else 1e12
            values.append(float(value))
        return values[0] if len(values) == 1 else tuple(values)

    def _failure_score(self, directions):
        """Return objective values that make a failed trial unattractive."""
        values = [-1e12 if direction == "maximize" else 1e12 for direction in directions]
        return values[0] if len(values) == 1 else tuple(values)

    def _objective_runner(self, study, metric_names, directions):
        """Build a generic executor-backed objective runner."""
        executor = (
            BacktestExecutor(store=study.store)
            if getattr(study, "execution_config", None)
            else BacktestExecutor(study.simulation)
        )
        return ExecutorObjectiveRunner(
            ExecutionSpecRunner({"trading.backtest": executor}),
            ObjectiveSpec(metric_names=list(metric_names), directions=list(directions)),
        )

    def _executor(self, study):
        """Return the executor adapter for the selected study execution mode."""
        return (
            BacktestExecutor(store=study.store)
            if getattr(study, "execution_config", None)
            else BacktestExecutor(study.simulation)
        )

    def _run_spec(self, study, spec):
        """Run and optionally record an execution spec launched by optimization."""
        project = getattr(study, "project", None)
        if project is not None:
            project.add_execution_spec(spec)
        bundle = ExecutionSpecRunner({"trading.backtest": self._executor(study)}).run(spec)
        if not bundle.metrics and bundle.artifact("events") is not None:
            self._attach_default_evaluation(study, spec, bundle)
        if project is not None:
            output_ids = [
                record.id
                for record in study.store.records()
                if record.attrs.get("execution_spec_id") == spec.id
            ]
            run = project.record_execution_run(
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

    def _attach_default_evaluation(self, study, spec, bundle):
        """Attach default portfolio evaluation artifacts for optimization scoring."""
        events = bundle.artifact("events")
        if events is None or not {"date", "portfolio_value"}.issubset(set(events.data.columns)):
            return
        outputs, metrics = PortfolioAnalytics(events.data[["date", "portfolio_value"]]).compute()
        bundle.metrics = metrics.to_dict(orient="records")[0]
        evaluation_artifacts = [
            ResultArtifact(
                role="portfolio_series",
                artifact_type="timeseries",
                kind="metrics",
                name=f"{spec.name}-Portfolio-Outputs",
                data=outputs,
                attrs={**spec.attrs, "artifact": "portfolio_outputs"},
                transform={"name": "trading.portfolio_metrics", "output": "timeseries"},
            ),
            ResultArtifact(
                role="metrics",
                artifact_type="scalar_map",
                kind="metrics",
                name=f"{spec.name}-Portfolio-Metrics",
                data=metrics,
                attrs={**spec.attrs, "artifact": "portfolio_metrics"},
                transform={"name": "trading.portfolio_metrics", "output": "summary"},
            ),
        ]
        bundle.artifacts.extend(evaluation_artifacts)
        if study.store is not None:
            parent_id = events.name or spec.primary_input_id
            for artifact in evaluation_artifacts:
                study.store.add_child(
                    artifact.name,
                    artifact.data,
                    parent_ids=[parent_id],
                    kind=artifact.kind,
                    attrs=artifact.attrs,
                    transform=artifact.transform,
                )

    def _input_preparer(self, study):
        """Build the input preparer for this optimizer bridge."""
        return CalculatorInputPreparer(study.store, study.calculator)

    def _apply_data_parameter(self, study, parameter, value):
        """Apply a trial value to upstream data-preparation config."""
        if parameter.target.lower() not in {"transform", "calculator"}:
            return
        if study.calculator is None:
            raise ValueError("Calculator is required to optimize transform parameters")
        if parameter.name not in study.calculator.transforms:
            raise ValueError(f"Transform '{parameter.name}' not found")
        study.calculator.transforms[parameter.name]["params"][parameter.param] = value

    def _trial_updates(self, trial, study):
        """Suggest all study parameters and patch data-prep config immediately."""
        updates = []
        for parameter in study.parameters:
            value = self._suggest_parameter(trial, parameter)
            self._apply_data_parameter(study, parameter, value)
            updates.append((parameter, value))
        return updates

    def _selected_updates(self, selected_trial, study):
        """Return selected trial values matched to study parameter objects."""
        updates = []
        for key, value in selected_trial.params.items():
            for parameter in study.parameters:
                if key == self._parameter_label(parameter):
                    self._apply_data_parameter(study, parameter, value)
                    updates.append((parameter, value))
        return updates

    def _execution_config(self, study, mode, updates=None, selected_params=None):
        """Return an executor config document patched with non-transform params."""
        config = copy.deepcopy(getattr(study, "execution_config", None) or {"domain": "trading"})
        config["mode"] = mode
        if selected_params:
            config["selected_params"] = dict(selected_params)
        for parameter, value in updates or []:
            self._apply_config_parameter(config, parameter, value)
        return config

    def _apply_config_parameter(self, config, parameter, value):
        """Apply a non-transform optimization parameter to an executor config."""
        target = parameter.target.lower()
        if target in {"transform", "calculator"}:
            return
        if target == "signal":
            component = self._select_config_component(config.get("strategy", {}).get("signals", []), parameter)
        elif target == "order":
            component = self._select_config_component(config.get("strategy", {}).get("orders", []), parameter)
        elif target == "simulation":
            component = config.get("simulation")
        elif target in {"evaluation", "evaluator"}:
            component = config.get("evaluation")
        else:
            raise ValueError(f"Unsupported optimization target '{parameter.target}'")
        if component is None:
            raise ValueError(f"No config component found for target '{parameter.target}'")
        component.setdefault("params", {})[parameter.param] = value

    def _select_config_component(self, components, parameter):
        """Select a config component by index or name."""
        if parameter.index is not None:
            return components[parameter.index]
        return next(
            (
                component
                for component in components
                if component.get("name") == parameter.name
                or component.get("params", {}).get("name") == parameter.name
                or component.get("function") == parameter.name
            ),
            None,
        )

    def _create_study(self, directions):
        """Create an Optuna study using configured storage."""
        storage = self.params["storage"]
        if len(directions) == 1:
            return optuna.create_study(direction=directions[0], storage=storage)
        return optuna.create_study(directions=directions, storage=storage)

    def _slice_range(self, df, index_range):
        """Return a reset-index slice from an inclusive validation range."""
        start, end = index_range
        end = len(df) - 1 if end == -1 else end
        return df.iloc[start:end + 1].reset_index(drop=True)

    def _range_end(self, df, index_range):
        """Return the inclusive end index for a validation range."""
        return len(df) - 1 if index_range[1] == -1 else index_range[1]

    def _select_trial(self, optuna_study, study, directions):
        """Select a single trial from an Optuna study."""
        if len(directions) == 1:
            return optuna_study.best_trial

        pareto_trials = optuna_study.best_trials
        pareto_solutions = [trial.values for trial in pareto_trials]
        if study.best_trial is None:
            return pareto_trials[0]

        _, optimal = study.best_trial.execute(
            pareto_solutions,
            objectives=directions,
        )
        return pareto_trials[optimal]

    def _apply_trial_params(self, selected_trial, study):
        """Apply selected trial parameters to the study pipeline."""
        self._selected_updates(selected_trial, study)

    def _run_objective(self, study, source_dataset, derived_name, metric_names, directions, attrs=None, updates=None):
        """Prepare trial input, run executor, and return objective values."""
        prepared = self._input_preparer(study).prepare(
            source_dataset,
            derived_name,
            attrs=attrs,
        )
        runner = self._objective_runner(study, metric_names, directions)
        spec = backtest_spec(
            prepared.input_id,
            name=f"{derived_name}-OptimizationBacktest",
            attrs={**(attrs or {}), "phase": "optimization"},
            config=self._execution_config(study, "objective", updates=updates),
        )
        if getattr(study, "project", None) is not None:
            bundle = self._run_spec(study, spec)
            score = runner.score(bundle.metrics)
        else:
            score, _ = runner.run(spec)
        return score

    def _run_selected(self, study, source_dataset, derived_name, backtest_name, selected_trial, attrs=None):
        """Apply selected params, prepare input, and run executor/evaluation."""
        updates = self._selected_updates(selected_trial, study)
        prepared = self._input_preparer(study).prepare(
            source_dataset,
            derived_name,
            attrs=attrs,
            selected_params=selected_trial.params,
        )
        bundle = self._run_spec(
            study,
            backtest_spec(
                    prepared.input_id,
                    name=backtest_name,
                    attrs={**(attrs or {}), "phase": "selected"},
                    config=self._execution_config(
                        study,
                        "selected",
                        updates=updates,
                        selected_params=selected_trial.params,
                    ),
                )
        )
        return (
            bundle.artifact("events").data if bundle.artifact("events") else None,
            bundle.artifact("portfolio_series").data if bundle.artifact("portfolio_series") else None,
            pd.DataFrame([bundle.metrics]) if bundle.metrics else None,
        )

    def execute_parameters(
        self,
        study,
        source_dataset: str,
        derived_name: str,
    ):
        """Optimize enabled Study parameters with Optuna."""
        if not study.parameters:
            raise ValueError("No optimization parameters enabled")
        if study.store is None or study.calculator is None or study.simulation is None:
            raise ValueError("Study requires store, calculator, and simulation")

        directions, metric_names = self._objective_spec()
        run_id = str(uuid4())
        run_attrs = {"run_id": run_id}

        def objective(trial):
            updates = self._trial_updates(trial, study)

            try:
                return self._run_objective(
                    study,
                    source_dataset,
                    f"{derived_name}-ObjectiveScratch",
                    metric_names,
                    directions,
                    attrs={**run_attrs, "split": "full"},
                    updates=updates,
                )
            except Exception:
                return self._failure_score(directions)

        optuna_study = self._create_study(directions)
        optuna_study.optimize(objective, n_trials=self.params["trials"])
        selected_trial = self._select_trial(optuna_study, study, directions)
        simulation_results, evaluator_outputs, metrics = self._run_selected(
            study,
            source_dataset,
            derived_name,
            f"{derived_name}-BestBacktest",
            selected_trial,
            attrs={**run_attrs, "split": "full"},
        )

        trials_df = optuna_study.trials_dataframe()
        study.store.add_child(
            f"{derived_name}-OptimizationTrials",
            trials_df,
            parent_ids=[derived_name],
            kind="study",
            attrs={**run_attrs, "artifact": "optimization_trials"},
            transform={
                "name": "Optuna",
                "objective_metrics": metric_names,
                "directions": directions,
            },
        )

        self.opt_study = optuna_study
        self.optimization_results = {
            "study": optuna_study,
            "run_id": run_id,
            "trials": trials_df,
            "best_trial": selected_trial,
            "simulation_results": simulation_results,
            "evaluator_outputs": evaluator_outputs,
            "metrics": metrics,
        }
        return self.optimization_results

    def execute_validated(
        self,
        study,
        source_dataset: str,
        derived_name: str,
    ):
        """Optimize on validation train folds and evaluate selected trials on test folds."""
        if study.validation is None:
            raise ValueError("Study requires a validation component")

        df = study.store.to_dataframe(source_dataset)
        if "date" in df.columns:
            df = df.sort_values("date").reset_index(drop=True)
        run_id = str(uuid4())
        run_attrs = {"run_id": run_id}
        sorted_source = f"{source_dataset}-ValidationOrdered"
        study.store.add_child(
            sorted_source,
            df,
            parent_ids=[source_dataset],
            kind="validation",
            attrs={**run_attrs, "artifact": "ordered_source"},
            transform={"name": "ValidationOrdered"},
        )

        directions, metric_names = self._objective_spec()
        fold_results = []

        for fold_index, (train_range, test_range) in enumerate(study.validation.execute(df)):
            train_df = self._slice_range(df, train_range)
            test_df = self._slice_range(df, test_range)

            train_source = f"{source_dataset}-Fold{fold_index}-Train"
            test_source = f"{source_dataset}-Fold{fold_index}-Test"
            train_derived = f"{derived_name}-Fold{fold_index}-Train"
            test_derived = f"{derived_name}-Fold{fold_index}-Test"

            fold_attrs = {**run_attrs, "fold": fold_index}
            study.store.add_child(
                train_source,
                train_df,
                parent_ids=[source_dataset],
                kind="validation",
                attrs={**fold_attrs, "split": "train", "artifact": "source"},
            )
            study.store.add_child(
                test_source,
                test_df,
                parent_ids=[source_dataset],
                kind="validation",
                attrs={**fold_attrs, "split": "test", "artifact": "source"},
            )

            def objective(trial):
                updates = self._trial_updates(trial, study)
                try:
                    return self._run_objective(
                        study,
                        train_source,
                        f"{train_derived}-ObjectiveScratch",
                        metric_names,
                        directions,
                        attrs={**fold_attrs, "split": "train"},
                        updates=updates,
                    )
                except Exception:
                    return self._failure_score(directions)

            optuna_study = self._create_study(directions)
            optuna_study.optimize(objective, n_trials=self.params["trials"])
            selected_trial = self._select_trial(optuna_study, study, directions)

            train_results = self._run_selected(
                study,
                train_source,
                train_derived,
                f"{train_derived}-SelectedBacktest",
                selected_trial,
                attrs={**fold_attrs, "split": "train"},
            )

            updates = self._selected_updates(selected_trial, study)
            test_end = self._range_end(df, test_range)
            context_source = f"{source_dataset}-Fold{fold_index}-TestContext"
            context_df = df.iloc[:test_end + 1].reset_index(drop=True)
            study.store.add_child(
                context_source,
                context_df,
                parent_ids=[sorted_source],
                kind="validation",
                attrs={**fold_attrs, "split": "test", "artifact": "context_source"},
            )
            full_indicators = study.calculator.derive_combined(study.store, context_source)
            if hasattr(full_indicators, "to_dataframe"):
                full_indicators = full_indicators.to_dataframe()
            context_start = max(test_range[0] - 1, 0)
            test_indicators = full_indicators.iloc[context_start:test_end + 1].reset_index(drop=True)
            prepared_test = self._input_preparer(study).prepare_from_dataframe(
                context_source,
                test_derived,
                test_indicators,
                parent_ids=[context_source, test_source],
                attrs={**fold_attrs, "split": "test"},
                selected_params=selected_trial.params,
                transform_metadata={
                    "context_start": context_start,
                    "test_start": test_range[0],
                },
            )
            test_bundle = self._run_spec(
                study,
                backtest_spec(
                    prepared_test.input_id,
                    name=f"{test_derived}-SelectedBacktest",
                    attrs={**fold_attrs, "split": "test", "phase": "selected"},
                    config=self._execution_config(
                        study,
                        "selected",
                        updates=updates,
                        selected_params=selected_trial.params,
                    ),
                )
            )
            test_results = (
                test_bundle.artifact("events").data if test_bundle.artifact("events") else None,
                test_bundle.artifact("portfolio_series").data if test_bundle.artifact("portfolio_series") else None,
                pd.DataFrame([test_bundle.metrics]) if test_bundle.metrics else None,
            )

            trials_df = optuna_study.trials_dataframe()
            study.store.add_child(
                f"{derived_name}-Fold{fold_index}-OptimizationTrials",
                trials_df,
                parent_ids=[train_derived],
                kind="study",
                attrs={**fold_attrs, "artifact": "optimization_trials"},
                transform={
                    "name": "Optuna",
                    "objective_metrics": metric_names,
                    "directions": directions,
                    "selected_params": selected_trial.params,
                },
            )
            study.store.add_child(
                f"{derived_name}-Fold{fold_index}-SelectedTrial",
                pd.DataFrame([{
                    "number": selected_trial.number,
                    "values": selected_trial.values,
                    **selected_trial.params,
                }]),
                parent_ids=[train_derived],
                kind="study",
                attrs={**fold_attrs, "artifact": "selected_trial"},
                transform={"name": "BestTrial", "directions": directions},
            )

            fold_results.append({
                "fold": fold_index,
                "run_id": run_id,
                "study": optuna_study,
                "trials": trials_df,
                "best_trial": selected_trial,
                "train": {
                    "simulation_results": train_results[0],
                    "evaluator_outputs": train_results[1],
                    "metrics": train_results[2],
                },
                "test": {
                    "simulation_results": test_results[0],
                    "evaluator_outputs": test_results[1],
                    "metrics": test_results[2],
                },
            })

        self.validation_results = fold_results
        return fold_results
    
    def objective(self,trial):
        """Optuna objective that updates optimizable strategy parameters."""
        
        print(f"TRIAL: {trial}")
        
        self.get_optimizable()
        
        # Original
        #for optimizable in self.optimizable_functions:
        #    for parameter,bounds in self.simulation.strategy.calculator.transforms[optimizable].params["optimizable"].items():
        #        parameter = list(self.simulation.strategy.calculator.transforms[optimizable].params["optimizable"].keys())[0]
        #        bounds = [self.simulation.strategy.calculator.transforms[optimizable].params["optimizable"][f"{parameter}_min"],self.simulation.strategy.calculator.transforms[optimizable].params["optimizable"][f"{parameter}_max"]]
        #        suggestion = trial.suggest_int(f"{optimizable}_{parameter}", bounds[0], bounds[1])
        #        #suggestion = 27
        #        # update config # may want to do this and make the class/function callable from the instance config
        #        setattr(self.simulation.strategy.calculator.transforms[optimizable].config, parameter, suggestion)
        #    # update transformation
        #    self.simulation.strategy.calculator.update(**self.simulation.strategy.calculator.transforms[optimizable].config.model_dump())
        #self.simulation.strategy.calculator.apply_transformations()
        
        for optimizable in self.optimizable_functions:

            parameter = list(self.simulation.strategy.calculator.transforms[optimizable].params["optimizable"].keys())[0]
            bounds = [self.simulation.strategy.calculator.transforms[optimizable].params["optimizable"][f"{parameter}_min"],self.simulation.strategy.calculator.transforms[optimizable].params["optimizable"][f"{parameter}_max"]]
            suggestion = trial.suggest_int(f"{optimizable}_{parameter}", bounds[0], bounds[1])
            #suggestion = 27
            # update config # may want to do this and make the class/function callable from the instance config
            print(optimizable,parameter,suggestion)
            self.simulation.strategy.calculator.transforms[optimizable].params[parameter]=suggestion
            # update transformation
            #self.simulation.strategy.calculator.update(**self.simulation.strategy.calculator.transforms[optimizable].params)
        self.simulation.strategy.calculator.apply_transformations()
        
        for optimizable in self.optimizable_conditions:
            for parameter,bounds in self.simulation.strategy.strategy_conditions[optimizable].config.optimizable.items():
                suggestion = trial.suggest_int(f"{optimizable}_{parameter}", bounds[0], bounds[1])
                setattr(self.simulation.strategy.strategy_conditions[optimizable].config, parameter, suggestion)
            # update transformation
            self.simulation.strategy.update_condition(optimizable,**self.simulation.strategy.strategy_conditions[optimizable].config.model_dump())
        #self.simulation.strategy.calculator.apply_transformations()
        
        simulation_results, evaluator_results, metrics = self.simulation.execute()
        print("5555555555555555555")
        print(type(metrics))
        
        objective_list = []
        for obj in self._objectives:
            objective_list.append(metrics[obj])
            
        return tuple(objective_list)
    
    
    def execute(
        self, 
        objectives: list[str] = ["Maximize Profit"], 
        trials: int = 25,
        ):
        """Run the configured Bayesian optimization study."""
        
        trials = self.params["trials"]
        self.objectives = self.params["objectives"]
        self._objectives = []
                
        directions = []
        
        for objective in self.objectives:
            directions.append(objective.split()[0].lower())
            self._objectives.append(" ".join(objective.split()[1:]))
        
        file_path = "./optuna_journal_storage.log"
        storage = optuna.storages.JournalStorage(optuna.storages.journal.JournalFileBackend(file_path))
        
        sampler_algo = optuna.samplers.TPESampler()
        
        study = optuna.create_study(
            #study_name=,
            storage=f"sqlite:///asimin.sqlite3",#storage, #f"sqlite:///asimin.sqlite3",
            directions=directions,
            sampler=sampler_algo
        )

        study.optimize(self.objective, n_trials=trials)
        
        self.opt_study = study
        
        return study
    
    def run_trial(self,trial):
        """Replay one Optuna trial and return simulation/evaluation outputs."""
        
        print(f"TRIAL: {trial}")
        
        self.get_optimizable()
        
        for optimizable in self.optimizable_functions:

            parameter = list(self.simulation.strategy.calculator.transforms[optimizable].params["optimizable"].keys())[0]
            bounds = [self.simulation.strategy.calculator.transforms[optimizable].params["optimizable"][f"{parameter}_min"],self.simulation.strategy.calculator.transforms[optimizable].params["optimizable"][f"{parameter}_max"]]
            suggestion = trial.suggest_int(f"{optimizable}_{parameter}", bounds[0], bounds[1])
            #suggestion = 27
            # update config # may want to do this and make the class/function callable from the instance config
            print(optimizable,parameter,suggestion)
            self.simulation.strategy.calculator.transforms[optimizable].params[parameter]=suggestion
            # update transformation
            #self.simulation.strategy.calculator.update(**self.simulation.strategy.calculator.transforms[optimizable].params)
        self.simulation.strategy.calculator.apply_transformations()
        
        simulation_results, evaluator_results, metrics = self.simulation.execute()
        print("5555555555555555555")
        print(type(metrics))
        
        objective_list = []
        for obj in self._objectives:
            objective_list.append(metrics[obj])
            
        return simulation_results, evaluator_results, metrics

#class WrightedDistanceConfig(BaseComponentConfig):
#    """ Configuration schema for Bollinger Bands technical indicator"""
#    
#    "My Schema Here"
    
@register_component(category="Optimization", function="Weighted Distance to Ideal", source="Internal")
def weighted_euclidean_distance_to_ideal_test(study_obj, weights):
    """
    Compute weighted Euclidean distance of each solution to the ideal solution.
    
    Parameters:
    - pareto_solutions (np.array): 2D array (rows: solutions, columns: objectives).
    - objectives (list): List of 'max' or 'min' indicating the type of each objective.
    - weights (list): List of weights corresponding to each objective (must sum to 1 or be relative).

    Returns:
    - distances (np.array): Weighted Euclidean distances for each solution.
    """
    
    objectives = [direction.name.lower() for direction in study_obj.in_sample_studies[0].directions]
    
    studies = study_obj.in_sample_studies
    
    optimals = []
    
    for i,study in enumerate(studies):
        
        if len(objectives) > 1:
        
            print("Inspecting")
            
            pareto_solutions = []
            for trial in study.best_trials:
                pareto_solutions.append(trial.values)
    
            if len(pareto_solutions) < 1:
                print("Pareto Set Empty")
                continue
    
            unique_data = []
            seen = set()
            
            for item in pareto_solutions:
                t = tuple(item)
                if t not in seen:
                    seen.add(t)
                    unique_data.append(item) # get unique
            
            print(pareto_solutions)
            pareto_solutions = np.array(unique_data)
            print(pareto_solutions)
            # sometime returns same objective value so we take the first by using unique
            weights = np.array(weights) / np.sum(weights)  # Normalize weights to sum to 1
        
            if len(pareto_solutions) > 1:
            # Step 1: Normalize objectives
                norm_solutions = np.zeros_like(pareto_solutions, dtype=float)
                
                for j, obj_type in enumerate(objectives):
                    col = pareto_solutions[:, j]
                    if obj_type == 'maximize':
                        norm_solutions[:, j] = (col - np.min(col)) / (np.max(col) - np.min(col))
                    elif obj_type == 'minimize':
                        norm_solutions[:, j] = (np.max(col) - col) / (np.max(col) - np.min(col))
                    else:
                        raise ValueError(f"Invalid objective type: {obj_type}. Use 'max' or 'min'.")
            
                # Step 2: Define the ideal solution
                ideal_solution = np.max(norm_solutions, axis=0)
            
                # Step 3: Compute Weighted Euclidean Distance
                squared_diff = (norm_solutions - ideal_solution) ** 2
                weighted_diff = squared_diff * weights  # Apply weights element-wise
                distances = np.sqrt(np.sum(weighted_diff, axis=1))
                
                optimal = np.argmin(distances)
                
            elif len(pareto_solutions) == 1:
                distances = [1.0]
                optimal = 0
                
            optimals.append(optimal)
            
        else:
            
            optimals.append(0)
            
    return optimals
    
