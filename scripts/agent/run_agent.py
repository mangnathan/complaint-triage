"""Pose une demande à l'agent : uv run python scripts/agent/run_agent.py "Show the top 3 ..."

L'agent annonce son plan à chaque tour, puis répond ou refuse. Les appels à Gemini passent par le
cache et le plafond de la v0.2. Pour l'outil d'alerte, lancer d'abord le récepteur local
(scripts/agent/alert_receiver.py) et définir ALERT_WEBHOOK_URL dans .env.
"""

from __future__ import annotations

import argparse
import json
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pandas as pd

from complaint_triage.agent.database import AgentDatabase
from complaint_triage.agent.graph import Agent
from complaint_triage.agent.tools import ToolContext, call_tool
from complaint_triage.rag.__main__ import PASSAGES_FILE
from complaint_triage.rag.answer import Answer, answer_question
from complaint_triage.rag.embeddings import EMBEDDING_MODEL, FastEmbedder, cached_passage_vectors
from complaint_triage.rag.llm import (
    CachedModel,
    GeminiModel,
    LanguageModel,
    QuotaGuard,
    load_dotenv,
)
from complaint_triage.rag.passages import passages_by_id
from complaint_triage.rag.retrieval import DenseIndex

RAG_PASSAGES = 10  # réglage retenu en v0.2


def regulation_answerer(data_dir: Path, model: LanguageModel) -> Callable[[str], Answer]:
    """Le RAG n'est chargé qu'au premier appel : la plupart des demandes n'en ont pas besoin."""
    state: dict[str, Any] = {}

    def ask(question: str) -> Answer:
        if not state:
            passages = pd.read_parquet(data_dir / PASSAGES_FILE)
            documents = (passages["heading"] + "\n" + passages["text"]).tolist()
            embedder = FastEmbedder(cache_dir=data_dir / "models" / "fastembed")
            vectors = cached_passage_vectors(
                embedder, EMBEDDING_MODEL, documents, data_dir / "rag" / "vectors.npz"
            )
            state["retriever"] = DenseIndex(passages["passage_id"].tolist(), vectors, embedder)
            state["passages"] = passages_by_id(passages)
        return answer_question(
            question, state["retriever"], state["passages"], model, k=RAG_PASSAGES
        )

    return ask


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("request")
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    args = parser.parse_args()

    load_dotenv(Path(".env"))
    guard = QuotaGuard(args.data_dir / "rag" / "quota.json")
    model = CachedModel(GeminiModel(guard), args.data_dir / "rag" / "llm-cache")
    context = ToolContext(
        database=AgentDatabase.from_environment(),
        ask_regulations=regulation_answerer(args.data_dir, model),
        alert_url=os.environ.get("ALERT_WEBHOOK_URL", ""),
    )
    agent = Agent(model, lambda name, arguments: call_tool(context, name, arguments))
    run = agent.run(args.request)

    for number, round_ in enumerate(run.rounds, start=1):
        print(f"Tour {number} — plan annoncé : {round_['announcement']}")
        for step in round_["steps"]:
            mark = "ok" if step["ok"] else "ERREUR"
            detail = step["result"] if step["ok"] else step["error"]
            text = json.dumps(detail, ensure_ascii=False, default=str)
            print(f"  [{mark}] {step['tool']}({json.dumps(step['arguments'], ensure_ascii=False)})")
            print(f"        {text[:300]}{'…' if len(text) > 300 else ''}")
    print(f"\n{'Réponse' if run.status == 'repondu' else 'Refus'} : {run.text}")
    used = f"{guard.used_today()} / {guard.daily_cap}"
    print(f"\nAppels Gemini : {run.llm_calls} ; aujourd'hui : {used}")


if __name__ == "__main__":
    main()
