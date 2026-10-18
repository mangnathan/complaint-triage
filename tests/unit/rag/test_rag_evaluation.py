from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from complaint_triage.rag.evaluation import (
    first_relevant_rank,
    load_questions,
    rank_questions,
    summarize,
)
from complaint_triage.rag.retrieval import Hit


class FixedRetriever:
    def __init__(self, ranking: list[str]) -> None:
        self.ranking = ranking

    def search(self, query: str, k: int) -> list[Hit]:
        return [Hit(p, 1.0) for p in self.ranking[:k]]


def test_any_expected_passage_counts() -> None:
    assert first_relevant_rank(["x", "b", "a"], ["a", "b"]) == 2
    assert first_relevant_rank(["x", "y"], ["a"]) is None


def test_recall_and_mrr() -> None:
    ranks = pd.Series([1, 3, None], dtype="Int64")

    summary = summarize(ranks, k_values=(1, 5))

    assert summary["rappel@1"] == pytest.approx(1 / 3)
    assert summary["rappel@5"] == pytest.approx(2 / 3)
    assert summary["mrr"] == pytest.approx((1 + 1 / 3) / 3)


def test_rank_questions_uses_the_retriever(tmp_path: Path) -> None:
    path = tmp_path / "questions.csv"
    path.write_text(
        "id,partie,reglement,question,passages_attendus\n"
        "q1,developpement,Regulation E,Question one?,b\n"
        "q2,test,Regulation E,Question two?,z;c\n",
        encoding="utf-8",
    )

    ranks = rank_questions(FixedRetriever(["a", "b", "c"]), load_questions(path), depth=10)

    assert ranks.to_dict() == {"q1": 2, "q2": 3}


def test_a_question_outside_both_parts_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "questions.csv"
    path.write_text(
        "id,partie,reglement,question,passages_attendus\nq1,autre,Regulation E,Q?,a\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="développement ou au test"):
        load_questions(path)
