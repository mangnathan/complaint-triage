"""Outils de l'agent sur la vraie base, avec des réclamations fictives d'un établissement fictif.

Sautés sans base configurée (en CI, par exemple).
"""

from __future__ import annotations

import json
import os
from collections.abc import Iterator
from pathlib import Path

import psycopg
import pytest

from complaint_triage.agent.database import AgentDatabase
from complaint_triage.agent.receiver import start_receiver
from complaint_triage.agent.tools import ToolContext, ToolError, call_tool
from complaint_triage.db.roles import OWNER
from complaint_triage.db.settings import ENV_KEYS, url_for
from complaint_triage.rag.answer import REFUSED, Answer
from complaint_triage.rag.llm import load_dotenv

load_dotenv(Path(".env"))
# En CI, REQUIRE_DATABASE=1 : un test qui serait sauté faute de base échoue au lieu de passer.
pytestmark = pytest.mark.skipif(
    os.environ.get("REQUIRE_DATABASE") != "1"
    and not all(os.environ.get(key) for key in ENV_KEYS.values()),
    reason="base PostgreSQL non configurée",
)
BANK = "Banque fictive des tests"
# Identifiants hors de portée des vrais (7 à 8 chiffres au CFPB). Même semaine, même produit.
COMPLAINTS = {
    9_000_000_101: 0.9,
    9_000_000_102: 0.5,
    9_000_000_103: 0.1,
    9_000_000_104: 0.3,
    9_000_000_105: 0.2,
}


@pytest.fixture
def bank() -> Iterator[str]:
    with psycopg.connect(url_for(OWNER)) as conn:
        for complaint_id, score in COMPLAINTS.items():
            conn.execute(
                "INSERT INTO triage.complaints (complaint_id, date_received, product, issue,"
                " company, priority_score) VALUES (%s, '2026-03-04', 'Credit card', 'Fees', %s, %s)"
                " ON CONFLICT (complaint_id) DO NOTHING",
                (complaint_id, BANK, score),
            )
    yield BANK
    with psycopg.connect(url_for(OWNER)) as conn:
        ids = list(COMPLAINTS)
        conn.execute("DELETE FROM triage.action_log WHERE complaint_id = ANY(%s)", (ids,))
        conn.execute("DELETE FROM triage.complaints WHERE complaint_id = ANY(%s)", (ids,))


@pytest.fixture
def ctx(tmp_path: Path) -> Iterator[ToolContext]:
    server = start_receiver(tmp_path / "alertes.jsonl", port=0)
    port = server.server_address[1]
    yield ToolContext(
        database=AgentDatabase.from_environment(),
        ask_regulations=lambda question: Answer(REFUSED, reason="Not tested here."),
        alert_url=f"http://127.0.0.1:{port}/alerts",
        actor="test",
    )
    server.shutdown()


def log_entries(complaint_id: int) -> list[tuple[str, dict[str, object]]]:
    with psycopg.connect(url_for(OWNER)) as conn:
        return conn.execute(
            "SELECT action, details FROM triage.action_log WHERE complaint_id = %s ORDER BY id",
            (complaint_id,),
        ).fetchall()


def test_find_company_matches_part_of_the_name(bank: str, ctx: ToolContext) -> None:
    result = call_tool(ctx, "find_company", {"name": "fictive des"})

    assert result["etablissements"] == [{"company": bank, "reclamations": 5}]


def test_like_wildcards_typed_by_the_model_are_literal(bank: str, ctx: ToolContext) -> None:
    assert call_tool(ctx, "find_company", {"name": "%%"})["etablissements"] == []


def test_the_queue_is_ordered_by_priority(bank: str, ctx: ToolContext) -> None:
    result = call_tool(ctx, "list_priority_queue", {"company": bank, "limit": 3})

    assert [d["complaint_id"] for d in result["dossiers"]] == [
        9_000_000_101,
        9_000_000_102,
        9_000_000_104,
    ]


def test_an_approximate_institution_name_is_refused(bank: str, ctx: ToolContext) -> None:
    with pytest.raises(ToolError, match="find_company"):
        call_tool(ctx, "list_priority_queue", {"company": "Banque fictive"})


def test_priority_context_places_the_complaint_in_its_weekly_queue(
    bank: str, ctx: ToolContext
) -> None:
    top = call_tool(ctx, "priority_context", {"complaint_id": 9_000_000_101})
    low = call_tool(ctx, "priority_context", {"complaint_id": 9_000_000_103})

    assert (top["rang"], top["taille"], top["prioritaire"]) == (1, 5, True)
    assert (low["rang"], low["prioritaire"]) == (5, False)


def test_an_unknown_complaint_is_reported(ctx: ToolContext) -> None:
    with pytest.raises(ToolError, match="introuvable"):
        call_tool(ctx, "get_complaint", {"complaint_id": 999_999_999})


def test_a_status_change_is_logged_with_its_reason(bank: str, ctx: ToolContext) -> None:
    call_tool(
        ctx,
        "update_status",
        {"complaint_id": 9_000_000_101, "status": "en_cours", "reason": "Top priority"},
    )

    assert call_tool(ctx, "get_complaint", {"complaint_id": 9_000_000_101})["status"] == "en_cours"
    assert log_entries(9_000_000_101) == [
        (
            "changement de statut",
            {"avant": "nouveau", "apres": "en_cours", "raison": "Top priority"},
        )
    ]


def test_setting_the_same_status_twice_is_refused(bank: str, ctx: ToolContext) -> None:
    arguments = {"complaint_id": 9_000_000_102, "status": "traite", "reason": "Handled"}
    call_tool(ctx, "update_status", arguments)

    with pytest.raises(ToolError, match="déjà"):
        call_tool(ctx, "update_status", arguments)
    assert len(log_entries(9_000_000_102)) == 1


def test_an_alert_reaches_the_receiver_and_the_log(
    bank: str, ctx: ToolContext, tmp_path: Path
) -> None:
    call_tool(
        ctx,
        "raise_alert",
        {
            "complaint_id": 9_000_000_101,
            "severity": "urgent",
            "message": "Likely refund, act today.",
        },
    )

    received = [json.loads(line) for line in (tmp_path / "alertes.jsonl").read_text().splitlines()]
    assert received[0]["alerte"]["complaint_id"] == 9_000_000_101
    assert log_entries(9_000_000_101)[0][0] == "alerte"


def test_a_failed_alert_leaves_no_trace_in_the_log(bank: str, ctx: ToolContext) -> None:
    ctx.alert_url = "http://127.0.0.1:1/alerts"  # aucun récepteur à cette adresse

    with pytest.raises(OSError):
        call_tool(
            ctx,
            "raise_alert",
            {"complaint_id": 9_000_000_103, "severity": "info", "message": "This will not arrive."},
        )
    assert log_entries(9_000_000_103) == []
