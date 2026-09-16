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


def test_grid_config_numpad_and_mode_parsing():
    data = {
        "grid": {
            "active_modes": ["special, grid"],
        },
        "cells": {
            "&": [0, 0],
            "é": [1, 0],
            "num_7": [0, 0],
        }
    }
    cfg = GridConfig.from_dict(data)
    assert cfg.active_modes == ["special", "grid"]
    assert "&" in cfg.cells
    assert "é" in cfg.cells
    assert "num_7" in cfg.cells
    assert "7" in cfg.cells
    assert "7 (pavé num.)" in cfg.cells


def test_grid_get_cell_at_position():
    cfg = GridConfig(enabled=True, columns=3, rows=3)
    grid = GridManager(config=cfg)
    w, h = 1920, 1080

    assert grid.get_cell_at_position(100, 100, w, h) == (0, 0)
    assert grid.get_cell_at_position(960, 100, w, h) == (1, 0)
    assert grid.get_cell_at_position(1800, 100, w, h) == (2, 0)
    assert grid.get_cell_at_position(100, 500, w, h) == (0, 1)
    assert grid.get_cell_at_position(960, 540, w, h) == (1, 1)
    assert grid.get_cell_at_position(1800, 1000, w, h) == (2, 2)


def test_edge_snap_calculations():
    cfg = GridConfig(enabled=True, columns=3, rows=3, edge_offset=10)
    grid = GridManager(config=cfg)
    w, h = 1920, 1080

    # Coin haut-gauche : case (0, 0) -> x=10, y=10
    assert grid.calculate_edge_snap(320, 180, w, h) == (10, 10)

    # Haut-milieu : case (1, 0) -> x inchangé (960), y=10
    assert grid.calculate_edge_snap(960, 180, w, h) == (960, 10)

    # Coin haut-droite : case (2, 0) -> x=1909 (1920 - 1 - 10), y=10
    assert grid.calculate_edge_snap(1600, 180, w, h) == (1909, 10)

    # Centre-gauche : case (0, 1) -> x=10, y inchangé (540)
    assert grid.calculate_edge_snap(320, 540, w, h) == (10, 540)

    # Centre exact : case (1, 1) -> ne touche aucun bord -> None
    assert grid.calculate_edge_snap(960, 540, w, h) is None

    # Coin bas-droite : case (2, 2) -> x=1909, y=1069 (1080 - 1 - 10)
    assert grid.calculate_edge_snap(1600, 900, w, h) == (1909, 1069)

    # Test avec offset personnalisé (paramètre direct)
    assert grid.calculate_edge_snap(320, 180, w, h, offset=5) == (5, 5)


def test_edge_snap_key_detection():
    # Test avec la touche 'à' par défaut
    cfg_default = GridConfig.from_dict({"grid": {}})
    assert cfg_default.edge_snap_key == "à"
    grid_default = GridManager(config=cfg_default)
    assert grid_default.is_edge_snap_key("à") is True
    assert grid_default.is_edge_snap_key("0") is True
    assert grid_default.is_edge_snap_key("num_0") is True

    cfg = GridConfig.from_dict({
        "grid": {
            "edge_snap_key": "0",
            "edge_offset": 15,
        }
    })
    grid = GridManager(config=cfg)

    assert grid.is_edge_snap_key("0") is True
    assert grid.is_edge_snap_key("num_0") is True
    assert grid.is_edge_snap_key("à") is True
    assert grid.is_edge_snap_key("num 0") is True
    assert grid.is_edge_snap_key("0 (pavé num.)") is True
    assert grid.is_edge_snap_key("a") is False


def test_edge_snap_config_steps_alias():
    cfg = GridConfig.from_dict({
        "grid": {
            "steps": 25,
            "edge_snap_key": "x",
        }
    })
    assert cfg.edge_offset == 25
    assert cfg.edge_snap_key == "x"
    assert "x" in cfg.edge_snap_keys

