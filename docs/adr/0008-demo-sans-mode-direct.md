# ADR 0008 : une démo publique sans questions en direct

- Statut : accepté
- Date : 27 novembre 2026
- Version : maintenance après la v1.0
- Remplace en partie : [ADR 0007](0007-demo-publique-gratuite.md), sur les questions libres

## Contexte

L'ADR 0007 ouvrait aux visiteurs de la démo des questions libres, envoyées à Gemini avec une clé dédiée, dans un projet Google sans facturation, plafonnées à 5 par visite et 100 par jour.

Les conditions additionnelles de l'API Gemini, en vigueur depuis le 23 mars 2026, contiennent cette restriction : « You may use only Paid Services when making API Clients available to users in the European Economic Area, Switzerland, or the United Kingdom. » Elles précisent que l'accès à l'API n'est un service payant que par un projet Google Cloud relié à un compte de facturation actif. Une clé sans facturation relève donc de l'offre gratuite, que ces conditions excluent pour une application ouverte à des visiteurs en Europe.

Le projet suit une règle de zéro dépense : il ne relie aucun compte de facturation.

## Décision

La démo publique n'appelle plus le modèle de langage. La clé est retirée des variables de l'hébergeur, et la démo rejoue seulement ses exemples enregistrés : quatre pour l'onglet Réglementation, six pour l'onglet Agent. Ils viennent des évaluations de la v0.4 et sont relus dans le cache, sans aucun appel.

Le code ne change pas. Sans clé, le mode en direct est désactivé, comme prévu dès la v1.0. Il reste disponible pour un usage sur son propre poste, avec sa propre clé ; les plafonds par visite, par minute et par jour restent en place.

## Alternatives écartées

| Option | Raison |
|---|---|
| Relier un compte de facturation | Contraire à la règle de zéro dépense |
| Garder le mode en direct avec la clé gratuite | Non conforme aux conditions de l'API pour des visiteurs en Europe |
| Retirer du code le mode en direct | Inutile : l'usage sur son propre poste reste permis, et le code est testé |

## Conséquences

La démo montre toujours les trois briques (file prioritaire, RAG, agent), mais plus de question libre. Aucune clé d'API n'est exposée sur l'hébergeur. Le README, le résumé en anglais, `SECURITY.md` et le README du dépôt de déploiement le disent ; ce dernier est régénéré au prochain déploiement de la démo.
