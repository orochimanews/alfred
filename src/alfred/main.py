"""Point d'entrée principal de l'application Alfred."""

from __future__ import annotations
import sys
import logging
import argparse
from pathlib import Path

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
    if sys.stderr is not None:
        handlers.append(logging.StreamHandler(sys.stderr))

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
        handlers=handlers,
    )

setup_logging()
logger = logging.getLogger("Alfred")

from src.alfred.core.config import ConfigManager
from src.alfred.core.state import StateManager
from src.alfred.core.grid import GridManager
from src.alfred.core.commands_engine import CommandsEngine
from src.alfred.core.hook import KeyboardHookService
from src.alfred.core.mouse import mouse


def main() -> None:
    parser = argparse.ArgumentParser(description="Alfred - Raccourcis Clavier à Modes & Grille d'Écran")
    parser.add_argument("--headless", action="store_true", help="Lancer en tâche de fond sans interface graphique")
    args = parser.parse_args()

    logger.info("Démarrage d'Alfred...")

    # Association de l'icône personnalisée d'Alfred dans la barre des tâches Windows
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("alfred.shortcut.system.v1")
        except Exception:
            pass

    # 1. Chargement de la configuration
    config_mgr = ConfigManager()
    config_mgr.load_all()

    # 2. Initialisation de l'état
    default_mode = config_mgr.app_config.general.default_mode
    state_mgr = StateManager(initial_mode=default_mode)

    # 3. Initialisation des sous-systèmes
    grid_mgr = GridManager(config=config_mgr.grid_config, state_manager=state_mgr)
    commands_engine = CommandsEngine(
        state_manager=state_mgr,
        grid_manager=grid_mgr,
        config_manager=config_mgr,
    )
    hook_service = KeyboardHookService(
        state_manager=state_mgr,
        config_manager=config_mgr,
        commands_engine=commands_engine,
        grid_manager=grid_mgr,
    )

    # 4. Démarrage du hook clavier
    hook_service.start()

    if args.headless:
        logger.info("Mode Headless activé. Appuyez sur Ctrl+C pour quitter.")
        try:
            import keyboard
            keyboard.wait()
        except KeyboardInterrupt:
            logger.info("Arrêt du mode headless...")
        finally:
            hook_service.stop()
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
        )

        app.protocol("WM_DELETE_WINDOW", app.close)
        app.mainloop()

    except Exception as err:
        logger.error("Erreur d'exécution de l'application : %s", err, exc_info=True)
    finally:
        hook_service.stop()
        mouse.restore_initial_speed()
        mouse.stop_nudge_mode()


if __name__ == "__main__":
    main()
