from __future__ import annotations

import warnings
from pathlib import Path

import pandas as pd

from src.data.load_data import load_all_csv
from src.data.preprocess import clean_settlement_data, standardize_columns
from src.data.validation import validate_settlement_schema


def run_cleaning_pipeline(
    data_dir: str | Path = "data", output_path: str | Path = "data/processed/clean.csv"
) -> pd.DataFrame:
    """Load raw settlement files, clean data, and save clean dataset."""
    raw_df = load_all_csv(data_dir)
    raw_schema_df = standardize_columns(raw_df)

    validation = validate_settlement_schema(raw_schema_df)
    validation.raise_if_invalid()

    clean_df = clean_settlement_data(raw_df)

    if (
        validation.parseable_datetime_ratio is not None
        and validation.parseable_datetime_ratio < 0.8
    ):
        warnings.warn(
            f"Datetime parseable ratio is low: {validation.parseable_datetime_ratio:.2%}",
            stacklevel=2,
        )

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    clean_df.to_csv(out, index=False)
    return clean_df
