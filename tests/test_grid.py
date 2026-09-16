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


def test_subgrid_calculations():
    """Vérifie le calcul des coordonnées au centre des sous-cases 3x3."""
    cfg = GridConfig(
        enabled=True,
        columns=3,
        rows=3,
        subgrid_columns=3,
        subgrid_rows=3,
        cells={"&": (0, 0), "(": (1, 1), "ç": (2, 2)}
    )
    grid = GridManager(config=cfg)
    w, h = 1920, 1080

    # Case parente (0, 0) [coin haut-gauche de l'écran : 0..640 en X, 0..360 en Y]
    # Sous-case (0, 0) : centre à ((0 + 0.5/3) * 640, (0 + 0.5/3) * 360) = (106, 60)
    assert grid.get_subcell_center(0, 0, 0, 0, w, h) == (106, 60)

    # Sous-case (1, 1) : centre exact de la case parente (0, 0) -> (320, 180)
    assert grid.get_subcell_center(0, 0, 1, 1, w, h) == (320, 180)

    # Sous-case (2, 2) : sous-coin bas-droite de la case (0, 0) -> ((0 + 2.5/3) * 640, (0 + 2.5/3) * 360) = (533, 300)
    assert grid.get_subcell_center(0, 0, 2, 2, w, h) == (533, 300)

    # Case parente (1, 1) [centre de l'écran : 640..1280 en X, 360..720 en Y]
    # Sous-case (1, 1) : centre exact de l'écran -> (960, 540)
    assert grid.get_subcell_center(1, 1, 1, 1, w, h) == (960, 540)


def test_subgrid_key_detection_and_toggle():
    """Vérifie la détection de la touche toggle ² et le changement d'état."""
    from src.alfred.core.state import StateManager

    state = StateManager(initial_mode="grid")
    cfg = GridConfig.from_dict({
        "grid": {
            "subgrid_enabled": True,
            "subgrid_toggle_key": "²",
        }
    })
    grid = GridManager(config=cfg, state_manager=state)

    assert grid.is_subgrid_toggle_key("²") is True
    assert grid.is_subgrid_toggle_key("a") is False
    assert grid.is_subgrid_active is False

    # Activer la sous-grille
    is_active = grid.toggle_subgrid()
    assert is_active is True
    assert grid.is_subgrid_active is True
    assert state.current_mode == "subgrid"

    # Désactiver la sous-grille
    is_active = grid.toggle_subgrid()
    assert is_active is False
    assert grid.is_subgrid_active is False
    assert state.current_mode == "grid"


def test_subgrid_navigation_cycle():
    """Simule le cycle complet : saut grille normal (&) -> toggle subgrid (²) -> saut subgrid (&) -> retour (²)."""
    from unittest.mock import patch
    from src.alfred.core.state import StateManager

    state = StateManager(initial_mode="grid")
    cfg = GridConfig.from_dict({
        "grid": {
            "columns": 3,
            "rows": 3,
            "subgrid_columns": 3,
            "subgrid_rows": 3,
            "subgrid_enabled": True,
            "subgrid_toggle_key": "²",
        },
        "cells": {
            "&": [0, 0],
            "(": [1, 1],
            "ç": [2, 2],
        }
    })
    grid = GridManager(config=cfg, state_manager=state)

    with patch("src.alfred.core.grid.mouse") as mock_mouse:
        mock_mouse.get_screen_size.return_value = (1920, 1080)
        mock_mouse.get_position.return_value = (320, 180)

        # 1. En grille normale, saut vers la case haut-gauche avec '&'
        pos = grid.jump_by_key("&")
        assert pos == (320, 180)
        assert grid.subgrid_origin_cell == (0, 0)
        assert state.current_mode == "grid"

        # 2. Toggle sous-grille avec '²'
        assert grid.is_subgrid_toggle_key("²") is True
        grid.toggle_subgrid()
        assert grid.is_subgrid_active is True
        assert state.current_mode == "subgrid"
        assert grid.subgrid_origin_cell == (0, 0)

        # 3. Saut dans la sous-grille avec la même touche '&' (sous-case 0, 0 de la case 0, 0)
        sub_pos = grid.jump_subcell_by_key("&")
        assert sub_pos == (106, 60)

        # 4. Saut au centre de cette sous-grille avec '('
        sub_center = grid.jump_subcell_by_key("(")
        assert sub_center == (320, 180)

        # 5. Toggle retour avec '²'
        grid.toggle_subgrid()
        assert grid.is_subgrid_active is False
        assert state.current_mode == "grid"

        # 6. Saut grille normale à nouveau avec '&'
        norm_pos = grid.jump_by_key("&")
        assert norm_pos == (320, 180)



