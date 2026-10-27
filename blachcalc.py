import sqlite3
import tkinter as tk
from copy import deepcopy
from tkinter import messagebox, ttk
from typing import Any, NamedTuple

from PIL import ImageTk

from app_paths import resource_path
from app_paths import ensure_export_directories
from quote_domain import DEFAULT_OPERATION, OPERATIONS
from exports import PHOTO_WIDTH_DEFAULT_MM, PHOTO_WIDTH_MAX_MM, PHOTO_WIDTH_MIN_MM, photo_width_mm
from dashboard_shared import (
    ACCENT,
    ACCENT_DARK,
    BACKGROUND,
    BORDER,
    BRAND_RED,
    INK,
    LOGIN_ENABLED,
    MUTED,
    NAVY_DARK,
    PALE_RED,
    QUOTE_FIELD_COMBO_WIDTH,
    QUOTE_FIELD_ENTRY_WIDTH,
    WHITE,
)
from storage import Storage

from dashboard_documents import DashboardDocumentMixin
from dashboard_management import DashboardCustomerMixin
from dashboard_quote import DashboardQuoteMixin

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


class SizeSlider(NamedTuple):
    variable: tk.IntVar
    label_var: tk.StringVar
    scale: ttk.Scale

    @property
    def values(self) -> tuple[tk.IntVar, tk.StringVar, ttk.Scale]:
        return tuple(self)


class DashboardView(DashboardQuoteMixin, DashboardCustomerMixin, DashboardDocumentMixin, ttk.Frame):
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
            "operation": self.operation_var.get(),
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
            self.operation_var.set(state.get("operation", OPERATIONS[DEFAULT_OPERATION]))
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
        self.operation_var = tk.StringVar(value=OPERATIONS[DEFAULT_OPERATION])
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
        operation_cell = tk.Frame(self.item_details_body, bg=section_background)
        operation_cell.grid(row=5, column=0, sticky="ew", padx=5, pady=5)
        tk.Label(
            operation_cell,
            text="Operacja na elemencie",
            bg=section_background,
            fg=MUTED,
            font=("Segoe UI", 8, "bold"),
        ).pack(anchor="w", pady=(0, 3))
        self.operation_combo = ttk.Combobox(
            operation_cell,
            textvariable=self.operation_var,
            values=list(OPERATIONS.values()),
            state="readonly",
            width=QUOTE_FIELD_COMBO_WIDTH,
        )
        self.operation_combo.pack(anchor="w")
        self.item_field_cells["operation"] = operation_cell
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

    def _build_size_slider(
        self,
        parent: tk.Misc,
        title: str,
        minimum: int,
        maximum: int,
        initial: int,
        on_change: Any,
        on_release: Any,
    ) -> "SizeSlider":
        card = tk.Frame(parent, bg=WHITE, highlightbackground=BORDER, highlightthickness=1)
        card.pack(fill="x", pady=(0, 10))
        inner = tk.Frame(card, bg=WHITE, padx=14, pady=8)
        inner.pack(fill="x")
        tk.Label(inner, text=title, bg=WHITE, fg=MUTED, font=("Segoe UI", 8, "bold")).pack(side="left")
        value_var = tk.StringVar(value=f"{initial} mm")
        tk.Label(
            inner, textvariable=value_var, bg="#E8EEF8", fg=NAVY_DARK,
            font=("Segoe UI", 9, "bold"), padx=10, pady=2, width=6,
        ).pack(side="right")
        tk.Label(inner, text=f"{maximum}", bg=WHITE, fg=MUTED, font=("Segoe UI", 8)).pack(side="right", padx=(6, 12))
        number_var = tk.IntVar(value=initial)
        scale = ttk.Scale(
            inner, from_=minimum, to=maximum, orient="horizontal",
            variable=number_var, command=on_change, length=320,
        )
        scale.pack(side="right", padx=(12, 0))
        tk.Label(inner, text=f"{minimum}", bg=WHITE, fg=MUTED, font=("Segoe UI", 8)).pack(side="right", padx=(12, 0))
        scale.bind("<ButtonRelease-1>", on_release)
        scale.bind("<KeyRelease>", on_release)
        return SizeSlider(number_var, value_var, scale)

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

        try:
            start_width = int(photo_width_mm(self.settings))
        except (TypeError, ValueError):
            start_width = PHOTO_WIDTH_DEFAULT_MM
        (
            self.photo_width_var,
            self.photo_width_label_var,
            self.photo_width_scale,
        ) = self._build_size_slider(
            self.summary_tab,
            "Wielkość zdjęć w ofercie",
            PHOTO_WIDTH_MIN_MM,
            PHOTO_WIDTH_MAX_MM,
            start_width,
            self._on_photo_width_change,
            self._save_photo_width,
        ).values

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

def main() -> None:
    ensure_export_directories()
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
