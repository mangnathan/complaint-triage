"""Compare trois méthodes de recherche sur les questions de développement, puis mesure la méthode
retenue sur les questions de test.

Règle de choix, fixée avant de lancer : le meilleur rappel@5 sur le développement (la génération
lira les 5 premiers passages), puis le meilleur MRR en cas d'égalité, puis la méthode la plus
simple. Les embeddings sont calculés en local : aucun appel à une API.

Usage : python scripts/rag/evaluate_retrieval.py
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from complaint_triage.rag.__main__ import PASSAGES_FILE
from complaint_triage.rag.embeddings import EMBEDDING_MODEL, FastEmbedder, cached_passage_vectors
from complaint_triage.rag.evaluation import (
    DEVELOPMENT,
    TEST,
    load_questions,
    rank_questions,
    summarize,
)
from complaint_triage.rag.retrieval import Bm25Index, DenseIndex, HybridRetriever, Retriever

BLUE, GREY, INK, INK_2, GRID, SURFACE = (
    "#2a78d6",
    "#9a9993",
    "#0b0b0b",
    "#52514e",
    "#e4e3df",
    "#fcfcfb",
)
QUESTIONS = Path("evaluation/rag/questions-recherche.csv")
# De la plus simple à la plus complexe : c'est aussi l'ordre de départage.
METHODS = ("Mots-clés (BM25)", "Sens (embeddings)", "Hybride (fusion des rangs)")


def plot(summary: pd.DataFrame, out: Path) -> None:
    fig, ax = plt.subplots(figsize=(7.5, 3.2), facecolor=SURFACE)
    x = np.arange(len(METHODS))
    for offset, part, color in ((-0.18, DEVELOPMENT, GREY), (0.18, TEST, BLUE)):
        values = summary[summary["partie"] == part].set_index("methode").loc[list(METHODS)]
        label = "Développement" if part == DEVELOPMENT else "Test"
        bars = ax.bar(x + offset, values["rappel@5"] * 100, width=0.34, color=color, label=label)
        for bar, value in zip(bars, values["rappel@5"] * 100, strict=True):
            ax.annotate(
                f"{value:.0f} %",
                (bar.get_x() + bar.get_width() / 2, value),
                xytext=(0, 3),
                textcoords="offset points",
                ha="center",
                fontsize=8,
                color=INK,
            )
    ax.set_xticks(x, METHODS)
    ax.set_ylim(0, 112)
    ax.set_ylabel("Rappel@5 (%)", fontsize=8, color=INK_2)
    ax.set_facecolor(SURFACE)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.tick_params(colors=INK_2, labelsize=8, length=0)
    ax.legend(fontsize=8, frameon=False, loc="upper left", ncol=2)
    fig.suptitle(
        "Part des questions dont un bon passage est dans les 5 premiers",
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
    parser.add_argument("--out", type=Path, default=Path("docs/v0.2-rag"))
    args = parser.parse_args()

    passages = pd.read_parquet(args.data_dir / PASSAGES_FILE)
    documents = (passages["heading"] + "\n" + passages["text"]).tolist()
    ids = passages["passage_id"].tolist()
    embedder = FastEmbedder(cache_dir=args.data_dir / "models" / "fastembed")
    vectors = cached_passage_vectors(
        embedder, EMBEDDING_MODEL, documents, args.data_dir / "rag" / "vectors.npz"
    )
    bm25 = Bm25Index(ids, documents)
    dense = DenseIndex(ids, vectors, embedder)
    retrievers: dict[str, Retriever] = {
        METHODS[0]: bm25,
        METHODS[1]: dense,
        METHODS[2]: HybridRetriever([bm25, dense]),
    }

    questions = load_questions(QUESTIONS)
    ranks = pd.DataFrame({name: rank_questions(r, questions) for name, r in retrievers.items()})
    rows = []
    for part in (DEVELOPMENT, TEST):
        in_part = (questions["partie"] == part).to_numpy()
        for name in METHODS:
            rows.append({"partie": part, "methode": name, **summarize(ranks[name][in_part])})
    summary = pd.DataFrame(rows)

    development = summary[summary["partie"] == DEVELOPMENT].set_index("methode")
    chosen = max(
        METHODS,
        key=lambda m: (development.at[m, "rappel@5"], development.at[m, "mrr"], -METHODS.index(m)),
    )

    data = args.out / "data"
    data.mkdir(parents=True, exist_ok=True)
    summary.round(3).to_csv(data / "recherche-resume.csv", index=False)
    per_question = questions[["id", "partie", "reglement", "question", "passages_attendus"]]
    per_question.join(ranks, on="id").to_csv(data / "recherche-par-question.csv", index=False)
    (args.out / "figures").mkdir(parents=True, exist_ok=True)
    plot(summary, args.out / "figures" / "recherche.png")

    with pd.option_context("display.width", 200):
        print(summary.round(3).to_string(index=False))
        print(per_question[["id", "partie"]].join(ranks, on="id").to_string(index=False))
    print(f"méthode retenue sur le développement : {chosen}")


if __name__ == "__main__":
    main()
