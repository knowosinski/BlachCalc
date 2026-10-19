import csv
import os
from datetime import datetime
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from typing import Any, BinaryIO


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
    with Path(destination).open("w", encoding="utf-8-sig", newline="") as csv_file:
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


def export_estimate_pdf(
    estimate: dict[str, Any],
    settings: dict[str, str],
    destination: str | Path | BinaryIO,
    document_kind: str,
) -> None:
    try:
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_RIGHT
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
        from xml.sax.saxutils import escape
    except ImportError as error:
        raise ImportError("Eksport PDF wymaga biblioteki ReportLab. Zainstaluj zależności poleceniem: python -m pip install -r requirements.txt") from error

    if document_kind not in {"offer", "internal"}:
        raise ValueError("Nieznany rodzaj dokumentu PDF.")

    header = estimate["header"]
    items = estimate["items"]
    navy = colors.HexColor(settings.get("brand_primary", "#243F82"))
    red = colors.HexColor(settings.get("brand_accent", "#ED1B24"))
    ink = colors.HexColor("#18243A")
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
    font_directory = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
    regular_font = font_directory / "arial.ttf"
    bold_font = font_directory / "arialbd.ttf"
    if regular_font.is_file() and bold_font.is_file():
        try:
            pdfmetrics.registerFont(TTFont("BlachCalcArial", str(regular_font)))
            pdfmetrics.registerFont(TTFont("BlachCalcArialBold", str(bold_font)))
            font_regular = "BlachCalcArial"
            font_bold = "BlachCalcArialBold"
        except (OSError, ValueError):
            pass

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "BlachCalcTitle", parent=styles["Title"], fontName=font_bold,
        fontSize=19, leading=23, textColor=ink, spaceAfter=3,
    )
    subtitle_style = ParagraphStyle(
        "BlachCalcSubtitle", parent=styles["Normal"], fontName=font_regular,
        fontSize=9, leading=13, textColor=muted,
    )
    body_style = ParagraphStyle(
        "BlachCalcBody", parent=styles["Normal"], fontName=font_regular,
        fontSize=8.5, leading=12, textColor=ink,
    )
    cell_style = ParagraphStyle(
        "BlachCalcCell", parent=body_style, fontSize=7.5, leading=10,
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
        fontSize=10, leading=13, spaceBefore=7, spaceAfter=4,
    )
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
    company_block = Paragraph(
        f"<b>{escape(company_name)}</b><br/>"
        + "<br/>".join(escape(line) for line in company_details if line),
        ParagraphStyle(
            "BlachCalcCompanyDetails", parent=subtitle_style, alignment=TA_RIGHT,
            fontSize=8, leading=11, textColor=ink,
        ),
    )
    brand_logo = None
    if logo_path:
        logo_file = Path(logo_path)
        if not logo_file.is_file():
            raise ValueError(f"Nie znaleziono pliku logo: {logo_file}")
        try:
            brand_logo = Image(str(logo_file), width=62 * mm, height=18 * mm, kind="proportional")
        except (OSError, ValueError) as error:
            raise ValueError(f"Nie można odczytać wybranego pliku logo: {error}") from error
    brand_header = Table(
        [[brand_logo or Paragraph(escape(company_name), title_style), company_block]],
        colWidths=[doc.width * 0.43, doc.width * 0.57],
    )
    brand_header.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (0, 0), "LEFT"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ("LINEBELOW", (0, 0), (-1, -1), 1.6, red),
    ]))
    story.extend((brand_header, Spacer(1, 5 * mm)))

    document_title = "OFERTA CENOWA" if document_kind == "offer" else "KARTA KALKULACJI KOSZTÓW"
    story.append(Paragraph(document_title, ParagraphStyle(
        "BlachCalcDocumentKind", parent=subtitle_style, fontName=font_bold,
        fontSize=12, textColor=navy, spaceAfter=3,
    )))
    story.append(Spacer(1, 6 * mm))

    created_at = datetime.fromisoformat(header["created_at"]).astimezone()
    client_details = [
        f"<b>Zleceniodawca:</b> {escape(header['customer_name'])}",
        f"<b>Numer zamówienia:</b> {escape(header['order_number'])}",
    ]
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
    metadata = Table([[left_block, right_block]], colWidths=[doc.width * 0.61, doc.width * 0.39])
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

    def preview_image(item: dict[str, Any]) -> Any:
        image_data = item.get("preview_image")
        if not image_data:
            return ""
        if isinstance(image_data, memoryview):
            image_data = image_data.tobytes()
        try:
            return Image(
                BytesIO(bytes(image_data)),
                width=16 * mm,
                height=12 * mm,
                kind="proportional",
            )
        except (OSError, TypeError, ValueError) as error:
            raise ValueError(
                f"Nie można odczytać zdjęcia pozycji „{item['element_name']}”: {error}"
            ) from error

    if document_kind == "offer":
        if header.get("pricing_mode", "itemized") == "total_only":
            headers = ("Lp.", "Zakres oferty", "Zdjęcie", "Ilość", "Wartość netto", "VAT", "Wartość brutto")
            rows: list[list[Any]] = [[Paragraph(f"<b>{escape(value)}</b>", header_cell_style) for value in headers]]
            vat_label = ", ".join(vat_lines) + " VAT" if vat_lines else "VAT"
            total_quantity = sum(int(item["quantity"]) for item in items)
            rows.append([
                "1",
                Paragraph("Kompleksowa realizacja wypalanych elementów", cell_style),
                preview_image(next((item for item in items if item.get("preview_image")), {})),
                str(total_quantity),
                Paragraph(f"{Decimal(header['net_total']):.2f} zł", cell_right_style),
                Paragraph(f"{Decimal(header['vat_amount']):.2f} zł<br/><font color='#626262'>{escape(vat_label)}</font>", cell_right_style),
                Paragraph(f"<b>{Decimal(header['gross_total']):.2f} zł</b>", cell_right_style),
            ])
            widths = [7 * mm, 39 * mm, 20 * mm, 22 * mm, 29 * mm, 28 * mm, 30 * mm]
            heading = "Cena całego zamówienia"
        else:
            headers = ("Lp.", "Element / zakres", "Zdjęcie", "Ilość / zakres", "Netto", "VAT", "Brutto")
            rows = [[Paragraph(f"<b>{escape(value)}</b>", header_cell_style) for value in headers]]
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
                    Paragraph(f"{Decimal(item['line_net']):.2f} zł", cell_right_style),
                    Paragraph(f"{Decimal(item['line_vat']):.2f} zł<br/><font color='#626262'>{item['vat_percent']}%</font>", cell_right_style),
                    Paragraph(f"<b>{Decimal(item['line_gross']):.2f} zł</b>", cell_right_style),
                ])
            widths = [7 * mm, 39 * mm, 20 * mm, 22 * mm, 29 * mm, 28 * mm, 30 * mm]
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
    table = Table(rows, colWidths=widths, repeatRows=1, hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), navy),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), font_bold),
        ("FONTNAME", (0, 1), (-1, -1), font_regular),
        ("FONTSIZE", (0, 0), (-1, -1), 7),
        ("GRID", (0, 0), (-1, -1), 0.35, border),
        ("BACKGROUND", (0, 1), (-1, -1), colors.white),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), (colors.white, colors.HexColor("#FAFAFA"))),
        ("ALIGN", (0, 0), (0, -1), "CENTER"),
        ("ALIGN", (2, 1), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    story.append(table)
    story.append(Spacer(1, 5 * mm))

    net_total = Decimal(header["net_total"])
    vat_total = Decimal(header["vat_amount"])
    gross_total = Decimal(header["gross_total"])
    totals = [
        ["Razem netto", f"{net_total:.2f} zł"],
        *[[f"VAT {rate}", f"{amount:.2f} zł"] for rate, amount in vat_lines.items()],
        ["Razem brutto", f"{gross_total:.2f} zł"],
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
    story.append(totals_table)

    offer_conditions = []
    validity_days = settings.get("offer_validity_days", "").strip()
    if validity_days:
        offer_conditions.append(f"<b>Ważność oferty:</b> {escape(validity_days)} dni od daty wystawienia")
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

    footer_text = (
        "Dokument wewnętrzny — kalkulacja kosztów produkcyjnych."
        if document_kind == "internal"
        else "Oferta cenowa — dokument nie jest fakturą VAT."
    )

    def footer(canvas: Any, _document: Any) -> None:
        canvas.saveState()
        canvas.setStrokeColor(border)
        canvas.line(15 * mm, 13 * mm, page_size[0] - 15 * mm, 13 * mm)
        canvas.setFont(font_regular, 6.5)
        canvas.setFillColor(muted)
        company_footer = "  |  ".join(
            value for value in (
                company_name,
                settings.get("company_tax_id", "").strip(),
                settings.get("company_website", "").strip(),
            ) if value
        )
        canvas.drawString(15 * mm, 8 * mm, f"{company_footer}  |  {footer_text}")
        canvas.drawRightString(page_size[0] - 15 * mm, 8 * mm, f"Strona {canvas.getPageNumber()}")
        canvas.restoreState()

    doc.build(story, onFirstPage=footer, onLaterPages=footer)


def _duration_label(seconds: int) -> str:
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02}:{minutes:02}:{seconds:02}"
