"""Build the CP-SAT cargo loading model from packages and an experiment config."""

from dataclasses import dataclass

from ortools.sat.python import cp_model

from cargo_optimizer.config import ExperimentConfig
from cargo_optimizer.data import Package


@dataclass
class CargoModel:
    model: cp_model.CpModel
    load: dict[str, cp_model.IntVar]  # x_i: 1 if the package is loaded, keyed by package_id


def build_model(packages: list[Package], config: ExperimentConfig) -> CargoModel:
    """Create the decision variables, constraints and objective for one experiment."""
    model = cp_model.CpModel()
    load = {package.package_id: model.new_bool_var(f"load_{package.package_id}") for package in packages}

    _add_capacity(model, packages, load, config.capacity)
    _maximize_value(model, packages, load)

    return CargoModel(model=model, load=load)


def _add_capacity(model: cp_model.CpModel, packages: list[Package], load: dict[str, cp_model.IntVar], capacity: int) -> None:
    """Total loaded weight must not exceed the truck capacity: sum(w_i * x_i) <= C."""
    model.add(sum(package.weight_kg * load[package.package_id] for package in packages) <= capacity)


def _maximize_value(model: cp_model.CpModel, packages: list[Package], load: dict[str, cp_model.IntVar]) -> None:
    """Objective: maximize the total value of loaded packages, max sum(v_i * x_i)."""
    model.maximize(sum(package.value * load[package.package_id] for package in packages))
