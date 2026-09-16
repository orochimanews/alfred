"""Vue Tableau de Bord (Statut en direct et journal d'activité)."""

from __future__ import annotations
import customtkinter as ctk
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.alfred.core.state import StateManager
    from src.alfred.core.config import ConfigManager
    from src.alfred.ui.theme import ThemeManager


class DashboardView(ctk.CTkFrame):
    """Composant affichant le statut actuel du système et les dernières actions."""

    def __init__(
        self,
        master: ctk.CTkBaseClass,
        state_manager: StateManager,
        config_manager: ConfigManager,
        theme_manager: ThemeManager,
        **kwargs
    ) -> None:
        super().__init__(master, **kwargs)
        self.state_manager = state_manager
        self.config_manager = config_manager
        self.theme_manager = theme_manager

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self._build_status_card()
        self._build_logs_card()

    def _build_status_card(self) -> None:
        """Crée la carte de statut principal (mode, hook, actions rapides)."""
        card = ctk.CTkFrame(self, corner_radius=8)
        card.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 5))
        card.grid_columnconfigure(1, weight=1)

        # Indicateur de mode
        lbl_title = ctk.CTkLabel(
            card,
            text="Mode Actif :",
            font=self.theme_manager.get_font(size_offset=1, weight="bold")
        )
        lbl_title.grid(row=0, column=0, padx=12, pady=10, sticky="w")

        self.btn_mode_badge = ctk.CTkButton(
            card,
            text=self.state_manager.current_mode.upper(),
            font=self.theme_manager.get_font(size_offset=2, weight="bold"),
            width=130,
            height=32,
            command=self._on_toggle_mode_clicked,
        )
        self.btn_mode_badge.grid(row=0, column=1, padx=6, pady=10, sticky="w")
        self._update_mode_badge()

        # Raccourci de bascule configuré
        special_key = self.config_manager.app_config.general.special_mode_key
        if not special_key:
            for act in self.config_manager.actions:
                if act.toggle and (
                    any(any(c.type == "mode" for c in s.commands) for s in act.states)
                    or any(c.type == "mode" for c in act.commands)
                ):
                    special_key = act.trigger
                    break
        special_key = special_key or "!"
        lbl_hint = ctk.CTkLabel(
            card,
            text=f"Touche de bascule : [{special_key}]",
            font=self.theme_manager.get_font(size_offset=-1),
            text_color="gray",
        )
        lbl_hint.grid(row=0, column=2, padx=12, pady=10, sticky="e")

        # Boutons de sélection rapide de mode
        btn_box = ctk.CTkFrame(card, fg_color="transparent")
        btn_box.grid(row=1, column=0, columnspan=3, padx=12, pady=(0, 10), sticky="ew")

        ctk.CTkButton(
            btn_box,
            text="Normal",
            width=90,
            height=26,
            font=self.theme_manager.get_font(size_offset=-1),
            command=lambda: self.state_manager.set_mode("normal")
        ).pack(side="left", padx=4)

        ctk.CTkButton(
            btn_box,
            text="Spécial",
            width=90,
            height=26,
            font=self.theme_manager.get_font(size_offset=-1),
            fg_color="#D97706",
            hover_color="#B45309",
            command=lambda: self.state_manager.set_mode("special")
        ).pack(side="left", padx=4)

        ctk.CTkButton(
            btn_box,
            text="Grille",
            width=90,
            height=26,
            font=self.theme_manager.get_font(size_offset=-1),
            fg_color="#059669",
            hover_color="#047857",
            command=lambda: self.state_manager.set_mode("grid")
        ).pack(side="left", padx=4)

    def _build_logs_card(self) -> None:
        """Crée la section de journalisation des actions en direct."""
        container = ctk.CTkFrame(self, corner_radius=8)
        container.grid(row=1, column=0, sticky="nsew", padx=10, pady=(5, 10))
        container.grid_columnconfigure(0, weight=1)
        container.grid_rowconfigure(1, weight=1)

        # En-tête des logs
        header_bar = ctk.CTkFrame(container, fg_color="transparent")
        header_bar.grid(row=0, column=0, sticky="ew", padx=12, pady=(8, 4))
        header_bar.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            header_bar,
            text="Dernières Actions Exécutées",
            font=self.theme_manager.get_font(size_offset=0, weight="bold")
        ).grid(row=0, column=0, sticky="w")

        ctk.CTkButton(
            header_bar,
            text="Effacer",
            width=65,
            height=22,
            font=self.theme_manager.get_font(size_offset=-2),
            fg_color="transparent",
            border_width=1,
            command=self.state_manager.clear_logs
        ).grid(row=0, column=1, sticky="e")

        # Zone de défilement des logs
        self.scroll_logs = ctk.CTkScrollableFrame(container, fg_color="transparent")
        self.scroll_logs.grid(row=1, column=0, sticky="nsew", padx=6, pady=6)
        self.scroll_logs.grid_columnconfigure(0, weight=1)

        self.refresh_logs()

    def _update_mode_badge(self) -> None:
        cur_mode = self.state_manager.current_mode
        bg_color, text_color = self.theme_manager.get_mode_colors(cur_mode)
        self.btn_mode_badge.configure(
            text=cur_mode.upper(),
            fg_color=bg_color,
            text_color=text_color,
        )

    def _on_toggle_mode_clicked(self) -> None:
        gen_cfg = self.config_manager.app_config.general
        self.state_manager.toggle_mode(gen_cfg.special_mode_name)

    def refresh(self) -> None:
        """Met à jour l'affichage lors d'un changement d'état."""
        self._update_mode_badge()
        self.refresh_logs()

    def refresh_logs(self) -> None:
        """Recharge la liste visuelle des logs."""
        for child in self.scroll_logs.winfo_children():
            child.destroy()

        logs = self.state_manager.logs
        if not logs:
            lbl_empty = ctk.CTkLabel(
                self.scroll_logs,
                text="Aucune action exécutée pour le moment.\nAppuyez sur '!' pour activer le mode spécial puis sur une touche (t, o, space...).",
                font=self.theme_manager.get_font(size_offset=-1),
                text_color="gray"
            )
            lbl_empty.pack(pady=20)
            return

        for entry in logs[:25]:
            row_frame = ctk.CTkFrame(self.scroll_logs, height=28, fg_color=("gray85", "gray20"), corner_radius=4)
            row_frame.pack(fill="x", pady=2, padx=2)

            time_lbl = ctk.CTkLabel(
                row_frame,
                text=entry.formatted_time(),
                font=self.theme_manager.get_font(size_offset=-2),
                text_color="gray",
                width=65,
                anchor="w"
            )
            time_lbl.pack(side="left", padx=(8, 4))

            mode_badge = ctk.CTkLabel(
                row_frame,
                text=f"[{entry.mode}]",
                font=self.theme_manager.get_font(size_offset=-2, weight="bold"),
                width=60,
                anchor="w"
            )
            mode_badge.pack(side="left", padx=4)

            key_badge = ctk.CTkLabel(
                row_frame,
                text=f"Touche '{entry.trigger_key}'",
                font=self.theme_manager.get_font(size_offset=-1, weight="bold"),
                width=80,
                anchor="w"
            )
            key_badge.pack(side="left", padx=4)

            name_lbl = ctk.CTkLabel(
                row_frame,
                text=entry.action_name,
                font=self.theme_manager.get_font(size_offset=-1),
                anchor="w"
            )
            name_lbl.pack(side="left", padx=6, fill="x", expand=True)
