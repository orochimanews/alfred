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

## 3. Rapprochement vers les Bords (Edge Snap)

Une fonction paramétrable permet de rapprocher instantanément la souris très près du bord de l'écran en fonction de la cellule où se trouve actuellement le curseur :

- **Paramètres** :
  - `edge_snap_enabled` : Active ou désactive la fonction (défaut : `true`).
  - `edge_snap_key` : Touche de déclenchement (défaut : `"à"`, gère automatiquement `"à"`, `"0"` et `"num_0"`).
  - `edge_offset` (ou `steps`) : Distance en pixels par rapport au bord de l'écran (défaut : `10`).

- **Comportement géométrique** :
  - Si le curseur est dans une case touchant un coin (ex: `(0, 0)`), la souris saute à $(offset, offset)$ très près du coin haut-gauche.
  - Si le curseur est sur un bord médian (ex: `(1, 0)` en haut au milieu), la coordonnée verticale est plaquée à $offset$ tout en conservant la position horizontale au milieu.
  - Si le curseur est dans une case intérieure ne touchant aucun bord (ex: `(1, 1)` dans une grille 3x3), aucun déplacement n'est effectué.

