"""Pose une demande à l'agent : uv run python scripts/agent/run_agent.py "Show the top 3 ..."

L'agent annonce son plan à chaque tour, puis répond ou refuse. Les appels à Gemini passent par le
cache et le plafond de la v0.2. Pour l'outil d'alerte, lancer d'abord le récepteur local
(scripts/agent/alert_receiver.py) et définir ALERT_WEBHOOK_URL dans .env.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from complaint_triage.agent.runtime import build_agent
from complaint_triage.rag.llm import QuotaGuard, load_dotenv


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("request")
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    args = parser.parse_args()

    load_dotenv(Path(".env"))
    guard = QuotaGuard(args.data_dir / "rag" / "quota.json")
    agent = build_agent(args.data_dir, guard, os.environ.get("ALERT_WEBHOOK_URL", ""))
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
