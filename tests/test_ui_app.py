"""Tests unitaires pour la fenêtre principale de l'interface Alfred et la configuration de fermeture."""

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


def test_config_close_setting(tmp_path):
    config_mgr = ConfigManager(base_dir=tmp_path)
    # Vérification valeur par défaut
    app_cfg = config_mgr.load_app_config()
    assert app_cfg.general.close == "ctrl+w"

    # Sauvegarde avec close vide
    app_cfg.general.close = ""
    assert config_mgr.save_app_config() is True

    # Rechargement
    reloaded_cfg = config_mgr.load_app_config()
    assert reloaded_cfg.general.close == ""


def test_alfred_app_dynamic_close_binding_and_execution():
    config_mgr = ConfigManager()
    config_mgr.load_all()
    config_mgr.app_config.general.close = "ctrl+w"

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
            # 1. Vérifier que les bindings <Control-w> et <Control-W> existent
            assert "<Control-w>" in app._close_bound_sequences
            assert "<Control-W>" in app._close_bound_sequences
            assert app.bind("<Control-w>") != ""
            assert app.bind("<Control-W>") != ""

            # 2. Désactiver le raccourci (close = "")
            config_mgr.app_config.general.close = ""
            app._update_close_shortcut_binding()
            assert app._close_bound_sequences == []
            assert app.bind("<Control-w>") == ""
            assert app.bind("<Control-W>") == ""

            # 3. Changer pour un autre raccourci (close = "ctrl+q")
            config_mgr.app_config.general.close = "ctrl+q"
            app._update_close_shortcut_binding()
            assert "<Control-q>" in app._close_bound_sequences
            assert "<Control-Q>" in app._close_bound_sequences
            assert app.bind("<Control-q>") != ""

            # 4. Simuler l'appel à close() via le raccourci (avec un événement factice)
            event_mock = MagicMock()
            app.close(event_mock)

            hook_service.stop.assert_called_once()
            mock_restore.assert_called_once()
        finally:
            try:
                app.destroy()
            except Exception:
                pass
