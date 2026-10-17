from __future__ import annotations

import pandas as pd

from complaint_triage.models.features import VOLUME_FEATURES, recent_volume, volume_features


def complaints(rows: list[tuple[str, str, str]]) -> pd.DataFrame:
    df = pd.DataFrame(rows, columns=["company", "issue", "date_received"])
    df["date_received"] = pd.to_datetime(df["date_received"])
    return df


def test_counts_only_the_previous_days_of_the_same_company_and_issue() -> None:
    df = complaints(
        [
            ("Bank A", "Fees", "2025-01-01"),
            ("Bank A", "Fees", "2025-01-05"),
            ("Bank A", "Fees", "2025-01-08"),  # 01/01 est à 7 jours : dans la fenêtre
            ("Bank A", "Fees", "2025-01-09"),  # 01/01 est à 8 jours : hors fenêtre
            ("Bank A", "Other", "2025-01-08"),  # autre motif
            ("Bank B", "Fees", "2025-01-08"),  # autre établissement
        ]
    )

    assert list(recent_volume(df)) == [0, 1, 2, 2, 0, 0]


def test_same_day_complaints_are_not_counted() -> None:
    # Le compteur ne doit utiliser que le passé : les réclamations du jour même sont exclues.
    df = complaints([("Bank A", "Fees", "2025-01-08")] * 3)

    assert list(recent_volume(df)) == [0, 0, 0]


def test_volume_features_compute_every_counter() -> None:
    df = complaints(
        [
            ("Bank A", "Fees", "2025-01-01"),
            ("Bank B", "Fees", "2025-01-03"),
            ("Bank A", "Other", "2025-01-04"),
            ("Bank A", "Fees", "2025-01-05"),
        ]
    )

    volumes = volume_features(df)

    assert list(volumes.columns) == list(VOLUME_FEATURES)
    last = volumes.iloc[-1]
    assert last["recent_same_issue_7d"] == 1  # Bank A, Fees
    assert last["recent_company_7d"] == 2  # Bank A, tous motifs
    assert last["recent_issue_all_companies_7d"] == 2  # Fees, tous établissements


def test_result_keeps_the_original_row_order() -> None:
    df = complaints([("Bank A", "Fees", "2025-01-08"), ("Bank A", "Fees", "2025-01-01")]).set_index(
        pd.Index([10, 20])
    )

    volume = recent_volume(df)

    assert list(volume.index) == [10, 20]
    assert list(volume) == [1, 0]
