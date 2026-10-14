"""Part 3 checks: priority bonus in the objective."""

import pytest
from ortools.sat.python import cp_model

from cargo_optimizer.config import ExperimentConfig, Method, ShouldInclude, _build_config
from cargo_optimizer.data import Package
from cargo_optimizer.greedy import solve_greedy
from cargo_optimizer.model import build_model, package_score

# The truck fits only one. B overtakes A when 600 + 3w > 1000, i.e. w > 133.3.
A = Package("A", weight_kg=10, value=1000, priority="Low", category="Food", should_included=False)
B = Package("B", weight_kg=10, value=600, priority="Critical", category="Medical", should_included=False)


def _config(priority_weight: int, method: Method = Method.CPSAT) -> ExperimentConfig:
    return ExperimentConfig(
        name="test", method=method, capacity=10, should_include=ShouldInclude.IGNORE, priority_weight=priority_weight
    )


def _cpsat_choice(priority_weight: int) -> set[str]:
    cargo = build_model([A, B], _config(priority_weight))
    solver = cp_model.CpSolver()
    assert solver.solve(cargo.model) == cp_model.OPTIMAL
    return {pid for pid, var in cargo.load.items() if solver.value(var)}


def test_score_adds_weighted_priority_points():
    assert package_score(B, priority_weight=10) == 600 + 10 * 3
    assert package_score(A, priority_weight=10) == 1000


@pytest.mark.parametrize(("priority_weight", "expected"), [(0, {"A"}), (100, {"A"}), (150, {"B"})])
def test_choice_flips_to_critical_package_as_weight_grows(priority_weight, expected):
    assert _cpsat_choice(priority_weight) == expected


def test_greedy_uses_the_same_score():
    selected = solve_greedy([A, B], _config(150, method=Method.GREEDY))

    assert [package.package_id for package in selected] == ["B"]


def test_negative_priority_weight_is_rejected():
    settings = {"method": "cpsat", "capacity": 10, "should_include": "ignore", "priority_weight": -5}

    with pytest.raises(ValueError, match="priority_weight"):
        _build_config("test", settings)
