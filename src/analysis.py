from __future__ import annotations

import pandas as pd


def sku_performance(df: pd.DataFrame) -> pd.DataFrame:
    """Return SKU-level revenue, fee, and profit performance."""
    if "sku" not in df.columns:
        return pd.DataFrame()

    # Filter out rows without a valid SKU (exclude non-product transactions)
    df_with_sku = df[df["sku"].notna() & (df["sku"] != "")]
    if len(df_with_sku) == 0:
        return pd.DataFrame()

    metrics = ["gross_revenue", "total_fees", "net_profit", "quantity"]
    present = [m for m in metrics if m in df.columns]
    if not present:
        return pd.DataFrame()

    grouped = df_with_sku.groupby("sku")[present].sum().reset_index()
    if "gross_revenue" in grouped.columns and "net_profit" in grouped.columns:
        grouped["margin_pct"] = (
            grouped["net_profit"] / grouped["gross_revenue"]
        ).replace([float("inf"), float("-inf")], pd.NA) * 100
    return grouped.sort_values("gross_revenue", ascending=False, na_position="last")


def time_series_performance(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate daily performance over time."""
    date_col = "date"
    if date_col not in df.columns:
        return pd.DataFrame()

    metrics = ["gross_revenue", "total_fees", "net_profit", "quantity"]
    present = [m for m in metrics if m in df.columns]
    if not present:
        return pd.DataFrame()

    return (
        df.groupby(date_col, dropna=False)[present]
        .sum()
        .reset_index()
        .sort_values(date_col)
    )


def geographic_performance(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate performance by state/region."""
    state_col = "order_state"
    if state_col not in df.columns:
        return pd.DataFrame()

    metrics = ["gross_revenue", "total_fees", "net_profit", "quantity"]
    present = [m for m in metrics if m in df.columns]
    if not present:
        return pd.DataFrame()

    output = df.groupby(state_col, dropna=False)[present].sum().reset_index()
    if "gross_revenue" in output.columns and "net_profit" in output.columns:
        output["margin_pct"] = (output["net_profit"] / output["gross_revenue"]).replace(
            [float("inf"), float("-inf")], pd.NA
        ) * 100
    return output.sort_values("net_profit", ascending=False, na_position="last")


def fee_analysis(df: pd.DataFrame) -> pd.DataFrame:
    """Break down fee structure and fee ratio."""
    fee_cols = [
        c
        for c in ["selling_fees", "fba_fees", "other_transaction_fees", "total_fees"]
        if c in df.columns
    ]
    if not fee_cols:
        return pd.DataFrame()

    summary = pd.DataFrame(
        {
            "metric": fee_cols,
            "total_amount": [df[c].sum() for c in fee_cols],
        }
    )
    gross = df["gross_revenue"].sum() if "gross_revenue" in df.columns else 0
    summary["pct_of_gross_revenue"] = (
        (summary["total_amount"] / gross * 100) if gross else pd.NA
    )
    return summary
