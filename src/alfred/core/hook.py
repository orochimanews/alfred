"""Intercepteur global du clavier système (Keyboard Hook) pour Alfred."""

from __future__ import annotations
import threading
import logging
from typing import TYPE_CHECKING
import keyboard

if TYPE_CHECKING:
    from src.alfred.core.state import StateManager
    from src.alfred.core.config import ConfigManager
    from src.alfred.core.commands_engine import CommandsEngine
    from src.alfred.core.grid import GridManager

logger = logging.getLogger(__name__)


class KeyboardHookService:
    """Service d'interception et de routage des touches clavier."""

    def __init__(
        self,
        state_manager: StateManager,
        config_manager: ConfigManager,
        commands_engine: CommandsEngine,
        grid_manager: GridManager,
    ) -> None:
        self.state_manager = state_manager
        self.config_manager = config_manager
        self.commands_engine = commands_engine
        self.grid_manager = grid_manager
        self._hook_installed: bool = False
        self._pressed_keys: set[str] = set()

    def start(self) -> None:
        """Démarre l'écoute globale du clavier."""
        if self._hook_installed:
            return
        keyboard.hook(self._on_key_event, suppress=True)
        self._hook_installed = True
        logger.info("Hook clavier global installé avec succès.")

    def stop(self) -> None:
        """Arrête l'écoute du clavier."""
        if not self._hook_installed:
            return
        try:
            keyboard.unhook(self._on_key_event)
        except Exception:
            pass
        self._hook_installed = False
        logger.info("Hook clavier global désactivé.")

    def _on_key_event(self, event: keyboard.KeyboardEvent) -> bool:
        """Callback appelé pour chaque frappe système.
        Retourne False pour supprimer la touche (l'intercepter), True pour la laisser passer.
        """
        try:
            key_name = (event.name or "").lower().strip()
            if not key_name:
                return True

            # Si c'est un relâchement de touche, nettoyer les touches maintenues et laisser passer
            if event.event_type == keyboard.KEY_UP:
                self._pressed_keys.discard(key_name)
                return True

            # Événement KEY_DOWN
            # Éviter le spam des répétitions automatiques si la touche est déjà enfoncée
            is_repeat = key_name in self._pressed_keys
            self._pressed_keys.add(key_name)

            # Si le service est désactivé via le state manager, ne rien intercepter
            if not self.state_manager.is_hook_enabled:
                return True

            current_mode = self.state_manager.current_mode
            gen_cfg = self.config_manager.app_config.general
            special_key = gen_cfg.special_mode_key.lower().strip()

            # 1. Vérification de la touche de bascule vers le mode spécial (si configurée en dur)
            if special_key and key_name == special_key and not is_repeat:
                logger.debug("Touche de mode spécial détectée : '%s'", key_name)
                if gen_cfg.toggle_special_mode:
                    new_mode = self.state_manager.toggle_mode(gen_cfg.special_mode_name)
                else:
                    self.state_manager.set_mode(gen_cfg.special_mode_name)
                    new_mode = gen_cfg.special_mode_name

                self.state_manager.add_log(
                    action_name=f"Bascule vers mode '{new_mode}'",
                    trigger_key=key_name,
                    mode=current_mode,
                    status="success",
                )
                # Supprimer la touche pour éviter de taper le caractère spécial
                return False

            # 2. Vérification de la grille souris si le mode actif fait partie des active_modes
            grid_cfg = self.config_manager.grid_config
            if grid_cfg.enabled and (current_mode in grid_cfg.active_modes or "all" in grid_cfg.active_modes):
                # 2a. Touche de rapprochement du bord (edge snap)
                if self.grid_manager.is_edge_snap_key(key_name):
                    logger.debug("Touche de rapprochement bord grille détectée : '%s'", key_name)
                    threading.Thread(
                        target=self._execute_grid_edge_snap,
                        args=(key_name, current_mode),
                        daemon=True
                    ).start()
                    return False

                # 2b. Touche de cellule de grille
                if self.grid_manager.is_grid_key(key_name):
                    logger.debug("Touche de grille détectée : '%s'", key_name)
                    # Exécuter dans un thread séparé pour ne pas ralentir le hook système
                    threading.Thread(
                        target=self._execute_grid_jump,
                        args=(key_name, current_mode),
                        daemon=True
                    ).start()
                    return False

            # 3. Vérification des actions enregistrées pour le mode actif
            action = self.config_manager.get_action_for_key(key_name, current_mode)
            if action is not None:
                logger.debug("Action '%s' trouvée pour touche '%s' dans mode '%s'", action.name, key_name, current_mode)
                threading.Thread(
                    target=self.commands_engine.execute_action,
                    args=(action, key_name),
                    daemon=True
                ).start()
                return False

            # Si aucune règle ne s'applique, laisser la touche se propager normalement
            return True

        except Exception as err:
            logger.error("Erreur critique dans le hook clavier : %s", err, exc_info=True)
            # En cas d'erreur, ne jamais bloquer le clavier de l'utilisateur
            return True

    def _execute_grid_edge_snap(self, key_name: str, current_mode: str) -> None:
        """Exécute le rapprochement vers le bord de l'écran en arrière-plan."""
        try:
            coords = self.grid_manager.snap_to_edge()
            if coords:
                nx, ny = coords
                self.state_manager.add_log(
                    action_name=f"Bord Grille ({nx}, {ny})",
                    trigger_key=key_name,
                    mode=current_mode,
                    status="success",
                )
            else:
                self.state_manager.add_log(
                    action_name="Bord Grille (hors bord)",
                    trigger_key=key_name,
                    mode=current_mode,
                    status="ignored",
                )
        except Exception as err:
            logger.error("Erreur lors du rapprochement vers le bord pour la touche '%s': %s", key_name, err)

    def _execute_grid_jump(self, key_name: str, current_mode: str) -> None:
        """Exécute le saut de grille en arrière-plan."""
        try:
            coords = self.grid_manager.jump_by_key(key_name)
            if coords:
                cx, cy = coords
                self.state_manager.add_log(
                    action_name=f"Saut Grille ({cx}, {cy})",
                    trigger_key=key_name,
                    mode=current_mode,
                    status="success",
                )
        except Exception as err:
            logger.error("Erreur lors du saut de grille pour la touche '%s': %s", key_name, err)
