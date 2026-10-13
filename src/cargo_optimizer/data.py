"""Load and validate the package dataset."""

import csv
from dataclasses import dataclass
from pathlib import Path

PRIORITIES = ("Critical", "High", "Normal", "Low")
CATEGORIES = ("Electronics", "Equipment", "Food", "Furniture", "Medical")
REQUIRED_COLUMNS = ("package_id", "weight_kg", "value", "priority", "category", "should_included")


@dataclass(frozen=True)
class Package:
    package_id: str
    weight_kg: int
    value: int
    priority: str
    category: str
    should_included: bool


def load_packages(path: Path) -> list[Package]:
    """Read packages from a CSV file; raise ValueError listing every problem found."""
    with path.open(newline="", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)

        missing = [column for column in REQUIRED_COLUMNS if column not in (reader.fieldnames or [])]
        if missing:
            raise ValueError(f"{path}: missing columns {missing}")

        packages: list[Package] = []
        errors: list[str] = []
        for line_number, row in enumerate(reader, start=2):
            row = {key: value.strip() for key, value in row.items()}
            if row["priority"] not in PRIORITIES:
                errors.append(f"line {line_number}: unknown priority {row['priority']!r}")
            if row["category"] not in CATEGORIES:
                errors.append(f"line {line_number}: unknown category {row['category']!r}")
            packages.append(
                Package(
                    package_id=row["package_id"],
                    weight_kg=int(row["weight_kg"]),
                    value=int(row["value"]),
                    priority=row["priority"],
                    category=row["category"],
                    should_included=row["should_included"] == "True",
                )
            )

    if errors:
        raise ValueError(f"{path}: invalid data\n" + "\n".join(errors))
    return packages
