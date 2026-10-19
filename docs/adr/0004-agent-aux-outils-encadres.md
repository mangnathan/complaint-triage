# ADR 0004 : un agent aux outils encadrés, dont le code vérifie chaque plan

- Statut : accepté
- Date : 19 octobre 2026
- Version : v0.3
- Rapport détaillé : [complaint-triage_v0.3_Rapport-agent.pdf](../pdf/complaint-triage_v0.3_Rapport-agent.pdf)

## Contexte

Le cadrage prévoit un agent qui lit une réclamation, annonce son plan, interroge la base avec des requêtes paramétrées, met à jour un statut, alerte un responsable, et refuse en cas d'ambiguïté. Il ne doit jamais décider de l'issue d'un dossier, ni en retirer ou en retarder un. Un agent qui agit sur une base est plus risqué qu'un RAG qui ne fait que répondre : une erreur du modèle de langage peut devenir une écriture.

## Décisions

### PostgreSQL sur le poste, avec des comptes au moindre privilège

PostgreSQL 18, installé comme service Windows à démarrage manuel ; Docker, trop lourd pour une machine de 8 Go, viendra en v0.5. L'agent utilise deux comptes : l'un en lecture seule forcée, l'autre limité aux deux colonnes de statut et à l'ajout de lignes au journal. Requêtes limitées à 5 secondes, aucune suppression possible. Des tests tentent les opérations interdites sur la vraie base et vérifient que PostgreSQL les refuse. La base ne stocke ni l'issue des réclamations ni le code postal.

### Une liste fermée d'outils, jamais de SQL écrit par le modèle

Sept outils : recherche d'un établissement, lecture d'un dossier, rang dans la file de la semaine, file prioritaire, question de réglementation (RAG de la v0.2), changement de statut, alerte par webhook. Entrées validées par pydantic en mode strict avant toute action ; requêtes écrites dans le code et paramétrées. Un dossier ne revient jamais à « nouveau » ; chaque écriture est tracée au journal dans la même transaction.

### Un graphe LangGraph où le code vérifie chaque plan

Trois nœuds en boucle, trois tours au plus : Gemini décide (plan annoncé, réponse ou refus), le code vérifie, puis exécute. Le contrôle exige des outils connus, des entrées valides, une écriture au plus par demande, et aucun numéro de dossier ni nom de banque absent de la demande et des résultats d'outils. Un plan rejeté n'est jamais exécuté ; le modèle en lit la raison et peut le corriger une fois. Le début valide d'un plan s'exécute, les étapes douteuses sont écartées. Le modèle passe par le client Gemini de la v0.2, avec son cache et son plafond.

### Des démonstrations sur une banque fictive

Douze dossiers fictifs, remis à zéro avant chaque série, dont un au récit piégé. Dix scénarios versionnés avant le lancement, vérifiés par le code (statut, outils, écritures). Les vraies réclamations ne sont que lues.

## Résultat

Dix démonstrations réussies sur dix, dont quatre refus attendus et une manipulation cachée dans un récit, ignorée par l'agent ; seules les écritures demandées figurent au journal.

## Alternatives écartées

| Option | Raison |
|---|---|
| Laisser le modèle écrire ses requêtes SQL | Une erreur ou une manipulation pourrait devenir une fuite ou une destruction |
| Un seul compte de base pour l'agent | Les droits doivent limiter l'agent même si le code se trompe |
| Refuser dès qu'un plan est rejeté | L'agent devenait inutile : Gemini devinait le nom d'une banque au premier essai |
| Agents et modèles de LangChain | Le nœud de décision appelle le client Gemini du projet, avec son cache et son plafond |
| Docker dès la v0.3 | Trop lourd sur la machine de développement ; prévu en v0.5 |

## Conséquences et limite connue

Le contrôle du plan vérifie qu'une valeur n'est pas inventée, pas qu'elle vient d'une source de confiance. Un numéro cité dans le récit d'une réclamation passe le contrôle : si le modèle obéissait à une instruction cachée, une écriture sur ce dossier serait possible, dans la limite d'une écriture par demande. La v0.4 n'autorisera une écriture que sur un dossier nommé dans la demande elle-même, et mesurera l'agent sur un nouveau jeu de 20 à 25 scénarios jamais essayés, avec les seuils du cadrage : au moins 90 % d'outils bien choisis et 100 % de refus attendus.
