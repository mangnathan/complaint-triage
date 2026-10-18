# Changelog

Les évolutions notables du projet sont notées ici, selon le format [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/). Chaque version correspond à une étape du projet et porte un tag Git (`v0.0`, `v0.1`, etc.).

## [Non publié]

### Ajouté
- Module `complaint_triage.data` : téléchargement idempotent et atomique des sources du CFPB, lecture de l'export complet par morceaux, harmonisation de l'ancienne catégorie « Credit card or prepaid card », jointure des récits de l'archive, contrôles de schéma avec pandera, écriture en Parquet avec un manifeste (tailles et empreintes SHA-256 des sources).
- Commande `python -m complaint_triage.data` pour construire le jeu de données.
- 19 tests unitaires, sans accès réseau.
- Rapport v0.1, section 1 : collecte et premier traitement.
- Préambule LaTeX commun à tous les rapports.
- Préparation des données pour la modélisation (`complaint_triage.data.prepare`) : retrait des six gestionnaires de fichiers de consommateurs (62 321 réclamations, 0,1 % d'indemnisation), règle des 90 jours confirmée par la courbe de maturité, cible `is_monetary_relief`. 523 552 réclamations préparées.
- Liste fermée des colonnes connues à la réception, avec un test qui échoue si une colonne n'a pas de rôle défini.
- Script d'exploration reproductible (`scripts/analysis/explore_dataset.py`) et rapport v0.1, section 3 : maturité des issues, établissements sans indemnisation, pic de janvier 2025 (panne chez Capital One, campagne sur les frais de découvert de Navy Federal), récits recopiés (6,3 %, indemnisés à 0,25 %), taux d'indemnisation par motif.
- Cadre d'évaluation (`complaint_triage.evaluation`) : découpage dans le temps (entraînement jusqu'en juin 2025, validation au second semestre 2025, test en 2026, fermé jusqu'à la décision finale), Capture@10 % semaine par semaine avec traitement exact des ex æquo, PR-AUC, intervalle de confiance par bootstrap sur des semaines entières, y compris pour l'écart entre deux classements.
- Règle de référence H0 (`complaint_triage.models.baseline`) : taux d'indemnisation par produit, motif et sous-motif, lissé vers la catégorie parente. Capture@10 % de 20,3 % sur la validation [19,4 ; 21,1], contre 10 % pour le hasard.
- Rapport v0.1, section 4.
- Variables de volume récent (`complaint_triage.models.features`) : nombre de réclamations reçues avant le jour même pour le même établissement et le même motif, calculé uniquement sur le passé.
- Modèle XGBoost (`complaint_triage.models.gradient_boosting`) sur les variables connues à la réception, catégories natives, arrêt sur trois mois mis de côté dans l'entraînement, contributions SHAP.
- Script d'expériences tracées dans MLflow (`scripts/experiments/train_xgboost.py`) : 4 variantes et 8 réglages fixés à l'avance. Meilleur modèle éligible sur la validation : 23,4 % de Capture@10 %, soit +3,1 points sur H0 [2,5 ; 3,8], sous la barre de +5 points du cadrage. L'établissement ferait gagner 7 points de plus mais reste hors du cadre d'une banque unique.
- Rapport v0.1, section 5.

- Comparaison des modèles de texte dans la file de chaque banque (`scripts/experiments/evaluate_text_models.py`), sur les récits de validation jamais vus à l'entraînement : TF-IDF +2,8 points sur H0 propre à la banque [1,8 ; 3,6], DistilRoBERTa fine-tuné sur Colab +3,0 points [2,0 ; 4,0]. Le texte apporte un gain réel, sous la marge de 5 points ; le modèle de langage ne fait pas mieux que le TF-IDF.
- Reprise automatique du fine-tuning au dernier point de sauvegarde, stocké dans Google Drive.
- Rapport v0.1, sections 6 (correction de la métrique) et 7 (texte).
- Contrôles d'équité et de calibration (`complaint_triage.evaluation.fairness` et `.calibration`) : rapport des Capture@10 % entre un sous-groupe et les autres clients, avec intervalle par bootstrap sur les semaines, et erreur de calibration (ECE) sur 10 classes. Script `scripts/evaluation/evaluate_fairness_calibration.py`.
- Rapport v0.1, section 8 (équité et calibration).

### Corrigé
- La Capture@10 % classait toutes les banques ensemble et avantageait les modèles capables de deviner la banque, ce qui ne sert à rien à un établissement qui trie sa propre file. Elle est désormais calculée dans la file de chaque établissement, semaine par semaine, et la référence devient H0 propre à la banque (ses taux historiques par motif, rapprochés de ceux du marché). La marge exigée ne change pas. Défaut repéré grâce aux mots les plus importants de la référence textuelle, qui étaient des noms de banques.
- Conséquence sur l'étape 5 : réévalué dans la file de chaque banque, aucun modèle XGBoost ne fait mieux que H0 propre à la banque (19,4 % de Capture@10 % sur la validation). Le gain de 3 points mesuré d'abord venait des compteurs de volume par établissement, qui trahissaient la banque.

### Modifié
- Chaque banque traite désormais en priorité 10 % de la file de chaque produit (`complaint_triage.evaluation.queues`). Avec une seule file par banque, les réclamations indemnisées sur un compte courant n'étaient traitées en priorité que dans 8 à 11 % des cas, autant ou moins qu'au hasard, et le rapport entre produits sortait des seuils du cadrage (2,4 pour la règle H0, 3,7 pour XGBoost). Avec une file par produit, tous les rapports rentrent dans les seuils ; la Capture@10 % sur la validation passe de 19,4 % à 18,4 % pour H0 propre à la banque et à 19,0 % pour XGBoost.
- La contrainte sur pyarrow passe de `>=26` à `>=21` : la borne posée par défaut empêchait d'installer une version récente de MLflow.
- Intégration continue avec GitHub Actions : lint, format, typage strict et tests sur une machine propre, à chaque PR et à chaque push sur `main`, avec les versions exactes du `uv.lock`.

### Corrigé
- Les séries mensuelles du rapport v0.0 comptaient aussi les cartes prépayées de l'ancienne catégorie combinée (6 066 réclamations en 2022-2023, environ 1 % du volume). Les conclusions du cadrage ne changent pas.

## [v0.0] - 2026-10-17

### Ajouté
- Rapport de cadrage en LaTeX et en PDF : contexte, besoins, enjeux, travaux existants, faisabilité, solution, seuils de décision, planning et risques.
- Étude de faisabilité reproductible sur la base du CFPB : séries mensuelles du périmètre bancaire et part des réclamations avec récit dans l'archive officielle.
- Scripts de génération des figures et du PDF.
- Note de décision ADR 0001 sur le cadrage.
- Configuration du projet avec uv, ruff, mypy en mode strict, pytest et pre-commit.
