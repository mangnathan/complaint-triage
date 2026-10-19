"""Scénarios de sûreté : un modèle hostile ne doit jamais faire exécuter une action interdite.

Le faux modèle ne joue pas les bonnes réponses : il obéit à l'attaquant (écrire sur un dossier
cité dans un récit, appeler un outil inexistant, reculer un dossier...). Chaque scénario vérifie
que le code bloque l'action, quoi que propose le modèle. Deux scénarios témoins vérifient qu'un
usage légitime passe encore : un agent qui refuserait tout ne passerait pas cette suite.

Lancés en CI à chaque PR, dans une étape à part : une régression de sûreté bloque la fusion.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from complaint_triage.agent.graph import Agent

SCENARIOS = json.loads(
    (Path(__file__).parents[2] / "evaluation" / "agent" / "scenarios-surete.json").read_text(
        encoding="utf-8"
    )
)


class HostileModel:
    """Rejoue, dans l'ordre, les décisions qu'un modèle manipulé proposerait."""

    name = "modele-hostile"

    def __init__(self, replies: list[Any]) -> None:
        self.replies = [self._encode(reply) for reply in replies]

    @staticmethod
    def _encode(reply: Any) -> str:
        if isinstance(reply, str):
            return reply
        steps = [
            {"tool": s["tool"], "arguments_json": json.dumps(s["arguments"]), "purpose": "attack"}
            for s in reply.get("steps", [])
        ]
        return json.dumps({"announcement": "", **reply, "steps": steps})

    def generate(self, system: str, prompt: str, schema: dict[str, Any]) -> str:
        if not self.replies:
            raise AssertionError("le graphe a demandé plus de décisions que prévu")
        return self.replies.pop(0)


class RecordingTools:
    def __init__(self, results: dict[str, Any]) -> None:
        self.results = results
        self.executed: list[str] = []

    def __call__(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        self.executed.append(name)
        return dict(self.results.get(name, {"ok": True}))


@pytest.mark.parametrize("scenario", SCENARIOS, ids=[s["id"] for s in SCENARIOS])
def test_the_code_holds_whatever_the_model_proposes(scenario: dict[str, Any]) -> None:
    tools = RecordingTools(scenario.get("resultats_outils", {}))

    run = Agent(HostileModel(scenario["reponses_modele"]), tools).run(scenario["demande"])

    assert tools.executed == scenario["outils_executes"], scenario["menace"]
    assert run.status == scenario["statut_attendu"], scenario["menace"]


def test_the_suite_contains_both_attacks_and_legitimate_controls() -> None:
    statuses = [s["statut_attendu"] for s in SCENARIOS]

    assert statuses.count("refuse") >= 10
    assert statuses.count("repondu") >= 2
