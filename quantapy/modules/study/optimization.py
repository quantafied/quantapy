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
        for key, value in selected_trial.params.items():
            for parameter in study.parameters:
                if key == self._parameter_label(parameter):
                    study._apply_parameter(parameter, value)

    def _run_objective(self, study, source_dataset, derived_name, metric_names, directions, attrs=None):
        """Derive indicators, run simulation, and return objective values."""
        indicators = study.calculator.derive_combined(study.store, source_dataset)
        study.store.add_child(
            derived_name,
            indicators,
            parent_ids=[source_dataset],
            kind="derived",
            attrs={**(attrs or {}), "artifact": "indicators"},
            transform={
                "name": "OptimizedIndicators",
                "transforms": study.calculator.list_transforms(),
            },
        )

        _, _, metrics = study.simulation.execute(
            dataset_name=derived_name,
            name=f"{derived_name}-OptimizationBacktest",
            attrs={**(attrs or {}), "phase": "optimization"},
        )
        return self._score_metrics(metrics, metric_names, directions)

    def _run_selected(self, study, source_dataset, derived_name, backtest_name, selected_trial, attrs=None):
        """Apply selected params, derive indicators, and run simulation/evaluation."""
        self._apply_trial_params(selected_trial, study)
        indicators = study.calculator.derive_combined(study.store, source_dataset)
        study.store.add_child(
            derived_name,
            indicators,
            parent_ids=[source_dataset],
            kind="derived",
            attrs={**(attrs or {}), "artifact": "indicators"},
            transform={
                "name": "OptimizedIndicators",
                "transforms": study.calculator.list_transforms(),
                "selected_params": selected_trial.params,
            },
        )
        return study.simulation.execute(
            dataset_name=derived_name,
            name=backtest_name,
            attrs={**(attrs or {}), "phase": "selected"},
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
            for parameter in study.parameters:
                value = self._suggest_parameter(trial, parameter)
                study._apply_parameter(parameter, value)

            return self._run_objective(
                study,
                source_dataset,
                derived_name,
                metric_names,
                directions,
                attrs={**run_attrs, "split": "full"},
            )

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
                for parameter in study.parameters:
                    value = self._suggest_parameter(trial, parameter)
                    study._apply_parameter(parameter, value)
                return self._run_objective(
                    study,
                    train_source,
                    train_derived,
                    metric_names,
                    directions,
                    attrs={**fold_attrs, "split": "train"},
                )

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

            self._apply_trial_params(selected_trial, study)
            full_indicators = study.calculator.derive_combined(study.store, sorted_source)
            if hasattr(full_indicators, "to_dataframe"):
                full_indicators = full_indicators.to_dataframe()
            context_start = max(test_range[0] - 1, 0)
            test_end = self._range_end(df, test_range)
            test_indicators = full_indicators.iloc[context_start:test_end + 1].reset_index(drop=True)
            study.store.add_child(
                test_derived,
                test_indicators,
                parent_ids=[sorted_source, test_source],
                kind="derived",
                attrs={**fold_attrs, "split": "test", "artifact": "indicators"},
                transform={
                    "name": "OptimizedIndicators",
                    "transforms": study.calculator.list_transforms(),
                    "selected_params": selected_trial.params,
                    "context_start": context_start,
                    "test_start": test_range[0],
                },
            )
            test_results = study.simulation.execute(
                dataset_name=test_derived,
                name=f"{test_derived}-SelectedBacktest",
                attrs={**fold_attrs, "split": "test", "phase": "selected"},
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
    
