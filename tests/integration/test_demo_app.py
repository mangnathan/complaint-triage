"""La page de démo s'affiche sans erreur sur la vraie base, onglet par onglet.

Le test de l'image en CI vérifie seulement que Streamlit démarre : le script de la page ne
s'exécute qu'à la visite. Ici, il s'exécute en entier, sans clé Gemini, donc sans aucun appel.
"""

from __future__ import annotations

import os
from importlib.resources import files
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from complaint_triage.agent.demo import demo_rows, reset_fixtures
from complaint_triage.agent.evaluation_data import evaluation_rows
from complaint_triage.db.roles import OWNER
from complaint_triage.db.settings import ENV_KEYS, url_for
from complaint_triage.rag.llm import load_dotenv

load_dotenv(Path(".env"))
pytestmark = pytest.mark.skipif(
    os.environ.get("REQUIRE_DATABASE") != "1"
    and not all(os.environ.get(key) for key in ENV_KEYS.values()),
    reason="base PostgreSQL non configurée",
)


@pytest.fixture
def app(monkeypatch: pytest.MonkeyPatch) -> AppTest:
    # Sans clé, le mode en direct est coupé : le test ne peut rien envoyer à Google.
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    reset_fixtures(url_for(OWNER), demo_rows() + evaluation_rows())
    page = AppTest.from_file(str(files("complaint_triage.demo").joinpath("app.py")))
    page.run(timeout=60)
    return page


def test_page_renders_every_tab(app: AppTest) -> None:
    assert not app.exception
    assert len(app.tabs) == 4
    assert app.dataframe  # la file prioritaire de l'établissement choisi


def test_live_mode_is_off_without_a_key(app: AppTest) -> None:
    buttons = {button.label: button for button in app.button}
    assert buttons["Interroger le RAG"].disabled
    assert buttons["Lancer l'agent"].disabled


def test_recorded_examples_can_be_browsed(app: AppTest) -> None:
    examples = app.selectbox[2]  # établissement, produit, puis exemples du RAG
    for option in examples.options:
        examples.set_value(option).run(timeout=60)
        assert not app.exception
    agent_examples = app.selectbox[3]
    for option in agent_examples.options:
        agent_examples.set_value(option).run(timeout=60)
        assert not app.exception
