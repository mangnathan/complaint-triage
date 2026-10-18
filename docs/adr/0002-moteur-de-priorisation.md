# ADR 0002 : moteur de priorisation retenu à la fin de la v0.1

- Statut : accepté
- Date : 18 octobre 2026
- Version : v0.1
- Rapport détaillé : [complaint-triage_v0.1_Rapport-donnees-et-scoring.pdf](../pdf/complaint-triage_v0.1_Rapport-donnees-et-scoring.pdf), sections 6 à 10

## Contexte

L'ADR 0001 a fixé les critères de la v0.1 avant toute modélisation : un modèle structuré n'est retenu que s'il fait au moins 5 points de Capture@10 % de plus que la règle de référence, avec une borne basse d'intervalle au-dessus d'elle ; le texte est gardé si la PR-AUC gagne au moins 0,02 ; l'outil doit respecter des seuils d'équité (rapports entre 0,8 et 1,25) et de calibration (ECE sous 0,05).

Pendant la version, j'ai comparé quatre variantes d'XGBoost et huit réglages, une référence textuelle TF-IDF et un modèle de langage DistilRoBERTa, sur la validation (second semestre 2025). La période de test (janvier à juillet 2026, 99 089 réclamations) n'a été ouverte qu'une fois, après la publication du protocole de décision.

## Décisions

### La mesure se fait dans la file de chaque banque et de chaque produit

La première version de la Capture classait toutes les banques ensemble. Elle récompensait un modèle capable de reconnaître la banque, ce qui ne sert à rien à un établissement qui trie sa propre file. La mesure classe désormais dans la file de chaque établissement, et la référence devient H0 propre à la banque : ses taux historiques par produit, motif et sous-motif, rapprochés de ceux du marché quand elle a peu de réclamations.

Le contrôle d'équité a ensuite montré qu'avec une seule file par banque, les cartes de crédit, plus souvent indemnisées, prenaient presque toutes les places prioritaires. Une réclamation fondée sur un compte courant était traitée en priorité moins souvent qu'au hasard. Chaque produit a désormais sa propre file. La même logique s'applique à la PR-AUC, calculée dans chaque file.

Aucune de ces corrections n'a modifié un seuil.

### Le moteur de priorisation est la règle H0 propre à chaque banque

Sur le test, XGBoost capte 17,0 % des réclamations indemnisées, contre 17,4 % pour H0 propre à la banque : un écart de −0,5 point [−0,8 ; −0,1]. Le critère n'est pas atteint. Le gain de +0,6 point mesuré sur la validation ne s'est pas confirmé.

La règle retenue respecte les seuils sur le test : rapports d'équité de 0,93 à 1,12 et ECE de 0,024. La mise en service est possible.

### Le texte est gardé comme composant optionnel

Sur les 40 412 récits de test jamais vus pendant l'apprentissage, le TF-IDF gagne 0,063 de PR-AUC dans les files et 2,6 points de Capture@10 % [1,8 ; 3,4] sur H0 propre à la banque. Le critère est atteint. DistilRoBERTa n'a pas été porté jusqu'au test : sur la validation, il faisait jeu égal avec le TF-IDF (22,0 % contre 21,8 %) pour un coût bien plus élevé.

Le CFPB ne publie plus les récits depuis le 14 août 2026 : le système alimenté par ses données ne peut pas utiliser le texte. Le modèle de texte reste disponible pour une banque qui dispose du texte de ses propres réclamations.

## Alternatives écartées

| Option | Raison |
|---|---|
| Retenir XGBoost pour son léger avantage en validation | Le critère du cadrage n'est pas atteint, et le test montre un écart inverse |
| Garder une seule file par banque | Les clients des comptes courants étaient relégués ; le contrôle d'équité échouait |
| Retirer le produit des critères d'équité | Changer la règle après avoir vu le résultat, alors que le préjudice est réel |
| PR-AUC calculée en mélangeant les banques | Même défaut que l'ancienne Capture ; le choix a été fixé avant l'ouverture du test |
| Modèle de langage plutôt que TF-IDF | Résultat égal sur la validation, pour un coût bien plus élevé |

## Conséquences

Le RAG (v0.2) et l'agent (v0.3) sont construits autour de la règle H0 propre à chaque banque, qui leur sert d'outil de scoring. Elle est simple à expliquer à un chargé de réclamations : le dossier passe en tête parce que des réclamations du même type ont souvent été indemnisées par cette banque.

H0 surestime un peu le risque sur le test (17,6 % prédits pour 15,2 % observés), parce que ses taux remontent à 2022. Le classement n'en souffre pas, mais en production les taux seront recalculés chaque mois sur les issues mûres. La Capture@10 %, les rapports d'équité et la calibration seront suivis chaque semaine : sur la validation, les clients militaires avaient un rapport de 0,87, et de 1,12 sur le test. Ces rapports varient d'une période à l'autre.

La période de test est désormais utilisée. Une future comparaison de modèles devra s'appuyer sur des réclamations reçues après juillet 2026.
