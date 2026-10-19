"""Vérifie sur la vraie base que chaque compte ne peut faire que ce qui lui est permis.

Ces tests demandent une base PostgreSQL mise en place par scripts/db/setup_database.py. Sans les
adresses de connexion (en CI, par exemple), ils sont sautés.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import psycopg
import pytest

from complaint_triage.db.roles import AGENT_READ, AGENT_WRITE, OWNER
from complaint_triage.db.settings import ENV_KEYS, url_for
from complaint_triage.rag.llm import load_dotenv

load_dotenv(Path(".env"))
# En CI, REQUIRE_DATABASE=1 : un test qui serait sauté faute de base échoue au lieu de passer.
pytestmark = pytest.mark.skipif(
    os.environ.get("REQUIRE_DATABASE") != "1"
    and not all(os.environ.get(key) for key in ENV_KEYS.values()),
    reason="base PostgreSQL non configurée",
)
TEST_ID = -1  # identifiant négatif : jamais celui d'une vraie réclamation


@pytest.fixture
def test_complaint() -> Iterator[int]:
    """Une réclamation fictive, créée par le propriétaire puis supprimée."""
    with psycopg.connect(url_for(OWNER)) as conn:
        conn.execute(
            "INSERT INTO triage.complaints (complaint_id, date_received, product, issue, company,"
            " priority_score) VALUES (%s, '2026-01-02', 'Credit card', 'Test', 'Test bank', 0.5)"
            " ON CONFLICT (complaint_id) DO NOTHING",
            (TEST_ID,),
        )
    yield TEST_ID
    with psycopg.connect(url_for(OWNER)) as conn:
        conn.execute("DELETE FROM triage.action_log WHERE complaint_id = %s", (TEST_ID,))
        conn.execute("DELETE FROM triage.complaints WHERE complaint_id = %s", (TEST_ID,))


def test_the_read_account_reads_but_cannot_write(test_complaint: int) -> None:
    with psycopg.connect(url_for(AGENT_READ)) as conn:
        row = conn.execute(
            "SELECT status FROM complaints WHERE complaint_id = %s", (test_complaint,)
        ).fetchone()
        assert row == ("nouveau",)
        with pytest.raises(psycopg.errors.ReadOnlySqlTransaction):
            conn.execute(
                "UPDATE complaints SET status = 'traite' WHERE complaint_id = %s",
                (test_complaint,),
            )


def test_the_read_account_cannot_leave_read_only_mode(test_complaint: int) -> None:
    with psycopg.connect(url_for(AGENT_READ), autocommit=True) as conn:
        conn.execute("SET default_transaction_read_only = off")
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute(
                "UPDATE complaints SET status = 'traite' WHERE complaint_id = %s",
                (test_complaint,),
            )


def test_the_write_account_changes_a_status_and_logs_it(test_complaint: int) -> None:
    with psycopg.connect(url_for(AGENT_WRITE)) as conn:
        conn.execute(
            "UPDATE complaints SET status = 'en_cours', status_updated_at = now()"
            " WHERE complaint_id = %s",
            (test_complaint,),
        )
        conn.execute(
            "INSERT INTO action_log (actor, action, complaint_id) VALUES ('test', 'statut', %s)",
            (test_complaint,),
        )


@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE complaints SET priority_score = 1 WHERE complaint_id = %s",
        "UPDATE complaints SET company = 'Other' WHERE complaint_id = %s",
        "DELETE FROM complaints WHERE complaint_id = %s",
        "DELETE FROM action_log WHERE complaint_id = %s",
    ],
)
def test_the_write_account_cannot_do_anything_else(test_complaint: int, statement: str) -> None:
    with (
        psycopg.connect(url_for(AGENT_WRITE)) as conn,
        pytest.raises(psycopg.errors.InsufficientPrivilege),
    ):
        conn.execute(statement, (test_complaint,))  # type: ignore[arg-type]


def test_an_invalid_status_is_refused_by_the_database(test_complaint: int) -> None:
    with (
        psycopg.connect(url_for(AGENT_WRITE)) as conn,
        pytest.raises(psycopg.errors.CheckViolation),
    ):
        conn.execute(
            "UPDATE complaints SET status = 'supprime' WHERE complaint_id = %s",
            (test_complaint,),
        )
