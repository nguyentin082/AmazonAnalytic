from __future__ import annotations

import pandas as pd


def extract_key_insights(
    sku_df: pd.DataFrame,
    geo_df: pd.DataFrame,
    ts_df: pd.DataFrame,
    margin_threshold: float = 0.0,
    fee_ratio_alert: float = 0.35,
) -> dict[str, pd.DataFrame]:
    """Extract key insight tables required for analyst reporting."""
    insights: dict[str, pd.DataFrame] = {}

    if not sku_df.empty:
        insights["top_sku_by_revenue"] = sku_df.nlargest(10, "gross_revenue")
        if "net_profit" in sku_df.columns:
            insights["top_sku_by_profit"] = sku_df.nlargest(10, "net_profit")
        if "margin_pct" in sku_df.columns:
            insights["low_or_negative_margin_sku"] = sku_df[
                sku_df["margin_pct"] <= margin_threshold
            ].sort_values("margin_pct")
        if "total_fees" in sku_df.columns and "gross_revenue" in sku_df.columns:
            ratio = sku_df["total_fees"] / sku_df["gross_revenue"].replace(0, pd.NA)
            fee_alert = sku_df[ratio >= fee_ratio_alert].copy()
            fee_alert["fee_ratio"] = ratio[ratio >= fee_ratio_alert] * 100
            insights["abnormal_high_fee_sku"] = fee_alert.sort_values(
                "fee_ratio", ascending=False
            )

    if not geo_df.empty and "net_profit" in geo_df.columns:
        insights["top_regions_by_profit"] = geo_df.nlargest(10, "net_profit")

    if not ts_df.empty and "net_profit" in ts_df.columns:
        insights["best_days_by_profit"] = ts_df.nlargest(10, "net_profit")
        insights["worst_days_by_profit"] = ts_df.nsmallest(10, "net_profit")

    return insights
