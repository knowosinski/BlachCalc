import os
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.utils.exceptions import InvalidFileException

from app_paths import feedback_export_directory
from storage import Storage


FEEDBACK_WORKBOOK_NAME = "FEEDBACK.xlsx"
FEEDBACK_HEADERS = (
    "ID",
    "Autor",
    "E-mail",
    "Kategoria",
    "Opis",
    "Data i godzina",
)
LEGACY_ID_HEADER = "ID migracji SQLite"
LEGACY_ID_COLUMN = len(FEEDBACK_HEADERS) + 1


class FeedbackWorkbookError(ValueError):
    pass


def feedback_workbook_path() -> Path:
    return feedback_export_directory() / FEEDBACK_WORKBOOK_NAME


class FeedbackWorkbook:
    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path is not None else feedback_workbook_path()

    def append(
        self,
        author_name: str,
        author_email: str,
        category: str,
        message: str,
        created_at: str | None = None,
    ) -> tuple[int, str]:
        author_name = " ".join(author_name.split())
        author_email = author_email.strip()
        category = category.strip()
        message = message.strip()
        if not author_name:
            raise ValueError("Imię i nazwisko autora feedbacku są wymagane.")
        if not category:
            raise ValueError("Wybierz kategorię feedbacku.")
        if not message:
            raise ValueError("Treść feedbacku nie może być pusta.")

        created_at = created_at or datetime.now().astimezone().isoformat(timespec="seconds")
        workbook, sheet = self._load()
        try:
            feedback_id = self._next_id(sheet)
            self._append_row(
                sheet,
                feedback_id,
                author_name,
                author_email,
                category,
                message,
                created_at,
            )
            self._save(workbook)
        finally:
            workbook.close()
        return feedback_id, created_at

    def import_legacy_rows(self, rows: list[dict[str, Any]]) -> int:
        if not rows:
            return 0

        workbook, sheet = self._load()
        try:
            imported_legacy_ids = {
                int(value)
                for (value,) in sheet.iter_rows(
                    min_row=2,
                    min_col=LEGACY_ID_COLUMN,
                    max_col=LEGACY_ID_COLUMN,
                    values_only=True,
                )
                if value is not None
            }
            next_id = self._next_id(sheet)
            imported_count = 0
            for row in rows:
                legacy_id = int(row["id"])
                if legacy_id in imported_legacy_ids:
                    continue
                self._append_row(
                    sheet,
                    next_id,
                    str(row["author_name"]),
                    str(row["author_email"]),
                    str(row["category"]),
                    str(row["message"]),
                    str(row["created_at"]),
                    legacy_id=legacy_id,
                )
                imported_legacy_ids.add(legacy_id)
                next_id += 1
                imported_count += 1
            if imported_count:
                self._save(workbook)
        finally:
            workbook.close()
        return imported_count

    def _load(self) -> tuple[Workbook, Any]:
        workbook: Workbook | None = None
        try:
            if self.path.is_file():
                workbook = load_workbook(self.path)
            else:
                workbook = Workbook()
            if "Feedback" in workbook.sheetnames:
                sheet = workbook["Feedback"]
            elif (
                len(workbook.sheetnames) == 1
                and workbook.active.max_row == 1
                and all(cell.value is None for cell in workbook.active[1])
            ):
                sheet = workbook.active
                sheet.title = "Feedback"
            else:
                sheet = workbook.create_sheet("Feedback")

            if sheet.max_row == 1 and all(cell.value is None for cell in sheet[1]):
                for column, header in enumerate(FEEDBACK_HEADERS, start=1):
                    sheet.cell(row=1, column=column, value=header)
                sheet.cell(row=1, column=LEGACY_ID_COLUMN, value=LEGACY_ID_HEADER)
                self._style_header(sheet)
            elif tuple(
                sheet.cell(row=1, column=column).value
                for column in range(1, len(FEEDBACK_HEADERS) + 1)
            ) != FEEDBACK_HEADERS:
                raise FeedbackWorkbookError(
                    f"Arkusz Feedback w pliku {self.path} ma nieoczekiwany układ kolumn."
                )
            elif sheet.cell(row=1, column=LEGACY_ID_COLUMN).value is None:
                sheet.cell(row=1, column=LEGACY_ID_COLUMN, value=LEGACY_ID_HEADER)
            elif sheet.cell(row=1, column=LEGACY_ID_COLUMN).value != LEGACY_ID_HEADER:
                raise FeedbackWorkbookError(
                    f"Arkusz Feedback w pliku {self.path} zawiera nieoczekiwane dane w kolumnie G."
                )

            sheet.column_dimensions[get_column_letter(LEGACY_ID_COLUMN)].hidden = True
            sheet.freeze_panes = "A2"
            sheet.auto_filter.ref = f"A1:{get_column_letter(len(FEEDBACK_HEADERS))}{sheet.max_row}"
            return workbook, sheet
        except FeedbackWorkbookError:
            if workbook is not None:
                workbook.close()
            raise
        except (OSError, zipfile.BadZipFile, InvalidFileException) as error:
            if workbook is not None:
                workbook.close()
            raise FeedbackWorkbookError(
                f"Nie można otworzyć pliku feedbacku:\n{self.path}\n\n{error}"
            ) from error

    @staticmethod
    def _style_header(sheet: Any) -> None:
        for cell in sheet[1]:
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill("solid", fgColor="243F82")
            cell.alignment = Alignment(wrap_text=True, vertical="center")
        widths = (8, 24, 32, 18, 70, 28, 22)
        for column, width in enumerate(widths, start=1):
            sheet.column_dimensions[get_column_letter(column)].width = width

    @staticmethod
    def _next_id(sheet: Any) -> int:
        existing_ids = [
            int(value)
            for (value,) in sheet.iter_rows(min_row=2, max_col=1, values_only=True)
            if isinstance(value, (int, float)) and int(value) > 0
        ]
        return max(existing_ids, default=0) + 1

    @staticmethod
    def _append_row(
        sheet: Any,
        feedback_id: int,
        author_name: str,
        author_email: str,
        category: str,
        message: str,
        created_at: str,
        legacy_id: int | None = None,
    ) -> None:
        values = (
            feedback_id,
            author_name,
            author_email,
            category,
            message,
            created_at,
            legacy_id,
        )
        row_index = sheet.max_row + 1
        for column, value in enumerate(values, start=1):
            cell = sheet.cell(row=row_index, column=column, value=value)
            if isinstance(value, str):
                cell.data_type = "s"
                cell.number_format = "@"
                cell.alignment = Alignment(vertical="top", wrap_text=column == 5)
        sheet.auto_filter.ref = f"A1:{get_column_letter(len(FEEDBACK_HEADERS))}{row_index}"

    def _save(self, workbook: Workbook) -> None:
        temporary_path: Path | None = None
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                dir=self.path.parent,
                prefix=f".{self.path.stem}.",
                suffix=".tmp.xlsx",
                delete=False,
            ) as temporary_file:
                temporary_path = Path(temporary_file.name)
            workbook.save(temporary_path)
            os.replace(temporary_path, self.path)
        except OSError as error:
            raise FeedbackWorkbookError(
                f"Nie można zapisać pliku feedbacku:\n{self.path}\n\n"
                f"Sprawdź, czy plik nie jest otwarty w Excelu.\n{error}"
            ) from error
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)


def migrate_legacy_feedback(
    storage: Storage,
    workbook_path: str | Path | None = None,
) -> int:
    rows = storage.get_legacy_feedback()
    workbook = FeedbackWorkbook(workbook_path)
    imported_count = workbook.import_legacy_rows(rows)
    storage.drop_legacy_feedback_table()
    return imported_count
