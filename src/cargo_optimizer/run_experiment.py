"""Run experiments from configs/experiments.yaml, print their results and save them under results/."""

import argparse
import csv
import json
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from fnmatch import fnmatch
from pathlib import Path

import yaml
from ortools.sat.python import cp_model

from cargo_optimizer.config import DatasetConfig, ExperimentConfig, Method, load_datasets, load_experiments
from cargo_optimizer.data import PRIORITIES, Package, load_packages
from cargo_optimizer.diagnose import find_conflicting_rules
from cargo_optimizer.greedy import solve_greedy, unsupported_settings
from cargo_optimizer.model import build_model, make_solver, objective_value, rule_violation

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = PROJECT_ROOT / "configs" / "experiments.yaml"
RESULTS_DIR = PROJECT_ROOT / "results"


@dataclass(frozen=True)
class ExperimentResult:
    experiment: str
    dataset: str
    method: str
    status: str
    capacity: int  # kg per truck, after resolving a percentage capacity
    trucks: int
    total_weight: int
    total_value: int
    objective_value: int | None        # total value + priority bonus - soft rule penalties; None without a solution
    selected_by_priority: dict[str, int]
    soft_rule_violations: dict[str, int]  # packages beyond each soft category rule's bound
    preferred_included: int            # should_included packages that were loaded
    truck_weights: list[int]           # kg loaded on each truck (only with several trucks)
    conflicting_rules: list[str]       # for an infeasible model: a minimal set of hard rules that conflict
    num_selected: int
    solve_time_seconds: float
    num_variables: int                 # model size (0 for greedy)
    num_constraints: int
    best_bound: float | None           # CP-SAT's proven upper bound on the objective
    gap: float | None                  # (bound - objective) / bound: 0 means proven optimal
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
    truck_weights: list[int] = field(default_factory=list)
    conflicting_rules: list[str] = field(default_factory=list)
    num_variables: int = 0
    num_constraints: int = 0
    best_bound: float | None = None


def main() -> None:
    parser = argparse.ArgumentParser(description="Run cargo loading experiments.")
    parser.add_argument(
        "experiments", nargs="*", help="experiment names or patterns such as 'part3_*' (default: all)"
    )
    parser.add_argument("--dataset", default="full", help="dataset name from configs/experiments.yaml (default: full)")
    parser.add_argument("--quiet", action="store_true", help="print only the summary table, not every run's details")
    args = parser.parse_args()

    datasets = load_datasets(CONFIG_PATH)
    if args.dataset not in datasets:
        parser.error(f"unknown dataset {args.dataset!r}; available: {list(datasets)}")
    dataset = datasets[args.dataset]
    packages = load_packages(PROJECT_ROOT / dataset.path)
    _check_rule_ids(dataset, packages)
    configs = load_experiments(CONFIG_PATH)

    names: list[str] = []
    for pattern in args.experiments or ["*"]:
        matches = [name for name in configs if fnmatch(name, pattern)]
        if not matches:
            parser.error(f"no experiment matches {pattern!r}; available: {list(configs)}")
        names.extend(name for name in matches if name not in names)

    started = datetime.now()
    runs = [(configs[name], run_experiment(packages, configs[name], dataset, verbose=not args.quiet)) for name in names]
    _print_summary(runs)
    _save_summary(runs, dataset, started)


def _check_rule_ids(dataset: DatasetConfig, packages: list[Package]) -> None:
    """Every package ID a dataset's rules refer to must exist in that dataset."""
    missing = sorted(dataset.package_ids() - {package.package_id for package in packages})
    if missing:
        raise ValueError(f"dataset {dataset.name!r}: rules refer to unknown packages {missing}")


def run_experiment(
    packages: list[Package], config: ExperimentConfig, dataset: DatasetConfig, verbose: bool = True
) -> ExperimentResult:
    """Solve one experiment with its configured method, then print and save the result."""
    if config.method == Method.CPSAT:
        outcome = _solve_with_cpsat(packages, config, dataset)
    else:
        outcome = _solve_with_greedy(packages, config)

    has_solution = outcome.status in ("OPTIMAL", "FEASIBLE")
    objective = objective_value(outcome.selected, packages, config) if has_solution else None
    result = ExperimentResult(
        experiment=config.name,
        dataset=dataset.name,
        method=str(config.method),
        status=outcome.status,
        capacity=config.capacity_kg(sum(package.weight_kg for package in packages)),
        trucks=config.trucks,
        total_weight=sum(package.weight_kg for package in outcome.selected),
        total_value=sum(package.value for package in outcome.selected),
        objective_value=objective,
        selected_by_priority={
            priority: sum(package.priority == priority for package in outcome.selected) for priority in PRIORITIES
        },
        soft_rule_violations={
            rule.label: rule_violation(outcome.selected, rule) for rule in config.category_rules if rule.is_soft
        } if has_solution else {},
        preferred_included=sum(package.should_included for package in outcome.selected),
        truck_weights=outcome.truck_weights,
        conflicting_rules=outcome.conflicting_rules,
        num_selected=len(outcome.selected),
        solve_time_seconds=round(outcome.solve_time, 4),
        num_variables=outcome.num_variables,
        num_constraints=outcome.num_constraints,
        best_bound=outcome.best_bound,
        gap=_gap(outcome.best_bound, objective) if has_solution and outcome.best_bound is not None else None,
        rules=outcome.rules,
        skip_reason=outcome.skip_reason,
        selected_packages=[package.package_id for package in outcome.selected],
    )
    if verbose:
        _print_result(result)
    _save_result(config, dataset, result, verbose)
    return result


def _solve_with_cpsat(packages: list[Package], config: ExperimentConfig, dataset: DatasetConfig) -> _Outcome:
    """Build and solve the CP-SAT model."""
    cargo = build_model(packages, config, dataset)
    solver = make_solver(config)
    status = solver.solve(cargo.model)
    size = {
        "num_variables": len(cargo.model.proto.variables),
        "num_constraints": len(cargo.model.proto.constraints),
    }

    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        selected = [package for package in packages if solver.value(cargo.load[package.package_id])]
        truck_weights = [
            sum(package.weight_kg for package in selected if solver.value(cargo.on_truck[package.package_id, truck]))
            for truck in range(config.trucks)
        ] if cargo.on_truck else []
        return _Outcome(
            solver.status_name(status), selected, solver.wall_time, cargo.rules,
            truck_weights=truck_weights, best_bound=solver.best_objective_bound, **size,
        )

    conflict = find_conflicting_rules(packages, config, dataset) if status == cp_model.INFEASIBLE else []
    return _Outcome(solver.status_name(status), [], solver.wall_time, cargo.rules, conflicting_rules=conflict, **size)


def _gap(bound: float, objective: int) -> float:
    """Relative distance between the proven bound and the solution found (maximisation)."""
    return round((bound - objective) / max(1.0, abs(bound)), 6)


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
    print(f"\n=== {result.experiment} ({result.method}, {result.dataset} dataset) ===")
    if result.rules:
        print("Rules:          " + ", ".join(
            f"{rule} [{'ENABLED' if enabled else 'SKIPPED'}]" for rule, enabled in result.rules.items()
        ))
    print(f"Solver status:  {result.status}")
    if result.skip_reason:
        print(f"Skip reason:    {result.skip_reason}")
    if result.conflicting_rules:
        print(f"Conflict:       {' + '.join(result.conflicting_rules)} cannot all hold")
    print(f"Truck capacity: {result.capacity} kg" + (f" x {result.trucks} trucks" if result.trucks > 1 else ""))
    if result.truck_weights:
        print(f"Per truck:      {result.truck_weights} kg")
    print(f"Total weight:   {result.total_weight} kg")
    print(f"Total value:    {result.total_value}")
    print(f"Must-include:   {result.preferred_included} loaded")
    if result.num_variables:
        gap = "" if result.gap is None else f", gap {result.gap:.2%}"
        print(f"Model size:     {result.num_variables} variables, {result.num_constraints} constraints"
              f" | solved in {result.solve_time_seconds} s{gap}")
    print(f"Objective:      {'-' if result.objective_value is None else result.objective_value}")
    if result.soft_rule_violations:
        print("Violations:     " + ", ".join(f"{rule}: {n}" for rule, n in result.soft_rule_violations.items()))
    print("By priority:    " + ", ".join(f"{priority} {count}" for priority, count in result.selected_by_priority.items()))
    print(f"Selected ({result.num_selected}): {', '.join(result.selected_packages)}")


def _save_result(config: ExperimentConfig, dataset: DatasetConfig, result: ExperimentResult, verbose: bool) -> None:
    """Write a config snapshot (experiment + dataset) and the result into a timestamped folder under results/."""
    run_dir = RESULTS_DIR / f"{datetime.now():%Y%m%d_%H%M%S}_{dataset.name}_{config.name}"
    run_dir.mkdir(parents=True, exist_ok=True)
    snapshot = {**config.to_dict(), "dataset": dataset.to_dict()}
    (run_dir / "config.yaml").write_text(yaml.safe_dump(snapshot, sort_keys=False))
    (run_dir / "result.json").write_text(json.dumps(asdict(result), indent=2))
    if verbose:
        print(f"Saved to {run_dir}")


SUMMARY_COLUMNS = [
    "dataset", "experiment", "method", "status", "capacity", "trucks", "should_include", "should_include_penalty",
    "value_weight", "priority_weight", "incompatible", "dependency", "category_rules", "num_selected", "preferred_included",
    "total_weight", "total_value", "objective_value", *PRIORITIES, "soft_rule_violations", "conflicting_rules",
    "num_workers", "time_limit_seconds", "random_seed", "relative_gap_limit", "presolve", "symmetry_breaking", "num_variables", "num_constraints",
    "best_bound", "gap", "solve_time_seconds", "skip_reason",
]


def _summary_row(config: ExperimentConfig, result: ExperimentResult) -> dict:
    """One flat row per run: the settings that define it and the numbers that describe its result."""
    return {
        "dataset": result.dataset,
        "experiment": result.experiment,
        "method": result.method,
        "status": result.status,
        "capacity": result.capacity,
        "trucks": config.trucks,
        "should_include": str(config.should_include),
        "should_include_penalty": config.should_include_penalty,
        "value_weight": config.value_weight,
        "priority_weight": config.priority_weight,
        "incompatible": config.incompatible,
        "dependency": config.dependency,
        "category_rules": "; ".join(rule.label for rule in config.category_rules),
        "num_selected": result.num_selected,
        "preferred_included": result.preferred_included,
        "total_weight": result.total_weight,
        "total_value": result.total_value,
        "objective_value": "" if result.objective_value is None else result.objective_value,
        **result.selected_by_priority,
        "soft_rule_violations": sum(result.soft_rule_violations.values()),
        "conflicting_rules": " + ".join(result.conflicting_rules),
        "num_workers": config.num_workers,
        "time_limit_seconds": config.time_limit_seconds,
        "random_seed": config.random_seed,
        "relative_gap_limit": config.relative_gap_limit,
        "presolve": config.presolve,
        "symmetry_breaking": config.symmetry_breaking,
        "num_variables": result.num_variables,
        "num_constraints": result.num_constraints,
        "best_bound": "" if result.best_bound is None else result.best_bound,
        "gap": "" if result.gap is None else result.gap,
        "solve_time_seconds": result.solve_time_seconds,
        "skip_reason": result.skip_reason or "",
    }


def _save_summary(
    runs: list[tuple[ExperimentConfig, ExperimentResult]], dataset: DatasetConfig, started: datetime
) -> None:
    """Write one CSV row per run of this invocation, ready for comparison tables (Part 6)."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    path = RESULTS_DIR / f"summary_{started:%Y%m%d_%H%M%S}_{dataset.name}.csv"
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=SUMMARY_COLUMNS)
        writer.writeheader()
        writer.writerows(_summary_row(config, result) for config, result in runs)
    print(f"\nSummary of {len(runs)} runs saved to {path}")


def _print_summary(runs: list[tuple[ExperimentConfig, ExperimentResult]]) -> None:
    """One line per run, so many runs can be compared at a glance."""
    width = max(len(result.experiment) for _, result in runs)
    print(f"\n{'experiment':<{width}} {'status':<11} {'value':>8} {'objective':>10} {'C/H/N/L':>12}")
    for _, result in runs:
        counts = "/".join(str(count) for count in result.selected_by_priority.values())
        objective = "-" if result.objective_value is None else result.objective_value
        print(f"{result.experiment:<{width}} {result.status:<11} {result.total_value:>8} {objective:>10} {counts:>12}")


if __name__ == "__main__":
    main()
