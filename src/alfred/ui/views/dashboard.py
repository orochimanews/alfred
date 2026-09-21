"""Vue Tableau de Bord (Statut en direct et journal d'activité)."""

from __future__ import annotations
import customtkinter as ctk
from typing import TYPE_CHECKING, Callable

from src.alfred.ui.tray import ToolTip

if TYPE_CHECKING:
    from src.alfred.core.state import StateManager
    from src.alfred.core.config import ConfigManager
    from src.alfred.ui.theme import ThemeManager
    from src.alfred.core.move import MoveManager


class DashboardView(ctk.CTkFrame):
    """Composant affichant le statut actuel du système et les dernières actions."""

    def __init__(
        self,
        master: ctk.CTkBaseClass,
        state_manager: StateManager,
        config_manager: ConfigManager,
        theme_manager: ThemeManager,
        on_minimize: Callable[[], None] | None = None,
        move_manager: MoveManager | None = None,
        **kwargs
    ) -> None:
        super().__init__(master, **kwargs)
        self.state_manager = state_manager
        self.config_manager = config_manager
        self.theme_manager = theme_manager
        self.on_minimize = on_minimize
        self.move_manager = move_manager

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self._build_status_card()
        self._build_logs_card()

    def _build_status_card(self) -> None:
        """Crée la carte de statut principal (mode, hook, actions rapides)."""
        card = ctk.CTkFrame(self, corner_radius=8)
        card.grid(row=0, column=0, sticky="ew", padx=10, pady=(8, 4))
        card.grid_columnconfigure(1, weight=1)

        # Indicateur de mode et option démarrage
        lbl_title = ctk.CTkLabel(
            card,
            text="Mode Actif :",
            font=self.theme_manager.get_font(size_offset=1, weight="bold")
        )
        lbl_title.grid(row=0, column=0, padx=12, pady=8, sticky="w")

        mode_box = ctk.CTkFrame(card, fg_color="transparent")
        mode_box.grid(row=0, column=1, padx=6, pady=4, sticky="w")

        self.btn_mode_badge = ctk.CTkButton(
            mode_box,
            text=self.state_manager.current_mode.upper(),
            font=self.theme_manager.get_font(size_offset=2, weight="bold"),
            width=130,
            height=28,
            command=self._on_toggle_mode_clicked,
        )
        self.btn_mode_badge.pack(anchor="w")
        self._update_mode_badge()

        self.chk_start_in_special_mode = ctk.CTkCheckBox(
            mode_box,
            text="Démarrer en mode spécial",
            font=self.theme_manager.get_font(size_offset=-2),
            checkbox_width=16,
            checkbox_height=16,
            command=self._on_toggle_start_in_special_mode,
        )
        if getattr(self.config_manager.app_config.general, "start_in_special_mode", True):
            self.chk_start_in_special_mode.select()
        else:
            self.chk_start_in_special_mode.deselect()
        self.chk_start_in_special_mode.pack(anchor="w", pady=(3, 0))
        ToolTip(self.chk_start_in_special_mode, "Démarrer automatiquement Alfred en mode spécial au lancement")

        # Bloc droit sur la ligne de Mode : Raccourci de bascule et Bouton Minimiser
        right_panel = ctk.CTkFrame(card, fg_color="transparent")
        right_panel.grid(row=0, column=2, padx=12, pady=8, sticky="e")

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
            right_panel,
            text=f"Bascule : [{special_key}]",
            font=self.theme_manager.get_font(size_offset=-1),
            text_color="gray",
        )
        lbl_hint.pack(side="left", padx=(0, 10))

        # Sous-bloc Minimiser & Option "Démarrer minimisé"
        min_box = ctk.CTkFrame(right_panel, fg_color="transparent")
        min_box.pack(side="left")

        # Bouton Minimiser dans la ligne avec Mode à droite
        self.btn_minimize = ctk.CTkButton(
            min_box,
            text="📥 Minimiser",
            width=115,
            height=28,
            font=self.theme_manager.get_font(size_offset=-1, weight="bold"),
            fg_color=("gray75", "gray25"),
            hover_color=("gray65", "gray35"),
            text_color=("gray10", "gray95"),
            border_width=1,
            border_color=("gray60", "gray38"),
            command=self._on_minimize_clicked,
        )
        self.btn_minimize.pack(anchor="e")
        ToolTip(self.btn_minimize, "Réduire dans la zone de notification (Systray)")

        self.chk_start_minimized = ctk.CTkCheckBox(
            min_box,
            text="Démarrer minimisé",
            font=self.theme_manager.get_font(size_offset=-2),
            checkbox_width=16,
            checkbox_height=16,
            command=self._on_toggle_start_minimized,
        )
        if getattr(self.config_manager.app_config.ui, "start_minimized", True):
            self.chk_start_minimized.select()
        else:
            self.chk_start_minimized.deselect()
        self.chk_start_minimized.pack(anchor="e", pady=(3, 0))
        ToolTip(self.chk_start_minimized, "Lancer Alfred directement réduit dans le systray au démarrage")

        # Boutons de sélection rapide de mode
        btn_box = ctk.CTkFrame(card, fg_color="transparent")
        btn_box.grid(row=1, column=0, columnspan=3, padx=12, pady=(0, 8), sticky="ew")

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

        # Raccourcis et statut du Déplacement Dynamique (Move)
        self.btn_boost_badge: ctk.CTkButton | None = None
        self.btn_move_grid_badge: ctk.CTkButton | None = None
        move_cfg = self.config_manager.move_config
        if move_cfg.enabled:
            lbl_move = ctk.CTkLabel(
                btn_box,
                text=f"Move [{move_cfg.key_up},{move_cfg.key_left},{move_cfg.key_down},{move_cfg.key_right}]",
                font=self.theme_manager.get_font(size_offset=-2),
                text_color="gray",
            )
            lbl_move.pack(side="left", padx=(10, 4))

            is_boosted = self.move_manager.is_boosted if self.move_manager else False
            self.btn_boost_badge = ctk.CTkButton(
                btn_box,
                text=f"🚀 Boost x{move_cfg.boost_multiplier:.1f} [{move_cfg.boost_toggle_key}]" if is_boosted else f"⚡ Boost [{move_cfg.boost_toggle_key}]",
                width=100,
                height=26,
                font=self.theme_manager.get_font(size_offset=-2, weight="bold"),
                fg_color=("#8B5CF6", "#7C3AED") if is_boosted else ("gray70", "gray30"),
                hover_color=("#7C3AED", "#6D28D9") if is_boosted else ("gray60", "gray40"),
                command=self._on_boost_badge_clicked,
            )
            self.btn_boost_badge.pack(side="left", padx=4)
            ToolTip(self.btn_boost_badge, "Bascule la vitesse rapide (Boost) pour les déplacements curseur au clavier")

            if move_cfg.grid_enabled:
                is_grid_active = self.move_manager.is_grid_active if self.move_manager else False
                self.btn_move_grid_badge = ctk.CTkButton(
                    btn_box,
                    text=f"⊞ Grille ACTIVE [{move_cfg.grid_toggle_key}]" if is_grid_active else f"⊞ Grille [{move_cfg.grid_toggle_key}]",
                    width=110,
                    height=26,
                    font=self.theme_manager.get_font(size_offset=-2, weight="bold"),
                    fg_color=("#10B981", "#059669") if is_grid_active else ("gray70", "gray30"),
                    hover_color=("#059669", "#047857") if is_grid_active else ("gray60", "gray40"),
                    command=self._on_move_grid_badge_clicked,
                )
                self.btn_move_grid_badge.pack(side="left", padx=4)
                ToolTip(self.btn_move_grid_badge, "Bascule le pavé numérique entre déplacement curseur et grille 3x3")

    def _on_boost_badge_clicked(self) -> None:
        """Bascule le mode boost via clic UI."""
        if self.move_manager:
            self.move_manager.toggle_boost()
            self._update_boost_badge()

    def _on_move_grid_badge_clicked(self) -> None:
        """Bascule le mode grille pavé numérique via clic UI."""
        if self.move_manager:
            self.move_manager.toggle_grid()
            self._update_move_grid_badge()

    def _build_logs_card(self) -> None:
        """Crée la section de journalisation des actions en direct (format compact)."""
        container = ctk.CTkFrame(self, corner_radius=8)
        container.grid(row=1, column=0, sticky="nsew", padx=10, pady=(4, 8))
        container.grid_columnconfigure(0, weight=1)
        container.grid_rowconfigure(1, weight=1)

        # En-tête des logs
        header_bar = ctk.CTkFrame(container, fg_color="transparent")
        header_bar.grid(row=0, column=0, sticky="ew", padx=10, pady=(6, 2))
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
        self.scroll_logs.grid(row=1, column=0, sticky="nsew", padx=6, pady=(2, 6))
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

    def _on_minimize_clicked(self) -> None:
        """Déclenche la minimisation dans la zone de notification."""
        if self.on_minimize:
            self.on_minimize()

    def _on_toggle_start_minimized(self) -> None:
        """Met à jour l'option start_minimized depuis le tableau de bord et sauvegarde dans config.toml."""
        if hasattr(self, "chk_start_minimized"):
            is_checked = bool(self.chk_start_minimized.get())
            self.config_manager.app_config.ui.start_minimized = is_checked
            self.config_manager.save_app_config()

    def _on_toggle_start_in_special_mode(self) -> None:
        """Met à jour l'option start_in_special_mode depuis le tableau de bord et sauvegarde dans config.toml."""
        if hasattr(self, "chk_start_in_special_mode"):
            is_checked = bool(self.chk_start_in_special_mode.get())
            self.config_manager.app_config.general.start_in_special_mode = is_checked
            self.config_manager.app_config.general.default_mode = "special" if is_checked else "normal"
            self.config_manager.save_app_config()

    def _update_boost_badge(self) -> None:
        """Met à jour l'apparence du bouton boost."""
        if not hasattr(self, "btn_boost_badge") or self.btn_boost_badge is None:
            return
        move_cfg = self.config_manager.move_config
        is_boosted = self.move_manager.is_boosted if self.move_manager else False
        self.btn_boost_badge.configure(
            text=f"🚀 Boost x{move_cfg.boost_multiplier:.1f} [{move_cfg.boost_toggle_key}]" if is_boosted else f"⚡ Boost [{move_cfg.boost_toggle_key}]",
            fg_color=("#8B5CF6", "#7C3AED") if is_boosted else ("gray70", "gray30"),
            hover_color=("#7C3AED", "#6D28D9") if is_boosted else ("gray60", "gray40"),
        )

    def _update_move_grid_badge(self) -> None:
        """Met à jour l'apparence du bouton de la grille pavé numérique."""
        if not hasattr(self, "btn_move_grid_badge") or self.btn_move_grid_badge is None:
            return
        move_cfg = self.config_manager.move_config
        is_grid_active = self.move_manager.is_grid_active if self.move_manager else False
        self.btn_move_grid_badge.configure(
            text=f"⊞ Grille ACTIVE [{move_cfg.grid_toggle_key}]" if is_grid_active else f"⊞ Grille [{move_cfg.grid_toggle_key}]",
            fg_color=("#10B981", "#059669") if is_grid_active else ("gray70", "gray30"),
            hover_color=("#059669", "#047857") if is_grid_active else ("gray60", "gray40"),
        )

    def refresh(self) -> None:
        """Met à jour l'affichage lors d'un changement d'état."""
        self._update_mode_badge()
        self._update_boost_badge()
        self._update_move_grid_badge()
        self.refresh_logs()
        if hasattr(self, "chk_start_minimized"):
            if getattr(self.config_manager.app_config.ui, "start_minimized", True):
                self.chk_start_minimized.select()
            else:
                self.chk_start_minimized.deselect()
        if hasattr(self, "chk_start_in_special_mode"):
            if getattr(self.config_manager.app_config.general, "start_in_special_mode", True):
                self.chk_start_in_special_mode.select()
            else:
                self.chk_start_in_special_mode.deselect()

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
            lbl_empty.pack(pady=10)
            return

        for entry in logs[:25]:
            row_frame = ctk.CTkFrame(self.scroll_logs, height=26, fg_color=("gray85", "gray20"), corner_radius=4)
            row_frame.pack(fill="x", pady=1, padx=2)

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
