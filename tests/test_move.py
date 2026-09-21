"""Tests unitaires pour le déplacement dynamique du curseur au clavier (MoveManager)."""

from __future__ import annotations
import time
from unittest.mock import MagicMock, patch
import pytest

from src.alfred.core.models import MoveConfig, Command
from src.alfred.core.move import MoveManager, _compute_curve_factor
from src.alfred.core.state import StateManager
from src.alfred.core.config import ConfigManager
from src.alfred.core.commands_engine import CommandsEngine
from src.alfred.core.hook import KeyboardHookService


def test_move_config_defaults():
    """Vérifie les valeurs par défaut de MoveConfig."""
    cfg = MoveConfig()
    assert cfg.enabled is True
    assert "special" in cfg.active_modes
    assert cfg.key_up == "8"
    assert cfg.key_down == "5"
    assert cfg.key_left == "4"
    assert cfg.key_right == "6"
    assert cfg.boost_toggle_key == "0"
    assert cfg.boost_multiplier == 2.5
    assert cfg.acceleration_enabled is True


def test_move_config_from_dict():
    """Vérifie la création de MoveConfig depuis un dictionnaire TOML."""
    data = {
        "move": {
            "enabled": True,
            "active_modes": ["special", "grid"],
            "key_up": "8",
            "key_down": "2",
            "key_left": "4",
            "key_right": "6",
            "initial_speed": 400.0,
            "max_speed": 2000.0,
            "acceleration_enabled": True,
            "acceleration_time": 1.5,
            "boost_toggle_key": "num_0",
            "boost_multiplier": 3.0,
        }
    }
    cfg = MoveConfig.from_dict(data)
    assert cfg.enabled is True
    assert cfg.active_modes == ["special", "grid"]
    assert cfg.key_down == "2"
    assert cfg.initial_speed == 400.0
    assert cfg.max_speed == 2000.0
    assert cfg.boost_multiplier == 3.0

    # Vérification des alias du pavé numérique générés automatiquement
    assert "8" in cfg.keys_up
    assert "num_8" in cfg.keys_up
    assert "num 8" in cfg.keys_up
    assert "8 (pavé num.)" in cfg.keys_up

    assert "num_0" in cfg.keys_boost
    assert "0" in cfg.keys_boost


def test_curve_factor_computation():
    """Vérifie le calcul mathématique des courbes d'accélération."""
    assert _compute_curve_factor(0.0, "linear") == 0.0
    assert _compute_curve_factor(1.0, "linear") == 1.0
    assert _compute_curve_factor(0.5, "linear") == 0.5

    assert _compute_curve_factor(0.5, "ease_in") == pytest.approx(0.25)
    assert _compute_curve_factor(1.0, "ease_in") == pytest.approx(1.0)

    # Clamping
    assert _compute_curve_factor(-0.5, "linear") == 0.0
    assert _compute_curve_factor(1.5, "linear") == 1.0


def test_move_manager_directions_and_boost():
    """Vérifie la détection des directions et le toggle boost."""
    cfg = MoveConfig.from_dict({
        "move": {
            "key_up": "8",
            "key_down": "5",
            "key_left": "4",
            "key_right": "6",
            "key_up_left": "7",
            "boost_toggle_key": "0",
            "boost_multiplier": 2.5,
        }
    })
    mock_mouse = MagicMock()
    state_mgr = StateManager()

    mgr = MoveManager(config=cfg, mouse_controller=mock_mouse, state_manager=state_mgr)
    try:
        # Touche boost
        assert mgr.is_boost_key("0") is True
        assert mgr.is_boost_key("num_0") is True
        assert mgr.is_boost_key("1") is False

        assert mgr.is_boosted is False
        new_state = mgr.toggle_boost()
        assert new_state is True
        assert mgr.is_boosted is True
        assert mgr.toggle_boost() is False
        assert mgr.is_boosted is False

        # Touches de direction
        assert mgr.is_move_key("8") is True
        assert mgr.is_move_key("num_8") is True
        assert mgr.is_move_key("5") is True
        assert mgr.is_move_key("4") is True
        assert mgr.is_move_key("6") is True
        assert mgr.is_move_key("7") is True
        assert mgr.is_move_key("a") is False

        # Directions cardinales
        assert mgr.get_directions_for_key("8") == {"up"}
        assert mgr.get_directions_for_key("5") == {"down"}
        assert mgr.get_directions_for_key("4") == {"left"}
        assert mgr.get_directions_for_key("6") == {"right"}
        assert mgr.get_directions_for_key("7") == {"up", "left"}

        # Appui et relâchement
        assert mgr.press_key("8") is True
        with mgr._lock:
            assert "up" in mgr._active_directions
        assert mgr.release_key("8") is True
        with mgr._lock:
            assert "up" not in mgr._active_directions

    finally:
        mgr.stop()


def test_commands_engine_move_boost():
    """Vérifie l'exécution de la commande move_boost via CommandsEngine."""
    cfg = MoveConfig()
    mock_mouse = MagicMock()
    state_mgr = StateManager()
    mgr = MoveManager(config=cfg, mouse_controller=mock_mouse, state_manager=state_mgr)

    grid_mgr = MagicMock()
    config_mgr = MagicMock()
    engine = CommandsEngine(
        state_manager=state_mgr,
        grid_manager=grid_mgr,
        config_manager=config_mgr,
        move_manager=mgr,
    )

    try:
        assert mgr.is_boosted is False
        # Toggle via commande
        cmd_toggle = Command(type="move_boost", params={"toggle": True})
        engine.execute_command(cmd_toggle)
        assert mgr.is_boosted is True

        # Désactiver explicitement
        cmd_off = Command(type="move_boost", params={"active": False})
        engine.execute_command(cmd_off)
        assert mgr.is_boosted is False

        # Activer explicitement
        cmd_on = Command(type="move_boost", params={"active": True})
        engine.execute_command(cmd_on)
        assert mgr.is_boosted is True
    finally:
        mgr.stop()


def test_hook_service_move_key_interception():
    """Vérifie que les touches de déplacement ne sont interceptées qu'en mode spécial."""
    config_mgr = ConfigManager()
    config_mgr.load_all()

    state_mgr = StateManager(initial_mode="normal")
    mock_mouse = MagicMock()
    move_mgr = MoveManager(
        config=config_mgr.move_config,
        mouse_controller=mock_mouse,
        state_manager=state_mgr,
    )
    grid_mgr = MagicMock()
    commands_engine = MagicMock()

    hook = KeyboardHookService(
        state_manager=state_mgr,
        config_manager=config_mgr,
        commands_engine=commands_engine,
        grid_manager=grid_mgr,
        move_manager=move_mgr,
    )

    try:
        # En mode 'normal', les touches de déplacement (ex: 8) doivent passer (retourner True)
        mock_event_down_normal = MagicMock()
        mock_event_down_normal.name = "8"
        mock_event_down_normal.event_type = "down"
        mock_event_down_normal.scan_code = 100
        assert hook._on_key_event(mock_event_down_normal) is True

        # Basculer en mode 'special'
        state_mgr.set_mode("special")

        # En mode 'special', la touche 8 doit être interceptée (retourner False)
        mock_event_down_special = MagicMock()
        mock_event_down_special.name = "8"
        mock_event_down_special.event_type = "down"
        mock_event_down_special.scan_code = 100
        assert hook._on_key_event(mock_event_down_special) is False
        with move_mgr._lock:
            assert "up" in move_mgr._active_directions

        # Le relâchement (KEY_UP) de la touche 8 doit aussi être intercepté
        mock_event_up_special = MagicMock()
        mock_event_up_special.name = "8"
        mock_event_up_special.event_type = "up"
        mock_event_up_special.scan_code = 100
        assert hook._on_key_event(mock_event_up_special) is False
        with move_mgr._lock:
            assert "up" not in move_mgr._active_directions

        # La touche Boost doit être interceptée et basculer l'état
        boost_key = config_mgr.move_config.boost_toggle_key
        assert move_mgr.is_boosted is False
        mock_event_boost = MagicMock()
        mock_event_boost.name = boost_key
        mock_event_boost.event_type = "down"
        mock_event_boost.scan_code = 101
        assert hook._on_key_event(mock_event_boost) is False
        assert move_mgr.is_boosted is True

        # Test de la bascule vers la Grille Pavé Numérique
        grid_key = config_mgr.move_config.grid_toggle_key
        assert move_mgr.is_grid_active is False

        mock_event_grid_toggle = MagicMock()
        mock_event_grid_toggle.name = grid_key
        mock_event_grid_toggle.event_type = "down"
        mock_event_grid_toggle.scan_code = 102
        assert hook._on_key_event(mock_event_grid_toggle) is False
        assert move_mgr.is_grid_active is True

        # En mode grille pavé numérique, presser 7 saute au centre de la case (0, 0)
        with patch.object(move_mgr, "jump_grid_by_key") as mock_jump:
            mock_event_cell7 = MagicMock()
            mock_event_cell7.name = "7"
            mock_event_cell7.event_type = "down"
            mock_event_cell7.scan_code = 103
            assert hook._on_key_event(mock_event_cell7) is False
            time.sleep(0.05)  # Laisser le thread worker démarrer
            mock_jump.assert_called_with("7")

        # Le relâchement d'une case de grille est également intercepté
        mock_event_cell7_up = MagicMock()
        mock_event_cell7_up.name = "7"
        mock_event_cell7_up.event_type = "up"
        mock_event_cell7_up.scan_code = 103
        assert hook._on_key_event(mock_event_cell7_up) is False

        # Relâchement de la touche toggle initiale
        mock_event_grid_toggle_up = MagicMock()
        mock_event_grid_toggle_up.name = grid_key
        mock_event_grid_toggle_up.event_type = "up"
        mock_event_grid_toggle_up.scan_code = 102
        assert hook._on_key_event(mock_event_grid_toggle_up) is False

        # Rappui sur la touche toggle : désactive la grille et restaure le déplacement
        mock_event_grid_toggle2 = MagicMock()
        mock_event_grid_toggle2.name = grid_key
        mock_event_grid_toggle2.event_type = "down"
        mock_event_grid_toggle2.scan_code = 104
        assert hook._on_key_event(mock_event_grid_toggle2) is False
        assert move_mgr.is_grid_active is False

        # Désormais, 7 reprend son rôle de déplacement curseur (up_left)
        mock_event_cell7_move = MagicMock()
        mock_event_cell7_move.name = "7"
        mock_event_cell7_move.event_type = "down"
        mock_event_cell7_move.scan_code = 105
        assert hook._on_key_event(mock_event_cell7_move) is False
        with move_mgr._lock:
            assert "up" in move_mgr._active_directions
            assert "left" in move_mgr._active_directions

    finally:
        move_mgr.stop()


def test_move_worker_relative_displacement():
    """Vérifie que la boucle worker déclenche des appels réels à mouse.move_relative."""
    cfg = MoveConfig.from_dict({
        "move": {
            "enabled": True,
            "key_up": "8",
            "initial_speed": 1000.0,
            "acceleration_enabled": False,
            "update_interval_ms": 10,
        }
    })
    mock_mouse = MagicMock()
    state_mgr = StateManager()

    mgr = MoveManager(config=cfg, mouse_controller=mock_mouse, state_manager=state_mgr)
    try:
        mgr.press_key("8")
        # Laisser la boucle tourner pendant ~50ms
        time.sleep(0.06)
        mgr.release_key("8")

        # mouse.move_relative doit avoir été appelé avec dy négatif (vers le haut)
        assert mock_mouse.move_relative.called
        calls = mock_mouse.move_relative.call_args_list
        assert len(calls) > 0
        total_dx = sum(c[0][0] for c in calls)
        total_dy = sum(c[0][1] for c in calls)
        assert total_dx == 0
        assert total_dy < 0  # déplacement vers le haut
    finally:
        mgr.stop()


def test_move_grid_config():
    """Vérifie le chargement de la configuration de la grille 3x3 dans MoveConfig."""
    data = {
        "move": {
            "grid_enabled": True,
            "grid_toggle_key": "decimal",
            "grid_exit_after_jump": True,
            "grid_cells": {
                "7": [0, 0],
                "8": [1, 0],
                "3": [2, 2],
            }
        }
    }
    cfg = MoveConfig.from_dict(data)
    assert cfg.grid_enabled is True
    assert cfg.grid_toggle_key == "decimal"
    assert cfg.grid_exit_after_jump is True

    # Vérification des alias
    assert "decimal" in cfg.keys_grid_toggle
    assert "." in cfg.keys_grid_toggle
    assert "7" in cfg.grid_cells
    assert "num_7" in cfg.grid_cells
    assert cfg.grid_cells["7"] == (0, 0)
    assert cfg.grid_cells["num_8"] == (1, 0)
    assert cfg.grid_cells["3"] == (2, 2)


def test_move_grid_manager_calculations_and_jump():
    """Vérifie le calcul géométrique et le saut de grille dans MoveManager."""
    cfg = MoveConfig.from_dict({
        "move": {
            "grid_enabled": True,
            "grid_toggle_key": "decimal",
            "grid_cells": {
                "7": [0, 0],
                "8": [1, 0],
                "3": [2, 2],
            }
        }
    })
    mock_mouse = MagicMock()
    mock_mouse.get_screen_size.return_value = (1920, 1080)
    state_mgr = StateManager()

    mgr = MoveManager(config=cfg, mouse_controller=mock_mouse, state_manager=state_mgr)
    try:
        # Grille 3x3 sur 1920x1080:
        # Cell width = 640, height = 360
        # (0, 0) -> cx = 320, cy = 180 (7)
        # (1, 0) -> cx = 960, cy = 180 (8)
        # (2, 2) -> cx = 1600, cy = 900 (3)
        assert mgr.get_grid_cell_center(0, 0) == (320, 180)
        assert mgr.get_grid_cell_center(1, 0) == (960, 180)
        assert mgr.get_grid_cell_center(2, 2) == (1600, 900)

        # Saut direct par coordonnées
        res = mgr.jump_grid_cell(0, 0)
        assert res == (320, 180)
        mock_mouse.set_position.assert_called_with(320, 180)

        # Saut par touche
        res_key = mgr.jump_grid_by_key("8")
        assert res_key == (960, 180)
        mock_mouse.set_position.assert_called_with(960, 180)

        res_key3 = mgr.jump_grid_by_key("num_3")
        assert res_key3 == (1600, 900)
        mock_mouse.set_position.assert_called_with(1600, 900)

        # Test toggle
        assert mgr.is_grid_active is False
        assert mgr.toggle_grid() is True
        assert mgr.is_grid_active is True
        assert mgr.toggle_grid() is False
        assert mgr.is_grid_active is False
    finally:
        mgr.stop()


def test_move_grid_engine_commands():
    """Vérifie l'exécution des commandes move_grid_toggle et move_grid_cell via CommandsEngine."""
    cfg = MoveConfig()
    mock_mouse = MagicMock()
    mock_mouse.get_screen_size.return_value = (1920, 1080)
    state_mgr = StateManager()
    config_mgr = ConfigManager()
    grid_mgr = MagicMock()
    move_mgr = MoveManager(config=cfg, mouse_controller=mock_mouse, state_manager=state_mgr)

    engine = CommandsEngine(
        state_manager=state_mgr,
        grid_manager=grid_mgr,
        config_manager=config_mgr,
        move_manager=move_mgr,
    )
    try:
        assert move_mgr.is_grid_active is False

        # Commande move_grid_toggle
        engine.execute_command(Command(type="move_grid_toggle"))
        assert move_mgr.is_grid_active is True

        engine.execute_command(Command(type="move_grid_toggle", params={"active": False}))
        assert move_mgr.is_grid_active is False

        # Commande move_grid_cell
        engine.execute_command(Command(type="move_grid_cell", params={"col": 1, "row": 0}))
        mock_mouse.set_position.assert_called_with(960, 180)
    finally:
        move_mgr.stop()

