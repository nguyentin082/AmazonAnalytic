from __future__ import annotations

from src.analysis import (
    fee_analysis,
    geographic_performance,
    sku_performance,
    time_series_performance,
)
from src.data.load_data import basic_data_profile, load_all_csv
from src.data.preprocess import clean_settlement_data, standardize_columns
from src.data.validation import validate_settlement_schema
from src.export import export_dataframe, export_insights
from src.features.engineering import (
    add_financial_metrics,
    add_time_features,
    aggregate_order_level,
)
from src.insights import extract_key_insights
from src.report import generate_pdf_report


def main() -> None:
    # 1) Load + validate raw data
    raw_df = load_all_csv("data")
    raw_df = standardize_columns(raw_df)
    validation = validate_settlement_schema(raw_df)
    validation.raise_if_invalid()

    profile = basic_data_profile(raw_df)
    print(f"Rows: {profile['rows']:,}")
    print(f"Columns: {profile['columns']:,}")

    # 2) Clean data
    clean_df = clean_settlement_data(raw_df)
    clean_df.to_csv("data/processed/clean.csv", index=False)

    # 3) Feature engineering
    feat_df = add_financial_metrics(clean_df)
    feat_df = add_time_features(feat_df)
    order_df = aggregate_order_level(feat_df)

    # 4) Analysis
    sku_df = sku_performance(feat_df)
    ts_df = time_series_performance(feat_df)
    geo_df = geographic_performance(feat_df)
    fee_df = fee_analysis(feat_df)

    # 5) Insight extraction
    insights = extract_key_insights(sku_df=sku_df, geo_df=geo_df, ts_df=ts_df)

    # 6) Export
    export_dataframe(sku_df, "outputs/sku_performance.csv")
    export_dataframe(ts_df, "outputs/daily_report.csv")
    export_dataframe(geo_df, "outputs/geographic_performance.csv")
    export_dataframe(fee_df, "outputs/fee_breakdown.csv")
    export_dataframe(order_df, "outputs/order_level_report.csv")
    export_insights(insights, output_dir="outputs")
    pdf_path = generate_pdf_report(
        raw_df=raw_df,
        clean_df=clean_df,
        feat_df=feat_df,
        sku_df=sku_df,
        ts_df=ts_df,
        geo_df=geo_df,
        fee_df=fee_df,
        insights=insights,
        output_path="outputs/amazon_settlement_report.pdf",
    )

    print("Pipeline done. Clean data, outputs, and PDF report were exported.")
    print(f"PDF report: {pdf_path}")


if __name__ == "__main__":
    main()
