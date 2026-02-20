from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable


class HomePage(ttk.Frame):
    def __init__(
        self,
        parent,
        *,
        on_open_kalman: Callable[[], None],
        on_open_generator: Callable[[], None],
        on_open_step_response_generator: Callable[[], None],
        on_open_step_response_identification: Callable[[], None],
    ):
        super().__init__(parent, padding=24)
        self._setup_style()

        container = ttk.Frame(self, style="App.TFrame")
        container.pack(fill="both", expand=True)

        content = ttk.Frame(container, style="App.TFrame")
        content.pack(anchor="n", fill="x")
        content.columnconfigure(0, weight=1)

        title = ttk.Label(content, text="Ctrl Toolkit", style="Title.TLabel")
        title.grid(row=0, column=0, sticky="w")

        subtitle = ttk.Label(content, text="Choose a tool:", style="Subtitle.TLabel")
        subtitle.grid(row=1, column=0, sticky="w", pady=(6, 18))

        cards = ttk.Frame(content, style="App.TFrame")
        cards.grid(row=2, column=0, sticky="nsew")
        cards.columnconfigure(0, weight=1)

        self._tool_card(
            cards,
            row=0,
            title="Kalman Tuning",
            desc="Load a signal CSV, select steady + ramp spans, compute tuning, and overlay AOI Kalman.",
            button_text="Open Kalman Tuning",
            command=on_open_kalman,
        )

        self._tool_card(
            cards,
            row=1,
            title="Signal Generator",
            desc="Generate a ramp/hold signal with Gaussian noise and write signal.csv to the app directory.",
            button_text="Open Signal Generator",
            command=on_open_generator,
        )

        self._tool_card(
            cards,
            row=2,
            title="Step Response Generator",
            desc="Generate a step response from selected transfer functions.",
            button_text="Open Step Response Generator",
            command=on_open_step_response_generator,
        )

        self._tool_card(
            cards,
            row=3,
            title="Step Response Identification",
            desc="Tune a step response from selected transfer functions.",
            button_text="Open Step Response Identification",
            command=on_open_step_response_identification,
        )

        sep = ttk.Separator(content)
        sep.grid(row=3, column=0, sticky="ew", pady=18)

        footer = ttk.Label(
            content,
            text="More tools can be added here later (PID, filters, etc.)",
            style="Muted.TLabel",
        )
        footer.grid(row=4, column=0, sticky="w")

    def _setup_style(self) -> None:
        style = ttk.Style(self)
        try:
            style.theme_use("vista")
        except tk.TclError:
            style.theme_use("clam")

        self._bg = style.lookup("TFrame", "background") or "#F6F7FB"
        self._card_bg = "#FFFFFF"
        self._border = "#E3E6EF"
        self._muted = "#5C6470"

        style.configure("App.TFrame", background=self._bg)

        style.configure(
            "Title.TLabel",
            font=("Segoe UI", 20, "bold"),
            background=self._bg,
        )
        style.configure(
            "Subtitle.TLabel",
            font=("Segoe UI", 11),
            foreground=self._muted,
            background=self._bg,
        )
        style.configure(
            "Muted.TLabel",
            font=("Segoe UI", 10),
            foreground=self._muted,
            background=self._bg,
        )

        # Card surface + typography
        style.configure(
            "Card.TFrame",
            background=self._card_bg,
            bordercolor=self._border,
            relief="solid",
            borderwidth=1,
        )
        style.configure(
            "CardTitle.TLabel",
            font=("Segoe UI", 13, "bold"),
            background=self._card_bg,
        )
        style.configure(
            "CardBody.TLabel",
            font=("Segoe UI", 10),
            foreground="#2B2F36",
            background=self._card_bg,
        )

        style.configure(
            "Primary.TButton",
            padding=(12, 8),
        )

    def _tool_card(
        self,
        parent: ttk.Frame,
        *,
        row: int,
        title: str,
        desc: str,
        button_text: str,
        command: Callable[[], None],
    ) -> None:
        card = ttk.Frame(parent, style="Card.TFrame", padding=16)
        card.grid(row=row, column=0, sticky="ew", pady=(0 if row == 0 else 12, 0))
        card.columnconfigure(0, weight=1)

        ttl = ttk.Label(card, text=title, style="CardTitle.TLabel")
        ttl.grid(row=0, column=0, sticky="w")

        body = ttk.Label(card, text=desc, style="CardBody.TLabel", justify="left")
        body.grid(row=1, column=0, sticky="ew", pady=(6, 12))

        btn = ttk.Button(card, text=button_text, style="Primary.TButton", command=command)
        btn.grid(row=2, column=0, sticky="w")

        def _on_resize(_evt: tk.Event) -> None:
            wrap = max(320, card.winfo_width() - 32)
            body.configure(wraplength=wrap)

        card.bind("<Configure>", _on_resize)