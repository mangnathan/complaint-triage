"""Prépare le fichier de récits à envoyer sur Google Colab pour le fine-tuning.

Le fichier ne contient que l'apprentissage, l'arrêt et la validation : la période de test ne
quitte pas cette machine.

Usage : python scripts/experiments/export_text_for_colab.py
Puis copier data/processed/recits-colab.parquet dans Google Drive, dossier complaint-triage.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from complaint_triage.data.prepare import TARGET
from complaint_triage.evaluation.split import VALIDATION
from complaint_triage.models.dataset import load_modeling_frame, split_training
from complaint_triage.models.text import TEXT_COLUMN, deduplicate_texts, with_text

COLUMNS = ["complaint_id", "date_received", TEXT_COLUMN, TARGET, "partie"]
# Le jeu d'arrêt est évalué régulièrement pendant l'entraînement : un échantillon suffit.
STOP_SAMPLE = 10_000


def build_export(frame: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, int]]:
    fit, stop = split_training(frame)
    fit_texts, dropped_fit = deduplicate_texts(with_text(fit))
    stop_texts, _ = deduplicate_texts(with_text(stop))
    stop_texts = stop_texts.sample(min(STOP_SAMPLE, len(stop_texts)), random_state=0)
    validation_texts = with_text(frame[frame["periode"] == VALIDATION])

    parts = {"apprentissage": fit_texts, "arret": stop_texts, "validation": validation_texts}
    export = pd.concat(
        [part.assign(partie=name)[COLUMNS] for name, part in parts.items()], ignore_index=True
    )
    counts = {name: len(part) for name, part in parts.items()}
    counts["copies_retirees_apprentissage"] = dropped_fit
    return export, counts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    args = parser.parse_args()

    export, counts = build_export(load_modeling_frame(args.data_dir))
    out = args.data_dir / "processed" / "recits-colab.parquet"
    out.parent.mkdir(parents=True, exist_ok=True)
    export.to_parquet(out, index=False)
    print(counts)
    print(f"{out} : {out.stat().st_size / 1e6:.0f} Mo")


if __name__ == "__main__":
    main()
