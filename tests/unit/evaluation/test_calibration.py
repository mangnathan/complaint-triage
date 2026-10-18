from __future__ import annotations

import numpy as np
import pytest

from complaint_triage.evaluation.calibration import expected_calibration_error, reliability_table


def test_notes_matching_the_observed_rate_have_no_calibration_error() -> None:
    probabilities = [0.2] * 50 + [0.6] * 50
    labels = [1] * 10 + [0] * 40 + [1] * 30 + [0] * 20

    assert expected_calibration_error(probabilities, labels, n_bins=2) == pytest.approx(0.0)


def test_overconfident_notes_give_the_size_of_the_gap() -> None:
    # Note de 0,5 partout alors que seuls 10 % des dossiers sont indemnisés.
    labels = [1] * 10 + [0] * 90

    assert expected_calibration_error([0.5] * 100, labels) == pytest.approx(0.4)


def test_tied_notes_stay_in_the_same_bin_whatever_the_row_order() -> None:
    probabilities = [0.1] * 60 + [0.3] * 40
    labels = [1] * 6 + [0] * 54 + [1] * 12 + [0] * 28

    table = reliability_table(probabilities, labels, n_bins=4)

    assert list(table["count"]) == [60, 40]
    assert expected_calibration_error(probabilities, labels, n_bins=4) == pytest.approx(0.0)


def test_bins_have_the_same_size_and_go_up() -> None:
    rng = np.random.default_rng(0)
    probabilities = rng.random(1000) ** 3  # notes surtout basses, comme dans les données

    table = reliability_table(probabilities, rng.random(1000) < probabilities, n_bins=10)

    assert (table["count"] == 100).all()
    assert table["predicted"].is_monotonic_increasing
