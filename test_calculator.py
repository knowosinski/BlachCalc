import unittest
from decimal import Decimal

from calculator import calculate_quote, parse_decimal, parse_duration


class CalculatorTests(unittest.TestCase):
    def test_calculates_material_burning_and_vat(self) -> None:
        quote = calculate_quote(
            price_per_kg=Decimal("12.50"),
            used_weight_kg=Decimal("4"),
            duration_seconds=5400,
            burning_rate_per_hour=Decimal("500"),
            vat_percent=Decimal("23"),
        )
        self.assertEqual(quote.material_cost, Decimal("50.00"))
        self.assertEqual(quote.burning_cost, Decimal("750.00"))
        self.assertEqual(quote.net_total, Decimal("800.00"))
        self.assertEqual(quote.vat_amount, Decimal("184.00"))
        self.assertEqual(quote.gross_total, Decimal("984.00"))

    def test_accepts_polish_decimal_separator_and_rounds_half_up(self) -> None:
        self.assertEqual(parse_decimal("12,345", "Cena"), Decimal("12.345"))
        quote = calculate_quote(
            Decimal("1.005"), Decimal("1"), 0, Decimal("0"), Decimal("0")
        )
        self.assertEqual(quote.material_cost, Decimal("1.01"))

    def test_duration_converts_hours_minutes_and_seconds(self) -> None:
        self.assertEqual(parse_duration("1", "2", "3"), 3723)

    def test_duration_rejects_out_of_range_minutes(self) -> None:
        with self.assertRaises(ValueError):
            parse_duration("0", "60", "0")

    def test_calculation_rejects_zero_material_weight(self) -> None:
        with self.assertRaises(ValueError):
            calculate_quote(Decimal("10"), Decimal("0"), 10, Decimal("500"), Decimal("23"))

    def test_calculation_rejects_invalid_vat(self) -> None:
        with self.assertRaises(ValueError):
            calculate_quote(Decimal("10"), Decimal("1"), 10, Decimal("500"), Decimal("101"))

    def test_parse_decimal_rejects_extreme_values_and_exponents(self) -> None:
        for value in ("1e100", "1e-1000000", "9" * 65, "NaN", "Infinity"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_decimal(value, "Cena")

    def test_calculation_rejects_values_that_cannot_be_safely_rounded(self) -> None:
        with self.assertRaisesRegex(ValueError, "Cena, masa, stawka i VAT"):
            calculate_quote(Decimal("1e100"), Decimal("1"), 0, Decimal("0"), Decimal("23"))

    def test_duration_rejects_more_than_ten_years(self) -> None:
        with self.assertRaisesRegex(ValueError, "10 lat"):
            parse_duration("876001", "0", "0")


if __name__ == "__main__":
    unittest.main()
