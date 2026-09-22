"""Tests unitaires pour la fenêtre principale de l'interface Alfred."""

from unittest.mock import MagicMock, patch
from src.alfred.ui.app import AlfredApp, parse_shortcut_to_tk
from src.alfred.core.config import ConfigManager
from src.alfred.core.state import StateManager
from src.alfred.core.grid import GridManager
from src.alfred.core.commands_engine import CommandsEngine


def test_parse_shortcut_to_tk():
    assert parse_shortcut_to_tk("ctrl+w") == ["<Control-w>", "<Control-W>"]
    assert parse_shortcut_to_tk("ctrl + alt + q") == ["<Control-Alt-q>", "<Control-Alt-Q>"]
    assert parse_shortcut_to_tk("escape") == ["<Escape>"]
    assert parse_shortcut_to_tk("ctrl+f4") == ["<Control-F4>"]
    assert parse_shortcut_to_tk("<Control-w>") == ["<Control-w>"]
    assert parse_shortcut_to_tk("") == []


def test_alfred_app_minimize_and_restore_tray():
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
    config_mgr.app_config.ui.start_minimized = True

    with patch("pystray.Icon"):
        app = AlfredApp(
            config_manager=config_mgr,
            state_manager=state_mgr,
            commands_engine=commands_engine,
            grid_manager=grid_mgr,
            hook_service=hook_service,
        )
        try:
            assert hasattr(app, "btn_minimize_tray")
            assert app.btn_minimize_tray.cget("text") == "📥 Minimiser"

            # Test minimize to tray
            with patch.object(app, "withdraw") as mock_withdraw:
                app.minimize_to_tray()
                mock_withdraw.assert_called_once()

            # Test restore from tray
            with patch.object(app, "deiconify") as mock_deiconify, \
                 patch.object(app, "lift") as mock_lift, \
                 patch.object(app, "focus_force") as mock_focus:
                app.restore_from_tray()
                mock_deiconify.assert_called_once()
                mock_lift.assert_called_once()
                mock_focus.assert_called_once()
            # Test de la case à cocher Démarrer minimisé sur le Dashboard
            dash = app.views["dashboard"]
            assert hasattr(dash, "chk_start_minimized")
            assert dash.chk_start_minimized.get() == 1

            # Test de la case à cocher Démarrer en mode spécial sur le Dashboard
            assert hasattr(dash, "chk_start_in_special_mode")
            assert dash.chk_start_in_special_mode.get() == 1

            with patch.object(config_mgr, "save_app_config") as mock_save:
                dash.chk_start_minimized.deselect()
                dash._on_toggle_start_minimized()
                assert config_mgr.app_config.ui.start_minimized is False
                mock_save.assert_called_once()

                dash.chk_start_minimized.select()
                dash._on_toggle_start_minimized()
                assert config_mgr.app_config.ui.start_minimized is True

            with patch.object(config_mgr, "save_app_config") as mock_save_special:
                dash.chk_start_in_special_mode.deselect()
                dash._on_toggle_start_in_special_mode()
                assert config_mgr.app_config.general.start_in_special_mode is False
                assert config_mgr.app_config.general.default_mode == "normal"
                mock_save_special.assert_called_once()

                dash.chk_start_in_special_mode.select()
                dash._on_toggle_start_in_special_mode()
                assert config_mgr.app_config.general.start_in_special_mode is True
                assert config_mgr.app_config.general.default_mode == "special"

            # Test des cases à cocher et champs dans SettingsModal
            from src.alfred.ui.views.settings_modal import SettingsModal
            from src.alfred.ui.theme import ThemeManager
            theme_mgr = ThemeManager(config_mgr.app_config.ui)
            modal = SettingsModal(
                parent=app,
                config_manager=config_mgr,
                theme_manager=theme_mgr,
            )
            assert hasattr(modal, "chk_start_minimized")
            assert modal.chk_start_minimized.get() == 1
            assert hasattr(modal, "chk_start_in_special_mode")
            assert modal.chk_start_in_special_mode.get() == 1
            assert hasattr(modal, "entry_quit_shortcut")
            assert modal.entry_quit_shortcut.get() == config_mgr.app_config.general.quit

            with patch.object(config_mgr, "save_app_config"):
                modal.chk_start_minimized.deselect()
                modal.chk_start_in_special_mode.deselect()
                modal.entry_quit_shortcut.delete(0, "end")
                modal.entry_quit_shortcut.insert(0, "ctrl+alt+q")
                modal._save_changes()
                assert config_mgr.app_config.ui.start_minimized is False
                assert config_mgr.app_config.general.start_in_special_mode is False
                assert config_mgr.app_config.general.default_mode == "normal"
                assert config_mgr.app_config.general.quit == "ctrl+alt+q"
                # Restaurer pour la fin du test
                config_mgr.app_config.ui.start_minimized = True
                config_mgr.app_config.general.start_in_special_mode = True
                config_mgr.app_config.general.default_mode = "special"
                config_mgr.app_config.general.quit = "ctrl+shift+q"
        finally:
            try:
                app.close()
            except Exception:
                pass


