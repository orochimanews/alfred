"""Gestion de l'icône dans la zone de notification Windows (System Tray)."""

from __future__ import annotations
import logging
import threading
from typing import Callable, Optional
from PIL import Image, ImageDraw
import pystray

from src.alfred.core.assets import get_icon_png_path

logger = logging.getLogger(__name__)


def create_tray_icon_image(mode: str = "normal", size: tuple[int, int] = (64, 64)) -> Image.Image:
    """Génère une icône pour la zone de notification avec le majordome Alfred et badge de mode.

    La couleur du badge d'état s'adapte au mode (doré en mode normal, émeraude en mode spécial, etc.).
    """
    w, h = size
    mode_lower = mode.lower()
    if mode_lower == "special":
        badge_color = (16, 185, 129, 255)  # Vert émeraude
    elif mode_lower == "grid":
        badge_color = (139, 92, 246, 255)  # Violet
    else:
        badge_color = (250, 204, 21, 255)   # Doré / Jaune vif

    # 1. Tenter de charger l'icône du majordome Alfred
    icon_path = get_icon_png_path()
    if icon_path.exists():
        try:
            base_image = Image.new("RGBA", size, (0, 0, 0, 0))
            butler_img = Image.open(icon_path).convert("RGBA")

            # Réduire légèrement pour laisser la place au badge de statut
            padding = max(2, int(min(w, h) * 0.08))
            avatar_w = w - (padding * 2)
            avatar_h = h - (padding * 2)
            avatar_resized = butler_img.resize((avatar_w, avatar_h), Image.Resampling.LANCZOS)
            base_image.paste(avatar_resized, (padding, padding), avatar_resized)

            # Dessiner le badge d'état circulaire dans le coin inférieur droit
            draw = ImageDraw.Draw(base_image)
            badge_radius = max(5, int(min(w, h) * 0.16))
            cx = w - badge_radius - 2
            cy = h - badge_radius - 2
            # Bordure foncée de contraste
            draw.ellipse(
                [cx - badge_radius - 1, cy - badge_radius - 1, cx + badge_radius + 1, cy + badge_radius + 1],
                fill=(15, 23, 42, 255),
            )
            # Pastille de mode
            draw.ellipse(
                [cx - badge_radius, cy - badge_radius, cx + badge_radius, cy + badge_radius],
                fill=badge_color,
            )
            return base_image
        except Exception as e:
            logger.debug("Échec du chargement de l'avatar Alfred pour le tray, repli sur le logo : %s", e)

    # 2. Repli élégant : éclair stylisé sur fond arrondi
    image = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle([2, 2, w - 3, h - 3], radius=14, fill=(15, 23, 42, 255))

    bolt_polygon = [
        (int(w * 0.58), int(h * 0.10)),
        (int(w * 0.28), int(h * 0.53)),
        (int(w * 0.50), int(h * 0.53)),
        (int(w * 0.44), int(h * 0.90)),
        (int(w * 0.74), int(h * 0.44)),
        (int(w * 0.52), int(h * 0.44)),
    ]
    draw.polygon(bolt_polygon, fill=badge_color)
    return image


class ToolTip:
    """Infobulle légère au survol pour widgets CustomTkinter / Tkinter."""

    def __init__(self, widget: any, text: str, delay_ms: int = 400) -> None:
        self.widget = widget
        self.text = text
        self.delay_ms = delay_ms
        self.tip_window = None
        self._after_id = None

        self.widget.bind("<Enter>", self._on_enter, add="+")
        self.widget.bind("<Leave>", self._on_leave, add="+")
        self.widget.bind("<ButtonPress>", self._on_leave, add="+")

    def _on_enter(self, _event=None) -> None:
        self._cancel_schedule()
        self._after_id = self.widget.after(self.delay_ms, self._show_tip)

    def _on_leave(self, _event=None) -> None:
        self._cancel_schedule()
        self._hide_tip()

    def _cancel_schedule(self) -> None:
        if self._after_id:
            try:
                self.widget.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None

    def _show_tip(self) -> None:
        if self.tip_window or not self.text:
            return
        import tkinter as tk
        try:
            x = self.widget.winfo_rootx() + 10
            y = self.widget.winfo_rooty() + self.widget.winfo_height() + 6

            self.tip_window = tw = tk.Toplevel(self.widget)
            tw.wm_overrideredirect(True)
            tw.wm_geometry(f"+{x}+{y}")
            tw.attributes("-topmost", True)

            label = tk.Label(
                tw,
                text=self.text,
                justify=tk.LEFT,
                background="#1e293b",
                foreground="#f8fafc",
                relief=tk.SOLID,
                borderwidth=1,
                font=("Segoe UI", 9),
                padx=6,
                pady=3,
            )
            label.pack(ipadx=1)
        except Exception:
            pass

    def _hide_tip(self) -> None:
        if self.tip_window:
            try:
                self.tip_window.destroy()
            except Exception:
                pass
            self.tip_window = None


class TrayIconService:
    """Service de gestion de l'icône dans la zone de notification (System Tray)."""

    def __init__(
        self,
        on_restore: Callable[[], None],
        on_quit: Callable[[], None],
        on_toggle_mode: Optional[Callable[[], None]] = None,
        on_toggle_hook: Optional[Callable[[], None]] = None,
        initial_mode: str = "normal",
        is_hook_enabled: bool = True,
    ) -> None:
        self.on_restore = on_restore
        self.on_quit = on_quit
        self.on_toggle_mode = on_toggle_mode
        self.on_toggle_hook = on_toggle_hook
        self.current_mode = initial_mode
        self.is_hook_enabled = is_hook_enabled

        self._icon: Optional[pystray.Icon] = None
        self._lock = threading.Lock()
        self._is_running = False

    def start(self) -> None:
        """Démarre l'icône dans la zone de notification en arrière-plan."""
        with self._lock:
            if self._is_running:
                return
            try:
                image = create_tray_icon_image(self.current_mode)
                menu = self._build_menu()
                self._icon = pystray.Icon(
                    name="Alfred",
                    icon=image,
                    title="Alfred - Raccourcis & Grille",
                    menu=menu,
                )
                self._icon.run_detached()
                self._is_running = True
                logger.info("Service Tray démarré avec succès.")
            except Exception as e:
                logger.error("Impossible de démarrer le service de tray : %s", e)

    def stop(self) -> None:
        """Arrête proprement l'icône de notification."""
        with self._lock:
            if not self._is_running or not self._icon:
                return
            try:
                self._icon.stop()
            except Exception as e:
                logger.warning("Erreur lors de l'arrêt du tray icon : %s", e)
            finally:
                self._icon = None
                self._is_running = False
                logger.info("Service Tray arrêté.")

    def update_mode(self, mode: str) -> None:
        """Met à jour le mode actuel et rafraîchit l'icône et le menu."""
        self.current_mode = mode
        if self._icon and self._is_running:
            try:
                self._icon.icon = create_tray_icon_image(mode)
                self._icon.menu = self._build_menu()
            except Exception as e:
                logger.debug("Erreur lors de la mise à jour de l'icône tray : %s", e)

    def update_hook_state(self, is_enabled: bool) -> None:
        """Met à jour l'état du hook et rafraîchit le menu."""
        self.is_hook_enabled = is_enabled
        if self._icon and self._is_running:
            try:
                self._icon.menu = self._build_menu()
            except Exception as e:
                logger.debug("Erreur lors de la mise à jour du menu tray : %s", e)

    def notify(self, title: str, message: str) -> None:
        """Affiche une notification système via l'icône de notification."""
        if self._icon and self._is_running:
            try:
                self._icon.notify(message, title)
            except Exception as e:
                logger.debug("Erreur lors de l'envoi de notification tray : %s", e)

    def _build_menu(self) -> pystray.Menu:
        """Construit le menu contextuel du tray."""
        mode_label = f"Mode : {self.current_mode.upper()}"
        hook_label = "Hook : Actif" if self.is_hook_enabled else "Hook : En Pause"

        items = [
            pystray.MenuItem("⚡ Afficher Alfred", self._handle_restore, default=True),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(mode_label, self._handle_toggle_mode),
            pystray.MenuItem(hook_label, self._handle_toggle_hook),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("❌ Quitter", self._handle_quit),
        ]
        return pystray.Menu(*items)

    def _handle_restore(self, _icon=None, _item=None) -> None:
        if self.on_restore:
            self.on_restore()

    def _handle_toggle_mode(self, _icon=None, _item=None) -> None:
        if self.on_toggle_mode:
            self.on_toggle_mode()

    def _handle_toggle_hook(self, _icon=None, _item=None) -> None:
        if self.on_toggle_hook:
            self.on_toggle_hook()

    def _handle_quit(self, _icon=None, _item=None) -> None:
        if self.on_quit:
            self.on_quit()
