from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from complaint_triage.evaluation.fairness import cadrage_subgroups, compare_subgroup
from complaint_triage.evaluation.metrics import selection_in_queues


def test_identical_scores_treat_every_group_the_same() -> None:
    rng = np.random.default_rng(0)
    labels = rng.random(4000) < 0.15
    in_group = rng.random(4000) < 0.1
    weeks = np.repeat(np.arange(20), 200)
    selected = selection_in_queues(np.zeros(4000), weeks)

    result = compare_subgroup(selected, labels, in_group, weeks)

    assert result.ratio.estimate == pytest.approx(1.0)
    assert result.within_range


def test_a_ranking_that_pushes_a_group_back_gives_a_ratio_below_one() -> None:
    rng = np.random.default_rng(1)
    labels = rng.random(4000) < 0.15
    in_group = rng.random(4000) < 0.2
    weeks = np.repeat(np.arange(20), 200)
    # Le classement repère bien les positifs, sauf ceux du groupe, relégués en fin de file.
    scores = labels.astype(float) - 2 * (labels & in_group)
    selected = selection_in_queues(scores, weeks)

    result = compare_subgroup(selected, labels, in_group, weeks)

    assert result.capture_group == pytest.approx(0.0)
    assert result.capture_rest > 0.5
    assert not result.within_range
    assert result.ratio.low <= result.ratio.estimate <= result.ratio.high


def test_a_complaint_with_both_tags_counts_in_both_groups() -> None:
    frame = pd.DataFrame(
        {
            "tags": ["Older American, Servicemember", None, "Servicemember"],
            "product": ["Credit card", "Checking or savings account", "Credit card"],
        }
    )

    groups = cadrage_subgroups(frame)

    assert list(groups["Older American"]) == [True, False, False]
    assert list(groups["Servicemember"]) == [True, False, True]
    assert list(groups["Cartes de crédit"]) == [True, False, True]


def test_a_group_without_positive_is_refused() -> None:
    with pytest.raises(ValueError, match="au moins une"):
        compare_subgroup([1.0, 0.0], [1, 0], [False, True], ["s1", "s1"])
