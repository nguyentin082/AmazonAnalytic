from __future__ import annotations

import pandas as pd


def standardize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize column names for stable downstream usage."""
    result = df.copy()
    result.columns = (
        result.columns.str.strip()
        .str.lower()
        .str.replace(" ", "_", regex=False)
        .str.replace("-", "_", regex=False)
        .str.replace("/", "_", regex=False)
        .str.replace("(", "", regex=False)
        .str.replace(")", "", regex=False)
    )
    return result


def trim_text_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Strip whitespace on object columns."""
    result = df.copy()
    for col in result.select_dtypes(include=["object", "string"]).columns:
        result[col] = (
            result[col]
            .astype("string")
            .str.replace(r"\s+", " ", regex=True)
            .str.strip()
        )
    return result


def parse_datetime_columns(df: pd.DataFrame, column: str = "date_time") -> pd.DataFrame:
    """Parse Amazon date/time strings to datetime."""
    result = df.copy()
    if column not in result.columns:
        return result

    series = result[column].astype("string")
    # Remove trailing timezone abbreviations like PST/PDT for stable parsing.
    series = series.str.replace(r"\s[A-Z]{3}$", "", regex=True)
    result[column] = pd.to_datetime(
        series, errors="coerce", format="%b %d, %Y %I:%M:%S %p"
    )
    return result


def convert_numeric_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Convert quantity and financial columns to numeric values."""
    result = df.copy()
    numeric_candidates = [
        "quantity",
        "product_sales",
        "product_sales_tax",
        "shipping_credits",
        "shipping_credits_tax",
        "gift_wrap_credits",
        "giftwrap_credits_tax",
        "regulatory_fee",
        "tax_on_regulatory_fee",
        "promotional_rebates",
        "promotional_rebates_tax",
        "marketplace_withheld_tax",
        "selling_fees",
        "fba_fees",
        "other_transaction_fees",
        "other",
        "total",
    ]

    for col in numeric_candidates:
        if col in result.columns:
            cleaned = (
                result[col]
                .astype("string")
                .str.replace("$", "", regex=False)
                .str.replace(",", "", regex=False)
            )
            result[col] = pd.to_numeric(cleaned, errors="coerce")
    return result


def filter_transaction_types(
    df: pd.DataFrame, keep_types: list[str] | None = None
) -> pd.DataFrame:
    """Keep relevant transaction types for order and fee analysis."""
    result = df.copy()
    if "type" not in result.columns:
        return result

    allowed = keep_types or ["Order", "Refund", "Adjustment", "Service Fee"]
    return result[result["type"].astype("string").isin(allowed)].copy()


def clean_settlement_data(df: pd.DataFrame) -> pd.DataFrame:
    """Run full cleaning pipeline for settlement data."""
    result = standardize_columns(df)
    result = trim_text_columns(result)
    result = parse_datetime_columns(result, column="date_time")
    result = convert_numeric_columns(result)
    result = filter_transaction_types(result)
    return result
