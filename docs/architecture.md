# Architecture du Projet Alfred

Alfred est conçu selon une architecture découplée, séparant strictement la logique système, la persistance de configuration, l'état applicatif et la couche de présentation.

## Diagramme des Couches

```
+-------------------------------------------------------------+
|                      Interface Utilisateur                  |
|                   (CustomTkinter - src/alfred/ui)           |
|  - App Window (Sticky Header, Mode Badge, Pause/Resume)     |
|  - Dashboard View (Log d'activité, statut actif)            |
|  - Actions View (Explorateur des actions par mode)          |
|  - Grid View (Aperçu de la grille d'écran)                  |
|  - Settings Modal (Configuration et persistance TOML)       |
+------------------------------+------------------------------+
                               | Observe / Dispatch
                               v
+-------------------------------------------------------------+
|                  Gestionnaire d'État (State)                |
|                    (src/alfred/core/state.py)               |
|  - Mode courant (Normal, Special, Grid, custom)             |
|  - Notifications aux observateurs (Thread-safe)             |
|  - Journal d'historique des actions exécutées               |
+------------------------------+------------------------------+
                               ^
                               |
+------------------------------+------------------------------+
|            Moteur d'Interception Clavier (Hook)             |
|                    (src/alfred/core/hook.py)                |
|  - Intercepte les événements système bas-niveau (keyboard)  |
|  - Détecte la touche de bascule de mode spécial             |
|  - Supprime la frappe originale si une action est assignée  |
|  - Délègue au Moteur de Commandes en tâche asynchrone       |
+------------------------------+------------------------------+
                               |
                               v
+-------------------------------------------------------------+
|                 Moteur de Commandes (Engine)                |
|               (src/alfred/core/commands_engine.py)          |
|  - Séquenceur de commandes (sleep, hotkey, click, app...)   |
|  - Gestion des toggles d'état                               |
|  - Système de Grille Souris (src/alfred/core/grid.py)       |
|  - Déplacement Dynamique Curseur (src/alfred/core/move.py)  |
|  - Contrôle Windows API (src/alfred/core/mouse.py)          |
+-------------------------------------------------------------+
                               ^
                               | Charge / Sauvegarde
+-------------------------------------------------------------+
|               Configuration & Modèles de Données            |
|              (src/alfred/core/config.py & models.py)        |
|  - Charge les fichiers TOML (settings/*.toml)               |
|  - Valide les types et paramètres                           |
|  - Écrit les modifications apportées par l'utilisateur      |
+-------------------------------------------------------------+
```

## Modèle de Concurrence & Threads
- **Thread Principal (UI Loop)** : Exécute la boucle d'événements Tkinter / CustomTkinter.
- **Thread Hook (Keyboard)** : Géré par la bibliothèque `keyboard` pour intercepter sans latence les frappes clavier au niveau Windows.
- **Worker Threads (Actions Engine)** : Lorsqu'une action contenant des temporisations (`sleep`) ou des lancements de programmes externes est déclenchée, elle est exécutée dans un thread séparé afin de ne jamais bloquer le hook clavier ni geler l'interface graphique.
