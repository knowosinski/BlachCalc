import sqlite3
import tkinter as tk
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Any

from calculator import calculate_quote, parse_decimal
from dashboard_shared import (
    ACCENT,
    BORDER,
    BRAND_RED,
    INK,
    MUTED,
    NAVY,
    WHITE,
)
from offer_page import (
    CONTACT_FIELDS,
    LIST_SECTIONS,
    SETTING_KEY as OFFER_PAGE_SETTING,
    default_offer_page,
    parse_offer_page,
    serialize_offer_page,
)
from storage import (
    ADDRESS_FIELDS,
    format_postal_address,
    parse_polish_address,
    validate_postal_address,
)


class DashboardCustomerMixin:
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
        fields = (
            ("company_phone", "Telefon firmy"),
            ("company_email", "E-mail firmy"),
            ("company_tax_id", "NIP firmy"),
            ("company_regon", "REGON firmy"),
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
