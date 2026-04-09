from __future__ import annotations

import pandas as pd

from src.data.validation import validate_settlement_schema


def test_validate_settlement_schema_accepts_expected_columns() -> None:
    df = pd.DataFrame(
        {
            "date_time": ["Jan 1, 2023 1:51:19 AM PST"],
            "settlement_id": ["123"],
            "type": ["Order"],
            "sku": ["ABC"],
            "quantity": [1],
            "marketplace": ["amazon.com"],
            "account_type": ["Standard Orders"],
            "fulfillment": ["Seller"],
            "product_sales": [8.89],
        }
    )

    result = validate_settlement_schema(df)

    assert result.is_valid
    assert result.missing_columns == []


def test_validate_settlement_schema_flags_missing_columns() -> None:
    df = pd.DataFrame({"date_time": ["Jan 1, 2023 1:51:19 AM PST"]})

    result = validate_settlement_schema(df)

    assert not result.is_valid
    assert "sku" in result.missing_columns
