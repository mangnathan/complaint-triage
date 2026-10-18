"""Évalue les réponses du RAG, dans le corpus (bonne citation ?) et hors corpus (refus ?).

Sans --execute, le script compte seulement les appels nécessaires (les réponses déjà en cache ne
coûtent rien) et s'arrête. Il refuse de lancer si l'estimation dépasse ce qu'il reste du plafond
du jour.

Règle de choix fixée avant de lancer, sur le développement : parmi les nombres de passages lus
dont le taux de refus hors corpus atteint 95 %, le plus grand nombre de réponses correctes, puis
le plus petit nombre de passages (moins de texte envoyé).

Usage :
  python scripts/rag/evaluate_answers.py --part developpement -k 5 10
  python scripts/rag/evaluate_answers.py --part developpement -k 5 10 --execute
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from complaint_triage.rag.__main__ import PASSAGES_FILE
from complaint_triage.rag.answer import (
    RESPONSE_SCHEMA,
    SYSTEM_PROMPT,
    answer_question,
    build_prompt,
    validate_question,
)
from complaint_triage.rag.embeddings import EMBEDDING_MODEL, FastEmbedder, cached_passage_vectors
from complaint_triage.rag.evaluation import (
    CORRECT,
    DEVELOPMENT,
    OTHER_SOURCE,
    REFUSAL,
    TEST,
    WRONGLY_ANSWERED,
    classify,
    load_questions,
)
from complaint_triage.rag.llm import (
    CachedModel,
    GeminiModel,
    QuotaExceededError,
    QuotaGuard,
    load_dotenv,
)
from complaint_triage.rag.passages import passages_by_id
from complaint_triage.rag.retrieval import DenseIndex

IN_CORPUS = Path("evaluation/rag/questions-recherche.csv")
OUT_OF_CORPUS = Path("evaluation/rag/questions-hors-corpus.csv")
REFUSAL_TARGET = 0.95


def summarize(results: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for k, group in results.groupby("k"):
        inside = group[group["type"] == "dans le corpus"]
        outside = group[group["type"] == "hors corpus"]
        answered = group[group["statut"] == "repondu"]
        rows.append(
            {
                "k": k,
                "questions_dans_le_corpus": len(inside),
                "correctes": int((inside["classe"] == CORRECT).sum()),
                "autre_source": int((inside["classe"] == OTHER_SOURCE).sum()),
                "refus_a_tort": int((inside["classe"] == REFUSAL).sum()),
                "questions_hors_corpus": len(outside),
                "refus_hors_corpus": int((outside["classe"] == REFUSAL).sum()),
                "taux_refus_hors_corpus": float((outside["classe"] == REFUSAL).mean()),
                "reponses_avec_source": int((answered["sources"] != "").sum()),
                "reponses": len(answered),
            }
        )
    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--part", choices=(DEVELOPMENT, TEST), required=True)
    parser.add_argument("-k", type=int, nargs="+", default=[5])
    parser.add_argument("--execute", action="store_true", help="appeler réellement Gemini")
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--out", type=Path, default=Path("docs/v0.2-rag/data"))
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

    inside = load_questions(IN_CORPUS)
    outside = load_questions(OUT_OF_CORPUS)
    inside = inside[inside["partie"] == args.part]
    outside = outside[outside["partie"] == args.part]
    # (identifiant, type, question, passages attendus ; aucun pour une question hors corpus)
    questions: list[tuple[str, str, str, list[str] | None]] = [
        *(
            (str(qid), "dans le corpus", str(text), [str(p) for p in expected])
            for qid, text, expected in zip(
                inside["id"], inside["question"], inside["attendus"], strict=True
            )
        ),
        *(
            (str(qid), "hors corpus", str(text), None)
            for qid, text in zip(outside["id"], outside["question"], strict=True)
        ),
    ]

    needed = 0
    for k in args.k:
        for _, _, question, _ in questions:
            cleaned = validate_question(question)
            hits = retriever.search(cleaned, k)
            prompt = build_prompt(cleaned, [by_id[h.passage_id] for h in hits])
            needed += not model.is_cached(SYSTEM_PROMPT, prompt, RESPONSE_SCHEMA)
    remaining = guard.daily_cap - guard.used_today()
    print(
        f"{len(questions)} questions × {len(args.k)} réglage(s) : {needed} appel(s) nécessaire(s)"
    )
    print(f"Plafond du jour : {guard.used_today()} utilisés, {remaining} restants")
    if not args.execute:
        print("Estimation seulement : relancer avec --execute pour appeler Gemini.")
        return
    if needed > remaining:
        raise SystemExit("Estimation supérieure au plafond restant : rien n'est lancé.")

    rows = []
    try:
        for k in args.k:
            for qid, kind, question, expected in questions:
                answer = answer_question(question, retriever, by_id, model, k=k)
                rows.append(
                    {
                        "id": qid,
                        "type": kind,
                        "k": k,
                        "statut": answer.status,
                        "classe": classify(answer, expected),
                        "reponse": answer.text,
                        "sources": ";".join(s.passage_id for s in answer.sources),
                        "extraits": json.dumps([s.quote for s in answer.sources]),
                        "raison_du_refus": answer.reason,
                        "passages_lus": ";".join(answer.retrieved),
                        "passages_attendus": ";".join(expected) if expected else "",
                    }
                )
    except QuotaExceededError as error:
        raise SystemExit(f"Arrêt : {error} Les réponses obtenues restent en cache.") from error

    results = pd.DataFrame(rows)
    summary = summarize(results)
    args.out.mkdir(parents=True, exist_ok=True)
    results.to_csv(args.out / f"reponses-{args.part}.csv", index=False)
    summary.to_csv(args.out / f"reponses-resume-{args.part}.csv", index=False)
    with pd.option_context("display.width", 200):
        print(summary.to_string(index=False))
        wrong = results["classe"].isin([OTHER_SOURCE, WRONGLY_ANSWERED])
        print(results.loc[wrong, ["id", "k", "classe", "sources", "passages_attendus"]])
    eligible = summary[summary["taux_refus_hors_corpus"] >= REFUSAL_TARGET]
    if args.part == DEVELOPMENT and not eligible.empty:
        best = eligible.sort_values(["correctes", "k"], ascending=[False, True]).iloc[0]
        print(f"Réglage retenu sur le développement : k = {int(best['k'])}")
    print(f"Plafond du jour : {guard.used_today()} / {guard.daily_cap}")


if __name__ == "__main__":
    main()
