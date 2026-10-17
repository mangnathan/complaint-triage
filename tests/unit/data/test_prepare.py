from __future__ import annotations

from collections.abc import Callable
from datetime import date

import pandas as pd

from complaint_triage.data.columns import ID_COLUMN, INTAKE_COLUMNS
from complaint_triage.data.prepare import (
    TARGET,
    exclude_reporting_agencies,
    keep_mature,
    prepare_for_modeling,
)

MakeComplaints = Callable[..., pd.DataFrame]
EXPORT_DATE = date(2026, 10, 17)


def test_reporting_agencies_are_excluded_and_counted(make_complaints: MakeComplaints) -> None:
    df = make_complaints({"company": "EQUIFAX, INC."}, {"company": "Example Bank"})

    kept, dropped = exclude_reporting_agencies(df)

    assert dropped == 1
    assert list(kept["company"]) == ["Example Bank"]


def test_keep_mature_uses_the_export_date(make_complaints: MakeComplaints) -> None:
    df = make_complaints(
        {"date_received": "2026-09-01"},  # 46 jours avant l'export : trop récente
        {"date_received": "2026-07-19"},  # exactement 90 jours : gardée
        {"date_received": "2026-06-01", "company_response": "In progress"},
        {"date_received": "2026-06-01", "company_response": "Closed with explanation"},
    )

    kept, too_recent, still_pending = keep_mature(df, EXPORT_DATE)

    assert (too_recent, still_pending) == (1, 1)
    assert sorted(kept["complaint_id"]) == [2, 4]


def test_prepared_data_has_only_intake_columns_and_the_target(
    make_complaints: MakeComplaints,
) -> None:
    df = make_complaints(
        {"company_response": "Closed with monetary relief"},
        {"company_response": "Closed with non-monetary relief"},
        {"company_response": "Untimely response"},
        {"company": "TRANSUNION INTERMEDIATE HOLDINGS, INC."},
        {"date_received": "2026-10-01"},
    )

    prepared, report = prepare_for_modeling(df, EXPORT_DATE)

    assert list(prepared.columns) == [ID_COLUMN, *INTAKE_COLUMNS, TARGET]
    assert list(prepared[TARGET]) == [True, False, False]
    assert report.rows_in == 5
    assert report.dropped_reporting_agencies == 1
    assert report.dropped_too_recent == 1
    assert report.rows_out == 3
