"""Tests unitaires pour le moteur de commandes."""

from unittest.mock import MagicMock, patch
from src.alfred.core.models import Command, Action, ActionState
from src.alfred.core.state import StateManager
from src.alfred.core.config import ConfigManager
from src.alfred.core.grid import GridManager
from src.alfred.core.commands_engine import CommandsEngine


def test_command_engine_mode_switch():
    state = StateManager(initial_mode="normal")
    cfg_mgr = ConfigManager()
    grid_mgr = MagicMock()
    engine = CommandsEngine(state, grid_mgr, cfg_mgr)

    # Exécution commande mode -> special
    cmd = Command(type="mode", params={"target": "special"})
    engine.execute_command(cmd)
    assert state.current_mode == "special"

    # Exécution commande mode toggle -> normal
    cmd_toggle = Command(type="mode", params={"target": "toggle", "toggle_with": "normal"})
    engine.execute_command(cmd_toggle)
    assert state.current_mode == "normal"


def test_command_engine_action_execution():
    state = StateManager(initial_mode="special")
    cfg_mgr = ConfigManager()
    grid_mgr = MagicMock()
    engine = CommandsEngine(state, grid_mgr, cfg_mgr)

    with patch("keyboard.send") as mock_send:
        action = Action(
            name="Test Hotkey",
            trigger="t",
            modes=["special"],
            commands=[Command(type="hotkey", params={"keys": ["ctrl", "t"]})],
        )
        res = engine.execute_action(action)
        assert res is True
        mock_send.assert_called_once_with("ctrl+t")
        assert len(state.logs) == 1
        assert state.logs[0].action_name == "Test Hotkey"


def test_command_engine_action_toggle():
    state = StateManager(initial_mode="normal")
    cfg_mgr = ConfigManager()
    grid_mgr = MagicMock()
    engine = CommandsEngine(state, grid_mgr, cfg_mgr)

    action = Action(
        name="Toggle Mode Action",
        trigger="!",
        modes=["normal", "special"],
        toggle=True,
        states=[
            ActionState(name="Vers Spécial", commands=[Command(type="mode", params={"target": "special"})]),
            ActionState(name="Vers Normal", commands=[Command(type="mode", params={"target": "normal"})]),
        ],
    )

    # Premier déclenchement -> État 0
    engine.execute_action(action)
    assert state.current_mode == "special"
    assert action.current_state_index == 1

    # Second déclenchement -> État 1
    engine.execute_action(action)
    assert state.current_mode == "normal"
    assert action.current_state_index == 0
