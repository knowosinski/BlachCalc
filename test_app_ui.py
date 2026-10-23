import tempfile
import tkinter as tk
from tkinter import ttk
import unittest
from pathlib import Path
from unittest.mock import patch

from blachcalc import BlachCalcApp, DashboardView
from storage import Storage


class AppUiTests(unittest.TestCase):
    def test_offer_page_editor_saves_edited_text(self) -> None:
        self.view.open_offer_page_editor(self.app)
        self.app.update()
        dialog = next(w for w in self.app.winfo_children() if isinstance(w, tk.Toplevel))

        def walk(widget):
            for child in widget.winfo_children():
                yield child
                yield from walk(child)

        boxes = [w for w in walk(dialog) if isinstance(w, tk.Text)]
        self.assertEqual(len(boxes), 3)
        boxes[0].delete("1.0", "end")
        boxes[0].insert("1.0", "Jedyny warunek\n\nDrugi")

        def find_button(text):
            return next(
                widget
                for widget in walk(dialog)
                if isinstance(widget, ttk.Button) and widget.cget("text") == text
            )

        find_button("+  Dodaj rubrykę").invoke()
        self.app.update()
        boxes = [widget for widget in walk(dialog) if isinstance(widget, tk.Text)]
        custom_box = next(widget for widget in boxes if widget.get("1.0", "end-1c") == "")
        custom_box.insert("1.0", "Treść dodatkowej rubryki")
        custom_title = next(
            widget for widget in custom_box.master.winfo_children()
            if isinstance(widget, ttk.Entry)
        )
        custom_title.insert(0, "Zakres usługi")
        find_button("+  Dodaj rubrykę").invoke()
        self.app.update()
        remove_custom_buttons = [
            widget for widget in walk(dialog)
            if isinstance(widget, ttk.Button) and widget.cget("text") == "Usuń rubrykę"
        ]
        self.assertEqual(len(remove_custom_buttons), 2)
        remove_custom_buttons[-1].invoke()

        find_button("+  Dodaj osobę kontaktową").invoke()
        self.app.update()
        remove_buttons = [
            widget for widget in walk(dialog)
            if isinstance(widget, ttk.Button) and widget.cget("text") == "Usuń"
        ]
        self.assertEqual(len(remove_buttons), 2)
        remove_buttons[0].invoke()
        self.app.update()
        find_button("+  Dodaj osobę kontaktową").invoke()
        self.app.update()
        remove_buttons = [
            widget for widget in walk(dialog)
            if isinstance(widget, ttk.Button) and widget.cget("text") == "Usuń"
        ]
        contact_entries = [
            widget for widget in remove_buttons[0].master.winfo_children()
            if isinstance(widget, ttk.Entry)
        ]
        for entry, value in zip(contact_entries, ("Anna Nowak", "123 456 789", "anna@example.com")):
            entry.insert(0, value)

        save = next(w for w in walk(dialog) if isinstance(w, ttk.Button) and w.cget("text") == "Zapisz")
        save.invoke()
        self.app.update()
        from offer_page import parse_offer_page

        page = parse_offer_page(self.view.settings["offer_page2"])
        self.assertEqual(page["terms"]["items"], ["Jedyny warunek", "Drugi"])
        self.assertEqual(page["claims"]["title"], "Odbiór i reklamacje towaru")
        self.assertEqual(page["custom_sections"], [{
            "title": "Zakres usługi",
            "text": "Treść dodatkowej rubryki",
        }])
        self.assertEqual(page["contacts"], [{
            "person": "Anna Nowak",
            "phone": "123 456 789",
            "email": "anna@example.com",
        }])

    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        storage = Storage(Path(self.temporary_directory.name) / "ui.sqlite3")
        try:
            self.app = BlachCalcApp(storage)
        except tk.TclError as error:
            self.temporary_directory.cleanup()
            self.skipTest(f"Brak środowiska graficznego: {error}")
        self.app.geometry("1000x680+20+20")
        self.app.update()
        self.view: DashboardView = next(
            child for child in self.app.winfo_children() if isinstance(child, DashboardView)
        )
        self.app.update()

    def tearDown(self) -> None:
        self.app.destroy()
        self.temporary_directory.cleanup()

    def _wheel(self, widget: tk.Widget, delta: int = -120, state: int = 0) -> None:
        # winfo_containing zależy od okien innych procesów nad testowym oknem, więc podstawiamy widżet pod kursorem.
        with patch.object(self.view, "winfo_containing", return_value=widget):
            widget.event_generate("<MouseWheel>", x=6, y=6, delta=delta, state=state)
            self.app.update()

    def _add_items(self, count: int) -> None:
        for index in range(count):
            self.view.item_vars["element_name"].set(f"Element {index}")
            self.view.item_vars["used_weight_kg"].set("1")
            self.view.item_vars["seconds"].set("30")
            self.view.add_item()
        self.app.update()

    def test_wheel_scrolls_quote_form_from_anywhere_over_its_content(self) -> None:
        canvas = self.view.quote_canvas
        self.assertLess(canvas.yview()[1], 1.0)
        for state in (0, 0x0008):
            canvas.yview_moveto(0)
            self.app.update()
            self._wheel(self.view.customer_cell, state=state)
            self.assertGreater(canvas.yview()[0], 0.0, f"state={state:#x}")

    def test_wheel_scrolls_order_items_list_over_card_and_list(self) -> None:
        self._add_items(30)
        tree = self.view.draft_tree
        self.assertLess(tree.yview()[1], 1.0)
        for target in (tree, self.view.draft_card):
            tree.yview_moveto(0)
            self.app.update()
            self._wheel(target)
            self.assertGreater(tree.yview()[0], 0.0, str(target))

    def test_enter_moves_through_item_fields_in_visual_order(self) -> None:
        view = self.view
        expected = [
            view.item_field_cells["element_name"].winfo_children()[1],
            view.material_combo,
            view.item_field_cells["thickness_mm"].winfo_children()[1],
            view.quantity_entry,
            view.weight_entry,
        ]
        for current, following in zip(expected, expected[1:]):
            current.focus_force()
            self.app.update()
            current.event_generate("<Return>")
            self.app.update()
            self.assertIs(self.app.focus_get(), following)

    def test_edited_draft_item_can_be_added_as_a_new_position_or_updated(self) -> None:
        self.view.item_vars["element_name"].set("Wspornik")
        self.view.item_vars["quantity"].set("5")
        self.view.item_vars["used_weight_kg"].set("1")
        self.view.add_item()
        self.assertEqual(len(self.view.draft_items), 1)

        self.view.draft_tree.selection_set("0")
        self.view.edit_draft_item()
        self.assertEqual(self.view.add_edited_item_button.winfo_manager(), "pack")
        self.view.item_vars["quantity"].set("6")
        self.view.add_edited_item_button.invoke()

        self.assertEqual(len(self.view.draft_items), 2)
        self.assertEqual(self.view.draft_items[0]["quantity"], 5)
        self.assertEqual(self.view.draft_items[1]["quantity"], 6)
        self.assertIsNone(self.view.editing_draft_index)
        self.assertEqual(self.view.add_edited_item_button.winfo_manager(), "")

        self.view.draft_tree.selection_set("0")
        self.view.edit_draft_item()
        self.view.item_vars["quantity"].set("7")
        self.view.add_item_button.invoke()

        self.assertEqual(len(self.view.draft_items), 2)
        self.assertEqual(self.view.draft_items[0]["quantity"], 7)
        self.assertEqual(self.view.draft_items[1]["quantity"], 6)

    def test_saved_estimate_opens_editable_delivery_note_without_changing_offer(self) -> None:
        self.view.item_vars["element_name"].set("Detal 180x70")
        self.view.item_vars["material"].set("S355")
        self.view.item_vars["thickness_mm"].set("8")
        self.view.item_vars["quantity"].set("5")
        self.view.item_vars["used_weight_kg"].set("1")
        self.view.add_item()
        self.view.customer_var.set("KADAM")
        self.view.order_number_var.set("012/010/2026")
        self.view.save_estimate()

        self.view._show_page("history")
        self.view.history_tree.selection_set(str(self.view.editing_estimate_id))
        self.view.navigation_buttons["delivery_note"].invoke()
        self.app.update()

        self.assertEqual(self.view.current_page, "delivery_note")
        self.assertEqual(self.view.navigation_buttons["delivery_note"].cget("text"), "▣   Generuj WZ")
        def walk(widget):
            for child in widget.winfo_children():
                yield child
                yield from walk(child)

        delivery_entries = [
            widget for widget in walk(self.view.delivery_note_form) if isinstance(widget, ttk.Entry)
        ]
        for field in ("document_number", "order_number"):
            entry = next(
                widget
                for widget in delivery_entries
                if widget.cget("textvariable") == self.view.delivery_note_variables[field]._name
            )
            self.assertEqual(str(entry.cget("state")), "normal")
        self.assertEqual(self.view.delivery_note_variables["document_number"].get(), "WZ-012/010/2026")
        self.assertEqual(self.view.delivery_note_variables["delivery_address"].get(), "odbiór własny")
        self.assertEqual(len(self.view.delivery_note_rows), 1)
        row = self.view.delivery_note_rows[0]
        self.assertEqual(row["product"].get(), "Element cięty")
        self.assertEqual(row["description"].get(), "Detal 180x70")
        self.assertEqual(row["description2"].get(), "S355 · 8 mm")
        self.assertEqual(row["quantity"].get(), "5")
        row["quantity"].set("6")
        self.view._add_delivery_note_row({
            "product": "Element cięty",
            "description": "Element dodatkowy",
            "description2": "S235",
            "quantity": "2",
            "unit": "szt",
            "notes": "",
        })
        self.assertEqual(len(self.view.delivery_note_rows), 2)
        self.assertEqual(self.view.draft_items[0]["quantity"], 5)
        self.assertEqual(self.view._delivery_note_data()["items"][0]["quantity"], "6")
        self.assertEqual(self.view._delivery_note_data()["items"][1]["description"], "Element dodatkowy")
        self.assertEqual(
            self.view.storage.get_estimate(self.view.user_id, self.view.editing_estimate_id)["items"][0]["quantity"],
            5,
        )

        self.view._show_page("quote")
        self.view.draft_tree.selection_set("0")
        self.view.edit_draft_item()
        self.view.item_vars["quantity"].set("7")
        self.view.add_item()
        self.view.save_estimate()
        self.assertIsNone(self.view.delivery_note_estimate_id)
        self.view._open_delivery_note()
        self.assertEqual(len(self.view.delivery_note_rows), 1)
        self.assertEqual(self.view.delivery_note_rows[0]["quantity"].get(), "7")

    def test_navigation_opens_manual_wz_without_selected_or_saved_estimate(self) -> None:
        self.view._show_page("history")
        self.assertFalse(self.view.history_tree.selection())

        with patch("blachcalc.messagebox.showinfo") as showinfo:
            self.view.navigation_buttons["delivery_note"].invoke()

        self.assertEqual(self.view.current_page, "delivery_note")
        self.assertTrue(self.view.delivery_note_initialized)
        self.assertIsNone(self.view.delivery_note_estimate_id)
        self.assertFalse(showinfo.called)
        self.assertEqual(self.view.delivery_note_variables["customer_name"].get(), "")
        self.assertEqual(self.view.delivery_note_variables["order_number"].get(), "")
        self.assertEqual(self.view.delivery_note_variables["document_number"].get(), "")
        self.assertEqual(len(self.view.delivery_note_rows), 1)
        self.assertEqual(self.view.delivery_note_rows[0]["product"].get(), "")
        self.assertEqual(self.view.delivery_note_return_page, "history")

        self.view.delivery_note_variables["customer_name"].set("Nowy klient")
        self.view.delivery_note_variables["order_number"].set("RĘCZNE-01")
        self.view.delivery_note_variables["document_number"].set("WZ/01/2026")
        self.view.delivery_note_rows[0]["product"].set("Usługa CNC")
        self.view.delivery_note_rows[0]["description"].set("Element spoza wyceny")
        self.assertEqual(self.view._delivery_note_data()["document_number"], "WZ/01/2026")
        self.assertEqual(self.view._delivery_note_data()["items"][0]["description"], "Element spoza wyceny")
        from io import BytesIO

        import pymupdf

        preview: dict[str, bytes] = {}
        with patch.object(
            self.view,
            "_show_delivery_note_preview",
            side_effect=lambda _data, pdf_data: preview.setdefault("pdf", pdf_data),
        ):
            self.view._preview_delivery_note()
        document = pymupdf.open(stream=BytesIO(preview["pdf"]), filetype="pdf")
        self.assertIn("Element spoza wyceny", document[0].get_text())
        document.close()

    def test_navigation_can_start_wz_from_unsaved_quote_data(self) -> None:
        self.view.item_vars["element_name"].set("Detal z bieżącego formularza")
        self.view.item_vars["material"].set("S235")
        self.view.item_vars["thickness_mm"].set("4")
        self.view.item_vars["quantity"].set("3")
        self.view.item_vars["used_weight_kg"].set("1")
        self.view.add_item()
        self.view.customer_var.set("Klient bez zapisanej oferty")
        self.view.order_number_var.set("ROB-12")

        self.view.navigation_buttons["delivery_note"].invoke()

        self.assertEqual(self.view.current_page, "delivery_note")
        self.assertEqual(self.view.delivery_note_variables["customer_name"].get(), "Klient bez zapisanej oferty")
        self.assertEqual(self.view.delivery_note_variables["order_number"].get(), "ROB-12")
        self.assertEqual(self.view.delivery_note_variables["document_number"].get(), "WZ-ROB-12")
        self.assertEqual(len(self.view.delivery_note_rows), 1)
        self.assertEqual(
            self.view.delivery_note_rows[0]["description"].get(),
            "Detal z bieżącego formularza",
        )
        self.assertEqual(self.view.delivery_note_return_page, "quote")

    def test_delivery_note_labels_remain_centered_over_responsive_inputs(self) -> None:
        self.view.navigation_buttons["delivery_note"].invoke()
        self.app.update_idletasks()
        self.app.update()

        product_widths = []
        for width in (800, 1000, 1200):
            self.app.geometry(f"{width}x900+20+20")
            self.app.update_idletasks()
            self.app.update()
            row = self.view.delivery_note_rows[0]["frame"]
            product_widths.append(row.winfo_children()[0].winfo_width())
            for key, label, entry in zip(
                ("product", "description", "description2", "quantity", "unit", "notes"),
                self.view.delivery_note_header_labels,
                row.winfo_children()[:6],
            ):
                label_center = label.winfo_rootx() + label.winfo_width() / 2
                entry_center = entry.winfo_rootx() + entry.winfo_width() / 2
                with self.subTest(window_width=width, column=key):
                    self.assertLessEqual(abs(label_center - entry_center), 1)
        self.assertLess(product_widths[0], product_widths[-1])

    def test_delivery_note_preview_precedes_save_to_dedicated_folder(self) -> None:
        from io import BytesIO

        import pymupdf

        self.view.delivery_note_variables["document_number"].set("WZ-TEST")
        self.view.delivery_note_variables["date"].set("23.10.2026")
        self.view.delivery_note_variables["customer_name"].set("Klient")
        self.view.delivery_note_variables["order_number"].set("TEST")
        self.view.delivery_note_variables["delivery_address"].set("odbiór własny")
        self.view._add_delivery_note_row({
            "product": "Element cięty",
            "description": "Detal testowy",
            "description2": "S355 · 8 mm",
            "quantity": "2",
            "unit": "szt",
            "notes": "",
        })
        preview_data: dict[str, object] = {}

        def capture_preview(data, pdf_data: bytes) -> None:
            preview_data["data"] = data
            preview_data["pdf_data"] = pdf_data

        with patch.object(self.view, "_show_delivery_note_preview", side_effect=capture_preview):
            self.view._preview_delivery_note()

        self.assertIn("data", preview_data)
        generated_pdf = pymupdf.open(
            stream=BytesIO(preview_data["pdf_data"]),
            filetype="pdf",
        )
        self.assertIn("Detal testowy", generated_pdf[0].get_text())
        generated_pdf.close()
        self.view._show_delivery_note_preview(
            preview_data["data"],
            preview_data["pdf_data"],
        )
        self.app.update()
        self.assertEqual(self.view.current_page, "pdf_preview")
        self.assertTrue(self.view._pdf_preview_images)
        self.view.pdf_preview_back_button.invoke()
        self.app.update()
        self.assertEqual(self.view.current_page, "delivery_note")

        with tempfile.TemporaryDirectory() as directory:
            wz_directory = Path(directory) / "OFERTY CENOWE BLACHCALC" / "WZ"
            target = wz_directory / "WZ-TEST_Klient.pdf"
            with (
                patch("blachcalc.WZ_EXPORT_DIRECTORY", wz_directory),
                patch("blachcalc.filedialog.asksaveasfilename", return_value=str(target)) as save_dialog,
                patch("blachcalc.messagebox.showinfo"),
            ):
                self.view._save_delivery_note_pdf(preview_data["data"])
                self.assertTrue(target.is_file())
                self.assertEqual(Path(save_dialog.call_args.kwargs["initialdir"]), wz_directory)
                saved_pdf = pymupdf.open(target)
                self.assertIn("Detal testowy", saved_pdf[0].get_text())
                saved_pdf.close()

    def test_delivery_note_draft_is_persisted_and_restored(self) -> None:
        self.view.navigation_buttons["delivery_note"].invoke()
        self.view.delivery_note_variables["document_number"].set("WZ-ROB-9")
        self.view.delivery_note_variables["customer_name"].set("Klient roboczy")
        self.view.issued_packages_text.insert("1.0", "Paleta EUR")
        self.view.delivery_note_rows[0]["description"].set("Detal do wznowienia")
        self.view._add_delivery_note_row({
            "product": "Usługa",
            "description": "Pozycja druga",
            "description2": "",
            "quantity": "3",
            "unit": "szt",
            "notes": "Kontrola",
        })
        self.assertTrue(self.view.save_delivery_note_draft())

        restored_view = DashboardView(
            self.app,
            self.view.storage,
            self.view.user_id,
            self.view.username,
        )
        self.assertTrue(restored_view.delivery_note_initialized)
        self.assertEqual(
            restored_view.delivery_note_variables["document_number"].get(),
            "WZ-ROB-9",
        )
        self.assertEqual(
            restored_view.issued_packages_text.get("1.0", "end-1c"),
            "Paleta EUR",
        )
        self.assertEqual(len(restored_view.delivery_note_rows), 2)
        self.assertEqual(
            restored_view.delivery_note_rows[0]["description"].get(),
            "Detal do wznowienia",
        )
        self.assertEqual(
            restored_view.delivery_note_rows[1]["notes"].get(),
            "Kontrola",
        )

    def test_settings_window_is_resizable_and_scrollable(self) -> None:
        self.view.open_settings()
        self.app.update()
        dialog = next(
            window
            for window in self.view.winfo_children()
            if isinstance(window, tk.Toplevel)
        )
        self.assertEqual(dialog.resizable()[0], 1)
        self.assertTrue(any(
            isinstance(widget, tk.Canvas)
            for widget in dialog.winfo_children()[0].winfo_children()
        ))

    def test_control_s_saves_current_document_from_its_preview(self) -> None:
        self.view.current_page = "summary"
        with patch.object(self.view, "export_summary_pdf") as save_offer:
            self.view._shortcut_save()
        save_offer.assert_called_once_with()

        self.view.current_page = "pdf_preview"
        with patch.object(self.view, "_save_current_document_preview") as save_wz:
            self.view._shortcut_save()
        save_wz.assert_called_once_with()

    def test_print_pdf_bytes_uses_windows_print_verb_without_save_dialog(self) -> None:
        from pathlib import Path

        pdf_content = b"%PDF-test-document"
        submitted: dict[str, str] = {}

        def capture_print(filename: str, verb: str) -> None:
            submitted["filename"] = filename
            submitted["verb"] = verb

        with (
            patch("blachcalc.os.startfile", side_effect=capture_print, create=True),
            patch("blachcalc.messagebox.showinfo"),
        ):
            self.view._print_pdf_bytes(pdf_content, "testowa")

        print_file = Path(submitted["filename"])
        try:
            self.assertEqual(submitted["verb"], "print")
            self.assertEqual(print_file.read_bytes(), pdf_content)
            self.assertEqual(print_file.parent.name, "print_jobs")
        finally:
            print_file.unlink(missing_ok=True)

    def test_offer_and_delivery_note_have_direct_print_actions(self) -> None:
        def walk(widget):
            for child in widget.winfo_children():
                yield child
                yield from walk(child)

        self.assertTrue(any(
            isinstance(widget, ttk.Button) and widget.cget("text") == "Drukuj ofertę"
            for widget in walk(self.view.summary_tab)
        ))
        self.assertTrue(any(
            isinstance(widget, ttk.Button) and widget.cget("text") == "Drukuj WZ"
            for widget in walk(self.view.delivery_note_tab)
        ))

    def test_quote_form_fields_match_combined_burn_time_width(self) -> None:
        time_row = self.view.time_cell.winfo_children()[1]
        target_width = sum(child.winfo_reqwidth() for child in time_row.winfo_children())
        duration_entries = set(self.view._item_focus_chain[-3:])

        def walk(widget):
            for child in widget.winfo_children():
                if isinstance(child, (ttk.Entry, ttk.Combobox)):
                    yield child
                yield from walk(child)

        fields = [widget for widget in walk(self.view.item_body) if widget not in duration_entries]
        self.assertGreater(len(fields), 5)
        for field in fields:
            with self.subTest(field=field):
                self.assertLessEqual(abs(field.winfo_reqwidth() - target_width), 1)

    def test_order_fields_stretch_equally_at_all_form_widths(self) -> None:
        cells = (
            self.view.customer_cell,
            self.view.order_number_entry.master,
            self.view.notes_entry.master,
        )
        for width in (700, 1100):
            self.app.geometry(f"{width}x680+20+20")
            self.app.update()
            cell_widths = [cell.winfo_width() for cell in cells]
            with self.subTest(window_width=width):
                self.assertLess(max(cell_widths) - min(cell_widths), 2)
                self.assertTrue(all(cell.winfo_width() > 150 for cell in cells))
                for cell in cells:
                    field = next(
                        child
                        for child in cell.winfo_children()
                        if isinstance(child, (ttk.Entry, ttk.Combobox))
                    )
                    self.assertEqual(field.winfo_width(), cell.winfo_width())

    def test_item_sections_reflow_symmetrically_with_form_width(self) -> None:
        details = self.view.item_details_panel
        calculation = self.view.item_calculation_panel

        self.app.geometry("1260x680+20+20")
        self.app.update()
        self.assertFalse(self.view.quote_layout_compact)
        self.assertEqual(details.grid_info()["column"], 0)
        self.assertEqual(details.grid_info()["columnspan"], 1)
        self.assertEqual(calculation.grid_info()["column"], 1)
        self.assertEqual(calculation.grid_info()["columnspan"], 1)
        self.assertEqual(details.winfo_y(), calculation.winfo_y())
        self.assertLessEqual(abs(details.winfo_width() - calculation.winfo_width()), 2)
        self.assertGreaterEqual(
            self.view.item_name_entry.winfo_width(),
            self.view.item_details_body.winfo_width() - 12,
        )

        self.app.geometry("700x680+20+20")
        self.app.update()
        self.assertTrue(self.view.quote_layout_compact)
        self.assertEqual(details.grid_info()["columnspan"], 2)
        self.assertEqual(calculation.grid_info()["columnspan"], 2)
        self.assertLess(details.winfo_y() + details.winfo_height(), calculation.winfo_y())
        self.assertLessEqual(abs(details.winfo_width() - calculation.winfo_width()), 2)
        self.assertGreaterEqual(
            self.view.item_name_entry.winfo_width(),
            self.view.item_details_body.winfo_width() - 12,
        )

    def test_rates_are_locked_and_materials_come_from_settings(self) -> None:
        for field in ("price_per_kg", "burning_rate_per_hour", "vat_percent"):
            self.assertEqual(str(self.view._field_widgets[field].cget("state")), "readonly")
        self.view.storage.save_settings(self.view.user_id, {"materials": "S235\nDC01"})
        self.view.settings = self.view.storage.get_settings(self.view.user_id)
        self.view._refresh_material_choices()
        self.assertEqual(list(self.view.material_combo.cget("values")), ["S235", "DC01"])
        self.assertEqual(str(self.view.material_combo.cget("state")), "readonly")

    def test_wheel_scrolls_offer_preview(self) -> None:
        self._add_items(2)
        self.view.customer_var.set("Firma Testowa")
        self.view.order_number_var.set("Z-1")
        self.view.save_estimate()
        self.app.update()
        self.view._render_estimate_preview()
        self.app.update()
        canvas = self.view.preview_canvas
        self.assertLess(canvas.yview()[1], 1.0)
        self._wheel(canvas)
        self.assertGreater(canvas.yview()[0], 0.0)

    def test_invalid_field_is_highlighted_and_cleared_after_edit(self) -> None:
        with patch("blachcalc.messagebox.showerror") as show_error:
            self.view.add_item()
        show_error.assert_called_once()
        entry = self.view._field_widgets["element_name"]
        self.assertEqual(str(entry.cget("style")), "Invalid.TEntry")
        self.view.item_vars["element_name"].set("Wspornik")
        self.assertEqual(str(entry.cget("style")), "TEntry")

        self.view.item_vars["quantity"].set("abc")
        with patch("blachcalc.messagebox.showerror"):
            self.view.add_item()
        self.assertEqual(str(self.view._field_widgets["quantity"].cget("style")), "Invalid.TEntry")

    def test_missing_customer_is_highlighted_on_save(self) -> None:
        self._add_items(1)
        with patch("blachcalc.messagebox.showerror") as show_error:
            self.view.save_estimate()
        self.assertIn("zleceniodawc", show_error.call_args.args[1])
        self.assertEqual(
            str(self.view._field_widgets["customer"].cget("style")),
            "Invalid.TCombobox",
        )

    def test_keyboard_shortcuts_switch_pages_and_duplicate_summary(self) -> None:
        self.view.customer_combo.focus_force()
        self.app.update()
        self.view.customer_combo.event_generate("<Control-Key-3>")
        self.app.update()
        self.assertEqual(self.view.current_page, "customers")
        self.view.customer_combo.focus_force()
        self.app.update()
        self.view.customer_combo.event_generate("<Control-Key-2>")
        self.app.update()
        self.assertEqual(self.view.current_page, "history")

        self._add_items(1)
        self.view.customer_var.set("Firma")
        self.view.order_number_var.set("Z-2")
        self.view.save_estimate()
        self.assertEqual(self.view.current_page, "summary")
        self.view.preview_canvas.focus_force()
        self.app.update()
        self.view.preview_canvas.event_generate("<Control-Shift-D>")
        self.app.update()
        self.assertEqual(self.view.current_page, "quote")
        self.assertIsNone(self.view.editing_estimate_id)
        self.assertEqual(self.view.order_number_var.get(), "")
        self.assertEqual(len(self.view.draft_items), 1)


if __name__ == "__main__":
    unittest.main()
