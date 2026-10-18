"""Mesure de la recherche sur des questions dont on connaît le ou les bons passages."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import pandas as pd

from complaint_triage.rag.retrieval import Retriever

DEVELOPMENT = "developpement"
TEST = "test"
K_VALUES = (1, 3, 5, 10)


def load_questions(path: Path) -> pd.DataFrame:
    questions = pd.read_csv(path)
    questions["attendus"] = questions["passages_attendus"].str.split(";")
    if questions["id"].duplicated().any():
        raise ValueError("Deux questions ont le même identifiant.")
    if not set(questions["partie"]) <= {DEVELOPMENT, TEST}:
        raise ValueError("Chaque question doit appartenir au développement ou au test.")
    return questions


def first_relevant_rank(ranked_ids: Sequence[str], expected: Sequence[str]) -> int | None:
    """Rang (à partir de 1) du premier passage attendu, ou None s'il n'est pas retrouvé."""
    wanted = set(expected)
    for rank, passage_id in enumerate(ranked_ids, start=1):
        if passage_id in wanted:
            return rank
    return None


def rank_questions(retriever: Retriever, questions: pd.DataFrame, depth: int = 10) -> pd.Series:
    """Rang du premier bon passage pour chaque question ; vide s'il n'est pas dans les `depth`."""
    ranks = [
        first_relevant_rank([h.passage_id for h in retriever.search(q, depth)], expected)
        for q, expected in zip(questions["question"], questions["attendus"], strict=True)
    ]
    return pd.Series(ranks, index=questions["id"], dtype="Int64", name="rang")


def summarize(ranks: pd.Series, k_values: Sequence[int] = K_VALUES) -> dict[str, float]:
    """Rappel@k (part des questions dont un bon passage est dans les k premiers) et MRR."""
    found = ranks.dropna().astype(int)
    summary = {f"rappel@{k}": float((found <= k).sum() / len(ranks)) for k in k_values}
    summary["mrr"] = float((1 / found).sum() / len(ranks))
    return summary
