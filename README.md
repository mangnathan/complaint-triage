# complaint-triage

[![CI](https://github.com/mangnathan/complaint-triage/actions/workflows/ci.yml/badge.svg)](https://github.com/mangnathan/complaint-triage/actions/workflows/ci.yml)

Priorisation des réclamations clients en banque de détail, construite sur les données publiques du régulateur financier américain (CFPB).

Un service réclamations traite en général ses dossiers dans l'ordre d'arrivée. Environ un sur sept se termine pourtant par une indemnisation du client, et ce sont ceux-là qu'il faudrait traiter en premier. L'outil estime ce risque dès la réception, propose une réponse qui cite ses sources et peut exécuter quelques actions encadrées. S'il manque d'informations, il refuse d'agir et l'explique.

Le projet est pensé pour fonctionner en continu, pas comme une étude ponctuelle. Depuis le 14 août 2026, le CFPB ne publie plus le texte des réclamations. Le modèle de production doit donc se passer du texte, attendre que les issues soient connues avant d'apprendre, et être évalué en permanence sur les décisions réelles des banques.

Statut actuel : v0.1 en cours, étape 7 sur 8. Les données sont collectées et explorées, le cadre d'évaluation est en place, et les modèles avec et sans texte sont mesurés sur la période de validation.

## Où en est le projet

| v0.1, étape | Contenu | État |
|---|---|---|
| 1 | Collecte et contrôle des données du CFPB | terminé |
| 2 | Intégration continue (lint, typage, tests) | terminé |
| 3 | Exploration et préparation des données | terminé |
| 4 | Cadre d'évaluation et règle de référence | terminé |
| 5 | Modèle XGBoost sans texte | terminé, conclusion révisée à l'étape 6 |
| 6 | Modèle de texte et correction de la métrique | terminé |
| 7 | Équité par sous-groupe et calibration | en cours |
| 8 | Décision sur la période de test, rapport v0.1 | à venir |

Résultats provisoires sur la période de validation (juillet à décembre 2025), dans la file de chaque établissement :

| Classement | Capture@10 % |
|---|---|
| Hasard | 10,0 % |
| Règle H0 avec les taux du marché | 17,7 % |
| Règle H0 avec les taux propres à chaque banque | 19,4 % |
| Meilleur XGBoost, sans texte | 19,4 % |

Sur les réclamations qui ont un récit, dans la file de chaque établissement :

| Classement | Capture@10 % | Écart avec la règle propre à la banque |
|---|---|---|
| Règle H0 avec les taux propres à chaque banque | 19,0 % | — |
| Référence textuelle TF-IDF | 21,8 % | +2,8 points [1,8 ; 3,6] |
| Modèle de langage DistilRoBERTa | 22,0 % | +3,0 points [2,0 ; 4,0] |

Sans le texte, aucun modèle ne fait mieux que la règle des taux propres à chaque banque. Le texte apporte un gain réel d'environ 3 points, mais aucun modèle n'atteint la marge de 5 points fixée au cadrage, et le modèle de langage ne fait pas mieux que la référence TF-IDF. La décision finale sera prise une seule fois, sur la période de test.

## Quelques chiffres

Mesures du 17 octobre 2026 sur les cartes de crédit et les comptes courants et d'épargne. Elles sont reproductibles avec les scripts de `scripts/feasibility/`.

| Indicateur | Valeur |
|---|---|
| Réclamations par mois en 2026 | environ 16 000 (2,7 fois plus qu'en janvier 2022) |
| Part aboutissant à une indemnisation financière | 14 % entre 2022 et 2026 |
| Dossiers encore sans issue après 1 mois, puis après 3 mois | 29 %, puis moins de 1 % |
| Réclamations avec texte client, de mars-avril 2025 à août 2026 | de 51 % à 0 % |

## Mesure du succès

L'indicateur principal est la Capture@10 % : chaque semaine, chaque banque traite d'abord 10 % de sa propre file de réclamations, et on mesure la part des réclamations finalement indemnisées qui s'y trouvent. Un tri au hasard donne 10 %.

Le modèle doit faire au moins 5 points de mieux qu'une règle métier simple : les taux d'indemnisation historiques de la banque par produit, motif et sous-motif, rapprochés de ceux du marché quand elle a peu de réclamations dans une catégorie. Cette marge a été fixée avant toute modélisation. Si aucun modèle ne l'atteint, c'est la règle simple qui sera utilisée, et le résultat sera documenté. Le détail figure dans le [rapport de cadrage](docs/pdf/complaint-triage_v0.0_Rapport-de-cadrage.pdf), section 7.

La première version de la métrique classait toutes les banques ensemble. Elle avantageait les modèles capables de deviner la banque, ce qui ne sert à rien à un établissement qui trie sa propre file. Elle a été corrigée pendant la v0.1 pour coller à la définition du client écrite au cadrage, sans changer la marge exigée. L'explication complète figurera dans le rapport v0.1.

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
| v0.1 | Rapport en cours de rédaction ([source](docs/v0.1-donnees-et-scoring/v0.1-rapport-donnees-et-scoring.tex)), PDF publié à la fin de la version | à venir |

## Organisation du dépôt

```
docs/
  pdf/            rapports PDF, un par version
  vX.Y-<étape>/   source LaTeX, figures et données agrégées de chaque rapport
  adr/            notes de décision technique
  latex/          mise en page commune des rapports
notebooks/        lanceur Colab pour l'entraînement sur GPU (sans logique propre)
scripts/          scripts exécutables (faisabilité, exploration, évaluation, expériences, rapports)
src/complaint_triage/
  data/           collecte, contrôle, assemblage et préparation des données du CFPB
  evaluation/     découpage dans le temps, Capture@10 % par file, intervalles de confiance
  models/         règles de référence, XGBoost, référence textuelle TF-IDF, modèle de langage
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
uv run python scripts/analysis/explore_dataset.py       # analyses, tableaux et figures de l'exploration
uv run python scripts/evaluation/evaluate_references.py # classements de référence sur la validation
uv run python scripts/experiments/train_xgboost.py      # variantes XGBoost, tracées dans MLflow
uv run python scripts/evaluation/evaluate_by_bank.py    # réévaluation dans la file de chaque banque
uv run mlflow ui --backend-store-uri sqlite:///mlflow.db # consulter les expériences
```

Le modèle de langage s'entraîne sur GPU, avec Google Colab :

```bash
uv run python scripts/experiments/export_text_for_colab.py  # récits sans la période de test
```

Déposer `data/processed/recits-colab.parquet` dans le dossier `complaint-triage` de Google Drive, puis lancer [le notebook sur Colab](https://colab.research.google.com/github/mangnathan/complaint-triage/blob/main/notebooks/colab_fine_tune_text.ipynb).

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
