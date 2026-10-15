"""Sweep expansion: every combination of the listed values, for each base experiment."""

from pathlib import Path

import pytest

from cargo_optimizer.config import load_experiments

YAML = """
defaults: {method: cpsat, capacity: 1000, trucks: 1, should_include: ignore, should_include_penalty: 0,
           value_weight: 1, priority_weight: 0, num_workers: 8, time_limit_seconds: 60, random_seed: 0,
           symmetry_breaking: false, relative_gap_limit: 0, presolve: true,
           incompatible: false, dependency: false, category_rules: []}
experiments:
  base_a: {}
  base_b: {incompatible: true}
sweeps:
  grid:
    base: [base_a, base_b]
    should_include: [ignore, hard]
    priority_weight: [0, 50, 150]
"""


def _load(tmp_path: Path, text: str) -> dict:
    config_file = tmp_path / "experiments.yaml"
    config_file.write_text(text)
    return load_experiments(config_file)


def test_sweep_creates_every_combination_for_every_base(tmp_path: Path):
    configs = _load(tmp_path, YAML)
    sweep_runs = [name for name in configs if name.startswith("grid__")]

    assert len(sweep_runs) == 2 * 2 * 3


def test_sweep_run_keeps_base_settings_and_applies_swept_values(tmp_path: Path):
    config = _load(tmp_path, YAML)["grid__base_b__should_include=hard__priority_weight=150"]

    assert config.incompatible is True
    assert config.should_include == "hard"
    assert config.priority_weight == 150


def test_sweep_with_unknown_base_is_rejected(tmp_path: Path):
    with pytest.raises(ValueError, match="unknown: \\['missing'\\]"):
        _load(tmp_path, YAML.replace("base: [base_a, base_b]", "base: [base_a, missing]"))


def test_sweep_values_are_validated_like_experiments(tmp_path: Path):
    with pytest.raises(ValueError, match="priority_weight"):
        _load(tmp_path, YAML.replace("priority_weight: [0, 50, 150]", "priority_weight: [0, -5]"))


def test_sweep_values_can_be_labelled(tmp_path: Path):
    text = YAML.replace(
        "    priority_weight: [0, 50, 150]\n",
        "    category_rules:\n      none: []\n      furniture_max: [{category: Furniture, at_most: 3}]\n",
    )
    configs = _load(tmp_path, text)

    config = configs["grid__base_a__should_include=ignore__category_rules=furniture_max"]
    assert [rule.label for rule in config.category_rules] == ["Furniture at_most 3 (hard)"]
