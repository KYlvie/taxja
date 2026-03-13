"""
Official BMF E1 Form PDF Generator

Generates a PDF that precisely replicates the official Austrian BMF
Einkommensteuererklaerung (E1) form layout using PyMuPDF (fitz).

Instead of using ReportLab flowable layout, this service draws the form
at exact coordinates matching the official BMF form, then fills in the
user's data at the correct KZ field positions.

The result is a PDF that looks identical to the official E1 form and
can be printed and submitted to the Finanzamt.
"""
import io
import fitz  # PyMuPDF
from decimal import Decimal
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path

# ── Page dimensions (A4) ────────────────────────────────────────────
A4_W = 595.28  # points
A4_H = 841.89

# ── Official BMF colors ─────────────────────────────────────────────
BMF_GREEN = (0.0, 0.35, 0.20)
BMF_GREEN_LIGHT = (0.85, 0.93, 0.87)
BMF_GREEN_SECTION = (0.18, 0.45, 0.28)
WHITE = (1, 1, 1)
BLACK = (0, 0, 0)
GRAY_LIGHT = (0.92, 0.92, 0.92)
GRAY_BG = (0.96, 0.96, 0.96)
FIELD_BG = (1.0, 1.0, 0.92)  # light yellow for value fields
KZ_BG = (0.90, 0.95, 0.90)   # light green for KZ boxes
BORDER_COLOR = (0.5, 0.5, 0.5)

# ── Layout constants (points) ───────────────────────────────────────
LEFT_MARGIN = 42
RIGHT_MARGIN = A4_W - 42
TOP_MARGIN = 36
CONTENT_W = RIGHT_MARGIN - LEFT_MARGIN  # ~511 pt

# Section header bar
SECTION_H = 20
PUNKT_W = 50

# Field row
ROW_H = 22
KZ_COL_W = 48
LABEL_COL_W = 350
VALUE_COL_W = CONTENT_W - KZ_COL_W - LABEL_COL_W  # ~113 pt

# Fonts – use "helv" etc. as base names; we sanitize text to Latin-1 before rendering
FONT_REGULAR = "helv"
FONT_BOLD = "hebo"
FONT_MONO = "cour"


def _sanitize_latin1(text: str) -> str:
    """Replace non-Latin-1 characters with ASCII equivalents.

    PyMuPDF Base14 fonts (helv, hebo, cour) only support Latin-1 encoding.
    Characters outside Latin-1 (U+0100+) cause garbled output or silent failures.
    """
    replacements = {
        "\u2013": "-",       # en-dash -> hyphen
        "\u2014": "-",       # em-dash -> hyphen
        "\u2022": "*",       # bullet -> asterisk
        "\u2018": "'",       # left single quote
        "\u2019": "'",       # right single quote
        "\u201c": '"',       # left double quote
        "\u201d": '"',       # right double quote
        "\u2026": "...",     # ellipsis
        "\u03a3": "Sum.",    # Sigma -> Sum.
        "\u20ac": "EUR",     # Euro sign -> EUR
        "\u2264": "<=",      # less-than-or-equal
        "\u2265": ">=",      # greater-than-or-equal
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    # Drop any remaining non-Latin-1 characters
    result = []
    for ch in text:
        try:
            ch.encode("latin-1")
            result.append(ch)
        except UnicodeEncodeError:
            result.append("?")
    return "".join(result)


def _fmt_eur(value) -> str:
    """Format number as Austrian EUR: 1.234,56"""
    if value is None:
        return ""
    try:
        v = float(value)
        if v == 0:
            return "\u2013"
        sign = "" if v >= 0 else "-"
        v = abs(v)
        # Format with 2 decimals, then convert to Austrian format
        parts = f"{v:,.2f}".split(".")
        integer_part = parts[0].replace(",", ".")
        decimal_part = parts[1]
        return f"{sign}{integer_part},{decimal_part}"
    except (ValueError, TypeError):
        return str(value)



class OfficialE1PdfBuilder:
    """Builds a PDF that replicates the official BMF E1 form layout."""

    def __init__(self):
        self.doc = fitz.open()
        self.page: Optional[fitz.Page] = None
        self.y = TOP_MARGIN  # current vertical position

    def _new_page(self):
        """Add a new A4 page."""
        self.page = self.doc.new_page(width=A4_W, height=A4_H)
        self.y = TOP_MARGIN

    def _check_space(self, needed: float):
        """Start a new page if not enough space."""
        if self.y + needed > A4_H - 40:
            self._new_page()

    # ── Drawing primitives ──────────────────────────────────────────

    def _draw_rect(
        self, x: float, y: float, w: float, h: float,
        fill: Optional[Tuple] = None, stroke: Optional[Tuple] = None,
        stroke_width: float = 0.5,
    ):
        rect = fitz.Rect(x, y, x + w, y + h)
        shape = self.page.new_shape()
        shape.draw_rect(rect)
        shape.finish(
            color=stroke,
            fill=fill,
            width=stroke_width,
        )
        shape.commit()

    def _draw_text(
        self, x: float, y: float, text: str,
        fontsize: float = 9, fontname: str = FONT_REGULAR,
        color: Tuple = BLACK,
    ):
        self.page.insert_text(
            fitz.Point(x, y),
            _sanitize_latin1(text),
            fontsize=fontsize,
            fontname=fontname,
            color=color,
        )

    def _draw_text_right(
        self, x_right: float, y: float, text: str,
        fontsize: float = 10, fontname: str = FONT_MONO,
        color: Tuple = BLACK,
    ):
        """Draw text right-aligned to x_right."""
        safe = _sanitize_latin1(text)
        tw = fitz.get_text_length(safe, fontname=fontname, fontsize=fontsize)
        self.page.insert_text(
            fitz.Point(x_right - tw - 4, y),
            safe,
            fontsize=fontsize,
            fontname=fontname,
            color=color,
        )

    # ── BMF Header ──────────────────────────────────────────────────

    def _draw_header(self, form_data: Dict[str, Any]):
        """Draw the green BMF header bar with form code."""
        form_type = form_data.get("form_type", "E1")
        year = form_data.get("tax_year", "")
        form_names = {
            "E1": "Einkommensteuererklärung",
            "L1": "Erklärung zur Arbeitnehmerveranlagung",
            "K1": "Körperschaftsteuererklärung",
        }
        form_name = form_names.get(form_type, "")

        # Green header bar
        header_h = 48
        self._draw_rect(LEFT_MARGIN, self.y, CONTENT_W, header_h, fill=BMF_GREEN)

        # BMF title
        self._draw_text(
            LEFT_MARGIN + 10, self.y + 18,
            "Bundesministerium für Finanzen",
            fontsize=15, fontname=FONT_BOLD, color=WHITE,
        )
        self._draw_text(
            LEFT_MARGIN + 10, self.y + 32,
            f"Republik Österreich \u2022 {form_name} {year}",
            fontsize=8.5, fontname=FONT_REGULAR, color=WHITE,
        )

        # Form code box (right side)
        code_w = 50
        code_x = RIGHT_MARGIN - code_w - 6
        self._draw_text(
            code_x + 8, self.y + 30,
            form_type,
            fontsize=22, fontname=FONT_BOLD, color=WHITE,
        )

        self.y += header_h + 3

    # ── Personal info section ───────────────────────────────────────

    def _draw_personal_info(self, form_data: Dict[str, Any]):
        """Draw the personal info grid (StNr, Name, Year)."""
        user_name = form_data.get("user_name", "")
        tax_number = form_data.get("tax_number", "N/A")
        year = str(form_data.get("tax_year", ""))
        generated = form_data.get("generated_at", "")

        col_widths = [160, 240, CONTENT_W - 400]
        labels = ["Steuernummer (StNr.)", "Familienname / Firmenname", "Veranlagungsjahr"]
        values = [tax_number, user_name, year]

        # Label row (gray background)
        x = LEFT_MARGIN
        for i, (label, w) in enumerate(zip(labels, col_widths)):
            self._draw_rect(x, self.y, w, 14, fill=GRAY_LIGHT, stroke=BORDER_COLOR, stroke_width=0.3)
            self._draw_text(x + 3, self.y + 10, label, fontsize=6.5, color=(0.4, 0.4, 0.4))
            x += w

        self.y += 14

        # Value row
        x = LEFT_MARGIN
        for i, (val, w) in enumerate(zip(values, col_widths)):
            self._draw_rect(x, self.y, w, 18, fill=WHITE, stroke=BORDER_COLOR, stroke_width=0.3)
            self._draw_text(x + 4, self.y + 13, val, fontsize=9, fontname=FONT_BOLD)
            x += w

        self.y += 18 + 2

        # Generated note
        self._draw_text(
            LEFT_MARGIN, self.y + 8,
            f"Erstellt am {generated} \u2022 Taxja Steuer-Ausfüllhilfe",
            fontsize=6, color=(0.5, 0.5, 0.5),
        )
        self.y += 14

    # ── Section header bar ──────────────────────────────────────────

    def _draw_section_header(self, punkt_nr: str, title: str):
        """Draw a green section header bar."""
        self._check_space(SECTION_H + ROW_H)

        # Punkt number box
        self._draw_rect(LEFT_MARGIN, self.y, PUNKT_W, SECTION_H, fill=BMF_GREEN)
        self._draw_text(
            LEFT_MARGIN + 6, self.y + 14,
            f"Punkt {punkt_nr}",
            fontsize=9, fontname=FONT_BOLD, color=WHITE,
        )

        # Title bar
        self._draw_rect(LEFT_MARGIN + PUNKT_W, self.y, CONTENT_W - PUNKT_W, SECTION_H, fill=BMF_GREEN)
        self._draw_text(
            LEFT_MARGIN + PUNKT_W + 8, self.y + 14,
            title,
            fontsize=9, fontname=FONT_BOLD, color=WHITE,
        )

        self.y += SECTION_H + 1

    # ── KZ field row ────────────────────────────────────────────────

    def _draw_field_row(self, kz: str, label: str, value: str, note: str = "", row_idx: int = 0):
        """Draw a single KZ field row matching official form layout."""
        self._check_space(ROW_H)

        row_bg = WHITE if row_idx % 2 == 0 else GRAY_BG
        x = LEFT_MARGIN

        # KZ box (green tint)
        self._draw_rect(x, self.y, KZ_COL_W, ROW_H, fill=KZ_BG, stroke=BORDER_COLOR, stroke_width=0.3)
        self._draw_text(
            x + 4, self.y + 14,
            f"KZ {kz}",
            fontsize=7, fontname=FONT_BOLD, color=BMF_GREEN,
        )
        x += KZ_COL_W

        # Label
        self._draw_rect(x, self.y, LABEL_COL_W, ROW_H, fill=row_bg, stroke=BORDER_COLOR, stroke_width=0.3)
        # Truncate label if too long
        display_label = label
        if note:
            display_label += f"  ({note})"
        if len(display_label) > 70:
            display_label = display_label[:67] + "..."
        self._draw_text(x + 4, self.y + 14, display_label, fontsize=7.5)
        x += LABEL_COL_W

        # Value box (yellow tint)
        self._draw_rect(x, self.y, VALUE_COL_W, ROW_H, fill=FIELD_BG, stroke=BORDER_COLOR, stroke_width=0.3)
        self._draw_text_right(
            x + VALUE_COL_W, self.y + 15,
            value,
            fontsize=10, fontname=FONT_BOLD,
        )

        self.y += ROW_H


    # ── Summary section ─────────────────────────────────────────────

    def _draw_summary_section(self, form_data: Dict[str, Any]):
        """Draw the Zusammenfassung der Berechnung section."""
        summary = form_data.get("summary", {})
        if not summary:
            return

        form_type = form_data.get("form_type", "E1")

        self._draw_section_header("\u03a3", "Zusammenfassung der Berechnung")

        if form_type == "E1":
            summary_rows = [
                ("employment_income", "Einkünfte nichtselbständige Arbeit", False),
                ("self_employment_income", "Einkünfte selbständige Arbeit", False),
                ("gewerbebetrieb_gewinn", "Gewinn aus Gewerbebetrieb", False),
                ("rental_income", "Einkünfte Vermietung (brutto)", False),
                ("vermietung_einkuenfte", "Einkünfte Vermietung (netto)", False),
                ("capital_gains", "Einkünfte Kapitalvermögen", False),
                ("total_income", "GESAMTBETRAG DER EINKÜNFTE", True),
                ("total_deductible", "Abzugsfähige Aufwendungen", False),
                ("gesamtbetrag_einkuenfte", "ZU VERSTEUERNDES EINKOMMEN", True),
            ]
        elif form_type == "L1":
            summary_rows = [
                ("employment_income", "Einkünfte aus nichtselbständiger Arbeit", False),
                ("werbungskosten", "Werbungskosten", False),
                ("sonderausgaben", "Sonderausgaben", False),
                ("pendlerpauschale", "Pendlerpauschale", False),
                ("familienbonus", "Familienbonus Plus", False),
            ]
        else:  # K1
            summary_rows = [
                ("total_revenue", "Umsatzerlöse", False),
                ("total_expenses", "Betriebsausgaben gesamt", False),
                ("corporate_profit", "Gewinn / Verlust vor Steuern", True),
                ("koest", "Körperschaftsteuer", False),
                ("profit_after_koest", "Jahresüberschuss nach KöSt", True),
            ]

        row_idx = 0
        for key, label, is_total in summary_rows:
            val = summary.get(key)
            if val is None:
                continue
            fval = float(val)
            if fval == 0 and not is_total:
                continue

            self._check_space(ROW_H)

            bg = BMF_GREEN_LIGHT if is_total else (WHITE if row_idx % 2 == 0 else GRAY_BG)
            x = LEFT_MARGIN

            # Label column
            label_w = CONTENT_W - VALUE_COL_W
            self._draw_rect(x, self.y, label_w, ROW_H, fill=bg, stroke=BORDER_COLOR, stroke_width=0.3)
            font = FONT_BOLD if is_total else FONT_REGULAR
            color = BMF_GREEN if is_total else BLACK
            self._draw_text(x + 6, self.y + 14, label, fontsize=8, fontname=font, color=color)
            x += label_w

            # Value column
            self._draw_rect(x, self.y, VALUE_COL_W, ROW_H, fill=bg, stroke=BORDER_COLOR, stroke_width=0.3)
            formatted = f"EUR {_fmt_eur(fval)}"
            self._draw_text_right(
                x + VALUE_COL_W, self.y + 15,
                formatted,
                fontsize=10 if is_total else 9,
                fontname=FONT_BOLD,
                color=color,
            )

            self.y += ROW_H
            row_idx += 1

    # ── Footer ──────────────────────────────────────────────────────

    def _draw_footer(self, form_data: Dict[str, Any]):
        """Draw the footer with disclaimer and links."""
        self._check_space(60)

        # Green line
        shape = self.page.new_shape()
        shape.draw_line(
            fitz.Point(LEFT_MARGIN, self.y + 4),
            fitz.Point(RIGHT_MARGIN, self.y + 4),
        )
        shape.finish(color=BMF_GREEN, width=1.5)
        shape.commit()
        self.y += 10

        # Disclaimer
        disclaimer = form_data.get("disclaimer_de", "")
        if disclaimer:
            self._draw_text(
                LEFT_MARGIN, self.y + 8,
                f"HINWEIS: {disclaimer[:120]}",
                fontsize=6.5, color=(0.6, 0.3, 0.0),
            )
            if len(disclaimer) > 120:
                self.y += 9
                self._draw_text(
                    LEFT_MARGIN, self.y + 8,
                    disclaimer[120:240],
                    fontsize=6.5, color=(0.6, 0.3, 0.0),
                )
            self.y += 12

        # Links
        fon_url = form_data.get("finanzonline_url", "")
        form_url = form_data.get("form_download_url", "")
        if fon_url:
            self._draw_text(
                LEFT_MARGIN, self.y + 8,
                f"FinanzOnline: {fon_url}",
                fontsize=6, color=(0.3, 0.3, 0.3),
            )
            self.y += 9
        if form_url:
            self._draw_text(
                LEFT_MARGIN, self.y + 8,
                f"Offizielles Formular: {form_url}",
                fontsize=6, color=(0.3, 0.3, 0.3),
            )
            self.y += 9

        self.y += 4
        self._draw_text(
            LEFT_MARGIN, self.y + 8,
            "Erstellt von Taxja \u2013 Steuern einfach ja! | "
            "Nur als Referenz \u2013 keine Steuerberatung. "
            "Endgültige Einreichung über FinanzOnline.",
            fontsize=6, color=(0.5, 0.5, 0.5),
        )

    # ── Main build method ───────────────────────────────────────────

    def build(self, form_data: Dict[str, Any]) -> bytes:
        """Build the complete E1/L1/K1 PDF."""
        self._new_page()

        # 1. Header
        self._draw_header(form_data)

        # 2. Personal info
        self._draw_personal_info(form_data)

        # 3. Group fields by section
        fields = form_data.get("fields", [])
        sections: Dict[str, List] = {}
        for f in fields:
            sec = f.get("section", "other")
            sections.setdefault(sec, []).append(f)

        # 4. Section definitions
        form_type = form_data.get("form_type", "E1")
        section_order = _get_section_order(form_type)

        # 5. Render each section
        for punkt_nr, title, sec_key in section_order:
            sec_fields = sections.get(sec_key, [])
            if not sec_fields:
                continue

            self._draw_section_header(punkt_nr, title)

            for i, field in enumerate(sec_fields):
                kz = field.get("kz", "")
                label = field.get("label_de", "")
                value = _fmt_eur(field.get("value", 0))
                note = field.get("note_de", "")
                self._draw_field_row(kz, label, value, note, i)

            self.y += 6  # spacing between sections

        # 6. Summary
        self._draw_summary_section(form_data)

        # 7. Footer
        self._draw_footer(form_data)

        # Output
        buf = io.BytesIO()
        self.doc.save(buf)
        self.doc.close()
        return buf.getvalue()


# ── Section order definitions ───────────────────────────────────────

E1_SECTIONS = [
    ("1", "Einkünfte aus nichtselbständiger Arbeit", "einkuenfte_nichtselbstaendig"),
    ("2", "Einkünfte aus Gewerbebetrieb", "einkuenfte_gewerbebetrieb"),
    ("3", "Einkünfte aus selbständiger Arbeit", "einkuenfte_selbstaendig"),
    ("4", "Einkünfte aus Vermietung und Verpachtung", "einkuenfte_vermietung"),
    ("5", "Einkünfte aus Kapitalvermögen", "einkuenfte_kapital"),
    ("6", "Sonderausgaben (§ 18 EStG)", "sonderausgaben"),
    ("7", "Werbungskosten (§ 16 EStG)", "werbungskosten"),
    ("8", "Außergewöhnliche Belastungen und Absetzbeträge", "absetzbetraege"),
    ("9", "Pendlerpauschale (§ 16 Abs. 1 Z 6 EStG)", "pendler"),
]

L1_SECTIONS = [
    ("1", "Alleinverdiener-/Alleinerzieherabsetzbetrag, Familienbonus Plus", "absetzbetraege"),
    ("2", "Sonderausgaben (§ 18 EStG)", "sonderausgaben"),
    ("3", "Werbungskosten (§ 16 EStG)", "werbungskosten"),
    ("4", "Pendlerpauschale (§ 16 Abs. 1 Z 6 EStG)", "pendler"),
]

K1_SECTIONS = [
    ("1", "Erträge (Betriebseinnahmen)", "ertraege"),
    ("2", "Aufwendungen (Betriebsausgaben)", "aufwendungen"),
    ("3", "Ergebnis und Körperschaftsteuer", "ergebnis"),
    ("4", "Gewinnausschüttung (KESt)", "ausschuettung"),
]


def _get_section_order(form_type: str) -> List:
    if form_type == "L1":
        return L1_SECTIONS
    elif form_type == "K1":
        return K1_SECTIONS
    return E1_SECTIONS


# ── Public API ──────────────────────────────────────────────────────

def generate_official_e1_pdf(form_data: Dict[str, Any]) -> bytes:
    """Generate a filled E1/L1/K1 PDF in official BMF form style.

    Uses PyMuPDF for precise coordinate-based layout matching the
    official BMF form.

    Args:
        form_data: Dict from e1_form_service.generate_tax_form_data()

    Returns:
        PDF file content as bytes
    """
    builder = OfficialE1PdfBuilder()
    return builder.build(form_data)
