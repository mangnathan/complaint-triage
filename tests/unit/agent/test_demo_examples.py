"""Exemples enregistrés de la démo : forme attendue par l'interface, et aucune donnée réelle."""

from __future__ import annotations

import json
import re
from importlib.resources import files
from typing import Any

import pytest

from complaint_triage.agent.tools import TOOLS

FICTITIOUS_FLOOR = 9_000_000_000


@pytest.fixture(scope="module")
def examples() -> dict[str, list[dict[str, Any]]]:
    text = files("complaint_triage.demo").joinpath("examples.json").read_text(encoding="utf-8")
    loaded: dict[str, list[dict[str, Any]]] = json.loads(text)
    return loaded


def test_rag_examples_have_the_fields_shown(examples: dict[str, list[dict[str, Any]]]) -> None:
    assert examples["rag"]
    for example in examples["rag"]:
        assert {"titre", "question", "repondu", "texte", "sources"} <= example.keys()
        assert example["texte"]
        # Une réponse s'appuie sur au moins une source ; un refus n'en montre aucune.
        assert bool(example["sources"]) == example["repondu"]


def test_rag_sources_point_to_the_official_text(
    examples: dict[str, list[dict[str, Any]]],
) -> None:
    for example in examples["rag"]:
        for source in example["sources"]:
            assert source["lien"].startswith("https://www.ecfr.gov/")
            assert source["citation"].startswith("12 CFR ")
            assert source["extrait"]


def test_demo_shows_both_answers_and_refusals(examples: dict[str, list[dict[str, Any]]]) -> None:
    for kind in ("rag", "agent"):
        outcomes = {example["repondu"] for example in examples[kind]}
        assert outcomes == {True, False}


def test_agent_examples_use_known_tools(examples: dict[str, list[dict[str, Any]]]) -> None:
    assert examples["agent"]
    for example in examples["agent"]:
        assert {"titre", "demande", "repondu", "texte", "tours"} <= example.keys()
        # Un refus peut venir avant tout outil ; une réponse passe toujours par un outil.
        assert example["tours"] or not example["repondu"]
        for round_ in example["tours"]:
            assert round_["announcement"]
            for step in round_["steps"]:
                assert step["tool"] in TOOLS


def test_agent_examples_only_touch_fictitious_complaints(
    examples: dict[str, list[dict[str, Any]]],
) -> None:
    """Le dépôt public ne contient aucun dossier réel : tous les numéros sont fictifs."""
    text = json.dumps(examples["agent"])
    numbers = [int(n) for n in re.findall(r"\b\d{7,}\b", text)]
    assert numbers
    assert all(n >= FICTITIOUS_FLOOR for n in numbers)
