"""Service de détection du focus sur les champs de saisie texte (UI Automation)."""

from __future__ import annotations
import sys
import threading
import logging
import ctypes
from ctypes import wintypes
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.alfred.core.state import StateManager
    from src.alfred.core.config import ConfigManager

logger = logging.getLogger(__name__)

# Identifiants UI Automation standard (UIAutomationCore)
UIA_EDIT_CONTROL_TYPE_ID = 50004
UIA_DOCUMENT_CONTROL_TYPE_ID = 50030
UIA_COMBO_BOX_CONTROL_TYPE_ID = 50003

UIA_VALUE_IS_READ_ONLY_PROPERTY_ID = 30046

CUI_AUTOMATION8_CLSID = "{ff48dba4-60ef-4201-aa87-54103eef594e}"


class TextInputFocusWatcher:
    """Surveille les changements de focus système pour basculer automatiquement en mode normal.
    
    Lorsque l'utilisateur clique ou navigue sur un champ texte (barre de recherche, input web,
    éditeur de code, bloc-notes, etc.), Alfred détecte l'événement via Windows UI Automation
    et repasse immédiatement en mode 'normal'.
    """

    def __init__(
        self,
        state_manager: StateManager,
        config_manager: ConfigManager,
    ) -> None:
        self.state_manager = state_manager
        self.config_manager = config_manager
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._is_running: bool = False
        self._lock = threading.Lock()

    @property
    def is_running(self) -> bool:
        with self._lock:
            return self._is_running

    def start(self) -> None:
        """Démarre le service d'écoute du focus en arrière-plan."""
        if sys.platform != "win32":
            logger.debug("TextInputFocusWatcher n'est supporté que sous Windows.")
            return

        with self._lock:
            if self._is_running:
                return
            self._is_running = True
            self._stop_event.clear()
            self._thread = threading.Thread(
                target=self._worker_loop,
                daemon=True,
                name="Alfred-TextInputFocusWatcher",
            )
            self._thread.start()
            logger.info("Service de détection de champ texte (UI Automation) démarré.")

    def stop(self) -> None:
        """Arrête proprement le service d'écoute."""
        with self._lock:
            if not self._is_running:
                return
            self._is_running = False
            self._stop_event.set()

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.5)
            self._thread = None
        logger.info("Service de détection de champ texte arrêté.")

    def _worker_loop(self) -> None:
        """Boucle d'écoute Win32 / COM pour UI Automation."""
        user32 = ctypes.windll.user32
        ole32 = ctypes.windll.ole32

        handler = None
        uia = None

        try:
            import comtypes
            import comtypes.client

            UIAutomationCore = comtypes.client.GetModule("UIAutomationCore.dll")
            uia = comtypes.client.CreateObject(
                CUI_AUTOMATION8_CLSID,
                interface=UIAutomationCore.IUIAutomation,
            )

            watcher_ref = self

            class FocusHandler(comtypes.COMObject):
                _com_interfaces_ = [UIAutomationCore.IUIAutomationFocusChangedEventHandler]

                def HandleFocusChangedEvent(self, sender: Any) -> None:
                    watcher_ref._on_focus_changed(sender, UIAutomationCore)

            handler = FocusHandler()
            uia.AddFocusChangedEventHandler(None, handler)
            logger.debug("Gestionnaire de focus UI Automation enregistré avec succès.")

            msg = wintypes.MSG()
            while not self._stop_event.is_set():
                # Attendre les messages ou le timeout de 50ms pour vérifier _stop_event
                user32.MsgWaitForMultipleObjects(0, None, False, 50, 0x04FF)  # QS_ALLINPUT
                while user32.PeekMessageW(ctypes.byref(msg), 0, 0, 0, 1):  # PM_REMOVE = 1
                    user32.TranslateMessage(ctypes.byref(msg))
                    user32.DispatchMessageW(ctypes.byref(msg))

        except Exception as err:
            logger.warning(
                "Impossible d'initialiser le gestionnaire UI Automation (désactivation douce) : %s",
                err,
            )
        finally:
            if uia and handler:
                try:
                    uia.RemoveFocusChangedEventHandler(handler)
                    logger.debug("Gestionnaire de focus UI Automation désenregistré.")
                except Exception as err:
                    logger.debug("Erreur lors du désenregistrement UI Automation : %s", err)

    def _on_focus_changed(self, sender: Any, uia_core: Any) -> None:
        """Appelé par Windows lorsqu'un élément prend le focus."""
        try:
            # 1. Vérifier si l'option est activée
            if not self.config_manager.app_config.general.auto_exit_on_text_input:
                return

            # 2. Si on est déjà en mode normal, rien à faire
            current_mode = self.state_manager.current_mode
            if current_mode == "normal":
                return

            # 3. Vérifier si le contrôle est un champ de saisie texte
            if not self._is_text_input(sender, uia_core):
                return

            # 4. Basculer en mode normal
            name = ""
            try:
                name = str(sender.CurrentName or "").strip()
            except Exception:
                pass

            logger.info("Champ texte détecté avec focus ('%s'). Bascule vers mode 'normal'.", name)
            switched = self.state_manager.set_mode("normal")
            if switched:
                self.state_manager.add_log(
                    action_name="Auto-retour Mode Normal (Champ texte)",
                    trigger_key="Focus",
                    mode=current_mode,
                    status="success",
                    details=f"Champ détecté : {name}" if name else "Champ de saisie texte",
                )

        except Exception as err:
            logger.debug("Erreur lors de l'inspection de l'élément avec focus : %s", err)

    def _is_text_input(self, sender: Any, uia_core: Any) -> bool:
        """Détermine si l'élément UI Automation correspond à un champ de saisie éditable."""
        try:
            ctype = sender.CurrentControlType

            # Champ de saisie standard (ex: barre d'URL, champs de formulaire, searchbox)
            if ctype == UIA_EDIT_CONTROL_TYPE_ID:
                return True

            # Document de texte (ex: Bloc-notes, VS Code, éditeur de code, textarea)
            if ctype == UIA_DOCUMENT_CONTROL_TYPE_ID:
                val = sender.GetCurrentPropertyValue(UIA_VALUE_IS_READ_ONLY_PROPERTY_ID)
                return not bool(val)

            # Liste déroulante éditable
            if ctype == UIA_COMBO_BOX_CONTROL_TYPE_ID:
                val = sender.GetCurrentPropertyValue(UIA_VALUE_IS_READ_ONLY_PROPERTY_ID)
                return not bool(val)

        except Exception:
            pass

        return False
