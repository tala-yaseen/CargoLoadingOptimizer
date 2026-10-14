"""Part 2 checks: should_included as a hard constraint."""

from ortools.sat.python import cp_model

from cargo_optimizer.config import ExperimentConfig, Method, ShouldInclude
from cargo_optimizer.data import Package
from cargo_optimizer.greedy import unsupported_settings
from cargo_optimizer.model import build_model
from helpers import NO_RULES, make_config


def _package(package_id: str, weight_kg: int, value: int, should_included: bool) -> Package:
    return Package(package_id, weight_kg, value, "Normal", "Food", should_included)


def _solve(packages: list[Package], config: ExperimentConfig) -> tuple[int, set[str]]:
    cargo = build_model(packages, config, NO_RULES)
    solver = cp_model.CpSolver()
    status = solver.solve(cargo.model)
    loaded = {pid for pid, var in cargo.load.items() if status != cp_model.INFEASIBLE and solver.value(var)}
    return status, loaded


def test_hard_must_include_forces_a_low_value_package():
    packages = [_package("cheap", 5, 1, should_included=True), _package("rich", 5, 100, should_included=False)]

    status, loaded = _solve(packages, make_config(capacity=5, should_include=ShouldInclude.HARD))

    assert status == cp_model.OPTIMAL
    assert loaded == {"cheap"}


def test_ignore_mode_leaves_should_included_unused():
    packages = [_package("cheap", 5, 1, should_included=True), _package("rich", 5, 100, should_included=False)]

    status, loaded = _solve(packages, make_config(capacity=5, should_include=ShouldInclude.IGNORE))

    assert status == cp_model.OPTIMAL
    assert loaded == {"rich"}


def test_must_include_heavier_than_capacity_is_infeasible():
    packages = [_package("a", 6, 10, should_included=True), _package("b", 6, 10, should_included=True)]

    status, _ = _solve(packages, make_config(should_include=ShouldInclude.HARD))

    assert status == cp_model.INFEASIBLE


def test_greedy_reports_hard_must_include_as_unsupported():
    config = make_config(should_include=ShouldInclude.HARD, method=Method.GREEDY)

    assert unsupported_settings(config) == ["should_include=hard"]
