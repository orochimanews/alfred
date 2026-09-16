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
    assert len(mgr.actions) >= 1
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
