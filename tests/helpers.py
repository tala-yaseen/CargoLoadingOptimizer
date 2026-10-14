"""Shared builders so each test states only the settings it cares about."""

from dataclasses import replace

from cargo_optimizer.config import DatasetConfig, ExperimentConfig, Method, ShouldInclude

BASE_CONFIG = ExperimentConfig(
    name="test",
    method=Method.CPSAT,
    capacity=10,
    should_include=ShouldInclude.IGNORE,
    priority_weight=0,
    incompatible=False,
    dependency=False,
    category_rules=(),
)

NO_RULES = DatasetConfig(name="test", path="unused.csv", incompatible_pairs=(), dependencies=())


def make_config(**overrides) -> ExperimentConfig:
    """BASE_CONFIG with only the given settings changed, e.g. make_config(capacity=5)."""
    return replace(BASE_CONFIG, **overrides)


def make_dataset(**overrides) -> DatasetConfig:
    """NO_RULES with only the given rule IDs set, e.g. make_dataset(dependencies=(("A", "B"),))."""
    return replace(NO_RULES, **overrides)
