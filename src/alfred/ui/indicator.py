"""Voyant d'écran discret (Overlay) indiquant le mode actif d'Alfred en bas à droite de l'écran."""

from __future__ import annotations
import tkinter as tk
import logging
import sys
from typing import Any

logger = logging.getLogger(__name__)

# Couleurs par mode pour le voyant
MODE_COLORS: dict[str, dict[str, str]] = {
    "normal": {
        "main": "#3B82F6",       # Bleu vif
        "glow": "#1D4ED8",       # Halo / bordure bleue sombre
        "highlight": "#93C5FD",  # Reflet LED
    },
    "special": {
        "main": "#EF4444",       # Rouge vif
        "glow": "#B91C1C",       # Bordure rouge sombre
        "highlight": "#FCA5A5",  # Reflet LED
    },
    "grid": {
        "main": "#10B981",       # Émeraude / Vert
        "glow": "#047857",       # Bordure verte
        "highlight": "#6EE7B7",  # Reflet LED
    },
    "subgrid": {
        "main": "#06B6D4",       # Cyan
        "glow": "#0E7490",       # Bordure cyan
        "highlight": "#67E8F9",  # Reflet LED
    },
}

DEFAULT_MODE_COLOR = {
    "main": "#9CA3AF",
    "glow": "#4B5563",
    "highlight": "#E5E7EB",
}

# Clé de couleur de transparence pour Windows
TRANSPARENT_COLOR_KEY = "#010101"


class ScreenIndicator:
    """Fenêtre overlay sans bordure affichant un voyant LED discret en bas à droite de l'écran."""

    def __init__(
        self,
        master: tk.Misc,
        initial_mode: str = "normal",
        enabled: bool = True,
        size: int = 18,
        margin_x: int = 20,
        margin_y: int = 18,
    ) -> None:
        self.master = master
        self.current_mode = initial_mode
        self.enabled = enabled
        self.size = size
        self.margin_x = margin_x
        self.margin_y = margin_y
        self._window: tk.Toplevel | None = None
        self._canvas: tk.Canvas | None = None

        if self.enabled:
            self._create_window()

    def _get_work_area(self) -> tuple[int, int]:
        """Récupère les coordonnées du coin inférieur droit de la zone de travail de l'écran (hors barre des tâches)."""
        if sys.platform == "win32":
            try:
                import ctypes
                from ctypes import wintypes

                user32 = ctypes.windll.user32
                SPI_GETWORKAREA = 0x0030

                class RECT(ctypes.Structure):
                    _fields_ = [
                        ("left", wintypes.LONG),
                        ("top", wintypes.LONG),
                        ("right", wintypes.LONG),
                        ("bottom", wintypes.LONG),
                    ]

                rect = RECT()
                if user32.SystemParametersInfoW(SPI_GETWORKAREA, 0, ctypes.byref(rect), 0):
                    return (int(rect.right), int(rect.bottom))
            except Exception as e:
                logger.debug("Erreur lors de la récupération de la zone de travail Windows : %s", e)

        # Fallback via Tkinter
        screen_w = self.master.winfo_screenwidth()
        screen_h = self.master.winfo_screenheight()
        # Marge estimée pour la barre des tâches standard Windows (48px)
        return (screen_w, screen_h - 48)

    def _create_window(self) -> None:
        """Crée la fenêtre Toplevel sans bordure et transparente."""
        try:
            self._window = tk.Toplevel(self.master)
            self._window.overrideredirect(True)
            self._window.attributes("-topmost", True)

            # Transparence sous Windows
            if sys.platform == "win32":
                try:
                    self._window.attributes("-transparentcolor", TRANSPARENT_COLOR_KEY)
                except Exception:
                    pass

            self._window.configure(bg=TRANSPARENT_COLOR_KEY)

            # Calcul du positionnement
            right, bottom = self._get_work_area()
            pos_x = right - self.size - self.margin_x
            pos_y = bottom - self.size - self.margin_y

            self._window.geometry(f"{self.size}x{self.size}+{pos_x}+{pos_y}")

            # Création du canvas
            self._canvas = tk.Canvas(
                self._window,
                width=self.size,
                height=self.size,
                bg=TRANSPARENT_COLOR_KEY,
                highlightthickness=0,
                bd=0,
            )
            self._canvas.pack(fill="both", expand=True)

            # Dessin de la pastille LED
            self._draw_indicator()

            # Rendre la fenêtre traversable par les clics de souris sous Windows (Click-Through)
            self._apply_click_through()

        except Exception as err:
            logger.error("Impossible de créer le voyant d'écran : %s", err)

    def _apply_click_through(self) -> None:
        """Configure la fenêtre sous Windows pour que les clics traversent sans voler le focus."""
        if sys.platform != "win32" or not self._window:
            return

        try:
            import ctypes
            user32 = ctypes.windll.user32

            # Obtenir le handle de fenêtre racine
            hwnd = self._window.winfo_id()
            root_hwnd = user32.GetAncestor(hwnd, 2)  # GA_ROOT = 2
            target_hwnd = root_hwnd if root_hwnd else hwnd

            GWL_EXSTYLE = -20
            WS_EX_TRANSPARENT = 0x00000020
            WS_EX_LAYERED = 0x00080000
            WS_EX_TOOLWINDOW = 0x00000080
            WS_EX_NOACTIVATE = 0x08000000

            cur_style = user32.GetWindowLongW(target_hwnd, GWL_EXSTYLE)
            new_style = cur_style | WS_EX_TRANSPARENT | WS_EX_LAYERED | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE
            user32.SetWindowLongW(target_hwnd, GWL_EXSTYLE, new_style)
        except Exception as e:
            logger.debug("Impossible d'appliquer le click-through Windows sur le voyant : %s", e)

    def _draw_indicator(self) -> None:
        """Dessine ou redessine la pastille LED sur le canvas."""
        if not self._canvas:
            return

        self._canvas.delete("all")

        colors = MODE_COLORS.get(self.current_mode.lower(), DEFAULT_MODE_COLOR)
        pad = 2
        s = self.size - pad

        # 1. Anneau extérieur sombre pour un contraste optimal quel que soit le fond d'écran
        self._canvas.create_oval(
            pad - 1, pad - 1, s + 1, s + 1,
            fill="#111827",
            outline="#1F2937",
            width=1,
        )

        # 2. Cercle principal lumineux
        self._canvas.create_oval(
            pad, pad, s, s,
            fill=colors["main"],
            outline=colors["glow"],
            width=1,
        )

        # 3. Petit reflet brillant (effet diode / voyant allumé)
        reflet_x1 = pad + 3
        reflet_y1 = pad + 2
        reflet_x2 = pad + 6
        reflet_y2 = pad + 5
        self._canvas.create_oval(
            reflet_x1, reflet_y1, reflet_x2, reflet_y2,
            fill=colors["highlight"],
            outline="",
        )

    def update_mode(self, mode: str) -> None:
        """Met à jour le mode affiché par le voyant."""
        self.current_mode = mode
        if self._window and self._canvas and self.enabled:
            self._draw_indicator()

    def set_enabled(self, enabled: bool) -> None:
        """Active ou désactive la visibilité du voyant."""
        self.enabled = enabled
        if self.enabled:
            if not self._window:
                self._create_window()
            else:
                self._window.deiconify()
                self._window.attributes("-topmost", True)
                self._draw_indicator()
        else:
            if self._window:
                self._window.withdraw()

    def destroy(self) -> None:
        """Détruit proprement la fenêtre du voyant."""
        if self._window:
            try:
                self._window.destroy()
            except Exception:
                pass
            self._window = None
            self._canvas = None
