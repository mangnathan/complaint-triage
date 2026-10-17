"""Schéma d'architecture cible de complaint-triage (figure du rapport de cadrage)."""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.axes import Axes
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

BLUE = "#2a78d6"
INK = "#0b0b0b"
INK_2 = "#52514e"
FILL = "#eef4fc"
EXTERNAL = "#f3f3f1"

Box = tuple[float, float, float, float]  # x, y, largeur, hauteur


def _box(ax: Axes, box: Box, title: str, detail: str, external: bool = False) -> None:
    x, y, w, h = box
    ax.add_patch(
        FancyBboxPatch(
            (x, y),
            w,
            h,
            boxstyle="round,pad=0,rounding_size=0.12",
            facecolor=EXTERNAL if external else FILL,
            edgecolor=INK_2 if external else BLUE,
            linewidth=1.2,
        )
    )
    ax.text(
        x + w / 2,
        y + h * 0.66,
        title,
        ha="center",
        va="center",
        fontsize=9.5,
        fontweight="bold",
        color=INK,
    )
    ax.text(
        x + w / 2,
        y + h * 0.3,
        detail,
        ha="center",
        va="center",
        fontsize=7.5,
        color=INK_2,
        linespacing=1.3,
    )


def _arrow(ax: Axes, start: tuple[float, float], end: tuple[float, float]) -> None:
    ax.add_patch(
        FancyArrowPatch(start, end, arrowstyle="-|>", mutation_scale=10, color=INK_2, linewidth=1.1)
    )


def draw(out: Path) -> None:
    fig, ax = plt.subplots(figsize=(8.6, 5.4), facecolor="white")
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 7.6)
    ax.axis("off")

    api = (0.1, 5.9, 2.3, 1.2)
    ingest = (3.0, 5.9, 2.6, 1.2)
    db = (6.3, 5.9, 2.8, 1.2)
    archive = (9.6, 5.9, 2.3, 1.2)
    scoring = (0.1, 3.2, 2.7, 1.5)
    rag = (3.1, 3.2, 2.7, 1.5)
    agent = (6.1, 3.2, 2.7, 1.5)
    monitoring = (9.1, 3.2, 2.8, 1.5)
    serving = (5.4, 0.6, 3.4, 1.3)
    alert = (9.6, 0.6, 2.3, 1.3)

    _box(ax, api, "API CFPB", "données structurées\nquotidiennes", external=True)
    _box(ax, ingest, "Ingestion", "validation de schéma,\ncontrôles qualité")
    _box(ax, db, "PostgreSQL", "réclamations, scores,\njournal des décisions")
    _box(ax, archive, "Archive FOIA", "récits jusqu'au\n14/08/2026 (figée)", external=True)
    _box(ax, scoring, "Scoring", "priorité d'indemnisation\n+ modèle de repli sans texte")
    _box(ax, rag, "RAG", "réponse avec citations\nou refus")
    _box(ax, agent, "Agent", "plan, outils SQL\net webhook, refus")
    _box(ax, monitoring, "Monitoring", "dérive, qualité,\névaluation « shadow »")
    _box(ax, serving, "API FastAPI + tableau de bord", "point d'entrée unique, journalisé")
    _box(ax, alert, "Alerte", "webhook\n(Discord / Slack)", external=True)

    _arrow(ax, (2.4, 6.5), (3.0, 6.5))
    _arrow(ax, (5.6, 6.5), (6.3, 6.5))
    _arrow(ax, (9.6, 6.5), (9.1, 6.5))
    for x in (1.45, 4.45, 7.45, 10.5):
        _arrow(ax, (7.7, 5.9), (x, 4.7))
    _arrow(ax, (6.1, 3.95), (5.8, 3.95))
    _arrow(ax, (7.1, 1.9), (7.45, 3.2))
    _arrow(ax, (8.6, 3.2), (10.0, 1.9))
    _arrow(ax, (10.6, 3.2), (10.8, 1.9))

    ax.text(
        0.1,
        7.35,
        "Sources externes en gris, composants complaint-triage en bleu",
        fontsize=7.5,
        color=INK_2,
    )
    fig.tight_layout()
    fig.savefig(out, dpi=200)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out", type=Path, default=Path("docs/v0.0-cadrage/figures/architecture-cible.png")
    )
    args = parser.parse_args()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    draw(args.out)


if __name__ == "__main__":
    main()
