import csv
import os
import tempfile
from contextlib import contextmanager
from datetime import datetime, timedelta
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from typing import Any, BinaryIO, Iterator

from offer_page import CONTACT_FIELDS, SETTING_KEY as OFFER_PAGE_SETTING, parse_offer_page

def pl(value: Any) -> str:
    return f"{Decimal(value):.2f}".replace(".", ",")


PHOTO_WIDTH_MIN_MM = 25
PHOTO_WIDTH_MAX_MM = 56
PHOTO_WIDTH_DEFAULT_MM = 44


def photo_width_mm(settings: dict[str, Any]) -> float:
    try:
        value = float(str(settings.get("photo_width_mm", "")).replace(",", "."))
    except ValueError:
        return PHOTO_WIDTH_DEFAULT_MM
    return min(max(value, PHOTO_WIDTH_MIN_MM), PHOTO_WIDTH_MAX_MM)


@contextmanager
def _atomic_destination(destination: str | Path) -> Iterator[Path]:
    target = Path(destination)
    with tempfile.NamedTemporaryFile(
        prefix=f".{target.name}.",
        suffix=".tmp",
        dir=target.parent,
        delete=False,
    ) as temporary_file:
        temporary_path = Path(temporary_file.name)

    try:
        yield temporary_path
        temporary_path.replace(target)
    finally:
        temporary_path.unlink(missing_ok=True)


def _safe_spreadsheet_value(value: Any) -> Any:
    if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@", "\t", "\r")):
        return f"'{value}"
    return value


def export_estimate_csv(
    estimate: dict[str, Any],
    destination: str | Path,
    settings: dict[str, str] | None = None,
) -> None:
    header = estimate["header"]
    company = settings or {}
    fields = [
        "Numer wyceny",
        "Data",
        "Sprzedawca",
        "NIP sprzedawcy",
        "Adres sprzedawcy",
        "Telefon sprzedawcy",
        "E-mail sprzedawcy",
        "Strona sprzedawcy",
        "Zleceniodawca",
        "NIP klienta",
        "Adres klienta",
        "Numer zamówienia",
        "Uwagi",
        "Pozycja",
        "Zdjęcie poglądowe",
        "Materiał",
        "Grubość (mm)",
        "Sposób kalkulacji",
        "Ilość / zakres",
        "Cena materiału (zł/kg)",
        "Masa (kg/szt. lub razem)",
        "Czas palenia (sek./szt. lub razem)",
        "Stawka palenia (zł/godz.)",
        "VAT (%)",
        "Materiał netto / szt. (zł)",
        "Palenie netto / szt. (zł)",
        "Cena netto / szt. (zł)",
        "VAT / szt. (zł)",
        "Cena brutto / szt. (zł)",
        "Materiał netto razem (zł)",
        "Palenie netto razem (zł)",
        "Wartość netto (zł)",
        "VAT razem (zł)",
        "Wartość brutto (zł)",
    ]
    created_at = datetime.fromisoformat(header["created_at"]).astimezone().strftime("%Y-%m-%d %H:%M")
    with _atomic_destination(destination) as temporary_path:
        with temporary_path.open("w", encoding="utf-8-sig", newline="") as csv_file:
            writer = csv.writer(csv_file, delimiter=";")
            writer.writerow(fields)
            for item in estimate["items"]:
                whole_order = item.get("calculation_mode", "per_piece") == "whole_order"
                quantity = int(item["quantity"])
                material_total = Decimal(str(item["material_cost"])) * (1 if whole_order else quantity)
                burning_total = Decimal(str(item["burning_cost"])) * (1 if whole_order else quantity)
                unit_values = ("", "", "", "", "") if whole_order else (
                    item["material_cost"],
                    item["burning_cost"],
                    item["unit_net"],
                    item["unit_vat"],
                    item["unit_gross"],
                )
                writer.writerow(
                    _safe_spreadsheet_value(value)
                    for value in (
                        header["quote_number"],
                        created_at,
                        company.get("company_name", ""),
                        company.get("company_tax_id", ""),
                        company.get("company_address", ""),
                        company.get("company_phone", ""),
                        company.get("company_email", ""),
                        company.get("company_website", ""),
                        header["customer_name"],
                        header.get("customer_tax_id", ""),
                        header.get("customer_address", ""),
                        header["order_number"],
                        header.get("notes", ""),
                        item["element_name"],
                        "Tak" if item.get("preview_image") else "Nie",
                        item["material"],
                        item["thickness_mm"],
                        "Cała partia" if whole_order else "Na sztukę",
                        quantity,
                        item["price_per_kg"],
                        item["used_weight_kg"],
                        item["duration_seconds"],
                        item["burning_rate_per_hour"],
                        item["vat_percent"],
                        *unit_values,
                        material_total,
                        burning_total,
                        item["line_net"],
                        item["line_vat"],
                        item["line_gross"],
                    )
                )


def _render_estimate_pdf(
    estimate: dict[str, Any],
    settings: dict[str, str],
    destination: str | Path | BinaryIO,
    document_kind: str,
) -> None:
    try:
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_CENTER, TA_RIGHT
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.pdfgen.canvas import Canvas
        from reportlab.platypus import Image, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
        from xml.sax.saxutils import escape
    except ImportError as error:
        raise ImportError("Eksport PDF wymaga biblioteki ReportLab. Zainstaluj zależności poleceniem: python -m pip install -r requirements.txt") from error

    if document_kind not in {"offer", "internal"}:
        raise ValueError("Nieznany rodzaj dokumentu PDF.")

    header = estimate["header"]
    items = estimate["items"]
    navy = colors.HexColor(settings.get("brand_primary", "#243F82"))
    red = colors.HexColor(settings.get("brand_accent", "#ED1B24"))
    ink = colors.HexColor("#18345B")
    muted = colors.HexColor("#626262")
    border = colors.HexColor("#DADADA")
    page_size = A4 if document_kind == "offer" else landscape(A4)
    output_target = str(destination) if isinstance(destination, (str, Path)) else destination
    doc = SimpleDocTemplate(
        output_target,
        pagesize=page_size,
        leftMargin=15 * mm,
        rightMargin=15 * mm,
        topMargin=17 * mm,
        bottomMargin=18 * mm,
        title=f"{header['quote_number']} — BlachCalc",
        author=settings.get("company_name") or "BlachCalc",
    )

    font_regular = "Helvetica"
    font_bold = "Helvetica-Bold"
    content_width = doc.width - 12  # ramka SimpleDocTemplate ma 6 pt marginesu z każdej strony
    font_directory = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
    font_candidates = (
        (font_directory / "arial.ttf", font_directory / "arialbd.ttf", font_directory / "ariali.ttf", font_directory / "arialbi.ttf"),
        (font_directory / "segoeui.ttf", font_directory / "segoeuib.ttf", font_directory / "segoeuii.ttf", font_directory / "segoeuiz.ttf"),
        (font_directory / "tahoma.ttf", font_directory / "tahomabd.ttf", font_directory / "tahoma.ttf", font_directory / "tahomabd.ttf"),
        (Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"), Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
         Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Oblique.ttf"), Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-BoldOblique.ttf")),
    )
    for regular_font, bold_font, italic_font, bold_italic_font in font_candidates:
        if not (regular_font.is_file() and bold_font.is_file()):
            continue
        try:
            pdfmetrics.registerFont(TTFont("BlachCalcArial", str(regular_font)))
            pdfmetrics.registerFont(TTFont("BlachCalcArialBold", str(bold_font)))
            pdfmetrics.registerFont(TTFont("BlachCalcArialItalic", str(italic_font if italic_font.is_file() else regular_font)))
            pdfmetrics.registerFont(TTFont("BlachCalcArialBoldItalic", str(bold_italic_font if bold_italic_font.is_file() else bold_font)))
            # Bez rodziny znaczniki <b>/<i> w Paragraph wracają do Helvetica, która nie ma polskich liter.
            pdfmetrics.registerFontFamily(
                "BlachCalcArial",
                normal="BlachCalcArial",
                bold="BlachCalcArialBold",
                italic="BlachCalcArialItalic",
                boldItalic="BlachCalcArialBoldItalic",
            )
            font_regular = "BlachCalcArial"
            font_bold = "BlachCalcArialBold"
            break
        except (OSError, ValueError):
            continue
    else:
        raise OSError(
            "Nie znaleziono czcionki z polskimi znakami (Arial, Segoe UI, Tahoma lub DejaVu Sans). "
            "Wydruk bez niej zawierałby puste kwadraty zamiast liter."
        )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "BlachCalcTitle", parent=styles["Title"], fontName=font_bold,
        fontSize=19, leading=23, textColor=ink, spaceAfter=3,
    )
    subtitle_style = ParagraphStyle(
        "BlachCalcSubtitle", parent=styles["Normal"], fontName=font_regular,
        fontSize=10.5, leading=15, textColor=muted,
    )
    body_style = ParagraphStyle(
        "BlachCalcBody", parent=styles["Normal"], fontName=font_regular,
        fontSize=11.5, leading=16, textColor=ink,
    )
    cell_style = ParagraphStyle(
        "BlachCalcCell", parent=body_style, fontSize=9.5, leading=12,
    )
    header_cell_style = ParagraphStyle(
        "BlachCalcHeaderCell", parent=cell_style, textColor=colors.white,
        fontName=font_bold,
    )
    cell_right_style = ParagraphStyle(
        "BlachCalcRight", parent=cell_style, alignment=TA_RIGHT,
    )
    heading_style = ParagraphStyle(
        "BlachCalcHeading", parent=body_style, fontName=font_bold,
        fontSize=12.5, leading=15, spaceBefore=7, spaceAfter=4,
    )
    header_center_style = ParagraphStyle("BlachCalcHeaderCenter", parent=header_cell_style, alignment=TA_CENTER)
    header_right_style = ParagraphStyle("BlachCalcHeaderRight", parent=header_cell_style, alignment=TA_RIGHT)

    def offer_header_row(labels: tuple[str, ...]) -> list[Any]:
        alignments = (header_center_style, header_cell_style, header_center_style, header_center_style,
                      header_right_style, header_right_style, header_right_style)
        return [Paragraph(f"<b>{escape(label)}</b>", style) for label, style in zip(labels, alignments)]
    story: list[Any] = []
    logo_path = settings.get("logo_path", "")
    company_name = settings.get("company_name", "").strip() or "Izo-Technika Iłczyk Sp. Jawna"
    company_details = [
        settings.get("company_address", "").strip(),
        f"NIP: {settings['company_tax_id'].strip()}" if settings.get("company_tax_id", "").strip() else "",
        "  |  ".join(
            value for value in (
                settings.get("company_phone", "").strip(),
                settings.get("company_email", "").strip(),
            ) if value
        ),
        settings.get("company_website", "").strip(),
    ]
    logo_file: Path | None = None
    if logo_path:
        logo_file = Path(logo_path)
        if not logo_file.is_file():
            raise ValueError(f"Nie znaleziono pliku logo: {logo_file}")
    def make_brand_header() -> Any:
        brand_logo = None
        if logo_file is not None:
            try:
                brand_logo = Image(
                    str(logo_file), width=62 * mm, height=18 * mm, kind="proportional"
                )
            except (OSError, ValueError) as error:
                raise ValueError(f"Nie można odczytać wybranego pliku logo: {error}") from error
        details = Paragraph(
            f"<b>{escape(company_name)}</b><br/>"
            + "<br/>".join(escape(line) for line in company_details if line),
            ParagraphStyle(
                "BlachCalcCompanyDetails", parent=subtitle_style, alignment=TA_RIGHT,
                fontSize=9.5, leading=13, textColor=ink,
            ),
        )
        header = Table(
            [[brand_logo or Paragraph(escape(company_name), title_style), details]],
            colWidths=[content_width * 0.43, content_width * 0.57],
        )
        header.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN", (0, 0), (0, 0), "LEFT"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 2),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ("LINEBELOW", (0, 0), (-1, -1), 1.6, red),
        ]))
        return header

    story.extend((make_brand_header(), Spacer(1, 5 * mm)))

    document_title = "OFERTA HANDLOWA" if document_kind == "offer" else "KARTA KALKULACJI KOSZTÓW"
    story.append(Paragraph(document_title, ParagraphStyle(
        "BlachCalcDocumentKind", parent=subtitle_style, fontName=font_bold,
        fontSize=16.5, leading=20, textColor=navy, spaceAfter=3,
    )))
    story.append(Spacer(1, 6 * mm))

    created_at = datetime.fromisoformat(header["created_at"]).astimezone()
    client_details = [
        f"<b>Zleceniodawca:</b> {escape(header['customer_name'])}",
    ]
    if str(header.get("order_number", "")).strip():
        client_details.append(f"<b>Numer zamówienia:</b> {escape(str(header['order_number']).strip())}")
    for key, label in (
        ("customer_contact_person", "Osoba kontaktowa"),
        ("customer_address", "Adres"),
        ("customer_tax_id", "NIP"),
        ("customer_email", "E-mail"),
        ("customer_phone", "Telefon"),
    ):
        value = str(header.get(key, "")).strip()
        if value:
            client_details.append(f"<b>{label}:</b> {escape(value)}")
    left_block = Paragraph("<br/>".join(client_details), body_style)
    right_block = Paragraph(
        f"<b>Numer wyceny:</b> {escape(header['quote_number'])}<br/>"
        f"<b>Data:</b> {created_at.strftime('%d.%m.%Y %H:%M')}",
        ParagraphStyle("BlachCalcMetadata", parent=body_style, alignment=TA_RIGHT),
    )
    metadata = Table([[left_block, right_block]], colWidths=[content_width * 0.61, content_width * 0.39])
    metadata.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F6F6F6")),
        ("BOX", (0, 0), (-1, -1), 0.5, border),
        ("LEFTPADDING", (0, 0), (-1, -1), 9),
        ("RIGHTPADDING", (0, 0), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.extend((metadata, Spacer(1, 7 * mm)))

    vat_lines: dict[str, Decimal] = {}
    for item in items:
        vat_key = f"{Decimal(item['vat_percent']):g}%"
        vat_lines[vat_key] = vat_lines.get(vat_key, Decimal("0")) + Decimal(item["line_vat"])

    photo_width = photo_width_mm(settings) * mm

    def preview_image(item: dict[str, Any]) -> Any:
        image_data = item.get("preview_image")
        if not image_data:
            return ""
        if isinstance(image_data, memoryview):
            image_data = image_data.tobytes()
        try:
            return Image(
                BytesIO(bytes(image_data)),
                width=photo_width,
                height=photo_width * 32 / 44,
                kind="proportional",
            )
        except (OSError, TypeError, ValueError) as error:
            raise ValueError(
                f"Nie można odczytać zdjęcia pozycji „{item['element_name']}”: {error}"
            ) from error

    if document_kind == "offer":
        if header.get("pricing_mode", "itemized") == "total_only":
            headers = ("Lp.", "Zakres oferty", "Zdjęcie", "Ilość", "Wartość netto", "Wartość brutto")
            rows: list[list[Any]] = [offer_header_row(headers)]
            total_quantity = sum(int(item["quantity"]) for item in items)
            rows.append([
                "1",
                Paragraph("Kompleksowa realizacja wypalanych elementów", cell_style),
                preview_image(next((item for item in items if item.get("preview_image")), {})),
                str(total_quantity),
                Paragraph(f"{pl(Decimal(header['net_total']))} zł", cell_right_style),
                Paragraph(f"<b>{pl(Decimal(header['gross_total']))} zł</b>", cell_right_style),
            ])
            widths = [9 * mm, 40 * mm, photo_width + 4 * mm, 14 * mm, 24 * mm, 26 * mm]
            heading = "Cena całego zamówienia"
        else:
            headers = ("Lp.", "Element / zakres", "Zdjęcie", "Ilość", "Masa szt.", "Netto", "Brutto")
            rows = [offer_header_row(headers)]
            for index, item in enumerate(items, start=1):
                whole_order = item.get("calculation_mode", "per_piece") == "whole_order"
                description = escape(str(item["element_name"]))
                if item.get("material"):
                    description += f"<br/><font color='#626262'>{escape(str(item['material']))}"
                    if item.get("thickness_mm"):
                        description += f" · {escape(str(item['thickness_mm']))} mm"
                    description += "</font>"
                rows.append([
                    str(index),
                    Paragraph(description, cell_style),
                    preview_image(item),
                    str(item["quantity"]),
                    "—" if whole_order else f"{Decimal(item['used_weight_kg']):.3f}".replace(".", ",") + " kg",
                    Paragraph(f"{pl(Decimal(item['line_net']))} zł", cell_right_style),
                    Paragraph(f"<b>{pl(Decimal(item['line_gross']))} zł</b>", cell_right_style),
                ])
            widths = [9 * mm, 40 * mm, photo_width + 4 * mm, 14 * mm, 19 * mm, 23 * mm, 25 * mm]
            heading = "Zestawienie pozycji oferty"
    else:
        headers = ("Element / materiał", "Ilość / zakres", "Cena zł/kg", "Masa kg/szt. lub razem", "Czas/szt. lub razem", "Stawka/godz.", "Materiał razem", "Palenie razem", "Netto razem", "Brutto razem")
        rows = [[Paragraph(f"<b>{escape(value)}</b>", header_cell_style) for value in headers]]
        for item in items:
            whole_order = item.get("calculation_mode", "per_piece") == "whole_order"
            quantity = int(item["quantity"])
            factor = 1 if whole_order else quantity
            description = escape(str(item["element_name"]))
            details = " · ".join(
                part for part in (
                    str(item.get("material", "")).strip(),
                    f"{item['thickness_mm']} mm" if item.get("thickness_mm") else "",
                ) if part
            )
            if details:
                description += f"<br/><font color='#626262'>{escape(details)}</font>"
            rows.append([
                Paragraph(description, cell_style),
                str(item["quantity"]),
                f"{Decimal(item['price_per_kg']):.2f}",
                f"{Decimal(item['used_weight_kg']):.3f}",
                _duration_label(int(item["duration_seconds"])),
                f"{Decimal(item['burning_rate_per_hour']):.2f}",
                f"{Decimal(item['material_cost']) * factor:.2f} zł",
                f"{Decimal(item['burning_cost']) * factor:.2f} zł",
                f"{Decimal(item['line_net']):.2f} zł",
                f"{Decimal(item['line_gross']):.2f} zł",
            ])
        widths = [43 * mm, 11 * mm, 17 * mm, 18 * mm, 20 * mm, 19 * mm, 23 * mm, 22 * mm, 25 * mm, 25 * mm]
        heading = "Szczegółowa kalkulacja kosztów"

    story.append(Paragraph(heading, heading_style))
    if document_kind == "offer":
        if not any(item.get("preview_image") for item in items):
            rows = [row[:2] + row[3:] for row in rows]
            widths = widths[:2] + widths[3:]
        widths[1] = content_width - (sum(widths) - widths[1])
    table = Table(rows, colWidths=widths, repeatRows=1, hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), navy),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), font_bold),
        ("FONTNAME", (0, 1), (-1, -1), font_regular),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.35, border),
        ("BACKGROUND", (0, 1), (-1, -1), colors.white),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), (colors.white, colors.HexColor("#FAFAFA"))),
        ("ALIGN", (0, 0), (0, -1), "CENTER"),
        ("ALIGN", (2, 1), (-1, -1), "RIGHT" if document_kind == "internal" else "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    story.append(table)

    net_total = Decimal(header["net_total"])
    gross_total = Decimal(header["gross_total"])
    money = pl if document_kind == "offer" else (lambda value: f"{value:.2f}")
    totals = [
        ["Razem netto", f"{money(net_total)} zł"],
        *[[f"VAT {rate}", f"{money(amount)} zł"] for rate, amount in vat_lines.items()],
        ["Razem brutto", f"{money(gross_total)} zł"],
    ]
    totals_table = Table(
        [[Paragraph(f"<b>{escape(label)}</b>", body_style), Paragraph(f"<b>{escape(amount)}</b>", cell_right_style)] for label, amount in totals],
        colWidths=[38 * mm, 35 * mm],
        hAlign="RIGHT",
    )
    totals_table.setStyle(TableStyle([
        ("LINEABOVE", (0, 0), (-1, 0), 0.5, border),
        ("LINEABOVE", (0, -1), (-1, -1), 1.1, red),
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#F0F3FA")),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(KeepTogether([Spacer(1, 5 * mm), totals_table]))

    offer_conditions = []
    validity_days = settings.get("offer_validity_days", "").strip()
    if validity_days:
        valid_until = ""
        if validity_days.isdigit():
            valid_until = f" (do {(created_at + timedelta(days=int(validity_days))).strftime('%d.%m.%Y')})"
        offer_conditions.append(f"<b>Ważność oferty:</b> {escape(validity_days)} dni od daty wystawienia{valid_until}")
    for key, label in (
        ("payment_terms", "Warunki płatności"),
        ("delivery_terms", "Termin realizacji"),
    ):
        value = settings.get(key, "").strip()
        if value:
            offer_conditions.append(f"<b>{label}:</b> {escape(value)}")
    if document_kind == "offer" and offer_conditions:
        story.extend((
            Spacer(1, 5 * mm),
            Paragraph("Warunki oferty", heading_style),
            Paragraph("<br/>".join(offer_conditions), body_style),
        ))

    notes = str(header.get("notes", "")).strip()
    if notes:
        story.extend((Spacer(1, 5 * mm), Paragraph("Uwagi", heading_style), Paragraph(escape(notes).replace("\n", "<br/>"), body_style)))

    if document_kind == "offer":
        terms_style = ParagraphStyle(
            "BlachCalcOfferTerms", parent=body_style, fontSize=9,
            leading=11.6, leftIndent=9, firstLineIndent=-7, spaceAfter=2,
        )
        page2 = parse_offer_page(settings.get(OFFER_PAGE_SETTING, ""))
        section_style = ParagraphStyle(
            "BlachCalcSection", parent=heading_style, textColor=ink,
            fontSize=13, leading=16, spaceBefore=0, spaceAfter=0,
        )

        def section_heading(text: str) -> Any:
            block = Table([[Paragraph(escape(text), section_style)]], colWidths=[content_width], hAlign="LEFT")
            block.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F0F3FA")),
                ("LINEBEFORE", (0, 0), (0, 0), 3, red),
                ("LINEBELOW", (0, 0), (-1, 0), 0.6, navy),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]))
            block.keepWithNext = True
            return KeepTogether([Spacer(1, 3 * mm), block, Spacer(1, 2 * mm)])

        def bullet_list(key: str) -> list[Any]:
            return [Paragraph(f"- {escape(term)}", terms_style) for term in page2[key]["items"]]

        def titled(key: str, content: list[Any]) -> list[Any]:
            title = page2[key]["title"]
            return [section_heading(title), *content] if title else content

        story.extend((PageBreak(), make_brand_header(), *titled("terms", bullet_list("terms"))))
        pallet_rows = [[line] for line in page2["pallets"]["items"]]
        pallet_table = Table(pallet_rows or [[""]], colWidths=[76 * mm], hAlign="LEFT")
        pallet_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FAFAFA")),
            ("GRID", (0, 0), (-1, -1), 0.35, border),
            ("FONTNAME", (0, 0), (-1, -1), font_regular),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ]))
        contact_label_style = ParagraphStyle(
            "BlachCalcContactLabel", parent=cell_style, fontSize=8, leading=10, textColor=muted,
        )
        contact_value_style = ParagraphStyle(
            "BlachCalcContactValue", parent=cell_style, fontSize=11, leading=14, textColor=ink, fontName=font_bold,
        )
        contacts = [
            [Paragraph("OSOBA KONTAKTOWA", contact_label_style), Paragraph("TELEFON", contact_label_style), Paragraph("E-MAIL", contact_label_style)],
            [
                Paragraph(escape(page2["contact"]["person"]), contact_value_style),
                Paragraph(escape(page2["contact"]["phone"]), contact_value_style),
                Paragraph(escape(page2["contact"]["email"]), contact_value_style),
            ],
        ]
        contacts_table = Table(contacts, colWidths=[50 * mm, 40 * mm, 70 * mm], hAlign="LEFT")
        contacts_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F0F3FA")),
            ("LINEBEFORE", (0, 0), (0, -1), 3, red),
            ("LINEAFTER", (0, 0), (1, -1), 0.35, border),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 9),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, 0), 6),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 0),
            ("TOPPADDING", (0, 1), (-1, 1), 1),
            ("BOTTOMPADDING", (0, 1), (-1, 1), 7),
        ]))
        story.extend(titled("claims", bullet_list("claims")))
        if page2["pallets"]["items"]:
            story.extend(titled("pallets", [pallet_table]))
        if any(page2["contact"][field] for field in CONTACT_FIELDS):
            story.extend(titled("contact", [contacts_table]))

    footer_text = (
        "Dokument wewnętrzny — kalkulacja kosztów produkcyjnych."
        if document_kind == "internal"
        else "Oferta handlowa — dokument nie jest fakturą VAT."
    )

    def footer(canvas: Any, page_count: int) -> None:
        canvas.saveState()
        canvas.setStrokeColor(border)
        canvas.line(15 * mm + 6, 13 * mm, page_size[0] - 15 * mm - 6, 13 * mm)
        canvas.setFont(font_regular, 6.5)
        canvas.setFillColor(muted)
        company_footer = "  |  ".join(
            value for value in (
                company_name,
                settings.get("company_tax_id", "").strip(),
                settings.get("company_website", "").strip(),
            ) if value
        )
        canvas.drawString(15 * mm + 6, 8 * mm, f"{company_footer}  |  {footer_text}")
        canvas.drawRightString(page_size[0] - 15 * mm - 6, 8 * mm, f"Strona {canvas.getPageNumber()} z {page_count}")
        canvas.restoreState()

    class NumberedCanvas(Canvas):
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__(*args, **kwargs)
            self._saved_pages: list[dict[str, Any]] = []

        def showPage(self) -> None:
            self._saved_pages.append(dict(self.__dict__))
            self._startPage()

        def save(self) -> None:
            page_count = len(self._saved_pages)
            for state in self._saved_pages:
                self.__dict__.update(state)
                footer(self, page_count)
                super().showPage()
            super().save()

    doc.build(story, canvasmaker=NumberedCanvas)


def export_estimate_pdf(
    estimate: dict[str, Any],
    settings: dict[str, str],
    destination: str | Path | BinaryIO,
    document_kind: str,
) -> None:
    if isinstance(destination, (str, Path)):
        with _atomic_destination(destination) as temporary_path:
            _render_estimate_pdf(estimate, settings, temporary_path, document_kind)
        return

    _render_estimate_pdf(estimate, settings, destination, document_kind)


def _duration_label(seconds: int) -> str:
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02}:{minutes:02}:{seconds:02}"
