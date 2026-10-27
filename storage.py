import hashlib
import hmac
import os
import re
import secrets
import sqlite3
from contextlib import closing
from datetime import datetime
from decimal import Decimal, DecimalException
from pathlib import Path
from typing import Any

from calculator import (
    MAX_CALCULATION_TOTAL,
    MAX_DURATION_SECONDS,
    calculate_quote,
    parse_decimal,
)
from app_paths import resource_path
from quote_domain import DEFAULT_OPERATION, OPERATIONS


PBKDF2_ITERATIONS = 310_000
MAX_PREVIEW_IMAGE_BYTES = 10 * 1024 * 1024
DEFAULT_SETTINGS = {
    "price_per_kg": "4.7",
    "burning_rate_per_hour": "500",
    "vat_percent": "23",
    "materials": "",
    "logo_path": str(resource_path("logo.png")),
    "company_name": "Izo-Technika Iłczyk Sp. Jawna",
    "company_address": "ul. Wieniawskiego 18, 41-506 Chorzów",
    "company_street": "Wieniawskiego",
    "company_building_number": "18",
    "company_unit_number": "",
    "company_postal_code": "41-506",
    "company_city": "Chorzów",
    "company_country": "Polska",
    "company_phone": "+48 786 300 750",
    "company_email": "k.nowosinski@izotechnika-cnc.pl",
    "company_tax_id": "6272789387",
    "company_regon": "527515555",
    "company_website": "www.izotechnika-cnc.pl",
    "brand_tagline": "Usługi CNC · Laser · Prasa",
    "brand_primary": "#243F82",
    "brand_accent": "#ED1B24",
    "offer_validity_days": "",
    "payment_terms": "",
    "delivery_terms": "",
    "offer_page2": "",
    "photo_width_mm": "44",
    "wz_row_height_mm": "5",
}
ADDRESS_FIELDS = ("street", "building_number", "unit_number", "postal_code", "city", "country")


def parse_polish_address(address: str) -> dict[str, str] | None:
    normalized = " ".join(address.split()).strip()
    if not normalized:
        return None

    patterns = (
        re.compile(
            r"^(?P<street>.+?)\s+(?P<building>\d+[A-Za-z]?)"
            r"(?:\s*/\s*(?P<unit>[\w-]+))?,\s*"
            r"(?P<postal>\d{2}-\d{3})\s+(?P<city>[^,]+)"
            r"(?:,\s*(?P<country>[^,]+))?$",
            re.IGNORECASE,
        ),
        re.compile(
            r"^(?P<postal>\d{2}-\d{3})\s+(?P<city>[^,]+),\s*"
            r"(?:ul\.?\s*|al\.?\s*|pl\.?\s*|os\.?\s*)?"
            r"(?P<street>.+?)\s+(?P<building>\d+[A-Za-z]?)"
            r"(?:\s*/\s*(?P<unit>[\w-]+))?$",
            re.IGNORECASE,
        ),
    )
    for pattern in patterns:
        match = pattern.fullmatch(normalized)
        if match is None:
            continue
        values = match.groupdict()
        street = re.sub(r"^(?:ul\.?|al\.?|pl\.?|os\.?)\s*", "", values["street"], flags=re.IGNORECASE).strip()
        return {
            "street": street,
            "building_number": values["building"],
            "unit_number": values.get("unit") or "",
            "postal_code": values["postal"],
            "city": values["city"].strip(),
            "country": (values.get("country") or "Polska").strip(),
        }
    return None


def format_postal_address(values: dict[str, str], prefix: str = "") -> str:
    def get(field: str) -> str:
        return values.get(f"{prefix}{field}", "").strip()

    street_line = " ".join(part for part in (get("street"), get("building_number")) if part)
    if get("unit_number"):
        street_line = f"{street_line}/{get('unit_number')}".strip("/")
    postal_line = " ".join(part for part in (get("postal_code"), get("city")) if part)
    return ", ".join(
        part for part in (street_line, postal_line, get("country")) if part
    )


def validate_postal_address(values: dict[str, str], prefix: str = "") -> None:
    address = {
        field: values.get(f"{prefix}{field}", "").strip()
        for field in ADDRESS_FIELDS
    }
    has_address = any(address[field] for field in ADDRESS_FIELDS[:-1])
    if not has_address:
        return

    required_fields = {
        "street": "Ulica",
        "building_number": "Numer budynku",
        "postal_code": "Kod pocztowy",
        "city": "Miejscowość",
        "country": "Kraj",
    }
    for field, label in required_fields.items():
        if not address[field]:
            raise ValueError(f"Uzupełnij pole adresu: {label}.")

    if len(address["street"]) > 120 or len(address["city"]) > 100:
        raise ValueError("Ulica i miejscowość nie mogą przekraczać 120 i 100 znaków.")
    if len(address["building_number"]) > 20 or len(address["unit_number"]) > 20:
        raise ValueError("Numery budynku i lokalu nie mogą przekraczać 20 znaków.")
    if len(address["postal_code"]) > 16 or len(address["country"]) > 80:
        raise ValueError("Kod pocztowy lub kraj przekracza dozwoloną długość.")
    if address["country"].casefold() == "polska" and not re.fullmatch(
        r"\d{2}-\d{3}", address["postal_code"]
    ):
        raise ValueError("Polski kod pocztowy musi mieć format 00-000.")


class Storage:
    def __init__(self, database_path: str | Path | None = None) -> None:
        if database_path is None:
            local_app_data = os.environ.get("LOCALAPPDATA")
            data_directory = (
                Path(local_app_data) / "BlachCalc"
                if local_app_data
                else Path.home() / "AppData" / "Local" / "BlachCalc"
            )
            data_directory.mkdir(parents=True, exist_ok=True)
            database_path = data_directory / "blachcalc.sqlite3"

        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _initialize(self) -> None:
        with closing(self._connect()) as connection, connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY,
                    username TEXT NOT NULL UNIQUE COLLATE NOCASE,
                    password_salt TEXT NOT NULL,
                    password_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS quotes (
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
                CREATE INDEX IF NOT EXISTS quotes_by_user_date
                    ON quotes(user_id, created_at DESC);
                CREATE TABLE IF NOT EXISTS customers (
                    id INTEGER PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    name TEXT NOT NULL,
                    contact_person TEXT NOT NULL DEFAULT '',
                    email TEXT NOT NULL DEFAULT '',
                    phone TEXT NOT NULL DEFAULT '',
                    tax_id TEXT NOT NULL DEFAULT '',
                    address TEXT NOT NULL DEFAULT '',
                    address_legacy TEXT NOT NULL DEFAULT '',
                    street TEXT NOT NULL DEFAULT '',
                    building_number TEXT NOT NULL DEFAULT '',
                    unit_number TEXT NOT NULL DEFAULT '',
                    postal_code TEXT NOT NULL DEFAULT '',
                    city TEXT NOT NULL DEFAULT '',
                    country TEXT NOT NULL DEFAULT '',
                    UNIQUE (user_id, name)
                );
                CREATE INDEX IF NOT EXISTS customers_by_user_name
                    ON customers(user_id, name COLLATE NOCASE);
                CREATE UNIQUE INDEX IF NOT EXISTS customers_user_name_ci
                    ON customers(user_id, name COLLATE NOCASE);
                CREATE TABLE IF NOT EXISTS user_settings (
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    setting_key TEXT NOT NULL,
                    setting_value TEXT NOT NULL,
                    PRIMARY KEY (user_id, setting_key)
                );
                CREATE TABLE IF NOT EXISTS estimates (
                    id INTEGER PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    quote_number TEXT NOT NULL,
                    customer_id INTEGER REFERENCES customers(id) ON DELETE SET NULL,
                    customer_name TEXT NOT NULL,
                    customer_contact_person TEXT NOT NULL DEFAULT '',
                    customer_email TEXT NOT NULL DEFAULT '',
                    customer_phone TEXT NOT NULL DEFAULT '',
                    customer_tax_id TEXT NOT NULL DEFAULT '',
                    customer_address TEXT NOT NULL DEFAULT '',
                    customer_address_legacy TEXT NOT NULL DEFAULT '',
                    customer_street TEXT NOT NULL DEFAULT '',
                    customer_building_number TEXT NOT NULL DEFAULT '',
                    customer_unit_number TEXT NOT NULL DEFAULT '',
                    customer_postal_code TEXT NOT NULL DEFAULT '',
                    customer_city TEXT NOT NULL DEFAULT '',
                    customer_country TEXT NOT NULL DEFAULT '',
                    order_number TEXT NOT NULL,
                    notes TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'Obliczona',
                    pricing_mode TEXT NOT NULL DEFAULT 'itemized',
                    net_total TEXT NOT NULL,
                    vat_amount TEXT NOT NULL,
                    gross_total TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE (user_id, quote_number)
                );
                CREATE INDEX IF NOT EXISTS estimates_by_user_date
                    ON estimates(user_id, created_at DESC);
                CREATE TABLE IF NOT EXISTS estimate_items (
                    id INTEGER PRIMARY KEY,
                    estimate_id INTEGER NOT NULL REFERENCES estimates(id) ON DELETE CASCADE,
                    position INTEGER NOT NULL,
                    element_name TEXT NOT NULL,
                    material TEXT NOT NULL DEFAULT '',
                    thickness_mm TEXT NOT NULL DEFAULT '',
                    calculation_mode TEXT NOT NULL DEFAULT 'per_piece',
                    operation TEXT NOT NULL DEFAULT 'cutting',
                    quantity INTEGER NOT NULL DEFAULT 1,
                    price_per_kg TEXT NOT NULL,
                    used_weight_kg TEXT NOT NULL,
                    duration_seconds INTEGER NOT NULL,
                    burning_rate_per_hour TEXT NOT NULL,
                    vat_percent TEXT NOT NULL,
                    material_cost TEXT NOT NULL,
                    burning_cost TEXT NOT NULL,
                    unit_net TEXT NOT NULL,
                    unit_vat TEXT NOT NULL,
                    unit_gross TEXT NOT NULL,
                    line_net TEXT NOT NULL,
                    line_vat TEXT NOT NULL,
                    line_gross TEXT NOT NULL,
                    preview_image BLOB,
                    preview_image_name TEXT NOT NULL DEFAULT '',
                    UNIQUE (estimate_id, position)
                );
                CREATE TABLE IF NOT EXISTS app_migrations (
                    migration_key TEXT PRIMARY KEY,
                    applied_at TEXT NOT NULL
                );
                """
            )
            self._add_columns(
                connection,
                "customers",
                {
                    "address_legacy": "TEXT NOT NULL DEFAULT ''",
                    "street": "TEXT NOT NULL DEFAULT ''",
                    "building_number": "TEXT NOT NULL DEFAULT ''",
                    "unit_number": "TEXT NOT NULL DEFAULT ''",
                    "postal_code": "TEXT NOT NULL DEFAULT ''",
                    "city": "TEXT NOT NULL DEFAULT ''",
                    "country": "TEXT NOT NULL DEFAULT ''",
                },
            )
            self._add_columns(
                connection,
                "estimates",
                {
                    "customer_contact_person": "TEXT NOT NULL DEFAULT ''",
                    "customer_email": "TEXT NOT NULL DEFAULT ''",
                    "customer_phone": "TEXT NOT NULL DEFAULT ''",
                    "customer_tax_id": "TEXT NOT NULL DEFAULT ''",
                    "customer_address": "TEXT NOT NULL DEFAULT ''",
                    "customer_address_legacy": "TEXT NOT NULL DEFAULT ''",
                    "customer_street": "TEXT NOT NULL DEFAULT ''",
                    "customer_building_number": "TEXT NOT NULL DEFAULT ''",
                    "customer_unit_number": "TEXT NOT NULL DEFAULT ''",
                    "customer_postal_code": "TEXT NOT NULL DEFAULT ''",
                    "customer_city": "TEXT NOT NULL DEFAULT ''",
                    "customer_country": "TEXT NOT NULL DEFAULT ''",
                    "pricing_mode": "TEXT NOT NULL DEFAULT 'itemized'",
                },
            )
            self._add_columns(
                connection,
                "estimate_items",
                {
                    "calculation_mode": "TEXT NOT NULL DEFAULT 'per_piece'",
                    "operation": "TEXT NOT NULL DEFAULT 'cutting'",
                    "preview_image_name": "TEXT NOT NULL DEFAULT ''",
                },
            )
            self._migrate_legacy_addresses(connection)
            migrated = connection.execute(
                "SELECT 1 FROM app_migrations WHERE migration_key = ?",
                ("legacy_quotes_to_estimates_v1",),
            ).fetchone()
            if migrated is None:
                legacy_rows = connection.execute(
                    "SELECT * FROM quotes ORDER BY id"
                ).fetchall()
                for row in legacy_rows:
                    created_at = str(row["created_at"])
                    cursor = connection.execute(
                        """
                        INSERT INTO estimates (
                            user_id, quote_number, customer_name, order_number,
                            net_total, vat_amount, gross_total, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            row["user_id"],
                            f"BC-LEGACY-{row['id']:06}",
                            row["customer"],
                            row["order_number"],
                            row["net_total"],
                            row["vat_amount"],
                            row["gross_total"],
                            created_at,
                            created_at,
                        ),
                    )
                    connection.execute(
                        """
                        INSERT INTO estimate_items (
                            estimate_id, position, element_name, quantity,
                            price_per_kg, used_weight_kg, duration_seconds,
                            burning_rate_per_hour, vat_percent, material_cost,
                            burning_cost, unit_net, unit_vat, unit_gross,
                            line_net, line_vat, line_gross
                        ) VALUES (?, 1, ?, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            cursor.lastrowid,
                            row["element_name"],
                            row["price_per_kg"],
                            row["used_weight_kg"],
                            row["duration_seconds"],
                            row["burning_rate_per_hour"],
                            row["vat_percent"],
                            row["material_cost"],
                            row["burning_cost"],
                            row["net_total"],
                            row["vat_amount"],
                            row["gross_total"],
                            row["net_total"],
                            row["vat_amount"],
                            row["gross_total"],
                        ),
                    )
                connection.execute(
                    "INSERT INTO app_migrations VALUES (?, ?)",
                    (
                        "legacy_quotes_to_estimates_v1",
                        datetime.now().astimezone().isoformat(timespec="seconds"),
                    ),
                )
            quote_numbers_migrated = connection.execute(
                "SELECT 1 FROM app_migrations WHERE migration_key = ?",
                ("estimate_numbers_to_offer_filenames_v1",),
            ).fetchone()
            if quote_numbers_migrated is None:
                self._migrate_estimate_numbers(connection)
                connection.execute(
                    "INSERT INTO app_migrations VALUES (?, ?)",
                    (
                        "estimate_numbers_to_offer_filenames_v1",
                        datetime.now().astimezone().isoformat(timespec="seconds"),
                    ),
                )

    @staticmethod
    def _safe_filename_component(value: str) -> str:
        cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", value.strip())
        cleaned = re.sub(r"\s+", "_", cleaned)
        cleaned = re.sub(r"_+", "_", cleaned).strip(" ._")
        return (cleaned or "bez_nazwy")[:80].rstrip(" ._") or "bez_nazwy"

    @classmethod
    def _unique_quote_number(
        cls,
        connection: sqlite3.Connection,
        user_id: int,
        order_number: str,
        customer_name: str,
        exclude_estimate_id: int | None = None,
    ) -> str:
        base = "OF_{}_{}".format(
            cls._safe_filename_component(order_number),
            cls._safe_filename_component(customer_name),
        )
        candidate = base
        suffix = 2
        while connection.execute(
            """
            SELECT 1 FROM estimates
            WHERE user_id = ? AND quote_number = ? AND (? IS NULL OR id != ?)
            """,
            (user_id, candidate, exclude_estimate_id, exclude_estimate_id),
        ).fetchone():
            candidate = f"{base}_{suffix}"
            suffix += 1
        return candidate

    @classmethod
    def _migrate_estimate_numbers(cls, connection: sqlite3.Connection) -> None:
        rows = connection.execute(
            """
            SELECT id, user_id, customer_name, order_number
            FROM estimates
            ORDER BY user_id, id
            """
        ).fetchall()
        for row in rows:
            connection.execute(
                "UPDATE estimates SET quote_number = ? WHERE id = ?",
                (f"MIGRATING-{row['id']}", row["id"]),
            )
        for row in rows:
            quote_number = cls._unique_quote_number(
                connection,
                int(row["user_id"]),
                str(row["order_number"]),
                str(row["customer_name"]),
                int(row["id"]),
            )
            connection.execute(
                "UPDATE estimates SET quote_number = ? WHERE id = ?",
                (quote_number, row["id"]),
            )

    @staticmethod
    def _add_columns(
        connection: sqlite3.Connection,
        table: str,
        definitions: dict[str, str],
    ) -> None:
        existing_columns = {
            str(row["name"])
            for row in connection.execute(f"PRAGMA table_info({table})").fetchall()
        }
        for column, definition in definitions.items():
            if column not in existing_columns:
                connection.execute(
                    f"ALTER TABLE {table} ADD COLUMN {column} {definition}"
                )

    @staticmethod
    def _migrate_legacy_addresses(connection: sqlite3.Connection) -> None:
        customers = connection.execute(
            """
            SELECT id, address FROM customers
            WHERE address != '' AND address_legacy = '' AND street = ''
              AND building_number = '' AND postal_code = '' AND city = ''
            """
        ).fetchall()
        for customer in customers:
            address = str(customer["address"])
            parsed = parse_polish_address(address)
            connection.execute(
                "UPDATE customers SET address_legacy = ? WHERE id = ?",
                (address, customer["id"]),
            )
            if parsed:
                connection.execute(
                    """
                    UPDATE customers
                    SET street = ?, building_number = ?, unit_number = ?,
                        postal_code = ?, city = ?, country = ?
                    WHERE id = ?
                    """,
                    (
                        parsed["street"],
                        parsed["building_number"],
                        parsed["unit_number"],
                        parsed["postal_code"],
                        parsed["city"],
                        parsed["country"],
                        customer["id"],
                    ),
                )

        estimates = connection.execute(
            """
            SELECT id, customer_address FROM estimates
            WHERE customer_address != '' AND customer_address_legacy = ''
              AND customer_street = '' AND customer_building_number = ''
              AND customer_postal_code = '' AND customer_city = ''
            """
        ).fetchall()
        for estimate in estimates:
            address = str(estimate["customer_address"])
            parsed = parse_polish_address(address)
            connection.execute(
                "UPDATE estimates SET customer_address_legacy = ? WHERE id = ?",
                (address, estimate["id"]),
            )
            if parsed:
                connection.execute(
                    """
                    UPDATE estimates
                    SET customer_street = ?, customer_building_number = ?,
                        customer_unit_number = ?, customer_postal_code = ?,
                        customer_city = ?, customer_country = ?
                    WHERE id = ?
                    """,
                    (
                        parsed["street"],
                        parsed["building_number"],
                        parsed["unit_number"],
                        parsed["postal_code"],
                        parsed["city"],
                        parsed["country"],
                        estimate["id"],
                    ),
                )

    @staticmethod
    def _password_hash(password: str, salt: bytes) -> bytes:
        return hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS
        )

    def register(self, username: str, password: str) -> int:
        clean_username = username.strip()
        if not 3 <= len(clean_username) <= 50:
            raise ValueError("Nazwa użytkownika musi mieć od 3 do 50 znaków.")
        if len(password) < 8:
            raise ValueError("Hasło musi mieć co najmniej 8 znaków.")

        salt = secrets.token_bytes(16)
        password_hash = self._password_hash(password, salt)
        try:
            with closing(self._connect()) as connection, connection:
                cursor = connection.execute(
                    """
                    INSERT INTO users (username, password_salt, password_hash, created_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        clean_username,
                        salt.hex(),
                        password_hash.hex(),
                        datetime.now().astimezone().isoformat(timespec="seconds"),
                    ),
                )
                return int(cursor.lastrowid)
        except sqlite3.IntegrityError as error:
            raise ValueError("Użytkownik o tej nazwie już istnieje.") from error

    def authenticate(self, username: str, password: str) -> tuple[int, str] | None:
        clean_username = username.strip()
        with closing(self._connect()) as connection, connection:
            user = connection.execute(
                "SELECT id, username, password_salt, password_hash FROM users WHERE username = ?",
                (clean_username,),
            ).fetchone()

        salt = bytes.fromhex(user["password_salt"]) if user else bytes(16)
        expected_hash = bytes.fromhex(user["password_hash"]) if user else bytes(32)
        actual_hash = self._password_hash(password, salt)
        if user is None or not hmac.compare_digest(actual_hash, expected_hash):
            return None
        return int(user["id"]), str(user["username"])

    def get_desktop_user(self) -> tuple[int, str]:
        with closing(self._connect()) as connection, connection:
            users = connection.execute(
                "SELECT id, username FROM users ORDER BY id LIMIT 2"
            ).fetchall()
            if len(users) == 1:
                return int(users[0]["id"]), str(users[0]["username"])

            local_user = connection.execute(
                "SELECT id, username FROM users WHERE username = ?",
                ("BlachCalc-local",),
            ).fetchone()
            if local_user is not None:
                return int(local_user["id"]), str(local_user["username"])

        local_password = secrets.token_urlsafe(48)
        user_id = self.register("BlachCalc-local", local_password)
        return user_id, "BlachCalc-local"

    def get_settings(self, user_id: int) -> dict[str, str]:
        result = DEFAULT_SETTINGS.copy()
        with closing(self._connect()) as connection, connection:
            rows = connection.execute(
                "SELECT setting_key, setting_value FROM user_settings WHERE user_id = ?",
                (user_id,),
            ).fetchall()
        saved_settings = {str(row["setting_key"]): str(row["setting_value"]) for row in rows}
        for row in rows:
            value = str(row["setting_value"])
            if value or row["setting_key"] not in DEFAULT_SETTINGS:
                result[str(row["setting_key"])] = value
        legacy_address = saved_settings.get("company_address", "").strip()
        structured_keys = {
            f"company_{field}"
            for field in ADDRESS_FIELDS
        }
        if legacy_address and not structured_keys.intersection(saved_settings):
            parsed = parse_polish_address(legacy_address)
            if parsed:
                result.update({f"company_{key}": value for key, value in parsed.items()})
            else:
                result.update({key: "" for key in structured_keys})
        if result["logo_path"] and not Path(result["logo_path"]).is_file():
            result["logo_path"] = DEFAULT_SETTINGS["logo_path"]
        return result

    def save_settings(self, user_id: int, values: dict[str, str]) -> None:
        with closing(self._connect()) as connection, connection:
            connection.executemany(
                """
                INSERT INTO user_settings (user_id, setting_key, setting_value)
                VALUES (?, ?, ?)
                ON CONFLICT (user_id, setting_key)
                DO UPDATE SET setting_value = excluded.setting_value
                """,
                [(user_id, key, value) for key, value in values.items()],
            )

    def list_customers(self, user_id: int) -> list[sqlite3.Row]:
        with closing(self._connect()) as connection, connection:
            return list(
                connection.execute(
                    "SELECT * FROM customers WHERE user_id = ? ORDER BY name COLLATE NOCASE",
                    (user_id,),
                ).fetchall()
            )

    def save_customer(self, user_id: int, values: dict[str, str], customer_id: int | None = None) -> int:
        name = values["name"].strip()
        if not name:
            raise ValueError("Nazwa klienta jest wymagana.")
        address_values = {field: values.get(field, "").strip() for field in ADDRESS_FIELDS}
        validate_postal_address(address_values)
        legacy_address = values.get("address_legacy", values.get("address", "")).strip()
        if not any(address_values.values()) and values.get("address", "").strip():
            parsed = parse_polish_address(values["address"].strip())
            if parsed:
                address_values.update(parsed)
                legacy_address = values["address"].strip()
        formatted_address = format_postal_address(address_values) or legacy_address
        fields = (
            name,
            values.get("contact_person", "").strip(),
            values.get("email", "").strip(),
            values.get("phone", "").strip(),
            values.get("tax_id", "").strip(),
            formatted_address,
            legacy_address,
            *(address_values[field] for field in ADDRESS_FIELDS),
        )
        with closing(self._connect()) as connection, connection:
            if customer_id is None:
                existing = connection.execute(
                    "SELECT id FROM customers WHERE user_id = ? AND name = ? COLLATE NOCASE",
                    (user_id, name),
                ).fetchone()
                if existing is not None:
                    raise ValueError("Klient o tej nazwie już istnieje. Wybierz go z kartoteki lub edytuj istniejącego klienta.")
                cursor = connection.execute(
                    """
                    INSERT INTO customers (
                        user_id, name, contact_person, email, phone, tax_id,
                        address, address_legacy, street, building_number, unit_number,
                        postal_code, city, country
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (user_id, *fields),
                )
                return int(cursor.lastrowid)
            try:
                cursor = connection.execute(
                    """
                    UPDATE customers
                    SET name = ?, contact_person = ?, email = ?, phone = ?,
                        tax_id = ?, address = ?, address_legacy = ?, street = ?,
                        building_number = ?, unit_number = ?, postal_code = ?,
                        city = ?, country = ?
                    WHERE id = ? AND user_id = ?
                    """,
                    (*fields, customer_id, user_id),
                )
            except sqlite3.IntegrityError as error:
                raise ValueError("Klient o tej nazwie już istnieje. Wybierz go z kartoteki lub edytuj istniejącego klienta.") from error
            if cursor.rowcount != 1:
                raise ValueError("Nie znaleziono wskazanego klienta.")
            return customer_id

    def delete_customer(self, user_id: int, customer_id: int) -> None:
        with closing(self._connect()) as connection, connection:
            connection.execute(
                "DELETE FROM customers WHERE id = ? AND user_id = ?",
                (customer_id, user_id),
            )

    @staticmethod
    def _validate_estimate_item(item: dict[str, Any]) -> None:
        preview_image = item.get("preview_image")
        if preview_image is not None:
            if not isinstance(preview_image, (bytes, bytearray, memoryview)):
                raise ValueError("Zdjęcie pozycji musi być prawidłowym plikiem graficznym.")
            if not preview_image or len(preview_image) > MAX_PREVIEW_IMAGE_BYTES:
                raise ValueError("Zdjęcie pozycji nie może być puste ani przekraczać 10 MB.")
        preview_image_name = item.get("preview_image_name", "")
        if not isinstance(preview_image_name, str) or len(preview_image_name) > 255:
            raise ValueError("Nazwa zdjęcia pozycji może mieć maksymalnie 255 znaków.")
        calculation_mode = item.get("calculation_mode", "per_piece")
        if calculation_mode not in {"per_piece", "whole_order"}:
            raise ValueError("Wybierz prawidłowy sposób kalkulacji pozycji.")
        if item.get("operation", DEFAULT_OPERATION) not in OPERATIONS:
            raise ValueError("Wybierz prawidłową operację dla pozycji.")
        try:
            quantity = int(item["quantity"])
            duration_seconds = int(item["duration_seconds"])
            price_per_kg = parse_decimal(str(item["price_per_kg"]), "Cena materiału za kg")
            weight = parse_decimal(str(item["used_weight_kg"]), "Masa materiału")
            rate = parse_decimal(str(item["burning_rate_per_hour"]), "Stawka palenia")
            vat = parse_decimal(str(item["vat_percent"]), "VAT")
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError("Pozycja zawiera nieprawidłowe dane wejściowe.") from error

        if not 1 <= quantity <= 1_000_000:
            raise ValueError("Ilość musi mieścić się w zakresie od 1 do 1 000 000 sztuk.")
        if not 0 <= duration_seconds <= MAX_DURATION_SECONDS:
            raise ValueError("Czas palenia musi mieścić się w zakresie od 0 do 10 lat.")

        try:
            expected = calculate_quote(price_per_kg, weight, duration_seconds, rate, vat)
            quantity_multiplier = 1 if calculation_mode == "whole_order" else quantity
            expected_values = {
                "material_cost": expected.material_cost,
                "burning_cost": expected.burning_cost,
                "unit_net": expected.net_total,
                "unit_vat": expected.vat_amount,
                "unit_gross": expected.gross_total,
                "line_net": expected.net_total * quantity_multiplier,
                "line_vat": expected.vat_amount * quantity_multiplier,
                "line_gross": expected.gross_total * quantity_multiplier,
            }
            for field, expected_value in expected_values.items():
                actual = parse_decimal(str(item[field]), field)
                if actual != expected_value:
                    raise ValueError(
                        f"Kwota w polu {field} nie zgadza się z parametrami pozycji."
                    )
                if actual > MAX_CALCULATION_TOTAL:
                    raise ValueError(
                        "Wartość pojedynczej pozycji nie może przekraczać "
                        "1 000 000 000 000 zł."
                    )
        except KeyError as error:
            raise ValueError("Pozycja nie zawiera wszystkich wymaganych kwot.") from error
        except DecimalException as error:
            raise ValueError("Wartości pozycji są zbyt duże do bezpiecznego zapisu.") from error

    def save_estimate(
        self,
        user_id: int,
        header: dict[str, str],
        items: list[dict[str, Any]],
        estimate_id: int | None = None,
    ) -> int:
        if not items:
            raise ValueError("Dodaj co najmniej jedną pozycję do wyceny.")
        pricing_mode = header.get("pricing_mode", "itemized")
        if pricing_mode not in {"itemized", "total_only"}:
            raise ValueError("Wybierz prawidłowy sposób prezentacji cen w ofercie.")
        if not header.get("customer_name", "").strip():
            raise ValueError("Nazwa zleceniodawcy jest wymagana.")
        if not header.get("order_number", "").strip():
            raise ValueError("Numer zamówienia jest wymagany.")
        for item in items:
            self._validate_estimate_item(item)
        try:
            net_total = sum((Decimal(str(item["line_net"])) for item in items), Decimal("0"))
            vat_amount = sum((Decimal(str(item["line_vat"])) for item in items), Decimal("0"))
            gross_total = net_total + vat_amount
        except DecimalException as error:
            raise ValueError("Łączna wartość wyceny przekracza zakres bezpiecznych obliczeń.") from error
        if max(net_total, vat_amount, gross_total) > MAX_CALCULATION_TOTAL:
            raise ValueError("Łączna wartość wyceny nie może przekraczać 1 000 000 000 000 zł.")
        now = datetime.now().astimezone().isoformat(timespec="seconds")
        with closing(self._connect()) as connection, connection:
            customer = connection.execute(
                "SELECT * FROM customers WHERE user_id = ? AND name = ? COLLATE NOCASE",
                (user_id, header["customer_name"].strip()),
            ).fetchone()
            customer_id = customer["id"] if customer else None
            customer_address = (
                format_postal_address(dict(customer), prefix="")
                if customer
                else ""
            )
            if customer and not customer_address:
                customer_address = str(customer["address"] or "")
            customer_fields = {
                "customer_contact_person": customer["contact_person"] if customer else "",
                "customer_email": customer["email"] if customer else "",
                "customer_phone": customer["phone"] if customer else "",
                "customer_tax_id": customer["tax_id"] if customer else "",
                "customer_address": customer_address,
                "customer_address_legacy": customer["address_legacy"] if customer else "",
                "customer_street": customer["street"] if customer else "",
                "customer_building_number": customer["building_number"] if customer else "",
                "customer_unit_number": customer["unit_number"] if customer else "",
                "customer_postal_code": customer["postal_code"] if customer else "",
                "customer_city": customer["city"] if customer else "",
                "customer_country": customer["country"] if customer else "",
            }
            quote_number = self._unique_quote_number(
                connection,
                user_id,
                header["order_number"].strip(),
                header["customer_name"].strip(),
                estimate_id,
            )
            if estimate_id is None:
                cursor = connection.execute(
                    """
                    INSERT INTO estimates (
                        user_id, quote_number, customer_id, customer_name,
                        customer_contact_person, customer_email, customer_phone,
                        customer_tax_id, customer_address, customer_address_legacy,
                        customer_street, customer_building_number, customer_unit_number,
                        customer_postal_code, customer_city, customer_country,
                        order_number, notes, status, pricing_mode, net_total,
                        vat_amount, gross_total, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Obliczona', ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        user_id,
                        quote_number,
                        customer_id,
                        header["customer_name"].strip(),
                        customer_fields["customer_contact_person"],
                        customer_fields["customer_email"],
                        customer_fields["customer_phone"],
                        customer_fields["customer_tax_id"],
                        customer_fields["customer_address"],
                        customer_fields["customer_address_legacy"],
                        customer_fields["customer_street"],
                        customer_fields["customer_building_number"],
                        customer_fields["customer_unit_number"],
                        customer_fields["customer_postal_code"],
                        customer_fields["customer_city"],
                        customer_fields["customer_country"],
                        header["order_number"].strip(),
                        header.get("notes", "").strip(),
                        pricing_mode,
                        str(net_total),
                        str(vat_amount),
                        str(gross_total),
                        now,
                        now,
                    ),
                )
                estimate_id = int(cursor.lastrowid)
            else:
                cursor = connection.execute(
                    """
                    UPDATE estimates SET quote_number = ?, customer_id = ?, customer_name = ?,
                        customer_contact_person = ?, customer_email = ?,
                        customer_phone = ?, customer_tax_id = ?, customer_address = ?,
                        customer_address_legacy = ?, customer_street = ?,
                        customer_building_number = ?, customer_unit_number = ?,
                        customer_postal_code = ?, customer_city = ?, customer_country = ?,
                        order_number = ?, notes = ?, pricing_mode = ?, net_total = ?,
                        vat_amount = ?, gross_total = ?, updated_at = ?
                    WHERE id = ? AND user_id = ?
                    """,
                    (
                        quote_number,
                        customer_id,
                        header["customer_name"].strip(),
                        customer_fields["customer_contact_person"],
                        customer_fields["customer_email"],
                        customer_fields["customer_phone"],
                        customer_fields["customer_tax_id"],
                        customer_fields["customer_address"],
                        customer_fields["customer_address_legacy"],
                        customer_fields["customer_street"],
                        customer_fields["customer_building_number"],
                        customer_fields["customer_unit_number"],
                        customer_fields["customer_postal_code"],
                        customer_fields["customer_city"],
                        customer_fields["customer_country"],
                        header["order_number"].strip(),
                        header.get("notes", "").strip(),
                        pricing_mode,
                        str(net_total),
                        str(vat_amount),
                        str(gross_total),
                        now,
                        estimate_id,
                        user_id,
                    ),
                )
                if cursor.rowcount != 1:
                    raise ValueError("Nie znaleziono wyceny do edycji.")
                connection.execute(
                    "DELETE FROM estimate_items WHERE estimate_id = ?", (estimate_id,)
                )

            for position, item in enumerate(items, start=1):
                connection.execute(
                    """
                    INSERT INTO estimate_items (
                        estimate_id, position, element_name, material, thickness_mm,
                        calculation_mode, operation, quantity, price_per_kg, used_weight_kg, duration_seconds,
                        burning_rate_per_hour, vat_percent, material_cost,
                        burning_cost, unit_net, unit_vat, unit_gross, line_net,
                        line_vat, line_gross, preview_image, preview_image_name
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        estimate_id,
                        position,
                        item["element_name"],
                        item.get("material", ""),
                        item.get("thickness_mm", ""),
                        item.get("calculation_mode", "per_piece"),
                        item.get("operation", DEFAULT_OPERATION),
                        item["quantity"],
                        item["price_per_kg"],
                        item["used_weight_kg"],
                        item["duration_seconds"],
                        item["burning_rate_per_hour"],
                        item["vat_percent"],
                        item["material_cost"],
                        item["burning_cost"],
                        item["unit_net"],
                        item["unit_vat"],
                        item["unit_gross"],
                        item["line_net"],
                        item["line_vat"],
                        item["line_gross"],
                        bytes(item["preview_image"]) if item.get("preview_image") is not None else None,
                        item.get("preview_image_name", ""),
                    ),
                )
            return estimate_id

    def list_estimates(self, user_id: int, search: str = "", limit: int = 500) -> list[sqlite3.Row]:
        term = f"%{search.strip()}%"
        with closing(self._connect()) as connection, connection:
            return list(
                connection.execute(
                    """
                    SELECT e.*, COUNT(i.id) AS item_count
                    FROM estimates e
                    LEFT JOIN estimate_items i ON i.estimate_id = e.id
                    WHERE e.user_id = ?
                      AND (? = '%%' OR e.customer_name LIKE ? OR e.order_number LIKE ? OR e.quote_number LIKE ?)
                    GROUP BY e.id
                    ORDER BY e.created_at DESC, e.id DESC
                    LIMIT ?
                    """,
                    (user_id, term, term, term, term, limit),
                ).fetchall()
            )

    def get_estimate(self, user_id: int, estimate_id: int) -> dict[str, Any] | None:
        with closing(self._connect()) as connection, connection:
            header = connection.execute(
                "SELECT * FROM estimates WHERE id = ? AND user_id = ?",
                (estimate_id, user_id),
            ).fetchone()
            if header is None:
                return None
            items = connection.execute(
                "SELECT * FROM estimate_items WHERE estimate_id = ? ORDER BY position",
                (estimate_id,),
            ).fetchall()
            return {"header": dict(header), "items": [dict(item) for item in items]}

    def delete_estimate(self, user_id: int, estimate_id: int) -> None:
        with closing(self._connect()) as connection, connection:
            connection.execute(
                "DELETE FROM estimates WHERE id = ? AND user_id = ?",
                (estimate_id, user_id),
            )

    def backup(self, destination: str | Path) -> None:
        target = Path(destination)
        target.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as source, closing(sqlite3.connect(target)) as backup:
            source.backup(backup)

    @property
    def backup_directory(self) -> Path:
        return self.database_path.parent / "backups"

    def list_backups(self) -> list[Path]:
        if not self.backup_directory.is_dir():
            return []
        return sorted(
            self.backup_directory.glob("blachcalc-*.sqlite3"),
            key=lambda path: path.name,
            reverse=True,
        )

    def create_backup(self, reason: str = "auto", keep: int = 30) -> Path:
        label = re.sub(r"[^a-z0-9]+", "-", reason.lower()).strip("-") or "auto"
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        target = self.backup_directory / f"blachcalc-{stamp}-{label}.sqlite3"
        self.backup(target)
        for old_backup in self.list_backups()[max(1, keep):]:
            try:
                old_backup.unlink()
            except OSError:
                pass
        return target

    def create_backup_if_stale(self, max_age_hours: float = 12, reason: str = "start") -> Path | None:
        backups = self.list_backups()
        if backups:
            age_seconds = datetime.now().timestamp() - backups[0].stat().st_mtime
            if age_seconds < max_age_hours * 3600:
                return None
        return self.create_backup(reason)

    def restore_backup(self, source: str | Path) -> None:
        source_path = Path(source)
        try:
            with closing(sqlite3.connect(f"file:{source_path.as_posix()}?mode=ro", uri=True)) as check:
                if check.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                    raise ValueError("Wybrana kopia zapasowa jest uszkodzona.")
                tables = {row[0] for row in check.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        except sqlite3.Error as error:
            raise ValueError(f"Wybrany plik nie jest poprawną bazą BlachCalc: {error}") from error
        if not {"users", "estimates", "estimate_items"} <= tables:
            raise ValueError("Wybrany plik nie jest kopią zapasową BlachCalc.")
        self.create_backup("przed-przywroceniem")
        with closing(sqlite3.connect(source_path)) as source_connection, closing(self._connect()) as target:
            source_connection.backup(target)
        self._initialize()

    def save_quote(self, user_id: int, values: dict[str, Any]) -> None:
        with closing(self._connect()) as connection, connection:
            connection.execute(
                """
                INSERT INTO quotes (
                    user_id, customer, order_number, element_name, price_per_kg,
                    used_weight_kg, duration_seconds, burning_rate_per_hour,
                    vat_percent, material_cost, burning_cost, net_total,
                    vat_amount, gross_total, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id, values["customer"], values["order_number"], values["element_name"],
                    values["price_per_kg"], values["used_weight_kg"], values["duration_seconds"],
                    values["burning_rate_per_hour"], values["vat_percent"], values["material_cost"],
                    values["burning_cost"], values["net_total"], values["vat_amount"],
                    values["gross_total"], datetime.now().astimezone().isoformat(timespec="seconds"),
                ),
            )

    def list_quotes(self, user_id: int, limit: int = 100) -> list[sqlite3.Row]:
        with closing(self._connect()) as connection, connection:
            return list(
                connection.execute(
                    """
                    SELECT id, customer, order_number, element_name, net_total,
                           gross_total, created_at
                    FROM quotes WHERE user_id = ?
                    ORDER BY created_at DESC, id DESC LIMIT ?
                    """,
                    (user_id, limit),
                ).fetchall()
            )
