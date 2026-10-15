"""Shared builders so each test states only the settings it cares about."""

from dataclasses import replace

from cargo_optimizer.config import DatasetConfig, ExperimentConfig, Method, ShouldInclude

BASE_CONFIG = ExperimentConfig(
    name="test",
    method=Method.CPSAT,
    capacity=10,
    trucks=1,
    should_include=ShouldInclude.IGNORE,
    should_include_penalty=0,
    value_weight=1,
    priority_weight=0,
    incompatible=False,
    dependency=False,
    category_rules=(),
    num_workers=8,
    time_limit_seconds=60,
    random_seed=0,
    relative_gap_limit=0,
    presolve=True,
    symmetry_breaking=False,
)

NO_RULES = DatasetConfig(name="test", path="unused.csv", incompatible_pairs=(), dependencies=())


def make_config(**overrides) -> ExperimentConfig:
    """BASE_CONFIG with only the given settings changed, e.g. make_config(capacity=5)."""
    return replace(BASE_CONFIG, **overrides)


def make_dataset(**overrides) -> DatasetConfig:
    """NO_RULES with only the given rule IDs set, e.g. make_dataset(dependencies=(("A", "B"),))."""
    return replace(NO_RULES, **overrides)
