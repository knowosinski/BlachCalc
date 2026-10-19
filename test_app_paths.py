import unittest
from pathlib import Path
from unittest.mock import patch

import app_paths
from blachcalc import DashboardView, calculate_item_line_amounts, line_totals


class AppPathTests(unittest.TestCase):
    def test_resource_path_finds_bundled_company_logo(self) -> None:
        self.assertTrue(app_paths.resource_path("logo.png").is_file())

    def test_development_exports_stay_in_the_project(self) -> None:
        self.assertEqual(
            app_paths.offer_export_directory(),
            Path(__file__).resolve().parent / "OFERTY CENOWE BLACHCALC",
        )

    def test_frozen_exports_use_the_user_documents_folder(self) -> None:
        with patch.object(app_paths.sys, "frozen", True, create=True):
            self.assertEqual(
                app_paths.offer_export_directory(),
                Path.home() / "Documents" / "OFERTY CENOWE BLACHCALC",
            )

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
