"""Wspólna, jednorazowo uruchamiana aplikacja dla wszystkich testów interfejsu."""
import atexit
import sqlite3
import tempfile
import tkinter as tk
import unittest
from contextlib import closing
from pathlib import Path
from typing import Any
from unittest.mock import patch

from blachcalc import BlachCalcApp, DashboardView
from storage import Storage

_shared: dict[str, Any] = {}


def _ensure_app() -> dict[str, Any]:
    if _shared:
        return _shared
    temporary_directory = tempfile.TemporaryDirectory()
    storage = Storage(Path(temporary_directory.name) / "ui.sqlite3")
    try:
        app = BlachCalcApp(storage)
    except tk.TclError as error:
        temporary_directory.cleanup()
        raise unittest.SkipTest(f"Brak środowiska graficznego: {error}") from error
    app.geometry("1000x680+20+20")
    app.update()
    view = next(child for child in app.winfo_children() if isinstance(child, DashboardView))
    _shared.update(
        temporary_directory=temporary_directory,
        storage=storage,
        app=app,
        view=view,
        user_id=app.user_id,
        username=app.username,
    )
    return _shared


def shutdown() -> None:
    if not _shared:
        return
    app = _shared["app"]
    try:
        app.destroy()
    except tk.TclError:
        pass
    try:
        _shared["temporary_directory"].cleanup()
    except OSError:
        pass
    _shared.clear()


atexit.register(shutdown)


def walk(widget: tk.Misc):
    for child in widget.winfo_children():
        yield child
        yield from walk(child)


class SharedAppTestCase(unittest.TestCase):
    app: BlachCalcApp
    view: DashboardView
    storage: Storage
    user_id: int
    username: str

    @classmethod
    def setUpClass(cls) -> None:
        shared = _ensure_app()
        cls.app = shared["app"]
        cls.view = shared["view"]
        cls.storage = shared["storage"]
        cls.user_id = shared["user_id"]
        cls.username = shared["username"]

    def setUp(self) -> None:
        self.view = self.__class__.view
        self._reset_application_state()

    def tearDown(self) -> None:
        self.app.update()

    def _reset_application_state(self) -> None:
        for child in self.app.winfo_children() + self.view.winfo_children():
            if isinstance(child, tk.Toplevel):
                child.destroy()
        for attribute in (
            "_preview_resize_after_id",
            "_delivery_note_save_after_id",
            "_sidebar_density_after_id",
            "_pdf_preview_resize_after_id",
            "_pdf_preview_render_after_id",
        ):
            after_id = getattr(self.view, attribute, None)
            if after_id is not None:
                try:
                    self.view.after_cancel(after_id)
                except tk.TclError:
                    pass
                setattr(self.view, attribute, None)
        with closing(sqlite3.connect(self.storage.database_path)) as connection, connection:
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("DELETE FROM estimates WHERE user_id = ?", (self.user_id,))
            connection.execute("DELETE FROM customers WHERE user_id = ?", (self.user_id,))
            connection.execute("DELETE FROM quotes WHERE user_id = ?", (self.user_id,))
            connection.execute("DELETE FROM user_settings WHERE user_id = ?", (self.user_id,))
        self.view.settings = self.storage.get_settings(self.user_id)
        self.view._refresh_material_choices()
        self.view._refresh_brand_badge()
        self.view.clear_form()
        self._clear_delivery_note_form()
        self.view.delivery_note_return_page = "quote"
        self.view._delivery_note_draft_error_shown = False
        self.view.summary_estimate = None
        self.view.navigation_buttons["summary"].configure(state="disabled", style="Nav.TButton")
        self.view.summary_status_var.set("")
        self.view._pdf_preview_bytes = None
        self.view._pdf_preview_print_action = None
        self.view._pdf_preview_save_action = None
        self.view._pdf_preview_return_page = "delivery_note"
        self.view.pdf_preview_status.set("")
        self.view._pdf_preview_images.clear()
        self.view.preview_page_images.clear()
        self.view.preview_canvas.delete("all")
        self.view.pdf_preview_canvas.delete("all")
        self.view.history_search.set("")
        self.view._quote_undo_stack.clear()
        self.view._quote_redo_stack.clear()
        self.view._quote_history_snapshot = self.view._capture_quote_state()
        self.app.geometry("1000x680+20+20")
        self.view._show_page("quote")
        self.view.refresh_history()
        self.view.refresh_customers()
        self.app.update()

    def _clear_delivery_note_form(self) -> None:
        self.view._restoring_delivery_note_draft = True
        for variable in self.view.delivery_note_variables.values():
            variable.set("")
        self.view.issued_packages_text.delete("1.0", "end")
        self.view.returned_packages_text.delete("1.0", "end")
        for row in self.view.delivery_note_rows[:]:
            row["frame"].destroy()
        self.view.delivery_note_rows.clear()
        self.view.delivery_note_initialized = False
        self.view.delivery_note_estimate_id = None
        self.view._restoring_delivery_note_draft = False

    def _wheel(self, widget: tk.Widget, delta: int = -120, state: int = 0) -> None:
        with patch.object(self.view, "winfo_containing", return_value=widget):
            widget.event_generate("<MouseWheel>", x=6, y=6, delta=delta, state=state)
            self.app.update()
