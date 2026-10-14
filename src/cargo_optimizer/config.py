"""Load experiment settings from experiments.yaml."""

from dataclasses import asdict, dataclass, fields
from enum import StrEnum
from pathlib import Path

import yaml


class Method(StrEnum):
    CPSAT = "cpsat"
    GREEDY = "greedy"


class ShouldInclude(StrEnum):
    IGNORE = "ignore"  # Part 1: the column is not used
    HARD = "hard"      # Part 2: every should_included package must be loaded


@dataclass(frozen=True)
class ExperimentConfig:
    name: str
    method: Method
    capacity: int
    should_include: ShouldInclude
    priority_weight: int

    def to_dict(self) -> dict:
        """Plain values only (enums become their text), ready to save as YAML or JSON."""
        return {key: str(value) if isinstance(value, StrEnum) else value for key, value in asdict(self).items()}


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

    if settings["capacity"] <= 0:
        raise ValueError(f"experiment {name!r}: capacity must be positive, got {settings['capacity']}")
    if not isinstance(settings["priority_weight"], int) or settings["priority_weight"] < 0:
        raise ValueError(
            f"experiment {name!r}: priority_weight must be a whole number >= 0, got {settings['priority_weight']!r}"
        )

    return ExperimentConfig(
        name=name,
        method=_parse_enum(name, "method", settings["method"], Method),
        capacity=settings["capacity"],
        should_include=_parse_enum(name, "should_include", settings["should_include"], ShouldInclude),
        priority_weight=settings["priority_weight"],
    )


def _parse_enum[E: StrEnum](name: str, setting: str, value: str, enum: type[E]) -> E:
    """Convert a YAML text value into its enum member, with a clear error for unknown values."""
    try:
        return enum(value)
    except ValueError:
        allowed = [member.value for member in enum]
        raise ValueError(f"experiment {name!r}: {setting} must be one of {allowed}, got {value!r}") from None
