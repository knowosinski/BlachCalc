from collections.abc import Mapping
from decimal import Decimal, DecimalException, ROUND_HALF_UP
from typing import Any


from calculator import Quote, calculate_quote, parse_decimal
from currency import convert_currency, parse_currency_rates


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
BENDING_OPERATIONS = frozenset({"bending", "cutting_bending"})
BENDING_COST_PER_BEND = Decimal("3.00")
DEFAULT_OPERATION = "cutting"
PACKAGING_MATERIAL = "Opakowanie"
PACKAGING_PREFIX = "Opakowanie: "
PACKAGING_OPTIONS = {
    "pallet_a": "Paleta A",
    "pallet_b": "Paleta B",
    "pallet_c": "Paleta C",
    "carton": "Karton",
    "foil": "Folia",
}
PACKAGING_DEFAULT_PRICES = {
    "pallet_a": "90",
    "pallet_b": "180",
    "pallet_c": "200",
    "carton": "0",
    "foil": "0",
}


def packaging_setting_key(option: str) -> str:
    return f"packaging_price_{option}"


def is_packaging_item(item: Mapping[str, Any]) -> bool:
    return item.get("material") == PACKAGING_MATERIAL and str(item.get("element_name", "")).startswith(PACKAGING_PREFIX)


def packaging_option_from_item(item: Mapping[str, Any]) -> str | None:
    name = str(item.get("element_name", ""))[len(PACKAGING_PREFIX):]
    return next((key for key, label in PACKAGING_OPTIONS.items() if label == name), None)


def build_packaging_item(option: str, price: Decimal, vat: Decimal) -> dict[str, Any]:
    """Opakowanie zapisywane jako pozycja partii: 1 szt. w cenie ustawionej dla danego opakowania."""
    if option not in PACKAGING_OPTIONS:
        raise ValueError("Wybierz prawidłowe opakowanie.")
    burning_rate = Decimal("0")
    quote = calculate_quote(price, Decimal("1"), 0, burning_rate, vat)
    amounts = calculate_item_amounts(quote, 0, 1, "whole_order", vat)
    return {
        "element_name": PACKAGING_PREFIX + PACKAGING_OPTIONS[option],
        "material": PACKAGING_MATERIAL,
        "thickness_mm": "",
        "dimensions": "",
        "hole_diameters": "",
        "calculation_mode": "whole_order",
        "operation": DEFAULT_OPERATION,
        "bending_count": 0,
        "quantity": 1,
        "price_per_kg": str(price),
        "used_weight_kg": "1",
        "duration_seconds": 0,
        "burning_rate_per_hour": str(burning_rate),
        "vat_percent": str(vat),
        "material_cost": str(quote.material_cost),
        "burning_cost": str(quote.burning_cost),
        **{key: str(value) for key, value in amounts.items()},
        "preview_image": None,
        "preview_image_name": "",
    }


def format_currency(value: Decimal | str, currency: str = "PLN") -> str:
    formatted = f"{Decimal(value):,.2f}"
    amount = formatted.replace(",", " ").replace(".", ",")
    if currency == "PLN":
        return f"{amount} zł"
    return f"{amount} {currency}"


def format_pln(value: Decimal | str) -> str:
    return format_currency(value)


def is_batch_mode(calculation_mode: str) -> bool:
    return calculation_mode in {"whole_order", "full_batch"}


def calculate_item_amounts(
    quote: Quote,
    bending_count: int,
    quantity: int,
    calculation_mode: str,
    vat_percent: Decimal,
    bending_unit_price: Decimal = BENDING_COST_PER_BEND,
) -> dict[str, Decimal]:
    if not 0 <= bending_count <= 1_000_000:
        raise ValueError("Ilość gięć musi mieścić się w zakresie od 0 do 1 000 000.")
    if not bending_unit_price.is_finite() or bending_unit_price < 0:
        raise ValueError("Cena za jedno gięcie musi być liczbą nieujemną.")
    if calculation_mode not in CALCULATION_MODES:
        raise ValueError("Nieznany sposób kalkulacji pozycji.")
    if quantity < 1:
        raise ValueError("Ilość musi być większa od zera.")

    bending_cost = bending_unit_price * bending_count * quantity
    amount_bending_cost = (
        bending_unit_price * bending_count
        if calculation_mode == "per_piece"
        else bending_cost
    )
    unit_net = quote.net_total + amount_bending_cost
    unit_vat = (unit_net * vat_percent / Decimal("100")).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP,
    )
    unit_gross = unit_net + unit_vat
    line_net, line_vat, line_gross = calculate_item_line_amounts(
        unit_net,
        unit_vat,
        unit_gross,
        quantity,
        calculation_mode,
    )
    return {
        "bending_cost": bending_cost,
        "unit_net": unit_net,
        "unit_vat": unit_vat,
        "unit_gross": unit_gross,
        "line_net": line_net,
        "line_vat": line_vat,
        "line_gross": line_gross,
    }


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
    amounts = calculate_item_amounts(
        quote,
        int(item.get("bending_count", 0)),
        int(item["quantity"]),
        str(item["calculation_mode"]),
        parse_decimal(str(item["vat_percent"]), "VAT"),
        parse_decimal(str(item.get("bending_unit_price") or BENDING_COST_PER_BEND), "Cena za gięcie"),
    )
    return {
        **item,
        "used_weight_kg": str(weight),
        "duration_seconds": duration_seconds,
        "material_cost": str(quote.material_cost),
        "burning_cost": str(quote.burning_cost),
        **{key: str(value) for key, value in amounts.items()},
    }


def recalculate_estimate_for_settings(
    estimate: Mapping[str, Any],
    settings: Mapping[str, Any],
) -> dict[str, Any]:
    header = dict(estimate["header"])
    source_currency = str(settings.get("default_currency") or header.get("currency", "PLN"))
    quote_currency = str(header.get("currency", "PLN"))
    rates = parse_currency_rates(settings.get("currency_rates"))

    def setting_amount(key: str, label: str) -> Decimal:
        amount = parse_decimal(str(settings.get(key, "")), label)
        if source_currency != quote_currency:
            return convert_currency(
                amount,
                source_currency,
                quote_currency,
                rates,
            ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        return amount

    price_per_kg = setting_amount("price_per_kg", "Cena materiału za kg")
    burning_rate = setting_amount("burning_rate_per_hour", "Stawka palenia")
    vat = parse_decimal(str(settings.get("vat_percent", "")), "VAT")
    bending_unit_price = setting_amount("bending_price", "Cena za gięcie")

    items: list[dict[str, Any]] = []
    for original_item in estimate["items"]:
        item = dict(original_item)
        if is_packaging_item(item):
            option = packaging_option_from_item(item)
            if option is None:
                raise ValueError("Nie można rozpoznać rodzaju opakowania w wycenie.")
            item = {
                **item,
                **build_packaging_item(
                    option,
                    setting_amount(packaging_setting_key(option), "Cena opakowania"),
                    vat,
                ),
            }
        else:
            item_price = price_per_kg
            quote = calculate_quote(
                item_price,
                parse_decimal(str(item["used_weight_kg"]), "Masa materiału"),
                int(item["duration_seconds"]),
                burning_rate,
                vat,
                allow_zero_weight=is_pending_full_batch(item),
            )
            amounts = calculate_item_amounts(
                quote,
                int(item.get("bending_count", 0)),
                int(item["quantity"]),
                str(item.get("calculation_mode", "per_piece")),
                vat,
                bending_unit_price,
            )
            item = {
                **item,
                "price_per_kg": str(item_price),
                "burning_rate_per_hour": str(burning_rate),
                "vat_percent": str(vat),
                "bending_unit_price": str(bending_unit_price),
                "material_cost": str(quote.material_cost),
                "burning_cost": str(quote.burning_cost),
                **{key: str(value) for key, value in amounts.items()},
            }
        items.append(item)

    header["net_total"] = str(sum((Decimal(item["line_net"]) for item in items), Decimal("0")))
    header["vat_amount"] = str(sum((Decimal(item["line_vat"]) for item in items), Decimal("0")))
    header["gross_total"] = str(sum((Decimal(item["line_gross"]) for item in items), Decimal("0")))
    return {"header": header, "items": items}


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
