# ADR 0003 : RAG avec citations vérifiées par le code

- Statut : accepté
- Date : 18 octobre 2026
- Version : v0.2
- Rapport détaillé : [complaint-triage_v0.2_Rapport-RAG.pdf](../pdf/complaint-triage_v0.2_Rapport-RAG.pdf)

## Contexte

Le cadrage demande un assistant qui réponde aux questions des chargés de réclamations en citant ses sources, ou qui refuse. Deux seuils : 100 % des réponses citent une source vérifiable, et au moins 95 % des questions hors du corpus sont refusées. Un outil d'IA générative peut inventer une réponse : une banque ne peut pas l'accepter. Le projet doit aussi rester gratuit.

## Décisions

### Un corpus réglementaire public, figé à une date

Regulation E (sous-partie A), Regulation Z (sous-parties B et G) et Regulation DD, téléchargées depuis l'API officielle de l'eCFR dans leur version du 15 octobre 2026. Ce sont les règles qui encadrent les deux produits de la v0.1. Le texte est découpé en 394 passages, un par paragraphe de premier niveau, pour que chaque citation (« 12 CFR 1005.11(c) ») désigne un endroit précis du texte officiel. Le XML est lu avec defusedxml.

### Recherche par le sens, calculée en local

Mesurée seule sur 40 questions écrites en langage courant, la recherche par embeddings (`BAAI/bge-small-en-v1.5`, avec fastembed, sans API) place un bon passage parmi les 5 premiers pour 85 % des questions de test. La recherche par mots-clés échoue sur l'écart entre le vocabulaire des clients et celui du règlement (45 %), et la fusion des deux fait moins bien que le sens seul (75 %). Le modèle de langage lit 10 passages, réglage choisi sur le développement.

### Le modèle propose, le code vérifie

Gemini répond dans un format JSON imposé, avec pour chaque affirmation un identifiant de passage et un extrait exact. Le code contrôle chaque citation : passage fourni, extrait présent mot pour mot, au moins 20 caractères. Une seule citation invérifiable, et toute la réponse est refusée.

### Gemini 3.5 Flash-Lite, sur l'offre gratuite et sous plafond

Projet Google sans facturation liée. Le modèle a été choisi d'après les quotas réels du projet : 500 requêtes par jour, contre 20 pour la plupart des modèles Flash. Le code ajoute un cache des réponses, un plafond de 300 appels par jour et 10 par minute vérifié avant l'envoi, et l'arrêt sur une réponse 429. Les tests et la CI utilisent un faux modèle.

## Résultat

Sur le test, avec le réglage choisi sur le développement : 13 réponses sur 13 citent une source vérifiable, 20 questions hors corpus sur 20 sont refusées, tentatives de détournement comprises. Aucune réponse ne cite une mauvaise source. Les deux critères du cadrage sont atteints. Le RAG refuse en revanche 7 questions de test sur 20 auxquelles il aurait pu répondre.

## Alternatives écartées

| Option | Raison |
|---|---|
| Faire confiance au modèle pour citer juste | Un modèle peut affirmer citer un texte qu'il a reformulé ; deux réponses de l'évaluation l'ont fait |
| Recherche hybride | Moins bonne que la recherche par le sens sur ce corpus (75 % contre 85 %) |
| Embeddings par une API | Consommeraient le quota ; le calcul local prend cinq minutes, une fois |
| Modèles Flash plus récents | 20 requêtes par jour seulement sur l'offre gratuite |
| Assouplir la vérification avant de publier les résultats | Les cas à assouplir ont été trouvés dans le test ; les mesurer sur ce même test donnerait un chiffre trop favorable |

## Conséquences

Le RAG est sûr mais prudent : un refus coûte au chargé de réclamations le temps de chercher, une réponse fausse peut coûter une erreur de conformité. En v0.4, sur un nouveau jeu de questions, seront mesurés : une vérification insensible à la casse, qui accepte un sous-paragraphe du passage fourni et les extraits coupés signalés par des points de suspension ; un glossaire du vocabulaire courant pour la recherche. En v0.3, le RAG devient un outil de l'agent, à côté de la règle de priorisation de la v0.1.
