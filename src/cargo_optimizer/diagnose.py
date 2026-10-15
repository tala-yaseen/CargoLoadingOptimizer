"""Explain an infeasible model: which hard rule groups conflict with each other."""

from ortools.sat.python import cp_model

from cargo_optimizer.config import DatasetConfig, ExperimentConfig
from cargo_optimizer.data import Package
from cargo_optimizer.model import build_model


def find_conflicting_rules(packages: list[Package], config: ExperimentConfig, dataset: DatasetConfig) -> list[str]:
    """A minimal set of hard rule groups that cannot all hold together; empty if the model is feasible.

    Each rule group gets an on/off switch (its constraints only apply while the switch is on). Solving with
    every switch assumed on, CP-SAT reports a set of switches that explain the infeasibility; removing one
    group at a time then keeps only the groups that are really needed for the conflict.
    """
    cargo = build_model(packages, config, dataset)
    cargo.model.clear_objective()  # feasibility is all that matters here
    switches = {}
    for name, constraints in cargo.hard_rules.items():
        switches[name] = cargo.model.new_bool_var(f"enforce_{name}")
        for constraint in constraints:
            constraint.only_enforce_if(switches[name])

    def conflict_among(names: list[str]) -> list[str] | None:
        """The rule groups CP-SAT blames when only `names` are switched on, or None if that is feasible."""
        cargo.model.clear_assumptions()
        cargo.model.add_assumptions([switches[name] for name in names])
        solver = cp_model.CpSolver()
        if solver.solve(cargo.model) != cp_model.INFEASIBLE:
            return None
        blamed = set(solver.sufficient_assumptions_for_infeasibility())
        return [name for name in names if switches[name].index in blamed]

    conflict = conflict_among(list(switches))
    if conflict is None:
        return []
    for name in list(conflict):
        smaller = [other for other in conflict if other != name]
        if smaller and conflict_among(smaller) is not None:
            conflict = smaller
    return conflict
