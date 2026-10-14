"""Greedy baseline: load packages by score per kg until the truck is full."""

from cargo_optimizer.config import ExperimentConfig, ShouldInclude
from cargo_optimizer.data import Package
from cargo_optimizer.model import package_score


def unsupported_settings(config: ExperimentConfig) -> list[str]:
    """Settings in this config that greedy cannot honour; a non-empty list means the run is skipped."""
    unsupported = []
    if config.should_include != ShouldInclude.IGNORE:
        unsupported.append(f"should_include={config.should_include}")
    if config.incompatible:
        unsupported.append("incompatible packages")
    if config.dependency:
        unsupported.append("package dependencies")
    if config.category_rules:
        unsupported.append("category rules")
    return unsupported


def solve_greedy(packages: list[Package], config: ExperimentConfig) -> list[Package]:
    """Take packages in order of score per kg (value per kg when priority_weight is 0), skipping any that no longer fit."""
    by_ratio = sorted(
        packages,
        key=lambda package: package_score(package, config.priority_weight) / package.weight_kg,
        reverse=True,
    )

    selected: list[Package] = []
    remaining = config.capacity
    for package in by_ratio:
        if package.weight_kg <= remaining:
            selected.append(package)
            remaining -= package.weight_kg
    return selected
