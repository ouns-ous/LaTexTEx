# Audit LaTexTEx — 3 octobre 2026

Résultat : **58 vérifications fonctionnelles réussies, 7 tests du modèle réussis**, et tests de non-régression Code/Visual, compilation multi-fichiers/BibTeX/SyncTeX et mise en page réussis. Aucun callback Tk inattendu dans le scénario d’audit complet. Les tests utilisent des projets temporaires ; les projets personnels ne sont pas utilisés pour compiler ou éditer.

## Fonctions vérifiées

- Projets : création, ouverture, renommage, duplication, archive, corbeille, restauration, filtres et persistance après redémarrage.
- Fichiers : dossiers, création dans le dossier sélectionné, import, renommage d’un fichier ouvert, corbeille et restauration par la fenêtre dédiée.
- Édition : sélection et gras, annuler/rétablir, indentation, commentaires LaTeX, retour à la ligne, recherche/remplacement et lecture seule.
- Visual : texte et titres, préservation des blocs avancés, sauvegarde, navigation depuis le plan et bascule Code/Visual.
- Insertions : lien avec hyperref, tableau, image avec graphicx et nom de fichier compatible LaTeX ; compilation du document contenant ces insertions.
- Sauvegarde : autosave réel sur disque, historique et restauration, préférences persistantes et commentaires locaux résolus.
- Compilation réelle : pdfLaTeX, XeLaTeX, LuaLaTeX, BibTeX et Biber ; document principal multi-fichiers ; arrêt d’un processus LaTeX ; navigation d’erreurs et conservation du dernier PDF réussi.
- PDF : aperçu, export, précédent/suivant et numéro de page, recherche sur plusieurs pages, zoom, adaptation à la page, mode sombre, PDF invalide et bibliothèque PDF depuis le mode éditeur seul.
- Exports/imports : source, PDF et ZIP ; ressources incluses, données internes exclues ; import ZIP et dossier par l’interface ; archive ZIP invalide signalée proprement.
- Interface : boutons et icônes embarquées, Layout, panneau de fichiers, petites fenêtres, fenêtres de symboles/images/partage/compilation, aide et assistant local.

## Correctifs appliqués

1. Ajout de hyperref/graphicx sans déplacer le curseur : les liens et images restent dans le document.
2. Modification d’une sélection en une seule opération d’annulation, y compris les outils de mise en forme et le remplacement.
3. Navigation du plan et SyncTeX depuis Visual vers le code visible.
4. Remplacement désactivé en lecture seule, sans faux message de réussite.
5. Annulation du callback de coloration lors des fermetures/restaurations pour éviter une erreur sur un onglet détruit.
6. Bibliothèque PDF visible après une mise en page « éditeur seul » ; retour au projet avec éditeur visible.
7. Boutons de zoom basés sur le pourcentage réel, avec borne minimale de 25 %.
8. Commentaires conservant leur lien après renommage du fichier ou de son dossier.
9. Archive ZIP invalide affichant une erreur au lieu d’un callback non intercepté.
10. Noms d’images nettoyés des caractères problématiques pour LaTeX, et libellé compact Recompile après compilation.

## Portée

Les choix de fichiers et confirmations sont simulés dans les tests ; les boutons, opérations sur disque, exports et compilateurs sont réellement exécutés. Cela vérifie les scénarios listés, sans garantir tous les documents LaTeX possibles ni tous les packages externes. Les outils d’ouverture du dossier dans l’Explorateur, les états hover/focus et tous les raccourcis système ne sont pas validés exhaustivement. Share reste un export local ; l’assistant est une vérification locale ; Visual conserve les constructions avancées en code.

Le détail machine des vérifications est dans `audit-results.json`. Les scripts reproductibles sont `test_projects.py`, `verify_audit.py`, `verify_options.py`, `verify_projects.py`, `verify_biber.py`, `verify_edge_cases.py` et `preview_projects.py`.
