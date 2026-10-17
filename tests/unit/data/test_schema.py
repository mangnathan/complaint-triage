from __future__ import annotations

from typing import Any

import pandas as pd
import pandera.errors
import pytest

from complaint_triage.data.schema import validate_complaints

DATE_COLUMNS = ("date_received", "date_sent_to_company")


def complaints(**overrides: Any) -> pd.DataFrame:
    row: dict[str, Any] = {
        "complaint_id": 1,
        "date_received": "2024-01-15",
        "product": "Credit card",
        "sub_product": "Store credit card",
        "issue": "Fees or interest",
        "sub_issue": None,
        "company": "Example Bank",
        "state": "CA",
        "zip_code": "90001",
        "tags": None,
        "submitted_via": "Web",
        "date_sent_to_company": "2024-01-16",
        "company_public_response": None,
        "company_response": "Closed with monetary relief",
        "timely_response": "Yes",
        "narrative": None,
    }
    row.update(overrides)
    df = pd.DataFrame([row])
    for column in df.columns:
        if column in DATE_COLUMNS:
            df[column] = pd.to_datetime(df[column]).astype("datetime64[ns]")
        elif column != "complaint_id":
            df[column] = df[column].astype("str")
    return df.astype({"complaint_id": "int64"})


def test_valid_rows_pass() -> None:
    validate_complaints(complaints())


def test_duplicate_ids_are_rejected() -> None:
    df = pd.concat([complaints(), complaints()], ignore_index=True)
    with pytest.raises(pandera.errors.SchemaErrors):
        validate_complaints(df)


def test_unknown_response_is_rejected() -> None:
    with pytest.raises(pandera.errors.SchemaErrors):
        validate_complaints(complaints(company_response="Closed"))


def test_product_outside_scope_is_rejected() -> None:
    with pytest.raises(pandera.errors.SchemaErrors):
        validate_complaints(complaints(product="Mortgage"))


def test_unexpected_column_is_rejected() -> None:
    with pytest.raises(pandera.errors.SchemaErrors):
        validate_complaints(complaints().assign(extra_column="x"))
