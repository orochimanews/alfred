"""Gestion et localisation des ressources statiques (icônes, images) d'Alfred."""

from __future__ import annotations
import sys
from pathlib import Path


def get_assets_dir() -> Path:
    """Retourne le chemin absolu du dossier assets.

    Compatible exécution source locale et mode paquet autonome (PyInstaller).
    """
    # 1. Mode PyInstaller (_MEIPASS temporaire)
    if hasattr(sys, "_MEIPASS"):
        meipass_assets = Path(sys._MEIPASS) / "assets"
        if meipass_assets.exists():
            return meipass_assets

    # 2. Mode PyInstaller (répertoire de l'exécutable .exe)
    if getattr(sys, "frozen", False):
        exe_assets = Path(sys.executable).parent / "assets"
        if exe_assets.exists():
            return exe_assets

    # 3. Mode développement source
    # Racine du projet (au-dessus de src/alfred/core)
    root_dir = Path(__file__).resolve().parent.parent.parent.parent
    return root_dir / "assets"


def get_asset_path(filename: str) -> Path:
    """Retourne le chemin complet d'une ressource dans le dossier assets."""
    return get_assets_dir() / filename


def get_icon_ico_path() -> Path:
    """Retourne le chemin de l'icône Windows .ico d'Alfred."""
    return get_asset_path("icon.ico")


def get_icon_png_path() -> Path:
    """Retourne le chemin de l'icône PNG d'Alfred."""
    return get_asset_path("icon.png")
