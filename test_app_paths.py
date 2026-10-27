import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

import app_paths
from blachcalc import DashboardView
from quote_domain import calculate_item_line_amounts, line_totals


class AppPathTests(unittest.TestCase):
    def test_dated_export_directory_uses_day_and_month(self) -> None:
        base = Path("exports")

        self.assertEqual(
            app_paths.dated_export_directory(base, date(2026, 10, 26)),
            base / "26.10",
        )

    def test_export_filename_gets_extension_even_when_name_contains_dots(self) -> None:
        self.assertEqual(
            app_paths.ensure_file_extension("WZ-002_ELMAR__Rudniccy_S.C", "pdf"),
            "WZ-002_ELMAR__Rudniccy_S.C.pdf",
        )
        self.assertEqual(app_paths.ensure_file_extension("oferta.PDF", "pdf"), "oferta.PDF")
        self.assertEqual(app_paths.ensure_file_extension("", "pdf"), "")

    def test_resource_path_finds_bundled_company_logo(self) -> None:
        self.assertTrue(app_paths.resource_path("logo.png").is_file())

    def test_development_exports_use_the_user_documents_folder(self) -> None:
        self.assertEqual(
            app_paths.offer_export_directory(),
            Path.home() / "Documents" / "BLACHCALC" / "OFERTY",
        )

    def test_frozen_exports_use_the_user_documents_folder(self) -> None:
        with patch.object(app_paths.sys, "frozen", True, create=True):
            self.assertEqual(
                app_paths.offer_export_directory(),
                Path.home() / "Documents" / "BLACHCALC" / "OFERTY",
            )
            self.assertEqual(
                app_paths.wz_export_directory(),
                Path.home() / "Documents" / "BLACHCALC" / "WZ",
            )

    def test_development_wz_exports_use_a_dedicated_subfolder(self) -> None:
        self.assertEqual(
            app_paths.wz_export_directory(),
            app_paths.export_root_directory() / "WZ",
        )

    def test_dated_export_directory_zero_pads_and_handles_leap_day(self) -> None:
        base = Path("exports")
        cases = (
            (date(2024, 2, 29), "29.02"),
            (date(2026, 1, 5), "05.01"),
            (date(2026, 9, 9), "09.09"),
            (date(2026, 12, 31), "31.12"),
            (date(2026, 1, 1), "01.01"),
        )
        for export_date, expected in cases:
            with self.subTest(export_date=export_date):
                self.assertEqual(app_paths.dated_export_directory(base, export_date), base / expected)

    def test_dated_export_directory_defaults_to_today_and_ignores_year(self) -> None:
        class FixedDate(date):
            @classmethod
            def today(cls):
                return cls(2027, 3, 4)

        with patch.object(app_paths, "date", FixedDate):
            self.assertEqual(app_paths.dated_export_directory(Path("x")), Path("x") / "04.03")
            self.assertEqual(
                app_paths.dated_export_directory(Path("x"), date(2020, 3, 4)),
                app_paths.dated_export_directory(Path("x")),
            )

    def test_dated_export_directory_does_not_create_the_folder(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = app_paths.dated_export_directory(Path(directory), date(2026, 10, 26))
            self.assertFalse(result.exists())
            self.assertEqual(result.parent, Path(directory))

    def test_excel_copy_path_uses_pdf_stem_and_dated_folder(self) -> None:
        base = Path("EXCEL")
        self.assertEqual(
            app_paths.excel_copy_path(base, "OF_Z-10_Firma.pdf", date(2026, 10, 26)),
            base / "26.10" / "OF_Z-10_Firma.xlsx",
        )

    def test_excel_copy_path_keeps_inner_dots_and_drops_directories(self) -> None:
        base = Path("EXCEL")
        self.assertEqual(
            app_paths.excel_copy_path(base, "WZ-002_ELMAR__Rudniccy_S.C.pdf", date(2026, 2, 29 - 1)),
            base / "28.02" / "WZ-002_ELMAR__Rudniccy_S.C.xlsx",
        )
        self.assertEqual(
            app_paths.excel_copy_path(base, Path("C:/Users/a/Documents/oferta.PDF"), date(2024, 2, 29)),
            base / "29.02" / "oferta.xlsx",
        )

    def test_excel_copy_path_without_extension_or_with_other_extension(self) -> None:
        base = Path("EXCEL")
        day = date(2026, 5, 6)
        self.assertEqual(app_paths.excel_copy_path(base, "bez_rozszerzenia", day), base / "06.05" / "bez_rozszerzenia.xlsx")
        self.assertEqual(app_paths.excel_copy_path(base, "dane.csv", day), base / "06.05" / "dane.xlsx")
        self.assertEqual(app_paths.excel_copy_path(base, "Łódź Zażółć.pdf", day), base / "06.05" / "Łódź Zażółć.xlsx")

    def test_excel_copy_path_is_inside_excel_export_directory_by_default_layout(self) -> None:
        path = app_paths.excel_copy_path(app_paths.excel_export_directory(), "a.pdf", date(2026, 10, 26))
        self.assertEqual(path.parent.parent, app_paths.export_root_directory() / "EXCEL")
        self.assertEqual(path.suffix, ".xlsx")

    def test_export_directories_are_siblings_under_the_offer_directory(self) -> None:
        offer = app_paths.export_root_directory()
        self.assertEqual(app_paths.wz_export_directory().parent, offer)
        self.assertEqual(app_paths.excel_export_directory().parent, offer)
        self.assertEqual(app_paths.excel_export_directory().name, "EXCEL")
        self.assertNotEqual(app_paths.wz_export_directory(), app_paths.excel_export_directory())

    def test_export_directories_follow_the_home_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(app_paths.Path, "home", return_value=Path(directory)):
                self.assertEqual(
                    app_paths.offer_export_directory(),
                    Path(directory) / "Documents" / "BLACHCALC" / "OFERTY",
                )
                self.assertEqual(app_paths.wz_export_directory().parent.parent.parent, Path(directory))

    def test_ensure_file_extension_is_case_insensitive_and_preserves_original_case(self) -> None:
        for name in ("a.pdf", "a.PDF", "a.Pdf", "A.pDf"):
            with self.subTest(name=name):
                self.assertEqual(app_paths.ensure_file_extension(name, "pdf"), name)
        self.assertEqual(app_paths.ensure_file_extension("a.XLSX", "xlsx"), "a.XLSX")

    def test_ensure_file_extension_accepts_leading_dot_and_upper_case_extension(self) -> None:
        self.assertEqual(app_paths.ensure_file_extension("a", ".pdf"), "a.pdf")
        self.assertEqual(app_paths.ensure_file_extension("a", "..pdf"), "a.pdf")
        self.assertEqual(app_paths.ensure_file_extension("a.pdf", ".PDF"), "a.pdf")
        self.assertEqual(app_paths.ensure_file_extension("a", "PDF"), "a.PDF")

    def test_ensure_file_extension_appends_after_other_or_partial_extensions(self) -> None:
        cases = (
            ("S.C.", "pdf", "S.C..pdf"),
            ("Kowalski i Syn S.C", "xlsx", "Kowalski i Syn S.C.xlsx"),
            ("raport.pdf.txt", "pdf", "raport.pdf.txt.pdf"),
            ("a.csv", "xlsx", "a.csv.xlsx"),
            ("filepdf", "pdf", "filepdf.pdf"),
            ("file.pd", "pdf", "file.pd.pdf"),
            ("oferta.", "pdf", "oferta..pdf"),
            ("a.b.c.d", "csv", "a.b.c.d.csv"),
            ("a.xlsx.pdf", "xlsx", "a.xlsx.pdf.xlsx"),
            (" a ", "pdf", " a .pdf"),
            ("Łódź Zażółć", "pdf", "Łódź Zażółć.pdf"),
        )
        for name, extension, expected in cases:
            with self.subTest(name=name, extension=extension):
                self.assertEqual(app_paths.ensure_file_extension(name, extension), expected)

    def test_ensure_file_extension_is_idempotent(self) -> None:
        once = app_paths.ensure_file_extension("WZ_S.C", "pdf")
        self.assertEqual(app_paths.ensure_file_extension(once, "pdf"), once)

    def test_ensure_file_extension_returns_empty_name_unchanged_for_any_extension(self) -> None:
        self.assertEqual(app_paths.ensure_file_extension("", "xlsx"), "")
        self.assertEqual(app_paths.ensure_file_extension("", ".csv"), "")

    def test_resource_path_prefers_pyinstaller_bundle_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(app_paths.sys, "_MEIPASS", directory, create=True):
                self.assertEqual(app_paths.resource_path("logo.png"), Path(directory) / "logo.png")
                self.assertEqual(app_paths.resource_path("a/b.txt"), Path(directory) / "a" / "b.txt")

    def test_resource_path_defaults_to_module_directory_and_missing_files_are_not_files(self) -> None:
        module_directory = Path(app_paths.__file__).resolve().parent
        self.assertEqual(app_paths.resource_path("logo.png"), module_directory / "logo.png")
        self.assertFalse(app_paths.resource_path("definitely-missing-file.xyz").exists())

    def test_clicking_zero_duration_field_clears_its_initial_zero(self) -> None:
        class Entry:
            value = "0"

            def get(self) -> str:
                return self.value

            def delete(self, _start: int, _end: str) -> None:
                self.value = ""

        entry = Entry()
        DashboardView._clear_zero_duration_on_focus(type("Event", (), {"widget": entry})())

        self.assertEqual(entry.value, "")

    def test_duration_focus_does_not_clear_nonzero_value(self) -> None:
        class Entry:
            value = "10"

            def get(self) -> str:
                return self.value

            def delete(self, _start: int, _end: str) -> None:
                self.value = ""

        entry = Entry()
        DashboardView._clear_zero_duration_on_focus(type("Event", (), {"widget": entry})())

        self.assertEqual(entry.value, "10")

    def test_finished_quantity_does_not_multiply_whole_batch_cost(self) -> None:
        amounts = calculate_item_line_amounts(
            100,
            23,
            123,
            quantity=75,
            calculation_mode="whole_order",
        )

        self.assertEqual(amounts, (100, 23, 123))
        self.assertEqual(
            line_totals({
                "unit_net": "100",
                "unit_vat": "23",
                "calculation_mode": "whole_order",
                "quantity": 75,
            }),
            (100, 23, 123),
        )

    def test_per_piece_quantity_still_multiplies_cost(self) -> None:
        self.assertEqual(
            calculate_item_line_amounts(
                100,
                23,
                123,
                quantity=4,
                calculation_mode="per_piece",
            ),
            (400, 92, 492),
        )


if __name__ == "__main__":
    unittest.main()


class EnsureExportDirectoriesTests(unittest.TestCase):
    def test_fresh_computer_gets_all_three_folders(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(app_paths.Path, "home", return_value=Path(directory)):
                app_paths.ensure_export_directories()
                root = Path(directory) / "Documents" / "BLACHCALC"
                for name in ("OFERTY", "WZ", "EXCEL"):
                    self.assertTrue((root / name).is_dir())

    def test_legacy_folder_is_renamed_and_offer_days_move_to_oferty(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            documents = Path(directory) / "Documents"
            (documents / "OFERTY CENOWE BLACHCALC" / "26.10").mkdir(parents=True)
            (documents / "OFERTY CENOWE BLACHCALC" / "26.10" / "a.pdf").write_bytes(b"x")
            (documents / "OFERTY CENOWE BLACHCALC" / "WZ" / "26.10").mkdir(parents=True)
            with patch.object(app_paths.Path, "home", return_value=Path(directory)):
                app_paths.ensure_export_directories()
            root = documents / "BLACHCALC"
            self.assertFalse((documents / "OFERTY CENOWE BLACHCALC").exists())
            self.assertTrue((root / "OFERTY" / "26.10" / "a.pdf").is_file())
            self.assertTrue((root / "WZ" / "26.10").is_dir())
            self.assertTrue((root / "EXCEL").is_dir())
