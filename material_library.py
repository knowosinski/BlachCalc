from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation
from typing import Any


CATEGORIES = ("Blacha", "Rura", "Profil", "Inne")


def load_materials(library_raw: str | None, legacy_raw: str | None = None) -> list[dict[str, str]]:
    try:
        saved: Any = json.loads(library_raw or "")
    except ValueError:
        saved = None
    materials: list[dict[str, str]] = []
    if isinstance(saved, list):
        for item in saved:
            if not isinstance(item, dict):
                continue
            name = " ".join(str(item.get("name", "")).split())
            category = " ".join(str(item.get("category", "")).split()) or "Blacha"
            thickness = str(item.get("thickness_mm", "")).strip()
            price = str(item.get("price_per_kg", "")).strip()
            if name:
                materials.append({
                    "category": category,
                    "name": name,
                    "thickness_mm": thickness,
                    "price_per_kg": price,
                })
    if materials:
        return materials
    legacy_names = {
        " ".join(line.split()).casefold(): " ".join(line.split())
        for line in (legacy_raw or "").splitlines()
        if line.strip()
    }
    return [
        {"category": "Blacha", "name": name, "thickness_mm": "", "price_per_kg": ""}
        for name in legacy_names.values()
    ]


def serialize_materials(materials: list[dict[str, str]]) -> str:
    normalized: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for item in materials:
        category = " ".join(str(item.get("category", "")).split()) or "Inne"
        name = " ".join(str(item.get("name", "")).split())
        thickness = str(item.get("thickness_mm", "")).strip()
        price = str(item.get("price_per_kg", "")).strip()
        if not name or (category.casefold(), name.casefold()) in seen:
            continue
        if thickness:
            try:
                thickness_value = Decimal(thickness.replace(",", "."))
                if not thickness_value.is_finite() or thickness_value <= 0:
                    raise ValueError("Grubość materiału musi być większa od zera.")
            except InvalidOperation as error:
                raise ValueError("Podaj prawidłową grubość materiału.") from error
        if price:
            try:
                value = Decimal(price.replace(",", "."))
            except InvalidOperation as error:
                raise ValueError("Podaj prawidłową cenę materiału za kg.") from error
            if not value.is_finite() or value < 0:
                raise ValueError("Cena materiału za kg musi być nieujemną liczbą.")
        normalized.append({
            "category": category,
            "name": name,
            "thickness_mm": thickness,
            "price_per_kg": price,
        })
        seen.add((category.casefold(), name.casefold()))
    return json.dumps(normalized, ensure_ascii=False)


def material_label(item: dict[str, str]) -> str:
    return item["name"]
