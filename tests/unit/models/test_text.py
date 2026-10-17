from __future__ import annotations

import pandas as pd
import pytest

from complaint_triage.models.text import (
    TfidfTextScorer,
    clean_text,
    deduplicate_texts,
    unseen_texts,
    with_text,
)


def test_clean_text_removes_masks_and_normalizes_amounts() -> None:
    raw = "On XX/XX/2025 XXXX charged me {$34000.00}   twice."

    assert clean_text(raw) == "On / /2025 charged me montant twice."


def test_deduplicate_keeps_the_first_received_copy() -> None:
    df = pd.DataFrame(
        {
            "complaint_id": [1, 2, 3],
            "date_received": pd.to_datetime(["2025-01-03", "2025-01-01", "2025-01-02"]),
            "narrative": ["same letter", "same letter", "unique story"],
        }
    )

    kept, dropped = deduplicate_texts(df)

    assert dropped == 1
    assert sorted(kept["complaint_id"]) == [2, 3]


def test_unseen_texts_flags_only_new_narratives() -> None:
    train = pd.DataFrame({"narrative": ["known letter", "other"]})
    evaluated = pd.DataFrame({"narrative": ["known letter", "brand new"]})

    assert list(unseen_texts(evaluated, train)) == [False, True]


def test_with_text_drops_missing_narratives() -> None:
    df = pd.DataFrame({"narrative": ["story", None]})

    assert len(with_text(df)) == 1


def test_tfidf_scorer_learns_words_linked_to_relief() -> None:
    texts = pd.Series(
        ["unauthorized charge refunded please"] * 50 + ["question about my statement"] * 50
    )
    target = pd.Series([True] * 50 + [False] * 50)

    model = TfidfTextScorer(min_df=1).fit(texts, target)
    scores = model.score(pd.Series(["unauthorized charge", "question about statement"]))
    toward_relief, _ = model.top_terms(3)

    assert scores[0] > scores[1]
    assert any("unauthorized" in term or "charge" in term for term in toward_relief)


def test_score_before_fit_is_refused() -> None:
    with pytest.raises(RuntimeError):
        TfidfTextScorer().score(pd.Series(["text"]))
