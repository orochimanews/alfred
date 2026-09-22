"""Gestionnaire de configuration et persistance TOML pour Alfred."""

from __future__ import annotations
import os
from pathlib import Path
from typing import Any
import logging
import sys
import tomllib
import tomli_w

from src.alfred.core.models import (
    AppConfig,
    GeneralConfig,
    ModeConfig,
    MouseConfig,
    UIConfig,
    GridConfig,
    MoveConfig,
    Action,
)

logger = logging.getLogger(__name__)


class ConfigManager:
    """Charge, valide et sauvegarde la configuration d'Alfred depuis le dossier settings/."""

    def __init__(self, base_dir: Path | None = None) -> None:
        if base_dir is not None:
            self.root_dir = Path(base_dir)
        elif getattr(sys, "frozen", False):
            # En mode exécutable autonome (PyInstaller onedir/onefile)
            exe_dir = Path(sys.executable).resolve().parent
            if (exe_dir / "settings").exists():
                self.root_dir = exe_dir
            elif hasattr(sys, "_MEIPASS") and (Path(sys._MEIPASS) / "settings").exists():
                self.root_dir = Path(sys._MEIPASS)
            else:
                self.root_dir = exe_dir
        else:
            # Répertoire racine du projet (au-dessus de src/alfred/core)
            self.root_dir = Path(__file__).resolve().parent.parent.parent.parent

        self.settings_dir = self.root_dir / "settings"
        self.actions_dir = self.settings_dir / "actions"
        self.config_path = self.settings_dir / "config.toml"
        self.grid_path = self.settings_dir / "grid.toml"
        self.move_path = self.settings_dir / "move.toml"
        self.commands_path = self.settings_dir / "commands.toml"
        self.keys_path = self.settings_dir / "keys.toml"

        self.app_config: AppConfig = AppConfig()
        self.grid_config: GridConfig = GridConfig()
        self.move_config: MoveConfig = MoveConfig()
        self.actions: list[Action] = []
        self.commands_reference: dict[str, Any] = {}
        self.keys_reference: dict[str, Any] = {}

    def load_all(self) -> None:
        """Charge l'ensemble de la configuration depuis le système de fichiers."""
        self.load_app_config()
        self.load_grid_config()
        self.load_move_config()
        self.load_actions()
        self.load_references()

    def load_app_config(self) -> AppConfig:
        """Charge settings/config.toml."""
        if not self.config_path.exists():
            logger.warning("Fichier config.toml introuvable à %s, création avec valeurs par défaut.", self.config_path)
            self.app_config = AppConfig()
            self.save_app_config()
            return self.app_config

        try:
            with open(self.config_path, "rb") as f:
                data = tomllib.load(f)

            gen_data = data.get("general", {})

            raw_quit = gen_data.get("quit")
            if raw_quit is None:
                raw_quit = gen_data.get("quit_key")
            if raw_quit is None:
                raw_quit = gen_data.get("quit_shortcut")
            if raw_quit is None:
                raw_quit = gen_data.get("exit_shortcut")
            if raw_quit is None:
                raw_quit = gen_data.get("exit_key")
            if raw_quit is None:
                raw_quit = gen_data.get("exit")
            quit_shortcut = str(raw_quit).strip() if raw_quit is not None else "ctrl+shift+q"

            raw_start_special = gen_data.get("start_in_special_mode")
            if raw_start_special is not None:
                start_in_special = bool(raw_start_special)
                default_mode = "special" if start_in_special else gen_data.get("default_mode", "normal")
            elif "default_mode" in gen_data:
                default_mode = str(gen_data.get("default_mode", "special"))
                start_in_special = (default_mode == "special")
            else:
                start_in_special = True
                default_mode = "special"

            general = GeneralConfig(
                app_name=gen_data.get("app_name", "Alfred"),
                default_mode=default_mode,
                start_in_special_mode=start_in_special,
                quit=quit_shortcut,
                special_mode_key=gen_data.get("special_mode_key", ""),
                special_mode_name=gen_data.get("special_mode_name", "special"),
                toggle_special_mode=bool(gen_data.get("toggle_special_mode", True)),
                auto_exit_on_text_input=bool(gen_data.get("auto_exit_on_text_input", True)),
                auto_return_on_enter=bool(gen_data.get("auto_return_on_enter", True)),
            )

            modes_data = data.get("modes", {})
            modes: dict[str, ModeConfig] = {}
            if isinstance(modes_data, dict):
                for m_id, m_val in modes_data.items():
                    if isinstance(m_val, dict):
                        modes[m_id] = ModeConfig(
                            name=str(m_val.get("name", m_id.capitalize())),
                            description=str(m_val.get("description", "")),
                        )
            if not modes:
                modes = {
                    "normal": ModeConfig(name="Normal", description="Mode standard Windows (les touches fonctionnent normalement)."),
                    "special": ModeConfig(name="Spécial", description="Mode Alfred (les touches interceptées déclenchent des actions et raccourcis)."),
                    "grid": ModeConfig(name="Grille", description="Mode grille (déplacement rapide du curseur souris par zone d'écran)."),
                }

            mouse_data = data.get("mouse", {})
            raw_def = mouse_data.get("default_speed", 10)
            raw_use_sys = mouse_data.get("use_system_speed")

            if isinstance(raw_def, str) and raw_def.lower() in ("windows", "system", "auto"):
                use_sys = True
                def_spd = 10
            else:
                try:
                    def_spd = int(raw_def)
                except (ValueError, TypeError):
                    def_spd = 10
                use_sys = bool(raw_use_sys) if raw_use_sys is not None else True

            mouse = MouseConfig(
                use_system_speed=use_sys,
                default_speed=def_spd,
            )

            ui_data = data.get("ui", {})
            ui = UIConfig(
                theme=ui_data.get("theme", "dark"),
                color_theme=ui_data.get("color_theme", "blue"),
                font_size=int(ui_data.get("font_size", 13)),
                always_on_top=bool(ui_data.get("always_on_top", True)),
                start_minimized=bool(ui_data.get("start_minimized", True)),
                show_screen_indicator=bool(ui_data.get("show_screen_indicator", True)),
                screen_indicator_offset_x=int(ui_data.get("screen_indicator_offset_x", 12)),
                screen_indicator_offset_y=int(ui_data.get("screen_indicator_offset_y", 12)),
                screen_indicator_size=int(ui_data.get("screen_indicator_size", 20)),
            )

            self.app_config = AppConfig(general=general, modes=modes, mouse=mouse, ui=ui)
        except Exception as err:
            logger.error("Erreur lors du chargement de %s: %s", self.config_path, err)
            self.app_config = AppConfig()

        return self.app_config

    def save_app_config(self) -> bool:
        """Sauvegarde les paramètres actuels dans settings/config.toml."""
        try:
            self.settings_dir.mkdir(parents=True, exist_ok=True)
            gen_dict: dict[str, Any] = {
                "app_name": self.app_config.general.app_name,
                "default_mode": self.app_config.general.default_mode,
                "start_in_special_mode": self.app_config.general.start_in_special_mode,
                "auto_exit_on_text_input": self.app_config.general.auto_exit_on_text_input,
                "auto_return_on_enter": self.app_config.general.auto_return_on_enter,
                "quit": self.app_config.general.quit,
            }
            if self.app_config.general.special_mode_key:
                gen_dict["special_mode_key"] = self.app_config.general.special_mode_key

            data = {
                "general": gen_dict,
                "modes": {
                    m_id: {
                        "name": m_cfg.name,
                        "description": m_cfg.description,
                    }
                    for m_id, m_cfg in self.app_config.modes.items()
                },
                "mouse": {
                    "use_system_speed": self.app_config.mouse.use_system_speed,
                    "default_speed": self.app_config.mouse.default_speed,
                },
                "ui": {
                    "theme": self.app_config.ui.theme,
                    "color_theme": self.app_config.ui.color_theme,
                    "font_size": self.app_config.ui.font_size,
                    "always_on_top": self.app_config.ui.always_on_top,
                    "start_minimized": self.app_config.ui.start_minimized,
                    "show_screen_indicator": self.app_config.ui.show_screen_indicator,
                    "screen_indicator_offset_x": self.app_config.ui.screen_indicator_offset_x,
                    "screen_indicator_offset_y": self.app_config.ui.screen_indicator_offset_y,
                    "screen_indicator_size": self.app_config.ui.screen_indicator_size,
                },
            }
            with open(self.config_path, "wb") as f:
                tomli_w.dump(data, f)
            return True
        except Exception as err:
            logger.error("Erreur lors de la sauvegarde de %s: %s", self.config_path, err)
            return False

    def load_grid_config(self) -> GridConfig:
        """Charge settings/grid.toml."""
        if not self.grid_path.exists():
            self.grid_config = GridConfig()
            return self.grid_config

        try:
            with open(self.grid_path, "rb") as f:
                data = tomllib.load(f)
            self.grid_config = GridConfig.from_dict(data)
        except Exception as err:
            logger.error("Erreur lors du chargement de %s: %s", self.grid_path, err)
            self.grid_config = GridConfig()

        return self.grid_config

    def load_move_config(self) -> MoveConfig:
        """Charge settings/move.toml."""
        if not self.move_path.exists():
            self.move_config = MoveConfig()
            return self.move_config

        try:
            with open(self.move_path, "rb") as f:
                data = tomllib.load(f)
            self.move_config = MoveConfig.from_dict(data)
        except Exception as err:
            logger.error("Erreur lors du chargement de %s: %s", self.move_path, err)
            self.move_config = MoveConfig()

        return self.move_config

    def load_actions(self) -> list[Action]:
        """Scanne le répertoire settings/actions/ et charge toutes les actions TOML valides.
        Supporte aussi bien une seule action par fichier que plusieurs actions
        via la syntaxe standard [[actions]], [actions.nom], ou sections multiples.
        """
        self.actions = []
        if not self.actions_dir.exists():
            self.actions_dir.mkdir(parents=True, exist_ok=True)
            return self.actions

        for file_path in sorted(self.actions_dir.glob("*.toml")):
            try:
                with open(file_path, "rb") as f:
                    data = tomllib.load(f)
                file_actions = self._parse_actions_from_data(data, file_path)
                self.actions.extend(file_actions)
            except Exception as err:
                logger.error("Erreur lors de la lecture des actions dans %s: %s", file_path, err)

        logger.info("%d action(s) chargée(s) depuis %s", len(self.actions), self.actions_dir)
        return self.actions

    def _parse_actions_from_data(self, data: dict[str, Any], file_path: Path) -> list[Action]:
        """Extrait une ou plusieurs actions d'un contenu TOML analysé."""
        parsed_actions: list[Action] = []

        # 1. Syntaxe multi-actions standard TOML : [[actions]]
        if "actions" in data:
            raw_actions = data["actions"]
            if isinstance(raw_actions, list):
                for item in raw_actions:
                    if isinstance(item, dict):
                        parsed_actions.append(Action.from_dict(item))
            elif isinstance(raw_actions, dict):
                # 2. Syntaxe sous forme de tables : [actions.nom_action]
                for key, item in raw_actions.items():
                    if isinstance(item, dict):
                        if "name" not in item:
                            item["name"] = str(key)
                        parsed_actions.append(Action.from_dict(item))

        # 3. Tables nommées directes : [action_copier] ... [action_coller]
        if not parsed_actions:
            for key, val in data.items():
                if isinstance(val, dict) and ("trigger" in val or "commands" in val or "states" in val):
                    if "name" not in val:
                        val["name"] = str(key)
                    parsed_actions.append(Action.from_dict(val))

        # 4. Action unique à la racine du fichier (compatibilité ascendante)
        if not parsed_actions and ("trigger" in data or "commands" in data or "states" in data or "name" in data):
            parsed_actions.append(Action.from_dict(data))

        return parsed_actions

    def load_references(self) -> None:
        """Charge les notices d'aide settings/commands.toml et settings/keys.toml."""
        if self.commands_path.exists():
            try:
                with open(self.commands_path, "rb") as f:
                    self.commands_reference = tomllib.load(f)
            except Exception as err:
                logger.warning("Impossible de lire commands.toml: %s", err)

        if self.keys_path.exists():
            try:
                with open(self.keys_path, "rb") as f:
                    self.keys_reference = tomllib.load(f)
            except Exception as err:
                logger.warning("Impossible de lire keys.toml: %s", err)

    def get_action_for_key(self, key_name: str, mode: str) -> Action | None:
        """Trouve l'action correspondant à une touche dans un mode donné."""
        normalized_key = key_name.lower().strip()
        normalized_mode = mode.lower().strip()

        for act in self.actions:
            if (act.triggers and normalized_key in act.triggers) or act.trigger.lower().strip() == normalized_key:
                # Vérifier si l'action est active dans ce mode (ou mode 'all')
                act_modes = [m.lower().strip() for m in act.modes]
                if "all" in act_modes or normalized_mode in act_modes:
                    return act
        return None
