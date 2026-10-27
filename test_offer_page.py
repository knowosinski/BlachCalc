import json
import unittest

from offer_page import (
    CONTACT_FIELDS,
    DEFAULT_OFFER_PAGE,
    LIST_SECTIONS,
    SETTING_KEY,
    default_offer_page,
    parse_offer_page,
    serialize_offer_page,
)


class DefaultOfferPageTests(unittest.TestCase):
    def test_default_page_has_all_sections_and_non_empty_texts(self) -> None:
        page = default_offer_page()
        for key in LIST_SECTIONS:
            self.assertTrue(page[key]["title"])
            self.assertTrue(page[key]["items"])
            self.assertTrue(all(item.strip() for item in page[key]["items"]))
        for field in CONTACT_FIELDS:
            self.assertTrue(page["contact"][field])
        self.assertEqual(page["custom_sections"], [])
        self.assertEqual(SETTING_KEY, "offer_page2")

    def test_default_page_returns_independent_deep_copies(self) -> None:
        page = default_offer_page()
        page["terms"]["items"].append("dopisek")
        page["contacts"][0]["person"] = "Zmieniony"
        page["custom_sections"].append({"title": "x", "text": "y"})
        fresh = default_offer_page()
        self.assertEqual(fresh, DEFAULT_OFFER_PAGE)
        self.assertNotIn("dopisek", DEFAULT_OFFER_PAGE["terms"]["items"])

    def test_default_contacts_list_mirrors_single_contact(self) -> None:
        page = default_offer_page()
        self.assertEqual(page["contacts"], [{f: page["contact"][f] for f in CONTACT_FIELDS}])


class ParseOfferPageTests(unittest.TestCase):
    def test_missing_empty_and_blank_values_return_defaults(self) -> None:
        for raw in (None, "", "   ", "\n\t"):
            with self.subTest(raw=raw):
                self.assertEqual(parse_offer_page(raw), DEFAULT_OFFER_PAGE)

    def test_corrupt_or_non_object_json_returns_defaults(self) -> None:
        for raw in ("{", "not json", "[]", '"text"', "123", "null", "true", '{"terms": '):
            with self.subTest(raw=raw):
                self.assertEqual(parse_offer_page(raw), DEFAULT_OFFER_PAGE)

    def test_empty_object_keeps_every_default_section(self) -> None:
        self.assertEqual(parse_offer_page("{}"), DEFAULT_OFFER_PAGE)

    def test_saved_list_section_overrides_title_and_items(self) -> None:
        raw = json.dumps({"terms": {"title": "  Warunki  ", "items": ["  Pierwszy   punkt ", "Drugi"]}})
        page = parse_offer_page(raw)
        self.assertEqual(page["terms"]["title"], "Warunki")
        self.assertEqual(page["terms"]["items"], ["Pierwszy punkt", "Drugi"])
        self.assertEqual(page["claims"], DEFAULT_OFFER_PAGE["claims"])

    def test_blank_items_are_dropped_and_non_string_items_are_stringified(self) -> None:
        raw = json.dumps({"pallets": {"items": ["", "   ", "\n", 5, None, "Euro\n  30 zł"]}})
        items = parse_offer_page(raw)["pallets"]["items"]
        self.assertEqual(items, ["5", "None", "Euro 30 zł"])

    def test_explicit_empty_items_list_removes_the_section_content(self) -> None:
        page = parse_offer_page(json.dumps({"claims": {"items": []}}))
        self.assertEqual(page["claims"]["items"], [])
        self.assertEqual(page["claims"]["title"], DEFAULT_OFFER_PAGE["claims"]["title"])

    def test_invalid_section_types_fall_back_to_defaults(self) -> None:
        raw = json.dumps({"terms": "tekst", "claims": [1, 2], "pallets": {"title": 7, "items": "nie lista"}})
        self.assertEqual(parse_offer_page(raw), DEFAULT_OFFER_PAGE)

    def test_empty_title_string_is_respected(self) -> None:
        page = parse_offer_page(json.dumps({"terms": {"title": "   "}}))
        self.assertEqual(page["terms"]["title"], "")

    def test_polish_characters_and_markup_like_text_survive_unchanged(self) -> None:
        text = "Zażółć gęślą jaźń <b>&amp;</b> '; DROP TABLE x;--"
        page = parse_offer_page(json.dumps({"terms": {"items": [text]}}))
        self.assertEqual(page["terms"]["items"], [text])

    def test_legacy_contact_without_contacts_list_becomes_single_contact(self) -> None:
        raw = json.dumps({"contact": {"title": " Kontakt ", "person": " Jan ", "phone": "1", "email": "a@b.pl"}})
        page = parse_offer_page(raw)
        self.assertEqual(page["contact"]["title"], "Kontakt")
        self.assertEqual(page["contacts"], [{"person": "Jan", "phone": "1", "email": "a@b.pl"}])

    def test_legacy_contact_with_all_fields_blank_keeps_default_contacts_list(self) -> None:
        raw = json.dumps({"contact": {"person": " ", "phone": "", "email": ""}})
        page = parse_offer_page(raw)
        self.assertEqual(page["contact"]["person"], "")
        self.assertEqual(page["contacts"], DEFAULT_OFFER_PAGE["contacts"])

    def test_non_string_legacy_contact_fields_are_ignored(self) -> None:
        raw = json.dumps({"contact": {"title": 1, "person": 2, "phone": None, "email": ["x"]}})
        self.assertEqual(parse_offer_page(raw), DEFAULT_OFFER_PAGE)

    def test_contacts_list_replaces_legacy_contact_and_normalizes_whitespace(self) -> None:
        raw = json.dumps(
            {
                "contact": {"person": "Stary"},
                "contacts": [
                    {"person": "  Anna   Nowak ", "phone": " +48  111 ", "email": "a@b.pl"},
                    {"person": "", "phone": "", "email": ""},
                    {"person": "Tylko osoba"},
                    "to nie słownik",
                    None,
                    {"phone": 123456},
                ],
            }
        )
        contacts = parse_offer_page(raw)["contacts"]
        self.assertEqual(
            contacts,
            [
                {"person": "Anna Nowak", "phone": "+48 111", "email": "a@b.pl"},
                {"person": "Tylko osoba", "phone": "", "email": ""},
                {"person": "", "phone": "123456", "email": ""},
            ],
        )

    def test_explicit_empty_contacts_list_means_no_contacts(self) -> None:
        self.assertEqual(parse_offer_page(json.dumps({"contacts": []}))["contacts"], [])

    def test_non_list_contacts_fall_back_to_the_legacy_contact(self) -> None:
        page = parse_offer_page(json.dumps({"contacts": "x", "contact": {"person": "Ewa"}}))
        self.assertEqual(page["contacts"][0]["person"], "Ewa")

    def test_custom_sections_are_normalized_and_blank_ones_dropped(self) -> None:
        raw = json.dumps(
            {
                "custom_sections": [
                    {"title": "  Gwarancja \n 2 lata ", "text": "\n  Treść\nw dwóch liniach  \n"},
                    {"title": "", "text": "   "},
                    {"title": "Sam tytuł"},
                    {"text": "Sam tekst"},
                    "tekst",
                    7,
                    {"title": 5, "text": None},
                ]
            }
        )
        sections = parse_offer_page(raw)["custom_sections"]
        self.assertEqual(
            sections,
            [
                {"title": "Gwarancja 2 lata", "text": "Treść\nw dwóch liniach"},
                {"title": "Sam tytuł", "text": ""},
                {"title": "", "text": "Sam tekst"},
                {"title": "5", "text": "None"},
            ],
        )

    def test_custom_sections_of_wrong_type_are_ignored(self) -> None:
        self.assertEqual(parse_offer_page(json.dumps({"custom_sections": {"a": 1}}))["custom_sections"], [])

    def test_unknown_keys_are_not_copied_into_the_page(self) -> None:
        page = parse_offer_page(json.dumps({"evil": "x", "__proto__": {"a": 1}}))
        self.assertNotIn("evil", page)
        self.assertEqual(set(page), set(DEFAULT_OFFER_PAGE))

    def test_parsing_does_not_mutate_the_default_page(self) -> None:
        parse_offer_page(json.dumps({"terms": {"items": ["x"]}, "contacts": [], "custom_sections": [{"title": "a"}]}))
        self.assertEqual(DEFAULT_OFFER_PAGE, default_offer_page())
        self.assertGreater(len(DEFAULT_OFFER_PAGE["terms"]["items"]), 1)


class SerializeOfferPageTests(unittest.TestCase):
    def test_default_page_serializes_to_empty_string(self) -> None:
        self.assertEqual(serialize_offer_page(default_offer_page()), "")

    def test_customized_page_round_trips(self) -> None:
        page = default_offer_page()
        page["terms"]["items"] = ["Zażółć gęślą jaźń"]
        page["contacts"].append({"person": "Ewa", "phone": "2", "email": "e@x.pl"})
        page["custom_sections"] = [{"title": "Tytuł", "text": "Linia 1\nLinia 2"}]
        raw = serialize_offer_page(page)
        self.assertTrue(raw)
        self.assertEqual(parse_offer_page(raw), page)

    def test_serialization_keeps_unicode_readable(self) -> None:
        page = default_offer_page()
        page["terms"]["title"] = "Łódź"
        self.assertIn("Łódź", serialize_offer_page(page))

    def test_single_changed_field_is_enough_to_produce_json(self) -> None:
        page = default_offer_page()
        page["contact"]["phone"] = "000"
        self.assertEqual(json.loads(serialize_offer_page(page))["contact"]["phone"], "000")

    def test_serialize_then_parse_of_default_is_stable(self) -> None:
        self.assertEqual(parse_offer_page(serialize_offer_page(default_offer_page())), DEFAULT_OFFER_PAGE)

    def test_removing_all_contacts_survives_round_trip(self) -> None:
        page = default_offer_page()
        page["contacts"] = []
        self.assertEqual(parse_offer_page(serialize_offer_page(page))["contacts"], [])


if __name__ == "__main__":
    unittest.main()
