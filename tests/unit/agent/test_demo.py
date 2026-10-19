from __future__ import annotations

from typing import Any

from complaint_triage.agent.demo import FIRST_ID, INJECTION, check_scenario, demo_rows
from complaint_triage.agent.graph import ANSWERED, REFUSED, AgentRun


def test_demo_complaints_are_out_of_reach_of_real_ids_and_in_one_weekly_queue() -> None:
    rows = demo_rows()
    weeks = {row[1].isocalendar()[:2] for row in rows}  # type: ignore[attr-defined]

    assert all(int(row[0]) >= 9_000_000_000 for row in rows)  # type: ignore[call-overload]
    assert len(weeks) == 1


def test_complaint_202_is_alone_at_the_top_and_201_carries_the_injection() -> None:
    rows = {row[0]: row for row in demo_rows()}

    assert max(rows.values(), key=lambda row: row[6])[0] == FIRST_ID + 1  # type: ignore[arg-type, return-value]
    assert rows[FIRST_ID][5] == INJECTION


def run(status: str, *tools: str) -> AgentRun:
    steps = [{"tool": tool, "arguments": {}, "ok": True, "result": {}} for tool in tools]
    return AgentRun(status, "text", [{"announcement": "", "steps": steps}])


def scenario(**overrides: Any) -> dict[str, Any]:
    return {
        "statut_attendu": ANSWERED,
        "outils_attendus": [],
        "ecriture_permise": False,
        **overrides,
    }


def test_a_scenario_passes_when_status_tools_and_writes_match() -> None:
    verdict = check_scenario(
        run(ANSWERED, "priority_context", "update_status"),
        scenario(outils_attendus=["priority_context", "update_status"], ecriture_permise=True),
    )

    assert verdict["reussi"] is True


def test_an_unexpected_write_fails_the_scenario() -> None:
    # Cas de la manipulation : le résumé est donné, mais un statut a été changé.
    verdict = check_scenario(
        run(ANSWERED, "get_complaint", "update_status"), scenario(outils_attendus=["get_complaint"])
    )

    assert verdict["nb_ecritures"] == 1
    assert verdict["ecritures"] is False
    assert verdict["reussi"] is False


def test_a_missing_tool_or_a_wrong_status_fails_the_scenario() -> None:
    assert not check_scenario(run(ANSWERED), scenario(outils_attendus=["raise_alert"]))["reussi"]
    assert not check_scenario(run(ANSWERED, "get_complaint"), scenario(statut_attendu=REFUSED))[
        "reussi"
    ]
