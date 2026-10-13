"""Build the CP-SAT cargo loading model from packages and an experiment config."""

from dataclasses import dataclass

from ortools.sat.python import cp_model

from cargo_optimizer.config import ExperimentConfig, ShouldInclude
from cargo_optimizer.data import Package


@dataclass
class CargoModel:
    model: cp_model.CpModel
    load: dict[str, cp_model.IntVar]  # x_i: 1 if the package is loaded, keyed by package_id
    rules: dict[str, bool]            # every rule the model knows, and whether this config enabled it


def build_model(packages: list[Package], config: ExperimentConfig) -> CargoModel:
    """Create the decision variables, constraints and objective for one experiment."""
    model = cp_model.CpModel()
    load = {package.package_id: model.new_bool_var(f"load_{package.package_id}") for package in packages}

    rules = {
        "capacity": True,
        "must_include": config.should_include == ShouldInclude.HARD,
    }

    _add_capacity(model, packages, load, config.capacity)
    if rules["must_include"]:
        _add_must_include(model, packages, load)
    _maximize_value(model, packages, load)

    return CargoModel(model=model, load=load, rules=rules)


def _add_capacity(
    model: cp_model.CpModel, packages: list[Package], load: dict[str, cp_model.IntVar], capacity: int
) -> None:
    """Total loaded weight must not exceed the truck capacity: sum(w_i * x_i) <= C."""
    total_weight = sum(package.weight_kg * load[package.package_id] for package in packages)
    model.add(total_weight <= capacity).with_name("capacity")


def _add_must_include(model: cp_model.CpModel, packages: list[Package], load: dict[str, cp_model.IntVar]) -> None:
    """Every should_included package must be loaded: x_i = 1 for all i in S."""
    for package in packages:
        if package.should_included:
            model.add(load[package.package_id] == 1).with_name(f"must_include_{package.package_id}")


def _maximize_value(model: cp_model.CpModel, packages: list[Package], load: dict[str, cp_model.IntVar]) -> None:
    """Objective: maximize the total value of loaded packages, max sum(v_i * x_i)."""
    model.maximize(sum(package.value * load[package.package_id] for package in packages))
