from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Callable

import numpy as np

import matplotlib

matplotlib.use("TkAgg")
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from ctrl.models import RampHoldProfile
from ctrl.services import generate_signal_csv


class SignalGeneratorPage(ttk.Frame):
    def __init__(self, parent, *, on_back: Callable[[], None]):
        super().__init__(parent, padding=0)

        self._preview_job: str | None = None
        self._suppress_preview = False

        self._setup_style()


        # Header
        header = ttk.Frame(self, style="App.TFrame", padding=(16, 12))
        header.pack(side=tk.TOP, fill=tk.X)

        ttk.Button(header, text="← Back", command=on_back, style="Nav.TButton").pack(side=tk.LEFT)
        ttk.Label(header, text="Signal Generator", style="PageTitle.TLabel").pack(side=tk.LEFT, padx=12)

        ttk.Separator(self).pack(side=tk.TOP, fill=tk.X)


        # Body
        body = ttk.Frame(self, style="App.TFrame", padding=16)
        body.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        body.columnconfigure(0, weight=2, uniform="cols")  # form
        body.columnconfigure(1, weight=3, uniform="cols")  # preview
        body.rowconfigure(1, weight=1)  # preview expands


        # Vars
        self.out_filename = tk.StringVar(value="signal.csv")
        self.dt_ms = tk.StringVar(value="50")
        self.seconds = tk.StringVar(value="20")
        self.noise_amp = tk.StringVar(value="10.0")
        self.rng_seed = tk.StringVar(value="12345")
        self.time_unit_seconds = tk.BooleanVar(value=True)

        self.x_lo = tk.StringVar(value="0.0")
        self.x_hi = tk.StringVar(value="100.0")
        self.t_up = tk.StringVar(value="2000")
        self.t_hold_hi = tk.StringVar(value="4000")
        self.t_down = tk.StringVar(value="2000")
        self.t_hold_lo = tk.StringVar(value="4000")


        # Left column
        left = ttk.Frame(body, style="App.TFrame")
        left.grid(row=0, column=0, rowspan=2, sticky="nsew", padx=(0, 12))
        left.columnconfigure(0, weight=1)

        out_box = ttk.Frame(left, style="Card.TFrame", padding=14)
        out_box.grid(row=0, column=0, sticky="ew")
        out_box.columnconfigure(0, weight=0)
        out_box.columnconfigure(1, weight=0)
        out_box.columnconfigure(2, weight=0)
        out_box.columnconfigure(3, weight=1)

        ttk.Label(out_box, text="Output / Noise / Timing", style="SectionTitle.TLabel").grid(
            row=0, column=0, columnspan=4, sticky="w", pady=(0, 8)
        )

        r = 1
        r = self._add_full_row(out_box, r, "Output filename (app dir):", self.out_filename, width=30)

        r = self._add_pair_row(out_box, r, "DT_MS:", self.dt_ms, "SECONDS:", self.seconds)
        r = self._add_pair_row(out_box, r, "NOISE_AMP:", self.noise_amp, "RNG_SEED:", self.rng_seed)

        ttk.Checkbutton(
            out_box,
            text="Time column in seconds (unchecked = milliseconds)",
            variable=self.time_unit_seconds,
            command=lambda: self._schedule_preview(0),
        ).grid(row=r, column=0, columnspan=4, sticky="w", pady=(10, 0))

        prof_box = ttk.Frame(left, style="Card.TFrame", padding=14)
        prof_box.grid(row=1, column=0, sticky="ew", pady=(12, 0))
        prof_box.columnconfigure(0, weight=0)
        prof_box.columnconfigure(1, weight=0)
        prof_box.columnconfigure(2, weight=0)
        prof_box.columnconfigure(3, weight=1)

        ttk.Label(prof_box, text="Ramp/Hold Profile", style="SectionTitle.TLabel").grid(
            row=0, column=0, columnspan=4, sticky="w", pady=(0, 8)
        )

        rr = 1
        rr = self._add_pair_row(prof_box, rr, "X_LO:", self.x_lo, "X_HI:", self.x_hi)
        rr = self._add_pair_row(prof_box, rr, "T_UP_MS:", self.t_up, "T_HOLD_HI_MS:", self.t_hold_hi)
        rr = self._add_pair_row(prof_box, rr, "T_DOWN_MS:", self.t_down, "T_HOLD_LO_MS:", self.t_hold_lo)

        # Bottom controls
        controls = ttk.Frame(left, style="App.TFrame")
        controls.grid(row=2, column=0, sticky="ew", pady=(12, 0))
        controls.columnconfigure(2, weight=1)

        ttk.Button(controls, text="Refresh preview", command=self._on_preview).grid(row=0, column=0, sticky="w")

        ttk.Button(
            controls,
            text="Generate CSV",
            command=self._on_generate,
            style="Primary.TButton",
        ).grid(row=0, column=1, sticky="w", padx=(8, 0))

        self.status = ttk.Label(controls, text="", style="Muted.TLabel")
        self.status.grid(row=0, column=2, sticky="e")


        # Right column
        preview_card = ttk.Frame(body, style="Card.TFrame", padding=12)
        preview_card.grid(row=0, column=1, rowspan=2, sticky="nsew")
        preview_card.rowconfigure(1, weight=1)
        preview_card.columnconfigure(0, weight=1)

        ttk.Label(preview_card, text="Preview", style="SectionTitle.TLabel").grid(
            row=0, column=0, sticky="w", pady=(0, 8)
        )

        self._fig = Figure(dpi=100)
        self._ax = self._fig.add_subplot(1, 1, 1)
        self._apply_plot_style()

        self._canvas = FigureCanvasTkAgg(self._fig, master=preview_card)
        self._canvas.get_tk_widget().grid(row=1, column=0, sticky="nsew")

        def _trace(*_args):
            self._schedule_preview(200)

        for v in [
            self.out_filename, self.dt_ms, self.seconds, self.noise_amp, self.rng_seed,
            self.x_lo, self.x_hi, self.t_up, self.t_hold_hi, self.t_down, self.t_hold_lo,
        ]:
            v.trace_add("write", _trace)

        self._schedule_preview(0)

    def _setup_style(self) -> None:
        style = ttk.Style(self)
        try:
            style.theme_use("vista")
        except tk.TclError:
            style.theme_use("clam")

        bg = style.lookup("TFrame", "background") or "#F6F7FB"
        card_bg = "#FFFFFF"
        border = "#E3E6EF"
        muted = "#5C6470"

        style.configure("App.TFrame", background=bg)

        style.configure("PageTitle.TLabel", font=("Segoe UI", 16, "bold"), background=bg)
        style.configure("SectionTitle.TLabel", font=("Segoe UI", 12, "bold"), background=card_bg)
        style.configure("Muted.TLabel", font=("Segoe UI", 10), foreground=muted, background=bg)

        style.configure("Card.TFrame", background=card_bg, relief="solid", borderwidth=1, bordercolor=border)

        style.configure("Nav.TButton", padding=(10, 6))
        style.configure("Primary.TButton", padding=(12, 8))

        self._app_bg = bg
        self._card_bg = card_bg

    def _apply_plot_style(self) -> None:
        try:
            self._fig.patch.set_facecolor(self._card_bg)
        except Exception:
            pass

        self._ax.clear()
        self._ax.grid(True, alpha=0.25)
        self._ax.set_title("Generated signal preview")
        self._ax.set_xlabel("time")
        self._ax.set_ylabel("x")


    # Form helpers
    def _bind_preview_events(self, entry: ttk.Entry) -> None:
        entry.bind("<Return>", lambda _e: self._schedule_preview(0))
        entry.bind("<FocusOut>", lambda _e: self._schedule_preview(0))

    def _add_full_row(
        self, frame: ttk.Frame, row: int, label: str, var: tk.Variable, *, width: int = 28
    ) -> int:
        ttk.Label(frame, text=label, style="CardBody.TLabel").grid(
            row=row, column=0, sticky="w", padx=(0, 8), pady=4
        )
        e = ttk.Entry(frame, textvariable=var, width=width)
        e.grid(row=row, column=1, columnspan=3, sticky="w", pady=4)
        self._bind_preview_events(e)
        return row + 1

    def _add_pair_row(
        self,
        frame: ttk.Frame,
        row: int,
        label1: str,
        var1: tk.Variable,
        label2: str,
        var2: tk.Variable,
        *,
        width: int = 14,
    ) -> int:
        ttk.Label(frame, text=label1, style="CardBody.TLabel").grid(
            row=row, column=0, sticky="w", padx=(0, 8), pady=4
        )
        e1 = ttk.Entry(frame, textvariable=var1, width=width)
        e1.grid(row=row, column=1, sticky="w", pady=4)

        ttk.Label(frame, text=label2, style="CardBody.TLabel").grid(
            row=row, column=2, sticky="w", padx=(16, 8), pady=4
        )
        e2 = ttk.Entry(frame, textvariable=var2, width=width)
        e2.grid(row=row, column=3, sticky="w", pady=4)

        self._bind_preview_events(e1)
        self._bind_preview_events(e2)
        return row + 1

    def _schedule_preview(self, delay_ms: int = 200) -> None:
        if self._suppress_preview:
            return

        if self._preview_job is not None:
            try:
                self.after_cancel(self._preview_job)
            except Exception:
                pass
            self._preview_job = None

        self._preview_job = self.after(delay_ms, self._safe_preview)

    def _safe_preview(self) -> None:
        self._preview_job = None
        try:
            self._on_preview()
            self.status.configure(text="Preview updated")
        except Exception as e:
            # Don’t spam modal dialogs while typing—just show a gentle inline message.
            msg = str(e).strip() or "Invalid input"
            self.status.configure(text=f"Check inputs: {msg}")


    def _build_profile(self) -> RampHoldProfile:
        return RampHoldProfile(
            X_LO=float(self.x_lo.get()),
            X_HI=float(self.x_hi.get()),
            T_UP_MS=int(self.t_up.get()),
            T_HOLD_HI_MS=int(self.t_hold_hi.get()),
            T_DOWN_MS=int(self.t_down.get()),
            T_HOLD_LO_MS=int(self.t_hold_lo.get()),
        )

    @staticmethod
    def _ramp_hold_value(profile: RampHoldProfile, t_ms: int) -> float:
        period = profile.T_UP_MS + profile.T_HOLD_HI_MS + profile.T_DOWN_MS + profile.T_HOLD_LO_MS
        u = t_ms % period

        if u < profile.T_UP_MS:
            frac = u / max(profile.T_UP_MS, 1)
            return profile.X_LO + frac * (profile.X_HI - profile.X_LO)

        u -= profile.T_UP_MS
        if u < profile.T_HOLD_HI_MS:
            return profile.X_HI

        u -= profile.T_HOLD_HI_MS
        if u < profile.T_DOWN_MS:
            frac = u / max(profile.T_DOWN_MS, 1)
            return profile.X_HI - frac * (profile.X_HI - profile.X_LO)

        return profile.X_LO

    def _preview_series(self) -> tuple[np.ndarray, np.ndarray]:
        dt_ms = int(self.dt_ms.get())
        seconds = int(self.seconds.get())
        noise_amp = float(self.noise_amp.get())
        rng_seed = int(self.rng_seed.get())

        if dt_ms <= 0:
            raise ValueError("DT_MS must be > 0")
        if seconds <= 0:
            raise ValueError("SECONDS must be > 0")

        profile = self._build_profile()

        n = int((seconds * 1000) / dt_ms)
        if n <= 1:
            raise ValueError("SECONDS must be long enough for at least 2 samples.")

        t_ms = np.arange(n) * dt_ms
        t = (t_ms / 1000.0) if self.time_unit_seconds.get() else t_ms.astype(float)

        sigma = noise_amp / 3.0
        rng = np.random.default_rng(rng_seed)

        x_true = np.array([self._ramp_hold_value(profile, int(tm)) for tm in t_ms], dtype=float)
        x = x_true + rng.normal(0.0, sigma, size=n)
        return t, x


    # UI actions
    def _on_preview(self) -> None:
        t, x = self._preview_series()

        self._apply_plot_style()
        self._ax.plot(t, x, linewidth=2.0)

        self._ax.set_xlabel("time (s)" if self.time_unit_seconds.get() else "time (ms)")
        self._canvas.draw_idle()

    def _on_generate(self) -> None:
        try:
            profile = self._build_profile()

            out_path = generate_signal_csv(
                out_filename=self.out_filename.get().strip() or "signal.csv",
                dt_ms=int(self.dt_ms.get()),
                seconds=int(self.seconds.get()),
                profile=profile,
                noise_amp=float(self.noise_amp.get()),
                rng_seed=int(self.rng_seed.get()),
                time_unit_seconds=bool(self.time_unit_seconds.get()),
            )

            self.status.configure(text=f"Wrote: {out_path}")
            self._schedule_preview(0)
            messagebox.showinfo("Signal Generator", f"Wrote CSV:\n{out_path}")

        except Exception as e:
            messagebox.showerror("Generate error", str(e))