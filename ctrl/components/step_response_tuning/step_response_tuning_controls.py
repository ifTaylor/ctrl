from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable, List, Tuple


class StepTuningControls(ttk.Frame):
    def __init__(
        self,
        parent,
        *,
        active_mode_var: tk.StringVar,
        model_var: tk.StringVar,
        tuning_method_var: tk.StringVar,
        lam_var: tk.DoubleVar,
        on_load: Callable[[], None],
        on_fit: Callable[[], None],
        on_clear: Callable[[], None],
    ):
        super().__init__(parent, padding=10)

        self.active_mode_var = active_mode_var
        self.model_var = model_var
        self.tuning_method_var = tuning_method_var
        self.lam_var = lam_var

        file_box = ttk.LabelFrame(self, text="Data", padding=10)
        file_box.pack(fill="x")
        ttk.Button(file_box, text="Open CSV…", command=on_load).pack(fill="x")
        ttk.Button(file_box, text="Clear Picks", command=on_clear).pack(fill="x", pady=(6, 0))

        model_box = ttk.LabelFrame(self, text="Model", padding=10)
        model_box.pack(fill="x", pady=(10, 0))

        ttk.Label(model_box, text="Plant model:").grid(row=0, column=0, sticky="w", padx=(0, 8))
        ttk.Combobox(
            model_box,
            textvariable=self.model_var,
            state="readonly",
            values=["FOPDT", "IPDT", "SOPDT_UNDERDAMPED"],
            width=18,
        ).grid(row=0, column=1, sticky="w")

        meas_box = ttk.LabelFrame(self, text="Measurands (select ONE, then drag/click)", padding=10)
        meas_box.pack(fill="both", expand=False, pady=(10, 0))

        self._items: List[Tuple[str, str]] = []
        self._list = tk.Listbox(meas_box, height=7, exportselection=False)
        self._list.pack(fill="x")
        self._hint = ttk.Label(meas_box, text="Select a measurand above.", wraplength=240)
        self._hint.pack(fill="x", pady=(6, 0))
        self._list.bind("<<ListboxSelect>>", self._on_list_select)

        tuning_box = ttk.LabelFrame(self, text="Tuning", padding=10)
        tuning_box.pack(fill="x", pady=(10, 0))

        ttk.Label(tuning_box, text="Method:").grid(row=0, column=0, sticky="w", padx=(0, 8))
        ttk.Combobox(
            tuning_box,
            textvariable=self.tuning_method_var,
            state="readonly",
            values=["IMC_PID", "IMC_PI", "SIMC_PI"],
            width=18,
        ).grid(row=0, column=1, sticky="w")

        ttk.Label(tuning_box, text="λ (IMC):").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=(8, 0))
        ttk.Scale(
            tuning_box,
            from_=0.1,
            to=10.0,
            orient="horizontal",
            variable=self.lam_var,
        ).grid(row=1, column=1, sticky="ew", pady=(8, 0))
        tuning_box.columnconfigure(1, weight=1)

        self._lam_label = ttk.Label(tuning_box, text="")
        self._lam_label.grid(row=2, column=1, sticky="e")
        self.lam_var.trace_add("write", self._update_lam_label)
        self._update_lam_label()

        act = ttk.LabelFrame(self, text="Actions", padding=10)
        act.pack(fill="x", pady=(10, 0))
        ttk.Button(act, text="Compute / Update", command=on_fit).pack(fill="x")

        self._status = ttk.Label(self, text="", justify="left")
        self._status.pack(fill="x", pady=(10, 0))

        self.set_measurands(self.model_var.get() or "FOPDT")

    def _update_lam_label(self, *_args) -> None:
        self._lam_label.config(text=f"{float(self.lam_var.get()):.2f} s")

    def set_measurands(self, model: str) -> None:
        model = (model or "").strip().upper()
        if model not in ("FOPDT", "IPDT", "SOPDT_UNDERDAMPED"):
            model = "FOPDT"

        if model == "FOPDT":
            items = [("Baseline[span]", "baseline"), ("Final[span]", "final"), ("Theta θ[point]", "theta"), ("t63 (63%)[point]", "t63")]
        elif model == "IPDT":
            items = [("Baseline[span]", "baseline"), ("Final[span]", "final"), ("Theta θ[point]", "theta"), ("Slope[span]", "slope")]
        else:
            items = [("Baseline[span]", "baseline"), ("Final[span]", "final"), ("Theta θ[point]", "theta"), ("Peak (1st)[point]", "peak")]

        items.append(("Fit window[span] (optional)", "fit"))

        self._items = items
        self._list.delete(0, tk.END)
        for label, _mode in items:
            self._list.insert(tk.END, label)

        if items:
            self._list.selection_set(0)
            self._apply_selection(0)

    def _on_list_select(self, _evt=None) -> None:
        sel = self._list.curselection()
        if sel:
            self._apply_selection(int(sel[0]))

    def _apply_selection(self, idx: int) -> None:
        idx = max(0, min(idx, len(self._items) - 1))
        label, mode = self._items[idx]
        self.active_mode_var.set(mode)
        hint = "Drag on the plot to define this span." if mode in ("baseline", "final", "fit", "slope") else "Click on the plot to set this point."
        self._hint.config(text=hint + f"  ({label})")

    def set_status(self, text: str) -> None:
        self._status.config(text=text or "")
