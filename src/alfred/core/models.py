"""Modèles de données typés pour Alfred."""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any


def _normalize_params_from_list(cmd_type: str, items: list[Any]) -> dict[str, Any]:
    """Convertit un tableau de paramètres positionnels en dictionnaire nommé selon le type de commande."""
    t = cmd_type.lower().strip()
    match t:
        case "hotkey":
            if items and isinstance(items[0], list):
                return {"keys": items[0]}
            return {"keys": items}
        case "click":
            res = {}
            if len(items) >= 1:
                res["button"] = items[0]
            if len(items) >= 2:
                res["clicks"] = items[1]
            if len(items) >= 4:
                res["x"] = items[2]
                res["y"] = items[3]
            return res
        case "middle_click":
            return {}
        case "jump":
            res = {}
            if len(items) >= 1:
                res["x"] = items[0]
            if len(items) >= 2:
                res["y"] = items[1]
            if len(items) >= 3:
                res["relative"] = items[2]
            return res
        case "mode":
            res = {}
            if len(items) >= 1:
                res["target"] = items[0]
            if len(items) >= 2:
                res["toggle_with"] = items[1]
            return res
        case "mouse_speed":
            res = {}
            if len(items) >= 1:
                res["speed"] = items[0]
            if len(items) >= 2:
                res["toggle"] = items[1]
            return res
        case "app":
            res = {}
            if len(items) >= 1:
                res["command"] = items[0]
            if len(items) >= 2:
                res["args"] = items[1]
            return res
        case "sleep":
            return {"duration": items[0]} if items else {"duration": 0.1}
        case "text":
            return {"content": items[0]} if items else {"content": ""}
        case "grid_cell":
            res = {}
            if len(items) >= 1:
                res["col"] = items[0]
            if len(items) >= 2:
                res["row"] = items[1]
            return res
        case _:
            return {"args": items}


@dataclass
class Command:
    """Représente une commande unitaire à exécuter."""
    type: str
    params: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | list[Any]) -> Command:
        """Parse une commande sous forme de dictionnaire ou d'array [type, params]."""
        # Support array: ["hotkey", ["ctrl", "t"]] ou ["sleep", 0.15]
        if isinstance(data, list):
            if not data:
                return cls(type="unknown")
            cmd_type = str(data[0])
            raw_p = data[1] if len(data) > 1 else []
            if isinstance(raw_p, list):
                params = _normalize_params_from_list(cmd_type, raw_p)
            elif isinstance(raw_p, dict):
                params = raw_p
            else:
                params = _normalize_params_from_list(cmd_type, [raw_p])
            return cls(type=cmd_type, params=params)

        # Support dictionnaire: { type = "...", ... }
        cmd_type = str(data.get("type", "unknown"))

        # Si params est fourni explicitement
        if "params" in data:
            raw_params = data["params"]
            if isinstance(raw_params, list):
                params = _normalize_params_from_list(cmd_type, raw_params)
            elif isinstance(raw_params, dict):
                params = dict(raw_params)
            else:
                params = _normalize_params_from_list(cmd_type, [raw_params])
        else:
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
                if isinstance(cmd_data, (dict, list)):
                    commands.append(Command.from_dict(cmd_data))

        states: list[ActionState] = []
        raw_states = data.get("states", {})
        if isinstance(raw_states, list):
            for idx, state_data in enumerate(raw_states):
                if isinstance(state_data, dict):
                    state_name = state_data.get("name", f"État {idx}")
                    state_cmds = [Command.from_dict(c) for c in state_data.get("commands", []) if isinstance(c, (dict, list))]
                    states.append(ActionState(name=state_name, commands=state_cmds))
        elif isinstance(raw_states, dict):
            for key in sorted(raw_states.keys(), key=lambda x: str(x)):
                state_data = raw_states[key]
                if isinstance(state_data, dict):
                    state_name = state_data.get("name", f"État {key}")
                    state_cmds = [Command.from_dict(c) for c in state_data.get("commands", []) if isinstance(c, (dict, list))]
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
