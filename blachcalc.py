import json
import os
import sqlite3
import tempfile
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
from exports import (
    PHOTO_WIDTH_MAX_MM,
    PHOTO_WIDTH_MIN_MM,
    export_delivery_note_pdf,
    export_estimate_csv,
    export_estimate_pdf,
)
from offer_page import (
    CONTACT_FIELDS,
    LIST_SECTIONS,
    SETTING_KEY as OFFER_PAGE_SETTING,
    default_offer_page,
    parse_offer_page,
    serialize_offer_page,
)
from app_paths import offer_export_directory, resource_path, wz_export_directory
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
DELIVERY_NOTE_DRAFT_SETTING = "delivery_note_draft"
QUOTE_FIELD_ENTRY_WIDTH = 21
QUOTE_FIELD_COMBO_WIDTH = 19
OFFER_EXPORT_DIRECTORY = offer_export_directory()
WZ_EXPORT_DIRECTORY = wz_export_directory()


class FieldValidationError(ValueError):
    def __init__(self, message: str, field: str | None = None) -> None:
        super().__init__(message)
        self.field = field


class BlachCalcApp(tk.Tk):
    def __init__(self, storage: Storage) -> None:
        super().__init__()
        self.storage = storage
        self.title("Izo-Technika | BlachCalc — Wyceny CNC")
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        self.geometry(f"{min(1260, screen_width - 40)}x{min(900, screen_height - 80)}")
        self.minsize(min(800, screen_width - 40), min(680, screen_height - 80))
        self.protocol("WM_DELETE_WINDOW", self.close_application)
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

    def close_application(self) -> None:
        for child in self.winfo_children():
            if isinstance(child, DashboardView) and not child.save_delivery_note_draft():
                return
        self.destroy()

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
        for base_style in ("TEntry", "TCombobox"):
            style.configure(f"Invalid.{base_style}", fieldbackground=PALE_RED)
            style.map(
                f"Invalid.{base_style}",
                fieldbackground=[("readonly", PALE_RED), ("!disabled", PALE_RED)],
                bordercolor=[("focus", BRAND_RED), ("!focus", BRAND_RED)],
                lightcolor=[("focus", BRAND_RED), ("!focus", BRAND_RED)],
                darkcolor=[("focus", BRAND_RED), ("!focus", BRAND_RED)],
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
            "Mode.TRadiobutton",
            background="#F4F7FB",
            foreground=INK,
            padding=(8, 5),
            font=("Segoe UI", 9, "bold"),
        )
        style.map(
            "Mode.TRadiobutton",
            background=[("active", "#E8EEF5")],
            foreground=[("selected", ACCENT), ("active", INK)],
        )
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
        self._cleanup_stale_print_jobs()
        self.draft_items: list[dict[str, Any]] = []
        self.quote_layout_compact = False
        self.editing_draft_index: int | None = None
        self.editing_estimate_id: int | None = None
        self.legacy_pricing_mode = "itemized"
        self.summary_estimate: dict[str, Any] | None = None
        self.delivery_note_estimate_id: int | None = None
        self.delivery_note_initialized = False
        self.delivery_note_return_page = "quote"
        self.delivery_note_rows: list[dict[str, Any]] = []
        self._delivery_note_save_after_id: str | None = None
        self._sidebar_density_after_id: str | None = None
        self._pdf_preview_render_after_id: str | None = None
        self._restoring_delivery_note_draft = False
        self._delivery_note_draft_error_shown = False
        self._pdf_preview_images: list[ImageTk.PhotoImage] = []
        self._pdf_preview_bytes: bytes | None = None
        self._pdf_preview_return_page = "delivery_note"
        self._pdf_preview_print_action: Any = None
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
        self.bind("<Destroy>", self._cancel_pending_estimate_preview, add="+")
        self._build()
        self.refresh_history()
        self.refresh_customers()

    def _cancel_pending_estimate_preview(self, event: tk.Event) -> None:
        if event.widget is not self:
            return
        for attribute in (
            "_preview_resize_after_id",
            "_delivery_note_save_after_id",
            "_sidebar_density_after_id",
            "_pdf_preview_resize_after_id",
            "_pdf_preview_render_after_id",
        ):
            after_id = getattr(self, attribute, None)
            if after_id is None:
                continue
            try:
                self.after_cancel(after_id)
            except tk.TclError:
                pass
            setattr(self, attribute, None)

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
        exit_action = self.app.show_login if LOGIN_ENABLED else self.app.close_application
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
        self.delivery_note_tab = tk.Frame(self.main_content, bg=BACKGROUND, padx=4, pady=12)
        self.pdf_preview_tab = tk.Frame(self.main_content, bg=BACKGROUND, padx=4, pady=12)
        self._build_quote_tab()
        self._build_history_tab()
        self._build_customers_tab()
        self._build_summary_tab()
        self._build_delivery_note_tab()
        self._build_pdf_preview_tab()
        self._bind_mousewheel_events(self)
        self.bind_all("<Return>", self._focus_next_entry, add="+")
        self._bind_quote_history_shortcuts(self.quote_tab)
        self._bind_quote_history_shortcuts(self.sidebar)
        self._initialize_quote_history()
        self._restore_delivery_note_draft()
        self._bind_global_shortcuts()
        self._show_page("quote")

    def _bind_mousewheel_events(self, parent: tk.Widget) -> None:
        self.bind_all("<MouseWheel>", self._on_mousewheel, add="+")
        self.bind_all("<Button-4>", self._on_mousewheel_button, add="+")
        self.bind_all("<Button-5>", self._on_mousewheel_button, add="+")

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
        self.delivery_note_navigation_button = ttk.Button(
            navigation,
            text="▣   Generuj WZ",
            style="Nav.TButton",
            command=self._open_delivery_note_from_navigation,
        )
        self.delivery_note_navigation_button.pack(fill="x", pady=2)
        self.navigation_buttons["delivery_note"] = self.delivery_note_navigation_button
        tk.Frame(self.sidebar, bg=BORDER, height=1).pack(fill="x", padx=14)
        self.sidebar_order_block = tk.Frame(self.sidebar, bg=WHITE)
        self.sidebar_order_block.pack(fill="x")
        tk.Label(
            self.sidebar_order_block,
            text="BIEŻĄCE ZAMÓWIENIE",
            bg=WHITE,
            fg=INK,
            font=("Segoe UI", 9, "bold"),
        ).pack(anchor="w", padx=24, pady=(15, 8))
        self.sidebar_order_var = tk.StringVar(value="Zleceniodawca: —\nNr zamówienia: —")
        self.sidebar_order_label = tk.Label(
            self.sidebar_order_block,
            textvariable=self.sidebar_order_var,
            bg=WHITE,
            fg=MUTED,
            font=("Segoe UI", 9),
            justify="left",
            anchor="w",
            wraplength=280,
        )
        self.sidebar_order_label.pack(fill="x", padx=24, pady=(0, 10))

    def _show_page(self, page: str) -> None:
        pages = {
            "quote": self.quote_tab,
            "history": self.history_tab,
            "customers": self.customers_tab,
            "summary": self.summary_tab,
            "delivery_note": self.delivery_note_tab,
            "pdf_preview": self.pdf_preview_tab,
        }
        if page == "summary" and self.summary_estimate is None:
            return
        if page == "delivery_note" and not self.delivery_note_initialized:
            return
        selected = pages[page]
        for frame in pages.values():
            frame.pack_forget()
        selected.pack(fill="both", expand=True)
        self.current_page = page
        if page == "pdf_preview":
            if self._pdf_preview_render_after_id is not None:
                self.after_cancel(self._pdf_preview_render_after_id)
            self._pdf_preview_render_after_id = self.after_idle(
                self._render_document_preview
            )
        for key, button in self.navigation_buttons.items():
            active_page = "delivery_note" if page == "pdf_preview" else page
            button.configure(style="NavActive.TButton" if key == active_page else "Nav.TButton")

    def _bind_global_shortcuts(self) -> None:
        shortcuts = (
            (("<Control-s>", "<Control-S>"), self._shortcut_save),
            (("<Control-n>", "<Control-N>"), self._shortcut_new),
            (("<Control-p>", "<Control-P>"), self._shortcut_print),
            (("<Control-Shift-D>",), self._shortcut_duplicate),
            (("<Control-Key-1>",), lambda: self._show_page("quote")),
            (("<Control-Key-2>",), lambda: self._show_page("history")),
            (("<Control-Key-3>",), lambda: self._show_page("customers")),
            (("<Control-Key-4>",), lambda: self._show_page("summary")),
        )
        for sequences, handler in shortcuts:
            for sequence in sequences:
                self.bind_all(sequence, lambda event, action=handler: self._run_shortcut(event, action), add="+")
        self.bind_all("<F1>", lambda event: self._run_shortcut(event, self._show_shortcuts_help), add="+")

    def _run_shortcut(self, event: tk.Event, action: Any) -> str | None:
        try:
            if event.widget.winfo_toplevel() is not self.winfo_toplevel():
                return None
        except (AttributeError, tk.TclError):
            return None
        action()
        return "break"

    def _shortcut_save(self) -> None:
        page = getattr(self, "current_page", "quote")
        if page == "quote":
            self.save_estimate()
        elif page == "summary":
            self.export_summary_pdf()
        elif page == "delivery_note":
            self.save_delivery_note_draft()
        elif page == "pdf_preview":
            self._save_current_document_preview()

    def _shortcut_new(self) -> None:
        if self.draft_items and not messagebox.askyesno(
            "Nowe zamówienie",
            "Rozpocząć nowe zamówienie? Niezapisane pozycje zostaną usunięte z formularza.",
            parent=self,
        ):
            return
        self.clear_form()
        self._show_page("quote")

    def _shortcut_print(self) -> None:
        page = getattr(self, "current_page", "quote")
        if page == "summary":
            self.print_summary_pdf()
        elif page == "pdf_preview":
            self._print_current_document_preview()
        elif page == "delivery_note":
            self.print_delivery_note()
        elif page == "history":
            self.export_pdf()

    def _shortcut_duplicate(self) -> None:
        page = getattr(self, "current_page", "quote")
        if page == "summary":
            self.copy_summary_estimate()
        elif page == "history":
            self.copy_selected_estimate()

    def _show_shortcuts_help(self) -> None:
        messagebox.showinfo(
            "Skróty klawiszowe",
            "Ctrl+N — nowe zamówienie\n"
            "Ctrl+P — drukuj ofertę lub WZ / eksport PDF (historia)\n"
            "Ctrl+S — zapisz wycenę, PDF z podglądu albo szkic WZ\n"
            "Ctrl+Shift+D — kopiuj wycenę do nowej (podsumowanie / historia)\n"
            "Ctrl+Z / Ctrl+X — cofnij / ponów zmianę w formularzu\n"
            "Ctrl+1…4 — Wycena, Historia, Klienci, Podsumowanie\n"
            "F1 — ta pomoc",
            parent=self,
        )

    def _on_mousewheel(self, event: tk.Event) -> str | None:
        steps = -int(event.delta / 120)
        if steps == 0 and event.delta:
            steps = -1 if event.delta > 0 else 1
        return self._scroll_at_pointer(
            event,
            steps,
            horizontal=bool(event.state & 0x0001),
        )

    def _on_mousewheel_button(self, event: tk.Event) -> str | None:
        return self._scroll_at_pointer(event, -1 if event.num == 4 else 1)

    def _scroll_at_pointer(
        self,
        event: tk.Event,
        steps: int,
        horizontal: bool = False,
    ) -> str | None:
        if not steps:
            return None
        try:
            widget = self.winfo_containing(event.x_root, event.y_root)
        except (KeyError, tk.TclError):
            widget = None
        if widget is None:
            return None
        scrollable_types = (tk.Canvas, tk.Listbox, tk.Text, ttk.Treeview)
        draft_card = getattr(self, "draft_card", None)
        while widget is not None and widget is not self:
            if isinstance(widget, ttk.Scrollbar):
                command = widget.tk.splitlist(widget.cget("command"))
                if command:
                    widget.tk.call(
                        *command,
                        "scroll",
                        steps,
                        "units",
                    )
                    return "break"
            if isinstance(widget, scrollable_types):
                view_method = "xview" if horizontal else "yview"
                if hasattr(widget, view_method):
                    view = getattr(widget, view_method)()
                    can_scroll = (
                        view[1] < 1 if steps > 0 else view[0] > 0
                    ) if len(view) == 2 else False
                    if can_scroll:
                        getattr(widget, f"{view_method}_scroll")(steps, "units")
                        return "break"
            if widget is draft_card:
                view = self.draft_tree.yview()
                can_scroll = (
                    view[1] < 1 if steps > 0 else view[0] > 0
                ) if len(view) == 2 else False
                if can_scroll:
                    self.draft_tree.yview_scroll(steps, "units")
                    return "break"
            widget = widget.master
        return None

    def _focus_chain_step(self, event: tk.Event, step: int, submit_at_end: bool = False) -> str | None:
        chain = getattr(self, "_item_focus_chain", [])
        if event.widget not in chain:
            return None
        index = chain.index(event.widget) + step
        if 0 <= index < len(chain):
            target = chain[index]
            target.focus_set()
            if isinstance(target, (ttk.Entry, tk.Entry)):
                target.selection_range(0, "end")
        elif submit_at_end and step > 0:
            self.add_item()
        return "break"

    def _refresh_material_choices(self) -> None:
        materials = [line.strip() for line in self.settings.get("materials", "").splitlines() if line.strip()]
        self.material_combo.configure(
            values=materials,
            state="readonly" if materials else "normal",
        )

    def _focus_next_entry(self, event: tk.Event) -> str | None:
        editable_types = (tk.Entry, tk.Spinbox, ttk.Entry, ttk.Combobox, ttk.Spinbox)
        if not isinstance(event.widget, editable_types):
            return None
        if event.widget in getattr(self, "_item_focus_chain", []):
            return self._focus_chain_step(event, 1, submit_at_end=True)
        current = event.widget
        candidate = current.tk_focusNext()
        while candidate is not current:
            if isinstance(candidate, editable_types):
                candidate.focus_set()
                break
            candidate = candidate.tk_focusNext()
        return "break"

    def _register_validation_fields(self) -> None:
        def first_entry(widget: tk.Widget) -> tk.Widget | None:
            if isinstance(widget, (ttk.Entry, ttk.Combobox)):
                return widget
            for child in widget.winfo_children():
                found = first_entry(child)
                if found is not None:
                    return found
            return None

        cells: dict[str, tk.Widget] = {
            **self.item_field_cells,
            "quantity": self.quantity_cell,
            "hours": self.time_cell,
        }
        self._field_widgets: dict[str, tk.Widget] = {}
        for field, cell in cells.items():
            entry = first_entry(cell)
            if entry is not None:
                self._field_widgets[field] = entry
        self._field_widgets["customer"] = self.customer_combo
        self._field_widgets["order_number"] = self.order_number_entry
        aliases = {"minutes": "hours", "seconds": "hours"}
        variables = {**self.item_vars, "customer": self.customer_var, "order_number": self.order_number_var}
        for name, variable in variables.items():
            variable.trace_add(
                "write",
                lambda *_args, field=aliases.get(name, name): self._clear_invalid(field),
            )

    def _mark_invalid(self, field: str | None) -> None:
        widget = self._field_widgets.get(field) if field else None
        if widget is None:
            return
        base_style = "TCombobox" if isinstance(widget, ttk.Combobox) else "TEntry"
        widget.configure(style=f"Invalid.{base_style}")
        self._scroll_quote_form_to(widget)
        widget.focus_set()

    def _clear_invalid(self, field: str) -> None:
        widget = getattr(self, "_field_widgets", {}).get(field)
        if widget is not None:
            widget.configure(style="TCombobox" if isinstance(widget, ttk.Combobox) else "TEntry")

    def _clear_all_invalid(self) -> None:
        for field in getattr(self, "_field_widgets", {}):
            self._clear_invalid(field)

    def _scroll_quote_form_to(self, widget: tk.Widget) -> None:
        self.update_idletasks()
        form_height = max(1, self.quote_form.winfo_height())
        offset = widget.winfo_rooty() - self.quote_form.winfo_rooty()
        visible_top = self.quote_canvas.canvasy(0)
        visible_bottom = visible_top + self.quote_canvas.winfo_height()
        if offset < visible_top + 10 or offset + widget.winfo_height() > visible_bottom - 10:
            self.quote_canvas.yview_moveto(max(0.0, (offset - 60) / form_height))

    def _show_validation_error(self, title: str, error: ValueError) -> None:
        self._clear_all_invalid()
        self._mark_invalid(getattr(error, "field", None))
        messagebox.showerror(title, str(error), parent=self)
        field = getattr(error, "field", None)
        widget = self._field_widgets.get(field) if field else None
        if widget is not None:
            widget.focus_set()

    def _initialize_quote_history(self) -> None:
        self._register_validation_fields()
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
                self.add_edited_item_button.pack(side="right", padx=(0, 8))
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
            self.order_number_entry.master.grid_configure(row=1, column=0, columnspan=2, padx=0)
            self.notes_entry.master.grid_configure(row=2, column=0, columnspan=2, padx=0)
        else:
            self.customer_cell.grid_configure(row=0, column=0, columnspan=1, padx=5)
            self.order_number_entry.master.grid_configure(row=0, column=1, columnspan=1, padx=5)
            self.notes_entry.master.grid_configure(row=0, column=2, columnspan=1, padx=5)

        self._place_item_fields(compact)

    def _place_item_fields(self, compact: bool) -> None:
        for column in range(2):
            self.item_body.grid_columnconfigure(
                column,
                weight=1,
                uniform="item_sections" if not compact else "",
            )
        self.item_body.grid_columnconfigure(2, weight=0)
        if compact:
            self.item_details_panel.grid(
                row=2,
                column=0,
                columnspan=2,
                sticky="ew",
                pady=(8, 0),
            )
            self.item_calculation_panel.grid(
                row=3,
                column=0,
                columnspan=2,
                sticky="ew",
                pady=(10, 0),
            )
            separator_row = 4
            action_row = 5
        else:
            self.item_details_panel.grid(
                row=2,
                column=0,
                columnspan=1,
                sticky="nsew",
                padx=(0, 6),
                pady=(8, 0),
            )
            self.item_calculation_panel.grid(
                row=2,
                column=1,
                columnspan=1,
                sticky="nsew",
                padx=(6, 0),
                pady=(8, 0),
            )
            separator_row = 3
            action_row = 4
        self.mode_panel.grid(
            row=0,
            column=0,
            columnspan=2,
            sticky="ew",
            pady=(0, 4),
        )
        self.item_photo_cell.grid(
            row=2,
            column=0,
            columnspan=2,
            sticky="ew",
            padx=5,
            pady=5,
        )
        self.rate_hint_cell.grid(
            row=3,
            column=0,
            columnspan=2,
            sticky="ew",
            padx=5,
            pady=5,
        )
        self.item_action_separator.grid(
            row=separator_row,
            column=0,
            columnspan=2,
            sticky="ew",
            pady=(10, 0),
        )
        self.item_action_row.grid(
            row=action_row,
            column=0,
            columnspan=2,
            sticky="ew",
            pady=(8, 0),
        )

    def _resize_workspace(self, event: tk.Event) -> None:
        if event.widget is not self:
            return
        width = max(220, min(340, int(event.width * 0.27)))
        if self.sidebar.winfo_width() != width:
            self.sidebar.configure(width=width)
        if hasattr(self, "sidebar_order_label"):
            self.sidebar_order_label.configure(wraplength=max(160, width - 60))
        if hasattr(self, "sidebar_summary_label"):
            self.sidebar_summary_label.configure(wraplength=max(160, width - 60))
        if hasattr(self, "draft_card"):
            self._apply_sidebar_density(event.height)

    def _apply_sidebar_density(self, window_height: int) -> None:
        # Na niskich oknach chowamy elementy poboczne, aby lista pozycji zawsze miała miejsce.
        show_summary = window_height >= 780
        show_order_details = window_height >= 700
        show_new_order = window_height >= 640
        for widget, visible, options in (
            (self.sidebar_summary_label, show_summary, {"anchor": "w", "pady": (4, 10), "before": self.sidebar_new_order_button}),
            (self.sidebar_order_block, show_order_details, {"fill": "x", "before": self.draft_card}),
            (self.sidebar_new_order_button, show_new_order, {"fill": "x", "pady": (5, 0)}),
        ):
            if visible and not widget.winfo_manager():
                widget.pack(**options)
            elif not visible and widget.winfo_manager():
                widget.pack_forget()

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
    def _form_section_heading(
        parent: tk.Widget,
        title: str,
        background: str = WHITE,
    ) -> tk.Frame:
        heading = tk.Frame(parent, bg=background)
        heading.grid_columnconfigure(1, weight=1)
        tk.Label(
            heading,
            text=title,
            bg=background,
            fg=ACCENT,
            font=("Segoe UI", 8, "bold"),
        ).grid(row=0, column=0, sticky="w", padx=(0, 12))
        tk.Frame(heading, bg=BORDER, height=1).grid(row=0, column=1, sticky="ew")
        return heading

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
        width: int = QUOTE_FIELD_ENTRY_WIDTH,
        show: str | None = None,
        stretch: bool = False,
        background: str = WHITE,
    ) -> ttk.Entry:
        cell = tk.Frame(parent, bg=background)
        cell.grid(row=row, column=column, sticky="ew", padx=5, pady=5)
        tk.Label(cell, text=label, bg=background, fg=MUTED, font=("Segoe UI", 8, "bold")).pack(anchor="w", pady=(0, 3))
        entry = ttk.Entry(cell, textvariable=variable, width=width, show=show)
        entry.pack(fill="x" if stretch else None, anchor="w")
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
        customer_cell.grid(row=0, column=0, sticky="ew", padx=5)
        tk.Label(customer_cell, text="Zleceniodawca", bg=WHITE, fg=MUTED, font=("Segoe UI", 8, "bold")).pack(anchor="w", pady=(0, 3))
        self.customer_combo = ttk.Combobox(
            customer_cell,
            textvariable=self.customer_var,
            width=QUOTE_FIELD_COMBO_WIDTH,
        )
        self.customer_combo.pack(fill="x")
        self.order_number_entry = self._labeled_entry(
            order_body,
            "Numer zamówienia klienta",
            self.order_number_var,
            0,
            1,
            stretch=True,
        )
        self.notes_entry = self._labeled_entry(
            order_body,
            "Uwagi do oferty (opcjonalnie)",
            self.notes_var,
            0,
            2,
            stretch=True,
        )
        item_card, item_body = self._card(
            self.quote_form,
            "Pozycja zamówienia",
            "Dane elementu, materiału i kalkulacji zebrane w czytelne sekcje.",
        )
        self.item_body = item_body
        item_card.pack(fill="x", pady=(0, 12))
        self.calculation_mode_var = tk.StringVar(value="per_piece")
        self.calculation_mode_description = tk.StringVar()
        mode_panel = tk.Frame(
            item_body,
            bg="#F4F7FB",
            highlightthickness=1,
            highlightbackground=BORDER,
            padx=12,
            pady=10,
        )
        self.mode_panel = mode_panel
        mode_panel.grid_columnconfigure(1, weight=1)
        mode_row = tk.Frame(mode_panel, bg="#F4F7FB")
        self.mode_row = mode_row
        mode_row.grid(row=0, column=0, columnspan=2, sticky="ew")
        tk.Label(
            mode_row,
            text="METODA KALKULACJI",
            bg="#F4F7FB",
            fg=MUTED,
            font=("Segoe UI", 8, "bold"),
        ).pack(side="left", padx=(0, 10))
        mode_options = tk.Frame(mode_row, bg="#F4F7FB")
        mode_options.pack(side="right")
        ttk.Radiobutton(
            mode_options,
            text="Cała partia",
            variable=self.calculation_mode_var,
            value="whole_order",
            command=self._update_calculation_form,
            style="Mode.TRadiobutton",
        ).pack(side="left", padx=(0, 6))
        ttk.Radiobutton(
            mode_options,
            text="Na sztukę",
            variable=self.calculation_mode_var,
            value="per_piece",
            command=self._update_calculation_form,
            style="Mode.TRadiobutton",
        ).pack(side="left")
        self.mode_description_label = tk.Label(
            mode_panel,
            textvariable=self.calculation_mode_description,
            bg="#F4F7FB",
            fg=MUTED,
            font=("Segoe UI", 9),
            anchor="w",
            justify="left",
        )
        self.mode_description_label.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(7, 0))
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
        section_background = "#F8FAFC"
        self.item_details_panel = tk.Frame(
            item_body,
            bg=section_background,
            highlightthickness=1,
            highlightbackground=BORDER,
            padx=12,
            pady=10,
        )
        self.item_calculation_panel = tk.Frame(
            item_body,
            bg=section_background,
            highlightthickness=1,
            highlightbackground=BORDER,
            padx=12,
            pady=10,
        )
        for panel in (self.item_details_panel, self.item_calculation_panel):
            for column in range(2):
                panel.grid_columnconfigure(column, weight=1, uniform="item_panel_fields")
        self.item_details_heading = self._form_section_heading(
            self.item_details_panel,
            "01  DANE ELEMENTU",
            section_background,
        )
        self.item_details_heading.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 5))
        self.item_details_body = tk.Frame(self.item_details_panel, bg=section_background)
        self.item_details_body.grid(row=1, column=0, columnspan=2, sticky="ew")
        for column in range(2):
            self.item_details_body.grid_columnconfigure(column, weight=1, uniform="item_detail_fields")
        self.item_calculation_heading = self._form_section_heading(
            self.item_calculation_panel,
            "02  KALKULACJA",
            section_background,
        )
        self.item_calculation_heading.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 5))
        self.item_calculation_body = tk.Frame(self.item_calculation_panel, bg=section_background)
        self.item_calculation_body.grid(row=1, column=0, columnspan=2, sticky="ew")
        for column in range(2):
            self.item_calculation_body.grid_columnconfigure(column, weight=1, uniform="item_calculation_fields")
        self.item_field_cells: dict[str, tk.Widget] = {}
        name_entry = self._labeled_entry(
            self.item_details_body,
            "Nazwa elementu *",
            self.item_vars["element_name"],
            1,
            0,
            stretch=True,
            background=section_background,
        )
        self.item_field_cells["element_name"] = name_entry.master
        name_entry.master.grid_configure(columnspan=2)
        self.item_name_entry = name_entry
        self.item_photo_cell = tk.Frame(self.item_details_body, bg=section_background)
        tk.Label(
            self.item_photo_cell,
            text="Zdjęcie (opcjonalnie)",
            bg=section_background,
            fg=MUTED,
            font=("Segoe UI", 8, "bold"),
        ).pack(anchor="w", pady=(0, 3))
        photo_actions = tk.Frame(self.item_photo_cell, bg=section_background)
        photo_actions.pack(fill="x")
        self.item_photo_button = ttk.Button(
            photo_actions,
            text="Dodaj zdjęcie",
            command=self.choose_item_photo,
        )
        self.item_photo_button.pack(side="left")
        self.item_photo_label = tk.Label(
            photo_actions,
            text="Brak zdjęcia",
            bg=section_background,
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
        self.item_photo_remove_button.configure(state="disabled")
        self.item_photo_image: ImageTk.PhotoImage | None = None
        material_cell = tk.Frame(self.item_details_body, bg=section_background)
        material_cell.grid(row=3, column=0, sticky="ew", padx=5, pady=5)
        tk.Label(
            material_cell,
            text="Materiał / gatunek",
            bg=section_background,
            fg=MUTED,
            font=("Segoe UI", 8, "bold"),
        ).pack(anchor="w", pady=(0, 3))
        self.material_combo = ttk.Combobox(
            material_cell,
            textvariable=self.item_vars["material"],
            width=QUOTE_FIELD_COMBO_WIDTH,
        )
        self.material_combo.pack(anchor="w")
        self.item_field_cells["material"] = material_cell
        self._refresh_material_choices()
        self.item_field_cells["thickness_mm"] = self._labeled_entry(
            self.item_details_body,
            "Grubość (mm)",
            self.item_vars["thickness_mm"],
            3,
            1,
            background=section_background,
        ).master
        self.quantity_cell = tk.Frame(self.item_details_body, bg=section_background)
        self.quantity_label = tk.Label(
            self.quantity_cell,
            text="Ilość (szt.) *",
            bg=section_background,
            fg=MUTED,
            font=("Segoe UI", 8, "bold"),
        )
        self.quantity_label.pack(anchor="w", pady=(0, 3))
        self.quantity_entry = ttk.Entry(
            self.quantity_cell,
            textvariable=self.item_vars["quantity"],
            width=QUOTE_FIELD_ENTRY_WIDTH,
        )
        self.quantity_entry.pack(anchor="w")
        self.quantity_cell.grid(row=4, column=0, sticky="ew", padx=5, pady=5)
        self.weight_entry = self._labeled_entry(
            self.item_details_body,
            "Masa jednej sztuki (kg) *",
            self.item_vars["used_weight_kg"],
            4,
            1,
            background=section_background,
        )
        self.item_field_cells["used_weight_kg"] = self.weight_entry.master
        self.weight_label = self.weight_entry.master.winfo_children()[0]
        price_entry = self._labeled_entry(
            self.item_calculation_body,
            "Cena materiału (zł/kg)",
            self.item_vars["price_per_kg"],
            1,
            1,
            background=section_background,
        )
        self.item_field_cells["price_per_kg"] = price_entry.master
        time_cell = tk.Frame(self.item_calculation_body, bg=section_background)
        self.time_cell = time_cell
        time_cell.grid(row=1, column=0, sticky="ew", padx=5, pady=5)
        self.time_label = tk.Label(time_cell, text="Czas palenia jednej sztuki *", bg=section_background, fg=MUTED, font=("Segoe UI", 8, "bold"))
        self.time_label.pack(anchor="w", pady=(0, 3))
        time_row = tk.Frame(time_cell, bg=section_background)
        time_row.pack(fill="x")
        time_entries = []
        for key, width in (("hours", 4), ("minutes", 3), ("seconds", 3)):
            time_entry = ttk.Entry(time_row, textvariable=self.item_vars[key], width=width, justify="center")
            time_entry.pack(side="left")
            time_entries.append(time_entry)
            time_entry.bind("<FocusIn>", self._clear_zero_duration_on_focus, add="+")
            if key != "seconds":
                tk.Label(time_row, text=":", bg=section_background, fg=MUTED).pack(side="left", padx=4)
        rate_entry = self._labeled_entry(
            self.item_calculation_body,
            "Stawka palenia (zł/godz.)",
            self.item_vars["burning_rate_per_hour"],
            2,
            0,
            background=section_background,
        )
        vat_entry = self._labeled_entry(
            self.item_calculation_body,
            "VAT (%)",
            self.item_vars["vat_percent"],
            2,
            1,
            background=section_background,
        )
        self.item_field_cells["burning_rate_per_hour"] = rate_entry.master
        self.item_field_cells["vat_percent"] = vat_entry.master
        self.rate_hint_cell = tk.Frame(self.item_calculation_body, bg=section_background)
        tk.Label(
            self.rate_hint_cell,
            text="Zmiana stawek\nw Ustawieniach",
            bg=section_background,
            fg=MUTED,
            font=("Segoe UI", 8),
            justify="left",
        ).pack(anchor="w")
        self.item_action_separator = tk.Frame(item_body, bg=BORDER, height=1)
        # Stawki zmienia się tylko w Ustawieniach.
        for locked_entry in (price_entry, rate_entry, vat_entry):
            locked_entry.configure(state="readonly")
        self._item_focus_chain = [
            self.customer_combo,
            self.order_number_entry,
            self.notes_entry,
            self.item_field_cells["element_name"].winfo_children()[1],
            self.material_combo,
            self.item_field_cells["thickness_mm"].winfo_children()[1],
            self.quantity_entry,
            self.weight_entry,
            *time_entries,
        ]
        for chain_widget in self._item_focus_chain:
            chain_widget.bind("<Tab>", lambda event: self._focus_chain_step(event, 1), add="+")
            chain_widget.bind("<Shift-Tab>", lambda event: self._focus_chain_step(event, -1), add="+")
            chain_widget.bind("<ISO_Left_Tab>", lambda event: self._focus_chain_step(event, -1), add="+")
        self.item_action_row = tk.Frame(item_body, bg=WHITE)
        self.add_item_button = ttk.Button(self.item_action_row, text="＋  Dodaj pozycję", style="Primary.TButton", command=self.add_item)
        self.add_item_button.pack(side="right")
        self.add_edited_item_button = ttk.Button(
            self.item_action_row,
            text="＋  Dodaj jako nową pozycję",
            command=self.add_edited_item_as_new,
        )
        self.add_edited_item_button.pack(side="right", padx=(0, 8))
        self.add_edited_item_button.pack_forget()
        self.cancel_item_edit_button = ttk.Button(
            self.item_action_row,
            text="Anuluj edycję",
            command=self.cancel_draft_item_edit,
        )
        self.cancel_item_edit_button.pack(side="right", padx=(0, 8))
        self.cancel_item_edit_button.pack_forget()
        self._place_item_fields(self.quote_layout_compact)
        self._update_calculation_form()

        draft_card, draft_body = self._card(self.sidebar, "Elementy zamówienia")
        self.draft_card = draft_card
        draft_card.pack(fill="both", expand=True, padx=12, pady=(0, 0))
        columns = ("element", "scope", "gross")
        self.draft_tree = ttk.Treeview(draft_body, columns=columns, show="headings", height=3, selectmode="browse")
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
        self.sidebar_footer = footer
        self.summary_var = tk.StringVar(value="Dodaj pozycję, aby zobaczyć podsumowanie.")
        self.gross_var = tk.StringVar(value="—")
        tk.Label(footer, text="WARTOŚĆ BRUTTO", bg=WHITE, fg=MUTED, font=("Segoe UI", 8, "bold")).pack(anchor="w")
        tk.Label(footer, textvariable=self.gross_var, bg=WHITE, fg=ACCENT, font=("Segoe UI", 20, "bold")).pack(anchor="w", pady=(1, 0))
        self.sidebar_summary_label = tk.Label(
            footer,
            textvariable=self.summary_var,
            bg=WHITE,
            fg=MUTED,
            font=("Segoe UI", 8),
            wraplength=260,
            justify="left",
        )
        self.sidebar_summary_label.pack(anchor="w", pady=(4, 10))
        self.sidebar_new_order_button = ttk.Button(footer, text="Nowe zamówienie", style="Quiet.TButton", command=self.clear_form)
        self.sidebar_new_order_button.pack(fill="x", pady=(5, 0))
        footer.pack(side="bottom", fill="x", padx=12, pady=12, before=self.draft_card)
        self._sidebar_density_after_id = self.after_idle(
            lambda: self._apply_sidebar_density(self.winfo_height())
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
        ttk.Button(actions, text="Drukuj ofertę", command=self.print_summary_pdf).pack(side="left", padx=(7, 0))
        ttk.Button(actions, text="Generuj WZ", command=self._open_delivery_note).pack(side="left", padx=(7, 0))
        ttk.Button(actions, text="Kopiuj do nowej", command=self.copy_summary_estimate).pack(side="left", padx=(7, 0))
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
        self._preview_resize_after_id: str | None = None
        self.preview_canvas.bind("<Configure>", self._schedule_estimate_preview)

    def _build_delivery_note_tab(self) -> None:
        self._page_heading(
            self.delivery_note_tab,
            "Wydanie zewnętrzne",
            "Wypełnij dokument ręcznie albo zacznij od danych bieżącej lub zapisanej wyceny.",
        )
        action_bar = tk.Frame(
            self.delivery_note_tab,
            bg=WHITE,
            padx=14,
            pady=9,
            highlightthickness=1,
            highlightbackground=BORDER,
        )
        action_bar.pack(side="bottom", fill="x", pady=(8, 0))
        ttk.Button(
            action_bar,
            text="←  Wróć",
            command=self._return_from_delivery_note,
        ).pack(side="left")
        ttk.Button(
            action_bar,
            text="Drukuj WZ",
            command=self.print_delivery_note,
        ).pack(side="right", padx=(0, 8))
        ttk.Button(
            action_bar,
            text="Podgląd / zapisz PDF",
            style="Primary.TButton",
            command=self._preview_delivery_note,
        ).pack(side="right")
        ttk.Button(
            action_bar,
            text="+  Dodaj pozycję",
            command=self._add_delivery_note_row,
        ).pack(side="right", padx=(0, 8))
        ttk.Button(
            action_bar,
            text="Nowe WZ",
            style="Quiet.TButton",
            command=self._start_new_delivery_note,
        ).pack(side="right", padx=(0, 8))

        self.delivery_note_form = tk.Frame(self.delivery_note_tab, bg=BACKGROUND)
        self.delivery_note_form.pack(fill="both", expand=True)
        header_card, header_body = self._card(
            self.delivery_note_form,
            "Dane dokumentu i odbiorcy",
            "Numer WZ jest tworzony z numeru zamówienia klienta.",
        )
        header_card.pack(fill="x", pady=(0, 8))
        self.delivery_note_variables = {
            "document_number": tk.StringVar(),
            "date": tk.StringVar(),
            "customer_name": tk.StringVar(),
            "customer_tax_id": tk.StringVar(),
            "order_number": tk.StringVar(),
            "delivery_address": tk.StringVar(value="odbiór własny"),
            "issuer": tk.StringVar(),
            "receiver": tk.StringVar(),
        }
        for column in range(2):
            header_body.grid_columnconfigure(column, weight=1, uniform="delivery_header")
        delivery_fields = (
            ("document_number", "Numer dokumentu WZ"),
            ("date", "Data wydania"),
            ("customer_name", "Odbiorca"),
            ("customer_tax_id", "NIP odbiorcy"),
            ("order_number", "Numer zamówienia"),
            ("delivery_address", "Adres dostawy"),
        )
        for index, (key, label) in enumerate(delivery_fields):
            cell = tk.Frame(header_body, bg=WHITE)
            cell.grid(
                row=index // 2,
                column=index % 2,
                sticky="ew",
                padx=(0 if index % 2 == 0 else 8, 0),
                pady=4,
            )
            cell.grid_columnconfigure(0, weight=1)
            tk.Label(
                cell,
                text=label,
                bg=WHITE,
                fg=MUTED,
                font=("Segoe UI", 8, "bold"),
            ).grid(row=0, column=0, sticky="w", pady=(0, 3))
            entry = ttk.Entry(cell, textvariable=self.delivery_note_variables[key])
            entry.grid(row=1, column=0, sticky="ew")

        positions_card, positions_body = self._card(
            self.delivery_note_form,
            "Pozycje wydania",
            "Edytuj dane wydania niezależnie od oferty; dodatkowe elementy dodaj przyciskiem poniżej.",
        )
        positions_card.pack(fill="both", expand=True, pady=(0, 8))
        columns = (
            ("product", "Produkt", 12, 2),
            ("description", "Opis", 18, 3),
            ("description2", "Opis 2", 18, 3),
            ("quantity", "Ilość", 7, 1),
            ("unit", "jm", 5, 1),
            ("notes", "Uwagi", 16, 3),
        )
        header = tk.Frame(positions_body, bg="#E8EFF8")
        self.delivery_note_columns = columns
        self.delivery_note_header = header
        self.delivery_note_header_labels: list[tk.Label] = []
        for column, (_key, label, _width, weight) in enumerate(columns):
            header.grid_columnconfigure(
                column,
                weight=weight,
                uniform="delivery_note_columns",
            )
            heading_label = tk.Label(
                header,
                text=label,
                bg="#E8EFF8",
                fg=INK,
                font=("Segoe UI", 8, "bold"),
                anchor="center",
                padx=2,
                pady=5,
            )
            heading_label.grid(row=0, column=column, sticky="ew")
            self.delivery_note_header_labels.append(heading_label)
        self.delivery_note_header_action_label = tk.Label(
            header,
            text="",
            bg="#E8EFF8",
        )
        self.delivery_note_header_action_label.grid(
            row=0,
            column=len(columns),
            sticky="ew",
            padx=(2, 0),
        )
        rows_container = tk.Frame(positions_body, bg=WHITE)
        positions_body.grid_columnconfigure(0, weight=1)
        positions_body.grid_rowconfigure(1, weight=1)
        header.grid(row=0, column=0, sticky="ew")
        rows_container.grid(row=1, column=0, sticky="nsew")
        self.delivery_note_rows_canvas = tk.Canvas(
            rows_container,
            bg=WHITE,
            highlightthickness=0,
            height=175,
        )
        rows_scrollbar = ttk.Scrollbar(
            rows_container,
            orient="vertical",
            command=self.delivery_note_rows_canvas.yview,
        )
        header.grid_configure(padx=(0, rows_scrollbar.winfo_reqwidth()))
        self.delivery_note_rows_canvas.configure(yscrollcommand=rows_scrollbar.set)
        self.delivery_note_rows_canvas.pack(side="left", fill="both", expand=True)
        rows_scrollbar.pack(side="right", fill="y")
        self.delivery_note_rows_frame = tk.Frame(self.delivery_note_rows_canvas, bg=WHITE)
        self.delivery_note_rows_window = self.delivery_note_rows_canvas.create_window(
            (0, 0),
            window=self.delivery_note_rows_frame,
            anchor="nw",
        )
        self.delivery_note_rows_frame.bind(
            "<Configure>",
            lambda _event: self.delivery_note_rows_canvas.configure(
                scrollregion=self.delivery_note_rows_canvas.bbox("all")
            ),
        )
        self.delivery_note_rows_canvas.bind(
            "<Configure>",
            lambda event: self.delivery_note_rows_canvas.itemconfigure(
                self.delivery_note_rows_window,
                width=event.width,
            ),
        )

        sign_card, sign_body = self._card(
            self.delivery_note_form,
            "Wydanie, odbiór i opakowania",
        )
        sign_card.pack(fill="x")
        for column in range(2):
            sign_body.grid_columnconfigure(column, weight=1, uniform="delivery_sign")
        for column, (key, label) in enumerate(
            (("issuer", "Osoba wydająca"), ("receiver", "Osoba odbierająca"))
        ):
            cell = tk.Frame(sign_body, bg=WHITE)
            cell.grid(row=0, column=column, sticky="ew", padx=(0 if column == 0 else 8, 0))
            tk.Label(cell, text=label, bg=WHITE, fg=MUTED, font=("Segoe UI", 8, "bold")).pack(anchor="w", pady=(0, 3))
            ttk.Entry(cell, textvariable=self.delivery_note_variables[key]).pack(fill="x")
        self.issued_packages_text = self._labeled_text(
            sign_body,
            "Wydano opakowania",
            1,
            0,
        )
        self.returned_packages_text = self._labeled_text(
            sign_body,
            "Zdano opakowania",
            1,
            1,
        )
        for variable in self.delivery_note_variables.values():
            variable.trace_add("write", self._schedule_delivery_note_draft_save)
        self.issued_packages_text.bind("<KeyRelease>", self._schedule_delivery_note_draft_save, add="+")
        self.returned_packages_text.bind("<KeyRelease>", self._schedule_delivery_note_draft_save, add="+")
        self.issued_packages_text.bind("<<Paste>>", self._schedule_delivery_note_draft_save, add="+")
        self.returned_packages_text.bind("<<Paste>>", self._schedule_delivery_note_draft_save, add="+")
        self.issued_packages_text.bind("<<Cut>>", self._schedule_delivery_note_draft_save, add="+")
        self.returned_packages_text.bind("<<Cut>>", self._schedule_delivery_note_draft_save, add="+")

    def _build_pdf_preview_tab(self) -> None:
        self._page_heading(
            self.pdf_preview_tab,
            "Podgląd dokumentu PDF",
            "Podgląd oferty i dokumentu WZ jest wyświetlany bezpośrednio w aplikacji.",
        )
        actions = tk.Frame(self.pdf_preview_tab, bg=BACKGROUND)
        actions.pack(fill="x", pady=(0, 10))
        self.pdf_preview_back_button = ttk.Button(
            actions,
            text="←  Wróć do dokumentu",
            command=self._return_from_pdf_preview,
        )
        self.pdf_preview_back_button.pack(side="left")
        self.pdf_preview_save_button = ttk.Button(
            actions,
            text="Zapisz PDF…",
            style="Primary.TButton",
            command=self._save_current_document_preview,
        )
        self.pdf_preview_save_button.pack(side="right")
        self.pdf_preview_print_button = ttk.Button(
            actions,
            text="Drukuj",
            command=self._print_current_document_preview,
        )
        self.pdf_preview_print_button.pack(side="right", padx=(0, 8))
        self.pdf_preview_status = tk.StringVar(value="")
        ttk.Label(
            actions,
            textvariable=self.pdf_preview_status,
            style="Subtitle.TLabel",
        ).pack(side="right", padx=(0, 12))
        preview_card, preview_body = self._card(
            self.pdf_preview_tab,
            "Dokument",
            "Sprawdź wszystkie strony przed zapisaniem pliku.",
        )
        preview_card.pack(fill="both", expand=True)
        preview_frame = tk.Frame(preview_body, bg="#E7EDF4")
        preview_frame.pack(fill="both", expand=True)
        self.pdf_preview_canvas = tk.Canvas(
            preview_frame,
            bg="#E7EDF4",
            highlightthickness=0,
            borderwidth=0,
        )
        scrollbar = ttk.Scrollbar(
            preview_frame,
            orient="vertical",
            command=self.pdf_preview_canvas.yview,
        )
        self.pdf_preview_canvas.configure(yscrollcommand=scrollbar.set)
        self.pdf_preview_canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self.pdf_preview_canvas.bind(
            "<Configure>",
            self._schedule_document_preview_render,
        )
        self._pdf_preview_resize_after_id: str | None = None

    @staticmethod
    def _labeled_text(
        parent: tk.Widget,
        label: str,
        row: int,
        column: int,
    ) -> tk.Text:
        cell = tk.Frame(parent, bg=WHITE)
        cell.grid(row=row, column=column, sticky="ew", padx=(0 if column == 0 else 8, 0), pady=(8, 0))
        tk.Label(cell, text=label, bg=WHITE, fg=MUTED, font=("Segoe UI", 8, "bold")).pack(anchor="w", pady=(0, 3))
        text = tk.Text(cell, height=2, wrap="word", relief="solid", borderwidth=1, font=("Segoe UI", 9))
        text.pack(fill="x")
        return text

    def _open_delivery_note_from_navigation(self) -> None:
        if self.current_page == "delivery_note":
            self._show_page("delivery_note")
            return
        if self.delivery_note_initialized:
            self.delivery_note_return_page = self.current_page
            self._show_page("delivery_note")
            return
        if self.current_page == "history":
            selected = self.history_tree.selection()
            if selected:
                estimate = self._selected_estimate()
                if estimate is None:
                    return
                self._open_delivery_note(estimate, return_page="history")
                return
            self._open_new_delivery_note(return_page="history")
            return
        if self.current_page == "summary" and self.summary_estimate is not None:
            self._open_delivery_note(self.summary_estimate, return_page="summary")
            return
        if self.current_page == "quote" and self.editing_estimate_id is not None:
            try:
                estimate = self.storage.get_estimate(self.user_id, self.editing_estimate_id)
            except sqlite3.Error as error:
                messagebox.showerror(
                    "Błąd bazy danych",
                    f"Nie udało się odczytać zapisanej wyceny:\n{error}",
                    parent=self,
                )
                return
            if estimate is None:
                messagebox.showerror(
                    "Generowanie WZ",
                    "Nie znaleziono zapisanej wyceny. Możesz utworzyć nowe WZ ręcznie.",
                    parent=self,
                )
                return
            self._open_delivery_note(estimate, return_page="quote")
            return
        self._open_new_delivery_note(
            seed_from_quote=self.current_page == "quote",
            return_page=self.current_page,
        )

    def _open_delivery_note(
        self,
        estimate: dict[str, Any] | None = None,
        return_page: str | None = None,
    ) -> None:
        estimate = estimate or self.summary_estimate
        if estimate is None:
            return
        self.delivery_note_return_page = return_page or self.current_page
        self.summary_estimate = estimate
        self.navigation_buttons["summary"].configure(state="normal")
        header = estimate["header"]
        estimate_id = int(header["id"])
        if self.delivery_note_estimate_id != estimate_id:
            order_number = str(header.get("order_number", "")).strip()
            values = {
                "document_number": f"WZ-{order_number}",
                "date": datetime.now().astimezone().strftime("%d.%m.%Y"),
                "customer_name": str(header.get("customer_name", "")),
                "customer_tax_id": str(header.get("customer_tax_id", "")),
                "order_number": order_number,
                "delivery_address": "odbiór własny",
                "issuer": "",
                "receiver": "",
            }
            for key, value in values.items():
                self.delivery_note_variables[key].set(value)
            self.issued_packages_text.delete("1.0", "end")
            self.returned_packages_text.delete("1.0", "end")
            for row in self.delivery_note_rows[:]:
                row["frame"].destroy()
            self.delivery_note_rows.clear()
            for item in estimate["items"]:
                self._add_delivery_note_row(self._delivery_note_item_from_quote(item))
            self.delivery_note_estimate_id = estimate_id
        self.delivery_note_initialized = True
        self._schedule_delivery_note_draft_save()
        self._show_page("delivery_note")

    @staticmethod
    def _delivery_note_item_from_quote(item: dict[str, Any]) -> dict[str, str]:
        description2 = str(item.get("material", "")).strip()
        thickness = str(item.get("thickness_mm", "")).strip()
        if thickness:
            description2 = f"{description2} · {thickness} mm" if description2 else f"{thickness} mm"
        return {
            "product": "Element cięty",
            "description": str(item.get("element_name", "")),
            "description2": description2,
            "quantity": str(item.get("quantity", "1")),
            "unit": "szt",
            "notes": "",
        }

    def _open_new_delivery_note(
        self,
        seed_from_quote: bool = False,
        return_page: str | None = None,
    ) -> None:
        self.delivery_note_return_page = return_page or self.current_page
        order_number = self.order_number_var.get().strip() if seed_from_quote else ""
        values = {
            "document_number": f"WZ-{order_number}" if order_number else "",
            "date": datetime.now().astimezone().strftime("%d.%m.%Y"),
            "customer_name": self.customer_var.get().strip() if seed_from_quote else "",
            "customer_tax_id": "",
            "order_number": order_number,
            "delivery_address": "odbiór własny",
            "issuer": "",
            "receiver": "",
        }
        for key, value in values.items():
            self.delivery_note_variables[key].set(value)
        self.issued_packages_text.delete("1.0", "end")
        self.returned_packages_text.delete("1.0", "end")
        for row in self.delivery_note_rows[:]:
            row["frame"].destroy()
        self.delivery_note_rows.clear()
        items = self.draft_items if seed_from_quote else []
        for item in items:
            self._add_delivery_note_row(self._delivery_note_item_from_quote(item))
        if not items:
            self._add_delivery_note_row({
                "product": "",
                "description": "",
                "description2": "",
                "quantity": "1",
                "unit": "szt",
                "notes": "",
            })
        self.delivery_note_estimate_id = None
        self.delivery_note_initialized = True
        self._schedule_delivery_note_draft_save()
        self._show_page("delivery_note")

    def _return_from_delivery_note(self) -> None:
        if self.delivery_note_return_page in ("quote", "history", "customers", "summary"):
            self._show_page(self.delivery_note_return_page)
        else:
            self._show_page("quote")

    def _add_delivery_note_row(self, values: dict[str, str] | None = None) -> None:
        values = values or {
            "product": "Element cięty",
            "description": "",
            "description2": "",
            "quantity": "1",
            "unit": "szt",
            "notes": "",
        }
        row_frame = tk.Frame(
            self.delivery_note_rows_frame,
            bg=WHITE if len(self.delivery_note_rows) % 2 == 0 else "#F7F9FC",
        )
        row_frame.pack(fill="x")
        row_fields: dict[str, Any] = {"frame": row_frame}
        columns = (
            ("product", 12, 2),
            ("description", 18, 3),
            ("description2", 18, 3),
            ("quantity", 7, 1),
            ("unit", 5, 1),
            ("notes", 16, 3),
        )
        for column, (key, _width, weight) in enumerate(columns):
            row_frame.grid_columnconfigure(
                column,
                weight=weight,
                minsize=0,
                uniform="delivery_note_columns",
            )
            variable = tk.StringVar(value=str(values.get(key, "")))
            entry = ttk.Entry(row_frame, textvariable=variable, width=1)
            entry.grid(row=0, column=column, sticky="ew", padx=2, pady=2)
            minimum_width = max(
                entry.winfo_reqwidth(),
                self.delivery_note_header_labels[column].winfo_reqwidth(),
            ) + 4
            row_frame.grid_columnconfigure(column, minsize=minimum_width)
            self.delivery_note_header.grid_columnconfigure(column, minsize=minimum_width)
            row_fields[key] = variable
        remove = ttk.Button(
            row_frame,
            text="Usuń",
            style="Quiet.TButton",
            command=lambda: self._remove_delivery_note_row(row_fields),
        )
        remove.grid(row=0, column=len(columns), padx=(2, 0), sticky="ew")
        action_width = remove.winfo_reqwidth() + 2
        row_frame.grid_columnconfigure(len(columns), minsize=action_width)
        self.delivery_note_header.grid_columnconfigure(len(columns), minsize=action_width)
        row_fields["remove"] = remove
        self.delivery_note_rows.append(row_fields)
        for key in ("product", "description", "description2", "quantity", "unit", "notes"):
            row_fields[key].trace_add("write", self._schedule_delivery_note_draft_save)
        self._schedule_delivery_note_draft_save()

    def _remove_delivery_note_row(self, row: dict[str, Any]) -> None:
        self.delivery_note_rows.remove(row)
        row["frame"].destroy()
        self._schedule_delivery_note_draft_save()

    def _start_new_delivery_note(self) -> None:
        if self.delivery_note_initialized and not messagebox.askyesno(
            "Nowe WZ",
            "Rozpocząć nowy dokument? Bieżący szkic zostanie zastąpiony.",
            parent=self,
        ):
            return
        self._open_new_delivery_note(
            seed_from_quote=self.current_page == "quote",
            return_page=self.current_page,
        )

    def _schedule_delivery_note_draft_save(self, *_args: object) -> None:
        if self._restoring_delivery_note_draft or not self.delivery_note_initialized:
            return
        if self._delivery_note_save_after_id is not None:
            self.after_cancel(self._delivery_note_save_after_id)
        self._delivery_note_save_after_id = self.after(
            600,
            self._save_delivery_note_draft_after_delay,
        )

    def _save_delivery_note_draft_after_delay(self) -> None:
        self._delivery_note_save_after_id = None
        self.save_delivery_note_draft(show_error=not self._delivery_note_draft_error_shown)

    def save_delivery_note_draft(self, show_error: bool = True) -> bool:
        if self._delivery_note_save_after_id is not None:
            self.after_cancel(self._delivery_note_save_after_id)
            self._delivery_note_save_after_id = None
        if not self.delivery_note_initialized:
            return True
        try:
            data = self._delivery_note_data()
            self.storage.save_settings(
                self.user_id,
                {
                    DELIVERY_NOTE_DRAFT_SETTING: json.dumps(
                        {
                            "values": {
                                key: data[key]
                                for key in self.delivery_note_variables
                            },
                            "issued_packages": data["issued_packages"],
                            "returned_packages": data["returned_packages"],
                            "items": data["items"],
                        },
                        ensure_ascii=False,
                    )
                },
            )
        except (OSError, sqlite3.Error) as error:
            if show_error:
                messagebox.showerror(
                    "Szkic WZ",
                    f"Nie udało się zapisać roboczego dokumentu WZ:\n{error}",
                    parent=self,
                )
            self._delivery_note_draft_error_shown = True
            return False
        self._delivery_note_draft_error_shown = False
        return True

    def _restore_delivery_note_draft(self) -> None:
        raw_draft = self.settings.get(DELIVERY_NOTE_DRAFT_SETTING, "")
        if not raw_draft:
            return
        try:
            draft = json.loads(raw_draft)
            if not isinstance(draft, dict) or not isinstance(draft.get("items"), list):
                raise ValueError("Nieprawidłowy format szkicu.")
            values = draft.get("values", {})
            if not isinstance(values, dict):
                raise ValueError("Nieprawidłowe dane nagłówka szkicu.")
        except (TypeError, ValueError) as error:
            messagebox.showwarning(
                "Szkic WZ",
                f"Nie udało się odczytać zapisanego szkicu WZ:\n{error}",
                parent=self,
            )
            return
        self._restoring_delivery_note_draft = True
        try:
            for key, variable in self.delivery_note_variables.items():
                variable.set(str(values.get(key, "")))
            self.issued_packages_text.insert("1.0", str(draft.get("issued_packages", "")))
            self.returned_packages_text.insert("1.0", str(draft.get("returned_packages", "")))
            for row in self.delivery_note_rows[:]:
                row["frame"].destroy()
            self.delivery_note_rows.clear()
            for item in draft["items"]:
                if isinstance(item, dict):
                    self._add_delivery_note_row(
                        {key: str(item.get(key, "")) for key in (
                            "product", "description", "description2", "quantity", "unit", "notes"
                        )}
                    )
            if not self.delivery_note_rows:
                self._add_delivery_note_row({
                    "product": "",
                    "description": "",
                    "description2": "",
                    "quantity": "1",
                    "unit": "szt",
                    "notes": "",
                })
            self.delivery_note_initialized = True
            self.delivery_note_estimate_id = None
        finally:
            self._restoring_delivery_note_draft = False

    def _delivery_note_data(self) -> dict[str, Any]:
        return {
            **{
                key: variable.get().strip()
                for key, variable in self.delivery_note_variables.items()
            },
            "issued_packages": self.issued_packages_text.get("1.0", "end-1c").strip(),
            "returned_packages": self.returned_packages_text.get("1.0", "end-1c").strip(),
            "items": [
                {
                    key: row[key].get().strip()
                    for key in ("product", "description", "description2", "quantity", "unit", "notes")
                }
                for row in self.delivery_note_rows
            ],
        }

    def _preview_delivery_note(self) -> None:
        self.delivery_note_initialized = True
        self._schedule_delivery_note_draft_save()
        data = self._delivery_note_data()
        try:
            output = BytesIO()
            export_delivery_note_pdf(data, self.settings, output)
        except (OSError, ValueError, ImportError, RuntimeError) as error:
            messagebox.showerror(
                "Podgląd dokumentu WZ",
                f"Nie udało się przygotować podglądu PDF:\n{error}",
                parent=self,
            )
            return
        self._show_delivery_note_preview(data, output.getvalue())

    def _show_delivery_note_preview(self, data: dict[str, Any], pdf_data: bytes) -> None:
        try:
            import pymupdf

            document = pymupdf.open(stream=pdf_data, filetype="pdf")
        except (ImportError, OSError, RuntimeError, ValueError) as error:
            messagebox.showerror(
                "Podgląd dokumentu WZ",
                f"Nie udało się otworzyć podglądu PDF:\n{error}",
                parent=self,
            )
            return
        if document.page_count == 0:
            document.close()
            messagebox.showerror(
                "Podgląd dokumentu WZ",
                "Generator nie utworzył żadnej strony dokumentu.",
                parent=self,
            )
            return
        page_count = document.page_count
        document.close()
        self._pdf_preview_bytes = pdf_data
        self._pdf_preview_return_page = "delivery_note"
        self._pdf_preview_save_action = lambda: self._save_delivery_note_pdf(data)
        self._pdf_preview_print_action = lambda: self._print_pdf_bytes(
            pdf_data,
            f"WZ {data['document_number']}",
        )
        self.pdf_preview_status.set(
            f"WZ {data['document_number']}  ·  {data['customer_name']}  ·  {page_count} str."
        )
        self.pdf_preview_save_button.configure(text="Zapisz WZ PDF…")
        self._show_page("pdf_preview")

    def _schedule_document_preview_render(self, _event: tk.Event | None = None) -> None:
        if self._pdf_preview_resize_after_id is not None:
            self.after_cancel(self._pdf_preview_resize_after_id)
        self._pdf_preview_resize_after_id = self.after(
            100,
            self._render_document_preview,
        )

    def _render_document_preview(self) -> None:
        self._pdf_preview_render_after_id = None
        self._pdf_preview_resize_after_id = None
        if self._pdf_preview_bytes is None:
            return
        try:
            self._render_pdf_pages_to_canvas(
                self._pdf_preview_bytes,
                self.pdf_preview_canvas,
                self._pdf_preview_images,
            )
        except (ImportError, OSError, RuntimeError, ValueError) as error:
            messagebox.showerror(
                "Podgląd dokumentu PDF",
                f"Nie udało się wyświetlić dokumentu:\n{error}",
                parent=self,
            )

    def _return_from_pdf_preview(self) -> None:
        self._show_page(self._pdf_preview_return_page)

    def _save_current_document_preview(self) -> None:
        if hasattr(self, "_pdf_preview_save_action"):
            self._pdf_preview_save_action()

    def _print_current_document_preview(self) -> None:
        if self._pdf_preview_print_action is not None:
            self._pdf_preview_print_action()

    def print_delivery_note(self) -> None:
        data = self._delivery_note_data()
        try:
            output = BytesIO()
            export_delivery_note_pdf(data, self.settings, output)
        except (OSError, ValueError, ImportError, RuntimeError) as error:
            messagebox.showerror(
                "Drukowanie WZ",
                f"Nie udało się przygotować dokumentu do druku:\n{error}",
                parent=self,
            )
            return
        self.save_delivery_note_draft()
        self._print_pdf_bytes(output.getvalue(), f"WZ {data['document_number']}")

    def _print_pdf_bytes(self, pdf_data: bytes, document_label: str) -> None:
        open_file = getattr(os, "startfile", None)
        if open_file is None:
            messagebox.showerror(
                "Drukowanie PDF",
                "Drukowanie bezpośrednie jest dostępne w systemie Windows.",
                parent=self,
            )
            return
        try:
            print_directory = Path(tempfile.gettempdir()) / "BlachCalc" / "print_jobs"
            print_directory.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                mode="wb",
                prefix="BlachCalc-print-",
                suffix=".pdf",
                dir=print_directory,
                delete=False,
            ) as temporary_file:
                temporary_file.write(pdf_data)
                print_path = Path(temporary_file.name)
            open_file(str(print_path), "print")
        except (OSError, ValueError) as error:
            if "print_path" in locals():
                try:
                    print_path.unlink(missing_ok=True)
                except OSError:
                    pass
            messagebox.showerror(
                "Drukowanie PDF",
                f"Nie udało się przekazać dokumentu do domyślnej drukarki:\n{error}",
                parent=self,
            )
            return
        messagebox.showinfo(
            "Drukowanie PDF",
            f"Dokument {document_label} przekazano do domyślnej aplikacji PDF "
            "z poleceniem drukowania. Plik roboczy zostanie usunięty przy "
            "kolejnym uruchomieniu aplikacji, gdy będzie starszy niż 24 godziny.",
            parent=self,
        )

    @staticmethod
    def _cleanup_stale_print_jobs() -> None:
        print_directory = Path(tempfile.gettempdir()) / "BlachCalc" / "print_jobs"
        if not print_directory.is_dir():
            return
        cutoff = datetime.now().timestamp() - 24 * 60 * 60
        failed_files: list[Path] = []
        for print_file in print_directory.glob("BlachCalc-print-*.pdf"):
            try:
                if print_file.stat().st_mtime < cutoff:
                    print_file.unlink()
            except OSError:
                failed_files.append(print_file)
        if failed_files:
            messagebox.showwarning(
                "Pliki drukowania",
                "Nie udało się usunąć niektórych starych plików roboczych:\n"
                + "\n".join(str(path) for path in failed_files),
            )

    def _save_delivery_note_pdf(self, data: dict[str, Any], preview: tk.Misc | None = None) -> None:
        parent = preview or self
        try:
            WZ_EXPORT_DIRECTORY.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            messagebox.showerror(
                "Folder dokumentów WZ",
                f"Nie można przygotować domyślnego folderu zapisu:\n{WZ_EXPORT_DIRECTORY}\n\n{error}",
                parent=parent,
            )
            return

        safe_filename = "".join(
            character if character.isalnum() or character in "-_." else "_"
            for character in f"{data['document_number']}_{data['customer_name']}"
        ).strip("._")
        filename = filedialog.asksaveasfilename(
            parent=parent,
            title="Zapisz dokument WZ",
            initialdir=str(WZ_EXPORT_DIRECTORY),
            initialfile=f"{safe_filename or 'WZ'}.pdf",
            defaultextension=".pdf",
            confirmoverwrite=True,
            filetypes=[("Dokument PDF", "*.pdf")],
        )
        if not filename:
            return
        try:
            export_delivery_note_pdf(data, self.settings, filename)
        except (OSError, ValueError, ImportError, RuntimeError) as error:
            messagebox.showerror(
                "Zapisywanie dokumentu WZ",
                f"Nie udało się zapisać pliku PDF:\n{filename}\n\n{error}",
                parent=parent,
            )
            return
        messagebox.showinfo(
            "Wydanie zewnętrzne",
            f"Zapisano dokument WZ:\n{filename}",
            parent=parent,
        )

    def _schedule_estimate_preview(self, _event: tk.Event | None = None) -> None:
        if self.summary_estimate is None:
            return
        if self._preview_resize_after_id is not None:
            self.after_cancel(self._preview_resize_after_id)
        self._preview_resize_after_id = self.after(100, self._render_scheduled_estimate_preview)

    def _render_scheduled_estimate_preview(self) -> None:
        self._preview_resize_after_id = None
        self._render_estimate_preview()

    def _render_estimate_preview(self) -> None:
        if not hasattr(self, "preview_canvas") or self.summary_estimate is None:
            return
        try:
            document_stream = BytesIO()
            export_estimate_pdf(
                self.summary_estimate,
                self.settings,
                document_stream,
                "offer",
            )
            self._render_pdf_pages_to_canvas(
                document_stream.getvalue(),
                self.preview_canvas,
                self.preview_page_images,
            )
        except (ImportError, OSError, ValueError, RuntimeError) as error:
            messagebox.showerror(
                "Podgląd oferty",
                f"Nie udało się przygotować podglądu PDF:\n{error}",
                parent=self,
            )
            return

    @staticmethod
    def _render_pdf_pages_to_canvas(
        pdf_data: bytes,
        canvas: tk.Canvas,
        page_images: list[ImageTk.PhotoImage],
    ) -> None:
        import pymupdf

        previous_scroll_position = canvas.yview()[0]
        document = pymupdf.open(stream=pdf_data, filetype="pdf")
        try:
            if document.page_count == 0:
                raise ValueError("Dokument PDF nie zawiera stron.")
            canvas.delete("all")
            page_images.clear()
            display_width = max(1, canvas.winfo_width() - 40)
            y = 16
            page_gap = 20
            page_width = 0
            for page in document:
                zoom = min(1.5, display_width / page.rect.width)
                pixmap = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=False)
                rendered_page = Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)
                page_image = ImageTk.PhotoImage(rendered_page)
                page_images.append(page_image)
                page_width = max(page_width, pixmap.width)
                left = max(20, (canvas.winfo_width() - pixmap.width) // 2)
                canvas.create_image(left, y, image=page_image, anchor="nw")
                y += pixmap.height + page_gap
            canvas.configure(
                scrollregion=(
                    0,
                    0,
                    max(canvas.winfo_width(), page_width + 40),
                    y,
                )
            )
            canvas.yview_moveto(previous_scroll_position)
        finally:
            document.close()

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
            self.quantity_label.configure(text="Ilość gotowych (szt.) *")
            self.weight_label.configure(text="Masa całej partii (kg) *")
            self.time_label.configure(text="Czas palenia partii *")
            self.calculation_mode_description.set(
                "Wpisz łączną masę i czas palenia całej partii oraz końcową liczbę gotowych sztuk. Ilość nie zmienia kosztu partii."
            )
        else:
            self.quantity_label.configure(text="Ilość (szt.) *")
            self.weight_label.configure(text="Masa 1 szt. (kg) *")
            self.time_label.configure(text="Czas palenia 1 szt. *")
            self.calculation_mode_description.set(
                "Wpisz masę i czas jednej sztuki oraz ilość. Koszt jednostkowy zostanie przemnożony przez liczbę sztuk."
            )
        self.add_item_button.configure(text=button_text)
        if self.editing_draft_index is None:
            self.add_edited_item_button.pack_forget()
        else:
            self.add_edited_item_button.pack(side="right", padx=(0, 8))

    def _build_item_from_form(self) -> dict[str, Any]:
        values = {key: variable.get().strip() for key, variable in self.item_vars.items()}
        if not values["element_name"]:
            raise FieldValidationError("Podaj nazwę elementu.", "element_name")
        calculation_mode = self.calculation_mode_var.get()
        try:
            quantity = int(values["quantity"])
        except ValueError as error:
            raise FieldValidationError("Ilość musi być dodatnią liczbą całkowitą.", "quantity") from error
        if quantity < 1 or quantity > 1_000_000:
            raise FieldValidationError("Ilość musi mieścić się w zakresie od 1 do 1 000 000 sztuk.", "quantity")
        weight_label = "Masa całej partii" if calculation_mode == "whole_order" else "Masa jednej sztuki"

        def parse_field(field: str, label: str) -> Decimal:
            try:
                return parse_decimal(values[field], label)
            except ValueError as error:
                raise FieldValidationError(str(error), field) from error

        price = parse_field("price_per_kg", "Cena materiału za kg")
        weight = parse_field("used_weight_kg", weight_label)
        rate = parse_field("burning_rate_per_hour", "Stawka palenia")
        vat = parse_field("vat_percent", "VAT")
        try:
            duration_seconds = parse_duration(values["hours"], values["minutes"], values["seconds"])
        except ValueError as error:
            raise FieldValidationError(str(error), "hours") from error
        if calculation_mode == "whole_order" and weight <= 0:
            raise FieldValidationError("Masa całej partii musi być większa od zera.", "used_weight_kg")
        try:
            quote = calculate_quote(price, weight, duration_seconds, rate, vat)
        except ValueError as error:
            raise FieldValidationError(str(error)) from error
        line_net, line_vat, line_gross = calculate_item_line_amounts(
            quote.net_total,
            quote.vat_amount,
            quote.gross_total,
            quantity,
            calculation_mode,
        )
        if max(line_net, line_vat, line_gross) > Decimal("1000000000000"):
            raise FieldValidationError("Wartość pozycji nie może przekraczać 1 000 000 000 000 zł.", "price_per_kg")
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
            self.item_photo_remove_button.configure(state="normal")
        else:
            self.item_photo_label.configure(image="", text="Brak zdjęcia", compound="left")
            self.item_photo_remove_button.configure(state="disabled")

    def clear_item_photo(self) -> None:
        self._begin_quote_change()
        self._set_item_photo(None)
        self._end_quote_change()

    def add_item(self) -> None:
        try:
            item = self._build_item_from_form()
        except ValueError as error:
            self._show_validation_error("Sprawdź pozycję", error)
            return
        self._clear_all_invalid()
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

    def add_edited_item_as_new(self) -> None:
        if self.editing_draft_index is None:
            return
        try:
            item = self._build_item_from_form()
        except ValueError as error:
            self._show_validation_error("Sprawdź pozycję", error)
            return
        self._clear_all_invalid()
        self._begin_quote_change()
        self.draft_items.append(item)
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
        window.resizable(True, True)
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        window.minsize(
            min(480, screen_width - 40),
            min(360, screen_height - 80),
        )
        window.geometry(
            f"{min(820, screen_width - 40)}x{min(620, screen_height - 80)}"
        )
        image_canvas = tk.Canvas(window, bg="#E7EDF4", highlightthickness=0)
        image_canvas.pack(fill="both", expand=True, padx=12, pady=12)
        window.preview_image = None

        def render_image(_event: tk.Event | None = None) -> None:
            available_width = max(1, image_canvas.winfo_width() - 20)
            available_height = max(1, image_canvas.winfo_height() - 20)
            resized = preview.copy()
            resized.thumbnail((available_width, available_height), Image.Resampling.LANCZOS)
            window.preview_image = ImageTk.PhotoImage(resized)
            image_canvas.delete("all")
            image_canvas.create_image(
                image_canvas.winfo_width() // 2,
                image_canvas.winfo_height() // 2,
                image=window.preview_image,
                anchor="center",
            )

        image_canvas.bind("<Configure>", render_image)
        ttk.Button(window, text="Zamknij", command=window.destroy).pack(pady=(0, 12))

    def save_estimate(self) -> None:
        if self.editing_draft_index is not None:
            try:
                updated_item = self._build_item_from_form()
            except ValueError as error:
                self._show_validation_error("Sprawdź pozycję", error)
                return
            self.draft_items[self.editing_draft_index] = updated_item
            self._reset_item_editor()
            self._refresh_draft()
        customer = self.customer_var.get().strip()
        order_number = self.order_number_var.get().strip()
        if not customer:
            self._show_validation_error("Dane zamówienia", FieldValidationError("Uzupełnij zleceniodawcę.", "customer"))
            return
        if not order_number:
            self._show_validation_error(
                "Dane zamówienia",
                FieldValidationError("Uzupełnij numer zamówienia klienta.", "order_number"),
            )
            return
        if not self.draft_items:
            self._show_validation_error(
                "Brak pozycji",
                FieldValidationError("Dodaj przynajmniej jeden element do zamówienia.", "element_name"),
            )
            return
        self._clear_all_invalid()
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
        self.delivery_note_estimate_id = None
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
        self._schedule_estimate_preview()

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

    def copy_summary_estimate(self) -> None:
        if self.summary_estimate is not None:
            self._load_estimate_into_form(self.summary_estimate, copy=True)

    def copy_selected_estimate(self) -> None:
        estimate = self._selected_estimate()
        if estimate is not None:
            self._load_estimate_into_form(estimate, copy=True)

    def _backup_before_destructive_change(self, reason: str) -> None:
        try:
            self.storage.create_backup(reason)
        except (OSError, sqlite3.Error):
            pass

    def delete_selected_estimate(self) -> None:
        selected = self.history_tree.selection()
        if not selected:
            messagebox.showinfo("Historia wycen", "Zaznacz zamówienie, które chcesz usunąć.", parent=self)
            return
        if not messagebox.askyesno("Usuń wycenę", "Usunąć wycenę wraz z jej pozycjami? Tej operacji nie można cofnąć.", parent=self):
            return
        self._backup_before_destructive_change("usuniecie-wyceny")
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
        dialog.resizable(True, True)
        dialog.minsize(
            min(460, self.winfo_screenwidth() - 40),
            min(190, self.winfo_screenheight() - 80),
        )
        dialog.geometry(
            f"{min(620, self.winfo_screenwidth() - 40)}"
            f"x{min(230, self.winfo_screenheight() - 80)}"
        )
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

    def export_summary_pdf(self) -> None:
        if self.summary_estimate is not None:
            self._write_estimate_pdf(self.summary_estimate, "offer")

    def print_summary_pdf(self) -> None:
        if self.summary_estimate is None:
            return
        try:
            output = BytesIO()
            export_estimate_pdf(
                self.summary_estimate,
                self.settings,
                output,
                "offer",
            )
        except (OSError, ValueError, ImportError, RuntimeError) as error:
            messagebox.showerror(
                "Drukowanie oferty",
                f"Nie udało się przygotować oferty do druku:\n{error}",
                parent=self,
            )
            return
        self._print_pdf_bytes(
            output.getvalue(),
            f"oferty {self.summary_estimate['header']['quote_number']}",
        )

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
        dialog.resizable(True, True)
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        dialog.minsize(
            min(560, screen_width - 40),
            min(420, screen_height - 80),
        )
        dialog.geometry(
            f"{min(760, screen_width - 40)}x{min(620, screen_height - 80)}"
        )
        scroll_host = tk.Frame(dialog, bg=WHITE)
        scroll_host.pack(fill="both", expand=True)
        canvas = tk.Canvas(scroll_host, bg=WHITE, highlightthickness=0)
        scrollbar = ttk.Scrollbar(scroll_host, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        content = tk.Frame(canvas, bg=WHITE, padx=24, pady=20)
        window_id = canvas.create_window((0, 0), window=content, anchor="nw")
        content.bind(
            "<Configure>",
            lambda _event: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        canvas.bind(
            "<Configure>",
            lambda event: canvas.itemconfigure(window_id, width=event.width),
        )
        content.grid_columnconfigure(1, weight=1)
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
        self._backup_before_destructive_change("usuniecie-klienta")
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
        dialog.resizable(True, True)
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        dialog.minsize(min(620, screen_width - 40), min(460, screen_height - 80))
        dialog.geometry(
            f"{min(900, screen_width - 60)}x{min(820, screen_height - 100)}"
        )
        scroll_host = tk.Frame(dialog, bg=WHITE)
        scroll_host.pack(fill="both", expand=True)
        settings_canvas = tk.Canvas(scroll_host, bg=WHITE, highlightthickness=0)
        settings_scrollbar = ttk.Scrollbar(
            scroll_host,
            orient="vertical",
            command=settings_canvas.yview,
        )
        settings_canvas.configure(yscrollcommand=settings_scrollbar.set)
        settings_canvas.pack(side="left", fill="both", expand=True)
        settings_scrollbar.pack(side="right", fill="y")
        content = tk.Frame(settings_canvas, bg=WHITE, padx=24, pady=20)
        settings_window = settings_canvas.create_window(
            (0, 0),
            window=content,
            anchor="nw",
        )
        content.bind(
            "<Configure>",
            lambda _event: settings_canvas.configure(
                scrollregion=settings_canvas.bbox("all")
            ),
        )
        settings_canvas.bind(
            "<Configure>",
            lambda event: settings_canvas.itemconfigure(
                settings_window,
                width=event.width,
            ),
        )
        tk.Label(content, text="Profil firmowy Izo-Technika", bg=WHITE, fg=INK, font=("Segoe UI", 15, "bold")).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 3))
        tk.Label(
            content,
            text="Dane trafiają do nagłówka oferty PDF. Cena za kg, stawka palenia i VAT są stałe w formularzu wyceny — zmienisz je tylko tutaj.",
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
            ("company_regon", "REGON firmy"),
            ("company_website", "Strona internetowa"),
            ("brand_tagline", "Hasło / opis marki"),
            ("photo_width_mm", "Szerokość zdjęcia w ofercie PDF (25–56 mm)"),
            ("price_per_kg", "Domyślna cena materiału (zł/kg)"),
            ("burning_rate_per_hour", "Domyślna stawka palenia (zł/godz.)"),
            ("vat_percent", "Domyślna stawka VAT (%)"),
        )
        for row, (key, label) in enumerate(fields, start=5):
            variable = tk.StringVar(value=settings.get(key, ""))
            variables[key] = variable
            tk.Label(content, text=label, bg=WHITE, fg=MUTED, font=("Segoe UI", 9, "bold")).grid(row=row, column=0, sticky="w", padx=(0, 14), pady=5)
            ttk.Entry(content, textvariable=variable, width=42).grid(row=row, column=1, columnspan=2, sticky="ew", pady=5)

        materials_row = len(fields) + 5
        tk.Label(content, text="Materiały / gatunki blach", bg=WHITE, fg=MUTED, font=("Segoe UI", 9, "bold")).grid(row=materials_row, column=0, sticky="nw", padx=(0, 14), pady=5)
        materials_frame = tk.Frame(content, bg=WHITE)
        materials_frame.grid(row=materials_row, column=1, columnspan=2, sticky="ew", pady=5)
        materials_list = tk.Listbox(materials_frame, height=4, exportselection=False, activestyle="none", relief="solid", borderwidth=1)
        materials_list.grid(row=0, column=0, columnspan=2, sticky="ew")
        materials_scroll = ttk.Scrollbar(materials_frame, orient="vertical", command=materials_list.yview)
        materials_list.configure(yscrollcommand=materials_scroll.set)
        materials_scroll.grid(row=0, column=2, sticky="ns")
        materials_frame.grid_columnconfigure(0, weight=1)
        for line in settings.get("materials", "").splitlines():
            if line.strip():
                materials_list.insert("end", line.strip())
        new_material_var = tk.StringVar()
        new_material_entry = ttk.Entry(materials_frame, textvariable=new_material_var)
        new_material_entry.grid(row=1, column=0, sticky="ew", pady=(6, 0))

        def add_material(_event: tk.Event | None = None) -> str:
            name = " ".join(new_material_var.get().split())
            existing = {materials_list.get(index).casefold() for index in range(materials_list.size())}
            if name and name.casefold() not in existing:
                materials_list.insert("end", name)
            new_material_var.set("")
            return "break"

        def remove_material() -> None:
            for index in reversed(materials_list.curselection()):
                materials_list.delete(index)

        new_material_entry.bind("<Return>", add_material)
        ttk.Button(materials_frame, text="Dodaj", command=add_material).grid(row=1, column=1, padx=(6, 0), pady=(6, 0))
        ttk.Button(materials_frame, text="Usuń zaznaczony", style="Quiet.TButton", command=remove_material).grid(row=2, column=0, sticky="w", pady=(6, 0))

        logo_var = tk.StringVar(value=settings.get("logo_path", ""))
        logo_row = len(fields) + 6
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

        backup_actions = ttk.Frame(content)
        backup_actions.grid(row=logo_row + 1, column=0, columnspan=3, sticky="w", pady=(9, 0))
        ttk.Button(backup_actions, text="Utwórz kopię zapasową bazy…", command=backup).pack(side="left")

        def restore() -> None:
            self.storage.backup_directory.mkdir(parents=True, exist_ok=True)
            filename = filedialog.askopenfilename(
                parent=dialog,
                title="Wybierz kopię zapasową do przywrócenia",
                initialdir=str(self.storage.backup_directory),
                filetypes=[("Kopia bazy SQLite", "*.sqlite3")],
            )
            if not filename:
                return
            if not messagebox.askyesno(
                "Przywróć kopię",
                "Aktualne dane zostaną zastąpione danymi z wybranej kopii "
                "(przed tym powstanie automatyczna kopia obecnego stanu).\n\n"
                "Po przywróceniu aplikacja zostanie zamknięta. Kontynuować?",
                parent=dialog,
            ):
                return
            try:
                self.storage.restore_backup(filename)
            except (OSError, sqlite3.Error, ValueError) as error:
                messagebox.showerror("Przywracanie kopii", f"Nie udało się przywrócić kopii:\n{error}", parent=dialog)
                return
            messagebox.showinfo("Przywracanie kopii", "Kopia została przywrócona. Uruchom aplikację ponownie.", parent=dialog)
            self.app.destroy()

        ttk.Button(backup_actions, text="Przywróć kopię…", command=restore).pack(side="left", padx=(7, 0))
        ttk.Button(
            content,
            text="Edytuj drugą stronę oferty (warunki, reklamacje, palety, kontakt)…",
            command=lambda: self.open_offer_page_editor(dialog),
        ).grid(row=logo_row + 3, column=0, columnspan=3, sticky="w", pady=(9, 0))
        ttk.Label(
            backup_actions,
            text="Automatyczne kopie: przy starcie i przed usunięciem.",
            style="Subtitle.TLabel",
        ).pack(side="left", padx=(10, 0))

        def save() -> None:
            try:
                material_price = parse_decimal(
                    variables["price_per_kg"].get(),
                    "Domyślna cena materiału",
                )
                rate = parse_decimal(variables["burning_rate_per_hour"].get(), "Domyślna stawka palenia")
                vat = parse_decimal(variables["vat_percent"].get(), "Domyślny VAT")
                calculate_quote(material_price, Decimal("1"), 0, rate, vat)
                photo_width = parse_decimal(variables["photo_width_mm"].get(), "Szerokość zdjęcia")
                if not PHOTO_WIDTH_MIN_MM <= photo_width <= PHOTO_WIDTH_MAX_MM:
                    raise ValueError("Szerokość zdjęcia musi mieścić się w zakresie 25–56 mm.")
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
            updated["materials"] = "\n".join(materials_list.get(index) for index in range(materials_list.size()))
            try:
                self.storage.save_settings(self.user_id, updated)
            except sqlite3.Error as error:
                messagebox.showerror("Błąd bazy danych", f"Nie udało się zapisać ustawień:\n{error}", parent=dialog)
                return
            self.settings = self.storage.get_settings(self.user_id)
            self.item_vars["price_per_kg"].set(self.settings["price_per_kg"])
            self.item_vars["burning_rate_per_hour"].set(self.settings["burning_rate_per_hour"])
            self.item_vars["vat_percent"].set(self.settings["vat_percent"])
            self._refresh_material_choices()
            self._refresh_brand_badge()
            dialog.destroy()

        buttons = ttk.Frame(content)
        buttons.grid(row=logo_row + 2, column=0, columnspan=3, sticky="e", pady=(18, 0))
        ttk.Button(buttons, text="Zamknij", command=dialog.destroy).pack(side="right")
        ttk.Button(buttons, text="Zapisz ustawienia", style="Primary.TButton", command=save).pack(side="right", padx=(0, 8))

    def open_offer_page_editor(self, parent: tk.Misc) -> None:
        page = parse_offer_page(self.settings.get(OFFER_PAGE_SETTING, ""))
        dialog = tk.Toplevel(parent)
        dialog.title("Druga strona oferty")
        dialog.transient(parent)
        dialog.grab_set()
        dialog.configure(bg=WHITE)
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        dialog.geometry(
            f"{min(820, screen_width - 40)}x{min(680, screen_height - 80)}"
        )
        dialog.minsize(
            min(560, screen_width - 40),
            min(420, screen_height - 80),
        )
        footer = ttk.Frame(dialog, padding=(18, 10))
        footer.pack(side="bottom", fill="x")
        scroll_canvas = tk.Canvas(dialog, bg=WHITE, highlightthickness=0)
        scrollbar = ttk.Scrollbar(dialog, orient="vertical", command=scroll_canvas.yview)
        scroll_canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        scroll_canvas.pack(side="left", fill="both", expand=True)
        body = tk.Frame(scroll_canvas, bg=WHITE, padx=20, pady=14)
        window_id = scroll_canvas.create_window((0, 0), window=body, anchor="nw")
        body.bind("<Configure>", lambda _e: scroll_canvas.configure(scrollregion=scroll_canvas.bbox("all")))
        scroll_canvas.bind("<Configure>", lambda e: scroll_canvas.itemconfigure(window_id, width=e.width))
        body.grid_columnconfigure(0, weight=1)

        label_font = ("Segoe UI", 9, "bold")
        title_vars: dict[str, tk.StringVar] = {}
        text_boxes: dict[str, tk.Text] = {}
        custom_rows: list[dict[str, Any]] = []
        contact_rows: list[dict[str, Any]] = []
        row = 0

        def add_title(key: str, hint: str) -> None:
            nonlocal row
            title_vars[key] = tk.StringVar(value=page[key]["title"])
            tk.Label(body, text=hint, bg=WHITE, fg=MUTED, font=label_font).grid(row=row, column=0, sticky="w", pady=(12, 2))
            ttk.Entry(body, textvariable=title_vars[key]).grid(row=row + 1, column=0, sticky="ew")
            row += 2

        for key, title_hint, text_hint in (
            ("terms", "Dodatkowe warunki — nagłówek", "Jeden punkt na linię; zawijanie robi PDF."),
            ("claims", "Odbiór i reklamacje — nagłówek", "Jeden punkt na linię."),
            ("pallets", "Cennik palet — nagłówek", "Jedna pozycja cennika na linię (pusta lista ukrywa sekcję)."),
        ):
            add_title(key, title_hint)
            tk.Label(body, text=text_hint, bg=WHITE, fg=MUTED, font=("Segoe UI", 8)).grid(
                row=row, column=0, sticky="w", pady=(4, 2)
            )
            box = tk.Text(
                body,
                height=7 if key == "terms" else 4,
                wrap="word",
                relief="solid",
                borderwidth=1,
                font=("Segoe UI", 10),
                undo=True,
            )
            box.insert("1.0", "\n".join(page[key]["items"]))
            box.grid(row=row + 1, column=0, sticky="ew")
            text_boxes[key] = box
            row += 2

        tk.Label(body, text="Dodatkowe rubryki", bg=WHITE, fg=NAVY, font=label_font).grid(
            row=row, column=0, sticky="w", pady=(16, 4)
        )
        row += 1
        custom_container = tk.Frame(body, bg=WHITE)
        custom_container.grid(row=row, column=0, sticky="ew")
        custom_container.grid_columnconfigure(0, weight=1)
        row += 1

        def remove_custom_row(custom_row: dict[str, Any]) -> None:
            custom_rows.remove(custom_row)
            custom_row["frame"].destroy()

        def add_custom_row(section: dict[str, str] | None = None) -> None:
            section = section or {"title": "", "text": ""}
            custom_frame = tk.Frame(
                custom_container,
                bg="#F6F8FC",
                padx=10,
                pady=8,
                highlightthickness=1,
                highlightbackground=BORDER,
            )
            custom_frame.pack(fill="x", pady=(0, 8))
            custom_frame.grid_columnconfigure(0, weight=1)
            title_var = tk.StringVar(value=section["title"])
            tk.Label(
                custom_frame,
                text="Nagłówek rubryki",
                bg="#F6F8FC",
                fg=MUTED,
                font=("Segoe UI", 8, "bold"),
            ).grid(row=0, column=0, sticky="w")
            ttk.Entry(custom_frame, textvariable=title_var).grid(row=1, column=0, sticky="ew")
            tk.Label(
                custom_frame,
                text="Treść",
                bg="#F6F8FC",
                fg=MUTED,
                font=("Segoe UI", 8, "bold"),
            ).grid(row=2, column=0, sticky="w", pady=(6, 2))
            text_box = tk.Text(
                custom_frame,
                height=4,
                wrap="word",
                relief="solid",
                borderwidth=1,
                font=("Segoe UI", 10),
                undo=True,
            )
            text_box.insert("1.0", section["text"])
            text_box.grid(row=3, column=0, sticky="ew")
            custom_row: dict[str, Any] = {
                "frame": custom_frame,
                "title": title_var,
                "text": text_box,
            }
            ttk.Button(
                custom_frame,
                text="Usuń rubrykę",
                style="Quiet.TButton",
                command=lambda: remove_custom_row(custom_row),
            ).grid(row=0, column=1, sticky="e", padx=(8, 0))
            custom_rows.append(custom_row)

        ttk.Button(
            body,
            text="+  Dodaj rubrykę",
            style="Quiet.TButton",
            command=add_custom_row,
        ).grid(row=row, column=0, sticky="w", pady=(4, 0))
        row += 1

        add_title("contact", "Dane teleadresowe — nagłówek")
        contact_container = tk.Frame(body, bg=WHITE)
        contact_container.grid(row=row, column=0, sticky="ew", pady=(6, 0))
        for column, (field, label) in enumerate(
            (("person", "Osoba kontaktowa"), ("phone", "Telefon"), ("email", "E-mail"))
        ):
            contact_container.grid_columnconfigure(column, weight=1)
            tk.Label(contact_container, text=label, bg=WHITE, fg=MUTED, font=label_font).grid(
                row=0, column=column, sticky="w", padx=(0 if column == 0 else 8, 0)
            )
        row += 1

        def remove_contact_row(contact_row: dict[str, Any]) -> None:
            contact_rows.remove(contact_row)
            contact_row["frame"].destroy()

        def add_contact_row(contact: dict[str, str] | None = None) -> None:
            contact = contact or {field: "" for field in CONTACT_FIELDS}
            contact_frame = tk.Frame(contact_container, bg=WHITE)
            contact_frame.grid(row=len(contact_rows) + 1, column=0, columnspan=3, sticky="ew", pady=(4, 0))
            values = {field: tk.StringVar(value=contact[field]) for field in CONTACT_FIELDS}
            for column, field in enumerate(CONTACT_FIELDS):
                ttk.Entry(contact_frame, textvariable=values[field]).grid(
                    row=0, column=column, sticky="ew", padx=(0 if column == 0 else 8, 0)
                )
                contact_frame.grid_columnconfigure(column, weight=1)
            ttk.Button(
                contact_frame,
                text="Usuń",
                style="Quiet.TButton",
                command=lambda: remove_contact_row(contact_row),
            ).grid(row=0, column=3, padx=(8, 0))
            contact_row: dict[str, Any] = {"frame": contact_frame, **values}
            contact_rows.append(contact_row)
            for index, existing in enumerate(contact_rows):
                existing["frame"].grid_configure(row=index + 1)

        for contact in page["contacts"]:
            add_contact_row(contact)
        ttk.Button(
            body,
            text="+  Dodaj osobę kontaktową",
            style="Quiet.TButton",
            command=add_contact_row,
        ).grid(row=row, column=0, sticky="w", pady=(8, 0))

        def collect() -> dict[str, Any]:
            result = default_offer_page()
            for key in LIST_SECTIONS:
                result[key]["title"] = title_vars[key].get().strip()
                lines = text_boxes[key].get("1.0", "end").splitlines()
                result[key]["items"] = [" ".join(line.split()) for line in lines if line.strip()]
            result["contact"]["title"] = title_vars["contact"].get().strip()
            result["contacts"] = [
                {field: contact[field].get().strip() for field in CONTACT_FIELDS}
                for contact in contact_rows
                if any(contact[field].get().strip() for field in CONTACT_FIELDS)
            ]
            result["contact"].update(result["contacts"][0] if result["contacts"] else {
                field: "" for field in CONTACT_FIELDS
            })
            result["custom_sections"] = [
                {
                    "title": custom_row["title"].get().strip(),
                    "text": custom_row["text"].get("1.0", "end-1c").strip(),
                }
                for custom_row in custom_rows
                if custom_row["title"].get().strip()
                or custom_row["text"].get("1.0", "end-1c").strip()
            ]
            return result

        def fill(source: dict[str, Any]) -> None:
            for key in LIST_SECTIONS:
                title_vars[key].set(source[key]["title"])
                text_boxes[key].delete("1.0", "end")
                text_boxes[key].insert("1.0", "\n".join(source[key]["items"]))
            title_vars["contact"].set(source["contact"]["title"])
            for custom_row in custom_rows[:]:
                remove_custom_row(custom_row)
            for section in source["custom_sections"]:
                add_custom_row(section)
            for contact_row in contact_rows[:]:
                remove_contact_row(contact_row)
            for contact in source["contacts"]:
                add_contact_row(contact)

        def restore_defaults() -> None:
            if messagebox.askyesno("Druga strona oferty", "Przywrócić domyślną treść drugiej strony? Twoje zmiany w tym oknie zostaną utracone.", parent=dialog):
                fill(default_offer_page())

        def save_page() -> None:
            try:
                self.storage.save_settings(self.user_id, {OFFER_PAGE_SETTING: serialize_offer_page(collect())})
            except sqlite3.Error as error:
                messagebox.showerror("Błąd bazy danych", f"Nie udało się zapisać treści:\n{error}", parent=dialog)
                return
            self.settings = self.storage.get_settings(self.user_id)
            dialog.destroy()

        ttk.Button(footer, text="Przywróć domyślne", style="Quiet.TButton", command=restore_defaults).pack(side="left")
        ttk.Button(footer, text="Anuluj", command=dialog.destroy).pack(side="right")
        ttk.Button(footer, text="Zapisz", style="Primary.TButton", command=save_page).pack(side="right", padx=(0, 8))

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
        storage.create_backup_if_stale()
    except (OSError, sqlite3.Error):
        pass

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
