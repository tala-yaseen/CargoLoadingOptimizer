"""Greedy baseline: load packages by value per kg until the truck is full."""

from cargo_optimizer.config import ExperimentConfig
from cargo_optimizer.data import Package


def solve_greedy(packages: list[Package], config: ExperimentConfig) -> list[Package]:
    """Take packages in order of value per kg, skipping any that no longer fit."""
    by_ratio = sorted(packages, key=lambda package: package.value / package.weight_kg, reverse=True)

    selected: list[Package] = []
    remaining = config.capacity
    for package in by_ratio:
        if package.weight_kg <= remaining:
            selected.append(package)
            remaining -= package.weight_kg
    return selected
