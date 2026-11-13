import json
import random
import re
import sqlite3
import sys
import tempfile
import threading
import tkinter as tk
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from tkinter import colorchooser, filedialog, messagebox, ttk
from typing import Any

from calculator import calculate_quote, parse_decimal
from currency import (
    CURRENCIES,
    convert_currency,
    fetch_nbp_rates,
    parse_currency_rates,
    serialize_currency_rates,
)
from material_library import CATEGORIES, load_materials, serialize_materials
from quote_domain import format_currency
from app_paths import copy_export_directory, ensure_export_directories
from updater import UPDATED_FLAG, check_and_update, install_local_update
from version import APP_VERSION, WHATS_NEW
from dashboard_shared import (
    ACCENT,
    BACKGROUND,
    BORDER,
    BRAND_RED,
    INK,
    MUTED,
    NAVY,
    WHITE,
    THEME_PALETTE_SETTINGS,
    UI_SCALE_MAX_PERCENT,
    UI_SCALE_MIN_PERCENT,
    contrasting_text_color,
    theme_color,
)
from offer_page import (
    CONTACT_FIELDS,
    LIST_SECTIONS,
    SETTING_KEY as OFFER_PAGE_SETTING,
    default_offer_page,
    parse_offer_page,
    serialize_offer_page,
)
from quote_domain import PACKAGING_OPTIONS, calculate_item_amounts, packaging_setting_key
from exports import (
    OFFICE_FONT_SCALE_DEFAULT_PERCENT,
    OFFICE_FONT_SCALE_MAX_PERCENT,
    OFFICE_FONT_SCALE_MIN_PERCENT,
    OFFICE_ROW_HEIGHT_DEFAULT_MM,
    OFFICE_ROW_HEIGHT_MAX_MM,
    OFFICE_ROW_HEIGHT_MIN_MM,
    PHOTO_WIDTH_DEFAULT_MM,
    PHOTO_WIDTH_MAX_MM,
    PHOTO_WIDTH_MIN_MM,
    WZ_ROW_HEIGHT_DEFAULT_MM,
    WZ_ROW_HEIGHT_MAX_MM,
    WZ_ROW_HEIGHT_MIN_MM,
)
from run_tests import start_application_test_worker
from storage import (
    ADDRESS_FIELDS,
    DEFAULT_SETTINGS,
    application_config_path,
    default_data_directory,
    format_postal_address,
    parse_polish_address,
    validate_postal_address,
)


class DashboardCustomerMixin:
    def _open_currency_converter(
        self,
        parent: tk.Misc,
        rates_variable: tk.StringVar,
        on_rates_updated: Any,
    ) -> None:
        dialog = tk.Toplevel(parent)
        dialog.title("Konwerter walut")
        dialog.transient(parent)
        dialog.grab_set()
        dialog.resizable(False, False)
        dialog.configure(bg=WHITE)
        body = tk.Frame(dialog, bg=WHITE, padx=20, pady=18)
        body.pack(fill="both", expand=True)
        tk.Label(
            body,
            text="Konwerter walut",
            bg=WHITE,
            fg=INK,
            font=("Segoe UI", 14, "bold"),
        ).grid(row=0, column=0, columnspan=4, sticky="w")
        amount = tk.StringVar(value="1")
        source = tk.StringVar(value=self.settings.get("default_currency", "PLN"))
        target = tk.StringVar(value="EUR" if source.get() == "PLN" else "PLN")
        result = tk.StringVar()
        status = tk.StringVar(value="Kursy pobierane są z tabeli A Narodowego Banku Polskiego.")
        values = tuple(CURRENCIES)

        tk.Label(body, text="Kwota", bg=WHITE, fg=MUTED).grid(
            row=1, column=0, sticky="w", pady=(14, 4)
        )
        ttk.Entry(body, textvariable=amount, width=18).grid(
            row=2, column=0, sticky="ew"
        )
        ttk.Combobox(
            body, textvariable=source, values=values, state="readonly", width=8
        ).grid(row=2, column=1, padx=(8, 8))
        def swap_currencies() -> None:
            previous_source = source.get()
            source.set(target.get())
            target.set(previous_source)

        ttk.Button(
            body, text="⇄", width=3, command=swap_currencies
        ).grid(row=2, column=2)
        ttk.Combobox(
            body, textvariable=target, values=values, state="readonly", width=8
        ).grid(row=2, column=3, padx=(8, 0))
        tk.Label(
            body,
            textvariable=result,
            bg=WHITE,
            fg=ACCENT,
            font=("Segoe UI", 17, "bold"),
        ).grid(row=3, column=0, columnspan=4, sticky="w", pady=(15, 2))
        tk.Label(
            body,
            textvariable=status,
            bg=WHITE,
            fg=MUTED,
            wraplength=420,
            justify="left",
        ).grid(row=4, column=0, columnspan=4, sticky="w", pady=(4, 12))

        def update_result(*_args: object) -> None:
            try:
                amount_value = parse_decimal(amount.get(), "Kwota")
                rates = parse_currency_rates(rates_variable.get())
                converted = convert_currency(
                    amount_value, source.get(), target.get(), rates
                )
                result.set(f"{format_currency(converted, target.get())}")
            except ValueError as error:
                result.set(str(error))

        amount.trace_add("write", update_result)
        source.trace_add("write", update_result)
        target.trace_add("write", update_result)
        update_result()

        refresh_button = ttk.Button(
            body,
            text="Pobierz kursy NBP",
            command=lambda: refresh_rates(),
        )
        refresh_button.grid(row=5, column=0, sticky="w")

        def apply_rates(rates: dict[str, Decimal], effective_date: str) -> None:
            try:
                serialized = serialize_currency_rates(rates)
                self.storage.save_settings(
                    self.user_id, {"currency_rates": serialized}
                )
            except (ValueError, sqlite3.Error) as error:
                status.set(f"Nie udało się zapisać kursów: {error}")
                refresh_button.configure(state="normal")
                return
            rates_variable.set(serialized)
            self.settings["currency_rates"] = serialized
            on_rates_updated(serialized)
            self._refresh_summary_estimate_from_settings()
            status.set(f"Kursy NBP z dnia {effective_date} zostały zapisane.")
            update_result()
            refresh_button.configure(state="normal")

        def refresh_rates() -> None:
            refresh_button.configure(state="disabled")
            status.set("Pobieranie kursów z NBP…")

            def request_rates() -> None:
                try:
                    rates, effective_date = fetch_nbp_rates()
                except (OSError, ValueError) as error:
                    try:
                        dialog.after(
                            0,
                            lambda error=error: (
                                status.set(f"Nie udało się pobrać kursów NBP: {error}"),
                                refresh_button.configure(state="normal"),
                            ),
                        )
                    except tk.TclError:
                        pass
                    return
                try:
                    dialog.after(
                        0,
                        lambda: apply_rates(rates, effective_date)
                        if dialog.winfo_exists()
                        else None,
                    )
                except tk.TclError:
                    pass

            threading.Thread(target=request_rates, daemon=True).start()

        body.grid_columnconfigure(0, weight=1)
        dialog.bind("<Return>", lambda _event: (update_result(), "break")[1])
        self.fade_window(dialog)
        dialog.after(100, refresh_rates)

    def _build_customers_tab(self) -> None:
        self._page_heading(
            self.customers_tab,
            "Kartoteka klientów",
            "Dane kontaktowe są zapisywane lokalnie i mogą pojawić się w ofercie PDF.",
        )
        card, body = self._card(self.customers_tab, "Zleceniodawcy")
        self.customers_card = card
        card.pack(fill="both", expand=True)
        columns = ("name", "contact", "email", "phone", "tax_id", "address")
        customer_table = self._accent_outline(body)
        customer_table.pack(fill="both", expand=True)
        customer_table.grid_rowconfigure(0, weight=1)
        customer_table.grid_columnconfigure(0, weight=1)
        self.customers_tree = ttk.Treeview(customer_table, columns=columns, show="headings", height=8, selectmode="browse")
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
        scroll = ttk.Scrollbar(customer_table, orient="vertical", command=self.customers_tree.yview)
        self.customers_tree.configure(yscrollcommand=scroll.set)
        self.customers_tree.grid(row=0, column=0, sticky="nsew")
        scroll.grid(row=0, column=1, sticky="ns")
        horizontal_scroll = ttk.Scrollbar(customer_table, orient="horizontal", command=self.customers_tree.xview)
        self.customers_tree.configure(xscrollcommand=horizontal_scroll.set)
        horizontal_scroll.grid(row=1, column=0, sticky="ew")
        self.customers_tree.bind("<Double-1>", lambda _event: self.edit_customer())
        actions = ttk.Frame(body)
        actions.pack(fill="x", pady=(10, 8))
        ttk.Button(actions, text="＋  Dodaj klienta", style="Primary.TButton", command=self.add_customer).pack(side="left")
        ttk.Button(actions, text="Edytuj", command=self.edit_customer).pack(side="left", padx=(7, 0))
        ttk.Button(actions, text="Usuń", style="Danger.TButton", command=self.delete_customer).pack(side="left", padx=(7, 0))

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

    def update_application(self) -> None:
        if not getattr(sys, "frozen", False):
            messagebox.showinfo(
                "Aktualizuj aplikację",
                "Aktualizacja jest dostępna dla zainstalowanej wersji programu.",
                parent=self,
            )
            return
        if self.settings.get("update_source", "github") == "local":
            update_started = install_local_update(
                self.settings.get("local_update_path", ""),
                parent=self,
                before_install=self.save_delivery_note_draft,
            )
        else:
            update_started = check_and_update(
                parent=self,
                before_install=self.save_delivery_note_draft,
            )
        if update_started:
            self.after(1000, self.app.destroy)

    def check_for_startup_update(self) -> None:
        if (
            not getattr(sys, "frozen", False)
            or self.settings.get("update_source", "github") != "github"
        ):
            return
        if "--updated" in sys.argv[1:]:
            return
        if check_and_update(
            parent=self,
            before_install=self.save_delivery_note_draft,
            notify_if_current=False,
        ):
            self.after(1000, self.app.destroy)

    def _show_update_splash(self) -> tk.Toplevel:
        splash = tk.Toplevel(self)
        splash.title("BlachCalc — aktualizacja")
        splash.configure(bg=WHITE, padx=28, pady=22)
        splash.transient(self.winfo_toplevel())
        splash.resizable(False, False)
        splash.protocol("WM_DELETE_WINDOW", lambda: None)
        tk.Label(splash, text="Aktualizowanie BlachCalc…", bg=WHITE, fg=INK, font=("Segoe UI", 13, "bold")).pack()
        tk.Label(
            splash,
            text="Aplikacja zamknie się, zostanie zaktualizowana\ni uruchomi się ponownie.",
            bg=WHITE,
            fg=MUTED,
            justify="center",
        ).pack(pady=(6, 14))
        bar = ttk.Progressbar(splash, mode="indeterminate", length=300)
        bar.pack()
        bar.start(12)
        splash.update_idletasks()
        root = self.winfo_toplevel()
        x = root.winfo_rootx() + max(0, (root.winfo_width() - splash.winfo_width()) // 2)
        y = root.winfo_rooty() + max(0, (root.winfo_height() - splash.winfo_height()) // 3)
        splash.geometry(f"+{x}+{y}")
        splash.grab_set()
        splash.update()
        return splash

    def _maybe_show_welcome(self) -> None:
        """Jednorazowe powitanie z listą nowości po aktualizacji."""
        try:
            if not self.winfo_exists():
                return
        except tk.TclError:
            return
        stored = self.settings.get("last_seen_version", "")
        show = UPDATED_FLAG in sys.argv[1:] or (bool(stored) and stored != APP_VERSION)
        if stored != APP_VERSION:
            try:
                self.storage.save_settings(self.user_id, {"last_seen_version": APP_VERSION})
                self.settings["last_seen_version"] = APP_VERSION
            except sqlite3.Error:
                pass
        if not show:
            return
        dialog = tk.Toplevel(self)
        dialog.title("Witaj w nowej wersji BlachCalc")
        dialog.configure(bg=WHITE, padx=26, pady=22)
        dialog.transient(self.winfo_toplevel())
        dialog.resizable(False, False)
        tk.Label(
            dialog,
            text=f"Witaj w BlachCalc {APP_VERSION}!",
            bg=WHITE,
            fg=INK,
            font=("Segoe UI", 16, "bold"),
        ).pack(anchor="w")
        tk.Label(
            dialog,
            text="Aplikacja została zaktualizowana. Co nowego:",
            bg=WHITE,
            fg=MUTED,
        ).pack(anchor="w", pady=(4, 10))
        for entry in WHATS_NEW:
            tk.Label(
                dialog,
                text=f"•  {entry}",
                bg=WHITE,
                fg=INK,
                justify="left",
                anchor="w",
                wraplength=520,
            ).pack(anchor="w", pady=2)
        ttk.Button(dialog, text="Zaczynamy", style="Primary.TButton", command=dialog.destroy).pack(anchor="e", pady=(16, 0))
        dialog.update_idletasks()
        root = self.winfo_toplevel()
        x = root.winfo_rootx() + max(0, (root.winfo_width() - dialog.winfo_width()) // 2)
        y = root.winfo_rooty() + max(0, (root.winfo_height() - dialog.winfo_height()) // 3)
        dialog.geometry(f"+{x}+{y}")
        dialog.grab_set()

    def _activate_hidden_test_demo(self, _event: tk.Event) -> str | None:
        if self.notes_var.get() != "TesTDlugI":
            return None
        self.notes_var.set("")
        if getattr(self.app, "_simulated_test_stop", None) is None:
            self.app._test_demo_armed = True
        return "break"

    def run_application_tests(
        self,
        parent: tk.Misc,
        simulated: bool = False,
    ) -> None:
        dialog = tk.Toplevel(parent)
        dialog.title("Testy aplikacji BlachCalc")
        dark_mode = self.app._dark_mode
        theme_settings = self.app._theme_settings
        surface = theme_color(WHITE, dark_mode, theme_settings)
        text_color = theme_color(INK, dark_mode, theme_settings)
        muted_color = theme_color(MUTED, dark_mode, theme_settings)
        border_color = theme_color(BORDER, dark_mode, theme_settings)
        dialog.configure(bg=theme_color(BACKGROUND, dark_mode, theme_settings))
        dialog.transient(parent.winfo_toplevel())
        dialog.resizable(True, True)
        screen_width = dialog.winfo_screenwidth()
        screen_height = dialog.winfo_screenheight()
        dialog.minsize(min(620, screen_width - 40), min(420, screen_height - 80))
        dialog.geometry(f"{min(860, screen_width - 60)}x{min(620, screen_height - 100)}")

        content = ttk.Frame(dialog, padding=20)
        content.pack(fill="both", expand=True)
        ttk.Label(
            content,
            text="Pełne testy aplikacji",
            style="Title.TLabel",
        ).pack(anchor="w")
        progress_text = tk.StringVar(value="Przygotowywanie testów…")
        ttk.Label(
            content,
            textvariable=progress_text,
            font=("Segoe UI", 10, "bold"),
        ).pack(anchor="w")
        progress_bar = ttk.Progressbar(
            content,
            style="Horizontal.TProgressbar",
            mode="determinate",
            maximum=1,
            value=0,
        )
        progress_bar.pack(fill="x", pady=(8, 8))
        current_test = tk.StringVar(
            value="Testy czekają na rozpoczęcie…"
            if simulated
            else "Uruchamianie zestawu testów…"
        )
        ttk.Label(
            content,
            textvariable=current_test,
            style="Subtitle.TLabel",
            wraplength=780,
        ).pack(anchor="w", pady=(0, 10))

        result_host = ttk.Frame(content)
        result_host.pack(fill="both", expand=True)
        results = tk.Text(
            result_host,
            height=16,
            wrap="word",
            state="disabled",
            background=surface,
            foreground=text_color,
            insertbackground=text_color,
            selectbackground=theme_color("#DCE9F7", dark_mode, theme_settings),
            selectforeground=text_color,
            highlightthickness=1,
            highlightbackground=border_color,
            highlightcolor=theme_color(ACCENT, dark_mode, theme_settings),
            relief="flat",
            padx=12,
            pady=10,
            font=("Consolas", 9),
        )
        results.pack(side="left", fill="both", expand=True)
        results_scroll = ttk.Scrollbar(
            result_host,
            orient="vertical",
            command=results.yview,
        )
        results.configure(yscrollcommand=results_scroll.set)
        results_scroll.pack(side="right", fill="y")
        results.tag_configure(
            "PASS",
            foreground=theme_color("#18794E", dark_mode, theme_settings),
        )
        results.tag_configure(
            "FAIL",
            foreground=theme_color("#B42332", dark_mode, theme_settings),
        )
        results.tag_configure(
            "ERROR",
            foreground=theme_color("#B42332", dark_mode, theme_settings),
        )
        results.tag_configure("SKIP", foreground=muted_color)
        results.tag_configure("details", foreground=muted_color)

        footer = ttk.Frame(content)
        footer.pack(fill="x", pady=(12, 0))
        if simulated:
            ttk.Label(footer, text="DEMO", style="Subtitle.TLabel").pack(anchor="w")
        footer_actions = ttk.Frame(footer)
        footer_actions.pack(fill="x", pady=(4, 0))
        ttk.Label(
            footer_actions,
            text="Nie wyłączaj aplikacji podczas testowania.",
            style="Subtitle.TLabel",
        ).pack(side="left", fill="x", expand=True)
        close_button = ttk.Button(
            footer_actions,
            text="Zatrzymaj" if simulated else "Zamknij",
            state="normal" if simulated else "disabled",
        )
        close_button.pack(side="right")

        event_file: Path | None = None
        process = None
        if not simulated:
            try:
                with tempfile.NamedTemporaryFile(
                    prefix="blachcalc-test-results-",
                    suffix=".jsonl",
                    delete=False,
                ) as event_stream:
                    event_file = Path(event_stream.name)
                process = start_application_test_worker(event_file)
            except OSError as error:
                dialog.destroy()
                if event_file is not None:
                    try:
                        event_file.unlink(missing_ok=True)
                    except OSError as cleanup_error:
                        messagebox.showwarning(
                            "Testy aplikacji",
                            f"Nie udało się usunąć pliku tymczasowego:\n{cleanup_error}",
                            parent=parent,
                        )
                messagebox.showerror(
                    "Testy aplikacji",
                    f"Nie udało się uruchomić testów:\n{error}",
                    parent=parent,
                )
                return

        state: dict[str, Any] = {
            "offset": 0,
            "pending": "",
            "events": [],
            "done": 0,
            "total": 0,
            "summary": None,
            "problems": {},
            "transport_error": "",
            "finished": False,
            "after_id": None,
        }

        def append_result(line: str, tag: str | None = None) -> None:
            results.configure(state="normal")
            if simulated and int(results.index("end-1c").split(".")[0]) > 1200:
                results.delete("1.0", "201.0")
            results.insert("end", line, tag or ())
            results.see("end")
            results.configure(state="disabled")

        def close_dialog() -> None:
            if simulated and not state["finished"]:
                stop_simulation()
            elif not state["finished"]:
                return
            if event_file is not None:
                try:
                    event_file.unlink(missing_ok=True)
                except OSError as error:
                    messagebox.showwarning(
                        "Testy aplikacji",
                        f"Nie udało się usunąć pliku tymczasowego:\n{error}",
                        parent=parent,
                    )
            if simulated:
                self.app._simulated_test_stop = None
            dialog.destroy()

        dialog.protocol("WM_DELETE_WINDOW", close_dialog)
        dialog.grab_set()

        def update_progress(done: int, total: int) -> None:
            state["done"] = done
            state["total"] = total
            percentage = round(done * 100 / total) if total else 0
            progress_bar.configure(maximum=max(total, 1), value=done)
            progress_text.set(f"Postęp: {percentage}%  ·  {done} z {total} testów")

        def stop_simulation() -> None:
            if not simulated or state["finished"]:
                return
            state["finished"] = True
            after_id = state["after_id"]
            if after_id is not None:
                dialog.after_cancel(after_id)
                state["after_id"] = None
            self.app._simulated_test_stop = None
            current_test.set("")
            append_result("\n\n", "details")
            close_button.configure(
                text="Zamknij",
                command=close_dialog,
                state="normal",
            )

        def flash_test_window() -> None:
            previous_page = self.current_page
            page = random.choice(("quote", "history", "customers"))
            self._show_page(page)
            root = self.winfo_toplevel()
            root.lift()
            root.update_idletasks()
            targets: list[tk.Misc] = []

            def collect(widget: tk.Misc) -> None:
                for child in widget.winfo_children():
                    if (
                        isinstance(child, (ttk.Entry, ttk.Button, ttk.Combobox, ttk.Checkbutton, ttk.Treeview, tk.Entry))
                        and child.winfo_viewable()
                        and child.winfo_width() > 24
                        and child.winfo_height() > 12
                    ):
                        targets.append(child)
                    collect(child)

            collect(self)
            overlay: tk.Toplevel | None = None
            if targets:
                target = random.choice(targets)
                overlay = tk.Toplevel(root)
                overlay.overrideredirect(True)
                overlay.attributes("-topmost", True)
                overlay.attributes("-alpha", 0.35)
                overlay.configure(bg=theme_color(ACCENT, dark_mode, theme_settings))
                overlay.geometry(
                    f"{target.winfo_width()}x{target.winfo_height()}"
                    f"+{target.winfo_rootx()}+{target.winfo_rooty()}"
                )

            def restore() -> None:
                if overlay is not None and overlay.winfo_exists():
                    overlay.destroy()
                if self.winfo_exists():
                    self._show_page(previous_page)
                if dialog.winfo_exists():
                    dialog.lift()

            dialog.after(random.randint(350, 900), restore)

        def simulate_next_test() -> None:
            if state["finished"] or not dialog.winfo_exists():
                return
            if random.random() < 0.18:
                flash_test_window()
            if state["done"] >= state["total"]:
                append_result(
                    f"\n— Seria {state['cycle']} zakończona ({state['total']} pozycji) —\n",
                    "details",
                )
                state["cycle"] += 1
                state["total"] = random.randint(185, 245)
                state["done"] = 0
                update_progress(0, state["total"])
                current_test.set(
                    f"Przygotowuje kolejną serię: {state['total']} pozycji…"
                )
                delay = random.randint(450, 1400)
                state["after_id"] = dialog.after(delay, simulate_next_test)
                return

            test_names = (
                "test_quote_calculation",
                "test_material_price_validation",
                "test_customer_record",
                "test_offer_pdf_export",
                "test_delivery_note_layout",
                "test_theme_palette",
                "test_database_backup",
                "test_settings_persistence",
                "test_photo_gallery_selection",
                "test_keyboard_navigation",
                "test_excel_export",
                "test_quote_history_filter",
                "test_responsive_layout",
                "test_input_validation",
                "test_application_update",
                "test_packaging_calculation",
                "test_company_profile",
                "test_document_numbering",
            )
            test_name = random.choice(test_names)
            number = state["done"] + 1
            status = "SKIP" if random.random() < 0.015 else "PASS"
            current_test.set(
                f"{test_name}  ·  pozycja {number}/{state['total']}"
            )
            append_result(
                f"{number:03d}  {status:<5}  {test_name}\n",
                status,
            )
            if status == "SKIP":
                append_result("      \n", "details")
            state["done"] = number
            update_progress(number, state["total"])
            delay = random.randint(70, 760)
            if number % random.randint(11, 23) == 0:
                delay += random.randint(250, 950)
            state["after_id"] = dialog.after(delay, simulate_next_test)

        close_button.configure(
            command=stop_simulation if simulated else close_dialog
        )
        if simulated:
            state["cycle"] = 1
            state["total"] = random.randint(185, 245)
            self.app._simulated_test_stop = stop_simulation
            update_progress(0, state["total"])
            state["after_id"] = dialog.after(
                random.randint(180, 650),
                simulate_next_test,
            )

        def handle_event(event: dict[str, Any]) -> None:
            event_type = event.get("event")
            if event_type == "total":
                total = int(event["total"])
                update_progress(0, total)
                current_test.set(f"Znaleziono {total} testów.")
            elif event_type == "start":
                parts = str(event["test"]).split(".")
                current_test.set(" · ".join(parts[-2:]))
            elif event_type == "problem":
                state["problems"][event["test"]] = event["details"]
            elif event_type == "skip":
                state["problems"][event["test"]] = event["reason"]
            elif event_type == "result":
                status = str(event["status"])
                test_name = " · ".join(str(event["test"]).split(".")[-2:])
                append_result(
                    f"{state['done'] + 1:03d}  {status:<5}  {test_name}\n",
                    status if status in {"PASS", "FAIL", "ERROR", "SKIP"} else None,
                )
                if status in {"FAIL", "ERROR"}:
                    details = state["problems"].get(event["test"], "")
                    if details:
                        append_result(f"{details}\n\n", "details")
                elif status == "SKIP":
                    reason = state["problems"].get(event["test"], "")
                    if reason:
                        append_result(f"      Powód: {reason}\n", "details")
            elif event_type == "progress":
                update_progress(int(event["done"]), int(event["total"]))
            elif event_type == "done":
                state["summary"] = event

        def finish() -> None:
            state["finished"] = True
            summary = state["summary"]
            close_button.configure(state="normal")
            if summary is None:
                return_code = process.poll() if process is not None else "nieznany"
                current_test.set(
                    f"Proces testów zakończył się nieoczekiwanie (kod {return_code})."
                )
                progress_text.set(
                    f"Testy przerwane: {state['done']} z {state['total']} "
                    f"({round(state['done'] * 100 / state['total']) if state['total'] else 0}%)"
                )
                if state["transport_error"]:
                    append_result(f"\nBłąd odczytu wyników: {state['transport_error']}\n", "ERROR")
                return
            failures = int(summary["failures"]) + int(summary["errors"])
            skipped = int(summary["skipped"])
            result_label = "Wszystkie testy zaliczone." if summary["ok"] else "Testy zakończone z błędami."
            current_test.set(
                f"{result_label}  ·  Błędy: {failures}  ·  Pominięte: {skipped}"
            )
            progress_text.set(
                f"Postęp: {round(state['done'] * 100 / state['total']) if state['total'] else 100}%"
                f"  ·  {state['done']} z {state['total']} testów"
            )
            if state["transport_error"]:
                append_result(f"\nBłąd odczytu wyników: {state['transport_error']}\n", "ERROR")

        def poll() -> None:
            if not dialog.winfo_exists():
                return
            try:
                with event_file.open("r", encoding="utf-8") as event_stream:
                    event_stream.seek(state["offset"])
                    chunk = event_stream.read()
                    state["offset"] = event_stream.tell()
            except OSError as error:
                state["transport_error"] = str(error)
                chunk = ""
            if chunk:
                lines = (state["pending"] + chunk).split("\n")
                state["pending"] = lines.pop()
                for line in lines:
                    if not line:
                        continue
                    try:
                        state["events"].append(json.loads(line))
                    except json.JSONDecodeError as error:
                        state["transport_error"] = str(error)

            reached_progress = False
            while state["events"]:
                event = state["events"].pop(0)
                handle_event(event)
                if event.get("event") == "progress":
                    reached_progress = True
                    break

            if (
                process is not None
                and process.poll() is not None
                and not state["pending"]
                and not state["events"]
            ):
                finish()
                return
            dialog.after(135 if reached_progress else 30, poll)

        if not simulated:
            dialog.after(30, poll)

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
        dialog.minsize(min(480, screen_width - 24), min(360, screen_height - 48))
        dialog.geometry(
            f"{min(1100, screen_width - 24)}x{min(900, screen_height - 48)}"
        )
        try:
            dialog.state("zoomed")
        except tk.TclError:
            pass

        navigation = ttk.Frame(dialog, padding=(18, 12, 18, 4))
        navigation.pack(side="top", fill="x")
        navigation.grid_columnconfigure(2, weight=1)

        def create_scrollable_page(parent: tk.Misc) -> tuple[tk.Frame, tk.Frame]:
            tab = tk.Frame(parent)
            canvas = tk.Canvas(tab, bg=WHITE, highlightthickness=0)
            scrollbar = ttk.Scrollbar(tab, orient="vertical", command=canvas.yview)
            content = tk.Frame(canvas, bg=WHITE, padx=22, pady=20)
            content_window = canvas.create_window(
                (0, 0),
                window=content,
                anchor="nw",
            )
            canvas.configure(yscrollcommand=scrollbar.set)
            content.bind(
                "<Configure>",
                lambda _event: canvas.configure(scrollregion=canvas.bbox("all")),
            )
            canvas.bind(
                "<Configure>",
                lambda event: canvas.itemconfigure(content_window, width=event.width),
            )
            canvas.pack(side="left", fill="both", expand=True)
            scrollbar.pack(side="right", fill="y")
            return tab, content

        notebook = ttk.Notebook(dialog)
        notebook.pack(fill="both", expand=True, padx=18, pady=(4, 10))
        company_tab, company_page = create_scrollable_page(notebook)
        pricing_tab, pricing_page = create_scrollable_page(notebook)
        documents_tab, documents_page = create_scrollable_page(notebook)
        application_tab, application_page = create_scrollable_page(notebook)
        appearance_tab, appearance_page = create_scrollable_page(notebook)
        notebook.add(company_tab, text="Firma")
        notebook.add(pricing_tab, text="Wycena")
        notebook.add(documents_tab, text="Dokumenty")
        notebook.add(appearance_tab, text="Wygląd")
        notebook.add(application_tab, text="Aplikacja")

        def page_heading(page: tk.Misc, title: str, description: str) -> None:
            tk.Label(
                page,
                text=title,
                bg=WHITE,
                fg=INK,
                font=("Segoe UI", 15, "bold"),
            ).grid(row=0, column=0, columnspan=4, sticky="w", pady=(0, 3))
            tk.Label(
                page,
                text=description,
                bg=WHITE,
                fg=MUTED,
                font=("Segoe UI", 9),
                wraplength=760,
                justify="left",
            ).grid(row=1, column=0, columnspan=4, sticky="w", pady=(0, 14))
            page.grid_columnconfigure(1, weight=1)

        def add_field(
            page: tk.Misc,
            row: int,
            key: str,
            label: str,
            variables: dict[str, tk.StringVar],
            default: str | None = None,
        ) -> None:
            variable = tk.StringVar(value=settings.get(key, ""))
            variables[key] = variable
            tk.Label(
                page,
                text=label,
                bg=WHITE,
                fg=MUTED,
                font=("Segoe UI", 9, "bold"),
            ).grid(row=row, column=0, sticky="w", padx=(0, 14), pady=5)
            ttk.Entry(page, textvariable=variable).grid(
                row=row,
                column=1,
                columnspan=2,
                sticky="ew",
                pady=5,
            )
            ttk.Button(
                page,
                text="Domyślne",
                style="Quiet.TButton",
                command=lambda: variable.set(
                    DEFAULT_SETTINGS.get(key, "") if default is None else default
                ),
            ).grid(row=row, column=3, padx=(8, 0), pady=5)

        def add_color_field(
            page: tk.Misc,
            row: int,
            key: str,
            label: str,
            variables: dict[str, tk.StringVar],
        ) -> None:
            variable = tk.StringVar(value=settings.get(key, DEFAULT_SETTINGS[key]))
            variables[key] = variable

            def choose_color() -> None:
                _rgb, selected = colorchooser.askcolor(
                    color=variable.get(),
                    parent=dialog,
                    title=f"Wybierz kolor: {label}",
                )
                if selected:
                    variable.set(selected.upper())

            sample = tk.Label(
                page,
                textvariable=variable,
                bg=variable.get(),
                fg=INK,
                font=("Consolas", 9, "bold"),
                padx=8,
                pady=5,
            )

            def update_sample(*_args: object) -> None:
                color = variable.get()
                sample.configure(background=color)
                red, green, blue = (
                    int(color[index:index + 2], 16)
                    for index in (1, 3, 5)
                )
                brightness = (red * 299 + green * 587 + blue * 114) // 1000
                sample.configure(foreground="#FFFFFF" if brightness < 140 else INK)

            variable.trace_add("write", update_sample)
            sample.grid(row=row, column=2, sticky="w", padx=(8, 0), pady=5)
            tk.Label(
                page,
                text=label,
                bg=WHITE,
                fg=MUTED,
                font=("Segoe UI", 9, "bold"),
            ).grid(row=row, column=0, sticky="w", padx=(0, 14), pady=5)
            ttk.Button(
                page,
                text="Wybierz kolor…",
                command=choose_color,
            ).grid(row=row, column=1, sticky="w", pady=5)
            ttk.Button(
                page,
                text="Domyślne",
                style="Quiet.TButton",
                command=lambda: variable.set(DEFAULT_SETTINGS[key]),
            ).grid(row=row, column=3, padx=(8, 0), pady=5)

        def add_directory_field(
            page: tk.Misc,
            row: int,
            key: str,
            label: str,
            variables: dict[str, tk.StringVar],
            default: str,
        ) -> None:
            variable = tk.StringVar(value=settings.get(key, default))
            variables[key] = variable

            def choose_directory() -> None:
                current = Path(variable.get()).expanduser()
                initial = current if current.is_dir() else Path.home()
                selected = filedialog.askdirectory(
                    parent=dialog,
                    title=f"Wybierz folder: {label}",
                    initialdir=initial,
                    mustexist=True,
                )
                if selected:
                    variable.set(selected)

            tk.Label(
                page,
                text=label,
                bg=WHITE,
                fg=MUTED,
                font=("Segoe UI", 9, "bold"),
            ).grid(row=row, column=0, sticky="w", padx=(0, 14), pady=5)
            ttk.Entry(page, textvariable=variable).grid(
                row=row,
                column=1,
                sticky="ew",
                pady=5,
            )
            ttk.Button(
                page,
                text="Wybierz…",
                command=choose_directory,
            ).grid(row=row, column=2, padx=(8, 0), pady=5)
            ttk.Button(
                page,
                text="Domyślne",
                style="Quiet.TButton",
                command=lambda: variable.set(default),
            ).grid(row=row, column=3, padx=(8, 0), pady=5)

        page_heading(
            company_page,
            "Profil firmowy",
            "Dane firmy są wykorzystywane w nagłówku oferty PDF.",
        )
        variables: dict[str, tk.StringVar] = {}
        palette_samples: dict[str, tk.Label] = {}

        def refresh_palette_samples() -> None:
            for key, sample in palette_samples.items():
                color = variables[key].get().strip()
                if re.fullmatch(r"#[0-9A-Fa-f]{6}", color):
                    sample.configure(bg=color.upper())

        page_heading(
            appearance_page,
            "Wygląd aplikacji",
            "Dostosuj kolory interfejsu niezależnie dla jasnego i ciemnego motywu. "
            "Kliknij kwadracik, aby zmienić kolor (prawy przycisk myszy przywraca domyślny). "
            "Podgląd odpowiada aktualnie wybranej zakładce.",
        )
        def reset_theme_palettes() -> None:
            for key, (default, _label) in THEME_PALETTE_SETTINGS.items():
                variables[key].set(default)

        ttk.Button(
            appearance_page,
            text="Przywróć domyślne palety",
            style="Quiet.TButton",
            command=reset_theme_palettes,
        ).grid(row=2, column=0, sticky="w", pady=(0, 10))
        palette_save_status = tk.Label(
            appearance_page,
            text="",
            bg=WHITE,
            fg="#18794E",
            font=("Segoe UI", 9, "bold"),
        )
        palette_save_status.grid(row=2, column=1, columnspan=2, sticky="w", padx=(12, 0))
        appearance_notebook = ttk.Notebook(appearance_page)
        appearance_notebook.grid(row=4, column=0, columnspan=4, sticky="ew")

        display_frame = tk.LabelFrame(
            appearance_page,
            text="Ekran i ostrość obrazu",
            bg=WHITE,
            fg=NAVY,
            font=("Segoe UI", 9, "bold"),
            padx=10,
            pady=8,
        )
        display_frame.grid(row=5, column=0, columnspan=4, sticky="ew", pady=(10, 0))
        variables["dpi_awareness"] = tk.StringVar(value=settings.get("dpi_awareness", "1"))
        variables["ui_scale_percent"] = tk.StringVar(
            value=settings.get("ui_scale_percent", "100")
        )
        tk.Checkbutton(
            display_frame,
            text="Ostry obraz na ekranach HiDPI (wymaga ponownego uruchomienia aplikacji)",
            variable=variables["dpi_awareness"],
            onvalue="1",
            offvalue="0",
            bg=WHITE,
            fg=INK,
            activebackground=WHITE,
            selectcolor=WHITE,
            font=("Segoe UI", 9),
        ).grid(row=0, column=0, columnspan=3, sticky="w")
        tk.Label(
            display_frame,
            text="Skala interfejsu (%)",
            bg=WHITE,
            fg=INK,
            font=("Segoe UI", 9),
        ).grid(row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Combobox(
            display_frame,
            textvariable=variables["ui_scale_percent"],
            values=("75", "90", "100", "110", "125", "150", "175", "200", "250"),
            width=8,
        ).grid(row=1, column=1, sticky="w", padx=8, pady=(8, 0))
        tk.Label(
            display_frame,
            text="Zmiana skali działa od razu; zwiększ ją, jeśli tekst jest zbyt mały.",
            bg=WHITE,
            fg=MUTED,
            font=("Segoe UI", 8),
        ).grid(row=1, column=2, sticky="w", pady=(8, 0))
        appearance_page.grid_rowconfigure(3, weight=1)
        appearance_page.grid_columnconfigure(0, weight=1)

        palette_groups = (
            (
                "Powierzchnie",
                ("background", "surface", "subtle", "hover", "selection", "border", "disabled_surface"),
            ),
            ("Tekst", ("text", "muted", "disabled_text")),
            ("Akcenty", ("accent", "accent_pressed", "accent_secondary")),
            ("Status i komunikaty", ("success", "danger", "danger_hover", "danger_surface")),
        )
        for mode, mode_label in (("light", "Jasny motyw"), ("dark", "Ciemny motyw")):
            palette_page = tk.Frame(appearance_notebook, bg=WHITE, padx=12, pady=12)
            appearance_notebook.add(palette_page, text=mode_label)
            for group_index, (group_label, roles) in enumerate(palette_groups):
                group = tk.LabelFrame(
                    palette_page,
                    text=group_label,
                    bg=WHITE,
                    fg=NAVY,
                    font=("Segoe UI", 9, "bold"),
                    padx=10,
                    pady=8,
                )
                group.grid(
                    row=group_index // 2,
                    column=group_index % 2,
                    sticky="nsew",
                    padx=6,
                    pady=6,
                )
                for row, role in enumerate(roles):
                    key = f"ui_{mode}_{role}"
                    default, label = THEME_PALETTE_SETTINGS[key]
                    variable = tk.StringVar(value=settings.get(key, default))
                    variables[key] = variable

                    def choose_palette_color(
                        _event: tk.Event | None = None,
                        color_variable: tk.StringVar = variable,
                        color_label: str = label,
                    ) -> None:
                        _rgb, selected = colorchooser.askcolor(
                            color=color_variable.get(),
                            parent=dialog,
                            title=f"Wybierz kolor: {color_label}",
                        )
                        if selected:
                            color_variable.set(selected.upper())

                    tile = tk.Frame(group, bg=WHITE)
                    tile.grid(row=0, column=row, padx=5, pady=(0, 2), sticky="n")
                    sample = tk.Label(
                        tile,
                        text="",
                        width=7,
                        height=2,
                        bg=variable.get(),
                        relief="solid",
                        borderwidth=1,
                        cursor="hand2",
                    )
                    # Próbki pokazują dokładny kolor palety; globalne mapowanie motywu nie może ich przekolorowywać.
                    sample._blachcalc_skip_theme = True
                    sample.pack()
                    sample.bind("<Button-1>", choose_palette_color)
                    sample.bind(
                        "<Button-3>",
                        lambda _event, color_variable=variable, default_color=default: (
                            color_variable.set(default_color)
                        ),
                    )
                    tk.Label(
                        tile,
                        text=label,
                        bg=WHITE,
                        fg=MUTED,
                        font=("Segoe UI", 7),
                        wraplength=62,
                        justify="center",
                    ).pack()
                    palette_samples[key] = sample
                    variable.trace_add(
                        "write",
                        lambda *_args, color_variable=variable, color_sample=sample: (
                            color_sample.configure(bg=color_variable.get())
                            if re.fullmatch(r"#[0-9A-Fa-f]{6}", color_variable.get())
                            else None
                        ),
                    )
                palette_page.grid_columnconfigure(group_index % 2, weight=1)

        preview_frame = tk.LabelFrame(
            appearance_page,
            text="Podgląd strony początkowej",
            bg=WHITE,
            fg=NAVY,
            font=("Segoe UI", 9, "bold"),
            padx=10,
            pady=8,
        )
        preview_frame.grid(row=3, column=0, columnspan=4, sticky="nsew", pady=(0, 10))
        preview_window = tk.Frame(preview_frame, highlightthickness=1, height=260)
        preview_window._blachcalc_skip_theme = True
        preview_window.pack(fill="both", expand=True)
        preview_window.pack_propagate(False)
        preview_sidebar = tk.Frame(preview_window, width=210)
        preview_sidebar.pack(side="left", fill="y")
        preview_sidebar.pack_propagate(False)
        preview_sidebar_title = tk.Label(
            preview_sidebar, text="Elementy zamówienia", font=("Segoe UI", 10, "bold"), anchor="w"
        )
        preview_sidebar_title.pack(fill="x", padx=12, pady=(14, 8))
        preview_row_selected = tk.Label(
            preview_sidebar, text="Blacha S235 · 2 szt.", font=("Segoe UI", 9), anchor="w", pady=5, padx=6
        )
        preview_row_selected.pack(fill="x", padx=8, pady=2)
        preview_row_plain = tk.Label(
            preview_sidebar, text="Kątownik · 5 szt.", font=("Segoe UI", 9), anchor="w", pady=5, padx=6
        )
        preview_row_plain.pack(fill="x", padx=8, pady=2)
        preview_main = tk.Frame(preview_window)
        preview_main.pack(side="left", fill="both", expand=True, padx=16, pady=14)
        preview_stripe = tk.Frame(preview_main, width=4, height=40)
        preview_stripe.pack(side="left", fill="y", padx=(0, 12))
        preview_body = tk.Frame(preview_main)
        preview_body.pack(side="left", fill="both", expand=True)
        preview_heading = tk.Label(
            preview_body, text="Nowa wycena", font=("Segoe UI", 15, "bold"), anchor="w"
        )
        preview_heading.pack(fill="x")
        preview_hint = tk.Label(
            preview_body, text="Uzupełnij dane zlecenia i dodaj elementy.", font=("Segoe UI", 10), anchor="w"
        )
        preview_hint.pack(fill="x")
        preview_buttons = tk.Frame(preview_body)
        preview_buttons.pack(fill="x", pady=(14, 0))
        preview_input = tk.Label(
            preview_buttons, text=" Zleceniodawca ", font=("Segoe UI", 10), relief="solid", borderwidth=1, padx=8, pady=4
        )
        preview_input.pack(side="left")
        preview_primary = tk.Label(
            preview_buttons, text=" ＋ Dodaj pozycję ", font=("Segoe UI", 10, "bold"), padx=10, pady=5
        )
        preview_primary.pack(side="left", padx=(10, 0))
        preview_danger = tk.Label(
            preview_buttons, text=" Usuń ", font=("Segoe UI", 10, "bold"), padx=10, pady=5
        )
        preview_danger.pack(side="left", padx=(10, 0))
        preview_success = tk.Label(preview_buttons, text="✓ Zapisano", font=("Segoe UI", 10, "bold"))
        preview_success.pack(side="left", padx=(14, 0))
        preview_disabled = tk.Label(preview_buttons, text=" Nieaktywne ", font=("Segoe UI", 10), padx=10, pady=5)
        preview_disabled.pack(side="left", padx=(10, 0))

        def refresh_theme_preview(*_args: object) -> None:
            mode = "dark" if appearance_notebook.index("current") == 1 else "light"

            def color(role: str) -> str:
                value = variables[f"ui_{mode}_{role}"].get().strip()
                if re.fullmatch(r"#[0-9A-Fa-f]{6}", value):
                    return value.upper()
                return THEME_PALETTE_SETTINGS[f"ui_{mode}_{role}"][0]

            accent, danger = color("accent"), color("danger")
            preview_window.configure(bg=color("background"), highlightbackground=color("border"))
            preview_sidebar.configure(bg=color("surface"))
            preview_sidebar_title.configure(bg=color("surface"), fg=color("text"))
            preview_row_selected.configure(bg=color("selection"), fg=color("text"))
            preview_row_plain.configure(bg=color("surface"), fg=color("muted"))
            preview_main.configure(bg=color("background"))
            preview_stripe.configure(bg=color("accent_secondary"))
            preview_body.configure(bg=color("background"))
            preview_heading.configure(bg=color("background"), fg=color("text"))
            preview_hint.configure(bg=color("background"), fg=color("muted"))
            preview_buttons.configure(bg=color("background"))
            preview_input.configure(bg=color("subtle"), fg=color("text"), highlightbackground=color("border"))
            preview_primary.configure(bg=accent, fg=contrasting_text_color(accent))
            preview_danger.configure(bg=danger, fg=contrasting_text_color(danger))
            preview_success.configure(bg=color("background"), fg=color("success"))
            preview_disabled.configure(bg=color("disabled_surface"), fg=color("disabled_text"))

        for palette_variable in (variables[key] for key in THEME_PALETTE_SETTINGS):
            palette_variable.trace_add("write", refresh_theme_preview)
        appearance_notebook.bind("<<NotebookTabChanged>>", refresh_theme_preview, add="+")
        refresh_theme_preview()

        add_field(company_page, 2, "company_name", "Nazwa firmy", variables)
        previous_company_address = settings.get("company_address", "")
        company_address_variables, company_legacy_address = self._address_editor(
            company_page,
            3,
            settings,
            key_prefix="company_",
            legacy_address=(
                ""
                if parse_polish_address(previous_company_address)
                else previous_company_address
            ),
            include_legacy=bool(
                previous_company_address
                and not parse_polish_address(previous_company_address)
            ),
        )
        def reset_company_address() -> None:
            for key, variable in company_address_variables.items():
                variable.set(DEFAULT_SETTINGS.get(key, ""))
            company_legacy_address.set("")

        ttk.Button(
            company_page,
            text="Domyślny adres",
            style="Quiet.TButton",
            command=reset_company_address,
        ).grid(row=3, column=3, sticky="e", padx=(8, 0), pady=5)
        company_fields = (
            ("company_phone", "Telefon firmy"),
            ("company_email", "E-mail firmy"),
            ("company_tax_id", "NIP firmy"),
            ("company_regon", "REGON firmy"),
            ("company_website", "Strona internetowa"),
            ("brand_tagline", "Hasło / opis marki"),
        )
        for row, (key, label) in enumerate(company_fields, start=5):
            add_field(company_page, row, key, label, variables)

        logo_var = tk.StringVar(value=settings.get("logo_path", ""))
        logo_row = 5 + len(company_fields)
        tk.Label(
            company_page,
            text="Firmowe logo (PNG / GIF)",
            bg=WHITE,
            fg=MUTED,
            font=("Segoe UI", 9, "bold"),
        ).grid(row=logo_row, column=0, sticky="w", padx=(0, 14), pady=5)
        ttk.Entry(company_page, textvariable=logo_var).grid(
            row=logo_row,
            column=1,
            sticky="ew",
            pady=5,
        )

        def select_logo() -> None:
            filename = filedialog.askopenfilename(
                parent=dialog,
                title="Wybierz logo firmy",
                filetypes=[("Logo PNG lub GIF", "*.png *.gif"), ("Wszystkie pliki", "*.*")],
            )
            if filename:
                logo_var.set(filename)

        ttk.Button(company_page, text="Wybierz…", command=select_logo).grid(
            row=logo_row,
            column=2,
            padx=(7, 0),
        )
        ttk.Button(
            company_page,
            text="Domyślne",
            style="Quiet.TButton",
            command=lambda: logo_var.set(DEFAULT_SETTINGS["logo_path"]),
        ).grid(row=logo_row, column=3, padx=(8, 0))

        page_heading(
            pricing_page,
            "Parametry wyceny",
            "Ceny i stawki są podawane w domyślnej walucie. Przy jej zmianie dostosuj cennik konwerterem.",
        )
        pricing_fields = (
            ("price_per_kg", "Domyślna cena materiału (za kg)"),
            ("burning_rate_per_hour", "Domyślna stawka palenia (za godzinę)"),
            ("vat_percent", "Domyślna stawka VAT (%)"),
            ("bending_price", "Cena za jedno gięcie (netto)"),
            *(
                (packaging_setting_key(key), f"Cena opakowania: {label} (netto)")
                for key, label in PACKAGING_OPTIONS.items()
            ),
        )
        for row, (key, label) in enumerate(pricing_fields, start=2):
            add_field(pricing_page, row, key, label, variables)

        currency_row = len(pricing_fields) + 2
        currency_var = tk.StringVar(
            value=settings.get("default_currency", DEFAULT_SETTINGS["default_currency"])
        )
        currency_rates_var = tk.StringVar(
            value=settings.get("currency_rates", DEFAULT_SETTINGS["currency_rates"])
        )
        variables["default_currency"] = currency_var
        variables["currency_rates"] = currency_rates_var
        tk.Label(
            pricing_page,
            text="Domyślna waluta wyceny",
            bg=WHITE,
            fg=MUTED,
            font=("Segoe UI", 9, "bold"),
        ).grid(row=currency_row, column=0, sticky="w", padx=(0, 14), pady=5)
        ttk.Combobox(
            pricing_page,
            textvariable=currency_var,
            state="readonly",
            values=tuple(CURRENCIES),
            width=10,
        ).grid(row=currency_row, column=1, sticky="w", pady=5)
        ttk.Button(
            pricing_page,
            text="🧮",
            width=3,
            style="Quiet.TButton",
            command=lambda: self._open_currency_converter(
                dialog,
                currency_rates_var,
                lambda _rates: None,
            ),
        ).grid(row=currency_row, column=2, sticky="w", padx=(8, 0), pady=5)
        ttk.Label(
            pricing_page,
            text="Otwórz konwerter walut",
            style="Subtitle.TLabel",
        ).grid(row=currency_row, column=3, sticky="w", padx=(8, 0))

        materials_row = len(pricing_fields) + 3
        tk.Label(
            pricing_page,
            text="Biblioteka materiałów",
            bg=WHITE,
            fg=MUTED,
            font=("Segoe UI", 9, "bold"),
        ).grid(row=materials_row, column=0, sticky="nw", padx=(0, 14), pady=5)
        materials_frame = tk.Frame(pricing_page, bg=WHITE)
        materials_frame.grid(row=materials_row, column=1, columnspan=2, sticky="ew", pady=5)
        material_records = load_materials(
            settings.get("materials_library"),
            settings.get("materials", ""),
        )
        materials_tree = ttk.Treeview(
            materials_frame,
            columns=("category", "name", "thickness", "price"),
            show="headings",
            height=5,
            selectmode="browse",
        )
        for key, label, width in (
            ("category", "Kategoria", 100),
            ("name", "Materiał / gatunek", 190),
            ("thickness", "Grubość mm", 85),
            ("price", "Cena / kg", 85),
        ):
            materials_tree.heading(key, text=label)
            materials_tree.column(key, width=width, anchor="w")
        materials_tree.grid(row=0, column=0, columnspan=4, sticky="ew")
        materials_scroll = ttk.Scrollbar(
            materials_frame, orient="vertical", command=materials_tree.yview
        )
        materials_tree.configure(yscrollcommand=materials_scroll.set)
        materials_scroll.grid(row=0, column=4, sticky="ns")
        materials_frame.grid_columnconfigure(1, weight=1)

        category_var = tk.StringVar(value=CATEGORIES[0])
        material_name_var = tk.StringVar()
        material_thickness_var = tk.StringVar()
        material_price_var = tk.StringVar()
        for column, label in enumerate(
            ("Kategoria", "Materiał / gatunek", "Grubość (mm)", "Cena / kg")
        ):
            ttk.Label(
                materials_frame, text=label, style="Subtitle.TLabel"
            ).grid(row=1, column=column, sticky="w", padx=(0, 5), pady=(7, 2))
        ttk.Combobox(
            materials_frame,
            textvariable=category_var,
            values=CATEGORIES,
            state="readonly",
            width=12,
        ).grid(row=2, column=0, sticky="ew", padx=(0, 5))
        material_name_entry = ttk.Entry(
            materials_frame, textvariable=material_name_var
        )
        material_name_entry.grid(row=2, column=1, sticky="ew", padx=(0, 5))
        ttk.Entry(
            materials_frame, textvariable=material_thickness_var, width=10
        ).grid(row=2, column=2, sticky="ew", padx=(0, 5))
        ttk.Entry(materials_frame, textvariable=material_price_var, width=10).grid(
            row=2, column=3, sticky="ew", padx=(0, 5)
        )

        def refresh_material_table() -> None:
            materials_tree.delete(*materials_tree.get_children())
            for index, material in enumerate(material_records):
                materials_tree.insert(
                    "",
                    "end",
                    iid=str(index),
                    values=(
                        material["category"],
                        material["name"],
                        material["thickness_mm"],
                        material["price_per_kg"],
                    ),
                )

        def select_material(_event: tk.Event | None = None) -> None:
            selected = materials_tree.selection()
            if not selected:
                return
            material = material_records[int(selected[0])]
            category_var.set(material["category"])
            material_name_var.set(material["name"])
            material_thickness_var.set(material["thickness_mm"])
            material_price_var.set(material["price_per_kg"])

        def save_material(_event: tk.Event | None = None) -> str:
            name = " ".join(material_name_var.get().split())
            if not name:
                messagebox.showerror(
                    "Biblioteka materiałów",
                    "Podaj nazwę materiału lub gatunek.",
                    parent=dialog,
                )
                return "break"
            material = {
                "category": category_var.get(),
                "name": name,
                "thickness_mm": material_thickness_var.get().strip(),
                "price_per_kg": material_price_var.get().strip(),
            }
            selected = materials_tree.selection()
            index = int(selected[0]) if selected else None
            candidate = list(material_records)
            if index is None:
                candidate.append(material)
            else:
                candidate[index] = material
            try:
                serialize_materials(candidate)
            except ValueError as error:
                messagebox.showerror("Biblioteka materiałów", str(error), parent=dialog)
                return "break"
            material_records[:] = load_materials(
                serialize_materials(candidate),
                "",
            )
            refresh_material_table()
            material_name_var.set("")
            material_thickness_var.set("")
            material_price_var.set("")
            materials_tree.selection_remove(*materials_tree.selection())
            return "break"

        def remove_material() -> None:
            selected = materials_tree.selection()
            if selected:
                del material_records[int(selected[0])]
                refresh_material_table()
                material_name_var.set("")
                material_thickness_var.set("")
                material_price_var.set("")

        materials_tree.bind("<<TreeviewSelect>>", select_material, add="+")
        ttk.Button(
            materials_frame,
            text="Dodaj / zapisz",
            command=save_material,
        ).grid(row=3, column=0, sticky="w", pady=(5, 0))
        ttk.Button(
            materials_frame,
            text="Usuń zaznaczony",
            style="Quiet.TButton",
            command=remove_material,
        ).grid(row=3, column=1, sticky="w", padx=(5, 0), pady=(5, 0))
        material_name_entry.bind("<Return>", save_material)
        refresh_material_table()

        page_heading(
            documents_page,
            "Dokumenty i oferta",
            "Dostosuj warunki handlowe, kolory oraz układ wydruków.",
        )
        document_fields = (
            ("offer_validity_days", "Ważność oferty (dni)", ""),
            ("payment_terms", "Warunki płatności", ""),
            ("delivery_terms", "Termin realizacji", DEFAULT_SETTINGS["delivery_terms"]),
            ("photo_width_mm", "Szerokość zdjęcia w ofercie (mm)", str(PHOTO_WIDTH_DEFAULT_MM)),
            ("office_row_height_mm", "Wysokość wiersza oferty biurowej (mm)", str(OFFICE_ROW_HEIGHT_DEFAULT_MM)),
            ("office_font_scale_percent", "Rozmiar tekstu oferty biurowej (%)", str(OFFICE_FONT_SCALE_DEFAULT_PERCENT)),
            ("wz_row_height_mm", "Wysokość wiersza WZ (mm)", str(WZ_ROW_HEIGHT_DEFAULT_MM)),
        )
        for row, (key, label, default) in enumerate(document_fields, start=2):
            add_field(documents_page, row, key, label, variables, default)
        add_color_field(documents_page, len(document_fields) + 2, "brand_primary", "Kolor główny PDF", variables)
        add_color_field(documents_page, len(document_fields) + 3, "brand_accent", "Kolor akcentu PDF", variables)
        offer_editor_row = len(document_fields) + 4
        ttk.Button(
            documents_page,
            text="Edytuj drugą stronę oferty…",
            command=lambda: self.open_offer_page_editor(dialog),
        ).grid(row=offer_editor_row, column=0, columnspan=2, sticky="w", pady=(12, 0))

        page_heading(
            application_page,
            "Aplikacja i dane",
            "Wybierz foldery zapisu. Dane są przenoszone z zachowaniem kopii bezpieczeństwa.",
        )
        default_photo_directory = DEFAULT_SETTINGS["item_photo_directory"]
        directory_variables: dict[str, tk.StringVar] = {}
        add_directory_field(
            application_page,
            2,
            "item_photo_directory",
            "Domyślny folder zdjęć",
            directory_variables,
            default_photo_directory,
        )
        managed_directory_fields = (
            ("offer_export_directory", "Oferty PDF"),
            ("wz_export_directory", "Dokumenty WZ"),
            ("excel_export_directory", "Pliki Excel"),
            ("print_jobs_directory", "Tymczasowe pliki drukowania"),
        )
        for row, (key, label) in enumerate(managed_directory_fields, start=3):
            add_directory_field(
                application_page,
                row,
                key,
                label,
                directory_variables,
                DEFAULT_SETTINGS[key],
            )

        database_directory_var = tk.StringVar(
            value=str(self.storage.database_path.parent.resolve())
        )
        update_source_choices = {
            "github": "GitHub (automatyczne sprawdzanie)",
            "local": "Plik lokalny (.exe)",
        }
        selected_update_source = settings.get(
            "update_source",
            DEFAULT_SETTINGS["update_source"],
        )
        update_source_var = tk.StringVar(
            value=update_source_choices.get(
                selected_update_source,
                update_source_choices["github"],
            )
        )
        local_update_path_var = tk.StringVar(
            value=settings.get("local_update_path", "")
        )

        def choose_database_directory() -> None:
            current = Path(database_directory_var.get()).expanduser()
            initial = current if current.is_dir() else default_data_directory()
            selected = filedialog.askdirectory(
                parent=dialog,
                title="Wybierz folder bazy i kopii zapasowych",
                initialdir=initial,
                mustexist=False,
            )
            if selected:
                database_directory_var.set(selected)

        database_row = 7
        tk.Label(
            application_page,
            text="Baza danych i kopie",
            bg=WHITE,
            fg=MUTED,
            font=("Segoe UI", 9, "bold"),
        ).grid(row=database_row, column=0, sticky="w", padx=(0, 14), pady=5)
        ttk.Entry(application_page, textvariable=database_directory_var).grid(
            row=database_row,
            column=1,
            sticky="ew",
            pady=5,
        )
        ttk.Button(
            application_page,
            text="Wybierz…",
            command=choose_database_directory,
        ).grid(row=database_row, column=2, padx=(8, 0), pady=5)
        ttk.Button(
            application_page,
            text="Domyślne",
            style="Quiet.TButton",
            command=lambda: database_directory_var.set(str(default_data_directory())),
        ).grid(row=database_row, column=3, padx=(8, 0), pady=5)
        ttk.Label(
            application_page,
            text=(
                f"Plik bazy: {self.storage.database_path.resolve()}\n"
                f"Kopie: {self.storage.backup_directory.resolve()}\n"
                "Zdjęcia pozycji są przechowywane w bazie danych.\n"
                f"Konfiguracja lokalizacji: {application_config_path().resolve()}"
            ),
            style="Subtitle.TLabel",
            justify="left",
        ).grid(row=database_row + 1, column=1, columnspan=3, sticky="w", pady=(2, 8))

        source_row = database_row + 2
        tk.Label(
            application_page,
            text="Źródło aktualizacji",
            bg=WHITE,
            fg=MUTED,
            font=("Segoe UI", 9, "bold"),
        ).grid(row=source_row, column=0, sticky="w", padx=(0, 14), pady=5)
        update_source_combo = ttk.Combobox(
            application_page,
            textvariable=update_source_var,
            state="readonly",
            values=tuple(update_source_choices.values()),
            width=36,
        )
        update_source_combo.grid(row=source_row, column=1, sticky="w", pady=5)
        update_source_label = ttk.Label(
            application_page,
            text="GitHub — sprawdzanie aktualizacji przy uruchomieniu",
            style="Subtitle.TLabel",
        )
        update_source_label.grid(row=source_row, column=2, columnspan=2, sticky="w", padx=(8, 0))

        installer_row = source_row + 1
        tk.Label(
            application_page,
            text="Lokalny instalator (.exe)",
            bg=WHITE,
            fg=MUTED,
            font=("Segoe UI", 9, "bold"),
        ).grid(row=installer_row, column=0, sticky="w", padx=(0, 14), pady=5)
        ttk.Entry(
            application_page,
            textvariable=local_update_path_var,
        ).grid(row=installer_row, column=1, sticky="ew", pady=5)

        def choose_local_installer() -> None:
            current = Path(local_update_path_var.get()).expanduser()
            initialdir = current.parent if current.is_file() else Path.home()
            selected = filedialog.askopenfilename(
                parent=dialog,
                title="Wybierz lokalny instalator BlachCalc",
                initialdir=initialdir,
                filetypes=[("Instalator BlachCalc", "*.exe"), ("Wszystkie pliki", "*.*")],
            )
            if selected:
                local_update_path_var.set(selected)

        ttk.Button(
            application_page,
            text="Wybierz…",
            command=choose_local_installer,
        ).grid(row=installer_row, column=2, padx=(8, 0), pady=5)
        ttk.Label(
            application_page,
            text="W trybie lokalnym aktualizację uruchamia przycisk poniżej.",
            style="Subtitle.TLabel",
        ).grid(row=installer_row + 1, column=1, columnspan=3, sticky="w", pady=(0, 6))

        def update_source_help(*_args: object) -> None:
            if update_source_var.get() == update_source_choices["local"]:
                update_source_label.configure(
                    text="Plik lokalny — bez połączenia z GitHubem"
                )
            else:
                update_source_label.configure(
                    text="GitHub — sprawdzanie aktualizacji przy uruchomieniu"
                )

        update_source_var.trace_add("write", update_source_help)
        update_source_help()

        update_button_clicked = [False]

        def update_from_settings() -> None:
            if update_button_clicked[0]:
                return
            update_button_clicked[0] = True
            dialog.grab_release()
            try:
                self.update_application()
            finally:
                if dialog.winfo_exists():
                    dialog.grab_set()

        app_actions = ttk.Frame(application_page)
        app_actions.grid(row=installer_row + 2, column=0, columnspan=4, sticky="w", pady=(12, 4))
        update_button = ttk.Button(
            app_actions,
            text="⟳  Aktualizuj aplikację",
            command=update_from_settings,
        )
        update_button.pack(side="left")
        ttk.Button(
            app_actions,
            text="Uruchom testy aplikacji…",
            command=lambda: self.run_application_tests(dialog),
        ).pack(side="left", padx=(8, 0))

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

        backup_actions = ttk.Frame(application_page)
        backup_actions.grid(
            row=installer_row + 3,
            column=0,
            columnspan=4,
            sticky="w",
            pady=(14, 0),
        )
        ttk.Button(
            backup_actions,
            text="Utwórz kopię zapasową…",
            command=backup,
        ).pack(side="left")
        ttk.Button(
            backup_actions,
            text="Przywróć kopię…",
            command=restore,
        ).pack(side="left", padx=(8, 0))
        ttk.Label(
            application_page,
            text="Automatyczne kopie: przy starcie i przed usunięciem.",
            style="Subtitle.TLabel",
        ).grid(
            row=installer_row + 4,
            column=0,
            columnspan=4,
            sticky="w",
            pady=(8, 0),
        )

        def save() -> None:
            try:
                material_price = parse_decimal(
                    variables["price_per_kg"].get(),
                    "Domyślna cena materiału",
                )
                rate = parse_decimal(variables["burning_rate_per_hour"].get(), "Domyślna stawka palenia")
                vat = parse_decimal(variables["vat_percent"].get(), "Domyślny VAT")
                bending_price = parse_decimal(variables["bending_price"].get(), "Cena za jedno gięcie")
                calculate_item_amounts(
                    calculate_quote(material_price, Decimal("1"), 0, rate, vat),
                    1, 1, "per_piece", vat, bending_price,
                )
                packaging_prices = {}
                for key, label in PACKAGING_OPTIONS.items():
                    setting_key = packaging_setting_key(key)
                    packaging_prices[setting_key] = parse_decimal(
                        variables[setting_key].get(), f"Cena opakowania: {label}"
                    )
                    calculate_quote(packaging_prices[setting_key], Decimal("1"), 0, rate, vat)
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
            updated["bending_price"] = str(bending_price)
            updated.update({key: str(value) for key, value in packaging_prices.items()})
            logo_path = logo_var.get().strip()
            if logo_path and not Path(logo_path).is_file():
                messagebox.showerror("Ustawienia", "Wybrany plik logo nie istnieje.", parent=dialog)
                return
            if logo_path and Path(logo_path).suffix.lower() not in {".png", ".gif"}:
                messagebox.showerror("Ustawienia", "Logo aplikacji musi być w formacie PNG lub GIF.", parent=dialog)
                return
            updated["logo_path"] = logo_path
            update_source = next(
                (
                    key
                    for key, label in update_source_choices.items()
                    if label == update_source_var.get()
                ),
                None,
            )
            if update_source is None:
                messagebox.showerror("Aktualizacje", "Wybierz prawidłowe źródło aktualizacji.", parent=dialog)
                return
            updated["update_source"] = update_source
            local_update_path = local_update_path_var.get().strip()
            updated["local_update_path"] = (
                str(Path(local_update_path).expanduser().resolve())
                if local_update_path
                else ""
            )
            path_settings = {
                key: value.get().strip()
                for key, value in directory_variables.items()
            }
            photo_directory = path_settings["item_photo_directory"]
            empty_path_label = next(
                (
                    label
                    for key, label in (
                        ("item_photo_directory", "Domyślny folder zdjęć"),
                        *managed_directory_fields,
                    )
                    if not path_settings[key]
                ),
                None,
            )
            if empty_path_label is not None:
                messagebox.showerror(
                    "Ustawienia",
                    f"Uzupełnij lokalizację: {empty_path_label}.",
                    parent=dialog,
                )
                return
            for key, directory in path_settings.items():
                updated[key] = str(Path(directory).expanduser().resolve())

            numeric_limits = {
                "photo_width_mm": (PHOTO_WIDTH_MIN_MM, PHOTO_WIDTH_MAX_MM, False),
                "office_row_height_mm": (
                    OFFICE_ROW_HEIGHT_MIN_MM,
                    OFFICE_ROW_HEIGHT_MAX_MM,
                    False,
                ),
                "office_font_scale_percent": (
                    OFFICE_FONT_SCALE_MIN_PERCENT,
                    OFFICE_FONT_SCALE_MAX_PERCENT,
                    True,
                ),
                "wz_row_height_mm": (
                    WZ_ROW_HEIGHT_MIN_MM,
                    WZ_ROW_HEIGHT_MAX_MM,
                    True,
                ),
            }
            try:
                for key, (minimum, maximum, integer_only) in numeric_limits.items():
                    value = parse_decimal(variables[key].get(), key)
                    if value < minimum or value > maximum:
                        raise ValueError(f"{key} musi mieścić się w zakresie {minimum}–{maximum}.")
                    if integer_only and value != value.to_integral_value():
                        raise ValueError(f"{key} musi być liczbą całkowitą.")
                    updated[key] = str(int(value) if integer_only else value)
                validity_days = updated["offer_validity_days"]
                if validity_days and (
                    not validity_days.isdigit()
                    or int(validity_days) < 1
                    or int(validity_days) > 3650
                ):
                    raise ValueError("Ważność oferty musi wynosić od 1 do 3650 dni albo być pusta.")
                for key in ("brand_primary", "brand_accent"):
                    if not re.fullmatch(r"#[0-9A-Fa-f]{6}", updated[key]):
                        raise ValueError("Kolory dokumentów muszą być zapisane jako #RRGGBB.")
                for key in THEME_PALETTE_SETTINGS:
                    if not re.fullmatch(r"#[0-9A-Fa-f]{6}", updated[key]):
                        raise ValueError("Kolory motywów muszą być zapisane jako #RRGGBB.")
                if updated["default_currency"] not in CURRENCIES:
                    raise ValueError("Wybierz prawidłową domyślną walutę.")
                updated["currency_rates"] = serialize_currency_rates(
                    parse_currency_rates(updated["currency_rates"])
                )
                scale_text = updated["ui_scale_percent"]
                if (
                    not scale_text.isdigit()
                    or not UI_SCALE_MIN_PERCENT <= int(scale_text) <= UI_SCALE_MAX_PERCENT
                ):
                    raise ValueError(
                        f"Skala interfejsu musi mieścić się w zakresie "
                        f"{UI_SCALE_MIN_PERCENT}–{UI_SCALE_MAX_PERCENT}%."
                    )
            except ValueError as error:
                messagebox.showerror("Ustawienia dokumentów", str(error), parent=dialog)
                return

            try:
                updated["materials_library"] = serialize_materials(material_records)
            except ValueError as error:
                messagebox.showerror("Biblioteka materiałów", str(error), parent=dialog)
                return
            updated["materials"] = "\n".join(
                material["name"] for material in material_records
            )
            database_directory_text = database_directory_var.get().strip()
            if not database_directory_text:
                messagebox.showerror(
                    "Lokalizacja danych",
                    "Wybierz folder dla bazy danych.",
                    parent=dialog,
                )
                return
            database_directory = Path(database_directory_text).expanduser().resolve()
            database_location_changed = (
                database_directory != self.storage.database_path.parent.resolve()
            )
            if database_location_changed and not messagebox.askyesno(
                "Przenieś bazę danych",
                "Baza i kopie zapasowe zostaną skopiowane do nowej lokalizacji. "
                "Dotychczasowe pliki pozostaną jako kopia bezpieczeństwa. "
                "Po zapisaniu ustawień aplikacja zostanie zamknięta; uruchom ją ponownie.\n\n"
                "Kontynuować?",
                parent=dialog,
            ):
                return
            try:
                Path(photo_directory).expanduser().mkdir(parents=True, exist_ok=True)
                database_directory.mkdir(parents=True, exist_ok=True)
                export_migrations = [
                    (
                        Path(self.settings[key]).expanduser(),
                        Path(updated[key]).expanduser(),
                    )
                    for key, _label in managed_directory_fields
                ]
                for source, destination in export_migrations:
                    copy_export_directory(source, destination)
                ensure_export_directories(updated)
            except (OSError, ValueError) as error:
                messagebox.showerror(
                    "Lokalizacja danych",
                    f"Nie udało się przygotować folderów docelowych:\n{error}",
                    parent=dialog,
                )
                return

            try:
                self.storage.save_settings(self.user_id, updated)
            except sqlite3.Error as error:
                messagebox.showerror("Błąd bazy danych", f"Nie udało się zapisać ustawień:\n{error}", parent=dialog)
                return
            if database_location_changed:
                try:
                    new_database_path = self.storage.relocate_database(database_directory)
                except (OSError, sqlite3.Error, ValueError) as error:
                    messagebox.showerror(
                        "Lokalizacja danych",
                        f"Ustawienia zapisano, ale nie udało się przenieść bazy:\n{error}",
                        parent=dialog,
                    )
                    self.settings = self.storage.get_settings(self.user_id)
                    return
            self.settings = self.storage.get_settings(self.user_id)
            if self.editing_estimate_id is None and not self.draft_items:
                self.quote_currency = self.settings.get("default_currency", "PLN")
                self._update_currency_labels()
            self.app.apply_ui_scale(self.settings.get("ui_scale_percent"))
            self.app.set_theme(
                self.settings,
                self.settings.get("dark_mode") == "1",
            )
            self.app._apply_widget_theme(
                dialog,
                self.settings.get("dark_mode") == "1",
            )
            refresh_palette_samples()
            palette_save_status.configure(text="Ustawienia zapisane i zastosowane.")
            self.item_vars["price_per_kg"].set(self.settings["price_per_kg"])
            self.item_vars["burning_rate_per_hour"].set(self.settings["burning_rate_per_hour"])
            self.item_vars["vat_percent"].set(self.settings["vat_percent"])
            self._refresh_material_choices()
            self._refresh_brand_badge()
            self._refresh_summary_estimate_from_settings()
            if database_location_changed:
                messagebox.showinfo(
                    "Lokalizacja danych",
                    f"Baza została przeniesiona do:\n{new_database_path}\n\n"
                    "Stara baza i kopie eksportów pozostały w poprzednich folderach "
                    "jako kopie bezpieczeństwa. Uruchom BlachCalc ponownie.",
                    parent=dialog,
                )
                self.app.destroy()
                return
        ttk.Button(
            navigation,
            text="Zapisz ustawienia",
            style="Primary.TButton",
            command=save,
        ).grid(row=0, column=0, sticky="w")
        ttk.Button(
            navigation,
            text="Zamknij",
            command=dialog.destroy,
        ).grid(row=0, column=1, sticky="w", padx=(8, 0))

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
            self._refresh_summary_estimate_from_settings()
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
        logo_path_str = self.settings.get("logo_path", "")
        logo_path = Path(logo_path_str) if logo_path_str else None
        if logo_path and logo_path.is_file():
            try:
                source_image = tk.PhotoImage(file=str(logo_path))
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
            except (tk.TclError, OSError) as error:
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
