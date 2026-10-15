"""Part 6 checks: objective weights."""

from ortools.sat.python import cp_model

from cargo_optimizer.config import ShouldInclude
from cargo_optimizer.data import Package
from cargo_optimizer.model import build_model
from helpers import NO_RULES, make_config

# One slot. "rich" is worth more; "required" is Critical and must-include.
RICH = Package("rich", 10, 1000, "Low", "Food", False)
REQUIRED = Package("required", 10, 600, "Critical", "Medical", True)


def _choice(**weights) -> set[str]:
    config = make_config(capacity=10, should_include=ShouldInclude.SOFT, **weights)
    cargo = build_model([RICH, REQUIRED], config, NO_RULES)
    solver = cp_model.CpSolver()
    assert solver.solve(cargo.model) == cp_model.OPTIMAL
    return {pid for pid, var in cargo.load.items() if solver.value(var)}


def test_value_alone_picks_the_richer_package():
    assert _choice(value_weight=1, should_include_penalty=0, priority_weight=0) == {"rich"}


def test_should_include_weight_beyond_the_value_gap_keeps_the_required_package():
    # Leaving "required" costs 500 > 1000 - 600.
    assert _choice(value_weight=1, should_include_penalty=500, priority_weight=0) == {"required"}


def test_only_the_ratio_of_weights_matters():
    assert _choice(value_weight=10, should_include_penalty=5000, priority_weight=0) == {"required"}
    assert _choice(value_weight=10, should_include_penalty=300, priority_weight=0) == {"rich"}


def test_value_weight_zero_lets_priority_decide():
    assert _choice(value_weight=0, should_include_penalty=0, priority_weight=1) == {"required"}
