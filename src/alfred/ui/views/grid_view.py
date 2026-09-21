"""Vue interactive de la Grille Souris (settings/grid.toml)."""

from __future__ import annotations
import customtkinter as ctk
from typing import TYPE_CHECKING
import threading

from src.alfred.core.mouse import mouse

if TYPE_CHECKING:
    from src.alfred.core.grid import GridManager
    from src.alfred.ui.theme import ThemeManager


class GridView(ctk.CTkFrame):
    """Visualisation et test de la grille de coordonnées de l'écran."""

    def __init__(
        self,
        master: ctk.CTkBaseClass,
        grid_manager: GridManager,
        theme_manager: ThemeManager,
        **kwargs
    ) -> None:
        super().__init__(master, **kwargs)
        self.grid_manager = grid_manager
        self.theme_manager = theme_manager

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self._build_info_bar()
        self._build_matrix_display()

    def _build_info_bar(self) -> None:
        """Barre d'information sur la résolution et la grille."""
        w, h = mouse.get_screen_size()
        cfg = self.grid_manager.config

        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.grid(row=0, column=0, sticky="ew", padx=10, pady=(8, 4))
        bar.grid_columnconfigure(0, weight=1)

        snap_info = f"  |  Bord : [{cfg.edge_snap_key}] ({cfg.edge_offset} px)" if cfg.edge_snap_enabled else ""
        lbl_info = ctk.CTkLabel(
            bar,
            text=f"Résolution : {w}x{h} px  |  Grille : {cfg.columns}x{cfg.rows}  |  Sous-grille : [{cfg.subgrid_toggle_key}]{snap_info}",
            font=self.theme_manager.get_font(size_offset=-1, weight="bold")
        )
        lbl_info.grid(row=0, column=0, sticky="w")

        right_panel = ctk.CTkFrame(bar, fg_color="transparent")
        right_panel.grid(row=0, column=1, sticky="e")

        if cfg.edge_snap_enabled:
            btn_snap_edge = ctk.CTkButton(
                right_panel,
                text=f"Bord [{cfg.edge_snap_key}]",
                font=self.theme_manager.get_font(size_offset=-2),
                height=26,
                width=80,
                command=lambda: threading.Thread(target=self.grid_manager.snap_to_edge, daemon=True).start()
            )
            btn_snap_edge.pack(side="right", padx=(6, 0))

        btn_toggle_sub = ctk.CTkButton(
            right_panel,
            text=f"Toggle Sous-grille [{cfg.subgrid_toggle_key}]",
            font=self.theme_manager.get_font(size_offset=-2),
            height=26,
            width=130,
            command=lambda: threading.Thread(target=self.grid_manager.toggle_subgrid, daemon=True).start()
        )
        btn_toggle_sub.pack(side="right", padx=(6, 0))

        lbl_hint = ctk.CTkLabel(
            right_panel,
            text="Cliquez sur une case pour tester",
            font=self.theme_manager.get_font(size_offset=-2),
            text_color="gray"
        )
        lbl_hint.pack(side="right")

    def _build_matrix_display(self) -> None:
        """Construit la représentation visuelle en grille des cases."""
        container = ctk.CTkFrame(self, corner_radius=8)
        container.grid(row=1, column=0, sticky="nsew", padx=10, pady=(4, 10))

        cols = self.grid_manager.config.columns
        rows = self.grid_manager.config.rows

        for c in range(cols):
            container.grid_columnconfigure(c, weight=1, uniform="col")
        for r in range(rows):
            container.grid_rowconfigure(r, weight=1, uniform="row")

        # Inverser le mapping cellules pour retrouver la touche associée à (col, row)
        coord_to_key: dict[tuple[int, int], str] = {}
        for key, coords in self.grid_manager.config.cells.items():
            if coords not in coord_to_key:
                coord_to_key[coords] = key

        screen_w, screen_h = mouse.get_screen_size()

        for r in range(rows):
            for c in range(cols):
                assigned_key = coord_to_key.get((c, r), "--").upper()
                cx, cy = self.grid_manager.get_cell_center(c, r, screen_w, screen_h)

                cell_btn = ctk.CTkButton(
                    container,
                    text=f"[{assigned_key}]\nCol {c}, Lig {r}\n({cx}, {cy})",
                    font=self.theme_manager.get_font(size_offset=-1),
                    fg_color=("gray80", "gray25"),
                    hover_color=("#3B82F6", "#1D4ED8"),
                    corner_radius=6,
                    command=lambda col=c, row=r: threading.Thread(
                        target=self.grid_manager.jump_to_cell,
                        args=(col, row),
                        daemon=True
                    ).start()
                )
                cell_btn.grid(row=r, column=c, padx=4, pady=4, sticky="nsew")

    def refresh(self) -> None:
        """Rafraîchit l'affichage de la grille."""
        for child in self.winfo_children():
            child.destroy()
        self._build_info_bar()
        self._build_matrix_display()
