"""Gestionnaire de déplacement dynamique du curseur au clavier (MoveManager)."""

from __future__ import annotations
import math
import time
import threading
import logging
from typing import TYPE_CHECKING

from src.alfred.core.models import MoveConfig
from src.alfred.core.mouse import mouse as default_mouse

if TYPE_CHECKING:
    from src.alfred.core.state import StateManager
    from src.alfred.core.mouse import MouseController

logger = logging.getLogger(__name__)


def _compute_curve_factor(progress: float, curve: str) -> float:
    """Calcule le coefficient d'accélération (0.0 à 1.0) selon la courbe choisie."""
    p = min(1.0, max(0.0, progress))
    match curve:
        case "linear":
            return p
        case "ease_in":
            return p * p
        case "ease_out":
            return math.sin(p * (math.pi / 2.0))
        case "ease_in_out":
            return 0.5 * (1.0 - math.cos(p * math.pi))
        case _:
            return 0.5 * (1.0 - math.cos(p * math.pi))


def _matches_key(key_name: str, allowed_keys: set[str]) -> bool:
    """Vérifie si key_name correspond à l'une des touches autorisées.
    Respecte la sensibilité à la casse pour les lettres simples (ex: 'q' != 'Q').
    """
    raw = key_name.strip()
    if raw in allowed_keys:
        return True
    if not (len(raw) == 1 and raw.isalpha()):
        return raw.lower() in {k.lower() for k in allowed_keys}
    return False


class MoveManager:
    """Contrôleur de déplacement fluide et dynamique du curseur au clavier."""

    def __init__(
        self,
        config: MoveConfig,
        mouse_controller: MouseController | None = None,
        state_manager: StateManager | None = None,
    ) -> None:
        self.config = config
        self.mouse = mouse_controller or default_mouse
        self.state_manager = state_manager

        self._lock = threading.RLock()
        self._active_directions: set[str] = set()
        self._is_boosted: bool = bool(config.start_boosted)
        self._is_grid_active: bool = False

        self._move_start_time: float = 0.0
        self._subpixel_x: float = 0.0
        self._subpixel_y: float = 0.0

        self._stop_event = threading.Event()
        self._movement_event = threading.Event()

        # Démarrage du thread worker d'arrière-plan cadencé à 60 FPS
        self._worker_thread = threading.Thread(
            target=self._worker_loop,
            daemon=True,
            name="Alfred-DynamicMoveWorker",
        )
        self._worker_thread.start()

    def update_config(self, new_config: MoveConfig) -> None:
        """Met à jour dynamiquement la configuration du déplacement."""
        with self._lock:
            self.config = new_config

    @property
    def is_boosted(self) -> bool:
        """Indique si la vitesse boostée est actuellement active."""
        with self._lock:
            return self._is_boosted

    def toggle_boost(self) -> bool:
        """Bascule l'état du boost de vitesse (Turbo) et journalise l'événement."""
        with self._lock:
            self._is_boosted = not self._is_boosted
            state = self._is_boosted

        logger.info("Mode Boost déplacement : %s", "ACTIF (x%.1f)" % self.config.boost_multiplier if state else "INACTIF (Normal)")
        if self.state_manager:
            current_mode = self.state_manager.current_mode
            self.state_manager.add_log(
                action_name=f"Vitesse Curseur Boost ({'Actif' if state else 'Normal'})",
                trigger_key=self.config.boost_toggle_key,
                mode=current_mode,
                status="success",
                details=f"Multiplicateur: x{self.config.boost_multiplier if state else 1.0}",
            )
        return state

    def set_boost(self, enabled: bool) -> None:
        """Définit explicitement l'état du boost."""
        with self._lock:
            self._is_boosted = bool(enabled)

    @property
    def is_grid_active(self) -> bool:
        """Indique si le pavé numérique est actuellement en mode grille."""
        with self._lock:
            return self._is_grid_active

    def toggle_grid(self) -> bool:
        """Bascule le pavé numérique entre déplacement dynamique et grille 3x3."""
        with self._lock:
            self._is_grid_active = not self._is_grid_active
            state = self._is_grid_active

        self.stop_all_movement()
        logger.info("Grille Pavé Numérique (Move Grid) : %s", "ACTIF (3x3)" if state else "INACTIF (Déplacement normal)")
        if self.state_manager:
            current_mode = self.state_manager.current_mode
            self.state_manager.add_log(
                action_name=f"Grille Pavé Numérique ({'Actif' if state else 'Inactif'})",
                trigger_key=self.config.grid_toggle_key,
                mode=current_mode,
                status="success",
                details="Grille 3x3 active [7..9, 4..6, 1..3]" if state else "Retour déplacement curseur",
            )
        return state

    def set_grid_active(self, enabled: bool) -> None:
        """Définit explicitement l'état de la grille sur pavé numérique."""
        with self._lock:
            self._is_grid_active = bool(enabled)
        self.stop_all_movement()

    def is_grid_toggle_key(self, key_name: str) -> bool:
        """Vérifie si une touche correspond à la bascule vers la grille pavé numérique."""
        if not self.config.enabled or not self.config.grid_enabled:
            return False
        return _matches_key(key_name, self.config.keys_grid_toggle)

    def is_grid_cell_key(self, key_name: str) -> bool:
        """Vérifie si une touche correspond à une case de la grille pavé numérique."""
        if not self.config.enabled or not self.config.grid_enabled:
            return False
        raw = key_name.strip()
        if raw in self.config.grid_cells:
            return True
        if not (len(raw) == 1 and raw.isalpha()):
            return raw.lower() in {k.lower(): v for k, v in self.config.grid_cells.items()}
        return False

    def get_grid_cell_center(
        self,
        col: int,
        row: int,
        screen_width: int | None = None,
        screen_height: int | None = None
    ) -> tuple[int, int]:
        """Calcule les coordonnées exactes (x, y) du centre de la case (col, row) pour une grille 3x3."""
        if screen_width is None or screen_height is None:
            screen_width, screen_height = self.mouse.get_screen_size()

        cols, rows = 3, 3
        col = max(0, min(cols - 1, col))
        row = max(0, min(rows - 1, row))

        cell_w = screen_width / cols
        cell_h = screen_height / rows

        center_x = int((col + 0.5) * cell_w)
        center_y = int((row + 0.5) * cell_h)

        return (center_x, center_y)

    def jump_grid_cell(self, col: int, row: int, trigger_key: str = "") -> tuple[int, int]:
        """Déplace le curseur au centre de la case (col, row) et journalise l'action."""
        cx, cy = self.get_grid_cell_center(col, row)
        self.mouse.set_position(cx, cy)
        logger.info("Grille Pavé Numérique : Saut à la case [%d, %d] -> (%d, %d)", col, row, cx, cy)

        if self.state_manager:
            current_mode = self.state_manager.current_mode
            self.state_manager.add_log(
                action_name=f"Saut Grille Pavé [{col}, {row}]",
                trigger_key=trigger_key or f"{col},{row}",
                mode=current_mode,
                status="success",
                details=f"Centre case : ({cx}, {cy})",
            )

        if self.config.grid_exit_after_jump:
            self.set_grid_active(False)

        return (cx, cy)

    def jump_grid_by_key(self, key_name: str) -> tuple[int, int] | None:
        """Si la touche correspond à une case de grille configurée, saute sur cette case."""
        if not self.config.enabled or not self.config.grid_enabled:
            return None
        raw = key_name.strip()
        coords = self.config.grid_cells.get(raw)
        if coords is None and not (len(raw) == 1 and raw.isalpha()):
            lower_map = {k.lower(): v for k, v in self.config.grid_cells.items()}
            coords = lower_map.get(raw.lower())
        if coords is not None:
            col, row = coords
            return self.jump_grid_cell(col, row, trigger_key=key_name)
        return None

    def is_edge_snap_key(self, key_name: str) -> bool:
        """Indique si la touche déclenche le rapprochement vers le bord de l'écran."""
        if not self.config.enabled or not self.config.edge_snap_enabled:
            return False
        return _matches_key(key_name, self.config.edge_snap_keys)

    def calculate_edge_snap(
        self,
        x: int,
        y: int,
        screen_width: int | None = None,
        screen_height: int | None = None,
        offset: int | None = None,
    ) -> tuple[int, int] | None:
        """Calcule les nouvelles coordonnées (x, y) plaquées vers le ou les bords de l'écran.

        Retourne None si la position actuelle du curseur ne touche aucun bord (zone centrale).
        """
        if screen_width is None or screen_height is None:
            screen_width, screen_height = self.mouse.get_screen_size()

        cols, rows = 3, 3
        cell_w = screen_width / cols
        cell_h = screen_height / rows

        col = max(0, min(cols - 1, int(x / cell_w)))
        row = max(0, min(rows - 1, int(y / cell_h)))

        d = max(0, self.config.edge_offset if offset is None else offset)
        new_x = x
        new_y = y
        snapped = False

        # Axe horizontal (gauche / droite)
        if col == 0:
            new_x = min(screen_width - 1, d)
            snapped = True
        elif col == cols - 1:
            new_x = max(0, screen_width - 1 - d)
            snapped = True

        # Axe vertical (haut / bas)
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
        """Déplace la souris très proche du bord selon la zone actuelle du curseur."""
        cur_x, cur_y = self.mouse.get_position()
        coords = self.calculate_edge_snap(cur_x, cur_y, offset=offset)
        if coords is not None:
            nx, ny = coords
            self.mouse.set_position(nx, ny)
            effective_offset = self.config.edge_offset if offset is None else offset
            logger.info(
                "Déplacement Move : Rapprochement bord depuis (%d, %d) vers (%d, %d) [offset=%d px]",
                cur_x, cur_y, nx, ny, effective_offset
            )
            return (nx, ny)
        logger.debug("Déplacement Move : Curseur à (%d, %d) hors des zones de bord, aucun saut.", cur_x, cur_y)
        return None

    def is_boost_key(self, key_name: str) -> bool:
        """Vérifie si une touche correspond au raccourci de bascule boost."""
        if not self.config.boost_enabled:
            return False
        return _matches_key(key_name, self.config.keys_boost)

    def is_move_key(self, key_name: str) -> bool:
        """Vérifie si une touche correspond à l'une des directions de déplacement."""
        if not self.config.enabled:
            return False
        return _matches_key(key_name, self.config.all_move_keys)

    def get_directions_for_key(self, key_name: str) -> set[str]:
        """Retourne l'ensemble des directions cardinales activées par une touche."""
        dirs: set[str] = set()

        if _matches_key(key_name, self.config.keys_up):
            dirs.add("up")
        if _matches_key(key_name, self.config.keys_down):
            dirs.add("down")
        if _matches_key(key_name, self.config.keys_left):
            dirs.add("left")
        if _matches_key(key_name, self.config.keys_right):
            dirs.add("right")

        if _matches_key(key_name, self.config.keys_up_left):
            dirs.update(["up", "left"])
        if _matches_key(key_name, self.config.keys_up_right):
            dirs.update(["up", "right"])
        if _matches_key(key_name, self.config.keys_down_left):
            dirs.update(["down", "left"])
        if _matches_key(key_name, self.config.keys_down_right):
            dirs.update(["down", "right"])

        return dirs

    def press_key(self, key_name: str) -> bool:
        """Déclenche la prise en compte de l'appui sur une touche de déplacement."""
        dirs = self.get_directions_for_key(key_name)
        if not dirs:
            return False

        with self._lock:
            if not self._active_directions:
                self._move_start_time = time.perf_counter()
                self._subpixel_x = 0.0
                self._subpixel_y = 0.0
            self._active_directions.update(dirs)
            self._movement_event.set()

        return True

    def release_key(self, key_name: str) -> bool:
        """Déclenche le relâchement d'une touche de déplacement."""
        dirs = self.get_directions_for_key(key_name)
        if not dirs:
            return False

        with self._lock:
            self._active_directions.difference_update(dirs)
            if not self._active_directions:
                self._movement_event.clear()
                self._move_start_time = 0.0
                self._subpixel_x = 0.0
                self._subpixel_y = 0.0

        return True

    def stop_all_movement(self) -> None:
        """Arrête immédiatement tout mouvement en cours."""
        with self._lock:
            self._active_directions.clear()
            self._movement_event.clear()
            self._move_start_time = 0.0
            self._subpixel_x = 0.0
            self._subpixel_y = 0.0

    def stop(self) -> None:
        """Arrête définitivement le worker de déplacement."""
        self._stop_event.set()
        self._movement_event.set()
        if self._worker_thread.is_alive():
            self._worker_thread.join(timeout=0.5)

    def _worker_loop(self) -> None:
        """Boucle d'exécution continue à haute fréquence (60 FPS)."""
        logger.debug("Démarrage du worker de déplacement dynamique.")
        last_tick = time.perf_counter()

        while not self._stop_event.is_set():
            # Attente passive quand aucun déplacement n'est demandé
            self._movement_event.wait(timeout=0.1)
            if self._stop_event.is_set():
                break

            now = time.perf_counter()
            last_tick = now

            while not self._stop_event.is_set():
                with self._lock:
                    if not self._active_directions:
                        self._movement_event.clear()
                        break
                    active_dirs = set(self._active_directions)
                    start_time = self._move_start_time
                    cfg = self.config
                    is_boost = self._is_boosted

                now = time.perf_counter()
                dt = min(now - last_tick, 0.05)
                last_tick = now

                # 1. Calcul du vecteur de direction brut
                vx = 0
                vy = 0
                if "up" in active_dirs:
                    vy -= 1
                if "down" in active_dirs:
                    vy += 1
                if "left" in active_dirs:
                    vx -= 1
                if "right" in active_dirs:
                    vx += 1

                if vx == 0 and vy == 0:
                    with self._lock:
                        self._movement_event.clear()
                    break

                # 2. Ratio horizontal/vertical pour les diagonales (ajustement écrans larges)
                # Le ratio s'applique uniquement quand les deux axes sont actifs simultanément.
                ratio = cfg.diagonal_ratio if (vx != 0 and vy != 0) else 1.0
                rx = vx * ratio
                ry = vy

                # Normalisation vectorielle (conserve une vitesse constante quelle que soit la direction)
                length = math.hypot(rx, ry)
                nx = rx / length
                ny = ry / length

                # 3. Calcul de la vitesse dynamique avec accélération
                if cfg.acceleration_enabled and cfg.acceleration_time > 0:
                    elapsed = max(0.0, now - start_time)
                    progress = min(1.0, elapsed / cfg.acceleration_time)
                    factor = _compute_curve_factor(progress, cfg.curve)
                    current_speed = cfg.initial_speed + (cfg.max_speed - cfg.initial_speed) * factor
                else:
                    current_speed = cfg.initial_speed

                # 4. Multiplicateur boost
                if is_boost:
                    current_speed *= cfg.boost_multiplier

                # 5. Déplacement physique avec accumulateur sous-pixel
                step_x = nx * current_speed * dt
                step_y = ny * current_speed * dt

                with self._lock:
                    self._subpixel_x += step_x
                    self._subpixel_y += step_y
                    move_x = int(self._subpixel_x)
                    move_y = int(self._subpixel_y)
                    self._subpixel_x -= move_x
                    self._subpixel_y -= move_y

                if move_x != 0 or move_y != 0:
                    try:
                        self.mouse.move_relative(move_x, move_y)
                    except Exception as err:
                        logger.error("Erreur lors du déplacement souris : %s", err)

                # Cadencement précis
                sleep_sec = max(0.002, (cfg.update_interval_ms / 1000.0) - (time.perf_counter() - now))
                time.sleep(sleep_sec)

        logger.debug("Arrêt du worker de déplacement dynamique.")
