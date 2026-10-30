import json
import os
import sqlite3
import tempfile
import tkinter as tk
from datetime import datetime
from io import BytesIO
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Any

from PIL import Image, ImageTk

from app_paths import dated_export_directory, ensure_file_extension
from quote_domain import item_geometry_parts
from dashboard_shared import (
    BACKGROUND,
    BORDER,
    DELIVERY_NOTE_DRAFT_SETTING,
    INK,
    MUTED,
    WHITE,
    WZ_EXPORT_DIRECTORY,
)
from exports import (
    WZ_ROW_HEIGHT_MAX_MM,
    WZ_ROW_HEIGHT_MIN_MM,
    export_delivery_note_pdf,
    export_delivery_note_xlsx,
    export_estimate_pdf,
    wz_row_height_mm,
)


class DashboardDocumentMixin:
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
        (
            self.wz_row_height_var,
            self.wz_row_height_label_var,
            self.wz_row_height_scale,
        ) = self._build_size_slider(
            self.pdf_preview_tab,
            "Wysokość wierszy tabeli WZ",
            WZ_ROW_HEIGHT_MIN_MM,
            WZ_ROW_HEIGHT_MAX_MM,
            int(wz_row_height_mm(self.settings)),
            self._on_wz_row_height_change,
            self._save_wz_row_height,
        ).values
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
        geometry = ", ".join(item_geometry_parts(item))
        if geometry:
            description2 = f"{description2} · {geometry}" if description2 else geometry
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
        self._pdf_preview_data = data
        self._pdf_preview_save_action = lambda: self._save_delivery_note_pdf(data)
        self._pdf_preview_print_action = lambda: self._print_pdf_bytes(
            self._pdf_preview_bytes,
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
        export_directory = dated_export_directory(WZ_EXPORT_DIRECTORY)
        try:
            export_directory.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            messagebox.showerror(
                "Folder dokumentów WZ",
                f"Nie można przygotować domyślnego folderu zapisu:\n{export_directory}\n\n{error}",
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
            initialdir=str(export_directory),
            initialfile=f"{safe_filename or 'WZ'}.pdf",
            defaultextension=".pdf",
            confirmoverwrite=True,
            filetypes=[("Dokument PDF", "*.pdf")],
        )
        if not filename:
            return
        filename = ensure_file_extension(filename, "pdf")
        try:
            export_delivery_note_pdf(data, self.settings, filename)
        except (OSError, ValueError, ImportError, RuntimeError) as error:
            messagebox.showerror(
                "Zapisywanie dokumentu WZ",
                f"Nie udało się zapisać pliku PDF:\n{filename}\n\n{error}",
                parent=parent,
            )
            return
        excel_note = self._save_excel_copy(
            lambda path: export_delivery_note_xlsx(data, path),
            filename,
            parent,
        )
        messagebox.showinfo(
            "Wydanie zewnętrzne",
            f"Zapisano dokument WZ:\n{filename}{excel_note}",
            parent=parent,
        )

    def _on_wz_row_height_change(self, _value: str | None = None) -> None:
        height = int(round(float(self.wz_row_height_scale.get())))
        self.wz_row_height_label_var.set(f"{height} mm")
        self.settings["wz_row_height_mm"] = str(height)
        data = getattr(self, "_pdf_preview_data", None)
        if data is None or self._pdf_preview_bytes is None:
            return
        try:
            output = BytesIO()
            export_delivery_note_pdf(data, self.settings, output)
        except (OSError, ValueError, ImportError, RuntimeError):
            return
        self._pdf_preview_bytes = output.getvalue()
        if self._pdf_preview_resize_after_id is not None:
            self.after_cancel(self._pdf_preview_resize_after_id)
        self._pdf_preview_resize_after_id = self.after_idle(self._render_document_preview)

    def _save_wz_row_height(self, _event: tk.Event | None = None) -> None:
        height = int(round(float(self.wz_row_height_scale.get())))
        self.storage.save_settings(self.user_id, {"wz_row_height_mm": str(height)})

    def _on_photo_width_change(self, _value: str | None = None) -> None:
        width = int(round(float(self.photo_width_scale.get())))
        self.photo_width_label_var.set(f"{width} mm")
        self.settings["photo_width_mm"] = str(width)
        if self.summary_estimate is None:
            return
        if self._preview_resize_after_id is not None:
            self.after_cancel(self._preview_resize_after_id)
        # Bez opóźnienia: odświeżenie przy pierwszej wolnej chwili pętli zdarzeń.
        self._preview_resize_after_id = self.after_idle(self._render_scheduled_estimate_preview)

    def _save_photo_width(self, _event: tk.Event | None = None) -> None:
        width = int(round(float(self.photo_width_scale.get())))
        self.storage.save_settings(self.user_id, {"photo_width_mm": str(width)})

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
