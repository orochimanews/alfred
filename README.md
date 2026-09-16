# ⚡ Alfred — Raccourcis Clavier à Modes & Grille d'Écran

**Alfred** est un outil de productivité pour Windows conçu pour transformer votre clavier en une télécommande ultra-rapide grâce à un système de **modes** (ex: Normal, Spécial, Grille).

Une simple touche (par défaut `!`) vous permet de basculer en **Mode Spécial**, dans lequel le comportement des touches est intercepté et substitué par des commandes avancées (combinaisons de touches, clics de souris, navigation par grille, changement de vitesse du curseur, ouverture de programmes comme OneNote, macros temporisées).

---

## 🚀 Fonctionnalités Clés

- **Système de Modes Clavier** :
  - **Mode Normal** : Le clavier fonctionne exactement comme d'habitude.
  - **Mode Spécial** (activable via `!` par défaut) : Intercepte les touches choisies et exécute vos actions sans taper de texte intempestif.
  - **Mode Grille** : Découpe votre écran en une grille de cases (ex: 3x3). Chaque case est liée à une touche (AZERTY ou pavé numérique) pour téléporter instantanément le curseur au centre.
  - Possibilité de créer vos propres modes et de définir des actions actives dans un ou plusieurs modes (ou même en mode normal).
- **Catalogue de Commandes Riches** (`settings/commands.toml`) :
  - `hotkey` : `ctrl+t`, `alt+f4`, etc.
  - `click` & `middle_click` : Clic gauche, droit, molette centrale, double-clics.
  - `jump` : Déplacement instantané du curseur à des coordonnées absolues ou relatives.
  - `mode` : Changement de mode ou toggle.
  - `mouse_speed` : Accélération/ralentissement de la vitesse du curseur ou toggle rapide/normal.
  - `app` : Lancement ou activation d'applications Windows (`onenote:`, chemins d'accès).
  - `sleep` : Pause temporelle pour créer des macros multi-étapes précises.
  - `text` : Saisie automatique de texte.
- **Actions Toggle Multi-États** : Définissez une action qui alterne entre plusieurs états successifs à chaque appui de touche.
- **Notice des Touches AZERTY / Anglais** (`settings/keys.toml`) : Dictionnaire complet des noms de touches.
- **Interface Ergonomique CustomTkinter** :
  - Menu supérieur *sticky* toujours accessible.
  - Affichage en temps réel du mode actif avec badge interactif.
  - Historique en direct des dernières actions exécutées.
  - Fenêtre modale des paramètres permettant de changer la touche spéciale, la taille de police (10-18px), le thème (Sombre / Clair) avec sauvegarde automatique dans `settings/config.toml`.
  - Bouton pause/reprise de l'interception et rechargement à chaud des configurations TOML.

---

## 📦 Installation & Prérequis

### Prérequis
- **Windows** (10 ou 11)
- **UV** (gestionnaire ultra-rapide de dépendances Python) :
  ```cmd
  powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
  ```
- **Python 3.11+** (UV gère automatiquement la version si besoin)

### Installation
Clonez ou ouvrez le dossier du projet :
```cmd
cd c:\dive\alfred
uv sync
```

---

## 🎮 Lancement & Utilisation

### En mode Développement
Double-cliquez sur `dev.bat` ou lancez en ligne de commande :
```cmd
dev.bat
# ou directement :
uv run python main.py
```

Pour lancer en tâche de fond sans interface graphique :
```cmd
uv run python main.py --headless
```

### Utilisation Quotidienne
1. Dès le lancement, Alfred démarre en mode **Normal** et intercepte en arrière-plan la touche de mode spécial.
2. Appuyez sur la touche `!` :
   - Le badge passe en orange vif : **MODE SPÉCIAL**.
   - Vous pouvez maintenant utiliser les raccourcis configurés :
     - `t` : Ouvre un nouvel onglet de navigateur (`Ctrl+T`)
     - `o` : Lance Microsoft OneNote
     - `Espace` : Clic gauche
     - `m` : Clic molette (milieu)
     - `v` : Bascule la vitesse de la souris (Rapide / Normal)
     - `j` : Téléporte le curseur au centre de l'écran
     - `f` : Macro de recherche web rapide (Ctrl+T + pause + écriture URL + Entrée)
     - `g` : Bascule en **Mode Grille**
3. En **Mode Grille** :
   - Les touches `a`, `z`, `e`, `q`, `s`, `d`, `w`, `x`, `c` téléportent immédiatement le curseur dans l'une des 9 zones de l'écran !
4. Réappuyez sur `!` pour revenir immédiatement en **Mode Normal**.

---

## ⚙️ Configuration & Personnalisation

Tous les paramètres d'Alfred sont des fichiers lisibles au format **TOML** situés dans le dossier `settings/` :

```
settings/
├── config.toml            # Touche spéciale, mode par défaut, thème, police
├── commands.toml          # Notice technique de toutes les commandes
├── keys.toml              # Notice des noms de touches AZERTY / anglais
├── grid.toml              # Grille d'écran (lignes, colonnes, touches de cases)
└── actions/               # Définition des actions utilisateur
    ├── browser_new_tab.toml
    ├── onenote_open.toml
    ├── mouse_click_left.toml
    ├── mouse_middle_click.toml
    ├── mouse_speed_toggle.toml
    ├── cursor_jump_center.toml
    ├── mode_grid_switch.toml
    └── ...
```

### Créer une Nouvelle Action
Créez simplement un nouveau fichier `.toml` dans `settings/actions/` (par exemple `mon_action.toml`) :
```toml
name = "Sauvegarder et Fermer"
description = "Envoie Ctrl+S puis Alt+F4"
modes = ["special"]
trigger = "k"

[[commands]]
type = "hotkey"
keys = ["ctrl", "s"]

[[commands]]
type = "sleep"
duration = 0.2

[[commands]]
type = "hotkey"
keys = ["alt", "f4"]
```
Cliquez sur le bouton **🔄** dans le menu d'Alfred pour recharger la configuration à chaud sans redémarrer !

---

## 🔨 Compilation du Binaire Autonome (.exe)

Pour générer un fichier `.exe` autonome fonctionnant sur n'importe quel PC Windows sans Python :
```cmd
build.bat
```
L'exécutable autonome est produit dans `dist\Alfred\Alfred.exe` avec son dossier `settings/` modifiable à côté.

---

## 🧪 Tests Automatisés

Pour vérifier la conformité du code et des configurations :
```cmd
uv run pytest
```
