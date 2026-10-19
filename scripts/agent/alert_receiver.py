"""Lance le récepteur local d'alertes : uv run python scripts/agent/alert_receiver.py

Les alertes sont ajoutées à data/agent/alertes.jsonl. Adresse à mettre dans .env :
ALERT_WEBHOOK_URL=http://127.0.0.1:8765/alerts
"""

from __future__ import annotations

import argparse
import threading
from pathlib import Path

from complaint_triage.agent.receiver import DEFAULT_PORT, start_receiver


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--log", type=Path, default=Path("data/agent/alertes.jsonl"))
    args = parser.parse_args()
    server = start_receiver(args.log, args.port)
    print(f"Récepteur d'alertes sur http://127.0.0.1:{args.port}/alerts ; Ctrl+C pour arrêter.")
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        server.shutdown()


if __name__ == "__main__":
    main()
