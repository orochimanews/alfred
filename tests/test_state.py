"""Tests unitaires pour le gestionnaire d'état."""

from src.alfred.core.state import StateManager


def test_state_manager_mode_transition():
    state = StateManager(initial_mode="normal")
    assert state.current_mode == "normal"
    assert state.previous_mode == "normal"

    events = []
    state.subscribe(lambda event, data: events.append((event, data)))

    # Changement vers special
    res = state.set_mode("special")
    assert res is True
    assert state.current_mode == "special"
    assert state.previous_mode == "normal"
    assert ("mode_changed", "special") in events

    # Même mode ne doit rien déclencher
    assert state.set_mode("special") is False

    # Toggle mode
    target = state.toggle_mode("normal")
    assert target == "normal"
    assert state.current_mode == "normal"
    assert state.previous_mode == "special"


def test_state_manager_hook_and_logs():
    state = StateManager()
    assert state.is_hook_enabled is True

    state.set_hook_enabled(False)
    assert state.is_hook_enabled is False

    state.add_log(action_name="Action 1", trigger_key="x", mode="special", details="test")
    assert len(state.logs) == 1
    assert state.logs[0].action_name == "Action 1"
    assert state.logs[0].trigger_key == "x"

    state.clear_logs()
    assert len(state.logs) == 0
