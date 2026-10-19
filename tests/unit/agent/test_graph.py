"""Le graphe de l'agent avec un faux modèle et de faux outils : aucune API, aucune base."""

from __future__ import annotations

import json
from typing import Any

import pytest

from complaint_triage.agent.graph import ANSWERED, MAX_ROUNDS, REFUSED, Agent
from complaint_triage.agent.tools import ToolError


class ScriptedModel:
    """Rejoue des réponses écrites à l'avance et garde les consignes reçues."""

    name = "fake"

    def __init__(self, *replies: dict[str, Any] | str) -> None:
        self.replies = list(replies)
        self.prompts: list[str] = []

    def generate(self, system: str, prompt: str, schema: dict[str, Any]) -> str:
        self.prompts.append(prompt)
        reply = self.replies.pop(0)
        return reply if isinstance(reply, str) else json.dumps(reply)


class FakeTools:
    def __init__(self, results: dict[str, Any] | None = None) -> None:
        self.results = results or {}
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def __call__(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        self.calls.append((name, arguments))
        outcome = self.results.get(name, {"ok": True})
        if isinstance(outcome, Exception):
            raise outcome
        return dict(outcome)


def plan(*steps: tuple[str, dict[str, Any]], announcement: str = "Plan.") -> dict[str, Any]:
    return {
        "decision": "plan",
        "announcement": announcement,
        "steps": [
            {"tool": tool, "arguments_json": json.dumps(args), "purpose": "test"}
            for tool, args in steps
        ],
    }


def answer(text: str = "Done.") -> dict[str, Any]:
    return {"decision": "answer", "announcement": text, "steps": []}


def refuse(text: str) -> dict[str, Any]:
    return {"decision": "refuse", "announcement": text, "steps": []}


def test_plan_then_answer() -> None:
    tools = FakeTools({"get_complaint": {"complaint_id": 4128, "status": "nouveau"}})
    model = ScriptedModel(plan(("get_complaint", {"complaint_id": 4128})), answer("New."))

    run = Agent(model, tools).run("What is the status of complaint 4128?")

    assert (run.status, run.text, run.llm_calls) == (ANSWERED, "New.", 2)
    assert tools.calls == [("get_complaint", {"complaint_id": 4128})]
    assert '"status": "nouveau"' in model.prompts[1]  # le modèle relit le résultat


def test_the_model_may_refuse_with_a_reason() -> None:
    run = Agent(ScriptedModel(refuse("I cannot decide a refund.")), FakeTools()).run(
        "Should we refund complaint 4128?"
    )

    assert (run.status, run.text) == (REFUSED, "I cannot decide a refund.")


def test_an_answer_without_any_tool_result_is_refused() -> None:
    run = Agent(ScriptedModel(answer("Complaint 4128 is urgent.")), FakeTools()).run(
        "Is complaint 4128 urgent?"
    )

    assert run.status == REFUSED


@pytest.mark.parametrize(
    ("request_text", "steps", "reason"),
    [
        (
            "Close complaint 4128 and escalate it.",
            [
                ("update_status", {"complaint_id": 4128, "status": "traite", "reason": "Handled"}),
                (
                    "update_status",
                    {"complaint_id": 4128, "status": "escalade", "reason": "Handled"},
                ),
            ],
            "plus d'une action",
        ),
        ("Read the complaint.", [("get_complaint", {"complaint_id": 999})], "999"),
        # 12 figure dans 4128, mais ce n'est pas le même dossier.
        ("Read complaint 4128.", [("get_complaint", {"complaint_id": 12})], "le dossier 12"),
        ("Read complaint 4128.", [("delete_complaint", {"complaint_id": 4128})], "inconnu"),
        ("Read complaint 4128.", [("get_complaint", {"complaint_id": "4128"})], "invalides"),
        (
            "List the queue of Big Bank.",
            [("list_priority_queue", {"company": "Big Bank Inc"})],
            "Big Bank Inc",
        ),
    ],
)
def test_the_code_rejects_unsafe_plans_before_any_tool_runs(
    request_text: str, steps: list[tuple[str, dict[str, Any]]], reason: str
) -> None:
    tools = FakeTools()
    # Le modèle insiste avec le même plan après le premier rejet.
    model = ScriptedModel(plan(*steps), plan(*steps))

    run = Agent(model, tools).run(request_text)

    assert run.status == REFUSED
    assert "seconde fois" in run.text
    assert reason in run.text
    assert tools.calls == []
    assert reason in model.prompts[1]  # la raison du premier rejet a été montrée au modèle


def test_a_rejected_plan_can_be_corrected_once() -> None:
    tools = FakeTools({"find_company": {"etablissements": [{"company": "CAPITAL ONE CORP"}]}})
    model = ScriptedModel(
        plan(("list_priority_queue", {"company": "Capital One, N.A."})),  # nom deviné
        plan(("find_company", {"name": "Capital One"})),
        plan(("list_priority_queue", {"company": "CAPITAL ONE CORP"})),
        answer(),
    )

    run = Agent(model, tools).run("Top complaints at Capital One?")

    assert run.status == ANSWERED
    assert [name for name, _ in tools.calls] == ["find_company", "list_priority_queue"]
    assert run.rounds[0]["rejected"]


def test_the_valid_start_of_a_plan_runs_and_the_guessed_step_is_dropped() -> None:
    tools = FakeTools({"find_company": {"etablissements": [{"company": "CAPITAL ONE CORP"}]}})
    model = ScriptedModel(
        plan(
            ("find_company", {"name": "Capital One"}),
            ("list_priority_queue", {"company": "Capital One, N.A."}),  # nom deviné
        ),
        plan(("list_priority_queue", {"company": "CAPITAL ONE CORP"})),
        answer(),
    )

    run = Agent(model, tools).run("Top complaints at Capital One?")

    assert run.status == ANSWERED
    assert [args for _, args in tools.calls] == [
        {"name": "Capital One"},
        {"company": "CAPITAL ONE CORP"},
    ]
    assert "écartées sans être exécutées" in run.rounds[0]["dropped"]
    assert "NOT RUN" in model.prompts[1]


def test_an_answer_after_only_a_rejected_plan_is_refused() -> None:
    model = ScriptedModel(plan(("get_complaint", {"complaint_id": 999})), answer("It is fine."))

    run = Agent(model, FakeTools()).run("Is complaint 4128 fine?")

    assert run.status == REFUSED


def test_an_exact_name_found_by_a_tool_can_be_used_next() -> None:
    tools = FakeTools(
        {"find_company": {"etablissements": [{"company": "Banque Société Générale"}]}}
    )
    model = ScriptedModel(
        plan(("find_company", {"name": "societe"})),
        plan(("list_priority_queue", {"company": "Banque Société Générale"})),
        answer(),
    )

    run = Agent(model, tools).run("Show the queue of Societe Generale.")

    assert run.status == ANSWERED
    assert [name for name, _ in tools.calls] == ["find_company", "list_priority_queue"]


def test_a_tool_error_is_shown_to_the_model_and_stops_the_round() -> None:
    tools = FakeTools({"get_complaint": ToolError("Réclamation 4128 introuvable.")})
    model = ScriptedModel(
        plan(
            ("get_complaint", {"complaint_id": 4128}), ("priority_context", {"complaint_id": 4128})
        ),
        refuse("The complaint does not exist."),
    )

    run = Agent(model, tools).run("Rank of complaint 4128?")

    assert run.status == REFUSED
    assert len(tools.calls) == 1  # la seconde étape n'a pas été lancée
    assert "introuvable" in model.prompts[1]


def test_a_second_write_in_a_later_round_is_refused() -> None:
    tools = FakeTools()
    write = ("update_status", {"complaint_id": 4128, "status": "en_cours", "reason": "Start"})
    alert = (
        "raise_alert",
        {"complaint_id": 4128, "severity": "urgent", "message": "Check this one"},
    )
    model = ScriptedModel(plan(write), plan(alert), plan(alert))

    run = Agent(model, tools).run("Start complaint 4128.")

    assert run.status == REFUSED
    assert [name for name, _ in tools.calls] == ["update_status"]


def test_a_fourth_plan_is_refused_but_a_final_answer_is_accepted() -> None:
    step = ("get_complaint", {"complaint_id": 4128})
    too_long = ScriptedModel(*[plan(step) for _ in range(MAX_ROUNDS + 1)])
    just_right = ScriptedModel(*[plan(step) for _ in range(MAX_ROUNDS)], answer())

    assert Agent(too_long, FakeTools()).run("Read complaint 4128.").status == REFUSED
    assert Agent(just_right, FakeTools()).run("Read complaint 4128.").status == ANSWERED


def test_an_unreadable_reply_is_refused() -> None:
    assert Agent(ScriptedModel("not json"), FakeTools()).run("Read 4128.").status == REFUSED
