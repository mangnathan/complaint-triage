"""Publie la démo sur Hugging Face Spaces : huggingface.co/spaces/mangnathan/complaint-triage.

Le dépôt du Space reçoit seulement ce qu'il faut pour construire l'image : le Dockerfile de la
démo, le code, le uv.lock, les données de data/demo/ (scripts/demo/build_demo_data.py) et une
fiche de présentation. Rien d'autre ne part : ni .env, ni tests, ni le reste de data/. Le
jeton HF_TOKEN (droit d'écriture) est lu dans .env et n'est jamais affiché. La clé Gemini de
la démo se règle dans les paramètres du Space, pas ici.

Le dépôt local doit être propre : le Space porte le numéro du commit déployé.

Usage : uv run python scripts/demo/deploy_space.py [--dry-run]
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from huggingface_hub import HfApi

from complaint_triage.rag.llm import load_dotenv

SPACE = "mangnathan/complaint-triage"
REPOSITORY = "https://github.com/mangnathan/complaint-triage"
DEMO_DATA = Path("data/demo")
REQUIRED_DATA = ("demo-complaints.parquet", "rag/passages.parquet", "rag/vectors.npz")

SPACE_CARD = """---
title: complaint-triage
emoji: 📋
colorFrom: blue
colorTo: gray
sdk: docker
app_port: 7860
license: mit
short_description: Priorisation de réclamations, RAG réglementaire et agent
---

# complaint-triage : démonstration

Priorisation des réclamations bancaires, réponses de réglementation sourcées et agent aux
outils encadrés, sur les données publiques du CFPB et les textes de l'eCFR.

Code, rapports et notes de décision : {repository} (commit `{commit}`).

Ce dépôt est produit par `scripts/demo/deploy_space.py` : ne pas le modifier à la main.
"""

DOCKERIGNORE = """.git/
**/__pycache__/
"""


def git(*arguments: str) -> str:
    result = subprocess.run(  # noqa: S603
        ["git", *arguments],  # noqa: S607
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def stage(folder: Path, commit: str) -> None:
    """Assemble le dépôt du Space ; chaque fichier est choisi, rien n'est copié en bloc."""
    shutil.copyfile("demo/Dockerfile", folder / "Dockerfile")
    for name in ("pyproject.toml", "uv.lock", "LICENSE"):
        shutil.copyfile(name, folder / name)
    shutil.copytree("src", folder / "src", ignore=shutil.ignore_patterns("__pycache__"))
    for name in REQUIRED_DATA:
        target = folder / "demo" / "data" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(DEMO_DATA / name, target)
    (folder / "README.md").write_text(
        SPACE_CARD.format(repository=REPOSITORY, commit=commit), encoding="utf-8"
    )
    (folder / ".dockerignore").write_text(DOCKERIGNORE, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run", action="store_true", help="assembler et lister, sans rien envoyer"
    )
    args = parser.parse_args()

    if git("status", "--porcelain"):
        raise SystemExit("Dépôt local modifié : committer d'abord, le Space porte un commit.")
    missing = [name for name in REQUIRED_DATA if not (DEMO_DATA / name).exists()]
    if missing:
        raise SystemExit(f"Données absentes de {DEMO_DATA} : {missing}. Lancer build_demo_data.")
    commit = git("rev-parse", "--short", "HEAD")

    with tempfile.TemporaryDirectory(prefix="space-") as staging:
        folder = Path(staging)
        stage(folder, commit)
        files = sorted(p.relative_to(folder).as_posix() for p in folder.rglob("*") if p.is_file())
        print(f"{len(files)} fichiers à publier sur {SPACE} (commit {commit}).")
        if args.dry_run:
            print("\n".join(files))
            return
        load_dotenv(Path(".env"))
        token = os.environ.get("HF_TOKEN")
        if not token:
            raise SystemExit(
                "HF_TOKEN absent de .env : créer un jeton d'écriture sur Hugging Face."
            )
        api = HfApi(token=token)
        # Space créé à la main de préférence : le jeton peut alors se limiter à ce seul dépôt.
        if not api.repo_exists(SPACE, repo_type="space"):
            api.create_repo(SPACE, repo_type="space", space_sdk="docker")
        api.upload_folder(
            folder_path=folder,
            repo_id=SPACE,
            repo_type="space",
            commit_message=f"Déploie {commit} de {REPOSITORY}",
            # Un module supprimé du projet doit aussi disparaître du Space.
            delete_patterns=["src/**"],
        )
    print(f"Publié : https://huggingface.co/spaces/{SPACE} (construction en cours).")


if __name__ == "__main__":
    main()
