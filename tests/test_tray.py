"""Tests unitaires pour le service d'icône dans la zone de notification (Tray)."""

from unittest.mock import MagicMock, patch
from PIL import Image
from src.alfred.ui.tray import create_tray_icon_image, TrayIconService


def test_create_tray_icon_image():
    # Test génération pour tous les modes
    for mode in ("normal", "special", "grid", "unknown"):
        img = create_tray_icon_image(mode)
        assert isinstance(img, Image.Image)
        assert img.size == (64, 64)
        assert img.mode == "RGBA"


def test_tray_icon_service_callbacks():
    mock_restore = MagicMock()
    mock_quit = MagicMock()
    mock_toggle_mode = MagicMock()
    mock_toggle_hook = MagicMock()

    service = TrayIconService(
        on_restore=mock_restore,
        on_quit=mock_quit,
        on_toggle_mode=mock_toggle_mode,
        on_toggle_hook=mock_toggle_hook,
        initial_mode="normal",
        is_hook_enabled=True,
    )

    # Test menu building
    menu = service._build_menu()
    assert menu is not None

    # Test invoking callbacks
    service._handle_restore()
    mock_restore.assert_called_once()

    service._handle_quit()
    mock_quit.assert_called_once()

    service._handle_toggle_mode()
    mock_toggle_mode.assert_called_once()

    service._handle_toggle_hook()
    mock_toggle_hook.assert_called_once()


def test_tray_icon_service_start_and_stop():
    mock_restore = MagicMock()
    mock_quit = MagicMock()

    service = TrayIconService(
        on_restore=mock_restore,
        on_quit=mock_quit,
    )

    with patch("pystray.Icon") as mock_icon_cls:
        mock_icon_instance = MagicMock()
        mock_icon_cls.return_value = mock_icon_instance

        service.start()
        assert service._is_running is True
        mock_icon_instance.run_detached.assert_called_once()

        # Update mode
        service.update_mode("special")
        assert service.current_mode == "special"

        # Update hook state
        service.update_hook_state(False)
        assert service.is_hook_enabled is False

        # Notify
        service.notify("Titre", "Message")
        mock_icon_instance.notify.assert_called_once_with("Message", "Titre")

        # Stop
        service.stop()
        assert service._is_running is False
        mock_icon_instance.stop.assert_called_once()
