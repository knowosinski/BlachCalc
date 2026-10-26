from collections.abc import Mapping
from decimal import Decimal, DecimalException
from typing import Any


CALCULATION_MODES = frozenset({"per_piece", "whole_order"})
OPERATIONS = {
    "cutting": "Cięcie",
    "bending": "Gięcie",
    "cutting_bending": "Cięcie + gięcie",
}
DEFAULT_OPERATION = "cutting"


def format_pln(value: Decimal | str) -> str:
    formatted = f"{Decimal(value):,.2f}"
    return f"{formatted.replace(',', ' ').replace('.', ',')} zł"


def calculate_item_line_amounts(
    unit_net: Decimal,
    unit_vat: Decimal,
    unit_gross: Decimal,
    quantity: int,
    calculation_mode: str,
) -> tuple[Decimal, Decimal, Decimal]:
    if calculation_mode not in CALCULATION_MODES:
        raise ValueError("Nieznany sposób kalkulacji pozycji.")
    if quantity < 1:
        raise ValueError("Ilość musi być większa od zera.")

    multiplier = 1 if calculation_mode == "whole_order" else quantity
    return unit_net * multiplier, unit_vat * multiplier, unit_gross * multiplier


def line_totals(item: Mapping[str, Any]) -> tuple[Decimal, Decimal, Decimal]:
    try:
        quantity = int(item["quantity"])
        calculation_mode = str(item.get("calculation_mode", "per_piece"))
        unit_net = Decimal(str(item["unit_net"]))
        unit_vat = Decimal(str(item["unit_vat"]))
        unit_gross = unit_net + unit_vat
    except (DecimalException, KeyError, TypeError, ValueError) as error:
        raise ValueError("Pozycja zawiera nieprawidłowe kwoty lub ilość.") from error

    if not unit_net.is_finite() or not unit_vat.is_finite():
        raise ValueError("Pozycja zawiera nieprawidłowe kwoty lub ilość.")

    return calculate_item_line_amounts(
        unit_net,
        unit_vat,
        unit_gross,
        quantity,
        calculation_mode,
    )
