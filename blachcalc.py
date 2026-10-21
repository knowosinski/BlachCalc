import os
import sqlite3
import tkinter as tk
from copy import deepcopy
from datetime import datetime
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Any

from PIL import Image, ImageTk, UnidentifiedImageError

from calculator import calculate_quote, parse_decimal, parse_duration
from exports import export_estimate_csv, export_estimate_pdf
from app_paths import offer_export_directory, resource_path
from quote_domain import (
    calculate_item_line_amounts,
    format_pln,
    line_totals,
)
from storage import (
    ADDRESS_FIELDS,
    Storage,
    format_postal_address,
    parse_polish_address,
    validate_postal_address,
)


BACKGROUND = "#F2F5F9"
WHITE = "#FFFFFF"
INK = "#172B4D"
MUTED = "#64748B"
NAVY = "#173B63"
NAVY_DARK = "#102A47"
ACCENT = NAVY
ACCENT_DARK = NAVY_DARK
BRAND_RED = "#ED1B24"
GREEN = "#18794E"
BORDER = "#DCE4EE"
PALE_RED = "#FBECEE"
LOGIN_ENABLED = False
MAX_PREVIEW_IMAGE_BYTES = 10 * 1024 * 1024
OFFER_EXPORT_DIRECTORY = offer_export_directory()


class BlachCalcApp(tk.Tk):
    def __init__(self, storage: Storage) -> None:
        super().__init__()
        self.storage = storage
        self.title("Izo-Technika | BlachCalc — Wyceny CNC")
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        self.geometry(f"{min(1260, screen_width - 40)}x{min(900, screen_height - 80)}")
        self.minsize(min(900, screen_width - 40), min(620, screen_height - 80))
        self.configure(bg=BACKGROUND)
        icon_path = resource_path("BlachCalc.ico")
        if icon_path.is_file():
            self.iconbitmap(str(icon_path))
        self.user_id: int | None = None
        self.username = ""
        self._configure_styles()
        if LOGIN_ENABLED:
            self.show_login()
        else:
            user_id, username = self.storage.get_desktop_user()
            self.show_dashboard(user_id, username)

    def _configure_styles(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure(".", font=("Segoe UI", 10), foreground=INK)
        style.configure("TFrame", background=BACKGROUND)
        style.configure("Card.TFrame", background=WHITE)
        style.configure("TLabel", background=BACKGROUND, foreground=INK)
        style.configure("Card.TLabel", background=WHITE, foreground=INK)
        style.configure("Muted.TLabel", background=BACKGROUND, foreground=MUTED)
        style.configure("CardMuted.TLabel", background=WHITE, foreground=MUTED)
        style.configure("Title.TLabel", font=("Segoe UI", 25, "bold"), foreground=INK)
        style.configure("Subtitle.TLabel", font=("Segoe UI", 10), foreground=MUTED)
        style.configure("CardTitle.TLabel", background=WHITE, font=("Segoe UI", 12, "bold"))
        style.configure("Total.TLabel", background=WHITE, foreground=ACCENT, font=("Segoe UI", 19, "bold"))
        style.configure("TButton", padding=(13, 8), background=WHITE, foreground=INK, borderwidth=1, relief="flat")
        style.map(
            "TButton",
            background=[("pressed", "#E7EDF5"), ("active", "#F6F8FB"), ("disabled", "#F4F6F8")],
            foreground=[("disabled", "#9AA6B5")],
            bordercolor=[("focus", ACCENT), ("!focus", BORDER)],
        )
        style.configure(
            "Primary.TButton",
            padding=(16, 9),
            background=ACCENT,
            foreground=WHITE,
            borderwidth=0,
            relief="flat",
            font=("Segoe UI", 10, "bold"),
        )
        style.map(
            "Primary.TButton",
            background=[("pressed", NAVY_DARK), ("active", ACCENT_DARK), ("disabled", "#A7B5C6")],
            foreground=[("disabled", WHITE)],
        )
        style.configure("Danger.TButton", foreground="#B42332", background=WHITE)
        style.map("Danger.TButton", foreground=[("active", "#8F1D29")], background=[("active", "#FFF4F4")])
        style.configure("Quiet.TButton", padding=(9, 6), background=BACKGROUND, foreground=MUTED, borderwidth=0)
        style.map("Quiet.TButton", foreground=[("active", ACCENT)], background=[("active", "#E8EEF5")])
        style.configure(
            "Nav.TButton",
            padding=(13, 10),
            background=WHITE,
            foreground="#42536B",
            borderwidth=0,
            relief="flat",
            anchor="w",
            font=("Segoe UI", 10, "bold"),
        )
        style.map(
            "Nav.TButton",
            background=[("active", "#F1F5F9")],
            foreground=[("active", ACCENT)],
        )
        style.configure(
            "NavActive.TButton",
            padding=(13, 10),
            background="#EAF1F8",
            foreground=ACCENT,
            borderwidth=0,
            relief="flat",
            anchor="w",
            font=("Segoe UI", 10, "bold"),
        )
        style.map("NavActive.TButton", background=[("active", "#E1EAF4")])
        style.configure(
            "TEntry",
            padding=(10, 8),
            fieldbackground=WHITE,
            foreground=INK,
            insertcolor=INK,
            bordercolor=BORDER,
            lightcolor=BORDER,
            darkcolor=BORDER,
            relief="flat",
        )
        style.map(
            "TEntry",
            bordercolor=[("focus", ACCENT), ("!focus", BORDER)],
            lightcolor=[("focus", ACCENT), ("!focus", BORDER)],
            darkcolor=[("focus", ACCENT), ("!focus", BORDER)],
        )
        style.configure(
            "TCombobox",
            padding=(10, 7),
            fieldbackground=WHITE,
            foreground=INK,
            bordercolor=BORDER,
            lightcolor=BORDER,
            darkcolor=BORDER,
            arrowsize=13,
        )
        style.map(
            "TCombobox",
            fieldbackground=[("readonly", WHITE), ("disabled", "#F4F6F8")],
            foreground=[("disabled", "#9AA6B5")],
            bordercolor=[("focus", ACCENT), ("!focus", BORDER)],
        )
        style.configure(
            "TRadiobutton",
            background=WHITE,
            foreground=INK,
            padding=(4, 3),
            font=("Segoe UI", 9),
        )
        style.map("TRadiobutton", foreground=[("selected", ACCENT), ("active", INK)])
        style.configure(
            "Treeview",
            rowheight=36,
            font=("Segoe UI", 9),
            background=WHITE,
            fieldbackground=WHITE,
            foreground=INK,
            borderwidth=0,
            relief="flat",
        )
        style.configure(
            "Treeview.Heading",
            font=("Segoe UI", 9, "bold"),
            background="#EAF0F6",
            foreground="#344B68",
            padding=(10, 10),
            relief="flat",
            borderwidth=0,
        )
        style.map(
            "Treeview.Heading",
            background=[("active", "#DFE8F2")],
            foreground=[("active", INK)],
        )
        style.map(
            "Treeview",
            background=[("selected", "#DCE9F7")],
            foreground=[("selected", INK)],
        )
        style.configure(
            "Vertical.TScrollbar",
            background="#E2E8F0",
            troughcolor=BACKGROUND,
            bordercolor=BACKGROUND,
            arrowcolor=MUTED,
            relief="flat",
            width=12,
        )
        style.map("Vertical.TScrollbar", background=[("active", "#CBD5E1")])
        style.configure("TNotebook", background=BACKGROUND, borderwidth=0, tabmargins=(0, 0, 0, 0))
        style.configure(
            "TNotebook.Tab",
            padding=(20, 12),
            font=("Segoe UI", 9, "bold"),
            background="#E8EDF3",
            foreground=MUTED,
            borderwidth=0,
        )
        style.map(
            "TNotebook.Tab",
            background=[("selected", WHITE), ("active", "#E1E8F0")],
            foreground=[("selected", ACCENT), ("active", INK)],
            expand=[("selected", (0, 0, 0, 2))],
        )

    def _clear(self) -> None:
        for child in self.winfo_children():
            child.destroy()

    def show_login(self) -> None:
        self.user_id = None
        self._clear()
        LoginView(self, self.storage).pack(expand=True, fill="both")

    def show_dashboard(self, user_id: int, username: str) -> None:
        self.user_id = user_id
        self.username = username
        self._clear()
        DashboardView(self, self.storage, user_id, username).pack(fill="both", expand=True)


class LoginView(ttk.Frame):
    def __init__(self, app: BlachCalcApp, storage: Storage) -> None:
        super().__init__(app, padding=24)
        self.app = app
        self.storage = storage
        self.register_mode = False
        self.username_var = tk.StringVar()
        self.password_var = tk.StringVar()
        self.confirm_var = tk.StringVar()

        stage = tk.Frame(self, bg=BACKGROUND)
        stage.place(relx=0.5, rely=0.48, anchor="center")
        tk.Frame(stage, bg=ACCENT, width=6).pack(side="left", fill="y")
        card = tk.Frame(stage, bg=WHITE, padx=42, pady=38, highlightthickness=1, highlightbackground=BORDER)
        card.pack(side="left")
        mark = tk.Frame(card, bg=ACCENT, width=42, height=42)
        mark.pack(anchor="w")
        mark.pack_propagate(False)
        tk.Label(mark, text="B", bg=ACCENT, fg=WHITE, font=("Segoe UI", 22, "bold")).pack(expand=True)
        tk.Label(card, text="BlachCalc", bg=WHITE, fg=INK, font=("Segoe UI", 27, "bold")).pack(anchor="w", pady=(15, 1))
        tk.Label(card, text="KALKULACJE CNC  /  SYSTEM WYCEN", bg=WHITE, fg=MUTED, font=("Segoe UI", 9, "bold")).pack(anchor="w")
        tk.Frame(card, bg=ACCENT, height=3, width=54).pack(anchor="w", pady=(18, 20))
        self.form = tk.Frame(card, bg=WHITE)
        self.form.pack(fill="x")
        self._render_form()

    def _render_form(self) -> None:
        for child in self.form.winfo_children():
            child.destroy()
        title = "Utwórz konto" if self.register_mode else "Witaj ponownie"
        subtitle = "Skonfiguruj dostęp do lokalnych wycen." if self.register_mode else "Zaloguj się, aby kontynuować."
        tk.Label(self.form, text=title, bg=WHITE, fg=INK, font=("Segoe UI", 16, "bold")).pack(anchor="w")
        tk.Label(self.form, text=subtitle, bg=WHITE, fg=MUTED, font=("Segoe UI", 9)).pack(anchor="w", pady=(2, 16))
        self._entry_row("Nazwa użytkownika", self.username_var, None)
        self._entry_row("Hasło", self.password_var, "•")
        if self.register_mode:
            self._entry_row("Powtórz hasło", self.confirm_var, "•")
        ttk.Button(
            self.form,
            text="Utwórz konto" if self.register_mode else "Zaloguj się",
            style="Primary.TButton",
            command=self._submit,
        ).pack(fill="x", pady=(9, 8))
        ttk.Button(
            self.form,
            text="Mam już konto" if self.register_mode else "Utwórz konto",
            command=self._toggle_mode,
        ).pack(fill="x")
        tk.Label(
            self.form,
            text="Dane są przechowywane lokalnie na tym komputerze.",
            bg=WHITE,
            fg=MUTED,
            font=("Segoe UI", 8),
        ).pack(anchor="w", pady=(15, 0))

    def _entry_row(self, label: str, variable: tk.StringVar, show: str | None) -> None:
        tk.Label(self.form, text=label, bg=WHITE, fg=INK, font=("Segoe UI", 9, "bold")).pack(anchor="w")
        entry = ttk.Entry(self.form, textvariable=variable, show=show, width=42)
        entry.pack(fill="x", pady=(4, 12), ipady=4)
        if label == "Nazwa użytkownika":
            entry.focus_set()
        if label == "Hasło":
            entry.bind("<Return>", lambda _event: self._submit())

    def _toggle_mode(self) -> None:
        self.register_mode = not self.register_mode
        self.confirm_var.set("")
        self._render_form()

    def _submit(self) -> None:
        username = self.username_var.get()
        password = self.password_var.get()
        try:
            if self.register_mode:
                if password != self.confirm_var.get():
                    raise ValueError("Podane hasła nie są takie same.")
                user_id = self.storage.register(username, password)
                clean_username = username.strip()
            else:
                authenticated = self.storage.authenticate(username, password)
                if authenticated is None:
                    messagebox.showerror("Logowanie", "Nieprawidłowa nazwa użytkownika lub hasło.", parent=self)
                    return
                user_id, clean_username = authenticated
        except ValueError as error:
            messagebox.showerror("Dane konta", str(error), parent=self)
            return
        except sqlite3.Error as error:
            messagebox.showerror("Błąd bazy danych", f"Nie udało się obsłużyć konta:\n{error}", parent=self)
            return
        self.app.show_dashboard(user_id, clean_username)


class DashboardView(ttk.Frame):
    def __init__(self, app: BlachCalcApp, storage: Storage, user_id: int, username: str) -> None:
        super().__init__(app, padding=(26, 18))
        self.app = app
        self.storage = storage
        self.user_id = user_id
        self.username = username
        self.settings = storage.get_settings(user_id)
        self.draft_items: list[dict[str, Any]] = []
        self.quote_layout_compact = False
        self.editing_draft_index: int | None = None
        self.editing_estimate_id: int | None = None
        self.legacy_pricing_mode = "itemized"
        self.summary_estimate: dict[str, Any] | None = None
        self.logo_image: tk.PhotoImage | None = None
        self.preview_logo_image: tk.PhotoImage | None = None
        self.preview_page_images: list[ImageTk.PhotoImage] = []
        self._quote_history_vars: dict[str, tk.StringVar] = {}
        self._quote_undo_stack: list[dict[str, Any]] = []
        self._quote_redo_stack: list[dict[str, Any]] = []
        self._quote_history_suspended = 0
        self._quote_history_snapshot: dict[str, Any] | None = None
        self.item_photo_data: bytes | None = None
        self.item_photo_name = ""
        self.item_photo_thumbnail: ImageTk.PhotoImage | None = None
        self._build()
        self.refresh_history()
        self.refresh_customers()

    def _build(self) -> None:
        header = tk.Frame(self, bg=WHITE, padx=18, pady=13, highlightthickness=1, highlightbackground=BORDER)
        header.pack(fill="x", pady=(0, 16))
        brand = tk.Frame(header, bg=WHITE)
        brand.pack(side="left", fill="y")
        self.brand_badge = tk.Frame(brand, bg=WHITE)
        self.brand_badge.pack(side="left")
        self._refresh_brand_badge()
        title = tk.Frame(brand, bg=WHITE)
        title.pack(side="left", padx=(11, 0))
        tk.Label(title, text="BlachCalc", bg=WHITE, fg=INK, font=("Segoe UI", 22, "bold")).pack(anchor="w")
        tk.Label(
            title,
            text=f"{self.settings.get('brand_tagline', 'Usługi CNC · Laser · Prasa')}  |  Izo-Technika",
            bg=WHITE,
            fg=MUTED,
            font=("Segoe UI", 9),
        ).pack(anchor="w", pady=(0, 0))
        if LOGIN_ENABLED:
            ttk.Label(header, text=f"Zalogowano: {self.username}", style="Subtitle.TLabel").pack(side="right", padx=(12, 0))
        ttk.Button(header, text="⚙  Ustawienia", command=self.open_settings).pack(side="right", padx=(8, 0))
        exit_action = self.app.show_login if LOGIN_ENABLED else self.app.destroy
        exit_label = "Wyloguj" if LOGIN_ENABLED else "Zamknij"
        ttk.Button(header, text=exit_label, style="Quiet.TButton", command=exit_action).pack(side="right")
        tk.Frame(self, bg=BRAND_RED, height=3).pack(fill="x", pady=(0, 8))

        workspace = tk.Frame(self, bg=BACKGROUND)
        workspace.pack(fill="both", expand=True)
        self.sidebar = tk.Frame(
            workspace,
            bg=WHITE,
            width=320,
            highlightthickness=1,
            highlightbackground=BORDER,
        )
        self.sidebar.pack(side="left", fill="y", padx=(0, 14))
        self.sidebar.pack_propagate(False)
        self.bind("<Configure>", self._resize_workspace, add="+")
        self._build_navigation()
        self.main_content = tk.Frame(workspace, bg=BACKGROUND)
        self.main_content.pack(side="left", fill="both", expand=True)
        self.quote_tab = tk.Frame(self.main_content, bg=BACKGROUND, padx=4, pady=12)
        quote_form_container = tk.Frame(self.quote_tab, bg=BACKGROUND)
        quote_form_container.pack(fill="both", expand=True)
        self.quote_canvas = tk.Canvas(
            quote_form_container,
            bg=BACKGROUND,
            highlightthickness=0,
            borderwidth=0,
        )
        quote_scroll = ttk.Scrollbar(
            quote_form_container,
            orient="vertical",
            command=self.quote_canvas.yview,
        )
        self.quote_canvas.configure(yscrollcommand=quote_scroll.set)
        self.quote_canvas.pack(side="left", fill="both", expand=True)
        quote_scroll.pack(side="right", fill="y")
        self.quote_form = tk.Frame(self.quote_canvas, bg=BACKGROUND)
        self.quote_form_window = self.quote_canvas.create_window(
            (0, 0),
            window=self.quote_form,
            anchor="nw",
        )
        self.quote_form.bind(
            "<Configure>",
            lambda _event: self.quote_canvas.configure(
                scrollregion=self.quote_canvas.bbox("all")
            ),
        )
        self.quote_canvas.bind(
            "<Configure>",
            self._resize_quote_form,
        )
        quote_action_bar = tk.Frame(
            self.quote_tab,
            bg=WHITE,
            padx=18,
            pady=10,
            highlightthickness=1,
            highlightbackground=BORDER,
        )
        quote_action_bar.pack(side="bottom", fill="x", pady=(8, 0))
        tk.Label(
            quote_action_bar,
            text="Wycena zostanie zapisana w lokalnej bazie",
            bg=WHITE,
            fg=MUTED,
            font=("Segoe UI", 9),
        ).pack(side="left", fill="x", expand=True, anchor="w")
        self.save_estimate_button = ttk.Button(
            quote_action_bar,
            text="Zatwierdź wycenę",
            style="Primary.TButton",
            command=self.save_estimate,
        )
        self.save_estimate_button.pack(side="right")
        self.history_tab = tk.Frame(self.main_content, bg=BACKGROUND, padx=4, pady=12)
        self.customers_tab = tk.Frame(self.main_content, bg=BACKGROUND, padx=4, pady=12)
        self.summary_tab = tk.Frame(self.main_content, bg=BACKGROUND, padx=4, pady=12)
        self._build_quote_tab()
        self._build_history_tab()
        self._build_customers_tab()
        self._build_summary_tab()
        self.bind_all("<MouseWheel>", self._on_mousewheel, add="+")
        self.bind_all("<Return>", self._focus_next_entry, add="+")
        self._bind_quote_history_shortcuts(self.quote_tab)
        self._bind_quote_history_shortcuts(self.sidebar)
        self._initialize_quote_history()
        self._show_page("quote")

    def _build_navigation(self) -> None:
        navigation = tk.Frame(self.sidebar, bg=WHITE, padx=14, pady=16)
        navigation.pack(fill="x")
        tk.Label(
            navigation,
            text="NAWIGACJA",
            bg=WHITE,
            fg=MUTED,
            font=("Segoe UI", 8, "bold"),
        ).pack(anchor="w", padx=(10, 0), pady=(0, 8))
        self.navigation_buttons: dict[str, ttk.Button] = {}
        for key, label in (
            ("quote", "＋   Nowa wycena"),
            ("history", "▤   Historia wycen"),
            ("customers", "♙   Kartoteka klientów"),
            ("summary", "▧   Podsumowanie oferty"),
        ):
            button = ttk.Button(
                navigation,
                text=label,
                style="Nav.TButton",
                command=lambda page=key: self._show_page(page),
            )
            button.pack(fill="x", pady=2)
            self.navigation_buttons[key] = button
            if key == "summary":
                button.configure(state="disabled")
        tk.Frame(self.sidebar, bg=BORDER, height=1).pack(fill="x", padx=14)
        tk.Label(
            self.sidebar,
            text="BIEŻĄCE ZAMÓWIENIE",
            bg=WHITE,
            fg=INK,
            font=("Segoe UI", 9, "bold"),
        ).pack(anchor="w", padx=24, pady=(15, 8))
        self.sidebar_order_var = tk.StringVar(value="Zleceniodawca: —\nNr zamówienia: —")
        tk.Label(
            self.sidebar,
            textvariable=self.sidebar_order_var,
            bg=WHITE,
            fg=MUTED,
            font=("Segoe UI", 9),
            justify="left",
            anchor="w",
            wraplength=280,
        ).pack(fill="x", padx=24, pady=(0, 10))

    def _show_page(self, page: str) -> None:
        pages = {
            "quote": self.quote_tab,
            "history": self.history_tab,
            "customers": self.customers_tab,
            "summary": self.summary_tab,
        }
        if page == "summary" and self.summary_estimate is None:
            return
        selected = pages[page]
        for frame in pages.values():
            frame.pack_forget()
        selected.pack(fill="both", expand=True)
        for key, button in self.navigation_buttons.items():
            button.configure(style="NavActive.TButton" if key == page else "Nav.TButton")

    def _on_mousewheel(self, event: tk.Event) -> str | None:
        widget = self.winfo_containing(event.x_root, event.y_root)
        scrollable_types = (tk.Canvas, tk.Listbox, tk.Text, ttk.Treeview)
        while widget is not None and widget is not self:
            if isinstance(widget, scrollable_types):
                if event.state & 0x0008:
                    if hasattr(widget, "xview"):
                        current_view = widget.xview()
                        if len(current_view) == 2 and current_view[1] - current_view[0] < 1:
                            widget.xview_scroll(
                                -1 if event.delta > 0 else 1,
                                "units",
                            )
                    return "break"
                if hasattr(widget, "yview"):
                    steps = -int(event.delta / 120)
                    if steps == 0 and event.delta:
                        steps = -1 if event.delta > 0 else 1
                    widget.yview_scroll(steps, "units")
                return "break"
            widget = widget.master
        return None

    def _focus_next_entry(self, event: tk.Event) -> str | None:
        editable_types = (tk.Entry, tk.Spinbox, ttk.Entry, ttk.Combobox, ttk.Spinbox)
        if not isinstance(event.widget, editable_types):
            return None
        current = event.widget
        candidate = current.tk_focusNext()
        while candidate is not current:
            if isinstance(candidate, editable_types):
                candidate.focus_set()
                break
            candidate = candidate.tk_focusNext()
        return "break"

    def _initialize_quote_history(self) -> None:
        self._quote_history_vars = {
            "customer": self.customer_var,
            "order_number": self.order_number_var,
            "notes": self.notes_var,
            **self.item_vars,
        }
        for variable in self._quote_history_vars.values():
            variable.trace_add("write", self._quote_form_changed)
        self._quote_history_snapshot = self._capture_quote_state()

    def _bind_quote_history_shortcuts(self, widget: tk.Widget) -> None:
        widget.bind("<Control-z>", self._undo_quote_change, add="+")
        widget.bind("<Control-x>", self._redo_quote_change, add="+")
        for child in widget.winfo_children():
            self._bind_quote_history_shortcuts(child)

    def _capture_quote_state(self) -> dict[str, Any]:
        return {
            "variables": {
                name: variable.get()
                for name, variable in self._quote_history_vars.items()
            },
            "draft_items": deepcopy(self.draft_items),
            "calculation_mode": self.calculation_mode_var.get(),
            "editing_draft_index": self.editing_draft_index,
            "editing_estimate_id": self.editing_estimate_id,
            "legacy_pricing_mode": self.legacy_pricing_mode,
            "item_photo_data": self.item_photo_data,
            "item_photo_name": self.item_photo_name,
        }

    def _quote_form_changed(self, *_args: object) -> None:
        if self._quote_history_suspended or self._quote_history_snapshot is None:
            return
        current = self._capture_quote_state()
        if current == self._quote_history_snapshot:
            return
        self._quote_undo_stack.append(self._quote_history_snapshot)
        del self._quote_undo_stack[:-100]
        self._quote_redo_stack.clear()
        self._quote_history_snapshot = current

    def _begin_quote_change(self) -> None:
        if self._quote_history_suspended == 0 and self._quote_history_snapshot is not None:
            current = self._capture_quote_state()
            if current != self._quote_history_snapshot:
                self._quote_undo_stack.append(self._quote_history_snapshot)
            else:
                self._quote_undo_stack.append(current)
            del self._quote_undo_stack[:-100]
            self._quote_redo_stack.clear()
        self._quote_history_suspended += 1

    def _end_quote_change(self) -> None:
        self._quote_history_suspended = max(0, self._quote_history_suspended - 1)
        if self._quote_history_suspended == 0:
            self._quote_history_snapshot = self._capture_quote_state()

    def _undo_quote_change(self, _event: tk.Event | None = None) -> str | None:
        if not self.quote_tab.winfo_ismapped():
            return None
        if self._quote_undo_stack:
            self._quote_redo_stack.append(self._capture_quote_state())
            self._restore_quote_state(self._quote_undo_stack.pop())
        return "break"

    def _redo_quote_change(self, _event: tk.Event | None = None) -> str | None:
        if not self.quote_tab.winfo_ismapped():
            return None
        if self._quote_redo_stack:
            self._quote_undo_stack.append(self._capture_quote_state())
            self._restore_quote_state(self._quote_redo_stack.pop())
        return "break"

    def _restore_quote_state(self, state: dict[str, Any]) -> None:
        self._quote_history_suspended += 1
        try:
            for name, value in state["variables"].items():
                self._quote_history_vars[name].set(value)
            self.draft_items = deepcopy(state["draft_items"])
            self.calculation_mode_var.set(state["calculation_mode"])
            self.editing_draft_index = state["editing_draft_index"]
            self.editing_estimate_id = state["editing_estimate_id"]
            self.legacy_pricing_mode = state["legacy_pricing_mode"]
            self._set_item_photo(state["item_photo_data"], state["item_photo_name"])
            self._update_calculation_form()
            if self.editing_draft_index is None:
                self.add_item_button.configure(text="＋  Dodaj całą partię" if state["calculation_mode"] == "whole_order" else "＋  Dodaj pozycję")
                self.cancel_item_edit_button.pack_forget()
            else:
                self.add_item_button.configure(text="Zapisz zmiany pozycji")
                self.cancel_item_edit_button.pack(side="left", padx=(7, 0))
            self._refresh_draft()
        finally:
            self._quote_history_suspended -= 1
        self._quote_history_snapshot = self._capture_quote_state()

    @staticmethod
    def _clear_zero_duration_on_focus(event: tk.Event) -> None:
        if event.widget.get() == "0":
            event.widget.delete(0, "end")

    def _resize_quote_form(self, event: tk.Event) -> None:
        self.quote_canvas.itemconfigure(self.quote_form_window, width=event.width)
        if hasattr(self, "item_field_cells"):
            self._layout_quote_fields(event.width)

    def _layout_quote_fields(self, width: int) -> None:
        compact = width < 760
        if compact == self.quote_layout_compact:
            return
        self.quote_layout_compact = compact
        order_columns = 2 if compact else 3
        for column in range(3):
            self.order_body.grid_columnconfigure(column, weight=1 if column < order_columns else 0)
        if compact:
            self.customer_cell.grid_configure(row=0, column=0, columnspan=2, padx=(0, 0))
            self.order_number_entry.master.grid_configure(row=1, column=0, columnspan=1, padx=(0, 8))
            self.notes_entry.master.grid_configure(row=1, column=1, columnspan=1, padx=(8, 0))
        else:
            self.customer_cell.grid_configure(row=0, column=0, columnspan=1, padx=(0, 10))
            self.order_number_entry.master.grid_configure(row=0, column=1, columnspan=1, padx=(10, 10))
            self.notes_entry.master.grid_configure(row=0, column=2, columnspan=1, padx=(10, 10))

        for column in range(4):
            self.item_body.grid_columnconfigure(column, weight=1 if column < (2 if compact else 4) else 0)
        full_layout = {
            "element_name": (2, 0),
            "material": (2, 1),
            "thickness_mm": (2, 2),
            "used_weight_kg": (3, 0),
            "price_per_kg": (3, 1),
            "burning_rate_per_hour": (3, 3),
            "vat_percent": (4, 0),
        }
        compact_layout = {
            "element_name": (2, 0),
            "material": (2, 1),
            "thickness_mm": (3, 0),
            "used_weight_kg": (4, 0),
            "price_per_kg": (4, 1),
            "burning_rate_per_hour": (5, 1),
            "vat_percent": (6, 0),
        }
        field_layout = compact_layout if compact else full_layout
        for name, (row, column) in field_layout.items():
            self.item_field_cells[name].grid_configure(
                row=row,
                column=column,
                columnspan=1,
                sticky="ew",
            )
        if compact:
            self.time_cell.grid_configure(row=5, column=0, padx=(0, 8))
            self.quantity_cell.grid_configure(row=3, column=1, padx=(8, 0))
            self.item_action_row.grid_configure(row=6, column=1, columnspan=1)
        else:
            self.time_cell.grid_configure(row=3, column=2, padx=(0, 10))
            self.quantity_cell.grid_configure(row=2, column=3, padx=(0, 10))
            self.item_action_row.grid_configure(row=4, column=1, columnspan=3)
        self.mode_row.grid_configure(columnspan=2 if compact else 4)
        self.mode_description_label.grid_configure(columnspan=2 if compact else 4)

    def _resize_workspace(self, event: tk.Event) -> None:
        if event.widget is not self:
            return
        width = max(270, min(340, int(event.width * 0.30)))
        self.sidebar.configure(width=width)

    def _refresh_sidebar_order_details(self, *_args: object) -> None:
        if not hasattr(self, "sidebar_order_var"):
            return
        customer = self.customer_var.get().strip() if hasattr(self, "customer_var") else ""
        order_number = self.order_number_var.get().strip() if hasattr(self, "order_number_var") else ""
        item_count = len(self.draft_items)
        if customer or order_number:
            details = (
                f"Zleceniodawca: {customer or '—'}\n"
                f"Nr zamówienia: {order_number or '—'}"
            )
        else:
            details = "Zleceniodawca: —\nNr zamówienia: —"
        if item_count:
            details += f"\nPozycji w zamówieniu: {item_count}"
        self.sidebar_order_var.set(details)

    @staticmethod
    def _card(parent: tk.Widget, title: str, subtitle: str = "") -> tuple[tk.Frame, tk.Frame]:
        outer = tk.Frame(parent, bg=WHITE, highlightthickness=1, highlightbackground=BORDER)
        top = tk.Frame(outer, bg=WHITE)
        top.pack(fill="x", padx=18, pady=(15, 10))
        tk.Frame(top, bg=BRAND_RED, width=3, height=28).pack(side="left", fill="y", padx=(0, 10))
        heading = tk.Frame(top, bg=WHITE)
        heading.pack(side="left", fill="x", expand=True)
        tk.Label(heading, text=title, bg=WHITE, fg=INK, font=("Segoe UI", 12, "bold")).pack(anchor="w")
        if subtitle:
            tk.Label(heading, text=subtitle, bg=WHITE, fg=MUTED, font=("Segoe UI", 9)).pack(anchor="w", pady=(3, 0))
        tk.Frame(outer, bg=BORDER, height=1).pack(fill="x", padx=18)
        body = tk.Frame(outer, bg=WHITE, padx=18, pady=14)
        body.pack(fill="both", expand=True)
        return outer, body

    @staticmethod
    def _page_heading(parent: tk.Widget, title: str, subtitle: str) -> None:
        heading = tk.Frame(parent, bg=BACKGROUND)
        heading.pack(fill="x", pady=(0, 14))
        tk.Frame(heading, bg=BRAND_RED, width=4, height=38).pack(side="left", fill="y", padx=(0, 12))
        text = tk.Frame(heading, bg=BACKGROUND)
        text.pack(side="left", fill="x", expand=True)
        tk.Label(text, text=title, bg=BACKGROUND, fg=INK, font=("Segoe UI", 19, "bold")).pack(anchor="w")
        tk.Label(text, text=subtitle, bg=BACKGROUND, fg=MUTED, font=("Segoe UI", 9)).pack(anchor="w", pady=(3, 0))

    def _labeled_entry(
        self,
        parent: tk.Widget,
        label: str,
        variable: tk.StringVar,
        row: int,
        column: int,
        width: int | None = None,
        show: str | None = None,
    ) -> ttk.Entry:
        cell = tk.Frame(parent, bg=WHITE)
        cell.grid(row=row, column=column, sticky="ew", padx=(0 if column % 2 == 0 else 10, 10), pady=7)
        tk.Label(cell, text=label, bg=WHITE, fg=MUTED, font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(0, 5))
        entry = ttk.Entry(cell, textvariable=variable, width=width, show=show)
        entry.pack(fill="x")
        return entry

    def _build_quote_tab(self) -> None:
        self._page_heading(
            self.quote_form,
            "Wycena zamówienia",
            "Dodaj elementy, sprawdź koszt netto i brutto, a następnie zapisz ofertę.",
        )

        order_card, order_body = self._card(self.quote_form, "Dane zamówienia", "Informacje wspólne dla wszystkich pozycji.")
        order_card.pack(fill="x", pady=(0, 12))
        self.order_body = order_body
        self.customer_var = tk.StringVar()
        self.order_number_var = tk.StringVar()
        self.notes_var = tk.StringVar()
        self.customer_var.trace_add("write", self._refresh_sidebar_order_details)
        self.order_number_var.trace_add("write", self._refresh_sidebar_order_details)
        for column in range(3):
            order_body.grid_columnconfigure(column, weight=1)
        customer_cell = tk.Frame(order_body, bg=WHITE)
        self.customer_cell = customer_cell
        customer_cell.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        tk.Label(customer_cell, text="Zleceniodawca", bg=WHITE, fg=MUTED, font=("Segoe UI", 8, "bold")).pack(anchor="w", pady=(0, 3))
        self.customer_combo = ttk.Combobox(customer_cell, textvariable=self.customer_var)
        self.customer_combo.pack(fill="x")
        self.order_number_entry = self._labeled_entry(order_body, "Numer zamówienia klienta", self.order_number_var, 0, 1)
        self.notes_entry = self._labeled_entry(order_body, "Uwagi do oferty (opcjonalnie)", self.notes_var, 0, 2)
        item_card, item_body = self._card(
            self.quote_form,
            "Pozycja zamówienia",
            "Wybierz sposób kalkulacji, a formularz pokaże pola odpowiednie dla wybranej metody.",
        )
        self.item_body = item_body
        item_card.pack(fill="x", pady=(0, 12))
        self.calculation_mode_var = tk.StringVar(value="per_piece")
        self.calculation_mode_description = tk.StringVar()
        mode_row = tk.Frame(item_body, bg=WHITE)
        self.mode_row = mode_row
        mode_row.grid(row=0, column=0, columnspan=4, sticky="ew", pady=(0, 7))
        tk.Label(
            mode_row,
            text="SPOSÓB WPROWADZANIA KOSZTU",
            bg=WHITE,
            fg=MUTED,
            font=("Segoe UI", 8, "bold"),
        ).pack(side="left", padx=(0, 12))
        ttk.Radiobutton(
            mode_row,
            text="Cała partia",
            variable=self.calculation_mode_var,
            value="whole_order",
            command=self._update_calculation_form,
        ).pack(side="left", padx=(0, 8))
        ttk.Radiobutton(
            mode_row,
            text="Na sztukę",
            variable=self.calculation_mode_var,
            value="per_piece",
            command=self._update_calculation_form,
        ).pack(side="left")
        self.mode_description_label = tk.Label(
            item_body,
            textvariable=self.calculation_mode_description,
            bg=WHITE,
            fg=MUTED,
            font=("Segoe UI", 9),
            anchor="w",
            justify="left",
            wraplength=900,
        )
        self.mode_description_label.grid(row=1, column=0, columnspan=4, sticky="ew", pady=(0, 7))
        self.item_vars = {
            "element_name": tk.StringVar(),
            "material": tk.StringVar(),
            "thickness_mm": tk.StringVar(),
            "quantity": tk.StringVar(value="1"),
            "price_per_kg": tk.StringVar(value=self.settings["price_per_kg"]),
            "used_weight_kg": tk.StringVar(),
            "hours": tk.StringVar(value="0"),
            "minutes": tk.StringVar(value="0"),
            "seconds": tk.StringVar(value="0"),
            "burning_rate_per_hour": tk.StringVar(value=self.settings["burning_rate_per_hour"]),
            "vat_percent": tk.StringVar(value=self.settings["vat_percent"]),
        }
        self.quantity_cell = tk.Frame(item_body, bg=WHITE)
        self.quantity_cell.grid(row=2, column=3, sticky="ew", padx=(0, 10), pady=7)
        self.quantity_label = tk.Label(
            self.quantity_cell,
            text="Ilość (szt.) *",
            bg=WHITE,
            fg=MUTED,
            font=("Segoe UI", 9, "bold"),
        )
        self.quantity_label.pack(anchor="w", pady=(0, 5))
        ttk.Entry(self.quantity_cell, textvariable=self.item_vars["quantity"]).pack(fill="x")
        for column in range(4):
            item_body.grid_columnconfigure(column, weight=1)
        self.item_field_cells: dict[str, tk.Widget] = {}
        self.item_field_cells["element_name"] = self._labeled_entry(item_body, "Nazwa elementu *", self.item_vars["element_name"], 2, 0).master
        photo_actions = tk.Frame(self.item_field_cells["element_name"], bg=WHITE)
        photo_actions.pack(fill="x", pady=(5, 0))
        self.item_photo_button = ttk.Button(
            photo_actions,
            text="Dodaj zdjęcie",
            command=self.choose_item_photo,
        )
        self.item_photo_button.pack(side="left")
        self.item_photo_label = tk.Label(
            photo_actions,
            text="Brak zdjęcia",
            bg=WHITE,
            fg=MUTED,
            font=("Segoe UI", 8),
            anchor="w",
        )
        self.item_photo_label.pack(side="left", padx=(8, 0), fill="x", expand=True)
        self.item_photo_remove_button = ttk.Button(
            photo_actions,
            text="Usuń",
            style="Quiet.TButton",
            command=self.clear_item_photo,
        )
        self.item_photo_remove_button.pack(side="right")
        self.item_photo_image: ImageTk.PhotoImage | None = None
        self.item_field_cells["material"] = self._labeled_entry(item_body, "Materiał / gatunek", self.item_vars["material"], 2, 1).master
        self.item_field_cells["thickness_mm"] = self._labeled_entry(item_body, "Grubość (mm)", self.item_vars["thickness_mm"], 2, 2).master
        self.weight_entry = self._labeled_entry(item_body, "Masa jednej sztuki (kg) *", self.item_vars["used_weight_kg"], 3, 0)
        self.item_field_cells["used_weight_kg"] = self.weight_entry.master
        self.weight_label = self.weight_entry.master.winfo_children()[0]
        self.item_field_cells["price_per_kg"] = self._labeled_entry(item_body, "Cena materiału (zł/kg) *", self.item_vars["price_per_kg"], 3, 1).master
        time_cell = tk.Frame(item_body, bg=WHITE)
        self.time_cell = time_cell
        time_cell.grid(row=3, column=2, sticky="ew", padx=(0, 10), pady=7)
        self.time_label = tk.Label(time_cell, text="Czas palenia jednej sztuki *", bg=WHITE, fg=MUTED, font=("Segoe UI", 9, "bold"))
        self.time_label.pack(anchor="w", pady=(0, 5))
        time_row = tk.Frame(time_cell, bg=WHITE)
        time_row.pack(fill="x")
        for key, width in (("hours", 4), ("minutes", 3), ("seconds", 3)):
            time_entry = ttk.Entry(time_row, textvariable=self.item_vars[key], width=width, justify="center")
            time_entry.pack(side="left")
            time_entry.bind("<FocusIn>", self._clear_zero_duration_on_focus, add="+")
            if key != "seconds":
                tk.Label(time_row, text=":", bg=WHITE, fg=MUTED).pack(side="left", padx=4)
        self.item_field_cells["burning_rate_per_hour"] = self._labeled_entry(item_body, "Stawka palenia (zł/godz.)", self.item_vars["burning_rate_per_hour"], 3, 3).master
        self.item_field_cells["vat_percent"] = self._labeled_entry(item_body, "VAT (%)", self.item_vars["vat_percent"], 4, 0).master
        self.item_action_row = tk.Frame(item_body, bg=WHITE)
        self.item_action_row.grid(row=4, column=1, columnspan=3, sticky="e", padx=(0, 10), pady=(11, 5))
        self.add_item_button = ttk.Button(self.item_action_row, text="＋  Dodaj pozycję", style="Primary.TButton", command=self.add_item)
        self.add_item_button.pack(side="left")
        self.cancel_item_edit_button = ttk.Button(
            self.item_action_row,
            text="Anuluj edycję",
            command=self.cancel_draft_item_edit,
        )
        self.cancel_item_edit_button.pack(side="left", padx=(7, 0))
        self.cancel_item_edit_button.pack_forget()
        self._update_calculation_form()

        draft_card, draft_body = self._card(self.sidebar, "Elementy zamówienia")
        draft_card.pack(fill="both", expand=True, padx=12, pady=(0, 0))
        columns = ("element", "scope", "gross")
        self.draft_tree = ttk.Treeview(draft_body, columns=columns, show="headings", height=8, selectmode="browse")
        self.draft_tree.tag_configure("striped", background="#F7F9FC")
        for key, title, width in (
            ("element", "Element", 100),
            ("scope", "Ilość", 55),
            ("gross", "Brutto", 76),
        ):
            self.draft_tree.heading(key, text=title)
            self.draft_tree.column(
                key,
                width=width,
                minwidth=70 if key == "element" else (48 if key == "scope" else 65),
                stretch=key == "element",
                anchor="e" if key in ("scope", "gross") else "w",
            )
        draft_scroll = ttk.Scrollbar(draft_body, orient="vertical", command=self.draft_tree.yview)
        self.draft_tree.configure(yscrollcommand=draft_scroll.set)
        self.draft_tree.pack(side="left", fill="both", expand=True)
        draft_scroll.pack(side="right", fill="y")
        self.draft_tree.bind("<Double-1>", lambda _event: self.edit_draft_item())
        self.draft_tree.bind("<Delete>", lambda _event: self.remove_draft_item())
        self.draft_tree.bind("<Button-3>", self._show_draft_context_menu)

        footer = tk.Frame(self.sidebar, bg=WHITE, padx=18, pady=14, highlightthickness=1, highlightbackground=BORDER)
        self.summary_var = tk.StringVar(value="Dodaj pozycję, aby zobaczyć podsumowanie.")
        self.gross_var = tk.StringVar(value="—")
        tk.Label(footer, text="WARTOŚĆ BRUTTO", bg=WHITE, fg=MUTED, font=("Segoe UI", 8, "bold")).pack(anchor="w")
        tk.Label(footer, textvariable=self.gross_var, bg=WHITE, fg=ACCENT, font=("Segoe UI", 20, "bold")).pack(anchor="w", pady=(1, 0))
        tk.Label(
            footer,
            textvariable=self.summary_var,
            bg=WHITE,
            fg=MUTED,
            font=("Segoe UI", 8),
            wraplength=260,
            justify="left",
        ).pack(anchor="w", pady=(4, 10))
        ttk.Button(footer, text="Nowe zamówienie", style="Quiet.TButton", command=self.clear_form).pack(fill="x", pady=(5, 0))
        draft_card.pack_configure(pady=(0, footer.winfo_reqheight() + 24))
        footer.place(
            relx=1,
            rely=1,
            x=-12,
            y=-12,
            relwidth=1,
            width=-24,
            anchor="se",
        )

    def _build_history_tab(self) -> None:
        self._page_heading(
            self.history_tab,
            "Historia wycen",
            "Przeciągnij separator, aby zmienić szerokość listy i panelu akcji.",
        )
        card, body = self._card(self.history_tab, "Zapisane zamówienia")
        card.pack(fill="both", expand=True)
        search_row = ttk.Frame(body)
        search_row.pack(fill="x", pady=(0, 10))
        ttk.Label(search_row, text="Szukaj").pack(side="left", padx=(0, 8))
        self.history_search = tk.StringVar()
        search_entry = ttk.Entry(search_row, textvariable=self.history_search)
        search_entry.pack(side="left", fill="x", expand=True)
        self.history_search.trace_add("write", lambda *_args: self.refresh_history())

        self.history_panes = ttk.Panedwindow(body, orient="horizontal")
        self.history_panes.pack(fill="both", expand=True)
        list_panel = ttk.Frame(self.history_panes, padding=(0, 0, 8, 0))
        options_panel = ttk.Frame(self.history_panes, padding=(8, 0, 0, 0))
        self.history_panes.add(list_panel, weight=4)
        self.history_panes.add(options_panel, weight=1)
        self.history_panes.bind("<Configure>", self._position_history_sash, add="+")
        self._history_sash_positioned = False

        columns = ("quote", "date", "customer", "order", "count", "net", "gross")
        self.history_tree = ttk.Treeview(list_panel, columns=columns, show="headings", height=7, selectmode="browse")
        self.history_tree.tag_configure("striped", background="#F7F9FC")
        for key, title, width in (
            ("quote", "Numer wyceny", 135),
            ("date", "Data", 130),
            ("customer", "Zleceniodawca", 185),
            ("order", "Nr zamówienia", 140),
            ("count", "Pozycje", 75),
            ("net", "Netto", 120),
            ("gross", "Brutto", 120),
        ):
            self.history_tree.heading(key, text=title)
            self.history_tree.column(key, width=width, anchor="e" if key in ("count", "net", "gross") else "w")
        list_panel.grid_rowconfigure(0, weight=1)
        list_panel.grid_columnconfigure(0, weight=1)
        scroll = ttk.Scrollbar(list_panel, orient="vertical", command=self.history_tree.yview)
        horizontal_scroll = ttk.Scrollbar(list_panel, orient="horizontal", command=self.history_tree.xview)
        self.history_tree.configure(
            yscrollcommand=scroll.set,
            xscrollcommand=horizontal_scroll.set,
        )
        self.history_tree.grid(row=0, column=0, sticky="nsew")
        scroll.grid(row=0, column=1, sticky="ns")
        horizontal_scroll.grid(row=1, column=0, sticky="ew")
        self.history_tree.bind("<Double-1>", lambda _event: self.load_selected_estimate())
        self.history_tree.bind("<<TreeviewSelect>>", self.show_selected_items)

        options_canvas = tk.Canvas(options_panel, bg=WHITE, highlightthickness=0, borderwidth=0)
        options_scroll = ttk.Scrollbar(options_panel, orient="vertical", command=options_canvas.yview)
        options_canvas.configure(yscrollcommand=options_scroll.set)
        options_canvas.pack(side="left", fill="both", expand=True)
        options_scroll.pack(side="right", fill="y")
        self.history_options = ttk.Frame(options_canvas)
        options_window = options_canvas.create_window((0, 0), window=self.history_options, anchor="nw")
        self.history_options.bind(
            "<Configure>",
            lambda _event: options_canvas.configure(scrollregion=options_canvas.bbox("all")),
        )
        options_canvas.bind(
            "<Configure>",
            lambda event: options_canvas.itemconfigure(options_window, width=event.width),
        )
        options_canvas.bind(
            "<MouseWheel>",
            lambda event: options_canvas.yview_scroll(-int(event.delta / 120), "units"),
        )
        self.history_options.bind(
            "<MouseWheel>",
            lambda event: options_canvas.yview_scroll(-int(event.delta / 120), "units"),
        )
        ttk.Label(self.history_options, text="OPCJE WYCENY", style="CardTitle.TLabel").pack(anchor="w", pady=(4, 10))
        self.history_detail = tk.StringVar(value="Zaznacz wycenę, aby zobaczyć pozycje.")
        detail_box = tk.Frame(self.history_options, bg="#F6F8FB", padx=10, pady=10, highlightthickness=1, highlightbackground=BORDER)
        detail_box.pack(fill="x", pady=(0, 12))
        ttk.Label(
            detail_box,
            textvariable=self.history_detail,
            style="CardMuted.TLabel",
            wraplength=240,
            justify="left",
        ).pack(fill="x", anchor="w")
        for text, command, style in (
            ("Otwórz / edytuj", self.load_selected_estimate, "Primary.TButton"),
            ("Podgląd oferty", self.preview_selected_estimate, "TButton"),
            ("Kopiuj do nowej", self.copy_selected_estimate, "TButton"),
            ("Eksport CSV", self.export_csv, "TButton"),
            ("Eksport PDF", self.export_pdf, "TButton"),
        ):
            ttk.Button(
                self.history_options,
                text=text,
                command=command,
                style=style,
            ).pack(fill="x", pady=3)
        ttk.Separator(self.history_options).pack(fill="x", pady=(12, 9))
        ttk.Button(
            self.history_options,
            text="Usuń wycenę",
            style="Danger.TButton",
            command=self.delete_selected_estimate,
        ).pack(fill="x", pady=(4, 8))
        self.after_idle(self._position_history_sash)

    def _position_history_sash(self, _event: tk.Event | None = None) -> None:
        if self._history_sash_positioned or self.history_panes.winfo_width() < 300:
            return
        self.history_panes.sashpos(0, int(self.history_panes.winfo_width() * 0.68))
        self._history_sash_positioned = True

    def _build_summary_tab(self) -> None:
        self._page_heading(
            self.summary_tab,
            "Podsumowanie i podgląd oferty",
            "Podgląd dokumentu dla klienta. PDF zachowuje układ strony A4 i nadaje się do druku.",
        )
        actions = tk.Frame(self.summary_tab, bg=BACKGROUND)
        actions.pack(fill="x", pady=(0, 10))
        ttk.Button(actions, text="←  Wróć do edycji", command=self._return_to_estimate_edit).pack(side="left")
        ttk.Button(actions, text="Eksport CSV", command=self.export_summary_csv).pack(side="left", padx=(7, 0))
        ttk.Button(actions, text="Eksport PDF", style="Primary.TButton", command=self.export_summary_pdf).pack(side="left", padx=(7, 0))
        ttk.Button(actions, text="Otwórz PDF do druku", command=self.print_summary_pdf).pack(side="left", padx=(7, 0))
        self.summary_status_var = tk.StringVar(value="")
        ttk.Label(actions, textvariable=self.summary_status_var, style="Subtitle.TLabel").pack(side="right")

        preview_card, preview_body = self._card(
            self.summary_tab,
            "Oferta dla klienta",
            "Kwoty są prezentowane zgodnie z wybranym sposobem wyceny; szczegóły kosztów wewnętrznych nie są pokazywane.",
        )
        preview_card.pack(fill="both", expand=True)
        preview_frame = tk.Frame(preview_body, bg="#E7EDF4")
        preview_frame.pack(fill="both", expand=True)
        self.preview_canvas = tk.Canvas(
            preview_frame,
            bg="#E7EDF4",
            highlightthickness=0,
            borderwidth=0,
        )
        preview_scroll = ttk.Scrollbar(preview_frame, orient="vertical", command=self.preview_canvas.yview)
        self.preview_canvas.configure(yscrollcommand=preview_scroll.set)
        self.preview_canvas.pack(side="left", fill="both", expand=True)
        preview_scroll.pack(side="right", fill="y")
        self.preview_canvas.bind("<Configure>", lambda _event: self._render_estimate_preview())

    def _render_estimate_preview(self) -> None:
        if not hasattr(self, "preview_canvas") or self.summary_estimate is None:
            return

        try:
            import pymupdf

            document_stream = BytesIO()
            export_estimate_pdf(
                self.summary_estimate,
                self.settings,
                document_stream,
                "offer",
            )
            document = pymupdf.open(stream=document_stream.getvalue(), filetype="pdf")
        except (ImportError, OSError, ValueError, RuntimeError) as error:
            messagebox.showerror(
                "Podgląd oferty",
                f"Nie udało się przygotować podglądu PDF:\n{error}",
                parent=self,
            )
            return

        canvas = self.preview_canvas
        canvas.delete("all")
        self.preview_page_images = []
        try:
            display_width = max(1, canvas.winfo_width() - 40)
            y = 16
            page_gap = 20
            for page in document:
                zoom = min(1.5, display_width / page.rect.width)
                pixmap = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=False)
                rendered_page = Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)
                page_image = ImageTk.PhotoImage(rendered_page)
                self.preview_page_images.append(page_image)
                left = max(20, (canvas.winfo_width() - pixmap.width) // 2)
                canvas.create_image(left, y, image=page_image, anchor="nw")
                y += pixmap.height + page_gap
        except (OSError, RuntimeError, ValueError) as error:
            messagebox.showerror(
                "Podgląd oferty",
                f"Nie udało się wyświetlić stron PDF:\n{error}",
                parent=self,
            )
            return
        finally:
            document.close()
        canvas.configure(
            scrollregion=(
                0,
                0,
                max(canvas.winfo_width(), max((image.width() for image in self.preview_page_images), default=0) + 40),
                y,
            )
        )

    def _build_customers_tab(self) -> None:
        self._page_heading(
            self.customers_tab,
            "Kartoteka klientów",
            "Dane kontaktowe są zapisywane lokalnie i mogą pojawić się w ofercie PDF.",
        )
        card, body = self._card(self.customers_tab, "Zleceniodawcy")
        card.pack(fill="both", expand=True)
        columns = ("name", "contact", "email", "phone", "tax_id", "address")
        self.customers_tree = ttk.Treeview(body, columns=columns, show="headings", height=8, selectmode="browse")
        self.customers_tree.tag_configure("striped", background="#F7F9FC")
        for key, title, width in (
            ("name", "Firma / klient", 190),
            ("contact", "Osoba kontaktowa", 155),
            ("email", "E-mail", 190),
            ("phone", "Telefon", 125),
            ("tax_id", "NIP", 110),
            ("address", "Adres", 260),
        ):
            self.customers_tree.heading(key, text=title)
            self.customers_tree.column(key, width=width, anchor="w")
        scroll = ttk.Scrollbar(body, orient="vertical", command=self.customers_tree.yview)
        self.customers_tree.configure(yscrollcommand=scroll.set)
        self.customers_tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        horizontal_scroll = ttk.Scrollbar(body, orient="horizontal", command=self.customers_tree.xview)
        self.customers_tree.configure(xscrollcommand=horizontal_scroll.set)
        horizontal_scroll.pack(side="bottom", fill="x")
        self.customers_tree.bind("<Double-1>", lambda _event: self.edit_customer())
        actions = ttk.Frame(body)
        actions.pack(fill="x", pady=(10, 0))
        ttk.Button(actions, text="＋  Dodaj klienta", style="Primary.TButton", command=self.add_customer).pack(side="left")
        ttk.Button(actions, text="Edytuj", command=self.edit_customer).pack(side="left", padx=(7, 0))
        ttk.Button(actions, text="Usuń", style="Danger.TButton", command=self.delete_customer).pack(side="left", padx=(7, 0))

    def _duration_label(self, seconds: int) -> str:
        hours, remainder = divmod(seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours:02}:{minutes:02}:{seconds:02}"

    def _update_calculation_form(self) -> None:
        whole_order = self.calculation_mode_var.get() == "whole_order"
        button_text = (
            "Zapisz zmiany pozycji"
            if self.editing_draft_index is not None
            else "＋  Dodaj całą partię" if whole_order else "＋  Dodaj pozycję"
        )
        if whole_order:
            quantity_row, quantity_column = (3, 1) if self.quote_layout_compact else (2, 3)
            self.quantity_cell.grid(
                row=quantity_row,
                column=quantity_column,
                sticky="ew",
                padx=(8, 0) if self.quote_layout_compact else (0, 10),
                pady=7,
            )
            self.quantity_label.configure(text="Ilość gotowego produktu (szt.) *")
            self.weight_label.configure(text="Masa wszystkich sztuk razem (kg) *")
            self.time_label.configure(text="Czas palenia wszystkich sztuk razem *")
            self.calculation_mode_description.set(
                "Wpisz łączną masę i czas palenia całej partii oraz końcową liczbę gotowych sztuk. Ilość nie zmienia kosztu partii."
            )
        else:
            quantity_row, quantity_column = (3, 1) if self.quote_layout_compact else (2, 3)
            self.quantity_cell.grid(
                row=quantity_row,
                column=quantity_column,
                sticky="ew",
                padx=(8, 0) if self.quote_layout_compact else (0, 10),
                pady=7,
            )
            self.quantity_label.configure(text="Ilość (szt.) *")
            self.weight_label.configure(text="Masa jednej sztuki (kg) *")
            self.time_label.configure(text="Czas palenia jednej sztuki *")
            self.calculation_mode_description.set(
                "Wpisz masę i czas jednej sztuki oraz ilość. Koszt jednostkowy zostanie przemnożony przez liczbę sztuk."
            )
        self.add_item_button.configure(text=button_text)

    def _build_item_from_form(self) -> dict[str, Any]:
        values = {key: variable.get().strip() for key, variable in self.item_vars.items()}
        if not values["element_name"]:
            raise ValueError("Podaj nazwę elementu.")
        calculation_mode = self.calculation_mode_var.get()
        try:
            quantity = int(values["quantity"])
        except ValueError as error:
            raise ValueError("Ilość musi być dodatnią liczbą całkowitą.") from error
        if quantity < 1 or quantity > 1_000_000:
            raise ValueError("Ilość musi mieścić się w zakresie od 1 do 1 000 000 sztuk.")
        price = parse_decimal(values["price_per_kg"], "Cena materiału za kg")
        weight_label = "Masa całej partii" if calculation_mode == "whole_order" else "Masa jednej sztuki"
        weight = parse_decimal(values["used_weight_kg"], weight_label)
        rate = parse_decimal(values["burning_rate_per_hour"], "Stawka palenia")
        vat = parse_decimal(values["vat_percent"], "VAT")
        duration_seconds = parse_duration(values["hours"], values["minutes"], values["seconds"])
        if calculation_mode == "whole_order" and weight <= 0:
            raise ValueError("Masa całej partii musi być większa od zera.")
        quote = calculate_quote(price, weight, duration_seconds, rate, vat)
        line_net, line_vat, line_gross = calculate_item_line_amounts(
            quote.net_total,
            quote.vat_amount,
            quote.gross_total,
            quantity,
            calculation_mode,
        )
        if max(line_net, line_vat, line_gross) > Decimal("1000000000000"):
            raise ValueError("Wartość pozycji nie może przekraczać 1 000 000 000 000 zł.")
        return {
            "element_name": values["element_name"],
            "material": values["material"],
            "thickness_mm": values["thickness_mm"],
            "calculation_mode": calculation_mode,
            "quantity": quantity,
            "price_per_kg": str(price),
            "used_weight_kg": str(weight),
            "duration_seconds": duration_seconds,
            "burning_rate_per_hour": str(rate),
            "vat_percent": str(vat),
            "material_cost": str(quote.material_cost),
            "burning_cost": str(quote.burning_cost),
            "unit_net": str(quote.net_total),
            "unit_vat": str(quote.vat_amount),
            "unit_gross": str(quote.gross_total),
            "line_net": str(line_net),
            "line_vat": str(line_vat),
            "line_gross": str(line_gross),
            "preview_image": self.item_photo_data,
            "preview_image_name": self.item_photo_name,
        }

    def choose_item_photo(self) -> None:
        filename = filedialog.askopenfilename(
            parent=self,
            title="Wybierz zdjęcie poglądowe elementu",
            filetypes=[
                ("Pliki graficzne", "*.png *.jpg *.jpeg *.gif *.bmp *.webp *.tif *.tiff"),
                ("Wszystkie pliki", "*.*"),
            ],
        )
        if not filename:
            return
        image_path = Path(filename)
        try:
            if image_path.stat().st_size > MAX_PREVIEW_IMAGE_BYTES:
                raise ValueError("Zdjęcie może mieć maksymalnie 10 MB.")
            with Image.open(image_path) as source:
                source.seek(0)
                image = source.convert("RGB")
                image.thumbnail((1600, 1200), Image.Resampling.LANCZOS)
                output = BytesIO()
                image.save(output, format="JPEG", quality=88, optimize=True)
        except (
            OSError,
            UnidentifiedImageError,
            Image.DecompressionBombError,
            ValueError,
        ) as error:
            messagebox.showerror(
                "Nieprawidłowe zdjęcie",
                f"Nie udało się odczytać wybranego pliku graficznego:\n{error}",
                parent=self,
            )
            return
        self._begin_quote_change()
        self._set_item_photo(output.getvalue(), image_path.name)
        self._end_quote_change()

    def _set_item_photo(self, image_data: bytes | None, image_name: str = "") -> None:
        self.item_photo_data = image_data
        self.item_photo_name = image_name if image_data else ""
        self.item_photo_thumbnail = None
        if image_data:
            with Image.open(BytesIO(image_data)) as image:
                thumbnail = image.copy()
            thumbnail.thumbnail((54, 42), Image.Resampling.LANCZOS)
            self.item_photo_thumbnail = ImageTk.PhotoImage(thumbnail)
            self.item_photo_label.configure(
                image=self.item_photo_thumbnail,
                text="  Zdjęcie dodane",
                compound="left",
            )
        else:
            self.item_photo_label.configure(image="", text="Brak zdjęcia", compound="left")

    def clear_item_photo(self) -> None:
        self._begin_quote_change()
        self._set_item_photo(None)
        self._end_quote_change()

    def add_item(self) -> None:
        try:
            item = self._build_item_from_form()
        except ValueError as error:
            messagebox.showerror("Sprawdź pozycję", str(error), parent=self)
            return
        self._begin_quote_change()
        if self.editing_draft_index is None:
            self.draft_items.append(item)
        else:
            self.draft_items[self.editing_draft_index] = item
            self.editing_draft_index = None
            self.add_item_button.configure(text="＋  Dodaj pozycję")
            self.cancel_item_edit_button.pack_forget()
        self._refresh_draft()
        self._reset_item_editor()
        self._end_quote_change()

    def _reset_item_editor(self) -> None:
        self.editing_draft_index = None
        self.add_item_button.configure(text="＋  Dodaj pozycję")
        self.cancel_item_edit_button.pack_forget()
        self._set_item_photo(None)
        self.calculation_mode_var.set("per_piece")
        self._update_calculation_form()
        for key in ("element_name", "material", "thickness_mm", "used_weight_kg"):
            self.item_vars[key].set("")
        self.item_vars["price_per_kg"].set(self.settings["price_per_kg"])
        self.item_vars["quantity"].set("1")
        for key in ("hours", "minutes", "seconds"):
            self.item_vars[key].set("0")

    def cancel_draft_item_edit(self) -> None:
        if self.editing_draft_index is None:
            return
        self._reset_item_editor()

    def _refresh_draft(self) -> None:
        self.draft_tree.delete(*self.draft_tree.get_children())
        total_net = Decimal("0")
        total_vat = Decimal("0")
        total_quantity = 0
        for index, item in enumerate(self.draft_items):
            line_net, line_vat, gross = line_totals(item)
            total_net += line_net
            total_vat += line_vat
            total_quantity += int(item["quantity"])
            self.draft_tree.insert(
                "",
                "end",
                iid=str(index),
                tags=("striped",) if index % 2 else (),
                values=(
                    f"▧ {item['element_name']}" if item.get("preview_image") else str(item["element_name"]),
                    f"{item['quantity']} szt.",
                    format_pln(gross),
                ),
            )
        if self.draft_items:
            scope_summary = f"{total_quantity} szt." if total_quantity else ""
            position_summary = f"{len(self.draft_items)} poz."
            if scope_summary:
                position_summary += f"  ·  {scope_summary}"
            self.summary_var.set(f"{position_summary}  ·  Netto {format_pln(total_net)}  ·  VAT {format_pln(total_vat)}")
            self.gross_var.set(format_pln(total_net + total_vat))
        else:
            self.summary_var.set("Dodaj pozycję, aby zobaczyć podsumowanie.")
            self.gross_var.set("—")
        self._refresh_sidebar_order_details()

    def remove_draft_item(self) -> None:
        selected = self.draft_tree.selection()
        if not selected:
            messagebox.showinfo("Pozycje zamówienia", "Zaznacz pozycję, którą chcesz usunąć.", parent=self)
            return
        removed_index = int(selected[0])
        self._begin_quote_change()
        del self.draft_items[removed_index]
        if self.editing_draft_index == removed_index:
            self._reset_item_editor()
        elif self.editing_draft_index is not None and removed_index < self.editing_draft_index:
            self.editing_draft_index -= 1
        self._refresh_draft()
        self._end_quote_change()

    def edit_draft_item(self) -> None:
        selected = self.draft_tree.selection()
        if not selected:
            messagebox.showinfo("Pozycje zamówienia", "Zaznacz pozycję, którą chcesz poprawić.", parent=self)
            return
        selected_index = int(selected[0])
        self._quote_history_suspended += 1
        try:
            self._load_draft_item_into_editor(selected_index)
        finally:
            self._quote_history_suspended -= 1
        self._quote_history_snapshot = self._capture_quote_state()

    def _load_draft_item_into_editor(self, selected_index: int) -> None:
        item = self.draft_items[selected_index]
        self.editing_draft_index = selected_index
        self.calculation_mode_var.set(item.get("calculation_mode", "per_piece"))
        self._update_calculation_form()
        self.item_vars["element_name"].set(item["element_name"])
        self.item_vars["material"].set(item["material"])
        self.item_vars["thickness_mm"].set(item["thickness_mm"])
        self.item_vars["quantity"].set(str(item["quantity"]))
        self.item_vars["price_per_kg"].set(item["price_per_kg"])
        self.item_vars["used_weight_kg"].set(item["used_weight_kg"])
        self.item_vars["burning_rate_per_hour"].set(item["burning_rate_per_hour"])
        self.item_vars["vat_percent"].set(item["vat_percent"])
        hours, remainder = divmod(int(item["duration_seconds"]), 3600)
        minutes, seconds = divmod(remainder, 60)
        self.item_vars["hours"].set(str(hours))
        self.item_vars["minutes"].set(str(minutes))
        self.item_vars["seconds"].set(str(seconds))
        self._set_item_photo(
            item.get("preview_image"),
            item.get("preview_image_name", ""),
        )
        self.add_item_button.configure(text="Zapisz zmiany pozycji")
        self.cancel_item_edit_button.pack(side="left", padx=(7, 0))

    def _show_draft_context_menu(self, event: tk.Event) -> str:
        row_id = self.draft_tree.identify_row(event.y)
        if not row_id:
            return "break"
        self.draft_tree.selection_set(row_id)
        self.draft_tree.focus(row_id)
        item_index = int(row_id)
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label="Edytuj", command=self.edit_draft_item)
        menu.add_command(label="Usuń", command=self.remove_draft_item)
        menu.add_command(label="Podgląd", command=lambda: self.preview_draft_item(item_index))
        menu.tk_popup(event.x_root, event.y_root)
        menu.grab_release()
        return "break"

    def preview_draft_item(self, item_index: int) -> None:
        if not 0 <= item_index < len(self.draft_items):
            return
        image_data = self.draft_items[item_index].get("preview_image")
        if not image_data:
            messagebox.showinfo(
                "Podgląd elementu",
                "Ta pozycja nie ma przypisanego zdjęcia poglądowego.",
                parent=self,
            )
            return
        try:
            with Image.open(BytesIO(bytes(image_data))) as image:
                preview = image.copy()
            preview.thumbnail((1000, 750), Image.Resampling.LANCZOS)
        except (OSError, UnidentifiedImageError, ValueError) as error:
            messagebox.showerror(
                "Podgląd elementu",
                f"Nie można wyświetlić zdjęcia:\n{error}",
                parent=self,
            )
            return
        window = tk.Toplevel(self)
        window.title(f"Podgląd — {self.draft_items[item_index]['element_name']}")
        window.transient(self)
        window.configure(bg=WHITE)
        window.resizable(False, False)
        image_view = ImageTk.PhotoImage(preview)
        window.preview_image = image_view
        tk.Label(window, image=image_view, bg=WHITE).pack(padx=12, pady=12)
        ttk.Button(window, text="Zamknij", command=window.destroy).pack(pady=(0, 12))
        window.update_idletasks()
        window.geometry(
            f"+{self.winfo_rootx() + max(20, (self.winfo_width() - window.winfo_width()) // 2)}"
            f"+{self.winfo_rooty() + max(20, (self.winfo_height() - window.winfo_height()) // 2)}"
        )

    def save_estimate(self) -> None:
        if self.editing_draft_index is not None:
            try:
                updated_item = self._build_item_from_form()
            except ValueError as error:
                messagebox.showerror("Sprawdź pozycję", str(error), parent=self)
                return
            self.draft_items[self.editing_draft_index] = updated_item
            self._reset_item_editor()
            self._refresh_draft()
        customer = self.customer_var.get().strip()
        order_number = self.order_number_var.get().strip()
        if not customer or not order_number:
            messagebox.showerror("Dane zamówienia", "Uzupełnij zleceniodawcę i numer zamówienia klienta.", parent=self)
            return
        if not self.draft_items:
            messagebox.showerror("Brak pozycji", "Dodaj przynajmniej jeden element do zamówienia.", parent=self)
            return
        try:
            existing_customer = next(
                (row for row in self.storage.list_customers(self.user_id) if row["name"].casefold() == customer.casefold()),
                None,
            )
            if existing_customer is None:
                self.storage.save_customer(self.user_id, {"name": customer})
            estimate_id = self.storage.save_estimate(
                self.user_id,
                {
                    "customer_name": customer,
                    "order_number": order_number,
                    "notes": self.notes_var.get(),
                    "pricing_mode": self.legacy_pricing_mode,
                },
                self.draft_items,
                self.editing_estimate_id,
            )
            estimate = self.storage.get_estimate(self.user_id, estimate_id)
        except (ValueError, sqlite3.Error) as error:
            messagebox.showerror("Nie udało się zapisać wyceny", str(error), parent=self)
            return
        if estimate is None:
            messagebox.showerror(
                "Nie udało się otworzyć wyceny",
                "Wycena została zapisana, ale nie udało się odczytać jej podsumowania z lokalnej bazy.",
                parent=self,
            )
            return
        self.editing_estimate_id = estimate_id
        self.refresh_history()
        self.refresh_customers()
        self._show_estimate_summary(estimate)

    def _show_estimate_summary(self, estimate: dict[str, Any]) -> None:
        self.summary_estimate = estimate
        self.navigation_buttons["summary"].configure(state="normal")
        self.summary_status_var.set(
            f"Zapisano w bazie lokalnej · {estimate['header']['quote_number']}"
        )
        self._show_page("summary")
        self.after_idle(self._render_estimate_preview)

    def _return_to_estimate_edit(self) -> None:
        self._show_page("quote")

    def preview_selected_estimate(self) -> None:
        estimate = self._selected_estimate()
        if estimate is not None:
            self._show_estimate_summary(estimate)

    def clear_form(self) -> None:
        self._begin_quote_change()
        try:
            self.draft_items.clear()
            self.editing_draft_index = None
            self.editing_estimate_id = None
            self.legacy_pricing_mode = "itemized"
            self.save_estimate_button.configure(text="Zatwierdź wycenę")
            self.customer_var.set("")
            self.order_number_var.set("")
            self.notes_var.set("")
            self.calculation_mode_var.set("per_piece")
            self._update_calculation_form()
            self._refresh_draft()
            self._reset_item_editor()
            self.item_vars["quantity"].set("1")
            self.item_vars["price_per_kg"].set(self.settings["price_per_kg"])
            self.item_vars["burning_rate_per_hour"].set(self.settings["burning_rate_per_hour"])
            self.item_vars["vat_percent"].set(self.settings["vat_percent"])
            for key in ("hours", "minutes", "seconds"):
                self.item_vars[key].set("0")
        finally:
            self._end_quote_change()

    def refresh_history(self) -> None:
        if not hasattr(self, "history_tree"):
            return
        try:
            rows = self.storage.list_estimates(self.user_id, self.history_search.get() if hasattr(self, "history_search") else "")
        except sqlite3.Error as error:
            messagebox.showerror("Błąd bazy danych", f"Nie udało się odczytać historii:\n{error}", parent=self)
            return
        self.history_tree.delete(*self.history_tree.get_children())
        for index, row in enumerate(rows):
            created_at = datetime.fromisoformat(row["created_at"]).astimezone().strftime("%d.%m.%Y %H:%M")
            self.history_tree.insert(
                "",
                "end",
                iid=str(row["id"]),
                tags=("striped",) if index % 2 else (),
                values=(
                    row["quote_number"],
                    created_at,
                    row["customer_name"],
                    row["order_number"],
                    row["item_count"],
                    format_pln(row["net_total"]),
                    format_pln(row["gross_total"]),
                ),
            )

    def _selected_estimate(self) -> dict[str, Any] | None:
        selected = self.history_tree.selection()
        if not selected:
            messagebox.showinfo("Historia wycen", "Zaznacz zamówienie na liście.", parent=self)
            return None
        try:
            estimate = self.storage.get_estimate(self.user_id, int(selected[0]))
        except sqlite3.Error as error:
            messagebox.showerror("Błąd bazy danych", f"Nie udało się odczytać zamówienia:\n{error}", parent=self)
            return None
        if estimate is None:
            messagebox.showerror("Historia wycen", "Nie znaleziono zaznaczonej wyceny.", parent=self)
        return estimate

    def show_selected_items(self, _event: tk.Event | None = None) -> None:
        selected = self.history_tree.selection()
        if not selected:
            return
        try:
            estimate = self.storage.get_estimate(self.user_id, int(selected[0]))
        except sqlite3.Error as error:
            self.history_detail.set(f"Nie udało się odczytać pozycji: {error}")
            return
        if not estimate:
            self.history_detail.set("Nie znaleziono pozycji zamówienia.")
            return
        summary_parts = []
        for item in estimate["items"]:
            scope = (
                "cała partia"
                if item.get("calculation_mode", "per_piece") == "whole_order"
                else f"{item['quantity']} szt."
            )
            summary_parts.append(
                f"{item['element_name']} · {scope} ({format_pln(item['line_gross'])})"
            )
        summary = "   ·   ".join(summary_parts)
        self.history_detail.set(summary)

    def _load_estimate_into_form(self, estimate: dict[str, Any], copy: bool) -> None:
        header = estimate["header"]
        self._begin_quote_change()
        try:
            self.clear_form()
            self.customer_var.set(header["customer_name"])
            self.order_number_var.set(header["order_number"])
            self.notes_var.set(header["notes"])
            self.legacy_pricing_mode = header.get("pricing_mode", "itemized")
            self.draft_items = [dict(item) for item in estimate["items"]]
            self.editing_estimate_id = None if copy else int(header["id"])
            self.save_estimate_button.configure(
                text="Zatwierdź wycenę" if copy else "Zapisz zmiany i pokaż podsumowanie"
            )
            self._refresh_draft()
            if self.draft_items:
                first_item_id = "0"
                self.draft_tree.selection_set(first_item_id)
                self.draft_tree.focus(first_item_id)
                self.edit_draft_item()
            self._show_page("quote")
            if copy:
                self.order_number_var.set("")
        finally:
            self._end_quote_change()

    def load_selected_estimate(self) -> None:
        estimate = self._selected_estimate()
        if estimate is not None:
            self._load_estimate_into_form(estimate, copy=False)

    def copy_selected_estimate(self) -> None:
        estimate = self._selected_estimate()
        if estimate is not None:
            self._load_estimate_into_form(estimate, copy=True)

    def delete_selected_estimate(self) -> None:
        selected = self.history_tree.selection()
        if not selected:
            messagebox.showinfo("Historia wycen", "Zaznacz zamówienie, które chcesz usunąć.", parent=self)
            return
        if not messagebox.askyesno("Usuń wycenę", "Usunąć wycenę wraz z jej pozycjami? Tej operacji nie można cofnąć.", parent=self):
            return
        try:
            deleted_estimate_id = int(selected[0])
            self.storage.delete_estimate(self.user_id, deleted_estimate_id)
        except sqlite3.Error as error:
            messagebox.showerror("Błąd bazy danych", f"Nie udało się usunąć wyceny:\n{error}", parent=self)
            return
        if self.editing_estimate_id == deleted_estimate_id:
            self.clear_form()
        if self.summary_estimate and int(self.summary_estimate["header"]["id"]) == deleted_estimate_id:
            self.summary_estimate = None
            self.navigation_buttons["summary"].configure(state="disabled", style="Nav.TButton")
            self.summary_status_var.set("")
        self.refresh_history()

    def _estimate_export_basename(
        self,
        estimate: dict[str, Any],
        document_kind: str = "offer",
    ) -> str:
        quote_number = str(estimate["header"]["quote_number"])
        return quote_number if document_kind == "offer" else f"{quote_number}_koszty"

    def _export_target(self, extension: str, default_name: str) -> str:
        try:
            OFFER_EXPORT_DIRECTORY.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            messagebox.showerror(
                "Folder eksportu",
                f"Nie można przygotować domyślnego folderu ofert:\n{OFFER_EXPORT_DIRECTORY}\n\n{error}",
                parent=self,
            )
            return ""
        return filedialog.asksaveasfilename(
            parent=self,
            title=f"Zapisz eksport {extension.upper()}",
            initialdir=str(OFFER_EXPORT_DIRECTORY),
            initialfile=default_name,
            defaultextension=f".{extension}",
            confirmoverwrite=True,
            filetypes=[(f"Plik {extension.upper()}", f"*.{extension}")],
        )

    def export_csv(self) -> None:
        estimate = self._selected_estimate()
        if estimate is None:
            return
        self._write_estimate_csv(estimate)

    def export_summary_csv(self) -> None:
        if self.summary_estimate is None:
            return
        self._write_estimate_csv(self.summary_estimate)

    def _write_estimate_csv(self, estimate: dict[str, Any]) -> None:
        filename = self._export_target(
            "csv",
            f"{self._estimate_export_basename(estimate)}.csv",
        )
        if not filename:
            return
        try:
            export_estimate_csv(estimate, filename, self.settings)
        except (OSError, ValueError) as error:
            messagebox.showerror("Eksport CSV", f"Nie udało się zapisać pliku:\n{error}", parent=self)
            return
        messagebox.showinfo("Eksport CSV", f"Zapisano plik:\n{filename}", parent=self)

    def export_pdf(self) -> None:
        estimate = self._selected_estimate()
        if estimate is None:
            return
        dialog = tk.Toplevel(self)
        dialog.title("Eksport PDF")
        dialog.transient(self)
        dialog.grab_set()
        dialog.configure(bg=WHITE)
        dialog.resizable(False, False)
        content = tk.Frame(dialog, bg=WHITE, padx=24, pady=20)
        content.pack(fill="both", expand=True)
        tk.Label(content, text="Wybierz rodzaj dokumentu", bg=WHITE, fg=INK, font=("Segoe UI", 13, "bold")).pack(anchor="w")
        kind = tk.StringVar(value="offer")
        ttk.Radiobutton(content, text="Oferta dla klienta — bez szczegółów kosztów wewnętrznych", variable=kind, value="offer").pack(anchor="w", pady=(12, 4))
        ttk.Radiobutton(content, text="Arkusz wewnętrzny — materiał, czas i składowe kosztu", variable=kind, value="internal").pack(anchor="w", pady=4)
        buttons = ttk.Frame(content)
        buttons.pack(fill="x", pady=(16, 0))

        def choose_path() -> None:
            dialog.destroy()
            document_kind = kind.get()
            self._write_estimate_pdf(estimate, document_kind)

        ttk.Button(buttons, text="Anuluj", command=dialog.destroy).pack(side="right")
        ttk.Button(buttons, text="Dalej", style="Primary.TButton", command=choose_path).pack(side="right", padx=(0, 8))
        dialog.update_idletasks()
        dialog.geometry(f"+{self.winfo_rootx() + 350}+{self.winfo_rooty() + 250}")

    def export_summary_pdf(self) -> None:
        if self.summary_estimate is not None:
            self._write_estimate_pdf(self.summary_estimate, "offer")

    def print_summary_pdf(self) -> None:
        if self.summary_estimate is not None:
            self._write_estimate_pdf(self.summary_estimate, "offer", open_after_export=True)

    def _write_estimate_pdf(
        self,
        estimate: dict[str, Any],
        document_kind: str,
        open_after_export: bool = False,
    ) -> None:
        filename = self._export_target(
            "pdf",
            f"{self._estimate_export_basename(estimate, document_kind)}.pdf",
        )
        if not filename:
            return
        try:
            export_estimate_pdf(estimate, self.settings, filename, document_kind)
        except (OSError, ValueError, ImportError) as error:
            messagebox.showerror("Eksport PDF", f"Nie udało się utworzyć pliku PDF:\n{error}", parent=self)
            return
        if not open_after_export:
            messagebox.showinfo("Eksport PDF", f"Zapisano plik:\n{filename}", parent=self)
            return

        open_file = getattr(os, "startfile", None)
        if open_file is None:
            messagebox.showinfo(
                "PDF gotowy do druku",
                f"Zapisano plik:\n{filename}\nOtwórz go w przeglądarce PDF, aby wydrukować ofertę.",
                parent=self,
            )
            return
        try:
            open_file(filename)
        except OSError as error:
            messagebox.showerror(
                "Nie udało się otworzyć PDF",
                f"Plik został zapisany:\n{filename}\n\nNie można go otworzyć do druku:\n{error}",
                parent=self,
            )
            return
        messagebox.showinfo("PDF gotowy do druku", f"Otworzono ofertę:\n{filename}", parent=self)

    def refresh_customers(self) -> None:
        if not hasattr(self, "customers_tree"):
            return
        try:
            rows = self.storage.list_customers(self.user_id)
        except sqlite3.Error as error:
            messagebox.showerror("Błąd bazy danych", f"Nie udało się odczytać klientów:\n{error}", parent=self)
            return
        self.customers_tree.delete(*self.customers_tree.get_children())
        for index, row in enumerate(rows):
            self.customers_tree.insert(
                "", "end", iid=str(row["id"]),
                tags=("striped",) if index % 2 else (),
                values=(row["name"], row["contact_person"], row["email"], row["phone"], row["tax_id"], row["address"]),
            )
        self.customer_combo.configure(values=[row["name"] for row in rows])

    @staticmethod
    def _address_editor(
        parent: tk.Widget,
        row: int,
        values: dict[str, str],
        key_prefix: str = "",
        legacy_address: str = "",
        include_legacy: bool = False,
    ) -> tuple[dict[str, tk.StringVar], tk.StringVar]:
        preview = tk.StringVar()
        address_variables = {
            f"{key_prefix}{field}": tk.StringVar(
                value=values.get(f"{key_prefix}{field}", "Polska" if field == "country" else "")
            )
            for field in ADDRESS_FIELDS
        }
        legacy_variable = tk.StringVar(value=legacy_address)
        grid = tk.Frame(parent, bg=WHITE)
        for column in range(3):
            grid.grid_columnconfigure(column, weight=1)
        preview_label = tk.Label(
            grid,
            textvariable=preview,
            bg=WHITE,
            fg=INK,
            font=("Segoe UI", 9),
            justify="left",
            anchor="w",
            wraplength=600,
        )
        preview_label.grid(row=0, column=0, columnspan=2, sticky="ew", pady=3)
        open_state = {"open": False}
        editor = tk.Frame(grid, bg="#F7F8FA", padx=12, pady=10, highlightthickness=1, highlightbackground=BORDER)

        def update_preview(*_args: object) -> None:
            address_values = {
                key: value.get()
                for key, value in address_variables.items()
            }
            formatted = format_postal_address(address_values, key_prefix)
            if formatted and legacy_variable.get().strip():
                legacy = legacy_variable.get().strip()
                if not parse_polish_address(legacy):
                    formatted = f"{formatted}, {legacy}"
            preview.set(f"Adres: {formatted or legacy_variable.get().strip() or 'Nie uzupełniono'}")

        editor_fields = (
            ("street", "Ulica"),
            ("building_number", "Nr budynku"),
            ("unit_number", "Nr lokalu (opcjonalnie)"),
            ("postal_code", "Kod pocztowy"),
            ("city", "Miejscowość"),
            ("country", "Kraj"),
        )
        for column in range(3):
            editor.grid_columnconfigure(column, weight=1)
        for index, (field, label) in enumerate(editor_fields):
            key = f"{key_prefix}{field}"
            variable = address_variables[key]
            cell = tk.Frame(editor, bg="#F7F8FA")
            cell.grid(row=index // 3, column=index % 3, sticky="ew", padx=(0, 10), pady=4)
            tk.Label(cell, text=label, bg="#F7F8FA", fg=MUTED, font=("Segoe UI", 8, "bold")).pack(anchor="w", pady=(0, 3))
            ttk.Entry(cell, textvariable=variable).pack(fill="x")

        if include_legacy:
            legacy_row = (len(editor_fields) + 2) // 3
            legacy_cell = tk.Frame(editor, bg="#F7F8FA")
            legacy_cell.grid(row=legacy_row, column=0, columnspan=3, sticky="ew", pady=(7, 2))
            tk.Label(
                legacy_cell,
                text="Zachowany wcześniejszy zapis adresu (nie będzie usunięty)",
                bg="#F7F8FA",
                fg=MUTED,
                font=("Segoe UI", 8, "bold"),
            ).pack(anchor="w", pady=(0, 3))
            ttk.Entry(legacy_cell, textvariable=legacy_variable).pack(fill="x")

        def toggle_editor() -> None:
            open_state["open"] = not open_state["open"]
            if open_state["open"]:
                editor.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(7, 2))
                toggle.configure(text="Ukryj pola adresu ▲")
            else:
                editor.grid_remove()
                toggle.configure(text="Uzupełnij / edytuj adres ▼")

        toggle = ttk.Button(grid, text="Uzupełnij / edytuj adres ▼", command=toggle_editor)
        toggle.grid(row=0, column=2, sticky="e", padx=(8, 0), pady=2)
        for variable in (*address_variables.values(), legacy_variable):
            variable.trace_add("write", update_preview)
        update_preview()
        grid.grid(row=row, column=0, columnspan=3, sticky="ew", padx=0, pady=4)
        return address_variables, legacy_variable

    def _customer_dialog(self, customer: dict[str, Any] | None = None) -> None:
        editing_id = int(customer["id"]) if customer else None
        dialog = tk.Toplevel(self)
        dialog.title("Edytuj klienta" if customer else "Dodaj klienta")
        dialog.transient(self)
        dialog.grab_set()
        dialog.configure(bg=WHITE)
        dialog.resizable(False, False)
        content = tk.Frame(dialog, bg=WHITE, padx=24, pady=20)
        content.pack(fill="both", expand=True)
        tk.Label(content, text="Dane klienta", bg=WHITE, fg=INK, font=("Segoe UI", 14, "bold")).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 14))
        fields = (
            ("name", "Firma / klient *"),
            ("contact_person", "Osoba kontaktowa"),
            ("email", "E-mail"),
            ("phone", "Telefon"),
            ("tax_id", "NIP"),
        )
        variables: dict[str, tk.StringVar] = {}
        for row, (key, label) in enumerate(fields, start=1):
            variable = tk.StringVar(value=str(customer[key] or "") if customer else "")
            variables[key] = variable
            tk.Label(content, text=label, bg=WHITE, fg=MUTED, font=("Segoe UI", 9, "bold")).grid(row=row, column=0, sticky="w", padx=(0, 15), pady=6)
            ttk.Entry(content, textvariable=variable, width=38).grid(row=row, column=1, sticky="ew", pady=6, ipady=3)

        address_values = customer or {}
        if customer and not customer.get("street") and customer.get("address"):
            parsed = parse_polish_address(str(customer["address"]))
            if parsed:
                address_values = {**customer, **parsed}
        preserved_legacy_address = str((customer or {}).get("address_legacy") or "")
        address_variables, legacy_address = self._address_editor(
            content,
            len(fields) + 1,
            address_values,
            legacy_address=preserved_legacy_address,
            include_legacy=bool(preserved_legacy_address and not parse_polish_address(preserved_legacy_address)),
        )

        def save() -> None:
            try:
                values = {key: value.get() for key, value in variables.items()}
                values.update({key: value.get() for key, value in address_variables.items()})
                values["address_legacy"] = legacy_address.get()
                values["address"] = (
                    format_postal_address(values)
                    or legacy_address.get().strip()
                )
                validate_postal_address(values)
                self.storage.save_customer(self.user_id, values, editing_id)
            except ValueError as error:
                messagebox.showerror("Dane klienta", str(error), parent=dialog)
                return
            except sqlite3.IntegrityError:
                messagebox.showerror("Dane klienta", "Klient o tej nazwie już istnieje.", parent=dialog)
                return
            except sqlite3.Error as error:
                messagebox.showerror("Błąd bazy danych", f"Nie udało się zapisać klienta:\n{error}", parent=dialog)
                return
            dialog.destroy()
            self.refresh_customers()

        buttons = ttk.Frame(content)
        buttons.grid(row=len(fields) + 2, column=0, columnspan=3, sticky="e", pady=(14, 0))
        ttk.Button(buttons, text="Anuluj", command=dialog.destroy).pack(side="right")
        ttk.Button(buttons, text="Zapisz klienta", style="Primary.TButton", command=save).pack(side="right", padx=(0, 8))

    def add_customer(self) -> None:
        self._customer_dialog()

    def edit_customer(self) -> None:
        selected = self.customers_tree.selection()
        if not selected:
            messagebox.showinfo("Kartoteka klientów", "Zaznacz klienta do edycji.", parent=self)
            return
        try:
            customer = next((row for row in self.storage.list_customers(self.user_id) if row["id"] == int(selected[0])), None)
        except sqlite3.Error as error:
            messagebox.showerror("Błąd bazy danych", f"Nie udało się odczytać klienta:\n{error}", parent=self)
            return
        if customer:
            self._customer_dialog(dict(customer))

    def delete_customer(self) -> None:
        selected = self.customers_tree.selection()
        if not selected:
            messagebox.showinfo("Kartoteka klientów", "Zaznacz klienta do usunięcia.", parent=self)
            return
        if not messagebox.askyesno("Usuń klienta", "Usunąć dane klienta? Zapisane wyceny i ich dane pozostaną bez zmian.", parent=self):
            return
        try:
            self.storage.delete_customer(self.user_id, int(selected[0]))
        except sqlite3.Error as error:
            messagebox.showerror("Błąd bazy danych", f"Nie udało się usunąć klienta:\n{error}", parent=self)
            return
        self.refresh_customers()

    def open_settings(self) -> None:
        settings = self.storage.get_settings(self.user_id)
        dialog = tk.Toplevel(self)
        dialog.title("Ustawienia BlachCalc")
        dialog.transient(self)
        dialog.grab_set()
        dialog.configure(bg=WHITE)
        dialog.resizable(False, False)
        content = tk.Frame(dialog, bg=WHITE, padx=24, pady=20)
        content.pack(fill="both", expand=True)
        tk.Label(content, text="Profil firmowy Izo-Technika", bg=WHITE, fg=INK, font=("Segoe UI", 15, "bold")).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 3))
        tk.Label(
            content,
            text="Dane trafiają do nagłówka oferty PDF. Stawki poniżej są domyślne; pozycje wycen mogą je nadpisywać.",
            bg=WHITE,
            fg=MUTED,
            font=("Segoe UI", 9),
        ).grid(row=1, column=0, columnspan=3, sticky="w", pady=(0, 14))
        variables: dict[str, tk.StringVar] = {
            "company_name": tk.StringVar(value=settings.get("company_name", "")),
        }
        tk.Label(content, text="Nazwa firmy", bg=WHITE, fg=MUTED, font=("Segoe UI", 9, "bold")).grid(row=2, column=0, sticky="w", padx=(0, 14), pady=5)
        ttk.Entry(content, textvariable=variables["company_name"], width=42).grid(row=2, column=1, columnspan=2, sticky="ew", pady=5)
        previous_company_address = settings.get("company_address", "")
        company_address_variables, company_legacy_address = self._address_editor(
            content,
            3,
            settings,
            key_prefix="company_",
            legacy_address=previous_company_address,
            include_legacy=bool(
                previous_company_address
                and not parse_polish_address(previous_company_address)
            ),
        )
        fields = (
            ("company_phone", "Telefon firmy"),
            ("company_email", "E-mail firmy"),
            ("company_tax_id", "NIP firmy"),
            ("company_website", "Strona internetowa"),
            ("brand_tagline", "Hasło / opis marki"),
            ("price_per_kg", "Domyślna cena materiału (zł/kg)"),
            ("burning_rate_per_hour", "Domyślna stawka palenia (zł/godz.)"),
            ("vat_percent", "Domyślna stawka VAT (%)"),
        )
        for row, (key, label) in enumerate(fields, start=5):
            variable = tk.StringVar(value=settings.get(key, ""))
            variables[key] = variable
            tk.Label(content, text=label, bg=WHITE, fg=MUTED, font=("Segoe UI", 9, "bold")).grid(row=row, column=0, sticky="w", padx=(0, 14), pady=5)
            ttk.Entry(content, textvariable=variable, width=42).grid(row=row, column=1, columnspan=2, sticky="ew", pady=5)

        logo_var = tk.StringVar(value=settings.get("logo_path", ""))
        logo_row = len(fields) + 5
        tk.Label(content, text="Firmowe logo (PNG / GIF)", bg=WHITE, fg=MUTED, font=("Segoe UI", 9, "bold")).grid(row=logo_row, column=0, sticky="w", padx=(0, 14), pady=5)
        ttk.Entry(content, textvariable=logo_var, width=31).grid(row=logo_row, column=1, sticky="ew", pady=5)

        def select_logo() -> None:
            filename = filedialog.askopenfilename(
                parent=dialog,
                title="Wybierz logo firmy",
                filetypes=[("Logo PNG lub GIF", "*.png *.gif"), ("Wszystkie pliki", "*.*")],
            )
            if filename:
                logo_var.set(filename)

        ttk.Button(content, text="Wybierz…", command=select_logo).grid(row=logo_row, column=2, padx=(7, 0))

        def backup() -> None:
            filename = filedialog.asksaveasfilename(
                parent=dialog,
                title="Zapisz kopię zapasową",
                initialfile=f"blachcalc-kopia-{datetime.now():%Y%m%d-%H%M}.sqlite3",
                defaultextension=".sqlite3",
                filetypes=[("Kopia bazy SQLite", "*.sqlite3")],
            )
            if not filename:
                return
            try:
                self.storage.backup(filename)
            except (OSError, sqlite3.Error) as error:
                messagebox.showerror("Kopia zapasowa", f"Nie udało się utworzyć kopii:\n{error}", parent=dialog)
                return
            messagebox.showinfo("Kopia zapasowa", f"Zapisano kopię:\n{filename}", parent=dialog)

        ttk.Button(content, text="Utwórz kopię zapasową bazy…", command=backup).grid(row=logo_row + 1, column=0, columnspan=2, sticky="w", pady=(9, 0))

        def save() -> None:
            try:
                material_price = parse_decimal(
                    variables["price_per_kg"].get(),
                    "Domyślna cena materiału",
                )
                rate = parse_decimal(variables["burning_rate_per_hour"].get(), "Domyślna stawka palenia")
                vat = parse_decimal(variables["vat_percent"].get(), "Domyślny VAT")
                calculate_quote(material_price, Decimal("1"), 0, rate, vat)
            except ValueError as error:
                messagebox.showerror("Ustawienia", str(error), parent=dialog)
                return
            updated = {key: value.get().strip() for key, value in variables.items()}
            updated.update({
                key: value.get().strip()
                for key, value in company_address_variables.items()
            })
            try:
                validate_postal_address(updated, "company_")
            except ValueError as error:
                messagebox.showerror("Adres firmy", str(error), parent=dialog)
                return
            updated["company_address"] = (
                format_postal_address(updated, "company_")
                or company_legacy_address.get().strip()
            )
            updated["burning_rate_per_hour"] = str(rate)
            updated["price_per_kg"] = str(material_price)
            updated["vat_percent"] = str(vat)
            logo_path = logo_var.get().strip()
            if logo_path and not Path(logo_path).is_file():
                messagebox.showerror("Ustawienia", "Wybrany plik logo nie istnieje.", parent=dialog)
                return
            if logo_path and Path(logo_path).suffix.lower() not in {".png", ".gif"}:
                messagebox.showerror("Ustawienia", "Logo aplikacji musi być w formacie PNG lub GIF.", parent=dialog)
                return
            updated["logo_path"] = logo_path
            try:
                self.storage.save_settings(self.user_id, updated)
            except sqlite3.Error as error:
                messagebox.showerror("Błąd bazy danych", f"Nie udało się zapisać ustawień:\n{error}", parent=dialog)
                return
            self.settings = self.storage.get_settings(self.user_id)
            self.item_vars["price_per_kg"].set(self.settings["price_per_kg"])
            self.item_vars["burning_rate_per_hour"].set(self.settings["burning_rate_per_hour"])
            self.item_vars["vat_percent"].set(self.settings["vat_percent"])
            self._refresh_brand_badge()
            dialog.destroy()

        buttons = ttk.Frame(content)
        buttons.grid(row=logo_row + 2, column=0, columnspan=3, sticky="e", pady=(18, 0))
        ttk.Button(buttons, text="Zamknij", command=dialog.destroy).pack(side="right")
        ttk.Button(buttons, text="Zapisz ustawienia", style="Primary.TButton", command=save).pack(side="right", padx=(0, 8))

    @staticmethod
    def _brand_fallback(parent: tk.Widget) -> None:
        mark = tk.Frame(parent, bg=ACCENT, width=42, height=42)
        mark.pack(side="left")
        mark.pack_propagate(False)
        tk.Label(mark, text="B", bg=ACCENT, fg=WHITE, font=("Segoe UI", 21, "bold")).pack(expand=True)

    def _refresh_brand_badge(self) -> None:
        for child in self.brand_badge.winfo_children():
            child.destroy()
        self.logo_image = None
        logo_path = self.settings.get("logo_path", "")
        if logo_path:
            try:
                source_image = tk.PhotoImage(file=logo_path)
                factor = max(
                    (source_image.width() + 139) // 140,
                    (source_image.height() + 39) // 40,
                    1,
                )
                self.logo_image = source_image.subsample(factor, factor)
                tk.Label(self.brand_badge, image=self.logo_image, bg=WHITE).pack(side="left")
                icon_factor = max(
                    (source_image.width() + 47) // 48,
                    (source_image.height() + 47) // 48,
                    1,
                )
                self.window_icon = source_image.subsample(icon_factor, icon_factor)
                self.app.wm_iconphoto(True, self.window_icon)
                return
            except tk.TclError as error:
                messagebox.showwarning(
                    "Logo firmy",
                    f"Nie można wyświetlić wybranego logo. Wybierz poprawny plik PNG lub GIF.\n\n{error}",
                    parent=self,
                )
        self._brand_fallback(self.brand_badge)
        self.window_icon = tk.PhotoImage(width=32, height=32)
        self.window_icon.put(NAVY, to=(0, 0, 32, 32))
        self.window_icon.put(BRAND_RED, to=(0, 25, 32, 32))
        self.app.wm_iconphoto(True, self.window_icon)


def main() -> None:
    try:
        storage = Storage()
    except (OSError, sqlite3.Error) as error:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("BlachCalc — błąd uruchamiania", f"Nie można przygotować lokalnej bazy danych:\n{error}")
        root.destroy()
        return

    try:
        app = BlachCalcApp(storage)
    except (OSError, sqlite3.Error, ValueError) as error:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("BlachCalc — błąd uruchamiania", f"Nie można przygotować lokalnego profilu:\n{error}")
        root.destroy()
        return
    app.mainloop()


if __name__ == "__main__":
    main()
