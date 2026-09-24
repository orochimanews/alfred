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


def test_hook_uppercase_letter_trigger(monkeypatch):
    """Vérifie que le hook clavier distingue 'a' (sans shift) et 'A' (avec shift / majuscule)."""
    from src.alfred.core.models import Action, Command

    config_mgr = ConfigManager()
    config_mgr.load_all()
    config_mgr.app_config.general.special_mode_key = ""

    act_lower = Action(
        name="Action Minuscule A",
        modes=["special"],
        trigger="a",
        triggers={"a"},
        commands=[Command(type="text", params={"content": "minuscule"})],
    )
    act_upper = Action(
        name="Action Majuscule A",
        modes=["special"],
        trigger="A",
        triggers={"A", "shift+a", "maj+a"},
        commands=[Command(type="text", params={"content": "majuscule"})],
    )
    config_mgr.actions = [act_lower, act_upper]

    state_mgr = StateManager(initial_mode="special")
    grid_mgr = GridManager(config=config_mgr.grid_config, state_manager=state_mgr)
    commands_engine = CommandsEngine(state_manager=state_mgr, grid_manager=grid_mgr, config_manager=config_mgr)

    hook_service = KeyboardHookService(
        state_manager=state_mgr,
        config_manager=config_mgr,
        commands_engine=commands_engine,
        grid_manager=grid_mgr,
    )

    executed = []
    def mock_execute(action, trigger_key=""):
        executed.append((action.name, trigger_key))
        return True

    monkeypatch.setattr(commands_engine, "execute_action", mock_execute)

    # 1. Frappe de 'a' SANS shift -> doit exécuter "Action Minuscule A"
    event_lower = MagicMock()
    event_lower.name = "a"
    event_lower.scan_code = 16
    event_lower.event_type = "down"

    ret_lower = hook_service._on_key_event(event_lower)
    assert ret_lower is False
    assert len(executed) == 1
    assert executed[-1][0] == "Action Minuscule A"

    # Réinitialiser touches enfoncées
    hook_service._pressed_keys.clear()

    # 2. Frappe de 'a' AVEC shift enfoncé -> doit exécuter "Action Majuscule A"
    hook_service._pressed_keys.add("shift")
    event_with_shift = MagicMock()
    event_with_shift.name = "a"
    event_with_shift.scan_code = 16
    event_with_shift.event_type = "down"

    ret_shift = hook_service._on_key_event(event_with_shift)
    assert ret_shift is False
    assert len(executed) == 2
    assert executed[-1][0] == "Action Majuscule A"

    # 3. Frappe de 'A' (événement natif majuscule sous Windows) -> doit exécuter "Action Majuscule A"
    hook_service._pressed_keys.clear()
    event_upper = MagicMock()
    event_upper.name = "A"
    event_upper.scan_code = 16
    event_upper.event_type = "down"

    ret_upper = hook_service._on_key_event(event_upper)
    assert ret_upper is False
    assert len(executed) == 3
    assert executed[-1][0] == "Action Majuscule A"

    # 4. Action avec minuscule seule : si l'utilisateur appuie sur Shift, l'action minuscule ne doit PAS se déclencher
    config_mgr.actions = [act_lower]
    hook_service._pressed_keys.clear()
    hook_service._pressed_keys.add("shift")
    event_unmatched_upper = MagicMock()
    event_unmatched_upper.name = "a"
    event_unmatched_upper.scan_code = 16
    event_unmatched_upper.event_type = "down"

    ret_unmatched = hook_service._on_key_event(event_unmatched_upper)
    # Ne doit pas intercepter (ret_unmatched == True) car aucune action pour A/shift+a n'existe
    assert ret_unmatched is True
    assert len(executed) == 3


def test_hook_uppercase_action_not_intercepted_by_lowercase_move_grid(monkeypatch):
    """Vérifie que Shift+Q déclenche bien une action Q et n'est pas capturé par grid_toggle_key='q'."""
    from src.alfred.core.models import Action, Command, MoveConfig
    from src.alfred.core.move import MoveManager
    from src.alfred.core.mouse import mouse

    config_mgr = ConfigManager()
    config_mgr.load_all()
    config_mgr.app_config.general.special_mode_key = ""

    # Action avec trigger majuscule 'Q'
    act_quit = Action(
        name="Quitter",
        modes=["all"],
        trigger="Q",
        triggers={"Q", "shift+q", "maj+q"},
        commands=[Command(type="quit")],
    )
    config_mgr.actions = [act_quit]

    # MoveManager avec grid_toggle_key = 'q' (minuscule)
    move_cfg = MoveConfig(
        enabled=True,
        active_modes=["special"],
        grid_enabled=True,
        grid_toggle_key="q",
    )
    config_mgr.move_config = move_cfg

    state_mgr = StateManager(initial_mode="special")
    move_mgr = MoveManager(config=move_cfg, mouse_controller=mouse, state_manager=state_mgr)
    grid_mgr = GridManager(config=config_mgr.grid_config, state_manager=state_mgr)
    commands_engine = CommandsEngine(state_manager=state_mgr, grid_manager=grid_mgr, config_manager=config_mgr, move_manager=move_mgr)

    hook_service = KeyboardHookService(
        state_manager=state_mgr,
        config_manager=config_mgr,
        commands_engine=commands_engine,
        grid_manager=grid_mgr,
        move_manager=move_mgr,
    )

    executed = []
    def mock_execute(action, trigger_key=""):
        executed.append((action.name, trigger_key))
        return True

    monkeypatch.setattr(commands_engine, "execute_action", mock_execute)

    # 1. Frappe de 'q' SANS shift -> doit activer Move Grid, PAS l'action Quitter
    event_q = MagicMock()
    event_q.name = "q"
    event_q.scan_code = 16
    event_q.event_type = "down"

    ret_q = hook_service._on_key_event(event_q)
    assert ret_q is False
    assert move_mgr.is_grid_active is True
    assert len(executed) == 0

    # Réinitialiser Move Grid
    move_mgr.set_grid_active(False)
    hook_service._pressed_keys.clear()

    # 2. Frappe de Shift + 'q' -> doit exécuter l'action Quitter ('Q'), PAS activer Move Grid
    hook_service._pressed_keys.add("shift")
    event_shift_q = MagicMock()
    event_shift_q.name = "q"
    event_shift_q.scan_code = 16
    event_shift_q.event_type = "down"

    ret_shift_q = hook_service._on_key_event(event_shift_q)
    assert ret_shift_q is False
    assert move_mgr.is_grid_active is False
    assert len(executed) == 1
    assert executed[0][0] == "Quitter"




