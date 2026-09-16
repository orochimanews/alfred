"""Tests unitaires pour les modèles de données."""

from src.alfred.core.models import Command, Action, GridConfig, AppConfig


def test_command_from_dict():
    data = {"type": "hotkey", "keys": ["ctrl", "t"]}
    cmd = Command.from_dict(data)
    assert cmd.type == "hotkey"
    assert cmd.params == {"keys": ["ctrl", "t"]}


def test_action_from_dict_standard():
    data = {
        "name": "Test Action",
        "description": "Une description",
        "modes": ["special", "custom"],
        "trigger": "A",
        "commands": [
            {"type": "hotkey", "keys": ["ctrl", "a"]},
            {"type": "sleep", "duration": 0.2},
        ]
    }
    action = Action.from_dict(data)
    assert action.name == "Test Action"
    assert action.trigger == "a"  # Doit être mis en minuscule
    assert action.modes == ["special", "custom"]
    assert len(action.commands) == 2
    assert action.commands[0].type == "hotkey"
    assert action.commands[1].type == "sleep"
    assert action.toggle is False


def test_action_from_dict_toggle():
    data = {
        "name": "Toggle Action",
        "modes": ["normal"],
        "trigger": "x",
        "toggle": True,
        "states": {
            "0": {
                "name": "State 1",
                "commands": [{"type": "mode", "target": "special"}],
            },
            "1": {
                "name": "State 2",
                "commands": [{"type": "mode", "target": "normal"}],
            }
        }
    }
    action = Action.from_dict(data)
    assert action.toggle is True
    assert len(action.states) == 2
    assert action.states[0].name == "State 1"
    assert action.states[1].name == "State 2"


def test_grid_config_from_dict():
    data = {
        "grid": {
            "enabled": True,
            "columns": 4,
            "rows": 3,
            "active_modes": ["grid"],
            "exit_mode_after_jump": True,
            "auto_click": True,
        },
        "cells": {
            "a": [0, 0],
            "b": [1, 2],
        }
    }
    grid = GridConfig.from_dict(data)
    assert grid.enabled is True
    assert grid.columns == 4
    assert grid.rows == 3
    assert grid.active_modes == ["grid"]
    assert grid.exit_mode_after_jump is True
    assert grid.auto_click is True
    assert grid.cells["a"] == (0, 0)
    assert grid.cells["b"] == (1, 2)
