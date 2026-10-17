from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from complaint_triage.evaluation.metrics import (
    bootstrap_capture,
    capture_at,
    capture_by_group,
    expected_captured,
)


def test_perfect_ranking_captures_as_many_positives_as_capacity_allows() -> None:
    labels = [1] * 5 + [0] * 95
    scores = list(range(100, 0, -1))  # les 5 positifs ont les meilleures notes

    assert capture_at(scores, labels, share=0.10) == pytest.approx(1.0)
    assert capture_at(scores, labels, share=0.02) == pytest.approx(2 / 5)


def test_identical_scores_capture_exactly_the_share() -> None:
    # Toutes les notes égales : le classement ne vaut pas mieux que le hasard.
    labels = [1] * 13 + [0] * 87
    assert capture_at([0.5] * 100, labels, share=0.10) == pytest.approx(0.10)


def test_ties_at_the_limit_count_their_expected_share() -> None:
    # 2 places ; le premier dossier est seul en tête, puis 4 ex æquo dont 2 positifs.
    # Une place reste pour les 4 ex æquo : on capte en moyenne 2 x 1/4 = 0,5 positif.
    captured = expected_captured([0.9, 0.5, 0.5, 0.5, 0.5], [1, 1, 1, 0, 0], capacity=2)
    assert captured == pytest.approx(1.5)


def test_capture_is_computed_week_by_week_then_pooled() -> None:
    scores = [0.9, 0.1, 0.9, 0.1]
    labels = [1, 0, 0, 1]
    weeks = ["s1", "s1", "s2", "s2"]

    # 50 % de la file par semaine : semaine 1 capte son positif, semaine 2 le manque.
    assert capture_at(scores, labels, groups=weeks, share=0.5) == pytest.approx(0.5)


def test_ranking_within_queues_ignores_differences_between_queues() -> None:
    # Banque A : notes élevées, aucun positif. Banque B : notes basses, un positif sur dix.
    # Classées ensemble, les 10 % du haut viennent tous de A et ne captent rien.
    # Classées chacune dans sa file, B traite d'abord son dossier le mieux noté, qui est le bon.
    scores = [0.9] * 10 + [0.2] + [0.1] * 9
    labels = [0] * 10 + [1] + [0] * 9
    banks = ["A"] * 10 + ["B"] * 10

    assert capture_at(scores, labels, share=0.10) == pytest.approx(0.0)
    assert capture_at(scores, labels, share=0.10, queues=banks) == pytest.approx(1.0)


def test_queues_are_summed_back_into_one_row_per_week() -> None:
    table = capture_by_group(
        [0.9, 0.1, 0.9, 0.1],
        [1, 0, 0, 1],
        groups=["s1"] * 4,
        share=0.5,
        queues=["A", "A", "B", "B"],
    )

    assert list(table["group"]) == ["s1"]
    assert table["positives"].iloc[0] == 2


def test_bootstrap_interval_contains_the_estimate_and_is_reproducible() -> None:
    rng = np.random.default_rng(1)
    labels = rng.random(5000) < 0.15
    scores = labels + rng.normal(0, 1, 5000)
    weeks = np.repeat(np.arange(50), 100)
    by_week = capture_by_group(scores, labels, weeks)

    first = bootstrap_capture(by_week, seed=3)
    second = bootstrap_capture(by_week, seed=3)

    assert first == second
    assert first.low < first.estimate < first.high


def test_paired_bootstrap_measures_the_gain_over_a_baseline() -> None:
    rng = np.random.default_rng(2)
    labels = rng.random(5000) < 0.15
    weeks = np.repeat(np.arange(50), 100)
    good = capture_by_group(labels + rng.normal(0, 0.5, 5000), labels, weeks)
    random = capture_by_group(rng.random(5000), labels, weeks)

    gain = bootstrap_capture(good, baseline=random, seed=0)

    assert gain.low > 0


def test_paired_bootstrap_refuses_different_weeks() -> None:
    a = pd.DataFrame({"group": [1, 2], "captured": [1.0, 1.0], "positives": [2.0, 2.0]})
    b = pd.DataFrame({"group": [1, 3], "captured": [1.0, 1.0], "positives": [2.0, 2.0]})
    with pytest.raises(ValueError):
        bootstrap_capture(a, baseline=b)
