# Image de l'application : le paquet complaint_triage, ses scripts et ses jeux d'évaluation.
# Construite et testée par la CI à chaque PR. Aucune donnée ni aucun secret n'y entre : les
# données se montent au lancement, les secrets passent par les variables d'environnement.

# Version exacte : une image « 3.12 » flottante changerait sans prévenir. Debian 13 (trixie),
# la version stable actuelle : bien moins de vulnérabilités connues que bookworm. À relever
# régulièrement pour les correctifs de sécurité du système.
FROM python:3.12.15-slim-trixie

# uv, à la même version que le poste et la CI.
COPY --from=ghcr.io/astral-sh/uv:0.13.1 /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Dépendances d'abord, seules : cette couche reste en cache tant que uv.lock ne change pas.
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --locked --no-default-groups --no-install-project

COPY src ./src
COPY scripts ./scripts
COPY evaluation ./evaluation
RUN uv sync --locked --no-default-groups

# Jamais root à l'exécution.
RUN useradd --create-home --uid 10001 app && chown -R app:app /app
USER app

ENV PATH="/app/.venv/bin:$PATH"

CMD ["python", "scripts/agent/run_agent.py", "--help"]
