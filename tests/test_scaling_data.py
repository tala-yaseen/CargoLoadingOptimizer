"""Capacity as a share of total weight, and the random dataset generator."""

import importlib.util
from pathlib import Path

import pytest

from cargo_optimizer.config import _build_config
from cargo_optimizer.data import CATEGORIES, PRIORITIES
from helpers import BASE_CONFIG, make_config

GENERATOR_PATH = Path(__file__).resolve().parents[1] / "scripts" / "generate_dataset.py"
_spec = importlib.util.spec_from_file_location("generate_dataset", GENERATOR_PATH)
generate_dataset = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(generate_dataset)


@pytest.mark.parametrize(("capacity", "expected_kg"), [(1000, 1000), ("25%", 50_000), ("0.5%", 1_000)])
def test_capacity_in_kg_or_as_share_of_total_weight(capacity, expected_kg):
    assert make_config(capacity=capacity).capacity_kg(total_weight_kg=200_000) == expected_kg


@pytest.mark.parametrize("capacity", [0, -5, "0%", "150%", "lots", "25"])
def test_invalid_capacity_is_rejected(capacity):
    settings = {**BASE_CONFIG.to_dict(), "capacity": capacity}
    del settings["name"]

    with pytest.raises(ValueError, match="capacity"):
        _build_config("test", settings)


def test_generator_is_repeatable_and_valid():
    first = generate_dataset.generate_packages(size=200, seed=7)

    assert first == generate_dataset.generate_packages(size=200, seed=7)
    assert first != generate_dataset.generate_packages(size=200, seed=8)
    assert [row["package_id"] for row in first[:2]] == ["P000001", "P000002"]
    assert all(5 <= row["weight_kg"] <= 400 for row in first)
    assert all(row["weight_kg"] <= row["value"] <= 10 * row["weight_kg"] for row in first)
    assert {row["priority"] for row in first} <= set(PRIORITIES)
    assert {row["category"] for row in first} <= set(CATEGORIES)
