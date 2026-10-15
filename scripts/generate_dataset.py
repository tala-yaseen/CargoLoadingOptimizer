"""Generate a random package dataset with the same columns as data/packages.csv.

Usage:  uv run python scripts/generate_dataset.py --size 10000 [--seed 42] [--output data/random_10000.csv]

The same size and seed always produce the same file.
"""

import argparse
import csv
import random
from pathlib import Path

from cargo_optimizer.data import CATEGORIES, PRIORITIES, REQUIRED_COLUMNS

PROJECT_ROOT = Path(__file__).resolve().parents[1]

WEIGHT_KG = (5, 400)
VALUE_PER_KG = (1.0, 10.0)  # value = weight * a random value per kg, so heavier packages tend to be worth more
SHOULD_INCLUDED_SHARE = 0.18

# Shares observed in data/packages.csv, so random datasets keep a similar mix.
PRIORITY_SHARES = {"Critical": 0.07, "High": 0.22, "Normal": 0.44, "Low": 0.27}
CATEGORY_SHARES = {"Electronics": 0.22, "Equipment": 0.20, "Food": 0.27, "Furniture": 0.16, "Medical": 0.15}


def generate_packages(size: int, seed: int) -> list[dict]:
    """Rows for `size` random packages with IDs P000001, P000002, ..."""
    rng = random.Random(seed)
    rows = []
    for number in range(1, size + 1):
        weight = rng.randint(*WEIGHT_KG)
        rows.append({
            "package_id": f"P{number:06d}",
            "weight_kg": weight,
            "value": max(1, round(weight * rng.uniform(*VALUE_PER_KG))),
            "priority": rng.choices(PRIORITIES, weights=[PRIORITY_SHARES[p] for p in PRIORITIES])[0],
            "category": rng.choices(CATEGORIES, weights=[CATEGORY_SHARES[c] for c in CATEGORIES])[0],
            "should_included": rng.random() < SHOULD_INCLUDED_SHARE,
        })
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a random package dataset.")
    parser.add_argument("--size", type=int, required=True, help="number of packages")
    parser.add_argument("--seed", type=int, default=42, help="random seed (default: 42)")
    parser.add_argument("--output", type=Path, help="CSV path (default: data/random_<size>.csv)")
    args = parser.parse_args()

    output = args.output or PROJECT_ROOT / "data" / f"random_{args.size}.csv"
    with output.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=REQUIRED_COLUMNS)
        writer.writeheader()
        writer.writerows(generate_packages(args.size, args.seed))
    print(f"Wrote {args.size} packages to {output}")


if __name__ == "__main__":
    main()
