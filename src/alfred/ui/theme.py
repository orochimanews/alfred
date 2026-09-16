"""Gestionnaire de thème, couleurs et polices pour l'interface CustomTkinter."""

from __future__ import annotations
import customtkinter as ctk
from src.alfred.core.models import UIConfig


class ThemeManager:
    """Fournit les configurations de styles, polices dynamiques et palettes de couleurs."""

    def __init__(self, ui_config: UIConfig) -> None:
        self.config = ui_config
        self.apply_theme()

    def apply_theme(self) -> None:
        """Applique les préférences de thème à CustomTkinter."""
        ctk.set_appearance_mode(self.config.theme)
        try:
            ctk.set_default_color_theme(self.config.color_theme)
        except Exception:
            ctk.set_default_color_theme("blue")

    def get_font(self, size_offset: int = 0, weight: str = "normal") -> ctk.CTkFont:
        """Retourne un objet CTkFont dimensionné selon la taille de police configurée."""
        base_size = max(9, min(24, self.config.font_size))
        return ctk.CTkFont(family="Segoe UI", size=base_size + size_offset, weight=weight)

    @staticmethod
    def get_mode_colors(mode: str) -> tuple[str, str]:
        """Retourne un tuple (couleur_fond, couleur_texte) adapté au mode."""
        m = mode.lower().strip()
        match m:
            case "special":
                return ("#D97706", "#FFFFFF")  # Ambre / Orange vif
            case "grid":
                return ("#059669", "#FFFFFF")  # Vert émeraude
            case "normal":
                return ("#2563EB", "#FFFFFF")  # Bleu vif
            case _:
                return ("#4B5563", "#FFFFFF")  # Gris neutre
