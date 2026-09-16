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


def test_command_engine_mouse_speed_toggle_restores_original_speed():
    state = StateManager(initial_mode="special")
    cfg_mgr = ConfigManager()
    grid_mgr = MagicMock()
    engine = CommandsEngine(state, grid_mgr, cfg_mgr)

    with patch("src.alfred.core.commands_engine.mouse") as mock_mouse:
        # Vitesse Windows initiale personnalisée (ex: 14)
        mock_mouse.get_speed.return_value = 14

        cmd_toggle = Command(type="mouse_speed", params={"speed": 18, "toggle": True})

        # 1er appel : activation de la vitesse rapide
        engine.execute_command(cmd_toggle)
        mock_mouse.get_speed.assert_called_once()
        mock_mouse.set_speed.assert_called_with(18)
        assert engine._is_fast_mouse_speed is True
        assert engine._previous_mouse_speed == 14

        # 2e appel : restauration de la vitesse initiale (14)
        engine.execute_command(cmd_toggle)
        mock_mouse.set_speed.assert_called_with(14)
        assert engine._is_fast_mouse_speed is False


def test_command_engine_mouse_speed_toggle_custom_default_speed():
    state = StateManager(initial_mode="special")
    cfg_mgr = ConfigManager()
    cfg_mgr.app_config.mouse.use_system_speed = False
    cfg_mgr.app_config.mouse.default_speed = 7
    grid_mgr = MagicMock()
    engine = CommandsEngine(state, grid_mgr, cfg_mgr)

    with patch("src.alfred.core.commands_engine.mouse") as mock_mouse:
        cmd_toggle = Command(type="mouse_speed", params={"speed": 18, "toggle": True})

        # 1er appel : activation de la vitesse rapide
        engine.execute_command(cmd_toggle)
        mock_mouse.set_speed.assert_called_with(18)
        assert engine._previous_mouse_speed == 7

        # 2e appel : restauration de la vitesse personnalisée (7)
        engine.execute_command(cmd_toggle)
        mock_mouse.set_speed.assert_called_with(7)
        assert engine._is_fast_mouse_speed is False


def test_command_engine_app_onenote_normalization():
    """Vérifie que 'onenote:' est bien normalisé en 'onenote' pour éviter le bug de dialogue d'erreur OneNote."""
    state = StateManager(initial_mode="special")
    cfg_mgr = ConfigManager()
    grid_mgr = MagicMock()
    engine = CommandsEngine(state, grid_mgr, cfg_mgr)

    with patch("src.alfred.core.commands_engine.find_window_for_app", return_value=None), patch("os.startfile") as mock_startfile:
        cmd = Command(type="app", params={"command": "onenote:"})
        engine.execute_command(cmd)
        mock_startfile.assert_called_once_with("onenote")


def test_command_engine_app_direct_and_with_args():
    state = StateManager(initial_mode="special")
    cfg_mgr = ConfigManager()
    grid_mgr = MagicMock()
    engine = CommandsEngine(state, grid_mgr, cfg_mgr)

    with patch("src.alfred.core.commands_engine.find_window_for_app", return_value=None), patch("os.startfile") as mock_startfile:
        cmd_app = Command(type="app", params={"command": "onenote"})
        engine.execute_command(cmd_app)
        mock_startfile.assert_called_with("onenote")

    with patch("src.alfred.core.commands_engine.find_window_for_app", return_value=None), patch("os.startfile") as mock_startfile:
        cmd_args = Command(type="app", params={"command": "notepad", "args": ["file.txt"]})
        engine.execute_command(cmd_args)
        mock_startfile.assert_called_with("notepad", arguments="file.txt")


def test_command_engine_app_fallback_subprocess():
    state = StateManager(initial_mode="special")
    cfg_mgr = ConfigManager()
    grid_mgr = MagicMock()
    engine = CommandsEngine(state, grid_mgr, cfg_mgr)

    with patch("src.alfred.core.commands_engine.find_window_for_app", return_value=None), \
         patch("os.startfile", side_effect=OSError("Not found")), \
         patch("subprocess.Popen") as mock_popen:
        cmd = Command(type="app", params={"command": "custom_script.bat", "args": ["--run"]})
        engine.execute_command(cmd)
        mock_popen.assert_called_once_with(["custom_script.bat", "--run"], shell=True)


def test_command_engine_app_reuses_existing_window():
    """Vérifie que si une fenêtre de l'application est déjà ouverte, elle est réactivée au premier plan sans lancer de nouveau processus."""
    state = StateManager(initial_mode="special")
    cfg_mgr = ConfigManager()
    grid_mgr = MagicMock()
    engine = CommandsEngine(state, grid_mgr, cfg_mgr)

    with patch("src.alfred.core.commands_engine.find_window_for_app", return_value=12345) as mock_find, \
         patch("src.alfred.core.commands_engine.bring_window_to_foreground", return_value=True) as mock_bring, \
         patch("os.startfile") as mock_startfile:
        cmd = Command(type="app", params={"command": "explorer"})
        engine.execute_command(cmd)
        mock_find.assert_called_once_with("explorer")
        mock_bring.assert_called_once_with(12345)
        mock_startfile.assert_not_called()


