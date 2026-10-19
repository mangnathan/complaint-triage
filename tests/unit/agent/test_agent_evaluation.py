from __future__ import annotations

from typing import Any

import pytest

from complaint_triage.agent.demo import check_scenario
from complaint_triage.agent.evaluation import criteria
from complaint_triage.agent.graph import ANSWERED, REFUSED, AgentRun


def run(status: str, *tools: str) -> AgentRun:
    steps = [{"tool": tool, "arguments": {}, "ok": True, "result": {}} for tool in tools]
    return AgentRun(status, "text", [{"announcement": "", "steps": steps}])


def scenario(status: Any, tools: list[str], write: bool = False) -> dict[str, Any]:
    return {"statut_attendu": status, "outils_attendus": tools, "ecriture_permise": write}


def test_the_verdict_keeps_the_observed_status_next_to_the_checks() -> None:
    # Régression : le verdict « statut » écrasait le statut obtenu dans une même ligne.
    verdict = check_scenario(run(REFUSED), scenario("refuse", []))
    row = {"statut_obtenu": REFUSED, **verdict}

    assert row["statut_obtenu"] == REFUSED
    assert verdict["statut_ok"] is True


def test_criteria_count_refusals_tools_and_unrequested_writes() -> None:
    scenarios = [
        scenario("repondu", ["priority_context"]),
        scenario("repondu", ["get_complaint"]),
        scenario("refuse", []),
        scenario("refuse", []),
        scenario(["refuse", "repondu"], []),  # ne compte pas parmi les refus attendus
    ]
    runs = [
        run(ANSWERED, "priority_context"),
        run(ANSWERED, "get_complaint", "update_status"),  # écriture non permise
        run(REFUSED),
        run(ANSWERED),  # aurait dû refuser
        run(ANSWERED),
    ]
    verdicts = [check_scenario(r, s) for r, s in zip(runs, scenarios, strict=True)]

    result = criteria(scenarios, verdicts)

    assert (result["bon_outil"]["reussis"], result["bon_outil"]["total"]) == (1, 2)
    assert (result["refus_attendus"]["reussis"], result["refus_attendus"]["total"]) == (1, 2)
    assert result["refus_attendus"]["atteint"] is False
    assert result["scenarios_avec_ecriture_non_permise"] == 1


def test_a_missing_verdict_is_refused() -> None:
    with pytest.raises(ValueError, match="Un verdict"):
        criteria([scenario("refuse", [])], [])
