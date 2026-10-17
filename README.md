# complaint-triage

Priorisation des réclamations clients en banque de détail, construite sur les données publiques du régulateur financier américain (CFPB).

Un service réclamations traite en général ses dossiers dans l'ordre d'arrivée. Environ un sur sept se termine pourtant par une indemnisation du client, et ce sont ceux-là qu'il faudrait traiter en premier. L'outil estime ce risque dès la réception, propose une réponse qui cite ses sources et peut exécuter quelques actions encadrées. S'il manque d'informations, il refuse d'agir et l'explique.

Le projet est pensé pour fonctionner en continu, pas comme une étude ponctuelle. Depuis le 14 août 2026, le CFPB ne publie plus le texte des réclamations. Le modèle de production doit donc se passer du texte, attendre que les issues soient connues avant d'apprendre, et être évalué en permanence sur les décisions réelles des banques.

Statut actuel : v0.0, cadrage terminé. Aucun modèle n'a encore été entraîné, mais les critères de succès sont déjà fixés.

## Quelques chiffres

Mesures du 17 octobre 2026 sur les cartes de crédit et les comptes courants et d'épargne. Elles sont reproductibles avec les scripts de `scripts/feasibility/`.

| Indicateur | Valeur |
|---|---|
| Réclamations par mois en 2026 | environ 16 000 (2,7 fois plus qu'en janvier 2022) |
| Part aboutissant à une indemnisation financière | 14 % entre 2022 et 2026 |
| Dossiers encore sans issue après 1 mois, puis après 3 mois | 29 %, puis moins de 1 % |
| Réclamations avec texte client, de mars-avril 2025 à août 2026 | de 51 % à 0 % |

## Mesure du succès

L'indicateur principal est la Capture@10 % : la part des réclamations indemnisées que l'on retrouve dans les 10 % de la file traités en priorité. Un tri au hasard donne 10 %. Le modèle doit faire mieux qu'une règle métier simple (le taux historique par produit et par motif), avec une marge décidée avant toute modélisation. S'il n'y arrive pas, c'est la règle simple qui sera utilisée, et le résultat sera documenté. Le détail figure dans le [rapport de cadrage](docs/pdf/complaint-triage_v0.0_Rapport-de-cadrage.pdf), section 7.

## Feuille de route

| Version | Contenu | Statut |
|---|---|---|
| v0.0 Cadrage | Contexte, besoins, étude de faisabilité, seuils de décision | terminé |
| v0.1 Données et scoring | Collecte automatisée, contrôles, exploration, règle de référence, XGBoost, modèle de langage, analyse par sous-groupe | en cours |
| v0.2 RAG | Réponses avec citations, ou refus | à venir |
| v0.3 Agent | Planification, outils SQL paramétrés et webhook, refus argumentés | à venir |
| v0.4 Qualité | Tests par outil, 20 à 25 scénarios d'évaluation en CI | à venir |
| v0.5 Industrialisation | Docker, CI/CD avec GitHub Actions | à venir |
| v1.0 Production | Cloud Run, collecte quotidienne, mode shadow, tableau de bord | à venir |

## Documentation

Chaque version est livrée avec un rapport en PDF (source LaTeX dans le dépôt) et une note de décision technique (ADR).

| Version | Rapport | Décisions |
|---|---|---|
| v0.0 | [Rapport de cadrage](docs/pdf/complaint-triage_v0.0_Rapport-de-cadrage.pdf) ([source](docs/v0.0-cadrage/v0.0-rapport-de-cadrage.tex)) | [ADR 0001](docs/adr/0001-cadrage.md) |

## Organisation du dépôt

```
docs/
  pdf/            rapports PDF, un par version
  vX.Y-<étape>/   source LaTeX, figures et données agrégées de chaque rapport
  adr/            notes de décision technique
  latex/          mise en page commune des rapports
scripts/          scripts exécutables (faisabilité, génération des rapports)
src/complaint_triage/
  data/           collecte, contrôle et assemblage des données du CFPB
tests/            tests automatiques (pytest)
```

## Reproduire

Il faut Python 3.12, [uv](https://docs.astral.sh/uv/) et [Tectonic](https://tectonic-typesetting.github.io) pour compiler les rapports. Aucune clé d'API n'est nécessaire, car les données du CFPB sont publiques.

Construire le jeu de données (environ 1,4 Go téléchargés la première fois, puis réutilisés) :

```bash
uv sync
uv run python -m complaint_triage.data                  # écrit data/interim/complaints.parquet
uv run python -m complaint_triage.data --refresh-export # même chose avec l'export du jour
uv run pytest                                           # tests, sans réseau
```

Reproduire l'étude de faisabilité et les rapports :

```bash
uv run python scripts/feasibility/collect_cfpb_feasibility_stats.py
uv run python scripts/feasibility/plot_feasibility_figures.py
uv run python scripts/docs/build_report_pdf.py \
    docs/v0.0-cadrage/v0.0-rapport-de-cadrage.tex \
    docs/pdf/complaint-triage_v0.0_Rapport-de-cadrage.pdf
```

## Données

- [Consumer Complaint Database](https://www.consumerfinance.gov/data-research/consumer-complaints/) du CFPB : API publique, données structurées mises à jour chaque jour.
- [Narratives Archive](https://www.consumerfinance.gov/foia-requests/foia-electronic-reading-room/cfpb-consumer-complaint-database-narratives-archive/) du CFPB : récits publiés jusqu'au 14 août 2026.

Les données brutes ne sont pas versionnées. Le dépôt ne contient que des agrégats, et aucune autre donnée d'entreprise que ces publications officielles.

## Auteur

Nathan Mang, ingénieur Data Science et IA (ESIEE Paris, 2026).
