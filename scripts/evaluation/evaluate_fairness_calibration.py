"""Équité par sous-groupe et calibration des deux candidats, sur la période de validation.

Les candidats sont ceux qui peuvent servir en production, donc sans le texte : H0 propre à la
banque et le XGBoost retenu à l'étape 6. Les sous-groupes et les seuils sont ceux du cadrage :
clients signalés comme âgés (Older American) ou militaires (Servicemember), et produit. Pour
chaque sous-groupe, on compare la part de ses réclamations indemnisées que la banque traite en
priorité dans sa file avec celle des autres clients ; le rapport doit rester entre 0,8 et 1,25.
La calibration doit avoir une erreur (ECE) inférieure à 0,05.

Deux organisations des files sont mesurées : une file par banque, celle des étapes 4 à 6, qui
échoue sur le produit, et une file par banque et par produit, retenue à la suite de cet échec.

Usage : python scripts/evaluation/evaluate_fairness_calibration.py
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
from complaint_triage.evaluation.calibration import (
    ECE_THRESHOLD,
    expected_calibration_error,
    reliability_table,
)
from complaint_triage.evaluation.fairness import (
    FAIRNESS_RANGE,
    cadrage_subgroups,
    compare_subgroup,
)
from complaint_triage.evaluation.metrics import (
    bootstrap_capture,
    capture_by_group,
    selection_in_queues,
)
from complaint_triage.evaluation.queues import queue_of
from complaint_triage.evaluation.split import TRAIN, VALIDATION
from complaint_triage.models.baseline import BANK_H0_LEVELS, RateBaseline
from complaint_triage.models.dataset import load_modeling_frame, split_training
from complaint_triage.models.features import SELECTED_CATEGORICAL, SELECTED_NUMERIC
from complaint_triage.models.gradient_boosting import SELECTED_PARAMS, GradientBoostingScorer
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
ALL = "Toutes les réclamations"
BY_BANK = "Une file par banque"
BY_PRODUCT = "Une file par banque et produit"


def fairness_rows(
    name: str,
    design: str,
    scores: npt.NDArray[np.float64],
    queues: npt.NDArray[np.int64],
    validation: pd.DataFrame,
    groups: dict[str, npt.NDArray[np.bool_]],
) -> list[dict[str, Any]]:
    labels = validation[TARGET].to_numpy()
    weeks = validation["semaine"].to_numpy()
    weekly_queues = (
        pd.DataFrame({"semaine": weeks, "file": queues}).groupby(["semaine", "file"]).ngroup()
    )
    selected = selection_in_queues(scores, weekly_queues.to_numpy())
    rows = []
    for group, mask in groups.items():
        result = compare_subgroup(selected, labels, mask, weeks)
        rows.append(
            {
                "file": design,
                "modele": name,
                "sous_groupe": group,
                "reclamations": int(mask.sum()),
                "indemnisees": int(labels[mask].sum()),
                "taux_indemnisation": labels[mask].mean() * 100,
                "capture_groupe": result.capture_group * 100,
                "capture_autres": result.capture_rest * 100,
                "rapport": result.ratio.estimate,
                "rapport_bas": result.ratio.low,
                "rapport_haut": result.ratio.high,
                "dans_les_seuils": result.within_range,
            }
        )
    return rows


def capture_rows(
    design: str,
    candidates: dict[str, npt.NDArray[np.float64]],
    queues: npt.NDArray[np.int64],
    validation: pd.DataFrame,
) -> list[dict[str, Any]]:
    labels = validation[TARGET].to_numpy()
    weeks = validation["semaine"].to_numpy()
    tables = {
        name: capture_by_group(scores, labels, weeks, queues=queues)
        for name, scores in candidates.items()
    }
    rows = []
    for name, table in tables.items():
        capture = bootstrap_capture(table)
        gain = bootstrap_capture(table, baseline=tables[BANK_H0])
        rows.append(
            {
                "file": design,
                "modele": name,
                "capture": capture.estimate * 100,
                "capture_bas": capture.low * 100,
                "capture_haut": capture.high * 100,
                "gain_vs_h0_banque": gain.estimate * 100,
                "gain_bas": gain.low * 100,
                "gain_haut": gain.high * 100,
            }
        )
    return rows


def calibration_rows(
    name: str,
    scores: npt.NDArray[np.float64],
    validation: pd.DataFrame,
    groups: dict[str, npt.NDArray[np.bool_]],
) -> list[dict[str, Any]]:
    labels = validation[TARGET].to_numpy()
    populations = {ALL: np.ones(len(labels), dtype=bool), **groups}
    rows = []
    for population, mask in populations.items():
        ece = expected_calibration_error(scores[mask], labels[mask])
        rows.append(
            {
                "modele": name,
                "population": population,
                "reclamations": int(mask.sum()),
                "note_moyenne": scores[mask].mean() * 100,
                "taux_observe": labels[mask].mean() * 100,
                "ece": ece,
                "conforme": ece < ECE_THRESHOLD,
            }
        )
    return rows


def style(ax: Any) -> None:
    ax.set_facecolor(SURFACE)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)
    ax.grid(color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.tick_params(colors=INK_2, labelsize=8, length=0)


def plot_fairness(table: pd.DataFrame, out: Path) -> None:
    groups = list(dict.fromkeys(table["sous_groupe"]))
    models = list(dict.fromkeys(table["modele"]))
    designs = list(dict.fromkeys(table["file"]))
    fig, axes = plt.subplots(1, len(designs), figsize=(9.5, 3.8), sharey=True, facecolor=SURFACE)
    low, high = FAIRNESS_RANGE
    ticks = [0.25, 0.5, 0.8, 1.0, 1.25, 2.0, 4.0]
    for ax, design in zip(axes, designs, strict=True):
        ax.axvspan(low, high, color=GRID, alpha=0.6, lw=0, label="Seuils du cadrage")
        ax.axvline(1.0, color=INK_2, lw=0.8)
        for offset, model, color in zip((0.15, -0.15), models, (GREY, BLUE), strict=True):
            part = table[(table["file"] == design) & (table["modele"] == model)]
            part = part.set_index("sous_groupe").loc[groups]
            ax.errorbar(
                part["rapport"],
                np.arange(len(groups))[::-1] + offset,
                xerr=[
                    part["rapport"] - part["rapport_bas"],
                    part["rapport_haut"] - part["rapport"],
                ],
                fmt="o",
                color=color,
                ecolor=color,
                capsize=3,
                markersize=5,
                label=model,
            )
        # Échelle logarithmique : un rapport de 0,8 et un rapport de 1,25 sont à même distance de 1.
        ax.set_xscale("log")
        ax.set_xticks(ticks, [f"{t:g}".replace(".", ",") for t in ticks])
        ax.minorticks_off()
        ax.set_xlim(0.2, 5.0)
        ax.set_title(design, fontsize=9, color=INK, loc="left")
        style(ax)
        ax.grid(axis="y", visible=False)
    axes[0].set_yticks(np.arange(len(groups))[::-1], groups)
    axes[-1].legend(fontsize=7, frameon=False, loc="lower right")
    fig.supxlabel("Capture du sous-groupe / capture des autres clients", fontsize=8, color=INK_2)
    fig.suptitle(
        "Rapport des Capture@10 % par sous-groupe, validation", x=0.02, ha="left", fontsize=11
    )
    fig.tight_layout()
    fig.savefig(out, dpi=200)
    plt.close(fig)


def plot_calibration(tables: dict[str, pd.DataFrame], out: Path) -> None:
    fig, ax = plt.subplots(figsize=(5.5, 4.5), facecolor=SURFACE)
    top = max(max(t["predicted"].max(), t["observed"].max()) for t in tables.values()) * 110
    ax.plot([0, top], [0, top], color=INK_2, lw=0.8, ls="--", label="Calibration parfaite")
    for (name, table), color in zip(tables.items(), (GREY, BLUE), strict=True):
        ax.plot(
            table["predicted"] * 100,
            table["observed"] * 100,
            "o-",
            color=color,
            markersize=4,
            label=name,
        )
    ax.set_xlim(0, top)
    ax.set_ylim(0, top)
    ax.set_xlabel("Note moyenne de la classe (%)", fontsize=8, color=INK_2)
    ax.set_ylabel("Part réellement indemnisée (%)", fontsize=8, color=INK_2)
    style(ax)
    ax.legend(fontsize=8, frameon=False, loc="upper left")
    fig.suptitle("Calibration sur la validation, 10 classes", x=0.02, ha="left", fontsize=11)
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

    xgb = GradientBoostingScorer(SELECTED_CATEGORICAL, SELECTED_NUMERIC, SELECTED_PARAMS)
    xgb.fit(fit_part, fit_part[TARGET], stop_part, stop_part[TARGET])
    candidates = {
        BANK_H0: RateBaseline(BANK_H0_LEVELS).fit(train, train[TARGET]).score(validation),
        XGBOOST: xgb.score(validation),
    }
    designs = {
        BY_BANK: np.asarray(validation.groupby("company", sort=True).ngroup(), dtype=np.int64),
        BY_PRODUCT: queue_of(validation),
    }
    groups = cadrage_subgroups(validation)
    fairness = pd.DataFrame(
        [
            row
            for design, queues in designs.items()
            for name, scores in candidates.items()
            for row in fairness_rows(name, design, scores, queues, validation, groups)
        ]
    )
    captures = pd.DataFrame(
        [
            row
            for design, queues in designs.items()
            for row in capture_rows(design, candidates, queues, validation)
        ]
    )
    calibration = pd.DataFrame(
        [
            row
            for name, scores in candidates.items()
            for row in calibration_rows(name, scores, validation, groups)
        ]
    )
    labels = validation[TARGET].to_numpy()
    reliability = {name: reliability_table(s, labels) for name, s in candidates.items()}

    data, figures = args.out / "data", args.out / "figures"
    fairness.round(3).to_csv(data / "equite-validation.csv", index=False)
    captures.round(2).to_csv(data / "equite-capture-par-file.csv", index=False)
    calibration.round(4).to_csv(data / "calibration-validation.csv", index=False)
    pd.concat(reliability, names=["modele"]).reset_index(level=0).round(4).to_csv(
        data / "calibration-classes.csv", index=False
    )
    plot_fairness(fairness, figures / "equite-validation.png")
    plot_calibration(reliability, figures / "calibration-validation.png")

    mlflow.set_tracking_uri(tracking_uri())
    mlflow.set_experiment("v0.1-equite-calibration")
    common = {
        "commit": git_commit(),
        "manifeste_sha256": file_digest(args.data_dir / "interim" / "complaints.manifest.json"),
        **{f"sous_groupe_{i}": group for i, group in enumerate(groups, start=1)},
    }
    for name in candidates:
        ece = calibration[(calibration["modele"] == name) & (calibration["population"] == ALL)]
        with mlflow.start_run(run_name=name):
            mlflow.log_params(common)
            mlflow.log_metric("ece", float(ece["ece"].iloc[0]))
            # Les noms de métriques MLflow n'acceptent pas les accents : files et groupes numérotés.
            for d, design in enumerate(designs, start=1):
                part = fairness[(fairness["modele"] == name) & (fairness["file"] == design)]
                for i, ratio in enumerate(part["rapport"], start=1):
                    mlflow.log_metric(f"file_{d}_rapport_sous_groupe_{i}", float(ratio))
                capture = captures[(captures["modele"] == name) & (captures["file"] == design)]
                mlflow.log_metric(f"file_{d}_capture", float(capture["capture"].iloc[0]))

    with pd.option_context("display.width", 220):
        print(fairness.round(3).to_string(index=False))
        print(captures.round(2).to_string(index=False))
        print(calibration.round(4).to_string(index=False))


if __name__ == "__main__":
    main()
