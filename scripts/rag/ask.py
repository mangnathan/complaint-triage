"""Pose une question au RAG : python scripts/rag/ask.py "How long to investigate a disputed debit?"

Les réponses sont gardées en cache : poser deux fois la même question ne coûte qu'un appel. Le
nombre d'appels du jour est affiché à la fin, face au plafond fixé dans le code.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from complaint_triage.rag.__main__ import PASSAGES_FILE
from complaint_triage.rag.answer import ANSWERED, answer_question
from complaint_triage.rag.embeddings import EMBEDDING_MODEL, FastEmbedder, cached_passage_vectors
from complaint_triage.rag.llm import CachedModel, GeminiModel, QuotaGuard, load_dotenv
from complaint_triage.rag.passages import passages_by_id
from complaint_triage.rag.retrieval import DenseIndex


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("question")
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("-k", type=int, default=5, help="nombre de passages lus par le modèle")
    args = parser.parse_args()

    load_dotenv(Path(".env"))
    passages = pd.read_parquet(args.data_dir / PASSAGES_FILE)
    documents = (passages["heading"] + "\n" + passages["text"]).tolist()
    embedder = FastEmbedder(cache_dir=args.data_dir / "models" / "fastembed")
    vectors = cached_passage_vectors(
        embedder, EMBEDDING_MODEL, documents, args.data_dir / "rag" / "vectors.npz"
    )
    retriever = DenseIndex(passages["passage_id"].tolist(), vectors, embedder)
    by_id = passages_by_id(passages)

    guard = QuotaGuard(args.data_dir / "rag" / "quota.json")
    model = CachedModel(GeminiModel(guard), args.data_dir / "rag" / "llm-cache")
    answer = answer_question(args.question, retriever, by_id, model, k=args.k)

    if answer.status == ANSWERED:
        print(answer.text, "\n")
        for source in answer.sources:
            print(f"- {source.citation} : « {source.quote} »\n  {source.url}")
    else:
        print(f"Refus : {answer.reason}")
    print(f"\nPassages lus : {', '.join(answer.retrieved)}")
    print(f"Appels Gemini aujourd'hui : {guard.used_today()} / {guard.daily_cap}")


if __name__ == "__main__":
    main()
