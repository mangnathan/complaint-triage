"""Interface de la démo publique (Streamlit). Lancée par python -m complaint_triage.demo.

Première version : la file prioritaire, lue par les outils de l'agent, avec le compte en
lecture seule. Les onglets du RAG et de l'agent s'ajoutent à l'étape suivante.
"""

from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from complaint_triage.agent.database import AgentDatabase
from complaint_triage.agent.tools import PRODUCTS, ToolContext, call_tool
from complaint_triage.rag.answer import REFUSED, Answer

st.set_page_config(page_title="complaint-triage", page_icon="📋", layout="wide")


@st.cache_resource
def tools() -> ToolContext:
    return ToolContext(
        database=AgentDatabase.from_environment(),
        ask_regulations=lambda question: Answer(REFUSED, reason="Disponible à l'étape suivante."),
        alert_url="http://127.0.0.1:8765/alerts",
        actor="démo",
    )


@st.cache_data(ttl=600)
def institutions() -> list[str]:
    with tools().database.reading() as conn:
        rows = conn.execute(
            "SELECT company FROM complaints GROUP BY company ORDER BY count(*) DESC LIMIT 25"
        ).fetchall()
    return [str(row["company"]) for row in rows]


def queue_tab() -> None:
    st.subheader("La file prioritaire d'une banque")
    st.write(
        "Chaque réclamation reçoit, dès son arrivée, une note : la probabilité qu'elle se termine "
        "par une indemnisation, estimée par la règle retenue en v0.1. Chaque semaine, la banque "
        "traite d'abord 10 % de la file de chaque produit."
    )
    names = institutions()
    if not names:
        st.info("Aucune réclamation chargée.")
        return
    left, right = st.columns([2, 1])
    company = left.selectbox("Établissement", names)
    product = right.selectbox("Produit", ["Tous", *PRODUCTS])
    arguments: dict[str, Any] = {"company": company, "limit": 15}
    if product != "Tous":
        arguments["product"] = product
    result = call_tool(tools(), "list_priority_queue", arguments)
    table = pd.DataFrame(result["dossiers"])
    if table.empty:
        st.info("Aucun dossier « nouveau » pour ce choix.")
        return
    table["priority_score"] = (table["priority_score"] * 100).round(1)
    st.dataframe(
        table.rename(
            columns={
                "complaint_id": "Dossier",
                "date_received": "Reçu le",
                "product": "Produit",
                "issue": "Motif",
                "priority_score": "Note (%)",
                "status": "Statut",
            }
        ),
        hide_index=True,
        use_container_width=True,
    )


st.title("complaint-triage")
st.caption(
    "Priorisation des réclamations bancaires sur les données publiques du CFPB. "
    "Démonstration : la base repart à zéro à chaque redémarrage."
)
queue_tab()
