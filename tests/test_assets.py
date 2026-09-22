"""Tests unitaires pour le module de gestion des ressources statiques (assets)."""

from pathlib import Path
from src.alfred.core.assets import (
    get_assets_dir,
    get_asset_path,
    get_icon_ico_path,
    get_icon_png_path,
)


def test_assets_paths_exist():
    assets_dir = get_assets_dir()
    assert isinstance(assets_dir, Path)
    assert assets_dir.exists()
    assert assets_dir.is_dir()

    ico_path = get_icon_ico_path()
    assert ico_path.exists()
    assert ico_path.is_file()
    assert ico_path.suffix == ".ico"
    assert ico_path.stat().st_size > 0

    png_path = get_icon_png_path()
    assert png_path.exists()
    assert png_path.is_file()
    assert png_path.suffix == ".png"
    assert png_path.stat().st_size > 0


def test_get_asset_path_custom():
    path = get_asset_path("custom_file.txt")
    assert path.name == "custom_file.txt"
    assert path.parent == get_assets_dir()
