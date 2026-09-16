"""Modèles de données typés pour Alfred."""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Command:
    """Représente une commande unitaire à exécuter."""
    type: str
    params: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Command:
        cmd_type = data.get("type", "unknown")
        params = {k: v for k, v in data.items() if k != "type"}
        return cls(type=cmd_type, params=params)


@dataclass
class ActionState:
    """Représente un état au sein d'une action de type toggle."""
    name: str = ""
    commands: list[Command] = field(default_factory=list)


@dataclass
class Action:
    """Représente une action complète déclenchée par une touche."""
    name: str
    description: str = ""
    modes: list[str] = field(default_factory=lambda: ["special"])
    trigger: str = ""
    commands: list[Command] = field(default_factory=list)
    toggle: bool = False
    states: list[ActionState] = field(default_factory=list)
    current_state_index: int = 0

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Action:
        name = data.get("name", "Action sans nom")
        description = data.get("description", "")
        modes = data.get("modes", ["special"])
        if isinstance(modes, str):
            modes = [modes]
        trigger = str(data.get("trigger", "")).lower()
        toggle = bool(data.get("toggle", False))

        commands: list[Command] = []
        raw_commands = data.get("commands", [])
        if isinstance(raw_commands, list):
            for cmd_data in raw_commands:
                if isinstance(cmd_data, dict):
                    commands.append(Command.from_dict(cmd_data))

        states: list[ActionState] = []
        raw_states = data.get("states", {})
        if isinstance(raw_states, dict):
            for key in sorted(raw_states.keys(), key=lambda x: str(x)):
                state_data = raw_states[key]
                state_name = state_data.get("name", f"État {key}")
                state_cmds: list[Command] = []
                for scmd in state_data.get("commands", []):
                    if isinstance(scmd, dict):
                        state_cmds.append(Command.from_dict(scmd))
                states.append(ActionState(name=state_name, commands=state_cmds))

        return cls(
            name=name,
            description=description,
            modes=modes,
            trigger=trigger,
            commands=commands,
            toggle=toggle,
            states=states,
        )


@dataclass
class GridConfig:
    """Configuration de la grille d'écran."""
    enabled: bool = True
    columns: int = 3
    rows: int = 3
    active_modes: list[str] = field(default_factory=lambda: ["grid", "special"])
    exit_mode_after_jump: bool = False
    auto_click: bool = False
    cells: dict[str, tuple[int, int]] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GridConfig:
        grid_data = data.get("grid", {})
        enabled = bool(grid_data.get("enabled", True))
        columns = max(1, int(grid_data.get("columns", 3)))
        rows = max(1, int(grid_data.get("rows", 3)))
        active_modes = grid_data.get("active_modes", ["grid", "special"])
        if isinstance(active_modes, str):
            active_modes = [active_modes]
        exit_mode = bool(grid_data.get("exit_mode_after_jump", False))
        auto_click = bool(grid_data.get("auto_click", False))

        cells: dict[str, tuple[int, int]] = {}
        cells_data = data.get("cells", {})
        for key, coords in cells_data.items():
            if isinstance(coords, (list, tuple)) and len(coords) >= 2:
                cells[str(key).lower()] = (int(coords[0]), int(coords[1]))

        return cls(
            enabled=enabled,
            columns=columns,
            rows=rows,
            active_modes=active_modes,
            exit_mode_after_jump=exit_mode,
            auto_click=auto_click,
            cells=cells,
        )


@dataclass
class GeneralConfig:
    """Configuration générale du système."""
    app_name: str = "Alfred"
    default_mode: str = "normal"
    special_mode_key: str = "!"
    special_mode_name: str = "special"
    toggle_special_mode: bool = True


@dataclass
class MouseConfig:
    """Paramètres du comportement souris."""
    default_speed: int = 10
    fast_speed: int = 18


@dataclass
class UIConfig:
    """Paramètres visuels de l'interface utilisateur."""
    theme: str = "dark"
    color_theme: str = "blue"
    font_size: int = 13
    always_on_top: bool = True
    start_minimized: bool = False


@dataclass
class AppConfig:
    """Configuration globale regroupée."""
    general: GeneralConfig = field(default_factory=GeneralConfig)
    mouse: MouseConfig = field(default_factory=MouseConfig)
    ui: UIConfig = field(default_factory=UIConfig)
