"""Load experiment settings from experiments.yaml."""

from dataclasses import asdict, dataclass, fields
from enum import StrEnum
from pathlib import Path

import yaml

from cargo_optimizer.data import CATEGORIES


class Method(StrEnum):
    CPSAT = "cpsat"
    GREEDY = "greedy"


class ShouldInclude(StrEnum):
    IGNORE = "ignore"  # Part 1: the column is not used
    HARD = "hard"      # Part 2: every should_included package must be loaded


@dataclass(frozen=True)
class CategoryRule:
    """A limit on how many packages of one category are loaded: at least or at most `count`.

    Without a penalty the rule is hard; with one it is soft and each package beyond the bound costs `penalty`.
    """
    category: str
    direction: str  # "at_least" or "at_most"
    count: int
    penalty: int | None = None

    @property
    def is_soft(self) -> bool:
        return self.penalty is not None

    @property
    def label(self) -> str:
        strictness = f"soft, penalty {self.penalty}" if self.is_soft else "hard"
        return f"{self.category} {self.direction} {self.count} ({strictness})"

    def to_dict(self) -> dict:
        """The rule as written in the YAML file."""
        rule = {"category": self.category, self.direction: self.count}
        if self.is_soft:
            rule["penalty"] = self.penalty
        return rule


@dataclass(frozen=True)
class ExperimentConfig:
    name: str
    method: Method
    capacity: int
    should_include: ShouldInclude
    priority_weight: int
    incompatible: bool
    dependency: bool
    category_rules: tuple[CategoryRule, ...]

    def to_dict(self) -> dict:
        """Plain values only (enums become their text), ready to save as YAML or JSON."""
        settings = {key: str(value) if isinstance(value, StrEnum) else value for key, value in asdict(self).items()}
        settings["category_rules"] = [rule.to_dict() for rule in self.category_rules]
        return settings


@dataclass(frozen=True)
class DatasetConfig:
    """A package file plus the package IDs its rules refer to (IDs differ between datasets)."""
    name: str
    path: str
    incompatible_pairs: tuple[tuple[str, str], ...]
    dependencies: tuple[tuple[str, str], ...]  # (dependent, required): loading the first requires the second

    def package_ids(self) -> set[str]:
        return {package_id for pair in self.incompatible_pairs + self.dependencies for package_id in pair}

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "path": self.path,
            "incompatible_pairs": [list(pair) for pair in self.incompatible_pairs],
            "dependencies": [list(pair) for pair in self.dependencies],
        }


def load_datasets(path: Path) -> dict[str, DatasetConfig]:
    """Read the `datasets` section of the YAML file."""
    with path.open(encoding="utf-8") as file:
        content = yaml.safe_load(file)

    datasets = {}
    for name, settings in content["datasets"].items():
        unknown = settings.keys() - {"path", "incompatible_pairs", "dependencies"}
        if unknown:
            raise ValueError(f"dataset {name!r}: unknown settings {sorted(unknown)}")
        datasets[name] = DatasetConfig(
            name=name,
            path=settings["path"],
            incompatible_pairs=_parse_pairs(name, settings, "incompatible_pairs"),
            dependencies=_parse_pairs(name, settings, "dependencies"),
        )
    return datasets


def _parse_pairs(name: str, settings: dict, key: str) -> tuple[tuple[str, str], ...]:
    """Read a list of [id, id] pairs from a dataset entry; a missing key means no pairs."""
    pairs = tuple(tuple(pair) for pair in settings.get(key, []))
    if any(len(pair) != 2 for pair in pairs):
        raise ValueError(f"dataset {name!r}: every entry in {key} needs exactly 2 package IDs")
    return pairs


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
    for flag in ("incompatible", "dependency"):
        if not isinstance(settings[flag], bool):
            raise ValueError(f"experiment {name!r}: {flag} must be true or false, got {settings[flag]!r}")

    return ExperimentConfig(
        name=name,
        method=_parse_enum(name, "method", settings["method"], Method),
        capacity=settings["capacity"],
        should_include=_parse_enum(name, "should_include", settings["should_include"], ShouldInclude),
        priority_weight=settings["priority_weight"],
        incompatible=settings["incompatible"],
        dependency=settings["dependency"],
        category_rules=tuple(_parse_category_rule(name, rule) for rule in settings["category_rules"]),
    )


def _parse_category_rule(name: str, rule: dict) -> CategoryRule:
    """Read e.g. {category: Medical, at_least: 2, penalty: 150}; exactly one of at_least / at_most."""
    unknown = rule.keys() - {"category", "at_least", "at_most", "penalty"}
    if unknown:
        raise ValueError(f"experiment {name!r}: unknown keys {sorted(unknown)} in category rule {rule}")
    if rule.get("category") not in CATEGORIES:
        raise ValueError(f"experiment {name!r}: unknown category {rule.get('category')!r} in category rule {rule}")
    directions = [key for key in ("at_least", "at_most") if key in rule]
    if len(directions) != 1:
        raise ValueError(f"experiment {name!r}: category rule {rule} needs exactly one of at_least / at_most")
    direction = directions[0]
    for key in (direction, "penalty"):
        value = rule.get(key, 0)
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise ValueError(f"experiment {name!r}: {key} in category rule {rule} must be a whole number >= 0")
    return CategoryRule(rule["category"], direction, rule[direction], rule.get("penalty"))


def _parse_enum[E: StrEnum](name: str, setting: str, value: str, enum: type[E]) -> E:
    """Convert a YAML text value into its enum member, with a clear error for unknown values."""
    try:
        return enum(value)
    except ValueError:
        allowed = [member.value for member in enum]
        raise ValueError(f"experiment {name!r}: {setting} must be one of {allowed}, got {value!r}") from None
