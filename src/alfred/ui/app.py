"""Fenêtre principale de l'application Alfred avec menu supérieur sticky."""

from __future__ import annotations
import customtkinter as ctk
import logging
from typing import TYPE_CHECKING

from src.alfred.ui.theme import ThemeManager
from src.alfred.ui.views.dashboard import DashboardView
from src.alfred.ui.views.actions_view import ActionsView
from src.alfred.ui.views.grid_view import GridView
from src.alfred.ui.views.settings_modal import SettingsModal

if TYPE_CHECKING:
    from src.alfred.core.config import ConfigManager
    from src.alfred.core.state import StateManager
    from src.alfred.core.commands_engine import CommandsEngine
    from src.alfred.core.grid import GridManager
    from src.alfred.core.hook import KeyboardHookService

logger = logging.getLogger(__name__)


def parse_shortcut_to_tk(shortcut: str) -> list[str]:
    """Convertit une chaîne de raccourci (ex: 'ctrl+w') en séquences d'événements Tkinter."""
    s = shortcut.strip()
    if not s:
        return []
    if s.startswith("<") and s.endswith(">"):
        return [s]

    parts = [p.strip().lower() for p in s.split("+") if p.strip()]
    if not parts:
        return []

    mods: list[str] = []
    key = ""
    for p in parts:
        if p in ("ctrl", "control"):
            mods.append("Control")
        elif p in ("alt", "menu"):
            mods.append("Alt")
        elif p in ("shift",):
            mods.append("Shift")
        else:
            key = p

    if not key:
        return []

    mod_prefix = f"{'-'.join(mods)}-" if mods else ""
    if len(key) == 1 and key.isalpha():
        return [f"<{mod_prefix}{key.lower()}>", f"<{mod_prefix}{key.upper()}>"]
    elif len(key) > 1:
        if key.startswith("f") and key[1:].isdigit():
            return [f"<{mod_prefix}{key.upper()}>"]
        return [f"<{mod_prefix}{key.capitalize()}>"]
    else:
        return [f"<{mod_prefix}{key}>"]


class AlfredApp(ctk.CTk):
    """Fenêtre principale d'Alfred."""

    def __init__(
        self,
        config_manager: ConfigManager,
        state_manager: StateManager,
        commands_engine: CommandsEngine,
        grid_manager: GridManager,
        hook_service: KeyboardHookService,
    ) -> None:
        super().__init__()

        self.config_manager = config_manager
        self.state_manager = state_manager
        self.commands_engine = commands_engine
        self.grid_manager = grid_manager
        self.hook_service = hook_service

        self.theme_manager = ThemeManager(self.config_manager.app_config.ui)

        self.title("Alfred - Raccourcis à Modes & Grille")
        self.geometry("720x520")
        self.minsize(580, 420)

        if self.config_manager.app_config.ui.always_on_top:
            self.attributes("-topmost", True)

        # Souscription aux changements d'état
        self.state_manager.subscribe(self._on_state_event)

        # Raccourci clavier dynamique de fermeture quand l'application a le focus
        self._close_bound_sequences: list[str] = []
        self._update_close_shortcut_binding()

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Construction du menu sticky supérieur et des vues
        self._build_sticky_header()
        self._build_content_area()

        # Afficher la vue par défaut (Dashboard)
        self._switch_view("dashboard")

    def _update_close_shortcut_binding(self) -> None:
        """Met à jour les raccourcis clavier de fermeture selon config.toml [general].close."""
        for seq in getattr(self, "_close_bound_sequences", []):
            try:
                self.unbind(seq)
            except Exception:
                pass
        self._close_bound_sequences = []

        close_shortcut = getattr(self.config_manager.app_config.general, "close", "").strip()
        if not close_shortcut:
            logger.info("Aucun raccourci de fermeture configuré (close est vide).")
            return

        sequences = parse_shortcut_to_tk(close_shortcut)
        for seq in sequences:
            self.bind(seq, self.close)
            self._close_bound_sequences.append(seq)
        logger.debug("Raccourci de fermeture '%s' activé sur %s", close_shortcut, sequences)

    def close(self, event: any = None) -> None:
        """Ferme proprement l'application Alfred (arrêt du hook, restauration de la souris, destruction)."""
        logger.info("Fermeture de l'application Alfred...")
        if hasattr(self, "hook_service") and self.hook_service:
            self.hook_service.stop()
        from src.alfred.core.mouse import mouse
        mouse.restore_initial_speed()
        self.destroy()


    def _build_sticky_header(self) -> None:
        """Construit la barre de navigation supérieure toujours visible (Sticky Header)."""
        self.header_frame = ctk.CTkFrame(self, height=48, corner_radius=0, fg_color=("gray90", "gray15"))
        self.header_frame.grid(row=0, column=0, sticky="ew")
        self.header_frame.grid_columnconfigure(1, weight=1)

        # 1. Logo & Titre compact
        left_box = ctk.CTkFrame(self.header_frame, fg_color="transparent")
        left_box.grid(row=0, column=0, padx=(10, 6), pady=6, sticky="w")

        lbl_logo = ctk.CTkLabel(
            left_box,
            text="⚡ ALFRED",
            font=self.theme_manager.get_font(size_offset=2, weight="bold")
        )
        lbl_logo.pack(side="left", padx=(0, 6))

        # Badge interactif du mode actif
        self.btn_header_mode = ctk.CTkButton(
            left_box,
            text=self.state_manager.current_mode.upper(),
            width=90,
            height=26,
            font=self.theme_manager.get_font(size_offset=-1, weight="bold"),
            command=self._on_header_mode_clicked
        )
        self.btn_header_mode.pack(side="left", padx=4)
        self._update_header_mode_badge()

        # 2. Boutons de Navigation (Onglets)
        nav_box = ctk.CTkFrame(self.header_frame, fg_color="transparent")
        nav_box.grid(row=0, column=1, padx=6, pady=6, sticky="w")

        self.btn_nav_dash = ctk.CTkButton(
            nav_box,
            text="📊 Statut",
            width=85,
            height=28,
            font=self.theme_manager.get_font(size_offset=-1),
            command=lambda: self._switch_view("dashboard")
        )
        self.btn_nav_dash.pack(side="left", padx=2)

        self.btn_nav_actions = ctk.CTkButton(
            nav_box,
            text="⚡ Actions",
            width=85,
            height=28,
            font=self.theme_manager.get_font(size_offset=-1),
            fg_color="transparent",
            border_width=1,
            command=lambda: self._switch_view("actions")
        )
        self.btn_nav_actions.pack(side="left", padx=2)

        self.btn_nav_grid = ctk.CTkButton(
            nav_box,
            text="🎯 Grille",
            width=85,
            height=28,
            font=self.theme_manager.get_font(size_offset=-1),
            fg_color="transparent",
            border_width=1,
            command=lambda: self._switch_view("grid")
        )
        self.btn_nav_grid.pack(side="left", padx=2)

        # 3. Actions Rapides à Droite (Pause/Resume Hook, Recharger TOML, Paramètres)
        right_box = ctk.CTkFrame(self.header_frame, fg_color="transparent")
        right_box.grid(row=0, column=2, padx=(6, 10), pady=6, sticky="e")

        # Bouton Hook Actif / En Pause
        self.btn_hook_toggle = ctk.CTkButton(
            right_box,
            text="▶ Actif",
            width=70,
            height=28,
            font=self.theme_manager.get_font(size_offset=-2, weight="bold"),
            fg_color="#059669",
            hover_color="#047857",
            command=self._on_toggle_hook_clicked
        )
        self.btn_hook_toggle.pack(side="left", padx=2)

        # Bouton Recharger TOML
        btn_reload = ctk.CTkButton(
            right_box,
            text="🔄",
            width=32,
            height=28,
            font=self.theme_manager.get_font(size_offset=0),
            fg_color="transparent",
            border_width=1,
            command=self._reload_configurations
        )
        btn_reload.pack(side="left", padx=2)

        # Bouton Paramètres ⚙️
        btn_settings = ctk.CTkButton(
            right_box,
            text="⚙️",
            width=36,
            height=28,
            font=self.theme_manager.get_font(size_offset=1),
            fg_color="transparent",
            border_width=1,
            command=self._open_settings_modal
        )
        btn_settings.pack(side="left", padx=2)

    def _build_content_area(self) -> None:
        """Construit les différentes vues interchangeables."""
        self.content_container = ctk.CTkFrame(self, fg_color="transparent")
        self.content_container.grid(row=1, column=0, sticky="nsew")
        self.content_container.grid_columnconfigure(0, weight=1)
        self.content_container.grid_rowconfigure(0, weight=1)

        # Initialisation des vues
        self.views: dict[str, ctk.CTkFrame] = {
            "dashboard": DashboardView(
                self.content_container,
                self.state_manager,
                self.config_manager,
                self.theme_manager,
            ),
            "actions": ActionsView(
                self.content_container,
                self.config_manager,
                self.commands_engine,
                self.theme_manager,
            ),
            "grid": GridView(
                self.content_container,
                self.grid_manager,
                self.theme_manager,
            ),
        }

    def _switch_view(self, view_name: str) -> None:
        """Bascule d'onglet/vue."""
        for name, view in self.views.items():
            if name == view_name:
                view.grid(row=0, column=0, sticky="nsew")
            else:
                view.grid_forget()

        # Mise à jour visuelle des boutons de navigation
        nav_buttons = {
            "dashboard": self.btn_nav_dash,
            "actions": self.btn_nav_actions,
            "grid": self.btn_nav_grid,
        }
        for name, btn in nav_buttons.items():
            if name == view_name:
                btn.configure(fg_color=("#3B82F6", "#1D4ED8"), border_width=0)
            else:
                btn.configure(fg_color="transparent", border_width=1)

    def _on_header_mode_clicked(self) -> None:
        gen_cfg = self.config_manager.app_config.general
        self.state_manager.toggle_mode(gen_cfg.special_mode_name)

    def _on_toggle_hook_clicked(self) -> None:
        new_state = not self.state_manager.is_hook_enabled
        self.state_manager.set_hook_enabled(new_state)

    def _update_header_mode_badge(self) -> None:
        mode = self.state_manager.current_mode
        bg, text_color = self.theme_manager.get_mode_colors(mode)
        self.btn_header_mode.configure(
            text=mode.upper(),
            fg_color=bg,
            text_color=text_color,
        )

    def _update_hook_button(self) -> None:
        if self.state_manager.is_hook_enabled:
            self.btn_hook_toggle.configure(text="▶ Actif", fg_color="#059669", hover_color="#047857")
        else:
            self.btn_hook_toggle.configure(text="⏸ Pause", fg_color="#DC2626", hover_color="#B91C1C")

    def _on_state_event(self, event_type: str, data: any) -> None:
        """Reçoit les notifications d'état et planifie la mise à jour sur le thread UI Tkinter."""
        self.after(0, self._handle_state_event_in_ui, event_type, data)

    def _handle_state_event_in_ui(self, event_type: str, data: any) -> None:
        match event_type:
            case "mode_changed":
                self._update_header_mode_badge()
                dash = self.views.get("dashboard")
                if isinstance(dash, DashboardView):
                    dash.refresh()
            case "hook_state_changed":
                self._update_hook_button()
            case "log_added" | "logs_cleared":
                dash = self.views.get("dashboard")
                if isinstance(dash, DashboardView):
                    dash.refresh_logs()

    def _reload_configurations(self) -> None:
        """Recharge l'ensemble des fichiers TOML sans redémarrer l'application."""
        self.config_manager.load_all()
        self.grid_manager.update_config(self.config_manager.grid_config)
        self._update_close_shortcut_binding()

        # Rafraîchir les vues
        act_view = self.views.get("actions")
        if isinstance(act_view, ActionsView):
            act_view.refresh_actions()
        grid_view = self.views.get("grid")
        if isinstance(grid_view, GridView):
            grid_view.refresh()

        self.state_manager.add_log(
            action_name="Rechargement Configurations TOML",
            trigger_key="UI",
            mode=self.state_manager.current_mode,
            details=f"{len(self.config_manager.actions)} actions rechargées",
        )

    def _open_settings_modal(self) -> None:
        """Ouvre la popup de configuration."""
        SettingsModal(
            parent=self,
            config_manager=self.config_manager,
            theme_manager=self.theme_manager,
            on_saved_callback=self._on_settings_saved,
        )

    def _on_settings_saved(self) -> None:
        """Appelé lorsque l'utilisateur valide ses paramètres."""
        self.attributes("-topmost", self.config_manager.app_config.ui.always_on_top)
        self._reload_configurations()
