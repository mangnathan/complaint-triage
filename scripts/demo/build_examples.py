"""Construit les exemples enregistrés de la démo, à partir des évaluations de la v0.4.

Les réponses du RAG sont relues dans le cache avec un faux modèle qui refuse tout appel : si un
exemple n'est pas en cache, le script s'arrête au lieu de consommer du quota. Les parcours de
l'agent viennent tels quels de l'évaluation enregistrée. Seuls des exemples sur les banques
fictives et des textes réglementaires publics sont retenus : aucune donnée de réclamation réelle
n'entre dans le dépôt GitHub.

Usage : uv run python scripts/demo/build_examples.py
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd

from complaint_triage.rag.__main__ import PASSAGES_FILE
from complaint_triage.rag.answer import ANSWERED, answer_question
from complaint_triage.rag.embeddings import EMBEDDING_MODEL, FastEmbedder, cached_passage_vectors
from complaint_triage.rag.llm import CachedModel
from complaint_triage.rag.passages import passages_by_id
from complaint_triage.rag.retrieval import DenseIndex

MODEL_NAME = "gemini-3.5-flash-lite"
RAG_EXAMPLES = {
    "r08": "Frais pour un paiement par téléphone",
    "r11": "Carte de crédit à 19 ans",
    "r14": "Erreur de facturation reconnue",
    "n04": "Hors du corpus : assurance d'un compte joint",
}
AGENT_EXAMPLES = {
    "e05": "Lecture : le dossier fait-il partie des 10 % prioritaires ?",
    "e08": "Réglementation : carte de débit perdue",
    "e10": "Écriture demandée : passer un dossier en cours",
    "e14": "Refus : décider d'un remboursement",
    "e20": "Manipulation déjouée : instruction cachée dans un récit",
    "e24": "Manipulation déjouée : instruction cachée dans un nom de banque",
}


class CacheOnly:
    """Faux modèle : toute question absente du cache arrête le script, sans appel."""

    name = MODEL_NAME

    def generate(self, system: str, prompt: str, schema: dict[str, Any]) -> str:
        raise SystemExit("Exemple absent du cache : aucun appel n'est fait, choisir un autre.")


def rag_examples(data_dir: Path) -> list[dict[str, Any]]:
    questions = pd.concat(
        [
            pd.read_csv("evaluation/rag/questions-recherche-v2.csv"),
            pd.read_csv("evaluation/rag/questions-hors-corpus-v2.csv"),
        ]
    ).set_index("id")
    passages = pd.read_parquet(data_dir / PASSAGES_FILE)
    documents = (passages["heading"] + "\n" + passages["text"]).tolist()
    embedder = FastEmbedder(cache_dir=data_dir / "models" / "fastembed")
    vectors = cached_passage_vectors(
        embedder, EMBEDDING_MODEL, documents, data_dir / "rag" / "vectors.npz"
    )
    retriever = DenseIndex(passages["passage_id"].tolist(), vectors, embedder)
    model = CachedModel(CacheOnly(), data_dir / "rag" / "llm-cache")
    examples = []
    for qid, title in RAG_EXAMPLES.items():
        question = str(questions.at[qid, "question"])
        answer = answer_question(
            question, retriever, passages_by_id(passages), model, k=10, lenient=True
        )
        examples.append(
            {
                "titre": title,
                "question": question,
                "repondu": answer.status == ANSWERED,
                "texte": answer.text if answer.status == ANSWERED else answer.reason,
                "sources": [
                    {"citation": s.citation, "extrait": s.quote, "lien": s.url}
                    for s in answer.sources
                ],
            }
        )
    return examples


def agent_examples(evaluation: Path) -> list[dict[str, Any]]:
    runs = {r["id"]: r for r in json.loads(evaluation.read_text(encoding="utf-8"))}
    examples = []
    for sid, title in AGENT_EXAMPLES.items():
        run = runs[sid]
        if not run["reussi"]:
            raise SystemExit(f"Le scénario {sid} n'a pas réussi : il ne sert pas d'exemple.")
        examples.append(
            {
                "titre": title,
                "demande": run["demande"],
                # Tous les scénarios retenus sont réussis : le statut obtenu est l'attendu.
                "repondu": run["statut_attendu"] == "repondu",
                "texte": run["texte"],
                "tours": run["tours"],
            }
        )
    return examples


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument(
        "--evaluation", type=Path, default=Path("docs/v0.4-qualite/data/agent-evaluation.json")
    )
    parser.add_argument("--out", type=Path, default=Path("src/complaint_triage/demo/examples.json"))
    args = parser.parse_args()
    examples = {"rag": rag_examples(args.data_dir), "agent": agent_examples(args.evaluation)}
    args.out.write_text(
        json.dumps(examples, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8"
    )
    print(f"{len(examples['rag'])} exemples du RAG et {len(examples['agent'])} de l'agent.")


if __name__ == "__main__":
    main()
