from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation
from urllib.request import Request, urlopen
from typing import Any


CURRENCIES = {
    "PLN": "złoty polski",
    "EUR": "euro",
    "USD": "dolar amerykański",
    "GBP": "funt brytyjski",
}
NBP_RATES_URL = "https://api.nbp.pl/api/exchangerates/tables/A/?format=json"


def parse_currency_rates(raw: str | None) -> dict[str, Decimal]:
    rates: dict[str, Decimal] = {"PLN": Decimal("1")}
    if not raw:
        return rates
    try:
        saved = json.loads(raw)
    except (TypeError, ValueError):
        return rates
    if not isinstance(saved, dict):
        return rates
    for code in CURRENCIES:
        if code == "PLN":
            continue
        try:
            rate = Decimal(str(saved.get(code, "")))
        except InvalidOperation:
            continue
        if rate.is_finite() and rate > 0:
            rates[code] = rate
    return rates


def serialize_currency_rates(rates: dict[str, Decimal]) -> str:
    normalized = {"PLN": "1"}
    for code in CURRENCIES:
        if code == "PLN" or code not in rates:
            continue
        rate = rates[code]
        if not rate.is_finite() or rate <= 0:
            raise ValueError(f"Kurs {code} musi być dodatnią, skończoną liczbą.")
        normalized[code] = str(rate)
    return json.dumps(normalized, sort_keys=True)


def convert_currency(
    amount: Decimal,
    source: str,
    target: str,
    rates_to_pln: dict[str, Decimal],
) -> Decimal:
    if source not in CURRENCIES or target not in CURRENCIES:
        raise ValueError("Wybierz obsługiwaną walutę.")
    if not amount.is_finite():
        raise ValueError("Kwota musi być liczbą skończoną.")
    if source not in rates_to_pln or target not in rates_to_pln:
        raise ValueError("Brakuje kursu. Pobierz aktualne kursy z tabeli NBP.")
    return amount * rates_to_pln[source] / rates_to_pln[target]


def fetch_nbp_rates() -> tuple[dict[str, Decimal], str]:
    request = Request(
        NBP_RATES_URL,
        headers={"Accept": "application/json", "User-Agent": "BlachCalc"},
    )
    with urlopen(request, timeout=8) as response:
        payload = response.read(512 * 1024 + 1)
    if len(payload) > 512 * 1024:
        raise ValueError("Odpowiedź serwera NBP jest zbyt duża.")
    try:
        data: Any = json.loads(payload)
    except (UnicodeDecodeError, ValueError) as error:
        raise ValueError("Serwer NBP zwrócił nieprawidłowe dane.") from error
    if not isinstance(data, list) or not data or not isinstance(data[0], dict):
        raise ValueError("Serwer NBP nie zwrócił tabeli kursów.")
    table = data[0]
    raw_rates = table.get("rates")
    if not isinstance(raw_rates, list):
        raise ValueError("Tabela NBP nie zawiera kursów.")
    rates = {"PLN": Decimal("1")}
    for entry in raw_rates:
        if not isinstance(entry, dict):
            continue
        code = entry.get("code")
        if code not in CURRENCIES or code == "PLN":
            continue
        try:
            rate = Decimal(str(entry.get("mid", "")))
        except InvalidOperation:
            continue
        if rate.is_finite() and rate > 0:
            rates[code] = rate
    missing = set(CURRENCIES) - rates.keys()
    if missing:
        raise ValueError(
            "Tabela NBP nie zawiera kursów: " + ", ".join(sorted(missing)) + "."
        )
    effective_date = str(table.get("effectiveDate", ""))
    if not effective_date:
        raise ValueError("Tabela NBP nie zawiera daty kursów.")
    return rates, effective_date
