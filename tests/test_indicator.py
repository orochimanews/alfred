"""Tests unitaires pour le composant ScreenIndicator."""

import tkinter as tk
from unittest.mock import MagicMock, patch
from src.alfred.ui.indicator import ScreenIndicator, MODE_COLORS


def test_screen_indicator_init_and_mode_colors():
    root = tk.Tk()
    root.withdraw()
    try:
        indicator = ScreenIndicator(master=root, initial_mode="normal", enabled=True)
        assert indicator.current_mode == "normal"
        assert indicator.enabled is True
        assert indicator._window is not None
        assert indicator._canvas is not None

        # Vérification du mode special
        indicator.update_mode("special")
        assert indicator.current_mode == "special"

        # Vérification du masquage puis réactivation
        indicator.set_enabled(False)
        assert indicator.enabled is False

        indicator.set_enabled(True)
        assert indicator.enabled is True

        indicator.destroy()
        assert indicator._window is None
        assert indicator._canvas is None
    finally:
        root.destroy()


def test_screen_indicator_disabled_at_init():
    root = tk.Tk()
    root.withdraw()
    try:
        indicator = ScreenIndicator(master=root, initial_mode="normal", enabled=False)
        assert indicator.enabled is False
        assert indicator._window is None

        # Activation dynamique
        indicator.set_enabled(True)
        assert indicator.enabled is True
        assert indicator._window is not None

        indicator.destroy()
    finally:
        root.destroy()


def test_screen_indicator_app_integration():
    from src.alfred.ui.app import AlfredApp
    from src.alfred.core.config import ConfigManager
    from src.alfred.core.state import StateManager
    from src.alfred.core.grid import GridManager
    from src.alfred.core.commands_engine import CommandsEngine

    config_mgr = ConfigManager()
    config_mgr.load_all()
    config_mgr.app_config.ui.show_screen_indicator = True

    state_mgr = StateManager(initial_mode="normal")
    grid_mgr = GridManager(config=config_mgr.grid_config, state_manager=state_mgr)
    commands_engine = CommandsEngine(
        state_manager=state_mgr,
        grid_manager=grid_mgr,
        config_manager=config_mgr,
    )
    hook_service = MagicMock()

    app = AlfredApp(
        config_manager=config_mgr,
        state_manager=state_mgr,
        commands_engine=commands_engine,
        grid_manager=grid_mgr,
        hook_service=hook_service,
    )
    try:
        assert hasattr(app, "screen_indicator")
        assert app.screen_indicator is not None
        assert app.screen_indicator.enabled is True
        assert app.screen_indicator.current_mode == "normal"

        # Basculer le mode via state_manager
        state_mgr.set_mode("special")
        app._handle_state_event_in_ui("mode_changed", "special")
        assert app.screen_indicator.current_mode == "special"

        # Désactiver le voyant via la méthode dédiée
        app.set_screen_indicator_enabled(False)
        assert app.screen_indicator.enabled is False

        # Réactiver le voyant
        app.set_screen_indicator_enabled(True)
        assert app.screen_indicator.enabled is True
    finally:
        app.close()


def test_screen_indicator_pixel_offsets():
    root = tk.Tk()
    root.withdraw()
    try:
        indicator = ScreenIndicator(
            master=root,
            initial_mode="normal",
            enabled=True,
            size=20,
            offset_x=10,
            offset_y=15,
        )
        assert indicator.offset_x == 10
        assert indicator.offset_y == 15
        assert indicator.size == 20

        # Vérifier le calcul des coordonnées
        pos_x, pos_y = indicator._get_target_coordinates()
        assert pos_x > 0
        assert pos_y > 0

        # Mise à jour dynamique des offsets
        indicator.update_config(offset_x=5, offset_y=8, size=24)
        assert indicator.offset_x == 5
        assert indicator.offset_y == 8
        assert indicator.size == 24

        indicator.destroy()
    finally:
        root.destroy()
