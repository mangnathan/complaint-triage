# ADR 0006 : une industrialisation légère, dans la CI de GitHub

- Statut : accepté
- Date : 19 octobre 2026
- Version : v0.5
- Rapport détaillé : [complaint-triage_v0.5_Rapport-industrialisation.pdf](../pdf/complaint-triage_v0.5_Rapport-industrialisation.pdf)

## Contexte

Le cadrage prévoyait pour la v0.5 Docker et une chaîne CI/CD complète, puis en v1.0 un déploiement sur Google Cloud Run. Trois éléments ont changé la donne : le poste de développement n'a que 8 Go de mémoire, ce qui rend Docker Desktop pénible ; le projet suit une règle de zéro dépense, alors que Google Cloud exige de lier un moyen de paiement ; et le projet sert de vitrine pour une recherche d'emploi, où le temps passé compte autant que la technique.

## Décisions

### La base et l'image testées dans la CI, rien à installer sur le poste

Une tâche de CI démarre PostgreSQL 18.6 dans un conteneur jetable, le met en place avec le script du projet et lance les tests d'intégration. Avec `REQUIRE_DATABASE=1`, un test qui serait sauté faute de base échoue. Une autre tâche construit l'image de l'application et vérifie qu'elle démarre, tourne sans root et ne contient ni secret, ni données, ni tests.

### Une image aux versions exactes, sans rien de privé

Python 3.12.15 et uv 0.13.1, vérifiés sur les registres avant d'être figés ; dépendances depuis `uv.lock` ; utilisateur dédié ; `.dockerignore` strict. Les données se montent au lancement, les secrets passent par l'environnement.

### Le déploiement de la v1.0 devient une démo publique gratuite

Google Cloud Run est écarté : il impose un moyen de paiement. La v1.0 sera une démo publique, hébergée gratuitement sans carte bancaire, sur des données fictives, avec des réponses en cache et un plafond strict d'appels au modèle de langage.

## Alternatives écartées

| Option | Raison |
|---|---|
| Docker Desktop sur le poste | Trop lourd pour 8 Go ; la CI construit et teste l'image |
| Podman sur le poste | Utile pour déboguer une image, inutile tant que la CI suffit |
| Publier l'image dans un registre | Sans valeur avant un hébergement |
| Google Cloud Run | Exige un moyen de paiement, contraire à la règle de zéro dépense |

## Conséquences

Chaque PR passe par trois tâches en parallèle, d'environ une minute chacune : qualité et sûreté, base et intégration, image. Une erreur dans l'image ne se voit qu'en CI, pas sur le poste : c'est acceptable tant que l'image reste simple. Les nouvelles tâches ne sont pas encore obligatoires dans la protection de la branche principale ; il suffit de les ajouter à la règle dans GitHub.
