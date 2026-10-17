"""Exploration du jeu de données (v0.1, étape 3) : tableaux et figures du rapport.

Usage : python scripts/analysis/explore_dataset.py
"""

from __future__ import annotations

import argparse
import textwrap
from dataclasses import asdict
from datetime import date
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.axes import Axes

from complaint_triage.data.pipeline import load_interim
from complaint_triage.data.prepare import (
    IN_PROGRESS,
    MATURITY_DAYS,
    MONETARY_RELIEF,
    prepare_for_modeling,
)
from complaint_triage.data.taxonomy import CONSUMER_REPORTING_AGENCIES

BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
INK, INK_2, GRID, SURFACE = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
AGE_BINS = [0, 15, 30, 45, 60, 75, 90, 105, 120, 150, 180, 365, 2000]
SPIKE_COMPANIES = {
    "CAPITAL ONE FINANCIAL CORPORATION": "Capital One",
    "NAVY FEDERAL CREDIT UNION": "Navy Federal",
}


def _style(ax: Axes, title: str) -> None:
    ax.set_facecolor(SURFACE)
    ax.set_title(title, loc="left", fontsize=11, color=INK, pad=10)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(colors=INK_2, labelsize=8, length=0)


def label_maturity(df: pd.DataFrame, export_date: date) -> pd.DataFrame:
    age = (pd.Timestamp(export_date) - df["date_received"]).dt.days
    grouped = df.assign(age_bin=pd.cut(age, AGE_BINS, right=False)).groupby(
        "age_bin", observed=True
    )
    table = grouped.agg(
        reclamations=("complaint_id", "size"),
        en_cours=("company_response", lambda s: s.eq(IN_PROGRESS).mean() * 100),
        indemnisees=("company_response", lambda s: s.eq(MONETARY_RELIEF).mean() * 100),
    ).round(2)
    table.index = [f"{int(b.left)}-{int(b.right)}" for b in table.index]
    return table.rename_axis("age_jours").reset_index()


def zero_relief_companies(df: pd.DataFrame, min_complaints: int = 1000) -> pd.DataFrame:
    table = df.groupby("company").agg(
        reclamations=("complaint_id", "size"),
        indemnisees=("company_response", lambda s: s.eq(MONETARY_RELIEF).mean() * 100),
    )
    table = table[(table["reclamations"] >= min_complaints) & (table["indemnisees"] < 1)]
    table["gestionnaire_de_fichiers"] = table.index.isin(CONSUMER_REPORTING_AGENCIES)
    return table.round(2).sort_values("reclamations", ascending=False).reset_index()


def january_2025_spike(df: pd.DataFrame) -> pd.DataFrame:
    window = df[(df["date_received"] >= "2024-12-01") & (df["date_received"] <= "2025-02-28")]
    group = window["company"].map(SPIKE_COMPANIES).fillna("Autres établissements")
    daily = pd.crosstab(window["date_received"], group)
    return daily[["Capital One", "Navy Federal", "Autres établissements"]]


def relief_by_issue(prepared: pd.DataFrame, min_complaints: int = 2000) -> pd.DataFrame:
    table = prepared.groupby(["product", "issue"]).agg(
        reclamations=("complaint_id", "size"), indemnisees=("is_monetary_relief", "mean")
    )
    table = table[table["reclamations"] >= min_complaints]
    table["indemnisees"] = (table["indemnisees"] * 100).round(1)
    return table.sort_values("indemnisees", ascending=False).reset_index()


def duplicated_narratives(df: pd.DataFrame) -> pd.DataFrame:
    """Récits présents en plusieurs exemplaires mot pour mot, par année et sur toute la période."""
    texts = df.dropna(subset=["narrative"])
    texts = texts.assign(
        repete=texts["narrative"].duplicated(keep=False),
        indemnisee=texts["company_response"].eq(MONETARY_RELIEF),
    )

    def summarize(period: str, group: pd.DataFrame) -> dict[str, object]:
        return {
            "periode": period,
            "recits": len(group),
            "part_repetes": group["repete"].mean() * 100,
            "indemnisees_repetes": group.loc[group["repete"], "indemnisee"].mean() * 100,
            "indemnisees_uniques": group.loc[~group["repete"], "indemnisee"].mean() * 100,
        }

    rows = [
        summarize(str(year), group) for year, group in texts.groupby(texts["date_received"].dt.year)
    ]
    rows.append(summarize("toutes", texts))
    return pd.DataFrame(rows).round(2)


def plot_maturity(table: pd.DataFrame, out: Path) -> None:
    shown = table[
        table["age_jours"].isin(
            [f"{a}-{b}" for a, b in zip(AGE_BINS, AGE_BINS[1:10], strict=False)]
        )
    ]
    fig, ax = plt.subplots(figsize=(7.5, 3.2), facecolor=SURFACE)
    x = range(len(shown))
    ax.plot(
        x,
        shown["en_cours"],
        color=ORANGE,
        linewidth=2,
        marker="o",
        markersize=4,
        label="Encore en cours",
    )
    ax.plot(
        x,
        shown["indemnisees"],
        color=BLUE,
        linewidth=2,
        marker="o",
        markersize=4,
        label="Indemnisées",
    )
    _style(ax, "Issue des réclamations selon leur âge à la date de l'export (%)")
    ax.set_xticks(list(x), list(shown["age_jours"]))
    ax.set_xlabel("âge en jours", fontsize=8, color=INK_2)
    cutoff = list(shown["age_jours"]).index(f"{MATURITY_DAYS}-105")
    ax.axvline(cutoff - 0.5, color=INK_2, linewidth=1, linestyle="--")
    ax.annotate(
        f"règle des {MATURITY_DAYS} jours",
        (cutoff - 0.45, ax.get_ylim()[1] * 0.92),
        fontsize=8,
        color=INK_2,
    )
    ax.legend(frameon=False, fontsize=8, loc="center right", labelcolor=INK_2)
    fig.tight_layout()
    fig.savefig(out, dpi=200)
    plt.close(fig)


def plot_spike(daily: pd.DataFrame, out: Path) -> None:
    fig, ax = plt.subplots(figsize=(7.5, 3.2), facecolor=SURFACE)
    for column, color in zip(daily.columns, (BLUE, ORANGE, AQUA), strict=True):
        ax.plot(daily.index, daily[column], color=color, linewidth=2, label=column)
    _style(ax, "Réclamations reçues par jour, décembre 2024 à février 2025")
    ax.legend(frameon=False, fontsize=8, loc="upper right", labelcolor=INK_2)
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(out, dpi=200)
    plt.close(fig)


def plot_relief_by_issue(table: pd.DataFrame, out: Path) -> None:
    table = table.iloc[::-1]
    labels = [
        textwrap.fill(f"{issue} ({'carte' if product == 'Credit card' else 'compte'})", 52)
        for product, issue in zip(table["product"], table["issue"], strict=True)
    ]
    fig, ax = plt.subplots(figsize=(7.5, 0.36 * len(table) + 1.0), facecolor=SURFACE)
    bars = ax.barh(labels, table["indemnisees"], color=BLUE, height=0.6)
    _style(ax, "")
    # Titre placé sur la figure : les libellés longs décalent le cadre vers la droite.
    fig.suptitle(
        "Part de réclamations indemnisées par motif (%), hors gestionnaires de fichiers",
        x=0.02,
        ha="left",
        fontsize=11,
        color=INK,
    )
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    ax.grid(axis="y", visible=False)
    for bar, value in zip(bars, table["indemnisees"], strict=True):
        ax.annotate(
            f"{value:.1f}",
            (value, bar.get_y() + bar.get_height() / 2),
            xytext=(3, 0),
            textcoords="offset points",
            va="center",
            fontsize=7,
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
    data_out, figures_out = args.out / "data", args.out / "figures"
    data_out.mkdir(parents=True, exist_ok=True)
    figures_out.mkdir(parents=True, exist_ok=True)

    df, export_date = load_interim(args.data_dir)
    prepared, report = prepare_for_modeling(df, export_date)

    maturity = label_maturity(df, export_date)
    maturity.to_csv(data_out / "maturite-des-issues.csv", index=False)
    plot_maturity(maturity, figures_out / "maturite-des-issues.png")

    zero_relief_companies(df).to_csv(
        data_out / "etablissements-sans-indemnisation.csv", index=False
    )

    daily = january_2025_spike(df)
    daily.to_csv(data_out / "pic-janvier-2025.csv")
    plot_spike(daily, figures_out / "pic-janvier-2025.png")

    by_issue = relief_by_issue(prepared)
    by_issue.to_csv(data_out / "indemnisation-par-motif.csv", index=False)
    plot_relief_by_issue(by_issue, figures_out / "indemnisation-par-motif.png")

    duplicated_narratives(df).to_csv(data_out / "recits-repetes.csv", index=False)
    pd.DataFrame([asdict(report)]).to_csv(data_out / "preparation.csv", index=False)
    print(f"export du {export_date} : {report}")


if __name__ == "__main__":
    main()
