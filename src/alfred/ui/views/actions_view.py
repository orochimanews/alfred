"""Vue Explorateur des Actions (settings/actions/*.toml)."""

from __future__ import annotations
import customtkinter as ctk
from typing import TYPE_CHECKING
import threading

if TYPE_CHECKING:
    from src.alfred.core.config import ConfigManager
    from src.alfred.core.commands_engine import CommandsEngine
    from src.alfred.ui.theme import ThemeManager


class ActionsView(ctk.CTkFrame):
    """Affiche et filtre toutes les actions configurées dans settings/actions/."""

    def __init__(
        self,
        master: ctk.CTkBaseClass,
        config_manager: ConfigManager,
        commands_engine: CommandsEngine,
        theme_manager: ThemeManager,
        **kwargs
    ) -> None:
        super().__init__(master, **kwargs)
        self.config_manager = config_manager
        self.commands_engine = commands_engine
        self.theme_manager = theme_manager

        self._filter_mode = "all"

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self._build_filter_bar()
        self._build_actions_list()

    def _build_filter_bar(self) -> None:
        """Barre de filtres par mode."""
        bar = ctk.CTkFrame(self, height=36, fg_color="transparent")
        bar.grid(row=0, column=0, sticky="ew", padx=10, pady=(8, 4))

        lbl_filter = ctk.CTkLabel(
            bar,
            text="Filtrer par mode :",
            font=self.theme_manager.get_font(size_offset=-1, weight="bold")
        )
        lbl_filter.pack(side="left", padx=(4, 8))

        modes = ["all", "special", "normal", "grid"]
        self.seg_filter = ctk.CTkSegmentedButton(
            bar,
            values=["Tous", "Spécial", "Normal", "Grille"],
            command=self._on_filter_changed,
            font=self.theme_manager.get_font(size_offset=-1)
        )
        self.seg_filter.set("Tous")
        self.seg_filter.pack(side="left")

        # Compteur
        self.lbl_count = ctk.CTkLabel(
            bar,
            text=f"{len(self.config_manager.actions)} actions chargées",
            font=self.theme_manager.get_font(size_offset=-1),
            text_color="gray"
        )
        self.lbl_count.pack(side="right", padx=6)

    def _build_actions_list(self) -> None:
        """Zone de défilement des cartes d'actions."""
        self.scroll_frame = ctk.CTkScrollableFrame(self)
        self.scroll_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=(4, 10))
        self.scroll_frame.grid_columnconfigure(0, weight=1)

        self.refresh_actions()

    def _on_filter_changed(self, value: str) -> None:
        mapping = {"Tous": "all", "Spécial": "special", "Normal": "normal", "Grille": "grid"}
        self._filter_mode = mapping.get(value, "all")
        self.refresh_actions()

    def refresh_actions(self) -> None:
        """Recharge la liste des actions selon le filtre."""
        for child in self.scroll_frame.winfo_children():
            child.destroy()

        actions = self.config_manager.actions
        filtered = []
        for act in actions:
            if self._filter_mode == "all":
                filtered.append(act)
            else:
                act_modes = [m.lower().strip() for m in act.modes]
                if self._filter_mode in act_modes or "all" in act_modes:
                    filtered.append(act)

        self.lbl_count.configure(text=f"{len(filtered)} / {len(actions)} actions")

        if not filtered:
            lbl_empty = ctk.CTkLabel(
                self.scroll_frame,
                text="Aucune action trouvée pour ce filtre.",
                font=self.theme_manager.get_font(size_offset=-1),
                text_color="gray"
            )
            lbl_empty.pack(pady=30)
            return

        for action in filtered:
            card = ctk.CTkFrame(self.scroll_frame, fg_color=("gray85", "gray20"), corner_radius=6)
            card.pack(fill="x", pady=4, padx=2)
            card.grid_columnconfigure(1, weight=1)

            # Badge Touche
            key_text = f"[{action.trigger.upper()}]" if action.trigger else "[--]"
            btn_key = ctk.CTkButton(
                card,
                text=key_text,
                width=55,
                height=30,
                font=self.theme_manager.get_font(size_offset=0, weight="bold"),
                fg_color=("#3B82F6", "#1D4ED8"),
            )
            btn_key.grid(row=0, column=0, rowspan=2, padx=10, pady=8)

            # Titre & description
            title_text = action.name + (" (Toggle)" if action.toggle else "")
            lbl_title = ctk.CTkLabel(
                card,
                text=title_text,
                font=self.theme_manager.get_font(size_offset=0, weight="bold"),
                anchor="w"
            )
            lbl_title.grid(row=0, column=1, sticky="w", padx=4, pady=(6, 0))

            desc_text = action.description or self._format_commands_summary(action)
            lbl_desc = ctk.CTkLabel(
                card,
                text=desc_text,
                font=self.theme_manager.get_font(size_offset=-2),
                text_color="gray",
                anchor="w"
            )
            lbl_desc.grid(row=1, column=1, sticky="w", padx=4, pady=(0, 6))

            # Modes badges
            modes_str = ", ".join(action.modes)
            lbl_modes = ctk.CTkLabel(
                card,
                text=f"Modes: {modes_str}",
                font=self.theme_manager.get_font(size_offset=-2),
                text_color=("gray40", "gray70"),
            )
            lbl_modes.grid(row=0, column=2, padx=8, sticky="e")

            # Bouton Test manuel
            btn_test = ctk.CTkButton(
                card,
                text="Tester",
                width=65,
                height=24,
                font=self.theme_manager.get_font(size_offset=-2),
                command=lambda a=action: threading.Thread(
                    target=self.commands_engine.execute_action,
                    args=(a, "test_ui"),
                    daemon=True
                ).start()
            )
            btn_test.grid(row=1, column=2, padx=8, pady=(0, 6), sticky="e")

    def _format_commands_summary(self, action) -> str:
        """Formate un résumé lisible des commandes de l'action."""
        if action.toggle:
            return f"Bascule entre {len(action.states)} états alternés"
        parts = []
        for cmd in action.commands:
            parts.append(f"{cmd.type}({list(cmd.params.keys())})")
        return " -> ".join(parts) if parts else "Aucune commande"
