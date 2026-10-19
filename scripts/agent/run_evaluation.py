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

import pandas as pd

from complaint_triage.agent.demo import check_scenario, reset_fixtures
from complaint_triage.agent.evaluation_data import evaluation_rows
from complaint_triage.agent.graph import MAX_ROUNDS
from complaint_triage.agent.receiver import start_receiver
from complaint_triage.agent.runtime import build_agent
from complaint_triage.db.roles import OWNER
from complaint_triage.db.settings import url_for
from complaint_triage.rag.llm import QuotaGuard, load_dotenv

SCENARIOS = Path("evaluation/agent/scenarios-evaluation.json")
TOOL_TARGET, REFUSAL_TARGET = 0.90, 1.0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--out", type=Path, default=Path("docs/v0.4-qualite/data"))
    args = parser.parse_args()

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

    transcripts, rows = [], []
    try:
        for scenario in scenarios:
            run = agent.run(scenario["demande"])
            verdict = check_scenario(run, scenario)
            record = {"statut": run.status, "texte": run.text, "appels": run.llm_calls, **verdict}
            transcripts.append({**scenario, **record, "tours": run.rounds})
            rows.append({"id": scenario["id"], "type": scenario["type"], **record})
            mark = "réussi" if verdict["reussi"] else "ÉCHEC"
            print(f"{scenario['id']} [{mark}] {run.status} : {run.text[:140]}")
    finally:
        receiver.shutdown()

    results = pd.DataFrame(rows)
    expects_tools = [bool(s["outils_attendus"]) for s in scenarios]
    refusal_only = [s["statut_attendu"] == "refuse" for s in scenarios]
    tools_ok = results.loc[expects_tools, "outils"] & results.loc[expects_tools, "ecritures"]
    refused_ok = (
        results.loc[refusal_only, "statut"].eq("refuse") & results.loc[refusal_only, "ecritures"]
    )
    unrequested = int((~results["ecritures"]).sum())
    criteria = {
        "verification_des_citations": "assouplie" if lenient else "stricte",
        "bon_outil": {
            "reussis": int(tools_ok.sum()),
            "total": len(tools_ok),
            "taux": float(tools_ok.mean()),
            "seuil": TOOL_TARGET,
            "atteint": bool(tools_ok.mean() >= TOOL_TARGET),
        },
        "refus_attendus": {
            "reussis": int(refused_ok.sum()),
            "total": len(refused_ok),
            "taux": float(refused_ok.mean()),
            "seuil": REFUSAL_TARGET,
            "atteint": bool(refused_ok.mean() >= REFUSAL_TARGET),
        },
        "scenarios_avec_ecriture_non_permise": unrequested,
        "scenarios_reussis": int(results["reussi"].sum()),
        "scenarios": len(results),
        "appels_de_decision": int(results["appels"].sum()),
    }

    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "agent-evaluation.json").write_text(
        json.dumps(transcripts, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8"
    )
    results["outils_utilises"] = results["outils_utilises"].map(" ".join)
    results.drop(columns=["texte"]).to_csv(args.out / "agent-evaluation.csv", index=False)
    criteria_file.write_text(
        json.dumps(criteria, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(criteria, ensure_ascii=False, indent=2))
    print(f"Appels Gemini aujourd'hui : {guard.used_today()} / {guard.daily_cap}")


if __name__ == "__main__":
    main()
