# Guide de l'Agent de Développement - Alfred

Ce document est le point d'entrée principal pour tout agent d'IA ou développeur travaillant sur le projet **Alfred**.
Il synthétise l'architecture, les conventions, le workflow et les liens vers la documentation approfondie dans `docs/`.

---

## 1. Vue d'ensemble du Projet

**Alfred** est un utilitaire système Windows permettant d'étendre la productivité au clavier via un système de **modes** (ex: Normal, Spécial, Grille).
Une touche paramétrable (par exemple `!`) permet de basculer du mode normal vers un mode spécial dans lequel les frappes clavier sont interceptées et remplacées par des commandes riches (actions hotkey, clics souris, déplacement vers une grille d'écran, changement de vitesse curseur, lancement d'applications, etc.).

### Objectifs d'Ingénierie
- **Modulaire et découplé** : Séparation stricte entre le moteur de hook bas-niveau, la gestion d'état, l'interpréteur de commandes et l'interface utilisateur.
- **Configurable par fichiers TOML** : Tout le comportement est défini dans le dossier `settings/`.
- **Agnostique & Remplaçable** : Aucune dépendance matérielle ou d'interface n'est couplée directement au cœur métier.
- **UI Ergonomique (CustomTkinter)** : Design sombre/clair compact, sticky header, accès rapide aux paramètres.

---

## 2. Structure du Dépôt

```
alfred/
├── .gitignore
├── AGENTS.md                  <-- Ce fichier (point d'entrée agent)
├── README.md                  <-- Guide pour l'utilisateur final
├── pyproject.toml             <-- Configuration uv / dépendances
├── dev.bat                    <-- Lancement en mode développement
├── build.bat                  <-- Compilation du binaire Windows autonome (.exe)
│
├── settings/                  <-- Fichiers de configuration utilisateur (TOML)
│   ├── config.toml            <-- Paramètres généraux (mode par défaut, trigger, UI)
│   ├── commands.toml          <-- Notice descriptive de toutes les commandes
│   ├── keys.toml              <-- Notice des noms de touches (AZERTY / Anglais)
│   ├── grid.toml              <-- Configuration de la grille écran (cases, touches)
│   └── actions/               <-- Actions individuelles configurables
│       ├── browser_new_tab.toml
│       ├── onenote_open.toml
│       ├── mouse_click_left.toml
│       ├── mouse_middle_click.toml
│       ├── mouse_speed_toggle.toml
│       ├── cursor_jump_center.toml
│       ├── mode_grid_switch.toml
│       ├── macro_search_example.toml
│       └── toggle_mode.toml
│
├── docs/                      <-- Documentation technique détaillée
│   ├── architecture.md        <-- Architecture des couches et flux de données
│   ├── conventions.md         <-- Règles de codage, typage, tests
│   ├── commands_reference.md  <-- Spécification des commandes d'actions
│   ├── grid_system.md         <-- Calculs géométriques et fonctionnement de la grille
│   ├── decisions.md           <-- Journal des décisions d'architecture (ADR)
│   └── tasks.md               <-- Roadmap et tâches futures
│
├── src/alfred/
│   ├── __init__.py
│   ├── main.py                <-- Point d'entrée de l'application
│   ├── core/                  <-- Cœur applicatif indépendant de l'UI
│   │   ├── config.py          <-- Chargeur et validateur TOML
│   │   ├── models.py          <-- Structures de données typées
│   │   ├── state.py           <-- Gestionnaire d'états et événements
│   │   ├── mouse.py           <-- Interaction Windows API (curseur, clics, vitesse)
│   │   ├── commands_engine.py <-- Moteur d'exécution des commandes et macros
│   │   ├── grid.py            <-- Calculateur de grille d'écran
│   │   └── hook.py            <-- Intercepteur clavier système (suppression & routing)
│   │
│   └── ui/                    <-- Interface graphique CustomTkinter
│       ├── app.py             <-- Fenêtre principale & sticky header
│       ├── theme.py           <-- Gestion dynamique du thème et de la taille de police
│       └── views/
│           ├── dashboard.py   <-- Vue d'accueil et historique des actions
│           ├── actions_view.py<-- Explorateur des actions par mode
│           ├── grid_view.py   <-- Vue interactive de la grille
│           └── settings_modal.py <-- Modal de personnalisation et sauvegarde TOML
│
└── tests/                     <-- Tests automatisés
    ├── test_config.py
    ├── test_models.py
    ├── test_state.py
    ├── test_grid.py
    └── test_commands.py
```

---

## 3. Références de Documentation

Avant toute modification importante ou résolution de problème complexe, consulte :
- [Architecture](docs/architecture.md) : Flux de communication inter-composants et thread model.
- [Conventions de code](docs/conventions.md) : Typage statique, docstrings, imports, gestion d'erreurs.
- [Référence des commandes](docs/commands_reference.md) : Spécification des paramètres de chaque commande.
- [Système de Grille](docs/grid_system.md) : Logique de partition d'écran et saut curseur.
- [Décisions Architecturales](docs/decisions.md) : Choix techniques (`keyboard`, ctypes `user32`, `CustomTkinter`).
- [Feuille de Route & Tâches](docs/tasks.md) : Historique des évolutions et items restants.

---

## 4. Outils et Commandes de Développement

Le projet s'appuie sur `uv` pour la gestion des paquets et l'exécution :
- **Lancer en dev** :
  ```cmd
  dev.bat
  # ou manuellement :
  uv run python -m src.alfred.main
  ```
- **Lancer les tests unitaires** :
  ```cmd
  uv run pytest
  ```
- **Compiler en exécutable Windows (.exe autonome)** :
  ```cmd
  build.bat
  ```

---

## 5. Règles pour l'Agent de Développement

1. **Privilégier la modularité** : Ne jamais intégrer du code d'interception système directement dans les widgets UI.
2. **Robustesse du Hook** : L'interception clavier ne doit pas bloquer le système en cas d'exception dans une commande. Toujours exécuter les actions de façon asynchrone dans un thread worker.
3. **Persistance TOML** : Toute modification effectuée dans la fenêtre des paramètres doit être enregistrée dans `settings/config.toml` sans corrompre les autres sections.
4. **Mises à jour Git** : Créer un commit à chaque jalon significatif.
