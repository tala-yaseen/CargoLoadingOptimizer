"""Load experiment settings from experiments.yaml."""

from dataclasses import asdict, dataclass, fields
from enum import StrEnum
from itertools import product
from pathlib import Path

import yaml

from cargo_optimizer.data import CATEGORIES


class Method(StrEnum):
    CPSAT = "cpsat"
    GREEDY = "greedy"


class ShouldInclude(StrEnum):
    IGNORE = "ignore"  # Part 1: the column is not used
    HARD = "hard"      # Part 2: every should_included package must be loaded
    SOFT = "soft"      # Part 5/6: each should_included package left behind costs should_include_penalty


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
    capacity: int | str  # kg per truck, or a share of the dataset's total weight such as "25%"
    trucks: int
    should_include: ShouldInclude
    should_include_penalty: int  # used when should_include is soft
    priority_weight: int
    incompatible: bool
    dependency: bool
    category_rules: tuple[CategoryRule, ...]

    def capacity_kg(self, total_weight_kg: int) -> int:
        """Capacity in kg: as given, or the given percentage of all packages' total weight."""
        if isinstance(self.capacity, int):
            return self.capacity
        return round(total_weight_kg * float(self.capacity.rstrip("%")) / 100)

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
    """Read every experiment in the YAML file, each merged over the defaults, plus every sweep combination."""
    with path.open(encoding="utf-8") as file:
        content = yaml.safe_load(file)

    defaults = content["defaults"]
    experiments = {name: overrides or {} for name, overrides in content["experiments"].items()}
    configs = {name: _build_config(name, {**defaults, **overrides}) for name, overrides in experiments.items()}
    for sweep_name, sweep in (content.get("sweeps") or {}).items():
        for name, settings in _expand_sweep(sweep_name, sweep, defaults, experiments).items():
            configs[name] = _build_config(name, settings)
    return configs


def _expand_sweep(sweep_name: str, sweep: dict, defaults: dict, experiments: dict) -> dict[str, dict]:
    """Every combination of a sweep: each base experiment with each mix of the listed setting values.

    The name records the base and the swept values, e.g. all_cases__part1__should_include=hard__priority_weight=50.
    """
    bases = sweep.get("base", [])
    unknown_bases = [base for base in bases if base not in experiments]
    if not bases or unknown_bases:
        raise ValueError(f"sweep {sweep_name!r}: base must list existing experiments, unknown: {unknown_bases}")
    swept = {key: values for key, values in sweep.items() if key != "base"}
    not_lists = [key for key, values in swept.items() if not isinstance(values, list)]
    if not_lists:
        raise ValueError(f"sweep {sweep_name!r}: values must be lists, check {not_lists}")

    combinations = {}
    for base in bases:
        for values in product(*swept.values()):
            choice = dict(zip(swept, values))
            name = "__".join([sweep_name, base, *(f"{key}={value}" for key, value in choice.items())])
            combinations[name] = {**defaults, **experiments[base], **choice}
    return combinations


def _build_config(name: str, settings: dict) -> ExperimentConfig:
    """Turn one experiment's settings into an ExperimentConfig, rejecting typos and bad values."""
    expected = {field.name for field in fields(ExperimentConfig)} - {"name"}

    unknown = settings.keys() - expected
    if unknown:
        raise ValueError(f"experiment {name!r}: unknown settings {sorted(unknown)}")
    missing = expected - settings.keys()
    if missing:
        raise ValueError(f"experiment {name!r}: missing settings {sorted(missing)}")

    _check_capacity(name, settings["capacity"])
    for setting, smallest in (("trucks", 1), ("should_include_penalty", 0)):
        value = settings[setting]
        if not isinstance(value, int) or isinstance(value, bool) or value < smallest:
            raise ValueError(f"experiment {name!r}: {setting} must be a whole number >= {smallest}, got {value!r}")
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
        trucks=settings["trucks"],
        should_include=_parse_enum(name, "should_include", settings["should_include"], ShouldInclude),
        should_include_penalty=settings["should_include_penalty"],
        priority_weight=settings["priority_weight"],
        incompatible=settings["incompatible"],
        dependency=settings["dependency"],
        category_rules=tuple(_parse_category_rule(name, rule) for rule in settings["category_rules"]),
    )


def _check_capacity(name: str, capacity: int | str) -> None:
    """Capacity is a positive number of kg, or a percentage of total weight between 0 and 100, e.g. "25%"."""
    if isinstance(capacity, int) and not isinstance(capacity, bool) and capacity > 0:
        return
    if isinstance(capacity, str) and capacity.endswith("%"):
        try:
            if 0 < float(capacity[:-1]) <= 100:
                return
        except ValueError:
            pass
    raise ValueError(f"experiment {name!r}: capacity must be kg > 0 or a percentage like '25%', got {capacity!r}")


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
