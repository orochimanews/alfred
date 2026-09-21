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
    config_mgr.app_config.general.special_mode_key = ""
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


def test_match_shortcut():
    """Vérifie le parsing et la correspondance des raccourcis simples et combinés."""
    from src.alfred.core.hook import match_shortcut

    # Combinaison Ctrl + Shift + Q
    assert match_shortcut("ctrl+shift+q", ["q"], {"ctrl", "shift", "q"}) is True
    assert match_shortcut("ctrl+shift+q", ["q"], {"ctrl", "q"}) is False
    assert match_shortcut("ctrl+shift+q", ["q"], {"ctrl", "shift", "alt", "q"}) is False

    # Touche unique (F12)
    assert match_shortcut("f12", ["f12"], {"f12"}) is True
    assert match_shortcut("f12", ["f12"], {"ctrl", "f12"}) is False

    # Aliases de touches (esc -> escape)
    assert match_shortcut("esc", ["escape"], {"escape"}) is True
    assert match_shortcut("escape", ["esc"], {"esc"}) is True

    # Raccourci vide
    assert match_shortcut("", ["q"], {"q"}) is False


def test_hook_global_quit_shortcut_triggers_callback(monkeypatch):
    """Vérifie que le raccourci global configuré dans config.toml quitte l'application et supprime la touche."""
    config_mgr = ConfigManager()
    config_mgr.load_all()
    config_mgr.app_config.general.quit = "ctrl+shift+q"

    state_mgr = StateManager(initial_mode="normal")
    grid_mgr = GridManager(config=config_mgr.grid_config, state_manager=state_mgr)
    commands_engine = CommandsEngine(state_manager=state_mgr, grid_manager=grid_mgr, config_manager=config_mgr)

    hook_service = KeyboardHookService(
        state_manager=state_mgr,
        config_manager=config_mgr,
        commands_engine=commands_engine,
        grid_manager=grid_mgr,
    )

    quit_called = []
    hook_service.set_quit_callback(lambda: quit_called.append(True))

    # 1. Touche Ctrl enfoncée
    ev_ctrl = MagicMock()
    ev_ctrl.name = "left ctrl"
    ev_ctrl.scan_code = 29
    ev_ctrl.event_type = "down"
    assert hook_service._on_key_event(ev_ctrl) is True
    assert len(quit_called) == 0

    # 2. Touche Shift enfoncée
    ev_shift = MagicMock()
    ev_shift.name = "left shift"
    ev_shift.scan_code = 42
    ev_shift.event_type = "down"
    assert hook_service._on_key_event(ev_shift) is True
    assert len(quit_called) == 0

    # 3. Touche Q enfoncée -> Doit matcher 'ctrl+shift+q'
    ev_q = MagicMock()
    ev_q.name = "q"
    ev_q.scan_code = 16
    ev_q.event_type = "down"
    ret = hook_service._on_key_event(ev_q)

    # La touche doit être supprimée (return False)
    assert ret is False

    # Le callback de terminaison doit être invoqué via le thread
    import time
    time.sleep(0.1)
    assert len(quit_called) == 1

    # Un log d'historique doit être enregistré dans state_mgr
    logs = state_mgr.logs
    assert len(logs) >= 1
    assert "Quitter Alfred" in logs[-1].action_name


def test_hook_global_quit_single_key(monkeypatch):
    """Vérifie qu'une touche unique (ex: F12) configurée dans quit fonctionne également."""
    config_mgr = ConfigManager()
    config_mgr.load_all()
    config_mgr.app_config.general.quit = "f12"

    state_mgr = StateManager(initial_mode="special")
    grid_mgr = GridManager(config=config_mgr.grid_config, state_manager=state_mgr)
    commands_engine = CommandsEngine(state_manager=state_mgr, grid_manager=grid_mgr, config_manager=config_mgr)

    hook_service = KeyboardHookService(
        state_manager=state_mgr,
        config_manager=config_mgr,
        commands_engine=commands_engine,
        grid_manager=grid_mgr,
    )

    quit_called = []
    hook_service.set_quit_callback(lambda: quit_called.append(True))

    ev_f12 = MagicMock()
    ev_f12.name = "f12"
    ev_f12.scan_code = 88
    ev_f12.event_type = "down"

    ret = hook_service._on_key_event(ev_f12)
    assert ret is False

    import time
    time.sleep(0.1)
    assert len(quit_called) == 1

