# Changelog

Les évolutions notables du projet sont notées ici, selon le format [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/). Chaque version correspond à une étape du projet et porte un tag Git (`v0.0`, `v0.1`, etc.).

## [Non publié]

### Modifié
- Une écriture de l'agent (statut, alerte) n'est plus permise que sur un dossier nommé dans la demande de l'utilisateur. Un numéro lu dans un résultat d'outil, par exemple dans le récit d'une réclamation, suffit pour lire ce dossier, plus pour écrire dessus. Corrige la limite identifiée en v0.3.

### Ajouté
- Jeux d'évaluation de la v0.4, écrits et versionnés avant tout essai : 24 scénarios d'agent (`evaluation/agent/scenarios-evaluation.json`), dont cinq manipulations par des canaux différents (récits, demande, nom d'établissement) ; 20 nouvelles questions du RAG dans le corpus et 10 hors du corpus (`evaluation/rag/*-v2.csv`).
- Données fictives de l'évaluation (`complaint_triage.agent.evaluation_data`), distinctes de celles des démonstrations ; la remise à zéro refuse tout identifiant réel.
- Scénarios de sûreté de l'agent (`evaluation/agent/scenarios-surete.json`, `tests/safety/`) : 14 attaques d'un modèle hostile et 2 témoins légitimes, rejoués dans une étape à part de la CI. Deux défauts volontaires ont confirmé que les scénarios détectent les failles qu'ils visent.
- Assouplissements de la vérification des citations du RAG (casse, sous-paragraphe d'un passage fourni, extrait coupé par des points de suspension), adoptés selon la règle fixée à l'avance : 17 réponses correctes sur 20 contre 16, aucune mauvaise source, 10 refus hors corpus sur 10.
- Évaluation de l'agent sur 24 scénarios jamais essayés : 100 % d'outils bien choisis (16 / 16), 100 % de refus attendus (7 / 7), aucune écriture non demandée ; les cinq manipulations ont échoué.
- Calcul des critères de l'agent (`complaint_triage.agent.evaluation`), testé ; option `--recompute` pour recalculer à partir des résultats enregistrés.
- Rapport v0.4 commencé (objectifs, provenance, protocole, sûreté en CI, évaluation).

### Corrigé
- Le calcul des critères fusionnait le statut obtenu et sa vérification sous le même nom et affichait 0 refus sur 7. Vérifications renommées (`statut_ok`, `outils_ok`, `ecritures_ok`) ; critères recalculés sans relancer l'agent.

## [v0.3] - 2026-10-19

Bilan ([ADR 0004](docs/adr/0004-agent-aux-outils-encadres.md)) : l'agent annonce son plan, utilise sept outils encadrés et répond ou refuse. Trois couches de sûreté : les droits de la base, des outils fermés aux entrées validées, et un contrôle de chaque plan par le code avant exécution. Dix démonstrations réussies sur dix, dont une manipulation cachée dans un récit. Limite connue, traitée en v0.4 : le contrôle vérifie qu'une valeur n'est pas inventée, pas qu'elle vient d'une source de confiance.

### Ajouté
- Base PostgreSQL (`complaint_triage.db`) : trois comptes au moindre privilège (propriétaire ; agent en lecture seule ; agent qui ne peut modifier que le statut d'un dossier et écrire dans le journal), limite de 5 secondes par requête, schéma `triage` avec les réclamations et le journal des actions. Script de mise en place (`scripts/db/setup_database.py`) qui tire les mots de passe au hasard et les écrit dans `.env` sans les afficher. Tests d'intégration qui tentent les opérations interdites sur la vraie base.
- Chargement de la file (`python -m complaint_triage.db`) : 140 512 réclamations reçues depuis le 1er janvier 2026, sans issue ni code postal, notées par la règle retenue en v0.1.
- Outils de l'agent (`complaint_triage.agent.tools`) : recherche d'un établissement, lecture d'une réclamation, rang dans la file de la semaine, file prioritaire d'un établissement, question de réglementation par le RAG, changement de statut et alerte. Entrées validées par pydantic avant toute action, requêtes écrites dans le code et paramétrées, chaque écriture tracée au journal dans la même transaction.
- Alertes par webhook (`complaint_triage.agent.alerts`) et récepteur local qui n'écoute que sur 127.0.0.1 (`scripts/agent/alert_receiver.py`).
- Graphe de l'agent avec LangGraph (`complaint_triage.agent.graph`) : décider, vérifier le plan, exécuter, trois tours au plus. Le code contrôle chaque plan avant exécution (outils connus, entrées valides, une écriture au plus, aucun numéro ni établissement inventé) ; un plan rejeté peut être corrigé une fois, et le début valide d'un plan s'exécute pendant que les étapes douteuses sont écartées. Commande `scripts/agent/run_agent.py`.
- Démonstrations reproductibles (`scripts/agent/run_demonstrations.py`) : banque fictive remise à zéro avant chaque série, dix scénarios versionnés avant le premier lancement (`evaluation/agent/scenarios-demonstration.json`), vérification automatique du statut, des outils et des écritures. Dix scénarios réussis sur dix, dont une manipulation cachée dans un récit, ignorée par l'agent.
- Rapport v0.3 complet en LaTeX et en PDF (9 pages) et note de décision ADR 0004.

## [v0.2] - 2026-10-18

Bilan ([ADR 0003](docs/adr/0003-rag-avec-citations-verifiees.md)) : sur le test, 13 réponses sur 13 citent une source vérifiable et 20 questions hors corpus sur 20 sont refusées, tentatives de détournement comprises ; les deux critères du cadrage sont atteints, et aucune réponse ne cite une mauvaise source. Le RAG refuse en revanche 7 questions de test sur 20 auxquelles il aurait pu répondre.

### Ajouté
- Corpus réglementaire du RAG (`complaint_triage.rag`, commande `python -m complaint_triage.rag`) : Regulation E (sous-partie A), Regulation Z (sous-parties B et G) et Regulation DD, téléchargées depuis l'API officielle de l'eCFR dans leur version du 15 octobre 2026, lues avec defusedxml et découpées en 394 passages citables, un par paragraphe de premier niveau (« 12 CFR 1005.11(b) »), avec un lien vers le texte officiel et un manifeste des sources.
- Recherche des passages (`complaint_triage.rag.retrieval`) : mots-clés (BM25), sens (embeddings locaux `BAAI/bge-small-en-v1.5` avec fastembed, gardés en cache sur disque) et fusion par rangs réciproques. Jeu de 40 questions avec leurs passages attendus (`evaluation/rag/questions-recherche.csv`), réparties entre développement et test. La recherche par le sens est retenue sur le développement : rappel@5 de 80 %, puis 85 % sur le test, contre 45 % pour les mots-clés.
- Génération avec citations vérifiées (`complaint_triage.rag.answer`) : Gemini répond dans un format JSON imposé, chaque citation donne un passage et un extrait exact, et le code refuse toute la réponse si une seule citation est invérifiable. Question nettoyée et limitée à 1 000 caractères.
- Accès à Gemini (`complaint_triage.rag.llm`) sur l'offre gratuite, avec cache des réponses, plafond de 300 appels par jour et 10 par minute contrôlé avant l'envoi, arrêt sur une réponse 429 ; clé dans `.env`, transmise par en-tête. Commande `scripts/rag/ask.py` pour poser une question.
- Évaluation des réponses (`scripts/rag/evaluate_answers.py`) : 40 questions hors corpus (`evaluation/rag/questions-hors-corpus.csv`) en plus des 40 du corpus, estimation des appels avant de lancer, règle de choix fixée avant le premier appel. 10 passages lus, retenus sur le développement. Analyse des refus à tort (`docs/v0.2-rag/data/refus-a-tort.csv`).
- Rapport v0.2 complet en LaTeX et en PDF (11 pages) et note de décision ADR 0003.

### Corrigé
- Le découpage du corpus laissait les définitions de la Regulation E en un seul bloc (« (a)(1) » sans espace) et prenait certaines lettres pour des chiffres romains. Les voisins de chaque marqueur tranchent désormais ; le corpus passe de 366 à 394 passages.

## [v0.1] - 2026-10-18

Décision de fin de version ([ADR 0002](docs/adr/0002-moteur-de-priorisation.md)) : sur la période de test, XGBoost ne bat pas la règle H0 propre à chaque banque (17,0 % de Capture@10 % contre 17,4 %, écart de −0,5 point [−0,8 ; −0,1]). La règle est retenue comme moteur de priorisation. Elle respecte les seuils d'équité (rapports de 0,93 à 1,12) et de calibration (ECE de 0,024). Le texte atteint son critère (+0,063 de PR-AUC) et reste un composant optionnel, faute de récits publiés depuis août 2026.

### Ajouté
- Module `complaint_triage.data` : téléchargement idempotent et atomique des sources du CFPB, lecture de l'export complet par morceaux, harmonisation de l'ancienne catégorie « Credit card or prepaid card », jointure des récits de l'archive, contrôles de schéma avec pandera, écriture en Parquet avec un manifeste (tailles et empreintes SHA-256 des sources).
- Commande `python -m complaint_triage.data` pour construire le jeu de données.
- Préparation des données pour la modélisation (`complaint_triage.data.prepare`) : retrait des six gestionnaires de fichiers de consommateurs (62 321 réclamations, 0,1 % d'indemnisation), règle des 90 jours confirmée par la courbe de maturité, cible `is_monetary_relief`. 523 552 réclamations préparées.
- Liste fermée des colonnes connues à la réception, avec un test qui échoue si une colonne n'a pas de rôle défini.
- Script d'exploration reproductible (`scripts/analysis/explore_dataset.py`) : maturité des issues, établissements sans indemnisation, pic de janvier 2025 (panne chez Capital One, campagne sur les frais de découvert de Navy Federal), récits recopiés (6,3 %, indemnisés à 0,25 %), taux d'indemnisation par motif.
- Cadre d'évaluation (`complaint_triage.evaluation`) : découpage dans le temps (entraînement jusqu'en juin 2025, validation au second semestre 2025, test en 2026, ouvert une seule fois), Capture@10 % semaine par semaine avec traitement exact des ex æquo, PR-AUC, intervalle de confiance par bootstrap sur des semaines entières, y compris pour l'écart entre deux classements.
- Règles de référence (`complaint_triage.models.baseline`) : H0, taux d'indemnisation par produit, motif et sous-motif, lissé vers la catégorie parente, et H0 propre à la banque.
- Variables de volume récent (`complaint_triage.models.features`), calculées uniquement sur le passé.
- Modèle XGBoost (`complaint_triage.models.gradient_boosting`) sur les variables connues à la réception, catégories natives, arrêt sur trois mois mis de côté, contributions SHAP. Expériences tracées dans MLflow : 4 variantes et 8 réglages fixés à l'avance.
- Référence textuelle TF-IDF et fine-tuning de DistilRoBERTa sur Google Colab, avec reprise automatique au dernier point de sauvegarde. Sur les récits de validation jamais vus, dans la file de chaque banque : TF-IDF +2,8 points sur H0 propre à la banque [1,8 ; 3,6], DistilRoBERTa +3,0 points [2,0 ; 4,0]. Le modèle de langage ne fait pas mieux que le TF-IDF.
- Contrôles d'équité et de calibration (`complaint_triage.evaluation.fairness` et `.calibration`) : rapport des Capture@10 % entre un sous-groupe et les autres clients, et erreur de calibration (ECE) sur 10 classes.
- PR-AUC calculée dans chaque file (`pr_auc_in_queues`).
- Règles de décision du cadrage dans le code (`complaint_triage.evaluation.decision`) et script de décision sur la période de test (`scripts/evaluation/decide_on_test.py`), qui refuse de tourner une seconde fois et propose une répétition sur la validation. Le protocole a été publié avant l'ouverture du test.
- Rapport v0.1 complet en LaTeX et en PDF (32 pages) et note de décision ADR 0002.
- 81 tests unitaires, sans accès réseau.

### Modifié
- Chaque banque traite en priorité 10 % de la file de chaque produit (`complaint_triage.evaluation.queues`). Avec une seule file par banque, les réclamations indemnisées sur un compte courant n'étaient traitées en priorité que dans 8 à 11 % des cas, autant ou moins qu'au hasard, et le rapport entre produits sortait des seuils du cadrage (2,4 pour la règle H0, 3,7 pour XGBoost). Avec une file par produit, tous les rapports rentrent dans les seuils ; la Capture@10 % sur la validation passe de 19,4 % à 18,4 % pour H0 propre à la banque et à 19,0 % pour XGBoost.
- Pour la décision finale, les modèles sont réentraînés sur l'entraînement et la validation réunis, avec les réglages choisis sur la validation.
- La contrainte sur pyarrow passe de `>=26` à `>=21` : la borne posée par défaut empêchait d'installer une version récente de MLflow.
- Intégration continue avec GitHub Actions : lint, format, typage strict et tests sur une machine propre, à chaque PR et à chaque push sur `main`, avec les versions exactes du `uv.lock`.

### Corrigé
- La Capture@10 % classait toutes les banques ensemble et avantageait les modèles capables de deviner la banque, ce qui ne sert à rien à un établissement qui trie sa propre file. Elle est désormais calculée dans la file de chaque établissement, et la référence devient H0 propre à la banque. La marge exigée ne change pas. Défaut repéré grâce aux mots les plus importants de la référence textuelle, qui étaient des noms de banques. Conséquence : le gain de 3 points mesuré d'abord pour XGBoost venait des compteurs de volume par établissement, et disparaît.
- Les séries mensuelles du rapport v0.0 comptaient aussi les cartes prépayées de l'ancienne catégorie combinée (6 066 réclamations en 2022-2023, environ 1 % du volume). Les conclusions du cadrage ne changent pas.

## [v0.0] - 2026-10-17

### Ajouté
- Rapport de cadrage en LaTeX et en PDF : contexte, besoins, enjeux, travaux existants, faisabilité, solution, seuils de décision, planning et risques.
- Étude de faisabilité reproductible sur la base du CFPB : séries mensuelles du périmètre bancaire et part des réclamations avec récit dans l'archive officielle.
- Scripts de génération des figures et du PDF.
- Note de décision ADR 0001 sur le cadrage.
- Configuration du projet avec uv, ruff, mypy en mode strict, pytest et pre-commit.
