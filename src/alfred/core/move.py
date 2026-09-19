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

    def is_boost_key(self, key_name: str) -> bool:
        """Vérifie si une touche correspond au raccourci de bascule boost."""
        if not self.config.boost_enabled:
            return False
        k = key_name.lower().strip()
        return k in self.config.keys_boost

    def is_move_key(self, key_name: str) -> bool:
        """Vérifie si une touche correspond à l'une des directions de déplacement."""
        if not self.config.enabled:
            return False
        k = key_name.lower().strip()
        return k in self.config.all_move_keys

    def get_directions_for_key(self, key_name: str) -> set[str]:
        """Retourne l'ensemble des directions cardinales activées par une touche."""
        k = key_name.lower().strip()
        dirs: set[str] = set()

        if k in self.config.keys_up:
            dirs.add("up")
        if k in self.config.keys_down:
            dirs.add("down")
        if k in self.config.keys_left:
            dirs.add("left")
        if k in self.config.keys_right:
            dirs.add("right")

        if k in self.config.keys_up_left:
            dirs.update(["up", "left"])
        if k in self.config.keys_up_right:
            dirs.update(["up", "right"])
        if k in self.config.keys_down_left:
            dirs.update(["down", "left"])
        if k in self.config.keys_down_right:
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

                # 2. Normalisation vectorielle (diagonales fluides)
                length = math.hypot(vx, vy)
                nx = vx / length
                ny = vy / length

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
