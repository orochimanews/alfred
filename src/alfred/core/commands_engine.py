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

if TYPE_CHECKING:
    from src.alfred.core.state import StateManager
    from src.alfred.core.grid import GridManager
    from src.alfred.core.config import ConfigManager

logger = logging.getLogger(__name__)


class CommandsEngine:
    """Interprète et exécute les commandes individuelles ou séquences d'actions."""

    def __init__(
        self,
        state_manager: StateManager,
        grid_manager: GridManager,
        config_manager: ConfigManager,
    ) -> None:
        self.state_manager = state_manager
        self.grid_manager = grid_manager
        self.config_manager = config_manager
        self._is_fast_mouse_speed: bool = False

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
            case _:
                logger.warning("Commande de type inconnu ignorée : '%s'", cmd_type)

    def _cmd_hotkey(self, params: dict) -> None:
        keys = params.get("keys")
        if not keys:
            return
        if isinstance(keys, list):
            hotkey_str = "+".join(str(k).strip() for k in keys)
        else:
            hotkey_str = str(keys).strip()
        keyboard.send(hotkey_str)

    def _cmd_click(self, params: dict) -> None:
        x = params.get("x")
        y = params.get("y")
        if x is not None and y is not None:
            mouse.set_position(int(x), int(y))
        button = str(params.get("button", "left"))
        clicks = int(params.get("clicks", 1))
        mouse.click(button=button, clicks=clicks)

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
        cfg = self.config_manager.app_config.mouse
        is_toggle = bool(params.get("toggle", False))
        target_speed = params.get("speed")
        step = params.get("step")

        if step is not None:
            cur = mouse.get_speed()
            mouse.set_speed(cur + int(step))
            return

        if is_toggle:
            fast_speed = int(target_speed or cfg.fast_speed)
            default_speed = cfg.default_speed
            if not self._is_fast_mouse_speed:
                mouse.set_speed(fast_speed)
                self._is_fast_mouse_speed = True
                logger.info("Vitesse souris passée en mode rapide : %d", fast_speed)
            else:
                mouse.set_speed(default_speed)
                self._is_fast_mouse_speed = False
                logger.info("Vitesse souris restaurée en mode normal : %d", default_speed)
        elif target_speed is not None:
            mouse.set_speed(int(target_speed))

    def _cmd_app(self, params: dict) -> None:
        command = str(params.get("command", "")).strip()
        args = params.get("args", [])
        if not command:
            return

        try:
            # Gestion des protocoles Windows (ex: onenote:, ms-settings:, urls)
            if ":" in command and not Path_is_absolute_win(command):
                os.startfile(command)
                return

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
