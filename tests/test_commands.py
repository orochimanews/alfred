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


def test_command_engine_edge_snap():
    state = StateManager(initial_mode="special")
    cfg_mgr = ConfigManager()
    grid_mgr = MagicMock()
    engine = CommandsEngine(state, grid_mgr, cfg_mgr)

    cmd = Command(type="edge_snap", params={"offset": 20})
    engine.execute_command(cmd)
    grid_mgr.snap_to_edge.assert_called_once_with(offset=20)


def test_command_engine_scroll():
    state = StateManager(initial_mode="special")
    cfg_mgr = ConfigManager()
    grid_mgr = MagicMock()
    engine = CommandsEngine(state, grid_mgr, cfg_mgr)

    with patch("src.alfred.core.commands_engine.mouse") as mock_mouse:
        cmd_up = Command(type="scroll", params={"delta": 3})
        engine.execute_command(cmd_up)
        mock_mouse.scroll.assert_called_with(3)

        cmd_down = Command(type="wheel", params={"delta": -3})
        engine.execute_command(cmd_down)
        mock_mouse.scroll.assert_called_with(-3)


def test_command_engine_mouse_down_up():
    state = StateManager(initial_mode="special")
    cfg_mgr = ConfigManager()
    grid_mgr = MagicMock()
    engine = CommandsEngine(state, grid_mgr, cfg_mgr)

    with patch("src.alfred.core.commands_engine.mouse") as mock_mouse:
        cmd_down = Command(type="mouse_down", params={"button": "left"})
        engine.execute_command(cmd_down)
        mock_mouse.mouse_down.assert_called_with("left")

        cmd_up = Command(type="mouse_up", params={"button": "left"})
        engine.execute_command(cmd_up)
        mock_mouse.mouse_up.assert_called_with("left")


def test_mouse_controller_scroll_and_down_up():
    from src.alfred.core.mouse import MouseController, MOUSEEVENTF_WHEEL, MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP, WHEEL_DELTA

    controller = MouseController()
    with patch.object(controller._user32, "mouse_event") as mock_event:
        controller.scroll(3)
        mock_event.assert_called_with(MOUSEEVENTF_WHEEL, 0, 0, 3 * WHEEL_DELTA, 0)

        controller.mouse_down("left")
        mock_event.assert_called_with(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)

        controller.mouse_up("left")
        mock_event.assert_called_with(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)


def test_command_engine_zoom():
    state = StateManager(initial_mode="special")
    cfg_mgr = ConfigManager()
    grid_mgr = MagicMock()
    engine = CommandsEngine(state, grid_mgr, cfg_mgr)

    with patch("src.alfred.core.commands_engine.mouse") as mock_mouse:
        cmd_in = Command(type="zoom", params={"direction": "in"})
        engine.execute_command(cmd_in)
        mock_mouse.zoom.assert_called_with(direction="in", steps=1)

        cmd_out = Command(type="zoom", params={"direction": "out", "steps": 2})
        engine.execute_command(cmd_out)
        mock_mouse.zoom.assert_called_with(direction="out", steps=2)


def test_mouse_controller_zoom():
    from src.alfred.core.mouse import MouseController, VK_CONTROL, VK_ADD, VK_OEM_MINUS

    controller = MouseController()
    with patch.object(controller._user32, "keybd_event") as mock_event:
        controller.zoom(direction="in")
        # Doit presser VK_CONTROL, puis VK_ADD down/up, puis VK_CONTROL up
        mock_event.assert_any_call(VK_CONTROL, 0, 0, 0)
        mock_event.assert_any_call(VK_ADD, 0x4E, 0, 0)
        mock_event.assert_any_call(VK_ADD, 0x4E, 2, 0)
        mock_event.assert_any_call(VK_CONTROL, 0, 2, 0)

        mock_event.reset_mock()
        controller.zoom(direction="out")
        mock_event.assert_any_call(VK_CONTROL, 0, 0, 0)
        mock_event.assert_any_call(VK_OEM_MINUS, 0x0C, 0, 0)
        mock_event.assert_any_call(VK_OEM_MINUS, 0x0C, 2, 0)
        mock_event.assert_any_call(VK_CONTROL, 0, 2, 0)






