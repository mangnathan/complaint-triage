"""Mesure ce qu'apporte le texte : comparaison sur les mêmes réclamations de validation.

Tous les classements sont évalués sur les réclamations de validation qui ont un récit, dans la file
de chaque établissement, et comparés à H0 propre à la banque. La mesure principale exclut les récits
déjà présents mot pour mot dans l'entraînement. Les scores du modèle de langage, calculés sur
Colab, sont lus dans data/processed/ s'ils sont présents.

Usage : python scripts/experiments/evaluate_text_models.py
"""

from __future__ import annotations

import argparse
from pathlib import Path

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
from complaint_triage.models.baseline import BANK_H0_LEVELS, RateBaseline
from complaint_triage.models.dataset import load_modeling_frame, split_training
from complaint_triage.models.features import SELECTED_CATEGORICAL, SELECTED_NUMERIC
from complaint_triage.models.gradient_boosting import SELECTED_PARAMS, GradientBoostingScorer
from complaint_triage.models.text import (
    TEXT_COLUMN,
    TfidfTextScorer,
    deduplicate_texts,
    unseen_texts,
    with_text,
)
from complaint_triage.tracking import file_digest, git_commit, tracking_uri

BLUE, GREY, INK, INK_2, GRID, SURFACE = (
    "#2a78d6",
    "#9a9993",
    "#0b0b0b",
    "#52514e",
    "#e4e3df",
    "#fcfcfb",
)
TRANSFORMER_SCORES = "scores-validation-distilroberta.parquet"
REFERENCE = "H0 propre à la banque"
STRUCTURED = "XGBoost (sans texte)"


def rank_average(*scores: npt.NDArray[np.float64]) -> npt.NDArray[np.float64]:
    """Moyenne des rangs à poids égaux, fixée à l'avance plutôt que réglée sur la validation."""
    ranks = [pd.Series(s).rank(pct=True).to_numpy() for s in scores]
    return np.asarray(np.mean(ranks, axis=0), dtype=float)


def evaluate(scores: dict[str, npt.NDArray[np.float64]], rows: pd.DataFrame) -> pd.DataFrame:
    labels, weeks = rows[TARGET].to_numpy(), rows["semaine"].to_numpy()
    banks = rows["company"].to_numpy()
    reference = capture_by_group(scores[REFERENCE], labels, weeks, queues=banks)
    results = []
    for name, values in scores.items():
        by_week = capture_by_group(values, labels, weeks, queues=banks)
        capture = bootstrap_capture(by_week)
        gain = bootstrap_capture(by_week, baseline=reference)
        results.append(
            {
                "modele": name,
                "capture_par_banque": capture.estimate * 100,
                "capture_bas": capture.low * 100,
                "capture_haut": capture.high * 100,
                "gain_vs_h0_banque": gain.estimate * 100,
                "gain_bas": gain.low * 100,
                "gain_haut": gain.high * 100,
                "pr_auc": pr_auc(values, labels),
            }
        )
    return pd.DataFrame(results)


def plot_results(results: pd.DataFrame, out: Path) -> None:
    table = results.iloc[::-1]
    colors = [GREY if name.startswith("H0") else BLUE for name in table["modele"]]
    fig, ax = plt.subplots(figsize=(7.5, 0.5 * len(table) + 1.0), facecolor=SURFACE)
    bars = ax.barh(table["modele"], table["capture_par_banque"], color=colors, height=0.55)
    errors = [
        table["capture_par_banque"] - table["capture_bas"],
        table["capture_haut"] - table["capture_par_banque"],
    ]
    ax.errorbar(
        table["capture_par_banque"],
        table["modele"],
        xerr=errors,
        fmt="none",
        ecolor=INK,
        capsize=3,
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
        "Capture@10 % dans la file de chaque banque, récits de validation jamais vus",
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
    fit_part, stop_part = split_training(frame)
    validation = with_text(frame[frame["periode"] == VALIDATION]).reset_index(drop=True)

    h0 = RateBaseline(BANK_H0_LEVELS).fit(train, train[TARGET])
    xgb = GradientBoostingScorer(SELECTED_CATEGORICAL, SELECTED_NUMERIC, SELECTED_PARAMS)
    xgb.fit(fit_part, fit_part[TARGET], stop_part, stop_part[TARGET])
    train_texts, _ = deduplicate_texts(with_text(train))
    tfidf = TfidfTextScorer().fit(train_texts[TEXT_COLUMN], train_texts[TARGET])

    scores = {
        REFERENCE: h0.score(validation),
        STRUCTURED: xgb.score(validation),
        "TF-IDF (texte seul)": tfidf.score(validation[TEXT_COLUMN]),
    }
    transformer_path = args.data_dir / "processed" / TRANSFORMER_SCORES
    if transformer_path.exists():
        transformer = pd.read_parquet(transformer_path).set_index("complaint_id")["score"]
        scores["DistilRoBERTa (texte seul)"] = (
            validation["complaint_id"].map(transformer).to_numpy(dtype=float)
        )
    text_models = [name for name in scores if "texte seul" in name]
    for name in text_models:
        short = name.split(" (")[0]
        scores[f"XGBoost + {short}"] = rank_average(scores[STRUCTURED], scores[name])

    new_texts = unseen_texts(validation, train).to_numpy()
    main_results = evaluate({k: v[new_texts] for k, v in scores.items()}, validation[new_texts])
    all_results = evaluate(scores, validation)

    mlflow.set_tracking_uri(tracking_uri())
    mlflow.set_experiment("v0.1-texte-par-etablissement")
    manifest = args.data_dir / "interim" / "complaints.manifest.json"
    for _, row in main_results.iterrows():
        with mlflow.start_run(run_name=str(row["modele"])):
            mlflow.log_params(
                {
                    "evaluation": "file de chaque banque, récits de validation jamais vus",
                    "reclamations": int(new_texts.sum()),
                    "commit": git_commit(),
                    "manifeste_sha256": file_digest(manifest),
                }
            )
            mlflow.log_metrics({str(k): float(v) for k, v in row.items() if k != "modele"})

    to_vocab, against = tfidf.top_terms(20)
    pd.DataFrame({"vers_indemnisation": to_vocab, "vers_absence": against}).to_csv(
        args.out / "data" / "tfidf-termes.csv", index=False
    )
    main_results.round(2).to_csv(args.out / "data" / "texte-validation.csv", index=False)
    all_results.round(2).to_csv(args.out / "data" / "texte-validation-tous.csv", index=False)
    plot_results(main_results, args.out / "figures" / "texte-validation.png")

    print(f"récits de validation : {len(validation)}, jamais vus : {int(new_texts.sum())}")
    print(main_results.round(2).to_string(index=False))
    print("tous les récits :")
    columns = ["modele", "capture_par_banque", "gain_vs_h0_banque"]
    print(all_results[columns].round(2).to_string(index=False))
    print("vers l'indemnisation :", ", ".join(to_vocab))
    print("vers l'absence :", ", ".join(against))


if __name__ == "__main__":
    main()
