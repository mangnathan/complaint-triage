"""Met en place la base : comptes, base, schéma et droits. À lancer soi-même, une fois.

Le mot de passe du super-utilisateur postgres est demandé en saisie masquée et n'est enregistré
nulle part. Les mots de passe des trois comptes du projet sont tirés au hasard et écrits dans
.env (ignoré par Git), sans jamais être affichés. Relancer le script change ces mots de passe.

Usage : uv run python scripts/db/setup_database.py
"""

from __future__ import annotations

import getpass
import os
import secrets
import subprocess
from importlib.resources import files
from pathlib import Path

import psycopg
from psycopg import sql

from complaint_triage.db.roles import (
    DATABASE,
    OWNER,
    ROLES,
    SCHEMA,
    privilege_statements,
    role_statements,
)
from complaint_triage.db.settings import ENV_KEYS, database_url, write_env_values

ENV_FILE = Path(".env")


def ensure_ignored(path: Path) -> None:
    """Refuse d'écrire des mots de passe dans un fichier que Git pourrait versionner."""
    result = subprocess.run(  # noqa: S603
        ["git", "check-ignore", "-q", str(path)],  # noqa: S607
        check=False,
    )
    if result.returncode != 0:
        raise SystemExit(f"{path} n'est pas ignoré par Git : aucun mot de passe n'est écrit.")


def connect_as_admin(dbname: str) -> psycopg.Connection[tuple[object, ...]]:
    # Le mot de passe passe par PGPASSWORD et non par la chaîne de connexion : sous Windows,
    # libpq prend l'octet 0xA0 pour un espace et couperait un mot de passe contenant « à ».
    return psycopg.connect(
        host="localhost", port=5432, user="postgres", dbname=dbname, autocommit=True
    )


def main() -> None:
    ensure_ignored(ENV_FILE)
    admin_password = getpass.getpass("Mot de passe du super-utilisateur postgres : ")
    passwords = {role: secrets.token_urlsafe(24) for role in ROLES}
    # Variable propre à ce processus, effacée dès la fin de la mise en place.
    os.environ["PGPASSWORD"] = admin_password
    try:
        configure(passwords)
    finally:
        os.environ.pop("PGPASSWORD", None)
    write_env_values(
        ENV_FILE, {ENV_KEYS[role]: database_url(role, pw) for role, pw in passwords.items()}
    )
    print(f"Base {DATABASE} prête : schéma {SCHEMA}, comptes {', '.join(ROLES)}.")
    print(f"Adresses de connexion écrites dans {ENV_FILE} (mots de passe non affichés).")


def configure(passwords: dict[str, str]) -> None:
    """Comptes, base, schéma et droits, en tant que super-utilisateur."""
    with connect_as_admin("postgres") as conn:
        for role, password in passwords.items():
            exists = conn.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (role,)).fetchone()
            conn.execute(role_statements(role, password, exists is not None))
        if (
            conn.execute("SELECT 1 FROM pg_database WHERE datname = %s", (DATABASE,)).fetchone()
            is None
        ):
            conn.execute(
                sql.SQL("CREATE DATABASE {} OWNER {}").format(
                    sql.Identifier(DATABASE), sql.Identifier(OWNER)
                )
            )

    schema_sql = files("complaint_triage.db").joinpath("schema.sql").read_text(encoding="utf-8")
    with connect_as_admin(DATABASE) as conn:
        conn.execute(
            sql.SQL("CREATE SCHEMA IF NOT EXISTS {} AUTHORIZATION {}").format(
                sql.Identifier(SCHEMA), sql.Identifier(OWNER)
            )
        )
        conn.execute(sql.SQL("SET ROLE {}").format(sql.Identifier(OWNER)))
        conn.execute(schema_sql)  # fichier du dépôt, sans aucun paramètre extérieur
        conn.execute("RESET ROLE")
        for statement in privilege_statements():
            conn.execute(statement)


if __name__ == "__main__":
    main()
