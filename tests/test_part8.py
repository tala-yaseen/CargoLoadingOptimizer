"""Part 8 checks: solver settings and truck symmetry breaking."""

import pytest
from ortools.sat.python import cp_model

from cargo_optimizer.config import _build_config
from cargo_optimizer.data import Package
from cargo_optimizer.model import build_model, make_solver
from helpers import BASE_CONFIG, NO_RULES, make_config

PACKAGES = [Package(f"P{i}", weight_kg=3 + i % 4, value=10 + 7 * i, priority="Normal", category="Food",
                    should_included=False) for i in range(12)]


def _best_value(**settings) -> float:
    config = make_config(**settings)
    cargo = build_model(PACKAGES, config, NO_RULES)
    solver = make_solver(config)
    assert solver.solve(cargo.model) == cp_model.OPTIMAL
    return solver.objective_value


def test_solver_uses_the_configured_settings():
    config = make_config(num_workers=2, time_limit_seconds=5, random_seed=7, relative_gap_limit=0.01, presolve=False)
    parameters = make_solver(config).parameters

    assert (parameters.num_workers, parameters.max_time_in_seconds, parameters.random_seed) == (2, 5, 7)
    assert (parameters.relative_gap_limit, parameters.cp_model_presolve) == (0.01, False)


def test_symmetry_breaking_keeps_the_same_optimum():
    assert _best_value(trucks=3, symmetry_breaking=True) == _best_value(trucks=3, symmetry_breaking=False)


def test_symmetry_breaking_orders_trucks_by_load():
    config = make_config(trucks=3, symmetry_breaking=True)
    cargo = build_model(PACKAGES, config, NO_RULES)
    solver = make_solver(config)
    solver.solve(cargo.model)
    loads = [
        sum(p.weight_kg for p in PACKAGES if solver.value(cargo.on_truck[p.package_id, truck])) for truck in range(3)
    ]

    assert loads == sorted(loads, reverse=True)


@pytest.mark.parametrize(
    ("setting", "value"),
    [("time_limit_seconds", 0), ("num_workers", 0), ("random_seed", -1), ("relative_gap_limit", 1.5)],
)
def test_invalid_solver_settings_are_rejected(setting, value):
    settings = {**BASE_CONFIG.to_dict(), setting: value}
    del settings["name"]

    with pytest.raises(ValueError, match=setting):
        _build_config("test", settings)
