# ADR 0005 : une sûreté placée dans le code et mesurée sur des jeux jamais essayés

- Statut : accepté
- Date : 19 octobre 2026
- Version : v0.4
- Rapport détaillé : [complaint-triage_v0.4_Rapport-qualite.pdf](../pdf/complaint-triage_v0.4_Rapport-qualite.pdf)

## Contexte

La v0.3 avait montré que chaque comportement attendu de l'agent existait, sur dix démonstrations qui avaient aussi servi à régler la consigne. Elle laissait une limite connue : le contrôle du plan vérifiait qu'un numéro de dossier n'était pas inventé, pas qu'il venait d'une source de confiance. Le cadrage fixe pour la v0.4 deux seuils : au moins 90 % d'outils bien choisis sur 20 à 25 scénarios écrits à l'avance, et 100 % des refus attendus. La v0.2 avait aussi noté trois cas où la vérification des citations du RAG était plus stricte que nécessaire.

## Décisions

### Une écriture seulement sur un dossier nommé dans la demande

Un numéro lu dans un résultat d'outil, par exemple dans le récit d'une réclamation, que le client rédige, permet de lire ce dossier, plus d'écrire dessus. La règle est appliquée par le contrôle du plan, donc par le code : même si le modèle obéissait à une instruction cachée, l'écriture serait rejetée. La consigne demande de présenter les dossiers candidats et de faire confirmer le numéro.

### Des scénarios de sûreté où le modèle est hostile, dans une étape à part de la CI

Seize scénarios décrits dans un fichier de données : quatorze attaques d'un faux modèle qui obéit à l'attaquant et deux témoins légitimes. Chacun vérifie la liste exacte des outils exécutés. Deux défauts introduits volontairement ont fait échouer exactement les scénarios qui les visent. L'étape « Scénarios de sûreté de l'agent » bloque la fusion d'une PR en cas de régression.

### Des jeux d'évaluation écrits avant tout essai, lancés une seule fois

Vingt-quatre scénarios d'agent sur une nouvelle banque fictive, dont cinq manipulations par des canaux différents ; trente nouvelles questions du RAG. Le calcul des critères et la règle d'adoption des assouplissements ont été fixés et versionnés avant le lancement ; les deux scripts refusent de tourner une seconde fois.

### La vérification assouplie des citations adoptée

Insensible à la casse, acceptant un sous-paragraphe d'un passage fourni et les extraits coupés par des points de suspension (morceaux d'au moins dix caractères, dans l'ordre). Adoptée selon la règle fixée : 17 réponses correctes sur 20 contre 16, aucune mauvaise source, 10 refus hors corpus sur 10. Activée pour l'usage réel ; les fonctions gardent la vérification stricte par défaut.

## Résultat

Agent : 100 % d'outils bien choisis (16 / 16), 100 % de refus attendus (7 / 7), aucune écriture non demandée sur 24 scénarios ; les cinq manipulations ont échoué. RAG : réponse correcte à chaque question dont le bon passage a été retrouvé (17 / 17) ; les trois refus restants viennent de la recherche.

## Alternatives écartées

| Option | Raison |
|---|---|
| Garder la protection contre l'injection dans la seule consigne | Un modèle peut être manipulé ; la règle doit être dans le code |
| N'autoriser aucune écriture sur un dossier trouvé par un outil, même nommé ensuite | Trop restrictif : l'utilisateur doit pouvoir agir sur un dossier qu'il a désigné |
| Réévaluer sur les scénarios de démonstration | Ils avaient servi à régler la consigne ; le résultat aurait été trop favorable |
| Relancer l'évaluation après l'erreur de calcul | L'évaluation aurait cessé d'être unique ; les critères ont été recalculés sur les résultats enregistrés |

## Conséquences

Une écriture demande désormais que l'utilisateur désigne le dossier : une étape de confirmation en plus, que l'on assume. Vingt-quatre scénarios restent un petit échantillon : ils montrent que les seuils sont franchis, pas que l'agent ne se trompera jamais ; la garantie forte vient des scénarios de sûreté. L'assouplissement des extraits coupés peut en théorie inverser le sens d'un texte ; aucun cas n'est apparu, il faudra le surveiller. Le maillon faible du RAG est la recherche, sur le vocabulaire des clients. La v0.5 apportera Docker et la base dans la CI.
