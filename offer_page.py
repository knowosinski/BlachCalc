"""Edytowalna treść drugiej strony oferty PDF (warunki, reklamacje, cennik palet, kontakt)."""
from __future__ import annotations

import copy
import json
from typing import Any

SETTING_KEY = "offer_page2"

DEFAULT_OFFER_PAGE: dict[str, Any] = {
    "terms": {
        "title": "Dodatkowe warunki:",
        "items": [
            "O ile nie zaznaczono inaczej, oferta dotyczy obróbki cięcia laserem i gięcia. Usługi dodatkowe do indywidualnego ustalenia.",
            "Oferta cenowa nie zawiera usuwania zadziorów, nadpaleń, nagaru powstających podczas cięcia laserem w wyniku odbicia wiązki od rusztów.",
            "Zastrzegamy możliwość wystąpienia zniekształcenia otworów z uwagi na ich położenie przy linii gięcia, odcisków od narzędzi prasy krawędziowej lub zarysowań powstałych od rusztów lasera podczas cięcia.",
            "Nie zapewniamy płaskości powierzchni.",
            "Termin realizacji liczony jest od daty złożenia zamówienia wraz z pełną dokumentacją techniczną, a w przypadku przedpłaty lub przeterminowanych płatności, również od daty wpływu pieniędzy na konto.",
            "Wykonanie usług cięcia laserem i/lub gięcia na materiale powierzonym wymaga wysokiej jakości co do jego powierzchni, prostolinijności, płaskości i czystości powierzchni (blachy/formatki bez rdzy, zarysowań, pofalowań) oraz zgodności gatunkowej - zastrzegamy sobie możliwość odstąpienia od realizacji zlecenia jeżeli powierzony materiał jest złej jakości.",
            "Odbiór materiałów odbywa się na podstawie wcześniejszej awizacji w dniach roboczych w godzinach 8:00 - 15:00.",
            "Przyjęcie zamówienia do realizacji wymaga złożenia formalnego zamówienia i potwierdzenia wszystkich wymaganych szczegółów technicznych.",
            "Ceny są skalkulowane dla ilości podanych w ofercie loco magazyn IZO-TECHNIKA. Zmiana ilości lub pozycji może spowodować zmianę ceny.",
            "Cena nie zawiera opłaty za palety transportowe. Palety zostaną zafakturowane zgodnie z dokumentem WZ dla każdego zamówienia. W przypadku zwrotu w terminie do 30 dni od daty wystawienia faktury - zostanie wystawiona korekta.",
            "Tolerancja gięcia blach wg DIN ISO 2768 – klasa c.",
            "Tolerancja cięcia laserem wg PN-EN ISO 9013 – klasa 1.",
            "Zapewniamy jakość wykonania po wierzchniej stronie detalu.",
        ],
    },
    "claims": {
        "title": "Odbiór i reklamacje towaru",
        "items": [
            "Nabywca jest zobowiązany do zbadania towaru pod względem ilościowym i jakościowym natychmiast po jego otrzymaniu oraz do niezwłocznego powiadomienia dostawcy o wykrytych w trakcie tego badania niezgodnościach. Termin powiadomienia dostawcy o niezgodnościach określa się na maksymalnie 1 dzień.",
            "Reklamacje dotyczące jakości towaru/usługi muszą być zgłoszone pisemnie niezwłocznie, lecz nie później niż 2 dni od daty odbioru.",
            "Reklamacje dotyczące ilości towaru muszą być zgłoszone pisemnie niezwłocznie, lecz nie później niż jeden dzień od daty odbioru.",
            "Reklamacje będą rozpatrywane tylko co do towarów w stanie takim jak zostały dostarczone, nieprzetworzonych i nieuszkodzonych.",
        ],
    },
    "pallets": {
        "title": "Cennik palet:",
        "items": [
            "Euro – 30 zł netto,",
            "A (1000x2000) – 90 zł netto",
            "B (1250x2500) – 180 zł netto",
            "C (1500x3000) – 200 zł netto",
        ],
    },
    "contact": {
        "title": "Dane teleadresowe:",
        "person": "Katarzyna Iłczyk",
        "phone": "+48 786 300 750",
        "email": "biuro@izotechnika.com.pl",
    },
}

LIST_SECTIONS = ("terms", "claims", "pallets")
CONTACT_FIELDS = ("person", "phone", "email")


def default_offer_page() -> dict[str, Any]:
    return copy.deepcopy(DEFAULT_OFFER_PAGE)


def parse_offer_page(raw: str | None) -> dict[str, Any]:
    """Zwraca treść strony; brakujące lub błędne części zastępuje domyślnymi."""
    page = default_offer_page()
    if not raw or not raw.strip():
        return page
    try:
        saved = json.loads(raw)
    except ValueError:
        return page
    if not isinstance(saved, dict):
        return page
    for key in LIST_SECTIONS:
        section = saved.get(key)
        if not isinstance(section, dict):
            continue
        title = section.get("title")
        items = section.get("items")
        if isinstance(title, str):
            page[key]["title"] = title.strip()
        if isinstance(items, list):
            page[key]["items"] = [" ".join(str(item).split()) for item in items if str(item).strip()]
    contact = saved.get("contact")
    if isinstance(contact, dict):
        if isinstance(contact.get("title"), str):
            page["contact"]["title"] = contact["title"].strip()
        for field in CONTACT_FIELDS:
            if isinstance(contact.get(field), str):
                page["contact"][field] = contact[field].strip()
    return page


def serialize_offer_page(page: dict[str, Any]) -> str:
    """Zapisuje tylko różnice względem domyślnej treści (pusty tekst = domyślna)."""
    if page == DEFAULT_OFFER_PAGE:
        return ""
    return json.dumps(page, ensure_ascii=False)
