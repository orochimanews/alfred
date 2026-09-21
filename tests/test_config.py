"""Tests unitaires pour le chargeur de configuration TOML."""

from pathlib import Path
from src.alfred.core.config import ConfigManager


def test_config_manager_load_all():
    mgr = ConfigManager()
    mgr.load_all()

    # Vérification config globale
    assert mgr.app_config.general.app_name == "Alfred"
    assert mgr.app_config.general.default_mode == "special"
    assert mgr.app_config.general.start_in_special_mode is True
    assert "normal" in mgr.app_config.modes
    assert "special" in mgr.app_config.modes
    assert "grid" in mgr.app_config.modes
    assert mgr.app_config.modes["special"].name == "Spécial"
    assert mgr.app_config.ui.theme in ["dark", "light", "system"]

    # Vérification grille
    assert mgr.grid_config.columns >= 1
    assert mgr.grid_config.rows >= 1
    assert len(mgr.grid_config.cells) > 0
    assert "&" in mgr.grid_config.cells or "a" in mgr.grid_config.cells

    # Vérification des actions
    assert len(mgr.actions) >= 1
    action_t = mgr.get_action_for_key("t", "special")
    assert action_t is not None
    assert "Nouvel Onglet" in action_t.name

    # Vérification des références
    assert len(mgr.commands_reference) > 0
    assert len(mgr.keys_reference) > 0


def test_config_save_and_reload(tmp_path: Path):
    from src.alfred.core.models import ModeConfig
    mgr = ConfigManager(base_dir=tmp_path)
    mgr.app_config.general.default_mode = "special"
    mgr.app_config.general.start_in_special_mode = False
    mgr.app_config.modes["custom"] = ModeConfig(name="Custom", description="Mode personnalisé")
    mgr.app_config.mouse.use_system_speed = False
    mgr.app_config.mouse.default_speed = 8
    mgr.app_config.ui.font_size = 16
    mgr.app_config.ui.theme = "light"
    mgr.app_config.ui.start_minimized = True
    mgr.app_config.ui.show_screen_indicator = False

    assert mgr.save_app_config() is True

    # Recharger dans une nouvelle instance
    mgr2 = ConfigManager(base_dir=tmp_path)
    loaded = mgr2.load_app_config()
    assert loaded.general.default_mode == "special"
    assert loaded.general.start_in_special_mode is False
    assert "custom" in loaded.modes
    assert loaded.modes["custom"].name == "Custom"
    assert loaded.mouse.use_system_speed is False
    assert loaded.mouse.default_speed == 8
    assert loaded.ui.font_size == 16
    assert loaded.ui.theme == "light"
    assert loaded.ui.start_minimized is True
    assert loaded.ui.show_screen_indicator is False


def test_config_manager_load_multi_actions_file(tmp_path: Path):
    actions_dir = tmp_path / "settings" / "actions"
    actions_dir.mkdir(parents=True)

    # Fichier multi-actions avec la syntaxe standard TOML [[actions]]
    multi_toml = """
[[actions]]
name = "Copier Rapide"
modes = ["special"]
trigger = "c"
[[actions.commands]]
type = "hotkey"
keys = ["ctrl", "c"]

[[actions]]
name = "Coller Rapide"
modes = ["special"]
trigger = "p"
[[actions.commands]]
type = "hotkey"
keys = ["ctrl", "v"]
"""
    (actions_dir / "clipboard_actions.toml").write_text(multi_toml, encoding="utf-8")

    mgr = ConfigManager(base_dir=tmp_path)
    actions = mgr.load_actions()

    assert len(actions) == 2
    act_c = mgr.get_action_for_key("c", "special")
    act_p = mgr.get_action_for_key("p", "special")

    assert act_c is not None
    assert act_c.name == "Copier Rapide"
    assert act_c.trigger == "c"

    assert act_p is not None
    assert act_p.name == "Coller Rapide"
    assert act_p.trigger == "p"


def test_config_manager_frozen_mode(monkeypatch, tmp_path: Path):
    import sys
    app_dir = tmp_path / "Alfred"
    app_dir.mkdir(parents=True)
    fake_settings = app_dir / "settings"
    fake_settings.mkdir()
    (fake_settings / "config.toml").write_text("[general]\napp_name = 'AlfredFrozen'\n", encoding="utf-8")

    fake_exe = app_dir / "Alfred.exe"

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(fake_exe))

    mgr = ConfigManager()
    assert mgr.root_dir == app_dir
    assert mgr.settings_dir == fake_settings
    cfg = mgr.load_app_config()
    assert cfg.general.app_name == "AlfredFrozen"


def test_config_start_in_special_mode_inference(tmp_path: Path):
    # 1. Config vide : doit valoir True par défaut
    settings_dir = tmp_path / "settings"
    settings_dir.mkdir(parents=True)
    cfg_file = settings_dir / "config.toml"
    cfg_file.write_text("[general]\napp_name = 'Test'\n", encoding="utf-8")

    mgr = ConfigManager(base_dir=tmp_path)
    loaded = mgr.load_app_config()
    assert loaded.general.start_in_special_mode is True
    assert loaded.general.default_mode == "special"

    # 2. Config legacy avec default_mode = "normal"
    cfg_file.write_text("[general]\ndefault_mode = 'normal'\n", encoding="utf-8")
    loaded2 = mgr.load_app_config()
    assert loaded2.general.start_in_special_mode is False
    assert loaded2.general.default_mode == "normal"

    # 3. Config explicite avec start_in_special_mode = false
    cfg_file.write_text("[general]\nstart_in_special_mode = false\n", encoding="utf-8")
    loaded3 = mgr.load_app_config()
    assert loaded3.general.start_in_special_mode is False
    assert loaded3.general.default_mode == "normal"


def test_config_quit_setting(tmp_path: Path):
    """Vérifie le chargement, la persistance et les alias du raccourci global quit dans config.toml."""
    mgr = ConfigManager(base_dir=tmp_path)
    loaded = mgr.load_app_config()
    # Valeur par défaut
    assert loaded.general.quit == "ctrl+shift+q"
    assert loaded.general.quit_key == "ctrl+shift+q"

    # Sauvegarde d'une nouvelle valeur
    loaded.general.quit = "ctrl+alt+q"
    assert mgr.save_app_config() is True

    # Rechargement
    mgr2 = ConfigManager(base_dir=tmp_path)
    loaded2 = mgr2.load_app_config()
    assert loaded2.general.quit == "ctrl+alt+q"

    # Test avec alias 'quit_key' dans le fichier TOML
    cfg_file = tmp_path / "settings" / "config.toml"
    cfg_file.write_text("[general]\nquit_key = 'f12'\n", encoding="utf-8")
    loaded3 = mgr2.load_app_config()
    assert loaded3.general.quit == "f12"



