from __future__ import annotations

from datetime import date

import pandas as pd

from complaint_triage.evaluation.split import TEST, TRAIN, VALIDATION
from complaint_triage.models.dataset import (
    FINAL_PERIODS,
    FINAL_STOP_START,
    split_training,
)


def frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date_received": pd.to_datetime(
                ["2025-03-31", "2025-04-01", "2025-09-30", "2025-10-01", "2026-01-05"]
            ),
            "periode": [TRAIN, TRAIN, VALIDATION, VALIDATION, TEST],
        }
    )


def test_training_keeps_its_last_three_months_to_stop_learning() -> None:
    fit, stop = split_training(frame())

    assert list(fit["date_received"].dt.date) == [date(2025, 3, 31)]
    assert list(stop["date_received"].dt.date) == [date(2025, 4, 1)]


def test_final_training_adds_validation_and_never_touches_the_test() -> None:
    fit, stop = split_training(frame(), FINAL_PERIODS, FINAL_STOP_START)

    assert len(fit) == 3
    assert list(stop["date_received"].dt.date) == [date(2025, 10, 1)]
    assert TEST not in set(fit["periode"]) | set(stop["periode"])
