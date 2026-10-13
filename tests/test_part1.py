"""Part 1 checks on small hand-computed examples."""

from pathlib import Path

import pytest
from ortools.sat.python import cp_model

from cargo_optimizer.config import ExperimentConfig, Method, ShouldInclude, load_experiments
from cargo_optimizer.data import Package, load_packages
from cargo_optimizer.greedy import solve_greedy
from cargo_optimizer.model import build_model

# Capacity 10: greedy takes A (best value per kg) and gets 30; the optimum is B + D = 40.
PACKAGES = [
    Package("A", weight_kg=6, value=30, priority="Normal", category="Food", should_included=False),
    Package("B", weight_kg=5, value=20, priority="Normal", category="Food", should_included=False),
    Package("D", weight_kg=5, value=20, priority="Normal", category="Food", should_included=False),
]


def _config(method: Method) -> ExperimentConfig:
    return ExperimentConfig(name="test", method=method, capacity=10, should_include=ShouldInclude.IGNORE)


def test_cpsat_finds_the_optimum():
    cargo = build_model(PACKAGES, _config(Method.CPSAT))
    solver = cp_model.CpSolver()

    assert solver.solve(cargo.model) == cp_model.OPTIMAL
    assert solver.objective_value == 40
    assert {pid for pid, var in cargo.load.items() if solver.value(var)} == {"B", "D"}


def test_greedy_takes_best_ratio_first():
    selected = solve_greedy(PACKAGES, _config(Method.GREEDY))

    assert [package.package_id for package in selected] == ["A"]


def test_config_rejects_unknown_setting(tmp_path: Path):
    config_file = tmp_path / "experiments.yaml"
    config_file.write_text(
        "defaults:\n  method: cpsat\n  capcity: 1000\n  should_include: ignore\nexperiments:\n  part1: {}\n"
    )

    with pytest.raises(ValueError, match="capcity"):
        load_experiments(config_file)


def test_data_rejects_unknown_priority(tmp_path: Path):
    csv_file = tmp_path / "packages.csv"
    csv_file.write_text(
        "package_id,weight_kg,value,priority,category,should_included\n"
        "P1,10,100,Hihg,Food,True\n"
    )

    with pytest.raises(ValueError, match="line 2: unknown priority 'Hihg'"):
        load_packages(csv_file)
