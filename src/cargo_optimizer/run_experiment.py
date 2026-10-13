"""Run experiments from configs/experiments.yaml, print their results and save them under results/."""

import argparse
import json
import time
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

import yaml
from ortools.sat.python import cp_model

from cargo_optimizer.config import ExperimentConfig, load_experiments
from cargo_optimizer.data import Package, load_packages
from cargo_optimizer.greedy import solve_greedy
from cargo_optimizer.model import build_model

DATA_PATH = Path("data/packages.csv")
CONFIG_PATH = Path("configs/experiments.yaml")
RESULTS_DIR = Path("results")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run cargo loading experiments.")
    parser.add_argument("experiments", nargs="*", help="experiment names to run (default: all)")
    args = parser.parse_args()

    packages = load_packages(DATA_PATH)
    configs = load_experiments(CONFIG_PATH)

    names = args.experiments or list(configs)
    unknown = [name for name in names if name not in configs]
    if unknown:
        parser.error(f"unknown experiments {unknown}; available: {list(configs)}")

    for name in names:
        run_experiment(packages, configs[name])


def run_experiment(packages: list[Package], config: ExperimentConfig) -> dict:
    """Solve one experiment with its configured method, then print and save the result."""
    if config.method == "cpsat":
        status, selected, solve_time = _solve_with_cpsat(packages, config)
    else:
        status, selected, solve_time = _solve_with_greedy(packages, config)

    result = {
        "experiment": config.name,
        "method": config.method,
        "status": status,
        "capacity": config.capacity,
        "total_weight": sum(package.weight_kg for package in selected),
        "total_value": sum(package.value for package in selected),
        "num_selected": len(selected),
        "solve_time_seconds": round(solve_time, 4),
        "selected_packages": [package.package_id for package in selected],
    }
    _print_result(result)
    _save_result(config, result)
    return result


def _solve_with_cpsat(packages: list[Package], config: ExperimentConfig) -> tuple[str, list[Package], float]:
    """Build and solve the CP-SAT model; return status name, selected packages and solve time."""
    cargo = build_model(packages, config)
    solver = cp_model.CpSolver()
    status = solver.solve(cargo.model)

    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        selected = [package for package in packages if solver.value(cargo.load[package.package_id])]
    else:
        selected = []
    return solver.status_name(status), selected, solver.wall_time


def _solve_with_greedy(packages: list[Package], config: ExperimentConfig) -> tuple[str, list[Package], float]:
    """Run the greedy baseline; its answer always fits but is not proven optimal, hence FEASIBLE."""
    start = time.perf_counter()
    selected = solve_greedy(packages, config)
    return "FEASIBLE", selected, time.perf_counter() - start


def _print_result(result: dict) -> None:
    print(f"\n=== {result['experiment']} ({result['method']}) ===")
    print(f"Solver status:  {result['status']}")
    print(f"Truck capacity: {result['capacity']} kg")
    print(f"Total weight:   {result['total_weight']} kg")
    print(f"Total value:    {result['total_value']}")
    print(f"Selected ({result['num_selected']}): {', '.join(result['selected_packages'])}")


def _save_result(config: ExperimentConfig, result: dict) -> None:
    """Write a config snapshot and the result into a new timestamped folder under results/."""
    run_dir = RESULTS_DIR / f"{datetime.now():%Y%m%d_%H%M%S}_{config.name}"
    run_dir.mkdir(parents=True)
    (run_dir / "config.yaml").write_text(yaml.safe_dump(asdict(config), sort_keys=False))
    (run_dir / "result.json").write_text(json.dumps(result, indent=2))
    print(f"Saved to {run_dir}")


if __name__ == "__main__":
    main()
