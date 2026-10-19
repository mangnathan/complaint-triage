"""Rejoue les scénarios de démonstration de l'agent et enregistre ce qu'il fait.

Avant la série, les dossiers de la banque fictive sont remis dans leur état initial ; un
récepteur d'alertes local est lancé pour la durée du script. Les vraies réclamations ne sont
que lues. Chaque scénario coûte au plus quatre appels à Gemini : le script refuse de lancer si
le plafond restant du jour ne le permet pas.

Usage : uv run python scripts/agent/run_demonstrations.py
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from complaint_triage.agent.demo import check_scenario, reset_demo
from complaint_triage.agent.graph import MAX_ROUNDS
from complaint_triage.agent.receiver import start_receiver
from complaint_triage.agent.runtime import build_agent
from complaint_triage.db.roles import OWNER
from complaint_triage.db.settings import url_for
from complaint_triage.rag.llm import QuotaGuard, load_dotenv

SCENARIOS = Path("evaluation/agent/scenarios-demonstration.json")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--out", type=Path, default=Path("docs/v0.3-agent/data"))
    args = parser.parse_args()

    load_dotenv(Path(".env"))
    scenarios = json.loads(SCENARIOS.read_text(encoding="utf-8"))
    guard = QuotaGuard(args.data_dir / "rag" / "quota.json")
    worst_case = len(scenarios) * (MAX_ROUNDS + 1)
    if guard.daily_cap - guard.used_today() < worst_case:
        raise SystemExit(f"Moins de {worst_case} appels restants aujourd'hui : rien n'est lancé.")

    reset_demo(url_for(OWNER))
    receiver = start_receiver(args.data_dir / "agent" / "alertes-demonstration.jsonl", port=0)
    alert_url = f"http://127.0.0.1:{receiver.server_address[1]}/alerts"
    agent = build_agent(args.data_dir, guard, alert_url, actor="agent (démonstration)")

    transcripts, rows = [], []
    try:
        for scenario in scenarios:
            run = agent.run(scenario["demande"])
            verdict = check_scenario(run, scenario)
            transcripts.append(
                {
                    **scenario,
                    "statut": run.status,
                    "texte": run.text,
                    "tours": run.rounds,
                    "appels": run.llm_calls,
                    **verdict,
                }
            )
            rows.append(
                {
                    "id": scenario["id"],
                    "type": scenario["type"],
                    "statut": run.status,
                    "appels": run.llm_calls,
                    **verdict,
                }
            )
            mark = "réussi" if verdict["reussi"] else "ÉCHEC"
            print(f"{scenario['id']} [{mark}] {run.status} : {run.text[:150]}")
    finally:
        receiver.shutdown()

    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "demonstrations.json").write_text(
        json.dumps(transcripts, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8"
    )
    summary = pd.DataFrame(rows)
    summary["outils_utilises"] = summary["outils_utilises"].map(" ".join)
    summary.to_csv(args.out / "demonstrations.csv", index=False)
    print(f"\n{int(summary['reussi'].sum())} / {len(summary)} scénarios réussis")
    print(f"Appels Gemini aujourd'hui : {guard.used_today()} / {guard.daily_cap}")


if __name__ == "__main__":
    main()
