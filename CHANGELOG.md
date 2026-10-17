# Changelog

Les évolutions notables du projet sont notées ici, selon le format [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/). Chaque version correspond à une étape du projet et porte un tag Git (`v0.0`, `v0.1`, etc.).

## [Non publié]

### Ajouté
- Module `complaint_triage.data` : téléchargement idempotent et atomique des sources du CFPB, lecture de l'export complet par morceaux, harmonisation de l'ancienne catégorie « Credit card or prepaid card », jointure des récits de l'archive, contrôles de schéma avec pandera, écriture en Parquet avec un manifeste (tailles et empreintes SHA-256 des sources).
- Commande `python -m complaint_triage.data` pour construire le jeu de données.
- 19 tests unitaires, sans accès réseau.
- Rapport v0.1, section 1 : collecte et premier traitement.
- Préambule LaTeX commun à tous les rapports.

### Corrigé
- Les séries mensuelles du rapport v0.0 comptaient aussi les cartes prépayées de l'ancienne catégorie combinée (6 066 réclamations en 2022-2023, environ 1 % du volume). Les conclusions du cadrage ne changent pas.

## [v0.0] - 2026-10-17

### Ajouté
- Rapport de cadrage en LaTeX et en PDF : contexte, besoins, enjeux, travaux existants, faisabilité, solution, seuils de décision, planning et risques.
- Étude de faisabilité reproductible sur la base du CFPB : séries mensuelles du périmètre bancaire et part des réclamations avec récit dans l'archive officielle.
- Scripts de génération des figures et du PDF.
- Note de décision ADR 0001 sur le cadrage.
- Configuration du projet avec uv, ruff, mypy en mode strict, pytest et pre-commit.
