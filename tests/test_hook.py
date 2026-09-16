"""Tests unitaires pour le KeyboardHookService et les optimisations Windows."""

from __future__ import annotations
import sys
import pytest
from unittest.mock import MagicMock

from src.alfred.core.hook import KeyboardHookService, _patch_keyboard_windows_listen
from src.alfred.core.state import StateManager
from src.alfred.core.config import ConfigManager
from src.alfred.core.grid import GridManager
from src.alfred.core.commands_engine import CommandsEngine
from src.alfred.main import configure_windows_process


def test_patch_keyboard_windows_listen():
    """Vérifie que le patch safe_listen est bien appliqué sous Windows."""
    _patch_keyboard_windows_listen()
    if sys.platform == "win32":
        from keyboard import _winkeyboard
        assert _winkeyboard.listen.__name__ == "safe_listen"


def test_configure_windows_process_does_not_crash():
    """Vérifie que la configuration du processus Windows s'exécute sans exception."""
    configure_windows_process()


def test_hook_candidate_keys_exclamation(monkeypatch):
    """Vérifie que les touches '§' ou scan code 53 (AZERTY) sont reconnues comme '!'."""
    config_mgr = ConfigManager()
    config_mgr.load_all()
    state_mgr = StateManager(initial_mode="normal")
    grid_mgr = GridManager(config=config_mgr.grid_config, state_manager=state_mgr)
    commands_engine = CommandsEngine(state_manager=state_mgr, grid_manager=grid_mgr, config_manager=config_mgr)

    hook_service = KeyboardHookService(
        state_manager=state_mgr,
        config_manager=config_mgr,
        commands_engine=commands_engine,
        grid_manager=grid_mgr,
    )

    executed_actions = []
    def mock_execute_action(action, trigger_key=""):
        executed_actions.append((action.name, trigger_key))
        return True

    monkeypatch.setattr(commands_engine, "execute_action", mock_execute_action)

    mock_event = MagicMock()
    mock_event.name = "§"
    mock_event.scan_code = 53
    mock_event.event_type = "down"

    ret = hook_service._on_key_event(mock_event)
    assert ret is False
    assert len(executed_actions) == 1
    assert "Toggle" in executed_actions[0][0]
