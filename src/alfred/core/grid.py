"""Sous-système de calcul et navigation par grille d'écran (Grid System)."""

from __future__ import annotations
import logging
from typing import TYPE_CHECKING

from src.alfred.core.models import GridConfig
from src.alfred.core.mouse import mouse

if TYPE_CHECKING:
    from src.alfred.core.state import StateManager

logger = logging.getLogger(__name__)


class GridManager:
    """Gère la géométrie de la grille d'écran et l'acheminement du curseur vers chaque cellule."""

    def __init__(self, config: GridConfig, state_manager: StateManager | None = None) -> None:
        self.config = config
        self.state_manager = state_manager

    def update_config(self, new_config: GridConfig) -> None:
        """Met à jour la configuration de la grille."""
        self.config = new_config

    def get_cell_center(self, col: int, row: int, screen_width: int | None = None, screen_height: int | None = None) -> tuple[int, int]:
        """Calcule les coordonnées exactes (x, y) du centre de la case (col, row)."""
        if screen_width is None or screen_height is None:
            screen_width, screen_height = mouse.get_screen_size()

        cols = max(1, self.config.columns)
        rows = max(1, self.config.rows)

        col = max(0, min(cols - 1, col))
        row = max(0, min(rows - 1, row))

        cell_w = screen_width / cols
        cell_h = screen_height / rows

        center_x = int((col + 0.5) * cell_w)
        center_y = int((row + 0.5) * cell_h)

        return (center_x, center_y)

    def jump_to_cell(self, col: int, row: int) -> tuple[int, int]:
        """Déplace le curseur au centre de la case et effectue les actions associées."""
        cx, cy = self.get_cell_center(col, row)
        mouse.set_position(cx, cy)
        logger.info("Grille : Saut à la case [%d, %d] -> coordonnées (%d, %d)", col, row, cx, cy)

        if self.config.auto_click:
            mouse.click("left")

        if self.config.exit_mode_after_jump and self.state_manager:
            self.state_manager.set_mode(self.state_manager.previous_mode or "normal")

        return (cx, cy)

    def jump_by_key(self, key_name: str) -> tuple[int, int] | None:
        """Si la touche correspond à une case configurée, saute sur cette case."""
        clean_key = key_name.lower().strip()
        coords = self.config.cells.get(clean_key)
        if coords is not None:
            col, row = coords
            return self.jump_to_cell(col, row)
        return None

    def is_grid_key(self, key_name: str) -> bool:
        """Indique si la touche est assignée à une case de la grille."""
        return key_name.lower().strip() in self.config.cells

    def is_edge_snap_key(self, key_name: str) -> bool:
        """Indique si la touche déclenche le rapprochement vers le bord."""
        if not self.config.edge_snap_enabled:
            return False
        return key_name.lower().strip() in self.config.edge_snap_keys

    def get_cell_at_position(
        self,
        x: int,
        y: int,
        screen_width: int | None = None,
        screen_height: int | None = None
    ) -> tuple[int, int]:
        """Détermine la cellule (col, row) contenant les coordonnées (x, y)."""
        if screen_width is None or screen_height is None:
            screen_width, screen_height = mouse.get_screen_size()

        cols = max(1, self.config.columns)
        rows = max(1, self.config.rows)

        cell_w = screen_width / cols
        cell_h = screen_height / rows

        col = max(0, min(cols - 1, int(x / cell_w)))
        row = max(0, min(rows - 1, int(y / cell_h)))
        return (col, row)

    def calculate_edge_snap(
        self,
        x: int,
        y: int,
        screen_width: int | None = None,
        screen_height: int | None = None,
        offset: int | None = None,
    ) -> tuple[int, int] | None:
        """Calcule les nouvelles coordonnées (x, y) plaquées vers le ou les bords de l'écran.

        Retourne None si la case actuelle du curseur ne touche aucun bord.
        """
        if screen_width is None or screen_height is None:
            screen_width, screen_height = mouse.get_screen_size()

        cols = max(1, self.config.columns)
        rows = max(1, self.config.rows)
        col, row = self.get_cell_at_position(x, y, screen_width, screen_height)

        d = max(0, self.config.edge_offset if offset is None else offset)
        new_x = x
        new_y = y
        snapped = False

        # Axe horizontal (gauche / droite)
        if cols > 1:
            if col == 0:
                new_x = min(screen_width - 1, d)
                snapped = True
            elif col == cols - 1:
                new_x = max(0, screen_width - 1 - d)
                snapped = True

        # Axe vertical (haut / bas)
        if rows > 1:
            if row == 0:
                new_y = min(screen_height - 1, d)
                snapped = True
            elif row == rows - 1:
                new_y = max(0, screen_height - 1 - d)
                snapped = True

        if not snapped:
            return None

        return (new_x, new_y)

    def snap_to_edge(self, offset: int | None = None) -> tuple[int, int] | None:
        """Déplace la souris très proche du bord selon la case actuelle du curseur."""
        cur_x, cur_y = mouse.get_position()
        coords = self.calculate_edge_snap(cur_x, cur_y, offset=offset)
        if coords is not None:
            nx, ny = coords
            mouse.set_position(nx, ny)
            logger.info(
                "Grille : Rapprochement bord depuis (%d, %d) vers (%d, %d) [offset=%d px]",
                cur_x, cur_y, nx, ny, self.config.edge_offset if offset is None else offset
            )
            return (nx, ny)
        logger.debug("Grille : Curseur à (%d, %d) hors des cases de bord, aucun saut.", cur_x, cur_y)
        return None

    def get_all_cells_preview(self) -> list[dict[str, int | str]]:
        """Génère la liste de toutes les cellules avec leurs touches et centres pour l'UI."""
        w, h = mouse.get_screen_size()
        items = []
        for key, (col, row) in self.config.cells.items():
            cx, cy = self.get_cell_center(col, row, w, h)
            items.append({
                "key": key,
                "col": col,
                "row": row,
                "cx": cx,
                "cy": cy,
            })
        return items
