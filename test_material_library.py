import unittest

from material_library import load_materials, material_label, serialize_materials


class MaterialLibraryTests(unittest.TestCase):
    def test_legacy_material_names_load_as_selectable_blanks(self) -> None:
        materials = load_materials(None, "S235JR\nAluminium")
        self.assertEqual(materials[0]["name"], "S235JR")
        self.assertEqual(material_label(materials[0]), "S235JR")

    def test_structured_materials_round_trip_and_remove_duplicate_entries(self) -> None:
        raw = serialize_materials([
            {
                "category": "Blacha",
                "name": "S235JR",
                "thickness_mm": "2",
                "price_per_kg": "4,7",
            },
            {
                "category": "Blacha",
                "name": "S235JR",
                "thickness_mm": "2",
                "price_per_kg": "4,7",
            },
        ])
        materials = load_materials(raw)
        self.assertEqual(len(materials), 1)
        self.assertEqual(materials[0]["price_per_kg"], "4,7")
        self.assertEqual(material_label(materials[0]), "S235JR")

    def test_material_dimensions_and_prices_are_validated(self) -> None:
        for field, value in (("thickness_mm", "0"), ("price_per_kg", "-1")):
            with self.subTest(field=field), self.assertRaises(ValueError):
                serialize_materials([{
                    "category": "Blacha",
                    "name": "S235JR",
                    "thickness_mm": "",
                    "price_per_kg": "",
                    field: value,
                }])
