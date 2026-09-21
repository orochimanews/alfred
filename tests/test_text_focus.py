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


def test_auto_return_on_enter_config_default():
    """Vérifie que auto_return_on_enter est activé par défaut."""
    gen = GeneralConfig()
    assert gen.auto_return_on_enter is True


def test_state_manager_auto_switched_flag():
    """Vérifie la gestion du drapeau is_auto_switched_to_normal dans StateManager."""
    state_mgr = StateManager(initial_mode="special")
    assert state_mgr.is_auto_switched_to_normal is False

    # Quand on passe en normal manuellement, c'est False
    state_mgr.set_mode("normal")
    assert state_mgr.is_auto_switched_to_normal is False

    # Activé explicitement suite à un focus champ texte
    state_mgr.set_auto_switched_to_normal(True)
    assert state_mgr.is_auto_switched_to_normal is True

    # Si le mode change vers 'special', le drapeau retombe à False
    state_mgr.set_mode("special")
    assert state_mgr.is_auto_switched_to_normal is False


def test_hook_returns_to_special_on_enter():
    """Vérifie que la touche Entrée déclenche le retour au mode spécial sans bloquer la touche."""
    import time
    from src.alfred.core.hook import KeyboardHookService
    import keyboard

    state_mgr = StateManager(initial_mode="normal")
    state_mgr.set_auto_switched_to_normal(True)

    config_mgr = MagicMock()
    config_mgr.app_config.general.auto_return_on_enter = True
    config_mgr.app_config.general.special_mode_key = "!"
    config_mgr.app_config.general.special_mode_name = "special"
    config_mgr.move_config.enabled = False
    config_mgr.grid_config.enabled = False
    config_mgr.get_action_for_key.return_value = None

    hook_service = KeyboardHookService(
        state_manager=state_mgr,
        config_manager=config_mgr,
        commands_engine=MagicMock(),
        grid_manager=MagicMock(),
    )

    event = keyboard.KeyboardEvent(
        event_type=keyboard.KEY_DOWN,
        scan_code=28,
        name="enter",
    )

    # L'événement doit retourner True (la touche passe à l'application)
    res = hook_service._on_key_event(event)
    assert res is True

    # Le drapeau est immédiatement consommé
    assert state_mgr.is_auto_switched_to_normal is False

    # Attendre la fin du délai du thread worker
    time.sleep(0.1)
    assert state_mgr.current_mode == "special"
    logs = state_mgr.logs
    assert len(logs) > 0
    assert logs[0].trigger_key == "Entrée"
    assert "Validation par Entrée" in logs[0].details


def test_hook_does_not_return_to_special_on_shift_enter():
    """Vérifie que Shift+Entrée (saut de ligne) ne déclenche pas le retour au mode spécial."""
    from src.alfred.core.hook import KeyboardHookService
    import keyboard

    state_mgr = StateManager(initial_mode="normal")
    state_mgr.set_auto_switched_to_normal(True)

    config_mgr = MagicMock()
    config_mgr.app_config.general.auto_return_on_enter = True
    config_mgr.app_config.general.special_mode_key = "!"
    config_mgr.app_config.general.special_mode_name = "special"
    config_mgr.move_config.enabled = False
    config_mgr.grid_config.enabled = False
    config_mgr.get_action_for_key.return_value = None

    hook_service = KeyboardHookService(
        state_manager=state_mgr,
        config_manager=config_mgr,
        commands_engine=MagicMock(),
        grid_manager=MagicMock(),
    )

    # Simuler Shift enfoncé
    hook_service._pressed_keys.add("shift")

    event = keyboard.KeyboardEvent(
        event_type=keyboard.KEY_DOWN,
        scan_code=28,
        name="enter",
    )

    res = hook_service._on_key_event(event)
    assert res is True
    # Doit rester en normal
    assert state_mgr.current_mode == "normal"
    assert state_mgr.is_auto_switched_to_normal is True


def test_hook_does_not_return_to_special_if_manual_normal():
    """Vérifie que la touche Entrée ne repasse pas en spécial si le mode normal a été activé manuellement."""
    import time
    from src.alfred.core.hook import KeyboardHookService
    import keyboard

    state_mgr = StateManager(initial_mode="normal")
    # Pas de flag auto_switched !
    assert state_mgr.is_auto_switched_to_normal is False

    config_mgr = MagicMock()
    config_mgr.app_config.general.auto_return_on_enter = True
    config_mgr.app_config.general.special_mode_key = "!"
    config_mgr.app_config.general.special_mode_name = "special"
    config_mgr.move_config.enabled = False
    config_mgr.grid_config.enabled = False
    config_mgr.get_action_for_key.return_value = None

    hook_service = KeyboardHookService(
        state_manager=state_mgr,
        config_manager=config_mgr,
        commands_engine=MagicMock(),
        grid_manager=MagicMock(),
    )

    event = keyboard.KeyboardEvent(
        event_type=keyboard.KEY_DOWN,
        scan_code=28,
        name="enter",
    )

    res = hook_service._on_key_event(event)
    assert res is True
    time.sleep(0.1)
    # Reste en normal !
    assert state_mgr.current_mode == "normal"

