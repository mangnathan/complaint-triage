# Sécurité

## Signaler une faille

Merci de **ne pas ouvrir d'issue publique** pour une faille. Utilisez le signalement privé de GitHub : onglet **Security**, puis **Report a vulnerability**. Une réponse est donnée sous sept jours. Cela vaut aussi pour la démonstration en ligne et pour son dépôt de déploiement, `complaint-triage-demo`.

*English: please do not open a public issue for a vulnerability; use GitHub's private vulnerability reporting (Security tab, "Report a vulnerability").*

## Ce qui est exposé

- **La démonstration publique** (complaint-triage-zj94.onrender.com) : une interface Streamlit et une base PostgreSQL interne à l'image. Elle n'appelle pas le modèle de langage et rejoue des réponses enregistrées ; aucune clé d'API n'est rangée chez l'hébergeur ([ADR 0008](docs/adr/0008-demo-sans-mode-direct.md)).

Il n'y a ni compte, ni connexion, ni paiement, ni envoi de fichier.

## Mesures en place

**Base de données**
- Elle n'écoute que dans le conteneur. L'administrateur n'y est joignable que par le socket local ; les comptes du projet reçoivent de nouveaux mots de passe aléatoires à chaque démarrage.
- Un compte par usage, aux droits minimaux : lecture seule pour l'agent, et en écriture seulement le statut et le journal.
- Requêtes paramétrées uniquement ; le modèle de langage n'écrit jamais de SQL.
- Ce qu'un visiteur modifie disparaît au redémarrage suivant.

**Agent et RAG**
- L'agent choisit parmi sept outils aux entrées validées et bornées. Le code contrôle chaque plan avant de l'exécuter : une écriture au plus, seulement sur un dossier nommé dans la demande, et seulement sur des banques fictives.
- Les textes des réclamations sont traités comme des données, jamais comme des instructions ; des scénarios d'injection sont rejoués dans la CI à chaque PR.
- Une réponse du RAG n'est donnée que si chaque citation est retrouvée dans le texte officiel.

**Modèle de langage**
- Sans clé dans l'environnement, le mode en direct reste désactivé dans le code : c'est le cas de la démo publique.
- Pour un usage sur son propre poste, avec sa propre clé : la clé reste sur le serveur et passe dans un en-tête, jamais dans une adresse ni dans un message d'erreur ; les questions libres sont plafonnées à 5 par visite, 10 par minute et 100 par jour ; après un refus de quota de Google, plus aucun appel.

**Image et dépôt**
- L'application ne tourne jamais en root, ce que la CI vérifie sur les deux images ; elle vérifie aussi que l'image principale ne contient ni secret ni donnée.
- Actions GitHub référencées par l'empreinte de leur commit, aucun jeton gardé par un checkout, aucune valeur extérieure collée dans un script. Un test (`tests/unit/test_workflows.py`) vérifie ces règles.
- Dépendances verrouillées par `uv.lock`, sans faille connue au dernier audit (`pip-audit`).
- `.env` n'est jamais versionné.

## Risques connus et acceptés

- **En-têtes de sécurité.** Streamlit ne permet pas d'ajouter des en-têtes comme l'interdiction d'affichage dans un cadre. La démo n'ayant ni compte ni action sensible, le risque est jugé faible.
