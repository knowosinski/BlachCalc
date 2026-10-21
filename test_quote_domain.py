import unittest
from decimal import Decimal

from quote_domain import calculate_item_line_amounts, format_pln, line_totals


class QuoteDomainTests(unittest.TestCase):
    def test_formats_amounts_using_polish_currency_conventions(self) -> None:
        self.assertEqual(format_pln("1234567.8"), "1 234 567,80 zł")

    def test_line_totals_use_quantity_for_per_piece_items(self) -> None:
        self.assertEqual(
            line_totals(
                {
                    "quantity": 3,
                    "unit_net": "10.00",
                    "unit_vat": "2.30",
                    "calculation_mode": "per_piece",
                }
            ),
            (Decimal("30.00"), Decimal("6.90"), Decimal("36.90")),
        )

    def test_line_totals_keep_whole_order_cost_fixed(self) -> None:
        self.assertEqual(
            line_totals(
                {
                    "quantity": 12,
                    "unit_net": "10.00",
                    "unit_vat": "2.30",
                    "calculation_mode": "whole_order",
                }
            ),
            (Decimal("10.00"), Decimal("2.30"), Decimal("12.30")),
        )

    def test_line_totals_reject_unknown_mode_and_invalid_quantity(self) -> None:
        with self.assertRaises(ValueError):
            calculate_item_line_amounts(
                Decimal("10"),
                Decimal("2.3"),
                Decimal("12.3"),
                quantity=1,
                calculation_mode="unexpected",
            )
        with self.assertRaises(ValueError):
            calculate_item_line_amounts(
                Decimal("10"),
                Decimal("2.3"),
                Decimal("12.3"),
                quantity=0,
                calculation_mode="per_piece",
            )

    def test_line_totals_report_missing_or_invalid_amount_fields(self) -> None:
        with self.assertRaisesRegex(ValueError, "nieprawidłowe kwoty"):
            line_totals({"quantity": 1, "unit_net": "invalid"})
        with self.assertRaisesRegex(ValueError, "nieprawidłowe kwoty"):
            line_totals(
                {
                    "quantity": 1,
                    "unit_net": "NaN",
                    "unit_vat": "2.30",
                }
            )


if __name__ == "__main__":
    unittest.main()
