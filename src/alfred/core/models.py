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
        case "move_boost" | "move_speed_boost":
            res = {}
            if len(items) >= 1:
                res["toggle"] = items[0]
            if len(items) >= 2:
                res["multiplier"] = items[1]
            return res if res else {"toggle": True}
        case "move_grid_toggle" | "move_grid":
            return {"toggle": items[0]} if items else {"toggle": True}
        case "move_grid_cell":
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
    triggers: set[str] = field(default_factory=set)
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

        raw_trigger = data.get("trigger", data.get("triggers", ""))
        triggers: set[str] = set()
        if isinstance(raw_trigger, list):
            for t in raw_trigger:
                triggers.update(generate_key_aliases(str(t)))
            trigger = ", ".join(str(t).strip() for t in raw_trigger if str(t).strip()).lower()
        else:
            raw_s = str(raw_trigger).strip()
            trigger = raw_s.lower()
            if "," in raw_s and raw_s != ",":
                for t in raw_s.split(","):
                    if t.strip():
                        triggers.update(generate_key_aliases(t.strip()))
            elif raw_s:
                triggers.update(generate_key_aliases(raw_s))

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
            triggers=triggers,
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
    edge_snap_enabled: bool = False
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

        # Paramètres de rapprochement vers les bords (Edge Snap - rétrocompatibilité, déplacé dans MoveConfig)
        edge_snap_enabled = bool(grid_data.get("edge_snap_enabled", False))
        raw_edge_key = grid_data.get("edge_snap_key", grid_data.get("edge_key", grid_data.get("snap_key", "à")))
        if isinstance(raw_edge_key, list):
            edge_snap_key = ", ".join(str(k) for k in raw_edge_key)
            key_candidates = [str(k).lower().strip() for k in raw_edge_key if str(k).strip()]
        else:
            edge_snap_key = str(raw_edge_key).strip()
            if edge_snap_key == ",":
                key_candidates = [","]
            else:
                key_candidates = [k.lower().strip() for k in edge_snap_key.split(",") if k.strip()]
                if not key_candidates and "," in edge_snap_key:
                    key_candidates = [","]

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
            elif cand in (",", "virgule", "comma"):
                edge_snap_keys.update([",", "virgule", "comma"])
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
            subgrid_candidates = [str(k).lower().strip() for k in raw_subgrid_key if str(k).strip()]
        else:
            subgrid_toggle_key = str(raw_subgrid_key).strip()
            if subgrid_toggle_key == ",":
                subgrid_candidates = [","]
            else:
                subgrid_candidates = [k.lower().strip() for k in subgrid_toggle_key.split(",") if k.strip()]
                if not subgrid_candidates and "," in subgrid_toggle_key:
                    subgrid_candidates = [","]

        subgrid_columns = max(1, int(grid_data.get("subgrid_columns", 3)))
        subgrid_rows = max(1, int(grid_data.get("subgrid_rows", 3)))
        subgrid_exit_after_jump = bool(grid_data.get("subgrid_exit_after_jump", False))

        subgrid_toggle_keys: set[str] = set()
        for cand in subgrid_candidates:
            if not cand:
                continue
            subgrid_toggle_keys.add(cand)
            if cand in (",", "virgule", "comma"):
                subgrid_toggle_keys.update([",", "virgule", "comma"])

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


def generate_key_aliases(key: str | list[str]) -> set[str]:
    """Génère tous les alias courants pour une touche ou une liste de touches (chiffre, pavé numérique, séparateurs)."""
    raw_items = key if isinstance(key, list) else [key]
    keys: list[str] = []
    for item in raw_items:
        s = str(item).strip()
        if "," in s and s != ",":
            keys.extend([part.strip() for part in s.split(",") if part.strip()])
        elif s:
            keys.append(s)

    aliases: set[str] = set()
    for raw in keys:
        k = str(raw).lower().strip()
        if not k:
            continue
        aliases.add(k)
        if k in ("0", "num_0", "num 0", "à"):
            aliases.update(["0", "num_0", "num 0", "0 (pavé num.)", "0 (pave num.)", "à"])
        elif k in ("decimal", ".", ",", "point", "virgule"):
            aliases.update([
                "decimal",
                ".",
                ",",
                "point",
                "virgule",
                "decimal (pavé num.)",
                "decimal (pave num.)",
                ". (pavé num.)",
                ". (pave num.)",
                ", (pavé num.)",
                ", (pave num.)",
                "num_decimal",
                "num decimal",
            ])
        elif k.startswith("num_") or k.startswith("num "):
            digit = k.replace("num_", "").replace("num ", "").strip()
            aliases.update([
                f"num_{digit}",
                f"num {digit}",
                f"{digit} (pave num.)",
                f"{digit} (pavé num.)",
                digit,
            ])
        elif k.isdigit():
            aliases.update([
                f"num_{k}",
                f"num {k}",
                f"{k} (pave num.)",
                f"{k} (pavé num.)",
                k,
            ])
    return aliases


@dataclass
class MoveConfig:
    """Configuration du déplacement dynamique du curseur au clavier."""
    enabled: bool = True
    active_modes: list[str] = field(default_factory=lambda: ["special"])

    key_up: str = "8"
    key_down: str = "5"
    key_left: str = "4"
    key_right: str = "6"

    key_up_left: str = "7"
    key_up_right: str = "9"
    key_down_left: str = "1"
    key_down_right: str = "3"

    initial_speed: float = 300.0
    max_speed: float = 1800.0
    acceleration_enabled: bool = True
    acceleration_time: float = 1.2
    curve: str = "ease_in_out"
    diagonal_ratio: float = 1.0
    update_interval_ms: int = 16

    boost_enabled: bool = True
    boost_toggle_key: str = "0"
    boost_multiplier: float = 2.5
    start_boosted: bool = False

    # Grille 3x3 sur Pavé Numérique (Move Grid)
    grid_enabled: bool = True
    grid_toggle_key: str = "decimal"
    grid_exit_after_jump: bool = False
    grid_cells: dict[str, tuple[int, int]] = field(default_factory=dict)
    keys_grid_toggle: set[str] = field(default_factory=set)

    # Rapprochement vers les bords de l'écran (Edge Snap)
    edge_snap_enabled: bool = True
    edge_snap_key: str = "e"
    edge_offset: int = 40
    edge_snap_keys: set[str] = field(default_factory=set)

    # Alias résolus pour test rapide
    keys_up: set[str] = field(default_factory=set)
    keys_down: set[str] = field(default_factory=set)
    keys_left: set[str] = field(default_factory=set)
    keys_right: set[str] = field(default_factory=set)
    keys_up_left: set[str] = field(default_factory=set)
    keys_up_right: set[str] = field(default_factory=set)
    keys_down_left: set[str] = field(default_factory=set)
    keys_down_right: set[str] = field(default_factory=set)
    keys_boost: set[str] = field(default_factory=set)
    all_move_keys: set[str] = field(default_factory=set)

    def __post_init__(self) -> None:
        """Initialise automatiquement les alias de touches s'ils ne sont pas fournis."""
        if not self.edge_snap_keys and self.edge_snap_key:
            self.edge_snap_keys = generate_key_aliases(self.edge_snap_key)
        if not self.keys_grid_toggle and self.grid_toggle_key:
            self.keys_grid_toggle = generate_key_aliases(self.grid_toggle_key)
        if not self.keys_up and self.key_up:
            self.keys_up = generate_key_aliases(self.key_up)
        if not self.keys_down and self.key_down:
            self.keys_down = generate_key_aliases(self.key_down)
        if not self.keys_left and self.key_left:
            self.keys_left = generate_key_aliases(self.key_left)
        if not self.keys_right and self.key_right:
            self.keys_right = generate_key_aliases(self.key_right)
        if not self.keys_up_left and self.key_up_left:
            self.keys_up_left = generate_key_aliases(self.key_up_left)
        if not self.keys_up_right and self.key_up_right:
            self.keys_up_right = generate_key_aliases(self.key_up_right)
        if not self.keys_down_left and self.key_down_left:
            self.keys_down_left = generate_key_aliases(self.key_down_left)
        if not self.keys_down_right and self.key_down_right:
            self.keys_down_right = generate_key_aliases(self.key_down_right)
        if not self.keys_boost and self.boost_toggle_key:
            self.keys_boost = generate_key_aliases(self.boost_toggle_key)
        if not self.all_move_keys:
            self.all_move_keys = (
                self.keys_up
                | self.keys_down
                | self.keys_left
                | self.keys_right
                | self.keys_up_left
                | self.keys_up_right
                | self.keys_down_left
                | self.keys_down_right
            )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MoveConfig:
        """Parse la table [move] du fichier settings/move.toml."""
        move_data = data.get("move", data)
        enabled = bool(move_data.get("enabled", True))

        raw_modes = move_data.get("active_modes", ["special"])
        if isinstance(raw_modes, str):
            active_modes = [raw_modes.lower().strip()]
        else:
            active_modes = [str(m).lower().strip() for m in raw_modes]

        def _parse_key_str(raw: Any, default: str) -> str:
            if raw is None:
                return default
            if isinstance(raw, list):
                return ", ".join(str(k).strip() for k in raw if str(k).strip())
            return str(raw).strip()

        key_up = _parse_key_str(move_data.get("key_up"), "8")
        key_down = _parse_key_str(move_data.get("key_down"), "5")
        key_left = _parse_key_str(move_data.get("key_left"), "4")
        key_right = _parse_key_str(move_data.get("key_right"), "6")

        key_up_left = _parse_key_str(move_data.get("key_up_left"), "7")
        key_up_right = _parse_key_str(move_data.get("key_up_right"), "9")
        key_down_left = _parse_key_str(move_data.get("key_down_left"), "1")
        key_down_right = _parse_key_str(move_data.get("key_down_right"), "3")

        initial_speed = max(10.0, float(move_data.get("initial_speed", 300.0)))
        max_speed = max(initial_speed, float(move_data.get("max_speed", 1800.0)))
        acceleration_enabled = bool(move_data.get("acceleration_enabled", True))
        acceleration_time = max(0.05, float(move_data.get("acceleration_time", 1.2)))
        curve = str(move_data.get("curve", "ease_in_out")).lower().strip()
        diagonal_ratio = max(0.1, float(move_data.get("diagonal_ratio", 1.0)))
        update_interval_ms = max(5, int(move_data.get("update_interval_ms", 16)))

        boost_enabled = bool(move_data.get("boost_enabled", True))
        boost_toggle_key = str(move_data.get("boost_toggle_key", "0")).strip()
        boost_multiplier = max(1.0, float(move_data.get("boost_multiplier", 2.5)))
        start_boosted = bool(move_data.get("start_boosted", False))

        grid_enabled = bool(move_data.get("grid_enabled", True))
        grid_toggle_key = str(move_data.get("grid_toggle_key", "decimal")).strip()
        grid_exit_after_jump = bool(move_data.get("grid_exit_after_jump", False))
        keys_grid_toggle = generate_key_aliases(grid_toggle_key)

        grid_cells_raw = move_data.get("grid_cells")
        if grid_cells_raw is None:
            grid_cells_raw = {
                "7": [0, 0], "8": [1, 0], "9": [2, 0],
                "4": [0, 1], "5": [1, 1], "6": [2, 1],
                "1": [0, 2], "2": [1, 2], "3": [2, 2],
            }

        grid_cells: dict[str, tuple[int, int]] = {}
        for cell_key, cell_coords in grid_cells_raw.items():
            if isinstance(cell_coords, (list, tuple)) and len(cell_coords) >= 2:
                coords = (int(cell_coords[0]), int(cell_coords[1]))
                for alias in generate_key_aliases(str(cell_key)):
                    grid_cells[alias] = coords

        keys_up = generate_key_aliases(key_up)
        keys_down = generate_key_aliases(key_down)
        keys_left = generate_key_aliases(key_left)
        keys_right = generate_key_aliases(key_right)
        keys_up_left = generate_key_aliases(key_up_left)
        keys_up_right = generate_key_aliases(key_up_right)
        keys_down_left = generate_key_aliases(key_down_left)
        keys_down_right = generate_key_aliases(key_down_right)
        keys_boost = generate_key_aliases(boost_toggle_key)

        # Rapprochement vers les bords de l'écran (Edge Snap)
        edge_snap_enabled = bool(move_data.get("edge_snap_enabled", True))
        raw_edge_key = move_data.get("edge_snap_key", move_data.get("edge_key", move_data.get("snap_key", "e")))
        if isinstance(raw_edge_key, list):
            edge_snap_key = ", ".join(str(k) for k in raw_edge_key)
            edge_snap_candidates = [str(k).lower().strip() for k in raw_edge_key if str(k).strip()]
        else:
            edge_snap_key = str(raw_edge_key).strip()
            if edge_snap_key == ",":
                edge_snap_candidates = [","]
            else:
                edge_snap_candidates = [k.lower().strip() for k in edge_snap_key.split(",") if k.strip()]
                if not edge_snap_candidates and "," in edge_snap_key:
                    edge_snap_candidates = [","]

        raw_offset = move_data.get(
            "edge_offset",
            move_data.get("steps", move_data.get("edge_distance", move_data.get("offset", 40)))
        )
        try:
            edge_offset = max(0, int(raw_offset))
        except (ValueError, TypeError):
            edge_offset = 40

        edge_snap_keys = generate_key_aliases(edge_snap_candidates)

        all_move_keys = (
            keys_up
            | keys_down
            | keys_left
            | keys_right
            | keys_up_left
            | keys_up_right
            | keys_down_left
            | keys_down_right
        )

        return cls(
            enabled=enabled,
            active_modes=active_modes,
            key_up=key_up,
            key_down=key_down,
            key_left=key_left,
            key_right=key_right,
            key_up_left=key_up_left,
            key_up_right=key_up_right,
            key_down_left=key_down_left,
            key_down_right=key_down_right,
            initial_speed=initial_speed,
            max_speed=max_speed,
            acceleration_enabled=acceleration_enabled,
            acceleration_time=acceleration_time,
            curve=curve,
            diagonal_ratio=diagonal_ratio,
            update_interval_ms=update_interval_ms,
            boost_enabled=boost_enabled,
            boost_toggle_key=boost_toggle_key,
            boost_multiplier=boost_multiplier,
            start_boosted=start_boosted,
            grid_enabled=grid_enabled,
            grid_toggle_key=grid_toggle_key,
            grid_exit_after_jump=grid_exit_after_jump,
            grid_cells=grid_cells,
            keys_grid_toggle=keys_grid_toggle,
            edge_snap_enabled=edge_snap_enabled,
            edge_snap_key=edge_snap_key,
            edge_offset=edge_offset,
            edge_snap_keys=edge_snap_keys,
            keys_up=keys_up,
            keys_down=keys_down,
            keys_left=keys_left,
            keys_right=keys_right,
            keys_up_left=keys_up_left,
            keys_up_right=keys_up_right,
            keys_down_left=keys_down_left,
            keys_down_right=keys_down_right,
            keys_boost=keys_boost,
            all_move_keys=all_move_keys,
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
    default_mode: str = "special"
    start_in_special_mode: bool = True
    close: str = "ctrl+w"
    quit: str = "ctrl+shift+q"
    special_mode_key: str = ""
    special_mode_name: str = "special"
    toggle_special_mode: bool = True
    auto_exit_on_text_input: bool = True
    auto_return_on_enter: bool = True

    @property
    def quit_key(self) -> str:
        return self.quit

    @quit_key.setter
    def quit_key(self, val: str) -> None:
        self.quit = val



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
    start_minimized: bool = True
    show_screen_indicator: bool = True
    screen_indicator_offset_x: int = 12
    screen_indicator_offset_y: int = 12
    screen_indicator_size: int = 20


@dataclass
class AppConfig:
    """Configuration globale regroupée."""
    general: GeneralConfig = field(default_factory=GeneralConfig)
    modes: dict[str, ModeConfig] = field(default_factory=dict)
    mouse: MouseConfig = field(default_factory=MouseConfig)
    ui: UIConfig = field(default_factory=UIConfig)
