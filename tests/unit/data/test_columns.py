from __future__ import annotations

from collections.abc import Callable

import pandas as pd

from complaint_triage.data.columns import (
    ID_COLUMN,
    INTAKE_COLUMNS,
    POST_INTAKE_COLUMNS,
    RESPONSE_COLUMN,
    intake_view,
)
from complaint_triage.data.schema import COMPLAINTS_SCHEMA


def test_every_column_of_the_dataset_has_exactly_one_role() -> None:
    # Si une colonne est ajoutée au jeu de données, ce test oblige à décider si elle est connue
    # à la réception ou seulement après : une fuite ne peut pas entrer par oubli.
    roles = [ID_COLUMN, RESPONSE_COLUMN, *INTAKE_COLUMNS, *POST_INTAKE_COLUMNS]
    assert len(roles) == len(set(roles))
    assert set(roles) == set(COMPLAINTS_SCHEMA.columns)


def test_intake_view_hides_outcome_and_post_intake_columns(
    make_complaints: Callable[..., pd.DataFrame],
) -> None:
    columns = set(intake_view(make_complaints()).columns)

    assert RESPONSE_COLUMN not in columns
    assert columns.isdisjoint(POST_INTAKE_COLUMNS)
