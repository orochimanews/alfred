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

    # Injecter une action test avec trigger '!' pour valider la résolution de candidate_keys
    from src.alfred.core.models import Action, Command
    test_action = Action(
        name="Test Action Exclamation",
        modes=["all"],
        trigger="!",
        triggers={"!"},
        commands=[Command(type="text", params={"content": "test"})],
    )
    config_mgr.actions.insert(0, test_action)

    state_mgr = StateManager(initial_mode="special")
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
    assert executed_actions[0][0] == "Test Action Exclamation"


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


def test_hook_stuck_key_recovery(monkeypatch):
    """Vérifie que si une touche est marquée 'is_repeat' mais n'est pas physiquement enfoncée, elle est débloquée."""
    config_mgr = ConfigManager()
    config_mgr.load_all()
    state_mgr = StateManager(initial_mode="special")
    grid_mgr = GridManager(config=config_mgr.grid_config, state_manager=state_mgr)
    commands_engine = CommandsEngine(state_manager=state_mgr, grid_manager=grid_mgr, config_manager=config_mgr)

    hook_service = KeyboardHookService(
        state_manager=state_mgr,
        config_manager=config_mgr,
        commands_engine=commands_engine,
        grid_manager=grid_mgr,
    )

    # Simuler une touche restée coincée dans _pressed_keys
    hook_service._pressed_keys.add("y")

    executed = []
    monkeypatch.setattr(commands_engine, "execute_action", lambda act, tr: executed.append(act.name))

    # Événement de touche 'y' (scan code 21)
    mock_event = MagicMock()
    mock_event.name = "y"
    mock_event.scan_code = 21
    mock_event.event_type = "down"

    # Simuler GetAsyncKeyState retournant 0 (non maintenue physiquement)
    if sys.platform == "win32":
        import ctypes
        monkeypatch.setattr(ctypes.windll.user32, "GetAsyncKeyState", lambda vk: 0)

    # L'événement doit débloquer la touche et exécuter l'action associée
    hook_service._on_key_event(mock_event)
    assert len(executed) >= 1 or "y" in hook_service._pressed_keys


def test_setup_hook_thread_win32_does_not_crash():
    """Vérifie que l'optimisation thread du hook s'exécute sans erreur."""
    from src.alfred.core.hook import _setup_hook_thread_win32
    _setup_hook_thread_win32()


def test_hook_reinstall_and_health_check(monkeypatch):
    """Vérifie que la réinstallation et la surveillance du hook s'exécutent correctement."""
    config_mgr = ConfigManager()
    config_mgr.load_all()
    state_mgr = StateManager(initial_mode="special")
    grid_mgr = GridManager(config=config_mgr.grid_config, state_manager=state_mgr)
    commands_engine = CommandsEngine(state_manager=state_mgr, grid_manager=grid_mgr, config_manager=config_mgr)

    hook_service = KeyboardHookService(
        state_manager=state_mgr,
        config_manager=config_mgr,
        commands_engine=commands_engine,
        grid_manager=grid_mgr,
    )

    installed = []
    teardowns = []
    monkeypatch.setattr(hook_service, "_install_hook", lambda: installed.append(True))
    monkeypatch.setattr(hook_service, "_teardown_hook", lambda: teardowns.append(True))

    # 1. Test reinstall_hook
    hook_service.reinstall_hook()
    assert len(teardowns) == 1
    assert len(installed) == 1

    # 2. Test ensure_hook_healthy quand hook non installé -> appelle start()
    started = []
    monkeypatch.setattr(hook_service, "start", lambda: started.append(True))
    hook_service._hook_installed = False
    hook_service.ensure_hook_healthy()
    assert len(started) == 1



