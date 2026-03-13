"""
E/A Rechnung PDF Generation Service
Generates a professional Einnahmen-Ausgaben-Rechnung PDF using reportlab.
"""
import io
from typing import Dict, Any, List

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable,
)

HEADER_BG = colors.Color(0.12, 0.25, 0.44)
GREEN_BG = colors.Color(0.90, 0.97, 0.90)
RED_BG = colors.Color(0.97, 0.90, 0.90)
LIGHT_GRAY = colors.Color(0.96, 0.96, 0.96)
BORDER = colors.Color(0.6, 0.6, 0.6)


def _styles():
    ss = getSampleStyleSheet()
    ss.add(ParagraphStyle("Title2", parent=ss["Heading1"],
        fontSize=13, textColor=colors.white, alignment=TA_CENTER,
        spaceAfter=0, spaceBefore=0))
    ss.add(ParagraphStyle("Meta", parent=ss["Normal"],
        fontSize=9, textColor=colors.white, alignment=TA_CENTER, leading=11))
    ss.add(ParagraphStyle("SecHead", parent=ss["Heading2"],
        fontSize=10, textColor=HEADER_BG, spaceAfter=2, spaceBefore=6, leading=13))
    ss.add(ParagraphStyle("GroupHead", parent=ss["Normal"],
        fontSize=9, textColor=colors.Color(0.2, 0.2, 0.2), leading=11))
    ss.add(ParagraphStyle("Cell", parent=ss["Normal"],
        fontSize=8, leading=10))
    ss.add(ParagraphStyle("CellR", parent=ss["Normal"],
        fontSize=8, alignment=TA_RIGHT, leading=10))
    ss.add(ParagraphStyle("TotalLabel", parent=ss["Normal"],
        fontSize=10, leading=12))
    ss.add(ParagraphStyle("TotalVal", parent=ss["Normal"],
        fontSize=10, alignment=TA_RIGHT, leading=12))
    ss.add(ParagraphStyle("SmallNote", parent=ss["Normal"],
        fontSize=7, textColor=colors.Color(0.4, 0.4, 0.4), leading=9))
    ss.add(ParagraphStyle("Disclaimer", parent=ss["Normal"],
        fontSize=7, textColor=colors.Color(0.5, 0.2, 0.0), leading=9))
    return ss


def _fmt(v) -> str:
    try:
        f = float(v)
        if f == 0:
            return "-"
        return f"{f:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (ValueError, TypeError):
        return str(v)


def generate_ea_pdf(report_data: Dict[str, Any]) -> bytes:
    """Generate E/A Rechnung PDF."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
        leftMargin=18*mm, rightMargin=18*mm,
        topMargin=15*mm, bottomMargin=15*mm,
        title=f"E/A Rechnung {report_data.get('tax_year', '')}",
        author="Taxja")

    styles = _styles()
    elems = []

    year = report_data.get("tax_year", "")
    name = report_data.get("user_name", "")
    tax_nr = report_data.get("tax_number", "")
    gen_date = report_data.get("generated_at", "")

    # Header
    t = Table([[Paragraph(f"<b>Einnahmen-Ausgaben-Rechnung {year}</b>", styles["Title2"])]],
              colWidths=[174*mm])
    t.setStyle(TableStyle([("BACKGROUND", (0,0), (-1,-1), HEADER_BG),
        ("TOPPADDING", (0,0), (-1,-1), 8), ("BOTTOMPADDING", (0,0), (-1,-1), 8)]))
    elems.append(t)

    mt = Table([[Paragraph(f"Name: {name}", styles["Meta"]),
                 Paragraph(f"StNr: {tax_nr or 'N/A'}", styles["Meta"]),
                 Paragraph(f"Datum: {gen_date}", styles["Meta"])]],
               colWidths=[70*mm, 52*mm, 52*mm])
    mt.setStyle(TableStyle([("BACKGROUND", (0,0), (-1,-1), colors.Color(0.2, 0.35, 0.55)),
        ("TOPPADDING", (0,0), (-1,-1), 3), ("BOTTOMPADDING", (0,0), (-1,-1), 3)]))
    elems.append(mt)
    elems.append(Spacer(1, 5*mm))

    # Income sections
    income_sections = report_data.get("income_sections", [])
    if income_sections:
        elems.append(Paragraph("<b>EINNAHMEN</b>", styles["SecHead"]))
        for sec in income_sections:
            elems.append(Paragraph(f"<b>{sec['label']}</b>", styles["GroupHead"]))
            rows = [[
                Paragraph("<b>Datum</b>", styles["Cell"]),
                Paragraph("<b>Beschreibung</b>", styles["Cell"]),
                Paragraph("<b>Betrag (EUR)</b>", styles["CellR"]),
            ]]
            for item in sec.get("items", []):
                desc = item.get("description", "")
                if len(desc) > 70:
                    desc = desc[:67] + "..."
                rows.append([
                    Paragraph(item.get("date", ""), styles["Cell"]),
                    Paragraph(desc, styles["Cell"]),
                    Paragraph(_fmt(item.get("amount", 0)), styles["CellR"]),
                ])
            # Subtotal row
            rows.append([
                Paragraph("", styles["Cell"]),
                Paragraph("<b>Zwischensumme</b>", styles["Cell"]),
                Paragraph(f"<b>{_fmt(sec.get('subtotal', 0))}</b>", styles["CellR"]),
            ])
            tbl = Table(rows, colWidths=[22*mm, 118*mm, 34*mm])
            tbl_style = [
                ("GRID", (0,0), (-1,-1), 0.4, BORDER),
                ("BACKGROUND", (0,0), (-1,0), GREEN_BG),
                ("BACKGROUND", (0,-1), (-1,-1), colors.Color(0.85, 0.95, 0.85)),
                ("VALIGN", (0,0), (-1,-1), "TOP"),
                ("TOPPADDING", (0,0), (-1,-1), 2),
                ("BOTTOMPADDING", (0,0), (-1,-1), 2),
                ("LEFTPADDING", (0,0), (-1,-1), 3),
                ("RIGHTPADDING", (0,0), (-1,-1), 3),
            ]
            tbl.setStyle(TableStyle(tbl_style))
            elems.append(tbl)
            elems.append(Spacer(1, 2*mm))

    # Expense sections
    expense_sections = report_data.get("expense_sections", [])
    if expense_sections:
        elems.append(Paragraph("<b>AUSGABEN</b>", styles["SecHead"]))
        for sec in expense_sections:
            elems.append(Paragraph(f"<b>{sec['label']}</b>", styles["GroupHead"]))
            rows = [[
                Paragraph("<b>Datum</b>", styles["Cell"]),
                Paragraph("<b>Beschreibung</b>", styles["Cell"]),
                Paragraph("<b>Betrag (EUR)</b>", styles["CellR"]),
            ]]
            for item in sec.get("items", []):
                desc = item.get("description", "")
                if len(desc) > 70:
                    desc = desc[:67] + "..."
                ded = " [abzugsf.]" if item.get("is_deductible") else ""
                rows.append([
                    Paragraph(item.get("date", ""), styles["Cell"]),
                    Paragraph(f"{desc}{ded}", styles["Cell"]),
                    Paragraph(_fmt(item.get("amount", 0)), styles["CellR"]),
                ])
            rows.append([
                Paragraph("", styles["Cell"]),
                Paragraph("<b>Zwischensumme</b>", styles["Cell"]),
                Paragraph(f"<b>{_fmt(sec.get('subtotal', 0))}</b>", styles["CellR"]),
            ])
            tbl = Table(rows, colWidths=[22*mm, 118*mm, 34*mm])
            tbl_style = [
                ("GRID", (0,0), (-1,-1), 0.4, BORDER),
                ("BACKGROUND", (0,0), (-1,0), RED_BG),
                ("BACKGROUND", (0,-1), (-1,-1), colors.Color(0.95, 0.85, 0.85)),
                ("VALIGN", (0,0), (-1,-1), "TOP"),
                ("TOPPADDING", (0,0), (-1,-1), 2),
                ("BOTTOMPADDING", (0,0), (-1,-1), 2),
                ("LEFTPADDING", (0,0), (-1,-1), 3),
                ("RIGHTPADDING", (0,0), (-1,-1), 3),
            ]
            tbl.setStyle(TableStyle(tbl_style))
            elems.append(tbl)
            elems.append(Spacer(1, 2*mm))

    # Summary box
    summary = report_data.get("summary", {})
    elems.append(Spacer(1, 4*mm))
    elems.append(Paragraph("<b>BETRIEBSERGEBNIS</b>", styles["SecHead"]))

    sum_rows = [
        [Paragraph("<b>Summe Einnahmen</b>", styles["TotalLabel"]),
         Paragraph(f"<b>EUR {_fmt(summary.get('total_income', 0))}</b>", styles["TotalVal"])],
        [Paragraph("<b>Summe Ausgaben</b>", styles["TotalLabel"]),
         Paragraph(f"<b>- EUR {_fmt(summary.get('total_expenses', 0))}</b>", styles["TotalVal"])],
        [Paragraph("<b>BETRIEBSERGEBNIS</b>", styles["TotalLabel"]),
         Paragraph(f"<b>EUR {_fmt(summary.get('betriebsergebnis', 0))}</b>", styles["TotalVal"])],
    ]
    st = Table(sum_rows, colWidths=[120*mm, 54*mm])
    st.setStyle(TableStyle([
        ("GRID", (0,0), (-1,-1), 0.8, HEADER_BG),
        ("BACKGROUND", (0,0), (-1,1), colors.Color(0.95, 0.97, 1.0)),
        ("BACKGROUND", (0,2), (-1,2), colors.Color(0.85, 0.90, 1.0)),
        ("TOPPADDING", (0,0), (-1,-1), 5),
        ("BOTTOMPADDING", (0,0), (-1,-1), 5),
        ("LEFTPADDING", (0,0), (-1,-1), 6),
        ("RIGHTPADDING", (0,0), (-1,-1), 6),
    ]))
    elems.append(st)

    # Footer
    elems.append(Spacer(1, 6*mm))
    elems.append(HRFlowable(width="100%", thickness=1, color=BORDER, spaceAfter=3*mm))
    elems.append(Paragraph(
        "HINWEIS: Dieser Bericht dient nur als Referenz. "
        "Alle Steuererklaerungen muessen ueber FinanzOnline eingereicht werden. "
        "Bei komplexen Faellen konsultieren Sie einen Steuerberater.",
        styles["Disclaimer"]))
    elems.append(Spacer(1, 2*mm))
    elems.append(Paragraph(
        "Erstellt von Taxja - Steuern einfach ja! | Nur als Referenz, keine Steuerberatung.",
        styles["SmallNote"]))

    doc.build(elems)
    return buf.getvalue()

