from __future__ import annotations

import tkinter as tk
from tkinter import ttk


class ToolbarPanel(ttk.Frame):
    def __init__(
        self,
        parent,
        *,
        on_load_csv,
        on_export_json,
        on_time_unit_changed,
        time_unit_var: tk.StringVar,
        active_span_var: tk.StringVar,
    ):
        super().__init__(parent, padding=(12, 10))

        left = ttk.Frame(self)
        mid1 = ttk.Frame(self)
        mid2 = ttk.Frame(self)
        right = ttk.Frame(self)

        left.pack(side=tk.LEFT)
        mid1.pack(side=tk.LEFT, padx=14)
        mid2.pack(side=tk.LEFT, padx=14)
        right.pack(side=tk.RIGHT)

        ttk.Button(left, text="Load CSV…", command=on_load_csv, style="Primary.TButton").pack(side=tk.LEFT)

        ttk.Label(mid1, text="Time unit:").pack(side=tk.LEFT, padx=(0, 6))
        ttk.Radiobutton(mid1, text="s", value="s", variable=time_unit_var, command=on_time_unit_changed).pack(side=tk.LEFT)
        ttk.Radiobutton(mid1, text="ms", value="ms", variable=time_unit_var, command=on_time_unit_changed).pack(side=tk.LEFT)

        ttk.Label(mid2, text="Selecting:").pack(side=tk.LEFT, padx=(0, 6))
        ttk.Radiobutton(mid2, text="STEADY", value="steady", variable=active_span_var).pack(side=tk.LEFT)
        ttk.Radiobutton(mid2, text="RAMP", value="ramp", variable=active_span_var).pack(side=tk.LEFT)

        ttk.Button(right, text="Export…", command=on_export_json).pack(side=tk.RIGHT)
