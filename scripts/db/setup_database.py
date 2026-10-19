"""Met en place la base : comptes, base, schéma et droits. À lancer soi-même, une fois.

Le mot de passe du super-utilisateur postgres est demandé en saisie masquée et n'est enregistré
nulle part. Les mots de passe des trois comptes du projet sont tirés au hasard et écrits dans
.env (ignoré par Git), sans jamais être affichés. Relancer le script change ces mots de passe.

Usage : uv run python scripts/db/setup_database.py
"""

from __future__ import annotations

import getpass
import os
import subprocess
from pathlib import Path

from complaint_triage.db.roles import DATABASE, ROLES, SCHEMA
from complaint_triage.db.settings import ENV_KEYS, database_url, write_env_values
from complaint_triage.db.setup import admin_password, create_database, random_passwords

ENV_FILE = Path(".env")


def ensure_ignored(path: Path) -> None:
    """Refuse d'écrire des mots de passe dans un fichier que Git pourrait versionner."""
    result = subprocess.run(  # noqa: S603
        ["git", "check-ignore", "-q", str(path)],  # noqa: S607
        check=False,
    )
    if result.returncode != 0:
        raise SystemExit(f"{path} n'est pas ignoré par Git : aucun mot de passe n'est écrit.")


def main() -> None:
    ensure_ignored(ENV_FILE)
    # En CI, la base est jetable et le mot de passe vient de l'environnement ; sur un poste, il
    # est demandé en saisie masquée et n'est enregistré nulle part.
    password = os.environ.get("POSTGRES_ADMIN_PASSWORD") or getpass.getpass(
        "Mot de passe du super-utilisateur postgres : "
    )
    passwords = random_passwords()
    with admin_password(password):
        create_database(passwords)
    write_env_values(
        ENV_FILE, {ENV_KEYS[role]: database_url(role, pw) for role, pw in passwords.items()}
    )
    print(f"Base {DATABASE} prête : schéma {SCHEMA}, comptes {', '.join(ROLES)}.")
    print(f"Adresses de connexion écrites dans {ENV_FILE} (mots de passe non affichés).")


if __name__ == "__main__":
    main()
