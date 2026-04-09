from __future__ import annotations

from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.ticker as mtick
import numpy as np
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    Image,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

REPORT_TITLE = "Amazon Settlement Dashboard Report"
PAGE_COLOR = colors.HexColor("#1F3A5F")
ACCENT_COLOR = colors.HexColor("#2E86AB")
ACCENT_2_COLOR = colors.HexColor("#1B998B")
WARN_COLOR = colors.HexColor("#D1495B")
LIGHT_BG = colors.HexColor("#F5F7FA")
BORDER_COLOR = colors.HexColor("#D6DCE5")
TEXT_DARK = colors.HexColor("#233142")
SOFT_TEXT = colors.HexColor("#52616B")


def _numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").fillna(0.0)


def _parse_currency_series(series: pd.Series) -> pd.Series:
    cleaned = (
        series.astype("string")
        .str.replace("$", "", regex=False)
        .str.replace(",", "", regex=False)
    )
    return pd.to_numeric(cleaned, errors="coerce").fillna(0.0)


def _format_money(value: Any) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "N/A"
    return f"${number:,.2f}"


def _format_percent(value: Any) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "N/A"
    return f"{number:,.2f}%"


def _safe_col(df: pd.DataFrame, column: str) -> pd.Series:
    if column in df.columns:
        return _numeric(df[column])
    return pd.Series(0.0, index=df.index)


def _build_styles() -> dict[str, ParagraphStyle]:
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="ReportTitle",
            parent=styles["Title"],
            fontName="Helvetica-Bold",
            fontSize=24,
            leading=30,
            textColor=PAGE_COLOR,
            alignment=TA_CENTER,
            spaceAfter=10,
        )
    )
    styles.add(
        ParagraphStyle(
            name="SectionHeading",
            parent=styles["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=15,
            leading=19,
            textColor=PAGE_COLOR,
            spaceBefore=10,
            spaceAfter=8,
        )
    )
    styles.add(
        ParagraphStyle(
            name="SubHeading",
            parent=styles["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=11.5,
            leading=15,
            textColor=ACCENT_COLOR,
            spaceBefore=7,
            spaceAfter=5,
        )
    )
    styles.add(
        ParagraphStyle(
            name="BodyTextReport",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=9.8,
            leading=13.5,
            textColor=TEXT_DARK,
        )
    )
    styles.add(
        ParagraphStyle(
            name="TableHeaderLabel",
            parent=styles["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=9.2,
            leading=11,
            textColor=colors.white,
        )
    )
    return styles


def _display_col_name(column: str) -> str:
    pretty = column.replace("_", " ").strip().title()
    if column in {
        "gross_revenue",
        "total_expenses",
        "net_income",
        "total_col",
        "total_amount",
        "product_sales",
        "fba_fees",
        "selling_fees",
        "amount",
        "tax_net_diff",
        "product_sales_tax",
        "marketplace_withheld_tax",
        "total",
    }:
        return f"{pretty} (USD)"
    if column in {
        "quantity",
        "sold_qty",
        "refund_qty",
        "sold_quantity",
        "refunded_quantity",
        "net_quantity",
        "transaction_count",
    }:
        return f"{pretty} (Units)"
    if column in {"margin_pct", "gross_margin_pct", "pct_of_fee", "refund_rate_pct"}:
        return f"{pretty} (%)"
    return pretty


def _format_value_by_column(value: Any, column: str) -> str:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return "N/A"

    is_number = isinstance(value, (int, float, np.number))
    if not is_number:
        return str(value)

    number = float(value)
    if column in {
        "quantity",
        "sold_qty",
        "refund_qty",
        "sold_quantity",
        "refunded_quantity",
        "net_quantity",
        "transaction_count",
    }:
        return f"{number:,.0f}"
    if column in {"margin_pct", "gross_margin_pct", "pct_of_fee", "refund_rate_pct"}:
        return _format_percent(number)
    if column in {
        "gross_revenue",
        "total_expenses",
        "net_income",
        "total_col",
        "total_amount",
        "product_sales",
        "fba_fees",
        "selling_fees",
        "amount",
        "tax_net_diff",
        "product_sales_tax",
        "marketplace_withheld_tax",
        "total",
        "order_net_income",
        "refunded_sales",
        "net_sales_after_refund",
    }:
        return _format_money(number)
    return f"{number:,.2f}"


def _header_footer(canvas: Any, doc: Any) -> None:
    canvas.saveState()
    canvas.setFillColor(PAGE_COLOR)
    canvas.setFont("Helvetica-Bold", 9)
    canvas.drawString(doc.leftMargin, A4[1] - 1.1 * cm, REPORT_TITLE)
    canvas.setFont("Helvetica", 8)
    canvas.drawRightString(
        A4[0] - doc.rightMargin,
        A4[1] - 1.1 * cm,
        datetime.now().strftime("%Y-%m-%d"),
    )
    canvas.setStrokeColor(BORDER_COLOR)
    canvas.setLineWidth(0.6)
    canvas.line(
        doc.leftMargin,
        A4[1] - 1.25 * cm,
        A4[0] - doc.rightMargin,
        A4[1] - 1.25 * cm,
    )
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.HexColor("#52616B"))
    canvas.drawRightString(
        A4[0] - doc.rightMargin, 1.0 * cm, f"Page {canvas.getPageNumber()}"
    )
    canvas.restoreState()


def _table_from_dataframe(
    df: pd.DataFrame, styles: dict[str, ParagraphStyle], max_rows: int = 12
) -> Table:
    display_df = df.head(max_rows).copy()
    rows: list[list[Any]] = [
        [
            Paragraph(_display_col_name(str(col)), styles["TableHeaderLabel"])
            for col in display_df.columns
        ]
    ]

    if display_df.empty:
        rows.append([Paragraph("No data available", styles["BodyTextReport"])])
    else:
        for _, row in display_df.iterrows():
            formatted: list[Any] = []
            for col_name, value in zip(display_df.columns, row.tolist()):
                formatted.append(
                    Paragraph(
                        _format_value_by_column(value, str(col_name)),
                        styles["BodyTextReport"],
                    )
                )
            rows.append(formatted)

    table = Table(rows, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), PAGE_COLOR),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8.8),
                ("GRID", (0, 0), (-1, -1), 0.35, BORDER_COLOR),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT_BG]),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return table


def _save_chart(fig: plt.Figure, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=170, bbox_inches="tight")
    plt.close(fig)
    return output_path


def _scaled_image(
    image_path: Path, max_width_cm: float = 17.0, max_height_cm: float = 7.4
) -> Image:
    """Create a ReportLab image that fits within bounds while keeping aspect ratio."""
    image = Image(str(image_path))
    max_w = max_width_cm * cm
    max_h = max_height_cm * cm

    width = float(image.imageWidth)
    height = float(image.imageHeight)
    if width <= 0 or height <= 0:
        image.drawWidth = max_w
        image.drawHeight = max_h
        return image

    scale = min(max_w / width, max_h / height)
    image.drawWidth = width * scale
    image.drawHeight = height * scale
    return image


def _placeholder_chart(output_path: Path, title: str, message: str) -> Path:
    fig, ax = plt.subplots(figsize=(10.8, 5.2))
    ax.axis("off")
    ax.text(0.5, 0.62, title, ha="center", va="center", fontsize=16, fontweight="bold")
    ax.text(0.5, 0.42, message, ha="center", va="center", fontsize=11, color="#555555")
    return _save_chart(fig, output_path)


def _add_month_period(
    df: pd.DataFrame, datetime_col: str = "date_time"
) -> pd.DataFrame:
    result = df.copy()
    if datetime_col not in result.columns:
        result["period"] = pd.NaT
        return result
    dt = pd.to_datetime(result[datetime_col], errors="coerce")
    result["period"] = dt.dt.to_period("M").astype("string")
    return result


def _standardize_type_group(raw_df: pd.DataFrame) -> pd.DataFrame:
    result = raw_df.copy()
    if "type" not in result.columns:
        result["type_group"] = "Unknown"
        return result

    mapping = {
        "Order": "Order",
        "Refund": "Refund",
        "Adjustment": "Adjustment",
        "FBA Inventory Fee": "FBA Inventory Fee",
        "Service Fee": "Service Fee",
        "Transfer": "Transfer",
    }
    result["type_group"] = (
        result["type"]
        .astype("string")
        .map(mapping)
        .fillna(result["type"].astype("string"))
    )
    return result


def _build_monthly_pl(feat_df: pd.DataFrame) -> pd.DataFrame:
    monthly = _add_month_period(feat_df)

    gross_revenue = (
        _safe_col(monthly, "product_sales")
        + _safe_col(monthly, "shipping_credits")
        + _safe_col(monthly, "gift_wrap_credits")
        + _safe_col(monthly, "promotional_rebates")
    )
    total_expenses = (
        _safe_col(monthly, "selling_fees")
        + _safe_col(monthly, "fba_fees")
        + _safe_col(monthly, "other_transaction_fees")
        + _safe_col(monthly, "other")
    )
    net_income = gross_revenue + total_expenses

    monthly["gross_revenue_calc"] = gross_revenue
    monthly["total_expenses_calc"] = total_expenses
    monthly["net_income_calc"] = net_income

    output = (
        monthly.groupby("period", dropna=False)
        .agg(
            gross_revenue=("gross_revenue_calc", "sum"),
            total_expenses=("total_expenses_calc", "sum"),
            net_income=("net_income_calc", "sum"),
            total_col=(
                ("total", "sum")
                if "total" in monthly.columns
                else ("gross_revenue_calc", "sum")
            ),
        )
        .reset_index()
    )
    output["period"] = output["period"].astype("string")
    output = output.sort_values("period")
    output["margin_pct"] = (
        output["net_income"] / output["gross_revenue"].replace(0, np.nan) * 100
    ).fillna(0.0)
    return output


def _sum_money_column(df: pd.DataFrame, column: str) -> float:
    if column not in df.columns:
        return 0.0
    series = df[column]
    if pd.api.types.is_numeric_dtype(series):
        return float(_numeric(series).sum())
    return float(_parse_currency_series(series).sum())


def _build_fee_deep_dive_table(df: pd.DataFrame) -> pd.DataFrame:
    fee_types = ["selling_fees", "fba_fees", "other_transaction_fees", "other"]
    fees = pd.DataFrame(
        {
            "fee_type": fee_types,
            "amount": [_sum_money_column(df, col) for col in fee_types],
        }
    )
    amount_abs_total = fees["amount"].abs().sum()
    fees["pct_of_fee"] = (
        (fees["amount"].abs() / amount_abs_total * 100).fillna(0.0)
        if amount_abs_total
        else 0.0
    )
    return (
        fees.assign(amount_abs=lambda x: x["amount"].abs())
        .sort_values("amount_abs", ascending=False)
        .drop(columns=["amount_abs"])
    )


def _build_report_tables(
    raw_df: pd.DataFrame, clean_df: pd.DataFrame, feat_df: pd.DataFrame
) -> dict[str, pd.DataFrame]:
    tables: dict[str, pd.DataFrame] = {}

    monthly_pl = _build_monthly_pl(feat_df)
    tables["T1 - P&L Summary (Monthly)"] = monthly_pl[
        [
            "period",
            "gross_revenue",
            "total_expenses",
            "net_income",
            "margin_pct",
        ]
    ]

    typed = _standardize_type_group(raw_df)
    typed["total_num"] = (
        _parse_currency_series(typed["total"]) if "total" in typed.columns else 0.0
    )
    tables["T2 - Transaction Type Master Table"] = (
        typed.groupby("type_group", dropna=False, as_index=False)
        .agg(
            transaction_count=("type_group", "size"), total_amount=("total_num", "sum")
        )
        .assign(total_abs=lambda x: x["total_amount"].abs())
        .sort_values(["total_abs", "transaction_count"], ascending=[False, False])
        .drop(columns=["total_abs"])
    )

    sku_base = feat_df.copy()
    if "sku" in sku_base.columns:
        # Profitability view can include all transaction types.
        sku_profitability = (
            sku_base.groupby("sku", dropna=False)
            .agg(
                quantity=(
                    ("quantity", "sum")
                    if "quantity" in sku_base.columns
                    else ("sku", "size")
                ),
                product_sales=(
                    ("product_sales", "sum")
                    if "product_sales" in sku_base.columns
                    else ("sku", "size")
                ),
                gross_revenue=(
                    ("gross_revenue", "sum")
                    if "gross_revenue" in sku_base.columns
                    else ("sku", "size")
                ),
                fba_fees=(
                    ("fba_fees", "sum")
                    if "fba_fees" in sku_base.columns
                    else ("sku", "size")
                ),
                selling_fees=(
                    ("selling_fees", "sum")
                    if "selling_fees" in sku_base.columns
                    else ("sku", "size")
                ),
                net_income=(
                    ("total", "sum")
                    if "total" in sku_base.columns
                    else ("gross_revenue", "sum")
                ),
            )
            .reset_index()
        )
        sku_profitability["gross_margin_pct"] = (
            sku_profitability["net_income"]
            / sku_profitability["gross_revenue"].replace(0, np.nan)
            * 100
        ).fillna(0.0)

        # Bestseller view should represent sold orders only.
        order_only = (
            sku_base[sku_base["type"].astype("string").eq("Order")].copy()
            if "type" in sku_base.columns
            else sku_base.copy()
        )
        refund_only = (
            sku_base[sku_base["type"].astype("string").eq("Refund")].copy()
            if "type" in sku_base.columns
            else pd.DataFrame()
        )

        bestseller_full = (
            order_only.groupby("sku", dropna=False)
            .agg(
                sold_quantity=(
                    ("quantity", "sum")
                    if "quantity" in order_only.columns
                    else ("sku", "size")
                ),
                product_sales=(
                    ("product_sales", "sum")
                    if "product_sales" in order_only.columns
                    else ("sku", "size")
                ),
                gross_revenue=(
                    ("gross_revenue", "sum")
                    if "gross_revenue" in order_only.columns
                    else ("sku", "size")
                ),
                order_net_income=(
                    ("total", "sum")
                    if "total" in order_only.columns
                    else ("gross_revenue", "sum")
                ),
            )
            .reset_index()
        )

        if not refund_only.empty:
            refund_stats = (
                refund_only.groupby("sku", dropna=False)
                .agg(
                    refunded_quantity=("quantity", "sum"),
                    refunded_sales=("product_sales", "sum"),
                )
                .reset_index()
            )
            bestseller_full = bestseller_full.merge(refund_stats, on="sku", how="left")
        else:
            bestseller_full["refunded_quantity"] = 0.0
            bestseller_full["refunded_sales"] = 0.0

        bestseller_full["refunded_quantity"] = (
            bestseller_full["refunded_quantity"].fillna(0.0).abs()
        )
        bestseller_full["refunded_sales"] = (
            bestseller_full["refunded_sales"].fillna(0.0).abs()
        )
        bestseller_full["net_quantity"] = (
            bestseller_full["sold_quantity"] - bestseller_full["refunded_quantity"]
        )
        bestseller_full["net_sales_after_refund"] = (
            bestseller_full["product_sales"] - bestseller_full["refunded_sales"]
        )
        bestseller_full = bestseller_full.sort_values("product_sales", ascending=False)
    else:
        sku_profitability = pd.DataFrame(
            columns=[
                "sku",
                "quantity",
                "product_sales",
                "gross_revenue",
                "fba_fees",
                "selling_fees",
                "net_income",
                "gross_margin_pct",
            ]
        )
        bestseller_full = pd.DataFrame(
            columns=[
                "sku",
                "sold_quantity",
                "product_sales",
                "gross_revenue",
                "order_net_income",
                "refunded_quantity",
                "refunded_sales",
                "net_quantity",
                "net_sales_after_refund",
            ]
        )

    tables["T3 - Top 10 Bestsellers (Revenue & Quantity)"] = bestseller_full.head(10)[
        [
            "sku",
            "product_sales",
            "sold_quantity",
            "refunded_quantity",
            "net_quantity",
            "gross_revenue",
            "order_net_income",
        ]
    ]
    tables["T4 - Worst Performing SKUs"] = sku_profitability.nsmallest(
        10, "net_income"
    )[
        [
            "sku",
            "gross_revenue",
            "fba_fees",
            "selling_fees",
            "net_income",
            "gross_margin_pct",
        ]
    ]
    tables["T5 - SKU Profitability Matrix"] = sku_profitability.sort_values(
        "gross_revenue", ascending=False
    )[
        [
            "sku",
            "product_sales",
            "quantity",
            "gross_revenue",
            "fba_fees",
            "selling_fees",
            "net_income",
            "gross_margin_pct",
        ]
    ]
    # Internal dataset for sales-volume figures, based on order-only logic.
    tables["_T3_FULL_ORDER_ONLY"] = bestseller_full

    adj = clean_df.copy()
    if "type" in adj.columns:
        adj_mask = adj["type"].astype("string").eq("Adjustment")
    else:
        adj_mask = pd.Series(False, index=adj.index)
    desc = (
        adj["description"].astype("string")
        if "description" in adj.columns
        else pd.Series("", index=adj.index)
    )
    reimb_mask = desc.str.contains(
        r"Damaged|Lost|Customer Return", case=False, regex=True, na=False
    )
    reimbursements = adj[adj_mask & reimb_mask].copy()
    if "total" in reimbursements.columns:
        reimbursements = reimbursements.assign(
            total_abs=_safe_col(reimbursements, "total").abs()
        ).sort_values(
            [
                "total_abs",
                "date_time" if "date_time" in reimbursements.columns else "total_abs",
            ],
            ascending=[False, False],
        )
    tables["T6 - Reimbursement Log"] = reimbursements[
        [
            c
            for c in ["date_time", "order_id", "sku", "description", "total"]
            if c in reimbursements.columns
        ]
    ]

    refunds = (
        clean_df[clean_df["type"].astype("string").eq("Refund")].copy()
        if "type" in clean_df.columns
        else pd.DataFrame()
    )
    if "total" in refunds.columns:
        refunds = refunds.assign(
            total_abs=_safe_col(refunds, "total").abs()
        ).sort_values(
            [
                "total_abs",
                "date_time" if "date_time" in refunds.columns else "total_abs",
            ],
            ascending=[False, False],
        )
    tables["T7 - Refund / Return Detail"] = refunds[
        [
            c
            for c in [
                "date_time",
                "order_id",
                "sku",
                "description",
                "quantity",
                "total",
            ]
            if c in refunds.columns
        ]
    ]

    tables["T8 - Fees Deep-Dive"] = _build_fee_deep_dive_table(feat_df)
    tables["T8B - Fees Deep-Dive (All Raw Types)"] = _build_fee_deep_dive_table(raw_df)

    if {"order_state", "order_city"}.issubset(feat_df.columns):
        geo_city = (
            feat_df.groupby(["order_state", "order_city"], dropna=False)
            .agg(
                gross_revenue=("gross_revenue", "sum"),
                quantity=("quantity", "sum"),
                net_income=(
                    ("total", "sum")
                    if "total" in feat_df.columns
                    else ("gross_revenue", "sum")
                ),
            )
            .reset_index()
            .sort_values("gross_revenue", ascending=False)
        )
    else:
        geo_city = pd.DataFrame(
            columns=[
                "order_state",
                "order_city",
                "gross_revenue",
                "quantity",
                "net_income",
            ]
        )
    tables["T9 - Sales by State / City"] = geo_city

    tax_monthly = _add_month_period(feat_df)
    tax_table = (
        tax_monthly.groupby("period", dropna=False)
        .agg(
            product_sales_tax=(
                ("product_sales_tax", "sum")
                if "product_sales_tax" in tax_monthly.columns
                else ("period", "size")
            ),
            marketplace_withheld_tax=(
                ("marketplace_withheld_tax", "sum")
                if "marketplace_withheld_tax" in tax_monthly.columns
                else ("period", "size")
            ),
        )
        .reset_index()
    )
    if (
        "product_sales_tax" in tax_table.columns
        and "marketplace_withheld_tax" in tax_table.columns
    ):
        tax_table["tax_net_diff"] = (
            tax_table["product_sales_tax"] + tax_table["marketplace_withheld_tax"]
        )
    tables["T10 - Tax Collection Summary"] = tax_table.sort_values("period")

    return tables


def _fig1_monthly_net_income(monthly_pl: pd.DataFrame, output_path: Path) -> Path:
    if monthly_pl.empty:
        return _placeholder_chart(
            output_path, "Monthly Net Income Trend", "Insufficient data"
        )
    fig, ax = plt.subplots(figsize=(10.8, 5.2))
    ax.plot(
        monthly_pl["period"],
        _numeric(monthly_pl["net_income"]),
        marker="o",
        linewidth=2.2,
        color="#1B998B",
    )
    ax.set_title("Monthly Net Income Trend")
    ax.set_xlabel("Month")
    ax.set_ylabel("Net Income (USD)")
    ax.tick_params(axis="x", rotation=35)
    ax.grid(alpha=0.25)
    return _save_chart(fig, output_path)


def _fig2_revenue_vs_expenses(monthly_pl: pd.DataFrame, output_path: Path) -> Path:
    if monthly_pl.empty:
        return _placeholder_chart(
            output_path, "Revenue vs Expenses", "Insufficient data"
        )
    x = np.arange(len(monthly_pl))
    revenue = _numeric(monthly_pl["gross_revenue"]).to_numpy()
    expenses = _numeric(monthly_pl["total_expenses"]).abs().to_numpy()
    fig, ax = plt.subplots(figsize=(10.8, 5.2))
    ax.bar(x, revenue, label="Gross Revenue", color="#2E86AB")
    ax.bar(x, expenses, bottom=revenue, label="Total Expenses (abs)", color="#D1495B")
    ax.set_xticks(x)
    ax.set_xticklabels(monthly_pl["period"], rotation=35)
    ax.set_title("Revenue vs Expenses (Stacked)")
    ax.set_ylabel("Amount (USD)")
    ax.legend(frameon=False)
    ax.grid(axis="y", alpha=0.25)
    return _save_chart(fig, output_path)


def _fig3_profit_waterfall(feat_df: pd.DataFrame, output_path: Path) -> Path:
    gross_revenue = (
        _safe_col(feat_df, "product_sales").sum()
        + _safe_col(feat_df, "shipping_credits").sum()
        + _safe_col(feat_df, "gift_wrap_credits").sum()
        + _safe_col(feat_df, "promotional_rebates").sum()
    )
    selling_fee = _safe_col(feat_df, "selling_fees").sum()
    fba_fee = _safe_col(feat_df, "fba_fees").sum()
    refund_impact = (
        _safe_col(feat_df[feat_df["type"].astype("string").eq("Refund")], "total").sum()
        if "type" in feat_df.columns
        else 0.0
    )
    net_income = gross_revenue + selling_fee + fba_fee + refund_impact

    labels = [
        "Gross Revenue",
        "Selling Fees",
        "FBA Fees",
        "Refund Impact",
        "Net Income",
    ]
    values = [gross_revenue, selling_fee, fba_fee, refund_impact, net_income]
    colors_list = ["#2E86AB", "#D1495B", "#D1495B", "#F6AE2D", "#1B998B"]

    fig, ax = plt.subplots(figsize=(11.2, 5.8))
    bars = ax.bar(labels, values, color=colors_list)
    ax.axhline(0, color="#666666", linewidth=0.9)
    ax.set_title("Profit Drivers (Diverging Bar)")
    ax.set_ylabel("Amount (USD)")
    ax.tick_params(axis="x", rotation=18)
    ax.grid(axis="y", alpha=0.22)

    max_abs = max(abs(v) for v in values) if values else 0.0
    offset = max_abs * 0.03 if max_abs else 0.0
    for rect, value in zip(bars, values):
        y = rect.get_height()
        va = "bottom" if value >= 0 else "top"
        text_y = y + offset if value >= 0 else y - offset
        ax.text(
            rect.get_x() + rect.get_width() / 2,
            text_y,
            _format_money(value),
            ha="center",
            va=va,
            fontsize=8.8,
            color="#2B2B2B",
        )

    ax.text(
        0.01,
        0.97,
        "Interpretation: positive bars add profit; negative bars reduce profit.",
        transform=ax.transAxes,
        ha="left",
        va="top",
        fontsize=8.6,
        color="#555555",
    )
    return _save_chart(fig, output_path)


def _fig4_expense_breakdown(feat_df: pd.DataFrame, output_path: Path) -> Path:
    labels = ["Selling Fees", "FBA Fees", "Other Transaction Fees", "Other"]
    values = [
        abs(_safe_col(feat_df, "selling_fees").sum()),
        abs(_safe_col(feat_df, "fba_fees").sum()),
        abs(_safe_col(feat_df, "other_transaction_fees").sum()),
        abs(_safe_col(feat_df, "other").sum()),
    ]
    if np.isclose(sum(values), 0.0):
        return _placeholder_chart(
            output_path, "Expense Breakdown", "No fee values available"
        )

    fig, ax = plt.subplots(figsize=(15.0, 9.6))
    wedges, _, _ = ax.pie(
        values,
        labels=None,
        autopct=lambda pct: f"{pct:.1f}%" if pct >= 4 else "",
        startangle=100,
        pctdistance=0.72,
        wedgeprops={"linewidth": 1, "edgecolor": "white"},
        textprops={"fontsize": 10},
    )
    legend_labels = [
        f"{name}: ${amount:,.2f} ({(amount / sum(values) * 100):.1f}%)"
        for name, amount in zip(labels, values)
    ]
    ax.legend(
        wedges,
        legend_labels,
        loc="center left",
        bbox_to_anchor=(1.0, 0.5),
        frameon=False,
        fontsize=12.5,
    )
    ax.set_title("Expense Breakdown", fontsize=14, fontweight="bold")
    fig.subplots_adjust(right=0.72)
    return _save_chart(fig, output_path)


def _fig5_type_distribution(raw_df: pd.DataFrame, output_path: Path) -> Path:
    typed = _standardize_type_group(raw_df)
    if "total" in typed.columns:
        typed["total_num"] = _parse_currency_series(typed["total"])
        grouped = (
            typed.groupby("type_group", dropna=False)["total_num"]
            .sum()
            .abs()
            .reset_index()
        )
    else:
        grouped = (
            typed.groupby("type_group", dropna=False)
            .size()
            .reset_index(name="total_num")
        )
    if grouped.empty:
        return _placeholder_chart(
            output_path, "Total Type Distribution", "No transaction types"
        )

    grouped = grouped.sort_values("total_num", ascending=False)
    fig, ax = plt.subplots(figsize=(15.0, 9.6))
    wedges, _, autotexts = ax.pie(
        grouped["total_num"],
        labels=None,
        autopct=lambda pct: f"{pct:.1f}%" if pct >= 4 else "",
        startangle=110,
        pctdistance=0.75,
        wedgeprops={"width": 0.42, "edgecolor": "white"},
        textprops={"fontsize": 10},
    )
    legend_labels = [
        f"{name}: ${value:,.2f} ({(value / grouped['total_num'].sum() * 100):.1f}%)"
        for name, value in zip(grouped["type_group"].astype(str), grouped["total_num"])
    ]
    ax.legend(
        wedges,
        legend_labels,
        loc="center left",
        bbox_to_anchor=(1.0, 0.5),
        frameon=False,
        fontsize=12.5,
    )
    for txt in autotexts:
        txt.set_fontsize(9.5)
    ax.set_title("Total Type Distribution (Donut)", fontsize=14, fontweight="bold")
    fig.subplots_adjust(right=0.71)
    return _save_chart(fig, output_path)


def _fig6_top_sku_sales(sku_perf: pd.DataFrame, output_path: Path) -> Path:
    plot_df = (
        sku_perf.nlargest(10, "product_sales") if not sku_perf.empty else pd.DataFrame()
    )
    if plot_df.empty:
        return _placeholder_chart(
            output_path, "Top 10 SKUs by Sales", "No SKU sales data"
        )
    fig, ax = plt.subplots(figsize=(10.8, 5.2))
    plot_df = plot_df.sort_values("product_sales")
    ax.barh(
        plot_df["sku"].astype(str), _numeric(plot_df["product_sales"]), color="#2E86AB"
    )
    ax.set_title("Top 10 SKUs by Sales")
    ax.set_xlabel("Product Sales (USD)")
    ax.set_ylabel("SKU")
    ax.grid(axis="x", alpha=0.25)
    return _save_chart(fig, output_path)


def _fig7_top_sku_volume(sku_perf: pd.DataFrame, output_path: Path) -> Path:
    quantity_col = (
        "sold_quantity" if "sold_quantity" in sku_perf.columns else "quantity"
    )
    plot_df = (
        sku_perf.nlargest(10, quantity_col)
        if not sku_perf.empty and quantity_col in sku_perf.columns
        else pd.DataFrame()
    )
    if plot_df.empty:
        return _placeholder_chart(
            output_path, "Top 10 SKUs by Volume", "No SKU quantity data"
        )
    fig, ax = plt.subplots(figsize=(10.8, 5.2))
    plot_df = plot_df.sort_values(quantity_col)
    ax.barh(
        plot_df["sku"].astype(str), _numeric(plot_df[quantity_col]), color="#1B998B"
    )
    ax.set_title("Top 10 SKUs by Volume")
    ax.set_xlabel("Sold Quantity (Units)")
    ax.set_ylabel("SKU")
    ax.grid(axis="x", alpha=0.25)
    return _save_chart(fig, output_path)


def _fig8_sales_vs_fba_scatter(sku_perf: pd.DataFrame, output_path: Path) -> Path:
    if sku_perf.empty:
        return _placeholder_chart(
            output_path, "Product Sales vs FBA Fees", "No SKU performance data"
        )
    fig, ax = plt.subplots(figsize=(15.2, 9.2))
    x = _numeric(sku_perf["product_sales"]).clip(lower=0)
    y = _numeric(sku_perf["fba_fees"]).abs()

    # Use net income sign as a simple profitability cue if available.
    if "net_income" in sku_perf.columns:
        profit_sign = np.where(
            _numeric(sku_perf["net_income"]) >= 0, "#1B998B", "#D1495B"
        )
    else:
        profit_sign = "#2E86AB"

    ax.scatter(
        x,
        y,
        alpha=0.82,
        c=profit_sign,
        edgecolor="white",
        linewidth=0.55,
        s=88,
    )

    # Add medians to quickly identify high-sales/high-fee clusters.
    x_median = float(x.median())
    y_median = float(y.median())
    ax.axvline(x_median, color="#6B7280", linestyle="--", linewidth=1.0, alpha=0.85)
    ax.axhline(y_median, color="#6B7280", linestyle="--", linewidth=1.0, alpha=0.85)

    # Add simple trend line when data is sufficient.
    valid = x.notna() & y.notna()
    if int(valid.sum()) >= 3 and x[valid].nunique() >= 2:
        slope, intercept = np.polyfit(x[valid], y[valid], 1)
        x_line = np.linspace(float(x[valid].min()), float(x[valid].max()), 100)
        y_line = slope * x_line + intercept
        ax.plot(x_line, y_line, color="#1F3A5F", linewidth=1.6, label="Trend")

    # Highlight top fee-heavy SKUs for easier actioning.
    top_fee = sku_perf.assign(_x=x, _y=y).nlargest(3, "_y")
    for _, row in top_fee.iterrows():
        sku_label = str(row.get("sku", "N/A"))
        label = sku_label if len(sku_label) <= 18 else f"{sku_label[:18]}..."
        ax.annotate(
            label,
            xy=(float(row["_x"]), float(row["_y"])),
            xytext=(5, 4),
            textcoords="offset points",
            fontsize=13,
            color="#1F2937",
        )

    ax.set_title("Product Sales vs FBA Fees by SKU", fontsize=22, fontweight="bold")
    ax.set_xlabel("Product Sales (USD)", fontsize=16)
    ax.set_ylabel("FBA Fees (USD, abs)", fontsize=16)
    ax.xaxis.set_major_formatter(mtick.StrMethodFormatter("${x:,.0f}"))
    ax.yaxis.set_major_formatter(mtick.StrMethodFormatter("${x:,.0f}"))
    ax.tick_params(axis="both", labelsize=14)
    ax.grid(alpha=0.25)
    ax.legend(frameon=False, loc="upper left", fontsize=14)
    fig.tight_layout()
    return _save_chart(fig, output_path)


def _fig9_pareto(sku_perf: pd.DataFrame, output_path: Path) -> Path:
    if sku_perf.empty:
        return _placeholder_chart(
            output_path, "Revenue Concentration (Pareto)", "No SKU revenue data"
        )
    plot_df = sku_perf.sort_values("product_sales", ascending=False).head(15).copy()
    revenue = _numeric(plot_df["product_sales"])
    cumulative = revenue.cumsum() / max(revenue.sum(), 1.0) * 100

    labels = plot_df["sku"].astype(str).tolist()
    labels = [label if len(label) <= 20 else f"{label[:20]}..." for label in labels]
    y_pos = np.arange(len(plot_df))

    fig, ax1 = plt.subplots(figsize=(15.6, 9.4))
    bars = ax1.barh(y_pos, revenue, color="#2E86AB", alpha=0.9)
    ax1.set_yticks(y_pos)
    ax1.set_yticklabels(labels, fontsize=13)
    ax1.invert_yaxis()
    ax1.set_xlabel("Revenue (USD)", fontsize=16)
    ax1.set_title("Revenue Concentration (Pareto)", fontsize=22, fontweight="bold")
    ax1.grid(axis="x", alpha=0.22)
    ax1.xaxis.set_major_formatter(mtick.StrMethodFormatter("${x:,.0f}"))
    ax1.tick_params(axis="both", labelsize=14)

    for bar, value in zip(bars, revenue):
        ax1.text(
            bar.get_width(),
            bar.get_y() + bar.get_height() / 2,
            f" ${value:,.0f}",
            va="center",
            ha="left",
            fontsize=12,
            color="#1F2937",
        )

    ax2 = ax1.twiny()
    ax2.plot(cumulative, y_pos, color="#D1495B", marker="o", linewidth=1.8)
    ax2.set_xlabel("Cumulative Revenue (%)", fontsize=16)
    ax2.xaxis.set_major_formatter(mtick.PercentFormatter(decimals=0))
    ax2.set_xlim(0, 110)
    ax2.axvline(80, color="#777777", linestyle="--", linewidth=1)
    ax2.tick_params(axis="x", labelsize=14)

    reach_80_idx = int(np.argmax(cumulative.to_numpy() >= 80)) if len(cumulative) else 0
    if len(cumulative) and cumulative.iloc[reach_80_idx] >= 80:
        ax2.annotate(
            f"80% reached at SKU #{reach_80_idx + 1}",
            xy=(80, reach_80_idx),
            xytext=(6, -10),
            textcoords="offset points",
            fontsize=13,
            color="#374151",
        )

    fig.tight_layout()
    return _save_chart(fig, output_path)


def _fig10_top3_sku_trend(
    feat_df: pd.DataFrame, sku_perf: pd.DataFrame, output_path: Path
) -> Path:
    if feat_df.empty or sku_perf.empty or "sku" not in feat_df.columns:
        return _placeholder_chart(
            output_path, "Sales Trend of Top 3 SKUs", "No SKU time-series data"
        )
    ranked = sku_perf.copy()
    ranked = ranked[
        ranked["sku"].notna() & ranked["sku"].astype("string").str.strip().ne("")
    ]
    top3 = ranked.nlargest(3, "product_sales")["sku"].astype("string").tolist()
    if not top3:
        return _placeholder_chart(
            output_path, "Sales Trend of Top 3 SKUs", "No valid top SKU list"
        )

    base = feat_df[feat_df["sku"].astype("string").isin(top3)].copy()
    if "type" in base.columns:
        base = base[base["type"].astype("string").eq("Order")]
    if (
        base.empty
        or "date_time" not in base.columns
        or "product_sales" not in base.columns
    ):
        return _placeholder_chart(
            output_path, "Sales Trend of Top 3 SKUs", "No monthly trend data"
        )

    base["date_dt"] = pd.to_datetime(base["date_time"], errors="coerce")
    base = base.dropna(subset=["date_dt"])
    if base.empty:
        return _placeholder_chart(
            output_path, "Sales Trend of Top 3 SKUs", "No valid order timestamps"
        )

    base["period"] = base["date_dt"].dt.to_period("M").dt.to_timestamp()
    grouped = (
        base.groupby(["period", "sku"], dropna=False)["product_sales"]
        .sum()
        .reset_index()
    )
    if grouped.empty:
        return _placeholder_chart(
            output_path, "Sales Trend of Top 3 SKUs", "No grouped monthly trend"
        )

    pivot = grouped.pivot(
        index="period", columns="sku", values="product_sales"
    ).sort_index()

    fig, ax = plt.subplots(figsize=(10.8, 5.2))
    palette = ["#2E86AB", "#F46036", "#1B998B"]
    for sku in top3:
        if sku in pivot.columns:
            series = pd.to_numeric(pivot[sku], errors="coerce")
            valid = series.notna()
            if valid.any():
                color = palette[top3.index(sku) % len(palette)]
                label = str(sku) if len(str(sku)) <= 22 else f"{str(sku)[:22]}..."
                ax.plot(
                    pivot.index[valid],
                    series[valid],
                    marker="o",
                    linewidth=2,
                    label=label,
                    color=color,
                )

    if len(ax.lines) == 0:
        plt.close(fig)
        return _placeholder_chart(
            output_path, "Sales Trend of Top 3 SKUs", "No plottable monthly lines"
        )

    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=1))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    ax.yaxis.set_major_formatter(mtick.StrMethodFormatter("${x:,.0f}"))
    ax.tick_params(axis="x", rotation=35)
    ax.set_title("Sales Trend of Top 3 SKUs")
    ax.set_xlabel("Month")
    ax.set_ylabel("Product Sales (USD)")
    ax.grid(alpha=0.25)
    ax.legend(frameon=False)
    fig.tight_layout()
    return _save_chart(fig, output_path)


def _fig11_reimbursement_treemap(
    reimbursements: pd.DataFrame, output_path: Path
) -> Path:
    if reimbursements.empty or "description" not in reimbursements.columns:
        return _placeholder_chart(
            output_path, "Reimbursement Types", "No reimbursement entries"
        )

    category = pd.Series("Other", index=reimbursements.index)
    desc = reimbursements["description"].astype("string")
    category = np.where(
        desc.str.contains("Damaged", case=False, na=False), "Damaged", category
    )
    category = np.where(
        desc.str.contains("Lost", case=False, na=False), "Lost", category
    )
    category = np.where(
        desc.str.contains("Customer Return", case=False, na=False),
        "Customer Return",
        category,
    )
    temp = reimbursements.copy()
    temp["reimb_type"] = category
    temp["amount"] = _safe_col(temp, "total").abs()
    grouped = (
        temp.groupby("reimb_type", dropna=False)
        .agg(amount=("amount", "sum"), transaction_count=("reimb_type", "size"))
        .reset_index()
    )
    grouped = grouped[grouped["amount"] > 0]
    if grouped.empty:
        return _placeholder_chart(
            output_path, "Reimbursement Credit Types", "No amount to classify"
        )

    try:
        import squarify  # type: ignore

        fig, ax = plt.subplots(figsize=(10.8, 5.2))
        squarify.plot(
            sizes=grouped["amount"],
            label=[
                f"{t}\n{_format_money(a)}\n{int(c)} txns"
                for t, a, c in zip(
                    grouped["reimb_type"],
                    grouped["amount"],
                    grouped["transaction_count"],
                )
            ],
            color=["#2E86AB", "#1B998B", "#D1495B", "#F6AE2D", "#8F5DB7"],
            alpha=0.9,
            ax=ax,
            text_kwargs={"fontsize": 10},
        )
        ax.axis("off")
        ax.set_title("Reimbursement Credit Types (Tree Map)")
        return _save_chart(fig, output_path)
    except Exception:
        fig, ax = plt.subplots(figsize=(10.8, 5.2))
        grouped = grouped.sort_values("amount")
        ax.barh(grouped["reimb_type"], grouped["amount"], color="#2E86AB")
        ax.set_title("Reimbursement Credit Types (Fallback Bar)")
        ax.set_xlabel("Amount (USD)")
        ax.grid(axis="x", alpha=0.25)
        return _save_chart(fig, output_path)


def _fig12_refund_rate_by_sku(clean_df: pd.DataFrame, output_path: Path) -> Path:
    if (
        clean_df.empty
        or "sku" not in clean_df.columns
        or "type" not in clean_df.columns
    ):
        return _placeholder_chart(output_path, "Refund Ratio by SKU", "No refund data")

    qty = _safe_col(clean_df, "quantity").abs()
    orders = clean_df[clean_df["type"].astype("string").eq("Order")].copy()
    refunds = clean_df[clean_df["type"].astype("string").eq("Refund")].copy()
    orders["qty_num"] = _safe_col(orders, "quantity").abs()
    refunds["qty_num"] = _safe_col(refunds, "quantity").abs()

    sold = orders.groupby("sku", dropna=False)["qty_num"].sum()
    returned = refunds.groupby("sku", dropna=False)["qty_num"].sum()
    rate_df = (
        pd.DataFrame({"sold_qty": sold, "refund_qty": returned})
        .fillna(0.0)
        .reset_index()
    )
    rate_df["refund_rate_pct"] = (
        rate_df["refund_qty"] / rate_df["sold_qty"].replace(0, np.nan) * 100
    ).fillna(0.0)
    plot_df = rate_df.sort_values("refund_rate_pct", ascending=False).head(30)

    if plot_df.empty:
        return _placeholder_chart(
            output_path, "Refund Ratio by SKU", "No SKU refund ratio"
        )

    plot_df = plot_df.sort_values("refund_rate_pct")
    fig_height = max(16.0, 0.28 * len(plot_df) + 4.0)
    fig, ax = plt.subplots(figsize=(13.0, fig_height))
    ax.barh(plot_df["sku"].astype(str), plot_df["refund_rate_pct"], color="#D1495B")
    ax.set_title("Refund Ratio by SKU (Top 30)", fontsize=20, fontweight="bold")
    ax.set_xlabel("Refund Rate (%)", fontsize=16)
    ax.set_ylabel("SKU", fontsize=16)
    ax.tick_params(axis="x", labelsize=12)
    ax.tick_params(axis="y", labelsize=13)
    ax.grid(axis="x", alpha=0.25)
    fig.tight_layout()
    return _save_chart(fig, output_path)


def _fig13_fba_fee_vs_qty(feat_df: pd.DataFrame, output_path: Path) -> Path:
    monthly = _add_month_period(feat_df)
    if monthly.empty:
        return _placeholder_chart(
            output_path, "FBA Fee vs Quantity Sold", "No monthly data"
        )
    grouped = (
        monthly.groupby("period", dropna=False)
        .agg(
            quantity=(
                ("quantity", "sum")
                if "quantity" in monthly.columns
                else ("period", "size")
            ),
            fba_fees=(
                ("fba_fees", "sum")
                if "fba_fees" in monthly.columns
                else ("period", "size")
            ),
        )
        .reset_index()
        .sort_values("period")
    )
    fig, ax1 = plt.subplots(figsize=(10.8, 5.2))
    ax1.plot(
        grouped["period"],
        _numeric(grouped["quantity"]),
        marker="o",
        color="#1B998B",
        label="Quantity",
    )
    ax1.set_ylabel("Quantity", color="#1B998B")
    ax1.tick_params(axis="x", rotation=35)

    ax2 = ax1.twinx()
    ax2.plot(
        grouped["period"],
        _numeric(grouped["fba_fees"]).abs(),
        marker="s",
        color="#D1495B",
        label="FBA Fees (abs)",
    )
    ax2.set_ylabel("FBA Fees (USD)", color="#D1495B")

    ax1.set_title("FBA Fee vs Quantity Sold")
    ax1.grid(alpha=0.22)
    return _save_chart(fig, output_path)


def _fig14_general_adjustment_trend(clean_df: pd.DataFrame, output_path: Path) -> Path:
    if clean_df.empty or "type" not in clean_df.columns:
        return _placeholder_chart(
            output_path, "General Adjustment Trends", "No adjustment data"
        )
    data = clean_df[clean_df["type"].astype("string").eq("Adjustment")].copy()
    if "description" in data.columns:
        data = data[
            data["description"]
            .astype("string")
            .str.contains("General Adjustment", case=False, na=False)
        ]
    data = _add_month_period(data)
    grouped = (
        data.groupby("period", dropna=False)["total"].sum().reset_index()
        if "total" in data.columns
        else pd.DataFrame()
    )
    if grouped.empty:
        return _placeholder_chart(
            output_path, "General Adjustment Trends", "No general adjustment records"
        )
    fig, ax = plt.subplots(figsize=(10.8, 5.2))
    ax.fill_between(
        grouped["period"], _numeric(grouped["total"]), color="#F6AE2D", alpha=0.65
    )
    ax.plot(
        grouped["period"], _numeric(grouped["total"]), color="#D1495B", linewidth=1.8
    )
    ax.set_title("General Adjustment Trends (Area)")
    ax.set_xlabel("Month")
    ax.set_ylabel("Adjustment Amount (USD)")
    ax.tick_params(axis="x", rotation=35)
    ax.grid(alpha=0.25)
    return _save_chart(fig, output_path)


def _fig15_storage_non_order_fees(clean_df: pd.DataFrame, output_path: Path) -> Path:
    data = clean_df.copy()
    if "type" not in data.columns:
        return _placeholder_chart(
            output_path, "Storage/Non-order Fees Trend", "No type column"
        )
    type_mask = data["type"].astype("string").isin(["FBA Inventory Fee", "Service Fee"])
    if "description" in data.columns:
        desc_mask = (
            data["description"]
            .astype("string")
            .str.contains(
                "storage|long-term|label|removal", case=False, regex=True, na=False
            )
        )
        type_mask = type_mask | desc_mask
    data = data[type_mask]
    data = _add_month_period(data)
    grouped = (
        data.groupby("period", dropna=False)["total"].sum().reset_index()
        if "total" in data.columns
        else pd.DataFrame()
    )
    if grouped.empty:
        return _placeholder_chart(
            output_path, "Storage/Non-order Fees Trend", "No non-order fee values"
        )
    fig, ax = plt.subplots(figsize=(10.8, 5.2))
    ax.bar(grouped["period"], _numeric(grouped["total"]).abs(), color="#2E86AB")
    ax.set_title("Storage/Non-order Fees Trend")
    ax.set_xlabel("Month")
    ax.set_ylabel("Amount (USD, abs)")
    ax.tick_params(axis="x", rotation=35)
    ax.grid(axis="y", alpha=0.25)
    return _save_chart(fig, output_path)


def _fig16_state_heatmap(feat_df: pd.DataFrame, output_path: Path) -> Path:
    if feat_df.empty or "order_state" not in feat_df.columns:
        return _placeholder_chart(
            output_path, "Sales Heatmap by State", "No state sales data"
        )
    data = _add_month_period(feat_df)
    pivot = (
        data.pivot_table(
            index="order_state",
            columns="period",
            values="gross_revenue",
            aggfunc="sum",
            fill_value=0.0,
        ).sort_values(
            by=(
                list(data["period"].dropna().unique())[-1]
                if data["period"].notna().any()
                else data.columns[0]
            ),
            ascending=False,
        )
        if "gross_revenue" in data.columns
        else pd.DataFrame()
    )
    if pivot.empty:
        return _placeholder_chart(
            output_path, "Sales Heatmap by State", "No state-period matrix"
        )
    pivot = pivot.head(15)
    pivot = pivot.apply(pd.to_numeric, errors="coerce").fillna(0.0)

    fig, ax = plt.subplots(figsize=(15.5, 10.5))
    values = pivot.to_numpy(dtype=float)
    im = ax.imshow(values, aspect="auto", cmap="YlGnBu")
    ax.set_yticks(np.arange(len(pivot.index)))
    ax.set_yticklabels(pivot.index.astype(str), fontsize=12)
    ax.set_xticks(np.arange(len(pivot.columns)))
    ax.set_xticklabels(pivot.columns.astype(str), rotation=45, ha="right", fontsize=12)
    ax.set_title("Sales Heatmap by State", fontsize=20, fontweight="bold")

    # Show exact values directly on each cell for easier reading in the PDF.
    vmax = float(np.nanmax(values)) if values.size else 0.0
    threshold = vmax * 0.5
    for i in range(values.shape[0]):
        for j in range(values.shape[1]):
            val = values[i, j]
            text_color = "white" if val >= threshold else "#1F2937"
            ax.text(
                j,
                i,
                f"${val:,.0f}",
                ha="center",
                va="center",
                fontsize=11,
                fontweight="bold",
                color=text_color,
            )

    cbar = plt.colorbar(im, ax=ax, shrink=0.92)
    cbar.ax.tick_params(labelsize=12)
    fig.tight_layout()
    return _save_chart(fig, output_path)


def _fig17_top_cities(feat_df: pd.DataFrame, output_path: Path) -> Path:
    if feat_df.empty or "order_city" not in feat_df.columns:
        return _placeholder_chart(
            output_path, "Top 10 Order Cities", "No city-level data"
        )
    grouped = (
        feat_df.groupby("order_city", dropna=False)["gross_revenue"]
        .sum()
        .reset_index()
        .sort_values("gross_revenue", ascending=False)
        .head(10)
    )
    if grouped.empty:
        return _placeholder_chart(
            output_path, "Top 10 Order Cities", "No city revenue values"
        )

    fig, ax = plt.subplots(figsize=(10.8, 5.2))
    grouped = grouped.sort_values("gross_revenue")
    ax.barh(
        grouped["order_city"].astype(str), grouped["gross_revenue"], color="#1B998B"
    )
    ax.set_title("Top 10 Order Cities")
    ax.set_xlabel("Gross Revenue")
    ax.set_ylabel("City")
    ax.grid(axis="x", alpha=0.25)
    return _save_chart(fig, output_path)


def _fig18_tax_dual_line(feat_df: pd.DataFrame, output_path: Path) -> Path:
    monthly = _add_month_period(feat_df)
    if monthly.empty:
        return _placeholder_chart(
            output_path, "Tax Collected vs Tax Withheld", "No tax data"
        )
    grouped = (
        monthly.groupby("period", dropna=False)
        .agg(
            product_sales_tax=(
                ("product_sales_tax", "sum")
                if "product_sales_tax" in monthly.columns
                else ("period", "size")
            ),
            marketplace_withheld_tax=(
                ("marketplace_withheld_tax", "sum")
                if "marketplace_withheld_tax" in monthly.columns
                else ("period", "size")
            ),
        )
        .reset_index()
        .sort_values("period")
    )

    fig, ax = plt.subplots(figsize=(10.8, 5.2))
    ax.plot(
        grouped["period"],
        _numeric(grouped["product_sales_tax"]),
        marker="o",
        linewidth=2,
        label="Product Sales Tax",
        color="#2E86AB",
    )
    ax.plot(
        grouped["period"],
        _numeric(grouped["marketplace_withheld_tax"]),
        marker="s",
        linewidth=2,
        label="Marketplace Withheld Tax",
        color="#D1495B",
    )
    ax.set_title("Tax Collected vs Tax Withheld")
    ax.set_xlabel("Month")
    ax.set_ylabel("Tax Amount (USD)")
    ax.tick_params(axis="x", rotation=35)
    ax.grid(alpha=0.25)
    ax.legend(frameon=False)
    return _save_chart(fig, output_path)


def _fig19_promotional_impact(feat_df: pd.DataFrame, output_path: Path) -> Path:
    monthly = _add_month_period(feat_df)
    if monthly.empty:
        return _placeholder_chart(output_path, "Promotional Impact", "No promo data")
    grouped = (
        monthly.groupby("period", dropna=False)
        .agg(
            promotional_rebates=(
                ("promotional_rebates", "sum")
                if "promotional_rebates" in monthly.columns
                else ("period", "size")
            ),
            gross_revenue=(
                ("gross_revenue", "sum")
                if "gross_revenue" in monthly.columns
                else ("period", "size")
            ),
        )
        .reset_index()
        .sort_values("period")
    )
    x = np.arange(len(grouped))
    gross = _numeric(grouped["gross_revenue"])
    promo = _numeric(grouped["promotional_rebates"])

    fig, ax_left = plt.subplots(figsize=(10.8, 5.2))
    ax_right = ax_left.twinx()

    bars_revenue = ax_left.bar(
        x - 0.2,
        gross,
        width=0.4,
        color="#2E86AB",
        alpha=0.9,
    )
    bars_promo = ax_right.bar(
        x + 0.2,
        promo,
        width=0.4,
        color="#F6AE2D",
        alpha=0.95,
    )

    ax_left.set_xticks(x)
    ax_left.set_xticklabels(grouped["period"], rotation=35)
    ax_left.set_title("Promotional Impact (Dual Axis)")
    ax_left.set_ylabel("Gross Revenue (USD)", color="#2E86AB")
    ax_right.set_ylabel("Promotional Rebates (USD)", color="#F6AE2D")
    ax_left.tick_params(axis="y", colors="#2E86AB")
    ax_right.tick_params(axis="y", colors="#B87500")
    ax_left.yaxis.set_major_formatter(mtick.StrMethodFormatter("${x:,.0f}"))
    ax_right.yaxis.set_major_formatter(mtick.StrMethodFormatter("${x:,.0f}"))
    ax_left.grid(axis="y", alpha=0.25)

    # Make each month-pair easier to read.
    for idx in range(len(x) - 1):
        ax_left.axvline(idx + 0.5, color="#D1D5DB", linewidth=0.7, alpha=0.7)

    legend_handles = [bars_revenue, bars_promo]
    legend_labels = ["Gross Revenue", "Promotional Rebates"]
    ax_left.legend(
        legend_handles,
        legend_labels,
        loc="upper center",
        bbox_to_anchor=(0.5, 1.17),
        ncol=2,
        frameon=False,
    )

    fig.tight_layout(rect=[0, 0, 1, 0.92])

    return _save_chart(fig, output_path)


def _fig20_daily_order_hist(order_df: pd.DataFrame, output_path: Path) -> Path:
    if order_df.empty or "gross_revenue" not in order_df.columns:
        return _placeholder_chart(
            output_path, "Daily Order Frequency (AOV)", "No order-level revenue data"
        )
    aov = _numeric(order_df["gross_revenue"])
    if aov.empty:
        return _placeholder_chart(
            output_path, "Daily Order Frequency (AOV)", "No AOV values"
        )

    fig, ax = plt.subplots(figsize=(10.8, 5.2))
    ax.hist(aov, bins=25, color="#2E86AB", alpha=0.85, edgecolor="white")
    ax.set_title("Daily Order Frequency (AOV Histogram)")
    ax.set_xlabel("Order Value (USD)")
    ax.set_ylabel("Frequency")
    ax.grid(axis="y", alpha=0.25)
    return _save_chart(fig, output_path)


def _build_figure_artifacts(
    raw_df: pd.DataFrame,
    clean_df: pd.DataFrame,
    feat_df: pd.DataFrame,
    order_df: pd.DataFrame,
    tables: dict[str, pd.DataFrame],
    chart_dir: Path,
) -> list[tuple[int, str, Path]]:
    sku_perf = tables.get("T5 - SKU Profitability Matrix", pd.DataFrame())
    sku_sales_order_only = tables.get("_T3_FULL_ORDER_ONLY", pd.DataFrame())
    reimbursements = tables.get("T6 - Reimbursement Log", pd.DataFrame())
    monthly_pl = tables.get("T1 - P&L Summary (Monthly)", pd.DataFrame())

    figures: list[tuple[int, str, Path]] = []
    figures.append(
        (
            1,
            "Monthly Net Income Trend",
            _fig1_monthly_net_income(
                monthly_pl, chart_dir / "fig_01_monthly_net_income.png"
            ),
        )
    )
    figures.append(
        (
            2,
            "Revenue vs Expenses",
            _fig2_revenue_vs_expenses(
                monthly_pl, chart_dir / "fig_02_revenue_vs_expenses.png"
            ),
        )
    )
    figures.append(
        (
            3,
            "Profit Drivers (Diverging Bar)",
            _fig3_profit_waterfall(feat_df, chart_dir / "fig_03_profit_waterfall.png"),
        )
    )
    figures.append(
        (
            4,
            "Expense Breakdown",
            _fig4_expense_breakdown(
                feat_df, chart_dir / "fig_04_expense_breakdown.png"
            ),
        )
    )
    figures.append(
        (
            5,
            "Total Type Distribution",
            _fig5_type_distribution(raw_df, chart_dir / "fig_05_type_distribution.png"),
        )
    )

    figures.append(
        (
            6,
            "Top 10 SKUs by Sales",
            _fig6_top_sku_sales(
                sku_sales_order_only, chart_dir / "fig_06_top_sku_sales.png"
            ),
        )
    )
    figures.append(
        (
            7,
            "Top 10 SKUs by Volume",
            _fig7_top_sku_volume(
                sku_sales_order_only, chart_dir / "fig_07_top_sku_volume.png"
            ),
        )
    )
    figures.append(
        (
            8,
            "Product Sales vs FBA Fees by SKU",
            _fig8_sales_vs_fba_scatter(
                sku_perf, chart_dir / "fig_08_sales_vs_fba_scatter.png"
            ),
        )
    )
    figures.append(
        (
            9,
            "Revenue Concentration (Pareto)",
            _fig9_pareto(sku_sales_order_only, chart_dir / "fig_09_pareto.png"),
        )
    )
    figures.append(
        (
            10,
            "Sales Trend of Top 3 SKUs",
            _fig10_top3_sku_trend(
                feat_df, sku_sales_order_only, chart_dir / "fig_10_top3_sku_trend.png"
            ),
        )
    )

    figures.append(
        (
            11,
            "Reimbursement Types",
            _fig11_reimbursement_treemap(
                reimbursements, chart_dir / "fig_11_reimbursement_types.png"
            ),
        )
    )
    figures.append(
        (
            12,
            "Refund Rate by SKU",
            _fig12_refund_rate_by_sku(clean_df, chart_dir / "fig_12_refund_rate.png"),
        )
    )
    figures.append(
        (
            13,
            "FBA Fee vs Quantity Sold",
            _fig13_fba_fee_vs_qty(feat_df, chart_dir / "fig_13_fba_fee_vs_qty.png"),
        )
    )
    figures.append(
        (
            14,
            "General Adjustment Trends",
            _fig14_general_adjustment_trend(
                clean_df, chart_dir / "fig_14_adjustment_trend.png"
            ),
        )
    )
    figures.append(
        (
            15,
            "Storage / Non-order Fees Trend",
            _fig15_storage_non_order_fees(
                clean_df, chart_dir / "fig_15_storage_non_order_fees.png"
            ),
        )
    )

    figures.append(
        (
            16,
            "Sales Heatmap by State",
            _fig16_state_heatmap(feat_df, chart_dir / "fig_16_state_heatmap.png"),
        )
    )
    figures.append(
        (
            17,
            "Top 10 Order Cities",
            _fig17_top_cities(feat_df, chart_dir / "fig_17_top_cities.png"),
        )
    )
    figures.append(
        (
            18,
            "Tax Collected vs Tax Withheld",
            _fig18_tax_dual_line(feat_df, chart_dir / "fig_18_tax_dual_line.png"),
        )
    )
    figures.append(
        (
            19,
            "Promotional Impact",
            _fig19_promotional_impact(
                feat_df, chart_dir / "fig_19_promotional_impact.png"
            ),
        )
    )
    figures.append(
        (
            20,
            "Daily Order Frequency (AOV)",
            _fig20_daily_order_hist(order_df, chart_dir / "fig_20_aov_hist.png"),
        )
    )

    return figures


def _append_table_block(
    story: list[Any],
    styles: dict[str, ParagraphStyle],
    heading: str,
    df: pd.DataFrame,
    max_rows: int = 12,
) -> None:
    story.append(Paragraph(heading, styles["SubHeading"]))
    story.append(_table_from_dataframe(df, styles, max_rows=max_rows))
    story.append(Spacer(1, 0.28 * cm))


def _append_figure_block(
    story: list[Any],
    styles: dict[str, ParagraphStyle],
    figures: list[tuple[int, str, Path]],
    numbers: list[int],
) -> None:
    figure_descriptions: dict[int, str] = {
        1: "This line chart shows monthly net income after combining gross revenue and total expenses. It is the quickest way to see whether the settlement improved or deteriorated over time.",
        2: "This stacked chart compares monthly gross revenue against total expenses. The gap between the two bars shows how much of revenue was absorbed by fees and other deductions.",
        3: "This diverging bar chart shows profit drivers in one view: Gross Revenue (positive), cost/refund impacts (negative), and final Net Income. It is easier to read quickly than a cumulative waterfall when stakeholders focus on component impact.",
        4: "This pie chart breaks down the main fee categories using absolute values. It is meant to show which fee buckets consume the most cash, not the direction of the sign.",
        5: "This donut chart groups raw transaction types by their total absolute value. It helps identify which transaction families dominate the settlement flow.",
        6: "This bar chart ranks the top SKUs by product sales from order-only rows. It reflects sales performance rather than profitability, so a high-selling SKU may still have weak margin.",
        7: "This bar chart ranks the top SKUs by sold quantity from order-only rows. It is useful for understanding volume concentration and operational demand.",
        11: "This chart groups reimbursement credits by reason. Lost, Damaged, and Customer Return are Amazon reimbursements, so the amounts shown here are positive credits, not expenses. The transaction count helps separate a few large reimbursements from many small ones.",
        8: "This scatter chart maps each SKU by Product Sales (x-axis) and absolute FBA Fees (y-axis). Dashed median lines split the chart into quadrants to quickly spot SKUs with unusually high fee burden at comparable sales levels.",
        9: "This Pareto view ranks the top SKUs by revenue and overlays cumulative contribution. Use the 80% reference line to estimate how many SKUs drive most revenue, then prioritize those SKUs for pricing, inventory, and ad optimization.",
        10: "This line chart tracks the top three revenue SKUs over time. It helps separate stable sellers from one-time spikes and shows whether the best products are growing or fading.",
        12: "This bar chart shows refund ratio by SKU using refunded units divided by sold units within the same reporting period. It is not capped at 100%, so values above 100% mean refunded units in the period exceeded sold units for that SKU, which can happen for low-volume items or when returns land in a different timing window.",
        13: "This dual-axis chart compares monthly FBA fees with quantity sold. It is useful for checking whether fulfillment cost is scaling proportionally with volume.",
        14: "This area chart shows the monthly total of rows classified as Adjustment and filtered to descriptions containing General Adjustment. The red line is the summed total amount for each month: positive values mean Amazon credited the account, while negative values mean Amazon deducted money.",
        15: "This bar chart shows storage and non-order fees over time, including FBA inventory fees and related description-based charges. It is intended to surface operational leakage outside direct sales rows.",
        16: "This heatmap shows monthly gross revenue by state. Darker cells indicate stronger sales concentration in a given region and month.",
        17: "This bar chart ranks the top cities by gross revenue. It helps identify localized demand concentration and the main shipping markets.",
        18: "This dual-line chart compares product sales tax and marketplace withheld tax across months. It is meant for reconciliation and spotting divergence between tax collected and tax withheld.",
        19: "This dual-axis monthly chart is used to compare revenue scale and promotional spend in the same view. It shows Gross Revenue (left axis, blue bars) against Promotional Rebates (right axis, yellow bars), helping you see whether promotion intensity is rising, stable, or dropping relative to sales over time.",
        20: "This histogram shows the distribution of order-level gross revenue. It gives a fast view of average order value spread and whether the business is concentrated in small or high-value orders.",
    }

    rendered = 0
    total = len(numbers)
    for n in numbers:
        selected = [item for item in figures if item[0] == n]
        if not selected:
            continue
        fig_no, title, img_path = selected[0]
        if fig_no in {12, 16}:
            story.append(PageBreak())
        max_height = 11.8 if fig_no in {4, 5} else 7.4
        max_width = 17.8 if fig_no in {4, 5} else 17.0
        if fig_no in {8, 9}:
            max_height = 9.8
            max_width = 17.8
        if fig_no == 12:
            max_width = 18.2
            max_height = 20.0
        if fig_no == 16:
            max_width = 18.2
            max_height = 20.0
        description = figure_descriptions.get(fig_no)
        block = [Paragraph(f"Figure {fig_no}: {title}", styles["BodyTextReport"])]
        if description:
            block.append(Paragraph(description, styles["BodyTextReport"]))
        block.extend(
            [
                Spacer(1, 0.05 * cm),
                _scaled_image(
                    img_path, max_width_cm=max_width, max_height_cm=max_height
                ),
                Spacer(1, 0.2 * cm),
            ]
        )
        story.append(KeepTogether(block))
        rendered += 1
        if fig_no in {12, 16}:
            story.append(PageBreak())
            continue
        # Keep figure pages clean and predictable: maximum 2 figures per page.
        if rendered < total and rendered % 2 == 0:
            story.append(PageBreak())


def generate_pdf_report(
    raw_df: pd.DataFrame,
    clean_df: pd.DataFrame,
    feat_df: pd.DataFrame,
    sku_df: pd.DataFrame,
    ts_df: pd.DataFrame,
    geo_df: pd.DataFrame,
    fee_df: pd.DataFrame,
    insights: dict[str, pd.DataFrame],
    output_path: str | Path = "outputs/amazon_settlement_report.pdf",
) -> Path:
    """Generate a 4-layer dashboard PDF with 11 tables and 20 figures."""
    _ = sku_df, ts_df, geo_df, fee_df, insights

    styles = _build_styles()
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    order_df = pd.DataFrame()
    if "order_id" in feat_df.columns:
        order_df = (
            feat_df[feat_df["order_id"].notna()]
            .groupby("order_id", dropna=False)
            .agg(
                gross_revenue=(
                    ("gross_revenue", "sum")
                    if "gross_revenue" in feat_df.columns
                    else ("order_id", "size")
                )
            )
            .reset_index()
        )

    tables = _build_report_tables(raw_df=raw_df, clean_df=clean_df, feat_df=feat_df)

    with TemporaryDirectory() as tmp_dir:
        tmp_root = Path(tmp_dir)
        figures = _build_figure_artifacts(
            raw_df=raw_df,
            clean_df=clean_df,
            feat_df=feat_df,
            order_df=order_df,
            tables=tables,
            chart_dir=tmp_root,
        )

        story: list[Any] = []
        story.append(Spacer(1, 1.7 * cm))
        story.append(Paragraph(REPORT_TITLE, styles["ReportTitle"]))
        story.append(
            Paragraph(
                "This report is structured into 4 dashboard layers: Executive, SKU/Product, FBA/Adjustment, and Geographic/Tax. It includes 11 tables and 20 figures to monitor Amazon settlement cash flow.",
                styles["BodyTextReport"],
            )
        )
        story.append(Spacer(1, 0.25 * cm))
        story.append(
            Paragraph(
                "Core requirements covered: (1) Total aggregation by Type Group; (2) Net Income computed as Total Revenue + Total Expenses (where expense components are negative), with reconciliation against the total column.",
                styles["BodyTextReport"],
            )
        )
        story.append(PageBreak())

        story.append(
            Paragraph("Layer 1: Executive Dashboard", styles["SectionHeading"])
        )
        story.append(
            Paragraph(
                "Monthly overview of cash flow, net income, and transaction structure.",
                styles["BodyTextReport"],
            )
        )
        story.append(Spacer(1, 0.16 * cm))
        story.append(
            Paragraph(
                "Table 1 summarizes monthly gross revenue, total expenses, net income, and margin percentage. Use it as the executive P/L view for the settlement period.",
                styles["BodyTextReport"],
            )
        )
        story.append(Spacer(1, 0.08 * cm))
        _append_table_block(
            story,
            styles,
            "Table 1 - P&L Summary",
            tables["T1 - P&L Summary (Monthly)"],
            max_rows=24,
        )
        story.append(
            Paragraph(
                "Table 2 groups the raw transaction stream by type group and shows both transaction count and total amount. It is the reconciliation table for understanding where money entered or left the account.",
                styles["BodyTextReport"],
            )
        )
        story.append(Spacer(1, 0.08 * cm))
        _append_table_block(
            story,
            styles,
            "Table 2 - Transaction Type Master Table",
            tables["T2 - Transaction Type Master Table"],
            max_rows=24,
        )
        _append_figure_block(story, styles, figures, [1, 2, 3, 4, 5])
        story.append(PageBreak())

        story.append(
            Paragraph("Layer 2: Product & SKU Performance", styles["SectionHeading"])
        )
        story.append(
            Paragraph(
                "Revenue, volume, and margin analysis by SKU to optimize the product portfolio.",
                styles["BodyTextReport"],
            )
        )
        story.append(Spacer(1, 0.16 * cm))
        story.append(
            Paragraph(
                "Table 3 is ranked by Order-only Product Sales to reflect true selling performance. "
                "Sold Quantity includes order units only, Refunded Quantity captures returned units, "
                "and Net Quantity = Sold Quantity - Refunded Quantity.",
                styles["BodyTextReport"],
            )
        )
        story.append(Spacer(1, 0.12 * cm))
        story.append(
            Paragraph(
                "Table 3 is the bestseller view. It ranks SKUs by sold revenue from order rows only, then shows how much of that volume was later refunded.",
                styles["BodyTextReport"],
            )
        )
        story.append(Spacer(1, 0.08 * cm))
        _append_table_block(
            story,
            styles,
            "Table 3 - Top 10 Bestsellers",
            tables["T3 - Top 10 Bestsellers (Revenue & Quantity)"],
            max_rows=10,
        )
        story.append(
            Paragraph(
                "Table 4 highlights the lowest-net-income SKUs so you can quickly inspect items that are underperforming after fees are applied.",
                styles["BodyTextReport"],
            )
        )
        story.append(Spacer(1, 0.08 * cm))
        _append_table_block(
            story,
            styles,
            "Table 4 - Worst Performing SKUs",
            tables["T4 - Worst Performing SKUs"],
            max_rows=10,
        )
        story.append(
            Paragraph(
                "Table 5 is a full SKU profitability matrix. It lets you compare sales, quantity, fee burden, and gross margin percentage on the same row.",
                styles["BodyTextReport"],
            )
        )
        story.append(Spacer(1, 0.08 * cm))
        _append_table_block(
            story,
            styles,
            "Table 5 - SKU Profitability Matrix",
            tables["T5 - SKU Profitability Matrix"],
            max_rows=18,
        )
        _append_figure_block(story, styles, figures, [6, 7, 8, 9, 10])
        story.append(PageBreak())

        story.append(
            Paragraph("Layer 3: FBA, Inventory & Adjustment", styles["SectionHeading"])
        )
        story.append(
            Paragraph(
                "Track refunds, reimbursements, and operational fee categories to reduce leakage.",
                styles["BodyTextReport"],
            )
        )
        story.append(Spacer(1, 0.16 * cm))
        story.append(
            Paragraph(
                "Figure 11 is a reimbursement-credit view, not a loss chart: Lost, Damaged, and Customer Return rows are Amazon credits. Use it to confirm that some large 'Lost' amounts are reimbursements back to the account, while the real outflows are usually in fee and refund tables.",
                styles["BodyTextReport"],
            )
        )
        story.append(Spacer(1, 0.08 * cm))
        story.append(
            Paragraph(
                "Table 6 lists reimbursement-related adjustments matched from descriptions containing Lost, Damaged, or Customer Return. It is the transaction-level audit trail behind Figure 11.",
                styles["BodyTextReport"],
            )
        )
        story.append(Spacer(1, 0.08 * cm))
        _append_table_block(
            story,
            styles,
            "Table 6 - Reimbursement Log",
            tables["T6 - Reimbursement Log"],
            max_rows=20,
        )
        story.append(
            Paragraph(
                "Table 7 shows refund and return rows sorted by absolute amount. Use it to identify the largest reversals and check which SKUs are driving returns.",
                styles["BodyTextReport"],
            )
        )
        story.append(Spacer(1, 0.08 * cm))
        _append_table_block(
            story,
            styles,
            "Table 7 - Refund/Return Detail",
            tables["T7 - Refund / Return Detail"],
            max_rows=20,
        )
        story.append(
            Paragraph(
                "Table 8 summarizes fee buckets from the cleaned analysis scope, so it reflects the operational picture used in the core metrics.",
                styles["BodyTextReport"],
            )
        )
        story.append(Spacer(1, 0.08 * cm))
        _append_table_block(
            story,
            styles,
            "Table 8 - Fees Deep-Dive",
            tables["T8 - Fees Deep-Dive"],
            max_rows=12,
        )
        story.append(
            Paragraph(
                "Table 8B shows the same fee view on the full raw transaction set. It is included for reconciliation when you want to compare cleaned scope against all transaction types.",
                styles["BodyTextReport"],
            )
        )
        story.append(Spacer(1, 0.08 * cm))
        _append_table_block(
            story,
            styles,
            "Table 8B - Fees Deep-Dive (All Raw Types)",
            tables["T8B - Fees Deep-Dive (All Raw Types)"],
            max_rows=12,
        )
        story.append(
            Paragraph(
                "Table 8 uses the cleaned analysis scope (Order, Refund, Adjustment, Service Fee). "
                "Table 8B shows full raw transaction scope for reconciliation.",
                styles["BodyTextReport"],
            )
        )
        story.append(Spacer(1, 0.1 * cm))
        _append_figure_block(story, styles, figures, [11, 12, 13, 14, 15])
        story.append(PageBreak())

        story.append(
            Paragraph(
                "Layer 4: Geographic, Tax & Customer Insights", styles["SectionHeading"]
            )
        )
        story.append(
            Paragraph(
                "Market, city, and tax reconciliation analysis to support ad strategy and compliance.",
                styles["BodyTextReport"],
            )
        )
        story.append(Spacer(1, 0.16 * cm))
        story.append(
            Paragraph(
                "Table 9 groups revenue by state and city so you can see where sales are concentrated geographically and where fulfillment demand is strongest.",
                styles["BodyTextReport"],
            )
        )
        story.append(Spacer(1, 0.08 * cm))
        _append_table_block(
            story,
            styles,
            "Table 9 - Sales by State/City",
            tables["T9 - Sales by State / City"],
            max_rows=20,
        )
        story.append(
            Paragraph(
                "Table 10 reconciles tax collected versus marketplace withheld tax by month. It is intended to surface differences that may need manual review.",
                styles["BodyTextReport"],
            )
        )
        story.append(Spacer(1, 0.08 * cm))
        _append_table_block(
            story,
            styles,
            "Table 10 - Tax Collection Summary",
            tables["T10 - Tax Collection Summary"],
            max_rows=24,
        )
        _append_figure_block(story, styles, figures, [16, 17, 18, 19, 20])

        story.append(Spacer(1, 0.2 * cm))
        story.append(Paragraph("Analyst Recommendation", styles["SectionHeading"]))
        story.append(
            Paragraph(
                "The settlement data shows frequent Adjustment activity. Prioritize Table 6 and Figure 11 to monitor reimbursements, audit Damaged/Lost cases, and proactively submit claims when needed.",
                styles["BodyTextReport"],
            )
        )

        doc = SimpleDocTemplate(
            str(output),
            pagesize=A4,
            rightMargin=1.4 * cm,
            leftMargin=1.4 * cm,
            topMargin=1.7 * cm,
            bottomMargin=1.4 * cm,
            title=REPORT_TITLE,
            author="GitHub Copilot",
        )
        doc.build(story, onFirstPage=_header_footer, onLaterPages=_header_footer)

    return output
