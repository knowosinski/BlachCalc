import json
import unittest
from decimal import Decimal
from unittest.mock import patch

from currency import (
    convert_currency,
    fetch_nbp_rates,
    parse_currency_rates,
    serialize_currency_rates,
)


class CurrencyTests(unittest.TestCase):
    def test_conversion_uses_pln_based_rates_in_both_directions(self) -> None:
        rates = {
            "PLN": Decimal("1"),
            "EUR": Decimal("4"),
            "USD": Decimal("2"),
            "GBP": Decimal("5"),
        }
        self.assertEqual(convert_currency(Decimal("10"), "EUR", "USD", rates), Decimal("20"))
        self.assertEqual(convert_currency(Decimal("10"), "USD", "EUR", rates), Decimal("5"))

    def test_missing_rate_is_reported_instead_of_returning_a_false_result(self) -> None:
        with self.assertRaisesRegex(ValueError, "Brakuje kursu"):
            convert_currency(
                Decimal("10"),
                "PLN",
                "EUR",
                {"PLN": Decimal("1")},
            )

    def test_rate_settings_round_trip_and_reject_invalid_values(self) -> None:
        rates = {"PLN": Decimal("1"), "EUR": Decimal("4.25")}
        serialized = serialize_currency_rates(rates)
        self.assertEqual(parse_currency_rates(serialized), rates)
        with self.assertRaisesRegex(ValueError, "dodatnią"):
            serialize_currency_rates({"PLN": Decimal("1"), "EUR": Decimal("0")})

    def test_nbp_response_is_parsed_and_requires_all_supported_rates(self) -> None:
        payload = json.dumps([{
            "effectiveDate": "2026-11-12",
            "rates": [
                {"code": "EUR", "mid": 4.3},
                {"code": "USD", "mid": 3.9},
                {"code": "GBP", "mid": 5.0},
            ],
        }]).encode()

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return None

            def read(self, _limit):
                return payload

        with patch("currency.urlopen", return_value=FakeResponse()):
            rates, effective_date = fetch_nbp_rates()
        self.assertEqual(effective_date, "2026-11-12")
        self.assertEqual(rates["EUR"], Decimal("4.3"))
        self.assertEqual(rates["PLN"], Decimal("1"))
