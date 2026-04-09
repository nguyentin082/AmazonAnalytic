from __future__ import annotations

import pandas as pd

from src.data.preprocess import convert_numeric_columns
from src.report import _parse_currency_series


def test_convert_numeric_columns_parses_currency_and_thousands() -> None:
    df = pd.DataFrame(
        {
            "total": ["6,000.00", "-$25.50", "0"],
            "product_sales": ["1,234.56", "$9.99", "-100"],
            "fba_fees": ["-1,200.00", "0", "12.34"],
        }
    )

    result = convert_numeric_columns(df)

    assert result["total"].tolist() == [6000.0, -25.5, 0.0]
    assert result["product_sales"].tolist() == [1234.56, 9.99, -100.0]
    assert result["fba_fees"].tolist() == [-1200.0, 0.0, 12.34]


def test_convert_numeric_columns_parses_additional_fee_columns() -> None:
    df = pd.DataFrame(
        {
            "regulatory_fee": ["1,500.10", "$0.90"],
            "tax_on_regulatory_fee": ["150.01", "$0.09"],
        }
    )

    result = convert_numeric_columns(df)

    assert result["regulatory_fee"].tolist() == [1500.10, 0.90]
    assert result["tax_on_regulatory_fee"].tolist() == [150.01, 0.09]


def test_parse_currency_series_handles_thousand_separator() -> None:
    series = pd.Series(["6,000.00", "-5,064.71", "$12.50"])

    parsed = _parse_currency_series(series)

    assert parsed.tolist() == [6000.0, -5064.71, 12.5]
