"""Part 5 checks: conflict diagnosis and the relaxations (trucks, soft must-include)."""

import pytest
from ortools.sat.python import cp_model

from cargo_optimizer.config import CategoryRule, ShouldInclude
from cargo_optimizer.data import Package
from cargo_optimizer.diagnose import find_conflicting_rules
from cargo_optimizer.model import build_model
from helpers import NO_RULES, make_config


def _package(package_id: str, weight_kg: int, value: int, should_included: bool = False, category: str = "Food"):
    return Package(package_id, weight_kg, value, "Normal", category, should_included)


def _loaded(packages, config) -> set[str]:
    cargo = build_model(packages, config, NO_RULES)
    solver = cp_model.CpSolver()
    assert solver.solve(cargo.model) == cp_model.OPTIMAL
    return {pid for pid, var in cargo.load.items() if solver.value(var)}


# Two must-include packages of 6 kg: they do not fit together in one 10 kg truck.
HEAVY_MUST = [_package("a", 6, 10, should_included=True), _package("b", 6, 10, should_included=True)]


def test_diagnosis_names_capacity_and_must_include():
    config = make_config(should_include=ShouldInclude.HARD)

    assert find_conflicting_rules(HEAVY_MUST, config, NO_RULES) == ["capacity", "must_include"]


def test_diagnosis_finds_a_rule_that_is_impossible_on_its_own():
    medical = [_package("m1", 1, 10, category="Medical"), _package("m2", 1, 10, category="Medical")]
    config = make_config(category_rules=(CategoryRule("Medical", "at_least", 3),))

    assert find_conflicting_rules(medical, config, NO_RULES) == ["Medical at_least 3 (hard)"]


def test_diagnosis_of_a_feasible_model_is_empty():
    assert find_conflicting_rules(HEAVY_MUST, make_config(), NO_RULES) == []


def test_a_second_truck_restores_feasibility():
    assert _loaded(HEAVY_MUST, make_config(should_include=ShouldInclude.HARD, trucks=2)) == {"a", "b"}


@pytest.mark.parametrize(("penalty", "expected"), [(50, {"rich"}), (200, {"must"})])
def test_soft_must_include_is_kept_only_when_the_penalty_outweighs_the_value_lost(penalty, expected):
    # One slot: "rich" is worth 100, "must" 1; leaving "must" behind costs the penalty.
    packages = [_package("must", 5, 1, should_included=True), _package("rich", 5, 100)]
    config = make_config(capacity=5, should_include=ShouldInclude.SOFT, should_include_penalty=penalty)

    assert _loaded(packages, config) == expected
