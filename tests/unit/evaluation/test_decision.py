from __future__ import annotations

from complaint_triage.evaluation.decision import model_beats_reference, text_is_kept
from complaint_triage.evaluation.metrics import Interval


def test_the_model_needs_five_points_and_a_lower_bound_above_zero() -> None:
    assert model_beats_reference(Interval(0.05, 0.01, 0.09))
    assert not model_beats_reference(Interval(0.049, 0.02, 0.08))  # moins de 5 points
    assert not model_beats_reference(Interval(0.06, -0.01, 0.13))  # intervalle qui touche zéro


def test_the_text_needs_two_hundredths_of_pr_auc() -> None:
    assert text_is_kept(0.02)
    assert not text_is_kept(0.019)
