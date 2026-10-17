from __future__ import annotations

from collections.abc import Callable

import pandas as pd
import pandera.errors
import pytest

from complaint_triage.data.schema import validate_complaints

MakeComplaints = Callable[..., pd.DataFrame]


def test_valid_rows_pass(make_complaints: MakeComplaints) -> None:
    validate_complaints(make_complaints())


def test_duplicate_ids_are_rejected(make_complaints: MakeComplaints) -> None:
    with pytest.raises(pandera.errors.SchemaErrors):
        validate_complaints(make_complaints({"complaint_id": 1}, {"complaint_id": 1}))


def test_unknown_response_is_rejected(make_complaints: MakeComplaints) -> None:
    with pytest.raises(pandera.errors.SchemaErrors):
        validate_complaints(make_complaints({"company_response": "Closed"}))


def test_product_outside_scope_is_rejected(make_complaints: MakeComplaints) -> None:
    with pytest.raises(pandera.errors.SchemaErrors):
        validate_complaints(make_complaints({"product": "Mortgage"}))


def test_unexpected_column_is_rejected(make_complaints: MakeComplaints) -> None:
    with pytest.raises(pandera.errors.SchemaErrors):
        validate_complaints(make_complaints().assign(extra_column="x"))
