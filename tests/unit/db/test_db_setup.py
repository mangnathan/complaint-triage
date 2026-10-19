from __future__ import annotations

import os
from pathlib import Path

import pytest

from complaint_triage.db.roles import AGENT_READ, AGENT_WRITE, privilege_statements, role_statements
from complaint_triage.db.settings import database_url, write_env_values
from complaint_triage.db.setup import admin_password, random_passwords


def rendered() -> list[str]:
    return [statement.as_string() for statement in privilege_statements()]


def test_the_read_account_can_only_read() -> None:
    granted = [s for s in rendered() if s.startswith("GRANT") and f'"{AGENT_READ}"' in s]

    assert all("SELECT" in s or "CONNECT" in s or "USAGE" in s for s in granted)
    assert any("default_transaction_read_only = on" in s and AGENT_READ in s for s in rendered())


def test_the_write_account_can_only_change_a_status_and_log() -> None:
    granted = [s for s in rendered() if s.startswith("GRANT") and f'"{AGENT_WRITE}"' in s]
    updates = [s for s in granted if "UPDATE" in s]

    assert updates == [
        'GRANT UPDATE (status, status_updated_at) ON "triage".complaints TO "ct_agent_write"'
    ]
    assert not any("DELETE" in s or "TRUNCATE" in s or "ALL PRIVILEGES" in s for s in granted)


def test_agent_queries_have_a_time_limit() -> None:
    timeouts = [s for s in rendered() if "statement_timeout" in s]

    assert len(timeouts) == 2


def test_the_admin_password_lives_only_inside_the_block(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PGPASSWORD", raising=False)

    with admin_password("secret-à-ne-pas-garder"):
        assert os.environ["PGPASSWORD"] == "secret-à-ne-pas-garder"

    assert "PGPASSWORD" not in os.environ


def test_each_account_gets_a_different_random_password() -> None:
    first, second = random_passwords(), random_passwords()

    assert set(first) == {"ct_owner", "ct_agent_read", "ct_agent_write"}
    assert len(set(first.values())) == 3
    assert first != second
    assert all(len(pw) >= 32 for pw in first.values())


def test_passwords_are_quoted_as_literals() -> None:
    statement = role_statements("ct_owner", "it's; DROP ROLE x", exists=False).as_string()

    assert statement == "CREATE ROLE \"ct_owner\" WITH LOGIN PASSWORD 'it''s; DROP ROLE x'"


def test_special_characters_are_escaped_in_urls() -> None:
    url = database_url("ct_owner", "a/b@c:d")

    assert url == "postgresql://ct_owner:a%2Fb%40c%3Ad@localhost:5432/complaint_triage"


def test_env_values_are_replaced_without_touching_other_lines(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    env.write_text(
        "# commentaire\nGEMINI_API_KEY=secret\nDATABASE_URL_OWNER=old\n", encoding="utf-8"
    )

    write_env_values(env, {"DATABASE_URL_OWNER": "new", "DATABASE_URL_AGENT_READ": "read"})

    text = env.read_text(encoding="utf-8")
    assert "GEMINI_API_KEY=secret" in text
    assert "DATABASE_URL_OWNER=new" in text
    assert "old" not in text
    assert text.count("DATABASE_URL_AGENT_READ=read") == 1
