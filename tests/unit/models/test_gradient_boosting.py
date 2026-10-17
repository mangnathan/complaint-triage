from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from complaint_triage.models.gradient_boosting import GradientBoostingScorer

FAST = {"n_estimators": 200, "early_stopping_rounds": 20, "min_child_weight": 1}


def synthetic(n: int, seed: int) -> tuple[pd.DataFrame, pd.Series]:
    """Motif « Fees » souvent indemnisé, motif « Other » rarement ; volume sans effet."""
    rng = np.random.default_rng(seed)
    issue = rng.choice(["Fees", "Other"], size=n)
    df = pd.DataFrame(
        {"issue": issue, "state": rng.choice(["CA", "TX", None], size=n), "volume": rng.random(n)}
    )
    y = pd.Series(rng.random(n) < np.where(issue == "Fees", 0.6, 0.05))
    return df, y


def test_learns_an_obvious_signal() -> None:
    train, y = synthetic(4000, seed=0)
    stop, y_stop = synthetic(1000, seed=1)

    model = GradientBoostingScorer(("issue", "state"), ("volume",), FAST).fit(
        train, y, stop, y_stop
    )
    scores = model.score(
        pd.DataFrame({"issue": ["Fees", "Other"], "state": ["CA", "CA"], "volume": [0.5, 0.5]})
    )

    assert scores[0] > scores[1]
    assert ((scores >= 0) & (scores <= 1)).all()


def test_unseen_category_is_scored_without_error() -> None:
    train, y = synthetic(2000, seed=0)
    stop, y_stop = synthetic(500, seed=1)
    model = GradientBoostingScorer(("issue", "state"), ("volume",), FAST).fit(
        train, y, stop, y_stop
    )

    scores = model.score(pd.DataFrame({"issue": ["New issue"], "state": ["ZZ"], "volume": [0.1]}))

    assert np.isfinite(scores).all()


def test_same_seed_gives_same_scores() -> None:
    train, y = synthetic(2000, seed=0)
    stop, y_stop = synthetic(500, seed=1)

    first = GradientBoostingScorer(("issue", "state"), ("volume",), FAST).fit(
        train, y, stop, y_stop
    )
    second = GradientBoostingScorer(("issue", "state"), ("volume",), FAST).fit(
        train, y, stop, y_stop
    )

    np.testing.assert_allclose(first.score(stop), second.score(stop))


def test_contributions_rank_the_informative_variable_first() -> None:
    train, y = synthetic(4000, seed=0)
    stop, y_stop = synthetic(1000, seed=1)
    model = GradientBoostingScorer(("issue", "state"), ("volume",), FAST).fit(
        train, y, stop, y_stop
    )

    contributions = model.contributions(stop)

    assert contributions.index[0] == "issue"
    assert set(contributions.index) == {"issue", "state", "volume"}


def test_using_the_model_before_fit_is_refused() -> None:
    with pytest.raises(RuntimeError):
        GradientBoostingScorer(("issue",)).score(pd.DataFrame({"issue": ["Fees"]}))
