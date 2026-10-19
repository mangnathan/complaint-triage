"""Prépare les données de la démo publique, dans data/demo/ (jamais versionné sur GitHub).

La file réelle : les réclamations publiques du CFPB reçues depuis le 1er août 2026 par les 25
établissements les plus visés, notées par la règle retenue en v0.1, comme au chargement de la
base locale. Un échantillon récent garde la démo réaliste et son démarrage rapide. S'y ajoutent
le corpus du RAG et ses vecteurs, pour que la démo n'ait rien à recalculer.

Usage : uv run python scripts/demo/build_demo_data.py
"""

from __future__ import annotations

import argparse
import shutil
from datetime import date
from pathlib import Path

import pandas as pd

from complaint_triage.db.load import build_queue
from complaint_triage.demo.boot import QUEUE_FILE
from complaint_triage.rag.__main__ import PASSAGES_FILE

VECTORS_FILE = Path("rag") / "vectors.npz"


def demo_sample(queue: pd.DataFrame, since: date, companies: int) -> pd.DataFrame:
    """Les réclamations récentes des établissements les plus visés sur la période."""
    recent = queue[queue["date_received"] >= since]
    largest = recent["company"].value_counts().head(companies).index
    return recent[recent["company"].isin(largest)].reset_index(drop=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--out", type=Path, default=Path("data/demo"))
    parser.add_argument("--since", type=date.fromisoformat, default=date(2026, 8, 1))
    parser.add_argument("--companies", type=int, default=25)
    args = parser.parse_args()

    sample = demo_sample(build_queue(args.data_dir), args.since, args.companies)
    args.out.mkdir(parents=True, exist_ok=True)
    sample.to_parquet(args.out / QUEUE_FILE, index=False)
    for name in (PASSAGES_FILE, VECTORS_FILE):
        (args.out / name).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(args.data_dir / name, args.out / name)
    print(
        f"{len(sample)} réclamations de {sample['company'].nunique()} établissements, "
        f"du {sample['date_received'].min()} au {sample['date_received'].max()}, "
        f"et le corpus du RAG, dans {args.out}."
    )


if __name__ == "__main__":
    main()
