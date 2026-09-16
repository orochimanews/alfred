"""Tests unitaires pour le chargeur de configuration TOML."""

from pathlib import Path
from src.alfred.core.config import ConfigManager


def test_config_manager_load_all():
    mgr = ConfigManager()
    mgr.load_all()

    # Vérification config globale
    assert mgr.app_config.general.app_name == "Alfred"
    assert mgr.app_config.general.special_mode_key == "!"
    assert mgr.app_config.ui.theme in ["dark", "light", "system"]

    # Vérification grille
    assert mgr.grid_config.columns >= 1
    assert mgr.grid_config.rows >= 1
    assert len(mgr.grid_config.cells) > 0
    assert "a" in mgr.grid_config.cells

    # Vérification des actions
    assert len(mgr.actions) >= 5
    action_t = mgr.get_action_for_key("t", "special")
    assert action_t is not None
    assert action_t.name == "Nouvel Onglet Navigateur"

    # Vérification des références
    assert len(mgr.commands_reference) > 0
    assert len(mgr.keys_reference) > 0


def test_config_save_and_reload(tmp_path: Path):
    mgr = ConfigManager(base_dir=tmp_path)
    mgr.app_config.general.special_mode_key = "f1"
    mgr.app_config.ui.font_size = 16
    mgr.app_config.ui.theme = "light"

    assert mgr.save_app_config() is True

    # Recharger dans une nouvelle instance
    mgr2 = ConfigManager(base_dir=tmp_path)
    loaded = mgr2.load_app_config()
    assert loaded.general.special_mode_key == "f1"
    assert loaded.ui.font_size == 16
    assert loaded.ui.theme == "light"
