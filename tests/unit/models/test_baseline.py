from __future__ import annotations

import pandas as pd
import pytest

from complaint_triage.models.baseline import RateBaseline


def complaints(rows: list[tuple[str, str, str | None, bool]]) -> tuple[pd.DataFrame, pd.Series]:
    df = pd.DataFrame(rows, columns=["product", "issue", "sub_issue", "relief"])
    return df.drop(columns="relief"), df["relief"]


def test_frequent_category_scores_close_to_its_own_rate() -> None:
    rows = [("Card", "Fees", "Late fee", True)] * 300 + [("Card", "Fees", "Late fee", False)] * 700
    rows += [("Card", "Other", None, False)] * 1000
    df, y = complaints(rows)

    model = RateBaseline().fit(df, y)
    score = model.score(df.head(1))[0]

    assert score == pytest.approx(0.30, abs=0.01)


def test_rare_category_is_pulled_toward_its_parent() -> None:
    rows = [("Card", "Fees", "Late fee", False)] * 1000
    rows += [("Card", "Fees", "Rare", True)] * 2  # 2 sur 2 indemnisées : 100 % sans lissage
    df, y = complaints(rows)

    model = RateBaseline(prior_weight=20).fit(df, y)
    rare = model.score(pd.DataFrame([{"product": "Card", "issue": "Fees", "sub_issue": "Rare"}]))[0]

    assert rare < 0.15


def test_unseen_category_falls_back_on_its_parent_rate() -> None:
    rows = [("Card", "Fees", "Late fee", True)] * 400 + [("Card", "Fees", "Late fee", False)] * 600
    df, y = complaints(rows)

    model = RateBaseline().fit(df, y)
    seen = model.score(df.head(1))[0]
    unseen = model.score(
        pd.DataFrame([{"product": "Card", "issue": "Fees", "sub_issue": "New sub-issue"}])
    )[0]

    assert unseen == pytest.approx(seen, abs=0.01)


def test_missing_sub_issue_is_a_category_of_its_own() -> None:
    rows = [("Card", "Fees", None, True)] * 500 + [("Card", "Fees", "Late fee", False)] * 500
    df, y = complaints(rows)

    scores = RateBaseline().fit(df, y).score(df)

    assert scores[0] > scores[-1]


def test_score_before_fit_is_refused() -> None:
    with pytest.raises(RuntimeError):
        RateBaseline().score(pd.DataFrame({"product": ["Card"]}))
