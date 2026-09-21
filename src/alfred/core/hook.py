"""Intercepteur global du clavier système (Keyboard Hook) pour Alfred."""

from __future__ import annotations
import sys
import threading
import logging
from typing import TYPE_CHECKING
import keyboard

if TYPE_CHECKING:
    from src.alfred.core.state import StateManager
    from src.alfred.core.config import ConfigManager
    from src.alfred.core.commands_engine import CommandsEngine
    from src.alfred.core.grid import GridManager
    from src.alfred.core.move import MoveManager

logger = logging.getLogger(__name__)


def _patch_keyboard_windows_listen() -> None:
    """Corrige le bug critique de pointeur NULL dans keyboard._winkeyboard.listen sous Windows.

    Par défaut, keyboard._winkeyboard fait 'msg = LPMSG()', ce qui passe un pointeur NULL
    à GetMessage(). Dès qu'un message système arrive dans la file du thread, une violation
    d'accès (Access Violation 0x00000008) survient et tue le thread d'écoute en silence.
    Ce patch alloue une structure MSG() valide et implémente la vraie boucle Win32.
    """
    if sys.platform != "win32":
        return

    try:
        from keyboard import _winkeyboard
        import ctypes
        from ctypes.wintypes import MSG

        def safe_listen(callback):
            _winkeyboard.prepare_intercept(callback)
            msg = MSG()
            p_msg = ctypes.byref(msg)
            # while GetMessage(...) > 0 : continue tant que WM_QUIT (0) ou une erreur (-1) n'arrive pas
            while _winkeyboard.GetMessage(p_msg, 0, 0, 0) > 0:
                _winkeyboard.TranslateMessage(p_msg)
                _winkeyboard.DispatchMessage(p_msg)

        _winkeyboard.listen = safe_listen
        logger.debug("Patch de sécurité appliqué à keyboard._winkeyboard.listen.")
    except Exception as err:
        logger.warning("Impossible de patcher keyboard._winkeyboard.listen : %s", err)


class KeyboardHookService:
    """Service d'interception et de routage des touches clavier."""

    def __init__(
        self,
        state_manager: StateManager,
        config_manager: ConfigManager,
        commands_engine: CommandsEngine,
        grid_manager: GridManager,
        move_manager: MoveManager | None = None,
    ) -> None:
        self.state_manager = state_manager
        self.config_manager = config_manager
        self.commands_engine = commands_engine
        self.grid_manager = grid_manager
        self.move_manager = move_manager
        self._hook_installed: bool = False
        self._pressed_keys: set[str] = set()

        # Surveiller les changements de mode pour couper les mouvements en cours si nécessaire
        self.state_manager.subscribe(self._on_state_event)

    def start(self) -> None:
        """Démarre l'écoute globale du clavier."""
        if self._hook_installed:
            return
        # Appliquer le patch Win32 avant d'installer le hook
        _patch_keyboard_windows_listen()
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

    def _on_state_event(self, event_type: str, data: any) -> None:
        """Surveille les changements de mode applicatif."""
        if event_type == "mode_changed" and self.move_manager:
            move_cfg = self.config_manager.move_config
            if data not in move_cfg.active_modes and "all" not in move_cfg.active_modes:
                self.move_manager.stop_all_movement()
                self.move_manager.set_grid_active(False)

    def _on_key_event(self, event: keyboard.KeyboardEvent) -> bool:
        """Callback appelé pour chaque frappe système.
        Retourne False pour supprimer la touche (l'intercepter), True pour la laisser passer.
        """
        try:
            key_name = (event.name or "").lower().strip()
            if not key_name:
                return True

            # Tolérance de saisie clavier pour AZERTY / verrouillage majuscule :
            # Sur AZERTY France, la touche physique 53 est le point d'exclamation ('!' sans shift, '§' avec shift/caps lock).
            candidate_keys: list[str] = [key_name]
            if key_name == "§" or event.scan_code == 53:
                if "!" not in candidate_keys:
                    candidate_keys.append("!")

            # Si c'est un relâchement de touche, nettoyer les touches maintenues et notifier move_manager
            if event.event_type == keyboard.KEY_UP:
                for k in candidate_keys:
                    self._pressed_keys.discard(k)

                if self.move_manager and self.state_manager.is_hook_enabled:
                    current_mode = self.state_manager.current_mode
                    move_cfg = self.config_manager.move_config
                    if move_cfg.enabled and (current_mode in move_cfg.active_modes or "all" in move_cfg.active_modes):
                        if self.move_manager.is_grid_active:
                            for cand in candidate_keys:
                                if self.move_manager.is_grid_cell_key(cand) or self.move_manager.is_grid_toggle_key(cand):
                                    return False

                        for cand in candidate_keys:
                            if self.move_manager.is_move_key(cand):
                                self.move_manager.release_key(cand)
                                return False
                return True

            # Événement KEY_DOWN
            # Éviter le spam des répétitions automatiques si la touche est déjà enfoncée
            is_repeat = any(k in self._pressed_keys for k in candidate_keys)
            for k in candidate_keys:
                self._pressed_keys.add(k)

            # Si le service est désactivé via le state manager, ne rien intercepter
            if not self.state_manager.is_hook_enabled:
                return True

            current_mode = self.state_manager.current_mode
            gen_cfg = self.config_manager.app_config.general
            special_key = gen_cfg.special_mode_key.lower().strip()

            # 1. Vérification de la touche de bascule vers le mode spécial (si configurée en dur)
            matched_special_key = None
            if special_key and not is_repeat:
                for cand in candidate_keys:
                    if cand == special_key:
                        matched_special_key = cand
                        break

            if matched_special_key:
                logger.debug("Touche de mode spécial détectée : '%s'", matched_special_key)
                if gen_cfg.toggle_special_mode:
                    new_mode = self.state_manager.toggle_mode(gen_cfg.special_mode_name)
                else:
                    self.state_manager.set_mode(gen_cfg.special_mode_name)
                    new_mode = gen_cfg.special_mode_name

                self.state_manager.add_log(
                    action_name=f"Bascule vers mode '{new_mode}'",
                    trigger_key=matched_special_key,
                    mode=current_mode,
                    status="success",
                )
                # Supprimer la touche pour éviter de taper le caractère spécial
                return False

            # 2. Vérification du déplacement dynamique au clavier (Move) et Grille Pavé Numérique
            move_cfg = self.config_manager.move_config
            if self.move_manager and move_cfg.enabled and (current_mode in move_cfg.active_modes or "all" in move_cfg.active_modes):
                for cand in candidate_keys:
                    # 2a. Touche Toggle Grille Pavé Numérique
                    if self.move_manager.is_grid_toggle_key(cand):
                        if not is_repeat:
                            self.move_manager.toggle_grid()
                        return False

                    # 2b. Si la grille pavé numérique est active, les touches de cellule effectuent un saut direct
                    if self.move_manager.is_grid_active:
                        if self.move_manager.is_grid_cell_key(cand):
                            if not is_repeat:
                                threading.Thread(
                                    target=self.move_manager.jump_grid_by_key,
                                    args=(cand,),
                                    daemon=True
                                ).start()
                            return False

                    # 2c. Touche Toggle Boost
                    if self.move_manager.is_boost_key(cand):
                        if not is_repeat:
                            self.move_manager.toggle_boost()
                        return False

                    # 2d. Touche de déplacement continu
                    if not self.move_manager.is_grid_active and self.move_manager.is_move_key(cand):
                        self.move_manager.press_key(cand)
                        return False

            # 2. Vérification de la grille souris si le mode actif fait partie des active_modes
            grid_cfg = self.config_manager.grid_config
            if grid_cfg.enabled and (current_mode in grid_cfg.active_modes or "all" in grid_cfg.active_modes):
                for cand in candidate_keys:
                    # 2a. Touche de bascule vers/depuis le mode sous-grille (subgrid toggle)
                    if self.grid_manager.is_subgrid_toggle_key(cand):
                        logger.debug("Touche toggle sous-grille détectée : '%s'", cand)
                        threading.Thread(
                            target=self._execute_subgrid_toggle,
                            args=(cand, current_mode),
                            daemon=True
                        ).start()
                        return False

                    # 2b. Touche de cellule en mode sous-grille (réutilise les mêmes touches de cases)
                    if current_mode == "subgrid" or self.grid_manager.is_subgrid_active:
                        if self.grid_manager.is_grid_key(cand):
                            logger.debug("Touche sous-grille détectée : '%s'", cand)
                            threading.Thread(
                                target=self._execute_subgrid_jump,
                                args=(cand, current_mode),
                                daemon=True
                            ).start()
                            return False

                    # 2c. Touche de rapprochement du bord (edge snap)
                    if self.grid_manager.is_edge_snap_key(cand):
                        logger.debug("Touche de rapprochement bord grille détectée : '%s'", cand)
                        threading.Thread(
                            target=self._execute_grid_edge_snap,
                            args=(cand, current_mode),
                            daemon=True
                        ).start()
                        return False

                    # 2d. Touche de cellule de grille standard
                    if self.grid_manager.is_grid_key(cand):
                        logger.debug("Touche de grille détectée : '%s'", cand)
                        # Exécuter dans un thread séparé pour ne pas ralentir le hook système
                        threading.Thread(
                            target=self._execute_grid_jump,
                            args=(cand, current_mode),
                            daemon=True
                        ).start()
                        return False

            # 3. Vérification des actions enregistrées pour le mode actif
            action = None
            matched_trigger = key_name
            for cand in candidate_keys:
                action = self.config_manager.get_action_for_key(cand, current_mode)
                if action is not None:
                    matched_trigger = cand
                    break

            if action is not None:
                logger.debug("Action '%s' trouvée pour touche '%s' dans mode '%s'", action.name, matched_trigger, current_mode)
                threading.Thread(
                    target=self.commands_engine.execute_action,
                    args=(action, matched_trigger),
                    daemon=True
                ).start()
                return False

            # Si aucune règle ne s'applique, laisser la touche se propager normalement
            return True

        except Exception as err:
            logger.error("Erreur critique dans le hook clavier : %s", err, exc_info=True)
            # En cas d'erreur, ne jamais bloquer le clavier de l'utilisateur
            return True

    def _execute_subgrid_toggle(self, key_name: str, current_mode: str) -> None:
        """Exécute la bascule sous-grille en arrière-plan."""
        try:
            is_active = self.grid_manager.toggle_subgrid()
            new_mode = self.state_manager.current_mode
            origin = self.grid_manager.subgrid_origin_cell
            self.state_manager.add_log(
                action_name=f"Toggle Sous-Grille ({'Actif' if is_active else 'Inactif'})",
                trigger_key=key_name,
                mode=current_mode,
                status="success",
                details=f"Nouveau mode : {new_mode}" + (f" | Case parente : {origin}" if origin else ""),
            )
        except Exception as err:
            logger.error("Erreur lors de la bascule sous-grille pour la touche '%s': %s", key_name, err, exc_info=True)

    def _execute_subgrid_jump(self, key_name: str, current_mode: str) -> None:
        """Exécute le saut de sous-grille en arrière-plan."""
        try:
            coords = self.grid_manager.jump_subcell_by_key(key_name)
            if coords:
                cx, cy = coords
                origin = self.grid_manager.subgrid_origin_cell or (0, 0)
                self.state_manager.add_log(
                    action_name=f"Saut Sous-Grille ({cx}, {cy})",
                    trigger_key=key_name,
                    mode=current_mode,
                    status="success",
                    details=f"Case parente : {origin}",
                )
        except Exception as err:
            logger.error("Erreur lors du saut de sous-grille pour la touche '%s': %s", key_name, err, exc_info=True)

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
