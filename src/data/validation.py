from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

import pandas as pd


DEFAULT_REQUIRED_COLUMNS = [
    "date_time",
    "settlement_id",
    "type",
    "sku",
    "quantity",
    "marketplace",
    "account_type",
    "fulfillment",
    "product_sales",
]


@dataclass
class ValidationResult:
    """Container for schema validation issues."""

    missing_columns: list[str] = field(default_factory=list)
    empty_columns: list[str] = field(default_factory=list)
    duplicate_columns: list[str] = field(default_factory=list)
    parseable_datetime_ratio: float | None = None

    @property
    def is_valid(self) -> bool:
        return not self.missing_columns and not self.duplicate_columns

    def raise_if_invalid(self) -> None:
        if self.is_valid:
            return

        messages = []
        if self.missing_columns:
            messages.append(f"Missing columns: {', '.join(self.missing_columns)}")
        if self.duplicate_columns:
            messages.append(f"Duplicate columns: {', '.join(self.duplicate_columns)}")
        raise ValueError("Settlement data validation failed: " + " | ".join(messages))


def validate_settlement_schema(
    df: pd.DataFrame,
    required_columns: Iterable[str] | None = None,
    datetime_column: str = "date_time",
    minimum_datetime_ratio: float = 0.8,
) -> ValidationResult:
    """Validate key settlement schema expectations.

    This is intentionally light-weight: it checks for required columns, duplicate
    names, and whether the datetime column is parseable enough for time-series work.
    """
    required = list(required_columns or DEFAULT_REQUIRED_COLUMNS)
    result = ValidationResult()

    result.missing_columns = [column for column in required if column not in df.columns]
    result.duplicate_columns = df.columns[df.columns.duplicated()].tolist()

    if datetime_column in df.columns:
        series = df[datetime_column].astype("string")
        series = series.str.replace(r"\s[A-Z]{3}$", "", regex=True)
        parsed = pd.to_datetime(
            series,
            errors="coerce",
            format="%b %d, %Y %I:%M:%S %p",
        )
        valid_ratio = float(parsed.notna().mean()) if len(parsed) else 0.0
        result.parseable_datetime_ratio = valid_ratio
        if valid_ratio < minimum_datetime_ratio:
            result.empty_columns.append(
                f"{datetime_column} parseable ratio {valid_ratio:.2%} below threshold {minimum_datetime_ratio:.2%}"
            )
    else:
        result.empty_columns.append(f"Missing datetime column: {datetime_column}")

    return result
