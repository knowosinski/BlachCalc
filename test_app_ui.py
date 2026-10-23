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
        save = next(w for w in walk(dialog) if isinstance(w, ttk.Button) and w.cget("text") == "Zapisz")
        save.invoke()
        self.app.update()
        from offer_page import parse_offer_page

        page = parse_offer_page(self.view.settings["offer_page2"])
        self.assertEqual(page["terms"]["items"], ["Jedyny warunek", "Drugi"])
        self.assertEqual(page["claims"]["title"], "Odbiór i reklamacje towaru")

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
