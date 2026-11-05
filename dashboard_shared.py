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
UI_SCALE_MIN_PERCENT = 75
UI_SCALE_MAX_PERCENT = 250


def parse_ui_scale_percent(value: object) -> int:
    try:
        percent = int(str(value).strip())
    except ValueError:
        return 100
    return min(UI_SCALE_MAX_PERCENT, max(UI_SCALE_MIN_PERCENT, percent))


DARK_THEME_COLORS = {
    "#F2F5F9": "#0E1622",
    "#FFFFFF": "#182433",
    "#172B4D": "#F1F6FC",
    "#64748B": "#BAC8D8",
    "#173B63": "#4C93E6",
    "#102A47": "#326FA8",
    "#DCE4EE": "#3D5067",
    "#FBECEE": "#4B252B",
    "#18794E": "#78D9A5",
    "#E7EDF5": "#2C4058",
    "#F6F8FB": "#24364B",
    "#F4F6F8": "#293B50",
    "#9AA6B5": "#A6B6C8",
    "#A7B5C6": "#52647A",
    "#E8EEF5": "#354D67",
    "#42536B": "#BDCAD9",
    "#F1F5F9": "#243143",
    "#EAF1F8": "#30465F",
    "#E1EAF4": "#405B78",
    "#F4F7FB": "#2A3D53",
    "#EAF0F6": "#263548",
    "#344B68": "#C3D0E0",
    "#DFE8F2": "#34465C",
    "#DCE9F7": "#30445C",
    "#E2E8F0": "#344255",
    "#CBD5E1": "#46566B",
    "#E8EDF3": "#263548",
    "#E1E8F0": "#34465C",
    "#F4F7FB": "#202C3A",
    "#F8FAFC": "#1D2A39",
    "#F7F9FC": "#1D2937",
    "#F7F8FA": "#202C3A",
    "#F6F8FC": "#202C3A",
    "#E8EFF8": "#26374B",
    "#E7EDF4": "#111B28",
    "#F6F8FB": "#1D2A39",
    "#E8EEF8": "#26374B",
    "#626262": "#A6B4C5",
    "#243F82": "#8EB7E5",
    "#B42332": "#FF8A96",
    "#8F1D29": "#FF7484",
    "#FFF4F4": "#3A2229",
    "#B42318": "#FF8A96",
    "#18345B": "#E5EDF6",
    "#DADADA": "#344255",
    "#FAFAFA": "#1D2937",
    "#F0F3FA": "#243143",
    "#DCE8F7": "#30445C",
    "#395B91": "#536E91",
    "#5B6B84": "#A6B4C5",
    "#5485BE": "#314765",
    "#B9C5D5": "#344255",
    "#E7EDF4": "#111B28",
}

THEME_PALETTE_DEFAULTS = {
    "background": ("#F2F5F9", "#0E1622", "Tło okna"),
    "surface": ("#FFFFFF", "#182433", "Karty i pola"),
    "text": ("#172B4D", "#F1F6FC", "Tekst główny"),
    "muted": ("#64748B", "#BAC8D8", "Tekst pomocniczy"),
    "accent": ("#173B63", "#4C93E6", "Akcent główny"),
    "accent_pressed": ("#102A47", "#326FA8", "Akcent wciśnięty"),
    "accent_secondary": ("#ED1B24", "#FF7E87", "Akcent dodatkowy"),
    "border": ("#DCE4EE", "#3D5067", "Obramowania"),
    "hover": ("#F6F8FB", "#24364B", "Podświetlenie"),
    "subtle": ("#F4F7FB", "#202C3A", "Tło pomocnicze"),
    "selection": ("#DCE9F7", "#30445C", "Zaznaczenie"),
    "disabled_surface": ("#F4F6F8", "#293B50", "Tło nieaktywne"),
    "disabled_text": ("#9AA6B5", "#A6B6C8", "Tekst nieaktywny"),
    "success": ("#18794E", "#78D9A5", "Komunikat poprawny"),
    "danger": ("#B42332", "#FF8A96", "Błąd i usuwanie"),
    "danger_hover": ("#8F1D29", "#FF7484", "Błąd po wskazaniu"),
    "danger_surface": ("#FFF4F4", "#3A2229", "Tło błędu"),
}
THEME_PALETTE_SETTINGS = {
    f"ui_{mode}_{role}": (colors[0 if mode == "light" else 1], colors[2])
    for role, colors in THEME_PALETTE_DEFAULTS.items()
    for mode in ("light", "dark")
}
_THEME_COLOR_ROLES = {
    "#F2F5F9": "background",
    "#FFFFFF": "surface",
    "#172B4D": "text",
    "#64748B": "muted",
    "#173B63": "accent",
    "#102A47": "accent_pressed",
    "#ED1B24": "accent_secondary",
    "#DCE4EE": "border",
    "#F6F8FB": "hover",
    "#E8EEF5": "hover",
    "#E1EAF4": "hover",
    "#E1E8F0": "hover",
    "#E7EDF5": "hover",
    "#DFE8F2": "hover",
    "#E8EEF8": "hover",
    "#F4F7FB": "subtle",
    "#F7F9FC": "subtle",
    "#EAF0F6": "subtle",
    "#F8FAFC": "subtle",
    "#F7F8FA": "subtle",
    "#F6F8FC": "subtle",
    "#F1F5F9": "subtle",
    "#F0F3FA": "subtle",
    "#FAFAFA": "subtle",
    "#E7EDF4": "subtle",
    "#E8EFF8": "subtle",
    "#EAF1F8": "subtle",
    "#DCE9F7": "selection",
    "#DCE8F7": "selection",
    "#F4F6F8": "disabled_surface",
    "#9AA6B5": "disabled_text",
    "#A7B5C6": "disabled_text",
    "#626262": "muted",
    "#42536B": "muted",
    "#344B68": "muted",
    "#5B6B84": "muted",
    "#C7D3E1": "border",
    "#CBD5E1": "border",
    "#DADADA": "border",
    "#E2E8F0": "border",
    "#E8EDF3": "border",
    "#B9C5D5": "border",
    "#18794E": "success",
    "#B42332": "danger",
    "#B42318": "danger",
    "#8F1D29": "danger_hover",
    "#ED1B24": "accent_secondary",
    "#FFF4F4": "danger_surface",
    "#FBECEE": "danger_surface",
    "#243F82": "accent",
    "#18345B": "accent",
}


def theme_color(
    value: str,
    dark_mode: bool,
    settings: dict[str, str] | None = None,
) -> str:
    if settings is not None:
        normalized = value.upper()
        role = _THEME_COLOR_ROLES.get(normalized)
        if role is None:
            role = next(
                (
                    candidate
                    for light_value, dark_value in DARK_THEME_COLORS.items()
                    if normalized == dark_value.upper()
                    for candidate in (_THEME_COLOR_ROLES.get(light_value.upper()),)
                    if candidate is not None
                ),
                None,
            )
        if role is not None:
            mode = "dark" if dark_mode else "light"
            default = THEME_PALETTE_DEFAULTS[role][1 if dark_mode else 0]
            return settings.get(f"ui_{mode}_{role}", default)
    if dark_mode:
        return DARK_THEME_COLORS.get(value.upper(), value)
    inverse = {dark: light for light, dark in DARK_THEME_COLORS.items()}
    return inverse.get(value.upper(), value)


def contrasting_text_color(background: str) -> str:
    def relative_luminance(color: str) -> float:
        channels = (
            int(color[index:index + 2], 16) / 255
            for index in (1, 3, 5)
        )
        red, green, blue = (
            channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4
            for channel in channels
        )
        return 0.2126 * red + 0.7152 * green + 0.0722 * blue

    background_luminance = relative_luminance(background)
    ink_luminance = relative_luminance(INK)
    white_contrast = 1.05 / (background_luminance + 0.05)
    ink_contrast = (background_luminance + 0.05) / (ink_luminance + 0.05)
    return INK if ink_contrast >= white_contrast else WHITE


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
