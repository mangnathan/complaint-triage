"""Jeu de modélisation commun à tous les modèles : préparation, variables et périodes."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd

from complaint_triage.data.pipeline import load_interim
from complaint_triage.data.prepare import prepare_for_modeling
from complaint_triage.evaluation.split import TRAIN, assign_period, week_of
from complaint_triage.models.features import volume_features

# Les trois derniers mois de l'entraînement servent à arrêter l'apprentissage des modèles :
# la validation reste réservée à la comparaison.
STOP_START = date(2025, 4, 1)


def load_modeling_frame(data_dir: Path) -> pd.DataFrame:
    """Jeu préparé, avec les compteurs de volume récent, la période et la semaine de réception."""
    df, export_date = load_interim(data_dir)
    # Les volumes sont comptés sur toutes les réclamations reçues, y compris celles qui seront
    # retirées ensuite (trop récentes) : c'est ce que verrait la banque à l'arrivée.
    volumes = volume_features(df).set_axis(df["complaint_id"])
    prepared, _ = prepare_for_modeling(df, export_date)
    prepared = prepared.join(volumes, on="complaint_id")
    prepared["periode"] = assign_period(prepared["date_received"])
    prepared["semaine"] = week_of(prepared["date_received"])
    return prepared


def split_training(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Coupe la période d'entraînement en une partie d'apprentissage et une partie d'arrêt."""
    train = frame[frame["periode"] == TRAIN]
    stop = train["date_received"] >= pd.Timestamp(STOP_START)
    return train[~stop], train[stop]
