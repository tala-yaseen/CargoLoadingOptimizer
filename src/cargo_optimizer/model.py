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


def missing_must_include(selected: list[Package], packages: list[Package]) -> int:
    """should_included packages that were left behind."""
    selected_ids = {package.package_id for package in selected}
    return sum(package.should_included and package.package_id not in selected_ids for package in packages)


def objective_value(selected: list[Package], packages: list[Package], config: ExperimentConfig) -> int:
    """The objective of a selection: total score minus the penalties of its soft rule violations."""
    total_score = sum(package_score(package, config.priority_weight) for package in selected)
    penalties = sum(rule.penalty * rule_violation(selected, rule) for rule in config.category_rules if rule.is_soft)
    if config.should_include == ShouldInclude.SOFT:
        penalties += config.should_include_penalty * missing_must_include(selected, packages)
    return total_score - penalties


@dataclass
class CargoModel:
    model: cp_model.CpModel
    load: dict[str, cp_model.IntVar]  # x_i: 1 if the package is loaded, keyed by package_id
    rules: dict[str, bool]            # every rule the model knows, and whether this config enabled it
    hard_rules: dict[str, list[cp_model.Constraint]]  # constraints of each hard rule group, for diagnosis
    on_truck: dict[tuple[str, int], cp_model.IntVar]   # y_it: package i on truck t (empty with one truck)


def build_model(packages: list[Package], config: ExperimentConfig, dataset: DatasetConfig) -> CargoModel:
    """Create the decision variables, constraints and objective for one experiment."""
    model = cp_model.CpModel()
    load = {package.package_id: model.new_bool_var(f"load_{package.package_id}") for package in packages}

    rules = {
        "capacity": True,
        "must_include": config.should_include == ShouldInclude.HARD,
        "must_include (soft)": config.should_include == ShouldInclude.SOFT,
        "incompatible": config.incompatible,
        "dependency": config.dependency,
        "priority_bonus": config.priority_weight > 0,
        **{rule.label: True for rule in config.category_rules},
    }

    capacity = config.capacity_kg(sum(package.weight_kg for package in packages))
    hard_rules: dict[str, list[cp_model.Constraint]] = {}
    on_truck: dict[tuple[str, int], cp_model.IntVar] = {}
    if config.trucks == 1:
        hard_rules["capacity"] = [_add_capacity(model, packages, load, capacity)]
    else:
        on_truck, hard_rules["capacity"] = _add_trucks(model, packages, load, capacity, config.trucks)
    if rules["must_include"]:
        hard_rules["must_include"] = _add_must_include(model, packages, load)
    if rules["incompatible"]:
        hard_rules["incompatible"] = _add_incompatible(model, load, dataset.incompatible_pairs)
    if rules["dependency"]:
        hard_rules["dependency"] = _add_dependency(model, load, dataset.dependencies)

    penalties = []
    for rule in config.category_rules:
        if rule.is_soft:
            penalties.append((rule.penalty, _add_soft_category_rule(model, packages, load, rule)))
        else:
            hard_rules[rule.label] = [_add_hard_category_rule(model, packages, load, rule)]
    if rules["must_include (soft)"]:
        left_behind = sum(1 - load[package.package_id] for package in packages if package.should_included)
        penalties.append((config.should_include_penalty, left_behind))
    _maximize_score(model, packages, load, config.priority_weight, penalties)

    return CargoModel(model=model, load=load, rules=rules, hard_rules=hard_rules, on_truck=on_truck)


def _add_capacity(
    model: cp_model.CpModel, packages: list[Package], load: dict[str, cp_model.IntVar], capacity: int
) -> cp_model.Constraint:
    """Total loaded weight must not exceed the truck capacity: sum(w_i * x_i) <= C."""
    total_weight = sum(package.weight_kg * load[package.package_id] for package in packages)
    return model.add(total_weight <= capacity).with_name("capacity")


def _add_trucks(
    model: cp_model.CpModel, packages: list[Package], load: dict[str, cp_model.IntVar], capacity: int, trucks: int
) -> tuple[dict[tuple[str, int], cp_model.IntVar], list[cp_model.Constraint]]:
    """Several trucks of the same capacity: each loaded package rides on exactly one truck.

    sum_t y_it = x_i for every package;  sum_i w_i * y_it <= C for every truck t.
    """
    on_truck = {
        (package.package_id, truck): model.new_bool_var(f"on_truck_{package.package_id}_{truck}")
        for package in packages
        for truck in range(trucks)
    }
    for package in packages:
        ride = sum(on_truck[package.package_id, truck] for truck in range(trucks))
        model.add(ride == load[package.package_id]).with_name(f"one_truck_{package.package_id}")
    capacity_rules = [
        model.add(
            sum(package.weight_kg * on_truck[package.package_id, truck] for package in packages) <= capacity
        ).with_name(f"capacity_truck_{truck}")
        for truck in range(trucks)
    ]
    return on_truck, capacity_rules


def _add_must_include(
    model: cp_model.CpModel, packages: list[Package], load: dict[str, cp_model.IntVar]
) -> list[cp_model.Constraint]:
    """Every should_included package must be loaded: x_i = 1 for all i in S."""
    return [
        model.add(load[package.package_id] == 1).with_name(f"must_include_{package.package_id}")
        for package in packages
        if package.should_included
    ]


def _add_incompatible(
    model: cp_model.CpModel, load: dict[str, cp_model.IntVar], pairs: tuple[tuple[str, str], ...]
) -> list[cp_model.Constraint]:
    """Two incompatible packages cannot both be loaded: x_a + x_b <= 1 for every pair (a, b)."""
    return [
        model.add(load[first] + load[second] <= 1).with_name(f"incompatible_{first}_{second}")
        for first, second in pairs
    ]


def _add_dependency(
    model: cp_model.CpModel, load: dict[str, cp_model.IntVar], dependencies: tuple[tuple[str, str], ...]
) -> list[cp_model.Constraint]:
    """If a dependent package is loaded, its required package must be too: x_a <= x_b for every (a, b)."""
    return [
        model.add(load[dependent] <= load[required]).with_name(f"dependency_{dependent}_needs_{required}")
        for dependent, required in dependencies
    ]


def _add_hard_category_rule(
    model: cp_model.CpModel, packages: list[Package], load: dict[str, cp_model.IntVar], rule: CategoryRule
) -> cp_model.Constraint:
    """Hard bound on a category: sum(x_i for i in category) >= count (at_least) or <= count (at_most)."""
    loaded = sum(load[package.package_id] for package in packages if package.category == rule.category)
    name = f"{rule.category}_{rule.direction}_{rule.count}"

    if rule.direction == "at_least":
        return model.add(loaded >= rule.count).with_name(name)
    return model.add(loaded <= rule.count).with_name(name)


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
    penalties: list[tuple[int, cp_model.LinearExprT]],
) -> None:
    """Objective: max sum((v_i + w * p_i) * x_i) - sum(penalty * violation) over the soft rules."""
    total_score = sum(package_score(package, priority_weight) * load[package.package_id] for package in packages)
    model.maximize(total_score - sum(penalty * violation for penalty, violation in penalties))
