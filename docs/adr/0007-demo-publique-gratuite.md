# ADR 0007 : une démo publique gratuite, sur Render, avec sa base dans l'image

- Statut : accepté
- Date : 20 octobre 2026
- Version : v1.0
- Rapport détaillé : [complaint-triage_v1.0_Rapport-demo-publique.pdf](../pdf/complaint-triage_v1.0_Rapport-demo-publique.pdf)
- Remplace en partie : [ADR 0006](0006-industrialisation-legere.md), sur l'hébergement de la v1.0

## Contexte

L'ADR 0006 prévoyait une démo publique hébergée gratuitement, sans moyen de paiement. Le projet sert de vitrine : la démo doit montrer les trois briques (file prioritaire, RAG, agent) en un clic, sans rien coûter, ni à l'hébergement ni en appels au modèle de langage. Les données réelles ne doivent pas entrer dans le dépôt principal.

## Décisions

### Render, offre gratuite, au lieu de Hugging Face Spaces

Hugging Face Spaces était le premier choix. Au moment du déploiement, les Spaces Docker exigeaient un abonnement payant. Render construit la même image Docker que la CI, sur une offre gratuite sans carte bancaire : 512 Mo de mémoire, mise en veille après 15 minutes sans visite. La CI lance l'image avec ces mêmes contraintes.

### Un dépôt de déploiement à part

Un script publie le contenu de l'image, données comprises, dans le dépôt `complaint-triage-demo`, que Render reconstruit à chaque commit. Le script choisit chaque fichier, refuse un dépôt local modifié et ne publie qu'un commit de `main`. Les données réelles restent hors du dépôt principal.

### La base PostgreSQL préparée dans l'image

La première version créait la base et chargeait les 30 339 réclamations à chaque lancement : le premier réveil prenait plus de 150 secondes. La base est désormais préparée à la construction de l'image. Au lancement, PostgreSQL démarre et les comptes reçoivent des mots de passe neufs ; aucun mot de passe de la construction ne sert ensuite. L'administrateur n'est joignable que par le socket local, pour l'utilisateur système du conteneur. Réveil mesuré : 42 secondes, presque tout dû à l'hébergeur.

### Exemples enregistrés, questions libres plafonnées

Les exemples affichés viennent des évaluations de la v0.4, relus dans le cache sans aucun appel. Les questions libres n'existent que si une clé est fournie : une clé Gemini dédiée, dans un projet Google sans facturation, plafonnée par l'application à 5 questions par visite et 100 par jour ; le premier refus de Google pour quota coupe le mode en direct pour tous.

## Alternatives écartées

| Option | Raison |
|---|---|
| Hugging Face Spaces (Docker) | Abonnement payant exigé pour Docker |
| Page statique Hugging Face | Gratuite, mais ni base ni question libre : des résultats, pas un système qui tourne |
| Streamlit Community Cloud | Pas de Docker ; PostgreSQL par apt sur une autre version de Debian ; l'image testée en CI ne serait plus celle qui tourne |
| Base hébergée à part | Un service de plus à créer, et souvent limité dans le temps sur les offres gratuites |
| Charger la base à chaque lancement | Réveil de plus de deux minutes |

## Conséquences

La démo est en ligne à l'adresse https://complaint-triage-zj94.onrender.com, sans aucune dépense. Le premier visiteur après une mise en veille attend environ 40 secondes, ce qui est annoncé dans le README. La mémoire n'est pas observable sur l'offre gratuite ; seule l'absence de dépassement l'est. La reformulation finale de l'agent n'est pas vérifiée mot pour mot, contrairement aux réponses de l'onglet Réglementation. La CI compte quatre tâches bloquantes.
