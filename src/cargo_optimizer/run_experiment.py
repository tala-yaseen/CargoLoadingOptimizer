"""Run experiments from configs/experiments.yaml, print their results and save them under results/."""

import argparse
import json
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from fnmatch import fnmatch
from pathlib import Path

import yaml
from ortools.sat.python import cp_model

from cargo_optimizer.config import ExperimentConfig, Method, load_experiments
from cargo_optimizer.data import PRIORITIES, Package, load_packages
from cargo_optimizer.greedy import solve_greedy, unsupported_settings
from cargo_optimizer.model import build_model, package_score

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_PATH = PROJECT_ROOT / "data" / "packages.csv"
CONFIG_PATH = PROJECT_ROOT / "configs" / "experiments.yaml"
RESULTS_DIR = PROJECT_ROOT / "results"


@dataclass(frozen=True)
class ExperimentResult:
    experiment: str
    method: str
    status: str
    capacity: int
    total_weight: int
    total_value: int
    objective_value: int               # total value + priority bonus; equals total_value when priority_weight is 0
    selected_by_priority: dict[str, int]
    num_selected: int
    solve_time_seconds: float
    rules: dict[str, bool]
    skip_reason: str | None
    selected_packages: list[str]


@dataclass(frozen=True)
class _Outcome:
    """What a solving method returns, before totals are computed."""
    status: str
    selected: list[Package]
    solve_time: float
    rules: dict[str, bool]
    skip_reason: str | None = None


def main() -> None:
    parser = argparse.ArgumentParser(description="Run cargo loading experiments.")
    parser.add_argument(
        "experiments", nargs="*", help="experiment names or patterns such as 'part3_*' (default: all)"
    )
    args = parser.parse_args()

    packages = load_packages(DATA_PATH)
    configs = load_experiments(CONFIG_PATH)

    names: list[str] = []
    for pattern in args.experiments or ["*"]:
        matches = [name for name in configs if fnmatch(name, pattern)]
        if not matches:
            parser.error(f"no experiment matches {pattern!r}; available: {list(configs)}")
        names.extend(name for name in matches if name not in names)

    for name in names:
        run_experiment(packages, configs[name])


def run_experiment(packages: list[Package], config: ExperimentConfig) -> ExperimentResult:
    """Solve one experiment with its configured method, then print and save the result."""
    if config.method == Method.CPSAT:
        outcome = _solve_with_cpsat(packages, config)
    else:
        outcome = _solve_with_greedy(packages, config)

    result = ExperimentResult(
        experiment=config.name,
        method=str(config.method),
        status=outcome.status,
        capacity=config.capacity,
        total_weight=sum(package.weight_kg for package in outcome.selected),
        total_value=sum(package.value for package in outcome.selected),
        objective_value=sum(package_score(package, config.priority_weight) for package in outcome.selected),
        selected_by_priority={
            priority: sum(package.priority == priority for package in outcome.selected) for priority in PRIORITIES
        },
        num_selected=len(outcome.selected),
        solve_time_seconds=round(outcome.solve_time, 4),
        rules=outcome.rules,
        skip_reason=outcome.skip_reason,
        selected_packages=[package.package_id for package in outcome.selected],
    )
    _print_result(result)
    _save_result(config, result)
    return result


def _solve_with_cpsat(packages: list[Package], config: ExperimentConfig) -> _Outcome:
    """Build and solve the CP-SAT model."""
    cargo = build_model(packages, config)
    solver = cp_model.CpSolver()
    status = solver.solve(cargo.model)

    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        selected = [package for package in packages if solver.value(cargo.load[package.package_id])]
    else:
        selected = []
    return _Outcome(solver.status_name(status), selected, solver.wall_time, cargo.rules)


def _solve_with_greedy(packages: list[Package], config: ExperimentConfig) -> _Outcome:
    """Run the greedy baseline, or skip it when the config uses settings greedy cannot honour.

    Its answer always fits but is not proven optimal, hence FEASIBLE.
    """
    unsupported = unsupported_settings(config)
    if unsupported:
        return _Outcome("SKIPPED", [], 0.0, {}, skip_reason=f"greedy does not support {', '.join(unsupported)}")

    start = time.perf_counter()
    selected = solve_greedy(packages, config)
    rules = {"capacity": True, "priority_bonus": config.priority_weight > 0}
    return _Outcome("FEASIBLE", selected, time.perf_counter() - start, rules)


def _print_result(result: ExperimentResult) -> None:
    print(f"\n=== {result.experiment} ({result.method}) ===")
    if result.rules:
        print("Rules:          " + ", ".join(
            f"{rule} [{'ENABLED' if enabled else 'SKIPPED'}]" for rule, enabled in result.rules.items()
        ))
    print(f"Solver status:  {result.status}")
    if result.skip_reason:
        print(f"Skip reason:    {result.skip_reason}")
    print(f"Truck capacity: {result.capacity} kg")
    print(f"Total weight:   {result.total_weight} kg")
    print(f"Total value:    {result.total_value}")
    print(f"Objective:      {result.objective_value}")
    print("By priority:    " + ", ".join(f"{priority} {count}" for priority, count in result.selected_by_priority.items()))
    print(f"Selected ({result.num_selected}): {', '.join(result.selected_packages)}")


def _save_result(config: ExperimentConfig, result: ExperimentResult) -> None:
    """Write a config snapshot and the result into a timestamped folder under results/."""
    run_dir = RESULTS_DIR / f"{datetime.now():%Y%m%d_%H%M%S}_{config.name}"
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "config.yaml").write_text(yaml.safe_dump(config.to_dict(), sort_keys=False))
    (run_dir / "result.json").write_text(json.dumps(asdict(result), indent=2))
    print(f"Saved to {run_dir}")


if __name__ == "__main__":
    main()
