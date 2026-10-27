from app_paths import excel_export_directory, offer_export_directory, wz_export_directory


BACKGROUND = "#F2F5F9"
WHITE = "#FFFFFF"
INK = "#172B4D"
MUTED = "#64748B"
NAVY = "#173B63"
NAVY_DARK = "#102A47"
ACCENT = NAVY
ACCENT_DARK = NAVY_DARK
BRAND_RED = "#ED1B24"
GREEN = "#18794E"
BORDER = "#DCE4EE"
PALE_RED = "#FBECEE"
LOGIN_ENABLED = False
MAX_PREVIEW_IMAGE_BYTES = 10 * 1024 * 1024
DELIVERY_NOTE_DRAFT_SETTING = "delivery_note_draft"
QUOTE_FIELD_ENTRY_WIDTH = 21
QUOTE_FIELD_COMBO_WIDTH = 19
OFFER_EXPORT_DIRECTORY = offer_export_directory()
WZ_EXPORT_DIRECTORY = wz_export_directory()
EXCEL_EXPORT_DIRECTORY = excel_export_directory()


class FieldValidationError(ValueError):
    def __init__(self, message: str, field: str | None = None) -> None:
        super().__init__(message)
        self.field = field
