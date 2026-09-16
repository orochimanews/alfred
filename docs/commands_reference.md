# Spécification des Commandes - Alfred

Ce document répertorie le schéma technique de chaque commande disponible dans `settings/actions/*.toml`.

---

### 1. `hotkey`
Simule la pression d'une combinaison de touches.
- **Paramètres** :
  - `keys` (`list[str]` ou `str`) : Exemples : `["ctrl", "t"]`, `["alt", "f4"]`, `"ctrl+shift+esc"`.
- **Exemple** :
  ```toml
  [[commands]]
  type = "hotkey"
  keys = ["ctrl", "t"]
  ```

---

### 2. `click`
Simule un clic souris (gauche, droit ou milieu) avec coordonnées optionnelles.
- **Paramètres** :
  - `button` (`str`, défaut `"left"`) : `"left"`, `"right"`, ou `"middle"`.
  - `x` (`int`, optionnel) : Déplace d'abord le curseur en X.
  - `y` (`int`, optionnel) : Déplace d'abord le curseur en Y.
  - `clicks` (`int`, défaut `1`) : Nombre de clics (2 pour double clic).
- **Exemple** :
  ```toml
  [[commands]]
  type = "click"
  button = "left"
  ```

---

### 3. `middle_click`
Raccourci pour un clic du bouton central (molette).
- **Paramètres** : aucun.

---

### 4. `jump`
Déplace instantanément le curseur de la souris.
- **Paramètres** :
  - `x` (`int`) : Position X en pixels.
  - `y` (`int`) : Position Y en pixels.
  - `relative` (`bool`, défaut `false`) : Si `true`, le déplacement est relatif à la position courante.
- **Exemple** :
  ```toml
  [[commands]]
  type = "jump"
  x = 960
  y = 540
  ```

---

### 5. `mode`
Change le mode actif d'Alfred.
- **Paramètres** :
  - `target` (`str`) : Nom du mode (`"normal"`, `"special"`, `"grid"`, etc.) ou `"toggle"`.
  - `toggle_with` (`str`, optionnel, défaut `"normal"`) : Mode de retour si toggle.

---

### 6. `mouse_speed`
Modifie la sensibilité/vitesse du curseur de la souris Windows (échelle standard 1-20).
- **Paramètres** :
  - `speed` (`int`, optionnel) : Valeur cible (ex: `18` pour rapide, `10` pour normal).
  - `toggle` (`bool`, optionnel) : Si `true`, alterne entre `speed` et la vitesse par défaut.
  - `step` (`int`, optionnel) : Incrément/décrément relatif.

---

### 7. `app`
Lance une application Windows ou un protocole URI.
- **Paramètres** :
  - `command` (`str`) : Chemin d'accès ou commande URI (ex: `"onenote:"`, `"notepad.exe"`, `"calc.exe"`, `"https://..."`).
  - `args` (`list[str]`, optionnel) : Arguments supplémentaires.

---

### 8. `sleep`
Suspend l'exécution pour une durée déterminée (en secondes).
- **Paramètres** :
  - `duration` (`float`) : Pause en secondes (ex: `0.1` = 100ms).

---

### 9. `text`
Saisit une chaîne de texte au clavier.
- **Paramètres** :
  - `content` (`str`) : Le texte à insérer.

---

### 10. `grid_cell`
Déplace le curseur au centre d'une case de la grille configurée dans `settings/grid.toml`.
- **Paramètres** :
  - `col` (`int`) : Colonne de la grille (0-indexed).
  - `row` (`int`) : Ligne de la grille (0-indexed).
