from collections.abc import Mapping
from decimal import Decimal, DecimalException
from typing import Any


from calculator import calculate_quote, parse_decimal


CALCULATION_MODES = frozenset({"per_piece", "whole_order", "full_batch"})
CALCULATION_MODE_LABELS = {
    "per_piece": "Sztuka",
    "whole_order": "Partia",
    "full_batch": "Pełna partia",
}
MAX_DIMENSIONS_LENGTH = 120
MAX_HOLE_DIAMETERS_LENGTH = 200
OPERATIONS = {
    "cutting": "Cięcie",
    "bending": "Gięcie",
    "cutting_bending": "Cięcie + gięcie",
}
DEFAULT_OPERATION = "cutting"


def format_pln(value: Decimal | str) -> str:
    formatted = f"{Decimal(value):,.2f}"
    return f"{formatted.replace(',', ' ').replace('.', ',')} zł"


def is_batch_mode(calculation_mode: str) -> bool:
    return calculation_mode in {"whole_order", "full_batch"}


def parse_hole_diameters(text: str) -> str:
    """Normalizuje listę średnic otworów (fi) rozdzielonych przecinkami lub średnikami."""
    values: list[str] = []
    for part in text.replace(";", ",").split(","):
        part = part.strip().removeprefix("Ø").removeprefix("ø").removeprefix("fi").strip()
        if not part:
            continue
        diameter = parse_decimal(part, "Średnica otworu (fi)")
        if diameter <= 0:
            raise ValueError("Średnica otworu (fi) musi być większa od zera.")
        values.append(format(diameter.normalize(), "f"))
    result = ", ".join(values)
    if len(result) > MAX_HOLE_DIAMETERS_LENGTH:
        raise ValueError("Lista średnic otworów jest zbyt długa.")
    return result


def item_geometry_parts(item: Mapping[str, Any]) -> list[str]:
    parts: list[str] = []
    dimensions = str(item.get("dimensions", "") or "").strip()
    if dimensions:
        parts.append(f"Wymiary: {dimensions} mm")
    holes = str(item.get("hole_diameters", "") or "").strip()
    if holes:
        parts.append("Otwory: " + ", ".join(f"Ø{value.strip()}" for value in holes.split(",")))
    return parts


def is_pending_full_batch(item: Mapping[str, Any]) -> bool:
    """Pozycja pełnej partii, której masa i czas zostaną podane przy zatwierdzaniu wyceny."""
    try:
        return item.get("calculation_mode") == "full_batch" and Decimal(str(item["used_weight_kg"])) <= 0
    except (DecimalException, KeyError, TypeError):
        return False


def split_full_batch(
    items: list[Mapping[str, Any]],
    total_weight: Decimal,
    total_seconds: int,
) -> list[tuple[Decimal, int]]:
    """Dzieli masę i czas palenia pełnej partii na pozycje proporcjonalnie do ilości sztuk."""
    quantities = [Decimal(int(item["quantity"])) for item in items]
    total_quantity = sum(quantities)
    shares: list[tuple[Decimal, int]] = []
    allocated_weight = Decimal(0)
    allocated_seconds = 0
    for index, quantity in enumerate(quantities):
        if index == len(quantities) - 1:
            weight = total_weight - allocated_weight
            seconds = total_seconds - allocated_seconds
        else:
            weight = (total_weight * quantity / total_quantity).quantize(Decimal("0.001"))
            seconds = int((Decimal(total_seconds) * quantity / total_quantity).to_integral_value())
        shares.append((weight, seconds))
        allocated_weight += weight
        allocated_seconds += seconds
    return shares


def apply_item_batch_share(item: Mapping[str, Any], weight: Decimal, duration_seconds: int) -> dict[str, Any]:
    """Przelicza pozycję pełnej partii po przypisaniu jej masy i czasu palenia."""
    quote = calculate_quote(
        parse_decimal(str(item["price_per_kg"]), "Cena materiału za kg"),
        weight,
        duration_seconds,
        parse_decimal(str(item["burning_rate_per_hour"]), "Stawka palenia"),
        parse_decimal(str(item["vat_percent"]), "VAT"),
        allow_zero_weight=True,
    )
    line_net, line_vat, line_gross = calculate_item_line_amounts(
        quote.net_total,
        quote.vat_amount,
        quote.gross_total,
        int(item["quantity"]),
        str(item["calculation_mode"]),
    )
    return {
        **item,
        "used_weight_kg": str(weight),
        "duration_seconds": duration_seconds,
        "material_cost": str(quote.material_cost),
        "burning_cost": str(quote.burning_cost),
        "unit_net": str(quote.net_total),
        "unit_vat": str(quote.vat_amount),
        "unit_gross": str(quote.gross_total),
        "line_net": str(line_net),
        "line_vat": str(line_vat),
        "line_gross": str(line_gross),
    }

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

    multiplier = 1 if is_batch_mode(calculation_mode) else quantity
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
