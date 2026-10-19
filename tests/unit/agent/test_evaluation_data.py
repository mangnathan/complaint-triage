from __future__ import annotations

import json
from pathlib import Path

import pytest

from complaint_triage.agent.demo import reset_fixtures
from complaint_triage.agent.evaluation_data import (
    EVAL_COMPANY,
    FIRST_ID,
    NARRATIVES,
    TRAPPED_COMPANY,
    evaluation_rows,
)
from complaint_triage.agent.tools import TOOLS

SCENARIOS = Path("evaluation/agent/scenarios-evaluation.json")


def test_only_complaint_306_is_in_the_top_ten_percent_of_its_queue() -> None:
    cards = [r for r in evaluation_rows() if r[4] == EVAL_COMPANY and r[2] == "Credit card"]
    best = max(cards, key=lambda row: float(row[6]))  # type: ignore[arg-type]

    assert len(cards) == 10  # une place prioritaire sur dix
    assert best[0] == FIRST_ID + 5


def test_three_narratives_and_one_institution_name_carry_an_injection() -> None:
    rows = evaluation_rows()

    assert {r[0] for r in rows if r[5]} == set(NARRATIVES)
    assert sum(1 for r in rows if r[4] == TRAPPED_COMPANY) == 2
    assert all(int(r[0]) >= 9_000_000_000 for r in rows)  # type: ignore[call-overload]


def test_resetting_real_complaints_is_refused_before_connecting() -> None:
    real = [(18430782, None, "Credit card", "Fees", "BANK", None, 0.1)]

    with pytest.raises(ValueError, match="fictifs"):
        reset_fixtures("postgresql://nobody@127.0.0.1:1/none", real)


def test_the_scenarios_are_well_formed() -> None:
    scenarios = json.loads(SCENARIOS.read_text(encoding="utf-8"))

    assert 20 <= len(scenarios) <= 25
    assert len({s["id"] for s in scenarios}) == len(scenarios)
    for scenario in scenarios:
        assert set(scenario["outils_attendus"]) <= set(TOOLS)
        statuses = scenario["statut_attendu"]
        assert set(statuses if isinstance(statuses, list) else [statuses]) <= {"repondu", "refuse"}
