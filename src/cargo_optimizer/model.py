"""Build the CP-SAT cargo loading model from packages and an experiment config."""

from dataclasses import dataclass

from ortools.sat.python import cp_model

from cargo_optimizer.config import CategoryRule, DatasetConfig, ExperimentConfig, ShouldInclude
from cargo_optimizer.data import Package

PRIORITY_POINTS = {"Critical": 3, "High": 2, "Normal": 1, "Low": 0}


def package_score(package: Package, priority_weight: int) -> int:
    """Objective contribution of a loaded package: v_i + w * p_i."""
    return package.value + priority_weight * PRIORITY_POINTS[package.priority]


def rule_violation(selected: list[Package], rule: CategoryRule) -> int:
    """Packages beyond a category rule's bound: missing for at_least, extra for at_most; 0 when it holds."""
    loaded = sum(package.category == rule.category for package in selected)
    return max(0, rule.count - loaded) if rule.direction == "at_least" else max(0, loaded - rule.count)


def objective_value(selected: list[Package], config: ExperimentConfig) -> int:
    """The objective of a selection: total score minus the penalties of its soft rule violations."""
    total_score = sum(package_score(package, config.priority_weight) for package in selected)
    penalties = sum(rule.penalty * rule_violation(selected, rule) for rule in config.category_rules if rule.is_soft)
    return total_score - penalties


@dataclass
class CargoModel:
    model: cp_model.CpModel
    load: dict[str, cp_model.IntVar]  # x_i: 1 if the package is loaded, keyed by package_id
    rules: dict[str, bool]            # every rule the model knows, and whether this config enabled it


def build_model(packages: list[Package], config: ExperimentConfig, dataset: DatasetConfig) -> CargoModel:
    """Create the decision variables, constraints and objective for one experiment."""
    model = cp_model.CpModel()
    load = {package.package_id: model.new_bool_var(f"load_{package.package_id}") for package in packages}

    rules = {
        "capacity": True,
        "must_include": config.should_include == ShouldInclude.HARD,
        "incompatible": config.incompatible,
        "dependency": config.dependency,
        "priority_bonus": config.priority_weight > 0,
        **{rule.label: True for rule in config.category_rules},
    }

    _add_capacity(model, packages, load, config.capacity)
    if rules["must_include"]:
        _add_must_include(model, packages, load)
    if rules["incompatible"]:
        _add_incompatible(model, load, dataset.incompatible_pairs)
    if rules["dependency"]:
        _add_dependency(model, load, dataset.dependencies)
    penalties = []
    for rule in config.category_rules:
        if rule.is_soft:
            penalties.append((rule.penalty, _add_soft_category_rule(model, packages, load, rule)))
        else:
            _add_hard_category_rule(model, packages, load, rule)
    _maximize_score(model, packages, load, config.priority_weight, penalties)

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


def _add_incompatible(
    model: cp_model.CpModel, load: dict[str, cp_model.IntVar], pairs: tuple[tuple[str, str], ...]
) -> None:
    """Two incompatible packages cannot both be loaded: x_a + x_b <= 1 for every pair (a, b)."""
    for first, second in pairs:
        model.add(load[first] + load[second] <= 1).with_name(f"incompatible_{first}_{second}")


def _add_dependency(
    model: cp_model.CpModel, load: dict[str, cp_model.IntVar], dependencies: tuple[tuple[str, str], ...]
) -> None:
    """If a dependent package is loaded, its required package must be too: x_a <= x_b for every (a, b)."""
    for dependent, required in dependencies:
        model.add(load[dependent] <= load[required]).with_name(f"dependency_{dependent}_needs_{required}")


def _add_hard_category_rule(
    model: cp_model.CpModel, packages: list[Package], load: dict[str, cp_model.IntVar], rule: CategoryRule
) -> None:
    """Hard bound on a category: sum(x_i for i in category) >= count (at_least) or <= count (at_most)."""
    loaded = sum(load[package.package_id] for package in packages if package.category == rule.category)
    name = f"{rule.category}_{rule.direction}_{rule.count}"

    if rule.direction == "at_least":
        model.add(loaded >= rule.count).with_name(name)
    else:
        model.add(loaded <= rule.count).with_name(name)


def _add_soft_category_rule(
    model: cp_model.CpModel, packages: list[Package], load: dict[str, cp_model.IntVar], rule: CategoryRule
) -> cp_model.IntVar:
    """Soft bound: returns the violation variable that the objective penalises.

    at_least: shortfall = packages missing below the minimum;  at_most: excess = packages above the limit.
    """
    in_category = [package for package in packages if package.category == rule.category]
    loaded = sum(load[package.package_id] for package in in_category)
    name = f"{rule.category}_{rule.direction}_{rule.count}_soft"

    if rule.direction == "at_least":
        shortfall = model.new_int_var(0, rule.count, f"shortfall_{rule.category}")
        model.add(loaded + shortfall >= rule.count).with_name(name)  # missing packages fill the gap
        return shortfall

    excess = model.new_int_var(0, len(in_category), f"excess_{rule.category}")
    model.add(loaded - excess <= rule.count).with_name(name)  # extra packages beyond the limit
    return excess


def _maximize_score(
    model: cp_model.CpModel,
    packages: list[Package],
    load: dict[str, cp_model.IntVar],
    priority_weight: int,
    penalties: list[tuple[int, cp_model.IntVar]],
) -> None:
    """Objective: max sum((v_i + w * p_i) * x_i) - sum(penalty * violation) over the soft rules."""
    total_score = sum(package_score(package, priority_weight) * load[package.package_id] for package in packages)
    model.maximize(total_score - sum(penalty * violation for penalty, violation in penalties))
