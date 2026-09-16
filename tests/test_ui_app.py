"""Tests unitaires pour la fenêtre principale de l'interface Alfred."""

from unittest.mock import MagicMock, patch
from src.alfred.ui.app import AlfredApp
from src.alfred.core.config import ConfigManager
from src.alfred.core.state import StateManager
from src.alfred.core.grid import GridManager
from src.alfred.core.commands_engine import CommandsEngine


def test_alfred_app_ctrl_w_binding_and_close():
    config_mgr = ConfigManager()
    config_mgr.load_all()
    state_mgr = StateManager(initial_mode="normal")
    grid_mgr = GridManager(config=config_mgr.grid_config, state_manager=state_mgr)
    commands_engine = CommandsEngine(
        state_manager=state_mgr,
        grid_manager=grid_mgr,
        config_manager=config_mgr,
    )
    hook_service = MagicMock()

    with patch("src.alfred.core.mouse.mouse.restore_initial_speed") as mock_restore:
        app = AlfredApp(
            config_manager=config_mgr,
            state_manager=state_mgr,
            commands_engine=commands_engine,
            grid_manager=grid_mgr,
            hook_service=hook_service,
        )

        try:
            # Vérifier que les bindings <Control-w> et <Control-W> existent
            ctrl_w_binding = app.bind("<Control-w>")
            ctrl_w_upper_binding = app.bind("<Control-W>")
            assert ctrl_w_binding != ""
            assert ctrl_w_upper_binding != ""

            # Simuler l'appel à close() via le raccourci (avec un événement factice)
            event_mock = MagicMock()
            app.close(event_mock)

            # Vérifications
            hook_service.stop.assert_called_once()
            mock_restore.assert_called_once()
        finally:
            try:
                app.destroy()
            except Exception:
                pass
