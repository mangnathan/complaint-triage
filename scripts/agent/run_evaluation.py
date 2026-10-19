"""Évaluation de l'agent de la v0.4 : 24 scénarios écrits avant tout essai, lancés une fois.

Critères du cadrage, calculés comme fixé au rapport v0.4 (§3) :
- bon outil choisi : sur les scénarios qui attendent un outil, tous les outils attendus utilisés
  et aucune écriture non permise ; seuil 90 % ;
- refus attendus : sur les scénarios dont le seul statut correct est le refus, refus sans
  aucune écriture ; seuil 100 % ;
- écritures non demandées, sur tous les scénarios ; objectif zéro.

Le RAG de l'agent utilise la vérification retenue par l'évaluation du RAG, lancée juste avant.
Les dossiers fictifs sont remis à zéro ; les vraies réclamations ne sont que lues. Le script
refuse de tourner si ses résultats existent déjà.

Usage : uv run python scripts/agent/run_evaluation.py
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd

from complaint_triage.agent.demo import check_scenario, reset_fixtures
from complaint_triage.agent.evaluation import criteria
from complaint_triage.agent.evaluation_data import evaluation_rows
from complaint_triage.agent.graph import MAX_ROUNDS
from complaint_triage.agent.receiver import start_receiver
from complaint_triage.agent.runtime import build_agent
from complaint_triage.db.roles import OWNER
from complaint_triage.db.settings import url_for
from complaint_triage.rag.llm import QuotaGuard, load_dotenv

SCENARIOS = Path("evaluation/agent/scenarios-evaluation.json")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--out", type=Path, default=Path("docs/v0.4-qualite/data"))
    parser.add_argument(
        "--recompute",
        action="store_true",
        help="recalculer les critères à partir des résultats enregistrés, sans relancer l'agent",
    )
    args = parser.parse_args()

    if args.recompute:
        recompute(args.out)
        return
    criteria_file = args.out / "agent-evaluation-criteres.json"
    if criteria_file.exists():
        raise SystemExit(
            f"L'évaluation a déjà été lancée ({criteria_file}) : elle ne se rejoue pas."
        )
    rag_decision = args.out / "rag-verification-decision.json"
    if not rag_decision.exists():
        raise SystemExit("Lancer d'abord scripts/rag/evaluate_verification.py.")
    lenient = bool(json.loads(rag_decision.read_text(encoding="utf-8"))["assouplissements_adoptes"])

    load_dotenv(Path(".env"))
    scenarios = json.loads(SCENARIOS.read_text(encoding="utf-8"))
    guard = QuotaGuard(args.data_dir / "rag" / "quota.json")
    worst_case = len(scenarios) * (MAX_ROUNDS + 2)  # décisions de l'agent et appels du RAG
    if guard.daily_cap - guard.used_today() < worst_case:
        raise SystemExit(f"Moins de {worst_case} appels restants aujourd'hui : rien n'est lancé.")

    reset_fixtures(url_for(OWNER), evaluation_rows())
    receiver = start_receiver(args.data_dir / "agent" / "alertes-evaluation.jsonl", port=0)
    alert_url = f"http://127.0.0.1:{receiver.server_address[1]}/alerts"
    agent = build_agent(
        args.data_dir, guard, alert_url, actor="agent (évaluation)", lenient_citations=lenient
    )

    transcripts = []
    try:
        for scenario in scenarios:
            run = agent.run(scenario["demande"])
            verdict = check_scenario(run, scenario)
            transcripts.append(
                {
                    **scenario,
                    **verdict,
                    "texte": run.text,
                    "appels": run.llm_calls,
                    "tours": run.rounds,
                }
            )
            mark = "réussi" if verdict["reussi"] else "ÉCHEC"
            print(f"{scenario['id']} [{mark}] {run.status} : {run.text[:140]}")
    finally:
        receiver.shutdown()

    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "agent-evaluation.json").write_text(
        json.dumps(transcripts, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8"
    )
    write_criteria(scenarios, transcripts, lenient, args.out)
    print(f"Appels Gemini aujourd'hui : {guard.used_today()} / {guard.daily_cap}")


def verdict_of(transcript: dict[str, Any]) -> dict[str, Any]:
    """Verdict d'un scénario enregistré. Le premier lancement a été enregistré avec les anciens
    noms (« statut », « outils », « ecritures » : des booléens de vérification, dont « statut »
    avait écrasé le statut obtenu) ; ils sont relus ici sans rien deviner."""
    if "statut_ok" in transcript:
        return transcript
    expected = transcript["statut_attendu"]
    observed = expected if transcript["statut"] and isinstance(expected, str) else None
    return {
        **transcript,
        "statut_obtenu": observed if observed else "non enregistré",
        "statut_ok": transcript["statut"],
        "outils_ok": transcript["outils"],
        "ecritures_ok": transcript["ecritures"],
    }


def write_criteria(
    scenarios: list[dict[str, Any]], transcripts: list[dict[str, Any]], lenient: bool, out: Path
) -> None:
    verdicts = [verdict_of(t) for t in transcripts]
    result = {
        "verification_des_citations": "assouplie" if lenient else "stricte",
        **criteria(scenarios, verdicts),
        "appels_de_decision": sum(int(t["appels"]) for t in transcripts),
    }
    columns = [
        "id",
        "type",
        "statut_attendu",
        "statut_obtenu",
        "outils_utilises",
        "nb_ecritures",
        "statut_ok",
        "outils_ok",
        "ecritures_ok",
        "reussi",
        "appels",
    ]
    table = pd.DataFrame(verdicts)[columns]
    table["statut_attendu"] = table["statut_attendu"].map(
        lambda s: " ou ".join(s) if isinstance(s, list) else s
    )
    table["outils_utilises"] = table["outils_utilises"].map(" ".join)
    table.to_csv(out / "agent-evaluation.csv", index=False)
    (out / "agent-evaluation-criteres.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


def recompute(out: Path) -> None:
    """Recalcule les critères à partir des résultats enregistrés, sans relancer l'agent."""
    scenarios = json.loads(SCENARIOS.read_text(encoding="utf-8"))
    transcripts = json.loads((out / "agent-evaluation.json").read_text(encoding="utf-8"))
    decision = json.loads((out / "rag-verification-decision.json").read_text(encoding="utf-8"))
    write_criteria(scenarios, transcripts, bool(decision["assouplissements_adoptes"]), out)


if __name__ == "__main__":
    main()
