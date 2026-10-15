"""Part 4 checks: incompatible packages, dependencies and category limits."""

from pathlib import Path

import pytest
from ortools.sat.python import cp_model

from cargo_optimizer.config import CategoryRule, DatasetConfig, ExperimentConfig, Method, _build_config, load_datasets
from cargo_optimizer.data import Package
from cargo_optimizer.greedy import unsupported_settings
from cargo_optimizer.model import build_model, objective_value, rule_violation
from helpers import BASE_CONFIG, make_config, make_dataset


def _package(package_id: str, value: int, category: str = "Food") -> Package:
    return Package(package_id, weight_kg=5, value=value, priority="Normal", category=category, should_included=False)


def _loaded(packages: list[Package], config: ExperimentConfig, dataset: DatasetConfig) -> set[str]:
    cargo = build_model(packages, config, dataset)
    solver = cp_model.CpSolver()
    assert solver.solve(cargo.model) == cp_model.OPTIMAL
    return {pid for pid, var in cargo.load.items() if solver.value(var)}


# Incompatible: both fit (capacity 10) and are valuable, so without the rule both load.
X, Y = _package("X", 100), _package("Y", 80)
PAIR_XY = make_dataset(incompatible_pairs=(("X", "Y"),))


def test_without_the_rule_both_packages_load():
    assert _loaded([X, Y], make_config(), PAIR_XY) == {"X", "Y"}


def test_incompatible_pair_keeps_only_the_more_valuable_one():
    assert _loaded([X, Y], make_config(incompatible=True), PAIR_XY) == {"X"}


# Dependency: room for one package only. "tool" is the most valuable but needs "parts", which does not fit with it.
TOOL, PARTS, OTHER = _package("tool", 100), _package("parts", 10), _package("other", 60)
TOOL_NEEDS_PARTS = make_dataset(dependencies=(("tool", "parts"),))


def test_dependency_off_loads_the_most_valuable_package():
    assert _loaded([TOOL, PARTS, OTHER], make_config(capacity=5), TOOL_NEEDS_PARTS) == {"tool"}


def test_dependency_blocks_a_package_whose_requirement_does_not_fit():
    assert _loaded([TOOL, PARTS, OTHER], make_config(capacity=5, dependency=True), TOOL_NEEDS_PARTS) == {"other"}


def test_dependency_pulls_in_the_required_package_when_it_fits():
    loaded = _loaded([TOOL, PARTS, OTHER], make_config(capacity=10, dependency=True), TOOL_NEEDS_PARTS)

    assert loaded == {"tool", "parts"}


# Category rules. Room for four 5 kg packages (capacity 20).
FURNITURE = [_package(f"F{i}", 100 - i, category="Furniture") for i in range(4)]
FOOD, MEDICAL = _package("food", 100), _package("med", 60, category="Medical")


def test_hard_at_most_keeps_the_three_most_valuable():
    config = make_config(capacity=20, category_rules=(CategoryRule("Furniture", "at_most", 3),))

    assert _loaded(FURNITURE, config, make_dataset()) == {"F0", "F1", "F2"}


def test_hard_at_least_forces_a_less_valuable_package():
    # One slot: Food is worth more, but at least one Medical package is required.
    config = make_config(capacity=5, category_rules=(CategoryRule("Medical", "at_least", 1),))

    assert _loaded([FOOD, MEDICAL], config, make_dataset()) == {"med"}


@pytest.mark.parametrize(("penalty", "expected"), [(0, {"food"}), (30, {"food"}), (50, {"med"})])
def test_soft_at_least_is_kept_only_when_the_penalty_outweighs_the_value_lost(penalty, expected):
    # Food scores 100 - penalty (target missed); Medical scores 60 (target met). Medical wins once penalty > 40.
    config = make_config(capacity=5, category_rules=(CategoryRule("Medical", "at_least", 1, penalty),))

    assert _loaded([FOOD, MEDICAL], config, make_dataset()) == expected


@pytest.mark.parametrize(("penalty", "expected_count"), [(50, 4), (100, 3)])
def test_soft_at_most_allows_extra_packages_only_while_they_are_worth_the_penalty(penalty, expected_count):
    # The 4th Furniture package is worth 97: loaded when the penalty is 50, dropped when it is 100.
    config = make_config(capacity=20, category_rules=(CategoryRule("Furniture", "at_most", 3, penalty),))

    assert len(_loaded(FURNITURE, config, make_dataset())) == expected_count


def test_violation_and_objective_match_the_formula():
    rule = CategoryRule("Medical", "at_least", 2, penalty=50)
    config = make_config(category_rules=(rule,))

    assert rule_violation([FOOD], rule) == 2
    assert rule_violation([MEDICAL], rule) == 1
    assert rule_violation(FURNITURE, CategoryRule("Furniture", "at_most", 3)) == 1
    assert objective_value([FOOD], [FOOD, MEDICAL], config) == 100 - 50 * 2


@pytest.mark.parametrize(
    ("rule", "message"),
    [
        ({"category": "Furnitur", "at_most": 3}, "unknown category"),
        ({"category": "Medical"}, "exactly one of at_least / at_most"),
        ({"category": "Medical", "at_least": 2, "at_most": 5}, "exactly one of at_least / at_most"),
        ({"category": "Medical", "at_least": 2, "penalty": -1}, "penalty"),
        ({"category": "Medical", "at_least": 2, "weight": 1}, "unknown keys"),
    ],
)
def test_invalid_category_rules_are_rejected(rule, message):
    settings = {**BASE_CONFIG.to_dict(), "category_rules": [rule]}
    del settings["name"]

    with pytest.raises(ValueError, match=message):
        _build_config("test", settings)


def test_greedy_skips_every_part4_rule():
    config = make_config(
        method=Method.GREEDY, incompatible=True, dependency=True,
        category_rules=(CategoryRule("Furniture", "at_most", 3),),
    )

    assert unsupported_settings(config) == ["incompatible packages", "package dependencies", "category rules"]


def test_yaml_datasets_use_their_own_package_ids(tmp_path: Path):
    config_file = tmp_path / "experiments.yaml"
    config_file.write_text(
        "datasets:\n"
        "  full:\n    path: data/packages.csv\n    dependencies: [[P0007, P0003]]\n"
        "  example:\n    path: data/example_packages.csv\n    incompatible_pairs: [[P02, P06]]\n"
    )

    datasets = load_datasets(config_file)

    assert datasets["full"].dependencies == (("P0007", "P0003"),)
    assert datasets["example"].incompatible_pairs == (("P02", "P06"),)
