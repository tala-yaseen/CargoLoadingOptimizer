"""Load experiment settings from experiments.yaml."""

from dataclasses import dataclass, fields
from pathlib import Path

import yaml

METHODS = ("cpsat", "greedy")


@dataclass(frozen=True)
class ExperimentConfig:
    name: str
    method: str
    capacity: int


def load_experiments(path: Path) -> dict[str, ExperimentConfig]:
    """Read every experiment in the YAML file, each merged over the defaults."""
    with path.open(encoding="utf-8") as file:
        content = yaml.safe_load(file)

    defaults = content["defaults"]
    return {
        name: _build_config(name, {**defaults, **(overrides or {})})
        for name, overrides in content["experiments"].items()
    }


def _build_config(name: str, settings: dict) -> ExperimentConfig:
    """Turn one experiment's settings into an ExperimentConfig, rejecting typos and bad values."""
    expected = {field.name for field in fields(ExperimentConfig)} - {"name"}

    unknown = settings.keys() - expected
    if unknown:
        raise ValueError(f"experiment {name!r}: unknown settings {sorted(unknown)}")
    missing = expected - settings.keys()
    if missing:
        raise ValueError(f"experiment {name!r}: missing settings {sorted(missing)}")

    if settings["method"] not in METHODS:
        raise ValueError(f"experiment {name!r}: method must be one of {METHODS}, got {settings['method']!r}")
    if settings["capacity"] <= 0:
        raise ValueError(f"experiment {name!r}: capacity must be positive, got {settings['capacity']}")

    return ExperimentConfig(name=name, **settings)
