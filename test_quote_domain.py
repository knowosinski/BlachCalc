import unittest
from decimal import Decimal
from types import MappingProxyType

from quote_domain import (
    CALCULATION_MODES,
    apply_item_batch_share,
    calculate_item_line_amounts,
    format_pln,
    is_pending_full_batch,
    item_geometry_parts,
    line_totals,
    parse_hole_diameters,
    split_full_batch,
)


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

    def test_format_pln_handles_zero_negative_and_decimal_inputs(self) -> None:
        self.assertEqual(format_pln("0"), "0,00 zł")
        self.assertEqual(format_pln(Decimal("-1234.5")), "-1 234,50 zł")
        self.assertEqual(format_pln(Decimal("999.999")), "1 000,00 zł")
        self.assertEqual(format_pln("1000000000000"), "1 000 000 000 000,00 zł")
        self.assertEqual(format_pln("12"), "12,00 zł")

    def test_format_pln_never_leaves_dot_or_comma_thousand_separators(self) -> None:
        formatted = format_pln("1234567.89")
        self.assertNotIn(".", formatted)
        self.assertNotIn(",,", formatted)
        self.assertEqual(formatted.count(","), 1)

    def test_format_pln_rejects_garbage(self) -> None:
        with self.assertRaises(Exception):
            format_pln("abc")

    def test_line_totals_default_to_per_piece_and_accept_text_quantity(self) -> None:
        self.assertEqual(
            line_totals({"quantity": "4", "unit_net": 2.5, "unit_vat": "0.575"}),
            (Decimal("10.0"), Decimal("2.300"), Decimal("12.300")),
        )

    def test_line_totals_ignore_stored_unit_gross_and_use_net_plus_vat(self) -> None:
        net, vat, gross = line_totals(
            {"quantity": 2, "unit_net": "10", "unit_vat": "2", "unit_gross": "999"}
        )
        self.assertEqual((net, vat, gross), (Decimal("20"), Decimal("4"), Decimal("24")))

    def test_line_totals_do_not_round_so_sum_of_lines_stays_exact(self) -> None:
        net, vat, gross = line_totals({"quantity": 3, "unit_net": "0.333", "unit_vat": "0.077"})
        self.assertEqual(net, Decimal("0.999"))
        self.assertEqual(gross, net + vat)

    def test_line_totals_reject_invalid_quantities(self) -> None:
        base = {"unit_net": "1", "unit_vat": "0"}
        for quantity in (0, -3, "0", "abc", None, "", [], float("nan")):
            with self.subTest(quantity=quantity), self.assertRaises(ValueError):
                line_totals({**base, "quantity": quantity})

    def test_line_totals_reject_missing_keys_and_non_finite_amounts(self) -> None:
        for item in (
            {},
            {"quantity": 1, "unit_vat": "1"},
            {"quantity": 1, "unit_net": "1"},
            {"unit_net": "1", "unit_vat": "1"},
            {"quantity": 1, "unit_net": "Infinity", "unit_vat": "1"},
            {"quantity": 1, "unit_net": "1", "unit_vat": "-Infinity"},
            {"quantity": 1, "unit_net": None, "unit_vat": "1"},
        ):
            with self.subTest(item=item), self.assertRaisesRegex(ValueError, "nieprawidłowe kwoty"):
                line_totals(item)

    def test_line_totals_reject_unknown_calculation_mode(self) -> None:
        with self.assertRaisesRegex(ValueError, "Nieznany sposób"):
            line_totals({"quantity": 1, "unit_net": "1", "unit_vat": "0", "calculation_mode": "PER_PIECE"})

    def test_whole_order_mode_still_requires_positive_quantity(self) -> None:
        with self.assertRaisesRegex(ValueError, "Ilość"):
            calculate_item_line_amounts(
                Decimal("1"), Decimal("0"), Decimal("1"), 0, "whole_order"
            )

    def test_calculate_item_line_amounts_uses_supplied_gross_without_recomputing(self) -> None:
        self.assertEqual(
            calculate_item_line_amounts(Decimal("1"), Decimal("2"), Decimal("50"), 2, "per_piece"),
            (Decimal("2"), Decimal("4"), Decimal("100")),
        )

    def test_calculation_modes_constant_lists_exactly_the_supported_modes(self) -> None:
        self.assertEqual(CALCULATION_MODES, {"per_piece", "whole_order", "full_batch"})

    def test_hole_diameters_are_normalized(self) -> None:
        self.assertEqual(parse_hole_diameters("10, Ø12.50;  8"), "10, 12.5, 8")
        self.assertEqual(parse_hole_diameters(""), "")
        with self.assertRaises(ValueError):
            parse_hole_diameters("abc")
        with self.assertRaises(ValueError):
            parse_hole_diameters("0")

    def test_item_geometry_parts_list_dimensions_and_holes(self) -> None:
        self.assertEqual(
            item_geometry_parts({"dimensions": "200 x 100", "hole_diameters": "10, 12"}),
            ["Wymiary: 200 x 100 mm", "Otwory: Ø10, Ø12"],
        )
        self.assertEqual(item_geometry_parts({}), [])

    def test_full_batch_weight_and_time_are_split_by_quantity_and_sum_exactly(self) -> None:
        items = [{"quantity": 1}, {"quantity": 2}, {"quantity": 3}]
        shares = split_full_batch(items, Decimal("10"), 1000)
        self.assertEqual(sum(weight for weight, _ in shares), Decimal("10"))
        self.assertEqual(sum(seconds for _, seconds in shares), 1000)
        self.assertEqual(shares[0], (Decimal("1.667"), 167))

    def test_apply_item_batch_share_prices_full_batch_item_once(self) -> None:
        item = {
            "price_per_kg": "5", "burning_rate_per_hour": "360", "vat_percent": "23",
            "duration_seconds": 0, "used_weight_kg": "0", "quantity": 4, "calculation_mode": "full_batch",
        }
        self.assertTrue(is_pending_full_batch(item))
        priced = apply_item_batch_share(item, Decimal("2"), 3600)
        self.assertFalse(is_pending_full_batch(priced))
        self.assertEqual(priced["material_cost"], "10.00")
        self.assertEqual(priced["line_net"], "370.00")

    def test_line_totals_accept_any_mapping(self) -> None:
        item = MappingProxyType({"quantity": 2, "unit_net": "1.5", "unit_vat": "0.5"})
        self.assertEqual(line_totals(item)[2], Decimal("4.0"))


if __name__ == "__main__":
    unittest.main()
