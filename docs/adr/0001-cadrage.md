# ADR 0001 : sujet, données et critères de succès

- Statut : accepté
- Date : 17 octobre 2026
- Version : v0.0
- Rapport détaillé : [complaint-triage_v0.0_Rapport-de-cadrage.pdf](../pdf/complaint-triage_v0.0_Rapport-de-cadrage.pdf)

## Contexte

Je voulais un projet d'IA complet (scoring, RAG, agent, mise en production) qui réponde à un vrai problème, avec un résultat mesurable. Le plan de départ reposait sur un jeu de tickets de support trouvé sur Kaggle. Avant d'écrire du code, j'ai vérifié trois points : la qualité des données, la réalité du problème et la façon de mesurer le succès.

## Décisions

### Abandon des jeux de tickets synthétiques

Le jeu le plus utilisé sur Kaggle, *Customer Support Ticket Dataset* (suraj520), a des priorités tirées au hasard. Plusieurs projets publics obtiennent environ 20 % de bonnes réponses sur 5 classes, moins qu'en prédisant toujours la classe majoritaire. Certains textes contiennent même des gabarits jamais remplis, comme `{product_purchased}`.

Le second candidat, *Customer IT Support Tickets* (Tobi Bueck), est généré par un LLM et n'a pas de dates. Un modèle y apprendrait les habitudes du générateur, et un découpage dans le temps serait impossible.

### Base de réclamations du CFPB, limitée à la banque de détail

Cette base est réelle, publique, sans clé d'accès, datée et mise à jour chaque jour. L'issue de chaque réclamation y est renseignée par l'établissement. Je garde les cartes de crédit et les comptes courants et d'épargne : environ 16 000 réclamations par mois, dont 14 % aboutissent à une indemnisation. Le *credit reporting*, qui représente entre 84 % et 96 % du volume, est exclu. Il concerne les agences d'évaluation du crédit, et le taux d'indemnisation y est presque nul.

### L'arrêt des récits au centre du projet

Le 14 août 2026, le CFPB a arrêté de publier le texte des réclamations. L'API et l'export n'en contiennent plus aucun, même pour les dossiers anciens. Les récits déjà publiés restent dans une archive officielle qui n'évoluera plus. J'ai choisi de construire le projet autour de cette contrainte : le modèle de production utilise seulement les données structurées, un modèle de texte est entraîné sur l'archive, et je mesure ce que l'on perd sans le texte.

### Critères de succès fixés avant la modélisation

- L'indicateur principal est la Capture@10 %, la part des réclamations indemnisées présentes dans les 10 % les mieux classés.
- La référence n'est pas le hasard mais une règle métier, H0 : le taux historique par produit, motif et sous-motif.
- Le modèle doit faire au moins 5 points de mieux que H0, et la borne basse de son intervalle de confiance (bootstrap) doit rester au-dessus de H0. Sinon, H0 est livrée et l'échec est documenté.
- Seules les réclamations de plus de 90 jours servent à l'entraînement. Un mois après la réception, 29 % des dossiers n'ont pas encore d'issue. Après trois mois, il en reste moins de 1 %.

## Alternatives écartées

| Option | Raison |
|---|---|
| Tickets Kaggle synthétiques | Labels aléatoires ou générés, sans lien avec la réalité |
| Issues GitHub de Kubernetes (environ 14 000 priorités posées par des humains) | Bonne option technique, mais moins parlante pour la banque et l'assurance. Gardée en réserve |
| Journal d'incidents ITSM (UCI) | La priorité y est calculée par une formule et il n'y a pas de texte, donc ni NLP ni RAG |
| Copie Kaggle de la base CFPB (2016) | Ancienne nomenclature, peu de récits, moins complète que l'archive officielle |
| Comparaison avec le hasard | N'importe quelle règle de bon sens fait mieux, cela ne prouve pas l'utilité du modèle |

## Conséquences

Les données sont réelles, et leurs difficultés aussi : dérive, délai avant de connaître l'issue, disparition du texte, changement de nomenclature en 2023. Tout est reproductible par script.

En contrepartie, les trois derniers mois ne servent jamais à l'entraînement et le texte n'existe plus en production. La modélisation elle-même a déjà été explorée par d'autres, ce n'est donc pas là que le projet apporte quelque chose de nouveau.

Je m'engage aussi sur trois points pour la v0.1 : une liste fermée des variables connues à la réception, vérifiée par un test ; une table de correspondance entre anciennes et nouvelles catégories de produits ; une analyse par sous-groupe qui peut bloquer la mise en service.

## Pour l'oral (environ 1 min 30)

> Au départ, je voulais utiliser un jeu de tickets de support trouvé sur Kaggle. En le vérifiant avant de coder, je me suis rendu compte que les priorités étaient tirées au hasard : aucun modèle n'aurait pu apprendre quoi que ce soit. Je suis donc parti sur des données réelles, la base publique de réclamations du régulateur financier américain, en me limitant aux cartes et aux comptes bancaires. Ça représente environ 16 000 réclamations par mois, dont 14 % finissent par une indemnisation.
>
> Le problème métier est simple : un service réclamations traite les dossiers dans l'ordre d'arrivée, et l'objectif est de faire passer devant ceux qui sont fondés. J'ai fixé le critère de succès avant de commencer : la part des dossiers indemnisés qu'on retrouve dans les 10 % traités en priorité. Le modèle doit battre une règle métier simple, pas seulement le hasard. S'il n'y arrive pas, je garde la règle.
>
> Deux contraintes réelles structurent le projet. L'issue d'un dossier n'est connue qu'après plusieurs semaines. J'ai mesuré qu'il faut environ 90 jours, donc je n'entraîne que sur des dossiers plus anciens. Et en août 2026, le régulateur a arrêté de publier le texte des réclamations, donc mon système doit fonctionner sans texte en production. C'est ce qui en fait un projet de mise en production plutôt qu'un notebook.

## Questions probables en entretien

**Pourquoi ne pas simplement retirer les dossiers encore en cours ?** Les dossiers clos rapidement sont surtout des cas simples. En ne gardant qu'eux, on biaiserait l'échantillon. C'est un problème de censure, comme en analyse de survie.

**Pourquoi 90 jours et pas 60 ?** C'est une première valeur, mesurée sur un seul instantané : moins de 1 % de dossiers sans issue à trois mois. Elle sera affinée en v0.1 avec la courbe complète du taux de dossiers sans issue selon leur âge.

**La variable « établissement » ne pose-t-elle pas problème ?** Si. Pour une seule banque cliente, elle serait constante. Je déciderai de son traitement en v0.1, et l'évaluation sera aussi faite établissement par établissement.
