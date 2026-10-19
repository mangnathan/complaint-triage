"""Mesure les assouplissements de la vérification des citations, sur les questions de la v0.4.

Chaque question n'est posée qu'une fois à Gemini : la même réponse, relue dans le cache, est
vérifiée de façon stricte puis assouplie. Règle fixée avant le lancement (rapport v0.4, §3) :
les assouplissements sont adoptés s'ils donnent au moins autant de réponses correctes, gardent
au moins 95 % de refus hors corpus et n'introduisent aucune réponse citant une mauvaise source.
Le script refuse de tourner si ses résultats existent déjà.

Usage : uv run python scripts/rag/evaluate_verification.py
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from complaint_triage.rag.__main__ import PASSAGES_FILE
from complaint_triage.rag.answer import answer_question
from complaint_triage.rag.embeddings import EMBEDDING_MODEL, FastEmbedder, cached_passage_vectors
from complaint_triage.rag.evaluation import CORRECT, OTHER_SOURCE, REFUSAL, classify, load_questions
from complaint_triage.rag.llm import CachedModel, GeminiModel, QuotaGuard, load_dotenv
from complaint_triage.rag.passages import passages_by_id
from complaint_triage.rag.retrieval import DenseIndex

IN_CORPUS = Path("evaluation/rag/questions-recherche-v2.csv")
OUT_OF_CORPUS = Path("evaluation/rag/questions-hors-corpus-v2.csv")
PASSAGES_READ = 10
REFUSAL_TARGET = 0.95
MODES = {"stricte": False, "assouplie": True}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--out", type=Path, default=Path("docs/v0.4-qualite/data"))
    args = parser.parse_args()

    decision_file = args.out / "rag-verification-decision.json"
    if decision_file.exists():
        raise SystemExit(
            f"L'évaluation a déjà été lancée ({decision_file}) : elle ne se rejoue pas."
        )
    load_dotenv(Path(".env"))
    guard = QuotaGuard(args.data_dir / "rag" / "quota.json")
    inside, outside = load_questions(IN_CORPUS), load_questions(OUT_OF_CORPUS)
    if guard.daily_cap - guard.used_today() < len(inside) + len(outside):
        raise SystemExit("Plafond du jour insuffisant : rien n'est lancé.")

    passages = pd.read_parquet(args.data_dir / PASSAGES_FILE)
    documents = (passages["heading"] + "\n" + passages["text"]).tolist()
    embedder = FastEmbedder(cache_dir=args.data_dir / "models" / "fastembed")
    vectors = cached_passage_vectors(
        embedder, EMBEDDING_MODEL, documents, args.data_dir / "rag" / "vectors.npz"
    )
    retriever = DenseIndex(passages["passage_id"].tolist(), vectors, embedder)
    by_id = passages_by_id(passages)
    model = CachedModel(GeminiModel(guard), args.data_dir / "rag" / "llm-cache")

    questions: list[tuple[str, str, str, list[str] | None]] = [
        *(
            (str(i), "dans le corpus", str(q), [str(p) for p in e])
            for i, q, e in zip(inside["id"], inside["question"], inside["attendus"], strict=True)
        ),
        *(
            (str(i), "hors corpus", str(q), None)
            for i, q in zip(outside["id"], outside["question"], strict=True)
        ),
    ]
    rows = []
    for qid, kind, question, expected in questions:
        for mode, lenient in MODES.items():
            answer = answer_question(
                question, retriever, by_id, model, k=PASSAGES_READ, lenient=lenient
            )
            rows.append(
                {
                    "id": qid,
                    "type": kind,
                    "verification": mode,
                    "classe": classify(answer, expected),
                    "sources": ";".join(s.passage_id for s in answer.sources),
                    "raison_du_refus": answer.reason,
                    "reponse": answer.text,
                }
            )
    results = pd.DataFrame(rows)

    summary = []
    for mode in MODES:
        part = results[results["verification"] == mode]
        inside_part, outside_part = (
            part[part["type"] == "dans le corpus"],
            part[part["type"] == "hors corpus"],
        )
        summary.append(
            {
                "verification": mode,
                "correctes": int((inside_part["classe"] == CORRECT).sum()),
                "autre_source": int((inside_part["classe"] == OTHER_SOURCE).sum()),
                "refus_a_tort": int((inside_part["classe"] == REFUSAL).sum()),
                "refus_hors_corpus": int((outside_part["classe"] == REFUSAL).sum()),
                "taux_refus_hors_corpus": float((outside_part["classe"] == REFUSAL).mean()),
            }
        )
    table = pd.DataFrame(summary).set_index("verification")
    strict, lenient_row = table.loc["stricte"], table.loc["assouplie"]
    adopted = bool(
        lenient_row["correctes"] >= strict["correctes"]
        and lenient_row["taux_refus_hors_corpus"] >= REFUSAL_TARGET
        and lenient_row["autre_source"] == 0
    )

    args.out.mkdir(parents=True, exist_ok=True)
    results.to_csv(args.out / "rag-verification.csv", index=False)
    table.reset_index().to_csv(args.out / "rag-verification-resume.csv", index=False)
    decision_file.write_text(
        json.dumps(
            {"assouplissements_adoptes": adopted, **{m: table.loc[m].to_dict() for m in MODES}},
            ensure_ascii=False,
            indent=2,
            default=float,
        )
        + "\n",
        encoding="utf-8",
    )
    print(table.to_string())
    print(f"Assouplissements adoptés : {'oui' if adopted else 'non'}")
    print(f"Appels Gemini aujourd'hui : {guard.used_today()} / {guard.daily_cap}")


if __name__ == "__main__":
    main()
