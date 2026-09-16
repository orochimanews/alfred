"""Module d'interaction avec la souris et le curseur Windows via ctypes user32."""

from __future__ import annotations
import ctypes
from ctypes import wintypes
import time
import logging

logger = logging.getLogger(__name__)

# Constantes de l'API Windows user32
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP = 0x0040
MOUSEEVENTF_WHEEL = 0x0800
WHEEL_DELTA = 120

SPI_GETMOUSESPEED = 0x0070
SPI_SETMOUSESPEED = 0x0071
SPIF_SENDCHANGE = 0x0002

# Touches virtuelles pour les commandes zoom
VK_CONTROL = 0x11
VK_ADD = 0x6B
VK_SUBTRACT = 0x6D
VK_NUMPAD0 = 0x60


class POINT(ctypes.Structure):
    _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]


class MouseController:
    """Contrôleur bas-niveau de la souris sous Windows."""

    def __init__(self) -> None:
        self._user32 = ctypes.windll.user32
        self._initial_speed: int = self.get_speed()

    def get_screen_size(self) -> tuple[int, int]:
        """Retourne la résolution de l'écran principal (largeur, hauteur)."""
        width = self._user32.GetSystemMetrics(0)
        height = self._user32.GetSystemMetrics(1)
        return (width, height)

    def get_position(self) -> tuple[int, int]:
        """Retourne les coordonnées actuelles du curseur (x, y)."""
        pt = POINT()
        self._user32.GetCursorPos(ctypes.byref(pt))
        return (pt.x, pt.y)

    def set_position(self, x: int, y: int) -> None:
        """Déplace instantanément le curseur à la position absolue (x, y)."""
        self._user32.SetCursorPos(int(x), int(y))

    def move_relative(self, dx: int, dy: int) -> None:
        """Déplace le curseur de manière relative (+dx, +dy)."""
        cur_x, cur_y = self.get_position()
        self.set_position(cur_x + dx, cur_y + dy)

    def click(self, button: str = "left", clicks: int = 1) -> None:
        """Simule un clic ou multi-clic avec le bouton spécifié ('left', 'right', 'middle')."""
        btn = button.lower()
        if btn == "left":
            down_flag = MOUSEEVENTF_LEFTDOWN
            up_flag = MOUSEEVENTF_LEFTUP
        elif btn == "right":
            down_flag = MOUSEEVENTF_RIGHTDOWN
            up_flag = MOUSEEVENTF_RIGHTUP
        elif btn == "middle":
            down_flag = MOUSEEVENTF_MIDDLEDOWN
            up_flag = MOUSEEVENTF_MIDDLEUP
        else:
            down_flag = MOUSEEVENTF_LEFTDOWN
            up_flag = MOUSEEVENTF_LEFTUP

        for i in range(max(1, clicks)):
            self._user32.mouse_event(down_flag, 0, 0, 0, 0)
            time.sleep(0.01)
            self._user32.mouse_event(up_flag, 0, 0, 0, 0)
            if i < clicks - 1:
                time.sleep(0.05)

    def mouse_down(self, button: str = "left") -> None:
        """Enfonce et maintient le bouton spécifié ('left', 'right', 'middle')."""
        btn = button.lower()
        if btn == "right":
            down_flag = MOUSEEVENTF_RIGHTDOWN
        elif btn == "middle":
            down_flag = MOUSEEVENTF_MIDDLEDOWN
        else:
            down_flag = MOUSEEVENTF_LEFTDOWN
        self._user32.mouse_event(down_flag, 0, 0, 0, 0)

    def mouse_up(self, button: str = "left") -> None:
        """Relâche le bouton spécifié ('left', 'right', 'middle')."""
        btn = button.lower()
        if btn == "right":
            up_flag = MOUSEEVENTF_RIGHTUP
        elif btn == "middle":
            up_flag = MOUSEEVENTF_MIDDLEUP
        else:
            up_flag = MOUSEEVENTF_LEFTUP
        self._user32.mouse_event(up_flag, 0, 0, 0, 0)

    def scroll(self, clicks: int = 1) -> None:
        """Simule un défilement de molette (positif = vers le haut, négatif = vers le bas)."""
        dw_data = int(clicks * WHEEL_DELTA)
        self._user32.mouse_event(MOUSEEVENTF_WHEEL, 0, 0, dw_data, 0)

    def zoom(self, direction: str = "in", steps: int = 1) -> None:
        """Simule un zoom (in / out / reset) via Ctrl + Pavé Numérique universel."""
        d = direction.lower().strip()
        if d in ("in", "up", "+", "plus", "avant"):
            vk = VK_ADD
        elif d in ("out", "down", "-", "minus", "arrière", "arriere"):
            vk = VK_SUBTRACT
        elif d in ("reset", "0"):
            vk = VK_NUMPAD0
        else:
            vk = VK_ADD

        self._user32.keybd_event(VK_CONTROL, 0, 0, 0)
        try:
            for _ in range(max(1, steps)):
                self._user32.keybd_event(vk, 0, 0, 0)
                time.sleep(0.01)
                self._user32.keybd_event(vk, 0, 2, 0)
                time.sleep(0.02)
        finally:
            self._user32.keybd_event(VK_CONTROL, 0, 2, 0)

    def get_speed(self) -> int:
        """Récupère la vitesse actuelle du curseur Windows (entre 1 et 20)."""
        speed = wintypes.UINT()
        res = self._user32.SystemParametersInfoW(
            SPI_GETMOUSESPEED,
            0,
            ctypes.byref(speed),
            0
        )
        if res:
            return int(speed.value)
        return 10

    def set_speed(self, speed: int) -> bool:
        """Modifie la vitesse du curseur Windows (entre 1 et 20)."""
        clamped_speed = max(1, min(20, int(speed)))
        res = self._user32.SystemParametersInfoW(
            SPI_SETMOUSESPEED,
            0,
            ctypes.cast(clamped_speed, ctypes.c_void_p),
            SPIF_SENDCHANGE
        )
        return bool(res)

    def restore_initial_speed(self) -> None:
        """Restaure la vitesse initiale de la souris."""
        if self._initial_speed:
            self.set_speed(self._initial_speed)


# Instance globale réutilisable
mouse = MouseController()
