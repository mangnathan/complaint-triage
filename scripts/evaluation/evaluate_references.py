"""Évalue les classements de référence sur la période de validation (v0.1, étape 4).

La période de test n'est pas évaluée ici : elle est réservée à la décision finale.

Usage : python scripts/evaluation/evaluate_references.py
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from complaint_triage.data.pipeline import load_interim
from complaint_triage.data.prepare import TARGET, prepare_for_modeling
from complaint_triage.evaluation.metrics import bootstrap_capture, capture_by_group, pr_auc
from complaint_triage.evaluation.split import TRAIN, VALIDATION, assign_period, week_of
from complaint_triage.models.baseline import H0_LEVELS, RateBaseline

BLUE, INK, INK_2, GRID, SURFACE = "#2a78d6", "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"

REFERENCES: dict[str, tuple[tuple[str, ...], ...] | None] = {
    "Hasard": None,
    "Produit": H0_LEVELS[:1],
    "Produit x motif": H0_LEVELS[:2],
    "H0 : produit x motif x sous-motif": H0_LEVELS,
}


def summarize_periods(df: pd.DataFrame) -> pd.DataFrame:
    table = df.groupby("periode").agg(
        debut=("date_received", "min"),
        fin=("date_received", "max"),
        reclamations=("complaint_id", "size"),
        semaines=("semaine", "nunique"),
        taux_indemnisation=(TARGET, lambda s: round(s.mean() * 100, 2)),
    )
    return table.sort_values("debut").reset_index()


def evaluate(train: pd.DataFrame, validation: pd.DataFrame, prior_weight: float) -> pd.DataFrame:
    labels = validation[TARGET].to_numpy()
    weeks = validation["semaine"].to_numpy()
    rows, by_week = [], {}
    for name, levels in REFERENCES.items():
        if levels is None:
            scores = np.zeros(len(validation))
        else:
            model = RateBaseline(levels, prior_weight).fit(train, train[TARGET])
            scores = model.score(validation)
        by_week[name] = capture_by_group(scores, labels, weeks)
        interval = bootstrap_capture(by_week[name])
        rows.append(
            {
                "classement": name,
                "capture_10": interval.estimate * 100,
                "capture_10_bas": interval.low * 100,
                "capture_10_haut": interval.high * 100,
                "pr_auc": pr_auc(scores, labels),
            }
        )
    table = pd.DataFrame(rows)
    gain = bootstrap_capture(by_week[list(REFERENCES)[-1]], baseline=by_week["Produit x motif"])
    table.attrs["gain_sous_motif"] = gain
    return table


def sensitivity(train: pd.DataFrame, validation: pd.DataFrame) -> pd.DataFrame:
    labels, weeks = validation[TARGET].to_numpy(), validation["semaine"].to_numpy()
    rows = []
    for weight in (0, 5, 20, 100, 500):
        scores = RateBaseline(H0_LEVELS, weight).fit(train, train[TARGET]).score(validation)
        table = capture_by_group(scores, labels, weeks)
        rows.append(
            {
                "poids_du_lissage": weight,
                "capture_10": table["captured"].sum() / table["positives"].sum() * 100,
                "pr_auc": pr_auc(scores, labels),
            }
        )
    return pd.DataFrame(rows)


def plot_references(table: pd.DataFrame, out: Path) -> None:
    table = table.iloc[::-1]
    fig, ax = plt.subplots(figsize=(7.5, 2.8), facecolor=SURFACE)
    errors = [
        table["capture_10"] - table["capture_10_bas"],
        table["capture_10_haut"] - table["capture_10"],
    ]
    bars = ax.barh(table["classement"], table["capture_10"], color=BLUE, height=0.55)
    ax.errorbar(
        table["capture_10"], table["classement"], xerr=errors, fmt="none", ecolor=INK, capsize=3
    )
    for bar, value in zip(bars, table["capture_10"], strict=True):
        ax.annotate(
            f"{value:.1f} %",
            (value, bar.get_y() + bar.get_height() / 2),
            xytext=(22, 0),
            textcoords="offset points",
            va="center",
            fontsize=8,
            color=INK,
        )
    ax.set_facecolor(SURFACE)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.tick_params(colors=INK_2, labelsize=8, length=0)
    ax.set_xlim(0, max(table["capture_10_haut"]) * 1.2)
    fig.suptitle(
        "Capture@10 % sur la validation (juillet-décembre 2025), intervalle à 95 %",
        x=0.02,
        ha="left",
        fontsize=11,
        color=INK,
    )
    fig.tight_layout()
    fig.savefig(out, dpi=200)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--out", type=Path, default=Path("docs/v0.1-donnees-et-scoring"))
    parser.add_argument("--prior-weight", type=float, default=20.0)
    args = parser.parse_args()

    df, export_date = load_interim(args.data_dir)
    prepared, _ = prepare_for_modeling(df, export_date)
    prepared["periode"] = assign_period(prepared["date_received"])
    prepared["semaine"] = week_of(prepared["date_received"])
    train = prepared[prepared["periode"] == TRAIN]
    validation = prepared[prepared["periode"] == VALIDATION]

    summarize_periods(prepared).to_csv(args.out / "data" / "periodes.csv", index=False)
    references = evaluate(train, validation, args.prior_weight)
    references.round(2).to_csv(args.out / "data" / "references-validation.csv", index=False)
    sensitivity(train, validation).round(2).to_csv(
        args.out / "data" / "lissage-h0-validation.csv", index=False
    )
    plot_references(references, args.out / "figures" / "references-validation.png")

    print(references.round(2).to_string(index=False))
    gain = references.attrs["gain_sous_motif"]
    print(
        f"gain du sous-motif : {gain.estimate * 100:.2f} points "
        f"[{gain.low * 100:.2f} ; {gain.high * 100:.2f}]"
    )


if __name__ == "__main__":
    main()
