"""Module d'interaction avec la souris et le curseur Windows via ctypes user32."""

from __future__ import annotations
import ctypes
from ctypes import wintypes
import time
import math
import threading
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
VK_OEM_MINUS = 0xBD
VK_NUMPAD0 = 0x60


class POINT(ctypes.Structure):
    _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]


class MouseController:
    """Contrôleur bas-niveau de la souris sous Windows."""

    def __init__(self) -> None:
        self._user32 = ctypes.windll.user32
        self._initial_speed: int = self.get_speed()
        self._nudge_active: bool = False
        self._nudge_thread: threading.Thread | None = None
        self._nudge_stop_event = threading.Event()
        self._nudge_lock = threading.RLock()
        self._nudge_step: int = 120
        self._nudge_threshold: int = 4
        self._nudge_cooldown: float = 0.08

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

    def scroll(self, clicks: float = 1.0) -> None:
        """Simule un défilement de molette (positif = vers le haut, négatif = vers le bas).

        ``clicks`` accepte des décimales pour une granularité plus fine :
        1.0 = un cran complet (120 unités Windows), 0.5 = un demi-cran (60 unités), etc.
        """
        dw_data = int(clicks * WHEEL_DELTA)
        self._user32.mouse_event(MOUSEEVENTF_WHEEL, 0, 0, dw_data, 0)

    def zoom(self, direction: str = "in", steps: int = 1) -> None:
        """Simule un zoom (in / out / reset) via Ctrl + Molette de la souris (universel et fluide)."""
        d = direction.lower().strip()
        if d in ("in", "up", "+", "plus", "avant"):
            delta = WHEEL_DELTA * max(1, steps)
        elif d in ("out", "down", "-", "minus", "arrière", "arriere"):
            delta = -WHEEL_DELTA * max(1, steps)
        elif d in ("reset", "0"):
            self._user32.keybd_event(VK_CONTROL, 0, 0, 0)
            try:
                self._user32.keybd_event(0x30, 0, 0, 0)
                time.sleep(0.01)
                self._user32.keybd_event(0x30, 0, 2, 0)
            finally:
                self._user32.keybd_event(VK_CONTROL, 0, 2, 0)
            return
        else:
            delta = WHEEL_DELTA * max(1, steps)

        self._user32.keybd_event(VK_CONTROL, 0, 0, 0)
        time.sleep(0.01)
        try:
            self._user32.mouse_event(MOUSEEVENTF_WHEEL, 0, 0, int(delta), 0)
            time.sleep(0.01)
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

    @property
    def is_nudge_active(self) -> bool:
        """Indique si le mode Nudge est actuellement activé."""
        with self._nudge_lock:
            return self._nudge_active

    def start_nudge_mode(self, step: int = 120, threshold: int = 4, cooldown: float = 0.08) -> None:
        """Active le mode Nudge (amplifie les mouvements de souris/trackpad par bonds relatifs)."""
        with self._nudge_lock:
            self._nudge_step = max(10, int(step))
            self._nudge_threshold = max(1, int(threshold))
            self._nudge_cooldown = max(0.01, float(cooldown))

            if self._nudge_active:
                return

            self._nudge_active = True
            self._nudge_stop_event.clear()
            self._nudge_thread = threading.Thread(
                target=self._nudge_worker,
                daemon=True,
                name="Alfred-MouseNudge",
            )
            self._nudge_thread.start()
            logger.info(
                "Mode Nudge souris activé (step=%d px, threshold=%d px, cooldown=%.2fs)",
                self._nudge_step,
                self._nudge_threshold,
                self._nudge_cooldown,
            )

    def stop_nudge_mode(self) -> None:
        """Désactive le mode Nudge souris."""
        with self._nudge_lock:
            if not self._nudge_active:
                return
            self._nudge_active = False
            self._nudge_stop_event.set()
            self._nudge_thread = None
            logger.info("Mode Nudge souris désactivé.")

    def toggle_nudge_mode(self, step: int = 120, threshold: int = 4, cooldown: float = 0.08) -> bool:
        """Bascule le mode Nudge souris. Retourne True si activé, False si désactivé."""
        with self._nudge_lock:
            if self._nudge_active:
                self.stop_nudge_mode()
                return False
            else:
                self.start_nudge_mode(step=step, threshold=threshold, cooldown=cooldown)
                return True

    def _nudge_worker(self) -> None:
        """Boucle d'écoute et d'amplification des mouvements physiques de la souris/trackpad."""
        logger.debug("Démarrage du worker Nudge souris.")
        last_x, last_y = self.get_position()
        last_nudge_time = 0.0

        while not self._nudge_stop_event.is_set():
            try:
                time.sleep(0.016)
                if self._nudge_stop_event.is_set():
                    break

                cur_x, cur_y = self.get_position()
                dx = cur_x - last_x
                dy = cur_y - last_y

                now = time.time()
                dist = math.hypot(dx, dy)

                if dist >= self._nudge_threshold:
                    if (now - last_nudge_time) >= self._nudge_cooldown:
                        ux = dx / dist
                        uy = dy / dist
                        nx = int(round(ux * self._nudge_step))
                        ny = int(round(uy * self._nudge_step))

                        sw, sh = self.get_screen_size()
                        target_x = max(0, min(sw - 1, cur_x + nx))
                        target_y = max(0, min(sh - 1, cur_y + ny))

                        self.set_position(target_x, target_y)
                        last_x, last_y = target_x, target_y
                        last_nudge_time = now
                    else:
                        last_x, last_y = cur_x, cur_y
                else:
                    last_x, last_y = cur_x, cur_y
            except Exception as err:
                logger.error("Erreur dans le thread Nudge souris : %s", err)
                time.sleep(0.05)

        logger.debug("Arrêt du worker Nudge souris.")


# Instance globale réutilisable
mouse = MouseController()
