"""Publie la démo : pousse le contenu de l'image vers github.com/mangnathan/complaint-triage-demo.

Render construit et redéploie la démo à chaque commit de ce dépôt. Il ne reçoit que ce qu'il
faut pour construire l'image : le Dockerfile de la démo, le code, le uv.lock, les données de
data/demo/ (scripts/demo/build_demo_data.py), la configuration Render et une fiche de
présentation. Rien d'autre ne part : ni .env, ni tests, ni le reste de data/. Aucun jeton
n'est nécessaire : Git utilise les identifiants déjà enregistrés sur le poste. La clé Gemini
de la démo se règle dans le tableau de bord de Render, jamais ici.

Seul un commit de main, propre, est publié : la démo porte son numéro.

Usage : uv run python scripts/demo/deploy_demo.py [--dry-run]
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import tempfile
from pathlib import Path

REPOSITORY = "https://github.com/mangnathan/complaint-triage"
DEMO_REPOSITORY = "https://github.com/mangnathan/complaint-triage-demo.git"
DEMO_DATA = Path("data/demo")
REQUIRED_DATA = ("demo-complaints.parquet", "rag/passages.parquet", "rag/vectors.npz")

README = """# complaint-triage : démonstration

Dépôt de déploiement de la démo publique, produit par `scripts/demo/deploy_demo.py` à partir de
{repository} (commit `{commit}`). Ne pas le modifier à la main : le code, les rapports et les
notes de décision sont dans le dépôt principal.

Il contient de quoi construire l'image de la démo, avec un échantillon des réclamations
publiques du CFPB et le corpus réglementaire de l'eCFR. Render la construit à chaque commit.
"""

RENDER_BLUEPRINT = """services:
  - type: web
    name: complaint-triage
    runtime: docker
    plan: free
    region: frankfurt
    dockerfilePath: ./Dockerfile
    healthCheckPath: /_stcore/health
    autoDeploy: true
"""

DOCKERIGNORE = """.git/
**/__pycache__/
"""


def git(*arguments: str, cwd: Path | None = None) -> str:
    result = subprocess.run(  # noqa: S603
        ["git", *arguments],  # noqa: S607
        check=True,
        capture_output=True,
        text=True,
        cwd=cwd,
    )
    return result.stdout.strip()


def stage(folder: Path, commit: str) -> None:
    """Remplit le dépôt de la démo ; chaque fichier est choisi, rien n'est copié en bloc."""
    for path in folder.iterdir():
        if path.name == ".git":
            continue
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
    shutil.copyfile("demo/Dockerfile", folder / "Dockerfile")
    for name in ("pyproject.toml", "uv.lock", "LICENSE"):
        shutil.copyfile(name, folder / name)
    shutil.copytree("src", folder / "src", ignore=shutil.ignore_patterns("__pycache__"))
    for name in REQUIRED_DATA:
        target = folder / "demo" / "data" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(DEMO_DATA / name, target)
    texts = {
        "README.md": README.format(repository=REPOSITORY, commit=commit),
        "render.yaml": RENDER_BLUEPRINT,
        ".dockerignore": DOCKERIGNORE,
    }
    for name, text in texts.items():
        (folder / name).write_text(text, encoding="utf-8", newline="\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run", action="store_true", help="assembler et lister, sans rien envoyer"
    )
    args = parser.parse_args()

    if git("status", "--porcelain"):
        raise SystemExit("Dépôt local modifié : committer d'abord, la démo porte un commit.")
    if not args.dry_run and git("branch", "--show-current") != "main":
        raise SystemExit("Seul un commit de main, vérifié par la CI, est publié.")
    missing = [name for name in REQUIRED_DATA if not (DEMO_DATA / name).exists()]
    if missing:
        raise SystemExit(f"Données absentes de {DEMO_DATA} : {missing}. Lancer build_demo_data.")
    commit = git("rev-parse", "--short", "HEAD")

    # Sous Windows, Git laisse des fichiers en lecture seule : le nettoyage peut échouer sans gêne.
    with tempfile.TemporaryDirectory(prefix="demo-", ignore_cleanup_errors=True) as tmp:
        folder = Path(tmp) / "depot"
        if args.dry_run:
            folder.mkdir()
        else:
            git("clone", "--quiet", DEMO_REPOSITORY, str(folder))
        stage(folder, commit)
        files = sorted(
            p.relative_to(folder).as_posix()
            for p in folder.rglob("*")
            if p.is_file() and ".git" not in p.relative_to(folder).parts
        )
        print(f"{len(files)} fichiers pour la démo (commit {commit}).")
        if args.dry_run:
            print("\n".join(files))
            return
        git("add", "--all", cwd=folder)
        if not git("status", "--porcelain", cwd=folder):
            print("La démo est déjà à jour : rien à publier.")
            return
        identity = ["-c", f"user.name={git('config', 'user.name')}"]
        identity += ["-c", f"user.email={git('config', 'user.email')}"]
        git(*identity, "commit", "--quiet", "-m", f"Déploie {commit} de {REPOSITORY}", cwd=folder)
        git("push", "--quiet", "origin", "HEAD:main", cwd=folder)
    print("Publié : Render reconstruit la démo (quelques minutes).")


if __name__ == "__main__":
    main()
