"""
E1/L1/K1 PDF Generation Service

Generates a pre-filled PDF that visually resembles the official Austrian
BMF Einkommensteuererklaerung (E1) / Arbeitnehmerveranlagung (L1) form.

Layout: Official BMF form style with:
- Green/gray header with Bundesministerium fuer Finanzen branding
- Numbered sections (Punkt 1, 2, 3...)
- Grid-based KZ (Kennzahl) field boxes
- Official-looking typography and spacing
"""
import io
from decimal import Decimal
from typing import Dict, Any, List, Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm, cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer,
    HRFlowable, KeepTogether, PageBreak,
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT


# ── Official BMF color palette ──────────────────────────────────────
BMF_GREEN = colors.Color(0.0, 0.35, 0.20)        # dark green header
BMF_GREEN_LIGHT = colors.Color(0.85, 0.93, 0.87)  # light green tint
BMF_GRAY_DARK = colors.Color(0.25, 0.25, 0.25)
BMF_GRAY_MED = colors.Color(0.55, 0.55, 0.55)
BMF_GRAY_LIGHT = colors.Color(0.92, 0.92, 0.92)
BMF_GRAY_BG = colors.Color(0.96, 0.96, 0.96)
KZ_BOX_BG = colors.Color(0.95, 0.97, 0.95)       # very light green for KZ boxes
FIELD_BG = colors.Color(1.0, 1.0, 0.92)           # light yellow for editable fields
BORDER = colors.Color(0.4, 0.4, 0.4)
BORDER_LIGHT = colors.Color(0.7, 0.7, 0.7)
WHITE = colors.white
BLACK = colors.black


def _styles():
    ss = getSampleStyleSheet()

    ss.add(ParagraphStyle(
        "BMFTitle", parent=ss["Heading1"],
        fontSize=16, textColor=WHITE, alignment=TA_LEFT,
        fontName="Helvetica-Bold",
        spaceAfter=0, spaceBefore=0, leading=20,
    ))
    ss.add(ParagraphStyle(
        "BMFSubtitle", parent=ss["Normal"],
        fontSize=9, textColor=WHITE, alignment=TA_LEFT,
        fontName="Helvetica", leading=11,
    ))
    ss.add(ParagraphStyle(
        "FormCode", parent=ss["Normal"],
        fontSize=22, textColor=WHITE, alignment=TA_CENTER,
        fontName="Helvetica-Bold", leading=26,
    ))
    ss.add(ParagraphStyle(
        "SectionTitle", parent=ss["Heading2"],
        fontSize=9, textColor=WHITE, alignment=TA_LEFT,
        fontName="Helvetica-Bold",
        spaceAfter=0, spaceBefore=0, leading=12,
    ))
    ss.add(ParagraphStyle(
        "SectionNum", parent=ss["Normal"],
        fontSize=11, textColor=WHITE, alignment=TA_CENTER,
        fontName="Helvetica-Bold", leading=14,
    ))
    ss.add(ParagraphStyle(
        "FieldLabel", parent=ss["Normal"],
        fontSize=7.5, textColor=BMF_GRAY_DARK,
        fontName="Helvetica", leading=9.5,
    ))
    ss.add(ParagraphStyle(
        "FieldLabelBold", parent=ss["Normal"],
        fontSize=7.5, textColor=BMF_GRAY_DARK,
        fontName="Helvetica-Bold", leading=9.5,
    ))
    ss.add(ParagraphStyle(
        "FieldValue", parent=ss["Normal"],
        fontSize=10, textColor=BLACK,
        fontName="Courier-Bold", alignment=TA_RIGHT, leading=13,
    ))
    ss.add(ParagraphStyle(
        "KZNum", parent=ss["Normal"],
        fontSize=7, textColor=BMF_GREEN,
        fontName="Helvetica-Bold", alignment=TA_CENTER, leading=9,
    ))
    ss.add(ParagraphStyle(
        "MetaLabel", parent=ss["Normal"],
        fontSize=7, textColor=BMF_GRAY_MED,
        fontName="Helvetica", leading=9,
    ))
    ss.add(ParagraphStyle(
        "MetaValue", parent=ss["Normal"],
        fontSize=9, textColor=BLACK,
        fontName="Helvetica", leading=11,
    ))
    ss.add(ParagraphStyle(
        "FooterNote", parent=ss["Normal"],
        fontSize=6.5, textColor=BMF_GRAY_MED,
        fontName="Helvetica", leading=8.5, alignment=TA_LEFT,
    ))
    ss.add(ParagraphStyle(
        "Disclaimer", parent=ss["Normal"],
        fontSize=7, textColor=colors.Color(0.6, 0.3, 0.0),
        fontName="Helvetica-Oblique", leading=9,
    ))
    ss.add(ParagraphStyle(
        "SummaryLabel", parent=ss["Normal"],
        fontSize=8, textColor=BMF_GRAY_DARK,
        fontName="Helvetica", leading=10,
    ))
    ss.add(ParagraphStyle(
        "SummaryValue", parent=ss["Normal"],
        fontSize=10, textColor=BLACK,
        fontName="Helvetica-Bold", alignment=TA_RIGHT, leading=13,
    ))
    ss.add(ParagraphStyle(
        "SummaryTotal", parent=ss["Normal"],
        fontSize=11, textColor=BMF_GREEN,
        fontName="Helvetica-Bold", alignment=TA_RIGHT, leading=14,
    ))
    return ss


def _fmt(value) -> str:
    """Format number as Austrian EUR (1.234,56)."""
    if value is None:
        return ""
    try:
        v = float(value)
        if v == 0:
            return "\u2013"  # en-dash for zero
        sign = "" if v >= 0 else "-"
        v = abs(v)
        formatted = f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        return f"{sign}{formatted}"
    except (ValueError, TypeError):
        return str(value)


def _build_bmf_header(form_data: Dict[str, Any], styles) -> List:
    """Build the official BMF-style green header bar."""
    elements = []

    form_type = form_data["form_type"]
    year = form_data["tax_year"]

    # Map form types to official names
    form_names = {
        "E1": "Einkommensteuererkl\u00e4rung",
        "L1": "Erkl\u00e4rung zur Arbeitnehmerveranlagung",
        "K1": "K\u00f6rperschaftsteuererkl\u00e4rung",
    }
    form_name = form_names.get(form_type, form_data.get("form_name_de", ""))

    # Top green bar: BMF branding + form code
    left_content = [
        Paragraph("Bundesministerium f\u00fcr Finanzen", styles["BMFTitle"]),
        Paragraph(
            f"Republik \u00d6sterreich \u2022 {form_name} {year}",
            styles["BMFSubtitle"],
        ),
    ]
    left_cell = []
    for p in left_content:
        left_cell.append(p)

    right_cell = Paragraph(f"<b>{form_type}</b>", styles["FormCode"])

    header_data = [[left_cell, right_cell]]
    header_table = Table(header_data, colWidths=[140 * mm, 30 * mm])
    header_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), BMF_GREEN),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING", (0, 0), (0, 0), 10),
        ("RIGHTPADDING", (-1, -1), (-1, -1), 10),
    ]))
    elements.append(header_table)

    return elements


def _build_personal_info(form_data: Dict[str, Any], styles) -> List:
    """Build the personal information section (Punkt 1 equivalent)."""
    elements = []

    user_name = form_data.get("user_name", "")
    tax_number = form_data.get("tax_number", "")
    generated = form_data.get("generated_at", "")
    year = form_data["tax_year"]

    # Personal info grid
    info_data = [
        [
            Paragraph("Steuernummer (StNr.)", styles["MetaLabel"]),
            Paragraph("Familienname / Firmenname", styles["MetaLabel"]),
            Paragraph("Veranlagungsjahr", styles["MetaLabel"]),
        ],
        [
            Paragraph(f"<b>{tax_number or 'N/A'}</b>", styles["MetaValue"]),
            Paragraph(f"<b>{user_name}</b>", styles["MetaValue"]),
            Paragraph(f"<b>{year}</b>", styles["MetaValue"]),
        ],
    ]
    info_table = Table(info_data, colWidths=[55 * mm, 80 * mm, 35 * mm])
    info_table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, BORDER_LIGHT),
        ("BACKGROUND", (0, 0), (-1, 0), BMF_GRAY_LIGHT),
        ("BACKGROUND", (0, 1), (-1, 1), WHITE),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
    ]))
    elements.append(info_table)

    # Generated date note
    elements.append(Spacer(1, 1.5 * mm))
    elements.append(Paragraph(
        f"Erstellt am {generated} \u2022 Taxja Steuer-Ausf\u00fcllhilfe",
        styles["FooterNote"],
    ))
    elements.append(Spacer(1, 3 * mm))

    return elements


def _build_section_header(punkt_nr: str, title: str, styles) -> Table:
    """Build a green section header bar like the official form."""
    data = [[
        Paragraph(f"Punkt {punkt_nr}", styles["SectionNum"]),
        Paragraph(f"<b>{title}</b>", styles["SectionTitle"]),
    ]]
    table = Table(data, colWidths=[18 * mm, 152 * mm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), BMF_GREEN),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (0, 0), 4),
        ("LEFTPADDING", (1, 0), (1, 0), 6),
        ("LINEAFTER", (0, 0), (0, 0), 1, colors.Color(0.0, 0.45, 0.25)),
    ]))
    return table


def _build_field_rows(fields: List[Dict], styles) -> List:
    """Build KZ field rows in official form grid style."""
    elements = []

    for i, field in enumerate(fields):
        kz = field.get("kz", "")
        label = field.get("label_de", "")
        value = field.get("value", 0)
        note = field.get("note_de", "")
        editable = field.get("editable", True)

        # Build label with optional note
        label_text = label
        if note:
            label_text += f'  <font size="6" color="#888888"><i>({note})</i></font>'

        # KZ box | Label | Value box
        kz_cell = Paragraph(f"KZ {kz}", styles["KZNum"])
        label_cell = Paragraph(label_text, styles["FieldLabel"])
        value_cell = Paragraph(_fmt(value), styles["FieldValue"])

        row_data = [[kz_cell, label_cell, value_cell]]
        row_bg = WHITE if i % 2 == 0 else BMF_GRAY_BG

        row_table = Table(row_data, colWidths=[16 * mm, 122 * mm, 32 * mm])

        row_style = [
            ("BOX", (0, 0), (-1, -1), 0.3, BORDER_LIGHT),
            ("LINEAFTER", (0, 0), (0, 0), 0.3, BORDER_LIGHT),
            ("LINEAFTER", (1, 0), (1, 0), 0.3, BORDER_LIGHT),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("LEFTPADDING", (0, 0), (0, 0), 2),
            ("LEFTPADDING", (1, 0), (1, 0), 5),
            ("RIGHTPADDING", (2, 0), (2, 0), 4),
            # KZ box background
            ("BACKGROUND", (0, 0), (0, 0), KZ_BOX_BG),
            # Label background
            ("BACKGROUND", (1, 0), (1, 0), row_bg),
            # Value box background: yellow-ish if editable, gray if readonly
            ("BACKGROUND", (2, 0), (2, 0), FIELD_BG if editable else BMF_GRAY_LIGHT),
        ]
        row_table.setStyle(TableStyle(row_style))
        elements.append(row_table)

    return elements


# ── Section mapping for official form structure ─────────────────────

# E1 sections
E1_SECTIONS = [
    ("1", "Eink\u00fcnfte aus nichtselbst\u00e4ndiger Arbeit",
     "einkuenfte_nichtselbstaendig"),
    ("2", "Eink\u00fcnfte aus Gewerbebetrieb",
     "einkuenfte_gewerbebetrieb"),
    ("3", "Eink\u00fcnfte aus selbst\u00e4ndiger Arbeit",
     "einkuenfte_selbstaendig"),
    ("4", "Eink\u00fcnfte aus Vermietung und Verpachtung",
     "einkuenfte_vermietung"),
    ("5", "Eink\u00fcnfte aus Kapitalverm\u00f6gen",
     "einkuenfte_kapital"),
    ("6", "Sonderausgaben (\u00a7 18 EStG)",
     "sonderausgaben"),
    ("7", "Werbungskosten (\u00a7 16 EStG)",
     "werbungskosten"),
    ("8", "Au\u00dferergew\u00f6hnliche Belastungen und Absetzbetr\u00e4ge",
     "absetzbetraege"),
    ("9", "Pendlerpauschale (\u00a7 16 Abs. 1 Z 6 EStG)",
     "pendler"),
]

# L1 sections
L1_SECTIONS = [
    ("1", "Alleinverdiener-/Alleinerzieherabsetzbetrag, Familienbonus Plus",
     "absetzbetraege"),
    ("2", "Sonderausgaben (\u00a7 18 EStG)",
     "sonderausgaben"),
    ("3", "Werbungskosten (\u00a7 16 EStG)",
     "werbungskosten"),
    ("4", "Pendlerpauschale (\u00a7 16 Abs. 1 Z 6 EStG)",
     "pendler"),
]

# K1 sections
K1_SECTIONS = [
    ("1", "Ertr\u00e4ge (Betriebseinnahmen)",
     "ertraege"),
    ("2", "Aufwendungen (Betriebsausgaben)",
     "aufwendungen"),
    ("3", "Ergebnis und K\u00f6rperschaftsteuer",
     "ergebnis"),
    ("4", "Gewinnaussch\u00fcttung (KESt)",
     "ausschuettung"),
]


def _get_section_order(form_type: str) -> List:
    if form_type == "L1":
        return L1_SECTIONS
    elif form_type == "K1":
        return K1_SECTIONS
    return E1_SECTIONS


def _build_summary_section(form_data: Dict[str, Any], styles) -> List:
    """Build the Zusammenfassung (summary) section in official style."""
    elements = []
    summary = form_data.get("summary", {})
    if not summary:
        return elements

    form_type = form_data.get("form_type", "E1")

    # Section header
    elements.append(_build_section_header(
        "\u03a3", "Zusammenfassung der Berechnung", styles
    ))
    elements.append(Spacer(1, 1 * mm))

    # Define which summary keys to show based on form type
    if form_type == "L1":
        key_labels = [
            ("employment_income", "Eink\u00fcnfte aus nichtselbst\u00e4ndiger Arbeit"),
            ("werbungskosten", "Werbungskosten"),
            ("sonderausgaben", "Sonderausgaben"),
            ("pendlerpauschale", "Pendlerpauschale"),
            ("familienbonus", "Familienbonus Plus"),
            ("alleinerzieher", "Alleinverdiener-/Alleinerzieherabsetzbetrag"),
        ]
    elif form_type == "K1":
        key_labels = [
            ("total_revenue", "Umsatzerl\u00f6se"),
            ("total_expenses", "Betriebsausgaben gesamt"),
            ("corporate_profit", "Gewinn / Verlust vor Steuern"),
            ("koest", "K\u00f6rperschaftsteuer"),
            ("profit_after_koest", "Jahres\u00fcberschuss nach K\u00f6St"),
            ("kest_on_dividend", "KESt auf Gewinnaussch\u00fcttung"),
            ("net_dividend", "Netto-Aussch\u00fcttung"),
            ("vat_collected", "USt eingenommen"),
            ("vat_paid", "VSt bezahlt"),
            ("vat_balance", "USt-Zahllast / -Guthaben"),
        ]
    else:  # E1
        key_labels = [
            ("employment_income", "Eink\u00fcnfte nichtselbst\u00e4ndige Arbeit"),
            ("self_employment_income", "Eink\u00fcnfte selbst\u00e4ndige Arbeit"),
            ("gewerbebetrieb_gewinn", "Gewinn aus Gewerbebetrieb"),
            ("rental_income", "Eink\u00fcnfte Vermietung (brutto)"),
            ("vermietung_einkuenfte", "Eink\u00fcnfte Vermietung (netto)"),
            ("capital_gains", "Eink\u00fcnfte Kapitalverm\u00f6gen"),
            ("total_income", "GESAMTBETRAG DER EINK\u00dcNFTE"),
            ("total_deductible", "Abzugsf\u00e4hige Aufwendungen"),
            ("gesamtbetrag_einkuenfte", "ZU VERSTEUERNDES EINKOMMEN"),
            ("vat_collected", "USt eingenommen"),
            ("vat_paid", "VSt bezahlt"),
            ("vat_balance", "USt-Zahllast / -Guthaben"),
        ]

    # Totals that get special formatting
    total_keys = {
        "total_income", "gesamtbetrag_einkuenfte", "corporate_profit",
        "profit_after_koest", "net_dividend",
    }

    rows = []
    for key, label in key_labels:
        val = summary.get(key)
        if val is None:
            continue
        fval = float(val)
        if fval == 0 and key not in total_keys:
            continue

        is_total = key in total_keys
        if is_total:
            rows.append([
                Paragraph(f"<b>{label}</b>", styles["SummaryLabel"]),
                Paragraph(f"<b>EUR {_fmt(fval)}</b>", styles["SummaryTotal"]),
            ])
        else:
            rows.append([
                Paragraph(label, styles["SummaryLabel"]),
                Paragraph(f"EUR {_fmt(fval)}", styles["SummaryValue"]),
            ])

    if not rows:
        return elements

    sum_table = Table(rows, colWidths=[120 * mm, 50 * mm])
    sum_styles = [
        ("BOX", (0, 0), (-1, -1), 0.5, BORDER_LIGHT),
        ("LINEBELOW", (0, 0), (-1, -2), 0.3, BORDER_LIGHT),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (0, -1), 6),
        ("RIGHTPADDING", (1, 0), (1, -1), 6),
    ]
    # Highlight total rows with green tint
    for i, (key, _) in enumerate(
        [(k, l) for k, l in key_labels if summary.get(k) is not None and (float(summary.get(k, 0)) != 0 or k in total_keys)]
    ):
        if key in total_keys:
            sum_styles.append(
                ("BACKGROUND", (0, i), (-1, i), BMF_GREEN_LIGHT)
            )
        else:
            bg = WHITE if i % 2 == 0 else BMF_GRAY_BG
            sum_styles.append(
                ("BACKGROUND", (0, i), (-1, i), bg)
            )

    sum_table.setStyle(TableStyle(sum_styles))
    elements.append(sum_table)

    return elements


def _build_footer(form_data: Dict[str, Any], styles) -> List:
    """Build the official-looking footer with disclaimer and links."""
    elements = []
    elements.append(Spacer(1, 5 * mm))

    # Thin green line
    elements.append(HRFlowable(
        width="100%", thickness=1.5, color=BMF_GREEN,
        spaceAfter=3 * mm, spaceBefore=1 * mm,
    ))

    # Disclaimer
    disclaimer = form_data.get("disclaimer_de", "")
    if disclaimer:
        elements.append(Paragraph(
            f"HINWEIS: {disclaimer}",
            styles["Disclaimer"],
        ))
        elements.append(Spacer(1, 2 * mm))

    # Links
    fon_url = form_data.get("finanzonline_url", "")
    form_url = form_data.get("form_download_url", "")
    links = []
    if fon_url:
        links.append(f'FinanzOnline: <link href="{fon_url}">{fon_url}</link>')
    if form_url:
        links.append(
            f'Offizielles Formular: <link href="{form_url}">{form_url}</link>'
        )
    if links:
        elements.append(Paragraph(" | ".join(links), styles["FooterNote"]))

    elements.append(Spacer(1, 2 * mm))

    # Taxja branding
    elements.append(Paragraph(
        "Erstellt von Taxja \u2013 Steuern einfach ja! | "
        "Nur als Referenz \u2013 keine Steuerberatung. "
        "Endg\u00fcltige Einreichung \u00fcber FinanzOnline.",
        styles["FooterNote"],
    ))

    return elements


def generate_e1_pdf(form_data: Dict[str, Any]) -> bytes:
    """Generate a filled E1/L1/K1 PDF in official BMF form style.

    Args:
        form_data: The dict returned by e1_form_service.generate_tax_form_data()

    Returns:
        PDF file content as bytes
    """
    buffer = io.BytesIO()
    form_type = form_data.get("form_type", "E1")
    year = form_data.get("tax_year", "")

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=15 * mm,
        rightMargin=15 * mm,
        topMargin=12 * mm,
        bottomMargin=12 * mm,
        title=f"{form_type} \u2013 {year}",
        author="Taxja",
    )

    styles = _styles()
    elements = []

    # ── 1. BMF Header ───────────────────────────────────────────────
    elements.extend(_build_bmf_header(form_data, styles))
    elements.append(Spacer(1, 2 * mm))

    # ── 2. Personal info ────────────────────────────────────────────
    elements.extend(_build_personal_info(form_data, styles))

    # ── 3. Group fields by section ──────────────────────────────────
    fields = form_data.get("fields", [])
    sections: Dict[str, List] = {}
    for f in fields:
        sec = f.get("section", "other")
        if sec not in sections:
            sections[sec] = []
        sections[sec].append(f)

    # ── 4. Render sections in official order ────────────────────────
    section_order = _get_section_order(form_type)

    for punkt_nr, title, sec_key in section_order:
        if sec_key not in sections:
            continue
        sec_fields = sections[sec_key]
        if not sec_fields:
            continue

        section_elements = []
        section_elements.append(_build_section_header(punkt_nr, title, styles))
        section_elements.append(Spacer(1, 1 * mm))
        section_elements.extend(_build_field_rows(sec_fields, styles))
        section_elements.append(Spacer(1, 3 * mm))

        # Try to keep section together on one page
        elements.append(KeepTogether(section_elements))

    # Any remaining sections not in the official order
    rendered_keys = {s[2] for s in section_order}
    extra_nr = len(section_order) + 1
    for sec_key, sec_fields in sections.items():
        if sec_key in rendered_keys:
            continue
        if not sec_fields:
            continue
        section_elements = []
        section_elements.append(
            _build_section_header(str(extra_nr), sec_key.replace("_", " ").title(), styles)
        )
        section_elements.append(Spacer(1, 1 * mm))
        section_elements.extend(_build_field_rows(sec_fields, styles))
        section_elements.append(Spacer(1, 3 * mm))
        elements.append(KeepTogether(section_elements))
        extra_nr += 1

    # ── 5. Summary ──────────────────────────────────────────────────
    elements.extend(_build_summary_section(form_data, styles))

    # ── 6. Footer ───────────────────────────────────────────────────
    elements.extend(_build_footer(form_data, styles))

    doc.build(elements)
    return buffer.getvalue()
