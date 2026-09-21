"""Tests unitaires pour la détection de focus champ texte et auto-exit mode spécial."""

from unittest.mock import MagicMock
from src.alfred.core.models import GeneralConfig, AppConfig
from src.alfred.core.config import ConfigManager
from src.alfred.core.state import StateManager
from src.alfred.core.text_focus import (
    TextInputFocusWatcher,
    UIA_EDIT_CONTROL_TYPE_ID,
    UIA_DOCUMENT_CONTROL_TYPE_ID,
    UIA_COMBO_BOX_CONTROL_TYPE_ID,
    UIA_VALUE_IS_READ_ONLY_PROPERTY_ID,
)


def test_general_config_auto_exit_default():
    """Vérifie que l'option auto_exit_on_text_input est activée par défaut."""
    gen = GeneralConfig()
    assert gen.auto_exit_on_text_input is True


def test_config_manager_load_and_save_auto_exit(tmp_path):
    """Vérifie la persistance de l'option auto_exit_on_text_input."""
    cfg_mgr = ConfigManager(base_dir=tmp_path)
    cfg_mgr.config_path = tmp_path / "config.toml"
    cfg_mgr.settings_dir = tmp_path

    # Sauvegarde avec True
    cfg_mgr.app_config.general.auto_exit_on_text_input = True
    cfg_mgr.save_app_config()

    # Rechargement
    loaded = cfg_mgr.load_app_config()
    assert loaded.general.auto_exit_on_text_input is True

    # Modification vers False et re-sauvegarde
    cfg_mgr.app_config.general.auto_exit_on_text_input = False
    cfg_mgr.save_app_config()

    loaded2 = cfg_mgr.load_app_config()
    assert loaded2.general.auto_exit_on_text_input is False


def test_is_text_input_detection():
    """Teste la classification des types de contrôles UI Automation."""
    state_mgr = StateManager(initial_mode="special")
    config_mgr = MagicMock()
    watcher = TextInputFocusWatcher(state_mgr, config_mgr)

    # 1. EditControl -> True
    edit_elem = MagicMock()
    edit_elem.CurrentControlType = UIA_EDIT_CONTROL_TYPE_ID
    assert watcher._is_text_input(edit_elem, None) is True

    # 2. DocumentControl éditable -> True
    doc_elem = MagicMock()
    doc_elem.CurrentControlType = UIA_DOCUMENT_CONTROL_TYPE_ID
    doc_elem.GetCurrentPropertyValue.return_value = False
    assert watcher._is_text_input(doc_elem, None) is True

    # 3. DocumentControl en lecture seule -> False
    doc_ro = MagicMock()
    doc_ro.CurrentControlType = UIA_DOCUMENT_CONTROL_TYPE_ID
    doc_ro.GetCurrentPropertyValue.return_value = True
    assert watcher._is_text_input(doc_ro, None) is False

    # 4. ComboBox éditable -> True
    combo_elem = MagicMock()
    combo_elem.CurrentControlType = UIA_COMBO_BOX_CONTROL_TYPE_ID
    combo_elem.GetCurrentPropertyValue.return_value = False
    assert watcher._is_text_input(combo_elem, None) is True

    # 5. Bouton ou panneau -> False
    btn_elem = MagicMock()
    btn_elem.CurrentControlType = 50000  # UIA_ButtonControlTypeId
    assert watcher._is_text_input(btn_elem, None) is False


def test_on_focus_changed_switches_mode_when_special():
    """Vérifie que la détection d'un champ texte bascule de 'special' vers 'normal'."""
    state_mgr = StateManager(initial_mode="special")
    config_mgr = MagicMock()
    config_mgr.app_config.general.auto_exit_on_text_input = True

    watcher = TextInputFocusWatcher(state_mgr, config_mgr)

    edit_elem = MagicMock()
    edit_elem.CurrentControlType = UIA_EDIT_CONTROL_TYPE_ID
    edit_elem.CurrentName = "Champ Recherche"

    watcher._on_focus_changed(edit_elem, None)

    assert state_mgr.current_mode == "normal"
    logs = state_mgr.logs
    assert len(logs) > 0
    assert "Champ texte" in logs[0].action_name


def test_on_focus_changed_ignored_when_disabled():
    """Vérifie qu'aucune bascule n'a lieu si l'option est désactivée."""
    state_mgr = StateManager(initial_mode="special")
    config_mgr = MagicMock()
    config_mgr.app_config.general.auto_exit_on_text_input = False

    watcher = TextInputFocusWatcher(state_mgr, config_mgr)

    edit_elem = MagicMock()
    edit_elem.CurrentControlType = UIA_EDIT_CONTROL_TYPE_ID

    watcher._on_focus_changed(edit_elem, None)

    assert state_mgr.current_mode == "special"


def test_on_focus_changed_ignored_when_already_normal():
    """Vérifie qu'aucune bascule n'a lieu si Alfred est déjà en mode normal."""
    state_mgr = StateManager(initial_mode="normal")
    config_mgr = MagicMock()
    config_mgr.app_config.general.auto_exit_on_text_input = True

    watcher = TextInputFocusWatcher(state_mgr, config_mgr)

    edit_elem = MagicMock()
    edit_elem.CurrentControlType = UIA_EDIT_CONTROL_TYPE_ID

    watcher._on_focus_changed(edit_elem, None)

    assert state_mgr.current_mode == "normal"
    assert len(state_mgr.logs) == 0


def test_on_focus_changed_ignored_for_non_text_control():
    """Vérifie qu'un contrôle non-texte (ex: bouton) ne change pas le mode."""
    state_mgr = StateManager(initial_mode="special")
    config_mgr = MagicMock()
    config_mgr.app_config.general.auto_exit_on_text_input = True

    watcher = TextInputFocusWatcher(state_mgr, config_mgr)

    btn_elem = MagicMock()
    btn_elem.CurrentControlType = 50000  # Button

    watcher._on_focus_changed(btn_elem, None)

    assert state_mgr.current_mode == "special"
    assert len(state_mgr.logs) == 0
