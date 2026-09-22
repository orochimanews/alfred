"""Moteur d'exécution des commandes et séquences d'actions."""

from __future__ import annotations
import subprocess
import time
import os
import logging
from typing import TYPE_CHECKING
import keyboard

from src.alfred.core.models import Command, Action
from src.alfred.core.mouse import mouse
from src.alfred.core.window import find_window_for_app, bring_window_to_foreground

if TYPE_CHECKING:
    from src.alfred.core.state import StateManager
    from src.alfred.core.grid import GridManager
    from src.alfred.core.config import ConfigManager
    from src.alfred.core.move import MoveManager

logger = logging.getLogger(__name__)


class CommandsEngine:
    """Interprète et exécute les commandes individuelles ou séquences d'actions."""

    def __init__(
        self,
        state_manager: StateManager,
        grid_manager: GridManager,
        config_manager: ConfigManager,
        move_manager: MoveManager | None = None,
    ) -> None:
        self.state_manager = state_manager
        self.grid_manager = grid_manager
        self.config_manager = config_manager
        self.move_manager = move_manager
        self._is_fast_mouse_speed: bool = False
        self._previous_mouse_speed: int | None = None
        self._quit_callback: Any = None

    def set_quit_callback(self, callback: Any) -> None:
        """Définit le callback pour les commandes d'arrêt du programme."""
        self._quit_callback = callback

    def execute_action(self, action: Action, trigger_key: str = "") -> bool:
        """Exécute l'action complète (standard ou toggle) et journalise l'événement."""
        mode_when_triggered = self.state_manager.current_mode
        try:
            if action.toggle and action.states:
                # Gestion de la bascule d'états
                idx = action.current_state_index % len(action.states)
                current_state = action.states[idx]
                logger.info("Exécution de l'action toggle '%s' -> État [%d]: %s", action.name, idx, current_state.name)
                for cmd in current_state.commands:
                    self.execute_command(cmd)
                action.current_state_index = (idx + 1) % len(action.states)
                self.state_manager.add_log(
                    action_name=f"{action.name} ({current_state.name})",
                    trigger_key=trigger_key or action.trigger,
                    mode=mode_when_triggered,
                    status="success",
                    details=f"Bascule vers état {action.current_state_index}",
                )
            else:
                # Exécution séquentielle normale
                logger.info("Exécution de l'action '%s' (%d commandes)", action.name, len(action.commands))
                for cmd in action.commands:
                    self.execute_command(cmd)

                self.state_manager.add_log(
                    action_name=action.name,
                    trigger_key=trigger_key or action.trigger,
                    mode=mode_when_triggered,
                    status="success",
                )
            return True
        except Exception as err:
            logger.error("Erreur lors de l'exécution de l'action '%s': %s", action.name, err, exc_info=True)
            self.state_manager.add_log(
                action_name=action.name,
                trigger_key=trigger_key or action.trigger,
                mode=mode_when_triggered,
                status="error",
                details=str(err),
            )
            return False

    def execute_command(self, command: Command) -> None:
        """Exécute une commande élémentaire selon son type."""
        cmd_type = command.type.lower().strip()
        params = command.params

        match cmd_type:
            case "hotkey":
                self._cmd_hotkey(params)
            case "click":
                self._cmd_click(params)
            case "middle_click":
                mouse.click("middle")
            case "jump":
                self._cmd_jump(params)
            case "mode":
                self._cmd_mode(params)
            case "mouse_speed":
                self._cmd_mouse_speed(params)
            case "mouse_nudge" | "nudge":
                self._cmd_mouse_nudge(params)
            case "app":
                self._cmd_app(params)
            case "sleep":
                duration = float(params.get("duration", 0.1))
                time.sleep(max(0.0, duration))
            case "text":
                content = str(params.get("content", ""))
                if content:
                    keyboard.write(content)
            case "grid_cell":
                col = int(params.get("col", 0))
                row = int(params.get("row", 0))
                self.grid_manager.jump_to_cell(col, row)
            case "subgrid_cell":
                col = int(params.get("col", 0))
                row = int(params.get("row", 0))
                self.grid_manager.jump_to_subcell(col, row)
            case "subgrid":
                self._cmd_subgrid(params)
            case "edge_snap" | "grid_edge_snap" | "move_edge_snap":
                raw_off = params.get("offset", params.get("steps", params.get("distance", None)))
                offset = int(raw_off) if raw_off is not None else None
                if self.move_manager and self.move_manager.config.edge_snap_enabled:
                    self.move_manager.snap_to_edge(offset=offset)
                elif self.grid_manager:
                    self.grid_manager.snap_to_edge(offset=offset)
            case "scroll" | "wheel":
                self._cmd_scroll(params)
            case "mouse_down":
                self._cmd_mouse_down(params)
            case "mouse_up":
                self._cmd_mouse_up(params)
            case "zoom":
                self._cmd_zoom(params)
            case "move_boost" | "move_speed_boost":
                self._cmd_move_boost(params)
            case "move_grid_toggle" | "move_grid":
                self._cmd_move_grid_toggle(params)
            case "move_grid_cell":
                self._cmd_move_grid_cell(params)
            case "quit" | "exit":
                if self._quit_callback:
                    self._quit_callback()
            case _:
                logger.warning("Commande de type inconnu ignorée : '%s'", cmd_type)

    def _cmd_move_boost(self, params: dict) -> None:
        """Bascule ou modifie l'état de boost du déplacement clavier."""
        if not self.move_manager:
            return
        if "active" in params:
            self.move_manager.set_boost(bool(params["active"]))
        elif "toggle" in params:
            if bool(params["toggle"]):
                self.move_manager.toggle_boost()
        else:
            self.move_manager.toggle_boost()

    def _cmd_move_grid_toggle(self, params: dict) -> None:
        """Bascule ou modifie l'état de la grille pavé numérique du module Move."""
        if not self.move_manager:
            return
        if "active" in params:
            self.move_manager.set_grid_active(bool(params["active"]))
        elif "toggle" in params:
            if bool(params["toggle"]):
                self.move_manager.toggle_grid()
        else:
            self.move_manager.toggle_grid()

    def _cmd_move_grid_cell(self, params: dict) -> None:
        """Déplace le curseur au centre d'une case de la grille pavé numérique."""
        if not self.move_manager:
            return
        col = int(params.get("col", 0))
        row = int(params.get("row", 0))
        self.move_manager.jump_grid_cell(col, row)

    def _cmd_subgrid(self, params: dict) -> None:
        toggle = bool(params.get("toggle", True))
        active = params.get("active")
        if active is not None:
            self.grid_manager.set_subgrid_active(bool(active))
            if bool(active):
                self.state_manager.set_mode("subgrid")
            else:
                prev = self.state_manager.previous_mode
                self.state_manager.set_mode(prev if prev in ("grid", "special") else "grid")
        elif toggle:
            self.grid_manager.toggle_subgrid()
        else:
            self.grid_manager.toggle_subgrid()

    def _cmd_hotkey(self, params: dict) -> None:
        keys = params.get("keys")
        if not keys:
            return
        if isinstance(keys, list):
            cleaned = []
            for k in keys:
                s = str(k).strip()
                if s == "+":
                    cleaned.append("add")
                elif s == "-" and any(m in [str(x).lower() for x in keys] for m in ("ctrl", "alt")):
                    cleaned.append("subtract")
                else:
                    cleaned.append(s)
            hotkey_str = "+".join(cleaned)
        else:
            hotkey_str = str(keys).strip()
            if hotkey_str.endswith("++"):
                hotkey_str = hotkey_str[:-1] + "add"
        keyboard.send(hotkey_str)

    def _cmd_click(self, params: dict) -> None:
        x = params.get("x")
        y = params.get("y")
        if x is not None and y is not None:
            mouse.set_position(int(x), int(y))
        button = str(params.get("button", "left"))
        clicks = int(params.get("clicks", 1))
        mouse.click(button=button, clicks=clicks)

    def _cmd_scroll(self, params: dict) -> None:
        delta = params.get("delta", params.get("clicks", 1))
        try:
            delta_val = float(delta)
        except (ValueError, TypeError):
            delta_val = 1.0
        mouse.scroll(delta_val)

    def _cmd_mouse_down(self, params: dict) -> None:
        button = str(params.get("button", "left"))
        mouse.mouse_down(button)

    def _cmd_mouse_up(self, params: dict) -> None:
        button = str(params.get("button", "left"))
        mouse.mouse_up(button)

    def _cmd_zoom(self, params: dict) -> None:
        direction = str(params.get("direction", params.get("dir", "in"))).lower().strip()
        steps = int(params.get("steps", params.get("clicks", 1)))
        mouse.zoom(direction=direction, steps=steps)

    def _cmd_jump(self, params: dict) -> None:
        x = int(params.get("x", 0))
        y = int(params.get("y", 0))
        relative = bool(params.get("relative", False))
        if relative:
            mouse.move_relative(x, y)
        else:
            mouse.set_position(x, y)

    def _cmd_mode(self, params: dict) -> None:
        target = str(params.get("target", "normal")).lower().strip()
        if target == "toggle":
            toggle_with = str(params.get("toggle_with", "normal")).lower().strip()
            self.state_manager.toggle_mode(toggle_with)
        else:
            self.state_manager.set_mode(target)

    def _cmd_mouse_speed(self, params: dict) -> None:
        cfg = getattr(self.config_manager.app_config, "mouse", None)
        is_toggle = bool(params.get("toggle", False))
        target_speed = params.get("speed")
        step = params.get("step")

        if step is not None:
            cur = mouse.get_speed()
            mouse.set_speed(cur + int(step))
            return

        if is_toggle:
            fast_speed = int(target_speed or 18)

            if not self._is_fast_mouse_speed:
                # Mémoriser la sensibilité de retour (soit Windows en direct, soit valeur configurée)
                if cfg and not cfg.use_system_speed:
                    self._previous_mouse_speed = cfg.default_speed
                else:
                    self._previous_mouse_speed = mouse.get_speed()

                mouse.set_speed(fast_speed)
                self._is_fast_mouse_speed = True
                logger.info("Vitesse curseur activée : %d (vitesse normale mémorisée : %d)", fast_speed, self._previous_mouse_speed)
            else:
                # Restaurer la vitesse normale
                restore_speed = self._previous_mouse_speed
                if restore_speed is None:
                    restore_speed = cfg.default_speed if (cfg and not cfg.use_system_speed) else mouse.get_speed()

                mouse.set_speed(restore_speed)
                self._is_fast_mouse_speed = False
                logger.info("Vitesse curseur restaurée : %d", restore_speed)
        elif target_speed is not None:
            mouse.set_speed(int(target_speed))

    def _cmd_mouse_nudge(self, params: dict) -> None:
        step = int(params.get("step", params.get("pixels", 120)))
        threshold = int(params.get("threshold", 4))
        cooldown = float(params.get("cooldown", 0.08))
        toggle = bool(params.get("toggle", True))
        active = params.get("active")

        if active is not None:
            if bool(active):
                mouse.start_nudge_mode(step=step, threshold=threshold, cooldown=cooldown)
            else:
                mouse.stop_nudge_mode()
        elif toggle:
            mouse.toggle_nudge_mode(step=step, threshold=threshold, cooldown=cooldown)
        else:
            mouse.start_nudge_mode(step=step, threshold=threshold, cooldown=cooldown)

    def _cmd_app(self, params: dict) -> None:
        command = str(params.get("command", "")).strip()
        args = params.get("args", [])
        reuse_existing = bool(params.get("reuse_existing", True))
        if not command:
            return

        command = os.path.expandvars(os.path.expanduser(command))

        try:
            # Correction spécifique pour OneNote :
            # Sous Windows, le protocole "onenote:" est associé à : ONENOTE.EXE /hyperlink "%1"
            # Lancer "onenote:" sans URL de page valide fait croire à OneNote qu'un lien invalide a été ouvert,
            # provoquant l'affichage d'une boîte de dialogue d'erreur "Microsoft OneNote".
            # En ciblant l'exécutable/App Path "onenote", OneNote s'ouvre normalement sans message d'erreur.
            target = command
            if target.lower() == "onenote:":
                target = "onenote"
            elif target.lower() in ("antigravity", "antigravity.exe"):
                default_antigravity = os.path.expandvars(r"%LOCALAPPDATA%\Programs\antigravity\Antigravity.exe")
                if os.path.exists(default_antigravity):
                    target = default_antigravity
            elif target.lower() in ("chrome", "chrome.exe", "google-chrome", "googlechrome"):
                # Préférer le vrai Google Chrome officiel s'il est installé,
                # afin d'éviter qu'un fork Chromium (ex: BrowserOS) ne détourne l'appel via HKCU App Paths.
                real_chrome_paths = [
                    os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
                    os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
                    os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
                ]
                for p in real_chrome_paths:
                    if os.path.isfile(p):
                        target = p
                        break
            elif target.lower() in ("vscode", "code", "code.exe"):
                for p in [
                    r"C:\programs\Microsoft VS Code\Code.exe",
                    os.path.expandvars(r"%LOCALAPPDATA%\Programs\Microsoft VS Code\Code.exe"),
                    os.path.expandvars(r"%ProgramFiles%\Microsoft VS Code\Code.exe"),
                ]:
                    if os.path.isfile(p):
                        target = p
                        break
            elif target.lower() in ("vlc", "vlc.exe"):
                for p in [
                    r"C:\programs\VideoLAN\VLC\vlc.exe",
                    os.path.expandvars(r"%ProgramFiles%\VideoLAN\VLC\vlc.exe"),
                    os.path.expandvars(r"%ProgramFiles(x86)%\VideoLAN\VLC\vlc.exe"),
                ]:
                    if os.path.isfile(p):
                        target = p
                        break
            elif target.lower() in ("firefox", "firefox.exe"):
                for p in [
                    os.path.expandvars(r"%ProgramFiles%\Mozilla Firefox\firefox.exe"),
                    os.path.expandvars(r"%ProgramFiles(x86)%\Mozilla Firefox\firefox.exe"),
                    os.path.expandvars(r"%LOCALAPPDATA%\Mozilla Firefox\firefox.exe"),
                ]:
                    if os.path.isfile(p):
                        target = p
                        break
            elif target.lower() in ("brave", "brave.exe", "brave-browser"):
                for p in [
                    os.path.expandvars(r"%ProgramFiles%\BraveSoftware\Brave-Browser\Application\brave.exe"),
                    os.path.expandvars(r"%ProgramFiles(x86)%\BraveSoftware\Brave-Browser\Application\brave.exe"),
                    os.path.expandvars(r"%LOCALAPPDATA%\BraveSoftware\Brave-Browser\Application\brave.exe"),
                ]:
                    if os.path.isfile(p):
                        target = p
                        break

            # 0. Vérifier si l'application possède déjà une fenêtre ouverte à réactiver
            if reuse_existing:
                existing_hwnd = find_window_for_app(target)
                if existing_hwnd:
                    logger.info("Application '%s' déjà ouverte (HWND: %d), réactivation au premier plan.", target, existing_hwnd)
                    if bring_window_to_foreground(existing_hwnd):
                        return

            # 1. Tenter via os.startfile (gère nativement les App Paths Windows, protocoles URI, extensions associées et URLs)
            try:
                if args:
                    args_str = " ".join(str(a) for a in args)
                    os.startfile(target, arguments=args_str)
                else:
                    os.startfile(target)
                return
            except Exception:
                pass

            # 2. Repli sur subprocess.Popen si os.startfile échoue
            cmd_list = [command]
            if isinstance(args, list):
                cmd_list.extend(str(a) for a in args)
            subprocess.Popen(cmd_list, shell=True)
        except Exception as err:
            logger.error("Erreur lors du lancement de l'application '%s': %s", command, err)


def Path_is_absolute_win(path_str: str) -> bool:
    """Vérifie si la chaîne ressemble à un chemin absolu Windows (ex: C:\\...)"""
    if len(path_str) >= 2 and path_str[1] == ":" and (path_str[0].isalpha()):
        return True
    return False
