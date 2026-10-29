import os
import sqlite3
import tkinter as tk
from datetime import datetime
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Any

from PIL import Image, ImageTk, UnidentifiedImageError

from calculator import calculate_quote, parse_decimal, parse_duration
from app_paths import dated_export_directory, ensure_file_extension, excel_copy_path
from dashboard_shared import (
    BORDER,
    FieldValidationError,
    EXCEL_EXPORT_DIRECTORY,
    INK,
    MAX_PREVIEW_IMAGE_BYTES,
    MUTED,
    OFFER_EXPORT_DIRECTORY,
    WHITE,
)
from exports import export_estimate_csv, export_estimate_pdf, export_estimate_xlsx
from quote_domain import (
    CALCULATION_MODE_LABELS,
    DEFAULT_OPERATION,
    MAX_DIMENSIONS_LENGTH,
    OPERATIONS,
    apply_item_batch_share,
    calculate_item_line_amounts,
    format_pln,
    is_batch_mode,
    item_geometry_parts,
    line_totals,
    parse_hole_diameters,
    is_pending_full_batch,
    split_full_batch,
)


class DashboardQuoteMixin:
    def _duration_label(self, seconds: int) -> str:
        hours, remainder = divmod(seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours:02}:{minutes:02}:{seconds:02}"

    def _update_holes_field(self) -> None:
        if self.item_vars["has_holes"].get() == "1":
            self.hole_diameters_cell.grid(row=7, column=0, columnspan=2, sticky="ew", padx=5, pady=5)
        else:
            self.hole_diameters_cell.grid_remove()

    def _update_calculation_form(self) -> None:
        mode = self.calculation_mode_var.get()
        whole_order = mode == "whole_order"
        full_batch = mode == "full_batch"
        self._update_holes_field()
        button_text = (
            "Zapisz zmiany pozycji"
            if self.editing_draft_index is not None
            else "＋  Dodaj partię" if whole_order else "＋  Dodaj do pełnej partii" if full_batch else "＋  Dodaj pozycję"
        )
        self.weight_entry.configure(state="disabled" if full_batch else "normal")
        for time_entry in self.time_entries:
            time_entry.configure(state="disabled" if full_batch else "normal")
        if full_batch:
            self.quantity_label.configure(text="Ilość gotowych (szt.) *")
            self.weight_label.configure(text="Masa partii (podasz na końcu)")
            self.time_label.configure(text="Czas palenia (podasz na końcu)")
            self.calculation_mode_description.set(
                "Dodawaj dowolną liczbę elementów bez masy i czasu. Masę oraz czas palenia całej partii wpiszesz raz, po kliknięciu „Zatwierdź wycenę”."
            )
        elif whole_order:
            self.quantity_label.configure(text="Ilość gotowych (szt.) *")
            self.weight_label.configure(text="Masa całej partii (kg) *")
            self.time_label.configure(text="Czas palenia partii *")
            self.calculation_mode_description.set(
                "Wpisz masę i czas palenia partii tego elementu oraz liczbę gotowych sztuk. Ilość nie zmienia kosztu."
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

    def _operation_key(self) -> str:
        labels = {label: key for key, label in OPERATIONS.items()}
        return labels.get(self.operation_var.get(), DEFAULT_OPERATION)

    def _build_item_from_form(self) -> dict[str, Any]:
        values = {key: variable.get().strip() for key, variable in self.item_vars.items()}
        if not values["element_name"]:
            raise FieldValidationError("Podaj nazwę elementu.", "element_name")
        calculation_mode = self.calculation_mode_var.get()
        full_batch = calculation_mode == "full_batch"
        dimensions = values["dimensions"]
        if len(dimensions) > MAX_DIMENSIONS_LENGTH:
            raise FieldValidationError("Wymiary mogą mieć maksymalnie 120 znaków.", "dimensions")
        hole_diameters = ""
        if values["has_holes"] == "1":
            try:
                hole_diameters = parse_hole_diameters(values["hole_diameters"])
            except ValueError as error:
                raise FieldValidationError(str(error), "hole_diameters") from error
            if not hole_diameters:
                raise FieldValidationError("Podaj średnicę (fi) otworów albo odznacz opcję otworów.", "hole_diameters")
        try:
            quantity = int(values["quantity"])
        except ValueError as error:
            raise FieldValidationError("Ilość musi być dodatnią liczbą całkowitą.", "quantity") from error
        if quantity < 1 or quantity > 1_000_000:
            raise FieldValidationError("Ilość musi mieścić się w zakresie od 1 do 1 000 000 sztuk.", "quantity")
        weight_label = "Masa partii" if calculation_mode == "whole_order" else "Masa jednej sztuki"

        def parse_field(field: str, label: str) -> Decimal:
            try:
                return parse_decimal(values[field], label)
            except ValueError as error:
                raise FieldValidationError(str(error), field) from error

        price = parse_field("price_per_kg", "Cena materiału za kg")
        weight = Decimal("0") if full_batch else parse_field("used_weight_kg", weight_label)
        rate = parse_field("burning_rate_per_hour", "Stawka palenia")
        vat = parse_field("vat_percent", "VAT")
        try:
            duration_seconds = 0 if full_batch else parse_duration(values["hours"], values["minutes"], values["seconds"])
        except ValueError as error:
            raise FieldValidationError(str(error), "hours") from error
        if calculation_mode == "whole_order" and weight <= 0:
            raise FieldValidationError("Masa partii musi być większa od zera.", "used_weight_kg")
        try:
            quote = calculate_quote(price, weight, duration_seconds, rate, vat, allow_zero_weight=full_batch)
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
            "dimensions": dimensions,
            "hole_diameters": hole_diameters,
            "calculation_mode": calculation_mode,
            "operation": self._operation_key(),
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
        self.operation_var.set(OPERATIONS[DEFAULT_OPERATION])
        self._update_calculation_form()
        for key in ("element_name", "material", "thickness_mm", "used_weight_kg", "dimensions", "hole_diameters"):
            self.item_vars[key].set("")
        self.item_vars["has_holes"].set("0")
        self._update_holes_field()
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
            pending = is_pending_full_batch(item)
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
                    "do wyceny" if pending else format_pln(gross),
                ),
            )
        if self.draft_items:
            scope_summary = f"{total_quantity} szt." if total_quantity else ""
            position_summary = f"{len(self.draft_items)} poz."
            if scope_summary:
                position_summary += f"  ·  {scope_summary}"
            if any(is_pending_full_batch(item) for item in self.draft_items):
                position_summary += "  ·  pełna partia: masa i czas na końcu"
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
        self.operation_var.set(OPERATIONS.get(item.get("operation", DEFAULT_OPERATION), OPERATIONS[DEFAULT_OPERATION]))
        self._update_calculation_form()
        self.item_vars["element_name"].set(item["element_name"])
        self.item_vars["material"].set(item["material"])
        self.item_vars["thickness_mm"].set(item["thickness_mm"])
        self.item_vars["dimensions"].set(item.get("dimensions", ""))
        self.item_vars["hole_diameters"].set(item.get("hole_diameters", ""))
        self.item_vars["has_holes"].set("1" if item.get("hole_diameters") else "0")
        self._update_holes_field()
        self.item_vars["quantity"].set(str(item["quantity"]))
        self.item_vars["price_per_kg"].set(item["price_per_kg"])
        self.item_vars["used_weight_kg"].set("" if item.get("calculation_mode") == "full_batch" else item["used_weight_kg"])
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
        item = self.draft_items[item_index]
        image_data = item.get("preview_image")
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
        window.title(f"Podgląd — {item['element_name']}")
        window.transient(self)
        window.configure(bg=WHITE)
        window.resizable(True, True)
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        window.minsize(
            min(700, screen_width - 40),
            min(360, screen_height - 80),
        )
        window.geometry(
            f"{min(1040, screen_width - 40)}x{min(640, screen_height - 80)}"
        )
        content = tk.Frame(window, bg=WHITE, padx=14, pady=14)
        content.pack(fill="both", expand=True)
        content.grid_columnconfigure(0, weight=3, uniform="preview_columns")
        content.grid_columnconfigure(1, weight=2, uniform="preview_columns")
        content.grid_rowconfigure(0, weight=1)
        image_canvas = tk.Canvas(content, bg="#E7EDF4", highlightthickness=0)
        image_canvas.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        details = tk.Frame(
            content,
            bg=WHITE,
            highlightthickness=1,
            highlightbackground=BORDER,
            padx=16,
            pady=14,
        )
        details.grid(row=0, column=1, sticky="nsew")
        details.grid_columnconfigure(0, weight=1)
        tk.Label(
            details,
            text="Parametry elementu",
            bg=WHITE,
            fg=INK,
            font=("Segoe UI", 13, "bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="ew", pady=(0, 10))

        hours, remainder = divmod(int(item["duration_seconds"]), 3600)
        minutes, seconds = divmod(remainder, 60)
        whole_order = is_batch_mode(item.get("calculation_mode", "per_piece"))
        parameters = (
            ("Nazwa elementu", item.get("element_name", "")),
            ("Operacja", OPERATIONS.get(item.get("operation", DEFAULT_OPERATION), "")),
            ("Materiał", item.get("material", "")),
            ("Grubość", f"{item['thickness_mm']} mm" if item.get("thickness_mm") else ""),
            ("Wymiary", f"{item['dimensions']} mm" if item.get("dimensions") else ""),
            ("Otwory (fi)", item.get("hole_diameters", "")),
            ("Metoda kalkulacji", CALCULATION_MODE_LABELS.get(item.get("calculation_mode", "per_piece"), "Sztuka")),
            ("Ilość", f"{item['quantity']} szt."),
            (
                "Masa partii" if whole_order else "Masa jednej sztuki",
                f"{item['used_weight_kg']} kg",
            ),
            ("Cena materiału", f"{format_pln(item['price_per_kg'])}/kg"),
            (
                "Czas palenia partii" if whole_order else "Czas palenia jednej sztuki",
                f"{hours:02}:{minutes:02}:{seconds:02}",
            ),
            ("Stawka palenia", f"{format_pln(item['burning_rate_per_hour'])}/godz."),
            ("VAT", f"{item['vat_percent']}%"),
        )
        for row, (label, value) in enumerate(parameters, start=1):
            tk.Label(
                details,
                text=label,
                bg=WHITE,
                fg=MUTED,
                font=("Segoe UI", 8, "bold"),
                anchor="w",
            ).grid(row=row * 2 - 1, column=0, sticky="ew", pady=(4, 0))
            tk.Label(
                details,
                text=str(value).strip() or "—",
                bg=WHITE,
                fg=INK,
                font=("Segoe UI", 10),
                anchor="w",
                justify="left",
                wraplength=360,
            ).grid(row=row * 2, column=0, sticky="ew")

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
        ttk.Button(window, text="Zamknij", command=window.destroy).pack(pady=(0, 14))

    def _resolve_full_batch_weights(self) -> bool:
        indexes = [
            index
            for index, item in enumerate(self.draft_items)
            if item.get("calculation_mode") == "full_batch"
        ]
        if not indexes:
            return True
        selected = [self.draft_items[index] for index in indexes]
        known = [item for item in selected if not is_pending_full_batch(item)]
        initial_weight = sum((Decimal(str(item["used_weight_kg"])) for item in known), Decimal("0"))
        initial_seconds = sum(int(item["duration_seconds"]) for item in known)
        result = self._ask_full_batch_totals(selected, initial_weight, initial_seconds)
        if result is None:
            return False
        shares = split_full_batch(selected, *result)
        for index, item, (weight, seconds) in zip(indexes, selected, shares):
            self.draft_items[index] = apply_item_batch_share(item, weight, seconds)
        self._refresh_draft()
        return True

    def _ask_full_batch_totals(
        self,
        selected_items: list[dict[str, Any]],
        initial_weight: Decimal,
        initial_seconds: int,
    ) -> tuple[Decimal, int] | None:
        dialog = tk.Toplevel(self)
        dialog.title("Pełna partia — masa i czas")
        dialog.configure(bg=WHITE)
        dialog.transient(self)
        dialog.resizable(False, False)
        body = tk.Frame(dialog, bg=WHITE, padx=20, pady=16)
        body.pack(fill="both", expand=True)
        tk.Label(
            body,
            text=f"Pełna partia: {len(selected_items)} poz.",
            bg=WHITE,
            fg=INK,
            font=("Segoe UI", 12, "bold"),
        ).pack(anchor="w")
        tk.Label(
            body,
            text="Podaj łączną masę i czas palenia całej partii.\nKoszt zostanie rozdzielony na pozycje proporcjonalnie do ilości sztuk.",
            bg=WHITE,
            fg=MUTED,
            justify="left",
        ).pack(anchor="w", pady=(4, 12))
        weight_var = tk.StringVar(value=format(initial_weight.normalize(), "f") if initial_weight > 0 else "")
        hours, remainder = divmod(initial_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        time_vars = [tk.StringVar(value=str(value)) for value in (hours, minutes, seconds)]
        tk.Label(body, text="Masa całej partii (kg) *", bg=WHITE, fg=MUTED, font=("Segoe UI", 8, "bold")).pack(anchor="w")
        weight_entry = ttk.Entry(body, textvariable=weight_var, width=18)
        weight_entry.pack(anchor="w", pady=(2, 10))
        tk.Label(body, text="Czas palenia partii (godz. : min. : sek.) *", bg=WHITE, fg=MUTED, font=("Segoe UI", 8, "bold")).pack(anchor="w")
        time_row = tk.Frame(body, bg=WHITE)
        time_row.pack(anchor="w", pady=(2, 4))
        for position, (variable, width) in enumerate(zip(time_vars, (4, 3, 3))):
            ttk.Entry(time_row, textvariable=variable, width=width, justify="center").pack(side="left")
            if position < 2:
                tk.Label(time_row, text=":", bg=WHITE, fg=MUTED).pack(side="left", padx=4)
        error_var = tk.StringVar()
        tk.Label(body, textvariable=error_var, bg=WHITE, fg="#B42318", wraplength=320, justify="left").pack(anchor="w", pady=(6, 0))
        result: list[tuple[Decimal, int]] = []

        def confirm(_event: tk.Event | None = None) -> None:
            try:
                weight = parse_decimal(weight_var.get(), "Masa pełnej partii")
                if weight <= 0:
                    raise ValueError("Masa pełnej partii musi być większa od zera.")
                total_seconds = parse_duration(*(variable.get() for variable in time_vars))
                if total_seconds <= 0:
                    raise ValueError("Czas palenia pełnej partii musi być większy od zera.")
                shares = split_full_batch(selected_items, weight, total_seconds)
                if any(share_weight <= 0 for share_weight, _seconds in shares):
                    raise ValueError("Masa jest zbyt mała, aby rozdzielić ją na wszystkie pozycje partii.")
            except ValueError as error:
                error_var.set(str(error))
                return
            result.append((weight, total_seconds))
            dialog.destroy()

        actions = tk.Frame(body, bg=WHITE)
        actions.pack(fill="x", pady=(12, 0))
        ttk.Button(actions, text="Zatwierdź", style="Primary.TButton", command=confirm).pack(side="right")
        ttk.Button(actions, text="Anuluj", command=dialog.destroy).pack(side="right", padx=(0, 8))
        dialog.bind("<Return>", confirm)
        dialog.bind("<Escape>", lambda _event: dialog.destroy())
        dialog.update_idletasks()
        x = self.winfo_rootx() + max(0, (self.winfo_width() - dialog.winfo_width()) // 2)
        y = self.winfo_rooty() + max(0, (self.winfo_height() - dialog.winfo_height()) // 3)
        dialog.geometry(f"+{x}+{y}")
        dialog.grab_set()
        weight_entry.focus_set()
        self.wait_window(dialog)
        return result[0] if result else None

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
        if not self._resolve_full_batch_weights():
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
                "partia"
                if item.get("calculation_mode", "per_piece") == "whole_order"
                else "pełna partia"
                if item.get("calculation_mode") == "full_batch"
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
        export_directory = dated_export_directory(OFFER_EXPORT_DIRECTORY)
        try:
            export_directory.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            messagebox.showerror(
                "Folder eksportu",
                f"Nie można przygotować domyślnego folderu ofert:\n{export_directory}\n\n{error}",
                parent=self,
            )
            return ""
        filename = filedialog.asksaveasfilename(
            parent=self,
            title=f"Zapisz eksport {extension.upper()}",
            initialdir=str(export_directory),
            initialfile=default_name,
            defaultextension=f".{extension}",
            confirmoverwrite=True,
            filetypes=[(f"Plik {extension.upper()}", f"*.{extension}")],
        )
        return ensure_file_extension(filename, extension)

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

    def _save_excel_copy(self, write: Any, pdf_filename: str, parent: tk.Misc) -> str:
        excel_path = excel_copy_path(EXCEL_EXPORT_DIRECTORY, pdf_filename)
        try:
            excel_path.parent.mkdir(parents=True, exist_ok=True)
            write(excel_path)
        except (OSError, ValueError, ImportError) as error:
            messagebox.showwarning(
                "Zapis Excel",
                f"PDF został zapisany, ale nie udało się zapisać kopii Excel:\n{excel_path}\n\n{error}",
                parent=parent,
            )
            return ""
        return f"\n\nExcel:\n{excel_path}"

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
        excel_note = self._save_excel_copy(
            lambda path: export_estimate_xlsx(estimate, path, self.settings),
            filename,
            self,
        )
        if not open_after_export:
            messagebox.showinfo("Eksport PDF", f"Zapisano plik:\n{filename}{excel_note}", parent=self)
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
