"""Réévalue les références et les modèles de l'étape 5 dans la file de chaque établissement.

Le cadrage définit le client comme une banque qui trie sa propre file. Classer toutes les banques
ensemble avantage un modèle capable de deviner la banque : la mesure corrigée classe les
réclamations dans la file de chaque établissement, semaine par semaine, puis cumule. La référence
devient H0 propre à la banque. Aucune variante ni aucun réglage n'est ajouté à ceux de l'étape 5.

Usage : python scripts/evaluation/evaluate_by_bank.py
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import mlflow
import numpy as np
import numpy.typing as npt
import pandas as pd

from complaint_triage.data.prepare import TARGET
from complaint_triage.evaluation.metrics import bootstrap_capture, capture_by_group, pr_auc
from complaint_triage.evaluation.split import TRAIN, VALIDATION
from complaint_triage.models.baseline import BANK_H0_LEVELS, H0_LEVELS, RateBaseline
from complaint_triage.models.dataset import load_modeling_frame, split_training
from complaint_triage.models.features import (
    CATEGORICAL_FEATURES,
    COMPANY_FEATURE,
    RECENT_VOLUME_FEATURE,
    VOLUME_FEATURES,
)
from complaint_triage.models.gradient_boosting import GradientBoostingScorer
from complaint_triage.tracking import file_digest, git_commit, tracking_uri

BLUE, GREY, INK, INK_2, GRID, SURFACE = (
    "#2a78d6",
    "#9a9993",
    "#0b0b0b",
    "#52514e",
    "#e4e3df",
    "#fcfcfb",
)
BANK_H0 = "H0 propre à la banque"
ALL_VOLUMES = tuple(VOLUME_FEATURES)
VARIANTS: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    "A : variables structurées": (CATEGORICAL_FEATURES, ()),
    "B : A + volume récent": (CATEGORICAL_FEATURES, (RECENT_VOLUME_FEATURE,)),
    "C : A + tous les volumes récents": (CATEGORICAL_FEATURES, ALL_VOLUMES),
    "D : C + établissement": ((*CATEGORICAL_FEATURES, COMPANY_FEATURE), ALL_VOLUMES),
}
# Les 8 réglages de l'étape 5, sans en ajouter.
TUNING_BUDGET: list[dict[str, Any]] = [
    {"max_depth": 6, "min_child_weight": 50, "learning_rate": 0.05},
    {"max_depth": 4, "min_child_weight": 20, "learning_rate": 0.05},
    {"max_depth": 4, "min_child_weight": 100, "learning_rate": 0.05},
    {"max_depth": 6, "min_child_weight": 20, "learning_rate": 0.05},
    {"max_depth": 6, "min_child_weight": 100, "learning_rate": 0.05},
    {"max_depth": 8, "min_child_weight": 20, "learning_rate": 0.05},
    {"max_depth": 8, "min_child_weight": 100, "learning_rate": 0.05},
    {"max_depth": 6, "min_child_weight": 50, "learning_rate": 0.02},
]


class Evaluator:
    """Mesure un classement des deux façons, et son écart avec H0 propre à la banque."""

    def __init__(self, validation: pd.DataFrame, bank_h0: npt.NDArray[np.float64]) -> None:
        self.labels = validation[TARGET].to_numpy()
        self.weeks = validation["semaine"].to_numpy()
        self.banks = validation["company"].to_numpy()
        self.reference = capture_by_group(bank_h0, self.labels, self.weeks, queues=self.banks)

    def __call__(self, name: str, scores: npt.NDArray[np.float64]) -> dict[str, Any]:
        pooled = capture_by_group(scores, self.labels, self.weeks)
        by_bank = capture_by_group(scores, self.labels, self.weeks, queues=self.banks)
        capture = bootstrap_capture(by_bank)
        gain = bootstrap_capture(by_bank, baseline=self.reference)
        return {
            "modele": name,
            "capture_banques_melangees": pooled["captured"].sum() / pooled["positives"].sum() * 100,
            "capture_par_banque": capture.estimate * 100,
            "capture_bas": capture.low * 100,
            "capture_haut": capture.high * 100,
            "gain_vs_h0_banque": gain.estimate * 100,
            "gain_bas": gain.low * 100,
            "gain_haut": gain.high * 100,
            "pr_auc": pr_auc(scores, self.labels),
        }


def plot(results: pd.DataFrame, out: Path) -> None:
    table = results.iloc[::-1]
    colors = [GREY if name.startswith(("H0", "Hasard")) else BLUE for name in table["modele"]]
    fig, ax = plt.subplots(figsize=(7.5, 0.45 * len(table) + 1.0), facecolor=SURFACE)
    bars = ax.barh(table["modele"], table["capture_par_banque"], color=colors, height=0.55)
    errors = [
        table["capture_par_banque"] - table["capture_bas"],
        table["capture_haut"] - table["capture_par_banque"],
    ]
    ax.errorbar(
        table["capture_par_banque"], table["modele"], xerr=errors, fmt="none", ecolor=INK, capsize=3
    )
    for bar, value in zip(bars, table["capture_par_banque"], strict=True):
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
    ax.set_xlim(0, max(table["capture_haut"]) * 1.2)
    fig.suptitle(
        "Capture@10 % dans la file de chaque établissement, validation (références en gris)",
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
    args = parser.parse_args()

    frame = load_modeling_frame(args.data_dir)
    train = frame[frame["periode"] == TRAIN]
    validation = frame[frame["periode"] == VALIDATION].reset_index(drop=True)
    fit_part, stop_part = split_training(frame)
    bank_h0 = RateBaseline(BANK_H0_LEVELS).fit(train, train[TARGET]).score(validation)
    evaluate = Evaluator(validation, bank_h0)

    rows = [
        evaluate("Hasard", np.zeros(len(validation))),
        evaluate(
            "H0 du marché", RateBaseline(H0_LEVELS).fit(train, train[TARGET]).score(validation)
        ),
        evaluate(BANK_H0, bank_h0),
    ]
    mlflow.set_tracking_uri(tracking_uri())
    mlflow.set_experiment("v0.1-par-etablissement")
    common = {
        "evaluation": "file de chaque établissement",
        "commit": git_commit(),
        "manifeste_sha256": file_digest(args.data_dir / "interim" / "complaints.manifest.json"),
    }

    def train_and_evaluate(
        name: str, features: tuple[tuple[str, ...], tuple[str, ...]], params: dict[str, Any]
    ) -> dict[str, Any]:
        categorical, numeric = features
        model = GradientBoostingScorer(categorical, numeric, params)
        model.fit(fit_part, fit_part[TARGET], stop_part, stop_part[TARGET])
        row = evaluate(name, model.score(validation))
        with mlflow.start_run(run_name=name):
            mlflow.log_params({**common, "variables": ", ".join(model.features), **params})
            mlflow.log_metrics({k: float(v) for k, v in row.items() if k != "modele"})
        return row

    variant_rows = [train_and_evaluate(name, f, {}) for name, f in VARIANTS.items()]
    rows.extend(variant_rows)
    chosen = max(variant_rows, key=lambda row: row["capture_par_banque"])["modele"]
    tuning = [
        {
            "reglage": i,
            **params,
            **train_and_evaluate(f"{chosen}, réglage {i}", VARIANTS[chosen], params),
        }
        for i, params in enumerate(TUNING_BUDGET, start=1)
    ]

    results = pd.DataFrame(rows).round(2)
    results.to_csv(args.out / "data" / "par-etablissement-validation.csv", index=False)
    pd.DataFrame(tuning).round(2).to_csv(
        args.out / "data" / "par-etablissement-reglages.csv", index=False
    )
    plot(results, args.out / "figures" / "par-etablissement-validation.png")
    print(results.to_string(index=False))
    print(f"variante retenue : {chosen}")
    print(
        pd.DataFrame(tuning)
        .round(2)[
            [
                "reglage",
                "max_depth",
                "min_child_weight",
                "learning_rate",
                "capture_par_banque",
                "gain_vs_h0_banque",
                "gain_bas",
                "gain_haut",
            ]
        ]
        .to_string(index=False)
    )


if __name__ == "__main__":
    main()
