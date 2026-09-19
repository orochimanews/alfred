# Spécification des Commandes - Alfred

Ce document répertorie le schéma technique de chaque commande disponible dans les actions (`settings/actions/*.toml`).

## Syntaxes d'Écriture des Commandes

Une action peut structurer sa liste de commandes selon deux styles :

### 1. Style ARRAY (Recommandé - clair et compact)
```toml
commands = [
    { type = "hotkey", params = ["ctrl", "t"] },
    { type = "sleep", params = [0.15] },
    { type = "jump", params = [960, 540] },
    { type = "click", params = ["left", 1] },
    { type = "mouse_speed", params = [18, true] }
]
```

### 2. Style avec Clés Nommées ou Blocs `[[commands]]`
```toml
commands = [
    { type = "hotkey", keys = ["ctrl", "t"] },
    { type = "jump", x = 960, y = 540 }
]
```

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
  - `command` (`str`) : Nom de l'application (ex: `"onenote"`, `"notepad.exe"`, `"calc"`), URI ou lien (ex: `"ms-settings:"`, `"https://..."`).
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

---

### 11. `mouse_nudge`
Active ou bascule le mode Nudge : les déplacements physiques de la souris ou du trackpad sont amplifiés par bonds directionnels de `step` pixels. Idéal pour traverser de grands écrans rapidement au trackpad.
- **Paramètres** :
  - `step` (`int`, défaut: `120`) : Distance en pixels du bond directionnel (ex: `150`).
  - `toggle` (`bool`, défaut: `true`) : Bascule l'état on/off.
  - `threshold` (`int`, défaut: `4`) : Seuil de mouvement physique minimal en pixels.
  - `cooldown` (`float`, défaut: `0.08`) : Délai minimal en secondes entre deux bonds.

---

### 12. `move_boost`
Bascule ou modifie l'état de boost (vitesse rapide / turbo) pour les déplacements curseur au clavier configurés dans `settings/move.toml`.
- **Paramètres** :
  - `toggle` (`bool`, défaut: `true`) : Alterne l'activation du boost.
  - `active` (`bool`, optionnel) : Définit explicitement l'état actif ou inactif du boost.
- **Exemple** :
  ```toml
  [[commands]]
  type = "move_boost"
  toggle = true
  ```

