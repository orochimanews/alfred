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
        case "mouse_nudge" | "nudge":
            res = {}
            if len(items) >= 1:
                res["step"] = items[0]
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
        case "grid_cell" | "subgrid_cell":
            res = {}
            if len(items) >= 1:
                res["col"] = items[0]
            if len(items) >= 2:
                res["row"] = items[1]
            return res
        case "subgrid":
            return {"toggle": items[0]} if items else {"toggle": True}
        case "edge_snap" | "grid_edge_snap":
            res = {}
            if len(items) >= 1:
                res["offset"] = items[0]
            return res
        case "scroll" | "wheel":
            return {"delta": items[0]} if items else {"delta": 1}
        case "mouse_down":
            return {"button": items[0]} if items else {"button": "left"}
        case "mouse_up":
            return {"button": items[0]} if items else {"button": "left"}
        case "zoom":
            res = {}
            if len(items) >= 1:
                res["direction"] = items[0]
            if len(items) >= 2:
                res["steps"] = items[1]
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
    edge_snap_enabled: bool = True
    edge_snap_key: str = "à"
    edge_offset: int = 10
    cells: dict[str, tuple[int, int]] = field(default_factory=dict)
    edge_snap_keys: set[str] = field(default_factory=set)
    subgrid_enabled: bool = True
    subgrid_toggle_key: str = "²"
    subgrid_columns: int = 3
    subgrid_rows: int = 3
    subgrid_exit_after_jump: bool = False
    subgrid_toggle_keys: set[str] = field(default_factory=set)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GridConfig:
        grid_data = data.get("grid", {})
        enabled = bool(grid_data.get("enabled", True))
        columns = max(1, int(grid_data.get("columns", 3)))
        rows = max(1, int(grid_data.get("rows", 3)))

        raw_modes = grid_data.get("active_modes", ["grid", "special"])
        if isinstance(raw_modes, str):
            active_modes = [m.strip() for m in raw_modes.split(",") if m.strip()]
        elif isinstance(raw_modes, list):
            parsed_modes = []
            for item in raw_modes:
                if isinstance(item, str):
                    for m in item.split(","):
                        if m.strip():
                            parsed_modes.append(m.strip())
            active_modes = parsed_modes
        else:
            active_modes = ["grid", "special"]

        exit_mode = bool(grid_data.get("exit_mode_after_jump", False))
        auto_click = bool(grid_data.get("auto_click", False))

        # Paramètres de rapprochement vers les bords (Edge Snap)
        edge_snap_enabled = bool(grid_data.get("edge_snap_enabled", True))
        raw_edge_key = grid_data.get("edge_snap_key", grid_data.get("edge_key", grid_data.get("snap_key", "à")))
        if isinstance(raw_edge_key, list):
            edge_snap_key = ", ".join(str(k) for k in raw_edge_key)
            key_candidates = [str(k).lower().strip() for k in raw_edge_key]
        else:
            edge_snap_key = str(raw_edge_key).strip()
            key_candidates = [k.lower().strip() for k in edge_snap_key.split(",") if k.strip()]

        raw_offset = grid_data.get(
            "edge_offset",
            grid_data.get("steps", grid_data.get("edge_distance", grid_data.get("offset", 10)))
        )
        try:
            edge_offset = max(0, int(raw_offset))
        except (ValueError, TypeError):
            edge_offset = 10

        edge_snap_keys: set[str] = set()
        for cand in key_candidates:
            if not cand:
                continue
            edge_snap_keys.add(cand)
            if cand in ("0", "num_0", "num 0", "à"):
                edge_snap_keys.update(["0", "num_0", "num 0", "0 (pavé num.)", "0 (pave num.)", "à"])
            elif cand.startswith("num_") or cand.startswith("num "):
                digit = cand.replace("num_", "").replace("num ", "").strip()
                edge_snap_keys.update([
                    f"num_{digit}",
                    f"num {digit}",
                    f"{digit} (pave num.)",
                    f"{digit} (pavé num.)",
                    digit,
                ])

        cells: dict[str, tuple[int, int]] = {}
        cells_data = data.get("cells", {})
        for key, coords in cells_data.items():
            if isinstance(coords, (list, tuple)) and len(coords) >= 2:
                k = str(key).lower().strip()
                cell_coords = (int(coords[0]), int(coords[1]))
                cells[k] = cell_coords

                # Générer automatiquement les alias pour les touches du pavé numérique
                if k.startswith("num_") or k.startswith("num "):
                    num_digit = k.replace("num_", "").replace("num ", "").strip()
                    aliases = [
                        f"num_{num_digit}",
                        f"num {num_digit}",
                        f"{num_digit} (pave num.)",
                        f"{num_digit} (pavé num.)",
                        num_digit,
                    ]
                    for alias in aliases:
                        if alias not in cells:
                            cells[alias] = cell_coords

        # Paramètres de sous-grille (Subgrid)
        subgrid_enabled = bool(grid_data.get("subgrid_enabled", True))
        raw_subgrid_key = grid_data.get("subgrid_toggle_key", grid_data.get("subgrid_key", "²"))
        if isinstance(raw_subgrid_key, list):
            subgrid_toggle_key = ", ".join(str(k) for k in raw_subgrid_key)
            subgrid_candidates = [str(k).lower().strip() for k in raw_subgrid_key]
        else:
            subgrid_toggle_key = str(raw_subgrid_key).strip()
            subgrid_candidates = [k.lower().strip() for k in subgrid_toggle_key.split(",") if k.strip()]

        subgrid_columns = max(1, int(grid_data.get("subgrid_columns", 3)))
        subgrid_rows = max(1, int(grid_data.get("subgrid_rows", 3)))
        subgrid_exit_after_jump = bool(grid_data.get("subgrid_exit_after_jump", False))

        subgrid_toggle_keys: set[str] = set()
        for cand in subgrid_candidates:
            if not cand:
                continue
            subgrid_toggle_keys.add(cand)

        return cls(
            enabled=enabled,
            columns=columns,
            rows=rows,
            active_modes=active_modes,
            exit_mode_after_jump=exit_mode,
            auto_click=auto_click,
            edge_snap_enabled=edge_snap_enabled,
            edge_snap_key=edge_snap_key,
            edge_offset=edge_offset,
            cells=cells,
            edge_snap_keys=edge_snap_keys,
            subgrid_enabled=subgrid_enabled,
            subgrid_toggle_key=subgrid_toggle_key,
            subgrid_columns=subgrid_columns,
            subgrid_rows=subgrid_rows,
            subgrid_exit_after_jump=subgrid_exit_after_jump,
            subgrid_toggle_keys=subgrid_toggle_keys,
        )


@dataclass
class ModeConfig:
    """Description et métadonnées d'un mode d'Alfred."""
    name: str = ""
    description: str = ""


@dataclass
class GeneralConfig:
    """Configuration générale du système."""
    app_name: str = "Alfred"
    default_mode: str = "normal"
    close: str = "ctrl+w"
    special_mode_key: str = ""
    special_mode_name: str = "special"
    toggle_special_mode: bool = True


@dataclass
class MouseConfig:
    """Paramètres du comportement souris."""
    use_system_speed: bool = True
    default_speed: int = 10


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
    modes: dict[str, ModeConfig] = field(default_factory=dict)
    mouse: MouseConfig = field(default_factory=MouseConfig)
    ui: UIConfig = field(default_factory=UIConfig)
