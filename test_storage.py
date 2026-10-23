import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from storage import (
    Storage,
    format_postal_address,
    parse_polish_address,
    validate_postal_address,
)


def estimate_items() -> list[dict[str, object]]:
    return [
        {
            "element_name": "Wspornik",
            "material": "S235JR",
            "thickness_mm": "4",
            "quantity": 2,
            "price_per_kg": "12",
            "used_weight_kg": "2",
            "duration_seconds": 60,
            "burning_rate_per_hour": "500",
            "vat_percent": "23",
            "material_cost": "24.00",
            "burning_cost": "8.33",
            "unit_net": "32.33",
            "unit_vat": "7.44",
            "unit_gross": "39.77",
            "line_net": "64.66",
            "line_vat": "14.88",
            "line_gross": "79.54",
        },
        {
            "element_name": "Blacha",
            "material": "S235JR",
            "thickness_mm": "2",
            "quantity": 1,
            "price_per_kg": "10",
            "used_weight_kg": "0.8",
            "duration_seconds": 0,
            "burning_rate_per_hour": "500",
            "vat_percent": "23",
            "material_cost": "8.00",
            "burning_cost": "0.00",
            "unit_net": "8.00",
            "unit_vat": "1.84",
            "unit_gross": "9.84",
            "line_net": "8.00",
            "line_vat": "1.84",
            "line_gross": "9.84",
        },
    ]


class StorageTests(unittest.TestCase):
    def test_register_authenticate_and_keep_quotes_separate_by_user(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            storage = Storage(Path(temporary_directory) / "test.sqlite3")
            first_user = storage.register("operator", "a-secure-password")
            second_user = storage.register("other", "another-password")

            self.assertEqual(storage.authenticate("OPERATOR", "a-secure-password"), (first_user, "operator"))
            self.assertIsNone(storage.authenticate("operator", "wrong-password"))

            storage.save_quote(
                first_user,
                {
                    "customer": "Firma",
                    "order_number": "Z-100",
                    "element_name": "Wspornik",
                    "price_per_kg": "12",
                    "used_weight_kg": "2",
                    "duration_seconds": 60,
                    "burning_rate_per_hour": "500",
                    "vat_percent": "23",
                    "material_cost": "24.00",
                    "burning_cost": "8.33",
                    "net_total": "32.33",
                    "vat_amount": "7.44",
                    "gross_total": "39.77",
                },
            )
            self.assertEqual(len(storage.list_quotes(first_user)), 1)
            self.assertEqual(storage.list_quotes(second_user), [])

    def test_duplicate_usernames_are_rejected_case_insensitively(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            storage = Storage(Path(temporary_directory) / "test.sqlite3")
            storage.register("operator", "a-secure-password")
            with self.assertRaises(ValueError):
                storage.register("OPERATOR", "another-password")

    def test_desktop_profile_reuses_the_only_existing_account(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            storage = Storage(Path(temporary_directory) / "test.sqlite3")
            user_id = storage.register("operator", "a-secure-password")
            self.assertEqual(storage.get_desktop_user(), (user_id, "operator"))

    def test_desktop_profile_is_created_when_no_accounts_exist(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            storage = Storage(Path(temporary_directory) / "test.sqlite3")
            user_id, username = storage.get_desktop_user()
            self.assertEqual(username, "BlachCalc-local")
            self.assertEqual(storage.get_desktop_user(), (user_id, username))

    def test_desktop_profile_keeps_multiple_existing_accounts_separate(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            storage = Storage(Path(temporary_directory) / "test.sqlite3")
            first_user = storage.register("operator", "a-secure-password")
            second_user = storage.register("second", "another-password")
            local_user, local_username = storage.get_desktop_user()

            self.assertNotIn(local_user, (first_user, second_user))
            self.assertEqual(local_username, "BlachCalc-local")
            self.assertEqual(storage.get_desktop_user(), (local_user, local_username))

    def test_multi_item_estimate_preserves_customer_snapshot_and_user_isolation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            storage = Storage(Path(temporary_directory) / "test.sqlite3")
            user_id = storage.register("operator", "a-secure-password")
            other_user = storage.register("other", "another-password")
            storage.save_customer(
                user_id,
                {
                    "name": "Firma CNC",
                    "contact_person": "Jan Kowalski",
                    "email": "jan@example.com",
                    "phone": "123 456 789",
                    "tax_id": "1234567890",
                    "address": "Warszawa",
                },
            )

            estimate_id = storage.save_estimate(
                user_id,
                {"customer_name": "Firma CNC", "order_number": "Z-200", "notes": "Pilne"},
                estimate_items(),
            )
            estimate = storage.get_estimate(user_id, estimate_id)
            self.assertIsNotNone(estimate)
            self.assertEqual(estimate["header"]["quote_number"], "OF_Z-200_Firma_CNC")
            self.assertEqual(estimate["header"]["net_total"], "72.66")
            self.assertEqual(estimate["header"]["vat_amount"], "16.72")
            self.assertEqual(estimate["header"]["gross_total"], "89.38")
            self.assertEqual(estimate["header"]["pricing_mode"], "itemized")
            self.assertEqual(estimate["header"]["customer_email"], "jan@example.com")
            self.assertEqual(len(estimate["items"]), 2)
            self.assertIsNone(storage.get_estimate(other_user, estimate_id))

            customer = storage.list_customers(user_id)[0]
            storage.save_customer(
                user_id,
                {"name": "Firma CNC", "address": "Kraków"},
                int(customer["id"]),
            )
            unchanged_snapshot = storage.get_estimate(user_id, estimate_id)
            self.assertEqual(unchanged_snapshot["header"]["customer_address"], "Warszawa")

    def test_legacy_single_item_quotes_are_migrated(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            database_path = Path(temporary_directory) / "legacy.sqlite3"
            with closing(sqlite3.connect(database_path)) as connection, connection:
                connection.executescript(
                    """
                    CREATE TABLE users (
                        id INTEGER PRIMARY KEY,
                        username TEXT NOT NULL UNIQUE COLLATE NOCASE,
                        password_salt TEXT NOT NULL,
                        password_hash TEXT NOT NULL,
                        created_at TEXT NOT NULL
                    );
                    CREATE TABLE quotes (
                        id INTEGER PRIMARY KEY,
                        user_id INTEGER NOT NULL REFERENCES users(id),
                        customer TEXT NOT NULL,
                        order_number TEXT NOT NULL,
                        element_name TEXT NOT NULL,
                        price_per_kg TEXT NOT NULL,
                        used_weight_kg TEXT NOT NULL,
                        duration_seconds INTEGER NOT NULL,
                        burning_rate_per_hour TEXT NOT NULL,
                        vat_percent TEXT NOT NULL,
                        material_cost TEXT NOT NULL,
                        burning_cost TEXT NOT NULL,
                        net_total TEXT NOT NULL,
                        vat_amount TEXT NOT NULL,
                        gross_total TEXT NOT NULL,
                        created_at TEXT NOT NULL
                    );
                    INSERT INTO users VALUES (1, 'operator', 'salt', 'hash', '2026-01-01T12:00:00+01:00');
                    INSERT INTO quotes VALUES (
                        9, 1, 'Firma', 'Z-10', 'Blacha', '10', '2', 60,
                        '500', '23', '20.00', '8.33', '28.33', '6.52',
                        '34.85', '2026-01-01T12:00:00+01:00'
                    );
                    """
                )

            storage = Storage(database_path)
            estimates = storage.list_estimates(1)
            self.assertEqual(len(estimates), 1)
            self.assertEqual(estimates[0]["quote_number"], "OF_Z-10_Firma")
            estimate = storage.get_estimate(1, int(estimates[0]["id"]))
            self.assertEqual(estimate["items"][0]["element_name"], "Blacha")
            self.assertEqual(estimate["items"][0]["duration_seconds"], 60)

    def test_settings_and_sqlite_backup_are_restorable(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            database_path = Path(temporary_directory) / "test.sqlite3"
            backup_path = Path(temporary_directory) / "backup.sqlite3"
            storage = Storage(database_path)
            user_id = storage.register("operator", "a-secure-password")
            storage.save_settings(user_id, {"vat_percent": "8", "company_name": "Firma"})
            storage.backup(backup_path)

            restored = Storage(backup_path)
            self.assertEqual(restored.get_settings(user_id)["vat_percent"], "8")
            self.assertEqual(restored.get_settings(user_id)["company_name"], "Firma")
            self.assertEqual(restored.authenticate("operator", "a-secure-password"), (user_id, "operator"))

    def test_automatic_backups_are_rotated_and_restorable(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            storage = Storage(Path(temporary_directory) / "test.sqlite3")
            user_id = storage.register("operator", "a-secure-password")
            storage.save_settings(user_id, {"vat_percent": "8"})
            first = storage.create_backup("start")
            self.assertTrue(first.is_file())
            self.assertIsNone(storage.create_backup_if_stale(12))

            storage.save_settings(user_id, {"vat_percent": "23"})
            for _ in range(4):
                storage.create_backup("auto", keep=3)
            self.assertEqual(len(storage.list_backups()), 3)

            storage.restore_backup(storage.list_backups()[-1])
            self.assertEqual(storage.get_settings(user_id)["vat_percent"], "23")
            invalid = Path(temporary_directory) / "not-a-db.sqlite3"
            invalid.write_bytes(b"not sqlite")
            with self.assertRaises(ValueError):
                storage.restore_backup(invalid)

    def test_company_brand_defaults_are_available_without_manual_setup(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            storage = Storage(Path(temporary_directory) / "test.sqlite3")
            user_id, _username = storage.get_desktop_user()
            settings = storage.get_settings(user_id)

            self.assertEqual(settings["price_per_kg"], "4.7")
            self.assertEqual(settings["company_name"], "Izo-Technika Iłczyk Sp. Jawna")
            self.assertEqual(settings["company_address"], "ul. Wieniawskiego 18, 41-506 Chorzów")
            self.assertEqual(settings["company_phone"], "+48 786 300 750")
            self.assertEqual(settings["company_email"], "k.nowosinski@izotechnika-cnc.pl")
            self.assertEqual(settings["company_tax_id"], "6272789387")
            self.assertEqual(settings["company_regon"], "527515555")
            self.assertEqual(settings["company_website"], "www.izotechnika-cnc.pl")
            self.assertTrue(Path(settings["logo_path"]).is_file())
            self.assertEqual(settings["offer_validity_days"], "")

    def test_default_material_price_can_be_saved_and_loaded(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            storage = Storage(Path(temporary_directory) / "test.sqlite3")
            user_id = storage.get_desktop_user()[0]

            storage.save_settings(user_id, {"price_per_kg": "5.25"})

            self.assertEqual(storage.get_settings(user_id)["price_per_kg"], "5.25")

    def test_structured_polish_address_parses_and_formats_unit_numbers(self) -> None:
        parsed = parse_polish_address("ul. Wieniawskiego 18/4, 41-506 Chorzów, Polska")
        self.assertEqual(
            parsed,
            {
                "street": "Wieniawskiego",
                "building_number": "18",
                "unit_number": "4",
                "postal_code": "41-506",
                "city": "Chorzów",
                "country": "Polska",
            },
        )
        self.assertEqual(
            format_postal_address(parsed),
            "Wieniawskiego 18/4, 41-506 Chorzów, Polska",
        )

    def test_structured_address_validates_required_fields_and_polish_postcode(self) -> None:
        with self.assertRaisesRegex(ValueError, "Numer budynku"):
            validate_postal_address(
                {
                    "street": "Wieniawskiego",
                    "postal_code": "41-506",
                    "city": "Chorzów",
                    "country": "Polska",
                }
            )
        with self.assertRaisesRegex(ValueError, "00-000"):
            validate_postal_address(
                {
                    "street": "Wieniawskiego",
                    "building_number": "18",
                    "postal_code": "41506",
                    "city": "Chorzów",
                    "country": "Polska",
                }
            )
        validate_postal_address({"country": "Polska"})

    def test_previous_customer_addresses_are_parsed_without_removing_original_text(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            database_path = Path(temporary_directory) / "test.sqlite3"
            storage = Storage(database_path)
            user_id = storage.register("operator", "a-secure-password")
            storage.save_customer(user_id, {"name": "Firma"})
            with closing(sqlite3.connect(database_path)) as connection, connection:
                connection.execute(
                    """
                    UPDATE customers SET address = ?, address_legacy = '',
                        street = '', building_number = '', postal_code = '', city = ''
                    WHERE user_id = ?
                    """,
                    ("ul. Wieniawskiego 18, 41-506 Chorzów", user_id),
                )

            Storage(database_path)
            customer = storage.list_customers(user_id)[0]
            self.assertEqual(customer["street"], "Wieniawskiego")
            self.assertEqual(customer["building_number"], "18")
            self.assertEqual(customer["postal_code"], "41-506")
            self.assertEqual(customer["city"], "Chorzów")
            self.assertEqual(customer["address_legacy"], "ul. Wieniawskiego 18, 41-506 Chorzów")

    def test_older_company_address_is_split_into_fields_without_losing_text(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            storage = Storage(Path(temporary_directory) / "test.sqlite3")
            user_id = storage.register("operator", "a-secure-password")
            legacy_address = "ul. Polna 4/12, 00-950 Warszawa"
            storage.save_settings(user_id, {"company_address": legacy_address})

            settings = storage.get_settings(user_id)
            self.assertEqual(settings["company_address"], legacy_address)
            self.assertEqual(settings["company_street"], "Polna")
            self.assertEqual(settings["company_building_number"], "4")
            self.assertEqual(settings["company_unit_number"], "12")
            self.assertEqual(settings["company_postal_code"], "00-950")
            self.assertEqual(settings["company_city"], "Warszawa")

    def test_empty_saved_company_fields_fall_back_to_confirmed_brand_profile(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            storage = Storage(Path(temporary_directory) / "test.sqlite3")
            user_id = storage.register("operator", "a-secure-password")
            storage.save_settings(
                user_id,
                {"company_name": "", "company_email": "", "logo_path": ""},
            )

            settings = storage.get_settings(user_id)
            self.assertEqual(settings["company_name"], "Izo-Technika Iłczyk Sp. Jawna")
            self.assertEqual(settings["company_email"], "k.nowosinski@izotechnika-cnc.pl")
            self.assertTrue(Path(settings["logo_path"]).is_file())

    def test_customer_names_are_unique_without_case_sensitive_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            storage = Storage(Path(temporary_directory) / "test.sqlite3")
            user_id = storage.register("operator", "a-secure-password")
            storage.save_customer(
                user_id,
                {"name": "Firma CNC", "email": "kontakt@example.com"},
            )
            with self.assertRaises(ValueError):
                storage.save_customer(user_id, {"name": "firma cnc"})
            self.assertEqual(len(storage.list_customers(user_id)), 1)
            self.assertEqual(storage.list_customers(user_id)[0]["email"], "kontakt@example.com")

    def test_existing_estimate_can_be_updated_without_creating_a_duplicate(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            storage = Storage(Path(temporary_directory) / "test.sqlite3")
            user_id = storage.register("operator", "a-secure-password")
            estimate_id = storage.save_estimate(
                user_id,
                {"customer_name": "Firma", "order_number": "Z-200"},
                estimate_items(),
            )
            revised_item = estimate_items()[0]
            revised_item["quantity"] = 4
            revised_item["line_net"] = "129.32"
            revised_item["line_vat"] = "29.76"
            revised_item["line_gross"] = "159.08"
            storage.save_estimate(
                user_id,
                {
                    "customer_name": "Firma",
                    "order_number": "Z-200",
                    "pricing_mode": "total_only",
                },
                [revised_item],
                estimate_id,
            )

            estimates = storage.list_estimates(user_id)
            updated = storage.get_estimate(user_id, estimate_id)
            self.assertEqual(len(estimates), 1)
            self.assertEqual(estimates[0]["item_count"], 1)
            self.assertEqual(updated["items"][0]["quantity"], 4)
            self.assertEqual(updated["header"]["gross_total"], "159.08")
            self.assertEqual(updated["header"]["pricing_mode"], "total_only")

    def test_deleting_estimate_also_removes_its_positions(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            storage = Storage(Path(temporary_directory) / "test.sqlite3")
            user_id = storage.register("operator", "a-secure-password")
            estimate_id = storage.save_estimate(
                user_id,
                {"customer_name": "Firma", "order_number": "Z-201"},
                estimate_items(),
            )

            storage.delete_estimate(user_id, estimate_id)

            self.assertIsNone(storage.get_estimate(user_id, estimate_id))
            self.assertEqual(storage.list_estimates(user_id), [])

    def test_estimate_position_preserves_preview_image_in_database(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            storage = Storage(Path(temporary_directory) / "test.sqlite3")
            user_id = storage.register("operator", "a-secure-password")
            items = estimate_items()[:1]
            items[0]["preview_image"] = b"local image data"
            items[0]["preview_image_name"] = "part.jpg"

            estimate_id = storage.save_estimate(
                user_id,
                {"customer_name": "Firma", "order_number": "Z-202"},
                items,
            )

            saved_item = storage.get_estimate(user_id, estimate_id)["items"][0]
            self.assertEqual(saved_item["preview_image"], b"local image data")
            self.assertEqual(saved_item["preview_image_name"], "part.jpg")

    def test_estimate_numbers_match_safe_offer_filenames_and_avoid_collisions(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            storage = Storage(Path(temporary_directory) / "test.sqlite3")
            user_id = storage.register("operator", "a-secure-password")
            quote_numbers = []
            estimate_ids = []

            for order_number in ("Z/202", "Z/202"):
                estimate_id = storage.save_estimate(
                    user_id,
                    {"customer_name": "Firma: CNC", "order_number": order_number},
                    estimate_items()[:1],
                )
                estimate_ids.append(estimate_id)
                quote_numbers.append(
                    storage.get_estimate(user_id, estimate_id)["header"]["quote_number"]
                )

            self.assertEqual(quote_numbers, ["OF_Z_202_Firma_CNC", "OF_Z_202_Firma_CNC_2"])
            storage.save_estimate(
                user_id,
                {"customer_name": "Firma: CNC", "order_number": "Z-203"},
                estimate_items()[:1],
                estimate_ids[1],
            )
            updated = storage.get_estimate(user_id, estimate_ids[1])
            self.assertEqual(updated["header"]["quote_number"], "OF_Z-203_Firma_CNC")

    def test_estimate_saves_the_customer_offer_pricing_mode(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            storage = Storage(Path(temporary_directory) / "test.sqlite3")
            user_id = storage.register("operator", "a-secure-password")
            estimate_id = storage.save_estimate(
                user_id,
                {
                    "customer_name": "Firma",
                    "order_number": "Z-300",
                    "pricing_mode": "total_only",
                },
                estimate_items(),
            )
            estimate = storage.get_estimate(user_id, estimate_id)
            self.assertEqual(estimate["header"]["pricing_mode"], "total_only")
            with self.assertRaisesRegex(ValueError, "sposób prezentacji"):
                storage.save_estimate(
                    user_id,
                    {
                        "customer_name": "Firma",
                        "order_number": "Z-301",
                        "pricing_mode": "invalid",
                    },
                    estimate_items(),
                )

    def test_estimate_saves_calculation_mode_for_each_item(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            storage = Storage(Path(temporary_directory) / "test.sqlite3")
            user_id = storage.register("operator", "a-secure-password")
            whole_order_item = {
                **estimate_items()[0],
                "calculation_mode": "whole_order",
                "quantity": 12,
                "material_cost": "48.00",
                "burning_cost": "16.67",
                "used_weight_kg": "4",
                "duration_seconds": 120,
                "unit_net": "64.67",
                "unit_vat": "14.87",
                "unit_gross": "79.54",
                "line_net": "64.67",
                "line_vat": "14.87",
                "line_gross": "79.54",
            }
            estimate_id = storage.save_estimate(
                user_id,
                {"customer_name": "Firma", "order_number": "Z-400"},
                [whole_order_item],
            )

            estimate = storage.get_estimate(user_id, estimate_id)

            self.assertEqual(estimate["items"][0]["calculation_mode"], "whole_order")
            self.assertEqual(estimate["items"][0]["used_weight_kg"], "4")
            self.assertEqual(estimate["items"][0]["duration_seconds"], 120)
            self.assertEqual(estimate["items"][0]["quantity"], 12)
            self.assertEqual(estimate["items"][0]["line_gross"], "79.54")

    def test_estimate_rejects_unknown_calculation_mode(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            storage = Storage(Path(temporary_directory) / "test.sqlite3")
            user_id = storage.register("operator", "a-secure-password")
            item = {**estimate_items()[0], "calculation_mode": "unknown"}

            with self.assertRaisesRegex(ValueError, "sposób kalkulacji"):
                storage.save_estimate(
                    user_id,
                    {"customer_name": "Firma", "order_number": "Z-401"},
                    [item],
                )

    def test_estimate_rejects_amounts_inconsistent_with_calculation_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            storage = Storage(Path(temporary_directory) / "test.sqlite3")
            user_id = storage.register("operator", "a-secure-password")
            item = {**estimate_items()[0], "line_net": "1.00"}

            with self.assertRaisesRegex(ValueError, "line_net"):
                storage.save_estimate(
                    user_id,
                    {"customer_name": "Firma", "order_number": "Z-403"},
                    [item],
                )

    def test_estimate_rejects_order_totals_above_safe_limit(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            storage = Storage(Path(temporary_directory) / "test.sqlite3")
            user_id = storage.register("operator", "a-secure-password")
            item = {
                **estimate_items()[0],
                "quantity": 1,
                "price_per_kg": "600000000000",
                "used_weight_kg": "1",
                "duration_seconds": 0,
                "material_cost": "600000000000.00",
                "burning_cost": "0.00",
                "unit_net": "600000000000.00",
                "unit_vat": "138000000000.00",
                "unit_gross": "738000000000.00",
                "line_net": "600000000000.00",
                "line_vat": "138000000000.00",
                "line_gross": "738000000000.00",
            }

            with self.assertRaisesRegex(ValueError, "nie może przekraczać"):
                storage.save_estimate(
                    user_id,
                    {"customer_name": "Firma", "order_number": "Z-404"},
                    [item, item],
                )

    def test_existing_estimate_items_migrate_to_per_piece_mode(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            database_path = Path(temporary_directory) / "test.sqlite3"
            storage = Storage(database_path)
            user_id = storage.register("operator", "a-secure-password")
            estimate_id = storage.save_estimate(
                user_id,
                {"customer_name": "Firma", "order_number": "Z-402"},
                estimate_items(),
            )
            with closing(sqlite3.connect(database_path)) as connection, connection:
                connection.execute("ALTER TABLE estimate_items DROP COLUMN calculation_mode")

            migrated_storage = Storage(database_path)
            estimate = migrated_storage.get_estimate(user_id, estimate_id)

            self.assertEqual(estimate["items"][0]["calculation_mode"], "per_piece")


if __name__ == "__main__":
    unittest.main()
