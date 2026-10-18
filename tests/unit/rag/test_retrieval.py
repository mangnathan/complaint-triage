from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import numpy as np
import numpy.typing as npt
import pytest

from complaint_triage.rag.embeddings import cached_passage_vectors
from complaint_triage.rag.retrieval import (
    Bm25Index,
    DenseIndex,
    Hit,
    HybridRetriever,
    reciprocal_rank_fusion,
    tokenize,
)

IDS = ["1005.11(c)", "1005.6(b)", "1026.13(b)"]
TEXTS = [
    "The institution shall investigate promptly and determine whether an error occurred "
    "within 10 business days.",
    "The consumer's liability for an unauthorized transfer shall not exceed $50.",
    "A billing error notice must be received within 60 days of the statement.",
]
VOCABULARY = ["investigate", "liability", "billing"]


class KeywordEmbedder:
    """Faux modèle : un vecteur par mot du vocabulaire, présent ou non dans le texte."""

    def __init__(self) -> None:
        self.calls = 0

    def _vector(self, text: str) -> npt.NDArray[np.float64]:
        words = set(tokenize(text))
        return np.array([float(word in words) for word in VOCABULARY])

    def embed_passages(self, texts: Sequence[str]) -> npt.NDArray[np.float64]:
        self.calls += 1
        return np.array([self._vector(t) for t in texts])

    def embed_query(self, text: str) -> npt.NDArray[np.float64]:
        return self._vector(text)


def test_stopwords_and_case_are_ignored() -> None:
    assert tokenize("What is THE Liability of a consumer?") == ["liability", "consumer"]


def test_bm25_ranks_the_passage_with_the_rare_words_first() -> None:
    hits = Bm25Index(IDS, TEXTS).search("liability for unauthorized transfer", k=3)

    assert hits[0].passage_id == "1005.6(b)"
    assert hits[0].score > hits[1].score


def test_bm25_returns_zero_scores_for_unknown_words() -> None:
    hits = Bm25Index(IDS, TEXTS).search("mortgage escrow", k=3)

    assert all(hit.score == 0 for hit in hits)
    assert [hit.passage_id for hit in hits] == IDS  # à égalité, l'ordre du corpus


def test_dense_index_finds_the_closest_meaning() -> None:
    embedder = KeywordEmbedder()
    index = DenseIndex(IDS, embedder.embed_passages(TEXTS), embedder)

    assert index.search("how long to investigate?", k=1)[0].passage_id == "1005.11(c)"


def test_fusion_favours_passages_ranked_well_by_both_methods() -> None:
    first = [Hit("a", 9.0), Hit("b", 8.0), Hit("c", 7.0)]
    second = [Hit("b", 0.9), Hit("c", 0.8), Hit("a", 0.1)]

    fused = reciprocal_rank_fusion([first, second], k=3)

    assert fused[0].passage_id == "b"


def test_hybrid_combines_the_two_methods() -> None:
    embedder = KeywordEmbedder()
    hybrid = HybridRetriever(
        [Bm25Index(IDS, TEXTS), DenseIndex(IDS, embedder.embed_passages(TEXTS), embedder)]
    )

    assert hybrid.search("billing error notice", k=1)[0].passage_id == "1026.13(b)"


def test_mismatched_inputs_are_refused() -> None:
    with pytest.raises(ValueError, match="Autant"):
        Bm25Index(IDS, TEXTS[:2])


def test_vectors_are_computed_once_then_read_from_disk(tmp_path: Path) -> None:
    embedder = KeywordEmbedder()
    cache = tmp_path / "vectors.npz"

    first = cached_passage_vectors(embedder, "fake", TEXTS, cache)
    second = cached_passage_vectors(embedder, "fake", TEXTS, cache)
    cached_passage_vectors(embedder, "fake", [*TEXTS, "new passage"], cache)

    assert embedder.calls == 2  # une fois au départ, une fois quand le corpus change
    np.testing.assert_array_equal(first, second)
