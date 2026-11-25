"""Règles de sécurité des workflows GitHub, vérifiées sur le texte des fichiers.

- aucune action n'est référencée par une étiquette, qui peut être déplacée : seulement par SHA ;
- aucun checkout ne garde le jeton dans `.git` : il n'est fourni qu'à l'étape qui pousse ;
- aucun déclencheur `pull_request_target`, qui donne des droits d'écriture à du code de fork ;
- une valeur venue de l'extérieur (`inputs`, `github.event`) n'est jamais collée dans un script
  shell : elle passe par une variable d'environnement.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

WORKFLOWS = sorted((Path(__file__).resolve().parents[2] / ".github" / "workflows").glob("*.yml"))
USES = re.compile(r"^\s*-?\s*uses:\s*(\S+)")
PINNED = re.compile(r"^[\w.-]+/[\w.-]+(/[\w./-]+)?@[0-9a-f]{40}$")
OUTSIDE_VALUE = re.compile(r"\$\{\{[^}]*\b(inputs\.|github\.event\.)")
ENV_ASSIGNMENT = re.compile(r"^\s+[A-Z_][A-Z0-9_]*:\s*\$\{\{")


def test_workflows_are_found() -> None:
    assert "ci.yml" in [path.name for path in WORKFLOWS]


@pytest.mark.parametrize("path", WORKFLOWS, ids=lambda p: p.name)
def test_actions_are_pinned_by_commit_sha(path: Path) -> None:
    for line in path.read_text(encoding="utf-8").splitlines():
        match = USES.match(line)
        if match:
            assert PINNED.match(match.group(1)), f"{path.name} : {match.group(1)}"


@pytest.mark.parametrize("path", WORKFLOWS, ids=lambda p: p.name)
def test_no_checkout_keeps_the_token(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    checkouts = len(re.findall(r"uses:\s*actions/checkout@", text))
    assert text.count("persist-credentials: false") == checkouts


@pytest.mark.parametrize("path", WORKFLOWS, ids=lambda p: p.name)
def test_no_trigger_gives_write_rights_to_fork_code(path: Path) -> None:
    assert "pull_request_target" not in path.read_text(encoding="utf-8")


@pytest.mark.parametrize("path", WORKFLOWS, ids=lambda p: p.name)
def test_outside_values_reach_scripts_only_through_the_environment(path: Path) -> None:
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if OUTSIDE_VALUE.search(line):
            assert ENV_ASSIGNMENT.match(line), f"{path.name}, ligne {number} : {line.strip()}"
