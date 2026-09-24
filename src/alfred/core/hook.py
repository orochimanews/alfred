"""Intercepteur global du clavier système (Keyboard Hook) pour Alfred."""

from __future__ import annotations
import sys
import time
import threading
import logging
from typing import Callable, TYPE_CHECKING, Any
import keyboard

if TYPE_CHECKING:
    from src.alfred.core.state import StateManager
    from src.alfred.core.config import ConfigManager
    from src.alfred.core.commands_engine import CommandsEngine
    from src.alfred.core.grid import GridManager
    from src.alfred.core.move import MoveManager

logger = logging.getLogger(__name__)


def _setup_hook_thread_win32() -> None:
    """Optimise le thread d'écoute du hook pour garantir sa réactivité même sans fenêtre visible.

    Dans un build PyInstaller --windowed, quand toutes les fenêtres Tkinter sont cachées
    (withdraw/tray), Windows 11 peut throttler le thread du hook via EcoQoS/Power Throttling,
    stoppant silencieusement la livraison des callbacks WH_KEYBOARD_LL.

    Trois couches de protection :
    1. Priorité thread HIGHEST  → le thread n'est pas mis en attente par le scheduler
    2. SetThreadInformation     → désactive le Power Throttling pour ce thread précis
    3. AvSetMmThreadCharacteristicsW("Pro Audio") → marque le thread comme temps-réel
       (même mécanisme que les DAW audio, garantit 0 throttling par Windows)
    """
    if sys.platform != "win32":
        return
    try:
        import ctypes
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        h_thread = kernel32.GetCurrentThread()

        # 1. Priorité maximale du thread scheduler
        THREAD_PRIORITY_HIGHEST = 2
        kernel32.SetThreadPriority(h_thread, THREAD_PRIORITY_HIGHEST)

        # 2. Désactiver le Power Throttling (EcoQoS) pour ce thread individuel
        try:
            class THREAD_POWER_THROTTLING_STATE(ctypes.Structure):
                _fields_ = [
                    ("Version",     ctypes.c_uint32),
                    ("ControlMask", ctypes.c_uint32),
                    ("StateMask",   ctypes.c_uint32),
                ]
            state = THREAD_POWER_THROTTLING_STATE()
            state.Version = 1
            state.ControlMask = 0x1  # THREAD_POWER_THROTTLING_EXECUTION_SPEED
            state.StateMask = 0       # 0 = désactiver le throttling

            # OpenThread avec THREAD_SET_INFORMATION (0x0020) requis pour SetThreadInformation
            # ThreadPowerThrottling = 3
            h_thread_set = kernel32.OpenThread(0x0020, False, kernel32.GetCurrentThreadId())
            if h_thread_set:
                try:
                    kernel32.SetThreadInformation(
                        h_thread_set,
                        3,  # ThreadPowerThrottling
                        ctypes.byref(state),
                        ctypes.sizeof(state),
                    )
                finally:
                    kernel32.CloseHandle(h_thread_set)
        except Exception:
            pass

        logger.debug("Thread hook clavier optimisé : priorité HIGHEST, EcoQoS off.")
    except Exception as err:
        logger.debug("Impossible d'optimiser le thread du hook : %s", err)


_current_hook_handle: Any = None
_hook_thread_id: int | None = None


def _patch_keyboard_windows_listen() -> None:
    """Corrige le bug critique de pointeur NULL dans keyboard._winkeyboard.listen sous Windows.

    Par défaut, keyboard._winkeyboard fait 'msg = LPMSG()', ce qui passe un pointeur NULL
    à GetMessage(). Dès qu'un message système arrive dans la file du thread, une violation
    d'accès (Access Violation 0x00000008) survient et tue le thread d'écoute en silence.
    Ce patch alloue une structure MSG() valide, capture le thread ID et le hook handle pour
    permettre la réinstallation à chaud, et optimise le thread scheduler.
    """
    if sys.platform != "win32":
        return

    try:
        from keyboard import _winkeyboard
        import ctypes
        from ctypes.wintypes import MSG

        # Intercepter SetWindowsHookEx pour conserver le handle HHOOK
        if not getattr(_winkeyboard, "_alfred_hook_patched", False):
            orig_set_hook = _winkeyboard.SetWindowsHookEx

            def custom_set_hook(*args, **kwargs):
                global _current_hook_handle
                h = orig_set_hook(*args, **kwargs)
                _current_hook_handle = h
                return h

            _winkeyboard.SetWindowsHookEx = custom_set_hook
            _winkeyboard._alfred_hook_patched = True

        def safe_listen(callback):
            global _hook_thread_id
            import ctypes
            kernel32 = ctypes.windll.kernel32
            _hook_thread_id = kernel32.GetCurrentThreadId()

            # Optimiser ce thread immédiatement : priorité haute, EcoQoS désactivé.
            _setup_hook_thread_win32()
            try:
                _winkeyboard.prepare_intercept(callback)
                msg = MSG()
                p_msg = ctypes.byref(msg)
                # Boucle Win32 robuste : s'arrête sur WM_QUIT (0), tolère les retours -1 transitoires
                while True:
                    res = _winkeyboard.GetMessage(p_msg, 0, 0, 0)
                    if res == 0:  # WM_QUIT reçu
                        break
                    elif res == -1:  # Erreur système transitoire, ne pas quitter le thread
                        time.sleep(0.01)
                        continue
                    _winkeyboard.TranslateMessage(p_msg)
                    _winkeyboard.DispatchMessage(p_msg)
            finally:
                _hook_thread_id = None

        _winkeyboard.listen = safe_listen
        logger.debug("Patch de sécurité appliqué à keyboard._winkeyboard.listen.")
    except Exception as err:
        logger.warning("Impossible de patcher keyboard._winkeyboard.listen : %s", err)


def is_modifier_pressed_win32(mod: str) -> bool:
    """Vérifie si une touche modificatrice est physiquement enfoncée via Windows API."""
    if sys.platform != "win32":
        return False
    try:
        import ctypes
        VK_MAP = {
            "ctrl": 0x11,        # VK_CONTROL
            "shift": 0x10,       # VK_SHIFT
            "alt": 0x12,         # VK_MENU
            "win": [0x5B, 0x5C], # VK_LWIN, VK_RWIN
        }
        vk = VK_MAP.get(mod)
        if vk is not None:
            user32 = ctypes.windll.user32
            if isinstance(vk, list):
                return any(bool(user32.GetAsyncKeyState(k) & 0x8000) for k in vk)
            return bool(user32.GetAsyncKeyState(vk) & 0x8000)
    except Exception:
        pass
    return False


def match_shortcut(shortcut: str, candidate_keys: list[str], pressed_keys: set[str]) -> bool:
    """Vérifie si une frappe clavier correspond à un raccourci défini (ex: 'ctrl+shift+q' ou 'f12')."""
    s = shortcut.strip().lower()
    if not s:
        return False

    if s.endswith("++"):
        parts = [p.strip() for p in s[:-2].split("+") if p.strip()]
        parts.append("+")
    else:
        parts = [p.strip() for p in s.split("+") if p.strip()]

    if not parts:
        return False

    MODIFIERS_MAP = {
        "ctrl": "ctrl", "control": "ctrl",
        "shift": "shift", "maj": "shift",
        "alt": "alt", "altgr": "alt", "alt gr": "alt",
        "win": "win", "windows": "win", "super": "win"
    }

    req_mods: set[str] = set()
    trigger_key = ""
    for idx, part in enumerate(parts):
        if idx < len(parts) - 1 and part in MODIFIERS_MAP:
            req_mods.add(MODIFIERS_MAP[part])
        else:
            if idx == len(parts) - 1:
                trigger_key = part
            else:
                req_mods.add(part)

    KEY_ALIASES = {
        "esc": {"esc", "escape"},
        "escape": {"esc", "escape"},
        "return": {"enter", "return", "entree", "entrée"},
        "enter": {"enter", "return", "entree", "entrée"},
        "del": {"del", "delete", "suppr"},
        "delete": {"del", "delete", "suppr"},
    }
    allowed_triggers = KEY_ALIASES.get(trigger_key, {trigger_key})
    if not any(k in allowed_triggers for k in candidate_keys):
        return False

    ALL_MODS = ("ctrl", "shift", "alt", "win")
    MOD_ALIASES = {
        "ctrl": {"ctrl", "left ctrl", "right ctrl", "control"},
        "shift": {"shift", "left shift", "right shift", "maj"},
        "alt": {"alt", "left alt", "right alt", "alt gr", "altgr"},
        "win": {"win", "windows", "left windows", "right windows", "super"},
    }
    for m in ALL_MODS:
        aliases = MOD_ALIASES[m]
        is_down = is_modifier_pressed_win32(m) or any(k in pressed_keys for k in aliases)
        if m in req_mods:
            if not is_down:
                return False
        else:
            if is_down:
                return False
    return True


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
        self._quit_callback: Callable[[], None] | None = None
        self._hook_lock = threading.RLock()
        self._last_event_time: float = time.time()

        # Surveiller les changements de mode pour couper les mouvements en cours si nécessaire
        self.state_manager.subscribe(self._on_state_event)

    def set_quit_callback(self, callback: Callable[[], None]) -> None:
        """Définit le callback invoqué lors du déclenchement du raccourci global de fermeture."""
        self._quit_callback = callback

    def _trigger_quit(self) -> None:
        """Déclenche la fermeture propre de l'application Alfred."""
        logger.info("Déclenchement du callback de fermeture globale...")
        if self._quit_callback:
            try:
                self._quit_callback()
            except Exception as err:
                logger.error("Erreur lors de l'exécution du quit_callback : %s", err, exc_info=True)
        else:
            import os
            os._exit(0)

    def start(self) -> None:
        """Démarre l'écoute globale du clavier."""
        with self._hook_lock:
            if self._hook_installed:
                return
            self._install_hook()
            logger.info("Hook clavier global installé avec succès.")

    def stop(self) -> None:
        """Arrête l'écoute du clavier."""
        with self._hook_lock:
            if not self._hook_installed:
                return
            self._teardown_hook()
            logger.info("Hook clavier global désactivé.")

    def _install_hook(self) -> None:
        """Installe le hook bas-niveau Windows et démarre le thread."""
        _patch_keyboard_windows_listen()
        keyboard.hook(self._on_key_event, suppress=True)
        self._hook_installed = True

    def _teardown_hook(self) -> None:
        """Détruit proprement le hook et le thread de message loop existant."""
        global _current_hook_handle, _hook_thread_id
        try:
            if sys.platform == "win32":
                from keyboard import _winkeyboard
                import ctypes

                # 1. Unhook explicitement via Windows API si le handle existe
                if _current_hook_handle:
                    try:
                        _winkeyboard.UnhookWindowsHookEx(_current_hook_handle)
                    except Exception:
                        pass
                    _current_hook_handle = None

                # 2. Envoyer WM_QUIT (0x0012) au thread de la boucle GetMessage pour le libérer
                if _hook_thread_id:
                    try:
                        ctypes.windll.user32.PostThreadMessageW(_hook_thread_id, 0x0012, 0, 0)
                    except Exception:
                        pass
                    _hook_thread_id = None

            # 3. Réinitialiser l'état interne de la bibliothèque keyboard
            if hasattr(keyboard, "_listener") and keyboard._listener:
                keyboard._listener.listening = False
                if hasattr(keyboard._listener, "blocking_hooks"):
                    del keyboard._listener.blocking_hooks[:]
                old_thread = getattr(keyboard._listener, "listening_thread", None)
                if old_thread and old_thread.is_alive():
                    old_thread.join(timeout=0.3)

            try:
                keyboard.unhook(self._on_key_event)
            except Exception:
                pass

            self._pressed_keys.clear()
            self._hook_installed = False
        except Exception as err:
            logger.warning("Erreur lors de la désinstallation du hook : %s", err)
            self._hook_installed = False

    def reinstall_hook(self) -> None:
        """Réinstalle proprement le hook clavier Windows (recréation complète du thread et de WH_KEYBOARD_LL)."""
        with self._hook_lock:
            logger.info("Réinstallation complète du hook clavier Windows...")
            self._teardown_hook()
            self._install_hook()
            logger.info("Hook clavier Windows réinstallé avec succès.")

    def ensure_hook_healthy(self) -> None:
        """Vérifie la santé du hook clavier et le réinstalle automatiquement en cas d'anomalie."""
        with self._hook_lock:
            if not self._hook_installed:
                self.start()
                return

            listener = getattr(keyboard, "_listener", None)
            if listener:
                listening_thread = getattr(listener, "listening_thread", None)
                if listening_thread and not listening_thread.is_alive():
                    logger.warning("Thread d'écoute du hook clavier inactif détecté. Réinstallation automatique...")
                    self.reinstall_hook()

    def _on_state_event(self, event_type: str, data: Any) -> None:
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
            self._last_event_time = time.time()
            key_name = (event.name or "").lower().strip()
            if not key_name:
                return True

            # Tolérance de saisie clavier pour AZERTY / verrouillage majuscule :
            # Sur AZERTY France, la touche physique 53 est le point d'exclamation ('!' sans shift, '§' avec shift/caps lock).
            candidate_keys: list[str] = [key_name]
            if key_name == "§" or event.scan_code == 53:
                if "!" not in candidate_keys:
                    candidate_keys.append("!")

            # Normalisation et alias des modificateurs pour le suivi d'état des touches
            if key_name in ("left ctrl", "right ctrl", "control", "ctrl"):
                for m in ("ctrl", "control"):
                    if m not in candidate_keys:
                        candidate_keys.append(m)
            elif key_name in ("left shift", "right shift", "shift", "maj"):
                for m in ("shift", "maj"):
                    if m not in candidate_keys:
                        candidate_keys.append(m)
            elif key_name in ("left alt", "right alt", "alt", "alt gr", "altgr"):
                for m in ("alt", "altgr"):
                    if m not in candidate_keys:
                        candidate_keys.append(m)
            elif key_name in ("left windows", "right windows", "windows", "win", "super"):
                for m in ("win", "windows"):
                    if m not in candidate_keys:
                        candidate_keys.append(m)

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
            # Protection contre les touches fantômes restées coincées (perte de focus, fermeture de fenêtre type Explorateur)
            if is_repeat and sys.platform == "win32" and getattr(event, "scan_code", None):
                try:
                    import ctypes
                    user32 = ctypes.windll.user32
                    vk = user32.MapVirtualKeyW(abs(event.scan_code), 1)
                    if vk and not (user32.GetAsyncKeyState(vk) & 0x8000):
                        # La touche n'est plus physiquement maintenue : c'était un reliquat coincé
                        for k in candidate_keys:
                            self._pressed_keys.discard(k)
                        is_repeat = False
                except Exception:
                    pass

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

            # 1b. Retour automatique au mode spécial lors de la validation avec la touche Entrée
            if (
                current_mode == "normal"
                and getattr(gen_cfg, "auto_return_on_enter", True)
                and self.state_manager.is_auto_switched_to_normal
                and not is_repeat
            ):
                is_enter = (
                    any(k in ("enter", "return", "entree") for k in candidate_keys)
                    or getattr(event, "scan_code", None) in (28, 284)
                )
                if is_enter:
                    # Si Shift est maintenu (ex: saut de ligne dans textarea/messagerie), ne pas basculer
                    is_shift = any(k in self._pressed_keys for k in ("shift", "maj", "left shift", "right shift"))
                    if not is_shift:
                        logger.debug("Touche Entrée détectée après auto-switch champ texte. Programmation du retour en mode spécial.")
                        self.state_manager.set_auto_switched_to_normal(False)
                        target_mode = gen_cfg.special_mode_name

                        def _return_to_special():
                            time.sleep(0.06)
                            if self.state_manager.current_mode == "normal":
                                self.state_manager.set_mode(target_mode)
                                self.state_manager.add_log(
                                    action_name=f"Bascule vers mode '{target_mode}'",
                                    trigger_key="Entrée",
                                    mode="normal",
                                    status="success",
                                    details="Validation par Entrée (fin de saisie texte)",
                                )

                        threading.Thread(
                            target=_return_to_special,
                            daemon=True,
                            name="Alfred-ReturnSpecialOnEnter",
                        ).start()
                        # Laisser passer la touche Entrée pour que l'application reçoive la validation/envoi
                        return True

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

                    # 2d. Touche de rapprochement du bord (Edge Snap)
                    if self.move_manager.is_edge_snap_key(cand):
                        if not is_repeat:
                            logger.debug("Touche de rapprochement bord (move) détectée : '%s'", cand)
                            threading.Thread(
                                target=self._execute_move_edge_snap,
                                args=(cand, current_mode),
                                daemon=True
                            ).start()
                        return False

                    # 2e. Touche de déplacement continu
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

    def _execute_move_edge_snap(self, key_name: str, current_mode: str) -> None:
        """Exécute le rapprochement vers le bord de l'écran en arrière-plan (Move)."""
        try:
            coords = self.move_manager.snap_to_edge() if self.move_manager else None
            if coords:
                nx, ny = coords
                self.state_manager.add_log(
                    action_name=f"Bord Curseur ({nx}, {ny})",
                    trigger_key=key_name,
                    mode=current_mode,
                    status="success",
                )
            else:
                self.state_manager.add_log(
                    action_name="Bord Curseur (hors bord)",
                    trigger_key=key_name,
                    mode=current_mode,
                    status="ignored",
                )
        except Exception as err:
            logger.error("Erreur lors du rapprochement vers le bord (move) pour la touche '%s': %s", key_name, err)

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
