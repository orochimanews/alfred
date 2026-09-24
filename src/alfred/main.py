"""Point d'entrée principal de l'application Alfred."""

from __future__ import annotations
import sys
import logging
import argparse
from pathlib import Path

import os
import threading

# En mode PyInstaller --windowed, sys.stdout et sys.stderr sont None.
# On les redirige pour éviter les AttributeError dans les bibliothèques tierces.
if sys.stdout is None:
    try:
        sys.stdout = open(os.devnull, "w", encoding="utf-8")
    except Exception:
        pass
if sys.stderr is None:
    try:
        sys.stderr = open(os.devnull, "w", encoding="utf-8")
    except Exception:
        pass


def setup_logging() -> None:
    """Configure la journalisation à la fois sur console et dans alfred.log."""
    if getattr(sys, "frozen", False):
        app_dir = Path(sys.executable).resolve().parent
    else:
        app_dir = Path(__file__).resolve().parent.parent.parent

    log_file = app_dir / "alfred.log"
    handlers: list[logging.Handler] = [
        logging.FileHandler(log_file, encoding="utf-8", mode="a"),
    ]
    if sys.stderr is not None and not getattr(sys.stderr, "closed", False):
        try:
            handlers.append(logging.StreamHandler(sys.stderr))
        except Exception:
            pass

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
        handlers=handlers,
    )


setup_logging()
logger = logging.getLogger("Alfred")


def _install_exception_handlers() -> None:
    """Capture les exceptions non gérées du thread principal et des threads d'arrière-plan."""
    def _handle_unhandled_exception(exc_type, exc_value, exc_traceback):
        logger.critical("Exception non gérée reçue :", exc_info=(exc_type, exc_value, exc_traceback))

    sys.excepthook = _handle_unhandled_exception

    if hasattr(threading, "excepthook"):
        def _handle_thread_exception(args):
            logger.critical("Exception non gérée dans le thread '%s' :", args.thread.name, exc_info=(args.exc_type, args.exc_value, args.exc_traceback))
        threading.excepthook = _handle_thread_exception


_install_exception_handlers()


def configure_windows_process() -> None:
    """Optimise le processus sous Windows (priorité et prévention du mode efficacité EcoQoS)."""
    if sys.platform != "win32":
        return

    try:
        import ctypes
        from ctypes import wintypes

        # 1. Identifiant AppUserModelID pour la barre des tâches
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("alfred.shortcut.system.v1")
        except Exception:
            pass

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        p_handle = kernel32.GetCurrentProcess()

        # 2. Définir la priorité du processus à Haute (HIGH_PRIORITY_CLASS)
        # Nécessaire pour que le hook système bas niveau ne subisse aucun lag en tâche de fond
        HIGH_PRIORITY_CLASS = 0x00000080
        kernel32.SetPriorityClass(p_handle, HIGH_PRIORITY_CLASS)

        # 3. Désactiver explicitement le Power Throttling / EcoQoS Windows 11
        # Empêche Windows de suspendre ou ralentir les threads d'arrière-plan quand la fenêtre est minimisée
        try:
            ProcessPowerThrottling = 4
            PROCESS_POWER_THROTTLING_CURRENT_VERSION = 1
            PROCESS_POWER_THROTTLING_EXECUTION_SPEED = 0x1

            class PROCESS_POWER_THROTTLING_STATE(ctypes.Structure):
                _fields_ = [
                    ("Version", wintypes.DWORD),
                    ("ControlMask", wintypes.DWORD),
                    ("StateMask", wintypes.DWORD),
                ]

            throttling_state = PROCESS_POWER_THROTTLING_STATE()
            throttling_state.Version = PROCESS_POWER_THROTTLING_CURRENT_VERSION
            throttling_state.ControlMask = PROCESS_POWER_THROTTLING_EXECUTION_SPEED
            throttling_state.StateMask = 0  # Désactiver le throttling

            # OpenProcess avec PROCESS_SET_INFORMATION (0x0200) requis pour SetProcessInformation
            h_proc_set = kernel32.OpenProcess(0x0200, False, kernel32.GetCurrentProcessId())
            if h_proc_set:
                try:
                    kernel32.SetProcessInformation(
                        h_proc_set,
                        ProcessPowerThrottling,
                        ctypes.byref(throttling_state),
                        ctypes.sizeof(throttling_state),
                    )
                finally:
                    kernel32.CloseHandle(h_proc_set)
        except Exception:
            pass

        # 4. Résolution timer à 1 ms via winmm.timeBeginPeriod
        # Sans ça, Windows peut coarsener le scheduler à ~15 ms en arrière-plan,
        # retardant ou bloquant la livraison des messages Win32 au thread du hook clavier.
        try:
            winmm = ctypes.WinDLL("winmm")
            winmm.timeBeginPeriod(1)
        except Exception:
            pass

        logger.info("Configuration système Windows appliquée (Haute priorité & EcoQoS prévenu).")
    except Exception as err:
        logger.debug("Impossible d'appliquer certaines optimisations système Windows : %s", err)


from src.alfred.core.config import ConfigManager
from src.alfred.core.state import StateManager
from src.alfred.core.grid import GridManager
from src.alfred.core.move import MoveManager
from src.alfred.core.commands_engine import CommandsEngine
from src.alfred.core.hook import KeyboardHookService
from src.alfred.core.mouse import mouse
from src.alfred.core.text_focus import TextInputFocusWatcher


def main() -> None:
    parser = argparse.ArgumentParser(description="Alfred - Raccourcis Clavier à Modes & Grille d'Écran")
    parser.add_argument("--headless", action="store_true", help="Lancer en tâche de fond sans interface graphique")
    args = parser.parse_args()

    logger.info("Démarrage d'Alfred...")

    # Application des optimisations de processus Windows
    configure_windows_process()

    # 1. Chargement de la configuration
    config_mgr = ConfigManager()
    config_mgr.load_all()

    # 2. Initialisation de l'état
    gen_cfg = config_mgr.app_config.general
    initial_mode = "special" if getattr(gen_cfg, "start_in_special_mode", True) else getattr(gen_cfg, "default_mode", "normal")
    if not getattr(gen_cfg, "start_in_special_mode", True) and initial_mode == "special":
        initial_mode = "normal"
    state_mgr = StateManager(initial_mode=initial_mode)

    # 3. Initialisation des sous-systèmes
    move_mgr = MoveManager(
        config=config_mgr.move_config,
        mouse_controller=mouse,
        state_manager=state_mgr,
    )
    grid_mgr = GridManager(config=config_mgr.grid_config, state_manager=state_mgr)
    commands_engine = CommandsEngine(
        state_manager=state_mgr,
        grid_manager=grid_mgr,
        config_manager=config_mgr,
        move_manager=move_mgr,
    )
    hook_service = KeyboardHookService(
        state_manager=state_mgr,
        config_manager=config_mgr,
        commands_engine=commands_engine,
        grid_manager=grid_mgr,
        move_manager=move_mgr,
    )
    text_focus_watcher = TextInputFocusWatcher(
        state_manager=state_mgr,
        config_manager=config_mgr,
    )

    # 4. Démarrage des services d'arrière-plan
    hook_service.start()
    if getattr(config_mgr.app_config.general, "auto_exit_on_text_input", False):
        text_focus_watcher.start()

    if args.headless:
        quit_event = threading.Event()
        hook_service.set_quit_callback(quit_event.set)
        commands_engine.set_quit_callback(quit_event.set)
        logger.info("Mode Headless activé. Utilisez le raccourci configuré ou Ctrl+C pour quitter.")
        try:
            while not quit_event.is_set():
                if quit_event.wait(timeout=0.5):
                    break
        except KeyboardInterrupt:
            logger.info("Arrêt du mode headless...")
        finally:
            text_focus_watcher.stop()
            hook_service.stop()
            move_mgr.stop()
            mouse.restore_initial_speed()
            mouse.stop_nudge_mode()
        return

    # 5. Lancement de l'interface graphique CustomTkinter
    try:
        from src.alfred.ui.app import AlfredApp
        app = AlfredApp(
            config_manager=config_mgr,
            state_manager=state_mgr,
            commands_engine=commands_engine,
            grid_manager=grid_mgr,
            hook_service=hook_service,
            move_manager=move_mgr,
            text_focus_watcher=text_focus_watcher,
        )

        app.protocol("WM_DELETE_WINDOW", app.close)
        app.mainloop()

    except Exception as err:
        logger.error("Erreur d'exécution de l'application : %s", err, exc_info=True)
    finally:
        text_focus_watcher.stop()
        hook_service.stop()
        move_mgr.stop()
        mouse.restore_initial_speed()
        mouse.stop_nudge_mode()


if __name__ == "__main__":
    main()
