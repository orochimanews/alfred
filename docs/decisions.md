# Décisions Architecturales (ADR) - Alfred

## ADR-001 : Choix de la bibliothèque de hook clavier
- **Décision** : Utiliser la bibliothèque `keyboard` pour intercepter les touches système sous Windows.
- **Raison** : `keyboard` permet le hook de bas niveau avec interception et suppression (`suppress=True`) des touches afin que la touche tapée ne s'écrive pas dans les applications tierces lorsqu'elle déclenche une action.
- **Conséquence** : Nécessite les privilèges utilisateur standard ou administrateur sous Windows selon les fenêtres cibles protégées (UAC).

## ADR-002 : Contrôle Curseur & Vitesse via Windows API (ctypes user32)
- **Décision** : Utiliser `ctypes.windll.user32` (`SetCursorPos`, `mouse_event`, `SystemParametersInfoW`) pour les interactions souris et le changement de vitesse.
- **Raison** : Zéro dépendance binaire lourde, exécution instantanée en microsecondes, support natif de la modification de vitesse du curseur Windows sans redémarrage.

## ADR-003 : Format de Configuration TOML & Multi-Fichiers
- **Décision** : Utiliser le format TOML avec un découpage par domaine (`config.toml`, `commands.toml`, `keys.toml`, `grid.toml`, `actions/*.toml`).
- **Raison** : TOML est très lisible pour l'humain, typé, et permet d'ajouter de nouvelles actions simplement en déposant un fichier `.toml` dans `settings/actions/` sans toucher au code ni aux autres actions.

## ADR-004 : Framework UI CustomTkinter
- **Décision** : Utiliser `customtkinter` pour l'interface graphique.
- **Raison** : Moderne, support natif des thèmes Sombre / Clair, légèreté, empaquetage facile avec PyInstaller sous Windows.
