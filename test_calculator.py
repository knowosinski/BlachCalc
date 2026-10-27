import dataclasses
import unittest
from decimal import Decimal
from unittest import mock

import calculator
from calculator import (
    MAX_CALCULATION_TOTAL,
    MAX_DURATION_SECONDS,
    MAX_INPUT_AMOUNT,
    calculate_quote,
    parse_decimal,
    parse_duration,
)


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

    def test_duration_accepts_exactly_ten_years_but_not_one_second_more(self) -> None:
        self.assertEqual(parse_duration("87600", "0", "0"), MAX_DURATION_SECONDS)
        with self.assertRaisesRegex(ValueError, "10 lat"):
            parse_duration("87600", "0", "1")

    def test_duration_boundaries_and_whitespace(self) -> None:
        self.assertEqual(parse_duration("0", "0", "0"), 0)
        self.assertEqual(parse_duration(" 0 ", " 59 ", " 59 "), 3599)
        self.assertEqual(parse_duration("+1", "00", "07"), 3607)

    def test_duration_rejects_negative_and_out_of_range_parts(self) -> None:
        for parts in (("-1", "0", "0"), ("0", "-1", "0"), ("0", "0", "-1"), ("0", "0", "60")):
            with self.subTest(parts=parts), self.assertRaisesRegex(ValueError, "0–59"):
                parse_duration(*parts)

    def test_duration_rejects_non_integer_parts(self) -> None:
        for parts in (("", "0", "0"), ("0", "", "0"), ("0", "0", ""), ("1.5", "0", "0"),
                      ("1,5", "0", "0"), ("a", "0", "0"), ("0", "1e1", "0")):
            with self.subTest(parts=parts), self.assertRaisesRegex(ValueError, "pełnych godzinach"):
                parse_duration(*parts)

    def test_parse_decimal_accepts_signs_whitespace_and_both_separators(self) -> None:
        self.assertEqual(parse_decimal("  7,5 ", "Cena"), Decimal("7.5"))
        self.assertEqual(parse_decimal("-3.25", "Cena"), Decimal("-3.25"))
        self.assertEqual(parse_decimal("+0", "Cena"), Decimal("0"))
        self.assertEqual(parse_decimal(".5", "Cena"), Decimal("0.5"))
        self.assertEqual(parse_decimal("1E3", "Cena"), Decimal("1000"))

    def test_parse_decimal_rejects_empty_and_malformed_text_with_field_label(self) -> None:
        for value in ("", "   ", "abc", "1 000", "1.2.3", "1,2,3", "--1", "0x10", "12zł", "1;2"):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "Moja etykieta"):
                parse_decimal(value, "Moja etykieta")

    def test_parse_decimal_amount_and_scale_boundaries(self) -> None:
        self.assertEqual(parse_decimal("1000000000000", "Cena"), MAX_INPUT_AMOUNT)
        self.assertEqual(parse_decimal("-1000000000000", "Cena"), -MAX_INPUT_AMOUNT)
        self.assertEqual(parse_decimal("0.123456789012345678", "Cena"), Decimal("0.123456789012345678"))
        for value in ("1000000000000.01", "-1000000000001", "0.1234567890123456789", "1E13", "-Infinity", "sNaN"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_decimal(value, "Cena")

    def test_parse_decimal_length_limit_is_64_characters(self) -> None:
        self.assertEqual(parse_decimal("0." + "0" * 17 + "1", "Cena"), Decimal("1E-18"))
        with self.assertRaises(ValueError):
            parse_decimal("0." + "0" * 63, "Cena")

    def test_rounding_is_half_up_for_every_component(self) -> None:
        # 18 s * 1 zł/h / 3600 = 0.005 -> 0.01; net 0.50 * 23% = 0.115 -> 0.12
        quote = calculate_quote(Decimal("0.50"), Decimal("1"), 18, Decimal("1"), Decimal("23"))
        self.assertEqual(quote.material_cost, Decimal("0.50"))
        self.assertEqual(quote.burning_cost, Decimal("0.01"))
        self.assertEqual(quote.net_total, Decimal("0.51"))
        self.assertEqual(quote.vat_amount, Decimal("0.12"))
        self.assertEqual(quote.gross_total, Decimal("0.63"))

    def test_rounding_below_half_cent_goes_down(self) -> None:
        quote = calculate_quote(Decimal("1.004"), Decimal("1"), 17, Decimal("1"), Decimal("0"))
        self.assertEqual(quote.material_cost, Decimal("1.00"))
        self.assertEqual(quote.burning_cost, Decimal("0.00"))

    def test_gross_is_always_net_plus_vat_and_net_is_sum_of_rounded_parts(self) -> None:
        for price, weight, seconds, rate, vat in (
            ("3.333", "3", 1, "7", "8"),
            ("0.01", "0.001", 3599, "123.456", "5"),
            ("99.995", "1.005", 7, "33.33", "23"),
        ):
            with self.subTest(price=price):
                quote = calculate_quote(Decimal(price), Decimal(weight), seconds, Decimal(rate), Decimal(vat))
                self.assertEqual(quote.net_total, quote.material_cost + quote.burning_cost)
                self.assertEqual(quote.gross_total, quote.net_total + quote.vat_amount)
                for value in (quote.material_cost, quote.burning_cost, quote.vat_amount):
                    self.assertEqual(value, value.quantize(Decimal("0.01")))

    def test_vat_boundaries_zero_and_hundred_are_accepted(self) -> None:
        zero = calculate_quote(Decimal("10"), Decimal("1"), 0, Decimal("0"), Decimal("0"))
        self.assertEqual(zero.vat_amount, Decimal("0.00"))
        self.assertEqual(zero.gross_total, Decimal("10.00"))
        full = calculate_quote(Decimal("10"), Decimal("1"), 0, Decimal("0"), Decimal("100"))
        self.assertEqual(full.vat_amount, Decimal("10.00"))
        self.assertEqual(full.gross_total, Decimal("20.00"))

    def test_vat_outside_range_is_rejected(self) -> None:
        for vat in ("-0.01", "100.01", "-1"):
            with self.subTest(vat=vat), self.assertRaisesRegex(ValueError, "VAT"):
                calculate_quote(Decimal("10"), Decimal("1"), 0, Decimal("0"), Decimal(vat))

    def test_zero_price_rate_and_duration_are_valid_but_negative_values_are_not(self) -> None:
        quote = calculate_quote(Decimal("0"), Decimal("0.001"), 0, Decimal("0"), Decimal("23"))
        self.assertEqual(quote.net_total, Decimal("0.00"))
        self.assertEqual(quote.gross_total, Decimal("0.00"))
        cases = (
            ((Decimal("-1"), Decimal("1"), 0, Decimal("0"), Decimal("23")), "Cena"),
            ((Decimal("1"), Decimal("-1"), 0, Decimal("0"), Decimal("23")), "Waga"),
            ((Decimal("1"), Decimal("1"), -1, Decimal("0"), Decimal("23")), "Czas"),
            ((Decimal("1"), Decimal("1"), 0, Decimal("-1"), Decimal("23")), "Stawka"),
        )
        for args, message in cases:
            with self.subTest(message=message), self.assertRaisesRegex(ValueError, message):
                calculate_quote(*args)

    def test_calculation_rejects_non_finite_and_overscaled_inputs(self) -> None:
        for args in (
            (Decimal("NaN"), Decimal("1"), 0, Decimal("0"), Decimal("23")),
            (Decimal("1"), Decimal("Infinity"), 0, Decimal("0"), Decimal("23")),
            (Decimal("1"), Decimal("1"), 0, Decimal("1e13"), Decimal("23")),
            (Decimal("1"), Decimal("1E-19"), 0, Decimal("0"), Decimal("23")),
            (Decimal("1"), Decimal("1"), 0, Decimal("0"), Decimal("23.0000000000000000001")),
        ):
            with self.subTest(args=args), self.assertRaises(ValueError):
                calculate_quote(*args)

    def test_calculation_rejects_duration_above_ten_years(self) -> None:
        calculate_quote(Decimal("1"), Decimal("1"), MAX_DURATION_SECONDS, Decimal("1"), Decimal("0"))
        with self.assertRaisesRegex(ValueError, "10 lat"):
            calculate_quote(Decimal("1"), Decimal("1"), MAX_DURATION_SECONDS + 1, Decimal("1"), Decimal("0"))

    def test_total_above_one_trillion_is_rejected_but_exact_limit_is_allowed(self) -> None:
        quote = calculate_quote(Decimal("1000000000000"), Decimal("1"), 0, Decimal("0"), Decimal("0"))
        self.assertEqual(quote.net_total, MAX_CALCULATION_TOTAL)
        with self.assertRaisesRegex(ValueError, "Łączna wartość"):
            calculate_quote(Decimal("1000000000000"), Decimal("1.00000001"), 0, Decimal("0"), Decimal("0"))
        with self.assertRaisesRegex(ValueError, "Łączna wartość"):
            calculate_quote(Decimal("1000000000000"), Decimal("1"), 0, Decimal("0"), Decimal("1"))

    def test_huge_but_legal_inputs_do_not_lose_precision(self) -> None:
        quote = calculate_quote(
            Decimal("999999999999.999999999999999999"), Decimal("0.000000000000000001"),
            0, Decimal("0"), Decimal("0"),
        )
        self.assertEqual(quote.material_cost, Decimal("0.00"))

    def test_decimal_arithmetic_failure_is_reported_as_value_error(self) -> None:
        with mock.patch.object(calculator, "CENT", Decimal("1E-100")):
            with self.assertRaisesRegex(ValueError, "zbyt duże"):
                calculate_quote(Decimal("1"), Decimal("1"), 0, Decimal("0"), Decimal("0"))

    def test_quote_is_immutable(self) -> None:
        quote = calculate_quote(Decimal("1"), Decimal("1"), 0, Decimal("0"), Decimal("0"))
        with self.assertRaises(dataclasses.FrozenInstanceError):
            quote.net_total = Decimal("5")  # type: ignore[misc]

    def test_inputs_are_not_mutated_and_result_is_deterministic(self) -> None:
        args = (Decimal("12.345"), Decimal("1.5"), 1234, Decimal("77.77"), Decimal("23"))
        self.assertEqual(calculate_quote(*args), calculate_quote(*args))
        self.assertEqual(args[0], Decimal("12.345"))


if __name__ == "__main__":
    unittest.main()
