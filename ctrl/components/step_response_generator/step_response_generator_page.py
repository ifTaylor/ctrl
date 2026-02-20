from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Callable

import matplotlib

from ctrl.models import SOPDTUnderdampedParams, IPDTParams, FOPDTParams, ActuatorParams, StepSpec
from ctrl.services import export_step_csv, simulate_step_response

matplotlib.use("TkAgg")
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg




class StepResponsePage(ttk.Frame):
    def __init__(self, parent, *, on_back: Callable[[], None]):
        super().__init__(parent, padding=0)
        self._preview_job: str | None = None
        self._suppress_preview = False

        self._setup_style()

        # Header
        header = ttk.Frame(self, style="App.TFrame", padding=(16, 12))
        header.pack(side=tk.TOP, fill=tk.X)

        ttk.Button(header, text="← Back", command=on_back, style="Nav.TButton").pack(side=tk.LEFT)
        ttk.Label(header, text="Step Response Generator", style="PageTitle.TLabel").pack(side=tk.LEFT, padx=12)

        ttk.Separator(self).pack(side=tk.TOP, fill=tk.X)


        # Body
        body = ttk.Frame(self, style="App.TFrame", padding=16)
        body.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        body.columnconfigure(0, weight=2, uniform="cols")
        body.columnconfigure(1, weight=3, uniform="cols")
        body.rowconfigure(0, weight=1)

        left = ttk.Frame(body, style="App.TFrame")
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        left.columnconfigure(0, weight=1)

        right = ttk.Frame(body, style="App.TFrame")
        right.grid(row=0, column=1, sticky="nsew")
        right.rowconfigure(1, weight=1)
        right.columnconfigure(0, weight=1)


        # Vars
        self.out_filename = tk.StringVar(value="step_response.csv")
        self.time_unit_seconds = tk.BooleanVar(value=True)

        # Step spec
        self.dt_s = tk.StringVar(value="0.05")
        self.duration_s = tk.StringVar(value="5.0")
        self.t_step_s = tk.StringVar(value="1.0")
        self.cv0 = tk.StringVar(value="0.0")
        self.cv_step = tk.StringVar(value="10.0")

        # Model selection
        self.model = tk.StringVar(value="FOPDT")

        # Actuator
        self.pv0 = tk.StringVar(value="0.0")
        self.pv_min = tk.StringVar(value="0")
        self.pv_max = tk.StringVar(value="9")
        self.rate_limit = tk.StringVar(value="0.0")
        self.act_tau = tk.StringVar(value="0.0")

        # FOPDT params
        self.f_k = tk.StringVar(value="1.0")
        self.f_tau = tk.StringVar(value="0.3")
        self.f_theta = tk.StringVar(value="0.2")

        # IPDT params
        self.i_k = tk.StringVar(value="0.4")
        self.i_theta = tk.StringVar(value="0.3")
        self.i_leak_tau = tk.StringVar(value="0.0")

        # SOPDT underdamped params
        self.s_k = tk.StringVar(value="1.0")
        self.s_zeta = tk.StringVar(value="0.45")
        self.s_wn = tk.StringVar(value="6.0")
        self.s_theta = tk.StringVar(value="0.3")


        # Left column: Cards
        export_card, rr = self._card(left, "Export")
        self._card_pair_grid(export_card)

        rr = self._add_full_row(export_card, rr, "CSV filename (app dir):", self.out_filename, width=28)
        ttk.Checkbutton(
            export_card,
            text="Time in seconds (unchecked = ms)",
            variable=self.time_unit_seconds,
            command=lambda: self._schedule_preview(0),
        ).grid(row=rr, column=0, columnspan=4, sticky="w", pady=(8, 0))

        step_card, rr = self._card(left, "CV Command", pady=(12, 0))
        self._card_pair_grid(step_card)
        rr = self._add_pair_row(step_card, rr, "dt (s):", self.dt_s, "duration (s):", self.duration_s)
        rr = self._add_pair_row(step_card, rr, "t_step (s):", self.t_step_s, "CV0:", self.cv0)
        rr = self._add_full_row(step_card, rr, "CV_STEP:", self.cv_step, width=14)

        act_card, rr = self._card(left, "Actuator", pady=(12, 0))
        self._card_pair_grid(act_card)
        rr = self._add_pair_row(act_card, rr, "PV0:", self.pv0, "PV_MIN:", self.pv_min)
        rr = self._add_pair_row(act_card, rr, "PV_MAX:", self.pv_max, "Rate limit (CV/s):", self.rate_limit)
        rr = self._add_full_row(act_card, rr, "Actuator tau (s):", self.act_tau, width=14)

        model_card, rr = self._card(left, "Transfer Function", pady=(12, 0))
        self._card_pair_grid(model_card)

        ttk.Label(model_card, text="Select function:", style="CardBody.TLabel").grid(
            row=rr, column=0, sticky="w", padx=(0, 8), pady=4
        )
        cmb = ttk.Combobox(
            model_card,
            textvariable=self.model,
            state="readonly",
            values=["FOPDT", "IPDT", "SOPDT_UNDERDAMPED"],
            width=18,
        )
        cmb.grid(row=rr, column=1, sticky="w", pady=4)
        cmb.bind("<<ComboboxSelected>>", lambda _e: self._on_model_changed())

        rr += 1

        # Param subframes
        self._fopdt_frame = ttk.Frame(model_card)
        self._ipdt_frame = ttk.Frame(model_card)
        self._sopdt_frame = ttk.Frame(model_card)

        for f in (self._fopdt_frame, self._ipdt_frame, self._sopdt_frame):
            f.grid(row=rr, column=0, columnspan=4, sticky="ew", pady=(8, 0))
            self._card_pair_grid(f)

        # FOPDT
        rrr = 0
        rrr = self._add_pair_row(self._fopdt_frame, rrr, "K:", self.f_k, "tau (s):", self.f_tau)
        rrr = self._add_full_row(self._fopdt_frame, rrr, "theta (s):", self.f_theta, width=14)

        # IPDT
        rrr = 0
        rrr = self._add_pair_row(self._ipdt_frame, rrr, "K:", self.i_k, "theta (s):", self.i_theta)
        rrr = self._add_full_row(self._ipdt_frame, rrr, "leak_tau (s) (0=pure):", self.i_leak_tau, width=14)

        # SOPDT underdamped
        rrr = 0
        rrr = self._add_pair_row(self._sopdt_frame, rrr, "K:", self.s_k, "zeta:", self.s_zeta)
        rrr = self._add_pair_row(self._sopdt_frame, rrr, "wn (rad/s):", self.s_wn, "theta (s):", self.s_theta)

        # Bottom actions
        actions = ttk.Frame(left, style="App.TFrame")
        actions.grid(row=99, column=0, sticky="ew", pady=(12, 0))
        actions.columnconfigure(2, weight=1)

        ttk.Button(actions, text="Refresh preview", command=self._on_preview).grid(row=0, column=0, sticky="w")
        ttk.Button(actions, text="Export CSV", command=self._on_export, style="Primary.TButton").grid(
            row=0, column=1, sticky="w", padx=(8, 0)
        )

        self.status = ttk.Label(actions, text="", style="Muted.TLabel")
        self.status.grid(row=0, column=2, sticky="e")


        # Right column
        plot_card = ttk.Frame(right, style="Card.TFrame", padding=12)
        plot_card.grid(row=1, column=0, sticky="nsew")
        plot_card.rowconfigure(1, weight=1)
        plot_card.columnconfigure(0, weight=1)

        ttk.Label(plot_card, text="Preview", style="SectionTitle.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 8))

        self._fig = Figure(dpi=100)
        self._ax = self._fig.add_subplot(1, 1, 1)
        self._apply_plot_style()

        self._canvas = FigureCanvasTkAgg(self._fig, master=plot_card)
        self._canvas.get_tk_widget().grid(row=1, column=0, sticky="nsew")

        def trace_all(*_):
            self._schedule_preview(200)

        for v in [
            self.out_filename, self.dt_s, self.duration_s, self.t_step_s, self.cv0, self.cv_step,
            self.pv0, self.pv_min, self.pv_max, self.rate_limit, self.act_tau,
            self.f_k, self.f_tau, self.f_theta,
            self.i_k, self.i_theta, self.i_leak_tau,
            self.s_k, self.s_zeta, self.s_wn, self.s_theta,
        ]:
            v.trace_add("write", trace_all)

        self._on_model_changed()
        self._schedule_preview(0)

    # Styling
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
        style.configure("CardBody.TLabel", font=("Segoe UI", 10), background=card_bg)
        style.configure("Muted.TLabel", font=("Segoe UI", 10), foreground=muted, background=bg)

        style.configure("Card.TFrame", background=card_bg, relief="solid", borderwidth=1, bordercolor=border)

        style.configure("Nav.TButton", padding=(10, 6))
        style.configure("Primary.TButton", padding=(12, 8))

        self._card_bg = card_bg


    # UI building helpers
    def _card(self, parent: ttk.Frame, title: str, *, pady=(0, 0)) -> tuple[ttk.Frame, int]:
        card = ttk.Frame(parent, style="Card.TFrame", padding=14)
        card.grid(sticky="ew", pady=pady)
        ttk.Label(card, text=title, style="SectionTitle.TLabel").grid(
            row=0, column=0, columnspan=4, sticky="w", pady=(0, 8)
        )
        return card, 1

    @staticmethod
    def _card_pair_grid(frame: ttk.Frame) -> None:
        # 4 columns: label/entry + label/entry
        frame.columnconfigure(0, weight=0)
        frame.columnconfigure(1, weight=0)
        frame.columnconfigure(2, weight=0)
        frame.columnconfigure(3, weight=1)

    def _bind_preview_events(self, entry: ttk.Entry) -> None:
        entry.bind("<Return>", lambda _e: self._schedule_preview(0))
        entry.bind("<FocusOut>", lambda _e: self._schedule_preview(0))

    def _add_full_row(self, frame: ttk.Frame, row: int, label: str, var: tk.Variable, *, width: int = 16) -> int:
        ttk.Label(frame, text=label, style="CardBody.TLabel").grid(row=row, column=0, sticky="w", padx=(0, 8), pady=4)
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
        ttk.Label(frame, text=label1, style="CardBody.TLabel").grid(row=row, column=0, sticky="w", padx=(0, 8), pady=4)
        e1 = ttk.Entry(frame, textvariable=var1, width=width)
        e1.grid(row=row, column=1, sticky="w", pady=4)

        ttk.Label(frame, text=label2, style="CardBody.TLabel").grid(row=row, column=2, sticky="w", padx=(16, 8), pady=4)
        e2 = ttk.Entry(frame, textvariable=var2, width=width)
        e2.grid(row=row, column=3, sticky="w", pady=4)

        self._bind_preview_events(e1)
        self._bind_preview_events(e2)
        return row + 1


    # Model swapping
    def _on_model_changed(self) -> None:
        m = self.model.get()
        self._fopdt_frame.grid_remove()
        self._ipdt_frame.grid_remove()
        self._sopdt_frame.grid_remove()

        if m == "FOPDT":
            self._fopdt_frame.grid()
        elif m == "IPDT":
            self._ipdt_frame.grid()
        elif m == "SOPDT_UNDERDAMPED":
            self._sopdt_frame.grid()

        self._schedule_preview(0)


    # Debounced preview
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
            msg = str(e).strip() or "Invalid input"
            self.status.configure(text=f"Check inputs: {msg}")


    # Build model/spec
    def _build_spec(self) -> StepSpec:
        dt = float(self.dt_s.get())
        dur = float(self.duration_s.get())
        if dt <= 0:
            raise ValueError("dt (s) must be > 0")
        if dur <= 0:
            raise ValueError("duration (s) must be > 0")
        return StepSpec(
            dt_s=dt,
            duration_s=dur,
            t_step_s=float(self.t_step_s.get()),
            cv0=float(self.cv0.get()),
            cv_step=float(self.cv_step.get()),
        )

    def _build_actuator(self) -> ActuatorParams:
        return ActuatorParams(
            pv0=float(self.pv0.get()),
            pv_min=float(self.pv_min.get()),
            pv_max=float(self.pv_max.get()),
            rate_limit=float(self.rate_limit.get()),
            tau_s=float(self.act_tau.get()),
        )

    def _simulate(self):
        spec = self._build_spec()
        actuator = self._build_actuator()
        m = self.model.get()

        if m == "FOPDT":
            p = FOPDTParams(
                K=float(self.f_k.get()),
                tau_s=float(self.f_tau.get()),
                theta_s=float(self.f_theta.get()),
            )
            return simulate_step_response(spec=spec, actuator=actuator, model="FOPDT", fopdt=p)

        if m == "IPDT":
            i = IPDTParams(
                K=float(self.i_k.get()),
                theta_s=float(self.i_theta.get()),
                leak_tau_s=float(self.i_leak_tau.get()),
            )
            return simulate_step_response(spec=spec, actuator=actuator, model="IPDT", ipdt=i)

        if m == "SOPDT_UNDERDAMPED":
            p = SOPDTUnderdampedParams(
                K=float(self.s_k.get()),
                zeta=float(self.s_zeta.get()),
                wn=float(self.s_wn.get()),
                theta_s=float(self.s_theta.get()),
            )
            return simulate_step_response(spec=spec, actuator=actuator, model="SOPDT_UNDERDAMPED", sopdt=p)

        raise ValueError(f"Unknown model: {m}")


    # Plot + actions
    def _apply_plot_style(self) -> None:
        try:
            self._fig.patch.set_facecolor(self._card_bg)
        except Exception:
            pass
        self._ax.clear()
        self._ax.grid(True, alpha=0.25)
        self._ax.set_title("Step Response Preview")
        self._ax.set_xlabel("time (s)")
        self._ax.set_ylabel("Value")

    def _on_preview(self) -> None:
        t, cv_cmd, pv, cv_eff = self._simulate()

        self._apply_plot_style()
        self._ax.plot(t, pv, linewidth=2.2, label="PV")
        self._ax.plot(t, cv_cmd, "--", linewidth=1.8, label="CV_cmd")
        self._ax.set_title(f"Step Response Preview — {self.model.get()}")
        self._ax.legend(loc="best")
        self._canvas.draw_idle()

    def _on_export(self) -> None:
        try:
            t, cv_cmd, pv, _cv_eff = self._simulate()
            out_name = (self.out_filename.get().strip() or "step_response.csv")
            out_path = export_step_csv(
                out_filename=out_name,
                t=t,
                cv_cmd=cv_cmd,
                pv=pv,
                time_unit_seconds=bool(self.time_unit_seconds.get()),
            )
            self.status.configure(text=f"Wrote: {out_path}")
            messagebox.showinfo("Export", f"Wrote CSV:\n{out_path}")
        except Exception as e:
            messagebox.showerror("Export error", str(e))