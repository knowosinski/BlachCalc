import sqlite3
import tempfile
import unittest
from contextlib import closing
from datetime import datetime
from pathlib import Path

from openpyxl import load_workbook

from feedback_store import FeedbackWorkbook, FeedbackWorkbookError, migrate_legacy_feedback
from storage import Storage


class FeedbackWorkbookTests(unittest.TestCase):
    def test_append_creates_xlsx_and_keeps_user_text_as_text(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "FEEDBACK.xlsx"
            workbook = FeedbackWorkbook(path)
            feedback_id, created_at = workbook.append(
                "  Jan  Kowalski ",
                " jan@example.com ",
                "Błąd",
                " =HYPERLINK(\"https://example.com\") ",
            )

            sheet = load_workbook(path)["Feedback"]
            row = [cell.value for cell in sheet[2]]

        self.assertEqual(row[:6], [
            feedback_id,
            "Jan Kowalski",
            "jan@example.com",
            "Błąd",
            '=HYPERLINK("https://example.com")',
            created_at,
        ])
        self.assertEqual(sheet["E2"].data_type, "s")
        self.assertEqual(sheet["G1"].value, "ID migracji SQLite")
        self.assertTrue(sheet.column_dimensions["G"].hidden)
        self.assertIsNotNone(datetime.fromisoformat(created_at).tzinfo)

    def test_append_adds_rows_without_replacing_existing_feedback(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "FEEDBACK.xlsx"
            workbook = FeedbackWorkbook(path)
            first_id, _ = workbook.append("Jan Kowalski", "", "Błąd", "Pierwsze zgłoszenie")
            second_id, _ = workbook.append("Anna Nowak", "", "Pomysł", "Drugie zgłoszenie")
            sheet = load_workbook(path)["Feedback"]

        self.assertEqual((first_id, second_id), (1, 2))
        self.assertEqual(sheet.max_row, 3)
        self.assertEqual(sheet["E3"].value, "Drugie zgłoszenie")

    def test_legacy_sqlite_feedback_is_moved_then_removed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            storage = Storage(root / "test.sqlite3")
            with closing(sqlite3.connect(storage.database_path)) as connection, connection:
                connection.execute(
                    """
                    CREATE TABLE feedback (
                        id INTEGER PRIMARY KEY,
                        author_name TEXT NOT NULL,
                        author_email TEXT NOT NULL DEFAULT '',
                        category TEXT NOT NULL,
                        message TEXT NOT NULL,
                        created_at TEXT NOT NULL
                    )
                    """
                )
                connection.execute(
                    """
                    INSERT INTO feedback
                    (id, author_name, author_email, category, message, created_at)
                    VALUES (7, 'Jan Kowalski', '', 'Błąd', 'Zawiesza się', '2026-11-23T14:00:00+01:00')
                    """
                )

            xlsx_path = root / "FEEDBACK" / "FEEDBACK.xlsx"
            imported = migrate_legacy_feedback(storage, xlsx_path)
            rows = load_workbook(xlsx_path)["Feedback"]
            with closing(sqlite3.connect(storage.database_path)) as connection:
                feedback_table = connection.execute(
                    "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'feedback'"
                ).fetchone()

            self.assertEqual(imported, 1)
            self.assertEqual(
                [rows.cell(row=2, column=column).value for column in range(1, 7)],
                [1, "Jan Kowalski", None, "Błąd", "Zawiesza się", "2026-11-23T14:00:00+01:00"],
            )
            self.assertEqual(rows["G2"].value, 7)
            self.assertIsNone(feedback_table)

    def test_failed_migration_keeps_legacy_sqlite_feedback(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            storage = Storage(root / "test.sqlite3")
            with closing(sqlite3.connect(storage.database_path)) as connection, connection:
                connection.execute(
                    """
                    CREATE TABLE feedback (
                        id INTEGER PRIMARY KEY,
                        author_name TEXT NOT NULL,
                        author_email TEXT NOT NULL DEFAULT '',
                        category TEXT NOT NULL,
                        message TEXT NOT NULL,
                        created_at TEXT NOT NULL
                    )
                    """
                )
                connection.execute(
                    """
                    INSERT INTO feedback
                    (author_name, author_email, category, message, created_at)
                    VALUES ('Jan Kowalski', '', 'Błąd', 'Zawiesza się', '2026-11-23T14:00:00+01:00')
                    """
                )
            blocked_path = root / "FEEDBACK.xlsx"
            blocked_path.mkdir()

            with self.assertRaises(FeedbackWorkbookError):
                migrate_legacy_feedback(storage, blocked_path)
            self.assertEqual(len(storage.get_legacy_feedback()), 1)


if __name__ == "__main__":
    unittest.main()
