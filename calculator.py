from dataclasses import dataclass
from decimal import Decimal, DecimalException, InvalidOperation, ROUND_HALF_UP, localcontext


CENT = Decimal("0.01")
MAX_INPUT_AMOUNT = Decimal("1000000000000")
MAX_CALCULATION_TOTAL = Decimal("1000000000000")
MAX_DURATION_SECONDS = 10 * 365 * 24 * 60 * 60


@dataclass(frozen=True)
class Quote:
    material_cost: Decimal
    burning_cost: Decimal
    net_total: Decimal
    vat_amount: Decimal
    gross_total: Decimal


def parse_decimal(value: str, label: str) -> Decimal:
    normalized = value.strip().replace(",", ".")
    if not normalized or len(normalized) > 64:
        raise ValueError(f"Podaj prawidłową wartość pola: {label}.")
    try:
        result = Decimal(normalized)
    except InvalidOperation as error:
        raise ValueError(f"Podaj prawidłową wartość pola: {label}.") from error

    exponent = result.as_tuple().exponent
    if (
        not result.is_finite()
        or abs(result) > MAX_INPUT_AMOUNT
        or exponent < -18
        or exponent > 12
    ):
        raise ValueError(
            f"Wartość pola {label} musi być skończona, nie większa niż "
            f"{MAX_INPUT_AMOUNT} i mieć najwyżej 18 miejsc po przecinku."
        )
    return result


def parse_duration(hours: str, minutes: str, seconds: str) -> int:
    try:
        h = int(hours.strip())
        m = int(minutes.strip())
        s = int(seconds.strip())
    except ValueError as error:
        raise ValueError("Czas palenia musi być podany w pełnych godzinach, minutach i sekundach.") from error

    if h < 0 or not 0 <= m <= 59 or not 0 <= s <= 59:
        raise ValueError("Godziny nie mogą być ujemne, a minuty i sekundy muszą mieścić się w zakresie 0–59.")
    duration = h * 3600 + m * 60 + s
    if duration > MAX_DURATION_SECONDS:
        raise ValueError("Czas palenia nie może przekraczać 10 lat.")
    return duration


def calculate_quote(
    price_per_kg: Decimal,
    used_weight_kg: Decimal,
    duration_seconds: int,
    burning_rate_per_hour: Decimal,
    vat_percent: Decimal,
) -> Quote:
    if price_per_kg < 0:
        raise ValueError("Cena blachy nie może być ujemna.")
    if used_weight_kg <= 0:
        raise ValueError("Waga zużytego materiału musi być większa od zera.")
    if duration_seconds < 0:
        raise ValueError("Czas palenia nie może być ujemny.")
    if burning_rate_per_hour < 0:
        raise ValueError("Stawka palenia nie może być ujemna.")
    if not Decimal("0") <= vat_percent <= Decimal("100"):
        raise ValueError("VAT musi mieścić się w zakresie 0–100%.")

    inputs = (price_per_kg, used_weight_kg, burning_rate_per_hour, vat_percent)
    if any(
        not value.is_finite()
        or abs(value) > MAX_INPUT_AMOUNT
        or value.as_tuple().exponent < -18
        or value.as_tuple().exponent > 12
        for value in inputs
    ):
        raise ValueError(
            "Cena, masa, stawka i VAT muszą mieścić się w bezpiecznym zakresie "
            "i mieć najwyżej 18 miejsc po przecinku."
        )
    if duration_seconds > MAX_DURATION_SECONDS:
        raise ValueError("Czas palenia nie może przekraczać 10 lat.")

    try:
        with localcontext() as context:
            context.prec = 40
            material_cost = (price_per_kg * used_weight_kg).quantize(CENT, rounding=ROUND_HALF_UP)
            burning_cost = (
                Decimal(duration_seconds) * burning_rate_per_hour / Decimal(3600)
            ).quantize(CENT, rounding=ROUND_HALF_UP)
            net_total = material_cost + burning_cost
            vat_amount = (net_total * vat_percent / Decimal(100)).quantize(CENT, rounding=ROUND_HALF_UP)
            gross_total = net_total + vat_amount
    except DecimalException as error:
        raise ValueError("Wartości są zbyt duże, aby obliczyć bezpieczną wycenę.") from error

    if any(value > MAX_CALCULATION_TOTAL for value in (net_total, vat_amount, gross_total)):
        raise ValueError("Łączna wartość kalkulacji nie może przekraczać 1 000 000 000 000 zł.")
    return Quote(
        material_cost=material_cost,
        burning_cost=burning_cost,
        net_total=net_total,
        vat_amount=vat_amount,
        gross_total=gross_total,
    )
