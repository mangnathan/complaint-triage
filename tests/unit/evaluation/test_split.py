from __future__ import annotations

from datetime import date

import pandas as pd

from complaint_triage.evaluation.split import (
    TEST,
    TRAIN,
    VALIDATION,
    TemporalSplit,
    assign_period,
    week_of,
)

SPLIT = TemporalSplit(train_end=date(2025, 6, 30), validation_end=date(2025, 12, 31))


def test_periods_follow_each_other_with_inclusive_end_dates() -> None:
    received = pd.Series(pd.to_datetime(["2025-06-30", "2025-07-01", "2025-12-31", "2026-01-01"]))

    assert list(assign_period(received, SPLIT)) == [TRAIN, VALIDATION, VALIDATION, TEST]


def test_every_row_belongs_to_exactly_one_period() -> None:
    received = pd.Series(pd.date_range("2022-01-01", "2026-07-19", freq="D"))
    periods = assign_period(received, SPLIT)

    assert set(periods) == {TRAIN, VALIDATION, TEST}
    assert received[periods == TRAIN].max() < received[periods == VALIDATION].min()
    assert received[periods == VALIDATION].max() < received[periods == TEST].min()


def test_week_groups_monday_to_sunday() -> None:
    received = pd.Series(pd.to_datetime(["2025-01-13", "2025-01-19", "2025-01-20"]))
    weeks = week_of(received)

    assert weeks[0] == weeks[1] != weeks[2]
