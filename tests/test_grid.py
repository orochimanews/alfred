"""Tests unitaires pour les calculs de grille d'écran."""

from src.alfred.core.models import GridConfig
from src.alfred.core.grid import GridManager


def test_grid_cell_center_calculation():
    cfg = GridConfig(
        enabled=True,
        columns=3,
        rows=3,
        cells={
            "a": (0, 0),
            "s": (1, 1),
            "c": (2, 2),
        }
    )
    grid = GridManager(config=cfg)

    # Écran simulé 1920 x 1080
    w, h = 1920, 1080
    # Case (0, 0) : centre à ( (0 + 0.5) * 640, (0 + 0.5) * 360 ) = (320, 180)
    assert grid.get_cell_center(0, 0, w, h) == (320, 180)

    # Case (1, 1) : centre à ( (1 + 0.5) * 640, (1 + 0.5) * 360 ) = (960, 540)
    assert grid.get_cell_center(1, 1, w, h) == (960, 540)

    # Case (2, 2) : centre à ( (2 + 0.5) * 640, (2 + 0.5) * 360 ) = (1600, 900)
    assert grid.get_cell_center(2, 2, w, h) == (1600, 900)


def test_grid_key_detection():
    cfg = GridConfig(
        enabled=True,
        columns=3,
        rows=3,
        cells={"a": (0, 0), "z": (1, 0)}
    )
    grid = GridManager(config=cfg)

    assert grid.is_grid_key("a") is True
    assert grid.is_grid_key("A") is True
    assert grid.is_grid_key("k") is False
