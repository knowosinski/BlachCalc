import os
import sqlite3
import sys
import tkinter as tk
from tkinter import messagebox, ttk
from pathlib import Path
from typing import Any

from app_paths import offer_export_directory, resource_path, wz_export_directory
from dashboard_shared import (
    ACCENT,
    BACKGROUND,
    BORDER,
    INK,
    MUTED,
    UI_SCALE_MAX_PERCENT,
    UI_SCALE_MIN_PERCENT,
    WHITE,
    parse_ui_scale_percent,
    theme_color,
)
from storage import DEFAULT_SETTINGS, Storage
from version import APP_VERSION


WINDOW_MODES = {
    "Okno": "windowed",
    "Okno zmaksymalizowane": "maximized",
    "Pełny ekran": "fullscreen",
    "Pełny ekran bez ramek": "borderless",
}
WINDOW_MODE_LABELS = {value: label for label, value in WINDOW_MODES.items()}
WINDOW_PRESETS = {
    "Dopasuj do ekranu": None,
    "Kompaktowe — 1K (1024 × 768)": (1024, 768),
    "HD (1280 × 720)": (1280, 720),
    "Full HD (1920 × 1080)": (1920, 1080),
    "QHD / 2K (2560 × 1440)": (2560, 1440),
    "4K UHD (3840 × 2160)": (3840, 2160),
    "5K (5120 × 2880)": (5120, 2880),
    "8K (7680 × 4320)": (7680, 4320),
    "Własny rozmiar": "custom",
}
WINDOW_PRESET_LABELS = tuple(WINDOW_PRESETS)


def _app_color(app: Any, color: str) -> str:
    return theme_color(color, app._dark_mode, app._theme_settings)


def application_directory() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def open_directory(path: Path) -> None:
    path = path.expanduser()
    path.mkdir(parents=True, exist_ok=True)
    os.startfile(str(path))


class MainMenuView(tk.Frame):
    def __init__(
        self,
        app: Any,
        storage: Storage,
        user_id: int,
        username: str,
    ) -> None:
        super().__init__(app)
        self.app = app
        self.storage = storage
        self.user_id = user_id
        self.username = username
        self.logo_image: tk.PhotoImage | None = None
        self._build()

    def _build(self) -> None:
        background = _app_color(self.app, BACKGROUND)
        surface = _app_color(self.app, WHITE)
        text = _app_color(self.app, INK)
        muted = _app_color(self.app, MUTED)
        accent = _app_color(self.app, ACCENT)
        border = _app_color(self.app, BORDER)
        self.configure(background=background)

        top = tk.Frame(self, background=background, padx=30, pady=20)
        top.pack(fill="x")
        tk.Label(
            top,
            text="IZO-TECHNIKA  /  BLACHCALC",
            background=background,
            foreground=muted,
            font=("Segoe UI", 10, "bold"),
        ).pack(side="left")
        tk.Label(
            top,
            text=f"v{APP_VERSION}",
            background=background,
            foreground=muted,
            font=("Segoe UI", 9),
        ).pack(side="right")
        self.feedback_button = ttk.Button(
            top,
            text="Feedback",
            command=self.app.open_feedback,
        )
        self.feedback_button.pack(side="right", padx=(0, 12))

        stage = tk.Frame(self, background=background)
        stage.pack(fill="both", expand=True, padx=24, pady=(0, 24))
        card = tk.Frame(
            stage,
            background=surface,
            highlightthickness=1,
            highlightbackground=border,
            padx=48,
            pady=34,
        )
        card.place(relx=0.5, rely=0.48, anchor="center")

        tk.Frame(card, background=accent, height=4, width=76).pack(pady=(0, 22))
        logo_path = resource_path("logo.png")
        if not logo_path.is_file():
            raise FileNotFoundError(f"Nie znaleziono logo Izo-Technika:\n{logo_path}")
        self.logo_image = tk.PhotoImage(master=self, file=str(logo_path))
        tk.Label(
            card,
            image=self.logo_image,
            background=surface,
            borderwidth=0,
        ).pack(pady=(0, 22))
        tk.Label(
            card,
            text="BlachCalc",
            background=surface,
            foreground=text,
            font=("Segoe UI", 28, "bold"),
        ).pack()
        tk.Label(
            card,
            text="Firmowa aplikacja do wycen elementów wypalanych laserowo",
            background=surface,
            foreground=muted,
            font=("Segoe UI", 11),
            wraplength=560,
            justify="center",
        ).pack(pady=(5, 24))

        actions = tk.Frame(card, background=surface)
        actions.pack(fill="x")
        self.start_button = ttk.Button(
            actions,
            text="Start  →",
            style="Primary.TButton",
            command=self.app.start_application,
        )
        self.start_button.pack(fill="x", pady=4)
        ttk.Button(
            actions,
            text="Ustawienia ekranu i okna",
            command=self.open_settings,
        ).pack(fill="x", pady=4)
        ttk.Button(
            actions,
            text="O aplikacji",
            command=self.open_about,
        ).pack(fill="x", pady=4)
        folders = ttk.Frame(card, style="Card.TFrame")
        folders.pack(fill="x", pady=(12, 0))
        for column in range(3):
            folders.columnconfigure(column, weight=1, uniform="folder_buttons")
        self.app_folder_button = ttk.Button(
            folders,
            text="Folder aplikacji",
            command=lambda: self._open_folder(application_directory(), "aplikacji"),
        )
        self.app_folder_button.grid(row=0, column=0, sticky="ew", padx=(0, 4))
        self.offers_folder_button = ttk.Button(
            folders,
            text="Folder wycen",
            command=self.open_offers_folder,
        )
        self.offers_folder_button.grid(row=0, column=1, sticky="ew", padx=4)
        self.wz_folder_button = ttk.Button(
            folders,
            text="Folder WZ",
            command=self.open_wz_folder,
        )
        self.wz_folder_button.grid(row=0, column=2, sticky="ew", padx=(4, 0))
        self.start_button.focus_set()
        tk.Label(
            self,
            text="Dane i dokumenty pozostają lokalnie na tym komputerze.",
            background=background,
            foreground=muted,
            font=("Segoe UI", 9),
        ).pack(side="bottom", pady=(0, 18))

    def open_settings(self) -> None:
        WindowSettingsDialog(self.app, self.storage, self.user_id)

    def open_about(self) -> None:
        settings = self.storage.get_settings(self.user_id)
        dialog = tk.Toplevel(self.app)
        dialog.title("O aplikacji BlachCalc")
        dialog.transient(self.app)
        dialog.configure(background=_app_color(self.app, BACKGROUND))
        dialog.resizable(True, True)
        width = min(780, max(1, self.app.winfo_screenwidth() - 40))
        height = min(720, max(1, self.app.winfo_screenheight() - 80))
        dialog.minsize(min(620, width), min(560, height))
        x = max(0, (self.app.winfo_screenwidth() - width) // 2)
        y = max(0, (self.app.winfo_screenheight() - height) // 2)
        dialog.geometry(f"{width}x{height}+{x}+{y}")
        dialog.grab_set()

        content = ttk.Frame(dialog, padding=28)
        content.pack(fill="both", expand=True)
        header = ttk.Frame(content, style="Card.TFrame", padding=18)
        header.pack(fill="x")
        logo_path = resource_path("logo.png")
        if logo_path.is_file():
            dialog.logo_image = tk.PhotoImage(master=dialog, file=str(logo_path))
            tk.Label(
                header,
                image=dialog.logo_image,
                background=_app_color(self.app, WHITE),
                borderwidth=0,
            ).pack(side="left", padx=(0, 18))
        heading = ttk.Frame(header, style="Card.TFrame")
        heading.pack(side="left", fill="both", expand=True)
        ttk.Label(
            heading,
            text="BlachCalc",
            style="Card.TLabel",
            font=("Segoe UI", 23, "bold"),
        ).pack(anchor="w")
        ttk.Label(
            heading,
            text="Firmowa aplikacja do wycen elementów wypalanych laserowo",
            style="CardMuted.TLabel",
            wraplength=560,
            justify="left",
        ).pack(anchor="w", pady=(3, 10))
        ttk.Label(
            heading,
            text=f"Wersja {APP_VERSION}  ·  Izo-Technika",
            style="CardTitle.TLabel",
        ).pack(anchor="w")

        creators = ttk.Frame(content, style="Card.TFrame", padding=18)
        creators.pack(fill="x", pady=(14, 0))
        ttk.Label(
            creators,
            text="Autorzy i współtworzenie",
            style="CardTitle.TLabel",
        ).pack(anchor="w", pady=(0, 7))
        ttk.Label(
            creators,
            text="Autor aplikacji: @knowosinski",
            style="Card.TLabel",
        ).pack(anchor="w")
        ttk.Label(
            creators,
            text="BlachCalc jest rozwijany przez autora przy współpracy z GitHub Copilot.",
            style="CardMuted.TLabel",
            wraplength=660,
            justify="left",
        ).pack(anchor="w", pady=(3, 0))

        details = ttk.Frame(content, style="Card.TFrame", padding=18)
        details.pack(fill="both", expand=True, pady=(14, 0))
        ttk.Label(
            details,
            text="Informacje o aplikacji",
            style="CardTitle.TLabel",
        ).pack(anchor="w", pady=(0, 7))
        contact = " · ".join(
            value
            for value in (
                settings.get("company_phone", ""),
                settings.get("company_email", ""),
                settings.get("company_website", ""),
            )
            if value
        )
        info_rows = ttk.Frame(details, style="Card.TFrame")
        info_rows.pack(fill="both", expand=True)
        info = (
            ("Firma", settings.get("company_name", DEFAULT_SETTINGS["company_name"])),
            ("Funkcje", "Wyceny, eksport PDF/Excel oraz dokumenty WZ."),
            ("Przechowywanie", "Baza, ustawienia i dokumenty pozostają lokalnie na komputerze."),
            ("Baza danych", str(self.storage.database_path)),
            ("Folder wycen", settings.get("offer_export_directory", str(offer_export_directory()))),
            ("Folder WZ", settings.get("wz_export_directory", str(wz_export_directory()))),
            ("Kontakt", contact or "Nie skonfigurowano danych kontaktowych."),
        )
        info_rows.columnconfigure(1, weight=1)
        for index, (label, value) in enumerate(info):
            ttk.Label(
                info_rows,
                text=f"{label}:",
                width=16,
                style="CardMuted.TLabel",
            ).grid(row=index, column=0, sticky="nw", padx=(0, 12), pady=4)
            ttk.Label(
                info_rows,
                text=value,
                wraplength=600,
                justify="left",
                style="Card.TLabel",
            ).grid(row=index, column=1, sticky="ew", pady=4)
        about_actions = ttk.Frame(content)
        about_actions.pack(fill="x", pady=(14, 0))
        ttk.Button(
            about_actions,
            text="Zgłoś feedback",
            command=self.app.open_feedback,
        ).pack(side="left")
        ttk.Button(
            about_actions,
            text="Zamknij",
            command=dialog.destroy,
        ).pack(
            side="right",
        )

    def open_offers_folder(self) -> None:
        settings = self.storage.get_settings(self.user_id)
        self._open_folder(
            Path(settings.get("offer_export_directory", str(offer_export_directory()))),
            "wycen",
        )

    def open_wz_folder(self) -> None:
        settings = self.storage.get_settings(self.user_id)
        self._open_folder(
            Path(settings.get("wz_export_directory", str(wz_export_directory()))),
            "dokumentów WZ",
        )

    def _open_folder(self, path: Path, label: str) -> None:
        try:
            open_directory(path)
        except OSError as error:
            messagebox.showerror(
                "Otwieranie folderu",
                f"Nie udało się otworzyć folderu {label}:\n{error}",
                parent=self.app,
            )


class WindowSettingsDialog:
    def __init__(self, app: Any, storage: Storage, user_id: int) -> None:
        self.app = app
        self.storage = storage
        self.user_id = user_id
        self.dialog = tk.Toplevel(app)
        self.dialog.title("Ustawienia ekranu i okna")
        self.dialog.transient(app)
        self.dialog.configure(background=_app_color(app, BACKGROUND))
        self.dialog.resizable(True, True)
        width = min(760, max(1, app.winfo_screenwidth() - 40))
        height = min(640, max(1, app.winfo_screenheight() - 80))
        self.dialog.minsize(min(640, width), min(520, height))
        x = max(0, (app.winfo_screenwidth() - width) // 2)
        y = max(0, (app.winfo_screenheight() - height) // 2)
        self.dialog.geometry(f"{width}x{height}+{x}+{y}")
        self.dialog.grab_set()

        settings = storage.get_settings(user_id)
        mode = settings.get("window_mode", DEFAULT_SETTINGS["window_mode"])
        if mode not in WINDOW_MODE_LABELS:
            mode = DEFAULT_SETTINGS["window_mode"]
        self.mode_var = tk.StringVar(value=WINDOW_MODE_LABELS[mode])
        self.width_var = tk.StringVar(value=str(app._window_width))
        self.height_var = tk.StringVar(value=str(app._window_height))
        self.preset_var = tk.StringVar(value="Własny rozmiar")
        self.scale_var = tk.StringVar(
            value=str(
                parse_ui_scale_percent(
                    settings.get("ui_scale_percent", DEFAULT_SETTINGS["ui_scale_percent"])
                )
            )
        )
        self.dpi_var = tk.BooleanVar(value=settings.get("dpi_awareness", "1") != "0")
        self.center_var = tk.BooleanVar(value=settings.get("center_window", "1") != "0")
        self._applying_preset = False
        self.width_var.trace_add("write", self._mark_custom_size)
        self.height_var.trace_add("write", self._mark_custom_size)
        self._build()

    def _build(self) -> None:
        content = ttk.Frame(self.dialog, padding=26)
        content.pack(fill="both", expand=True)
        ttk.Label(content, text="Ekran i okno", style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            content,
            text="Dopasuj okno i skalowanie interfejsu do swojego stanowiska.",
            style="Subtitle.TLabel",
        ).pack(anchor="w", pady=(3, 14))

        form = ttk.Frame(content, style="Card.TFrame", padding=18)
        form.pack(fill="x")
        ttk.Label(form, text="Tryb wyświetlania", style="Card.TLabel").grid(
            row=0, column=0, sticky="w", pady=7
        )
        mode_combo = ttk.Combobox(
            form,
            textvariable=self.mode_var,
            values=tuple(WINDOW_MODES),
            state="readonly",
            width=31,
        )
        mode_combo.grid(row=0, column=1, sticky="ew", padx=(14, 0), pady=7)
        ttk.Label(form, text="Preset rozmiaru", style="Card.TLabel").grid(
            row=1, column=0, sticky="w", pady=7
        )
        preset_combo = ttk.Combobox(
            form,
            textvariable=self.preset_var,
            values=WINDOW_PRESET_LABELS,
            state="readonly",
            width=31,
        )
        preset_combo.grid(row=1, column=1, sticky="ew", padx=(14, 0), pady=7)
        preset_combo.bind("<<ComboboxSelected>>", self._apply_size_preset)
        minimum_width = min(800, max(1, self.app.winfo_screenwidth() - 40))
        minimum_height = min(680, max(1, self.app.winfo_screenheight() - 80))
        size_fields = ttk.Frame(form, style="Card.TFrame")
        size_fields.grid(row=2, column=0, columnspan=2, sticky="ew", pady=7)
        ttk.Label(size_fields, text="Szerokość", style="Card.TLabel").pack(side="left")
        ttk.Spinbox(
            size_fields,
            textvariable=self.width_var,
            from_=minimum_width,
            to=max(minimum_width, self.app.winfo_screenwidth() - 40),
            increment=40,
            width=9,
        ).pack(side="left", padx=(8, 24))
        ttk.Label(size_fields, text="Wysokość", style="Card.TLabel").pack(side="left")
        ttk.Spinbox(
            size_fields,
            textvariable=self.height_var,
            from_=minimum_height,
            to=max(minimum_height, self.app.winfo_screenheight() - 80),
            increment=40,
            width=9,
        ).pack(side="left", padx=(8, 0))
        ttk.Label(form, text="Skala interfejsu", style="Card.TLabel").grid(
            row=3, column=0, sticky="w", pady=7
        )
        scale_field = ttk.Frame(form, style="Card.TFrame")
        scale_field.grid(row=3, column=1, sticky="w", padx=(14, 0), pady=7)
        ttk.Spinbox(
            scale_field,
            textvariable=self.scale_var,
            from_=UI_SCALE_MIN_PERCENT,
            to=UI_SCALE_MAX_PERCENT,
            increment=5,
            width=9,
        ).pack(side="left")
        ttk.Label(scale_field, text="%", style="CardMuted.TLabel").pack(
            side="left", padx=(6, 0)
        )
        ttk.Checkbutton(
            form,
            text="Wyśrodkuj okno przy uruchomieniu",
            variable=self.center_var,
        ).grid(row=4, column=0, columnspan=2, sticky="w", pady=(7, 2))
        ttk.Checkbutton(
            form,
            text="Używaj wysokiej zgodności DPI systemu Windows",
            variable=self.dpi_var,
        ).grid(row=5, column=0, columnspan=2, sticky="w", pady=2)
        form.columnconfigure(1, weight=1)

        ttk.Label(
            content,
            text=(
                "Presety zmieniają tylko rozmiar okna, nie rozdzielczość Windows; "
                "rozmiar zostanie dopasowany, jeśli przekracza obszar ekranu. "
                "Możesz też wpisać własne wymiary. Skala interfejsu działa od razu; "
                "zmiana zgodności DPI wymaga ponownego uruchomienia. Tryby "
                "pełnoekranowe ignorują wymiary, a Esc opuszcza pełny ekran bez ramek."
            ),
            style="Subtitle.TLabel",
            wraplength=660,
            justify="left",
        ).pack(anchor="w", pady=(12, 16))

        actions = ttk.Frame(content)
        actions.pack(fill="x", side="bottom")
        ttk.Button(
            actions,
            text="Zgłoś feedback",
            command=self.app.open_feedback,
        ).pack(side="left")
        ttk.Button(actions, text="Anuluj", command=self.dialog.destroy).pack(side="right")
        ttk.Button(
            actions,
            text="Zapisz i zastosuj",
            style="Primary.TButton",
            command=self.save,
        ).pack(side="right", padx=(0, 8))

    def _mark_custom_size(self, *_args: str) -> None:
        if not self._applying_preset:
            self.preset_var.set("Własny rozmiar")

    def _apply_size_preset(self, _event: tk.Event | None = None) -> None:
        preset_name = self.preset_var.get()
        preset = WINDOW_PRESETS.get(preset_name, "custom")
        if preset == "custom":
            return
        screen_width = self.app.winfo_screenwidth()
        screen_height = self.app.winfo_screenheight()
        minimum_width = min(800, max(1, screen_width - 40))
        minimum_height = min(680, max(1, screen_height - 80))
        maximum_width = max(minimum_width, screen_width - 40)
        maximum_height = max(minimum_height, screen_height - 80)
        if preset_name == "Dopasuj do ekranu":
            width, height = maximum_width, maximum_height
        elif isinstance(preset, tuple):
            width, height = preset
            width = min(max(width, minimum_width), maximum_width)
            height = min(max(height, minimum_height), maximum_height)
        else:
            return
        self._applying_preset = True
        try:
            self.width_var.set(str(width))
            self.height_var.set(str(height))
        finally:
            self._applying_preset = False

    def save(self) -> None:
        mode = WINDOW_MODES.get(self.mode_var.get())
        if mode is None:
            messagebox.showerror(
                "Ustawienia okna",
                "Wybierz prawidłowy tryb okna.",
                parent=self.dialog,
            )
            return
        try:
            width = int(self.width_var.get())
            height = int(self.height_var.get())
        except ValueError:
            messagebox.showerror(
                "Ustawienia okna",
                "Szerokość i wysokość muszą być liczbami całkowitymi.",
                parent=self.dialog,
            )
            return
        try:
            ui_scale = int(self.scale_var.get())
        except ValueError:
            messagebox.showerror(
                "Ustawienia ekranu",
                "Skala interfejsu musi być liczbą całkowitą.",
                parent=self.dialog,
            )
            return
        if not UI_SCALE_MIN_PERCENT <= ui_scale <= UI_SCALE_MAX_PERCENT:
            messagebox.showerror(
                "Ustawienia ekranu",
                f"Skala musi mieścić się w zakresie {UI_SCALE_MIN_PERCENT}–"
                f"{UI_SCALE_MAX_PERCENT}%.",
                parent=self.dialog,
            )
            return

        screen_width = self.app.winfo_screenwidth()
        screen_height = self.app.winfo_screenheight()
        minimum_width = min(800, max(1, screen_width - 40))
        minimum_height = min(680, max(1, screen_height - 80))
        maximum_width = max(minimum_width, screen_width - 40)
        maximum_height = max(minimum_height, screen_height - 80)
        if not minimum_width <= width <= maximum_width or not minimum_height <= height <= maximum_height:
            messagebox.showerror(
                "Ustawienia okna",
                f"Podaj szerokość {minimum_width}–{maximum_width} i wysokość "
                f"{minimum_height}–{maximum_height} pikseli.",
                parent=self.dialog,
            )
            return

        updates = {
            "window_mode": mode,
            "window_width": str(width),
            "window_height": str(height),
            "ui_scale_percent": str(ui_scale),
            "center_window": "1" if self.center_var.get() else "0",
            "dpi_awareness": "1" if self.dpi_var.get() else "0",
        }
        dpi_setting_changed = False
        try:
            previous_settings = self.storage.get_settings(self.user_id)
            dpi_setting_changed = (
                previous_settings.get("dpi_awareness", "1") != updates["dpi_awareness"]
            )
            self.storage.save_settings(self.user_id, updates)
            settings = self.storage.get_settings(self.user_id)
            self.app.apply_ui_scale(ui_scale)
            self.app.apply_window_settings(settings)
        except (OSError, ValueError, sqlite3.Error, tk.TclError) as error:
            messagebox.showerror(
                "Ustawienia okna",
                f"Nie udało się zastosować ustawień:\n{error}",
                parent=self.dialog,
            )
            return
        self.dialog.destroy()
        if dpi_setting_changed:
            messagebox.showinfo(
                "Ustawienia ekranu",
                "Zmiana zgodności DPI zostanie zastosowana po ponownym uruchomieniu aplikacji.",
                parent=self.app,
            )
