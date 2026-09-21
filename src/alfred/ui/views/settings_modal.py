"""Modal Popup des Paramètres avec persistance dans settings/config.toml."""

from __future__ import annotations
import customtkinter as ctk
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from src.alfred.core.config import ConfigManager
    from src.alfred.ui.theme import ThemeManager


class SettingsModal(ctk.CTkToplevel):
    """Fenêtre modale compacte de configuration des préférences utilisateur."""

    def __init__(
        self,
        parent: ctk.CTkBaseClass,
        config_manager: ConfigManager,
        theme_manager: ThemeManager,
        on_saved_callback: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(parent)
        self.config_manager = config_manager
        self.theme_manager = theme_manager
        self.on_saved_callback = on_saved_callback

        self.title("Paramètres - Alfred")
        self.geometry("460x540")
        self.resizable(False, False)

        # Rendre modal
        self.transient(parent)
        self.grab_set()

        # Fermeture avec Échap ou le raccourci de fermeture configuré s'il existe
        self.bind("<Escape>", lambda e: self.destroy())
        close_key = getattr(self.config_manager.app_config.general, "close", "").strip()
        if close_key:
            from src.alfred.ui.app import parse_shortcut_to_tk
            for seq in parse_shortcut_to_tk(close_key):
                self.bind(seq, lambda e: self.destroy())

        self._build_ui()

    def _build_ui(self) -> None:
        cfg = self.config_manager.app_config

        container = ctk.CTkScrollableFrame(self, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=16, pady=16)

        # En-tête
        lbl_header = ctk.CTkLabel(
            container,
            text="⚙️ Paramètres de Configuration",
            font=self.theme_manager.get_font(size_offset=2, weight="bold")
        )
        lbl_header.pack(anchor="w", pady=(0, 14))

        # --- Section 1: Modes & Raccourcis ---
        sec_mode = ctk.CTkFrame(container, corner_radius=6)
        sec_mode.pack(fill="x", pady=6, padx=2)

        ctk.CTkLabel(
            sec_mode,
            text="CLAVIER & MODES",
            font=self.theme_manager.get_font(size_offset=-1, weight="bold"),
            text_color="gray"
        ).pack(anchor="w", padx=12, pady=(10, 4))

        # Touche mode spécial
        row_key = ctk.CTkFrame(sec_mode, fg_color="transparent")
        row_key.pack(fill="x", padx=12, pady=4)
        ctk.CTkLabel(
            row_key,
            text="Touche Mode Spécial :",
            font=self.theme_manager.get_font(size_offset=-1)
        ).pack(side="left")
        self.entry_special_key = ctk.CTkEntry(
            row_key,
            width=80,
            font=self.theme_manager.get_font(size_offset=-1)
        )
        current_special_key = cfg.general.special_mode_key
        if not current_special_key:
            for act in self.config_manager.actions:
                if act.toggle and (
                    any(any(c.type == "mode" for c in s.commands) for s in act.states)
                    or any(c.type == "mode" for c in act.commands)
                ):
                    current_special_key = act.trigger
                    break
        self.entry_special_key.insert(0, current_special_key or "!")
        self.entry_special_key.pack(side="right")

        # Démarrage automatique en mode spécial
        row_start_special = ctk.CTkFrame(sec_mode, fg_color="transparent")
        row_start_special.pack(fill="x", padx=12, pady=4)
        self.chk_start_in_special_mode = ctk.CTkCheckBox(
            row_start_special,
            text="Démarrer automatiquement en mode spécial",
            font=self.theme_manager.get_font(size_offset=-1),
            checkbox_width=18,
            checkbox_height=18,
        )
        if getattr(cfg.general, "start_in_special_mode", True):
            self.chk_start_in_special_mode.select()
        else:
            self.chk_start_in_special_mode.deselect()
        self.chk_start_in_special_mode.pack(side="left")

        # Sortir automatiquement du mode spécial sur champ texte
        row_auto_exit = ctk.CTkFrame(sec_mode, fg_color="transparent")
        row_auto_exit.pack(fill="x", padx=12, pady=4)
        self.chk_auto_exit_on_text = ctk.CTkCheckBox(
            row_auto_exit,
            text="Quitter le mode spécial sur sélection d'un champ texte",
            font=self.theme_manager.get_font(size_offset=-1),
            checkbox_width=18,
            checkbox_height=18,
        )
        if getattr(cfg.general, "auto_exit_on_text_input", True):
            self.chk_auto_exit_on_text.select()
        else:
            self.chk_auto_exit_on_text.deselect()
        self.chk_auto_exit_on_text.pack(side="left")

        # Retourner en mode spécial lors de l'envoi avec Entrée
        row_auto_return = ctk.CTkFrame(sec_mode, fg_color="transparent")
        row_auto_return.pack(fill="x", padx=12, pady=4)
        self.chk_auto_return_on_enter = ctk.CTkCheckBox(
            row_auto_return,
            text="Retourner en mode spécial lors de l'envoi avec Entrée",
            font=self.theme_manager.get_font(size_offset=-1),
            checkbox_width=18,
            checkbox_height=18,
        )
        if getattr(cfg.general, "auto_return_on_enter", True):
            self.chk_auto_return_on_enter.select()
        else:
            self.chk_auto_return_on_enter.deselect()
        self.chk_auto_return_on_enter.pack(side="left")

        # Raccourci de fermeture
        row_close = ctk.CTkFrame(sec_mode, fg_color="transparent")
        row_close.pack(fill="x", padx=12, pady=(4, 10))
        ctk.CTkLabel(
            row_close,
            text="Fermer Alfred (Focus) :",
            font=self.theme_manager.get_font(size_offset=-1)
        ).pack(side="left")
        self.entry_close_shortcut = ctk.CTkEntry(
            row_close,
            width=120,
            font=self.theme_manager.get_font(size_offset=-1),
            placeholder_text="ex: ctrl+w"
        )
        self.entry_close_shortcut.insert(0, getattr(cfg.general, "close", ""))
        self.entry_close_shortcut.pack(side="right")

        # --- Section 2: Vitesse Normale du Curseur ---
        sec_mouse = ctk.CTkFrame(container, corner_radius=6)
        sec_mouse.pack(fill="x", pady=6, padx=2)

        ctk.CTkLabel(
            sec_mouse,
            text="VITESSE NORMALE DU CURSEUR",
            font=self.theme_manager.get_font(size_offset=-1, weight="bold"),
            text_color="gray"
        ).pack(anchor="w", padx=12, pady=(10, 4))

        row_sys_speed = ctk.CTkFrame(sec_mouse, fg_color="transparent")
        row_sys_speed.pack(fill="x", padx=12, pady=4)

        self.switch_use_sys_speed = ctk.CTkSwitch(
            row_sys_speed,
            text="Prendre la vitesse de Windows par défaut",
            font=self.theme_manager.get_font(size_offset=-1),
            command=self._on_toggle_sys_speed
        )
        if cfg.mouse.use_system_speed:
            self.switch_use_sys_speed.select()
        else:
            self.switch_use_sys_speed.deselect()
        self.switch_use_sys_speed.pack(side="left")

        self.row_custom_speed = ctk.CTkFrame(sec_mouse, fg_color="transparent")
        self.row_custom_speed.pack(fill="x", padx=12, pady=(4, 10))

        ctk.CTkLabel(
            self.row_custom_speed,
            text="Vitesse Personnalisée :",
            font=self.theme_manager.get_font(size_offset=-1)
        ).pack(side="left")

        self.slider_def_speed = ctk.CTkSlider(
            self.row_custom_speed,
            from_=1,
            to=20,
            number_of_steps=19,
            width=140,
            command=self._on_speed_slider_changed
        )
        self.slider_def_speed.set(cfg.mouse.default_speed)
        self.slider_def_speed.pack(side="left", padx=8)

        self.lbl_def_speed_val = ctk.CTkLabel(
            self.row_custom_speed,
            text=str(cfg.mouse.default_speed),
            width=30,
            font=self.theme_manager.get_font(size_offset=-1, weight="bold")
        )
        self.lbl_def_speed_val.pack(side="right")
        self._update_speed_slider_state()

        # --- Section 3: Interface Visuelle (Thème, Police) ---
        sec_ui = ctk.CTkFrame(container, corner_radius=6)
        sec_ui.pack(fill="x", pady=6, padx=2)

        ctk.CTkLabel(
            sec_ui,
            text="APPARENCE & DESIGN UI",
            font=self.theme_manager.get_font(size_offset=-1, weight="bold"),
            text_color="gray"
        ).pack(anchor="w", padx=12, pady=(10, 4))

        # Thème sombre / clair
        row_theme = ctk.CTkFrame(sec_ui, fg_color="transparent")
        row_theme.pack(fill="x", padx=12, pady=4)
        ctk.CTkLabel(
            row_theme,
            text="Thème Couleur :",
            font=self.theme_manager.get_font(size_offset=-1)
        ).pack(side="left")

        theme_french = {"dark": "Sombre", "light": "Clair", "system": "Système"}
        current_theme_fr = theme_french.get(cfg.ui.theme, "Sombre")
        self.seg_theme = ctk.CTkSegmentedButton(
            row_theme,
            values=["Sombre", "Clair", "Système"],
            font=self.theme_manager.get_font(size_offset=-2)
        )
        self.seg_theme.set(current_theme_fr)
        self.seg_theme.pack(side="right")

        # Taille de police
        row_font = ctk.CTkFrame(sec_ui, fg_color="transparent")
        row_font.pack(fill="x", padx=12, pady=4)
        ctk.CTkLabel(
            row_font,
            text="Taille Police :",
            font=self.theme_manager.get_font(size_offset=-1)
        ).pack(side="left")
        self.slider_font = ctk.CTkSlider(
            row_font,
            from_=10,
            to=18,
            number_of_steps=8,
            width=140,
            command=self._on_font_slider_changed
        )
        self.slider_font.set(cfg.ui.font_size)
        self.slider_font.pack(side="left", padx=8)
        self.lbl_font_val = ctk.CTkLabel(
            row_font,
            text=f"{cfg.ui.font_size} px",
            width=45,
            font=self.theme_manager.get_font(size_offset=-1, weight="bold")
        )
        self.lbl_font_val.pack(side="right")

        # Always on top
        row_top = ctk.CTkFrame(sec_ui, fg_color="transparent")
        row_top.pack(fill="x", padx=12, pady=4)
        self.switch_always_top = ctk.CTkSwitch(
            row_top,
            text="Toujours au premier plan (Always on Top)",
            font=self.theme_manager.get_font(size_offset=-1)
        )
        if cfg.ui.always_on_top:
            self.switch_always_top.select()
        else:
            self.switch_always_top.deselect()
        self.switch_always_top.pack(anchor="w")

        # Démarrer réduit dans la zone de notification (au lancement)
        row_min = ctk.CTkFrame(sec_ui, fg_color="transparent")
        row_min.pack(fill="x", padx=12, pady=(4, 10))
        self.chk_start_minimized = ctk.CTkCheckBox(
            row_min,
            text="Démarrer minimisé au lancement (dans la zone de notification)",
            font=self.theme_manager.get_font(size_offset=-1),
            checkbox_width=20,
            checkbox_height=20,
        )
        if getattr(cfg.ui, "start_minimized", True):
            self.chk_start_minimized.select()
        else:
            self.chk_start_minimized.deselect()
        self.chk_start_minimized.pack(anchor="w")
        self.switch_start_minimized = self.chk_start_minimized

        # --- Boutons d'Action Inférieurs ---
        btn_bar = ctk.CTkFrame(container, fg_color="transparent")
        btn_bar.pack(fill="x", pady=(14, 6))

        ctk.CTkButton(
            btn_bar,
            text="Annuler",
            width=90,
            height=32,
            fg_color="transparent",
            border_width=1,
            font=self.theme_manager.get_font(size_offset=-1),
            command=self.destroy
        ).pack(side="left", padx=4)

        ctk.CTkButton(
            btn_bar,
            text="💾 Enregistrer les Modifications",
            height=32,
            font=self.theme_manager.get_font(size_offset=0, weight="bold"),
            command=self._save_changes
        ).pack(side="right", padx=4, fill="x", expand=True)

    def _on_toggle_sys_speed(self) -> None:
        self._update_speed_slider_state()

    def _update_speed_slider_state(self) -> None:
        use_sys = bool(self.switch_use_sys_speed.get())
        if use_sys:
            self.slider_def_speed.configure(state="disabled")
            self.lbl_def_speed_val.configure(text_color="gray")
        else:
            self.slider_def_speed.configure(state="normal")
            self.lbl_def_speed_val.configure(text_color=("black", "white"))

    def _on_speed_slider_changed(self, val: float) -> None:
        self.lbl_def_speed_val.configure(text=str(int(val)))

    def _on_font_slider_changed(self, val: float) -> None:
        self.lbl_font_val.configure(text=f"{int(val)} px")

    def _save_changes(self) -> None:
        """Persiste les données dans config.toml et met à jour l'application."""
        cfg = self.config_manager.app_config

        # Récupération des valeurs
        new_key = self.entry_special_key.get().strip() or "!"
        new_start_special = bool(self.chk_start_in_special_mode.get())
        new_auto_exit = bool(self.chk_auto_exit_on_text.get())
        new_default_mode = "special" if new_start_special else "normal"
        new_close = self.entry_close_shortcut.get().strip()
        new_use_sys_speed = bool(self.switch_use_sys_speed.get())
        new_def_speed = int(self.slider_def_speed.get())

        theme_map = {"Sombre": "dark", "Clair": "light", "Système": "system"}
        new_theme = theme_map.get(self.seg_theme.get(), "dark")
        new_font_size = int(self.slider_font.get())
        new_always_top = bool(self.switch_always_top.get())
        new_start_minimized = bool(self.switch_start_minimized.get())

        # Affectation
        cfg.general.special_mode_key = new_key
        cfg.general.start_in_special_mode = new_start_special
        cfg.general.auto_exit_on_text_input = new_auto_exit
        cfg.general.auto_return_on_enter = bool(self.chk_auto_return_on_enter.get())
        cfg.general.default_mode = new_default_mode
        cfg.general.close = new_close
        for act in self.config_manager.actions:
            if act.toggle and (
                any(any(c.type == "mode" for c in s.commands) for s in act.states)
                or any(c.type == "mode" for c in act.commands)
            ):
                act.trigger = new_key.lower()
        cfg.mouse.use_system_speed = new_use_sys_speed
        cfg.mouse.default_speed = new_def_speed
        cfg.ui.theme = new_theme
        cfg.ui.font_size = new_font_size
        cfg.ui.always_on_top = new_always_top
        cfg.ui.start_minimized = new_start_minimized

        # Sauvegarde sur le disque
        self.config_manager.save_app_config()

        # Application du thème
        self.theme_manager.apply_theme()

        if self.on_saved_callback:
            self.on_saved_callback()

        self.destroy()
