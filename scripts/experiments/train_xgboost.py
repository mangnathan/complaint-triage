"""Entraîne les variantes XGBoost, les compare à H0 sur la validation et les trace dans MLflow.

Le test n'est pas évalué ici : il est réservé à la décision finale de la v0.1.

Usage : python scripts/experiments/train_xgboost.py
Résultats détaillés : mlflow ui --backend-store-uri sqlite:///mlflow.db
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
import subprocess
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import mlflow
import pandas as pd

from complaint_triage.data.pipeline import load_interim
from complaint_triage.data.prepare import TARGET, prepare_for_modeling
from complaint_triage.evaluation.metrics import bootstrap_capture, capture_by_group, pr_auc
from complaint_triage.evaluation.split import TRAIN, VALIDATION, assign_period, week_of
from complaint_triage.models.baseline import RateBaseline
from complaint_triage.models.features import (
    CATEGORICAL_FEATURES,
    COMPANY_FEATURE,
    RECENT_VOLUME_FEATURE,
    VOLUME_FEATURES,
    volume_features,
)
from complaint_triage.models.gradient_boosting import GradientBoostingScorer

BLUE, GREY, INK, INK_2, GRID, SURFACE = (
    "#2a78d6",
    "#9a9993",
    "#0b0b0b",
    "#52514e",
    "#e4e3df",
    "#fcfcfb",
)
# Les trois derniers mois de l'entraînement servent à arrêter l'ajout d'arbres :
# la validation reste réservée à la comparaison des modèles.
STOP_START = date(2025, 4, 1)
ALL_VOLUMES = tuple(VOLUME_FEATURES)
EXPERIMENTS: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    "A : variables structurées": (CATEGORICAL_FEATURES, ()),
    "B : A + volume récent": (CATEGORICAL_FEATURES, (RECENT_VOLUME_FEATURE,)),
    "C : A + tous les volumes récents": (CATEGORICAL_FEATURES, ALL_VOLUMES),
    # L'établissement serait constant pour une banque cliente : variante mesurée pour information.
    "D : C + établissement (information)": (
        (*CATEGORICAL_FEATURES, COMPANY_FEATURE),
        ALL_VOLUMES,
    ),
}
CHOSEN = "B : A + volume récent"

# Budget de réglage fixé avant de regarder les résultats : 8 essais sur la variante retenue.
# Le meilleur score sera légèrement optimiste (choisi parmi 8) ; le test tranchera.
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


@dataclass(frozen=True)
class Context:
    fit_part: pd.DataFrame
    stop_part: pd.DataFrame
    validation: pd.DataFrame
    h0_weeks: pd.DataFrame
    manifest: Path


def git_commit() -> str:
    git = shutil.which("git")
    if git is None:
        return "inconnu"
    result = subprocess.run(
        [git, "rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=False
    )
    return result.stdout.strip() or "inconnu"


def file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def load_modeling_frame(data_dir: Path) -> pd.DataFrame:
    df, export_date = load_interim(data_dir)
    # Les volumes sont comptés sur toutes les réclamations reçues, y compris celles qui seront
    # retirées ensuite (trop récentes) : c'est ce que verrait la banque à l'arrivée.
    volumes = volume_features(df).set_axis(df["complaint_id"])
    prepared, _ = prepare_for_modeling(df, export_date)
    prepared = prepared.join(volumes, on="complaint_id")
    prepared["periode"] = assign_period(prepared["date_received"])
    prepared["semaine"] = week_of(prepared["date_received"])
    return prepared


def run_experiment(
    context: Context,
    name: str,
    categorical: tuple[str, ...],
    numeric: tuple[str, ...],
    params: dict[str, Any],
) -> tuple[dict[str, float], pd.Series]:
    """Entraîne une variante, l'évalue sur la validation et l'enregistre dans MLflow."""
    labels = context.validation[TARGET].to_numpy()
    weeks = context.validation["semaine"].to_numpy()
    with mlflow.start_run(run_name=name):
        model = GradientBoostingScorer(categorical, numeric, params)
        model.fit(
            context.fit_part,
            context.fit_part[TARGET],
            context.stop_part,
            context.stop_part[TARGET],
        )
        scores = model.score(context.validation)
        by_week = capture_by_group(scores, labels, weeks)
        capture = bootstrap_capture(by_week)
        gain = bootstrap_capture(by_week, baseline=context.h0_weeks)
        metrics = {
            "capture_10": capture.estimate * 100,
            "capture_10_bas": capture.low * 100,
            "capture_10_haut": capture.high * 100,
            "gain_vs_h0": gain.estimate * 100,
            "gain_bas": gain.low * 100,
            "gain_haut": gain.high * 100,
            "pr_auc": pr_auc(scores, labels),
            "arbres": float(model.best_iteration + 1),
        }
        mlflow.log_params(
            {
                "variables": ", ".join(model.features),
                "debut_arret": str(STOP_START),
                "commit": git_commit(),
                "manifeste_sha256": file_digest(context.manifest),
                **{f"xgb_{key}": value for key, value in model.params.items()},
            }
        )
        mlflow.log_metrics(metrics)
        contributions = model.contributions(context.validation.sample(50_000, random_state=0))
        mlflow.log_dict(
            {str(feature): float(value) for feature, value in contributions.round(5).items()},
            "contributions.json",
        )
    return metrics, contributions


def plot_comparison(results: pd.DataFrame, out: Path) -> None:
    table = results.iloc[::-1]
    colors = [GREY if name.startswith("H0") else BLUE for name in table["modele"]]
    fig, ax = plt.subplots(figsize=(7.5, 2.9), facecolor=SURFACE)
    bars = ax.barh(table["modele"], table["capture_10"], color=colors, height=0.55)
    errors = [
        table["capture_10"] - table["capture_10_bas"],
        table["capture_10_haut"] - table["capture_10"],
    ]
    ax.errorbar(
        table["capture_10"], table["modele"], xerr=errors, fmt="none", ecolor=INK, capsize=3
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
        "Capture@10 % sur la validation, intervalle à 95 % (H0 en gris)",
        x=0.02,
        ha="left",
        fontsize=11,
        color=INK,
    )
    fig.tight_layout()
    fig.savefig(out, dpi=200)
    plt.close(fig)


def plot_contributions(contributions: pd.Series, out: Path) -> None:
    labels = {
        "issue": "motif",
        "sub_issue": "sous-motif",
        "product": "produit",
        "sub_product": "sous-produit",
        "submitted_via": "canal de dépôt",
        "state": "État",
        RECENT_VOLUME_FEATURE: "volume établissement x motif (7 j)",
        "recent_same_issue_30d": "volume établissement x motif (30 j)",
        "recent_company_7d": "volume établissement (7 j)",
        "recent_issue_all_companies_7d": "volume national du motif (7 j)",
        COMPANY_FEATURE: "établissement",
    }
    table = contributions.iloc[::-1]
    fig, ax = plt.subplots(figsize=(7.5, 2.8), facecolor=SURFACE)
    ax.barh([labels.get(name, name) for name in table.index], table.to_numpy(), color=BLUE)
    ax.set_facecolor(SURFACE)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.tick_params(colors=INK_2, labelsize=8, length=0)
    fig.suptitle(
        "Contribution moyenne de chaque variable (valeurs SHAP absolues), modèle B",
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
    validation = frame[frame["periode"] == VALIDATION]
    labels, weeks = validation[TARGET].to_numpy(), validation["semaine"].to_numpy()
    h0_scores = RateBaseline().fit(train, train[TARGET]).score(validation)
    h0_weeks = capture_by_group(h0_scores, labels, weeks)
    h0 = bootstrap_capture(h0_weeks)
    context = Context(
        fit_part=train[train["date_received"] < pd.Timestamp(STOP_START)],
        stop_part=train[train["date_received"] >= pd.Timestamp(STOP_START)],
        validation=validation,
        h0_weeks=h0_weeks,
        manifest=args.data_dir / "interim" / "complaints.manifest.json",
    )
    mlflow.set_tracking_uri(f"sqlite:///{Path('mlflow.db').resolve().as_posix()}")

    rows: list[dict[str, object]] = [
        {
            "modele": "H0 : produit x motif x sous-motif",
            "capture_10": h0.estimate * 100,
            "capture_10_bas": h0.low * 100,
            "capture_10_haut": h0.high * 100,
            "gain_vs_h0": 0.0,
            "gain_bas": 0.0,
            "gain_haut": 0.0,
            "pr_auc": pr_auc(h0_scores, labels),
            "arbres": 0.0,
        }
    ]
    mlflow.set_experiment("v0.1-xgboost-variables")
    chosen_contributions = pd.Series(dtype=float)
    for name, (categorical, numeric) in EXPERIMENTS.items():
        metrics, contributions = run_experiment(context, name, categorical, numeric, {})
        rows.append({"modele": name, **metrics})
        if name == CHOSEN:
            chosen_contributions = contributions

    mlflow.set_experiment("v0.1-xgboost-reglages")
    categorical, numeric = EXPERIMENTS[CHOSEN]
    tuning_rows: list[dict[str, object]] = []
    for index, params in enumerate(TUNING_BUDGET, start=1):
        metrics, _ = run_experiment(context, f"réglage {index}", categorical, numeric, params)
        tuning_rows.append({"reglage": index, **params, **metrics})

    results = pd.DataFrame(rows).round(2)
    results.to_csv(args.out / "data" / "xgboost-validation.csv", index=False)
    tuning = pd.DataFrame(tuning_rows).round(2)
    tuning.to_csv(args.out / "data" / "xgboost-reglages-validation.csv", index=False)
    chosen_contributions.round(5).rename("contribution").to_csv(
        args.out / "data" / "xgboost-contributions.csv"
    )
    plot_comparison(results, args.out / "figures" / "xgboost-validation.png")
    plot_contributions(chosen_contributions, args.out / "figures" / "xgboost-contributions.png")
    print(results.to_string(index=False))
    print(tuning.to_string(index=False))
    print(chosen_contributions.round(4).to_string())


if __name__ == "__main__":
    main()
