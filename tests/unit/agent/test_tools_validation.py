"""Validation des entrées des outils, sans base : tout est refusé avant d'atteindre la base."""

from __future__ import annotations

import json
import urllib.request
from typing import Any

import pytest

from complaint_triage.agent.alerts import check_webhook_url, send_alert
from complaint_triage.agent.database import AgentDatabase
from complaint_triage.agent.tools import TOOLS, ToolContext, ToolError, call_tool
from complaint_triage.rag.answer import ANSWERED, REFUSED, Answer, Source


class NoDatabase(AgentDatabase):
    """Échoue si un outil tente d'ouvrir la base : la validation doit refuser avant."""

    def reading(self) -> Any:
        raise AssertionError("la base ne devait pas être ouverte")

    writing = reading


def context(answer: Answer | None = None) -> ToolContext:
    return ToolContext(
        database=NoDatabase("", ""),
        ask_regulations=lambda question: answer or Answer(REFUSED, reason="Nothing."),
        alert_url="http://127.0.0.1:1/alerts",
    )


@pytest.mark.parametrize(
    ("name", "arguments", "expected"),
    [
        ("get_complaint", {"complaint_id": -5}, "complaint_id"),
        ("get_complaint", {"complaint_id": "123"}, "complaint_id"),  # pas de conversion implicite
        ("get_complaint", {"complaint_id": 1, "sql": "DROP TABLE"}, "sql"),  # champ inconnu
        ("list_priority_queue", {"company": "Bank", "limit": 500}, "limit"),
        ("list_priority_queue", {"company": "Bank", "product": "Mortgage"}, "product"),
        ("update_status", {"complaint_id": 1, "status": "nouveau", "reason": "Retour"}, "status"),
        ("update_status", {"complaint_id": 1, "status": "traite"}, "reason"),
        (
            "raise_alert",
            {"complaint_id": 1, "severity": "critique", "message": "x" * 20},
            "severity",
        ),
        ("find_company", {"name": "x"}, "name"),
    ],
)
def test_invalid_inputs_are_refused_before_any_action(
    name: str, arguments: dict[str, Any], expected: str
) -> None:
    with pytest.raises(ToolError, match=expected):
        call_tool(context(), name, arguments)


def test_an_unknown_tool_is_refused() -> None:
    with pytest.raises(ToolError, match="inconnu"):
        call_tool(context(), "execute_sql", {"query": "DELETE FROM complaints"})


def test_every_tool_publishes_a_schema_for_the_model() -> None:
    for tool in TOOLS.values():
        schema = tool.schema()
        assert schema["type"] == "object"
        assert schema.get("additionalProperties") is False


def test_only_two_tools_can_write() -> None:
    assert sorted(name for name, tool in TOOLS.items() if tool.writes) == [
        "raise_alert",
        "update_status",
    ]


def test_regulation_answers_keep_their_sources() -> None:
    source = Source("1005.11(c)-1", "12 CFR 1005.11(c)", "shall investigate promptly", "url")
    answer = Answer(ANSWERED, text="Within 10 business days.", sources=(source,))

    result = call_tool(
        context(answer), "search_regulations", {"question": "How long to investigate?"}
    )

    assert result["repondu"] is True
    assert result["sources"][0]["citation"] == "12 CFR 1005.11(c)"


def test_a_regulation_refusal_is_passed_on() -> None:
    result = call_tool(
        context(), "search_regulations", {"question": "Minimum credit score for a mortgage?"}
    )

    assert result == {"repondu": False, "raison": "Nothing."}


@pytest.mark.parametrize(
    "url",
    ["http://example.com/hook", "ftp://127.0.0.1/hook", "file:///etc/passwd", "https:///nohost"],
)
def test_unsafe_webhook_urls_are_refused(url: str) -> None:
    with pytest.raises(ValueError, match="refusée"):
        check_webhook_url(url)


def test_local_http_and_remote_https_are_accepted() -> None:
    assert check_webhook_url("http://127.0.0.1:8765/alerts")
    assert check_webhook_url("https://discord.com/api/webhooks/1/abc")


def test_the_alert_is_sent_as_json() -> None:
    sent: list[urllib.request.Request] = []

    def post(request: urllib.request.Request, timeout: float) -> int:
        sent.append(request)
        return 204

    status = send_alert("http://127.0.0.1:8765/alerts", {"complaint_id": 1}, post=post)

    assert status == 204
    assert json.loads(sent[0].data) == {"complaint_id": 1}  # type: ignore[arg-type]
