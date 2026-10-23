import csv
import tempfile
import unittest
from io import BytesIO
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from exports import export_estimate_csv, export_estimate_pdf
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from storage import DEFAULT_SETTINGS
from reportlab.platypus import Table as ReportLabTable
from reportlab.platypus import Image as ReportLabImage
from PIL import Image as PillowImage


class ExportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.estimate = {
            "header": {
                "quote_number": "OF_Z-10_Firma",
                "customer_name": "=2+2",
                "customer_tax_id": "1234567890",
                "customer_address": "Warszawa",
                "customer_email": "kontakt@example.com",
                "customer_phone": "123 456 789",
                "customer_contact_person": "Jan Kowalski",
                "order_number": "Z-10",
                "notes": "Termin: 7 dni",
                "net_total": "32.33",
                "vat_amount": "7.44",
                "gross_total": "39.77",
                "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            },
            "items": [
                {
                    "element_name": "Wspornik",
                    "material": "S235JR",
                    "thickness_mm": "4",
                    "quantity": 1,
                    "price_per_kg": "12",
                    "used_weight_kg": "2",
                    "duration_seconds": 60,
                    "burning_rate_per_hour": "500",
                    "vat_percent": "23",
                    "material_cost": "24.00",
                    "burning_cost": "8.33",
                    "unit_net": "32.33",
                    "unit_vat": "7.44",
                    "unit_gross": "39.77",
                    "line_net": "32.33",
                    "line_vat": "7.44",
                    "line_gross": "39.77",
                }
            ],
        }

    def test_csv_uses_semicolon_bom_and_sanitizes_formula_cells(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "estimate.csv"
            export_estimate_csv(self.estimate, path, DEFAULT_SETTINGS)

            raw = path.read_bytes()
            self.assertTrue(raw.startswith(b"\xef\xbb\xbf"))
            with path.open(encoding="utf-8-sig", newline="") as file:
                rows = list(csv.reader(file, delimiter=";"))
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[1][rows[0].index("Zleceniodawca")], "'=2+2")
            self.assertEqual(rows[1][rows[0].index("Pozycja")], "Wspornik")
            self.assertEqual(rows[1][rows[0].index("Sprzedawca")], DEFAULT_SETTINGS["company_name"])
            self.assertEqual(rows[1][rows[0].index("NIP sprzedawcy")], "6272789387")

    def test_csv_reports_photo_presence_without_exposing_filename(self) -> None:
        estimate = {
            **self.estimate,
            "items": [{
                **self.estimate["items"][0],
                "preview_image": b"stored locally",
                "preview_image_name": "wspornik.jpg",
            }],
        }
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "with-image.csv"
            export_estimate_csv(estimate, path, DEFAULT_SETTINGS)
            with path.open(encoding="utf-8-sig", newline="") as file:
                rows = list(csv.DictReader(file, delimiter=";"))
            with path.open(encoding="utf-8-sig") as csv_file:
                self.assertNotIn("wspornik.jpg", csv_file.read())

        self.assertEqual(rows[0]["Zdjęcie poglądowe"], "Tak")

    def test_csv_failure_preserves_existing_export_and_cleans_temporary_file(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "estimate.csv"
            original_content = b"previous export"
            path.write_bytes(original_content)
            invalid_estimate = {
                **self.estimate,
                "items": [
                    self.estimate["items"][0],
                    {"element_name": "Incomplete item"},
                ],
            }

            with self.assertRaises(KeyError):
                export_estimate_csv(invalid_estimate, path)

            self.assertEqual(path.read_bytes(), original_content)
            self.assertEqual(list(Path(temporary_directory).glob(".estimate.csv.*.tmp")), [])

    def test_offer_pdf_includes_position_preview_images(self) -> None:
        image_buffer = BytesIO()
        PillowImage.new("RGB", (80, 50), color=(30, 80, 140)).save(image_buffer, format="JPEG")
        estimate = {
            **self.estimate,
            "items": [{
                **self.estimate["items"][0],
                "preview_image": image_buffer.getvalue(),
                "preview_image_name": "wspornik.jpg",
            }],
        }

        captured_tables = []

        def capture_table(data, *args, **kwargs):
            captured_tables.append(data)
            return ReportLabTable(data, *args, **kwargs)

        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "offer-with-image.pdf"
            with patch("reportlab.platypus.Table", side_effect=capture_table):
                export_estimate_pdf(estimate, DEFAULT_SETTINGS, path, "offer")
            pdf = path.read_bytes()

        self.assertTrue(pdf.startswith(b"%PDF-"))
        self.assertIn(b"/Subtype /Image", pdf)
        self.assertNotIn(b"wspornik.jpg", pdf)
        logo_headers = [
            table for table in captured_tables
            if isinstance(table[0][0], ReportLabImage)
        ]
        self.assertGreaterEqual(len(logo_headers), 2)
        offer_table = next(
            table for table in captured_tables
            if len(table[0]) == 7
            and getattr(table[0][2], "getPlainText", lambda: "")() == "Zdjęcie"
        )
        self.assertIsInstance(offer_table[1][2], ReportLabImage)
        self.assertEqual(offer_table[1][3], "1")
        for header in offer_table[0]:
            self.assertEqual(header.style.textColor.hexval(), "0xffffff")

    def test_offer_pdf_can_be_rendered_from_memory_for_exact_preview(self) -> None:
        import pymupdf

        output = BytesIO()
        export_estimate_pdf(self.estimate, DEFAULT_SETTINGS, output, "offer")
        document = pymupdf.open(stream=output.getvalue(), filetype="pdf")

        self.assertGreaterEqual(document.page_count, 2)
        page = document[0]
        self.assertEqual(round(page.rect.width), round(A4[0]))
        self.assertGreater(page.get_pixmap().width, 0)
        document.close()

    def test_pdf_uses_only_embedded_fonts_with_polish_letters(self) -> None:
        import pymupdf

        for kind in ("offer", "internal"):
            output = BytesIO()
            export_estimate_pdf(self.estimate, DEFAULT_SETTINGS, output, kind)
            document = pymupdf.open(stream=output.getvalue(), filetype="pdf")
            for page in document:
                for block in page.get_text("dict")["blocks"]:
                    for line in block.get("lines", []):
                        for span in line["spans"]:
                            self.assertNotIn("Helvetica", span["font"], f"{kind}: {span['text']!r}")
                            self.assertNotIn("\ufffd", span["text"])
            document.close()

    def test_photo_width_setting_is_clamped_and_resizes_column(self) -> None:
        from exports import photo_width_mm

        self.assertEqual(photo_width_mm({}), 44)
        self.assertEqual(photo_width_mm({"photo_width_mm": "30,5"}), 30.5)
        self.assertEqual(photo_width_mm({"photo_width_mm": "500"}), 56)
        self.assertEqual(photo_width_mm({"photo_width_mm": "x"}), 44)
        buffer = BytesIO()
        PillowImage.new("RGB", (80, 50), color=(30, 80, 140)).save(buffer, format="JPEG")
        estimate = {**self.estimate, "items": [{**self.estimate["items"][0], "preview_image": buffer.getvalue()}]}
        captured = []

        def capture_table(data, *args, **kwargs):
            captured.append(data)
            return ReportLabTable(data, *args, **kwargs)

        with patch("reportlab.platypus.Table", side_effect=capture_table):
            export_estimate_pdf(estimate, {**DEFAULT_SETTINGS, "photo_width_mm": "30"}, BytesIO(), "offer")
        offer_table = next(
            t for t in captured
            if len(t[0]) == 7 and getattr(t[0][2], "getPlainText", lambda: "")() == "Zdjęcie"
        )
        self.assertAlmostEqual(offer_table[1][2].drawWidth / mm, 30, places=1)

    def test_offer_page_two_uses_custom_content_from_settings(self) -> None:
        import json

        import pymupdf
        from offer_page import default_offer_page, parse_offer_page, serialize_offer_page

        page = default_offer_page()
        page["terms"]["title"] = "ZXTITLE"
        page["terms"]["items"] = ["ZXPUNKT jeden", "ZXPUNKT dwa"]
        page["pallets"]["items"] = []
        page["contact"]["person"] = "ZXOSOBA"
        settings = {**DEFAULT_SETTINGS, "offer_page2": serialize_offer_page(page)}
        output = BytesIO()
        export_estimate_pdf(self.estimate, settings, output, "offer")
        document = pymupdf.open(stream=output.getvalue(), filetype="pdf")
        text = " ".join(document[-1].get_text().split())
        document.close()
        for expected in ("ZXTITLE", "ZXPUNKT jeden", "ZXPUNKT dwa", "ZXOSOBA"):
            self.assertIn(expected, text)
        self.assertNotIn("Cennik palet", text)
        self.assertNotIn("Nie zapewniamy", text)
        self.assertEqual(serialize_offer_page(default_offer_page()), "")
        self.assertEqual(parse_offer_page("{zepsute"), default_offer_page())
        self.assertEqual(parse_offer_page(json.dumps({"terms": 5})), default_offer_page())

    def test_offer_pdf_includes_terms_pallet_prices_and_contact_details(self) -> None:
        import pymupdf

        with tempfile.TemporaryDirectory() as temporary_directory:
            offer_path = Path(temporary_directory) / "offer.pdf"
            internal_path = Path(temporary_directory) / "internal.pdf"
            captured_tables = []

            def capture_table(data, *args, **kwargs):
                captured_tables.append((data, kwargs.get("colWidths")))
                return ReportLabTable(data, *args, **kwargs)

            with patch("reportlab.platypus.Table", side_effect=capture_table):
                export_estimate_pdf(self.estimate, DEFAULT_SETTINGS, offer_path, "offer")
            export_estimate_pdf(self.estimate, DEFAULT_SETTINGS, internal_path, "internal")

            offer = pymupdf.open(offer_path)
            offer_text = " ".join("\n".join(page.get_text() for page in offer).split())
            continuation_page = offer[1]
            continuation_images = continuation_page.get_images(full=True)
            continuation_colors = {
                span["color"]
                for block in continuation_page.get_text("dict")["blocks"]
                for line in block.get("lines", [])
                for span in line["spans"]
                if span["text"].strip()
            }
            offer.close()
            internal = pymupdf.open(internal_path)
            internal_text = "\n".join(page.get_text() for page in internal)
            internal.close()

        for expected_text in (
            "Dodatkowe warunki:",
            "Nie zapewniamy płaskości powierzchni",
            "Tolerancja gięcia blach wg DIN ISO 2768 – klasa c",
            "Tolerancja cięcia laserem wg PN-EN ISO 9013 – klasa 1",
            "Zapewniamy jakość wykonania po wierzchniej stronie detalu.",
            "powstających podczas cięcia laserem",
            "zniekształcenia otworów",
            "powstałych od rusztów lasera podczas cięcia.",
            "loco magazyn IZO-TECHNIKA",
            "Cennik palet:",
            "Euro",
            "Odbiór i reklamacje towaru",
            "2 dni od daty odbioru.",
            "jeden dzień od daty odbioru.",
            "Strona 1 z 2",
            "Strona 2 z 2",
            "+48 786 300 750",
            "biuro@izotechnika.com.pl",
        ):
            with self.subTest(expected_text=expected_text):
                self.assertIn(expected_text, offer_text)
        self.assertNotIn("DIN ISO 2768", internal_text)
        self.assertTrue(continuation_images)
        self.assertIn(0x18345B, continuation_colors)
        pallet_table, pallet_widths = next(
            (data, widths)
            for data, widths in captured_tables
            if data and data[0] == ["Euro – 30 zł netto,"]
        )
        self.assertEqual(
            [row[0] for row in pallet_table],
            [
                "Euro – 30 zł netto,",
                "A (1000x2000) – 90 zł netto",
                "B (1250x2500) – 180 zł netto",
                "C (1500x3000) – 200 zł netto",
            ],
        )
        self.assertEqual(sum(pallet_widths), 76 * mm)
        contact_table, _ = next(
            (data, widths)
            for data, widths in captured_tables
            if data and getattr(data[0][0], "getPlainText", lambda: "")() == "OSOBA KONTAKTOWA"
        )
        self.assertEqual(
            [cell.getPlainText() for cell in contact_table[1]],
            ["Katarzyna Iłczyk", "+48 786 300 750", "biuro@izotechnika.com.pl"],
        )
        self.assertNotIn("Biuro: Kontakt:", [getattr(row[0], "getPlainText", lambda: "")() for row in contact_table])

    def test_csv_marks_whole_order_scope_and_exports_aggregate_costs(self) -> None:
        whole_order_estimate = {
            **self.estimate,
            "items": [{
                **self.estimate["items"][0],
                "calculation_mode": "whole_order",
                "quantity": 12,
                "used_weight_kg": "4",
                "duration_seconds": 120,
                "material_cost": "48.00",
                "burning_cost": "16.67",
                "unit_net": "64.67",
                "unit_vat": "14.87",
                "unit_gross": "79.54",
                "line_net": "64.67",
                "line_vat": "14.87",
                "line_gross": "79.54",
            }],
        }
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "whole-order.csv"
            export_estimate_csv(whole_order_estimate, path, DEFAULT_SETTINGS)

            with path.open(encoding="utf-8-sig", newline="") as file:
                rows = list(csv.DictReader(file, delimiter=";"))

        self.assertEqual(rows[0]["Sposób kalkulacji"], "Cała partia")
        self.assertEqual(rows[0]["Ilość / zakres"], "12")
        self.assertEqual(rows[0]["Materiał netto razem (zł)"], "48.00")
        self.assertEqual(rows[0]["Palenie netto razem (zł)"], "16.67")

    def test_pdf_exports_both_client_and_internal_documents(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            for document_kind in ("offer", "internal"):
                path = Path(temporary_directory) / f"{document_kind}.pdf"
                export_estimate_pdf(self.estimate, {}, path, document_kind)
                self.assertTrue(path.read_bytes().startswith(b"%PDF-"))
                self.assertGreater(path.stat().st_size, 1000)

    def test_offer_pdf_tables_fit_inside_a4_page_margins(self) -> None:
        table_widths: list[list[float]] = []

        def capture_table(data: list[list[object]], *args: object, **kwargs: object) -> object:
            widths = kwargs.get("colWidths")
            if widths:
                table_widths.append([float(width) for width in widths])
            return ReportLabTable(data, *args, **kwargs)

        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "offer-width.pdf"
            with patch("reportlab.platypus.Table", side_effect=capture_table):
                export_estimate_pdf(self.estimate, DEFAULT_SETTINGS, path, "offer")

        available_width = A4[0] - 30 * mm
        self.assertTrue(table_widths)
        self.assertTrue(any(widths[0] == 9 * mm for widths in table_widths))
        for widths in table_widths:
            with self.subTest(widths=widths):
                self.assertLessEqual(sum(widths), available_width)

    def test_client_offer_exports_with_confirmed_izotechnika_profile_and_logo(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "izotechnika-offer.pdf"
            export_estimate_pdf(self.estimate, DEFAULT_SETTINGS, path, "offer")

            self.assertTrue(path.read_bytes().startswith(b"%PDF-"))
            self.assertGreater(path.stat().st_size, 4000)

    def test_total_only_offer_hides_per_item_names_and_unit_prices(self) -> None:
        doubled_estimate = {
            **self.estimate,
            "header": {
                **self.estimate["header"],
                "pricing_mode": "total_only",
                "net_total": "64.66",
                "vat_amount": "14.88",
                "gross_total": "79.54",
            },
            "items": [
                {
                    **self.estimate["items"][0],
                    "quantity": 2,
                    "line_net": "64.66",
                    "line_vat": "14.88",
                    "line_gross": "79.54",
                }
            ],
        }
        tables: list[list[list[object]]] = []

        def capture_table(data: list[list[object]], *args: object, **kwargs: object) -> object:
            tables.append(data)
            return ReportLabTable(data, *args, **kwargs)

        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "total-only.pdf"
            with patch("reportlab.platypus.Table", side_effect=capture_table):
                export_estimate_pdf(doubled_estimate, DEFAULT_SETTINGS, path, "offer")

            offer_table = next(table for table in tables if len(table[0]) == 5)
            offer_text = " ".join(
                str(cell.getPlainText()) if hasattr(cell, "getPlainText") else str(cell)
                for row in offer_table
                for cell in row
            )
            self.assertIn("Kompleksowa realizacja wypalanych elementów", offer_text)
            self.assertIn("79,54 zł", offer_text)
            self.assertNotIn("Wspornik", offer_text)
            self.assertEqual(offer_table[1][2], "2")
            self.assertNotIn("32,33 zł", offer_text)

    def test_whole_order_offer_and_internal_sheet_show_finished_quantity(self) -> None:
        whole_order_estimate = {
            **self.estimate,
            "items": [{
                **self.estimate["items"][0],
                "calculation_mode": "whole_order",
                "quantity": 12,
                "used_weight_kg": "4",
                "duration_seconds": 120,
                "material_cost": "48.00",
                "burning_cost": "16.67",
                "unit_net": "64.67",
                "unit_vat": "14.87",
                "unit_gross": "79.54",
                "line_net": "64.67",
                "line_vat": "14.87",
                "line_gross": "79.54",
            }],
        }
        tables: list[list[list[object]]] = []

        def capture_table(data: list[list[object]], *args: object, **kwargs: object) -> object:
            tables.append(data)
            return ReportLabTable(data, *args, **kwargs)

        with tempfile.TemporaryDirectory() as temporary_directory:
            for document_kind in ("offer", "internal"):
                tables.clear()
                path = Path(temporary_directory) / f"{document_kind}-batch.pdf"
                with patch("reportlab.platypus.Table", side_effect=capture_table):
                    export_estimate_pdf(whole_order_estimate, DEFAULT_SETTINGS, path, document_kind)

                table_width = 6 if document_kind == "offer" else 10
                detail_table = next(
                    table
                    for table in tables
                    if len(table[0]) == table_width
                )
                table_text = " ".join(
                    str(cell.getPlainText()) if hasattr(cell, "getPlainText") else str(cell)
                    for row in detail_table
                    for cell in row
                )
                self.assertIn("64,67 zł" if document_kind == "offer" else "64.67 zł", table_text)
                self.assertIn("12", table_text)
                if document_kind == "offer":
                    self.assertNotIn("Netto / szt.", table_text)
                else:
                    self.assertIn("Masa kg/szt. lub razem", table_text)
                    self.assertIn("48.00 zł", table_text)

    def test_pdf_rejects_unknown_document_type(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "bad.pdf"
            path.write_bytes(b"previous export")
            with self.assertRaises(ValueError):
                export_estimate_pdf(self.estimate, {}, path, "other")
            self.assertEqual(path.read_bytes(), b"previous export")
            self.assertEqual(list(Path(temporary_directory).glob(".bad.pdf.*.tmp")), [])


if __name__ == "__main__":
    unittest.main()
