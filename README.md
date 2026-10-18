# complaint-triage

[![CI](https://github.com/mangnathan/complaint-triage/actions/workflows/ci.yml/badge.svg)](https://github.com/mangnathan/complaint-triage/actions/workflows/ci.yml)

Priorisation des réclamations clients en banque de détail, construite sur les données publiques du régulateur financier américain (CFPB).

Un service réclamations traite en général ses dossiers dans l'ordre d'arrivée. Environ un sur sept se termine pourtant par une indemnisation du client, et ce sont ceux-là qu'il faudrait traiter en premier. L'outil estime ce risque dès la réception, propose une réponse qui cite ses sources et peut exécuter quelques actions encadrées. S'il manque d'informations, il refuse d'agir et l'explique.

Le projet est pensé pour fonctionner en continu, pas comme une étude ponctuelle. Depuis le 14 août 2026, le CFPB ne publie plus le texte des réclamations. Le modèle de production doit donc se passer du texte, attendre que les issues soient connues avant d'apprendre, et être évalué en permanence sur les décisions réelles des banques.

Statut actuel : v0.2 terminée. Le moteur de priorisation est choisi (v0.1), et un assistant répond aux questions de réglementation en citant ses sources, ou refuse (v0.2). La v0.3 (agent) est la prochaine étape.

## Résultat de la v0.2 : réponses avec citations, ou refus

Le chargé de réclamations pose une question (« Combien de temps la banque a-t-elle pour enquêter sur une opération contestée ? »). L'assistant retrouve les passages utiles dans les Regulations E, Z et DD, et Gemini répond en citant un extrait exact pour chaque affirmation. **Le code vérifie chaque citation mot pour mot** : une seule citation invérifiable, et toute la réponse est refusée.

| Critère fixé au cadrage | Seuil | Sur le test |
|---|---|---|
| Réponses qui citent au moins une source vérifiable | 100 % | **100 %** (13 / 13) |
| Refus sur des questions hors du corpus | 95 % | **100 %** (20 / 20, tentatives de détournement comprises) |

- **Aucune réponse ne cite une mauvaise source.** En contrepartie, l'assistant est prudent : il refuse 7 questions de test sur 20 auxquelles il aurait pu répondre. L'analyse de ces refus est dans le [rapport v0.2](docs/pdf/complaint-triage_v0.2_Rapport-RAG.pdf).
- **La recherche a été mesurée seule, avant tout modèle de langage** : la recherche par le sens (embeddings calculés en local) trouve un bon passage dans les 5 premiers pour 85 % des questions de test, contre 45 % pour les mots-clés. La recherche hybride, souvent recommandée, fait moins bien ici (75 %).
- **Gratuit, sous plafond.** Gemini 3.5 Flash-Lite sur l'offre gratuite, dans un projet sans facturation ; cache des réponses et plafond d'appels codé sous la limite gratuite. Toute l'évaluation a tenu en 122 appels.

## Résultat de la v0.1 : le moteur de priorisation

Sur la période de test (janvier à juillet 2026, 99 089 réclamations), chaque banque traitant d'abord 10 % de la file de chaque produit :

| Classement | Capture@10 % | Écart avec la règle propre à la banque |
|---|---|---|
| Tri au hasard | 10,0 % | — |
| **Règle H0 avec les taux propres à chaque banque** | **17,4 %** [17,1 ; 17,7] | — |
| Meilleur XGBoost, sans texte | 17,0 % [16,6 ; 17,3] | −0,5 point [−0,8 ; −0,1] |
| Référence textuelle TF-IDF, sur les 40 412 récits jamais vus | 19,4 % | +2,6 points [1,8 ; 3,4] |

- **Le modèle ne bat pas la règle simple.** Le cadrage exigeait 5 points de plus ; XGBoost fait légèrement moins bien. La règle propre à chaque banque devient le moteur de priorisation. C'est un résultat négatif assumé : il évite de maintenir un modèle qui ne sert pas mieux le client.
- **L'outil est équitable et ses notes sont fiables.** Les rapports de capture entre clients âgés, militaires, cartes et comptes vont de 0,93 à 1,12 (seuils : 0,8 à 1,25), et l'erreur de calibration vaut 0,024 (seuil : 0,05).
- **Le texte apporte un vrai signal** (+0,063 de PR-AUC, critère atteint), mais le CFPB ne le publie plus. Il reste un composant optionnel pour une banque qui dispose de ses propres récits. Un modèle de langage (DistilRoBERTa) ne faisait pas mieux que le TF-IDF sur la validation.

Deux corrections de méthode ont rendu l'évaluation plus exigeante en cours de version. La mesure classait d'abord toutes les banques ensemble, ce qui récompensait les modèles capables de reconnaître la banque. Puis le contrôle d'équité a montré qu'avec une seule file par banque, les clients des comptes courants passaient après ceux des cartes, même quand leur dossier était fondé. Le détail est dans le [rapport v0.1](docs/pdf/complaint-triage_v0.1_Rapport-donnees-et-scoring.pdf) et l'[ADR 0002](docs/adr/0002-moteur-de-priorisation.md).

## Étapes de la v0.1

| v0.1, étape | Contenu | État |
|---|---|---|
| 1 | Collecte et contrôle des données du CFPB | terminé |
| 2 | Intégration continue (lint, typage, tests) | terminé |
| 3 | Exploration et préparation des données | terminé |
| 4 | Cadre d'évaluation et règle de référence | terminé |
| 5 | Modèle XGBoost sans texte | terminé, conclusion révisée à l'étape 6 |
| 6 | Modèle de texte et correction de la métrique | terminé |
| 7 | Équité par sous-groupe et calibration | terminé, files séparées par produit |
| 8 | Décision sur la période de test, rapport v0.1 | terminé, règle propre à chaque banque retenue |

## Quelques chiffres

Mesures du 17 octobre 2026 sur les cartes de crédit et les comptes courants et d'épargne. Elles sont reproductibles avec les scripts de `scripts/feasibility/`.

| Indicateur | Valeur |
|---|---|
| Réclamations par mois en 2026 | environ 16 000 (2,7 fois plus qu'en janvier 2022) |
| Part aboutissant à une indemnisation financière | 14 % entre 2022 et 2026 |
| Dossiers encore sans issue après 1 mois, puis après 3 mois | 29 %, puis moins de 1 % |
| Réclamations avec texte client, de mars-avril 2025 à août 2026 | de 51 % à 0 % |

## Mesure du succès

L'indicateur principal est la Capture@10 % : chaque semaine, chaque banque traite d'abord 10 % de sa propre file de réclamations pour chaque produit, et on mesure la part des réclamations finalement indemnisées qui s'y trouvent. Un tri au hasard donne 10 %.

Le modèle doit faire au moins 5 points de mieux qu'une règle métier simple : les taux d'indemnisation historiques de la banque par produit, motif et sous-motif, rapprochés de ceux du marché quand elle a peu de réclamations dans une catégorie. Cette marge a été fixée avant toute modélisation. Si aucun modèle ne l'atteint, c'est la règle simple qui sera utilisée, et le résultat sera documenté. Le détail figure dans le [rapport de cadrage](docs/pdf/complaint-triage_v0.0_Rapport-de-cadrage.pdf), section 7.

La première version de la métrique classait toutes les banques ensemble. Elle avantageait les modèles capables de deviner la banque, ce qui ne sert à rien à un établissement qui trie sa propre file. Elle a été corrigée pendant la v0.1 pour coller à la définition du client écrite au cadrage, sans changer la marge exigée. La file a ensuite été séparée par produit à la suite du contrôle d'équité. L'explication complète est dans le rapport v0.1, sections 6 et 8.

Avant toute mise en service, deux contrôles fixés au cadrage doivent être passés : entre un sous-groupe de clients et les autres, le rapport des Capture@10 % doit rester entre 0,8 et 1,25, et l'erreur de calibration (ECE) doit rester sous 0,05.

## Feuille de route

| Version | Contenu | Statut |
|---|---|---|
| v0.0 Cadrage | Contexte, besoins, étude de faisabilité, seuils de décision | terminé |
| v0.1 Données et scoring | Collecte automatisée, contrôles, exploration, règle de référence, XGBoost, modèle de langage, analyse par sous-groupe | terminé |
| v0.2 RAG | Réponses avec citations, ou refus | terminé |
| v0.3 Agent | Planification, outils SQL paramétrés et webhook, refus argumentés | à venir |
| v0.4 Qualité | Tests par outil, 20 à 25 scénarios d'évaluation en CI | à venir |
| v0.5 Industrialisation | Docker, CI/CD avec GitHub Actions | à venir |
| v1.0 Production | Cloud Run, collecte quotidienne, mode shadow, tableau de bord | à venir |

## Documentation

Chaque version est livrée avec un rapport en PDF (source LaTeX dans le dépôt) et une note de décision technique (ADR).

| Version | Rapport | Décisions |
|---|---|---|
| v0.0 | [Rapport de cadrage](docs/pdf/complaint-triage_v0.0_Rapport-de-cadrage.pdf) ([source](docs/v0.0-cadrage/v0.0-rapport-de-cadrage.tex)) | [ADR 0001](docs/adr/0001-cadrage.md) |
| v0.1 | [Rapport données et scoring](docs/pdf/complaint-triage_v0.1_Rapport-donnees-et-scoring.pdf) ([source](docs/v0.1-donnees-et-scoring/v0.1-rapport-donnees-et-scoring.tex)) | [ADR 0002](docs/adr/0002-moteur-de-priorisation.md) |
| v0.2 | [Rapport RAG](docs/pdf/complaint-triage_v0.2_Rapport-RAG.pdf) ([source](docs/v0.2-rag/v0.2-rapport-rag.tex)) | [ADR 0003](docs/adr/0003-rag-avec-citations-verifiees.md) |

## Organisation du dépôt

```
docs/
  pdf/            rapports PDF, un par version
  vX.Y-<étape>/   source LaTeX, figures et données agrégées de chaque rapport
  adr/            notes de décision technique
  latex/          mise en page commune des rapports
evaluation/       jeux de questions écrits à la main pour évaluer le RAG
notebooks/        lanceur Colab pour l'entraînement sur GPU (sans logique propre)
scripts/          scripts exécutables (faisabilité, exploration, évaluation, expériences, rapports)
src/complaint_triage/
  data/           collecte, contrôle, assemblage et préparation des données du CFPB
  evaluation/     découpage dans le temps, files, Capture@10 %, équité, calibration, intervalles
  models/         règles de référence, XGBoost, référence textuelle TF-IDF, modèle de langage
  rag/            corpus réglementaire de l'eCFR, recherche des passages, mesure de la recherche
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
uv run python scripts/evaluation/evaluate_fairness_calibration.py # équité et calibration
uv run python scripts/evaluation/decide_on_test.py --rehearsal data/repetition  # répétition de la décision sur la validation
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

Le RAG (v0.2) demande une clé Gemini gratuite, créée sur [Google AI Studio](https://aistudio.google.com) dans un projet sans facturation, à placer dans `.env` (voir `.env.example`). Les tests n'en ont pas besoin.

```bash
uv run python -m complaint_triage.rag                       # corpus réglementaire depuis l'eCFR
uv run python scripts/rag/evaluate_retrieval.py             # mesure de la recherche, sans API
uv run python scripts/rag/ask.py "How long does a bank have to investigate a disputed debit card transaction?"
uv run python scripts/rag/evaluate_answers.py --part developpement -k 10   # estimation des appels
uv run python scripts/rag/evaluate_answers.py --part developpement -k 10 --execute
```

La décision sur la période de test (`scripts/evaluation/decide_on_test.py` sans option) a été prise une seule fois ; le script refuse de la rejouer tant que ses résultats sont présents dans `docs/v0.1-donnees-et-scoring/data/`.

## Données

- [Consumer Complaint Database](https://www.consumerfinance.gov/data-research/consumer-complaints/) du CFPB : API publique, données structurées mises à jour chaque jour.
- [Narratives Archive](https://www.consumerfinance.gov/foia-requests/foia-electronic-reading-room/cfpb-consumer-complaint-database-narratives-archive/) du CFPB : récits publiés jusqu'au 14 août 2026.
- [eCFR](https://www.ecfr.gov) : texte officiel des Regulations E, Z et DD (titre 12 du code des règlements fédéraux), version du 15 octobre 2026.

Les données brutes ne sont pas versionnées. Le dépôt ne contient que des agrégats, et aucune autre donnée d'entreprise que ces publications officielles.

## Auteur

Nathan Mang, ingénieur Data Science et IA (ESIEE Paris, 2026).
