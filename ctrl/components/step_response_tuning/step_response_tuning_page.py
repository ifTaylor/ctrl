from __future__ import annotations

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from typing import Callable, Optional

import numpy as np

from ctrl.components.step_response_tuning.step_response_tuning_controls import StepTuningControls
from ctrl.components.step_response_tuning.step_response_tuning_plot_panel import StepTuningPlotPanel
from ctrl.models import StepTuneSelections, StepIdResult
from ctrl.services import StepSeries, load_step_csv
from ctrl.services.step_identification_service import smooth_moving_average, identify, compute_pid_gains


class StepTuningPage(ttk.Frame):
    def __init__(self, parent, *, on_back: Callable[[], None]):
        super().__init__(parent, padding=0)

        self.ts: Optional[StepSeries] = None
        self.selections = StepTuneSelections()
        self.result: Optional[StepIdResult] = None
        self.pv_hat: Optional[np.ndarray] = None

        header = ttk.Frame(self, padding=8)
        header.pack(side=tk.TOP, fill=tk.X)
        ttk.Button(header, text="← Back", command=on_back).pack(side=tk.LEFT)
        ttk.Label(header, text="Step Response Tuner", font=("Segoe UI", 14, "bold")).pack(side=tk.LEFT, padx=10)

        pan = ttk.Panedwindow(self, orient=tk.HORIZONTAL)
        pan.pack(fill=tk.BOTH, expand=True)

        left = ttk.Frame(pan)
        right = ttk.Frame(pan)
        pan.add(left, weight=0)
        pan.add(right, weight=1)

        self.active_mode = tk.StringVar(value="baseline")
        self.model = tk.StringVar(value="FOPDT")

        self.tuning_method = tk.StringVar(value="IMC_PID")
        self.lam = tk.DoubleVar(value=1.0)

        self.controls = StepTuningControls(
            left,
            active_mode_var=self.active_mode,
            model_var=self.model,
            tuning_method_var=self.tuning_method,
            lam_var=self.lam,
            on_load=self._on_load,
            on_fit=self._on_fit,
            on_clear=self._on_clear,
        )
        self.controls.pack(fill="both", expand=True)

        self.plot = StepTuningPlotPanel(
            right,
            on_span_selected=self._on_span_selected,
            on_point_selected=self._on_point_selected,
            active_mode_var=self.active_mode,
        )
        self.plot.pack(fill="both", expand=True)

        self.model.trace_add("write", self._on_model_changed)
        self._refresh_ui()

    def _on_model_changed(self, *_args) -> None:
        self.controls.set_measurands(self.model.get())
        self._refresh_ui()

    def _refresh_ui(self) -> None:
        self._refresh_plot_annotations()
        self._refresh_status()

    def _refresh_plot_annotations(self) -> None:
        self.plot.set_spans(
            self.selections.baseline.as_tuple(),
            self.selections.final.as_tuple(),
            self.selections.fit.as_tuple(),
            self.selections.slope.as_tuple(),
        )
        self.plot.set_points(
            self.selections.t_step.get(),
            self.selections.t_dead.get(),
            self.selections.theta.get(),
            self.selections.t63.get(),
            self.selections.peak.get(),
        )
        self.plot.set_overlay(self.pv_hat)

    def _refresh_status(self) -> None:
        model = self.model.get()
        lines = [
            f"Model: {model}",
            f"Active: {self.active_mode.get()}",
            f"Tuning: {self.tuning_method.get()}  (λ={float(self.lam.get()):.2f}s)",
            "",
            "Filled:",
        ]

        def have_span(s) -> bool:
            return s.as_tuple() is not None

        def have_point(p) -> bool:
            return p.get() is not None

        if have_span(self.selections.baseline): lines.append("  • Baseline")
        if have_span(self.selections.final): lines.append("  • Final")
        if have_point(self.selections.theta) or have_point(self.selections.t_dead): lines.append("  • Theta θ")
        if model == "FOPDT" and have_point(self.selections.t63): lines.append("  • t63")
        if model == "IPDT" and have_span(self.selections.slope): lines.append("  • Slope")
        if model == "SOPDT_UNDERDAMPED" and have_point(self.selections.peak): lines.append("  • Peak")
        if have_span(self.selections.fit): lines.append("  • Fit(optional)")

        if self.result is not None:
            lines += ["", "Identified:"]
            lines.append(f"  K = {self.result.get('K', float('nan')):.6g}")
            if model == "FOPDT":
                lines.append(f"  tau = {self.result.get('tau_s', float('nan')):.6g} s")
                lines.append(f"  theta = {self.result.theta_s:.6g} s")
            if model == "SOPDT_UNDERDAMPED":
                lines.append(f"  zeta = {self.result.get('zeta', float('nan')):.6g}")
                lines.append(f"  wn = {self.result.get('wn', float('nan')):.6g} rad/s")
                lines.append(f"  theta = {self.result.theta_s:.6g} s")
            if np.isfinite(self.result.rmse):
                lines.append(f"  RMSE = {self.result.rmse:.6g} ({self.result.n_fit} pts)")

            if "Kp" in self.result.params:
                lines += ["", "PID/PI Gains:"]
                lines.append(f"  Kp = {self.result.get('Kp', float('nan')):.6g}")
                lines.append(f"  Ki = {self.result.get('Ki', float('nan')):.6g}")
                lines.append(f"  Kd = {self.result.get('Kd', float('nan')):.6g}")
                Ti = self.result.get("Ti", float('nan'))
                Td = self.result.get("Td", float('nan'))
                if np.isfinite(Ti): lines.append(f"  Ti = {Ti:.6g} s")
                if np.isfinite(Td) and Td > 0: lines.append(f"  Td = {Td:.6g} s")

        self.controls.set_status("\n".join(lines))

    def _on_span_selected(self, span_name: str, a: int, b: int) -> None:
        try:
            self.selections.set_span(span_name, a, b)
            self._refresh_ui()
        except Exception as e:
            messagebox.showerror("Span Selection Error", str(e))

    def _on_point_selected(self, point_name: str, i: int) -> None:
        try:
            self.selections.set_point(point_name, i)
            if point_name == "theta":
                self.selections.t_dead.clear()
            self._refresh_ui()
        except Exception as e:
            messagebox.showerror("Point Selection Error", str(e))

    def _on_clear(self) -> None:
        self.selections.clear_all()
        self.result = None
        self.pv_hat = None
        self._refresh_ui()

    def _on_load(self) -> None:
        path = filedialog.askopenfilename(
            title="Open step response CSV",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            ts = load_step_csv(path)
            pv_raw = ts.pv_raw if ts.pv_raw is not None else ts.pv.copy()
            pv_sm = smooth_moving_average(pv_raw, win=9)
            ts = StepSeries(t=ts.t, cv=ts.cv, pv=pv_sm, pv_raw=pv_raw, dt_s=ts.dt_s, source_path=ts.source_path)

            self.ts = ts
            self.plot.set_series(ts.t, ts.cv, ts.pv, pv_raw=ts.pv_raw)
            self._on_clear()
        except Exception as e:
            messagebox.showerror("Load Error", str(e))

    def _on_fit(self) -> None:
        if self.ts is None:
            messagebox.showwarning("No data", "Load a CSV first.")
            return
        try:
            res, pv_hat = identify(self.ts, self.selections, self.model.get())
            gains = compute_pid_gains(self.model.get(), res, method=self.tuning_method.get(), lam_s=float(self.lam.get()))
            res.params.update(gains)

            self.result = res
            self.pv_hat = pv_hat
            self._refresh_ui()
        except Exception as e:
            messagebox.showerror("Identify Error", str(e))
