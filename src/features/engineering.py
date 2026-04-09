from __future__ import annotations

import pandas as pd


def add_financial_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """Create revenue, fee, profit and margin metrics."""
    result = df.copy()

    revenue_cols = [
        "product_sales",
        "shipping_credits",
        "gift_wrap_credits",
    ]
    fee_cols = [
        "selling_fees",
        "fba_fees",
        "other_transaction_fees",
    ]

    for col in revenue_cols + fee_cols:
        if col not in result.columns:
            result[col] = 0.0

    result["gross_revenue"] = result[revenue_cols].sum(axis=1)
    result["total_fees"] = result[fee_cols].sum(axis=1)
    result["net_profit"] = result["gross_revenue"] - result["total_fees"]
    result["margin_pct"] = (result["net_profit"] / result["gross_revenue"]).replace(
        [float("inf"), float("-inf")], pd.NA
    ) * 100
    return result


def add_time_features(
    df: pd.DataFrame, datetime_col: str = "date_time"
) -> pd.DataFrame:
    """Create day/week/month level time features."""
    result = df.copy()
    if datetime_col not in result.columns:
        return result

    dt = result[datetime_col]
    result["date"] = dt.dt.date
    result["year"] = dt.dt.year
    result["month"] = dt.dt.month
    result["month_name"] = dt.dt.month_name()
    result["week"] = dt.dt.isocalendar().week.astype("Int64")
    result["day_of_week"] = dt.dt.day_name()
    result["hour"] = dt.dt.hour
    return result


def aggregate_order_level(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate transaction rows into order-level metrics."""
    if "order_id" not in df.columns:
        return pd.DataFrame()

    data = df[df["order_id"].notna()].copy()
    if data.empty:
        return pd.DataFrame()

    agg_map = {
        "gross_revenue": "sum",
        "total_fees": "sum",
        "net_profit": "sum",
        "quantity": "sum",
        "sku": "nunique",
    }
    present_map = {k: v for k, v in agg_map.items() if k in data.columns}

    order_df = data.groupby("order_id", dropna=False).agg(present_map).reset_index()
    if "gross_revenue" in order_df.columns and "net_profit" in order_df.columns:
        order_df["margin_pct"] = (
            order_df["net_profit"] / order_df["gross_revenue"]
        ).replace([float("inf"), float("-inf")], pd.NA) * 100
    return order_df
