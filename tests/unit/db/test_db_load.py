from __future__ import annotations

import pandas as pd

from complaint_triage.db.load import STORED_COLUMNS, queue_frame
from complaint_triage.models.baseline import H0_LEVELS, RateBaseline


def complaints() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "complaint_id": [3, 1, 2, 4],
            "date_received": pd.to_datetime(
                ["2026-02-01", "2025-12-31", "2026-01-01", "2026-03-01"]
            ),
            "product": ["Credit card"] * 4,
            "sub_product": [None] * 4,
            "issue": ["Fees", "Fees", "Other", "Fees"],
            "sub_issue": [None] * 4,
            "company": ["Bank A", "Bank A", "Bank A", "EQUIFAX, INC."],
            "state": ["CA"] * 4,
            "zip_code": ["94110"] * 4,
            "submitted_via": ["Web"] * 4,
            "tags": [None] * 4,
            "narrative": ["text", "", "", "text"],
            "company_response": ["Closed with monetary relief"] * 4,
        }
    )


def scorer() -> RateBaseline:
    train = complaints()
    return RateBaseline(H0_LEVELS).fit(train, pd.Series([1, 0, 0, 1]))


def test_the_queue_starts_in_2026_and_excludes_reporting_agencies() -> None:
    queue = queue_frame(complaints(), scorer())

    assert list(queue["complaint_id"]) == [2, 3]


def test_only_intake_columns_without_zip_code_are_stored() -> None:
    queue = queue_frame(complaints(), scorer())

    assert tuple(queue.columns) == STORED_COLUMNS
    assert "zip_code" not in queue.columns
    assert "company_response" not in queue.columns


def test_every_complaint_gets_a_priority_between_zero_and_one() -> None:
    queue = queue_frame(complaints(), scorer())

    assert queue["priority_score"].between(0, 1).all()


def test_an_empty_narrative_becomes_null() -> None:
    queue = queue_frame(complaints(), scorer())

    assert queue.loc[queue["complaint_id"] == 2, "narrative"].isna().all()
