"""Capture@k : part des cas positifs retrouvés dans les k % de la file traités en premier."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import numpy.typing as npt
import pandas as pd
from sklearn.metrics import average_precision_score

DEFAULT_SHARE = 0.10


@dataclass(frozen=True)
class Interval:
    estimate: float
    low: float
    high: float


def expected_captured(scores: npt.ArrayLike, labels: npt.ArrayLike, capacity: float) -> float:
    """Nombre de positifs attendus parmi les `capacity` dossiers les mieux notés.

    Les dossiers de même note sont départagés au hasard : pour le groupe d'ex æquo coupé par la
    limite, on compte la part de ses positifs proportionnelle aux places restantes. Le résultat
    est l'espérance exacte, sans tirage aléatoire.
    """
    scores_arr = np.asarray(scores, dtype=float)
    labels_arr = np.asarray(labels, dtype=float)
    order = np.argsort(-scores_arr, kind="stable")
    sorted_scores, sorted_labels = scores_arr[order], labels_arr[order]

    _, starts, sizes = np.unique(-sorted_scores, return_index=True, return_counts=True)
    positives = np.add.reduceat(sorted_labels, starts) if len(starts) else np.array([])

    captured, remaining = 0.0, float(capacity)
    for size, positive in zip(sizes, positives, strict=True):
        if remaining <= 0:
            break
        taken = min(float(size), remaining)
        captured += float(positive) * taken / float(size)
        remaining -= taken
    return captured


def capture_by_group(
    scores: npt.ArrayLike,
    labels: npt.ArrayLike,
    groups: npt.ArrayLike,
    share: float = DEFAULT_SHARE,
) -> pd.DataFrame:
    """Positifs captés et positifs totaux pour chaque groupe (une semaine de réclamations)."""
    frame = pd.DataFrame(
        {"score": np.asarray(scores), "label": np.asarray(labels), "group": np.asarray(groups)}
    )
    rows = [
        {
            "group": group,
            "captured": expected_captured(part["score"], part["label"], share * len(part)),
            "positives": float(part["label"].sum()),
        }
        for group, part in frame.groupby("group", sort=True)
    ]
    return pd.DataFrame(rows)


def capture_at(
    scores: npt.ArrayLike,
    labels: npt.ArrayLike,
    groups: npt.ArrayLike | None = None,
    share: float = DEFAULT_SHARE,
) -> float:
    """Capture@share, calculée groupe par groupe puis cumulée sur tous les groupes."""
    labels_arr = np.asarray(labels)
    groups_arr = np.zeros(len(labels_arr)) if groups is None else np.asarray(groups)
    table = capture_by_group(scores, labels_arr, groups_arr, share)
    return float(table["captured"].sum() / table["positives"].sum())


def pr_auc(scores: npt.ArrayLike, labels: npt.ArrayLike) -> float:
    return float(average_precision_score(np.asarray(labels), np.asarray(scores)))


def bootstrap_capture(
    by_group: pd.DataFrame,
    *,
    baseline: pd.DataFrame | None = None,
    n_resamples: int = 2000,
    level: float = 0.95,
    seed: int = 0,
) -> Interval:
    """Intervalle de confiance de la Capture, en tirant des groupes entiers avec remise.

    On tire des semaines et non des réclamations : les réclamations d'une même semaine se
    ressemblent (événements, campagnes), et les tirer séparément sous-estimerait l'incertitude.
    Avec `baseline`, l'intervalle porte sur l'écart entre les deux classements, calculé sur les
    mêmes semaines tirées (comparaison appariée).
    """
    rng = np.random.default_rng(seed)
    captured = by_group["captured"].to_numpy()
    positives = by_group["positives"].to_numpy()
    draws = rng.integers(0, len(by_group), size=(n_resamples, len(by_group)))

    def statistic(
        cap: npt.NDArray[np.float64], pos: npt.NDArray[np.float64]
    ) -> npt.NDArray[np.float64]:
        return cap[draws].sum(axis=1) / pos[draws].sum(axis=1)

    estimate = captured.sum() / positives.sum()
    samples = statistic(captured, positives)
    if baseline is not None:
        if not by_group["group"].equals(baseline["group"]):
            raise ValueError("Les deux classements doivent couvrir les mêmes groupes.")
        base_captured = baseline["captured"].to_numpy()
        estimate -= base_captured.sum() / positives.sum()
        samples = samples - statistic(base_captured, positives)

    tail = (1 - level) / 2
    low, high = np.quantile(samples, [tail, 1 - tail])
    return Interval(float(estimate), float(low), float(high))
