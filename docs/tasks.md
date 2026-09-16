# Suivi des Tâches - Alfred

## Phase 1 : Cœur Applicatif & Configuration (Terminé)
- [x] Initialisation du projet avec `uv` et `git`.
- [x] Spécification des notices de configuration : `commands.toml`, `keys.toml`.
- [x] Configuration globale et grille : `config.toml`, `grid.toml`.
- [x] Échantillons d'actions complètes : `settings/actions/*.toml`.
- [x] Documentation d'ingénierie : `AGENTS.md`, `docs/*.md`.

## Phase 2 : Moteur Système & Interception (En cours)
- [x] Modèles de données typés (`src/alfred/core/models.py`).
- [x] Chargeur et sérialiseur de configuration TOML (`src/alfred/core/config.py`).
- [x] Gestionnaire de souris et vitesse Windows (`src/alfred/core/mouse.py`).
- [x] Calculateur de grille d'écran (`src/alfred/core/grid.py`).
- [x] Exécuteur de commandes & actions (`src/alfred/core/commands_engine.py`).
- [x] Gestionnaire d'état (`src/alfred/core/state.py`).
- [x] Intercepteur de clavier global (`src/alfred/core/hook.py`).

## Phase 3 : Interface Graphique CustomTkinter
- [x] Thème dynamique et taille de police (`src/alfred/ui/theme.py`).
- [x] Fenêtre principale avec menu sticky (`src/alfred/ui/app.py`).
- [x] Dashboard avec statut en temps réel et journal d'activité.
- [x] Vue des actions enregistrées par mode.
- [x] Vue interactive de la grille.
- [x] Modal popup de configuration avec sauvegarde TOML.

## Phase 4 : Tests & Packaging Windows
- [x] Tests unitaires automatisés (`pytest`).
- [x] Scripts d'exécution et de build (`dev.bat`, `build.bat`).
- [x] Documentation utilisateur (`README.md`).
