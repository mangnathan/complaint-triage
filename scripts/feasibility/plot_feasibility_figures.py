"""Graphiques du rapport de cadrage, à partir des CSV de collect_cfpb_feasibility_stats.py."""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.axes import Axes

BLUE = "#2a78d6"
ORANGE = "#eb6834"
INK = "#0b0b0b"
INK_2 = "#52514e"
GRID = "#e4e3df"
SURFACE = "#fcfcfb"
NARRATIVE_CUTOFF = pd.Timestamp("2026-08-14")


def _style(ax: Axes, title: str) -> None:
    ax.set_facecolor(SURFACE)
    ax.set_title(title, loc="left", fontsize=11, color=INK, pad=10)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(colors=INK_2, labelsize=8, length=0)


def _mark_cutoff(ax: Axes) -> None:
    # matplotlib convertit les dates à l'exécution, mais ses annotations n'acceptent que des float.
    ax.axvline(NARRATIVE_CUTOFF, color=INK_2, linewidth=1, linestyle="--")  # type: ignore[arg-type]
    ax.annotate(
        "14/08/2026 : fin des récits",
        (NARRATIVE_CUTOFF, ax.get_ylim()[1]),
        xytext=(-6, -4),
        textcoords="offset points",
        ha="right",
        va="top",
        fontsize=8,
        color=INK_2,
    )


def plot_volume(df: pd.DataFrame, out: Path) -> None:
    fig, ax = plt.subplots(figsize=(7.5, 3.2), facecolor=SURFACE)
    complete = df[df["month"] < "2026-10"]
    ax.plot(complete["date"], complete["total"], color=BLUE, linewidth=2)
    _style(ax, "Réclamations reçues par mois - cartes de crédit + comptes courants/épargne")
    ax.set_ylim(0, complete["total"].max() * 1.12)
    spike = complete.iloc[int(complete["total"].to_numpy().argmax())]
    ax.annotate(
        f"Pic {spike['month']} : {spike['total']:,}".replace(",", " "),
        (spike["date"], spike["total"]),
        xytext=(8, -2),
        textcoords="offset points",
        fontsize=8,
        color=INK_2,
    )
    _mark_cutoff(ax)
    fig.tight_layout()
    fig.savefig(out, dpi=200)
    plt.close(fig)


def plot_responses(df: pd.DataFrame, out: Path) -> None:
    fig, ax = plt.subplots(figsize=(7.5, 3.2), facecolor=SURFACE)
    complete = df[df["month"] < "2026-10"]
    monetary = 100 * complete["Closed with monetary relief"] / complete["total"]
    pending = 100 * complete["In progress"] / complete["total"]
    ax.plot(complete["date"], monetary, color=BLUE, linewidth=2, label="Indemnisation financière")
    ax.plot(complete["date"], pending, color=ORANGE, linewidth=2, label="Encore « In progress »")
    _style(ax, "Part des réclamations par issue (%) - même périmètre")
    ax.set_ylim(0, max(monetary.max(), pending.max()) * 1.15)
    ax.legend(frameon=False, fontsize=8, loc="upper left", labelcolor=INK_2)
    last = complete.iloc[-1]
    ax.annotate(
        f"{pending.iloc[-1]:.0f} %",
        (last["date"], pending.iloc[-1]),
        xytext=(4, 0),
        textcoords="offset points",
        fontsize=8,
        color=INK_2,
        va="center",
    )
    _mark_cutoff(ax)
    fig.tight_layout()
    fig.savefig(out, dpi=200)
    plt.close(fig)


def plot_narratives(cov: pd.DataFrame, out: Path) -> None:
    fig, ax = plt.subplots(figsize=(7.5, 2.6), facecolor=SURFACE)
    share = 100 * cov["narrative_share_scope"]
    bars = ax.bar(cov["period"], share, color=BLUE, width=0.5)
    _style(ax, "Part des réclamations du périmètre avec récit client (archive FOIA, %)")
    ax.set_ylim(0, 65)
    for bar, value in zip(bars, share, strict=True):
        ax.annotate(
            f"{value:.0f} %",
            (bar.get_x() + bar.get_width() / 2, value),
            xytext=(0, 3),
            textcoords="offset points",
            ha="center",
            fontsize=9,
            color=INK,
        )
    fig.tight_layout()
    fig.savefig(out, dpi=200)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=Path("docs/v0.0-cadrage/data"))
    parser.add_argument("--out", type=Path, default=Path("docs/v0.0-cadrage/figures"))
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    monthly = pd.read_csv(args.data / "series-mensuelles-perimetre-bancaire.csv")
    monthly["date"] = pd.to_datetime(monthly["month"])
    plot_volume(monthly, args.out / "volume-mensuel-reclamations.png")
    plot_responses(monthly, args.out / "issues-des-reclamations-par-mois.png")
    plot_narratives(
        pd.read_csv(args.data / "couverture-des-recits-archive-foia.csv"),
        args.out / "couverture-des-recits-clients.png",
    )


if __name__ == "__main__":
    main()
