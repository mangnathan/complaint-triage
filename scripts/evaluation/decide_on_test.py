"""Décision finale de la v0.1, sur la période de test, ouverte une seule fois.

Protocole fixé avant l'ouverture (rapport v0.1, section 9) :
- les deux candidats sans texte, H0 propre à la banque et le XGBoost retenu, sont réentraînés sur
  l'entraînement et la validation réunis, avec les réglages choisis sur la validation ;
- la Capture@10 % est mesurée chaque semaine dans la file de chaque banque et de chaque produit ;
- XGBoost n'est retenu que s'il fait au moins 5 points de plus que H0, avec une borne basse de
  l'intervalle de l'écart au-dessus de zéro ; sinon, H0 est retenu ;
- le candidat retenu doit respecter les seuils d'équité et de calibration ;
- le texte (TF-IDF, retenu sur la validation) est gardé si sa PR-AUC, calculée dans les files,
  dépasse d'au moins 0,02 celle du candidat retenu, sur les récits de test jamais vus.

Le script refuse de tourner si les résultats du test existent déjà.

Usage : python scripts/evaluation/decide_on_test.py
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import mlflow
import numpy as np
import numpy.typing as npt
import pandas as pd

from complaint_triage.data.prepare import TARGET
from complaint_triage.evaluation.calibration import ECE_THRESHOLD, expected_calibration_error
from complaint_triage.evaluation.decision import (
    MODEL_MARGIN,
    model_beats_reference,
    text_is_kept,
)
from complaint_triage.evaluation.fairness import cadrage_subgroups, compare_subgroup
from complaint_triage.evaluation.metrics import (
    Interval,
    bootstrap_capture,
    capture_by_group,
    pr_auc,
    pr_auc_in_queues,
    selection_in_queues,
)
from complaint_triage.evaluation.queues import queue_of, weekly_queue_of
from complaint_triage.evaluation.split import TEST, TRAIN, VALIDATION
from complaint_triage.models.baseline import BANK_H0_LEVELS, RateBaseline
from complaint_triage.models.dataset import (
    FINAL_PERIODS,
    FINAL_STOP_START,
    STOP_START,
    load_modeling_frame,
    split_training,
)
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
BANK_H0 = "H0 propre à la banque"
XGBOOST = "XGBoost retenu"
TFIDF = "TF-IDF (texte seul)"


def compare(
    scores: dict[str, npt.NDArray[np.float64]], rows: pd.DataFrame, reference: str
) -> pd.DataFrame:
    """Capture@10 % et PR-AUC de chaque classement, et leur écart avec la référence."""
    labels, weeks, queues = rows[TARGET].to_numpy(), rows["semaine"].to_numpy(), queue_of(rows)
    tables = {n: capture_by_group(s, labels, weeks, queues=queues) for n, s in scores.items()}
    in_queues = {n: pr_auc_in_queues(s, labels, queues) for n, s in scores.items()}
    results = []
    for name, table in tables.items():
        capture = bootstrap_capture(table)
        gain = bootstrap_capture(table, baseline=tables[reference])
        results.append(
            {
                "modele": name,
                "reclamations": len(rows),
                "capture": capture.estimate * 100,
                "capture_bas": capture.low * 100,
                "capture_haut": capture.high * 100,
                "gain": gain.estimate * 100,
                "gain_bas": gain.low * 100,
                "gain_haut": gain.high * 100,
                "pr_auc_dans_les_files": in_queues[name],
                "gain_pr_auc_dans_les_files": in_queues[name] - in_queues[reference],
                "pr_auc_banques_melangees": pr_auc(scores[name], labels),
            }
        )
    return pd.DataFrame(results)


def fairness_and_calibration(
    scores: dict[str, npt.NDArray[np.float64]], test: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame]:
    labels, weeks = test[TARGET].to_numpy(), test["semaine"].to_numpy()
    groups = cadrage_subgroups(test)
    fairness, calibration = [], []
    for name, values in scores.items():
        selected = selection_in_queues(values, weekly_queue_of(test))
        for group, mask in groups.items():
            result = compare_subgroup(selected, labels, mask, weeks)
            fairness.append(
                {
                    "modele": name,
                    "sous_groupe": group,
                    "capture_groupe": result.capture_group * 100,
                    "capture_autres": result.capture_rest * 100,
                    "rapport": result.ratio.estimate,
                    "rapport_bas": result.ratio.low,
                    "rapport_haut": result.ratio.high,
                    "dans_les_seuils": result.within_range,
                }
            )
        ece = expected_calibration_error(values, labels)
        calibration.append(
            {
                "modele": name,
                "note_moyenne": values.mean() * 100,
                "taux_observe": labels.mean() * 100,
                "ece": ece,
                "conforme": ece < ECE_THRESHOLD,
            }
        )
    return pd.DataFrame(fairness), pd.DataFrame(calibration)


def plot(structure: pd.DataFrame, out: Path) -> None:
    table = structure.iloc[::-1]
    reference = float(structure.loc[structure["modele"] == BANK_H0, "capture"].iloc[0])
    fig, ax = plt.subplots(figsize=(7.5, 2.4), facecolor=SURFACE)
    colors = [GREY if name == BANK_H0 else BLUE for name in table["modele"]]
    bars = ax.barh(table["modele"], table["capture"], color=colors, height=0.5)
    ax.errorbar(
        table["capture"],
        table["modele"],
        xerr=[table["capture"] - table["capture_bas"], table["capture_haut"] - table["capture"]],
        fmt="none",
        ecolor=INK,
        capsize=3,
    )
    bar_to_beat = reference + MODEL_MARGIN * 100
    ax.axvline(bar_to_beat, color=INK, lw=1, ls="--")
    ax.text(
        bar_to_beat,
        1.02,
        " barre du cadrage : H0 + 5 points",
        transform=ax.get_xaxis_transform(),
        fontsize=7,
        color=INK_2,
        va="bottom",
    )
    for bar, value in zip(bars, table["capture"], strict=True):
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
    ax.set_xlim(0, bar_to_beat * 1.25)
    fig.suptitle(
        "Capture@10 % sur la période de test, file de chaque banque et produit",
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
    parser.add_argument(
        "--rehearsal",
        type=Path,
        metavar="DOSSIER",
        help="répétition sur la validation, sans toucher au test ; résultats écrits dans DOSSIER",
    )
    args = parser.parse_args()

    learning_periods: tuple[str, ...]
    if args.rehearsal:
        # Mêmes calculs, un cran plus tôt : apprentissage sur l'entraînement, mesure sur la
        # validation. Doit redonner les chiffres de l'étape 7.
        learning_periods, stop_start, evaluated = (TRAIN,), STOP_START, VALIDATION
        data = figures = args.rehearsal
        data.mkdir(parents=True, exist_ok=True)
    else:
        learning_periods, stop_start, evaluated = FINAL_PERIODS, FINAL_STOP_START, TEST
        data, figures = args.out / "data", args.out / "figures"
    decision_file = data / "decision-test.json"
    if decision_file.exists():
        raise SystemExit(
            f"La période de test a déjà été ouverte ({decision_file}). "
            "La décision ne se rejoue pas."
        )

    frame = load_modeling_frame(args.data_dir)
    learning = frame[frame["periode"].isin(learning_periods)]
    test = frame[frame["periode"] == evaluated].reset_index(drop=True)
    fit_part, stop_part = split_training(frame, learning_periods, stop_start)

    h0 = RateBaseline(BANK_H0_LEVELS).fit(learning, learning[TARGET])
    xgb = GradientBoostingScorer(SELECTED_CATEGORICAL, SELECTED_NUMERIC, SELECTED_PARAMS)
    xgb.fit(fit_part, fit_part[TARGET], stop_part, stop_part[TARGET])
    candidates = {BANK_H0: h0.score(test), XGBOOST: xgb.score(test)}

    # 1. Modèle structuré contre la règle de référence.
    structure = compare(candidates, test, BANK_H0)
    xgb_row = structure[structure["modele"] == XGBOOST].iloc[0]
    gain = Interval(xgb_row["gain"] / 100, xgb_row["gain_bas"] / 100, xgb_row["gain_haut"] / 100)
    retained = XGBOOST if model_beats_reference(gain) else BANK_H0

    # 2. Équité et calibration des deux candidats.
    fairness, calibration = fairness_and_calibration(candidates, test)
    retained_fair = bool(fairness.loc[fairness["modele"] == retained, "dans_les_seuils"].all())
    retained_calibrated = bool(calibration.loc[calibration["modele"] == retained, "conforme"].all())

    # 3. Apport du texte, sur les récits de test jamais vus pendant l'apprentissage.
    learning_texts, _ = deduplicate_texts(with_text(learning))
    tfidf = TfidfTextScorer().fit(learning_texts[TEXT_COLUMN], learning_texts[TARGET])
    with_narrative = with_text(test).reset_index(drop=True)
    new_texts = unseen_texts(with_narrative, learning).to_numpy()
    rows = with_narrative[new_texts].reset_index(drop=True)
    text_scores = {
        BANK_H0: h0.score(rows),
        XGBOOST: xgb.score(rows),
        TFIDF: tfidf.score(rows[TEXT_COLUMN]),
    }
    text = compare(text_scores, rows, retained)
    text_gain = float(text.loc[text["modele"] == TFIDF, "gain_pr_auc_dans_les_files"].iloc[0])

    decision = {
        "modele_retenu": retained,
        "ecart_xgboost_points": round(gain.estimate * 100, 2),
        "ecart_xgboost_intervalle": [round(gain.low * 100, 2), round(gain.high * 100, 2)],
        "equite_respectee": retained_fair,
        "calibration_respectee": retained_calibrated,
        "mise_en_service_possible": retained_fair and retained_calibrated,
        "texte_garde": text_is_kept(text_gain),
        "gain_pr_auc_texte": round(text_gain, 4),
        "reclamations_test": len(test),
        "recits_test_jamais_vus": len(rows),
        "arbres_xgboost": xgb.best_iteration + 1,
    }

    structure.round(3).to_csv(data / "decision-test-structure.csv", index=False)
    fairness.round(3).to_csv(data / "decision-test-equite.csv", index=False)
    calibration.round(4).to_csv(data / "decision-test-calibration.csv", index=False)
    text.round(3).to_csv(data / "decision-test-texte.csv", index=False)
    plot(structure, figures / "decision-test.png")

    mlflow.set_tracking_uri(tracking_uri())
    mlflow.set_experiment("v0.1-decision-test")
    run_name = "répétition sur la validation" if args.rehearsal else "décision finale"
    with mlflow.start_run(run_name=run_name):
        mlflow.log_params(
            {
                "commit": git_commit(),
                "manifeste_sha256": file_digest(
                    args.data_dir / "interim" / "complaints.manifest.json"
                ),
                "modele_retenu": retained,
                "texte_garde": decision["texte_garde"],
            }
        )
        mlflow.log_metrics(
            {
                "ecart_xgboost": gain.estimate * 100,
                "ecart_xgboost_bas": gain.low * 100,
                **{
                    f"capture_{key}": float(
                        structure.loc[structure["modele"] == name, "capture"].iloc[0]
                    )
                    for key, name in (("h0", BANK_H0), ("xgboost", XGBOOST))
                },
                "gain_pr_auc_texte": text_gain,
            }
        )
    # Écrit en dernier : sa présence signifie que le test a été ouvert et la décision prise.
    decision_file.write_text(json.dumps(decision, ensure_ascii=False, indent=2) + "\n")

    with pd.option_context("display.width", 220):
        print(structure.round(3).to_string(index=False))
        print(fairness.round(3).to_string(index=False))
        print(calibration.round(4).to_string(index=False))
        print(text.round(3).to_string(index=False))
    print(json.dumps(decision, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
