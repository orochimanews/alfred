# Système de Grille Souris - Alfred

Le module de grille d'écran permet de contrôler et cibler n'importe quelle zone de l'affichage sans avoir à manipuler la souris ou le trackpad physique.

## 1. Principe de Découpage

L'écran principal (ou zone de travail active) de résolution $W \times H$ est partitionné en une matrice de $C$ colonnes et $R$ lignes ($C \times R$ cases rectangulaires).

Pour une case située à la colonne $c \in [0, C-1]$ et à la ligne $r \in [0, R-1]$ :
- Largeur d'une case : $W_{\text{cell}} = \frac{W}{C}$
- Hauteur d'une case : $H_{\text{cell}} = \frac{H}{R}$
- Coordonnées du centre :
  $$X_c = \left(c + 0.5\right) \times W_{\text{cell}}$$
  $$Y_r = \left(r + 0.5\right) \times H_{\text{cell}}$$

## 2. Configuration (`settings/grid.toml`)
- `columns` : Nombre de subdivisions horizontales (ex: 3).
- `rows` : Nombre de subdivisions verticales (ex: 3).
- `active_modes` : Liste des modes où la grille réagit (ex: `["grid", "special"]`).
- `exit_mode_after_jump` : Si `true`, quitte automatiquement le mode grille après avoir sauté sur la case pour revenir au mode normal ou précédent.
- `auto_click` : Si `true`, effectue un clic gauche dès l'arrivée sur la case ciblée.
- `[cells]` : Dictionnaire associant chaque touche à un doublet `[colonne, ligne]`.

Exemple :
```toml
[grid]
columns = 3
rows = 3
active_modes = ["grid"]

[cells]
a = [0, 0] # Haut-gauche
z = [1, 0] # Haut-milieu
e = [2, 0] # Haut-droite
q = [0, 1] # Centre-gauche
s = [1, 1] # Centre exact
d = [2, 1] # Centre-droite
w = [0, 2] # Bas-gauche
x = [1, 2] # Bas-milieu
c = [2, 2] # Bas-droite
```
