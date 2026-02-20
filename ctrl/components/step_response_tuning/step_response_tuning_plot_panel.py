from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable, Optional, Tuple

import matplotlib
matplotlib.use("TkAgg")
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.widgets import SpanSelector

import numpy as np


class StepTuningPlotPanel(ttk.Frame):
    def __init__(
        self,
        parent,
        *,
        on_span_selected: Callable[[str, int, int], None],
        on_point_selected: Callable[[str, int], None],
        active_mode_var: tk.StringVar,
    ):
        super().__init__(parent, padding=8)

        self._on_span_selected = on_span_selected
        self._on_point_selected = on_point_selected
        self._active_mode_var = active_mode_var

        self._t: Optional[np.ndarray] = None
        self._cv: Optional[np.ndarray] = None
        self._pv: Optional[np.ndarray] = None
        self._pv_raw: Optional[np.ndarray] = None
        self._pv_hat: Optional[np.ndarray] = None

        self._baseline_span: Optional[Tuple[int, int]] = None
        self._final_span: Optional[Tuple[int, int]] = None
        self._fit_span: Optional[Tuple[int, int]] = None
        self._slope_span: Optional[Tuple[int, int]] = None

        self._i_step: Optional[int] = None
        self._i_dead: Optional[int] = None
        self._i_theta: Optional[int] = None
        self._i_t63: Optional[int] = None
        self._i_peak: Optional[int] = None

        self.fig = Figure(figsize=(10.5, 6.5), dpi=100)
        self.ax = self.fig.add_subplot(1, 1, 1)
        self.ax.grid(True)
        self.ax.set_title("Step Tuner")
        self.ax.set_xlabel("time (s)")
        self.ax.set_ylabel("Value")

        self.canvas = FigureCanvasTkAgg(self.fig, master=self)
        self.canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        self.toolbar = NavigationToolbar2Tk(self.canvas, self)
        self.toolbar.update()

        self._span_selector = SpanSelector(
            self.ax,
            onselect=self._on_span_select,
            direction="horizontal",
            useblit=True,
            interactive=True,
            drag_from_anywhere=True,
        )

        self.canvas.mpl_connect("button_press_event", self._on_click)

    def set_series(self, t: np.ndarray, cv: np.ndarray, pv: np.ndarray, pv_raw: Optional[np.ndarray] = None) -> None:
        self._t = t
        self._cv = cv
        self._pv = pv
        self._pv_raw = pv_raw
        self.redraw()

    def set_overlay(self, pv_hat: Optional[np.ndarray]) -> None:
        self._pv_hat = pv_hat
        self.redraw()

    def set_spans(self, baseline: Optional[Tuple[int, int]], final: Optional[Tuple[int, int]], fit: Optional[Tuple[int, int]], slope: Optional[Tuple[int, int]] = None) -> None:
        self._baseline_span = baseline
        self._final_span = final
        self._fit_span = fit
        self._slope_span = slope
        self.redraw()

    def set_points(self, i_step: Optional[int], i_dead: Optional[int], i_theta: Optional[int] = None, i_t63: Optional[int] = None, i_peak: Optional[int] = None) -> None:
        self._i_step = i_step
        self._i_dead = i_dead
        self._i_theta = i_theta
        self._i_t63 = i_t63
        self._i_peak = i_peak
        self.redraw()

    def _on_span_select(self, xmin: float, xmax: float) -> None:
        if self._t is None:
            return
        if xmax < xmin:
            xmin, xmax = xmax, xmin

        a = int(np.searchsorted(self._t, float(xmin), side="left"))
        b = int(np.searchsorted(self._t, float(xmax), side="right"))

        a = max(0, min(a, len(self._t) - 1))
        b = max(0, min(b, len(self._t)))

        if b <= a:
            return

        mode = self._active_mode_var.get().strip().lower()
        if mode in ("baseline", "final", "fit", "slope"):
            self._on_span_selected(mode, a, b)

    def _on_click(self, event) -> None:
        if event.inaxes != self.ax:
            return
        if self._t is None or event.xdata is None:
            return

        i = int(np.searchsorted(self._t, float(event.xdata), side="left"))
        i = max(0, min(i, len(self._t) - 1))

        mode = self._active_mode_var.get().strip().lower()
        if mode in ("step", "deadtime", "peak", "theta", "t63"):
            name = {"step": "t_step", "deadtime": "t_dead", "theta": "theta", "t63": "t63", "peak": "peak"}[mode]
            self._on_point_selected(name, i)

    def redraw(self) -> None:
        self.ax.clear()
        self.ax.grid(True)

        if self._t is None or self._pv is None or self._cv is None:
            self.ax.set_title("Step Tuner — open a CSV to begin")
            self.ax.set_xlabel("time (s)")
            self.ax.set_ylabel("Value")
            self.canvas.draw_idle()
            return

        t = self._t
        pv = self._pv
        cv = self._cv

        if self._pv_raw is not None and len(self._pv_raw) == len(t):
            self.ax.plot(t, self._pv_raw, label="PV raw", alpha=0.35)

        self.ax.plot(t, pv, label="PV (smoothed)")
        self.ax.plot(t, cv, label="CO", linewidth=2.0)

        if self._pv_hat is not None and len(self._pv_hat) == len(t):
            self.ax.plot(t, self._pv_hat, label="PV_hat")

        def draw_span(span: Optional[Tuple[int, int]], label: str, alpha: float) -> None:
            if span is None:
                return
            a, b = span
            if a < 0 or b <= a or b > len(t):
                return
            self.ax.axvspan(t[a], t[b - 1], alpha=alpha, label=label)

        draw_span(self._baseline_span, "Baseline", 0.12)
        draw_span(self._final_span, "Final", 0.12)
        draw_span(self._fit_span, "Fit", 0.08)
        draw_span(self._slope_span, "Slope", 0.08)

        def draw_point(i: Optional[int], label: str) -> None:
            if i is None:
                return
            ii = int(i)
            if ii < 0 or ii >= len(t):
                return
            self.ax.axvline(t[ii], linestyle=":", linewidth=1.2, label=label)

        draw_point(self._i_step, "t_step")
        draw_point(self._i_dead, "t_dead")
        draw_point(self._i_theta, "θ")
        draw_point(self._i_t63, "t63")
        draw_point(self._i_peak, "Peak")

        self.ax.set_title("Step Tuner — select measurand, then drag/click")
        self.ax.set_xlabel("time (s)")
        self.ax.set_ylabel("Value")
        self.ax.legend(loc="best")
        self.canvas.draw_idle()
