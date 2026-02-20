from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable

from .toolbar_panel import ToolbarPanel
from .plot_panel import PlotPanel
from .results_panel import ResultsPanel
from .tuning_controls_panel import TuningControlsPanel


class MainView(ttk.Frame):
    def __init__(
        self,
        parent,
        *,
        on_load_csv: Callable[[], None],
        on_export_json: Callable[[], None],
        on_time_unit_changed: Callable[[], None],
        on_span_selected: Callable[[str, int, int], None],
        on_tuning_changed: Callable[[], None],
    ):
        super().__init__(parent, padding=0)

        self.time_unit_var = tk.StringVar(value="s")
        self.active_span_var = tk.StringVar(value="steady")

        # ---- toolbar at top ----
        self.toolbar = ToolbarPanel(
            self,
            on_load_csv=on_load_csv,
            on_export_json=on_export_json,
            on_time_unit_changed=on_time_unit_changed,
            time_unit_var=self.time_unit_var,
            active_span_var=self.active_span_var,
        )
        self.toolbar.grid(row=0, column=0, columnspan=2, sticky="ew")
        self.columnconfigure(0, weight=4)
        self.columnconfigure(1, weight=1)
        self.rowconfigure(1, weight=1)

        # Left
        left = ttk.Frame(self, padding=8)
        left.grid(row=1, column=0, sticky="nsew")
        left.rowconfigure(0, weight=1)
        left.columnconfigure(0, weight=1)

        self.panes = ttk.PanedWindow(left, orient=tk.VERTICAL)
        self.panes.grid(row=0, column=0, sticky="nsew")

        self.plot_container = ttk.Frame(self.panes)
        self.results_container = ttk.Frame(self.panes)

        self.plot = PlotPanel(
            self.plot_container,
            on_span_selected=on_span_selected,
            active_span_var=self.active_span_var,
        )
        self.plot.pack(fill=tk.BOTH, expand=True)

        self.results = ResultsPanel(self.results_container)
        self.results.pack(fill=tk.BOTH, expand=True)

        self.panes.add(self.plot_container, weight=4)
        self.panes.add(self.results_container, weight=1)

        # Right
        self.tuning_controls = TuningControlsPanel(self, on_change=on_tuning_changed)
        self.tuning_controls.grid(row=1, column=1, sticky="nsew", padx=(0, 8), pady=8)

        self.after(50, self._set_initial_sash)

    def _set_initial_sash(self):
        try:
            total_h = self.winfo_height()
            if total_h > 300:
                self.panes.sashpos(0, int(total_h * 0.75))
        except Exception:
            pass

    def time_unit(self) -> str:
        return self.time_unit_var.get().strip().lower()
